"""scripts/record_golden_traces.py and scripts/golden_inputs.py load a game only when needed.

Many tests import the scripts for their tables (``GAME_SCENES``, ``SCRIPT_BUILDERS``) and run no
game, so importing them imports no workspace member: ``GAME_SCENES`` holds each game's scene
class by reference and imports it the first time it is looked up (the engine's
``GameSceneClasses``, tested in tests/replay/tools/test_golden_trace_harness.py), and the input
scripts import what they read of a game where they read it.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest
from scripts import record_golden_traces

from glitchygames.process import run_command

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHILD_TIMEOUT_SECONDS = 60.0
# A child that imports the harness's scripts and prints every member package it then holds
IMPORTED_MEMBERS_PROGRAM = """
import json
import sys

from pathlib import Path

import scripts.golden_inputs
import scripts.record_golden_traces
import scripts.record_scripted_session
from scripts.workspace_packages import workspace_members

members = {
    package
    for member in workspace_members(project_root=Path.cwd())
    for package in member.import_packages
}
loaded = {module.partition('.')[0] for module in sys.modules}
print(json.dumps([len(members), sorted(loaded & members)]))
"""
# A child that looks up one game: only that game's member is imported
LOOKED_UP_GAME_PROGRAM = """
import json
import sys

from pathlib import Path

from scripts.record_golden_traces import GAME_SCENES
from scripts.workspace_packages import workspace_members

members = {
    package
    for member in workspace_members(project_root=Path.cwd())
    for package in member.import_packages
}
scene_class = GAME_SCENES['clockwork_keep']
loaded = {module.partition('.')[0] for module in sys.modules}
print(json.dumps([scene_class.__name__, sorted(loaded & members)]))
"""


def run_child(*, program: str) -> Any:
    """Run a Python program in a fresh interpreter from the repository; return its JSON line.

    Returns:
        The decoded last line it printed.

    """
    completed = run_command(
        command=[sys.executable, '-c', program],
        environment={**os.environ, 'SDL_VIDEODRIVER': 'dummy', 'SDL_AUDIODRIVER': 'dummy'},
        timeout_seconds=CHILD_TIMEOUT_SECONDS,
        capture_output=True,
        working_directory=PROJECT_ROOT,
    )
    assert completed.returncode == 0, completed.stdout
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_importing_the_harness_imports_no_member():
    """A fresh interpreter that imports the harness's scripts holds no member package.

    The member packages are the workspace's (every member's ``import_packages``, read in the
    child from the repository it runs in), and there are some.
    """
    member_package_count, loaded_members = run_child(program=IMPORTED_MEMBERS_PROGRAM)

    assert member_package_count > 0
    assert loaded_members == []


def test_looking_up_a_game_imports_only_its_member():
    """GAME_SCENES['clockwork_keep'] imports Clockwork Keep, and nothing else of the members."""
    assert run_child(program=LOOKED_UP_GAME_PROGRAM) == [
        'ClockworkKeepScene',
        ['clockwork_keep'],
    ]


@pytest.mark.parametrize(
    ('arguments', 'exit_status'),
    [(['--help'], 0), (['--no-such-option'], 2)],
    ids=['help', 'unknown-argument'],
)
def test_the_command_records_nothing_unless_asked(mocker, capsys, arguments, exit_status):
    """``--help`` prints the usage and an unknown argument is refused: neither records a trace.

    A command that ignored its arguments re-recorded every golden trace in tests/world/golden/
    for ``--help`` (found in Task D4b's review). Recording and writing are patched out, so a
    regression here never touches the repository's traces.
    """
    recorded = mocker.patch.object(record_golden_traces, 'record_trace')
    written = mocker.patch.object(record_golden_traces, 'write_trace')
    mocker.patch.object(sys, 'argv', ['record_golden_traces', *arguments])

    with pytest.raises(SystemExit) as exit_information:
        record_golden_traces.main()

    assert exit_information.value.code == exit_status
    recorded.assert_not_called()
    written.assert_not_called()
    if exit_status == 0:
        assert 'usage:' in capsys.readouterr().out
