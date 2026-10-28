"""Every golden and bundled demo, replayed at the tools' log level, emits no INFO or DEBUG record.

The replay tools start a game with ``--log-level warning`` (``children.headless_replay_arguments``),
so a replay should emit only warnings and worse. A logger level set behind the command line's
back (a module's ``logging.getLogger('game').setLevel(...)`` at import) made processes log
records that ``--log-level`` dropped everywhere else; in the test suite pytest kept them in
memory, and the serial Linux CI run was killed (signal 9) at 2 GB (BUGS.md #235). Each recording
is replayed in a child through the engine's own replay command, its records counted by logger and
level (tests/logged_records.py); a failure names every logger that emitted an INFO or DEBUG
record, with its count. A game that wants another default level sets it through ``--log-level``
(the engine's ``logging.basicConfig``), never with ``setLevel`` at import.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from glitchygames.exit_codes import ExitCode
from tests.logged_records import replay_counting_records
from tests.workspace_goldens import every_golden_and_bundled_demo

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# The levels below the tools' warning
QUIET_LEVELS = frozenset({'INFO', 'DEBUG'})
# Every golden, then every bundled demo: (console script, recording)
RECORDINGS = every_golden_and_bundled_demo(project_root=PROJECT_ROOT)


def quiet_level_offenders(*, loggers: dict[str, int]) -> str:
    """Describe the loggers that emitted records below warning, the most first.

    Args:
        loggers: Each logger's count of INFO and DEBUG records.

    Returns:
        ``game: 12 records, game.paddle: 3 records``.

    """
    ordered = sorted(loggers.items(), key=lambda item: (-item[1], item[0]))
    return ', '.join(f'{name}: {count} records' for name, count in ordered)


@pytest.mark.parametrize(
    ('console_script', 'recording'),
    RECORDINGS,
    ids=[f'{console_script}/{path.name}' for console_script, path in RECORDINGS],
)
def test_a_replay_at_the_tools_level_emits_no_info_or_debug_record(
    console_script, recording, tmp_path
):
    """A headless replay at ``--log-level warning`` logs nothing below warning, on any logger."""
    logged = replay_counting_records(
        console_script=console_script, recording=recording, work_directory=tmp_path
    )

    assert logged.returncode == ExitCode.SUCCESS, logged.output_tail
    offenders = dict(logged.by_logger(levels=QUIET_LEVELS))
    assert not offenders, (
        f'{console_script} {recording.name} at --log-level warning emitted INFO/DEBUG records '
        f'(a logger level set at import?): {quiet_level_offenders(loggers=offenders)}'
    )


def test_quiet_level_offenders_lists_the_most_first():
    """The failure message names each logger and its count, the chattiest first."""
    assert (
        quiet_level_offenders(loggers={'game.paddle': 3, 'game': 12, 'game.ball': 3})
        == 'game: 12 records, game.ball: 3 records, game.paddle: 3 records'
    )


def test_the_recordings_are_every_golden_and_bundled_demo():
    """Six goldens and PaddleSlap's demo: an empty list would skip the guard, not fail it."""
    names = sorted(f'{console_script}/{path.name}' for console_script, path in RECORDINGS)

    assert names == [
        'brave-adventurer/golden-classic.jsonl.gz',
        'brave-adventurer/golden-papyrus.jsonl.gz',
        'clockwork-keep/golden.jsonl.gz',
        'drawing-fire/golden.jsonl.gz',
        'mr-muncher/golden.jsonl.gz',
        'paddleslap/golden.jsonl.gz',
        'paddleslap/rally.jsonl.gz',
    ]
