"""Test suite for InputDialog coverage.

This module tests InputDialog event handling including update rendering,
confirm/cancel events, input box submit/cancel, mouse button routing,
and key event routing.
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.ui import InputDialog
from tests.mocks.test_mock_factory import MockFactory

# Test constants
TEST_DIALOG_X = 100
TEST_DIALOG_Y = 100
TEST_DIALOG_WIDTH = 400
TEST_DIALOG_HEIGHT = 200


def _create_input_dialog(mocker, parent=None):
    """Create an InputDialog with standard test configuration.

    Returns:
        An InputDialog instance configured for testing.
    """
    groups = mocker.Mock()
    return InputDialog(
        x=TEST_DIALOG_X,
        y=TEST_DIALOG_Y,
        width=TEST_DIALOG_WIDTH,
        height=TEST_DIALOG_HEIGHT,
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
        mock_fill = mocker.patch.object(dialog.image, 'fill')
        mock_blit = mocker.patch.object(dialog.image, 'blit')
        mocker.patch('pygame.draw.rect')

        dialog.update()

        mock_fill.assert_called_once_with((0, 0, 0))

    def test_update_draws_border(self, mocker):
        """Test that update draws a gray border rectangle."""
        dialog = _create_input_dialog(mocker)
        mocker.patch.object(dialog.image, 'fill')
        mocker.patch.object(dialog.image, 'blit')
        mock_draw_rect = mocker.patch('pygame.draw.rect')

        dialog.update()

        mock_draw_rect.assert_called_once()

    def test_update_blits_all_components(self, mocker):
        """Test that update blits all nested components to the image."""
        dialog = _create_input_dialog(mocker)
        mocker.patch.object(dialog.image, 'fill')
        mock_blit = mocker.patch.object(dialog.image, 'blit')
        mocker.patch('pygame.draw.rect')

        dialog.update()

        # Should blit dialog_text_sprite, cancel_button, confirm_button, input_box
        assert mock_blit.call_count == 4

    def test_update_marks_components_dirty(self, mocker):
        """Test that update sets dirty=1 on nested components."""
        dialog = _create_input_dialog(mocker)
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
