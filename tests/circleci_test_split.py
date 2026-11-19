"""Run one CircleCI machine's share of the suite, as CircleCI's splitter assigns it by timings.

One machine ran the whole suite on Linux and stopped at CircleCI's one-hour job limit (jobs 3705
and 3707: 60.4 and 60.6 minutes, one Python each). With ``parallelism: N`` CircleCI starts N
copies of a job (``CIRCLE_NODE_INDEX`` 0 to ``CIRCLE_NODE_TOTAL`` - 1), and each runs a share
(the owner, 2026-11-18: "yes", and "Do it for windows too").

On only when ``GLITCHYGAMES_TEST_SPLIT`` is ``circleci`` (the split CI jobs set it); unset, it
does nothing, and any other value stops the run. Before collection, every test file pytest would
collect is listed from the paths it was given (``candidate_test_files``: each ``python_files``
module and each golden replay, ``glitchygames.testing.replays``' rule, in directories pytest
recurses into), written to ``test-results/test-split-input-<pid>.txt`` and given to ``circleci
tests split --split-by=timings --timings-type=filename`` once (through
``glitchygames.process.run_command``). The files it returns are collected; every other listed
file is skipped before pytest imports it (``pytest_ignore_collect``). Each machine once
collected the whole suite and deselected the other half: importing every test module, and
keeping every deselected item, cost each machine about 150 MiB more than collecting its half
(2026-11-19, a 2 GB arm64 Ubuntu container; the owner: "Yes").

No test may fall outside every share. Every listed file goes to the splitter, and after
collection every collected test's file (``item.location[0]``: the name the JUnit report's
``file`` attribute carries) must be one listed: a file the listing missed stops the run, naming
it, rather than running on every machine unseen. CircleCI's timings come from the stored JUnit
reports, which carry each file's name under ``junit_family=xunit1`` (``noxfile.py`` sets it with
this variable); without timings the splitter divides by name.

Each machine runs its share alone, so none reaches the 100% coverage rule: the test session turns
the rule off with this variable, and a job after the split ones combines their coverage data and
applies it (``nox -s coverage-combine``).

The share is written to ``test-results/test-split.txt`` (the files sent, then the ones kept), for
the job's artifacts. Under pytest-xdist each worker collects and asks the splitter for the same
list (it divides the same input the same way), and only the first worker writes the file.
Registered in the root conftest.py's ``pytest_plugins``. Tests: tests/test_circleci_test_split.py.
"""

from __future__ import annotations

import fnmatch
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

from glitchygames.process import OutputCapture, run_command
from glitchygames.testing.replays import RECORDING_SUFFIX, is_under_replay_fixtures
from glitchygames.tracing import is_bookmarked_copy

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

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
# This machine's split, made as collection starts: every listed file, and the ones it keeps
_SPLIT_KEY: Final = pytest.StashKey[tuple[tuple[str, ...], frozenset[str]]]()


def _is_test_file(*, path: Path, python_files: Sequence[str]) -> bool:
    if any(fnmatch.fnmatch(path.name, pattern) for pattern in python_files):
        return True
    # A golden replay, as glitchygames.testing.replays' pytest_collect_file takes one
    return (
        path.name.endswith(RECORDING_SUFFIX)
        and is_under_replay_fixtures(directory=path.parent)
        and not is_bookmarked_copy(path=path)
    )


def _walk(*, directory: Path, norecursedirs: Sequence[str]) -> Iterator[Path]:
    for entry in sorted(directory.iterdir()):
        if entry.is_dir():
            # pytest's own skips: a norecursedirs name, or a virtual environment
            if any(fnmatch.fnmatch(entry.name, pattern) for pattern in norecursedirs):
                continue
            if (entry / 'pyvenv.cfg').is_file():
                continue
            yield from _walk(directory=entry, norecursedirs=norecursedirs)
        elif entry.is_file():
            yield entry


def _location_name(*, path: Path, root: Path) -> str:
    # As pytest's Item.location names a file (os.path.relpath from the rootdir): the names
    # the split lists, keeps and checks collected tests against must be the same strings. A
    # forward-slash name never matched a Windows location, so every Windows worker stopped
    # (CircleCI job 3919)
    return os.path.relpath(path, root)


def candidate_test_files(
    *,
    start_paths: Sequence[Path],
    root: Path,
    python_files: Sequence[str],
    norecursedirs: Sequence[str],
) -> list[str]:
    """Return every test file pytest would collect from the paths, without importing any.

    Args:
        start_paths: What pytest was given (its arguments, or ``testpaths``), resolved.
        root: The rootdir the names are relative to (as ``item.location[0]`` is).
        python_files: pytest's ``python_files`` patterns.
        norecursedirs: pytest's ``norecursedirs`` patterns (directory names, any depth).

    Returns:
        Each file once, named as pytest names a test's file (``item.location[0]``: relative to
        the root, with the platform's separators, so backslashes on Windows), in the order
        pytest finds them.

    """
    found: dict[str, None] = {}
    for start in start_paths:
        if start.is_file():
            files: Iterator[Path] = iter((start,))
        else:
            files = _walk(directory=start, norecursedirs=norecursedirs)
        for path in files:
            if path == start or _is_test_file(path=path, python_files=python_files):
                found[_location_name(path=path, root=root)] = None
    return list(found)


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


def _start_paths(config: pytest.Config) -> list[Path]:
    # config.args: the arguments, or testpaths when none were given, from the invocation folder
    invocation = config.invocation_params.dir
    return [(invocation / argument.split('::')[0]).resolve() for argument in config.args]


@pytest.hookimpl(tryfirst=True)
def pytest_collection(session: pytest.Session) -> None:
    """List every test file, and ask the splitter which this machine collects."""
    config = session.config
    if not _split_requested():
        return
    listed = candidate_test_files(
        start_paths=_start_paths(config),
        root=config.rootpath,
        python_files=config.getini('python_files'),
        norecursedirs=config.getini('norecursedirs'),
    )
    kept = split_files(collected_files=listed, run_splitter=run_circleci_splitter)
    _write_record(collected_files=listed, kept=kept)
    config.stash[_SPLIT_KEY] = (tuple(listed), kept)


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    """Skip a listed test file another machine runs, before pytest imports it.

    Returns:
        True to skip it; None leaves every other path to pytest.

    """
    split = config.stash.get(_SPLIT_KEY, None)
    if split is None or not collection_path.is_file():
        return None
    listed, kept = split
    # A path outside the rootdir is never listed under the name pytest would give it here
    if not collection_path.is_relative_to(config.rootpath):
        return None
    name = _location_name(path=collection_path, root=config.rootpath)
    if name in listed and name not in kept:
        return True
    return None


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Stop the run if a test was collected from a file the split never listed.

    Raises:
        pytest.UsageError: Naming each such file: no machine's share accounts for it.

    """
    split = config.stash.get(_SPLIT_KEY, None)
    if split is None:
        return
    listed = set(split[0])
    unlisted = sorted({item.location[0] for item in items} - listed)
    if unlisted:
        message = (
            'tests were collected from files the test split did not list (so no machine '
            f'accounts for them; tests/circleci_test_split.py): {", ".join(unlisted)}'
        )
        raise pytest.UsageError(message)
