#!/usr/bin/env python3
"""Test-driven development tests for animation system audit issues.

These tests are designed to expose bugs and missing functionality
in the animation system before implementing fixes.
"""

import unittest

import pygame
from glitchygames.sprites import SpriteFactory
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame


class TestAnimationSystemAudit(unittest.TestCase):
    """Test cases that expose animation system issues."""

    def setUp(self):
        """Set up test fixtures."""
        pygame.init()
        pygame.display.set_mode((800, 600))

    def tearDown(self):
        """Clean up test fixtures."""
        pygame.quit()

    def test_frame_interval_bug_exposure(self):
        """Test that exposes the frame_interval property bug.

        BUG: frame_interval accesses self._current_animation instead of
        self.frame_manager.current_animation, causing incorrect behavior
        when animation state is managed through frame_manager.
        """
        # Load an animated sprite
        sprite = SpriteFactory.load_sprite(filename="colors.toml")

        # Set animation through frame_manager
        sprite.frame_manager.current_animation = "timing_demo"
        sprite.frame_manager.current_frame = 0

        # This should work but will fail due to the bug
        try:
            interval = sprite.frame_interval
            self.assertIsInstance(interval, float)
            self.assertGreater(interval, 0)
            print(f"✅ Frame interval retrieved: {interval}")
        except (AttributeError, KeyError, IndexError) as e:
            self.fail(f"frame_interval property failed: {e}")

    def test_animations_property_interface_mismatch(self):
        """Test that exposes the animations property interface mismatch.

        BUG: animations property returns dict[str, list] but interface
        expects dict[str, dict] (metadata, not frames).
        """
        sprite = SpriteFactory.load_sprite(filename="colors.toml")

        # Get animations property
        animations = sprite.animations

        # Test discrete property accessors for metadata
        self.assertIsInstance(sprite.animation_count, int)
        self.assertGreater(sprite.animation_count, 0)

        self.assertIsInstance(sprite.current_animation_frame_count, int)
        self.assertGreater(sprite.current_animation_frame_count, 0)

        self.assertIsInstance(sprite.current_animation_total_duration, float)
        self.assertGreater(sprite.current_animation_total_duration, 0)

        self.assertIsInstance(sprite.animation_names, list)
        self.assertGreater(len(sprite.animation_names), 0)

        # Test read/write properties
        original_looping = sprite.is_looping
        sprite.is_looping = not original_looping
        self.assertEqual(sprite.is_looping, not original_looping)
        sprite.is_looping = original_looping  # Restore

        print(f"✅ Animation count: {sprite.animation_count}")
        print(f"✅ Current animation frames: {sprite.current_animation_frame_count}")
        print(f"✅ Current animation duration: {sprite.current_animation_total_duration}")
        print(f"✅ Animation names: {sprite.animation_names}")

    def test_missing_add_frame_method(self):
        """Test that exposes missing add_frame method.

        MISSING: add_frame method to add individual frames to animations.
        """
        sprite = AnimatedSprite()

        # Create a test frame
        frame = SpriteFrame(pygame.Surface((16, 16)))
        frame.duration = 0.5

        # This should work but will fail due to missing method
        try:
            sprite.add_frame("test_anim", frame, index=0)
            print("✅ add_frame method exists")

            # Verify frame was added
            self.assertIn("test_anim", sprite._animations)
            self.assertEqual(len(sprite._animations["test_anim"]), 1)

        except AttributeError as e:
            self.fail(f"add_frame method missing: {e}")

    def test_missing_remove_frame_method(self):
        """Test that exposes missing remove_frame method.

        MISSING: remove_frame method to remove frames from animations.
        """
        sprite = AnimatedSprite()

        # Add some frames first - create all frames and add them as one animation
        frames = [SpriteFrame(pygame.Surface((16, 16))) for _ in range(3)]
        for frame in frames:
            frame.duration = 0.5
        sprite.add_animation("test_anim", frames)

        # This should work but will fail due to missing method
        try:
            sprite.remove_frame("test_anim", 1)
            print("✅ remove_frame method exists")

            # Verify frame was removed
            self.assertEqual(len(sprite._animations["test_anim"]), 2)

        except AttributeError as e:
            self.fail(f"remove_frame method missing: {e}")

    def test_get_frame_error_handling(self):
        """Test that exposes missing error handling in get_frame method.

        MISSING: Proper error handling for invalid animation names and frame indices.
        """
        sprite = SpriteFactory.load_sprite(filename="colors.toml")

        # Test invalid animation name
        with self.assertRaises(ValueError):
            sprite.get_frame("nonexistent_animation", 0)

        # Test invalid frame index
        with self.assertRaises(IndexError):
            sprite.get_frame("timing_demo", 999)

        # Test negative frame index
        with self.assertRaises(IndexError):
            sprite.get_frame("timing_demo", -1)

        print("✅ get_frame error handling works correctly")

    def test_frame_interval_bounds_checking(self):
        """Test that exposes missing bounds checking in frame_interval.

        MISSING: Bounds checking for frame_interval property.
        """
        sprite = AnimatedSprite()

        # Test with no animations
        interval = sprite.frame_interval
        self.assertEqual(interval, 0.5)  # Should return default

        # Test with invalid current animation
        sprite.frame_manager.current_animation = "nonexistent"
        interval = sprite.frame_interval
        self.assertEqual(interval, 0.5)  # Should return default

        # Test with invalid frame index
        sprite.add_animation("test", [SpriteFrame(pygame.Surface((16, 16)))])
        sprite.frame_manager.current_animation = "test"
        sprite.frame_manager.current_frame = 999
        interval = sprite.frame_interval
        self.assertEqual(interval, 0.5)  # Should return default

        print("✅ frame_interval bounds checking works correctly")

    def test_animation_state_consistency(self):
        """Test that exposes potential state inconsistency issues.

        ISSUE: AnimatedSprite maintains _is_playing/_is_looping while
        FrameManager manages frame state - potential for inconsistency.
        """
        sprite = AnimatedSprite()

        # Set state through different paths
        sprite._is_playing = True
        sprite._is_looping = True
        sprite.frame_manager.current_animation = "test"

        # State should be consistent
        self.assertTrue(sprite.is_playing)
        self.assertTrue(sprite.is_looping)
        self.assertEqual(sprite.current_animation, "test")

        # Test state changes through frame_manager
        sprite.frame_manager.current_animation = "new_anim"
        self.assertEqual(sprite.current_animation, "new_anim")

        print("✅ Animation state consistency maintained")

    def test_animation_metadata_access(self):
        """Test that exposes missing animation metadata access methods.

        MISSING: Methods to get and set animation metadata.
        """
        sprite = SpriteFactory.load_sprite(filename="colors.toml")

        # Test getting animation metadata
        try:
            metadata = sprite.get_animation_metadata("timing_demo")
            self.assertIsInstance(metadata, dict)
            self.assertIn("frame_count", metadata)
            self.assertIn("total_duration", metadata)
            print("✅ get_animation_metadata method exists")
        except AttributeError:
            self.fail("get_animation_metadata method missing")

        # Test setting animation metadata
        try:
            sprite.set_animation_metadata("timing_demo", {"is_looping": True})
            print("✅ set_animation_metadata method exists")
        except AttributeError:
            self.fail("set_animation_metadata method missing")

    def test_animation_validation(self):
        """Test that exposes missing animation validation.

        MISSING: Validation for animation names, frame indices, etc.
        """
        sprite = AnimatedSprite()

        # Test invalid animation name in set_animation
        with self.assertRaises(ValueError):
            sprite.set_animation("nonexistent_animation")

        # Test invalid frame index in set_frame
        sprite.add_animation("test", [SpriteFrame(pygame.Surface((16, 16)))])
        sprite.set_animation("test")

        with self.assertRaises(IndexError):
            sprite.set_frame(999)

        print("✅ Animation validation works correctly")

    def test_animation_edge_cases(self):
        """Test that exposes missing edge case handling.

        MISSING: Proper handling of edge cases like empty animations,
        single-frame animations, etc.
        """
        sprite = AnimatedSprite()

        # Test empty animation
        sprite.add_animation("empty", [])
        sprite.set_animation("empty")

        # Should handle gracefully
        self.assertEqual(sprite.frame_count, 0)
        self.assertIsNone(sprite.get_current_frame())

        # Test single-frame animation
        frame = SpriteFrame(pygame.Surface((16, 16)))
        frame.duration = 1.0
        sprite.add_animation("single", [frame])
        sprite.set_animation("single")

        self.assertEqual(sprite.frame_count, 1)
        self.assertIsNotNone(sprite.get_current_frame())

        print("✅ Animation edge cases handled correctly")


if __name__ == "__main__":
    unittest.main()
