"""Tests for scene-based film strip system."""

from unittest.mock import Mock, patch

import pytest
from glitchygames.tools import bitmappy
from tests.mocks.test_mock_factory import MockFactory


class TestSceneFilmStrips:
    """Test the new scene-based film strip system."""

    def setUp(self):
        """Set up pygame mocks for each test."""
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Tear down pygame mocks."""
        for patcher in self.patchers:
            patcher.stop()

    def test_scene_film_strips_creation(self):
        """Test that scene creates film strips correctly."""
        # Create mock animated sprite
        mock_sprite = MockFactory.create_animated_sprite_mock()
        
        # Debug: Check if mocks are working
        import pygame
        print("DEBUG: pygame.display.get_surface():", pygame.display.get_surface())
        print("DEBUG: get_surface() type:", type(pygame.display.get_surface()))
        
        # Create scene with mock sprite (using centralized mocks)
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
        
        # Create scene (using centralized mocks)
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
