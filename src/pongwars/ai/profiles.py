"""@package pongwars.ai.profiles
@brief Difficulty profiles: pure parameter sets, no behaviour.
"""

from dataclasses import dataclass

from pongwars.core.registry import Registry


@dataclass(frozen=True)
class Profile:
    """@brief Parameters that define how well an AI plays.

    @param reaction_ticks Delay between the world and what the AI perceives.
    @param aim_error Maximum random aim error in world units (re-rolled on every bounce).
    @param speed Fraction of the paddle's maximum speed the AI may use.
    @param predict_walls Whether bounces on walls are predicted.
    @param predict_obstacles Whether bounces on obstacles are predicted.
    @param recenter Whether the paddle returns to the middle when the ball goes away.
    @param extra_skill Probability-like skill in [0, 1] to use extras (used from Phase 5).
    """

    reaction_ticks: int
    aim_error: float
    speed: float
    predict_walls: bool
    predict_obstacles: bool
    recenter: bool
    extra_skill: float


PROFILES: Registry[Profile] = Registry("difficulty")
PROFILES.add("easy", Profile(24, 16.0, 0.5, False, False, False, 0.1))
PROFILES.add("normal", Profile(12, 8.0, 0.75, True, False, True, 0.4))
PROFILES.add("hard", Profile(5, 3.0, 0.95, True, True, True, 0.75))
PROFILES.add("insane", Profile(1, 0.5, 1.0, True, True, True, 1.0))
