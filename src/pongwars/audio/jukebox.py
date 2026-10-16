"""@package pongwars.audio.jukebox
@brief Song library and playlist engine: plays songs back to back, rendering ahead in a thread.
"""

import logging
import os
import random
import sys
import threading
from array import array
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Protocol

import pygame

from pongwars.audio.sequencer import render_song
from pongwars.audio.songfile import SONG_SUFFIX, Song, SongError, load_song

logger = logging.getLogger(__name__)

MUSIC_DIR = Path(__file__).resolve().parent.parent / "data" / "music"


class Sink(Protocol):
    """@brief Destination for rendered songs (a mixer channel, or a fake in tests)."""

    def start(self, samples: "array[int]") -> None:
        """@brief Start playing a buffer from the beginning."""

    def busy(self) -> bool:
        """@brief True while a buffer is still playing."""

    def stop(self) -> None:
        """@brief Stop playback."""

    def set_volume(self, volume: float) -> None:
        """@brief Set the playback level (0-1)."""


class PygameSink:
    """@brief Plays songs on a reserved pygame mixer channel."""

    def __init__(self) -> None:
        """@brief Reserve channel 0 for music."""
        pygame.mixer.set_reserved(1)
        self._channel = pygame.mixer.Channel(0)
        self._volume = 1.0

    def start(self, samples: "array[int]") -> None:
        """@brief Start playing a buffer from the beginning.
        @param samples Signed 16-bit mono samples.
        """
        self._channel.play(pygame.mixer.Sound(buffer=samples.tobytes()))
        self._channel.set_volume(self._volume)

    def busy(self) -> bool:
        """@brief True while a buffer is still playing."""
        return bool(self._channel.get_busy())

    def stop(self) -> None:
        """@brief Stop playback."""
        self._channel.stop()

    def set_volume(self, volume: float) -> None:
        """@brief Set the playback level.
        @param volume Level 0-1.
        """
        self._volume = volume
        self._channel.set_volume(volume)


class Library:
    """@brief All songs found in a directory of `.pws` files."""

    def __init__(self, songs: dict[str, Song]) -> None:
        """@brief Wrap already parsed songs.
        @param songs Song id -> song.
        """
        self.songs = dict(sorted(songs.items()))

    @classmethod
    def load(cls, directory: Path = MUSIC_DIR) -> "Library":
        """@brief Parse every song file of a directory (broken files are logged and skipped).
        @param directory Folder with `.pws` files.
        @return The library.
        """
        songs: dict[str, Song] = {}
        for path in sorted(directory.glob(f"*{SONG_SUFFIX}")):
            try:
                songs[path.stem] = load_song(path)
            except SongError as error:
                logger.warning("Skipping song %s: %s", path.name, error)
        return cls(songs)

    def ids_for(self, context: str) -> list[str]:
        """@brief Ids of the songs allowed in a context, sorted.
        @param context `menu` or `match`.
        @return Song ids.
        """
        return [sid for sid, song in self.songs.items() if context in song.contexts]


def _lower_priority() -> None:
    """@brief Worker initializer: keep the renderer from competing with the game loop."""
    try:
        if sys.platform == "win32":
            import ctypes

            kernel = ctypes.windll.kernel32
            kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL
        else:
            os.nice(10)
    except (OSError, AttributeError):
        pass


def _render_in_worker(song: Song) -> bytes:
    """@brief Render a song inside the worker process.
    @param song Song to render.
    @return Raw 16-bit PCM bytes.
    """
    return render_song(song).tobytes()


class Jukebox:
    """@brief Plays random songs of a context with a silent gap between them, forever."""

    def __init__(
        self,
        library: Library,
        sink: Sink,
        renderer: Callable[[Song], "array[int]"] = render_song,
        threaded: bool = True,
        gap: tuple[float, float] = (2.0, 3.0),
    ) -> None:
        """@brief Create an idle jukebox.
        @param library Available songs.
        @param sink Where audio goes.
        @param renderer Song -> PCM function.
        @param threaded Render in a background thread (tests use False).
        @param gap Min and max seconds of silence between two songs.
        """
        self.library = library
        self.sink = sink
        self._renderer = renderer
        self._threaded = threaded
        self._gap_range = gap
        self._cache: dict[str, array[int]] = {}
        self._lock = threading.Lock()
        self._pool: ProcessPoolExecutor | None = None
        self._pool_ok = True
        self._closed = False
        self._pending: set[str] = set()
        self._rng = random.Random()  # noqa: S311 - not security related
        self._context = ""
        self._ids: list[str] = []
        self._last_played = ""
        self._last_by_context: dict[str, str] = {}
        self._next = ""
        self._gap = 0.0
        self.current = ""
        self._waiting = ""

    @property
    def context(self) -> str:
        """@brief Context being played, or an empty string when stopped."""
        return self._context

    def start(
        self,
        context: str,
        first: str | None = None,
        seed: int | None = None,
        avoid_previous: str = "",
    ) -> str:
        """@brief Start playing a context unless it is already playing.
        @param context `menu` or `match`.
        @param first Song to play first (it must be allowed in the context).
        @param seed Optional deterministic seed for the random order.
        @param avoid_previous Song id to exclude from the random first pick.
        @return The selected first song id, or an empty string when unavailable.
        """
        ids = self.library.ids_for(context)
        if not ids:
            self.stop()
            return ""
        if self._context == context and (first is None or first == self.current):
            return self.current or self._waiting
        self.sink.stop()
        if seed is not None:
            self._rng = random.Random(seed)  # noqa: S311 - not security related
        self._context, self._ids = context, ids
        self.current = self._waiting = ""
        self._gap = 0.0
        previous = self._last_by_context.get(context, "")
        excluded = {previous, self._last_played, avoid_previous}
        if first in ids and first not in excluded:
            selected = first
        else:
            selected = self._pick(previous, avoid_previous, self._last_played)
        self._begin(selected)
        return selected

    def stop(self) -> None:
        """@brief Stop playing and forget the context."""
        self.sink.stop()
        self._context = self.current = self._waiting = self._next = ""
        self._ids = []
        self._gap = 0.0

    def close(self) -> None:
        """@brief Stop playback and kill the render process so exit is immediate."""
        self.stop()
        self._closed = True
        pool, self._pool = self._pool, None
        if pool is not None:
            procs = list(getattr(pool, "_processes", {}).values())
            pool.shutdown(wait=False, cancel_futures=True)
            for proc in procs:
                proc.terminate()

    def update(self, dt: float = 0.0) -> None:
        """@brief Call every frame: handle the gap and start the next song.
        @param dt Seconds since the previous call.
        """
        if not self._context:
            return
        if self._waiting:
            if self._waiting in self._cache:
                self._play(self._waiting)
        elif self._gap > 0:
            self._gap -= dt
            if self._gap <= 0:
                self._begin(self._next)
        elif not self.sink.busy():
            self.current = ""
            self._gap = self._rng.uniform(*self._gap_range)
            if self._gap <= 0:
                self._begin(self._next)

    def _pick(
        self, previous: str = "", avoid_previous: str = "", last_played: str = ""
    ) -> str:
        """@brief Random song excluding recent context, global and caller-specified tracks."""
        excluded = {previous, avoid_previous, last_played}
        choices = [sid for sid in self._ids if sid not in excluded] or self._ids
        return self._rng.choice(choices)

    def _begin(self, song_id: str) -> None:
        self._waiting = song_id
        self._request(song_id)
        self._next = self._pick(song_id)
        self._request(self._next)
        if song_id in self._cache:
            self._play(song_id)

    def _play(self, song_id: str) -> None:
        self.current, self._waiting = song_id, ""
        self._last_played = song_id
        self._last_by_context[self._context] = song_id
        self.sink.start(self._cache[song_id])
        self._evict()

    def _evict(self) -> None:
        """@brief Drop rendered songs that are neither playing nor queued (bounds memory)."""
        keep = {self.current, self._waiting, self._next}
        with self._lock:
            for sid in [sid for sid in self._cache if sid not in keep]:
                del self._cache[sid]

    def _request(self, song_id: str) -> None:
        with self._lock:
            if song_id in self._cache or song_id in self._pending:
                return
            self._pending.add(song_id)
        if self._threaded:
            threading.Thread(target=self._render, args=(song_id,), daemon=True).start()
        else:
            self._render(song_id)

    def _render(self, song_id: str) -> None:
        song = self.library.songs[song_id]
        samples: array[int] | None = None
        if self._threaded and self._pool_ok and self._renderer is render_song:
            samples = self._render_in_process(song)
        if samples is None:
            samples = self._renderer(song)
        with self._lock:
            self._cache[song_id] = samples
            self._pending.discard(song_id)

    def _render_in_process(self, song: Song) -> "array[int] | None":
        """@brief Render in a worker process so the game loop never shares its GIL.
        @param song Song to render.
        @return PCM, or None when processes are unavailable (caller falls back to a thread).
        """
        try:
            with self._lock:
                if self._pool is None:
                    self._pool = ProcessPoolExecutor(max_workers=1, initializer=_lower_priority)
                pool = self._pool
            data = pool.submit(_render_in_worker, song).result()
        except Exception:  # noqa: BLE001 - any pool failure just disables the pool
            if not self._closed:
                logging.getLogger(__name__).warning("Render process unavailable, using a thread")
            self._pool_ok = False
            return None
        samples = array("h")
        samples.frombytes(data)
        return samples
