## ADDED Requirements

### Requirement: Event-driven sound effects
The audio layer SHALL play sound effects in response to domain events (hit, wall, goal, pickup, effect apply, win), mapped by data.

#### Scenario: Goal sound
- **WHEN** a `GoalScored` event arrives
- **THEN** the goal sound is played once

### Requirement: Song files and jukebox
Music SHALL be loaded from text `.pws` song files (instruments, meter, tempo, notes; see `docs/music-format.md`), synthesized by a sequencer, and played by a jukebox that starts another song when one ends, separately for the menu and match contexts.

#### Scenario: Song ends
- **WHEN** the current song finishes
- **THEN** after 2-3 seconds of silence a random song of the same context starts, never the one that just played

#### Scenario: Now playing
- **WHEN** the main menu is shown while a song plays
- **THEN** its title and author are displayed

#### Scenario: Invalid song
- **WHEN** a `.pws` file has a bar whose length does not match the meter
- **THEN** it is rejected with the line number and the other songs still load

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
