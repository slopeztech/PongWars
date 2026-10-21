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
STADIUM_ROWS = 12
SPECTATOR_COLORS = (
    pal.BLUE,
    pal.PINK,
    pal.UI_CYAN,
    pal.LAVENDER,
    pal.LIME,
    pal.ORANGE,
    pal.RED,
    pal.WHITE,
)
SPECTATOR_HAIR_COLORS = (pal.NAVY, pal.BROWN, pal.DARK_GREY, pal.PURPLE)
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


def _stadium(surface: pygame.Surface, tick: int, rng: random.Random) -> None:
    width, height = surface.get_size()
    top_margin = max(2, round(height * 0.05))
    side_margin = max(2, round(width * 0.035))
    for row in range(STADIUM_ROWS):
        if row == STADIUM_ROWS - 2:
            continue
        depth = (row + 1) / STADIUM_ROWS
        scale = 0.35 + depth * 0.9
        if row == STADIUM_ROWS - 1:
            scale *= 1.15
        person_height = max(3, round(13 * scale))
        person_width = max(2, round(7 * scale))
        spacing = max(person_width + 1, round(person_width * 1.15))
        if row == STADIUM_ROWS - 1:
            head_radius = max(1, round(scale * 2))
            max_jump = round(scale * 2)
            center_y = height - person_height // 2 - head_radius - max_jump - 2
        else:
            row_progress = row / max(1, STADIUM_ROWS - 1)
            bottom_row_y = height - round(height * 0.06)
            center_y = round(top_margin + (bottom_row_y - top_margin) * row_progress**1.4)
        x = side_margin + rng.randrange(max(1, spacing))

        while x + person_width < width - side_margin:
            phase = rng.randrange(360)
            model = rng.randrange(4)
            color = pal.shade(SPECTATOR_COLORS[rng.randrange(len(SPECTATOR_COLORS))], 0.42)
            energy = (math.sin((tick + phase) * 0.11) + 1) * 0.5
            jump = round(energy * scale * 2) if model == 2 else 0
            head_radius = max(1, round(scale * 2))
            head_x = x + person_width // 2
            head_y = center_y - person_height // 2 - jump
            shoulder_y = head_y + head_radius
            feet_y = center_y + person_height // 2 - jump
            waving_flag = rng.randrange(18) == 0
            flag_side = -1 if rng.randrange(2) else 1
            bounds = pygame.Rect(
                x - head_radius,
                head_y - head_radius,
                person_width + head_radius * 2,
                person_height + head_radius * 2,
            )
            if (
                bounds.left < side_margin
                or bounds.right > width - side_margin
                or bounds.top < 1
                or bounds.bottom > height - 1
            ) and row != STADIUM_ROWS - 1:
                x += spacing
                continue

            pygame.draw.circle(surface, pal.shade(pal.PEACH, 0.62), (head_x, head_y), head_radius)
            hair_color = SPECTATOR_HAIR_COLORS[rng.randrange(len(SPECTATOR_HAIR_COLORS))]
            hairstyle = rng.randrange(5)
            hair_top = head_y - head_radius
            if hairstyle == 0:
                pygame.draw.ellipse(
                    surface,
                    hair_color,
                    (head_x - head_radius, hair_top, head_radius * 2 + 1, max(1, head_radius)),
                )
            elif hairstyle == 1:
                pygame.draw.polygon(
                    surface,
                    hair_color,
                    (
                        (head_x - head_radius, head_y),
                        (head_x - head_radius, hair_top + 1),
                        (head_x, hair_top - max(1, round(scale))),
                        (head_x + head_radius, hair_top + 1),
                        (head_x + head_radius, head_y),
                    ),
                )
            elif hairstyle == 2:
                pygame.draw.rect(
                    surface,
                    hair_color,
                    (head_x - head_radius - 1, head_y, 1, head_radius + 1),
                )
                pygame.draw.rect(
                    surface,
                    hair_color,
                    (head_x + head_radius, head_y, 1, head_radius + 1),
                )
            elif hairstyle == 3:
                pygame.draw.rect(
                    surface,
                    hair_color,
                    (head_x - head_radius, hair_top, head_radius * 2 + 1, 1),
                )
                pygame.draw.line(
                    surface,
                    pal.shade(hair_color, 1.4),
                    (head_x, hair_top),
                    (head_x + head_radius, hair_top + 1),
                )
            pygame.draw.rect(
                surface,
                color,
                (x, shoulder_y, person_width, max(1, feet_y - shoulder_y)),
            )

            arm_swing = round(energy * scale * 4)
            if waving_flag:
                pole_x = x - head_radius if flag_side < 0 else x + person_width + head_radius
                pole_top = head_y - max(2, round(scale * 7))
                pole_bottom = shoulder_y + max(1, round(scale * 2))
                flag_color_index = rng.randrange(len(pal.PADDLE_PALETTE))
                flag_color = pal.PADDLE_PALETTE[flag_color_index]
                second_flag_color = pal.PADDLE_PALETTE[
                    (flag_color_index + 1 + rng.randrange(len(pal.PADDLE_PALETTE) - 1))
                    % len(pal.PADDLE_PALETTE)
                ]
                flutter = round(math.sin((tick + phase) * 0.16) * max(1, round(scale)))
                flag_width = max(3, round(scale * 5))
                flag_height = max(2, round(scale * 3))
                flag = pygame.Rect(
                    min(pole_x, pole_x + flag_side * flag_width),
                    pole_top - 1,
                    flag_width + 1,
                    flag_height + abs(flutter) + 2,
                )
                if (
                    flag.left >= side_margin
                    and flag.right <= width - side_margin
                    and not _stadium_near_arena(flag, width, height)
                ):
                    pygame.draw.line(
                        surface, pal.LIGHT_GREY, (pole_x, pole_bottom), (pole_x, pole_top), 1
                    )
                    pygame.draw.polygon(
                        surface,
                        flag_color,
                        (
                            (pole_x, pole_top),
                            (pole_x + flag_side * flag_width, pole_top + 1 + flutter),
                            (
                                pole_x + flag_side * (flag_width - 1),
                                pole_top + flag_height + flutter,
                            ),
                            (pole_x, pole_top + flag_height),
                        ),
                    )
                    stripe_y = pole_top + max(1, flag_height // 2)
                    stripe_outer_x = pole_x + flag_side * flag_width
                    stripe_outer_y = pole_top + 1 + flutter + max(1, flag_height // 2)
                    pygame.draw.polygon(
                        surface,
                        second_flag_color,
                        (
                            (pole_x, stripe_y),
                            (stripe_outer_x, stripe_outer_y),
                            (
                                pole_x + flag_side * (flag_width - 1),
                                pole_top + flag_height + flutter,
                            ),
                            (pole_x, pole_top + flag_height),
                        ),
                    )
                    raised_hand_y = pole_top + round(scale * 4)
                    pygame.draw.line(
                        surface,
                        color,
                        (x if flag_side < 0 else x + person_width, shoulder_y + 1),
                        (pole_x, raised_hand_y),
                        1,
                    )
            elif model == 0:
                pygame.draw.line(
                    surface, color, (x, shoulder_y + 1), (x - head_radius, head_y - arm_swing), 1
                )
                pygame.draw.line(
                    surface,
                    color,
                    (x + person_width, shoulder_y + 1),
                    (x + person_width + head_radius, head_y - arm_swing),
                    1,
                )
            elif model == 1:
                clap = round(energy * head_radius)
                pygame.draw.line(
                    surface,
                    color,
                    (x, shoulder_y + 1),
                    (head_x - clap, head_y + head_radius),
                    1,
                )
                pygame.draw.line(
                    surface,
                    color,
                    (x + person_width, shoulder_y + 1),
                    (head_x + clap, head_y + head_radius),
                    1,
                )
            elif model == 2:
                pygame.draw.line(
                    surface,
                    color,
                    (x, shoulder_y + 1),
                    (x - head_radius, head_y - head_radius),
                    1,
                )
                pygame.draw.line(
                    surface,
                    color,
                    (x + person_width, shoulder_y + 1),
                    (x + person_width + head_radius, head_y - head_radius),
                    1,
                )
            else:
                wave = round(math.sin((tick + phase) * 0.14) * head_radius)
                pygame.draw.line(
                    surface,
                    color,
                    (x + person_width, shoulder_y + 1),
                    (x + person_width + head_radius, head_y - head_radius + wave),
                    1,
                )
                pygame.draw.line(surface, color, (x, shoulder_y + 1), (x - head_radius, feet_y), 1)
            x += spacing


def _stadium_near_arena(bounds: pygame.Rect, width: int, height: int) -> bool:
    margin_x = max(2, round(width * 0.025))
    margin_y = max(2, round(height * 0.025))
    field_top = round(height * 0.28)
    field_bottom = round(height * 0.83)
    arena_top = field_top - margin_y
    arena_bottom = field_bottom + margin_y
    if bounds.bottom < arena_top or bounds.top > arena_bottom:
        return False

    for y in (max(bounds.top, arena_top), min(bounds.bottom, arena_bottom)):
        progress = max(0.0, min(1.0, (y - field_top) / max(1, field_bottom - field_top)))
        arena_left = width * (0.19 - 0.14 * progress) - margin_x
        arena_right = width * (0.81 + 0.14 * progress) + margin_x
        if bounds.right >= arena_left and bounds.left <= arena_right:
            return True
    return False


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
    "stadium": _stadium,
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
