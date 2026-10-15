"""Phase 3 tests: loop, camera, effects, input, rendering (specs: rendering, input)."""

import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from pongwars.core.loop import FixedStepLoop
from pongwars.domain import constants as c
from pongwars.domain.config import MatchConfig
from pongwars.domain.events import Goal, PaddleHit
from pongwars.domain.world import FrameInputs, World
from pongwars.input.controllers import (
    GamepadInput,
    KeyBinding,
    KeyboardInput,
    KeyMap,
    collect_inputs,
)
from pongwars.render.camera import Camera
from pongwars.render.effects import ParticleSystem, Shake, Trail
from pongwars.render.font import draw_text, text_width
from pongwars.render.palette import shade
from pongwars.render.renderer import Renderer, RenderSettings

FRAME_BUDGET_SECONDS = 0.016


def test_loop_runs_fixed_steps_and_returns_alpha() -> None:
    count = []
    loop = FixedStepLoop(lambda: count.append(1), 0.1)
    alpha = loop.advance(0.25)
    assert len(count) == 2
    assert alpha == pytest.approx(0.5)


def test_loop_clamps_huge_frames() -> None:
    count = []
    loop = FixedStepLoop(lambda: count.append(1), 0.001)
    loop.advance(100.0)
    assert len(count) == 8


def test_camera_center_projects_to_screen_center() -> None:
    cam = Camera(320, 180)
    p = cam.project(c.FIELD_WIDTH / 2, c.FIELD_HEIGHT / 2)
    assert (p.sx, p.sy) == pytest.approx((160, 90))


def test_camera_perspective_far_is_smaller_and_higher() -> None:
    cam = Camera(320, 180)
    far, near = cam.project(0, 0), cam.project(0, c.FIELD_HEIGHT)
    assert far.scale < near.scale
    assert far.sy < near.sy
    assert cam.project(80, 45, 10).sy < cam.project(80, 45, 0).sy


def test_camera_is_left_right_symmetric() -> None:
    cam = Camera(320, 180)
    a, b = cam.project(10, 30), cam.project(c.FIELD_WIDTH - 10, 30)
    assert a.sx + b.sx == pytest.approx(320)
    assert a.sy == pytest.approx(b.sy)


def test_camera_table_fits_screen() -> None:
    cam = Camera(320, 180)
    for x, y in ((0, 0), (160, 0), (0, 90), (160, 90)):
        p = cam.project(x, y)
        assert 0 <= p.sx <= 320 and 0 <= p.sy <= 180


def test_effects_particles_expire() -> None:
    ps = ParticleSystem(1)
    ps.burst(1, 1, (1, 2, 3), count=5)
    assert len(ps.particles) == 5
    for _ in range(100):
        ps.update(0.05)
    assert ps.particles == []


def test_effects_trail_bounded_and_shake_decays() -> None:
    trail = Trail(3)
    for i in range(10):
        trail.push(i, i)
    assert len(trail.points) == 3
    shake = Shake(1)
    shake.trigger(4)
    for _ in range(100):
        shake.update()
    assert shake.update() == (0, 0)


def test_palette_shade_clamps() -> None:
    assert shade((200, 200, 200), 2.0) == (255, 255, 255)
    assert shade((100, 100, 100), 0.5) == (50, 50, 50)


def test_font_draws_pixels() -> None:
    surf = pygame.Surface((20, 10))
    draw_text(surf, "A1", 0, 0, (255, 255, 255))
    assert surf.get_at((1, 0))[:3] == (255, 255, 255)
    assert text_width("AB") == 7


def test_input_keyboard_and_gamepad() -> None:
    state = {pygame.K_w: False, pygame.K_s: True}
    keys = type("Keys", (), {"__getitem__": lambda _s, k: state.get(k, False)})()
    kb = KeyboardInput(KeyBinding(pygame.K_w, pygame.K_s), lambda: keys)
    assert kb.poll() == 1.0

    class Stick:
        def __init__(self, v: float) -> None:
            self.v = v

        def get_axis(self, axis: int) -> float:
            return self.v

    assert GamepadInput(Stick(0.1)).poll() == 0.0
    assert GamepadInput(Stick(-0.9)).poll() == -0.9
    assert collect_inputs([GamepadInput(Stick(1.0)), GamepadInput(Stick(-1.0))]) == FrameInputs(
        (1.0, -1.0)
    )


def test_input_keymap_remap_and_conflicts() -> None:
    keymap = KeyMap()
    keymap.rebind(0, KeyBinding(pygame.K_a, pygame.K_d))
    assert keymap.get(0).negative == pygame.K_a
    with pytest.raises(ValueError, match="key_in_use"):
        keymap.rebind(0, KeyBinding(pygame.K_UP, pygame.K_d))
    with pytest.raises(ValueError, match="duplicate"):
        keymap.rebind(0, KeyBinding(pygame.K_a, pygame.K_a))
    assert KeyMap.from_dict(keymap.to_dict()).get(0) == keymap.get(0)


@pytest.mark.parametrize(("arena", "players"), [("classic", 2), ("trident", 3), ("crossfire", 4)])
def test_render_draws_every_arena(arena: str, players: int) -> None:
    config = MatchConfig(arena=arena, controllers=("human",) * players, seed=1)
    world = World(config)
    renderer = Renderer(RenderSettings(scale=1))
    window = pygame.Surface((320, 180))
    events = []
    for _ in range(120):
        events += world.step(FrameInputs())
    renderer.handle_events(world, [PaddleHit(0), Goal(0, 1)])
    renderer.update(world, 0.016)
    renderer.present(world, window)
    assert window.get_bounding_rect().width > 0


def test_render_benchmark_under_frame_budget() -> None:
    world = World(MatchConfig(arena="crossfire", controllers=("human",) * 4, seed=1))
    renderer = Renderer(RenderSettings(scale=4))
    window = pygame.Surface((1280, 720))
    renderer.handle_events(world, [Goal(0, 1)])
    frames = 60
    start = time.perf_counter()
    for _ in range(frames):
        world.step(FrameInputs())
        renderer.update(world, 0.016)
        renderer.present(world, window)
    assert (time.perf_counter() - start) / frames < FRAME_BUDGET_SECONDS
