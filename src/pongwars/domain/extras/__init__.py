"""@package pongwars.domain.extras
@brief Weapons, powers and penalties implemented as composable effects.
"""

from pongwars.domain.extras import effects as _effects  # noqa: F401  (registers the built-ins)
from pongwars.domain.extras.base import EFFECTS, Effect, EffectSpec, Mods, load_specs
from pongwars.domain.extras.manager import ExtrasManager, Pickup

__all__ = ["EFFECTS", "Effect", "EffectSpec", "ExtrasManager", "Mods", "Pickup", "load_specs"]
