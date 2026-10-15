"""@package pongwars.input.controllers
@brief Local input sources (keyboard, gamepad) producing one movement intent per seat.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

import pygame

from pongwars.domain.world import FrameInputs

DEADZONE = 0.2


class PlayerInput(Protocol):
    """@brief Anything that yields a movement intent in [-1, 1] for one seat."""

    def poll(self) -> float:
        """@brief Read the current intent.
        @return -1 (up/left) to 1 (down/right).
        """
        ...


@dataclass(frozen=True)
class KeyBinding:
    """@brief A pair of keys driving one paddle."""

    negative: int
    positive: int


DEFAULT_BINDINGS: tuple[KeyBinding, ...] = (
    KeyBinding(pygame.K_w, pygame.K_s),
    KeyBinding(pygame.K_UP, pygame.K_DOWN),
    KeyBinding(pygame.K_j, pygame.K_l),
    KeyBinding(pygame.K_KP8, pygame.K_KP2),
)

FIRE_KEYS: tuple[int, ...] = (pygame.K_d, pygame.K_LEFT, pygame.K_k, pygame.K_KP5)


class KeyMap:
    """@brief Per-seat key bindings with conflict-checked remapping."""

    def __init__(self, bindings: Sequence[KeyBinding] = DEFAULT_BINDINGS) -> None:
        """@brief Create a key map.
        @param bindings One binding per seat.
        """
        self._bindings = list(bindings)

    def get(self, seat: int) -> KeyBinding:
        """@brief Binding of a seat.
        @param seat Seat index.
        @return The seat's key pair.
        """
        return self._bindings[seat]

    def rebind(self, seat: int, binding: KeyBinding) -> None:
        """@brief Replace a seat's keys.
        @param seat Seat index.
        @param binding New key pair.
        @throws ValueError If a key is duplicated or used by another seat.
        """
        if binding.negative == binding.positive:
            raise ValueError("input.error.duplicate_key")
        used = {
            k for i, b in enumerate(self._bindings) if i != seat for k in (b.negative, b.positive)
        }
        if used & {binding.negative, binding.positive}:
            raise ValueError("input.error.key_in_use")
        self._bindings[seat] = binding

    def to_dict(self) -> dict[str, list[int]]:
        """@brief Serialise for settings storage.
        @return Mapping of seat index to [negative, positive] key codes.
        """
        return {str(i): [b.negative, b.positive] for i, b in enumerate(self._bindings)}

    @classmethod
    def from_dict(cls, data: dict[str, list[int]]) -> "KeyMap":
        """@brief Restore from `to_dict` output; missing seats keep defaults.
        @param data Serialised bindings.
        @return A new key map.
        """
        keymap = cls()
        for key, (neg, pos) in data.items():
            keymap.rebind(int(key), KeyBinding(neg, pos))
        return keymap


class KeyboardInput:
    """@brief Reads one seat from the keyboard state."""

    def __init__(self, binding: KeyBinding, pressed: Callable[[], Sequence[bool]]) -> None:
        """@brief Create the controller.
        @param binding Keys to use.
        @param pressed Callable returning the key state (e.g. `pygame.key.get_pressed`).
        """
        self._binding = binding
        self._pressed = pressed

    def poll(self) -> float:
        """@brief Read the intent from the held keys.
        @return -1, 0 or 1.
        """
        state = self._pressed()
        return float(bool(state[self._binding.positive])) - float(
            bool(state[self._binding.negative])
        )


class _Joystick(Protocol):
    def get_axis(self, axis: int) -> float: ...


class GamepadInput:
    """@brief Reads one seat from a gamepad axis with a dead zone."""

    def __init__(self, joystick: _Joystick, axis: int = 1, deadzone: float = DEADZONE) -> None:
        """@brief Create the controller.
        @param joystick Object exposing `get_axis`.
        @param axis Axis index to read.
        @param deadzone Magnitudes below this count as zero.
        """
        self._joystick = joystick
        self._axis = axis
        self._deadzone = deadzone

    def poll(self) -> float:
        """@brief Read the axis.
        @return Value in [-1, 1], zero inside the dead zone.
        """
        value = self._joystick.get_axis(self._axis)
        return 0.0 if abs(value) < self._deadzone else max(-1.0, min(1.0, value))


def collect_inputs(controllers: Sequence[PlayerInput], fire: Sequence[bool] = ()) -> FrameInputs:
    """@brief Poll every seat into the simulation's input record.
    @param controllers One input source per seat.
    @param fire Fire button state per seat (missing seats count as released).
    @return The frame inputs.
    """
    moves = tuple(controller.poll() for controller in controllers)
    shots = list(fire)
    for seat, controller in enumerate(controllers):
        intent = getattr(controller, "fire_intent", None)
        if intent is not None:
            shots += [False] * (seat + 1 - len(shots))
            shots[seat] = shots[seat] or bool(intent())
    return FrameInputs(moves, tuple(shots))


def poll_fire(
    seats: Sequence[bool], pressed: Callable[[], Sequence[bool]], keys: Sequence[int] = FIRE_KEYS
) -> tuple[bool, ...]:
    """@brief Read the fire buttons of the human seats.
    @param seats True for each seat controlled by a local human.
    @param pressed Callable returning the key state (e.g. `pygame.key.get_pressed`).
    @param keys Fire key per seat.
    @return Fire state per seat (always False for non-human seats).
    """
    state = pressed()
    return tuple(human and bool(state[key]) for human, key in zip(seats, keys, strict=False))
