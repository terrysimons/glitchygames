"""Tests for scene-based film strip system."""

from glitchygames.tools import bitmappy

from tests.mocks import MockFactory

# Test constants to avoid magic values
ANIMATION_COUNT = 3


class TestSceneFilmStrips:
    """Test the new scene-based film strip system."""

    def test_scene_film_strips_creation(self, mock_pygame_patches):
        """Test that scene creates film strips correctly."""
        # Create mock animated sprite
        mock_sprite = MockFactory.create_animated_sprite_mock()

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

    def test_scene_film_strips_multiple_animations(self, mock_pygame_patches):
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
        assert len(scene.film_strips) == ANIMATION_COUNT  # idle, walk, jump
        assert len(scene.film_strip_sprites) == ANIMATION_COUNT

        # Test that each animation has its own film strip
        for anim_name in ["idle", "walk", "jump"]:
            assert anim_name in scene.film_strips
            assert anim_name in scene.film_strip_sprites
