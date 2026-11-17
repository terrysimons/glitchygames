"""Where the listening WAVs go and how they are written (the listening package's rules).

plans/2026-11-14-sound-cache-on-first-use.md, decision 5: rendered for people to listen to (an
instrument's range, a timbre by ear), never by a game. Moved from ``scripts/`` into the engine so
the ``listening-instruments`` and ``listening-pipes`` tools (and GG Sound Studio) can render them
anywhere the engine is installed.

Rules:

1. They live in the cache root's own folder for them, ``<root>/listening/<render version>/``
   (``listening_directory``): ``instruments/<family>/<name>.wav`` with ``instruments/index.txt``,
   ``pipes/<demo>.wav`` and ``pipes/tunes/<tune>.wav``. At about 300 MB they would flush a game's
   64 MB sound cache, so they have no size limit and nothing prunes them; only ``clear`` removes
   them. A render version names what compiled them, so a file there is never stale.
2. A render writes only the files missing (``write_missing``), and reports each file, written or
   already kept, so a tool can print where to find it.
3. Every file is 16-bit mono PCM at 44100 Hz, written by the engine's one WAV writer
   (``offline.write_wave_file``).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from glitchygames.audio.disk_cache import LISTENING_FOLDER
from glitchygames.audio.offline import write_wave_file
from glitchygames.audio.spec import AUDIO_RENDER_VERSION

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    import numpy as np
    import numpy.typing as npt

INSTRUMENTS_FOLDER = 'instruments'
PIPES_FOLDER = 'pipes'
TUNES_FOLDER = 'tunes'
WAVE_SUFFIX = '.wav'
SAMPLE_RATE = 44100


class ListeningReport(BaseModel):
    """What a render found and did (rule 2).

    Attributes:
        written: The files written now, in order.
        already_kept: The files that were there already, in order.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    written: tuple[Path, ...]
    already_kept: tuple[Path, ...]


def listening_directory(*, root: Path | str) -> Path:
    """Return the listening folder for this engine's render version (rule 1).

    Args:
        root: The cache root (``disk_cache.sound_cache_root``), a path or its text.

    Returns:
        ``<root>/listening/<render version>``.
    """
    return Path(root) / LISTENING_FOLDER / str(AUDIO_RENDER_VERSION)


def write_missing(
    *, files: Mapping[Path, Callable[[], npt.NDArray[np.float64]]]
) -> ListeningReport:
    """Render and write each file that is missing (rules 2 and 3).

    Args:
        files: Each file and what renders its mono samples, in the order to report them.

    Returns:
        What was written and what was there already.
    """
    written: list[Path] = []
    already_kept: list[Path] = []
    for path, render in files.items():
        if path.is_file():
            already_kept.append(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        write_wave_file(path, render(), sample_rate=SAMPLE_RATE, sample_format='int16')
        written.append(path)
    return ListeningReport(written=tuple(written), already_kept=tuple(already_kept))
