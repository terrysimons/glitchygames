"""Tests for the Bitmappy SliderManager (glitchygames/bitmappy/slider_manager.py).

The sliders, color well, tab control and bounding boxes are built for real by
``setup_sliders_and_color_well`` on a lightweight editor stand-in, so the tests
check the state the manager leaves behind rather than calls on mocks.
"""

from types import SimpleNamespace

import pygame
import pytest

from glitchygames import events
from glitchygames.bitmappy.slider_manager import SliderManager

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
TRANSPARENT = (0, 0, 0, 0)


class _EditorStandIn:
    """Minimal editor carrying the attributes SliderManager reads and writes."""

    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.screen_width = SCREEN_WIDTH
        self.screen_height = SCREEN_HEIGHT
        self.all_sprites = pygame.sprite.LayeredDirty()
        self.canvas = SimpleNamespace(active_color=None, pixels_across=32, pixel_width=16)
        self.dirty = 0

    def on_slider_event(self, event, trigger) -> None:
        """Pass a slider's value change to the slider manager, as the editor does."""
        self.slider_manager.on_slider_event(event=event, trigger=trigger)


@pytest.fixture
def screen():
    """Provide a display surface on the dummy video driver.

    Returns:
        pygame.Surface: The display surface.

    """
    if not pygame.get_init():
        pygame.init()
    return pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))


@pytest.fixture
def editor(screen):
    """Provide an editor stand-in whose sliders were set up by a SliderManager.

    Returns:
        _EditorStandIn: The editor, with ``slider_manager`` attached.

    """
    editor_stand_in = _EditorStandIn(screen=screen)
    slider_manager = SliderManager(editor_stand_in)  # type: ignore[arg-type]
    slider_manager.setup_sliders_and_color_well()
    editor_stand_in.slider_manager = slider_manager  # type: ignore[attr-defined]
    return editor_stand_in


def _center_of(rect: pygame.Rect) -> tuple[int, int]:
    """Return the center point of a rect as a plain tuple.

    Returns:
        tuple[int, int]: The center point.

    """
    return (rect.centerx, rect.centery)


def _outside_everything() -> tuple[int, int]:
    """Return a point that hovers over no slider or text box.

    Returns:
        tuple[int, int]: A point in the top-left corner of the screen.

    """
    return (1, 1)


class TestSetup:
    """Test the real slider, color well and bounding box setup."""

    def test_setup_initializes_values_and_colors(self, editor):
        """Sliders start at opaque black and the canvas color follows the well."""
        assert editor.alpha_slider.value == 255
        assert (editor.red_slider.value, editor.green_slider.value, editor.blue_slider.value) == (
            0,
            0,
            0,
        )
        assert editor.color_well.active_color == (0, 0, 0, 255)
        assert editor.canvas.active_color == (0, 0, 0, 255)
        assert editor.slider_input_format == '%d'

    def test_bounding_boxes_start_hidden_around_their_sliders(self, editor):
        """Each bounding box surrounds its slider by two pixels and starts hidden."""
        slider_manager = editor.slider_manager
        for color_name in ('alpha', 'red', 'green', 'blue'):
            slider = getattr(editor, f'{color_name}_slider')
            bounding_box = getattr(slider_manager, f'{color_name}_slider_bbox')
            assert bounding_box.visible is False
            assert bounding_box.rect == slider.rect.inflate(4, 4)

    def test_color_well_width_falls_back_to_screen_width_without_canvas(self, screen):
        """Without a canvas the color well reaches to 20 pixels from the screen edge."""
        editor_stand_in = _EditorStandIn(screen=screen)
        editor_stand_in.canvas = None  # type: ignore[assignment]
        slider_manager = SliderManager(editor_stand_in)  # type: ignore[arg-type]

        slider_manager.setup_sliders_and_color_well()

        assert editor_stand_in.color_well.rect.right == SCREEN_WIDTH - 20
        assert editor_stand_in.canvas is None


class TestHoverEffects:
    """Test bounding box and text box hover borders."""

    def test_hover_before_the_sliders_are_set_up_does_nothing(self, screen):
        """Hover effects before setup skip the missing bounding boxes (BUGS.md #100)."""
        slider_manager = SliderManager(_EditorStandIn(screen=screen))  # type: ignore[arg-type]

        slider_manager.update_slider_hover_effects(_outside_everything())

        assert slider_manager.red_slider_bbox is None
        assert slider_manager.green_slider_bbox is None
        assert slider_manager.blue_slider_bbox is None

    def test_hovering_alpha_slider_draws_gradient_border(self, editor):
        """Hovering the alpha slider shows a left-transparent, right-magenta border."""
        slider_manager = editor.slider_manager
        bounding_box = slider_manager.alpha_slider_bbox

        slider_manager.update_slider_hover_effects(_center_of(editor.alpha_slider.rect))

        assert bounding_box.visible is True
        assert bounding_box.dirty == 1
        width, height = bounding_box.rect.size
        assert tuple(bounding_box.image.get_at((0, 0))) == TRANSPARENT
        assert tuple(bounding_box.image.get_at((width - 1, height // 2))) == (255, 0, 255, 255)
        # The top border fades in from left to right
        left_alpha = bounding_box.image.get_at((1, 0)).a
        right_alpha = bounding_box.image.get_at((width - 2, 0)).a
        assert left_alpha < right_alpha

    def test_leaving_alpha_slider_hides_its_border(self, editor):
        """Moving off the alpha slider clears and hides its border."""
        slider_manager = editor.slider_manager
        bounding_box = slider_manager.alpha_slider_bbox
        slider_manager.update_slider_hover_effects(_center_of(editor.alpha_slider.rect))

        slider_manager.update_slider_hover_effects(_outside_everything())

        assert bounding_box.visible is False
        width, height = bounding_box.rect.size
        assert tuple(bounding_box.image.get_at((width - 1, height // 2))) == TRANSPARENT

    @pytest.mark.parametrize(
        ('color_name', 'border_color'),
        [
            ('red', (255, 0, 0, 255)),
            ('green', (0, 255, 0, 255)),
            ('blue', (0, 0, 255, 255)),
        ],
    )
    def test_hovering_color_slider_draws_border_in_its_color(
        self, editor, color_name, border_color
    ):
        """Hovering a color slider shows a border of that color; leaving hides it."""
        slider_manager = editor.slider_manager
        slider = getattr(editor, f'{color_name}_slider')
        bounding_box = getattr(slider_manager, f'{color_name}_slider_bbox')

        slider_manager.update_slider_hover_effects(_center_of(slider.rect))

        assert bounding_box.visible is True
        assert tuple(bounding_box.image.get_at((0, 0))) == border_color
        assert slider_manager.alpha_slider_bbox.visible is False

        slider_manager.update_slider_hover_effects(_outside_everything())

        assert bounding_box.visible is False
        assert tuple(bounding_box.image.get_at((0, 0))) == TRANSPARENT

    def test_hovering_text_box_adds_white_border_once_then_removes_it(self, editor):
        """A hovered text box gets a white border, kept while hovered, removed on leave."""
        slider_manager = editor.slider_manager
        text_sprite = editor.green_slider.text_sprite
        text_center = _center_of(text_sprite.rect)

        slider_manager.update_slider_hover_effects(text_center)

        assert text_sprite.hover_border_added is True
        assert tuple(text_sprite.image.get_at((0, 0)))[:3] == (255, 255, 255)

        # Hovering again keeps the border without redrawing it
        text_sprite.dirty = 0
        slider_manager.update_slider_hover_effects(text_center)
        assert text_sprite.dirty == 0

        slider_manager.update_slider_hover_effects(_outside_everything())

        assert text_sprite.hover_border_added is False
        assert tuple(text_sprite.image.get_at((0, 0)))[:3] != (255, 255, 255)

    def test_text_hover_skips_sliders_the_editor_lacks(self, editor):
        """A slider missing from the editor is never hovered and does not fail."""
        del editor.blue_slider

        editor.slider_manager.update_slider_hover_effects(_outside_everything())

        assert editor.slider_manager._is_slider_text_hovered('blue_slider', (0, 0)) is False


class TestSliderEvents:
    """Test slider events updating the sliders, color well and canvas."""

    @pytest.mark.parametrize(
        ('trigger_name', 'slider_attribute'),
        [
            ('R', 'red_slider'),
            ('G', 'green_slider'),
            ('B', 'blue_slider'),
            ('A', 'alpha_slider'),
        ],
    )
    def test_slider_event_sets_named_slider_and_colors(
        self, editor, trigger_name, slider_attribute
    ):
        """The named slider takes the value and both colors follow."""
        trigger = events.HashableEvent(0, name=trigger_name, value=100)

        editor.slider_manager.on_slider_event(event=events.HashableEvent(0), trigger=trigger)

        assert getattr(editor, slider_attribute).value == 100
        expected_color = (
            editor.red_slider.value,
            editor.green_slider.value,
            editor.blue_slider.value,
            editor.alpha_slider.value,
        )
        assert editor.color_well.active_color == expected_color
        assert editor.canvas.active_color == expected_color

    @pytest.mark.parametrize(
        ('requested_value', 'clamped_value'),
        [(-5, 0), (300, 255)],
    )
    def test_slider_event_clamps_out_of_range_values(self, editor, requested_value, clamped_value):
        """Values outside 0-255 are clamped on the trigger and the slider."""
        trigger = events.HashableEvent(0, name='R', value=requested_value)

        editor.slider_manager.on_slider_event(event=events.HashableEvent(0), trigger=trigger)

        assert trigger.value == clamped_value
        assert editor.red_slider.value == clamped_value

    def test_slider_event_shows_hex_text_in_hex_format(self, editor):
        """With the hex tab selected, slider text is shown as two hex digits."""
        editor.slider_manager.on_tab_change_event('%X')
        trigger = events.HashableEvent(0, name='G', value=171)

        editor.slider_manager.on_slider_event(event=events.HashableEvent(0), trigger=trigger)

        assert editor.slider_input_format == '%X'
        assert editor.green_slider.text_sprite.text == 'AB'
        assert editor.red_slider.text_sprite.text == '00'
        assert editor.blue_slider.text_sprite.text == '00'

    def test_tab_change_back_to_decimal_shows_decimal_text(self, editor):
        """Switching back to decimal shows the values as decimal numbers."""
        editor.slider_manager.on_slider_event(
            event=events.HashableEvent(0),
            trigger=events.HashableEvent(0, name='B', value=200),
        )
        editor.slider_manager.on_tab_change_event('%X')

        editor.slider_manager.on_tab_change_event('%d')

        assert editor.blue_slider.text_sprite.text == '200'

    def test_tab_change_refreshes_the_alpha_text_too(self, editor):
        """The hex tab shows alpha in hex like R, G and B (BUGS.md #110 item 4)."""
        editor.slider_manager.on_slider_event(
            event=events.HashableEvent(0),
            trigger=events.HashableEvent(0, name='A', value=171),
        )

        editor.slider_manager.on_tab_change_event('%X')

        assert editor.alpha_slider.text_sprite.text == 'AB'

        editor.slider_manager.on_tab_change_event('%d')

        assert editor.alpha_slider.text_sprite.text == '171'

    def test_event_from_an_unknown_slider_changes_no_slider(self, editor):
        """A trigger named after no color slider changes none, and the colors stay in step."""
        trigger = events.HashableEvent(0, name='Hue', value=100)

        editor.slider_manager.on_slider_event(event=events.HashableEvent(0), trigger=trigger)

        assert (
            editor.red_slider.value,
            editor.green_slider.value,
            editor.blue_slider.value,
            editor.alpha_slider.value,
        ) == (0, 0, 0, 255)
        assert editor.color_well.active_color == (0, 0, 0, 255)
        assert editor.canvas.active_color == (0, 0, 0, 255)

    def test_tab_change_before_setup_changes_nothing(self, screen):
        """With no sliders yet, a tab change only records the format."""
        editor_stand_in = _EditorStandIn(screen=screen)
        slider_manager = SliderManager(editor_stand_in)  # type: ignore[arg-type]

        slider_manager.on_tab_change_event('%X')

        assert editor_stand_in.slider_input_format == '%X'
        assert slider_manager.channel_sliders() == ()

    def test_tab_change_uses_the_current_format_when_none_is_given(self, editor):
        """Without a format, the slider text follows the editor's current format."""
        editor.green_slider.value = 171
        editor.slider_input_format = '%X'

        editor.slider_manager._update_slider_text_format()

        assert editor.green_slider.text_sprite.text == 'AB'


class TestCommitSliderTextBoxes:
    """Test committing typed text when a slider's text box loses focus (a click elsewhere)."""

    CLICK = events.HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(1, 1), button=1)

    @staticmethod
    def _activate_with_text(slider, text):
        """Put the slider's text box in editing mode holding the given text."""
        slider.original_value = slider.value
        slider.text_sprite.is_active = True
        slider.text_sprite.text = text

    def test_decimal_text_commits_value_and_color(self, editor):
        """Decimal text sets the slider value, the colors follow, and the box deactivates."""
        slider = editor.red_slider
        self._activate_with_text(slider, '120')

        editor.slider_manager.commit_slider_text_boxes(event=self.CLICK, clicked_slider=None)

        assert slider.value == 120
        assert slider.original_value == 120
        assert slider.text_sprite.text == '120'
        assert slider.text_sprite.is_active is False
        assert editor.color_well.active_color == (120, 0, 0, 255)
        assert editor.canvas.active_color == (120, 0, 0, 255)

    def test_hex_text_commits_value_shown_in_hex_format(self, editor):
        """Text with hex letters is parsed as hex and shown in hex in hex format."""
        editor.slider_input_format = '%X'
        slider = editor.green_slider
        self._activate_with_text(slider, 'ff')

        editor.slider_manager.commit_slider_text_boxes(
            event=self.CLICK, clicked_slider=editor.red_slider
        )

        assert slider.value == 255
        assert slider.text_sprite.text == 'FF'
        assert slider.text_sprite.is_active is False

    def test_digits_typed_on_the_hex_tab_are_hex(self, editor):
        """On the hex tab "10" is 16, not 10 (BUGS.md #110 item 3)."""
        editor.slider_input_format = '%X'
        slider = editor.green_slider
        self._activate_with_text(slider, '10')

        editor.slider_manager.commit_slider_text_boxes(event=self.CLICK, clicked_slider=None)

        assert slider.value == 16
        assert slider.text_sprite.text == '10'

    def test_digits_typed_on_the_decimal_tab_are_decimal(self, editor):
        """On the decimal tab "10" is 10."""
        slider = editor.green_slider
        self._activate_with_text(slider, '10')

        editor.slider_manager.commit_slider_text_boxes(event=self.CLICK, clicked_slider=None)

        assert slider.value == 10
        assert slider.text_sprite.text == '10'

    def test_alpha_text_is_committed_too(self, editor):
        """The alpha text box is committed like the color channels."""
        slider = editor.alpha_slider
        self._activate_with_text(slider, '64')

        editor.slider_manager.commit_slider_text_boxes(event=self.CLICK, clicked_slider=None)

        assert slider.value == 64
        assert slider.text_sprite.is_active is False
        assert editor.color_well.active_color == (0, 0, 0, 64)

    @pytest.mark.parametrize('typed_text', ['', '   ', '999', 'zz'])
    def test_empty_out_of_range_or_invalid_text_restores_original(self, editor, typed_text):
        """Empty, out-of-range or unparsable text restores the original value."""
        slider = editor.blue_slider
        slider.value = 42
        self._activate_with_text(slider, typed_text)

        editor.slider_manager.commit_slider_text_boxes(event=self.CLICK, clicked_slider=None)

        assert slider.value == 42
        assert slider.text_sprite.text == '42'
        assert slider.text_sprite.is_active is False

    @pytest.mark.parametrize('typed_text', ['', '999', 'zz'])
    def test_restoring_on_the_hex_tab_writes_hex(self, editor, typed_text):
        """On the hex tab a restored original value is written in hex ('2A', not '42')."""
        editor.slider_input_format = '%X'
        slider = editor.blue_slider
        slider.value = 42
        self._activate_with_text(slider, typed_text)

        editor.slider_manager.commit_slider_text_boxes(event=self.CLICK, clicked_slider=None)

        assert slider.value == 42
        assert slider.text_sprite.text == '2A'
        assert slider.text_sprite.is_active is False

    def test_clicking_the_same_slider_keeps_editing(self, editor):
        """Clicking the slider being edited leaves its text box active and untouched."""
        slider = editor.red_slider
        self._activate_with_text(slider, '7')

        editor.slider_manager.commit_slider_text_boxes(event=self.CLICK, clicked_slider=slider)

        assert slider.text_sprite.is_active is True
        assert slider.text_sprite.text == '7'
        assert slider.value == 0


class TestInteraction:
    """Test click detection and keyboard routing to slider text boxes."""

    def test_detect_clicked_slider_finds_text_box_under_mouse(self, editor):
        """A click on a color slider's text box names that slider."""
        slider_manager = editor.slider_manager

        blue_text_center = _center_of(editor.blue_slider.text_sprite.rect)

        alpha_text_center = _center_of(editor.alpha_slider.text_sprite.rect)

        assert slider_manager.detect_clicked_slider(blue_text_center) is editor.blue_slider
        assert slider_manager.detect_clicked_slider(alpha_text_center) is editor.alpha_slider
        assert slider_manager.detect_clicked_slider(_outside_everything()) is None

    def test_text_input_returns_false_when_no_text_box_active(self, editor):
        """No active text box means the key is not consumed."""
        key_event = events.HashableEvent(pygame.KEYDOWN, key=pygame.K_1, unicode='1')

        assert editor.slider_manager.handle_slider_text_input(key_event) is False

    def test_text_input_goes_to_active_text_box(self, editor):
        """A digit typed into the active text box is appended to its text."""
        slider = editor.alpha_slider
        slider.text_sprite.is_active = True
        slider.text_sprite.text = ''
        key_event = events.HashableEvent(pygame.KEYDOWN, key=pygame.K_7, unicode='7', mod=0)

        result = editor.slider_manager.handle_slider_text_input(key_event)

        assert result is None
        assert slider.text_sprite.text == '7'

    def test_escape_in_active_text_box_is_consumed_and_restores(self, editor):
        """Escape restores the original value and is consumed so the game keeps running."""
        slider = editor.red_slider
        slider.value = 33
        slider.original_value = 33
        slider.text_sprite.is_active = True
        slider.text_sprite.text = '1'
        key_event = events.HashableEvent(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode='', mod=0)

        result = editor.slider_manager.handle_slider_text_input(key_event)

        assert result is True
        assert slider.text_sprite.is_active is False
        assert slider.text_sprite.text == '33'


class TestColorApi:
    """Test reading the current color and setting it with apply_color."""

    def test_get_current_color_reads_sliders(self, editor):
        """The current color is the RGBA slider values, alpha included."""
        editor.slider_manager.apply_color(red=10, green=20, blue=30, alpha=40)

        assert editor.slider_manager.get_current_color() == (10, 20, 30, 40)

    def test_get_current_color_defaults_to_white_without_sliders(self, screen):
        """With no sliders the current color is opaque white."""
        slider_manager = SliderManager(_EditorStandIn(screen=screen))  # type: ignore[arg-type]

        assert slider_manager.get_current_color() == (255, 255, 255, 255)

    def test_get_current_color_defaults_to_white_on_bad_slider_value(self, editor):
        """A slider value that is not a number falls back to opaque white."""
        editor.red_slider = SimpleNamespace(value='not a number')

        assert editor.slider_manager.get_current_color() == (255, 255, 255, 255)

    def test_apply_color_sets_sliders_text_color_well_and_canvas(self, editor):
        """apply_color sets the four sliders, their text, the color well and the canvas."""
        editor.slider_input_format = '%X'

        editor.slider_manager.apply_color(red=1, green=2, blue=171, alpha=4)

        assert [slider.value for slider in editor.slider_manager.channel_sliders()] == [
            1,
            2,
            171,
            4,
        ]
        assert editor.blue_slider.text_sprite.text == 'AB'
        assert editor.color_well.active_color == (1, 2, 171, 4)
        assert editor.color_well.dirty == 1
        assert editor.canvas.active_color == (1, 2, 171, 4)

    def test_apply_color_clamps_through_the_sliders(self, editor):
        """Out-of-range channels are clamped by the sliders before the colors are set."""
        editor.slider_manager.apply_color(red=-3, green=300, blue=0, alpha=255)

        assert editor.color_well.active_color == (0, 255, 0, 255)
        assert editor.canvas.active_color == (0, 255, 0, 255)

    def test_apply_color_without_a_canvas_sets_the_color_well(self, editor):
        """An editor without a canvas still gets its sliders and color well set."""
        editor.canvas = None

        editor.slider_manager.apply_color(red=5, green=6, blue=7, alpha=8)

        assert editor.color_well.active_color == (5, 6, 7, 8)
        assert editor.canvas is None


class TestSampleColorFromScreen:
    """Test sampling a screen pixel into the sliders."""

    def test_sampled_pixel_sets_sliders_with_opaque_alpha(self, editor, screen):
        """The pixel's RGB goes to the sliders and alpha is forced to 255."""
        screen.fill((12, 34, 56))
        editor.alpha_slider.value = 7

        editor.slider_manager.sample_color_from_screen((5, 5))

        assert editor.red_slider.value == 12
        assert editor.green_slider.value == 34
        assert editor.blue_slider.value == 56
        assert editor.alpha_slider.value == 255
        assert editor.canvas.active_color == (12, 34, 56, 255)

    def test_sampling_rgb_color_without_alpha_component(self, editor):
        """A screen that answers with a 3-component color is sampled too."""
        editor.screen = SimpleNamespace(get_at=lambda position: (9, 8, 7))

        editor.slider_manager.sample_color_from_screen((0, 0))

        assert editor.color_well.active_color == (9, 8, 7, 255)

    def test_sampling_without_screen_leaves_sliders_unchanged(self, editor, caplog):
        """With no screen the error is logged and the sliders keep their values."""
        editor.screen = None

        editor.slider_manager.sample_color_from_screen((0, 0))

        assert editor.color_well.active_color == (0, 0, 0, 255)
        assert 'Error sampling color from screen' in caplog.text


class TestControllerSliderMode:
    """Test detecting controllers in a slider mode."""

    @staticmethod
    def _mode_switcher(modes):
        """Build a mode switcher stand-in answering the given controller modes.

        Returns:
            SimpleNamespace: The mode switcher.

        """
        return SimpleNamespace(
            controller_modes=dict(modes),
            get_controller_mode=lambda controller_id: modes[controller_id],
        )

    def test_no_mode_switcher_means_no_slider_mode(self, editor):
        """An editor without a mode switcher has no controller in slider mode."""
        assert editor.slider_manager.is_any_controller_in_slider_mode() is False

    def test_controller_in_slider_mode_is_detected(self, editor):
        """A controller in the green slider mode is detected."""
        editor.mode_switcher = self._mode_switcher(
            {0: SimpleNamespace(value='canvas'), 1: None, 2: SimpleNamespace(value='g_slider')},
        )

        assert editor.slider_manager.is_any_controller_in_slider_mode() is True

    def test_controllers_outside_slider_modes_are_not_detected(self, editor):
        """Controllers in other modes, or with no mode, are not in slider mode."""
        editor.mode_switcher = self._mode_switcher(
            {0: SimpleNamespace(value='film_strip'), 1: None},
        )

        assert editor.slider_manager.is_any_controller_in_slider_mode() is False


@pytest.fixture
def real_editor(screen, mocker):
    """Build a real Bitmappy editor on the real display, with a fresh controller manager.

    Returns:
        BitmapEditorScene: The editor.

    """
    from glitchygames.bitmappy.controllers.manager import MultiControllerManager
    from glitchygames.bitmappy.editor import BitmapEditorScene

    mocker.patch.object(MultiControllerManager, '_instance', None)
    return BitmapEditorScene(options={})


def _click(editor, position: tuple[int, int]) -> None:
    """Press the left mouse button on the editor at a screen position."""
    editor.on_left_mouse_button_down_event(
        events.HashableEvent(pygame.MOUSEBUTTONDOWN, pos=position, button=1),
    )


def _type_into_text_box(editor, slider, text: str) -> None:
    """Click a slider's text box, then type the text into it through the editor's keys."""
    _click(editor, _center_of(slider.text_sprite.rect))
    assert slider.text_sprite.is_active is True
    for character in text:
        editor.on_key_down_event(
            events.HashableEvent(
                pygame.KEYDOWN,
                key=pygame.key.key_code(character),
                unicode=character,
                mod=0,
                scancode=0,
            ),
        )


class TestClickAwayCommitInTheRealEditor:
    """Typed slider text committed by clicking elsewhere, in the real editor."""

    def test_click_away_commit_changes_the_color_too(self, real_editor):
        """Clicking away from typed red text sets the color well and canvas color, as Enter does.

        The click-away commit used to set only the slider value, so the color well and the
        canvas kept painting the old color.
        """
        _type_into_text_box(real_editor, real_editor.red_slider, '200')

        _click(real_editor, _center_of(real_editor.green_slider.text_sprite.rect))

        assert real_editor.red_slider.value == 200
        assert real_editor.red_slider.text_sprite.is_active is False
        assert real_editor.color_well.active_color == (200, 0, 0, 255)
        assert real_editor.canvas.active_color == (200, 0, 0, 255)

    def test_click_away_commits_the_alpha_text_box(self, real_editor):
        """Clicking away from typed alpha text commits it and stops the box taking keys.

        The click-away loop covered only R, G and B, so the alpha box stayed active.
        """
        _type_into_text_box(real_editor, real_editor.alpha_slider, '128')

        _click(real_editor, _center_of(real_editor.red_slider.text_sprite.rect))

        assert real_editor.alpha_slider.text_sprite.is_active is False
        assert real_editor.alpha_slider.value == 128
        assert real_editor.color_well.active_color == (0, 0, 0, 128)
        assert real_editor.canvas.active_color == (0, 0, 0, 128)
        assert real_editor.red_slider.text_sprite.is_active is True


class TestSliderModeIndicatorsInTheRealEditor:
    """A controller in a slider mode is shown once, centred on its own slider."""

    CONTROLLER_ID = 0
    CONTROLLER_YELLOW = (255, 255, 0)

    def _put_controller_in_red_slider_mode(self, editor) -> None:
        """Connect a yellow controller and switch it to the red slider mode, as L2/R2 do."""
        from glitchygames.bitmappy.controllers.manager import ControllerInfo, ControllerStatus
        from glitchygames.bitmappy.controllers.modes import ControllerMode
        from glitchygames.clock import elapsed_seconds

        manager = editor.multi_controller_manager
        manager.controllers[self.CONTROLLER_ID] = ControllerInfo(
            controller_id=self.CONTROLLER_ID,
            instance_id=self.CONTROLLER_ID,
            status=ControllerStatus.ACTIVE,
            color=self.CONTROLLER_YELLOW,
        )
        # Just scanned: no joystick is plugged in, so a scan now would disconnect it
        manager.last_scan_time = elapsed_seconds()
        editor.controller_handler.render_visual_indicators()
        editor.mode_switcher.controller_modes[self.CONTROLLER_ID].switch_to_mode(
            ControllerMode.R_SLIDER,
            elapsed_seconds(),
        )
        editor.controller_handler.update_controller_visual_indicator_for_mode(
            self.CONTROLLER_ID,
            ControllerMode.R_SLIDER,
        )
        editor.controller_handler.render_visual_indicators()

    def test_only_the_controllers_slider_shows_its_indicator(self, real_editor, screen):
        """The indicator is drawn centred on the red slider, and on no other slider.

        The slider widget used to draw every slider-mode indicator again at the top-left of
        all four sliders.
        """
        self._put_controller_in_red_slider_mode(real_editor)
        screen.fill((0, 0, 0))

        real_editor.all_sprites.update()
        real_editor.all_sprites.draw(screen)

        red_center = _center_of(real_editor.red_slider.rect)
        assert tuple(screen.get_at(red_center))[:3] == self.CONTROLLER_YELLOW
        for slider in (
            real_editor.alpha_slider,
            real_editor.red_slider,
            real_editor.green_slider,
            real_editor.blue_slider,
        ):
            top_left_inside = (slider.rect.x + 1, slider.rect.y + 1)
            assert tuple(screen.get_at(top_left_inside))[:3] != self.CONTROLLER_YELLOW
