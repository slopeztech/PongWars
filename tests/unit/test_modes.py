"""Tests for pluggable game modes."""

import pytest

from pongwars.domain import constants as c
from pongwars.domain.config import ConfigError, MatchConfig
from pongwars.domain.events import Goal, MatchEnded, SuddenDeath
from pongwars.domain.modes import MODES, Mode, register_mode
from pongwars.domain.vec import Vec2
from pongwars.domain.world import FrameInputs, Phase, World


def _world(mode: str, **options: float) -> World:
    return World(MatchConfig(mode=mode, options=tuple(options.items())), obstacles=[])


def _goal(world: World, scorer: int) -> list[object]:
    """Force a goal for `scorer` by placing the ball past the opposite line."""
    world.phase = Phase.PLAYING
    x = c.FIELD_WIDTH + 5 if scorer == 0 else -5
    world.ball.pos = Vec2(x, 45)
    world.ball.vel = Vec2(1.0 if scorer == 0 else -1.0, 0.0)
    return list(world.step(FrameInputs()))


def test_game_modes_builtin_registered() -> None:
    assert {"classic", "timed", "survival", "king"} <= set(MODES.names())


def test_game_modes_option_validation() -> None:
    with pytest.raises(ConfigError) as unknown:
        _world("classic", nope=1)
    assert unknown.value.key == "error.config.unknown_option"
    with pytest.raises(ConfigError) as rng:
        _world("classic", points_to_win=0)
    assert rng.value.key == "error.config.option_out_of_range"
    with pytest.raises(ConfigError) as mode:
        _world("missing")
    assert mode.value.key == "error.config.unknown_mode"


def test_game_modes_classic_points_to_win() -> None:
    world = _world("classic", points_to_win=1)
    events = _goal(world, 0)
    assert any(isinstance(e, MatchEnded) for e in events)
    assert world.winner == 0


def test_game_modes_classic_win_by_two() -> None:
    world = _world("classic", points_to_win=1, win_by_two=1)
    _goal(world, 0)
    assert world.winner is None
    _goal(world, 0)
    assert world.winner == 0


def test_game_modes_timed_leader_wins_and_tie_goes_sudden_death() -> None:
    world = _world("timed", duration_seconds=10)
    _goal(world, 1)
    world.tick = 10 * c.TICK_RATE
    world.step(FrameInputs())
    assert world.winner == 1

    tied = _world("timed", duration_seconds=10)
    tied.tick = 10 * c.TICK_RATE
    events = tied.step(FrameInputs())
    assert any(isinstance(e, SuddenDeath) for e in events)
    assert tied.winner is None
    _goal(tied, 0)
    assert tied.winner == 0


def test_game_modes_survival_lives() -> None:
    world = _world("survival", lives=2)
    assert isinstance(world.mode, Mode)
    _goal(world, 0)
    assert world.winner is None
    _goal(world, 0)
    assert world.winner == 0


def test_game_modes_king_scores_from_zone_not_goals() -> None:
    world = _world("king", points_to_win=1)
    _goal(world, 0)
    assert world.scores == [0, 0]
    world.phase = Phase.PLAYING
    world.last_toucher = 1
    world.ball.pos = Vec2(c.FIELD_WIDTH / 2, 45)
    world.ball.vel = Vec2()
    for _ in range(c.KING_POINT_INTERVAL_TICKS):
        world.step(FrameInputs())
    assert world.winner == 1


def test_game_modes_king_awards_point_during_normal_zone_crossing() -> None:
    world = _world("king", points_to_win=10)
    world.phase = Phase.PLAYING
    world.last_toucher = 0
    world.ball.pos = Vec2(c.FIELD_WIDTH / 2 - c.KING_ZONE_HALF_WIDTH - 2, c.FIELD_HEIGHT / 2)
    world.ball.vel = Vec2(c.BALL_START_SPEED, 0)

    for _ in range(c.KING_POINT_INTERVAL_TICKS + 2):
        world.step(FrameInputs())

    assert world.scores == [1, 0]


def test_game_modes_custom_mode_registration() -> None:
    @register_mode("first_goal")
    class FirstGoal(Mode):
        def winner(self, world: World) -> int | None:
            return 0 if world.scores[0] else (1 if world.scores[1] else None)

    try:
        world = _world("first_goal")
        _goal(world, 1)
        assert world.winner == 1
    finally:
        MODES.remove("first_goal")
    assert "first_goal" not in MODES


def test_game_modes_goal_event_emitted() -> None:
    assert any(isinstance(e, Goal) for e in _goal(_world("classic"), 0))
