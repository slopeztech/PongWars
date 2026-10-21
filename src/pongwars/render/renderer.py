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
    BallReleased,
    BallSwallowed,
    BallWarped,
    BombDetonated,
    BumperHit,
    EffectApplied,
    Event,
    Goal,
    LaserFired,
    LeviathanRoared,
    MissileHit,
    PaddleHit,
    PickupCollected,
    StalkerExploded,
    WallHit,
)
from pongwars.domain.vec import Vec2
from pongwars.domain.world import SEAT_LEFT, SEAT_RIGHT, SEAT_TOP, Phase, World
from pongwars.render import palette as pal
from pongwars.render.backgrounds import draw_background
from pongwars.render.camera import DEFAULT_BACK, DEFAULT_FOCAL, DEFAULT_HEIGHT, Camera
from pongwars.render.effects import Explosion, ParticleSystem, Shake, Trail
from pongwars.render.extras_icons import PICKUP_ICONS
from pongwars.render.font import GLYPH_H, draw_text, text_width
from pongwars.render.hud import HUD_CATEGORY_COLORS, HUD_STYLES, HudRenderer

LOW_W = 320
LOW_H = 180
PADDLE_HEIGHT = 4.0
OBSTACLE_HEIGHT = 5.0
BALL_LIFT = 2.0
SHAKE_GOAL = 4.0
SHAKE_HIT = 1.0
HUD_MARGIN = 4
BIG_TEXT = 2
SMALL_TEXT = 1
SIDE_FACE_SHADE = 0.45
FRONT_FACE_SHADE = 0.6
SEAT_TURNS = {3: 0, 1: 1, 2: 2, 0: 3}
SPLIT_COLUMNS = 2
PICKUP_HEIGHT = 5.5
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
ODD_TURN_ZOOM = 1.6
KIND_COLORS = {
    "solid": pal.LAVENDER,
    "bumper": pal.ORANGE,
    "moving": pal.PINK,
    "destructible": pal.BROWN,
    "built": pal.UI_CYAN,
}
Point = tuple[float, float]
Corner = tuple[float, float, float]
ViewMode = Literal["shared", "split"]
FACES = ((0, -1), (0, 1), (-1, 0), (1, 0))
CATEGORY_COLORS = HUD_CATEGORY_COLORS


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
    hud_style: str = "arcade"
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
        self.hud = HudRenderer()
        self.camera = Camera(LOW_W, LOW_H)
        self.surface = pygame.Surface((LOW_W, LOW_H))
        self._canvas = self.surface
        self.particles = ParticleSystem(seed)
        self.trail = Trail()
        self.shake = Shake(seed)
        self._lasers: list[tuple[Point, Point, pal.Color, int]] = []
        self.explosions: list[Explosion] = []
        self._clock = 0
        self._ramp_incline = 0.0
        self._field_layer: pygame.Surface | None = None
        self._field_mask: pygame.Surface | None = None
        self.colors = [
            pal.PADDLE_PALETTE[i % len(pal.PADDLE_PALETTE)] for i in self.settings.paddle_colors
        ]
        self.colors += list(pal.PLAYER_COLORS[len(self.colors) :])

    def set_settings(self, settings: RenderSettings) -> None:
        """Replace visual options and refresh the per-seat paddle palette."""
        self.settings = settings
        self.colors = [
            pal.PADDLE_PALETTE[i % len(pal.PADDLE_PALETTE)] for i in settings.paddle_colors
        ]
        self.colors += list(pal.PLAYER_COLORS[len(self.colors) :])

    def handle_events(self, world: World, events: Iterable[Event]) -> None:
        """@brief React to simulation events with visual effects.
        @param world World the events came from.
        @param events Events emitted by the last step.
        """
        pos = world.ball.pos
        for event in events:
            if isinstance(event, StalkerExploded):
                self.explosions.append(Explosion(event.x, event.y))
                self._burst(event.x, event.y, pal.LIME, 28)
                self._shake(SHAKE_GOAL * 0.8)
            elif isinstance(event, BallSwallowed):
                self._burst(event.x, event.y, pal.YELLOW, 10)
            elif isinstance(event, BallReleased):
                self._burst(event.x, event.y, pal.UI_CYAN, 14)
            elif isinstance(event, LeviathanRoared):
                self._burst(c.FIELD_WIDTH / 2, c.FIELD_HEIGHT / 2, pal.LAVENDER, 24)
                self._shake(SHAKE_GOAL)
            elif isinstance(event, LaserFired):
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
                if event.target is not None:
                    self.explosions.append(Explosion(event.x, event.y))
                    self._burst(event.x, event.y, pal.YELLOW, 16)
            elif isinstance(event, BombDetonated):
                self.explosions.append(Explosion(event.x, event.y))
                self._burst(event.x, event.y, pal.YELLOW, 28)
            elif isinstance(event, BallWarped):
                self._burst(event.x, event.y, pal.UI_CYAN, 12)
            elif isinstance(event, PickupCollected):
                self._burst(pos.x, pos.y, pal.LIME, 10)
            elif isinstance(event, EffectApplied) and event.name == "ramp":
                paddle = world.paddles[event.player].rect
                self._burst(paddle.cx, paddle.cy, pal.ORANGE, 18)
                self._shake(SHAKE_GOAL * 0.65)
            elif isinstance(event, MissileHit):
                self._burst(event.x, event.y, pal.ORANGE, 8)
                if event.target is not None:
                    self.explosions.append(Explosion(event.x, event.y))
                    self._burst(event.x, event.y, pal.YELLOW, 16)
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
        blend = 1.0 - math.exp(-max(0.0, dt) / c.RAMP_VISUAL_RESPONSE)
        self._ramp_incline += (world.ramp_incline - self._ramp_incline) * blend
        self._lasers = [(a, b, col, n - 1) for a, b, col, n in self._lasers if n > 1]
        for explosion in self.explosions:
            explosion.update(dt)
        self.explosions = [e for e in self.explosions if e.progress < 1.0]
        if self.settings.trail and world.phase.value == "playing" and not world.ball.swallowed:
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
            self.camera = self._camera_for(view, world)
            draw_background(self._canvas, self.settings.background, self._clock)
            self._draw_scene(world)
            self._draw_hud(world, view)
        self._canvas = self.surface
        return self.surface

    def draw_preview(self, world: World) -> pygame.Surface:
        """Render the arena without HUD for use in the live appearance preview."""
        self.surface.fill(pal.BLACK)
        self._canvas = self.surface
        view = Viewport(pygame.Rect(0, 0, LOW_W, LOW_H), None, 0)
        self.camera = self._camera_for(view, world)
        draw_background(self._canvas, self.settings.background, self._clock)
        try:
            self._draw_scene(world)
        finally:
            self._canvas = self.surface
        return self.surface

    def draw_hud_preview(self, world: World) -> pygame.Surface:
        """Render a sample match HUD with the configured HUD appearance."""
        self.surface.fill(pal.BLACK)
        self._canvas = self.surface
        self.camera = self._camera_for(Viewport(pygame.Rect(0, 0, LOW_W, LOW_H), None, 0), world)
        self.hud.draw(
            self.surface,
            world,
            self.camera,
            self.translator,
            self.colors,
            self.settings.hud_style,
            own_seat=None,
        )
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

    def _camera_for(self, view: Viewport, world: World | None = None) -> Camera:
        w, h = view.rect.size
        gravity_well = world is not None and world.config.arena == "gravity"
        underside = self._leviathan_amount(world) if world is not None else 0.0
        if view.seat is None:
            return Camera(
                w,
                h,
                back=DEFAULT_BACK * (1 - underside) - 110.0 * underside,
                height=DEFAULT_HEIGHT * (1 - underside) - 80.0 * underside,
                incline=self._ramp_incline,
                gravity_well=gravity_well,
            )
        # Odd turns look along the long table axis, so pull the camera back and widen less.
        extent = (c.FIELD_WIDTH - c.FIELD_HEIGHT) / 2 if view.turns % 2 else 0.0
        focal = DEFAULT_FOCAL * w / LOW_W * (ODD_TURN_ZOOM if view.turns % 2 else 1.0)
        if view.turns % 2 and h < LOW_H:
            # Fit the rotated field in short panes and leave room for the countdown HUD.
            focal = min(focal, DEFAULT_FOCAL * h / LOW_H * 0.8)
        back = DEFAULT_BACK + extent
        height = DEFAULT_HEIGHT + extent
        return Camera(
            w,
            h,
            back=back * (1 - underside) - 110.0 * underside,
            height=height * (1 - underside) - 80.0 * underside,
            focal=focal,
            quarter_turns=view.turns,
            incline=self._ramp_incline,
            gravity_well=gravity_well,
        )

    def _draw_scene(self, world: World) -> None:
        if self._leviathan_amount(world) > 0.0:
            self._draw_leviathan(world)
        self._draw_table(world)
        items: list[tuple[float, str, int]] = []
        items += [
            (self._sort(portal.x, portal.y), "portal", i) for i, portal in enumerate(world.portals)
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
        items += [
            (self._sort(invader.pos.x, invader.pos.y), "invader", i)
            for i, invader in enumerate(world.extras.invaders)
        ]
        items += [
            (self._sort(stalker.pos.x, stalker.pos.y), "stalker", i)
            for i, stalker in enumerate(world.extras.stalkers)
        ]
        items += [
            (self._sort(chomper.pos.x, chomper.pos.y), "chomper", i)
            for i, chomper in enumerate(world.extras.chompers)
            if chomper.phase in ("roaming", "seeking", "releasing")
            and any(chomper.ball is ball for ball in world.balls)
        ]
        items = [item for item in items if item[1] != "ball" or not world.balls[item[2]].swallowed]
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
            elif kind == "invader":
                self._invader(world, index)
            elif kind == "stalker":
                self._stalker(world, index)
            elif kind == "chomper":
                self._chomper(world, index)
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
        elif skin >= 4:
            vertical = rect.half_h >= rect.half_w
            long_size = 2 * (rect.half_h if vertical else rect.half_w)
            short_size = 2 * (rect.half_w if vertical else rect.half_h)
            accent = pal.shade(pal.WHITE, 0.82)

            def point(fraction: float, across: float = 0.0) -> tuple[float, float]:
                along = (fraction - 0.5) * long_size
                across *= short_size / 2
                return (
                    (rect.cx + across, rect.cy + along)
                    if vertical
                    else (rect.cx + along, rect.cy + across)
                )

            def mark(fraction: float, size: float, color: pal.Color = accent) -> None:
                px, py = point(fraction)
                projected = self.camera.project(px, py, top + 0.1)
                pygame.draw.circle(
                    self._canvas,
                    color,
                    (round(projected.sx), round(projected.sy)),
                    max(1, round(size * projected.scale)),
                )

            def line(
                start: tuple[float, float], end: tuple[float, float], color: pal.Color = accent
            ) -> None:
                first = self.camera.project(*start, top + 0.1)
                last = self.camera.project(*end, top + 0.1)
                pygame.draw.line(
                    self._canvas,
                    color,
                    (round(first.sx), round(first.sy)),
                    (round(last.sx), round(last.sy)),
                )

            pattern = skin - 4
            fractions = (0.2, 0.4, 0.6, 0.8)
            if pattern == 0:
                for fraction in fractions:
                    mark(fraction, 0.5)
            elif pattern == 1:
                rows, columns = 4, 2
                for row in range(rows):
                    for column in range(columns):
                        if (row + column) % 2:
                            continue
                        if vertical:
                            xa = x0 + (x1 - x0) * column / columns
                            xb = x0 + (x1 - x0) * (column + 1) / columns
                            ya = y0 + (y1 - y0) * row / rows
                            yb = y0 + (y1 - y0) * (row + 1) / rows
                        else:
                            xa = x0 + (x1 - x0) * row / rows
                            xb = x0 + (x1 - x0) * (row + 1) / rows
                            ya = y0 + (y1 - y0) * column / columns
                            yb = y0 + (y1 - y0) * (column + 1) / columns
                        self._quad(
                            [(xa, ya, top), (xb, ya, top), (xb, yb, top), (xa, yb, top)],
                            pal.shade(color, 0.48),
                        )
            elif pattern == 2:
                for fraction in fractions:
                    line(
                        point(fraction - 0.04, -0.55),
                        point(fraction, 0.0),
                    )
                    line(
                        point(fraction, 0.0),
                        point(fraction - 0.04, 0.55),
                    )
            elif pattern == 3:
                for across in (-0.35, 0.35):
                    line(point(0.05, across), point(0.95, across))
            elif pattern == 4:
                for fraction in fractions:
                    line(point(fraction, -0.35), point(fraction, 0.35))
            elif pattern == 5:
                for fraction in (0.25, 0.5, 0.75):
                    center_x, center_y = point(fraction)
                    size = long_size * 0.07
                    projected = [
                        self.camera.project(px, py, top + 0.1)
                        for px, py in (
                            (center_x, center_y - size),
                            (center_x + size, center_y),
                            (center_x, center_y + size),
                            (center_x - size, center_y),
                        )
                    ]
                    pygame.draw.polygon(
                        self._canvas,
                        accent,
                        [(round(p.sx), round(p.sy)) for p in projected],
                        1,
                    )
            elif pattern == 6:
                for fraction in (0.25, 0.5, 0.75):
                    center_x, center_y = point(fraction)
                    size = long_size * 0.07
                    projected = [
                        self.camera.project(px, py, top + 0.1)
                        for px, py in (
                            (center_x, center_y - size),
                            (center_x + size, center_y + size),
                            (center_x - size, center_y + size),
                        )
                    ]
                    pygame.draw.polygon(
                        self._canvas,
                        accent,
                        [(round(p.sx), round(p.sy)) for p in projected],
                        1,
                    )
            elif pattern == 7:
                wave_points = [
                    self.camera.project(
                        *point(fraction, math.sin(fraction * math.tau * 2) * 0.55),
                        top + 0.1,
                    )
                    for fraction in [step / 24 for step in range(1, 24)]
                ]
                pygame.draw.lines(
                    self._canvas,
                    accent,
                    False,
                    [(round(p.sx), round(p.sy)) for p in wave_points],
                )
            elif pattern == 8:
                for fraction in fractions:
                    line(point(fraction, -0.7), point(fraction, 0.7))
            elif pattern == 9:
                line(point(0.05), point(0.95))
                line(point(0.05, 0.45), point(0.95, 0.45), pal.shade(color, 0.55))
            elif pattern == 10:
                for fraction in fractions:
                    line(
                        point(fraction - 0.06, -0.55),
                        point(fraction + 0.06, 0.55),
                    )
            elif pattern == 11:
                zigzag = [
                    self.camera.project(
                        *point(fraction, -0.55 if step % 2 else 0.55),
                        top + 0.1,
                    )
                    for step, fraction in enumerate([index / 16 for index in range(1, 16)])
                ]
                pygame.draw.lines(
                    self._canvas,
                    accent,
                    False,
                    [(round(p.sx), round(p.sy)) for p in zigzag],
                )
            elif pattern == 12:
                for fraction in fractions:
                    ring_projection = self.camera.project(*point(fraction), top + 0.1)
                    pygame.draw.circle(
                        self._canvas,
                        accent,
                        (round(ring_projection.sx), round(ring_projection.sy)),
                        max(2, round(long_size * 0.09 * ring_projection.scale)),
                        1,
                    )
                    pygame.draw.circle(
                        self._canvas,
                        color,
                        (round(ring_projection.sx), round(ring_projection.sy)),
                        1,
                    )
            elif pattern == 13:
                for fraction in fractions:
                    line(
                        point(fraction - 0.035, -0.35),
                        point(fraction + 0.035, 0.35),
                    )
            elif pattern == 14:
                for fraction in fractions:
                    line(
                        point(fraction - 0.06, -0.5),
                        point(fraction + 0.06, 0.5),
                    )
                    line(
                        point(fraction - 0.06, 0.5),
                        point(fraction + 0.06, -0.5),
                    )
            elif pattern == 15:
                pulse = 0.55 + 0.4 * (0.5 + 0.5 * math.sin(self._clock / 5 + index + math.pi / 2))
                self._quad(
                    [(x0, y0, top), (x1, y0, top), (x1, y1, top), (x0, y1, top)],
                    pal.shade(pal.WHITE, pulse),
                )

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

    def _stalker(self, world: World, index: int) -> None:
        stalker = world.extras.stalkers[index]
        ground = self.camera.project(stalker.pos.x, stalker.pos.y)
        pixel = max(1, round(ground.scale * 0.75))
        cx = round(ground.sx)
        bob = round(math.sin(self._clock / 5.0 + index) * pixel * 0.5)
        foot_phase = round(math.sin(self._clock / 3.0 + index) * pixel)
        ground_y = round(ground.sy) + bob

        def block(x: int, y: int, width: int, height: int, color: pal.Color) -> None:
            self._canvas.fill(
                color,
                (
                    cx + x * pixel,
                    ground_y - (y + height) * pixel,
                    width * pixel,
                    height * pixel,
                ),
            )

        outline = (0, 55, 27)
        shadow = (0, 91, 39)
        mid_green = (0, 154, 47)
        bright_green = (40, 205, 57)
        highlight = (89, 238, 74)

        pygame.draw.line(
            self._canvas,
            pal.NAVY,
            (cx - 9 * pixel, ground_y + pixel),
            (cx + 9 * pixel, ground_y + pixel),
            max(1, pixel),
        )

        # Feet and blocky torso.
        block(-5, 0, 4, 4 + max(0, foot_phase), outline)
        block(1, 0, 4, 4 + max(0, -foot_phase), outline)
        block(-4, 1, 3, 3 + max(0, foot_phase), mid_green)
        block(2, 1, 3, 3 + max(0, -foot_phase), shadow)
        block(-4, 4, 8, 9, outline)
        block(-3, 5, 6, 7, mid_green)
        block(-2, 6, 2, 5, bright_green)
        block(1, 7, 1, 2, highlight)
        block(2, 5, 1, 2, shadow)
        block(-6, 5, 2, 6, outline)
        block(4, 5, 2, 6, outline)
        block(-5, 6, 1, 4, shadow)
        block(5, 6, 1, 4, mid_green)

        # Oversized square head with a dark pixel outline and shaded sides.
        block(-7, 12, 14, 10, outline)
        block(-6, 13, 12, 8, mid_green)
        block(-5, 14, 7, 6, bright_green)
        block(2, 14, 3, 6, shadow)
        block(-4, 19, 5, 1, highlight)
        block(3, 19, 1, 1, highlight)

        # Square black eyes and a downturned, pixel-stepped mouth.
        block(-4, 17, 2, 2, pal.BLACK)
        block(2, 17, 2, 2, pal.BLACK)
        block(-2, 14, 4, 1, pal.BLACK)
        block(-3, 15, 1, 2, pal.BLACK)
        block(2, 15, 1, 2, pal.BLACK)

    def _chomper(self, world: World, index: int) -> None:
        chomper = world.extras.chompers[index]
        target = chomper.ball.pos
        center = self.camera.project(chomper.pos.x, chomper.pos.y, BALL_LIFT)
        radius = max(3, round(c.CHOMPER_RADIUS * center.scale))
        cx, cy = round(center.sx), round(center.sy)
        pygame.draw.circle(self._canvas, pal.YELLOW, (cx, cy), radius)
        target_point = self.camera.project(target.x, target.y, BALL_LIFT)
        angle = math.atan2(target_point.sy - center.sy, target_point.sx - center.sx)
        aperture = 0.25 + 0.18 * (0.5 + 0.5 * math.sin(self._clock / 2))
        mouth = [
            (cx, cy),
            (
                round(cx + radius * math.cos(angle - aperture)),
                round(cy + radius * math.sin(angle - aperture)),
            ),
            (
                round(cx + radius * math.cos(angle + aperture)),
                round(cy + radius * math.sin(angle + aperture)),
            ),
        ]
        pygame.draw.polygon(self._canvas, pal.NAVY, mouth)
        glint = self.camera.project(chomper.pos.x - 1.2, chomper.pos.y - 1.5, BALL_LIFT + 0.5)
        self._canvas.fill(pal.WHITE, (round(glint.sx), round(glint.sy), 1, 1))

    def _leviathan_amount(self, world: World | None) -> float:
        if world is None:
            return 0.0
        transition = max(1, round(c.LEVIATHAN_TRANSITION_SECONDS * c.TICK_RATE))
        amount = 0.0
        for effects in world.extras.active:
            for effect in effects:
                if effect.name != "leviathan":
                    continue
                elapsed = effect.spec.ticks - effect.remaining
                progress = max(0.0, min(1.0, elapsed / transition, effect.remaining / transition))
                amount = max(amount, progress * progress * (3.0 - 2.0 * progress))
        return amount

    def _draw_leviathan(self, world: World) -> None:
        amount = self._leviathan_amount(world)
        edge_y = -5.0 + 100.0 * amount
        centre_x = c.FIELD_WIDTH / 2

        def screen(x: float, y: float, z: float) -> Point:
            point = self.camera.project(x, y, z)
            return round(point.sx), round(point.sy)

        def polygon(points: list[tuple[float, float, float]], color: pal.Color) -> None:
            pygame.draw.polygon(self._canvas, color, [screen(*point) for point in points])

        # Fan the limbs out from behind the skull; the board is drawn afterward to
        # occlude the parts that have already slipped underneath it.
        for arm in range(8):
            side = -1 if arm < 4 else 1
            fan = arm % 4
            root_x = centre_x + side * (5.0 + fan * 8.0)
            length = 22.0 + fan * 4.0
            points = []
            for step in range(11):
                fraction = step / 10
                x = (
                    root_x
                    + side * fraction * length * 0.75
                    + math.sin(self._clock / 7 + arm + fraction * 3.0) * (1 + fraction * 3)
                )
                y = edge_y + 7.0 + fraction * (13.0 + fan * 3.0)
                z = 7.0 + math.sin(self._clock / 6 + arm + fraction * 4) * 1.5
                points.append(screen(x, y, z))
            width = max(2, round(self.camera.project(root_x, edge_y, 8.0).scale * 6))
            pygame.draw.lines(self._canvas, pal.shade(pal.NAVY, 0.45), False, points, width + 2)
            pygame.draw.lines(self._canvas, pal.shade(pal.BLUE, 0.55), False, points, width)
            for step in (3, 5, 7, 9):
                pygame.draw.circle(
                    self._canvas,
                    pal.LAVENDER,
                    points[step],
                    max(1, round(width * (0.22 if step < 8 else 0.16))),
                )
            pygame.draw.circle(
                self._canvas,
                pal.PINK,
                points[-1],
                max(2, round(width * 0.65)),
            )

        skull = self.camera.project(centre_x, edge_y + 5.0, 17.0)
        skull_rect = pygame.Rect(
            0, 0, max(20, round(82 * skull.scale)), max(14, round(46 * skull.scale))
        )
        skull_rect.center = (round(skull.sx), round(skull.sy))
        pygame.draw.ellipse(self._canvas, pal.shade(pal.NAVY, 0.5), skull_rect.inflate(6, 4))
        pygame.draw.ellipse(self._canvas, pal.shade(pal.BLUE, 0.48), skull_rect)
        pygame.draw.ellipse(self._canvas, pal.LAVENDER, skull_rect, max(1, round(skull.scale * 2)))

        for side in (-1, 1):
            polygon(
                [
                    (centre_x + side * 24, edge_y + 1, 25),
                    (centre_x + side * 39, edge_y - 5, 30),
                    (centre_x + side * 32, edge_y + 9, 17),
                ],
                pal.shade(pal.LAVENDER, 0.65),
            )

            eye = self.camera.project(centre_x + side * 15.0, edge_y + 1.0, 25.0)
            eye_pos = (round(eye.sx), round(eye.sy))
            pygame.draw.circle(
                self._canvas,
                pal.shade(pal.NAVY, 0.45),
                eye_pos,
                max(3, round(eye.scale * 5)),
            )
            pygame.draw.circle(
                self._canvas,
                pal.ORANGE,
                eye_pos,
                max(2, round(eye.scale * 3)),
            )
            pygame.draw.circle(
                self._canvas,
                pal.WHITE,
                (eye_pos[0] - max(1, round(eye.scale)), eye_pos[1] - max(1, round(eye.scale))),
                max(1, round(eye.scale)),
            )

        jaw = self.camera.project(centre_x, edge_y + 13.0, 16.0)
        jaw_rect = pygame.Rect(0, 0, max(14, round(48 * jaw.scale)), max(5, round(13 * jaw.scale)))
        jaw_rect.center = (round(jaw.sx), round(jaw.sy))
        pygame.draw.ellipse(self._canvas, pal.PURPLE, jaw_rect)
        for tooth in range(7):
            x = centre_x + (tooth - 3) * 5.0
            polygon(
                [
                    (x - 1.8, edge_y + 9.0, 21),
                    (x + 1.8, edge_y + 9.0, 21),
                    (x, edge_y + 13.0, 21),
                ],
                pal.WHITE,
            )

        for spine in range(5):
            x = centre_x + (spine - 2) * 11.0
            polygon(
                [
                    (x - 4, edge_y - 2, 24),
                    (x, edge_y - 10 - (spine % 2) * 3, 31),
                    (x + 4, edge_y - 2, 24),
                ],
                pal.shade(pal.BLUE, 0.65),
            )

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
        if world.config.arena == "gravity":
            for x0 in range(0, int(w), 10):
                x1 = min(w, x0 + 10)
                for y0 in range(0, int(h), 10):
                    y1 = min(h, y0 + 10)
                    self._quad(
                        [
                            (x0, y0, 0),
                            (x1, y0, 0),
                            (x1, y1, 0),
                            (x0, y1, 0),
                        ],
                        pal.NAVY,
                    )
        else:
            self._quad([(0, 0, 0), (w, 0, 0), (w, h, 0), (0, h, 0)], pal.NAVY)
        field_style = (
            self.settings.field_style if self.settings.field_style in FIELD_STYLES else "grid"
        )
        self._draw_field_pattern(field_style)
        self._draw_blind_zones(world)
        walls = (
            (world.players < 3 or not world.alive[2], 0.0),
            (world.players < 4 or not world.alive[3], h),
        )
        for is_wall, y in walls:
            if is_wall:
                self._quad([(0, y, 0), (w, y, 0), (w, y, 2), (0, y, 2)], pal.DARK_GREY)
        middle = [self.camera.project(w / 2, y, 0) for y in range(0, int(h) + 1, 5)]
        pygame.draw.lines(
            self._canvas,
            pal.DARK_GREY,
            False,
            [(round(point.sx), round(point.sy)) for point in middle],
        )

    def _draw_grid(self, color: pal.Color | None = None) -> None:
        w, h = c.FIELD_WIDTH, c.FIELD_HEIGHT
        color = color or pal.shade(pal.NAVY, 1.5)
        offset = (self._clock // 4) % GRID_STEP
        for k in range(-1, int(w // GRID_STEP) + 1):
            x = k * GRID_STEP + offset
            if 0 <= x <= w:
                points = [self.camera.project(x, y, 0) for y in range(0, int(h) + 1, 5)]
                pygame.draw.lines(
                    self._canvas,
                    color,
                    False,
                    [(round(point.sx), round(point.sy)) for point in points],
                )

    def _draw_field_pattern(self, style: str) -> None:
        if style == "solid":
            return
        size = self._canvas.get_size()
        if self._field_layer is None or self._field_layer.get_size() != size:
            self._field_layer = pygame.Surface(size, pygame.SRCALPHA)
            self._field_mask = pygame.Surface(size, pygame.SRCALPHA)
        assert self._field_mask is not None
        canvas = self._canvas
        layer = self._field_layer
        mask = self._field_mask
        layer.fill((0, 0, 0, 0))
        mask.fill((0, 0, 0, 0))
        self._canvas = layer
        try:
            self._draw_field_pattern_unclipped(style)
        finally:
            self._canvas = canvas
        boundary = (
            ((0.0, 0.0), (c.FIELD_WIDTH, 0.0)),
            ((c.FIELD_WIDTH, 0.0), (c.FIELD_WIDTH, c.FIELD_HEIGHT)),
            ((c.FIELD_WIDTH, c.FIELD_HEIGHT), (0.0, c.FIELD_HEIGHT)),
            ((0.0, c.FIELD_HEIGHT), (0.0, 0.0)),
        )
        boundary_points = [
            self.camera.project(
                start_x + (end_x - start_x) * step / 32,
                start_y + (end_y - start_y) * step / 32,
                0,
            )
            for (start_x, start_y), (end_x, end_y) in boundary
            for step in range(32)
        ]
        pygame.draw.polygon(
            mask,
            (255, 255, 255, 255),
            [(round(point.sx), round(point.sy)) for point in boundary_points],
        )
        layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        canvas.blit(layer, (0, 0))

    def _draw_field_pattern_unclipped(self, style: str) -> None:
        if style == "grid":
            self._draw_grid()
        elif style == "checker":
            self._draw_checkerboard()
        elif style == "neon":
            self._draw_grid(pal.shade(pal.BLUE, 0.75))
            self._draw_field_border(pal.UI_CYAN)
        elif style in ("dots", "stars"):
            for x in range(10, int(c.FIELD_WIDTH), 20):
                for y in range(8, int(c.FIELD_HEIGHT), 16):
                    point = self.camera.project(x, y, 0)
                    center = (round(point.sx), round(point.sy))
                    if style == "dots":
                        pygame.draw.circle(self._canvas, pal.shade(pal.BLUE, 0.45), center, 1)
                    else:
                        radius = 3 + (x + y) % 3
                        vertices = [
                            self.camera.project(
                                x
                                + math.cos(step * math.pi / 5 - math.pi / 2)
                                * (radius if step % 2 == 0 else radius / 2),
                                y
                                + math.sin(step * math.pi / 5 - math.pi / 2)
                                * (radius if step % 2 == 0 else radius / 2),
                                0,
                            )
                            for step in range(10)
                        ]
                        pygame.draw.polygon(
                            self._canvas,
                            pal.YELLOW,
                            [(round(vertex.sx), round(vertex.sy)) for vertex in vertices],
                        )
        elif style in ("diagonal", "crosshatch"):
            step = 20
            color = pal.shade(pal.UI_CYAN if style == "diagonal" else pal.LAVENDER, 0.42)
            for offset in range(-int(c.FIELD_HEIGHT), int(c.FIELD_WIDTH), step):
                points = [
                    self.camera.project(x, y, 0)
                    for x, y in (
                        (max(0, offset), max(0, -offset)),
                        (
                            min(c.FIELD_WIDTH, offset + c.FIELD_HEIGHT),
                            min(c.FIELD_HEIGHT, c.FIELD_WIDTH - offset),
                        ),
                    )
                ]
                pygame.draw.line(
                    self._canvas,
                    color,
                    (round(points[0].sx), round(points[0].sy)),
                    (round(points[1].sx), round(points[1].sy)),
                )
                if style == "crosshatch":
                    points = [
                        self.camera.project(x, y, 0)
                        for x, y in (
                            (max(0, offset), min(c.FIELD_HEIGHT, c.FIELD_WIDTH - offset)),
                            (min(c.FIELD_WIDTH, offset + c.FIELD_HEIGHT), max(0, -offset)),
                        )
                    ]
                    pygame.draw.line(
                        self._canvas,
                        color,
                        (round(points[0].sx), round(points[0].sy)),
                        (round(points[1].sx), round(points[1].sy)),
                    )
        elif style in ("rings", "target", "radial"):
            ring_center = self.camera.project(c.FIELD_WIDTH / 2, c.FIELD_HEIGHT / 2, 0)
            if style in ("rings", "target"):
                for index, radius in enumerate(range(8, 49, 8)):
                    points = [
                        self.camera.project(
                            c.FIELD_WIDTH / 2 + math.cos(step * math.tau / 32) * radius,
                            c.FIELD_HEIGHT / 2 + math.sin(step * math.tau / 32) * radius,
                            0,
                        )
                        for step in range(33)
                    ]
                    pygame.draw.lines(
                        self._canvas,
                        pal.shade(
                            pal.PINK if style == "target" and index == 0 else pal.BLUE,
                            0.35 + index * 0.08,
                        ),
                        False,
                        [(round(point.sx), round(point.sy)) for point in points],
                    )
            if style == "target":
                half_w, half_h = c.FIELD_WIDTH / 2, c.FIELD_HEIGHT / 2
                crosshair = (
                    ((half_w, 0), (half_w, c.FIELD_HEIGHT)),
                    ((0, half_h), (c.FIELD_WIDTH, half_h)),
                )
                for start, end in crosshair:
                    points = [
                        self.camera.project(position[0], position[1], 0)
                        for position in (start, end)
                    ]
                    pygame.draw.lines(
                        self._canvas,
                        pal.PINK,
                        False,
                        [(round(point.sx), round(point.sy)) for point in points],
                    )
                pygame.draw.circle(
                    self._canvas,
                    pal.YELLOW,
                    (round(ring_center.sx), round(ring_center.sy)),
                    2,
                )
            if style == "radial":
                for angle in range(0, 360, 30):
                    edge = self.camera.project(
                        c.FIELD_WIDTH / 2 + math.cos(math.radians(angle)) * 75,
                        c.FIELD_HEIGHT / 2 + math.sin(math.radians(angle)) * 38,
                        0,
                    )
                    pygame.draw.line(
                        self._canvas,
                        pal.shade(pal.UI_CYAN, 0.4),
                        (round(ring_center.sx), round(ring_center.sy)),
                        (round(edge.sx), round(edge.sy)),
                    )
        elif style in ("stripes", "scanlines"):
            if style == "stripes":
                color = pal.shade(pal.BLUE, 0.35)
                stripe_width = c.FIELD_WIDTH / 9
                for stripe_x in (
                    c.FIELD_WIDTH / 6,
                    c.FIELD_WIDTH / 2,
                    5 * c.FIELD_WIDTH / 6,
                ):
                    self._quad(
                        [
                            (stripe_x, 0, 0),
                            (stripe_x + stripe_width, 0, 0),
                            (stripe_x + stripe_width, c.FIELD_HEIGHT, 0),
                            (stripe_x, c.FIELD_HEIGHT, 0),
                        ],
                        color,
                    )
            else:
                color = pal.shade(pal.BLUE, 0.25)
                for y in range(0, int(c.FIELD_HEIGHT), 6):
                    points = [
                        self.camera.project(x, y, 0) for x in range(0, int(c.FIELD_WIDTH) + 1, 10)
                    ]
                    pygame.draw.lines(
                        self._canvas,
                        color,
                        False,
                        [(round(point.sx), round(point.sy)) for point in points],
                    )
        elif style == "waves":
            for band in range(5):
                points = [
                    self.camera.project(
                        x,
                        c.FIELD_HEIGHT * (band + 1) / 6
                        + math.sin(x / 9 + self._clock / 12 + band) * 3,
                        0,
                    )
                    for x in range(0, int(c.FIELD_WIDTH) + 1, 4)
                ]
                pygame.draw.lines(
                    self._canvas,
                    pal.shade(pal.BLUE, 0.45),
                    False,
                    [(round(point.sx), round(point.sy)) for point in points],
                )
        elif style in ("diamonds", "boxes", "maze", "circuit", "lanes", "sparkle"):
            color = pal.shade(pal.UI_CYAN if style in ("circuit", "sparkle") else pal.BLUE, 0.48)
            if style == "boxes":
                for inset, box_color in ((0.12, color), (0.3, pal.PINK)):
                    x0, x1 = c.FIELD_WIDTH * inset, c.FIELD_WIDTH * (1 - inset)
                    y0, y1 = c.FIELD_HEIGHT * inset, c.FIELD_HEIGHT * (1 - inset)
                    points = [
                        self.camera.project(x, y, 0)
                        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
                    ]
                    pygame.draw.lines(
                        self._canvas,
                        box_color,
                        True,
                        [(round(point.sx), round(point.sy)) for point in points],
                    )
                return
            if style == "maze":
                paths = (
                    ((0.1, 0.1), (0.45, 0.1), (0.45, 0.45), (0.2, 0.45), (0.2, 0.8)),
                    ((0.9, 0.1), (0.65, 0.1), (0.65, 0.6), (0.4, 0.6), (0.4, 0.9)),
                    ((0.9, 0.8), (0.7, 0.8), (0.7, 0.4), (0.9, 0.4)),
                )
                for path in paths:
                    points = [
                        self.camera.project(x * c.FIELD_WIDTH, y * c.FIELD_HEIGHT, 0)
                        for x, y in path
                    ]
                    pygame.draw.lines(
                        self._canvas,
                        pal.LAVENDER,
                        False,
                        [(round(point.sx), round(point.sy)) for point in points],
                    )
                return
            if style == "circuit":
                for circuit_x, circuit_y in (
                    (0.2, 0.25),
                    (0.7, 0.3),
                    (0.38, 0.72),
                    (0.82, 0.75),
                ):
                    path = (
                        (circuit_x - 0.12, circuit_y),
                        (circuit_x, circuit_y),
                        (circuit_x, circuit_y + 0.16),
                        (circuit_x + 0.12, circuit_y + 0.16),
                    )
                    points = [
                        self.camera.project(px * c.FIELD_WIDTH, py * c.FIELD_HEIGHT, 0)
                        for px, py in path
                    ]
                    pygame.draw.lines(
                        self._canvas,
                        color,
                        False,
                        [(round(point.sx), round(point.sy)) for point in points],
                    )
                    endpoint = self.camera.project(
                        (circuit_x + 0.12) * c.FIELD_WIDTH,
                        (circuit_y + 0.16) * c.FIELD_HEIGHT,
                        0,
                    )
                    pygame.draw.circle(
                        self._canvas, pal.UI_CYAN, (round(endpoint.sx), round(endpoint.sy)), 1
                    )
                return
            if style == "lanes":
                for lane in (c.FIELD_WIDTH / 4, c.FIELD_WIDTH / 2, 3 * c.FIELD_WIDTH / 4):
                    points = [
                        self.camera.project(lane, y, 0)
                        for y in range(0, int(c.FIELD_HEIGHT) + 1, 5)
                    ]
                    pygame.draw.lines(
                        self._canvas,
                        color,
                        False,
                        [(round(point.sx), round(point.sy)) for point in points],
                        2 if lane == c.FIELD_WIDTH / 2 else 1,
                    )
                lane_center = self.camera.project(c.FIELD_WIDTH / 2, c.FIELD_HEIGHT / 2, 0)
                pygame.draw.circle(
                    self._canvas,
                    pal.WHITE,
                    (round(lane_center.sx), round(lane_center.sy)),
                    2,
                )
                return
            for x in range(0, int(c.FIELD_WIDTH), 20):
                for y in range(0, int(c.FIELD_HEIGHT), 15):
                    if style == "sparkle":
                        sparkle_center = self.camera.project(x + 10, y + 7, 0)
                        cx, cy = round(sparkle_center.sx), round(sparkle_center.sy)
                        pygame.draw.line(self._canvas, color, (cx - 2, cy), (cx + 2, cy))
                        pygame.draw.line(self._canvas, color, (cx, cy - 2), (cx, cy + 2))
                        continue
                    corners = [
                        (x + 10, y, 0),
                        (x + 20, y + 7.5, 0),
                        (x + 10, y + 15, 0),
                        (x, y + 7.5, 0),
                    ]
                    projected = [self.camera.project(px, py, 0) for px, py, _ in corners]
                    pygame.draw.lines(
                        self._canvas,
                        color,
                        True,
                        [(round(point.sx), round(point.sy)) for point in projected],
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
        style = self.settings.ball_style if self.settings.ball_style in BALL_STYLES else "classic"
        colors = {
            "classic": (pal.WHITE,),
            "pixel": (pal.ORANGE, pal.WHITE, pal.YELLOW),
            "energy": (pal.BLUE, pal.WHITE, pal.UI_CYAN),
            "ring": (pal.WHITE, pal.PINK),
            "star": (pal.YELLOW, pal.WHITE),
            "crystal": (pal.UI_CYAN, pal.BLUE, pal.WHITE),
            "sun": (pal.ORANGE, pal.YELLOW),
            "target": (pal.WHITE, pal.RED),
            "moon": (pal.LAVENDER, pal.WHITE),
            "flower": (pal.PINK, pal.YELLOW),
            "dice": (pal.WHITE, pal.BLACK),
            "eye": (pal.BLUE, pal.WHITE),
            "atom": (pal.UI_CYAN, pal.PINK),
            "gear": (pal.LIGHT_GREY, pal.WHITE),
            "prism": (pal.LIME, pal.BLUE, pal.PINK),
            "comet": (pal.ORANGE, pal.WHITE),
            "bubble": (pal.UI_CYAN, pal.WHITE),
            "spiral": (pal.PINK, pal.WHITE),
            "cross": (pal.LIME, pal.WHITE),
            "heart": (pal.RED, pal.PINK),
        }.get(style, (pal.WHITE,))
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
        bob = 0.45 + 0.45 * math.sin(self._clock / 7.0 + index)
        ground = self.camera.project(pickup.pos.x, pickup.pos.y, 0.0)
        glow = max(2, round((5.0 + math.sin(self._clock / 5.0) * 1.0) * ground.scale))
        shadow = pygame.Rect(0, 0, glow * 2, max(2, glow // 2))
        shadow.center = (round(ground.sx), round(ground.sy))
        pygame.draw.ellipse(self._canvas, pal.shade(color, 0.35), shadow)
        anchor = self.camera.project(
            pickup.pos.x,
            pickup.pos.y,
            PICKUP_HEIGHT / 2 + bob,
        )
        cell = max(1, round(anchor.scale * 0.78))
        front_w, front_h = 8 * cell, 8 * cell
        depth = 2 * cell
        left = round(anchor.sx - front_w / 2)
        top = round(anchor.sy - front_h / 2)
        right, bottom = left + front_w, top + front_h

        # Pixel beams behind the crate, with gaps to keep the arcade glow crisp.
        for offset, beam_height, beam_width in (
            (-3, 7, 1),
            (0, 9, 2),
            (3, 7, 1),
        ):
            beam_x = round(anchor.sx) + offset * cell
            for segment in range(3):
                segment_top = top - depth - (segment + 1) * 2 * cell
                if top - segment_top > beam_height * cell:
                    continue
                pygame.draw.rect(
                    self._canvas,
                    pal.shade(color, 0.62 if beam_width == 1 else 0.9),
                    (
                        beam_x - beam_width * cell // 2,
                        segment_top,
                        beam_width * cell,
                        cell,
                    ),
                )

        pygame.draw.polygon(
            self._canvas,
            pal.shade(color, 0.68),
            [
                (left, top),
                (right, top),
                (right + depth, top - depth),
                (left + depth, top - depth),
            ],
        )
        pygame.draw.polygon(
            self._canvas,
            pal.shade(color, 0.42),
            [
                (right, top),
                (right + depth, top - depth),
                (right + depth, bottom - depth),
                (right, bottom),
            ],
        )
        pygame.draw.rect(
            self._canvas,
            pal.shade(color, 0.28),
            (left - 1, top - 1, front_w + 2, front_h + 2),
        )
        pygame.draw.rect(self._canvas, color, (left, top, front_w, front_h))
        pygame.draw.rect(
            self._canvas,
            pal.shade(color, 0.38),
            (left + 1, top + 1, front_w - 2, front_h - 2),
        )
        icon = PICKUP_ICONS[pickup.name]
        icon_x = left + (front_w - len(icon[0]) * cell) // 2
        icon_y = top + (front_h - len(icon) * cell) // 2
        for row, pixels in enumerate(icon):
            for column, pixel in enumerate(pixels):
                if pixel == "1":
                    pygame.draw.rect(
                        self._canvas,
                        pal.WHITE,
                        (icon_x + column * cell, icon_y + row * cell, cell, cell),
                    )
        if pickup.target is not None:
            pygame.draw.rect(
                self._canvas,
                self.colors[pickup.target],
                (left - cell, top - cell, front_w + 2 * cell, front_h + 2 * cell),
                1,
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
            trail_colors = {
                "neon": (pal.BLUE, pal.PINK, pal.ORANGE),
                "comet": (pal.ORANGE, pal.YELLOW, pal.WHITE),
                "dotted": (pal.WHITE, pal.UI_CYAN),
                "rainbow": (pal.RED, pal.ORANGE, pal.YELLOW, pal.LIME, pal.BLUE, pal.PINK),
                "flame": (pal.YELLOW, pal.ORANGE, pal.RED),
                "frost": (pal.WHITE, pal.UI_CYAN, pal.BLUE),
                "spark": (pal.YELLOW, pal.WHITE, pal.ORANGE),
                "stars": (pal.WHITE, pal.YELLOW, pal.LAVENDER),
                "glitch": (pal.PINK, pal.UI_CYAN, pal.LIME),
                "orbit": (pal.LAVENDER, pal.PINK, pal.BLUE),
            }
            for age, (tx, ty) in enumerate(self.trail.points):
                p = self.camera.project(tx, ty, BALL_LIFT)
                shade = (age + 1) / (len(self.trail.points) + 1)
                radius = max(1, round(ball.radius * p.scale * shade * 0.6))
                if self.settings.trail_style == "fade":
                    radius = max(1, round(radius * shade))
                center = (round(p.sx), round(p.sy))
                trail_style = (
                    self.settings.trail_style
                    if self.settings.trail_style in TRAIL_STYLES
                    else "classic"
                )
                colors = trail_colors.get(trail_style)
                color = (
                    colors[age % len(colors)]
                    if colors
                    else pal.shade(pal.WHITE, 0.4 * shade + 0.2)
                    if trail_style in ("classic", "fade")
                    else pal.shade(pal.BLUE, 0.5 * shade + 0.2)
                )
                if trail_style == "fade":
                    color = pal.shade(pal.LAVENDER, 0.35 + shade * 0.65)
                if trail_style in ("pixel", "glitch"):
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
                elif trail_style == "squares":
                    pygame.draw.rect(
                        self._canvas,
                        color,
                        (center[0] - radius // 2, center[1] - radius // 2, radius + 1, radius + 1),
                    )
                elif trail_style in ("rings", "orbit"):
                    pygame.draw.circle(self._canvas, color, center, radius, 1)
                elif trail_style == "ripple":
                    pygame.draw.circle(self._canvas, color, center, radius, 1)
                    pygame.draw.circle(self._canvas, color, center, radius + 2, 1)
                elif trail_style == "double":
                    pygame.draw.circle(self._canvas, color, (center[0] - 2, center[1]), radius)
                    pygame.draw.circle(
                        self._canvas,
                        color,
                        (center[0] + 2, center[1]),
                        radius,
                    )
                elif trail_style == "ribbon":
                    pygame.draw.line(
                        self._canvas,
                        color,
                        (center[0] - radius * 2, center[1] + 2),
                        (center[0] + radius * 2, center[1] - 2),
                        max(1, radius),
                    )
                elif trail_style == "dash":
                    pygame.draw.line(
                        self._canvas,
                        color,
                        (center[0] - radius * 2, center[1]),
                        (center[0] + radius * 2, center[1]),
                        max(1, radius),
                    )
                elif trail_style == "comet":
                    pygame.draw.line(
                        self._canvas,
                        color,
                        (center[0] - radius * 2, center[1] + radius),
                        center,
                        max(1, radius),
                    )
                    pygame.draw.circle(self._canvas, color, center, radius)
                elif trail_style == "dotted":
                    pygame.draw.circle(self._canvas, color, center, max(1, radius // 2))
                elif trail_style == "frost":
                    pygame.draw.rect(
                        self._canvas,
                        color,
                        (center[0] - radius, center[1] - radius, radius * 2 + 1, radius * 2 + 1),
                    )
                elif trail_style == "spark":
                    pygame.draw.line(
                        self._canvas,
                        color,
                        (center[0] - radius, center[1]),
                        (center[0] + radius, center[1]),
                    )
                    pygame.draw.line(
                        self._canvas,
                        color,
                        (center[0], center[1] - radius),
                        (center[0], center[1] + radius),
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
            self._draw_ball_detail(ball_style, center, radius, ball.rotation)
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

    def _draw_ball_detail(
        self, style: str, center: tuple[int, int], radius: int, rotation: float
    ) -> None:
        colors = {
            "star": pal.YELLOW,
            "crystal": pal.UI_CYAN,
            "sun": pal.ORANGE,
            "target": pal.WHITE,
            "moon": pal.LAVENDER,
            "flower": pal.PINK,
            "dice": pal.WHITE,
            "eye": pal.WHITE,
            "atom": pal.UI_CYAN,
            "gear": pal.LIGHT_GREY,
            "prism": pal.PINK,
            "comet": pal.ORANGE,
            "bubble": pal.BLUE,
            "spiral": pal.LAVENDER,
            "cross": pal.LIME,
            "heart": pal.RED,
        }
        color = colors.get(style, pal.WHITE)
        cx, cy = center
        pygame.draw.circle(self._canvas, color, center, radius)
        if style == "star":
            vertices = [
                (
                    cx + round(math.cos(rotation + i * math.tau / 5) * radius),
                    cy + round(math.sin(rotation + i * math.tau / 5) * radius),
                )
                for i in range(5)
            ]
            pygame.draw.polygon(self._canvas, pal.WHITE, vertices, 1)
        elif style == "crystal":
            pygame.draw.polygon(
                self._canvas,
                pal.WHITE,
                [(cx, cy - radius), (cx + radius, cy), (cx, cy + radius), (cx - radius, cy)],
                1,
            )
        elif style == "sun":
            for spoke in range(8):
                angle = rotation + spoke * math.tau / 8
                start = (
                    cx + round(math.cos(angle) * (radius + 1)),
                    cy + round(math.sin(angle) * (radius + 1)),
                )
                end = (
                    cx + round(math.cos(angle) * (radius + 3)),
                    cy + round(math.sin(angle) * (radius + 3)),
                )
                pygame.draw.line(self._canvas, pal.YELLOW, start, end)
        elif style == "target":
            pygame.draw.circle(self._canvas, pal.RED, center, max(1, radius * 2 // 3), 1)
            pygame.draw.circle(self._canvas, pal.YELLOW, center, max(1, radius // 3), 1)
        elif style == "moon":
            pygame.draw.circle(self._canvas, pal.WHITE, (cx - 1, cy), radius, 1)
            pygame.draw.circle(
                self._canvas, pal.NAVY, (cx + radius // 2, cy - radius // 4), max(1, radius - 1)
            )
        elif style == "flower":
            for petal in range(6):
                angle = rotation + petal * math.tau / 6
                pos = (
                    cx + round(math.cos(angle) * radius // 2),
                    cy + round(math.sin(angle) * radius // 2),
                )
                pygame.draw.circle(self._canvas, pal.WHITE, pos, max(1, radius // 3))
        elif style == "dice":
            for dx, dy in ((-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)):
                pygame.draw.circle(self._canvas, pal.NAVY, (cx + dx, cy + dy), 1)
        elif style == "eye":
            pygame.draw.ellipse(
                self._canvas, pal.NAVY, (cx - radius, cy - radius // 2, radius * 2, radius)
            )
            pygame.draw.circle(self._canvas, pal.UI_CYAN, center, max(1, radius // 3))
        elif style == "atom":
            pygame.draw.ellipse(
                self._canvas, pal.WHITE, (cx - radius, cy - radius // 2, radius * 2, radius), 1
            )
            pygame.draw.ellipse(
                self._canvas, pal.WHITE, (cx - radius // 2, cy - radius, radius, radius * 2), 1
            )
            pygame.draw.circle(self._canvas, pal.PINK, center, 1)
        elif style == "gear":
            for tooth in range(8):
                angle = rotation + tooth * math.tau / 8
                start = (cx + round(math.cos(angle) * radius), cy + round(math.sin(angle) * radius))
                end = (
                    cx + round(math.cos(angle) * (radius + 2)),
                    cy + round(math.sin(angle) * (radius + 2)),
                )
                pygame.draw.line(self._canvas, pal.WHITE, start, end)
        elif style == "prism":
            pygame.draw.polygon(
                self._canvas,
                pal.WHITE,
                [(cx, cy - radius), (cx + radius, cy + radius), (cx - radius, cy + radius)],
                1,
            )
        elif style == "comet":
            pygame.draw.line(
                self._canvas,
                pal.YELLOW,
                (cx - radius * 3, cy + radius),
                (cx, cy),
                max(1, radius // 2),
            )
            pygame.draw.line(
                self._canvas, pal.WHITE, (cx - radius * 2, cy + radius * 2), (cx, cy), 1
            )
        elif style == "bubble":
            pygame.draw.circle(self._canvas, pal.WHITE, center, radius, 1)
            pygame.draw.circle(self._canvas, pal.WHITE, (cx - radius // 2, cy - radius // 2), 1)
        elif style == "spiral":
            pygame.draw.arc(
                self._canvas,
                pal.WHITE,
                (cx - radius, cy - radius, radius * 2, radius * 2),
                rotation,
                rotation + math.pi * 1.5,
                1,
            )
        elif style == "cross":
            pygame.draw.line(self._canvas, pal.WHITE, (cx - radius, cy), (cx + radius, cy), 1)
            pygame.draw.line(self._canvas, pal.WHITE, (cx, cy - radius), (cx, cy + radius), 1)
        elif style == "heart":
            pygame.draw.circle(
                self._canvas, pal.PINK, (cx - radius // 3, cy - radius // 4), max(1, radius // 2)
            )
            pygame.draw.circle(
                self._canvas, pal.PINK, (cx + radius // 3, cy - radius // 4), max(1, radius // 2)
            )
            pygame.draw.polygon(
                self._canvas, pal.PINK, [(cx - radius, cy), (cx + radius, cy), (cx, cy + radius)]
            )

    def _missile(self, world: World, index: int) -> None:
        missile = world.extras.missiles[index]
        p = self.camera.project(missile.pos.x, missile.pos.y, BALL_LIFT)
        if missile.kind == "bomb":
            radius = max(2, round(missile.radius * p.scale))
            pygame.draw.circle(self._canvas, pal.ORANGE, (round(p.sx), round(p.sy)), radius)
            pygame.draw.circle(
                self._canvas,
                pal.YELLOW,
                (round(p.sx), round(p.sy)),
                max(1, radius // 2),
            )
            return
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

    def _invader(self, world: World, index: int) -> None:
        invader = world.extras.invaders[index]
        pattern = (
            "00111100",
            "01111110",
            "11011011",
            "11111111",
            "10100101",
        )
        target = world.paddles[invader.target].rect
        facing = Vec2(target.cx - invader.pos.x, target.cy - invader.pos.y)
        distance = facing.length()
        if distance == 0.0:
            facing = Vec2(-1.0 if target.cx > invader.pos.x else 1.0, 0.0)
        else:
            facing = facing * (1.0 / distance)
        camera_forward = self.camera.unrotate(0.0, 1.0)
        facing = facing * 0.62 + Vec2(*camera_forward)
        facing_length = facing.length()
        if facing_length > 0.0:
            facing = facing * (1.0 / facing_length)
        horizontal = Vec2(-facing.y, facing.x)
        cell_w, cell_h, depth = 2.0, 1.55, 1.55
        center = invader.pos + facing * 1.8
        shadow = self.camera.project(invader.pos.x, invader.pos.y, 0.0)
        pygame.draw.ellipse(
            self._canvas,
            pal.shade(pal.NAVY, 0.55),
            (
                round(shadow.sx) - max(2, round(7 * shadow.scale)),
                round(shadow.sy) - max(1, round(2 * shadow.scale)),
                max(4, round(14 * shadow.scale)),
                max(2, round(4 * shadow.scale)),
            ),
        )

        def pixel_corners(column: int, row: int, back: float = 0.0) -> list[Corner]:
            offset = (column - 3.5) * cell_w
            z0 = 2.5 + (4 - row) * cell_h
            base = center + horizontal * offset - facing * back
            next_column = base + horizontal * cell_w * 0.82
            return [
                (base.x, base.y, z0),
                (next_column.x, next_column.y, z0),
                (next_column.x, next_column.y, z0 + cell_h * 0.82),
                (base.x, base.y, z0 + cell_h * 0.82),
            ]

        # Build dark extrusions first so every lit pixel reads as a solid voxel.
        for row, pixels in enumerate(pattern):
            for column, pixel in enumerate(pixels):
                if pixel != "1":
                    continue
                front = pixel_corners(column, row)
                rear = pixel_corners(column, row, depth)
                self._quad([front[0], front[1], rear[1], rear[0]], pal.shade(pal.GREEN, 0.5))
                self._quad([front[1], front[2], rear[2], rear[1]], pal.shade(pal.GREEN, 0.7))
                self._quad(rear, pal.shade(pal.GREEN, 0.38))
        for row, pixels in enumerate(pattern):
            for column, pixel in enumerate(pixels):
                if pixel != "1":
                    continue
                color = pal.WHITE if row == 2 and column in (2, 5) else pal.LIME
                self._quad(pixel_corners(column, row), color)

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

    def _draw_hud(self, world: World, view: Viewport) -> None:
        w, h = view.rect.size
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
                "match.score.winner",
                player=self.translator.translate("hud.player", number=world.winner + 1).upper(),
            )
        if message:
            text = message.upper()
            size = BIG_TEXT if world.countdown_number is not None else SMALL_TEXT
            x = (w - text_width(text, size)) // 2
            draw_text(self._canvas, text, x, message_y, pal.WHITE, size)
        clock: str | None = None
        if world.config.mode == "timed":
            duration = world.mode.values["duration_seconds"]
            remaining = max(0, duration * c.TICK_RATE - world.tick)
            seconds = (remaining + c.TICK_RATE - 1) // c.TICK_RATE
            clock = f"{seconds // 60:02d}:{seconds % 60:02d}"
        pickup_labels_top = self.hud.draw(
            self._canvas,
            world,
            self.camera,
            self.translator,
            self.colors,
            self.settings.hud_style if self.settings.hud_style in HUD_STYLES else "arcade",
            own_seat=view.seat,
        )
        if clock is not None:
            clock_y = (
                pickup_labels_top - GLYPH_H - HUD_MARGIN
                if pickup_labels_top is not None
                else h - GLYPH_H - HUD_MARGIN
            )
            draw_text(
                self._canvas,
                clock,
                (w - text_width(clock, SMALL_TEXT)) // 2,
                max(0, clock_y),
                pal.YELLOW,
                SMALL_TEXT,
            )
