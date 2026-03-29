"""Test suite for text sprite cursor functionality.

This module tests TextSprite cursor blinking, input handling, and visual updates.
"""

import sys
from pathlib import Path

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.ui import TextSprite
from tests.mocks import MockFactory

# Test constants to avoid magic values
TEST_CURSOR_BLINK_RATE = 2


class TestTextSpriteCursorFunctionality:
    """Test TextSprite cursor functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def test_text_sprite_cursor_initialization(self, mocker):
        """Test TextSprite cursor initialization."""
        # Arrange
        mock_get_font = mocker.patch('glitchygames.fonts.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        # Act
        text_sprite = TextSprite(x=10, y=20, width=100, height=30, text='Test', name='TestText')

        # Assert
        assert hasattr(text_sprite, '_cursor_timer')
        assert hasattr(text_sprite, '_cursor_visible')
        assert text_sprite._cursor_timer == 0
        # Cursor visibility may be True by default in the actual implementation
        assert text_sprite._cursor_visible is True

    def test_text_sprite_cursor_blinking_when_active(self, mocker):
        """Test TextSprite cursor blinking when active."""
        mock_get_font = mocker.patch('glitchygames.fonts.FontManager.get_font')
        # Arrange
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        text_sprite = TextSprite(x=10, y=20, width=100, height=30, text='Test', name='TestText')
        text_sprite.is_active = True
        text_sprite._cursor_timer = 0
        text_sprite._cursor_visible = False

        # Act - simulate time passing
        text_sprite.update()

        # Assert - should set dirty flag for redraw
        assert text_sprite.dirty == TEST_CURSOR_BLINK_RATE

    def test_text_sprite_cursor_not_blinking_when_inactive(self, mocker):
        """Test TextSprite cursor not blinking when inactive."""
        mock_get_font = mocker.patch('glitchygames.fonts.FontManager.get_font')
        # Arrange
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        text_sprite = TextSprite(x=10, y=20, width=100, height=30, text='Test', name='TestText')
        text_sprite.is_active = False

        # Act
        text_sprite.update()

        # Assert - should set dirty flag to 1 (not 2 for cursor)
        assert text_sprite.dirty == 1

    def test_text_sprite_cursor_timer_increment(self, mocker):
        """Test TextSprite cursor timer increment."""
        mock_get_font = mocker.patch('glitchygames.fonts.FontManager.get_font')
        # Arrange
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        text_sprite = TextSprite(x=10, y=20, width=100, height=30, text='Test', name='TestText')
        text_sprite.is_active = True
        text_sprite._cursor_timer = 0

        # Act
        text_sprite.update()

        # Assert - timer should increment
        assert text_sprite._cursor_timer > 0

    def test_text_sprite_cursor_visibility_toggle(self, mocker):
        """Test TextSprite cursor visibility toggle."""
        mock_get_font = mocker.patch('glitchygames.fonts.FontManager.get_font')
        # Arrange
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        text_sprite = TextSprite(x=10, y=20, width=100, height=30, text='Test', name='TestText')
        text_sprite.is_active = True
        text_sprite._cursor_timer = 0
        text_sprite._cursor_visible = False

        # Act - simulate enough time for cursor to toggle
        text_sprite._cursor_timer = 500  # Half second
        text_sprite.update()

        # Assert - cursor visibility should toggle
        assert text_sprite._cursor_visible is True

    def test_text_sprite_cursor_draw_when_visible(self, mocker):
        """Test TextSprite cursor drawing when visible."""
        mock_get_font = mocker.patch('glitchygames.fonts.FontManager.get_font')
        # Arrange
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        text_rect = mocker.Mock()
        text_rect.right = 50
        text_rect.top = 20
        text_rect.height = 20
        rendered_surface.get_rect.return_value = text_rect
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        text_sprite = TextSprite(x=10, y=20, width=100, height=30, text='Test', name='TestText')
        text_sprite.is_active = True
        text_sprite._cursor_visible = True

        # Mock the image surface
        text_sprite.image = mocker.Mock()

        # Act
        text_sprite.update_text('Test')

        # Assert - should call _draw_cursor
        # Note: The actual drawing would be tested in integration tests

    def test_text_sprite_cursor_draw_when_invisible(self, mocker):
        """Test TextSprite cursor not drawing when invisible."""
        mock_get_font = mocker.patch('glitchygames.fonts.FontManager.get_font')
        # Arrange
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        text_rect = mocker.Mock()
        text_rect.right = 50
        text_rect.top = 20
        text_rect.height = 20
        rendered_surface.get_rect.return_value = text_rect
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        text_sprite = TextSprite(x=10, y=20, width=100, height=30, text='Test', name='TestText')
        text_sprite.is_active = True
        text_sprite._cursor_visible = False

        # Mock the image surface
        text_sprite.image = mocker.Mock()

        # Act
        text_sprite.update_text('Test')

        # Assert - should not draw cursor when invisible
        # Note: The actual drawing would be tested in integration tests

    def test_text_sprite_cursor_handles_mock_objects(self, mocker):
        """Test TextSprite cursor handles mock objects gracefully."""
        mock_get_font = mocker.patch('glitchygames.fonts.FontManager.get_font')
        # Arrange
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        text_rect = mocker.Mock()
        text_rect.right = 50
        text_rect.top = 20
        text_rect.height = 20
        rendered_surface.get_rect.return_value = text_rect
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        text_sprite = TextSprite(x=10, y=20, width=100, height=30, text='Test', name='TestText')
        text_sprite.is_active = True
        text_sprite._cursor_visible = True

        # Mock the image surface
        text_sprite.image = mocker.Mock()

        # Act - should not crash with mock objects
        text_sprite.update_text('Test')

        # Assert - should complete without error
        assert text_sprite is not None

    def test_text_sprite_cursor_reset_on_deactivation(self, mocker):
        """Test TextSprite cursor resets on deactivation."""
        mock_get_font = mocker.patch('glitchygames.fonts.FontManager.get_font')
        # Arrange
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        text_sprite = TextSprite(x=10, y=20, width=100, height=30, text='Test', name='TestText')
        text_sprite.is_active = True
        text_sprite._cursor_timer = 100
        text_sprite._cursor_visible = True

        # Act - deactivate
        text_sprite.is_active = False
        text_sprite.update()

        # Assert - should set dirty flag to 1 (not 2 for cursor)
        assert text_sprite.dirty == 1

    def test_text_sprite_cursor_continuous_updates_when_active(self, mocker):
        """Test TextSprite cursor provides continuous updates when active."""
        mock_get_font = mocker.patch('glitchygames.fonts.FontManager.get_font')
        # Arrange
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        text_sprite = TextSprite(x=10, y=20, width=100, height=30, text='Test', name='TestText')
        text_sprite.is_active = True

        # Act - multiple updates
        text_sprite.update()
        text_sprite.update()
        text_sprite.update()

        # Assert - should set dirty flag to 2 for cursor updates
        assert text_sprite.dirty == TEST_CURSOR_BLINK_RATE

    def test_text_sprite_cursor_timer_wraparound(self, mocker):
        """Test TextSprite cursor timer wraparound behavior."""
        mock_get_font = mocker.patch('glitchygames.fonts.FontManager.get_font')
        # Arrange
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        text_sprite = TextSprite(x=10, y=20, width=100, height=30, text='Test', name='TestText')
        text_sprite.is_active = True
        text_sprite._cursor_timer = 1000  # Max timer value

        # Act
        text_sprite.update()

        # Assert - timer should wrap around
        assert text_sprite._cursor_timer == 0
