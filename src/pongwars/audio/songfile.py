"""@package pongwars.audio.songfile
@brief Parser for the PongWars song format (`.pws`), a small text protocol for 8-bit music.

The format is documented in `docs/music-format.md`. A file declares metadata (title, tempo, meter),
instruments, named sections holding one line of bars per instrument, and an arrangement that
lists the sections to play in order. Parsing produces an immutable, fully validated ::Song.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

SONG_SUFFIX = ".pws"
UNITS_PER_WHOLE = 64  # time resolution: a 64th note is one unit
DENOMINATORS = (1, 2, 4, 8, 16, 32)
WAVES = ("square", "triangle", "saw", "noise")
CONTEXTS = ("menu", "match")
DEFAULT_DURATION = 4
DEFAULT_TEMPO = 120
MIN_TEMPO, MAX_TEMPO = 40, 300
SEMITONES = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}
_COMMENT_RE = re.compile(r"(^|\s)#.*$")  # '#' starts a comment only after whitespace
NOTE_RE = re.compile(r"^(?:([A-Ga-g])([#b]?)(-?\d)|([RrXx]))(?::(\d+)(\.?))?$")
REPEAT_RE = re.compile(r"^([A-Za-z_][\w-]*)(?:\*(\d+))?$")


class SongError(ValueError):
    """@brief Raised when a song file is malformed; the message carries the line number."""


@dataclass(frozen=True)
class Instrument:
    """@brief A synthesizer voice.

    @param name Identifier used in sections.
    @param wave One of WAVES.
    @param volume Relative level in [0, 1].
    @param duty Pulse width of a square wave in (0, 1).
    @param attack Seconds to reach full level.
    @param decay Seconds to fall from full level to the sustain level.
    @param sustain Held level in [0, 1].
    @param release Seconds of fade at the end of each note.
    @param vibrato Vibrato depth in semitones (0 disables it).
    @param vibrato_rate Vibrato speed in Hz.
    """

    name: str
    wave: str = "square"
    volume: float = 0.5
    duty: float = 0.5
    attack: float = 0.004
    decay: float = 0.06
    sustain: float = 0.7
    release: float = 0.04
    vibrato: float = 0.0
    vibrato_rate: float = 5.5


@dataclass(frozen=True)
class Note:
    """@brief One note placed on the song timeline.

    @param start Start time in units (64ths of a whole note).
    @param length Length in units.
    @param pitch Semitones from A4, or None for an unpitched hit (`X`).
    """

    start: int
    length: int
    pitch: int | None


@dataclass(frozen=True)
class Song:
    """@brief A validated, flattened song.

    @param song_id File stem, used as the identifier.
    @param title Human readable title.
    @param artist Author.
    @param tempo Quarter notes per minute.
    @param beats_per_bar Numerator of the meter.
    @param beat_unit Denominator of the meter.
    @param volume Overall level in [0, 1].
    @param contexts Where the song may play (subset of CONTEXTS).
    @param instruments Instrument name -> definition.
    @param parts Instrument name -> notes in time order.
    @param total_units Song length in units.
    """

    song_id: str
    title: str
    artist: str
    tempo: int
    beats_per_bar: int
    beat_unit: int
    volume: float
    contexts: tuple[str, ...]
    instruments: dict[str, Instrument]
    parts: dict[str, tuple[Note, ...]]
    total_units: int

    @property
    def seconds_per_unit(self) -> float:
        """@brief Duration of one time unit in seconds."""
        return 60.0 / self.tempo * 4.0 / UNITS_PER_WHOLE

    @property
    def duration(self) -> float:
        """@brief Song length in seconds."""
        return self.total_units * self.seconds_per_unit


@dataclass
class _Section:
    """@brief A parsed section: instrument -> bars (each bar is a list of notes relative to it)."""

    name: str
    voices: dict[str, list[list[Note]]] = field(default_factory=dict)

    @property
    def bar_count(self) -> int:
        """@brief Number of bars (the longest voice)."""
        return max((len(bars) for bars in self.voices.values()), default=0)


def _fail(line_no: int, message: str) -> SongError:
    return SongError(f"line {line_no}: {message}")


def _parse_number(raw: str, line_no: int, what: str) -> float:
    try:
        return float(raw)
    except ValueError:
        raise _fail(line_no, f"{what} must be a number, got '{raw}'") from None


def parse_note_token(token: str, previous: int, line_no: int = 0) -> tuple[int | None, int, int]:
    """@brief Parse one note token such as `C#4:8`, `R:4`, `X:16` or `A3.`.
    @param token Token text.
    @param previous Duration denominator used when the token has none.
    @param line_no Line number for error messages.
    @return (pitch semitones from A4 or None for hits and rests, length in units, denominator).
    @throws SongError For an unknown token or duration.
    """
    match = NOTE_RE.match(token)
    if match is None:
        raise _fail(line_no, f"invalid note '{token}'")
    letter, accidental, octave, special, denom_raw, dot = match.groups()
    denom = int(denom_raw) if denom_raw else previous
    if denom not in DENOMINATORS:
        raise _fail(line_no, f"unsupported duration {denom} in '{token}'")
    length = UNITS_PER_WHOLE // denom
    if dot:
        length = length * 3 // 2
    if special is not None:
        return None, length, denom
    semitone = SEMITONES[letter.upper()] + (int(octave) - 4) * 12
    semitone += {"#": 1, "b": -1, "": 0}[accidental]
    return semitone, length, denom


def _parse_bars(body: str, bar_units: int, line_no: int) -> list[list[Note]]:
    bars: list[list[Note]] = []
    for chunk in body.split("|"):
        tokens = chunk.split()
        if not tokens:
            continue
        notes: list[Note] = []
        cursor = 0
        denom = DEFAULT_DURATION
        for token in tokens:
            pitch, length, denom = parse_note_token(token, denom, line_no)
            if token[0] not in "Rr":
                notes.append(Note(cursor, length, pitch))
            cursor += length
        if cursor != bar_units:
            raise _fail(
                line_no, f"bar {len(bars) + 1} has {cursor} units, the meter needs {bar_units}"
            )
        bars.append(notes)
    return bars


def _parse_instrument(rest: str, line_no: int) -> Instrument:
    if "=" not in rest:
        raise _fail(line_no, "expected 'instrument NAME = WAVE [key=value ...]'")
    name, spec = (part.strip() for part in rest.split("=", 1))
    tokens = spec.split()
    if not name or not tokens:
        raise _fail(line_no, "expected 'instrument NAME = WAVE [key=value ...]'")
    wave = tokens[0]
    if wave not in WAVES:
        raise _fail(line_no, f"unknown wave '{wave}' (use {', '.join(WAVES)})")
    values: dict[str, float] = {}
    allowed = {
        "volume",
        "duty",
        "attack",
        "decay",
        "sustain",
        "release",
        "vibrato",
        "vibrato_rate",
    }
    for token in tokens[1:]:
        key, sep, raw = token.partition("=")
        if not sep or key not in allowed:
            raise _fail(line_no, f"unknown instrument setting '{token}'")
        values[key] = _parse_number(raw, line_no, key)
    instrument = Instrument(name, wave, **values)
    for key in ("volume", "sustain"):
        if not 0.0 <= getattr(instrument, key) <= 1.0:
            raise _fail(line_no, f"{key} must be between 0 and 1")
    if not 0.0 < instrument.duty < 1.0:
        raise _fail(line_no, "duty must be between 0 and 1")
    return instrument


@dataclass
class _Meta:
    title: str = ""
    artist: str = ""
    tempo: int = DEFAULT_TEMPO
    meter: tuple[int, int] = (4, 4)
    volume: float = 1.0
    contexts: tuple[str, ...] = CONTEXTS


def _parse_meta(meta: _Meta, key: str, value: str, line_no: int) -> None:
    if key == "title":
        meta.title = value
    elif key == "artist":
        meta.artist = value
    elif key == "tempo":
        meta.tempo = int(_parse_number(value, line_no, "tempo"))
        if not MIN_TEMPO <= meta.tempo <= MAX_TEMPO:
            raise _fail(line_no, f"tempo must be between {MIN_TEMPO} and {MAX_TEMPO}")
    elif key == "meter":
        top, sep, bottom = value.partition("/")
        if not (sep and top.strip().isdigit() and bottom.strip().isdigit()):
            raise _fail(line_no, "meter must look like 4/4")
        beats, unit = int(top), int(bottom)
        if beats < 1 or unit not in DENOMINATORS:
            raise _fail(line_no, f"unsupported meter {value}")
        meta.meter = (beats, unit)
    elif key == "volume":
        meta.volume = _parse_number(value, line_no, "volume")
        if not 0.0 < meta.volume <= 1.0:
            raise _fail(line_no, "volume must be in (0, 1]")
    elif key == "use":
        names = tuple(part.strip() for part in value.replace(",", " ").split())
        expanded = CONTEXTS if names == ("any",) else names
        if not expanded or any(name not in CONTEXTS for name in expanded):
            raise _fail(line_no, f"use must be 'any' or a list of {', '.join(CONTEXTS)}")
        meta.contexts = expanded
    else:
        raise _fail(line_no, f"unknown setting '{key}'")


def parse_song(text: str, song_id: str = "song") -> Song:
    """@brief Parse song text into a validated song.
    @param text Contents of a `.pws` file.
    @param song_id Identifier to store in the song.
    @return The parsed song.
    @throws SongError On any syntax or consistency problem.
    """
    meta = _Meta()
    instruments: dict[str, Instrument] = {}
    sections: dict[str, _Section] = {}
    arrangement: list[tuple[str, int, int]] = []
    current: _Section | None = None
    in_arrangement = False
    bar_units = 0

    def bar_size() -> int:
        return meta.meter[0] * UNITS_PER_WHOLE // meta.meter[1]

    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = _COMMENT_RE.sub("", raw).strip()
        if not line:
            continue
        if line.startswith("["):
            if not line.endswith("]"):
                raise _fail(line_no, "unterminated section header")
            head = line[1:-1].split()
            bar_units = bar_size()
            if head == ["arrangement"]:
                current, in_arrangement = None, True
            elif len(head) == 2 and head[0] == "section":
                if head[1] in sections:
                    raise _fail(line_no, f"duplicate section '{head[1]}'")
                current = sections[head[1]] = _Section(head[1])
                in_arrangement = False
            else:
                raise _fail(line_no, "expected [section NAME] or [arrangement]")
        elif in_arrangement:
            for token in line.split():
                found = REPEAT_RE.match(token)
                if found is None:
                    raise _fail(line_no, f"invalid arrangement entry '{token}'")
                arrangement.append((found.group(1), int(found.group(2) or 1), line_no))
        elif current is not None:
            name, sep, body = line.partition(":")
            name = name.strip()
            if not sep or name not in instruments:
                raise _fail(line_no, f"'{name}' is not a declared instrument")
            bars = _parse_bars(body, bar_units, line_no)
            if instruments[name].wave != "noise" and any(
                n.pitch is None for bar in bars for n in bar
            ):
                raise _fail(line_no, "X hits are only valid for noise instruments")
            current.voices.setdefault(name, []).extend(bars)
        elif line.startswith("instrument "):
            instrument = _parse_instrument(line[len("instrument ") :], line_no)
            if instrument.name in instruments:
                raise _fail(line_no, f"duplicate instrument '{instrument.name}'")
            instruments[instrument.name] = instrument
        else:
            key, sep, value = line.partition("=")
            if not sep:
                raise _fail(line_no, f"cannot understand '{line}'")
            _parse_meta(meta, key.strip().lower(), value.strip(), line_no)
    return _assemble(song_id, meta, instruments, sections, arrangement)


def _assemble(
    song_id: str,
    meta: _Meta,
    instruments: dict[str, Instrument],
    sections: dict[str, _Section],
    arrangement: list[tuple[str, int, int]],
) -> Song:
    if not instruments:
        raise SongError("the song declares no instruments")
    if not arrangement:
        raise SongError("the song has an empty or missing [arrangement]")
    bar_units = meta.meter[0] * UNITS_PER_WHOLE // meta.meter[1]
    parts: dict[str, list[Note]] = {name: [] for name in instruments}
    offset = 0
    for name, repeat, line_no in arrangement:
        section = sections.get(name)
        if section is None:
            raise _fail(line_no, f"unknown section '{name}'")
        if repeat < 1:
            raise _fail(line_no, "repeat count must be at least 1")
        for _ in range(repeat):
            for voice, bars in section.voices.items():
                for index, bar in enumerate(bars):
                    base = offset + index * bar_units
                    parts[voice].extend(Note(base + n.start, n.length, n.pitch) for n in bar)
            offset += section.bar_count * bar_units
    if offset == 0:
        raise SongError("the arrangement contains no bars")
    return Song(
        song_id=song_id,
        title=meta.title or song_id,
        artist=meta.artist,
        tempo=meta.tempo,
        beats_per_bar=meta.meter[0],
        beat_unit=meta.meter[1],
        volume=meta.volume,
        contexts=meta.contexts,
        instruments=instruments,
        parts={name: tuple(notes) for name, notes in parts.items() if notes},
        total_units=offset,
    )


def load_song(path: Path) -> Song:
    """@brief Read and parse one song file.
    @param path File to read; the stem becomes the song id.
    @return The parsed song.
    @throws SongError If the file is malformed (the message is prefixed with the file name).
    """
    try:
        return parse_song(path.read_text(encoding="utf-8"), path.stem)
    except SongError as error:
        raise SongError(f"{path.name}: {error}") from None
