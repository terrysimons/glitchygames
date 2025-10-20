"""Test scene lifecycle functionality.

This module tests the lifecycle of scenes including:
- Scene creation and initialization
- Scene activation and deactivation
- Scene transitions
- Scene cleanup and destruction
- Scene state management
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.scenes import Scene, SceneManager

from tests.mocks.test_mock_factory import MockFactory


class TestSceneLifecycle(unittest.TestCase):
    """Test scene lifecycle functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset singleton state for clean test
        SceneManager._instance = None
        
        # Use centralized mocks for pygame initialization
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all the patchers
        for patcher in self.patchers:
            patcher.start()
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()
        
        # Create a mock game scene class for the engine
        class MockGameScene(Scene):
            NAME = "MockGameScene"
            VERSION = "1.0"
            
            def __init__(self, options=None, groups=None):
                super().__init__(options=options, groups=groups)
        
        # Mock argparse to prevent command line argument parsing
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = self._create_mock_args()
            # Create a mock game engine to properly initialize SceneManager
            from glitchygames.engine import GameEngine
            self.engine = GameEngine(MockGameScene)
            # Set up the engine's OPTIONS
            self.engine.OPTIONS = {
                "update_type": "update",
                "fps_refresh_rate": 1000,
                "target_fps": 60,
                "font_name": "Arial",
                "font_size": 16
            }

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

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_scene_creation(self):
        """Test scene creation and initialization."""
        # Create a scene
        scene = Scene()

        # Verify scene properties
        assert scene.name is type(scene)
        assert scene.target_fps == 0
        assert scene.fps == 0
        assert scene.dt == 0
        assert scene.dirty == 1

    def test_scene_initialization(self):
        """Test scene initialization."""
        scene = Scene()

        # Verify basic initialization
        assert scene.target_fps == 0
        assert scene.fps == 0
        assert scene.dt == 0
        assert scene.dirty == 1
        assert scene.options == {"debug_events": False, "no_unhandled_events": False}
        assert scene.name is type(scene)

    def test_scene_cleanup(self):
        """Test scene cleanup."""
        scene = Scene()

        # Test cleanup method (should not raise exceptions)
        scene.cleanup()

    def test_scene_lifecycle_with_manager(self):
        """Test complete scene lifecycle with manager."""
        manager = self.engine.scene_manager
        scene = Scene()

        # Switch to scene using the correct API
        manager.switch_to_scene(scene)
        assert manager.active_scene == scene

    def test_scene_transition(self):
        """Test scene transition."""
        manager = self.engine.scene_manager
        scene1 = Scene()
        scene2 = Scene()

        # Switch to first scene
        manager.switch_to_scene(scene1)
        assert manager.active_scene == scene1

        # Transition to second scene
        manager.switch_to_scene(scene2)
        assert manager.active_scene == scene2

    def test_scene_destruction(self):
        """Test scene destruction and cleanup."""
        scene = Scene()

        # Test cleanup method
        scene.cleanup()

    def test_scene_state_persistence(self):
        """Test scene state persistence during transitions."""
        manager = self.engine.scene_manager
        scene1 = Scene()
        scene2 = Scene()

        # Set some state on scene1
        scene1.custom_data = "test_data"

        # Switch to scene1
        manager.switch_to_scene(scene1)
        assert manager.active_scene == scene1
        assert scene1.custom_data == "test_data"

        # Transition to scene2
        manager.switch_to_scene(scene2)
        assert manager.active_scene == scene2

        # Scene1 should retain its state
        assert scene1.custom_data == "test_data"

        # Transition back to scene1
        manager.switch_to_scene(scene1)
        assert manager.active_scene == scene1
        assert scene1.custom_data == "test_data"

    def test_scene_lifecycle_with_custom_methods(self):
        """Test scene lifecycle with custom methods."""
        class CustomScene(Scene):
            def __init__(self):
                super().__init__()
                self.custom_init_called = False
                self.custom_cleanup_called = False

            def custom_init(self):
                self.custom_init_called = True

            def custom_cleanup(self):
                self.custom_cleanup_called = True

        scene = CustomScene()

        # Test custom initialization
        scene.custom_init()
        assert scene.custom_init_called is True

        # Test custom cleanup
        scene.custom_cleanup()
        assert scene.custom_cleanup_called is True

        # Test standard lifecycle still works
        scene.cleanup()

    def test_scene_lifecycle_with_manager_integration(self):
        """Test scene lifecycle with full manager integration."""
        manager = self.engine.scene_manager

        # Create multiple scenes
        scene1 = Scene()
        scene2 = Scene()
        scene3 = Scene()

        # Test scene switching
        manager.switch_to_scene(scene1)
        assert manager.active_scene == scene1

        # Test scene transition
        manager.switch_to_scene(scene2)
        assert manager.active_scene == scene2

        # Test another transition
        manager.switch_to_scene(scene3)
        assert manager.active_scene == scene3
