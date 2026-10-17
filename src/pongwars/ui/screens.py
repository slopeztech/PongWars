"""@package pongwars.ui.screens
@brief Concrete screens: title, menus, match setup, match, pause, results and settings.
"""

import math
import random
from dataclasses import replace

import pygame

from pongwars.ai import AIController, Observation
from pongwars.core.i18n import available_languages, load_catalog
from pongwars.core.loop import FixedStepLoop
from pongwars.core.settings import (
    BACKGROUNDS,
    BALL_STYLES,
    FIELD_STYLES,
    HUD_STYLES,
    PADDLE_COLOR_COUNT,
    PADDLE_SKIN_COUNT,
    SEATS,
    TRAIL_STYLES,
    Settings,
)
from pongwars.domain import constants as c
from pongwars.domain.arenas import ArenaSpec, arena_names, get_arena
from pongwars.domain.config import AI_DIFFICULTIES, MAX_PLAYERS, ConfigError, MatchConfig
from pongwars.domain.modes import MODES, OptionSpec
from pongwars.domain.world import Phase, World
from pongwars.input.controllers import (
    FIRE_KEYS,
    SPIN_KEYS,
    KeyBinding,
    KeyboardInput,
    KeyMap,
    PlayerInput,
    collect_inputs,
    poll_fire,
    poll_spin,
)
from pongwars.render import palette as pal
from pongwars.render.backgrounds import draw_background
from pongwars.render.font import draw_text, text_width
from pongwars.render.renderer import (
    BALL_LIFT,
    LOW_H,
    LOW_W,
    PADDLE_HEIGHT,
    Renderer,
    RenderSettings,
    ViewMode,
)
from pongwars.ui.appearance_preview import draw_field_style_icon
from pongwars.ui.core import AppContext, Screen
from pongwars.ui.widgets import Menu, MenuItem

MENU_X = 40
MENU_W = 240
MENU_Y = 40
TITLE_Y = 14
HINT_Y = LOW_H - 10
EXTRAS_CHOICES = ("off", "all", "power", "weapon", "penalty")
VIEWS = ("shared", "split")
CONTROLLER_CHOICES = ("human", "ai")
LAN_CONTROLLER_CHOICES = ("remote", "ai")
MAX_SEED = 2**31 - 1
BLINK_PERIOD = 1.0
PREVIEW_BOX = (190, 100, 120, 68)
APPEARANCE_MENU_W = 205
PLAYER_PREVIEW_BOX = (252, 40, 60, 46)
STYLE_PREVIEW_BOX = (252, 94, 60, 46)
VOLUME_STEP = 10
MAX_VOLUME = 100
MIN_SCALE = 2
MAX_SCALE = 8
OPTION_STEP_THRESHOLD = 50
ROOM_NAME_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_. ")


def _make_render_settings(
    settings: Settings, view: ViewMode = "shared", *, show_trail: bool | None = None
) -> RenderSettings:
    return RenderSettings(
        particles=settings.particles,
        trail=settings.trail if show_trail is None else show_trail,
        shake=settings.shake,
        scale=1,
        view=view,
        background=settings.background,
        ball_style=settings.ball_style,
        trail_style=settings.trail_style,
        field_style=settings.field_style,
        hud_style=settings.hud_style,
        paddle_colors=tuple(settings.paddle_colors),
        paddle_skins=tuple(settings.paddle_skins),
    )


def cycle(values: tuple[str, ...] | list[str], current: str, step: int) -> str:
    """@brief Pick the neighbour of a value in a circular list.
    @param values Ordered choices.
    @param current Current value.
    @param step +1 or -1.
    @return The next value.
    """
    index = values.index(current) if current in values else 0
    return values[(index + step) % len(values)]


def _centered(surface: pygame.Surface, text: str, y: int, color: pal.Color, scale: int = 1) -> None:
    draw_text(surface, text, (LOW_W - text_width(text, scale)) // 2, y, color, scale)


def _centered_title(surface: pygame.Surface, text: str, y: int) -> None:
    """@brief Draw a white pixel heading with cyan and orange offset accents."""
    x = (LOW_W - text_width(text, 2)) // 2
    draw_text(surface, text, x + 1, y + 1, pal.UI_ORANGE, 2)
    draw_text(surface, text, x - 1, y - 1, pal.UI_CYAN, 2)
    draw_text(surface, text, x, y, pal.WHITE, 2)


def _menu_backdrop(surface: pygame.Surface) -> None:
    """@brief Paint the shared midnight-blue pixel-art frame used by menu screens."""
    surface.fill(pal.UI_BACKGROUND)
    pygame.draw.line(surface, pal.UI_DARK, (2, 2), (LOW_W - 3, 2))
    for y in range(5, 17, 5):
        pygame.draw.rect(surface, pal.UI_MUTED, (LOW_W // 2 - 1, y, 2, 2))
    for y in range(151, 163, 5):
        pygame.draw.rect(surface, pal.UI_MUTED, (LOW_W // 2 - 1, y, 2, 2))
    pygame.draw.line(surface, pal.UI_MUTED, (16, 166), (110, 166))
    pygame.draw.line(surface, pal.UI_MUTED, (210, 166), (LOW_W - 16, 166))
    pygame.draw.rect(surface, pal.UI_CYAN, (8, 66, 7, 34))
    pygame.draw.rect(surface, pal.BLUE, (8, 66, 3, 34))
    pygame.draw.rect(surface, pal.UI_ORANGE, (LOW_W - 15, 66, 7, 34))
    pygame.draw.rect(surface, pal.YELLOW, (LOW_W - 15, 66, 3, 34))


def _title(ctx: AppContext, surface: pygame.Surface, key: str) -> None:
    _menu_backdrop(surface)
    _centered_title(surface, ctx.t(key), TITLE_Y)


def _overlay_panel(surface: pygame.Surface) -> None:
    """@brief Frame a menu overlay above the running match."""
    panel = pygame.Rect(70, 30, 180, 112)
    pygame.draw.rect(surface, pal.UI_BACKGROUND, panel)
    pygame.draw.rect(surface, pal.UI_CYAN, panel, 1)


def _hint(ctx: AppContext, surface: pygame.Surface) -> None:
    _centered(surface, ctx.t("menu.hint"), HINT_Y, pal.LIGHT_GREY)


class MenuScreen(Screen):
    """@brief Base of screens made of a single menu."""

    show_music_notice = True
    title_key = "app.title"

    def __init__(self, ctx: AppContext) -> None:
        """@brief Create the screen.
        @param ctx Application context.
        """
        super().__init__(ctx)
        self.menu = Menu()

    def handle_event(self, event: pygame.event.Event) -> None:
        """@brief Route keys to the menu; Esc goes back.
        @param event pygame event.
        """
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.back()
        elif self.menu.handle_key(event.key):
            self.ctx.audio.play("menu")

    def back(self) -> None:
        """@brief Leave the screen."""
        self.ctx.stack.pop()

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Draw title, menu and hint.
        @param surface Low-resolution target.
        """
        _title(self.ctx, surface, self.title_key)
        self.menu.draw(surface, MENU_X, MENU_Y, MENU_W)
        _hint(self.ctx, surface)


class TitleScreen(Screen):
    """@brief Splash screen with a blinking prompt."""

    def __init__(self, ctx: AppContext) -> None:
        """@brief Create the screen.
        @param ctx Application context.
        """
        super().__init__(ctx)
        self.clock = 0.0

    def update(self, dt: float) -> None:
        """@brief Advance the blink timer.
        @param dt Seconds elapsed.
        """
        self.clock += dt

    def handle_event(self, event: pygame.event.Event) -> None:
        """@brief Enter opens the main menu, Esc quits.
        @param event pygame event.
        """
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.ctx.stack.pop()
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.ctx.stack.push(MainMenuScreen(self.ctx))

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Draw the logo and prompt.
        @param surface Low-resolution target.
        """
        _menu_backdrop(surface)
        _centered(surface, self.ctx.t("app.title"), 50, pal.UI_ORANGE, 5)
        _centered(surface, self.ctx.t("app.title"), 48, pal.UI_CYAN, 5)
        _centered(surface, self.ctx.t("app.title"), 49, pal.WHITE, 5)
        if self.clock % BLINK_PERIOD < BLINK_PERIOD / 2:
            _centered(surface, self.ctx.t("menu.title.press_start"), 120, pal.WHITE, 1)


class MainMenuScreen(MenuScreen):
    """@brief Entry point of every game mode."""

    title_key = "app.title"

    def __init__(self, ctx: AppContext) -> None:
        """@brief Build the menu.
        @param ctx Application context.
        """
        super().__init__(ctx)
        t = ctx.t
        self.menu.set_items(
            [
                MenuItem(lambda: t("menu.main.vs"), on_activate=self.open_vs),
                MenuItem(lambda: t("menu.main.lan"), on_activate=self.open_lan),
                MenuItem(lambda: t("menu.main.help"), on_activate=self.open_help),
                MenuItem(lambda: t("menu.main.appearance"), on_activate=self.open_appearance),
                MenuItem(lambda: t("menu.main.settings"), on_activate=self.open_settings),
                MenuItem(lambda: t("menu.main.quit"), on_activate=ctx.stack.pop_all),
            ]
        )
        first = ctx.audio.start_music(
            "menu",
            avoid_previous=ctx.settings.last_menu_track,
        )
        if first:
            ctx.settings.last_menu_track = first
            ctx.settings.save()

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Draw the menu plus the song that is playing.
        @param surface Low-resolution target.
        """
        _menu_backdrop(surface)
        title = self.ctx.t("app.title")
        title_x = (LOW_W - text_width(title, 4)) // 2
        pygame.draw.line(surface, pal.UI_CYAN, (59, 32), (88, 32), 1)
        pygame.draw.line(surface, pal.UI_ORANGE, (LOW_W - 89, 32), (LOW_W - 60, 32), 1)
        _centered(surface, title, 27, pal.UI_ORANGE, 4)
        draw_text(surface, title, title_x - 1, 25, pal.UI_CYAN, 4)
        draw_text(surface, title, title_x, 26, pal.WHITE, 4)
        for y in range(48, 60, 5):
            pygame.draw.rect(surface, pal.UI_MUTED, (LOW_W // 2 - 1, y, 2, 2))
        self.menu.draw(surface, 126, 64, 68, centered=True, row_gap=14)
        _centered(surface, "slopeztech", 169, pal.UI_MUTED)

    def open_vs(self) -> None:
        """@brief Open a versus match using the last saved controller setup."""
        self.ctx.stack.push(SetupScreen(self.ctx))

    def open_lan(self) -> None:
        """@brief Open the LAN actions submenu."""
        self.ctx.stack.push(LanMenuScreen(self.ctx))

    def open_help(self) -> None:
        """@brief Open the help submenu."""
        self.ctx.stack.push(HelpMenuScreen(self.ctx))

    def open_lan_host(self) -> None:
        """@brief Open the LAN host setup."""
        self.ctx.stack.push(SetupScreen(self.ctx, ("human", "remote"), lan=True))

    def open_lan_join(self) -> None:
        """@brief Open the LAN join screen."""
        from pongwars.ui.lan import LanJoinScreen  # noqa: PLC0415

        self.ctx.stack.push(LanJoinScreen(self.ctx))

    def open_lan_help(self) -> None:
        """@brief Open the LAN help pages."""
        from pongwars.ui.lan import LanHelpScreen  # noqa: PLC0415

        self.ctx.stack.push(LanHelpScreen(self.ctx))

    def open_appearance(self) -> None:
        """@brief Open the appearance screen."""
        self.ctx.stack.push(AppearanceScreen(self.ctx))

    def open_howto(self) -> None:
        """@brief Open the how-to-play pages."""
        self.ctx.stack.push(HowToPlayScreen(self.ctx))

    def open(self, preset: tuple[str, str]) -> None:
        """@brief Open the match setup with a controller preset.
        @param preset Controllers for the first two seats.
        """
        self.ctx.stack.push(SetupScreen(self.ctx, preset))

    def open_settings(self) -> None:
        """@brief Open the settings screen."""
        self.ctx.stack.push(SettingsScreen(self.ctx))

    def back(self) -> None:
        """@brief Esc on the main menu returns to the title."""
        self.ctx.stack.pop()


class LanMenuScreen(MenuScreen):
    """@brief Submenu for LAN hosting and joining."""

    title_key = "menu.main.lan"

    def __init__(self, ctx: AppContext) -> None:
        super().__init__(ctx)
        self.menu.set_items(
            [
                MenuItem(lambda: ctx.t("menu.main.lan_host"), on_activate=self.open_host),
                MenuItem(lambda: ctx.t("menu.main.lan_join"), on_activate=self.open_join),
            ]
        )

    def open_host(self) -> None:
        self.ctx.stack.push(SetupScreen(self.ctx, ("human", "remote"), lan=True))

    def open_join(self) -> None:
        from pongwars.ui.lan import LanJoinScreen  # noqa: PLC0415

        self.ctx.stack.push(LanJoinScreen(self.ctx))


class HelpMenuScreen(MenuScreen):
    """@brief Submenu for game instructions and LAN help."""

    title_key = "menu.main.help"

    def __init__(self, ctx: AppContext) -> None:
        super().__init__(ctx)
        self.menu.set_items(
            [
                MenuItem(lambda: ctx.t("menu.main.howto"), on_activate=self.open_howto),
                MenuItem(lambda: ctx.t("menu.main.lan_help"), on_activate=self.open_lan_help),
            ]
        )

    def open_howto(self) -> None:
        self.ctx.stack.push(HowToPlayScreen(self.ctx))

    def open_lan_help(self) -> None:
        from pongwars.ui.lan import LanHelpScreen  # noqa: PLC0415

        self.ctx.stack.push(LanHelpScreen(self.ctx))


class SetupScreen(MenuScreen):
    """@brief Auto-generated match configuration form with an arena preview."""

    title_key = "setup.title"

    def __init__(
        self, ctx: AppContext, preset: tuple[str, ...] = ("human", "human"), lan: bool = False
    ) -> None:
        """@brief Build the form.
        @param ctx Application context.
        @param preset Controllers used for the first seats.
        @param lan True when hosting a LAN match (seat 1 is human, the rest remote or AI).
        """
        super().__init__(ctx)
        self.lan = lan
        self.mode = "classic"
        self.arena = "classic"
        self.preset = preset
        self.controllers: list[str] = []
        self.difficulty = "normal"
        self.extras = "off"
        self.view = ctx.settings.view
        self.room_name = ctx.settings.last_match.get(
            "room_name", f"{ctx.settings.player_name} GAME"
        )
        self.editing_room_name = False
        self.options: dict[str, float] = {}
        self._reset_options()
        self._restore_last_match()
        self._fit_controllers()
        self.rebuild()

    def _restore_last_match(self) -> None:
        saved = self.ctx.settings.last_match
        if saved.get("mode") in MODES.names():
            self.mode = str(saved["mode"])
            self._reset_options()
        if saved.get("arena") in arena_names():
            self.arena = str(saved["arena"])
        if saved.get("difficulty") in AI_DIFFICULTIES:
            self.difficulty = str(saved["difficulty"])
        if saved.get("extras") in EXTRAS_CHOICES:
            self.extras = str(saved["extras"])
        if saved.get("view") in VIEWS:
            self.view = str(saved["view"])
        if isinstance(saved.get("room_name"), str):
            self.room_name = saved["room_name"][:20]
        options = saved.get("options")
        if isinstance(options, dict):
            for spec in self._option_specs():
                value = options.get(spec.name)
                if isinstance(value, int | float) and not isinstance(value, bool):
                    self.options[spec.name] = float(min(spec.maximum, max(spec.minimum, value)))
        controllers = saved.get("controllers")
        if isinstance(controllers, list):
            valid = LAN_CONTROLLER_CHOICES if self.lan else CONTROLLER_CHOICES
            self.controllers = [
                value if value in valid else self.preset[i % len(self.preset)]
                for i, value in enumerate(controllers[:MAX_PLAYERS])
            ]

    @property
    def spec(self) -> ArenaSpec:
        """@brief Selected arena.
        @return Its specification.
        """
        return get_arena(self.arena)

    def _option_specs(self) -> tuple[OptionSpec, ...]:
        return tuple(MODES.get(self.mode).options)

    def _reset_options(self) -> None:
        self.options = {o.name: float(o.default) for o in self._option_specs()}

    def _fit_controllers(self) -> None:
        count = self.spec.players
        fitted = [
            self.controllers[i]
            if i < len(self.controllers)
            else ("remote" if self.lan and i else self.preset[i % len(self.preset)])
            for i in range(count)
        ]
        self.controllers = fitted

    def _set_mode(self, step: int) -> None:
        self.mode = cycle(MODES.names(), self.mode, step)
        self._reset_options()
        self.rebuild()

    def _set_arena(self, step: int) -> None:
        self.arena = cycle(arena_names(), self.arena, step)
        self._fit_controllers()
        self.rebuild()

    def _set_controller(self, seat: int, step: int) -> None:
        if self.lan:
            if seat == 0:
                return
            self.controllers[seat] = cycle(LAN_CONTROLLER_CHOICES, self.controllers[seat], step)
        else:
            self.controllers[seat] = cycle(CONTROLLER_CHOICES, self.controllers[seat], step)
        self.rebuild()

    def _adjust_option(self, spec: OptionSpec, step: int) -> None:
        if spec.kind == "bool":
            self.options[spec.name] = 0.0 if self.options[spec.name] else 1.0
            return
        span = spec.maximum - spec.minimum
        size = 10 if span > OPTION_STEP_THRESHOLD else 1
        value = self.options[spec.name] + step * size
        self.options[spec.name] = float(min(spec.maximum, max(spec.minimum, value)))

    def _option_text(self, spec: OptionSpec) -> str:
        value = self.options[spec.name]
        if spec.kind == "bool":
            return self.ctx.t("option.on" if value else "option.off")
        return str(int(value))

    def rebuild(self) -> None:
        """@brief Recreate the rows after a structural change (mode or arena)."""
        t = self.ctx.t
        items = [
            MenuItem(
                lambda: t("setup.mode"),
                lambda: t(f"mode.{self.mode}.name"),
                on_adjust=self._set_mode,
            ),
            MenuItem(
                lambda: t("setup.arena"),
                lambda: t(f"arena.{self.arena}.name"),
                on_adjust=self._set_arena,
            ),
        ]
        for seat in range(len(self.controllers)):
            items.append(
                MenuItem(
                    lambda seat=seat: t("setup.seat", number=seat + 1),  # type: ignore[misc]
                    lambda seat=seat: t(f"controller.{self.controllers[seat]}"),  # type: ignore[misc]
                    on_adjust=lambda step, seat=seat: self._set_controller(seat, step),  # type: ignore[misc]
                )
            )
        items.append(
            MenuItem(
                lambda: t("setup.difficulty"),
                lambda: t(f"difficulty.{self.difficulty}"),
                on_adjust=lambda s: setattr(
                    self, "difficulty", cycle(AI_DIFFICULTIES, self.difficulty, s)
                ),
                enabled="ai" in self.controllers,
            )
        )
        items.append(
            MenuItem(
                lambda: t("setup.extras"),
                lambda: t(f"extras.choice.{self.extras}"),
                on_adjust=lambda s: setattr(self, "extras", cycle(EXTRAS_CHOICES, self.extras, s)),
            )
        )
        items.append(
            MenuItem(
                lambda: t("setup.view"),
                lambda: t(f"view.{self.view}"),
                on_adjust=lambda s: setattr(self, "view", cycle(VIEWS, self.view, s)),
            )
        )
        if self.lan:
            items.append(
                MenuItem(
                    lambda: t("setup.room_name"),
                    lambda: self.room_name + ("_" if self.editing_room_name else ""),
                    on_activate=lambda: setattr(self, "editing_room_name", True),
                )
            )
        for spec in self._option_specs():
            items.append(
                MenuItem(
                    lambda spec=spec: t(f"mode.{self.mode}.option.{spec.name}"),  # type: ignore[misc]
                    lambda spec=spec: self._option_text(spec),  # type: ignore[misc]
                    on_adjust=lambda s, spec=spec: self._adjust_option(spec, s),  # type: ignore[misc]
                )
            )
        items.append(MenuItem(lambda: t("setup.start"), on_activate=self.start))
        self.menu.set_items(items)

    def build_config(self, seed: int | None = None) -> MatchConfig:
        """@brief Turn the form into a validated configuration.
        @param seed Fixed seed, random when omitted.
        @return The match configuration.
        @throws ConfigError If the selection is invalid.
        """
        return MatchConfig(
            mode=self.mode,
            arena=self.arena,
            options=tuple(self.options.items()),
            controllers=tuple(self.controllers),
            ai_difficulty=self.difficulty,
            extras=() if self.extras == "off" else (self.extras,),
            seed=random.randrange(MAX_SEED) if seed is None else seed,  # noqa: S311
        )

    def _save_last_match(self) -> None:
        settings = self.ctx.settings
        settings.last_match = {
            "mode": self.mode,
            "arena": self.arena,
            "controllers": list(self.controllers),
            "difficulty": self.difficulty,
            "extras": self.extras,
            "view": self.view,
            "options": self.options.copy(),
            "room_name": self.room_name,
        }
        settings.save()

    def start(self) -> None:
        """@brief Launch the match."""
        try:
            config = self.build_config()
        except ConfigError:
            return
        self._save_last_match()
        if self.lan:
            from pongwars.ui.lan import LanLobbyScreen  # noqa: PLC0415

            self.ctx.stack.push(
                LanLobbyScreen(self.ctx, config, self.view, room_name=self.room_name)
            )
            return
        self.ctx.stack.push(MatchScreen(self.ctx, config, self.view))

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.editing_room_name and event.type == pygame.KEYDOWN:
            self._edit_room_name(event)
            return
        super().handle_event(event)

    def _edit_room_name(self, event: pygame.event.Event) -> None:
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
            self.editing_room_name = False
        elif event.key == pygame.K_BACKSPACE:
            self.room_name = self.room_name[:-1]
        else:
            char = event.unicode.upper()
            if char in ROOM_NAME_CHARS and len(self.room_name) < 20:
                self.room_name += char

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Draw the form and the arena preview.
        @param surface Low-resolution target.
        """
        _title(self.ctx, surface, self.title_key)
        self.menu.draw(surface, 24, 30, 150)
        draw_arena_preview(surface, self.spec, pygame.Rect(*PREVIEW_BOX))
        _hint(self.ctx, surface)


def draw_arena_preview(surface: pygame.Surface, spec: ArenaSpec, box: pygame.Rect) -> None:
    """@brief Draw a top-down sketch of an arena.
    @param surface Target surface.
    @param spec Arena to sketch.
    @param box Destination rectangle.
    """
    pygame.draw.rect(surface, pal.DARK_GREY, box)
    pygame.draw.rect(surface, pal.LIGHT_GREY, box, 1)
    sx = box.width / c.FIELD_WIDTH
    sy = box.height / c.FIELD_HEIGHT
    for ob in spec.obstacles:
        w = max(2, int(ob.half_w * 2 * sx))
        h = max(2, int(ob.half_h * 2 * sy))
        cx = box.x + int(ob.x * sx)
        cy = box.y + int(ob.y * sy)
        color = pal.ORANGE if ob.kind == "bumper" else pal.LAVENDER
        pygame.draw.rect(surface, color, pygame.Rect(cx - w // 2, cy - h // 2, w, h))
    for seat in range(spec.players):
        pygame.draw.circle(
            surface, pal.PLAYER_COLORS[seat % len(pal.PLAYER_COLORS)], box.center, 2 + seat
        )


class MatchScreen(Screen):
    """@brief Runs a match: simulation, input, rendering and audio."""

    def __init__(self, ctx: AppContext, config: MatchConfig, view: str | None = None) -> None:
        """@brief Create the match.
        @param ctx Application context.
        @param config Match configuration.
        @param view Camera mode override ("shared" or "split").
        """
        super().__init__(ctx)
        s = ctx.settings
        self.config = config
        self.view = view or s.view
        self.world = World(config)
        render_settings = _make_render_settings(s, "split" if self.view == "split" else "shared")
        self.renderer = Renderer(render_settings, config.seed, ctx.translator)
        self.humans = [config.controllers[i] == "human" for i in range(self.world.players)]
        self.controllers = [self._controller(i) for i in range(self.world.players)]
        self._fire_taps = [False] * self.world.players
        self._spin_taps = [False] * self.world.players
        self.loop = FixedStepLoop(self._step, c.DT)
        self.paused = False
        ctx.audio.start_music("match")

    def _controller(self, seat: int) -> PlayerInput:
        config, world = self.config, self.world
        if config.controllers[seat] == "ai":
            return AIController(
                lambda: Observation.from_world(world, seat),
                config.ai_difficulty,
                config.ai_strategy,
                config.seed + seat,
            )
        return KeyboardInput(self.ctx.keymap.get(seat), pygame.key.get_pressed)

    def _step(self) -> None:
        held = poll_fire(self.humans, pygame.key.get_pressed)
        fire = tuple(
            h or (p and human)
            for h, p, human in zip(held, self._fire_taps, self.humans, strict=False)
        )
        self._fire_taps = [False] * len(self._fire_taps)
        spinning = poll_spin(self.humans, pygame.key.get_pressed)
        spin = tuple(
            down or (tap and human)
            for down, tap, human in zip(spinning, self._spin_taps, self.humans, strict=False)
        )
        self._spin_taps = [False] * len(self._spin_taps)
        events = self.world.step(collect_inputs(self.controllers, fire, spin))
        self.renderer.handle_events(self.world, events)
        self.ctx.audio.handle_events(events)

    def handle_event(self, event: pygame.event.Event) -> None:
        """@brief Esc opens the pause menu.
        @param event pygame event.
        """
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.ctx.stack.push(PauseScreen(self.ctx))
        elif event.type == pygame.KEYDOWN and event.key in FIRE_KEYS:
            seat = FIRE_KEYS.index(event.key)
            if seat < len(self._fire_taps):
                self._fire_taps[seat] = True
        elif event.type == pygame.KEYDOWN and event.key in SPIN_KEYS:
            seat = SPIN_KEYS.index(event.key)
            if seat < len(self._spin_taps) and self.humans[seat]:
                self._spin_taps[seat] = True

    def update(self, dt: float) -> None:
        """@brief Advance the simulation unless a overlay is on top.
        @param dt Seconds elapsed.
        """
        if self.ctx.stack.top is not self:
            return
        self.loop.advance(dt)
        self.renderer.update(self.world, dt)
        if self.world.phase is Phase.FINISHED:
            self.ctx.audio.start_music("menu")
            self.ctx.stack.replace(ResultsScreen(self.ctx, self.config, self.world, self.view))

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Render the world.
        @param surface Low-resolution target.
        """
        self.renderer.present(self.world, surface)


class PauseScreen(MenuScreen):
    """@brief Overlay shown over a running match."""

    transparent = True
    title_key = "pause.title"

    def __init__(self, ctx: AppContext) -> None:
        """@brief Build the menu.
        @param ctx Application context.
        """
        super().__init__(ctx)
        t = ctx.t
        self.menu.set_items(
            [
                MenuItem(lambda: t("pause.resume"), on_activate=ctx.stack.pop),
                MenuItem(lambda: t("pause.settings"), on_activate=self._settings),
                MenuItem(lambda: t("pause.quit"), on_activate=self._quit),
            ]
        )

    def _settings(self) -> None:
        self.ctx.stack.push(SettingsScreen(self.ctx))

    def _quit(self) -> None:
        self.ctx.audio.start_music("menu")
        self.ctx.stack.pop_to(MainMenuScreen)

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Dim the match and draw the menu.
        @param surface Low-resolution target.
        """
        shade = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        surface.blit(shade, (0, 0))
        _overlay_panel(surface)
        _centered_title(surface, self.ctx.t(self.title_key), 40)
        self.menu.draw(surface, 100, 80, 120)


class ResultsScreen(MenuScreen):
    """@brief End-of-match summary with follow-up actions."""

    title_key = "results.title"

    def __init__(
        self, ctx: AppContext, config: MatchConfig, world: World, view: str, lan: bool = False
    ) -> None:
        """@brief Build the screen.
        @param ctx Application context.
        @param config Configuration that was played.
        @param world Finished world.
        @param view Camera mode used.
        @param lan True for a network match (only "back to menu" is offered).
        """
        super().__init__(ctx)
        self.config = config
        self.world = world
        self.view = view
        t = ctx.t
        rows = [
            MenuItem(lambda: t("results.rematch"), on_activate=self.rematch),
            MenuItem(lambda: t("results.setup"), on_activate=self._to_setup),
            MenuItem(lambda: t("results.menu"), on_activate=self._to_menu),
        ]
        self.menu.set_items(rows[2:] if lan else rows)
        self.lan = lan

    def headline(self) -> str:
        """@brief Winner message.
        @return Localised winner (or draw) text.
        """
        winner = self.world.winner
        if winner is None:
            return self.ctx.t("results.draw")
        player = self.ctx.t("hud.player", number=winner + 1)
        return self.ctx.t("match.score.winner", player=player)

    def rematch(self) -> None:
        """@brief Replay with a fresh seed."""
        config = replace(self.config, seed=self.config.seed + 1)
        self.ctx.stack.replace(MatchScreen(self.ctx, config, self.view))

    def _to_setup(self) -> None:
        self.ctx.stack.pop()

    def _to_menu(self) -> None:
        self.ctx.stack.pop_to(MainMenuScreen)

    def back(self) -> None:
        """@brief Esc returns to the setup form (or the menu for a network match)."""
        if self.lan:
            self._to_menu()
        else:
            self._to_setup()

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Draw winner, scores and actions.
        @param surface Low-resolution target.
        """
        _title(self.ctx, surface, self.title_key)
        _centered(surface, self.headline(), 36, pal.YELLOW, 2)
        for seat, score in enumerate(self.world.scores):
            label = self.ctx.t("hud.player", number=seat + 1)
            color = pal.PLAYER_COLORS[seat % len(pal.PLAYER_COLORS)]
            _centered(surface, f"{label}  {score}", 58 + seat * 9, color)
        self.menu.draw(surface, 100, 110, 120)


class SettingsScreen(MenuScreen):
    """@brief Entry point for the settings submenus."""

    title_key = "settings.title"

    def __init__(self, ctx: AppContext) -> None:
        """@brief Build links to each settings category.
        @param ctx Shared application context.
        """
        super().__init__(ctx)
        self.menu.set_items(
            [
                MenuItem(
                    lambda: ctx.t("settings.graphics"),
                    on_activate=lambda: self._open_category("graphics"),
                ),
                MenuItem(
                    lambda: ctx.t("settings.audio"),
                    on_activate=lambda: self._open_category("audio"),
                ),
                MenuItem(
                    lambda: ctx.t("settings.gameplay"),
                    on_activate=lambda: self._open_category("gameplay"),
                ),
                MenuItem(
                    lambda: ctx.t("settings.controls"),
                    on_activate=lambda: self._open_category("controls"),
                ),
            ]
        )

    def _open_category(self, category: str) -> None:
        self.ctx.stack.push(SettingsCategoryScreen(self.ctx, category))


class SettingsCategoryScreen(MenuScreen):
    """@brief Configure one settings category; each change is applied and saved."""

    def __init__(self, ctx: AppContext, category: str) -> None:
        """@brief Build one category of settings.
        @param ctx Shared application context.
        @param category Category key: graphics, audio, gameplay or controls.
        """
        super().__init__(ctx)
        if category not in ("graphics", "audio", "gameplay", "controls"):
            raise ValueError(f"Unknown settings category: {category}")
        self.category = category
        self.title_key = f"settings.{category}.title"
        self.capturing: int | None = None
        self.captured: list[int] = []
        self.error = ""
        self.rebuild()

    def _volume(self, attr: str, step: int) -> None:
        value = getattr(self.ctx.settings, attr) + step * VOLUME_STEP
        setattr(self.ctx.settings, attr, min(MAX_VOLUME, max(0, value)))
        self.commit()

    def _toggle(self, attr: str) -> None:
        setattr(self.ctx.settings, attr, not getattr(self.ctx.settings, attr))
        self.commit()

    def _scale(self, step: int) -> None:
        s = self.ctx.settings
        s.scale = min(MAX_SCALE, max(MIN_SCALE, s.scale + step))
        self.commit()

    def _display(self, step: int) -> None:
        s = self.ctx.settings
        count = max(1, pygame.display.get_num_displays())
        s.display_index = (s.display_index + step) % count
        self.commit()

    def _display_text(self) -> str:
        s = self.ctx.settings
        sizes = pygame.display.get_desktop_sizes()
        count = max(1, pygame.display.get_num_displays())
        index = min(s.display_index, count - 1)
        width, height = sizes[index] if index < len(sizes) else (0, 0)
        return self.ctx.t(
            "settings.display.value",
            number=index + 1,
            width=width,
            height=height,
        )

    def _language(self, step: int) -> None:
        s = self.ctx.settings
        s.language = cycle(available_languages(), s.language, step)
        self.commit()

    def _view(self, step: int) -> None:
        s = self.ctx.settings
        s.view = cycle(VIEWS, s.view, step)
        self.commit()

    def commit(self) -> None:
        """@brief Apply and persist the settings, then refresh the labels."""
        self.ctx.apply_settings()
        self.ctx.settings.save()

    def _onoff(self, attr: str) -> str:
        return self.ctx.t("option.on" if getattr(self.ctx.settings, attr) else "option.off")

    def rebuild(self) -> None:
        """@brief Create the rows belonging to this category."""
        t, s = self.ctx.t, self.ctx.settings
        if self.category == "audio":
            items = [
                MenuItem(
                    lambda: t("settings.master"),
                    lambda: str(s.master_volume),
                    on_adjust=lambda d: self._volume("master_volume", d),
                ),
                MenuItem(
                    lambda: t("settings.music"),
                    lambda: str(s.music_volume),
                    on_adjust=lambda d: self._volume("music_volume", d),
                ),
                MenuItem(
                    lambda: t("settings.sfx"),
                    lambda: str(s.sfx_volume),
                    on_adjust=lambda d: self._volume("sfx_volume", d),
                ),
            ]
        elif self.category == "graphics":
            items = [
                MenuItem(
                    lambda: t("settings.fullscreen"),
                    lambda: self._onoff("fullscreen"),
                    on_adjust=lambda _d: self._toggle("fullscreen"),
                ),
                MenuItem(
                    lambda: t("settings.display"),
                    self._display_text,
                    on_adjust=self._display,
                ),
                MenuItem(
                    lambda: t("settings.scale"),
                    lambda: f"x{s.scale}",
                    on_adjust=self._scale,
                ),
            ]
        elif self.category == "gameplay":
            items = [
                MenuItem(
                    lambda: t("settings.language"),
                    lambda: load_catalog(s.language).get("language.name", s.language),
                    on_adjust=self._language,
                ),
                MenuItem(
                    lambda: t("settings.particles"),
                    lambda: self._onoff("particles"),
                    on_adjust=lambda _d: self._toggle("particles"),
                ),
                MenuItem(
                    lambda: t("settings.trail"),
                    lambda: self._onoff("trail"),
                    on_adjust=lambda _d: self._toggle("trail"),
                ),
                MenuItem(
                    lambda: t("settings.shake"),
                    lambda: self._onoff("shake"),
                    on_adjust=lambda _d: self._toggle("shake"),
                ),
                MenuItem(
                    lambda: t("settings.view"),
                    lambda: t(f"view.{s.view}"),
                    on_adjust=self._view,
                ),
            ]
        else:
            items = [
                MenuItem(
                    lambda seat=seat: t("settings.keys", number=seat + 1),  # type: ignore[misc]
                    lambda seat=seat: self._key_names(seat),  # type: ignore[misc]
                    on_activate=lambda seat=seat: self.begin_capture(seat),  # type: ignore[misc]
                )
                for seat in range(MAX_PLAYERS)
            ]
        self.menu.set_items(items)

    def _key_names(self, seat: int) -> str:
        if self.capturing == seat:
            return "?"
        binding = self.ctx.keymap.get(seat)
        return " ".join(
            pygame.key.name(k).upper().replace(" ", "_")
            for k in (binding.negative, binding.positive)
        )

    def begin_capture(self, seat: int) -> None:
        """@brief Start listening for two key presses to rebind a seat.
        @param seat Seat to rebind.
        """
        self.capturing = seat
        self.captured = []
        self.error = ""

    def handle_event(self, event: pygame.event.Event) -> None:
        """@brief Capture keys when rebinding, otherwise behave as a menu.
        @param event pygame event.
        """
        if self.capturing is None or event.type != pygame.KEYDOWN:
            super().handle_event(event)
            return
        if event.key == pygame.K_ESCAPE:
            self.capturing = None
            return
        self.captured.append(event.key)
        if len(self.captured) == 2:
            seat, (neg, pos) = self.capturing, self.captured
            self.capturing = None
            try:
                self.ctx.keymap.rebind(seat, KeyBinding(neg, pos))
            except ValueError as exc:
                self.error = str(exc)
                return
            self.ctx.settings.keys = self.ctx.keymap.to_dict()
            self.ctx.settings.save()

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Draw the menu and capture/error hints."""
        _title(self.ctx, surface, self.title_key)
        self.menu.draw(surface, MENU_X, MENU_Y, MENU_W)
        if self.capturing is not None:
            _centered(surface, self.ctx.t("settings.press_keys"), HINT_Y - 10, pal.YELLOW)
        elif self.error:
            _centered(surface, self.ctx.t(self.error), HINT_Y - 10, pal.RED)
        _hint(self.ctx, surface)


class AppearanceScreen(MenuScreen):
    """@brief Configure player looks, ball and trail models, and arena styles."""

    title_key = "appearance.title"

    def __init__(self, ctx: AppContext) -> None:
        """@brief Build the rows.
        @param ctx Application context.
        """
        super().__init__(ctx)
        t, s = ctx.t, ctx.settings
        self._preview_tick = 0
        self.preview_world = World(
            MatchConfig(
                arena="crossfire",
                controllers=("human",) * SEATS,
                seed=0,
            )
        )
        self.preview_hud_world = World(
            MatchConfig(arena="crossfire", controllers=("human",) * SEATS, seed=1)
        )
        for seat, effect in enumerate(("shield", "slow_paddle", "drunk", "inverted")):
            self.preview_hud_world.extras.apply_direct(effect, seat, [])
        self.preview_hud_world.extras.weapons[3] = ("laser", 2)
        self.preview_renderer = Renderer(_make_render_settings(s, show_trail=True), seed=0)
        ball_position = self.preview_world.ball.pos
        for offset in range(12, 0, -1):
            self.preview_renderer.trail.push(
                ball_position.x - offset * 1.4,
                ball_position.y - offset * 0.7,
            )
        items: list[MenuItem] = []
        for seat in range(SEATS):

            def player_label(seat_number: int = seat) -> str:
                return t("appearance.player", number=seat_number + 1)

            def player_value(seat_number: int = seat) -> str:
                return (
                    f"{t(f'color.{s.paddle_colors[seat_number]}')} "
                    f"{t(f'skin.{s.paddle_skins[seat_number]}')}"
                )

            items.append(
                MenuItem(
                    player_label,
                    player_value,
                    on_activate=lambda seat=seat: self._step_seat(  # type: ignore[misc]
                        s.paddle_skins, seat, 1, PADDLE_SKIN_COUNT
                    ),
                    on_adjust=lambda d, seat=seat: self._step_seat(  # type: ignore[misc]
                        s.paddle_colors, seat, d, PADDLE_COLOR_COUNT
                    ),
                )
            )
        items.append(
            MenuItem(
                lambda: t("appearance.background"),
                lambda: t(f"background.{s.background}"),
                on_adjust=self._background,
            )
        )
        items.extend(
            (
                MenuItem(
                    lambda: t("appearance.ball"),
                    lambda: t(f"ball_style.{s.ball_style}"),
                    on_adjust=self._ball_style,
                ),
                MenuItem(
                    lambda: t("appearance.trail_style"),
                    lambda: t(f"trail_style.{s.trail_style}"),
                    on_adjust=self._trail_style,
                ),
                MenuItem(
                    lambda: t("appearance.field_style"),
                    lambda: t(f"field_style.{s.field_style}"),
                    on_adjust=self._field_style,
                ),
                MenuItem(
                    lambda: t("appearance.hud_style"),
                    lambda: t(f"hud_style.{s.hud_style}"),
                    on_adjust=self._hud_style,
                ),
            )
        )
        self.menu.set_items(items)

    def _step_seat(self, values: list[int], seat: int, step: int, count: int) -> None:
        values[seat] = (values[seat] + step) % count
        self.ctx.settings.save()

    def _background(self, step: int) -> None:
        s = self.ctx.settings
        s.background = cycle(BACKGROUNDS, s.background, step)
        s.save()

    def _ball_style(self, step: int) -> None:
        s = self.ctx.settings
        s.ball_style = cycle(BALL_STYLES, s.ball_style, step)
        s.save()

    def _trail_style(self, step: int) -> None:
        s = self.ctx.settings
        s.trail_style = cycle(TRAIL_STYLES, s.trail_style, step)
        s.save()

    def _field_style(self, step: int) -> None:
        s = self.ctx.settings
        s.field_style = cycle(FIELD_STYLES, s.field_style, step)
        s.save()

    def _hud_style(self, step: int) -> None:
        s = self.ctx.settings
        s.hud_style = cycle(HUD_STYLES, s.hud_style, step)
        s.save()

    def update(self, dt: float) -> None:
        """Advance the live preview's animation clocks."""
        self._preview_tick += 1
        self.preview_renderer.set_settings(
            _make_render_settings(self.ctx.settings, show_trail=True)
        )
        self.preview_renderer.update(self.preview_world, dt)
        self.preview_world.ball.rotation = (
            self.preview_world.ball.rotation + max(0.0, dt) * 2.0
        ) % math.tau

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Draw the rows and live player, ball and field previews.
        @param surface Low-resolution target.
        """
        selected = self.menu.index
        preview_settings = _make_render_settings(self.ctx.settings, show_trail=True)
        if selected < SEATS:
            color = self.ctx.settings.paddle_colors[selected]
            skin = self.ctx.settings.paddle_skins[selected]
            preview_settings = replace(
                preview_settings,
                paddle_colors=(color,) * SEATS,
                paddle_skins=(skin,) * SEATS,
            )
        self.preview_renderer.set_settings(preview_settings)
        preview = (
            None
            if selected == SEATS + 3
            else self.preview_renderer.draw_hud_preview(self.preview_hud_world)
            if selected == SEATS + 4
            else self.preview_renderer.draw_preview(self.preview_world)
        )
        _title(self.ctx, surface, self.title_key)
        self.menu.draw(surface, MENU_X, MENU_Y, APPEARANCE_MENU_W)
        self._draw_player_preview(surface)
        self._draw_style_preview(surface, preview)
        _centered(surface, self.ctx.t("appearance.hint"), HINT_Y, pal.LIGHT_GREY)

    def _draw_player_preview(self, surface: pygame.Surface) -> None:
        settings = self.ctx.settings
        rect = pygame.Rect(*PLAYER_PREVIEW_BOX)
        pygame.draw.rect(surface, pal.NAVY, rect)
        for seat, color_index in enumerate(settings.paddle_colors):
            color = pal.PADDLE_PALETTE[color_index % len(pal.PADDLE_PALETTE)]
            x = rect.x + 5 + seat * 15
            pygame.draw.rect(surface, pal.UI_BACKGROUND, (x - 1, rect.y + 5, 10, 25))
            pygame.draw.rect(surface, color, (x, rect.y + 6, 8, 23))
            draw_text(surface, str(seat + 1), x + 2, rect.y + 36, pal.WHITE)
        pygame.draw.rect(surface, pal.UI_MUTED, rect, 1)

    def _draw_style_preview(self, surface: pygame.Surface, frame: pygame.Surface | None) -> None:
        rect = pygame.Rect(*STYLE_PREVIEW_BOX)
        pygame.draw.rect(surface, pal.NAVY, rect)
        inner = rect.inflate(-2, -2)
        selected = self.menu.index
        if selected == SEATS + 3:
            draw_field_style_icon(surface, inner, self.ctx.settings.field_style)
            pygame.draw.rect(surface, pal.UI_MUTED, rect, 1)
            return
        assert frame is not None
        if selected < SEATS:
            preview = self._paddle_preview_crop(frame, 0)
        elif selected == SEATS:
            preview = pygame.Surface(inner.size)
            preview.fill(pal.BLACK)
            draw_background(preview, self.ctx.settings.background, self._preview_tick)
        elif selected == SEATS + 1:
            point = self.preview_renderer.camera.project(
                self.preview_world.ball.pos.x,
                self.preview_world.ball.pos.y,
                BALL_LIFT,
            )
            preview = self._crop_preview(
                frame,
                pygame.Rect(round(point.sx) - 12, round(point.sy) - 12, 24, 24),
                inner.size,
            )
        elif selected == SEATS + 2:
            trail_points = [
                self.preview_renderer.camera.project(x, y, BALL_LIFT)
                for x, y in self.preview_renderer.trail.points
            ]
            bounds = pygame.Rect(
                round(min(point.sx for point in trail_points)) - 5,
                round(min(point.sy for point in trail_points)) - 5,
                round(
                    max(point.sx for point in trail_points)
                    - min(point.sx for point in trail_points)
                )
                + 10,
                round(
                    max(point.sy for point in trail_points)
                    - min(point.sy for point in trail_points)
                )
                + 10,
            )
            preview = self._crop_preview(frame, bounds, inner.size)
        else:
            preview = frame
        self._blit_preview_fit(surface, inner, preview)
        pygame.draw.rect(surface, pal.UI_MUTED, rect, 1)

    def _paddle_preview_crop(self, frame: pygame.Surface, seat: int) -> pygame.Surface:
        paddle = self.preview_world.paddles[seat]
        rect = paddle.rect
        projected = [
            self.preview_renderer.camera.project(x, y, z)
            for x in (rect.cx - rect.half_w, rect.cx + rect.half_w)
            for y in (rect.cy - rect.half_h, rect.cy + rect.half_h)
            for z in (0.0, PADDLE_HEIGHT)
        ]
        bounds = pygame.Rect(
            round(min(point.sx for point in projected)) - 4,
            round(min(point.sy for point in projected)) - 4,
            round(max(point.sx for point in projected) - min(point.sx for point in projected)) + 8,
            round(max(point.sy for point in projected) - min(point.sy for point in projected)) + 8,
        )
        return self._crop_preview(frame, bounds, (64, 44), rotate=True)

    @staticmethod
    def _crop_preview(
        frame: pygame.Surface, bounds: pygame.Rect, size: tuple[int, int], *, rotate: bool = False
    ) -> pygame.Surface:
        crop = bounds.clip(frame.get_rect())
        image = frame.subsurface(crop).copy()
        if rotate:
            image = pygame.transform.rotate(image, 90)
        return pygame.transform.scale(image, size)

    @staticmethod
    def _blit_preview_fit(
        surface: pygame.Surface, target: pygame.Rect, preview: pygame.Surface
    ) -> None:
        scale = min(target.width / preview.get_width(), target.height / preview.get_height())
        size = (
            max(1, round(preview.get_width() * scale)),
            max(1, round(preview.get_height() * scale)),
        )
        fitted = pygame.transform.scale(preview, size)
        surface.blit(
            fitted,
            (target.centerx - size[0] // 2, target.centery - size[1] // 2),
        )


class HowToPlayScreen(Screen):
    """@brief Paged explanation of the goal, controls, modes and extras."""

    show_music_notice = True
    PAGES = 6
    LINES = 6

    def __init__(self, ctx: AppContext) -> None:
        """@brief Create the screen on the first page.
        @param ctx Application context.
        """
        super().__init__(ctx)
        self.page = 1

    def handle_event(self, event: pygame.event.Event) -> None:
        """@brief Left/Right turn pages; Esc leaves.
        @param event pygame event.
        """
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.ctx.stack.pop()
        elif event.key in (pygame.K_RIGHT, pygame.K_RETURN, pygame.K_KP_ENTER):
            self.page = self.page % self.PAGES + 1
            self.ctx.audio.play("menu")
        elif event.key == pygame.K_LEFT:
            self.page = (self.page - 2) % self.PAGES + 1
            self.ctx.audio.play("menu")

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Draw the current page.
        @param surface Low-resolution target.
        """
        t = self.ctx.t
        _menu_backdrop(surface)
        _centered_title(surface, t("howto.title"), TITLE_Y - 6)
        _centered(surface, t(f"howto.{self.page}.title"), 36, pal.YELLOW, 2)
        for i in range(1, self.LINES + 1):
            key = f"howto.{self.page}.line{i}"
            text = t(key)
            if text != key:
                draw_text(surface, text, 24, 58 + (i - 1) * 12, pal.WHITE)
        _centered(
            surface, t("howto.page", page=self.page, total=self.PAGES), HINT_Y - 12, pal.LIGHT_GREY
        )
        _centered(surface, t("howto.nav"), HINT_Y, pal.LIGHT_GREY)


def make_keymap(data: dict[str, list[int]]) -> KeyMap:
    """@brief Restore a key map from settings, falling back to defaults when invalid.
    @param data Serialised bindings.
    @return A usable key map.
    """
    try:
        return KeyMap.from_dict(data)
    except (ValueError, IndexError, TypeError):
        return KeyMap()
