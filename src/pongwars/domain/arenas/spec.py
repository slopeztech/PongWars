"""@package pongwars.domain.arenas.spec
@brief Data description of an arena (obstacle layout) and its fairness checks.
"""

from dataclasses import dataclass, replace

from pongwars.domain import constants as c
from pongwars.domain.entities import OBSTACLE_KINDS, Obstacle, Rect
from pongwars.domain.vec import Vec2

MAX_SEATS = 4


@dataclass(frozen=True)
class ObstacleSpec:
    """@brief Declarative obstacle: position, size, kind and optional patrol motion."""

    kind: str
    x: float
    y: float
    half_w: float
    half_h: float
    hp: int = 0
    patrol_x: float = 0.0
    patrol_y: float = 0.0
    period: int = 0

    def build(self) -> Obstacle:
        """@brief Create the runtime obstacle."""
        return Obstacle(
            Rect(self.x, self.y, self.half_w, self.half_h),
            self.kind,
            self.hp,
            Vec2(self.patrol_x, self.patrol_y),
            self.period,
        )

    def swept(self) -> tuple[float, float, float, float]:
        """@brief Bounding box (x_min, x_max, y_min, y_max) over the whole patrol path."""
        return (
            self.x - abs(self.patrol_x) - self.half_w,
            self.x + abs(self.patrol_x) + self.half_w,
            self.y - abs(self.patrol_y) - self.half_h,
            self.y + abs(self.patrol_y) + self.half_h,
        )

    def mirrored(self, axis: str) -> "ObstacleSpec":
        """@brief Mirror across the field's vertical ("x") or horizontal ("y") axis."""
        if axis == "x":
            return replace(self, x=c.FIELD_WIDTH - self.x, patrol_x=-self.patrol_x)
        return replace(self, y=c.FIELD_HEIGHT - self.y, patrol_y=-self.patrol_y)

    def key(self) -> tuple[object, ...]:
        """@brief Hashable identity used to compare layouts (patrol sign is irrelevant)."""
        return (
            self.kind,
            round(self.x, 3),
            round(self.y, 3),
            self.half_w,
            self.half_h,
            self.hp,
            abs(self.patrol_x),
            abs(self.patrol_y),
            self.period,
        )

    def validate(self, players: int = 2) -> str | None:
        """@brief Return a problem key if the obstacle is invalid, else None.
        @param players Player count of the arena (3-4 players keep obstacles off the top/bottom).
        """
        if self.kind not in OBSTACLE_KINDS:
            return "error.arena.invalid_value"
        if self.half_w <= 0 or self.half_h <= 0:
            return "error.arena.invalid_value"
        if self.kind == "destructible" and self.hp < 1:
            return "error.arena.invalid_value"
        moving = self.patrol_x != 0 or self.patrol_y != 0
        if moving != (self.period > 0):
            return "error.arena.invalid_value"
        x0, x1, y0, y1 = self.swept()
        if x0 < c.ARENA_SIDE_MARGIN or x1 > c.FIELD_WIDTH - c.ARENA_SIDE_MARGIN:
            return "error.arena.obstacle_out_of_bounds"
        end_margin = c.ARENA_END_MARGIN if players > 2 else 0.0
        if y0 < end_margin or y1 > c.FIELD_HEIGHT - end_margin:
            return "error.arena.obstacle_out_of_bounds"
        return None


@dataclass(frozen=True)
class ArenaSpec:
    """@brief A named arena: translation key, visual theme and obstacle layout."""

    id: str
    name_key: str
    theme: str
    obstacles: tuple[ObstacleSpec, ...] = ()
    players: int = 2

    def build_obstacles(self) -> list[Obstacle]:
        """@brief Fresh runtime obstacles for a new match."""
        return [o.build() for o in self.obstacles]

    def is_mirror_symmetric(self) -> bool:
        """@brief True if the layout is fair to every seat.

        Always mirror-symmetric left-right; 4-player arenas must also be symmetric top-bottom.
        """
        original = {o.key() for o in self.obstacles}
        axes = ("x", "y") if self.players == MAX_SEATS else ("x",)
        return all({o.mirrored(axis).key() for o in self.obstacles} == original for axis in axes)

    def has_open_path(self) -> bool:
        """@brief True if the ball can always get across: no slab is fully blocked.

        With paddles on the top/bottom lines (3-4 players) the vertical direction is checked too.
        """
        boxes = [o.swept() for o in self.obstacles]
        if not _slabs_open(boxes, c.FIELD_WIDTH, c.FIELD_HEIGHT):
            return False
        if self.players > 2:
            transposed = [(b[2], b[3], b[0], b[1]) for b in boxes]
            return _slabs_open(transposed, c.FIELD_HEIGHT, c.FIELD_WIDTH)
        return True


def _slabs_open(
    boxes: list[tuple[float, float, float, float]], length: float, cross: float
) -> bool:
    """@brief Check that every slab along the main axis keeps a ball-wide gap across it.
    @param boxes Swept boxes as (main_min, main_max, cross_min, cross_max).
    @param length Field extent along the main axis.
    @param cross Field extent across it.
    """
    gap_needed = 2 * c.BALL_RADIUS
    edges = sorted({0.0, length, *(v for b in boxes for v in b[:2])})
    for left, right in zip(edges, edges[1:], strict=False):
        mid = (left + right) / 2
        spans = sorted((b[2], b[3]) for b in boxes if b[0] < mid < b[1])
        cursor = 0.0
        largest = 0.0
        for low, high in spans:
            largest = max(largest, low - cursor)
            cursor = max(cursor, high)
        if max(largest, cross - cursor) < gap_needed:
            return False
    return True
