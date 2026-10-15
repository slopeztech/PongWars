"""@package pongwars.domain.modes
@brief Registrable game modes (classic, timed, survival, king of the table).
"""

from pongwars.domain.modes import builtin as _builtin  # noqa: F401  (registers the modes)
from pongwars.domain.modes.base import MODES, Mode, OptionSpec, create_mode, register_mode

__all__ = ["MODES", "Mode", "OptionSpec", "create_mode", "register_mode"]
