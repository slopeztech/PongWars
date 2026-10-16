"""@package pongwars.render.renderer
@brief Draws a read-only `World` as an 8-bit pseudo-3D scene on a low-resolution surface.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

import pygame

from pongwars.core.i18n import Translator
from pongwars.core.settings import BALL_STYLES, FIELD_STYLES, TRAIL_STYLES
from pongwars.domain import constants as c
from pongwars.domain.entities import Ball, Paddle, Rect
from pongwars.domain.events import (
    BallWarped,
    BombDetonated,
    BumperHit,
    Event,
    Goal,
    LaserFired,
    MissileHit,
    PaddleHit,
    PickupCollected,
    WallHit,
)
from pongwars.domain.world import SEAT_LEFT, SEAT_RIGHT, SEAT_TOP, Phase, World
from pongwars.render import palette as pal
from pongwars.render.backgrounds import draw_background
from pongwars.render.camera import DEFAULT_BACK, DEFAULT_FOCAL, DEFAULT_HEIGHT, Camera
from pongwars.render.effects import Explosion, ParticleSystem, Shake, Trail
from pongwars.render.font import GLYPH_H, draw_text, text_width

LOW_W = 320
LOW_H = 180
PADDLE_HEIGHT = 4.0
OBSTACLE_HEIGHT = 5.0
BALL_LIFT = 2.0
SHAKE_GOAL = 4.0
SHAKE_HIT = 1.0
HUD_MARGIN = 4
HUD_TOP = 3
BIG_TEXT = 2
SMALL_TEXT = 1
LABEL_GAP = 8
SHARED_SLOT_OFFSET = 20
SHARED_DUEL_OFFSET = 30
SIDE_FACE_SHADE = 0.45
FRONT_FACE_SHADE = 0.6
SEAT_TURNS = {3: 0, 1: 1, 2: 2, 0: 3}
SPLIT_COLUMNS = 2
PICKUP_HEIGHT = 3.0
SKIN_STRIPED = 1
SKIN_GLOW = 2
SKIN_CAPPED = 3
STRIPES = 6
GRID_STEP = 20
STRIPE_SHADE = 0.6
CAP_SIZE = 3.0
PICKUP_BLINK_TICKS = 120
PICKUP_BLINK_PERIOD = 6
SHIELD_GAP = 1.5
LASER_FRAMES = 6
EFFECT_ROW = 7
CATEGORY_COLORS = {
    "power": pal.LIME,
    "weapon": pal.ORANGE,
    "penalty": pal.RED,
    "status": pal.PINK,
}
ODD_TURN_ZOOM = 1.6
KIND_COLORS = {
    "solid": pal.LAVENDER,
    "bumper": pal.ORANGE,
    "moving": pal.PINK,
    "destructible": pal.BROWN,
}
Point = tuple[float, float]
Corner = tuple[float, float, float]
ViewMode = Literal["shared", "split"]
FACES = ((0, -1), (0, 1), (-1, 0), (1, 0))


@dataclass
class RenderSettings:
    """@brief User-configurable visual options."""

    particles: bool = True
    trail: bool = True
    shake: bool = True
    scale: int = 4
    view: ViewMode = "shared"
    background: str = "grid"
    ball_style: str = "classic"
    trail_style: str = "classic"
    field_style: str = "grid"
    paddle_colors: tuple[int, ...] = (0, 1, 2, 3)
    paddle_skins: tuple[int, ...] = (0, 0, 0, 0)


@dataclass(frozen=True)
class Viewport:
    """@brief A screen area showing the table from one seat's point of view."""

    rect: pygame.Rect
    seat: int | None
    turns: int


def split_viewports(players: int) -> list[Viewport]:
    """@brief Lay out one viewport per seat: halves for two players, quadrants for 3-4.
    @param players Number of seats.
    @return Viewports ordered by seat.
    """
    if players <= SPLIT_COLUMNS:
        half = LOW_W // SPLIT_COLUMNS
        return [
            Viewport(pygame.Rect(seat * half, 0, half, LOW_H), seat, SEAT_TURNS[seat])
            for seat in range(players)
        ]
    w, h = LOW_W // SPLIT_COLUMNS, LOW_H // SPLIT_COLUMNS
    return [
        Viewport(pygame.Rect((seat % 2) * w, (seat // 2) * h, w, h), seat, SEAT_TURNS[seat])
        for seat in range(players)
    ]


class Renderer:
    """@brief Renders the world each frame; owns purely visual state (effects)."""

    def __init__(
        self,
        settings: RenderSettings | None = None,
        seed: int = 0,
        translator: Translator | None = None,
    ) -> None:
        """@brief Create a renderer.
        @param settings Visual options.
        @param seed Seed for the visual RNGs.
        @param translator Text source for the HUD (English when omitted).
        """
        self.settings = settings or RenderSettings()
        self.translator = translator or Translator()
        self.camera = Camera(LOW_W, LOW_H)
        self.surface = pygame.Surface((LOW_W, LOW_H))
        self._canvas = self.surface
        self.particles = ParticleSystem(seed)
        self.trail = Trail()
        self.shake = Shake(seed)
        self._lasers: list[tuple[Point, Point, pal.Color, int]] = []
        self.explosions: list[Explosion] = []
        self._clock = 0
        self.colors = [
            pal.PADDLE_PALETTE[i % len(pal.PADDLE_PALETTE)] for i in self.settings.paddle_colors
        ]
        self.colors += list(pal.PLAYER_COLORS[len(self.colors) :])

    def handle_events(self, world: World, events: Iterable[Event]) -> None:
        """@brief React to simulation events with visual effects.
        @param world World the events came from.
        @param events Events emitted by the last step.
        """
        pos = world.ball.pos
        for event in events:
            if isinstance(event, LaserFired):
                rect = world.paddles[event.player].rect
                self._lasers.append(
                    (
                        (rect.cx, rect.cy),
                        (event.x, event.y),
                        self.colors[event.player],
                        LASER_FRAMES,
                    )
                )
                self._burst(event.x, event.y, pal.ORANGE, 6)
            elif isinstance(event, BombDetonated):
                self.explosions.append(Explosion(event.x, event.y))
                self._burst(event.x, event.y, pal.YELLOW, 28)
            elif isinstance(event, BallWarped):
                self._burst(event.x, event.y, pal.UI_CYAN, 12)
            elif isinstance(event, PickupCollected):
                self._burst(pos.x, pos.y, pal.LIME, 10)
            elif isinstance(event, MissileHit):
                self._burst(event.x, event.y, pal.ORANGE, 8)
            elif isinstance(event, PaddleHit):
                color = self.colors[event.player]
                self._burst(pos.x, pos.y, color, 8)
                self._shake(SHAKE_HIT)
            elif isinstance(event, WallHit | BumperHit):
                self._burst(pos.x, pos.y, pal.WHITE, 5)
            elif isinstance(event, Goal):
                self._burst(pos.x, pos.y, pal.YELLOW, 30)
                self._shake(SHAKE_GOAL)
                self.trail.clear()

    def update(self, world: World, dt: float) -> None:
        """@brief Advance visual-only state by one frame.
        @param world Current world.
        @param dt Real frame time in seconds.
        """
        self.particles.update(dt)
        self._clock += 1
        self._lasers = [(a, b, col, n - 1) for a, b, col, n in self._lasers if n > 1]
        for explosion in self.explosions:
            explosion.update(dt)
        self.explosions = [e for e in self.explosions if e.progress < 1.0]
        if self.settings.trail and world.phase.value == "playing":
            self.trail.push(world.ball.pos.x, world.ball.pos.y)

    def viewports(self, world: World) -> list[Viewport]:
        """@brief Viewports for the current view mode.
        @param world World being drawn.
        @return One full-screen viewport (shared) or one per seat (split).
        """
        if self.settings.view == "split":
            return split_viewports(world.players)
        return [Viewport(pygame.Rect(0, 0, LOW_W, LOW_H), None, 0)]

    def draw(self, world: World) -> pygame.Surface:
        """@brief Render one frame onto the low-res surface.
        @param world World to draw.
        @return The low-resolution surface (do not keep a reference across frames).
        """
        self.surface.fill(pal.BLACK)
        for view in self.viewports(world):
            self._canvas = self.surface.subsurface(view.rect)
            self.camera = self._camera_for(view)
            draw_background(self._canvas, self.settings.background, self._clock)
            self._draw_scene(world)
            self._draw_hud(world, view)
        self._canvas = self.surface
        return self.surface

    def present(self, world: World, window: pygame.Surface) -> None:
        """@brief Draw and scale the frame onto a window with nearest-neighbour filtering.
        @param world World to draw.
        @param window Destination surface.
        """
        frame = self.draw(world)
        offset = self.shake.update() if self.settings.shake else (0, 0)
        scaled = pygame.transform.scale(frame, window.get_size())
        window.blit(scaled, (offset[0] * self.settings.scale, offset[1] * self.settings.scale))

    @staticmethod
    def _camera_for(view: Viewport) -> Camera:
        w, h = view.rect.size
        if view.seat is None:
            return Camera(w, h)
        # Odd turns look along the long table axis, so pull the camera back and widen less.
        extent = (c.FIELD_WIDTH - c.FIELD_HEIGHT) / 2 if view.turns % 2 else 0.0
        focal = DEFAULT_FOCAL * w / LOW_W * (ODD_TURN_ZOOM if view.turns % 2 else 1.0)
        if view.turns % 2 and h < LOW_H:
            # Fit the rotated field in short panes and leave room for the countdown HUD.
            focal = min(focal, DEFAULT_FOCAL * h / LOW_H * 0.8)
        return Camera(
            w,
            h,
            back=DEFAULT_BACK + extent,
            height=DEFAULT_HEIGHT + extent,
            focal=focal,
            quarter_turns=view.turns,
        )

    def _draw_scene(self, world: World) -> None:
        self._draw_table(world)
        items: list[tuple[float, str, int]] = []
        items += [
            (self._sort(portal.x, portal.y), "portal", i)
            for i, portal in enumerate(world.portals)
        ]
        items += [
            (self._sort(o.rect.cx, o.rect.cy), "obstacle", i)
            for i, o in enumerate(world.obstacles)
            if o.active
        ]
        items += [
            (self._sort(p.rect.cx, p.rect.cy), "paddle", i)
            for i, p in enumerate(world.paddles)
            if world.alive[i]
        ]
        items += [(self._sort(b.pos.x, b.pos.y), "ball", i) for i, b in enumerate(world.balls)]
        items += [
            (self._sort(p.pos.x, p.pos.y), "pickup", i) for i, p in enumerate(world.extras.pickups)
        ]
        items += [(self._sort(k.pos.x, k.pos.y), "cat", i) for i, k in enumerate(world.extras.cats)]
        items += [
            (
                self._sort(a.paddle.rect.cx, a.paddle.rect.cy),
                "companion",
                i,
            )
            for i, a in enumerate(world.extras.companions)
        ]
        items += [
            (self._sort(m.pos.x, m.pos.y), "missile", i)
            for i, m in enumerate(world.extras.missiles)
        ]
        for _, kind, index in sorted(items):
            if kind == "portal":
                self._portal(world, index)
            elif kind == "obstacle":
                obstacle = world.obstacles[index]
                self._box(
                    obstacle.rect, OBSTACLE_HEIGHT, KIND_COLORS.get(obstacle.kind, pal.LAVENDER)
                )
            elif kind == "paddle":
                self._paddle(world, index)
            elif kind == "pickup":
                self._pickup(world, index)
            elif kind == "cat":
                self._cat(world, index)
            elif kind == "companion":
                ally = world.extras.companions[index]
                self._draw_paddle(ally.paddle, ally.owner)
            elif kind == "missile":
                self._missile(world, index)
            else:
                self._ball(world, index)
        self._draw_shields(world)
        self._draw_lasers()
        self._draw_explosions()
        self._draw_particles()

    def _paddle(self, world: World, index: int) -> None:
        self._draw_paddle(world.paddles[index], index)

    def _draw_paddle(self, paddle: Paddle, index: int) -> None:
        rect = paddle.rect
        color = self.colors[index]
        skin = self.settings.paddle_skins[index] if index < len(self.settings.paddle_skins) else 0
        self._box(rect, PADDLE_HEIGHT, color)
        x0, x1 = rect.cx - rect.half_w, rect.cx + rect.half_w
        y0, y1 = rect.cy - rect.half_h, rect.cy + rect.half_h
        top = PADDLE_HEIGHT
        if skin == SKIN_STRIPED:
            vertical = rect.half_h >= rect.half_w
            for k in range(1, STRIPES, 2):
                f0, f1 = k / STRIPES, (k + 1) / STRIPES
                if vertical:
                    ya, yb = y0 + (y1 - y0) * f0, y0 + (y1 - y0) * f1
                    corners = [(x0, ya, top), (x1, ya, top), (x1, yb, top), (x0, yb, top)]
                else:
                    xa, xb = x0 + (x1 - x0) * f0, x0 + (x1 - x0) * f1
                    corners = [(xa, y0, top), (xb, y0, top), (xb, y1, top), (xa, y1, top)]
                self._quad(corners, pal.shade(color, STRIPE_SHADE))
        elif skin == SKIN_GLOW:
            pulse = 0.75 + 0.25 * math.sin(self._clock / 6.0 + index)
            self._quad(
                [(x0, y0, top), (x1, y0, top), (x1, y1, top), (x0, y1, top)],
                pal.shade(pal.WHITE, pulse),
            )
        elif skin == SKIN_CAPPED:
            vertical = rect.half_h >= rect.half_w
            cap = CAP_SIZE
            ends = (
                [(x0, y0, top), (x1, y0, top), (x1, y0 + cap, top), (x0, y0 + cap, top)],
                [(x0, y1 - cap, top), (x1, y1 - cap, top), (x1, y1, top), (x0, y1, top)],
            )
            if not vertical:
                ends = (
                    [(x0, y0, top), (x0 + cap, y0, top), (x0 + cap, y1, top), (x0, y1, top)],
                    [(x1 - cap, y0, top), (x1, y0, top), (x1, y1, top), (x1 - cap, y1, top)],
                )
            for corners in ends:
                self._quad(corners, pal.WHITE)

    def _cat(self, world: World, index: int) -> None:
        cat = world.extras.cats[index]
        ground = self.camera.project(cat.pos.x, cat.pos.y, 0.0)
        body = self.camera.project(cat.pos.x, cat.pos.y, BALL_LIFT)
        r = max(2, round(c.CAT_RADIUS * body.scale))
        cx, cy = round(body.sx), round(body.sy)
        shadow = pygame.Rect(0, 0, r * 2, max(1, r // 2))
        shadow.center = (round(ground.sx), round(ground.sy))
        pygame.draw.ellipse(self._canvas, pal.shade(pal.NAVY, 0.4), shadow)
        pygame.draw.circle(self._canvas, pal.ORANGE, (cx, cy), r)
        for side in (-1, 1):
            ear = [(cx + side * r, cy - r // 2), (cx + side * (r // 2), cy - r - 1)]
            pygame.draw.polygon(self._canvas, pal.ORANGE, [*ear, (cx + side * r // 3, cy - r // 2)])
        self._canvas.fill(pal.BLACK, (cx - r // 2, cy - r // 3, 1, 1))
        self._canvas.fill(pal.BLACK, (cx + r // 2 - 1, cy - r // 3, 1, 1))
        tail_x = cx + (r + 1) * (1 if (self._clock // 8) % 2 else -1)
        pygame.draw.line(self._canvas, pal.ORANGE, (cx, cy + r // 2), (tail_x, cy - r // 2))

    def _sort(self, x: float, y: float) -> float:
        return self.camera.rotate(x - c.FIELD_WIDTH / 2, y - c.FIELD_HEIGHT / 2)[1]

    def _burst(self, x: float, y: float, color: pal.Color, count: int) -> None:
        if self.settings.particles:
            self.particles.burst(x, y, color, count)

    def _shake(self, strength: float) -> None:
        if self.settings.shake:
            self.shake.trigger(strength)

    def _poly(self, points: list[Point], color: pal.Color) -> None:
        pygame.draw.polygon(self._canvas, color, [(round(x), round(y)) for x, y in points])

    def _quad(self, corners: list[Corner], color: pal.Color) -> None:
        projected = [self.camera.project(*corner) for corner in corners]
        self._poly([(p.sx, p.sy) for p in projected], color)

    def _draw_table(self, world: World) -> None:
        w, h = c.FIELD_WIDTH, c.FIELD_HEIGHT
        self._quad([(0, 0, 0), (w, 0, 0), (w, h, 0), (0, h, 0)], pal.NAVY)
        field_style = (
            self.settings.field_style
            if self.settings.field_style in FIELD_STYLES
            else "grid"
        )
        if field_style == "grid":
            self._draw_grid()
        elif field_style == "checker":
            self._draw_checkerboard()
        elif field_style == "neon":
            self._draw_grid(pal.shade(pal.BLUE, 0.75))
            self._draw_field_border(pal.UI_CYAN)
        self._draw_blind_zones(world)
        walls = (
            (world.players < 3 or not world.alive[2], 0.0),
            (world.players < 4 or not world.alive[3], h),
        )
        for is_wall, y in walls:
            if is_wall:
                self._quad([(0, y, 0), (w, y, 0), (w, y, 2), (0, y, 2)], pal.DARK_GREY)
        mid = self.camera.project(w / 2, 0), self.camera.project(w / 2, h)
        pygame.draw.line(
            self._canvas,
            pal.DARK_GREY,
            (round(mid[0].sx), round(mid[0].sy)),
            (round(mid[1].sx), round(mid[1].sy)),
        )

    def _draw_grid(self, color: pal.Color | None = None) -> None:
        w, h = c.FIELD_WIDTH, c.FIELD_HEIGHT
        color = color or pal.shade(pal.NAVY, 1.5)
        offset = (self._clock // 4) % GRID_STEP
        for k in range(-1, int(w // GRID_STEP) + 1):
            x = k * GRID_STEP + offset
            if 0 <= x <= w:
                a, b = self.camera.project(x, 0, 0), self.camera.project(x, h, 0)
                pygame.draw.line(
                    self._canvas, color, (round(a.sx), round(a.sy)), (round(b.sx), round(b.sy))
                )

    def _draw_checkerboard(self) -> None:
        columns, rows = 8, 6
        cell_w, cell_h = c.FIELD_WIDTH / columns, c.FIELD_HEIGHT / rows
        for row in range(rows):
            for column in range(columns):
                if (row + column) % 2:
                    continue
                x0, y0 = column * cell_w, row * cell_h
                x1, y1 = x0 + cell_w, y0 + cell_h
                self._quad(
                    [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)],
                    pal.shade(pal.BLUE, 0.2),
                )

    def _draw_field_border(self, color: pal.Color) -> None:
        corners = (
            (0.0, 0.0),
            (c.FIELD_WIDTH, 0.0),
            (c.FIELD_WIDTH, c.FIELD_HEIGHT),
            (0.0, c.FIELD_HEIGHT),
            (0.0, 0.0),
        )
        projected = [self.camera.project(x, y, 0.2) for x, y in corners]
        pygame.draw.lines(
            self._canvas,
            color,
            False,
            [(round(point.sx), round(point.sy)) for point in projected],
        )

    def _draw_blind_zones(self, world: World) -> None:
        for seat, effects in enumerate(world.extras.active):
            if any(effect.name == "blind" for effect in effects):
                self._draw_blind_zone(world, seat)

    def _draw_blind_zone(self, world: World, seat: int) -> None:
        half_w, half_h = c.FIELD_WIDTH / 2, c.FIELD_HEIGHT / 2
        bounds = (
            (0.0, 0.0, half_w, c.FIELD_HEIGHT)
            if seat == SEAT_LEFT
            else (half_w, 0.0, c.FIELD_WIDTH, c.FIELD_HEIGHT)
            if seat == SEAT_RIGHT
            else (0.0, 0.0, c.FIELD_WIDTH, half_h)
            if seat == SEAT_TOP
            else (0.0, half_h, c.FIELD_WIDTH, c.FIELD_HEIGHT)
        )
        x0, y0, x1, y1 = bounds
        columns, rows = (4, 6) if seat in (SEAT_LEFT, SEAT_RIGHT) else (8, 3)
        cell_w, cell_h = (x1 - x0) / columns, (y1 - y0) / rows
        colors = self._blind_ball_colors(world.ball)
        overlay = pygame.Surface(self._canvas.get_size(), pygame.SRCALPHA)
        for row in range(rows):
            for column in range(columns):
                color_index = (row * 2 + column) % len(colors)
                color = colors[color_index]
                if len(colors) == 1:
                    color = pal.shade(color, 0.72 if (row + column) % 2 else 1.0)
                corners = [
                    self.camera.project(x, y, 0.15)
                    for x, y in (
                        (x0 + column * cell_w, y0 + row * cell_h),
                        (x0 + (column + 1) * cell_w, y0 + row * cell_h),
                        (x0 + (column + 1) * cell_w, y0 + (row + 1) * cell_h),
                        (x0 + column * cell_w, y0 + (row + 1) * cell_h),
                    )
                ]
                pygame.draw.polygon(
                    overlay,
                    (*color, 190),
                    [(round(point.sx), round(point.sy)) for point in corners],
                )
        self._canvas.blit(overlay, (0, 0))

    def _blind_ball_colors(self, ball: Ball) -> tuple[pal.Color, ...]:
        style = (
            self.settings.ball_style
            if self.settings.ball_style in BALL_STYLES
            else "classic"
        )
        colors = {
            "classic": (pal.WHITE,),
            "pixel": (pal.ORANGE, pal.WHITE, pal.YELLOW),
            "energy": (pal.BLUE, pal.WHITE, pal.UI_CYAN),
            "ring": (pal.WHITE, pal.PINK),
        }[style]
        if ball.spin_rate > 0:
            return (*colors, pal.ORANGE)
        if ball.spin_rate < 0:
            return (*colors, pal.LIME)
        return colors

    def _box(self, rect: Rect, height: float, color: pal.Color) -> None:
        x0, x1 = rect.cx - rect.half_w, rect.cx + rect.half_w
        y0, y1 = rect.cy - rect.half_h, rect.cy + rect.half_h
        self._quad(
            [(x0 + 1, y0 + 1, 0), (x1 + 1, y0 + 1, 0), (x1 + 1, y1 + 1, 0), (x0 + 1, y1 + 1, 0)],
            pal.shade(pal.NAVY, 0.5),
        )
        for nx, ny in FACES:
            rx, ry = self.camera.rotate(nx, ny)
            face_x = rect.cx + nx * rect.half_w
            face_y = rect.cy + ny * rect.half_h
            centre_x = self.camera.rotate(face_x - c.FIELD_WIDTH / 2, face_y - c.FIELD_HEIGHT / 2)[
                0
            ]
            if not (ry > 0 or (ry == 0 and rx * centre_x < 0)):
                continue
            if nx == 0:
                bottom = [(x0, face_y, 0.0), (x1, face_y, 0.0)]
                top = [(x1, face_y, height), (x0, face_y, height)]
            else:
                bottom = [(face_x, y0, 0.0), (face_x, y1, 0.0)]
                top = [(face_x, y1, height), (face_x, y0, height)]
            shade = FRONT_FACE_SHADE if ry != 0 else SIDE_FACE_SHADE
            self._quad(bottom + top, pal.shade(color, shade))
        self._quad([(x0, y0, height), (x1, y0, height), (x1, y1, height), (x0, y1, height)], color)

    def _pickup(self, world: World, index: int) -> None:
        pickup = world.extras.pickups[index]
        spec = world.extras.specs[pickup.name]
        color = CATEGORY_COLORS.get(spec.category, pal.WHITE)
        if pickup.ttl < PICKUP_BLINK_TICKS and (pickup.ttl // PICKUP_BLINK_PERIOD) % 2:
            return
        half = c.PICKUP_RADIUS
        self._box(Rect(pickup.pos.x, pickup.pos.y, half, half), PICKUP_HEIGHT, color)
        if pickup.target is not None:
            p = self.camera.project(pickup.pos.x, pickup.pos.y, PICKUP_HEIGHT + 1.0)
            pygame.draw.rect(
                self._canvas,
                self.colors[pickup.target],
                (round(p.sx) - 2, round(p.sy) - 2, 5, 5),
                1,
            )
        p = self.camera.project(pickup.pos.x, pickup.pos.y, PICKUP_HEIGHT + 1.0)
        label = self.translator.translate(f"extras.{pickup.name}.name")
        label_width = text_width(label, SMALL_TEXT)
        label_x = min(
            max(round(p.sx) - label_width // 2, 0),
            max(0, self._canvas.get_width() - label_width),
        )
        draw_text(
            self._canvas,
            label,
            label_x,
            round(p.sy) - LABEL_GAP,
            pal.WHITE,
            SMALL_TEXT,
        )

    def _draw_shields(self, world: World) -> None:
        for seat in range(world.players):
            if not world.alive[seat] or not any(
                e.name == "shield" for e in world.extras.active[seat]
            ):
                continue
            if seat in (SEAT_LEFT, SEAT_RIGHT):
                x = SHIELD_GAP if seat == SEAT_LEFT else c.FIELD_WIDTH - SHIELD_GAP
                a, b = (x, 0.0), (x, c.FIELD_HEIGHT)
            else:
                y = SHIELD_GAP if seat == SEAT_TOP else c.FIELD_HEIGHT - SHIELD_GAP
                a, b = (0.0, y), (c.FIELD_WIDTH, y)
            pa = self.camera.project(a[0], a[1], BALL_LIFT)
            pb = self.camera.project(b[0], b[1], BALL_LIFT)
            pygame.draw.line(
                self._canvas,
                self.colors[seat],
                (round(pa.sx), round(pa.sy)),
                (round(pb.sx), round(pb.sy)),
            )

    def _draw_lasers(self) -> None:
        for shooter, (x, y), color, _ in self._lasers:
            p = self.camera.project(x, y, BALL_LIFT)
            origin = self.camera.project(shooter[0], shooter[1], BALL_LIFT)
            pygame.draw.line(
                self._canvas,
                color,
                (round(origin.sx), round(origin.sy)),
                (round(p.sx), round(p.sy)),
            )

    def _ball(self, world: World, index: int = 0) -> None:
        ball = world.balls[index]
        if self.settings.trail and index == 0:
            for age, (tx, ty) in enumerate(self.trail.points):
                p = self.camera.project(tx, ty, BALL_LIFT)
                shade = (age + 1) / (len(self.trail.points) + 1)
                radius = max(1, round(ball.radius * p.scale * shade * 0.6))
                center = (round(p.sx), round(p.sy))
                trail_style = (
                    self.settings.trail_style
                    if self.settings.trail_style in TRAIL_STYLES
                    else "classic"
                )
                color = (
                    (pal.BLUE, pal.PINK, pal.ORANGE)[age % 3]
                    if trail_style == "neon"
                    else pal.shade(pal.WHITE, 0.4 * shade + 0.2)
                )
                if trail_style == "pixel":
                    pygame.draw.rect(
                        self._canvas,
                        color,
                        (
                            center[0] - radius,
                            center[1] - radius,
                            radius * 2 + 1,
                            radius * 2 + 1,
                        ),
                    )
                else:
                    pygame.draw.circle(self._canvas, color, center, radius)
        ground = self.camera.project(ball.pos.x, ball.pos.y, 0.0)
        radius = max(1, round(ball.radius * ground.scale))
        shadow_rect = pygame.Rect(0, 0, radius * 2, max(1, radius))
        shadow_rect.center = (round(ground.sx), round(ground.sy))
        pygame.draw.ellipse(self._canvas, pal.shade(pal.NAVY, 0.4), shadow_rect)
        p = self.camera.project(ball.pos.x, ball.pos.y, BALL_LIFT)
        center = (round(p.sx), round(p.sy))
        ball_style = (
            self.settings.ball_style if self.settings.ball_style in BALL_STYLES else "classic"
        )
        if ball_style == "pixel":
            pygame.draw.rect(
                self._canvas,
                pal.ORANGE,
                (center[0] - radius, center[1] - radius, radius * 2 + 1, radius * 2 + 1),
            )
            pygame.draw.rect(
                self._canvas,
                pal.WHITE,
                (
                    center[0] - max(1, radius // 2),
                    center[1] - max(1, radius // 2),
                    max(2, radius),
                    max(2, radius),
                ),
            )
        elif ball_style == "energy":
            pygame.draw.circle(self._canvas, pal.BLUE, center, radius + 1)
            pygame.draw.circle(self._canvas, pal.WHITE, center, max(1, radius - 1))
        elif ball_style == "ring":
            pygame.draw.circle(self._canvas, pal.WHITE, center, radius)
            pygame.draw.circle(self._canvas, pal.PINK, center, max(1, radius - 1), 1)
        else:
            pygame.draw.circle(self._canvas, pal.WHITE, center, radius)
        mark = (
            max(
                0,
                min(
                    self._canvas.get_width() - 1,
                    round(p.sx + math.cos(ball.rotation) * max(1, radius - 1)),
                ),
            ),
            max(
                0,
                min(
                    self._canvas.get_height() - 1,
                    round(p.sy + math.sin(ball.rotation) * max(1, radius - 1)),
                ),
            ),
        )
        self._canvas.set_at(
            mark,
            (
                pal.ORANGE
                if ball.spin_rate > 0
                else pal.LIME
                if ball.spin_rate < 0
                else pal.YELLOW
                if ball_style == "pixel"
                else pal.UI_CYAN
                if ball_style == "energy"
                else pal.PINK
                if ball_style == "ring"
                else pal.WHITE
            ),
        )

    def _missile(self, world: World, index: int) -> None:
        missile = world.extras.missiles[index]
        p = self.camera.project(missile.pos.x, missile.pos.y, BALL_LIFT)
        length = missile.vel.length()
        if length <= 0.0:
            return
        dx = missile.vel.x / length * max(2.0, missile.radius * 2.0)
        dy = missile.vel.y / length * max(2.0, missile.radius * 2.0)
        nose = self.camera.project(missile.pos.x + dx, missile.pos.y + dy, BALL_LIFT)
        pygame.draw.line(
            self._canvas,
            self.colors[missile.owner],
            (round(p.sx), round(p.sy)),
            (round(nose.sx), round(nose.sy)),
            2,
        )

    def _portal(self, world: World, index: int) -> None:
        portal = world.portals[index]
        point = self.camera.project(portal.x, portal.y, 0.5)
        center = (round(point.sx), round(point.sy))
        pulse = math.sin(self._clock / 3.0 + index * math.pi)
        radius = max(4, round((7.0 + pulse) * point.scale))
        color = pal.UI_CYAN if index == 0 else pal.PINK
        pygame.draw.circle(self._canvas, color, center, radius, 2)
        pygame.draw.circle(self._canvas, pal.WHITE, center, max(1, radius - 3), 1)
        pygame.draw.circle(self._canvas, pal.NAVY, center, max(1, radius // 2))

    def _draw_particles(self) -> None:
        for part in self.particles.particles:
            p = self.camera.project(part.x, part.y, part.z)
            self._canvas.fill(part.color, (round(p.sx), round(p.sy), 1, 1))

    def _draw_explosions(self) -> None:
        for explosion in self.explosions:
            progress = explosion.progress
            point = self.camera.project(explosion.x, explosion.y, BALL_LIFT)
            center = (round(point.sx), round(point.sy))
            radius = max(2, round((3.0 + 17.0 * progress) * point.scale))
            for offset, color in (
                (0.0, pal.YELLOW),
                (0.28, pal.ORANGE),
                (0.56, pal.RED),
            ):
                ring_radius = max(1, round(radius * (1.0 - offset)))
                pygame.draw.circle(self._canvas, color, center, ring_radius, 1)

    def _seat_label(self, seat: int) -> str:
        return self.translator.translate("hud.player", number=seat + 1).upper()

    def _draw_hud(self, world: World, view: Viewport) -> None:
        w, h = view.rect.size
        if view.seat is None:
            score_positions = self._draw_shared_scores(world, w)
        else:
            score_positions = self._draw_split_scores(world, view.seat, w)
        message = None
        message_y = h // 2
        if world.phase is Phase.SERVING:
            countdown = world.countdown_number
            message = (
                str(countdown)
                if countdown is not None
                else self.translator.translate("hud.get_ready")
            )
            if countdown is not None:
                corners = [
                    self.camera.project(x, y)
                    for x, y in (
                        (0.0, 0.0),
                        (c.FIELD_WIDTH, 0.0),
                        (c.FIELD_WIDTH, c.FIELD_HEIGHT),
                        (0.0, c.FIELD_HEIGHT),
                    )
                ]
                message_y = min(
                    h - GLYPH_H * BIG_TEXT,
                    round(max(point.sy for point in corners)) + HUD_MARGIN,
                )
        elif world.phase is Phase.FINISHED and world.winner is not None:
            message = self.translator.translate(
                "match.score.winner", player=self._seat_label(world.winner)
            )
        if message:
            text = message.upper()
            size = BIG_TEXT if world.countdown_number is not None else SMALL_TEXT
            x = (w - text_width(text, size)) // 2
            draw_text(self._canvas, text, x, message_y, pal.WHITE, size)
        if world.config.mode == "timed":
            duration = world.mode.values["duration_seconds"]
            remaining = max(0, duration * c.TICK_RATE - world.tick)
            seconds = (remaining + c.TICK_RATE - 1) // c.TICK_RATE
            clock = f"{seconds // 60:02d}:{seconds % 60:02d}"
            draw_text(
                self._canvas,
                clock,
                (w - text_width(clock, SMALL_TEXT)) // 2,
                h - GLYPH_H - HUD_MARGIN,
                pal.YELLOW,
                SMALL_TEXT,
            )
        self._draw_effects(world, score_positions, view.seat)

    def _draw_effects(
        self, world: World, positions: dict[int, tuple[int, int]], own_seat: int | None
    ) -> None:
        line_height = GLYPH_H * SMALL_TEXT + 1
        width = self._canvas.get_width()
        occupied: list[pygame.Rect] = []
        for seat, (x, y) in positions.items():
            labels = [
                f"{self.translator.translate(f'extras.{effect.name}.name')} "
                f"{effect.remaining // c.TICK_RATE + 1}"
                for effect in world.extras.active[seat]
            ]
            weapon = world.extras.weapons[seat]
            if weapon is not None:
                name = self.translator.translate(f"extras.{weapon[0]}.name")
                labels.append(f"{name} X{weapon[1]}")
            for row, label in enumerate(labels):
                label_width = text_width(label, SMALL_TEXT)
                left = 0
                right = width
                if own_seat is None and world.players > SPLIT_COLUMNS:
                    left = 0 if seat in (0, 2) else width // SPLIT_COLUMNS
                    right = left + width // SPLIT_COLUMNS
                label_x = min(max(x, left), max(left, right - label_width))
                row_y = y + row * line_height
                if own_seat is None and world.players > SPLIT_COLUMNS and seat >= SPLIT_COLUMNS:
                    row_y += 2 * line_height
                label_rect = pygame.Rect(label_x, row_y, label_width, line_height)
                while any(label_rect.colliderect(placed) for placed in occupied):
                    row_y += line_height
                    label_rect.y = row_y
                occupied.append(label_rect)
                draw_text(
                    self._canvas,
                    label,
                    label_x,
                    row_y,
                    self.colors[seat],
                    SMALL_TEXT,
                )

    def _draw_shared_scores(self, world: World, w: int) -> dict[int, tuple[int, int]]:
        mid = w // 2
        slots = [
            HUD_MARGIN,
            w - HUD_MARGIN,
            mid - SHARED_SLOT_OFFSET,
            mid + SHARED_SLOT_OFFSET,
        ]
        if world.players == SPLIT_COLUMNS:
            slots = [mid - SHARED_DUEL_OFFSET, mid + SHARED_DUEL_OFFSET]
        positions: dict[int, tuple[int, int]] = {}
        for seat, score in enumerate(world.scores):
            x = slots[seat]
            color = self.colors[seat] if world.alive[seat] else pal.DARK_GREY
            label, value = self._seat_label(seat), str(score)
            width = max(text_width(value, BIG_TEXT), text_width(label, SMALL_TEXT))
            if world.players > SPLIT_COLUMNS and seat == 1:
                x -= width
            elif world.players == SPLIT_COLUMNS:
                x -= width // 2
            draw_text(self._canvas, label, x, HUD_TOP, color, SMALL_TEXT)
            draw_text(self._canvas, value, x, HUD_TOP + LABEL_GAP, color, BIG_TEXT)
            positions[seat] = (
                x,
                HUD_TOP + LABEL_GAP + BIG_TEXT * GLYPH_H + HUD_MARGIN,
            )
        return positions

    def _draw_split_scores(self, world: World, own: int, w: int) -> dict[int, tuple[int, int]]:
        x = HUD_MARGIN
        positions: dict[int, tuple[int, int]] = {}
        for seat in sorted(range(world.players), key=lambda s: s != own):
            color = self.colors[seat] if world.alive[seat] else pal.DARK_GREY
            text = f"{self._seat_label(seat)} {world.scores[seat]}"
            size = BIG_TEXT if seat == own else SMALL_TEXT
            if x + text_width(text, size) > w:
                break
            draw_text(self._canvas, text, x, HUD_TOP, color, size)
            positions[seat] = (x, HUD_TOP + max(size, SMALL_TEXT) * GLYPH_H + HUD_MARGIN)
            x += text_width(text, size) + HUD_MARGIN
        return positions
