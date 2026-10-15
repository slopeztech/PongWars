"""@package pongwars.app
@brief Application composition root: window, main loop and screen stack.
"""

import pygame

from pongwars.audio.player import AudioPlayer
from pongwars.core.i18n import Translator
from pongwars.core.settings import Settings
from pongwars.domain import constants as c
from pongwars.render.renderer import LOW_H, LOW_W
from pongwars.ui.core import AppContext
from pongwars.ui.screens import TitleScreen, make_keymap

MS_PER_SECOND = 1000.0
MAX_FRAME = 0.1


class App:
    """@brief Owns the window and drives the screen stack."""

    def __init__(self, settings: Settings | None = None) -> None:
        """@brief Initialise pygame, services and the first screen.
        @param settings Settings to use (loaded from disk when omitted).
        """
        pygame.init()
        self.settings = settings or Settings.load()
        self.ctx = AppContext(
            self.settings,
            Translator(self.settings.language),
            AudioPlayer(),
            make_keymap(self.settings.keys),
        )
        self.ctx.on_display_change = self.apply_display
        self.window = self._open_window()
        self.surface = pygame.Surface((LOW_W, LOW_H))
        self.ctx.apply_settings()
        pygame.display.set_caption(self.ctx.t("app.title"))
        self.ctx.stack.push(TitleScreen(self.ctx))

    def _open_window(self) -> pygame.Surface:
        size = (LOW_W * self.settings.scale, LOW_H * self.settings.scale)
        flags = pygame.FULLSCREEN | pygame.SCALED if self.settings.fullscreen else 0
        return pygame.display.set_mode(size, flags)

    def apply_display(self) -> None:
        """@brief Re-open the window when size or fullscreen changed."""
        if not hasattr(self, "window"):
            return
        wanted = (LOW_W * self.settings.scale, LOW_H * self.settings.scale)
        fullscreen = bool(self.window.get_flags() & pygame.FULLSCREEN)
        if fullscreen != self.settings.fullscreen or (
            not fullscreen and self.window.get_size() != wanted
        ):
            self.window = self._open_window()

    def tick(self, dt: float) -> bool:
        """@brief Process one frame.
        @param dt Seconds since the previous frame.
        @return False when the application should exit.
        """
        stack = self.ctx.stack
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                stack.pop_all()
            else:
                stack.handle_event(event)
        self.ctx.audio.update(dt)
        stack.update(dt)
        if stack.top is None:
            return False
        stack.draw(self.surface)
        pygame.transform.scale(self.surface, self.window.get_size(), self.window)
        pygame.display.flip()
        return True

    def run(self) -> None:
        """@brief Run until the stack is empty, then persist settings and shut down."""
        clock = pygame.time.Clock()
        try:
            while self.tick(min(clock.tick(c.TICK_RATE) / MS_PER_SECOND, MAX_FRAME)):
                pass
        finally:
            self.settings.save()
            pygame.quit()


def run() -> None:
    """@brief Launch the game."""
    App().run()
