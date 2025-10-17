"""Tests for AnimatedSprite frame addition functionality."""

import pygame
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

# Test constants to avoid magic values
TEST_SIZE_2 = 2
TEST_SIZE_3 = 3


class TestAnimatedSpriteFrameAddition:
    """Test frame addition behavior in AnimatedSprite."""

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

    def test_single_frame_animation_stays_static(self):
        """Test that single-frame animations remain static."""
        # Create single frame
        frame1 = SpriteFrame(self.surface1, duration=0.5)

        # Create animated sprite with single frame
        sprite = AnimatedSprite()
        sprite._animations = {"idle": [frame1]}
        sprite.frame_manager.current_animation = "idle"
        sprite.frame_manager.current_frame = 0
        sprite._is_playing = False
        sprite._is_looping = False

        # Verify initial state
        assert len(sprite._animations["idle"]) == 1
        assert not sprite._is_playing
        assert not sprite._is_looping

        # Update animation - should stay on frame 0
        sprite.update(0.1)  # 100ms
        assert sprite.current_frame == 0
        assert not sprite._is_playing

    def test_adding_second_frame_starts_animation(self):
        """Test that adding a second frame to single-frame animation starts it."""
        # Create frames
        frame1 = SpriteFrame(self.surface1, duration=0.5)
        frame2 = SpriteFrame(self.surface2, duration=0.5)

        # Create animated sprite with single frame
        sprite = AnimatedSprite()
        sprite._animations = {"idle": [frame1]}
        sprite.frame_manager.current_animation = "idle"
        sprite.frame_manager.current_frame = 0
        sprite._is_playing = False
        sprite._is_looping = False

        # Verify initial state
        assert len(sprite._animations["idle"]) == 1
        assert not sprite._is_playing
        assert not sprite._is_looping

        # Add second frame
        sprite.add_frame("idle", frame2)

        # Verify animation started
        assert len(sprite._animations["idle"]) == TEST_SIZE_2
        assert sprite._is_playing
        assert sprite._is_looping

    def test_adding_second_frame_with_insertion(self):
        """Test that adding second frame at specific index starts animation."""
        # Create frames
        frame1 = SpriteFrame(self.surface1, duration=0.5)
        frame2 = SpriteFrame(self.surface2, duration=0.5)

        # Create animated sprite with single frame
        sprite = AnimatedSprite()
        sprite._animations = {"idle": [frame1]}
        sprite.frame_manager.current_animation = "idle"
        sprite._is_playing = False
        sprite._is_looping = False

        # Add second frame at index 0 (before first frame)
        sprite.add_frame("idle", frame2, index=0)

        # Verify animation started
        assert len(sprite._animations["idle"]) == TEST_SIZE_2
        assert sprite._is_playing
        assert sprite._is_looping

    def test_adding_frame_to_multi_frame_animation(self):
        """Test that adding frame to multi-frame animation doesn't change playing state."""
        # Create frames
        frame1 = SpriteFrame(self.surface1, duration=0.5)
        frame2 = SpriteFrame(self.surface2, duration=0.5)
        frame3 = SpriteFrame(self.surface3, duration=0.5)

        # Create animated sprite with two frames
        sprite = AnimatedSprite()
        sprite._animations = {"idle": [frame1, frame2]}
        sprite.frame_manager.current_animation = "idle"
        sprite._is_playing = True
        sprite._is_looping = True

        # Add third frame
        sprite.add_frame("idle", frame3)

        # Verify state unchanged
        assert len(sprite._animations["idle"]) == TEST_SIZE_3
        assert sprite._is_playing
        assert sprite._is_looping

    def test_adding_frame_to_stopped_multi_frame_animation(self):
        """Test that adding frame to stopped multi-frame animation doesn't restart it."""
        # Create frames
        frame1 = SpriteFrame(self.surface1, duration=0.5)
        frame2 = SpriteFrame(self.surface2, duration=0.5)
        frame3 = SpriteFrame(self.surface3, duration=0.5)

        # Create animated sprite with two frames, but stopped
        sprite = AnimatedSprite()
        sprite._animations = {"idle": [frame1, frame2]}
        sprite.frame_manager.current_animation = "idle"
        sprite._is_playing = False
        sprite._is_looping = False

        # Add third frame
        sprite.add_frame("idle", frame3)

        # Verify state unchanged (should not restart)
        assert len(sprite._animations["idle"]) == TEST_SIZE_3
        assert not sprite._is_playing
        assert not sprite._is_looping

    def test_animation_advances_after_second_frame_added(self):
        """Test that animation properly advances after second frame is added."""
        # Create frames
        frame1 = SpriteFrame(self.surface1, duration=0.1)  # Short duration
        frame2 = SpriteFrame(self.surface2, duration=0.1)

        # Create animated sprite with single frame
        sprite = AnimatedSprite()
        sprite._animations = {"idle": [frame1]}
        sprite.frame_manager.current_animation = "idle"
        sprite.frame_manager.current_frame = 0
        sprite._is_playing = False
        sprite._is_looping = False

        # Add second frame
        sprite.add_frame("idle", frame2)

        # Verify animation started
        assert sprite._is_playing
        assert sprite._is_looping

        # Update animation and verify it advances
        sprite.update(0.15)  # Should advance past first frame duration

        # Should have advanced to frame 1
        assert sprite.current_frame == 1

        # Update more to test looping
        sprite.update(0.15)  # Should loop back to frame 0
        assert sprite.current_frame == 0

    def test_multiple_animations_frame_addition(self):
        """Test frame addition with multiple animations."""
        # Create frames
        frame1 = SpriteFrame(self.surface1, duration=0.5)
        frame2 = SpriteFrame(self.surface2, duration=0.5)

        # Create animated sprite with multiple animations
        sprite = AnimatedSprite()
        sprite._animations = {
            "idle": [frame1],
            "walk": [frame1, frame2]  # Already multi-frame
        }
        sprite.frame_manager.current_animation = "idle"
        sprite._is_playing = False
        sprite._is_looping = False

        # Add frame to single-frame animation
        sprite.add_frame("idle", frame2)

        # Verify only idle animation started
        assert len(sprite._animations["idle"]) == TEST_SIZE_2
        assert sprite._is_playing
        assert sprite._is_looping

        # Verify walk animation unchanged
        assert len(sprite._animations["walk"]) == TEST_SIZE_2
