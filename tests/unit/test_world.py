"""World simulation tests (spec: game-core)."""

import pytest

from pongwars.domain import constants as c
from pongwars.domain.config import MatchConfig
from pongwars.domain.entities import Obstacle, Rect
from pongwars.domain.events import Goal, MatchEnded, PaddleHit, Served, WallHit
from pongwars.domain.vec import Vec2
from pongwars.domain.world import FrameInputs, Phase, World

IDLE = FrameInputs()


def _run_until(world: World, kind: type, max_ticks: int = 2000) -> list[object]:
    for _ in range(max_ticks):
        events = world.step(IDLE)
        if any(isinstance(e, kind) for e in events):
            return list(events)
    raise AssertionError(f"no {kind.__name__} within {max_ticks} ticks")


def test_game_core_serves_after_delay() -> None:
    world = World(MatchConfig(seed=1))
    assert world.phase.value == "serving"
    _run_until(world, Served)
    assert world.phase.value == "playing"
    assert abs(world.ball.vel.length() - c.BALL_START_SPEED) < 1e-6


def test_game_core_paddle_moves_and_is_clamped() -> None:
    world = World(MatchConfig())
    for _ in range(600):
        world.step(FrameInputs((-1.0, 1.0)))
    assert world.paddles[0].rect.cy == c.PADDLE_HALF_HEIGHT
    assert world.paddles[1].rect.cy == c.FIELD_HEIGHT - c.PADDLE_HALF_HEIGHT


def test_game_core_ball_bounces_off_paddle() -> None:
    world = World(MatchConfig(seed=2))
    world.phase = Phase.PLAYING
    world.ball.pos = Vec2(20, world.paddles[0].rect.cy)
    world.ball.vel = Vec2(-c.BALL_START_SPEED, 0)
    events = _run_until(world, PaddleHit)
    assert PaddleHit(0) in events
    assert world.ball.vel.x > 0
    assert world.ball.vel.length() > c.BALL_START_SPEED


def test_ball_physics_ordinary_hit_speedup_is_random_and_bounded() -> None:
    world = World(MatchConfig(seed=4))
    ball = world.ball
    ball.vel = Vec2(c.BALL_START_SPEED, 0.0)
    speeds = []

    for _ in range(10):
        previous_speed = ball.vel.length()
        world._paddle_bounce(ball, 0, Vec2(1.0, 0.0))
        speeds.append(ball.vel.length())
        factor = ball.vel.length() / previous_speed
        assert factor >= c.BALL_HIT_SPEEDUP_MIN
        assert factor <= c.BALL_HIT_SPEEDUP_MAX

    assert len(set(speeds)) > 1


def test_ball_physics_ordinary_hit_speedup_is_deterministic() -> None:
    def hit_speeds(seed: int) -> list[float]:
        world = World(MatchConfig(seed=seed))
        ball = world.ball
        ball.vel = Vec2(c.BALL_START_SPEED, 0.0)
        speeds = []
        for _ in range(10):
            world._paddle_bounce(ball, 0, Vec2(1.0, 0.0))
            speeds.append(ball.vel.length())
        return speeds

    assert hit_speeds(12) == hit_speeds(12)


def test_ball_physics_paddle_hit_speedup_respects_maximum() -> None:
    world = World(MatchConfig(seed=2))
    world.ball.vel = Vec2(c.BALL_MAX_SPEED, 0.0)

    world._paddle_bounce(world.ball, 0, Vec2(1.0, 0.0))

    assert world.ball.vel.length() == pytest.approx(c.BALL_MAX_SPEED)


def test_game_core_paddle_edge_hit_deflects_ball() -> None:
    world = World(MatchConfig())
    world.phase = Phase.PLAYING
    rect = world.paddles[0].rect
    world.ball.pos = Vec2(20, rect.cy + rect.half_h)
    world.ball.vel = Vec2(-c.BALL_START_SPEED, 0)
    _run_until(world, PaddleHit)
    assert world.ball.vel.y > 0


def test_game_core_ball_bounces_off_border_and_wall() -> None:
    world = World(MatchConfig(), obstacles=[Obstacle(Rect(80, 45, 2, 10))])
    world.phase = Phase.PLAYING
    world.ball.pos = Vec2(60, 5)
    world.ball.vel = Vec2(0, -50)
    _run_until(world, WallHit)
    assert world.ball.vel.y > 0
    world.ball.pos = Vec2(70, 45)
    world.ball.vel = Vec2(c.BALL_START_SPEED, 0)
    _run_until(world, WallHit)
    assert world.ball.vel.x < 0


def test_game_core_goal_scores_and_ends_match() -> None:
    world = World(MatchConfig(options=(("points_to_win", 1),), seed=3))
    world.phase = Phase.PLAYING
    world.ball.pos = Vec2(c.FIELD_WIDTH - 12, 5)
    world.ball.vel = Vec2(c.BALL_START_SPEED, 0)
    events = _run_until(world, Goal)
    assert Goal(0, 1) in events
    assert MatchEnded(0) in events
    assert world.phase is Phase.FINISHED
    assert world.winner == 0
    assert world.step(IDLE) == []


def test_game_core_goal_reserves_next_serve() -> None:
    world = World(MatchConfig(options=(("points_to_win", 5),), seed=3))
    world.phase = Phase.PLAYING
    world.ball.pos = Vec2(12, 5)
    world.ball.vel = Vec2(-c.BALL_START_SPEED, 0)
    _run_until(world, Goal)
    assert world.scores == [0, 1]
    assert world.phase is Phase.SERVING


def test_game_core_is_deterministic() -> None:
    def play(seed: int) -> tuple[list[int], float, float, int]:
        world = World(MatchConfig(seed=seed, options=(("points_to_win", 3),)))
        for i in range(3000):
            world.step(FrameInputs((1.0 if i % 90 < 45 else -1.0, 0.0)))
        return world.scores, world.ball.pos.x, world.ball.pos.y, world.tick

    assert play(7) == play(7)
