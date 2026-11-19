"""Tests of tests/circleci_test_split.py: one CircleCI machine's share of the suite.

The splitter is CircleCI's own command, which runs only in a CircleCI job, so it is stood in for
by its contract: it is given a file listing test files, one a line, and prints the ones this
machine runs, one a line, each a name it was given.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tests import circleci_test_split
from tests.circleci_test_split import (
    CIRCLECI_SPLIT,
    NODE_INDEX_VARIABLE,
    NODE_TOTAL_VARIABLE,
    SPLIT_RECORD,
    SPLIT_VARIABLE,
    SPLITTER_COMMAND,
    run_circleci_splitter,
    split_files,
)

INNER_RUN_ARGUMENTS = ('-p', 'tests.circleci_test_split', '-p', 'no:randomly', '--assert=plain')
# Two inner test files, of which the stand-in splitter keeps the first
INNER_TESTS = {
    'test_kept': 'def test_one():\n    pass\n\ndef test_two():\n    pass\n',
    'test_left_out': 'def test_three():\n    pass\n',
}


def finished(*, returncode: int, stdout: str, stderr: str) -> SimpleNamespace:
    """Return a finished child as ``run_command`` does (``returncode``, ``stdout``, ``stderr``).

    Returns:
        The stand-in result.

    """
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


class StandInSplitter:
    """Keeps the files named at its making, of those it is given, recording each list given."""

    def __init__(self, *kept: str) -> None:
        """Keep ``kept``, given nothing yet."""
        self.kept = kept
        self.given: list[list[str]] = []

    def __call__(self, file_list: str) -> str:
        """Record the list and print the kept files it holds, one a line.

        Returns:
            The kept files, one a line.

        """
        names = file_list.splitlines()
        self.given.append(names)
        return ''.join(f'{name}\n' for name in names if name in self.kept)


def split_environment(monkeypatch: pytest.MonkeyPatch, *, node_index: int = 0) -> None:
    """Set the split on, as a CircleCI machine of two (this process may itself be split)."""
    monkeypatch.setenv(SPLIT_VARIABLE, CIRCLECI_SPLIT)
    monkeypatch.setenv(NODE_TOTAL_VARIABLE, '2')
    monkeypatch.setenv(NODE_INDEX_VARIABLE, str(node_index))
    monkeypatch.delenv('PYTEST_XDIST_WORKER', raising=False)


def test_every_collected_file_goes_to_the_splitter_once_in_collection_order():
    """Repeats (a file's many tests) go once, in the order collected."""
    splitter = StandInSplitter('b.py')

    split_files(collected_files=['b.py', 'a.py', 'b.py', 'c.py', 'a.py'], run_splitter=splitter)

    assert splitter.given == [['b.py', 'a.py', 'c.py']]


def test_the_files_kept_are_the_ones_the_splitter_prints():
    """Its blank lines and surrounding spaces aside."""
    kept = split_files(
        collected_files=['a.py', 'b.py', 'c.py'], run_splitter=lambda _list: '\n a.py \n\nc.py\n'
    )

    assert kept == frozenset({'a.py', 'c.py'})


def test_a_file_the_splitter_was_not_given_stops_the_run():
    """A name it made up (or a path spelled another way) would match no test: refused, named."""
    with pytest.raises(pytest.UsageError, match=r'not given: elsewhere\.py'):
        split_files(collected_files=['a.py'], run_splitter=lambda _list: 'a.py\nelsewhere.py\n')


def test_the_shares_of_all_machines_cover_every_file_once():
    """Two machines, each given the same list, keep what together is every file, once."""
    files = [f'tests/test_{number}.py' for number in range(7)]
    shares = [
        split_files(collected_files=files, run_splitter=StandInSplitter(*files[index::2]))
        for index in range(2)
    ]

    assert shares[0] | shares[1] == frozenset(files)
    assert not shares[0] & shares[1]


def test_unset_the_plugin_runs_every_test(pytester, monkeypatch):
    """Through pytest's hooks: no variable, no splitter, nothing deselected."""
    monkeypatch.delenv(SPLIT_VARIABLE, raising=False)
    monkeypatch.setattr(
        circleci_test_split,
        'run_circleci_splitter',
        lambda _list: pytest.fail('the splitter ran with the split off'),
    )
    pytester.makepyfile(**INNER_TESTS)

    result = pytester.runpytest_inprocess(*INNER_RUN_ARGUMENTS)

    result.assert_outcomes(passed=3)


def test_set_the_plugin_runs_only_the_kept_files_tests_and_records_the_share(pytester, monkeypatch):
    """The kept file's two tests run, the other's is deselected, and the share is written."""
    split_environment(monkeypatch, node_index=1)
    splitter = StandInSplitter('test_kept.py')
    monkeypatch.setattr(circleci_test_split, 'run_circleci_splitter', splitter)
    pytester.makepyfile(**INNER_TESTS)

    result = pytester.runpytest_inprocess(*INNER_RUN_ARGUMENTS)

    result.assert_outcomes(passed=2, deselected=1)
    assert splitter.given == [['test_kept.py', 'test_left_out.py']]
    record = (pytester.path / SPLIT_RECORD).read_text(encoding='utf-8').splitlines()
    assert record == [
        '# CircleCI machine 1 of 2: 1 of 2 test files',
        'kept test_kept.py',
        '     test_left_out.py',
    ]


def test_an_xdist_worker_after_the_first_writes_no_record(pytester, monkeypatch):
    """Every worker splits alike; only the first (or no worker) writes the share's file."""
    split_environment(monkeypatch)
    monkeypatch.setenv('PYTEST_XDIST_WORKER', 'gw1')
    monkeypatch.setattr(
        circleci_test_split, 'run_circleci_splitter', StandInSplitter('test_kept.py')
    )
    pytester.makepyfile(**INNER_TESTS)

    result = pytester.runpytest_inprocess(*INNER_RUN_ARGUMENTS)

    result.assert_outcomes(passed=2, deselected=1)
    assert not (pytester.path / SPLIT_RECORD).exists()


def test_any_other_value_of_the_variable_stops_the_run(pytester, monkeypatch):
    """Only ``circleci`` is a split: a typo never runs the whole suite, or none of it, quietly."""
    monkeypatch.setenv(SPLIT_VARIABLE, 'circle')
    pytester.makepyfile(**INNER_TESTS)

    result = pytester.runpytest_inprocess(*INNER_RUN_ARGUMENTS)

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines([f"*{SPLIT_VARIABLE} must be 'circleci' or unset, not 'circle'*"])


@pytest.mark.parametrize('missing', [NODE_TOTAL_VARIABLE, NODE_INDEX_VARIABLE])
def test_the_split_without_circlecis_node_variables_stops_the_run(pytester, monkeypatch, missing):
    """Outside a CircleCI job with ``parallelism`` the split has no machine to be: refused."""
    split_environment(monkeypatch)
    monkeypatch.delenv(missing)
    pytester.makepyfile(**INNER_TESTS)

    result = pytester.runpytest_inprocess(*INNER_RUN_ARGUMENTS)

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines([f'*needs {missing}*'])


def test_the_splitter_is_given_the_list_in_a_file_and_its_answer_returned(mocker, tmp_path):
    """``circleci tests split ... <file>``: the list written to the file named, the answer read."""
    input_path = tmp_path / 'test-results' / 'input.txt'
    mocker.patch.object(circleci_test_split, 'SPLIT_INPUT', input_path)
    mocker.patch.object(circleci_test_split.shutil, 'which', return_value='/bin/circleci')
    given: dict[str, object] = {}

    def stand_in_run_command(*, command, environment, timeout_seconds, capture_output):
        given['command'] = list(command)
        given['list'] = Path(command[-1]).read_text(encoding='utf-8')
        given['capture_output'] = capture_output
        del environment, timeout_seconds
        return finished(returncode=0, stdout='a.py\n', stderr='')

    mocker.patch.object(circleci_test_split, 'run_command', side_effect=stand_in_run_command)

    answer = run_circleci_splitter('a.py\nb.py\n')

    assert answer == 'a.py\n'
    assert given['command'] == ['/bin/circleci', *SPLITTER_COMMAND, str(input_path)]
    assert given['list'] == 'a.py\nb.py\n'
    assert given['capture_output'] == circleci_test_split.OutputCapture.APART


def test_a_failing_splitter_stops_the_run_naming_its_error(mocker, tmp_path):
    """Its exit status and standard error, in the refusal."""
    mocker.patch.object(circleci_test_split, 'SPLIT_INPUT', tmp_path / 'input.txt')
    mocker.patch.object(circleci_test_split.shutil, 'which', return_value='/bin/circleci')
    mocker.patch.object(
        circleci_test_split,
        'run_command',
        return_value=finished(returncode=2, stdout='', stderr='no timings\n'),
    )

    with pytest.raises(pytest.UsageError, match=r'failed \(2\): no timings'):
        run_circleci_splitter('a.py\n')


def test_no_circleci_command_stops_the_run(mocker):
    """Set outside a CircleCI job, where there is no ``circleci``: refused, saying so."""
    mocker.patch.object(circleci_test_split.shutil, 'which', return_value=None)

    with pytest.raises(pytest.UsageError, match=r'needs the circleci command'):
        run_circleci_splitter('a.py\n')
