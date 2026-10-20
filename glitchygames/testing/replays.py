r"""A pytest plugin that runs recordings as regression tests.

A recording ``.../fixtures/replays/<console-script>/<name>.jsonl.gz`` (in this project,
``tests/fixtures/replays/``; the directory is the game's console script from ``[project.scripts]``,
for example ``paddleslap`` or ``clockwork-keep``) is collected as one test item,
``<console-script>/<name>``. The item replays the recording headless through the real engine in
a child process (started with ``run_command``, glitchygames/process.py: the engine's one
child-process launcher):

    <this interpreter> -c 'from importlib.metadata import EntryPoint; \
        EntryPoint(name=..., value=..., group=...).load()()' \
        --replay-trace <recording> --headless --log-level warning

where the entry point is the console script's (``game_entry_point``), loaded the way its
installed console script loads it.
``--headless`` puts the child on SDL's dummy drivers and runs it unpaced, so the environment is
passed on unchanged. The item passes when the child exits ``ExitCode.SUCCESS`` (the replay matched
every frame); any other exit fails it with the exit code's name and the child's output (standard
output and error together), which holds the divergence report (``Replay diverged at frame N:
...``) or the reason the recording was refused (``ExitCode.UNUSABLE_INPUT`` and
``ExitCode.MISSING_INPUT`` are reported as an unusable recording). These fail at collection: a
directory under ``fixtures/replays/`` that is not a console script, and a recording anywhere under
``fixtures/replays/`` that is not directly in a game's directory (directly in ``replays/``, or
nested deeper).

Loading the plugin: ``pytest_plugins = ['glitchygames.testing.replays']`` in the root conftest
(this project's ``conftest.py``), or ``pytest -p glitchygames.testing.replays``. Recordings are
made by ``--record-trace``; this project's fixtures (``tests/fixtures/replays/``) are recorded by
scripts/record_scripted_session.py.

The collector follows pytest's "Working with non-python tests" example
(https://docs.pytest.org/en/stable/example/nonpython.html).
"""

from __future__ import annotations

import importlib.metadata
import os
import sys
from typing import TYPE_CHECKING, Protocol, Self, cast, override

import pytest

from glitchygames.exit_codes import ExitCode
from glitchygames.process import run_command

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

# A recording is collected from .../fixtures/replays/<console-script>/<name>.jsonl.gz
REPLAY_FIXTURES_PATH_PARTS = ('fixtures', 'replays')
REPLAY_FIXTURES_LAYOUT = f'{"/".join(REPLAY_FIXTURES_PATH_PARTS)}/<console-script>/'
# The exit codes of a replay that refused its recording
UNUSABLE_RECORDING_EXIT_CODES = frozenset({ExitCode.UNUSABLE_INPUT, ExitCode.MISSING_INPUT})
RECORDING_SUFFIX = '.jsonl.gz'
CONSOLE_SCRIPTS_GROUP = 'console_scripts'
# Kill a replay child that runs longer than this (a headless replay of a few hundred frames
# takes a second or two)
REPLAY_TIMEOUT_SECONDS = 300.0


def game_entry_point(*, console_script: str) -> importlib.metadata.EntryPoint:
    """Return a console script's entry point from the installed package metadata.

    Every distribution on ``sys.path`` is searched, in order. ``importlib.metadata.entry_points``
    is not used: it keeps only the first distribution of each name, so stale metadata of the same
    package earlier on ``sys.path`` (an old ``<package>.egg-info`` in a source checkout's root,
    which pytest puts first) would hide the installed package's console scripts.

    Args:
        console_script: The console script's name (``[project.scripts]``), for example
            ``paddleslap``.

    Returns:
        The entry point (``value`` is ``'module:function'``).

    Raises:
        KeyError: If no installed package has a console script of that name.

    """
    for distribution in importlib.metadata.distributions():
        for entry_point in distribution.entry_points.select(
            group=CONSOLE_SCRIPTS_GROUP, name=console_script
        ):
            return entry_point
    raise KeyError(console_script)


class ReplayFileFactory(Protocol):
    """``ReplayFile.from_parent`` as called here.

    pytest's ``Node.from_parent`` takes untyped ``**kw``, so the type checker sees it as partly
    unknown; cast to this, the call's argument names are still checked.
    """

    def __call__(self, *, parent: pytest.Collector, path: Path) -> ReplayFile:
        """Make the collector of one recording."""
        ...


class ReplayItemFactory(Protocol):
    """``ReplayItem.from_parent`` as called here (see ReplayFileFactory)."""

    def __call__(self, *, parent: ReplayFile, name: str) -> ReplayItem:
        """Make the item of one recording."""
        ...


def is_under_replay_fixtures(*, directory: Path) -> bool:
    """Tell whether a directory is ``fixtures/replays`` or anywhere below it.

    Args:
        directory: The directory a file was found in.

    Returns:
        True if ``REPLAY_FIXTURES_PATH_PARTS`` appear in it, in order and adjacent.

    """
    parts = directory.parts
    width = len(REPLAY_FIXTURES_PATH_PARTS)
    return any(
        parts[start : start + width] == REPLAY_FIXTURES_PATH_PARTS
        for start in range(len(parts) - width + 1)
    )


def replay_command(*, entry_point: importlib.metadata.EntryPoint, recording: Path) -> list[str]:
    """Build the child command that replays a recording headless through a game's entry point.

    The child loads the entry point with ``EntryPoint.load()``, as its installed console script
    does, and calls it. Python places the arguments after ``-c``'s code in the child's
    ``sys.argv[1:]``, where the engine's option parser reads them.

    Args:
        entry_point: The game's console script entry point.
        recording: The recording to replay.

    Returns:
        The command, as an argument list.

    """
    load_and_call = (
        'from importlib.metadata import EntryPoint; '
        f'EntryPoint(name={entry_point.name!r}, value={entry_point.value!r}, '
        f'group={entry_point.group!r}).load()()'
    )
    return [
        sys.executable,
        '-c',
        load_and_call,
        '--replay-trace',
        str(recording),
        '--headless',
        '--log-level',
        'warning',
    ]


class ReplayFile(pytest.File):
    """A recording under ``fixtures/replays/``: collects one ReplayItem, or fails if misplaced."""

    @override
    def collect(self: Self) -> Iterator[ReplayItem]:
        """Yield the recording's item, after checking where it is.

        Yields:
            The recording's ReplayItem, named ``<console-script>/<name>``.

        Raises:
            pytest.Collector.CollectError: If the recording is not directly in a game's
                directory, or the directory name is not an installed console script.

        """
        if self.path.parent.parent.parts[-len(REPLAY_FIXTURES_PATH_PARTS) :] != (
            REPLAY_FIXTURES_PATH_PARTS
        ):
            message = (
                f'{self.path}: recordings go in {REPLAY_FIXTURES_LAYOUT}<name>{RECORDING_SUFFIX}'
            )
            raise pytest.Collector.CollectError(message)
        console_script = self.path.parent.name
        try:
            game_entry_point(console_script=console_script)
        except KeyError:
            message = (
                f'{self.path}: the directory {console_script!r} is not a console script; '
                f"recordings go in {REPLAY_FIXTURES_LAYOUT}, named after the game's "
                '[project.scripts] entry'
            )
            raise pytest.Collector.CollectError(message) from None
        name = self.path.name.removesuffix(RECORDING_SUFFIX)
        make_item = cast('ReplayItemFactory', ReplayItem.from_parent)
        yield make_item(parent=self, name=f'{console_script}/{name}')


class ReplayItem(pytest.Item):
    """Replays one recording headless in a child process; passes on ``ExitCode.SUCCESS``."""

    @override
    def runtest(self: Self) -> None:
        """Run the replay child; fail with its exit code and output unless it succeeded.

        ``pytest.fail(..., pytrace=False)`` shows the message alone, without the plugin's
        traceback. A child still running after REPLAY_TIMEOUT_SECONDS is killed, and the item
        fails with run_command's ``subprocess.TimeoutExpired``.

        """
        # ReplayFile.collect has checked the directory is a console script
        entry_point = game_entry_point(console_script=self.path.parent.name)
        command = replay_command(entry_point=entry_point, recording=self.path)
        finished = run_command(
            command=command,
            environment=os.environ,
            timeout_seconds=REPLAY_TIMEOUT_SECONDS,
            capture_output=True,
        )
        if finished.returncode == ExitCode.SUCCESS:
            return
        unusable = (
            ' (unusable recording)' if finished.returncode in UNUSABLE_RECORDING_EXIT_CODES else ''
        )
        message = (
            f'{self.name}: the replay exited {ExitCode.describe_status(finished.returncode)}'
            f'{unusable}\n{finished.stdout}'
        )
        pytest.fail(message, pytrace=False)


def pytest_collect_file(file_path: Path, parent: pytest.Collector) -> ReplayFile | None:
    """Collect a ``.jsonl.gz`` anywhere under ``fixtures/replays/`` as a ReplayFile.

    A recording at the wrong depth is collected too, so ReplayFile reports it instead of it
    being skipped without a word.

    Interface conformance: pytest's ``pytest_collect_file`` hook signature.

    Args:
        file_path: A file pytest found.
        parent: The directory's collector.

    Returns:
        The recording's collector, or None for any other file.

    """
    if not (
        file_path.name.endswith(RECORDING_SUFFIX)
        and is_under_replay_fixtures(directory=file_path.parent)
    ):
        return None
    make_file = cast('ReplayFileFactory', ReplayFile.from_parent)
    return make_file(parent=parent, path=file_path)
