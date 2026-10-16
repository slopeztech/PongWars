# PongWars

Classic Pong with an **8-bit** look and a pseudo-3D view. Play on the same keyboard,
challenge the AI, or face your friends over a local network.

## Game modes

Choose a mode, arena, players, and optional extras before each match.

| Mode | How to win |
|------|------------|
| **Classic** | Be the first to reach the points target. You can enable **Win by two** to require a two-point lead. |
| **Timed** | Score as many points as possible before time runs out. A tie starts sudden death; the next point wins. |
| **Survival** | Each goal you concede costs a life. Eliminate every opponent to be the last player standing. |
| **King of the Table** | Hold the ball in the center zone to score for the last player who touched it. Goals do not score; reach the points target to win. |

The target score, time limit, and number of lives can be adjusted in match setup.

## Arenas

There are eleven arenas. **Classic** through **Portal** are for two players;
**Trident** is for three and **Crossfire** is for four.

| Arena | What to expect |
|-------|----------------|
| **Classic** | An open court with no obstacles. |
| **Pillars** | A pair of solid pillars blocks the center lanes. |
| **Bumpers** | Two bumpers send the ball bouncing back into play. |
| **Moving Walls** | A solid wall moves across the court, changing the available routes. |
| **Fortress** | A destructible central barrier can be broken by repeated hits. |
| **Monolith** | A fixed solid barrier splits the middle of the court. |
| **Orbital** | Two orbiting bumpers move around the court and deflect the ball. |
| **Pinball** | Two bumpers create a pinball-style court. |
| **Portal** | A pair of portals moves the ball to the other side while preserving its direction and reducing its speed. |
| **Trident** | A three-player court with a central solid obstacle. |
| **Crossfire** | A four-player court with a central solid obstacle. |

## Pickups and extras

Extras are optional. Set them to **Off**, **All**, or enable only powers, weapons, or
penalties. Pickups appear on the court and are collected by the ball.

### Powers

| Power | Effect |
|-------|--------|
| **Big paddle** | Temporarily enlarges your paddle. |
| **Speed boost** | Temporarily makes your paddle move faster. |
| **Magnet** | Lets your paddle catch the ball; fire your weapon or wait for the effect to release it. |
| **Shield** | Bounces back the next ball that would score against you. |
| **Multiball** | Splits the ball into several balls. |
| **Slow motion** | Temporarily slows your opponents' paddles. |
| **Aim assist** | A paddle hit aims the ball toward the next opponent. |
| **Cleanse** | Removes your penalties and disabling effects. |
| **Slow ball** | Slows all balls down. |
| **Companion** | Adds a temporary AI paddle to help defend your goal. |

### Weapons

Collect a weapon, then press your **Use weapon** key to fire it.

| Weapon | Effect |
|--------|--------|
| **Laser** | Fires across the court, stunning the first opponent hit or damaging a destructible obstacle. |
| **Freeze** | Temporarily stops an opponent's paddle from moving. |
| **Bomb** | Blasts nearby balls away from your paddle. |
| **Cat** | Releases a cat that chases the ball and scrambles its direction and speed. |
| **Hex** | Curses an opponent with a random penalty. |
| **Warp** | Teleports every moving ball to a random spot without changing its velocity. |
| **Headbutt** | Briefly lunges your paddle forward to extend its reach. |
| **Missiles** | Fires guided missiles at opponents; missiles can also damage destructible obstacles. |

### Penalties

| Penalty | Effect |
|---------|--------|
| **Small paddle** | Temporarily shrinks your paddle. |
| **Inverted controls** | Reverses your paddle controls. |
| **Slow paddle** | Temporarily reduces your paddle's movement speed. |
| **Blind** | Obscures your view of the court. |
| **Turbo ball** | Speeds all balls up. |
| **Dizzy controls** | Makes your paddle sway on its own. |
| **Weapon jam** | Prevents you from firing your weapon. |

## Players and match setup

- Play with **2-4 people on one keyboard**, or choose **Versus AI** and set the AI difficulty.
- In three- and four-player arenas, the players share the court; a goal eliminates or scores against the player who conceded it, depending on the selected mode.
- Enable **Extras** for pickups, and choose a shared or split camera in larger arenas.
- In a match, press **Esc** to pause, resume, open settings, or return to the menu.

For LAN play, one player hosts and others join from the same local network. Hosts can
configure open seats; unfilled seats are controlled by AI. See the
[player guide](docs/user-guide.md#lan-play) for connection details.

## Appearance and sound

Choose paddle colors and styles, ball designs, ball trails, and arena-field styles.
Select an animated background or turn it off. **Settings** is split into Graphics,
Sound, Gameplay, and Controls. Graphics lets you choose fullscreen, window size, and
which monitor to use; the selected monitor is also used in fullscreen. Preferences are
saved automatically. The original soundtrack plays in menus and matches.

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

## License

PongWars is distributed under the [MIT License](LICENSE).
