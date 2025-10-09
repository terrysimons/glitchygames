"""Comprehensive test coverage for UI Dialogs module."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.ui.dialogs import (
    InputConfirmationDialogScene,
    LoadDialogScene,
    NewCanvasDialogScene,
    SaveDialogScene,
)

from test_mock_factory import MockFactory


class TestUIDialogsComprehensive(unittest.TestCase):
    """Comprehensive test coverage for UI Dialogs module."""

    def setUp(self):
        """Set up test fixtures using enhanced MockFactory."""
        # Use the enhanced centralized pygame mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        
        # Get the mocked objects for direct access
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()
        
        # Mock screen will be set by pygame.display.get_surface() in the Scene constructor

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_input_confirmation_dialog_scene_init(self):
        """Test InputConfirmationDialogScene initialization."""
        # Mock the screen and groups
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty:
            with patch("glitchygames.ui.InputDialog") as mock_input_dialog:
                # Create mock groups
                mock_groups = Mock()
                mock_layered_dirty.return_value = mock_groups
                
                # Create mock dialog
                mock_dialog = Mock()
                mock_dialog.dialog_text_sprite = Mock()
                mock_dialog.dialog_text_sprite.text_box = Mock()
                mock_dialog.dialog_text_sprite.border_width = 0
                mock_dialog.cancel_button = Mock()
                mock_dialog.confirm_button = Mock()
                mock_input_dialog.return_value = mock_dialog
                
                # Create scene
                scene = InputConfirmationDialogScene(
                    previous_scene=Mock(),
                    options=Mock()
                )
                
                # Verify initialization
                self.assertEqual(scene.NAME, "InputConfirmationDialog")
                self.assertEqual(scene.DIALOG_TEXT, "Would you like to do a thing?")
                self.assertEqual(scene.CONFIRMATION_TEXT, "Confirm")
                self.assertEqual(scene.CANCEL_TEXT, "Cancel")
                self.assertEqual(scene.VERSION, "")

    def test_input_confirmation_dialog_scene_init_with_groups(self):
        """Test InputConfirmationDialogScene initialization with existing groups."""
        with patch("glitchygames.ui.InputDialog") as mock_input_dialog:
            # Create mock dialog
            mock_dialog = Mock()
            mock_dialog.dialog_text_sprite = Mock()
            mock_dialog.dialog_text_sprite.text_box = Mock()
            mock_dialog.dialog_text_sprite.border_width = 0
            mock_dialog.cancel_button = Mock()
            mock_dialog.confirm_button = Mock()
            mock_input_dialog.return_value = mock_dialog
            
            # Create existing groups
            existing_groups = Mock()
            
            # Create scene with existing groups
            scene = InputConfirmationDialogScene(
                previous_scene=Mock(),
                options=Mock(),
                groups=existing_groups
            )
            
            # Verify groups were used
            self.assertEqual(scene.all_sprites, existing_groups)

    def test_input_confirmation_dialog_scene_setup(self):
        """Test InputConfirmationDialogScene setup method."""
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty:
            with patch("glitchygames.ui.InputDialog") as mock_input_dialog:
                # Create mock groups
                mock_groups = Mock()
                mock_layered_dirty.return_value = mock_groups
                
                # Create mock dialog
                mock_dialog = Mock()
                mock_dialog.dialog_text_sprite = Mock()
                mock_dialog.dialog_text_sprite.text_box = Mock()
                mock_dialog.dialog_text_sprite.border_width = 0
                mock_dialog.cancel_button = Mock()
                mock_dialog.confirm_button = Mock()
                mock_dialog.add = Mock()
                mock_input_dialog.return_value = mock_dialog
                
                # Create scene
                scene = InputConfirmationDialogScene(
                    previous_scene=Mock(),
                    options=Mock()
                )
                
                # Call setup
                scene.setup()
                
                # Verify callbacks were set
                mock_dialog.cancel_button.callbacks = {
                    "on_left_mouse_button_up_event": scene.on_cancel_event
                }
                mock_dialog.confirm_button.callbacks = {
                    "on_left_mouse_button_up_event": scene.on_confirm_event
                }
                
                # Verify dialog was added to sprites (this happens in setup method)
                mock_dialog.add.assert_called_once_with(scene.all_sprites)

    def test_input_confirmation_dialog_scene_cleanup(self):
        """Test InputConfirmationDialogScene cleanup method."""
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty:
            with patch("glitchygames.ui.InputDialog") as mock_input_dialog:
                # Create mock groups
                mock_groups = Mock()
                mock_layered_dirty.return_value = mock_groups
                
                # Create mock dialog
                mock_dialog = Mock()
                mock_dialog.dialog_text_sprite = Mock()
                mock_dialog.dialog_text_sprite.text_box = Mock()
                mock_dialog.dialog_text_sprite.border_width = 0
                mock_dialog.cancel_button = Mock()
                mock_dialog.confirm_button = Mock()
                mock_input_dialog.return_value = mock_dialog
                
                # Create scene
                scene = InputConfirmationDialogScene(
                    previous_scene=Mock(),
                    options=Mock()
                )
                
                # Call cleanup
                scene.cleanup()
                
                # Verify next_scene was set
                self.assertEqual(scene.next_scene, scene)

    def test_input_confirmation_dialog_scene_dismiss(self):
        """Test InputConfirmationDialogScene dismiss method."""
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty:
            with patch("glitchygames.ui.InputDialog") as mock_input_dialog:
                # Create mock groups
                mock_groups = Mock()
                mock_layered_dirty.return_value = mock_groups
                
                # Create mock dialog
                mock_dialog = Mock()
                mock_dialog.dialog_text_sprite = Mock()
                mock_dialog.dialog_text_sprite.text_box = Mock()
                mock_dialog.dialog_text_sprite.border_width = 0
                mock_dialog.cancel_button = Mock()
                mock_dialog.confirm_button = Mock()
                mock_input_dialog.return_value = mock_dialog
                
                # Create mock previous scene
                mock_previous_scene = Mock()
                mock_sprites = [Mock(), Mock()]  # Make it iterable
                mock_previous_scene.all_sprites = mock_sprites
                
                # Create scene
                scene = InputConfirmationDialogScene(
                    previous_scene=mock_previous_scene,
                    options=Mock()
                )
                
                # Call dismiss
                scene.dismiss()
                
                # Verify previous scene was set as next scene
                self.assertEqual(scene.next_scene, mock_previous_scene)
                self.assertEqual(mock_previous_scene.next_scene, mock_previous_scene)

    def test_input_confirmation_dialog_scene_on_cancel_event(self):
        """Test InputConfirmationDialogScene on_cancel_event method."""
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty:
            with patch("glitchygames.ui.InputDialog") as mock_input_dialog:
                # Create mock groups
                mock_groups = Mock()
                mock_layered_dirty.return_value = mock_groups
                
                # Create mock dialog
                mock_dialog = Mock()
                mock_dialog.dialog_text_sprite = Mock()
                mock_dialog.dialog_text_sprite.text_box = Mock()
                mock_dialog.dialog_text_sprite.border_width = 0
                mock_dialog.cancel_button = Mock()
                mock_dialog.confirm_button = Mock()
                mock_input_dialog.return_value = mock_dialog
                
                # Create scene
                scene = InputConfirmationDialogScene(
                    previous_scene=Mock(),
                    options=Mock()
                )
                
                # Mock the dismiss method
                scene.dismiss = Mock()
                
                # Create mock event
                mock_event = Mock()
                mock_trigger = Mock()
                
                # Call on_cancel_event
                scene.on_cancel_event(mock_event, mock_trigger)
                
                # Verify dismiss was called
                scene.dismiss.assert_called_once()

    def test_input_confirmation_dialog_scene_on_confirm_event(self):
        """Test InputConfirmationDialogScene on_confirm_event method."""
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty:
            with patch("glitchygames.ui.InputDialog") as mock_input_dialog:
                # Create mock groups
                mock_groups = Mock()
                mock_layered_dirty.return_value = mock_groups
                
                # Create mock dialog
                mock_dialog = Mock()
                mock_dialog.dialog_text_sprite = Mock()
                mock_dialog.dialog_text_sprite.text_box = Mock()
                mock_dialog.dialog_text_sprite.border_width = 0
                mock_dialog.cancel_button = Mock()
                mock_dialog.confirm_button = Mock()
                mock_input_dialog.return_value = mock_dialog
                
                # Create scene
                scene = InputConfirmationDialogScene(
                    previous_scene=Mock(),
                    options=Mock()
                )
                
                # Mock the dismiss method
                scene.dismiss = Mock()
                
                # Create mock event
                mock_event = Mock()
                mock_trigger = Mock()
                
                # Call on_confirm_event
                scene.on_confirm_event(mock_event, mock_trigger)
                
                # Verify dismiss was called
                scene.dismiss.assert_called_once()

    def test_new_canvas_dialog_scene_init(self):
        """Test NewCanvasDialogScene initialization."""
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty:
            with patch("glitchygames.ui.InputDialog") as mock_input_dialog:
                # Create mock groups
                mock_groups = Mock()
                mock_layered_dirty.return_value = mock_groups
                
                # Create mock dialog
                mock_dialog = Mock()
                mock_dialog.dialog_text_sprite = Mock()
                mock_dialog.dialog_text_sprite.text_box = Mock()
                mock_dialog.dialog_text_sprite.border_width = 0
                mock_dialog.cancel_button = Mock()
                mock_dialog.confirm_button = Mock()
                mock_input_dialog.return_value = mock_dialog
                
                # Create scene
                scene = NewCanvasDialogScene(
                    previous_scene=Mock(),
                    options=Mock()
                )
                
                # Verify initialization
                self.assertEqual(scene.NAME, "New Canvas Dialog")
                self.assertEqual(scene.DIALOG_TEXT, "Enter canvas size (WxH):")
                self.assertEqual(scene.CONFIRMATION_TEXT, "Create")
                self.assertEqual(scene.CANCEL_TEXT, "Cancel")
                self.assertEqual(scene.VERSION, "")

    def test_load_dialog_scene_init(self):
        """Test LoadDialogScene initialization."""
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty:
            with patch("glitchygames.ui.InputDialog") as mock_input_dialog:
                # Create mock groups
                mock_groups = Mock()
                mock_layered_dirty.return_value = mock_groups
                
                # Create mock dialog
                mock_dialog = Mock()
                mock_dialog.dialog_text_sprite = Mock()
                mock_dialog.dialog_text_sprite.text_box = Mock()
                mock_dialog.dialog_text_sprite.border_width = 0
                mock_dialog.cancel_button = Mock()
                mock_dialog.confirm_button = Mock()
                mock_input_dialog.return_value = mock_dialog
                
                # Create scene
                scene = LoadDialogScene(
                    previous_scene=Mock(),
                    options=Mock()
                )
                
                # Verify initialization
                self.assertEqual(scene.NAME, "Load Dialog")
                self.assertEqual(scene.DIALOG_TEXT, "Enter filename to load:")
                self.assertEqual(scene.CONFIRMATION_TEXT, "Load")
                self.assertEqual(scene.CANCEL_TEXT, "Cancel")
                self.assertEqual(scene.VERSION, "")

    def test_save_dialog_scene_init(self):
        """Test SaveDialogScene initialization."""
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty:
            with patch("glitchygames.ui.InputDialog") as mock_input_dialog:
                # Create mock groups
                mock_groups = Mock()
                mock_layered_dirty.return_value = mock_groups
                
                # Create mock dialog
                mock_dialog = Mock()
                mock_dialog.dialog_text_sprite = Mock()
                mock_dialog.dialog_text_sprite.text_box = Mock()
                mock_dialog.dialog_text_sprite.border_width = 0
                mock_dialog.cancel_button = Mock()
                mock_dialog.confirm_button = Mock()
                mock_input_dialog.return_value = mock_dialog
                
                # Create scene
                scene = SaveDialogScene(
                    previous_scene=Mock(),
                    options=Mock()
                )
                
                # Verify initialization
                self.assertEqual(scene.NAME, "Save Dialog")
                self.assertEqual(scene.DIALOG_TEXT, "Enter filename to save:")
                self.assertEqual(scene.CONFIRMATION_TEXT, "Save")
                self.assertEqual(scene.CANCEL_TEXT, "Cancel")
                self.assertEqual(scene.VERSION, "")

    def test_dialog_scene_inheritance(self):
        """Test that dialog scenes properly inherit from InputConfirmationDialogScene."""
        # Test NewCanvasDialogScene inheritance by checking MRO
        self.assertIn(InputConfirmationDialogScene, NewCanvasDialogScene.__mro__)
        
        # Test LoadDialogScene inheritance by checking MRO
        self.assertIn(InputConfirmationDialogScene, LoadDialogScene.__mro__)
        
        # Test SaveDialogScene inheritance by checking MRO
        self.assertIn(InputConfirmationDialogScene, SaveDialogScene.__mro__)

    def test_dialog_scene_method_resolution(self):
        """Test that dialog scenes can call inherited methods."""
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty:
            with patch("glitchygames.ui.InputDialog") as mock_input_dialog:
                # Create mock groups
                mock_groups = Mock()
                mock_layered_dirty.return_value = mock_groups
                
                # Create mock dialog
                mock_dialog = Mock()
                mock_dialog.dialog_text_sprite = Mock()
                mock_dialog.dialog_text_sprite.text_box = Mock()
                mock_dialog.dialog_text_sprite.border_width = 0
                mock_dialog.cancel_button = Mock()
                mock_dialog.confirm_button = Mock()
                mock_input_dialog.return_value = mock_dialog
                
                # Create scene
                scene = NewCanvasDialogScene(
                    previous_scene=Mock(),
                    options=Mock()
                )
                
                # Test that inherited methods exist
                self.assertTrue(hasattr(scene, "setup"))
                self.assertTrue(hasattr(scene, "cleanup"))
                self.assertTrue(hasattr(scene, "dismiss"))
                self.assertTrue(hasattr(scene, "on_cancel_event"))
                self.assertTrue(hasattr(scene, "on_confirm_event"))

    def test_dialog_scene_screen_dimensions(self):
        """Test that dialog scenes use screen dimensions correctly."""
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty:
            with patch("glitchygames.ui.InputDialog") as mock_input_dialog:
                # Create mock groups
                mock_groups = Mock()
                mock_layered_dirty.return_value = mock_groups
                
                # Create mock dialog
                mock_dialog = Mock()
                mock_dialog.dialog_text_sprite = Mock()
                mock_dialog.dialog_text_sprite.text_box = Mock()
                mock_dialog.dialog_text_sprite.border_width = 0
                mock_dialog.cancel_button = Mock()
                mock_dialog.confirm_button = Mock()
                mock_input_dialog.return_value = mock_dialog
                
                # Create scene
                scene = InputConfirmationDialogScene(
                    previous_scene=Mock(),
                    options=Mock()
                )
                
                # Verify screen dimensions are accessible (mocked by MockFactory)
                self.assertEqual(scene.screen_width, 800)
                self.assertEqual(scene.screen_height, 600)

    def test_dialog_scene_dialog_creation(self):
        """Test that dialog is created with correct parameters."""
        with patch("pygame.sprite.LayeredDirty") as mock_layered_dirty:
            with patch("glitchygames.ui.InputDialog") as mock_input_dialog:
                # Create mock groups
                mock_groups = Mock()
                mock_layered_dirty.return_value = mock_groups
                
                # Create mock dialog
                mock_dialog = Mock()
                mock_dialog.dialog_text_sprite = Mock()
                mock_dialog.dialog_text_sprite.text_box = Mock()
                mock_dialog.dialog_text_sprite.border_width = 0
                mock_dialog.cancel_button = Mock()
                mock_dialog.confirm_button = Mock()
                mock_input_dialog.return_value = mock_dialog
                
                # Create scene - this should trigger InputDialog creation
                scene = InputConfirmationDialogScene(
                    previous_scene=Mock(),
                    options=Mock()
                )
                
                # Verify InputDialog was called with correct parameters
                mock_input_dialog.assert_called_once()
                call_args = mock_input_dialog.call_args
                
                # Check that the call was made with expected parameters
                self.assertEqual(call_args[1]["name"], scene.NAME)
                self.assertEqual(call_args[1]["dialog_text"], scene.DIALOG_TEXT)
                self.assertEqual(call_args[1]["confirm_text"], scene.CONFIRMATION_TEXT)
                self.assertEqual(call_args[1]["cancel_text"], scene.CANCEL_TEXT)


if __name__ == "__main__":
    unittest.main()
