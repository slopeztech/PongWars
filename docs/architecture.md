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

Arenas support 2, 3 or 4 players (seats: left, right, top, bottom); absent seats are walls. The pseudo-3D view is a pitched pinhole camera (ender/camera.py) drawing onto a 320x180 surface scaled up; input lives in input/controllers.py and the loop in core/loop.py.

## Extras

Powers, weapons, penalties and statuses are Effect subclasses registered in domain.extras.effects.EFFECTS and balanced in data/extras/extras.toml. ExtrasManager (owned by World) spawns pickups, applies effects and exposes per-player Mods that World.step reads. Fire keys per seat: D, LEFT, K, KP5. The AI never fires. HUD codes come from the `extras.NAME.short` locale keys.

## UI, audio and settings

The ui package is a stack of screens (title, menus, setup with arena preview, match, pause overlay, results, settings) driven by pp.App. All text goes through the Translator; the bitmap font exposes 
ormalize for unsupported characters. udio synthesizes chiptune sounds from data/audio/sounds.toml (event class name to sound) and falls back to silence without a device. core.settings.Settings persists user preferences as JSON in the user config directory.

