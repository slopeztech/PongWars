"""@package pongwars.render.palette
@brief Fixed 16-colour 8-bit palette.
"""

Color = tuple[int, int, int]

BLACK: Color = (0, 0, 0)
NAVY: Color = (29, 43, 83)
PURPLE: Color = (126, 37, 83)
GREEN: Color = (0, 135, 81)
BROWN: Color = (171, 82, 54)
DARK_GREY: Color = (95, 87, 79)
LIGHT_GREY: Color = (194, 195, 199)
WHITE: Color = (255, 241, 232)
RED: Color = (255, 0, 77)
ORANGE: Color = (255, 163, 0)
YELLOW: Color = (255, 236, 39)
LIME: Color = (0, 228, 54)
BLUE: Color = (41, 173, 255)
LAVENDER: Color = (131, 118, 156)
PINK: Color = (255, 119, 168)
PEACH: Color = (255, 204, 170)
UI_BACKGROUND: Color = (5, 12, 30)
UI_CYAN: Color = (0, 190, 245)
UI_ORANGE: Color = (255, 163, 0)
UI_MUTED: Color = (54, 73, 123)
UI_DARK: Color = (20, 34, 69)

PLAYER_COLORS: tuple[Color, ...] = (BLUE, RED, LIME, YELLOW)
PADDLE_PALETTE: tuple[Color, ...] = (
    BLUE,
    RED,
    LIME,
    YELLOW,
    ORANGE,
    PINK,
    WHITE,
    LAVENDER,
    (0, 255, 255),
    (0, 160, 150),
    (108, 255, 190),
    (0, 100, 60),
    (100, 220, 255),
    (40, 90, 220),
    (75, 55, 170),
    (190, 120, 255),
    (255, 0, 190),
    (255, 110, 90),
    (190, 25, 55),
    (110, 30, 60),
    (255, 205, 60),
    (220, 180, 130),
    (160, 180, 195),
    (55, 65, 85),
)
THEMES: dict[str, tuple[Color, Color, Color]] = {
    "stone": (NAVY, DARK_GREY, LIGHT_GREY),
    "default": (NAVY, DARK_GREY, LIGHT_GREY),
}


def shade(color: Color, factor: float) -> Color:
    """@brief Scale a colour's brightness.
    @param color Source colour.
    @param factor Multiplier (below 1 darkens).
    @return The shaded colour, clamped to 0..255.
    """
    r, g, b = color
    return (
        max(0, min(255, int(r * factor))),
        max(0, min(255, int(g * factor))),
        max(0, min(255, int(b * factor))),
    )
