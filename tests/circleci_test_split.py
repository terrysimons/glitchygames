"""Run one CircleCI machine's share of the suite: heavy tests dealt out, the rest split by timings.

One machine ran the whole suite on Linux and stopped at CircleCI's one-hour job limit (jobs 3705
and 3707: 60.4 and 60.6 minutes, one Python each). With ``parallelism: N`` CircleCI starts N
copies of a job (``CIRCLE_NODE_INDEX`` 0 to ``CIRCLE_NODE_TOTAL`` - 1), and each runs a share
(the owner, 2026-11-18: "yes", and "Do it for windows too").

On only when ``GLITCHYGAMES_TEST_SPLIT`` is ``circleci`` (the split CI jobs set it); unset, it
does nothing, and any other value stops the run. A run a test started (``PYTEST_CURRENT_TEST`` set
when it configures: pytester, in process or as a child, or a tool's pytest) inherits a split
machine's variables and is never split: #286's Windows job (5096) split a pytester run's one test
away to another machine. The same rule as the draws_frames check
(glitchygames.testing.frame_fingerprints).

The share is chosen test by test (the owner, 2026-11-23: split by test, the costs accepted). It
was chosen file by file until then: each file went whole to one machine, so the 42 cases of
tests/test_every_recording_replays_inside_an_inner_game.py (1,585 s summed, up to 153 s a case,
each replaying in a child process beside two inner games) always shared one machine. On #285's
Windows job (5051) that machine's tests took 1,914 s against 1,312 and 1,297 s, and the owner
called concentrating the most taxing tests on one machine the worst case: load, timeouts and
races, not only time. The shuffled order (pytest-randomly) only reorders within a machine.

Every machine collects the whole suite, then keeps its share (``pytest_collection_modifyitems``,
run last, after any reordering):

1. **Heavy tests are dealt first.** A test marked ``heavy_replay(reason)`` is one of the most
   taxing (a replay in a child process and the like). The marked tests, sorted by node id, go
   round-robin: the first to machine 0, the next to machine 1, and so on, so the machines' counts
   differ by at most one, from a heavy test's first run, with no timing data needed.
2. **Every other test is split by timings.** Each is named as its JUnit report names it under
   ``junit_family=xunit1`` (``junit_test_name``: the ``classname`` and ``name`` attributes,
   joined by a dot; ``noxfile.py`` sets the family with this variable), the names sorted, and the
   list given once to ``circleci tests split --split-by=timings --timings-type=testname``
   (through ``glitchygames.process.run_command``), which prints this machine's names. Sorted,
   because each machine rolls its own order (``noxfile.choose_suite_order``) and every machine
   must give the splitter the same list to get shares that fit together. CircleCI's docs do not
   say which JUnit attributes ``testname`` matches (2026-11-23): when the names match no stored
   timing, the splitter weighs them by name instead, and says so on its standard error, which is
   kept in ``test-results/test-split-messages-<pid>.txt`` for the job's artifacts.

Every collected test runs on exactly one machine: a heavy test on the machine it is dealt to, and
every other test goes to the splitter, which divides the same list the same way on every
machine. A name the splitter was not given stops the run, and so do two tests with one name
(their JUnit timings could not be told apart).

The costs the owner accepted: each machine imports every test module and keeps every deselected
test (about 150 MiB more than collecting its own files, measured 2026-11-19 in a 2 GB arm64
Ubuntu container), and a module- or session-scoped fixture is set up on each machine that runs
one of its tests, where one machine used to set it up once.

Each machine runs its share alone, so none reaches the 100% coverage rule: the test session turns
the rule off with this variable, and a job after the split ones combines their coverage data and
applies it (``nox -s coverage-combine``).

The share is written to ``test-results/test-split.txt`` (every test, the kept ones marked; node
ids, which pytest takes back to replay a share's order), for the job's artifacts. Under
pytest-xdist each worker collects and asks the splitter for the same list, and only the first
worker writes the file. Registered in the root conftest.py's ``pytest_plugins``. Tests:
tests/test_circleci_test_split.py.
"""

from __future__ import annotations

import collections
import os
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

from glitchygames.process import OutputCapture, run_command

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

SPLIT_VARIABLE: Final = 'GLITCHYGAMES_TEST_SPLIT'
CIRCLECI_SPLIT: Final = 'circleci'
NODE_TOTAL_VARIABLE: Final = 'CIRCLE_NODE_TOTAL'
NODE_INDEX_VARIABLE: Final = 'CIRCLE_NODE_INDEX'
# pytest sets this while a test runs: a pytest that configures with it set was started by a
# test (pytester, a tool's pytest) and splits nothing (as glitchygames.testing.frame_fingerprints)
CURRENT_TEST_VARIABLE: Final = 'PYTEST_CURRENT_TEST'
SPLITTER_COMMAND: Final = ('tests', 'split', '--split-by=timings', '--timings-type=testname')
# The marker of a test dealt out round-robin before the timing split
HEAVY_MARKER: Final = 'heavy_replay'
SPLIT_RECORD: Final = Path('test-results') / 'test-split.txt'
# Each process's list for the splitter, and what the splitter said on its standard error (under
# pytest-xdist each worker writes its own)
SPLIT_INPUT: Final = Path('test-results') / f'test-split-input-{os.getpid()}.txt'
SPLIT_MESSAGES: Final = Path('test-results') / f'test-split-messages-{os.getpid()}.txt'
# The splitter reads timings and prints names: seconds, never minutes
SPLITTER_TIMEOUT_SECONDS: Final = 120.0
# Whether a test started this run (PYTEST_CURRENT_TEST set at configure): then it splits nothing
_NESTED_KEY: Final = pytest.StashKey[bool]()


def junit_test_name(*, node_id: str) -> str:
    """Return a test's name as its JUnit report names it (xunit1): ``classname.name``.

    pytest's junitxml derives both attributes from the node id (``mangle_test_address``,
    _pytest/junitxml.py, pytest 9.1): the file's path, its ``.py`` dropped and its ``/``s made
    dots, then each ``::`` part, the last one keeping its parameters whole. The classname is
    every part but the last; the name is the last.

    Args:
        node_id: The test's node id (``/``-separated on every platform).

    Returns:
        The classname and the name, joined by a dot.

    """
    path, open_bracket, parameters = node_id.partition('[')
    names = path.split('::')
    names[0] = re.sub(r'\.py$', '', names[0].replace('/', '.'))
    names[-1] += open_bracket + parameters
    return '.'.join(names)


def repeated_junit_names(
    *, node_ids: Sequence[str], name_of: Callable[..., str] = junit_test_name
) -> list[str]:
    """Return each JUnit name two or more of the tests share, sorted.

    Args:
        node_ids: The tests' node ids.
        name_of: Names a test from its node id (``junit_test_name``).

    Returns:
        The repeated names; empty when every test's is its own.

    """
    counts = collections.Counter(name_of(node_id=node_id) for node_id in node_ids)
    return sorted(name for name, count in counts.items() if count > 1)


def deal_heavy_tests(*, node_ids: Sequence[str], index: int, total: int) -> frozenset[str]:
    """Return the heavy tests machine ``index`` of ``total`` runs: every ``total``-th, sorted.

    Args:
        node_ids: Every heavy test's node id, in any order.
        index: This machine's index, from 0.
        total: The number of machines.

    Returns:
        This machine's heavy tests.

    """
    return frozenset(sorted(set(node_ids))[index::total])


def split_names(*, names: Sequence[str], run_splitter: Callable[[str], str]) -> frozenset[str]:
    """Return this machine's names: those the splitter keeps of every name, given sorted.

    Args:
        names: Every name to split, in any order (each once).
        run_splitter: Runs the splitter on the list (one name a line) and returns what it
            prints, one kept name a line.

    Returns:
        The names this machine runs.

    Raises:
        pytest.UsageError: If a name is given twice, or the splitter names one it wasn't given.

    """
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        message = (
            'two or more tests share a JUnit name, so the test split cannot tell their timings '
            f'apart: {", ".join(repeated)}'
        )
        raise pytest.UsageError(message)
    given = sorted(names)
    answer = run_splitter(''.join(f'{name}\n' for name in given))
    kept = frozenset(line.strip() for line in answer.splitlines() if line.strip())
    unknown = sorted(kept - set(given))
    if unknown:
        message = f'the test splitter named tests it was not given: {", ".join(unknown)}'
        raise pytest.UsageError(message)
    return kept


def choose_share(
    *,
    node_ids: Sequence[str],
    heavy_node_ids: Sequence[str],
    index: int,
    total: int,
    run_splitter: Callable[[str], str],
) -> frozenset[str]:
    """Return the node ids machine ``index`` of ``total`` runs.

    Args:
        node_ids: Every collected test's node id.
        heavy_node_ids: Those of them marked heavy.
        index: This machine's index, from 0.
        total: The number of machines.
        run_splitter: As ``split_names``.

    Returns:
        This machine's dealt heavy tests and the other tests the splitter keeps.

    """
    heavy = set(heavy_node_ids)
    others = [node_id for node_id in node_ids if node_id not in heavy]
    names = [junit_test_name(node_id=node_id) for node_id in others]
    kept = split_names(names=names, run_splitter=run_splitter)
    node_id_of = dict(zip(names, others, strict=True))
    return deal_heavy_tests(node_ids=list(heavy), index=index, total=total) | {
        node_id_of[name] for name in kept
    }


def run_circleci_splitter(name_list: str) -> str:
    """Run ``circleci tests split`` on the name list, returning this machine's share.

    The list goes in a file the splitter is given by name (``SPLIT_INPUT``), and what it says on
    its standard error in another (``SPLIT_MESSAGES``), both kept with the job's test results.

    Returns:
        What the splitter prints: this machine's names, one a line.

    Raises:
        pytest.UsageError: If there is no ``circleci`` command or the splitter fails.

    """
    circleci = shutil.which('circleci')
    if circleci is None:
        message = f'{SPLIT_VARIABLE}={CIRCLECI_SPLIT} needs the circleci command (a CircleCI job)'
        raise pytest.UsageError(message)
    SPLIT_INPUT.parent.mkdir(parents=True, exist_ok=True)
    SPLIT_INPUT.write_text(name_list, encoding='utf-8')
    result = run_command(
        command=[circleci, *SPLITTER_COMMAND, str(SPLIT_INPUT)],
        environment=os.environ,
        timeout_seconds=SPLITTER_TIMEOUT_SECONDS,
        capture_output=OutputCapture.APART,
    )
    SPLIT_MESSAGES.write_text(result.stderr or '', encoding='utf-8')
    if result.returncode != 0:
        error = (result.stderr or '').strip()
        message = f'circleci tests split failed ({result.returncode}): {error}'
        raise pytest.UsageError(message)
    return result.stdout or ''


def _split_requested() -> bool:
    value = os.environ.get(SPLIT_VARIABLE)
    if value is None:
        return False
    if value != CIRCLECI_SPLIT:
        message = f'{SPLIT_VARIABLE} must be {CIRCLECI_SPLIT!r} or unset, not {value!r}'
        raise pytest.UsageError(message)
    for variable in (NODE_TOTAL_VARIABLE, NODE_INDEX_VARIABLE):
        if variable not in os.environ:
            message = f'{SPLIT_VARIABLE}={CIRCLECI_SPLIT} needs {variable} (a CircleCI job)'
            raise pytest.UsageError(message)
    return True


def _write_record(*, node_ids: Sequence[str], heavy: set[str], kept: frozenset[str]) -> None:
    if os.environ.get('PYTEST_XDIST_WORKER') not in {None, 'gw0'}:
        return
    node = f'{os.environ[NODE_INDEX_VARIABLE]} of {os.environ[NODE_TOTAL_VARIABLE]}'
    dealt = len(kept & heavy)
    lines = [
        (
            f'# CircleCI machine {node}: {len(kept)} of {len(node_ids)} tests'
            f' ({dealt} of {len(heavy)} heavy, dealt)'
        ),
        *(f'{"kept " if node_id in kept else "     "}{node_id}' for node_id in node_ids),
    ]
    SPLIT_RECORD.parent.mkdir(parents=True, exist_ok=True)
    SPLIT_RECORD.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def pytest_configure(config: pytest.Config) -> None:
    """Register the heavy marker, and note whether a test started this run."""
    config.stash[_NESTED_KEY] = bool(os.environ.get(CURRENT_TEST_VARIABLE))
    config.addinivalue_line(
        'markers',
        f'{HEAVY_MARKER}(reason): one of the most taxing tests (a replay in a child process and '
        'the like); a split CI job deals these out round-robin before splitting the rest by '
        'timings, so no machine gets them all (tests/circleci_test_split.py)',
    )


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Keep this machine's share of the collected tests, deselecting the others.

    A run a test started (pytester, a tool's pytest) inherits a split machine's variables and
    splits nothing: its tests are the test's own, never a share of the job's.
    """
    if config.stash.get(_NESTED_KEY, False) or not _split_requested():
        return
    node_ids = [item.nodeid for item in items]
    heavy = {item.nodeid for item in items if item.get_closest_marker(HEAVY_MARKER) is not None}
    kept = choose_share(
        node_ids=node_ids,
        heavy_node_ids=sorted(heavy),
        index=int(os.environ[NODE_INDEX_VARIABLE]),
        total=int(os.environ[NODE_TOTAL_VARIABLE]),
        run_splitter=run_circleci_splitter,
    )
    _write_record(node_ids=node_ids, heavy=heavy, kept=kept)
    deselected = [item for item in items if item.nodeid not in kept]
    if deselected:
        config.hook.pytest_deselected(items=deselected)
    items[:] = [item for item in items if item.nodeid in kept]
