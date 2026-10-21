"""@file test_render_extras.py
@brief Headless smoke test for extras rendering (pickups, effects, lasers and blind field).
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from pongwars.core.i18n import Translator
from pongwars.domain.config import MatchConfig
from pongwars.domain.events import (
    BallReleased,
    BallSwallowed,
    BallWarped,
    BombDetonated,
    Event,
    LaserFired,
    LeviathanRoared,
    MissileHit,
    StalkerExploded,
)
from pongwars.domain.extras import Pickup, load_specs
from pongwars.domain.vec import Vec2
from pongwars.domain.world import FrameInputs, World
from pongwars.render import hud as hud_module
from pongwars.render import palette as pal
from pongwars.render import renderer as renderer_module
from pongwars.render.font import text_width, unsupported_chars
from pongwars.render.hud import HUD_STYLES, HudRenderer, player_slot_layout
from pongwars.render.renderer import BIG_TEXT, Renderer, RenderSettings


def _world() -> World:
    return World(MatchConfig(extras=("all",), seed=3))


def test_draws_every_extra_without_error() -> None:
    """@brief Pickups, active effects, shield, laser flash and blind field render."""
    pygame.init()
    for view in ("shared", "split"):
        world = _world()
        renderer = Renderer(RenderSettings(view=view))
        for name in (
            "shield",
            "blind",
            "laser",
            "multiball",
            "big_paddle",
            "stalker",
            "chomper",
            "leviathan",
        ):
            world.extras.apply(name, 0, [])
        world.extras.pickups.append(Pickup(Vec2(80.0, 45.0), "bomb", 50))
        events: list[Event] = []
        for _ in range(3):
            events = world.step(FrameInputs(moves=(0.0, 0.0), fire=(True, False)))
            renderer.handle_events(world, events)
            renderer.update(world, 1 / 60)
            surface = renderer.draw(world)
        assert surface.get_size() == (320, 180)


def test_bomb_detonation_starts_and_expires_explosion_animation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pygame.init()
    world = _world()
    renderer = Renderer()
    renderer._canvas = pygame.Surface((320, 180))
    renderer.handle_events(world, [BombDetonated(0, 80.0, 45.0)])
    assert len(renderer.explosions) == 1

    circles: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        renderer_module.pygame.draw,
        "circle",
        lambda *args, **kwargs: circles.append(args),
    )
    renderer._draw_explosions()
    assert len(circles) == 3

    renderer.update(world, 0.5)
    assert renderer.explosions == []


def test_laser_and_missile_paddle_hits_start_explosions() -> None:
    pygame.init()
    world = _world()
    renderer = Renderer()

    renderer.handle_events(
        world,
        [LaserFired(0, 140.0, 45.0, 1), MissileHit(0, 140.0, 45.0, 1)],
    )

    assert len(renderer.explosions) == 2
    assert [(e.x, e.y) for e in renderer.explosions] == [
        (140.0, 45.0),
        (140.0, 45.0),
    ]


def test_invasor_renders_without_error() -> None:
    pygame.init()
    world = _world()
    world.extras.apply_direct("invasor", 1, [])
    renderer = Renderer()
    renderer.draw(world)


def test_hungry_orb_is_drawn_during_its_roaming_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pygame.init()
    world = _world()
    world.extras.apply("chomper", 0, [])
    assert world.extras.chompers[0].phase == "roaming"
    renderer = Renderer()
    drawn: list[int] = []
    monkeypatch.setattr(renderer, "_chomper", lambda _world, index: drawn.append(index))

    renderer.draw(world)

    assert drawn == [0]


def test_stalker_renders_as_a_pixelated_green_creature() -> None:
    pygame.init()
    world = _world()
    world.extras.apply_direct("stalker", 1, [])
    renderer = Renderer()
    renderer.draw(world)

    colors = {
        renderer.surface.get_at((x, y))[:3]
        for x in range(renderer.surface.get_width())
        for y in range(renderer.surface.get_height())
    }
    assert (0, 154, 47) in colors
    assert pal.BLACK in colors


def test_new_extra_events_start_their_visual_effects() -> None:
    world = _world()
    renderer = Renderer()
    renderer.handle_events(
        world,
        [
            StalkerExploded(0, 20.0, 45.0),
            BallSwallowed(80.0, 45.0),
            BallReleased(100.0, 45.0),
            LeviathanRoared(),
        ],
    )

    assert len(renderer.explosions) == 1
    assert len(renderer.particles.particles) > 0
    assert renderer.shake.amplitude > 0.0


def test_leviathan_flips_camera_below_the_arena_and_renders() -> None:
    pygame.init()
    world = _world()
    renderer = Renderer()
    world.extras.apply_direct("leviathan", 0, [])
    for _ in range(round(0.6 * 60)):
        world.extras.tick_effects([])

    camera = renderer._camera_for(renderer.viewports(world)[0], world)

    assert camera._pitch < 0
    canvas = pygame.Surface((320, 180), pygame.SRCALPHA)
    renderer._canvas = canvas
    renderer.camera = camera
    renderer._draw_leviathan(world)
    assert pygame.mask.from_surface(canvas).count() > 100
    assert renderer.draw(world).get_size() == (320, 180)


def test_every_extra_has_a_unique_category_colored_pickup_icon() -> None:
    specs = load_specs()
    assert set(specs) == set(renderer_module.PICKUP_ICONS)
    assert len(set(renderer_module.PICKUP_ICONS.values())) == len(specs)
    assert set(spec.category for spec in specs.values()) <= set(renderer_module.CATEGORY_COLORS)


def test_portal_arena_renders_both_portals() -> None:
    pygame.init()
    world = World(MatchConfig(arena="portal", seed=9))
    renderer = Renderer()
    canvas = pygame.Surface((320, 180))
    renderer._canvas = canvas

    for index in range(len(world.portals)):
        renderer._portal(world, index)

    assert pygame.image.tobytes(canvas, "RGB") != pygame.image.tobytes(
        pygame.Surface((320, 180)), "RGB"
    )


def test_portal_warp_event_starts_visual_particles() -> None:
    world = World(MatchConfig(arena="portal", seed=9))
    renderer = Renderer()

    renderer.handle_events(world, [BallWarped(80.0, 45.0)])

    assert len(renderer.particles.particles) == 12


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        ("classic", (pal.WHITE,)),
        ("pixel", (pal.ORANGE, pal.WHITE, pal.YELLOW)),
        ("energy", (pal.BLUE, pal.WHITE, pal.UI_CYAN)),
        ("ring", (pal.WHITE, pal.PINK)),
    ],
)
def test_blind_field_uses_current_ball_colors(style: str, expected: tuple[pal.Color, ...]) -> None:
    pygame.init()
    world = _world()
    world.extras.apply("blind", 1, [])
    renderer = Renderer(RenderSettings(ball_style=style))
    canvas = pygame.Surface((320, 180))
    canvas.fill(pal.BLACK)
    renderer._canvas = canvas

    renderer._draw_blind_zones(world)

    assert renderer._blind_ball_colors(world.ball) == expected
    assert pygame.image.tobytes(canvas, "RGB") != pygame.image.tobytes(
        pygame.Surface((320, 180)), "RGB"
    )


@pytest.mark.parametrize(
    ("arena", "players"),
    [
        ("classic", 2),
        ("trident", 3),
        ("crossfire", 4),
    ],
)
@pytest.mark.parametrize("style", HUD_STYLES)
def test_hud_layout_separates_every_player_zone(arena: str, players: int, style: str) -> None:
    pygame.init()
    world = World(MatchConfig(arena=arena, controllers=("human",) * players))
    renderer = Renderer(RenderSettings(hud_style=style))
    for seat in range(players):
        world.extras.apply("inverted", seat, [])
    world.extras.weapons[players - 1] = ("laser", 2)
    world.extras.pickups.extend(
        [
            Pickup(Vec2(35.0, 30.0), "bomb", 100),
            Pickup(Vec2(80.0, 45.0), "shield", 100),
            Pickup(Vec2(125.0, 65.0), "small_paddle", 100),
        ]
    )
    assert renderer.draw(world).get_size() == (320, 180)

    slots = player_slot_layout((320, 180), players)
    assert {seat for seat, _ in slots} == set(range(players))
    for index, (_, rect) in enumerate(slots):
        assert rect.left >= 0 and rect.right <= 320
        assert all(not rect.colliderect(other) for _, other in slots[index + 1 :])


@pytest.mark.parametrize(("players", "size"), [(2, (160, 180)), (3, (160, 90)), (4, (160, 90))])
def test_split_hud_layout_keeps_all_players_inside_each_view(
    players: int, size: tuple[int, int]
) -> None:
    for own_seat in range(players):
        slots = player_slot_layout(size, players, own_seat)
        assert len(slots) == players
        assert slots[0][0] == own_seat
        for index, (_, rect) in enumerate(slots):
            assert rect.left >= 0 and rect.top >= 0
            assert rect.right <= size[0] and rect.bottom <= size[1]
            assert all(not rect.colliderect(other) for _, other in slots[index + 1 :])


def test_pickup_hud_labels_are_visible_and_do_not_overlap() -> None:
    items = (
        ("shield", 10.0, "Shield"),
        ("slow_paddle", 30.0, "Slow paddle"),
        ("small_paddle", 80.0, "Small paddle"),
        ("inverted", 150.0, "Inverted controls"),
    )
    labels = [(center, label, name, text_width(label) + 10) for name, center, label in items]
    rows = HudRenderer._pack_pickup_labels(labels, 160)

    assert sum(map(len, rows)) == len(items)
    assert len(rows) > 1
    for row in rows:
        for index, (x, width, _, _) in enumerate(row):
            assert x >= 0 and x + width <= 160
            if index:
                previous_x, previous_width, _, _ = row[index - 1]
                assert previous_x + previous_width < x


def test_spanish_hud_displays_pickup_name_and_player_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _world()
    world.extras.apply("big_paddle", 0, [])
    world.extras.pickups.append(Pickup(Vec2(80.0, 45.0), "small_paddle", 100))
    renderer = Renderer(RenderSettings(view="split"), translator=Translator("es"))
    rendered: list[str] = []
    monkeypatch.setattr(
        hud_module,
        "draw_text",
        lambda _surface, text, *_args: rendered.append(text),
    )
    view = renderer.viewports(world)[0]
    surface = pygame.Surface(view.rect.size)
    renderer.hud.draw(
        surface,
        world,
        renderer._camera_for(view, world),
        renderer.translator,
        renderer.colors,
        "arcade",
        own_seat=view.seat,
    )

    assert "J1 0" in rendered
    assert "Pala grande" in rendered
    assert "Pala pequeña" in rendered


@pytest.mark.parametrize(("width", "own_seat"), [(320, None), (160, 0)])
@pytest.mark.parametrize("extra_count", [0, 1, 2])
def test_active_extra_names_fit_player_panel_for_zero_one_or_two_extras(
    monkeypatch: pytest.MonkeyPatch, width: int, own_seat: int | None, extra_count: int
) -> None:
    world = World(MatchConfig(arena="classic", controllers=("human", "human")))
    active_names = ("big_paddle", "shield")[:extra_count]
    for name in active_names:
        world.extras.apply(name, 0, [])
    renderer = Renderer(translator=Translator("es"))
    surface = pygame.Surface((width, 180))
    rendered: list[tuple[str, int, int]] = []

    def capture(
        _surface: pygame.Surface,
        text: str,
        x: int,
        y: int,
        color: tuple[int, ...],
        scale: int = 1,
    ) -> None:
        if color == pal.WHITE:
            rendered.append((text, x, scale))

    monkeypatch.setattr(hud_module, "draw_text", capture)
    renderer.hud._draw_players(
        surface, world, renderer.translator, renderer.colors, "arcade", own_seat
    )

    slot = next(rect for seat, rect in player_slot_layout((width, 180), 2, own_seat) if seat == 0)
    active_labels = [item for item in rendered if item[0] in ("Pala grande", "Escudo")]
    assert len(active_labels) == extra_count
    assert all(
        x >= slot.left and x + text_width(text, scale) <= slot.right - 2
        for text, x, scale in active_labels
    ), (slot, active_labels)


def test_pickup_labels_are_bottom_anchored_in_original_card_height(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _world()
    world.extras.pickups.append(Pickup(Vec2(80.0, 45.0), "bomb", 100))
    renderer = Renderer()
    camera = renderer._camera_for(renderer.viewports(world)[0], world)
    surface = pygame.Surface((320, 180))
    rendered: list[tuple[str, int, int]] = []
    monkeypatch.setattr(
        hud_module,
        "draw_text",
        lambda _surface, text, _x, y, _color, scale=1: rendered.append((text, y, scale)),
    )

    labels_top = renderer.hud._draw_pickup_labels(
        surface, world, camera, renderer.translator, "arcade"
    )

    assert labels_top == surface.get_height() - 2 - hud_module.HUD_PICKUP_HEIGHT
    name = next(item for item in rendered if item[0] == "Bomb")
    assert name[1] == labels_top + (hud_module.HUD_PICKUP_HEIGHT - 1 - 5) // 2
    assert name[2] == 1


def test_timed_clock_stays_above_bottom_anchored_pickup_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = World(
        MatchConfig(
            mode="timed",
            options=(("duration_seconds", 60),),
            seed=3,
        )
    )
    world.extras.pickups.append(Pickup(Vec2(80.0, 45.0), "bomb", 100))
    renderer = Renderer()
    view = renderer.viewports(world)[0]
    renderer._canvas = pygame.Surface(view.rect.size)
    renderer.camera = renderer._camera_for(view, world)
    rendered: list[tuple[str, int]] = []
    monkeypatch.setattr(
        renderer_module,
        "draw_text",
        lambda _surface, text, _x, y, _color, _scale=1: rendered.append((text, y)),
    )

    renderer._draw_hud(world, view)

    clock_y = next(y for text, y in rendered if text == "01:00")
    pickup_labels_top = view.rect.height - 2 - hud_module.HUD_PICKUP_HEIGHT
    assert clock_y + 5 < pickup_labels_top


def test_extra_name_catalogs_cover_every_effect_and_fit_split_hud() -> None:
    world = _world()
    for language in ("en", "es"):
        translator = Translator(language)
        for name in world.extras.specs:
            label = translator.translate(f"extras.{name}.name")
            assert label != f"extras.{name}.name"
            assert not unsupported_chars(label)
            assert text_width(f"{label} 99") <= 160


def test_countdown_is_drawn_below_the_projected_arena(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pygame.init()
    world = _world()
    positions: list[tuple[str, int, int]] = []

    def capture(
        _surface: pygame.Surface, text: str, x: int, y: int, _color: tuple[int, ...], _scale: int
    ) -> None:
        positions.append((text, x, y))

    monkeypatch.setattr(renderer_module, "draw_text", capture)
    for settings, arena in (
        (RenderSettings(view="shared"), "classic"),
        (RenderSettings(view="split"), "crossfire"),
    ):
        current = (
            world
            if arena == "classic"
            else World(
                MatchConfig(arena="crossfire", controllers=("human", "human", "human", "human"))
            )
        )
        renderer = Renderer(settings)
        for view in renderer.viewports(current):
            renderer._canvas = pygame.Surface(view.rect.size)
            renderer.camera = renderer._camera_for(view)
            positions.clear()
            renderer._draw_hud(current, view)

            countdown = next(item for item in positions if item[0] == "3")
            boundary = max(
                renderer.camera.project(x, y).sy
                for x, y in (
                    (0.0, 0.0),
                    (160.0, 0.0),
                    (160.0, 90.0),
                    (0.0, 90.0),
                )
            )
            assert countdown[2] > boundary
            assert countdown[2] + 5 * BIG_TEXT <= view.rect.height
