"""Run a scene headless in the golden-trace harness, for root tests and member tests.

Moved out of tests/world/test_frame_integration.py so member packages' tests import a
helper module, not a root test module.
"""

from __future__ import annotations

import contextlib
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pygame

from glitchygames.replay.tools.golden_traces import (
    RANDOM_SEED,
    SCREEN_RESOLUTION,
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    command_line,
    deterministic_environment,
)

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from glitchygames.scenes import Scene


@contextlib.contextmanager
def running_scene(
    scene_class: type[Scene], *, extra_arguments: Sequence[str] = ()
) -> Generator[GoldenTraceSceneManager]:
    """Start a scene headless in the harness's deterministic environment.

    Args:
        scene_class: The scene class to make active.
        extra_arguments: More command-line arguments (``--replay-trace PATH``).

    Yields:
        The scene manager with the scene active.

    """
    with (
        tempfile.TemporaryDirectory(prefix='frame-integration-saves-') as save_directory,
        deterministic_environment(save_root=Path(save_directory)),
    ):
        manager = GoldenTraceSceneManager.install()
        try:
            with command_line([
                '--windowed',
                '--resolution',
                SCREEN_RESOLUTION,
                '--log-level',
                'warning',
                '--random-seed',
                str(RANDOM_SEED),
                *extra_arguments,
            ]):
                engine = GoldenTraceEngine(game=scene_class)
            engine.install_game(scene_class=scene_class)
            yield manager
        finally:
            pygame.event.clear()
            GoldenTraceSceneManager.uninstall()
