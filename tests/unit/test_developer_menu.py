"""Tests for the hidden developer menu and extra-testing arena."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from pongwars.audio.player import AudioPlayer
from pongwars.core.i18n import Translator
from pongwars.core.settings import Settings
from pongwars.domain import constants as c
from pongwars.domain.config import MatchConfig
from pongwars.domain.extras.base import load_specs
from pongwars.domain.extras.manager import Pickup
from pongwars.domain.vec import Vec2
from pongwars.domain.world import World
from pongwars.input.controllers import KeyMap
from pongwars.render.extras_icons import PICKUP_ICONS
from pongwars.render.renderer import LOW_H, LOW_W
from pongwars.ui.core import AppContext
from pongwars.ui.developer import DeveloperDataScreen, DeveloperMenuScreen, ExtraTestingScreen
from pongwars.ui.screens import MatchScreen, PauseScreen, TitleScreen


def _ctx() -> AppContext:
    pygame.init()
    return AppContext(Settings(), Translator("es"), AudioPlayer(), KeyMap())


def _key(code: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=code)


def test_title_screen_opens_hidden_menu_with_four_then_two() -> None:
    ctx = _ctx()
    title = TitleScreen(ctx)
    ctx.stack.push(title)

    title.handle_event(_key(pygame.K_4))
    assert ctx.stack.top is title
    title.handle_event(_key(pygame.K_2))

    assert isinstance(ctx.stack.top, DeveloperMenuScreen)


def test_wrong_key_resets_hidden_code() -> None:
    ctx = _ctx()
    title = TitleScreen(ctx)
    ctx.stack.push(title)
    title.handle_event(_key(pygame.K_4))
    title.handle_event(_key(pygame.K_a))
    title.handle_event(_key(pygame.K_2))

    assert ctx.stack.top is title


def test_developer_data_and_extra_catalogue_render() -> None:
    ctx = _ctx()
    surface = pygame.Surface((LOW_W, LOW_H))
    DeveloperDataScreen(ctx).draw(surface)
    catalogue = ExtraTestingScreen(ctx)
    catalogue.draw(surface)

    specs = load_specs()
    assert len(catalogue.specs) == len(specs)
    assert all(spec.name in PICKUP_ICONS for spec in specs.values())
    assert all(ctx.t(f"dev.extra.{name}") != f"dev.extra.{name}" for name in specs)


def test_selecting_extra_starts_normal_practice_with_targeted_pickup() -> None:
    ctx = _ctx()
    catalogue = ExtraTestingScreen(ctx)
    catalogue.index = next(
        index for index, spec in enumerate(catalogue.specs) if spec.name == "build"
    )
    catalogue.handle_event(_key(pygame.K_RETURN))

    match = ctx.stack.top
    assert isinstance(match, MatchScreen)
    assert match.practice_extra == "build"
    assert match.config.controllers == ("human", "ai")
    assert match.config.ai_difficulty == "normal"
    assert match.world.extras.auto_spawn_enabled is False
    assert [pickup.name for pickup in match.world.extras.pickups] == ["build"]
    assert match.world.extras.pickups[0].target == 0
    assert match.world.extras.pickups[0].pos.y != match.world.paddles[0].rect.cy
    assert match.world.extras._paddle_collector(match.world.extras.pickups[0]) is None
    assert (
        abs(match.world.extras.pickups[0].pos.x - match.world.paddles[0].rect.cx)
        <= match.world.paddles[0].rect.half_w + c.PICKUP_RADIUS
    )

    pickup = match.world.extras.pickups[0]
    paddle = match.world.paddles[0]
    paddle.move(pickup.pos.y - paddle.rect.cy, c.FIELD_HEIGHT)
    match._step()

    assert match.world.extras.pickups == []
    assert match.world.extras.weapons[0] == ("build", 2)

    match._step()
    assert match.world.extras.pickups == []

    match.world.extras.weapons[0] = None
    paddle.rect.cy = c.FIELD_HEIGHT / 2
    match._step()
    assert [pickup.name for pickup in match.world.extras.pickups] == ["build"]


@pytest.mark.parametrize("name", load_specs())
def test_every_registered_extra_can_be_delivered_in_practice(name: str) -> None:
    world = World(
        MatchConfig(
            arena="classic",
            controllers=("human", "ai"),
            ai_difficulty="easy",
            extras=(name,),
        )
    )
    world.extras.auto_spawn_enabled = False
    paddle = world.paddles[0].rect
    pickup = Pickup(
        Vec2(paddle.cx + paddle.half_w + c.PICKUP_RADIUS - 0.25, paddle.cy),
        name,
        c.PICKUP_LIFETIME_TICKS,
        target=0,
    )
    world.extras.pickups.append(pickup)

    world.extras.update_pickups([])

    assert pickup not in world.extras.pickups


def test_quitting_practice_returns_to_extra_catalogue() -> None:
    ctx = _ctx()
    catalogue = ExtraTestingScreen(ctx)
    ctx.stack.push(catalogue)
    pause = PauseScreen(ctx, practice=True)
    ctx.stack.push(pause)
    pause._quit()

    assert ctx.stack.top is catalogue
