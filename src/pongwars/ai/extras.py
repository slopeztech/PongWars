"""@package pongwars.ai.extras
@brief Pure heuristics deciding whether an AI should use its held weapon right now.
"""

from pongwars.ai.observation import Observation
from pongwars.domain import constants as c
from pongwars.domain.vec import Vec2

HOLD_TICKS = 25
ALIGN_MARGIN = 1.0


def _approaching(obs: Observation) -> bool:
    vel = obs.ball_vel
    component = vel.x if obs.seat in (0, 1) else vel.y
    return component < 0 if obs.seat in (0, 2) else component > 0


def _aligned_with_foe(obs: Observation) -> bool:
    mine = obs.paddle
    for foe in obs.foes:
        if obs.axis == "y":
            if abs(foe.cy - mine.cy) <= foe.half_h * ALIGN_MARGIN:
                return True
        elif abs(foe.cx - mine.cx) <= foe.half_w * ALIGN_MARGIN:
            return True
    return False


def _ball_distance(obs: Observation) -> float:
    return (obs.ball_pos - Vec2(obs.paddle.cx, obs.paddle.cy)).length()


def wants_fire(obs: Observation) -> bool:
    """@brief Decide whether the held weapon is worth using this tick.
    @param obs Current observation of the AI's seat.
    @return True if the AI should press fire.
    """
    if obs.weapon is None or obs.jammed or not obs.foes:
        return False
    name = obs.weapon
    if name == "laser":
        return _aligned_with_foe(obs)
    if name in ("freeze", "hex"):
        return True
    if name == "cat":
        return not _approaching(obs)
    if name == "bomb":
        return _approaching(obs) and _ball_distance(obs) < c.BOMB_RADIUS * 0.6
    if name == "warp":
        along = obs.ball_pos.y if obs.axis == "y" else obs.ball_pos.x
        return _approaching(obs) and abs(along - obs.paddle_pos) > obs.paddle_half * 3
    return True
