"""@package pongwars.ai.strategies
@brief Pluggable target-selection strategies (registered by name).
"""

from collections.abc import Callable

from pongwars.ai.observation import Observation
from pongwars.ai.prediction import predict_intercept
from pongwars.ai.profiles import Profile
from pongwars.core.registry import Registry
from pongwars.domain import constants as c

Strategy = Callable[[Observation, Profile], float | None]
STRATEGIES: Registry[Strategy] = Registry("ai strategy")


def _ball_along(obs: Observation) -> float:
    return obs.ball_pos.y if obs.axis == "y" else obs.ball_pos.x


def _approaching(obs: Observation) -> bool:
    vel = obs.ball_vel
    component = vel.x if obs.seat in (0, 1) else vel.y
    return component < 0 if obs.seat in (0, 2) else component > 0


def centre(obs: Observation) -> float:
    """@brief Middle of the field along the observer's paddle axis."""
    return c.FIELD_HEIGHT / 2 if obs.axis == "y" else c.FIELD_WIDTH / 2


@STRATEGIES.register("predictive")
def predictive(obs: Observation, profile: Profile) -> float | None:
    """@brief Intercept the predicted arrival point, or follow the ball when prediction is off.
    @return Target coordinate along the paddle axis, or None to stay put.
    """
    if not profile.predict_walls:
        return _ball_along(obs) if _approaching(obs) else None
    target = predict_intercept(obs, profile.predict_obstacles)
    if target is not None:
        return target
    return centre(obs) if profile.recenter else None


@STRATEGIES.register("tracker")
def tracker(obs: Observation, profile: Profile) -> float | None:
    """@brief Always follow the ball's current coordinate (simple, beatable)."""
    return _ball_along(obs)
