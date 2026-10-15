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
class SoundBank:
    """@brief Parsed audio data.

    @param events Event class name -> sound name.
    @param sounds Sound name -> tone description.
    @param music_notes Semitones per step of the background loop (None is a rest).
    @param music_step Seconds per music step.
    @param music_wave Waveform of the music.
    @param music_volume Relative level of the music.
    """

    events: dict[str, str]
    sounds: dict[str, ToneSpec]
    music_notes: tuple[int | None, ...]
    music_step: float
    music_wave: str
    music_volume: float


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
    music = data["music"]
    notes = tuple(None if int(n) == REST else int(n) for n in music["notes"])
    return SoundBank(
        events,
        sounds,
        notes,
        float(music["step_seconds"]),
        str(music["wave"]),
        float(music["volume"]),
    )


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
        self._music_sound: pygame.mixer.Sound | None = None
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

    def start_music(self) -> None:
        """@brief Start the background loop (no-op when silent or already playing)."""
        if not self.enabled or (self._music_channel and self._music_channel.get_busy()):
            return
        if self._music_sound is None:
            samples = render_melody(
                self.bank.music_notes,
                self.bank.music_step,
                self.bank.music_wave,
                self.bank.music_volume,
            )
            self._music_sound = pygame.mixer.Sound(buffer=samples.tobytes())
        self._music_channel = self._music_sound.play(loops=-1)
        self._apply_music_volume()

    def stop_music(self) -> None:
        """@brief Stop the background loop."""
        if self._music_channel is not None:
            self._music_channel.stop()
        self._music_channel = None
