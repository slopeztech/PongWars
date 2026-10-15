"""@package pongwars.ui.widgets
@brief Keyboard-driven menu widget drawn with the bitmap font.
"""

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from pongwars.render import palette as pal
from pongwars.render.font import GLYPH_H, draw_text, text_width

ROW_GAP = 11
CURSOR = ">"
SELECT_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)


@dataclass
class MenuItem:
    """@brief One menu row.

    @param label Returns the (translated) label.
    @param value Returns the current value text, if the row has one.
    @param on_activate Called on Enter/Space.
    @param on_adjust Called with -1 / +1 on Left / Right (Enter also adjusts +1 if no activate).
    @param enabled Disabled rows are skipped by the cursor and drawn dimmed.
    """

    label: Callable[[], str]
    value: Callable[[], str] | None = None
    on_activate: Callable[[], None] | None = None
    on_adjust: Callable[[int], None] | None = None
    enabled: bool = True


class Menu:
    """@brief A vertical list of rows with a cursor."""

    def __init__(self, items: list[MenuItem] | None = None) -> None:
        """@brief Create a menu.
        @param items Initial rows.
        """
        self.items: list[MenuItem] = []
        self.index = 0
        self.set_items(items or [])

    def set_items(self, items: list[MenuItem]) -> None:
        """@brief Replace the rows, keeping the cursor on a valid enabled row.
        @param items New rows.
        """
        self.items = items
        self.index = min(self.index, max(0, len(items) - 1))
        self._skip(1)

    def _skip(self, step: int) -> None:
        for _ in range(len(self.items)):
            if self.items[self.index].enabled:
                return
            self.index = (self.index + step) % len(self.items)

    def move(self, step: int) -> None:
        """@brief Move the cursor, wrapping and skipping disabled rows.
        @param step +1 for down, -1 for up.
        """
        if not self.items:
            return
        self.index = (self.index + step) % len(self.items)
        self._skip(step)

    def handle_key(self, key: int) -> bool:
        """@brief React to a key press.
        @param key pygame key code.
        @return True if the key was consumed.
        """
        if not self.items:
            return False
        item = self.items[self.index]
        if key == pygame.K_UP:
            self.move(-1)
        elif key == pygame.K_DOWN:
            self.move(1)
        elif key in (pygame.K_LEFT, pygame.K_RIGHT) and item.on_adjust and item.enabled:
            item.on_adjust(-1 if key == pygame.K_LEFT else 1)
        elif key in SELECT_KEYS and item.enabled:
            if item.on_activate:
                item.on_activate()
            elif item.on_adjust:
                item.on_adjust(1)
        else:
            return False
        return True

    def draw(self, surface: pygame.Surface, x: int, y: int, width: int) -> None:
        """@brief Draw all rows.
        @param surface Target surface.
        @param x Left pixel.
        @param y Top pixel of the first row.
        @param width Row width; values are right-aligned inside it.
        """
        for i, item in enumerate(self.items):
            top = y + i * ROW_GAP
            selected = i == self.index
            color = pal.DARK_GREY if not item.enabled else pal.YELLOW if selected else pal.WHITE
            if selected:
                draw_text(surface, CURSOR, x - 2 * (GLYPH_H - 1), top, color)
            draw_text(surface, item.label(), x, top, color)
            if item.value is not None:
                text = item.value()
                draw_text(surface, text, x + width - text_width(text), top, color)
