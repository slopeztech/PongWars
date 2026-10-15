"""@package pongwars.domain.rng
@brief Seeded random source so simulations are reproducible.
"""

import random


class RandomSource:
    """@brief Deterministic pseudo-random generator (the only source of randomness)."""

    def __init__(self, seed: int) -> None:
        """@brief Create a generator.
        @param seed Integer seed.
        """
        self._rng = random.Random(seed)

    def uniform(self, low: float, high: float) -> float:
        """@brief Float in [low, high]."""
        return self._rng.uniform(low, high)

    def randint(self, low: int, high: int) -> int:
        """@brief Integer in [low, high], both inclusive."""
        return self._rng.randint(low, high)

    def choice(self, items: list[int]) -> int:
        """@brief Pick one element of a non-empty list."""
        return self._rng.choice(items)
