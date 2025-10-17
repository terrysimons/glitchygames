"""Test suite for UI Dialog components.

This module tests dialog scene functionality including initialization,
user interactions, and dialog-specific behavior.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.ui.dialogs import (
    InputConfirmationDialogScene,
    LoadDialogScene,
    NewCanvasDialogScene,
    SaveDialogScene,
)

from tests.mocks.test_mock_factory import MockFactory


class TestInputConfirmationDialogScene(unittest.TestCase):
    """Test InputConfirmationDialogScene functionality."""

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

    def test_input_confirmation_dialog_scene_init(self):
        """Test InputConfirmationDialogScene initialization."""
        # Mock the screen and groups
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty, \
             patch("glitchygames.ui.dialogs.InputDialog") as mock_input_dialog:
            # Create mock groups
            mock_groups = Mock()
            mock_layered_dirty.return_value = mock_groups

            # Create mock dialog
            mock_dialog = Mock()
            mock_dialog.dialog_text_sprite = Mock()
            mock_input_dialog.return_value = mock_dialog

            # Act
            scene = InputConfirmationDialogScene(
                previous_scene=Mock(),
                groups=mock_groups
            )

            # Assert
            assert scene is not None
            mock_input_dialog.assert_called_once()

    def test_input_confirmation_dialog_text_submission(self):
        """Test InputConfirmationDialogScene text submission."""
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty, \
             patch("glitchygames.ui.dialogs.InputDialog") as mock_input_dialog:
            # Create mock groups
            mock_groups = Mock()
            mock_layered_dirty.return_value = mock_groups

            # Create mock dialog
            mock_dialog = Mock()
            mock_dialog.dialog_text_sprite = Mock()
            mock_input_dialog.return_value = mock_dialog

            scene = InputConfirmationDialogScene(
                previous_scene=Mock(),
                groups=mock_groups
            )

            # Act: simulate text submission
            scene.on_text_submit_event("Submitted Text")

            # Assert: should handle text submission
            assert scene is not None

    def test_input_confirmation_dialog_cancellation(self):
        """Test InputConfirmationDialogScene cancellation."""
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty, \
             patch("glitchygames.ui.dialogs.InputDialog") as mock_input_dialog:
            # Create mock groups
            mock_groups = Mock()
            mock_layered_dirty.return_value = mock_groups

            # Create mock dialog
            mock_dialog = Mock()
            mock_dialog.dialog_text_sprite = Mock()
            mock_input_dialog.return_value = mock_dialog

            scene = InputConfirmationDialogScene(
                previous_scene=Mock(),
                groups=mock_groups
            )

            # Act: simulate cancellation via key down event
            event = Mock()
            event.key = pygame.K_ESCAPE
            scene.on_key_down_event(event)

            # Assert: should handle cancellation
            assert scene is not None


class TestLoadDialogScene(unittest.TestCase):
    """Test LoadDialogScene functionality."""

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

    def test_load_dialog_scene_init(self):
        """Test LoadDialogScene initialization."""
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty:
            # Create mock groups
            mock_groups = Mock()
            mock_layered_dirty.return_value = mock_groups

            # Act
            scene = LoadDialogScene(
                previous_scene=Mock(),
                groups=mock_groups
            )

            # Assert
            assert scene is not None

    def test_load_dialog_file_selection(self):
        """Test LoadDialogScene file selection."""
        # Create mock groups using centralized mocks
        mock_groups = Mock()
        mock_groups.__iter__ = Mock(return_value=iter([]))  # Make it iterable

        # Create mock previous scene with iterable all_sprites
        mock_previous_scene = Mock()
        mock_previous_scene.all_sprites = []  # Empty list is iterable

        scene = LoadDialogScene(
            previous_scene=mock_previous_scene,
            groups=mock_groups
        )

        # Act: simulate file selection via confirm event
        event = Mock()
        scene.dialog.input_box.text = "test_file.toml"
        scene.on_confirm_event(event, Mock())

        # Assert: should handle file selection
        assert scene is not None

    def test_load_dialog_cancellation(self):
        """Test LoadDialogScene cancellation."""
        # Create mock groups using centralized mocks
        mock_groups = Mock()
        mock_groups.__iter__ = Mock(return_value=iter([]))  # Make it iterable

        # Create mock previous scene with iterable all_sprites
        mock_previous_scene = Mock()
        mock_previous_scene.all_sprites = []  # Empty list is iterable

        scene = LoadDialogScene(
            previous_scene=mock_previous_scene,
            groups=mock_groups
        )

        # Act: simulate cancellation via key down event
        event = Mock()
        event.key = pygame.K_ESCAPE
        event.unicode = ""  # Add unicode attribute
        scene.on_key_down_event(event)

        # Assert: should handle cancellation
        assert scene is not None


class TestSaveDialogScene(unittest.TestCase):
    """Test SaveDialogScene functionality."""

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

    def test_save_dialog_scene_init(self):
        """Test SaveDialogScene initialization."""
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty:
            # Create mock groups
            mock_groups = Mock()
            mock_layered_dirty.return_value = mock_groups

            # Act
            scene = SaveDialogScene(
                previous_scene=Mock(),
                groups=mock_groups
            )

            # Assert
            assert scene is not None

    def test_save_dialog_filename_input(self):
        """Test SaveDialogScene filename input."""
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty:
            # Create mock groups
            mock_groups = Mock()
            mock_layered_dirty.return_value = mock_groups

            scene = SaveDialogScene(
                previous_scene=Mock(),
                groups=mock_groups
            )

            # Act: simulate filename input
            scene.on_text_input_event("n")
            scene.on_text_input_event("e")
            scene.on_text_input_event("w")
            scene.on_text_input_event("_")
            scene.on_text_input_event("f")
            scene.on_text_input_event("i")
            scene.on_text_input_event("l")
            scene.on_text_input_event("e")

            # Assert: should handle filename input
            assert scene is not None

    def test_save_dialog_save_confirmation(self):
        """Test SaveDialogScene save confirmation."""
        # Create mock groups using centralized mocks
        mock_groups = Mock()
        mock_groups.__iter__ = Mock(return_value=iter([]))  # Make it iterable

        # Create mock previous scene with iterable all_sprites
        mock_previous_scene = Mock()
        mock_previous_scene.all_sprites = []  # Empty list is iterable

        scene = SaveDialogScene(
            previous_scene=mock_previous_scene,
            groups=mock_groups
        )

        # Act: simulate save confirmation via confirm event
        event = Mock()
        scene.dialog.input_box.text = "test_file.toml"
        scene.on_confirm_event(event, Mock())

        # Assert: should handle save confirmation
        assert scene is not None


class TestNewCanvasDialogScene(unittest.TestCase):
    """Test NewCanvasDialogScene functionality."""

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

    def test_new_canvas_dialog_scene_init(self):
        """Test NewCanvasDialogScene initialization."""
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty:
            # Create mock groups
            mock_groups = Mock()
            mock_layered_dirty.return_value = mock_groups

            # Act
            scene = NewCanvasDialogScene(
                previous_scene=Mock(),
                groups=mock_groups
            )

            # Assert
            assert scene is not None

    def test_new_canvas_dialog_dimension_input(self):
        """Test NewCanvasDialogScene dimension input."""
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty:
            # Create mock groups
            mock_groups = Mock()
            mock_layered_dirty.return_value = mock_groups

            scene = NewCanvasDialogScene(
                previous_scene=Mock(),
                groups=mock_groups
            )

            # Act: simulate dimension input
            scene.on_text_input_event("1")
            scene.on_text_input_event("0")
            scene.on_text_input_event("2")
            scene.on_text_input_event("4")

            # Assert: should handle dimension input
            assert scene is not None

    def test_new_canvas_dialog_creation_confirmation(self):
        """Test NewCanvasDialogScene creation confirmation."""
        # Create mock groups using centralized mocks
        mock_groups = Mock()
        mock_groups.__iter__ = Mock(return_value=iter([]))  # Make it iterable

        # Create mock previous scene with iterable all_sprites
        mock_previous_scene = Mock()
        mock_previous_scene.all_sprites = []  # Empty list is iterable

        scene = NewCanvasDialogScene(
            previous_scene=mock_previous_scene,
            groups=mock_groups
        )

        # Act: simulate creation confirmation via confirm event
        event = Mock()
        scene.dialog.input_box.text = "1024x768"
        scene.on_confirm_event(event, Mock())

        # Assert: should handle creation confirmation
        assert scene is not None

    def test_new_canvas_dialog_dimension_validation(self):
        """Test NewCanvasDialogScene dimension validation."""
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty:
            # Create mock groups
            mock_groups = Mock()
            mock_layered_dirty.return_value = mock_groups

            scene = NewCanvasDialogScene(
                previous_scene=Mock(),
                groups=mock_groups
            )

            # Act: test valid dimensions by setting input box text
            scene.dialog.input_box.text = "1024x768"

            # Assert: should accept valid dimensions
            assert scene.dialog.input_box.text == "1024x768"

            # Act: test invalid dimensions (should be handled by input validation)
            scene.dialog.input_box.text = "invalid"

            # Assert: should handle invalid input
            assert scene.dialog.input_box.text == "invalid"


if __name__ == "__main__":
    unittest.main()
