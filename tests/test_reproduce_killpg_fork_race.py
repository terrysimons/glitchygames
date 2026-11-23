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
from scripts.reproduce_killpg_fork_race import (
    TrialHadNoMemberError,
    first_member,
    main,
    run_trial,
)

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


# The shell before 2026-11-23: it logged "started" before its first fork, so a stop could land
# while the group had no member, and that trial left nothing whatever the stop did
SHELL_LOGGING_BEFORE_ITS_FIRST_FORK = (
    f'printf "started\\n" >> "$1"; i=0; while [ "$i" -lt {reproducer.MEMBERS} ]; do '
    f'sleep {reproducer.MEMBER_SECONDS} & i=$((i + 1)); done; wait'
)


@pytest.mark.parametrize('mode', reproducer.MODES)
def test_a_trial_whose_shell_logs_before_its_first_fork_is_refused(mocker, mode):
    """A trial that cannot show a member running when it stops is refused, never counted.

    It would otherwise pass without testing anything (job 5176's ``left == []``).
    """
    mocker.patch.object(reproducer, 'TRIAL_SCRIPT', SHELL_LOGGING_BEFORE_ITS_FIRST_FORK)

    with pytest.raises(TrialHadNoMemberError, match='names no member'):
        run_trial(mode=mode)


def test_the_first_members_pid_is_read_from_the_log_line(tmp_path):
    """The shell logs "started" and the pid of the member it forked first."""
    log = tmp_path / 'log'
    log.write_text('started 4321\n', encoding='utf-8')

    assert first_member(log=log) == 4321


@pytest.mark.parametrize('line', ['started\n', 'started 12 34\n', 'begun 12\n', 'started x\n'])
def test_a_log_line_naming_no_member_is_refused(tmp_path, line):
    """Anything but "started PID" names no member."""
    log = tmp_path / 'log'
    log.write_text(line, encoding='utf-8')

    with pytest.raises(TrialHadNoMemberError):
        first_member(log=log)


def test_a_first_member_gone_before_the_stop_is_refused(mocker):
    """The member the log names must still exist when the stop lands."""
    mocker.patch.object(reproducer, 'process_exists', return_value=False)

    with pytest.raises(TrialHadNoMemberError, match='gone before the stop'):
        run_trial(mode='stop-command')
