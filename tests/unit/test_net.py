"""LAN networking tests: codec, snapshots, host/client sessions over a memory network."""

import socket
import zlib
from typing import Any

import pytest

from pongwars.domain.config import MatchConfig
from pongwars.domain.events import Goal, PaddleHit
from pongwars.domain.world import Phase, World
from pongwars.net import snapshot
from pongwars.net.client import ClientSession, ClientState
from pongwars.net.codec import MAX_PACKET, JsonCodec
from pongwars.net.discovery import Discovery
from pongwars.net.host import HostSession, HostState, clean_name, sanitize_move
from pongwars.net.protocol import (
    PROTOCOL_VERSION,
    REASON_FULL,
    REASON_VERSION,
    Hello,
    Input,
    Ping,
    ProtocolError,
    Snapshot,
    from_dict,
    to_dict,
)
from pongwars.net.transport import MemoryNetwork, UdpTransport

PORT = 47474
CODEC = JsonCodec()


class Clock:
    """Manual clock shared by the sessions."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def make_pair(
    loss: float = 0.0, controllers: tuple[str, ...] = ("human", "remote")
) -> tuple[Clock, MemoryNetwork, HostSession, ClientSession]:
    clock = Clock()
    net = MemoryNetwork(loss=loss, seed=3)
    config = MatchConfig(controllers=controllers, seed=5)
    host = HostSession(config, "hoster", net.endpoint("10.0.0.1", PORT), clock)
    client = ClientSession(("10.0.0.1", PORT), "guest", net.endpoint("10.0.0.2"), clock)
    return clock, net, host, client


def pump(
    clock: Clock, net: MemoryNetwork, host: HostSession, client: ClientSession, n: int = 1
) -> None:
    for _ in range(n):
        clock.now += 1 / 60
        net.advance()
        host.poll()
        client.poll()


def play(
    clock: Clock,
    net: MemoryNetwork,
    host: HostSession,
    client: ClientSession,
    ticks: int,
    move: float = 0.0,
) -> None:
    for _ in range(ticks):
        pump(clock, net, host, client)
        client.send_input(move, False)
        host.step(lambda seat: (0.0, False))
        client.interpolate()


def test_codec_round_trip_and_errors() -> None:
    message = Input(3, 0.5, True)
    assert CODEC.decode(CODEC.encode(message)) == message
    assert from_dict(to_dict(message)) == message
    for bad in (b"", b"garbage", zlib.compress(b"[1,2]"), zlib.compress(b'{"t":"Nope"}')):
        with pytest.raises(ProtocolError):
            CODEC.decode(bad)
    with pytest.raises(ProtocolError):
        CODEC.decode(zlib.compress(b"x" * (MAX_PACKET * 100)))
    with pytest.raises(ProtocolError):
        from_dict({"t": "Input", "seq": 1})


def test_sanitizers() -> None:
    assert clean_name("ana maría!!!verylongname") == "ANAMARAVER"
    assert clean_name("") == "PLAYER"
    assert sanitize_move(float("nan")) == 0.0
    assert sanitize_move(9) == 1.0
    assert sanitize_move("x") == 0.0
    assert sanitize_move(True) == 0.0


def test_snapshot_round_trip() -> None:
    config = MatchConfig(arena="crossfire", controllers=("human",) * 4, extras=("shield", "cat"))
    world = World(config)
    mirror = World(config)
    from pongwars.domain.world import FrameInputs

    for _ in range(300):
        world.step(FrameInputs((0.3, -0.2, 0.1, 0.0), (True, True, False, False)))
    state = snapshot.capture(world)
    snapshot.apply(mirror, state)
    assert snapshot.capture(mirror) == state
    with pytest.raises(ProtocolError):
        snapshot.apply(mirror, {**state, "paddles": state["paddles"][:2]})
    with pytest.raises(ProtocolError):
        snapshot.apply(mirror, {"tick": 1})


def test_blend_and_events() -> None:
    a = {"balls": [[0, 0, 1, 1, None, None]], "paddles": [], "cats": [], "obs": []}
    b = {"balls": [[10, 0, 1, 1, None, None]], "paddles": [], "cats": [], "obs": []}
    assert snapshot.blend(a, b, 0.5)["balls"][0][0] == 5
    far = {"balls": [[100, 0, 1, 1, None, None]], "paddles": [], "cats": [], "obs": []}
    assert snapshot.blend(a, far, 0.5)["balls"][0][0] == 100
    assert snapshot.blend({}, b, 0.5) is b
    events = [PaddleHit(1), Goal(0, 1)]
    assert snapshot.events_from_list(snapshot.events_to_list(events)) == events
    assert snapshot.events_from_list([["Nope", 1], ["Goal"], 5]) == []


def test_join_and_start_flow() -> None:
    clock, net, host, client = make_pair()
    pump(clock, net, host, client, 10)
    assert client.state is ClientState.LOBBY
    assert client.seat == 1
    assert host.names() == ["HOSTER", "GUEST"]
    assert client.roster == ["HOSTER", "GUEST"]
    host.start()
    play(clock, net, host, client, 120)
    assert client.state.name == "PLAYING"
    assert client.world is not None
    assert client.world.tick > 60
    assert client.ping_ms >= 0


def test_remote_input_drives_paddle_and_cheats_are_ignored() -> None:
    clock, net, host, client = make_pair()
    pump(clock, net, host, client, 10)
    host.start()
    play(clock, net, host, client, 30)
    assert host.world is not None
    before = host.world.paddles[1].rect.cy
    play(clock, net, host, client, 40, move=1.0)
    assert host.world.paddles[1].rect.cy != before
    remote = host.remotes[1]
    host._handle(Input(10**6, float("nan"), True), client.transport.local_addr, clock.now)
    assert remote.move == 0.0
    host._handle(Input(5, 1.0, False), client.transport.local_addr, clock.now)
    assert remote.seq == 10**6
    host._handle(Input(10**6 + 1, 77.0, True), ("6.6.6.6", 1), clock.now)
    assert remote.move == 0.0


def test_version_mismatch_and_full() -> None:
    clock, net, host, client = make_pair()
    pump(clock, net, host, client, 10)
    spy = net.endpoint("10.0.0.9")
    spy.send(CODEC.encode(Hello(PROTOCOL_VERSION + 1, "old")), ("10.0.0.1", PORT))
    spy.send(CODEC.encode(Hello(PROTOCOL_VERSION, "late")), ("10.0.0.1", PORT))
    pump(clock, net, host, client, 3)
    replies = [CODEC.decode(d) for d, _ in spy.poll()]
    assert [getattr(r, "reason", None) for r in replies] == [REASON_VERSION, REASON_FULL]
    rejected = ClientSession(("10.0.0.1", PORT), "x", net.endpoint("10.0.0.5"), clock)
    rejected.transport.send(CODEC.encode(Hello(1, "x")), ("10.0.0.1", PORT))
    late = ClientSession(("10.0.0.1", PORT), "y", net.endpoint("10.0.0.6"), clock)
    for _ in range(10):
        pump(clock, net, host, late)
    assert late.state is ClientState.REJECTED
    assert late.reject_reason == REASON_FULL


def test_unfilled_remote_seat_becomes_ai() -> None:
    clock = Clock()
    net = MemoryNetwork()
    host = HostSession(
        MatchConfig(controllers=("human", "remote")), "h", net.endpoint("1.1.1.1", PORT), clock
    )
    host.start()
    assert host.config.controllers == ("human", "ai")
    assert host.state is HostState.PLAYING
    host.step(lambda seat: (0.0, False))
    host.close()
    assert host.state.name == "CLOSED"


def test_ten_percent_loss_still_plays_full_match() -> None:
    clock, net, host, client = make_pair(loss=0.1)
    pump(clock, net, host, client, 300)
    assert client.state is ClientState.LOBBY
    host.start()
    assert host.world is not None
    for _ in range(60 * 60 * 3):
        play(clock, net, host, client, 1)
        if host.world.phase is Phase.FINISHED:
            break
    play(clock, net, host, client, 20)
    assert client.state.name == "PLAYING"
    assert client.world is not None
    assert snapshot.capture(client.world)["scores"] == host.world.scores
    assert client.world.phase is host.world.phase


def test_client_timeout_and_host_drop_with_ai_handoff() -> None:
    clock, net, host, client = make_pair()
    pump(clock, net, host, client, 10)
    host.start()
    play(clock, net, host, client, 60)
    assert host.world is not None
    for _ in range(60 * 6):
        clock.now += 1 / 60
        net.advance()
        host.poll()
        assert host.step(lambda seat: (0.0, False)) == [] or not host.paused
    assert host.dropped == [1]
    assert host.paused
    tick = host.world.tick
    host.step(lambda seat: (0.0, False))
    assert host.world.tick == tick
    host.resolve("ai")
    assert not host.paused and not host.is_remote(1)
    host.step(lambda seat: (0.0, False))
    assert host.world.tick == tick + 1
    for _ in range(60 * 6):
        clock.now += 1 / 60
        net.advance()
        client.poll()
    assert client.state is ClientState.TIMEOUT


def test_rejoin_takes_over_dropped_seat() -> None:
    clock, net, host, client = make_pair()
    pump(clock, net, host, client, 10)
    host.start()
    play(clock, net, host, client, 60)
    client.close()
    pump(clock, net, host, client, 5)
    assert host.dropped == [1]
    again = ClientSession(("10.0.0.1", PORT), "guest", net.endpoint("10.0.0.7"), clock)
    for _ in range(300):
        clock.now += 1 / 60
        net.advance()
        host.poll()
        again.poll()
        again.send_input(0.0, False)
        host.step(lambda seat: (0.0, False))
    assert again.state is ClientState.PLAYING
    assert again.seat == 1
    assert not host.dropped


def test_host_close_notifies_client() -> None:
    clock, net, host, client = make_pair()
    pump(clock, net, host, client, 10)
    host.close()
    pump(clock, net, host, client, 3)
    assert client.state is ClientState.CLOSED


def test_lobby_leave_frees_seat_and_ping() -> None:
    clock, net, host, client = make_pair()
    pump(clock, net, host, client, 10)
    assert host.open_seats == []
    client.close()
    pump(clock, net, host, client, 3)
    assert host.open_seats == [1]
    spy = net.endpoint("10.0.0.8")
    spy.send(CODEC.encode(Ping(1.0)), ("10.0.0.1", PORT))
    pump(clock, net, host, client)
    assert spy.poll() == []


def test_garbage_and_stale_snapshots_are_ignored() -> None:
    clock, net, host, client = make_pair()
    pump(clock, net, host, client, 10)
    host.start()
    play(clock, net, host, client, 20)
    assert client.world is not None
    tick = client.world.tick
    stale = Snapshot(0, snapshot.capture(World(client.config or MatchConfig())), [], False)
    client._on_snapshot(stale, clock.now)
    assert client.world.tick == tick
    net.endpoint("10.0.0.99").send(b"junk", client.transport.local_addr)
    pump(clock, net, host, client, 2)
    assert client.state.name == "PLAYING"


def test_discovery_over_memory_network() -> None:
    clock = Clock()
    net = MemoryNetwork()
    host = HostSession(
        MatchConfig(controllers=("human", "remote")), "lan", net.endpoint("10.0.0.1", PORT), clock
    )
    scanner = Discovery(net.endpoint("10.0.0.3"), PORT, clock)
    scanner.scan()
    net.advance()
    host.poll()
    net.advance()
    found = scanner.poll()
    assert [(h.name, h.mode, h.joined) for h in found] == [("LAN", "classic", 0)]
    assert found[0].addr == ("10.0.0.1", PORT)
    host.start()
    scanner.scan()
    net.advance()
    host.poll()
    net.advance()
    assert scanner.poll() == []
    scanner.close()


def test_real_udp_loopback() -> None:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    server = UdpTransport(port, "127.0.0.1")
    other = UdpTransport(0, "127.0.0.1")
    other.send(b"hello", ("127.0.0.1", port))
    other.broadcast(b"x", port)
    got: list[Any] = []
    for _ in range(200):
        got += server.poll()
        if got:
            break
        socket.getaddrinfo("localhost", None)
    assert got and got[0][0] == b"hello"
    server.send(b"back", got[0][1])
    server.close()
    other.close()
