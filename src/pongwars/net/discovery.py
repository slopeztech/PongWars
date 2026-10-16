"""@package pongwars.net.discovery
@brief Finds LAN hosts by broadcasting a discovery request.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from pongwars.net.codec import Codec, JsonCodec
from pongwars.net.host import clean_name
from pongwars.net.protocol import (
    DEFAULT_PORT,
    PROTOCOL_VERSION,
    DiscoverReply,
    DiscoverRequest,
    ProtocolError,
)
from pongwars.net.transport import Address, Transport


@dataclass(frozen=True)
class HostInfo:
    """@brief A host found on the network."""

    name: str
    mode: str
    arena: str
    addr: Address
    players: int
    joined: int
    ping_ms: float
    room_name: str = ""


class Discovery:
    """@brief Broadcasts requests and collects the replies."""

    def __init__(
        self,
        transport: Transport,
        port: int = DEFAULT_PORT,
        clock: Callable[[], float] = time.monotonic,
        codec: Codec | None = None,
    ) -> None:
        """@brief Create a scanner.
        @param transport Datagram endpoint used to scan.
        @param port Game port hosts listen on.
        @param clock Monotonic time source in seconds.
        @param codec Message codec (JSON by default).
        """
        self.transport = transport
        self.port = port
        self.clock = clock
        self.codec = codec or JsonCodec()
        self.found: dict[Address, HostInfo] = {}
        self._sent = 0.0

    def scan(self) -> None:
        """@brief Broadcast a discovery request and forget stale results."""
        self._sent = self.clock()
        self.found.clear()
        data = self.codec.encode(DiscoverRequest(PROTOCOL_VERSION))
        self.transport.broadcast(data, self.port)

    def poll(self) -> list[HostInfo]:
        """@brief Collect replies received so far.
        @return All hosts found since the last scan(), sorted by name.
        """
        now = self.clock()
        for data, addr in self.transport.poll():
            try:
                reply = self.codec.decode(data)
            except ProtocolError:
                continue
            if not isinstance(reply, DiscoverReply) or reply.version != PROTOCOL_VERSION:
                continue
            host = (addr[0], reply.port)
            self.found[host] = HostInfo(
                clean_name(reply.name),
                str(reply.mode),
                str(reply.arena),
                host,
                int(reply.players),
                int(reply.joined),
                max(0.0, (now - self._sent) * 1000.0),
                str(reply.room_name),
            )
        return sorted(self.found.values(), key=lambda h: h.name)

    def close(self) -> None:
        """@brief Release the transport."""
        self.transport.close()
