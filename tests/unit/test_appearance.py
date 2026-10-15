"""Tests for appearance: backgrounds, paddle skins, cats, settings and music choice."""

import os
from array import array
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from pongwars.audio.player import AudioPlayer
from pongwars.core.i18n import Translator
from pongwars.core.settings import BACKGROUNDS, Settings
from pongwars.domain.config import MatchConfig
from pongwars.domain.entities import Cat
from pongwars.domain.vec import Vec2
from pongwars.domain.world import FrameInputs, World
from pongwars.render.backgrounds import draw_background
from pongwars.render.renderer import Renderer, RenderSettings
from pongwars.ui.core import AppContext
from pongwars.ui.screens import AppearanceScreen, HowToPlayScreen, MainMenuScreen, MatchScreen


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
            "music_track": 7,
            "paddle_colors": [99, -1],
            "paddle_skins": "x",
        }
    )
    assert s.background == "grid"
    assert s.music_track == "random"
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
    assert ctx.settings.music_track != "random"
    screen.handle_event(key(pygame.K_LEFT))
    assert ctx.settings.music_track == "random"
    screen.draw(surface)


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


def test_match_music_follows_the_setting(ctx: AppContext) -> None:
    assert ctx.audio.jukebox is not None
    ctx.audio.jukebox._threaded = False
    ctx.audio.jukebox._renderer = lambda _song: array("h", [0] * 8)
    first = ctx.audio.song_ids("match")[0]
    ctx.settings.music_track = first
    MatchScreen(ctx, MatchConfig(seed=1))
    assert ctx.audio.jukebox.context == "match"
    assert ctx.audio.jukebox.current == first
    ctx.settings.music_track = "random"
    MatchScreen(ctx, MatchConfig(seed=5))
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
    ctx.audio.jukebox.current = ""
    assert ctx.audio.now_playing() is None
    screen.draw(surface)
