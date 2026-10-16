"""@package pongwars.domain.extras.effects
@brief Built-in powers, weapons, penalties and status effects.
"""

import math
from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

from pongwars.domain import constants as c
from pongwars.domain.entities import Ball, Cat, Companion, Invader, Missile, Paddle, Rect
from pongwars.domain.events import (
    BallWarped,
    BombDetonated,
    CatReleased,
    Event,
    LaserFired,
)
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


def _paddle_inner_direction(player: int) -> Vec2:
    return Vec2(*SHOT_DIRECTIONS[player])


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


@_register("ramp", "penalty")
class Ramp(Effect):
    """@brief Tilts the court toward the affected player and changes ball gravity."""


@_register("invasor", "penalty")
class Invasor(Effect):
    """@brief Sends a slow-moving invader to harass the penalized player's paddle."""

    def on_apply(self, world: "World", player: int, events: list[Event]) -> None:
        """@brief Spawn an invader on the far side of the penalized player."""
        for invader in world.extras.invaders:
            if invader.target == player:
                invader.ttl = self.spec.ticks
                return
        alternatives = opponents(world, player)
        if not alternatives:
            return
        opponent = world.paddles[alternatives[0]].rect
        inward = -1.0 if opponent.cx > c.FIELD_WIDTH / 2 else 1.0
        anchor = Vec2(opponent.cx + inward * 18.0, c.FIELD_HEIGHT / 2)
        world.extras.invaders.append(
            Invader(
                anchor,
                player,
                self.spec.ticks,
                1,
                c.INVADER_BOMBS_PER_EFFECT,
                world.rng.uniform(0.0, math.tau),
                anchor,
            )
        )

    def on_expire(self, world: "World", player: int, events: list[Event]) -> None:
        """@brief Remove the invader when its penalty ends or is cleansed."""
        world.extras.invaders = [
            invader for invader in world.extras.invaders if invader.target != player
        ]


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
        events.append(
            LaserFired(player, ox + dx * best, oy + dy * best, victim if victim >= 0 else None)
        )


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
        events.append(BombDetonated(player, centre.x, centre.y))


def _scale_balls(world: "World", factor: float) -> None:
    for ball in world.balls:
        if ball.held_by is not None:
            continue
        speed = ball.vel.length()
        if speed > 0.0:
            ball.vel = ball.vel * (
                min(max(speed * factor, c.BALL_MIN_SPEED), c.BALL_MAX_SPEED) / speed
            )


@_register("aim_assist", "power")
class AimAssist(Effect):
    """@brief The owner's paddle bounces the ball towards the next opponent."""

    def modify(self, mods: Mods) -> None:
        """@brief Enable aiming."""
        mods.aim = True


@_register("cleanse", "power")
class Cleanse(Effect):
    """@brief Removes every penalty and status effect from the owner."""

    lasting = False

    def on_apply(self, world: "World", player: int, events: list[Event]) -> None:
        """@brief Purge the owner's penalties.
        @param world Match being played.
        @param player Collector.
        @param events Event list to append to.
        """
        world.extras.clear_penalties(player, events)


@_register("slow_ball", "power")
class SlowBall(Effect):
    """@brief Slows every ball down."""

    lasting = False

    def on_apply(self, world: "World", player: int, events: list[Event]) -> None:
        """@brief Reduce the ball speed.
        @param world Match being played.
        @param player Unused.
        @param events Unused.
        """
        _scale_balls(world, c.SLOW_BALL_FACTOR)


@_register("turbo_ball", "penalty")
class TurboBall(Effect):
    """@brief Speeds every ball up."""

    lasting = False
    single_target = True

    def on_apply(self, world: "World", player: int, events: list[Event]) -> None:
        """@brief Increase the ball speed.
        @param world Match being played.
        @param player Unused.
        @param events Unused.
        """
        _scale_balls(world, c.TURBO_BALL_FACTOR)


@_register("drunk", "penalty")
class Drunk(Effect):
    """@brief The paddle sways on its own."""

    def modify(self, mods: Mods) -> None:
        """@brief Make the paddle wobble."""
        mods.drunk = True


@_register("jammed", "penalty")
class Jammed(Effect):
    """@brief Weapons cannot be fired."""

    def modify(self, mods: Mods) -> None:
        """@brief Block weapons."""
        mods.jammed = True


@_register("cat", "weapon")
class CatWeapon(Effect):
    """@brief Releases a cat that chases the ball and scrambles its direction and speed."""

    lasting = False

    def fire(self, world: "World", player: int, events: list[Event]) -> None:
        """@brief Drop the cat in front of the owner's paddle.
        @param world Match being played.
        @param player Owner seat.
        @param events Event list to append to.
        """
        rect = world.paddles[player].rect
        dx, dy = SHOT_DIRECTIONS[player]
        pos = Vec2(
            rect.cx + dx * (rect.half_w + c.CAT_RADIUS), rect.cy + dy * (rect.half_h + c.CAT_RADIUS)
        )
        world.extras.cats.append(
            Cat(pos, player, round(world.extras.specs["cat"].duration * c.TICK_RATE))
        )
        events.append(CatReleased(player))


@_register("hex", "weapon")
class Hex(Effect):
    """@brief Curses the next opponent with a random lasting penalty."""

    lasting = False

    def fire(self, world: "World", player: int, events: list[Event]) -> None:
        """@brief Cast the curse.
        @param world Match being played.
        @param player Caster seat.
        @param events Event list to append to.
        """
        targets = opponents(world, player)
        curses = sorted(
            name
            for name, spec in world.extras.specs.items()
            if spec.category == "penalty" and EFFECTS.get(name).lasting
        )
        if targets and curses:
            world.extras.apply_direct(
                curses[world.rng.randint(0, len(curses) - 1)], targets[0], events
            )


@_register("warp", "weapon")
class Warp(Effect):
    """@brief Teleports every free ball to a random spot, keeping its velocity."""

    lasting = False

    def fire(self, world: "World", player: int, events: list[Event]) -> None:
        """@brief Warp the balls.
        @param world Match being played.
        @param player Unused.
        @param events Event list to append to.
        """
        for ball in world.balls:
            if ball.held_by is not None:
                continue
            x = world.rng.uniform(c.WARP_MARGIN, c.FIELD_WIDTH - c.WARP_MARGIN)
            y = world.rng.uniform(c.WARP_MARGIN, c.FIELD_HEIGHT - c.WARP_MARGIN)
            ball.pos = Vec2(x, y)
            events.append(BallWarped(x, y))


@_register("companion", "power")
class CompanionPower(Effect):
    """@brief Adds a temporary AI mini-paddle that helps defend the owner's goal."""

    def on_apply(self, world: "World", player: int, events: list[Event]) -> None:
        """@brief Create or refresh the owner's helper paddle.
        @param world Match being played.
        @param player Collector.
        @param events Unused.
        """
        paddle = world.paddles[player]
        toward = _paddle_inner_direction(player)
        x = paddle.rect.cx + toward.x * c.COMPANION_OFFSET
        y = paddle.rect.cy + toward.y * c.COMPANION_OFFSET
        if paddle.axis == "y":
            rect = Rect(
                x,
                y,
                paddle.rect.half_w * 0.65,
                c.COMPANION_HALF_LENGTH,
            )
        else:
            rect = Rect(
                x,
                y,
                c.COMPANION_HALF_LENGTH,
                paddle.rect.half_h * 0.65,
            )
        world.extras.companions = [ally for ally in world.extras.companions if ally.owner != player]
        world.extras.companions.append(
            Companion(Paddle(rect, paddle.axis), player, self.spec.ticks)
        )


@_register("headbutt", "weapon")
class Headbutt(Effect):
    """@brief Lunges the owner's paddle forward for a short time."""

    lasting = False

    def fire(self, world: "World", player: int, events: list[Event]) -> None:
        """@brief Extend the paddle's forward reach briefly.
        @param world Match being played.
        @param player Shooter.
        @param events Unused.
        """
        world.start_headbutt(player)


@_register("missile", "weapon")
class MissileWeapon(Effect):
    """@brief Fires two missiles aimed at opponents that damage destructibles."""

    lasting = False

    def fire(self, world: "World", player: int, events: list[Event]) -> None:
        """@brief Launch a missile at the nearest living opponent.
        @param world Match being played.
        @param player Shooter.
        @param events Unused.
        """
        targets = opponents(world, player)
        if not targets:
            return
        paddle = world.paddles[player]
        origin = Vec2(paddle.rect.cx, paddle.rect.cy)
        target = min(
            targets,
            key=lambda seat: (
                Vec2(world.paddles[seat].rect.cx, world.paddles[seat].rect.cy) - origin
            ).length(),
        )
        delta = Vec2(
            world.paddles[target].rect.cx - origin.x,
            world.paddles[target].rect.cy - origin.y,
        )
        length = delta.length()
        if length == 0.0:
            return
        direction = delta * (1.0 / length)
        offset = paddle.rect.half_w if abs(direction.x) >= abs(direction.y) else paddle.rect.half_h
        pos = origin + direction * (offset + c.MISSILE_RADIUS + 1.0)
        world.extras.missiles.append(
            Missile(
                pos,
                direction * c.MISSILE_SPEED,
                player,
                c.MISSILE_TTL_TICKS,
                c.MISSILE_RADIUS,
            )
        )
