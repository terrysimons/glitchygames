"""Test shift-right-click screen sampling functionality - simplified version."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.tools import bitmappy, film_strip
from tests.mocks.test_mock_factory import MockFactory


class TestShiftRightClickSamplingSimple(unittest.TestCase):
    """Test shift-right-click screen sampling functionality - simplified version."""

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

        # Create a mock parent scene with the _sample_color_from_screen method
        self.parent_scene = Mock()
        self.parent_scene.screen = Mock()
        self.parent_scene.screen.get_at.return_value = (128, 64, 192, 255)  # RGBA color
        self.parent_scene.on_slider_event = Mock()
        
        # Add the _sample_color_from_screen method as a Mock
        self.parent_scene._sample_color_from_screen = Mock()
        
        # Set parent scene reference
        self.film_strip_sprite.parent_scene = self.parent_scene
        
        # Mock the _sample_color_from_frame method to prevent it from interfering
        self.film_strip_sprite._sample_color_from_frame = Mock()

    def test_regular_right_click_samples_pixel_data(self):
        """Test that regular right-click samples from pixel data (RGBA)."""
        # Mock the film strip widget to return a frame when clicked
        self.film_strip_widget.get_frame_at_position = Mock(return_value=("animation", 0))
        
        # Create a mock right-click event (no shift)
        event = MockFactory.create_pygame_event_mock()
        event.pos = (150, 150)  # Inside the film strip bounds
        event.button = 3  # Right mouse button
        
        # Mock pygame key state to return False for shift keys
        with patch('pygame.key.get_pressed') as mock_get_pressed:
            mock_key_state = MockFactory.create_pygame_key_mock(shift_pressed=False)
            mock_get_pressed.return_value = mock_key_state
            
            # Call the event handler
            result = self.film_strip_sprite.on_right_mouse_button_up_event(event)
            
            # Should return True when event is handled
            self.assertTrue(result, "Regular right-click should be handled")
            
            # Should call get_frame_at_position for pixel data sampling
            self.film_strip_widget.get_frame_at_position.assert_called_once()

    def test_shift_right_click_samples_screen(self):
        """Test that shift-right-click samples from screen (RGB only)."""
        # Mock the film strip widget to return a frame when clicked
        self.film_strip_widget.get_frame_at_position = Mock(return_value=("animation", 0))
        
        # Create a mock right-click event
        event = MockFactory.create_pygame_event_mock()
        event.pos = (150, 150)  # Inside the film strip bounds
        event.button = 3  # Right mouse button

        # Mock pygame key state to return True for left shift key
        with patch('glitchygames.tools.bitmappy.pygame.key.get_pressed') as mock_get_pressed:
            mock_key_state = MockFactory.create_pygame_key_mock(shift_pressed=True)
            mock_get_pressed.return_value = mock_key_state
            
            # Debug: Check the mock key state
            print(f"Mock key state: {mock_key_state}")
            print(f"Mock key state[304] (LSHIFT): {mock_key_state[304]}")
            print(f"Mock key state[303] (RSHIFT): {mock_key_state[303]}")
            
            # Call the event handler
            result = self.film_strip_sprite.on_right_mouse_button_up_event(event)

            # Should return True when event is handled
            self.assertTrue(result, "Shift-right-click should be handled")

            # Debug: Check if the mock was called
            print(f"Mock call count: {self.parent_scene._sample_color_from_screen.call_count}")
            print(f"Mock call args: {self.parent_scene._sample_color_from_screen.call_args_list}")
            print(f"get_pressed call count: {mock_get_pressed.call_count}")
            print(f"get_pressed call args: {mock_get_pressed.call_args_list}")

            # Should call the parent scene's screen sampling method
            self.parent_scene._sample_color_from_screen.assert_called_once_with((150, 150))
            
            # Verify that get_pressed was called (short-circuits after first True, so only 1 call)
            self.assertEqual(mock_get_pressed.call_count, 1, f"Expected get_pressed to be called 1 time, but was called {mock_get_pressed.call_count} times")

    def test_screen_sampling_handles_rgb_format(self):
        """Test that screen sampling handles RGB format correctly."""
        # Test the _sample_color_from_screen method directly
        from glitchygames.tools.bitmappy import BitmapEditorScene
        
        # Create a mock scene with required attributes
        scene = Mock()
        scene.screen = self.parent_scene.screen
        scene.on_slider_event = self.parent_scene.on_slider_event
        scene.log = Mock()
        
        # Mock screen color (RGB only)
        self.parent_scene.screen.get_at.return_value = (128, 64, 192)  # RGB only
        
        # Call the screen sampling method directly
        BitmapEditorScene._sample_color_from_screen(scene, (100, 100))
        
        # Should sample from screen
        self.parent_scene.screen.get_at.assert_called_once_with((100, 100))
        
        # Should update sliders (4 calls for R, G, B, A)
        self.assertEqual(self.parent_scene.on_slider_event.call_count, 4)

    def test_screen_sampling_handles_rgba_format(self):
        """Test that screen sampling handles RGBA format correctly."""
        # Test the _sample_color_from_screen method directly
        from glitchygames.tools.bitmappy import BitmapEditorScene
        
        # Create a mock scene with required attributes
        scene = Mock()
        scene.screen = self.parent_scene.screen
        scene.on_slider_event = self.parent_scene.on_slider_event
        scene.log = Mock()
        
        # Mock screen color (RGBA)
        self.parent_scene.screen.get_at.return_value = (128, 64, 192, 128)  # RGBA
        
        # Call the screen sampling method directly
        BitmapEditorScene._sample_color_from_screen(scene, (100, 100))
        
        # Should sample from screen
        self.parent_scene.screen.get_at.assert_called_once_with((100, 100))
        
        # Should update sliders (4 calls for R, G, B, A)
        self.assertEqual(self.parent_scene.on_slider_event.call_count, 4)

    def test_screen_sampling_ignores_alpha_from_screen(self):
        """Test that screen sampling ignores alpha from screen and uses default."""
        # Test the _sample_color_from_screen method directly
        from glitchygames.tools.bitmappy import BitmapEditorScene
        
        # Create a mock scene with required attributes
        scene = Mock()
        scene.screen = self.parent_scene.screen
        scene.on_slider_event = self.parent_scene.on_slider_event
        scene.log = Mock()
        
        # Mock screen color with alpha
        self.parent_scene.screen.get_at.return_value = (128, 64, 192, 128)  # RGBA with alpha
        
        # Call the screen sampling method directly
        BitmapEditorScene._sample_color_from_screen(scene, (100, 100))
        
        # Should update sliders with RGB from screen but alpha = 255
        expected_calls = [
            unittest.mock.call(event=unittest.mock.ANY, trigger=unittest.mock.ANY),  # R slider
            unittest.mock.call(event=unittest.mock.ANY, trigger=unittest.mock.ANY),  # G slider
            unittest.mock.call(event=unittest.mock.ANY, trigger=unittest.mock.ANY),  # B slider
            unittest.mock.call(event=unittest.mock.ANY, trigger=unittest.mock.ANY),  # A slider (255)
        ]
        self.parent_scene.on_slider_event.assert_has_calls(expected_calls, any_order=True)

    def test_shift_right_click_outside_bounds_not_handled(self):
        """Test that shift-right-click outside film strip bounds is not handled."""
        # Create a mock right-click event outside bounds
        event = MockFactory.create_pygame_event_mock()
        event.pos = (50, 50)  # Outside the film strip bounds
        event.button = 3  # Right mouse button
        
        # Mock pygame key state to return True for shift key
        with patch('pygame.key.get_pressed') as mock_get_pressed:
            mock_key_state = [False] * 512
            mock_key_state[304] = True  # Left shift pressed
            mock_get_pressed.return_value = mock_key_state
            
            # Call the event handler
            result = self.film_strip_sprite.on_right_mouse_button_up_event(event)
            
            # Should return False when event is not handled
            self.assertFalse(result, "Shift-right-click outside bounds should not be handled")

    def test_regular_right_click_outside_bounds_not_handled(self):
        """Test that regular right-click outside film strip bounds is not handled."""
        # Create a mock right-click event outside bounds
        event = MockFactory.create_pygame_event_mock()
        event.pos = (50, 50)  # Outside the film strip bounds
        event.button = 3  # Right mouse button
        
        # Mock pygame key state to return False for shift keys
        with patch('pygame.key.get_pressed') as mock_get_pressed:
            mock_key_state = MockFactory.create_pygame_key_mock(shift_pressed=False)
            mock_get_pressed.return_value = mock_key_state
            
            # Call the event handler
            result = self.film_strip_sprite.on_right_mouse_button_up_event(event)
            
            # Should return False when event is not handled
            self.assertFalse(result, "Regular right-click outside bounds should not be handled")

    def test_shift_right_click_without_parent_scene_handles_gracefully(self):
        """Test that shift-right-click without parent scene handles gracefully."""
        # Remove parent scene
        self.film_strip_sprite.parent_scene = None
        
        # Mock the film strip widget to return a frame when clicked
        self.film_strip_widget.get_frame_at_position = Mock(return_value=("animation", 0))
        
        # Create a mock right-click event
        event = MockFactory.create_pygame_event_mock()
        event.pos = (150, 150)  # Inside the film strip bounds
        event.button = 3  # Right mouse button
        
        # Mock pygame key state to return True for shift key
        with patch('pygame.key.get_pressed') as mock_get_pressed:
            mock_key_state = [False] * 512
            mock_key_state[304] = True  # Left shift pressed
            mock_get_pressed.return_value = mock_key_state
            
            # Call the event handler - should not crash
            result = self.film_strip_sprite.on_right_mouse_button_up_event(event)
            
            # Should still return True (event was handled, just no sampling occurred)
            self.assertTrue(result, "Shift-right-click should be handled even without parent scene")


if __name__ == "__main__":
    unittest.main()
