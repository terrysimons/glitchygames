"""Tests for src/apps/bitmappy/bitmappy/controllers/slider_operations.py.

The slider delegate moves a controller between the R, G and B slider modes and adjusts the
slider of its mode, once or continuously with acceleration. These tests drive it through a
real ControllerEventHandler and ModeSwitcher with stand-in sliders, and check the slider
values, the slider events sent to the editor and the modes that result.
"""

from __future__ import annotations

from typing import Any

import pytest

from bitmappy.controllers.event_handler import ControllerEventHandler
from bitmappy.controllers.manager import MultiControllerManager
from bitmappy.controllers.modes import ControllerMode, ModeSwitcher
from glitchygames.sources import advance_frame_clock

CONTROLLER_ID = 0


@pytest.fixture(autouse=True)
def fresh_controller_manager(mocker):
    """Give each test its own MultiControllerManager singleton, restoring the shared one after."""
    mocker.patch.object(MultiControllerManager, '_instance', None)


class FakeSlider:
    """A slider holding only its value."""

    def __init__(self, *, value: int) -> None:
        """Start at ``value``."""
        self.value = value


class FakeEditor:
    """The parts of the editor the slider delegate reads."""

    def __init__(self) -> None:
        """Make an editor with all three sliders at 100."""
        self.mode_switcher = ModeSwitcher()
        self.multi_controller_manager = MultiControllerManager()
        self.red_slider = FakeSlider(value=100)
        self.green_slider = FakeSlider(value=100)
        self.blue_slider = FakeSlider(value=100)
        self.slider_events: list[tuple[str, int]] = []

    def on_slider_event(self, event: Any, trigger: Any) -> None:
        """Record the slider event the delegate sends (it updates the color well)."""
        self.slider_events.append((trigger.name, trigger.value))


def _make_handler(*, mode: ControllerMode | None = ControllerMode.R_SLIDER):
    """Build a handler over a FakeEditor with one controller in ``mode``.

    Args:
        mode: The controller's mode, or None to leave it unregistered.

    Returns:
        The (handler, editor) pair.

    """
    editor = FakeEditor()
    handler = ControllerEventHandler(editor=editor)  # type: ignore[arg-type]
    if mode is not None:
        editor.mode_switcher.register_controller(CONTROLLER_ID, mode)
    return handler, editor


class TestHandleSliderModeNavigation:
    """Up and down move between the R, G and B slider modes, wrapping around."""

    @pytest.mark.parametrize(
        ('start_mode', 'direction', 'expected_mode'),
        [
            (ControllerMode.R_SLIDER, 'down', ControllerMode.G_SLIDER),
            (ControllerMode.B_SLIDER, 'down', ControllerMode.R_SLIDER),
            (ControllerMode.G_SLIDER, 'up', ControllerMode.R_SLIDER),
            (ControllerMode.R_SLIDER, 'up', ControllerMode.B_SLIDER),
        ],
    )
    def test_navigates_the_given_controller(self, start_mode, direction, expected_mode):
        """D-pad navigation moves the named controller through the cycle."""
        handler, editor = _make_handler(mode=start_mode)

        handler.slider.handle_slider_mode_navigation(direction, CONTROLLER_ID)

        assert editor.mode_switcher.get_controller_mode(CONTROLLER_ID) == expected_mode

    def test_keyboard_navigation_moves_the_first_controller_in_slider_mode(self):
        """Without a controller id, the first controller in a slider mode is moved."""
        handler, editor = _make_handler(mode=ControllerMode.CANVAS)
        editor.mode_switcher.register_controller(1, ControllerMode.G_SLIDER)
        editor.mode_switcher.register_controller(2, ControllerMode.R_SLIDER)

        handler.slider.handle_slider_mode_navigation('down')

        assert editor.mode_switcher.get_controller_mode(CONTROLLER_ID) == ControllerMode.CANVAS
        assert editor.mode_switcher.get_controller_mode(1) == ControllerMode.B_SLIDER
        assert editor.mode_switcher.get_controller_mode(2) == ControllerMode.R_SLIDER

    def test_keyboard_navigation_without_a_slider_controller_does_nothing(self):
        """No controller in a slider mode: nothing changes."""
        handler, editor = _make_handler(mode=ControllerMode.CANVAS)

        handler.slider.handle_slider_mode_navigation('down')

        assert editor.mode_switcher.get_controller_mode(CONTROLLER_ID) == ControllerMode.CANVAS

    def test_a_controller_outside_the_slider_modes_is_not_moved(self):
        """A named controller in canvas mode keeps its mode."""
        handler, editor = _make_handler(mode=ControllerMode.CANVAS)

        handler.slider.handle_slider_mode_navigation('down', CONTROLLER_ID)

        assert editor.mode_switcher.get_controller_mode(CONTROLLER_ID) == ControllerMode.CANVAS

    def test_an_unregistered_controller_is_ignored(self):
        """A controller id the mode switcher does not know changes nothing."""
        handler, editor = _make_handler(mode=None)

        handler.slider.handle_slider_mode_navigation('down', CONTROLLER_ID)

        assert editor.mode_switcher.controller_modes == {}

    def test_an_editor_without_a_mode_switcher_is_ignored(self):
        """No mode switcher: the call returns without error."""
        handler, editor = _make_handler(mode=None)
        del editor.mode_switcher

        handler.slider.handle_slider_mode_navigation('down', CONTROLLER_ID)

        assert not hasattr(editor, 'mode_switcher')


class TestSliderAdjustValue:
    """Adjusting changes the slider of the controller's mode, clamped to 0..255."""

    @pytest.mark.parametrize(
        ('mode', 'slider_attribute', 'slider_name'),
        [
            (ControllerMode.R_SLIDER, 'red_slider', 'R'),
            (ControllerMode.G_SLIDER, 'green_slider', 'G'),
            (ControllerMode.B_SLIDER, 'blue_slider', 'B'),
        ],
    )
    def test_adjusts_the_slider_of_the_mode(self, mode, slider_attribute, slider_name):
        """Only the mode's slider changes, and the editor gets its slider event."""
        handler, editor = _make_handler(mode=mode)

        handler.slider._slider_adjust_value(CONTROLLER_ID, 5)

        assert getattr(editor, slider_attribute).value == 105
        assert editor.slider_events == [(slider_name, 105)]
        untouched = {'red_slider', 'green_slider', 'blue_slider'} - {slider_attribute}
        assert all(getattr(editor, name).value == 100 for name in untouched)

    @pytest.mark.parametrize(('delta', 'expected_value'), [(500, 255), (-500, 0)])
    def test_clamps_to_the_color_range(self, delta, expected_value):
        """The value never leaves 0..255."""
        handler, editor = _make_handler(mode=ControllerMode.R_SLIDER)

        handler.slider._slider_adjust_value(CONTROLLER_ID, delta)

        assert editor.red_slider.value == expected_value

    @pytest.mark.parametrize('mode', [ControllerMode.CANVAS, None])
    def test_a_controller_outside_the_slider_modes_changes_nothing(self, mode):
        """Canvas mode or no mode: no slider changes and no event is sent."""
        handler, editor = _make_handler(mode=mode)

        handler.slider._slider_adjust_value(CONTROLLER_ID, 5)

        assert editor.slider_events == []
        assert editor.red_slider.value == 100

    def test_an_editor_without_a_mode_switcher_changes_nothing(self):
        """No mode switcher: no slider changes."""
        handler, editor = _make_handler(mode=None)
        del editor.mode_switcher

        handler.slider._slider_adjust_value(CONTROLLER_ID, 5)

        assert editor.slider_events == []


class TestContinuousSliderAdjustment:
    """Holding the D-pad adjusts the slider with acceleration."""

    def test_start_adjusts_once_and_records_the_adjustment(self):
        """Starting ticks immediately and records the held direction."""
        handler, editor = _make_handler(mode=ControllerMode.G_SLIDER)

        handler.slider.start_slider_continuous_adjustment(CONTROLLER_ID, -1)

        assert editor.green_slider.value == 99
        adjustment_data = handler.slider_continuous_adjustments[CONTROLLER_ID]
        assert adjustment_data['direction'] == -1
        assert adjustment_data['acceleration_level'] == 0

    def test_stop_ends_the_adjustment(self):
        """Stopping removes the controller's adjustment."""
        handler, _editor = _make_handler()
        handler.slider.start_slider_continuous_adjustment(CONTROLLER_ID, 1)

        handler.slider.stop_slider_continuous_adjustment(CONTROLLER_ID)

        assert CONTROLLER_ID not in handler.slider_continuous_adjustments

    def test_stop_without_an_adjustment_does_nothing(self):
        """Stopping a controller that is not adjusting leaves the table alone."""
        handler, _editor = _make_handler()

        handler.slider.stop_slider_continuous_adjustment(CONTROLLER_ID)

        assert handler.slider_continuous_adjustments == {}

    def test_update_without_adjustment_state_does_nothing(self):
        """A handler without the adjustment table is left alone."""
        handler, editor = _make_handler()
        del handler.slider_continuous_adjustments

        handler.slider.update_slider_continuous_adjustments()

        assert editor.red_slider.value == 100

    def test_update_waits_for_the_interval(self):
        """Before the first interval (0.15 s at level 0) the slider does not change again."""
        handler, editor = _make_handler()
        handler.slider.start_slider_continuous_adjustment(CONTROLLER_ID, 1)
        advance_frame_clock(seconds=0.1)

        handler.slider.update_slider_continuous_adjustments()

        assert editor.red_slider.value == 101
        assert editor.slider_events == [('R', 101)]

    @pytest.mark.parametrize(
        ('held_seconds', 'expected_level', 'expected_step'),
        [(0.2, 0, 1), (1.0, 1, 2), (2.0, 2, 4), (3.0, 3, 8)],
    )
    def test_update_accelerates_the_longer_the_dpad_is_held(
        self,
        held_seconds,
        expected_level,
        expected_step,
    ):
        """Each acceleration level doubles the step, and each step updates the color."""
        handler, editor = _make_handler()
        handler.slider.start_slider_continuous_adjustment(CONTROLLER_ID, 1)
        advance_frame_clock(seconds=held_seconds)

        handler.slider.update_slider_continuous_adjustments()

        adjustment_data = handler.slider_continuous_adjustments[CONTROLLER_ID]
        assert adjustment_data['acceleration_level'] == expected_level
        assert editor.red_slider.value == 101 + expected_step
        assert editor.slider_events == [('R', 101), ('R', 101 + expected_step)]

    def test_update_caps_the_step_at_eight(self):
        """A shoulder-held adjustment of 8 never steps more than 8, however accelerated."""
        handler, editor = _make_handler()
        handler.slider.start_slider_continuous_adjustment(CONTROLLER_ID, -8)
        advance_frame_clock(seconds=3.0)

        handler.slider.update_slider_continuous_adjustments()

        assert editor.red_slider.value == 100 - 8 - 8

    def test_update_outside_slider_mode_does_not_change_the_color(self):
        """A controller that left the slider modes mid-hold changes no slider or color well."""
        handler, editor = _make_handler()
        handler.slider.start_slider_continuous_adjustment(CONTROLLER_ID, 1)
        editor.mode_switcher.controller_modes[CONTROLLER_ID].switch_to_mode(
            ControllerMode.CANVAS,
            0.0,
        )
        advance_frame_clock(seconds=0.2)

        handler.slider.update_slider_continuous_adjustments()

        assert editor.red_slider.value == 101
        assert editor.slider_events == [('R', 101)]


class TestSliderPreviousAndNext:
    """The D-pad slider previous/next hooks are kept for compatibility and change nothing."""

    @pytest.mark.parametrize('method_name', ['_slider_previous', '_slider_next'])
    def test_changes_nothing(self, method_name):
        """L2/R2 switch sliders now, so these leave the mode and sliders alone."""
        handler, editor = _make_handler(mode=ControllerMode.G_SLIDER)

        getattr(handler.slider, method_name)(CONTROLLER_ID)

        assert editor.mode_switcher.get_controller_mode(CONTROLLER_ID) == ControllerMode.G_SLIDER
        assert editor.slider_events == []
