"""Every path the tools write into a file is relative to the project root (D15 item 4).

``stored_path`` (glitchygames/replay/tools/settings.py) is the one rule: a path inside the
project is stored relative to its root, POSIX-style; one outside it, or with no project, as its
file name only. A recording's header stores its path options that way (``stored_options``), and
a rebaseline its ``rebaselined_from``, in the header and in its newest run (the run a ledger row
copies). The recording renames table is checked here too.
"""

from __future__ import annotations

import gzip
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from glitchygames.engine.game_engine import stored_options
from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, run_command
from glitchygames.replay.tools.settings import (
    ProjectSettings,
    ProjectSettingsError,
    is_absolute_path,
    load_project_settings,
    recording_renames_problems,
    stored_path,
)
from tests.stand_in_games import record_stand_in_game, use_stand_in_game, write_stand_in_game

# How long a stand-in game's rebaseline may run
CHILD_TIMEOUT_SECONDS = 120.0


def write_project(*, directory: Path) -> Path:
    """Make ``directory`` a project (a pyproject.toml with a [tool.glitchygames] table).

    Returns:
        The directory.

    """
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'pyproject.toml').write_text(
        '[project]\nname = "space-game"\n\n[tool.glitchygames]\n', encoding='utf-8'
    )
    return directory


def recording_header(*, path: Path) -> dict[str, Any]:
    """Return a recording's header line, parsed.

    Returns:
        The header.

    """
    with gzip.open(path, 'rt', encoding='utf-8') as recording:
        return json.loads(recording.readline())


def test_a_path_inside_the_project_is_stored_relative_to_its_root(tmp_path, monkeypatch):
    """Absolute or relative to the current directory, it is stored from the root, POSIX-style."""
    project = write_project(directory=tmp_path / 'project')
    (project / 'runs').mkdir()
    monkeypatch.chdir(project / 'runs')

    assert stored_path(path=project / 'runs' / 'a.jsonl.gz', project_root=project) == (
        'runs/a.jsonl.gz'
    )
    assert stored_path(path='b.jsonl.gz', project_root=project) == 'runs/b.jsonl.gz'
    assert stored_path(path='../c.jsonl.gz', project_root=project) == 'c.jsonl.gz'


def test_a_path_outside_the_project_or_with_no_project_is_its_file_name(tmp_path):
    """No user name, home or scratch directory is ever written: only the file's name."""
    project = write_project(directory=tmp_path / 'project')
    elsewhere = tmp_path / 'scratch' / 'session.jsonl.gz'

    assert stored_path(path=elsewhere, project_root=project) == 'session.jsonl.gz'
    assert stored_path(path=elsewhere, project_root=None) == 'session.jsonl.gz'


def write_checkout(*, directory: Path, name: str) -> Path:
    """Make ``directory`` a checkout of the project ``name``, with a member of another name inside.

    Returns:
        The directory.

    """
    write_project(directory=directory)
    (directory / 'pyproject.toml').write_text(
        f'[project]\nname = "{name}"\n\n[tool.glitchygames]\n', encoding='utf-8'
    )
    member = directory / 'src' / 'games' / 'mr-muncher'
    member.mkdir(parents=True)
    (member / 'pyproject.toml').write_text('[project]\nname = "mr-muncher"\n', encoding='utf-8')
    return directory


def test_a_path_in_another_checkout_of_the_project_is_relative_to_that_checkout(tmp_path):
    """A recording in another clone of this project keeps its path in the project."""
    project = write_checkout(directory=tmp_path / 'project', name='space-game')
    other_checkout = write_checkout(directory=tmp_path / 'space-game-wasm', name='space-game')
    recording = other_checkout / 'src' / 'games' / 'mr-muncher' / 'tests' / 'golden.jsonl.gz'

    assert stored_path(path=recording, project_root=project) == (
        'src/games/mr-muncher/tests/golden.jsonl.gz'
    )


def test_a_path_in_another_project_is_its_file_name(tmp_path):
    """A recording in a project of another name is stored by its file name only."""
    project = write_checkout(directory=tmp_path / 'project', name='space-game')
    other_project = write_checkout(directory=tmp_path / 'other', name='other-game')
    recording = other_project / 'src' / 'games' / 'mr-muncher' / 'tests' / 'golden.jsonl.gz'

    assert stored_path(path=recording, project_root=project) == 'golden.jsonl.gz'


def test_a_path_in_no_project_is_its_file_name(tmp_path):
    """No project above the path (nor one given): its file name only."""
    project = write_checkout(directory=tmp_path / 'project', name='space-game')
    loose = tmp_path / 'scratch' / 'runs' / 'session.jsonl.gz'

    assert stored_path(path=loose, project_root=project) == 'session.jsonl.gz'
    assert stored_path(path=loose, project_root=None) == 'session.jsonl.gz'


def test_a_broken_pyproject_above_a_path_is_no_checkout_of_ours(tmp_path):
    """A pyproject.toml that is no TOML never stops a writer: the file name is stored."""
    project = write_checkout(directory=tmp_path / 'project', name='space-game')
    broken = tmp_path / 'broken'
    broken.mkdir()
    (broken / 'pyproject.toml').write_text('[project\n', encoding='utf-8')

    assert stored_path(path=broken / 'a.jsonl.gz', project_root=project) == 'a.jsonl.gz'


@pytest.mark.parametrize(
    ('text', 'absolute'),
    [
        ('/Users/someone/run.jsonl.gz', True),
        ('~/run.jsonl.gz', True),
        ('~someone/run.jsonl.gz', True),
        ('C:\\Users\\someone\\run.jsonl.gz', True),
        ('c:/run.jsonl.gz', True),
        ('\\\\server\\share\\run.jsonl.gz', True),
        ('src/games/x/golden.jsonl.gz', False),
        ('run.jsonl.gz', False),
        ('../run.jsonl.gz', False),
    ],
)
def test_absolute_paths_are_told_on_every_platform(text, absolute):
    """POSIX roots, home directories, Windows drives and shares are absolute."""
    assert is_absolute_path(text=text) is absolute


def test_a_recordings_path_options_are_stored_relative_to_the_project(tmp_path, monkeypatch):
    """Tools' paths and path options are stored by stored_path; every other option as given."""
    project = write_project(directory=tmp_path / 'project')
    monkeypatch.chdir(project)
    options = {
        'record_trace': str(project / 'runs' / 'session.jsonl.gz'),
        'rebaseline': Path('new.jsonl.gz'),
        'compare_trace': str(tmp_path / 'scratch' / 'old.jsonl.gz'),
        'verify': [str(project / 'a.jsonl.gz'), 'b/c.jsonl.gz'],
        'replay_restart_handoff': str(tmp_path / 'handoff.json'),
        'replay_trace': None,
        'resolution': '800x480',
        'input_script': 'scripts.golden_inputs:paddleslap',
    }

    assert stored_options(options=options) == {
        'record_trace': 'runs/session.jsonl.gz',
        'rebaseline': 'new.jsonl.gz',
        'compare_trace': 'old.jsonl.gz',
        'verify': ['a.jsonl.gz', 'b/c.jsonl.gz'],
        'replay_restart_handoff': 'handoff.json',
        'replay_trace': None,
        'resolution': '800x480',
        'input_script': 'scripts.golden_inputs:paddleslap',
    }


def test_a_recording_made_outside_the_project_stores_its_file_name(tmp_path, monkeypatch):
    """A real recording's header names where it went by its file name only (it is outside)."""
    game = write_stand_in_game(directory=tmp_path / 'site-packages')
    use_stand_in_game(install_directory=game.install_directory, monkeypatch=monkeypatch)

    recording = record_stand_in_game(game=game, path=tmp_path / 'scratch' / 'run.jsonl.gz')

    assert recording_header(path=recording)['options']['record_trace'] == 'run.jsonl.gz'


def test_a_rebaseline_names_old_relative_to_the_project(tmp_path, monkeypatch):
    """In the header and in its newest run (the one a ledger row copies), from the project root."""
    game = write_stand_in_game(directory=tmp_path / 'site-packages')
    use_stand_in_game(install_directory=game.install_directory, monkeypatch=monkeypatch)
    project = write_project(directory=tmp_path / 'project')
    old = record_stand_in_game(game=game, path=project / 'recordings' / 'old.jsonl.gz')
    new = project / 'recordings' / 'new.jsonl.gz'

    completed = run_command(
        command=[
            sys.executable,
            '-c',
            f'import {game.package}; {game.package}.main()',
            '--log-level',
            'error',
            '--replay-trace',
            str(old),
            '--headless',
            '--rebaseline',
            str(new),
        ],
        environment=os.environ,
        timeout_seconds=CHILD_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
        working_directory=project,
    )

    assert completed.returncode == ExitCode.SUCCESS, completed.stdout
    header = recording_header(path=new)
    assert header['rebaselined_from'] == 'recordings/old.jsonl.gz'
    assert header['measurement_runs'][0]['rebaselined_from'] == 'recordings/old.jsonl.gz'
    # OLD's options are kept: recorded outside this project's directory, by file name
    assert header['options']['record_trace'] == 'old.jsonl.gz'


@pytest.mark.parametrize(
    ('renames', 'refusal'),
    [
        ({'/old/a.jsonl.gz': 'new/a.jsonl.gz'}, 'must be relative to the project root'),
        ({'old/a.jsonl.gz': 'C:\\new\\a.jsonl.gz'}, 'must be relative to the project root'),
        ({'old/a.jsonl.gz': './old/a.jsonl.gz'}, 'is renamed to itself'),
        (
            {'old/a.jsonl.gz': 'new/a.jsonl.gz', 'old//a.jsonl.gz': 'new/a.jsonl.gz'},
            'are the same old path',
        ),
        (
            {'first/a.jsonl.gz': 'second/a.jsonl.gz', 'second/a.jsonl.gz': 'third/a.jsonl.gz'},
            'which is itself renamed',
        ),
    ],
    ids=['absolute-old', 'absolute-new', 'to-itself', 'same-old-path', 'chain'],
)
def test_a_renames_table_a_one_hop_lookup_would_misread_is_refused(tmp_path, renames, refusal):
    """Refused as the settings are read, naming the key."""
    entries = '\n'.join(
        f'{json.dumps(source)} = {json.dumps(target)}' for source, target in renames.items()
    )
    project = write_project(directory=tmp_path / 'project')
    (project / 'pyproject.toml').write_text(
        f'[project]\nname = "space-game"\n\n[tool.glitchygames.recording-renames]\n{entries}\n',
        encoding='utf-8',
    )

    with pytest.raises(ProjectSettingsError, match='recording-renames') as refused:
        load_project_settings(project_root=project)

    assert refusal in str(refused.value)


def test_a_rename_to_a_missing_recording_is_found(tmp_path):
    """The table's new paths must exist: a move that left one behind is reported."""
    (tmp_path / 'new').mkdir()
    (tmp_path / 'new' / 'a.jsonl.gz').write_bytes(b'')
    settings = ProjectSettings(
        recording_renames={'old/a.jsonl.gz': 'new/a.jsonl.gz', 'old/b.jsonl.gz': 'new/b.jsonl.gz'}
    )

    assert recording_renames_problems(settings=settings, project_root=tmp_path) == [
        'old/b.jsonl.gz is renamed to new/b.jsonl.gz, which does not exist'
    ]


def test_a_rename_from_a_recording_still_there_is_found(tmp_path):
    """An old path that still holds a recording is no rename: its history would go to the new one.

    A moved recording whose old file was copied rather than moved, or a new recording made at
    an old path, would have both files' runs counted as one recording's.
    """
    for relative_path in ('old/a.jsonl.gz', 'new/a.jsonl.gz', 'new/b.jsonl.gz'):
        (tmp_path / relative_path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative_path).write_bytes(b'')
    settings = ProjectSettings(
        recording_renames={'old/a.jsonl.gz': 'new/a.jsonl.gz', 'old/b.jsonl.gz': 'new/b.jsonl.gz'}
    )

    assert recording_renames_problems(settings=settings, project_root=tmp_path) == [
        'old/a.jsonl.gz is renamed to new/a.jsonl.gz, but old/a.jsonl.gz still exists'
    ]


@pytest.mark.parametrize(
    'pyproject_text', ['[project\n', '[tool.glitchygames]\n'], ids=['broken', 'no-name']
)
def test_a_project_without_a_readable_name_has_no_other_checkouts(tmp_path, pyproject_text):
    """Our own project's name unknown: a path outside it is stored by its file name only."""
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'pyproject.toml').write_text(pyproject_text, encoding='utf-8')
    other_checkout = write_checkout(directory=tmp_path / 'other', name='space-game')

    assert stored_path(path=other_checkout / 'a.jsonl.gz', project_root=project) == 'a.jsonl.gz'
