"""Physics tests (spec: game-core)."""

from hypothesis import given
from hypothesis import strategies as st

from pongwars.domain.entities import Rect
from pongwars.domain.physics import reflect, sweep_circle_rect
from pongwars.domain.vec import Vec2


def test_game_core_sweep_hits_front_face() -> None:
    hit = sweep_circle_rect(Vec2(0, 0), Vec2(10, 0), 1.0, Rect(5, 0, 1, 5))
    assert hit is not None
    assert hit.normal == Vec2(-1, 0)
    assert abs(hit.t - 0.3) < 1e-9


def test_game_core_sweep_misses_and_ignores_moving_away() -> None:
    rect = Rect(5, 0, 1, 1)
    assert sweep_circle_rect(Vec2(0, 20), Vec2(10, 0), 1.0, rect) is None
    assert sweep_circle_rect(Vec2(3.9, 0), Vec2(-5, 0), 1.0, rect) is None


@given(speed=st.floats(100, 5000), y=st.floats(-1, 1))
def test_game_core_no_tunneling_at_high_speed(speed: float, y: float) -> None:
    hit = sweep_circle_rect(Vec2(0, y), Vec2(speed, 0), 1.0, Rect(50, 0, 1, 5))
    assert hit is not None


def test_game_core_reflect_preserves_speed() -> None:
    v = reflect(Vec2(3, -4), Vec2(0, 1))
    assert v == Vec2(3, 4)
