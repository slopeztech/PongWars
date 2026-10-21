"""Tests for the cat weapon and the second wave of powers, weapons and penalties."""

import pytest
from test_extras import FIRE, IDLE, make_world

from pongwars.domain import constants as c
from pongwars.domain.events import (
    BallReleased,
    BallSwallowed,
    BallWarped,
    CatPounced,
    CatReleased,
    Event,
    StalkerExploded,
    WeaponEmpty,
)
from pongwars.domain.vec import Vec2
from pongwars.domain.world import FrameInputs, Phase


def arm(world, name: str, seat: int = 0, ammo: int = 2) -> None:  # type: ignore[no-untyped-def]
    world.extras.weapons[seat] = (name, ammo)


def test_cat_is_released_and_expires() -> None:
    world = make_world()
    arm(world, "cat")
    events = world.step(FIRE)
    assert any(isinstance(e, CatReleased) for e in events)
    assert len(world.extras.cats) == 1
    for _ in range(c.CAT_LIFETIME_TICKS + 5):
        world.ball.vel = Vec2(0.001, 0.0)
        world.ball.pos = Vec2(c.FIELD_WIDTH - 5, 5.0)
        world.step(IDLE)
    assert world.extras.cats == []


def test_cat_chases_and_scrambles_the_ball() -> None:
    world = make_world()
    arm(world, "cat")
    world.step(FIRE)
    ball = world.ball
    ball.pos = Vec2(c.FIELD_WIDTH / 2, c.FIELD_HEIGHT / 2)
    ball.vel = Vec2(0.01, 0.0)
    events: list[Event] = []
    for _ in range(c.TICK_RATE * 4):
        events += world.step(IDLE)
        if any(isinstance(e, CatPounced) for e in events):
            break
    assert any(isinstance(e, CatPounced) for e in events)
    assert c.BALL_MIN_SPEED <= ball.vel.length() <= c.BALL_MAX_SPEED


def test_cat_is_cleared_on_goal_reset() -> None:
    world = make_world()
    arm(world, "cat")
    world.step(FIRE)
    world.ball.pos = Vec2(-5.0, c.FIELD_HEIGHT / 2)
    world.ball.vel = Vec2(-50.0, 0.0)
    for _ in range(5):
        world.step(IDLE)
    assert world.extras.cats == []


def test_warp_moves_the_ball_keeping_velocity() -> None:
    world = make_world()
    arm(world, "warp")
    world.ball.vel = Vec2(10.0, 0.0)
    events = world.step(FIRE)
    assert any(isinstance(e, BallWarped) for e in events)
    assert world.ball.vel.x > 0.0


def test_hex_curses_the_opponent() -> None:
    world = make_world()
    arm(world, "hex", ammo=1)
    world.step(FIRE)
    assert any(e.category == "penalty" for e in world.extras.active[1])
    assert world.extras.weapons[0] is None


def test_jammed_blocks_weapons() -> None:
    world = make_world()
    arm(world, "laser", ammo=3)
    world.extras.apply_direct("jammed", 0, [])
    events = world.step(FIRE)
    assert any(isinstance(e, WeaponEmpty) for e in events)
    assert world.extras.weapons[0] == ("laser", 3)


def test_cleanse_removes_penalties() -> None:
    world = make_world()
    world.extras.apply_direct("inverted", 0, [])
    world.extras.apply_direct("big_paddle", 0, [])
    world.extras.apply("cleanse", 0, [])
    names = [e.name for e in world.extras.active[0]]
    assert names == ["big_paddle"]
    assert not world.extras.mods(0).invert


def test_slow_ball_and_turbo_ball_scale_speed() -> None:
    world = make_world()
    world.ball.vel = Vec2(100.0, 0.0)
    world.extras.apply("slow_ball", 0, [])
    assert abs(world.ball.vel.length() - 100.0 * c.SLOW_BALL_FACTOR) < 1e-6
    world.extras.apply("turbo_ball", 0, [])
    assert world.ball.vel.length() > 70.0


def test_drunk_paddle_moves_on_its_own() -> None:
    world = make_world()
    world.extras.apply_direct("drunk", 0, [])
    start = world.paddles[0].rect.cy
    for _ in range(30):
        world.step(FrameInputs())
    assert world.paddles[0].rect.cy != start


def test_aim_assist_turns_the_bounce_towards_the_opponent() -> None:
    world = make_world()
    world.extras.apply_direct("aim_assist", 0, [])
    world.phase = Phase.PLAYING
    paddle = world.paddles[0].rect
    world.paddles[1].rect.cy = 10.0
    world.ball.pos = Vec2(paddle.cx + paddle.half_w + 3.0, paddle.cy)
    world.ball.vel = Vec2(-80.0, 0.0)
    for _ in range(10):
        world.step(IDLE)
    assert world.ball.vel.x > 0.0
    assert world.ball.vel.y < 0.0


def test_stalker_chases_from_the_opposite_half_and_explodes_on_contact() -> None:
    world = make_world()
    events: list[Event] = []
    world.extras.apply_direct("stalker", 1, events)
    stalker = world.extras.stalkers[0]

    assert stalker.pos.x < c.FIELD_WIDTH / 2
    previous = stalker.pos
    for _ in range(c.TICK_RATE * 7):
        world.extras.update_stalkers(events)
        assert (stalker.pos - previous).length() <= c.STALKER_SPEED / c.TICK_RATE + 1e-9
        previous = stalker.pos
        if any(isinstance(event, StalkerExploded) for event in events):
            break

    assert any(isinstance(event, StalkerExploded) for event in events)
    assert any(effect.name == "stun" for effect in world.extras.active[1])
    assert world.extras.stalkers == []


def test_cleanse_removes_stalker_penalty_entity() -> None:
    world = make_world()
    world.extras.apply_direct("stalker", 1, [])

    world.extras.clear_penalties(1, [])

    assert world.extras.stalkers == []


def test_hungry_orb_appears_immediately_and_slows_swallowed_ball() -> None:
    world = make_world()
    ball = world.ball
    ball.vel = Vec2(60.0, -30.0)
    start = ball.pos
    velocity = ball.vel
    events: list[Event] = []
    world.extras.apply("chomper", 0, events)
    assert len(world.extras.chompers) == 1
    assert world.extras.chompers[0].phase == "roaming"

    for _ in range(c.CHOMPER_LIFETIME_TICKS):
        world.extras.update_chompers(events)
        if ball.swallowed:
            break

    assert ball.swallowed
    assert ball.vel == velocity * c.CHOMPER_BALL_SPEED_FACTOR
    assert any(isinstance(event, BallSwallowed) for event in events)
    swallowed_position = ball.pos
    world.step(IDLE)
    assert ball.pos == swallowed_position
    assert ball.vel == velocity * c.CHOMPER_BALL_SPEED_FACTOR

    for _ in range(c.CHOMPER_SWALLOW_TICKS + 1):
        world.extras.update_chompers(events)

    assert not ball.swallowed
    assert ball.pos != start
    assert ball.vel.length() == pytest.approx(
        velocity.length() * c.CHOMPER_BALL_SPEED_FACTOR
    )
    assert abs(ball.vel.x) > 0.0
    assert abs(ball.vel.y) > 0.0
    if ball.vel.y < 0.0:
        wall_time = (c.BALL_RADIUS - ball.pos.y) / ball.vel.y
    else:
        wall_time = (c.FIELD_HEIGHT - c.BALL_RADIUS - ball.pos.y) / ball.vel.y
    wall_x = ball.pos.x + ball.vel.x * wall_time
    assert wall_time > 0.0
    assert c.BALL_RADIUS <= wall_x <= c.FIELD_WIDTH - c.BALL_RADIUS
    assert any(isinstance(event, BallReleased) for event in events)
    assert world.extras.chompers[0].phase == "releasing"


def test_hungry_orb_roams_randomly_for_two_to_three_seconds() -> None:
    world = make_world()
    world.extras.apply("chomper", 0, [])
    chomper = world.extras.chompers[0]
    assert c.CHOMPER_ROAM_MIN_TICKS <= chomper.phase_ticks <= c.CHOMPER_ROAM_MAX_TICKS
    assert chomper.phase == "roaming"
    assert chomper.target is not None

    start = chomper.pos
    distance_travelled = 0.0
    previous = chomper.pos
    for _ in range(c.CHOMPER_ROAM_MAX_TICKS):
        world.extras.update_chompers([])
        distance_travelled += (chomper.pos - previous).length()
        previous = chomper.pos
        if chomper.phase != "roaming":
            break

    assert c.CHOMPER_ROAM_MIN_TICKS <= _ + 1 <= c.CHOMPER_ROAM_MAX_TICKS
    assert (chomper.pos - start).length() > 5.0
    assert distance_travelled > 20.0
    assert chomper.phase == "seeking"
