"""
Test scene lifecycle functionality.

This module tests the lifecycle of scenes including:
- Scene creation and initialization
- Scene activation and deactivation
- Scene transitions
- Scene cleanup and destruction
- Scene state management
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from glitchygames.scenes import SceneManager, Scene


class TestSceneLifecycle:
    """Test scene lifecycle functionality."""

    def test_scene_creation(self, mock_pygame_patches):
        """Test scene creation and initialization."""
        # Create a scene
        scene = Scene()
        
        # Verify scene properties
        assert scene.name == type(scene)
        assert scene.target_fps == 0
        assert scene.fps == 0
        assert scene.dt == 0
        assert scene.dirty == 1

    def test_scene_initialization(self, mock_pygame_patches):
        """Test scene initialization."""
        scene = Scene()
        
        # Verify basic initialization
        assert scene.target_fps == 0
        assert scene.fps == 0
        assert scene.dt == 0
        assert scene.dirty == 1
        assert scene.options == {}
        assert scene.name == type(scene)

    def test_scene_cleanup(self, mock_pygame_patches):
        """Test scene cleanup."""
        scene = Scene()
        
        # Test cleanup method (should not raise exceptions)
        scene.cleanup()

    def test_scene_lifecycle_with_manager(self, mock_pygame_patches):
        """Test complete scene lifecycle with manager."""
        manager = SceneManager()
        scene = Scene()
        
        # Switch to scene using the correct API
        manager.switch_to_scene(scene)
        assert manager.active_scene == scene

    def test_scene_transition(self, mock_pygame_patches):
        """Test scene transition."""
        manager = SceneManager()
        scene1 = Scene()
        scene2 = Scene()
        
        # Switch to first scene
        manager.switch_to_scene(scene1)
        assert manager.active_scene == scene1
        
        # Transition to second scene
        manager.switch_to_scene(scene2)
        assert manager.active_scene == scene2

    def test_scene_destruction(self, mock_pygame_patches):
        """Test scene destruction and cleanup."""
        scene = Scene()
        
        # Test cleanup method
        scene.cleanup()

    def test_scene_state_persistence(self, mock_pygame_patches):
        """Test scene state persistence during transitions."""
        manager = SceneManager()
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

    def test_scene_lifecycle_with_custom_methods(self, mock_pygame_patches):
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

    def test_scene_lifecycle_with_manager_integration(self, mock_pygame_patches):
        """Test scene lifecycle with full manager integration."""
        manager = SceneManager()
        
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
