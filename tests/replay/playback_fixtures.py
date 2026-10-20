"""Small scenes and a recorder for the playback scope's tests (a helper module, not tests)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self, override

import pygame

from glitchygames.randomness import random_stream
from glitchygames.recording import post_event
from glitchygames.state import open_saves
from tests.world.test_frame_integration import (
    CameraFreeScene,
    ScreenSprite,
    running_scene,
    step,
)

if TYPE_CHECKING:
    from pathlib import Path

    from glitchygames.scenes import Scene

COUNTING_STREAM_NAME = 'test.counting'
COUNTING_SAVE_NAMESPACE = 'counting'
COUNTING_SAVE_SLOT = 'slot'
# SavingCountingScene writes its slot on this tick
SAVING_TICK = 3
MARKER_TRAVEL = 100


class CountingScene(CameraFreeScene):
    """Counts its ticks and setups, and moves a marker by an engine stream draw every tick."""

    NAME = 'Counting'

    def __init__(
        self: Self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Start uncounted, with a screen-space marker the draws move.

        Args:
            options: The game's options.
            groups: The sprite group.

        """
        super().__init__(options=options, groups=groups)
        self.frames_ticked = 0
        self.setup_calls = 0
        self.marker = ScreenSprite()
        self.all_sprites.add(self.marker)

    @override
    def setup(self: Self) -> None:
        """Count the setup."""
        super().setup()
        self.setup_calls += 1

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Count the tick and move the marker by a draw (so a replay compares the stream)."""
        super().dt_tick(dt)
        self.frames_ticked += 1
        self.marker.rect.x = int(random_stream(COUNTING_STREAM_NAME).random() * MARKER_TRAVEL)


class SavingCountingScene(CountingScene):
    """Writes its save slot on its third tick, through the saves door."""

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Write the slot on the third tick."""
        super().dt_tick(dt)
        if self.frames_ticked == SAVING_TICK:
            open_saves(app_name=COUNTING_SAVE_NAMESPACE).save(COUNTING_SAVE_SLOT, {'value': 2})


class PostingCountingScene(CountingScene):
    """Posts an internal event every tick, as engine code would (Scene.on_user_event takes it)."""

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Post this tick's event."""
        super().dt_tick(dt)
        post_event(pygame.event.Event(pygame.USEREVENT, {'tick': self.frames_ticked}))


def record_counting_scene(
    *, tmp_path: Path, frames: int, scene_class: type[CountingScene] = CountingScene
) -> Path:
    """Record ``frames`` frames of a counting scene through the harness; return the file.

    The scene is built and switched to once recording has started, so it captures its start
    and frame 0 holds it, as a ``--record-trace`` run's first scene does.

    Args:
        tmp_path: Where the recording goes.
        frames: How many frames to record.
        scene_class: The counting scene to record.

    Returns:
        The recording's path.

    """
    recording_path = tmp_path / f'{scene_class.__name__}.jsonl.gz'
    with running_scene(CameraFreeScene) as manager:
        engine = manager.game_engine
        assert engine is not None
        engine.start_trace_recording(path=recording_path)
        manager.switch_to_scene(scene_class(options=engine.OPTIONS))
        step(manager, frames=frames)
        engine.stop_trace_recording()
    return recording_path


def active_counting_scene(manager: Any) -> CountingScene:
    """Return the active scene, checked to be a CountingScene.

    Args:
        manager: The running scene manager.

    Returns:
        The scene.

    """
    scene: Scene | None = manager.active_scene
    assert isinstance(scene, CountingScene)
    return scene
