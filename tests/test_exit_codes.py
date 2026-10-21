"""The process exit codes (glitchygames/exit_codes.py) and their sysexits values."""

import os
import signal

import pytest

from glitchygames import engine
from glitchygames.exit_codes import SIGNAL_EXIT_STATUS_BASE, ExitCode

# Each member whose value is a sysexits.h code, and the name Python gives that code in os
SYSEXITS_COUNTERPARTS = {
    ExitCode.SUCCESS: 'EX_OK',
    ExitCode.OPTIONS_REFUSED: 'EX_USAGE',
    ExitCode.UNUSABLE_INPUT: 'EX_DATAERR',
    ExitCode.MISSING_INPUT: 'EX_NOINPUT',
    ExitCode.SERVICE_UNAVAILABLE: 'EX_UNAVAILABLE',
    ExitCode.INTERNAL_ERROR: 'EX_SOFTWARE',
    ExitCode.CANNOT_WRITE_OUTPUT: 'EX_CANTCREAT',
}

# The engine's own failed checks, which must stay clear of argparse's, sysexits' and the shell's
FAILED_CHECKS = (
    ExitCode.REPLAY_DIVERGED,
    ExitCode.AUDIT_NONDETERMINISTIC,
    ExitCode.GENERATION_REJECTED,
    ExitCode.EXTRACTION_REJECTED,
    ExitCode.AUDIO_DROPOUT_RISK,
    ExitCode.REBASELINE_INPUT_LOST,
    ExitCode.PROCESSING_SLOWER,
)
# sysexits.h codes run from EX_USAGE (64) to EX_CONFIG (78)
SYSEXITS_FIRST = ExitCode.OPTIONS_REFUSED
SYSEXITS_LAST = 78
# The shell's own statuses start at 126 (found but not executable)
SHELL_RESERVED_FIRST = 126


@pytest.mark.parametrize(
    ('exit_code', 'os_name'),
    sorted(SYSEXITS_COUNTERPARTS.items()),
    ids=[exit_code.name for exit_code in sorted(SYSEXITS_COUNTERPARTS)],
)
def test_each_sysexits_member_equals_the_os_constant(exit_code, os_name):
    """Each sysexits member has the value Python gives it in os, where os has the name."""
    if not hasattr(os, os_name):
        pytest.skip(f'os.{os_name} exists only on Unix; this platform has no sysexits names')
    assert exit_code == getattr(os, os_name)


def test_every_code_has_exactly_one_name():
    """No aliases: ExitCode(value).name always names the one meaning of that value."""
    assert len(ExitCode.__members__) == len(ExitCode)
    assert len({exit_code.value for exit_code in ExitCode}) == len(ExitCode)
    assert ExitCode(ExitCode.AUDIO_DROPOUT_RISK.value).name == 'AUDIO_DROPOUT_RISK'


@pytest.mark.parametrize('exit_code', FAILED_CHECKS, ids=lambda exit_code: exit_code.name)
def test_failed_checks_avoid_reserved_codes(exit_code):
    """The failed checks stay clear of argparse, sysexits and the shell's statuses."""
    assert exit_code != ExitCode.ARGUMENT_PARSER_ERROR
    assert not SYSEXITS_FIRST <= exit_code <= SYSEXITS_LAST
    assert exit_code < SHELL_RESERVED_FIRST


def test_describe_names_the_code_and_its_number():
    """describe() is the form the engine logs: the name and the number."""
    assert ExitCode.OPTIONS_REFUSED.describe() == f'OPTIONS_REFUSED ({ExitCode.OPTIONS_REFUSED:d})'


@pytest.mark.parametrize(
    ('status', 'expected'),
    [
        (ExitCode.INTERNAL_ERROR.value, ExitCode.INTERNAL_ERROR.describe()),
        (
            SIGNAL_EXIT_STATUS_BASE + signal.SIGABRT,
            f'signal {signal.SIGABRT:d} ({SIGNAL_EXIT_STATUS_BASE + signal.SIGABRT})',
        ),
        (SHELL_RESERVED_FIRST, str(SHELL_RESERVED_FIRST)),
        (-signal.SIGTERM, f'TERMINATED (signal {signal.SIGTERM:d})'),
        (-signal.SIGABRT, f'signal {signal.SIGABRT:d}'),
    ],
    ids=['member', 'unwired signal', 'unknown', 'killed by a wired signal', 'killed by another'],
)
def test_describe_status_reads_any_process_status(status, expected):
    """A child's status reads as its member, an unwired signal, or a bare number."""
    assert ExitCode.describe_status(status) == expected


def test_the_engine_re_exports_the_exit_codes():
    """Games and scripts import ExitCode from glitchygames.engine."""
    assert engine.ExitCode is ExitCode


# Each signal member and the signal it stands for, by name (some exist on one platform only)
SIGNAL_MEMBERS = {
    ExitCode.HANGUP: 'SIGHUP',
    ExitCode.INTERRUPTED: 'SIGINT',
    ExitCode.TERMINATED: 'SIGTERM',
    ExitCode.BREAK: 'SIGBREAK',
}


@pytest.mark.parametrize(
    ('exit_code', 'signal_name'),
    sorted(SIGNAL_MEMBERS.items()),
    ids=[exit_code.name for exit_code in sorted(SIGNAL_MEMBERS)],
)
def test_each_signal_member_is_the_shell_status_of_its_signal(exit_code, signal_name):
    """Each signal member is 128 + its signal, where this platform has the signal."""
    if not hasattr(signal, signal_name):
        pytest.skip(f'signal.{signal_name} does not exist on this platform')
    signal_number = getattr(signal, signal_name)
    assert exit_code == SIGNAL_EXIT_STATUS_BASE + signal_number
    assert ExitCode.for_signal(signal_number) is exit_code


@pytest.mark.parametrize('signal_number', [signal.SIGABRT, 0], ids=['unwired signal', 'zero'])
def test_a_signal_the_engine_does_not_handle_has_no_exit_code(signal_number):
    """for_signal refuses an unwired signal rather than returning a nameless number."""
    with pytest.raises(ValueError, match=f'signal {signal_number} has no exit code'):
        ExitCode.for_signal(signal_number)
