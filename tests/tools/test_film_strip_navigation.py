"""Tests for film strip navigation and scrolling functionality."""

import pygame
import pytest

from tests.mocks.test_mock_factory import MockFactory, MockSpriteConfig
from tests.tools.test_film_strip_base import FilmStripTestBase

# Additional test constants
FRAME_INDEX_2 = 2
MAX_VISIBLE_STRIPS = 2
SCROLL_OFFSET_2 = 2
SCROLL_OFFSET_1 = 1
SCROLL_OFFSET_0 = 0


class TestFilmStripNavigation(FilmStripTestBase):
    """Test film strip navigation and scrolling functionality."""

    @pytest.fixture(autouse=True)
    def setup_navigation(self, mocker):
        """Set up test fixtures for navigation testing.

        Note: The base class setup_mocks fixture runs first (autouse),
        so pygame mocks and cached objects are already available.
        """
        # Use the optimized setup from base class
        self.scene, self.mock_sprite = self.setup_scene_with_sprite()

        # Configure scene for navigation testing
        self.scene.max_visible_strips = MAX_VISIBLE_STRIPS
        self.scene.film_strip_scroll_offset = SCROLL_OFFSET_0

        # Set up multiple animations for navigation testing using centralized mocks

        # Create additional animations using the centralized mock factory
        walk_sprite = MockFactory.create_animated_sprite_mock(
            config=MockSpriteConfig(animation_name='walk'),
        )
        jump_sprite = MockFactory.create_animated_sprite_mock(
            config=MockSpriteConfig(animation_name='jump'),
        )
        attack_sprite = MockFactory.create_animated_sprite_mock(
            config=MockSpriteConfig(animation_name='attack'),
        )

        # Replace mock frame images with real pygame Surfaces for rendering
        self._replace_mock_images_with_real_surfaces(walk_sprite)
        self._replace_mock_images_with_real_surfaces(jump_sprite)
        self._replace_mock_images_with_real_surfaces(attack_sprite)

        # Combine animations from different sprites
        self.mock_sprite._animations.update({
            'walk': walk_sprite._animations['walk'],
            'jump': jump_sprite._animations['jump'],
            'attack': attack_sprite._animations['attack'],
        })

        # Reload the sprite to create film strips for all animations
        self.scene.film_strip_coordinator.on_sprite_loaded(self.mock_sprite)

        # Ensure canvas has proper navigation state
        self.scene.canvas.current_animation = 'idle'
        self.scene.canvas.current_frame = SCROLL_OFFSET_0

    def test_up_arrow_navigation(self):
        """Test UP arrow navigates to previous animation."""
        # Get the list of animations in the order they appear
        animation_names = list(self.mock_sprite._animations.keys())

        # Start at the last animation
        self.scene.canvas.current_animation = animation_names[-1]
        self.scene.canvas.current_frame = SCROLL_OFFSET_0

        # Create UP arrow event
        up_event = self._mocker.Mock()
        up_event.key = pygame.K_UP
        up_event.type = pygame.KEYDOWN
        up_event.mod = 0

        # Handle the event
        self.scene.on_key_down_event(up_event)

        # Should navigate to the previous animation
        expected_animation = animation_names[-2] if len(animation_names) > 1 else animation_names[0]
        assert self.scene.canvas.current_animation == expected_animation
        assert self.scene.canvas.current_frame == SCROLL_OFFSET_0

    def test_down_arrow_navigation(self):
        """Test DOWN arrow navigates to next animation."""
        # Get the list of animations in the order they appear
        animation_names = list(self.mock_sprite._animations.keys())

        # Start at the first animation
        self.scene.canvas.current_animation = animation_names[0]
        self.scene.canvas.current_frame = SCROLL_OFFSET_0

        # Create DOWN arrow event
        down_event = self._mocker.Mock()
        down_event.key = pygame.K_DOWN
        down_event.type = pygame.KEYDOWN
        down_event.mod = 0

        # Handle the event
        self.scene.on_key_down_event(down_event)

        # Should navigate to the next animation
        expected_animation = animation_names[1] if len(animation_names) > 1 else animation_names[0]
        assert self.scene.canvas.current_animation == expected_animation
        assert self.scene.canvas.current_frame == SCROLL_OFFSET_0

    def test_left_arrow_frame_navigation(self):
        """Test LEFT arrow navigates to previous frame."""
        # Start at frame 2 of "idle" (3 frames total)
        self.scene.canvas.current_animation = 'idle'
        self.scene.canvas.current_frame = FRAME_INDEX_2

        # Create LEFT arrow event
        left_event = self._mocker.Mock()
        left_event.key = pygame.K_LEFT
        left_event.type = pygame.KEYDOWN
        left_event.mod = 0

        # Handle the event
        self.scene.on_key_down_event(left_event)

        # Should navigate to frame 1
        assert self.scene.canvas.current_animation == 'idle'
        assert self.scene.canvas.current_frame == 1

    def test_right_arrow_frame_navigation(self):
        """Test RIGHT arrow navigates to next frame."""
        # Start at frame 0 of "idle"
        self.scene.canvas.current_animation = 'idle'
        self.scene.canvas.current_frame = SCROLL_OFFSET_0

        # Create RIGHT arrow event
        right_event = self._mocker.Mock()
        right_event.key = pygame.K_RIGHT
        right_event.type = pygame.KEYDOWN
        right_event.mod = 0

        # Handle the event
        self.scene.on_key_down_event(right_event)

        # Should navigate to frame 1
        assert self.scene.canvas.current_animation == 'idle'
        assert self.scene.canvas.current_frame == 1

    def test_animation_wraparound(self):
        """Test animation navigation wraps around at boundaries."""
        # Get the list of animations in the order they appear
        animation_names = list(self.mock_sprite._animations.keys())

        # Start at the last animation
        self.scene.canvas.current_animation = animation_names[-1]
        self.scene.canvas.current_frame = SCROLL_OFFSET_0

        # Navigate down (should wrap to first)
        down_event = self._mocker.Mock()
        down_event.key = pygame.K_DOWN
        down_event.type = pygame.KEYDOWN
        down_event.mod = 0
        self.scene.on_key_down_event(down_event)

        # Should wrap to first animation
        assert self.scene.canvas.current_animation == animation_names[0]

        # Navigate up (should wrap to last)
        up_event = self._mocker.Mock()
        up_event.key = pygame.K_UP
        up_event.type = pygame.KEYDOWN
        up_event.mod = 0
        self.scene.on_key_down_event(up_event)

        # Should wrap to last animation
        assert self.scene.canvas.current_animation == animation_names[-1]

    def test_frame_wraparound(self):
        """Test frame navigation wraps around at boundaries."""
        # Get the number of frames for the idle animation
        idle_frames = len(self.mock_sprite._animations['idle'])
        last_frame_index = idle_frames - 1

        # Start at the last frame of "idle"
        self.scene.canvas.current_animation = 'idle'
        self.scene.canvas.current_frame = last_frame_index

        # Navigate right (should wrap to frame 0)
        right_event = self._mocker.Mock()
        right_event.key = pygame.K_RIGHT
        right_event.type = pygame.KEYDOWN
        right_event.mod = 0
        self.scene.on_key_down_event(right_event)

        # Should wrap to frame 0
        assert self.scene.canvas.current_frame == SCROLL_OFFSET_0

        # Navigate left (should wrap to last frame)
        left_event = self._mocker.Mock()
        left_event.key = pygame.K_LEFT
        left_event.type = pygame.KEYDOWN
        left_event.mod = 0
        self.scene.on_key_down_event(left_event)

        # Should wrap to last frame
        assert self.scene.canvas.current_frame == last_frame_index

    def test_film_strip_scrolling_up(self):
        """Test film strip scrolling up functionality."""
        # Set up with 4 animations, only 2 visible
        self.scene.max_visible_strips = MAX_VISIBLE_STRIPS
        self.scene.film_strip_scroll_offset = SCROLL_OFFSET_2  # Showing animations 2 and 3

        # Scroll up
        self.scene.scroll_film_strips_up()

        # Should show animations 1 and 2
        assert self.scene.film_strip_scroll_offset == SCROLL_OFFSET_1

    def test_film_strip_scrolling_down(self):
        """Test film strip scrolling down functionality."""
        # Set up with 4 animations, only 2 visible
        self.scene.max_visible_strips = MAX_VISIBLE_STRIPS
        self.scene.film_strip_scroll_offset = SCROLL_OFFSET_0  # Showing animations 0 and 1

        # Scroll down
        self.scene.scroll_film_strips_down()

        # Should show animations 1 and 2
        assert self.scene.film_strip_scroll_offset == SCROLL_OFFSET_1

    def test_scroll_boundaries(self):
        """Test scrolling respects boundaries."""
        # Set up with multiple animations, only 2 visible
        self.scene.max_visible_strips = MAX_VISIBLE_STRIPS

        # Try to scroll up from offset 0 (should not go negative)
        self.scene.film_strip_scroll_offset = SCROLL_OFFSET_0
        self.scene.scroll_film_strips_up()
        assert self.scene.film_strip_scroll_offset == SCROLL_OFFSET_0

        # Calculate actual max scroll based on total animations
        total_animations = len(self.scene.canvas.animated_sprite._animations)
        max_scroll = max(0, total_animations - self.scene.max_visible_strips)

        # Try to scroll down from max offset (should not exceed max)
        self.scene.film_strip_scroll_offset = max_scroll
        self.scene.scroll_film_strips_down()
        assert self.scene.film_strip_scroll_offset == max_scroll

    def test_auto_scroll_to_current_animation(self):
        """Test automatic scrolling to show current animation."""
        # Set up with multiple animations, only 2 visible
        self.scene.max_visible_strips = MAX_VISIBLE_STRIPS
        self.scene.film_strip_scroll_offset = SCROLL_OFFSET_0  # Showing first animations

        # Set current animation to "attack" (last added animation)
        self.scene.canvas.current_animation = 'attack'

        # Find the index of "attack" in the animation list
        animation_names = list(self.scene.canvas.animated_sprite._animations.keys())
        attack_index = animation_names.index('attack')

        # Call auto-scroll
        self.scene.film_strip_coordinator.scroll_to_current_animation()

        # Should scroll so "attack" is visible
        # The offset should be at least attack_index - max_visible + 1
        expected_offset = max(0, attack_index - self.scene.max_visible_strips + 1)
        assert self.scene.film_strip_scroll_offset == expected_offset

    def test_auto_scroll_when_animation_already_visible(self):
        """Test auto-scroll doesn't change offset when animation is already visible."""
        # Set up with 4 animations, only 2 visible
        self.scene.max_visible_strips = MAX_VISIBLE_STRIPS
        self.scene.film_strip_scroll_offset = SCROLL_OFFSET_1  # Showing animations 1 and 2

        # Set current animation to "walk" (index 1, should be visible)
        self.scene.canvas.current_animation = 'walk'

        # Call auto-scroll
        self.scene.film_strip_coordinator.scroll_to_current_animation()

        # Should not change offset since "walk" is already visible
        assert self.scene.film_strip_scroll_offset == SCROLL_OFFSET_1

    @pytest.mark.skip(reason='Selection state management not implemented')
    def test_film_strip_selection_state(self):
        """Test film strip selection state management."""
        # Set current animation to "walk"
        self.scene.canvas.current_animation = 'walk'
        self.scene.canvas.current_frame = 1

        # Update selection state
        self.scene.update_film_strip_selection_state()

        # Check that the correct strip is marked as selected
        if 'walk' in self.scene.film_strips:
            walk_strip = self.scene.film_strips['walk']
            assert walk_strip.is_selected
            assert walk_strip.current_animation == 'walk'
            assert walk_strip.current_frame == 1

    def test_switch_to_film_strip(self):
        """Test switching to a specific film strip."""
        # Switch to "jump" animation, frame 0
        self.scene.film_strip_coordinator.switch_to_film_strip('jump', SCROLL_OFFSET_0)

        # Check global selection state
        assert self.scene.selected_animation == 'jump'
        assert self.scene.selected_frame == SCROLL_OFFSET_0

        # Check canvas state
        assert self.scene.canvas.current_animation == 'jump'
        assert self.scene.canvas.current_frame == SCROLL_OFFSET_0

    @pytest.mark.skip(reason='Selection state management not implemented')
    def test_dirty_marking_on_selection_change(self):
        """Test that selection changes properly mark sprites as dirty."""
        # Switch to a different strip
        self.scene.film_strip_coordinator.switch_to_film_strip('attack', SCROLL_OFFSET_0)

        # Check that the film strip sprite is marked as dirty
        if 'attack' in self.scene.film_strip_sprites:
            attack_sprite = self.scene.film_strip_sprites['attack']
            assert attack_sprite.dirty == SCROLL_OFFSET_2

    def test_keyboard_navigation_with_auto_scroll(self):
        """Test that keyboard navigation triggers auto-scroll when needed."""
        # Set up with multiple animations, only 2 visible, showing first 2
        self.scene.max_visible_strips = MAX_VISIBLE_STRIPS
        self.scene.film_strip_scroll_offset = SCROLL_OFFSET_0

        # Find "idle" and "attack" positions in the animation list
        animation_names = list(self.scene.canvas.animated_sprite._animations.keys())
        idle_index = animation_names.index('idle')
        attack_index = animation_names.index('attack')
        steps_needed = attack_index - idle_index

        # Start at "idle"
        self.scene.canvas.current_animation = 'idle'

        # Navigate down to "attack"
        down_event = self._mocker.Mock()
        down_event.key = pygame.K_DOWN
        down_event.type = pygame.KEYDOWN
        down_event.mod = 0

        for _ in range(steps_needed):
            self.scene.on_key_down_event(down_event)

        # Should have navigated to "attack" and auto-scrolled to show it
        assert self.scene.canvas.current_animation == 'attack'
        # Should have scrolled so "attack" is visible
        expected_offset = max(0, attack_index - self.scene.max_visible_strips + 1)
        assert self.scene.film_strip_scroll_offset == expected_offset
