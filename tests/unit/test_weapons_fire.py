"""Regression tests: every weapon fires and the cat can catch the ball."""

import pytest

from pongwars.domain.config import MatchConfig
from pongwars.domain.entities import Missile, Obstacle, Rect
from pongwars.domain.events import CatPounced, ObstacleDestroyed
from pongwars.domain.vec import Vec2
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


@pytest.mark.parametrize("weapon", ["laser", "freeze", "bomb", "cat", "hex", "warp", "build"])
def test_weapon_consumes_ammo_on_fire(weapon: str) -> None:
    """@brief Firing with a weapon spends one charge."""
    world = _armed(weapon)
    before = world.extras.weapons[0]
    assert before is not None
    world.step(FIRE)
    after = world.extras.weapons[0]
    assert after is None or after[1] == before[1] - 1


def test_build_places_two_blocks_that_break_on_first_ball_hit() -> None:
    world = _armed("build")
    world.step(FIRE)
    world.step(IDLE)
    world.step(FIRE)

    blocks = [obstacle for obstacle in world.obstacles if obstacle.kind == "built"]
    assert len(blocks) == 2
    assert all(block.owner == 0 and block.active and block.hp == 1 for block in blocks)
    assert blocks[0].rect.cx > world.paddles[0].rect.cx
    assert not world.build_block(0)
    assert world.extras.weapons[0] is None

    events = []
    index = world.obstacles.index(blocks[0])
    ball = world.ball
    ball.pos = Vec2(
        blocks[0].rect.cx + ball.radius + blocks[0].rect.half_w + 0.5,
        blocks[0].rect.cy,
    )
    ball.vel = Vec2(-36.0, 0.0)
    world._move_ball(ball, events)
    assert not blocks[0].active and blocks[0].hp == 0
    assert events[-1] == ObstacleDestroyed(index)


def test_built_block_breaks_on_first_laser_hit() -> None:
    world = _armed("laser")
    world.paddles[0].rect.cy = 45.0
    block = Obstacle(Rect(80.0, 45.0, 2.0, 4.0), kind="built", hp=1, owner=0)
    world.obstacles.append(block)

    world.step(FIRE)

    assert not block.active


def test_built_block_breaks_on_first_missile_hit() -> None:
    world = _armed("missile")
    block = Obstacle(Rect(80.0, 45.0, 2.0, 4.0), kind="built", hp=1, owner=0)
    world.obstacles.append(block)
    world.extras.missiles.append(
        Missile(Vec2(75.0, 45.0), Vec2(120.0, 0.0), 0, 10, 1.0)
    )
    events = []

    world.extras.update_missiles(events)

    assert not block.active
    assert ObstacleDestroyed(world.obstacles.index(block)) in events


def test_built_block_with_legacy_health_still_breaks_on_one_contact() -> None:
    world = _armed("build")
    block = Obstacle(Rect(80.0, 45.0, 2.0, 4.0), kind="built", hp=3, owner=0)
    world.obstacles.append(block)

    world.damage_obstacle(world.obstacles.index(block), [])

    assert not block.active and block.hp == 0


def test_build_places_a_horizontal_block_in_front_of_top_player() -> None:
    world = World(MatchConfig(arena="crossfire", controllers=("human",) * 4))

    assert world.build_block(2)

    block = next(obstacle for obstacle in world.obstacles if obstacle.kind == "built")
    assert block.rect.cy > world.paddles[2].rect.cy
    assert block.rect.half_w > block.rect.half_h


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
