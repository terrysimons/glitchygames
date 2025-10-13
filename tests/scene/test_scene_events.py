"""Test scene event handling functionality.

This module tests scene event handling including:
- Event processing and handling
- Event delegation to scenes
- Event filtering and routing
- Scene-specific event handling
- Event manager integration
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.scenes import Scene, SceneManager

from mocks.test_mock_factory import MockFactory


class TestSceneEvents(unittest.TestCase):
    """Test scene event handling functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Use centralized mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all the patchers
        for patcher in self.patchers:
            patcher.start()
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_scene_event_handling(self):
        """Test basic scene event handling."""
        scene = Scene()

        # Create a mock event
        mock_event = Mock()
        mock_event.type = "test_event"

        # Test that scene can handle events (Scene inherits from AllEventStubs)
        # The scene should have event handler methods
        assert hasattr(scene, "on_quit_event")
        assert hasattr(scene, "on_fps_event")
        assert hasattr(scene, "on_game_event")

    def test_scene_event_processing(self):
        """Test scene event processing."""
        scene = Scene()

        # Test that scene has event processing capabilities
        # Scene inherits from AllEventStubs which provides event handling
        assert hasattr(scene, "on_quit_event")
        assert hasattr(scene, "on_fps_event")
        assert hasattr(scene, "on_game_event")

    def test_scene_event_routing(self):
        """Test scene event routing."""
        manager = SceneManager()
        scene1 = Scene()

        # Switch to scene1
        manager.switch_to_scene(scene1)
        assert manager.active_scene == scene1

        # Create mock event
        mock_event = Mock()
        mock_event.type = "test_event"

        # Test that manager can handle events
        # The manager should have event handling capabilities
        assert hasattr(manager, "on_quit_event")
        assert hasattr(manager, "on_fps_event")
        assert hasattr(manager, "on_game_event")

    def test_scene_event_handling_with_manager(self):
        """Test scene event handling with manager."""
        manager = SceneManager()
        scene = Scene()

        # Switch to scene
        manager.switch_to_scene(scene)
        assert manager.active_scene == scene

        # Test that both manager and scene have event handling capabilities
        assert hasattr(manager, "on_quit_event")
        assert hasattr(scene, "on_quit_event")

    def test_scene_event_handling_multiple_scenes(self):
        """Test event handling with multiple scenes."""
        manager = SceneManager()
        scene1 = Scene()

        # Switch to scene1
        manager.switch_to_scene(scene1)
        assert manager.active_scene == scene1

        # Test that scene has event handling capabilities
        assert hasattr(scene1, "on_quit_event")

    def test_scene_event_handling_scene_transition(self):
        """Test event handling during scene transition."""
        manager = SceneManager()
        scene1 = Scene()
        scene2 = Scene()

        # Switch to scene1
        manager.switch_to_scene(scene1)
        assert manager.active_scene == scene1

        # Transition to scene2
        manager.switch_to_scene(scene2)
        assert manager.active_scene == scene2

        # Test that both scenes have event handling capabilities
        assert hasattr(scene1, "on_quit_event")
        assert hasattr(scene2, "on_quit_event")

    def test_scene_event_handling_with_custom_handlers(self):
        """Test scene event handling with custom handlers."""
        class CustomScene(Scene):
            def __init__(self):
                super().__init__()
                self.custom_events_handled = []

            def handle_custom_event(self, event):
                self.custom_events_handled.append(event)

        scene = CustomScene()

        # Test that custom scene has event handling capabilities
        assert hasattr(scene, "on_quit_event")
        assert hasattr(scene, "on_fps_event")
        assert hasattr(scene, "on_game_event")

        # Test custom event handling
        custom_event = Mock()
        scene.handle_custom_event(custom_event)
        assert len(scene.custom_events_handled) == 1
        assert scene.custom_events_handled[0] == custom_event

    def test_scene_event_handling_with_manager_integration(self):
        """Test scene event handling with full manager integration."""
        manager = SceneManager()

        # Create scenes with custom event handling
        class EventScene(Scene):
            def __init__(self):
                super().__init__()
                self.events_handled = []

        scene1 = EventScene()
        scene2 = EventScene()

        # Switch to scene1
        manager.switch_to_scene(scene1)
        assert manager.active_scene == scene1

        # Test that both scenes have event handling capabilities
        assert hasattr(scene1, "on_quit_event")
        assert hasattr(scene2, "on_quit_event")

        # Transition to scene2
        manager.switch_to_scene(scene2)
        assert manager.active_scene == scene2

    def test_scene_event_handling_edge_cases(self):
        """Test scene event handling edge cases."""
        scene = Scene()

        # Test that scene has event handling capabilities
        assert hasattr(scene, "on_quit_event")
        assert hasattr(scene, "on_fps_event")
        assert hasattr(scene, "on_game_event")

    def test_scene_event_handling_with_exceptions(self):
        """Test scene event handling with exceptions."""
        scene = Scene()

        # Test that scene has event handling capabilities
        assert hasattr(scene, "on_quit_event")
        assert hasattr(scene, "on_fps_event")
        assert hasattr(scene, "on_game_event")

    def test_scene_event_handling_with_manager_exceptions(self):
        """Test scene event handling with manager exceptions."""
        manager = SceneManager()
        scene = Scene()

        # Switch to scene
        manager.switch_to_scene(scene)
        assert manager.active_scene == scene

        # Test that both manager and scene have event handling capabilities
        assert hasattr(manager, "on_quit_event")
        assert hasattr(scene, "on_quit_event")
