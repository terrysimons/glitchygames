"""Writes cut short part way, as a Ctrl-C, a kill or a power cut leaves them.

``with cut_writes_short(mocker=..., characters=N):`` makes every file opened for writing through
``Path.open`` (which ``Path.write_text`` uses too) in the block take only its first ``N``
characters, then raise ``KeyboardInterrupt`` from the write that would pass them: what was
written stays on disk, as it would after the process was stopped there. Files opened for reading
are untouched, and the patch ends with the block, even when the block raises.

Used by the tests that a durable record (a ledger row file, the pending ledger) is written whole
or not at all (bugs/2026-11-20-ledger-row-writes-are-not-atomic.md).
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from collections.abc import Generator
    from types import TracebackType

    from pytest_mock import MockerFixture

# The modes that write: a file opened in one of them is cut short
WRITING_MODE_CHARACTERS = frozenset('wax+')


class CutShortFile:
    """A file that takes its first ``characters`` characters, then is interrupted."""

    def __init__(self, *, stream: IO[Any], characters: int) -> None:
        """Wrap an open file.

        Args:
            stream: The real file, open for writing.
            characters: How many characters it takes before the interruption.

        """
        self.stream = stream
        self.remaining = characters

    def __enter__(self) -> Self:
        """Return the file itself, as an open file does.

        Returns:
            This file.

        """
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the real file, keeping what it took."""
        self.stream.close()

    def write(self, text: str) -> int:
        """Write what is left of the allowance, then interrupt if the text did not fit.

        Returns:
            The text's length, when all of it fitted.

        Raises:
            KeyboardInterrupt: When the text passed the allowance (what fitted is on disk).

        """
        allowed = text[: self.remaining]
        self.stream.write(allowed)
        self.remaining -= len(allowed)
        if len(allowed) < len(text):
            self.stream.flush()
            raise KeyboardInterrupt
        return len(text)

    def __getattr__(self, name: str) -> object:
        """Pass anything else (flush, fileno, close) to the real file.

        Returns:
            The real file's attribute.

        """
        return getattr(self.stream, name)


@contextlib.contextmanager
def cut_writes_short(*, mocker: MockerFixture, characters: int) -> Generator[None]:
    """Cut every write through ``Path.open`` short after ``characters`` characters, in the block.

    The patch ends with the block, even when the block raises: a test that fails inside it still
    makes its teardown writes whole (the harness's failure records), and its KeyboardInterrupt
    never reaches them.

    Args:
        mocker: The test's mocker.
        characters: How many characters each file opened for writing takes.

    Yields:
        Nothing: the block runs with writes cut short.

    """
    real_open = Path.open

    def open_cut_short(
        self: Path, mode: str = 'r', *arguments: Any, **keywords: Any
    ) -> IO[Any] | CutShortFile:
        stream = real_open(self, mode, *arguments, **keywords)
        if WRITING_MODE_CHARACTERS.isdisjoint(mode):
            return stream
        return CutShortFile(stream=stream, characters=characters)

    patch = mocker.patch.object(Path, 'open', autospec=True, side_effect=open_cut_short)
    try:
        yield
    finally:
        mocker.stop(patch)
