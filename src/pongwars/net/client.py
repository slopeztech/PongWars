"""@package pongwars.net.client
@brief LAN client: sends inputs, mirrors the host world from snapshots.
"""

import contextlib
import time
from collections.abc import Callable
from enum import Enum

from pongwars.domain.config import MatchConfig
from pongwars.domain.events import Event
from pongwars.domain.world import World
from pongwars.net import snapshot
from pongwars.net.codec import Codec, JsonCodec
from pongwars.net.host import TIMEOUT, clean_name
from pongwars.net.protocol import (
    PROTOCOL_VERSION,
    Accept,
    Bye,
    Hello,
    Input,
    Message,
    Ping,
    Pong,
    ProtocolError,
    Ready,
    Reject,
    Roster,
    Snapshot,
    Start,
)
from pongwars.net.transport import Address, Transport

HELLO_RETRY = 0.5
PING_EVERY = 1.0
INTERP_DELAY = 1 / 30


class ClientState(Enum):
    """@brief Lifecycle of a client session."""

    CONNECTING = "connecting"
    LOBBY = "lobby"
    PLAYING = "playing"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    CLOSED = "closed"


class ClientSession:
    """@brief One connection to a host."""

    def __init__(
        self,
        host: Address,
        name: str,
        transport: Transport,
        clock: Callable[[], float] = time.monotonic,
        codec: Codec | None = None,
    ) -> None:
        """@brief Start connecting.
        @param host Host address.
        @param name Player name.
        @param transport Datagram endpoint.
        @param clock Monotonic time source in seconds.
        @param codec Message codec (JSON by default).
        """
        self.host = host
        self.name = clean_name(name)
        self.transport = transport
        self.clock = clock
        self.codec = codec or JsonCodec()
        self.state = ClientState.CONNECTING
        self.seat = -1
        self.config: MatchConfig | None = None
        self.world: World | None = None
        self.roster: list[str] = []
        self.reject_reason = ""
        self.ping_ms = 0.0
        self.host_paused = False
        self._events: list[Event] = []
        self._seq = 0
        self._last_snapshot = -1
        self._prev: dict | None = None  # type: ignore[type-arg]
        self._curr: dict | None = None  # type: ignore[type-arg]
        self._curr_time = 0.0
        now = clock()
        self._last_rx = now
        self._last_hello = now - HELLO_RETRY
        self._last_ping = now

    @property
    def active(self) -> bool:
        """@brief Whether the connection is still usable."""
        return self.state in (ClientState.CONNECTING, ClientState.LOBBY, ClientState.PLAYING)

    def _send(self, message: Message) -> None:
        with contextlib.suppress(ProtocolError):
            self.transport.send(self.codec.encode(message), self.host)

    def poll(self) -> None:
        """@brief Process incoming messages, retries and timeouts (call every frame)."""
        if not self.active:
            return
        now = self.clock()
        for data, addr in self.transport.poll():
            if addr != self.host:
                continue
            try:
                message = self.codec.decode(data)
            except ProtocolError:
                continue
            self._last_rx = now
            self._handle(message, now)
            if not self.active:
                return
        if self.state is ClientState.CONNECTING and now - self._last_hello >= HELLO_RETRY:
            self._last_hello = now
            self._send(Hello(PROTOCOL_VERSION, self.name))
        if self.state is not ClientState.CONNECTING and now - self._last_ping >= PING_EVERY:
            self._last_ping = now
            self._send(Ping(now))
        if now - self._last_rx >= TIMEOUT:
            self.state = ClientState.TIMEOUT

    def _handle(self, message: Message, now: float) -> None:
        if isinstance(message, Accept):
            self._on_accept(message)
        elif isinstance(message, Reject):
            self.reject_reason = message.reason
            self.state = ClientState.REJECTED
        elif isinstance(message, Roster):
            self.roster = [str(n) for n in message.names]
        elif isinstance(message, Start):
            self._on_start(message)
        elif isinstance(message, Snapshot):
            self._on_snapshot(message, now)
        elif isinstance(message, Pong):
            self.ping_ms = max(0.0, (now - message.ts) * 1000.0)
        elif isinstance(message, Bye):
            self.state = ClientState.CLOSED

    def _on_accept(self, accept: Accept) -> None:
        try:
            config = MatchConfig.from_json(accept.config)
        except (ValueError, TypeError, KeyError):
            self.reject_reason = "BadConfig"
            self.state = ClientState.REJECTED
            return
        if not 0 <= accept.seat < len(config.controllers):
            self.reject_reason = "BadConfig"
            self.state = ClientState.REJECTED
            return
        self.seat = accept.seat
        self.config = config
        if self.state is ClientState.CONNECTING:
            self.state = ClientState.LOBBY

    def _on_start(self, start: Start) -> None:
        if self.seat < 0:
            return
        if self.world is None:
            try:
                config = MatchConfig.from_json(start.config)
                self.world = World(config)
            except (ValueError, TypeError, KeyError):
                return
            self.config = config
            self._last_snapshot = -1
            self._prev = self._curr = None
        self.state = ClientState.PLAYING
        self._send(Ready())

    def _on_snapshot(self, message: Snapshot, now: float) -> None:
        if self.state is not ClientState.PLAYING or self.world is None:
            return
        if message.seq <= self._last_snapshot:
            return
        try:
            snapshot.apply(self.world, message.state)
        except ProtocolError:
            return
        self._last_snapshot = message.seq
        self._prev, self._curr = self._curr, message.state
        self._curr_time = now
        self.host_paused = bool(message.paused)
        self._events.extend(snapshot.events_from_list(message.events))

    def send_input(self, move: float, fire: bool) -> None:
        """@brief Send this tick's paddle intent.
        @param move Paddle direction in [-1, 1].
        @param fire Whether the fire key is pressed.
        """
        if self.state is not ClientState.PLAYING:
            return
        self._seq += 1
        self._send(Input(self._seq, float(move), bool(fire)))

    def pop_events(self) -> list[Event]:
        """@brief Take the events received since the last call."""
        events, self._events = self._events, []
        return events

    def interpolate(self) -> None:
        """@brief Smooth the mirror world between the last two snapshots."""
        if self.world is None or self._curr is None or self._prev is None:
            return
        alpha = (self.clock() - self._curr_time) / max(INTERP_DELAY, 1e-6)
        try:
            snapshot.apply(self.world, snapshot.blend(self._prev, self._curr, alpha))
        except ProtocolError:
            return

    def close(self) -> None:
        """@brief Leave the match and release the transport."""
        if self.state is not ClientState.CLOSED:
            if self.active:
                self._send(Bye("left"))
            self.state = ClientState.CLOSED
        self.transport.close()
