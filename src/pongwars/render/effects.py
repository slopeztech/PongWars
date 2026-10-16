"""@package pongwars.render.effects
@brief Purely visual effects: particles, ball trail and screen shake (never affect gameplay).
"""

import random
from collections import deque
from dataclasses import dataclass

from pongwars.render.palette import Color

GRAVITY = 60.0
MAX_PARTICLES = 256
TRAIL_LENGTH = 8
SHAKE_DECAY = 0.85
SHAKE_CUTOFF = 0.05
EXPLOSION_DURATION = 0.42


@dataclass
class Explosion:
    """@brief Short-lived expanding blast effect in table space."""

    x: float
    y: float
    elapsed: float = 0.0

    @property
    def progress(self) -> float:
        """@brief Normalized animation progress."""
        return min(1.0, self.elapsed / EXPLOSION_DURATION)

    def update(self, dt: float) -> None:
        """@brief Advance the animation."""
        self.elapsed += dt


@dataclass
class Particle:
    """@brief A single sparkle in table space."""

    x: float
    y: float
    z: float
    vx: float
    vy: float
    vz: float
    life: float
    color: Color


class ParticleSystem:
    """@brief Bounded pool of short-lived particles."""

    def __init__(self, seed: int = 0) -> None:
        """@brief Create the pool.
        @param seed Seed of the private visual RNG.
        """
        self._rng = random.Random(seed)  # noqa: S311 - visual only
        self.particles: list[Particle] = []

    def burst(self, x: float, y: float, color: Color, count: int = 10, speed: float = 40.0) -> None:
        """@brief Emit a burst of particles.
        @param x Table x.
        @param y Table y.
        @param color Particle colour.
        @param count Number of particles.
        @param speed Initial speed scale.
        """
        for _ in range(count):
            if len(self.particles) >= MAX_PARTICLES:
                return
            self.particles.append(
                Particle(
                    x,
                    y,
                    1.0,
                    self._rng.uniform(-speed, speed),
                    self._rng.uniform(-speed, speed),
                    self._rng.uniform(0.0, speed),
                    self._rng.uniform(0.3, 0.7),
                    color,
                )
            )

    def update(self, dt: float) -> None:
        """@brief Advance and cull particles.
        @param dt Elapsed seconds.
        """
        alive: list[Particle] = []
        for p in self.particles:
            p.life -= dt
            if p.life <= 0.0:
                continue
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vz -= GRAVITY * dt
            p.z = max(0.0, p.z + p.vz * dt)
            alive.append(p)
        self.particles = alive


class Trail:
    """@brief Fixed-length history of recent ball positions."""

    def __init__(self, length: int = TRAIL_LENGTH) -> None:
        """@brief Create the trail.
        @param length Number of remembered positions.
        """
        self.points: deque[tuple[float, float]] = deque(maxlen=length)

    def push(self, x: float, y: float) -> None:
        """@brief Record a position.
        @param x Table x.
        @param y Table y.
        """
        self.points.append((x, y))

    def clear(self) -> None:
        """@brief Forget all positions (e.g. after a serve)."""
        self.points.clear()


class Shake:
    """@brief Decaying screen-shake offset."""

    def __init__(self, seed: int = 0) -> None:
        """@brief Create the shaker.
        @param seed Seed of the private visual RNG.
        """
        self._rng = random.Random(seed)  # noqa: S311 - visual only
        self.amplitude = 0.0

    def trigger(self, strength: float) -> None:
        """@brief Start or strengthen a shake.
        @param strength Peak offset in pixels.
        """
        self.amplitude = max(self.amplitude, strength)

    def update(self) -> tuple[int, int]:
        """@brief Advance one frame.
        @return Pixel offset to apply to the whole frame.
        """
        if self.amplitude < SHAKE_CUTOFF:
            self.amplitude = 0.0
            return (0, 0)
        offset = (
            round(self._rng.uniform(-self.amplitude, self.amplitude)),
            round(self._rng.uniform(-self.amplitude, self.amplitude)),
        )
        self.amplitude *= SHAKE_DECAY
        return offset
