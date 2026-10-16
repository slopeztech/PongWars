# Spec Delta

## Purpose

Help LAN players find the intended match and coordinate player appearance in a shared lobby before a match begins.

## ADDED Requirements

### Requirement: Named LAN rooms
The host SHALL assign each waiting LAN match a printable room name, and discovery results SHALL show that room name alongside the host and player occupancy.

#### Scenario: Find a named room
- **WHEN** a client scans for LAN matches
- **THEN** each discovered match displays its room name, host name, and joined-player count

#### Scenario: Use a default room name
- **WHEN** the host submits an empty room name
- **THEN** the match is still discoverable under a non-empty default room name

### Requirement: Shared pre-match lobby
After joining, every peer SHALL see the same roster of occupied and waiting seats, including each occupied player's selected paddle color and style.

#### Scenario: Join the lobby
- **WHEN** a client is accepted into an open remote seat before match start
- **THEN** the client enters the lobby and receives the current roster

#### Scenario: Reflect a joined player
- **WHEN** a client joins or leaves before match start
- **THEN** all connected peers see the updated seat occupancy

### Requirement: Player-selected LAN cosmetics
Each peer SHALL be able to select the paddle color and style for its own seat, and the host SHALL distribute the selected cosmetics to all peers and apply them when the match starts.

#### Scenario: Synchronize a cosmetic choice
- **WHEN** a client changes its color or style in the lobby
- **THEN** the host roster and every connected client's roster show the updated choice

#### Scenario: Apply lobby cosmetics
- **WHEN** the host starts the match
- **THEN** the host and clients render every player's selected color and style

### Requirement: Host-controlled lobby start
The host SHALL start a LAN match only after every configured remote seat is occupied, and only the host can start it.

#### Scenario: Wait for all configured clients
- **WHEN** at least one configured remote seat is still empty
- **THEN** the host cannot start the match

#### Scenario: Host starts a full lobby
- **WHEN** all configured remote seats are occupied and the host activates Start
- **THEN** the match starts for the host and all joined clients
