"""Test suite for ConfirmDialog coverage.

This module tests ConfirmDialog initialization, button positioning,
rendering, mouse down handling for Yes/No buttons, callback invocation,
and dialog removal via kill().
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.ui import ConfirmDialog
from tests.mocks.test_mock_factory import MockFactory

# Test constants
TEST_DIALOG_X = 50
TEST_DIALOG_Y = 50
TEST_DIALOG_WIDTH = 300
TEST_DIALOG_HEIGHT = 100
BUTTON_WIDTH = 80
BUTTON_HEIGHT = 30
BUTTON_SPACING = 20


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
        x=TEST_DIALOG_X,
        y=TEST_DIALOG_Y,
        width=TEST_DIALOG_WIDTH,
        height=TEST_DIALOG_HEIGHT,
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

        assert dialog.yes_button_rect.width == BUTTON_WIDTH
        assert dialog.yes_button_rect.height == BUTTON_HEIGHT

    def test_no_button_rect_is_positioned(self, mocker):
        """Test no button rect has correct dimensions."""
        dialog = _create_confirm_dialog(mocker)

        assert dialog.no_button_rect.width == BUTTON_WIDTH
        assert dialog.no_button_rect.height == BUTTON_HEIGHT

    def test_buttons_are_centered(self, mocker):
        """Test buttons are horizontally centered within dialog."""
        dialog = _create_confirm_dialog(mocker)

        total_button_width = (BUTTON_WIDTH * 2) + BUTTON_SPACING
        expected_start_x = (TEST_DIALOG_WIDTH - total_button_width) // 2

        assert dialog.yes_button_rect.x == expected_start_x
        assert dialog.no_button_rect.x == expected_start_x + BUTTON_WIDTH + BUTTON_SPACING

    def test_buttons_vertical_position(self, mocker):
        """Test buttons are positioned near the bottom of the dialog."""
        dialog = _create_confirm_dialog(mocker)

        expected_button_y = TEST_DIALOG_HEIGHT - BUTTON_HEIGHT - 10

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
        dialog.image.get_width.return_value = TEST_DIALOG_WIDTH
        dialog.image.get_height.return_value = TEST_DIALOG_HEIGHT
        dialog.image.get_rect.return_value = pygame.Rect(
            0, 0, TEST_DIALOG_WIDTH, TEST_DIALOG_HEIGHT
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
        dialog.image.get_width.return_value = TEST_DIALOG_WIDTH
        dialog.image.get_height.return_value = TEST_DIALOG_HEIGHT
        dialog.image.get_rect.return_value = pygame.Rect(
            0, 0, TEST_DIALOG_WIDTH, TEST_DIALOG_HEIGHT
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
        dialog.image.get_width.return_value = TEST_DIALOG_WIDTH
        dialog.image.get_height.return_value = TEST_DIALOG_HEIGHT
        dialog.image.get_rect.return_value = pygame.Rect(
            0, 0, TEST_DIALOG_WIDTH, TEST_DIALOG_HEIGHT
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
        dialog.image.get_width.return_value = TEST_DIALOG_WIDTH
        dialog.image.get_height.return_value = TEST_DIALOG_HEIGHT
        dialog.image.get_rect.return_value = pygame.Rect(
            0, 0, TEST_DIALOG_WIDTH, TEST_DIALOG_HEIGHT
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
        click_pos = (TEST_DIALOG_WIDTH // 2, 10)
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
