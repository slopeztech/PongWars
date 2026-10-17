"""Modular score, active-extra, and on-field pickup HUD rendering."""

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import pygame

from pongwars.core.settings import HUD_STYLES
from pongwars.render import palette as pal
from pongwars.render.camera import Camera
from pongwars.render.extras_icons import PICKUP_ICONS
from pongwars.render.font import draw_text, text_width

if TYPE_CHECKING:
    from pongwars.core.i18n import Translator
    from pongwars.domain.world import World

__all__ = ["HUD_STYLES", "HudRenderer", "player_slot_layout"]

HudStyle = Literal["arcade", "minimal", "neon", "cabinet", "scoreboard", "pixel"]
HUD_ROW_HEIGHT = 7
HUD_ICON_SIZE = 5
HUD_PICKUP_GAP = 2
HUD_PICKUP_HEIGHT = 14
HUD_PICKUP_ICON = 5
HUD_PICKUP_TEXT_SCALE = 1
HUD_STYLE_COLORS: dict[str, tuple[pal.Color, pal.Color]] = {
    "arcade": (pal.UI_CYAN, pal.UI_BACKGROUND),
    "minimal": (pal.LIGHT_GREY, pal.UI_BACKGROUND),
    "neon": (pal.PINK, pal.UI_DARK),
    "cabinet": (pal.ORANGE, (24, 18, 30)),
    "scoreboard": (pal.LIME, (8, 24, 31)),
    "pixel": (pal.LAVENDER, (19, 16, 40)),
}
HUD_CATEGORY_COLORS = {
    "power": pal.LIME,
    "weapon": pal.ORANGE,
    "penalty": pal.RED,
    "status": pal.PINK,
}


def player_slot_layout(
    surface_size: tuple[int, int], players: int, own_seat: int | None = None
) -> list[tuple[int, pygame.Rect]]:
    """Return deterministic, non-overlapping HUD zones for every player."""
    width, height = surface_size
    columns = players if own_seat is None else min(2, players)
    rows = math.ceil(players / columns)
    slot_width = width // columns
    slot_height = min(29, max(HUD_ROW_HEIGHT * 2, (height - 4) // rows))
    seats = list(range(players))
    if own_seat is not None:
        seats.sort(key=lambda seat: seat != own_seat)
    slots = []
    for position, seat in enumerate(seats):
        row, column = divmod(position, columns)
        left = column * slot_width
        width_for_slot = width - left if column == columns - 1 else slot_width
        rect = pygame.Rect(
            left + 1,
            2 + row * slot_height,
            max(1, width_for_slot - 2),
            slot_height - 1,
        )
        slots.append((seat, rect))
    return slots


@dataclass(frozen=True)
class _HudExtra:
    name: str
    color: pal.Color
    remaining: int
    duration: int
    count: int = 0


class HudRenderer:
    """Draw player score cards and non-overlapping labels for field pickups."""

    def draw(
        self,
        surface: pygame.Surface,
        world: "World",
        camera: Camera,
        translator: "Translator",
        colors: list[pal.Color],
        style: str,
        *,
        own_seat: int | None,
    ) -> int | None:
        self._draw_players(surface, world, translator, colors, style, own_seat)
        return self._draw_pickup_labels(surface, world, camera, translator, style)

    def _draw_players(
        self,
        surface: pygame.Surface,
        world: "World",
        translator: "Translator",
        colors: list[pal.Color],
        style: str,
        own_seat: int | None,
    ) -> None:
        selected_style = style if style in HUD_STYLE_COLORS else "arcade"
        accent, background = HUD_STYLE_COLORS[selected_style]
        for seat, rect in player_slot_layout(surface.get_size(), world.players, own_seat):
            color = colors[seat] if world.alive[seat] else pal.DARK_GREY
            self._draw_panel(surface, rect, color, accent, background, selected_style)

            label = translator.translate("hud.player", number=seat + 1).upper()
            score = str(world.scores[seat])
            header = f"{label} {score}"
            header_scale = 2 if rect.width >= 100 else 1
            header_x = rect.x + 3
            header_y = rect.y + 2
            header_width = text_width(header, header_scale)
            header_height = 5 * header_scale
            pygame.draw.rect(
                surface,
                pal.UI_BACKGROUND,
                (header_x - 1, header_y - 1, header_width + 3, header_height + 2),
            )
            self._draw_readable_text(surface, header, header_x, header_y, header_scale)
            extras = self._extras_for(world, seat)
            self._draw_extra_icons(
                surface, rect, extras, color, selected_style, translator, header_scale
            )

    @staticmethod
    def _draw_panel(
        surface: pygame.Surface,
        rect: pygame.Rect,
        player_color: pal.Color,
        accent: pal.Color,
        background: pal.Color,
        style: str,
    ) -> None:
        if style == "minimal":
            return
        pygame.draw.rect(surface, background, rect)
        border = pal.shade(player_color, 0.62) if style == "arcade" else accent
        pygame.draw.rect(surface, border, rect, 1)
        if style == "arcade":
            pygame.draw.line(
                surface,
                player_color,
                (rect.left + 2, rect.bottom - 2),
                (rect.right - 2, rect.bottom - 2),
            )
        elif style == "neon":
            pygame.draw.line(
                surface,
                player_color,
                (rect.left + 2, rect.bottom - 2),
                (rect.right - 2, rect.bottom - 2),
            )
            pygame.draw.line(
                surface,
                accent,
                (rect.left + 2, rect.top + 3),
                (rect.right - 2, rect.top + 3),
            )
        elif style == "cabinet":
            header_h = min(12, rect.height // 2)
            pygame.draw.rect(
                surface, (52, 37, 48), (rect.x + 1, rect.y + 1, rect.width - 2, header_h)
            )
            pygame.draw.line(
                surface,
                accent,
                (rect.left + 2, rect.top + header_h + 1),
                (rect.right - 2, rect.top + header_h + 1),
            )
            for y in (rect.top + 2, rect.bottom - 3):
                pygame.draw.rect(surface, player_color, (rect.left + 2, y, 2, 2))
                pygame.draw.rect(surface, player_color, (rect.right - 4, y, 2, 2))
        elif style == "scoreboard":
            header_h = min(11, rect.height // 2)
            pygame.draw.rect(
                surface, (18, 43, 48), (rect.x + 1, rect.y + 1, rect.width - 2, header_h)
            )
            pygame.draw.rect(
                surface,
                accent,
                (
                    rect.right - min(20, rect.width // 3),
                    rect.top + 2,
                    min(16, rect.width // 3 - 2),
                    2,
                ),
            )
            pygame.draw.line(
                surface,
                pal.shade(accent, 0.55),
                (rect.left + 2, rect.bottom - 3),
                (rect.right - 2, rect.bottom - 3),
            )
        elif style == "pixel":
            for x in range(rect.left + 3, rect.right - 3, 8):
                pygame.draw.rect(surface, pal.shade(accent, 0.7), (x, rect.top + 2, 2, 2))
                pygame.draw.rect(surface, pal.shade(accent, 0.7), (x, rect.bottom - 4, 2, 2))
            pygame.draw.rect(surface, player_color, (rect.left + 2, rect.top + 2, 2, 2))
            pygame.draw.rect(surface, player_color, (rect.right - 4, rect.top + 2, 2, 2))

    @staticmethod
    def _extras_for(world: "World", seat: int) -> list[_HudExtra]:
        entries = [
            _HudExtra(
                effect.name,
                HUD_CATEGORY_COLORS.get(world.extras.specs[effect.name].category, pal.WHITE),
                effect.remaining,
                effect.spec.ticks,
            )
            for effect in world.extras.active[seat]
        ]
        weapon = world.extras.weapons[seat]
        if weapon is not None:
            name, count = weapon
            entries.append(
                _HudExtra(
                    name,
                    HUD_CATEGORY_COLORS.get(world.extras.specs[name].category, pal.WHITE),
                    0,
                    0,
                    count,
                )
            )
        return entries

    @staticmethod
    def _draw_extra_icons(
        surface: pygame.Surface,
        slot: pygame.Rect,
        extras: list[_HudExtra],
        player_color: pal.Color,
        style: str,
        translator: "Translator",
        header_scale: int,
    ) -> None:
        if not extras:
            return
        first_y = slot.y + (12 if header_scale == 2 else 10)
        rows = max(0, (slot.bottom - first_y - HUD_ICON_SIZE) // HUD_ROW_HEIGHT + 1)
        visible = min(len(extras), rows)
        overflow = len(extras) - visible
        icon_x = slot.x + 3
        text_x = icon_x + HUD_ICON_SIZE + 2
        marker = f"+{overflow}" if overflow else ""
        for index, extra in enumerate(extras[:visible]):
            y = first_y + index * HUD_ROW_HEIGHT
            name = translator.translate(f"extras.{extra.name}.name")
            suffix = f" x{extra.count}" if extra.count else ""
            text_right = slot.right - 2
            if overflow and index == visible - 1:
                text_right -= text_width(marker) + 4
            available = max(0, text_right - text_x)
            label = HudRenderer._fit_text(name + suffix, available)
            color = extra.color if style != "minimal" else player_color
            HudRenderer._draw_icon(surface, extra.name, icon_x, y, color)
            label_width = text_width(label)
            if label_width:
                pygame.draw.rect(
                    surface,
                    pal.UI_BACKGROUND,
                    (text_x - 1, y - 1, label_width + 2, 7),
                )
                HudRenderer._draw_readable_text(surface, label, text_x, y)
            if extra.duration:
                bar_width = max(1, round(HUD_ICON_SIZE * extra.remaining / extra.duration))
                pygame.draw.line(
                    surface,
                    pal.YELLOW,
                    (icon_x, y + HUD_ICON_SIZE + 1),
                    (icon_x + bar_width, y + HUD_ICON_SIZE + 1),
                )
        if overflow and visible:
            draw_text(
                surface,
                marker,
                slot.right - text_width(marker) - 2,
                first_y + (visible - 1) * HUD_ROW_HEIGHT,
                player_color,
            )

    def _draw_pickup_labels(
        self,
        surface: pygame.Surface,
        world: "World",
        camera: Camera,
        translator: "Translator",
        style: str,
    ) -> int | None:
        if not world.extras.pickups:
            return None
        selected_style = style if style in HUD_STYLE_COLORS else "arcade"
        accent, background = HUD_STYLE_COLORS[selected_style]
        bottom_margin = 2
        labels = []
        max_width = max(1, surface.get_width() - 4)
        for pickup in world.extras.pickups:
            name = translator.translate(f"extras.{pickup.name}.name")
            label_width = text_width(name, HUD_PICKUP_TEXT_SCALE)
            width = min(max_width, label_width + HUD_PICKUP_ICON + 9)
            point = camera.project(pickup.pos.x, pickup.pos.y)
            labels.append((point.sx, name, pickup.name, width))
        labels.sort(key=lambda entry: entry[0])
        rows = self._pack_pickup_labels(labels, surface.get_width())
        total_height = len(rows) * HUD_PICKUP_HEIGHT
        first_y = max(1, surface.get_height() - bottom_margin - total_height)
        for row, items in enumerate(rows):
            for x, width, name, pickup_name in items:
                y = first_y + row * HUD_PICKUP_HEIGHT
                category = world.extras.specs[pickup_name].category
                color = self._muted_color(HUD_CATEGORY_COLORS.get(category, accent))
                rect = pygame.Rect(x, y, width, HUD_PICKUP_HEIGHT - 1)
                if selected_style != "minimal":
                    pygame.draw.rect(surface, background, rect)
                    pygame.draw.rect(surface, pal.shade(color, 0.72), rect, 1)
                self._draw_icon(surface, pickup_name, x + 2, y + 4, color)
                label = self._fit_text(
                    name,
                    width - HUD_PICKUP_ICON - 7,
                    HUD_PICKUP_TEXT_SCALE,
                )
                draw_text(
                    surface,
                    label,
                    x + HUD_PICKUP_ICON + 5,
                    y + (HUD_PICKUP_HEIGHT - 1 - 5) // 2,
                    pal.LIGHT_GREY,
                    HUD_PICKUP_TEXT_SCALE,
                )
        return first_y

    @staticmethod
    def _pack_pickup_labels(
        labels: list[tuple[float, str, str, int]], screen_width: int
    ) -> list[list[tuple[int, int, str, str]]]:
        rows: list[list[tuple[float, int, str, str]]] = []
        row_widths: list[int] = []
        for desired_center, name, pickup_name, width in labels:
            row_index = next(
                (
                    index
                    for index, used in enumerate(row_widths)
                    if used + width + (HUD_PICKUP_GAP if used else 0) <= screen_width - 4
                ),
                len(rows),
            )
            if row_index == len(rows):
                rows.append([])
                row_widths.append(0)
            rows[row_index].append((desired_center, width, name, pickup_name))
            row_widths[row_index] += width + (HUD_PICKUP_GAP if len(rows[row_index]) > 1 else 0)

        packed: list[list[tuple[int, int, str, str]]] = []
        for row in rows:
            positions = [
                max(2, min(screen_width - width - 2, round(center - width / 2)))
                for center, width, _, _ in row
            ]
            for index in range(1, len(row)):
                previous_width = row[index - 1][1]
                positions[index] = max(
                    positions[index], positions[index - 1] + previous_width + HUD_PICKUP_GAP
                )
            overflow = positions[-1] + row[-1][1] - (screen_width - 2)
            if overflow > 0:
                positions = [x - overflow for x in positions]
            if positions[0] < 2:
                shift = 2 - positions[0]
                positions = [x + shift for x in positions]
            packed.append(
                [
                    (x, width, name, pickup_name)
                    for x, (_, width, name, pickup_name) in zip(positions, row, strict=True)
                ]
            )
        return packed

    @staticmethod
    def _fit_text(text: str, width: int, scale: int = 1) -> str:
        if text_width(text, scale) <= width:
            return text
        shortened = text
        while shortened and text_width(shortened + ".", scale) > width:
            shortened = shortened[:-1]
        return shortened + "." if shortened else ""

    @staticmethod
    def _draw_readable_text(
        surface: pygame.Surface, text: str, x: int, y: int, scale: int = 1
    ) -> None:
        draw_text(surface, text, x + 1, y + 1, pal.BLACK, scale)
        draw_text(surface, text, x, y, pal.WHITE, scale)

    @staticmethod
    def _muted_color(color: pal.Color) -> pal.Color:
        neutral = pal.LIGHT_GREY
        red, green, blue = color
        grey_red, grey_green, grey_blue = neutral
        return (
            round(red * 0.45 + grey_red * 0.55),
            round(green * 0.45 + grey_green * 0.55),
            round(blue * 0.45 + grey_blue * 0.55),
        )

    @staticmethod
    def _draw_icon(surface: pygame.Surface, name: str, x: int, y: int, color: pal.Color) -> None:
        icon = PICKUP_ICONS[name]
        for row, pixels in enumerate(icon):
            for column, pixel in enumerate(pixels):
                if pixel == "1":
                    surface.fill(color, (x + column, y + row, 1, 1))
