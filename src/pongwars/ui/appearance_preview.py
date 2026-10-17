"""Small, screen-space icons for arena field styles in the appearance menu."""

import math

import pygame

from pongwars.render import palette as pal


def draw_field_style_icon(surface: pygame.Surface, rect: pygame.Rect, style: str) -> None:
    """Draw a recognizable, compact icon for one arena field style."""
    previous_clip = surface.get_clip()
    surface.set_clip(rect)
    surface.fill(pal.UI_BACKGROUND, rect)
    field = rect.inflate(-10, -8)
    left, top, width, height = field
    right, bottom = left + width, top + height
    center = (left + width // 2, top + height // 2)
    accent = pal.UI_CYAN
    dim = pal.shade(pal.BLUE, 0.45)
    pygame.draw.rect(surface, dim, field, 1)

    def point(x: float, y: float) -> tuple[int, int]:
        return round(left + x * width), round(top + y * height)

    def line(points: list[tuple[float, float]], color: pal.Color = accent) -> None:
        pygame.draw.lines(surface, color, False, [point(x, y) for x, y in points])

    try:
        if style == "grid":
            for step in range(1, 5):
                x, y = step / 5, step / 5
                line([(x, 0), (x, 1)], dim)
                line([(0, y), (1, y)], dim)
        elif style == "checker":
            for row in range(3):
                for column in range(4):
                    if (row + column) % 2 == 0:
                        pygame.draw.rect(
                            surface,
                            dim,
                            (
                                left + column * width // 4,
                                top + row * height // 3,
                                max(1, width // 4),
                                max(1, height // 3),
                            ),
                        )
        elif style == "neon":
            pygame.draw.rect(surface, accent, field.inflate(-2, -2), 1)
            line([(0.5, 0), (0.5, 1)], pal.PINK)
            pygame.draw.circle(surface, pal.WHITE, center, max(2, height // 8), 1)
        elif style == "solid":
            surface.fill(pal.shade(pal.BLUE, 0.32), field.inflate(-2, -2))
            pygame.draw.rect(surface, pal.LIGHT_GREY, field.inflate(-2, -2), 1)
        elif style == "dots":
            for row in range(4):
                for column in range(5):
                    pygame.draw.circle(
                        surface,
                        accent,
                        point((column + 0.5) / 5, (row + 0.5) / 4),
                        1,
                    )
        elif style == "diagonal":
            for offset in range(-2, 7, 2):
                line([(offset / 5, 0), ((offset + 3) / 5, 1)])
        elif style == "crosshatch":
            for offset in range(-2, 7, 2):
                line([(offset / 5, 0), ((offset + 3) / 5, 1)], pal.LAVENDER)
                line([(offset / 5, 1), ((offset + 3) / 5, 0)], pal.LAVENDER)
        elif style in ("rings", "target"):
            for index in range(1, 5):
                color = pal.PINK if style == "target" and index == 1 else accent
                pygame.draw.ellipse(
                    surface,
                    color,
                    (
                        left + width // 2 - index * width // 10,
                        top + height // 2 - index * height // 10,
                        index * width // 5,
                        index * height // 5,
                    ),
                    1,
                )
            if style == "target":
                pygame.draw.circle(surface, pal.YELLOW, center, 2)
                line([(0.5, 0), (0.5, 1)], pal.PINK)
                line([(0, 0.5), (1, 0.5)], pal.PINK)
        elif style == "stripes":
            for step in range(1, 6, 2):
                x = step / 6
                pygame.draw.rect(
                    surface, dim, (round(left + x * width), top, max(1, width // 9), height)
                )
        elif style == "waves":
            for band in range(3):
                line(
                    [
                        (step / 24, 0.2 + band * 0.3 + math.sin(step * math.tau / 12) * 0.08)
                        for step in range(25)
                    ],
                    (pal.UI_CYAN, pal.BLUE, pal.PINK)[band],
                )
        elif style == "diamonds":
            for x in (0.25, 0.75):
                for y in (0.33, 0.67):
                    line(
                        [
                            (x, y - 0.22),
                            (x + 0.2, y),
                            (x, y + 0.22),
                            (x - 0.2, y),
                            (x, y - 0.22),
                        ]
                    )
        elif style == "circuit":
            for x, y in ((0.2, 0.25), (0.7, 0.3), (0.38, 0.72), (0.82, 0.75)):
                line([(x - 0.12, y), (x, y), (x, y + 0.16), (x + 0.12, y + 0.16)])
                pygame.draw.circle(surface, pal.YELLOW, point(x + 0.12, y + 0.16), 2)
        elif style == "boxes":
            for inset in (0.12, 0.3):
                pygame.draw.rect(
                    surface,
                    accent if inset == 0.12 else pal.PINK,
                    (
                        round(left + width * inset),
                        round(top + height * inset),
                        round(width * (1 - 2 * inset)),
                        round(height * (1 - 2 * inset)),
                    ),
                    1,
                )
        elif style == "radial":
            for angle in range(0, 360, 30):
                radians = math.radians(angle)
                line(
                    [
                        (0.5, 0.5),
                        (0.5 + math.cos(radians) * 0.48, 0.5 + math.sin(radians) * 0.48),
                    ]
                )
            pygame.draw.circle(surface, pal.PINK, center, 2)
        elif style == "stars":
            stars = ((0.25, 0.35, 4), (0.68, 0.3, 3), (0.48, 0.72, 5), (0.83, 0.72, 2))
            for x, y, radius in stars:
                cx, cy = point(x, y)
                vertices = [
                    (
                        cx
                        + round(
                            math.cos(step * math.pi / 5 - math.pi / 2)
                            * (radius if step % 2 == 0 else radius // 2)
                        ),
                        cy
                        + round(
                            math.sin(step * math.pi / 5 - math.pi / 2)
                            * (radius if step % 2 == 0 else radius // 2)
                        ),
                    )
                    for step in range(10)
                ]
                pygame.draw.polygon(surface, pal.YELLOW, vertices)
        elif style == "lanes":
            for lane in range(1, 4):
                x = round(left + lane * width / 4)
                pygame.draw.line(
                    surface, accent, (x, top + 2), (x, bottom - 2), 2 if lane == 2 else 1
                )
            pygame.draw.circle(surface, pal.WHITE, center, 2)
        elif style == "scanlines":
            for y in range(2, height, 4):
                pygame.draw.line(surface, pal.LAVENDER, (left + 2, top + y), (right - 2, top + y))
        elif style == "maze":
            maze = (
                ((0.1, 0.1), (0.45, 0.1), (0.45, 0.45), (0.2, 0.45), (0.2, 0.8)),
                ((0.9, 0.1), (0.65, 0.1), (0.65, 0.6), (0.4, 0.6), (0.4, 0.9)),
                ((0.9, 0.8), (0.7, 0.8), (0.7, 0.4), (0.9, 0.4)),
            )
            for path in maze:
                line(list(path), pal.LAVENDER)
        elif style == "sparkle":
            for x, y in ((0.25, 0.3), (0.72, 0.28), (0.48, 0.7), (0.82, 0.74)):
                cx, cy = point(x, y)
                pygame.draw.line(surface, pal.WHITE, (cx - 4, cy), (cx + 4, cy), 1)
                pygame.draw.line(surface, pal.WHITE, (cx, cy - 4), (cx, cy + 4), 1)
                pygame.draw.circle(surface, pal.YELLOW, (cx, cy), 1)
    finally:
        surface.set_clip(previous_clip)
