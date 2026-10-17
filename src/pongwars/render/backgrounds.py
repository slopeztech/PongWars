"""@package pongwars.render.backgrounds
@brief Animated screen-space arena backgrounds drawn behind the table.
"""

import math
import random
from collections.abc import Callable

import pygame

from pongwars.render import palette as pal

STAR_COUNT = 70
RAIN_COUNT = 50
RAIN_LENGTH = 4
WAVE_BANDS = 5
AURORA_BANDS = 3
BACKGROUND_GRADIENT_STEPS = 24
AMBIENT_COLORS = (pal.BLUE, pal.PINK, pal.UI_CYAN, pal.LAVENDER, pal.LIME, pal.ORANGE)
Painter = Callable[[pygame.Surface, int, random.Random], None]


def _none(_surface: pygame.Surface, _tick: int, _rng: random.Random) -> None:
    return


def _stars(surface: pygame.Surface, tick: int, rng: random.Random) -> None:
    w, h = surface.get_size()
    for _ in range(STAR_COUNT):
        x, y = rng.randrange(w), rng.randrange(h)
        speed = 1 + rng.randrange(3)
        twinkle = rng.randrange(40)
        sx = (x - tick * speed // 8) % w
        color = pal.WHITE if (tick // 10 + twinkle) % 5 else pal.LAVENDER
        surface.fill(color if speed > 1 else pal.DARK_GREY, (sx, y, 1, 1))


def _rain(surface: pygame.Surface, tick: int, rng: random.Random) -> None:
    w, h = surface.get_size()
    for _ in range(RAIN_COUNT):
        x, y0 = rng.randrange(w), rng.randrange(h)
        speed = 2 + rng.randrange(3)
        y = (y0 + tick * speed) % h
        pygame.draw.line(surface, pal.BLUE, (x, y), (x, y + RAIN_LENGTH))


def _waves(surface: pygame.Surface, tick: int, _rng: random.Random) -> None:
    w, h = surface.get_size()
    for band in range(WAVE_BANDS):
        base = h * (band + 1) // (WAVE_BANDS + 1)
        color = pal.shade(pal.BLUE, 0.3 + 0.1 * band)
        for x in range(0, w, 2):
            y = base + round(3 * math.sin((x + tick * (1 + band)) / 12.0 + band))
            surface.fill(color, (x, y, 2, 1))


def _aurora(surface: pygame.Surface, tick: int, _rng: random.Random) -> None:
    w, h = surface.get_size()
    colors = (pal.LIME, pal.PINK, pal.BLUE)
    for band in range(AURORA_BANDS):
        color = pal.shade(colors[band], 0.45)
        for x in range(0, w, 2):
            phase = (x - tick * 0.7) / 25.0 + band * 2
            y = round(h * (band + 0.5) / AURORA_BANDS + math.sin(phase) * h * 0.12)
            curtain_height = max(8, h // 3)
            pygame.draw.line(surface, color, (x, y), (x, y + curtain_height))


def _fill_ambient_gradient(surface: pygame.Surface) -> None:
    width, height = surface.get_size()
    top = pal.UI_BACKGROUND
    bottom = pal.shade(pal.NAVY, 0.32)
    for step in range(BACKGROUND_GRADIENT_STEPS):
        fraction = step / (BACKGROUND_GRADIENT_STEPS - 1)
        color = tuple(
            round(first + (last - first) * fraction)
            for first, last in zip(top, bottom, strict=True)
        )
        y0 = step * height // BACKGROUND_GRADIENT_STEPS
        y1 = (step + 1) * height // BACKGROUND_GRADIENT_STEPS
        pygame.draw.rect(surface, color, (0, y0, width, y1 - y0))


def _generated(pattern: str) -> Painter:
    def paint(surface: pygame.Surface, tick: int, rng: random.Random) -> None:
        w, h = surface.get_size()
        if pattern in ("nebula", "plasma", "rainbow"):
            for band, color in enumerate(AMBIENT_COLORS):
                phase = tick * 0.025 + band * 1.1
                for x in range(0, w, 3):
                    wave = math.sin(x / (12.0 + band * 2) + phase)
                    if pattern == "nebula":
                        y = h // 2 + round(wave * (12 + band * 3))
                        surface.fill(pal.shade(color, 0.25 + band * 0.06), (x, y, 3, 7))
                    elif pattern == "plasma":
                        y = h // 2 + round(wave * (8 + band * 2))
                        pygame.draw.line(surface, pal.shade(color, 0.38), (x, y), (x + 2, y + 3))
                    else:
                        y = band * h // len(AMBIENT_COLORS)
                        pygame.draw.line(
                            surface, pal.shade(color, 0.3), (0, y + round(wave * 3)), (w, y + 3)
                        )
            return

        if pattern in ("comets", "meteor", "embers"):
            count = 20 if pattern == "embers" else 12
            for _ in range(count):
                x0, y0 = rng.randrange(w), rng.randrange(h)
                speed = 1 + rng.randrange(4)
                if pattern == "comets":
                    x = (x0 - tick * speed) % w
                    pygame.draw.line(surface, pal.UI_CYAN, (x, y0), (x + speed * 4, y0 - 2))
                elif pattern == "meteor":
                    x = (x0 - tick * speed) % w
                    y = (y0 + tick * speed // 2) % h
                    pygame.draw.line(surface, pal.PINK, (x, y), (x + 5, y - 3))
                else:
                    y = (y0 - tick * speed) % h
                    surface.fill(pal.ORANGE if speed > 2 else pal.RED, (x0, y, 2, 2))
            return

        if pattern in ("bubbles", "snow", "fireflies", "confetti", "starscape"):
            count = 45 if pattern in ("snow", "starscape") else 28
            for _ in range(count):
                x0, y0 = rng.randrange(w), rng.randrange(h)
                speed = 1 + rng.randrange(3)
                x = (x0 + (tick // 5 * speed if pattern == "confetti" else 0)) % w
                y = (y0 + tick * speed // 4) % h if pattern in ("snow", "confetti") else y0
                radius = 1 + rng.randrange(3)
                color = AMBIENT_COLORS[rng.randrange(len(AMBIENT_COLORS))]
                if pattern == "bubbles":
                    y = (y0 - tick * speed // 5) % h
                    pygame.draw.circle(surface, pal.shade(pal.BLUE, 0.55), (x, y), radius, 1)
                elif pattern == "snow":
                    surface.fill(pal.WHITE, (x, y, 1 + (speed == 3), 1 + (speed == 3)))
                elif pattern == "fireflies":
                    if (tick // 8 + x0 + y0) % 3 == 0:
                        pygame.draw.circle(surface, pal.LIME, (x, y), radius)
                elif pattern == "confetti":
                    pygame.draw.rect(surface, color, (x, y, radius + 1, radius))
                else:
                    pygame.draw.circle(surface, color, (x, y), 1 if speed == 1 else 2)
            return

        if pattern == "matrix":
            for column in range(24):
                x = column * (w // 24)
                head = (column * 17 + tick * (1 + column % 3)) % h
                for length in range(5):
                    y = (head - length * 5) % h
                    surface.fill(pal.shade(pal.LIME, 1.0 - length * 0.15), (x, y, 1, 3))
            return

        if pattern == "circuit":
            step = 24
            offset = tick // 6 % step
            for x in range(-step, w + step, step):
                y = (x // step * 13 + offset * 2) % h
                pygame.draw.line(surface, pal.shade(pal.UI_CYAN, 0.5), (x, y), (x + 10, y))
                pygame.draw.line(surface, pal.shade(pal.UI_CYAN, 0.5), (x + 10, y), (x + 10, y + 8))
                pygame.draw.circle(surface, pal.UI_CYAN, (x + 10, y + 8), 1)
            return

        if pattern == "spiral":
            for center_x, center_y in ((w // 3, h // 2), (2 * w // 3, h // 2)):
                for arm in range(3):
                    points = []
                    for radius in range(2, 42, 2):
                        angle = radius * 0.12 + tick * 0.025 + arm * math.tau / 3
                        points.append(
                            (
                                center_x + round(math.cos(angle) * radius),
                                center_y + round(math.sin(angle) * radius * 0.6),
                            )
                        )
                    if len(points) > 1:
                        pygame.draw.lines(surface, pal.PINK, False, points, 1)
            return

        if pattern == "gears":
            for cx, cy, radius in ((w // 4, h // 2, 18), (3 * w // 4, h // 2, 24)):
                pygame.draw.circle(surface, pal.LAVENDER, (cx, cy), radius, 1)
                for spoke in range(8):
                    angle = tick * 0.02 + spoke * math.tau / 8
                    end = (
                        cx + round(math.cos(angle) * radius),
                        cy + round(math.sin(angle) * radius),
                    )
                    pygame.draw.line(surface, pal.LAVENDER, (cx, cy), end)
            return

        if pattern == "pulse":
            for radius in range(8, max(w, h), 16):
                phase = (tick // 3 + radius) % 3
                color = AMBIENT_COLORS[phase]
                pygame.draw.ellipse(
                    surface,
                    pal.shade(color, 0.35),
                    (w // 2 - radius, h // 2 - radius // 2, radius * 2, radius),
                    1,
                )

    return paint


PAINTERS: dict[str, Painter] = {
    "none": _none,
    "grid": _none,
    "stars": _stars,
    "rain": _rain,
    "waves": _waves,
    "aurora": _aurora,
    "nebula": _generated("nebula"),
    "comets": _generated("comets"),
    "bubbles": _generated("bubbles"),
    "snow": _generated("snow"),
    "fireflies": _generated("fireflies"),
    "matrix": _generated("matrix"),
    "circuit": _generated("circuit"),
    "embers": _generated("embers"),
    "meteor": _generated("meteor"),
    "spiral": _generated("spiral"),
    "confetti": _generated("confetti"),
    "starscape": _generated("starscape"),
    "plasma": _generated("plasma"),
    "rainbow": _generated("rainbow"),
    "gears": _generated("gears"),
    "pulse": _generated("pulse"),
}


def draw_background(surface: pygame.Surface, name: str, tick: int, seed: int = 0) -> None:
    """@brief Paint an animated background.
    @param surface Target surface (already cleared).
    @param name Background name (unknown names draw nothing).
    @param tick Animation clock in frames.
    @param seed Seed of the deterministic layout.
    """
    if name not in ("none", "grid"):
        _fill_ambient_gradient(surface)
    PAINTERS.get(name, _none)(surface, tick, random.Random(seed))  # noqa: S311 - visual only
