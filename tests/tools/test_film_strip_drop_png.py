#!/usr/bin/env python3
"""Test film strip PNG drop functionality using centralized mocks."""

import tempfile
from pathlib import Path

import pytest
from glitchygames.tools.bitmappy import FilmStripSprite
from glitchygames.tools.film_strip import FilmStripWidget

from tests.mocks.test_mock_factory import MockFactory


class TestFilmStripDropPNG:
    """Test film strip PNG drop functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        self._mocker = mocker
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_drop_png_on_existing_frame(self):
        """Test dropping a PNG on an existing frame replaces its contents."""
        # Create a mock film strip widget
        film_strip_widget = self._mocker.Mock(spec=FilmStripWidget)
        film_strip_widget.current_animation = "test_animation"
        film_strip_widget.animated_sprite = self._mocker.Mock()
        film_strip_widget.animated_sprite._animations = {
            "test_animation": [self._mocker.Mock(), self._mocker.Mock()]
        }
        film_strip_widget.get_frame_at_position = self._mocker.Mock(
            return_value=("test_animation", 0)
        )
        film_strip_widget.mark_dirty = self._mocker.Mock()

        # Create film strip sprite
        film_strip_sprite = FilmStripSprite(film_strip_widget, x=0, y=0, width=100, height=100)
        film_strip_sprite.rect = self._mocker.Mock()
        film_strip_sprite.rect.collidepoint = self._mocker.Mock(return_value=True)
        film_strip_sprite.rect.x = 0
        film_strip_sprite.rect.y = 0

        # Mock _convert_image_to_sprite_frame to avoid pygame C-level surface issues
        mock_frame = self._mocker.Mock()
        self._mocker.patch.object(
            film_strip_sprite, "_convert_image_to_sprite_frame", return_value=mock_frame
        )

        # Mock pygame.mouse.get_pos since on_drop_file_event uses it instead of event.pos
        self._mocker.patch("pygame.mouse.get_pos", return_value=(50, 50))

        # Create a test PNG file path (no need to create real image since conversion is mocked)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as test_file:
            Path(test_file.name).write_bytes(b"fake png data")

            # Create mock drop event
            class MockEvent:
                def __init__(self, file_path, pos):
                    self.file = file_path
                    self.pos = pos

            event = MockEvent(test_file.name, (50, 50))  # Drop in middle of film strip

            # Test the drop
            result = film_strip_sprite.on_drop_file_event(event)

            # Verify the drop was handled
            assert result is True
            assert film_strip_widget.mark_dirty.called

            # Clean up
            Path(test_file.name).unlink()

    def test_drop_png_on_strip_area(self):
        """Test dropping a PNG on the film strip (not on a frame) inserts new frame."""
        # Create a mock film strip widget
        film_strip_widget = self._mocker.Mock(spec=FilmStripWidget)
        film_strip_widget.current_animation = "test_animation"
        film_strip_widget.animated_sprite = self._mocker.Mock()
        film_strip_widget.animated_sprite._animations = {"test_animation": [self._mocker.Mock()]}
        film_strip_widget.get_frame_at_position = self._mocker.Mock(
            return_value=None
        )  # No frame clicked
        film_strip_widget.mark_dirty = self._mocker.Mock()
        film_strip_widget.set_current_frame = self._mocker.Mock()

        # Mock the add_frame method
        film_strip_widget.animated_sprite.add_frame = self._mocker.Mock()

        # Create film strip sprite
        film_strip_sprite = FilmStripSprite(film_strip_widget, x=0, y=0, width=100, height=100)
        film_strip_sprite.rect = self._mocker.Mock()
        film_strip_sprite.rect.collidepoint = self._mocker.Mock(return_value=True)
        film_strip_sprite.rect.x = 0
        film_strip_sprite.rect.y = 0

        # Mock _convert_image_to_sprite_frame to avoid pygame C-level surface issues
        mock_frame = self._mocker.Mock()
        self._mocker.patch.object(
            film_strip_sprite, "_convert_image_to_sprite_frame", return_value=mock_frame
        )

        # Mock pygame.mouse.get_pos since on_drop_file_event uses it instead of event.pos
        self._mocker.patch("pygame.mouse.get_pos", return_value=(50, 50))

        # Create a test PNG file path (no need to create real image since conversion is mocked)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as test_file:
            Path(test_file.name).write_bytes(b"fake png data")

            # Create mock drop event
            class MockEvent:
                def __init__(self, file_path, pos):
                    self.file = file_path
                    self.pos = pos

            event = MockEvent(test_file.name, (50, 50))  # Drop in middle of film strip

            # Test the drop
            result = film_strip_sprite.on_drop_file_event(event)

            # Verify the drop was handled
            assert result is True
            assert film_strip_widget.animated_sprite.add_frame.called
            assert film_strip_widget.mark_dirty.called

            # Clean up
            Path(test_file.name).unlink()

    def test_drop_unsupported_file_type(self):
        """Test dropping an unsupported file type returns False."""
        # Create a mock film strip widget
        film_strip_widget = self._mocker.Mock(spec=FilmStripWidget)

        # Create film strip sprite
        film_strip_sprite = FilmStripSprite(film_strip_widget, x=0, y=0, width=100, height=100)
        film_strip_sprite.rect = self._mocker.Mock()
        film_strip_sprite.rect.collidepoint = self._mocker.Mock(return_value=True)
        film_strip_sprite.rect.x = 0
        film_strip_sprite.rect.y = 0

        # Create mock drop event with unsupported file
        class MockEvent:
            def __init__(self, file_path, pos):
                self.file = file_path
                self.pos = pos

        event = MockEvent("test.txt", (50, 50))  # Text file, not image

        # Test the drop
        result = film_strip_sprite.on_drop_file_event(event)

        # Verify the drop was rejected
        assert result is False

    def test_drop_outside_film_strip_bounds(self):
        """Test dropping outside film strip bounds returns False."""
        # Create a mock film strip widget
        film_strip_widget = self._mocker.Mock(spec=FilmStripWidget)

        # Create film strip sprite
        film_strip_sprite = FilmStripSprite(film_strip_widget, x=0, y=0, width=100, height=100)
        film_strip_sprite.rect = self._mocker.Mock()
        film_strip_sprite.rect.collidepoint = self._mocker.Mock(
            return_value=False
        )  # Outside bounds

        # Create mock drop event
        class MockEvent:
            def __init__(self, file_path, pos):
                self.file = file_path
                self.pos = pos

        event = MockEvent("test.png", (200, 200))  # Outside film strip

        # Test the drop
        result = film_strip_sprite.on_drop_file_event(event)

        # Verify the drop was rejected
        assert result is False

    def test_image_conversion_to_sprite_frame(self):
        """Test that image conversion creates a proper SpriteFrame."""
        # Create a mock film strip widget
        film_strip_widget = self._mocker.Mock(spec=FilmStripWidget)
        film_strip_widget.current_animation = "test_animation"
        film_strip_widget.animated_sprite = self._mocker.Mock()
        film_strip_widget.animated_sprite._animations = {"test_animation": [self._mocker.Mock()]}
        film_strip_widget.get_frame_at_position = self._mocker.Mock(return_value=None)
        film_strip_widget.mark_dirty = self._mocker.Mock()
        film_strip_widget.set_current_frame = self._mocker.Mock()
        film_strip_widget.animated_sprite.add_frame = self._mocker.Mock()

        # Create film strip sprite
        film_strip_sprite = FilmStripSprite(film_strip_widget, x=0, y=0, width=100, height=100)
        film_strip_sprite.rect = self._mocker.Mock()
        film_strip_sprite.rect.collidepoint = self._mocker.Mock(return_value=True)
        film_strip_sprite.rect.x = 0
        film_strip_sprite.rect.y = 0

        # Mock _convert_image_to_sprite_frame to avoid pygame C-level surface issues
        mock_frame = self._mocker.Mock()
        self._mocker.patch.object(
            film_strip_sprite, "_convert_image_to_sprite_frame", return_value=mock_frame
        )

        # Mock pygame.mouse.get_pos since on_drop_file_event uses it instead of event.pos
        self._mocker.patch("pygame.mouse.get_pos", return_value=(50, 50))

        # Create a test PNG file path (no need to create real image since conversion is mocked)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as test_file:
            Path(test_file.name).write_bytes(b"fake png data")

            # Create mock drop event
            class MockEvent:
                def __init__(self, file_path, pos):
                    self.file = file_path
                    self.pos = pos

            event = MockEvent(test_file.name, (50, 50))

            # Test the drop
            result = film_strip_sprite.on_drop_file_event(event)

            # Verify the drop was handled and frame was added
            assert result is True
            assert film_strip_widget.animated_sprite.add_frame.called

            # Clean up
            Path(test_file.name).unlink()
