"""@file test_render_extras.py
@brief Headless smoke test for extras rendering (pickups, effects, lasers and blind field).
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from pongwars.core.i18n import Translator
from pongwars.domain.config import MatchConfig
from pongwars.domain.events import BallWarped, BombDetonated, Event
from pongwars.domain.extras import Pickup
from pongwars.domain.vec import Vec2
from pongwars.domain.world import FrameInputs, World
from pongwars.render import palette as pal
from pongwars.render import renderer as renderer_module
from pongwars.render.font import text_width, unsupported_chars
from pongwars.render.renderer import BIG_TEXT, Renderer, RenderSettings


def _world() -> World:
    return World(MatchConfig(extras=("all",), seed=3))


def test_draws_every_extra_without_error() -> None:
    """@brief Pickups, active effects, shield, laser flash and blind field render."""
    pygame.init()
    for view in ("shared", "split"):
        world = _world()
        renderer = Renderer(RenderSettings(view=view))
        for name in ("shield", "blind", "laser", "multiball", "big_paddle"):
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


def test_shared_hud_draws_each_players_extras_under_their_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pygame.init()
    world = _world()
    renderer = Renderer()
    renderer._canvas = pygame.Surface((320, 180))
    world.extras.apply("shield", 0, [])
    world.extras.apply("slow_paddle", 1, [])
    positions: list[tuple[str, int, int]] = []

    def capture(
        _surface: pygame.Surface, text: str, x: int, y: int, _color: tuple[int, ...], _scale: int
    ) -> None:
        positions.append((text, x, y))

    monkeypatch.setattr(renderer_module, "draw_text", capture)
    anchors = renderer._draw_shared_scores(world, 320)
    renderer._draw_effects(world, anchors, None)

    assert next(item[1:] for item in positions if item[0].startswith("Shield")) == anchors[0]
    assert next(item[1:] for item in positions if item[0].startswith("Slow paddle")) == anchors[1]
    assert anchors[0][0] != anchors[1][0]


def test_split_hud_keeps_extras_under_the_affected_players_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pygame.init()
    world = World(
        MatchConfig(arena="crossfire", controllers=("human", "human", "human", "human"))
    )
    renderer = Renderer(RenderSettings(view="split"))
    view = renderer.viewports(world)[0]
    renderer._canvas = pygame.Surface(view.rect.size)
    world.extras.apply("shield", 0, [])
    world.extras.apply("slow_paddle", 1, [])
    positions: list[tuple[str, int, int]] = []

    def capture(
        _surface: pygame.Surface, text: str, x: int, y: int, _color: tuple[int, ...], _scale: int
    ) -> None:
        positions.append((text, x, y))

    monkeypatch.setattr(renderer_module, "draw_text", capture)
    anchors = renderer._draw_split_scores(world, 0, view.rect.width)
    renderer._draw_effects(world, anchors, view.seat)

    assert next(item[1:] for item in positions if item[0].startswith("Shield")) == anchors[0]
    assert next(item[1:] for item in positions if item[0].startswith("Slow paddle")) == anchors[1]


def test_spanish_hud_draws_complete_effect_and_weapon_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pygame.init()
    world = _world()
    renderer = Renderer(RenderSettings(view="split"), translator=Translator("es"))
    view = renderer.viewports(world)[0]
    renderer._canvas = pygame.Surface(view.rect.size)
    world.extras.apply("inverted", 0, [])
    world.extras.apply("aim_assist", 0, [])
    world.extras.weapons[0] = ("freeze", 2)
    world.extras.pickups.append(Pickup(Vec2(80.0, 45.0), "small_paddle", 100))
    rendered: list[tuple[str, int, int]] = []

    def capture(
        _surface: pygame.Surface, text: str, x: int, y: int, _color: tuple[int, ...], _scale: int
    ) -> None:
        rendered.append((text, x, y))

    monkeypatch.setattr(renderer_module, "draw_text", capture)
    assert view.seat is not None
    anchors = renderer._draw_split_scores(world, view.seat, view.rect.width)
    renderer._draw_effects(world, anchors, view.seat)
    renderer._pickup(world, 0)

    assert {text for text, _, _ in rendered} >= {
        "Controles invertidos 7",
        "Asistencia de puntería 11",
        "Congelar X2",
        "Pala pequeña",
    }
    assert all(x >= 0 and x + text_width(text) <= view.rect.width for text, x, _ in rendered)
    effect_rows = {
        y
        for text, _, y in rendered
        if text.startswith(("Controles", "Asistencia", "Congelar"))
    }
    assert len(effect_rows) == 3


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
                MatchConfig(
                    arena="crossfire", controllers=("human", "human", "human", "human")
                )
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
