"""Tests for controller event functionality.

This module tests controller event interfaces, stubs, event handling,
ControllerEventProxy forwarding and routing methods, and
ControllerEventManager initialization.

Controllers are hardware, so the devices door (glitchygames/input/devices.py) serves the
replay stand-ins (``ReplayController``) from a ``ReplayDeviceRegistry``; everything else is
real: the event managers and proxies, real Scenes receiving the events, real events.
"""

import math
import sys
from pathlib import Path
from typing import Any, Self

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.record_golden_traces import (
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    command_line,
)

from glitchygames.events import (
    ControllerEvents,
    ControllerEventStubs,
    HashableEvent,
    UnhandledEventError,
)
from glitchygames.events.controller import ControllerEventManager
from glitchygames.input.devices import (
    CONTROLLER_COUNT_CALL,
    CONTROLLER_KIND,
    IS_CONTROLLER_CALL,
    OPEN_CONTROLLER_CALL,
    DeviceDescriptor,
    EnumerationAnswer,
    ReplayDeviceRegistry,
)
from glitchygames.input.state import InputSnapshot, set_current_input
from glitchygames.live_sources import LiveSources
from glitchygames.scenes import Scene
from glitchygames.sources import install_sources

NO_UNHANDLED_EVENTS_OPTIONS = {'debug_events': False, 'no_unhandled_events': True}

CONTROLLER_NAME = 'Test Controller'


class ControllerRecordingScene(Scene):
    """A real scene that records every controller event it receives, in order."""

    def __init__(self: Self, options: dict[str, Any] | None = None, groups: Any = None) -> None:
        """Create the scene with no events received yet."""
        super().__init__(
            options=dict(NO_UNHANDLED_EVENTS_OPTIONS) if options is None else options,
            groups=groups,
        )
        self.controller_events_received: list[tuple[str, HashableEvent]] = []

    def on_controller_axis_motion_event(self: Self, event: HashableEvent) -> None:
        self.controller_events_received.append(('axis_motion', event))

    def on_controller_button_down_event(self: Self, event: HashableEvent) -> None:
        self.controller_events_received.append(('button_down', event))

    def on_controller_button_up_event(self: Self, event: HashableEvent) -> None:
        self.controller_events_received.append(('button_up', event))

    def on_controller_device_added_event(self: Self, event: HashableEvent) -> None:
        self.controller_events_received.append(('device_added', event))

    def on_controller_device_remapped_event(self: Self, event: HashableEvent) -> None:
        self.controller_events_received.append(('device_remapped', event))

    def on_controller_device_removed_event(self: Self, event: HashableEvent) -> None:
        self.controller_events_received.append(('device_removed', event))

    def on_controller_touchpad_down_event(self: Self, event: HashableEvent) -> None:
        self.controller_events_received.append(('touchpad_down', event))

    def on_controller_touchpad_motion_event(self: Self, event: HashableEvent) -> None:
        self.controller_events_received.append(('touchpad_motion', event))

    def on_controller_touchpad_up_event(self: Self, event: HashableEvent) -> None:
        self.controller_events_received.append(('touchpad_up', event))

    def on_controller_sensor_update_event(self: Self, event: HashableEvent) -> None:
        self.controller_events_received.append(('sensor_update', event))


class ReplayDeviceSources(LiveSources):
    """Live doors whose devices are a replay registry's stand-ins (no controller hardware)."""

    def __init__(self: Self, *, registry: ReplayDeviceRegistry) -> None:
        """Create the doors around the registry."""
        super().__init__(random_seed=1)
        self.registry = registry

    def devices(self: Self) -> ReplayDeviceRegistry:  # type: ignore[override]
        return self.registry


class ScriptedBatchSources(ReplayDeviceSources):
    """Replay-device doors whose first pump returns the given batch (the real queue drained)."""

    def __init__(
        self: Self, *, registry: ReplayDeviceRegistry, batch: list[pygame.event.Event]
    ) -> None:
        """Create the doors with the one batch still to pump."""
        super().__init__(registry=registry)
        self.batches = [batch]

    def pump_events(self: Self) -> list[pygame.event.Event]:
        pygame.event.get()  # the real queue is drained and ignored
        return self.batches.pop(0) if self.batches else []


def _controller_descriptor(*, device_index: int, instance_id: int) -> DeviceDescriptor:
    return DeviceDescriptor(
        kind=CONTROLLER_KIND,
        device_index=device_index,
        instance_id=instance_id,
        name=CONTROLLER_NAME,
        guid='test-guid',
        axis_count=6,
        button_count=15,
        hat_count=0,
        ball_count=0,
    )


def _controller_registry(
    *, instance_ids_by_device_index: dict[int, int], counted_controllers: int | None = None
) -> ReplayDeviceRegistry:
    """Build a registry of stand-in controllers.

    Args:
        instance_ids_by_device_index: The recorded controllers (device index -> instance id).
        counted_controllers: How many controllers the count reports (default: all of them;
            0 leaves them to be hot-plugged).

    Returns:
        The registry.

    """
    controller_count = (
        len(instance_ids_by_device_index) if counted_controllers is None else counted_controllers
    )
    answers = [
        EnumerationAnswer(call=CONTROLLER_COUNT_CALL, device_index=None, value=controller_count)
    ]
    answers.extend(
        EnumerationAnswer(call=IS_CONTROLLER_CALL, device_index=device_index, value=True)
        for device_index in range(controller_count)
    )
    return ReplayDeviceRegistry(
        descriptors=[
            _controller_descriptor(device_index=device_index, instance_id=instance_id)
            for device_index, instance_id in instance_ids_by_device_index.items()
        ],
        enumeration_answers=answers,
    )


def _install_controllers(
    *, instance_ids_by_device_index: dict[int, int], counted_controllers: int | None = None
) -> ReplayDeviceRegistry:
    """Install doors whose devices are stand-in controllers.

    Returns:
        The installed registry.

    """
    registry = _controller_registry(
        instance_ids_by_device_index=instance_ids_by_device_index,
        counted_controllers=counted_controllers,
    )
    install_sources(sources=ReplayDeviceSources(registry=registry))
    return registry


def _manager_with_controller() -> tuple[ControllerEventManager, ControllerRecordingScene]:
    """Create a real manager with one stand-in controller (device index 0, instance id 0).

    Returns:
        The manager and the scene it forwards to.

    """
    _install_controllers(instance_ids_by_device_index={0: 0})
    scene = ControllerRecordingScene()
    return ControllerEventManager(game=scene), scene


def _manager_without_controllers() -> tuple[ControllerEventManager, ControllerRecordingScene]:
    """Create a real manager that finds no controllers.

    Returns:
        The manager and the scene it forwards to.

    """
    _install_controllers(instance_ids_by_device_index={})
    scene = ControllerRecordingScene()
    return ControllerEventManager(game=scene), scene


def _received(scene: ControllerRecordingScene) -> list[tuple[str, HashableEvent]]:
    return scene.controller_events_received


class TestControllerEventProxyMethods:
    """Test ControllerEventManager routing to its controller proxies and on to the game."""

    def test_axis_motion_routes_to_controller_proxy(self):
        """Axis motion event should be routed to the correct controller proxy."""
        manager, scene = _manager_with_controller()

        event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=0.5, instance_id=0)
        manager.on_controller_axis_motion_event(event)

        assert _received(scene) == [('axis_motion', event)]
        assert math.isclose(manager.controllers[0]._axes[0], 0.5)

    def test_button_down_routes_to_controller_proxy(self):
        """Button down event should be routed to the correct controller proxy."""
        manager, scene = _manager_with_controller()

        event = HashableEvent(pygame.CONTROLLERBUTTONDOWN, button=0, instance_id=0)
        manager.on_controller_button_down_event(event)

        assert _received(scene) == [('button_down', event)]
        assert manager.controllers[0]._buttons[0] is True

    def test_button_up_routes_to_controller_proxy(self):
        """Button up event should be routed to the correct controller proxy."""
        manager, scene = _manager_with_controller()

        event = HashableEvent(pygame.CONTROLLERBUTTONUP, button=0, instance_id=0)
        manager.on_controller_button_up_event(event)

        assert _received(scene) == [('button_up', event)]
        assert manager.controllers[0]._buttons[0] is False

    def test_device_added_creates_and_routes(self):
        """Device added event should create a new proxy and forward the event."""
        # One controller in the registry, but none counted at start: it is hot-plugged
        _install_controllers(instance_ids_by_device_index={0: 0}, counted_controllers=0)
        scene = ControllerRecordingScene()
        manager = ControllerEventManager(game=scene)
        assert manager.controllers == {}

        event = HashableEvent(pygame.CONTROLLERDEVICEADDED, device_index=0, guid='test-guid')
        manager.on_controller_device_added_event(event)

        assert 0 in manager.controllers
        assert manager.controllers[0].controller.name == CONTROLLER_NAME
        assert _received(scene) == [('device_added', event)]

    def test_device_remapped_routes_to_controller_proxy(self):
        """Device remapped event should be routed to the correct controller proxy."""
        manager, scene = _manager_with_controller()

        # A remapped event carries the instance id (pygame's event docs)
        event = HashableEvent(pygame.CONTROLLERDEVICEREMAPPED, instance_id=0)
        manager.on_controller_device_remapped_event(event)

        assert _received(scene) == [('device_remapped', event)]

    def test_device_removed_routes_and_deletes(self):
        """Device removed event should forward to proxy, then delete it."""
        manager, scene = _manager_with_controller()

        event = HashableEvent(pygame.CONTROLLERDEVICEREMOVED, instance_id=0)
        manager.on_controller_device_removed_event(event)

        assert _received(scene) == [('device_removed', event)]
        assert 0 not in manager.controllers

    def test_device_removed_missing_instance_is_noop(self):
        """Device removed for unknown instance_id should not crash or reach the game."""
        manager, scene = _manager_without_controllers()

        event = HashableEvent(pygame.CONTROLLERDEVICEREMOVED, instance_id=999)
        manager.on_controller_device_removed_event(event)

        assert _received(scene) == []

    def test_touchpad_down_routes_to_controller_proxy(self):
        """Touchpad down event should be routed to the correct controller proxy."""
        manager, scene = _manager_with_controller()

        event = HashableEvent(
            pygame.CONTROLLERTOUCHPADDOWN,
            touchpad=0,
            finger=0,
            x=100,
            y=100,
            instance_id=0,
        )
        manager.on_controller_touchpad_down_event(event)

        assert _received(scene) == [('touchpad_down', event)]

    def test_touchpad_motion_routes_to_controller_proxy(self):
        """Touchpad motion event should be routed to the correct controller proxy."""
        manager, scene = _manager_with_controller()

        event = HashableEvent(
            pygame.CONTROLLERTOUCHPADMOTION,
            touchpad=0,
            finger=0,
            x=100,
            y=100,
            instance_id=0,
        )
        manager.on_controller_touchpad_motion_event(event)

        assert _received(scene) == [('touchpad_motion', event)]

    def test_touchpad_up_routes_to_controller_proxy(self):
        """Touchpad up event should be routed to the correct controller proxy."""
        manager, scene = _manager_with_controller()

        event = HashableEvent(
            pygame.CONTROLLERTOUCHPADUP,
            touchpad=0,
            finger=0,
            x=100,
            y=100,
            instance_id=0,
        )
        manager.on_controller_touchpad_up_event(event)

        assert _received(scene) == [('touchpad_up', event)]


def _create_proxy() -> tuple[Any, ControllerRecordingScene]:
    """Create a real ControllerEventProxy over a stand-in controller.

    Returns:
        Tuple of (proxy, scene).

    """
    _install_controllers(instance_ids_by_device_index={0: 0})
    scene = ControllerRecordingScene()
    proxy = ControllerEventManager.ControllerEventProxy(game=scene, controller_id=0)
    return proxy, scene


class TestControllerEventProxyDirectMethods:
    """Test the ControllerEventProxy methods directly over a stand-in controller."""

    def test_proxy_axis_motion_updates_axes_and_forwards(self):
        """Axis motion should update internal state and forward to game."""
        proxy, scene = _create_proxy()

        event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=12345)
        proxy.on_controller_axis_motion_event(event)

        assert proxy._axes[0] == 12345
        assert _received(scene) == [('axis_motion', event)]

    def test_proxy_button_down_updates_state_and_forwards(self):
        """Button down should set button state to 1 and forward to game."""
        proxy, scene = _create_proxy()

        event = HashableEvent(pygame.CONTROLLERBUTTONDOWN, button=2)
        proxy.on_controller_button_down_event(event)

        assert proxy._buttons[2] == 1
        assert _received(scene) == [('button_down', event)]

    def test_proxy_button_down_negative_button_is_noop(self):
        """Button down with negative button index should return early."""
        proxy, scene = _create_proxy()
        buttons_before = list(proxy._buttons)

        event = HashableEvent(pygame.CONTROLLERBUTTONDOWN, button=-1)
        proxy.on_controller_button_down_event(event)

        assert _received(scene) == []
        assert proxy._buttons == buttons_before

    def test_proxy_button_down_extends_buttons_list(self):
        """Button down with index beyond list should extend storage."""
        proxy, scene = _create_proxy()

        original_length = len(proxy._buttons)
        event = HashableEvent(pygame.CONTROLLERBUTTONDOWN, button=original_length + 5)
        proxy.on_controller_button_down_event(event)

        assert len(proxy._buttons) > original_length
        assert proxy._buttons[original_length + 5] == 1
        assert _received(scene) == [('button_down', event)]

    def test_proxy_button_up_updates_state_and_forwards(self):
        """Button up should set button state to 0 and forward to game."""
        proxy, scene = _create_proxy()

        # First press button down
        proxy._buttons[2] = 1

        event = HashableEvent(pygame.CONTROLLERBUTTONUP, button=2)
        proxy.on_controller_button_up_event(event)

        assert proxy._buttons[2] == 0
        assert _received(scene) == [('button_up', event)]

    def test_proxy_button_up_negative_button_is_noop(self):
        """Button up with negative button index should return early."""
        proxy, scene = _create_proxy()

        event = HashableEvent(pygame.CONTROLLERBUTTONUP, button=-1)
        proxy.on_controller_button_up_event(event)

        assert _received(scene) == []

    def test_proxy_button_up_extends_buttons_list(self):
        """Button up with index beyond list should extend storage."""
        proxy, scene = _create_proxy()

        original_length = len(proxy._buttons)
        event = HashableEvent(pygame.CONTROLLERBUTTONUP, button=original_length + 3)
        proxy.on_controller_button_up_event(event)

        assert len(proxy._buttons) > original_length
        assert proxy._buttons[original_length + 3] == 0
        assert _received(scene) == [('button_up', event)]

    def test_proxy_device_added_forwards(self):
        """Device added should forward to game."""
        proxy, scene = _create_proxy()

        event = HashableEvent(pygame.CONTROLLERDEVICEADDED, device_index=0, guid='test')
        proxy.on_controller_device_added_event(event)

        assert _received(scene) == [('device_added', event)]

    def test_proxy_device_remapped_forwards(self):
        """Device remapped should forward to game."""
        proxy, scene = _create_proxy()

        event = HashableEvent(pygame.CONTROLLERDEVICEREMAPPED, device_index=0)
        proxy.on_controller_device_remapped_event(event)

        assert _received(scene) == [('device_remapped', event)]

    def test_proxy_device_removed_forwards(self):
        """Device removed should forward to game."""
        proxy, scene = _create_proxy()

        event = HashableEvent(pygame.CONTROLLERDEVICEREMOVED, instance_id=0)
        proxy.on_controller_device_removed_event(event)

        assert _received(scene) == [('device_removed', event)]

    def test_proxy_touchpad_down_forwards(self):
        """Touchpad down should forward to game."""
        proxy, scene = _create_proxy()

        event = HashableEvent(pygame.CONTROLLERTOUCHPADDOWN, touchpad=0, finger=0, x=50, y=50)
        proxy.on_controller_touchpad_down_event(event)

        assert _received(scene) == [('touchpad_down', event)]

    def test_proxy_touchpad_motion_forwards(self):
        """Touchpad motion should forward to game."""
        proxy, scene = _create_proxy()

        event = HashableEvent(pygame.CONTROLLERTOUCHPADMOTION, touchpad=0, finger=0, x=60, y=60)
        proxy.on_controller_touchpad_motion_event(event)

        assert _received(scene) == [('touchpad_motion', event)]

    def test_proxy_touchpad_up_forwards(self):
        """Touchpad up should forward to game."""
        proxy, scene = _create_proxy()

        event = HashableEvent(pygame.CONTROLLERTOUCHPADUP, touchpad=0, finger=0, x=70, y=70)
        proxy.on_controller_touchpad_up_event(event)

        assert _received(scene) == [('touchpad_up', event)]

    def test_proxy_str_representation(self):
        """str() should return a multi-line controller info string."""
        proxy, _scene = _create_proxy()

        proxy_class = ControllerEventManager.ControllerEventProxy
        result = str(proxy)
        assert result.splitlines() == [
            f'Controller Name: {CONTROLLER_NAME}',
            '\tController Id: 0',
            '\tController Inited: True',
            f'\tController Axis Count: {len(proxy_class.AXIS)}',
            f'\tController Button Count: {len(proxy_class.BUTTONS)}',
        ]

    def test_proxy_repr(self):
        """repr() should return repr of the underlying controller."""
        proxy, _scene = _create_proxy()

        assert repr(proxy) == repr(proxy.controller)


class TestControllerEventProxyOutputs:
    """The proxy's sensor forwarding and its outputs: rumble and the LED."""

    def test_proxy_sensor_update_forwards(self):
        """A sensor update (gyro/accelerometer) is forwarded to the game."""
        proxy, scene = _create_proxy()

        event = HashableEvent(pygame.CONTROLLERSENSORUPDATE, sensor=1, data=(0.1, 0.2, 0.3))
        proxy.on_controller_sensor_update_event(event)

        assert _received(scene) == [('sensor_update', event)]

    def test_proxy_rumble_reports_whether_it_started(self, mocker):
        """Rumble passes the motor strengths and duration on and returns the device's answer."""
        proxy, _scene = _create_proxy()
        rumble_spy = mocker.spy(proxy.controller, 'rumble')

        # The stand-in accepts the request, as pygame does
        assert proxy.rumble(low_frequency=0.25, high_frequency=0.75, duration=200) is True
        rumble_spy.assert_called_once_with(0.25, 0.75, 200)

        # A device that refuses (no haptics motor running) answers False
        mocker.patch.object(proxy.controller, 'rumble', return_value=False)
        assert proxy.rumble() is False

    @pytest.mark.parametrize('failure', [pygame.error('no haptics'), AttributeError('rumble')])
    def test_proxy_rumble_failure_returns_false(self, mocker, failure):
        """A device without rumble (pygame.error, or no rumble method) answers False."""
        proxy, _scene = _create_proxy()
        mocker.patch.object(proxy.controller, 'rumble', side_effect=failure)

        assert proxy.rumble(low_frequency=1.0, high_frequency=1.0, duration=100) is False

    def test_proxy_stop_rumble_stops_the_device(self, mocker):
        """stop_rumble stops the device's motors."""
        proxy, _scene = _create_proxy()
        stop_spy = mocker.spy(proxy.controller, 'stop_rumble')

        proxy.stop_rumble()

        stop_spy.assert_called_once_with()

    @pytest.mark.parametrize('failure', [pygame.error('no haptics'), AttributeError('stop_rumble')])
    def test_proxy_stop_rumble_failure_is_suppressed(self, mocker, failure):
        """A device that cannot stop rumbling raises nothing to the caller."""
        proxy, _scene = _create_proxy()
        failing_stop = mocker.patch.object(proxy.controller, 'stop_rumble', side_effect=failure)

        proxy.stop_rumble()

        failing_stop.assert_called_once_with()

    def test_proxy_set_led_passes_the_color(self, mocker):
        """set_led sends the color as one (red, green, blue) tuple and returns the answer."""
        proxy, _scene = _create_proxy()
        set_led_spy = mocker.spy(proxy.controller, 'set_led')

        # The stand-in has no LED, so it answers False, as pygame does
        assert proxy.set_led(red=255, green=128, blue=0) is False
        set_led_spy.assert_called_once_with((255, 128, 0))

        # A controller with an LED answers True
        mocker.patch.object(proxy.controller, 'set_led', return_value=True)
        assert proxy.set_led(red=255, green=128, blue=0) is True

    @pytest.mark.parametrize('failure', [pygame.error('no LED'), AttributeError('set_led')])
    def test_proxy_set_led_failure_returns_false(self, mocker, failure):
        """A controller without an LED answers False."""
        proxy, _scene = _create_proxy()
        mocker.patch.object(proxy.controller, 'set_led', side_effect=failure)

        assert proxy.set_led(red=1, green=2, blue=3) is False


class TestControllerEvents:
    """Test ControllerEvents interface functionality, through the real manager."""

    def test_controller_events_interface(self):
        """Test ControllerEvents interface methods."""
        # Test that ControllerEvents has required abstract methods
        assert hasattr(ControllerEvents, 'on_controller_axis_motion_event')
        assert hasattr(ControllerEvents, 'on_controller_button_down_event')
        assert hasattr(ControllerEvents, 'on_controller_button_up_event')
        assert hasattr(ControllerEvents, 'on_controller_device_added_event')
        assert hasattr(ControllerEvents, 'on_controller_device_remapped_event')
        assert hasattr(ControllerEvents, 'on_controller_device_removed_event')
        assert hasattr(ControllerEvents, 'on_controller_touchpad_down_event')
        assert hasattr(ControllerEvents, 'on_controller_touchpad_motion_event')
        assert hasattr(ControllerEvents, 'on_controller_touchpad_up_event')

    def test_controller_event_stubs_implementation(self, mocker):
        """Test ControllerEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = ControllerEventStubs()
        assert hasattr(stub, 'on_controller_axis_motion_event')
        assert hasattr(stub, 'on_controller_button_down_event')
        assert hasattr(stub, 'on_controller_button_up_event')

        # The stub reads the options unhandled_event checks from itself
        stub.options = dict(NO_UNHANDLED_EVENTS_OPTIONS)  # type: ignore[attr-defined]

        event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=0.5)

        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_controller_axis_motion_event(event)

    def test_controller_axis_motion_event(self):
        """Test controller axis motion event handling."""
        manager, scene = _manager_with_controller()

        event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=0.5, instance_id=0)
        manager.on_controller_axis_motion_event(event)

        assert len(_received(scene)) == 1
        assert _received(scene)[0][1].axis == 0
        assert math.isclose(_received(scene)[0][1].value, 0.5)

    def test_controller_button_down_event(self):
        """Test controller button down event handling."""
        manager, scene = _manager_with_controller()

        event = HashableEvent(pygame.CONTROLLERBUTTONDOWN, button=0, instance_id=0)
        manager.on_controller_button_down_event(event)

        assert len(_received(scene)) == 1
        assert _received(scene)[0][1].button == 0

    def test_controller_button_up_event(self):
        """Test controller button up event handling."""
        manager, scene = _manager_with_controller()

        event = HashableEvent(pygame.CONTROLLERBUTTONUP, button=0, instance_id=0)
        manager.on_controller_button_up_event(event)

        assert len(_received(scene)) == 1
        assert _received(scene)[0][1].button == 0

    def test_controller_device_added_event(self):
        """Test controller device added event handling."""
        _install_controllers(instance_ids_by_device_index={0: 0}, counted_controllers=0)
        scene = ControllerRecordingScene()
        manager = ControllerEventManager(game=scene)

        event = HashableEvent(pygame.CONTROLLERDEVICEADDED, device_index=0)
        manager.on_controller_device_added_event(event)

        assert len(_received(scene)) == 1
        assert _received(scene)[0][1].device_index == 0

    def test_controller_device_removed_event(self):
        """Test controller device removed event handling."""
        manager, scene = _manager_with_controller()

        event = HashableEvent(pygame.CONTROLLERDEVICEREMOVED, instance_id=0)
        manager.on_controller_device_removed_event(event)

        assert len(_received(scene)) == 1
        assert _received(scene)[0][1].instance_id == 0

    def test_controller_device_remapped_event(self):
        """Test controller device remapped event handling."""
        manager, scene = _manager_with_controller()

        event = HashableEvent(pygame.CONTROLLERDEVICEREMAPPED, instance_id=0)
        manager.on_controller_device_remapped_event(event)

        assert len(_received(scene)) == 1
        assert _received(scene)[0][1].instance_id == 0

    def test_controller_touchpad_down_event(self):
        """Test controller touchpad down event handling."""
        manager, scene = _manager_with_controller()

        event = HashableEvent(
            pygame.CONTROLLERTOUCHPADDOWN, touchpad=0, finger=0, x=100, y=100, instance_id=0
        )
        manager.on_controller_touchpad_down_event(event)

        assert len(_received(scene)) == 1
        assert _received(scene)[0][1].touchpad == 0
        assert _received(scene)[0][1].finger == 0

    def test_controller_touchpad_motion_event(self):
        """Test controller touchpad motion event handling."""
        manager, scene = _manager_with_controller()

        event = HashableEvent(
            pygame.CONTROLLERTOUCHPADMOTION, touchpad=0, finger=0, x=100, y=100, instance_id=0
        )
        manager.on_controller_touchpad_motion_event(event)

        assert len(_received(scene)) == 1
        assert _received(scene)[0][1].touchpad == 0
        assert _received(scene)[0][1].finger == 0

    def test_controller_touchpad_up_event(self):
        """Test controller touchpad up event handling."""
        manager, scene = _manager_with_controller()

        event = HashableEvent(
            pygame.CONTROLLERTOUCHPADUP, touchpad=0, finger=0, x=100, y=100, instance_id=0
        )
        manager.on_controller_touchpad_up_event(event)

        assert len(_received(scene)) == 1
        assert _received(scene)[0][1].touchpad == 0
        assert _received(scene)[0][1].finger == 0

    def test_controller_axis_values(self):
        """Test controller axis motion with different values."""
        manager, scene = _manager_with_controller()

        axis_values = [-1.0, -0.5, 0.0, 0.5, 1.0]
        for value in axis_values:
            event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=value, instance_id=0)
            manager.on_controller_axis_motion_event(event)

        assert [received.value for _kind, received in _received(scene)] == axis_values
        # The proxy keeps the latest value
        assert manager.controllers[0]._axes[0] == axis_values[-1]

    def test_controller_button_variations(self):
        """Test controller button events with different buttons."""
        manager, scene = _manager_with_controller()

        controller_buttons = [
            pygame.CONTROLLER_BUTTON_A,
            pygame.CONTROLLER_BUTTON_B,
            pygame.CONTROLLER_BUTTON_X,
            pygame.CONTROLLER_BUTTON_Y,
            pygame.CONTROLLER_BUTTON_BACK,
            pygame.CONTROLLER_BUTTON_GUIDE,
            pygame.CONTROLLER_BUTTON_START,
            pygame.CONTROLLER_BUTTON_LEFTSTICK,
            pygame.CONTROLLER_BUTTON_RIGHTSTICK,
            pygame.CONTROLLER_BUTTON_LEFTSHOULDER,
            pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
            pygame.CONTROLLER_BUTTON_DPAD_UP,
            pygame.CONTROLLER_BUTTON_DPAD_DOWN,
            pygame.CONTROLLER_BUTTON_DPAD_LEFT,
            pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
        ]

        for button in controller_buttons:
            manager.on_controller_button_down_event(
                HashableEvent(pygame.CONTROLLERBUTTONDOWN, button=button, instance_id=0)
            )
            assert manager.controllers[0]._buttons[button] is True
            manager.on_controller_button_up_event(
                HashableEvent(pygame.CONTROLLERBUTTONUP, button=button, instance_id=0)
            )
            assert manager.controllers[0]._buttons[button] is False

        # Every event reached the game (2 events per button), in order
        assert [(kind, received.button) for kind, received in _received(scene)] == [
            (kind, button) for button in controller_buttons for kind in ('button_down', 'button_up')
        ]

    def test_controller_axis_variations(self):
        """Test controller axis motion with different axes."""
        manager, scene = _manager_with_controller()

        controller_axes = [
            pygame.CONTROLLER_AXIS_LEFTX,
            pygame.CONTROLLER_AXIS_LEFTY,
            pygame.CONTROLLER_AXIS_RIGHTX,
            pygame.CONTROLLER_AXIS_RIGHTY,
            pygame.CONTROLLER_AXIS_TRIGGERLEFT,
            pygame.CONTROLLER_AXIS_TRIGGERRIGHT,
        ]

        for axis in controller_axes:
            event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=axis, value=0.5, instance_id=0)
            manager.on_controller_axis_motion_event(event)

        assert [received.axis for _kind, received in _received(scene)] == controller_axes
        assert all(
            math.isclose(manager.controllers[0]._axes[axis], 0.5) for axis in controller_axes
        )


class TestControllerEventFlow:
    """Test controller events through the proper engine flow."""

    def test_controller_event_through_engine(self):
        """A controller axis motion pumped by the engine reaches the active scene."""
        scene_manager = GoldenTraceSceneManager.install()
        with command_line([
            '--windowed',
            '--resolution',
            '800x600',
            '--log-level',
            'warning',
            '--no-unhandled-events',
            '--input-mode',
            'controller',
        ]):
            engine = GoldenTraceEngine(game=ControllerRecordingScene)
        pygame_event = pygame.event.Event(
            pygame.CONTROLLERAXISMOTION, axis=0, value=16384, instance_id=0
        )
        install_sources(
            sources=ScriptedBatchSources(
                registry=_controller_registry(instance_ids_by_device_index={0: 0}),
                batch=[pygame_event],
            )
        )
        engine.install_game(scene_class=ControllerRecordingScene)
        scene = scene_manager.active_scene
        assert isinstance(scene, ControllerRecordingScene)

        assert engine.process_events() is True

        assert len(_received(scene)) == 1
        kind, received = _received(scene)[0]
        assert kind == 'axis_motion'
        assert received.type == pygame.CONTROLLERAXISMOTION
        assert received.axis == 0
        assert received.value == 16384

    def test_controller_event_falls_back_to_stubs(self, mocker):
        """Test unhandled controller events fall back to stubs.

        Verifies that they cause UnhandledEventError: a real Scene without its own controller
        axis handler gets the stub, which raises under no_unhandled_events.
        """
        _install_controllers(instance_ids_by_device_index={0: 0})
        scene = Scene(options=dict(NO_UNHANDLED_EVENTS_OPTIONS))
        manager = ControllerEventManager(game=scene)

        event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=0.5, instance_id=0)

        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            manager.on_controller_axis_motion_event(event)

    def test_controller_manager_initialization(self):
        """Test ControllerEventManager initializes correctly."""
        manager, scene = _manager_without_controllers()

        assert manager.game is scene
        assert manager.proxies == [scene]
        assert manager.controllers == {}

    def test_controller_manager_directly(self):
        """Test ControllerEventManager in isolation: each event reaches the game in order."""
        manager, scene = _manager_with_controller()

        axis_event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=0.5, instance_id=0)
        down_event = HashableEvent(pygame.CONTROLLERBUTTONDOWN, button=0, instance_id=0)
        up_event = HashableEvent(pygame.CONTROLLERBUTTONUP, button=0, instance_id=0)
        manager.on_controller_axis_motion_event(axis_event)
        manager.on_controller_button_down_event(down_event)
        manager.on_controller_button_up_event(up_event)

        assert _received(scene) == [
            ('axis_motion', axis_event),
            ('button_down', down_event),
            ('button_up', up_event),
        ]


class TestControllerSensorEvent:
    """Test sensor update event routing."""

    def test_sensor_update_routes_to_proxy(self):
        """Sensor update event should route to the correct controller proxy."""
        manager, scene = _manager_with_controller()

        event = HashableEvent(
            pygame.CONTROLLERSENSORUPDATE,
            instance_id=0,
            sensor=0,
            data=(0.1, 0.2, 0.3),
        )
        manager.on_controller_sensor_update_event(event)

        assert _received(scene) == [('sensor_update', event)]

    def test_sensor_update_missing_instance_is_safe(self):
        """Sensor update for unknown instance_id should not crash or reach the game."""
        manager, scene = _manager_without_controllers()

        event = HashableEvent(
            pygame.CONTROLLERSENSORUPDATE,
            instance_id=999,
            sensor=0,
            data=(0.0, 0.0, 0.0),
        )
        manager.on_controller_sensor_update_event(event)

        assert _received(scene) == []


class TestControllerRumble:
    """Test rumble and LED output features on the manager."""

    def test_rumble_delegates_to_proxy(self, mocker):
        """Rumble call should reach the controller through its proxy."""
        manager, _scene = _manager_with_controller()
        rumble_spy = mocker.spy(manager.controllers[0].controller, 'rumble')

        result = manager.rumble(
            instance_id=0,
            low_frequency=0.5,
            high_frequency=0.8,
            duration=200,
        )

        assert result is True
        rumble_spy.assert_called_once_with(0.5, 0.8, 200)

    def test_rumble_missing_controller_returns_false(self):
        """Rumble for non-existent controller returns False."""
        manager, _scene = _manager_without_controllers()

        assert manager.rumble(instance_id=99) is False

    def test_stop_rumble_delegates_to_proxy(self, mocker):
        """Stop rumble should reach the controller through its proxy."""
        manager, _scene = _manager_with_controller()
        stop_spy = mocker.spy(manager.controllers[0].controller, 'stop_rumble')

        manager.stop_rumble(instance_id=0)

        stop_spy.assert_called_once_with()

    def test_stop_rumble_missing_controller_is_safe(self):
        """Stop rumble for non-existent controller should not crash."""
        manager, _scene = _manager_without_controllers()

        manager.stop_rumble(instance_id=99)  # Should not raise


class TestControllerLED:
    """Test LED color output feature."""

    def test_set_led_delegates_to_proxy(self, mocker):
        """Set LED should reach the controller through its proxy, with its answer back."""
        manager, _scene = _manager_with_controller()
        set_led_spy = mocker.spy(manager.controllers[0].controller, 'set_led')

        result = manager.set_led(instance_id=0, red=255, green=0, blue=0)

        # The stand-in has no LED: it answers False, as pygame does
        assert result is False
        set_led_spy.assert_called_once_with((255, 0, 0))

    def test_set_led_missing_controller_returns_false(self):
        """Set LED for non-existent controller returns False."""
        manager, _scene = _manager_without_controllers()

        assert manager.set_led(instance_id=99, red=0, green=0, blue=0) is False


# ---------------------------------------------------------------------------
# The devices door (glitchygames/input/devices.py): enumeration, opening and polling
# ---------------------------------------------------------------------------


class TestControllerDevicesDoor:
    """Controllers are counted and opened through the registry and read from the snapshot."""

    def test_controller_proxy_opens_through_the_registry_and_reads_the_snapshot(self, mocker):
        """The proxy's caches come from the snapshot's controller layer, by instance id."""
        _install_controllers(instance_ids_by_device_index={0: 7})
        # Tripwire: the real controller constructor (hardware) must never be reached
        real_controller = mocker.patch('pygame._sdl2.controller.Controller')
        set_current_input(
            snapshot=InputSnapshot(
                pressed_scancodes=frozenset(),
                modifiers=0,
                mouse_position=(0, 0),
                mouse_buttons=(False, False, False),
                mouse_focused=True,
                controller_axes={7: (100, -200, 0, 0, 32767, 0)},
                controller_buttons={7: (True,) + (False,) * 14},
            )
        )

        proxy = ControllerEventManager.ControllerEventProxy(controller_id=0, game=None)

        real_controller.assert_not_called()
        assert proxy._axes == [100, -200, 0, 0, 32767, 0]
        assert proxy._buttons == [True] + [False] * 14

    def test_controller_manager_enumerates_through_the_registry(self, mocker):
        """The manager counts controllers and asks which are controllers via the registry."""
        _install_controllers(instance_ids_by_device_index={0: 7})
        # Tripwires: the real enumeration and constructor (hardware) must never be reached
        real_count = mocker.patch('pygame._sdl2.controller.get_count')
        real_is_controller = mocker.patch('pygame._sdl2.controller.is_controller')
        real_controller = mocker.patch('pygame._sdl2.controller.Controller')

        manager = ControllerEventManager(game=ControllerRecordingScene())

        real_count.assert_not_called()
        real_is_controller.assert_not_called()
        real_controller.assert_not_called()
        # Keyed by instance id, as the events carry it (BUGS.md #181)
        assert list(manager.controllers) == [7]

    def test_controller_removal_makes_the_registry_forget_the_device(self):
        """A removed controller is forgotten by the devices door, tracked or not."""
        registry = _install_controllers(instance_ids_by_device_index={0: 7})
        registry.open_controller(device_index=0)
        manager = ControllerEventManager.__new__(ControllerEventManager)
        manager.controllers = {}
        manager.game = ControllerRecordingScene()

        manager.on_controller_device_removed_event(
            HashableEvent(pygame.CONTROLLERDEVICEREMOVED, instance_id=7)
        )

        assert registry.joystick_for_instance(instance_id=7) is None

    def test_a_device_that_is_not_a_controller_is_skipped(self, caplog):
        """A counted device the registry says is not a controller gets no proxy, with a warning."""
        registry = ReplayDeviceRegistry(
            descriptors=[],
            enumeration_answers=[
                EnumerationAnswer(call=CONTROLLER_COUNT_CALL, device_index=None, value=1),
                EnumerationAnswer(call=IS_CONTROLLER_CALL, device_index=0, value=False),
            ],
        )
        install_sources(sources=ReplayDeviceSources(registry=registry))

        with caplog.at_level('WARNING'):
            manager = ControllerEventManager(game=ControllerRecordingScene())

        assert manager.controllers == {}
        assert 'Controller #0 is not a controller.' in caplog.text

    def test_manager_starts_when_controller_events_cannot_be_allowed(self, mocker, caplog):
        """If pygame refuses to allow controller events, the manager still starts (debug log)."""
        # Simulated failure: pygame refusing (video not initialized)
        mocker.patch('pygame.event.set_allowed', side_effect=pygame.error('video not initialized'))
        _install_controllers(instance_ids_by_device_index={})

        with caplog.at_level('DEBUG', logger='game.controllers'):
            manager = ControllerEventManager(game=ControllerRecordingScene())

        assert manager.controllers == {}
        assert 'Failed to set allowed controller events' in caplog.text


class TestControllersKeyedByInstanceId:
    """Controllers are tracked by the instance id their events carry (BUGS.md #181).

    A device's instance id differs from its device index after a replug (SDL gives the device
    a new instance id) or when devices open out of order, so each stand-in here has an
    instance id other than its device index.
    """

    def test_startup_controller_is_found_by_its_events_instance_id(self):
        """A controller at device index 0 with instance id 7 gets its axis and button events."""
        _install_controllers(instance_ids_by_device_index={0: 7})
        scene = ControllerRecordingScene()
        manager = ControllerEventManager(game=scene)

        axis_event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=10, instance_id=7)
        button_event = HashableEvent(pygame.CONTROLLERBUTTONDOWN, button=1, instance_id=7)
        manager.on_controller_axis_motion_event(axis_event)
        manager.on_controller_button_down_event(button_event)

        assert list(manager.controllers) == [7]
        assert _received(scene) == [('axis_motion', axis_event), ('button_down', button_event)]

    def test_hot_plugged_controller_is_found_by_its_events_instance_id(self):
        """CONTROLLERDEVICEADDED (by device index) tracks the controller by its instance id."""
        _install_controllers(instance_ids_by_device_index={0: 9}, counted_controllers=0)
        scene = ControllerRecordingScene()
        manager = ControllerEventManager(game=scene)

        added_event = HashableEvent(pygame.CONTROLLERDEVICEADDED, device_index=0, guid='g')
        manager.on_controller_device_added_event(added_event)
        button_event = HashableEvent(pygame.CONTROLLERBUTTONUP, button=2, instance_id=9)
        manager.on_controller_button_up_event(button_event)
        touch_event = HashableEvent(
            pygame.CONTROLLERTOUCHPADDOWN, touchpad=0, finger=0, x=0.5, y=0.5, instance_id=9
        )
        manager.on_controller_touchpad_down_event(touch_event)

        assert list(manager.controllers) == [9]
        assert manager.controllers[9].instance_id == 9
        assert manager.controllers[9].device_index == 0
        assert _received(scene) == [
            ('device_added', added_event),
            ('button_up', button_event),
            ('touchpad_down', touch_event),
        ]

    def test_remapped_controller_is_found_by_its_events_instance_id(self):
        """CONTROLLERDEVICEREMAPPED carries the instance id (pygame's event docs)."""
        _install_controllers(instance_ids_by_device_index={0: 7})
        scene = ControllerRecordingScene()
        manager = ControllerEventManager(game=scene)

        remapped_event = HashableEvent(pygame.CONTROLLERDEVICEREMAPPED, instance_id=7)
        manager.on_controller_device_remapped_event(remapped_event)

        assert _received(scene) == [('device_remapped', remapped_event)]

    def test_remapped_event_for_an_untracked_controller_is_ignored(self):
        """A remap of a controller the manager does not track reaches nobody (no KeyError)."""
        manager, scene = _manager_without_controllers()

        manager.on_controller_device_remapped_event(
            HashableEvent(pygame.CONTROLLERDEVICEREMAPPED, instance_id=3)
        )

        assert _received(scene) == []

    def test_replugged_controller_replaces_nothing_and_is_removed_by_instance_id(self):
        """A replug (new instance id at the same device index) is tracked apart, then removed."""
        registry = _install_controllers(instance_ids_by_device_index={0: 7})
        scene = ControllerRecordingScene()
        manager = ControllerEventManager(game=scene)
        manager.on_controller_device_removed_event(
            HashableEvent(pygame.CONTROLLERDEVICEREMOVED, instance_id=7)
        )
        # Plugged in again: SDL gives it instance id 8 at device index 0
        registry.add_descriptors(
            descriptors=[_controller_descriptor(device_index=0, instance_id=8)]
        )
        registry.add_enumeration_answers(
            answers=[EnumerationAnswer(call=OPEN_CONTROLLER_CALL, device_index=0, value=8)]
        )

        manager.on_controller_device_added_event(
            HashableEvent(pygame.CONTROLLERDEVICEADDED, device_index=0, guid='g')
        )
        manager.on_controller_axis_motion_event(
            HashableEvent(pygame.CONTROLLERAXISMOTION, axis=1, value=5, instance_id=8)
        )

        assert list(manager.controllers) == [8]
        assert [name for name, _event in _received(scene)] == [
            'device_removed',
            'device_added',
            'axis_motion',
        ]

    def test_hot_plugged_controller_that_vanished_before_it_opened_is_skipped(self, caplog):
        """A controller unplugged again before it could be opened is logged, not tracked."""
        registry = _install_controllers(instance_ids_by_device_index={}, counted_controllers=0)
        registry.add_enumeration_answers(
            answers=[
                EnumerationAnswer(
                    call=OPEN_CONTROLLER_CALL, device_index=0, value=None, error='gone'
                )
            ]
        )
        scene = ControllerRecordingScene()
        manager = ControllerEventManager(game=scene)

        with caplog.at_level('WARNING', logger='game.controllers'):
            manager.on_controller_device_added_event(
                HashableEvent(pygame.CONTROLLERDEVICEADDED, device_index=0, guid='g')
            )

        assert manager.controllers == {}
        assert _received(scene) == []
        assert 'Controller at device index 0 vanished before it could be opened' in caplog.text
