"""@package pongwars.domain.arenas.loader
@brief Parses arena files (TOML/JSON) and exposes the arena registry.
"""

import json
import tomllib
from pathlib import Path
from typing import Any

from pongwars.core.registry import Registry
from pongwars.domain import constants as c
from pongwars.domain.arenas.spec import ArenaSpec, ObstacleSpec, ServeSpec
from pongwars.domain.config import MAX_PLAYERS, MIN_PLAYERS, ConfigError

ARENAS: Registry[ArenaSpec] = Registry("arena")
BUILTIN_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "arenas"
_MIRRORS = {"none": "", "x": "x", "y": "y", "xy": "xy"}


class ArenaError(ConfigError):
    """@brief Invalid arena file; names the file and, when known, the obstacle index."""

    def __init__(self, key: str, file: str, obstacle: int | None = None, **params: object) -> None:
        """@param key Translation key. @param file Source name. @param obstacle Obstacle index."""
        super().__init__(key, file=file, obstacle=obstacle, **params)


def _obstacle(raw: dict[str, Any], index: int, source: str, players: int) -> ObstacleSpec:
    try:
        spec = ObstacleSpec(
            kind=str(raw["kind"]),
            x=float(raw["x"]),
            y=float(raw["y"]),
            half_w=float(raw["half_w"]),
            half_h=float(raw["half_h"]),
            hp=int(raw.get("hp", 0)),
            patrol_x=float(raw.get("patrol_x", 0.0)),
            patrol_y=float(raw.get("patrol_y", 0.0)),
            period=int(raw.get("period", 0)),
            orbit=raw.get("orbit", False),
        )
    except KeyError as exc:
        raise ArenaError("error.arena.missing_field", source, index, field=exc.args[0]) from exc
    except (TypeError, ValueError) as exc:
        raise ArenaError("error.arena.invalid_value", source, index) from exc
    if not isinstance(spec.orbit, bool):
        raise ArenaError("error.arena.invalid_value", source, index)
    problem = spec.validate(players)
    if problem:
        raise ArenaError(problem, source, index)
    return spec


def parse_arena(data: dict[str, Any], source: str = "<memory>") -> ArenaSpec:
    """@brief Build and validate an arena from parsed data.
    @param data Parsed TOML/JSON document.
    @param source File name used in error messages.
    @throws ArenaError If the data is invalid or the layout blocks the table.
    """
    for field_name in ("id", "theme"):
        if field_name not in data:
            raise ArenaError("error.arena.missing_field", source, field=field_name)
    if data.get("width", c.FIELD_WIDTH) != c.FIELD_WIDTH or (
        data.get("height", c.FIELD_HEIGHT) != c.FIELD_HEIGHT
    ):
        raise ArenaError("error.arena.unsupported_size", source)
    mirror = str(data.get("mirror", "none"))
    if mirror not in _MIRRORS:
        raise ArenaError("error.arena.invalid_value", source)
    players = data.get("players", MIN_PLAYERS)
    if not isinstance(players, int) or not MIN_PLAYERS <= players <= MAX_PLAYERS:
        raise ArenaError("error.arena.invalid_value", source)
    obstacles: dict[tuple[object, ...], ObstacleSpec] = {}
    for index, raw in enumerate(data.get("obstacles", [])):
        base = _obstacle(raw, index, source, players)
        variants = [base]
        if "x" in _MIRRORS[mirror]:
            variants += [v.mirrored("x") for v in variants]
        if "y" in _MIRRORS[mirror]:
            variants += [v.mirrored("y") for v in variants]
        for variant in variants:
            obstacles.setdefault(variant.key(), variant)
    serve_data = data.get("serve", {})
    if not isinstance(serve_data, dict):
        raise ArenaError("error.arena.invalid_value", source)
    try:
        serve = ServeSpec(
            x=float(serve_data.get("x", c.FIELD_WIDTH / 2)),
            y=float(serve_data.get("y", c.FIELD_HEIGHT / 2)),
            speed=float(serve_data.get("speed", c.BALL_START_SPEED)),
        )
    except (TypeError, ValueError) as exc:
        raise ArenaError("error.arena.invalid_value", source) from exc
    if serve.validate():
        raise ArenaError("error.arena.invalid_value", source)
    arena_id = str(data["id"])
    arena = ArenaSpec(
        arena_id,
        f"arena.{arena_id}.name",
        str(data["theme"]),
        tuple(obstacles.values()),
        players,
        serve,
    )
    if not arena.has_open_path():
        raise ArenaError("error.arena.blocked_path", source)
    return arena


def load_arena_file(path: Path) -> ArenaSpec:
    """@brief Load an arena from a .toml or .json file.
    @param path File path.
    @throws ArenaError If the file cannot be parsed or is invalid.
    """
    try:
        text = path.read_text(encoding="utf-8")
        data = tomllib.loads(text) if path.suffix == ".toml" else json.loads(text)
    except (OSError, ValueError) as exc:
        raise ArenaError("error.arena.parse", path.name) from exc
    return parse_arena(data, path.name)


def ensure_builtin_arenas() -> None:
    """@brief Register the arenas shipped in data/arenas (idempotent)."""
    for path in sorted(BUILTIN_DIR.glob("*.toml")):
        arena = load_arena_file(path)
        if arena.id not in ARENAS:
            ARENAS.add(arena.id, arena)


def get_arena(name: str) -> ArenaSpec:
    """@brief Look up an arena by id.
    @param name Arena id.
    @throws ConfigError If unknown.
    """
    ensure_builtin_arenas()
    if name not in ARENAS:
        raise ConfigError("error.config.unknown_arena", arena=name)
    return ARENAS.get(name)


def arena_names() -> list[str]:
    """@brief Ids of all available arenas."""
    ensure_builtin_arenas()
    return ARENAS.names()
