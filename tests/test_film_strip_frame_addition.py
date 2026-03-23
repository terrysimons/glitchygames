"""Tests for film strip frame addition functionality."""

import math

import pygame
import pytest

from glitchygames.bitmappy.film_strip import FilmStripWidget, FilmTabWidget
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from tests.mocks import MockFactory

# Test constants to avoid magic values
TEST_DURATION_0_001 = 0.001
TEST_SIZE_2 = 2

# Canvas dimensions used across all tests
CANVAS_WIDTH = 8
CANVAS_HEIGHT = 8


def _create_blank_frame_mock(width, height, duration=0.5):
    """Create a proper SpriteFrame for use as a _create_blank_frame mock return value.

    Returns:
        object: The result.

    """
    surface = MockFactory.create_pygame_surface_mock(width, height)
    surface.fill((255, 0, 255))
    frame = SpriteFrame(surface, duration=duration)
    frame.pixels = [(255, 0, 255, 255)] * (width * height)
    return frame


def _mock_parent_scene(animated_sprite, mocker):
    """Create a properly configured parent scene mock.

    Sets up canvas.animated_sprite so that film_strip._update_film_tabs()
    can iterate _animations.keys() without hitting 'Mock is not iterable'.

    Returns:
        object: The result.

    """
    parent_scene = mocker.Mock()
    parent_scene.on_frame_inserted = mocker.Mock()
    parent_scene.canvas = mocker.Mock()
    parent_scene.canvas.pixels_across = CANVAS_WIDTH
    parent_scene.canvas.pixels_tall = CANVAS_HEIGHT
    parent_scene.canvas.animated_sprite = animated_sprite
    parent_scene._create_blank_frame = mocker.Mock(
        side_effect=lambda w, h, duration=0.5: _create_blank_frame_mock(w, h, duration)
    )
    return parent_scene


class TestFilmStripFrameAddition:
    """Test film strip frame addition behavior."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up test fixtures."""
        # Ensure pygame is properly initialized for mocks
        if not pygame.get_init():
            pygame.init()

        MockFactory.setup_pygame_mocks_with_mocker(mocker)

        self.surface1 = MockFactory.create_pygame_surface_mock(8, 8)
        self.surface1.fill((255, 0, 0))  # Red

        self.surface2 = MockFactory.create_pygame_surface_mock(8, 8)
        self.surface2.fill((0, 255, 0))  # Green

        self.surface3 = MockFactory.create_pygame_surface_mock(8, 8)
        self.surface3.fill((0, 0, 255))  # Blue

        yield

        pygame.quit()

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

        # Verify frame was inserted at index 0
        assert len(animated_sprite._animations['idle']) == TEST_SIZE_2
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

        # Verify frame was inserted at index 1
        assert len(animated_sprite._animations['idle']) == TEST_SIZE_2
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
            film_strip.preview_animation_times['idle'], 0.0, abs_tol=1e-9
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
