"""@package pongwars.ai.controller
@brief AI controller exposing the same `poll()` contract as any human input.
"""

from collections import deque
from collections.abc import Callable

from pongwars.ai.extras import HOLD_TICKS, wants_fire
from pongwars.ai.observation import Observation
from pongwars.ai.profiles import PROFILES, Profile
from pongwars.ai.strategies import STRATEGIES, Strategy
from pongwars.domain import constants as c
from pongwars.domain.rng import RandomSource

RECOMPUTE_TICKS = 15
DEAD_ZONE_FRACTION = 0.25
FIRE_BASE_CHANCE = 0.05
FIRE_SKILL_GAIN = 0.3
SPIN_BASE_CHANCE = 0.1
SPIN_SKILL_GAIN = 0.5
SPIN_WINDOW_SECONDS = 0.35
SPIN_MIN_MOVE = 0.05


class AIController:
    """@brief Plays a seat using only `Observation`s; deterministic for a given seed."""

    def __init__(
        self,
        observe: Callable[[], Observation],
        difficulty: str = "normal",
        strategy: str = "predictive",
        seed: int = 0,
    ) -> None:
        """@brief Create the controller.
        @param observe Callable returning the current observation of the controlled seat.
        @param difficulty Registered profile name.
        @param strategy Registered strategy name.
        @param seed Seed of the aiming-error generator.
        @throws RegistryError For an unknown difficulty or strategy.
        """
        self.profile: Profile = PROFILES.get(difficulty)
        self._strategy: Strategy = STRATEGIES.get(strategy)
        self._observe = observe
        self._rng = RandomSource(seed)
        self._history: deque[Observation] = deque(maxlen=self.profile.reaction_ticks + 1)
        self._target: float | None = None
        self._noise = 0.0
        self._last_vel: tuple[float, float] | None = None
        self._age = RECOMPUTE_TICKS
        self._now: Observation | None = None
        self._opportunity = 0
        self._pulse = False
        self._last_move = 0.0
        self._spin_window = False
        self._spin_selected = False

    def fire_intent(self) -> bool:
        """@brief Fire button state for this tick (call once per tick, after `poll`).
        @return True for a single tick when the AI decides to use its extra.
        """
        if self._pulse:
            self._pulse = False
            return False
        obs = self._now
        if obs is None:
            return False
        want = obs.holding or wants_fire(obs)
        if not want:
            self._opportunity = 0
            return False
        self._opportunity += 1
        needed = HOLD_TICKS if obs.holding else self.profile.reaction_ticks
        if self._opportunity < needed:
            return False
        if (
            self._rng.uniform(0.0, 1.0)
            > FIRE_BASE_CHANCE + self.profile.extra_skill * FIRE_SKILL_GAIN
        ):
            return False
        self._opportunity = 0
        self._pulse = True
        return True

    def spin_intent(self) -> bool:
        """@brief Hold spin near an approaching paddle hit on selected rallies.
        @return True while the AI has selected spin and is moving its paddle.
        """
        obs = self._now
        if obs is None or not self._approaching(obs):
            self._spin_window = False
            return False
        normal_distance = self._distance_to_paddle(obs)
        normal_half = obs.paddle.half_w if obs.axis == "y" else obs.paddle.half_h
        normal_speed = abs(obs.ball_vel.x if obs.axis == "y" else obs.ball_vel.y)
        if normal_speed == 0.0 or (
            normal_distance - normal_half - obs.ball_radius
        ) / normal_speed > SPIN_WINDOW_SECONDS:
            self._spin_window = False
            return False
        if not self._spin_window:
            self._spin_selected = (
                self._rng.uniform(0.0, 1.0)
                <= SPIN_BASE_CHANCE + self.profile.extra_skill * SPIN_SKILL_GAIN
            )
            self._spin_window = True
        return self._spin_selected and abs(self._last_move) > SPIN_MIN_MOVE

    @staticmethod
    def _approaching(obs: Observation) -> bool:
        velocity = obs.ball_vel.x if obs.axis == "y" else obs.ball_vel.y
        return velocity < 0.0 if obs.seat in (0, 2) else velocity > 0.0

    @staticmethod
    def _distance_to_paddle(obs: Observation) -> float:
        coordinate = obs.ball_pos.x if obs.axis == "y" else obs.ball_pos.y
        center = obs.paddle.cx if obs.axis == "y" else obs.paddle.cy
        return coordinate - center if obs.seat in (0, 2) else center - coordinate

    def poll(self) -> float:
        """@brief Movement intent in [-1, 1] for this tick (call exactly once per tick)."""
        now = self._observe()
        self._now = now
        self._history.append(now)
        seen = self._history[0]
        vel = (seen.ball_vel.x, seen.ball_vel.y)
        self._age += 1
        if vel != self._last_vel or self._age >= RECOMPUTE_TICKS:
            if vel != self._last_vel:
                limit = self.profile.aim_error
                self._noise = self._rng.uniform(-limit, limit)
            self._last_vel = vel
            self._age = 0
            self._target = self._strategy(seen, self.profile)
        if self._target is None:
            self._last_move = 0.0
            return 0.0
        error = self._target + self._noise - now.paddle_pos
        if abs(error) < now.paddle_half * DEAD_ZONE_FRACTION:
            self._last_move = 0.0
            return 0.0
        wanted = error / (c.PADDLE_SPEED * c.DT)
        cap = self.profile.speed
        self._last_move = max(-cap, min(cap, wanted))
        return self._last_move
