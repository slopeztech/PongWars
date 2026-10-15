"""@package pongwars.domain.arenas
@brief Data-driven arenas: obstacle layouts loaded from TOML/JSON files.
"""

from pongwars.domain.arenas.loader import (
    ARENAS,
    ArenaError,
    arena_names,
    ensure_builtin_arenas,
    get_arena,
    load_arena_file,
    parse_arena,
)
from pongwars.domain.arenas.spec import ArenaSpec, ObstacleSpec

__all__ = [
    "ARENAS",
    "ArenaError",
    "ArenaSpec",
    "ObstacleSpec",
    "arena_names",
    "ensure_builtin_arenas",
    "get_arena",
    "load_arena_file",
    "parse_arena",
]
