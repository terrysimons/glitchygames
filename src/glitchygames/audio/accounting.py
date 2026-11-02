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
# The gameplay compiles kept by name for diagnostics (the counts cover all of them)
GAMEPLAY_COMPILE_LOG_LENGTH: Final[int] = 32
# How many of a setup's slowest sounds its report names (impl spec 6.5)
SLOWEST_SETUP_COMPILES_NAMED: Final[int] = 3
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
    """Adds up a frame's audio work and counts the compiles, setup apart from gameplay.

    The audio engine sets ``frame_number`` each frame and ``setup_mode`` from a scene's setup to
    its first logic frame: compiles before the first logic frame are setup, later ones belong to
    their frame. Compiles and decodes are counted; the last eight are kept in the compile log,
    the last 32 gameplay ones by name, and a setup's total and slowest sounds until the engine
    takes them (``take_setup_compiles``, impl spec 6.5).

    Attributes:
        frame_number: The frame being run, or None.
        setup_mode: Whether compiles are attributed to setup (True until the first logic frame).
        setup_compile_count: Compiles and decodes run in setup.
        setup_compile_milliseconds: Their total time.
        gameplay_compile_count: Compiles and decodes run in gameplay frames.
        gameplay_compile_milliseconds: Their total time.
    """

    def __init__(self) -> None:
        """Start with an empty frame, an empty compile log and no compiles counted."""
        self.frame_number: int | None = None
        self.setup_mode: bool = True
        self.setup_compile_count = 0
        self.setup_compile_milliseconds = 0.0
        self.gameplay_compile_count = 0
        self.gameplay_compile_milliseconds = 0.0
        self._pieces: list[tuple[str, str, int]] = []  # (kind, name, nanoseconds)
        self._compile_log: deque[CompileRecord] = deque(maxlen=COMPILE_LOG_LENGTH)
        self._gameplay_compiles: deque[CompileRecord] = deque(maxlen=GAMEPLAY_COMPILE_LOG_LENGTH)
        # The setup since the last take_setup_compiles: its total and its slowest compiles
        self._setup_tally_milliseconds = 0.0
        self._slowest_setup_compiles: list[CompileRecord] = []

    @property
    def compile_log(self) -> tuple[CompileRecord, ...]:
        """The last eight compiles and decodes, oldest first."""
        return tuple(self._compile_log)

    @property
    def gameplay_compiles(self) -> tuple[CompileRecord, ...]:
        """The last 32 compiles and decodes run in gameplay frames, oldest first."""
        return tuple(self._gameplay_compiles)

    @property
    def compile_count(self) -> int:
        """Every compile and decode so far, setup and gameplay."""
        return self.setup_compile_count + self.gameplay_compile_count

    def take_setup_compiles(self) -> tuple[float, tuple[CompileRecord, ...]]:
        """Return the setup compiles' total and slowest since the last call, and start afresh.

        Returns:
            The total milliseconds, and the slowest compiles (at most three), slowest first.
        """
        taken = (self._setup_tally_milliseconds, tuple(self._slowest_setup_compiles))
        self._setup_tally_milliseconds = 0.0
        self._slowest_setup_compiles = []
        return taken

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
                self._count_compile(
                    CompileRecord(
                        frame_number=self.frame_number,
                        name=name,
                        milliseconds=elapsed / NANOSECONDS_PER_MILLISECOND,
                        during_setup=self.setup_mode,
                    )
                )

    def _count_compile(self, record: CompileRecord) -> None:
        """Log a compile or decode and count it as setup or gameplay work."""
        self._compile_log.append(record)
        if record.during_setup:
            self.setup_compile_count += 1
            self.setup_compile_milliseconds += record.milliseconds
            self._setup_tally_milliseconds += record.milliseconds
            slowest = sorted(
                [*self._slowest_setup_compiles, record],
                key=lambda kept: kept.milliseconds,
                reverse=True,
            )
            self._slowest_setup_compiles = slowest[:SLOWEST_SETUP_COMPILES_NAMED]
        else:
            self.gameplay_compile_count += 1
            self.gameplay_compile_milliseconds += record.milliseconds
            self._gameplay_compiles.append(record)

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
