# PongWars User Guide

## Requirements

- Python 3.11 or newer
- A desktop with a display (audio is optional; the game stays silent without a sound device)

## Install and start

```powershell
cd PongWars
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
python -m pongwars        # or simply: pongwars
```

Linux/macOS: use `source .venv/bin/activate` instead of the `Activate.ps1` line.

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
  such as points to win, duration or lives).
- **Arena**: Classic, Pillars, Bumpers, Moving Walls, Fortress (2 players);
  Trident (3 players); Crossfire (4 players). Choosing an arena sets the number of seats.
- **Players**: each seat is *human* or *AI*; AI seats have a difficulty
  (easy, normal, hard, insane) and strategy.
- **Extras**: off, all, powers only, weapons only or penalties only.
- **Start** launches the match.

## Controls (defaults)

| Seat | Move up | Move down | Fire weapon |
|------|---------|-----------|-------------|
| 1 (left) | W | S | D |
| 2 (right) | Up arrow | Down arrow | Left arrow |
| 3 | J | L | K |
| 4 | Numpad 8 | Numpad 2 | Numpad 5 |

Keys can be rebound in **Settings** (two keys per seat). A key already in use is rejected.

## Playing

- Return the ball past the opponent's paddle to score. The first to the point limit wins
  (rules differ per mode).
- In 3- and 4-player arenas the point goes to the last player who touched the ball when it
  enters a goal; players can be eliminated.
- Obstacles: *bumpers* bounce the ball with extra force, *solid* walls just reflect it and
  *destructible* blocks break after being hit.
- **Extras** appear on the field when enabled:
  - **Powers** (big paddle, speed, magnet, shield, multiball, slow motion, aim assist,
    cleanse, slow ball, turbo ball) help you.
  - **Weapons** (laser, freeze, bomb, **cat**, hex, warp) have limited ammo; fire with your
    fire key. The cat chases the ball for a few seconds and randomly changes its direction
    and speed.
  - **Penalties** (small paddle, inverted controls, slowness, blindness, drunk, jammed) hurt
    you.
  - Active effects are shown in the HUD.
- **Esc** pauses: resume, open settings or quit to the menu.
- At the end the results screen offers rematch, change setup or main menu.

## Appearance and music

**Appearance** in the main menu lets each seat pick a paddle colour (8) and style (4), the
animated arena background (none, grid, stars, rain, waves, aurora) and the music track
(random or one of arcade, chase, hero, dusk, boss). A live preview is shown.
**How to play** is an in-game guide (6 pages: goal, controls, modes, powers, weapons,
penalties); use Left/Right to turn pages.

## Settings

Master / music / effects volume, fullscreen, window scale, language (English, Spanish),
particles, ball trail, screen shake and the camera for 3-4 player arenas
(**shared** view or **split** screen). Settings are saved automatically to
`%APPDATA%\PongWars\settings.json` (Linux: `~/.config/PongWars/`).

## Troubleshooting

- *No sound*: the game logs a warning and continues silently if no audio device exists.
- *Window too big/small*: change **Scale** in Settings.
- *Reset everything*: delete the `settings.json` file mentioned above.

## Adding content

- **Language**: copy `src/pongwars/data/locales/en.json` to `<code>.json`, translate the values
  and set `language.name`; it appears in Settings automatically.
- **Arena**: add a TOML file in `src/pongwars/data/arenas/`.
- **Sounds**: edit `src/pongwars/data/audio/sounds.toml`.

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
