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
    language: str = "en"
    particles: bool = True
    trail: bool = True
    shake: bool = True
    view: str = "shared"
    keys: dict[str, list[int]] = field(default_factory=dict)

    def sanitize(self) -> None:
        """@brief Clamp numeric fields and reset invalid choices to their defaults."""
        for name in ("master_volume", "music_volume", "sfx_volume"):
            setattr(self, name, max(MIN_VOLUME, min(MAX_VOLUME, int(getattr(self, name)))))
        self.scale = max(MIN_SCALE, min(MAX_SCALE, int(self.scale)))
        if self.view not in VIEW_MODES:
            self.view = "shared"

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
