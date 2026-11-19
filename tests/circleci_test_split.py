"""Run one CircleCI machine's share of the suite, as CircleCI's splitter assigns it by timings.

One machine ran the whole suite on Linux and stopped at CircleCI's one-hour job limit (jobs 3705
and 3707: 60.4 and 60.6 minutes, one Python each). With ``parallelism: N`` CircleCI starts N
copies of a job (``CIRCLE_NODE_INDEX`` 0 to ``CIRCLE_NODE_TOTAL`` - 1), and each runs a share
(the owner, 2026-11-18: "yes", and "Do it for windows too").

On only when ``GLITCHYGAMES_TEST_SPLIT`` is ``circleci`` (the split CI jobs set it); unset, it
does nothing, and any other value stops the run. After collection, every collected test's file
(``item.location[0]``: the name the JUnit report's ``file`` attribute carries, golden replays
included) is written to ``test-results/test-split-input.txt`` and given to ``circleci tests split
--split-by=timings --timings-type=filename`` once (through ``glitchygames.process.run_command``),
and
the tests of the files it returns are kept; the rest are deselected. The list is what pytest
collected, never a pattern written beside it, so no test can fall outside every share. CircleCI's
timings come from the stored JUnit reports, which carry each file's name under
``junit_family=xunit1`` (``noxfile.py`` sets it with this variable); without timings the splitter
divides by name.

Each machine runs its share alone, so none reaches the 100% coverage rule: the test session turns
the rule off with this variable, and a job after the split ones combines their coverage data and
applies it (``nox -s coverage-combine``).

The share is written to ``test-results/test-split.txt`` (the files sent, then the ones kept), for
the job's artifacts. Under pytest-xdist each worker collects and asks the splitter for the same
list (it divides the same input the same way), and only the first worker writes the file.
Registered in the root conftest.py's ``pytest_plugins``. Tests: tests/test_circleci_test_split.py.
"""

from __future__ import annotations

import os
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
SPLITTER_COMMAND: Final = ('tests', 'split', '--split-by=timings', '--timings-type=filename')
SPLIT_RECORD: Final = Path('test-results') / 'test-split.txt'
# Each process's list for the splitter (under pytest-xdist each worker writes its own)
SPLIT_INPUT: Final = Path('test-results') / f'test-split-input-{os.getpid()}.txt'
# The splitter reads timings and prints names: seconds, never minutes
SPLITTER_TIMEOUT_SECONDS: Final = 120.0


def split_files(
    *, collected_files: Sequence[str], run_splitter: Callable[[str], str]
) -> frozenset[str]:
    """Return this machine's files: those the splitter keeps of every collected file.

    Args:
        collected_files: Every collected test's file, in collection order (repeats allowed).
        run_splitter: Runs the splitter on the list (one file a line) and returns what it
            prints, one kept file a line.

    Returns:
        The files this machine runs.

    Raises:
        pytest.UsageError: If the splitter names a file it wasn't given.

    """
    unique_files = list(dict.fromkeys(collected_files))
    answer = run_splitter(''.join(f'{file}\n' for file in unique_files))
    kept = frozenset(line.strip() for line in answer.splitlines() if line.strip())
    unknown = sorted(kept - set(unique_files))
    if unknown:
        message = f'the test splitter named files it was not given: {", ".join(unknown)}'
        raise pytest.UsageError(message)
    return kept


def run_circleci_splitter(file_list: str) -> str:
    """Run ``circleci tests split`` on the file list, returning this machine's share.

    The list goes in a file the splitter is given by name (``SPLIT_INPUT``), kept with the job's
    test results.

    Returns:
        What the splitter prints: this machine's files, one a line.

    Raises:
        pytest.UsageError: If there is no ``circleci`` command or the splitter fails.

    """
    circleci = shutil.which('circleci')
    if circleci is None:
        message = f'{SPLIT_VARIABLE}={CIRCLECI_SPLIT} needs the circleci command (a CircleCI job)'
        raise pytest.UsageError(message)
    SPLIT_INPUT.parent.mkdir(parents=True, exist_ok=True)
    SPLIT_INPUT.write_text(file_list, encoding='utf-8')
    result = run_command(
        command=[circleci, *SPLITTER_COMMAND, str(SPLIT_INPUT)],
        environment=os.environ,
        timeout_seconds=SPLITTER_TIMEOUT_SECONDS,
        capture_output=OutputCapture.APART,
    )
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


def _write_record(*, collected_files: Sequence[str], kept: frozenset[str]) -> None:
    if os.environ.get('PYTEST_XDIST_WORKER') not in {None, 'gw0'}:
        return
    unique_files = list(dict.fromkeys(collected_files))
    node = f'{os.environ[NODE_INDEX_VARIABLE]} of {os.environ[NODE_TOTAL_VARIABLE]}'
    lines = [
        f'# CircleCI machine {node}: {len(kept)} of {len(unique_files)} test files',
        *(f'{"kept " if file in kept else "     "}{file}' for file in unique_files),
    ]
    SPLIT_RECORD.parent.mkdir(parents=True, exist_ok=True)
    SPLIT_RECORD.write_text('\n'.join(lines) + '\n', encoding='utf-8')


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Keep this machine's share of the collected tests, deselecting the others."""
    if not _split_requested():
        return
    collected_files = [item.location[0] for item in items]
    kept = split_files(collected_files=collected_files, run_splitter=run_circleci_splitter)
    _write_record(collected_files=collected_files, kept=kept)
    selected = [item for item in items if item.location[0] in kept]
    deselected = [item for item in items if item.location[0] not in kept]
    if deselected:
        config.hook.pytest_deselected(items=deselected)
    items[:] = selected
