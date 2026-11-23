"""Tests of tests/circleci_test_split.py: one CircleCI machine's share of the suite.

The splitter is CircleCI's own command, which runs only in a CircleCI job, so it is stood in for
by its contract: it is given a file listing test names, one a line, and prints the ones this
machine runs, one a line, each a name it was given, dividing the same list the same way on every
machine.
"""

from __future__ import annotations

import html
import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests import circleci_test_split
from tests.circleci_test_split import (
    CIRCLECI_SPLIT,
    CURRENT_TEST_VARIABLE,
    HEAVY_MARKER,
    NODE_INDEX_VARIABLE,
    NODE_TOTAL_VARIABLE,
    SPLIT_RECORD,
    SPLIT_VARIABLE,
    SPLITTER_COMMAND,
    choose_share,
    deal_heavy_tests,
    junit_test_name,
    repeated_junit_names,
    run_circleci_splitter,
    split_names,
)

INNER_RUN_ARGUMENTS = ('-p', 'tests.circleci_test_split', '-p', 'no:randomly', '--assert=plain')
# Two inner test files; the stand-in splitters below keep test_kept's tests
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
    """Keeps the names given at its making, of those it is given, recording each list given."""

    def __init__(self, *kept: str) -> None:
        """Keep ``kept``, given nothing yet."""
        self.kept = kept
        self.given: list[list[str]] = []

    def __call__(self, file_list: str) -> str:
        """Record the list and print the kept names it holds, one a line.

        Returns:
            The kept names, one a line.

        """
        names = file_list.splitlines()
        self.given.append(names)
        return ''.join(f'{name}\n' for name in names if name in self.kept)


class EveryNthSplitter:
    """As CircleCI's: every machine given one list keeps its own every ``total``-th name."""

    def __init__(self, *, index: int, total: int) -> None:
        """Be machine ``index`` of ``total``."""
        self.index = index
        self.total = total

    def __call__(self, name_list: str) -> str:
        """Keep this machine's names of the list, in the list's order.

        Returns:
            The kept names, one a line.

        """
        names = name_list.splitlines()
        return ''.join(f'{name}\n' for name in names[self.index :: self.total])


def split_environment(
    monkeypatch: pytest.MonkeyPatch, *, node_index: int = 0, node_total: int = 2
) -> None:
    """Set the split on, as a CircleCI machine (this process may itself be split).

    And as a run no test started: ``PYTEST_CURRENT_TEST`` is removed (pytest sets it at the
    start of each phase, so this holds for the test body), or the inner run would be nested and
    split nothing.
    """
    monkeypatch.delenv(CURRENT_TEST_VARIABLE, raising=False)
    monkeypatch.setenv(SPLIT_VARIABLE, CIRCLECI_SPLIT)
    monkeypatch.setenv(NODE_TOTAL_VARIABLE, str(node_total))
    monkeypatch.setenv(NODE_INDEX_VARIABLE, str(node_index))
    monkeypatch.delenv('PYTEST_XDIST_WORKER', raising=False)


@pytest.mark.parametrize(
    ('node_id', 'name'),
    [
        ('tests/test_a.py::test_one', 'tests.test_a.test_one'),
        ('tests/test_a.py::TestThing::test_two', 'tests.test_a.TestThing.test_two'),
        (
            'tests/deep/test_b.py::test_three[a/b-c\\d-[x]]',
            'tests.deep.test_b.test_three[a/b-c\\d-[x]]',
        ),
        (
            'src/games/x/tests/fixtures/replays/golden.jsonl.gz::golden',
            'src.games.x.tests.fixtures.replays.golden.jsonl.gz.golden',
        ),
    ],
)
def test_a_test_is_named_as_its_xunit1_junit_report_names_it(node_id, name):
    """classname.name: the file's dotted path without .py, then each part; parameters whole."""
    assert junit_test_name(node_id=node_id) == name


def test_the_names_this_process_reports_match_its_junit_report(pytester):
    """The names given the splitter are those pytest's own xunit1 report writes, joined."""
    pytester.makepyfile(
        test_names="""
        import pytest

        class TestGroup:
            def test_in_a_class(self):
                pass

        @pytest.mark.parametrize('value', ['a/b', 'c\\\\d', '[x]', 'with space'])
        def test_with_parameters(value):
            pass
        """
    )

    result = pytester.runpytest_inprocess(
        '-p',
        'no:randomly',
        '-o',
        'junit_family=xunit1',
        '--junitxml=report.xml',
        '-q',
        '--collect-only',
    )
    node_ids = [line for line in result.stdout.lines if '::' in line]
    pytester.runpytest_inprocess(
        '-p', 'no:randomly', '-o', 'junit_family=xunit1', '--junitxml=report.xml', '-q'
    )
    # The report's own attributes, unescaped (no XML parser: bandit refuses the standard one)
    report = (pytester.path / 'report.xml').read_text(encoding='utf-8')
    reported = {
        f'{html.unescape(classname)}.{html.unescape(name)}'
        for classname, name in re.findall(r'<testcase classname="([^"]*)" name="([^"]*)"', report)
    }

    assert len(node_ids) == 5
    assert {junit_test_name(node_id=node_id) for node_id in node_ids} == reported


def test_every_name_goes_to_the_splitter_once_sorted():
    """Sorted, whatever the order collected: every machine must give the splitter one list."""
    splitter = StandInSplitter('b')

    split_names(names=['c', 'a', 'b'], run_splitter=splitter)

    assert splitter.given == [['a', 'b', 'c']]


def test_the_names_kept_are_the_ones_the_splitter_prints():
    """Its blank lines and surrounding spaces aside."""
    kept = split_names(names=['a', 'b', 'c'], run_splitter=lambda _list: '\n a \n\nc\n')

    assert kept == frozenset({'a', 'c'})


def test_a_name_the_splitter_was_not_given_stops_the_run():
    """A name it made up (or a name spelled another way) would match no test: refused, named."""
    with pytest.raises(pytest.UsageError, match=r'not given: elsewhere'):
        split_names(names=['a'], run_splitter=lambda _list: 'a\nelsewhere\n')


def test_no_repeated_name_among_distinct_tests():
    """Every test's name is its own: nothing found."""
    assert (
        repeated_junit_names(
            node_ids=['tests/a.py::test_x[1]', 'tests/a.py::test_x[2]', 'tests/b.py::test_x']
        )
        == []
    )


def test_the_same_name_from_two_files_is_found():
    """A class in one file and a module of the class's name in a folder name one test alike."""
    assert repeated_junit_names(
        node_ids=[
            'tests/test_a.py::TestThing::test_y',
            'tests/test_a/TestThing.py::test_y',
            'tests/test_b.py::test_y',
        ]
    ) == ['tests.test_a.TestThing.test_y']


def test_names_that_drop_the_parameters_are_found_repeated():
    """A naming that loses the parameters (planted) makes every case of a test one name."""

    def without_parameters(*, node_id: str) -> str:
        return junit_test_name(node_id=node_id.partition('[')[0])

    assert repeated_junit_names(
        node_ids=['tests/a.py::test_x[1]', 'tests/a.py::test_x[2]', 'tests/a.py::test_z'],
        name_of=without_parameters,
    ) == ['tests.a.test_x']


def test_two_tests_with_one_name_stop_the_run():
    """Their timings could not be told apart, nor which one the splitter meant."""
    with pytest.raises(pytest.UsageError, match=r'share a JUnit name.*: tests\.a\.test_x'):
        choose_share(
            node_ids=['tests/a.py::test_x', 'tests.a.py::test_x'],
            heavy_node_ids=[],
            index=0,
            total=2,
            run_splitter=lambda name_list: name_list,
        )


@pytest.mark.parametrize('total', [1, 2, 3, 4])
def test_every_collected_test_runs_on_exactly_one_machine(total):
    """The invariant: the machines' shares, heavy and timed, together hold every test once.

    Each machine collects in its own (shuffled) order, as each CI machine rolls its own.
    """
    node_ids = [f'tests/test_{file}.py::test_{case}' for file in range(5) for case in range(7)]
    heavy = node_ids[3:20:2]
    shares = []
    for index in range(total):
        collected = node_ids[index:] + node_ids[:index]
        shares.append(
            choose_share(
                node_ids=collected,
                heavy_node_ids=list(reversed(heavy)),
                index=index,
                total=total,
                run_splitter=EveryNthSplitter(index=index, total=total),
            )
        )

    assert sorted(node_id for share in shares for node_id in share) == sorted(node_ids)


@pytest.mark.parametrize(('heavy_count', 'total'), [(42, 3), (43, 3), (44, 3), (2, 3), (7, 2)])
def test_the_machines_heavy_test_counts_differ_by_at_most_one(heavy_count, total):
    """Dealt round-robin in a stable order: no machine gets the heavy tests together."""
    heavy = [f'tests/test_heavy.py::test_case[{number}]' for number in range(heavy_count)]
    counts = [
        len(deal_heavy_tests(node_ids=list(reversed(heavy)), index=index, total=total))
        for index in range(total)
    ]

    assert sum(counts) == heavy_count
    assert max(counts) - min(counts) <= 1


def test_heavy_tests_never_reach_the_splitter():
    """Dealt without timing data: the splitter is given only the other tests."""
    splitter = StandInSplitter()

    choose_share(
        node_ids=['tests/a.py::test_light', 'tests/a.py::test_heavy'],
        heavy_node_ids=['tests/a.py::test_heavy'],
        index=0,
        total=2,
        run_splitter=splitter,
    )

    assert splitter.given == [['tests.a.test_light']]


def test_a_run_a_test_started_keeps_all_its_tests_under_a_split_environment(pytester, monkeypatch):
    """A nested run (pytester, a tool's pytest) inherits a CI machine's split variables: inactive.

    #286's Windows job (5096) ran this module's own tests on a split machine: a pytester run
    inherited GLITCHYGAMES_TEST_SPLIT and the node index, asked the real splitter, and its one
    test went to another machine. A pytest that configures while PYTEST_CURRENT_TEST is set was
    started by a test, as the draws_frames check rules (glitchygames.testing.frame_fingerprints).
    """
    assert os.environ.get(CURRENT_TEST_VARIABLE)
    monkeypatch.setenv(SPLIT_VARIABLE, CIRCLECI_SPLIT)
    monkeypatch.setenv(NODE_TOTAL_VARIABLE, '3')
    monkeypatch.setenv(NODE_INDEX_VARIABLE, '1')
    monkeypatch.setattr(
        circleci_test_split,
        'run_circleci_splitter',
        lambda _list: pytest.fail('a nested run asked the splitter'),
    )
    pytester.makepyfile(**INNER_TESTS)

    result = pytester.runpytest_inprocess(*INNER_RUN_ARGUMENTS)

    result.assert_outcomes(passed=3)
    assert not (pytester.path / SPLIT_RECORD).exists()


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


def test_set_the_plugin_runs_only_the_kept_tests_and_records_the_share(pytester, monkeypatch):
    """The kept tests run, the others are deselected; the share is written, by node id."""
    split_environment(monkeypatch, node_index=1)
    splitter = StandInSplitter('test_kept.test_one', 'test_left_out.test_three')
    monkeypatch.setattr(circleci_test_split, 'run_circleci_splitter', splitter)
    pytester.makepyfile(**INNER_TESTS)

    result = pytester.runpytest_inprocess(*INNER_RUN_ARGUMENTS)

    result.assert_outcomes(passed=2, deselected=1)
    assert splitter.given == [
        ['test_kept.test_one', 'test_kept.test_two', 'test_left_out.test_three']
    ]
    record = (pytester.path / SPLIT_RECORD).read_text(encoding='utf-8').splitlines()
    assert record == [
        '# CircleCI machine 1 of 2: 2 of 3 tests (0 of 0 heavy, dealt)',
        'kept test_kept.py::test_one',
        '     test_kept.py::test_two',
        'kept test_left_out.py::test_three',
    ]


def test_a_files_tests_can_run_on_different_machines(pytester, monkeypatch):
    """Split by test: one file's cases are divided between the machines, not kept together."""
    pytester.makepyfile(
        test_many="""
        import pytest

        @pytest.mark.parametrize('case', range(6))
        def test_case(case):
            pass
        """
    )
    ran = []
    for index in range(2):
        split_environment(monkeypatch, node_index=index)
        monkeypatch.setattr(
            circleci_test_split, 'run_circleci_splitter', EveryNthSplitter(index=index, total=2)
        )
        result = pytester.runpytest_inprocess(*INNER_RUN_ARGUMENTS)
        ran.append(result.parseoutcomes()['passed'])

    assert ran == [3, 3]


def test_marked_heavy_tests_are_dealt_out_across_the_machines(pytester, monkeypatch):
    """Three machines, nine heavy cases in one file: three each, none sent to the splitter."""
    pytester.makepyfile(
        test_heavy=f"""
        import pytest

        @pytest.mark.{HEAVY_MARKER}(reason='a replay in a child process')
        @pytest.mark.parametrize('case', range(9))
        def test_replay(case):
            pass

        def test_light():
            pass
        """
    )
    for index in range(3):
        split_environment(monkeypatch, node_index=index, node_total=3)
        splitter = StandInSplitter()
        monkeypatch.setattr(circleci_test_split, 'run_circleci_splitter', splitter)

        result = pytester.runpytest_inprocess(*INNER_RUN_ARGUMENTS)

        result.assert_outcomes(passed=3, deselected=7)
        assert splitter.given == [['test_heavy.test_light']]


def test_the_heavy_marker_is_registered(pytester):
    """Under --strict-markers a marked test is collected: the plugin registers the marker."""
    pytester.makepyfile(
        test_marked=f"""
        import pytest

        @pytest.mark.{HEAVY_MARKER}(reason='heavy')
        def test_marked():
            pass
        """
    )

    result = pytester.runpytest_inprocess(*INNER_RUN_ARGUMENTS, '--strict-markers')

    result.assert_outcomes(passed=1)


@pytest.mark.parametrize('parameter', ['a/b', 'c\\\\d', '[x]'])
def test_a_test_whose_name_holds_slashes_backslashes_or_brackets_survives_the_split(
    pytester, monkeypatch, parameter
):
    """The splitter's answer maps back to exactly the test it names."""
    split_environment(monkeypatch)
    pytester.makepyfile(
        test_odd=f"""
        import pytest

        @pytest.mark.parametrize('value', [{parameter!r}, 'plain'])
        def test_value(value):
            pass
        """
    )
    collected = pytester.runpytest_inprocess('-p', 'no:randomly', '-q', '--collect-only')
    odd = next(line for line in collected.stdout.lines if '::' in line and 'plain' not in line)
    monkeypatch.setattr(
        circleci_test_split,
        'run_circleci_splitter',
        StandInSplitter(junit_test_name(node_id=odd)),
    )

    result = pytester.runpytest_inprocess(*INNER_RUN_ARGUMENTS, '-v')

    result.assert_outcomes(passed=1, deselected=1)
    assert odd in result.stdout.str()


def test_an_xdist_worker_after_the_first_writes_no_record(pytester, monkeypatch):
    """Every worker splits alike; only the first (or no worker) writes the share's file."""
    split_environment(monkeypatch)
    monkeypatch.setenv('PYTEST_XDIST_WORKER', 'gw1')
    monkeypatch.setattr(
        circleci_test_split,
        'run_circleci_splitter',
        StandInSplitter('test_kept.test_one', 'test_kept.test_two'),
    )
    pytester.makepyfile(**INNER_TESTS)

    result = pytester.runpytest_inprocess(*INNER_RUN_ARGUMENTS)

    result.assert_outcomes(passed=2, deselected=1)
    assert not (pytester.path / SPLIT_RECORD).exists()


def test_any_other_value_of_the_variable_stops_the_run(pytester, monkeypatch):
    """Only ``circleci`` is a split: a typo never runs the whole suite, or none of it, quietly."""
    monkeypatch.delenv(CURRENT_TEST_VARIABLE, raising=False)
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
        return finished(returncode=0, stdout='a\n', stderr='no matching timings\n')

    mocker.patch.object(circleci_test_split, 'run_command', side_effect=stand_in_run_command)

    mocker.patch.object(circleci_test_split, 'SPLIT_MESSAGES', tmp_path / 'messages.txt')
    answer = run_circleci_splitter('a\nb\n')

    assert answer == 'a\n'
    assert (tmp_path / 'messages.txt').read_text(encoding='utf-8') == 'no matching timings\n'
    assert given['command'] == ['/bin/circleci', *SPLITTER_COMMAND, str(input_path)]
    assert given['list'] == 'a\nb\n'
    assert given['capture_output'] == circleci_test_split.OutputCapture.APART


def test_a_failing_splitter_stops_the_run_naming_its_error(mocker, tmp_path):
    """Its exit status and standard error, in the refusal."""
    mocker.patch.object(circleci_test_split, 'SPLIT_INPUT', tmp_path / 'input.txt')
    mocker.patch.object(circleci_test_split, 'SPLIT_MESSAGES', tmp_path / 'messages.txt')
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
