"""Tests for film strip frame addition functionality."""

import math

import pygame

from bitmappy.film_strip import FilmStripWidget, FilmTabWidget
from bitmappy.film_strip_coordinator import FilmStripCoordinator
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

# Test constants to avoid magic values
TEST_DURATION_0_001 = 0.001
TEST_SIZE_2 = 2

# Canvas dimensions used across all tests
CANVAS_WIDTH = 8
CANVAS_HEIGHT = 8


def _solid_rgb(image):
    """Return the one RGB color an image is filled with (fails if it has more than one).

    Returns:
        tuple[int, int, int]: The image's only color.

    """
    pixels = pygame.surfarray.array3d(image).reshape(-1, 3)
    unique_colors = {tuple(int(channel) for channel in pixel) for pixel in pixels}
    assert len(unique_colors) == 1, f'expected one color, got {sorted(unique_colors)}'
    (only_color,) = unique_colors
    return only_color


def _mock_parent_scene(animated_sprite, mocker):
    """Create a stand-in editor scene for the film strip, with the real frame coordinator.

    The editor scene itself is a mock (the film strip only reads its canvas size and calls
    on_frame_inserted), but its film_strip_coordinator is the real FilmStripCoordinator, so
    inserted frames are the editor's real blank frames. canvas.animated_sprite is the real
    sprite so film_strip._create_film_tabs() can iterate its animations.

    Returns:
        object: The result.

    """
    parent_scene = mocker.Mock()
    parent_scene.on_frame_inserted = mocker.Mock()
    parent_scene.canvas = mocker.Mock()
    parent_scene.canvas.pixels_across = CANVAS_WIDTH
    parent_scene.canvas.pixels_tall = CANVAS_HEIGHT
    parent_scene.canvas.animated_sprite = animated_sprite
    # _insert_frame_at_tab routes through the coordinator
    parent_scene.film_strip_coordinator = FilmStripCoordinator(parent_scene)
    return parent_scene


class TestFilmStripFrameAddition:
    """Test film strip frame addition behavior."""

    def setup_method(self):
        """Set up test fixtures: three solid 8x8 frames (red, green, blue)."""
        self.surface1 = pygame.Surface((8, 8))
        self.surface1.fill((255, 0, 0))  # Red

        self.surface2 = pygame.Surface((8, 8))
        self.surface2.fill((0, 255, 0))  # Green

        self.surface3 = pygame.Surface((8, 8))
        self.surface3.fill((0, 0, 255))  # Blue

    def test_film_strip_reinitializes_after_frame_addition(self, mocker):
        """Test that film strip reinitializes preview animations after frame addition."""
        # Create animated sprite with single frame
        frame1 = SpriteFrame(self.surface1, duration=0.5)
        animated_sprite = AnimatedSprite()
        animated_sprite._animations = {'idle': [frame1]}
        animated_sprite.frame_manager.current_animation = 'idle'
        animated_sprite._is_playing = False
        animated_sprite._is_looping = False

        # Create film strip widget
        film_strip = FilmStripWidget(x=0, y=0, width=100, height=50)
        film_strip.set_animated_sprite(animated_sprite)
        film_strip.current_animation = 'idle'

        # Mock parent scene with canvas.animated_sprite pointing to real sprite
        film_strip.parent_scene = _mock_parent_scene(animated_sprite, mocker)

        # Verify initial state - single frame, animation started by film strip
        assert len(animated_sprite._animations['idle']) == 1
        assert animated_sprite._is_playing  # Film strip starts animation
        assert 'idle' in film_strip.preview_animation_times
        assert film_strip.preview_animation_times['idle'] == TEST_DURATION_0_001  # Single frame

        # Create a tab for frame insertion
        tab = FilmTabWidget(x=0, y=0, width=20, height=20)
        tab.set_insertion_type('after', 0)

        # Insert frame at tab
        film_strip._insert_frame_at_tab(tab)

        # Verify frame was added and animation started
        assert len(animated_sprite._animations['idle']) == TEST_SIZE_2
        assert animated_sprite._is_playing
        assert animated_sprite._is_looping

        # Verify film strip reinitialized its preview animations
        # The preview animation time should be reset to 0.0 for multi-frame
        assert math.isclose(film_strip.preview_animation_times['idle'], 0.0, abs_tol=1e-9)

        # Verify parent scene was notified
        film_strip.parent_scene.on_frame_inserted.assert_called_once_with('idle', 1)

    def test_film_strip_handles_before_insertion(self, mocker):
        """Test film strip handles frame insertion before existing frame."""
        # Create animated sprite with single frame
        frame1 = SpriteFrame(self.surface1, duration=0.5)
        animated_sprite = AnimatedSprite()
        animated_sprite._animations = {'idle': [frame1]}
        animated_sprite.frame_manager.current_animation = 'idle'

        # Create film strip widget
        film_strip = FilmStripWidget(x=0, y=0, width=100, height=50)
        film_strip.set_animated_sprite(animated_sprite)
        film_strip.current_animation = 'idle'
        film_strip.parent_scene = _mock_parent_scene(animated_sprite, mocker)

        # Create tab for "before" insertion
        tab = FilmTabWidget(x=0, y=0, width=20, height=20)
        tab.set_insertion_type('before', 0)

        # Insert frame before first frame
        film_strip._insert_frame_at_tab(tab)

        # Verify frame was inserted at index 0: a blank magenta frame, then the red one
        assert len(animated_sprite._animations['idle']) == TEST_SIZE_2
        inserted_frame, original_frame = animated_sprite._animations['idle']
        assert original_frame is frame1
        assert inserted_frame.image.get_size() == (CANVAS_WIDTH, CANVAS_HEIGHT)
        assert _solid_rgb(inserted_frame.image) == (255, 0, 255)
        assert animated_sprite._is_playing
        assert animated_sprite._is_looping

        # Verify parent scene was notified with correct index
        film_strip.parent_scene.on_frame_inserted.assert_called_once_with('idle', 0)

    def test_film_strip_handles_after_insertion(self, mocker):
        """Test film strip handles frame insertion after existing frame."""
        # Create animated sprite with single frame
        frame1 = SpriteFrame(self.surface1, duration=0.5)
        animated_sprite = AnimatedSprite()
        animated_sprite._animations = {'idle': [frame1]}
        animated_sprite.frame_manager.current_animation = 'idle'

        # Create film strip widget
        film_strip = FilmStripWidget(x=0, y=0, width=100, height=50)
        film_strip.set_animated_sprite(animated_sprite)
        film_strip.current_animation = 'idle'
        film_strip.parent_scene = _mock_parent_scene(animated_sprite, mocker)

        # Create tab for "after" insertion
        tab = FilmTabWidget(x=0, y=0, width=20, height=20)
        tab.set_insertion_type('after', 0)

        # Insert frame after first frame
        film_strip._insert_frame_at_tab(tab)

        # Verify frame was inserted at index 1: the red frame, then a blank magenta one
        assert len(animated_sprite._animations['idle']) == TEST_SIZE_2
        original_frame, inserted_frame = animated_sprite._animations['idle']
        assert original_frame is frame1
        assert inserted_frame.image.get_size() == (CANVAS_WIDTH, CANVAS_HEIGHT)
        assert _solid_rgb(inserted_frame.image) == (255, 0, 255)
        assert animated_sprite._is_playing
        assert animated_sprite._is_looping

        # Verify parent scene was notified with correct index
        film_strip.parent_scene.on_frame_inserted.assert_called_once_with('idle', 1)

    def test_film_strip_no_animation_without_sprite(self, mocker):
        """Test film strip handles missing animated sprite gracefully."""
        # Create film strip widget without animated sprite
        film_strip = FilmStripWidget(x=0, y=0, width=100, height=50)
        film_strip.parent_scene = mocker.Mock()

        # Create tab
        tab = FilmTabWidget(x=0, y=0, width=20, height=20)
        tab.set_insertion_type('after', 0)

        # Should not crash
        film_strip._insert_frame_at_tab(tab)

        # Should not call parent scene
        film_strip.parent_scene.on_frame_inserted.assert_not_called()

    def test_film_strip_no_animation_without_scene(self):
        """Test film strip handles missing parent scene gracefully."""
        # Create animated sprite
        frame1 = SpriteFrame(self.surface1, duration=0.5)
        animated_sprite = AnimatedSprite()
        animated_sprite._animations = {'idle': [frame1]}

        # Create film strip widget without parent scene
        film_strip = FilmStripWidget(x=0, y=0, width=100, height=50)
        film_strip.set_animated_sprite(animated_sprite)
        film_strip.current_animation = 'idle'
        film_strip.parent_scene = None

        # Create tab
        tab = FilmTabWidget(x=0, y=0, width=20, height=20)
        tab.set_insertion_type('after', 0)

        # Should not crash
        film_strip._insert_frame_at_tab(tab)

        # Frame should NOT be added when there's no parent scene
        # (the method returns early without doing anything)
        assert len(animated_sprite._animations['idle']) == 1
        assert animated_sprite._is_playing  # Still playing from film strip setup

    def test_film_strip_animation_timing_after_reinitialization(self, mocker):
        """Test that film strip animation timing works after reinitialization."""
        # Create animated sprite with single frame
        frame1 = SpriteFrame(self.surface1, duration=0.1)
        animated_sprite = AnimatedSprite()
        animated_sprite._animations = {'idle': [frame1]}
        animated_sprite.frame_manager.current_animation = 'idle'

        # Create film strip widget
        film_strip = FilmStripWidget(x=0, y=0, width=100, height=50)
        film_strip.set_animated_sprite(animated_sprite)
        film_strip.current_animation = 'idle'
        film_strip.parent_scene = _mock_parent_scene(animated_sprite, mocker)

        # Add second frame
        tab = FilmTabWidget(x=0, y=0, width=20, height=20)
        tab.set_insertion_type('after', 0)
        film_strip._insert_frame_at_tab(tab)

        # Verify preview animation timing was reinitialized
        assert math.isclose(
            film_strip.preview_animation_times['idle'],
            0.0,
            abs_tol=1e-9,
        )  # Multi-frame timing
        assert math.isclose(film_strip.preview_animation_speeds['idle'], 1.0)
        assert len(film_strip.preview_frame_durations['idle']) == TEST_SIZE_2

        # Test that animation updates work
        film_strip.update_animations(0.05)  # 50ms
        assert film_strip.current_frame == animated_sprite.current_frame

    def test_film_strip_multiple_animations_frame_addition(self, mocker):
        """Test film strip with multiple animations."""
        # Create animated sprite with multiple animations
        frame1 = SpriteFrame(self.surface1, duration=0.5)
        frame2 = SpriteFrame(self.surface2, duration=0.5)
        animated_sprite = AnimatedSprite()
        animated_sprite._animations = {
            'idle': [frame1],  # Single frame
            'walk': [frame1, frame2],  # Multi frame
        }
        animated_sprite.frame_manager.current_animation = 'idle'

        # Create film strip widget
        film_strip = FilmStripWidget(x=0, y=0, width=100, height=50)
        film_strip.set_animated_sprite(animated_sprite)
        film_strip.current_animation = 'idle'
        film_strip.parent_scene = _mock_parent_scene(animated_sprite, mocker)

        # Add frame to idle animation
        tab = FilmTabWidget(x=0, y=0, width=20, height=20)
        tab.set_insertion_type('after', 0)
        film_strip._insert_frame_at_tab(tab)

        # Verify idle animation started
        assert len(animated_sprite._animations['idle']) == TEST_SIZE_2
        assert animated_sprite._is_playing
        assert animated_sprite._is_looping

        # Verify walk animation unchanged
        assert len(animated_sprite._animations['walk']) == TEST_SIZE_2

        # Verify preview animations were reinitialized for all animations
        assert 'idle' in film_strip.preview_animation_times
        assert 'walk' in film_strip.preview_animation_times
