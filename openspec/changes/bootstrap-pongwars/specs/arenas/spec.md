## ADDED Requirements

### Requirement: Data-driven arenas
The system SHALL load arenas from data files (TOML/JSON) declaring table size, walls, theme (palette, decoration) and obstacle list, validated on load.

#### Scenario: Invalid arena file
- **WHEN** an arena file has an obstacle outside the table bounds
- **THEN** loading fails with an error that names the file and obstacle

### Requirement: Obstacles
The system SHALL support static obstacles (solid blocks, bumpers that add speed), moving obstacles (patrol path) and destructible obstacles (hit points), all interacting with the ball and projectiles.

#### Scenario: Bumper
- **WHEN** the ball hits a bumper
- **THEN** it bounces and its speed increases by the bumper factor (capped at max speed)

#### Scenario: Destructible
- **WHEN** a destructible obstacle's hit points reach 0
- **THEN** it is removed and an event is emitted

### Requirement: Fair layouts
Obstacle layouts SHALL be symmetric by default so neither player is favoured, and no layout may fully block the ball's path between goals.

#### Scenario: Symmetry check
- **WHEN** a built-in arena is validated
- **THEN** mirroring its obstacles across the table axis yields the same set

### Requirement: Built-in arenas
The system SHALL ship at least 5 arenas: Classic (empty), Pillars, Bumpers, Moving Walls and Fortress (destructible).

#### Scenario: Arena list
- **WHEN** the arena selector opens
- **THEN** all built-in arenas are listed with a preview

### Requirement: Player count per arena
Each arena SHALL declare a player count of 2, 3 or 4. Seats are placed left, right, top, bottom in that order; sides without a seat (or whose player was eliminated) are reflective walls. A match SHALL require exactly one controller per seat.

#### Scenario: Controller mismatch
- **WHEN** a match is created with a controller count different from the arena's player count
- **THEN** creation fails with a translated configuration error

#### Scenario: Scoring with three or four players
- **WHEN** the ball leaves through a seat's goal
- **THEN** the last player to touch the ball scores, unless that player is the one conceding, in which case nobody scores