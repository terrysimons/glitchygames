"""Deeper coverage tests for glitchygames/ui/widgets.py.

Targets uncovered areas NOT covered by test_widgets_coverage.py:
- TextSprite update() with cursor blinking
- TextSprite _render_text_with_font fallback paths
- TextSprite _draw_cursor edge cases
- ButtonSprite x/y setters and update_nested_sprites
- ButtonSprite mouse button events
- CheckboxSprite update and toggle
- InputBox on_key_down_event (Return, Backspace, colon, unicode)
- InputBox on_input_box_submit_event
- InputBox render and update
- TextBoxSprite update and mouse events
- SliderSprite value setter, text input, drag handling
- SliderSprite _handle_text_enter, _handle_text_character_input, _restore_original_value
- ColorWellSprite hex_color, active_color setter with RGBA
- TabControlSprite on_left_mouse_button_down_event, update
- InputDialog on_key_up_event, on_key_down_event
- MenuBar update with focus, add_menu_item
- MenuItem add_menu, add_menu_item, on_left_mouse_button_up_event
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Save REAL LayeredDirty before mock_pygame_patches replaces it with a Mock.
_RealLayeredDirty = pygame.sprite.LayeredDirty

from glitchygames.ui import (  # noqa: E402
    ButtonSprite,
    CheckboxSprite,
    ColorWellSprite,
    MenuItem,
    SliderSprite,
    TextBoxSprite,
    TextSprite,
)
from glitchygames.ui.widgets import InputBox, MultiLineTextBox, TabControlSprite  # noqa: E402
from tests.mocks import MockFactory  # noqa: E402

# Test constants
TEST_X = 10
TEST_Y = 20
TEST_WIDTH = 200
TEST_HEIGHT = 30


class TestTextSpriteUpdate:
    """Test TextSprite update method with cursor blinking."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_active_increments_cursor_timer(self):
        """Test update increments cursor timer when active."""
        groups = _RealLayeredDirty()
        text_sprite = TextSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='test',
            groups=groups,
        )
        text_sprite.active = True
        text_sprite._cursor_timer = 0
        text_sprite.update()
        assert text_sprite._cursor_timer >= 1

    def test_update_active_toggles_cursor_visibility(self):
        """Test update toggles cursor visibility at blink interval."""
        groups = _RealLayeredDirty()
        text_sprite = TextSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='test',
            groups=groups,
        )
        text_sprite.active = True
        # Force the timer just below the threshold so next update toggles
        text_sprite._cursor_timer = 29
        text_sprite._cursor_visible = True
        text_sprite.update()
        # After 30 frames, cursor should toggle
        assert text_sprite._cursor_visible is False

    def test_update_inactive_sets_dirty_to_one(self):
        """Test update sets dirty=1 when not active."""
        groups = _RealLayeredDirty()
        text_sprite = TextSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='test',
            groups=groups,
        )
        text_sprite.active = False
        text_sprite.dirty = 2
        text_sprite.update()
        # After inactive update, dirty is set to 1 but then text is re-rendered
        assert text_sprite.dirty >= 1


class TestTextSpriteProperties:
    """Test TextSprite property setters."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_x_setter_updates_rect(self):
        """Test x setter updates rect and marks dirty."""
        groups = _RealLayeredDirty()
        text_sprite = TextSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='test',
            groups=groups,
        )
        text_sprite.x = 50
        assert text_sprite.rect.x == 50
        assert text_sprite.dirty == 2

    def test_y_setter_updates_rect(self):
        """Test y setter updates rect and marks dirty."""
        groups = _RealLayeredDirty()
        text_sprite = TextSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='test',
            groups=groups,
        )
        text_sprite.y = 50
        assert text_sprite.rect.y == 50
        assert text_sprite.dirty == 2

    def test_text_setter_triggers_update(self):
        """Test text setter triggers update_text when value changes."""
        groups = _RealLayeredDirty()
        text_sprite = TextSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='old',
            groups=groups,
        )
        text_sprite.text = 'new'
        assert text_sprite._text == 'new'
        assert text_sprite.dirty == 2

    def test_text_setter_no_change_skips_update(self):
        """Test text setter does not update when value is the same."""
        groups = _RealLayeredDirty()
        text_sprite = TextSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='same',
            groups=groups,
        )
        text_sprite.dirty = 0
        text_sprite.text = 'same'
        # dirty should remain 0 since text didn't change
        assert text_sprite.dirty == 0

    def test_on_mouse_motion_event_does_nothing(self):
        """Test on_mouse_motion_event is a no-op (hover disabled)."""
        groups = _RealLayeredDirty()
        text_sprite = TextSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='test',
            groups=groups,
        )
        event = pygame.event.Event(pygame.MOUSEMOTION, pos=(15, 25))
        # Should not raise
        text_sprite.on_mouse_motion_event(event)


class TestTextSpriteTransparentBackground:
    """Test TextSprite with transparent background."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_text_transparent_background(self):
        """Test update_text with transparent (alpha=0) background."""
        groups = _RealLayeredDirty()
        text_sprite = TextSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            background_color=(0, 0, 0, 0),
            text='transparent',
            groups=groups,
        )
        # Should not raise, transparent path is handled
        text_sprite.update_text('transparent')

    def test_update_text_active_background(self):
        """Test update_text with active state fills darker background."""
        groups = _RealLayeredDirty()
        text_sprite = TextSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='test',
            groups=groups,
        )
        text_sprite.active = True
        text_sprite.update_text('active text')
        # Should not raise; dark background drawn


class TestButtonSpritePropertySetters:
    """Test ButtonSprite x/y setters and update_nested_sprites."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_x_setter_updates_button_and_text(self):
        """Test x setter updates button rect and text position."""
        groups = _RealLayeredDirty()
        button = ButtonSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestButton',
            groups=groups,
        )
        button.x = 100
        assert button.rect.x == 100
        assert button.dirty == 1

    def test_y_setter_updates_button_and_text(self):
        """Test y setter updates button rect and text position."""
        groups = _RealLayeredDirty()
        button = ButtonSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestButton',
            groups=groups,
        )
        button.y = 100
        assert button.rect.y == 100
        assert button.dirty == 1

    def test_update_nested_sprites_propagates_dirty(self):
        """Test update_nested_sprites propagates dirty to text."""
        groups = _RealLayeredDirty()
        button = ButtonSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestButton',
            groups=groups,
        )
        button.dirty = 2
        button.update_nested_sprites()
        assert button.text.dirty == 2

    def test_on_left_mouse_button_down_sets_active_color(self, mocker):
        """Test mouse button down changes to active color."""
        groups = _RealLayeredDirty()
        button = ButtonSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestButton',
            groups=groups,
        )
        event = mocker.Mock()
        event.pos = (TEST_X + 5, TEST_Y + 5)
        button.on_left_mouse_button_down_event(event)
        assert button.background_color == button.active_color

    def test_on_left_mouse_button_up_sets_inactive_color(self, mocker):
        """Test mouse button up changes to inactive color."""
        groups = _RealLayeredDirty()
        button = ButtonSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestButton',
            groups=groups,
        )
        event = mocker.Mock()
        event.pos = (TEST_X + 5, TEST_Y + 5)
        button.on_left_mouse_button_up_event(event)
        assert button.background_color == button.inactive_color


class TestCheckboxSpriteToggle:
    """Test CheckboxSprite toggle and update."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_checkbox_toggle_on(self, mocker):
        """Test checkbox toggles to checked state."""
        groups = _RealLayeredDirty()
        checkbox = CheckboxSprite(
            x=TEST_X,
            y=TEST_Y,
            width=20,
            height=20,
            name='TestCheckbox',
            groups=groups,
        )
        assert checkbox.checked is False
        event = mocker.Mock()
        checkbox.on_left_mouse_button_up_event(event)
        assert checkbox.checked is True

    def test_checkbox_toggle_off(self, mocker):
        """Test checkbox toggles back to unchecked state."""
        groups = _RealLayeredDirty()
        checkbox = CheckboxSprite(
            x=TEST_X,
            y=TEST_Y,
            width=20,
            height=20,
            name='TestCheckbox',
            groups=groups,
        )
        checkbox.checked = True
        event = mocker.Mock()
        checkbox.on_left_mouse_button_up_event(event)
        assert checkbox.checked is False

    def test_checkbox_update_unchecked(self):
        """Test checkbox update renders unchecked state."""
        groups = _RealLayeredDirty()
        checkbox = CheckboxSprite(
            x=TEST_X,
            y=TEST_Y,
            width=20,
            height=20,
            name='TestCheckbox',
            groups=groups,
        )
        checkbox.checked = False
        checkbox.update()  # Should not raise

    def test_checkbox_update_checked(self):
        """Test checkbox update renders checked state with X marks."""
        groups = _RealLayeredDirty()
        checkbox = CheckboxSprite(
            x=TEST_X,
            y=TEST_Y,
            width=20,
            height=20,
            name='TestCheckbox',
            groups=groups,
        )
        checkbox.checked = True
        checkbox.update()  # Should not raise

    def test_checkbox_mouse_down_is_noop(self, mocker):
        """Test checkbox mouse down is a no-op."""
        groups = _RealLayeredDirty()
        checkbox = CheckboxSprite(
            x=TEST_X,
            y=TEST_Y,
            width=20,
            height=20,
            name='TestCheckbox',
            groups=groups,
        )
        event = mocker.Mock()
        checkbox.on_left_mouse_button_down_event(event)  # Should not raise


class TestInputBoxKeyHandling:
    """Test InputBox key handling methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_on_key_down_return_triggers_confirm(self, mocker):
        """Test Return key triggers parent on_confirm_event."""
        groups = _RealLayeredDirty()
        parent = mocker.Mock()
        parent.x = 0
        parent.y = 0
        input_box = InputBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            parent=parent,
            groups=groups,
        )
        input_box.active = True
        event = mocker.Mock()
        event.key = pygame.K_RETURN
        event.unicode = ''
        input_box.on_key_down_event(event)
        parent.on_confirm_event.assert_called_once()

    def test_on_key_down_backspace_removes_last_char(self, mocker):
        """Test Backspace removes last character."""
        groups = _RealLayeredDirty()
        parent = mocker.Mock()
        parent.x = 0
        parent.y = 0
        input_box = InputBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='hello',
            parent=parent,
            groups=groups,
        )
        input_box.active = True
        event = mocker.Mock()
        event.key = pygame.K_BACKSPACE
        event.unicode = ''
        event.mod = 0
        input_box.on_key_down_event(event)
        assert input_box.text == 'hell'

    def test_on_key_down_unicode_appends_char(self, mocker):
        """Test unicode input appends character."""
        groups = _RealLayeredDirty()
        parent = mocker.Mock()
        parent.x = 0
        parent.y = 0
        del parent.on_confirm_event  # No confirm handler
        input_box = InputBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='hi',
            parent=parent,
            groups=groups,
        )
        input_box.active = True
        event = mocker.Mock()
        event.key = pygame.K_a
        event.unicode = 'a'
        event.mod = 0
        input_box.on_key_down_event(event)
        assert input_box.text == 'hia'

    def test_on_key_down_shift_semicolon_adds_colon(self, mocker):
        """Test Shift+semicolon adds colon character."""
        groups = _RealLayeredDirty()
        parent = mocker.Mock()
        parent.x = 0
        parent.y = 0
        del parent.on_confirm_event
        input_box = InputBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='example',
            parent=parent,
            groups=groups,
        )
        input_box.active = True
        event = mocker.Mock()
        event.key = pygame.K_SEMICOLON
        event.mod = pygame.KMOD_SHIFT
        event.unicode = ':'
        input_box.on_key_down_event(event)
        assert input_box.text == 'example:'

    def test_on_key_down_inactive_does_nothing(self, mocker):
        """Test key down when inactive does nothing."""
        groups = _RealLayeredDirty()
        parent = mocker.Mock()
        parent.x = 0
        parent.y = 0
        input_box = InputBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='test',
            parent=parent,
            groups=groups,
        )
        input_box.active = False
        event = mocker.Mock()
        event.key = pygame.K_a
        event.unicode = 'a'
        input_box.on_key_down_event(event)
        assert input_box.text == 'test'

    def test_on_key_up_tab_deactivates(self, mocker):
        """Test Tab key deactivates input box."""
        groups = _RealLayeredDirty()
        parent = mocker.Mock()
        parent.x = 0
        parent.y = 0
        input_box = InputBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            parent=parent,
            groups=groups,
        )
        input_box.active = True
        event = mocker.Mock()
        event.key = pygame.K_TAB
        input_box.on_key_up_event(event)
        assert input_box.active is False

    def test_on_key_up_escape_deactivates(self, mocker):
        """Test Escape key deactivates input box."""
        groups = _RealLayeredDirty()
        parent = mocker.Mock()
        parent.x = 0
        parent.y = 0
        input_box = InputBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            parent=parent,
            groups=groups,
        )
        input_box.active = True
        event = mocker.Mock()
        event.key = pygame.K_ESCAPE
        input_box.on_key_up_event(event)
        assert input_box.active is False

    def test_activate_and_deactivate(self, mocker):
        """Test activate and deactivate methods."""
        groups = _RealLayeredDirty()
        parent = mocker.Mock()
        parent.x = 0
        parent.y = 0
        input_box = InputBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            parent=parent,
            groups=groups,
        )
        input_box.activate()
        assert input_box.active is True
        assert input_box.dirty == 2
        input_box.deactivate()
        assert input_box.active is False
        assert input_box.dirty == 0

    def test_on_input_box_submit_event_with_parent(self, mocker):
        """Test submit event delegates to parent."""
        groups = _RealLayeredDirty()
        parent = mocker.Mock()
        parent.x = 0
        parent.y = 0
        input_box = InputBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='submitted',
            parent=parent,
            groups=groups,
        )
        event = mocker.Mock()
        input_box.on_input_box_submit_event(event)
        parent.on_input_box_submit_event.assert_called_once()

    def test_on_input_box_submit_no_parent_handler(self, mocker):
        """Test submit event with parent that lacks handler."""
        groups = _RealLayeredDirty()
        parent = mocker.Mock()
        parent.x = 0
        parent.y = 0
        del parent.on_input_box_submit_event  # Remove handler
        input_box = InputBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='submitted',
            parent=parent,
            groups=groups,
        )
        event = mocker.Mock()
        # Should not raise, logs instead
        input_box.on_input_box_submit_event(event)

    def test_render_updates_text_image(self, mocker):
        """Test render updates the text image surface."""
        groups = _RealLayeredDirty()
        parent = mocker.Mock()
        parent.x = 0
        parent.y = 0
        input_box = InputBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='rendered',
            parent=parent,
            groups=groups,
        )
        input_box.render()
        assert input_box.text_image is not None

    def test_update_draws_input_box(self, mocker):
        """Test update draws the input box contents."""
        groups = _RealLayeredDirty()
        parent = mocker.Mock()
        parent.x = 0
        parent.y = 0
        input_box = InputBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='update',
            parent=parent,
            groups=groups,
        )
        input_box.update()  # Should not raise

    def test_on_mouse_up_activates(self, mocker):
        """Test mouse up event activates the input box."""
        groups = _RealLayeredDirty()
        parent = mocker.Mock()
        parent.x = 0
        parent.y = 0
        input_box = InputBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            parent=parent,
            groups=groups,
        )
        event = mocker.Mock()
        input_box.on_mouse_up_event(event)
        assert input_box.active is True


class TestTextBoxSpriteUpdateAndEvents:
    """Test TextBoxSprite update and mouse event methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_textbox_update_renders(self):
        """Test TextBoxSprite update renders correctly."""
        groups = _RealLayeredDirty()
        # No parent needed for this test
        textbox = TextBoxSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestTextBox',
            groups=groups,
        )
        textbox.dirty = 1
        textbox.update()  # Should not raise

    def test_textbox_update_nested_sprites(self):
        """Test update_nested_sprites propagates dirty."""
        groups = _RealLayeredDirty()
        textbox = TextBoxSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestTextBox',
            groups=groups,
        )
        textbox.dirty = 2
        textbox.update_nested_sprites()
        assert textbox.text_box.dirty == 2

    def test_textbox_mouse_down_sets_background(self, mocker):
        """Test left mouse button down changes background color."""
        groups = _RealLayeredDirty()
        textbox = TextBoxSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestTextBox',
            groups=groups,
        )
        event = mocker.Mock()
        textbox.on_left_mouse_button_down_event(event)
        assert textbox.background_color == (128, 128, 128)
        assert textbox.dirty == 1

    def test_textbox_mouse_up_resets_background(self, mocker):
        """Test left mouse button up resets background color."""
        groups = _RealLayeredDirty()
        textbox = TextBoxSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestTextBox',
            groups=groups,
        )
        textbox.background_color = (128, 128, 128)
        event = mocker.Mock()
        textbox.on_left_mouse_button_up_event(event)
        assert textbox.background_color == (0, 0, 0)
        assert textbox.dirty == 1


class TestColorWellSpriteDeeper:
    """Test ColorWellSprite hex_color and active_color setter."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_hex_color_returns_rrggbbaa(self):
        """Test hex_color returns correct format."""
        groups = _RealLayeredDirty()
        color_well = ColorWellSprite(
            x=TEST_X,
            y=TEST_Y,
            width=30,
            height=30,
            name='TestColorWell',
            groups=groups,
        )
        color_well.active_color = (255, 128, 0, 200)
        assert color_well.hex_color == '#FF8000C8'

    def test_active_color_setter_rgb(self):
        """Test active_color setter with RGB tuple defaults alpha to 255."""
        groups = _RealLayeredDirty()
        color_well = ColorWellSprite(
            x=TEST_X,
            y=TEST_Y,
            width=30,
            height=30,
            name='TestColorWell',
            groups=groups,
        )
        color_well.active_color = (100, 150, 200)
        assert color_well.red == 100
        assert color_well.green == 150
        assert color_well.blue == 200
        assert color_well.alpha == 255

    def test_active_color_setter_rgba(self):
        """Test active_color setter with RGBA tuple."""
        groups = _RealLayeredDirty()
        color_well = ColorWellSprite(
            x=TEST_X,
            y=TEST_Y,
            width=30,
            height=30,
            name='TestColorWell',
            groups=groups,
        )
        color_well.active_color = (100, 150, 200, 128)
        assert color_well.alpha == 128

    def test_update_nested_sprites_does_not_raise(self):
        """Test update_nested_sprites is a no-op (hex display hidden)."""
        groups = _RealLayeredDirty()
        color_well = ColorWellSprite(
            x=TEST_X,
            y=TEST_Y,
            width=30,
            height=30,
            name='TestColorWell',
            groups=groups,
        )
        color_well.update_nested_sprites()  # Should not raise

    def test_update_renders_color(self):
        """Test update renders the active color."""
        groups = _RealLayeredDirty()
        color_well = ColorWellSprite(
            x=TEST_X,
            y=TEST_Y,
            width=30,
            height=30,
            name='TestColorWell',
            groups=groups,
        )
        color_well.active_color = (255, 0, 0, 255)
        color_well.update()  # Should not raise


class TestTabControlSpriteEvents:
    """Test TabControlSprite event handling and update."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_tab_click_switches_active_tab(self, mocker):
        """Test clicking on a tab switches the active tab."""
        groups = _RealLayeredDirty()
        tab_control = TabControlSprite(
            x=TEST_X,
            y=TEST_Y,
            width=100,
            height=20,
            name='TestTabs',
            groups=groups,
        )
        # Click on the second tab (right half)
        event = mocker.Mock()
        event.pos = (TEST_X + 75, TEST_Y + 10)
        tab_control.on_left_mouse_button_down_event(event)
        assert tab_control.active_tab == 1

    def test_tab_click_outside_does_nothing(self, mocker):
        """Test clicking outside the tab control does nothing."""
        groups = _RealLayeredDirty()
        tab_control = TabControlSprite(
            x=TEST_X,
            y=TEST_Y,
            width=100,
            height=20,
            name='TestTabs',
            groups=groups,
        )
        event = mocker.Mock()
        event.pos = (500, 500)  # Outside
        tab_control.on_left_mouse_button_down_event(event)
        assert tab_control.active_tab == 0

    def test_tab_click_notifies_parent(self, mocker):
        """Test clicking on a tab notifies parent with on_tab_change_event."""
        groups = _RealLayeredDirty()
        parent = mocker.Mock()
        tab_control = TabControlSprite(
            x=TEST_X,
            y=TEST_Y,
            width=100,
            height=20,
            name='TestTabs',
            parent=parent,
            groups=groups,
        )
        event = mocker.Mock()
        event.pos = (TEST_X + 75, TEST_Y + 10)
        tab_control.on_left_mouse_button_down_event(event)
        parent.on_tab_change_event.assert_called_once_with('%X')

    def test_tab_update_renders_tabs(self):
        """Test update renders tab backgrounds and text."""
        groups = _RealLayeredDirty()
        tab_control = TabControlSprite(
            x=TEST_X,
            y=TEST_Y,
            width=100,
            height=20,
            name='TestTabs',
            groups=groups,
        )
        tab_control.dirty = 1
        tab_control.update()  # Should not raise


class TestSliderSpriteDeeper:
    """Test SliderSprite value setter and text input handling."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @staticmethod
    def _make_slider_parent(mocker):
        """Create a parent mock without visual_collision_manager.

        Mocks auto-create attributes, so visual_collision_manager would
        exist and trigger _draw_slider_visual_indicators which calls
        len() on a Mock. Deleting the attribute prevents that code path.

        Returns:
            A Mock parent object without visual_collision_manager.
        """
        parent = mocker.Mock()
        del parent.visual_collision_manager
        return parent

    def test_slider_value_setter_clamps(self, mocker):
        """Test slider value setter clamps to 0-255 range."""
        groups = _RealLayeredDirty()
        parent = self._make_slider_parent(mocker)
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='R',
            parent=parent,
            groups=groups,
        )
        slider.value = 300
        assert slider._value == 255
        slider.value = -10
        assert slider._value == 0

    def test_slider_update_calls_appearance(self, mocker):
        """Test slider update refreshes appearance when dirty."""
        groups = _RealLayeredDirty()
        parent = self._make_slider_parent(mocker)
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='G',
            parent=parent,
            groups=groups,
        )
        slider.dirty = 1
        slider.update()  # Should not raise

    def test_slider_on_mouse_up_stops_dragging(self, mocker):
        """Test mouse button up stops dragging."""
        groups = _RealLayeredDirty()
        parent = self._make_slider_parent(mocker)
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='B',
            parent=parent,
            groups=groups,
        )
        slider.dragging = True
        event = mocker.Mock()
        slider.on_left_mouse_button_up_event(event)
        assert slider.dragging is False

    def test_slider_restore_original_value(self, mocker):
        """Test _restore_original_value restores and deactivates text."""
        groups = _RealLayeredDirty()
        parent = self._make_slider_parent(mocker)
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='R',
            parent=parent,
            groups=groups,
        )
        slider.original_value = 42
        slider.text_sprite.active = True
        slider._restore_original_value()
        assert slider.text_sprite.text == '42'
        assert slider.text_sprite.active is False

    def test_slider_handle_text_enter_empty_restores(self, mocker):
        """Test _handle_text_enter with empty text restores original."""
        groups = _RealLayeredDirty()
        parent = self._make_slider_parent(mocker)
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='R',
            parent=parent,
            groups=groups,
        )
        slider.original_value = 100
        slider.text_sprite.text = ''
        event = mocker.Mock()
        slider._handle_text_enter(event)
        assert slider.text_sprite.text == '100'

    def test_slider_handle_text_enter_valid_decimal(self, mocker):
        """Test _handle_text_enter with valid decimal value."""
        groups = _RealLayeredDirty()
        parent = self._make_slider_parent(mocker)
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='R',
            parent=parent,
            groups=groups,
        )
        slider.text_sprite.text = '128'
        slider.text_sprite.active = True
        event = mocker.Mock()
        slider._handle_text_enter(event)
        assert slider._value == 128
        assert slider.text_sprite.active is False

    def test_slider_handle_text_enter_valid_hex(self, mocker):
        """Test _handle_text_enter with valid hex value."""
        groups = _RealLayeredDirty()
        parent = self._make_slider_parent(mocker)
        parent.slider_input_format = '%X'
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='R',
            parent=parent,
            groups=groups,
        )
        slider.text_sprite.text = 'ff'
        slider.text_sprite.active = True
        event = mocker.Mock()
        slider._handle_text_enter(event)
        assert slider._value == 255

    def test_slider_handle_text_enter_out_of_range_restores(self, mocker):
        """Test _handle_text_enter with out-of-range value restores."""
        groups = _RealLayeredDirty()
        parent = self._make_slider_parent(mocker)
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='R',
            parent=parent,
            groups=groups,
        )
        slider.original_value = 50
        slider.text_sprite.text = '999'
        event = mocker.Mock()
        slider._handle_text_enter(event)
        assert slider.text_sprite.text == '50'

    def test_slider_handle_text_character_input_backspace(self, mocker):
        """Test _handle_text_character_input with backspace."""
        groups = _RealLayeredDirty()
        parent = self._make_slider_parent(mocker)
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='R',
            parent=parent,
            groups=groups,
        )
        slider.text_sprite.text = '12'
        slider.text_sprite.active = True
        event = mocker.Mock()
        event.key = pygame.K_BACKSPACE
        slider._handle_text_character_input(event)
        assert slider.text_sprite.text == '1'

    def test_slider_handle_text_character_input_digit(self, mocker):
        """Test _handle_text_character_input with digit appends."""
        groups = _RealLayeredDirty()
        parent = self._make_slider_parent(mocker)
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='R',
            parent=parent,
            groups=groups,
        )
        slider.text_sprite.text = '1'
        slider.text_sprite.active = True
        event = mocker.Mock()
        event.key = pygame.K_5
        event.unicode = '5'
        slider._handle_text_character_input(event)
        assert slider.text_sprite.text == '15'

    def test_slider_handle_text_character_input_truncates_at_max(self, mocker):
        """Test _handle_text_character_input truncates at max length."""
        groups = _RealLayeredDirty()
        parent = self._make_slider_parent(mocker)
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='R',
            parent=parent,
            groups=groups,
        )
        slider.text_sprite.text = '255'
        slider.text_sprite.active = True
        event = mocker.Mock()
        event.key = pygame.K_9
        event.unicode = '9'
        slider._handle_text_character_input(event)
        # Should truncate to 3 chars
        assert len(slider.text_sprite.text) <= 3


class TestMenuBarAddMenuItem:
    """Test MenuBar add_menu_item method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_add_menu_item_without_menu_calls_add_menu(self):
        """Test add_menu_item without menu argument delegates to add_menu."""
        from glitchygames.ui import MenuBar

        groups = _RealLayeredDirty()
        menu_bar = MenuBar(x=0, y=0, width=800, height=30, groups=groups)
        menu_item = MenuItem(
            x=0,
            y=0,
            width=60,
            height=20,
            name='File',
            groups=groups,
        )
        menu_bar.add_menu_item(menu_item=menu_item)
        assert 'File' in menu_bar.menu_items

    def test_add_menu_item_with_menu_logs(self, mocker):
        """Test add_menu_item with menu argument logs."""
        from glitchygames.ui import MenuBar

        groups = _RealLayeredDirty()
        menu_bar = MenuBar(x=0, y=0, width=800, height=30, groups=groups)
        menu_item = MenuItem(
            x=0,
            y=0,
            width=60,
            height=20,
            name='New',
            groups=groups,
        )
        parent_menu = mocker.Mock()
        # Should not raise, just logs
        menu_bar.add_menu_item(menu_item=menu_item, menu=parent_menu)


class TestMenuBarGroupsNone:
    """Test MenuBar with groups=None default branch (line 71)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_menubar_groups_none_creates_default(self):
        """Test MenuBar creates default LayeredDirty when groups is None."""
        from glitchygames.ui import MenuBar

        menu_bar = MenuBar(x=0, y=0, width=800, height=30, groups=None)
        assert menu_bar.all_sprites is not None


class TestMenuItemLeftMouseButtonUpSubitems:
    """Test MenuItem on_left_mouse_button_up_event with subitems (line 322)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_left_mouse_button_up_delegates_to_subitems(self, mocker):
        """Test on_left_mouse_button_up_event forwards to submenu items."""
        from glitchygames.ui import MenuBar

        groups = _RealLayeredDirty()
        menu_bar = MenuBar(x=0, y=0, width=800, height=30, groups=groups)

        # Create a menu item and add it
        menu_item = MenuItem(
            x=0,
            y=0,
            width=60,
            height=20,
            name='File',
            groups=groups,
        )
        # Add a sub-menu item to the menu item
        sub_item = mocker.Mock()
        sub_item.on_left_mouse_button_up_event = mocker.Mock()
        menu_item.menu_items = {'SubItem': sub_item}

        # Add the menu_item to the menu_bar
        menu_bar.add_menu_item(menu_item=menu_item)

        # Fake a collision by inserting the menu_item into all_sprites
        event = mocker.Mock()
        event.pos = (5, 5)

        # Mock spritecollide to return the menu item
        mocker.patch('pygame.sprite.spritecollide', return_value=[menu_item])

        menu_bar.on_left_mouse_button_up_event(event)
        sub_item.on_left_mouse_button_up_event.assert_called_once_with(event)


class TestMenuItemAddMenuItemNoneMenu:
    """Test MenuItem add_menu_item when menu is None (lines 534-535)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_add_menu_item_with_none_menu_calls_add_menu(self, mocker):
        """Test add_menu_item with menu=None delegates to add_menu."""
        groups = _RealLayeredDirty()
        menu_item = MenuItem(
            x=0,
            y=0,
            width=60,
            height=20,
            name='File',
            groups=groups,
        )
        # Mock add_menu to avoid the full layout recalculation
        menu_item.add_menu = mocker.Mock()
        sub_item = MenuItem(
            x=0,
            y=0,
            width=60,
            height=20,
            name='New',
            groups=groups,
        )
        menu_item.add_menu_item(menu_item=sub_item, menu=None)
        menu_item.add_menu.assert_called_once_with(menu=sub_item)


class TestMenuItemMouseEventSubmenus:
    """Test MenuItem mouse event propagation to submenu items (lines 633, 663, 692).

    Note: The source code iterates over dict keys (strings) and then calls
    event methods on those keys. The keys in menu_items are submenu name strings.
    To cover these lines, we use mock objects as dict keys that have the event methods.
    """

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def _make_collided_sprite_with_submenu_keys(self, mocker):
        """Create a collided_sprite mock with mock objects as dict keys.

        The source code does: `for submenu in collided_sprite.menu_items:`
        which iterates dict keys, then calls `.on_mouse_*_event(event)` on them.
        We use mock objects as dict keys to make this work.

        Returns:
            tuple: (collided_sprite, submenu_key) mock objects.

        """
        collided_sprite = mocker.Mock()
        submenu_key = mocker.Mock()
        submenu_key.on_mouse_motion_event = mocker.Mock()
        submenu_key.on_mouse_enter_event = mocker.Mock()
        submenu_key.on_mouse_exit_event = mocker.Mock()
        collided_sprite.menu_items = {submenu_key: mocker.Mock()}
        return collided_sprite, submenu_key

    def test_on_mouse_motion_event_propagates_to_submenus(self, mocker):
        """Test on_mouse_motion_event propagates to submenu keys (line 633)."""
        groups = _RealLayeredDirty()
        menu_item = MenuItem(
            x=0,
            y=0,
            width=60,
            height=20,
            name='File',
            groups=groups,
        )
        collided_sprite, submenu_key = self._make_collided_sprite_with_submenu_keys(mocker)
        collided_sprite.name = 'File'
        menu_item.menu_items = {'File': collided_sprite}

        event = mocker.Mock()
        event.pos = (5, 5)
        mocker.patch('pygame.sprite.spritecollide', return_value=[collided_sprite])

        menu_item.on_mouse_motion_event(event)
        submenu_key.on_mouse_motion_event.assert_called_with(event)

    def test_on_mouse_enter_event_propagates_to_submenus(self, mocker):
        """Test on_mouse_enter_event propagates to submenu keys (line 663)."""
        groups = _RealLayeredDirty()
        menu_item = MenuItem(
            x=0,
            y=0,
            width=60,
            height=20,
            name='File',
            groups=groups,
        )
        collided_sprite, submenu_key = self._make_collided_sprite_with_submenu_keys(mocker)
        collided_sprite.name = 'File'
        menu_item.menu_items = {'File': collided_sprite}

        event = mocker.Mock()
        event.pos = (5, 5)
        mocker.patch('pygame.sprite.spritecollide', return_value=[collided_sprite])

        menu_item.on_mouse_enter_event(event)
        submenu_key.on_mouse_enter_event.assert_called_with(event)
        assert menu_item.has_focus is True

    def test_on_mouse_exit_event_propagates_to_submenus(self, mocker):
        """Test on_mouse_exit_event propagates to submenu keys (line 692)."""
        groups = _RealLayeredDirty()
        menu_item = MenuItem(
            x=0,
            y=0,
            width=60,
            height=20,
            name='File',
            groups=groups,
        )
        collided_sprite, submenu_key = self._make_collided_sprite_with_submenu_keys(mocker)
        collided_sprite.name = 'File'
        menu_item.menu_items = {'File': collided_sprite}

        event = mocker.Mock()
        event.pos = (5, 5)
        mocker.patch('pygame.sprite.spritecollide', return_value=[collided_sprite])

        menu_item.on_mouse_exit_event(event)
        # Line 692 calls on_mouse_enter_event on the submenu key (not exit)
        submenu_key.on_mouse_enter_event.assert_called_with(event)
        assert menu_item.has_focus is False


class TestTextSpiteRenderPygameFont:
    """Test TextSprite _render_with_pygame_font path (lines 1011, 1032)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_text_with_non_freetype_font(self, mocker):
        """Test _render_text_with_font fallback to pygame.font style (line 1011)."""
        groups = _RealLayeredDirty()
        text_sprite = TextSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='test',
            groups=groups,
        )
        # Create a mock font that is NOT freetype (no render_to)
        mock_font = mocker.Mock(spec=['render'])
        mock_font.render.return_value = pygame.Surface((50, 20))

        surface = text_sprite._render_with_pygame_font(
            mock_font, 'hello', (255, 255, 255), is_transparent=False
        )
        assert surface is not None
        mock_font.render.assert_called_once()

    def test_render_with_pygame_font_transparent(self, mocker):
        """Test _render_with_pygame_font with transparent background (line 1032)."""
        groups = _RealLayeredDirty()
        text_sprite = TextSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='test',
            groups=groups,
        )
        mock_font = mocker.Mock(spec=['render'])
        mock_font.render.return_value = pygame.Surface((50, 20))

        surface = text_sprite._render_with_pygame_font(
            mock_font, 'hello', (255, 255, 255), is_transparent=True
        )
        assert surface is not None


class TestInputBoxCursorBlink:
    """Test InputBox cursor blink during update (lines 1403-1407)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_draws_cursor_when_active_and_blink_visible(self, mocker):
        """Test InputBox update draws cursor when active and in blink cycle."""
        groups = _RealLayeredDirty()
        parent = mocker.Mock()
        parent.x = 0
        parent.y = 0
        input_box = InputBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='hello',
            parent=parent,
            groups=groups,
        )
        input_box.active = True
        # Mock time.time to return a value that triggers cursor draw
        # time.time() % 1 > 0.5 when e.g. time returns 1.7
        mocker.patch('glitchygames.ui.widgets.time.time', return_value=1.7)
        input_box.update()
        # Should have drawn cursor rect; verify it doesn't raise


class TestSliderKnobSpriteInit:
    """Test SliderKnobSprite initialization (lines 1602-1614)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_slider_knob_sprite_inner_class_init_none_groups(self, mocker):
        """Test SliderKnobSprite inner class with groups=None (lines 1602-1614)."""
        # Access the inner class directly
        knob_class = SliderSprite.SliderKnobSprite
        parent = mocker.Mock()
        knob = knob_class(
            x=TEST_X,
            y=TEST_Y,
            width=5,
            height=9,
            name='R_knob',
            parent=parent,
            groups=None,
        )
        assert knob.value == 0
        assert knob.rect.x == TEST_X
        assert knob.rect.y == TEST_Y


class TestSliderKnobDragEvent:
    """Test SliderKnobSprite on_left_mouse_drag_event (lines 1650-1651)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_knob_drag_calls_mouse_down(self, mocker):
        """Test SliderKnobSprite on_left_mouse_drag_event delegates and marks dirty."""
        knob_class = SliderSprite.SliderKnobSprite
        parent = mocker.Mock()
        groups = _RealLayeredDirty()
        knob = knob_class(
            x=TEST_X,
            y=TEST_Y,
            width=5,
            height=9,
            name='R_knob',
            parent=parent,
            groups=groups,
        )
        # Mock on_left_mouse_button_down_event since the inherited version
        # needs callbacks attribute
        knob.on_left_mouse_button_down_event = mocker.Mock()
        knob.dirty = 0
        event = mocker.Mock()
        event.pos = (TEST_X + 2, TEST_Y + 3)
        trigger = mocker.Mock()
        knob.on_left_mouse_drag_event(event, trigger)
        knob.on_left_mouse_button_down_event.assert_called_once_with(event)
        assert knob.dirty == 1


class TestSliderTextInputInactive:
    """Test slider text input when inactive (line 1805)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_handle_text_input_when_inactive_returns_early(self, mocker):
        """Test text input handler returns early when text_sprite is not active."""
        parent = mocker.Mock()
        del parent.visual_collision_manager
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='R',
            parent=parent,
            groups=_RealLayeredDirty(),
        )
        slider.text_sprite.active = False
        event = mocker.Mock()
        event.key = pygame.K_RETURN
        event.unicode = ''
        # Call the handler directly; it should return early without error
        slider.text_sprite.on_key_down_event(event)


class TestSliderTextClickOutside:
    """Test slider text click returning False (line 1830)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_text_click_outside_returns_false(self, mocker):
        """Test clicking outside text sprite returns False (line 1830).

        The text_sprite.rect may be a Mock from the patched Surface, so we
        need to ensure it's a real pygame.Rect for collidepoint to work correctly.
        The closure `handle_text_click` checks `self.text_sprite.rect.collidepoint(event.pos)`.
        """
        parent = mocker.Mock()
        del parent.visual_collision_manager
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='R',
            parent=parent,
            groups=_RealLayeredDirty(),
        )
        # Force text_sprite to have a real rect
        slider.text_sprite.rect = pygame.Rect(TEST_X + 260, TEST_Y, 30, 9)
        # Create a simple object with pos attribute as a tuple

        class SimpleEvent:
            pos = (9999, 9999)

        result = slider.text_sprite.on_left_mouse_button_down_event(SimpleEvent())
        assert result is False


class TestSliderTriangleIndicator:
    """Test SliderSprite triangle indicator drawing (lines 1962-1975)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_draw_triangle_indicator(self, mocker):
        """Test _draw_slider_visual_indicators with triangle-shaped indicator."""
        from glitchygames.tools.visual_collision_manager import (
            IndicatorShape,
        )

        parent = mocker.Mock()
        # Initially disable visual_collision_manager for slider construction
        del parent.visual_collision_manager
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='R',
            parent=parent,
            groups=_RealLayeredDirty(),
        )

        # Ensure slider has a real pygame Surface for drawing
        slider.image = pygame.Surface((256, 9))

        # Now re-enable visual_collision_manager with triangle indicators
        mock_indicator = mocker.Mock()
        mock_indicator.shape = IndicatorShape.TRIANGLE
        mock_indicator.color = (255, 0, 0)
        mock_indicator.size = 10
        mock_indicator.position = (50, 4)
        parent.visual_collision_manager = mocker.Mock()
        parent.visual_collision_manager.get_indicators_by_location.return_value = {
            0: mock_indicator,
        }

        # Should draw the triangle without error
        slider._draw_slider_visual_indicators()


class TestSliderUpdateColorWellBranches:
    """Test update_color_well for G, B, A branches (lines 2056-2061)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def _make_parent_with_color_well(self, mocker):
        """Create a parent mock with color_well and all slider attrs.

        Returns:
            Mock: A configured parent mock with color_well and slider attributes.

        """
        parent = mocker.Mock()
        del parent.visual_collision_manager
        parent.color_well = mocker.Mock()
        parent.red_slider = mocker.Mock()
        parent.red_slider.value = 0
        parent.green_slider = mocker.Mock()
        parent.green_slider.value = 0
        parent.blue_slider = mocker.Mock()
        parent.blue_slider.value = 0
        parent.alpha_slider = mocker.Mock()
        parent.alpha_slider.value = 255
        return parent

    def test_update_color_well_green(self, mocker):
        """Test update_color_well for G slider sets green value."""
        parent = self._make_parent_with_color_well(mocker)
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='G',
            parent=parent,
            groups=_RealLayeredDirty(),
        )
        slider._value = 128
        slider.update_color_well()
        assert parent.green_slider.value == 128

    def test_update_color_well_blue(self, mocker):
        """Test update_color_well for B slider sets blue value."""
        parent = self._make_parent_with_color_well(mocker)
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='B',
            parent=parent,
            groups=_RealLayeredDirty(),
        )
        slider._value = 64
        slider.update_color_well()
        assert parent.blue_slider.value == 64

    def test_update_color_well_alpha(self, mocker):
        """Test update_color_well for A slider sets alpha value."""
        parent = self._make_parent_with_color_well(mocker)
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='A',
            parent=parent,
            groups=_RealLayeredDirty(),
        )
        slider._value = 200
        slider.update_color_well()
        assert parent.alpha_slider.value == 200


class TestSliderMouseDownWithParentEvent:
    """Test SliderSprite on_left_mouse_button_down_event with on_slider_event (lines 2083-2086)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_mouse_down_calls_parent_on_slider_event(self, mocker):
        """Test clicking on slider calls parent.on_slider_event."""
        parent = mocker.Mock()
        del parent.visual_collision_manager
        del parent.slider_input_format
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='R',
            parent=parent,
            groups=_RealLayeredDirty(),
        )
        # Click within slider rect
        event = mocker.Mock()
        event.pos = (TEST_X + 128, TEST_Y + 4)
        slider.on_left_mouse_button_down_event(event)
        parent.on_slider_event.assert_called_once()

    def test_mouse_down_hex_format(self, mocker):
        """Test clicking on slider with hex format updates text (line 2097)."""
        parent = mocker.Mock()
        del parent.visual_collision_manager
        parent.slider_input_format = '%X'
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='R',
            parent=parent,
            groups=_RealLayeredDirty(),
        )
        event = mocker.Mock()
        event.pos = (TEST_X + 128, TEST_Y + 4)
        slider.on_left_mouse_button_down_event(event)
        # Text should be hex format
        assert all(c in '0123456789ABCDEF' for c in slider.text_sprite.text)

    def test_mouse_down_outside_slider_logs(self, mocker):
        """Test clicking outside slider rect (line 2103)."""
        parent = mocker.Mock()
        del parent.visual_collision_manager
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='R',
            parent=parent,
            groups=_RealLayeredDirty(),
        )
        event = mocker.Mock()
        event.pos = (9999, 9999)  # Outside
        slider.on_left_mouse_button_down_event(event)
        # Should not call on_slider_event
        parent.on_slider_event.assert_not_called()


class TestSliderDragWithParentEvent:
    """Test SliderSprite on_mouse_motion_event drag (lines 2121-2124, 2135)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_drag_calls_parent_on_slider_event(self, mocker):
        """Test dragging slider calls parent.on_slider_event."""
        parent = mocker.Mock()
        del parent.visual_collision_manager
        del parent.slider_input_format
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='R',
            parent=parent,
            groups=_RealLayeredDirty(),
        )
        slider.dragging = True
        event = mocker.Mock()
        event.pos = (TEST_X + 100, TEST_Y + 4)
        slider.on_mouse_motion_event(event)
        parent.on_slider_event.assert_called_once()

    def test_drag_hex_format_updates_text(self, mocker):
        """Test dragging slider with hex format updates text (line 2135)."""
        parent = mocker.Mock()
        del parent.visual_collision_manager
        parent.slider_input_format = '%X'
        slider = SliderSprite(
            x=TEST_X,
            y=TEST_Y,
            width=256,
            height=9,
            name='R',
            parent=parent,
            groups=_RealLayeredDirty(),
        )
        slider.dragging = True
        event = mocker.Mock()
        event.pos = (TEST_X + 100, TEST_Y + 4)
        slider.on_mouse_motion_event(event)
        assert all(c in '0123456789ABCDEF' for c in slider.text_sprite.text)


class TestTabControlFontError:
    """Test TabControlSprite font error handling (lines 2391-2393)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_handles_font_error_gracefully(self, mocker):
        """Test tab update catches font errors without raising."""
        groups = _RealLayeredDirty()
        tab_control = TabControlSprite(
            x=TEST_X,
            y=TEST_Y,
            width=100,
            height=20,
            name='TestTabs',
            groups=groups,
        )
        tab_control.dirty = 1
        # Make font.render raise pygame.error
        mocker.patch('pygame.font.Font', side_effect=pygame.error('Font error'))
        tab_control.update()  # Should not raise


class TestMultiLineTextBoxCursorNavigation:
    """Test MultiLineTextBox cursor navigation edge cases."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def _make_textbox(self, mocker, text='Line1\nLine2\nLine3'):
        """Create a MultiLineTextBox for testing.

        Patches FontManager.get_font to return a font with numeric get_rect().width
        so that _get_text_width returns an int, not a Mock.

        Returns:
            MultiLineTextBox: A configured text box for testing.
        """
        # Ensure the font's get_rect returns a real Rect with numeric width
        mock_font_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        mock_font = mock_font_get_font.return_value
        mock_font.get_linesize.return_value = 16
        mock_font.get_rect.return_value = pygame.Rect(0, 0, 50, 16)
        mock_font.size.return_value = (50, 16)

        def mock_render(*args, **kwargs):
            text_arg = str(args[0]) if args else 'X'
            width = max(1, len(text_arg) * 8)
            surface = pygame.Surface((width, 16))
            rect = pygame.Rect(0, 0, width, 16)
            return surface, rect

        mock_font.render = mock_render

        groups = _RealLayeredDirty()
        textbox = MultiLineTextBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=100,
            name='TestMLTB',
            groups=groups,
        )
        textbox.text = text
        return textbox

    def test_move_cursor_up_at_top_goes_to_beginning(self, mocker):
        """Test _move_cursor_up at top line moves cursor to 0 (line 3056)."""
        textbox = self._make_textbox(mocker)
        textbox.cursor_pos = 2  # Middle of first line
        textbox._move_cursor_up()
        assert textbox.cursor_pos == 0

    def test_move_cursor_down_at_bottom_goes_to_end(self, mocker):
        """Test _move_cursor_down at bottom line moves to end (line 3077)."""
        textbox = self._make_textbox(mocker)
        textbox.cursor_pos = len(textbox._original_text) - 1  # Near end
        textbox._move_cursor_down()
        assert textbox.cursor_pos == len(textbox._original_text)

    def test_map_wrapped_position_out_of_bounds(self, mocker):
        """Test _map_wrapped_position_to_original with line beyond wrap (line 3089)."""
        textbox = self._make_textbox(mocker, text='short')
        result = textbox._map_wrapped_position_to_original(line=999, column=0)
        assert result == len(textbox._original_text)

    def test_map_cursor_pos_fallback_return(self, mocker):
        """Test _map_cursor_pos_to_wrapped_text fallback return (line 3008).

        When the wrapped text has fewer occurrences of the target character
        than the original text (e.g., due to wrapping removing chars), the
        fallback path returns min(wrapped_pos, len(self._text)).
        """
        textbox = self._make_textbox(mocker, text='aaa')
        # Manipulate _text to have fewer 'a's than _original_text so the
        # char_count loop exhausts without matching
        textbox._original_text = 'aaa'
        textbox._text = 'a'  # Only 1 'a' in wrapped text vs 3 in original
        # Position 2 needs 3rd 'a' (char_count_before_target=2) but wrapped text only has 1
        result = textbox._map_cursor_pos_to_wrapped_text(2)
        assert result >= 0

    def test_get_line_height_freetype_fallback(self, mocker):
        """Test _get_line_height returns font.size for freetype (line 3145)."""
        textbox = self._make_textbox(mocker)
        # Remove get_linesize to simulate freetype font
        mock_font = mocker.Mock(spec=['size'])
        mock_font.size = 18
        textbox.font = mock_font
        result = textbox._get_line_height()
        assert result == 18

    def test_get_line_height_no_size_attribute(self, mocker):
        """Test _get_line_height returns 24 when no size attribute."""
        textbox = self._make_textbox(mocker)
        mock_font = mocker.Mock(spec=[])
        textbox.font = mock_font
        result = textbox._get_line_height()
        assert result == 24


class TestMultiLineTextBoxScrolling:
    """Test MultiLineTextBox auto-scroll and cursor visibility (lines 3163, 3171-3172, 3212)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def _setup_mock_font(self, mocker):
        """Set up mock font with numeric get_rect widths.

        The mock font needs get_rect for _get_text_width, and render needs
        to return (surface, rect) tuple since get_rect exists (freetype style).
        """
        mock_font_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        mock_font = mock_font_get_font.return_value
        mock_font.get_linesize.return_value = 16
        mock_font.get_rect.return_value = pygame.Rect(0, 0, 50, 16)
        mock_font.size.return_value = (50, 16)

        def mock_render(*args, **kwargs):
            text_arg = str(args[0]) if args else 'X'
            width = max(1, len(text_arg) * 8)
            surface = pygame.Surface((width, 16))
            rect = pygame.Rect(0, 0, width, 16)
            return surface, rect

        mock_font.render = mock_render

    def _make_textbox_with_many_lines(self, mocker):
        """Create a MultiLineTextBox with many lines for scrolling tests.

        Returns:
            MultiLineTextBox: A configured text box with 30 lines.

        """
        self._setup_mock_font(mocker)
        groups = _RealLayeredDirty()
        textbox = MultiLineTextBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=60,
            name='TestMLTB',
            groups=groups,
        )
        # Create enough text to require scrolling
        lines = [f'Line {i}' for i in range(30)]
        textbox.text = '\n'.join(lines)
        return textbox

    def test_auto_scroll_when_cursor_below_visible(self, mocker):
        """Test auto-scroll adjusts when cursor is below visible area (line 3171)."""
        textbox = self._make_textbox_with_many_lines(mocker)
        textbox.active = True
        textbox.scroll_offset = 0
        # Move cursor to last line
        textbox.cursor_pos = len(textbox._original_text)
        # Render should auto-scroll
        textbox._render_visible_lines((255, 255, 255), 16)
        assert textbox.scroll_offset > 0

    def test_auto_scroll_when_cursor_above_visible(self, mocker):
        """Test auto-scroll adjusts when cursor is above visible area (line 3172)."""
        textbox = self._make_textbox_with_many_lines(mocker)
        textbox.active = True
        textbox.scroll_offset = 20  # Scrolled down
        textbox.cursor_pos = 0  # Cursor at beginning
        textbox._render_visible_lines((255, 255, 255), 16)
        assert textbox.scroll_offset == 0

    def test_cursor_not_in_visible_range_not_drawn(self, mocker):
        """Test cursor is not drawn when outside visible range (line 3212)."""
        textbox = self._make_textbox_with_many_lines(mocker)
        textbox.active = True
        textbox.cursor_visible = True
        textbox.scroll_offset = 20  # Scrolled far down
        textbox.cursor_pos = 0  # Cursor at top
        textbox.cursor_blink_time = 0
        # Should not raise even though cursor is outside visible range
        textbox._update_cursor_blink(pygame.time.get_ticks(), 16)


class TestMultiLineTextBoxMouseEvents:
    """Test MultiLineTextBox mouse event handlers (lines 3287-3289, 3307, 3338-3342)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def _setup_mock_font(self, mocker):
        """Set up mock font with numeric get_rect widths."""
        mock_font_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        mock_font = mock_font_get_font.return_value
        mock_font.get_linesize.return_value = 16
        mock_font.get_rect.return_value = pygame.Rect(0, 0, 50, 16)
        mock_font.size.return_value = (50, 16)

        def mock_render(*args, **kwargs):
            text_arg = str(args[0]) if args else 'X'
            width = max(1, len(text_arg) * 8)
            surface = pygame.Surface((width, 16))
            rect = pygame.Rect(0, 0, width, 16)
            return surface, rect

        mock_font.render = mock_render

    def _make_textbox(self, mocker, text='Hello World'):
        """Create a MultiLineTextBox for testing.

        Returns:
            MultiLineTextBox: A configured text box for testing.

        """
        self._setup_mock_font(mocker)
        groups = _RealLayeredDirty()
        textbox = MultiLineTextBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=100,
            name='TestMLTB',
            groups=groups,
        )
        textbox.text = text
        return textbox

    def test_mouse_down_on_scrollbar(self, mocker):
        """Test mouse down on scrollbar handles event (lines 3287-3289)."""
        textbox = self._make_textbox(mocker)
        # Mock scrollbar to handle the click
        textbox.scrollbar.handle_mouse_down = mocker.Mock(return_value=True)
        textbox.scrollbar.scroll_offset = 5
        event = mocker.Mock()
        event.pos = (TEST_X + TEST_WIDTH - 5, TEST_Y + 5)
        textbox.on_left_mouse_button_down_event(event)
        assert textbox.scroll_offset == 5

    def test_mouse_down_outside_deactivates(self, mocker):
        """Test clicking outside textbox deactivates it (lines 3338-3342)."""
        textbox = self._make_textbox(mocker)
        textbox.active = True
        # Ensure textbox has a real rect for collidepoint
        textbox.rect = pygame.Rect(TEST_X, TEST_Y, TEST_WIDTH, 100)
        far_away = (textbox.rect.right + 500, textbox.rect.bottom + 500)
        event = mocker.Mock()
        event.pos = far_away
        textbox.on_left_mouse_button_down_event(event)
        assert textbox.active is False

    def test_mouse_down_line_height_no_size_fallback(self, mocker):
        """Test mouse down uses 24 default for line height (line 3307 else branch).

        When font has no get_linesize and no size attribute, line 3307 falls back to 24.
        """
        textbox = self._make_textbox(mocker)
        # Force a real rect for collidepoint
        textbox.rect = pygame.Rect(TEST_X, TEST_Y, TEST_WIDTH, 100)
        # Replace font with one that lacks both get_linesize and size
        mock_font = mocker.Mock()
        del mock_font.get_linesize
        del mock_font.size
        # Keep get_rect so _get_text_width uses it (avoids the size(text) conflict)
        mock_font.get_rect.return_value = pygame.Rect(0, 0, 50, 16)
        mock_font.render.return_value = (pygame.Surface((50, 16)), pygame.Rect(0, 0, 50, 16))
        textbox.font = mock_font
        event = mocker.Mock()
        event.pos = (TEST_X + 5, TEST_Y + 5)
        textbox.on_left_mouse_button_down_event(event)
        assert textbox.active is True


class TestMultiLineTextBoxDeleteSelection:
    """Test MultiLineTextBox _handle_delete_selection path (line 3394)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def _setup_mock_font(self, mocker):
        """Set up mock font with numeric get_rect widths."""
        mock_font_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        mock_font = mock_font_get_font.return_value
        mock_font.get_linesize.return_value = 16
        mock_font.get_rect.return_value = pygame.Rect(0, 0, 50, 16)
        mock_font.size.return_value = (50, 16)

        def mock_render(*args, **kwargs):
            text_arg = str(args[0]) if args else 'X'
            width = max(1, len(text_arg) * 8)
            surface = pygame.Surface((width, 16))
            rect = pygame.Rect(0, 0, width, 16)
            return surface, rect

        mock_font.render = mock_render

    def test_delete_key_with_selection(self, mocker):
        """Test delete key with active selection removes selected text."""
        self._setup_mock_font(mocker)
        groups = _RealLayeredDirty()
        textbox = MultiLineTextBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=100,
            name='TestMLTB',
            groups=groups,
        )
        textbox.text = 'Hello World'
        textbox.active = True
        textbox.selection_start = 5
        textbox.selection_end = 11
        event = mocker.Mock()
        event.key = pygame.K_DELETE
        event.mod = 0
        textbox.on_key_down_event(event)
        assert 'World' not in textbox.text


class TestMultiLineTextBoxHoverExit:
    """Test MultiLineTextBox mouse motion hover exit (lines 3591-3593)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def _setup_mock_font(self, mocker):
        """Set up mock font with numeric get_rect widths."""
        mock_font_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        mock_font = mock_font_get_font.return_value
        mock_font.get_linesize.return_value = 16
        mock_font.get_rect.return_value = pygame.Rect(0, 0, 50, 16)
        mock_font.size.return_value = (50, 16)

    def test_mouse_exit_clears_hover(self, mocker):
        """Test mouse motion outside textbox clears hover state."""
        self._setup_mock_font(mocker)
        groups = _RealLayeredDirty()
        textbox = MultiLineTextBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=100,
            name='TestMLTB',
            groups=groups,
        )
        textbox.is_hovered = True
        # Force real rect for collidepoint
        textbox.rect = pygame.Rect(TEST_X, TEST_Y, TEST_WIDTH, 100)
        textbox.scrollbar.handle_mouse_motion = mocker.Mock(return_value=False)
        event = mocker.Mock()
        event.pos = (9999, 9999)  # Outside
        textbox.on_mouse_motion_event(event)
        assert textbox.is_hovered is False


class TestMultiLineTextBoxMouseWheel:
    """Test MultiLineTextBox mouse wheel with pygame 1.9 style (lines 3622-3627)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def _setup_mock_font(self, mocker):
        """Set up mock font with numeric get_rect widths."""
        mock_font_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        mock_font = mock_font_get_font.return_value
        mock_font.get_linesize.return_value = 16
        mock_font.get_rect.return_value = pygame.Rect(0, 0, 50, 16)
        mock_font.size.return_value = (50, 16)

    def test_mouse_wheel_pygame19_scroll_up(self, mocker):
        """Test mouse wheel with button 4 (scroll up) in pygame 1.9 style."""
        self._setup_mock_font(mocker)
        groups = _RealLayeredDirty()
        textbox = MultiLineTextBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=60,
            name='TestMLTB',
            groups=groups,
        )
        lines = [f'Line {i}' for i in range(30)]
        textbox.text = '\n'.join(lines)
        textbox.scroll_offset = 10
        mocker.patch('pygame.mouse.get_pos', return_value=(TEST_X + 5, TEST_Y + 5))
        event = mocker.Mock(spec=['button'])  # No 'y' attribute
        event.button = 4  # PYGAME_MOUSE_SCROLL_UP_BUTTON
        textbox.on_mouse_wheel_event(event)
        assert textbox.scroll_offset < 10

    def test_mouse_wheel_pygame19_scroll_down(self, mocker):
        """Test mouse wheel with button 5 (scroll down) in pygame 1.9 style."""
        self._setup_mock_font(mocker)
        groups = _RealLayeredDirty()
        textbox = MultiLineTextBox(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=60,
            name='TestMLTB',
            groups=groups,
        )
        lines = [f'Line {i}' for i in range(30)]
        textbox.text = '\n'.join(lines)
        textbox.scroll_offset = 5
        mocker.patch('pygame.mouse.get_pos', return_value=(TEST_X + 5, TEST_Y + 5))
        event = mocker.Mock(spec=['button'])  # No 'y' attribute
        event.button = 5  # PYGAME_MOUSE_SCROLL_DOWN_BUTTON
        textbox.on_mouse_wheel_event(event)
        assert textbox.scroll_offset > 5


class TestConfirmDialogNonTupleRender:
    """Test ConfirmDialog render fallbacks for non-tuple font.render (lines 3729, 3744, 3757)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_with_non_tuple_font_render(self, mocker):
        """Test ConfirmDialog update when font.render returns Surface (not tuple)."""
        from glitchygames.ui.widgets import ConfirmDialog

        groups = _RealLayeredDirty()
        # Mock FontManager.get_font to return a font that returns Surface (not tuple)
        mock_font = mocker.Mock()
        surface = pygame.Surface((50, 20))
        mock_font.render.return_value = surface  # Returns Surface, not tuple
        mocker.patch('glitchygames.ui.widgets.FontManager.get_font', return_value=mock_font)

        dialog = ConfirmDialog(
            text='Delete?',
            confirm_callback=mocker.Mock(),
            cancel_callback=mocker.Mock(),
            x=0,
            y=0,
            width=300,
            height=100,
            groups=groups,
        )
        # Ensure dialog has a real image surface for drawing
        dialog.image = pygame.Surface((300, 100))
        dialog.rect = pygame.Rect(0, 0, 300, 100)
        dialog.dirty = 1
        dialog.update()  # Should handle non-tuple render results
