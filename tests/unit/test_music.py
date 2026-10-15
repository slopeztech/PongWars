"""Tests for the .pws song format, the sequencer and the jukebox."""

import os
from array import array

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

from pongwars.audio.jukebox import Jukebox, Library
from pongwars.audio.sequencer import render_song
from pongwars.audio.songfile import SongError, parse_note_token, parse_song

BASIC = """
title = Test
tempo = 120
meter = 4/4
use = any
instrument lead = square volume=0.5
instrument drum = noise
[section a]
lead: | C4:4 D4:4 E4:4 F4:4 | G4:1 |
drum: | X:4 R:4 X:4 R:4 | R:1 |
[arrangement]
a*2
"""


def test_note_tokens() -> None:
    assert parse_note_token("A4:4", 4) == (0, 16, 4)
    assert parse_note_token("A5:4", 4)[0] == 12
    assert parse_note_token("C#4:8", 4)[0] == parse_note_token("Db4:8", 4)[0]
    assert parse_note_token("R:2.", 4) == (None, 48, 2)
    assert parse_note_token("E4", 8) == (parse_note_token("E4:8", 4)[0], 8, 8)
    with pytest.raises(SongError):
        parse_note_token("H4:4", 4)
    with pytest.raises(SongError):
        parse_note_token("C4:5", 4)


def test_parse_song_structure() -> None:
    song = parse_song(BASIC, "test")
    assert song.title == "Test"
    assert song.tempo == 120
    assert set(song.parts) == {"lead", "drum"}
    assert song.total_units == 2 * 2 * 64
    assert song.duration == pytest.approx(8.0)
    assert song.contexts == ("menu", "match")
    assert len(song.parts["lead"]) == 2 * 5


@pytest.mark.parametrize(
    "mutation",
    [
        ("C4:4 D4:4 E4:4 F4:4 | G4:1", "C4:4 D4:4 E4:4 | G4:1"),
        ("lead: |", "ghost: |"),
        ("a*2", "missing"),
        ("meter = 4/4", "meter = 4/5"),
        ("use = any", "use = lobby"),
        ("instrument lead = square", "instrument lead = banjo"),
        ("X:4 R:4 X:4 R:4", "X:4 R:4 X:4 R:4 R:4"),
    ],
)
def test_parse_errors(mutation: tuple[str, str]) -> None:
    with pytest.raises(SongError):
        parse_song(BASIC.replace(*mutation))


def test_unpitched_hit_needs_noise_instrument() -> None:
    with pytest.raises(SongError):
        parse_song(BASIC.replace("lead: | C4:4", "lead: | X:4 R:4 R:2 | C4:4"))


def test_meters_and_comments() -> None:
    text = (
        "# c\nmeter = 6/8\ninstrument l = triangle # inline\n"
        "[section a]\nl: | C4:4. D4:4. |\n[arrangement]\na\n"
    )
    song = parse_song(text)
    assert (song.beats_per_bar, song.beat_unit) == (6, 8)
    assert song.total_units == 48


def test_render_song_length_and_signal() -> None:
    song = parse_song(BASIC)
    pcm = render_song(song, 8000)
    assert abs(len(pcm) - int(8.0 * 8000)) < 8000 // 2
    assert max(pcm) > 0
    assert max(abs(s) for s in pcm) <= 32767


class FakeSink:
    def __init__(self) -> None:
        self.started: list[int] = []
        self.playing = False
        self.volume = 1.0

    def start(self, samples: "array[int]") -> None:
        self.started.append(len(samples))
        self.playing = True

    def busy(self) -> bool:
        return self.playing

    def stop(self) -> None:
        self.playing = False

    def set_volume(self, volume: float) -> None:
        self.volume = volume


def make_jukebox() -> tuple[Jukebox, FakeSink, Library]:
    songs = {
        "m": parse_song(BASIC.replace("use = any", "use = menu"), "m"),
        "a": parse_song(BASIC.replace("use = any", "use = match"), "a"),
        "b": parse_song(BASIC, "b"),
    }
    sink = FakeSink()
    library = Library(songs)
    renderer = lambda song: array("h", [len(song.song_id)] * 4)  # noqa: E731
    return Jukebox(library, sink, renderer, threaded=False), sink, library


def test_library_contexts() -> None:
    _, _, library = make_jukebox()
    assert library.ids_for("menu") == ["b", "m"]
    assert library.ids_for("match") == ["a", "b"]


def test_jukebox_random_order_gap_and_no_repeat() -> None:
    box, sink, _ = make_jukebox()
    box.start("match", first="b", seed=3)
    assert box.current == "b"
    box.update()
    assert len(sink.started) == 1
    previous = "b"
    for _ in range(12):
        sink.playing = False
        box.update(0.0)
        assert box.current == ""  # silence between songs
        assert 2.0 <= box._gap <= 3.0
        box.update(1.0)
        assert box.current == ""
        box.update(2.1)
        assert box.current in {"a", "b"} and box.current != previous
        previous = box.current


def test_now_playing_is_none_during_gap() -> None:
    box, sink, _ = make_jukebox()
    box.start("menu", first="m", seed=1)
    box.update()
    assert box.current == "m"
    sink.playing = False
    box.update(0.0)
    assert box.current == ""


def test_jukebox_restart_is_a_no_op_and_stop_clears() -> None:
    box, sink, _ = make_jukebox()
    box.start("menu")
    count = len(sink.started)
    box.start("menu")
    assert len(sink.started) == count
    box.start("match", first="nope")
    assert box.context == "match"
    box.stop()
    assert box.context == "" and not sink.playing
    box.update()


def test_bundled_songs_are_valid() -> None:
    library = Library.load()
    assert len(library.songs) >= 30
    assert len(library.ids_for("menu")) >= 8
    assert len(library.ids_for("match")) >= 20
    for song in library.songs.values():
        assert song.title and song.duration > 150
