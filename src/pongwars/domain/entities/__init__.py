"""@package pongwars.domain.entities
@brief Mutable simulation entities: paddle, ball and rectangular obstacle.
"""

import math
from dataclasses import dataclass, field

from pongwars.domain.vec import Vec2

OBSTACLE_KINDS = ("solid", "bumper", "destructible")


@dataclass
class Rect:
    """@brief Axis-aligned rectangle given by its center and half sizes."""

    cx: float
    cy: float
    half_w: float
    half_h: float


@dataclass
class Paddle:
    """@brief Player paddle; slides along its goal line (vertical "y" or horizontal "x")."""

    rect: Rect
    axis: str = "y"
    headbutt_offset: float = 0.0
    headbutt_ticks: int = 0

    def __post_init__(self) -> None:
        """@brief Remember the unmodified half length."""
        self.base_half = self.rect.half_h if self.axis == "y" else self.rect.half_w

    def resize(self, scale: float, field_size: float) -> None:
        """@brief Set the half length to `scale` times the base and keep the paddle in the field.
        @param scale Size multiplier.
        @param field_size Field extent along the paddle axis.
        """
        if self.axis == "y":
            self.rect.half_h = self.base_half * scale
        else:
            self.rect.half_w = self.base_half * scale
        self.move(0.0, field_size)

    def move(self, delta: float, field_size: float) -> None:
        """@brief Slide along the paddle axis, clamped inside the field.
        @param delta Displacement in world units.
        @param field_size Field extent along the paddle axis.
        """
        if self.axis == "y":
            half = self.rect.half_h
            self.rect.cy = min(max(self.rect.cy + delta, half), field_size - half)
        else:
            half = self.rect.half_w
            self.rect.cx = min(max(self.rect.cx + delta, half), field_size - half)


@dataclass
class Ball:
    """@brief The ball (a circle).

    `toucher` is the last player to hit it. While a magnet holds the ball, `held_by` is that
    player, `stored_vel` is the velocity to restore and `hold_offset` is the distance from the
    paddle center along the paddle axis.
    """

    pos: Vec2
    vel: Vec2
    radius: float
    toucher: int | None = None
    held_by: int | None = None
    hold_ticks: int = 0
    hold_offset: float = 0.0
    stored_vel: Vec2 = field(default_factory=Vec2)
    rotation: float = 0.0
    spin_rate: float = 0.0


@dataclass
class Cat:
    """@brief A cat released by a weapon: chases the nearest ball and scrambles it on contact.

    `cooldown` counts the ticks left before the cat may pounce again.
    """

    pos: Vec2
    owner: int
    ttl: int
    cooldown: int = 0


@dataclass
class Companion:
    """@brief Temporary AI-controlled mini-paddle that protects its owner's goal."""

    paddle: Paddle
    owner: int
    ttl: int


@dataclass
class Missile:
    """@brief Projectile that hits paddles and can damage destructible obstacles."""

    pos: Vec2
    vel: Vec2
    owner: int
    ttl: int
    radius: float
    target: int | None = None
    kind: str = "missile"


@dataclass
class Invader:
    """@brief Wandering penalty NPC that launches a limited number of bombs."""

    pos: Vec2
    target: int
    ttl: int
    fire_timer: int
    bombs_left: int
    phase: float
    anchor: Vec2


@dataclass
class Obstacle:
    """@brief Rectangular obstacle: solid, bumper or destructible; optionally patrolling."""

    rect: Rect
    kind: str = "solid"
    hp: int = 0
    patrol: Vec2 = field(default_factory=Vec2)
    period: int = 0
    active: bool = True
    orbit: bool = False

    def __post_init__(self) -> None:
        """@brief Remember the home position used by the patrol path."""
        self.home = Vec2(self.rect.cx, self.rect.cy)

    def update(self, tick: int) -> None:
        """@brief Place the obstacle on its patrol path (a pure function of the tick).
        @param tick Simulation tick.
        """
        if self.period <= 0:
            return
        phase = math.sin(2.0 * math.pi * tick / self.period)
        if self.orbit:
            angle = 2.0 * math.pi * tick / self.period
            self.rect.cx = self.home.x + self.patrol.x * math.cos(angle)
            self.rect.cy = self.home.y + self.patrol.y * math.sin(angle)
        else:
            self.rect.cx = self.home.x + self.patrol.x * phase
            self.rect.cy = self.home.y + self.patrol.y * phase
