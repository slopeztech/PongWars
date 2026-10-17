# PongWars

Classic Pong with an **8-bit** look and a pseudo-3D view. Play on the same keyboard,
challenge the AI, or face your friends over a local network.

## Game modes

Choose a mode, arena, players, and optional extras before each match. Each mode
has its own scoring and end conditions; see the [game modes guide](docs/game-modes.md)
for detailed rules and configurable options.

The target score, time limit, and number of lives can be adjusted in match setup.

## Arenas

Thirteen arenas offer open courts, moving obstacles, bumpers, destructible
blocks, portals, and gravity. **Trident** is for three players and **Crossfire**
for four; see the [arena guide](docs/arenas.md) for every layout and its
collision behavior.

## Pickups and extras

Extras are optional. Set them to **Off**, **All**, or enable only powers, weapons,
or penalties. See the [extras guide](docs/extras.md) for every pickup, duration,
weapon ammunition, and collection rules.

## Players and match setup

- Play with **2-4 people on one keyboard**, or choose **Versus AI** and set the AI difficulty.
- In three- and four-player arenas, the players share the court; a goal eliminates or scores against the player who conceded it, depending on the selected mode.
- Enable **Extras** for pickups, and choose a shared or split camera in larger arenas.
- In a match, press **Esc** to pause, resume, open settings, or return to the menu.

For LAN play, one player hosts and others join from the same local network. Hosts can
configure open seats; unfilled seats are controlled by AI. See the
[player guide](docs/user-guide.md#lan-play) for connection details.

## Appearance and sound

Choose from 24 paddle colors, 20 paddle patterns, 20 ball designs, 19 ball trails,
20 arena-field styles, and 22 background choices. See the full [appearance guide](docs/appearance.md).
**Settings** is split into Graphics, Sound, Gameplay, and Controls. Graphics lets you
choose fullscreen, window size, and which monitor to use; the selected monitor is
also used in fullscreen. Preferences are saved automatically. The original soundtrack
plays in menus and matches.

### Controls

| Player | Move up | Move down | Spin on hit | Use weapon |
|--------|---------|-----------|-------------|------------|
| 1 (left) | W | S | A | D |
| 2 (right) | Up arrow | Down arrow | Right arrow | Left arrow |
| 3 | J | L | H | K |
| 4 | Numpad 8 | Numpad 2 | Numpad 4 | Numpad 5 |

In menus, use **Up/Down** to select, **Left/Right** to change options,
**Enter/Space** to confirm, and **Esc** to go back or pause. Controls can be
customized in **Settings**.

## Install on Windows

Look for **PongWars-Setup** on the [releases page](https://github.com/slopeztech/PongWars/releases).
The installer includes the game and its dependencies; Python is not required. If no
installer is listed there, a public download has not been published yet.

For more gameplay details and LAN instructions, see the [player guide](docs/user-guide.md).

## Other guides

- [Run PongWars from Python](docs/python-console.md) — launch the game from a terminal
  or interactive Python console.
- [Development and contribution](docs/development.md) — set up tools, run checks, and
  build installers.
- [Appearance guide](docs/appearance.md) — catalogs the available paddle, ball,
  trail, field, and background customizations.

## License

PongWars is distributed under the [MIT License](LICENSE).
