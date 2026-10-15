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

from pongwars.audio.synth import (
    SAMPLE_RATE,
    ToneSpec,
    render_melody,
    render_tone,
)
from pongwars.domain.events import Event

logger = logging.getLogger(__name__)

SOUNDS_FILE = Path(__file__).resolve().parent.parent / "data" / "audio" / "sounds.toml"
REST = -99
VOLUME_SCALE = 100.0


@dataclass(frozen=True)
class Track:
    """@brief A looping background track.

    @param notes Semitones per step (None is a rest).
    @param step Seconds per step.
    @param wave Waveform.
    @param volume Relative level.
    """

    notes: tuple[int | None, ...]
    step: float
    wave: str
    volume: float


MENU_TRACK = "menu"


@dataclass(frozen=True)
class SoundBank:
    """@brief Parsed audio data.

    @param events Event class name -> sound name.
    @param sounds Sound name -> tone description.
    @param tracks Track name -> background track.
    """

    events: dict[str, str]
    sounds: dict[str, ToneSpec]
    tracks: dict[str, Track]

    @property
    def match_tracks(self) -> list[str]:
        """@brief Names of the tracks that can play during a match, sorted."""
        return sorted(name for name in self.tracks if name != MENU_TRACK)


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
    tracks = {
        name: Track(
            tuple(None if int(n) == REST else int(n) for n in raw["notes"]),
            float(raw["step_seconds"]),
            str(raw["wave"]),
            float(raw["volume"]),
        )
        for name, raw in data["music"].items()
    }
    return SoundBank(events, sounds, tracks)


class AudioPlayer:
    """@brief Plays sound effects for simulation events and a looping music track.

    When no audio device is available the player stays silent after logging one warning.
    """

    def __init__(
        self, master: int = 80, music: int = 60, sfx: int = 100, bank: SoundBank | None = None
    ) -> None:
        """@brief Create the player and try to open the mixer.
        @param master Master volume 0-100.
        @param music Music volume 0-100.
        @param sfx Effects volume 0-100.
        @param bank Sound definitions (the built-in bank when omitted).
        """
        self.bank = bank or load_bank()
        self.master = master
        self.music = music
        self.sfx = sfx
        self.enabled = self._open_mixer()
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._music_sounds: dict[str, pygame.mixer.Sound] = {}
        self._current_track = ""
        self._music_channel: pygame.mixer.Channel | None = None

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
        if self._music_channel is not None:
            self._music_channel.set_volume(self.master / VOLUME_SCALE * self.music / VOLUME_SCALE)

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

    def start_music(self, track: str = MENU_TRACK) -> None:
        """@brief Loop a background track (no-op when silent or that track is already playing).
        @param track Track name from the bank; an unknown name falls back to the menu track.
        """
        if track not in self.bank.tracks:
            track = MENU_TRACK
        if not self.enabled:
            return
        if self._music_channel and self._music_channel.get_busy():
            if track == self._current_track:
                return
            self._music_channel.stop()
        if track not in self._music_sounds:
            spec = self.bank.tracks[track]
            samples = render_melody(spec.notes, spec.step, spec.wave, spec.volume)
            self._music_sounds[track] = pygame.mixer.Sound(buffer=samples.tobytes())
        self._current_track = track
        self._music_channel = self._music_sounds[track].play(loops=-1)
        self._apply_music_volume()

    def stop_music(self) -> None:
        """@brief Stop the background loop."""
        if self._music_channel is not None:
            self._music_channel.stop()
        self._music_channel = None
        self._current_track = ""
