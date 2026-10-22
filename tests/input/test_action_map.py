"""Tests for ActionMap input action mapping."""

from __future__ import annotations

import pygame
import pytest

from glitchygames.events.base import HashableEvent
from glitchygames.input.action_map import ActionMap
from glitchygames.testing.keys import qwerty_scancode


def _key_down(key: int) -> HashableEvent:
    """Create a KEYDOWN HashableEvent."""
    return HashableEvent(type=pygame.KEYDOWN, key=key, mod=0, unicode='')


def _key_up(key: int) -> HashableEvent:
    """Create a KEYUP HashableEvent."""
    return HashableEvent(type=pygame.KEYUP, key=key, mod=0)


def _button_down(button: int, instance_id: int = 0) -> HashableEvent:
    """Create a CONTROLLERBUTTONDOWN HashableEvent."""
    return HashableEvent(
        type=pygame.CONTROLLERBUTTONDOWN,
        button=button,
        instance_id=instance_id,
    )


def _button_up(button: int, instance_id: int = 0) -> HashableEvent:
    """Create a CONTROLLERBUTTONUP HashableEvent."""
    return HashableEvent(
        type=pygame.CONTROLLERBUTTONUP,
        button=button,
        instance_id=instance_id,
    )


def _joy_button_down(button: int, joy: int = 0) -> HashableEvent:
    """Create a JOYBUTTONDOWN HashableEvent."""
    return HashableEvent(
        type=pygame.JOYBUTTONDOWN,
        button=button,
        joy=joy,
    )


def _joy_button_up(button: int, joy: int = 0) -> HashableEvent:
    """Create a JOYBUTTONUP HashableEvent."""
    return HashableEvent(
        type=pygame.JOYBUTTONUP,
        button=button,
        joy=joy,
    )


def _axis_motion(axis: int, value: int, instance_id: int = 0) -> HashableEvent:
    """Create a CONTROLLERAXISMOTION HashableEvent.

    Args:
        axis: The axis constant.
        value: Raw SDL value (-32767 to 32767).
        instance_id: Controller instance.

    """
    return HashableEvent(
        type=pygame.CONTROLLERAXISMOTION,
        axis=axis,
        value=value,
        instance_id=instance_id,
    )


def _joy_axis_motion(axis: int, value: float, joy: int = 0) -> HashableEvent:
    """Create a JOYAXISMOTION HashableEvent.

    Args:
        axis: The axis constant.
        value: Normalized float (-1.0 to 1.0).
        joy: Joystick instance.

    """
    return HashableEvent(
        type=pygame.JOYAXISMOTION,
        axis=axis,
        value=value,
        joy=joy,
    )


class TestBasicLookup:
    """Tests for stateless event-to-action lookup."""

    def test_keyboard_binding_returns_action(self) -> None:
        """Bound keyboard key returns the action name."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        assert actions.get_action(_key_down(pygame.K_SPACE)) == 'jump'

    def test_controller_button_returns_action(self) -> None:
        """Bound controller button returns the action name."""
        actions = ActionMap(input_mode='controller')
        actions.bind('jump', controller_button=pygame.CONTROLLER_BUTTON_A)
        assert actions.get_action(_button_down(pygame.CONTROLLER_BUTTON_A)) == 'jump'

    def test_joystick_button_returns_action(self) -> None:
        """Bound joystick button returns the action name (default mode)."""
        actions = ActionMap(input_mode='joystick')
        actions.bind('jump', controller_button=pygame.CONTROLLER_BUTTON_A)
        assert actions.get_action(_joy_button_down(pygame.CONTROLLER_BUTTON_A)) == 'jump'

    def test_unbound_event_returns_none(self) -> None:
        """Unbound event returns None."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        assert actions.get_action(_key_down(pygame.K_RETURN)) is None

    def test_multiple_bindings_same_action(self) -> None:
        """Multiple keys can map to the same action."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        actions.bind('jump', keyboard=pygame.K_UP)
        assert actions.get_action(_key_down(pygame.K_SPACE)) == 'jump'
        assert actions.get_action(_key_down(pygame.K_UP)) == 'jump'

    def test_keyboard_and_controller_same_action(self) -> None:
        """Keyboard and controller can both map to the same action."""
        actions = ActionMap(input_mode='controller')
        actions.bind('jump', keyboard=pygame.K_SPACE, controller_button=pygame.CONTROLLER_BUTTON_A)
        assert actions.get_action(_key_down(pygame.K_SPACE)) == 'jump'
        assert actions.get_action(_button_down(pygame.CONTROLLER_BUTTON_A)) == 'jump'

    def test_get_actions_returns_all(self) -> None:
        """get_actions returns all matching action names."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        actions.bind('confirm', keyboard=pygame.K_SPACE)
        result = actions.get_actions(_key_down(pygame.K_SPACE))
        assert 'jump' in result
        assert 'confirm' in result

    def test_mouse_event_ignored(self) -> None:
        """Non-input events return None without error."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        mouse_event = HashableEvent(type=pygame.MOUSEMOTION, pos=(100, 200), rel=(1, 0))
        assert actions.get_action(mouse_event) is None

    def test_input_mode_determines_event_family(self) -> None:
        """Controller mode binds CONTROLLERBUTTONDOWN, joystick mode binds JOYBUTTONDOWN."""
        ctrl = ActionMap(input_mode='controller')
        ctrl.bind('jump', controller_button=pygame.CONTROLLER_BUTTON_A)
        # Controller event matches, joystick event does not
        assert ctrl.get_action(_button_down(pygame.CONTROLLER_BUTTON_A)) == 'jump'
        assert ctrl.get_action(_joy_button_down(pygame.CONTROLLER_BUTTON_A)) is None

        joy = ActionMap(input_mode='joystick')
        joy.bind('jump', controller_button=pygame.CONTROLLER_BUTTON_A)
        # Joystick event matches, controller event does not
        assert joy.get_action(_joy_button_down(pygame.CONTROLLER_BUTTON_A)) == 'jump'
        assert joy.get_action(_button_down(pygame.CONTROLLER_BUTTON_A)) is None


class TestStateTracking:
    """Tests for frame-based held/pressed/released state."""

    def test_just_pressed_on_key_down(self) -> None:
        """just_pressed is True after handling a key down event."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        actions.handle_event(_key_down(pygame.K_SPACE))
        assert actions.just_pressed('jump') is True

    def test_just_pressed_clears_after_begin_frame(self) -> None:
        """just_pressed is False after begin_frame."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        actions.handle_event(_key_down(pygame.K_SPACE))
        actions.begin_frame()
        assert actions.just_pressed('jump') is False

    def test_is_held_while_down(self) -> None:
        """is_held is True while the key is held down."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        actions.handle_event(_key_down(pygame.K_SPACE))
        assert actions.is_held('jump') is True

    def test_is_held_false_after_release(self) -> None:
        """is_held is False after key release."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        actions.handle_event(_key_down(pygame.K_SPACE))
        actions.handle_event(_key_up(pygame.K_SPACE))
        assert actions.is_held('jump') is False

    def test_just_released_on_key_up(self) -> None:
        """just_released is True after releasing a held key."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        actions.handle_event(_key_down(pygame.K_SPACE))
        actions.begin_frame()
        actions.handle_event(_key_up(pygame.K_SPACE))
        assert actions.just_released('jump') is True

    def test_controller_state_tracking(self) -> None:
        """State tracking works for controller buttons too."""
        actions = ActionMap(input_mode='controller')
        actions.bind('jump', controller_button=pygame.CONTROLLER_BUTTON_A)
        actions.handle_event(_button_down(pygame.CONTROLLER_BUTTON_A))
        assert actions.is_held('jump') is True
        assert actions.just_pressed('jump') is True
        actions.begin_frame()
        actions.handle_event(_button_up(pygame.CONTROLLER_BUTTON_A))
        assert actions.is_held('jump') is False
        assert actions.just_released('jump') is True

    def test_joystick_state_tracking(self) -> None:
        """State tracking works for joystick buttons (default mode)."""
        actions = ActionMap(input_mode='joystick')
        actions.bind('jump', controller_button=pygame.CONTROLLER_BUTTON_A)
        actions.handle_event(_joy_button_down(pygame.CONTROLLER_BUTTON_A))
        assert actions.is_held('jump') is True
        assert actions.just_pressed('jump') is True
        actions.begin_frame()
        actions.handle_event(_joy_button_up(pygame.CONTROLLER_BUTTON_A))
        assert actions.is_held('jump') is False
        assert actions.just_released('jump') is True

    def test_repeated_keydown_no_double_press(self) -> None:
        """OS key repeat does not re-trigger just_pressed."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        actions.handle_event(_key_down(pygame.K_SPACE))
        actions.begin_frame()
        # OS sends another KEYDOWN while held
        actions.handle_event(_key_down(pygame.K_SPACE))
        assert actions.just_pressed('jump') is False
        assert actions.is_held('jump') is True

    def test_is_held_persists_across_frames(self) -> None:
        """is_held stays True across multiple frames without release."""
        actions = ActionMap()
        actions.bind('run', keyboard=pygame.K_RIGHT)
        actions.handle_event(_key_down(pygame.K_RIGHT))
        actions.begin_frame()
        assert actions.is_held('run') is True
        actions.begin_frame()
        assert actions.is_held('run') is True


class TestControllerAxisHandling:
    """Tests for controller-mode analog axis to digital action conversion."""

    def test_axis_above_positive_threshold(self) -> None:
        """Axis value above positive threshold activates the action."""
        actions = ActionMap(input_mode='controller')
        actions.bind('move_right', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, 0.3))
        # Value 20000/32767 ≈ 0.61, above threshold
        actions.handle_event(_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 20000))
        assert actions.is_held('move_right') is True

    def test_axis_below_positive_threshold(self) -> None:
        """Axis value below positive threshold does not activate."""
        actions = ActionMap(input_mode='controller')
        actions.bind('move_right', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, 0.3))
        # Value 5000/32767 ≈ 0.15, below threshold
        actions.handle_event(_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 5000))
        assert actions.is_held('move_right') is False

    def test_negative_threshold(self) -> None:
        """Negative threshold detects negative axis direction."""
        actions = ActionMap(input_mode='controller')
        actions.bind('move_left', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, -0.3))
        actions.handle_event(_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, -20000))
        assert actions.is_held('move_left') is True

    def test_deadzone_filters_small_values(self) -> None:
        """Values below deadzone are treated as zero."""
        actions = ActionMap(deadzone=0.15, input_mode='controller')
        actions.bind('move_right', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, 0.3))
        # Value 3000/32767 ≈ 0.09, below deadzone
        actions.handle_event(_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 3000))
        assert actions.axis_value('move_right') == 0.0

    def test_axis_value_returns_normalized(self) -> None:
        """axis_value returns the deadzone-filtered normalized float."""
        actions = ActionMap(input_mode='controller')
        actions.bind('move_right', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, 0.3))
        actions.handle_event(_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 20000))
        value = actions.axis_value('move_right')
        assert 0.5 < value < 0.7  # 20000/32767 ≈ 0.61

    def test_axis_release_on_return_to_center(self) -> None:
        """Action deactivates when axis returns below threshold."""
        actions = ActionMap(input_mode='controller')
        actions.bind('move_right', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, 0.3))
        actions.handle_event(_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 20000))
        assert actions.is_held('move_right') is True
        actions.begin_frame()
        actions.handle_event(_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 0))
        assert actions.is_held('move_right') is False
        assert actions.just_released('move_right') is True


class TestJoystickAxisHandling:
    """Tests for joystick-mode analog axis to digital action conversion."""

    def test_joystick_axis_above_threshold(self) -> None:
        """Joystick axis above threshold activates the action."""
        actions = ActionMap(input_mode='joystick')
        actions.bind('move_right', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, 0.3))
        actions.handle_event(_joy_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 0.7))
        assert actions.is_held('move_right') is True

    def test_joystick_axis_value_is_float(self) -> None:
        """Joystick axis values are already -1.0 to 1.0 (no SDL normalization)."""
        actions = ActionMap(input_mode='joystick')
        actions.bind('move_right', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, 0.3))
        actions.handle_event(_joy_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 0.7))
        value = actions.axis_value('move_right')
        assert 0.6 < value < 0.8

    def test_joystick_axis_negative_threshold(self) -> None:
        """Joystick negative threshold detects negative direction."""
        actions = ActionMap(input_mode='joystick')
        actions.bind('move_left', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, -0.3))
        actions.handle_event(_joy_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, -0.6))
        assert actions.is_held('move_left') is True

    def test_joystick_axis_deadzone(self) -> None:
        """Joystick values below deadzone are treated as zero."""
        actions = ActionMap(deadzone=0.15, input_mode='joystick')
        actions.bind('move_right', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, 0.3))
        actions.handle_event(_joy_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 0.1))
        assert actions.axis_value('move_right') == 0.0
        assert actions.is_held('move_right') is False

    def test_joystick_axis_release_on_return_to_center(self) -> None:
        """Joystick action deactivates when axis returns to center."""
        actions = ActionMap(input_mode='joystick')
        actions.bind('move_right', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, 0.3))
        actions.handle_event(_joy_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 0.7))
        assert actions.is_held('move_right') is True
        actions.begin_frame()
        actions.handle_event(_joy_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 0.0))
        assert actions.is_held('move_right') is False
        assert actions.just_released('move_right') is True


class TestMultiController:
    """Tests for multi-controller instance filtering."""

    def test_instance_id_accepts_matching(self) -> None:
        """Binding with instance_id accepts matching controller."""
        actions = ActionMap(input_mode='controller')
        actions.bind('jump', controller_button=pygame.CONTROLLER_BUTTON_A, instance_id=0)
        assert actions.get_action(_button_down(pygame.CONTROLLER_BUTTON_A, instance_id=0)) == 'jump'

    def test_instance_id_rejects_nonmatching(self) -> None:
        """Binding with instance_id rejects non-matching controller."""
        actions = ActionMap(input_mode='controller')
        actions.bind('jump', controller_button=pygame.CONTROLLER_BUTTON_A, instance_id=0)
        assert actions.get_action(_button_down(pygame.CONTROLLER_BUTTON_A, instance_id=1)) is None

    def test_none_instance_id_accepts_any(self) -> None:
        """Binding with no instance_id accepts any controller."""
        actions = ActionMap(input_mode='controller')
        actions.bind('jump', controller_button=pygame.CONTROLLER_BUTTON_A)
        assert actions.get_action(_button_down(pygame.CONTROLLER_BUTTON_A, instance_id=0)) == 'jump'
        assert actions.get_action(_button_down(pygame.CONTROLLER_BUTTON_A, instance_id=1)) == 'jump'

    def test_separate_maps_per_player(self) -> None:
        """Separate ActionMaps track state independently per player."""
        p1 = ActionMap(input_mode='controller')
        p1.bind('up', controller_button=pygame.CONTROLLER_BUTTON_DPAD_UP, instance_id=0)
        p2 = ActionMap(input_mode='controller')
        p2.bind('up', controller_button=pygame.CONTROLLER_BUTTON_DPAD_UP, instance_id=1)

        event_p1 = _button_down(pygame.CONTROLLER_BUTTON_DPAD_UP, instance_id=0)
        p1.handle_event(event_p1)
        p2.handle_event(event_p1)

        assert p1.is_held('up') is True
        assert p2.is_held('up') is False

    def test_joystick_instance_uses_joy_attr(self) -> None:
        """Joystick events use event.joy for instance matching."""
        actions = ActionMap(input_mode='joystick')
        actions.bind('up', controller_button=pygame.CONTROLLER_BUTTON_DPAD_UP, instance_id=0)
        assert actions.get_action(_joy_button_down(pygame.CONTROLLER_BUTTON_DPAD_UP, joy=0)) == 'up'
        assert actions.get_action(_joy_button_down(pygame.CONTROLLER_BUTTON_DPAD_UP, joy=1)) is None

    def test_joystick_separate_maps_state_tracking(self) -> None:
        """Joystick per-player ActionMaps track held state independently."""
        p1 = ActionMap(input_mode='joystick')
        p1.bind('up', controller_button=pygame.CONTROLLER_BUTTON_DPAD_UP, instance_id=0)
        p2 = ActionMap(input_mode='joystick')
        p2.bind('up', controller_button=pygame.CONTROLLER_BUTTON_DPAD_UP, instance_id=1)

        event_p1 = _joy_button_down(pygame.CONTROLLER_BUTTON_DPAD_UP, joy=0)
        p1.handle_event(event_p1)
        p2.handle_event(event_p1)

        assert p1.is_held('up') is True
        assert p2.is_held('up') is False


class TestModeExclusivity:
    """Verify each input_mode only responds to its own event family."""

    def test_controller_mode_ignores_joystick_state(self) -> None:
        """Controller mode handle_event ignores JOYBUTTONDOWN."""
        actions = ActionMap(input_mode='controller')
        actions.bind('jump', controller_button=pygame.CONTROLLER_BUTTON_A)
        actions.handle_event(_joy_button_down(pygame.CONTROLLER_BUTTON_A))
        assert actions.is_held('jump') is False

    def test_joystick_mode_ignores_controller_state(self) -> None:
        """Joystick mode handle_event ignores CONTROLLERBUTTONDOWN."""
        actions = ActionMap(input_mode='joystick')
        actions.bind('jump', controller_button=pygame.CONTROLLER_BUTTON_A)
        actions.handle_event(_button_down(pygame.CONTROLLER_BUTTON_A))
        assert actions.is_held('jump') is False

    def test_controller_mode_ignores_joystick_axis(self) -> None:
        """Controller mode ignores JOYAXISMOTION events."""
        actions = ActionMap(input_mode='controller')
        actions.bind('move_right', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, 0.3))
        actions.handle_event(_joy_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 0.7))
        assert actions.is_held('move_right') is False

    def test_joystick_mode_ignores_controller_axis(self) -> None:
        """Joystick mode ignores CONTROLLERAXISMOTION events."""
        actions = ActionMap(input_mode='joystick')
        actions.bind('move_right', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, 0.3))
        actions.handle_event(_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 20000))
        assert actions.is_held('move_right') is False


class TestKeyboardGamepadCoexistence:
    """Verify keyboard and gamepad bindings work together in both modes."""

    def test_keyboard_and_joystick_coexist(self) -> None:
        """Keyboard and joystick bindings both work in joystick mode."""
        actions = ActionMap(input_mode='joystick')
        actions.bind('jump', keyboard=pygame.K_SPACE, controller_button=pygame.CONTROLLER_BUTTON_A)

        # Keyboard works
        actions.handle_event(_key_down(pygame.K_SPACE))
        assert actions.is_held('jump') is True
        actions.handle_event(_key_up(pygame.K_SPACE))
        assert actions.is_held('jump') is False

        # Joystick button works
        actions.handle_event(_joy_button_down(pygame.CONTROLLER_BUTTON_A))
        assert actions.is_held('jump') is True
        actions.handle_event(_joy_button_up(pygame.CONTROLLER_BUTTON_A))
        assert actions.is_held('jump') is False

    def test_keyboard_and_controller_coexist(self) -> None:
        """Keyboard and controller bindings both work in controller mode."""
        actions = ActionMap(input_mode='controller')
        actions.bind('jump', keyboard=pygame.K_SPACE, controller_button=pygame.CONTROLLER_BUTTON_A)

        # Keyboard works
        actions.handle_event(_key_down(pygame.K_SPACE))
        assert actions.is_held('jump') is True
        actions.handle_event(_key_up(pygame.K_SPACE))
        assert actions.is_held('jump') is False

        # Controller button works
        actions.handle_event(_button_down(pygame.CONTROLLER_BUTTON_A))
        assert actions.is_held('jump') is True
        actions.handle_event(_button_up(pygame.CONTROLLER_BUTTON_A))
        assert actions.is_held('jump') is False

    def test_keyboard_always_works_regardless_of_mode(self) -> None:
        """Keyboard bindings use KEYDOWN/KEYUP in both modes."""
        for mode in ('joystick', 'controller'):
            actions = ActionMap(input_mode=mode)
            actions.bind('pause', keyboard=pygame.K_ESCAPE)
            assert actions.get_action(_key_down(pygame.K_ESCAPE)) == 'pause'


class TestUnbindAndClear:
    """Tests for unbind and clear operations."""

    def test_unbind_removes_action(self) -> None:
        """Unbind removes all bindings for an action."""
        actions = ActionMap(input_mode='controller')
        actions.bind('jump', keyboard=pygame.K_SPACE, controller_button=pygame.CONTROLLER_BUTTON_A)
        actions.unbind('jump')
        assert actions.get_action(_key_down(pygame.K_SPACE)) is None
        assert actions.get_action(_button_down(pygame.CONTROLLER_BUTTON_A)) is None

    def test_clear_removes_everything(self) -> None:
        """Clear removes all bindings and state."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        actions.bind('run', keyboard=pygame.K_RIGHT)
        actions.handle_event(_key_down(pygame.K_SPACE))
        actions.clear()
        assert actions.get_action(_key_down(pygame.K_SPACE)) is None
        assert actions.is_held('jump') is False


class TestPersistence:
    """Tests for serialization and deserialization."""

    def test_to_dict_round_trip(self) -> None:
        """Bindings survive a to_dict → from_dict round trip."""
        original = ActionMap(input_mode='controller')
        original.bind('jump', keyboard=pygame.K_SPACE)
        original.bind('jump', controller_button=pygame.CONTROLLER_BUTTON_A)

        data = original.to_dict()
        restored = ActionMap.from_dict(data)

        assert restored.get_action(_key_down(pygame.K_SPACE)) == 'jump'
        # Restored default input_mode is 'joystick', so controller event won't match
        # but joystick equivalent will
        assert restored.get_action(_joy_button_down(pygame.CONTROLLER_BUTTON_A)) == 'jump'

    def test_from_dict_with_defaults(self) -> None:
        """File data overrides defaults; missing actions use defaults."""
        defaults = ActionMap()
        defaults.bind('jump', keyboard=pygame.K_SPACE)
        defaults.bind('run', keyboard=pygame.K_RIGHT)

        # File only overrides 'jump' to K_RETURN
        file_data: dict[str, list[dict[str, object]]] = {
            'jump': [{'type': 'KeyDown', 'code': pygame.K_RETURN}],
        }
        restored = ActionMap.from_dict(file_data, defaults=defaults)

        # Jump is overridden
        assert restored.get_action(_key_down(pygame.K_RETURN)) == 'jump'
        assert restored.get_action(_key_down(pygame.K_SPACE)) is None
        # Run kept from defaults
        assert restored.get_action(_key_down(pygame.K_RIGHT)) == 'run'

    def test_axis_binding_round_trip(self) -> None:
        """Axis bindings survive serialization."""
        original = ActionMap(input_mode='controller')
        original.bind('move_right', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, 0.3))

        data = original.to_dict()
        restored = ActionMap.from_dict(data)

        # Restored uses default joystick mode, so feed a joystick axis event
        restored.handle_event(_joy_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 0.7))
        assert restored.is_held('move_right') is True


def _positional_key_down(*, key: int, scancode: int) -> HashableEvent:
    """Create a KEYDOWN HashableEvent with the physical key position it came from."""
    return HashableEvent(type=pygame.KEYDOWN, key=key, scancode=scancode, mod=0, unicode='')


def _positional_key_up(*, key: int, scancode: int) -> HashableEvent:
    """Create a KEYUP HashableEvent with the physical key position it came from."""
    return HashableEvent(type=pygame.KEYUP, key=key, scancode=scancode, mod=0)


class TestScancodeBindings:
    """scancode= binds a physical key position, the same place on every keyboard layout."""

    def test_a_position_matches_whatever_the_layout_calls_the_key(self) -> None:
        """On AZERTY the key in QWERTY's A position reports K_q; its scancode is still A's."""
        actions = ActionMap()
        actions.bind('move_left', scancode=pygame.KSCAN_A)
        azerty_press = _positional_key_down(key=pygame.K_q, scancode=pygame.KSCAN_A)
        assert actions.get_action(azerty_press) == 'move_left'

    def test_a_key_code_binding_follows_the_layout_instead(self) -> None:
        """keyboard= stays the layout's key (mnemonic keys: P for pause)."""
        actions = ActionMap()
        actions.bind('move_left', keyboard=pygame.K_a)
        azerty_press = _positional_key_down(key=pygame.K_q, scancode=pygame.KSCAN_A)
        assert actions.get_action(azerty_press) is None

    def test_a_scancode_is_never_matched_against_a_key_code(self) -> None:
        """The two kinds of key binding are looked up apart (KSCAN_A and a key code can be 4)."""
        actions = ActionMap()
        actions.bind('move_left', scancode=pygame.KSCAN_A)
        other_key = _positional_key_down(key=pygame.KSCAN_A, scancode=pygame.KSCAN_B)
        assert actions.get_action(other_key) is None

    def test_an_event_without_a_scancode_matches_no_position(self) -> None:
        actions = ActionMap()
        actions.bind('move_left', scancode=pygame.KSCAN_A)
        assert actions.get_action(_key_down(pygame.K_a)) is None

    def test_held_pressed_and_released_by_position(self) -> None:
        actions = ActionMap()
        actions.bind('jump', scancode=pygame.KSCAN_SPACE)
        actions.handle_event(_positional_key_down(key=pygame.K_SPACE, scancode=pygame.KSCAN_SPACE))
        assert actions.is_held('jump') is True
        assert actions.just_pressed('jump') is True
        actions.begin_frame()
        actions.handle_event(_positional_key_up(key=pygame.K_SPACE, scancode=pygame.KSCAN_SPACE))
        assert actions.is_held('jump') is False
        assert actions.just_released('jump') is True

    def test_a_position_and_a_key_code_can_share_an_action(self) -> None:
        actions = ActionMap()
        actions.bind('move_left', scancode=pygame.KSCAN_A, keyboard=pygame.K_LEFT)
        assert actions.get_actions(
            _positional_key_down(key=pygame.K_LEFT, scancode=pygame.KSCAN_LEFT)
        ) == ['move_left']
        assert actions.get_actions(
            _positional_key_down(key=pygame.K_q, scancode=pygame.KSCAN_A)
        ) == ['move_left']

    def test_unbind_and_clear_remove_positions(self) -> None:
        press = _positional_key_down(key=pygame.K_a, scancode=pygame.KSCAN_A)
        actions = ActionMap()
        actions.bind('move_left', scancode=pygame.KSCAN_A)
        actions.unbind('move_left')
        assert actions.get_action(press) is None
        actions.bind('move_left', scancode=pygame.KSCAN_A)
        actions.clear()
        assert actions.get_action(press) is None

    def test_positions_round_trip_through_to_dict(self) -> None:
        original = ActionMap()
        original.bind('move_left', scancode=pygame.KSCAN_A)
        data = original.to_dict()
        assert data == {'move_left': [{'type': 'KeyDown', 'scancode': pygame.KSCAN_A}]}
        restored = ActionMap.from_dict(data)
        press = _positional_key_down(key=pygame.K_q, scancode=pygame.KSCAN_A)
        assert restored.get_action(press) == 'move_left'

    def test_default_positions_fill_actions_the_file_leaves_out(self) -> None:
        defaults = ActionMap()
        defaults.bind('move_left', scancode=pygame.KSCAN_A)
        defaults.bind('jump', scancode=pygame.KSCAN_SPACE)
        file_data: dict[str, list[dict[str, object]]] = {
            'jump': [{'type': 'KeyDown', 'code': pygame.K_RETURN}],
        }
        restored = ActionMap.from_dict(file_data, defaults=defaults)
        assert (
            restored.get_action(_positional_key_down(key=pygame.K_q, scancode=pygame.KSCAN_A))
            == 'move_left'
        )
        assert (
            restored.get_action(
                _positional_key_down(key=pygame.K_SPACE, scancode=pygame.KSCAN_SPACE)
            )
            is None
        )


class TestQwertyScancodes:
    """Fabricated key events carry the US QWERTY position of their key (testing/keys.py)."""

    @pytest.mark.parametrize(
        ('key', 'scancode'),
        [
            (pygame.K_w, pygame.KSCAN_W),
            (pygame.K_s, pygame.KSCAN_S),
            (pygame.K_LSHIFT, pygame.KSCAN_LSHIFT),
            (pygame.K_RIGHT, pygame.KSCAN_RIGHT),
            (pygame.K_ESCAPE, pygame.KSCAN_ESCAPE),
            (pygame.K_SPACE, pygame.KSCAN_SPACE),
            (pygame.K_1, pygame.KSCAN_1),
            (pygame.K_KP_1, pygame.KSCAN_KP_1),
        ],
    )
    def test_a_key_maps_to_its_qwerty_position(self, key, scancode):
        assert qwerty_scancode(key=key) == scancode

    def test_a_key_with_no_position_is_unknown(self):
        """SDL's own answer for a key it cannot place."""
        assert qwerty_scancode(key=-1) == pygame.KSCAN_UNKNOWN

    def test_a_fabricated_press_is_bound_by_its_position(self):
        actions = ActionMap()
        actions.bind('move_left', scancode=pygame.KSCAN_A)
        press = HashableEvent(
            type=pygame.KEYDOWN, key=pygame.K_a, scancode=qwerty_scancode(key=pygame.K_a), mod=0
        )
        assert actions.get_action(press) == 'move_left'
