## ADDED Requirements

### Requirement: Single-player versus AI
The system SHALL offer a 1 vs AI mode where the AI controller uses the same `PlayerInput` interface and the same game rules as a human, with no access to hidden state.

#### Scenario: Fair information
- **WHEN** the AI decides its move
- **THEN** it only reads an `Observation` (visible positions, velocities, extras) and never the mutable world

### Requirement: Difficulty levels
The system SHALL provide at least four difficulties (Easy, Normal, Hard, Insane) defined by parameters: reaction delay, prediction error, max paddle speed and extra-usage skill.

#### Scenario: Ordering
- **WHEN** the AI of each difficulty plays 100 simulated matches against a fixed reference bot
- **THEN** the win rate is monotonically non-decreasing from Easy to Insane

### Requirement: Pluggable strategies
AI strategies SHALL be registered in a `Registry`; adding a strategy MUST NOT require changes in the core.

#### Scenario: Select strategy
- **WHEN** a config names a registered strategy
- **THEN** the match uses it

### Requirement: Obstacle and extra awareness
The AI SHALL predict ball trajectory including bounces on walls and obstacles, and SHALL be able to pick up and use extras according to its difficulty.

#### Scenario: Bounce prediction
- **WHEN** the ball will bounce on a wall before reaching the AI side
- **THEN** the predicted intercept point accounts for that bounce

### Requirement: Deterministic AI
Given the same seed and observations the AI SHALL produce the same inputs.

#### Scenario: Reproducible
- **WHEN** the same match is simulated twice with the same seed
- **THEN** the AI inputs are identical
