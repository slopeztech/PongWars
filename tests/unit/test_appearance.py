"""Tests for backgrounds, player and ball styles, cats, settings and music."""

import os
from array import array
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from pongwars.audio.player import AudioPlayer
from pongwars.core.i18n import Translator
from pongwars.core.settings import (
    BACKGROUNDS,
    BALL_STYLES,
    FIELD_STYLES,
    TRAIL_STYLES,
    Settings,
)
from pongwars.domain.config import MatchConfig
from pongwars.domain.entities import Cat
from pongwars.domain.vec import Vec2
from pongwars.domain.world import FrameInputs, World
from pongwars.render import palette as pal
from pongwars.render.backgrounds import draw_background
from pongwars.render.font import draw_text, text_width, unsupported_chars
from pongwars.render.renderer import Renderer, RenderSettings
from pongwars.ui.core import AppContext
from pongwars.ui.screens import (
    AppearanceScreen,
    HowToPlayScreen,
    MainMenuScreen,
    MatchScreen,
    SettingsScreen,
)


def key(code: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=code)


@pytest.fixture(autouse=True)
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))


@pytest.fixture
def ctx() -> AppContext:
    pygame.init()
    return AppContext(Settings(), Translator(), AudioPlayer())


def test_every_background_draws_and_animates() -> None:
    surface = pygame.Surface((320, 180))
    for name in BACKGROUNDS:
        surface.fill((0, 0, 0))
        draw_background(surface, name, 10, 1)
        draw_background(surface, name, 200, 1)
    surface.fill((0, 0, 0))
    draw_background(surface, "stars", 5, 1)
    assert surface.get_at((0, 0)) is not None


@pytest.mark.parametrize("skin", [0, 1, 2, 3])
def test_skins_and_cat_render(skin: int) -> None:
    pygame.init()
    world = World(MatchConfig(extras=("all",), seed=2))
    world.extras.cats.append(Cat(Vec2(80.0, 45.0), 0, 100, 0))
    for background in BACKGROUNDS:
        renderer = Renderer(
            RenderSettings(
                background=background, paddle_colors=(5, 6, 7, 4), paddle_skins=(skin,) * 4
            )
        )
        world.step(FrameInputs(moves=(0.0, 0.0), fire=(False, False)))
        renderer.update(world, 1 / 60)
        assert renderer.draw(world).get_size() == (320, 180)


def test_settings_sanitise_appearance() -> None:
    s = Settings.from_dict(
        {
            "background": "bogus",
            "ball_style": "bogus",
            "trail_style": "bogus",
            "field_style": "bogus",
            "music_track": 7,
            "paddle_colors": [99, -1],
            "paddle_skins": "x",
        }
    )
    assert s.background == "grid"
    assert s.ball_style == "classic"
    assert s.trail_style == "classic"
    assert s.field_style == "grid"
    assert s.last_menu_track == ""
    assert len(s.paddle_colors) == 4
    assert all(0 <= v < 8 for v in s.paddle_colors)
    assert s.paddle_skins == [0, 0, 0, 0]


def test_appearance_screen_changes_and_persists(ctx: AppContext) -> None:
    screen = AppearanceScreen(ctx)
    surface = pygame.Surface((320, 180))
    screen.draw(surface)
    screen.handle_event(key(pygame.K_RIGHT))
    assert ctx.settings.paddle_colors[0] == 1
    for _ in range(4):
        screen.handle_event(key(pygame.K_DOWN))
    screen.handle_event(key(pygame.K_RIGHT))
    assert ctx.settings.paddle_skins[0] == 1
    for _ in range(4):
        screen.handle_event(key(pygame.K_DOWN))
    screen.handle_event(key(pygame.K_RIGHT))
    assert ctx.settings.background == BACKGROUNDS[BACKGROUNDS.index("grid") + 1]
    screen.handle_event(key(pygame.K_DOWN))
    screen.handle_event(key(pygame.K_RIGHT))
    assert ctx.settings.ball_style == BALL_STYLES[1]
    screen.handle_event(key(pygame.K_DOWN))
    screen.handle_event(key(pygame.K_RIGHT))
    assert ctx.settings.trail_style == TRAIL_STYLES[1]
    screen.handle_event(key(pygame.K_DOWN))
    screen.handle_event(key(pygame.K_RIGHT))
    assert ctx.settings.field_style == FIELD_STYLES[1]
    persisted = Settings.load()
    assert persisted.ball_style == ctx.settings.ball_style
    assert persisted.trail_style == ctx.settings.trail_style
    assert persisted.field_style == ctx.settings.field_style
    assert all(item.label() != "Match music" for item in SettingsScreen(ctx).menu.items)
    settings = SettingsScreen(ctx)
    assert all(item.label() != "Canción de partida" for item in settings.menu.items)
    screen.draw(surface)


def test_match_renderer_uses_saved_ball_trail_and_field_styles(ctx: AppContext) -> None:
    ctx.settings.ball_style = "energy"
    ctx.settings.trail_style = "neon"
    ctx.settings.field_style = "checker"

    screen = MatchScreen(ctx, MatchConfig(seed=3))

    assert screen.renderer.settings.ball_style == "energy"
    assert screen.renderer.settings.trail_style == "neon"
    assert screen.renderer.settings.field_style == "checker"


@pytest.mark.parametrize(
    ("setting", "choices"),
    [
        ("ball_style", BALL_STYLES),
        ("trail_style", TRAIL_STYLES),
        ("field_style", FIELD_STYLES),
    ],
)
def test_every_ball_trail_and_field_style_renders(
    setting: str, choices: tuple[str, ...]
) -> None:
    pygame.init()
    world = World(MatchConfig())
    outputs: set[bytes] = set()
    for choice in choices:
        settings = RenderSettings(**{setting: choice})
        renderer = Renderer(settings)
        renderer.trail.push(70, 40)
        renderer.trail.push(75, 43)
        outputs.add(pygame.image.tobytes(renderer.draw(world), "RGB"))
    assert len(outputs) == len(choices)


def test_how_to_play_pages(ctx: AppContext) -> None:
    ctx.stack.push(HowToPlayScreen(ctx))
    screen = ctx.stack.top
    assert isinstance(screen, HowToPlayScreen)
    surface = pygame.Surface((320, 180))
    for _ in range(screen.PAGES + 1):
        screen.draw(surface)
        screen.handle_event(key(pygame.K_RIGHT))
    assert screen.page == 2
    screen.handle_event(key(pygame.K_LEFT))
    screen.handle_event(key(pygame.K_LEFT))
    assert screen.page == screen.PAGES
    screen.handle_event(pygame.event.Event(pygame.MOUSEMOTION))
    screen.handle_event(key(pygame.K_ESCAPE))
    assert ctx.stack.top is None


def test_match_music_starts_from_random_playlist(ctx: AppContext) -> None:
    assert ctx.audio.jukebox is not None
    ctx.audio.jukebox._threaded = False
    ctx.audio.jukebox._renderer = lambda _song: array("h", [0] * 8)
    MatchScreen(ctx, MatchConfig(seed=1))
    assert ctx.audio.jukebox.context == "match"
    assert ctx.audio.jukebox.current in ctx.audio.song_ids("match")


def test_main_menu_shows_now_playing(ctx: AppContext) -> None:
    assert ctx.audio.jukebox is not None
    ctx.audio.jukebox._threaded = False
    ctx.audio.jukebox._renderer = lambda _song: array("h", [0] * 8)
    song_id = ctx.audio.song_ids("menu")[0]
    ctx.audio.start_music("menu", first=song_id)
    assert ctx.audio.now_playing() is not None
    surface = pygame.Surface((320, 180))
    screen = MainMenuScreen(ctx)
    screen.draw(surface)
    ctx.music_notice.update(
        (ctx.audio.music_context, ctx.audio.current_song_id() or ""),
        ctx.audio.now_playing(),
        0,
    )
    assert ctx.music_notice.visible
    ctx.music_notice.update(
        (ctx.audio.music_context, ctx.audio.current_song_id() or ""),
        ctx.audio.now_playing(),
        0.3,
    )
    ctx.music_notice.draw(surface)
    assert surface.get_at((202, 133))[:3] == pal.UI_CYAN
    assert surface.get_at((313, 156))[:3] == pal.UI_CYAN
    assert surface.get_at((201, 132))[:3] == pal.UI_BACKGROUND


def test_main_menu_uses_reference_pixel_art_frame(ctx: AppContext) -> None:
    surface = pygame.Surface((320, 180))
    MainMenuScreen(ctx).draw(surface)

    assert surface.get_at((0, 0))[:3] == pal.UI_BACKGROUND
    assert unsupported_chars("slopeztech") == set()
    expected_footer = pygame.Surface((320, 6))
    expected_footer.fill(pal.UI_BACKGROUND)
    draw_text(
        expected_footer,
        "slopeztech",
        (320 - text_width("slopeztech")) // 2,
        0,
        pal.UI_MUTED,
    )
    for x in range(320):
        for y in range(6):
            assert surface.get_at((x, 169 + y))[:3] == expected_footer.get_at((x, y))[:3]
    assert surface.get_at((110, 166))[:3] == pal.UI_MUTED
    assert surface.get_at((123, 61))[:3] == pal.UI_CYAN
    assert surface.get_at((14, 70))[:3] == pal.UI_CYAN
    assert pal.UI_CYAN not in {
        surface.get_at((x, y))[:3] for x in range(126, 194) for y in range(64, 69)
    }


def test_main_menu_start_song_avoids_previous_launch_track(ctx: AppContext) -> None:
    assert ctx.audio.jukebox is not None
    ctx.audio.jukebox._threaded = False
    ctx.audio.jukebox._renderer = lambda _song: array("h", [0] * 8)
    previous = ctx.audio.song_ids("menu")[0]
    ctx.settings.last_menu_track = previous

    MainMenuScreen(ctx)

    assert ctx.settings.last_menu_track != previous
    assert ctx.audio.jukebox.current == ctx.settings.last_menu_track
