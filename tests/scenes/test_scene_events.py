"""Test scene event handling functionality.

This module tests scene event handling including:
- Event processing and handling
- Event delegation to scenes
- Event filtering and routing
- Scene-specific event handling
- Event manager integration

Real scenes and the real SceneManager handle real events; QUIT posts go to pygame's real
event queue and are read back from it.
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames import events
from glitchygames.events.base import FPSEVENT, GAMEEVENT
from glitchygames.scenes import Scene, SceneManager
from glitchygames.testing.keys import qwerty_scancode


class RecordingScene(Scene):
    """A real scene that records the events its handlers receive, in order."""

    def __init__(self):
        """Start with no events handled."""
        super().__init__()
        self.handled_events: list[tuple[str, events.HashableEvent]] = []

    def on_key_down_event(self, event):
        """Record the key-down, then let the base scene handle it."""
        self.handled_events.append(('key_down', event))
        super().on_key_down_event(event)

    def on_mouse_motion_event(self, event):
        """Record the mouse motion."""
        self.handled_events.append(('mouse_motion', event))

    def on_fps_event(self, event):
        """Record the FPS event, then let the base scene store its FPS."""
        self.handled_events.append(('fps', event))
        super().on_fps_event(event)


def _key_down(key: int) -> events.HashableEvent:
    """Return a real KEYDOWN event for the key, with its US QWERTY scancode.

    Returns:
        events.HashableEvent: The event.

    """
    return events.HashableEvent(
        pygame.KEYDOWN, key=key, scancode=qwerty_scancode(key=key), mod=pygame.KMOD_NONE
    )


def _key_up(key: int) -> events.HashableEvent:
    """Return a real KEYUP event for the key, with its US QWERTY scancode.

    Returns:
        events.HashableEvent: The event.

    """
    return events.HashableEvent(
        pygame.KEYUP, key=key, scancode=qwerty_scancode(key=key), mod=pygame.KMOD_NONE
    )


def _take_quit_events() -> list[pygame.event.Event]:
    """Remove and return the QUIT events waiting in pygame's real event queue.

    Returns:
        list[pygame.event.Event]: The QUIT events.

    """
    return pygame.event.get(eventtype=pygame.QUIT)


class TestSceneEvents:
    """Test scene event handling functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Reset singleton state for clean test
        SceneManager._reset()
        self.scene_manager = SceneManager()
        _take_quit_events()

    def teardown_method(self):
        """Clean up test fixtures."""
        # Reset singleton state for clean test
        SceneManager._reset()
        _take_quit_events()

    def test_scene_event_handling(self):
        """A scene stores the FPS an FPS event carries."""
        scene = Scene()

        scene.on_fps_event(events.HashableEvent(FPSEVENT, fps=59.5))

        assert scene.fps == pytest.approx(59.5)

    def test_scene_event_processing(self):
        """Q down then up, routed by the manager, quits: QUIT reaches the real queue."""
        manager = self.scene_manager
        scene = Scene()
        manager.switch_to_scene(scene)

        manager.on_key_down_event(_key_down(pygame.K_q))
        assert _take_quit_events() == []  # the quit waits for the release

        manager.on_key_up_event(_key_up(pygame.K_q))

        assert len(_take_quit_events()) == 1

    def test_scene_event_routing(self):
        """The manager routes events it does not handle itself to the active scene."""
        manager = self.scene_manager
        scene1 = RecordingScene()
        manager.switch_to_scene(scene1)
        assert manager.active_scene == scene1
        motion = events.HashableEvent(
            pygame.MOUSEMOTION, pos=(10, 20), rel=(1, 2), buttons=(0, 0, 0)
        )

        manager.on_mouse_motion_event(motion)

        assert scene1.handled_events == [('mouse_motion', motion)]

    def test_scene_event_handling_with_manager(self):
        """The manager forwards FPS events to the active scene, which stores the FPS."""
        manager = self.scene_manager
        scene = RecordingScene()
        manager.switch_to_scene(scene)
        assert manager.active_scene == scene
        fps_event = events.HashableEvent(FPSEVENT, fps=30.0)

        manager.on_fps_event(fps_event)

        assert scene.handled_events == [('fps', fps_event)]
        assert scene.fps == pytest.approx(30.0)

    def test_scene_event_handling_multiple_scenes(self):
        """Only the active scene receives events: a scene not switched to hears nothing."""
        manager = self.scene_manager
        scene1 = RecordingScene()
        idle_scene = RecordingScene()
        manager.switch_to_scene(scene1)
        assert manager.active_scene == scene1

        manager.on_key_down_event(_key_down(pygame.K_a))

        assert [kind for kind, _ in scene1.handled_events] == ['key_down']
        assert idle_scene.handled_events == []

    def test_scene_event_handling_scene_transition(self):
        """After a switch, events go to the new scene and no longer to the old one."""
        manager = self.scene_manager
        scene1 = RecordingScene()
        scene2 = RecordingScene()
        manager.switch_to_scene(scene1)
        manager.on_key_down_event(_key_down(pygame.K_a))
        assert manager.active_scene == scene1

        manager.switch_to_scene(scene2)
        manager.on_key_down_event(_key_down(pygame.K_b))

        assert manager.active_scene == scene2
        assert [event.key for _, event in scene1.handled_events] == [pygame.K_a]
        assert [event.key for _, event in scene2.handled_events] == [pygame.K_b]

    def test_scene_event_handling_with_custom_handlers(self):
        """A scene's own on_*_event override receives the events the manager routes."""

        class CustomScene(Scene):
            def __init__(self):
                super().__init__()
                self.custom_events_handled = []

            def on_mouse_wheel_event(self, event):
                self.custom_events_handled.append(event)

        manager = self.scene_manager
        scene = CustomScene()
        manager.switch_to_scene(scene)
        wheel = events.HashableEvent(pygame.MOUSEWHEEL, x=0, y=1, flipped=False)

        manager.on_mouse_wheel_event(wheel)

        assert scene.custom_events_handled == [wheel]

    def test_scene_event_handling_with_manager_integration(self):
        """A QUIT event sets the manager's quit_requested; the scene's handler only logs it."""
        manager = self.scene_manager
        scene1 = RecordingScene()
        scene2 = RecordingScene()
        manager.switch_to_scene(scene1)
        manager.switch_to_scene(scene2)
        assert manager.active_scene == scene2
        assert manager.quit_requested is False

        manager.on_quit_event(events.HashableEvent(pygame.QUIT))

        assert manager.quit_requested is True

    def test_scene_event_handling_edge_cases(self):
        """A key release whose press the scene never saw does not quit, even for Q."""
        scene = Scene()

        scene.on_key_up_event(_key_up(pygame.K_q))

        assert _take_quit_events() == []

    def test_scene_event_handling_with_exceptions(self, caplog, mocker):
        """A game event of an unregistered subtype is logged as an error, not raised."""
        # Setting the manager's engine copies the engine's OPTIONS onto the SceneManager class
        mocker.patch.object(SceneManager, 'OPTIONS', SceneManager.OPTIONS)
        manager = self.scene_manager

        class EngineWithoutGameEvents:
            """An engine stand-in with no registered game events."""

            def __init__(self):
                """Hold the options a scene manager reads and no game events."""
                self.OPTIONS = {
                    'update_type': 'update',
                    'fps_log_interval_ms': 1000,
                    'target_fps': 60,
                }
                self.registered_events = {}

        manager.game_engine = EngineWithoutGameEvents()

        with caplog.at_level('ERROR'):
            manager.on_game_event(events.HashableEvent(GAMEEVENT, subtype=12345))

        assert 'Unregistered Event' in caplog.text

    def test_scene_event_handling_with_manager_exceptions(self):
        """The manager refuses attributes other than on_*_event handlers."""
        manager = self.scene_manager
        scene = Scene()
        manager.switch_to_scene(scene)
        assert manager.active_scene == scene

        with pytest.raises(AttributeError, match='no attribute'):
            _ = manager.not_an_event_handler
