"""Tests for arenas and obstacles."""

from pathlib import Path

import pytest

from pongwars.domain import constants as c
from pongwars.domain.arenas import (
    ArenaError,
    arena_names,
    get_arena,
    load_arena_file,
    parse_arena,
)
from pongwars.domain.config import ConfigError, MatchConfig
from pongwars.domain.entities import Obstacle, Rect
from pongwars.domain.events import BallWarped, BumperHit, Event, ObstacleDestroyed, WallHit
from pongwars.domain.physics import sweep_circle_rect
from pongwars.domain.vec import Vec2
from pongwars.domain.world import FrameInputs, Phase, World


def _fire(world: World, obstacle_x: float) -> list[object]:
    """Shoot the ball at the obstacle from the left and return the events."""
    world.phase = Phase.PLAYING
    world.ball.pos = Vec2(obstacle_x - 10, 45)
    world.ball.vel = Vec2(1.0, 0.0) * c.BALL_START_SPEED
    events: list[object] = []
    for _ in range(120):
        events += world.step(FrameInputs())
        if events:
            break
    return events


def test_arenas_at_least_five_builtin() -> None:
    assert len(arena_names()) >= 5


@pytest.mark.parametrize(
    "name",
    [
        "classic",
        "pillars",
        "bumpers",
        "moving_walls",
        "fortress",
        "monolith",
        "orbital",
        "pinball",
        "portal",
    ],
)
def test_arenas_builtin_fair_and_open(name: str) -> None:
    arena = get_arena(name)
    assert arena.is_mirror_symmetric()
    assert arena.has_open_path()
    World(MatchConfig(arena=name))


@pytest.mark.parametrize("name", ["monolith", "orbital", "pinball", "portal"])
def test_new_arenas_are_two_player(name: str) -> None:
    assert get_arena(name).players == 2


def test_orbital_arena_obstacles_follow_circular_paths() -> None:
    world = World(MatchConfig(arena="orbital"))
    first, second = world.obstacles

    first.update(0)
    second.update(0)
    assert first.rect.cx == pytest.approx(65.0)
    assert first.rect.cy == pytest.approx(45.0)
    assert second.rect.cx == pytest.approx(95.0)
    assert second.rect.cy == pytest.approx(45.0)

    first.update(90)
    second.update(90)
    assert first.rect.cx == pytest.approx(55.0)
    assert first.rect.cy == pytest.approx(55.0)
    assert second.rect.cx == pytest.approx(105.0)
    assert second.rect.cy == pytest.approx(55.0)


def test_portal_positions_are_seeded_and_separated() -> None:
    first = World(MatchConfig(arena="portal", seed=20))
    same_seed = World(MatchConfig(arena="portal", seed=20))
    other_seed = World(MatchConfig(arena="portal", seed=21))

    assert first.portals == same_seed.portals
    assert first.portals != other_seed.portals
    assert len(first.portals) == 2
    assert (first.portals[1] - first.portals[0]).length() >= c.PORTAL_MIN_SEPARATION


def test_ball_teleports_through_portal_preserving_direction_and_reducing_speed() -> None:
    world = World(MatchConfig(arena="portal", seed=20))
    entry, exit = world.portals
    world.ball.pos = Vec2(
        entry.x - c.PORTAL_RADIUS - world.ball.radius - 0.5,
        entry.y,
    )
    world.ball.vel = Vec2(80.0, 0.0)
    events: list[Event] = []

    world._move_ball(world.ball, events)

    assert any(isinstance(event, BallWarped) for event in events)
    assert world.ball.vel.x > 0
    assert world.ball.vel.y == pytest.approx(0)
    assert world.ball.vel.length() == pytest.approx(80.0 * c.PORTAL_SPEED_FACTOR)
    assert world.ball.pos.x > exit.x + c.PORTAL_RADIUS + world.ball.radius
    assert world.ball.pos.y == pytest.approx(exit.y)


def test_arenas_unknown_raises() -> None:
    with pytest.raises(ConfigError) as err:
        get_arena("nowhere")
    assert err.value.key == "error.config.unknown_arena"


def test_arenas_invalid_file_names_file_and_obstacle(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text(
        'id = "bad"\ntheme = "x"\n[[obstacles]]\nkind = "solid"\nx = 1\ny = 5\n'
        "half_w = 2\nhalf_h = 2\n",
        encoding="utf-8",
    )
    with pytest.raises(ArenaError) as err:
        load_arena_file(path)
    assert err.value.params["file"] == "bad.toml"
    assert err.value.params["obstacle"] == 0
    assert err.value.key == "error.arena.obstacle_out_of_bounds"


def test_arenas_blocked_path_detected() -> None:
    data = {
        "id": "wall",
        "theme": "x",
        "obstacles": [{"kind": "solid", "x": 80, "y": 45, "half_w": 2, "half_h": 45}],
    }
    with pytest.raises(ArenaError) as err:
        parse_arena(data, "wall.json")
    assert err.value.key == "error.arena.blocked_path"


def test_obstacles_bumper_speeds_ball_up() -> None:
    bumper = Obstacle(Rect(80, 45, 2, 2), "bumper")
    world = World(MatchConfig(), obstacles=[bumper])
    events = _fire(world, 80)
    assert any(isinstance(e, BumperHit) for e in events)
    assert world.ball.vel.length() == pytest.approx(c.BALL_START_SPEED * c.BUMPER_FACTOR)


def test_obstacles_destructible_removed_after_hp() -> None:
    wall = Obstacle(Rect(80, 45, 2, 2), "destructible", hp=1)
    world = World(MatchConfig(), obstacles=[wall])
    events = _fire(world, 80)
    assert any(isinstance(e, ObstacleDestroyed) for e in events)
    assert any(isinstance(e, WallHit) for e in events)
    assert not wall.active


def test_obstacles_moving_position_is_function_of_tick() -> None:
    wall = Obstacle(Rect(60, 45, 2, 5), patrol=Vec2(0.0, 10.0), period=100)
    wall.update(25)
    assert wall.rect.cy == pytest.approx(55.0)
    wall.update(0)
    assert wall.rect.cy == pytest.approx(45.0)


def test_physics_ball_inside_rect_is_pushed_out() -> None:
    hit = sweep_circle_rect(Vec2(80.5, 45), Vec2(-0.4, 0), c.BALL_RADIUS, Rect(80, 45, 2, 2))
    assert hit is not None and hit.t == 0.0
