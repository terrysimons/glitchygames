"""A fatal signal ends the process at once, with a traceback, instead of hanging it forever.

pygame-ce installs a handler (its "parachute", ``pygame_parachute`` in src_c/base.c) for SIGSEGV,
SIGBUS, SIGFPE and SIGQUIT when ``pygame`` is first imported, on each still at its default. It
calls ``pygame.quit()`` before dying, which touches Python objects: on a thread that does not
hold the GIL (SDL's audio thread, Apple's audio code under it) it spins forever instead, and the
process never ends (bugs/2026-11-20-a-crash-on-the-audio-thread-hung-the-process.md: a native
driver run hung 3.5 hours). The engine (``report_fatal_signals_with_faulthandler``) puts those
signals back to their defaults and enables faulthandler, which prints every thread's traceback
and lets the signal end the process.

The child-process tests crash a thread that has released the GIL (``signal.pthread_kill``, as
the audio thread's crash arrives) after importing pygame, as every game and the test harness do.
A hang is a child still running at ``CRASH_DEADLINE_SECONDS``; ``run_command`` then kills it.
"""

from __future__ import annotations

import faulthandler
import os
import signal
import sys
import textwrap
import threading
from pathlib import Path

import pytest

from glitchygames.engine import game_engine as game_engine_module
from glitchygames.engine.game_engine import (
    FATAL_SIGNAL_NAMES,
    FatalSignalHandling,
    fatal_signals,
    report_fatal_signals_with_faulthandler,
)
from glitchygames.process import CompletedProcess, OutputCapture, TimeoutExpired, run_command

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

# A crashed child dies in well under a second once started; its start-up (pygame, the engine)
# takes a few seconds on a loaded machine. A hung child never ends: it is killed at this.
CRASH_DEADLINE_SECONDS = 60.0

# What faulthandler prints first for a segmentation fault (pygame's parachute prints
# "(pygame parachute) Segmentation Fault" when it gets that far, which it does not off the GIL)
FAULTHANDLER_SEGFAULT_LINE = 'Fatal Python error: Segmentation fault'

# The crash: a thread that has released the GIL (sleeping, as SDL's threads never hold it) is
# sent SIGSEGV, so the handler runs on it, as on the audio thread that crashed
CRASH_A_THREAD_WITHOUT_THE_GIL = textwrap.dedent(
    """
    import signal
    import threading
    import time

    started = threading.Event()

    def wait_without_the_gil():
        started.set()
        time.sleep(600)

    crashing = threading.Thread(target=wait_without_the_gil, daemon=True)
    crashing.start()
    started.wait()
    time.sleep(0.2)
    signal.pthread_kill(crashing.ident, signal.SIGSEGV)
    crashing.join()
    print('the process outlived its crash')
    """
)

# A game: pygame first (the import order ruff gives every game), then the engine is built
A_GAME_THAT_CRASHES = (
    textwrap.dedent(
        """
        import sys

        import pygame

        from glitchygames.replay.tools.golden_traces import GoldenTraceEngine
        from glitchygames.scenes import Scene


        class StillScene(Scene):
            NAME = 'Still'


        sys.argv = ['a-game-that-crashes', '--resolution', '320x240', '--log-level', 'error',
                    '--target-fps', '0', '--no-lucid-circuit']
        GoldenTraceEngine(game=StillScene)
        """
    )
    + CRASH_A_THREAD_WITHOUT_THE_GIL
)

# A test worker: the harness (the root conftest's first plugin) imports pygame at its top
A_TEST_WORKER_THAT_CRASHES = 'import tests.harness\n' + CRASH_A_THREAD_WITHOUT_THE_GIL

needs_pthread_kill = pytest.mark.skipif(
    not hasattr(signal, 'pthread_kill'),
    reason='signal.pthread_kill (sending a signal to one thread) is Unix only',
)


def run_crashing_child(*, source: str) -> CompletedProcess[str]:
    """Run ``source`` in a child Python from the repository root, failing the test if it hangs.

    Returns:
        The finished child (its output, stdout and stderr together).

    """
    try:
        return run_command(
            command=[sys.executable, '-c', source],
            environment=os.environ.copy(),
            working_directory=REPOSITORY_ROOT,
            timeout_seconds=CRASH_DEADLINE_SECONDS,
            capture_output=OutputCapture.TOGETHER,
        )
    except TimeoutExpired as timeout:
        pytest.fail(
            f'the child hung after its crash: still running at {CRASH_DEADLINE_SECONDS} s '
            f"(pygame's parachute on a thread without the GIL). Its output:\n{timeout.output}"
        )


def assert_ended_by_its_crash(*, child: CompletedProcess[str]) -> None:
    """Check the child died of SIGSEGV with faulthandler's traceback, not by surviving it."""
    assert child.returncode == -signal.SIGSEGV, child.stdout
    assert FAULTHANDLER_SEGFAULT_LINE in child.stdout
    assert 'the process outlived its crash' not in child.stdout


@needs_pthread_kill
def test_a_game_crashing_on_a_thread_without_the_gil_ends_at_once():
    """A game that imported pygame first and built its engine dies of the crash, not hangs."""
    child = run_crashing_child(source=A_GAME_THAT_CRASHES)

    assert_ended_by_its_crash(child=child)


@needs_pthread_kill
def test_a_test_worker_crashing_on_a_thread_without_the_gil_ends_at_once():
    """A process that loaded the test harness dies of the crash, so its test fails, not hangs."""
    child = run_crashing_child(source=A_TEST_WORKER_THAT_CRASHES)

    assert_ended_by_its_crash(child=child)


def test_the_fatal_signals_are_the_ones_pygames_parachute_takes():
    """SIGSEGV, SIGBUS, SIGFPE and SIGQUIT (pygame's fatal_signals[]), where the platform has it."""
    assert FATAL_SIGNAL_NAMES == ('SIGSEGV', 'SIGBUS', 'SIGFPE', 'SIGQUIT')
    assert fatal_signals() == [
        getattr(signal, name) for name in FATAL_SIGNAL_NAMES if hasattr(signal, name)
    ]


def test_an_enabled_faulthandler_is_left_as_it_is(mocker):
    """Someone already chose how crashes are reported (pytest does): nothing is changed."""
    set_handler = mocker.patch.object(game_engine_module.signal, 'signal')
    enable = mocker.patch.object(game_engine_module.faulthandler, 'enable')

    handling = report_fatal_signals_with_faulthandler()

    assert faulthandler.is_enabled()
    assert handling is FatalSignalHandling.ALREADY_REPORTED
    set_handler.assert_not_called()
    enable.assert_not_called()


def test_each_fatal_signal_goes_back_to_its_default_then_faulthandler_reports_it(mocker):
    """The parachute is dropped from every fatal signal before faulthandler takes them."""
    mocker.patch.object(game_engine_module.faulthandler, 'is_enabled', return_value=False)
    order: list[object] = []
    mocker.patch.object(
        game_engine_module.signal,
        'signal',
        side_effect=lambda number, handler: order.append((number, handler)),
    )
    mocker.patch.object(
        game_engine_module.faulthandler, 'enable', side_effect=lambda: order.append('enable')
    )

    handling = report_fatal_signals_with_faulthandler()

    assert handling is FatalSignalHandling.REPORTED
    assert order == [*((number, signal.SIG_DFL) for number in fatal_signals()), 'enable']


def test_a_stderr_faulthandler_cannot_write_to_still_drops_the_parachute(mocker):
    """No usable stderr (a windowed build's None): the crash still kills, without the traceback."""
    mocker.patch.object(game_engine_module.faulthandler, 'is_enabled', return_value=False)
    set_handler = mocker.patch.object(game_engine_module.signal, 'signal')
    mocker.patch.object(
        game_engine_module.faulthandler,
        'enable',
        side_effect=RuntimeError('sys.stderr is None'),
    )

    handling = report_fatal_signals_with_faulthandler()

    assert handling is FatalSignalHandling.DEFAULT_ONLY
    assert [call.args for call in set_handler.call_args_list] == [
        (number, signal.SIG_DFL) for number in fatal_signals()
    ]


def test_off_the_main_thread_nothing_is_changed(mocker):
    """Python sets signal handlers from the main thread only: another thread changes nothing."""
    mocker.patch.object(game_engine_module.faulthandler, 'is_enabled', return_value=False)
    set_handler = mocker.patch.object(game_engine_module.signal, 'signal')
    enable = mocker.patch.object(game_engine_module.faulthandler, 'enable')
    outcomes: list[FatalSignalHandling] = []

    worker = threading.Thread(
        target=lambda: outcomes.append(report_fatal_signals_with_faulthandler())
    )
    worker.start()
    worker.join()

    assert outcomes == [FatalSignalHandling.NOT_THE_MAIN_THREAD]
    set_handler.assert_not_called()
    enable.assert_not_called()
