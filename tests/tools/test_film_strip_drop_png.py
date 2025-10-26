#!/usr/bin/env python3
"""Test film strip PNG drop functionality using centralized mocks."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glitchygames.tools.bitmappy import FilmStripSprite
from glitchygames.tools.film_strip import FilmStripWidget
from tests.mocks.test_mock_factory import MockFactory


class TestFilmStripDropPNG:
    """Test film strip PNG drop functionality."""

    def setup_method(self):
        """Set up test fixtures using centralized mocks."""
        # Use centralized mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all the patchers
        for patcher in self.patchers:
            patcher.start()

    def teardown_method(self):
        """Clean up after tests."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_drop_png_on_existing_frame(self):
        """Test dropping a PNG on an existing frame replaces its contents."""
        # Create a mock film strip widget
        film_strip_widget = Mock(spec=FilmStripWidget)
        film_strip_widget.current_animation = "test_animation"
        film_strip_widget.animated_sprite = Mock()
        film_strip_widget.animated_sprite._animations = {
            "test_animation": [Mock(), Mock()]
        }
        film_strip_widget.get_frame_at_position = Mock(return_value=("test_animation", 0))
        film_strip_widget.mark_dirty = Mock()

        # Create film strip sprite
        film_strip_sprite = FilmStripSprite(film_strip_widget, x=0, y=0, width=100, height=100)
        film_strip_sprite.rect = Mock()
        film_strip_sprite.rect.collidepoint = Mock(return_value=True)
        film_strip_sprite.rect.x = 0
        film_strip_sprite.rect.y = 0

        # Create a test PNG file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as test_file:
            # Create a simple 32x32 test image
            import pygame
            test_surface = pygame.Surface((32, 32))
            test_surface.fill((255, 0, 0))  # Red
            pygame.image.save(test_surface, test_file.name)

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
        film_strip_widget = Mock(spec=FilmStripWidget)
        film_strip_widget.current_animation = "test_animation"
        film_strip_widget.animated_sprite = Mock()
        film_strip_widget.animated_sprite._animations = {
            "test_animation": [Mock()]
        }
        film_strip_widget.get_frame_at_position = Mock(return_value=None)  # No frame clicked
        film_strip_widget.mark_dirty = Mock()
        film_strip_widget.set_current_frame = Mock()

        # Mock the add_frame method
        film_strip_widget.animated_sprite.add_frame = Mock()

        # Create film strip sprite
        film_strip_sprite = FilmStripSprite(film_strip_widget, x=0, y=0, width=100, height=100)
        film_strip_sprite.rect = Mock()
        film_strip_sprite.rect.collidepoint = Mock(return_value=True)
        film_strip_sprite.rect.x = 0
        film_strip_sprite.rect.y = 0

        # Create a test PNG file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as test_file:
            # Create a simple 32x32 test image
            import pygame
            test_surface = pygame.Surface((32, 32))
            test_surface.fill((0, 255, 0))  # Green
            pygame.image.save(test_surface, test_file.name)

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
        film_strip_widget = Mock(spec=FilmStripWidget)

        # Create film strip sprite
        film_strip_sprite = FilmStripSprite(film_strip_widget, x=0, y=0, width=100, height=100)
        film_strip_sprite.rect = Mock()
        film_strip_sprite.rect.collidepoint = Mock(return_value=True)
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
        film_strip_widget = Mock(spec=FilmStripWidget)

        # Create film strip sprite
        film_strip_sprite = FilmStripSprite(film_strip_widget, x=0, y=0, width=100, height=100)
        film_strip_sprite.rect = Mock()
        film_strip_sprite.rect.collidepoint = Mock(return_value=False)  # Outside bounds

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
        film_strip_widget = Mock(spec=FilmStripWidget)
        film_strip_widget.current_animation = "test_animation"
        film_strip_widget.animated_sprite = Mock()
        film_strip_widget.animated_sprite._animations = {
            "test_animation": [Mock()]
        }
        film_strip_widget.get_frame_at_position = Mock(return_value=None)
        film_strip_widget.mark_dirty = Mock()
        film_strip_widget.set_current_frame = Mock()
        film_strip_widget.animated_sprite.add_frame = Mock()

        # Create film strip sprite
        film_strip_sprite = FilmStripSprite(film_strip_widget, x=0, y=0, width=100, height=100)
        film_strip_sprite.rect = Mock()
        film_strip_sprite.rect.collidepoint = Mock(return_value=True)
        film_strip_sprite.rect.x = 0
        film_strip_sprite.rect.y = 0

        # Create a test PNG file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as test_file:
            # Create a simple 32x32 test image
            import pygame
            test_surface = pygame.Surface((32, 32))
            test_surface.fill((128, 128, 128))  # Gray
            pygame.image.save(test_surface, test_file.name)

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
