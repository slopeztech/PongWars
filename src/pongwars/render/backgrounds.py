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
            y = h // 4 + band * 6 + round(8 * math.sin((x - tick * 0.7) / 25.0 + band * 2))
            pygame.draw.line(surface, color, (x, y), (x, y + 10))


PAINTERS: dict[str, Painter] = {
    "none": _none,
    "grid": _none,
    "stars": _stars,
    "rain": _rain,
    "waves": _waves,
    "aurora": _aurora,
}


def draw_background(surface: pygame.Surface, name: str, tick: int, seed: int = 0) -> None:
    """@brief Paint an animated background.
    @param surface Target surface (already cleared).
    @param name Background name (unknown names draw nothing).
    @param tick Animation clock in frames.
    @param seed Seed of the deterministic layout.
    """
    PAINTERS.get(name, _none)(surface, tick, random.Random(seed))  # noqa: S311 - visual only
