"""@package pongwars.core.settings
@brief Persistent user settings stored as JSON in the user configuration directory.
"""

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SETTINGS_FILE = "settings.json"
APP_DIR = "PongWars"
MIN_VOLUME = 0
MAX_VOLUME = 100
MIN_SCALE = 2
MAX_SCALE = 8
VIEW_MODES = ("shared", "split")
BACKGROUNDS = (
    "none",
    "grid",
    "stars",
    "rain",
    "waves",
    "aurora",
    "nebula",
    "comets",
    "bubbles",
    "snow",
    "fireflies",
    "matrix",
    "circuit",
    "embers",
    "meteor",
    "spiral",
    "confetti",
    "starscape",
    "plasma",
    "rainbow",
    "gears",
    "pulse",
)
BALL_STYLES = (
    "classic",
    "pixel",
    "energy",
    "ring",
    "star",
    "crystal",
    "sun",
    "target",
    "moon",
    "flower",
    "dice",
    "eye",
    "atom",
    "gear",
    "prism",
    "comet",
    "bubble",
    "spiral",
    "cross",
    "heart",
)
TRAIL_STYLES = (
    "classic",
    "pixel",
    "neon",
    "comet",
    "dotted",
    "rainbow",
    "flame",
    "frost",
    "spark",
    "squares",
    "rings",
    "double",
    "dash",
    "ripple",
    "stars",
    "ribbon",
    "glitch",
    "orbit",
    "fade",
)
FIELD_STYLES = (
    "grid",
    "checker",
    "neon",
    "solid",
    "dots",
    "diagonal",
    "crosshatch",
    "rings",
    "target",
    "stripes",
    "waves",
    "diamonds",
    "circuit",
    "boxes",
    "radial",
    "stars",
    "lanes",
    "scanlines",
    "maze",
    "sparkle",
)
HUD_STYLES = ("arcade", "minimal", "neon", "cabinet", "scoreboard", "pixel")
PADDLE_COLOR_COUNT = 24
PADDLE_SKIN_COUNT = 20
SEATS = 4


def _fit_seats(values: list[int], default: list[int], count: int) -> list[int]:
    """@brief Coerce a per-seat list to SEATS valid indices below count.
    @param values Raw list.
    @param default Fallback list.
    @param count Exclusive upper bound of valid indices.
    @return A list of exactly SEATS valid ints.
    """
    result = list(default)
    for seat, value in enumerate(values[:SEATS]):
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < count:
            result[seat] = value
    return result


def user_config_dir() -> Path:
    """@brief Directory where the settings file lives (platform specific).
    @return The directory path (not created).
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_DIR


@dataclass
class Settings:
    """@brief User preferences; every field has a safe default and is clamped on load."""

    master_volume: int = 80
    music_volume: int = 60
    sfx_volume: int = 100
    fullscreen: bool = False
    scale: int = 4
    display_index: int = 0
    language: str = "en"
    particles: bool = True
    trail: bool = True
    shake: bool = True
    view: str = "shared"
    last_menu_track: str = ""
    background: str = "grid"
    ball_style: str = "classic"
    trail_style: str = "classic"
    field_style: str = "grid"
    hud_style: str = "arcade"
    player_name: str = "PLAYER"
    last_host: str = ""
    last_match: dict[str, Any] = field(default_factory=dict)
    paddle_colors: list[int] = field(default_factory=lambda: [0, 1, 2, 3])
    paddle_skins: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    keys: dict[str, list[int]] = field(default_factory=dict)

    def sanitize(self) -> None:
        """@brief Clamp numeric fields and reset invalid choices to their defaults."""
        for name in ("master_volume", "music_volume", "sfx_volume"):
            setattr(self, name, max(MIN_VOLUME, min(MAX_VOLUME, int(getattr(self, name)))))
        self.scale = max(MIN_SCALE, min(MAX_SCALE, int(self.scale)))
        self.display_index = max(0, int(self.display_index))
        if self.view not in VIEW_MODES:
            self.view = "shared"
        if self.background not in BACKGROUNDS:
            self.background = "grid"
        if self.ball_style not in BALL_STYLES:
            self.ball_style = "classic"
        if self.trail_style not in TRAIL_STYLES:
            self.trail_style = "classic"
        if self.field_style not in FIELD_STYLES:
            self.field_style = "grid"
        if self.hud_style not in HUD_STYLES:
            self.hud_style = "arcade"
        self.paddle_colors = _fit_seats(self.paddle_colors, [0, 1, 2, 3], PADDLE_COLOR_COUNT)
        self.paddle_skins = _fit_seats(self.paddle_skins, [0, 0, 0, 0], PADDLE_SKIN_COUNT)

    def to_json(self) -> str:
        """@brief Serialise to JSON text.
        @return The JSON document.
        """
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        """@brief Build settings from a mapping, ignoring unknown or ill-typed entries.
        @param data Raw values.
        @return Sanitised settings.
        """
        defaults = cls()
        known = {f.name: getattr(defaults, f.name) for f in fields(cls)}
        values: dict[str, Any] = {}
        for name, default in known.items():
            value = data.get(name, default)
            if name == "last_match":
                values[name] = dict(value) if isinstance(value, dict) else {}
                continue
            same_type = isinstance(value, type(default)) and (
                isinstance(value, bool) == isinstance(default, bool)
            )
            values[name] = value if same_type else default
        settings = cls(**values)
        settings.sanitize()
        return settings

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        """@brief Read settings from disk; defaults when missing or corrupt.
        @param path File to read (the user config file when omitted).
        @return The loaded settings.
        """
        path = path or user_config_dir() / SETTINGS_FILE
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("settings root must be an object")
            return cls.from_dict(raw)
        except FileNotFoundError:
            return cls()
        except (OSError, ValueError) as error:
            logger.warning("Ignoring unreadable settings file %s: %s", path, error)
            return cls()

    def save(self, path: Path | None = None) -> bool:
        """@brief Write settings to disk.
        @param path File to write (the user config file when omitted).
        @return True on success; failures are logged and never raised.
        """
        path = path or user_config_dir() / SETTINGS_FILE
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.to_json(), encoding="utf-8")
        except OSError as error:
            logger.warning("Could not save settings to %s: %s", path, error)
            return False
        return True
