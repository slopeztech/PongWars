"""@package pongwars.net.protocol
@brief Wire messages of the LAN protocol (transport and encoding independent).
"""

from dataclasses import dataclass, field, fields
from typing import Any

PROTOCOL_VERSION = 6
DEFAULT_PORT = 47474
MAX_NAME = 10
REASON_VERSION = "VersionMismatch"
REASON_FULL = "Full"
REASON_STARTED = "Started"


class ProtocolError(ValueError):
    """@brief Raised for malformed, oversized or unknown network data."""


@dataclass(frozen=True)
class Message:
    """@brief Base class of every protocol message."""


@dataclass(frozen=True)
class Hello(Message):
    """@brief Client asks to join. @param version Protocol version. @param name Player name."""

    version: int
    name: str


@dataclass(frozen=True)
class Accept(Message):
    """@brief Host grants a seat. @param seat Assigned seat. @param config MatchConfig JSON."""

    seat: int
    config: str


@dataclass(frozen=True)
class Reject(Message):
    """@brief Host refuses a client. @param reason One of the REASON_* constants."""

    reason: str


@dataclass(frozen=True)
class Roster(Message):
    """@brief Lobby state with player cosmetics."""

    names: list[str]
    colors: list[int] = field(default_factory=list)
    skins: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class Cosmetics(Message):
    """@brief A client selects the color and paddle style for its seat."""

    color: int
    skin: int


@dataclass(frozen=True)
class Start(Message):
    """@brief Match config and final lobby cosmetics."""

    config: str
    colors: list[int] = field(default_factory=list)
    skins: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class Ready(Message):
    """@brief Client has built its match and awaits snapshots."""


@dataclass(frozen=True)
class Input(Message):
    """@brief Client controls. @param seq Counter. @param move Intent. @param fire Fire.
    @param spin Spin button.
    """

    seq: int
    move: float
    fire: bool
    spin: bool = False


@dataclass(frozen=True)
class Snapshot(Message):
    """@brief World state. @param seq Increasing counter. @param state Captured world.
    @param events Events since the previous snapshot. @param paused Host is waiting for a player.
    """

    seq: int
    state: dict[str, Any]
    events: list[Any]
    paused: bool


@dataclass(frozen=True)
class Ping(Message):
    """@brief Latency probe. @param ts Sender's clock value, echoed back."""

    ts: float


@dataclass(frozen=True)
class Pong(Message):
    """@brief Latency reply. @param ts Echoed Ping value."""

    ts: float


@dataclass(frozen=True)
class Bye(Message):
    """@brief Orderly disconnect. @param reason Free text."""

    reason: str


@dataclass(frozen=True)
class DiscoverRequest(Message):
    """@brief Broadcast looking for hosts. @param version Protocol version."""

    version: int


@dataclass(frozen=True)
class DiscoverReply(Message):
    """@brief A host announces itself.
    @param name Host player name. @param mode Game mode. @param arena Arena.
    @param port Game port. @param players Seats in the arena. @param joined Remote players joined.
    @param version Protocol version. @param room_name User-facing room name.
    """

    name: str
    mode: str
    arena: str
    port: int
    players: int
    joined: int
    version: int
    room_name: str = ""


MESSAGE_TYPES: dict[str, type[Message]] = {
    cls.__name__: cls
    for cls in (
        Hello,
        Accept,
        Reject,
        Roster,
        Start,
        Cosmetics,
        Ready,
        Input,
        Snapshot,
        Ping,
        Pong,
        Bye,
        DiscoverRequest,
        DiscoverReply,
    )
}


def to_dict(message: Message) -> dict[str, Any]:
    """@brief Flatten a message into a JSON-friendly dict with a type tag.
    @param message Message to convert.
    @return Dict with key "t" plus the fields.
    """
    data = {f.name: getattr(message, f.name) for f in fields(message)}
    data["t"] = type(message).__name__
    return data


def from_dict(data: object) -> Message:
    """@brief Rebuild a message, validating tag and field set.
    @param data Decoded dict.
    @return The message.
    @throws ProtocolError If the tag is unknown or the fields do not match.
    """
    if not isinstance(data, dict):
        raise ProtocolError("message must be an object")
    kind = MESSAGE_TYPES.get(str(data.get("t")))
    if kind is None:
        raise ProtocolError("unknown message type")
    names = {f.name for f in fields(kind)}
    values = {k: v for k, v in data.items() if k != "t"}
    if set(values) != names:
        raise ProtocolError("bad message fields")
    return kind(**values)
