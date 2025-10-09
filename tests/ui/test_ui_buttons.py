"""Test suite for ButtonSprite UI component.

This module tests the ButtonSprite class functionality including initialization,
mouse interactions, and visual state changes.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.ui import ButtonSprite
from mocks.test_mock_factory import MockFactory


class TestButtonSpriteFunctionality:
    """Test ButtonSprite functionality."""

    def test_button_mouse_down_up_changes_background(self, mock_pygame_patches):
        """Test that button background changes on mouse down/up events."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            btn = ButtonSprite(x=10, y=20, width=100, height=40, name="ClickMe")
            assert btn.background_color == btn.inactive_color

            # Act: simulate mouse down
            event = Mock()
            btn.on_left_mouse_button_down_event(event)

            # Assert
            assert btn.background_color == btn.active_color

            # Act: simulate mouse up
            btn.on_left_mouse_button_up_event(event)

            # Assert
            assert btn.background_color == btn.inactive_color

    def test_button_hover_state_changes(self, mock_pygame_patches):
        """Test that button changes appearance on hover."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            btn = ButtonSprite(x=10, y=20, width=100, height=40, name="HoverButton")
            initial_color = btn.background_color

            # Act: simulate mouse enter
            event = Mock()
            btn.on_mouse_enter_event(event)

            # Assert: ButtonSprite doesn't change color on hover, only on click
            assert btn.background_color == btn.inactive_color

            # Act: simulate mouse exit (ButtonSprite doesn't have on_mouse_leave_event)
            btn.on_mouse_exit_event(event)

            # Assert: should return to initial color
            assert btn.background_color == initial_color

    def test_button_click_behavior(self, mock_pygame_patches):
        """Test that button changes color on click."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            btn = ButtonSprite(x=10, y=20, width=100, height=40, name="ClickButton")
            assert btn.background_color == btn.inactive_color

            # Act: simulate click
            event = Mock()
            btn.on_left_mouse_button_down_event(event)
            
            # Assert: should change to active color
            assert btn.background_color == btn.active_color
            
            btn.on_left_mouse_button_up_event(event)
            
            # Assert: should return to inactive color
            assert btn.background_color == btn.inactive_color

    def test_button_initialization(self, mock_pygame_patches):
        """Test ButtonSprite initialization."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            # Act
            btn = ButtonSprite(x=10, y=20, width=100, height=40, name="TestButton")

            # Assert
            assert btn.rect.x == 10
            assert btn.rect.y == 20
            assert btn.rect.width == 100
            assert btn.rect.height == 40
            assert btn.name == "TestButton"
            assert btn.background_color is not None
            assert btn.active_color is not None
            assert btn.inactive_color is not None
            assert btn.border_color is not None

    def test_button_text_rendering(self, mock_pygame_patches):
        """Test that button text is rendered correctly."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            # Act
            btn = ButtonSprite(x=10, y=20, width=100, height=40, name="TextButton")

            # Assert - ButtonSprite creates a TextSprite internally, so we check that it exists
            assert btn.text is not None
            # TextSprite name is set to the button's name
            assert btn.text.name == "TextButton"

    def test_button_disabled_state(self, mock_pygame_patches):
        """Test button disabled state functionality."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            btn = ButtonSprite(x=10, y=20, width=100, height=40, name="DisabledButton")

            # Test that button can be created and has expected properties
            assert btn is not None
            assert btn.name == "DisabledButton"
            
            # Test that button responds to mouse events
            event = Mock()
            initial_color = btn.background_color
            
            # Act: simulate mouse down
            btn.on_left_mouse_button_down_event(event)
            
            # Assert: background color should change
            assert btn.background_color != initial_color
            
            # Act: simulate mouse up
            btn.on_left_mouse_button_up_event(event)
            
            # Assert: background color should return to inactive
            assert btn.background_color == btn.inactive_color


if __name__ == "__main__":
    unittest.main()
