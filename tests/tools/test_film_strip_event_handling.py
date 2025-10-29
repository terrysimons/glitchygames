"""Test film strip event handling with return value pattern."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.tools import bitmappy, film_strip
from tests.mocks.test_mock_factory import MockFactory


class TestFilmStripEventHandling(unittest.TestCase):
    """Test film strip event handling with return value pattern."""

    @classmethod
    def setUpClass(cls):
        """Set up pygame mocks for all tests."""
        cls.patchers = MockFactory.setup_pygame_mocks()
        for patcher in cls.patchers:
            patcher.start()

    @classmethod
    def tearDownClass(cls):
        """Tear down pygame mocks."""
        MockFactory.teardown_pygame_mocks(cls.patchers)

    def setUp(self):
        """Set up test fixtures."""
        # Create a real film strip widget
        self.film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        
        # Create film strip sprite
        self.film_strip_sprite = bitmappy.FilmStripSprite(
            film_strip_widget=self.film_strip_widget,
            x=100, y=100, width=200, height=100
        )

    def test_right_click_inside_bounds_returns_true(self):
        """Test that right-click inside film strip bounds returns True."""
        # Create a mock right-click event inside the film strip
        event = MockFactory.create_pygame_event_mock()
        event.pos = (150, 150)  # Inside the film strip bounds
        event.button = 3  # Right mouse button
        
        # Test that the film strip handles the event
        result = self.film_strip_sprite.on_right_mouse_button_up_event(event)
        
        # Should return True when event is handled
        self.assertTrue(result, "Film strip should return True when handling event inside bounds")

    def test_right_click_outside_bounds_returns_false(self):
        """Test that right-click outside film strip bounds returns False."""
        # Create a mock right-click event outside the film strip
        event = MockFactory.create_pygame_event_mock()
        event.pos = (50, 50)  # Outside the film strip bounds
        event.button = 3  # Right mouse button
        
        # Test that the film strip does not handle the event
        result = self.film_strip_sprite.on_right_mouse_button_up_event(event)
        
        # Should return False when event is not handled
        self.assertFalse(result, "Film strip should return False when not handling event outside bounds")

    def test_right_click_with_frame_selection_returns_true(self):
        """Test that right-click on a frame for color sampling returns True."""
        # Mock the film strip widget to return a frame when clicked
        self.film_strip_widget.get_frame_at_position = Mock(return_value=("animation", 0))
        
        # Create a mock right-click event inside the film strip
        event = MockFactory.create_pygame_event_mock()
        event.pos = (150, 150)  # Inside the film strip bounds
        event.button = 3  # Right mouse button
        
        # Test that the film strip handles the event
        result = self.film_strip_sprite.on_right_mouse_button_up_event(event)
        
        # Should return True when event is handled
        self.assertTrue(result, "Film strip should return True when handling frame selection event")

    def test_right_click_with_onion_skinning_returns_true(self):
        """Test that right-click for onion skinning returns True."""
        # Mock the film strip widget to return None for frame selection but handle onion skinning
        self.film_strip_widget.get_frame_at_position = Mock(return_value=None)
        self.film_strip_widget.handle_click = Mock(return_value=("animation", 0))
        
        # Create a mock right-click event inside the film strip
        event = MockFactory.create_pygame_event_mock()
        event.pos = (150, 150)  # Inside the film strip bounds
        event.button = 3  # Right mouse button
        
        # Test that the film strip handles the event
        result = self.film_strip_sprite.on_right_mouse_button_up_event(event)
        
        # Should return True when event is handled
        self.assertTrue(result, "Film strip should return True when handling onion skinning event")

    def test_right_click_when_invisible_returns_false(self):
        """Test that right-click when sprite is invisible returns False."""
        # Make the sprite invisible
        self.film_strip_sprite.visible = False
        
        # Create a mock right-click event inside the film strip
        event = MockFactory.create_pygame_event_mock()
        event.pos = (150, 150)  # Inside the film strip bounds
        event.button = 3  # Right mouse button
        
        # Test that the film strip does not handle the event
        result = self.film_strip_sprite.on_right_mouse_button_up_event(event)
        
        # Should return False when sprite is invisible
        self.assertFalse(result, "Film strip should return False when sprite is invisible")

    def test_right_click_without_widget_returns_false(self):
        """Test that right-click without widget returns False."""
        # Remove the widget
        self.film_strip_sprite.film_strip_widget = None
        
        # Create a mock right-click event inside the film strip
        event = MockFactory.create_pygame_event_mock()
        event.pos = (150, 150)  # Inside the film strip bounds
        event.button = 3  # Right mouse button
        
        # Test that the film strip does not handle the event
        result = self.film_strip_sprite.on_right_mouse_button_up_event(event)
        
        # Should return False when no widget
        self.assertFalse(result, "Film strip should return False when no widget")

    def test_event_coordinate_conversion(self):
        """Test that screen coordinates are properly converted to film strip coordinates."""
        # Mock the film strip widget methods to capture the converted coordinates
        self.film_strip_widget.get_frame_at_position = Mock(return_value=None)
        self.film_strip_widget.handle_click = Mock(return_value=None)
        
        # Create a mock right-click event
        event = MockFactory.create_pygame_event_mock()
        event.pos = (150, 150)  # Screen coordinates
        event.button = 3  # Right mouse button
        
        # Call the event handler
        self.film_strip_sprite.on_right_mouse_button_up_event(event)
        
        # Verify that handle_click was called with converted coordinates
        # Screen (150, 150) - Film strip (100, 100) = Film strip (50, 50)
        self.film_strip_widget.handle_click.assert_called_once_with((50, 50), is_right_click=True)

    def test_frame_selection_takes_priority_over_onion_skinning(self):
        """Test that frame selection for color sampling takes priority over onion skinning."""
        # Mock the film strip widget to return a frame (color sampling)
        self.film_strip_widget.get_frame_at_position = Mock(return_value=("animation", 0))
        self.film_strip_widget.handle_click = Mock(return_value=None)
        
        # Create a mock right-click event
        event = MockFactory.create_pygame_event_mock()
        event.pos = (150, 150)
        event.button = 3
        
        # Call the event handler
        result = self.film_strip_sprite.on_right_mouse_button_up_event(event)
        
        # Should return True (handled)
        self.assertTrue(result)
        
        # Should call get_frame_at_position for color sampling
        self.film_strip_widget.get_frame_at_position.assert_called_once()
        
        # Should NOT call handle_click for onion skinning
        self.film_strip_widget.handle_click.assert_not_called()


if __name__ == "__main__":
    unittest.main()
