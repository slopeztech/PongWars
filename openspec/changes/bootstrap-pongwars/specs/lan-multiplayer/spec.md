## ADDED Requirements

### Requirement: Host-authoritative architecture
In LAN play one peer (host) SHALL run the authoritative simulation; the client SHALL send inputs and receive state snapshots, and MUST NOT be able to change the state except through inputs.

#### Scenario: Client cheating
- **WHEN** a client sends malformed or out-of-range input
- **THEN** the host ignores or clamps it and the simulation stays valid

### Requirement: LAN discovery
The system SHALL discover hosts on the local network via UDP broadcast and list them (name, mode, arena, ping), and also allow direct connection by IP:port.

#### Scenario: Discover
- **WHEN** a host is waiting and a client opens the "Join LAN" screen
- **THEN** the host appears in the list within 2 seconds

### Requirement: Versioned protocol
All messages SHALL carry a protocol version and type; peers with incompatible versions MUST refuse the connection with a clear message.

#### Scenario: Version mismatch
- **WHEN** a client with a different protocol version connects
- **THEN** the host rejects it with a `VersionMismatch` reason

### Requirement: Smooth gameplay
The client SHALL interpolate snapshots (sent at >= 30 Hz) to render smoothly, tolerate packet loss and reordering using sequence numbers, and display the current ping.

#### Scenario: Packet loss
- **WHEN** 10% of packets are lost in a simulated network
- **THEN** the match continues without desync or crash

### Requirement: Disconnection handling
The system SHALL detect timeouts (>= 5 s without packets), pause the match and offer to wait, return to the menu, or hand the slot to the AI.

#### Scenario: Client drops
- **WHEN** the client stops sending packets for 5 seconds
- **THEN** the host shows a disconnection prompt

### Requirement: Transport abstraction
Networking SHALL sit behind `Transport` and `Codec` interfaces, with an in-memory implementation for tests.

#### Scenario: Integration test without sockets
- **WHEN** a host and client are wired with the in-memory transport
- **THEN** a full match can be played in a test
