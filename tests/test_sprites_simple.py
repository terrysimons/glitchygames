"""Focused, low-friction tests for sprites module quick coverage wins."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pygame
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.sprites import Sprite, SpriteFactory

# Constants for test values
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
SPRITE_WIDTH_100 = 100
SPRITE_WIDTH_200 = 200
SPRITE_HEIGHT_50 = 50
SPRITE_HEIGHT_75 = 75
DT_60_FPS = 0.016


class TestSpriteBreakWhen(unittest.TestCase):
    """Verify class-level breakpoint registration behavior."""

    def test_break_when_none_creates_list(self):  # noqa: PLR6301
        """Test that break_when creates a list when passed None."""
        # Reset for test isolation
        Sprite.SPRITE_BREAKPOINTS = None
        Sprite.break_when(None)

        assert Sprite.SPRITE_BREAKPOINTS is not None
        assert Sprite.SPRITE_BREAKPOINTS == []

    def test_break_when_specific_type_appends(self):  # noqa: PLR6301
        """Test that break_when appends to the list when given a sprite type."""
        # Reset and append
        Sprite.SPRITE_BREAKPOINTS = []
        Sprite.break_when(sprite_type="Dummy")
        assert len(Sprite.SPRITE_BREAKPOINTS) >= 1


class TestSpriteInitialization(unittest.TestCase):
    """Exercise Sprite.__init__ with display/surface mocked."""

    def test_sprite_initialization_sets_screen_dimensions(self):  # noqa: PLR6301
        """Test that sprite initialization captures screen dimensions."""
        # Mock pygame display surface and surface class
        with patch("pygame.display.get_surface") as mock_get_surface:
            display_surface = Mock()
            display_surface.get_width.return_value = 800
            display_surface.get_height.return_value = 600
            mock_get_surface.return_value = display_surface

            with patch("pygame.Surface") as mock_surface_cls:
                surface_instance = Mock()
                surface_instance.get_rect.return_value = Mock(x=0, y=0, width=10, height=10)
                mock_surface_cls.return_value = surface_instance

                with patch("pygame.sprite.LayeredDirty") as mock_group_cls:
                    group_instance = Mock()
                    mock_group_cls.return_value = group_instance

                    # Ensure breakpoints disabled to avoid hitting breakpoint()
                    Sprite.SPRITE_BREAKPOINTS = None

                    # Instantiate a minimal Sprite
                    s = Sprite(x=1, y=2, width=3, height=4, name="S")

                    # Validate screen dimensions captured
                    assert s.screen_width == SCREEN_WIDTH
                    assert s.screen_height == SCREEN_HEIGHT


class TestSpriteProperties(unittest.TestCase):
    """Test Sprite properties and methods."""

    def setUp(self):  # noqa: PLR6301
        """Set up test fixtures."""
        # Reset SPRITE_BREAKPOINTS to None to avoid triggering the breakpoint() in Sprite.__init__
        Sprite.SPRITE_BREAKPOINTS = None

    def test_sprite_width_property(self):  # noqa: PLR6301
        """Test Sprite width property getter and setter."""
        with patch("pygame.display.get_surface") as mock_get_surface:
            display_surface = Mock()
            display_surface.get_width.return_value = 800
            display_surface.get_height.return_value = 600
            mock_get_surface.return_value = display_surface

            with patch("pygame.Surface") as mock_surface_cls:
                surface_instance = Mock()
                surface_instance.get_rect.return_value = Mock(x=0, y=0, width=10, height=10)
                mock_surface_cls.return_value = surface_instance

                with patch("pygame.sprite.LayeredDirty") as mock_group_cls:
                    group_instance = Mock()
                    mock_group_cls.return_value = group_instance

                    s = Sprite(
                        x=1, y=2, width=SPRITE_WIDTH_100, height=SPRITE_HEIGHT_50, name="TestSprite"
                    )

                    # Test width getter
                    assert s.width == SPRITE_WIDTH_100

                    # Test width setter
                    s.width = SPRITE_WIDTH_200
                    assert s.width == SPRITE_WIDTH_200
                    assert s.dirty == 1

    def test_sprite_height_property(self):  # noqa: PLR6301
        """Test Sprite height property getter and setter."""
        with patch("pygame.display.get_surface") as mock_get_surface:
            display_surface = Mock()
            display_surface.get_width.return_value = 800
            display_surface.get_height.return_value = 600
            mock_get_surface.return_value = display_surface

            with patch("pygame.Surface") as mock_surface_cls:
                surface_instance = Mock()
                surface_instance.get_rect.return_value = Mock(x=0, y=0, width=10, height=10)
                mock_surface_cls.return_value = surface_instance

                with patch("pygame.sprite.LayeredDirty") as mock_group_cls:
                    group_instance = Mock()
                    mock_group_cls.return_value = group_instance

                    s = Sprite(
                        x=1, y=2, width=SPRITE_WIDTH_100, height=SPRITE_HEIGHT_50, name="TestSprite"
                    )

                    # Test height getter
                    assert s.height == SPRITE_HEIGHT_50

                    # Test height setter
                    s.height = SPRITE_HEIGHT_75
                    assert s.height == SPRITE_HEIGHT_75
                    assert s.dirty == 1

    def test_sprite_dt_tick(self):  # noqa: PLR6301
        """Test Sprite dt_tick method."""
        with patch("pygame.display.get_surface") as mock_get_surface:
            display_surface = Mock()
            display_surface.get_width.return_value = 800
            display_surface.get_height.return_value = 600
            mock_get_surface.return_value = display_surface

            with patch("pygame.Surface") as mock_surface_cls:
                surface_instance = Mock()
                surface_instance.get_rect.return_value = Mock(x=0, y=0, width=10, height=10)
                mock_surface_cls.return_value = surface_instance

                with patch("pygame.sprite.LayeredDirty") as mock_group_cls:
                    group_instance = Mock()
                    mock_group_cls.return_value = group_instance

                    s = Sprite(
                        x=1, y=2, width=SPRITE_WIDTH_100, height=SPRITE_HEIGHT_50, name="TestSprite"
                    )

                    # Test dt_tick
                    initial_dt_timer = s.dt_timer
                    s.dt_tick(DT_60_FPS)  # 60 FPS delta time
                    assert s.dt == DT_60_FPS
                    assert s.dt_timer == initial_dt_timer + DT_60_FPS

    def test_sprite_update(self):  # noqa: PLR6301
        """Test Sprite update method (should not raise exception)."""
        with patch("pygame.display.get_surface") as mock_get_surface:
            display_surface = Mock()
            display_surface.get_width.return_value = 800
            display_surface.get_height.return_value = 600
            mock_get_surface.return_value = display_surface

            with patch("pygame.Surface") as mock_surface_cls:
                surface_instance = Mock()
                surface_instance.get_rect.return_value = Mock(x=0, y=0, width=10, height=10)
                mock_surface_cls.return_value = surface_instance

                with patch("pygame.sprite.LayeredDirty") as mock_group_cls:
                    group_instance = Mock()
                    mock_group_cls.return_value = group_instance

                    s = Sprite(x=1, y=2, width=100, height=50, name="TestSprite")

                    # Test update method (should not raise exception)
                    s.update()

    def test_sprite_event_handlers(self):  # noqa: PLR6301
        """Test Sprite event handler methods."""
        with patch("pygame.display.get_surface") as mock_get_surface:
            display_surface = Mock()
            display_surface.get_width.return_value = 800
            display_surface.get_height.return_value = 600
            mock_get_surface.return_value = display_surface

            with patch("pygame.Surface") as mock_surface_cls:
                surface_instance = Mock()
                surface_instance.get_rect.return_value = Mock(x=0, y=0, width=10, height=10)
                mock_surface_cls.return_value = surface_instance

                with patch("pygame.sprite.LayeredDirty") as mock_group_cls:
                    group_instance = Mock()
                    mock_group_cls.return_value = group_instance

                    s = Sprite(x=1, y=2, width=100, height=50, name="TestSprite")

                    # Create mock events
                    mock_event = Mock()
                    mock_event.type = pygame.JOYAXISMOTION

                    # Test various event handlers (should not raise exceptions)
                    s.on_joy_axis_motion_event(mock_event)
                    s.on_joy_button_down_event(mock_event)
                    s.on_joy_button_up_event(mock_event)
                    s.on_joy_hat_motion_event(mock_event)
                    s.on_joy_ball_motion_event(mock_event)
                    s.on_mouse_motion_event(mock_event)
                    s.on_mouse_focus_event(mock_event, None)
                    s.on_mouse_unfocus_event(mock_event)
                    s.on_mouse_enter_event(mock_event)


class TestSpriteFactory(unittest.TestCase):
    """Test SpriteFactory class methods."""

    def test_detect_file_format_default(self):  # noqa: PLR6301
        """Test SpriteFactory._detect_file_format returns 'toml' by default."""
        format_type = SpriteFactory._detect_file_format("test.toml")
        assert format_type == "toml"

    def test_detect_file_format_unknown(self):  # noqa: PLR6301
        """Test SpriteFactory._detect_file_format returns 'toml' for unknown formats."""
        format_type = SpriteFactory._detect_file_format("test.unknown")
        assert format_type == "toml"

    def test_analyze_file_unsupported_format(self):  # noqa: PLR6301
        """Test SpriteFactory._analyze_file raises ValueError for unsupported formats."""
        with patch.object(SpriteFactory, "_detect_file_format", return_value="unsupported"), \
             patch("pathlib.Path.open") as mock_open, \
             patch("toml.load") as mock_toml_load:
            mock_file = Mock()
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=None)
            mock_file.read.return_value = "test content"
            mock_open.return_value = mock_file
            mock_toml_load.return_value = {}

            with pytest.raises(ValueError, match="Unsupported format: unsupported. Only TOML is currently supported."):
                SpriteFactory._analyze_file("test.unsupported")

    def test_analyze_toml_file_basic(self):  # noqa: PLR6301
        """Test SpriteFactory._analyze_toml_file with basic file structure."""
        with patch("pathlib.Path.open") as mock_open:
            mock_file = Mock()
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=None)
            mock_open.return_value = mock_file

            with patch("toml.load") as mock_toml_load:
                mock_toml_load.return_value = {
                    "sprite": {
                        "pixels": "some pixel data"
                    }
                }

                result = SpriteFactory._analyze_toml_file("test.toml")

                assert result["has_sprite_pixels"]
                assert not result["has_animation_sections"]
                assert not result["has_frame_sections"]

    def test_analyze_toml_file_animation(self):  # noqa: PLR6301
        """Test SpriteFactory._analyze_toml_file with animation data."""
        with patch("pathlib.Path.open") as mock_open:
            mock_file = Mock()
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=None)
            mock_open.return_value = mock_file

            with patch("toml.load") as mock_toml_load:
                # Test with animation data that has frame sections
                mock_toml_load.return_value = {
                    "animation": [
                        {"frame": {"pixels": "data1"}},
                        {"frame": {"pixels": "data2"}}
                    ]
                }

                result = SpriteFactory._analyze_toml_file("test.toml")

                assert not result["has_sprite_pixels"]
                assert result["has_animation_sections"]
                assert result["has_frame_sections"]  # Animation with frames

    def test_analyze_toml_file_empty_pixels(self):  # noqa: PLR6301
        """Test SpriteFactory._analyze_toml_file with empty pixels string."""
        with patch("pathlib.Path.open") as mock_open:
            mock_file = Mock()
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=None)
            mock_open.return_value = mock_file

            with patch("toml.load") as mock_toml_load:
                mock_toml_load.return_value = {
                    "sprite": {
                        "pixels": ""  # Empty string should be ignored
                    }
                }

                result = SpriteFactory._analyze_toml_file("test.toml")

                assert not result["has_sprite_pixels"]

    def test_load_sprite_invalid_file(self):  # noqa: PLR6301
        """Test SpriteFactory.load_sprite raises ValueError for invalid file."""
        with patch.object(SpriteFactory, "_analyze_file") as mock_analyze, \
             patch("pathlib.Path.open") as mock_open, \
             patch("toml.load") as mock_toml_load:
            mock_analyze.return_value = {
                "has_sprite_pixels": False,
                "has_animation_sections": False,
                "has_frame_sections": False
            }
            mock_file = Mock()
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=None)
            mock_file.read.return_value = "test content"
            mock_open.return_value = mock_file
            mock_toml_load.return_value = {}

            with pytest.raises(ValueError, match="Invalid sprite file"):
                SpriteFactory.load_sprite(filename="invalid.toml")

    def test_load_sprite_mixed_content(self):  # noqa: PLR6301
        """Test SpriteFactory.load_sprite raises ValueError for mixed content."""
        with patch.object(SpriteFactory, "_analyze_file") as mock_analyze, \
             patch("pathlib.Path.open") as mock_open, \
             patch("toml.load") as mock_toml_load:
            mock_analyze.return_value = {
                "has_sprite_pixels": True,
                "has_animation_sections": True,
                "has_frame_sections": False
            }
            mock_file = Mock()
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=None)
            mock_file.read.return_value = "test content"
            mock_open.return_value = mock_file
            mock_toml_load.return_value = {}

            with pytest.raises(ValueError, match="Invalid sprite file"):
                SpriteFactory.load_sprite(filename="mixed.toml")


if __name__ == "__main__":
    unittest.main()
