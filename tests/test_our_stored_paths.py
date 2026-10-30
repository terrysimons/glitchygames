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
import sys
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


def is_ledger_row(*, value: object) -> bool:
    """Tell whether a JSON value is shaped like a ledger row: a ``recording`` and a ``run``.

    Rows live in the ledger directory, but pinned copies of them live elsewhere too (a test's
    fixture, ``tests/fixtures/provenance/``), so rows are recognized by shape, not by place.

    Args:
        value: The value.

    Returns:
        True for a table with a string ``recording`` and a table ``run``.

    """
    return (
        isinstance(value, dict)
        and isinstance(value.get('recording'), str)
        and isinstance(value.get('run'), dict)
    )


def tracked_json_values(*, name: str) -> list[object]:
    """Return the JSON values a tracked ``.json`` or ``.jsonl`` file holds (none if not JSON).

    Args:
        name: The file, relative to the repository.

    Returns:
        The whole file's value for ``.json``, each line's for ``.jsonl``.

    """
    text = (PROJECT_ROOT / name).read_text(encoding='utf-8')
    try:
        if name.endswith('.jsonl'):
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        return [json.loads(text)]
    except json.JSONDecodeError:
        return []


def test_no_tracked_recording_header_or_ledger_row_stores_an_absolute_path():
    """Every recording header and ledger row, wherever tracked, names paths relatively."""
    found: list[str] = []
    rows_checked = 0
    recordings_checked = 0
    for name in tracked_files():
        if name.endswith(RECORDING_SUFFIX):
            with gzip.open(PROJECT_ROOT / name, 'rt', encoding='utf-8') as recording:
                header = json.loads(recording.readline())
            found += absolute_paths_in(value=header, where=f'{name} header')
            recordings_checked += 1
        elif name.endswith(('.json', '.jsonl')):
            for value in tracked_json_values(name=name):
                if is_ledger_row(value=value):
                    found += absolute_paths_in(value=value, where=name)
                    rows_checked += 1

    assert recordings_checked
    assert rows_checked
    assert found == []


def test_rows_are_recognized_by_shape_wherever_they_are():
    """A table with a recording and a run is a row; other JSON is not."""
    assert is_ledger_row(value={'recording': 'a.jsonl.gz', 'run': {}})
    assert not is_ledger_row(value={'recording': 'a.jsonl.gz'})
    assert not is_ledger_row(value={'recording': 3, 'run': {}})
    assert not is_ledger_row(value=['recording', 'run'])


def test_tracked_json_is_read_whole_or_by_line(tmp_path, mocker):
    """A .json file is one value, a .jsonl file one per line; a file that is no JSON, none."""
    mocker.patch.object(sys.modules[__name__], 'PROJECT_ROOT', tmp_path)
    (tmp_path / 'row.json').write_text('{"a": 1}', encoding='utf-8')
    (tmp_path / 'rows.jsonl').write_text('{"a": 1}\n\n{"b": 2}\n', encoding='utf-8')
    (tmp_path / 'broken.json').write_text('{not json', encoding='utf-8')

    assert tracked_json_values(name='row.json') == [{'a': 1}]
    assert tracked_json_values(name='rows.jsonl') == [{'a': 1}, {'b': 2}]
    assert tracked_json_values(name='broken.json') == []


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
    """Each new path in our renames table is a committed recording; no old path is committed.

    The table's shape was checked as read (no new path is also an old one: lookups take one
    hop), and ``recording_renames_problems`` checks the files on disk; this checks what git
    holds, so a new path that exists only in this checkout, or an old one still committed, fails.
    """
    settings = load_project_settings(project_root=PROJECT_ROOT)
    tracked = set(tracked_files())

    assert settings.recording_renames
    assert recording_renames_problems(settings=settings, project_root=PROJECT_ROOT) == []
    assert not set(settings.recording_renames.values()) & set(settings.recording_renames)
    assert sorted(set(settings.recording_renames.values()) - tracked) == []
    assert all(target.endswith(RECORDING_SUFFIX) for target in settings.recording_renames.values())
    assert sorted(set(settings.recording_renames) & tracked) == []
