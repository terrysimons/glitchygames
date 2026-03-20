"""Coverage tests for glitchygames/ui/dialogs.py.

This module targets uncovered areas of the dialogs module including:
- _process_example_filename helper function
- _get_examples_dir helper function
- _get_save_path and _get_load_path helper functions
- Dialog scene lifecycle methods (setup, cleanup, dismiss)
- DeleteAnimationDialogScene and DeleteFrameDialogScene
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Save REAL LayeredDirty before mock_pygame_patches replaces it with a Mock.
_RealLayeredDirty = pygame.sprite.LayeredDirty

from glitchygames.ui.dialogs import (  # noqa: E402
    _get_examples_dir,
    _get_load_path,
    _get_save_path,
    _process_example_filename,
)
from tests.mocks import MockFactory  # noqa: E402


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
        from glitchygames.ui.dialogs import InputConfirmationDialogScene

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
        from glitchygames.ui.dialogs import InputConfirmationDialogScene

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []

        scene = InputConfirmationDialogScene(previous_scene=mock_previous, groups=mock_groups)
        scene.cleanup()

        assert scene.next_scene is scene

    def test_input_confirmation_dialog_dismiss(self, mocker):
        """Test InputConfirmationDialogScene dismiss returns to previous scene."""
        from glitchygames.ui.dialogs import InputConfirmationDialogScene

        mock_groups = _RealLayeredDirty()
        mock_previous = mocker.Mock()
        mock_previous.all_sprites = []

        scene = InputConfirmationDialogScene(previous_scene=mock_previous, groups=mock_groups)
        scene.dismiss()

        assert scene.next_scene is mock_previous
        assert mock_previous.next_scene is mock_previous

    def test_input_confirmation_dialog_cancel_event(self, mocker):
        """Test InputConfirmationDialogScene on_cancel_event dismisses dialog."""
        from glitchygames.ui.dialogs import InputConfirmationDialogScene

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
        from glitchygames.ui.dialogs import InputConfirmationDialogScene

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
        from glitchygames.ui.dialogs import InputConfirmationDialogScene

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
        from glitchygames.ui.dialogs import InputConfirmationDialogScene

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
        from glitchygames.ui.dialogs import InputConfirmationDialogScene

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
        from glitchygames.ui.dialogs import InputConfirmationDialogScene

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
        from glitchygames.ui.dialogs import InputConfirmationDialogScene

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
