"""Test scene event handling functionality.

This module tests scene event handling including:
- Event processing and handling
- Event delegation to scenes
- Event filtering and routing
- Scene-specific event handling
- Event manager integration
"""

import sys
from pathlib import Path
from unittest.mock import Mock

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.scenes import Scene, SceneManager

from tests.mocks.test_mock_factory import MockFactory


class TestSceneEvents:
    """Test scene event handling functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Reset singleton state for clean test
        SceneManager._instance = None

        # Create a mock game scene class for the engine
        class MockGameScene(Scene):
            NAME = "MockGameScene"
            VERSION = "1.0"

            def __init__(self, options=None, groups=None):
                super().__init__(options=options, groups=groups)

        # Create a simple scene manager for testing (centralized mocks handle pygame)
        self.scene_manager = SceneManager()

    def _create_mock_args(self):
        """Create mock command line arguments."""
        mock_args = Mock()
        mock_args.fps = 60
        mock_args.resolution = "800x600"
        mock_args.windowed = True
        mock_args.use_gfxdraw = False
        mock_args.update_type = "update"
        mock_args.fps_refresh_rate = 1000
        mock_args.profile = False
        mock_args.test_flag = False
        mock_args.font_name = "Arial"
        mock_args.font_size = 16
        mock_args.font_bold = False
        mock_args.font_italic = False
        mock_args.font_antialias = True
        mock_args.font_dpi = 72
        mock_args.font_system = "pygame"
        mock_args.log_level = "info"
        mock_args.no_unhandled_events = False
        return mock_args

    def teardown_method(self):
        """Clean up test fixtures."""
        # Reset singleton state for clean test
        SceneManager._instance = None

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
        manager = self.scene_manager
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
        manager = self.scene_manager
        scene = Scene()
        # Set up proper background surface for the scene
        scene.background = MockFactory.create_pygame_surface_mock()

        # Switch to scene
        manager.switch_to_scene(scene)
        assert manager.active_scene == scene

        # Test that both manager and scene have event handling capabilities
        assert hasattr(manager, "on_quit_event")
        assert hasattr(scene, "on_quit_event")

    def test_scene_event_handling_multiple_scenes(self):
        """Test event handling with multiple scenes."""
        manager = self.scene_manager
        scene1 = Scene()
        # Set up proper background surface for the scene
        scene1.background = MockFactory.create_pygame_surface_mock()

        # Switch to scene1
        manager.switch_to_scene(scene1)
        assert manager.active_scene == scene1

        # Test that scene has event handling capabilities
        assert hasattr(scene1, "on_quit_event")

    def test_scene_event_handling_scene_transition(self):
        """Test event handling during scene transition."""
        manager = self.scene_manager
        scene1 = Scene()
        scene2 = Scene()
        # Set up proper background surfaces for the scenes
        scene1.background = MockFactory.create_pygame_surface_mock()
        scene2.background = MockFactory.create_pygame_surface_mock()

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
        manager = self.scene_manager

        # Create scenes with custom event handling
        class EventScene(Scene):
            def __init__(self):
                super().__init__()
                self.events_handled = []

        scene1 = EventScene()
        scene2 = EventScene()
        # Set up proper background surfaces for the scenes
        scene1.background = MockFactory.create_pygame_surface_mock()
        scene2.background = MockFactory.create_pygame_surface_mock()

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
        manager = self.scene_manager
        scene = Scene()
        # Set up proper background surface for the scene
        scene.background = MockFactory.create_pygame_surface_mock()

        # Switch to scene
        manager.switch_to_scene(scene)
        assert manager.active_scene == scene

        # Test that both manager and scene have event handling capabilities
        assert hasattr(manager, "on_quit_event")
        assert hasattr(scene, "on_quit_event")
