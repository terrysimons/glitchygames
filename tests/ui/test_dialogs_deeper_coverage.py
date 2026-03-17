"""Deeper coverage tests for glitchygames/ui/dialogs.py.

Targets uncovered areas NOT covered by test_dialogs_coverage.py:
- InputConfirmationDialogScene.on_confirm_event for SaveDialogScene
- InputConfirmationDialogScene.on_confirm_event for LoadDialogScene
- InputConfirmationDialogScene.on_confirm_event for NewCanvasDialogScene
- InputConfirmationDialogScene.on_key_up_event with non-quit key (inactive input)
- NewCanvasDialogScene.on_confirm_event
- LoadDialogScene.on_confirm_event (with example: prefix)
- SaveDialogScene.on_confirm_event (with example: prefix)
- DeleteAnimationDialogScene.setup
- DeleteFrameDialogScene.setup
- DeleteFrameDialogScene.on_cancel_event without callback
- DeleteFrameDialogScene.on_key_down_event inactive input
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Save REAL LayeredDirty before mock_pygame_patches replaces it with a Mock.
_RealLayeredDirty = pygame.sprite.LayeredDirty

from tests.mocks import MockFactory  # noqa: E402


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
        dialog.game_engine = mocker.Mock()
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
