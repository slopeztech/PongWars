"""Tests for pickups, powers, weapons and penalties."""

import pytest

from pongwars.domain import constants as c
from pongwars.domain.config import ConfigError, MatchConfig
from pongwars.domain.entities import Ball, Obstacle, Rect
from pongwars.domain.events import (
    EffectApplied,
    EffectExpired,
    Event,
    Goal,
    PickupCollected,
    PickupSpawned,
    ShieldUsed,
    WeaponEmpty,
)
from pongwars.domain.extras import EFFECTS, load_specs
from pongwars.domain.vec import Vec2
from pongwars.domain.world import FrameInputs, Phase, World

IDLE = FrameInputs()
FIRE = FrameInputs((0.0, 0.0), (True, False))


def make_world(**kwargs: object) -> World:
    world = World(MatchConfig(extras=("all",), seed=3, **kwargs))  # type: ignore[arg-type]
    world.phase = Phase.PLAYING
    world.ball.vel = Vec2()
    world.ball.pos = Vec2(c.FIELD_WIDTH / 2, c.FIELD_HEIGHT / 2)
    return world


def test_every_spec_has_an_effect_class() -> None:
    for name in load_specs():
        assert EFFECTS.get(name).name == name


def test_unknown_extra_is_rejected() -> None:
    with pytest.raises(ConfigError):
        World(MatchConfig(extras=("nope",)))


def test_extras_disabled_never_spawn() -> None:
    world = World(MatchConfig(seed=1))
    world.phase = Phase.PLAYING
    for _ in range(c.TICK_RATE * 30):
        world.ball.vel = Vec2()
        world.step(IDLE)
    assert world.extras.pickups == []


def test_pickups_spawn_and_are_deterministic() -> None:
    def run() -> list[tuple[float, float, str]]:
        world = make_world(extras_interval=1.0)
        for _ in range(c.TICK_RATE * 5):
            world.ball.vel = Vec2()
            world.step(IDLE)
        return [(p.pos.x, p.pos.y, p.name) for p in world.extras.pickups]

    first = run()
    assert first and first == run()
    assert len(first) <= c.PICKUP_MAX_ON_TABLE


def test_spawn_event_and_collection_by_last_toucher() -> None:
    world = make_world(extras_interval=0.5)
    events: list[Event] = []
    for _ in range(c.TICK_RATE):
        world.ball.vel = Vec2()
        events += world.step(IDLE)
    assert any(isinstance(e, PickupSpawned) for e in events)
    pickup = world.extras.pickups[0]
    world.ball.pos = pickup.pos
    events = world.step(IDLE)
    assert not any(isinstance(e, PickupCollected) for e in events)
    world.ball.toucher = 1
    events = world.step(IDLE)
    assert PickupCollected(1, pickup.name) in events


def test_pickups_avoid_obstacles() -> None:
    wall = Obstacle(Rect(c.FIELD_WIDTH / 2, c.FIELD_HEIGHT / 2, 30.0, 30.0))
    world = World(MatchConfig(extras=("all",), extras_interval=0.2), obstacles=[wall])
    world.phase = Phase.PLAYING
    for _ in range(c.TICK_RATE * 3):
        world.ball.vel = Vec2()
        world.step(IDLE)
    assert all(
        abs(p.pos.x - wall.rect.cx) > 30.0 or abs(p.pos.y - wall.rect.cy) > 30.0
        for p in world.extras.pickups
    )


def test_big_paddle_grows_and_expires() -> None:
    world = make_world()
    base = world.paddles[0].rect.half_h
    world.extras.apply("big_paddle", 0, [])
    world.step(IDLE)
    assert world.paddles[0].rect.half_h > base
    events: list[Event] = []
    for _ in range(world.extras.specs["big_paddle"].ticks + 2):
        events += world.step(IDLE)
    assert world.paddles[0].rect.half_h == pytest.approx(base)
    assert EffectExpired(0, "big_paddle") in events


def test_inverted_controls_reverse_movement() -> None:
    world = make_world()
    start = world.paddles[0].rect.cy
    world.extras.apply("inverted", 0, [])
    world.step(FrameInputs((1.0, 0.0)))
    assert world.paddles[0].rect.cy < start


def test_frozen_paddle_does_not_move() -> None:
    world = make_world()
    start = world.paddles[0].rect.cy
    world.extras.apply("frozen", 0, [])
    world.step(FrameInputs((1.0, 0.0)))
    assert world.paddles[0].rect.cy == start


def test_speed_boost_moves_faster() -> None:
    plain, boosted = make_world(), make_world()
    boosted.extras.apply("speed_boost", 0, [])
    plain.step(FrameInputs((1.0, 0.0)))
    boosted.step(FrameInputs((1.0, 0.0)))
    assert boosted.paddles[0].rect.cy > plain.paddles[0].rect.cy


def test_penalty_target_opponents() -> None:
    world = make_world(penalty_target="opponents")
    events: list[Event] = []
    world.extras.apply("small_paddle", 0, events)
    assert EffectApplied(1, "small_paddle") in events
    assert not world.extras.active[0]


def test_reapplying_refreshes_instead_of_stacking() -> None:
    world = make_world()
    world.extras.apply("big_paddle", 0, [])
    for _ in range(30):
        world.step(IDLE)
    world.extras.apply("big_paddle", 0, [])
    assert len(world.extras.active[0]) == 1
    assert world.extras.active[0][0].remaining == world.extras.specs["big_paddle"].ticks


def test_active_cap_drops_oldest() -> None:
    world = make_world(extras_max_active=2)
    events: list[Event] = []
    for name in ("big_paddle", "speed_boost", "slow_paddle"):
        world.extras.apply(name, 0, events)
    assert [e.name for e in world.extras.active[0]] == ["speed_boost", "slow_paddle"]
    assert EffectExpired(0, "big_paddle") in events


def test_multiball_adds_balls_up_to_cap() -> None:
    world = make_world()
    world.ball.vel = Vec2(40.0, 10.0)
    world.extras.apply("multiball", 0, [])
    assert len(world.balls) == 3
    world.extras.apply("multiball", 0, [])
    assert len(world.balls) == c.MAX_BALLS


def test_extra_ball_goal_keeps_match_playing() -> None:
    world = make_world()
    world.ball.vel = Vec2(0.0, 0.0)
    extra = Ball(Vec2(-5.0, 45.0), Vec2(-20.0, 0.0), c.BALL_RADIUS, toucher=1)
    world.extra_balls.append(extra)
    events = world.step(IDLE)
    assert any(isinstance(e, Goal) for e in events)
    assert world.extra_balls == []
    assert world.phase is Phase.PLAYING


def test_shield_absorbs_one_goal() -> None:
    world = make_world()
    world.extras.apply("shield", 0, [])
    world.ball.pos = Vec2(-4.0, 45.0)
    world.ball.vel = Vec2(-20.0, 0.0)
    events = world.step(IDLE)
    assert ShieldUsed(0) in events
    assert not any(isinstance(e, Goal) for e in events)
    assert world.ball.vel.x > 0
    assert world.scores == [0, 0]
    assert not world.extras.active[0]


def test_laser_stuns_opponent_and_runs_out_of_ammo() -> None:
    world = make_world()
    world.paddles[1].rect.cy = world.paddles[0].rect.cy
    world.extras.apply("laser", 0, [])
    ammo = world.extras.specs["laser"].ammo
    for shot in range(ammo):
        world.step(IDLE)
        events = world.step(FIRE)
        assert any(type(e).__name__ == "LaserFired" for e in events), shot
    assert any(e.name == "stun" for e in world.extras.active[1])
    world.step(IDLE)
    assert WeaponEmpty(0) in world.step(FIRE)


def test_fire_without_weapon_reports_empty() -> None:
    world = make_world()
    assert WeaponEmpty(0) in world.step(FIRE)


def test_freeze_weapon_freezes_target() -> None:
    world = make_world()
    world.extras.apply("freeze", 0, [])
    world.step(FIRE)
    assert any(e.name == "frozen" for e in world.extras.active[1])


def test_bomb_pushes_nearby_ball() -> None:
    world = make_world()
    world.ball.vel = Vec2(1.0, 0.0)
    world.ball.pos = Vec2(world.paddles[0].rect.cx + 10.0, world.paddles[0].rect.cy)
    world.extras.apply("bomb", 0, [])
    world.step(FIRE)
    assert world.ball.vel.length() > 1.0
    assert world.ball.vel.x > 0


def test_laser_damages_destructible_obstacle() -> None:
    wall = Obstacle(Rect(40.0, 45.0, 2.0, 40.0), kind="destructible", hp=1)
    world = World(MatchConfig(extras=("all",)), obstacles=[wall])
    world.phase = Phase.PLAYING
    world.paddles[0].rect.cy = 45.0
    world.extras.apply("laser", 0, [])
    world.step(FIRE)
    assert not wall.active


def test_magnet_holds_ball_until_fire() -> None:
    world = make_world()
    world.extras.apply("magnet", 1, [])
    paddle = world.paddles[1].rect
    world.ball.pos = Vec2(paddle.cx - 3.0, paddle.cy)
    world.ball.vel = Vec2(60.0, 0.0)
    for _ in range(10):
        world.step(IDLE)
        if world.ball.held_by is not None:
            break
    assert world.ball.held_by == 1
    held_x = world.ball.pos.x
    world.step(IDLE)
    assert world.ball.pos.x == pytest.approx(held_x)
    world.step(FrameInputs((0.0, 0.0), (False, True)))
    assert world.ball.held_by is None
    assert world.ball.vel.x < 0


def test_magnet_releases_on_timeout() -> None:
    world = make_world()
    world.extras.apply("magnet", 1, [])
    paddle = world.paddles[1].rect
    world.ball.pos = Vec2(paddle.cx - 3.0, paddle.cy)
    world.ball.vel = Vec2(60.0, 0.0)
    for _ in range(10):
        world.step(IDLE)
    for _ in range(c.MAGNET_HOLD_TICKS + 2):
        world.step(IDLE)
    assert world.ball.held_by is None


def test_config_round_trip_with_extras() -> None:
    config = MatchConfig(extras=("power", "laser"), extras_interval=5.0, penalty_target="opponents")
    assert MatchConfig.from_json(config.to_json()) == config


@pytest.mark.parametrize(
    "kwargs",
    [{"extras_interval": 0.0}, {"extras_max_active": 0}, {"penalty_target": "nobody"}],
)
def test_invalid_extras_config(kwargs: dict[str, object]) -> None:
    with pytest.raises(ConfigError):
        MatchConfig(**kwargs)  # type: ignore[arg-type]
