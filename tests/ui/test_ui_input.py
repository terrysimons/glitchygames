"""Test suite for input-related UI components.

This module tests InputBox functionality including typing, submission, cancellation, focus
and drawing, with the real default font on real surfaces.
"""

import sys
from pathlib import Path

import numpy as np
import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events.base import HashableEvent
from glitchygames.ui import InputBox

# Test constants to avoid magic values
TEST_INPUT_X_POS = 10
TEST_INPUT_Y_POS = 20
TEST_INPUT_WIDTH = 200
TEST_INPUT_HEIGHT = 30
INPUT_BOX_COLOR = (233, 248, 215)
BACKGROUND_COLOR = (0, 0, 0)
KEY_REPEAT_DELAY_MILLISECONDS = 200


@pytest.fixture
def input_box():
    """A real InputBox on the real display.

    Returns:
        InputBox: The input box.

    """
    return InputBox(
        x=TEST_INPUT_X_POS,
        y=TEST_INPUT_Y_POS,
        width=TEST_INPUT_WIDTH,
        height=TEST_INPUT_HEIGHT,
        name='TestInputBox',
    )


@pytest.fixture
def key_repeat_off():
    """Turn key repeat off for the test and restore the previous setting after it.

    Yields:
        None

    """
    previous_delay, previous_interval = pygame.key.get_repeat()
    pygame.key.set_repeat()
    yield
    pygame.key.set_repeat(previous_delay, previous_interval)


class _ConfirmingParent:
    """A dialog-like parent that records the confirmations an input box asks for."""

    def __init__(self):
        self.confirmations = []

    def on_confirm_event(self, event, trigger):
        self.confirmations.append((event, trigger))


def _key_down(key, *, unicode='', mod=pygame.KMOD_NONE):
    """Build a key down event.

    Returns:
        HashableEvent: The event.

    """
    return HashableEvent(pygame.KEYDOWN, key=key, mod=mod, unicode=unicode)


def _type_text(box, text):
    """Type each character of a text into an input box."""
    for character in text:
        box.on_key_down_event(_key_down(ord(character), unicode=character))


def _interior_text_pixel_count(box):
    """Count the non-background pixels inside the input box's border.

    Returns:
        int: The number of pixels drawn inside the border.

    """
    rgb_pixels = pygame.surfarray.array3d(box.image)
    interior = rgb_pixels[1:-1, 1:-1]
    return int((interior != BACKGROUND_COLOR).any(axis=2).sum())


class TestInputBoxFunctionality:
    """Test InputBox functionality."""

    def test_inputbox_initialization(self, input_box):
        """Test InputBox initialization."""
        assert input_box.rect.x == TEST_INPUT_X_POS
        assert input_box.rect.y == TEST_INPUT_Y_POS
        assert input_box.rect.width == TEST_INPUT_WIDTH
        assert input_box.rect.height == TEST_INPUT_HEIGHT
        assert input_box.name == 'TestInputBox'
        assert not input_box.text
        assert input_box.is_active is False
        assert input_box.color == INPUT_BOX_COLOR
        assert input_box.image.get_size() == (TEST_INPUT_WIDTH, TEST_INPUT_HEIGHT)
        assert input_box.dirty == 2

    def test_inputbox_text_input(self, input_box):
        """Typing into an active input box appends the characters and draws them."""
        input_box.activate()
        input_box.update()
        assert _interior_text_pixel_count(input_box) == 0

        _type_text(input_box, 'hello')
        input_box.update()

        assert input_box.text == 'hello'
        assert _interior_text_pixel_count(input_box) > 0

    def test_inputbox_ignores_typing_while_inactive(self, input_box):
        """Keys typed while the box is inactive are dropped."""
        _type_text(input_box, 'hello')

        assert not input_box.text

    def test_inputbox_enter_key_submission(self, input_box):
        """Return asks the parent to confirm, with the box as the trigger, and adds no text."""
        parent = _ConfirmingParent()
        input_box.parent = parent
        input_box.activate()
        input_box.text = 'sprite.toml'
        return_event = _key_down(pygame.K_RETURN, unicode='\r')

        input_box.on_key_down_event(return_event)

        assert parent.confirmations == [(return_event, input_box)]
        assert input_box.text == 'sprite.toml'

    def test_inputbox_escape_key_cancellation(self, input_box, key_repeat_off):
        """Releasing Escape deactivates the box and stops it redrawing."""
        input_box.activate()

        input_box.on_key_up_event(HashableEvent(pygame.KEYUP, key=pygame.K_ESCAPE))

        assert input_box.is_active is False
        assert input_box.dirty == 0

    def test_inputbox_focus_handling(self, input_box):
        """A mouse up activates the box; deactivate clears it."""
        input_box.on_mouse_up_event(
            HashableEvent(pygame.MOUSEBUTTONUP, pos=input_box.rect.center, button=1)
        )
        assert input_box.is_active is True
        assert input_box.dirty == 2

        input_box.deactivate()
        assert input_box.is_active is False
        assert input_box.dirty == 0

    def test_inputbox_shift_semicolon_types_a_colon(self, input_box):
        """Shift+; types a colon even when the event carries no unicode text."""
        input_box.activate()

        input_box.on_key_down_event(_key_down(pygame.K_SEMICOLON, mod=pygame.KMOD_LSHIFT))

        assert input_box.text == ':'

    def test_inputbox_key_without_text_adds_nothing(self, input_box):
        """A key with no unicode text (an arrow) leaves the text unchanged."""
        input_box.activate()
        input_box.text = 'abc'

        input_box.on_key_down_event(_key_down(pygame.K_LEFT))

        assert input_box.text == 'abc'

    def test_inputbox_initial_text_is_drawn(self):
        """Text given to the constructor is drawn by the first update."""
        box = InputBox(
            x=TEST_INPUT_X_POS,
            y=TEST_INPUT_Y_POS,
            width=TEST_INPUT_WIDTH,
            height=TEST_INPUT_HEIGHT,
            text='name',
            name='TestInputBox',
        )

        box.update()

        assert box.text == 'name'
        assert _interior_text_pixel_count(box) > 0

    def test_inputbox_has_no_length_limit(self, input_box):
        """The box keeps every character typed (it has no maximum length)."""
        input_box.activate()
        long_text = 'x' * 100

        _type_text(input_box, long_text)

        assert input_box.text == long_text

    def test_inputbox_clear_functionality(self, input_box):
        """Backspace removes the last character, and does nothing on an empty box."""
        input_box.activate()
        _type_text(input_box, 'ab')

        input_box.on_key_down_event(_key_down(pygame.K_BACKSPACE, unicode='\b'))
        assert input_box.text == 'a'

        input_box.on_key_down_event(_key_down(pygame.K_BACKSPACE, unicode='\b'))
        input_box.on_key_down_event(_key_down(pygame.K_BACKSPACE, unicode='\b'))
        assert not input_box.text

        input_box.update()
        assert _interior_text_pixel_count(input_box) == 0


class TestInputBoxDrawing:
    """InputBox.update() on its real image."""

    def test_update_draws_the_border_on_a_black_background(self, input_box):
        input_box.update()

        rgb_pixels = pygame.surfarray.array3d(input_box.image)
        assert tuple(rgb_pixels[0, 0]) == INPUT_BOX_COLOR
        assert tuple(rgb_pixels[TEST_INPUT_WIDTH - 1, TEST_INPUT_HEIGHT - 1]) == INPUT_BOX_COLOR
        assert tuple(rgb_pixels[TEST_INPUT_WIDTH // 2, TEST_INPUT_HEIGHT // 2]) == BACKGROUND_COLOR

    def test_active_box_draws_its_cursor_in_the_second_half_of_each_second(self, input_box, mocker):
        """The cursor is drawn in the box colour only while frame clock % 1 > 0.5."""
        input_box.activate()
        clock = mocker.patch('glitchygames.ui.inputs.frame_clock_seconds', return_value=0.25)
        input_box.update()
        without_cursor = pygame.surfarray.array3d(input_box.image)

        clock.return_value = 0.75
        input_box.update()
        with_cursor = pygame.surfarray.array3d(input_box.image)

        changed = (with_cursor != without_cursor).any(axis=2)
        assert changed.any()
        assert (with_cursor[changed] == INPUT_BOX_COLOR).all()
        # The cursor is 3 px wide
        assert np.flatnonzero(changed.any(axis=1)).size == input_box.cursor.width

    def test_inactive_box_draws_no_cursor(self, input_box, mocker):
        mocker.patch('glitchygames.ui.inputs.frame_clock_seconds', return_value=0.75)

        input_box.update()

        assert _interior_text_pixel_count(input_box) == 0


class TestInputBoxKeyHandling:
    """InputBox key events while active and inactive."""

    def test_key_up_while_inactive_changes_nothing(self, input_box, key_repeat_off):
        input_box.on_key_up_event(HashableEvent(pygame.KEYUP, key=pygame.K_TAB))

        assert pygame.key.get_repeat() == (0, 0)
        assert input_box.is_active is False

    def test_key_up_of_an_ordinary_key_keeps_the_box_active(self, input_box, key_repeat_off):
        input_box.activate()

        input_box.on_key_up_event(HashableEvent(pygame.KEYUP, key=pygame.K_a))

        assert pygame.key.get_repeat()[0] == KEY_REPEAT_DELAY_MILLISECONDS
        assert input_box.is_active is True

    def test_key_up_of_tab_deactivates_the_box(self, input_box, key_repeat_off):
        input_box.activate()

        input_box.on_key_up_event(HashableEvent(pygame.KEYUP, key=pygame.K_TAB))

        assert input_box.is_active is False

    def test_return_without_a_confirming_parent_does_nothing(self, input_box):
        """Return asks the parent to confirm; a box without one keeps its text."""
        input_box.activate()
        input_box.text = 'sprite.toml'
        input_box.parent = object()

        input_box.on_key_down_event(
            HashableEvent(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode='\r')
        )

        assert input_box.text == 'sprite.toml'
        assert input_box.is_active is True
