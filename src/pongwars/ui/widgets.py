"""@package pongwars.ui.widgets
@brief Keyboard-driven menu widget drawn with the bitmap font.
"""

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from pongwars.render import palette as pal
from pongwars.render.font import GLYPH_H, draw_text, text_width

ROW_GAP = 11
SELECT_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
MUSIC_NOTICE_SECONDS = 5.0
MUSIC_NOTICE_FADE_SECONDS = 0.3


class MusicNotice:
    """@brief Brief pixel-art notice shown when a new song starts."""

    def __init__(self) -> None:
        """@brief Start with no active song notification."""
        self._song_key: tuple[str, str] | None = None
        self._remaining = 0.0
        self._title = ""
        self._artist = ""

    @property
    def visible(self) -> bool:
        """@brief Whether the notice has time remaining."""
        return self._remaining > 0.0

    def update(
        self,
        song_key: tuple[str, str] | None,
        song: tuple[str, str] | None,
        dt: float,
    ) -> None:
        """@brief Track song transitions and count down the five-second notice.
        @param song_key Playlist context and song id, or None during silence.
        @param song Song title and artist, or None when unavailable.
        @param dt Seconds elapsed.
        """
        self._remaining = max(0.0, self._remaining - dt)
        if song_key == self._song_key:
            return
        self._song_key = song_key
        if song_key is not None and song is not None:
            self._title, self._artist = song
            self._remaining = MUSIC_NOTICE_SECONDS

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Draw the fading song card anchored to the lower-right corner."""
        if not self.visible:
            return
        elapsed = MUSIC_NOTICE_SECONDS - self._remaining
        fade = min(
            1.0,
            elapsed / MUSIC_NOTICE_FADE_SECONDS,
            self._remaining / MUSIC_NOTICE_FADE_SECONDS,
        )
        alpha = max(0, min(255, round(255 * fade)))
        if alpha == 0:
            return

        width, height = 112, 24
        x, y = surface.get_width() - width - 6, surface.get_height() - height - 23
        card = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(card, pal.UI_BACKGROUND, (0, 0, width, height))
        pygame.draw.rect(card, pal.UI_CYAN, (0, 0, width, height), 1)
        pygame.draw.rect(card, pal.UI_DARK, (2, 2, width - 4, height - 4), 1)

        icon_x, icon_y = 5, 5
        pygame.draw.rect(card, pal.UI_CYAN, (icon_x + 5, icon_y, 2, 10))
        pygame.draw.rect(card, pal.UI_CYAN, (icon_x + 5, icon_y, 6, 2))
        pygame.draw.rect(card, pal.UI_CYAN, (icon_x + 9, icon_y + 2, 2, 5))
        pygame.draw.ellipse(card, pal.UI_CYAN, (icon_x, icon_y + 7, 5, 4))
        pygame.draw.ellipse(card, pal.UI_CYAN, (icon_x + 5, icon_y + 8, 5, 4))

        text_x, text_width_limit = 21, width - 27
        title = _truncate(self._title, text_width_limit)
        artist = _truncate(self._artist, text_width_limit)
        draw_text(card, title, text_x, 5, pal.WHITE)
        draw_text(card, artist, text_x, 14, pal.LIGHT_GREY)
        card.set_alpha(alpha)
        surface.blit(card, (x, y))


def _truncate(text: str, width: int) -> str:
    """@brief Fit a label to a pixel width, keeping a visible ellipsis when shortened."""
    if text_width(text) <= width:
        return text
    shortened = text
    while shortened and text_width(shortened + ".") > width:
        shortened = shortened[:-1]
    return shortened + "." if shortened else ""


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

    def draw(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        width: int,
        *,
        centered: bool = False,
        row_gap: int = ROW_GAP,
    ) -> None:
        """@brief Draw all rows.
        @param surface Target surface.
        @param x Left pixel.
        @param y Top pixel of the first row.
        @param width Row width; values are right-aligned inside it.
        @param centered Center labels within a compact column.
        @param row_gap Vertical distance between rows.
        """
        for i, item in enumerate(self.items):
            top = y + i * row_gap
            selected = i == self.index
            color = pal.DARK_GREY if not item.enabled else pal.WHITE
            if selected:
                self._draw_selection(surface, x, top, width)
            label = item.label()
            label_x = (
                x + (width - text_width(label)) // 2
                if centered
                else x
            )
            draw_text(surface, label, label_x, top, color)
            if item.value is not None:
                text = item.value()
                draw_text(surface, text, x + width - text_width(text), top, color)

    @staticmethod
    def _draw_selection(surface: pygame.Surface, x: int, y: int, width: int) -> None:
        """@brief Draw the selected row as a cyan pixel-frame with clipped corners."""
        left, top = x - 6, y - 3
        right, bottom = x + width + 5, y + GLYPH_H + 2
        pygame.draw.line(surface, pal.UI_CYAN, (left + 3, top), (right - 3, top))
        pygame.draw.line(surface, pal.UI_CYAN, (left + 3, bottom), (right - 3, bottom))
        pygame.draw.line(surface, pal.UI_CYAN, (left, top + 3), (left, bottom - 3))
        pygame.draw.line(surface, pal.UI_CYAN, (right, top + 3), (right, bottom - 3))
        for dx, dy in ((1, 1), (2, 2)):
            surface.set_at((left + dx, top + dy), pal.UI_CYAN)
            surface.set_at((right - dx, top + dy), pal.UI_CYAN)
            surface.set_at((left + dx, bottom - dy), pal.UI_CYAN)
            surface.set_at((right - dx, bottom - dy), pal.UI_CYAN)
