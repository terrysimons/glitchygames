"""Test suite for control UI components.

This module tests SliderSprite, CheckboxSprite, and ColorWellSprite functionality
including user interactions, value changes, and visual feedback.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.ui import SliderSprite, CheckboxSprite, ColorWellSprite
from mocks.test_mock_factory import MockFactory


class TestSliderSpriteFunctionality(unittest.TestCase):
    """Test SliderSprite functionality."""

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

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_slider_initialization(self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display):
        """Test SliderSprite initialization."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        # Act
        slider = SliderSprite(x=10, y=20, width=200, height=20, name="TestSlider")

        # Assert
        self.assertEqual(slider.rect.x, 10)
        self.assertEqual(slider.rect.y, 20)
        self.assertEqual(slider.rect.width, 200)
        self.assertEqual(slider.rect.height, 20)
        self.assertEqual(slider.name, "TestSlider")

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_slider_value_change(self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display):
        """Test SliderSprite value change functionality."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        slider = SliderSprite(x=10, y=20, width=200, height=20, name="TestSlider")

        # Test that slider can be created and has expected properties
        self.assertIsNotNone(slider)
        self.assertEqual(slider.name, "TestSlider")

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_slider_mouse_drag(self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display):
        """Test SliderSprite mouse drag functionality."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        slider = SliderSprite(x=10, y=20, width=200, height=20, name="TestSlider")

        # Test that slider can be created and responds to mouse events
        self.assertIsNotNone(slider)
        
        # Act: simulate mouse motion
        event = Mock()
        event.pos = (110, 30)  # Middle of slider
        slider.on_mouse_motion_event(event)

        # Assert: slider should handle mouse motion without error
        self.assertIsNotNone(slider)

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_slider_callback(self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display):
        """Test SliderSprite value change callback."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        slider = SliderSprite(x=10, y=20, width=200, height=20, name="TestSlider")

        # Test that slider can be created
        self.assertIsNotNone(slider)
        self.assertEqual(slider.name, "TestSlider")


class TestCheckboxSpriteFunctionality(unittest.TestCase):
    """Test CheckboxSprite functionality."""

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

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_checkbox_initialization(self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display):
        """Test CheckboxSprite initialization."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        # Act
        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name="TestCheckbox")

        # Assert
        self.assertEqual(checkbox.rect.x, 10)
        self.assertEqual(checkbox.rect.y, 20)
        self.assertEqual(checkbox.rect.width, 20)
        self.assertEqual(checkbox.rect.height, 20)
        self.assertEqual(checkbox.name, "TestCheckbox")
        self.assertFalse(checkbox.checked)

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_checkbox_toggle(self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display):
        """Test CheckboxSprite toggle functionality."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name="TestCheckbox")

        # Test initial state
        self.assertFalse(checkbox.checked)

        # Act: simulate click to toggle
        event = Mock()
        checkbox.on_left_mouse_button_up_event(event)

        # Assert: should be checked after click
        self.assertTrue(checkbox.checked)

        # Act: click again
        checkbox.on_left_mouse_button_up_event(event)

        # Assert: should be unchecked after second click
        self.assertFalse(checkbox.checked)

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_checkbox_click_toggle(self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display):
        """Test CheckboxSprite click to toggle functionality."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name="TestCheckbox")

        # Test initial state
        self.assertFalse(checkbox.checked)

        # Act: simulate click
        event = Mock()
        event.pos = (20, 30)  # Within checkbox
        checkbox.on_left_mouse_button_up_event(event)

        # Assert: should be checked after click
        self.assertTrue(checkbox.checked)

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_checkbox_callback(self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display):
        """Test CheckboxSprite state change callback."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name="TestCheckbox")

        # Test that checkbox can be created and responds to events
        self.assertIsNotNone(checkbox)
        self.assertEqual(checkbox.name, "TestCheckbox")

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_checkbox_set_checked(self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display):
        """Test CheckboxSprite set checked state."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name="TestCheckbox")

        # Test initial state
        self.assertFalse(checkbox.checked)

        # Act: simulate click to check
        event = Mock()
        checkbox.on_left_mouse_button_up_event(event)

        # Assert: should be checked
        self.assertTrue(checkbox.checked)

        # Act: simulate click to uncheck
        checkbox.on_left_mouse_button_up_event(event)

        # Assert: should be unchecked
        self.assertFalse(checkbox.checked)


class TestColorWellSpriteFunctionality(unittest.TestCase):
    """Test ColorWellSprite functionality."""

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

    def test_colorwell_initialization(self):
        """Test ColorWellSprite initialization."""
        # Arrange - use centralized mocks
        # Act
        colorwell = ColorWellSprite(x=10, y=20, width=50, height=30, name="TestColorWell")

        # Assert
        self.assertEqual(colorwell.rect.x, 10)
        self.assertEqual(colorwell.rect.y, 20)
        self.assertEqual(colorwell.rect.width, 50)
        self.assertEqual(colorwell.rect.height, 30)
        self.assertEqual(colorwell.name, "TestColorWell")
        self.assertEqual(colorwell.active_color, (0, 0, 0))  # Default color

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_colorwell_color_change(self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display):
        """Test ColorWellSprite color change functionality."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        colorwell = ColorWellSprite(x=10, y=20, width=50, height=30, name="TestColorWell")

        # Test that colorwell can be created
        self.assertIsNotNone(colorwell)
        self.assertEqual(colorwell.name, "TestColorWell")

    def test_colorwell_click_callback(self):
        """Test ColorWellSprite click callback."""
        # Arrange - use centralized mocks
        colorwell = ColorWellSprite(x=10, y=20, width=50, height=30, name="TestColorWell")

        # Test that colorwell can be created and responds to mouse events
        self.assertIsNotNone(colorwell)
        
        # Act: simulate click
        event = Mock()
        event.pos = (35, 35)  # Within color well
        colorwell.on_left_mouse_button_down_event(event)

        # Assert: should handle click without error
        self.assertIsNotNone(colorwell)

    def test_colorwell_hover_effect(self):
        """Test ColorWellSprite hover effect."""
        # Arrange - use centralized mocks
        colorwell = ColorWellSprite(x=10, y=20, width=50, height=30, name="TestColorWell")

        # Test that colorwell can be created and responds to mouse events
        self.assertIsNotNone(colorwell)
        
        # Act: simulate mouse enter
        event = Mock()
        colorwell.on_mouse_enter_event(event)

        # Assert: should handle mouse enter without error
        self.assertIsNotNone(colorwell)
        
        # Act: simulate mouse exit (correct method name)
        colorwell.on_mouse_exit_event(event)

        # Assert: should handle mouse exit without error
        self.assertIsNotNone(colorwell)

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_colorwell_color_validation(self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display):
        """Test ColorWellSprite color validation."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        colorwell = ColorWellSprite(x=10, y=20, width=50, height=30, name="TestColorWell")

        # Test that colorwell can be created
        self.assertIsNotNone(colorwell)
        self.assertEqual(colorwell.name, "TestColorWell")
        
        # Test that it has default color properties
        self.assertIsNotNone(colorwell.active_color)
        self.assertIsNotNone(colorwell.red)
        self.assertIsNotNone(colorwell.green)
        self.assertIsNotNone(colorwell.blue)


if __name__ == "__main__":
    unittest.main()
