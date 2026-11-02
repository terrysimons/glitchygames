"""Per-frame audio accounting: what audio work a frame did, and the last few compiles.

The sound library wraps each compile, file decode, live chunk and cache read in
``AudioAccountant.measure``. At the end of each frame the engine takes the frame's account
(``take_frame``) and hands it to the recording doors as ``audio_seconds`` and ``audio_work``
(impl spec 11.0). The times are measurements only: they never change what is drawn or played.
"""

from __future__ import annotations

import contextlib
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from glitchygames import clock

if TYPE_CHECKING:
    from collections.abc import Generator

MAXIMUM_WORK_ENTRIES: Final[int] = 32
COMPILE_LOG_LENGTH: Final[int] = 8
NANOSECONDS_PER_MICROSECOND: Final[int] = 1000
NANOSECONDS_PER_MILLISECOND: Final[int] = 1_000_000
NANOSECONDS_PER_SECOND: Final[int] = 1_000_000_000
# The kinds of work that make a sound (and so appear in the compile log)
COMPILE_KINDS: Final[tuple[str, ...]] = ('compile', 'decode')
OTHER_KIND: Final[str] = 'other'


@dataclass(frozen=True, slots=True)
class AudioFrameAccount:
    """One frame's audio work.

    Attributes:
        audio_seconds: The total time of every piece of work.
        audio_work: ``(kind, name, microseconds)`` per piece, at most 32; when there were more,
            the last entry is ``('other', '', microseconds)`` summing the rest.
    """

    audio_seconds: float
    audio_work: tuple[tuple[str, str, int], ...]


@dataclass(frozen=True, slots=True)
class CompileRecord:
    """One compile or decode, kept in the accountant's short log.

    Attributes:
        frame_number: The frame that asked for it, or None when no frame was set (setup).
        name: The sound's name.
        milliseconds: How long it took.
        during_setup: Whether it ran before the scene's first logic frame.
    """

    frame_number: int | None
    name: str
    milliseconds: float
    during_setup: bool


class AudioAccountant:
    """Adds up a frame's audio work and remembers the last eight compiles.

    The engine sets ``frame_number`` and ``setup_mode`` (Task 8): compiles before the first logic
    frame are setup, later ones belong to their frame.

    Attributes:
        frame_number: The frame being run, or None.
        setup_mode: Whether compiles are attributed to setup (True until the first logic frame).
    """

    def __init__(self) -> None:
        """Start with an empty frame and an empty compile log."""
        self.frame_number: int | None = None
        self.setup_mode: bool = True
        self._pieces: list[tuple[str, str, int]] = []  # (kind, name, nanoseconds)
        self._compile_log: deque[CompileRecord] = deque(maxlen=COMPILE_LOG_LENGTH)

    @property
    def compile_log(self) -> tuple[CompileRecord, ...]:
        """The last eight compiles and decodes, oldest first."""
        return tuple(self._compile_log)

    @contextlib.contextmanager
    def measure(self, kind: str, name: str) -> Generator[None]:
        """Time a piece of audio work (two raw counter reads) and add it to the frame.

        Args:
            kind: ``'compile'``, ``'decode'``, ``'live_chunk'`` or ``'cache_read'``.
            name: The sound the work was for.

        Yields:
            Nothing; the work runs inside the ``with`` block.
        """
        started = clock.raw_counter_ns()
        try:
            yield
        finally:
            elapsed = clock.raw_counter_ns() - started
            self._pieces.append((kind, name, elapsed))
            if kind in COMPILE_KINDS:
                self._compile_log.append(
                    CompileRecord(
                        frame_number=self.frame_number,
                        name=name,
                        milliseconds=elapsed / NANOSECONDS_PER_MILLISECOND,
                        during_setup=self.setup_mode,
                    )
                )

    def take_frame(self) -> AudioFrameAccount:
        """Return the frame's account and start a new one.

        Returns:
            The account; the compile log is kept.
        """
        pieces = self._pieces
        self._pieces = []
        total_nanoseconds = sum(nanoseconds for _, _, nanoseconds in pieces)
        kept = pieces if len(pieces) <= MAXIMUM_WORK_ENTRIES else pieces[: MAXIMUM_WORK_ENTRIES - 1]
        work = [
            (kind, name, nanoseconds // NANOSECONDS_PER_MICROSECOND)
            for kind, name, nanoseconds in kept
        ]
        if len(kept) < len(pieces):
            rest_nanoseconds = sum(nanoseconds for _, _, nanoseconds in pieces[len(kept) :])
            work.append((OTHER_KIND, '', rest_nanoseconds // NANOSECONDS_PER_MICROSECOND))
        return AudioFrameAccount(
            audio_seconds=total_nanoseconds / NANOSECONDS_PER_SECOND, audio_work=tuple(work)
        )
