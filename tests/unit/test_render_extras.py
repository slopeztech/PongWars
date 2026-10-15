"""@file test_render_extras.py
@brief Headless smoke test for the extras rendering (pickups, effects, lasers, blind noise).
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from pongwars.domain.config import MatchConfig
from pongwars.domain.events import Event
from pongwars.domain.extras import Pickup
from pongwars.domain.vec import Vec2
from pongwars.domain.world import FrameInputs, World
from pongwars.render.renderer import Renderer, RenderSettings


def _world() -> World:
    return World(MatchConfig(extras=("all",), seed=3))


def test_draws_every_extra_without_error() -> None:
    """@brief Pickups, active effects, shield, laser flash and blind noise render."""
    pygame.init()
    for view in ("shared", "split"):
        world = _world()
        renderer = Renderer(RenderSettings(view=view))
        for name in ("shield", "blind", "laser", "multiball", "big_paddle"):
            world.extras.apply(name, 0, [])
        world.extras.pickups.append(Pickup(Vec2(80.0, 45.0), "bomb", 50))
        events: list[Event] = []
        for _ in range(3):
            events = world.step(FrameInputs(moves=(0.0, 0.0), fire=(True, False)))
            renderer.handle_events(world, events)
            renderer.update(world, 1 / 60)
            surface = renderer.draw(world)
        assert surface.get_size() == (320, 180)
