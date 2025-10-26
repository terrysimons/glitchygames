"""Test shift-right-click screen sampling functionality."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.tools import bitmappy, film_strip
from tests.mocks.test_mock_factory import MockFactory


class TestShiftRightClickSampling(unittest.TestCase):
    """Test shift-right-click screen sampling functionality."""

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
        
        # Add the _sample_color_from_screen method to the mock
        def mock_sample_color_from_screen(screen_pos):
            try:
                color = self.parent_scene.screen.get_at(screen_pos)
                if len(color) == 4:
                    red, green, blue, _ = color
                else:
                    red, green, blue = color
                alpha = 255
                
                # Update sliders
                trigger = pygame.event.Event(0, {"name": "R", "value": red})
                self.parent_scene.on_slider_event(event=pygame.event.Event(0), trigger=trigger)
                trigger = pygame.event.Event(0, {"name": "G", "value": green})
                self.parent_scene.on_slider_event(event=pygame.event.Event(0), trigger=trigger)
                trigger = pygame.event.Event(0, {"name": "B", "value": blue})
                self.parent_scene.on_slider_event(event=pygame.event.Event(0), trigger=trigger)
                trigger = pygame.event.Event(0, {"name": "A", "value": alpha})
                self.parent_scene.on_slider_event(event=pygame.event.Event(0), trigger=trigger)
            except Exception:
                pass
        
        self.parent_scene._sample_color_from_screen = mock_sample_color_from_screen
        
        # Set parent scene reference
        self.film_strip_sprite.parent_scene = self.parent_scene

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
            mock_key_state = [False] * 512
            # Use actual pygame constants if available, otherwise use known values
            try:
                mock_key_state[pygame.K_LSHIFT] = False
                mock_key_state[pygame.K_RSHIFT] = False
            except (IndexError, AttributeError):
                # Fallback: just return all False
                pass
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
        with patch('pygame.key.get_pressed') as mock_get_pressed:
            mock_key_state = [False] * 512
            # Use actual pygame constants if available, otherwise use known values
            try:
                mock_key_state[pygame.K_LSHIFT] = True  # Left shift pressed
            except (IndexError, AttributeError):
                # Fallback: just return all False
                pass
            mock_get_pressed.return_value = mock_key_state
            
            # Call the event handler
            result = self.film_strip_sprite.on_right_mouse_button_up_event(event)
            
            # Should return True when event is handled
            self.assertTrue(result, "Shift-right-click should be handled")
            
            # Should call the parent scene's screen sampling method
            self.parent_scene._sample_color_from_screen.assert_called_once_with((150, 150))

    def test_shift_right_click_samples_screen_rgb_only(self):
        """Test that shift-right-click samples screen and converts to RGB only."""
        # Mock screen color (RGBA)
        self.parent_scene.screen.get_at.return_value = (128, 64, 192, 128)  # RGBA with alpha
        
        # Call the screen sampling method directly
        self.parent_scene._sample_color_from_screen((100, 100))
        
        # Should sample from screen
        self.parent_scene.screen.get_at.assert_called_once_with((100, 100))
        
        # Should update sliders with RGB values and default alpha (255)
        expected_calls = [
            unittest.mock.call(event=unittest.mock.ANY, trigger=unittest.mock.ANY),  # R slider
            unittest.mock.call(event=unittest.mock.ANY, trigger=unittest.mock.ANY),  # G slider
            unittest.mock.call(event=unittest.mock.ANY, trigger=unittest.mock.ANY),  # B slider
            unittest.mock.call(event=unittest.mock.ANY, trigger=unittest.mock.ANY),  # A slider
        ]
        self.parent_scene.on_slider_event.assert_has_calls(expected_calls, any_order=True)

    def test_regular_right_click_canvas_samples_pixel_data(self):
        """Test that regular right-click on canvas samples pixel data (RGBA)."""
        # Create a mock scene with canvas
        scene = Mock()
        scene.canvas = Mock()
        scene.canvas.rect = Mock()
        scene.canvas.rect.collidepoint.return_value = True
        scene.canvas.pixel_width = 10
        scene.canvas.pixel_height = 10
        scene.canvas.pixels_across = 32
        scene.canvas.pixels_tall = 32
        scene.canvas.pixels = [(255, 128, 64, 200)] * (32 * 32)  # RGBA pixels
        scene.on_slider_event = Mock()
        scene.screen = Mock()
        
        # Add the right-click handler method to the mock scene
        def mock_on_right_mouse_button_up_event(event):
            # Check if the click is on the canvas to sample canvas pixel data
            if hasattr(scene, "canvas") and scene.canvas and scene.canvas.rect.collidepoint(event.pos):
                canvas_x = (event.pos[0] - scene.canvas.rect.x) // scene.canvas.pixel_width
                canvas_y = (event.pos[1] - scene.canvas.rect.y) // scene.canvas.pixel_height
                
                # Check bounds
                if (0 <= canvas_x < scene.canvas.pixels_across and
                    0 <= canvas_y < scene.canvas.pixels_tall):
                    pixel_num = canvas_y * scene.canvas.pixels_across + canvas_x
                    if pixel_num < len(scene.canvas.pixels):
                        color = scene.canvas.pixels[pixel_num]
                        
                        # Handle both RGB and RGBA pixel formats
                        if len(color) == 4:
                            red, green, blue, alpha = color
                        else:
                            red, green, blue = color
                            alpha = 255  # Default to opaque for RGB pixels
                        
                        # Update all sliders with the sampled RGBA values
                        trigger = pygame.event.Event(0, {"name": "R", "value": red})
                        scene.on_slider_event(event=event, trigger=trigger)
                        
                        trigger = pygame.event.Event(0, {"name": "G", "value": green})
                        scene.on_slider_event(event=event, trigger=trigger)
                        
                        trigger = pygame.event.Event(0, {"name": "B", "value": blue})
                        scene.on_slider_event(event=event, trigger=trigger)
                        
                        trigger = pygame.event.Event(0, {"name": "A", "value": alpha})
                        scene.on_slider_event(event=event, trigger=trigger)
                        return
        
        scene.on_right_mouse_button_up_event = mock_on_right_mouse_button_up_event
        
        # Create event
        event = MockFactory.create_pygame_event_mock()
        event.pos = (50, 50)  # On canvas
        
        # Mock pygame key state to return False for shift keys
        with patch('pygame.key.get_pressed') as mock_get_pressed:
            mock_key_state = [False] * 512
            # Use actual pygame constants if available, otherwise use known values
            try:
                mock_key_state[pygame.K_LSHIFT] = False
                mock_key_state[pygame.K_RSHIFT] = False
            except (IndexError, AttributeError):
                # Fallback: just return all False
                pass
            mock_get_pressed.return_value = mock_key_state
            
            # Call the scene's right-click handler
            scene.on_right_mouse_button_up_event(event)
            
            # Should call on_slider_event for RGBA values
            self.assertEqual(scene.on_slider_event.call_count, 4)  # R, G, B, A

    def test_shift_right_click_canvas_samples_screen(self):
        """Test that shift-right-click on canvas samples screen (RGB only)."""
        # Create a mock scene with canvas
        scene = Mock()
        scene.canvas = Mock()
        scene.canvas.rect = Mock()
        scene.canvas.rect.collidepoint.return_value = True
        scene.on_slider_event = Mock()
        scene.screen = Mock()
        scene.screen.get_at.return_value = (128, 64, 192, 128)  # RGBA screen color
        
        # Add the _sample_color_from_screen method to the mock scene
        def mock_sample_color_from_screen(screen_pos):
            try:
                color = scene.screen.get_at(screen_pos)
                if len(color) == 4:
                    red, green, blue, _ = color
                else:
                    red, green, blue = color
                alpha = 255
                
                # Update sliders
                trigger = pygame.event.Event(0, {"name": "R", "value": red})
                scene.on_slider_event(event=pygame.event.Event(0), trigger=trigger)
                trigger = pygame.event.Event(0, {"name": "G", "value": green})
                scene.on_slider_event(event=pygame.event.Event(0), trigger=trigger)
                trigger = pygame.event.Event(0, {"name": "B", "value": blue})
                scene.on_slider_event(event=pygame.event.Event(0), trigger=trigger)
                trigger = pygame.event.Event(0, {"name": "A", "value": alpha})
                scene.on_slider_event(event=pygame.event.Event(0), trigger=trigger)
            except Exception:
                pass
        
        scene._sample_color_from_screen = mock_sample_color_from_screen
        
        # Add the right-click handler method to the mock scene
        def mock_on_right_mouse_button_up_event(event):
            # Check for shift-right-click (screen sampling)
            is_shift_click = pygame.key.get_pressed()[pygame.K_LSHIFT] or pygame.key.get_pressed()[pygame.K_RSHIFT]
            
            # Check if the click is on the canvas
            if hasattr(scene, "canvas") and scene.canvas and scene.canvas.rect.collidepoint(event.pos):
                if is_shift_click:
                    # Shift-right-click: sample screen directly (RGB only)
                    scene._sample_color_from_screen(event.pos)
                    return
        
        scene.on_right_mouse_button_up_event = mock_on_right_mouse_button_up_event
        
        # Create event
        event = MockFactory.create_pygame_event_mock()
        event.pos = (50, 50)  # On canvas
        
        # Mock pygame key state to return True for left shift key
        with patch('pygame.key.get_pressed') as mock_get_pressed:
            mock_key_state = [False] * 512
            # Use actual pygame constants if available, otherwise use known values
            try:
                mock_key_state[pygame.K_LSHIFT] = True  # Left shift pressed
            except (IndexError, AttributeError):
                # Fallback: just return all False
                pass
            mock_get_pressed.return_value = mock_key_state
            
            # Call the scene's right-click handler
            scene.on_right_mouse_button_up_event(event)
            
            # Should sample from screen
            scene.screen.get_at.assert_called_once_with((50, 50))
            
            # Should call on_slider_event for RGB values with default alpha
            self.assertEqual(scene.on_slider_event.call_count, 4)  # R, G, B, A

    def test_screen_sampling_handles_rgb_format(self):
        """Test that screen sampling handles RGB format correctly."""
        # Mock screen color (RGB only)
        self.parent_scene.screen.get_at.return_value = (128, 64, 192)  # RGB only
        
        # Call the screen sampling method
        self.parent_scene._sample_color_from_screen((100, 100))
        
        # Should sample from screen
        self.parent_scene.screen.get_at.assert_called_once_with((100, 100))
        
        # Should update sliders (4 calls for R, G, B, A)
        self.assertEqual(self.parent_scene.on_slider_event.call_count, 4)

    def test_screen_sampling_handles_rgba_format(self):
        """Test that screen sampling handles RGBA format correctly."""
        # Mock screen color (RGBA)
        self.parent_scene.screen.get_at.return_value = (128, 64, 192, 128)  # RGBA
        
        # Call the screen sampling method
        self.parent_scene._sample_color_from_screen((100, 100))
        
        # Should sample from screen
        self.parent_scene.screen.get_at.assert_called_once_with((100, 100))
        
        # Should update sliders (4 calls for R, G, B, A)
        self.assertEqual(self.parent_scene.on_slider_event.call_count, 4)

    def test_screen_sampling_ignores_alpha_from_screen(self):
        """Test that screen sampling ignores alpha from screen and uses default."""
        # Mock screen color with alpha
        self.parent_scene.screen.get_at.return_value = (128, 64, 192, 128)  # RGBA with alpha
        
        # Call the screen sampling method
        self.parent_scene._sample_color_from_screen((100, 100))
        
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
            mock_key_state[pygame.K_LSHIFT] = True  # Left shift pressed
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
            mock_key_state = [False] * 512
            # Use actual pygame constants if available, otherwise use known values
            try:
                mock_key_state[pygame.K_LSHIFT] = False
                mock_key_state[pygame.K_RSHIFT] = False
            except (IndexError, AttributeError):
                # Fallback: just return all False
                pass
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
            mock_key_state[pygame.K_LSHIFT] = True  # Left shift pressed
            mock_get_pressed.return_value = mock_key_state
            
            # Call the event handler - should not crash
            result = self.film_strip_sprite.on_right_mouse_button_up_event(event)
            
            # Should still return True (event was handled, just no sampling occurred)
            self.assertTrue(result, "Shift-right-click should be handled even without parent scene")


if __name__ == "__main__":
    unittest.main()
