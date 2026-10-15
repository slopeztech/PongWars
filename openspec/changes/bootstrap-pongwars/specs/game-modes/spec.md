## ADDED Requirements

### Requirement: Pluggable game modes
The system SHALL define game modes as classes registered in a `Registry`, each providing a win condition, optional per-tick rules and a display name, so that new modes can be added without editing core code.

#### Scenario: Register new mode
- **WHEN** a new mode class is decorated with `@register_mode("id")`
- **THEN** it appears in the mode list and can be selected in `MatchConfig`

### Requirement: Built-in modes
The system SHALL include at least: **Classic** (first to N points, win by 2 optional), **Timed** (most points when time ends, with sudden death on tie), **Survival** (limited lives), and **King of the Table** (points only while holding a zone).

#### Scenario: First to N
- **WHEN** a player reaches N points in Classic mode
- **THEN** the match ends with that player as winner

#### Scenario: Timed tie
- **WHEN** time ends with equal scores in Timed mode
- **THEN** sudden death starts and the next goal wins

### Requirement: Mode-specific options
Each mode SHALL declare its configurable options (name, type, range, default) so the UI builds its settings form automatically.

#### Scenario: Auto-generated form
- **WHEN** the user selects a mode with a "points to win" option
- **THEN** the setup screen shows a numeric control limited to the declared range
