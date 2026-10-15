## ADDED Requirements

### Requirement: Screen flow
The system SHALL provide a screen stack/state machine: Title → Main menu → (Local 2P | 1 vs AI | LAN Host | LAN Join | Settings | Quit) → Match setup → Match → Results → back.

#### Scenario: Back navigation
- **WHEN** the user presses Esc in a sub-menu
- **THEN** the previous screen is shown

### Requirement: Match setup screen
The system SHALL let the user configure all `MatchConfig` fields (mode, arena, limits, extras, AI difficulty, controllers) with live preview of the arena, generated from the declared options.

#### Scenario: Start with config
- **WHEN** the user confirms the setup
- **THEN** a match starts with exactly the chosen configuration

### Requirement: Keyboard and gamepad navigation
All menus SHALL be navigable without a mouse.

#### Scenario: Navigate
- **WHEN** the user presses Down and Enter
- **THEN** the next item is selected and activated

### Requirement: HUD and pause
During a match the system SHALL show scores, timer, active effects and, in LAN, ping; and allow pausing (local games) with resume, settings, and quit.

#### Scenario: Pause
- **WHEN** the user presses Esc in a local match
- **THEN** the simulation stops and the pause menu appears

### Requirement: Settings
The user SHALL be able to change resolution/fullscreen, volume, visual effects and key mappings, persisted in the user config directory.

#### Scenario: Persist
- **WHEN** the user changes volume and restarts the game
- **THEN** the volume is retained

### Requirement: Results screen
After a match the system SHALL show a summary (scores, duration, stats) with options: rematch, change settings, main menu.

#### Scenario: Rematch
- **WHEN** the user selects "Rematch"
- **THEN** a new match starts with the same configuration
