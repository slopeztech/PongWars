## ADDED Requirements

### Requirement: Event-driven sound effects
The audio layer SHALL play sound effects in response to domain events (hit, wall, goal, pickup, effect apply, win), mapped by data.

#### Scenario: Goal sound
- **WHEN** a `GoalScored` event arrives
- **THEN** the goal sound is played once

### Requirement: Chiptune assets generated or free
Sounds and music SHALL be synthesized by code (square/triangle/noise waves) or come from free-licensed assets listed in `assets/LICENSES.md`.

#### Scenario: License file
- **WHEN** an external audio asset is added
- **THEN** `assets/LICENSES.md` lists its source and license

### Requirement: Volume control and graceful degradation
The system SHALL expose master/music/sfx volume and MUST run normally (silently) when no audio device is available.

#### Scenario: No audio device
- **WHEN** the mixer fails to initialize
- **THEN** the game starts without sound and logs a warning
