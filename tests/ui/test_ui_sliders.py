"""Test suite for slider and color well UI components.

This module tests SliderSprite and ColorWellSprite functionality including
slider dragging, text input, value validation, and color well display.
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events.base import HashableEvent
from glitchygames.ui import ColorWellSprite, SliderSprite

# Test constants to avoid magic values
TEST_X_POS = 10
TEST_Y_POS = 20
TEST_WIDTH = 200
TEST_HEIGHT = 20
TEST_MIN_VALUE = 0
TEST_MAX_VALUE = 255
TEST_DEFAULT_VALUE = 128
TEST_COLOR_WELL_X = 250
TEST_COLOR_WELL_Y = 20
TEST_COLOR_WELL_WIDTH = 100
TEST_COLOR_WELL_HEIGHT = 60

# Additional constants for magic values
TEST_VALUE_180 = 180
TEST_VALUE_150 = 150
TEST_VALUE_100 = 100
TEST_VALUE_75 = 75
TEST_VALUE_64 = 64
TEST_VALUE_200 = 200
TEST_VALUE_NEGATIVE_10 = -10
TEST_VALUE_300 = 300
KNOB_COLOR = (200, 200, 200)
COLOR_WELL_BORDER_COLOR = (128, 128, 255)


def _mouse_event(position):
    """Build a real mouse event at a position.

    Returns:
        HashableEvent: The event.
    """
    return HashableEvent(pygame.MOUSEBUTTONDOWN, pos=position, button=1)


def _key_down(key, *, unicode=''):
    """Build a real key down event.

    Returns:
        HashableEvent: The event.
    """
    return HashableEvent(pygame.KEYDOWN, key=key, mod=pygame.KMOD_NONE, unicode=unicode)


def _rgb_at(surface, position):
    """Return the RGB colour of one pixel (the alpha is not the point here).

    Returns:
        tuple: The (red, green, blue) colour.
    """
    return tuple(surface.get_at(position))[:3]


class _ColorWellParent:
    """A minimal slider parent: it copies each slider's value into a colour well channel."""

    slider_input_format = '%d'

    def __init__(self, *, color_well):
        self.color_well = color_well

    def on_slider_event(self, event, trigger):
        channel = {'R': 'red', 'G': 'green', 'B': 'blue'}[trigger.name]
        setattr(self.color_well, channel, trigger.value)


class TestSliderSpriteFunctionality:
    """Test SliderSprite functionality."""

    def test_slider_initialization(self):
        """Test SliderSprite initialization."""
        # Arrange

        # Act
        slider = SliderSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestSlider',
        )

        # Assert
        assert slider.rect is not None
        assert slider.rect.x == TEST_X_POS
        assert slider.rect.y == TEST_Y_POS
        assert slider.rect.width == TEST_WIDTH
        assert slider.rect.height == TEST_HEIGHT
        assert slider.name == 'TestSlider'
        assert hasattr(slider, 'text_sprite')
        assert slider.text_sprite is not None
        assert hasattr(slider, 'slider_knob')
        assert slider.slider_knob is not None

    def test_slider_value_setting(self):
        """Test SliderSprite value setting."""
        # Arrange

        slider = SliderSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestSlider',
        )

        # Act
        slider.value = 200

        # Assert
        assert slider.value == TEST_VALUE_200
        assert slider.text_sprite.text == '200'

    def test_slider_value_clamping(self):
        """Test SliderSprite value clamping to min/max bounds."""
        # Arrange

        slider = SliderSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestSlider',
        )

        # Act - set value below minimum
        slider.value = -10

        # Assert - should be clamped to minimum
        assert slider.value == TEST_MIN_VALUE

        # Act - set value above maximum
        slider.value = 300

        # Assert - should be clamped to maximum
        assert slider.value == TEST_MAX_VALUE

    def test_slider_mouse_click_handling(self):
        """Test SliderSprite mouse click handling."""
        # Arrange

        slider = SliderSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestSlider',
        )

        event = _mouse_event((TEST_X_POS + 100, TEST_Y_POS + 10))  # Click in middle of slider

        # Act
        slider.on_left_mouse_button_down_event(event)

        # Assert - the value follows the click, and the knob moves to it
        assert slider.dragging is True
        expected_value = 100 * TEST_MAX_VALUE // (slider.max_x - slider.min_x)
        assert slider.value == expected_value
        assert slider.slider_knob.rect.x == slider.min_x + (
            expected_value * (slider.max_x - slider.min_x) // TEST_MAX_VALUE
        )
        assert slider.text_sprite.text == str(expected_value)

    def test_slider_mouse_click_outside_the_slider_is_ignored(self):
        """A click outside the slider neither starts a drag nor changes the value."""
        slider = SliderSprite(x=TEST_X_POS, y=TEST_Y_POS, width=TEST_WIDTH, height=TEST_HEIGHT)

        slider.on_left_mouse_button_down_event(_mouse_event((0, 0)))

        assert slider.dragging is False
        assert slider.value == 0

    def test_slider_mouse_drag_handling(self):
        """Test SliderSprite mouse drag handling."""
        # Arrange

        slider = SliderSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestSlider',
        )

        # Start dragging
        slider.dragging = True

        event = _mouse_event((TEST_X_POS + 150, TEST_Y_POS + 10))  # Drag to 75% position

        # Act
        slider.on_mouse_motion_event(event)

        # Assert - the knob's 150 px of its 195 px travel is about 75% of the maximum
        assert slider.value == 150 * TEST_MAX_VALUE // (slider.max_x - slider.min_x)
        assert TEST_VALUE_180 <= slider.value <= TEST_VALUE_200

    def test_slider_mouse_motion_without_a_drag_changes_nothing(self):
        """Moving the mouse over the slider without dragging keeps the value."""
        slider = SliderSprite(x=TEST_X_POS, y=TEST_Y_POS, width=TEST_WIDTH, height=TEST_HEIGHT)

        slider.on_mouse_motion_event(_mouse_event((TEST_X_POS + 150, TEST_Y_POS + 10)))

        assert slider.value == 0

    def test_slider_mouse_release_handling(self):
        """Test SliderSprite mouse release handling."""
        # Arrange

        slider = SliderSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestSlider',
        )

        # Start dragging
        slider.dragging = True

        event = _mouse_event((TEST_X_POS + 100, TEST_Y_POS + 10))

        # Act
        slider.on_left_mouse_button_up_event(event)

        # Assert
        assert slider.dragging is False

    def test_slider_text_input_activation(self):
        """Test SliderSprite text input activation."""
        # Arrange

        slider = SliderSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestSlider',
        )

        event = _mouse_event((TEST_X_POS + TEST_WIDTH + 10, TEST_Y_POS + 10))  # Click on text box

        # Act
        result = slider.text_sprite.on_left_mouse_button_down_event(event)

        # Assert
        assert result is True  # Should handle the event
        assert slider.text_sprite.is_active is True
        assert not slider.text_sprite.text  # Should be cleared for editing

    def test_slider_text_input_validation(self):
        """Test SliderSprite text input validation."""
        # Arrange

        slider = SliderSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestSlider',
        )

        # Activate text input
        slider.text_sprite.is_active = True
        slider.text_sprite.text = '150'

        # Enter key
        event = _key_down(pygame.K_RETURN, unicode='')

        # Act
        slider.text_sprite.on_key_down_event(event)

        # Assert
        assert slider.value == TEST_VALUE_150
        assert slider.text_sprite.is_active is False

    def test_slider_text_input_invalid_value(self):
        """Test SliderSprite text input with invalid value."""
        # Arrange

        slider = SliderSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestSlider',
        )

        original_value = slider.value

        # Activate text input
        slider.text_sprite.is_active = True
        slider.text_sprite.text = '300'  # Invalid - above max

        # Enter key
        event = _key_down(pygame.K_RETURN, unicode='')

        # Act
        slider.text_sprite.on_key_down_event(event)

        # Assert - should revert to original value
        assert slider.value == original_value
        assert slider.text_sprite.is_active is False

    def test_slider_text_input_escape_key(self):
        """Test SliderSprite text input escape key handling."""
        # Arrange

        slider = SliderSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestSlider',
        )

        original_value = slider.value

        # Activate text input
        slider.text_sprite.is_active = True
        slider.text_sprite.text = '200'

        # Escape key
        event = _key_down(pygame.K_ESCAPE, unicode='')

        # Act
        slider.text_sprite.on_key_down_event(event)

        # Assert - should revert to original value
        assert slider.value == original_value
        assert slider.text_sprite.is_active is False

    def test_slider_text_input_character_typing(self):
        """Test SliderSprite text input character typing."""
        # Arrange

        slider = SliderSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestSlider',
        )

        # Activate text input
        slider.text_sprite.is_active = True
        slider.text_sprite.text = ''

        # digit key
        event = _key_down(pygame.K_1, unicode='1')

        # Act
        slider.text_sprite.on_key_down_event(event)

        # Assert
        assert slider.text_sprite.text == '1'

    def test_slider_text_input_backspace(self):
        """Test SliderSprite text input backspace handling."""
        # Arrange

        slider = SliderSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='TestSlider',
        )

        # Activate text input
        slider.text_sprite.is_active = True
        slider.text_sprite.text = '12'

        # backspace key
        event = _key_down(pygame.K_BACKSPACE, unicode='')

        # Act
        slider.text_sprite.on_key_down_event(event)

        # Assert
        assert slider.text_sprite.text == '1'


class TestColorWellSpriteFunctionality:
    """Test ColorWellSprite functionality."""

    def test_color_well_initialization(self):
        """Test ColorWellSprite initialization."""
        # Act
        color_well = ColorWellSprite(
            x=TEST_COLOR_WELL_X,
            y=TEST_COLOR_WELL_Y,
            width=TEST_COLOR_WELL_WIDTH,
            height=TEST_COLOR_WELL_HEIGHT,
            name='TestColorWell',
        )

        # Assert
        assert color_well.rect is not None
        assert color_well.rect.x == TEST_COLOR_WELL_X
        assert color_well.rect.y == TEST_COLOR_WELL_Y
        assert color_well.rect.width == TEST_COLOR_WELL_WIDTH
        assert color_well.rect.height == TEST_COLOR_WELL_HEIGHT
        assert color_well.name == 'TestColorWell'

    def test_color_well_color_setting(self):
        """Test ColorWellSprite color setting."""
        # Arrange
        color_well = ColorWellSprite(
            x=TEST_COLOR_WELL_X,
            y=TEST_COLOR_WELL_Y,
            width=TEST_COLOR_WELL_WIDTH,
            height=TEST_COLOR_WELL_HEIGHT,
            name='TestColorWell',
        )

        # Act
        color_well.active_color = (255, 128, 64)

        # Assert
        assert color_well.red == TEST_MAX_VALUE
        assert color_well.green == TEST_DEFAULT_VALUE
        assert color_well.blue == TEST_VALUE_64

    def test_color_well_color_getting(self):
        """Test ColorWellSprite color getting."""
        # Arrange
        color_well = ColorWellSprite(
            x=TEST_COLOR_WELL_X,
            y=TEST_COLOR_WELL_Y,
            width=TEST_COLOR_WELL_WIDTH,
            height=TEST_COLOR_WELL_HEIGHT,
            name='TestColorWell',
        )
        color_well.active_color = (100, 150, 200)

        # Act - active_color returns RGBA 4-tuple
        red, green, blue, alpha = color_well.active_color

        # Assert
        assert red == TEST_VALUE_100
        assert green == TEST_VALUE_150
        assert blue == TEST_VALUE_200
        assert alpha == TEST_MAX_VALUE

    def test_color_well_color_clamping(self):
        """Test ColorWellSprite color value clamping."""
        # Arrange
        color_well = ColorWellSprite(
            x=TEST_COLOR_WELL_X,
            y=TEST_COLOR_WELL_Y,
            width=TEST_COLOR_WELL_WIDTH,
            height=TEST_COLOR_WELL_HEIGHT,
            name='TestColorWell',
        )

        # Act - set values outside valid range
        color_well.active_color = (-10, 300, 128)

        # Assert - ColorWellSprite doesn't clamp values, so they remain as set
        assert color_well.red == TEST_VALUE_NEGATIVE_10
        assert color_well.green == TEST_VALUE_300
        assert color_well.blue == TEST_DEFAULT_VALUE

    def test_color_well_red_property(self):
        """Test ColorWellSprite red property."""
        # Arrange
        color_well = ColorWellSprite(
            x=TEST_COLOR_WELL_X,
            y=TEST_COLOR_WELL_Y,
            width=TEST_COLOR_WELL_WIDTH,
            height=TEST_COLOR_WELL_HEIGHT,
            name='TestColorWell',
        )

        # Act
        color_well.red = 200

        # Assert
        assert color_well.red == TEST_VALUE_200

    def test_color_well_green_property(self):
        """Test ColorWellSprite green property."""
        # Arrange
        color_well = ColorWellSprite(
            x=TEST_COLOR_WELL_X,
            y=TEST_COLOR_WELL_Y,
            width=TEST_COLOR_WELL_WIDTH,
            height=TEST_COLOR_WELL_HEIGHT,
            name='TestColorWell',
        )

        # Act
        color_well.green = 150

        # Assert
        assert color_well.green == TEST_VALUE_150

    def test_color_well_blue_property(self):
        """Test ColorWellSprite blue property."""
        # Arrange
        color_well = ColorWellSprite(
            x=TEST_COLOR_WELL_X,
            y=TEST_COLOR_WELL_Y,
            width=TEST_COLOR_WELL_WIDTH,
            height=TEST_COLOR_WELL_HEIGHT,
            name='TestColorWell',
        )

        # Act
        color_well.blue = 75

        # Assert
        assert color_well.blue == TEST_VALUE_75

    def test_color_well_update_display(self):
        """Test ColorWellSprite display update."""
        # Arrange
        color_well = ColorWellSprite(
            x=TEST_COLOR_WELL_X,
            y=TEST_COLOR_WELL_Y,
            width=TEST_COLOR_WELL_WIDTH,
            height=TEST_COLOR_WELL_HEIGHT,
            name='TestColorWell',
        )
        color_well.active_color = (255, 0, 0)  # Red color

        # Act
        color_well.update()

        # Assert - a 1 px border around the colour
        assert color_well.red == TEST_MAX_VALUE
        assert color_well.green == 0
        assert color_well.blue == 0
        assert _rgb_at(color_well.image, (0, 0)) == COLOR_WELL_BORDER_COLOR
        assert (
            _rgb_at(color_well.image, (TEST_COLOR_WELL_WIDTH - 1, TEST_COLOR_WELL_HEIGHT - 1))
            == COLOR_WELL_BORDER_COLOR
        )
        assert _rgb_at(color_well.image, (1, 1)) == (255, 0, 0)
        assert _rgb_at(
            color_well.image, (TEST_COLOR_WELL_WIDTH // 2, TEST_COLOR_WELL_HEIGHT // 2)
        ) == (255, 0, 0)

    def test_color_well_draws_its_alpha(self):
        """The colour well's image carries the colour's alpha (its surface has per-pixel alpha)."""
        color_well = ColorWellSprite(
            x=TEST_COLOR_WELL_X,
            y=TEST_COLOR_WELL_Y,
            width=TEST_COLOR_WELL_WIDTH,
            height=TEST_COLOR_WELL_HEIGHT,
            name='TestColorWell',
        )
        color_well.active_color = (10, 20, 30, 128)

        color_well.update()

        assert tuple(color_well.image.get_at((5, 5))) == (10, 20, 30, 128)

    def test_color_well_initial_color(self):
        """Test ColorWellSprite initial color values."""
        # Act
        color_well = ColorWellSprite(
            x=TEST_COLOR_WELL_X,
            y=TEST_COLOR_WELL_Y,
            width=TEST_COLOR_WELL_WIDTH,
            height=TEST_COLOR_WELL_HEIGHT,
            name='TestColorWell',
        )

        # Assert - opaque black by default
        assert color_well.active_color == (0, 0, 0, TEST_MAX_VALUE)


class TestSliderColorWellIntegration:
    """Test integration between SliderSprite and ColorWellSprite."""

    def test_slider_color_well_synchronization(self):
        """A slider tells its parent its new value, so the parent's colour well follows it."""
        color_well = ColorWellSprite(
            x=TEST_COLOR_WELL_X,
            y=TEST_COLOR_WELL_Y,
            width=TEST_COLOR_WELL_WIDTH,
            height=TEST_COLOR_WELL_HEIGHT,
            name='TestColorWell',
        )
        parent = _ColorWellParent(color_well=color_well)
        slider = SliderSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='R',
            parent=parent,  # ty: ignore[invalid-argument-type]
        )

        # Act - type a value and press Enter
        slider.text_sprite.is_active = True
        slider.text_sprite.text = '200'
        slider.text_sprite.on_key_down_event(_key_down(pygame.K_RETURN, unicode='\r'))

        # Assert - the colour well shows the slider's value
        assert slider.value == TEST_VALUE_200
        assert color_well.red == TEST_VALUE_200
        color_well.update()
        assert _rgb_at(
            color_well.image, (TEST_COLOR_WELL_WIDTH // 2, TEST_COLOR_WELL_HEIGHT // 2)
        ) == (
            TEST_VALUE_200,
            0,
            0,
        )

    def test_multiple_sliders_color_well_integration(self):
        """Test integration of multiple sliders with color well."""
        # Arrange

        # Create RGB sliders
        red_slider = SliderSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='RedSlider',
        )
        red_slider.value = 255

        green_slider = SliderSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS + 30,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='GreenSlider',
        )
        green_slider.value = 128

        blue_slider = SliderSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS + 60,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name='BlueSlider',
        )
        blue_slider.value = 64

        color_well = ColorWellSprite(
            x=TEST_COLOR_WELL_X,
            y=TEST_COLOR_WELL_Y,
            width=TEST_COLOR_WELL_WIDTH,
            height=TEST_COLOR_WELL_HEIGHT,
            name='TestColorWell',
        )

        # Act - set color well based on slider values
        color_well.active_color = (red_slider.value, green_slider.value, blue_slider.value)

        # Assert
        assert color_well.red == TEST_MAX_VALUE
        assert color_well.green == TEST_DEFAULT_VALUE
        assert color_well.blue == TEST_VALUE_64


class TestSliderSpriteWithRealSurfaces:
    """SliderSprite built on real pygame surfaces (no pygame mocks)."""

    @pytest.fixture
    def slider(self):
        """A real slider.

        Returns:
            The slider.

        """
        return SliderSprite(x=TEST_X_POS, y=TEST_Y_POS, width=TEST_WIDTH, height=TEST_HEIGHT)

    def test_typing_a_key_that_is_not_a_hex_digit_is_ignored(self, slider):
        slider.text_sprite.is_active = True
        slider.text_sprite.text = '1'

        slider.text_sprite.on_key_down_event(_key_down(pygame.K_z, unicode='z'))

        assert slider.text_sprite.text == '1'
        assert slider.text_sprite.is_active is True

    def test_update_redraws_the_track_only_when_dirty(self, slider):
        slider.dirty = 2
        slider.update()
        slider.image.fill((1, 2, 3))
        slider.dirty = 0

        slider.update()

        assert slider.image.get_at((0, 0))[:3] == (1, 2, 3)

    def test_update_draws_a_grey_gradient_for_an_unnamed_slider(self, slider):
        slider.update()

        assert _rgb_at(slider.image, (0, 0)) == (0, 0, 0)
        middle = TEST_WIDTH // 2
        middle_intensity = int(middle / TEST_WIDTH * 255)
        assert _rgb_at(slider.image, (middle, TEST_HEIGHT // 2)) == (middle_intensity,) * 3
        last_intensity = int((TEST_WIDTH - 1) / TEST_WIDTH * 255)
        assert _rgb_at(slider.image, (TEST_WIDTH - 1, 0)) == (last_intensity,) * 3

    @pytest.mark.parametrize(
        ('name', 'channel_index'),
        [('R', 0), ('G', 1), ('B', 2)],
    )
    def test_update_draws_a_channel_gradient_for_a_named_slider(self, name, channel_index):
        slider = SliderSprite(
            x=TEST_X_POS, y=TEST_Y_POS, width=TEST_WIDTH, height=TEST_HEIGHT, name=name
        )

        slider.update()

        middle = TEST_WIDTH // 2
        expected = [0, 0, 0]
        expected[channel_index] = int(middle / TEST_WIDTH * 255)
        assert _rgb_at(slider.image, (middle, 0)) == tuple(expected)

    def test_drawing_the_group_puts_the_knob_at_the_value_on_the_screen(self):
        """Drawn to the real display, the knob covers the track where the value puts it."""
        group = pygame.sprite.LayeredDirty()
        slider = SliderSprite(
            x=TEST_X_POS, y=TEST_Y_POS, width=TEST_WIDTH, height=TEST_HEIGHT, groups=group
        )
        slider.value = TEST_VALUE_200
        screen = pygame.display.get_surface()
        screen.fill((0, 0, 0))
        group.update()

        group.draw(screen)

        knob_rect = slider.slider_knob.rect
        assert knob_rect.x == TEST_X_POS + TEST_VALUE_200 * (TEST_WIDTH - 5) // TEST_MAX_VALUE
        assert _rgb_at(screen, knob_rect.center) == KNOB_COLOR
        # Left of the knob is the track's gradient, not the knob
        track_x = knob_rect.x - 10
        assert (
            _rgb_at(screen, (track_x, knob_rect.centery))
            == (int((track_x - TEST_X_POS) / TEST_WIDTH * 255),) * 3
        )
        # The value is drawn in the text box right of the track
        text_rect = slider.text_sprite.rect
        text_area = pygame.surfarray.array3d(screen.subsurface(text_rect))
        assert (text_area == (255, 255, 255)).all(axis=2).any()

    @staticmethod
    def _draw_slider_group(*, slider, group, screen):
        """Update and draw a slider's group on a black screen, as one frame.

        Returns:
            numpy.ndarray: The RGB pixels the frame shows inside the slider's rect.

        """
        screen.fill((0, 0, 0))
        group.update()
        group.draw(screen)
        return pygame.surfarray.array3d(screen.subsurface(slider.rect))

    @staticmethod
    def _expected_slider_pixels(*, slider, name, screen):
        """Draw what the slider should show onto a copy of the screen, in its pixel format.

        The track is one column per x, intensity int(x / width * 255) in the slider's channel
        (all three for a slider that is not R, G or B), with the knob drawn over it.

        Returns:
            numpy.ndarray: The RGB pixels expected inside the slider's rect.

        """
        expected_screen = screen.copy()
        expected_screen.fill((0, 0, 0))
        for column in range(TEST_WIDTH):
            intensity = int(column / TEST_WIDTH * 255)
            channels = {
                'R': (intensity, 0, 0),
                'G': (0, intensity, 0),
                'B': (0, 0, intensity),
            }.get(name, (intensity, intensity, intensity))
            expected_screen.fill(
                channels, pygame.Rect(TEST_X_POS + column, TEST_Y_POS, 1, TEST_HEIGHT)
            )
        expected_screen.fill(KNOB_COLOR, slider.slider_knob.rect)
        return pygame.surfarray.array3d(expected_screen.subsurface(slider.rect))

    @pytest.mark.parametrize('name', ['R', 'G', 'B', 'A', None])
    def test_the_drawn_slider_shows_its_gradient_and_knob_frame_after_frame(self, name):
        """On the real display, every frame shows the track's gradient with the knob over it.

        The knob moves between frames, so the track must show again where the knob was.
        """
        group = pygame.sprite.LayeredDirty()
        slider = SliderSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            name=name,
            groups=group,
        )
        screen = pygame.display.get_surface()

        for value in (TEST_MIN_VALUE, TEST_DEFAULT_VALUE, TEST_MAX_VALUE, TEST_VALUE_64):
            slider.value = value
            drawn_pixels = self._draw_slider_group(slider=slider, group=group, screen=screen)

            expected_pixels = self._expected_slider_pixels(slider=slider, name=name, screen=screen)
            assert (drawn_pixels == expected_pixels).all(), f'value {value}'

    def test_the_gradient_is_drawn_once_across_many_dirty_updates(self, slider, mocker):
        """A dirty slider whose size and name have not changed repaints its track in one blit."""
        draw_line_spy = mocker.spy(pygame.draw, 'line')
        slider.dirty = 2

        for value in range(TEST_MAX_VALUE + 1):
            slider.value = value
            slider.update()

        assert draw_line_spy.call_count == 0

    def test_resizing_the_slider_redraws_its_gradient_for_the_new_width(self, slider):
        new_width = TEST_WIDTH // 2
        slider.width = new_width

        slider.update()

        middle = new_width // 2
        assert _rgb_at(slider.image, (middle, 0)) == (int(middle / new_width * 255),) * 3

    def test_renaming_the_slider_redraws_its_gradient_in_the_new_channel(self, slider):
        slider.name = 'G'

        slider.update()

        middle = TEST_WIDTH // 2
        assert _rgb_at(slider.image, (middle, 0)) == (0, int(middle / TEST_WIDTH * 255), 0)

    def test_a_new_image_gets_the_gradient_drawn_on_it(self, slider):
        slider.image = pygame.Surface((TEST_WIDTH, TEST_HEIGHT))

        slider.update()

        middle = TEST_WIDTH // 2
        assert _rgb_at(slider.image, (middle, 0)) == (int(middle / TEST_WIDTH * 255),) * 3
