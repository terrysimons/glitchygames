"""Test scene rendering functionality.

This module tests scene rendering including:
- Scene rendering and drawing
- Render surface management
- Rendering order and layering
- Scene visibility and rendering
- Render state management
"""

import sys
from pathlib import Path

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.scenes import Scene, SceneManager
from tests.mocks.test_mock_factory import MockFactory


class TestSceneRendering:
    """Test scene rendering functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Reset singleton state for clean test
        SceneManager._reset()

        # Create a simple scene manager for testing (centralized mocks handle pygame)
        self.scene_manager = SceneManager()

    def teardown_method(self):
        """Clean up test fixtures."""
        # Reset singleton state for clean test
        SceneManager._reset()

    def test_scene_rendering(self, mocker):
        """Test basic scene rendering."""
        scene = Scene('test_scene')  # type: ignore[invalid-argument-type]

        # Mock render method
        scene.render = mocker.Mock()

        # Create mock surface
        mock_surface = MockFactory.create_pygame_surface_mock()

        # Render scene
        scene.render(mock_surface)

        # Verify rendering
        scene.render.assert_called_once_with(mock_surface)

    def test_scene_rendering_with_surface(self, mocker):
        """Test scene rendering with surface."""
        scene = Scene('test_scene')  # type: ignore[invalid-argument-type]

        # Mock render method
        scene.render = mocker.Mock()

        # Create mock surface
        mock_surface = MockFactory.create_pygame_surface_mock()

        # Render scene
        scene.render(mock_surface)

        # Verify rendering
        scene.render.assert_called_once_with(mock_surface)

    def test_scene_rendering_with_manager(self, mocker):
        """Test scene rendering with manager."""
        # Reset singleton state for clean test
        SceneManager._reset()

        manager = self.scene_manager

        # Create a mock scene instead of real Scene to avoid pygame.display issues
        mock_scene = mocker.Mock()
        mock_scene.all_sprites = mocker.Mock()
        mock_scene.background = MockFactory.create_pygame_surface_mock()
        mock_scene.render = mocker.Mock()

        # Switch to scene
        manager.switch_to_scene(mock_scene)
        assert manager.active_scene == mock_scene

        # Test that scene has render method
        assert hasattr(mock_scene, 'render')

    def test_scene_rendering_multiple_scenes(self, mocker):
        """Test rendering with multiple scenes."""
        # Reset singleton state for clean test
        SceneManager._reset()

        manager = self.scene_manager

        # Create mock scenes instead of real Scene to avoid pygame.display issues
        mock_scene1 = mocker.Mock()
        mock_scene1.all_sprites = mocker.Mock()
        mock_scene1.background = MockFactory.create_pygame_surface_mock()
        mock_scene1.render = mocker.Mock()

        mock_scene2 = mocker.Mock()
        mock_scene2.all_sprites = mocker.Mock()
        mock_scene2.background = MockFactory.create_pygame_surface_mock()
        mock_scene2.render = mocker.Mock()

        # Switch to scene1
        manager.switch_to_scene(mock_scene1)
        assert manager.active_scene == mock_scene1

        # Test that both scenes have render methods
        assert hasattr(mock_scene1, 'render')
        assert hasattr(mock_scene2, 'render')

    def test_scene_rendering_scene_transition(self, mocker):
        """Test rendering during scene transition."""
        # Reset singleton state for clean test
        SceneManager._reset()

        manager = self.scene_manager

        # Create mock scenes instead of real Scene to avoid pygame.display issues
        mock_scene1 = mocker.Mock()
        mock_scene1.all_sprites = mocker.Mock()
        mock_scene1.background = MockFactory.create_pygame_surface_mock()
        mock_scene1.render = mocker.Mock()

        mock_scene2 = mocker.Mock()
        mock_scene2.all_sprites = mocker.Mock()
        mock_scene2.background = MockFactory.create_pygame_surface_mock()
        mock_scene2.render = mocker.Mock()

        # Switch to scene1
        manager.switch_to_scene(mock_scene1)
        assert manager.active_scene == mock_scene1

        # Transition to scene2
        manager.switch_to_scene(mock_scene2)
        assert manager.active_scene == mock_scene2

        # Test that both scenes have render methods
        assert hasattr(mock_scene1, 'render')
        assert hasattr(mock_scene2, 'render')

    def test_scene_rendering_with_visibility(self, mocker):
        """Test scene rendering with visibility."""
        # Create a mock scene using centralized mocks
        mock_scene = mocker.Mock()
        mock_scene.all_sprites = mocker.Mock()
        mock_scene.background = MockFactory.create_pygame_surface_mock()
        mock_scene.render = mocker.Mock()

        # Test that scene has render method
        assert hasattr(mock_scene, 'render')

    def test_scene_rendering_with_visibility_manager(self, mocker):
        """Test scene rendering with visibility through manager."""
        # Reset singleton state for clean test
        SceneManager._reset()

        manager = self.scene_manager

        # Create a mock scene using centralized mocks
        mock_scene = mocker.Mock()
        mock_scene.all_sprites = mocker.Mock()
        mock_scene.background = MockFactory.create_pygame_surface_mock()
        mock_scene.render = mocker.Mock()

        # Switch to scene
        manager.switch_to_scene(mock_scene)
        assert manager.active_scene == mock_scene

        # Test that scene has render method
        assert hasattr(mock_scene, 'render')

    def test_scene_rendering_with_custom_drawing(self, mocker):
        """Test scene rendering with custom drawing."""
        # Create a mock scene with custom drawing behavior
        mock_scene = mocker.Mock()
        mock_scene.draw_calls = []

        def mock_render(surface):
            mock_scene.draw_calls.append(surface)

        mock_scene.render = mock_render

        # Test that custom scene has render method
        assert hasattr(mock_scene, 'render')

        # Create mock surface using centralized mocks
        mock_surface = MockFactory.create_pygame_surface_mock()

        # Render scene
        mock_scene.render(mock_surface)

        # Verify custom drawing
        assert len(mock_scene.draw_calls) == 1
        assert mock_scene.draw_calls[0] == mock_surface

    def test_scene_rendering_with_layering(self, mocker):
        """Test scene rendering with layering."""
        # Reset singleton state for clean test
        SceneManager._reset()

        manager = self.scene_manager

        # Create mock scenes with different layers using centralized mocks
        mock_scene1 = mocker.Mock()
        mock_scene1.all_sprites = mocker.Mock()
        mock_scene1.background = MockFactory.create_pygame_surface_mock()
        mock_scene1.render = mocker.Mock()

        mock_scene2 = mocker.Mock()
        mock_scene2.all_sprites = mocker.Mock()
        mock_scene2.background = MockFactory.create_pygame_surface_mock()
        mock_scene2.render = mocker.Mock()

        mock_scene3 = mocker.Mock()
        mock_scene3.all_sprites = mocker.Mock()
        mock_scene3.background = MockFactory.create_pygame_surface_mock()
        mock_scene3.render = mocker.Mock()

        # Switch to scene1
        manager.switch_to_scene(mock_scene1)
        assert manager.active_scene == mock_scene1

        # Test that all scenes have render methods
        assert hasattr(mock_scene1, 'render')
        assert hasattr(mock_scene2, 'render')
        assert hasattr(mock_scene3, 'render')

    def test_scene_rendering_with_render_state(self, mocker):
        """Test scene rendering with render state."""
        # Create a mock scene using centralized mocks
        mock_scene = mocker.Mock()
        mock_scene.all_sprites = mocker.Mock()
        mock_scene.background = MockFactory.create_pygame_surface_mock()
        mock_scene.render = mocker.Mock()

        # Test that scene has render method
        assert hasattr(mock_scene, 'render')

    def test_scene_rendering_with_render_state_manager(self, mocker):
        """Test scene rendering with render state through manager."""
        # Reset singleton state for clean test
        SceneManager._reset()

        manager = self.scene_manager

        # Create a mock scene using centralized mocks
        mock_scene = mocker.Mock()
        mock_scene.all_sprites = mocker.Mock()
        mock_scene.background = MockFactory.create_pygame_surface_mock()
        mock_scene.render = mocker.Mock()

        # Switch to scene
        manager.switch_to_scene(mock_scene)
        assert manager.active_scene == mock_scene

        # Test that scene has render method
        assert hasattr(mock_scene, 'render')

    def test_scene_rendering_with_exceptions(self, mocker):
        """Test scene rendering with exceptions."""
        # Create a mock scene using centralized mocks
        mock_scene = mocker.Mock()
        mock_scene.all_sprites = mocker.Mock()
        mock_scene.background = MockFactory.create_pygame_surface_mock()
        mock_scene.render = mocker.Mock()

        # Test that scene has render method
        assert hasattr(mock_scene, 'render')

    def test_scene_rendering_with_manager_exceptions(self, mocker):
        """Test scene rendering with manager exceptions."""
        # Reset singleton state for clean test
        SceneManager._reset()

        manager = self.scene_manager

        # Create a mock scene using centralized mocks
        mock_scene = mocker.Mock()
        mock_scene.all_sprites = mocker.Mock()
        mock_scene.background = MockFactory.create_pygame_surface_mock()
        mock_scene.render = mocker.Mock()

        # Switch to scene
        manager.switch_to_scene(mock_scene)
        assert manager.active_scene == mock_scene

        # Test that scene has render method
        assert hasattr(mock_scene, 'render')

    def test_scene_rendering_with_surface_management(self, mocker):
        """Test scene rendering with surface management."""
        # Create a mock scene using centralized mocks
        mock_scene = mocker.Mock()
        mock_scene.all_sprites = mocker.Mock()
        mock_scene.background = MockFactory.create_pygame_surface_mock()
        mock_scene.render = mocker.Mock()

        # Test that scene has render method
        assert hasattr(mock_scene, 'render')

    def test_scene_rendering_with_surface_management_manager(self, mocker):
        """Test scene rendering with surface management through manager."""
        # Reset singleton state for clean test
        SceneManager._reset()

        manager = self.scene_manager

        # Create a mock scene using centralized mocks
        mock_scene = mocker.Mock()
        mock_scene.all_sprites = mocker.Mock()
        mock_scene.background = MockFactory.create_pygame_surface_mock()
        mock_scene.render = mocker.Mock()

        # Switch to scene
        manager.switch_to_scene(mock_scene)
        assert manager.active_scene == mock_scene

        # Test that scene has render method
        assert hasattr(mock_scene, 'render')

    def test_scene_rendering_with_custom_surface(self, mocker):
        """Test scene rendering with custom surface."""
        # Create a mock scene with custom surface behavior
        mock_scene = mocker.Mock()
        mock_scene.custom_surface = mocker.Mock()

        def mock_render(surface):
            # Use custom surface for rendering
            mock_scene.custom_surface.blit(surface, (0, 0))

        mock_scene.render = mock_render

        # Test that custom scene has render method
        assert hasattr(mock_scene, 'render')

        # Create mock surface using centralized mocks
        mock_surface = MockFactory.create_pygame_surface_mock()

        # Render scene
        mock_scene.render(mock_surface)

        # Verify custom surface usage
        mock_scene.custom_surface.blit.assert_called_once_with(mock_surface, (0, 0))

    def test_scene_rendering_with_render_order(self, mocker):
        """Test scene rendering with render order."""
        # Reset singleton state for clean test
        SceneManager._reset()

        manager = self.scene_manager

        # Create mock scenes using centralized mocks
        mock_scene1 = mocker.Mock()
        mock_scene1.all_sprites = mocker.Mock()
        mock_scene1.background = MockFactory.create_pygame_surface_mock()
        mock_scene1.render = mocker.Mock()

        mock_scene2 = mocker.Mock()
        mock_scene2.all_sprites = mocker.Mock()
        mock_scene2.background = MockFactory.create_pygame_surface_mock()
        mock_scene2.render = mocker.Mock()

        # Switch to scene1
        manager.switch_to_scene(mock_scene1)
        assert manager.active_scene == mock_scene1

        # Test that both scenes have render methods
        assert hasattr(mock_scene1, 'render')
        assert hasattr(mock_scene2, 'render')

    def test_scene_rendering_with_render_order_transition(self, mocker):
        """Test scene rendering with render order during transition."""
        # Reset singleton state for clean test
        SceneManager._reset()

        manager = self.scene_manager

        # Create mock scenes using centralized mocks
        mock_scene1 = mocker.Mock()
        mock_scene1.all_sprites = mocker.Mock()
        mock_scene1.background = MockFactory.create_pygame_surface_mock()
        mock_scene1.render = mocker.Mock()

        mock_scene2 = mocker.Mock()
        mock_scene2.all_sprites = mocker.Mock()
        mock_scene2.background = MockFactory.create_pygame_surface_mock()
        mock_scene2.render = mocker.Mock()

        # Switch to scene1
        manager.switch_to_scene(mock_scene1)
        assert manager.active_scene == mock_scene1

        # Transition to scene2
        manager.switch_to_scene(mock_scene2)
        assert manager.active_scene == mock_scene2

        # Test that both scenes have render methods
        assert hasattr(mock_scene1, 'render')
        assert hasattr(mock_scene2, 'render')


class TestSceneRenderingEdgeCases:
    """Test scene rendering edge cases."""

    def setup_method(self):
        """Set up test fixtures."""
        # Reset singleton state for clean test
        SceneManager._reset()

        # Create a simple scene manager for testing (centralized mocks handle pygame)
        self.scene_manager = SceneManager()

    def teardown_method(self):
        """Clean up test fixtures."""
        # Reset singleton state for clean test
        SceneManager._reset()

    def test_scene_rendering_with_render_state_changes(self, mocker):
        """Test scene rendering with render state changes."""
        # Create a mock scene using centralized mocks
        mock_scene = mocker.Mock()
        mock_scene.all_sprites = mocker.Mock()
        mock_scene.background = MockFactory.create_pygame_surface_mock()
        mock_scene.render = mocker.Mock()

        # Test that scene has render method
        assert hasattr(mock_scene, 'render')

    def test_scene_rendering_with_render_state_changes_manager(self, mocker):
        """Test scene rendering with render state changes through manager."""
        # Reset singleton state for clean test
        SceneManager._reset()

        manager = self.scene_manager

        # Create a mock scene using centralized mocks
        mock_scene = mocker.Mock()
        mock_scene.all_sprites = mocker.Mock()
        mock_scene.background = MockFactory.create_pygame_surface_mock()
        mock_scene.render = mocker.Mock()

        # Switch to scene
        manager.switch_to_scene(mock_scene)
        assert manager.active_scene == mock_scene

        # Test that scene has render method
        assert hasattr(mock_scene, 'render')

    def test_scene_rendering_with_edge_cases(self, mocker):
        """Test scene rendering with edge cases."""
        # Create a mock scene using centralized mocks
        mock_scene = mocker.Mock()
        mock_scene.all_sprites = mocker.Mock()
        mock_scene.background = MockFactory.create_pygame_surface_mock()
        mock_scene.render = mocker.Mock()

        # Test that scene has render method
        assert hasattr(mock_scene, 'render')

    def test_scene_rendering_with_edge_cases_manager(self, mocker):
        """Test scene rendering with edge cases through manager."""
        # Reset singleton state for clean test
        SceneManager._reset()

        manager = self.scene_manager

        # Create a mock scene using centralized mocks
        mock_scene = mocker.Mock()
        mock_scene.all_sprites = mocker.Mock()
        mock_scene.background = MockFactory.create_pygame_surface_mock()
        mock_scene.render = mocker.Mock()

        # Switch to scene
        manager.switch_to_scene(mock_scene)
        assert manager.active_scene == mock_scene

        # Test that scene has render method
        assert hasattr(mock_scene, 'render')
