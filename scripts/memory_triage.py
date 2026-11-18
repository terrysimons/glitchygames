"""Find what the test process holds in Python memory, for test-memory triage.

The tracemalloc probes that found the Linux CI job's memory causes in November 2026
(bugs/2026-11-17-linux-test-memory-guard-stops.md). Each runs pytest inside this process,
serially, then reports from tracemalloc. They see Python allocations only: SDL surfaces and
memory the allocator keeps after it is freed are not counted. For resident memory per test
file, use the ``tests.memory_by_file`` plugin (docs/architecture/playback/testing.md, "Memory by
test file").

  collection          Collect the suite (no tests run): what collection holds, by file.
  held TARGET         Run TARGET, then list what it still holds, by allocating traceback.
                      ``--by owner`` sums it by the first engine frame that allocated it;
                      ``--by unattributed`` lists the largest blocks no engine frame allocated.
  traced TARGET...    Run the tests: Python memory kept afterwards, and the peak while they ran.
  per-test TARGET...  Run the tests: Python memory and peak after each test.

Run: ``uv run python -m scripts.memory_triage held tests/audio/test_instrument_catalog.py``.
"""

from __future__ import annotations

import argparse
import gc
import sys
import tracemalloc
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Sequence

MEBIBYTE = 1024 * 1024
# One process, one test at a time, nothing else allocating beside the tests
SERIAL_PYTEST_OPTIONS = (
    '-q',
    '-n',
    '0',
    '-p',
    'no:randomly',
    '--no-cov',
    '-p',
    'no:cacheprovider',
    '--dummy-only',
)
ENGINE_SOURCE = '/src/glitchygames/'
TRACEBACK_DEPTH = 25
LISTED_ROWS = 12


def _say(line: str) -> None:
    """Write one line of the report."""
    sys.stdout.write(f'{line}\n')


def _mebibytes(size: int) -> str:
    return f'{size / MEBIBYTE:7.1f} MiB'


def _run_pytest(targets: Sequence[str], *, plugins: Sequence[object] = ()) -> None:
    pytest.main([*targets, *SERIAL_PYTEST_OPTIONS], plugins=list(plugins))


def _held_after(target: str) -> list[tracemalloc.StatisticDiff]:
    """Run ``target`` under tracemalloc; what it allocated and still holds, largest first.

    Returns:
        The differences by traceback, imports and tracemalloc's own blocks left out.
    """
    tracemalloc.start(TRACEBACK_DEPTH)
    before = tracemalloc.take_snapshot()
    _run_pytest([target])
    gc.collect()
    after = tracemalloc.take_snapshot()
    filters = [
        tracemalloc.Filter(inclusive=False, filename_pattern=tracemalloc.__file__),
        tracemalloc.Filter(inclusive=False, filename_pattern='<frozen importlib._bootstrap*>'),
    ]
    return after.filter_traces(filters).compare_to(before.filter_traces(filters), 'traceback')


def _engine_owner(traceback: tracemalloc.Traceback) -> str | None:
    """The oldest engine frame (outside tests) in ``traceback``, as ``path:line``.

    Returns:
        The frame, or None when no engine frame allocated it.
    """
    for frame in traceback:
        if ENGINE_SOURCE in frame.filename and '/tests/' not in frame.filename:
            return f'{frame.filename.split(ENGINE_SOURCE)[-1]}:{frame.lineno}'
    return None


def report_collection(pytest_options: Sequence[str]) -> None:
    """What collecting the suite holds, by allocating file."""
    tracemalloc.start(1)
    pytest.main(['--collect-only', *SERIAL_PYTEST_OPTIONS, *pytest_options])
    gc.collect()
    statistics = tracemalloc.take_snapshot().statistics('filename')
    _say(f'held after collection: {_mebibytes(sum(stat.size for stat in statistics))}')
    for stat in statistics[:LISTED_ROWS]:
        _say(f'{_mebibytes(stat.size)} {stat.count:8d} blocks  {stat.traceback[0].filename}')


def report_held(target: str, *, by: str) -> None:
    """What ``target`` still holds after it ran, grouped as ``by`` says."""
    differences = _held_after(target)
    _say(f'held after {target}: {_mebibytes(sum(stat.size_diff for stat in differences))}')
    if by == 'owner':
        by_owner: dict[str, int] = {}
        for stat in differences:
            owner = _engine_owner(stat.traceback) or 'no engine frame'
            by_owner[owner] = by_owner.get(owner, 0) + stat.size_diff
        for owner, size in sorted(by_owner.items(), key=lambda item: -item[1])[:LISTED_ROWS]:
            _say(f'{_mebibytes(size)}  first engine frame {owner}')
        return
    if by == 'unattributed':
        differences = [stat for stat in differences if _engine_owner(stat.traceback) is None]
    for stat in sorted(differences, key=lambda stat: -stat.size_diff)[: LISTED_ROWS // 2]:
        _say(f'\n{_mebibytes(stat.size_diff)} in {stat.count_diff} blocks')
        for line in stat.traceback.format()[-LISTED_ROWS:]:
            _say(f'    {line.strip()}')


def report_traced(targets: Sequence[str]) -> None:
    """Python memory kept after ``targets`` ran, and the peak while they ran."""
    tracemalloc.start()
    _run_pytest(targets)
    gc.collect()
    current, peak = tracemalloc.get_traced_memory()
    _say(f'traced now {_mebibytes(current)}, peak {_mebibytes(peak)}')


class PerTestReporter:
    """A pytest plugin: Python memory and peak after each test, garbage collected."""

    def pytest_runtest_logfinish(self, nodeid: str) -> None:
        """Report this test's memory and peak, then start the next test's peak afresh.

        Args:
            nodeid: The finished test's id.
        """
        gc.collect()
        current, peak = tracemalloc.get_traced_memory()
        _say(f'[memory] {_mebibytes(current)} now, {_mebibytes(peak)} peak  {nodeid}')
        tracemalloc.reset_peak()


def report_per_test(targets: Sequence[str]) -> None:
    """Python memory and peak after each test of ``targets``."""
    tracemalloc.start()
    _run_pytest([*targets, '-s'], plugins=[PerTestReporter()])


def main(argv: Sequence[str] | None = None) -> None:
    """Run the probe the command line names."""
    parser = argparse.ArgumentParser(
        description='Find what the test process holds in Python memory.'
    )
    probes = parser.add_subparsers(dest='probe', required=True)
    collection = probes.add_parser('collection', help='what collecting the suite holds')
    collection.add_argument('pytest_options', nargs='*', help='more pytest options')
    held = probes.add_parser('held', help='what a test file still holds after it ran')
    held.add_argument('target', help='a test file or node id')
    held.add_argument('--by', choices=('traceback', 'owner', 'unattributed'), default='traceback')
    traced = probes.add_parser('traced', help='Python memory kept, and the peak')
    traced.add_argument('targets', nargs='+', help='test files or node ids')
    per_test = probes.add_parser('per-test', help='Python memory after each test')
    per_test.add_argument('targets', nargs='+', help='test files or node ids')
    arguments = parser.parse_args(argv)
    match arguments.probe:
        case 'collection':
            report_collection(arguments.pytest_options)
        case 'held':
            report_held(arguments.target, by=arguments.by)
        case 'traced':
            report_traced(arguments.targets)
        case _:
            report_per_test(arguments.targets)


if __name__ == '__main__':
    main()
