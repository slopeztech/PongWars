"""@package pongwars.audio.synth
@brief Pure chiptune waveform synthesis (square, triangle, noise) into 16-bit PCM.
"""

import math
import random
from array import array
from dataclasses import dataclass

SAMPLE_RATE = 22050
PEAK = 32767
WAVES = ("square", "triangle", "noise")
SQUARE_DUTY = 0.5
FADE_FRACTION = 0.15  # tail of each tone faded out to avoid clicks
NOISE_SEED = 1234


@dataclass(frozen=True)
class ToneSpec:
    """@brief One synthesized sound effect.

    @param wave One of WAVES.
    @param freq_start Frequency at the start (Hz).
    @param freq_end Frequency at the end (Hz); the pitch slides linearly.
    @param duration Length in seconds.
    @param volume Relative level in [0, 1].
    """

    wave: str
    freq_start: float
    freq_end: float
    duration: float
    volume: float = 0.5


def render_tone(spec: ToneSpec, sample_rate: int = SAMPLE_RATE) -> "array[int]":
    """@brief Synthesize a tone.
    @param spec Tone description.
    @param sample_rate Samples per second.
    @return Signed 16-bit mono samples.
    @throws ValueError For an unknown waveform or non-positive duration.
    """
    if spec.wave not in WAVES:
        raise ValueError(f"unknown wave {spec.wave}")
    if spec.duration <= 0:
        raise ValueError("duration must be positive")
    count = max(1, int(spec.duration * sample_rate))
    rng = random.Random(NOISE_SEED)  # noqa: S311 - audio only
    samples = array("h")
    phase = 0.0
    fade = max(1, int(count * FADE_FRACTION))
    for i in range(count):
        t = i / count
        freq = spec.freq_start + (spec.freq_end - spec.freq_start) * t
        phase = (phase + freq / sample_rate) % 1.0
        if spec.wave == "square":
            level = 1.0 if phase < SQUARE_DUTY else -1.0
        elif spec.wave == "triangle":
            level = 4.0 * abs(phase - 0.5) - 1.0
        else:
            level = rng.uniform(-1.0, 1.0)
        envelope = min(1.0, (count - i) / fade)
        samples.append(int(PEAK * spec.volume * envelope * level))
    return samples


def note_frequency(semitones_from_a4: float) -> float:
    """@brief Equal-tempered frequency.
    @param semitones_from_a4 Semitone distance from A4 (440 Hz).
    @return Frequency in Hz.
    """
    return 440.0 * math.pow(2.0, semitones_from_a4 / 12.0)
