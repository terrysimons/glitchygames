"""What logging costs a replay: every golden and bundled demo at ``warning`` and at ``debug``.

The owner, 2026-10-28: "add a benchmark that measures the delta between the game running with
logs disabled and enabled? That could also help determine if logging needs to be cleaned up
somewhere." Each recording is rebaselined headless twice through the engine's own child command
(``children.replay_command`` plus ``--rebaseline NEW``, what ``glitchygames measure`` runs), at
``--log-level warning`` (the tools' level) and at ``--log-level debug``, with
tests/logged_records.py counting every record the child creates by logger and level and sending
its output to a file. Per recording and level it reports the processing time per frame (the
rebaselined run's ``RunSummary``: the time the engine measured for each frame's work, with the
logging it did), the child's peak resident memory (None on Windows) and the records per frame,
then the loggers that emit the most at ``debug``, per recording. Both tables are printed and
written to ``test-results/logging-cost.md``.

Not in the test run (``nox -s test``, every CI job's tests): it replays every recording twice
(about a minute), so it runs only under ``--benchmark-only`` and is skipped otherwise.
pytest-benchmark's own switch is not enough: it turns benchmarks off only under xdist, and the
Linux CI job runs serially. CI does run it: the macOS job's ``nox -s performance-test`` passes
``--benchmark-only`` (.circleci/config.yml), where a rebaseline that fails, or a quiet run that
logs below warning, fails the job. Locally: the command in docs/quality/performance.md.
"""

from __future__ import annotations

import collections
import dataclasses
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from glitchygames.recording_history import recording_run_summaries
from glitchygames.replay.tools.measure import MEASURED_EXIT_CODES
from glitchygames.tracing import FRAMES_FIELD, read_trace
from tests.logged_records import replay_counting_records
from tests.workspace_goldens import every_golden_and_bundled_demo

if TYPE_CHECKING:
    from tests.logged_records import LoggedRecords

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = PROJECT_ROOT / 'test-results' / 'logging-cost.md'
# Logs disabled (the tools' level) and enabled (everything)
QUIET_LEVEL = 'warning'
LOUD_LEVEL = 'debug'
# The loggers listed per recording in the first table
TOP_LOGGER_COUNT = 5
BYTES_PER_MEGABYTE = 1024 * 1024
MILLISECONDS_PER_SECOND = 1000.0
PERCENT = 100.0


@dataclasses.dataclass(frozen=True)
class LevelRun:
    """One recording rebaselined at one log level.

    Attributes:
        frames: Frames the rebaseline measured.
        processing_seconds_per_frame: Their mean processing time.
        median_processing_seconds: Their median processing time.
        logged: The child's records, peak memory and output.

    """

    frames: int
    processing_seconds_per_frame: float
    median_processing_seconds: float
    logged: LoggedRecords

    def records_per_frame(self) -> float:
        """Return the records emitted per measured frame (any level).

        Returns:
            The rate.

        """
        return self.logged.total() / self.frames


@dataclasses.dataclass(frozen=True)
class RecordingCost:
    """One recording at both levels.

    Attributes:
        name: ``<console script>/<file name>``.
        quiet: The run at ``warning``.
        loud: The run at ``debug``.

    """

    name: str
    quiet: LevelRun
    loud: LevelRun


def rebaseline_at_level(
    *, console_script: str, recording: Path, level: str, work_directory: Path
) -> LevelRun:
    """Rebaseline a recording at one log level, counting its records.

    Args:
        console_script: The game's console script.
        recording: The recording.
        level: ``--log-level``'s value.
        work_directory: An empty directory for the rebaselined copy and the counts.

    Returns:
        The run.

    """
    rebaselined = work_directory / 'rebaselined.jsonl.gz'
    logged = replay_counting_records(
        console_script=console_script,
        recording=recording,
        work_directory=work_directory,
        extra_arguments=['--log-level', level, '--rebaseline', str(rebaselined)],
    )
    assert logged.returncode in MEASURED_EXIT_CODES, (
        f'{console_script} {recording.name} at --log-level {level}: the rebaseline exited '
        f'{logged.returncode}\n{logged.output_tail}'
    )
    trace = read_trace(path=rebaselined)
    summary = recording_run_summaries(header=trace, frames=trace[FRAMES_FIELD])[0]
    assert summary is not None, f'{rebaselined}: the rebaselined run has no processing times'
    return LevelRun(
        frames=summary.measured_frames,
        processing_seconds_per_frame=summary.total_processing_seconds / summary.measured_frames,
        median_processing_seconds=summary.p50_processing_seconds,
        logged=logged,
    )


def _megabytes(byte_count: int | None) -> str:
    return 'n/a' if byte_count is None else f'{byte_count / BYTES_PER_MEGABYTE:.0f}'


def _milliseconds(seconds: float) -> str:
    return f'{seconds * MILLISECONDS_PER_SECOND:.3f}'


def _change(*, before: float, after: float) -> str:
    if before <= 0.0:
        return 'n/a'
    return f'{(after / before - 1.0) * PERCENT:+.1f}%'


def top_loggers_table(*, costs: list[RecordingCost]) -> list[str]:
    """Return the first table: each recording's chattiest loggers at ``debug``.

    Args:
        costs: Every recording's runs.

    Returns:
        Markdown lines: recording, logger, records per frame, records, and their share.

    """
    lines = [
        f'Top {TOP_LOGGER_COUNT} loggers by volume at --log-level {LOUD_LEVEL}, per recording',
        '',
        '| Recording | Logger | Records/frame | Records | Share |',
        '|---|---|---:|---:|---:|',
    ]
    for cost in costs:
        loggers: collections.Counter[str] = collections.Counter()
        for (name, _level), count in cost.loud.logged.counts.items():
            loggers[name] += count
        total = sum(loggers.values())
        ordered = sorted(loggers.items(), key=lambda item: (-item[1], item[0]))
        if not ordered:
            lines.append(f'| {cost.name} | (none) | 0 | 0 | |')
        lines.extend(
            f'| {cost.name} | {name} | {count / cost.loud.frames:.2f} | {count} | '
            f'{count / total * PERCENT:.1f}% |'
            for name, count in ordered[:TOP_LOGGER_COUNT]
        )
    return lines


def deltas_table(*, costs: list[RecordingCost]) -> list[str]:
    """Return the second table: what ``debug`` costs against ``warning``, per recording.

    Args:
        costs: Every recording's runs.

    Returns:
        Markdown lines: frames, mean and median processing ms per frame at each level and the
        change, peak resident MB at each level, records per frame and output MB at ``debug``.

    """
    lines = [
        f'Logging cost: --log-level {QUIET_LEVEL} against {LOUD_LEVEL}',
        '',
        (
            '| Recording | Frames | ms/frame warning | ms/frame debug | Change | Median ms warning '
            '| Median ms debug | Peak MB warning | Peak MB debug | Records/frame warning '
            '| Records/frame debug | Output MB debug |'
        ),
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    lines.extend(
        f'| {cost.name} | {cost.loud.frames} '
        f'| {_milliseconds(cost.quiet.processing_seconds_per_frame)} '
        f'| {_milliseconds(cost.loud.processing_seconds_per_frame)} '
        f'| {
            _change(
                before=cost.quiet.processing_seconds_per_frame,
                after=cost.loud.processing_seconds_per_frame,
            )
        } '
        f'| {_milliseconds(cost.quiet.median_processing_seconds)} '
        f'| {_milliseconds(cost.loud.median_processing_seconds)} '
        f'| {_megabytes(cost.quiet.logged.peak_resident_bytes)} '
        f'| {_megabytes(cost.loud.logged.peak_resident_bytes)} '
        f'| {cost.quiet.records_per_frame():.2f} | {cost.loud.records_per_frame():.2f} '
        f'| {cost.loud.logged.output_bytes / BYTES_PER_MEGABYTE:.1f} |'
        for cost in costs
    )
    return lines


def measure_every_recording(*, work_directory: Path) -> list[RecordingCost]:
    """Rebaseline every golden and bundled demo at both levels.

    Args:
        work_directory: An empty directory (one subdirectory per run).

    Returns:
        Each recording's runs, in ``every_golden_and_bundled_demo``'s order.

    """
    costs: list[RecordingCost] = []
    for index, (console_script, recording) in enumerate(
        every_golden_and_bundled_demo(project_root=PROJECT_ROOT)
    ):
        runs: dict[str, LevelRun] = {}
        for level in (QUIET_LEVEL, LOUD_LEVEL):
            run_directory = work_directory / f'{index}-{level}'
            run_directory.mkdir()
            runs[level] = rebaseline_at_level(
                console_script=console_script,
                recording=recording,
                level=level,
                work_directory=run_directory,
            )
        costs.append(
            RecordingCost(
                name=f'{console_script}/{recording.name}',
                quiet=runs[QUIET_LEVEL],
                loud=runs[LOUD_LEVEL],
            )
        )
    return costs


def test_logging_cost_of_every_golden_and_bundled_demo(benchmark, request, tmp_path, capsys):
    """Report what ``--log-level debug`` costs each recording against ``warning``.

    It asserts only what makes the numbers mean something: every rebaseline succeeded, and the
    quiet run emitted no INFO or DEBUG record (the quiet-run guard's rule; its own test is
    tests/replay/test_replays_log_quietly.py).
    """
    if not request.config.getoption('benchmark_only'):
        pytest.skip('replays every recording twice: run with --benchmark-only')

    costs: list[RecordingCost] = benchmark.pedantic(
        measure_every_recording, kwargs={'work_directory': tmp_path}, rounds=1, iterations=1
    )

    report = '\n'.join([
        *top_loggers_table(costs=costs),
        '',
        *deltas_table(costs=costs),
        '',
    ])
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding='utf-8')
    terminal = request.config.pluginmanager.get_plugin('terminalreporter')
    with capsys.disabled():
        terminal.write_line(f'\n{report}\n(written to {REPORT_PATH})')
    for cost in costs:
        assert not cost.quiet.logged.by_logger(levels=frozenset({'INFO', 'DEBUG'})), cost.name
