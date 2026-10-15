## ADDED Requirements

### Requirement: Translation catalogs
The system SHALL load user-visible text from per-language JSON catalogs (`data/locales/<lang>.json`) addressed by stable dotted keys, with English as the source language.

#### Scenario: Lookup
- **WHEN** the active language is `es` and key `menu.main.play` exists in the `es` catalog
- **THEN** the translator returns the Spanish text

#### Scenario: Fallback
- **WHEN** a key is missing in the active language
- **THEN** the English text is returned, and if also missing the key itself is returned without raising

### Requirement: Parameters and plurals
Translations SHALL support `{name}` placeholders and plural forms selected by count.

#### Scenario: Placeholder
- **WHEN** `"score.winner": "{player} wins!"` is translated with `player="P1"`
- **THEN** the result is `P1 wins!`

#### Scenario: Plural
- **WHEN** a key has `.one` and `.other` forms and the count is 1
- **THEN** the `.one` form is used

### Requirement: Domain and network emit keys, not text
The `domain` and `net` layers SHALL NOT contain user-visible prose; events, errors and status values MUST carry translation keys and parameters that the UI translates.

#### Scenario: Validation error
- **WHEN** a `MatchConfig` validation fails
- **THEN** the error exposes a key and parameters usable for translation

### Requirement: Language selection
The user SHALL be able to choose the language in settings; the choice MUST persist, default to the system locale when supported (else English), and be independent of the match configuration and of the remote peer's language.

#### Scenario: Switch language
- **WHEN** the user selects another language
- **THEN** all menus show it without restarting

### Requirement: Catalog consistency
A test SHALL verify that no catalog contains keys absent from the English catalog and that placeholders match the English ones.

#### Scenario: Unknown key
- **WHEN** a translated catalog contains a key not in English
- **THEN** the consistency test fails
