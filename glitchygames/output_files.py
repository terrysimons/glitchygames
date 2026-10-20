"""Files a run writes as its output: checked before the run starts, written whole.

- ``output_refusal``: why an output file cannot be written, asked before a run starts
  (``--record-trace``'s recording, ``--rebaseline``'s partial file, ``--replay-digest``'s digest
  file), so the engine refuses it with ``ExitCode.CANNOT_WRITE_OUTPUT`` and one line before any
  game code runs, instead of failing part way with a traceback. It creates the parent
  directories (as the writers do) and opens the file for appending; a file the check created
  is removed again, so nothing is left behind.
- ``partial_path``: the file an output is written to before it is moved into place
  (``<name>.partial``, next to it).
- ``write_aside_then_replace``: writes an output whole: to its partial file, then moved into
  place, so the destination is never left half written (a watched replay's restart handoff,
  glitchygames/replay/rebuild.py; a bookmarked copy, glitchygames/replay/driver.py). A
  rebaseline writes its partial file over the whole run and moves it once the run is over
  (glitchygames/replay/rebaseline.py), with the same ``partial_path``.

This module is a leaf: it imports only the standard library.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

# The suffix of the file an output is written to before it is moved into place
PARTIAL_SUFFIX = '.partial'


def partial_path(*, destination: Path) -> Path:
    """Name the file an output is written to before it is moved into place.

    Args:
        destination: The output's file.

    Returns:
        ``<destination>.partial``, next to it.

    """
    return destination.with_name(destination.name + PARTIAL_SUFFIX)


def write_aside_then_replace(*, destination: Path, write: Callable[[Path], object]) -> None:
    """Write an output to its partial file, then move it into place.

    The partial file is removed whatever happens, so a failed write leaves the destination as
    it was (absent, or its earlier contents) and no partial file behind; the error (an OSError
    when the partial file cannot be written or moved into place) propagates.

    Args:
        destination: The output's file.
        write: Writes the whole output to the path it is given (what it returns is ignored).

    """
    aside = partial_path(destination=destination)
    try:
        write(aside)
        aside.replace(destination)
    finally:
        aside.unlink(missing_ok=True)


def output_refusal(*, path: Path) -> str | None:
    """Say why an output file cannot be written, before the run that writes it starts.

    Args:
        path: The output's file.

    Returns:
        The reason (one line, naming the path), or None when the file can be written.

    """
    if path.is_dir():
        return f'{path} is a directory'
    existed = path.exists()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('ab'):
            pass
    except OSError as error:
        return f'{path} cannot be written ({error.strerror or error})'
    if not existed:
        path.unlink(missing_ok=True)
    return None
