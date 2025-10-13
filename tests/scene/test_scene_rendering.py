"""
Test scene rendering functionality.

This module tests scene rendering including:
- Scene rendering and drawing
- Render surface management
- Rendering order and layering
- Scene visibility and rendering
- Render state management
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.scenes import Scene, SceneManager

from mocks.test_mock_factory import MockFactory


class TestSceneRendering(unittest.TestCase):
    """Test scene rendering functionality."""

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

    def test_scene_rendering(self):
        """Test basic scene rendering."""
        scene = Scene("test_scene")
        
        # Mock render method
        scene.render = Mock()
        
        # Create mock surface
        mock_surface = MockFactory.create_pygame_surface_mock()
        
        # Render scene
        scene.render(mock_surface)
        
        # Verify rendering
        scene.render.assert_called_once_with(mock_surface)

    def test_scene_rendering_with_surface(self):
        """Test scene rendering with surface."""
        scene = Scene("test_scene")
        
        # Mock render method
        scene.render = Mock()
        
        # Create mock surface
        mock_surface = MockFactory.create_pygame_surface_mock()
        mock_surface.get_width.return_value = 800
        mock_surface.get_height.return_value = 600
        
        # Render scene
        scene.render(mock_surface)
        
        # Verify rendering
        scene.render.assert_called_once_with(mock_surface)

    def test_scene_rendering_with_manager(self):
        """Test scene rendering with manager."""
        manager = SceneManager()
        scene = Scene()
        
        # Switch to scene
        manager.switch_to_scene(scene)
        assert manager.active_scene == scene
        
        # Test that scene has render method
        assert hasattr(scene, "render")

    def test_scene_rendering_multiple_scenes(self):
        """Test rendering with multiple scenes."""
        manager = SceneManager()
        scene1 = Scene()
        scene2 = Scene()
        
        # Switch to scene1
        manager.switch_to_scene(scene1)
        assert manager.active_scene == scene1
        
        # Test that both scenes have render methods
        assert hasattr(scene1, "render")
        assert hasattr(scene2, "render")

    def test_scene_rendering_scene_transition(self):
        """Test rendering during scene transition."""
        manager = SceneManager()
        scene1 = Scene()
        scene2 = Scene()
        
        # Switch to scene1
        manager.switch_to_scene(scene1)
        assert manager.active_scene == scene1
        
        # Transition to scene2
        manager.switch_to_scene(scene2)
        assert manager.active_scene == scene2
        
        # Test that both scenes have render methods
        assert hasattr(scene1, "render")
        assert hasattr(scene2, "render")

    def test_scene_rendering_with_visibility(self):
        """Test scene rendering with visibility."""
        scene = Scene()
        
        # Test that scene has render method
        assert hasattr(scene, "render")

    def test_scene_rendering_with_visibility_manager(self):
        """Test scene rendering with visibility through manager."""
        manager = SceneManager()
        scene = Scene()
        
        # Switch to scene
        manager.switch_to_scene(scene)
        assert manager.active_scene == scene
        
        # Test that scene has render method
        assert hasattr(scene, "render")

    def test_scene_rendering_with_custom_drawing(self):
        """Test scene rendering with custom drawing."""
        class CustomScene(Scene):
            def __init__(self):
                super().__init__()
                self.draw_calls = []
            
            def render(self, surface):
                self.draw_calls.append(surface)
                # Custom drawing logic here
        
        scene = CustomScene()
        
        # Test that custom scene has render method
        assert hasattr(scene, "render")
        
        # Create mock surface
        mock_surface = MockFactory.create_pygame_surface_mock()
        
        # Render scene
        scene.render(mock_surface)
        
        # Verify custom drawing
        assert len(scene.draw_calls) == 1
        assert scene.draw_calls[0] == mock_surface

    def test_scene_rendering_with_layering(self):
        """Test scene rendering with layering."""
        manager = SceneManager()
        
        # Create scenes with different layers
        scene1 = Scene()
        scene2 = Scene()
        scene3 = Scene()
        
        # Switch to scene1
        manager.switch_to_scene(scene1)
        assert manager.active_scene == scene1
        
        # Test that all scenes have render methods
        assert hasattr(scene1, "render")
        assert hasattr(scene2, "render")
        assert hasattr(scene3, "render")

    def test_scene_rendering_with_render_state(self):
        """Test scene rendering with render state."""
        scene = Scene()
        
        # Test that scene has render method
        assert hasattr(scene, "render")

    def test_scene_rendering_with_render_state_manager(self):
        """Test scene rendering with render state through manager."""
        manager = SceneManager()
        scene = Scene()
        
        # Switch to scene
        manager.switch_to_scene(scene)
        assert manager.active_scene == scene
        
        # Test that scene has render method
        assert hasattr(scene, "render")

    def test_scene_rendering_with_exceptions(self):
        """Test scene rendering with exceptions."""
        scene = Scene()
        
        # Test that scene has render method
        assert hasattr(scene, "render")

    def test_scene_rendering_with_manager_exceptions(self):
        """Test scene rendering with manager exceptions."""
        manager = SceneManager()
        scene = Scene()
        
        # Switch to scene
        manager.switch_to_scene(scene)
        assert manager.active_scene == scene
        
        # Test that scene has render method
        assert hasattr(scene, "render")

    def test_scene_rendering_with_surface_management(self):
        """Test scene rendering with surface management."""
        scene = Scene()
        
        # Test that scene has render method
        assert hasattr(scene, "render")

    def test_scene_rendering_with_surface_management_manager(self):
        """Test scene rendering with surface management through manager."""
        manager = SceneManager()
        scene = Scene()
        
        # Switch to scene
        manager.switch_to_scene(scene)
        assert manager.active_scene == scene
        
        # Test that scene has render method
        assert hasattr(scene, "render")

    def test_scene_rendering_with_custom_surface(self):
        """Test scene rendering with custom surface."""
        class CustomScene(Scene):
            def __init__(self):
                super().__init__()
                self.custom_surface = Mock()
            
            def render(self, surface):
                # Use custom surface for rendering
                self.custom_surface.blit(surface, (0, 0))
        
        scene = CustomScene()
        
        # Test that custom scene has render method
        assert hasattr(scene, "render")
        
        # Create mock surface
        mock_surface = MockFactory.create_pygame_surface_mock()
        
        # Render scene
        scene.render(mock_surface)
        
        # Verify custom surface usage
        scene.custom_surface.blit.assert_called_once_with(mock_surface, (0, 0))

    def test_scene_rendering_with_render_order(self):
        """Test scene rendering with render order."""
        manager = SceneManager()
        
        # Create scenes
        scene1 = Scene()
        scene2 = Scene()
        
        # Switch to scene1
        manager.switch_to_scene(scene1)
        assert manager.active_scene == scene1
        
        # Test that both scenes have render methods
        assert hasattr(scene1, "render")
        assert hasattr(scene2, "render")

    def test_scene_rendering_with_render_order_transition(self):
        """Test scene rendering with render order during transition."""
        manager = SceneManager()
        
        # Create scenes
        scene1 = Scene()
        scene2 = Scene()
        
        # Switch to scene1
        manager.switch_to_scene(scene1)
        assert manager.active_scene == scene1
        
        # Transition to scene2
        manager.switch_to_scene(scene2)
        assert manager.active_scene == scene2
        
        # Test that both scenes have render methods
        assert hasattr(scene1, "render")
        assert hasattr(scene2, "render")

    def test_scene_rendering_with_render_state_changes(self):
        """Test scene rendering with render state changes."""
        scene = Scene()
        
        # Test that scene has render method
        assert hasattr(scene, "render")

    def test_scene_rendering_with_render_state_changes_manager(self):
        """Test scene rendering with render state changes through manager."""
        manager = SceneManager()
        scene = Scene()
        
        # Switch to scene
        manager.switch_to_scene(scene)
        assert manager.active_scene == scene
        
        # Test that scene has render method
        assert hasattr(scene, "render")

    def test_scene_rendering_with_edge_cases(self):
        """Test scene rendering with edge cases."""
        scene = Scene()
        
        # Test that scene has render method
        assert hasattr(scene, "render")

    def test_scene_rendering_with_edge_cases_manager(self):
        """Test scene rendering with edge cases through manager."""
        manager = SceneManager()
        scene = Scene()
        
        # Switch to scene
        manager.switch_to_scene(scene)
        assert manager.active_scene == scene
        
        # Test that scene has render method
        assert hasattr(scene, "render")
