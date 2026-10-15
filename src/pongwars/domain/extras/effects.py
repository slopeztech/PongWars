"""@package pongwars.domain.extras.effects
@brief Built-in powers, weapons, penalties and status effects.
"""

import math
from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

from pongwars.domain import constants as c
from pongwars.domain.entities import Ball, Rect
from pongwars.domain.events import BombDetonated, Event, LaserFired
from pongwars.domain.extras.base import EFFECTS, Effect, Mods
from pongwars.domain.vec import Vec2

if TYPE_CHECKING:
    from pongwars.domain.world import World

E = TypeVar("E", bound=type[Effect])
SHOT_DIRECTIONS = ((1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0))  # per seat, towards the table


def _register(name: str, category: str) -> Callable[[E], E]:
    def decorator(cls: E) -> E:
        cls.name = name
        cls.category = category
        EFFECTS.add(name, cls)
        return cls

    return decorator


def opponents(world: "World", player: int) -> list[int]:
    """@brief Alive seats other than `player`, in seat order starting after `player`.
    @param world Match being played.
    @param player Reference seat.
    @return The opponents' seats.
    """
    order = [(player + step) % world.players for step in range(1, world.players)]
    return [seat for seat in order if world.alive[seat]]


def ray_rect(ox: float, oy: float, dx: float, dy: float, rect: Rect) -> float | None:
    """@brief Distance along an axis-aligned ray to a rectangle.
    @param ox Ray origin x.
    @param oy Ray origin y.
    @param dx Direction x (-1, 0 or 1).
    @param dy Direction y (-1, 0 or 1).
    @param rect Target rectangle.
    @return The distance to the near face, or None when the ray misses.
    """
    if dx != 0.0:
        if abs(oy - rect.cy) > rect.half_h:
            return None
        near = (rect.cx - dx * rect.half_w - ox) * dx
        far = (rect.cx + dx * rect.half_w - ox) * dx
    else:
        if abs(ox - rect.cx) > rect.half_w:
            return None
        near = (rect.cy - dy * rect.half_h - oy) * dy
        far = (rect.cy + dy * rect.half_h - oy) * dy
    return None if far < 0.0 else max(near, 0.0)


@_register("big_paddle", "power")
class BigPaddle(Effect):
    """@brief Enlarges the owner's paddle."""

    def modify(self, mods: Mods) -> None:
        """@brief Grow the paddle."""
        mods.size_scale *= self.spec.magnitude


@_register("speed_boost", "power")
class SpeedBoost(Effect):
    """@brief Makes the owner's paddle faster."""

    def modify(self, mods: Mods) -> None:
        """@brief Speed the paddle up."""
        mods.speed_scale *= self.spec.magnitude


@_register("magnet", "power")
class Magnet(Effect):
    """@brief The owner's paddle catches the ball; fire (or a timeout) releases it."""

    def modify(self, mods: Mods) -> None:
        """@brief Enable catching."""
        mods.magnet = True


@_register("shield", "power")
class Shield(Effect):
    """@brief Bounces back the next ball that would score against the owner."""

    def modify(self, mods: Mods) -> None:
        """@brief Enable the shield."""
        mods.shield = True


@_register("multiball", "power")
class Multiball(Effect):
    """@brief Splits the main ball into several balls."""

    lasting = False

    def on_apply(self, world: "World", player: int, events: list[Event]) -> None:
        """@brief Add two clones of the main ball, diverging from it.
        @param world Match being played.
        @param player Collector (credited as the clones' last toucher).
        @param events Unused.
        """
        main = world.ball
        speed = main.vel.length()
        if speed == 0.0 or main.held_by is not None:
            return
        base = math.atan2(main.vel.y, main.vel.x)
        for sign in (-1.0, 1.0):
            if len(world.balls) >= c.MAX_BALLS:
                return
            vel = Vec2.from_angle(base + sign * c.MULTIBALL_SPREAD, speed)
            world.extra_balls.append(Ball(main.pos, vel, main.radius, toucher=player))


@_register("slow_mo", "power")
class SlowMo(Effect):
    """@brief Slows the owner's opponents."""

    on_opponents = True

    def modify(self, mods: Mods) -> None:
        """@brief Slow the paddle."""
        mods.speed_scale *= self.spec.magnitude


@_register("small_paddle", "penalty")
class SmallPaddle(Effect):
    """@brief Shrinks the paddle."""

    def modify(self, mods: Mods) -> None:
        """@brief Shrink the paddle."""
        mods.size_scale *= self.spec.magnitude


@_register("inverted", "penalty")
class Inverted(Effect):
    """@brief Reverses the paddle controls."""

    def modify(self, mods: Mods) -> None:
        """@brief Invert the controls."""
        mods.invert = True


@_register("slow_paddle", "penalty")
class SlowPaddle(Effect):
    """@brief Slows the paddle down."""

    def modify(self, mods: Mods) -> None:
        """@brief Slow the paddle."""
        mods.speed_scale *= self.spec.magnitude


@_register("blind", "penalty")
class Blind(Effect):
    """@brief Hides the table from the affected player's view (rendering only)."""

    def modify(self, mods: Mods) -> None:
        """@brief Flag the player as blind."""
        mods.blind = True


@_register("stun", "status")
class Stun(Effect):
    """@brief The paddle cannot move (laser hit)."""

    def modify(self, mods: Mods) -> None:
        """@brief Freeze the paddle."""
        mods.frozen = True


@_register("frozen", "status")
class Frozen(Effect):
    """@brief The paddle cannot move (freeze weapon)."""

    def modify(self, mods: Mods) -> None:
        """@brief Freeze the paddle."""
        mods.frozen = True


@_register("laser", "weapon")
class Laser(Effect):
    """@brief Hitscan shot: damages the first destructible obstacle or stuns the first paddle."""

    lasting = False

    def fire(self, world: "World", player: int, events: list[Event]) -> None:
        """@brief Shoot across the table.
        @param world Match being played.
        @param player Shooter seat.
        @param events Event list to append to.
        """
        paddle = world.paddles[player]
        ox, oy = paddle.rect.cx, paddle.rect.cy
        dx, dy = SHOT_DIRECTIONS[player]
        best = math.hypot(c.FIELD_WIDTH, c.FIELD_HEIGHT)
        obstacle = -1
        victim = -1
        for index, item in enumerate(world.obstacles):
            dist = ray_rect(ox, oy, dx, dy, item.rect) if item.active else None
            if dist is not None and dist < best:
                best, obstacle, victim = dist, index, -1
        for seat in opponents(world, player):
            dist = ray_rect(ox, oy, dx, dy, world.paddles[seat].rect)
            if dist is not None and dist < best:
                best, obstacle, victim = dist, -1, seat
        if obstacle >= 0:
            world.damage_obstacle(obstacle, events)
        elif victim >= 0:
            world.extras.apply("stun", victim, events)
        events.append(LaserFired(player, ox + dx * best, oy + dy * best))


@_register("freeze", "weapon")
class Freeze(Effect):
    """@brief Freezes the next alive opponent's paddle."""

    lasting = False

    def fire(self, world: "World", player: int, events: list[Event]) -> None:
        """@brief Freeze an opponent.
        @param world Match being played.
        @param player Shooter seat.
        @param events Event list to append to.
        """
        targets = opponents(world, player)
        if targets:
            world.extras.apply("frozen", targets[0], events)


@_register("bomb", "weapon")
class Bomb(Effect):
    """@brief Blasts away every ball close to the owner's paddle."""

    lasting = False

    def fire(self, world: "World", player: int, events: list[Event]) -> None:
        """@brief Detonate next to the paddle.
        @param world Match being played.
        @param player Shooter seat.
        @param events Event list to append to.
        """
        centre = Vec2(world.paddles[player].rect.cx, world.paddles[player].rect.cy)
        for ball in world.balls:
            delta = ball.pos - centre
            dist = delta.length()
            if dist >= c.BOMB_RADIUS:
                continue
            inward = Vec2(*SHOT_DIRECTIONS[player])
            heading = inward if dist == 0.0 else delta * (1.0 / dist)
            speed = min(
                max(ball.vel.length(), ball.stored_vel.length(), c.BALL_START_SPEED)
                * c.BOMB_IMPULSE,
                c.BALL_MAX_SPEED,
            )
            ball.vel = heading * speed
            ball.held_by = None
        events.append(BombDetonated(player))
