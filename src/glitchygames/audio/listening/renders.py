"""Render the listening WAVs into their folder: what the tools and the Studio call.

Each renders only the files missing (glitchygames/audio/listening/files.py, rule 2) and reports
every file it covered, written or kept, so ``listening-instruments`` and ``listening-pipes`` print
where to find them.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from glitchygames.audio import instruments
from glitchygames.audio.listening.files import (
    INSTRUMENTS_FOLDER,
    PIPES_FOLDER,
    TUNES_FOLDER,
    WAVE_SUFFIX,
    ListeningReport,
    listening_directory,
    write_missing,
)
from glitchygames.audio.listening.instrument_demos import index_line, instrument_demo
from glitchygames.audio.listening.pipe_tunes import tune_entries, tune_name, tune_samples
from glitchygames.audio.listening.pipes import PIPE_DEMOS

if TYPE_CHECKING:
    from pathlib import Path

# Every instrument, its family and its range: written by an unfiltered render
INSTRUMENT_INDEX_FILE = 'index.txt'


def render_instruments(
    *, root: Path | str, family: instruments.Family | None = None, only: str = ''
) -> ListeningReport:
    """Render each catalog instrument's demo that is missing (``instrument_demos``).

    Args:
        root: The cache root.
        family: Only this family's instruments; None for every family.
        only: Only instruments whose name contains this text.

    Returns:
        Each file covered, written or already kept. An unfiltered render also writes
        ``index.txt`` (every instrument, its family and its range), as the script did.
    """
    directory = listening_directory(root=root) / INSTRUMENTS_FOLDER
    chosen = [
        entry
        for entry in instruments.entries()
        if only in entry.name and (family is None or entry.family is family)
    ]
    report = write_missing(
        files={
            directory / entry.family.value / f'{entry.name}{WAVE_SUFFIX}': partial(
                instrument_demo, entry
            )
            for entry in chosen
        }
    )
    if family is None and not only:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / INSTRUMENT_INDEX_FILE).write_text(
            '\n'.join(index_line(entry) for entry in chosen) + '\n', encoding='utf-8'
        )
    return report


def render_pipes(*, root: Path | str, only: str = '') -> ListeningReport:
    """Render each pipe demo and pipe tune that is missing (``pipes``, ``pipe_tunes``).

    Args:
        root: The cache root.
        only: Only demos and tunes whose file name contains this text.

    Returns:
        Each file covered, written or already kept: the demos, then the tunes.
    """
    directory = listening_directory(root=root) / PIPES_FOLDER
    files = {
        directory / f'{name}{WAVE_SUFFIX}': render
        for name, render in PIPE_DEMOS.items()
        if only in name
    }
    files.update({
        directory / TUNES_FOLDER / f'{tune_name(entry)}{WAVE_SUFFIX}': partial(tune_samples, entry)
        for entry in tune_entries()
        if only in tune_name(entry)
    })
    return write_missing(files=files)
