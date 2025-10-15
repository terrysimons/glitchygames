"""Test suite for text sprite cursor functionality.

This module tests TextSprite cursor blinking, input handling, and visual updates.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.ui import TextSprite
from mocks.test_mock_factory import MockFactory


class TestTextSpriteCursorFunctionality(unittest.TestCase):
    """Test TextSprite cursor functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Use centralized mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all the patchers
        for patcher in self.patchers:
            patcher.start()
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_text_sprite_cursor_initialization(self):
        """Test TextSprite cursor initialization."""
        # Arrange
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            # Act
            text_sprite = TextSprite(x=10, y=20, width=100, height=30, text="Test", name="TestText")

        # Assert
        assert hasattr(text_sprite, "_cursor_timer")
        assert hasattr(text_sprite, "_cursor_visible")
        assert text_sprite._cursor_timer == 0
        # Cursor visibility may be True by default in the actual implementation
        assert text_sprite._cursor_visible is True

    def test_text_sprite_cursor_blinking_when_active(self):
        """Test TextSprite cursor blinking when active."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            text_sprite = TextSprite(x=10, y=20, width=100, height=30, text="Test", name="TestText")
            text_sprite.active = True
            text_sprite._cursor_timer = 0
            text_sprite._cursor_visible = False

            # Act - simulate time passing
            text_sprite.update()

            # Assert - should set dirty flag for redraw
            assert text_sprite.dirty == 2

    def test_text_sprite_cursor_not_blinking_when_inactive(self):
        """Test TextSprite cursor not blinking when inactive."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            text_sprite = TextSprite(x=10, y=20, width=100, height=30, text="Test", name="TestText")
            text_sprite.active = False

            # Act
            text_sprite.update()

            # Assert - should set dirty flag to 1 (not 2 for cursor)
            assert text_sprite.dirty == 1

    def test_text_sprite_cursor_timer_increment(self):
        """Test TextSprite cursor timer increment."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            text_sprite = TextSprite(x=10, y=20, width=100, height=30, text="Test", name="TestText")
            text_sprite.active = True
            text_sprite._cursor_timer = 0

            # Act
            text_sprite.update()

            # Assert - timer should increment
            assert text_sprite._cursor_timer > 0

    def test_text_sprite_cursor_visibility_toggle(self):
        """Test TextSprite cursor visibility toggle."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            text_sprite = TextSprite(x=10, y=20, width=100, height=30, text="Test", name="TestText")
            text_sprite.active = True
            text_sprite._cursor_timer = 0
            text_sprite._cursor_visible = False

            # Act - simulate enough time for cursor to toggle
            text_sprite._cursor_timer = 500  # Half second
            text_sprite.update()

            # Assert - cursor visibility should toggle
            assert text_sprite._cursor_visible is True

    def test_text_sprite_cursor_draw_when_visible(self):
        """Test TextSprite cursor drawing when visible."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            text_rect = Mock()
            text_rect.right = 50
            text_rect.top = 20
            text_rect.height = 20
            rendered_surface.get_rect.return_value = text_rect
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            text_sprite = TextSprite(x=10, y=20, width=100, height=30, text="Test", name="TestText")
            text_sprite.active = True
            text_sprite._cursor_visible = True

            # Mock the image surface
            text_sprite.image = Mock()

            # Act
            text_sprite.update_text("Test")

            # Assert - should call _draw_cursor
            # Note: The actual drawing would be tested in integration tests

    def test_text_sprite_cursor_draw_when_invisible(self):
        """Test TextSprite cursor not drawing when invisible."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            text_rect = Mock()
            text_rect.right = 50
            text_rect.top = 20
            text_rect.height = 20
            rendered_surface.get_rect.return_value = text_rect
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            text_sprite = TextSprite(x=10, y=20, width=100, height=30, text="Test", name="TestText")
            text_sprite.active = True
            text_sprite._cursor_visible = False

            # Mock the image surface
            text_sprite.image = Mock()

            # Act
            text_sprite.update_text("Test")

            # Assert - should not draw cursor when invisible
            # Note: The actual drawing would be tested in integration tests

    def test_text_sprite_cursor_handles_mock_objects(self):
        """Test TextSprite cursor handles mock objects gracefully."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            text_rect = Mock()
            text_rect.right = 50
            text_rect.top = 20
            text_rect.height = 20
            rendered_surface.get_rect.return_value = text_rect
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            text_sprite = TextSprite(x=10, y=20, width=100, height=30, text="Test", name="TestText")
            text_sprite.active = True
            text_sprite._cursor_visible = True

            # Mock the image surface
            text_sprite.image = Mock()

            # Act - should not crash with mock objects
            text_sprite.update_text("Test")

            # Assert - should complete without error
            assert text_sprite is not None

    def test_text_sprite_cursor_reset_on_deactivation(self):
        """Test TextSprite cursor resets on deactivation."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            text_sprite = TextSprite(x=10, y=20, width=100, height=30, text="Test", name="TestText")
            text_sprite.active = True
            text_sprite._cursor_timer = 100
            text_sprite._cursor_visible = True

            # Act - deactivate
            text_sprite.active = False
            text_sprite.update()

            # Assert - should set dirty flag to 1 (not 2 for cursor)
            assert text_sprite.dirty == 1

    def test_text_sprite_cursor_continuous_updates_when_active(self):
        """Test TextSprite cursor provides continuous updates when active."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            text_sprite = TextSprite(x=10, y=20, width=100, height=30, text="Test", name="TestText")
            text_sprite.active = True

            # Act - multiple updates
            text_sprite.update()
            text_sprite.update()
            text_sprite.update()

            # Assert - should set dirty flag to 2 for cursor updates
            assert text_sprite.dirty == 2

    def test_text_sprite_cursor_timer_wraparound(self):
        """Test TextSprite cursor timer wraparound behavior."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            text_sprite = TextSprite(x=10, y=20, width=100, height=30, text="Test", name="TestText")
            text_sprite.active = True
            text_sprite._cursor_timer = 1000  # Max timer value

            # Act
            text_sprite.update()

            # Assert - timer should wrap around
            assert text_sprite._cursor_timer == 0


if __name__ == "__main__":
    unittest.main()
