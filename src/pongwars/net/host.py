"""@package pongwars.net.host
@brief Authoritative LAN host: owns the World, validates remote inputs, broadcasts snapshots.
"""

import contextlib
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import Enum

from pongwars.domain.config import MatchConfig
from pongwars.domain.events import Event
from pongwars.domain.world import FrameInputs, World
from pongwars.net import snapshot
from pongwars.net.codec import Codec, JsonCodec
from pongwars.net.protocol import (
    MAX_NAME,
    PROTOCOL_VERSION,
    REASON_FULL,
    REASON_STARTED,
    REASON_VERSION,
    Accept,
    Bye,
    Cosmetics,
    DiscoverReply,
    DiscoverRequest,
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

TIMEOUT = 5.0
SNAPSHOT_EVERY = 2
HEARTBEAT = 1.0
START_RESEND = 0.25
START_WAIT = 3.0
NAME_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
ROOM_NAME_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_. ")

LocalInput = Callable[[int], tuple[float, bool] | tuple[float, bool, bool]]


class HostState(Enum):
    """@brief Lifecycle of a host session."""

    LOBBY = "lobby"
    PLAYING = "playing"
    CLOSED = "closed"


@dataclass
class RemotePlayer:
    """@brief A connected client."""

    addr: Address
    name: str
    last_seen: float
    seq: int = -1
    move: float = 0.0
    fire: bool = False
    spin: bool = False
    ready: bool = False


def clean_name(raw: object) -> str:
    """@brief Reduce a player name to the characters the game font can draw.
    @param raw Untrusted value.
    @return Upper-case name of at most MAX_NAME characters ("PLAYER" when empty).
    """
    text = "".join(ch for ch in str(raw).upper() if ch in NAME_CHARS)[:MAX_NAME]
    return text or "PLAYER"


def clean_room_name(raw: object) -> str:
    """@brief Normalize a discovery room title to printable, bounded text."""
    text = "".join(ch for ch in str(raw).upper() if ch in ROOM_NAME_CHARS).strip()[:20]
    return text or "PONGWARS"


def _fit_cosmetics(values: list[int] | tuple[int, ...] | None, count: int, limit: int) -> list[int]:
    fitted = list(values or ())[:count]
    return [
        value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < limit else 0
        for value in fitted
    ] + [0] * (count - len(fitted))


def sanitize_move(value: object) -> float:
    """@brief Make an untrusted paddle intent safe for the simulation.
    @param value Raw value from the network.
    @return A finite number in [-1, 1] (0 for anything unusable).
    """
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        return 0.0
    return max(-1.0, min(1.0, float(value)))


class HostSession:
    """@brief Hosts one LAN match: lobby first, then the authoritative simulation."""

    def __init__(
        self,
        config: MatchConfig,
        name: str,
        transport: Transport,
        clock: Callable[[], float] = time.monotonic,
        codec: Codec | None = None,
        room_name: str | None = None,
        colors: list[int] | tuple[int, ...] | None = None,
        skins: list[int] | tuple[int, ...] | None = None,
    ) -> None:
        """@brief Open the lobby.
        @param config Match settings; seat 0 is the host, "remote" seats wait for clients.
        @param name Host player name.
        @param transport Datagram endpoint (already bound to the game port).
        @param clock Monotonic time source in seconds.
        @param codec Message codec (JSON by default).
        """
        self.config = config
        self.name = clean_name(name)
        self.room_name = clean_room_name(room_name or name)
        self.transport = transport
        self.clock = clock
        self.codec = codec or JsonCodec()
        self.state = HostState.LOBBY
        self.world: World | None = None
        self.remotes: dict[int, RemotePlayer] = {}
        self.colors = _fit_cosmetics(colors, len(config.controllers), 8)
        self.skins = _fit_cosmetics(skins, len(config.controllers), 4)
        self.dropped: list[int] = []
        self.ai_seats: set[int] = set()
        self._seq = 0
        self._pending: list[Event] = []
        self._last_heartbeat = clock()
        self._start_time = 0.0
        self._last_start = 0.0

    @property
    def paused(self) -> bool:
        """@brief True while a remote player is missing and the match is frozen."""
        return self.state is HostState.PLAYING and bool(self.dropped)

    @property
    def open_seats(self) -> list[int]:
        """@brief Remote seats still waiting for a client."""
        return [
            s
            for s, kind in enumerate(self.config.controllers)
            if kind == "remote" and s not in self.remotes
        ]

    def names(self) -> list[str]:
        """@brief Player name per seat ("" for an empty seat)."""
        result = [""] * len(self.config.controllers)
        result[0] = self.name
        for seat, remote in self.remotes.items():
            result[seat] = remote.name
        return result

    def is_remote(self, seat: int) -> bool:
        """@brief Whether a seat is driven by a network client.
        @param seat Seat index.
        @return True for connected or temporarily missing remote players.
        """
        return seat in self.remotes and seat not in self.ai_seats

    def _send(self, message: Message, addr: Address) -> None:
        with contextlib.suppress(ProtocolError):
            self.transport.send(self.codec.encode(message), addr)

    def _broadcast_remotes(self, message: Message) -> None:
        for remote in self.remotes.values():
            self._send(message, remote.addr)

    def _receive(self) -> list[tuple[Message, Address]]:
        out: list[tuple[Message, Address]] = []
        for data, addr in self.transport.poll():
            try:
                out.append((self.codec.decode(data), addr))
            except ProtocolError:
                continue
        return out

    def poll(self) -> None:
        """@brief Process incoming messages, heartbeats and timeouts (call every frame)."""
        if self.state is HostState.CLOSED:
            return
        now = self.clock()
        for message, addr in self._receive():
            self._handle(message, addr, now)
        self._check_timeouts(now)
        if self.state is HostState.LOBBY and now - self._last_heartbeat >= HEARTBEAT:
            self._last_heartbeat = now
            self._broadcast_remotes(self._roster())

    def _roster(self) -> Roster:
        return Roster(self.names(), self.colors.copy(), self.skins.copy())

    def set_cosmetics(self, seat: int, color: int | None = None, skin: int | None = None) -> None:
        if not 0 <= seat < len(self.colors):
            return
        if color is not None and isinstance(color, int) and not isinstance(color, bool) and 0 <= color < 8:
            self.colors[seat] = color
        if skin is not None and isinstance(skin, int) and not isinstance(skin, bool) and 0 <= skin < 4:
            self.skins[seat] = skin
        self._broadcast_remotes(self._roster())

    def _seat_of(self, addr: Address) -> int | None:
        for seat, remote in self.remotes.items():
            if remote.addr == addr:
                return seat
        return None

    def _handle(self, message: Message, addr: Address, now: float) -> None:
        if isinstance(message, DiscoverRequest):
            if self.state is HostState.LOBBY:
                self._reply_discovery(addr)
            return
        if isinstance(message, Hello):
            self._on_hello(message, addr, now)
            return
        seat = self._seat_of(addr)
        if seat is None:
            return
        remote = self.remotes[seat]
        remote.last_seen = now
        if isinstance(message, Input):
            if message.seq > remote.seq:
                remote.seq = message.seq
                remote.move = sanitize_move(message.move)
                remote.fire = message.fire is True
                remote.spin = message.spin is True
        elif isinstance(message, Ping):
            self._send(Pong(message.ts), addr)
        elif isinstance(message, Ready):
            remote.ready = True
        elif isinstance(message, Cosmetics) and self.state is HostState.LOBBY:
            self.set_cosmetics(seat, message.color, message.skin)
        elif isinstance(message, Bye):
            self._on_leave(seat)

    def _reply_discovery(self, addr: Address) -> None:
        reply = DiscoverReply(
            self.name,
            self.config.mode,
            self.config.arena,
            self.transport.local_addr[1],
            len(self.config.controllers),
            len(self.remotes),
            PROTOCOL_VERSION,
            self.room_name,
        )
        self._send(reply, addr)

    def _on_hello(self, hello: Hello, addr: Address, now: float) -> None:
        if hello.version != PROTOCOL_VERSION:
            self._send(Reject(REASON_VERSION), addr)
            return
        seat = self._seat_of(addr)
        if seat is None:
            if self.state is HostState.LOBBY:
                free = self.open_seats
            else:
                free = [s for s in self.dropped if s not in self.ai_seats]
            if not free:
                self._send(
                    Reject(REASON_FULL if self.state is HostState.LOBBY else REASON_STARTED), addr
                )
                return
            seat = free[0]
            self.remotes[seat] = RemotePlayer(addr, clean_name(hello.name), now)
            if seat in self.dropped:
                self.dropped.remove(seat)
        else:
            self.remotes[seat].last_seen = now
        self._send(Accept(seat, self.config.to_json()), addr)
        if self.state is HostState.PLAYING:
            self.remotes[seat].ready = False
            self._send(self._start_message(), addr)
        else:
            self._broadcast_remotes(self._roster())

    def _on_leave(self, seat: int) -> None:
        if self.state is HostState.LOBBY:
            self.remotes.pop(seat, None)
            self._broadcast_remotes(self._roster())
        elif seat not in self.dropped:
            self.dropped.append(seat)

    def _check_timeouts(self, now: float) -> None:
        for seat, remote in list(self.remotes.items()):
            if seat in self.ai_seats or seat in self.dropped:
                continue
            if now - remote.last_seen >= TIMEOUT:
                self._on_leave(seat)

    def start(self) -> World:
        """@brief Close the lobby and start the match; empty remote seats become AI.
        @return The authoritative world.
        """
        controllers = tuple(
            "human" if s == 0 else ("remote" if s in self.remotes else "ai")
            for s in range(len(self.config.controllers))
        )
        self.config = replace(self.config, controllers=controllers)
        self.world = World(self.config)
        self.state = HostState.PLAYING
        self._start_time = self._last_start = self.clock()
        self._broadcast_remotes(self._start_message())
        return self.world

    def _start_message(self) -> Start:
        return Start(self.config.to_json(), self.colors.copy(), self.skins.copy())

    def resolve(self, action: str) -> None:
        """@brief Decide what to do about missing players.
        @param action "ai" hands their seats to the AI; "wait" keeps waiting.
        """
        if action == "ai":
            for seat in self.dropped:
                self.ai_seats.add(seat)
            self.dropped = []

    def step(self, local: LocalInput) -> list[Event]:
        """@brief Advance the match one tick (a no-op while paused or waiting for clients).
        @param local Supplies (move, fire) for every seat that is not remote.
        @return Events of this tick.
        @throws RuntimeError If the match has not been started.
        """
        if self.world is None or self.state is not HostState.PLAYING:
            raise RuntimeError("match not started")
        now = self.clock()
        if self._waiting_for_clients(now):
            if now - self._last_start >= START_RESEND:
                self._last_start = now
                for remote in self.remotes.values():
                    if not remote.ready:
                        self._send(self._start_message(), remote.addr)
            return []
        if self.paused:
            self._send_snapshot([])
            return []
        moves: list[float] = []
        fire: list[bool] = []
        spin: list[bool] = []
        for seat in range(self.world.players):
            if self.is_remote(seat):
                remote = self.remotes[seat]
                moves.append(remote.move)
                fire.append(remote.fire)
                spin.append(remote.spin)
            else:
                local_input = local(seat)
                move, shot = local_input[:2]
                spinning = local_input[2] if len(local_input) > 2 else False
                moves.append(move)
                fire.append(shot)
                spin.append(spinning)
        events = self.world.step(FrameInputs(tuple(moves), tuple(fire), tuple(spin)))
        self._pending.extend(events)
        finished = self.world.phase.value == "finished"
        if self.world.tick % SNAPSHOT_EVERY == 0 or finished or events:
            self._send_snapshot(self._pending)
            self._pending = []
        return events

    def _waiting_for_clients(self, now: float) -> bool:
        if now - self._start_time >= START_WAIT:
            return False
        return any(not r.ready for s, r in self.remotes.items() if s not in self.dropped)

    def _send_snapshot(self, events: list[Event]) -> None:
        if self.world is None:
            return
        self._seq += 1
        message = Snapshot(
            self._seq,
            snapshot.capture(self.world),
            snapshot.events_to_list(events),
            self.paused,
        )
        for remote in self.remotes.values():
            self._send(message, remote.addr)

    def close(self, reason: str = "closed") -> None:
        """@brief Tell the clients goodbye and release the transport.
        @param reason Free text sent to the clients.
        """
        if self.state is HostState.CLOSED:
            return
        self._broadcast_remotes(Bye(reason))
        self.state = HostState.CLOSED
        self.transport.close()
