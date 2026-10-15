"""@package pongwars.domain.events
@brief Typed events emitted by the simulation (consumed by audio, render and UI).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    """@brief Base class of all simulation events."""


@dataclass(frozen=True)
class Served(Event):
    """@brief The ball was launched."""


@dataclass(frozen=True)
class PaddleHit(Event):
    """@brief The ball bounced off a paddle. @param player Paddle index (0 = left)."""

    player: int


@dataclass(frozen=True)
class WallHit(Event):
    """@brief The ball bounced off a wall or the field border."""


@dataclass(frozen=True)
class Goal(Event):
    """@brief The ball crossed a goal line.
    @param scorer Player credited with the point, or None when nobody scores.
    @param conceded Player whose goal was crossed.
    """

    scorer: int | None
    conceded: int


@dataclass(frozen=True)
class PlayerEliminated(Event):
    """@brief A player is out; their goal turns into a wall. @param player Player index."""

    player: int


@dataclass(frozen=True)
class MatchEnded(Event):
    """@brief The match is over. @param winner Index of the winning player."""

    winner: int


@dataclass(frozen=True)
class BumperHit(Event):
    """@brief The ball hit a bumper. @param index Obstacle index."""

    index: int


@dataclass(frozen=True)
class ObstacleDestroyed(Event):
    """@brief A destructible obstacle lost its last hit point. @param index Obstacle index."""

    index: int


@dataclass(frozen=True)
class PickupSpawned(Event):
    """@brief A pickup appeared on the table. @param name Effect name."""

    name: str


@dataclass(frozen=True)
class PickupCollected(Event):
    """@brief A player collected a pickup. @param player Collector. @param name Effect name."""

    player: int
    name: str


@dataclass(frozen=True)
class EffectApplied(Event):
    """@brief An effect started on a player. @param player Affected seat. @param name Effect."""

    player: int
    name: str


@dataclass(frozen=True)
class EffectExpired(Event):
    """@brief An effect ended. @param player Affected seat. @param name Effect."""

    player: int
    name: str


@dataclass(frozen=True)
class LaserFired(Event):
    """@brief A laser shot. @param player Shooter. @param x Impact x. @param y Impact y."""

    player: int
    x: float
    y: float


@dataclass(frozen=True)
class WeaponEmpty(Event):
    """@brief A player tried to fire without ammo. @param player Seat index."""

    player: int


@dataclass(frozen=True)
class ShieldUsed(Event):
    """@brief A shield saved a goal. @param player Protected seat."""

    player: int


@dataclass(frozen=True)
class BombDetonated(Event):
    """@brief A bomb went off next to a paddle. @param player Owner of the bomb."""

    player: int


@dataclass(frozen=True)
class CatReleased(Event):
    """@brief A cat was dropped on the table. @param player Owner of the cat."""

    player: int


@dataclass(frozen=True)
class CatPounced(Event):
    """@brief A cat scrambled a ball's direction and speed. @param x Ball x. @param y Ball y."""

    x: float
    y: float


@dataclass(frozen=True)
class BallWarped(Event):
    """@brief A ball was teleported. @param x New x. @param y New y."""

    x: float
    y: float


@dataclass(frozen=True)
class SuddenDeath(Event):
    """@brief Time ran out on a tie; the next goal wins."""
