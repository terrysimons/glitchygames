r"""A pytest plugin that runs recordings as regression tests.

A recording is collected as one test item, ``<console-script>/<name>``, from either of two
layouts (``recording_console_script`` tells which console script replays it):

- ``.../fixtures/replays/<console-script>/<name>.jsonl.gz`` (in this project, the engine's own
  ``tests/fixtures/replays/``; the directory is the game's console script from
  ``[project.scripts]``, for example ``paddleslap`` or ``clockwork-keep``);
- ``<member>/tests/fixtures/replays/<name>.jsonl.gz``, a workspace member's golden replays
  (``src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz``): the member's directory is
  named after its distribution, whose one console script replays them.

The item replays the recording headless through the real engine in a child process (started
with ``run_command``, glitchygames/process.py: the engine's one child-process launcher):

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
directory under ``fixtures/replays/`` that is not a console script, a recording directly in
``fixtures/replays/`` that is not in a ``tests/`` directory (another project's layout: the
plugin ships in the engine's wheel) or whose member (the directory above ``tests/``) is not an
installed distribution with exactly one console script, and a recording nested deeper than a game's
directory. A bookmarked copy (a header naming its source, ``bookmarked_copy_of``: what S
saves beside a recording a watched replay plays; glitchygames/replay/driver.py, rule 16) is not
collected.

The child replay is ``replay_recording_headless``, which other tests reuse: demos bundled in a
game's package (``glitchygames/examples/<game>_demos/<name>.jsonl.gz``, listed by
``bundled_demo_paths``) are outside the suite's directories, so tests/replay/test_bundled_demos.py
replays each one through it. ``rebaseline_recording_headless`` runs the same child with
``--rebaseline NEW`` (scripts/replay_metrics.py measures every recording through it).

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
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, Self, cast, override

import pytest

from glitchygames.exit_codes import ExitCode
from glitchygames.process import run_command, with_options_appended
from glitchygames.tracing import is_bookmarked_copy

if TYPE_CHECKING:
    from collections.abc import Iterator

    from glitchygames.process import CompletedProcess

RECORDING_SUFFIX = '.jsonl.gz'
# A recording is collected from .../fixtures/replays/<console-script>/<name>.jsonl.gz, or from a
# workspace member's <member>/tests/fixtures/replays/<name>.jsonl.gz
REPLAY_FIXTURES_PATH_PARTS = ('fixtures', 'replays')
# The directory a workspace member's fixtures/ is in: <member>/tests/
MEMBER_TESTS_DIRECTORY_NAME = 'tests'
REPLAY_FIXTURES_LAYOUT = (
    f'{"/".join(REPLAY_FIXTURES_PATH_PARTS)}/<console-script>/<name>{RECORDING_SUFFIX} '
    f"(a workspace member's: <member>/tests/{'/'.join(REPLAY_FIXTURES_PATH_PARTS)}/"
    f'<name>{RECORDING_SUFFIX})'
)
# The exit codes of a replay that refused its recording
UNUSABLE_RECORDING_EXIT_CODES = frozenset({ExitCode.UNUSABLE_INPUT, ExitCode.MISSING_INPUT})
CONSOLE_SCRIPTS_GROUP = 'console_scripts'
# Kill a replay child that runs longer than this (a headless replay of a few hundred frames
# takes a second or two)
REPLAY_TIMEOUT_SECONDS = 300.0
# Bundled demos: glitchygames/examples/<game>_demos/<name>.jsonl.gz, the game being the module
# glitchygames.examples.<game> (found by path, so this module imports no game)
BUNDLED_DEMO_DIRECTORY_SUFFIX = '_demos'
EXAMPLES_PACKAGE = 'glitchygames.examples'
EXAMPLES_DIRECTORY = Path(__file__).resolve().parent.parent / 'examples'


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


def recording_console_script(*, path: Path) -> str:
    """Return the console script that replays a recording under a ``fixtures/replays/`` directory.

    Two layouts: a workspace member's recordings lie directly in
    ``<member>/tests/fixtures/replays/`` and are replayed by the member distribution's one console
    script (the member's directory is named after its distribution: ``src/games/mr-muncher``);
    the engine's own (and the games not yet moved) lie in
    ``tests/fixtures/replays/<console-script>/``, whose folder names the script.

    Args:
        path: The recording.

    Returns:
        The console script's name.

    Raises:
        KeyError: If a recording directly in ``fixtures/replays/`` is not in a member's
            ``tests/`` (the directory above ``fixtures/`` is not ``tests``: another project's
            layout, whose directory four levels up names no member), the member's distribution
            is not installed or has not exactly one console script, or the folder names no
            installed console script.

    """
    if path.parent.parts[-len(REPLAY_FIXTURES_PATH_PARTS) :] == REPLAY_FIXTURES_PATH_PARTS:
        tests_directory = path.parent.parent.parent
        if tests_directory.name != MEMBER_TESTS_DIRECTORY_NAME:
            message = (
                f'{path}: a recording directly in {"/".join(REPLAY_FIXTURES_PATH_PARTS)}/ is a '
                f"workspace member's, in <member>/{MEMBER_TESTS_DIRECTORY_NAME}/, but the "
                f'directory above fixtures/ is {tests_directory.name!r}, not '
                f'{MEMBER_TESTS_DIRECTORY_NAME!r}'
            )
            raise KeyError(message)
        distribution_name = tests_directory.parent.name
        try:
            distribution = importlib.metadata.distribution(distribution_name)
        except importlib.metadata.PackageNotFoundError:
            message = (
                f'{path}: {distribution_name!r} is not an installed workspace member (a plain '
                '`uv sync` uninstalls members the root does not depend on); install every '
                'member with `uv sync --all-packages`'
            )
            raise KeyError(message) from None
        console_scripts = [
            entry_point.name
            for entry_point in distribution.entry_points
            if entry_point.group == CONSOLE_SCRIPTS_GROUP
        ]
        if len(console_scripts) != 1:
            message = (
                f'{path}: {distribution_name!r} has {len(console_scripts)} console scripts, not one'
            )
            raise KeyError(message)
        return console_scripts[0]
    try:
        game_entry_point(console_script=path.parent.name)
    except KeyError:
        message = f'{path}: the directory {path.parent.name!r} is not a console script'
        raise KeyError(message) from None
    return path.parent.name


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


def replay_recording_headless(*, console_script: str, path: Path) -> CompletedProcess[str]:
    """Replay a recording headless through a game's console script, in a child process.

    The child is ``replay_command``'s, started with ``run_command`` with this process's
    environment (``--headless`` puts it on SDL's dummy drivers). A child still running after
    REPLAY_TIMEOUT_SECONDS is killed, and run_command's ``subprocess.TimeoutExpired`` is raised.

    Args:
        console_script: The game's console script (``[project.scripts]``), for example
            ``paddleslap``.
        path: The recording.

    Returns:
        The finished child: ``returncode`` is the replay's ``ExitCode`` (``SUCCESS`` when every
        frame matched) and ``stdout`` its standard output and error together (the divergence
        report, or why the recording was refused).

    """
    entry_point = game_entry_point(console_script=console_script)
    return run_command(
        command=replay_command(entry_point=entry_point, recording=path),
        environment=os.environ,
        timeout_seconds=REPLAY_TIMEOUT_SECONDS,
        capture_output=True,
    )


def rebaseline_recording_headless(
    *, console_script: str, path: Path, new_path: Path
) -> CompletedProcess[str]:
    """Rebaseline a recording headless through a game's console script, in a child process.

    The child is ``replay_command``'s plus ``--rebaseline NEW`` (glitchygames/replay/rebaseline.py):
    it replays ``path`` on the current code, measuring each frame's processing time, and writes
    the run into ``new_path``. Started and timed out as ``replay_recording_headless`` is.

    Args:
        console_script: The game's console script (``[project.scripts]``).
        path: The recording.
        new_path: Where the rebaselined recording goes (never ``path``: refused).

    Returns:
        The finished child: ``returncode`` is the rebaseline's ``ExitCode`` and ``stdout`` its
        standard output and error together (the rebaseline's summary line).

    """
    entry_point = game_entry_point(console_script=console_script)
    return run_command(
        command=with_options_appended(
            arguments=replay_command(entry_point=entry_point, recording=path),
            appended=['--rebaseline', str(new_path)],
        ),
        environment=os.environ,
        timeout_seconds=REPLAY_TIMEOUT_SECONDS,
        capture_output=True,
    )


def bundled_demo_paths(*, examples_directory: Path = EXAMPLES_DIRECTORY) -> list[tuple[str, Path]]:
    """Return every demo bundled in a game's package, with the console script that replays it.

    A bundled demo is ``<examples_directory>/<game>_demos/<name>.jsonl.gz``; its game is the
    console script whose entry point lives in the module ``glitchygames.examples.<game>``.

    Args:
        examples_directory: Where the games' demo folders are (glitchygames/examples/).

    Returns:
        ``(console script, demo path)`` pairs, sorted by path.

    Raises:
        ValueError: If no installed console script's entry point is in a demo folder's game
            module (the demo could not be replayed, so it would go untested).

    """
    demos: list[tuple[str, Path]] = []
    for path in sorted(
        examples_directory.glob(f'*{BUNDLED_DEMO_DIRECTORY_SUFFIX}/*{RECORDING_SUFFIX}')
    ):
        game_module = (
            f'{EXAMPLES_PACKAGE}.{path.parent.name.removesuffix(BUNDLED_DEMO_DIRECTORY_SUFFIX)}'
        )
        console_script = console_script_in_module(module=game_module)
        if console_script is None:
            message = f'{path}: no console script has its entry point in {game_module}'
            raise ValueError(message)
        demos.append((console_script, path))
    return demos


def console_script_in_module(*, module: str) -> str | None:
    """Return the name of the first console script whose entry point is in a module.

    Distributions are searched as ``game_entry_point`` searches them, in ``sys.path`` order.

    Args:
        module: A module's dotted name, for example ``glitchygames.examples.paddleslap``.

    Returns:
        The console script's name, or None if no installed console script is in the module.

    """
    for distribution in importlib.metadata.distributions():
        for entry_point in distribution.entry_points.select(group=CONSOLE_SCRIPTS_GROUP):
            if entry_point.module == module:
                return entry_point.name
    return None


class ReplayFile(pytest.File):
    """A recording under ``fixtures/replays/``: collects one ReplayItem, or fails if misplaced."""

    @override
    def collect(self: Self) -> Iterator[ReplayItem]:
        """Yield the recording's item, after checking where it is.

        Yields:
            The recording's ReplayItem, named ``<console-script>/<name>``.

        Raises:
            pytest.Collector.CollectError: If the recording is in neither layout
                (``REPLAY_FIXTURES_LAYOUT``), or ``recording_console_script`` finds no console
                script for it.

        """
        width = len(REPLAY_FIXTURES_PATH_PARTS)
        if REPLAY_FIXTURES_PATH_PARTS not in {
            self.path.parent.parts[-width:],
            self.path.parent.parent.parts[-width:],
        }:
            message = f'{self.path}: recordings go in {REPLAY_FIXTURES_LAYOUT}'
            raise pytest.Collector.CollectError(message)
        try:
            console_script = recording_console_script(path=self.path)
        except KeyError as error:
            message = f'{error.args[0]}; recordings go in {REPLAY_FIXTURES_LAYOUT}'
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
        # ReplayFile.collect has checked the recording has a console script
        finished = replay_recording_headless(
            console_script=recording_console_script(path=self.path), path=self.path
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

    @override
    def reportinfo(self: Self) -> tuple[Path, int, str]:
        """Locate the item for reports: the recording, at its first line.

        pytest reports a skip made at the item's location (a skip marker, or pytest-benchmark's
        ``--benchmark-only`` skipping every non-benchmark item) at this line, and refuses None,
        the default for an item that is not a Python function.

        Returns:
            The recording's path, line 0 (the first) and the item's name.

        """
        return self.path, 0, self.name


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
    # A watched replay's S saves x.bookmarked.jsonl.gz beside a fixture it replays: a viewer's
    # copy, not a regression test of its own
    if is_bookmarked_copy(path=file_path):
        return None
    make_file = cast('ReplayFileFactory', ReplayFile.from_parent)
    return make_file(parent=parent, path=file_path)
