"""Tests for scene-based film strip system."""

from src.apps.bitmappy.tests.film_strip_support import make_real_animated_sprite

from bitmappy import editor as bitmappy
from bitmappy.film_strip import FilmStripWidget
from bitmappy.film_strip_sprite import FilmStripSprite


def build_editor_with_sprite(*, frame_counts):
    """Build a real editor scene on the real display and load a sprite into it.

    Returns:
        tuple: The scene and the loaded sprite.

    """
    animated_sprite = make_real_animated_sprite(frame_counts=frame_counts)
    scene = bitmappy.BitmapEditorScene(
        options={'pixels_across': 32, 'pixels_tall': 32, 'pixel_size': 16},
    )
    scene.film_strip_coordinator.on_sprite_loaded(animated_sprite)
    return scene, animated_sprite


class TestSceneFilmStrips:
    """Test the new scene-based film strip system."""

    def test_scene_film_strips_creation(self):
        """Test that the scene creates a film strip and its sprite for the animation."""
        scene, _animated_sprite = build_editor_with_sprite(frame_counts={'idle': 5})

        assert set(scene.film_strips) == {'idle'}
        assert set(scene.film_strip_sprites) == {'idle'}

        film_strip = scene.film_strips['idle']
        film_strip_sprite = scene.film_strip_sprites['idle']
        assert isinstance(film_strip, FilmStripWidget)
        assert isinstance(film_strip_sprite, FilmStripSprite)
        assert film_strip_sprite.film_strip_widget is film_strip
        assert len(film_strip.animated_sprite.animations['idle']) == 5

    def test_scene_film_strips_multiple_animations(self):
        """Test that each animation gets its own film strip."""
        scene, _animated_sprite = build_editor_with_sprite(
            frame_counts={'idle': 5, 'walk': 5, 'jump': 5},
        )

        assert set(scene.film_strips) == {'idle', 'walk', 'jump'}
        assert set(scene.film_strip_sprites) == {'idle', 'walk', 'jump'}
        for animation_name, film_strip in scene.film_strips.items():
            assert film_strip.current_animation == animation_name
