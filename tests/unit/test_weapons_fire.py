"""Regression tests: every weapon fires and the cat can catch the ball."""

import pytest

from pongwars.domain.config import MatchConfig
from pongwars.domain.events import CatPounced
from pongwars.domain.world import FrameInputs, Phase, World

IDLE = FrameInputs((0.0, 0.0), (False, False))
FIRE = FrameInputs((0.0, 0.0), (True, False))


def _armed(weapon: str, seed: int = 0) -> World:
    world = World(MatchConfig(seed=seed))
    for _ in range(200):
        world.step(IDLE)
    while world.phase is Phase.SERVING:
        world.step(IDLE)
    world.extras.apply(weapon, 0, [])
    return world


@pytest.mark.parametrize("weapon", ["laser", "freeze", "bomb", "cat", "hex", "warp"])
def test_weapon_consumes_ammo_on_fire(weapon: str) -> None:
    """@brief Firing with a weapon spends one charge."""
    world = _armed(weapon)
    before = world.extras.weapons[0]
    assert before is not None
    world.step(FIRE)
    after = world.extras.weapons[0]
    assert after is None or after[1] == before[1] - 1


def test_cat_spawns_and_pounces() -> None:
    """@brief The cat appears and catches the ball in most seeds."""
    pounces = 0
    for seed in range(8):
        world = _armed("cat", seed)
        world.step(FIRE)
        assert world.extras.cats
        for _ in range(300):
            pounces += sum(isinstance(e, CatPounced) for e in world.step(IDLE))
    assert pounces > 0
