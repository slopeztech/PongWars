"""Phase 6 tests: settings, audio, font coverage and the UI screens."""

import os
import re
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from pongwars.audio.player import AudioPlayer, load_bank
from pongwars.audio.synth import ToneSpec, note_frequency, render_tone
from pongwars.core.i18n import Translator, available_languages, load_catalog
from pongwars.core.settings import Settings
from pongwars.domain.arenas import arena_names
from pongwars.domain.events import Goal
from pongwars.domain.modes import MODES
from pongwars.domain.world import Phase
from pongwars.render.font import normalize, unsupported_chars
from pongwars.render.renderer import LOW_H, LOW_W
from pongwars.ui.core import AppContext
from pongwars.ui.screens import (
    AppearanceScreen,
    HelpMenuScreen,
    LanMenuScreen,
    MainMenuScreen,
    MatchScreen,
    PauseScreen,
    ResultsScreen,
    SettingsScreen,
    SetupScreen,
    TitleScreen,
    make_keymap,
)
from pongwars.ui.widgets import Menu, MenuItem


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


# --- settings -------------------------------------------------------------


def test_settings_round_trip_and_clamping(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    original = Settings(master_volume=30, language="es", view="split", keys={"0": [1, 2]})
    assert original.save(path)
    assert Settings.load(path) == original
    clamped = Settings.from_dict({"master_volume": 900, "scale": 99, "view": "bogus"})
    assert clamped.master_volume == 100
    assert clamped.scale == 8
    assert clamped.view == "shared"


def test_settings_tolerate_corruption(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    assert Settings.load(path) == Settings()
    path.write_text("{not json", encoding="utf-8")
    assert Settings.load(path) == Settings()
    path.write_text("[1]", encoding="utf-8")
    assert Settings.load(path) == Settings()
    assert Settings.from_dict({"fullscreen": 1, "language": 5}) == Settings()


def test_settings_save_failure_is_reported(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    assert Settings().save(blocker / "sub" / "s.json") is False


def test_make_keymap_falls_back_on_bad_data() -> None:
    assert make_keymap({"0": [pygame.K_a, pygame.K_a]}).get(0).negative == pygame.K_w
    assert make_keymap({"0": [pygame.K_a, pygame.K_z]}).get(0).negative == pygame.K_a


# --- audio ----------------------------------------------------------------


def test_render_tone_bounds_and_errors() -> None:
    for wave in ("square", "triangle", "noise"):
        samples = render_tone(ToneSpec(wave, 440, 220, 0.05, 0.5))
        assert len(samples) == int(0.05 * 22050)
        assert max(abs(s) for s in samples) <= 32767
    with pytest.raises(ValueError):
        render_tone(ToneSpec("saw", 440, 440, 0.1))
    with pytest.raises(ValueError):
        render_tone(ToneSpec("square", 440, 440, 0))


def test_notes() -> None:
    assert note_frequency(0) == pytest.approx(440.0)
    assert note_frequency(12) == pytest.approx(880.0)


def test_bank_maps_every_event_to_a_sound() -> None:
    bank = load_bank()
    assert "Goal" in bank.events
    assert set(bank.events.values()) <= set(bank.sounds)


def test_player_plays_and_handles_events(ctx: AppContext) -> None:
    audio = ctx.audio
    assert audio.enabled
    audio.set_volumes(50, 50, 50)
    assert audio.play("paddle")
    assert not audio.play("does_not_exist")
    assert audio.handle_events([Goal(scorer=0, conceded=1)]) == 1
    audio.start_music()
    audio.start_music("match", first=audio.song_ids("match")[0])
    audio.start_music("match", first="no_such_track")
    audio.update()
    audio.set_volumes(0, 0, 0)
    audio.stop_music()


def test_player_is_silent_without_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pygame.mixer, "get_init", lambda: None)

    def fail(*_a: object, **_k: object) -> None:
        raise pygame.error("no device")

    monkeypatch.setattr(pygame.mixer, "init", fail)
    audio = AudioPlayer()
    assert not audio.enabled
    assert not audio.play("paddle")
    audio.start_music()
    audio.stop_music()


# --- font -----------------------------------------------------------------


def test_normalize_strips_accents() -> None:
    assert normalize("¡Canción!") == "CANCION!"
    assert unsupported_chars("ABC") == set()


def test_every_catalog_string_is_drawable() -> None:
    for lang in available_languages():
        for key_, text in load_catalog(lang).items():
            plain = re.sub(r"\{[^}]*\}", "", text)
            assert not unsupported_chars(plain), f"{lang}:{key_}"


def test_spanish_keys_exist_in_english() -> None:
    assert set(load_catalog("es")) <= set(load_catalog("en"))


# --- widgets --------------------------------------------------------------


def test_menu_navigation_skips_disabled() -> None:
    log: list[str] = []
    menu = Menu(
        [
            MenuItem(lambda: "a", on_activate=lambda: log.append("a")),
            MenuItem(lambda: "b", enabled=False),
            MenuItem(lambda: "c", on_adjust=lambda d: log.append(f"c{d}")),
        ]
    )
    assert menu.handle_key(pygame.K_DOWN)
    assert menu.index == 2
    menu.handle_key(pygame.K_RIGHT)
    menu.handle_key(pygame.K_LEFT)
    menu.handle_key(pygame.K_RETURN)
    menu.handle_key(pygame.K_DOWN)
    assert menu.index == 0
    menu.handle_key(pygame.K_RETURN)
    assert log == ["c1", "c-1", "c1", "a"]
    assert not menu.handle_key(pygame.K_x)
    surface = pygame.Surface((LOW_W, LOW_H))
    menu.draw(surface, 10, 10, 100)
    Menu().draw(surface, 0, 0, 10)
    assert not Menu().handle_key(pygame.K_UP)


# --- screens --------------------------------------------------------------


def test_app_runs_frames_and_quits() -> None:
    from pongwars.app import App

    app = App(Settings())
    try:
        assert app.tick(0.016)
        pygame.event.post(key(pygame.K_RETURN))
        assert app.tick(0.016)
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        assert not app.tick(0.016)
        app.settings.scale = 3
        app.apply_display()
        assert app.window.get_size() == (LOW_W * 3, LOW_H * 3)
    finally:
        pygame.quit()


def test_fourth_default_binding_exists() -> None:
    assert make_keymap({}).get(3).negative == pygame.K_KP8


def test_title_to_menu_and_quit(ctx: AppContext) -> None:
    ctx.stack.push(TitleScreen(ctx))
    surface = pygame.Surface((LOW_W, LOW_H))
    ctx.stack.update(0.7)
    ctx.stack.draw(surface)
    ctx.stack.handle_event(key(pygame.K_RETURN))
    assert isinstance(ctx.stack.top, MainMenuScreen)
    ctx.stack.draw(surface)
    ctx.stack.handle_event(key(pygame.K_ESCAPE))
    assert isinstance(ctx.stack.top, TitleScreen)
    ctx.stack.handle_event(key(pygame.K_ESCAPE))
    assert ctx.stack.top is None
    assert len(ctx.stack) == 0


def test_main_menu_entries(ctx: AppContext) -> None:
    menu = MainMenuScreen(ctx)
    ctx.stack.push(menu)
    menu.handle_event(key(pygame.K_RETURN))
    setup = ctx.stack.top
    assert isinstance(setup, SetupScreen)
    assert setup.controllers == ["human", "human"]
    ctx.stack.pop()
    menu.handle_event(key(pygame.K_DOWN))
    menu.handle_event(key(pygame.K_RETURN))
    assert isinstance(ctx.stack.top, LanMenuScreen)
    ctx.stack.pop()
    menu.handle_event(key(pygame.K_DOWN))
    menu.handle_event(key(pygame.K_RETURN))
    assert isinstance(ctx.stack.top, HelpMenuScreen)
    ctx.stack.pop()
    menu.handle_event(key(pygame.K_DOWN))
    menu.handle_event(key(pygame.K_RETURN))
    assert isinstance(ctx.stack.top, AppearanceScreen)
    ctx.stack.pop()
    menu.handle_event(key(pygame.K_DOWN))
    menu.handle_event(key(pygame.K_RETURN))
    assert isinstance(ctx.stack.top, SettingsScreen)
    ctx.stack.pop()
    menu.handle_event(key(pygame.K_DOWN))
    menu.handle_event(key(pygame.K_RETURN))
    assert ctx.stack.top is None


def test_setup_builds_valid_config_for_every_mode_and_arena(ctx: AppContext) -> None:
    setup = SetupScreen(ctx, ("human", "ai"))
    surface = pygame.Surface((LOW_W, LOW_H))
    for mode in MODES.names():
        for arena in arena_names():
            setup.mode, setup.arena = mode, arena
            setup._reset_options()
            setup._fit_controllers()
            setup.rebuild()
            setup.draw(surface)
            config = setup.build_config(seed=1)
            assert config.controllers == tuple(setup.controllers)
            assert len(config.controllers) == setup.spec.players
            assert MatchScreen(ctx, config).world.players == setup.spec.players


def test_setup_cycles_and_options(ctx: AppContext) -> None:
    setup = SetupScreen(ctx)
    setup.handle_event(key(pygame.K_RIGHT))
    assert setup.mode != "classic"
    setup.handle_event(key(pygame.K_LEFT))
    assert setup.mode == "classic"
    setup.handle_event(key(pygame.K_DOWN))
    setup.handle_event(key(pygame.K_RIGHT))
    assert setup.arena != "classic"
    spec = next(o for o in setup._option_specs() if o.kind == "int")
    setup._adjust_option(spec, 1)
    setup._adjust_option(spec, -1)
    boolean = next(o for o in setup._option_specs() if o.kind == "bool")
    setup._adjust_option(boolean, 1)
    assert setup.options[boolean.name] != float(boolean.default)
    setup.extras = "all"
    setup.controllers[0] = "ai"
    config = setup.build_config()
    assert config.extras == ("all",)


def test_setup_remembers_last_match_options(ctx: AppContext) -> None:
    setup = SetupScreen(ctx)
    setup.mode = "classic"
    setup.arena = "crossfire"
    setup.extras = "all"
    setup.view = "split"
    setup.room_name = "FRIENDS ROOM"
    setup.options = {"points_to_win": 9.0}
    setup._save_last_match()

    restored = SetupScreen(ctx)
    assert restored.mode == "classic"
    assert restored.arena == "crossfire"
    assert restored.extras == "all"
    assert restored.view == "split"
    assert restored.room_name == "FRIENDS ROOM"
    assert restored.options["points_to_win"] == 9.0


def test_start_pushes_match_and_flows_to_results(ctx: AppContext) -> None:
    setup = SetupScreen(ctx, ("ai", "ai"))
    setup.options["points_to_win"] = 1.0
    setup.difficulty = "easy"
    ctx.stack.push(setup)
    setup.start()
    match = ctx.stack.top
    assert isinstance(match, MatchScreen)
    surface = pygame.Surface((LOW_W, LOW_H))
    for _ in range(4000):
        ctx.stack.update(1 / 30)
        ctx.stack.draw(surface)
        if match.world.phase is Phase.FINISHED:
            break
    assert isinstance(ctx.stack.top, ResultsScreen)
    results = ctx.stack.top
    assert results.headline()
    ctx.stack.draw(surface)
    results.handle_event(key(pygame.K_RETURN))  # rematch
    assert isinstance(ctx.stack.top, MatchScreen)
    ctx.stack.top.world.winner = None
    ctx.stack.replace(ResultsScreen(ctx, ctx.stack.top.config, ctx.stack.top.world, "shared"))
    ctx.stack.handle_event(key(pygame.K_ESCAPE))
    assert ctx.stack.top is not None


def test_pause_overlay_freezes_match(ctx: AppContext) -> None:
    setup = SetupScreen(ctx)
    ctx.stack.push(MainMenuScreen(ctx))
    ctx.stack.push(setup)
    setup.start()
    match = ctx.stack.top
    assert isinstance(match, MatchScreen)
    surface = pygame.Surface((LOW_W, LOW_H))
    ctx.stack.update(0.1)
    tick = match.world.tick
    ctx.stack.handle_event(key(pygame.K_ESCAPE))
    assert isinstance(ctx.stack.top, PauseScreen)
    ctx.stack.update(0.5)
    ctx.stack.draw(surface)
    assert match.world.tick == tick
    ctx.stack.handle_event(key(pygame.K_ESCAPE))
    assert not isinstance(ctx.stack.top, PauseScreen)
    ctx.stack.handle_event(key(pygame.K_ESCAPE))
    ctx.stack.handle_event(key(pygame.K_DOWN))
    ctx.stack.handle_event(key(pygame.K_DOWN))
    ctx.stack.handle_event(key(pygame.K_RETURN))
    assert isinstance(ctx.stack.top, MainMenuScreen)


def test_pause_opens_settings(ctx: AppContext) -> None:
    ctx.stack.push(PauseScreen(ctx))
    ctx.stack.handle_event(key(pygame.K_DOWN))
    ctx.stack.handle_event(key(pygame.K_RETURN))
    assert isinstance(ctx.stack.top, SettingsScreen)


def test_settings_changes_apply_and_persist(ctx: AppContext) -> None:
    screen = SettingsScreen(ctx)
    screen.handle_event(key(pygame.K_LEFT))
    assert ctx.settings.master_volume == 70
    screen.menu.index = 5
    screen.handle_event(key(pygame.K_RIGHT))
    assert ctx.settings.language == "es"
    assert ctx.translator.language == "es"
    screen.handle_event(key(pygame.K_LEFT))
    for index in (3, 4, 6, 7, 8, 9):
        screen.menu.index = index
        screen.handle_event(key(pygame.K_RIGHT))
    assert ctx.settings.fullscreen
    assert ctx.settings.scale == 5
    assert ctx.settings.view == "split"
    ctx.stack.push(screen)
    screen.draw(pygame.Surface((LOW_W, LOW_H)))
    assert Settings.load() == ctx.settings


def test_key_rebinding_capture(ctx: AppContext) -> None:
    screen = SettingsScreen(ctx)
    screen.menu.index = 10
    screen.handle_event(key(pygame.K_RETURN))
    assert screen.capturing == 0
    surface = pygame.Surface((LOW_W, LOW_H))
    screen.draw(surface)
    screen.handle_event(key(pygame.K_q))
    screen.handle_event(key(pygame.K_a))
    assert screen.capturing is None
    assert ctx.keymap.get(0).negative == pygame.K_q
    assert ctx.settings.keys["0"] == [pygame.K_q, pygame.K_a]
    screen.begin_capture(0)
    screen.handle_event(key(pygame.K_ESCAPE))
    assert screen.capturing is None
    screen.begin_capture(0)
    screen.handle_event(key(pygame.K_UP))
    screen.handle_event(key(pygame.K_z))
    assert screen.error == "input.error.key_in_use"
    screen.draw(surface)
