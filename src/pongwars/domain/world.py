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
    BumperHit,
    Event,
    Goal,
    MatchEnded,
    ObstacleDestroyed,
    PaddleHit,
    PlayerEliminated,
    Served,
    WallHit,
)
from pongwars.domain.extras import ExtrasManager
from pongwars.domain.modes import create_mode
from pongwars.domain.physics import reflect, sweep_circle_rect
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
    """

    moves: tuple[float, ...] = ()
    fire: tuple[bool, ...] = ()


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
        if len(config.controllers) != arena.players:
            raise ConfigError(
                "error.config.player_count_mismatch",
                expected=arena.players,
                given=len(config.controllers),
            )
        self.players = arena.players
        self.mode = create_mode(config)
        self.rng = RandomSource(config.seed)
        self.obstacles = arena.build_obstacles() if obstacles is None else obstacles
        self.paddles = _make_paddles(self.players)
        self.alive = [True] * self.players
        mid = c.FIELD_HEIGHT / 2
        self.ball = Ball(Vec2(c.FIELD_WIDTH / 2, mid), Vec2(), c.BALL_RADIUS)
        self.extra_balls: list[Ball] = []
        self.scores = [0] * self.players
        self.extras = ExtrasManager(self)
        self._prev_fire = [False] * self.players
        self.phase = Phase.SERVING
        self.tick = 0
        self.winner: int | None = None
        self._serve_timer = c.SERVE_DELAY_TICKS
        self._next_server = self.rng.choice(list(range(self.players)))

    def step(self, inputs: FrameInputs) -> list[Event]:
        """@brief Advance one fixed tick.
        @param inputs Player inputs for this tick.
        @return Events produced during the tick.
        """
        events: list[Event] = []
        if self.phase is Phase.FINISHED:
            return events
        self.tick += 1
        for obstacle in self.obstacles:
            obstacle.update(self.tick)
        self.extras.tick_effects(events)
        for seat, paddle in enumerate(self.paddles):
            mods = self.extras.mods(seat)
            move = inputs.moves[seat] if seat < len(inputs.moves) else 0.0
            move = max(-1.0, min(1.0, move)) * (-1.0 if mods.invert else 1.0)
            if mods.frozen:
                move = 0.0
            size = c.FIELD_HEIGHT if paddle.axis == "y" else c.FIELD_WIDTH
            paddle.resize(mods.size_scale, size)
            paddle.move(move * mods.speed_scale * c.PADDLE_SPEED * c.DT, size)
        self._handle_fire(inputs, events)
        if self.phase is Phase.SERVING:
            self._serve_timer -= 1
            if self._serve_timer <= 0:
                self._serve(events)
        else:
            self._update_held()
            for ball in self.balls:
                if self.phase is Phase.PLAYING and ball.held_by is None:
                    self._move_ball(ball, events)
            if self.phase is Phase.PLAYING:
                self.extras.update_pickups(events)
        self.mode.on_tick(self, events)
        winner = self.mode.winner(self)
        if winner is not None:
            self.phase = Phase.FINISHED
            self.winner = winner
            events.append(MatchEnded(winner))
        return events

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

    def _handle_fire(self, inputs: FrameInputs, events: list[Event]) -> None:
        for seat in range(self.players):
            pressed = inputs.fire[seat] if seat < len(inputs.fire) else False
            edge = pressed and not self._prev_fire[seat]
            self._prev_fire[seat] = pressed
            playing = self.alive[seat] and self.phase is Phase.PLAYING
            if edge and playing and not self._release_held(seat):
                self.extras.fire(seat, events)

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
        self.ball.vel = heading * c.BALL_START_SPEED
        self.phase = Phase.PLAYING
        events.append(Served())

    def _move_ball(self, ball: Ball, events: list[Event]) -> None:
        time_left = c.DT
        for _ in range(c.MAX_COLLISIONS_PER_STEP):
            disp = ball.vel * time_left
            best = None
            best_rect: Rect | None = None
            best_paddle = -1
            best_obstacle = -1
            targets = [(p.rect, i, -1) for i, p in enumerate(self.paddles) if self.alive[i]]
            targets += [(o.rect, -1, i) for i, o in enumerate(self.obstacles) if o.active]
            for rect, pidx, oidx in targets:
                hit = sweep_circle_rect(ball.pos, disp, ball.radius, rect)
                if hit and (best is None or hit.t < best.t):
                    best, best_rect, best_paddle, best_obstacle = hit, rect, pidx, oidx
            if best is None or best_rect is None:
                break
            ball.pos = ball.pos + disp * best.t
            if best_paddle >= 0:
                paddle = self.paddles[best_paddle]
                face = best.normal.y == 0.0 if paddle.axis == "y" else best.normal.x == 0.0
                if face:
                    self._paddle_bounce(ball, best_paddle, best.normal)
                else:
                    ball.vel = reflect(ball.vel, best.normal)
                ball.toucher = best_paddle
                events.append(PaddleHit(best_paddle))
                if face and self.extras.mods(best_paddle).magnet and ball.held_by is None:
                    self._grab(ball, best_paddle)
                    time_left = 0.0
                    break
            else:
                ball.vel = reflect(ball.vel, best.normal)
                self._obstacle_hit(ball, best_obstacle, events)
            time_left *= 1.0 - best.t
        else:
            time_left = 0.0
        ball.pos = ball.pos + ball.vel * time_left
        self._bounce_borders(ball, events)
        self._check_goal(ball, events)

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
        self.damage_obstacle(index, events)

    def _paddle_bounce(self, ball: Ball, index: int, normal: Vec2) -> None:
        paddle = self.paddles[index]
        rect = paddle.rect
        speed = min(ball.vel.length() * c.BALL_HIT_SPEEDUP, c.BALL_MAX_SPEED)
        if paddle.axis == "y":
            offset = (ball.pos.y - rect.cy) / (rect.half_h + ball.radius)
            angle = max(-1.0, min(1.0, offset)) * c.MAX_BOUNCE_ANGLE
            ball.vel = Vec2(normal.x * math.cos(angle), math.sin(angle)) * speed
        else:
            offset = (ball.pos.x - rect.cx) / (rect.half_w + ball.radius)
            angle = max(-1.0, min(1.0, offset)) * c.MAX_BOUNCE_ANGLE
            ball.vel = Vec2(math.sin(angle), normal.y * math.cos(angle)) * speed

    def _bounce_borders(self, ball: Ball, events: list[Event]) -> None:
        r = ball.radius
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
        self.ball = Ball(Vec2(c.FIELD_WIDTH / 2, c.FIELD_HEIGHT / 2), Vec2(), c.BALL_RADIUS)
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
