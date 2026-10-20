"""Small scenes and a recorder for the playback scope's tests (a helper module, not tests)."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

import pygame
from scripts.record_golden_traces import discard_environment_events

from glitchygames.input.state import current_input
from glitchygames.randomness import random_stream
from glitchygames.recording import post_event
from glitchygames.replay.playback import start_playback_from_recording
from glitchygames.scenes import SceneManager
from glitchygames.state import open_saves
from glitchygames.transitions import FadeTransition
from tests.world.test_frame_integration import (
    TEST_FADE_SECONDS,
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
# QuittingCountingScene posts its QUIT on this tick
QUITTING_TICK = 3
# The switching scenes leave on this tick
SWITCHING_TICK = 3
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


class QuittingCountingScene(CountingScene):
    """Asks the game to quit on its third tick, as quit_game() does (an internal QUIT)."""

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Post a QUIT on the third tick."""
        super().dt_tick(dt)
        if self.frames_ticked == QUITTING_TICK:
            post_event(pygame.event.Event(pygame.QUIT, {}))


class InputReadingScene(CountingScene):
    """Keeps the polled mouse position each tick saw (dt_tick reads the frame's snapshot)."""

    def __init__(
        self: Self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Start with no positions seen.

        Args:
            options: The game's options.
            groups: The sprite group.

        """
        super().__init__(options=options, groups=groups)
        self.mouse_positions: list[tuple[int, int]] = []

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Keep the mouse position this tick saw."""
        super().dt_tick(dt)
        self.mouse_positions.append(current_input().mouse_position)


class SwitchingCountingScene(CountingScene):
    """Asks for a new CountingScene with next_scene on a tick (switched at the frame's end)."""

    SWITCH_TICK: ClassVar[int] = SWITCHING_TICK

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Request the next scene on SWITCH_TICK."""
        super().dt_tick(dt)
        if self.frames_ticked == self.SWITCH_TICK:
            self.next_scene = CountingScene(options=self.options)


class TransitioningCountingScene(CountingScene):
    """Fades to a new CountingScene on its third tick (it arrives by a transition)."""

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Start the fade on the third tick."""
        super().dt_tick(dt)
        if self.frames_ticked == SWITCHING_TICK:
            self.transition_to(
                CountingScene(options=self.options), FadeTransition(duration=TEST_FADE_SECONDS)
            )


class KeyReleaseCountingScene(CountingScene):
    """Moves its marker down a pixel per key release (so a lost or extra release diverges)."""

    @override
    def on_key_up_event(self: Self, event: Any) -> None:
        """Move the marker down for each release."""
        super().on_key_up_event(event)
        self.marker.rect.y += 1


class DemoLoopScene(KeyReleaseCountingScene):
    """A title screen that starts a demo each time it is set up, while demos are left."""

    def __init__(
        self: Self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Start with no demo to play.

        Args:
            options: The game's options.
            groups: The sprite group.

        """
        super().__init__(options=options, groups=groups)
        self.demo_path: Path | None = None
        self.demos_left = 0

    @override
    def setup(self: Self) -> None:
        """Start the next demo, returning here, while demos are left."""
        super().setup()
        if self.demo_path is not None and self.demos_left > 0:
            self.demos_left -= 1
            start_playback_from_recording(manager=SceneManager(), path=self.demo_path, then=self)


def step_finishing(manager: Any, *events: pygame.event.Event, frames: int = 1) -> None:
    """Run frames as SceneManager.start() does, _finish_frame included, without pacing.

    The frame clock advances and FPS events are posted (the frame time comes from the doors:
    tests patch the live doors' frame_seconds for a fixed dt).

    Args:
        manager: The running scene manager.
        *events: Events posted before the first frame.
        frames: How many frames to run.

    """
    for frame_index in range(frames):
        discard_environment_events()
        if frame_index == 0:
            for event in events:
                pygame.event.post(event)
        frame_start_seconds = time.perf_counter()
        manager.run_frame()
        manager._finish_frame(
            frame_start_seconds=frame_start_seconds,
            timer=None,
            period_ns=0,
            paced_seconds=0.0,
            processing_seconds=0.0,
        )


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
