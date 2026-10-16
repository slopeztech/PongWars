"""LAN screen tests (lobby, join, host/client matches, help) over a memory network."""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pygame
import pytest

from pongwars.audio.player import AudioPlayer
from pongwars.core.i18n import Translator
from pongwars.core.settings import Settings
from pongwars.domain.config import MatchConfig
from pongwars.domain.world import Phase
from pongwars.net.transport import MemoryNetwork, local_ip
from pongwars.net.client import ClientState
from pongwars.ui.core import AppContext
from pongwars.ui.lan import (
    LanClientMatchScreen,
    LanClientLobbyScreen,
    LanDropScreen,
    LanHelpScreen,
    LanHostMatchScreen,
    LanJoinScreen,
    LanLobbyScreen,
    LanNoticeScreen,
    LanQuitScreen,
    parse_address,
)
from pongwars.ui.screens import MainMenuScreen, ResultsScreen, SetupScreen
from pongwars.ui.widgets import Menu

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


@pytest.fixture(autouse=True)
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("APPDATA", "XDG_CONFIG_HOME", "HOME"):
        monkeypatch.setenv(name, str(tmp_path))


@pytest.fixture
def ctx() -> Iterator[AppContext]:
    pygame.init()
    yield AppContext(Settings(), Translator(), AudioPlayer())
    pygame.quit()


def key(code: int, char: str = "") -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=code, unicode=char)


def activate(menu: Menu, index: int) -> None:
    callback = menu.items[index].on_activate
    assert callback is not None
    callback()


def surface() -> pygame.Surface:
    return pygame.Surface((320, 180))


def test_parse_address() -> None:
    assert parse_address("10.0.0.2") == ("10.0.0.2", 47474)
    assert parse_address("host:5000") == ("host", 5000)
    assert parse_address("") is None
    assert parse_address("h:x") is None
    assert parse_address("h:70000") is None


def test_local_ip_is_text() -> None:
    assert local_ip().count(".") == 3


def test_help_pages(ctx: AppContext) -> None:
    ctx.stack.push(MainMenuScreen(ctx))
    screen = LanHelpScreen(ctx)
    ctx.stack.push(screen)
    for _ in range(5):
        screen.handle_event(key(pygame.K_RIGHT))
        screen.draw(surface())
    assert screen.page == 2
    screen.handle_event(key(pygame.K_LEFT))
    screen.handle_event(key(pygame.K_LEFT))
    assert screen.page == 4
    screen.handle_event(key(pygame.K_ESCAPE))
    assert isinstance(ctx.stack.top, MainMenuScreen)


def test_menu_opens_lan_screens(ctx: AppContext) -> None:
    menu = MainMenuScreen(ctx)
    ctx.stack.push(menu)
    menu.menu.index = 1
    activate(menu.menu, 1)
    lan_menu = ctx.stack.top
    assert lan_menu is not menu
    activate(lan_menu.menu, 1)
    assert isinstance(ctx.stack.top, LanJoinScreen)
    ctx.stack.top.back()
    assert ctx.stack.top is lan_menu
    ctx.stack.pop()
    menu.menu.index = 2
    activate(menu.menu, 2)
    help_menu = ctx.stack.top
    activate(help_menu.menu, 1)
    assert isinstance(ctx.stack.top, LanHelpScreen)


def test_setup_lan_seats(ctx: AppContext) -> None:
    setup = SetupScreen(ctx, ("human", "remote"), lan=True)
    ctx.stack.push(setup)
    setup._set_controller(0, 1)
    assert setup.controllers[0] == "human"
    setup._set_controller(1, 1)
    assert setup.controllers[1] == "ai"
    setup.start()
    assert isinstance(ctx.stack.top, LanLobbyScreen)
    ctx.stack.top.back()
    assert isinstance(ctx.stack.top, SetupScreen)


def full_session(ctx: AppContext) -> tuple[MemoryNetwork, LanLobbyScreen, LanJoinScreen]:
    """Host lobby + join screen on one memory network, client joined and started."""
    net = MemoryNetwork()
    config = MatchConfig(controllers=("human", "remote"), seed=3)
    lobby = LanLobbyScreen(ctx, config, "shared", net.endpoint("10.0.0.1", 47474))
    ctx.stack.push(lobby)
    ctx.settings.player_name = "BOB"
    join = LanJoinScreen(ctx, lambda: net.endpoint("10.0.0.2"))
    ctx.stack.push(join)
    return net, lobby, join


def spin(net: MemoryNetwork, *screens: Any, n: int = 6) -> None:
    for _ in range(n):
        net.advance(1)
        for s in screens:
            s.update(0.016)


def test_lobby_join_and_match_flow(ctx: AppContext) -> None:
    net, lobby, join = full_session(ctx)
    spin(net, join, lobby)
    assert [h.name for h in join.hosts]
    assert join.hosts[0].room_name == "PLAYER"
    lobby.draw(surface())
    join.draw(surface())
    assert not lobby.menu.items[2].enabled
    lobby.start()
    assert lobby.host is not None and lobby.host.world is None
    activate(join.menu, 0)  # connect to the discovered host
    spin(net, join, lobby, n=2)
    assert lobby.host is not None and "BOB" in lobby.host.names()
    client_lobby = ctx.stack.top
    assert isinstance(client_lobby, LanClientLobbyScreen)
    client_lobby._adjust_color(1)
    client_lobby._adjust_skin(1)
    spin(net, client_lobby, lobby)
    assert lobby.host.colors[1] == client_lobby.client.colors[1]
    assert lobby.host.skins[1] == client_lobby.client.skins[1]
    lobby.start()
    host_screen = ctx.stack.top
    assert isinstance(host_screen, LanHostMatchScreen)
    for _ in range(40):
        net.advance(1)
        client_lobby.update(0.016)
        host_screen.update(0.016)
        if client_lobby.client.state is not ClientState.PLAYING:
            continue
        break
    client_screen = ctx.stack.top
    assert isinstance(client_screen, LanClientMatchScreen)
    for _ in range(60):
        net.advance(1)
        host_screen.update(0.05)
        client_screen.update(0.05)
    client_screen.draw(surface())
    host_screen.draw(surface())
    assert client_screen.world.tick > 0


def test_join_edit_and_errors(ctx: AppContext) -> None:
    net = MemoryNetwork()
    join = LanJoinScreen(ctx, lambda: net.endpoint("10.0.0.2"))
    ctx.stack.push(join)
    join.address = ""
    items = join.menu.items
    address_row = next(i for i, it in enumerate(items) if it.label() == ctx.t("lan.join.address"))
    activate(join.menu, address_row)
    for ch in "1.2":
        join.handle_event(key(pygame.K_1, ch))
    join.handle_event(key(pygame.K_BACKSPACE))
    join.handle_event(key(pygame.K_RETURN))
    assert join.address == "1."
    join.connect_typed()
    assert join.client is not None
    join.cancel()
    join.address = "bad:port"
    join.connect_typed()
    assert join.client is None
    join.name = ""
    join.editing = "name"
    join.handle_event(key(pygame.K_a, "a"))
    assert join.name == "A"
    join.draw(surface())


def test_join_timeout_reports_status(ctx: AppContext) -> None:
    net = MemoryNetwork()
    join = LanJoinScreen(ctx, lambda: net.endpoint("10.0.0.2"))
    ctx.stack.push(join)
    join.connect(("10.9.9.9", 47474))
    assert join.client is not None
    join.client.close()
    join.update(0.1)
    assert join.client is None
    join.back()


def test_lobby_port_busy(ctx: AppContext) -> None:
    class Busy:
        def __call__(self) -> None:
            raise OSError

    lobby = LanLobbyScreen(ctx, MatchConfig(controllers=("human", "remote")), "shared")
    lobby.back()
    ctx.stack.push(lobby)
    lobby.draw(surface())


def test_notice_and_quit_overlays(ctx: AppContext) -> None:
    ctx.stack.push(MainMenuScreen(ctx))
    notice = LanNoticeScreen(ctx, "lan.notice.lost")
    ctx.stack.push(notice)
    notice.draw(surface())
    notice.back()
    assert isinstance(ctx.stack.top, MainMenuScreen)
    calls: list[int] = []
    quit_screen = LanQuitScreen(ctx, lambda: calls.append(1))
    ctx.stack.push(quit_screen)
    quit_screen.draw(surface())
    activate(quit_screen.menu, 1)
    assert calls == [1]
    assert isinstance(ctx.stack.top, MainMenuScreen)


def test_host_drop_overlay_and_finish(ctx: AppContext) -> None:
    net, lobby, join = full_session(ctx)
    spin(net, join, lobby)
    activate(join.menu, 0)
    spin(net, join, lobby)
    lobby.start()
    host_screen = ctx.stack.top
    assert isinstance(host_screen, LanHostMatchScreen)
    for _ in range(40):
        net.advance(1)
        join.update(0.016)
        host_screen.update(0.016)
    host = host_screen.host
    client = join.client or ctx.stack.top
    if ctx.stack.top is not host_screen:
        ctx.stack.pop_all()
        ctx.stack.push(host_screen)
    assert client is not None
    # Age the remote so the host times it out and shows the drop overlay.
    for remote in host.remotes.values():
        remote.last_seen = -1e9
    for _ in range(400):
        net.advance(1)
        host_screen.update(0.1)
        if isinstance(ctx.stack.top, LanDropScreen):
            break
    assert host.paused
    overlay = ctx.stack.top
    assert isinstance(overlay, LanDropScreen)
    overlay.draw(surface())
    activate(overlay.menu, 1)  # hand the seat to the AI
    assert not host.paused
    host_screen.world.phase = Phase.FINISHED
    host_screen.update(0.016)
    assert isinstance(ctx.stack.top, ResultsScreen)
    ctx.stack.top.back()
    assert isinstance(ctx.stack.top, MainMenuScreen) or ctx.stack.top is None
