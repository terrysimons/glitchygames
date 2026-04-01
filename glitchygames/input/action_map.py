"""Input action mapping with optional state tracking.

Maps physical inputs (keyboard keys, controller buttons, analog axes)
to named game actions. Supports two complementary usage modes:

- **Event-driven lookup**: ``get_action(event)`` returns the action name
  for one-shot actions like jump or pause.
- **Frame-based state**: ``is_held(action)``, ``just_pressed(action)``
  for continuous actions like movement.

Usage:
    actions = ActionMap()
    actions.bind('jump', keyboard=pygame.K_SPACE,
                 controller_button=pygame.CONTROLLER_BUTTON_A)
    actions.bind('move_right', keyboard=pygame.K_RIGHT,
                 controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, 0.3))

    # In event handlers:
    actions.handle_event(event)
    action = actions.get_action(event)

    # In dt_tick:
    actions.begin_frame()
    if actions.is_held('move_right'):
        player.move_right()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import pygame

if TYPE_CHECKING:
    from glitchygames.events.base import HashableEvent

log: logging.Logger = logging.getLogger('game.input.action_map')

# SDL2 axis range for normalization
_SDL_AXIS_MAX: float = 32767.0

# Default deadzone for analog sticks (industry standard)
DEFAULT_DEADZONE: float = 0.15


@dataclass(frozen=True)
class Binding:
    """A single physical input mapped to a named action.

    Attributes:
        action: The game action name (e.g. 'jump', 'move_right').
        event_type: The pygame event type (KEYDOWN, CONTROLLERBUTTONDOWN, etc.).
        input_code: The key or button constant.
        instance_id: Controller instance filter (None accepts any controller).

    """

    action: str
    event_type: int
    input_code: int
    instance_id: int | None = None


@dataclass(frozen=True)
class AxisBinding:
    """An analog axis mapped to a named action via threshold.

    The threshold sign encodes direction:
    - Positive threshold (e.g. +0.3): fires when axis >= threshold
    - Negative threshold (e.g. -0.3): fires when axis <= threshold

    Attributes:
        action: The game action name.
        axis: The pygame axis constant (e.g. CONTROLLER_AXIS_LEFTX).
        threshold: The activation threshold (sign encodes direction).
        instance_id: Controller instance filter (None accepts any controller).

    """

    action: str
    axis: int
    threshold: float
    instance_id: int | None = None


class ActionMap:
    """Maps physical inputs to named game actions.

    Provides both stateless event-to-action lookup and optional
    frame-based state tracking for held/pressed/released queries.

    Args:
        deadzone: Analog stick deadzone. Values below this are
            treated as zero. Default 0.15.

    """

    def __init__(
        self,
        deadzone: float = DEFAULT_DEADZONE,
        input_mode: str = 'joystick',
    ) -> None:
        """Initialize the action map.

        Args:
            deadzone: Analog stick deadzone (default 0.15).
            input_mode: Which gamepad event family to bind.
                'joystick' binds JOYBUTTONDOWN/UP and JOYAXISMOTION.
                'controller' binds CONTROLLERBUTTONDOWN/UP and
                CONTROLLERAXISMOTION. Default 'joystick' (pygame-ce).

        """
        self._deadzone = deadzone
        self._input_mode = input_mode

        # Digital bindings: (event_type, input_code) → list of Binding
        self._bindings: dict[tuple[int, int], list[Binding]] = {}

        # Analog axis bindings (small list, iterated on axis events)
        self._axis_bindings: list[AxisBinding] = []

        # Frame-based state tracking
        self._held: set[str] = set()
        self._just_pressed: set[str] = set()
        self._just_released: set[str] = set()
        self._axis_values: dict[str, float] = {}

    # --- Binding API ---

    def bind(  # noqa: PLR0913
        self,
        action: str,
        *,
        keyboard: int | None = None,
        controller_button: int | None = None,
        controller_axis: tuple[int, float] | None = None,
        joystick_button: int | None = None,
        instance_id: int | None = None,
    ) -> None:
        """Bind physical inputs to a named action.

        Multiple inputs can be bound to the same action by calling
        bind() multiple times or by passing multiple keyword arguments.

        Args:
            action: The game action name.
            keyboard: A pygame key constant (e.g. pygame.K_SPACE).
            controller_button: A gamepad button constant. Automatically
                uses the correct event type based on input_mode.
            controller_axis: Tuple of (axis_constant, threshold).
                Threshold sign encodes direction.
            joystick_button: A raw joystick button index. Always binds
                JOYBUTTONDOWN/UP regardless of input_mode. Use for
                non-standard buttons (e.g. DualSense mic mute) that
                only come through the raw joystick API.
            instance_id: Controller instance filter for button/axis
                bindings. None accepts any controller.

        """
        if keyboard is not None:
            self._add_binding(
                Binding(
                    action=action,
                    event_type=pygame.KEYDOWN,
                    input_code=keyboard,
                )
            )
            self._add_binding(
                Binding(
                    action=action,
                    event_type=pygame.KEYUP,
                    input_code=keyboard,
                )
            )

        if controller_button is not None:
            # Register the event family matching the active input mode.
            # 'joystick' → JOYBUTTONDOWN/UP (pygame-ce default)
            # 'controller' → CONTROLLERBUTTONDOWN/UP (SDL Game Controller API)
            if self._input_mode == 'controller':
                down_type = pygame.CONTROLLERBUTTONDOWN
                up_type = pygame.CONTROLLERBUTTONUP
            else:
                down_type = pygame.JOYBUTTONDOWN
                up_type = pygame.JOYBUTTONUP

            self._add_binding(
                Binding(
                    action=action,
                    event_type=down_type,
                    input_code=controller_button,
                    instance_id=instance_id,
                )
            )
            self._add_binding(
                Binding(
                    action=action,
                    event_type=up_type,
                    input_code=controller_button,
                    instance_id=instance_id,
                )
            )

        if controller_axis is not None:
            axis_constant, threshold = controller_axis
            axis_binding = AxisBinding(
                action=action,
                axis=axis_constant,
                threshold=threshold,
                instance_id=instance_id,
            )
            self._axis_bindings.append(axis_binding)

        if joystick_button is not None:
            # Always use JOYBUTTONDOWN/UP regardless of input_mode.
            # For non-standard buttons (mic mute, etc.) that only
            # arrive through the raw joystick API.
            self._add_binding(
                Binding(
                    action=action,
                    event_type=pygame.JOYBUTTONDOWN,
                    input_code=joystick_button,
                    instance_id=instance_id,
                )
            )
            self._add_binding(
                Binding(
                    action=action,
                    event_type=pygame.JOYBUTTONUP,
                    input_code=joystick_button,
                    instance_id=instance_id,
                )
            )

    def unbind(self, action: str) -> None:
        """Remove all bindings for an action.

        Args:
            action: The action name to unbind.

        """
        # Remove digital bindings
        keys_to_remove = [
            key
            for key, bindings in self._bindings.items()
            if all(binding.action == action for binding in bindings)
        ]
        for key in keys_to_remove:
            del self._bindings[key]
        for key in self._bindings:
            self._bindings[key] = [
                binding for binding in self._bindings[key] if binding.action != action
            ]

        # Remove axis bindings
        self._axis_bindings = [
            axis_binding for axis_binding in self._axis_bindings if axis_binding.action != action
        ]

        # Clear state
        self._held.discard(action)
        self._just_pressed.discard(action)
        self._just_released.discard(action)
        self._axis_values.pop(action, None)

    def clear(self) -> None:
        """Remove all bindings and reset all state."""
        self._bindings.clear()
        self._axis_bindings.clear()
        self._held.clear()
        self._just_pressed.clear()
        self._just_released.clear()
        self._axis_values.clear()

    # --- Event-driven lookup ---

    def get_action(self, event: HashableEvent) -> str | None:
        """Get the action name for a raw input event.

        Pure lookup — does not modify state. Returns the first
        matching action, or None if the event has no binding.

        Args:
            event: A HashableEvent from the event system.

        Returns:
            The action name, or None.

        """
        actions = self.get_actions(event)
        return actions[0] if actions else None

    def get_actions(self, event: HashableEvent) -> list[str]:
        """Get all action names matching a raw input event.

        Args:
            event: A HashableEvent from the event system.

        Returns:
            List of matching action names (may be empty).

        """
        input_code = self._extract_input_code(event)
        if input_code is None:
            return []

        key = (event.type, input_code)
        bindings = self._bindings.get(key, [])

        return [
            binding.action
            for binding in bindings
            if self._instance_matches(binding.instance_id, event)
        ]

    # --- State tracking ---

    def handle_event(self, event: HashableEvent) -> None:
        """Feed a raw event into the state tracker.

        Call this in every on_*_event handler to keep held/pressed/
        released state accurate.

        Args:
            event: A HashableEvent from the event system.

        """
        # Handle digital inputs (keyboard + controller/joystick buttons)
        input_code = self._extract_input_code(event)
        if input_code is not None:
            key = (event.type, input_code)
            for binding in self._bindings.get(key, []):
                if not self._instance_matches(binding.instance_id, event):
                    continue

                is_down = event.type in {
                    pygame.KEYDOWN,
                    pygame.CONTROLLERBUTTONDOWN,
                    pygame.JOYBUTTONDOWN,
                }
                if is_down:
                    if binding.action not in self._held:
                        self._just_pressed.add(binding.action)
                    self._held.add(binding.action)
                else:
                    if binding.action in self._held:
                        self._just_released.add(binding.action)
                    self._held.discard(binding.action)

        # Handle analog axis inputs (only the active event family)
        expected_axis_type = (
            pygame.CONTROLLERAXISMOTION
            if self._input_mode == 'controller'
            else pygame.JOYAXISMOTION
        )
        if event.type == expected_axis_type:
            self._handle_axis_event(event)

    def begin_frame(self) -> None:
        """Reset per-frame transient state.

        Call at the start of dt_tick() before querying just_pressed
        or just_released.
        """
        self._just_pressed.clear()
        self._just_released.clear()

    def is_held(self, action: str) -> bool:
        """Check if an action is currently held down.

        Args:
            action: The action name.

        Returns:
            True if any binding for this action is active.

        """
        return action in self._held

    def just_pressed(self, action: str) -> bool:
        """Check if an action was pressed this frame.

        Only True for one frame after the press event. Requires
        begin_frame() to be called each frame.

        Args:
            action: The action name.

        Returns:
            True if the action was pressed since the last begin_frame().

        """
        return action in self._just_pressed

    def just_released(self, action: str) -> bool:
        """Check if an action was released this frame.

        Only True for one frame after the release event.

        Args:
            action: The action name.

        Returns:
            True if the action was released since the last begin_frame().

        """
        return action in self._just_released

    def axis_value(self, action: str) -> float:
        """Get the current analog axis value for an action.

        Returns the deadzone-filtered normalized value (-1.0 to 1.0).
        Returns 0.0 if the action has no axis binding or no data.

        Args:
            action: The action name.

        Returns:
            The analog value after deadzone filtering.

        """
        return self._axis_values.get(action, 0.0)

    # --- Persistence ---

    def to_dict(self) -> dict[str, Any]:
        """Serialize bindings to a dict for SaveManager.

        Only serializes bindings, not runtime state. The dict is
        suitable for JSON or TOML serialization.

        Returns:
            A dict mapping action names to lists of binding dicts.

        """
        result: dict[str, list[dict[str, Any]]] = {}

        # Digital bindings (only DOWN events, UP is derived)
        for bindings in self._bindings.values():
            for binding in bindings:
                if binding.event_type not in {pygame.KEYDOWN, pygame.CONTROLLERBUTTONDOWN}:
                    continue
                if binding.action not in result:
                    result[binding.action] = []
                entry: dict[str, Any] = {
                    'type': pygame.event.event_name(binding.event_type),
                    'code': binding.input_code,
                }
                if binding.instance_id is not None:
                    entry['instance_id'] = binding.instance_id
                result[binding.action].append(entry)

        # Axis bindings
        for axis_binding in self._axis_bindings:
            if axis_binding.action not in result:
                result[axis_binding.action] = []
            entry = {
                'type': 'AxisMotion',
                'axis': axis_binding.axis,
                'threshold': axis_binding.threshold,
            }
            if axis_binding.instance_id is not None:
                entry['instance_id'] = axis_binding.instance_id
            result[axis_binding.action].append(entry)

        return result

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        defaults: ActionMap | None = None,
    ) -> ActionMap:
        """Deserialize bindings from a dict.

        If defaults is provided, actions not in data use the default
        bindings. Actions in data override defaults completely.

        Args:
            data: Binding data from SaveManager/serializer.
            defaults: Optional ActionMap with default bindings.

        Returns:
            A new ActionMap with the loaded bindings.

        """
        action_map = cls()
        loaded_actions: set[str] = set()

        for action_name, binding_list in data.items():
            if not isinstance(binding_list, list):
                continue
            loaded_actions.add(action_name)
            for entry in cast('list[Any]', binding_list):
                if isinstance(entry, dict):
                    cls._load_binding_entry(
                        action_map,
                        action_name,
                        cast('dict[str, Any]', entry),
                    )

        # Merge defaults for actions not in the loaded data
        if defaults is not None:
            cls._merge_defaults(action_map, defaults, loaded_actions)

        return action_map

    @staticmethod
    def _load_binding_entry(
        action_map: ActionMap,
        action_name: str,
        entry: dict[str, Any],
    ) -> None:
        """Load a single binding entry from serialized data.

        Args:
            action_map: The ActionMap to add the binding to.
            action_name: The action this binding belongs to.
            entry: A serialized binding dict.

        """
        event_name_to_type = {
            'KeyDown': pygame.KEYDOWN,
            'ControllerButtonDown': pygame.CONTROLLERBUTTONDOWN,
        }

        binding_type = entry.get('type', '')
        instance_id = entry.get('instance_id')

        if binding_type == 'AxisMotion':
            axis = entry.get('axis')
            threshold = entry.get('threshold')
            if axis is not None and threshold is not None:
                action_map.bind(
                    action_name,
                    controller_axis=(int(axis), float(threshold)),
                    instance_id=instance_id,
                )
            return

        event_type = event_name_to_type.get(binding_type)
        code = entry.get('code')
        if event_type is None or code is None:
            return

        if event_type == pygame.KEYDOWN:
            action_map.bind(action_name, keyboard=int(code))
        elif event_type == pygame.CONTROLLERBUTTONDOWN:
            action_map.bind(
                action_name,
                controller_button=int(code),
                instance_id=instance_id,
            )

    @staticmethod
    def _merge_defaults(
        action_map: ActionMap,
        defaults: ActionMap,
        loaded_actions: set[str],
    ) -> None:
        """Merge default bindings for actions not present in loaded data.

        Args:
            action_map: The ActionMap to merge into.
            defaults: The ActionMap with default bindings.
            loaded_actions: Set of action names already loaded from data.

        """
        for bindings in defaults._bindings.values():
            for binding in bindings:
                if binding.action not in loaded_actions:
                    action_map._add_binding(binding)
        for axis_binding in defaults._axis_bindings:
            if axis_binding.action not in loaded_actions:
                action_map._axis_bindings.append(axis_binding)

    # --- Private helpers ---

    def _add_binding(self, binding: Binding) -> None:
        """Add a binding to the internal lookup table.

        Args:
            binding: The binding to add.

        """
        key = (binding.event_type, binding.input_code)
        self._bindings.setdefault(key, []).append(binding)

    def _extract_input_code(self, event: HashableEvent) -> int | None:
        """Extract the input code from a HashableEvent.

        Args:
            event: The event to extract from.

        Returns:
            The key or button code, or None for unsupported event types.

        """
        if event.type in {pygame.KEYDOWN, pygame.KEYUP}:
            return int(event.key)
        if event.type in {
            pygame.CONTROLLERBUTTONDOWN,
            pygame.CONTROLLERBUTTONUP,
            pygame.JOYBUTTONDOWN,
            pygame.JOYBUTTONUP,
        }:
            return int(event.button)
        return None

    def _instance_matches(self, binding_instance_id: int | None, event: HashableEvent) -> bool:
        """Check if a binding's instance_id filter matches an event.

        Controller events use ``instance_id``, joystick events use
        ``joy``. Both are checked.

        Args:
            binding_instance_id: The binding's filter (None = any).
            event: The event to check.

        Returns:
            True if the instance_id matches or the binding accepts any.

        """
        if binding_instance_id is None:
            return True
        # Controller events use instance_id, joystick events use joy
        event_instance_id = getattr(event, 'instance_id', None)
        if event_instance_id is None:
            event_instance_id = getattr(event, 'joy', None)
        return event_instance_id == binding_instance_id

    def _handle_axis_event(self, event: HashableEvent) -> None:
        """Process a controller axis motion event.

        Normalizes the raw SDL value, applies deadzone, and updates
        held/pressed/released state based on axis thresholds.

        Args:
            event: A CONTROLLERAXISMOTION or JOYAXISMOTION HashableEvent.

        """
        value = float(event.value)

        # Controller axis values are raw SDL ints (-32767 to 32767).
        # Joystick axis values are already normalized floats (-1.0 to 1.0).
        if event.type == pygame.CONTROLLERAXISMOTION:
            raw_value: float = value / _SDL_AXIS_MAX
        else:
            raw_value = value

        # Apply deadzone
        if abs(raw_value) < self._deadzone:
            raw_value = 0.0

        for axis_binding in self._axis_bindings:
            if axis_binding.axis != event.axis:
                continue
            if not self._instance_matches(axis_binding.instance_id, event):
                continue

            # Store filtered value
            self._axis_values[axis_binding.action] = raw_value

            # Digital threshold check
            was_active = axis_binding.action in self._held
            if axis_binding.threshold > 0:
                is_active = raw_value >= axis_binding.threshold
            else:
                is_active = raw_value <= axis_binding.threshold

            if is_active and not was_active:
                self._held.add(axis_binding.action)
                self._just_pressed.add(axis_binding.action)
            elif not is_active and was_active:
                self._held.discard(axis_binding.action)
                self._just_released.add(axis_binding.action)
