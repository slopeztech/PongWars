"""@package pongwars.audio.player
@brief Event-driven audio: data-driven event -> sound mapping, volumes and silent fallback.
"""

import logging
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pygame

from pongwars.audio.jukebox import Jukebox, Library, PygameSink
from pongwars.audio.synth import (
    SAMPLE_RATE,
    ToneSpec,
    render_tone,
)
from pongwars.domain.events import Event

logger = logging.getLogger(__name__)

SOUNDS_FILE = Path(__file__).resolve().parent.parent / "data" / "audio" / "sounds.toml"
VOLUME_SCALE = 100.0


@dataclass(frozen=True)
class SoundBank:
    """@brief Parsed sound-effect data.

    @param events Event class name -> sound name.
    @param sounds Sound name -> tone description.
    """

    events: dict[str, str]
    sounds: dict[str, ToneSpec]


def load_bank(path: Path = SOUNDS_FILE) -> SoundBank:
    """@brief Read the sound definitions.
    @param path TOML file to read.
    @return The parsed bank.
    @throws ValueError If an event references an undefined sound.
    """
    data: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))
    sounds = {
        name: ToneSpec(
            str(raw["wave"]),
            float(raw["from"]),
            float(raw["to"]),
            float(raw["duration"]),
            float(raw.get("volume", 0.5)),
        )
        for name, raw in data["sounds"].items()
    }
    events: dict[str, str] = dict(data["events"])
    for event, sound in events.items():
        if sound not in sounds:
            raise ValueError(f"event {event} maps to unknown sound {sound}")
    return SoundBank(events, sounds)


class AudioPlayer:
    """@brief Plays sound effects for simulation events and a looping music track.

    When no audio device is available the player stays silent after logging one warning.
    """

    def __init__(
        self,
        master: int = 80,
        music: int = 60,
        sfx: int = 100,
        bank: SoundBank | None = None,
        library: Library | None = None,
    ) -> None:
        """@brief Create the player and try to open the mixer.
        @param master Master volume 0-100.
        @param music Music volume 0-100.
        @param sfx Effects volume 0-100.
        @param bank Sound definitions (the built-in bank when omitted).
        @param library Songs (the bundled `.pws` files when omitted).
        """
        self.bank = bank or load_bank()
        self.master = master
        self.music = music
        self.sfx = sfx
        self.enabled = self._open_mixer()
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self.library = library or Library.load()
        self.jukebox: Jukebox | None = Jukebox(self.library, PygameSink()) if self.enabled else None
        self._apply_music_volume()

    @staticmethod
    def _open_mixer() -> bool:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=1)
        except pygame.error as error:
            logger.warning("Audio unavailable, running silently: %s", error)
            return False
        return True

    def set_volumes(self, master: int, music: int, sfx: int) -> None:
        """@brief Update the volumes (0-100 each) and apply them to the music immediately.
        @param master Master volume.
        @param music Music volume.
        @param sfx Effects volume.
        """
        self.master, self.music, self.sfx = master, music, sfx
        self._apply_music_volume()

    def _apply_music_volume(self) -> None:
        if self.jukebox is not None:
            self.jukebox.sink.set_volume(self.master / VOLUME_SCALE * self.music / VOLUME_SCALE)

    def _sound(self, name: str) -> "pygame.mixer.Sound":
        if name not in self._sounds:
            samples = render_tone(self.bank.sounds[name])
            self._sounds[name] = pygame.mixer.Sound(buffer=samples.tobytes())
        return self._sounds[name]

    def play(self, name: str) -> bool:
        """@brief Play one sound effect.
        @param name Sound name from the bank.
        @return True if it was started.
        """
        if not self.enabled or name not in self.bank.sounds:
            return False
        sound = self._sound(name)
        sound.set_volume(self.master / VOLUME_SCALE * self.sfx / VOLUME_SCALE)
        sound.play()
        return True

    def handle_events(self, events: Iterable[Event]) -> int:
        """@brief Play the sound mapped to each event.
        @param events Simulation events from one step.
        @return Number of sounds started.
        """
        started = 0
        for event in events:
            name = self.bank.events.get(type(event).__name__)
            if name is not None and self.play(name):
                started += 1
        return started

    def start_music(
        self,
        context: str = "menu",
        first: str | None = None,
        seed: int | None = None,
        avoid_previous: str = "",
    ) -> str:
        """@brief Play the songs of a context back to back (no-op if already playing it).
        @param context `menu` or `match`.
        @param first Song id to start with (an unknown id is ignored).
        @param seed Optional deterministic seed for the playlist.
        @param avoid_previous Song id to exclude from the random first pick.
        @return The selected first song id, or an empty string when music is unavailable.
        """
        if self.jukebox is not None:
            return self.jukebox.start(context, first, seed, avoid_previous)
        return ""

    def stop_music(self) -> None:
        """@brief Stop the background music."""
        if self.jukebox is not None:
            self.jukebox.stop()

    def close(self) -> None:
        """@brief Release background resources (the render process)."""
        if self.jukebox is not None:
            self.jukebox.close()

    def now_playing(self) -> tuple[str, str] | None:
        """@brief Song currently audible.
        @return (title, artist), or None during silence or when music is off.
        """
        if self.jukebox is None or not self.jukebox.current:
            return None
        song = self.library.songs.get(self.jukebox.current)
        return (song.title, song.artist) if song else None

    @property
    def music_context(self) -> str:
        """@brief Context of the current playlist, or an empty string when stopped."""
        return self.jukebox.context if self.jukebox is not None else ""

    def current_song_id(self) -> str | None:
        """@brief Id of the currently audible song.
        @return Song id, or None during silence or when music is unavailable.
        """
        if self.jukebox is None or not self.jukebox.current:
            return None
        return self.jukebox.current

    def update(self, dt: float = 0.0) -> None:
        """@brief Call once per frame so the next song starts after the gap.
        @param dt Seconds since the previous frame.
        """
        if self.jukebox is not None:
            self.jukebox.update(dt)

    def song_ids(self, context: str = "match") -> list[str]:
        """@brief Ids of the songs available in a context.
        @param context `menu` or `match`.
        @return Sorted song ids.
        """
        return self.library.ids_for(context)

    def song_title(self, song_id: str) -> str:
        """@brief Display title of a song.
        @param song_id Song id.
        @return The title, or the id when unknown.
        """
        song = self.library.songs.get(song_id)
        return song.title if song else song_id
