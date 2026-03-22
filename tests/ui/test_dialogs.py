"""Test suite for UI Dialog components.

This module consolidates tests from:
- test_ui_dialogs.py: Dialog scene functionality
- test_dialogs_coverage.py: Coverage tests for dialogs module
- test_dialogs_deeper_coverage.py: Deeper coverage tests for dialogs module
- test_confirm_dialog_coverage.py: ConfirmDialog coverage tests
- test_input_dialog_coverage.py: InputDialog coverage tests
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Save REAL LayeredDirty before mock_pygame_patches replaces it with a Mock.
_RealLayeredDirty = pygame.sprite.LayeredDirty

from glitchygames.events.core import HashableEvent  # noqa: E402
from glitchygames.ui import ConfirmDialog, InputDialog  # noqa: E402
from glitchygames.ui.dialogs import (  # noqa: E402
    InputConfirmationDialogScene,
    LoadDialogScene,
    NewCanvasDialogScene,
    SaveDialogScene,
    _get_examples_dir,
    _get_load_path,
    _get_save_path,
    _process_example_filename,
)
from tests.mocks import MockFactory  # noqa: E402

# Test constants from test_confirm_dialog_coverage.py
TEST_CONFIRM_DIALOG_X = 50
TEST_CONFIRM_DIALOG_Y = 50
TEST_CONFIRM_DIALOG_WIDTH = 300
TEST_CONFIRM_DIALOG_HEIGHT = 100
CONFIRM_BUTTON_WIDTH = 80
CONFIRM_BUTTON_HEIGHT = 30
BUTTON_SPACING = 20

# Test constants from test_input_dialog_coverage.py
TEST_INPUT_DIALOG_X = 100
TEST_INPUT_DIALOG_Y = 100
TEST_INPUT_DIALOG_WIDTH = 400
TEST_INPUT_DIALOG_HEIGHT = 200


# ============================================================================
# From test_ui_dialogs.py
# ============================================================================


class TestInputConfirmationDialogScene:
    """Test InputConfirmationDialogScene functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def test_input_confirmation_dialog_scene_init(self, mocker):
        """Test InputConfirmationDialogScene initialization."""
        # Mock the screen and groups
        mock_layered_dirty = mocker.patch('pygame.sprite.LayeredDirty')
        mock_input_dialog = mocker.patch('glitchygames.ui.dialogs.InputDialog')
        # Create mock groups
        mock_groups = mocker.Mock()
        mock_layered_dirty.return_value = mock_groups

        # Create mock dialog
        mock_dialog = mocker.Mock()
        mock_dialog.dialog_text_sprite = mocker.Mock()
        mock_input_dialog.return_value = mock_dialog

        # Act
        scene = InputConfirmationDialogScene(previous_scene=mocker.Mock(), groups=mock_groups)

        # Assert
        assert scene is not None
        mock_input_dialog.assert_called_once()

    def test_input_confirmation_dialog_text_submission(self, mocker):
        """Test InputConfirmationDialogScene text submission."""
        mock_layered_dirty = mocker.patch('pygame.sprite.LayeredDirty')
        mock_input_dialog = mocker.patch('glitchygames.ui.dialogs.InputDialog')
        # Create mock groups
        mock_groups = mocker.Mock()
        mock_layered_dirty.return_value = mock_groups

        # Create mock dialog
        mock_dialog = mocker.Mock()
        mock_dialog.dialog_text_sprite = mocker.Mock()
        mock_input_dialog.return_value = mock_dialog

        scene = InputConfirmationDialogScene(previous_scene=mocker.Mock(), groups=mock_groups)

        # Act: simulate text submission
        scene.on_text_submit_event('Submitted Text')

        # Assert: should handle text submission
        assert scene is not None

    def test_input_confirmation_dialog_cancellation(self, mocker):
        """Test InputConfirmationDialogScene cancellation."""
        mock_layered_dirty = mocker.patch('pygame.sprite.LayeredDirty')
        mock_input_dialog = mocker.patch('glitchygames.ui.dialogs.InputDialog')
        # Create mock groups
        mock_groups = mocker.Mock()
        mock_layered_dirty.return_value = mock_groups

        # Create mock dialog
        mock_dialog = mocker.Mock()
        mock_dialog.dialog_text_sprite = mocker.Mock()
        mock_input_dialog.return_value = mock_dialog

        scene = InputConfirmationDialogScene(previous_scene=mocker.Mock(), groups=mock_groups)

        # Act: simulate cancellation via key down event
        event = mocker.Mock()
        event.key = pygame.K_ESCAPE
        scene.on_key_down_event(event)

        # Assert: should handle cancellation
        assert scene is not None


class TestLoadDialogScene:
    """Test LoadDialogScene functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def test_load_dialog_scene_init(self, mocker):
        """Test LoadDialogScene initialization."""
        mock_layered_dirty = mocker.patch('pygame.sprite.LayeredDirty')
        # Create mock groups
        mock_groups = mocker.Mock()
        mock_layered_dirty.return_value = mock_groups

        # Act
        scene = LoadDialogScene(previous_scene=mocker.Mock(), groups=mock_groups)

        # Assert
        assert scene is not None

    def test_load_dialog_file_selection(self, mocker):
        """Test LoadDialogScene file selection."""
        # Create mock groups using centralized mocks
        mock_groups = mocker.Mock()
        mock_groups.__iter__ = mocker.Mock(return_value=iter([]))  # Make it iterable

        # Create mock previous scene with iterable all_sprites
        mock_previous_scene = mocker.Mock()
        mock_previous_scene.all_sprites = []  # Empty list is iterable

        scene = LoadDialogScene(previous_scene=mock_previous_scene, groups=mock_groups)

        # Act: simulate file selection via confirm event
        event = mocker.Mock()
        scene.dialog.input_box.text = 'test_file.toml'
        scene.on_confirm_event(event, mocker.Mock())

        # Assert: should handle file selection
        assert scene is not None

    def test_load_dialog_cancellation(self, mocker):
        """Test LoadDialogScene cancellation."""
        # Create mock groups using centralized mocks
        mock_groups = mocker.Mock()
        mock_groups.__iter__ = mocker.Mock(return_value=iter([]))  # Make it iterable

        # Create mock previous scene with iterable all_sprites
        mock_previous_scene = mocker.Mock()
        mock_previous_scene.all_sprites = []  # Empty list is iterable

        scene = LoadDialogScene(previous_scene=mock_previous_scene, groups=mock_groups)

        # Act: simulate cancellation via key down event
        event = mocker.Mock()
        event.key = pygame.K_ESCAPE
        event.unicode = ''  # Add unicode attribute
        scene.on_key_down_event(event)

        # Assert: should handle cancellation
        assert scene is not None


class TestSaveDialogScene:
    """Test SaveDialogScene functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def test_save_dialog_scene_init(self, mocker):
        """Test SaveDialogScene initialization."""
        mock_layered_dirty = mocker.patch('pygame.sprite.LayeredDirty')
        # Create mock groups
        mock_groups = mocker.Mock()
        mock_layered_dirty.return_value = mock_groups

        # Act
        scene = SaveDialogScene(previous_scene=mocker.Mock(), groups=mock_groups)

        # Assert
        assert scene is not None

    def test_save_dialog_filename_input(self, mocker):
        """Test SaveDialogScene filename input."""
        mock_layered_dirty = mocker.patch('pygame.sprite.LayeredDirty')
        # Create mock groups
        mock_groups = mocker.Mock()
        mock_layered_dirty.return_value = mock_groups

        scene = SaveDialogScene(previous_scene=mocker.Mock(), groups=mock_groups)

        # Act: simulate filename input
        scene.on_text_input_event(HashableEvent(pygame.TEXTINPUT, text='n'))
        scene.on_text_input_event(HashableEvent(pygame.TEXTINPUT, text='e'))
        scene.on_text_input_event(HashableEvent(pygame.TEXTINPUT, text='w'))
        scene.on_text_input_event(HashableEvent(pygame.TEXTINPUT, text='_'))
        scene.on_text_input_event(HashableEvent(pygame.TEXTINPUT, text='f'))
        scene.on_text_input_event(HashableEvent(pygame.TEXTINPUT, text='i'))
        scene.on_text_input_event(HashableEvent(pygame.TEXTINPUT, text='l'))
        scene.on_text_input_event(HashableEvent(pygame.TEXTINPUT, text='e'))

        # Assert: should handle filename input
        assert scene is not None

    def test_save_dialog_save_confirmation(self, mocker):
        """Test SaveDialogScene save confirmation."""
        # Create mock groups using centralized mocks
        mock_groups = mocker.Mock()
        mock_groups.__iter__ = mocker.Mock(return_value=iter([]))  # Make it iterable

        # Create mock previous scene with iterable all_sprites
        mock_previous_scene = mocker.Mock()
        mock_previous_scene.all_sprites = []  # Empty list is iterable

        scene = SaveDialogScene(previous_scene=mock_previous_scene, groups=mock_groups)

        # Act: simulate save confirmation via confirm event
        event = mocker.Mock()
        scene.dialog.input_box.text = 'test_file.toml'
        scene.on_confirm_event(event, mocker.Mock())

        # Assert: should handle save confirmation
        assert scene is not None


class TestNewCanvasDialogScene:
    """Test NewCanvasDialogScene functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def test_new_canvas_dialog_scene_init(self, mocker):
        """Test NewCanvasDialogScene initialization."""
        mock_layered_dirty = mocker.patch('pygame.sprite.LayeredDirty')
        # Create mock groups
        mock_groups = mocker.Mock()
        mock_layered_dirty.return_value = mock_groups

        # Act
        scene = NewCanvasDialogScene(previous_scene=mocker.Mock(), groups=mock_groups)

        # Assert
        assert scene is not None

    def test_new_canvas_dialog_dimension_input(self, mocker):
        """Test NewCanvasDialogScene dimension input."""
        mock_layered_dirty = mocker.patch('pygame.sprite.LayeredDirty')
        # Create mock groups
        mock_groups = mocker.Mock()
        mock_layered_dirty.return_value = mock_groups

        scene = NewCanvasDialogScene(previous_scene=mocker.Mock(), groups=mock_groups)

        # Act: simulate dimension input
        scene.on_text_input_event(HashableEvent(pygame.TEXTINPUT, text='1'))
        scene.on_text_input_event(HashableEvent(pygame.TEXTINPUT, text='0'))
        scene.on_text_input_event(HashableEvent(pygame.TEXTINPUT, text='2'))
        scene.on_text_input_event(HashableEvent(pygame.TEXTINPUT, text='4'))

        # Assert: should handle dimension input
        assert scene is not None

    def test_new_canvas_dialog_creation_confirmation(self, mocker):
        """Test NewCanvasDialogScene creation confirmation."""
        # Create mock groups using centralized mocks
        mock_groups = mocker.Mock()
        mock_groups.__iter__ = mocker.Mock(return_value=iter([]))  # Make it iterable

        # Create mock previous scene with iterable all_sprites
        mock_previous_scene = mocker.Mock()
        mock_previous_scene.all_sprites = []  # Empty list is iterable

        scene = NewCanvasDialogScene(previous_scene=mock_previous_scene, groups=mock_groups)

        # Act: simulate creation confirmation via confirm event
        event = mocker.Mock()
        scene.dialog.input_box.text = '1024x768'
        scene.on_confirm_event(event, mocker.Mock())

        # Assert: should handle creation confirmation
        assert scene is not None

    def test_new_canvas_dialog_dimension_validation(self, mocker):
        """Test NewCanvasDialogScene dimension validation."""
        mock_layered_dirty = mocker.patch('pygame.sprite.LayeredDirty')
        # Create mock groups
        mock_groups = mocker.Mock()
        mock_layered_dirty.return_value = mock_groups

        scene = NewCanvasDialogScene(previous_scene=mocker.Mock(), groups=mock_groups)

        # Act: test valid dimensions by setting input box text
        scene.dialog.input_box.text = '1024x768'

        # Assert: should accept valid dimensions
        assert scene.dialog.input_box.text == '1024x768'

        # Act: test invalid dimensions (should be handled by input validation)
        scene.dialog.input_box.text = 'invalid'

        # Assert: should handle invalid input
        assert scene.dialog.input_box.text == 'invalid'


# ============================================================================
# From test_dialogs_coverage.py
# ============================================================================


class TestProcessExampleFilename:
    """Test _process_example_filename helper function."""

    def test_plain_filename(self):
        """Test processing a plain filename without prefix."""
        filename, is_example = _process_example_filename('test.toml')
        assert filename == 'test.toml'
        assert is_example is False

    def test_example_prefix(self):
        """Test processing filename with 'example:' prefix."""
        filename, is_example = _process_example_filename('example:test.toml')
        assert filename == 'test.toml'
        assert is_example is True

    def test_examples_prefix(self):
        """Test processing filename with 'examples:' prefix."""
        filename, is_example = _process_example_filename('examples:test.toml')
        assert filename == 'test.toml'
        assert is_example is True

    def test_whitespace_handling(self):
        """Test processing filename with whitespace."""
        filename, is_example = _process_example_filename('  test.toml  ')
        assert filename == 'test.toml'
        assert is_example is False

    def test_example_prefix_with_spaces(self):
        """Test processing filename with 'example:' prefix and extra spaces."""
        filename, is_example = _process_example_filename('example:  test.toml')
        assert filename == 'test.toml'
        assert is_example is True


class TestGetExamplesDir:
    """Test _get_examples_dir helper function."""

    def test_returns_path(self):
        """Test _get_examples_dir returns a Path object."""
        result = _get_examples_dir()
        assert isinstance(result, Path)
        # Use Path parts for cross-platform compatibility
        assert result.parts[-3:] == ('examples', 'resources', 'sprites')

    def test_pyinstaller_bundle_path(self, mocker):
        """Test _get_examples_dir with PyInstaller _MEIPASS."""
        bundle_path = Path('/tmp/bundle')  # noqa: S108
        mocker.patch.object(sys, '_MEIPASS', str(bundle_path), create=True)
        result = _get_examples_dir()
        assert isinstance(result, Path)
        assert bundle_path in result.parents or result.parts[1] == 'tmp'
        assert result.parts[-3:] == ('examples', 'resources', 'sprites')


class TestGetSavePath:
    """Test _get_save_path helper function."""

    def test_plain_filename(self):
        """Test _get_save_path with a plain filename."""
        result = _get_save_path('test.toml')
        assert result == Path('test.toml')

    def test_example_prefix(self):
        """Test _get_save_path with 'example:' prefix."""
        result = _get_save_path('example:test.toml')
        assert isinstance(result, Path)
        assert result.name == 'test.toml'
        # Should be in the examples directory (cross-platform check)
        assert result.parent.parts[-3:] == ('examples', 'resources', 'sprites')


class TestGetLoadPath:
    """Test _get_load_path helper function."""

    def test_plain_filename(self):
        """Test _get_load_path with a plain filename."""
        result = _get_load_path('test.toml')
        assert result == Path('test.toml')

    def test_example_prefix(self):
        """Test _get_load_path with 'example:' prefix."""
        result = _get_load_path('example:test.toml')
        assert isinstance(result, Path)
        assert result.name == 'test.toml'
        assert result.parent.parts[-3:] == ('examples', 'resources', 'sprites')

    def test_examples_prefix(self):
        """Test _get_load_path with 'examples:' prefix."""
        result = _get_load_path('examples:heart.toml')
        assert isinstance(result, Path)
        assert result.name == 'heart.toml'
        assert result.parent.parts[-3:] == ('examples', 'resources', 'sprites')


class TestDialogSceneSetupCleanupDismiss:
    """Test dialog scene lifecycle methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_input_confirmation_dialog_setup(self, mocker):
        """Test InputConfirmationDialogScene setup configures button callbacks."""
        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []

        scene = InputConfirmationDialogScene(previous_scene=mock_previous, groups=mock_groups)
        scene.setup()

        # Verify button callbacks were set
        assert scene.dialog.cancel_button.callbacks is not None
        assert scene.dialog.confirm_button.callbacks is not None
        assert 'on_left_mouse_button_up_event' in scene.dialog.cancel_button.callbacks
        assert 'on_left_mouse_button_up_event' in scene.dialog.confirm_button.callbacks

    def test_input_confirmation_dialog_cleanup(self, mocker):
        """Test InputConfirmationDialogScene cleanup sets next_scene to self."""
        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []

        scene = InputConfirmationDialogScene(previous_scene=mock_previous, groups=mock_groups)
        scene.cleanup()

        assert scene.next_scene is scene

    def test_input_confirmation_dialog_dismiss(self, mocker):
        """Test InputConfirmationDialogScene dismiss returns to previous scene."""
        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []

        scene = InputConfirmationDialogScene(previous_scene=mock_previous, groups=mock_groups)
        scene.dismiss()

        assert scene.next_scene is mock_previous
        assert mock_previous.next_scene is mock_previous

    def test_input_confirmation_dialog_cancel_event(self, mocker):
        """Test InputConfirmationDialogScene on_cancel_event dismisses dialog."""
        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []

        scene = InputConfirmationDialogScene(previous_scene=mock_previous, groups=mock_groups)
        event = mocker.Mock()
        trigger = mocker.Mock()
        scene.on_cancel_event(event, trigger)

        assert scene.next_scene is mock_previous

    def test_input_confirmation_dialog_on_input_box_submit(self, mocker):
        """Test InputConfirmationDialogScene on_input_box_submit_event."""
        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []

        scene = InputConfirmationDialogScene(previous_scene=mock_previous, groups=mock_groups)
        control = mocker.Mock()
        control.name = 'TestInput'
        control.text = 'test value'
        # Should not raise
        scene.on_input_box_submit_event(control)

    def test_input_confirmation_dialog_mouse_button_up(self, mocker):
        """Test InputConfirmationDialogScene on_mouse_button_up_event activates input."""
        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []

        scene = InputConfirmationDialogScene(previous_scene=mock_previous, groups=mock_groups)
        event = mocker.Mock()
        # The input_box is a real InputBox, so we check its state after calling
        scene.on_mouse_button_up_event(event)
        assert scene.dialog.input_box.active is True

    def test_input_confirmation_dialog_key_up_tab_activates(self, mocker):
        """Test InputConfirmationDialogScene on_key_up_event with Tab activates input."""
        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []

        scene = InputConfirmationDialogScene(previous_scene=mock_previous, groups=mock_groups)
        scene.dialog.input_box.active = False
        event = mocker.Mock()
        event.key = pygame.K_TAB
        scene.on_key_up_event(event)
        assert scene.dialog.input_box.active is True

    def test_input_confirmation_dialog_key_up_active_input(self, mocker):
        """Test InputConfirmationDialogScene on_key_up_event when input is active."""
        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []

        scene = InputConfirmationDialogScene(previous_scene=mock_previous, groups=mock_groups)
        scene.dialog.input_box.active = True
        # Mock the dialog's on_key_up_event since it's the one being delegated to
        scene.dialog.on_key_up_event = mocker.Mock()
        event = mocker.Mock()
        event.key = pygame.K_a
        scene.on_key_up_event(event)
        scene.dialog.on_key_up_event.assert_called_once_with(event)

    def test_input_confirmation_dialog_key_down_active_input(self, mocker):
        """Test InputConfirmationDialogScene on_key_down_event when input is active."""
        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []

        scene = InputConfirmationDialogScene(previous_scene=mock_previous, groups=mock_groups)
        scene.dialog.input_box.active = True
        # Mock the dialog's on_key_down_event since it's the one being delegated to
        scene.dialog.on_key_down_event = mocker.Mock()
        event = mocker.Mock()
        event.key = pygame.K_a
        scene.on_key_down_event(event)
        scene.dialog.on_key_down_event.assert_called_once_with(event)

    def test_input_confirmation_dialog_key_down_inactive_input(self, mocker):
        """Test InputConfirmationDialogScene on_key_down_event when input is inactive."""
        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []

        scene = InputConfirmationDialogScene(previous_scene=mock_previous, groups=mock_groups)
        scene.dialog.input_box.active = False
        # The inactive branch calls super().on_key_up_event which may try to
        # iterate all_sprites, so provide proper mock
        scene.all_sprites = _RealLayeredDirty()
        event = mocker.Mock()
        event.key = pygame.K_a
        # Should call super().on_key_up_event - just verify it doesn't raise
        scene.on_key_down_event(event)


class TestDeleteAnimationDialogScene:
    """Test DeleteAnimationDialogScene."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_delete_animation_dialog_initialization(self, mocker):
        """Test DeleteAnimationDialogScene initialization."""
        from glitchygames.ui.dialogs import DeleteAnimationDialogScene

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        confirm_callback = mocker.Mock()
        cancel_callback = mocker.Mock()

        dialog = DeleteAnimationDialogScene(
            previous_scene=mock_previous,
            animation_name='idle',
            on_confirm_callback=confirm_callback,
            on_cancel_callback=cancel_callback,
            groups=mock_groups,
        )
        assert dialog.animation_name == 'idle'
        assert dialog.on_confirm_callback is confirm_callback
        assert dialog.on_cancel_callback is cancel_callback

    def test_delete_animation_confirm_matching_name(self, mocker):
        """Test confirm with matching animation name calls callback."""
        from glitchygames.ui.dialogs import DeleteAnimationDialogScene

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        confirm_callback = mocker.Mock()

        dialog = DeleteAnimationDialogScene(
            previous_scene=mock_previous,
            animation_name='idle',
            on_confirm_callback=confirm_callback,
            groups=mock_groups,
        )
        dialog.game_engine = mocker.Mock()  # type: ignore[unresolved-attribute]
        dialog.dialog.input_box.text = 'idle'
        event = mocker.Mock()
        dialog.on_confirm_event(event)
        confirm_callback.assert_called_once()

    def test_delete_animation_confirm_non_matching_name(self, mocker):
        """Test confirm with non-matching name clears input."""
        from glitchygames.ui.dialogs import DeleteAnimationDialogScene

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        confirm_callback = mocker.Mock()

        dialog = DeleteAnimationDialogScene(
            previous_scene=mock_previous,
            animation_name='idle',
            on_confirm_callback=confirm_callback,
            groups=mock_groups,
        )
        dialog.dialog.input_box.text = 'wrong'
        event = mocker.Mock()
        dialog.on_confirm_event(event)
        confirm_callback.assert_not_called()
        assert not dialog.dialog.input_box.text

    def test_delete_animation_cancel_with_callback(self, mocker):
        """Test cancel event calls cancel callback."""
        from glitchygames.ui.dialogs import DeleteAnimationDialogScene

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        cancel_callback = mocker.Mock()

        dialog = DeleteAnimationDialogScene(
            previous_scene=mock_previous,
            animation_name='idle',
            on_confirm_callback=mocker.Mock(),
            on_cancel_callback=cancel_callback,
            groups=mock_groups,
        )
        dialog.game_engine = mocker.Mock()  # type: ignore[unresolved-attribute]
        event = mocker.Mock()
        dialog.on_cancel_event(event)
        cancel_callback.assert_called_once()

    def test_delete_animation_cancel_without_callback(self, mocker):
        """Test cancel event without callback doesn't raise."""
        from glitchygames.ui.dialogs import DeleteAnimationDialogScene

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()

        dialog = DeleteAnimationDialogScene(
            previous_scene=mock_previous,
            animation_name='idle',
            on_confirm_callback=mocker.Mock(),
            on_cancel_callback=None,
            groups=mock_groups,
        )
        dialog.game_engine = mocker.Mock()  # type: ignore[unresolved-attribute]
        event = mocker.Mock()
        dialog.on_cancel_event(event)

    def test_delete_animation_key_down_active_input(self, mocker):
        """Test DeleteAnimationDialogScene key down when input is active."""
        from glitchygames.ui.dialogs import DeleteAnimationDialogScene

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()

        dialog = DeleteAnimationDialogScene(
            previous_scene=mock_previous,
            animation_name='idle',
            on_confirm_callback=mocker.Mock(),
            groups=mock_groups,
        )

        # Mock the dialog's on_key_down_event
        dialog.dialog.on_key_down_event = mocker.Mock()
        dialog.dialog.input_box.active = True
        event = mocker.Mock()
        event.key = pygame.K_a
        dialog.on_key_down_event(event)
        dialog.dialog.on_key_down_event.assert_called_once_with(event)

    def test_delete_animation_key_up_active_input(self, mocker):
        """Test DeleteAnimationDialogScene key up when input is active."""
        from glitchygames.ui.dialogs import DeleteAnimationDialogScene

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()

        dialog = DeleteAnimationDialogScene(
            previous_scene=mock_previous,
            animation_name='idle',
            on_confirm_callback=mocker.Mock(),
            groups=mock_groups,
        )

        dialog.dialog.on_key_up_event = mocker.Mock()
        dialog.dialog.input_box.active = True
        event = mocker.Mock()
        event.key = pygame.K_a
        dialog.on_key_up_event(event)
        dialog.dialog.on_key_up_event.assert_called_once_with(event)

    def test_delete_animation_key_up_tab_activates(self, mocker):
        """Test DeleteAnimationDialogScene key up with Tab activates input."""
        from glitchygames.ui.dialogs import DeleteAnimationDialogScene

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()

        dialog = DeleteAnimationDialogScene(
            previous_scene=mock_previous,
            animation_name='idle',
            on_confirm_callback=mocker.Mock(),
            groups=mock_groups,
        )

        dialog.dialog.input_box.active = False
        tab_event = mocker.Mock()
        tab_event.key = pygame.K_TAB
        dialog.on_key_up_event(tab_event)
        assert dialog.dialog.input_box.active is True


class TestDeleteFrameDialogScene:
    """Test DeleteFrameDialogScene."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_delete_frame_dialog_initialization(self, mocker):
        """Test DeleteFrameDialogScene initialization."""
        from glitchygames.ui.dialogs import DeleteFrameDialogScene

        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()

        dialog = DeleteFrameDialogScene(
            previous_scene=mock_previous,
            animation_name='idle',
            frame_index=0,
            on_confirm_callback=mocker.Mock(),
            groups=mock_groups,
        )
        assert dialog.animation_name == 'idle'
        assert dialog.frame_index == 0

    def test_delete_frame_confirm_yes(self, mocker):
        """Test confirm with 'YES' calls callback."""
        from glitchygames.ui.dialogs import DeleteFrameDialogScene

        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        confirm_callback = mocker.Mock()

        dialog = DeleteFrameDialogScene(
            previous_scene=mock_previous,
            animation_name='idle',
            frame_index=0,
            on_confirm_callback=confirm_callback,
            groups=mock_groups,
        )
        dialog.game_engine = mocker.Mock()  # type: ignore[unresolved-attribute]
        dialog.dialog.input_box.text = 'YES'
        event = mocker.Mock()
        dialog.on_confirm_event(event)
        confirm_callback.assert_called_once()

    def test_delete_frame_confirm_wrong_text(self, mocker):
        """Test confirm with wrong text clears input."""
        from glitchygames.ui.dialogs import DeleteFrameDialogScene

        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        confirm_callback = mocker.Mock()

        dialog = DeleteFrameDialogScene(
            previous_scene=mock_previous,
            animation_name='idle',
            frame_index=0,
            on_confirm_callback=confirm_callback,
            groups=mock_groups,
        )
        dialog.dialog.input_box.text = 'no'
        event = mocker.Mock()
        dialog.on_confirm_event(event)
        confirm_callback.assert_not_called()
        assert not dialog.dialog.input_box.text

    def test_delete_frame_cancel(self, mocker):
        """Test cancel event on delete frame dialog."""
        from glitchygames.ui.dialogs import DeleteFrameDialogScene

        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        cancel_callback = mocker.Mock()

        dialog = DeleteFrameDialogScene(
            previous_scene=mock_previous,
            animation_name='idle',
            frame_index=0,
            on_confirm_callback=mocker.Mock(),
            on_cancel_callback=cancel_callback,
            groups=mock_groups,
        )
        dialog.game_engine = mocker.Mock()  # type: ignore[unresolved-attribute]
        event = mocker.Mock()
        dialog.on_cancel_event(event)
        cancel_callback.assert_called_once()

    def test_delete_frame_key_down_active(self, mocker):
        """Test DeleteFrameDialogScene key down when input is active."""
        from glitchygames.ui.dialogs import DeleteFrameDialogScene

        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()

        dialog = DeleteFrameDialogScene(
            previous_scene=mock_previous,
            animation_name='idle',
            frame_index=0,
            on_confirm_callback=mocker.Mock(),
            groups=mock_groups,
        )

        dialog.dialog.on_key_down_event = mocker.Mock()
        dialog.dialog.input_box.active = True
        event = mocker.Mock()
        event.key = pygame.K_y
        dialog.on_key_down_event(event)
        dialog.dialog.on_key_down_event.assert_called_once_with(event)

    def test_delete_frame_key_up_active(self, mocker):
        """Test DeleteFrameDialogScene key up when input is active."""
        from glitchygames.ui.dialogs import DeleteFrameDialogScene

        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()

        dialog = DeleteFrameDialogScene(
            previous_scene=mock_previous,
            animation_name='idle',
            frame_index=0,
            on_confirm_callback=mocker.Mock(),
            groups=mock_groups,
        )

        dialog.dialog.on_key_up_event = mocker.Mock()
        dialog.dialog.input_box.active = True
        event = mocker.Mock()
        event.key = pygame.K_y
        dialog.on_key_up_event(event)
        dialog.dialog.on_key_up_event.assert_called_once_with(event)

    def test_delete_frame_key_up_tab_inactive(self, mocker):
        """Test DeleteFrameDialogScene key up with Tab when inactive."""
        from glitchygames.ui.dialogs import DeleteFrameDialogScene

        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()

        dialog = DeleteFrameDialogScene(
            previous_scene=mock_previous,
            animation_name='idle',
            frame_index=0,
            on_confirm_callback=mocker.Mock(),
            groups=mock_groups,
        )

        dialog.dialog.input_box.active = False
        tab_event = mocker.Mock()
        tab_event.key = pygame.K_TAB
        dialog.on_key_up_event(tab_event)
        assert dialog.dialog.input_box.active is True


# ============================================================================
# From test_dialogs_deeper_coverage.py
# ============================================================================


class TestNewCanvasDialogConfirm:
    """Test NewCanvasDialogScene.on_confirm_event."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_confirm_calls_on_new_file_event(self, mocker):
        """Test confirm event calls previous scene's on_new_file_event."""
        from glitchygames.ui.dialogs import NewCanvasDialogScene

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []

        dialog = NewCanvasDialogScene(
            previous_scene=mock_previous,
            groups=mock_groups,
        )
        dialog.dialog.input_box.text = '16x16'
        event = mocker.Mock()
        trigger = mocker.Mock()
        dialog.on_confirm_event(event, trigger)

        mock_previous.on_new_file_event.assert_called_once_with('16x16')


class TestLoadDialogConfirm:
    """Test LoadDialogScene.on_confirm_event."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_confirm_calls_on_load_file_event(self, mocker):
        """Test confirm event calls canvas on_load_file_event."""
        from glitchygames.ui.dialogs import LoadDialogScene

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []
        mock_previous.canvas = mocker.Mock()

        dialog = LoadDialogScene(
            previous_scene=mock_previous,
            groups=mock_groups,
        )
        dialog.dialog.input_box.text = 'test.toml'
        event = mocker.Mock()
        trigger = mocker.Mock()
        dialog.on_confirm_event(event, trigger)

        mock_previous.canvas.on_load_file_event.assert_called_once()
        # Should have been called with the processed path
        call_args = mock_previous.canvas.on_load_file_event.call_args[0][0]
        assert 'test.toml' in call_args

    def test_confirm_with_example_prefix(self, mocker):
        """Test confirm event processes example: prefix correctly."""
        from glitchygames.ui.dialogs import LoadDialogScene

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []
        mock_previous.canvas = mocker.Mock()

        dialog = LoadDialogScene(
            previous_scene=mock_previous,
            groups=mock_groups,
        )
        dialog.dialog.input_box.text = 'example:heart.toml'
        event = mocker.Mock()
        trigger = mocker.Mock()
        dialog.on_confirm_event(event, trigger)

        mock_previous.canvas.on_load_file_event.assert_called_once()
        call_args = mock_previous.canvas.on_load_file_event.call_args[0][0]
        assert 'heart.toml' in call_args
        assert 'examples' in call_args


class TestSaveDialogConfirm:
    """Test SaveDialogScene.on_confirm_event."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_confirm_calls_on_save_file_event(self, mocker):
        """Test confirm event calls canvas on_save_file_event."""
        from glitchygames.ui.dialogs import SaveDialogScene

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []
        mock_previous.canvas = mocker.Mock()

        dialog = SaveDialogScene(
            previous_scene=mock_previous,
            groups=mock_groups,
        )
        dialog.dialog.input_box.text = 'output.toml'
        event = mocker.Mock()
        trigger = mocker.Mock()
        dialog.on_confirm_event(event, trigger)

        mock_previous.canvas.on_save_file_event.assert_called_once()
        call_args = mock_previous.canvas.on_save_file_event.call_args[0][0]
        assert 'output.toml' in call_args

    def test_confirm_with_example_prefix(self, mocker):
        """Test confirm event processes example: prefix for save."""
        from glitchygames.ui.dialogs import SaveDialogScene

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []
        mock_previous.canvas = mocker.Mock()

        dialog = SaveDialogScene(
            previous_scene=mock_previous,
            groups=mock_groups,
        )
        dialog.dialog.input_box.text = 'example:star.toml'
        event = mocker.Mock()
        trigger = mocker.Mock()
        dialog.on_confirm_event(event, trigger)

        mock_previous.canvas.on_save_file_event.assert_called_once()
        call_args = mock_previous.canvas.on_save_file_event.call_args[0][0]
        assert 'star.toml' in call_args
        assert 'examples' in call_args


class TestDeleteAnimationDialogSetup:
    """Test DeleteAnimationDialogScene.setup method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_setup_configures_buttons_and_activates_input(self, mocker):
        """Test setup configures button callbacks and activates input box."""
        from glitchygames.ui.dialogs import DeleteAnimationDialogScene

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()

        dialog = DeleteAnimationDialogScene(
            previous_scene=mock_previous,
            animation_name='walk',
            on_confirm_callback=mocker.Mock(),
            groups=mock_groups,
        )
        dialog.setup()

        assert dialog.dialog.cancel_button.callbacks is not None
        assert 'on_left_mouse_button_up_event' in dialog.dialog.cancel_button.callbacks
        assert dialog.dialog.confirm_button.callbacks is not None
        assert 'on_left_mouse_button_up_event' in dialog.dialog.confirm_button.callbacks
        assert dialog.dialog.input_box.active is True

    def test_key_down_inactive_calls_super(self, mocker):
        """Test key down when input inactive delegates to super."""
        from glitchygames.ui.dialogs import DeleteAnimationDialogScene

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()

        dialog = DeleteAnimationDialogScene(
            previous_scene=mock_previous,
            animation_name='walk',
            on_confirm_callback=mocker.Mock(),
            groups=mock_groups,
        )
        dialog.dialog.input_box.active = False
        dialog.all_sprites = _RealLayeredDirty()
        event = mocker.Mock()
        event.key = pygame.K_a
        # Should call super, not raise
        dialog.on_key_down_event(event)

    def test_key_up_non_tab_inactive_calls_super(self, mocker):
        """Test key up with non-Tab key when inactive delegates to super."""
        from glitchygames.ui.dialogs import DeleteAnimationDialogScene

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()

        dialog = DeleteAnimationDialogScene(
            previous_scene=mock_previous,
            animation_name='walk',
            on_confirm_callback=mocker.Mock(),
            groups=mock_groups,
        )
        dialog.dialog.input_box.active = False
        dialog.all_sprites = _RealLayeredDirty()
        event = mocker.Mock()
        event.key = pygame.K_a
        # Should call super, not raise
        dialog.on_key_up_event(event)


class TestDeleteFrameDialogSetup:
    """Test DeleteFrameDialogScene.setup method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_setup_configures_buttons_and_activates_input(self, mocker):
        """Test setup configures button callbacks and activates input box."""
        from glitchygames.ui.dialogs import DeleteFrameDialogScene

        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()

        dialog = DeleteFrameDialogScene(
            previous_scene=mock_previous,
            animation_name='idle',
            frame_index=0,
            on_confirm_callback=mocker.Mock(),
            groups=mock_groups,
        )
        dialog.setup()

        assert dialog.dialog.cancel_button.callbacks is not None
        assert 'on_left_mouse_button_up_event' in dialog.dialog.cancel_button.callbacks
        assert dialog.dialog.confirm_button.callbacks is not None
        assert 'on_left_mouse_button_up_event' in dialog.dialog.confirm_button.callbacks
        assert dialog.dialog.input_box.active is True

    def test_cancel_without_callback(self, mocker):
        """Test cancel event without callback does not raise."""
        from glitchygames.ui.dialogs import DeleteFrameDialogScene

        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()

        dialog = DeleteFrameDialogScene(
            previous_scene=mock_previous,
            animation_name='idle',
            frame_index=0,
            on_confirm_callback=mocker.Mock(),
            on_cancel_callback=None,
            groups=mock_groups,
        )
        dialog.game_engine = mocker.Mock()  # type: ignore[unresolved-attribute]
        event = mocker.Mock()
        dialog.on_cancel_event(event)  # Should not raise

    def test_key_down_inactive_calls_super(self, mocker):
        """Test key down when input inactive delegates to super."""
        from glitchygames.ui.dialogs import DeleteFrameDialogScene

        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()

        dialog = DeleteFrameDialogScene(
            previous_scene=mock_previous,
            animation_name='idle',
            frame_index=0,
            on_confirm_callback=mocker.Mock(),
            groups=mock_groups,
        )
        dialog.dialog.input_box.active = False
        dialog.all_sprites = _RealLayeredDirty()
        event = mocker.Mock()
        event.key = pygame.K_a
        dialog.on_key_down_event(event)  # Should not raise

    def test_key_up_non_tab_inactive_calls_super(self, mocker):
        """Test key up with non-Tab key when inactive delegates to super."""
        from glitchygames.ui.dialogs import DeleteFrameDialogScene

        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()

        dialog = DeleteFrameDialogScene(
            previous_scene=mock_previous,
            animation_name='idle',
            frame_index=0,
            on_confirm_callback=mocker.Mock(),
            groups=mock_groups,
        )
        dialog.dialog.input_box.active = False
        dialog.all_sprites = _RealLayeredDirty()
        event = mocker.Mock()
        event.key = pygame.K_a
        dialog.on_key_up_event(event)  # Should not raise


class TestInputConfirmationDialogGroupsNone:
    """Test InputConfirmationDialogScene with groups=None (line 156)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_groups_none_creates_default_layered_dirty(self, mocker):
        """Test InputConfirmationDialogScene creates LayeredDirty when groups=None."""
        from glitchygames.ui.dialogs import InputConfirmationDialogScene

        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []

        dialog = InputConfirmationDialogScene(
            previous_scene=mock_previous,
            groups=None,
        )
        assert dialog.all_sprites is not None


class TestDismissWithPreviousSceneSprites:
    """Test dismiss() iterating previous_scene.all_sprites (line 226)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_dismiss_marks_previous_scene_sprites_dirty(self, mocker):
        """Test dismiss forces redraw on previous scene sprites."""
        from glitchygames.ui.dialogs import InputConfirmationDialogScene

        mock_sprite = mocker.Mock()
        mock_sprite.dirty = 0
        mock_previous = mocker.Mock()
        mock_previous.all_sprites = [mock_sprite]

        dialog = InputConfirmationDialogScene(
            previous_scene=mock_previous,
            groups=_RealLayeredDirty(),
        )
        dialog.dismiss()
        assert mock_sprite.dirty == 1


class TestBaseOnConfirmEventIsinstance:
    """Test InputConfirmationDialogScene.on_confirm_event isinstance branches (lines 242-254)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_base_confirm_event_no_subclass_match(self, mocker):
        """Test on_confirm_event on base class does not trigger subclass-specific code."""
        from glitchygames.ui.dialogs import InputConfirmationDialogScene

        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []

        dialog = InputConfirmationDialogScene(
            previous_scene=mock_previous,
            groups=_RealLayeredDirty(),
        )
        dialog.dialog.input_box.text = 'test.toml'
        event = mocker.Mock()
        trigger = mocker.Mock()
        # Should not raise; base class is not a subclass dialog type
        dialog.on_confirm_event(event, trigger)


class TestDialogKeyUpElseBranch:
    """Test InputConfirmationDialogScene.on_key_up_event else branch (line 289)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_key_up_non_tab_inactive_calls_super(self, mocker):
        """Test on_key_up_event with non-tab key when input is inactive calls super."""
        from glitchygames.ui.dialogs import InputConfirmationDialogScene

        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []

        dialog = InputConfirmationDialogScene(
            previous_scene=mock_previous,
            groups=_RealLayeredDirty(),
        )
        dialog.dialog.input_box.active = False
        dialog.all_sprites = _RealLayeredDirty()
        event = mocker.Mock()
        event.key = pygame.K_a  # Not TAB
        # Should call super().on_key_up_event, not raise
        dialog.on_key_up_event(event)


class TestDialogSubclassGroupsNone:
    """Test groups=None branches in dialog subclasses (lines 331, 380, 431, 482, 600)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_new_canvas_dialog_groups_none(self, mocker):
        """Test NewCanvasDialogScene creates LayeredDirty when groups=None (line 331)."""
        from glitchygames.ui.dialogs import NewCanvasDialogScene

        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []
        dialog = NewCanvasDialogScene(previous_scene=mock_previous, groups=None)
        assert dialog.all_sprites is not None

    def test_load_dialog_groups_none(self, mocker):
        """Test LoadDialogScene creates LayeredDirty when groups=None (line 380)."""
        from glitchygames.ui.dialogs import LoadDialogScene

        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []
        dialog = LoadDialogScene(previous_scene=mock_previous, groups=None)
        assert dialog.all_sprites is not None

    def test_save_dialog_groups_none(self, mocker):
        """Test SaveDialogScene creates LayeredDirty when groups=None (line 431)."""
        from glitchygames.ui.dialogs import SaveDialogScene

        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []
        dialog = SaveDialogScene(previous_scene=mock_previous, groups=None)
        assert dialog.all_sprites is not None

    def test_delete_animation_dialog_groups_none(self, mocker):
        """Test DeleteAnimationDialogScene creates LayeredDirty when groups=None (line 482)."""
        from glitchygames.ui.dialogs import DeleteAnimationDialogScene

        mock_previous = mocker.Mock()
        dialog = DeleteAnimationDialogScene(
            previous_scene=mock_previous,
            animation_name='walk',
            on_confirm_callback=mocker.Mock(),
            groups=None,
        )
        assert dialog.all_sprites is not None

    def test_delete_frame_dialog_groups_none(self, mocker):
        """Test DeleteFrameDialogScene creates LayeredDirty when groups=None (line 600)."""
        from glitchygames.ui.dialogs import DeleteFrameDialogScene

        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        mock_previous = mocker.Mock()
        dialog = DeleteFrameDialogScene(
            previous_scene=mock_previous,
            animation_name='idle',
            frame_index=0,
            on_confirm_callback=mocker.Mock(),
            groups=None,
        )
        assert dialog.all_sprites is not None


# ============================================================================
# From test_confirm_dialog_coverage.py
# ============================================================================


def _create_confirm_dialog(mocker, confirm_callback=None, cancel_callback=None):
    """Create a ConfirmDialog with standard test configuration.

    Returns:
        A ConfirmDialog instance configured for testing.
    """
    groups = mocker.Mock()
    return ConfirmDialog(
        text='Are you sure?',
        confirm_callback=confirm_callback,
        cancel_callback=cancel_callback,
        x=TEST_CONFIRM_DIALOG_X,
        y=TEST_CONFIRM_DIALOG_Y,
        width=TEST_CONFIRM_DIALOG_WIDTH,
        height=TEST_CONFIRM_DIALOG_HEIGHT,
        groups=groups,
    )


class TestConfirmDialogInitialization:
    """Test ConfirmDialog initialization and button positioning."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_dialog_stores_text(self, mocker):
        """Test dialog stores the confirmation text."""
        dialog = _create_confirm_dialog(mocker)
        assert dialog.text == 'Are you sure?'

    def test_dialog_stores_callbacks(self, mocker):
        """Test dialog stores confirm and cancel callbacks."""
        confirm_callback = mocker.Mock()
        cancel_callback = mocker.Mock()

        dialog = _create_confirm_dialog(
            mocker, confirm_callback=confirm_callback, cancel_callback=cancel_callback
        )

        assert dialog.confirm_callback is confirm_callback
        assert dialog.cancel_callback is cancel_callback

    def test_yes_button_rect_is_positioned(self, mocker):
        """Test yes button rect has correct dimensions."""
        dialog = _create_confirm_dialog(mocker)

        assert dialog.yes_button_rect.width == CONFIRM_BUTTON_WIDTH
        assert dialog.yes_button_rect.height == CONFIRM_BUTTON_HEIGHT

    def test_no_button_rect_is_positioned(self, mocker):
        """Test no button rect has correct dimensions."""
        dialog = _create_confirm_dialog(mocker)

        assert dialog.no_button_rect.width == CONFIRM_BUTTON_WIDTH
        assert dialog.no_button_rect.height == CONFIRM_BUTTON_HEIGHT

    def test_buttons_are_centered(self, mocker):
        """Test buttons are horizontally centered within dialog."""
        dialog = _create_confirm_dialog(mocker)

        total_button_width = (CONFIRM_BUTTON_WIDTH * 2) + BUTTON_SPACING
        expected_start_x = (TEST_CONFIRM_DIALOG_WIDTH - total_button_width) // 2

        assert dialog.yes_button_rect.x == expected_start_x
        assert dialog.no_button_rect.x == expected_start_x + CONFIRM_BUTTON_WIDTH + BUTTON_SPACING

    def test_buttons_vertical_position(self, mocker):
        """Test buttons are positioned near the bottom of the dialog."""
        dialog = _create_confirm_dialog(mocker)

        expected_button_y = TEST_CONFIRM_DIALOG_HEIGHT - CONFIRM_BUTTON_HEIGHT - 10

        assert dialog.yes_button_rect.y == expected_button_y
        assert dialog.no_button_rect.y == expected_button_y

    def test_initial_hover_is_none(self, mocker):
        """Test hover_button is initially None."""
        dialog = _create_confirm_dialog(mocker)
        assert dialog.hover_button is None

    def test_initial_dirty_is_2(self, mocker):
        """Test dirty flag is initially 2 (continuous updates)."""
        dialog = _create_confirm_dialog(mocker)
        assert dialog.dirty == 2


class TestConfirmDialogRender:
    """Test ConfirmDialog.render() drawing."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_fills_background(self, mocker):
        """Test render fills the image with dark gray."""
        dialog = _create_confirm_dialog(mocker)

        # dialog.image must return ints for get_width/get_height and a real Rect
        dialog.image = mocker.Mock()
        dialog.image.get_width.return_value = TEST_CONFIRM_DIALOG_WIDTH
        dialog.image.get_height.return_value = TEST_CONFIRM_DIALOG_HEIGHT
        dialog.image.get_rect.return_value = pygame.Rect(
            0, 0, TEST_CONFIRM_DIALOG_WIDTH, TEST_CONFIRM_DIALOG_HEIGHT
        )

        mocker.patch('pygame.draw.rect')

        # Mock the font render to return a surface with get_rect
        mock_font = mocker.Mock()
        mock_surface = mocker.Mock()
        mock_rect = pygame.Rect(0, 0, 50, 14)
        mock_surface.get_rect.return_value = mock_rect
        mock_font.render.return_value = (mock_surface, mock_rect)
        mocker.patch('glitchygames.ui.widgets.FontManager.get_font', return_value=mock_font)

        dialog.render()

        dialog.image.fill.assert_called_once_with((40, 40, 40))

    def test_render_draws_border(self, mocker):
        """Test render draws a border rectangle."""
        dialog = _create_confirm_dialog(mocker)

        dialog.image = mocker.Mock()
        dialog.image.get_width.return_value = TEST_CONFIRM_DIALOG_WIDTH
        dialog.image.get_height.return_value = TEST_CONFIRM_DIALOG_HEIGHT
        dialog.image.get_rect.return_value = pygame.Rect(
            0, 0, TEST_CONFIRM_DIALOG_WIDTH, TEST_CONFIRM_DIALOG_HEIGHT
        )

        mock_draw_rect = mocker.patch('pygame.draw.rect')

        mock_font = mocker.Mock()
        mock_surface = mocker.Mock()
        mock_rect = pygame.Rect(0, 0, 50, 14)
        mock_surface.get_rect.return_value = mock_rect
        mock_font.render.return_value = (mock_surface, mock_rect)
        mocker.patch('glitchygames.ui.widgets.FontManager.get_font', return_value=mock_font)

        dialog.render()

        # Should have calls for border, yes button bg, yes button border,
        # no button bg, no button border
        assert mock_draw_rect.call_count >= 5

    def test_render_sets_dirty_to_zero(self, mocker):
        """Test render sets dirty to 0 after rendering."""
        dialog = _create_confirm_dialog(mocker)

        dialog.image = mocker.Mock()
        dialog.image.get_width.return_value = TEST_CONFIRM_DIALOG_WIDTH
        dialog.image.get_height.return_value = TEST_CONFIRM_DIALOG_HEIGHT
        dialog.image.get_rect.return_value = pygame.Rect(
            0, 0, TEST_CONFIRM_DIALOG_WIDTH, TEST_CONFIRM_DIALOG_HEIGHT
        )

        mocker.patch('pygame.draw.rect')

        mock_font = mocker.Mock()
        mock_surface = mocker.Mock()
        mock_rect = pygame.Rect(0, 0, 50, 14)
        mock_surface.get_rect.return_value = mock_rect
        mock_font.render.return_value = (mock_surface, mock_rect)
        mocker.patch('glitchygames.ui.widgets.FontManager.get_font', return_value=mock_font)

        dialog.render()

        assert dialog.dirty == 0

    def test_render_hover_yes_changes_color(self, mocker):
        """Test render uses highlight color when yes button is hovered."""
        dialog = _create_confirm_dialog(mocker)
        dialog.hover_button = 'yes'

        dialog.image = mocker.Mock()
        dialog.image.get_width.return_value = TEST_CONFIRM_DIALOG_WIDTH
        dialog.image.get_height.return_value = TEST_CONFIRM_DIALOG_HEIGHT
        dialog.image.get_rect.return_value = pygame.Rect(
            0, 0, TEST_CONFIRM_DIALOG_WIDTH, TEST_CONFIRM_DIALOG_HEIGHT
        )

        mock_draw_rect = mocker.patch('pygame.draw.rect')

        mock_font = mocker.Mock()
        mock_surface = mocker.Mock()
        mock_rect = pygame.Rect(0, 0, 50, 14)
        mock_surface.get_rect.return_value = mock_rect
        mock_font.render.return_value = (mock_surface, mock_rect)
        mocker.patch('glitchygames.ui.widgets.FontManager.get_font', return_value=mock_font)

        dialog.render()

        # Verify Yes button was drawn with highlight color (60, 120, 60)
        draw_calls = mock_draw_rect.call_args_list
        yes_button_colors = [call.args[1] for call in draw_calls if len(call.args) >= 2]
        assert (60, 120, 60) in yes_button_colors


class TestConfirmDialogHandleMouseDown:
    """Test ConfirmDialog.handle_mouse_down()."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_click_yes_invokes_confirm_callback(self, mocker):
        """Test clicking Yes button invokes confirm_callback."""
        confirm_callback = mocker.Mock()
        dialog = _create_confirm_dialog(mocker, confirm_callback=confirm_callback)

        mock_kill = mocker.patch.object(dialog, 'kill')

        click_pos = (dialog.yes_button_rect.centerx, dialog.yes_button_rect.centery)
        result = dialog.handle_mouse_down(click_pos)

        assert result is True
        confirm_callback.assert_called_once()
        mock_kill.assert_called_once()

    def test_click_no_invokes_cancel_callback(self, mocker):
        """Test clicking No button invokes cancel_callback."""
        cancel_callback = mocker.Mock()
        dialog = _create_confirm_dialog(mocker, cancel_callback=cancel_callback)

        mock_kill = mocker.patch.object(dialog, 'kill')

        click_pos = (dialog.no_button_rect.centerx, dialog.no_button_rect.centery)
        result = dialog.handle_mouse_down(click_pos)

        assert result is True
        cancel_callback.assert_called_once()
        mock_kill.assert_called_once()

    def test_click_yes_without_callback(self, mocker):
        """Test clicking Yes without callback still kills dialog."""
        dialog = _create_confirm_dialog(mocker, confirm_callback=None)
        mock_kill = mocker.patch.object(dialog, 'kill')

        click_pos = (dialog.yes_button_rect.centerx, dialog.yes_button_rect.centery)
        result = dialog.handle_mouse_down(click_pos)

        assert result is True
        mock_kill.assert_called_once()

    def test_click_no_without_callback(self, mocker):
        """Test clicking No without callback still kills dialog."""
        dialog = _create_confirm_dialog(mocker, cancel_callback=None)
        mock_kill = mocker.patch.object(dialog, 'kill')

        click_pos = (dialog.no_button_rect.centerx, dialog.no_button_rect.centery)
        result = dialog.handle_mouse_down(click_pos)

        assert result is True
        mock_kill.assert_called_once()

    def test_click_outside_buttons_returns_false(self, mocker):
        """Test clicking outside both buttons returns False."""
        dialog = _create_confirm_dialog(mocker)

        # Click in the middle of the dialog, above the buttons
        click_pos = (TEST_CONFIRM_DIALOG_WIDTH // 2, 10)
        result = dialog.handle_mouse_down(click_pos)

        assert result is False

    def test_click_yes_removes_dialog(self, mocker):
        """Test clicking Yes calls kill() to remove dialog from groups."""
        confirm_callback = mocker.Mock()
        dialog = _create_confirm_dialog(mocker, confirm_callback=confirm_callback)

        mock_kill = mocker.patch.object(dialog, 'kill')

        click_pos = (dialog.yes_button_rect.centerx, dialog.yes_button_rect.centery)
        dialog.handle_mouse_down(click_pos)

        mock_kill.assert_called_once()


class TestConfirmDialogUpdate:
    """Test ConfirmDialog.update() hover tracking."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_detects_yes_hover(self, mocker):
        """Test update detects mouse hovering over Yes button."""
        dialog = _create_confirm_dialog(mocker)

        # Mock mouse position over yes button (relative to dialog)
        assert dialog.rect is not None
        yes_center_x = dialog.yes_button_rect.centerx + dialog.rect.x
        yes_center_y = dialog.yes_button_rect.centery + dialog.rect.y
        mocker.patch.object(pygame.mouse, 'get_pos', return_value=(yes_center_x, yes_center_y))

        # Mock render to avoid full rendering
        mocker.patch.object(dialog, 'render')

        dialog.update()

        assert dialog.hover_button == 'yes'

    def test_update_detects_no_hover(self, mocker):
        """Test update detects mouse hovering over No button."""
        dialog = _create_confirm_dialog(mocker)

        assert dialog.rect is not None
        no_center_x = dialog.no_button_rect.centerx + dialog.rect.x
        no_center_y = dialog.no_button_rect.centery + dialog.rect.y
        mocker.patch.object(pygame.mouse, 'get_pos', return_value=(no_center_x, no_center_y))

        mocker.patch.object(dialog, 'render')

        dialog.update()

        assert dialog.hover_button == 'no'

    def test_update_clears_hover_when_outside(self, mocker):
        """Test update clears hover when mouse is outside buttons."""
        dialog = _create_confirm_dialog(mocker)
        dialog.hover_button = 'yes'

        # Mouse far from both buttons
        mocker.patch.object(pygame.mouse, 'get_pos', return_value=(0, 0))

        mocker.patch.object(dialog, 'render')

        dialog.update()

        assert dialog.hover_button is None

    def test_update_calls_render_when_dirty(self, mocker):
        """Test update calls render when dialog is dirty."""
        dialog = _create_confirm_dialog(mocker)
        dialog.dirty = 2

        mocker.patch.object(pygame.mouse, 'get_pos', return_value=(0, 0))
        mock_render = mocker.patch.object(dialog, 'render')

        dialog.update()

        mock_render.assert_called_once()


# ============================================================================
# From test_input_dialog_coverage.py
# ============================================================================


def _create_input_dialog(mocker, parent=None):
    """Create an InputDialog with standard test configuration.

    Returns:
        An InputDialog instance configured for testing.
    """
    groups = mocker.Mock()
    return InputDialog(
        x=TEST_INPUT_DIALOG_X,
        y=TEST_INPUT_DIALOG_Y,
        width=TEST_INPUT_DIALOG_WIDTH,
        height=TEST_INPUT_DIALOG_HEIGHT,
        name='test_input_dialog',
        dialog_text='Enter a value:',
        confirm_text='OK',
        cancel_text='Cancel',
        parent=parent,
        groups=groups,
    )


class TestInputDialogUpdate:
    """Test InputDialog.update() rendering."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_fills_background(self, mocker):
        """Test that update fills the image with black background."""
        dialog = _create_input_dialog(mocker)
        assert dialog.image is not None
        mock_fill = mocker.patch.object(dialog.image, 'fill')
        mock_blit = mocker.patch.object(dialog.image, 'blit')
        mocker.patch('pygame.draw.rect')

        dialog.update()

        mock_fill.assert_called_once_with((0, 0, 0))

    def test_update_draws_border(self, mocker):
        """Test that update draws a gray border rectangle."""
        dialog = _create_input_dialog(mocker)
        assert dialog.image is not None
        mocker.patch.object(dialog.image, 'fill')
        mocker.patch.object(dialog.image, 'blit')
        mock_draw_rect = mocker.patch('pygame.draw.rect')

        dialog.update()

        mock_draw_rect.assert_called_once()

    def test_update_blits_all_components(self, mocker):
        """Test that update blits all nested components to the image."""
        dialog = _create_input_dialog(mocker)
        assert dialog.image is not None
        mocker.patch.object(dialog.image, 'fill')
        mock_blit = mocker.patch.object(dialog.image, 'blit')
        mocker.patch('pygame.draw.rect')

        dialog.update()

        # Should blit dialog_text_sprite, cancel_button, confirm_button, input_box
        assert mock_blit.call_count == 4

    def test_update_marks_components_dirty(self, mocker):
        """Test that update sets dirty=1 on nested components."""
        dialog = _create_input_dialog(mocker)
        assert dialog.image is not None
        mocker.patch.object(dialog.image, 'fill')
        mocker.patch.object(dialog.image, 'blit')
        mocker.patch('pygame.draw.rect')

        dialog.update()

        assert dialog.dialog_text_sprite.dirty == 1
        assert dialog.cancel_button.dirty == 1
        assert dialog.confirm_button.dirty == 1


class TestInputDialogConfirmEvent:
    """Test InputDialog.on_confirm_event()."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_confirm_event_delegates_to_parent(self, mocker):
        """Test on_confirm_event delegates to parent when parent exists."""
        parent = mocker.Mock()
        dialog = _create_input_dialog(mocker, parent=parent)

        event = mocker.Mock()
        trigger = mocker.Mock()

        dialog.on_confirm_event(event=event, trigger=trigger)

        parent.on_confirm_event.assert_called_once_with(event=event, trigger=trigger)

    def test_confirm_event_without_parent(self, mocker):
        """Test on_confirm_event does not raise when no parent."""
        dialog = _create_input_dialog(mocker, parent=None)

        event = mocker.Mock()
        trigger = mocker.Mock()

        # Should not raise
        dialog.on_confirm_event(event=event, trigger=trigger)


class TestInputDialogCancelEvent:
    """Test InputDialog.on_cancel_event()."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_cancel_event_delegates_to_parent(self, mocker):
        """Test on_cancel_event delegates to parent when parent exists."""
        parent = mocker.Mock()
        dialog = _create_input_dialog(mocker, parent=parent)

        event = mocker.Mock()
        trigger = mocker.Mock()

        dialog.on_cancel_event(event=event, trigger=trigger)

        parent.on_cancel_event.assert_called_once_with(event=event, trigger=trigger)

    def test_cancel_event_without_parent(self, mocker):
        """Test on_cancel_event does not raise when no parent."""
        dialog = _create_input_dialog(mocker, parent=None)

        event = mocker.Mock()
        trigger = mocker.Mock()

        # Should not raise
        dialog.on_cancel_event(event=event, trigger=trigger)


class TestInputDialogInputBoxSubmitEvent:
    """Test InputDialog.on_input_box_submit_event()."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_input_box_submit_calls_confirm_event(self, mocker):
        """Test on_input_box_submit_event calls on_confirm_event."""
        parent = mocker.Mock()
        dialog = _create_input_dialog(mocker, parent=parent)

        event = mocker.Mock()
        event.name = 'test_input'
        event.text = 'hello world'

        dialog.on_input_box_submit_event(event=event)

        parent.on_confirm_event.assert_called_once_with(event=event, trigger=event)


class TestInputDialogInputBoxCancelEvent:
    """Test InputDialog.on_input_box_cancel_event()."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_input_box_cancel_calls_cancel_event(self, mocker):
        """Test on_input_box_cancel_event calls on_cancel_event."""
        parent = mocker.Mock()
        dialog = _create_input_dialog(mocker, parent=parent)

        control = mocker.Mock()
        control.name = 'test_input'
        control.text = 'hello world'

        dialog.on_input_box_cancel_event(control=control)

        parent.on_cancel_event.assert_called_once_with(event=control, trigger=control)


class TestInputDialogMouseButtonUpEvent:
    """Test InputDialog.on_mouse_button_up_event()."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_click_within_input_box_activates(self, mocker):
        """Test clicking within input box bounds activates it."""
        dialog = _create_input_dialog(mocker)

        # Position within the input box rect
        assert dialog.input_box.rect is not None
        input_box_center_x = dialog.input_box.rect.centerx
        input_box_center_y = dialog.input_box.rect.centery

        event = mocker.Mock()
        event.pos = (input_box_center_x, input_box_center_y)

        dialog.on_mouse_button_up_event(event)

        assert dialog.input_box.active is True

    def test_click_outside_input_box_deactivates(self, mocker):
        """Test clicking outside input box bounds deactivates it."""
        dialog = _create_input_dialog(mocker)
        dialog.input_box.activate()

        event = mocker.Mock()
        # Position far outside the input box
        event.pos = (0, 0)

        dialog.on_mouse_button_up_event(event)

        assert dialog.input_box.active is False


class TestInputDialogKeyUpEvent:
    """Test InputDialog.on_key_up_event()."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_key_up_routes_to_active_input_box(self, mocker):
        """Test key up routes to input box when active."""
        dialog = _create_input_dialog(mocker)
        dialog.input_box.active = True

        mock_input_box_key_up = mocker.patch.object(dialog.input_box, 'on_key_up_event')

        event = mocker.Mock()
        event.key = pygame.K_a

        dialog.on_key_up_event(event)

        mock_input_box_key_up.assert_called_once_with(event)

    def test_key_up_tab_activates_input_box(self, mocker):
        """Test Tab key activates the input box when it is inactive."""
        dialog = _create_input_dialog(mocker)
        dialog.input_box.active = False

        event = mocker.Mock()
        event.key = pygame.K_TAB

        dialog.on_key_up_event(event)

        assert dialog.input_box.active is True

    def test_key_up_non_tab_when_inactive_calls_super(self, mocker):
        """Test non-Tab key when input box is inactive calls super handler."""
        dialog = _create_input_dialog(mocker)
        dialog.input_box.active = False

        event = mocker.Mock()
        event.key = pygame.K_ESCAPE

        # Should not raise - calls super's on_key_up_event
        dialog.on_key_up_event(event)


class TestInputDialogKeyDownEvent:
    """Test InputDialog.on_key_down_event()."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_key_down_tab_activates_input_box(self, mocker):
        """Test Tab key activates the input box."""
        dialog = _create_input_dialog(mocker)
        dialog.input_box.active = False

        event = mocker.Mock()
        event.key = pygame.K_TAB

        dialog.on_key_down_event(event)

        assert dialog.input_box.active is True

    def test_key_down_routes_to_input_box(self, mocker):
        """Test non-Tab key routes to input box on_key_down_event."""
        dialog = _create_input_dialog(mocker)

        mock_input_box_key_down = mocker.patch.object(dialog.input_box, 'on_key_down_event')

        event = mocker.Mock()
        event.key = pygame.K_a

        dialog.on_key_down_event(event)

        mock_input_box_key_down.assert_called_once_with(event)


class TestInputDialogUpdateNestedSprites:
    """Test InputDialog.update_nested_sprites()."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_nested_sprites_syncs_dirty(self, mocker):
        """Test update_nested_sprites syncs dirty flag to buttons."""
        dialog = _create_input_dialog(mocker)
        dialog.dirty = 2

        dialog.update_nested_sprites()

        assert dialog.cancel_button.dirty == 2
        assert dialog.confirm_button.dirty == 2
