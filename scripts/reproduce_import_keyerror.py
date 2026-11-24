"""Reproduce the import KeyError of bugs/2026-11-20-httpcore2-import-keyerror-on-windows.md.

importlib raises ``KeyError: '<module>'`` from ``_load_unlocked`` when a module's entry leaves
``sys.modules`` while the module's own code runs. Each mode imports a package fresh (``httpcore2``
by default: CircleCI's failure) many times, with something else going on, and tallies what each
import did:

MODE:
    restore-during-import   Another thread restores a ``sys.modules`` snapshot (as
                            ``mock.patch.dict(sys.modules)`` does when its patch ends) at a random
                            moment of the import. Reproduces the CI failure.
    two-importers           Two threads import the package at once; nothing else touches
                            ``sys.modules``. A control: every import succeeds.
    leftover-importer       A thread is importing when the main thread restores a snapshot, then
                            the main thread imports. The leftover's import may fail; the main
                            thread's succeeds (so CI's failing thread was not the restorer).

Usage (from the repository root):

    uv run python -m scripts.reproduce_import_keyerror MODE [--trials N] [--package NAME]

Prints one line per outcome, ``<count> <who>: <outcome>``, most frequent first. Exit status:
SUCCESS (0) when every import succeeded, REPLAY_DIVERGED (1, the "found something" code) when
any failed.
"""

from __future__ import annotations

import argparse
import collections
import random
import sys
import threading
import traceback
from unittest import mock

from glitchygames import clock
from glitchygames.exit_codes import ExitCode

# The command's one-line description
DESCRIPTION = 'Reproduce the import KeyError of CircleCI job 4241 (httpcore2, Windows).'

MODES = ('restore-during-import', 'two-importers', 'leftover-importer')

# The longest a restore waits into an import (an import of httpcore2 takes a few milliseconds)
LONGEST_RESTORE_DELAY_SECONDS = 0.03

# The outcome of an import that succeeded
SUCCEEDED = 'ok'


def forget(package: str) -> None:
    """Remove a package and its submodules from ``sys.modules``, so the next import is fresh."""
    for name in [name for name in sys.modules if name == package or name.startswith(f'{package}.')]:
        del sys.modules[name]


def import_outcome(package: str) -> str:
    """Import a package and describe what happened.

    Returns:
        ``ok``, or the exception's type and message and the innermost two frames it passed.

    """
    try:
        __import__(package)
    except Exception as error:  # ruff: ignore[blind-except] - every failure is tallied
        frames = traceback.extract_tb(error.__traceback__)[-2:]
        where = ' <- '.join(
            f'{frame.filename.rsplit("/", 1)[-1]}:{frame.lineno}' for frame in reversed(frames)
        )
        return f'{type(error).__name__}: {error} at {where}'
    return SUCCEEDED


def restore_during_import(*, package: str, trials: int, tally: collections.Counter[str]) -> None:
    """Restore a snapshot on another thread at a random moment of each import."""
    for _ in range(trials):
        forget(package)
        patcher = mock.patch.dict(sys.modules)
        patcher.start()
        delay = random.uniform(0, LONGEST_RESTORE_DELAY_SECONDS)  # ruff: ignore[suspicious-non-cryptographic-random-usage] - a timing jitter

        def restore(delay: float = delay, patcher: mock._patch_dict = patcher) -> None:  # type: ignore[reportPrivateUsage]
            clock.raw_sleep(delay)
            patcher.stop()

        restorer = threading.Thread(target=restore, daemon=True)
        restorer.start()
        tally[f'main: {import_outcome(package)}'] += 1
        restorer.join()


def two_importers(*, package: str, trials: int, tally: collections.Counter[str]) -> None:
    """Import on two threads at once, released together."""
    for _ in range(trials):
        forget(package)
        barrier = threading.Barrier(2)

        def importer(barrier: threading.Barrier = barrier) -> None:
            barrier.wait()
            tally[f'thread: {import_outcome(package)}'] += 1

        threads = [threading.Thread(target=importer) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()


def leftover_importer(*, package: str, trials: int, tally: collections.Counter[str]) -> None:
    """Restore a snapshot on the main thread while a thread imports, then import on the main."""
    for _ in range(trials):
        forget(package)
        patcher = mock.patch.dict(sys.modules)
        patcher.start()
        leftover = threading.Thread(
            target=lambda: tally.update([f'leftover: {import_outcome(package)}']), daemon=True
        )
        leftover.start()
        clock.raw_sleep(random.uniform(0, LONGEST_RESTORE_DELAY_SECONDS))  # ruff: ignore[suspicious-non-cryptographic-random-usage] - a timing jitter
        patcher.stop()
        tally[f'main: {import_outcome(package)}'] += 1
        leftover.join()


def main(argv: list[str] | None = None) -> int:
    """Run one mode and print its tally.

    Returns:
        SUCCESS when every import succeeded, REPLAY_DIVERGED when any failed.

    """
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument('mode', choices=MODES)
    parser.add_argument('--trials', type=int, default=300)
    parser.add_argument('--package', default='httpcore2')
    arguments = parser.parse_args(argv)
    tally: collections.Counter[str] = collections.Counter()
    run = {
        'restore-during-import': restore_during_import,
        'two-importers': two_importers,
        'leftover-importer': leftover_importer,
    }[arguments.mode]
    run(package=arguments.package, trials=arguments.trials, tally=tally)
    for outcome, count in tally.most_common():
        print(f'{count} {outcome}')  # ruff: ignore[print] - the tool's output
    failed = any(not outcome.endswith(f': {SUCCEEDED}') for outcome in tally)
    return ExitCode.REPLAY_DIVERGED if failed else ExitCode.SUCCESS


if __name__ == '__main__':
    sys.exit(main())
