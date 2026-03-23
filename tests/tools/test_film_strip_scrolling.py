"""Tests for film strip scrolling functionality."""

import pygame
import pytest

from glitchygames.bitmappy.editor import BitmapEditorScene

# Test constants to avoid magic values
MAX_VISIBLE_STRIPS = 2
SCROLL_OFFSET_0 = 0
SCROLL_OFFSET_1 = 1
SCROLL_OFFSET_2 = 2
ANIMATION_COUNT = 4
DIRTY_VALUE = 2


class TestFilmStripScrolling:
    """Test film strip scrolling functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up test fixtures using centralized mocks."""
        self._mocker = mocker

        # Use real pygame initialization since BitmapEditorScene requires it
        pygame.init()
        pygame.display.set_mode((800, 600))

        # Create scene
        self.scene = BitmapEditorScene(options={})
        self.scene.max_visible_strips = MAX_VISIBLE_STRIPS
        self.scene.film_strip_scroll_offset = SCROLL_OFFSET_0

        yield

        pygame.quit()

    def test_scroll_film_strips_up(self):
        """Test scrolling film strips up functionality."""
        # Set up with scroll offset at 2
        self.scene.film_strip_scroll_offset = SCROLL_OFFSET_2

        # Scroll up
        self.scene.scroll_film_strips_up()

        # Should decrement the offset
        assert self.scene.film_strip_scroll_offset == SCROLL_OFFSET_1

    def test_scroll_film_strips_down(self):
        """Test scrolling film strips down functionality."""
        # Set up with scroll offset at 0
        self.scene.film_strip_scroll_offset = SCROLL_OFFSET_0

        # Mock the canvas and animated sprite
        self.scene.canvas = self._mocker.Mock()
        self.scene.canvas.animated_sprite = self._mocker.Mock()
        self.scene.canvas.animated_sprite._animations = {
            'anim1': [self._mocker.Mock()],
            'anim2': [self._mocker.Mock()],
            'anim3': [self._mocker.Mock()],
            'anim4': [self._mocker.Mock()],
        }

        # Scroll down
        self.scene.scroll_film_strips_down()

        # Should increment the offset
        assert self.scene.film_strip_scroll_offset == SCROLL_OFFSET_1

    def test_scroll_boundaries_up(self):
        """Test scrolling up respects boundaries."""
        # Set up with scroll offset at 0 (minimum)
        self.scene.film_strip_scroll_offset = SCROLL_OFFSET_0

        # Try to scroll up
        self.scene.scroll_film_strips_up()

        # Should not go below 0
        assert self.scene.film_strip_scroll_offset == SCROLL_OFFSET_0

    def test_scroll_boundaries_down(self):
        """Test scrolling down respects boundaries."""
        # Set up with 4 animations, 2 visible, max scroll = 2
        self.scene.canvas = self._mocker.Mock()
        self.scene.canvas.animated_sprite = self._mocker.Mock()
        self.scene.canvas.animated_sprite._animations = {
            'anim1': [self._mocker.Mock()],
            'anim2': [self._mocker.Mock()],
            'anim3': [self._mocker.Mock()],
            'anim4': [self._mocker.Mock()],
        }

        # Set scroll offset to maximum
        self.scene.film_strip_scroll_offset = SCROLL_OFFSET_2

        # Try to scroll down
        self.scene.scroll_film_strips_down()

        # Should not exceed maximum
        assert self.scene.film_strip_scroll_offset == SCROLL_OFFSET_2

    def test_auto_scroll_to_current_animation(self):
        """Test automatic scrolling to show current animation."""
        # Set up with 4 animations, 2 visible
        self.scene.canvas = self._mocker.Mock()
        self.scene.canvas.animated_sprite = self._mocker.Mock()
        self.scene.canvas.animated_sprite._animations = {
            'anim1': [self._mocker.Mock()],
            'anim2': [self._mocker.Mock()],
            'anim3': [self._mocker.Mock()],
            'anim4': [self._mocker.Mock()],
        }
        self.scene.canvas.current_animation = 'anim4'  # Last animation (index 3)

        # Set up film strips dictionary
        self.scene.film_strips = {
            'anim1': self._mocker.Mock(),
            'anim2': self._mocker.Mock(),
            'anim3': self._mocker.Mock(),
            'anim4': self._mocker.Mock(),
        }
        self.scene.film_strip_sprites = {
            'anim1': self._mocker.Mock(),
            'anim2': self._mocker.Mock(),
            'anim3': self._mocker.Mock(),
            'anim4': self._mocker.Mock(),
        }

        # Mock the update methods
        self.scene.update_film_strip_visibility = self._mocker.Mock()
        self.scene.update_scroll_arrows = self._mocker.Mock()
        self.scene._update_film_strip_selection = self._mocker.Mock()

        # Call auto-scroll
        self.scene._scroll_to_current_animation()

        # Should scroll to show the last animation (offset should be 2)
        assert self.scene.film_strip_scroll_offset == SCROLL_OFFSET_2

    def test_auto_scroll_when_animation_already_visible(self):
        """Test auto-scroll doesn't change offset when animation is already visible."""
        # Set up with 4 animations, 2 visible, showing first 2
        self.scene.canvas = self._mocker.Mock()
        self.scene.canvas.animated_sprite = self._mocker.Mock()
        self.scene.canvas.animated_sprite._animations = {
            'anim1': [self._mocker.Mock()],
            'anim2': [self._mocker.Mock()],
            'anim3': [self._mocker.Mock()],
            'anim4': [self._mocker.Mock()],
        }
        # Second animation (index 1, should be visible)
        self.scene.canvas.current_animation = 'anim2'

        # Set up film strips dictionary
        self.scene.film_strips = {
            'anim1': self._mocker.Mock(),
            'anim2': self._mocker.Mock(),
            'anim3': self._mocker.Mock(),
            'anim4': self._mocker.Mock(),
        }
        self.scene.film_strip_sprites = {
            'anim1': self._mocker.Mock(),
            'anim2': self._mocker.Mock(),
            'anim3': self._mocker.Mock(),
            'anim4': self._mocker.Mock(),
        }

        # Set scroll offset to show first 2 animations
        self.scene.film_strip_scroll_offset = SCROLL_OFFSET_0

        # Mock the update methods
        self.scene.update_film_strip_visibility = self._mocker.Mock()
        self.scene.update_scroll_arrows = self._mocker.Mock()
        self.scene._update_film_strip_selection = self._mocker.Mock()

        # Call auto-scroll
        self.scene._scroll_to_current_animation()

        # Should not change offset since "anim2" is already visible
        assert self.scene.film_strip_scroll_offset == SCROLL_OFFSET_0

    def test_switch_to_film_strip(self):
        """Test switching to a specific film strip."""
        # Set up film strips
        self.scene.film_strips = {'anim1': self._mocker.Mock(), 'anim2': self._mocker.Mock()}
        self.scene.film_strip_sprites = {'anim1': self._mocker.Mock(), 'anim2': self._mocker.Mock()}

        # Set up canvas
        self.scene.canvas = self._mocker.Mock()

        # Switch to "anim2"
        self.scene._switch_to_film_strip('anim2', 1)

        # Check global selection state
        assert self.scene.selected_animation == 'anim2'
        assert self.scene.selected_frame == 1

        # Check canvas was updated
        self.scene.canvas.show_frame.assert_called_once_with('anim2', 1)

    def test_dirty_marking_on_switch(self):
        """Test that switching film strips marks sprites as dirty."""
        # Set up film strips
        self.scene.film_strips = {'anim1': self._mocker.Mock(), 'anim2': self._mocker.Mock()}
        self.scene.film_strip_sprites = {'anim1': self._mocker.Mock(), 'anim2': self._mocker.Mock()}

        # Set up canvas
        self.scene.canvas = self._mocker.Mock()

        # Switch to "anim2"
        self.scene._switch_to_film_strip('anim2', SCROLL_OFFSET_0)

        # Check that the film strip sprite is marked as dirty
        self.scene.film_strip_sprites['anim2'].dirty = DIRTY_VALUE
        assert self.scene.film_strip_sprites['anim2'].dirty == DIRTY_VALUE
