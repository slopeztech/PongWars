"""@package pongwars.render.renderer
@brief Draws a read-only `World` as an 8-bit pseudo-3D scene on a low-resolution surface.
"""

import random
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

import pygame

from pongwars.core.i18n import Translator
from pongwars.domain import constants as c
from pongwars.domain.entities import Rect
from pongwars.domain.events import (
    BumperHit,
    Event,
    Goal,
    LaserFired,
    PaddleHit,
    PickupCollected,
    WallHit,
)
from pongwars.domain.world import SEAT_LEFT, SEAT_RIGHT, SEAT_TOP, Phase, World
from pongwars.render import palette as pal
from pongwars.render.camera import DEFAULT_BACK, DEFAULT_FOCAL, DEFAULT_HEIGHT, Camera
from pongwars.render.effects import ParticleSystem, Shake, Trail
from pongwars.render.font import draw_text, text_width

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
PICKUP_BLINK_TICKS = 120
PICKUP_BLINK_PERIOD = 6
SHIELD_GAP = 1.5
LASER_FRAMES = 6
BLIND_NOISE_DOTS = 400
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
        self._noise = random.Random(seed)  # noqa: S311 - visual only
        self._lasers: list[tuple[Point, Point, pal.Color, int]] = []

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
                        pal.PLAYER_COLORS[event.player],
                        LASER_FRAMES,
                    )
                )
                self._burst(event.x, event.y, pal.ORANGE, 6)
            elif isinstance(event, PickupCollected):
                self._burst(pos.x, pos.y, pal.LIME, 10)
            elif isinstance(event, PaddleHit):
                color = pal.PLAYER_COLORS[event.player]
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
        self._lasers = [(a, b, col, n - 1) for a, b, col, n in self._lasers if n > 1]
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
        return Camera(
            w,
            h,
            back=DEFAULT_BACK + extent,
            height=DEFAULT_HEIGHT + extent,
            focal=DEFAULT_FOCAL * w / LOW_W * (ODD_TURN_ZOOM if view.turns % 2 else 1.0),
            quarter_turns=view.turns,
        )

    def _draw_scene(self, world: World) -> None:
        self._draw_table(world)
        items: list[tuple[float, str, int]] = []
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
        for _, kind, index in sorted(items):
            if kind == "obstacle":
                obstacle = world.obstacles[index]
                self._box(
                    obstacle.rect, OBSTACLE_HEIGHT, KIND_COLORS.get(obstacle.kind, pal.LAVENDER)
                )
            elif kind == "paddle":
                self._box(world.paddles[index].rect, PADDLE_HEIGHT, pal.PLAYER_COLORS[index])
            elif kind == "pickup":
                self._pickup(world, index)
            else:
                self._ball(world, index)
        self._draw_shields(world)
        self._draw_lasers()
        self._draw_particles()

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
        p = self.camera.project(pickup.pos.x, pickup.pos.y, PICKUP_HEIGHT + 1.0)
        code = self.translator.translate(f"extras.{pickup.name}.short")
        draw_text(
            self._canvas,
            code,
            round(p.sx) - text_width(code, SMALL_TEXT) // 2,
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
                pal.PLAYER_COLORS[seat],
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
                pygame.draw.circle(
                    self._canvas,
                    pal.shade(pal.WHITE, 0.4 * shade + 0.2),
                    (round(p.sx), round(p.sy)),
                    radius,
                )
        ground = self.camera.project(ball.pos.x, ball.pos.y, 0.0)
        radius = max(1, round(ball.radius * ground.scale))
        shadow_rect = pygame.Rect(0, 0, radius * 2, max(1, radius))
        shadow_rect.center = (round(ground.sx), round(ground.sy))
        pygame.draw.ellipse(self._canvas, pal.shade(pal.NAVY, 0.4), shadow_rect)
        p = self.camera.project(ball.pos.x, ball.pos.y, BALL_LIFT)
        pygame.draw.circle(self._canvas, pal.WHITE, (round(p.sx), round(p.sy)), radius)

    def _draw_particles(self) -> None:
        for part in self.particles.particles:
            p = self.camera.project(part.x, part.y, part.z)
            self._canvas.fill(part.color, (round(p.sx), round(p.sy), 1, 1))

    def _seat_label(self, seat: int) -> str:
        return self.translator.translate("hud.player", number=seat + 1).upper()

    def _draw_hud(self, world: World, view: Viewport) -> None:
        w, h = view.rect.size
        if view.seat is None:
            self._draw_shared_scores(world, w)
        else:
            self._draw_split_scores(world, view.seat, w)
        message = None
        if world.phase is Phase.SERVING:
            message = self.translator.translate("hud.get_ready")
        elif world.phase is Phase.FINISHED and world.winner is not None:
            message = self.translator.translate(
                "match.score.winner", player=self._seat_label(world.winner)
            )
        if message:
            text = message.upper()
            x = (w - text_width(text, SMALL_TEXT)) // 2
            draw_text(self._canvas, text, x, h // 2, pal.WHITE, SMALL_TEXT)
        self._draw_effects(world, view)

    def _draw_effects(self, world: World, view: Viewport) -> None:
        w, h = view.rect.size
        seats = range(world.players) if view.seat is None else [view.seat]
        row = 0
        for seat in seats:
            parts = [
                f"{self.translator.translate(f'extras.{e.name}.short')} "
                f"{e.remaining // c.TICK_RATE + 1}"
                for e in world.extras.active[seat]
            ]
            weapon = world.extras.weapons[seat]
            if weapon is not None:
                code = self.translator.translate(f"extras.{weapon[0]}.short")
                parts.append(f"{code} X{weapon[1]}")
            if parts:
                draw_text(
                    self._canvas,
                    " ".join(parts).upper(),
                    HUD_MARGIN,
                    h - EFFECT_ROW * (row + 1),
                    pal.PLAYER_COLORS[seat],
                    SMALL_TEXT,
                )
                row += 1
            blind = any(e.name == "blind" for e in world.extras.active[seat])
            if blind and view.seat == seat:
                for _ in range(BLIND_NOISE_DOTS):
                    dot = (self._noise.randrange(w), self._noise.randrange(h))
                    self._canvas.set_at(dot, pal.WHITE)

    def _draw_shared_scores(self, world: World, w: int) -> None:
        mid = w // 2
        slots = [
            HUD_MARGIN,
            w - HUD_MARGIN,
            mid - SHARED_SLOT_OFFSET,
            mid + SHARED_SLOT_OFFSET,
        ]
        if world.players == SPLIT_COLUMNS:
            slots = [mid - SHARED_DUEL_OFFSET, mid + SHARED_DUEL_OFFSET]
        for seat, score in enumerate(world.scores):
            x = slots[seat]
            color = pal.PLAYER_COLORS[seat] if world.alive[seat] else pal.DARK_GREY
            label, value = self._seat_label(seat), str(score)
            width = max(text_width(value, BIG_TEXT), text_width(label, SMALL_TEXT))
            if world.players > SPLIT_COLUMNS and seat == 1:
                x -= width
            elif world.players == SPLIT_COLUMNS:
                x -= width // 2
            draw_text(self._canvas, label, x, HUD_TOP, color, SMALL_TEXT)
            draw_text(self._canvas, value, x, HUD_TOP + LABEL_GAP, color, BIG_TEXT)

    def _draw_split_scores(self, world: World, own: int, w: int) -> None:
        x = HUD_MARGIN
        for seat in sorted(range(world.players), key=lambda s: s != own):
            color = pal.PLAYER_COLORS[seat] if world.alive[seat] else pal.DARK_GREY
            text = f"{self._seat_label(seat)} {world.scores[seat]}"
            size = BIG_TEXT if seat == own else SMALL_TEXT
            if x + text_width(text, size) > w:
                break
            draw_text(self._canvas, text, x, HUD_TOP, color, size)
            x += text_width(text, size) + HUD_MARGIN
