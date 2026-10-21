# PongWars Architecture

Summary; the full decision record and discarded alternatives live in
`openspec/changes/bootstrap-pongwars/design.md`.

## Layers

```
app -> ui -> render / input / audio / net -> domain <- ai
                                               ^
                                             core
```

- `domain`: pure deterministic 60 Hz simulation. No pygame, no I/O, no prose.
- `render`: software pseudo-3D projection onto a low-resolution 8-bit surface,
  upscaled nearest-neighbor. Read-only on state.
- `input`: keyboard/gamepad -> `PlayerInput`. `ai` and `net` produce the same type.
- `net`: authoritative host (UDP); client sends inputs, receives snapshots.
- `core`: `Registry`, i18n `Translator`, utilities.
- Extensibility: modes, arenas, extras and AI are registered in `core.Registry`.
- Localization: events/errors carry translation keys; only `ui` produces text.

## Match data flow

`MatchConfig` -> `World` <- `FrameInputs` (keyboard | AI | network) -> events ->
(`audio`, `render`, `ui`).

## Capability to package map

| Capability (OpenSpec)  | Package                         |
|------------------------|---------------------------------|
| game-core              | `domain`                        |
| match-configuration    | `domain.config`                 |
| game-modes             | `domain.modes`                  |
| arenas                 | `domain.arenas`, `data/arenas`  |
| extras                 | `domain.extras`, `data/extras`  |
| rendering              | `render`                        |
| input                  | `input`                         |
| ai-opponent            | `ai`                            |
| lan-multiplayer        | `net`                           |
| ui-menus               | `ui`                            |
| audio                  | `audio`                         |
| localization           | `core.i18n`, `data/locales`     |
| engineering-quality    | `tests`, `scripts`, `docs`      |

## Players and rendering

Arenas support 2, 3 or 4 players (seats: left, right, top, bottom); absent seats are walls. The pseudo-3D view is a pitched pinhole camera (
ender/camera.py) drawing onto a 320x180 surface scaled up; input lives in input/controllers.py and the loop in core/loop.py.

## Extras

Powers, weapons, penalties and statuses are Effect subclasses registered in domain.extras.effects.EFFECTS and balanced in data/extras/extras.toml. ExtrasManager (owned by World) spawns pickups, applies effects and exposes per-player Mods that World.step reads. Fire keys per seat: D, LEFT, K, KP5; spin keys are A, RIGHT, H, KP4. Spin is part of `FrameInputs`, curves the ball's velocity continuously after impact, and emits a distinct `SpinHit` audio event. Score-gap assistance is limited to one targeted pickup every 15 seconds; the table holds at most two pickups, which maintain a minimum separation. The companion paddle and missiles are authoritative world entities and are included in LAN snapshots. AI seats fire extras through `AIController.fire_intent()` and occasionally apply spin during an approaching return, with both decisions paced by the difficulty profile. Active effect and weapon names are translated using full `extras.NAME.name` locale entries and displayed on separate HUD lines.

Each new match has a deterministic three-step countdown of 30 ticks per digit (half a second at 60 ticks per second) before its first serve.

## UI, audio and settings


The ui package is a stack of screens (title, menus, setup with arena preview, match, pause overlay, results, settings) driven by `pongwars.app.App`. All text goes through the `Translator`; the bitmap font exposes `normalize` for unsupported characters. The `audio` package synthesizes sound effects from `data/audio/sounds.toml` and music from `.pws` song files (see [music-format.md](music-format.md)): `songfile` parses them, `sequencer` renders them to PCM and `jukebox` plays random songs per context with a 2-3 s gap. Audio falls back to silence without a device. `core.settings.Settings` persists user preferences as JSON in the user config directory.


## LAN (net package)

The host is authoritative: `HostSession` runs the `World`, receives client inputs and
broadcasts snapshots; `ClientSession` sends inputs and interpolates snapshots. Messages
are versioned dataclasses (`protocol`), encoded by a `Codec` (`codec`) and sent through
a `Transport` (`UdpTransport` or the in-memory `MemoryNetwork` with simulated loss used
by tests). `Discovery` finds hosts by broadcast. `net` imports only `core` and `domain`;
the screens live in `ui/lan.py`. The lobby roster and match-start message synchronize
paddle colors and patterns against the full appearance catalog. Ball, trail, field,
background, and HUD styling remain local render preferences. Incompatible LAN message
changes are reflected in `PROTOCOL_VERSION`. The current snapshot includes the state of
the temporary swallowed-ball and pursuing-creature extras.
