"""Shared helpers for replay tests: running a replay through the engine, editing a recording."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pygame
from scripts.record_golden_traces import (
    GAME_SCENES,
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    command_line,
)

from glitchygames.scenes import SceneManager
from glitchygames.tracing import read_trace_result, write_trace

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from pytest_mock import MockerFixture

    from glitchygames.replay import ReplayResult


def replay_through_engine(*, mocker: MockerFixture, game_key: str, path: Path) -> ReplayResult:
    """Replay a recording headless through the real engine loop and return its result.

    The replay is started the normal way, with ``--replay-trace`` (GameEngine.__init__ installs
    the ReplaySources, GameEngine.start runs SceneManager.start). Frame pacing is switched off:
    it only sleeps (the replay's frame times come from the recording), so the replay runs as fast
    as it can instead of in real time. pygame is left initialized for later tests on the worker.

    Args:
        mocker: pytest-mock's fixture.
        game_key: The game (a key of GAME_SCENES).
        path: The recording.

    Returns:
        The replay's result, settled by GameEngine._shutdown.

    """
    mocker.patch.object(SceneManager, '_handle_frame_pacing')
    # GameEngine._shutdown quits pygame; later tests on this worker still need it
    mocker.patch('pygame.quit')
    mocker.patch('pygame.display.quit')
    GoldenTraceSceneManager.install()
    try:
        with command_line(['--log-level', 'warning', '--replay-trace', str(path)]):
            engine = GoldenTraceEngine(game=GAME_SCENES[game_key])
        engine.start()
    finally:
        pygame.event.clear()
        GoldenTraceSceneManager.uninstall()
    sources = engine.replay_sources
    assert sources is not None
    return sources.result


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
