"""scripts/reproduce_killpg_fork_race.py: stop a process group as it forks, count what is left.

The raw ``killpg`` mode leaves a member running only on some trials on macOS (a race), so these
tests drive the ``stop-command`` mode, which must never leave one, and a stand-in group signal
that misses the forked member every time, which the report must name.
"""

from __future__ import annotations

import os
import sys

import pytest
from scripts import reproduce_killpg_fork_race as reproducer
from scripts.reproduce_killpg_fork_race import main, run_trial

from glitchygames.exit_codes import ExitCode

pytestmark = pytest.mark.skipif(sys.platform == 'win32', reason='process groups are POSIX')


def test_stop_command_leaves_nothing_in_any_trial(capsys):
    """stop_command kills whatever the group signal missed: every trial's pipe closes."""
    assert main(['stop-command', '--trials', '3']) == ExitCode.SUCCESS

    assert capsys.readouterr().out == 'stop-command: 0 of 3 trials left a member running\n'


def test_a_group_signal_that_misses_the_forked_member_is_reported(mocker):
    """A kill that reaches only the leader leaves its forked sleeps holding the pipe: named."""
    mocker.patch.object(reproducer, 'PIPES_CLOSE_SECONDS', 0.5)
    real_killpg = os.killpg
    missed = []

    def killpg_missing_the_forked_member(group: int, signal_number: int) -> None:
        # The first group signal reaches the leader only, as if the sleep were forked during
        # its delivery; the trial's own cleanup afterwards is the real killpg
        if not missed:
            missed.append(signal_number)
            os.kill(group, signal_number)
            return
        real_killpg(group, signal_number)

    mocker.patch.object(reproducer.os, 'killpg', side_effect=killpg_missing_the_forked_member)

    left = run_trial(mode='killpg')

    # The shell itself was killed; what it had forked is left, and only that
    assert left
    assert all(member.endswith(f'sleep {reproducer.MEMBER_SECONDS}') for member in left), left
