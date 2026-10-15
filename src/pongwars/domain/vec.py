"""@package pongwars.domain.vec
@brief Minimal immutable 2D vector.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Vec2:
    """@brief Immutable 2D vector of floats."""

    x: float = 0.0
    y: float = 0.0

    def __add__(self, other: "Vec2") -> "Vec2":
        """@brief Component-wise sum."""
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vec2") -> "Vec2":
        """@brief Component-wise difference."""
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, k: float) -> "Vec2":
        """@brief Scale by a scalar."""
        return Vec2(self.x * k, self.y * k)

    def length(self) -> float:
        """@brief Euclidean length."""
        return math.hypot(self.x, self.y)

    @staticmethod
    def from_angle(angle: float, length: float = 1.0) -> "Vec2":
        """@brief Vector from polar coordinates.
        @param angle Angle in radians (0 = +x).
        @param length Vector length.
        """
        return Vec2(math.cos(angle) * length, math.sin(angle) * length)
