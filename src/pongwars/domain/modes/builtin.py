"""@package pongwars.domain.modes.builtin
@brief Built-in game modes: classic, timed, survival and king of the table.
"""

from typing import TYPE_CHECKING, ClassVar

from pongwars.domain import constants as c
from pongwars.domain.events import Event, SuddenDeath
from pongwars.domain.modes.base import Mode, OptionSpec, register_mode

if TYPE_CHECKING:
    from pongwars.domain.world import World


def _leader(scores: list[int]) -> int | None:
    """@brief Index of the unique top scorer, or None on a tie for first."""
    top = max(scores)
    leaders = [i for i, s in enumerate(scores) if s == top]
    return leaders[0] if len(leaders) == 1 else None


@register_mode("classic")
class ClassicMode(Mode):
    """@brief First to N points wins, optionally by a two-point margin."""

    options: ClassVar[tuple[OptionSpec, ...]] = (
        OptionSpec("points_to_win", c.DEFAULT_SCORE_LIMIT, 1, 50),
        OptionSpec("win_by_two", 0, 0, 1, "bool"),
    )

    def winner(self, world: "World") -> int | None:
        """@brief Winner once the target is reached (and the margin if required)."""
        target = self.values["points_to_win"]
        margin = 2 if self.values["win_by_two"] else 1
        for player, score in enumerate(world.scores):
            rival = max(s for i, s in enumerate(world.scores) if i != player)
            if score >= target and score - rival >= margin:
                return player
        return None


@register_mode("timed")
class TimedMode(Mode):
    """@brief Most points when time runs out; a tie goes to sudden death."""

    options: ClassVar[tuple[OptionSpec, ...]] = (OptionSpec("duration_seconds", 120, 10, 600),)

    def __init__(self, values: dict[str, int]) -> None:
        """@param values Validated option values."""
        super().__init__(values)
        self.sudden_death = False

    def on_tick(self, world: "World", events: list[Event]) -> None:
        """@brief Start sudden death when time is up and scores are level."""
        limit = self.values["duration_seconds"] * c.TICK_RATE
        if world.tick >= limit and not self.sudden_death and _leader(world.scores) is None:
            self.sudden_death = True
            events.append(SuddenDeath())

    def winner(self, world: "World") -> int | None:
        """@brief Leader at the time limit, or the first scorer in sudden death."""
        limit = self.values["duration_seconds"] * c.TICK_RATE
        if self.sudden_death or world.tick >= limit:
            return _leader(world.scores)
        return None


@register_mode("survival")
class SurvivalMode(Mode):
    """@brief Each conceded goal costs a life; the last player standing wins."""

    options: ClassVar[tuple[OptionSpec, ...]] = (OptionSpec("lives", 3, 1, 20),)

    def __init__(self, values: dict[str, int]) -> None:
        """@param values Validated option values."""
        super().__init__(values)
        self.lives: list[int] = []

    def on_goal(
        self, world: "World", scorer: int | None, conceded: int, events: list[Event]
    ) -> None:
        """@brief The conceding player loses a life and is eliminated at zero."""
        if not self.lives:
            self.lives = [self.values["lives"]] * len(world.scores)
        if scorer is not None:
            world.scores[scorer] += 1
        self.lives[conceded] -= 1
        if self.lives[conceded] <= 0:
            world.eliminate(conceded, events)

    def winner(self, world: "World") -> int | None:
        """@brief The last player still alive."""
        alive = [i for i, ok in enumerate(world.alive) if ok]
        return alive[0] if len(alive) == 1 else None


@register_mode("king")
class KingMode(Mode):
    """@brief Points come from holding the ball in the central zone, not from goals."""

    options: ClassVar[tuple[OptionSpec, ...]] = (OptionSpec("points_to_win", 10, 1, 100),)

    def __init__(self, values: dict[str, int]) -> None:
        """@param values Validated option values."""
        super().__init__(values)
        self._holder: int | None = None
        self._held_ticks = 0

    def on_goal(
        self, world: "World", scorer: int | None, conceded: int, events: list[Event]
    ) -> None:
        """@brief Goals give no points in this mode."""
        self._holder, self._held_ticks = None, 0

    def on_tick(self, world: "World", events: list[Event]) -> None:
        """@brief Accumulate zone time for the last player who touched the ball."""
        in_zone = abs(world.ball.pos.x - c.FIELD_WIDTH / 2) <= c.KING_ZONE_HALF_WIDTH
        holder = world.last_toucher
        if not in_zone or holder is None or world.phase.value != "playing":
            self._holder, self._held_ticks = None, 0
            return
        if holder != self._holder:
            self._holder, self._held_ticks = holder, 0
        self._held_ticks += 1
        if self._held_ticks >= c.KING_POINT_INTERVAL_TICKS:
            self._held_ticks = 0
            world.scores[holder] += 1

    def winner(self, world: "World") -> int | None:
        """@brief First to the target score."""
        for player, score in enumerate(world.scores):
            if score >= self.values["points_to_win"]:
                return player
        return None
