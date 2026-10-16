"""@package pongwars.domain.world
@brief Deterministic match simulation advanced in fixed steps.
"""

import math
from dataclasses import dataclass
from enum import Enum

from pongwars.domain import constants as c
from pongwars.domain.arenas import get_arena
from pongwars.domain.config import ConfigError, MatchConfig
from pongwars.domain.entities import Ball, Obstacle, Paddle, Rect
from pongwars.domain.events import (
    BallWarped,
    BumperHit,
    Event,
    Goal,
    MatchEnded,
    ObstacleDestroyed,
    PaddleHit,
    PlayerEliminated,
    Served,
    SpinHit,
    WallHit,
)
from pongwars.domain.extras import ExtrasManager
from pongwars.domain.extras.effects import opponents
from pongwars.domain.modes import create_mode
from pongwars.domain.physics import reflect, sweep_circle_circle, sweep_circle_rect
from pongwars.domain.rng import RandomSource
from pongwars.domain.vec import Vec2

SEAT_LEFT, SEAT_RIGHT, SEAT_TOP, SEAT_BOTTOM = range(4)
MIN_PLAYERS = 2


class Phase(Enum):
    """@brief Match phase."""

    SERVING = "serving"
    PLAYING = "playing"
    FINISHED = "finished"


@dataclass(frozen=True)
class FrameInputs:
    """@brief Per-tick input of every player.
    @param moves Intent in [-1, 1] per seat along its paddle axis; missing seats count as idle.
    @param fire Fire button state per seat; a press (rising edge) fires or releases a held ball.
    @param spin Spin button state per seat; a press applies spin at the next paddle hit.
    """

    moves: tuple[float, ...] = ()
    fire: tuple[bool, ...] = ()
    spin: tuple[bool, ...] = ()


class World:
    """@brief Complete state of a match; step() is the only way to advance it."""

    def __init__(self, config: MatchConfig, obstacles: list[Obstacle] | None = None) -> None:
        """@brief Create a match ready to serve.
        @param config Validated match configuration.
        @param obstacles Obstacles overriding the configured arena (mainly for tests).
        @throws ConfigError For an unknown mode/arena, invalid options or a player-count mismatch.
        """
        self.config = config
        arena = get_arena(config.arena)
        self.arena = arena
        if len(config.controllers) != arena.players:
            raise ConfigError(
                "error.config.player_count_mismatch",
                expected=arena.players,
                given=len(config.controllers),
            )
        self.players = arena.players
        self.mode = create_mode(config)
        self.rng = RandomSource(config.seed)
        self.obstacles = (
            self._make_arkanoid_blocks()
            if obstacles is None and config.arena == "arkanoid"
            else arena.build_obstacles()
            if obstacles is None
            else obstacles
        )
        self.portals = self._make_portals()
        self.paddles = _make_paddles(self.players)
        self.alive = [True] * self.players
        self.ball = Ball(arena.serve.position, Vec2(), c.BALL_RADIUS)
        self.extra_balls: list[Ball] = []
        self.scores = [0] * self.players
        self.extras = ExtrasManager(self)
        self._prev_fire = [False] * self.players
        self._spin_pressed = [False] * self.players
        self._paddle_moves = [0.0] * self.players
        self.phase = Phase.SERVING
        self.tick = 0
        self.winner: int | None = None
        self._serve_timer = c.MATCH_COUNTDOWN_TICKS
        self._countdown_enabled = True
        self._next_server = self.rng.choice(list(range(self.players)))

    def step(self, inputs: FrameInputs) -> list[Event]:
        """@brief Advance one fixed tick.
        @param inputs Player inputs for this tick.
        @return Events produced during the tick.
        """
        events: list[Event] = []
        if self.phase is Phase.FINISHED:
            return events
        self._spin_pressed = [
            inputs.spin[seat] if seat < len(inputs.spin) else False for seat in range(self.players)
        ]
        self.tick += 1
        for obstacle in self.obstacles:
            obstacle.update(self.tick)
        self.extras.tick_effects(events)
        for seat, paddle in enumerate(self.paddles):
            self._return_headbutt(paddle)
            mods = self.extras.mods(seat)
            move = inputs.moves[seat] if seat < len(inputs.moves) else 0.0
            move = max(-1.0, min(1.0, move)) * (-1.0 if mods.invert else 1.0)
            if mods.drunk:
                move += c.DRUNK_AMPLITUDE * math.sin(self.tick * c.DRUNK_FREQUENCY + seat)
                move = max(-1.0, min(1.0, move))
            if mods.frozen:
                move = 0.0
            self._paddle_moves[seat] = move * mods.speed_scale
            size = c.FIELD_HEIGHT if paddle.axis == "y" else c.FIELD_WIDTH
            paddle.resize(mods.size_scale, size)
            paddle.move(self._paddle_moves[seat] * c.PADDLE_SPEED * c.DT, size)
        self._handle_fire(inputs, events)
        if self.phase is Phase.SERVING:
            self._serve_timer -= 1
            if self._serve_timer <= 0:
                self._serve(events)
        else:
            self._apply_ramp_gravity()
            self._update_held()
            self.extras.update_companions()
            self.extras.update_invaders()
            for ball in self.balls:
                if self.phase is Phase.PLAYING and ball.held_by is None:
                    ball.rotation = (ball.rotation + ball.spin_rate * c.DT) % (2.0 * math.pi)
                    self._curve_ball(ball)
                    self._apply_arena_gravity(ball)
                    self._move_ball(ball, events)
            if self.phase is Phase.PLAYING:
                self.extras.update_pickups(events)
                self.extras.update_cats(events)
                self.extras.update_missiles(events)
        self.mode.on_tick(self, events)
        winner = self.mode.winner(self)
        if winner is not None:
            self.phase = Phase.FINISHED
            self.winner = winner
            events.append(MatchEnded(winner))
        return events

    @property
    def ramp_incline(self) -> float:
        """@brief Current signed court angle in radians, smoothed at both ends of its lifetime."""
        if self.players != MIN_PLAYERS:
            return 0.0
        transition = max(1, round(c.RAMP_TRANSITION_SECONDS * c.TICK_RATE))
        angle = 0.0
        for seat, effects in enumerate(self.extras.active):
            direction = 1.0 if seat == SEAT_LEFT else -1.0
            for effect in effects:
                if effect.name != "ramp":
                    continue
                elapsed = effect.spec.ticks - effect.remaining
                ramp_up = _smoothstep(elapsed / transition)
                ramp_down = _smoothstep(effect.remaining / transition)
                angle += direction * effect.spec.magnitude * min(ramp_up, ramp_down)
        return angle

    def _apply_ramp_gravity(self) -> None:
        incline = self.ramp_incline
        if incline == 0.0:
            return
        acceleration = -math.tan(incline) * c.RAMP_GRAVITY
        for ball in self.balls:
            if ball.held_by is not None:
                continue
            ball.vel = ball.vel + Vec2(acceleration * c.DT, 0.0)
            speed = ball.vel.length()
            if speed > c.BALL_MAX_SPEED:
                ball.vel = ball.vel * (c.BALL_MAX_SPEED / speed)

    def _apply_arena_gravity(self, ball: Ball) -> None:
        if self.config.arena != "gravity":
            return
        toward_center = Vec2(c.FIELD_WIDTH / 2, c.FIELD_HEIGHT / 2) - ball.pos
        distance = toward_center.length()
        if distance == 0.0:
            return
        acceleration = c.GRAVITY_WELL_ACCELERATION * math.exp(
            -distance / c.GRAVITY_WELL_RADIUS
        )
        ball.vel = ball.vel + toward_center * (acceleration * c.DT / distance)
        radial_direction = toward_center * (-1.0 / distance)
        outward_speed = ball.vel.x * radial_direction.x + ball.vel.y * radial_direction.y
        if outward_speed > 0.0 and distance < c.GRAVITY_WELL_RADIUS:
            depth = 1.0 - distance / c.GRAVITY_WELL_RADIUS
            exit_acceleration = c.GRAVITY_WELL_EXIT_ACCELERATION * depth * depth
            ball.vel = ball.vel + radial_direction * (exit_acceleration * c.DT)
        speed = ball.vel.length()
        if speed > c.BALL_MAX_SPEED:
            ball.vel = ball.vel * (c.BALL_MAX_SPEED / speed)

    def _make_arkanoid_blocks(self) -> list[Obstacle]:
        """@brief Generate a seeded, centered cluster of one-hit blocks for an Arkanoid round."""
        count = self.rng.randint(2, 16)
        center_x = self.rng.uniform(70.0, 90.0)
        center_y = self.rng.uniform(36.0, 54.0)
        cells = list(range(16))
        selected: list[int] = []
        for _ in range(count):
            selected.append(cells.pop(self.rng.randint(0, len(cells) - 1)))
        return [
            Obstacle(
                Rect(
                    center_x + (cell % 4 - 1.5) * 8.0,
                    center_y + (cell // 4 - 1.5) * 7.0,
                    3.0,
                    2.5,
                ),
                "destructible",
                hp=1,
            )
            for cell in selected
        ]

    @property
    def balls(self) -> list[Ball]:
        """@brief Every ball in play: the main ball first, then the extra ones."""
        return [self.ball, *self.extra_balls]

    @property
    def last_toucher(self) -> int | None:
        """@brief Seat that last touched the main ball."""
        return self.ball.toucher

    @last_toucher.setter
    def last_toucher(self, seat: int | None) -> None:
        self.ball.toucher = seat

    @property
    def countdown_number(self) -> int | None:
        """@brief Current initial serve countdown digit, or None outside the countdown."""
        if self.phase is not Phase.SERVING or not self._countdown_enabled:
            return None
        return max(
            1,
            (self._serve_timer + c.SERVE_COUNTDOWN_STEP_TICKS - 1)
            // c.SERVE_COUNTDOWN_STEP_TICKS,
        )

    def damage_obstacle(self, index: int, events: list[Event]) -> None:
        """@brief Deal one point of damage to an obstacle; destructible ones may break.
        @param index Obstacle index.
        @param events Event list to append to.
        """
        obstacle = self.obstacles[index]
        if obstacle.kind == "destructible" and obstacle.active:
            obstacle.hp -= 1
            if obstacle.hp <= 0:
                obstacle.active = False
                events.append(ObstacleDestroyed(index))

    def destroy_obstacle(self, index: int, events: list[Event]) -> None:
        """@brief Remove an active obstacle regardless of its material.
        @param index Obstacle index.
        @param events Event list to append to.
        """
        obstacle = self.obstacles[index]
        if obstacle.active:
            obstacle.hp = 0
            obstacle.active = False
            events.append(ObstacleDestroyed(index))

    def _handle_fire(self, inputs: FrameInputs, events: list[Event]) -> None:
        for seat in range(self.players):
            pressed = inputs.fire[seat] if seat < len(inputs.fire) else False
            edge = pressed and not self._prev_fire[seat]
            self._prev_fire[seat] = pressed
            playing = self.alive[seat] and self.phase is Phase.PLAYING
            if edge and playing and not self._release_held(seat):
                self.extras.fire(seat, events)

    def start_headbutt(self, seat: int) -> None:
        """@brief Lunge a paddle towards the table for a brief extended reach.
        @param seat Player using the headbutt weapon.
        """
        paddle = self.paddles[seat]
        direction = 1.0 if seat in (SEAT_LEFT, SEAT_TOP) else -1.0
        if paddle.axis == "y":
            paddle.rect.cx += direction * c.HEADBUTT_DISTANCE
        else:
            paddle.rect.cy += direction * c.HEADBUTT_DISTANCE
        paddle.headbutt_offset += direction * c.HEADBUTT_DISTANCE
        paddle.headbutt_ticks = c.HEADBUTT_RETURN_TICKS

    @staticmethod
    def _return_headbutt(paddle: Paddle) -> None:
        if paddle.headbutt_ticks <= 0:
            return
        correction = -paddle.headbutt_offset / paddle.headbutt_ticks
        if paddle.axis == "y":
            paddle.rect.cx += correction
        else:
            paddle.rect.cy += correction
        paddle.headbutt_offset += correction
        paddle.headbutt_ticks -= 1
        if paddle.headbutt_ticks == 0:
            paddle.headbutt_offset = 0.0

    def _release_held(self, seat: int) -> bool:
        released = False
        for ball in self.balls:
            if ball.held_by == seat:
                ball.held_by = None
                ball.vel = ball.stored_vel
                released = True
        return released

    def _update_held(self) -> None:
        for ball in self.balls:
            seat = ball.held_by
            if seat is None:
                continue
            rect = self.paddles[seat].rect
            if self.paddles[seat].axis == "y":
                ball.pos = Vec2(ball.pos.x, rect.cy + ball.hold_offset)
            else:
                ball.pos = Vec2(rect.cx + ball.hold_offset, ball.pos.y)
            ball.hold_ticks -= 1
            if ball.hold_ticks <= 0:
                self._release_held(seat)

    def _grab(self, ball: Ball, seat: int) -> None:
        rect = self.paddles[seat].rect
        axis_y = self.paddles[seat].axis == "y"
        ball.held_by = seat
        ball.stored_vel = ball.vel
        ball.vel = Vec2()
        ball.hold_ticks = c.MAGNET_HOLD_TICKS
        ball.hold_offset = ball.pos.y - rect.cy if axis_y else ball.pos.x - rect.cx

    def eliminate(self, player: int, events: list[Event]) -> None:
        """@brief Take a player out of the match; their goal becomes a wall.
        @param player Seat index.
        @param events Event list to append to.
        """
        if self.alive[player]:
            self.alive[player] = False
            events.append(PlayerEliminated(player))

    def _is_wall(self, seat: int) -> bool:
        return seat >= self.players or not self.alive[seat]

    def _serve(self, events: list[Event]) -> None:
        angle = self.rng.uniform(-c.MAX_SERVE_ANGLE, c.MAX_SERVE_ANGLE)
        seat = self._next_server
        direction = 1.0 if seat in (1, 3) else -1.0
        if seat < SEAT_TOP:
            heading = Vec2(direction * math.cos(angle), math.sin(angle))
        else:
            heading = Vec2(math.sin(angle), direction * math.cos(angle))
        self.ball.vel = heading * self.arena.serve.speed
        self.phase = Phase.PLAYING
        self._countdown_enabled = False
        events.append(Served())

    @staticmethod
    def _curve_ball(ball: Ball) -> None:
        if ball.spin_rate == 0.0:
            return
        angle = ball.spin_rate * c.SPIN_CURVE_FACTOR * c.DT
        cosine, sine = math.cos(angle), math.sin(angle)
        velocity = ball.vel
        ball.vel = Vec2(
            velocity.x * cosine - velocity.y * sine,
            velocity.x * sine + velocity.y * cosine,
        )

    def _move_ball(self, ball: Ball, events: list[Event]) -> None:
        time_left = c.DT
        for _ in range(c.MAX_COLLISIONS_PER_STEP):
            disp = ball.vel * time_left
            best = None
            best_rect: Rect | None = None
            best_paddle: Paddle | None = None
            best_owner = -1
            best_obstacle = -1
            targets: list[tuple[Paddle | None, int, int, Paddle | None]] = [
                (p, i, -1, p) for i, p in enumerate(self.paddles) if self.alive[i]
            ]
            targets.extend(
                (ally.paddle, ally.owner, -1, ally.paddle) for ally in self.extras.companions
            )
            targets.extend((None, -1, i, None) for i, o in enumerate(self.obstacles) if o.active)
            for target, pidx, oidx, paddle_target in targets:
                rect = target.rect if target is not None else self.obstacles[oidx].rect
                hit = sweep_circle_rect(ball.pos, disp, ball.radius, rect)
                if hit and (best is None or hit.t < best.t):
                    best, best_rect, best_paddle, best_owner, best_obstacle = (
                        hit,
                        rect,
                        paddle_target,
                        pidx,
                        oidx,
                    )
            best_portal: tuple[float, int] | None = None
            for portal_index, portal in enumerate(self.portals):
                portal_t = sweep_circle_circle(
                    ball.pos, disp, portal, ball.radius + c.PORTAL_RADIUS
                )
                if portal_t is not None and (
                    best_portal is None or portal_t < best_portal[0]
                ):
                    best_portal = (portal_t, portal_index)
            if best_portal is not None and (best is None or best_portal[0] < best.t):
                portal_t, portal_index = best_portal
                ball.pos = ball.pos + disp * portal_t
                destination = self.portals[1 - portal_index]
                speed = ball.vel.length()
                if speed > 0.0:
                    direction = ball.vel * (1.0 / speed)
                    ball.pos = destination + direction * (
                        c.PORTAL_RADIUS + ball.radius + c.PORTAL_EXIT_CLEARANCE
                    )
                previous_portals = self.portals
                self.portals = self._make_portals(previous_portals, (ball.pos,))
                events.append(BallWarped(ball.pos.x, ball.pos.y))
                time_left *= 1.0 - portal_t
                continue
            if best is None or best_rect is None:
                break
            ball.pos = ball.pos + disp * best.t
            spin_was_active = ball.spin_rate != 0.0
            if best_paddle is not None:
                paddle = best_paddle
                face = best.normal.y == 0.0 if paddle.axis == "y" else best.normal.x == 0.0
                spin = False
                if spin_was_active:
                    ball.spin_rate = 0.0
                if face:
                    spin = self._paddle_bounce(ball, best_owner, best.normal, paddle)
                else:
                    ball.vel = reflect(ball.vel, best.normal)
                ball.toucher = best_owner
                events.append(SpinHit(best_owner) if spin else PaddleHit(best_owner))
                if (
                    face
                    and paddle is self.paddles[best_owner]
                    and self.extras.mods(best_owner).magnet
                    and ball.held_by is None
                ):
                    self._grab(ball, best_owner)
                    time_left = 0.0
                    break
            else:
                ball.vel = reflect(ball.vel, best.normal)
                if spin_was_active:
                    ball.spin_rate = 0.0
                self._obstacle_hit(ball, best_obstacle, events)
            time_left *= 1.0 - best.t
        else:
            time_left = 0.0
        ball.pos = ball.pos + ball.vel * time_left
        self._bounce_borders(ball, events)
        self._check_goal(ball, events)

    def _make_portals(
        self,
        previous: tuple[Vec2, ...] = (),
        avoid: tuple[Vec2, ...] = (),
    ) -> tuple[Vec2, ...]:
        """@brief Pick an unobstructed portal pair, distinct from recently used positions."""
        if self.config.arena != "portal":
            return ()
        serve_point = Vec2(c.FIELD_WIDTH / 2, c.FIELD_HEIGHT / 2)
        change_clearance = c.PORTAL_RADIUS * 2 + c.BALL_RADIUS
        avoid_positions = (*previous, *avoid)

        def valid_pair(entry: Vec2, exit: Vec2) -> bool:
            if (exit - entry).length() < c.PORTAL_MIN_SEPARATION:
                return False
            for portal in (entry, exit):
                if (portal - serve_point).length() <= c.PORTAL_RADIUS + c.BALL_RADIUS:
                    return False
                if any(
                    (portal - point).length() < change_clearance for point in avoid_positions
                ):
                    return False
                if any(
                    abs(portal.x - obstacle.rect.cx)
                    <= obstacle.rect.half_w + c.PORTAL_RADIUS
                    and abs(portal.y - obstacle.rect.cy)
                    <= obstacle.rect.half_h + c.PORTAL_RADIUS
                    for obstacle in self.obstacles
                    if obstacle.active
                ):
                    return False
            return True

        for _ in range(100):
            entry = Vec2(
                self.rng.uniform(c.PORTAL_MARGIN_X, c.FIELD_WIDTH - c.PORTAL_MARGIN_X),
                self.rng.uniform(c.PORTAL_MARGIN_Y, c.FIELD_HEIGHT - c.PORTAL_MARGIN_Y),
            )
            exit = Vec2(
                self.rng.uniform(c.PORTAL_MARGIN_X, c.FIELD_WIDTH - c.PORTAL_MARGIN_X),
                self.rng.uniform(c.PORTAL_MARGIN_Y, c.FIELD_HEIGHT - c.PORTAL_MARGIN_Y),
            )
            if valid_pair(entry, exit):
                return entry, exit

        coordinates = [
            Vec2(float(x), float(y))
            for x in range(int(c.PORTAL_MARGIN_X), int(c.FIELD_WIDTH - c.PORTAL_MARGIN_X) + 1, 8)
            for y in range(int(c.PORTAL_MARGIN_Y), int(c.FIELD_HEIGHT - c.PORTAL_MARGIN_Y) + 1, 8)
        ]
        for entry in coordinates:
            for exit in coordinates:
                if valid_pair(entry, exit):
                    return entry, exit
        raise RuntimeError("Unable to find a valid portal pair for the current arena state")

    def _obstacle_hit(self, ball: Ball, index: int, events: list[Event]) -> None:
        obstacle = self.obstacles[index]
        if obstacle.kind == "bumper":
            speed = min(ball.vel.length() * c.BUMPER_FACTOR, c.BALL_MAX_SPEED)
            current = ball.vel.length()
            if current > 0:
                ball.vel = ball.vel * (speed / current)
            events.append(BumperHit(index))
            return
        events.append(WallHit())
        if self.config.arena == "monolith":
            obstacle.rect.half_w, obstacle.rect.half_h = (
                obstacle.rect.half_h,
                obstacle.rect.half_w,
            )
            rect = obstacle.rect
            closest_x = min(max(ball.pos.x, rect.cx - rect.half_w), rect.cx + rect.half_w)
            closest_y = min(max(ball.pos.y, rect.cy - rect.half_h), rect.cy + rect.half_h)
            offset = Vec2(ball.pos.x - closest_x, ball.pos.y - closest_y)
            distance = offset.length()
            if distance < ball.radius:
                clearance = ball.radius - distance + 1e-6
                if distance > 0.0:
                    ball.pos = ball.pos + offset * (clearance / distance)
                else:
                    edges = (
                        (ball.pos.x - (rect.cx - rect.half_w - ball.radius), "left"),
                        (rect.cx + rect.half_w + ball.radius - ball.pos.x, "right"),
                        (ball.pos.y - (rect.cy - rect.half_h - ball.radius), "top"),
                        (rect.cy + rect.half_h + ball.radius - ball.pos.y, "bottom"),
                    )
                    _, side = min(edges)
                    if side == "left":
                        ball.pos = Vec2(rect.cx - rect.half_w - ball.radius - 1e-6, ball.pos.y)
                    elif side == "right":
                        ball.pos = Vec2(rect.cx + rect.half_w + ball.radius + 1e-6, ball.pos.y)
                    elif side == "top":
                        ball.pos = Vec2(ball.pos.x, rect.cy - rect.half_h - ball.radius - 1e-6)
                    else:
                        ball.pos = Vec2(ball.pos.x, rect.cy + rect.half_h + ball.radius + 1e-6)
        self.damage_obstacle(index, events)

    def _paddle_bounce(
        self, ball: Ball, index: int, normal: Vec2, paddle: Paddle | None = None
    ) -> bool:
        paddle = paddle or self.paddles[index]
        rect = paddle.rect
        headbutt_hit = paddle is self.paddles[index] and paddle.headbutt_ticks > 0
        if headbutt_hit:
            if paddle.axis == "y":
                normal = Vec2(1.0 if index == SEAT_LEFT else -1.0, 0.0)
            else:
                normal = Vec2(0.0, 1.0 if index == SEAT_TOP else -1.0)
        movement = self._paddle_moves[index] if paddle is self.paddles[index] else 0.0
        spin = self._spin_pressed[index] and abs(movement) > 0.05
        spin_sign = (1.0 if movement > 0 else -1.0) if spin else 0.0
        speed_factor = (
            c.HEADBUTT_HIT_SPEED_FACTOR
            if paddle is self.paddles[index] and paddle.headbutt_ticks > 0
            else c.SPIN_SPEED_FACTOR
            if spin
            else c.BALL_HIT_SPEEDUP
        )
        speed = min(ball.vel.length() * speed_factor, c.BALL_MAX_SPEED)
        if paddle.axis == "y":
            offset = (ball.pos.y - rect.cy) / (rect.half_h + ball.radius)
            angle = max(-1.0, min(1.0, offset)) * c.MAX_BOUNCE_ANGLE
            angle += spin_sign * c.SPIN_BOUNCE_ANGLE
            ball.vel = Vec2(normal.x * math.cos(angle), math.sin(angle)) * speed
        else:
            offset = (ball.pos.x - rect.cx) / (rect.half_w + ball.radius)
            angle = max(-1.0, min(1.0, offset)) * c.MAX_BOUNCE_ANGLE
            angle += spin_sign * c.SPIN_BOUNCE_ANGLE
            ball.vel = Vec2(math.sin(angle), normal.y * math.cos(angle)) * speed
        ball.spin_rate = spin_sign * c.SPIN_ROTATION_RATE
        if self.extras.mods(index).aim:
            self._aim(ball, index, normal, speed)
        return spin

    def _aim(self, ball: Ball, index: int, normal: Vec2, speed: float) -> None:
        targets = opponents(self, index)
        if not targets:
            return
        goal = self.paddles[targets[0]].rect
        want = Vec2(goal.cx - ball.pos.x, goal.cy - ball.pos.y)
        length = want.length()
        if length == 0.0:
            return
        mixed = ball.vel * (1.0 / speed) + want * (1.0 / length)
        if mixed.x * normal.x + mixed.y * normal.y <= 0.1 * mixed.length():
            return
        ball.vel = mixed * (speed / mixed.length())

    def _bounce_borders(self, ball: Ball, events: list[Event]) -> None:
        r = ball.radius
        was_spinning = ball.spin_rate != 0.0
        hit = False
        if self._is_wall(SEAT_TOP) and ball.pos.y < r:
            ball.pos = Vec2(ball.pos.x, 2 * r - ball.pos.y)
            ball.vel = Vec2(ball.vel.x, abs(ball.vel.y))
            hit = True
        elif self._is_wall(SEAT_BOTTOM) and ball.pos.y > c.FIELD_HEIGHT - r:
            ball.pos = Vec2(ball.pos.x, 2 * (c.FIELD_HEIGHT - r) - ball.pos.y)
            ball.vel = Vec2(ball.vel.x, -abs(ball.vel.y))
            hit = True
        if self._is_wall(SEAT_LEFT) and ball.pos.x < r:
            ball.pos = Vec2(2 * r - ball.pos.x, ball.pos.y)
            ball.vel = Vec2(abs(ball.vel.x), ball.vel.y)
            hit = True
        elif self._is_wall(SEAT_RIGHT) and ball.pos.x > c.FIELD_WIDTH - r:
            ball.pos = Vec2(2 * (c.FIELD_WIDTH - r) - ball.pos.x, ball.pos.y)
            ball.vel = Vec2(-abs(ball.vel.x), ball.vel.y)
            hit = True
        if hit and was_spinning:
            ball.spin_rate = 0.0
        if hit:
            events.append(WallHit())

    def _conceding_seat(self, ball: Ball) -> int | None:
        pos, r = ball.pos, ball.radius
        crossed = (
            pos.x < -r,
            pos.x > c.FIELD_WIDTH + r,
            pos.y < -r,
            pos.y > c.FIELD_HEIGHT + r,
        )
        for seat, out in enumerate(crossed):
            if out and not self._is_wall(seat):
                return seat
        return None

    def _shield_bounce(self, ball: Ball, seat: int) -> None:
        gap = ball.radius + c.SHIELD_BALL_CLEARANCE
        x, y, vx, vy = ball.pos.x, ball.pos.y, ball.vel.x, ball.vel.y
        if seat == SEAT_LEFT:
            x, vx = gap, abs(vx)
        elif seat == SEAT_RIGHT:
            x, vx = c.FIELD_WIDTH - gap, -abs(vx)
        elif seat == SEAT_TOP:
            y, vy = gap, abs(vy)
        else:
            y, vy = c.FIELD_HEIGHT - gap, -abs(vy)
        ball.pos, ball.vel = Vec2(x, y), Vec2(vx, vy)

    def _check_goal(self, ball: Ball, events: list[Event]) -> None:
        conceded = self._conceding_seat(ball)
        if conceded is None:
            return
        if self.extras.use_shield(conceded, events):
            self._shield_bounce(ball, conceded)
            ball.spin_rate = 0.0
            return
        scorer: int | None
        if self.players == MIN_PLAYERS:
            scorer = 1 - conceded
        else:
            scorer = ball.toucher if ball.toucher != conceded else None
        events.append(Goal(scorer, conceded))
        self.mode.on_goal(self, scorer, conceded, events)
        if ball is not self.ball:
            self.extra_balls.remove(ball)
            return
        self.extra_balls.clear()
        self.extras.cats.clear()
        if self.config.arena == "fortress":
            self.obstacles = get_arena("fortress").build_obstacles()
        elif self.config.arena == "arkanoid":
            self.obstacles = self._make_arkanoid_blocks()
        self.ball = Ball(
            self.arena.serve.position,
            Vec2(),
            c.BALL_RADIUS,
        )
        self.phase = Phase.SERVING
        self._serve_timer = c.SERVE_DELAY_TICKS
        for step in range(self.players):
            candidate = (conceded + step) % self.players
            if self.alive[candidate]:
                self._next_server = candidate
                break


def _make_paddles(players: int) -> list[Paddle]:
    """@brief Paddles for each seat: left, right, top, bottom (in that order)."""
    mid_y, mid_x = c.FIELD_HEIGHT / 2, c.FIELD_WIDTH / 2
    long_side, short_side = c.PADDLE_HALF_HEIGHT, c.PADDLE_HALF_WIDTH
    seats = [
        Paddle(Rect(c.PADDLE_MARGIN, mid_y, short_side, long_side)),
        Paddle(Rect(c.FIELD_WIDTH - c.PADDLE_MARGIN, mid_y, short_side, long_side)),
        Paddle(Rect(mid_x, c.PADDLE_MARGIN, long_side, short_side), axis="x"),
        Paddle(Rect(mid_x, c.FIELD_HEIGHT - c.PADDLE_MARGIN, long_side, short_side), axis="x"),
    ]
    return seats[:players]


def _smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)
