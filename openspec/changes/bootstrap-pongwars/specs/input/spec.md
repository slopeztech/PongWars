## ADDED Requirements

### Requirement: Abstract input
Controllers (keyboard, gamepad, AI, network) SHALL produce the same `PlayerInput` value (move axis, action buttons) per tick, so the simulation is agnostic to the device.

#### Scenario: Interchangeable controllers
- **WHEN** a player's controller is swapped from keyboard to AI
- **THEN** the world consumes the same `PlayerInput` type with no code change

### Requirement: Two players on one keyboard
The system SHALL allow two players on the same keyboard with non-conflicting default mappings (P1: W/S + Space, P2: Up/Down + Enter) and SHALL handle simultaneous key presses.

#### Scenario: Simultaneous movement
- **WHEN** P1 holds W and P2 holds Up at the same time
- **THEN** both paddles move up

### Requirement: Remapping
The user SHALL be able to remap keys and the mapping SHALL persist between sessions; conflicting bindings between players MUST be rejected.

#### Scenario: Conflict
- **WHEN** the user assigns a key already used by the other player
- **THEN** the change is rejected with a message

### Requirement: Gamepad support
The system SHALL support gamepads (axis or d-pad for movement, buttons for extras) when connected, with hot-plug.

#### Scenario: Hot-plug
- **WHEN** a gamepad is connected during the menu
- **THEN** it becomes selectable as a controller

## ADDED Requirements

### Requirement: Multi-seat support
The input layer SHALL support 2 to 4 seats, including horizontal paddles for the top and bottom seats.

#### Scenario: Four seats
- **WHEN** a 4-player arena is active
- **THEN** all four seats are drawn or polled independently
