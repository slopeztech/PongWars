"""Multi-player (3 and 4 seat) arena tests (spec: arenas, game-core)."""

import pytest

from pongwars.domain import constants as c
from pongwars.domain.config import ConfigError, MatchConfig
from pongwars.domain.events import Goal, PlayerEliminated
from pongwars.domain.vec import Vec2
from pongwars.domain.world import FrameInputs, Phase, World


def _cfg(arena: str, players: int, mode: str = "classic") -> MatchConfig:
    return MatchConfig(arena=arena, mode=mode, controllers=("human",) * players, seed=3)


def test_multiplayer_seat_counts() -> None:
    assert len(World(_cfg("trident", 3)).paddles) == 3
    world = World(_cfg("crossfire", 4))
    assert [p.axis for p in world.paddles] == ["y", "y", "x", "x"]
    assert len(world.scores) == 4


def test_multiplayer_controller_mismatch() -> None:
    with pytest.raises(ConfigError) as err:
        World(_cfg("crossfire", 3))
    assert err.value.key == "error.config.player_count_mismatch"


def test_multiplayer_top_paddle_moves_along_x() -> None:
    world = World(_cfg("crossfire", 4))
    for _ in range(600):
        world.step(FrameInputs((0.0, 0.0, -1.0, 1.0)))
    assert world.paddles[2].rect.cx == c.PADDLE_HALF_HEIGHT
    assert world.paddles[3].rect.cx == c.FIELD_WIDTH - c.PADDLE_HALF_HEIGHT


def test_multiplayer_bottom_is_wall_in_three_player_arena() -> None:
    world = World(_cfg("trident", 3))
    world.phase = Phase.PLAYING
    world.ball.pos = Vec2(40, c.FIELD_HEIGHT - 0.5)
    world.ball.vel = Vec2(0.0, 1.0)
    world.step(FrameInputs())
    assert world.ball.vel.y < 0


def test_multiplayer_goal_credits_last_toucher() -> None:
    world = World(_cfg("crossfire", 4))
    world.phase = Phase.PLAYING
    world.last_toucher = 1
    world.ball.pos = Vec2(80, -5)
    world.ball.vel = Vec2(0.0, -1.0)
    events = world.step(FrameInputs())
    assert Goal(1, 2) in events
    assert world.scores[1] == 1


def test_multiplayer_own_goal_scores_nothing() -> None:
    world = World(_cfg("crossfire", 4))
    world.phase = Phase.PLAYING
    world.last_toucher = 3
    world.ball.pos = Vec2(80, c.FIELD_HEIGHT + 5)
    world.ball.vel = Vec2(0.0, 1.0)
    events = world.step(FrameInputs())
    assert Goal(None, 3) in events
    assert sum(world.scores) == 0


def test_multiplayer_survival_eliminates_and_walls_goal() -> None:
    world = World(_cfg("trident", 3, "survival"))
    events: list[object] = []
    for _ in range(world.mode.lives[0] if hasattr(world.mode, "lives") and world.mode.lives else 3):
        world.phase = Phase.PLAYING
        world.ball.pos = Vec2(-5, 45)
        world.ball.vel = Vec2(-1.0, 0.0)
        events += world.step(FrameInputs())
    assert not world.alive[0]
    assert any(isinstance(e, PlayerEliminated) for e in events)
    world.phase = Phase.PLAYING
    world.ball.pos = Vec2(0.5, 45)
    world.ball.vel = Vec2(-1.0, 0.0)
    world.step(FrameInputs())
    assert world.ball.vel.x > 0


def test_multiplayer_deterministic() -> None:
    a, b = World(_cfg("crossfire", 4)), World(_cfg("crossfire", 4))
    for _ in range(600):
        a.step(FrameInputs())
        b.step(FrameInputs())
    assert a.ball.pos == b.ball.pos and a.scores == b.scores
