r"""A pytest plugin that runs recordings as regression tests.

A recording is collected as one test item, ``<console-script>/<name>``, from either of two
layouts (``recording_console_script`` tells which console script replays it):

- ``.../fixtures/replays/<console-script>/<name>.jsonl.gz``, another project's layout (the
  plugin ships in the engine's wheel; no game of this project's is there, every one is a
  workspace member): the directory is the game's console script from ``[project.scripts]``;
- ``<member>/tests/fixtures/replays/<name>.jsonl.gz``, a workspace member's golden replays
  (``src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz``): the member's directory is
  named after its distribution, whose console script replays them: its one (Brave Adventurer's
  is a launcher that starts the game the recording's header names), or, for a member with a
  console script per game, the one starting the game the recording's header names
  (``recorded_games_console_script``).

The item replays the recording headless through the real engine in a child process (started
with ``run_command``, glitchygames/process.py: the engine's one child-process launcher):

    <this interpreter> -c 'from importlib.metadata import EntryPoint; \
        EntryPoint(name=..., value=..., group=...).load()()' \
        --replay-trace <recording> --headless --log-level warning

where the entry point is the console script's (``game_entry_point``), loaded the way its
installed console script loads it. The console script lookups and the child replay live in
glitchygames/replay/tools/children.py (``recording_console_script``, ``replay_recording_headless``),
which the ``glitchygames`` command shares and which never imports pytest.
``--headless`` puts the child on SDL's dummy drivers and runs it unpaced, so the environment is
passed on unchanged. The item passes when the child exits ``ExitCode.SUCCESS`` (the replay matched
every frame); any other exit fails it with the exit code's name and the child's output (standard
output and error together), which holds the divergence report (``Replay diverged at frame N:
...``) or the reason the recording was refused (``ExitCode.UNUSABLE_INPUT`` and
``ExitCode.MISSING_INPUT`` are reported as an unusable recording). These fail at collection: a
directory under ``fixtures/replays/`` that is not a console script, a recording directly in
``fixtures/replays/`` that is not in a ``tests/`` directory (another project's layout: the
plugin ships in the engine's wheel) or whose member (the directory above ``tests/``) is not an
installed distribution with a console script that starts the recorded game, and a recording
nested deeper than a game's directory. A bookmarked copy (a header naming its source,
``bookmarked_copy_of``: what S saves beside a recording a watched replay plays;
glitchygames/replay/driver.py, rule 16) is not collected.

The child replay is ``replay_recording_headless``, which other tests reuse: demos bundled in a
workspace member's package (``<package>/demos/<name>.jsonl.gz``, found by
``glitchygames.bundled_demos``, listed by ``bundled_demo_paths``) are outside the suite's
directories, so tests/replay/test_bundled_demos.py replays each one through it.
``rebaseline_recording_headless`` runs the same child with ``--rebaseline NEW``
(``glitchygames.replay.tools.measure`` measures every recording through it).

Loading the plugin: ``pytest_plugins = ['glitchygames.testing.replays']`` in the root conftest
(this project's ``conftest.py``), or ``pytest -p glitchygames.testing.replays``. Recordings are
made by ``--record-trace``; this project's fixtures (each member's
``<member>/tests/fixtures/replays/``) are recorded by scripts/record_scripted_session.py.

The collector follows pytest's "Working with non-python tests" example
(https://docs.pytest.org/en/stable/example/nonpython.html).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self, cast, override

import pytest

from glitchygames.bundled_demos import bundled_demos
from glitchygames.exit_codes import ExitCode
from glitchygames.replay.tools.children import (
    REPLAY_FIXTURES_PATH_PARTS,
    recording_console_script,
    replay_recording_headless,
)
from glitchygames.tracing import is_bookmarked_copy

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

RECORDING_SUFFIX = '.jsonl.gz'
# A recording is collected from .../fixtures/replays/<console-script>/<name>.jsonl.gz, or from a
# workspace member's <member>/tests/fixtures/replays/<name>.jsonl.gz (REPLAY_FIXTURES_PATH_PARTS,
# glitchygames/replay/tools/children.py, with the console script lookup that reads them)
REPLAY_FIXTURES_LAYOUT = (
    f'{"/".join(REPLAY_FIXTURES_PATH_PARTS)}/<console-script>/<name>{RECORDING_SUFFIX} '
    f"(a workspace member's: <member>/tests/{'/'.join(REPLAY_FIXTURES_PATH_PARTS)}/"
    f'<name>{RECORDING_SUFFIX})'
)
# The exit codes of a replay that refused its recording
UNUSABLE_RECORDING_EXIT_CODES = frozenset({ExitCode.UNUSABLE_INPUT, ExitCode.MISSING_INPUT})


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


def bundled_demo_paths(*, packages: tuple[str, ...]) -> list[tuple[str, Path]]:
    """Return every demo bundled in an installed package, with the console script that replays it.

    The demos are ``glitchygames.bundled_demos.bundled_demos``'s (the one lookup, which
    ``glitchygames.replay.tools.recordings`` uses too); this caller's reaction to a demo no
    console script replays is to refuse it.

    Args:
        packages: The top-level import packages to search (there is no default, as
            ``bundled_demos`` has none).

    Returns:
        ``(console script, demo path)`` pairs, sorted by path.

    Raises:
        ValueError: If no installed console script's entry point is in the package holding a
            demo (the demo could not be replayed, so it would go untested).

    """
    pairs: list[tuple[str, Path]] = []
    for demo in bundled_demos(packages=packages):
        if demo.console_script is None:
            message = f'{demo.path}: no console script has its entry point in {demo.package}'
            raise ValueError(message)
        pairs.append((demo.console_script, demo.path))
    return pairs


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
