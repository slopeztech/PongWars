# Spec Delta

## Purpose

Make the main menu easier to navigate and let players continue with their previous match configuration without configuring it again.

## ADDED Requirements

### Requirement: Grouped main menu
The main menu SHALL offer one VS entry for local and AI matches, one LAN entry that opens host/join choices, and one Help entry that opens game and LAN help choices.

#### Scenario: Open VS setup
- **WHEN** a player selects VS from the main menu
- **THEN** the match setup opens with the available local and AI controller choices

#### Scenario: Open LAN choices
- **WHEN** a player selects LAN from the main menu
- **THEN** a LAN submenu offers hosting and joining

#### Scenario: Open help choices
- **WHEN** a player selects Help from the main menu
- **THEN** a help submenu offers the game guide and LAN guide

### Requirement: Remember the last match setup
When a player starts a local or LAN-hosted match, the system SHALL persist that setup and restore its valid values in the next match setup.

#### Scenario: Restore match choices
- **WHEN** a player starts a match with selected mode, arena, controllers, difficulty, extras, view, and mode options, then opens setup again
- **THEN** those choices are selected by default

#### Scenario: Restore LAN room name
- **WHEN** a player starts a named LAN match and opens LAN setup again
- **THEN** the previous room name is selected by default

#### Scenario: Ignore invalid saved choices
- **WHEN** a saved match choice is unknown or outside its allowed range
- **THEN** setup uses a valid default for that choice and remains usable
