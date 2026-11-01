"""Test suite for widget UI components.

This module consolidates tests from:
- test_ui_buttons.py: ButtonSprite functionality
- test_ui_controls.py: SliderSprite, CheckboxSprite, ColorWellSprite functionality
- test_ui_text.py: TextSprite, TextBoxSprite, MultiLineTextBox functionality
- test_widgets_coverage.py: Coverage tests for widgets module
- test_widgets_deeper_coverage.py: Deeper coverage tests for widgets module

Every widget here is built on the real display, with real surfaces and the real default font
(FontManager); drawing is checked through the pixels it leaves. Comparisons use RGB only: the
display's pixel format (per-pixel alpha or not) depends on the video driver.
"""

import pygame
import pytest

from glitchygames import clock, events
from glitchygames.clipboard import ClipboardUnavailableError, install_clipboard
from glitchygames.color import WHITE
from glitchygames.events.base import HashableEvent
from glitchygames.fonts import FontManager
from glitchygames.fonts.font_manager import (
    DEFAULT_FONT_NAME,
)
from glitchygames.input.state import (
    InputSnapshot,
    set_current_input,
)
from glitchygames.sources import advance_frame_clock
from glitchygames.ui import (
    ButtonSprite,
    CheckboxSprite,
    ColorWellSprite,
    InputDialog,
    MenuBar,
    MenuItem,
    MultiLineTextBox,
    SliderSprite,
    TextBoxSprite,
    TextSprite,
)
from glitchygames.ui.inputs import InputBox
from glitchygames.ui.sliders import (
    DECIMAL_INPUT_FORMAT,
    HEX_INPUT_FORMAT,
    TabControlSprite,
    format_channel,
    parse_channel,
)

# Test constants from test_ui_buttons.py
BUTTON_X = 10
BUTTON_Y = 20
BUTTON_WIDTH = 100
BUTTON_HEIGHT = 40

# Test constants from test_ui_controls.py
SLIDER_X = 10
SLIDER_Y = 20
SLIDER_WIDTH = 200
SLIDER_HEIGHT = 20
CHECKBOX_X = 10
CHECKBOX_Y = 20
CHECKBOX_WIDTH = 20
CHECKBOX_HEIGHT = 20
COLORWELL_X = 10
COLORWELL_Y = 20
COLORWELL_WIDTH = 50
COLORWELL_HEIGHT = 30

# Test constants from test_ui_text.py
TEST_X_POS = 10
TEST_Y_POS = 20
TEST_MULTILINE_WIDTH = 300
TEST_MULTILINE_HEIGHT = 100
TEST_SCROLL_OFFSET = 10

# Test constants shared by test_widgets_coverage.py and test_widgets_deeper_coverage.py
TEST_X = 10
TEST_Y = 20
TEST_WIDTH = 200
TEST_HEIGHT = 30
TEST_MENUBAR_WIDTH = 800
TEST_MENUBAR_HEIGHT = 50

# A channel value above this counts as lit (text, a cursor) against a dark or magenta background
LIT_CHANNEL_THRESHOLD = 128
# A fill no widget draws, so a pixel still holding it was not drawn over
PLACEHOLDER_FILL = (9, 9, 9)


@pytest.fixture(autouse=True)
def restore_key_repeat():
    """Put pygame's key repeat back after each test: the text widgets set it for real."""
    key_repeat = pygame.key.get_repeat()
    yield
    pygame.key.set_repeat(*key_repeat)


@pytest.fixture(autouse=True)
def drop_posted_menu_events():
    """Drop the MENUEVENTs a menu click posted to the real event queue, so none leak on."""
    yield
    pygame.event.clear(events.MENUEVENT)


def _rgb_at(surface, position):
    """Return the RGB colour of one pixel (the alpha is not the point here).

    Returns:
        tuple: The (red, green, blue) colour.
    """
    return tuple(surface.get_at(position))[:3]


def _mouse_event(event_type, position, *, button=1):
    """Build a real mouse event at a position.

    Returns:
        HashableEvent: The event.
    """
    if event_type == pygame.MOUSEMOTION:
        return HashableEvent(event_type, pos=position, rel=(0, 0), buttons=(0, 0, 0))
    return HashableEvent(event_type, pos=position, button=button)


def _key_down(*, key, unicode='', mod=0):
    """Build a real key down event.

    Returns:
        HashableEvent: The event.
    """
    return HashableEvent(pygame.KEYDOWN, key=key, unicode=unicode, mod=mod)


def _key_up(*, key, mod=0):
    """Build a real key up event.

    Returns:
        HashableEvent: The event.
    """
    return HashableEvent(pygame.KEYUP, key=key, mod=mod)


def _install_frame_input(*, modifiers=0, mouse_position=(0, 0)):
    """Make this frame's polled input (``current_input()``) hold modifiers and a mouse position.

    The autouse ``reset_engine_sources`` fixture (tests/harness.py) resets it after the test.
    """
    set_current_input(
        snapshot=InputSnapshot(
            pressed_scancodes=frozenset(),
            modifiers=modifiers,
            mouse_position=mouse_position,
            mouse_buttons=(False, False, False),
            mouse_focused=True,
        ),
    )


def _lit_pixel_count(surface, area=None, *, channel=None):
    """Count the lit pixels of a surface, or of an area of it.

    A pixel is lit when every RGB channel (or the one channel given: 0 red, 1 green, 2 blue)
    is above LIT_CHANNEL_THRESHOLD.

    Returns:
        int: The number of lit pixels.
    """
    area = surface.get_rect() if area is None else pygame.Rect(area)
    rgb_pixels = pygame.surfarray.pixels3d(surface)
    region = rgb_pixels[area.left : area.right, area.top : area.bottom]
    if channel is None:
        count = int((region > LIT_CHANNEL_THRESHOLD).all(axis=2).sum())
    else:
        count = int((region[:, :, channel] > LIT_CHANNEL_THRESHOLD).sum())
    del region, rgb_pixels
    return count


def _pixel_count_of(surface, rgb, area=None):
    """Count the pixels of a surface (or of an area of it) holding exactly one RGB colour.

    Returns:
        int: The number of pixels in that colour.
    """
    area = surface.get_rect() if area is None else pygame.Rect(area)
    rgb_pixels = pygame.surfarray.pixels3d(surface)
    region = rgb_pixels[area.left : area.right, area.top : area.bottom]
    count = int((region == rgb).all(axis=2).sum())
    del region, rgb_pixels
    return count


def _rgb_bytes(surface):
    """Return a surface's RGB pixels as bytes, to compare two renderings.

    Returns:
        bytes: The RGB pixel data.
    """
    return pygame.image.tobytes(surface, 'RGB')


# ============================================================================
# From test_ui_buttons.py
# ============================================================================


class TestButtonSpriteFunctionality:
    """Test ButtonSprite functionality."""

    def test_button_mouse_down_up_changes_background(self):
        """Test that button background changes on mouse down/up events."""
        button = ButtonSprite(x=10, y=20, width=100, height=40, name='ClickMe')
        assert button.background_color == button.inactive_color

        # Act: simulate mouse down
        button.on_left_mouse_button_down_event(_mouse_event(pygame.MOUSEBUTTONDOWN, (60, 40)))

        # Assert
        assert button.background_color == button.active_color
        assert button.dirty == 1

        # Act: simulate mouse up
        button.on_left_mouse_button_up_event(_mouse_event(pygame.MOUSEBUTTONUP, (60, 40)))

        # Assert
        assert button.background_color == button.inactive_color
        assert button.dirty == 1

    def test_pressed_button_is_drawn_in_its_active_color(self):
        """A pressed button shows its active colour on screen."""
        groups = pygame.sprite.LayeredDirty()
        button = ButtonSprite(x=10, y=20, width=100, height=40, name='ClickMe', groups=groups)
        screen = pygame.Surface((200, 100))
        # Inside the button, clear of its border and of its centred label
        inside_point = (button.rect.x + 5, button.rect.y + 5)

        button.on_left_mouse_button_down_event(
            _mouse_event(pygame.MOUSEBUTTONDOWN, button.rect.center)
        )
        groups.update()
        groups.draw(screen)

        assert _rgb_at(screen, inside_point) == button.active_color

    def test_button_hover_state_changes(self):
        """Test that hovering does not change the button's colour (only a click does)."""
        button = ButtonSprite(x=10, y=20, width=100, height=40, name='HoverButton')
        initial_color = button.background_color

        # Act: simulate mouse enter
        button.on_mouse_enter_event(_mouse_event(pygame.MOUSEMOTION, (60, 40)))

        # Assert: ButtonSprite doesn't change color on hover, only on click
        assert button.background_color == button.inactive_color

        # Act: simulate mouse exit (ButtonSprite doesn't have on_mouse_leave_event)
        button.on_mouse_exit_event(_mouse_event(pygame.MOUSEMOTION, (500, 500)))

        # Assert: should return to initial color
        assert button.background_color == initial_color

    def test_button_click_behavior(self, mocker):
        """A click changes the colour and runs the button's down and up callbacks."""
        button = ButtonSprite(x=10, y=20, width=100, height=40, name='ClickButton')
        down_callback = mocker.Mock()
        up_callback = mocker.Mock()
        button.callbacks = {
            'on_left_mouse_button_down_event': down_callback,
            'on_left_mouse_button_up_event': up_callback,
        }
        assert button.background_color == button.inactive_color

        # Act: simulate click
        down_event = _mouse_event(pygame.MOUSEBUTTONDOWN, (60, 40))
        button.on_left_mouse_button_down_event(down_event)

        # Assert: should change to active color
        assert button.background_color == button.active_color
        down_callback.assert_called_once_with(event=down_event, trigger=button)

        up_event = _mouse_event(pygame.MOUSEBUTTONUP, (60, 40))
        button.on_left_mouse_button_up_event(up_event)

        # Assert: should return to inactive color
        assert button.background_color == button.inactive_color
        up_callback.assert_called_once_with(event=up_event, trigger=button)

    def test_button_initialization(self):
        """Test ButtonSprite initialization draws a one-pixel border in its border colour."""
        # Act
        button = ButtonSprite(x=10, y=20, width=100, height=40, name='TestButton')

        # Assert
        assert button.rect.x == BUTTON_X
        assert button.rect.y == BUTTON_Y
        assert button.rect.width == BUTTON_WIDTH
        assert button.rect.height == BUTTON_HEIGHT
        assert button.name == 'TestButton'
        assert button.background_color == (0, 0, 0)
        assert button.active_color == (128, 128, 128)
        assert button.inactive_color == (0, 0, 0)
        assert button.border_color == (255, 255, 255)
        assert button.image.get_size() == (BUTTON_WIDTH, BUTTON_HEIGHT)
        for corner in [(0, 0), (BUTTON_WIDTH - 1, 0), (0, BUTTON_HEIGHT - 1)]:
            assert _rgb_at(button.image, corner) == button.border_color
        assert _rgb_at(button.image, (1, 1)) != button.border_color

    def test_button_text_rendering(self):
        """Test that the button's label is a TextSprite drawing its name, centred on it."""
        # Act
        button = ButtonSprite(x=10, y=20, width=100, height=40, name='TextButton')

        # Assert - ButtonSprite creates a TextSprite internally that shows its name
        assert button.text.name == 'TextButton'
        assert button.text.text == 'TextButton'
        assert button.text.rect.center == button.rect.center
        # The label's white text is drawn on its image
        assert _lit_pixel_count(button.text.image) > 0

    def test_button_disabled_state(self):
        """Test the button changes colour on a press and back on the release."""
        button = ButtonSprite(x=10, y=20, width=100, height=40, name='DisabledButton')

        # Test that button can be created and has expected properties
        assert button.name == 'DisabledButton'

        # Test that button responds to mouse events
        initial_color = button.background_color

        # Act: simulate mouse down
        button.on_left_mouse_button_down_event(_mouse_event(pygame.MOUSEBUTTONDOWN, (60, 40)))

        # Assert: background color should change
        assert button.background_color != initial_color

        # Act: simulate mouse up
        button.on_left_mouse_button_up_event(_mouse_event(pygame.MOUSEBUTTONUP, (60, 40)))

        # Assert: background color should return to inactive
        assert button.background_color == button.inactive_color


# ============================================================================
# From test_ui_controls.py
# ============================================================================


class TestSliderSpriteFunctionality:
    """Test SliderSprite functionality."""

    def test_slider_initialization(self):
        """Test SliderSprite initialization: rect, knob at the left end, value 0 shown."""
        # Act
        slider = SliderSprite(x=10, y=20, width=200, height=20, name='TestSlider')

        # Assert
        assert slider.rect.x == SLIDER_X
        assert slider.rect.y == SLIDER_Y
        assert slider.rect.width == SLIDER_WIDTH
        assert slider.rect.height == SLIDER_HEIGHT
        assert slider.name == 'TestSlider'
        assert slider.value == 0
        assert slider.slider_knob.rect.x == SLIDER_X
        assert slider.text_sprite.text == '0'
        # The text box sits 4 pixels right of the slider
        assert slider.text_sprite.rect.x == SLIDER_X + SLIDER_WIDTH + 4

    def test_slider_value_change(self):
        """Test setting the value moves the knob and updates the text."""
        slider = SliderSprite(x=10, y=20, width=200, height=20, name='TestSlider')

        slider.value = 255

        assert slider.value == 255
        assert slider.slider_knob.rect.x == slider.max_x
        assert slider.text_sprite.text == '255'

    def test_slider_mouse_drag(self):
        """Test a press then a drag moves the value to the mouse position."""
        slider = SliderSprite(x=10, y=20, width=200, height=20, name='TestSlider')

        # Act: press at the left end, then drag to the middle
        slider.on_left_mouse_button_down_event(_mouse_event(pygame.MOUSEBUTTONDOWN, (10, 30)))
        assert slider.dragging is True
        assert slider.value == 0
        slider.on_mouse_motion_event(_mouse_event(pygame.MOUSEMOTION, (110, 30)))

        # Assert: the value follows the mouse
        expected_value = (110 - slider.min_x) * 255 // (slider.max_x - slider.min_x)
        assert slider.value == expected_value

    def test_slider_callback(self):
        """Test a slider without a parent takes a click without notifying anyone."""
        slider = SliderSprite(x=10, y=20, width=200, height=20, name='TestSlider')

        slider.on_left_mouse_button_down_event(
            _mouse_event(pygame.MOUSEBUTTONDOWN, (slider.max_x, 30))
        )

        assert slider.parent is None
        assert slider.value == 255


class TestCheckboxSpriteFunctionality:
    """Test CheckboxSprite functionality."""

    def test_checkbox_initialization(self):
        """Test CheckboxSprite initialization."""
        # Act
        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name='TestCheckbox')

        # Assert
        assert checkbox.rect.x == CHECKBOX_X
        assert checkbox.rect.y == CHECKBOX_Y
        assert checkbox.rect.width == CHECKBOX_WIDTH
        assert checkbox.rect.height == CHECKBOX_HEIGHT
        assert checkbox.name == 'TestCheckbox'
        assert not checkbox.checked

    def test_checkbox_toggle(self):
        """Test CheckboxSprite toggle functionality."""
        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name='TestCheckbox')

        # Test initial state
        assert not checkbox.checked

        # Act: simulate click to toggle
        event = _mouse_event(pygame.MOUSEBUTTONUP, (20, 30))
        checkbox.on_left_mouse_button_up_event(event)

        # Assert: should be checked after click
        assert checkbox.checked

        # Act: click again
        checkbox.on_left_mouse_button_up_event(event)

        # Assert: should be unchecked after second click
        assert not checkbox.checked

    def test_checkbox_click_toggle(self):
        """Test a click checks the box, and the next draw shows the X."""
        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name='TestCheckbox')

        # Test initial state
        assert not checkbox.checked

        # Act: simulate click
        checkbox.on_left_mouse_button_up_event(_mouse_event(pygame.MOUSEBUTTONUP, (20, 30)))
        checkbox.update()

        # Assert: should be checked after click, with the X's diagonals drawn
        assert checkbox.checked
        assert _rgb_at(checkbox.image, (10, 10)) == checkbox.color
        assert _rgb_at(checkbox.image, (10, 9)) == checkbox.color

    def test_checkbox_callback(self):
        """Test a click toggles the box and marks it dirty, so the next draw shows the change."""
        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name='TestCheckbox')
        checkbox.dirty = 0

        checkbox.on_left_mouse_button_up_event(_mouse_event(pygame.MOUSEBUTTONUP, (20, 30)))

        assert checkbox.checked is True
        assert checkbox.dirty == 1

    def test_checkbox_click_runs_its_callback(self, mocker):
        """A checkbox click runs its on_left_mouse_button_up_event callback, as a button's does."""
        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name='TestCheckbox')
        up_callback = mocker.Mock()
        checkbox.callbacks = {'on_left_mouse_button_up_event': up_callback}
        event = _mouse_event(pygame.MOUSEBUTTONUP, (20, 30))

        checkbox.on_left_mouse_button_up_event(event)

        up_callback.assert_called_once_with(event=event, trigger=checkbox)

    def test_checkbox_set_checked(self):
        """Test CheckboxSprite set checked state."""
        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name='TestCheckbox')

        # Test initial state
        assert not checkbox.checked

        # Act: simulate click to check
        event = _mouse_event(pygame.MOUSEBUTTONUP, (20, 30))
        checkbox.on_left_mouse_button_up_event(event)

        # Assert: should be checked
        assert checkbox.checked

        # Act: simulate click to uncheck
        checkbox.on_left_mouse_button_up_event(event)

        # Assert: should be unchecked
        assert not checkbox.checked


class TestColorWellSpriteFunctionality:
    """Test ColorWellSprite functionality."""

    def test_colorwell_initialization(self):
        """Test ColorWellSprite initialization."""
        # Act
        colorwell = ColorWellSprite(x=10, y=20, width=50, height=30, name='TestColorWell')

        # Assert
        assert colorwell.rect.x == COLORWELL_X
        assert colorwell.rect.y == COLORWELL_Y
        assert colorwell.rect.width == COLORWELL_WIDTH
        assert colorwell.rect.height == COLORWELL_HEIGHT
        assert colorwell.name == 'TestColorWell'
        assert colorwell.active_color == (0, 0, 0, 255)  # Default color (RGBA)
        # Its image keeps per-pixel alpha, so a translucent colour shows as one
        assert colorwell.image.get_flags() & pygame.SRCALPHA

    def test_colorwell_color_change(self):
        """Test changing the colour marks the well dirty and the next draw shows it."""
        colorwell = ColorWellSprite(x=10, y=20, width=50, height=30, name='TestColorWell')
        colorwell.dirty = 0

        colorwell.active_color = (10, 200, 30)
        colorwell.update()

        assert colorwell.dirty == 1
        assert _rgb_at(colorwell.image, (25, 15)) == (10, 200, 30)

    def test_colorwell_hover_effect(self):
        """Test hovering over the well changes nothing it draws."""
        colorwell = ColorWellSprite(x=10, y=20, width=50, height=30, name='TestColorWell')
        colorwell.active_color = (10, 200, 30)
        colorwell.update()
        drawn_pixels = _rgb_bytes(colorwell.image)

        # Act: simulate mouse enter, then exit
        colorwell.on_mouse_enter_event(_mouse_event(pygame.MOUSEMOTION, (35, 35)))
        colorwell.on_mouse_exit_event(_mouse_event(pygame.MOUSEMOTION, (500, 500)))
        colorwell.update()

        # Assert: the well looks the same
        assert colorwell.active_color == (10, 200, 30, 255)
        assert _rgb_bytes(colorwell.image) == drawn_pixels

    def test_colorwell_color_validation(self):
        """Test the well's colour channels start at opaque black."""
        colorwell = ColorWellSprite(x=10, y=20, width=50, height=30, name='TestColorWell')

        assert colorwell.name == 'TestColorWell'
        assert (colorwell.red, colorwell.green, colorwell.blue, colorwell.alpha) == (0, 0, 0, 255)


# ============================================================================
# From test_ui_text.py
# ============================================================================


class TestTextSpriteFunctionality:
    """Test TextSprite functionality."""

    def test_text_sprite_initialization(self):
        """Test TextSprite initialization renders its text centred on its image."""
        # Act
        text_sprite = TextSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='Hello World',
            name='TestText',
        )

        # Assert
        assert text_sprite.rect.x == TEST_X_POS
        assert text_sprite.rect.y == TEST_Y_POS
        assert text_sprite.text == 'Hello World'
        assert text_sprite.name == 'TestText'
        assert text_sprite.image.get_size() == (TEST_WIDTH, TEST_HEIGHT)
        # The default background is magenta (no green); the white text lights the green channel
        assert _rgb_at(text_sprite.image, (0, 0)) == (255, 0, 255)
        left_half_text = _lit_pixel_count(text_sprite.image, (0, 0, TEST_WIDTH // 2, TEST_HEIGHT))
        right_half_text = _lit_pixel_count(
            text_sprite.image, (TEST_WIDTH // 2, 0, TEST_WIDTH // 2, TEST_HEIGHT)
        )
        assert left_half_text > 0
        assert right_half_text > 0

    def test_text_sprite_text_update(self):
        """Test changing the text renders the new text."""
        text_sprite = TextSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='Hello',
            name='TestText',
        )
        short_text_pixels = _lit_pixel_count(text_sprite.image)

        # Act
        text_sprite.text = 'Updated Text'

        # Assert: the longer text lights more pixels
        assert text_sprite.text == 'Updated Text'
        assert text_sprite.dirty == 2
        assert _lit_pixel_count(text_sprite.image) > short_text_pixels


class TestTextBoxSpriteFunctionality:
    """Test TextBoxSprite functionality."""

    def test_textbox_initialization(self):
        """Test TextBoxSprite initialization."""
        # Act
        textbox = TextBoxSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestTextBox',
        )

        # Assert
        assert textbox.rect.x == TEST_X_POS
        assert textbox.rect.y == TEST_Y_POS
        assert textbox.rect.width == TEST_WIDTH
        assert textbox.rect.height == TEST_HEIGHT
        assert textbox.name == 'TestTextBox'
        # Its text sprite sits on it, one border width smaller
        assert textbox.text_box.rect.topleft == (TEST_X_POS, TEST_Y_POS)
        assert textbox.text_box.rect.size == (TEST_WIDTH - 1, TEST_HEIGHT - 1)
        assert not textbox.text_box.text

    def test_textbox_text_input(self):
        """Test text set on the text box's text sprite is rendered by it."""
        textbox = TextBoxSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestTextBox',
        )
        assert _lit_pixel_count(textbox.text_box.image) == 0

        # Act: set the text on the text box's text sprite
        textbox.text_box.text = 'Hello'

        # Assert - TextBoxSprite has text_box attribute that contains the text
        assert textbox.text_box.text == 'Hello'
        assert _lit_pixel_count(textbox.text_box.image) > 0

    def test_textbox_backspace(self):
        """Test a shorter text replaces the longer one on the text sprite."""
        textbox = TextBoxSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestTextBox',
        )
        textbox.text_box.text = 'Hello'
        longer_text_pixels = _lit_pixel_count(textbox.text_box.image)

        # Act: simulate backspace by setting the text without its last character
        textbox.text_box.text = 'Hell'

        # Assert
        assert textbox.text_box.text == 'Hell'
        assert 0 < _lit_pixel_count(textbox.text_box.image) < longer_text_pixels

    def test_textbox_focus_handling(self):
        """Test a press greys the text box's background and the release restores it."""
        textbox = TextBoxSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestTextBox',
        )

        # Act: press on the textbox
        textbox.on_left_mouse_button_down_event(_mouse_event(pygame.MOUSEBUTTONDOWN, (15, 25)))

        # Assert - the background changes on the press
        assert textbox.background_color == (128, 128, 128)
        assert textbox.dirty == 1

        # Act: the mouse button comes back up
        textbox.on_left_mouse_button_up_event(_mouse_event(pygame.MOUSEBUTTONUP, (15, 25)))

        # Assert - and back to black on the release
        assert textbox.background_color == (0, 0, 0)


class TestMultiLineTextBoxFunctionality:
    """Test MultiLineTextBox functionality."""

    def test_multiline_textbox_initialization(self):
        """Test MultiLineTextBox initialization sizes its visible lines from the font."""
        # Act
        multiline = MultiLineTextBox(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_MULTILINE_WIDTH,
            height=TEST_MULTILINE_HEIGHT,
            name='TestMultiLine',
        )

        # Assert
        assert multiline.rect.x == TEST_X_POS
        assert multiline.rect.y == TEST_Y_POS
        assert multiline.rect.width == TEST_MULTILINE_WIDTH
        assert multiline.rect.height == TEST_MULTILINE_HEIGHT
        assert multiline.name == 'TestMultiLine'
        line_height = multiline._get_line_height()
        assert multiline.visible_lines == (TEST_MULTILINE_HEIGHT - 10) // line_height
        assert multiline.scrollbar.x == TEST_MULTILINE_WIDTH - 8 - 2

    def test_multiline_textbox_line_breaks(self):
        """Test a newline puts the second line's text below the first."""
        multiline = MultiLineTextBox(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_MULTILINE_WIDTH,
            height=TEST_MULTILINE_HEIGHT,
            name='TestMultiLine',
        )

        # Act: set text with a line break, then draw it
        multiline.text = 'Line 1\nLine 2'
        multiline.update()

        # Assert: each line's band of the box holds text
        assert multiline.text == 'Line 1\nLine 2'
        line_height = multiline._get_line_height()
        text_width = TEST_MULTILINE_WIDTH - 20
        first_line_band = (5, 5, text_width, line_height)
        second_line_band = (5, 5 + line_height, text_width, line_height)
        below_text_band = (5, 5 + 2 * line_height, text_width, line_height)
        assert _lit_pixel_count(multiline.image, first_line_band) > 0
        assert _lit_pixel_count(multiline.image, second_line_band) > 0
        assert _lit_pixel_count(multiline.image, below_text_band) == 0

    def test_multiline_textbox_scrolling(self):
        """Test the scroll offset picks the first line drawn."""
        multiline = MultiLineTextBox(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_MULTILINE_WIDTH,
            height=TEST_MULTILINE_HEIGHT,
            name='TestMultiLine',
        )
        multiline.text = '\n'.join(['' if index else 'Top' for index in range(30)])
        line_height = multiline._get_line_height()
        first_line_band = (5, 5, TEST_MULTILINE_WIDTH - 20, line_height)

        # Act: scroll down, then draw
        multiline.scroll_offset = TEST_SCROLL_OFFSET
        multiline.update()

        # Assert: the top line ('Top') is scrolled out of view
        assert multiline.scroll_offset == TEST_SCROLL_OFFSET
        assert _lit_pixel_count(multiline.image, first_line_band) == 0

        # Act: scroll back to the top
        multiline.scroll_offset = 0
        multiline.update()

        # Assert: the top line is drawn again
        assert multiline.scroll_offset == 0
        assert _lit_pixel_count(multiline.image, first_line_band) > 0


# ============================================================================
# From test_widgets_coverage.py
# ============================================================================


def _menubar(*, x=0, y=0, width=TEST_MENUBAR_WIDTH, height=TEST_MENUBAR_HEIGHT):
    """Build a MenuBar in its own real sprite group.

    Returns:
        MenuBar: The menu bar.
    """
    return MenuBar(
        x=x,
        y=y,
        width=width,
        height=height,
        name='test_menubar',
        groups=pygame.sprite.LayeredDirty(),
    )


def _menubar_state(menubar):
    """Return the menu bar state its event handlers could change.

    Returns:
        tuple: Its menu items, focus, dirty flag and pixels.
    """
    return (dict(menubar.menu_items), menubar.has_focus, menubar.dirty, _rgb_bytes(menubar.image))


class TestMenuBarEventHandlers:
    """Test the MenuBar event handlers.

    The drag, drop, motion and wheel handlers only log: each test checks the event leaves the
    menu bar as it was.
    """

    def test_menubar_left_mouse_drag_event(self):
        """Test MenuBar on_left_mouse_drag_event changes nothing."""
        menubar = _menubar()
        state_before = _menubar_state(menubar)
        event = _mouse_event(pygame.MOUSEMOTION, (10, 10))

        menubar.on_left_mouse_drag_event(event, event)

        assert _menubar_state(menubar) == state_before

    def test_menubar_left_mouse_drop_event(self):
        """Test MenuBar on_left_mouse_drop_event changes nothing."""
        menubar = _menubar()
        state_before = _menubar_state(menubar)

        menubar.on_left_mouse_drop_event(_mouse_event(pygame.MOUSEBUTTONUP, (10, 10)))

        assert _menubar_state(menubar) == state_before

    def test_menubar_middle_mouse_drag_event(self):
        """Test MenuBar on_middle_mouse_drag_event changes nothing."""
        menubar = _menubar()
        state_before = _menubar_state(menubar)

        menubar.on_middle_mouse_drag_event(_mouse_event(pygame.MOUSEMOTION, (10, 10)))

        assert _menubar_state(menubar) == state_before

    def test_menubar_middle_mouse_drop_event(self):
        """Test MenuBar on_middle_mouse_drop_event changes nothing."""
        menubar = _menubar()
        state_before = _menubar_state(menubar)

        menubar.on_middle_mouse_drop_event(_mouse_event(pygame.MOUSEBUTTONUP, (10, 10), button=2))

        assert _menubar_state(menubar) == state_before

    def test_menubar_mouse_drag_event(self):
        """Test MenuBar on_mouse_drag_event changes nothing."""
        menubar = _menubar()
        state_before = _menubar_state(menubar)
        event = _mouse_event(pygame.MOUSEMOTION, (10, 10))

        menubar.on_mouse_drag_event(event, event)

        assert _menubar_state(menubar) == state_before

    def test_menubar_mouse_drop_event(self):
        """Test MenuBar on_mouse_drop_event changes nothing."""
        menubar = _menubar()
        state_before = _menubar_state(menubar)
        event = _mouse_event(pygame.MOUSEBUTTONUP, (10, 10))

        menubar.on_mouse_drop_event(event, event)

        assert _menubar_state(menubar) == state_before

    def test_menubar_mouse_motion_event(self):
        """Test MenuBar on_mouse_motion_event changes nothing."""
        menubar = _menubar()
        state_before = _menubar_state(menubar)

        menubar.on_mouse_motion_event(_mouse_event(pygame.MOUSEMOTION, (10, 10)))

        assert _menubar_state(menubar) == state_before

    def test_menubar_right_mouse_drag_event(self):
        """Test MenuBar on_right_mouse_drag_event changes nothing."""
        menubar = _menubar()
        state_before = _menubar_state(menubar)

        menubar.on_right_mouse_drag_event(_mouse_event(pygame.MOUSEMOTION, (10, 10)))

        assert _menubar_state(menubar) == state_before

    def test_menubar_right_mouse_drop_event(self):
        """Test MenuBar on_right_mouse_drop_event changes nothing."""
        menubar = _menubar()
        state_before = _menubar_state(menubar)

        menubar.on_right_mouse_drop_event(_mouse_event(pygame.MOUSEBUTTONUP, (10, 10), button=3))

        assert _menubar_state(menubar) == state_before

    def test_menubar_mouse_wheel_event(self):
        """Test MenuBar on_mouse_wheel_event changes nothing."""
        menubar = _menubar()
        state_before = _menubar_state(menubar)

        menubar.on_mouse_wheel_event(HashableEvent(pygame.MOUSEWHEEL, x=0, y=1))

        assert _menubar_state(menubar) == state_before

    def test_menubar_update_with_menu_items(self):
        """Test MenuBar update draws each menu item's image at the item's position."""
        menubar = _menubar()
        # A nameless item is an icon: its image is drawn as it is (no colour key)
        icon_item = MenuItem(
            x=40, y=10, width=20, height=15, name=None, groups=pygame.sprite.LayeredDirty()
        )
        icon_item.image.fill((10, 200, 30))
        menubar.menu_items['Icon'] = icon_item

        # Update should blit menu items
        menubar.update()

        assert _rgb_at(menubar.image, (40, 10)) == (10, 200, 30)
        assert _rgb_at(menubar.image, (59, 24)) == (10, 200, 30)
        assert _rgb_at(menubar.image, (60, 25)) != (10, 200, 30)

    def test_menubar_update_with_focus(self):
        """Test MenuBar update draws its focus border around itself when focused."""
        menubar = _menubar()
        menubar.image.fill((0, 0, 0, 255))
        menubar.has_focus = True

        menubar.update()

        border_rgb = WHITE[:3]
        assert _rgb_at(menubar.image, (0, 0)) == border_rgb
        assert _rgb_at(menubar.image, (TEST_MENUBAR_WIDTH - 1, TEST_MENUBAR_HEIGHT - 1)) == (
            border_rgb
        )
        # One pixel wide: the next pixel in is untouched
        assert _rgb_at(menubar.image, (1, 1)) == (0, 0, 0)

    def test_menubar_update_without_focus_draws_no_border(self):
        """Test an unfocused MenuBar's update leaves its edges alone."""
        menubar = _menubar()
        menubar.image.fill((0, 0, 0, 255))
        menubar.has_focus = False

        menubar.update()

        assert _rgb_at(menubar.image, (0, 0)) == (0, 0, 0)

    def test_menubar_away_from_the_origin_draws_its_background_on_all_of_itself(self):
        """A menu bar at x=50 draws its translucent white background from its own left edge."""
        menubar = _menubar(x=50, width=200, height=30)

        assert tuple(menubar.image.get_at((1, 1))) == (255, 255, 255, 128)

    def test_menubar_add_menu_item_with_menu(self):
        """Test MenuBar add_menu_item with an explicit menu only logs: no menu is added."""
        menubar = _menubar()
        menu_item = MenuItem(
            x=0, y=0, width=60, height=20, name='Item', groups=pygame.sprite.LayeredDirty()
        )

        # Call with menu parameter (takes the else branch)
        menubar.add_menu_item(menu_item, menu=_menubar())

        assert menubar.menu_items == {}


def _menu_item(*, x=0, y=0, width=100, height=20, name='TestItem'):
    """Build a MenuItem in its own real sprite group.

    Returns:
        MenuItem: The menu item.
    """
    return MenuItem(
        x=x, y=y, width=width, height=height, name=name, groups=pygame.sprite.LayeredDirty()
    )


class TestMenuItemEventHandlers:
    """Test MenuItem event handlers."""

    def test_menuitem_drag_events(self):
        """Test the MenuItem drag, drop and wheel handlers (they only log) change nothing."""
        item = _menu_item()
        state_before = (item.is_active, item.dirty, item.rect.copy(), _rgb_bytes(item.image))
        event = _mouse_event(pygame.MOUSEMOTION, (10, 10))
        trigger = _mouse_event(pygame.MOUSEBUTTONDOWN, (10, 10))

        item.on_left_mouse_drag_event(event, trigger)
        item.on_left_mouse_drop_event(event, trigger)
        item.on_middle_mouse_drag_event(event, trigger)
        item.on_middle_mouse_drop_event(event, trigger)
        item.on_mouse_drag_event(event, trigger)
        item.on_mouse_drop_event(event, trigger)
        item.on_right_mouse_drag_event(event)
        item.on_right_mouse_drop_event(event)
        item.on_mouse_wheel_event(HashableEvent(pygame.MOUSEWHEEL, x=0, y=1))

        assert (item.is_active, item.dirty, item.rect, _rgb_bytes(item.image)) == state_before

    def test_menuitem_without_name(self):
        """Test a MenuItem without a name has no text sprite and no white colour key."""
        item = _menu_item(name=None)

        assert item.name is None
        assert not hasattr(item, 'text')
        assert item.image.get_colorkey() is None

    def test_menuitem_with_name_draws_its_name_on_a_text_sprite(self):
        """A named MenuItem keys out its white image and shows its name in black on white."""
        item = _menu_item()

        colorkey = item.image.get_colorkey()
        assert colorkey is not None
        assert colorkey[:3] == (255, 255, 255)
        assert item.text.text == 'TestItem'
        assert item.text.rect.topleft == item.rect.topleft
        # Black text on the text sprite's white background
        assert _pixel_count_of(item.text.image, (0, 0, 0)) > 0

    def test_menuitem_update_active(self):
        """Test an active MenuItem's update draws its menu image on its own image."""
        item = _menu_item()
        item.is_active = True
        item.menu_image = pygame.Surface((100, 100))
        item.menu_image.fill((10, 200, 30))
        item.menu_rect = item.menu_image.get_rect()

        item.update()

        assert _rgb_at(item.image, (0, 0)) == (10, 200, 30)
        assert _rgb_at(item.image, (99, 19)) == (10, 200, 30)

    def test_menuitem_update_inactive(self):
        """Test an inactive MenuItem's update leaves its image alone."""
        item = _menu_item()
        item.is_active = False
        item.menu_image = pygame.Surface((100, 100))
        item.menu_image.fill((10, 200, 30))
        drawn_pixels = _rgb_bytes(item.image)

        item.update()

        assert _rgb_bytes(item.image) == drawn_pixels

    def test_menuitem_add_method(self):
        """Test MenuItem add puts its text sprite (not itself) in the group."""
        item = _menu_item()
        group = pygame.sprite.LayeredDirty()

        item.add(group)

        assert item.text in group
        assert item not in group

    def test_menuitem_add_method_without_text(self):
        """Test MenuItem add without a text sprite adds nothing."""
        item = _menu_item(name=None)
        group = pygame.sprite.LayeredDirty()

        item.add(group)

        assert len(group) == 0

    def test_menuitem_add_menu_item_method_with_menu(self):
        """Test MenuItem add_menu_item with an explicit menu only logs: nothing is added."""
        item = _menu_item()
        sub_item = _menu_item(name='SubItem')

        # Call with menu parameter to take the else branch (just logs)
        item.add_menu_item(sub_item, menu=_menubar())

        assert item.menu_items == {}

    def test_menuitem_mouse_exit_sets_dirty(self):
        """Test MenuItem on_mouse_exit_event clears focus and sets the dirty flag."""
        item = _menu_item()
        item.has_focus = True
        item.dirty = 0

        item.on_mouse_exit_event(_mouse_event(pygame.MOUSEMOTION, (50, 10)))

        assert item.has_focus is False
        assert item.dirty == 1

    def test_menuitem_left_button_up_resets_state(self):
        """A release on a MenuItem shows its menu-up image and posts a MENUEVENT for it."""
        item = _menu_item()
        item.on_left_mouse_button_down_event(_mouse_event(pygame.MOUSEBUTTONDOWN, (50, 10)))

        item.on_left_mouse_button_up_event(_mouse_event(pygame.MOUSEBUTTONUP, (50, 10)))

        assert item.is_active == 0
        assert item.dirty == 2
        assert item.image is item.menu_up_image
        assert item.rect is item.menu_up_rect
        menu_events = pygame.event.get(events.MENUEVENT)
        assert [(event.menu, event.menu_item) for event in menu_events] == [(item, item)]

    def test_menuitem_left_button_up_runs_the_menu_item_callback(self, mocker):
        """A release on a MenuItem runs its on_menu_item_event callback with the event."""
        item = _menu_item()
        menu_item_callback = mocker.Mock()
        item.callbacks = {'on_menu_item_event': menu_item_callback}
        event = _mouse_event(pygame.MOUSEBUTTONUP, (50, 10))

        item.on_left_mouse_button_up_event(event)

        menu_item_callback.assert_called_once_with(item, event)

    def test_menuitem_left_button_down_activates(self):
        """Test MenuItem on_left_mouse_button_down_event shows its dropped-down menu."""
        item = _menu_item()

        item.on_left_mouse_button_down_event(_mouse_event(pygame.MOUSEBUTTONDOWN, (50, 10)))

        assert item.is_active == 1
        assert item.dirty == 2
        assert item.image is item.menu_down_image
        assert item.rect is item.menu_down_rect


class TestMenuItemAddMenu:
    """Test MenuItem.add_menu() layout recalculation.

    Note: MenuItem.add_menu references self.x which is set by the MenuItem's
    __init__ but only through rect.x. We need to set self.x manually since
    the Sprite base class doesn't set it as an instance attribute.
    """

    @staticmethod
    def _create_menuitem_with_x(rect, name):
        """Create a MenuItem and ensure self.x is set for add_menu compatibility.

        Args:
            rect: A tuple of (x, y, width, height) for the menu item bounds.
            name: The name of the menu item.

        Returns:
            A MenuItem with self.x set.
        """
        x, y, width, height = rect
        item = _menu_item(x=x, y=y, width=width, height=height, name=name)
        # MenuItem.add_menu references self.x which isn't set by Sprite.__init__
        # This is needed for the add_menu path to work
        item.x = x  # type: ignore[unresolved-attribute]
        return item

    def test_add_menu_first_item(self):
        """Test MenuItem.add_menu adds the first submenu item below the item."""
        parent_item = self._create_menuitem_with_x((0, 0, 100, 20), 'FileMenu')
        sub_item = self._create_menuitem_with_x((0, 0, 80, 20), 'Open')

        parent_item.add_menu(sub_item)

        assert parent_item.menu_items == {'Open': sub_item}
        # The next sub-item's offset moves down one item height
        assert parent_item.menu_offset_y == parent_item.border_width + 20

    def test_add_menu_puts_the_first_sub_item_right_below_the_item(self):
        """The first sub-item of a 20-pixel-tall item starts at y=20, inside the menu image."""
        parent_item = self._create_menuitem_with_x((0, 0, 100, 20), 'FileMenu')
        sub_item = self._create_menuitem_with_x((0, 0, 80, 20), 'Open')

        parent_item.add_menu(sub_item)

        assert sub_item.rect.y == 20
        assert sub_item.rect.bottom <= parent_item.menu_down_image.get_height()

    def test_add_menu_second_item_adjusts_offset(self):
        """Test MenuItem.add_menu stacks the second item below the first."""
        parent_item = self._create_menuitem_with_x((0, 0, 100, 20), 'FileMenu')
        sub_item1 = self._create_menuitem_with_x((0, 0, 80, 20), 'Open')
        sub_item2 = self._create_menuitem_with_x((0, 0, 80, 20), 'Save')

        parent_item.add_menu(sub_item1)
        parent_item.add_menu(sub_item2)

        assert list(parent_item.menu_items) == ['Open', 'Save']
        assert sub_item2.rect.y == sub_item1.rect.bottom

    def test_second_add_menu_sizes_the_image_for_the_item_and_both_sub_items(self):
        """A second add_menu counts the item's own height once, not the whole first menu."""
        parent_item = self._create_menuitem_with_x((0, 0, 100, 20), 'FileMenu')
        parent_item.add_menu(self._create_menuitem_with_x((0, 0, 80, 20), 'Open'))
        parent_item.add_menu(self._create_menuitem_with_x((0, 0, 80, 20), 'Save'))

        assert parent_item.menu_down_image.get_height() == 20 + 20 + 20

    def test_add_menu_recalculates_image_dimensions(self):
        """Test MenuItem.add_menu sizes the dropped-down image to hold the item and its menu."""
        parent_item = self._create_menuitem_with_x((0, 0, 100, 20), 'FileMenu')
        sub_item = self._create_menuitem_with_x((0, 0, 80, 20), 'Open')
        item_height = parent_item.rect.height

        parent_item.add_menu(sub_item)

        # Wide enough for the widest sub-item (plus 20) times 2.5; tall enough for both
        expected_width = int((sub_item.rect.width + 20) * 2.5)
        assert parent_item.menu_down_image.get_size() == (expected_width, item_height + 20)
        assert parent_item.menu_down_rect.size == parent_item.menu_down_image.get_size()

    def test_add_menu_updates_rect_dimensions(self):
        """Test MenuItem.add_menu updates parent rect width and height."""
        parent_item = self._create_menuitem_with_x((0, 0, 100, 20), 'FileMenu')
        sub_item = self._create_menuitem_with_x((0, 0, 80, 20), 'Open')
        parent_item.add_menu(sub_item)

        # After adding menu, rect should have been resized
        assert parent_item.rect.width == parent_item.menu_down_rect.width
        assert parent_item.rect.height == parent_item.menu_down_rect.height

    def test_add_menu_multiple_items_layouts_correctly(self):
        """Test MenuItem.add_menu stacks multiple sub items one below the other."""
        parent_item = self._create_menuitem_with_x((10, 5, 100, 20), 'FileMenu')
        sub_items = []
        for name in ['New', 'Open', 'Save', 'Close']:
            item = self._create_menuitem_with_x((0, 0, 80, 20), name)
            parent_item.add_menu(item)
            sub_items.append(item)

        assert list(parent_item.menu_items) == ['New', 'Open', 'Save', 'Close']
        tops = [item.rect.y for item in sub_items]
        assert tops == sorted(tops)
        assert len(set(tops)) == len(tops)

    def test_add_menu_whose_items_have_no_rect_keeps_the_item_size(self):
        """A sub-menu without a rect takes no room: the dropped-down menu is the item's size.

        max() over the items' rects used to raise ValueError when none had one (BUGS.md #136).
        """
        parent_item = self._create_menuitem_with_x((0, 0, 100, 20), 'FileMenu')
        sub_item = self._create_menuitem_with_x((0, 0, 80, 20), 'Open')
        sub_item.rect = None
        width_before = parent_item.rect.width
        height_before = parent_item.rect.height

        parent_item.add_menu(sub_item)

        assert 'Open' in parent_item.menu_items
        assert parent_item.menu_down_image.get_size() == (width_before, height_before)


class _RecordingParent:
    """A parent widget that records each call its children make to the handlers it is given."""

    def __init__(self, *handler_names, **attributes):
        """Give the parent the named handlers and the attributes.

        Args:
            *handler_names: The handlers to record calls to (e.g. 'on_confirm_event').
            **attributes: Other attributes a child reads (e.g. slider_input_format).
        """
        self.calls = []
        for handler_name in handler_names:
            setattr(self, handler_name, self._recorder(handler_name))
        for attribute_name, value in attributes.items():
            setattr(self, attribute_name, value)

    def _recorder(self, handler_name):
        """Return a handler that records its calls under its name.

        Returns:
            Callable: The recording handler.
        """

        def record(*args, **kwargs):
            self.calls.append((handler_name, args, kwargs))

        return record


def _text_sprite(*, text='Hello', **keyword_arguments):
    """Build a TextSprite at the shared test position and size.

    Returns:
        TextSprite: The text sprite.
    """
    return TextSprite(
        x=TEST_X,
        y=TEST_Y,
        width=TEST_WIDTH,
        height=TEST_HEIGHT,
        text=text,
        groups=pygame.sprite.LayeredDirty(),
        **keyword_arguments,
    )


class TestTextSpritePropertyAccessors:
    """Test TextSprite property accessors and cursor blinking."""

    def test_text_sprite_x_setter(self):
        """Test TextSprite x property setter updates rect and dirty flag."""
        text_sprite = _text_sprite()
        text_sprite.x = 50
        assert text_sprite.x == 50
        assert text_sprite.rect.x == 50
        assert text_sprite.dirty == 2

    def test_text_sprite_y_setter(self):
        """Test TextSprite y property setter updates rect and dirty flag."""
        text_sprite = _text_sprite()
        text_sprite.y = 100
        assert text_sprite.y == 100
        assert text_sprite.rect.y == 100
        assert text_sprite.dirty == 2

    def test_text_sprite_text_setter_same_value_no_update(self):
        """Test TextSprite text setter does not re-render when the value is the same."""
        text_sprite = _text_sprite()
        image_before = text_sprite.image
        text_sprite.dirty = 0

        text_sprite.text = 'Hello'  # Same value

        # Rendering makes a new image; the same text keeps the old one and the dirty flag
        assert text_sprite.image is image_before
        assert text_sprite.dirty == 0

    def test_text_sprite_update_active_cursor_blink(self):
        """Test TextSprite update with active state toggles cursor."""
        text_sprite = _text_sprite()
        text_sprite.is_active = True
        text_sprite._cursor_timer = 29  # Just before blink threshold

        text_sprite.update()
        # After update, timer should have rolled over and cursor toggled
        assert text_sprite._cursor_timer == 0
        assert text_sprite._cursor_visible is False
        assert text_sprite.dirty == 2

    def test_text_sprite_active_draws_a_cursor_only_while_it_is_visible(self):
        """An active text sprite draws its cursor in the visible half of the blink only."""
        text_sprite = _text_sprite()
        text_sprite.is_active = True
        text_sprite._cursor_visible = False
        text_sprite.update_text('Hello')
        without_cursor = _lit_pixel_count(text_sprite.image)

        text_sprite._cursor_visible = True
        text_sprite.update_text('Hello')

        assert _lit_pixel_count(text_sprite.image) > without_cursor

    def test_text_sprite_update_inactive(self):
        """Test TextSprite update when not active sets dirty to 1 and draws no cursor."""
        text_sprite = _text_sprite()
        text_sprite.is_active = False
        text_pixels = _lit_pixel_count(text_sprite.image)

        text_sprite.update()

        assert text_sprite.dirty == 1
        assert _lit_pixel_count(text_sprite.image) == text_pixels

    def test_text_sprite_transparent_background(self):
        """Test TextSprite with transparent background (alpha=0) draws only its text."""
        text_sprite = _text_sprite(background_color=(0, 0, 0, 0))

        # The corner is transparent; the text is drawn opaque
        assert text_sprite.image.get_at((0, 0)).a == 0
        assert _lit_pixel_count(text_sprite.image) > 0

    def test_text_sprite_on_mouse_motion_event(self):
        """Test TextSprite on_mouse_motion_event changes nothing (hover disabled)."""
        text_sprite = _text_sprite()
        text_sprite.dirty = 0
        drawn_pixels = _rgb_bytes(text_sprite.image)

        text_sprite.on_mouse_motion_event(_mouse_event(pygame.MOUSEMOTION, (15, 25)))

        assert text_sprite.dirty == 0
        assert _rgb_bytes(text_sprite.image) == drawn_pixels

    def test_text_sprite_text_box_self_reference(self):
        """Test TextSprite text_box is self-referential for compatibility."""
        text_sprite = _text_sprite()
        assert text_sprite.text_box is text_sprite


class TestButtonSpriteExtended:
    """Extended coverage tests for ButtonSprite."""

    def test_button_x_property_setter(self):
        """Test ButtonSprite x property setter moves the button and its label."""
        button = ButtonSprite(x=10, y=20, width=100, height=40, name='TestBtn')
        button.x = 50
        assert button.x == 50
        assert button.rect.x == 50
        assert button.text.rect.x == 50
        assert button.dirty == 1

    def test_button_y_property_setter(self):
        """Test ButtonSprite y property setter moves the button and its label."""
        button = ButtonSprite(x=10, y=20, width=100, height=40, name='TestBtn')
        button.y = 80
        assert button.y == 80
        assert button.rect.y == 80
        assert button.text.rect.y == 80
        assert button.dirty == 1

    def test_button_update_nested_sprites(self):
        """Test ButtonSprite update_nested_sprites propagates dirty flag."""
        button = ButtonSprite(x=10, y=20, width=100, height=40, name='TestBtn')
        button.dirty = 2
        button.update_nested_sprites()
        assert button.text.dirty == 2

    def test_button_callbacks_initialized_to_empty_dict(self):
        """Test ButtonSprite callbacks attribute is initialized to an empty dict.

        The base Sprite class initializes callbacks as {} (empty dict).
        """
        button = ButtonSprite(x=10, y=20, width=100, height=40, name='TestBtn')
        assert button.callbacks == {}


class TestCheckboxSpriteCoverage:
    """Coverage tests for CheckboxSprite."""

    def test_checkbox_initialization(self):
        """Test CheckboxSprite initialization."""
        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name='TestCheck')
        assert checkbox.checked is False
        assert checkbox.color == (128, 128, 128)

    def test_checkbox_toggle_on_click(self):
        """Test CheckboxSprite toggles checked state on left mouse button up."""
        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name='TestCheck')
        event = _mouse_event(pygame.MOUSEBUTTONUP, (20, 30))

        assert checkbox.checked is False
        checkbox.on_left_mouse_button_up_event(event)
        assert checkbox.checked is True
        assert checkbox.dirty == 1

        checkbox.on_left_mouse_button_up_event(event)
        assert checkbox.checked is False

    def test_checkbox_update_unchecked(self):
        """Test an unchecked CheckboxSprite draws a grey border around a black inside."""
        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name='TestCheck')
        checkbox.image.fill((255, 255, 255))
        checkbox.checked = False

        checkbox.update()

        assert _rgb_at(checkbox.image, (0, 0)) == checkbox.color
        assert _rgb_at(checkbox.image, (19, 19)) == checkbox.color
        assert _pixel_count_of(checkbox.image, (0, 0, 0), (1, 1, 18, 18)) == 18 * 18

    def test_checkbox_update_checked(self):
        """Test a checked CheckboxSprite draws an X corner to corner inside its border."""
        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name='TestCheck')
        checkbox.update()
        checkbox.checked = True

        checkbox.update()

        assert _rgb_at(checkbox.image, (0, 0)) == checkbox.color
        for diagonal_point in [(5, 5), (14, 14), (5, 14), (14, 5)]:
            assert _rgb_at(checkbox.image, diagonal_point) == checkbox.color
        # Off the diagonals the inside stays black
        assert _rgb_at(checkbox.image, (10, 3)) == (0, 0, 0)

    def test_checkbox_left_mouse_down_does_nothing(self):
        """Test CheckboxSprite on_left_mouse_button_down_event is a no-op."""
        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name='TestCheck')
        checkbox.dirty = 0
        initial_checked = checkbox.checked

        checkbox.on_left_mouse_button_down_event(_mouse_event(pygame.MOUSEBUTTONDOWN, (20, 30)))

        assert checkbox.checked == initial_checked
        assert checkbox.background_color == checkbox.inactive_color
        assert checkbox.dirty == 0


class TestInputBoxCoverage:
    """Coverage tests for InputBox."""

    def test_inputbox_initialization(self):
        """Test InputBox initialization renders its text in its colour."""
        inputbox = InputBox(x=10, y=20, width=200, height=30, text='initial')
        assert inputbox.text == 'initial'
        assert inputbox.is_active is False
        assert inputbox.rect == pygame.Rect(10, 20, 200, 30)
        assert inputbox.image.get_size() == (200, 30)
        assert _lit_pixel_count(inputbox.text_image) > 0

    def test_inputbox_activate_deactivate(self):
        """Test InputBox activate and deactivate methods."""
        inputbox = InputBox(x=10, y=20, width=200, height=30)
        inputbox.activate()
        assert inputbox.is_active is True
        assert inputbox.dirty == 2

        inputbox.deactivate()
        assert inputbox.is_active is False
        assert inputbox.dirty == 0

    def test_inputbox_render(self):
        """Test InputBox render redraws its text image from the current text, in white."""
        inputbox = InputBox(x=10, y=20, width=200, height=30, text='')
        inputbox.text = 'hello'

        inputbox.render()

        assert inputbox.text_image.get_width() == inputbox.font.size('hello')[0]
        assert _pixel_count_of(inputbox.text_image, (255, 255, 255)) > 0

    def test_inputbox_on_mouse_up_activates(self):
        """Test InputBox on_mouse_up_event activates the input box."""
        inputbox = InputBox(x=10, y=20, width=200, height=30)
        inputbox.on_mouse_up_event(_mouse_event(pygame.MOUSEBUTTONUP, (20, 30)))
        assert inputbox.is_active is True

    def test_inputbox_key_up_tab_deactivates(self):
        """Test InputBox on_key_up_event with Tab key deactivates and turns on key repeat."""
        inputbox = InputBox(x=10, y=20, width=200, height=30)
        inputbox.activate()
        inputbox.on_key_up_event(_key_up(key=pygame.K_TAB))
        assert inputbox.is_active is False
        # Keys held in an active input box repeat after 200 ms
        assert pygame.key.get_repeat()[0] == 200

    def test_inputbox_key_up_escape_deactivates(self):
        """Test InputBox on_key_up_event with Escape key deactivates."""
        inputbox = InputBox(x=10, y=20, width=200, height=30)
        inputbox.activate()
        inputbox.on_key_up_event(_key_up(key=pygame.K_ESCAPE))
        assert inputbox.is_active is False

    def test_inputbox_key_down_backspace(self):
        """Test InputBox on_key_down_event with backspace removes character."""
        inputbox = InputBox(x=10, y=20, width=200, height=30, text='hello')
        inputbox.activate()
        inputbox.on_key_down_event(_key_down(key=pygame.K_BACKSPACE))
        assert inputbox.text == 'hell'
        assert inputbox.text_image.get_width() == inputbox.font.size('hell')[0]

    def test_inputbox_key_down_unicode_input(self):
        """Test InputBox on_key_down_event with unicode character input."""
        inputbox = InputBox(x=10, y=20, width=200, height=30, text='')
        inputbox.activate()
        inputbox.on_key_down_event(_key_down(key=pygame.K_a, unicode='a'))
        assert inputbox.text == 'a'
        assert inputbox.text_image.get_width() == inputbox.font.size('a')[0]

    def test_inputbox_key_down_return_triggers_confirm(self):
        """Test InputBox on_key_down_event with Return triggers parent confirm."""
        parent = _RecordingParent('on_confirm_event', x=0, y=0)
        inputbox = InputBox(x=10, y=20, width=200, height=30, text='test', parent=parent)
        inputbox.activate()
        event = _key_down(key=pygame.K_RETURN, unicode='\r')
        inputbox.on_key_down_event(event)
        assert parent.calls == [('on_confirm_event', (), {'event': event, 'trigger': inputbox})]
        assert inputbox.text == 'test'

    def test_inputbox_key_down_colon_via_shift_semicolon(self):
        """Test InputBox on_key_down_event with Shift+semicolon produces colon."""
        inputbox = InputBox(x=10, y=20, width=200, height=30, text='')
        inputbox.activate()
        inputbox.on_key_down_event(
            _key_down(key=pygame.K_SEMICOLON, unicode='', mod=pygame.KMOD_SHIFT)
        )
        assert inputbox.text == ':'

    def test_inputbox_on_input_box_submit_no_parent(self):
        """Test InputBox submit event with no parent changes nothing."""
        inputbox = InputBox(x=10, y=20, width=200, height=30, text='test')
        inputbox.parent = None
        inputbox.on_input_box_submit_event(_key_down(key=pygame.K_RETURN, unicode='\r'))
        assert inputbox.text == 'test'

    def test_inputbox_on_input_box_submit_with_parent(self):
        """Test InputBox submit event passes the input box to its parent."""
        parent = _RecordingParent('on_input_box_submit_event', x=0, y=0)
        inputbox = InputBox(x=10, y=20, width=200, height=30, text='test', parent=parent)
        inputbox.on_input_box_submit_event(_key_down(key=pygame.K_RETURN, unicode='\r'))
        assert parent.calls == [('on_input_box_submit_event', (), {'control': inputbox})]

    def test_inputbox_update(self):
        """Test InputBox update draws its text inside a border in its colour."""
        inputbox = InputBox(x=10, y=20, width=200, height=30, text='hello')
        inputbox.image.fill(PLACEHOLDER_FILL)

        inputbox.update()

        assert _rgb_at(inputbox.image, (0, 0)) == inputbox.color
        assert _rgb_at(inputbox.image, (199, 29)) == inputbox.color
        assert _rgb_at(inputbox.image, (1, 1)) == (0, 0, 0)
        assert _pixel_count_of(inputbox.image, PLACEHOLDER_FILL) == 0
        # The text, drawn at (4, 4), lights pixels inside the border
        assert _lit_pixel_count(inputbox.image, (2, 2, 196, 26)) > 0

    def test_inputbox_text_is_white_before_and_after_a_render(self):
        """The first text is drawn white, as render() redraws it (BUGS.md #178 item 30)."""
        inputbox = InputBox(x=10, y=20, width=200, height=30, text='hello')
        first_text_colors = {
            inputbox.text_image.get_at((x, y))[:3]
            for x in range(inputbox.text_image.get_width())
            for y in range(inputbox.text_image.get_height())
            if inputbox.text_image.get_at((x, y))[3] == 255
        }

        inputbox.render()

        assert first_text_colors == {(255, 255, 255)}
        assert pygame.image.tobytes(inputbox.text_image, 'RGBA') == pygame.image.tobytes(
            InputBox(x=10, y=20, width=200, height=30, text='hello').text_image, 'RGBA'
        )


class TestTextBoxSpriteCoverage:
    """Coverage tests for TextBoxSprite."""

    def test_textbox_update_nested_sprites(self):
        """Test TextBoxSprite update_nested_sprites propagates dirty flag."""
        textbox = TextBoxSprite(x=10, y=20, width=200, height=30, name='TestTB')
        textbox.dirty = 2
        textbox.update_nested_sprites()
        assert textbox.text_box.dirty == 2

    def test_textbox_update_with_border(self):
        """Test TextBoxSprite update draws a grey border border_width pixels wide."""
        textbox = TextBoxSprite(x=10, y=20, width=200, height=30, name='TestTB')
        textbox.border_width = 2
        textbox.image.fill(PLACEHOLDER_FILL)

        textbox.update()

        for border_point in [(0, 0), (1, 1), (199, 29), (198, 28)]:
            assert _rgb_at(textbox.image, border_point) == (128, 128, 128)
        assert _rgb_at(textbox.image, (2, 2)) != (128, 128, 128)

    def test_text_box_at_the_origin_shows_its_text(self):
        """A TextBoxSprite at (0, 0) draws its text sprite's text on its own image."""
        textbox = TextBoxSprite(x=0, y=0, width=200, height=30, name='TestTB')
        textbox.text_box.text = 'Hello'
        textbox.image.fill(PLACEHOLDER_FILL)

        textbox.update()

        assert _lit_pixel_count(textbox.image, (1, 1, 198, 28)) > 0

    def test_text_box_away_from_the_origin_shows_its_text(self):
        """A TextBoxSprite at (10, 20) draws its text sprite's text on its own image."""
        textbox = TextBoxSprite(x=10, y=20, width=200, height=30, name='TestTB')
        textbox.text_box.text = 'Hello'
        textbox.image.fill(PLACEHOLDER_FILL)

        textbox.update()

        assert _lit_pixel_count(textbox.image, (1, 1, 198, 28)) > 0
        assert _pixel_count_of(textbox.image, PLACEHOLDER_FILL) == 0


class TestColorWellSpriteCoverage:
    """Coverage tests for ColorWellSprite."""

    def test_color_well_rgba_setter(self):
        """Test ColorWellSprite active_color setter with 4-tuple RGBA."""
        color_well = ColorWellSprite(x=10, y=20, width=100, height=60, name='TestCW')
        color_well.active_color = (10, 20, 30, 40)
        assert color_well.red == 10
        assert color_well.green == 20
        assert color_well.blue == 30
        assert color_well.alpha == 40

    def test_color_well_rgb_setter_defaults_alpha(self):
        """Test ColorWellSprite active_color setter with 3-tuple defaults alpha to 255."""
        color_well = ColorWellSprite(x=10, y=20, width=100, height=60, name='TestCW')
        color_well.active_color = (10, 20, 30)
        assert color_well.alpha == 255

    def test_color_well_update(self):
        """Test ColorWellSprite update draws a border and fills with the colour and its alpha."""
        color_well = ColorWellSprite(x=10, y=20, width=100, height=60, name='TestCW')
        color_well.active_color = (255, 0, 0, 100)

        color_well.update()

        assert _rgb_at(color_well.image, (0, 0)) == (128, 128, 255)
        assert _rgb_at(color_well.image, (99, 59)) == (128, 128, 255)
        # The colour keeps its alpha on the well's per-pixel-alpha image
        assert tuple(color_well.image.get_at((50, 30))) == (255, 0, 0, 100)

    def test_color_well_update_nested_sprites(self):
        """Test ColorWellSprite update_nested_sprites is a no-op."""
        color_well = ColorWellSprite(x=10, y=20, width=100, height=60, name='TestCW')
        color_well.dirty = 0
        drawn_pixels = _rgb_bytes(color_well.image)

        color_well.update_nested_sprites()

        assert color_well.dirty == 0
        assert _rgb_bytes(color_well.image) == drawn_pixels


def _input_dialog(**keyword_arguments):
    """Build a 400x200 InputDialog at (100, 100).

    Returns:
        InputDialog: The dialog.
    """
    return InputDialog(
        x=100,
        y=100,
        width=400,
        height=200,
        name='TestDialog',
        groups=pygame.sprite.LayeredDirty(),
        **keyword_arguments,
    )


class TestInputDialogCoverage:
    """Coverage tests for InputDialog widget."""

    def test_input_dialog_initialization(self):
        """Test InputDialog lays out its text, input box and buttons inside itself."""
        dialog = _input_dialog(dialog_text='Enter value:', confirm_text='OK', cancel_text='Cancel')

        assert dialog.dialog_text_sprite.rect.topleft == (120, 120)
        assert dialog.input_box.rect == pygame.Rect(120, 190, 360, 20)
        assert dialog.cancel_button.rect.topleft == (405, 260)
        assert dialog.confirm_button.rect.topleft == (320, 260)
        assert dialog.input_box.is_active is True
        for child in [
            dialog.dialog_text_sprite,
            dialog.input_box,
            dialog.cancel_button,
            dialog.confirm_button,
        ]:
            assert dialog.rect.contains(child.rect)

    def test_input_dialog_custom_text(self):
        """Test InputDialog with custom dialog text (and no groups: it makes its own)."""
        dialog = InputDialog(
            x=100,
            y=100,
            width=400,
            height=200,
            name='TestDialog',
            dialog_text='Custom prompt',
            confirm_text='Save',
            cancel_text='Abort',
        )
        assert dialog.dialog_text_sprite.text_box.text == 'Custom prompt'
        assert dialog.confirm_button.name == 'Save'
        assert dialog.cancel_button.name == 'Abort'
        assert dialog.confirm_button.text.text == 'Save'
        assert dialog.cancel_button.text.text == 'Abort'

    def test_input_dialog_update_draws_its_border_and_buttons(self):
        """InputDialog.update draws its grey border and each button's border where it sits."""
        dialog = _input_dialog()
        dialog.image.fill(PLACEHOLDER_FILL)

        dialog.update()

        assert _rgb_at(dialog.image, (0, 0)) == (128, 128, 128)
        assert _rgb_at(dialog.image, (399, 199)) == (128, 128, 128)
        for button in [dialog.cancel_button, dialog.confirm_button]:
            button_corner = (button.rect.x - dialog.rect.x, button.rect.y - dialog.rect.y)
            assert _rgb_at(dialog.image, button_corner) == button.border_color
        # The input box's border is drawn where the input box sits
        input_box_corner = (
            dialog.input_box.rect.x - dialog.rect.x,
            dialog.input_box.rect.y - dialog.rect.y,
        )
        dialog.input_box.update()
        dialog.update()
        assert _rgb_at(dialog.image, input_box_corner) == dialog.input_box.color
        assert _pixel_count_of(dialog.image, PLACEHOLDER_FILL) == 0


def _slider(*, name='TestSlider', parent=None, width=200, height=10):
    """Build a slider at (10, 20).

    Returns:
        SliderSprite: The slider.
    """
    return SliderSprite(
        x=10,
        y=20,
        width=width,
        height=height,
        name=name,
        parent=parent,
        groups=pygame.sprite.LayeredDirty(),
    )


def _return_key():
    """Build the Enter key event that commits slider text.

    Returns:
        HashableEvent: The event.
    """
    return _key_down(key=pygame.K_RETURN, unicode='\r')


class TestSliderSpriteCoverage:
    """Additional coverage tests for SliderSprite."""

    def test_slider_update_method(self):
        """Test a dirty SliderSprite's update redraws its grey gradient."""
        slider = _slider()
        slider.image.fill(PLACEHOLDER_FILL)
        slider.dirty = 2

        slider.update()

        assert _rgb_at(slider.image, (0, 5)) == (0, 0, 0)
        right_end_intensity = int((199 / 200) * 255)
        assert _rgb_at(slider.image, (199, 5)) == (right_end_intensity,) * 3
        assert _pixel_count_of(slider.image, PLACEHOLDER_FILL) == 0

    def test_slider_update_while_clean_keeps_its_image(self):
        """A clean SliderSprite's update leaves its gradient alone."""
        slider = _slider()
        slider.image.fill(PLACEHOLDER_FILL)
        slider.dirty = 0

        slider.update()

        assert _rgb_at(slider.image, (199, 5)) == PLACEHOLDER_FILL

    def test_slider_restore_original_value(self):
        """Test SliderSprite _restore_original_value restores text."""
        slider = _slider()
        slider.value = 100
        slider.original_value = 100
        slider.text_sprite.is_active = True
        slider.text_sprite.text = '200'
        slider._restore_original_value()
        assert slider.text_sprite.text == '100'
        assert slider.text_sprite.is_active is False

    def test_slider_commit_text_empty(self):
        """Test SliderSprite commit_text with empty text restores."""
        slider = _slider()
        slider.value = 50
        slider.original_value = 50
        slider.text_sprite.text = '  '
        slider.text_sprite.is_active = True
        slider.commit_text(event=_return_key())
        assert slider.text_sprite.text == '50'

    def test_slider_commit_text_hex_value(self):
        """Test SliderSprite commit_text with hex input."""
        slider = _slider()
        slider.text_sprite.text = 'ff'
        slider.text_sprite.is_active = True
        slider.commit_text(event=_return_key())
        assert slider.value == 255
        assert slider.slider_knob.rect.x == slider.max_x

    def test_slider_handle_text_character_max_length(self):
        """Test SliderSprite _handle_text_character_input respects max length."""
        slider = _slider()
        slider.text_sprite.text = '12'
        slider.text_sprite.is_active = True
        slider._handle_text_character_input(_key_down(key=pygame.K_3, unicode='3'))
        assert slider.text_sprite.text == '123'

        # Try adding a 4th character - should be truncated to 3
        slider._handle_text_character_input(_key_down(key=pygame.K_4, unicode='4'))
        assert slider.text_sprite.text == '123'

    def test_slider_commit_text_out_of_range_restores(self):
        """Test SliderSprite commit_text with out-of-range value restores."""
        slider = _slider()
        slider.value = 50
        slider.original_value = 50
        slider.text_sprite.text = '999'
        slider.text_sprite.is_active = True
        slider.commit_text(event=_return_key())
        assert slider.text_sprite.text == '50'
        assert slider.value == 50

    def test_slider_commit_text_invalid_value_restores(self):
        """Test SliderSprite commit_text with invalid input restores."""
        slider = _slider()
        slider.value = 50
        slider.original_value = 50
        slider.text_sprite.text = 'xyz'
        slider.text_sprite.is_active = True
        slider.commit_text(event=_return_key())
        assert slider.text_sprite.text == '50'
        assert slider.value == 50

    def test_slider_handle_text_character_backspace(self):
        """Test SliderSprite _handle_text_character_input handles backspace."""
        slider = _slider()
        slider.text_sprite.text = '12'
        slider._handle_text_character_input(_key_down(key=pygame.K_BACKSPACE))
        assert slider.text_sprite.text == '1'

    def test_slider_commit_text_with_hex_format(self):
        """Test SliderSprite commit_text uses hex format when parent expects it."""
        parent = _RecordingParent('on_slider_event', slider_input_format='%X')
        slider = _slider(name='R', parent=parent)
        # On the hex tab digits without a-f are hex too (BUGS.md #110 item 3)
        slider.text_sprite.text = '80'
        slider.text_sprite.is_active = True
        event = _return_key()
        slider.commit_text(event=event)
        assert slider.value == 128
        assert slider.text_sprite.text == '80'
        [(handler_name, _arguments, keyword_arguments)] = parent.calls
        assert handler_name == 'on_slider_event'
        assert keyword_arguments['event'] is event
        assert (keyword_arguments['trigger'].name, keyword_arguments['trigger'].value) == (
            'R',
            128,
        )


def _multiline_text_box(*, x=100, y=100, width=300, height=200, text=''):
    """Build a MultiLineTextBox in its own real sprite group, with its text set.

    The text is set after construction, as the editor does, so it is wrapped and scrolled.

    Returns:
        MultiLineTextBox: The text box.
    """
    text_box = MultiLineTextBox(
        x=x, y=y, width=width, height=height, groups=pygame.sprite.LayeredDirty()
    )
    text_box.text = text
    return text_box


class _UnavailableClipboard:
    """A clipboard that cannot be used (a machine without a clipboard program)."""

    def copy(self, text):
        """Fail as pyperclip's clipboard does without a clipboard program.

        Raises:
            ClipboardUnavailableError: Always.
        """
        raise ClipboardUnavailableError(text)

    def paste(self):
        """Fail as pyperclip's clipboard does without a clipboard program.

        Raises:
            ClipboardUnavailableError: Always.
        """
        raise ClipboardUnavailableError


class TestMultiLineTextBoxClipboard:
    """Test MultiLineTextBox clipboard operations (copy, paste, cut).

    Every test has an in-process clipboard (tests/harness.py): none may read or write the
    machine's clipboard.
    """

    @pytest.fixture
    def text_box(self):
        """Create a MultiLineTextBox for testing.

        Returns:
            A MultiLineTextBox instance.
        """
        return _multiline_text_box(x=10, y=10, width=300, height=200, text='Hello World')

    @pytest.fixture
    def clipboard(self, in_process_clipboard):
        """Return the test's clipboard.

        Returns:
            InProcessClipboard: The clipboard the text box uses.
        """
        return in_process_clipboard

    def test_handle_copy_full_text(self, text_box, clipboard):
        """Test _handle_copy copies full text when no selection."""
        text_box.selection_start = None
        text_box.selection_end = None
        text_box._handle_copy()
        assert clipboard.text == 'Hello World'
        assert text_box._original_text == 'Hello World'

    def test_handle_copy_selected_text(self, text_box, clipboard):
        """Test _handle_copy copies selected text."""
        text_box.selection_start = 0
        text_box.selection_end = 5
        text_box._handle_copy()
        assert clipboard.text == 'Hello'

    def test_handle_paste_inserts_text(self, text_box, clipboard):
        """Test _handle_paste inserts clipboard text at cursor."""
        clipboard.text = 'pasted'
        text_box.cursor_pos = 5
        text_box._handle_paste()
        assert text_box._original_text == 'Hellopasted World'

    def test_handle_paste_leaves_the_cursor_after_the_pasted_text(self, text_box, clipboard):
        """Pasting 'pasted' at position 5 leaves the cursor at 11, right after it."""
        clipboard.text = 'pasted'
        text_box.cursor_pos = 5

        text_box._handle_paste()

        assert text_box.cursor_pos == len('Hellopasted')

    def test_handle_paste_no_clipboard(self, text_box, clipboard):
        """Test _handle_paste handles empty clipboard."""
        clipboard.text = ''
        original_text = text_box._original_text
        text_box._handle_paste()
        assert text_box._original_text == original_text

    def test_handle_cut_full_text(self, text_box, clipboard):
        """Test _handle_cut cuts all text when no selection."""
        text_box.selection_start = None
        text_box.selection_end = None
        text_box._handle_cut()
        assert clipboard.text == 'Hello World'
        assert not text_box._original_text
        assert text_box.cursor_pos == 0

    def test_handle_cut_selected_text(self, text_box, clipboard):
        """Test _handle_cut cuts selected text."""
        text_box.selection_start = 0
        text_box.selection_end = 5
        text_box._handle_cut()
        assert clipboard.text == 'Hello'
        assert text_box._original_text == ' World'
        assert text_box.selection_start is None
        assert text_box.selection_end is None

    @pytest.mark.parametrize('operation', ['copy', 'paste', 'cut'])
    def test_an_unavailable_clipboard_keeps_the_text(self, text_box, operation):
        """No clipboard program (headless Linux without xclip/xsel/wl-clipboard): no crash."""
        install_clipboard(clipboard=_UnavailableClipboard())
        text_box.selection_start = 0
        text_box.selection_end = 5
        original_text = text_box._original_text

        getattr(text_box, f'_handle_{operation}')()

        assert text_box._original_text == original_text

    def test_copy_and_paste_round_trip_through_the_clipboard(self, text_box, clipboard):
        """Copy, then paste, through a clipboard (an in-memory one: never the machine's)."""
        clipboard.text = 'what was there before'
        text_box.text = 'Round trip'
        text_box.selection_start = 0
        text_box.selection_end = len('Round')
        text_box._handle_copy()
        text_box.text = ''
        text_box.cursor_pos = 0
        text_box.selection_start = None
        text_box.selection_end = None

        text_box._handle_paste()

        assert text_box._original_text == 'Round'


class TestMultiLineTextBoxClipboardKeys:
    """Test the Ctrl key shortcuts MultiLineTextBox dispatches to clipboard operations.

    Every test has an in-process clipboard (tests/harness.py): none may read or write the
    machine's clipboard.
    """

    @pytest.fixture
    def text_box(self):
        """Create a MultiLineTextBox for testing.

        Returns:
            A MultiLineTextBox instance.
        """
        return _multiline_text_box(x=10, y=10, width=300, height=200, text='Hello World')

    @pytest.fixture
    def clipboard(self, in_process_clipboard):
        """Return the test's clipboard.

        Returns:
            InProcessClipboard: The clipboard the text box uses.
        """
        return in_process_clipboard

    def test_clipboard_operation_copy_key(self, text_box, clipboard):
        """Test _handle_clipboard_operation dispatches Ctrl+C to copy."""
        result = text_box._handle_clipboard_operation(
            _key_down(key=pygame.K_c, unicode='c'), is_ctrl=True
        )
        assert result is True
        assert clipboard.text == 'Hello World'

    def test_clipboard_operation_paste_key(self, text_box, clipboard):
        """Test _handle_clipboard_operation dispatches Ctrl+V to paste."""
        clipboard.text = '!'
        result = text_box._handle_clipboard_operation(
            _key_down(key=pygame.K_v, unicode='v'), is_ctrl=True
        )
        assert result is True
        assert text_box._original_text == 'Hello World!'

    def test_clipboard_operation_cut_key(self, text_box, clipboard):
        """Test _handle_clipboard_operation dispatches Ctrl+X to cut."""
        result = text_box._handle_clipboard_operation(
            _key_down(key=pygame.K_x, unicode='x'), is_ctrl=True
        )
        assert result is True
        assert clipboard.text == 'Hello World'
        assert not text_box._original_text

    def test_clipboard_operation_select_all(self, text_box):
        """Test _handle_clipboard_operation handles Ctrl+A select all."""
        result = text_box._handle_clipboard_operation(
            _key_down(key=pygame.K_a, unicode='a'), is_ctrl=True
        )
        assert result is True
        assert text_box.selection_start == 0
        assert text_box.selection_end == len(text_box._original_text)
        assert text_box.cursor_pos == len(text_box._original_text)

    def test_clipboard_operation_not_ctrl(self, text_box, clipboard):
        """Test _handle_clipboard_operation returns False when not ctrl."""
        result = text_box._handle_clipboard_operation(
            _key_down(key=pygame.K_c, unicode='c'), is_ctrl=False
        )
        assert result is False
        assert not clipboard.text

    def test_clipboard_operation_unknown_key_returns_false(self, text_box):
        """Test _handle_clipboard_operation returns False for unknown ctrl key."""
        result = text_box._handle_clipboard_operation(
            _key_down(key=pygame.K_z, unicode='z'), is_ctrl=True
        )
        assert result is False


class TestMultiLineTextBoxDeactivation:
    """Test MultiLineTextBox activation and deactivation."""

    @pytest.fixture
    def text_box(self):
        """Create a MultiLineTextBox for testing.

        Returns:
            A MultiLineTextBox instance.
        """
        return _multiline_text_box(text='Test content')

    def test_deactivate_method_sets_active_false(self, text_box):
        """Test deactivate method sets active to False and stops key repeat."""
        text_box.activate()
        text_box.deactivate()
        assert text_box.is_active is False
        assert pygame.key.get_repeat() == (0, 0)

    def test_mouse_down_inside_activates(self, text_box):
        """Clicking inside activates the text box and restarts its blink on the frame clock."""
        text_box.is_active = False
        advance_frame_clock(seconds=1.25)
        # Position inside the text box (rect starts at 100, 100 with 300x200)
        text_box.on_left_mouse_button_down_event(_mouse_event(pygame.MOUSEBUTTONDOWN, (150, 150)))
        assert text_box.is_active is True
        assert text_box.cursor_blink_time == 1250
        # Held keys repeat after 500 ms, every 50 ms, while editing
        assert pygame.key.get_repeat() == (500, 50)

    def test_key_down_escape_deactivates(self, text_box):
        """Test pressing Escape deactivates the text box."""
        text_box.activate()
        text_box.on_key_down_event(_key_down(key=pygame.K_ESCAPE, unicode='\x1b'))
        assert text_box.is_active is False
        assert text_box.dirty == 2
        assert pygame.key.get_repeat() == (0, 0)

    def test_activate_method(self, text_box):
        """Test activate method enables text input with key repeat."""
        text_box.is_active = False
        text_box.activate()
        assert text_box.is_active is True
        assert pygame.key.get_repeat()[0] == 200

    def test_deactivate_method(self, text_box):
        """Test deactivate method disables text input."""
        text_box.is_active = True
        text_box.deactivate()
        assert text_box.is_active is False


def _scrollable_text_box():
    """Build a 300x200 MultiLineTextBox at (100, 100) holding 50 lines, scrolled to the top.

    Returns:
        MultiLineTextBox: The text box, whose scrollbar is visible.
    """
    text_box = _multiline_text_box(text='\n'.join(f'Line {index}' for index in range(50)))
    text_box.scroll_offset = 0
    text_box.scrollbar.update(50, text_box.visible_lines, 0)
    assert text_box.scrollbar.is_visible
    return text_box


def _scrollbar_thumb_center_on_screen(text_box):
    """Return the screen position of the centre of a text box's scrollbar thumb.

    Returns:
        tuple: The (x, y) position.
    """
    thumb_center = text_box.scrollbar.get_thumb_rect().center
    return (thumb_center[0] + text_box.rect.x, thumb_center[1] + text_box.rect.y)


class TestMultiLineTextBoxScrollbar:
    """Test MultiLineTextBox scrollbar mouse events."""

    def test_left_mouse_button_up_scrollbar_handled(self):
        """A drag of the scrollbar thumb, then the release, scroll the text box with it."""
        text_box = _scrollable_text_box()
        thumb_center = _scrollbar_thumb_center_on_screen(text_box)
        text_box.on_left_mouse_button_down_event(_mouse_event(pygame.MOUSEBUTTONDOWN, thumb_center))
        text_box.scrollbar.handle_mouse_motion((
            thumb_center[0] - text_box.rect.x,
            thumb_center[1] - text_box.rect.y + 60,
        ))

        text_box.on_left_mouse_button_up_event(
            _mouse_event(pygame.MOUSEBUTTONUP, (thumb_center[0], thumb_center[1] + 60))
        )

        assert text_box.scrollbar.is_dragging is False
        assert text_box.scroll_offset > 0
        assert text_box.scroll_offset == int(text_box.scrollbar.scroll_offset)
        assert text_box.dirty == 2

    def test_left_mouse_button_up_scrollbar_not_handled(self):
        """A release with no scrollbar drag leaves the scroll offset alone."""
        text_box = _scrollable_text_box()
        original_offset = text_box.scroll_offset

        text_box.on_left_mouse_button_up_event(_mouse_event(pygame.MOUSEBUTTONUP, (150, 150)))

        assert text_box.scroll_offset == original_offset


class TestMultiLineTextBoxMouseMotion:
    """Test MultiLineTextBox mouse motion event handling."""

    @pytest.fixture
    def text_box(self):
        """Create a MultiLineTextBox for testing.

        Returns:
            A MultiLineTextBox instance.
        """
        return _multiline_text_box(text='Hello')

    def test_mouse_motion_scrollbar_handled(self):
        """Dragging the scrollbar thumb scrolls the text box as the mouse moves."""
        text_box = _scrollable_text_box()
        thumb_center = _scrollbar_thumb_center_on_screen(text_box)
        text_box.on_left_mouse_button_down_event(_mouse_event(pygame.MOUSEBUTTONDOWN, thumb_center))

        text_box.on_mouse_motion_event(
            _mouse_event(pygame.MOUSEMOTION, (thumb_center[0], thumb_center[1] + 60))
        )

        assert text_box.scroll_offset > 0
        assert text_box.scroll_offset == int(text_box.scrollbar.scroll_offset)

    def test_mouse_motion_hover_inside(self, text_box):
        """Test mouse motion sets hover state when inside, which the next draw shows."""
        text_box.is_hovered = False
        text_box.on_mouse_motion_event(_mouse_event(pygame.MOUSEMOTION, (150, 150)))
        assert text_box.is_hovered is True
        assert text_box.dirty == 1

        text_box.update()

        assert _rgb_at(text_box.image, (0, 0)) == (100, 150, 255)

    def test_mouse_motion_hover_clears_on_deactivate(self, text_box):
        """Test hover state can be cleared by setting is_hovered directly."""
        text_box.is_hovered = True
        assert text_box.is_hovered is True
        text_box.is_hovered = False
        assert text_box.is_hovered is False


class TestMultiLineTextBoxKeyHandling:
    """Test MultiLineTextBox key handling."""

    @pytest.fixture
    def text_box(self):
        """Create a MultiLineTextBox for testing.

        Returns:
            A MultiLineTextBox instance.
        """
        text_box = _multiline_text_box(text='Hello World')
        text_box.is_active = True
        return text_box

    @staticmethod
    def _set_key_mods(modifiers):
        """Make ``modifiers`` the held modifier keys in this frame's polled input."""
        _install_frame_input(modifiers=modifiers)

    def test_key_down_inactive_returns(self, text_box):
        """Test key_down_event changes nothing when not active."""
        text_box.is_active = False
        text_box.on_key_down_event(_key_down(key=pygame.K_a, unicode='a'))
        assert text_box._original_text == 'Hello World'

    def test_key_down_typed_character_is_inserted_at_the_cursor(self, text_box):
        """A typed character goes in at the cursor, and the cursor moves past it."""
        text_box.cursor_pos = 5
        text_box.on_key_down_event(_key_down(key=pygame.K_COMMA, unicode=','))
        assert text_box._original_text == 'Hello, World'
        assert text_box.cursor_pos == 6

    def test_key_down_ctrl_d_clears_text(self, text_box):
        """Test Ctrl+D clears text contents."""
        self._set_key_mods(pygame.KMOD_CTRL)
        text_box.on_key_down_event(_key_down(key=pygame.K_d, unicode='d'))
        assert not text_box._original_text
        assert text_box.cursor_pos == 0

    def test_key_down_shift_arrow_extends_selection(self, text_box):
        """Test Shift+Arrow extends text selection."""
        self._set_key_mods(pygame.KMOD_LSHIFT)
        text_box.cursor_pos = 5
        text_box.on_key_down_event(_key_down(key=pygame.K_RIGHT))
        assert text_box.selection_start == 5
        assert text_box.selection_end == 6
        assert text_box.cursor_pos == 6

    def test_key_down_shift_left_arrow(self, text_box):
        """Test Shift+Left Arrow moves selection left."""
        self._set_key_mods(pygame.KMOD_LSHIFT)
        text_box.cursor_pos = 5
        text_box.on_key_down_event(_key_down(key=pygame.K_LEFT))
        assert text_box.cursor_pos == 4
        assert (text_box.selection_start, text_box.selection_end) == (5, 4)

    def test_key_down_arrow_clears_selection(self, text_box):
        """Test Arrow key without shift clears selection."""
        self._set_key_mods(0)
        text_box.selection_start = 0
        text_box.selection_end = 5
        text_box.cursor_pos = 5
        text_box.on_key_down_event(_key_down(key=pygame.K_RIGHT))
        assert text_box.selection_start is None
        assert text_box.selection_end is None
        assert text_box.cursor_pos == 6

    def test_handle_delete_selection(self, text_box):
        """Test _handle_delete_selection removes selected text."""
        text_box.selection_start = 0
        text_box.selection_end = 5
        result = text_box._handle_delete_selection(_key_down(key=pygame.K_DELETE))
        assert result is True
        assert text_box._original_text == ' World'
        assert text_box.selection_start is None

    def test_handle_delete_no_selection(self, text_box):
        """Test _handle_delete_selection returns False with no selection."""
        text_box.selection_start = None
        text_box.selection_end = None
        result = text_box._handle_delete_selection(_key_down(key=pygame.K_DELETE))
        assert result is False
        assert text_box._original_text == 'Hello World'

    def test_handle_delete_wrong_key(self, text_box):
        """Test _handle_delete_selection returns False for non-delete key."""
        text_box.selection_start = 0
        text_box.selection_end = 5
        result = text_box._handle_delete_selection(_key_down(key=pygame.K_BACKSPACE))
        assert result is False
        assert text_box._original_text == 'Hello World'

    def test_ctrl_enter_submit(self, text_box):
        """Test Ctrl+Enter submits the text to the parent and stops editing."""
        self._set_key_mods(pygame.KMOD_CTRL)
        parent = _RecordingParent('on_text_submit_event')
        text_box.parent = parent
        text_box.on_key_down_event(_key_down(key=pygame.K_RETURN, unicode='\r'))
        assert parent.calls == [('on_text_submit_event', ('Hello World',), {})]
        assert text_box.is_active is False


class TestMultiLineTextBoxMouseUpActivation:
    """Test MultiLineTextBox on_mouse_up_event activation."""

    @pytest.fixture
    def text_box(self):
        """Create a MultiLineTextBox for testing.

        Returns:
            A MultiLineTextBox instance.
        """
        return _multiline_text_box(text='Test')

    def test_mouse_up_inside_activates(self, text_box):
        """Test mouse up inside textbox activates it."""
        text_box.on_mouse_up_event(_mouse_event(pygame.MOUSEBUTTONUP, (150, 150)))
        assert text_box.is_active is True

    def test_mouse_up_outside_deactivates(self, text_box):
        """Test mouse up outside the textbox deactivates it."""
        text_box.is_active = True
        text_box.on_mouse_up_event(_mouse_event(pygame.MOUSEBUTTONUP, (5, 5)))
        assert text_box.is_active is False


class TestMultiLineTextBoxUpdate:
    """Test MultiLineTextBox update method."""

    @pytest.fixture
    def text_box(self):
        """Create a MultiLineTextBox for testing.

        Returns:
            A MultiLineTextBox instance.
        """
        return _multiline_text_box(text='Line 1\nLine 2')

    def test_update_hovered_not_active(self, text_box):
        """Test update with hover state but not active draws the text in the hover colour."""
        text_box.is_hovered = True
        text_box.is_active = False

        text_box.update()

        hover_text_color = (150, 200, 255)
        assert _rgb_at(text_box.image, (0, 0)) == (100, 150, 255)
        assert _pixel_count_of(text_box.image, hover_text_color, (5, 5, 200, 30)) > 0
        assert _pixel_count_of(text_box.image, WHITE, (5, 5, 200, 30)) == 0

    def test_update_active(self, text_box):
        """Test update when active draws the cursor after the last character."""
        text_box.is_active = True
        text_box.cursor_visible = True
        text_box.cursor_blink_time = clock.frame_clock_milliseconds()
        line_height = text_box._get_line_height()
        cursor_x = 5 + text_box._get_text_width('Line 2')
        cursor_column = (cursor_x, 5 + line_height + 2, 1, 16)

        text_box.update()

        assert _rgb_at(text_box.image, (0, 0)) == (64, 64, 255)
        assert _pixel_count_of(text_box.image, text_box.cursor_color, cursor_column) == 16

        text_box.cursor_visible = False
        text_box.cursor_blink_time = clock.frame_clock_milliseconds()
        text_box.update()

        assert _pixel_count_of(text_box.image, text_box.cursor_color, cursor_column) == 0

    def test_text_setter_wraps_and_scrolls(self, text_box):
        """Test text setter wraps text and auto-scrolls to bottom."""
        long_text = '\n'.join([f'Line {i}' for i in range(50)])
        text_box.text = long_text
        # Should auto-scroll to bottom
        assert text_box.scroll_offset == 50 - text_box.visible_lines
        assert text_box.scrollbar.scroll_offset == text_box.scroll_offset

    def test_text_setter_wraps_a_line_too_wide_for_the_box(self, text_box):
        """A line wider than the box (less its padding) is wrapped at word boundaries."""
        words = ' '.join(['word'] * 40)

        text_box.text = words

        wrapped_lines = text_box.text.split('\n')
        assert len(wrapped_lines) > 1
        assert all(text_box._get_text_width(line) <= 300 - 10 for line in wrapped_lines)
        assert ' '.join(wrapped_lines) == words

    def test_get_border_color_active(self, text_box):
        """Test _get_border_color returns blue when active."""
        text_box.is_active = True
        color = text_box._get_border_color()
        assert color == (64, 64, 255)

    def test_get_border_color_hovered(self, text_box):
        """Test _get_border_color returns light blue when hovered."""
        text_box.is_active = False
        text_box.is_hovered = True
        color = text_box._get_border_color()
        assert color == (100, 150, 255)

    def test_get_border_color_normal(self, text_box):
        """Test _get_border_color returns white when neither active nor hovered."""
        text_box.is_active = False
        text_box.is_hovered = False
        color = text_box._get_border_color()
        assert color == WHITE


# ============================================================================
# From test_widgets_deeper_coverage.py
# ============================================================================


class TestTextSpriteUpdate:
    """Test TextSprite update method with cursor blinking."""

    def test_update_active_increments_cursor_timer(self):
        """Test update increments cursor timer when active."""
        text_sprite = _text_sprite(text='test')
        text_sprite.is_active = True
        text_sprite._cursor_timer = 0
        text_sprite.update()
        assert text_sprite._cursor_timer == 1
        assert text_sprite.dirty == 2

    def test_update_active_toggles_cursor_visibility(self):
        """Test update toggles cursor visibility at blink interval, hiding the drawn cursor."""
        text_sprite = _text_sprite(text='test')
        text_sprite.is_active = True
        text_sprite._cursor_timer = 0
        text_sprite.update()
        with_cursor = _lit_pixel_count(text_sprite.image)
        # Force the timer just below the threshold so next update toggles
        text_sprite._cursor_timer = 29
        text_sprite._cursor_visible = True

        text_sprite.update()

        # After 30 frames, cursor should toggle, and the redraw leaves it out
        assert text_sprite._cursor_visible is False
        assert _lit_pixel_count(text_sprite.image) < with_cursor

    def test_update_inactive_sets_dirty_to_one(self):
        """Test update sets dirty=1 when not active."""
        text_sprite = _text_sprite(text='test')
        text_sprite.is_active = False
        text_sprite.dirty = 2
        text_sprite.update()
        assert text_sprite.dirty == 1


class TestTextSpriteProperties:
    """Test TextSprite property setters."""

    def test_x_setter_updates_rect(self):
        """Test x setter updates rect and marks dirty."""
        text_sprite = _text_sprite(text='test')
        text_sprite.x = 50
        assert text_sprite.rect.x == 50
        assert text_sprite.dirty == 2

    def test_y_setter_updates_rect(self):
        """Test y setter updates rect and marks dirty."""
        text_sprite = _text_sprite(text='test')
        text_sprite.y = 50
        assert text_sprite.rect.y == 50
        assert text_sprite.dirty == 2

    def test_text_setter_triggers_update(self):
        """Test text setter re-renders the image when the value changes."""
        text_sprite = _text_sprite(text='old')
        image_before = text_sprite.image
        text_sprite.text = 'new'
        assert text_sprite._text == 'new'
        assert text_sprite.dirty == 2
        assert text_sprite.image is not image_before

    def test_text_setter_no_change_skips_update(self):
        """Test text setter does not update when value is the same."""
        text_sprite = _text_sprite(text='same')
        text_sprite.dirty = 0
        text_sprite.text = 'same'
        # dirty should remain 0 since text didn't change
        assert text_sprite.dirty == 0

    def test_on_mouse_motion_event_does_nothing(self):
        """Test on_mouse_motion_event is a no-op (hover disabled)."""
        text_sprite = _text_sprite(text='test')
        text_sprite.dirty = 0
        image_before = text_sprite.image

        text_sprite.on_mouse_motion_event(HashableEvent(pygame.MOUSEMOTION, pos=(15, 25)))

        assert text_sprite.dirty == 0
        assert text_sprite.image is image_before


class TestTextSpriteTransparentBackground:
    """Test TextSprite with transparent background."""

    def test_update_text_transparent_background(self):
        """Test update_text with transparent (alpha=0) background draws only the text."""
        text_sprite = _text_sprite(text='transparent', background_color=(0, 0, 0, 0))

        text_sprite.update_text('transparent')

        assert text_sprite.image.get_at((0, 0)).a == 0
        assert text_sprite.image.get_at((TEST_WIDTH - 1, TEST_HEIGHT - 1)).a == 0
        assert _lit_pixel_count(text_sprite.image) > 0

    def test_update_text_active_background(self):
        """Test update_text with active state fills a darker background."""
        text_sprite = _text_sprite(text='test')
        text_sprite.is_active = True
        text_sprite.update_text('active text')
        assert _rgb_at(text_sprite.image, (0, 0)) == (50, 50, 50)
        assert _lit_pixel_count(text_sprite.image) > 0


def _button(**keyword_arguments):
    """Build a ButtonSprite at the shared test position and size.

    Returns:
        ButtonSprite: The button.
    """
    return ButtonSprite(
        x=TEST_X,
        y=TEST_Y,
        width=TEST_WIDTH,
        height=TEST_HEIGHT,
        name='TestButton',
        groups=pygame.sprite.LayeredDirty(),
        **keyword_arguments,
    )


class TestButtonSpritePropertySetters:
    """Test ButtonSprite x/y setters and update_nested_sprites."""

    def test_x_setter_updates_button_and_text(self):
        """Test x setter updates button rect and text position."""
        button = _button()
        button.x = 100
        assert button.rect.x == 100
        assert button.text.rect.x == 100
        assert button.dirty == 1

    def test_y_setter_updates_button_and_text(self):
        """Test y setter updates button rect and text position."""
        button = _button()
        button.y = 100
        assert button.rect.y == 100
        assert button.text.rect.y == 100
        assert button.dirty == 1

    def test_update_nested_sprites_propagates_dirty(self):
        """Test update_nested_sprites propagates dirty to text."""
        button = _button()
        button.dirty = 2
        button.update_nested_sprites()
        assert button.text.dirty == 2

    def test_on_left_mouse_button_down_sets_active_color(self):
        """Test mouse button down changes to active color."""
        button = _button()
        button.on_left_mouse_button_down_event(
            _mouse_event(pygame.MOUSEBUTTONDOWN, (TEST_X + 5, TEST_Y + 5))
        )
        assert button.background_color == button.active_color

    def test_on_left_mouse_button_up_sets_inactive_color(self):
        """Test mouse button up changes to inactive color."""
        button = _button()
        button.background_color = button.active_color
        button.on_left_mouse_button_up_event(
            _mouse_event(pygame.MOUSEBUTTONUP, (TEST_X + 5, TEST_Y + 5))
        )
        assert button.background_color == button.inactive_color


def _checkbox():
    """Build a 20x20 CheckboxSprite at the shared test position.

    Returns:
        CheckboxSprite: The checkbox.
    """
    return CheckboxSprite(
        x=TEST_X,
        y=TEST_Y,
        width=20,
        height=20,
        name='TestCheckbox',
        groups=pygame.sprite.LayeredDirty(),
    )


class TestCheckboxSpriteToggle:
    """Test CheckboxSprite toggle and update."""

    def test_checkbox_toggle_on(self):
        """Test checkbox toggles to checked state."""
        checkbox = _checkbox()
        assert checkbox.checked is False
        checkbox.on_left_mouse_button_up_event(_mouse_event(pygame.MOUSEBUTTONUP, (15, 25)))
        assert checkbox.checked is True

    def test_checkbox_toggle_off(self):
        """Test checkbox toggles back to unchecked state."""
        checkbox = _checkbox()
        checkbox.checked = True
        checkbox.on_left_mouse_button_up_event(_mouse_event(pygame.MOUSEBUTTONUP, (15, 25)))
        assert checkbox.checked is False

    def test_checkbox_update_unchecked(self):
        """Test unchecking a checkbox clears its X on the next draw."""
        checkbox = _checkbox()
        checkbox.checked = True
        checkbox.update()
        checkbox.checked = False

        checkbox.update()

        assert _rgb_at(checkbox.image, (10, 10)) == (0, 0, 0)
        assert _rgb_at(checkbox.image, (0, 0)) == checkbox.color

    def test_checkbox_update_checked(self):
        """Test checkbox update renders checked state with X marks."""
        checkbox = _checkbox()
        checkbox.checked = True
        checkbox.update()
        assert _rgb_at(checkbox.image, (3, 3)) == checkbox.color
        assert _rgb_at(checkbox.image, (3, 16)) == checkbox.color

    def test_checkbox_mouse_down_is_noop(self):
        """Test checkbox mouse down is a no-op."""
        checkbox = _checkbox()
        checkbox.on_left_mouse_button_down_event(_mouse_event(pygame.MOUSEBUTTONDOWN, (15, 25)))
        assert checkbox.checked is False


def _input_box(*, text='', parent=None):
    """Build an InputBox at the shared test position and size.

    Returns:
        InputBox: The input box.
    """
    return InputBox(
        x=TEST_X,
        y=TEST_Y,
        width=TEST_WIDTH,
        height=TEST_HEIGHT,
        text=text,
        parent=parent,
        groups=pygame.sprite.LayeredDirty(),
    )


class TestInputBoxKeyHandling:
    """Test InputBox key handling methods."""

    def test_on_key_down_return_triggers_confirm(self):
        """Test Return key triggers parent on_confirm_event."""
        parent = _RecordingParent('on_confirm_event', x=0, y=0)
        input_box = _input_box(parent=parent)
        input_box.is_active = True
        event = _key_down(key=pygame.K_RETURN, unicode='\r')
        input_box.on_key_down_event(event)
        assert parent.calls == [('on_confirm_event', (), {'event': event, 'trigger': input_box})]

    def test_on_key_down_return_without_a_confirm_handler_changes_nothing(self):
        """Return with a parent that has no on_confirm_event leaves the text as it is."""
        input_box = _input_box(text='keep', parent=_RecordingParent(x=0, y=0))
        input_box.is_active = True
        input_box.on_key_down_event(_key_down(key=pygame.K_RETURN, unicode='\r'))
        assert input_box.text == 'keep'

    def test_on_key_down_backspace_removes_last_char(self):
        """Test Backspace removes last character."""
        input_box = _input_box(text='hello', parent=_RecordingParent(x=0, y=0))
        input_box.is_active = True
        input_box.on_key_down_event(_key_down(key=pygame.K_BACKSPACE))
        assert input_box.text == 'hell'

    def test_on_key_down_unicode_appends_char(self):
        """Test unicode input appends character."""
        input_box = _input_box(text='hi', parent=_RecordingParent(x=0, y=0))
        input_box.is_active = True
        input_box.on_key_down_event(_key_down(key=pygame.K_a, unicode='a'))
        assert input_box.text == 'hia'

    def test_on_key_down_without_text_adds_nothing(self):
        """A key with no character (a bare Shift) adds nothing to the text."""
        input_box = _input_box(text='hi')
        input_box.is_active = True
        input_box.on_key_down_event(_key_down(key=pygame.K_LSHIFT))
        assert input_box.text == 'hi'

    def test_on_key_down_shift_semicolon_adds_colon(self):
        """Test Shift+semicolon adds colon character."""
        input_box = _input_box(text='example', parent=_RecordingParent(x=0, y=0))
        input_box.is_active = True
        input_box.on_key_down_event(
            _key_down(key=pygame.K_SEMICOLON, unicode=':', mod=pygame.KMOD_SHIFT)
        )
        assert input_box.text == 'example:'

    def test_on_key_down_inactive_does_nothing(self):
        """Test key down when inactive does nothing."""
        input_box = _input_box(text='test', parent=_RecordingParent(x=0, y=0))
        input_box.is_active = False
        input_box.on_key_down_event(_key_down(key=pygame.K_a, unicode='a'))
        assert input_box.text == 'test'

    def test_on_key_up_tab_deactivates(self):
        """Test Tab key deactivates input box."""
        input_box = _input_box(parent=_RecordingParent(x=0, y=0))
        input_box.is_active = True
        input_box.on_key_up_event(_key_up(key=pygame.K_TAB))
        assert input_box.is_active is False

    def test_on_key_up_escape_deactivates(self):
        """Test Escape key deactivates input box."""
        input_box = _input_box(parent=_RecordingParent(x=0, y=0))
        input_box.is_active = True
        input_box.on_key_up_event(_key_up(key=pygame.K_ESCAPE))
        assert input_box.is_active is False

    def test_on_key_up_other_key_keeps_it_active(self):
        """A key up other than Tab or Escape leaves the input box active."""
        input_box = _input_box()
        input_box.is_active = True
        input_box.on_key_up_event(_key_up(key=pygame.K_a))
        assert input_box.is_active is True

    def test_activate_and_deactivate(self):
        """Test activate and deactivate methods."""
        input_box = _input_box(parent=_RecordingParent(x=0, y=0))
        input_box.activate()
        assert input_box.is_active is True
        assert input_box.dirty == 2
        input_box.deactivate()
        assert input_box.is_active is False
        assert input_box.dirty == 0

    def test_on_input_box_submit_event_with_parent(self):
        """Test submit event delegates to parent."""
        parent = _RecordingParent('on_input_box_submit_event', x=0, y=0)
        input_box = _input_box(text='submitted', parent=parent)
        input_box.on_input_box_submit_event(_key_down(key=pygame.K_RETURN, unicode='\r'))
        assert parent.calls == [('on_input_box_submit_event', (), {'control': input_box})]

    def test_on_input_box_submit_no_parent_handler(self):
        """Test submit event with a parent that lacks the handler only logs."""
        parent = _RecordingParent(x=0, y=0)
        input_box = _input_box(text='submitted', parent=parent)
        input_box.on_input_box_submit_event(_key_down(key=pygame.K_RETURN, unicode='\r'))
        assert parent.calls == []
        assert input_box.text == 'submitted'

    def test_render_updates_text_image(self):
        """Test render renders the text in white onto a new text image."""
        input_box = _input_box(text='rendered', parent=_RecordingParent(x=0, y=0))
        input_box.render()
        assert input_box.text_image.get_size() == input_box.font.size('rendered')
        assert _pixel_count_of(input_box.text_image, (255, 255, 255)) > 0

    def test_update_draws_input_box(self):
        """Test update draws the input box's border and text."""
        input_box = _input_box(text='update', parent=_RecordingParent(x=0, y=0))
        input_box.update()
        assert _rgb_at(input_box.image, (0, 0)) == input_box.color
        assert _lit_pixel_count(input_box.image, (2, 2, TEST_WIDTH - 4, TEST_HEIGHT - 4)) > 0

    def test_on_mouse_up_activates(self):
        """Test mouse up event activates the input box."""
        input_box = _input_box(parent=_RecordingParent(x=0, y=0))
        input_box.on_mouse_up_event(_mouse_event(pygame.MOUSEBUTTONUP, (15, 25)))
        assert input_box.is_active is True


def _text_box_sprite():
    """Build a TextBoxSprite at the shared test position and size.

    Returns:
        TextBoxSprite: The text box.
    """
    return TextBoxSprite(
        x=TEST_X,
        y=TEST_Y,
        width=TEST_WIDTH,
        height=TEST_HEIGHT,
        name='TestTextBox',
        groups=pygame.sprite.LayeredDirty(),
    )


class TestTextBoxSpriteUpdateAndEvents:
    """Test TextBoxSprite update and mouse event methods."""

    def test_textbox_update_renders(self):
        """Test TextBoxSprite update passes its background colour on and draws its border."""
        textbox = _text_box_sprite()
        textbox.background_color = (128, 128, 128)
        textbox.dirty = 1

        textbox.update()

        assert textbox.text_box.background_color == (128, 128, 128)
        assert _rgb_at(textbox.image, (0, 0)) == (128, 128, 128)
        assert _rgb_at(textbox.image, (TEST_WIDTH - 1, TEST_HEIGHT - 1)) == (128, 128, 128)

    def test_textbox_update_nested_sprites(self):
        """Test update_nested_sprites propagates dirty."""
        textbox = _text_box_sprite()
        textbox.dirty = 2
        textbox.update_nested_sprites()
        assert textbox.text_box.dirty == 2

    def test_textbox_mouse_down_sets_background(self):
        """Test left mouse button down changes background color."""
        textbox = _text_box_sprite()
        textbox.on_left_mouse_button_down_event(_mouse_event(pygame.MOUSEBUTTONDOWN, (15, 25)))
        assert textbox.background_color == (128, 128, 128)
        assert textbox.dirty == 1

    def test_textbox_mouse_up_resets_background(self):
        """Test left mouse button up resets background color."""
        textbox = _text_box_sprite()
        textbox.background_color = (128, 128, 128)
        textbox.on_left_mouse_button_up_event(_mouse_event(pygame.MOUSEBUTTONUP, (15, 25)))
        assert textbox.background_color == (0, 0, 0)
        assert textbox.dirty == 1


def _color_well():
    """Build a 30x30 ColorWellSprite at the shared test position.

    Returns:
        ColorWellSprite: The color well.
    """
    return ColorWellSprite(
        x=TEST_X,
        y=TEST_Y,
        width=30,
        height=30,
        name='TestColorWell',
        groups=pygame.sprite.LayeredDirty(),
    )


class TestColorWellSpriteDeeper:
    """Test ColorWellSprite active_color setter."""

    def test_active_color_setter_rgb(self):
        """Test active_color setter with RGB tuple defaults alpha to 255."""
        color_well = _color_well()
        color_well.active_color = (100, 150, 200)
        assert color_well.red == 100
        assert color_well.green == 150
        assert color_well.blue == 200
        assert color_well.alpha == 255

    def test_active_color_setter_rgba(self):
        """Test active_color setter with RGBA tuple."""
        color_well = _color_well()
        color_well.active_color = (100, 150, 200, 128)
        assert color_well.alpha == 128

    def test_update_nested_sprites_does_not_raise(self):
        """Test update_nested_sprites is a no-op (hex display hidden): nothing is redrawn."""
        color_well = _color_well()
        color_well.update()
        drawn_pixels = _rgb_bytes(color_well.image)
        color_well.active_color = (255, 0, 0)

        color_well.update_nested_sprites()

        assert _rgb_bytes(color_well.image) == drawn_pixels

    def test_update_renders_color(self):
        """Test update renders the active color inside the border."""
        color_well = _color_well()
        color_well.active_color = (255, 0, 0, 255)
        color_well.update()
        assert _rgb_at(color_well.image, (15, 15)) == (255, 0, 0)
        assert _rgb_at(color_well.image, (0, 15)) == (128, 128, 255)


def _tab_control(*, parent=None):
    """Build a 100x20 TabControlSprite at the shared test position.

    Returns:
        TabControlSprite: The tab control.
    """
    return TabControlSprite(
        x=TEST_X,
        y=TEST_Y,
        width=100,
        height=20,
        name='TestTabs',
        parent=parent,
        groups=pygame.sprite.LayeredDirty(),
    )


class TestTabControlSpriteEvents:
    """Test TabControlSprite event handling and update."""

    def test_tab_click_switches_active_tab(self):
        """Test clicking on a tab switches the active tab."""
        tab_control = _tab_control()
        # Click on the second tab (right half)
        tab_control.on_left_mouse_button_down_event(
            _mouse_event(pygame.MOUSEBUTTONDOWN, (TEST_X + 75, TEST_Y + 10))
        )
        assert tab_control.active_tab == 1
        # Redrawn once, not every frame (BUGS.md #155 item 2)
        assert tab_control.dirty == 1

    def test_tab_click_outside_does_nothing(self):
        """Test clicking outside the tab control does nothing."""
        tab_control = _tab_control()
        tab_control.on_left_mouse_button_down_event(
            _mouse_event(pygame.MOUSEBUTTONDOWN, (500, 500))
        )
        assert tab_control.active_tab == 0

    def test_tab_click_on_the_last_pixel_of_an_odd_width_hits_no_tab(self):
        """A 101-pixel control has two 50-pixel tabs: its last pixel column is in neither."""
        parent = _RecordingParent('on_tab_change_event')
        tab_control = TabControlSprite(
            x=TEST_X,
            y=TEST_Y,
            width=101,
            height=20,
            name='TestTabs',
            parent=parent,
            groups=pygame.sprite.LayeredDirty(),
        )
        tab_control.dirty = 0

        tab_control.on_left_mouse_button_down_event(
            _mouse_event(pygame.MOUSEBUTTONDOWN, (TEST_X + 100, TEST_Y + 10))
        )

        assert tab_control.active_tab == 0
        assert tab_control.dirty == 0
        assert parent.calls == []

    def test_tab_click_notifies_parent(self):
        """Test clicking on a tab notifies parent with on_tab_change_event."""
        parent = _RecordingParent('on_tab_change_event')
        tab_control = _tab_control(parent=parent)
        tab_control.on_left_mouse_button_down_event(
            _mouse_event(pygame.MOUSEBUTTONDOWN, (TEST_X + 75, TEST_Y + 10))
        )
        assert parent.calls == [('on_tab_change_event', ('%X',), {})]

    def test_tab_update_renders_tabs(self):
        """Test update renders tab backgrounds and labels."""
        tab_control = _tab_control()
        tab_control.dirty = 1
        tab_control.update()
        assert _rgb_at(tab_control.image, (2, 2)) == tab_control.active_color
        assert _rgb_at(tab_control.image, (52, 2)) == tab_control.inactive_color
        assert _pixel_count_of(tab_control.image, tab_control.text_color, (1, 1, 48, 18)) > 0


def _channel_slider(*, name='R', parent=None):
    """Build a 256-pixel channel slider at the shared test position.

    Returns:
        SliderSprite: The slider.
    """
    return SliderSprite(
        x=TEST_X,
        y=TEST_Y,
        width=256,
        height=9,
        name=name,
        parent=parent,
        groups=pygame.sprite.LayeredDirty(),
    )


class TestSliderSpriteDeeper:
    """Test SliderSprite value setter and text input handling."""

    @staticmethod
    def _make_slider_parent():
        """Create a parent for a slider that records its slider events.

        Returns:
            _RecordingParent: The parent.
        """
        return _RecordingParent('on_slider_event')

    def test_slider_value_setter_clamps(self):
        """Test slider value setter clamps to 0-255 range."""
        slider = _channel_slider(parent=self._make_slider_parent())
        slider.value = 300
        assert slider._value == 255
        assert slider.slider_knob.rect.x == slider.max_x
        slider.value = -10
        assert slider._value == 0
        assert slider.slider_knob.rect.x == slider.min_x

    def test_slider_update_calls_appearance(self):
        """Test slider update redraws its green gradient when dirty."""
        slider = _channel_slider(name='G', parent=self._make_slider_parent())
        slider.image.fill(PLACEHOLDER_FILL)
        slider.dirty = 1

        slider.update()

        assert _rgb_at(slider.image, (0, 4)) == (0, 0, 0)
        assert _rgb_at(slider.image, (128, 4)) == (0, 127, 0)
        assert _pixel_count_of(slider.image, PLACEHOLDER_FILL) == 0

    def test_slider_on_mouse_up_stops_dragging(self):
        """Test mouse button up stops dragging: later motion moves nothing."""
        parent = self._make_slider_parent()
        slider = _channel_slider(name='B', parent=parent)
        slider.dragging = True
        slider.on_left_mouse_button_up_event(_mouse_event(pygame.MOUSEBUTTONUP, (50, 24)))
        assert slider.dragging is False

        slider.on_mouse_motion_event(_mouse_event(pygame.MOUSEMOTION, (200, 24)))

        assert slider.value == 0
        assert parent.calls == []

    def test_slider_restore_original_value(self):
        """Test _restore_original_value restores and deactivates text."""
        slider = _channel_slider(parent=self._make_slider_parent())
        slider.original_value = 42
        slider.text_sprite.is_active = True
        slider._restore_original_value()
        assert slider.text_sprite.text == '42'
        assert slider.text_sprite.is_active is False

    @pytest.mark.parametrize(
        ('input_format', 'expected_text'),
        [pytest.param('%X', 'FF', id='hex_tab'), pytest.param('%d', '255', id='decimal_tab')],
    )
    def test_slider_restore_original_value_uses_the_active_format(
        self, input_format, expected_text
    ):
        """Restoring writes the original value in the tab's format: 'FF' on the hex tab."""
        parent = self._make_slider_parent()
        parent.slider_input_format = input_format
        slider = _channel_slider(parent=parent)
        slider.original_value = 255
        slider.text_sprite.is_active = True
        slider._restore_original_value()
        assert slider.text_sprite.text == expected_text
        assert slider.text_sprite.is_active is False

    def test_slider_commit_text_empty_restores(self):
        """Test commit_text with empty text restores original."""
        parent = self._make_slider_parent()
        slider = _channel_slider(parent=parent)
        slider.original_value = 100
        slider.text_sprite.text = ''
        slider.commit_text(event=_return_key())
        assert slider.text_sprite.text == '100'
        assert parent.calls == []

    def test_slider_commit_text_valid_decimal(self):
        """Test commit_text with valid decimal value."""
        parent = self._make_slider_parent()
        slider = _channel_slider(parent=parent)
        slider.text_sprite.text = '128'
        slider.text_sprite.is_active = True
        slider.commit_text(event=_return_key())
        assert slider._value == 128
        assert slider.text_sprite.is_active is False
        assert len(parent.calls) == 1

    def test_slider_commit_text_valid_hex(self):
        """Test commit_text with valid hex value."""
        parent = self._make_slider_parent()
        parent.slider_input_format = '%X'
        slider = _channel_slider(parent=parent)
        slider.text_sprite.text = 'ff'
        slider.text_sprite.is_active = True
        slider.commit_text(event=_return_key())
        assert slider._value == 255
        assert slider.text_sprite.text == 'FF'

    def test_slider_commit_text_digits_on_the_hex_tab_are_hex(self):
        """On the hex tab "10" is 16, not 10 (BUGS.md #110 item 3)."""
        parent = self._make_slider_parent()
        parent.slider_input_format = '%X'
        slider = _channel_slider(parent=parent)
        slider.text_sprite.text = '10'
        slider.text_sprite.is_active = True
        slider.commit_text(event=_return_key())
        assert slider._value == 16
        assert slider.text_sprite.text == '10'

    def test_slider_commit_text_digits_on_the_decimal_tab_are_decimal(self):
        """On the decimal tab "10" is 10."""
        parent = self._make_slider_parent()
        parent.slider_input_format = '%d'
        slider = _channel_slider(parent=parent)
        slider.text_sprite.text = '10'
        slider.text_sprite.is_active = True
        slider.commit_text(event=_return_key())
        assert slider._value == 10

    def test_slider_commit_text_out_of_range_restores(self):
        """Test commit_text with out-of-range value restores."""
        slider = _channel_slider(parent=self._make_slider_parent())
        slider.original_value = 50
        slider.text_sprite.text = '999'
        slider.commit_text(event=_return_key())
        assert slider.text_sprite.text == '50'

    def test_slider_handle_text_character_input_backspace(self):
        """Test _handle_text_character_input with backspace."""
        slider = _channel_slider(parent=self._make_slider_parent())
        slider.text_sprite.text = '12'
        slider.text_sprite.is_active = True
        slider._handle_text_character_input(_key_down(key=pygame.K_BACKSPACE))
        assert slider.text_sprite.text == '1'

    def test_slider_handle_text_character_input_digit(self):
        """Test _handle_text_character_input with digit appends."""
        slider = _channel_slider(parent=self._make_slider_parent())
        slider.text_sprite.text = '1'
        slider.text_sprite.is_active = True
        slider._handle_text_character_input(_key_down(key=pygame.K_5, unicode='5'))
        assert slider.text_sprite.text == '15'

    def test_slider_handle_text_character_input_truncates_at_max(self):
        """Test _handle_text_character_input truncates at max length."""
        slider = _channel_slider(parent=self._make_slider_parent())
        slider.text_sprite.text = '255'
        slider.text_sprite.is_active = True
        slider._handle_text_character_input(_key_down(key=pygame.K_9, unicode='9'))
        # Should truncate to 3 chars
        assert slider.text_sprite.text == '255'

    def test_slider_typed_hex_letter_is_lower_cased(self):
        """A typed hex letter goes into the text box in lower case."""
        slider = _channel_slider(parent=self._make_slider_parent())
        slider.text_sprite.text = ''
        slider.text_sprite.is_active = True
        slider._handle_text_character_input(_key_down(key=pygame.K_a, unicode='A'))
        assert slider.text_sprite.text == 'a'


class TestMenuBarAddMenuItem:
    """Test MenuBar add_menu_item method."""

    def test_add_menu_item_without_menu_calls_add_menu(self):
        """Test add_menu_item without menu argument delegates to add_menu."""
        groups = pygame.sprite.LayeredDirty()
        menu_bar = MenuBar(x=0, y=0, width=800, height=30, groups=groups)
        menu_item = MenuItem(x=0, y=0, width=60, height=20, name='File', groups=groups)
        menu_bar.add_menu_item(menu_item=menu_item)
        assert menu_bar.menu_items == {'File': menu_item}
        # The first menu is moved inside the menu bar's border
        assert menu_item.rect.y == menu_bar.border_width
        assert menu_bar.menu_offset_x == menu_item.rect.right + menu_bar.border_width

    def test_add_menu_item_with_menu_logs(self):
        """Test add_menu_item with menu argument only logs: nothing is added."""
        groups = pygame.sprite.LayeredDirty()
        menu_bar = MenuBar(x=0, y=0, width=800, height=30, groups=groups)
        menu_item = MenuItem(x=0, y=0, width=60, height=20, name='New', groups=groups)
        menu_bar.add_menu_item(menu_item=menu_item, menu=_menubar())
        assert menu_bar.menu_items == {}


class TestMenuBarGroupsNone:
    """Test MenuBar with groups=None default branch."""

    def test_menubar_groups_none_creates_default(self):
        """Test MenuBar creates a LayeredDirty holding itself when groups is None."""
        menu_bar = MenuBar(x=0, y=0, width=800, height=30, groups=None)
        assert isinstance(menu_bar.all_sprites, pygame.sprite.LayeredDirty)
        assert menu_bar in menu_bar.all_sprites


class TestMenuItemLeftMouseButtonUpSubitems:
    """Test MenuBar on_left_mouse_button_up_event with subitems."""

    def test_left_mouse_button_up_delegates_to_subitems(self):
        """A release over a menu bar's item forwards the release to the item's sub-items."""
        groups = pygame.sprite.LayeredDirty()
        menu_bar = MenuBar(x=0, y=0, width=800, height=30, groups=groups)

        # Create a menu item with a sub-menu item, and add it
        menu_item = MenuItem(x=0, y=0, width=60, height=20, name='File', groups=groups)
        sub_item = _RecordingParent('on_left_mouse_button_up_event')
        menu_item.menu_items = {'SubItem': sub_item}
        menu_bar.add_menu_item(menu_item=menu_item)

        # The release lands on the menu item, in the menu bar's group
        event = _mouse_event(pygame.MOUSEBUTTONUP, (5, 5))
        menu_bar.on_left_mouse_button_up_event(event)

        assert sub_item.calls == [('on_left_mouse_button_up_event', (event,), {})]

    def test_left_mouse_button_up_away_from_the_items_reaches_none(self):
        """A release away from every menu item forwards nothing."""
        groups = pygame.sprite.LayeredDirty()
        menu_bar = MenuBar(x=0, y=0, width=800, height=30, groups=groups)
        menu_item = MenuItem(x=0, y=0, width=60, height=20, name='File', groups=groups)
        sub_item = _RecordingParent('on_left_mouse_button_up_event')
        menu_item.menu_items = {'SubItem': sub_item}
        menu_bar.add_menu_item(menu_item=menu_item)

        menu_bar.on_left_mouse_button_up_event(_mouse_event(pygame.MOUSEBUTTONUP, (500, 25)))

        assert sub_item.calls == []


class TestMenuItemAddMenuItemNoneMenu:
    """Test MenuItem add_menu_item when menu is None."""

    def test_add_menu_item_with_none_menu_calls_add_menu(self):
        """Test add_menu_item with menu=None adds the item as a sub-menu (through add_menu)."""
        groups = pygame.sprite.LayeredDirty()
        menu_item = MenuItem(x=0, y=0, width=60, height=20, name='File', groups=groups)
        sub_item = MenuItem(x=0, y=0, width=60, height=20, name='New', groups=groups)

        menu_item.add_menu_item(menu_item=sub_item, menu=None)

        assert menu_item.menu_items == {'New': sub_item}
        # add_menu grew the dropped-down image to hold the sub-item
        assert menu_item.menu_down_image.get_height() == 40


class TestMenuItemMouseEventSubmenus:
    """Test MenuItem mouse event propagation to submenu items.

    menu_items maps submenu names to submenu items; the events reach the items (the dict's
    values). These tests used mock objects as dict keys while the code iterated the keys.
    """

    @staticmethod
    def _menu_with_a_collided_item():
        """Build a 'Menu' item whose 'File' item lies under (5, 5) and has one sub-item.

        Returns:
            tuple: (menu_item, collided_item, submenu_item); the sub-item records its events.
        """
        groups = pygame.sprite.LayeredDirty()
        # The menu item itself lies away from (5, 5), so only the File item is under it
        menu_item = MenuItem(x=100, y=0, width=60, height=20, name='Menu', groups=groups)
        collided_item = MenuItem(x=0, y=0, width=60, height=20, name='File', groups=groups)
        submenu_item = _RecordingParent(
            'on_mouse_motion_event', 'on_mouse_enter_event', 'on_mouse_exit_event'
        )
        collided_item.menu_items = {'Submenu': submenu_item}
        menu_item.menu_items = {'File': collided_item}
        return menu_item, collided_item, submenu_item

    def test_on_mouse_motion_event_propagates_to_submenus(self):
        """Test on_mouse_motion_event propagates to submenu items."""
        menu_item, _collided_item, submenu_item = self._menu_with_a_collided_item()
        event = _mouse_event(pygame.MOUSEMOTION, (5, 5))

        menu_item.on_mouse_motion_event(event)

        assert submenu_item.calls == [('on_mouse_motion_event', (event,), {})]

    def test_on_mouse_enter_event_propagates_to_submenus(self):
        """Test on_mouse_enter_event propagates to submenu items."""
        menu_item, collided_item, submenu_item = self._menu_with_a_collided_item()
        event = _mouse_event(pygame.MOUSEMOTION, (5, 5))

        menu_item.on_mouse_enter_event(event)

        assert submenu_item.calls == [('on_mouse_enter_event', (event,), {})]
        assert collided_item.has_focus is True
        assert menu_item.has_focus is True

    def test_on_mouse_exit_event_propagates_to_submenus(self):
        """Test on_mouse_exit_event propagates the exit to submenu items."""
        menu_item, collided_item, submenu_item = self._menu_with_a_collided_item()
        event = _mouse_event(pygame.MOUSEMOTION, (5, 5))

        menu_item.on_mouse_exit_event(event)

        assert submenu_item.calls == [('on_mouse_exit_event', (event,), {})]
        assert collided_item.has_focus is False
        assert menu_item.has_focus is False


def _pygame_font():
    """Return the bundled default font as a pygame.font font (no render_to), from FontManager.

    Returns:
        pygame.font.Font: The font.
    """
    return FontManager.pygame_font(font_config={'font_name': DEFAULT_FONT_NAME, 'font_size': 14})


class TestTextSpiteRenderPygameFont:
    """Test TextSprite _render_with_pygame_font path (a pygame.font font, not freetype)."""

    def test_render_text_with_non_freetype_font(self):
        """Test _render_with_pygame_font renders the text with a pygame.font font."""
        text_sprite = _text_sprite(text='test')
        font = _pygame_font()

        surface = text_sprite._render_with_pygame_font(
            font,
            'hello',
            (255, 255, 255),
            is_transparent=False,
        )

        assert surface.get_size() == font.size('hello')
        assert _pixel_count_of(surface, (255, 255, 255)) > 0

    def test_render_with_pygame_font_transparent(self):
        """Test _render_with_pygame_font with transparent background renders the text too."""
        text_sprite = _text_sprite(text='test')
        font = _pygame_font()

        surface = text_sprite._render_with_pygame_font(
            font,
            'hello',
            (255, 255, 255),
            is_transparent=True,
        )

        assert surface.get_size() == font.size('hello')
        assert _pixel_count_of(surface, (255, 255, 255)) > 0

    def test_render_with_a_freetype_font_returns_the_surface_of_its_tuple(self):
        """A freetype font (the fallback when freetype rejects the color) gives its surface.

        A freetype render returns (surface, rect); only the surface is handed back.
        """
        text_sprite = _text_sprite(text='test')
        font = FontManager.get_font()
        assert hasattr(font, 'render_to')

        surface = text_sprite._render_with_pygame_font(
            font,
            'hello',
            (255, 255, 255),
            is_transparent=False,
        )

        assert isinstance(surface, pygame.Surface)
        assert surface.get_width() > 0


class _SurfaceOnlyFreetypeFont:
    """The real default font, whose render returns only the surface (no rect)."""

    def __init__(self, font):
        """Wrap a real freetype font."""
        self._font = font

    def render_to(self, surface, destination, text, fgcolor):
        """Render text onto a surface with the real font.

        Returns:
            pygame.Rect: Where the text was drawn.
        """
        return self._font.render_to(surface, destination, text, fgcolor)

    def render(self, text, fgcolor, bgcolor):
        """Render text with the real font, returning only the surface.

        Returns:
            pygame.Surface: The rendered text.
        """
        return self._font.render(text, fgcolor=fgcolor, bgcolor=bgcolor)[0]


class TestTextSpriteFreetypeFallbacks:
    """TextSprite with a freetype-style font whose render returns no rect, and no text rect."""

    def test_render_with_a_font_returning_only_a_surface(self):
        """A render that returns just the surface still gives the text, without a rect."""
        text_sprite = _text_sprite(text='test', background_color=(0, 0, 0))
        font = _SurfaceOnlyFreetypeFont(FontManager.get_font())

        text_surface, text_rect = text_sprite._render_with_freetype_font(
            font, 'hello', (255, 255, 255), is_transparent=False
        )

        assert text_rect is None
        assert _lit_pixel_count(text_surface) > 0

    def test_draw_cursor_without_a_text_rect_draws_nothing(self):
        """_draw_cursor skips drawing when it has no text rect to place the cursor after."""
        text_sprite = _text_sprite(text='test')
        text_sprite._cursor_visible = True
        drawn_pixels = _rgb_bytes(text_sprite.image)

        text_sprite._draw_cursor(None, text_sprite.font)

        assert _rgb_bytes(text_sprite.image) == drawn_pixels


class TestInputBoxCursorBlink:
    """Test InputBox cursor blink during update."""

    @pytest.mark.parametrize(
        ('frame_clock_seconds', 'cursor_drawn'),
        [(1.7, True), (1.2, False)],
    )
    def test_update_draws_cursor_in_the_visible_half_of_the_blink(
        self, frame_clock_seconds, cursor_drawn
    ):
        """The InputBox cursor blinks on the frame clock: drawn when its fraction is past 0.5."""
        input_box = _input_box(text='hello', parent=_RecordingParent(x=0, y=0))
        input_box.is_active = True
        advance_frame_clock(seconds=frame_clock_seconds)
        # Where the cursor goes: right after the text, which is drawn at (5, 2)
        text_rect = input_box.text_image.get_rect(topleft=(5, 2))
        cursor_area = pygame.Rect(0, 0, 3, text_rect.height)
        cursor_area.midleft = text_rect.midright

        input_box.update()

        cursor_pixels = _pixel_count_of(input_box.image, input_box.color, cursor_area)
        assert (cursor_pixels == cursor_area.width * cursor_area.height) is cursor_drawn
        if not cursor_drawn:
            assert cursor_pixels == 0


class TestSliderTextInputInactive:
    """Test slider text input when inactive."""

    def test_handle_text_input_when_inactive_returns_early(self):
        """Test the text box ignores keys (even Enter) while it is not being edited."""
        parent = _RecordingParent('on_slider_event')
        slider = _channel_slider(parent=parent)
        slider.text_sprite.is_active = False
        slider.text_sprite.text = '7'

        slider.text_sprite.on_key_down_event(_key_down(key=pygame.K_RETURN, unicode='\r'))

        assert slider.value == 0
        assert slider.text_sprite.text == '7'
        assert parent.calls == []

    def test_escape_while_editing_restores_the_value(self):
        """Escape while editing the text box puts back the value it showed."""
        slider = _channel_slider(parent=_RecordingParent('on_slider_event'))
        slider.value = 12
        slider.text_sprite.on_left_mouse_button_down_event(
            _mouse_event(pygame.MOUSEBUTTONDOWN, slider.text_sprite.rect.center)
        )
        slider.text_sprite.on_key_down_event(_key_down(key=pygame.K_5, unicode='5'))

        slider.text_sprite.on_key_down_event(_key_down(key=pygame.K_ESCAPE, unicode='\x1b'))

        assert slider.text_sprite.text == '12'
        assert slider.text_sprite.is_active is False
        assert slider.value == 12


class TestSliderTextClickOutside:
    """Test slider text click returning False."""

    def test_text_click_outside_returns_false(self):
        """Clicking away from the slider's text box does not start editing it."""
        slider = _channel_slider(parent=_RecordingParent('on_slider_event'))
        offscreen_event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(9999, 9999), button=1)

        result = slider.text_sprite.on_left_mouse_button_down_event(offscreen_event)

        assert result is False
        assert slider.text_sprite.is_active is False
        assert slider.text_sprite.text == '0'

    def test_text_click_inside_starts_editing_with_an_empty_box(self):
        """Clicking the slider's text box clears it for typing and starts editing."""
        slider = _channel_slider(parent=_RecordingParent('on_slider_event'))
        slider.value = 99

        result = slider.text_sprite.on_left_mouse_button_down_event(
            _mouse_event(pygame.MOUSEBUTTONDOWN, slider.text_sprite.rect.center)
        )

        assert result is True
        assert slider.text_sprite.is_active is True
        assert not slider.text_sprite.text
        assert slider.original_value == 99


class TestSliderMouseDownWithParentEvent:
    """Test SliderSprite on_left_mouse_button_down_event with on_slider_event."""

    def test_mouse_down_calls_parent_on_slider_event(self):
        """Test clicking on slider calls parent.on_slider_event with the new value."""
        parent = _RecordingParent('on_slider_event')
        slider = _channel_slider(parent=parent)
        event = _mouse_event(pygame.MOUSEBUTTONDOWN, (TEST_X + 128, TEST_Y + 4))

        slider.on_left_mouse_button_down_event(event)

        [(handler_name, _arguments, keyword_arguments)] = parent.calls
        assert handler_name == 'on_slider_event'
        assert keyword_arguments['event'] is event
        expected_value = 128 * 255 // (slider.max_x - slider.min_x)
        assert (keyword_arguments['trigger'].name, keyword_arguments['trigger'].value) == (
            'R',
            expected_value,
        )

    def test_mouse_down_hex_format(self):
        """Test clicking on slider with hex format writes the value as two hex digits."""
        parent = _RecordingParent('on_slider_event', slider_input_format='%X')
        slider = _channel_slider(parent=parent)
        slider.on_left_mouse_button_down_event(
            _mouse_event(pygame.MOUSEBUTTONDOWN, (TEST_X + 128, TEST_Y + 4))
        )
        assert slider.text_sprite.text == f'{slider.value:02X}'

    def test_mouse_down_outside_slider_logs(self):
        """Test clicking outside slider rect changes nothing and tells no one."""
        parent = _RecordingParent('on_slider_event')
        slider = _channel_slider(parent=parent)
        slider.on_left_mouse_button_down_event(_mouse_event(pygame.MOUSEBUTTONDOWN, (9999, 9999)))
        # Should not call on_slider_event
        assert parent.calls == []
        assert slider.dragging is False


class TestSliderDragWithParentEvent:
    """Test SliderSprite on_mouse_motion_event drag."""

    def test_drag_calls_parent_on_slider_event(self):
        """Test dragging slider calls parent.on_slider_event."""
        parent = _RecordingParent('on_slider_event')
        slider = _channel_slider(parent=parent)
        slider.dragging = True
        slider.on_mouse_motion_event(_mouse_event(pygame.MOUSEMOTION, (TEST_X + 100, TEST_Y + 4)))
        assert len(parent.calls) == 1
        assert slider.value == 100 * 255 // (slider.max_x - slider.min_x)

    def test_drag_hex_format_updates_text(self):
        """Test dragging slider with hex format writes the value as two hex digits."""
        parent = _RecordingParent('on_slider_event', slider_input_format='%X')
        slider = _channel_slider(parent=parent)
        slider.dragging = True
        slider.on_mouse_motion_event(_mouse_event(pygame.MOUSEMOTION, (TEST_X + 100, TEST_Y + 4)))
        assert slider.text_sprite.text == f'{slider.value:02X}'


class TestTabControlFontError:
    """Test TabControlSprite font error handling."""

    def test_update_handles_font_error_gracefully(self, mocker):
        """When the font fails to load, the tabs are still drawn, without their labels."""
        tab_control = _tab_control()
        tab_control.dirty = 1
        # Simulate the font failing to load
        mocker.patch('glitchygames.ui.sliders.pygame.font.Font', side_effect=pygame.error('Font'))

        tab_control.update()

        assert _rgb_at(tab_control.image, (2, 2)) == tab_control.active_color
        assert _rgb_at(tab_control.image, (52, 2)) == tab_control.inactive_color
        assert _pixel_count_of(tab_control.image, tab_control.text_color) == 0


class _FontWithoutSize:
    """The real default font, without get_linesize or size: a font that names no line height."""

    def __init__(self, font):
        """Wrap a real freetype font."""
        self._font = font

    def get_rect(self, text):
        """Measure text with the real font.

        Returns:
            pygame.Rect: The text's bounds.
        """
        return self._font.get_rect(text)

    def render(self, text, fgcolor):
        """Render text with the real font.

        Returns:
            tuple: (surface, rect).
        """
        return self._font.render(text, fgcolor=fgcolor)

    def get_metrics(self, text):
        """Measure each character with the real font.

        Returns:
            list: Each character's metrics (its advance at index 4).
        """
        return self._font.get_metrics(text)


def _small_multiline_text_box(*, text, height=100):
    """Build a MultiLineTextBox at the shared test position and width, with its text set.

    Returns:
        MultiLineTextBox: The text box.
    """
    textbox = MultiLineTextBox(
        x=TEST_X,
        y=TEST_Y,
        width=TEST_WIDTH,
        height=height,
        name='TestMLTB',
        groups=pygame.sprite.LayeredDirty(),
    )
    textbox.text = text
    return textbox


class TestMultiLineTextBoxCursorNavigation:
    """Test MultiLineTextBox cursor navigation edge cases."""

    @staticmethod
    def _make_textbox(text='Line1\nLine2\nLine3'):
        """Create a MultiLineTextBox for testing.

        Returns:
            MultiLineTextBox: A configured text box for testing.
        """
        return _small_multiline_text_box(text=text)

    def test_move_cursor_up_at_top_goes_to_beginning(self):
        """Test _move_cursor_up at top line moves cursor to 0."""
        textbox = self._make_textbox()
        textbox.cursor_pos = 2  # Middle of first line
        textbox._move_cursor_up()
        assert textbox.cursor_pos == 0

    def test_move_cursor_up_keeps_the_column(self):
        """_move_cursor_up from the middle of a line lands on the same column one line up."""
        textbox = self._make_textbox()
        textbox.cursor_pos = len('Line1\nLi')
        textbox._move_cursor_up()
        assert textbox.cursor_pos == len('Li')

    def test_move_cursor_down_at_bottom_goes_to_end(self):
        """Test _move_cursor_down at bottom line moves to end."""
        textbox = self._make_textbox()
        textbox.cursor_pos = len(textbox._original_text) - 1  # Near end
        textbox._move_cursor_down()
        assert textbox.cursor_pos == len(textbox._original_text)

    def test_map_wrapped_position_out_of_bounds(self):
        """Test _map_wrapped_position_to_original with line beyond wrap."""
        textbox = self._make_textbox(text='short')
        result = textbox._map_wrapped_position_to_original(line=999, column=0)
        assert result == len(textbox._original_text)

    def test_map_cursor_pos_stops_at_the_end_of_a_shorter_wrapped_text(self):
        """A position past the end of the wrapped text maps to the wrapped text's end.

        Wrapping never makes the text this much shorter; the mapping still stays in range.
        """
        textbox = self._make_textbox(text='aaa')
        textbox._original_text = 'aaa'
        textbox._text = 'a'

        result = textbox._map_cursor_pos_to_wrapped_text(2)

        assert result == len(textbox._text)

    def test_get_line_height_freetype_fallback(self):
        """Test _get_line_height uses a freetype font's size (it has no get_linesize)."""
        textbox = self._make_textbox()
        assert not hasattr(textbox.font, 'get_linesize')
        assert textbox._get_line_height() == int(textbox.font.size)

    def test_get_line_height_of_a_pygame_font(self):
        """_get_line_height uses a pygame.font font's line size."""
        textbox = self._make_textbox()
        textbox.font = _pygame_font()
        assert textbox._get_line_height() == textbox.font.get_linesize()

    def test_box_built_with_a_pygame_font_sizes_its_lines_from_it(self, mocker):
        """A text box made while the default font is a pygame.font font uses its line size."""
        font = _pygame_font()
        mocker.patch('glitchygames.fonts.FontManager.get_font', return_value=font)

        textbox = _small_multiline_text_box(text='Line1\nLine2')

        assert textbox.visible_lines == (100 - 10) // font.get_linesize()

    def test_click_with_a_pygame_font_picks_the_line_from_its_line_size(self):
        """A click on the second line of a pygame.font text box puts the cursor on that line."""
        textbox = self._make_textbox()
        textbox.font = _pygame_font()
        line_height = textbox.font.get_linesize()

        textbox.on_left_mouse_button_down_event(
            _mouse_event(pygame.MOUSEBUTTONDOWN, (TEST_X + 5 + 1, TEST_Y + 5 + line_height + 2))
        )

        assert textbox.cursor_pos == len('Line1\n')

    def test_get_line_height_no_size_attribute(self):
        """Test _get_line_height returns 24 when the font names no line height."""
        textbox = self._make_textbox()
        textbox.font = _FontWithoutSize(textbox.font)
        assert textbox._get_line_height() == 24


class TestMultiLineTextBoxScrolling:
    """Test MultiLineTextBox auto-scroll and cursor visibility."""

    @staticmethod
    def _make_textbox_with_many_lines():
        """Create a MultiLineTextBox with many lines for scrolling tests.

        Returns:
            MultiLineTextBox: A configured text box with 30 lines.

        """
        return _small_multiline_text_box(
            text='\n'.join(f'Line {index}' for index in range(30)), height=60
        )

    def test_auto_scroll_when_cursor_below_visible(self):
        """Test auto-scroll adjusts when cursor is below visible area."""
        textbox = self._make_textbox_with_many_lines()
        textbox.is_active = True
        textbox.scroll_offset = 0
        # Move cursor to last line
        textbox.cursor_pos = len(textbox._original_text)
        line_height = textbox._get_line_height()
        # Render should auto-scroll
        textbox._render_visible_lines((255, 255, 255), line_height)
        assert textbox.scroll_offset == 30 - textbox.visible_lines
        assert textbox.scrollbar.scroll_offset == textbox.scroll_offset

    def test_auto_scroll_when_cursor_above_visible(self):
        """Test auto-scroll adjusts when cursor is above visible area."""
        textbox = self._make_textbox_with_many_lines()
        textbox.is_active = True
        textbox.scroll_offset = 20  # Scrolled down
        textbox.cursor_pos = 0  # Cursor at beginning
        textbox._render_visible_lines((255, 255, 255), textbox._get_line_height())
        assert textbox.scroll_offset == 0

    def test_cursor_not_in_visible_range_not_drawn(self):
        """Test cursor is not drawn when outside visible range."""
        textbox = self._make_textbox_with_many_lines()
        textbox.is_active = True
        textbox.cursor_visible = True
        textbox.scroll_offset = 20  # Scrolled far down
        textbox.cursor_pos = 0  # Cursor at top
        textbox.cursor_blink_time = clock.frame_clock_milliseconds()
        textbox.image.fill((0, 0, 0, 255))

        textbox._update_cursor_blink(clock.frame_clock_milliseconds(), textbox._get_line_height())

        assert _pixel_count_of(textbox.image, textbox.cursor_color) == 0

    def test_cursor_in_visible_range_is_drawn(self):
        """A visible cursor on a visible line is drawn as a vertical line."""
        textbox = self._make_textbox_with_many_lines()
        textbox.is_active = True
        textbox.cursor_visible = True
        textbox.scroll_offset = 0
        textbox.cursor_pos = 0
        textbox.cursor_blink_time = clock.frame_clock_milliseconds()
        textbox.image.fill((0, 0, 0, 255))

        textbox._update_cursor_blink(clock.frame_clock_milliseconds(), textbox._get_line_height())

        # The cursor runs 20 pixels down from (5, 5), two pixels wide
        assert _pixel_count_of(textbox.image, textbox.cursor_color, (3, 5, 4, 21)) >= 21

    def test_cursor_blink_hides_the_cursor_after_the_blink_rate(self):
        """After cursor_blink_rate milliseconds the cursor toggles off and is not drawn."""
        textbox = self._make_textbox_with_many_lines()
        textbox.is_active = True
        textbox.cursor_visible = True
        textbox.scroll_offset = 0
        textbox.cursor_pos = 0
        textbox.cursor_blink_time = clock.frame_clock_milliseconds()
        textbox.image.fill((0, 0, 0, 255))

        textbox._update_cursor_blink(
            clock.frame_clock_milliseconds() + textbox.cursor_blink_rate, textbox._get_line_height()
        )

        assert textbox.cursor_visible is False
        assert _pixel_count_of(textbox.image, textbox.cursor_color) == 0


class TestMultiLineTextBoxMouseEvents:
    """Test MultiLineTextBox mouse event handlers."""

    @staticmethod
    def _make_textbox(text='Hello World'):
        """Create a MultiLineTextBox for testing.

        Returns:
            MultiLineTextBox: A configured text box for testing.

        """
        return _small_multiline_text_box(text=text)

    def test_mouse_down_on_scrollbar(self):
        """A click on the scrollbar's track jumps the scroll offset there (no activation)."""
        textbox = _small_multiline_text_box(
            text='\n'.join(f'Line {index}' for index in range(30)), height=60
        )
        textbox.scroll_offset = 0
        textbox.scrollbar.update(30, textbox.visible_lines, 0)
        scrollbar = textbox.scrollbar
        # The bottom of the track, below the thumb
        track_bottom = (
            TEST_X + scrollbar.x + scrollbar.width // 2,
            TEST_Y + scrollbar.y + scrollbar.height - 1,
        )

        textbox.on_left_mouse_button_down_event(_mouse_event(pygame.MOUSEBUTTONDOWN, track_bottom))

        assert textbox.scroll_offset == int(scrollbar.scroll_offset)
        assert textbox.scroll_offset > 0
        assert textbox.is_active is False

    def test_mouse_down_outside_deactivates(self):
        """Test clicking outside textbox deactivates it."""
        textbox = self._make_textbox()
        textbox.is_active = True
        far_away = (textbox.rect.right + 500, textbox.rect.bottom + 500)
        textbox.on_left_mouse_button_down_event(_mouse_event(pygame.MOUSEBUTTONDOWN, far_away))
        assert textbox.is_active is False
        assert pygame.key.get_repeat() == (0, 0)

    def test_mouse_down_on_the_first_character_puts_the_cursor_before_it(self):
        """A click on the left half of the first character puts the cursor at 0."""
        textbox = self._make_textbox()

        textbox.on_left_mouse_button_down_event(
            _mouse_event(pygame.MOUSEBUTTONDOWN, (TEST_X + 5 + 1, TEST_Y + 8))
        )

        assert textbox.is_active is True
        assert textbox.cursor_pos == 0

    def test_mouse_down_past_the_end_of_a_line_puts_the_cursor_at_its_end(self):
        """A click right of a line's text puts the cursor at the end of that line."""
        textbox = self._make_textbox()

        textbox.on_left_mouse_button_down_event(
            _mouse_event(pygame.MOUSEBUTTONDOWN, (TEST_X + TEST_WIDTH - 20, TEST_Y + 8))
        )

        assert textbox.cursor_pos == len('Hello World')

    def test_mouse_down_in_the_middle_of_a_character_puts_the_cursor_before_it(self):
        """A click on the middle of 'W' (character 6 of 'Hello World') puts the cursor at 6."""
        textbox = self._make_textbox()
        text = 'Hello World'
        advances = [
            character_metrics[4]
            for character_metrics in textbox.font.get_metrics(text)
            if character_metrics is not None
        ]
        assert len(advances) == len(text)  # The default font has every glyph of the text
        # The text is drawn from its first ink column (the first glyph's left bearing)
        left_bearing = textbox.font.get_rect(text).x
        w_middle = sum(advances[:6]) + advances[6] / 2 - left_bearing

        textbox.on_left_mouse_button_down_event(
            _mouse_event(pygame.MOUSEBUTTONDOWN, (TEST_X + 5 + int(w_middle), TEST_Y + 8))
        )

        assert textbox.cursor_pos == 6

    def test_mouse_down_line_height_no_size_fallback(self):
        """Test mouse down uses 24 as the line height for a font that names none.

        When the font has neither get_linesize nor size, the click falls back to 24.
        """
        textbox = self._make_textbox(text='first\nsecond')
        textbox.font = _FontWithoutSize(textbox.font)
        # 30 pixels down is the second line with 24-pixel lines (the first with 14-pixel ones)
        textbox.on_left_mouse_button_down_event(
            _mouse_event(pygame.MOUSEBUTTONDOWN, (TEST_X + 5, TEST_Y + 5 + 30))
        )
        assert textbox.is_active is True
        assert textbox.cursor_pos == len('first\n')


class TestMultiLineTextBoxDeleteSelection:
    """Test MultiLineTextBox _handle_delete_selection path."""

    def test_delete_key_with_selection(self):
        """Test delete key with active selection removes selected text."""
        textbox = _small_multiline_text_box(text='Hello World')
        textbox.is_active = True
        textbox.selection_start = 5
        textbox.selection_end = 11
        textbox.on_key_down_event(_key_down(key=pygame.K_DELETE))
        assert textbox.text == 'Hello'
        assert textbox.cursor_pos == 5


class TestMultiLineTextBoxHoverExit:
    """Test MultiLineTextBox mouse motion hover exit."""

    def test_mouse_exit_clears_hover(self):
        """Test mouse motion outside textbox clears hover state."""
        textbox = _small_multiline_text_box(text='')
        textbox.is_hovered = True
        textbox.on_mouse_motion_event(_mouse_event(pygame.MOUSEMOTION, (9999, 9999)))
        assert textbox.is_hovered is False
        assert textbox.dirty == 1


class TestMultiLineTextBoxMouseWheel:
    """Test MultiLineTextBox mouse wheel scrolling."""

    @staticmethod
    def _many_line_textbox():
        """Build a 60-pixel-tall text box holding 30 lines.

        Returns:
            MultiLineTextBox: The text box.
        """
        return _small_multiline_text_box(
            text='\n'.join(f'Line {index}' for index in range(30)), height=60
        )

    def test_mouse_wheel_pygame19_scroll_up(self):
        """Test mouse wheel with button 4 (scroll up) in pygame 1.9 style."""
        textbox = self._many_line_textbox()
        textbox.scroll_offset = 10
        _install_frame_input(mouse_position=(TEST_X + 5, TEST_Y + 5))
        # A pygame 1.9 wheel event: a button press without a 'y'
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=4, pos=(TEST_X + 5, TEST_Y + 5))
        textbox.on_mouse_wheel_event(event)
        assert textbox.scroll_offset == 7
        assert textbox.scrollbar.scroll_offset == 7

    def test_mouse_wheel_pygame19_scroll_down(self):
        """Test mouse wheel with button 5 (scroll down) in pygame 1.9 style."""
        textbox = self._many_line_textbox()
        textbox.scroll_offset = 5
        _install_frame_input(mouse_position=(TEST_X + 5, TEST_Y + 5))
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=5, pos=(TEST_X + 5, TEST_Y + 5))
        textbox.on_mouse_wheel_event(event)
        assert textbox.scroll_offset == 8

    def test_mouse_wheel_scrolls_three_lines_per_notch(self):
        """A pygame 2 wheel event scrolls three lines per notch, clamped to the text."""
        textbox = self._many_line_textbox()
        textbox.scroll_offset = 5
        _install_frame_input(mouse_position=(TEST_X + 5, TEST_Y + 5))

        textbox.on_mouse_wheel_event(HashableEvent(pygame.MOUSEWHEEL, x=0, y=-1))
        assert textbox.scroll_offset == 8

        textbox.on_mouse_wheel_event(HashableEvent(pygame.MOUSEWHEEL, x=0, y=10))
        assert textbox.scroll_offset == 0

    def test_mouse_wheel_away_from_the_box_does_not_scroll(self):
        """A wheel turned while the mouse is elsewhere leaves the text box alone."""
        textbox = self._many_line_textbox()
        textbox.scroll_offset = 5
        _install_frame_input(mouse_position=(700, 500))

        textbox.on_mouse_wheel_event(HashableEvent(pygame.MOUSEWHEEL, x=0, y=1))

        assert textbox.scroll_offset == 5


class _SurfaceOnlyFont:
    """The real default font, whose render returns only the surface (no rect)."""

    def __init__(self, font):
        """Wrap a real freetype font."""
        self._font = font

    def render(self, text, fgcolor, size):
        """Render text with the real font, returning only the surface.

        Returns:
            pygame.Surface: The rendered text.
        """
        return self._font.render(text, fgcolor=fgcolor, size=size)[0]


class TestConfirmDialogNonTupleRender:
    """Test ConfirmDialog render fallbacks for a font whose render returns only a surface."""

    def test_update_with_non_tuple_font_render(self, mocker):
        """ConfirmDialog draws its message and both buttons' labels from surface-only renders."""
        from glitchygames.ui.inputs import ConfirmDialog

        surface_only_font = _SurfaceOnlyFont(FontManager.get_font())
        mocker.patch('glitchygames.fonts.FontManager.get_font', return_value=surface_only_font)
        confirm_calls = []
        dialog = ConfirmDialog(
            text='Delete?',
            confirm_callback=lambda: confirm_calls.append('confirm'),
            cancel_callback=None,
            x=0,
            y=0,
            width=300,
            height=100,
            groups=pygame.sprite.LayeredDirty(),
        )
        dialog.dirty = 1

        dialog.update()

        # White text on the dark grey background and on the green and red buttons
        message_area = (0, 15, 300, 25)
        assert _lit_pixel_count(dialog.image, message_area) > 0
        assert _lit_pixel_count(dialog.image, dialog.yes_button_rect) > 0
        assert _lit_pixel_count(dialog.image, dialog.no_button_rect) > 0
        assert dialog.dirty == 0
        # The Yes button still confirms
        assert dialog.handle_mouse_down(dialog.yes_button_rect.center) is True
        assert confirm_calls == ['confirm']


class TestTextWidgetsWithRealSurfaces:
    """TextSprite and TextBoxSprite on real surfaces and fonts."""

    def test_text_sprite_renders_with_a_pygame_font(self, mocker):
        """A pygame.font.Font (no render_to) renders through the pygame.font path."""
        pygame_font = pygame.font.Font(None, 24)
        mocker.patch('glitchygames.fonts.FontManager.get_font', return_value=pygame_font)
        text_sprite = TextSprite(
            x=0,
            y=0,
            width=60,
            height=30,
            background_color=(0, 0, 0),
            text_color=(255, 255, 255),
            text='W',
        )

        text_sprite.update_text('W')

        assert _lit_pixel_count(text_sprite.image) > 0

    def test_text_box_without_its_text_sprite_draws_only_the_border(self):
        text_box = TextBoxSprite(x=0, y=0, width=40, height=20, name='box')
        text_box.text_box = None
        text_box.image.fill((0, 0, 0))

        text_box.update()

        assert text_box.image.get_at((0, 0))[:3] == (128, 128, 128)
        assert text_box.image.get_at((20, 10))[:3] == (0, 0, 0)

    def test_text_box_without_a_border_draws_none(self):
        text_box = TextBoxSprite(x=0, y=0, width=40, height=20, name='box')
        text_box.text_box = None
        text_box.border_width = 0
        text_box.image.fill((0, 0, 0))

        text_box.update()

        assert text_box.image.get_at((0, 0))[:3] == (0, 0, 0)


class _RecordingSliderParent:
    """A slider parent that records the slider events it receives."""

    def __init__(self, *, slider_input_format: str = DECIMAL_INPUT_FORMAT) -> None:
        """Start with no events, in the given text box format."""
        self.slider_input_format = slider_input_format
        self.slider_events: list[tuple[str, int]] = []

    def on_slider_event(self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Record the slider's name and value."""
        self.slider_events.append((trigger.name, trigger.value))


def _key_event(*, key: int, unicode: str) -> HashableEvent:
    """Build a key down event.

    Returns:
        HashableEvent: The event.

    """
    return HashableEvent(pygame.KEYDOWN, key=key, unicode=unicode, mod=0)


class TestChannelFormatAndParse:
    """The one formatter and parser of slider text box values."""

    @pytest.mark.parametrize(
        ('value', 'input_format', 'expected_text'),
        [
            (255, DECIMAL_INPUT_FORMAT, '255'),
            (255, HEX_INPUT_FORMAT, 'FF'),
            (5, HEX_INPUT_FORMAT, '05'),
        ],
    )
    def test_format_channel(self, value, input_format, expected_text):
        """Decimal is plain digits; hex is two upper-case digits."""
        assert format_channel(value, input_format) == expected_text

    @pytest.mark.parametrize(
        ('text', 'input_format', 'expected_value'),
        [
            ('200', DECIMAL_INPUT_FORMAT, 200),
            (' 10 ', DECIMAL_INPUT_FORMAT, 10),
            ('10', HEX_INPUT_FORMAT, 16),
            ('ff', DECIMAL_INPUT_FORMAT, 255),
            ('FF', HEX_INPUT_FORMAT, 255),
            ('', DECIMAL_INPUT_FORMAT, None),
            ('   ', HEX_INPUT_FORMAT, None),
            ('256', DECIMAL_INPUT_FORMAT, None),
            ('-1', DECIMAL_INPUT_FORMAT, None),
            ('xyz', DECIMAL_INPUT_FORMAT, None),
        ],
    )
    def test_parse_channel(self, text, input_format, expected_value):
        """Valid text gives its value; empty, unparsable or out-of-range text gives None."""
        assert parse_channel(text, input_format) == expected_value


class TestSliderSpriteOnTheRealDisplay:
    """SliderSprite with real surfaces and a real parent (no pygame mocks)."""

    @staticmethod
    def _slider(*, parent=None, name='R'):
        """Build a 256-pixel slider at (10, 20).

        Returns:
            SliderSprite: The slider.

        """
        return SliderSprite(x=10, y=20, width=256, height=9, name=name, parent=parent)

    def test_the_parent_is_kept(self):
        """The parent given to the slider is its parent."""
        parent = _RecordingSliderParent()

        assert self._slider(parent=parent).parent is parent

    def test_value_setter_writes_text_in_the_parents_format(self):
        """Setting the value shows it in hex on the hex tab and ends text editing."""
        slider = self._slider(parent=_RecordingSliderParent(slider_input_format=HEX_INPUT_FORMAT))
        slider.text_sprite.is_active = True

        slider.value = 171

        assert slider.text_sprite.text == 'AB'
        assert slider.text_sprite.is_active is False

    def test_value_setter_writes_decimal_without_a_parent(self):
        """A slider without a parent shows decimal text."""
        slider = self._slider()

        slider.value = 171

        assert slider.text_sprite.text == '171'

    def test_enter_commits_the_typed_text_and_tells_the_parent(self):
        """Typing digits then Enter sets the value and sends one slider event."""
        parent = _RecordingSliderParent()
        slider = self._slider(parent=parent)
        slider.text_sprite.on_left_mouse_button_down_event(
            HashableEvent(pygame.MOUSEBUTTONDOWN, pos=slider.text_sprite.rect.center, button=1),
        )

        for character in '42':
            slider.text_sprite.on_key_down_event(_key_event(key=ord(character), unicode=character))
        slider.text_sprite.on_key_down_event(_key_event(key=pygame.K_RETURN, unicode='\r'))

        assert slider.value == 42
        assert slider.original_value == 42
        assert slider.text_sprite.is_active is False
        assert parent.slider_events == [('R', 42)]

    def test_invalid_text_is_restored_and_the_parent_is_not_told(self):
        """Out-of-range text restores the original value and sends no event."""
        parent = _RecordingSliderParent()
        slider = self._slider(parent=parent)
        slider.value = 7
        slider.original_value = 7
        slider.text_sprite.is_active = True
        slider.text_sprite.text = '999'

        slider.commit_text(event=_key_event(key=pygame.K_RETURN, unicode='\r'))

        assert slider.value == 7
        assert slider.text_sprite.text == '7'
        assert slider.text_sprite.is_active is False
        assert parent.slider_events == []

    def test_commit_without_a_parent_sets_the_value(self):
        """A slider without a parent still takes committed text."""
        slider = self._slider()
        slider.text_sprite.is_active = True
        slider.text_sprite.text = '9'

        slider.commit_text(event=_key_event(key=pygame.K_RETURN, unicode='\r'))

        assert slider.value == 9

    def test_click_and_drag_set_the_value_and_tell_the_parent(self):
        """A click at the right end gives 255, a drag to the left end gives 0."""
        parent = _RecordingSliderParent()
        slider = self._slider(parent=parent)

        slider.on_left_mouse_button_down_event(
            HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(slider.rect.right - 1, 24), button=1),
        )
        slider.on_mouse_motion_event(HashableEvent(pygame.MOUSEMOTION, pos=(0, 24)))
        slider.on_left_mouse_button_up_event(
            HashableEvent(pygame.MOUSEBUTTONUP, pos=(0, 24), button=1),
        )
        slider.on_mouse_motion_event(HashableEvent(pygame.MOUSEMOTION, pos=(200, 24)))

        assert parent.slider_events == [('R', 255), ('R', 0)]
        assert slider.value == 0
        assert slider.slider_knob.rect.x == slider.min_x

    def test_click_off_the_slider_changes_nothing(self):
        """A click outside the slider's rect leaves its value and sends no event."""
        parent = _RecordingSliderParent()
        slider = self._slider(parent=parent)

        slider.on_left_mouse_button_down_event(
            HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=1),
        )

        assert slider.dragging is False
        assert parent.slider_events == []

    @pytest.mark.parametrize(
        ('name', 'right_end_color'),
        [('R', (255, 0, 0)), ('G', (0, 255, 0)), ('B', (0, 0, 255)), ('A', (255, 255, 255))],
    )
    def test_gradient_runs_to_the_channel_color(self, name, right_end_color):
        """Each slider draws a gradient from black to its channel's color."""
        slider = self._slider(name=name)

        slider.update()

        assert tuple(slider.image.get_at((0, 4)))[:3] == (0, 0, 0)
        assert all(
            abs(channel - expected) <= 1
            for channel, expected in zip(
                tuple(slider.image.get_at((255, 4)))[:3], right_end_color, strict=True
            )
        )


class TestColorWellSpriteOnTheRealDisplay:
    """ColorWellSprite with real surfaces (no pygame mocks)."""

    def test_click_changes_nothing(self):
        """The color well only shows the color; a click leaves it as it was."""
        color_well = ColorWellSprite(x=10, y=20, width=50, height=30, name='Well')
        color_well.active_color = (1, 2, 3, 4)

        color_well.on_left_mouse_button_down_event(
            HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(35, 35), button=1),
        )

        assert color_well.active_color == (1, 2, 3, 4)
        assert color_well.callbacks == {}

    def test_update_draws_the_color_inside_a_border(self):
        """The well draws its color inside a one-pixel border."""
        color_well = ColorWellSprite(x=10, y=20, width=50, height=30, name='Well')
        color_well.active_color = (200, 100, 50)

        color_well.update()

        assert tuple(color_well.image.get_at((0, 0))) == (128, 128, 255, 255)
        assert tuple(color_well.image.get_at((25, 15))) == (200, 100, 50, 255)
