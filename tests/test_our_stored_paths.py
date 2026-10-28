"""Our committed recordings and ledger rows store no absolute path; our renames all resolve.

Every path the tools write into a file is relative to the project root, or a file name for one
outside it (``stored_path``, glitchygames/replay/tools/settings.py). This checks what is
committed: each tracked recording's header and each tracked ledger row, every string in them at
any depth. An absolute path there (a POSIX root, a home directory, a Windows drive) would hold
a user name, a home or a scratch directory, and mean nothing on another machine. The recording
renames table (``[tool.glitchygames.recording-renames]``) is checked here too: each new path
exists.
"""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path

from glitchygames.process import OutputCapture, run_command
from glitchygames.replay.tools.settings import (
    is_absolute_path,
    load_project_settings,
    recording_renames_problems,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RECORDING_SUFFIX = '.jsonl.gz'
# How long listing the tracked files may take
GIT_TIMEOUT_SECONDS = 60.0
# Where our ledger's row files are ([tool.glitchygames] ledger-directory)
LEDGER_DIRECTORY = load_project_settings(project_root=PROJECT_ROOT).ledger_directory


def tracked_files() -> list[str]:
    """Return every file git tracks in this repository, relative to it.

    Returns:
        The paths.

    """
    completed = run_command(
        command=['git', 'ls-files', '-z'],
        environment=os.environ,
        working_directory=PROJECT_ROOT,
        capture_output=OutputCapture.APART,
        timeout_seconds=GIT_TIMEOUT_SECONDS,
    )
    return [name for name in completed.stdout.split('\0') if name]


def absolute_paths_in(*, value: object, where: str) -> list[str]:
    """Return every absolute path string in a JSON value, at any depth, with where it is.

    Args:
        value: The value.
        where: Its place so far (``header.options``).

    Returns:
        ``<place>: <path>`` lines.

    """
    if isinstance(value, dict):
        return [
            found
            for key, item in value.items()
            for found in absolute_paths_in(value=item, where=f'{where}.{key}')
        ]
    if isinstance(value, list):
        return [found for item in value for found in absolute_paths_in(value=item, where=where)]
    if isinstance(value, str) and is_absolute_path(text=value):
        return [f'{where}: {value}']
    return []


def test_no_tracked_recording_header_or_ledger_row_stores_an_absolute_path():
    """Every recording header and ledger row names paths relative to the project root."""
    found: list[str] = []
    checked = 0
    for name in tracked_files():
        if name.endswith(RECORDING_SUFFIX):
            with gzip.open(PROJECT_ROOT / name, 'rt', encoding='utf-8') as recording:
                header = json.loads(recording.readline())
            found += absolute_paths_in(value=header, where=f'{name} header')
            checked += 1
        elif name.startswith(f'{LEDGER_DIRECTORY}/') and name.endswith('.json'):
            row = json.loads((PROJECT_ROOT / name).read_text(encoding='utf-8'))
            found += absolute_paths_in(value=row, where=name)
            checked += 1

    assert checked
    assert found == []


def test_the_absolute_path_scan_finds_one_at_any_depth():
    """The scan reads nested tables and lists, and leaves relative paths alone."""
    row = {
        'recording': 'src/games/x/golden.jsonl.gz',
        'run': {'rebaselined_from': '/home/someone/golden.jsonl.gz'},
        'runs': [{'path': 'C:\\scratch\\a.jsonl.gz'}, 3, None],
    }

    assert absolute_paths_in(value=row, where='row') == [
        'row.run.rebaselined_from: /home/someone/golden.jsonl.gz',
        'row.runs.path: C:\\scratch\\a.jsonl.gz',
    ]


def test_every_recording_rename_ends_at_a_committed_recording():
    """Each new path in our renames table exists (and the table's shape was checked as read)."""
    settings = load_project_settings(project_root=PROJECT_ROOT)

    assert settings.recording_renames
    assert recording_renames_problems(settings=settings, project_root=PROJECT_ROOT) == []
