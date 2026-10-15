## ADDED Requirements

### Requirement: Fixed-step deterministic simulation
The system SHALL advance the match with a fixed time step of 60 Hz, independent of the render frame rate, and the simulation MUST be a deterministic function of the initial `MatchConfig` (incl. seed) and the sequence of per-tick inputs.

#### Scenario: Same inputs give same result
- **WHEN** two worlds are created with the same `MatchConfig` and receive the same input sequence for N ticks
- **THEN** their serialized states are identical after N ticks

#### Scenario: Render rate does not affect simulation
- **WHEN** the render loop runs at 30 FPS or 144 FPS for the same wall-clock time
- **THEN** the number of simulated ticks is the same (±1)

### Requirement: Domain layer isolation
The `domain` package SHALL NOT import `pygame`, sockets, or any I/O module.

#### Scenario: Import check
- **WHEN** the test suite inspects the imports of every module in `pongwars.domain`
- **THEN** no forbidden module is imported

### Requirement: Ball and paddle physics
The system SHALL simulate a ball moving in the table plane, bouncing on walls, paddles and obstacles, with the exit angle depending on the contact point on the paddle and with speed increasing per paddle hit up to a configurable maximum.

#### Scenario: Wall bounce
- **WHEN** the ball reaches a side wall
- **THEN** its normal velocity component is reversed and its speed is preserved

#### Scenario: Paddle contact point
- **WHEN** the ball hits the paddle edge instead of its center
- **THEN** the outgoing angle is larger than when hitting the center

#### Scenario: No tunneling
- **WHEN** the ball moves at maximum speed toward a thin paddle
- **THEN** the collision is still detected (swept collision)

### Requirement: Scoring and match end
The system SHALL award a point to a player when the ball passes the opponent's goal line, then reset the ball (serve), and SHALL end the match when the active mode's win condition is met.

#### Scenario: Goal scored
- **WHEN** the ball crosses a goal line
- **THEN** the opposing player's score increases by 1 and a serve starts after a configurable delay

### Requirement: Domain events
The simulation SHALL emit typed events (hit, goal, pickup, effect applied, match end) consumed by audio, render and UI without those layers mutating the world.

#### Scenario: Event on goal
- **WHEN** a goal is scored
- **THEN** a `GoalScored` event is emitted exactly once for that tick

### Requirement: N-player simulation
The simulation SHALL support 2 to 4 paddles; top and bottom paddles move along the horizontal axis. Survival mode eliminates a player at zero lives and turns their goal into a wall.

#### Scenario: Elimination
- **WHEN** a player's lives reach 0 in survival mode
- **THEN** a player-eliminated event is emitted and the ball reflects off that side