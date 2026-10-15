"""@package pongwars.ui.core
@brief Screen abstraction, screen stack and the shared application context.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

import pygame

from pongwars.audio.player import AudioPlayer
from pongwars.core.i18n import Translator
from pongwars.core.settings import Settings
from pongwars.input.controllers import KeyMap


class Screen:
    """@brief Base class of every UI screen; draws on the low-resolution surface."""

    transparent = False

    def __init__(self, ctx: "AppContext") -> None:
        """@brief Create a screen.
        @param ctx Shared application context.
        """
        self.ctx = ctx

    def handle_event(self, event: pygame.event.Event) -> None:
        """@brief React to an input event.
        @param event pygame event.
        """

    def update(self, dt: float) -> None:
        """@brief Advance time.
        @param dt Seconds since the previous frame.
        """

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Render the screen.
        @param surface Low-resolution target.
        """


class ScreenStack:
    """@brief LIFO of screens; the top one receives input, overlays draw over what is below."""

    def __init__(self) -> None:
        """@brief Create an empty stack (an empty stack means the app should quit)."""
        self._screens: list[Screen] = []

    def __len__(self) -> int:
        """@brief Number of screens.
        @return Stack depth.
        """
        return len(self._screens)

    @property
    def top(self) -> Screen | None:
        """@brief The active screen.
        @return Top screen or None when empty.
        """
        return self._screens[-1] if self._screens else None

    def push(self, screen: Screen) -> None:
        """@brief Open a screen above the current one.
        @param screen Screen to show.
        """
        self._screens.append(screen)

    def pop(self) -> None:
        """@brief Close the active screen."""
        if self._screens:
            self._screens.pop()

    def handle_event(self, event: pygame.event.Event) -> None:
        """@brief Deliver an event to the active screen.
        @param event pygame event.
        """
        if self.top is not None:
            self.top.handle_event(event)

    def update(self, dt: float) -> None:
        """@brief Advance the active screen.
        @param dt Seconds elapsed.
        """
        if self.top is not None:
            self.top.update(dt)

    def pop_all(self) -> None:
        """@brief Close every screen, which ends the application."""
        self._screens.clear()

    def replace(self, screen: Screen) -> None:
        """@brief Swap the active screen.
        @param screen Replacement.
        """
        self.pop()
        self.push(screen)

    def pop_to(self, kind: type[Screen]) -> None:
        """@brief Close screens until the top one is of the given type.
        @param kind Screen class to stop at (everything is closed if absent).
        """
        while self._screens and not isinstance(self._screens[-1], kind):
            self._screens.pop()

    def draw(self, surface: pygame.Surface) -> None:
        """@brief Draw from the lowest opaque screen up to the top.
        @param surface Low-resolution target.
        """
        start = len(self._screens) - 1
        while start > 0 and self._screens[start].transparent:
            start -= 1
        for screen in self._screens[max(start, 0) :]:
            screen.draw(surface)


@dataclass
class AppContext:
    """@brief Services shared by all screens."""

    settings: Settings
    translator: Translator
    audio: AudioPlayer
    keymap: KeyMap = field(default_factory=KeyMap)
    stack: ScreenStack = field(default_factory=ScreenStack)
    on_display_change: Callable[[], None] = lambda: None

    def apply_settings(self) -> None:
        """@brief Push the current settings to language, audio and display."""
        self.translator.set_language(self.settings.language)
        self.audio.set_volumes(
            self.settings.master_volume, self.settings.music_volume, self.settings.sfx_volume
        )
        self.on_display_change()

    def t(self, key: str, **params: object) -> str:
        """@brief Translate a key.
        @param key Message key.
        @param params Placeholder values.
        @return Localised text.
        """
        return self.translator.translate(key, None, **params)
