"""@package pongwars.net.transport
@brief Datagram transports: real UDP and a deterministic in-memory network for tests.
"""

import contextlib
import errno
import random
import socket
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

Address = tuple[str, int]
RECV_SIZE = 65535


def local_ip() -> str:
    """@brief Best guess of this machine's LAN address (no packet is sent).
    @return A dotted IPv4 address, "127.0.0.1" when none can be found.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("10.255.255.255", 9))
        return str(probe.getsockname()[0])
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


class Transport(ABC):
    """@brief Unreliable, non-blocking datagram endpoint."""

    @property
    @abstractmethod
    def local_addr(self) -> Address:
        """@brief Address this endpoint is bound to."""

    @abstractmethod
    def send(self, data: bytes, addr: Address) -> None:
        """@brief Send a datagram (best effort; never raises on network errors).
        @param data Payload.
        @param addr Destination.
        """

    @abstractmethod
    def broadcast(self, data: bytes, port: int) -> None:
        """@brief Send a datagram to every host of the local network.
        @param data Payload.
        @param port Destination port.
        """

    @abstractmethod
    def poll(self) -> list[tuple[bytes, Address]]:
        """@brief Collect the datagrams received so far (never blocks).
        @return (payload, sender) pairs.
        """

    @abstractmethod
    def close(self) -> None:
        """@brief Release the endpoint."""


class UdpTransport(Transport):
    """@brief Transport over a non-blocking UDP socket."""

    def __init__(self, port: int = 0, host: str = "0.0.0.0") -> None:  # noqa: S104
        """@brief Bind the socket.
        @param port Local port (0 picks a free one).
        @param host Local interface.
        @throws OSError If the port cannot be bound.
        """
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._sock.setblocking(False)
        self._sock.bind((host, port))

    @property
    def local_addr(self) -> Address:
        """@brief Address this endpoint is bound to."""
        host, port = self._sock.getsockname()[:2]
        return str(host), int(port)

    def send(self, data: bytes, addr: Address) -> None:
        """@brief Send a datagram.
        @param data Payload.
        @param addr Destination.
        """
        with contextlib.suppress(OSError):
            self._sock.sendto(data, addr)

    def broadcast(self, data: bytes, port: int) -> None:
        """@brief Send to the limited broadcast address.
        @param data Payload.
        @param port Destination port.
        """
        self.send(data, ("255.255.255.255", port))

    def poll(self) -> list[tuple[bytes, Address]]:
        """@brief Collect received datagrams.
        @return (payload, sender) pairs.
        """
        packets: list[tuple[bytes, Address]] = []
        while True:
            try:
                data, sender = self._sock.recvfrom(RECV_SIZE)
            except BlockingIOError:
                break
            except OSError as exc:
                # Windows reports ICMP "port unreachable" of earlier sends as a reset.
                if exc.errno in (errno.EBADF, errno.ENOTSOCK):
                    break
                continue
            packets.append((data, (str(sender[0]), int(sender[1]))))
        return packets

    def close(self) -> None:
        """@brief Close the socket."""
        self._sock.close()


@dataclass
class _Queued:
    due: int
    data: bytes
    sender: Address


@dataclass
class MemoryNetwork:
    """@brief Simulated network: seeded packet loss, latency and reordering.

    Time only moves when advance() is called, so tests are fully deterministic.
    @param loss Probability in [0, 1) of dropping each datagram.
    @param latency Delay in steps.
    @param jitter Extra random delay in steps (causes reordering).
    @param seed Random seed.
    """

    loss: float = 0.0
    latency: int = 0
    jitter: int = 0
    seed: int = 0
    now: int = 0
    _ports: dict[Address, "MemoryTransport"] = field(default_factory=dict)
    _next_port: int = 40000

    def __post_init__(self) -> None:
        """@brief Seed the random source."""
        self._rng = random.Random(self.seed)  # noqa: S311

    def endpoint(self, host: str, port: int = 0) -> "MemoryTransport":
        """@brief Create an endpoint on the network.
        @param host Fake IP address.
        @param port Port (0 picks a free one).
        @return The transport.
        """
        if port == 0:
            self._next_port += 1
            port = self._next_port
        transport = MemoryTransport(self, (host, port))
        self._ports[(host, port)] = transport
        return transport

    def advance(self, steps: int = 1) -> None:
        """@brief Move simulated time forward.
        @param steps Number of steps.
        """
        self.now += steps

    def _deliver(self, data: bytes, sender: Address, target: "MemoryTransport") -> None:
        if self._rng.random() < self.loss:
            return
        delay = self.latency + (self._rng.randint(0, self.jitter) if self.jitter else 0)
        target.queue.append(_Queued(self.now + delay, data, sender))

    def send(self, data: bytes, sender: Address, addr: Address) -> None:
        """@brief Route a datagram to one endpoint.
        @param data Payload.
        @param sender Source address.
        @param addr Destination address.
        """
        target = self._ports.get(addr)
        if target is not None:
            self._deliver(data, sender, target)

    def broadcast(self, data: bytes, sender: Address, port: int) -> None:
        """@brief Route a datagram to every other endpoint bound to a port.
        @param data Payload.
        @param sender Source address.
        @param port Destination port.
        """
        for addr, target in self._ports.items():
            if addr[1] == port and addr != sender:
                self._deliver(data, sender, target)


class MemoryTransport(Transport):
    """@brief Endpoint of a MemoryNetwork."""

    def __init__(self, network: MemoryNetwork, addr: Address) -> None:
        """@brief Create the endpoint (use MemoryNetwork.endpoint()).
        @param network Owning network.
        @param addr Bound address.
        """
        self._network = network
        self._addr = addr
        self.queue: list[_Queued] = []

    @property
    def local_addr(self) -> Address:
        """@brief Bound address."""
        return self._addr

    def send(self, data: bytes, addr: Address) -> None:
        """@brief Send a datagram.
        @param data Payload.
        @param addr Destination.
        """
        self._network.send(data, self._addr, addr)

    def broadcast(self, data: bytes, port: int) -> None:
        """@brief Broadcast a datagram.
        @param data Payload.
        @param port Destination port.
        """
        self._network.broadcast(data, self._addr, port)

    def poll(self) -> list[tuple[bytes, Address]]:
        """@brief Collect datagrams whose delivery time has come.
        @return (payload, sender) pairs.
        """
        now = self._network.now
        ready = sorted((q for q in self.queue if q.due <= now), key=lambda q: q.due)
        self.queue = [q for q in self.queue if q.due > now]
        return [(q.data, q.sender) for q in ready]

    def close(self) -> None:
        """@brief Detach from the network."""
        self._network._ports.pop(self._addr, None)
