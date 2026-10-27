"""Shared helpers for replay tests: running a replay through the engine, editing a recording."""

from __future__ import annotations

import dataclasses
import os
from typing import TYPE_CHECKING, Any

import pygame
import pytest
from scripts.record_golden_traces import GAME_SCENES

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
    game_key: str,
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
        game_key: The game (a key of GAME_SCENES).
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
            engine = GoldenTraceEngine(game=GAME_SCENES[game_key])
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
