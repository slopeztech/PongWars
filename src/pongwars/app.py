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
        display_count = max(1, pygame.display.get_num_displays())
        display_index = min(self.settings.display_index, display_count - 1)
        self.settings.display_index = display_index
        self._active_display = display_index
        if self.settings.fullscreen:
            return pygame.display.set_mode((0, 0), pygame.FULLSCREEN, display=display_index)
        return pygame.display.set_mode(size, display=display_index)

    def apply_display(self) -> None:
        """@brief Apply window size, fullscreen and monitor changes immediately."""
        if not hasattr(self, "window"):
            return
        wanted = (LOW_W * self.settings.scale, LOW_H * self.settings.scale)
        fullscreen = bool(self.window.get_flags() & pygame.FULLSCREEN)
        display_changed = self._active_display != self.settings.display_index
        size_changed = not fullscreen and self.window.get_size() != wanted
        if not display_changed and fullscreen == self.settings.fullscreen and not size_changed:
            return

        display_count = max(1, pygame.display.get_num_displays())
        display_index = min(self.settings.display_index, display_count - 1)
        self.settings.display_index = display_index
        if display_changed:
            self.window = pygame.display.set_mode(wanted, display=display_index)
            centered_on_display = pygame.WINDOWPOS_CENTERED | display_index
            pygame.display.set_window_position((centered_on_display, centered_on_display))
            if self.settings.fullscreen:
                self.window = pygame.display.set_mode(
                    (0, 0), pygame.FULLSCREEN, display=display_index
                )
        elif fullscreen != self.settings.fullscreen:
            self.window = self._open_window()
        elif size_changed:
            self.window = pygame.display.set_mode(wanted, display=display_index)
        self._active_display = display_index

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
        song_id = self.ctx.audio.current_song_id()
        song_key = (self.ctx.audio.music_context, song_id) if song_id is not None else None
        self.ctx.music_notice.update(song_key, self.ctx.audio.now_playing(), dt)
        stack.update(dt)
        if stack.top is None:
            return False
        stack.draw(self.surface)
        if stack.top is not None and stack.top.show_music_notice:
            self.ctx.music_notice.draw(self.surface)
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
            self.ctx.audio.close()
            pygame.quit()


def run() -> None:
    """@brief Launch the game."""
    App().run()
