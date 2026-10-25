"""Test suite for MultiLineTextBox coverage.

This module tests MultiLineTextBox key handling, activation/deactivation,
mouse wheel scrolling, and regular key input including backspace, delete,
and navigation, on real surfaces with the real (FontManager) font and real events.
"""

import logging
import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.input.state import InputSnapshot, set_current_input
from glitchygames.ui import MultiLineTextBox

# Test constants
TEST_TEXTBOX_X = 10
TEST_TEXTBOX_Y = 20
TEST_TEXTBOX_WIDTH = 300
TEST_TEXTBOX_HEIGHT = 200

# Where the mouse is when a test says it is "outside" the text box
OUTSIDE_POSITION = (TEST_TEXTBOX_X + TEST_TEXTBOX_WIDTH + 50, TEST_TEXTBOX_Y + 10)


def _install_frame_input(*, modifiers=0, mouse_position=(0, 0)):
    """Make this frame's polled input (``current_input()``) hold modifiers and a mouse position.

    The text box reads held modifiers and the mouse from the frame's InputSnapshot, never from
    pygame. The autouse ``reset_engine_sources`` fixture (tests/harness.py) resets it after
    the test.
    """
    set_current_input(
        snapshot=InputSnapshot(
            pressed_scancodes=frozenset(),
            modifiers=modifiers,
            mouse_position=mouse_position,
            mouse_buttons=(False, False, False),
            mouse_focused=True,
        )
    )


@pytest.fixture(autouse=True)
def restore_key_repeat():
    """Put pygame's key repeat setting back after a test that activates a text box.

    Yields:
        None
    """
    delay, interval = pygame.key.get_repeat()
    yield
    pygame.key.set_repeat(delay, interval)
    pygame.key.stop_text_input()


def _create_multiline_textbox(text='', parent=None):
    """Create a MultiLineTextBox with standard test configuration in a real sprite group.

    Returns:
        A MultiLineTextBox instance configured for testing.
    """
    return MultiLineTextBox(
        x=TEST_TEXTBOX_X,
        y=TEST_TEXTBOX_Y,
        width=TEST_TEXTBOX_WIDTH,
        height=TEST_TEXTBOX_HEIGHT,
        name='test_textbox',
        text=text,
        parent=parent,
        groups=pygame.sprite.LayeredDirty(),
    )


def _make_key_event(key, unicode_char='', mods=0):
    """Create a real KEYDOWN event.

    Returns:
        pygame.event.Event: An event with key, unicode, and mod attributes.
    """
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode_char, mod=mods, scancode=0)


def _wheel_event(wheel_y):
    """Create a real MOUSEWHEEL event (positive y scrolls up).

    Returns:
        pygame.event.Event: The event.
    """
    return pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=wheel_y, flipped=False)


class TestMultiLineTextBoxKeyDownEscape:
    """Test on_key_down_event() with Escape key."""

    def test_escape_deactivates_textbox(self):
        """Test Escape key deactivates the textbox."""
        textbox = _create_multiline_textbox(text='hello')
        textbox.activate()
        textbox.dirty = 0
        _install_frame_input(modifiers=0)

        textbox.on_key_down_event(_make_key_event(pygame.K_ESCAPE))

        assert textbox.is_active is False
        assert textbox.dirty == 2
        assert pygame.key.get_repeat() == (0, 0)  # Key repeat is off again

    def test_escape_does_nothing_when_inactive(self):
        """Test Escape does nothing when textbox is already inactive."""
        textbox = _create_multiline_textbox(text='hello')
        textbox.is_active = False

        textbox.on_key_down_event(_make_key_event(pygame.K_ESCAPE))

        assert textbox.is_active is False
        assert textbox._original_text == 'hello'


class TestMultiLineTextBoxKeyDownCtrlD:
    """Test on_key_down_event() with Ctrl+D to clear."""

    def test_ctrl_d_clears_text(self):
        """Test Ctrl+D clears text contents."""
        textbox = _create_multiline_textbox(text='some text content')
        textbox.is_active = True
        _install_frame_input(modifiers=pygame.KMOD_CTRL)

        textbox.on_key_down_event(_make_key_event(pygame.K_d))

        assert not textbox._original_text
        assert textbox.cursor_pos == 0
        assert textbox.selection_start is None
        assert textbox.selection_end is None
        assert textbox.dirty == 2


class TestMultiLineTextBoxKeyDownCtrlEnter:
    """Test on_key_down_event() with Ctrl+Enter for submission."""

    def test_ctrl_enter_submits_to_parent(self, mocker):
        """Test Ctrl+Enter calls parent.on_text_submit_event with the text."""
        parent = mocker.Mock()
        textbox = _create_multiline_textbox(text='submitted text', parent=parent)
        textbox.is_active = True
        _install_frame_input(modifiers=pygame.KMOD_CTRL)

        textbox.on_key_down_event(_make_key_event(pygame.K_RETURN))

        parent.on_text_submit_event.assert_called_once_with('submitted text')
        # Ctrl+Enter submits: it does not type a newline
        assert textbox._original_text == 'submitted text'

    def test_ctrl_enter_without_parent_does_nothing(self):
        """Test Ctrl+Enter with no parent does not raise or change the text."""
        textbox = _create_multiline_textbox(text='hello')
        textbox.is_active = True
        textbox.parent = None
        _install_frame_input(modifiers=pygame.KMOD_CTRL)

        textbox.on_key_down_event(_make_key_event(pygame.K_RETURN))

        assert textbox._original_text == 'hello'


class TestMultiLineTextBoxActivateDeactivate:
    """Test activate() and deactivate() methods."""

    def test_activate_sets_active_and_starts_text_input(self, mocker):
        """Test activate() sets active=True, starts text input and turns on key repeat."""
        textbox = _create_multiline_textbox()
        # Whether SDL's text input is on cannot be read back: spy on the real call
        start_text_input = mocker.spy(pygame.key, 'start_text_input')

        textbox.activate()

        assert textbox.is_active is True
        start_text_input.assert_called_once_with()
        assert pygame.key.get_repeat() == (200, 200)

    def test_deactivate_clears_active_and_stops_text_input(self, mocker):
        """Test deactivate() sets active=False, stops text input and turns off key repeat."""
        textbox = _create_multiline_textbox()
        textbox.activate()
        stop_text_input = mocker.spy(pygame.key, 'stop_text_input')

        textbox.deactivate()

        assert textbox.is_active is False
        stop_text_input.assert_called_once_with()
        assert pygame.key.get_repeat() == (0, 0)


class TestMultiLineTextBoxMouseWheel:
    """Test on_mouse_wheel_event() scrolling."""

    @staticmethod
    def _scrollable_textbox(scroll_offset):
        textbox = _create_multiline_textbox(text='line1\nline2\nline3\n' * 20)
        textbox.scroll_offset = scroll_offset
        return textbox

    def test_wheel_scroll_up_decreases_offset(self):
        """Test scrolling up decreases scroll_offset by three lines."""
        textbox = self._scrollable_textbox(10)
        _install_frame_input(mouse_position=textbox.rect.center)

        textbox.on_mouse_wheel_event(_wheel_event(1))

        assert textbox.scroll_offset == 7

    def test_wheel_scroll_down_increases_offset(self):
        """Test scrolling down increases scroll_offset by three lines."""
        textbox = self._scrollable_textbox(5)
        _install_frame_input(mouse_position=textbox.rect.center)

        textbox.on_mouse_wheel_event(_wheel_event(-1))

        assert textbox.scroll_offset == 8

    def test_wheel_clamps_offset_to_zero(self):
        """Test scrolling up does not go below 0."""
        textbox = self._scrollable_textbox(1)
        _install_frame_input(mouse_position=textbox.rect.center)

        textbox.on_mouse_wheel_event(_wheel_event(10))

        assert textbox.scroll_offset == 0

    def test_wheel_does_nothing_when_mouse_outside(self):
        """Test mouse wheel is ignored when mouse is outside the textbox."""
        textbox = self._scrollable_textbox(10)
        assert not textbox.rect.collidepoint(OUTSIDE_POSITION)
        _install_frame_input(mouse_position=OUTSIDE_POSITION)

        textbox.on_mouse_wheel_event(_wheel_event(1))

        assert textbox.scroll_offset == 10

    def test_wheel_syncs_scrollbar(self):
        """Test mouse wheel scrolling syncs the scrollbar offset."""
        textbox = self._scrollable_textbox(5)
        _install_frame_input(mouse_position=textbox.rect.center)

        textbox.on_mouse_wheel_event(_wheel_event(-1))

        assert textbox.scrollbar.scroll_offset == textbox.scroll_offset


class TestMultiLineTextBoxRegularKeys:
    """Test _handle_regular_key() for text input, backspace, delete, navigation."""

    @staticmethod
    def _active_textbox(text, cursor_pos):
        textbox = _create_multiline_textbox(text=text)
        textbox.is_active = True
        textbox.cursor_pos = cursor_pos
        _install_frame_input(modifiers=0)
        return textbox

    def test_typing_character_inserts_at_cursor(self):
        """Test typing a character inserts it at the cursor position."""
        textbox = self._active_textbox('helo', 3)

        textbox.on_key_down_event(_make_key_event(pygame.K_l, unicode_char='l'))

        assert textbox._original_text == 'hello'
        assert textbox.cursor_pos == 4

    def test_backspace_removes_character_before_cursor(self):
        """Test backspace removes the character before the cursor."""
        textbox = self._active_textbox('hello', 5)

        textbox.on_key_down_event(_make_key_event(pygame.K_BACKSPACE))

        assert textbox._original_text == 'hell'
        assert textbox.cursor_pos == 4

    def test_backspace_at_position_zero_does_nothing(self):
        """Test backspace at position 0 does not change cursor or text."""
        textbox = self._active_textbox('hello', 0)

        textbox.on_key_down_event(_make_key_event(pygame.K_BACKSPACE))

        assert textbox._original_text == 'hello'
        assert textbox.cursor_pos == 0

    def test_delete_removes_character_at_cursor(self):
        """Test delete removes the character at the cursor position."""
        textbox = self._active_textbox('hello', 0)

        textbox.on_key_down_event(_make_key_event(pygame.K_DELETE))

        assert textbox._original_text == 'ello'
        assert textbox.cursor_pos == 0

    def test_left_arrow_moves_cursor_left(self):
        """Test left arrow moves cursor one position left."""
        textbox = self._active_textbox('hello', 3)

        textbox.on_key_down_event(_make_key_event(pygame.K_LEFT))

        assert textbox.cursor_pos == 2

    def test_right_arrow_moves_cursor_right(self):
        """Test right arrow moves cursor one position right."""
        textbox = self._active_textbox('hello', 2)

        textbox.on_key_down_event(_make_key_event(pygame.K_RIGHT))

        assert textbox.cursor_pos == 3

    def test_left_arrow_clamps_at_zero(self):
        """Test left arrow does not go below 0."""
        textbox = self._active_textbox('hello', 0)

        textbox.on_key_down_event(_make_key_event(pygame.K_LEFT))

        assert textbox.cursor_pos == 0

    def test_right_arrow_clamps_at_text_length(self):
        """Test right arrow does not exceed text length."""
        textbox = self._active_textbox('hello', 5)

        textbox.on_key_down_event(_make_key_event(pygame.K_RIGHT))

        assert textbox.cursor_pos == 5

    def test_enter_inserts_newline(self):
        """Test Enter key inserts a newline at cursor position."""
        textbox = self._active_textbox('hello', 5)

        textbox.on_key_down_event(_make_key_event(pygame.K_RETURN))

        assert textbox._original_text == 'hello\n'
        assert textbox.cursor_pos == 6

    def test_up_arrow_moves_cursor_up(self):
        """Test up arrow key moves cursor up one line, keeping its column."""
        textbox = self._active_textbox('line1\nline2', 8)  # Column 2 of line2

        textbox.on_key_down_event(_make_key_event(pygame.K_UP))

        # Cursor should be on line1 now
        assert textbox.cursor_pos == 2

    def test_down_arrow_moves_cursor_down(self):
        """Test down arrow key moves cursor down one line, keeping its column."""
        textbox = self._active_textbox('line1\nline2', 2)  # Column 2 of line1

        textbox.on_key_down_event(_make_key_event(pygame.K_DOWN))

        # Cursor should be on line2 now
        assert textbox.cursor_pos == 8


class TestMultiLineTextBoxClipboardOperations:
    """Test clipboard operations (copy, cut, paste); the real system clipboard is never used."""

    def test_ctrl_a_selects_all(self):
        """Test Ctrl+A selects all text."""
        textbox = _create_multiline_textbox(text='hello world')
        textbox.is_active = True
        _install_frame_input(modifiers=pygame.KMOD_CTRL)

        textbox.on_key_down_event(_make_key_event(pygame.K_a))

        assert textbox.selection_start == 0
        assert textbox.selection_end == len(textbox._original_text)
        assert textbox.cursor_pos == len(textbox._original_text)

    def test_ctrl_c_copies_text(self, in_process_clipboard):
        """Test Ctrl+C copies the text to the clipboard."""
        textbox = _create_multiline_textbox(text='hello world')
        textbox.is_active = True
        _install_frame_input(modifiers=pygame.KMOD_CTRL)

        textbox.on_key_down_event(_make_key_event(pygame.K_c))

        assert in_process_clipboard.text == 'hello world'
        assert textbox._original_text == 'hello world'

    def test_shift_arrow_selects_text(self):
        """Test Shift+Arrow selects text."""
        textbox = _create_multiline_textbox(text='hello')
        textbox.is_active = True
        textbox.cursor_pos = 2
        _install_frame_input(modifiers=pygame.KMOD_SHIFT)

        textbox.on_key_down_event(_make_key_event(pygame.K_RIGHT))

        assert textbox.selection_start == 2
        assert textbox.selection_end == 3
        assert textbox.cursor_pos == 3


class TestMultiLineTextBoxMouseUpEvent:
    """Test on_mouse_up_event() activate/deactivate."""

    def test_mouse_up_inside_activates(self):
        """Test mouse up inside textbox activates it."""
        textbox = _create_multiline_textbox()

        textbox.on_mouse_up_event(
            pygame.event.Event(pygame.MOUSEBUTTONUP, pos=textbox.rect.center, button=1)
        )

        assert textbox.is_active is True

    def test_mouse_up_outside_deactivates(self):
        """Test mouse up outside textbox deactivates it."""
        textbox = _create_multiline_textbox()
        textbox.is_active = True

        textbox.on_mouse_up_event(
            pygame.event.Event(pygame.MOUSEBUTTONUP, pos=OUTSIDE_POSITION, button=1)
        )

        assert textbox.is_active is False


BACKGROUND_RGB = (32, 32, 32)


def _real_textbox(text=''):
    """A MultiLineTextBox on real surfaces and the real font, in no group.

    Returns:
        The text box.
    """
    return MultiLineTextBox(
        x=TEST_TEXTBOX_X,
        y=TEST_TEXTBOX_Y,
        width=TEST_TEXTBOX_WIDTH,
        height=TEST_TEXTBOX_HEIGHT,
        name='real_textbox',
        text=text,
    )


def _has_text_pixels(surface, *, top, bottom):
    """Return whether any pixel in rows top..bottom-1 (x 5..59, inside the border) is bright text.

    Returns:
        True when a text pixel is found.
    """
    red_values = pygame.surfarray.pixels_red(surface)
    found = bool((red_values[5:60, top:bottom] > 128).any())
    del red_values
    return found


def _rgb_at(surface, position):
    """Return the RGB colour of one pixel (the alpha is not the point here).

    Returns:
        tuple: The (red, green, blue) colour.
    """
    return tuple(surface.get_at(position))[:3]


class TestMultiLineTextBoxRealRendering:
    """update() drawing on real surfaces."""

    def test_empty_text_draws_only_the_background_and_border(self):
        textbox = _real_textbox()

        textbox.update()

        assert not _has_text_pixels(textbox.image, top=2, bottom=TEST_TEXTBOX_HEIGHT - 2)
        # No scrollbar either: its column is background
        assert _rgb_at(textbox.image, (TEST_TEXTBOX_WIDTH - 6, 10)) == BACKGROUND_RGB

    def test_text_is_drawn(self):
        textbox = _real_textbox(text='Hello')

        textbox.update()

        assert _has_text_pixels(textbox.image, top=5, bottom=5 + textbox._get_line_height())

    def test_a_blank_line_is_skipped_but_keeps_its_height(self):
        textbox = _real_textbox(text='A\n\nB')
        line_height = textbox._get_line_height()

        textbox.update()

        assert _has_text_pixels(textbox.image, top=5, bottom=5 + line_height)
        assert not _has_text_pixels(textbox.image, top=5 + line_height, bottom=5 + 2 * line_height)
        assert _has_text_pixels(textbox.image, top=5 + 2 * line_height, bottom=5 + 3 * line_height)

    def test_cursor_blinks_off_after_the_blink_interval(self):
        textbox = _real_textbox(text='A')
        textbox.is_active = True
        textbox.cursor_visible = True
        textbox.cursor_blink_time -= textbox.cursor_blink_rate

        textbox.update()

        assert textbox.cursor_visible is False
        # The cursor would be drawn just after the text, from row 5 down
        line_height = textbox._get_line_height()
        cursor_x = textbox._get_text_width('A') + 5
        rgb_pixels = pygame.surfarray.pixels3d(textbox.image)
        cursor_column = rgb_pixels[cursor_x, 6 : 5 + line_height]
        assert (cursor_column == BACKGROUND_RGB).all()
        del cursor_column, rgb_pixels

    def test_the_frame_dump_is_not_logged_without_debug_logging(self, caplog):
        """update() runs every frame: with DEBUG off it draws but logs no frame dump."""
        textbox = _real_textbox(text='Hello')
        caplog.clear()  # only this update counts

        with caplog.at_level(logging.INFO, logger=textbox.log.name):
            textbox.update()

        assert _has_text_pixels(textbox.image, top=5, bottom=5 + textbox._get_line_height())
        assert '--- Frame' not in caplog.text
        assert 'Update called after' not in caplog.text

    def test_the_frame_dump_is_logged_with_debug_logging(self, caplog):
        """With DEBUG on, update() logs the frame number, time since the last update, state."""
        textbox = _real_textbox(text='Hello')

        with caplog.at_level(logging.DEBUG, logger=textbox.log.name):
            textbox.update()

        assert f'--- Frame {textbox._frame_count} ---' in caplog.text
        assert 'Update called after' in caplog.text
        assert 'State: active=False, cursor_visible=' in caplog.text
        assert 'Dirty flag:' in caplog.text


class TestMultiLineTextBoxRealEvents:
    """Event handling that leaves the text box unchanged."""

    def test_paste_from_an_empty_clipboard_changes_nothing(self):
        textbox = _real_textbox(text='keep')
        textbox.is_active = True
        _install_frame_input(modifiers=pygame.KMOD_CTRL)

        textbox.on_key_down_event(_make_key_event(pygame.K_v, unicode_char='\x16'))

        assert textbox._original_text == 'keep'

    def test_a_control_character_is_not_typed(self):
        textbox = _real_textbox(text='keep')
        textbox.is_active = True

        textbox.on_key_down_event(_make_key_event(pygame.K_F1, unicode_char='\x1b'))
        textbox.on_key_down_event(_make_key_event(pygame.K_LSHIFT, unicode_char=''))

        assert textbox._original_text == 'keep'
        assert textbox.cursor_pos == len('keep')

    def test_motion_keeps_the_hover_state_it_already_has(self):
        textbox = _real_textbox(text='keep')
        inside = textbox.rect.center
        outside = (textbox.rect.right + 50, textbox.rect.bottom + 50)

        textbox.is_hovered = True
        textbox.dirty = 0
        textbox.on_mouse_motion_event(
            pygame.event.Event(pygame.MOUSEMOTION, pos=inside, rel=(0, 0), buttons=(0, 0, 0))
        )
        assert textbox.is_hovered is True
        assert textbox.dirty == 0

        textbox.is_hovered = False
        textbox.on_mouse_motion_event(
            pygame.event.Event(pygame.MOUSEMOTION, pos=outside, rel=(0, 0), buttons=(0, 0, 0))
        )
        assert textbox.is_hovered is False
        assert textbox.dirty == 0

    @pytest.mark.parametrize(
        'wheel_event',
        [
            pytest.param(pygame.event.Event(pygame.MOUSEWHEEL), id='no_y_or_button'),
            pytest.param(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=2), id='middle'),
        ],
    )
    def test_a_wheel_event_without_a_direction_does_not_scroll(self, wheel_event):
        textbox = _real_textbox(text='line\n' * 40)
        textbox.scroll_offset = 3
        _install_frame_input(mouse_position=textbox.rect.center)

        textbox.on_mouse_wheel_event(wheel_event)

        assert textbox.scroll_offset == 3
        assert textbox.scrollbar.scroll_offset == 3
