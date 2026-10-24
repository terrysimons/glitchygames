#!/usr/bin/env python3
"""Tests for SceneManager timer-based frame pacing."""

from __future__ import annotations

import pygame
import pytest

from glitchygames.engine.game_engine import DEFAULT_TARGET_FPS
from glitchygames.scenes import Scene, SceneManager


@pytest.fixture(autouse=True)
def restore_scene_manager_options(mocker):
    """Put SceneManager.OPTIONS back after each test.

    Setting a scene manager's game_engine copies the engine's OPTIONS onto the SceneManager
    class; without this, the stand-in engines below would leave their options for later tests.
    """
    mocker.patch.object(SceneManager, 'OPTIONS', SceneManager.OPTIONS)


class PacedScene(Scene):
    """A real scene with a green background, run by the paced loop below."""

    NAME = 'PacedScene'

    def __init__(self):
        """Paint the background green so a rendered frame is visible on the display."""
        super().__init__()
        self.background_color = (0, 255, 0)
        self.ticks = 0

    def dt_tick(self, dt):
        """Count the logic ticks the loop ran."""
        super().dt_tick(dt)
        self.ticks += 1


class FakeTimer:
    """Fake timer for testing frame pacing without real delays."""

    def __init__(self) -> None:
        """Initialize the fake timer with call counters."""
        self.start_calls = 0
        self.start_frame_targets: list[float] = []
        self.compute_calls = 0
        self.sleep_calls = 0
        self._now = 0

    def ns_now(self) -> int:
        """Return a simulated current time, advancing 0.1 ms per call.

        Returns:
            The simulated current time in nanoseconds.

        """
        self._now += 100_000
        return self._now

    def start_frame(self, target_fps: float) -> int:
        """Record a start_frame call and return a 60 FPS period.

        Returns:
            The frame period in nanoseconds.

        """
        self.start_calls += 1
        self.start_frame_targets.append(target_fps)
        return 16_666_667

    def compute_deadline(self, prev_deadline_ns: int | None, period_ns: int) -> int:
        """Compute the next deadline, recording the call.

        Returns:
            The deadline in nanoseconds.

        """
        self.compute_calls += 1
        if prev_deadline_ns is None:
            return self.ns_now() + period_ns
        return prev_deadline_ns + period_ns

    def sleep_until_next(self, deadline_ns: int) -> int:
        """Simulate sleeping until the deadline, recording the call.

        Returns:
            The time in nanoseconds after sleeping.

        """
        self.sleep_calls += 1
        return deadline_ns


def test_scene_manager_uses_timer_for_pacing(monkeypatch, mocker):
    """Test that SceneManager delegates frame pacing to the timer backend."""
    sm = SceneManager()
    fake_timer = FakeTimer()
    engine_mock = mocker.Mock()
    engine_mock.OPTIONS = {
        'update_type': 'update',
        'fps_log_interval_ms': 1000,
        'target_fps': 60,
        'log_timer_jitter': False,
    }
    engine_mock.timer = fake_timer
    sm.game_engine = engine_mock
    sm.target_fps = 60

    # The stand-in engine has no event managers; every other frame step runs for real
    monkeypatch.setattr(sm, '_process_events', lambda: None)

    iterations = {'n': 0}

    def loop_guard(*args, **kwargs):
        iterations['n'] += 1
        if iterations['n'] >= 3:
            sm.quit_requested = True

    orig_update_display = sm._update_display

    def wrapped_update_display():
        orig_update_display()
        loop_guard()

    monkeypatch.setattr(sm, '_update_display', wrapped_update_display)

    scene = PacedScene()
    sm.switch_to_scene(scene)
    display = pygame.display.get_surface()
    display.fill((0, 0, 0))
    sm.start()

    assert fake_timer.start_calls >= 1
    assert fake_timer.compute_calls >= 1
    assert fake_timer.sleep_calls >= 1
    # Three real frames ran: three logic ticks, and the scene's background reached the display
    assert scene.ticks == 3
    assert tuple(display.get_at((400, 300)))[:3] == (0, 255, 0)


def test_scene_manager_falls_back_to_default_target_fps_when_option_missing(mocker):
    """Test that a missing target_fps option falls back to DEFAULT_TARGET_FPS."""
    sm = SceneManager()
    engine_mock = mocker.Mock()
    engine_mock.OPTIONS = {'update_type': 'update', 'fps_log_interval_ms': 1000}
    sm.game_engine = engine_mock

    assert sm.target_fps == DEFAULT_TARGET_FPS


def test_scene_manager_passes_fractional_target_fps_to_timer(monkeypatch, mocker):
    """Test that a fractional target FPS reaches start_frame without truncation."""
    sm = SceneManager()
    fake_timer = FakeTimer()
    engine_mock = mocker.Mock()
    engine_mock.OPTIONS = {
        'update_type': 'update',
        'fps_log_interval_ms': 1000,
        'target_fps': 60.5,
        'log_timer_jitter': False,
    }
    engine_mock.timer = fake_timer
    sm.game_engine = engine_mock
    sm.target_fps = 60.5

    # The stand-in engine has no event managers; every other frame step runs for real
    monkeypatch.setattr(sm, '_process_events', lambda: None)

    def stop_after_first_frame():
        sm.quit_requested = True

    monkeypatch.setattr(sm, '_update_display', stop_after_first_frame)

    sm.switch_to_scene(PacedScene())
    sm.start()

    assert fake_timer.start_frame_targets[0] == 60.5


def test_unpaced_frame_steps_never_touch_the_timer_or_the_pacing_clock(monkeypatch, mocker):
    """An outer driver's steps (paced=False) run real frames but never wait or calibrate.

    glitchygames/host.py's async runner waits for its own tick (a browser animation frame)
    between steps, so the step itself must neither ask the timer backend (whose first paced
    frame may measure the sleep model, sleeping) nor tick the pacing clock. The wait still
    counts in the next frame's start-to-start dt, as a pacing sleep does.
    """
    sm = SceneManager()
    fake_timer = FakeTimer()
    engine_mock = mocker.Mock()
    engine_mock.OPTIONS = {
        'update_type': 'update',
        'fps_log_interval_ms': 1000,
        'target_fps': 60,
        'log_timer_jitter': False,
    }
    engine_mock.timer = fake_timer
    sm.game_engine = engine_mock
    sm.target_fps = 60
    # The stand-in engine has no event managers; every other frame step runs for real
    monkeypatch.setattr(sm, '_process_events', lambda: None)
    # pygame.time.Clock's methods are read-only: wrap the clock to watch its tick
    sm.clock = mocker.Mock(wraps=sm.clock)
    scene = PacedScene()
    sm.switch_to_scene(scene)

    frame_start_seconds = sm.begin_frames()
    for _ in range(3):
        assert sm.should_run_frames()
        frame_start_seconds = sm.run_frame_step(
            frame_start_seconds=frame_start_seconds, paced=False
        )

    assert scene.ticks == 3
    assert fake_timer.start_calls == 0
    assert fake_timer.sleep_calls == 0
    sm.clock.tick.assert_not_called()
    # Each frame's dt is measured start to start, as in the paced loop
    assert sm.dt > 0


def test_frame_steps_end_with_end_frames(monkeypatch, mocker):
    """should_run_frames turns False once a quit is requested; end_frames terminates."""
    sm = SceneManager()
    engine_mock = mocker.Mock()
    engine_mock.OPTIONS = {'update_type': 'update', 'fps_log_interval_ms': 1000}
    engine_mock.timer = None
    sm.game_engine = engine_mock
    monkeypatch.setattr(sm, '_process_events', lambda: None)
    terminate = mocker.spy(sm, 'terminate')
    sm.switch_to_scene(PacedScene())

    frame_start_seconds = sm.begin_frames()
    sm.run_frame_step(frame_start_seconds=frame_start_seconds, paced=False)
    sm.quit_requested = True

    assert sm.should_run_frames() is False
    sm.end_frames()
    terminate.assert_called_once_with()
