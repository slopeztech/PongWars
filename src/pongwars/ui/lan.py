"""@package pongwars.ui.lan
@brief LAN screens: host lobby, join browser, network matches, notices and help.
"""

from collections.abc import Callable

import pygame

from pongwars.ai import AIController, Observation
from pongwars.core.loop import FixedStepLoop
from pongwars.domain import constants as c
from pongwars.domain.config import MatchConfig
from pongwars.domain.world import Phase
from pongwars.input.controllers import FIRE_KEYS, KeyboardInput
from pongwars.net.client import ClientSession, ClientState
from pongwars.net.discovery import Discovery, HostInfo
from pongwars.net.host import HostSession, clean_name
from pongwars.net.protocol import DEFAULT_PORT, MAX_NAME
from pongwars.net.transport import Transport, UdpTransport, local_ip
from pongwars.render import palette as pal
from pongwars.render.font import draw_text
from pongwars.render.renderer import LOW_H, Renderer, RenderSettings
from pongwars.ui.core import AppContext, Screen
from pongwars.ui.screens import (
    HINT_Y,
    TITLE_Y,
    MainMenuScreen,
    MatchScreen,
    MenuScreen,
    ResultsScreen,
    _centered,
    _hint,
    _title,
)
from pongwars.ui.widgets import MenuItem

TransportFactory = Callable[[], Transport]
MAX_ADDRESS = 21
ADDRESS_CHARS = frozenset("0123456789.:-abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
NAME_INPUT_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
MAX_PORT = 65535
HELP_PAGES = 4
HELP_LINES = 6
LIST_X = 24
LIST_W = 272
LIST_Y = 30
STATUS_Y = LOW_H - 24


def parse_address(text: str) -> tuple[str, int] | None:
    """@brief Parse "host" or "host:port".
    @param text User input.
    @return The address, or None when it is malformed.
    """
    host, sep, port_text = text.strip().partition(":")
    if not host:
        return None
    if not sep:
        return host, DEFAULT_PORT
    if not port_text.isdigit() or not 0 < int(port_text) <= MAX_PORT:
        return None
    return host, int(port_text)


def _udp() -> Transport:
    return UdpTransport(0)


def _render_settings(ctx: AppContext) -> RenderSettings:
    s = ctx.settings
    return RenderSettings(
        particles=s.particles,
        trail=s.trail,
        shake=s.shake,
        scale=1,
        view="split" if s.view == "split" else "shared",
        background=s.background,
        paddle_colors=tuple(s.paddle_colors),
        paddle_skins=tuple(s.paddle_skins),
    )


class LanNoticeScreen(MenuScreen):
    """@brief A short message (error or disconnection) with a way back to the menu."""

    title_key = "lan.notice.title"

    def __init__(self, ctx: AppContext, message_key: str) -> None:
        """@brief Build the notice.
        @param ctx Application context.
        @param message_key Locale key of the message.
        """
        super().__init__(ctx)
        self.message_key = message_key
        self.menu.set_items([MenuItem(lambda: ctx.t("lan.notice.ok"), on_activate=self.back)])

    def back(self) -> None:
        """@brief Return to the main menu."""
        self.ctx.audio.stop_music()
        self.ctx.stack.pop_to(MainMenuScreen)

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Draw the message.
        @param surface Low-resolution target.
        """
        _title(self.ctx, surface, self.title_key)
        _centered(surface, self.ctx.t(self.message_key), 60, pal.YELLOW)
        self.menu.draw(surface, 120, 100, 80)


class LanLobbyScreen(MenuScreen):
    """@brief Host lobby: shows who joined and starts the match."""

    title_key = "lan.lobby.title"

    def __init__(
        self,
        ctx: AppContext,
        config: MatchConfig,
        view: str,
        transport: Transport | None = None,
    ) -> None:
        """@brief Open the game port and wait for players.
        @param ctx Application context.
        @param config Match configuration (remote seats wait for clients).
        @param view Camera mode of the host.
        @param transport Datagram endpoint (UDP on the game port when omitted).
        """
        super().__init__(ctx)
        self.config = config
        self.view = view
        self.error = False
        self.host: HostSession | None = None
        try:
            endpoint = transport or UdpTransport(DEFAULT_PORT)
        except OSError:
            self.error = True
        else:
            self.host = HostSession(config, ctx.settings.player_name, endpoint)
        self.address = f"{local_ip()}:{DEFAULT_PORT}"
        t = ctx.t
        rows = [MenuItem(lambda: t("lan.lobby.start"), on_activate=self.start)]
        self.menu.set_items(rows if self.host else [])

    def start(self) -> None:
        """@brief Start now; seats nobody took are played by the AI."""
        if self.host is None:
            return
        self.host.start()
        self.ctx.stack.replace(LanHostMatchScreen(self.ctx, self.host, self.view))

    def back(self) -> None:
        """@brief Close the lobby and return to the setup form."""
        if self.host is not None:
            self.host.close("closed")
        self.ctx.stack.pop()

    def update(self, dt: float) -> None:
        """@brief Serve joins and discovery requests.
        @param dt Seconds elapsed.
        """
        if self.host is not None:
            self.host.poll()

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Draw the roster and the address clients can use.
        @param surface Low-resolution target.
        """
        t = self.ctx.t
        _title(self.ctx, surface, self.title_key)
        if self.host is None:
            _centered(surface, t("lan.lobby.port_busy"), 60, pal.RED)
            _hint(self.ctx, surface)
            return
        _centered(surface, t("lan.lobby.address", address=self.address), 30, pal.LIGHT_GREY)
        open_seats = set(self.host.open_seats)
        for seat, name in enumerate(self.host.names()):
            if name:
                text = name
            elif seat in open_seats:
                text = t("lan.lobby.waiting")
            else:
                text = t("controller.ai")
            color = pal.PLAYER_COLORS[seat % len(pal.PLAYER_COLORS)]
            draw_text(
                surface,
                f"{t('hud.player', number=seat + 1)}  {text}",
                LIST_X,
                46 + seat * 10,
                color,
            )
        self.menu.draw(surface, LIST_X, 100, LIST_W - 2 * LIST_X)
        _centered(surface, t("lan.lobby.hint"), HINT_Y, pal.LIGHT_GREY)


class LanJoinScreen(MenuScreen):
    """@brief Find hosts on the network or type an address, then connect."""

    title_key = "lan.join.title"

    def __init__(self, ctx: AppContext, transport_factory: TransportFactory = _udp) -> None:
        """@brief Start scanning.
        @param ctx Application context.
        @param transport_factory Creates the datagram endpoints (UDP by default).
        """
        super().__init__(ctx)
        self.factory = transport_factory
        self.address = ctx.settings.last_host
        self.name = clean_name(ctx.settings.player_name)
        self.editing = ""
        self.status = ""
        self.hosts: list[HostInfo] = []
        self.client: ClientSession | None = None
        self.discovery: Discovery | None = None
        self._shown: tuple[object, ...] = ()
        self.scan()

    def scan(self) -> None:
        """@brief Broadcast a new discovery request."""
        try:
            if self.discovery is None:
                self.discovery = Discovery(self.factory())
            self.discovery.scan()
            self.status = self.ctx.t("lan.join.scanning")
        except OSError:
            self.status = self.ctx.t("lan.join.no_network")
        self.rebuild()

    def rebuild(self) -> None:
        """@brief Recreate the rows (hosts found, address, name, actions)."""
        t = self.ctx.t
        if self.client is not None:
            self.menu.set_items([MenuItem(lambda: t("lan.join.cancel"), on_activate=self.cancel)])
            return
        items = []
        for info in self.hosts:
            items.append(
                MenuItem(
                    lambda info=info: info.name,  # type: ignore[misc]
                    lambda info=info: f"{info.joined}/{info.players}",  # type: ignore[misc]
                    on_activate=lambda info=info: self.connect(info.addr),  # type: ignore[misc]
                )
            )
        items.append(MenuItem(lambda: t("lan.join.scan"), on_activate=self.scan))
        items.append(
            MenuItem(
                lambda: t("lan.join.address"),
                lambda: self._field("address"),
                on_activate=lambda: self._edit("address"),
            )
        )
        items.append(MenuItem(lambda: t("lan.join.connect"), on_activate=self.connect_typed))
        items.append(
            MenuItem(
                lambda: t("lan.join.name"),
                lambda: self._field("name"),
                on_activate=lambda: self._edit("name"),
            )
        )
        self.menu.set_items(items)

    def _field(self, field: str) -> str:
        text = self.address if field == "address" else self.name
        return text + ("_" if self.editing == field else "")

    def _edit(self, field: str) -> None:
        self.editing = field

    def connect_typed(self) -> None:
        """@brief Connect to the address typed by the user."""
        addr = parse_address(self.address)
        if addr is None:
            self.status = self.ctx.t("lan.join.bad_address")
            return
        self.ctx.settings.last_host = self.address
        self.connect(addr)

    def connect(self, addr: tuple[str, int]) -> None:
        """@brief Open a session to a host.
        @param addr Host address.
        """
        self.ctx.settings.player_name = self.name or "PLAYER"
        try:
            self.client = ClientSession(addr, self.name or "PLAYER", self.factory())
        except OSError:
            self.status = self.ctx.t("lan.join.no_network")
            return
        self.status = self.ctx.t("lan.join.connecting")
        self.rebuild()

    def cancel(self) -> None:
        """@brief Abort the connection attempt."""
        if self.client is not None:
            self.client.close()
            self.client = None
        self.status = ""
        self.rebuild()

    def back(self) -> None:
        """@brief Leave the screen and release the sockets."""
        self.cancel()
        if self.discovery is not None:
            self.discovery.close()
        self.ctx.settings.player_name = self.name or "PLAYER"
        self.ctx.stack.pop()

    def handle_event(self, event: pygame.event.Event) -> None:
        """@brief Text entry while editing; menu navigation otherwise.
        @param event pygame event.
        """
        if self.editing and event.type == pygame.KEYDOWN:
            self._type(event)
            return
        super().handle_event(event)

    def _type(self, event: pygame.event.Event) -> None:
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
            self.editing = ""
            return
        text = self.address if self.editing == "address" else self.name
        if event.key == pygame.K_BACKSPACE:
            text = text[:-1]
        else:
            char = event.unicode
            if self.editing == "name":
                char = char.upper()
            allowed = ADDRESS_CHARS if self.editing == "address" else NAME_INPUT_CHARS
            limit = MAX_ADDRESS if self.editing == "address" else MAX_NAME
            if len(char) == 1 and char in allowed and len(text) < limit:
                text += char
        if self.editing == "address":
            self.address = text
        else:
            self.name = text

    def update(self, dt: float) -> None:
        """@brief Collect replies and drive the connection.
        @param dt Seconds elapsed.
        """
        if self.client is not None:
            self._update_client()
            return
        if self.discovery is not None:
            found = self.discovery.poll()
            key = tuple((h.name, h.addr, h.joined) for h in found)
            if key != self._shown:
                self._shown = key
                self.hosts = found
                self.rebuild()

    def _update_client(self) -> None:
        client = self.client
        if client is None:
            return
        client.poll()
        t = self.ctx.t
        if client.state is ClientState.PLAYING and client.world is not None:
            self.client = None
            if self.discovery is not None:
                self.discovery.close()
            self.ctx.stack.replace(LanClientMatchScreen(self.ctx, client))
        elif client.state is ClientState.REJECTED:
            self.status = t(f"lan.reject.{client.reject_reason}")
            self.client = None
            self.rebuild()
        elif client.state in (ClientState.TIMEOUT, ClientState.CLOSED):
            self.status = t("lan.join.timeout")
            self.client = None
            self.rebuild()
        elif client.state is ClientState.LOBBY:
            self.status = t("lan.join.joined", seat=client.seat + 1)

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Draw the host list, fields and status.
        @param surface Low-resolution target.
        """
        _title(self.ctx, surface, self.title_key)
        self.menu.draw(surface, LIST_X, LIST_Y, LIST_W - 2 * LIST_X)
        _centered(surface, self.status, STATUS_Y, pal.YELLOW)
        _centered(
            surface,
            self.ctx.t("lan.join.hint_edit" if self.editing else "menu.hint"),
            HINT_Y,
            pal.LIGHT_GREY,
        )


class LanQuitScreen(MenuScreen):
    """@brief Overlay over a network match; the match keeps running underneath."""

    transparent = True
    title_key = "lan.quit.title"

    def __init__(self, ctx: AppContext, on_quit: Callable[[], None]) -> None:
        """@brief Build the menu.
        @param ctx Application context.
        @param on_quit Called before returning to the main menu.
        """
        super().__init__(ctx)
        self.on_quit = on_quit
        t = ctx.t
        self.menu.set_items(
            [
                MenuItem(lambda: t("pause.resume"), on_activate=ctx.stack.pop),
                MenuItem(lambda: t("lan.quit.leave"), on_activate=self._leave),
            ]
        )

    def _leave(self) -> None:
        self.on_quit()
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


class LanDropScreen(MenuScreen):
    """@brief Host overlay shown while a remote player is missing."""

    transparent = True
    title_key = "lan.drop.title"

    def __init__(self, ctx: AppContext, host: HostSession) -> None:
        """@brief Build the menu.
        @param ctx Application context.
        @param host The running host session.
        """
        super().__init__(ctx)
        self.host = host
        t = ctx.t
        self.menu.set_items(
            [
                MenuItem(lambda: t("lan.drop.wait"), on_activate=lambda: None),
                MenuItem(lambda: t("lan.drop.ai"), on_activate=self._hand_to_ai),
                MenuItem(lambda: t("lan.quit.leave"), on_activate=self._leave),
            ]
        )

    def _hand_to_ai(self) -> None:
        self.host.resolve("ai")
        self.ctx.stack.pop()

    def _leave(self) -> None:
        self.host.close("closed")
        self.ctx.audio.stop_music()
        self.ctx.stack.pop_to(MainMenuScreen)

    def back(self) -> None:
        """@brief Esc keeps waiting (the overlay stays)."""

    def update(self, dt: float) -> None:
        """@brief Close by itself once the missing player is back.
        @param dt Seconds elapsed.
        """
        if not self.host.paused and self.ctx.stack.top is self:
            self.ctx.stack.pop()

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Dim the match and draw the menu.
        @param surface Low-resolution target.
        """
        shade = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        surface.blit(shade, (0, 0))
        _centered(surface, self.ctx.t(self.title_key), 40, pal.ORANGE, 2)
        _centered(surface, self.ctx.t("lan.drop.text"), 62, pal.WHITE)
        self.menu.draw(surface, 90, 84, 140)


class LanHostMatchScreen(MatchScreen):
    """@brief The authoritative side of a network match (also plays seat 1)."""

    def __init__(self, ctx: AppContext, host: HostSession, view: str) -> None:
        """@brief Wrap a started host session.
        @param ctx Application context.
        @param host Session whose lobby has been closed with start().
        @param view Camera mode of the host.
        """
        super().__init__(ctx, host.config, view)
        assert host.world is not None  # noqa: S101
        self.host = host
        self.world = host.world
        self.local = KeyboardInput(ctx.keymap.get(0), pygame.key.get_pressed)
        self.bots: dict[int, AIController] = {}
        self._drop_shown = False
        self._fire_tap = False

    def _bot(self, seat: int) -> AIController:
        if seat not in self.bots:
            world = self.world
            self.bots[seat] = AIController(
                lambda: Observation.from_world(world, seat),
                self.config.ai_difficulty,
                self.config.ai_strategy,
                self.config.seed + seat,
            )
        return self.bots[seat]

    def _local_input(self, seat: int) -> tuple[float, bool]:
        if seat == 0:
            fire = self._fire_tap or bool(pygame.key.get_pressed()[FIRE_KEYS[0]])
            self._fire_tap = False
            return self.local.poll(), fire
        return self._bot(seat).poll(), False

    def _step(self) -> None:
        events = self.host.step(self._local_input)
        self.renderer.handle_events(self.world, events)
        self.ctx.audio.handle_events(events)

    def handle_event(self, event: pygame.event.Event) -> None:
        """@brief Esc opens the leave menu without pausing the match.
        @param event pygame event.
        """
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.ctx.stack.push(LanQuitScreen(self.ctx, lambda: self.host.close("closed")))
        elif event.type == pygame.KEYDOWN and event.key == FIRE_KEYS[0]:
            self._fire_tap = True

    def update(self, dt: float) -> None:
        """@brief Serve the network and advance the match.
        @param dt Seconds elapsed.
        """
        self.host.poll()
        self.loop.advance(dt)
        self.renderer.update(self.world, dt)
        if self.host.paused and not self._drop_shown and self.ctx.stack.top is self:
            self._drop_shown = True
            self.ctx.stack.push(LanDropScreen(self.ctx, self.host))
        elif not self.host.paused:
            self._drop_shown = False
        if self.world.phase is Phase.FINISHED:
            self.host.close("finished")
            self.ctx.audio.stop_music()
            while self.ctx.stack.top is not self:
                self.ctx.stack.pop()
            self.ctx.stack.replace(
                ResultsScreen(self.ctx, self.config, self.world, self.view, lan=True)
            )


class LanClientMatchScreen(Screen):
    """@brief The remote side: sends inputs, renders the interpolated host state."""

    def __init__(self, ctx: AppContext, client: ClientSession) -> None:
        """@brief Wrap a connected client session.
        @param ctx Application context.
        @param client Session that reached the PLAYING state.
        """
        super().__init__(ctx)
        assert client.world is not None and client.config is not None  # noqa: S101
        self.client = client
        self.config = client.config
        self.world = client.world
        self.renderer = Renderer(_render_settings(ctx), client.config.seed, ctx.translator)
        self.input = KeyboardInput(ctx.keymap.get(0), pygame.key.get_pressed)
        self.loop = FixedStepLoop(self._tick, c.DT)
        self._fire_tap = False
        ctx.audio.start_music("match", seed=client.config.seed)

    def _tick(self) -> None:
        fire = self._fire_tap or bool(pygame.key.get_pressed()[FIRE_KEYS[0]])
        self._fire_tap = False
        self.client.send_input(self.input.poll(), fire)

    def handle_event(self, event: pygame.event.Event) -> None:
        """@brief Esc opens the leave menu.
        @param event pygame event.
        """
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.ctx.stack.push(LanQuitScreen(self.ctx, self.client.close))
        elif event.type == pygame.KEYDOWN and event.key == FIRE_KEYS[0]:
            self._fire_tap = True

    def update(self, dt: float) -> None:
        """@brief Receive state, send inputs and detect the end of the match.
        @param dt Seconds elapsed.
        """
        client = self.client
        client.poll()
        self.loop.advance(dt)
        client.interpolate()
        events = client.pop_events()
        self.renderer.handle_events(self.world, events)
        self.ctx.audio.handle_events(events)
        self.renderer.update(self.world, dt)
        if self.world.phase is Phase.FINISHED:
            client.close()
            self._finish(ResultsScreen(self.ctx, self.config, self.world, "shared", lan=True))
        elif not client.active:
            self._finish(LanNoticeScreen(self.ctx, "lan.notice.lost"))

    def _finish(self, screen: Screen) -> None:
        self.ctx.audio.stop_music()
        while self.ctx.stack.top is not self:
            self.ctx.stack.pop()
        self.ctx.stack.replace(screen)

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Render the world plus a small status line.
        @param surface Low-resolution target.
        """
        t = self.ctx.t
        self.renderer.present(self.world, surface)
        if self.client.host_paused:
            _centered(surface, t("lan.client.waiting"), LOW_H // 2, pal.YELLOW, 2)
        status = t("lan.client.status", seat=self.client.seat + 1, ping=int(self.client.ping_ms))
        draw_text(surface, status, 2, LOW_H - 8, pal.LIGHT_GREY)


class LanHelpScreen(Screen):
    """@brief Paged explanation of LAN play."""

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
            self.page = self.page % HELP_PAGES + 1
            self.ctx.audio.play("menu")
        elif event.key == pygame.K_LEFT:
            self.page = (self.page - 2) % HELP_PAGES + 1
            self.ctx.audio.play("menu")

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Draw the current page.
        @param surface Low-resolution target.
        """
        t = self.ctx.t
        surface.fill(pal.NAVY)
        _centered(surface, t("lanhelp.title"), TITLE_Y - 6, pal.ORANGE, 2)
        _centered(surface, t(f"lanhelp.{self.page}.title"), 36, pal.YELLOW, 2)
        for i in range(1, HELP_LINES + 1):
            key = f"lanhelp.{self.page}.line{i}"
            text = t(key)
            if text != key:
                draw_text(surface, text, 24, 58 + (i - 1) * 12, pal.WHITE)
        _centered(
            surface, t("howto.page", page=self.page, total=HELP_PAGES), HINT_Y - 12, pal.LIGHT_GREY
        )
        _centered(surface, t("howto.nav"), HINT_Y, pal.LIGHT_GREY)
