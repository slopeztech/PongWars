# PongWars User Guide

## Install and start

On Windows, download and run **PongWars-Setup** from the
[PongWars releases page](https://github.com/slopeztech/PongWars/releases). The installer
includes the game and its runtime dependencies; Python is not required. If no installer
is listed on the releases page, a public download has not been published yet.

For instructions to run from source with Python, see
[Running from the Python console](python-console.md).

## Menus

Press **Enter** on the title screen. In every menu:

| Key | Action |
|-----|--------|
| Up / Down | Select an entry |
| Left / Right | Change the value of the entry |
| Enter / Space | Activate |
| Esc | Back (in a match: pause) |

Main menu entries:

- **Local play** - 2 or more humans on the same keyboard.
- **Versus AI** - you against the AI (pick the difficulty in the setup screen).
- **LAN host / LAN join / LAN help** - play over a local network (see "LAN play" below).
- **Settings** and **Quit**.

## Match setup

Every match is configured before it starts, with a live preview of the arena:

- **Mode**: Classic, Timed, Survival, King of the Table (each exposes its own options,
  such as points to win, duration or lives). See the [game modes guide](game-modes.md)
  for scoring rules and option ranges.
- **Arena**: choose from thirteen layouts. Trident is for three players and Crossfire
  for four; choosing an arena sets the number of seats. See the [arena guide](arenas.md)
  for the complete catalog and obstacle details.
- **Players**: each seat is *human* or *AI*; AI seats have a difficulty
  (easy, normal, hard, insane) and strategy.
- **Extras**: off, all, powers only, weapons only or penalties only.
- **Start** launches the match.

In **King of the Table**, the last player to touch the ball earns a point for each
quarter-second the ball remains in the central zone. **Timed** matches show the
remaining time at the bottom of the arena.

## Controls (defaults)

| Seat | Move up | Move down | Spin on hit | Fire weapon |
|------|---------|-----------|------------|-------------|
| 1 (left) | W | S | A | D |
| 2 (right) | Up arrow | Down arrow | Right arrow | Left arrow |
| 3 | J | L | H | K |
| 4 | Numpad 8 | Numpad 2 | Numpad 4 | Numpad 5 |

Spin is applied when the ball next hits your paddle while you are moving up/down. It bends
the ball's path in the direction of the spin, increases its speed, and ends at the next bounce.
The spin hit has a distinct impact sound. AI players also use spin occasionally when returning
an approaching ball; higher difficulties use it more often. Each match starts with a 3-2-1 countdown, with each
number shown for half a second below the arena. Keys can be rebound in **Settings** (movement
keys); a key already in use is rejected.

## Playing

- Return the ball past the opponent's paddle to score. The first to the point limit wins
  (rules differ per mode).
- In 3- and 4-player arenas the point goes to the last player who touched the ball when it
  enters a goal; players can be eliminated.
- Obstacles: *bumpers* bounce the ball with extra force, *solid* walls just reflect it and
  *destructible* blocks break after being hit.
- **Extras** appear on the field when enabled:
  - Pickups are collected by the ball. Powers help you, weapons have limited ammo and
    penalties make play harder.
  - See the [extras guide](extras.md) for every effect, duration, weapon ammunition,
    and special comeback pickup rules.
  - If extras are enabled and the score gap reaches two points, a short-lived bonus pickup
    may appear along the losing or leading player's paddle path, at most once every 15 seconds
    and only when no other pickup is on the table. At most two pickups are visible at once,
    and they are kept apart. Collect comeback pickups by moving the paddle over them; normal
    pickups still need the ball.
  - Active effects and weapons are shown by their complete translated names below the affected
    player's score, along with remaining time or ammunition.
- **Esc** pauses: resume, open settings or quit to the menu.
- At the end the results screen offers rematch, change setup or main menu.

## Appearance and music

**Appearance** in the main menu offers 24 paddle colours, 20 paddle patterns, 20 ball
designs, 19 ball-trail styles, 20 arena-field styles and 22 background choices.
Selections are previewed immediately and saved automatically. See the
[appearance guide](appearance.md) for the complete catalog and controls.
Songs play in random order (never the same one twice in a row) in the menus and during matches, with 2-3 seconds of silence between them. A pixel-art music card appears in the lower-right corner for five seconds when a song starts. The first menu song is different from the one that started the previous launch.
**How to play** is an in-game guide (6 pages: goal, controls, modes, powers, weapons,
penalties); use Left/Right to turn pages.

## Settings

Settings are grouped into four submenus:

- **Graphics**: fullscreen, monitor, and window scale. Select the monitor before
  enabling fullscreen to move the game to that screen.
- **Sound**: master, music, and effects volume.
- **Gameplay**: language, particles, ball trail, screen shake, and the camera for
  3-4 player arenas (**shared** view or **split** screen).
- **Controls**: rebind the movement keys for each player.

Changes are applied and saved automatically to
`%APPDATA%\PongWars\settings.json` (Linux: `~/.config/PongWars/`).

## Troubleshooting

- *No sound*: the game logs a warning and continues silently if no audio device exists.
- *Window too big/small*: change **Scale** in Settings.
- *Reset everything*: delete the `settings.json` file mentioned above.

## Adding content

- **Language**: copy `src/pongwars/data/locales/en.json` to `<code>.json`, translate the values
  and set `language.name`; it appears in Settings automatically.
- **Arena**: add a TOML file in `src/pongwars/data/arenas/` and document its layout in
  the [arena guide](arenas.md).
- **Documentation**: every new feature or change to existing behavior must update the
  relevant guide. See [Development and contribution](development.md#documentation-is-part-of-the-change).
- **Sounds**: edit `src/pongwars/data/audio/sounds.toml`.
- **Songs**: drop a `.pws` file in `src/pongwars/data/music/` (format in
  [music-format.md](music-format.md)).

## LAN play

One PC hosts and the others join; every PC runs its own copy of the game.

**Host**: Main menu -> LAN host, configure the match (the local player is seat 1; the
other human seats become open slots), then wait in the lobby. Start the match when the
wanted players have joined; unfilled seats are played by AI bots.

**Join**: Main menu -> LAN join. Hosts on the same subnet are found automatically
(UDP broadcast); pick one. To connect directly, edit the address field (`IP` or
`IP:PORT`) and press Connect. The player name is set in the same screen.

**Network**: UDP port 47474. Allow the game through the firewall on the host.
Both PCs must be on the same LAN. If the port is busy the lobby shows an error.

**Disconnections**: if a player is silent for 5 seconds the host pauses and offers
"replace with AI" or "wait". If the host closes, clients return to the menu with a notice.

**Help**: Main menu -> LAN help explains all of this in four pages.

Limitations: no internet relay/NAT traversal, no encryption, one match per host.
