#!/usr/bin/env python3
"""Tests for SceneManager timer-based frame pacing."""

from __future__ import annotations

from glitchygames.scenes import SceneManager
from tests.mocks.test_mock_factory import MockFactory


class FakeTimer:
    """Fake timer for testing frame pacing without real delays."""

    def __init__(self) -> None:
        """Initialize the fake timer with call counters."""
        self.start_calls = 0
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

    def start_frame(self, target_fps: int) -> int:
        """Record a start_frame call and return a 60 FPS period.

        Returns:
            The frame period in nanoseconds.

        """
        self.start_calls += 1
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

    monkeypatch.setattr(sm, '_update_scene', lambda: None)
    monkeypatch.setattr(sm, '_process_events', lambda: None)
    monkeypatch.setattr(sm, '_render_scene', lambda: None)
    monkeypatch.setattr(sm, '_update_display', lambda: None)

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

    sm.active_scene = MockFactory.create_event_test_scene_mock()
    sm.active_scene.next_scene = sm.active_scene
    sm.start()

    assert fake_timer.start_calls >= 1
    assert fake_timer.compute_calls >= 1
    assert fake_timer.sleep_calls >= 1
