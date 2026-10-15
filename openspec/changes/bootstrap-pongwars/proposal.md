## Why

PongWars is a new, wide-scope project (local and LAN multiplayer, AI, 8-bit
pseudo-3D rendering, extras, configurable matches, localization). To keep
AI-assisted code generation coherent and maintainable, we first fix the
contract: capabilities, architecture and a phased implementation plan.

## What Changes

- Define the layered architecture and repository structure.
- Specify the initial game capabilities (see *Capabilities*).
- Set quality standards: tests, typing, lint and Doxygen.
- Create the project skeleton (empty packages, tooling, docs).
- Publish a phased implementation plan in `tasks.md`.

## Capabilities

### New Capabilities

- `game-core`: loop, fixed step, match state and deterministic simulation.
- `match-configuration`: serializable `MatchConfig`, presets and validation.
- `game-modes`: registrable game modes (classic, first to N, timed, ...).
- `arenas`: data-defined arenas and obstacles.
- `rendering`: 8-bit pseudo-3D view.
- `input`: 2 players on one keyboard, remapping and gamepad.
- `ai-opponent`: AI opponent with several difficulties.
- `lan-multiplayer`: LAN play (authoritative host, discovery).
- `extras`: weapons, powers and penalties during a match.
- `ui-menus`: menus, match setup and screen flow.
- `audio`: chiptune effects and music.
- `localization`: multi-language support through translation catalogs.
- `engineering-quality`: structure, tests, typing and documentation.

### Modified Capabilities

(none; new project)

## Impact

- Creates `src/pongwars/**`, `tests/**`, `docs/**`, `pyproject.toml`.
- Phase 1 onward adds the domain core with tests.

## Non-goals

- Internet play (NAT traversal, matchmaking, accounts).
- More than 2 simultaneous players in one match (first version).
- A real 3D engine (OpenGL): software projection on pygame is used.
- Mobile / web.
- Shipping translations other than English (only the mechanism and the source catalog).
