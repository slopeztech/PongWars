"""@package pongwars.domain.extras.manager
@brief Pickups, active effects and weapon slots of a match.
"""

import math
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from pongwars.domain import constants as c
from pongwars.domain.config import ConfigError
from pongwars.domain.entities import Ball, Cat, Chomper, Companion, Invader, Missile, Stalker
from pongwars.domain.events import (
    BallReleased,
    BallSwallowed,
    CatPounced,
    EffectApplied,
    EffectExpired,
    Event,
    MissileHit,
    PickupCollected,
    PickupSpawned,
    ShieldUsed,
    StalkerExploded,
    WeaponEmpty,
)
from pongwars.domain.extras.base import CATEGORIES, EFFECTS, Effect, EffectSpec, Mods, load_specs
from pongwars.domain.extras.effects import opponents
from pongwars.domain.physics import sweep_circle_rect
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
    target: int | None = None
    reduced: bool = False


class ExtrasManager:
    """@brief Owns every extras-related piece of match state; driven by the world each tick."""

    def __init__(self, world: "World") -> None:
        """@brief Create the manager for a match.
        @param world Match being played.
        @throws ConfigError If the configuration names an unknown extra.
        """
        self._world = world
        self.specs = load_specs()
        self.auto_spawn_enabled = True
        self.pickups: list[Pickup] = []
        self.cats: list[Cat] = []
        self.companions: list[Companion] = []
        self.invaders: list[Invader] = []
        self.missiles: list[Missile] = []
        self.stalkers: list[Stalker] = []
        self.chompers: list[Chomper] = []
        self.active: list[list[Effect]] = [[] for _ in range(world.players)]
        self.weapons: list[tuple[str, int] | None] = [None] * world.players
        self.spawn_names = self._spawnable(world.config.extras)
        self._spawn_timer = round(world.config.extras_interval * c.TICK_RATE)
        self._comeback_timer = c.COMEBACK_PICKUP_INTERVAL_TICKS
        self._comeback_penalty_next = False
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
            and (name != "ramp" or self._world.players == 2)
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
        effect.on_expire(self._world, player, events)
        events.append(EffectExpired(player, effect.name))

    def apply(self, name: str, player: int, events: list[Event], reduced: bool = False) -> None:
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
            self._apply_one(effect_class(spec), spec, target, events, reduced)

    def apply_direct(
        self, name: str, player: int, events: list[Event], reduced: bool = False
    ) -> None:
        """@brief Apply an effect to exactly `player`, ignoring the penalty-target setting.
        @param name Registered effect name.
        @param player Seat that receives the effect.
        @param events Event list to append to.
        """
        self._apply_one(
            EFFECTS.get(name)(self.specs[name]), self.specs[name], player, events, reduced
        )

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
        free = [ball for ball in world.balls if ball.held_by is None and not ball.swallowed]
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

    def spawn_chomper(self, owner: int) -> None:
        """@brief Spawn a hungry orb that roams before chasing the nearest free ball.
        @param owner Player credited with collecting the power.
        """
        world = self._world
        free = [ball for ball in world.balls if ball.held_by is None and not ball.swallowed]
        if not free:
            return
        center = Vec2(c.FIELD_WIDTH / 2, c.FIELD_HEIGHT / 2)
        ball = min(free, key=lambda item: (item.pos - center).length())
        pos = None
        for _ in range(c.PICKUP_PLACEMENT_TRIES * 2):
            angle = world.rng.uniform(0.0, math.tau)
            distance = world.rng.uniform(12.0, 22.0)
            candidate = Vec2(
                min(max(ball.pos.x + math.cos(angle) * distance, 10.0), c.FIELD_WIDTH - 10.0),
                min(max(ball.pos.y + math.sin(angle) * distance, 10.0), c.FIELD_HEIGHT - 10.0),
            )
            if self._effect_position_clear(candidate, ball):
                pos = candidate
                break
        if pos is None:
            pos = self._random_clear_position(ball)
        if pos is not None:
            chomper = Chomper(
                pos,
                ball,
                owner,
                c.CHOMPER_LIFETIME_TICKS,
                "roaming",
                world.rng.randint(c.CHOMPER_ROAM_MIN_TICKS, c.CHOMPER_ROAM_MAX_TICKS),
            )
            chomper.target = self._random_chomper_target(chomper)
            self.chompers.append(chomper)

    def update_stalkers(self, events: list[Event]) -> None:
        """@brief Chase target paddles, stunning them when a creature reaches contact.
        @param events Event list to append to.
        """
        world = self._world
        for stalker in list(self.stalkers):
            stalker.ttl -= 1
            if stalker.ttl <= 0 or not world.alive[stalker.target]:
                self.stalkers.remove(stalker)
                continue
            paddle = world.paddles[stalker.target].rect
            closest = Vec2(
                min(max(stalker.pos.x, paddle.cx - paddle.half_w), paddle.cx + paddle.half_w),
                min(max(stalker.pos.y, paddle.cy - paddle.half_h), paddle.cy + paddle.half_h),
            )
            delta = closest - stalker.pos
            distance = delta.length()
            if distance > 0.0:
                step = min(c.STALKER_SPEED * c.DT, distance)
                stalker.pos = stalker.pos + delta * (step / distance)
            closest = Vec2(
                min(max(stalker.pos.x, paddle.cx - paddle.half_w), paddle.cx + paddle.half_w),
                min(max(stalker.pos.y, paddle.cy - paddle.half_h), paddle.cy + paddle.half_h),
            )
            if (closest - stalker.pos).length() <= c.STALKER_RADIUS:
                self.apply_direct("stun", stalker.target, events)
                events.append(StalkerExploded(stalker.target, stalker.pos.x, stalker.pos.y))
                self.stalkers.remove(stalker)

    def update_chompers(self, events: list[Event]) -> None:
        """@brief Chase free balls, briefly swallow one, then release it elsewhere.
        @param events Event list to append to.
        """
        for chomper in list(self.chompers):
            if not any(chomper.ball is ball for ball in self._world.balls):
                chomper.ball.swallowed = False
                self.chompers.remove(chomper)
                continue
            chomper.ttl -= 1
            if chomper.ttl <= 0:
                if chomper.phase == "swallowing":
                    self._release_chomper(chomper, events)
                else:
                    self.chompers.remove(chomper)
                continue
            if chomper.phase == "roaming":
                self._roam_chomper(chomper)
                continue
            if chomper.phase == "seeking":
                ball = chomper.ball
                if ball.held_by is not None or ball.swallowed:
                    self.chompers.remove(chomper)
                    continue
                distance = (ball.pos - chomper.pos).length()
                lead = min(distance / c.CHOMPER_SPEED, 0.25)
                aim = ball.pos + ball.vel * lead
                delta = aim - chomper.pos
                if distance > 0.0:
                    step = min(c.CHOMPER_SPEED * c.DT, distance)
                    chomper.pos = chomper.pos + delta * (step / distance)
                if distance <= (
                    c.CHOMPER_RADIUS + ball.radius + (c.CHOMPER_SPEED + ball.vel.length()) * c.DT
                ):
                    chomper.pos = ball.pos
                    ball.swallowed = True
                    ball.vel = ball.vel * c.CHOMPER_BALL_SPEED_FACTOR
                    chomper.phase = "swallowing"
                    chomper.phase_ticks = c.CHOMPER_SWALLOW_TICKS
                    events.append(BallSwallowed(ball.pos.x, ball.pos.y))
            elif chomper.phase == "swallowing":
                chomper.phase_ticks -= 1
                if chomper.phase_ticks <= 0:
                    self._release_chomper(chomper, events)
            else:
                chomper.phase_ticks -= 1
                if chomper.phase_ticks <= 0:
                    self.chompers.remove(chomper)

    def _roam_chomper(self, chomper: Chomper) -> None:
        if chomper.phase_ticks <= 0:
            chomper.phase = "seeking"
            chomper.target = None
            return
        if chomper.target is None:
            chomper.target = self._random_chomper_target(chomper)
        if chomper.target is not None:
            delta = chomper.target - chomper.pos
            distance = delta.length()
            step = min(c.CHOMPER_SPEED * c.DT, distance)
            if distance > 0.0:
                chomper.pos = chomper.pos + delta * (step / distance)
            if distance <= step:
                chomper.target = self._random_chomper_target(chomper)
        chomper.phase_ticks -= 1
        if chomper.phase_ticks <= 0:
            chomper.phase = "seeking"
            chomper.target = None

    def _random_chomper_target(self, chomper: Chomper) -> Vec2 | None:
        world = self._world
        for _ in range(c.PICKUP_PLACEMENT_TRIES * 2):
            candidate = Vec2(
                world.rng.uniform(10.0, c.FIELD_WIDTH - 10.0),
                world.rng.uniform(10.0, c.FIELD_HEIGHT - 10.0),
            )
            if (
                candidate - chomper.pos
            ).length() > c.CHOMPER_RADIUS * 4 and self._effect_position_clear(
                candidate, chomper.ball
            ):
                return candidate
        return self._random_clear_position(chomper.ball)

    def _release_chomper(self, chomper: Chomper, events: list[Event]) -> None:
        if chomper not in self.chompers:
            return
        position = self._random_clear_position(chomper.ball)
        if position is None:
            position = chomper.ball.pos
        chomper.ball.pos = position
        chomper.ball.vel = self._chomper_release_velocity(position, chomper.ball.vel)
        chomper.ball.swallowed = False
        chomper.pos = position
        chomper.phase = "releasing"
        chomper.phase_ticks = c.CHOMPER_RELEASE_TICKS
        chomper.ttl = max(chomper.ttl, c.CHOMPER_RELEASE_TICKS)
        events.append(BallReleased(position.x, position.y))

    def _chomper_release_velocity(self, position: Vec2, velocity: Vec2) -> Vec2:
        world = self._world
        targets: list[Vec2] = []
        for seat in range(4):
            if not world._is_wall(seat):
                continue
            if seat == 0:
                wall_x = c.BALL_RADIUS
                for offset in (-c.CHOMPER_RELEASE_WALL_OFFSET, c.CHOMPER_RELEASE_WALL_OFFSET):
                    wall_y = min(
                        max(position.y + offset, c.BALL_RADIUS),
                        c.FIELD_HEIGHT - c.BALL_RADIUS,
                    )
                    targets.append(Vec2(wall_x, wall_y))
            elif seat == 1:
                wall_x = c.FIELD_WIDTH - c.BALL_RADIUS
                for offset in (-c.CHOMPER_RELEASE_WALL_OFFSET, c.CHOMPER_RELEASE_WALL_OFFSET):
                    wall_y = min(
                        max(position.y + offset, c.BALL_RADIUS),
                        c.FIELD_HEIGHT - c.BALL_RADIUS,
                    )
                    targets.append(Vec2(wall_x, wall_y))
            elif seat == 2:
                wall_y = c.BALL_RADIUS
                for offset in (-c.CHOMPER_RELEASE_WALL_OFFSET, c.CHOMPER_RELEASE_WALL_OFFSET):
                    wall_x = min(
                        max(position.x + offset, c.BALL_RADIUS),
                        c.FIELD_WIDTH - c.BALL_RADIUS,
                    )
                    targets.append(Vec2(wall_x, wall_y))
            else:
                wall_y = c.FIELD_HEIGHT - c.BALL_RADIUS
                for offset in (-c.CHOMPER_RELEASE_WALL_OFFSET, c.CHOMPER_RELEASE_WALL_OFFSET):
                    wall_x = min(
                        max(position.x + offset, c.BALL_RADIUS),
                        c.FIELD_WIDTH - c.BALL_RADIUS,
                    )
                    targets.append(Vec2(wall_x, wall_y))
        for obstacle in world.obstacles:
            if not obstacle.active:
                continue
            rect = obstacle.rect
            for x_sign in (-1.0, 1.0):
                for y_sign in (-1.0, 1.0):
                    targets.append(
                        Vec2(
                            rect.cx + x_sign * rect.half_w * 0.75,
                            rect.cy + y_sign * rect.half_h * 0.75,
                        )
                    )
        if not targets:
            targets.extend(
                Vec2(paddle.rect.cx, paddle.rect.cy)
                for seat, paddle in enumerate(world.paddles)
                if world.alive[seat]
            )

        angled_targets = [
            target
            for target in targets
            if abs(target.x - position.x) >= 2.0 and abs(target.y - position.y) >= 2.0
        ]
        target = min(
            angled_targets or targets,
            key=lambda point: (point - position).length(),
        )
        direction = target - position
        distance = direction.length()
        speed = velocity.length() or c.BALL_MIN_SPEED
        return direction * (speed / distance)

    def _random_clear_position(self, ignored_ball: Ball | None = None) -> Vec2 | None:
        world = self._world
        for _ in range(c.PICKUP_PLACEMENT_TRIES * 2):
            pos = Vec2(
                world.rng.uniform(10.0, c.FIELD_WIDTH - 10.0),
                world.rng.uniform(10.0, c.FIELD_HEIGHT - 10.0),
            )
            if self._effect_position_clear(pos, ignored_ball):
                return pos
        for y in range(10, int(c.FIELD_HEIGHT) - 9, 8):
            for x in range(10, int(c.FIELD_WIDTH) - 9, 8):
                pos = Vec2(float(x), float(y))
                if self._effect_position_clear(pos, ignored_ball):
                    return pos
        return None

    def _effect_position_clear(self, pos: Vec2, ignored_ball: Ball | None) -> bool:
        world = self._world
        if self._blocked(pos):
            return False
        if any(
            abs(pos.x - paddle.rect.cx) <= paddle.rect.half_w + c.CHOMPER_RADIUS
            and abs(pos.y - paddle.rect.cy) <= paddle.rect.half_h + c.CHOMPER_RADIUS
            for seat, paddle in enumerate(world.paddles)
            if world.alive[seat]
        ):
            return False
        return not any(
            ball is not ignored_ball
            and not ball.swallowed
            and (pos - ball.pos).length() < c.CHOMPER_RADIUS + ball.radius
            for ball in world.balls
        )

    def update_companions(self) -> None:
        """@brief Move companion paddles towards the ball's current path and age them."""
        for companion in list(self.companions):
            companion.ttl -= 1
            if companion.ttl <= 0 or not self._world.alive[companion.owner]:
                self.companions.remove(companion)
                continue
            paddle = companion.paddle
            target = self._world.ball.pos.y if paddle.axis == "y" else self._world.ball.pos.x
            position = paddle.rect.cy if paddle.axis == "y" else paddle.rect.cx
            speed = c.COMPANION_SPEED * c.DT
            extent = c.FIELD_HEIGHT if paddle.axis == "y" else c.FIELD_WIDTH
            paddle.move(max(-speed, min(speed, target - position)), extent)
            owner_paddle = self._world.paddles[companion.owner]
            body = owner_paddle.rect
            helper = paddle.rect
            if (
                abs(body.cx - helper.cx) < body.half_w + helper.half_w
                and abs(body.cy - helper.cy) < body.half_h + helper.half_h
            ):
                owner_pos = body.cy if paddle.axis == "y" else body.cx
                helper_pos = helper.cy if paddle.axis == "y" else helper.cx
                direction = 1.0 if helper_pos >= owner_pos else -1.0
                paddle.move(direction * speed * 0.2, extent)

    def update_invaders(self) -> None:
        """@brief Move invaders slowly and launch up to five bombs at their targets."""
        world = self._world
        for invader in list(self.invaders):
            invader.ttl -= 1
            if invader.ttl <= 0 or not world.alive[invader.target]:
                self.invaders.remove(invader)
                continue
            elapsed = world.tick / c.TICK_RATE
            desired = invader.anchor + Vec2(
                24.0 * math.sin(elapsed * 0.65 + invader.phase),
                20.0 * math.sin(elapsed * 0.9 + invader.phase * 0.7),
            )
            desired = Vec2(
                min(max(desired.x, 8.0), c.FIELD_WIDTH - 8.0),
                min(max(desired.y, 8.0), c.FIELD_HEIGHT - 8.0),
            )
            delta = desired - invader.pos
            distance = delta.length()
            if distance > 0.0:
                step = min(c.INVADER_SPEED * c.DT, distance)
                invader.pos = invader.pos + delta * (step / distance)
            if invader.bombs_left <= 0:
                continue
            invader.fire_timer -= 1
            if invader.fire_timer > 0:
                continue
            paddle = world.paddles[invader.target].rect
            direction = Vec2(paddle.cx - invader.pos.x, paddle.cy - invader.pos.y)
            distance = direction.length()
            if distance > 0.0:
                direction = direction * (1.0 / distance)
                owners = opponents(world, invader.target)
                if not owners:
                    self.invaders.remove(invader)
                    continue
                owner = owners[0]
                self.missiles.append(
                    Missile(
                        invader.pos,
                        direction * c.INVADER_BOMB_SPEED,
                        owner,
                        c.INVADER_BOMB_TTL_TICKS,
                        c.INVADER_BOMB_RADIUS,
                        target=invader.target,
                        kind="bomb",
                    )
                )
                invader.bombs_left -= 1
            invader.fire_timer = c.INVADER_FIRE_INTERVAL_TICKS

    def update_missiles(self, events: list[Event]) -> None:
        """@brief Move missiles, damaging obstacles or stunning the first opponent hit."""
        world = self._world
        for missile in list(self.missiles):
            missile.ttl -= 1
            disp = missile.vel * c.DT
            best_t = 1.0
            obstacle_hit: int | None = None
            player_hit: int | None = None
            for index, obstacle in enumerate(world.obstacles):
                if not obstacle.active:
                    continue
                hit = sweep_circle_rect(missile.pos, disp, missile.radius, obstacle.rect)
                if hit is not None and hit.t <= best_t:
                    best_t, obstacle_hit, player_hit = hit.t, index, None
            for seat, paddle in enumerate(world.paddles):
                if not world.alive[seat]:
                    continue
                if missile.target is not None and seat != missile.target:
                    continue
                if missile.target is None and seat == missile.owner:
                    continue
                hit = sweep_circle_rect(missile.pos, disp, missile.radius, paddle.rect)
                if hit is not None and hit.t < best_t:
                    best_t, obstacle_hit, player_hit = hit.t, None, seat
            missile.pos = missile.pos + disp * best_t
            if obstacle_hit is not None:
                if world.obstacles[obstacle_hit].kind == "built":
                    world.damage_obstacle(obstacle_hit, events)
                else:
                    world.destroy_obstacle(obstacle_hit, events)
                events.append(MissileHit(missile.owner, missile.pos.x, missile.pos.y, None))
                self.missiles.remove(missile)
            elif player_hit is not None:
                self.apply_direct("stun", player_hit, events)
                events.append(MissileHit(missile.owner, missile.pos.x, missile.pos.y, player_hit))
                self.missiles.remove(missile)
            elif missile.ttl <= 0:
                self.missiles.remove(missile)
            else:
                missile.pos = missile.pos + disp * (1.0 - best_t)

    def _apply_one(
        self,
        effect: Effect,
        spec: EffectSpec,
        player: int,
        events: list[Event],
        reduced: bool = False,
    ) -> None:
        if reduced:
            scale = c.COMEBACK_EFFECT_SCALE
            spec = replace(
                spec,
                duration=spec.duration * scale,
                magnitude=1.0 + (spec.magnitude - 1.0) * scale,
                ammo=max(1, round(spec.ammo * scale)) if spec.ammo else 0,
            )
            effect = EFFECTS.get(spec.name)(spec)
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
                if spec.name == "companion":
                    for ally in self.companions:
                        if ally.owner == player:
                            ally.ttl = current.remaining
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
        if self.auto_spawn_enabled and self.spawn_names:
            self._spawn_timer -= 1
            if self._spawn_timer <= 0:
                self._spawn_timer = round(self._world.config.extras_interval * c.TICK_RATE)
                if len(self.pickups) < c.PICKUP_MAX_ON_TABLE:
                    self._spawn(events)
            self._comeback_timer -= 1
            if self._comeback_timer <= 0:
                self._comeback_timer = c.COMEBACK_PICKUP_INTERVAL_TICKS
                if not self.pickups:
                    self._spawn_comeback(events)
        for pickup in list(self.pickups):
            pickup.ttl -= 1
            owner = (
                self._paddle_collector(pickup)
                if pickup.target is not None
                else self._collector(pickup)
            )
            if owner is not None:
                self.pickups.remove(pickup)
                events.append(PickupCollected(owner, pickup.name))
                if pickup.target is not None:
                    if self.specs[pickup.name].category == "penalty":
                        self.apply_direct(pickup.name, owner, events, reduced=pickup.reduced)
                    else:
                        self.apply(pickup.name, owner, events, reduced=pickup.reduced)
                else:
                    self.apply(pickup.name, owner, events)
            elif pickup.ttl <= 0:
                self.pickups.remove(pickup)

    def _paddle_collector(self, pickup: Pickup) -> int | None:
        seat = pickup.target
        if seat is None or not self._world.alive[seat]:
            return None
        rect = self._world.paddles[seat].rect
        if (
            abs(rect.cx - pickup.pos.x) <= rect.half_w + c.PICKUP_RADIUS
            and abs(rect.cy - pickup.pos.y) <= rect.half_h + c.PICKUP_RADIUS
        ):
            return seat
        return None

    def _collector(self, pickup: Pickup) -> int | None:
        for ball in self._world.balls:
            if ball.swallowed:
                continue
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
        pos: Vec2 | None = None
        for _ in range(c.PICKUP_PLACEMENT_TRIES):
            candidate_pos = Vec2(
                world.rng.uniform(
                    c.FIELD_WIDTH * c.PICKUP_AREA_X[0], c.FIELD_WIDTH * c.PICKUP_AREA_X[1]
                ),
                world.rng.uniform(*c.PICKUP_AREA_Y),
            )
            if not self._blocked(candidate_pos):
                pos = candidate_pos
                break
        if pos is None:
            return
        self.pickups.append(Pickup(pos, name, c.PICKUP_LIFETIME_TICKS))
        events.append(PickupSpawned(name))

    def _spawn_comeback(self, events: list[Event]) -> None:
        world = self._world
        if not self.spawn_names or len(world.scores) < 2:
            return
        low, high = min(world.scores), max(world.scores)
        if high - low < c.COMEBACK_SCORE_GAP:
            return
        losing = [i for i, score in enumerate(world.scores) if score == low and world.alive[i]]
        leading = [i for i, score in enumerate(world.scores) if score == high and world.alive[i]]
        if not losing or not leading:
            return
        helpful = [
            name for name in self.spawn_names if self.specs[name].category in ("power", "weapon")
        ]
        harmful = [name for name in self.spawn_names if self.specs[name].category == "penalty"]
        if len(self.pickups) >= c.PICKUP_MAX_ON_TABLE:
            return
        offer_help = not self._comeback_penalty_next
        target = losing[0] if offer_help else leading[0]
        candidates = helpful if offer_help else harmful
        if not candidates:
            candidates = harmful if offer_help else helpful
            target = leading[0] if offer_help else losing[0]
        if not candidates:
            return
        paddle = world.paddles[target]
        clearance = (
            c.PICKUP_RADIUS
            + (paddle.rect.half_h if paddle.axis == "y" else paddle.rect.half_w)
            + 4.0
        )
        sign = -1.0 if world.rng.randint(0, 1) else 1.0
        if paddle.axis == "y":
            coordinate = min(
                max(paddle.rect.cy + sign * clearance, c.PICKUP_RADIUS),
                c.FIELD_HEIGHT - c.PICKUP_RADIUS,
            )
            pos = Vec2(paddle.rect.cx, coordinate)
        else:
            coordinate = min(
                max(paddle.rect.cx + sign * clearance, c.PICKUP_RADIUS),
                c.FIELD_WIDTH - c.PICKUP_RADIUS,
            )
            pos = Vec2(coordinate, paddle.rect.cy)
        if self._blocked(pos):
            return
        name = candidates[world.rng.randint(0, len(candidates) - 1)]
        self.pickups.append(Pickup(pos, name, c.COMEBACK_PICKUP_TTL, target=target, reduced=True))
        self._comeback_penalty_next = not self._comeback_penalty_next
        events.append(PickupSpawned(name))

    def _blocked(self, pos: Vec2) -> bool:
        margin = c.PICKUP_RADIUS
        blocked_by_obstacle = any(
            abs(pos.x - o.rect.cx) <= o.rect.half_w + margin
            and abs(pos.y - o.rect.cy) <= o.rect.half_h + margin
            for o in self._world.obstacles
            if o.active
        )
        too_close_to_pickup = any(
            (pos - pickup.pos).length() < c.PICKUP_MIN_SEPARATION for pickup in self.pickups
        )
        return blocked_by_obstacle or too_close_to_pickup
