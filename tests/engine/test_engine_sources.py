"""The engine's doors (glitchygames/sources.py).

Live by default, swappable before the first frame, and the only way the frame loop reads events
and frame time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

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
    NoScopedSourcesError,
    SourcesAlreadyInstalledError,
    SourcesAlreadyRunningError,
    active_sources,
    advance_frame_clock,
    frame_clock_seconds,
    has_scoped_sources,
    install_sources,
    mark_frames_started,
    pop_scoped_sources,
    push_scoped_sources,
    reset_sources,
)
from glitchygames.supervision import BREAKPOINT_KIND

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from glitchygames.supervision import ControlEvent

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

    def end_frame(
        self: Self,
        *,
        frame_number: int,
        dt: float,
        scene: Scene | None,
        control_events: list[ControlEvent],
    ) -> None:
        self.ended_frames.append(frame_number)


class FrameCountingSupervisor:
    """A supervisor that records the frame number of each call."""

    def __init__(self: Self) -> None:
        """Create the supervisor with no calls recorded yet."""
        self.frame_numbers: list[int] = []

    def on_frame(self: Self, *, frame_number: int, scene: Scene | None) -> None:
        """Record the frame number."""
        del scene  # Supervisor signature; only the frame number is recorded
        self.frame_numbers.append(frame_number)


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

    def test_installing_over_earlier_sources_tells_the_earlier_ones(self):
        earlier_sources = ScriptedSources()
        later_sources = ScriptedSources()
        install_sources(sources=earlier_sources)
        install_sources(sources=later_sources)
        assert earlier_sources.uninstalled_calls == 1
        assert later_sources.installed_calls == 1
        assert later_sources.uninstalled_calls == 0
        assert active_sources() is later_sources

    def test_installing_the_same_sources_twice_is_refused(self):
        sources = ScriptedSources()
        install_sources(sources=sources)
        with pytest.raises(SourcesAlreadyInstalledError):
            install_sources(sources=sources)
        # Refused before telling them anything: still installed once, never uninstalled
        assert sources.installed_calls == 1
        assert sources.uninstalled_calls == 0
        assert active_sources() is sources

    def test_reset_tells_the_scoped_sources(self):
        installed_sources = ScriptedSources()
        scoped_sources = ScriptedSources()
        install_sources(sources=installed_sources)
        push_scoped_sources(sources=scoped_sources)
        assert active_sources() is scoped_sources
        reset_sources()
        assert scoped_sources.uninstalled_calls == 1
        assert installed_sources.uninstalled_calls == 1
        assert active_sources() is not scoped_sources

    def test_scoped_sources_are_active_until_popped_and_are_told(self):
        """Pushing is allowed after the first frame; popping returns to the installed doors."""
        installed_sources = ScriptedSources()
        scoped_sources = ScriptedSources()
        install_sources(sources=installed_sources)
        mark_frames_started()
        push_scoped_sources(sources=scoped_sources)
        assert active_sources() is scoped_sources
        assert has_scoped_sources()
        assert scoped_sources.installed_calls == 1
        assert pop_scoped_sources() is scoped_sources
        assert scoped_sources.uninstalled_calls == 1
        assert active_sources() is installed_sources
        assert not has_scoped_sources()
        # The installed doors were never told anything by the scope
        assert installed_sources.installed_calls == 1
        assert installed_sources.uninstalled_calls == 0

    def test_pushing_sources_already_in_use_is_refused(self):
        """Installed or already scoped sources would be told on_installed twice."""
        installed_sources = ScriptedSources()
        scoped_sources = ScriptedSources()
        install_sources(sources=installed_sources)
        push_scoped_sources(sources=scoped_sources)
        with pytest.raises(SourcesAlreadyInstalledError):
            push_scoped_sources(sources=installed_sources)
        with pytest.raises(SourcesAlreadyInstalledError):
            push_scoped_sources(sources=scoped_sources)
        assert installed_sources.installed_calls == 1
        assert scoped_sources.installed_calls == 1
        assert active_sources() is scoped_sources

    def test_popping_with_nothing_pushed_is_refused(self):
        with pytest.raises(NoScopedSourcesError):
            pop_scoped_sources()


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
                paced_seconds=None,
                processing_seconds=0.0,
            )
            assert manager.dt == 0.25
            assert closing > 0.0
            # The door got the measured start-to-start time (start was 0.0), once
            frame_seconds = sources.frame_seconds
            assert isinstance(frame_seconds, mocker.Mock)
            frame_seconds.assert_called_once_with(measured=pytest.approx(closing - 0.0))
        finally:
            GoldenTraceSceneManager.uninstall()

    def test_a_second_engine_starts_numbering_frames_and_the_clock_at_zero(self):
        manager = start_engine(scene_class=KeyCountingScene)
        try:
            for _ in range(3):
                manager.dt = FRAME_SECONDS
                manager.run_frame()
            advance_frame_clock(seconds=3 * FRAME_SECONDS)
            assert manager.frame_number == 3
            assert frame_clock_seconds() == 3 * FRAME_SECONDS

            # The same SceneManager singleton serves the next engine in this process
            with command_line(['--windowed', '--resolution', '320x240', '--log-level', 'warning']):
                GoldenTraceEngine(game=KeyCountingScene)

            assert manager.frame_number == 0
            assert frame_clock_seconds() == 0.0
        finally:
            GoldenTraceSceneManager.uninstall()

    def test_a_second_engine_starts_with_no_supervision(self, mocker: MockerFixture):
        manager = start_engine(scene_class=KeyCountingScene)
        try:
            supervisor = FrameCountingSupervisor()
            handled: list[ControlEvent] = []
            manager.add_supervisor(supervisor=supervisor)
            manager.add_control_event_handler(kind=BREAKPOINT_KIND, handler=handled.append)
            manager.dt = FRAME_SECONDS
            manager.run_frame()
            # Recorded after run 1's last frame ended: pending, never handed to an end_frame
            manager.record_control_event(kind=BREAKPOINT_KIND, data={'label': 'run 1'})
            assert supervisor.frame_numbers == [0]
            assert len(handled) == 1

            # The same SceneManager singleton serves the next engine in this process
            with command_line(['--windowed', '--resolution', '320x240', '--log-level', 'warning']):
                engine = GoldenTraceEngine(game=KeyCountingScene)
            engine.install_game(scene_class=KeyCountingScene)
            end_frame = mocker.spy(active_sources(), 'end_frame')
            manager.dt = FRAME_SECONDS
            manager.run_frame()
            manager.record_control_event(kind=BREAKPOINT_KIND, data={'label': 'run 2'})

            assert end_frame.call_args.kwargs['frame_number'] == 0
            assert end_frame.call_args.kwargs['control_events'] == []
            assert supervisor.frame_numbers == [0]
            assert len(handled) == 1
        finally:
            GoldenTraceSceneManager.uninstall()
