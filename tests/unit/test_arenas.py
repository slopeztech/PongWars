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
        "arkanoid",
        "gravity",
    ],
)
def test_arenas_builtin_fair_and_open(name: str) -> None:
    arena = get_arena(name)
    assert arena.is_mirror_symmetric()
    assert arena.has_open_path()
    World(MatchConfig(arena=name))


@pytest.mark.parametrize(
    "name", ["monolith", "orbital", "pinball", "portal", "arkanoid", "gravity"]
)
def test_new_arenas_are_two_player(name: str) -> None:
    assert get_arena(name).players == 2


def test_arena_serve_configuration_controls_position_and_speed() -> None:
    gravity = World(MatchConfig(arena="gravity", seed=1))
    classic = World(MatchConfig(arena="classic", seed=1))
    gravity.phase = Phase.SERVING
    events: list[Event] = []
    center = Vec2(c.FIELD_WIDTH / 2, c.FIELD_HEIGHT / 2)

    assert gravity.ball.pos == Vec2(80.0, 3.0)
    start_radius = (gravity.ball.pos - center).length()
    assert start_radius >= c.GRAVITY_WELL_RADIUS
    assert classic.ball.pos == center
    gravity._serve(events)

    assert gravity.ball.vel.length() == pytest.approx(105.0)
    for _ in range(12):
        gravity.step(FrameInputs())
    assert (gravity.ball.pos - center).length() > start_radius


@pytest.mark.parametrize(
    "serve", [{"x": -1}, {"y": c.FIELD_HEIGHT + 1}, {"speed": 0}, {"speed": c.BALL_MAX_SPEED + 1}]
)
def test_arena_rejects_invalid_serve_configuration(serve: dict[str, float]) -> None:
    with pytest.raises(ArenaError) as err:
        parse_arena({"id": "test", "theme": "retro", "serve": serve})

    assert err.value.key == "error.arena.invalid_value"


def test_gravity_arena_pulls_more_strongly_near_the_center() -> None:
    close = World(MatchConfig(arena="gravity"))
    far = World(MatchConfig(arena="gravity"))
    close.ball.pos = Vec2(90.0, c.FIELD_HEIGHT / 2)
    far.ball.pos = Vec2(120.0, c.FIELD_HEIGHT / 2)
    close.ball.vel = far.ball.vel = Vec2(0.0, 80.0)

    close._apply_arena_gravity(close.ball)
    far._apply_arena_gravity(far.ball)

    assert close.ball.vel.x < far.ball.vel.x
    assert close.ball.vel.y == pytest.approx(far.ball.vel.y)


def test_gravity_arena_accelerates_ball_outward_from_the_well() -> None:
    world = World(MatchConfig(arena="gravity"))
    world.ball.pos = Vec2(c.FIELD_WIDTH / 2 + 10.0, c.FIELD_HEIGHT / 2)
    world.ball.vel = Vec2(80.0, 0.0)

    world._apply_arena_gravity(world.ball)

    assert world.ball.vel.x > 80.0


def test_gravity_is_disabled_in_other_arenas() -> None:
    world = World(MatchConfig(arena="classic"))
    world.ball.vel = Vec2(0.0, 80.0)

    world._apply_arena_gravity(world.ball)

    assert world.ball.vel == Vec2(0.0, 80.0)


def test_arkanoid_generates_seeded_centered_clusters_each_round() -> None:
    first = World(MatchConfig(arena="arkanoid", seed=20))
    same_seed = World(MatchConfig(arena="arkanoid", seed=20))
    other_seed = World(MatchConfig(arena="arkanoid", seed=21))

    assert 2 <= len(first.obstacles) <= 16
    assert [(o.rect.cx, o.rect.cy) for o in first.obstacles] == [
        (o.rect.cx, o.rect.cy) for o in same_seed.obstacles
    ]
    assert [(o.rect.cx, o.rect.cy) for o in first.obstacles] != [
        (o.rect.cx, o.rect.cy) for o in other_seed.obstacles
    ]
    assert all(o.kind == "destructible" and o.hp == 1 for o in first.obstacles)
    assert all(50.0 <= o.rect.cx <= 110.0 for o in first.obstacles)
    assert all(20.0 <= o.rect.cy <= 70.0 for o in first.obstacles)


def test_arkanoid_ball_hit_removes_block() -> None:
    world = World(MatchConfig(arena="arkanoid", seed=20))
    obstacle = world.obstacles[0]
    world.ball.pos = Vec2(
        obstacle.rect.cx - obstacle.rect.half_w - world.ball.radius - 0.5,
        obstacle.rect.cy,
    )
    world.ball.vel = Vec2(80.0, 0.0)
    events: list[Event] = []

    world._move_ball(world.ball, events)

    assert any(isinstance(event, WallHit) for event in events)
    assert not obstacle.active


@pytest.mark.parametrize("weapon", ["laser", "missile"])
def test_arkanoid_weapons_destroy_blocks(weapon: str) -> None:
    from pongwars.domain.entities import Missile

    world = World(MatchConfig(arena="arkanoid", seed=20, extras=("all",)))
    obstacle = world.obstacles[0]
    active_before = sum(block.active for block in world.obstacles)
    events: list[Event] = []
    if weapon == "laser":
        world.paddles[0].rect.cy = obstacle.rect.cy
        world.extras.weapons[0] = ("laser", 1)
        world.extras.fire(0, events)
    else:
        world.extras.missiles.append(
            Missile(
                Vec2(obstacle.rect.cx - obstacle.rect.half_w - 2.0, obstacle.rect.cy),
                Vec2(80.0, 0.0),
                0,
                10,
                1.5,
            )
        )
        for _ in range(10):
            world.extras.update_missiles(events)
            if not world.extras.missiles:
                break

    assert sum(block.active for block in world.obstacles) == active_before - 1


def test_arkanoid_regenerates_blocks_after_each_round() -> None:
    world = World(MatchConfig(arena="arkanoid", seed=20))
    previous = world.obstacles
    for index in range(len(previous)):
        world.destroy_obstacle(index, [])

    world.ball.pos = Vec2(-world.ball.radius - 1.0, c.FIELD_HEIGHT / 2)
    world._check_goal(world.ball, [])

    assert world.phase is Phase.SERVING
    assert 2 <= len(world.obstacles) <= 16
    assert all(block.active and block.hp == 1 for block in world.obstacles)
    assert all(
        not any(block is previous_block for previous_block in previous)
        for block in world.obstacles
    )


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


def test_ball_teleports_through_portal_preserving_trajectory_and_speed() -> None:
    world = World(MatchConfig(arena="portal", seed=20))
    entry, exit = world.portals
    previous = world.portals
    world.ball.pos = Vec2(
        entry.x - c.PORTAL_RADIUS - world.ball.radius - 0.5,
        entry.y,
    )
    original_velocity = Vec2(80.0, 12.0)
    world.ball.vel = original_velocity
    events: list[Event] = []

    world._move_ball(world.ball, events)

    assert any(isinstance(event, BallWarped) for event in events)
    assert world.ball.vel == original_velocity
    assert world.ball.vel.length() == pytest.approx(original_velocity.length())
    assert world.ball.pos.x > exit.x + c.PORTAL_RADIUS + world.ball.radius
    assert world.ball.pos.y > exit.y
    assert all(
        (portal - old_portal).length() >= c.PORTAL_RADIUS * 2 + c.BALL_RADIUS
        for portal in world.portals
        for old_portal in previous
    )
    assert all(
        (portal - world.ball.pos).length() >= c.PORTAL_RADIUS * 2 + c.BALL_RADIUS
        for portal in world.portals
    )

    previous = world.portals
    entry, _ = world.portals
    world.ball.pos = Vec2(
        entry.x - c.PORTAL_RADIUS - world.ball.radius - 0.5,
        entry.y,
    )
    original_velocity = Vec2(80.0, 12.0)
    world.ball.vel = original_velocity
    world._move_ball(world.ball, [])

    assert world.ball.vel == original_velocity
    assert all(
        (portal - old_portal).length() >= c.PORTAL_RADIUS * 2 + c.BALL_RADIUS
        for portal in world.portals
        for old_portal in previous
    )


def test_fortress_obstacles_are_restored_after_each_round() -> None:
    world = World(MatchConfig(arena="fortress", seed=20))
    initial_count = len(world.obstacles)
    for index, _obstacle in enumerate(world.obstacles):
        world.destroy_obstacle(index, [])

    world.ball.pos = Vec2(-world.ball.radius - 1.0, c.FIELD_HEIGHT / 2)
    world._check_goal(world.ball, [])

    assert world.phase is Phase.SERVING
    assert len(world.obstacles) == initial_count
    assert all(obstacle.active for obstacle in world.obstacles)
    assert all(obstacle.hp > 0 for obstacle in world.obstacles)


def test_monolith_rotates_ninety_degrees_after_each_hit() -> None:
    world = World(MatchConfig(arena="monolith", seed=20))
    obstacle = world.obstacles[0]
    initial_size = (obstacle.rect.half_w, obstacle.rect.half_h)
    events = _fire(world, obstacle.rect.cx)

    assert any(isinstance(event, WallHit) for event in events)
    assert (obstacle.rect.half_w, obstacle.rect.half_h) == (initial_size[1], initial_size[0])
    assert world.ball.vel.x < 0.0

    world.ball.pos = Vec2(obstacle.rect.cx, obstacle.rect.cy - obstacle.rect.half_h - 10.0)
    world.ball.vel = Vec2(0.0, 80.0)
    events = []
    for _ in range(20):
        world._move_ball(world.ball, events)
        if any(isinstance(event, WallHit) for event in events):
            break

    assert any(isinstance(event, WallHit) for event in events)
    assert (obstacle.rect.half_w, obstacle.rect.half_h) == initial_size


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
