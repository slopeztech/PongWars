"""@package pongwars.domain.extras.base
@brief Effect base class, effect registry and balance data (extras.toml).
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from pongwars.core.registry import Registry
from pongwars.domain import constants as c
from pongwars.domain.events import Event

if TYPE_CHECKING:
    from pongwars.domain.world import World

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "extras"
CATEGORIES = ("power", "weapon", "penalty", "status")


@dataclass(frozen=True)
class EffectSpec:
    """@brief Balance data of one effect.
    @param name Effect name (also its registry key).
    @param category One of CATEGORIES.
    @param duration Lifetime in seconds (0 for instant effects and weapons).
    @param magnitude Effect strength (a scale factor for size/speed effects).
    @param weight Spawn rarity weight; 0 means the effect never spawns on its own.
    @param ammo Shots granted by a weapon pickup.
    """

    name: str
    category: str
    duration: float = 0.0
    magnitude: float = 1.0
    weight: int = 0
    ammo: int = 0

    @property
    def ticks(self) -> int:
        """@brief Lifetime in simulation ticks."""
        return round(self.duration * c.TICK_RATE)


@dataclass
class Mods:
    """@brief Per-player gameplay modifiers recomputed every tick from the active effects."""

    size_scale: float = 1.0
    speed_scale: float = 1.0
    invert: bool = False
    frozen: bool = False
    magnet: bool = False
    shield: bool = False
    blind: bool = False
    drunk: bool = False
    jammed: bool = False
    aim: bool = False


class Effect:
    """@brief Base class of every power, weapon, penalty and status effect.

    Subclasses are registered in EFFECTS under their `name` and read their balance from the
    matching EffectSpec. Override only the hooks they need.
    """

    name: ClassVar[str] = ""
    category: ClassVar[str] = ""
    lasting: ClassVar[bool] = True  # False: applied once and never stored (e.g. multiball)
    on_opponents: ClassVar[bool] = False  # True: applied to the collector's opponents
    single_target: ClassVar[bool] = False  # True: applied to the first target only

    def __init__(self, spec: EffectSpec) -> None:
        """@brief Create an effect instance.
        @param spec Balance data.
        """
        self.spec = spec
        self.remaining = spec.ticks

    def modify(self, mods: Mods) -> None:
        """@brief Contribute to the owner's modifiers.
        @param mods Modifiers to adjust in place.
        """

    def on_apply(self, world: "World", player: int, events: list[Event]) -> None:
        """@brief Called once when the effect starts.
        @param world Match being played.
        @param player Affected seat.
        @param events Event list to append to.
        """

    def on_expire(self, world: "World", player: int, events: list[Event]) -> None:
        """@brief Called when the effect ends or is removed.
        @param world Match being played.
        @param player Seat whose effect ended.
        @param events Event list to append to.
        """

    def fire(self, world: "World", player: int, events: list[Event]) -> None:
        """@brief Weapon action; only meaningful for the weapon category.
        @param world Match being played.
        @param player Shooter seat.
        @param events Event list to append to.
        """


EFFECTS: Registry[type[Effect]] = Registry("effect")


def load_specs(path: Path | None = None) -> dict[str, EffectSpec]:
    """@brief Read the effect balance data.
    @param path TOML file to read; the built-in data when omitted.
    @return Specs keyed by effect name.
    @throws ValueError If an entry is malformed.
    """
    file = path or DATA_DIR / c.EXTRAS_DATA_FILE
    with file.open("rb") as handle:
        raw = tomllib.load(handle)
    specs: dict[str, EffectSpec] = {}
    for name, entry in raw.items():
        category = entry.get("category")
        if category not in CATEGORIES:
            raise ValueError(f"effect '{name}' has an invalid category")
        specs[name] = EffectSpec(
            name=name,
            category=category,
            duration=float(entry.get("duration", 0.0)),
            magnitude=float(entry.get("magnitude", 1.0)),
            weight=int(entry.get("weight", 0)),
            ammo=int(entry.get("ammo", 0)),
        )
    return specs
