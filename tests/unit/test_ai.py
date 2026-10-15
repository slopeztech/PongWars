"""AI tests (spec: ai-opponent)."""

from collections.abc import Callable

import pytest

from pongwars.ai import PROFILES, STRATEGIES, AIController, Observation
from pongwars.ai.prediction import predict_intercept
from pongwars.core.registry import RegistryError
from pongwars.domain.config import MatchConfig
from pongwars.domain.entities import Obstacle, Rect
from pongwars.domain.vec import Vec2
from pongwars.domain.world import FrameInputs, Phase, World

MATCHES = 30
POINTS_TO_WIN = 3
MAX_TICKS = 20000
REFERENCE_SPEED = 0.6
DIFFICULTIES = ("easy", "normal", "hard", "insane")


def _world(seed: int = 1, obstacles: list[Obstacle] | None = None) -> World:
    config = MatchConfig(options=(("points_to_win", POINTS_TO_WIN),), seed=seed)
    return World(config, obstacles=obstacles)


def _observer(world: World, seat: int) -> Callable[[], Observation]:
    return lambda: Observation.from_world(world, seat)


def _reference(world: World) -> float:
    error = world.ball.pos.y - world.paddles[1].rect.cy
    return max(-REFERENCE_SPEED, min(REFERENCE_SPEED, error / 3.0))


def _win_count(difficulty: str) -> int:
    wins = 0
    for seed in range(MATCHES):
        world = _world(seed)
        ai = AIController(_observer(world, 0), difficulty, seed=seed)
        for _ in range(MAX_TICKS):
            if world.phase is Phase.FINISHED:
                break
            world.step(FrameInputs((ai.poll(), _reference(world))))
        wins += world.winner == 0
    return wins


def test_observation_is_a_copy() -> None:
    world = _world()
    obs = Observation.from_world(world, 0)
    world.paddles[0].rect.cy = 10.0
    assert obs.paddle.cy != 10.0
    assert obs.walls == (False, False, True, True)


def test_prediction_accounts_for_wall_bounce() -> None:
    world = _world()
    world.ball.pos = Vec2(80.0, 30.0)
    world.ball.vel = Vec2(-60.0, -60.0)
    obs = Observation.from_world(world, 0)
    target = predict_intercept(obs)
    assert target is not None
    straight = 30.0 + (80.0 - 7.5) * 1.0 * -1
    assert target >= 0.0
    assert target != pytest.approx(straight)


def test_prediction_none_when_ball_leaves() -> None:
    world = _world()
    world.ball.pos = Vec2(80.0, 45.0)
    world.ball.vel = Vec2(60.0, 0.0)
    assert predict_intercept(Observation.from_world(world, 0)) is None
    world.ball.vel = Vec2(-60.0, 0.0)
    assert predict_intercept(Observation.from_world(world, 0)) is not None
    world.ball.vel = Vec2()
    assert predict_intercept(Observation.from_world(world, 0)) is None


def test_prediction_uses_obstacles() -> None:
    block = Obstacle(Rect(50.0, 45.0, 3.0, 12.0))
    world = _world(obstacles=[block])
    world.ball.pos = Vec2(80.0, 45.0)
    world.ball.vel = Vec2(-80.0, 0.0)
    obs = Observation.from_world(world, 0)
    assert predict_intercept(obs, use_obstacles=False) == pytest.approx(45.0, abs=1.0)
    assert predict_intercept(obs, use_obstacles=True) != pytest.approx(45.0, abs=1.0)


def test_ai_moves_toward_ball_and_is_deterministic() -> None:
    def run() -> list[float]:
        world = _world(3)
        ai = AIController(lambda: Observation.from_world(world, 0), "hard", seed=3)
        out = []
        for _ in range(400):
            move = ai.poll()
            out.append(move)
            world.step(FrameInputs((move, 0.0)))
        return out

    assert run() == run()
    assert any(m != 0.0 for m in run())


def test_unknown_difficulty_and_strategy() -> None:
    with pytest.raises(RegistryError):
        AIController(lambda: Observation.from_world(_world(), 0), "godlike")
    with pytest.raises(RegistryError):
        AIController(lambda: Observation.from_world(_world(), 0), strategy="nope")


def test_custom_strategy_can_be_registered() -> None:
    STRATEGIES.add("stay", lambda obs, profile: None)
    try:
        world = _world()
        ai = AIController(lambda: Observation.from_world(world, 0), strategy="stay")
        assert ai.poll() == 0.0
    finally:
        STRATEGIES.remove("stay")


def test_profiles_are_ordered() -> None:
    p = [PROFILES.get(n) for n in DIFFICULTIES]
    assert [x.reaction_ticks for x in p] == sorted((x.reaction_ticks for x in p), reverse=True)
    assert [x.aim_error for x in p] == sorted((x.aim_error for x in p), reverse=True)
    assert [x.speed for x in p] == sorted(x.speed for x in p)


def test_difficulty_win_rate_is_monotonic() -> None:
    rates = [_win_count(name) for name in DIFFICULTIES]
    assert rates == sorted(rates)
    assert rates[-1] > rates[0]


def test_ai_plays_a_top_seat() -> None:
    config = MatchConfig(arena="trident", controllers=("ai", "ai", "ai"), seed=2)
    world = World(config)
    bots = [AIController(_observer(world, s), "hard", seed=s) for s in range(3)]
    for _ in range(600):
        world.step(FrameInputs(tuple(b.poll() for b in bots)))
    assert all(abs(m) <= 1.0 for m in (b.poll() for b in bots))


def _fires_within(world: World, ai: AIController, ticks: int) -> bool:
    for _ in range(ticks):
        ai.poll()
        if ai.fire_intent():
            return True
    return False


@pytest.mark.parametrize("weapon", ["freeze", "hex", "laser", "cat", "bomb", "warp"])
def test_ai_uses_held_weapon(weapon: str) -> None:
    world = _world()
    world.extras.weapons[0] = (weapon, 1)
    paddle = world.paddles[0].rect
    if weapon == "bomb":
        world.ball.pos = Vec2(paddle.cx + 10.0, paddle.cy)
        world.ball.vel = Vec2(-60.0, 0.0)
    elif weapon == "cat":
        world.ball.vel = Vec2(60.0, 0.0)
    elif weapon == "warp":
        world.ball.pos = Vec2(paddle.cx + 60.0, paddle.cy + 60.0)
        world.ball.vel = Vec2(-60.0, 0.0)
    ai = AIController(_observer(world, 0), "insane", seed=3)
    assert _fires_within(world, ai, 600)


def test_ai_does_not_fire_without_weapon() -> None:
    world = _world()
    ai = AIController(_observer(world, 0), "insane", seed=3)
    assert not _fires_within(world, ai, 300)


def test_ai_does_not_fire_when_jammed() -> None:
    world = _world()
    world.extras.weapons[0] = ("freeze", 1)
    world.extras.apply_direct("jammed", 0, [])
    ai = AIController(_observer(world, 0), "insane", seed=3)
    assert not _fires_within(world, ai, 300)


def test_ai_fire_is_a_single_tick_pulse() -> None:
    world = _world()
    world.extras.weapons[0] = ("freeze", 5)
    ai = AIController(_observer(world, 0), "insane", seed=3)
    states = []
    for _ in range(200):
        ai.poll()
        states.append(ai.fire_intent())
    assert any(states)
    assert not any(a and b for a, b in zip(states, states[1:], strict=False))


def test_harder_ai_fires_sooner() -> None:
    def first_fire(level: str) -> int:
        world = _world()
        world.extras.weapons[0] = ("freeze", 1)
        ai = AIController(_observer(world, 0), level, seed=5)
        for tick in range(2000):
            ai.poll()
            if ai.fire_intent():
                return tick
        return 2000

    assert first_fire("insane") < first_fire("easy")


def test_ai_match_consumes_weapons() -> None:
    world = _world(seed=7)
    ais = [AIController(_observer(world, s), "hard", seed=s) for s in range(2)]
    fired = False
    for _ in range(3000):
        if world.phase is Phase.FINISHED:
            break
        for seat in range(2):
            if world.extras.weapons[seat] is None:
                world.extras.weapons[seat] = ("freeze", 1)
        before = [w for w in world.extras.weapons]
        world.step(FrameInputs(tuple(a.poll() for a in ais), tuple(a.fire_intent() for a in ais)))
        fired = (
            fired or any(w is None for w in world.extras.weapons) and before != world.extras.weapons
        )
    assert fired
