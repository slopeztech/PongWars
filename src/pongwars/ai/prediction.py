"""@package pongwars.ai.prediction
@brief Ball trajectory prediction including wall and obstacle bounces.
"""

from pongwars.ai.observation import Observation
from pongwars.domain import constants as c
from pongwars.domain.entities import Rect
from pongwars.domain.physics import reflect, sweep_circle_rect
from pongwars.domain.vec import Vec2

HORIZON_TICKS = 360
MAX_SWEEPS = 3
_MIN_SIDE = (True, False, True, False)


def _reached_line(obs: Observation, pos: Vec2) -> bool:
    paddle, r = obs.paddle, obs.ball_radius
    seat = obs.seat
    if seat == 0:
        return pos.x - r <= paddle.cx + paddle.half_w
    if seat == 1:
        return pos.x + r >= paddle.cx - paddle.half_w
    if seat == 2:
        return pos.y - r <= paddle.cy + paddle.half_h
    return pos.y + r >= paddle.cy - paddle.half_h


def _bounce_walls(obs: Observation, pos: Vec2, vel: Vec2) -> tuple[Vec2, Vec2]:
    r = obs.ball_radius
    walls = obs.walls
    if walls[2] and pos.y < r:
        pos, vel = Vec2(pos.x, 2 * r - pos.y), Vec2(vel.x, abs(vel.y))
    elif walls[3] and pos.y > c.FIELD_HEIGHT - r:
        pos, vel = Vec2(pos.x, 2 * (c.FIELD_HEIGHT - r) - pos.y), Vec2(vel.x, -abs(vel.y))
    if walls[0] and pos.x < r:
        pos, vel = Vec2(2 * r - pos.x, pos.y), Vec2(abs(vel.x), vel.y)
    elif walls[1] and pos.x > c.FIELD_WIDTH - r:
        pos, vel = Vec2(2 * (c.FIELD_WIDTH - r) - pos.x, pos.y), Vec2(-abs(vel.x), vel.y)
    return pos, vel


def _lost(obs: Observation, pos: Vec2) -> bool:
    r = obs.ball_radius
    out = (pos.x < -r, pos.x > c.FIELD_WIDTH + r, pos.y < -r, pos.y > c.FIELD_HEIGHT + r)
    return any(o and not obs.walls[s] for s, o in enumerate(out))


def predict_intercept(obs: Observation, use_obstacles: bool = True) -> float | None:
    """@brief Where along its sliding axis the ball will cross the observer's paddle line.
    @param obs Current observation.
    @param use_obstacles Whether obstacles are simulated (walls always are).
    @return Coordinate along the paddle axis, or None if the ball will not arrive (it leaves
        through another goal or is still travelling after the horizon).
    """
    pos, vel = obs.ball_pos, obs.ball_vel
    if vel.length() == 0.0:
        return None
    rects: list[Rect] = []
    bumpers: list[bool] = []
    if use_obstacles:
        rects = [o.rect for o in obs.obstacles]
        bumpers = [o.kind == "bumper" for o in obs.obstacles]
    for _ in range(HORIZON_TICKS):
        time_left = c.DT
        for _sweep in range(MAX_SWEEPS):
            disp = vel * time_left
            best = None
            best_index = -1
            for index, rect in enumerate(rects):
                hit = sweep_circle_rect(pos, disp, obs.ball_radius, rect)
                if hit and (best is None or hit.t < best.t):
                    best, best_index = hit, index
            if best is None:
                break
            pos = pos + disp * best.t
            vel = reflect(vel, best.normal)
            if bumpers[best_index]:
                vel = vel * c.BUMPER_FACTOR
            time_left *= 1.0 - best.t
        else:
            time_left = 0.0
        pos = pos + vel * time_left
        pos, vel = _bounce_walls(obs, pos, vel)
        if _reached_line(obs, pos):
            return pos.y if obs.axis == "y" else pos.x
        if _lost(obs, pos):
            return None
    return None
