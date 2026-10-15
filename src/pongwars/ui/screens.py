"""@package pongwars.ui.screens
@brief Concrete screens: title, menus, match setup, match, pause, results and settings.
"""

import random
from dataclasses import replace

import pygame

from pongwars.ai import AIController, Observation
from pongwars.core.i18n import available_languages, load_catalog
from pongwars.core.loop import FixedStepLoop
from pongwars.core.settings import BACKGROUNDS, PADDLE_COLOR_COUNT, PADDLE_SKIN_COUNT, SEATS
from pongwars.domain import constants as c
from pongwars.domain.arenas import ArenaSpec, arena_names, get_arena
from pongwars.domain.config import AI_DIFFICULTIES, MAX_PLAYERS, ConfigError, MatchConfig
from pongwars.domain.modes import MODES, OptionSpec
from pongwars.domain.world import Phase, World
from pongwars.input.controllers import (
    KeyBinding,
    KeyboardInput,
    KeyMap,
    PlayerInput,
    collect_inputs,
    poll_fire,
)
from pongwars.render import palette as pal
from pongwars.render.font import draw_text, text_width
from pongwars.render.renderer import LOW_H, LOW_W, Renderer, RenderSettings
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
MAX_SEED = 2**31 - 1
BLINK_PERIOD = 1.0
PREVIEW_BOX = (190, 100, 120, 68)
VOLUME_STEP = 10
MAX_VOLUME = 100
MIN_SCALE = 2
MAX_SCALE = 8
OPTION_STEP_THRESHOLD = 50


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


def _title(ctx: AppContext, surface: pygame.Surface, key: str) -> None:
    surface.fill(pal.NAVY)
    _centered(surface, ctx.t(key), TITLE_Y, pal.ORANGE, 2)


def _hint(ctx: AppContext, surface: pygame.Surface) -> None:
    _centered(surface, ctx.t("menu.hint"), HINT_Y, pal.LIGHT_GREY)


class MenuScreen(Screen):
    """@brief Base of screens made of a single menu."""

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
        surface.fill(pal.NAVY)
        _centered(surface, self.ctx.t("app.title"), 50, pal.ORANGE, 5)
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
        soon = lambda: t("menu.coming_soon")  # noqa: E731
        self.menu.set_items(
            [
                MenuItem(
                    lambda: t("menu.main.local"), on_activate=lambda: self.open(("human", "human"))
                ),
                MenuItem(
                    lambda: t("menu.main.versus_ai"), on_activate=lambda: self.open(("human", "ai"))
                ),
                MenuItem(lambda: t("menu.main.lan_host"), soon, enabled=False),
                MenuItem(lambda: t("menu.main.lan_join"), soon, enabled=False),
                MenuItem(lambda: t("menu.main.appearance"), on_activate=self.open_appearance),
                MenuItem(lambda: t("menu.main.howto"), on_activate=self.open_howto),
                MenuItem(lambda: t("menu.main.settings"), on_activate=self.open_settings),
                MenuItem(lambda: t("menu.main.quit"), on_activate=ctx.stack.pop_all),
            ]
        )
        ctx.audio.start_music()

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


class SetupScreen(MenuScreen):
    """@brief Auto-generated match configuration form with an arena preview."""

    title_key = "setup.title"

    def __init__(self, ctx: AppContext, preset: tuple[str, ...] = ("human", "human")) -> None:
        """@brief Build the form.
        @param ctx Application context.
        @param preset Controllers used for the first seats.
        """
        super().__init__(ctx)
        self.mode = "classic"
        self.arena = "classic"
        self.preset = preset
        self.controllers: list[str] = []
        self.difficulty = "normal"
        self.extras = "off"
        self.view = ctx.settings.view
        self.options: dict[str, float] = {}
        self._reset_options()
        self._fit_controllers()
        self.rebuild()

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
            self.controllers[i] if i < len(self.controllers) else self.preset[i % len(self.preset)]
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

    def start(self) -> None:
        """@brief Launch the match."""
        try:
            config = self.build_config()
        except ConfigError:
            return
        self.ctx.stack.push(MatchScreen(self.ctx, config, self.view))

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
        render_settings = RenderSettings(
            particles=s.particles,
            trail=s.trail,
            shake=s.shake,
            scale=1,
            view="split" if self.view == "split" else "shared",
            background=s.background,
            paddle_colors=tuple(s.paddle_colors),
            paddle_skins=tuple(s.paddle_skins),
        )
        self.renderer = Renderer(render_settings, config.seed, ctx.translator)
        self.humans = [config.controllers[i] == "human" for i in range(self.world.players)]
        self.controllers = [self._controller(i) for i in range(self.world.players)]
        self.loop = FixedStepLoop(self._step, c.DT)
        self.paused = False
        ctx.audio.start_music(self._pick_track(config.seed))

    def _pick_track(self, seed: int) -> str:
        tracks = self.ctx.audio.bank.match_tracks
        choice = self.ctx.settings.music_track
        if choice in tracks:
            return choice
        return tracks[seed % len(tracks)] if tracks else "menu"

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
        fire = poll_fire(self.humans, pygame.key.get_pressed)
        events = self.world.step(collect_inputs(self.controllers, fire))
        self.renderer.handle_events(self.world, events)
        self.ctx.audio.handle_events(events)

    def handle_event(self, event: pygame.event.Event) -> None:
        """@brief Esc opens the pause menu.
        @param event pygame event.
        """
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.ctx.stack.push(PauseScreen(self.ctx))

    def update(self, dt: float) -> None:
        """@brief Advance the simulation unless a overlay is on top.
        @param dt Seconds elapsed.
        """
        if self.ctx.stack.top is not self:
            return
        self.loop.advance(dt)
        self.renderer.update(self.world, dt)
        if self.world.phase is Phase.FINISHED:
            self.ctx.audio.stop_music()
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
        self.ctx.audio.stop_music()
        self.ctx.stack.pop_to(MainMenuScreen)

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Dim the match and draw the menu.
        @param surface Low-resolution target.
        """
        shade = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        surface.blit(shade, (0, 0))
        _centered(surface, self.ctx.t(self.title_key), 40, pal.ORANGE, 2)
        self.menu.draw(surface, 100, 80, 120)


class ResultsScreen(MenuScreen):
    """@brief End-of-match summary with follow-up actions."""

    title_key = "results.title"

    def __init__(self, ctx: AppContext, config: MatchConfig, world: World, view: str) -> None:
        """@brief Build the screen.
        @param ctx Application context.
        @param config Configuration that was played.
        @param world Finished world.
        @param view Camera mode used.
        """
        super().__init__(ctx)
        self.config = config
        self.world = world
        self.view = view
        t = ctx.t
        self.menu.set_items(
            [
                MenuItem(lambda: t("results.rematch"), on_activate=self.rematch),
                MenuItem(lambda: t("results.setup"), on_activate=self._to_setup),
                MenuItem(lambda: t("results.menu"), on_activate=self._to_menu),
            ]
        )

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
        """@brief Esc returns to the setup form."""
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
    """@brief Audio, display, effects, language and key bindings (persisted on every change)."""

    title_key = "settings.title"

    def __init__(self, ctx: AppContext) -> None:
        """@brief Build the menu.
        @param ctx Application context.
        """
        super().__init__(ctx)
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
        """@brief Create the rows."""
        t, s = self.ctx.t, self.ctx.settings
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
            MenuItem(
                lambda: t("settings.fullscreen"),
                lambda: self._onoff("fullscreen"),
                on_adjust=lambda d: self._toggle("fullscreen"),
            ),
            MenuItem(lambda: t("settings.scale"), lambda: f"x{s.scale}", on_adjust=self._scale),
            MenuItem(
                lambda: t("settings.language"),
                lambda: load_catalog(s.language).get("language.name", s.language),
                on_adjust=self._language,
            ),
            MenuItem(
                lambda: t("settings.particles"),
                lambda: self._onoff("particles"),
                on_adjust=lambda d: self._toggle("particles"),
            ),
            MenuItem(
                lambda: t("settings.trail"),
                lambda: self._onoff("trail"),
                on_adjust=lambda d: self._toggle("trail"),
            ),
            MenuItem(
                lambda: t("settings.shake"),
                lambda: self._onoff("shake"),
                on_adjust=lambda d: self._toggle("shake"),
            ),
            MenuItem(
                lambda: t("settings.view"),
                lambda: t(f"view.{s.view}"),
                on_adjust=self._view,
            ),
        ]
        for seat in range(MAX_PLAYERS):
            items.append(
                MenuItem(
                    lambda seat=seat: t("settings.keys", number=seat + 1),  # type: ignore[misc]
                    lambda seat=seat: self._key_names(seat),  # type: ignore[misc]
                    on_activate=lambda seat=seat: self.begin_capture(seat),  # type: ignore[misc]
                )
            )
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
        """@brief Draw the menu and capture/error hints.
        @param surface Low-resolution target.
        """
        _title(self.ctx, surface, self.title_key)
        self.menu.draw(surface, 24, 28, 272)
        if self.capturing is not None:
            _centered(surface, self.ctx.t("settings.press_keys"), HINT_Y - 10, pal.YELLOW)
        elif self.error:
            _centered(surface, self.ctx.t(self.error), HINT_Y - 10, pal.RED)
        _hint(self.ctx, surface)


class AppearanceScreen(MenuScreen):
    """@brief Paddle colours and styles, arena background and music track."""

    title_key = "appearance.title"

    def __init__(self, ctx: AppContext) -> None:
        """@brief Build the rows.
        @param ctx Application context.
        """
        super().__init__(ctx)
        t, s = ctx.t, ctx.settings
        items: list[MenuItem] = []
        for seat in range(SEATS):
            items.append(
                MenuItem(
                    lambda seat=seat: t("appearance.color", number=seat + 1),  # type: ignore[misc]
                    lambda seat=seat: t(f"color.{s.paddle_colors[seat]}"),  # type: ignore[misc]
                    on_adjust=lambda d, seat=seat: self._step_seat(  # type: ignore[misc]
                        s.paddle_colors, seat, d, PADDLE_COLOR_COUNT
                    ),
                )
            )
        for seat in range(SEATS):
            items.append(
                MenuItem(
                    lambda seat=seat: t("appearance.skin", number=seat + 1),  # type: ignore[misc]
                    lambda seat=seat: t(f"skin.{s.paddle_skins[seat]}"),  # type: ignore[misc]
                    on_adjust=lambda d, seat=seat: self._step_seat(  # type: ignore[misc]
                        s.paddle_skins, seat, d, PADDLE_SKIN_COUNT
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
        items.append(
            MenuItem(
                lambda: t("appearance.track"),
                lambda: t(f"track.{s.music_track}"),
                on_adjust=self._track,
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

    def _track(self, step: int) -> None:
        s = self.ctx.settings
        choices = ["random", *self.ctx.audio.bank.match_tracks]
        s.music_track = cycle(choices, s.music_track, step)
        s.save()
        if s.music_track != "random":
            self.ctx.audio.start_music(s.music_track)
        else:
            self.ctx.audio.start_music()

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Draw the rows and a live paddle preview.
        @param surface Low-resolution target.
        """
        _title(self.ctx, surface, self.title_key)
        self.menu.draw(surface, 24, 26, 220)
        s = self.ctx.settings
        for seat in range(SEATS):
            colour = pal.PADDLE_PALETTE[s.paddle_colors[seat] % len(pal.PADDLE_PALETTE)]
            x = 262 + seat * 12
            pygame.draw.rect(surface, colour, (x, 40, 6, 36))
            if s.paddle_skins[seat] == 1:
                for y in range(42, 76, 6):
                    pygame.draw.rect(surface, pal.WHITE, (x, y, 6, 2))
            elif s.paddle_skins[seat] == 2:
                pygame.draw.rect(surface, pal.WHITE, (x + 2, 40, 2, 36))
            elif s.paddle_skins[seat] == 3:
                pygame.draw.rect(surface, pal.WHITE, (x, 40, 6, 4))
                pygame.draw.rect(surface, pal.WHITE, (x, 72, 6, 4))
        _hint(self.ctx, surface)


class HowToPlayScreen(Screen):
    """@brief Paged explanation of the goal, controls, modes and extras."""

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
        surface.fill(pal.NAVY)
        _centered(surface, t("howto.title"), TITLE_Y - 6, pal.ORANGE, 2)
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
