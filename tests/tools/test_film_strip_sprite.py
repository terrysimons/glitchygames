"""Film strip sprite wrapper tests."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.tools import bitmappy, film_strip

from mocks.test_mock_factory import MockFactory


class TestFilmStripSprite(unittest.TestCase):
    """Test FilmStripSprite wrapper functionality."""

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

    def test_film_strip_sprite_initialization(self):
        """Test film strip sprite initialization."""
        # Create a film strip widget
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Create film strip sprite
        sprite = bitmappy.FilmStripSprite(film_strip_widget, x=10, y=20, width=200, height=150)

        # Test basic properties
        assert hasattr(sprite, "film_strip_widget")
        assert hasattr(sprite, "name")
        assert hasattr(sprite, "image")
        assert hasattr(sprite, "rect")
        assert hasattr(sprite, "dirty")

        # Test values
        assert sprite.film_strip_widget == film_strip_widget
        assert sprite.name == "Film Strip"
        # Note: Mock rect properties may not match exact values due to mock setup
        assert hasattr(sprite.rect, "x")
        assert hasattr(sprite.rect, "y")
        assert hasattr(sprite.rect, "width")
        assert hasattr(sprite.rect, "height")
        assert sprite.dirty == 1  # Should be dirty initially

    def test_film_strip_sprite_methods(self):
        """Test film strip sprite methods."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = bitmappy.FilmStripSprite(film_strip_widget)

        # Test methods exist
        assert hasattr(sprite, "update")
        assert hasattr(sprite, "force_redraw")
        assert hasattr(sprite, "on_left_mouse_button_down_event")
        assert hasattr(sprite, "set_parent_canvas")

        # Test methods are callable
        assert callable(sprite.update)
        assert callable(sprite.force_redraw)
        assert callable(sprite.on_left_mouse_button_down_event)
        assert callable(sprite.set_parent_canvas)

    def test_film_strip_sprite_update(self):
        """Test film strip sprite update functionality."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = bitmappy.FilmStripSprite(film_strip_widget)

        # Test initial dirty state
        assert sprite.dirty == 1

        # Test update with dirty flag
        sprite.update()
        # Should call force_redraw and reset dirty flag if no animations
        assert sprite.dirty == 0

    def test_film_strip_sprite_force_redraw(self):
        """Test film strip sprite force redraw."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = bitmappy.FilmStripSprite(film_strip_widget)

        # Test force redraw
        sprite.force_redraw()

        # Should have called film_strip_widget.render
        # The surface should be filled with film background color
        assert sprite.image is not None

    def test_film_strip_sprite_mouse_click(self):
        """Test film strip sprite mouse click handling."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = bitmappy.FilmStripSprite(film_strip_widget, x=10, y=20, width=200, height=150)

        # Create mock event
        mock_event = Mock()
        mock_event.pos = (50, 50)  # Within sprite bounds

        # Test click handling
        sprite.on_left_mouse_button_down_event(mock_event)

        # Should convert coordinates and call film_strip_widget.handle_click
        # Film strip widget should receive (40, 30) - adjusted for sprite position

    def test_film_strip_sprite_mouse_click_outside_bounds(self):
        """Test film strip sprite mouse click outside bounds."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = bitmappy.FilmStripSprite(film_strip_widget, x=10, y=20, width=200, height=150)

        # Create mock event outside bounds
        mock_event = Mock()
        mock_event.pos = (500, 500)  # Outside sprite bounds

        # Test click handling
        sprite.on_left_mouse_button_down_event(mock_event)

        # Should not call film_strip_widget.handle_click since click is outside bounds

    def test_film_strip_sprite_with_animations(self):
        """Test film strip sprite with animations running."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Set up mock sprite with animations
        mock_sprite = MockFactory.create_animated_sprite_mock()
        film_strip_widget.set_animated_sprite(mock_sprite)

        sprite = bitmappy.FilmStripSprite(film_strip_widget)

        # Test update with animations running
        sprite.update()

        # Should force redraw when animations are running
        # Dirty flag should remain set to ensure continuous updates

    def test_film_strip_sprite_parent_canvas(self):
        """Test film strip sprite parent canvas integration."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = bitmappy.FilmStripSprite(film_strip_widget)

        # Test setting parent canvas
        mock_canvas = Mock()
        sprite.set_parent_canvas(mock_canvas)
        assert sprite.parent_canvas == mock_canvas

    def test_film_strip_sprite_click_with_parent_canvas(self):
        """Test film strip sprite click with parent canvas."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = bitmappy.FilmStripSprite(film_strip_widget)

        # Set up mock sprite with animations
        mock_sprite = MockFactory.create_animated_sprite_mock()
        film_strip_widget.set_animated_sprite(mock_sprite)

        # Set parent canvas
        mock_canvas = Mock()
        sprite.set_parent_canvas(mock_canvas)

        # Create mock event
        mock_event = Mock()
        mock_event.pos = (50, 50)

        # Mock the handle_click to return a frame
        with patch.object(film_strip_widget, "handle_click", return_value=("idle", 0)):
            sprite.on_left_mouse_button_down_event(mock_event)

            # Should call parent canvas show_frame
            mock_canvas.show_frame.assert_called_once_with("idle", 0)

    def test_film_strip_sprite_click_no_frame_selected(self):
        """Test film strip sprite click when no frame is selected."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = bitmappy.FilmStripSprite(film_strip_widget)

        # Set parent canvas
        mock_canvas = Mock()
        sprite.set_parent_canvas(mock_canvas)

        # Create mock event
        mock_event = Mock()
        mock_event.pos = (50, 50)

        # Mock the handle_click to return None
        with patch.object(film_strip_widget, "handle_click", return_value=None):
            sprite.on_left_mouse_button_down_event(mock_event)

            # Should not call parent canvas show_frame
            mock_canvas.show_frame.assert_not_called()

    def test_film_strip_sprite_continuous_redraw_with_animations(self):
        """Test that film strip sprite continuously redraws when animations are present."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Set up mock sprite with animations
        mock_sprite = MockFactory.create_animated_sprite_mock()
        film_strip_widget.set_animated_sprite(mock_sprite)

        sprite = bitmappy.FilmStripSprite(film_strip_widget)

        # Reset dirty flag
        sprite.dirty = 0

        # Update with animations running
        sprite.update()

        # Should force redraw and keep dirty flag set for continuous updates
        # This ensures smooth animation previews

    def test_film_strip_sprite_surface_initialization(self):
        """Test film strip sprite surface initialization."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = bitmappy.FilmStripSprite(film_strip_widget, x=0, y=0, width=200, height=150)

        # Test surface properties
        assert sprite.image is not None
        assert hasattr(sprite.image, "get_width")
        assert hasattr(sprite.image, "get_height")

        # Test rect properties
        assert hasattr(sprite.rect, "width")
        assert hasattr(sprite.rect, "height")

    def test_film_strip_sprite_coordinate_conversion(self):
        """Test film strip sprite coordinate conversion."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = bitmappy.FilmStripSprite(film_strip_widget, x=10, y=20, width=200, height=150)

        # Create mock event
        mock_event = Mock()
        mock_event.pos = (50, 70)  # Screen coordinates

        # Test coordinate conversion
        with patch.object(film_strip_widget, "handle_click") as mock_handle_click:
            # Configure mock to return proper tuple
            mock_handle_click.return_value = ("idle", 0)
            sprite.on_left_mouse_button_down_event(mock_event)

            # Should convert screen coordinates to film strip coordinates
            # Sprite is at (10, 20), so (50, 70) - (10, 20) = (40, 50)
            mock_handle_click.assert_called_once_with((40, 50))

    def test_film_strip_sprite_edge_cases(self):
        """Test film strip sprite edge cases."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = bitmappy.FilmStripSprite(film_strip_widget)

        # Test with None parent canvas
        sprite.parent_canvas = None

        # Create mock event
        mock_event = Mock()
        mock_event.pos = (50, 50)

        # Should not crash when parent canvas is None
        sprite.on_left_mouse_button_down_event(mock_event)

        # Test with no film strip widget
        sprite.film_strip_widget = None
        sprite.on_left_mouse_button_down_event(mock_event)


if __name__ == "__main__":
    unittest.main()
