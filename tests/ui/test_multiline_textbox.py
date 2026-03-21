"""Test suite for MultiLineTextBox coverage.

This module tests MultiLineTextBox key handling, activation/deactivation,
mouse wheel scrolling, and regular key input including backspace, delete,
and navigation.
"""

import sys
from pathlib import Path
from typing import Any

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.ui import MultiLineTextBox
from tests.mocks.test_mock_factory import MockFactory


def _key_mock() -> Any:
    """Return the pygame.key mock for attribute access.

    mock_pygame_patches replaces pygame.key with a Mock, but basedpyright
    sees the real module type. This helper provides proper typing.
    """
    return pygame.key


# Test constants
TEST_TEXTBOX_X = 10
TEST_TEXTBOX_Y = 20
TEST_TEXTBOX_WIDTH = 300
TEST_TEXTBOX_HEIGHT = 200


def _create_multiline_textbox(mocker, text=''):
    """Create a MultiLineTextBox with standard test configuration.

    Returns:
        A MultiLineTextBox instance configured for testing.
    """
    groups = mocker.Mock()
    textbox = MultiLineTextBox(
        x=TEST_TEXTBOX_X,
        y=TEST_TEXTBOX_Y,
        width=TEST_TEXTBOX_WIDTH,
        height=TEST_TEXTBOX_HEIGHT,
        name='test_textbox',
        text=text,
        groups=groups,
    )
    # Patch _get_text_width to return a sensible int so comparisons work
    mocker.patch.object(textbox, '_get_text_width', return_value=10)
    return textbox


def _make_key_event(mocker, key, unicode_char='', mods=0):
    """Create a mock key event.

    Returns:
        A mock event with key, unicode, and mod attributes.
    """
    event = mocker.Mock()
    event.key = key
    event.unicode = unicode_char
    event.mod = mods
    return event


class TestMultiLineTextBoxKeyDownEscape:
    """Test on_key_down_event() with Escape key."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_escape_deactivates_textbox(self, mocker):
        """Test Escape key deactivates the textbox."""
        textbox = _create_multiline_textbox(mocker, text='hello')
        textbox.active = True

        event = _make_key_event(mocker, pygame.K_ESCAPE)
        _key_mock().get_mods.return_value = 0

        textbox.on_key_down_event(event)

        assert textbox.active is False
        assert textbox.dirty == 2

    def test_escape_does_nothing_when_inactive(self, mocker):
        """Test Escape does nothing when textbox is already inactive."""
        textbox = _create_multiline_textbox(mocker, text='hello')
        textbox.active = False

        event = _make_key_event(mocker, pygame.K_ESCAPE)

        textbox.on_key_down_event(event)

        assert textbox.active is False


class TestMultiLineTextBoxKeyDownCtrlD:
    """Test on_key_down_event() with Ctrl+D to clear."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_ctrl_d_clears_text(self, mocker):
        """Test Ctrl+D clears text contents."""
        textbox = _create_multiline_textbox(mocker, text='some text content')
        textbox.active = True

        event = _make_key_event(mocker, pygame.K_d)
        _key_mock().get_mods.return_value = pygame.KMOD_CTRL

        textbox.on_key_down_event(event)

        assert textbox.cursor_pos == 0
        assert textbox.selection_start is None
        assert textbox.selection_end is None
        assert textbox.dirty == 2


class TestMultiLineTextBoxKeyDownCtrlEnter:
    """Test on_key_down_event() with Ctrl+Enter for submission."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_ctrl_enter_submits_to_parent(self, mocker):
        """Test Ctrl+Enter calls parent.on_text_submit_event."""
        parent = mocker.Mock()
        parent.on_text_submit_event = mocker.Mock()

        groups = mocker.Mock()
        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH,
            height=TEST_TEXTBOX_HEIGHT,
            name='test_textbox',
            text='submitted text',
            parent=parent,
            groups=groups,
        )
        textbox.active = True

        event = _make_key_event(mocker, pygame.K_RETURN)
        _key_mock().get_mods.return_value = pygame.KMOD_CTRL
        textbox.on_key_down_event(event)

        parent.on_text_submit_event.assert_called_once()

    def test_ctrl_enter_without_parent_does_nothing(self, mocker):
        """Test Ctrl+Enter with no parent does not raise."""
        textbox = _create_multiline_textbox(mocker, text='hello')
        textbox.active = True
        textbox.parent = None

        event = _make_key_event(mocker, pygame.K_RETURN)
        _key_mock().get_mods.return_value = pygame.KMOD_CTRL

        # Should not raise
        textbox.on_key_down_event(event)


class TestMultiLineTextBoxActivateDeactivate:
    """Test activate() and deactivate() methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_activate_sets_active_and_starts_text_input(self, mocker):
        """Test activate() sets active=True and starts text input."""
        textbox = _create_multiline_textbox(mocker)

        textbox.activate()

        assert textbox.active is True
        _key_mock().start_text_input.assert_called()
        _key_mock().set_repeat.assert_called_with(200)

    def test_deactivate_clears_active_and_stops_text_input(self, mocker):
        """Test deactivate() sets active=False and stops text input."""
        textbox = _create_multiline_textbox(mocker)
        textbox.active = True

        textbox.deactivate()

        assert textbox.active is False
        _key_mock().stop_text_input.assert_called()
        _key_mock().set_repeat.assert_called_with()


class TestMultiLineTextBoxMouseWheel:
    """Test on_mouse_wheel_event() scrolling."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_wheel_scroll_up_decreases_offset(self, mocker):
        """Test scrolling up decreases scroll_offset."""
        textbox = _create_multiline_textbox(mocker, text='line1\nline2\nline3\n' * 20)
        textbox.scroll_offset = 10

        event = mocker.Mock()
        event.y = 1  # Scroll up
        event.button = None

        # Simulate mouse over the textbox by making collidepoint return True
        mocker.patch.object(textbox.rect, 'collidepoint', return_value=True)

        textbox.on_mouse_wheel_event(event)

        assert textbox.scroll_offset < 10

    def test_wheel_scroll_down_increases_offset(self, mocker):
        """Test scrolling down increases scroll_offset."""
        textbox = _create_multiline_textbox(mocker, text='line1\nline2\nline3\n' * 20)
        textbox.scroll_offset = 5

        event = mocker.Mock()
        event.y = -1  # Scroll down
        event.button = None

        # Simulate mouse over the textbox by making collidepoint return True
        mocker.patch.object(textbox.rect, 'collidepoint', return_value=True)

        textbox.on_mouse_wheel_event(event)

        assert textbox.scroll_offset > 5

    def test_wheel_clamps_offset_to_zero(self, mocker):
        """Test scrolling up does not go below 0."""
        textbox = _create_multiline_textbox(mocker, text='line1\nline2\nline3\n' * 20)
        textbox.scroll_offset = 1

        event = mocker.Mock()
        event.y = 10  # Large scroll up
        event.button = None

        # Simulate mouse over the textbox by making collidepoint return True
        mocker.patch.object(textbox.rect, 'collidepoint', return_value=True)

        textbox.on_mouse_wheel_event(event)

        assert textbox.scroll_offset >= 0

    def test_wheel_does_nothing_when_mouse_outside(self, mocker):
        """Test mouse wheel is ignored when mouse is outside the textbox."""
        textbox = _create_multiline_textbox(mocker, text='line1\nline2\nline3\n' * 20)
        textbox.scroll_offset = 10
        initial_offset = textbox.scroll_offset

        event = mocker.Mock()
        event.y = 1

        # Simulate mouse outside the textbox by making collidepoint return False
        mocker.patch.object(textbox.rect, 'collidepoint', return_value=False)

        textbox.on_mouse_wheel_event(event)

        assert textbox.scroll_offset == initial_offset

    def test_wheel_syncs_scrollbar(self, mocker):
        """Test mouse wheel scrolling syncs the scrollbar offset."""
        textbox = _create_multiline_textbox(mocker, text='line1\nline2\nline3\n' * 20)
        textbox.scroll_offset = 5

        event = mocker.Mock()
        event.y = -1
        event.button = None

        # Simulate mouse over the textbox by making collidepoint return True
        mocker.patch.object(textbox.rect, 'collidepoint', return_value=True)

        textbox.on_mouse_wheel_event(event)

        assert textbox.scrollbar.scroll_offset == textbox.scroll_offset


class TestMultiLineTextBoxRegularKeys:
    """Test _handle_regular_key() for text input, backspace, delete, navigation."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_typing_character_inserts_at_cursor(self, mocker):
        """Test typing a character inserts it at the cursor position."""
        textbox = _create_multiline_textbox(mocker, text='helo')
        textbox.active = True
        textbox.cursor_pos = 3

        event = _make_key_event(mocker, pygame.K_l, unicode_char='l')
        _key_mock().get_mods.return_value = 0

        textbox.on_key_down_event(event)

        assert textbox.cursor_pos == 4

    def test_backspace_removes_character_before_cursor(self, mocker):
        """Test backspace removes the character before the cursor."""
        textbox = _create_multiline_textbox(mocker, text='hello')
        textbox.active = True
        textbox.cursor_pos = 5

        event = _make_key_event(mocker, pygame.K_BACKSPACE)
        _key_mock().get_mods.return_value = 0

        textbox.on_key_down_event(event)

        assert textbox.cursor_pos == 4

    def test_backspace_at_position_zero_does_nothing(self, mocker):
        """Test backspace at position 0 does not change cursor."""
        textbox = _create_multiline_textbox(mocker, text='hello')
        textbox.active = True
        textbox.cursor_pos = 0

        event = _make_key_event(mocker, pygame.K_BACKSPACE)
        _key_mock().get_mods.return_value = 0

        textbox.on_key_down_event(event)

        assert textbox.cursor_pos == 0

    def test_delete_removes_character_at_cursor(self, mocker):
        """Test delete removes the character at the cursor position."""
        textbox = _create_multiline_textbox(mocker, text='hello')
        textbox.active = True
        textbox.cursor_pos = 0

        event = _make_key_event(mocker, pygame.K_DELETE)
        _key_mock().get_mods.return_value = 0

        textbox.on_key_down_event(event)

        assert textbox.cursor_pos == 0

    def test_left_arrow_moves_cursor_left(self, mocker):
        """Test left arrow moves cursor one position left."""
        textbox = _create_multiline_textbox(mocker, text='hello')
        textbox.active = True
        textbox.cursor_pos = 3

        event = _make_key_event(mocker, pygame.K_LEFT)
        _key_mock().get_mods.return_value = 0

        textbox.on_key_down_event(event)

        assert textbox.cursor_pos == 2

    def test_right_arrow_moves_cursor_right(self, mocker):
        """Test right arrow moves cursor one position right."""
        textbox = _create_multiline_textbox(mocker, text='hello')
        textbox.active = True
        textbox.cursor_pos = 2

        event = _make_key_event(mocker, pygame.K_RIGHT)
        _key_mock().get_mods.return_value = 0

        textbox.on_key_down_event(event)

        assert textbox.cursor_pos == 3

    def test_left_arrow_clamps_at_zero(self, mocker):
        """Test left arrow does not go below 0."""
        textbox = _create_multiline_textbox(mocker, text='hello')
        textbox.active = True
        textbox.cursor_pos = 0

        event = _make_key_event(mocker, pygame.K_LEFT)
        _key_mock().get_mods.return_value = 0

        textbox.on_key_down_event(event)

        assert textbox.cursor_pos == 0

    def test_right_arrow_clamps_at_text_length(self, mocker):
        """Test right arrow does not exceed text length."""
        textbox = _create_multiline_textbox(mocker, text='hello')
        textbox.active = True
        textbox.cursor_pos = 5

        event = _make_key_event(mocker, pygame.K_RIGHT)
        _key_mock().get_mods.return_value = 0

        textbox.on_key_down_event(event)

        assert textbox.cursor_pos == 5

    def test_enter_inserts_newline(self, mocker):
        """Test Enter key inserts a newline at cursor position."""
        textbox = _create_multiline_textbox(mocker, text='hello')
        textbox.active = True
        textbox.cursor_pos = 5

        event = _make_key_event(mocker, pygame.K_RETURN)
        _key_mock().get_mods.return_value = 0

        textbox.on_key_down_event(event)

        assert textbox.cursor_pos == 6

    def test_up_arrow_moves_cursor_up(self, mocker):
        """Test up arrow key moves cursor up one line."""
        textbox = _create_multiline_textbox(mocker, text='line1\nline2')
        textbox.active = True
        textbox.cursor_pos = 8  # Somewhere in line2

        event = _make_key_event(mocker, pygame.K_UP)
        _key_mock().get_mods.return_value = 0

        textbox.on_key_down_event(event)

        # Cursor should be on line1 now
        assert textbox.cursor_pos < 6

    def test_down_arrow_moves_cursor_down(self, mocker):
        """Test down arrow key moves cursor down one line."""
        textbox = _create_multiline_textbox(mocker, text='line1\nline2')
        textbox.active = True
        textbox.cursor_pos = 2  # In line1

        event = _make_key_event(mocker, pygame.K_DOWN)
        _key_mock().get_mods.return_value = 0

        textbox.on_key_down_event(event)

        # Cursor should be on line2 now
        assert textbox.cursor_pos >= 6


class TestMultiLineTextBoxClipboardOperations:
    """Test clipboard operations (copy, cut, paste)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_ctrl_a_selects_all(self, mocker):
        """Test Ctrl+A selects all text."""
        textbox = _create_multiline_textbox(mocker, text='hello world')
        textbox.active = True

        event = _make_key_event(mocker, pygame.K_a)
        _key_mock().get_mods.return_value = pygame.KMOD_CTRL
        mocker.patch('pygame.time.get_ticks', return_value=1000)

        textbox.on_key_down_event(event)

        assert textbox.selection_start == 0
        assert textbox.selection_end == len(textbox._original_text)
        assert textbox.cursor_pos == len(textbox._original_text)

    def test_ctrl_c_copies_text(self, mocker):
        """Test Ctrl+C copies text (does not raise even if pyperclip unavailable)."""
        textbox = _create_multiline_textbox(mocker, text='hello world')
        textbox.active = True

        event = _make_key_event(mocker, pygame.K_c)
        _key_mock().get_mods.return_value = pygame.KMOD_CTRL
        mocker.patch('pygame.time.get_ticks', return_value=1000)

        # Mock pyperclip in widgets module
        mocker.patch('glitchygames.ui.widgets.pyperclip', None)

        # Should not raise even without pyperclip
        textbox.on_key_down_event(event)

    def test_shift_arrow_selects_text(self, mocker):
        """Test Shift+Arrow selects text."""
        textbox = _create_multiline_textbox(mocker, text='hello')
        textbox.active = True
        textbox.cursor_pos = 2

        event = _make_key_event(mocker, pygame.K_RIGHT)
        _key_mock().get_mods.return_value = pygame.KMOD_SHIFT

        textbox.on_key_down_event(event)

        assert textbox.selection_start == 2
        assert textbox.selection_end == 3
        assert textbox.cursor_pos == 3


class TestMultiLineTextBoxMouseUpEvent:
    """Test on_mouse_up_event() activate/deactivate."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_mouse_up_inside_activates(self, mocker):
        """Test mouse up inside textbox activates it."""
        textbox = _create_multiline_textbox(mocker)

        assert textbox.rect is not None
        event = mocker.Mock()
        event.pos = (textbox.rect.centerx, textbox.rect.centery)

        # Simulate mouse inside the textbox by making collidepoint return True
        mocker.patch.object(textbox.rect, 'collidepoint', return_value=True)

        textbox.on_mouse_up_event(event)

        assert textbox.active is True

    def test_mouse_up_outside_deactivates(self, mocker):
        """Test mouse up outside textbox deactivates it."""
        textbox = _create_multiline_textbox(mocker)
        textbox.active = True

        event = mocker.Mock()
        event.pos = (-9999, -9999)

        # Simulate mouse outside the textbox by making collidepoint return False
        mocker.patch.object(textbox.rect, 'collidepoint', return_value=False)

        textbox.on_mouse_up_event(event)

        assert textbox.active is False
