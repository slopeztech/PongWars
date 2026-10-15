"""@package pongwars.domain.extras.manager
@brief Pickups, active effects and weapon slots of a match.
"""

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pongwars.domain import constants as c
from pongwars.domain.config import ConfigError
from pongwars.domain.entities import Ball, Cat
from pongwars.domain.events import (
    CatPounced,
    EffectApplied,
    EffectExpired,
    Event,
    PickupCollected,
    PickupSpawned,
    ShieldUsed,
    WeaponEmpty,
)
from pongwars.domain.extras.base import CATEGORIES, EFFECTS, Effect, EffectSpec, Mods, load_specs
from pongwars.domain.extras.effects import opponents
from pongwars.domain.vec import Vec2

if TYPE_CHECKING:
    from pongwars.domain.world import World

ALL_EXTRAS = "all"


@dataclass
class Pickup:
    """@brief A collectible lying on the table."""

    pos: Vec2
    name: str
    ttl: int


class ExtrasManager:
    """@brief Owns every extras-related piece of match state; driven by the world each tick."""

    def __init__(self, world: "World") -> None:
        """@brief Create the manager for a match.
        @param world Match being played.
        @throws ConfigError If the configuration names an unknown extra.
        """
        self._world = world
        self.specs = load_specs()
        self.pickups: list[Pickup] = []
        self.cats: list[Cat] = []
        self.active: list[list[Effect]] = [[] for _ in range(world.players)]
        self.weapons: list[tuple[str, int] | None] = [None] * world.players
        self.spawn_names = self._spawnable(world.config.extras)
        self._spawn_timer = round(world.config.extras_interval * c.TICK_RATE)
        self._mods = [Mods() for _ in range(world.players)]

    def _spawnable(self, selection: tuple[str, ...]) -> list[str]:
        for item in selection:
            if item != ALL_EXTRAS and item not in CATEGORIES and item not in self.specs:
                raise ConfigError("error.config.unknown_extra", extra=item)
        return [
            name
            for name, spec in sorted(self.specs.items())
            if spec.weight > 0
            and (ALL_EXTRAS in selection or name in selection or spec.category in selection)
        ]

    def mods(self, player: int) -> Mods:
        """@brief Current modifiers of a player.
        @param player Seat index.
        @return The modifiers computed at the start of the tick.
        """
        return self._mods[player]

    def tick_effects(self, events: list[Event]) -> None:
        """@brief Age active effects, expire finished ones and recompute every player's modifiers.
        @param events Event list to append to.
        """
        for player, effects in enumerate(self.active):
            for effect in list(effects):
                effect.remaining -= 1
                if effect.remaining <= 0:
                    self._expire(player, effect, events)
            mods = Mods()
            for effect in effects:
                effect.modify(mods)
            self._mods[player] = mods

    def _expire(self, player: int, effect: Effect, events: list[Event]) -> None:
        self.active[player].remove(effect)
        events.append(EffectExpired(player, effect.name))

    def apply(self, name: str, player: int, events: list[Event]) -> None:
        """@brief Apply an effect as if `player` had collected it.

        Powers flagged `on_opponents` and penalties (when configured so) hit the opponents.
        @param name Registered effect name.
        @param player Collector (or direct victim for status effects).
        @param events Event list to append to.
        """
        effect_class = EFFECTS.get(name)
        spec = self.specs[name]
        targets = [player]
        penalty_to_others = (
            spec.category == "penalty" and self._world.config.penalty_target == "opponents"
        )
        if effect_class.on_opponents or penalty_to_others:
            targets = opponents(self._world, player)
        if effect_class.single_target:
            targets = targets[:1]
        for target in targets:
            self._apply_one(effect_class(spec), spec, target, events)

    def apply_direct(self, name: str, player: int, events: list[Event]) -> None:
        """@brief Apply an effect to exactly `player`, ignoring the penalty-target setting.
        @param name Registered effect name.
        @param player Seat that receives the effect.
        @param events Event list to append to.
        """
        self._apply_one(EFFECTS.get(name)(self.specs[name]), self.specs[name], player, events)

    def clear_penalties(self, player: int, events: list[Event]) -> None:
        """@brief Remove every penalty and status effect of a player.
        @param player Seat to cleanse.
        @param events Event list to append to.
        """
        for effect in list(self.active[player]):
            if effect.category in ("penalty", "status"):
                self._expire(player, effect, events)
        self._mods[player] = self._mods_of(player)

    def update_cats(self, events: list[Event]) -> None:
        """@brief Move every cat towards the nearest free ball and scramble it on contact.
        @param events Event list to append to.
        """
        world = self._world
        free = [ball for ball in world.balls if ball.held_by is None]
        for cat in list(self.cats):
            cat.ttl -= 1
            cat.cooldown = max(0, cat.cooldown - 1)
            if cat.ttl <= 0:
                self.cats.remove(cat)
                continue
            if not free:
                continue
            ball = min(free, key=lambda b: (b.pos - cat.pos).length())
            dist = (ball.pos - cat.pos).length()
            lead = min(dist / c.CAT_SPEED, 0.4)
            delta = ball.pos + ball.vel * lead - cat.pos
            reach = delta.length()
            if reach > 0.0:
                step = min(c.CAT_SPEED * c.DT, reach)
                cat.pos = cat.pos + delta * (step / reach)
            if cat.cooldown == 0 and dist <= c.CAT_RADIUS + ball.radius:
                self._pounce(cat, ball, events)

    def _pounce(self, cat: Cat, ball: Ball, events: list[Event]) -> None:
        rng = self._world.rng
        angle = rng.uniform(0.0, 2.0 * math.pi)
        factor = rng.uniform(c.CAT_MIN_SPEED_FACTOR, c.CAT_MAX_SPEED_FACTOR)
        speed = min(c.BALL_START_SPEED * factor, c.BALL_MAX_SPEED)
        ball.vel = Vec2.from_angle(angle, speed)
        ball.toucher = cat.owner
        cat.cooldown = c.CAT_COOLDOWN_TICKS
        events.append(CatPounced(ball.pos.x, ball.pos.y))

    def _apply_one(
        self, effect: Effect, spec: EffectSpec, player: int, events: list[Event]
    ) -> None:
        events.append(EffectApplied(player, spec.name))
        if spec.category == "weapon":
            slot = self.weapons[player]
            ammo = spec.ammo + (slot[1] if slot and slot[0] == spec.name else 0)
            self.weapons[player] = (spec.name, ammo)
        effect.on_apply(self._world, player, events)
        if not effect.lasting:
            return
        effects = self.active[player]
        for current in effects:
            if current.name == spec.name:
                current.remaining = effect.remaining
                return
        effects.append(effect)
        limited = [e for e in effects if e.category != "status"]
        if len(limited) > self._world.config.extras_max_active:
            self._expire(player, limited[0], events)
        self._mods[player] = self._mods_of(player)

    def _mods_of(self, player: int) -> Mods:
        mods = Mods()
        for effect in self.active[player]:
            effect.modify(mods)
        return mods

    def fire(self, player: int, events: list[Event]) -> None:
        """@brief Use the player's weapon.
        @param player Shooter seat.
        @param events Event list to append to.
        """
        slot = self.weapons[player]
        if slot is None or self._mods[player].jammed:
            events.append(WeaponEmpty(player))
            return
        name, ammo = slot
        EFFECTS.get(name)(self.specs[name]).fire(self._world, player, events)
        self.weapons[player] = (name, ammo - 1) if ammo > 1 else None

    def use_shield(self, player: int, events: list[Event]) -> bool:
        """@brief Consume the player's shield if they have one.
        @param player Seat about to concede.
        @param events Event list to append to.
        @return True if a shield absorbed the goal.
        """
        for effect in self.active[player]:
            if effect.name == "shield":
                self._expire(player, effect, events)
                self._mods[player] = self._mods_of(player)
                events.append(ShieldUsed(player))
                return True
        return False

    def update_pickups(self, events: list[Event]) -> None:
        """@brief Spawn, age and collect pickups.
        @param events Event list to append to.
        """
        if not self.spawn_names:
            return
        self._spawn_timer -= 1
        if self._spawn_timer <= 0:
            self._spawn_timer = round(self._world.config.extras_interval * c.TICK_RATE)
            if len(self.pickups) < c.PICKUP_MAX_ON_TABLE:
                self._spawn(events)
        for pickup in list(self.pickups):
            pickup.ttl -= 1
            owner = self._collector(pickup)
            if owner is not None:
                self.pickups.remove(pickup)
                events.append(PickupCollected(owner, pickup.name))
                self.apply(pickup.name, owner, events)
            elif pickup.ttl <= 0:
                self.pickups.remove(pickup)

    def _collector(self, pickup: Pickup) -> int | None:
        for ball in self._world.balls:
            toucher = ball.toucher
            if toucher is None or not self._world.alive[toucher]:
                continue
            if (ball.pos - pickup.pos).length() <= ball.radius + c.PICKUP_RADIUS:
                return toucher
        return None

    def _spawn(self, events: list[Event]) -> None:
        world = self._world
        weights = [self.specs[name].weight for name in self.spawn_names]
        roll = world.rng.randint(0, sum(weights) - 1)
        name = self.spawn_names[-1]
        for candidate, weight in zip(self.spawn_names, weights, strict=True):
            if roll < weight:
                name = candidate
                break
            roll -= weight
        pos = Vec2(c.FIELD_WIDTH / 2, c.FIELD_HEIGHT / 2)
        for _ in range(c.PICKUP_PLACEMENT_TRIES):
            pos = Vec2(
                world.rng.uniform(
                    c.FIELD_WIDTH * c.PICKUP_AREA_X[0], c.FIELD_WIDTH * c.PICKUP_AREA_X[1]
                ),
                world.rng.uniform(*c.PICKUP_AREA_Y),
            )
            if not self._blocked(pos):
                break
        self.pickups.append(Pickup(pos, name, c.PICKUP_LIFETIME_TICKS))
        events.append(PickupSpawned(name))

    def _blocked(self, pos: Vec2) -> bool:
        margin = c.PICKUP_RADIUS
        return any(
            abs(pos.x - o.rect.cx) <= o.rect.half_w + margin
            and abs(pos.y - o.rect.cy) <= o.rect.half_h + margin
            for o in self._world.obstacles
            if o.active
        )
