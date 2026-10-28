"""Count the log records a game's child process emits, per logger and level (BUGS.md #235).

A logger level set behind the command line's back (a module's ``setLevel`` at import) made
processes log records that ``--log-level`` said to drop, and pytest kept them in memory. This
helper runs a recording through the engine's own child commands
(glitchygames/replay/tools/children.py: ``entry_point_command``, ``headless_replay_arguments``)
with a short prelude in front of the child's ``-c`` code that:

- counts every record the child creates, by ``(logger, level)``, through
  ``logging.setLogRecordFactory``. A record is created only when its logger is enabled for its
  level (``Logger._log``), so the count is what the child emitted. The factory, unlike a handler
  on the root logger, leaves ``logging.basicConfig`` alone: with a root handler already in place,
  the engine's ``basicConfig`` (``GameEngine.initialize_arguments``) would set no level at all.
- sends the child's standard output and error (file descriptors 1 and 2) to a file, so a run at
  ``--log-level debug`` writes its lines somewhere real without the parent holding them all in
  memory (``OutputCapture.TOGETHER`` would) or pytest's capture reading them back.
- at exit, writes the counts and its peak resident memory (``resource``; None on Windows) to a
  JSON file the parent reads.

Used by tests/replay/test_replays_log_quietly.py (the guard: a replay at the tools' level emits
no INFO or DEBUG record) and tests/benchmarks/test_logging_cost.py (the cost of logging).
"""

from __future__ import annotations

import collections
import dataclasses
import json
import os
from typing import TYPE_CHECKING, Any, cast

from glitchygames.process import OutputCapture, run_command, with_options_appended
from glitchygames.replay.tools.children import (
    REPLAY_TIMEOUT_SECONDS,
    entry_point_command,
    game_entry_point,
    headless_replay_arguments,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

# entry_point_command's shape: [interpreter, '-c', code]
CODE_FLAG = '-c'
# The lines of output kept in a failure's message
FAILURE_OUTPUT_LINES = 40

# The child's prelude, run before the entry point's code. Its names start with an underscore so
# they never shadow the entry point's. Formatted with the two paths (repr: quoted for Python)
COUNTING_PRELUDE = """\
import atexit as _atexit
import collections as _collections
import json as _json
import logging as _logging
import os as _os
import sys as _sys

_output = _os.open({output_path!r}, _os.O_WRONLY | _os.O_CREAT | _os.O_TRUNC, 0o644)
_os.dup2(_output, 1)
_os.dup2(_output, 2)
_counts = _collections.Counter()
_make_record = _logging.getLogRecordFactory()


def _counted_record(*args, **kwargs):
    record = _make_record(*args, **kwargs)
    _counts[(record.name, record.levelname)] += 1
    return record


def _write_counts():
    try:
        import resource as _resource
    except ImportError:
        peak = None
    else:
        # ru_maxrss is bytes on macOS and kibibytes on Linux
        scale = 1 if _sys.platform == 'darwin' else 1024
        peak = _resource.getrusage(_resource.RUSAGE_SELF).ru_maxrss * scale
    records = [[name, level, count] for (name, level), count in sorted(_counts.items())]
    with open({result_path!r}, 'w', encoding='utf-8') as result_file:
        _json.dump({{'records': records, 'peak_resident_bytes': peak}}, result_file)


_logging.setLogRecordFactory(_counted_record)
_atexit.register(_write_counts)
"""


@dataclasses.dataclass(frozen=True)
class LoggedRecords:
    """What one child run emitted.

    Attributes:
        returncode: The child's exit status.
        counts: Records emitted, by ``(logger, level name)``.
        peak_resident_bytes: The child's peak resident memory, or None (Windows).
        output_bytes: How much the child wrote to its standard output and error.
        output_tail: The last ``FAILURE_OUTPUT_LINES`` lines of that output.

    """

    returncode: int
    counts: collections.Counter[tuple[str, str]]
    peak_resident_bytes: int | None
    output_bytes: int
    output_tail: str

    def by_logger(self, *, levels: frozenset[str]) -> collections.Counter[str]:
        """Return the records of the given levels, by logger.

        Args:
            levels: Level names (``INFO``, ``DEBUG``).

        Returns:
            Each logger's count of records at one of them (none: absent).

        """
        loggers: collections.Counter[str] = collections.Counter()
        for (name, level), count in self.counts.items():
            if level in levels:
                loggers[name] += count
        return loggers

    def total(self) -> int:
        """Return how many records were emitted, at any level.

        Returns:
            The count.

        """
        return sum(self.counts.values())


def counting_command(*, command: Sequence[str], result_path: Path, output_path: Path) -> list[str]:
    """Return a ``python -c`` child command with the counting prelude in front of its code.

    Args:
        command: ``entry_point_command``'s command (``[interpreter, '-c', code]``) followed by
            the game's arguments.
        result_path: Where the child writes its counts at exit.
        output_path: Where its standard output and error go.

    Returns:
        The command, as an argument list.

    Raises:
        ValueError: If ``command`` is not a ``python -c`` command.

    """
    interpreter, flag, code, *arguments = command
    if flag != CODE_FLAG:
        message = f'not a python -c command: {list(command)!r}'
        raise ValueError(message)
    prelude = COUNTING_PRELUDE.format(output_path=str(output_path), result_path=str(result_path))
    return [interpreter, CODE_FLAG, f'{prelude}\n{code}', *arguments]


def read_logged_records(*, returncode: int, result_path: Path, output_path: Path) -> LoggedRecords:
    """Read what a counting child wrote.

    Args:
        returncode: The child's exit status.
        result_path: Its counts file.
        output_path: Its output file.

    A child that wrote no counts (it ended before its exit handlers ran) fails the assertion,
    with its exit status and the end of its output.

    Returns:
        The run's records.

    """
    output = output_path.read_text(encoding='utf-8', errors='replace')
    output_tail = '\n'.join(output.splitlines()[-FAILURE_OUTPUT_LINES:])
    assert result_path.is_file(), (
        f'the child (exit {returncode}) wrote no record counts; its output ended:\n{output_tail}'
    )
    result = cast('dict[str, Any]', json.loads(result_path.read_text(encoding='utf-8')))
    counts: collections.Counter[tuple[str, str]] = collections.Counter({
        (str(name), str(level)): int(count) for name, level, count in result['records']
    })
    peak = result['peak_resident_bytes']
    return LoggedRecords(
        returncode=returncode,
        counts=counts,
        peak_resident_bytes=None if peak is None else int(peak),
        output_bytes=output_path.stat().st_size,
        output_tail=output_tail,
    )


def replay_counting_records(
    *,
    console_script: str,
    recording: Path,
    work_directory: Path,
    extra_arguments: Sequence[str] = (),
) -> LoggedRecords:
    """Replay a recording headless through a game's console script, counting its log records.

    The child is the replay plugin's (``children.replay_command``: the console script's entry
    point with ``headless_replay_arguments``, whose level is ``warning``) with the counting
    prelude, and ``extra_arguments`` appended after its options (a later ``--log-level`` wins:
    argparse keeps the last).

    Args:
        console_script: The game's console script.
        recording: The recording.
        work_directory: An empty directory for the counts and output files.
        extra_arguments: More options for the game (``--log-level debug``, ``--rebaseline NEW``).

    Returns:
        The run's records.

    """
    entry_point = game_entry_point(console_script=console_script)
    command = with_options_appended(
        arguments=[
            *entry_point_command(entry_point=entry_point),
            *headless_replay_arguments(recording=recording),
        ],
        appended=list(extra_arguments),
    )
    result_path = work_directory / 'records.json'
    output_path = work_directory / 'output.log'
    completed = run_command(
        command=counting_command(command=command, result_path=result_path, output_path=output_path),
        environment=os.environ,
        timeout_seconds=REPLAY_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
    )
    return read_logged_records(
        returncode=completed.returncode, result_path=result_path, output_path=output_path
    )
