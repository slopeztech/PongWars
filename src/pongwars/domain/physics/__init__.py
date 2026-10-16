"""@package pongwars.domain.physics
@brief Swept collision of a circle (ball) against rectangles; prevents tunneling.
"""

import math
from dataclasses import dataclass

from pongwars.domain.constants import EPSILON
from pongwars.domain.entities import Rect
from pongwars.domain.vec import Vec2


@dataclass(frozen=True)
class Hit:
    """@brief Result of a sweep: fraction t in [0, 1] of the displacement and surface normal."""

    t: float
    normal: Vec2


def sweep_circle_circle(pos: Vec2, disp: Vec2, center: Vec2, radius: float) -> float | None:
    """@brief First contact fraction for a moving circle and a stationary circle."""
    a = disp.x * disp.x + disp.y * disp.y
    if a <= EPSILON:
        return None
    offset = pos - center
    c0 = offset.x * offset.x + offset.y * offset.y - radius * radius
    if c0 <= 0.0:
        return 0.0
    b = 2.0 * (offset.x * disp.x + offset.y * disp.y)
    discriminant = b * b - 4.0 * a * c0
    if discriminant < 0.0:
        return None
    t = (-b - math.sqrt(discriminant)) / (2.0 * a)
    return t if 0.0 <= t <= 1.0 else None


def sweep_circle_rect(pos: Vec2, disp: Vec2, radius: float, rect: Rect) -> Hit | None:
    """@brief First contact of a moving circle with a rectangle.
    @param pos Circle center at the start.
    @param disp Displacement over the step.
    @param radius Circle radius.
    @param rect Target rectangle.
    @return The hit, or None if no contact (or the circle is moving away).
    """
    # Minkowski sum: circle vs rect == point vs rect grown by the radius.
    mins = (rect.cx - rect.half_w - radius, rect.cy - rect.half_h - radius)
    maxs = (rect.cx + rect.half_w + radius, rect.cy + rect.half_h + radius)
    start = (pos.x, pos.y)
    delta = (disp.x, disp.y)
    t_enter, t_exit = 0.0, 1.0
    normal = Vec2()
    for axis in (0, 1):
        if abs(delta[axis]) < EPSILON:
            if start[axis] < mins[axis] or start[axis] > maxs[axis]:
                return None
            continue
        t1 = (mins[axis] - start[axis]) / delta[axis]
        t2 = (maxs[axis] - start[axis]) / delta[axis]
        sign = -1.0 if delta[axis] > 0 else 1.0
        if t1 > t2:
            t1, t2 = t2, t1
        if t1 > t_enter:
            t_enter = t1
            normal = Vec2(sign, 0.0) if axis == 0 else Vec2(0.0, sign)
        t_exit = min(t_exit, t2)
        if t_enter > t_exit:
            return None
    if normal == Vec2():
        # Started inside the grown rectangle (e.g. a moving obstacle reached the ball).
        gaps = (
            (start[0] - mins[0], Vec2(-1.0, 0.0)),
            (maxs[0] - start[0], Vec2(1.0, 0.0)),
            (start[1] - mins[1], Vec2(0.0, -1.0)),
            (maxs[1] - start[1], Vec2(0.0, 1.0)),
        )
        normal = min(gaps, key=lambda g: g[0])[1]
        if disp.x * normal.x + disp.y * normal.y >= 0:
            return None
        return Hit(0.0, normal)
    return Hit(t_enter, normal)


def reflect(vel: Vec2, normal: Vec2) -> Vec2:
    """@brief Reflect a velocity about a unit normal."""
    dot = vel.x * normal.x + vel.y * normal.y
    return Vec2(vel.x - 2 * dot * normal.x, vel.y - 2 * dot * normal.y)
