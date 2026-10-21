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
    HUD_STYLES,
    PADDLE_COLOR_COUNT,
    PADDLE_SKIN_COUNT,
    TRAIL_STYLES,
    Settings,
)
from pongwars.domain import constants as c
from pongwars.domain.config import MatchConfig
from pongwars.domain.entities import Cat
from pongwars.domain.vec import Vec2
from pongwars.domain.world import FrameInputs, World
from pongwars.render import palette as pal
from pongwars.render.backgrounds import (
    SPECTATOR_COLORS,
    SPECTATOR_HAIR_COLORS,
    draw_background,
)
from pongwars.render.font import draw_text, text_width, unsupported_chars
from pongwars.render.renderer import Renderer, RenderSettings
from pongwars.ui import screens as screens_module
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
    frames: set[bytes] = set()
    for name in BACKGROUNDS:
        surface.fill((0, 0, 0))
        draw_background(surface, name, 10, 1)
        surface.fill((0, 0, 0))
        draw_background(surface, name, 200, 1)
        frames.add(pygame.image.tobytes(surface, "RGB"))
    assert len(frames) == len(BACKGROUNDS) - 1
    surface.fill((0, 0, 0))
    draw_background(surface, "stars", 5, 1)
    assert surface.get_at((0, 0)) is not None


@pytest.mark.parametrize(
    "background", [name for name in BACKGROUNDS if name not in ("none", "grid")]
)
def test_animated_backgrounds_cover_the_full_screen(background: str) -> None:
    surface = pygame.Surface((320, 180))
    surface.fill(pal.BLACK)

    draw_background(surface, background, 37, 4)

    assert all(
        surface.get_at((x, y))[:3] != pal.BLACK
        for x in range(surface.get_width())
        for y in range(surface.get_height())
    )


def test_aurora_curtains_span_the_screen_height() -> None:
    surface = pygame.Surface((320, 180))
    surface.fill(pal.BLACK)
    draw_background(surface, "aurora", 37, 4)
    base = pygame.Surface(surface.get_size())
    base.fill(pal.BLACK)
    draw_background(base, "unpatterned", 37, 4)

    changed_rows = [
        y
        for y in range(surface.get_height())
        if any(surface.get_at((x, y)) != base.get_at((x, y)) for x in range(surface.get_width()))
    ]

    assert changed_rows
    assert changed_rows[-1] - changed_rows[0] >= surface.get_height() * 0.75


def test_stadium_crowd_animates_with_different_spectators() -> None:
    surface = pygame.Surface((320, 180))
    first_frame = pygame.Surface(surface.get_size())
    second_frame = pygame.Surface(surface.get_size())

    draw_background(first_frame, "stadium", 10, 4)
    draw_background(second_frame, "stadium", 11, 4)

    assert pygame.image.tobytes(first_frame, "RGB") != pygame.image.tobytes(second_frame, "RGB")


def test_stadium_bottom_row_stays_visible_while_spectators_move() -> None:
    surface = pygame.Surface((320, 180))
    spectator_colors = {pal.shade(color, 0.42) for color in SPECTATOR_COLORS}
    spectator_colors.add(pal.shade(pal.PEACH, 0.62))
    spectator_colors.update(SPECTATOR_HAIR_COLORS)

    for tick in range(0, 120, 5):
        draw_background(surface, "stadium", tick, 4)
        visible_pixels = sum(
            surface.get_at((x, y))[:3] in spectator_colors
            for x in range(surface.get_width())
            for y in range(150, surface.get_height())
        )
        assert visible_pixels >= 3000


def test_stadium_fills_the_background_with_spectators_and_paddle_flags() -> None:
    surface = pygame.Surface((320, 180))
    draw_background(surface, "stadium", 37, 4)
    width, height = surface.get_size()

    assert any(
        surface.get_at((x, y))[:3] in pal.PADDLE_PALETTE
        for x in range(width)
        for y in range(height)
    )
    spectator_colors = {pal.shade(color, 0.42) for color in SPECTATOR_COLORS}
    spectator_colors.add(pal.shade(pal.PEACH, 0.62))
    spectator_colors.update(SPECTATOR_HAIR_COLORS)
    assert (
        sum(
            surface.get_at((x, y))[:3] in spectator_colors
            for x in range(width)
            for y in range(height)
        )
        >= 12000
    )
    assert (
        sum(
            surface.get_at((x, y))[:3] in spectator_colors
            for x in range(width)
            for y in range(round(height * 0.9), height)
        )
        >= 300
    )
    flag_colors = {
        surface.get_at((x, y))[:3]
        for x in range(width)
        for y in range(height)
        if surface.get_at((x, y))[:3] in pal.PADDLE_PALETTE
    }
    assert len(flag_colors) >= 2
    assert (
        sum(
            surface.get_at((x, y))[:3] in spectator_colors
            for x in range(width)
            for y in range(round(height * 0.77), round(height * 0.82))
        )
        < 100
    )


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


def test_ramp_animation_and_sound_are_connected(monkeypatch: pytest.MonkeyPatch) -> None:
    from pongwars.domain.events import EffectApplied

    pygame.init()
    world = World(MatchConfig(extras=("all",), seed=2))
    world.extras.apply_direct("ramp", 0, [])
    world.extras.tick_effects([])
    renderer = Renderer()
    renderer.update(world, 1 / 60)

    assert renderer._ramp_incline > 0.0
    audio = AudioPlayer()
    played: list[str] = []
    monkeypatch.setattr(audio, "play", lambda name: played.append(name) is None)
    assert "ramp" in audio.bank.sounds
    assert audio.handle_events([EffectApplied(0, "ramp")]) == 1
    assert played == ["ramp"]
    audio.close()
    renderer.handle_events(world, [EffectApplied(0, "ramp")])
    assert renderer.shake.amplitude > 0.0


def test_settings_sanitise_appearance() -> None:
    assert PADDLE_COLOR_COUNT == len(pal.PADDLE_PALETTE) == 24
    assert PADDLE_SKIN_COUNT == 20
    assert len(BACKGROUNDS) == 23
    assert (len(BALL_STYLES), len(TRAIL_STYLES), len(FIELD_STYLES)) == (20, 19, 20)
    s = Settings.from_dict(
        {
            "background": "bogus",
            "ball_style": "bogus",
            "trail_style": "bogus",
            "field_style": "bogus",
            "hud_style": "bogus",
            "music_track": 7,
            "paddle_colors": [99, -1],
            "paddle_skins": "x",
        }
    )
    assert s.background == "grid"
    assert s.ball_style == "classic"
    assert s.trail_style == "classic"
    assert s.field_style == "grid"
    assert s.hud_style == "arcade"
    assert s.last_menu_track == ""
    assert len(s.paddle_colors) == 4
    assert all(0 <= v < PADDLE_COLOR_COUNT for v in s.paddle_colors)
    assert s.paddle_skins == [0, 0, 0, 0]


def test_appearance_screen_changes_and_persists(ctx: AppContext) -> None:
    screen = AppearanceScreen(ctx)
    surface = pygame.Surface((320, 180))
    screen.draw(surface)
    screen.handle_event(key(pygame.K_RIGHT))
    assert ctx.settings.paddle_colors[0] == 1
    screen.handle_event(key(pygame.K_RETURN))
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
    screen.handle_event(key(pygame.K_DOWN))
    screen.handle_event(key(pygame.K_RIGHT))
    assert ctx.settings.hud_style == HUD_STYLES[1]
    persisted = Settings.load()
    assert persisted.ball_style == ctx.settings.ball_style
    assert persisted.trail_style == ctx.settings.trail_style
    assert persisted.field_style == ctx.settings.field_style
    assert persisted.hud_style == ctx.settings.hud_style
    assert all(item.label() != "Match music" for item in SettingsScreen(ctx).menu.items)
    settings = SettingsScreen(ctx)
    assert all(item.label() != "Canción de partida" for item in settings.menu.items)
    screen.draw(surface)
    assert len(screen.menu.items) == 9
    assert screen.menu.items[0].label() == "Player 1"
    assert screen.menu.items[0].value() == "Red Striped"


@pytest.mark.parametrize("seat", range(4))
def test_appearance_preview_draws_all_four_paddles(ctx: AppContext, seat: int) -> None:
    screen = AppearanceScreen(ctx)
    screen.menu.index = seat

    screen.draw(pygame.Surface((320, 180)))

    assert len(screen.preview_world.paddles) == 4


def test_appearance_menu_uses_standard_margin_and_balanced_previews(
    ctx: AppContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    screen = AppearanceScreen(ctx)
    menu_layout: list[tuple[int, int, int]] = []
    monkeypatch.setattr(
        screen.menu,
        "draw",
        lambda _surface, x, y, width, **_kwargs: menu_layout.append((x, y, width)),
    )
    surface = pygame.Surface((320, 180))

    screen.draw(surface)

    assert menu_layout == [(40, 40, screens_module.APPEARANCE_MENU_W)]
    player_frame = pygame.Rect(*screens_module.PLAYER_PREVIEW_BOX)
    style_frame = pygame.Rect(*screens_module.STYLE_PREVIEW_BOX)
    assert surface.get_at(player_frame.topleft)[:3] == pal.UI_MUTED
    assert surface.get_at(style_frame.topleft)[:3] == pal.UI_MUTED
    assert player_frame.bottom < style_frame.top
    assert style_frame.right == 312


def test_appearance_style_preview_renders_every_field_style(ctx: AppContext) -> None:
    screen = AppearanceScreen(ctx)
    screen.menu.index = 7
    surface = pygame.Surface((320, 180))
    frames: set[bytes] = set()

    screen.preview_renderer.draw_preview = lambda _world: pytest.fail(
        "field-style icons must not render the game scene"
    )
    for field_style in FIELD_STYLES:
        ctx.settings.field_style = field_style
        screen.draw(surface)
        frames.add(
            pygame.image.tobytes(
                surface.subsurface(pygame.Rect(*screens_module.STYLE_PREVIEW_BOX)), "RGB"
            )
        )

    assert len(frames) == len(FIELD_STYLES)


def test_target_field_icon_has_distinctive_crosshair(ctx: AppContext) -> None:
    screen = AppearanceScreen(ctx)
    screen.menu.index = 7
    ctx.settings.field_style = "target"
    screen.preview_renderer.draw_preview = lambda _world: pytest.fail(
        "field-style icons must not render the game scene"
    )
    surface = pygame.Surface((320, 180))

    screen.draw(surface)

    icon = surface.subsurface(pygame.Rect(*screens_module.STYLE_PREVIEW_BOX))
    assert any(icon.get_at((x, 22))[:3] == pal.PINK for x in range(icon.get_width()))
    assert any(icon.get_at((30, y))[:3] == pal.PINK for y in range(icon.get_height()))


def test_target_field_pattern_draws_crosshair_over_rings(monkeypatch: pytest.MonkeyPatch) -> None:
    renderer = Renderer()
    paths: list[list[tuple[int, int]]] = []
    draw_lines = pygame.draw.lines

    def capture_lines(
        surface: pygame.Surface,
        color: tuple[int, int, int],
        closed: bool,
        points: list[tuple[int, int]],
        width: int = 1,
    ) -> pygame.Rect:
        if color == pal.PINK and len(points) == 2:
            paths.append(points)
        return draw_lines(surface, color, closed, points, width)

    monkeypatch.setattr(pygame.draw, "lines", capture_lines)

    renderer._draw_field_pattern("target")

    expected_paths = {
        tuple(
            (round(point.sx), round(point.sy))
            for point in (
                renderer.camera.project(c.FIELD_WIDTH / 2, 0, 0),
                renderer.camera.project(c.FIELD_WIDTH / 2, c.FIELD_HEIGHT, 0),
            )
        ),
        tuple(
            (round(point.sx), round(point.sy))
            for point in (
                renderer.camera.project(0, c.FIELD_HEIGHT / 2, 0),
                renderer.camera.project(c.FIELD_WIDTH, c.FIELD_HEIGHT / 2, 0),
            )
        ),
    }
    assert {tuple(path) for path in paths} == expected_paths


@pytest.mark.parametrize(
    ("style", "expected_paths", "expected_colors"),
    [
        ("boxes", 2, (pal.shade(pal.BLUE, 0.48), pal.PINK)),
        ("maze", 3, (pal.LAVENDER,)),
        ("circuit", 4, (pal.shade(pal.UI_CYAN, 0.48),)),
    ],
)
def test_field_patterns_match_their_design(
    monkeypatch: pytest.MonkeyPatch,
    style: str,
    expected_paths: int,
    expected_colors: tuple[tuple[int, int, int], ...],
) -> None:
    renderer = Renderer()
    paths: list[list[tuple[int, int]]] = []
    draw_lines = pygame.draw.lines

    def capture_lines(
        surface: pygame.Surface,
        color: tuple[int, int, int],
        closed: bool,
        points: list[tuple[int, int]],
        width: int = 1,
    ) -> pygame.Rect:
        if color in expected_colors and len(points) >= 4:
            paths.append(points)
        return draw_lines(surface, color, closed, points, width)

    monkeypatch.setattr(pygame.draw, "lines", capture_lines)

    renderer._draw_field_pattern(style)

    assert len(paths) == expected_paths


def test_stars_field_pattern_draws_star_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    renderer = Renderer()
    star_vertices: list[int] = []
    draw_polygon = pygame.draw.polygon

    def capture_polygon(
        surface: pygame.Surface,
        color: tuple[int, int, int],
        points: list[tuple[int, int]],
        width: int = 0,
    ) -> pygame.Rect:
        if color == pal.YELLOW:
            star_vertices.append(len(points))
        return draw_polygon(surface, color, points, width)

    monkeypatch.setattr(pygame.draw, "polygon", capture_polygon)

    renderer._draw_field_pattern("stars")

    assert star_vertices
    assert all(vertices == 10 for vertices in star_vertices)


def test_appearance_preview_renders_every_hud_style(ctx: AppContext) -> None:
    screen = AppearanceScreen(ctx)
    screen.menu.index = 8
    surface = pygame.Surface((320, 180))
    frames: set[bytes] = set()

    for hud_style in HUD_STYLES:
        ctx.settings.hud_style = hud_style
        screen.draw(surface)
        frames.add(
            pygame.image.tobytes(
                surface.subsurface(pygame.Rect(*screens_module.STYLE_PREVIEW_BOX)), "RGB"
            )
        )

    assert len(frames) == len(HUD_STYLES)


def test_live_appearance_preview_distinguishes_every_option(ctx: AppContext) -> None:
    screen = AppearanceScreen(ctx)
    surface = pygame.Surface((320, 180))
    screen.menu.index = 0
    ctx.settings.paddle_skins = [0, 0, 0, 0]
    skin_frames: set[bytes] = set()
    for skin in range(PADDLE_SKIN_COUNT):
        ctx.settings.paddle_skins = [skin] * 4
        screen.draw(surface)
        skin_frames.add(
            pygame.image.tobytes(
                surface.subsurface(pygame.Rect(*screens_module.STYLE_PREVIEW_BOX)), "RGB"
            )
        )
    assert len(skin_frames) == PADDLE_SKIN_COUNT

    color_frames: set[bytes] = set()
    for color in range(PADDLE_COLOR_COUNT):
        ctx.settings.paddle_colors = [color] * 4
        screen.draw(surface)
        color_frames.add(
            pygame.image.tobytes(
                surface.subsurface(pygame.Rect(*screens_module.PLAYER_PREVIEW_BOX)), "RGB"
            )
        )
    assert len(color_frames) == PADDLE_COLOR_COUNT

    for menu_index, setting, choices, expected in (
        (4, "background", BACKGROUNDS, len(BACKGROUNDS) - 1),
        (5, "ball_style", BALL_STYLES, len(BALL_STYLES)),
        (6, "trail_style", TRAIL_STYLES, len(TRAIL_STYLES)),
        (7, "field_style", FIELD_STYLES, len(FIELD_STYLES)),
        (8, "hud_style", HUD_STYLES, len(HUD_STYLES)),
    ):
        screen.menu.index = menu_index
        frames = set()
        for choice in choices:
            setattr(ctx.settings, setting, choice)
            screen.draw(surface)
            frames.add(
                pygame.image.tobytes(
                    surface.subsurface(pygame.Rect(*screens_module.STYLE_PREVIEW_BOX)), "RGB"
                )
            )
        assert len(frames) == expected, setting


def test_player_paddle_preview_uses_a_consistent_view_for_all_seats(ctx: AppContext) -> None:
    screen = AppearanceScreen(ctx)
    surface = pygame.Surface((320, 180))
    ctx.settings.paddle_colors = [5] * 4
    ctx.settings.paddle_skins = [8] * 4
    previews: set[bytes] = set()

    for seat in range(4):
        screen.menu.index = seat
        screen.draw(surface)
        previews.add(
            pygame.image.tobytes(
                surface.subsurface(pygame.Rect(*screens_module.STYLE_PREVIEW_BOX)), "RGB"
            )
        )

    assert len(previews) == 1


def test_appearance_preview_renders_every_paddle_skin(ctx: AppContext) -> None:
    screen = AppearanceScreen(ctx)
    surface = pygame.Surface((320, 180))
    frames: set[bytes] = set()

    for skin in range(PADDLE_SKIN_COUNT):
        ctx.settings.paddle_skins = [skin] * 4
        screen.draw(surface)
        frames.add(pygame.image.tobytes(surface, "RGB"))

    assert len(frames) == PADDLE_SKIN_COUNT


def test_match_renderer_renders_every_paddle_skin() -> None:
    pygame.init()
    world = World(MatchConfig())
    frames: set[bytes] = set()

    for skin in range(PADDLE_SKIN_COUNT):
        renderer = Renderer(RenderSettings(paddle_skins=(skin,) * 4))
        frames.add(pygame.image.tobytes(renderer.draw(world), "RGB"))

    assert len(frames) == PADDLE_SKIN_COUNT


def test_all_appearance_choices_have_localized_names() -> None:
    for language in ("en", "es"):
        translate = Translator(language)
        keys = [
            *(f"color.{index}" for index in range(PADDLE_COLOR_COUNT)),
            *(f"skin.{index}" for index in range(PADDLE_SKIN_COUNT)),
            *(f"background.{style}" for style in BACKGROUNDS),
            *(f"ball_style.{style}" for style in BALL_STYLES),
            *(f"trail_style.{style}" for style in TRAIL_STYLES),
            *(f"field_style.{style}" for style in FIELD_STYLES),
            *(f"hud_style.{style}" for style in HUD_STYLES),
        ]
        assert all(translate(key) != key for key in keys)


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
def test_every_ball_trail_and_field_style_renders(setting: str, choices: tuple[str, ...]) -> None:
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


@pytest.mark.parametrize("style", FIELD_STYLES)
@pytest.mark.parametrize("arena", ("classic", "gravity"))
def test_field_patterns_stay_inside_the_projected_arena(style: str, arena: str) -> None:
    renderer = Renderer()
    world = World(MatchConfig(arena=arena))
    renderer.camera = renderer._camera_for(renderer.viewports(world)[0], world)
    renderer.surface.fill((1, 2, 3))
    renderer._draw_field_pattern(style)

    mask = pygame.Surface(renderer.surface.get_size(), pygame.SRCALPHA)
    boundary = (
        ((0.0, 0.0), (c.FIELD_WIDTH, 0.0)),
        ((c.FIELD_WIDTH, 0.0), (c.FIELD_WIDTH, c.FIELD_HEIGHT)),
        ((c.FIELD_WIDTH, c.FIELD_HEIGHT), (0.0, c.FIELD_HEIGHT)),
        ((0.0, c.FIELD_HEIGHT), (0.0, 0.0)),
    )
    boundary_points = [
        renderer.camera.project(
            start_x + (end_x - start_x) * step / 128,
            start_y + (end_y - start_y) * step / 128,
            0,
        )
        for (start_x, start_y), (end_x, end_y) in boundary
        for step in range(128)
    ]
    pygame.draw.polygon(
        mask,
        (255, 255, 255, 255),
        [(round(point.sx), round(point.sy)) for point in boundary_points],
    )
    for y in range(renderer.surface.get_height()):
        for x in range(renderer.surface.get_width()):
            if mask.get_at((x, y)).a == 0:
                assert renderer.surface.get_at((x, y))[:3] == (1, 2, 3), (arena, style)


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
