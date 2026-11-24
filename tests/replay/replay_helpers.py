"""Shared helpers for replay tests: running a replay through the engine, editing a recording."""

from __future__ import annotations

import dataclasses
import functools
import os
from typing import TYPE_CHECKING, Any

import pygame
import pytest

from glitchygames.replay.tools.golden_traces import (
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    command_line,
)
from glitchygames.tracing import read_trace_result, write_trace

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from pytest_mock import MockerFixture

    from glitchygames.replay import ReplayResult
    from glitchygames.scenes import Scene


def failing_the_test[**Parameters, Result](
    callback: Callable[Parameters, Result],
) -> Callable[Parameters, Result]:
    """Wrap a test callback that runs inside a game's run, so its failure fails the test itself.

    The engine reports any ``Exception`` raised during its run as ``ExitCode.INTERNAL_ERROR``
    (``_crash_boundary``), so a callback's own failed check (a patched flip, sleep or key press)
    read as the engine's 70: once, in a full-suite run, a test saw only that
    (bugs/2026-11-20-compare-trace-step-back-exited-internal-error-under-load.md). The wrapper
    turns the failure into ``pytest.fail``, whose exception is a ``BaseException`` the crash
    boundary passes through, so the test fails at once, with the callback's own message.

    Returns:
        The wrapped callback.

    """

    @functools.wraps(callback)
    def call(*args: Parameters.args, **kwargs: Parameters.kwargs) -> Result:
        try:
            return callback(*args, **kwargs)
        except Exception as error:
            name = getattr(callback, '__name__', repr(callback))
            message = (
                f'a test callback failed inside the run ({name}): {type(error).__name__}: {error}'
            )
            raise pytest.fail.Exception(message, pytrace=False) from error

    return call


@dataclasses.dataclass(frozen=True)
class EngineReplay:
    """How a replay through the engine ended.

    Attributes:
        exit_status: The status GameEngine.start() exited with (SystemExit's code).
        result: The replay's result, settled by GameEngine._shutdown.

    """

    exit_status: object
    result: ReplayResult


def replay_through_engine(
    *,
    mocker: MockerFixture,
    scene_class: type[Scene],
    path: Path,
    extra_arguments: tuple[str, ...] = (),
) -> EngineReplay:
    """Replay a recording through the real engine loop with ``--replay-trace PATH --headless``.

    The replay is started the normal way (GameEngine.__init__ installs the ReplaySources,
    GameEngine.start runs SceneManager.start), headless: unpaced, on SDL's dummy drivers, the
    report printed to stdout and the run ended with the replay's exit code. pygame is left
    initialized for later tests on the worker, and the SDL driver variables are restored.

    Args:
        mocker: pytest-mock's fixture.
        scene_class: The game's scene class.
        path: The recording.
        extra_arguments: More command-line arguments (``--rebaseline NEW``).

    Returns:
        The exit status and the result.

    """
    # GameEngine._shutdown quits pygame; later tests on this worker still need it
    mocker.patch('pygame.quit')
    mocker.patch('pygame.display.quit')
    # --headless sets the SDL driver variables; the test's own values come back afterwards
    mocker.patch.dict(os.environ)
    GoldenTraceSceneManager.install()
    try:
        with command_line([
            '--log-level',
            'warning',
            '--replay-trace',
            str(path),
            '--headless',
            *extra_arguments,
        ]):
            engine = GoldenTraceEngine(game=scene_class)
        with pytest.raises(SystemExit) as exit_info:
            engine.start()
    finally:
        pygame.event.clear()
        GoldenTraceSceneManager.uninstall()
    sources = engine.replay_sources
    assert sources is not None
    # A replay is not hosted: its viewer, or nothing when headless, is its outer game; see
    # glitchygames/host.py
    assert engine.host is None
    return EngineReplay(exit_status=exit_info.value.code, result=sources.result)


def rewrite_recording(*, recording_path: Path, change: Callable[[dict[str, Any]], None]) -> None:
    """Read a recording, let `change` edit the in-memory trace, write it back (format 3)."""
    trace = read_trace_result(path=recording_path).trace
    change(trace)
    write_trace(trace=trace, path=recording_path)


def tamper_first_sprite_rect(*, recording_path: Path, frame_number: int) -> None:
    """Move the first sprite 1 px down from `frame_number` on."""

    def move(trace: dict[str, Any]) -> None:
        for frame in trace['frames'][frame_number:]:
            if frame['sprites']:
                frame['sprites'][0]['rect'][1] += 1

    rewrite_recording(recording_path=recording_path, change=move)
