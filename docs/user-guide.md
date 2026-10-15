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
- **LAN host / LAN join** - disabled for now ("Soon"); LAN play is not implemented yet.
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
  - **Powers** (big paddle, speed, magnet, shield, multiball, slow motion) help you.
  - **Weapons** (laser, freeze, bomb) have limited ammo; fire with your fire key.
  - **Penalties** (small paddle, inverted controls, slowness, blindness) hurt you.
  - Active effects are shown in the HUD.
- **Esc** pauses: resume, open settings or quit to the menu.
- At the end the results screen offers rematch, change setup or main menu.

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
