"""Tests for film strip frame addition functionality."""

from unittest.mock import Mock

import pygame
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from glitchygames.tools.film_strip import FilmStripWidget, FilmTabWidget

# Test constants to avoid magic values
TEST_DURATION_0_001 = 0.001
TEST_SIZE_2 = 2


class TestFilmStripFrameAddition:
    """Test film strip frame addition behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        pygame.init()
        self.surface1 = pygame.Surface((8, 8))
        self.surface1.fill((255, 0, 0))  # Red

        self.surface2 = pygame.Surface((8, 8))
        self.surface2.fill((0, 255, 0))  # Green

        self.surface3 = pygame.Surface((8, 8))
        self.surface3.fill((0, 0, 255))  # Blue

    def teardown_method(self):
        """Clean up after tests."""
        pygame.quit()

    def test_film_strip_reinitializes_after_frame_addition(self):
        """Test that film strip reinitializes preview animations after frame addition."""
        # Create animated sprite with single frame
        frame1 = SpriteFrame(self.surface1, duration=0.5)
        animated_sprite = AnimatedSprite()
        animated_sprite._animations = {"idle": [frame1]}
        animated_sprite.frame_manager.current_animation = "idle"
        animated_sprite._is_playing = False
        animated_sprite._is_looping = False

        # Create film strip widget
        film_strip = FilmStripWidget(x=0, y=0, width=100, height=50)
        film_strip.set_animated_sprite(animated_sprite)
        film_strip.current_animation = "idle"

        # Mock parent scene
        film_strip.parent_scene = Mock()
        film_strip.parent_scene._on_frame_inserted = Mock()

        # Verify initial state - single frame, animation started by film strip
        assert len(animated_sprite._animations["idle"]) == 1
        assert animated_sprite._is_playing  # Film strip starts animation
        assert "idle" in film_strip.preview_animation_times
        assert film_strip.preview_animation_times["idle"] == TEST_DURATION_0_001  # Single frame

        # Create a tab for frame insertion
        tab = FilmTabWidget(x=0, y=0, width=20, height=20)
        tab.set_insertion_type("after", 0)

        # Insert frame at tab
        film_strip._insert_frame_at_tab(tab)

        # Verify frame was added and animation started
        assert len(animated_sprite._animations["idle"]) == TEST_SIZE_2
        assert animated_sprite._is_playing
        assert animated_sprite._is_looping

        # Verify film strip reinitialized its preview animations
        # The preview animation time should be reset to 0.0 for multi-frame
        assert film_strip.preview_animation_times["idle"] == 0.0

        # Verify parent scene was notified
        film_strip.parent_scene._on_frame_inserted.assert_called_once_with("idle", 1)

    def test_film_strip_handles_before_insertion(self):
        """Test film strip handles frame insertion before existing frame."""
        # Create animated sprite with single frame
        frame1 = SpriteFrame(self.surface1, duration=0.5)
        animated_sprite = AnimatedSprite()
        animated_sprite._animations = {"idle": [frame1]}
        animated_sprite.frame_manager.current_animation = "idle"

        # Create film strip widget
        film_strip = FilmStripWidget(x=0, y=0, width=100, height=50)
        film_strip.set_animated_sprite(animated_sprite)
        film_strip.current_animation = "idle"
        film_strip.parent_scene = Mock()
        film_strip.parent_scene._on_frame_inserted = Mock()

        # Create tab for "before" insertion
        tab = FilmTabWidget(x=0, y=0, width=20, height=20)
        tab.set_insertion_type("before", 0)

        # Insert frame before first frame
        film_strip._insert_frame_at_tab(tab)

        # Verify frame was inserted at index 0
        assert len(animated_sprite._animations["idle"]) == TEST_SIZE_2
        assert animated_sprite._is_playing
        assert animated_sprite._is_looping

        # Verify parent scene was notified with correct index
        film_strip.parent_scene._on_frame_inserted.assert_called_once_with("idle", 0)

    def test_film_strip_handles_after_insertion(self):
        """Test film strip handles frame insertion after existing frame."""
        # Create animated sprite with single frame
        frame1 = SpriteFrame(self.surface1, duration=0.5)
        animated_sprite = AnimatedSprite()
        animated_sprite._animations = {"idle": [frame1]}
        animated_sprite.frame_manager.current_animation = "idle"

        # Create film strip widget
        film_strip = FilmStripWidget(x=0, y=0, width=100, height=50)
        film_strip.set_animated_sprite(animated_sprite)
        film_strip.current_animation = "idle"
        film_strip.parent_scene = Mock()
        film_strip.parent_scene._on_frame_inserted = Mock()

        # Create tab for "after" insertion
        tab = FilmTabWidget(x=0, y=0, width=20, height=20)
        tab.set_insertion_type("after", 0)

        # Insert frame after first frame
        film_strip._insert_frame_at_tab(tab)

        # Verify frame was inserted at index 1
        assert len(animated_sprite._animations["idle"]) == TEST_SIZE_2
        assert animated_sprite._is_playing
        assert animated_sprite._is_looping

        # Verify parent scene was notified with correct index
        film_strip.parent_scene._on_frame_inserted.assert_called_once_with("idle", 1)

    def test_film_strip_no_animation_without_sprite(self):
        """Test film strip handles missing animated sprite gracefully."""
        # Create film strip widget without animated sprite
        film_strip = FilmStripWidget(x=0, y=0, width=100, height=50)
        film_strip.parent_scene = Mock()

        # Create tab
        tab = FilmTabWidget(x=0, y=0, width=20, height=20)
        tab.set_insertion_type("after", 0)

        # Should not crash
        film_strip._insert_frame_at_tab(tab)

        # Should not call parent scene
        film_strip.parent_scene._on_frame_inserted.assert_not_called()

    def test_film_strip_no_animation_without_scene(self):
        """Test film strip handles missing parent scene gracefully."""
        # Create animated sprite
        frame1 = SpriteFrame(self.surface1, duration=0.5)
        animated_sprite = AnimatedSprite()
        animated_sprite._animations = {"idle": [frame1]}

        # Create film strip widget without parent scene
        film_strip = FilmStripWidget(x=0, y=0, width=100, height=50)
        film_strip.set_animated_sprite(animated_sprite)
        film_strip.current_animation = "idle"
        film_strip.parent_scene = None

        # Create tab
        tab = FilmTabWidget(x=0, y=0, width=20, height=20)
        tab.set_insertion_type("after", 0)

        # Should not crash
        film_strip._insert_frame_at_tab(tab)

        # Frame should NOT be added when there's no parent scene
        # (the method returns early without doing anything)
        assert len(animated_sprite._animations["idle"]) == 1
        assert animated_sprite._is_playing  # Still playing from film strip setup

    def test_film_strip_animation_timing_after_reinitialization(self):
        """Test that film strip animation timing works after reinitialization."""
        # Create animated sprite with single frame
        frame1 = SpriteFrame(self.surface1, duration=0.1)
        animated_sprite = AnimatedSprite()
        animated_sprite._animations = {"idle": [frame1]}
        animated_sprite.frame_manager.current_animation = "idle"

        # Create film strip widget
        film_strip = FilmStripWidget(x=0, y=0, width=100, height=50)
        film_strip.set_animated_sprite(animated_sprite)
        film_strip.current_animation = "idle"
        film_strip.parent_scene = Mock()
        film_strip.parent_scene._on_frame_inserted = Mock()

        # Add second frame
        tab = FilmTabWidget(x=0, y=0, width=20, height=20)
        tab.set_insertion_type("after", 0)
        film_strip._insert_frame_at_tab(tab)

        # Verify preview animation timing was reinitialized
        assert film_strip.preview_animation_times["idle"] == 0.0  # Multi-frame timing
        assert film_strip.preview_animation_speeds["idle"] == 1.0
        assert len(film_strip.preview_frame_durations["idle"]) == TEST_SIZE_2

        # Test that animation updates work
        film_strip.update_animations(0.05)  # 50ms
        assert film_strip.current_frame == animated_sprite.current_frame

    def test_film_strip_multiple_animations_frame_addition(self):
        """Test film strip with multiple animations."""
        # Create animated sprite with multiple animations
        frame1 = SpriteFrame(self.surface1, duration=0.5)
        frame2 = SpriteFrame(self.surface2, duration=0.5)
        animated_sprite = AnimatedSprite()
        animated_sprite._animations = {
            "idle": [frame1],  # Single frame
            "walk": [frame1, frame2]  # Multi frame
        }
        animated_sprite.frame_manager.current_animation = "idle"

        # Create film strip widget
        film_strip = FilmStripWidget(x=0, y=0, width=100, height=50)
        film_strip.set_animated_sprite(animated_sprite)
        film_strip.current_animation = "idle"
        film_strip.parent_scene = Mock()
        film_strip.parent_scene._on_frame_inserted = Mock()

        # Add frame to idle animation
        tab = FilmTabWidget(x=0, y=0, width=20, height=20)
        tab.set_insertion_type("after", 0)
        film_strip._insert_frame_at_tab(tab)

        # Verify idle animation started
        assert len(animated_sprite._animations["idle"]) == TEST_SIZE_2
        assert animated_sprite._is_playing
        assert animated_sprite._is_looping

        # Verify walk animation unchanged
        assert len(animated_sprite._animations["walk"]) == TEST_SIZE_2

        # Verify preview animations were reinitialized for all animations
        assert "idle" in film_strip.preview_animation_times
        assert "walk" in film_strip.preview_animation_times
