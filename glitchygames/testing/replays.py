r"""A pytest plugin that runs recordings as regression tests.

A recording ``.../fixtures/replays/<console-script>/<name>.jsonl.gz`` (in this project,
``tests/fixtures/replays/``; the directory is the game's console script from ``[project.scripts]``,
for example ``paddleslap`` or ``clockwork-keep``) is collected as one test item,
``<console-script>/<name>``. The item replays the recording headless through the real engine in
a child process (started with ``run_command``, glitchygames/replay/audit.py: the engine's one
child-process launcher):

    <this interpreter> -c 'from <module> import <function>; <function>()' \
        --replay-trace <recording> --headless --log-level warning

where ``<module>:<function>`` is the console script's entry point (``game_entry_point``).
``--headless`` puts the child on SDL's dummy drivers and runs it unpaced, so the environment is
passed on unchanged. The item passes when the child exits ``ExitCode.SUCCESS`` (the replay matched
every frame); any other exit fails it with the exit code's name and the child's output (standard
output and error together), which holds the divergence report (``Replay diverged at frame N:
...``) or the reason the recording was refused (``ExitCode.UNUSABLE_INPUT`` and
``ExitCode.MISSING_INPUT`` are reported as an unusable recording). A directory under
``fixtures/replays/`` that is not a console script fails at collection.

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
from typing import TYPE_CHECKING, Any, Self, override

import pytest

from glitchygames.exit_codes import ExitCode
from glitchygames.replay.audit import run_command

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

# A recording is collected from .../fixtures/replays/<console-script>/<name>.jsonl.gz
REPLAY_FIXTURES_PATH_PARTS = ('fixtures', 'replays')
# The exit codes of a replay that refused its recording
UNUSABLE_RECORDING_EXIT_CODES = frozenset({ExitCode.UNUSABLE_INPUT, ExitCode.MISSING_INPUT})
RECORDING_SUFFIX = '.jsonl.gz'
CONSOLE_SCRIPTS_GROUP = 'console_scripts'
# Kill a replay child that runs longer than this (a headless replay of a few hundred frames
# takes a second or two)
REPLAY_TIMEOUT_SECONDS = 300.0


def game_entry_point(*, console_script: str) -> str:
    """Return a console script's entry point from the installed package metadata.

    Every distribution on ``sys.path`` is searched, in order. ``importlib.metadata.entry_points``
    is not used: it keeps only the first distribution of each name, so stale metadata of the same
    package earlier on ``sys.path`` (an old ``<package>.egg-info`` in a source checkout's root,
    which pytest puts first) would hide the installed package's console scripts.

    Args:
        console_script: The console script's name (``[project.scripts]``), for example
            ``paddleslap``.

    Returns:
        The entry point as ``'module:function'``.

    Raises:
        KeyError: If no installed package has a console script of that name.

    """
    for distribution in importlib.metadata.distributions():
        for entry_point in distribution.entry_points.select(
            group=CONSOLE_SCRIPTS_GROUP, name=console_script
        ):
            return entry_point.value
    raise KeyError(console_script)


def replay_command(*, entry_point: str, recording: Path) -> list[str]:
    """Build the child command that replays a recording headless through a game's entry point.

    Python places the arguments after ``-c``'s code in the child's ``sys.argv[1:]``, where the
    engine's option parser reads them.

    Args:
        entry_point: The game's ``'module:function'``.
        recording: The recording to replay.

    Returns:
        The command, as an argument list.

    """
    module, _separator, function = entry_point.partition(':')
    return [
        sys.executable,
        '-c',
        f'from {module} import {function}; {function}()',
        '--replay-trace',
        str(recording),
        '--headless',
        '--log-level',
        'warning',
    ]


class ReplayFile(pytest.File):
    """A recording under ``fixtures/replays/<console-script>/``: collects one ReplayItem."""

    @override
    def collect(self: Self) -> Iterator[ReplayItem]:
        """Yield the recording's item, after checking its directory names a console script.

        Yields:
            The recording's ReplayItem, named ``<console-script>/<name>``.

        Raises:
            pytest.Collector.CollectError: If the directory name is not an installed console
                script.

        """
        console_script = self.path.parent.name
        try:
            game_entry_point(console_script=console_script)
        except KeyError:
            message = (
                f'{self.path}: the directory {console_script!r} is not a console script; a '
                f'recording must be in {"/".join(REPLAY_FIXTURES_PATH_PARTS)}/<console-script>/, '
                'named after '
                "the game's [project.scripts] entry"
            )
            raise pytest.Collector.CollectError(message) from None
        name = self.path.name.removesuffix(RECORDING_SUFFIX)
        item_class: Any = ReplayItem  # see pytest_collect_file: from_parent's **kw is untyped
        item: ReplayItem = item_class.from_parent(parent=self, name=f'{console_script}/{name}')
        yield item


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
    """Collect ``.../fixtures/replays/<console-script>/<name>.jsonl.gz`` as a ReplayFile.

    Interface conformance: pytest's ``pytest_collect_file`` hook signature.

    Args:
        file_path: A file pytest found.
        parent: The directory's collector.

    Returns:
        The recording's collector, or None for any other file.

    """
    if not (
        file_path.name.endswith(RECORDING_SUFFIX)
        and file_path.parent.parent.parts[-len(REPLAY_FIXTURES_PATH_PARTS) :]
        == REPLAY_FIXTURES_PATH_PARTS
    ):
        return None
    # pytest's Node.from_parent takes untyped **kw, so the type checker sees it as partly
    # unknown; it is reached through Any and its result typed here
    file_class: Any = ReplayFile
    replay_file: ReplayFile = file_class.from_parent(parent=parent, path=file_path)
    return replay_file
