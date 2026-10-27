#!/usr/bin/env python3
"""Move the run ledger published on gh-pages into the repository's row files, once.

The measured rows used to be kept on gh-pages (``quality/metrics/replay-ledger.jsonl``); since
plans/2026-10-25-measured-rows-in-the-repository.md they live in the repository, one file per
row under ``quality/replay-ledger/``. This writes every published row the repository does not
hold yet as its own row file (by the row's key, so running it again adds nothing); commit the
files it writes. Run 2026-10-25: 18 rows. The docs build still merges whatever gh-pages holds,
so a row published from elsewhere later is not lost.

Usage:
    uv run python scripts/import_published_ledger.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from glitchygames.recording_metrics import (
    parse_ledger,
    published_ledger_text,
    read_row_files,
    write_row_files,
)
from glitchygames.replay.tools.settings import load_project_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# This repository's [tool.glitchygames]: where the ledger is published and the rows are kept
PROJECT_SETTINGS = load_project_settings(project_root=PROJECT_ROOT)


def import_published_ledger(*, project_root: Path, rows_directory: Path) -> list[Path]:
    """Write the published rows the repository lacks as row files.

    Args:
        project_root: The repository (its ``origin/gh-pages`` holds the published ledger).
        rows_directory: Where the row files go.

    Returns:
        The files written.

    """
    held = {row.key for row in read_row_files(directory=rows_directory)}
    published = parse_ledger(
        text=published_ledger_text(
            project_root=project_root, published_ledger=PROJECT_SETTINGS.published_ledger
        )
    ).rows
    return write_row_files(
        rows=[row for row in published if row.key not in held], directory=rows_directory
    )


def main() -> None:
    """Import the published rows into this repository's ledger directory."""
    ledger_directory = PROJECT_SETTINGS.ledger_directory
    written = import_published_ledger(
        project_root=PROJECT_ROOT, rows_directory=PROJECT_ROOT / ledger_directory
    )
    sys.stdout.write(f'Imported {len(written)} published rows into {ledger_directory}/\n')


if __name__ == '__main__':
    main()
