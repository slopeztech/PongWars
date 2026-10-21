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
    LaserFired,
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


def test_ramp_only_spawns_in_two_player_matches() -> None:
    duel = World(MatchConfig(extras=("ramp",), seed=3))
    three_player = World(
        MatchConfig(
            arena="trident",
            controllers=("human", "human", "human"),
            extras=("ramp",),
            seed=3,
        )
    )

    assert duel.extras.spawn_names == ["ramp"]
    assert three_player.extras.spawn_names == []


def test_invasor_moves_slowly_and_fires_at_most_five_slow_bombs() -> None:
    world = make_world()
    events: list[Event] = []
    world.extras.apply_direct("invasor", 1, events)
    invader = world.extras.invaders[0]
    start = invader.pos

    assert invader.pos.x < c.FIELD_WIDTH / 2
    for _ in range(c.INVADER_FIRE_INTERVAL_TICKS * 6):
        world.tick += 1
        previous = invader.pos
        world.extras.update_invaders()
        assert (invader.pos - previous).length() <= c.INVADER_SPEED / c.TICK_RATE + 1e-9

    assert invader.pos != start
    assert invader.bombs_left == 0
    assert len(world.extras.missiles) == c.INVADER_BOMBS_PER_EFFECT
    assert all(m.target == 1 for m in world.extras.missiles)
    assert all(m.vel.length() == pytest.approx(c.INVADER_BOMB_SPEED) for m in world.extras.missiles)


def test_cleansing_invasor_removes_the_npc() -> None:
    world = make_world()
    world.extras.apply_direct("invasor", 1, [])

    world.extras.clear_penalties(1, [])

    assert world.extras.invaders == []


def test_laser_event_identifies_paddle_hit() -> None:
    world = make_world()
    world.paddles[1].rect.cy = world.paddles[0].rect.cy
    world.extras.weapons[0] = ("laser", 1)
    events: list[Event] = []

    world.extras.fire(0, events)

    laser = next(event for event in events if isinstance(event, LaserFired))
    assert laser.target == 1


@pytest.mark.parametrize(
    ("target", "initial_vx", "expected"),
    [
        (0, 20.0, "slower"),
        (0, -20.0, "faster"),
        (1, -20.0, "slower"),
        (1, 20.0, "faster"),
    ],
)
def test_ramp_accelerates_downhill_and_slows_uphill(
    target: int, initial_vx: float, expected: str
) -> None:
    world = make_world()
    world.ball.pos = Vec2(c.FIELD_WIDTH / 2, c.FIELD_HEIGHT / 2)
    world.ball.vel = Vec2(initial_vx, 0.0)
    world.extras.apply_direct("ramp", target, [])

    for _ in range(12):
        world.step(IDLE)

    if expected == "slower":
        assert abs(world.ball.vel.x) < abs(initial_vx)
    else:
        assert abs(world.ball.vel.x) > abs(initial_vx)


def test_ramp_incline_eases_in_and_out() -> None:
    world = make_world()
    world.extras.apply_direct("ramp", 0, [])
    assert world.ramp_incline == 0.0

    for _ in range(round(c.RAMP_TRANSITION_SECONDS * c.TICK_RATE) // 2):
        world.extras.tick_effects([])
    assert 0.0 < world.ramp_incline < world.extras.specs["ramp"].magnitude

    effect = world.extras.active[0][0]
    effect.remaining = round(c.RAMP_TRANSITION_SECONDS * c.TICK_RATE) // 2
    assert 0.0 < world.ramp_incline < world.extras.specs["ramp"].magnitude
    effect.remaining = 1
    assert world.ramp_incline < 0.001


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
    wall = Obstacle(Rect(c.FIELD_WIDTH / 2, c.FIELD_HEIGHT / 2, 20.0, 20.0))
    world = World(MatchConfig(extras=("all",), extras_interval=0.2), obstacles=[wall])
    world.phase = Phase.PLAYING
    for _ in range(c.TICK_RATE * 3):
        world.ball.vel = Vec2()
        world.step(IDLE)
    assert all(
        abs(p.pos.x - wall.rect.cx) > 20.0 or abs(p.pos.y - wall.rect.cy) > 20.0
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


@pytest.mark.parametrize("target_count", (2, 3, 4))
def test_multiball_randomly_sets_ball_count_between_two_and_four(
    monkeypatch: pytest.MonkeyPatch, target_count: int
) -> None:
    world = make_world()
    world.ball.vel = Vec2(40.0, 10.0)
    calls: list[tuple[int, int]] = []

    def random_count(low: int, high: int) -> int:
        calls.append((low, high))
        return target_count

    monkeypatch.setattr(world.rng, "randint", random_count)

    world.extras.apply("multiball", 0, [])
    assert len(world.balls) == target_count
    assert calls == [(2, c.MAX_BALLS)]


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


def test_player_zero_can_release_magnet_with_fire_input() -> None:
    world = make_world()
    world.ball.held_by = 0
    world.ball.stored_vel = Vec2(60.0, 0.0)
    world.ball.hold_ticks = c.MAGNET_HOLD_TICKS

    world.step(FrameInputs((0.0, 0.0), (True, False)))

    assert world.ball.held_by is None


def test_magnet_releases_on_timeout() -> None:
    world = make_world()
    world.ball.held_by = 1
    world.ball.stored_vel = Vec2(-60.0, 0.0)
    world.ball.hold_ticks = c.MAGNET_HOLD_TICKS
    for _ in range(c.MAGNET_HOLD_TICKS - 1):
        world.step(IDLE)
    assert world.ball.held_by == 1
    world.step(IDLE)
    assert world.ball.held_by is None
    assert c.MAGNET_HOLD_TICKS == 3 * c.TICK_RATE


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
