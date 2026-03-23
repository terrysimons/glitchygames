"""Tests for scene-based film strip system."""

import os

import pytest

from glitchygames.bitmappy import editor as bitmappy
from tests.mocks import MockFactory

# Skip in CI - BitmapEditorScene.__init__ requires full display and font system
pytestmark = pytest.mark.skipif(
    os.environ.get('CI') == 'true',
    reason='BitmapEditorScene requires full display stack, unavailable in CI',
)

# Test constants to avoid magic values
ANIMATION_COUNT = 3


class TestSceneFilmStrips:
    """Test the new scene-based film strip system."""

    def test_scene_film_strips_creation(self, mock_pygame_patches, mocker):
        """Test that scene creates film strips correctly."""
        # Create mock animated sprite
        mock_sprite = MockFactory.create_animated_sprite_mock()

        # Mock _setup_menu_bar to avoid real pygame sprite group operations
        # which are not safe under parallel test execution
        mocker.patch.object(bitmappy.BitmapEditorScene, '_setup_menu_bar')

        # Create scene with mock sprite (using centralized mocks)
        scene = bitmappy.BitmapEditorScene(
            options={'pixels_across': 32, 'pixels_tall': 32, 'pixel_size': 16}
        )

        # Load the sprite
        scene.film_strip_coordinator.on_sprite_loaded(mock_sprite)

        # Test that film strips are created using the new dictionary-based system
        assert hasattr(scene, 'film_strips')
        assert hasattr(scene, 'film_strip_sprites')
        assert len(scene.film_strips) > 0
        assert len(scene.film_strip_sprites) > 0

        # Test that film strips are properly accessible
        # Each animation should have its own film strip
        for anim_name in scene.film_strips:
            assert anim_name in scene.film_strip_sprites
            assert scene.film_strips[anim_name] is not None
            assert scene.film_strip_sprites[anim_name] is not None

    def test_scene_film_strips_multiple_animations(self, mock_pygame_patches, mocker):
        """Test scene with multiple animations."""
        # Create mock sprite with multiple animations
        mock_sprite = MockFactory.create_animated_sprite_mock()
        mock_sprite._animations['walk'] = mock_sprite._animations['idle'].copy()
        mock_sprite._animations['jump'] = mock_sprite._animations['idle'].copy()

        # Mock _setup_menu_bar to avoid real pygame sprite group operations
        # which are not safe under parallel test execution
        mocker.patch.object(bitmappy.BitmapEditorScene, '_setup_menu_bar')

        # Create scene (using centralized mocks)
        scene = bitmappy.BitmapEditorScene(
            options={'pixels_across': 32, 'pixels_tall': 32, 'pixel_size': 16}
        )

        # Load the sprite
        scene.film_strip_coordinator.on_sprite_loaded(mock_sprite)

        # Test that multiple film strips are created
        # Check for at least the animations we added (mock may create others)
        assert len(scene.film_strips) >= ANIMATION_COUNT  # At least idle, walk, jump
        assert len(scene.film_strip_sprites) >= ANIMATION_COUNT

        # Test that each animation we added has its own film strip
        for anim_name in ['idle', 'walk', 'jump']:
            assert anim_name in scene.film_strips
            assert anim_name in scene.film_strip_sprites
