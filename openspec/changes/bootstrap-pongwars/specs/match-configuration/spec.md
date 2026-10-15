## ADDED Requirements

### Requirement: Immutable serializable match configuration
The system SHALL represent every match setting (mode, arena, score/time limit, enabled extras and frequency, AI difficulty, controller type per player, seed) in a single immutable `MatchConfig` that round-trips through JSON without loss.

#### Scenario: Round trip
- **WHEN** a `MatchConfig` is serialized to JSON and deserialized
- **THEN** the result equals the original

### Requirement: Validation
The system SHALL reject invalid configurations (unknown mode/arena id, non-positive limits, both players on the same input device) with a descriptive error before a match starts.

#### Scenario: Unknown arena
- **WHEN** a config references an arena id that is not registered
- **THEN** validation fails and the error names the invalid field

### Requirement: Presets
The system SHALL ship named presets (e.g. "Classic", "Chaos", "Duel 1v1 AI") and allow the user to save and load custom presets from the user config directory.

#### Scenario: Load preset
- **WHEN** the user selects the "Chaos" preset
- **THEN** all fields of that preset populate the configuration screen

### Requirement: Defaults and versioning
The system SHALL provide defaults for every field and include a schema version so old saved files can be migrated or rejected cleanly.

#### Scenario: Old version
- **WHEN** a saved file has an older schema version
- **THEN** it is migrated or an explicit error is shown, never a crash
