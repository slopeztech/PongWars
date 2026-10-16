"""Regression coverage for ball spin, score-gap pickups and new extras."""

import math

import pytest

from pongwars.audio.player import AudioPlayer, load_bank
from pongwars.audio.synth import render_tone
from pongwars.domain import constants as c
from pongwars.domain.config import MatchConfig
from pongwars.domain.entities import Missile, Obstacle, Rect
from pongwars.domain.events import (
    BombDetonated,
    EffectApplied,
    Event,
    MissileHit,
    ObstacleDestroyed,
    PaddleHit,
    SpinHit,
    WallHit,
)
from pongwars.domain.extras import Pickup
from pongwars.domain.vec import Vec2
from pongwars.domain.world import FrameInputs, Phase, World
from pongwars.net import snapshot
from pongwars.net.protocol import Input, from_dict, to_dict


def make_world(**kwargs: object) -> World:
    world = World(MatchConfig(extras=("all",), seed=13, **kwargs))  # type: ignore[arg-type]
    world.phase = Phase.PLAYING
    world.ball.pos = Vec2(c.FIELD_WIDTH / 2, c.FIELD_HEIGHT / 2)
    world.ball.vel = Vec2()
    return world


@pytest.mark.parametrize(("move", "expected_sign"), [(1.0, 1), (-1.0, -1)])
def test_spin_changes_rebound_direction_and_increases_ball_speed(
    move: float, expected_sign: int
) -> None:
    world = make_world()
    world.ball.pos = Vec2(10.0, world.paddles[0].rect.cy)
    world.ball.vel = Vec2(-60.0, 0.0)

    events = world.step(FrameInputs((move, 0.0), (False, False), (True, False)))

    assert world.ball.vel.length() == pytest.approx(60.0 * c.SPIN_SPEED_FACTOR)
    assert world.ball.vel.length() > 60.0
    assert math.copysign(1.0, world.ball.vel.y) == expected_sign
    assert math.copysign(1.0, world.ball.spin_rate) == expected_sign
    assert SpinHit(0) in events
    slope_before = world.ball.vel.y / world.ball.vel.x
    start_y = world.ball.pos.y
    for _ in range(30):
        world.step(FrameInputs())
    slope_after = world.ball.vel.y / world.ball.vel.x
    assert math.copysign(1.0, slope_after - slope_before) == expected_sign
    assert math.copysign(1.0, world.ball.pos.y - start_y) == expected_sign
    before = world.ball.rotation
    world.step(FrameInputs((0.0, 0.0)))
    assert world.ball.rotation != before


def test_spin_ends_after_the_ball_bounces_once() -> None:
    world = make_world()
    world.ball.pos = Vec2(c.FIELD_WIDTH / 2, c.BALL_RADIUS + 0.05)
    world.ball.vel = Vec2(20.0, -10.0)
    world.ball.spin_rate = c.SPIN_ROTATION_RATE

    events = world.step(FrameInputs())

    assert WallHit() in events
    assert world.ball.spin_rate == 0.0


def test_ball_hit_without_spin_key_does_not_apply_spin() -> None:
    world = make_world()
    world.ball.pos = Vec2(10.0, world.paddles[0].rect.cy)
    world.ball.vel = Vec2(-60.0, 0.0)

    world.step(FrameInputs((1.0, 0.0)))

    assert world.ball.spin_rate == 0.0


def test_score_gap_spawns_paddle_targeted_pickups_with_reduced_duration() -> None:
    world = make_world()
    world.scores[:] = [0, 3]
    world.extras._spawn_timer = 10_000
    world.extras._comeback_timer = 1
    world.extras.update_pickups([])

    assert len(world.extras.pickups) == 1
    assert world.extras.pickups[0].target in (0, 1)
    assert all(pickup.reduced for pickup in world.extras.pickups)

    world.extras.pickups = [
        Pickup(
            Vec2(world.paddles[0].rect.cx, world.paddles[0].rect.cy),
            "big_paddle",
            60,
            target=0,
            reduced=True,
        )
    ]
    applied: list[Event] = []
    world.extras.update_pickups(applied)

    assert EffectApplied(0, "big_paddle") in applied
    assert world.extras.active[0][0].remaining == round(5.0 * c.TICK_RATE)

    leader = world.paddles[1].rect
    world.extras.pickups = [
        Pickup(Vec2(leader.cx, leader.cy), "slow_paddle", 60, target=1, reduced=True)
    ]
    penalties: list[Event] = []
    world.extras.update_pickups(penalties)
    assert EffectApplied(1, "slow_paddle") in penalties
    assert world.extras.active[1][0].remaining == round(3.0 * c.TICK_RATE)
    assert world.extras.active[1][0].spec.magnitude == pytest.approx(0.8)


def test_comeback_pickups_alternate_and_remain_spaced() -> None:
    world = make_world()
    world.scores[:] = [0, 3]
    world.extras._spawn_timer = 10_000
    world.extras._comeback_timer = 1

    world.extras.update_pickups([])
    aid = world.extras.pickups[0]
    assert aid.target == 0
    assert world.extras.specs[aid.name].category in ("power", "weapon")

    world.extras.pickups.clear()
    world.extras._comeback_timer = 1
    world.extras.update_pickups([])
    penalty = world.extras.pickups[0]
    assert penalty.target == 1
    assert world.extras.specs[penalty.name].category == "penalty"
    assert world.extras._blocked(
        penalty.pos + Vec2(c.PICKUP_MIN_SEPARATION - 0.1, 0.0)
    )
    assert not world.extras._blocked(
        penalty.pos + Vec2(c.PICKUP_MIN_SEPARATION + 0.1, 0.0)
    )


def test_pickup_spawning_never_exceeds_two_on_the_table() -> None:
    world = make_world(extras_interval=0.5)
    world.extras.pickups = [
        Pickup(Vec2(40.0, 20.0), "shield", 60),
        Pickup(Vec2(120.0, 70.0), "shield", 60),
    ]
    world.extras._spawn_timer = 1
    world.extras._comeback_timer = 10_000

    world.extras.update_pickups([])

    assert len(world.extras.pickups) == c.PICKUP_MAX_ON_TABLE == 2


def test_companion_tracks_ball_and_can_return_it() -> None:
    world = make_world()
    world.extras.apply("companion", 0, [])
    companion = world.extras.companions[0]
    world.ball.pos = Vec2(20.5, companion.paddle.rect.cy)
    world.ball.vel = Vec2(-60.0, 0.0)

    events = world.step(FrameInputs())

    assert PaddleHit(0) in events
    assert world.ball.vel.x > 0
    assert companion.ttl < c.COMPANION_LIFETIME_TICKS


def test_companion_is_pushed_slowly_when_owner_touches_it() -> None:
    world = make_world()
    world.extras.apply("companion", 0, [])
    companion = world.extras.companions[0]
    owner = world.paddles[0]
    companion.paddle.rect.cy = owner.rect.cy
    before = companion.paddle.rect.cy
    world.start_headbutt(0)

    world.extras.update_companions()

    assert companion.paddle.rect.cy > before


def test_headbutt_lunges_forward_and_returns() -> None:
    world = make_world()
    start = world.paddles[0].rect.cx
    world.extras.apply("headbutt", 0, [])

    world.step(FrameInputs((0.0, 0.0), (True, False)))
    lunged = world.paddles[0].rect.cx
    for _ in range(c.HEADBUTT_RETURN_TICKS):
        world.step(FrameInputs())

    assert lunged > start
    assert world.paddles[0].rect.cx == pytest.approx(start)


def test_headbutt_hit_delivers_a_fast_smash() -> None:
    world = make_world()
    world.extras.apply("headbutt", 0, [])
    world.ball.pos = Vec2(19.5, world.paddles[0].rect.cy)
    world.ball.vel = Vec2(-80.0, 0.0)

    events = world.step(FrameInputs(fire=(True, False)))

    assert PaddleHit(0) in events
    assert world.ball.vel.length() == pytest.approx(80.0 * c.HEADBUTT_HIT_SPEED_FACTOR)


def test_missile_destroys_destructible_obstacle() -> None:
    obstacle = Obstacle(Rect(30.0, 45.0, 1.0, 15.0), "destructible", hp=1)
    world = make_world()
    world.obstacles = [obstacle]
    world.extras.apply("missile", 0, [])

    events = world.step(FrameInputs((0.0, 0.0), (True, False)))
    for _ in range(20):
        events.extend(world.step(FrameInputs()))

    assert ObstacleDestroyed(0) in events
    assert any(isinstance(event, MissileHit) and event.target is None for event in events)
    assert not world.extras.missiles


@pytest.mark.parametrize("kind", ["solid", "bumper"])
def test_missile_destroys_any_arena_obstacle(kind: str) -> None:
    obstacle = Obstacle(Rect(30.0, 45.0, 1.0, 15.0), kind)
    world = make_world()
    world.obstacles = [obstacle]
    world.extras.apply("missile", 0, [])

    events = world.step(FrameInputs((0.0, 0.0), (True, False)))
    for _ in range(20):
        events.extend(world.step(FrameInputs()))

    assert not obstacle.active
    assert any(isinstance(event, ObstacleDestroyed) for event in events)
    assert any(isinstance(event, MissileHit) and event.target is None for event in events)


def test_bomb_detonation_event_contains_blast_position() -> None:
    world = make_world()
    world.extras.apply("bomb", 0, [])
    events = world.step(FrameInputs(fire=(True, False)))

    detonation = next(event for event in events if isinstance(event, BombDetonated))
    assert detonation.x == pytest.approx(world.paddles[0].rect.cx)
    assert detonation.y == pytest.approx(world.paddles[0].rect.cy)


def test_bomb_sound_uses_dedicated_explosion_synthesis() -> None:
    bank = load_bank()

    assert bank.sounds["bomb"].wave == "explosion"
    samples = render_tone(bank.sounds["bomb"])
    assert len(samples) > 0
    assert max(samples) > 0
    assert min(samples) < 0


def test_missile_stuns_opponent() -> None:
    world = make_world()
    world.obstacles = []
    world.paddles[1].rect.cy = world.paddles[0].rect.cy
    world.extras.apply("missile", 0, [])

    events = world.step(FrameInputs((0.0, 0.0), (True, False)))
    for _ in range(100):
        events.extend(world.step(FrameInputs()))
        if any(isinstance(event, MissileHit) for event in events):
            break

    assert any(isinstance(event, MissileHit) and event.target == 1 for event in events)
    assert any(effect.name == "stun" for effect in world.extras.active[1])


def test_snapshot_preserves_spin_companion_missile_and_targeted_pickup() -> None:
    source = make_world()
    source.ball.rotation = 1.25
    source.ball.spin_rate = -7.0
    source.extras.apply("companion", 0, [])
    source.extras.missiles.append(Missile(Vec2(20.0, 30.0), Vec2(4.0, 5.0), 0, 30, 1.5))
    source.extras.pickups.append(Pickup(Vec2(40.0, 45.0), "shield", 50, 0, True))
    mirror = make_world()

    snapshot.apply(mirror, snapshot.capture(source))

    assert mirror.ball.rotation == pytest.approx(1.25)
    assert mirror.ball.spin_rate == pytest.approx(-7.0)
    assert len(mirror.extras.companions) == 1
    assert len(mirror.extras.missiles) == 1
    assert mirror.extras.pickups[0].target == 0
    assert mirror.extras.pickups[0].reduced


def test_lan_input_codec_preserves_spin_button() -> None:
    message = Input(7, -0.5, False, True)

    assert from_dict(to_dict(message)) == message
    spin_event = SpinHit(0)
    assert snapshot.events_from_list(snapshot.events_to_list([spin_event])) == [spin_event]


def test_spin_sound_is_different_from_normal_paddle_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    player = object.__new__(AudioPlayer)
    player.bank = load_bank()
    player.enabled = True
    played: list[str] = []

    def record(name: str) -> bool:
        played.append(name)
        return True

    monkeypatch.setattr(player, "play", record)

    player.handle_events([PaddleHit(0), SpinHit(0)])

    assert played == ["paddle", "spin_hit"]


def test_match_countdown_shows_three_numbers_for_half_a_second_each() -> None:
    world = World(MatchConfig())

    assert world.countdown_number == 3
    for _ in range(c.SERVE_COUNTDOWN_STEP_TICKS):
        world.step(FrameInputs())
    assert world.countdown_number == 2
    for _ in range(c.SERVE_COUNTDOWN_STEP_TICKS):
        world.step(FrameInputs())
    assert world.countdown_number == 1
    for _ in range(c.SERVE_COUNTDOWN_STEP_TICKS):
        world.step(FrameInputs())

    assert world.phase is Phase.PLAYING
    assert world.countdown_number is None
