"""Tests for scene-based film strip system."""

import pytest
from unittest.mock import Mock, patch

from glitchygames.tools import bitmappy
from tests.mocks.test_mock_factory import MockFactory


class TestSceneFilmStrips:
    """Test the new scene-based film strip system."""

    @classmethod
    def setUpClass(cls):
        """Set up pygame mocks for all tests."""
        cls.patchers = MockFactory.setup_pygame_mocks()
        for patcher in cls.patchers:
            patcher.start()

    @classmethod
    def tearDownClass(cls):
        """Tear down pygame mocks."""
        MockFactory.teardown_pygame_mocks(cls.patchers)

    def test_scene_film_strips_creation(self):
        """Test that scene creates film strips correctly."""
        # Create mock animated sprite
        mock_sprite = MockFactory.create_animated_sprite_mock()
        
        # Create scene with mock sprite
        with patch('pygame.display.get_surface') as mock_display:
            mock_display.return_value = Mock()
            mock_display.return_value.get_width.return_value = 800
            mock_display.return_value.get_height.return_value = 600
            
            scene = bitmappy.BitmapEditorScene(
                options={"pixels_across": 32, "pixels_tall": 32, "pixel_size": 16}
            )
            
            # Load the sprite
            scene._on_sprite_loaded(mock_sprite)
            
            # Test that film strips are created
            assert hasattr(scene, "film_strips")
            assert hasattr(scene, "film_strip_sprites")
            assert len(scene.film_strips) > 0
            assert len(scene.film_strip_sprites) > 0
            
            # Test that canvas has backward compatibility attributes
            assert hasattr(scene.canvas, "film_strip")
            assert hasattr(scene.canvas, "film_strip_sprite")
            assert scene.canvas.film_strip is not None
            assert scene.canvas.film_strip_sprite is not None

    def test_scene_film_strips_multiple_animations(self):
        """Test scene with multiple animations."""
        # Create mock sprite with multiple animations
        mock_sprite = MockFactory.create_animated_sprite_mock()
        mock_sprite._animations["walk"] = mock_sprite._animations["idle"].copy()
        mock_sprite._animations["jump"] = mock_sprite._animations["idle"].copy()
        
        # Create scene
        with patch('pygame.display.get_surface') as mock_display:
            mock_display.return_value = Mock()
            mock_display.return_value.get_width.return_value = 800
            mock_display.return_value.get_height.return_value = 600
            
            scene = bitmappy.BitmapEditorScene(
                options={"pixels_across": 32, "pixels_tall": 32, "pixel_size": 16}
            )
            
            # Load the sprite
            scene._on_sprite_loaded(mock_sprite)
            
            # Test that multiple film strips are created
            assert len(scene.film_strips) == 3  # idle, walk, jump
            assert len(scene.film_strip_sprites) == 3
            
            # Test that each animation has its own film strip
            for anim_name in ["idle", "walk", "jump"]:
                assert anim_name in scene.film_strips
                assert anim_name in scene.film_strip_sprites
