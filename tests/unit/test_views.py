"""! @file test_views.py
@brief Tests for split-screen viewports, camera rotation and the translated HUD.
"""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from pongwars.core.i18n import Translator  # noqa: E402
from pongwars.domain.config import MatchConfig  # noqa: E402
from pongwars.domain.world import World  # noqa: E402
from pongwars.render import renderer as renderer_module  # noqa: E402
from pongwars.render.camera import Camera  # noqa: E402
from pongwars.render.renderer import (  # noqa: E402
    LOW_H,
    LOW_W,
    Renderer,
    RenderSettings,
    split_viewports,
)


@pytest.mark.parametrize("players", [2, 3, 4])
def test_viewports_fit_the_canvas(players: int) -> None:
    """! @brief Every viewport lies inside the low-res canvas, one per seat."""
    views = split_viewports(players)
    assert sorted(v.seat or 0 for v in views) == list(range(players))
    for v in views:
        assert v.rect.left >= 0 and v.rect.top >= 0
        assert v.rect.right <= LOW_W and v.rect.bottom <= LOW_H


def test_rotation_is_identity_after_four_turns() -> None:
    """! @brief Four quarter turns bring a point back to itself."""
    cam = Camera(LOW_W, LOW_H, quarter_turns=4)
    assert cam.rotate(10.0, 5.0) == pytest.approx((10.0, 5.0))


@pytest.mark.parametrize(
    ("arena", "players"),
    [("classic", 2), ("trident", 3), ("crossfire", 4)],
)
@pytest.mark.parametrize("view", ["shared", "split"])
def test_render_all_views(arena: str, players: int, view: str) -> None:
    """! @brief Rendering works for every arena in both camera modes."""
    pygame.init()
    cfg = MatchConfig(arena=arena, controllers=("human",) * players)
    world = World(cfg)
    renderer = Renderer(RenderSettings(view=view, scale=1))  # type: ignore[arg-type]
    screen = pygame.display.set_mode((LOW_W, LOW_H))
    renderer.present(world, screen)


def test_hud_uses_translator() -> None:
    """! @brief The HUD resolves its labels through the injected translator."""
    pygame.init()
    seen: list[str] = []

    class Spy(Translator):
        """! @brief Translator recording requested keys."""

        def translate(self, key: str, count: int | None = None, **params: object) -> str:
            seen.append(key)
            return super().translate(key, count, **params)

    renderer = Renderer(RenderSettings(scale=1), translator=Spy())
    screen = pygame.display.set_mode((LOW_W, LOW_H))
    renderer.present(World(MatchConfig()), screen)
    assert any(k.startswith("hud.") for k in seen)


def test_timed_hud_draws_clock_at_bottom_of_arena(monkeypatch: pytest.MonkeyPatch) -> None:
    pygame.init()
    drawn: list[tuple[str, int, int]] = []
    draw_text = renderer_module.draw_text

    def record_text(
        surface: pygame.Surface,
        text: str,
        x: int,
        y: int,
        color: tuple[int, int, int],
        scale: int = 1,
    ) -> None:
        drawn.append((text, x, y))
        draw_text(surface, text, x, y, color, scale)

    monkeypatch.setattr(renderer_module, "draw_text", record_text)
    world = World(MatchConfig(mode="timed", options=(("duration_seconds", 120),)))
    world.tick = 61
    renderer = Renderer(RenderSettings(scale=1))
    renderer.draw(world)

    assert any(text == "01:59" and y == LOW_H - 5 - 4 for text, _, y in drawn)
