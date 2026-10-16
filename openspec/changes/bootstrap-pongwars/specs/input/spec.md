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

### Requirement: Ball spin action
Each seat SHALL have a distinct spin action key. When held while the paddle is moving, it SHALL apply spin to the ball on its next paddle hit, alter the rebound angle, increase its speed, continuously curve its trajectory according to the spin direction and rate until its next bounce, set the direction and rate of the rendered ball rotation, and use an impact sound distinct from a normal paddle hit. LAN input messages SHALL carry the spin action.

#### Scenario: Spin on paddle impact
- **WHEN** a player moves their paddle and presses the spin key as the ball hits it
- **THEN** the ball rebounds faster, follows a curved path in the spin direction until it bounces again, and plays the spin-hit sound

### Requirement: Match countdown
The game SHALL show 3-2-1 before the first serve of a new match, with each number displayed for half a second.

#### Scenario: Countdown before a new match
- **WHEN** a new match starts
- **THEN** the display counts down from 3 to 1 below the arena in 30 simulation ticks per number before the ball is served
