"""@package pongwars.ai.observation
@brief Read-only snapshot of what a player can see; the only input of an AI.
"""

from dataclasses import dataclass

from pongwars.domain.entities import Rect
from pongwars.domain.vec import Vec2
from pongwars.domain.world import World

SEATS = 4


@dataclass(frozen=True)
class ObstacleView:
    """@brief Visible obstacle."""

    rect: Rect
    kind: str


@dataclass(frozen=True)
class Observation:
    """@brief Immutable view of the match from one seat.

    @param seat Seat of the observer (0 left, 1 right, 2 top, 3 bottom).
    @param axis Axis the observer's paddle slides along ("y" or "x").
    @param paddle Copy of the observer's paddle rectangle.
    @param ball_pos Ball centre.
    @param ball_vel Ball velocity.
    @param ball_radius Ball radius.
    @param walls Per seat: True if that side of the field is a reflective wall.
    @param obstacles Active obstacles.
    @param tick Simulation tick of the snapshot.
    @param weapon Name of the weapon held by the observer, if any.
    @param jammed True while the observer cannot fire weapons.
    @param holding True while the observer is holding a ball (magnet).
    @param foes Paddle rectangles of the opponents still alive.
    """

    seat: int
    axis: str
    paddle: Rect
    ball_pos: Vec2
    ball_vel: Vec2
    ball_radius: float
    walls: tuple[bool, ...]
    obstacles: tuple[ObstacleView, ...]
    tick: int
    weapon: str | None = None
    jammed: bool = False
    holding: bool = False
    foes: tuple[Rect, ...] = ()
    inverted: bool = False

    @property
    def paddle_pos(self) -> float:
        """@brief Paddle centre along its sliding axis."""
        return self.paddle.cy if self.axis == "y" else self.paddle.cx

    @property
    def paddle_half(self) -> float:
        """@brief Half length of the paddle along its sliding axis."""
        return self.paddle.half_h if self.axis == "y" else self.paddle.half_w

    @staticmethod
    def from_world(world: World, seat: int) -> "Observation":
        """@brief Snapshot the world for a seat (copies everything, keeps no reference).
        @param world Match to observe.
        @param seat Observer seat.
        """
        paddle = world.paddles[seat]
        rect = paddle.rect
        walls = tuple(s >= world.players or not world.alive[s] for s in range(SEATS))
        obstacles = tuple(
            ObstacleView(Rect(o.rect.cx, o.rect.cy, o.rect.half_w, o.rect.half_h), o.kind)
            for o in world.obstacles
            if o.active
        )
        slot = world.extras.weapons[seat]
        foes = tuple(
            Rect(r.cx, r.cy, r.half_w, r.half_h)
            for r in (
                world.paddles[s].rect for s in range(world.players) if s != seat and world.alive[s]
            )
        )
        return Observation(
            seat=seat,
            axis=paddle.axis,
            paddle=Rect(rect.cx, rect.cy, rect.half_w, rect.half_h),
            ball_pos=world.ball.pos,
            ball_vel=world.ball.vel,
            ball_radius=world.ball.radius,
            walls=walls,
            obstacles=obstacles,
            tick=world.tick,
            weapon=slot[0] if slot else None,
            jammed=world.extras.mods(seat).jammed,
            holding=any(b.held_by == seat for b in world.balls),
            foes=foes,
            inverted=any(effect.name == "inverted" for effect in world.extras.active[seat]),
        )
