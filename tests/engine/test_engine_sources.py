"""The engine's doors (glitchygames/sources.py).

Live by default, swappable before the first frame, and the only way the frame loop reads events
and frame time.
"""

from __future__ import annotations

from typing import Any, Self

import pygame
import pytest
from scripts.record_golden_traces import (
    FRAME_SECONDS,
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    command_line,
)

from glitchygames.live_sources import LiveSources
from glitchygames.scenes import Scene
from glitchygames.sources import (
    SourcesAlreadyRunningError,
    active_sources,
    install_sources,
    mark_frames_started,
    reset_sources,
)

SCRIPTED_KEY = pygame.K_x


class KeyCountingScene(Scene):
    """Counts the key-down events it receives."""

    def __init__(self: Self, options: dict[str, Any] | None = None, groups: Any = None) -> None:
        """Create the scene with no keys seen yet."""
        super().__init__(options=options, groups=groups)
        self.keys_seen: list[int] = []

    def on_key_down_event(self: Self, event: Any) -> None:
        self.keys_seen.append(event.key)


class ScriptedSources(LiveSources):
    """Live sources whose pump returns one scripted key press on the first pump only."""

    def __init__(self: Self) -> None:
        """Create the sources with nothing pumped, ended, installed or uninstalled yet."""
        super().__init__(random_seed=1)
        self.pump_count = 0
        self.ended_frames: list[int] = []
        self.installed_calls = 0
        self.uninstalled_calls = 0

    def on_installed(self: Self) -> None:
        self.installed_calls += 1

    def on_uninstalled(self: Self) -> None:
        self.uninstalled_calls += 1

    def pump_events(self: Self) -> list[pygame.event.Event]:
        self.pump_count += 1
        pygame.event.get()  # the real queue is drained and ignored
        if self.pump_count == 1:
            return [
                pygame.event.Event(
                    pygame.KEYDOWN, {'key': SCRIPTED_KEY, 'mod': 0, 'unicode': 'x', 'scancode': 27}
                )
            ]
        return []

    def end_frame(self: Self, *, frame_number: int, dt: float, scene: Scene | None) -> None:
        self.ended_frames.append(frame_number)


def start_engine(*, scene_class: type[Scene]) -> GoldenTraceSceneManager:
    """Start a golden-trace engine running ``scene_class`` and return its scene manager.

    Returns:
        The installed golden-trace scene manager.

    """
    manager = GoldenTraceSceneManager.install()
    with command_line(['--windowed', '--resolution', '320x240', '--log-level', 'warning']):
        engine = GoldenTraceEngine(game=scene_class)
    engine.install_game(scene_class=scene_class)
    return manager


class TestRegistry:
    """The registry: live by default, install, reset, and the first-frame lock."""

    def test_live_sources_are_the_default(self):
        assert isinstance(active_sources(), LiveSources)

    def test_installed_sources_become_active_and_are_told(self):
        sources = ScriptedSources()
        install_sources(sources=sources)
        assert active_sources() is sources
        assert sources.installed_calls == 1

    def test_reset_tells_the_installed_sources(self):
        sources = ScriptedSources()
        install_sources(sources=sources)
        reset_sources()
        assert sources.uninstalled_calls == 1
        assert active_sources() is not sources

    def test_install_after_the_first_frame_is_refused(self):
        mark_frames_started()
        with pytest.raises(SourcesAlreadyRunningError):
            install_sources(sources=ScriptedSources())


class TestFrameLoopUsesTheDoors:
    """The frame loop reads events and frame time and ends frames through the doors."""

    def test_events_come_from_the_installed_pump(self):
        manager = start_engine(scene_class=KeyCountingScene)
        try:
            sources = ScriptedSources()
            install_sources(sources=sources)
            manager.dt = FRAME_SECONDS
            manager.run_frame()
            scene = manager.active_scene
            assert isinstance(scene, KeyCountingScene)
            assert scene.keys_seen == [SCRIPTED_KEY]
            assert sources.pump_count == 1
        finally:
            GoldenTraceSceneManager.uninstall()

    def test_every_frame_ends_through_the_sources_with_its_number(self):
        manager = start_engine(scene_class=KeyCountingScene)
        try:
            sources = ScriptedSources()
            install_sources(sources=sources)
            for _ in range(3):
                manager.dt = FRAME_SECONDS
                manager.run_frame()
            assert sources.ended_frames == [0, 1, 2]
            assert manager.frame_number == 3
        finally:
            GoldenTraceSceneManager.uninstall()

    def test_frame_seconds_sets_dt(self, mocker):
        # GoldenTraceEngine.__init__ resets the doors, so install after constructing it
        manager = start_engine(scene_class=KeyCountingScene)
        try:
            sources = LiveSources(random_seed=1)
            mocker.patch.object(sources, 'frame_seconds', return_value=0.25)
            install_sources(sources=sources)
            closing = manager._finish_frame(
                frame_start_seconds=0.0,
                timer=None,
                period_ns=0,
                previous_deadline_ns=None,
                processing_seconds=0.0,
            )
            assert manager.dt == 0.25
            assert closing > 0.0
        finally:
            GoldenTraceSceneManager.uninstall()
