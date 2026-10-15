"""@package pongwars.audio.sequencer
@brief Renders a parsed ::Song into 16-bit mono PCM by mixing one voice per instrument.
"""

import math
import random
from array import array
from operator import add

from pongwars.audio.songfile import Instrument, Note, Song
from pongwars.audio.synth import PEAK, SAMPLE_RATE, note_frequency

HEADROOM = 0.45  # keeps the sum of several voices out of clipping
HIT_RATE = 5000.0  # sample-and-hold rate of unpitched noise hits (Hz)
MAX_NOISE_RATE = 12000.0
TAIL_SECONDS = 0.25  # silence kept after the last note so the release can ring out


def render_note(
    instrument: Instrument,
    pitch: int | None,
    samples: int,
    sample_rate: int = SAMPLE_RATE,
) -> list[int]:
    """@brief Synthesize one note with the instrument envelope.
    @param instrument Voice definition.
    @param pitch Semitones from A4, or None for an unpitched hit.
    @param samples Note length in samples.
    @param sample_rate Samples per second.
    @return Signed sample values (as ints, not yet clipped).
    """
    if samples <= 0:
        return []
    freq = note_frequency(pitch) if pitch is not None else HIT_RATE
    if instrument.wave == "noise" and pitch is not None:
        freq = min(freq, MAX_NOISE_RATE)
    rng = random.Random(pitch if pitch is not None else 0)  # noqa: S311 - audio only
    peak = PEAK * instrument.volume
    attack = max(1, int(instrument.attack * sample_rate))
    decay = max(1, int(instrument.decay * sample_rate))
    release = max(1, int(instrument.release * sample_rate))
    sustain = instrument.sustain
    out: list[int] = []
    phase = 0.0
    held = rng.uniform(-1.0, 1.0)
    for i in range(samples):
        bend = 1.0
        if instrument.vibrato:
            bend = 2.0 ** (
                instrument.vibrato
                * math.sin(2.0 * math.pi * instrument.vibrato_rate * i / sample_rate)
                / 12.0
            )
        phase += freq * bend / sample_rate
        if phase >= 1.0:
            phase -= int(phase)
            held = rng.uniform(-1.0, 1.0)
        if instrument.wave == "square":
            level = 1.0 if phase < instrument.duty else -1.0
        elif instrument.wave == "triangle":
            level = 4.0 * abs(phase - 0.5) - 1.0
        elif instrument.wave == "saw":
            level = 2.0 * phase - 1.0
        else:
            level = held
        if i < attack:
            env = i / attack
        elif i < attack + decay:
            env = 1.0 - (1.0 - sustain) * (i - attack) / decay
        else:
            env = sustain
        env *= min(1.0, (samples - i) / release)
        out.append(int(peak * env * level))
    return out


def render_song(song: Song, sample_rate: int = SAMPLE_RATE) -> "array[int]":
    """@brief Mix every voice of a song into one PCM buffer.
    @param song Song to render.
    @param sample_rate Samples per second.
    @return Signed 16-bit mono samples.
    """
    unit = song.seconds_per_unit * sample_rate
    total = int(song.total_units * unit) + int(TAIL_SECONDS * sample_rate)
    mix = [0] * total
    cache: dict[tuple[str, int | None, int], list[int]] = {}
    for name, notes in song.parts.items():
        instrument = song.instruments[name]
        for note in notes:
            start, length = _span(note, unit)
            key = (name, note.pitch, length)
            wave = cache.get(key)
            if wave is None:
                wave = cache[key] = render_note(instrument, note.pitch, length, sample_rate)
            end = min(total, start + length)
            mix[start:end] = map(add, mix[start:end], wave[: end - start])
    scale = HEADROOM * song.volume
    return array("h", [max(-PEAK, min(PEAK, int(value * scale))) for value in mix])


def _span(note: Note, unit: float) -> tuple[int, int]:
    start = round(note.start * unit)
    return start, max(1, round((note.start + note.length) * unit) - start)
