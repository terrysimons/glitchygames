"""Test-driven development tests for animation system audit issues.

These tests are designed to expose bugs and missing functionality
in the animation system before implementing fixes.
"""

import unittest
from pathlib import Path

import pygame
from glitchygames.sprites import SpriteFactory
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

# Constants for test thresholds
DEFAULT_FRAME_INTERVAL = 0.5
EXPECTED_FRAME_COUNT = 2


def get_resource_path(filename: str) -> str:
    """Get the full path to a resource file."""
    return str(
        Path(__file__).parent.parent
        / "glitchygames"
        / "examples"
        / "resources"
        / "sprites"
        / filename
    )


class TestAnimationSystemAudit(unittest.TestCase):
    """Test cases that expose animation system issues."""

    @staticmethod
    def setUp():
        """Set up test fixtures."""
        pygame.init()
        pygame.display.set_mode((800, 600))

    @staticmethod
    def tearDown():
        """Clean up test fixtures."""
        pygame.quit()

    def test_frame_interval_bug_exposure(self):
        """Test that exposes the frame_interval property bug.

        BUG: frame_interval accesses self._current_animation instead of
        self.frame_manager.current_animation, causing incorrect behavior
        when animation state is managed through frame_manager.
        """
        # Load an animated sprite
        sprite = SpriteFactory.load_sprite(filename=get_resource_path("colors.toml"))

        # Set animation through frame_manager
        sprite.frame_manager.current_animation = "timing_demo"
        sprite.frame_manager.current_frame = 0

        # This should work but will fail due to the bug
        try:
            interval = sprite.frame_interval
            assert isinstance(interval, float)
            assert interval > 0
        except (AttributeError, KeyError, IndexError) as e:
            self.fail(f"frame_interval property failed: {e}")

    @staticmethod
    def test_animations_property_interface_mismatch():
        """Test that exposes the animations property interface mismatch.

        BUG: animations property returns dict[str, list] but interface
        expects dict[str, dict] (metadata, not frames).
        """
        sprite = SpriteFactory.load_sprite(filename=get_resource_path("colors.toml"))

        # Test discrete property accessors for metadata
        assert isinstance(sprite.animation_count, int)
        assert sprite.animation_count > 0

        assert isinstance(sprite.current_animation_frame_count, int)
        assert sprite.current_animation_frame_count > 0

        assert isinstance(sprite.current_animation_total_duration, float)
        assert sprite.current_animation_total_duration > 0

        assert isinstance(sprite.animation_names, list)
        assert len(sprite.animation_names) > 0

        # Test read/write properties
        original_looping = sprite.is_looping
        sprite.is_looping = not original_looping
        expected_looping = not original_looping
        assert sprite.is_looping == expected_looping
        sprite.is_looping = original_looping  # Restore

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

            # Verify frame was added
            assert "test_anim" in sprite._animations
            assert len(sprite._animations["test_anim"]) == 1

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

            # Verify frame was removed
            assert len(sprite._animations["test_anim"]) == EXPECTED_FRAME_COUNT

        except AttributeError as e:
            self.fail(f"remove_frame method missing: {e}")

    def test_get_frame_error_handling(self):
        """Test that exposes missing error handling in get_frame method.

        MISSING: Proper error handling for invalid animation names and frame indices.
        """
        sprite = SpriteFactory.load_sprite(filename=get_resource_path("colors.toml"))

        # Test invalid animation name
        try:
            sprite.get_frame("nonexistent_animation", 0)
            self.fail("Expected ValueError for invalid animation name")
        except ValueError:
            pass

        # Test invalid frame index
        try:
            sprite.get_frame("timing_demo", 999)
            self.fail("Expected IndexError for invalid frame index")
        except IndexError:
            pass

        # Test negative frame index
        try:
            sprite.get_frame("timing_demo", -1)
            self.fail("Expected IndexError for negative frame index")
        except IndexError:
            pass

        # Print statement removed for linting compliance

    @staticmethod
    def test_frame_interval_bounds_checking():
        """Test that exposes missing bounds checking in frame_interval.

        MISSING: Bounds checking for frame_interval property.
        """
        sprite = AnimatedSprite()

        # Test with no animations
        interval = sprite.frame_interval
        assert interval == DEFAULT_FRAME_INTERVAL  # Should return default

        # Test with invalid current animation
        sprite.frame_manager.current_animation = "nonexistent"
        interval = sprite.frame_interval
        assert interval == DEFAULT_FRAME_INTERVAL  # Should return default

        # Test with invalid frame index
        sprite.add_animation("test", [SpriteFrame(pygame.Surface((16, 16)))])
        sprite.frame_manager.current_animation = "test"
        sprite.frame_manager.current_frame = 999
        interval = sprite.frame_interval
        assert interval == DEFAULT_FRAME_INTERVAL  # Should return default

    @staticmethod
    def test_animation_state_consistency():
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
        assert sprite.is_playing
        assert sprite.is_looping
        assert sprite.current_animation == "test"

        # Test state changes through frame_manager
        sprite.frame_manager.current_animation = "new_anim"
        assert sprite.current_animation == "new_anim"

    def test_animation_metadata_access(self):
        """Test that exposes missing animation metadata access methods.

        MISSING: Methods to get and set animation metadata.
        """
        sprite = SpriteFactory.load_sprite(filename=get_resource_path("colors.toml"))

        # Test getting animation metadata
        try:
            metadata = sprite.get_animation_metadata("timing_demo")
            assert isinstance(metadata, dict)
            assert "frame_count" in metadata
            assert "total_duration" in metadata
        except AttributeError:
            self.fail("get_animation_metadata method missing")

        # Test setting animation metadata
        try:
            sprite.set_animation_metadata("timing_demo", {"is_looping": True})
        except AttributeError:
            self.fail("set_animation_metadata method missing")

    def test_animation_validation(self):
        """Test that exposes missing animation validation.

        MISSING: Validation for animation names, frame indices, etc.
        """
        sprite = AnimatedSprite()

        # Test invalid animation name in set_animation
        try:
            sprite.set_animation("nonexistent_animation")
            self.fail("Expected ValueError for invalid animation name")
        except ValueError:
            pass

        # Test invalid frame index in set_frame
        sprite.add_animation("test", [SpriteFrame(pygame.Surface((16, 16)))])
        sprite.set_animation("test")

        try:
            sprite.set_frame(999)
            self.fail("Expected IndexError for invalid frame index")
        except IndexError:
            pass

    @staticmethod
    def test_animation_edge_cases():
        """Test that exposes missing edge case handling.

        MISSING: Proper handling of edge cases like empty animations,
        single-frame animations, etc.
        """
        sprite = AnimatedSprite()

        # Test empty animation
        sprite.add_animation("empty", [])
        sprite.set_animation("empty")

        # Should handle gracefully
        assert sprite.frame_count == 0
        assert sprite.get_current_frame() is None

        # Test single-frame animation
        frame = SpriteFrame(pygame.Surface((16, 16)))
        frame.duration = 1.0
        sprite.add_animation("single", [frame])
        sprite.set_animation("single")

        assert sprite.frame_count == 1
        assert sprite.get_current_frame() is not None


if __name__ == "__main__":
    unittest.main()
