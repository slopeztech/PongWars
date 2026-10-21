"""Hidden developer tools for inspecting game metadata and testing extras."""

import platform

import pygame

import pongwars
from pongwars.domain import constants as c
from pongwars.domain.config import MatchConfig
from pongwars.domain.extras.base import EffectSpec, load_specs
from pongwars.domain.extras.manager import Pickup
from pongwars.domain.vec import Vec2
from pongwars.domain.world import World
from pongwars.render import palette as pal
from pongwars.render.extras_icons import PICKUP_ICONS
from pongwars.render.font import draw_text, text_width
from pongwars.render.renderer import LOW_W
from pongwars.ui.core import AppContext, Screen
from pongwars.ui.screens import HINT_Y, MatchScreen, _centered, _centered_title, _menu_backdrop

ROWS_VISIBLE = 10
ROW_HEIGHT = 11
LIST_X = 18
LIST_Y = 40
LIST_WIDTH = 124
DETAIL_X = 153
DETAIL_WIDTH = 141
ICON_COLORS = {
    "power": pal.UI_CYAN,
    "weapon": pal.UI_ORANGE,
    "penalty": pal.RED,
    "status": pal.LAVENDER,
}


def place_practice_pickup(world: World, name: str) -> None:
    """Keep the selected extra in the player's reachable paddle lane."""
    seat = 0
    paddle = world.paddles[seat].rect
    existing = next((pickup for pickup in world.extras.pickups if pickup.name == name), None)
    if existing is not None:
        existing.ttl = c.PICKUP_LIFETIME_TICKS
        return
    if world.paddles[seat].axis == "y":
        margin = paddle.half_h + c.PICKUP_RADIUS + 1.0
        pickup_pos = Vec2(
            paddle.cx,
            min(max(c.FIELD_HEIGHT * 0.25, margin), c.FIELD_HEIGHT - margin),
        )
    else:
        margin = paddle.half_w + c.PICKUP_RADIUS + 1.0
        pickup_pos = Vec2(
            min(max(c.FIELD_WIDTH * 0.25, margin), c.FIELD_WIDTH - margin),
            paddle.cy,
        )
    world.extras.pickups.clear()
    world.extras.pickups.append(
        Pickup(
            pickup_pos,
            name,
            c.PICKUP_LIFETIME_TICKS,
            target=seat,
        )
    )


def practice_extra_is_active(world: World, name: str, seat: int = 0) -> bool:
    """Return whether a tested extra still has a live effect or usable weapon."""
    if any(effect.name == name for effects in world.extras.active for effect in effects):
        return True
    weapon = world.extras.weapons[seat]
    if weapon is not None and weapon[0] == name and weapon[1] > 0:
        return True
    if name == "cat":
        return any(cat.owner == seat for cat in world.extras.cats)
    if name == "chomper":
        return any(chomper.owner == seat for chomper in world.extras.chompers)
    if name == "companion":
        return any(ally.owner == seat for ally in world.extras.companions)
    if name == "invasor":
        return any(invader.target == seat for invader in world.extras.invaders)
    if name == "stalker":
        return any(stalker.target == seat for stalker in world.extras.stalkers)
    if name == "missile":
        return any(missile.owner == seat for missile in world.extras.missiles)
    if name == "multiball" and world.extra_balls:
        return True
    if name == "build" and any(
        obstacle.kind == "built" and obstacle.owner == seat for obstacle in world.obstacles
    ):
        return True
    return name == "headbutt" and world.paddles[seat].headbutt_ticks > 0


class DeveloperMenuScreen(Screen):
    """Menu reachable with the hidden 4-2 title-screen key sequence."""

    def __init__(self, ctx: AppContext) -> None:
        """Create the developer menu with its first entry selected."""
        super().__init__(ctx)
        self._selection = 0

    def handle_event(self, event: pygame.event.Event) -> None:
        """Navigate the menu and open the selected tool."""
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.ctx.stack.pop()
        elif event.key in (pygame.K_UP, pygame.K_DOWN):
            self._selection = (self._selection + (1 if event.key == pygame.K_DOWN else -1)) % 3
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            if self._selection == 0:
                self.ctx.stack.push(DeveloperDataScreen(self.ctx))
            elif self._selection == 1:
                self.ctx.stack.push(ExtraTestingScreen(self.ctx))
            else:
                self.ctx.stack.pop()
            self.ctx.audio.play("menu")

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the developer menu."""
        _menu_backdrop(surface)
        _centered_title(surface, self.ctx.t("dev.title"), 28)
        entries = (
            self.ctx.t("dev.data"),
            self.ctx.t("dev.extra_testing"),
            self.ctx.t("dev.back"),
        )
        for index, label in enumerate(entries):
            y = 72 + index * 20
            if index == self._selection:
                pygame.draw.rect(surface, pal.UI_DARK, (86, y - 2, 148, 14))
                pygame.draw.rect(surface, pal.UI_CYAN, (86, y - 2, 148, 14), 1)
            _centered(surface, label, y, pal.WHITE if index == self._selection else pal.LIGHT_GREY)
        _centered(surface, self.ctx.t("dev.menu_hint"), HINT_Y, pal.LIGHT_GREY)


class DeveloperDataScreen(Screen):
    """Shows application and runtime metadata."""

    def draw(self, surface: pygame.Surface) -> None:
        """Draw developer and runtime version information."""
        _menu_backdrop(surface)
        _centered_title(surface, self.ctx.t("dev.data"), 24)
        info = (
            ("dev.developer", "slopez.tech"),
            ("dev.version", pongwars.__version__),
            ("dev.website", "https://slopez.tech"),
            ("dev.python", platform.python_version()),
            ("dev.pygame", pygame.version.ver),
            ("dev.sdl", ".".join(map(str, pygame.get_sdl_version()))),
        )
        for index, (label_key, value) in enumerate(info):
            y = 54 + index * 15
            label = self.ctx.t(label_key) + ":"
            draw_text(surface, label, 26, y, pal.UI_CYAN)
            draw_text(surface, _fit(value, 154), 119, y, pal.WHITE)
        _centered(surface, self.ctx.t("dev.back_hint"), HINT_Y, pal.LIGHT_GREY)

    def handle_event(self, event: pygame.event.Event) -> None:
        """Return to the developer menu."""
        if event.type == pygame.KEYDOWN and event.key in (
            pygame.K_ESCAPE,
            pygame.K_RETURN,
            pygame.K_KP_ENTER,
            pygame.K_SPACE,
        ):
            self.ctx.stack.pop()


class ExtraTestingScreen(Screen):
    """Scrollable extra catalogue with descriptions, icons and direct practice launch."""

    def __init__(self, ctx: AppContext) -> None:
        """Load the registered extra catalogue."""
        super().__init__(ctx)
        self.specs = list(load_specs().values())
        self.index = 0

    def handle_event(self, event: pygame.event.Event) -> None:
        """Move through extras or start a practice match."""
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.ctx.stack.pop()
        elif event.key in (pygame.K_UP, pygame.K_DOWN):
            self.index = (self.index + (1 if event.key == pygame.K_DOWN else -1)) % len(
                self.specs
            )
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self._start_practice(self.specs[self.index])

    def _start_practice(self, spec: EffectSpec) -> None:
        """Start a normal-difficulty one-on-one match with the selected pickup."""
        config = MatchConfig(
            arena="classic",
            controllers=("human", "ai"),
            ai_difficulty="normal",
            extras=(spec.name,),
            seed=0,
        )
        self.ctx.stack.push(
            MatchScreen(self.ctx, config, "shared", practice_extra=spec.name)
        )

    def _visible_start(self) -> int:
        """Return the first catalogue row that fits around the current selection."""
        if len(self.specs) <= ROWS_VISIBLE:
            return 0
        return max(0, min(self.index - ROWS_VISIBLE // 2, len(self.specs) - ROWS_VISIBLE))

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the scrollable catalogue and the selected extra's details."""
        _menu_backdrop(surface)
        _centered_title(surface, self.ctx.t("dev.extra_testing"), 15)
        content = pygame.Rect(16, 34, LOW_W - 32, 118)
        pygame.draw.rect(surface, pal.UI_BACKGROUND, content)
        pygame.draw.rect(surface, pal.UI_MUTED, content, 1)
        start = self._visible_start()
        for row, spec in enumerate(self.specs[start : start + ROWS_VISIBLE]):
            selected = start + row == self.index
            y = LIST_Y + row * ROW_HEIGHT
            if selected:
                pygame.draw.rect(surface, pal.UI_DARK, (LIST_X, y - 1, LIST_WIDTH, 10))
                pygame.draw.rect(surface, pal.UI_CYAN, (LIST_X, y - 1, LIST_WIDTH, 10), 1)
            self._draw_icon(surface, spec.name, LIST_X + 3, y + 1, 1)
            name = self.ctx.t(f"extras.{spec.name}.name")
            draw_text(
                surface,
                _fit(name, 94),
                LIST_X + 12,
                y,
                pal.WHITE if selected else pal.LIGHT_GREY,
            )
        self._draw_details(surface, self.specs[self.index])
        _centered(surface, self.ctx.t("dev.extra_hint"), HINT_Y, pal.LIGHT_GREY)

    def _draw_icon(self, surface: pygame.Surface, name: str, x: int, y: int, pixel: int) -> None:
        pattern = PICKUP_ICONS.get(name)
        if pattern is None:
            return
        spec = next(spec for spec in self.specs if spec.name == name)
        color = ICON_COLORS[spec.category]
        for row, line in enumerate(pattern):
            for column, active in enumerate(line):
                if active == "1":
                    pygame.draw.rect(
                        surface,
                        color,
                        (x + column * pixel, y + row * pixel, pixel, pixel),
                    )

    def _draw_details(self, surface: pygame.Surface, spec: EffectSpec) -> None:
        panel = pygame.Rect(DETAIL_X, 38, DETAIL_WIDTH, 111)
        pygame.draw.rect(surface, pal.UI_BACKGROUND, panel)
        pygame.draw.rect(surface, pal.UI_MUTED, panel, 1)
        self._draw_icon(surface, spec.name, panel.centerx - 10, 46, 4)
        name = self.ctx.t(f"extras.{spec.name}.name")
        _centered_in(surface, _fit(name, DETAIL_WIDTH - 8), panel, 72, pal.WHITE)
        category = self.ctx.t(f"dev.category.{spec.category}")
        _centered_in(surface, category, panel, 85, ICON_COLORS[spec.category])
        description = self.ctx.t(f"dev.extra.{spec.name}")
        for row, line in enumerate(_wrap(description, DETAIL_WIDTH - 12)[:4]):
            _centered_in(surface, line, panel, 99 + row * 9, pal.LIGHT_GREY)


def _centered_in(
    surface: pygame.Surface, text: str, rect: pygame.Rect, y: int, color: pal.Color
) -> None:
    draw_text(surface, text, rect.centerx - text_width(text) // 2, y, color)


def _fit(text: str, width: int) -> str:
    if text_width(text) <= width:
        return text
    shortened = text
    while shortened and text_width(shortened + ".") > width:
        shortened = shortened[:-1]
    return shortened + "." if shortened else ""


def _wrap(text: str, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and text_width(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines
