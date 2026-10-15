"""@package pongwars.core.loop
@brief Fixed-step game loop driver (accumulator pattern), independent of any framework.
"""

from collections.abc import Callable

MAX_FRAME_SECONDS = 0.25
MAX_STEPS_PER_FRAME = 8


class FixedStepLoop:
    """@brief Converts variable frame times into a deterministic number of fixed steps."""

    def __init__(self, step: Callable[[], None], dt: float) -> None:
        """@brief Create the loop.
        @param step Callback run once per fixed step.
        @param dt Fixed step length in seconds.
        """
        self._step = step
        self.dt = dt
        self._accumulator = 0.0

    def advance(self, frame_seconds: float) -> float:
        """@brief Consume real elapsed time, running as many fixed steps as are due.
        @param frame_seconds Real time since the previous call (clamped to avoid a spiral of death).
        @return Interpolation factor in [0, 1) for the leftover time.
        """
        self._accumulator += max(0.0, min(frame_seconds, MAX_FRAME_SECONDS))
        steps = 0
        while self._accumulator >= self.dt and steps < MAX_STEPS_PER_FRAME:
            self._step()
            self._accumulator -= self.dt
            steps += 1
        if steps == MAX_STEPS_PER_FRAME:
            self._accumulator = 0.0
        return self._accumulator / self.dt
