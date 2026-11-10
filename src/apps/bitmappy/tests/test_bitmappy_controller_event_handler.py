"""Tests for src/apps/bitmappy/src/bitmappy/controllers/event_handler.py.

The ControllerEventHandler routes controller and joystick events to the mode strategies,
switches modes from the triggers, and delegates to its canvas, slider, indicator and film
strip helpers. These tests drive a real handler over a stand-in editor with a real
ModeSwitcher and MultiControllerManager, and the frame's input snapshot.
"""

from __future__ import annotations

import logging

import pygame
import pytest

from bitmappy.controllers.event_handler import ControllerEventHandler
from bitmappy.controllers.manager import (
    ControllerInfo,
    ControllerStatus,
    MultiControllerManager,
)
from bitmappy.controllers.modes import ControllerMode, ModeSwitcher
from bitmappy.controllers.selection import ControllerSelection
from glitchygames.events import HashableEvent
from glitchygames.input.state import InputSnapshot, set_current_input
from glitchygames.sources import advance_frame_clock

CONTROLLER_ID = 0
INSTANCE_ID = 12
HANDLER_LOGGER = 'game.tools.bitmappy.controllers.event_handler'


@pytest.fixture(autouse=True)
def fresh_controller_manager(mocker):
    """Give each test its own MultiControllerManager singleton, restoring the shared one after."""
    mocker.patch.object(MultiControllerManager, '_instance', None)


class FakeModeChangeTracker:
    """Records the controller mode changes submitted for undo."""

    def __init__(self) -> None:
        """Start with nothing submitted."""
        self.mode_changes: list[tuple[int, str, str]] = []

    def add_controller_mode_change(self, controller_id: int, old_mode: str, new_mode: str) -> None:
        """Record one mode change."""
        self.mode_changes.append((controller_id, old_mode, new_mode))


class FakeEditor:
    """The parts of the editor the controller event handler reaches."""

    def __init__(self) -> None:
        """Make an editor with a mode switcher, a controller manager and no selections."""
        self.mode_switcher = ModeSwitcher()
        self.multi_controller_manager = MultiControllerManager()
        # A scan just happened, so scan_for_controllers() reuses the known controllers
        # instead of enumerating real devices
        self.multi_controller_manager.last_scan_time = 0.0
        self.controller_selections: dict[int, ControllerSelection] = {}
        self.controller_position_operation_tracker = FakeModeChangeTracker()
        self.selected_frame_visible = True
        self.undo_count = 0

    def handle_undo(self) -> None:
        """Count undo requests."""
        self.undo_count += 1


def _make_handler() -> tuple[ControllerEventHandler, FakeEditor]:
    """Build a handler over a FakeEditor whose mode switcher hands out strategies.

    Returns:
        The (handler, editor) pair.

    """
    editor = FakeEditor()
    handler = ControllerEventHandler(editor=editor)  # type: ignore[arg-type]
    editor.mode_switcher.set_handler(handler)
    return handler, editor


def _connect_controller(
    editor: FakeEditor,
    *,
    status: ControllerStatus = ControllerStatus.CONNECTED,
    assigned: bool = False,
) -> ControllerInfo:
    """Make the manager know controller slot 0 as instance 12.

    Returns:
        The controller's info.

    """
    controller_info = ControllerInfo(
        controller_id=CONTROLLER_ID,
        instance_id=INSTANCE_ID,
        status=status,
    )
    editor.multi_controller_manager.controllers[INSTANCE_ID] = controller_info
    if assigned:
        editor.multi_controller_manager.assigned_controllers[INSTANCE_ID] = CONTROLLER_ID
    return controller_info


def _snapshot_with_axes(device_axes: dict[int, tuple[float, ...]]) -> None:
    """Make this frame's input snapshot hold the given device axes."""
    set_current_input(
        snapshot=InputSnapshot(
            pressed_scancodes=frozenset(),
            modifiers=0,
            mouse_position=(0, 0),
            mouse_buttons=(False, False, False),
            mouse_focused=True,
            device_axes=device_axes,
        ),
    )


def _debug_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Return the handler's captured log messages.

    Returns:
        The messages, oldest first.

    """
    return [record.getMessage() for record in caplog.records if record.name == HANDLER_LOGGER]


class TestDelegation:
    """The handler's public methods forward to its composition delegates."""

    @pytest.mark.parametrize(
        ('handler_method', 'delegate', 'arguments'),
        [
            ('render_visual_indicators', ('indicators', 'render_visual_indicators'), ()),
            ('update_continuous_movements', ('canvas', 'update_canvas_continuous_movements'), ()),
            (
                'update_continuous_adjustments',
                ('slider', 'update_slider_continuous_adjustments'),
                (),
            ),
            ('handle_controller_drag_end', ('canvas', 'handle_controller_drag_end'), (3,)),
            (
                'start_canvas_continuous_movement',
                ('canvas', 'start_canvas_continuous_movement'),
                (3, 1, -1),
            ),
            (
                'stop_canvas_continuous_movement',
                ('canvas', 'stop_canvas_continuous_movement'),
                (3,),
            ),
            ('canvas_paint_horizontal_line', ('canvas', 'canvas_paint_horizontal_line'), (3, 8)),
            ('canvas_paint_vertical_line', ('canvas', 'canvas_paint_vertical_line'), (3, -8)),
            ('canvas_jump_horizontal', ('canvas', 'canvas_jump_horizontal'), (3, 8)),
            ('canvas_jump_vertical', ('canvas', 'canvas_jump_vertical'), (3, -8)),
            (
                'handle_slider_mode_navigation',
                ('slider', 'handle_slider_mode_navigation'),
                ('up', 3),
            ),
            (
                'stop_slider_continuous_adjustment',
                ('slider', 'stop_slider_continuous_adjustment'),
                (3,),
            ),
            (
                'update_controller_visual_indicator_for_mode',
                ('indicators', 'update_controller_visual_indicator_for_mode'),
                (3, ControllerMode.CANVAS),
            ),
            (
                'update_controller_canvas_visual_indicator',
                ('indicators', 'update_controller_canvas_visual_indicator'),
                (3,),
            ),
            ('multi_controller_activate', ('film_strip', 'multi_controller_activate'), (3,)),
            (
                'multi_controller_previous_frame',
                ('film_strip', 'multi_controller_previous_frame'),
                (3,),
            ),
            ('multi_controller_next_frame', ('film_strip', 'multi_controller_next_frame'), (3,)),
            (
                'multi_controller_previous_animation',
                ('film_strip', 'multi_controller_previous_animation'),
                (3,),
            ),
            (
                'multi_controller_next_animation',
                ('film_strip', 'multi_controller_next_animation'),
                (3,),
            ),
            (
                'multi_controller_select_current_frame',
                ('film_strip', 'multi_controller_select_current_frame'),
                (3,),
            ),
            (
                'multi_controller_toggle_onion_skinning',
                ('film_strip', 'multi_controller_toggle_onion_skinning'),
                (3,),
            ),
            (
                'multi_controller_toggle_selected_frame_visibility',
                ('film_strip', 'multi_controller_toggle_selected_frame_visibility'),
                (3,),
            ),
            (
                'reinitialize_multi_controller_system',
                ('film_strip', 'reinitialize_multi_controller_system'),
                ({1: ('walk', 2)},),
            ),
        ],
    )
    def test_forwards_to_the_delegate(self, mocker, handler_method, delegate, arguments):
        """Each public method calls its delegate's method with the same arguments."""
        handler, _editor = _make_handler()
        delegate_name, delegate_method = delegate
        delegate_action = mocker.patch.object(getattr(handler, delegate_name), delegate_method)

        getattr(handler, handler_method)(*arguments)

        delegate_action.assert_called_once_with(*arguments)

    def test_paint_forwards_force(self, mocker):
        """The paint call passes ``force`` through as a keyword."""
        handler, _editor = _make_handler()
        paint = mocker.patch.object(handler.canvas, 'canvas_paint_at_controller_position')

        handler.canvas_paint_at_controller_position(3, force=True)

        paint.assert_called_once_with(3, force=True)

    def test_start_slider_adjustment_forwards(self, mocker):
        """The slider adjustment start passes the controller and direction through."""
        handler, _editor = _make_handler()
        start = mocker.patch.object(handler.slider, 'start_slider_continuous_adjustment')

        handler.start_slider_continuous_adjustment(3, -1)

        start.assert_called_once_with(3, -1)


class TestOnControllerButtonDownEvent:
    """Controller button presses assign the controller and reach its mode's strategy."""

    def test_an_unknown_instance_is_ignored(self):
        """A press from an instance the manager does not know changes nothing."""
        handler, editor = _make_handler()

        handler.on_controller_button_down_event(
            HashableEvent(pygame.CONTROLLERBUTTONDOWN, instance_id=99, button=0),
        )

        assert editor.controller_selections == {}
        assert editor.multi_controller_manager.assigned_controllers == {}

    def test_the_first_press_assigns_and_reaches_the_strategy(self):
        """A connected controller is assigned on its first press and the press is handled."""
        handler, editor = _make_handler()
        controller_info = _connect_controller(editor)
        editor.mode_switcher.register_controller(CONTROLLER_ID, ControllerMode.FILM_STRIP)

        handler.on_controller_button_down_event(
            HashableEvent(
                pygame.CONTROLLERBUTTONDOWN,
                instance_id=INSTANCE_ID,
                button=pygame.CONTROLLER_BUTTON_B,
            ),
        )

        assert editor.multi_controller_manager.assigned_controllers == {INSTANCE_ID: CONTROLLER_ID}
        assert controller_info.status == ControllerStatus.ASSIGNED
        assert editor.controller_selections[CONTROLLER_ID].instance_id == INSTANCE_ID
        assert editor.undo_count == 1

    def test_an_existing_selection_is_kept(self):
        """An assigned controller keeps its selection and its activity is updated."""
        handler, editor = _make_handler()
        _connect_controller(editor, status=ControllerStatus.ACTIVE, assigned=True)
        existing_selection = ControllerSelection(
            controller_id=CONTROLLER_ID,
            instance_id=INSTANCE_ID,
        )
        editor.controller_selections[CONTROLLER_ID] = existing_selection
        editor.mode_switcher.register_controller(CONTROLLER_ID, ControllerMode.FILM_STRIP)
        advance_frame_clock(seconds=0.5)

        handler.on_controller_button_down_event(
            HashableEvent(
                pygame.CONTROLLERBUTTONDOWN,
                instance_id=INSTANCE_ID,
                button=pygame.CONTROLLER_BUTTON_B,
            ),
        )

        assert editor.controller_selections[CONTROLLER_ID] is existing_selection
        assert existing_selection.state.last_update_time == pytest.approx(0.5)
        assert editor.undo_count == 1

    def test_an_assigned_controller_without_a_selection_gets_one(self):
        """An assigned controller that lost its selection gets a new one."""
        handler, editor = _make_handler()
        _connect_controller(editor, status=ControllerStatus.ACTIVE, assigned=True)
        editor.mode_switcher.register_controller(CONTROLLER_ID, ControllerMode.FILM_STRIP)

        handler.on_controller_button_down_event(
            HashableEvent(
                pygame.CONTROLLERBUTTONDOWN,
                instance_id=INSTANCE_ID,
                button=pygame.CONTROLLER_BUTTON_B,
            ),
        )

        assert editor.controller_selections[CONTROLLER_ID].controller_id == CONTROLLER_ID

    def test_a_known_but_unassigned_controller_is_ignored(self):
        """A controller that is neither connected-and-new nor assigned does nothing."""
        handler, editor = _make_handler()
        _connect_controller(editor, status=ControllerStatus.ACTIVE)
        editor.mode_switcher.register_controller(CONTROLLER_ID, ControllerMode.FILM_STRIP)

        handler.on_controller_button_down_event(
            HashableEvent(
                pygame.CONTROLLERBUTTONDOWN,
                instance_id=INSTANCE_ID,
                button=pygame.CONTROLLER_BUTTON_B,
            ),
        )

        assert editor.controller_selections == {}
        assert editor.undo_count == 0

    def test_a_controller_without_a_mode_skips_the_press(self):
        """No mode registered means no strategy, so the press is skipped."""
        handler, editor = _make_handler()
        _connect_controller(editor)

        handler.on_controller_button_down_event(
            HashableEvent(
                pygame.CONTROLLERBUTTONDOWN,
                instance_id=INSTANCE_ID,
                button=pygame.CONTROLLER_BUTTON_B,
            ),
        )

        assert CONTROLLER_ID in editor.controller_selections
        assert editor.undo_count == 0


class TestOnControllerButtonUpEvent:
    """Controller button releases reach the mode's strategy."""

    def test_an_unassigned_instance_is_ignored(self, mocker):
        """A release from an unassigned instance reaches no strategy."""
        handler, editor = _make_handler()
        editor.mode_switcher.register_controller(CONTROLLER_ID, ControllerMode.CANVAS)
        stop = mocker.patch.object(handler, 'stop_canvas_continuous_movement')

        handler.on_controller_button_up_event(
            HashableEvent(
                pygame.CONTROLLERBUTTONUP,
                instance_id=INSTANCE_ID,
                button=pygame.CONTROLLER_BUTTON_DPAD_LEFT,
            ),
        )

        stop.assert_not_called()

    def test_a_release_without_a_mode_is_ignored(self):
        """An assigned controller with no mode has no strategy to release to."""
        handler, editor = _make_handler()
        _connect_controller(editor, assigned=True)
        handler.canvas_continuous_movements[CONTROLLER_ID] = {'start_x': 0, 'start_y': 0}

        handler.on_controller_button_up_event(
            HashableEvent(
                pygame.CONTROLLERBUTTONUP,
                instance_id=INSTANCE_ID,
                button=pygame.CONTROLLER_BUTTON_DPAD_LEFT,
            ),
        )

        assert CONTROLLER_ID in handler.canvas_continuous_movements

    def test_a_canvas_dpad_release_stops_the_movement(self):
        """In canvas mode a D-pad release ends continuous movement."""
        handler, editor = _make_handler()
        _connect_controller(editor, assigned=True)
        editor.mode_switcher.register_controller(CONTROLLER_ID, ControllerMode.CANVAS)
        handler.canvas_continuous_movements[CONTROLLER_ID] = {'start_x': 0, 'start_y': 0}
        del editor.controller_position_operation_tracker

        handler.on_controller_button_up_event(
            HashableEvent(
                pygame.CONTROLLERBUTTONUP,
                instance_id=INSTANCE_ID,
                button=pygame.CONTROLLER_BUTTON_DPAD_LEFT,
            ),
        )

        assert CONTROLLER_ID not in handler.canvas_continuous_movements


class TestJoystickEvents:
    """Joystick (non game controller) events."""

    def test_button_zero_selects_the_frame_of_the_instance(self, mocker):
        """Joystick button 0 selects the current frame for the event's instance."""
        handler, _editor = _make_handler()
        select = mocker.patch.object(handler, 'multi_controller_select_current_frame')

        handler.on_joy_button_down_event(
            HashableEvent(pygame.JOYBUTTONDOWN, instance_id=INSTANCE_ID, button=0),
        )

        select.assert_called_once_with(INSTANCE_ID)

    def test_button_zero_without_an_instance_selects_for_controller_zero(self, mocker):
        """Without an instance id, joystick button 0 selects for controller 0."""
        handler, _editor = _make_handler()
        select = mocker.patch.object(handler, 'multi_controller_select_current_frame')

        handler.on_joy_button_down_event(HashableEvent(pygame.JOYBUTTONDOWN, button=0))

        select.assert_called_once_with(0)

    def test_button_one_cancels(self, mocker):
        """Joystick button 1 is the film strip cancel."""
        handler, _editor = _make_handler()
        cancel = mocker.patch.object(handler.film_strip, 'controller_cancel')

        handler.on_joy_button_down_event(HashableEvent(pygame.JOYBUTTONDOWN, button=1))

        cancel.assert_called_once_with()

    @pytest.mark.parametrize('button', [9, 5])
    def test_left_shoulder_and_other_buttons_do_nothing(self, mocker, button):
        """The left shoulder (button 9) and unknown buttons neither select nor cancel."""
        handler, _editor = _make_handler()
        select = mocker.patch.object(handler, 'multi_controller_select_current_frame')
        cancel = mocker.patch.object(handler.film_strip, 'controller_cancel')

        handler.on_joy_button_down_event(HashableEvent(pygame.JOYBUTTONDOWN, button=button))
        handler.on_joy_button_up_event(HashableEvent(pygame.JOYBUTTONUP, button=button))

        select.assert_not_called()
        cancel.assert_not_called()

    def test_a_centered_hat_is_below_the_threshold(self, caplog):
        """A centered hat ((0, 0), as pygame reports it) is ignored as below the threshold."""
        caplog.set_level(logging.DEBUG, logger=HANDLER_LOGGER)
        handler, _editor = _make_handler()

        handler.on_joy_hat_motion_event(
            HashableEvent(pygame.JOYHATMOTION, hat=0, value=(0, 0)),
        )

        assert 'DEBUG: Joystick hat motion below threshold, ignoring' in _debug_messages(caplog)

    @pytest.mark.parametrize(
        ('hat_value', 'direction'),
        [((0, 1), 'up'), ((1, 0), 'right'), ((0, -1), 'down'), ((-1, 0), 'left')],
    )
    def test_hat_directions_are_disabled(self, caplog, hat_value, direction):
        """Each hat direction (pygame's (x, y) tuple) is recognised but left to the controllers.

        They are left to the multi-controller system; they were compared with integer bitmasks,
        which never matched.
        """
        caplog.set_level(logging.DEBUG, logger=HANDLER_LOGGER)
        handler, _editor = _make_handler()

        handler.on_joy_hat_motion_event(
            HashableEvent(pygame.JOYHATMOTION, hat=0, value=hat_value),
        )

        assert (
            f'DEBUG: Joystick hat {direction} - DISABLED (use multi-controller system)'
            in _debug_messages(caplog)
        )

    def test_a_diagonal_hat_matches_no_direction(self, caplog):
        """A diagonal passes the threshold but names none of the four directions."""
        caplog.set_level(logging.DEBUG, logger=HANDLER_LOGGER)
        handler, _editor = _make_handler()

        handler.on_joy_hat_motion_event(
            HashableEvent(pygame.JOYHATMOTION, hat=0, value=(1, 1)),
        )

        assert not any('DISABLED' in message for message in _debug_messages(caplog))
        assert not any('below threshold' in message for message in _debug_messages(caplog))

    def test_stick_axis_and_ball_motion_are_ignored(self):
        """Joystick stick axes and balls change no mode."""
        handler, editor = _make_handler()

        handler.on_joy_axis_motion_event(HashableEvent(pygame.JOYAXISMOTION, axis=0, value=1.0))
        handler.on_joy_ball_motion_event(
            HashableEvent(pygame.JOYBALLMOTION, ball=0, rel=(1, 1)),
        )

        assert editor.mode_switcher.controller_modes == {}

    def test_a_joystick_trigger_axis_registers_the_joystick_by_its_index(self):
        """A joystick trigger axis registers the joystick by its index, and L2 moves it to canvas.

        The joystick path reads triggers on pygame 2's -1.0..1.0 scale, as the controller path
        does (BUGS.md #67): L2 fully pressed and R2 released switch film strip to canvas. It
        used to read about 0.5 for any position, so both counted as pressed and nothing switched.
        """
        handler, editor = _make_handler()
        _snapshot_with_axes({3: (0.0, 0.0, 0.0, 0.0, 1.0, -1.0)})

        handler.on_joy_axis_motion_event(
            HashableEvent(pygame.JOYAXISMOTION, joy=3, axis=4, value=1.0),
        )

        assert editor.mode_switcher.get_controller_mode(3) == ControllerMode.CANVAS
        assert editor.mode_switcher.trigger_detector.get_trigger_state(3, 'L2') == pytest.approx(
            1.0
        )
        assert editor.mode_switcher.trigger_detector.get_trigger_state(3, 'R2') == pytest.approx(
            0.0
        )


class TestControllerTriggerAxisMotion:
    """Controller triggers switch modes through the mode switcher."""

    def test_l2_moves_a_new_controller_from_film_strip_to_canvas(self):
        """An unregistered controller starts in film strip mode, and L2 moves it to canvas."""
        handler, editor = _make_handler()
        _connect_controller(editor, assigned=True)
        _snapshot_with_axes({INSTANCE_ID: (0.0, 0.0, 0.0, 0.0, 1.0, -1.0)})

        handler.on_controller_axis_motion_event(
            HashableEvent(
                pygame.CONTROLLERAXISMOTION,
                instance_id=INSTANCE_ID,
                axis=pygame.CONTROLLER_AXIS_TRIGGERLEFT,
                value=32767,
            ),
        )

        assert editor.mode_switcher.get_controller_mode(CONTROLLER_ID) == ControllerMode.CANVAS

    def test_a_trigger_mode_switch_records_the_old_and_new_mode_for_undo(self):
        """The undo record of a trigger mode switch holds the mode switched from (#95)."""
        handler, editor = _make_handler()
        _connect_controller(editor, assigned=True)
        _snapshot_with_axes({INSTANCE_ID: (0.0, 0.0, 0.0, 0.0, 1.0, -1.0)})

        handler.on_controller_axis_motion_event(
            HashableEvent(
                pygame.CONTROLLERAXISMOTION,
                instance_id=INSTANCE_ID,
                axis=pygame.CONTROLLER_AXIS_TRIGGERLEFT,
                value=32767,
            ),
        )

        assert editor.controller_position_operation_tracker.mode_changes == [
            (CONTROLLER_ID, 'film_strip', 'canvas'),
        ]

    def test_released_triggers_switch_nothing(self):
        """Triggers below the threshold leave the mode alone."""
        handler, editor = _make_handler()
        _connect_controller(editor, assigned=True)
        editor.mode_switcher.register_controller(CONTROLLER_ID, ControllerMode.CANVAS)
        _snapshot_with_axes({INSTANCE_ID: (0.0, 0.0, 0.0, 0.0, -1.0, -1.0)})

        handler.on_controller_axis_motion_event(
            HashableEvent(
                pygame.CONTROLLERAXISMOTION,
                instance_id=INSTANCE_ID,
                axis=pygame.CONTROLLER_AXIS_TRIGGERRIGHT,
                value=0,
            ),
        )

        assert editor.mode_switcher.get_controller_mode(CONTROLLER_ID) == ControllerMode.CANVAS
        assert editor.controller_position_operation_tracker.mode_changes == []

    def test_an_unassigned_controller_switches_nothing(self):
        """A trigger from an unassigned instance has no controller id, so nothing changes."""
        handler, editor = _make_handler()
        _snapshot_with_axes({INSTANCE_ID: (0.0, 0.0, 0.0, 0.0, 1.0, -1.0)})

        handler.on_controller_axis_motion_event(
            HashableEvent(
                pygame.CONTROLLERAXISMOTION,
                instance_id=INSTANCE_ID,
                axis=pygame.CONTROLLER_AXIS_TRIGGERLEFT,
                value=32767,
            ),
        )

        assert editor.mode_switcher.controller_modes == {}

    def test_a_stick_axis_is_ignored(self):
        """Stick motion on a controller is disabled and switches nothing."""
        handler, editor = _make_handler()
        _connect_controller(editor, assigned=True)

        handler.on_controller_axis_motion_event(
            HashableEvent(
                pygame.CONTROLLERAXISMOTION,
                instance_id=INSTANCE_ID,
                axis=pygame.CONTROLLER_AXIS_LEFTX,
                value=32767,
            ),
        )

        assert editor.mode_switcher.controller_modes == {}

    def test_controller_triggers_read_zero_without_a_manager(self):
        """An editor without a controller manager reads both triggers as released."""
        handler, editor = _make_handler()
        del editor.multi_controller_manager
        _snapshot_with_axes({INSTANCE_ID: (0.0, 0.0, 0.0, 0.0, 1.0, 1.0)})
        event = HashableEvent(pygame.CONTROLLERAXISMOTION, instance_id=INSTANCE_ID, axis=4)

        assert handler._read_controller_trigger_values(event, CONTROLLER_ID) == (0.0, 0.0)

    def test_controller_triggers_read_zero_for_an_unknown_instance(self):
        """An instance the manager does not know reads both triggers as released."""
        handler, _editor = _make_handler()
        _snapshot_with_axes({INSTANCE_ID: (0.0, 0.0, 0.0, 0.0, 1.0, 1.0)})
        event = HashableEvent(pygame.CONTROLLERAXISMOTION, instance_id=INSTANCE_ID, axis=4)

        assert handler._read_controller_trigger_values(event, CONTROLLER_ID) == (0.0, 0.0)

    def test_a_none_instance_id_falls_back_to_the_joystick_index(self):
        """An event whose instance id is None is identified by its ``joy`` index."""
        handler, _editor = _make_handler()
        event = HashableEvent(pygame.JOYAXISMOTION, instance_id=None, joy=2, axis=4)

        assert handler._get_controller_id_from_event(event) == 2


class TestTrackControllerModeChange:
    """Mode changes are recorded for undo unless undo/redo is being applied."""

    def test_records_while_not_applying_undo(self):
        """A registered controller's mode change is recorded."""
        handler, editor = _make_handler()
        editor.mode_switcher.register_controller(CONTROLLER_ID, ControllerMode.FILM_STRIP)

        handler._track_controller_mode_change(CONTROLLER_ID, ControllerMode.CANVAS)

        assert editor.controller_position_operation_tracker.mode_changes == [
            (CONTROLLER_ID, 'film_strip', 'canvas'),
        ]

    def test_nothing_is_recorded_while_applying_undo(self):
        """A mode change made by undo/redo itself is not recorded again."""
        handler, editor = _make_handler()
        editor.mode_switcher.register_controller(CONTROLLER_ID, ControllerMode.FILM_STRIP)
        # The editor's flag, which undo and redo set (BUGS.md #178 item 22)
        editor.applying_undo_redo = True

        handler._track_controller_mode_change(CONTROLLER_ID, ControllerMode.CANVAS)

        assert editor.controller_position_operation_tracker.mode_changes == []

    def test_nothing_is_recorded_without_a_tracker(self):
        """An editor without a position tracker records nothing."""
        handler, editor = _make_handler()
        tracker = editor.controller_position_operation_tracker
        del editor.controller_position_operation_tracker
        editor.mode_switcher.register_controller(CONTROLLER_ID, ControllerMode.FILM_STRIP)

        handler._track_controller_mode_change(CONTROLLER_ID, ControllerMode.CANVAS)

        assert tracker.mode_changes == []

    def test_nothing_is_recorded_for_an_unregistered_controller(self):
        """A controller without a mode has no old mode to record."""
        handler, editor = _make_handler()

        handler._track_controller_mode_change(CONTROLLER_ID, ControllerMode.CANVAS)

        assert editor.controller_position_operation_tracker.mode_changes == []


class TestStickAxisMotion:
    """The (currently disabled) left stick handling: deadzone, cooldown and direction."""

    @staticmethod
    def _axis_event(*, axis: int, value: int) -> HashableEvent:
        """Return a controller axis event.

        Returns:
            The event.

        """
        return HashableEvent(
            pygame.CONTROLLERAXISMOTION, instance_id=INSTANCE_ID, axis=axis, value=value
        )

    def test_ignored_while_controller_selection_is_inactive(self):
        """Without an active controller selection the stick changes no axis state."""
        handler, _editor = _make_handler()

        handler._handle_stick_axis_motion(
            self._axis_event(axis=pygame.CONTROLLER_AXIS_LEFTX, value=500),
        )

        assert handler._controller_axis_last_values == {}

    @pytest.mark.parametrize('axis', [pygame.CONTROLLER_AXIS_LEFTX, pygame.CONTROLLER_AXIS_LEFTY])
    def test_a_value_at_the_threshold_is_remembered(self, axis):
        """A value exactly at the threshold passes the deadzone and is remembered."""
        handler, _editor = _make_handler()
        handler.controller_selection_active = True  # type: ignore[attr-defined]

        handler._handle_stick_axis_motion(self._axis_event(axis=axis, value=500))

        assert handler._controller_axis_last_values[axis] == 500  # type: ignore[index]

    @pytest.mark.parametrize('axis', [pygame.CONTROLLER_AXIS_LEFTX, pygame.CONTROLLER_AXIS_LEFTY])
    @pytest.mark.parametrize('value', [-20000, 20000])
    def test_a_full_push_is_disabled(self, axis, value):
        """A full push in either direction is left to the multi-controller system."""
        handler, _editor = _make_handler()
        handler.controller_selection_active = True  # type: ignore[attr-defined]

        handler._handle_stick_axis_motion(self._axis_event(axis=axis, value=value))

        assert axis not in handler._controller_axis_last_values

    def test_the_deadzone_resets_the_axis(self):
        """A value inside the deadzone clears the axis's last value and cooldown."""
        handler, _editor = _make_handler()
        handler.controller_selection_active = True  # type: ignore[attr-defined]
        axis = pygame.CONTROLLER_AXIS_LEFTX
        handler._controller_axis_last_values[axis] = 500  # type: ignore[index]

        handler._handle_stick_axis_motion(self._axis_event(axis=axis, value=100))

        assert handler._controller_axis_last_values[axis] == 0  # type: ignore[index]
        assert handler._controller_axis_cooldown[axis] == float('-inf')  # type: ignore[index]

    def test_a_direction_change_starts_a_cooldown(self):
        """Reversing direction starts a cooldown, and the axis ignores input until it ends."""
        handler, _editor = _make_handler()
        handler.controller_selection_active = True  # type: ignore[attr-defined]
        axis = pygame.CONTROLLER_AXIS_LEFTY
        handler._controller_axis_last_values[axis] = 500  # type: ignore[index]

        handler._handle_stick_axis_motion(self._axis_event(axis=axis, value=-500))
        assert handler._controller_axis_cooldown[axis] == 0.0  # type: ignore[index]
        assert handler._controller_axis_last_values[axis] == -500  # type: ignore[index]

        handler._handle_stick_axis_motion(self._axis_event(axis=axis, value=500))
        assert handler._controller_axis_last_values[axis] == -500  # type: ignore[index]

        advance_frame_clock(seconds=0.25)
        handler._handle_stick_axis_motion(self._axis_event(axis=axis, value=500))
        assert handler._controller_axis_last_values[axis] == 500  # type: ignore[index]
        assert handler._controller_axis_cooldown[axis] == pytest.approx(0.25)  # type: ignore[index]

    def test_other_axes_are_ignored(self):
        """The right stick changes no axis state."""
        handler, _editor = _make_handler()
        handler.controller_selection_active = True  # type: ignore[attr-defined]

        handler._handle_stick_axis_motion(
            self._axis_event(axis=pygame.CONTROLLER_AXIS_RIGHTX, value=500),
        )

        assert handler._controller_axis_last_values == {}


class TestControllerLookup:
    """Finding a controller's info and reading its held buttons."""

    def test_find_controller_info_by_slot(self):
        """The info whose controller id matches the slot is found."""
        handler, editor = _make_handler()
        controller_info = _connect_controller(editor)

        assert handler.find_controller_info(CONTROLLER_ID) is controller_info
        assert handler.find_controller_info(3) is None

    def test_find_controller_info_without_a_manager(self):
        """An editor without a controller manager finds nothing."""
        handler, editor = _make_handler()
        del editor.multi_controller_manager

        assert handler.find_controller_info(CONTROLLER_ID) is None
        assert handler.is_controller_button_held(CONTROLLER_ID, 0) is False
