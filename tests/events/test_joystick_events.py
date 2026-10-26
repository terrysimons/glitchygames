"""Tests for joystick event functionality.

This module combines tests for:
- JoystickEvents interface and stubs
- JoystickEventProxy direct methods, forwarding, and fallback paths
- JoystickEventManager routing, initialization, device add/remove, and exception paths

Joysticks are hardware. Most tests serve the replay stand-ins (``ReplayJoystick``) from a
``ReplayDeviceRegistry`` through the devices door (glitchygames/input/devices.py). The tests of
the live door's failure handling go through the real ``LiveDeviceRegistry`` with only SDL's
hardware entry points faked (``pygame.joystick.get_count`` and the ``pygame.joystick.Joystick``
constructor, which returns a ``ScriptedJoystick``: a stand-in whose getters can fail on a given
call). Everything else is real: the managers and proxies, real Scenes receiving the events, and
real events.
"""

import argparse
import dataclasses
import math
from typing import Any, Self

import pygame
import pytest

from glitchygames.events import (
    HashableEvent,
    JoystickEvents,
    UnhandledEventError,
)
from glitchygames.events.joystick import JoystickEventManager
from glitchygames.input.devices import (
    JOYSTICK_COUNT_CALL,
    JOYSTICK_KIND,
    DeviceDescriptor,
    EnumerationAnswer,
    ReplayDeviceRegistry,
    ReplayJoystick,
)
from glitchygames.input.state import InputSnapshot, set_current_input
from glitchygames.live_sources import LiveSources
from glitchygames.scenes import Scene
from glitchygames.sources import active_sources, install_sources

NO_UNHANDLED_EVENTS_OPTIONS = {'debug_events': False, 'no_unhandled_events': True}

# The joystick a ScriptedJoystick describes unless told otherwise
SCRIPTED_JOYSTICK = DeviceDescriptor(
    kind=JOYSTICK_KIND,
    device_index=0,
    instance_id=0,
    name='TestJoystick',
    guid='test-guid',
    axis_count=0,
    button_count=0,
    hat_count=0,
    ball_count=0,
)

# The recorded joystick the replay registries hold unless told otherwise
PAD_JOYSTICK = DeviceDescriptor(
    kind=JOYSTICK_KIND,
    device_index=0,
    instance_id=0,
    name='Pad',
    guid=None,
    axis_count=2,
    button_count=1,
    hat_count=1,
    ball_count=1,
)

# ---------------------------------------------------------------------------
# Helpers: a recording scene, stand-in joysticks, and doors serving them
# ---------------------------------------------------------------------------


class JoystickRecordingScene(Scene):
    """A real scene that records every joystick event it receives, in order."""

    def __init__(self: Self, options: dict[str, Any] | None = None, groups: Any = None) -> None:
        """Create the scene with no events received yet."""
        super().__init__(
            options=dict(NO_UNHANDLED_EVENTS_OPTIONS) if options is None else options,
            groups=groups,
        )
        self.joystick_events_received: list[tuple[str, HashableEvent]] = []

    def on_joy_axis_motion_event(self: Self, event: HashableEvent) -> None:
        self.joystick_events_received.append(('axis_motion', event))

    def on_joy_button_down_event(self: Self, event: HashableEvent) -> None:
        self.joystick_events_received.append(('button_down', event))

    def on_joy_button_up_event(self: Self, event: HashableEvent) -> None:
        self.joystick_events_received.append(('button_up', event))

    def on_joy_hat_motion_event(self: Self, event: HashableEvent) -> None:
        self.joystick_events_received.append(('hat_motion', event))

    def on_joy_ball_motion_event(self: Self, event: HashableEvent) -> None:
        self.joystick_events_received.append(('ball_motion', event))

    def on_joy_device_added_event(self: Self, event: HashableEvent) -> None:
        self.joystick_events_received.append(('device_added', event))

    def on_joy_device_removed_event(self: Self, event: HashableEvent) -> None:
        self.joystick_events_received.append(('device_removed', event))


def _received(scene: JoystickRecordingScene) -> list[tuple[str, HashableEvent]]:
    return scene.joystick_events_received


class ScriptedJoystick(ReplayJoystick):
    """A stand-in joystick whose getters can fail on given calls (simulated hardware faults).

    The live devices door (``LiveDeviceRegistry``) gets it from the faked
    ``pygame.joystick.Joystick`` constructor. Calls are counted per method, from 1.
    """

    def __init__(
        self: Self,
        *,
        failing_calls: dict[str, dict[int, BaseException]] | None = None,
        always_failing: dict[str, BaseException] | None = None,
        **descriptor_fields: Any,
    ) -> None:
        """Create the stand-in.

        Args:
            failing_calls: Per method name, the call numbers that raise, and what they raise.
            always_failing: Per method name, what every call raises.
            **descriptor_fields: DeviceDescriptor fields that differ from SCRIPTED_JOYSTICK
                (instance_id, device_index, name, ...).

        """
        super().__init__(descriptor=dataclasses.replace(SCRIPTED_JOYSTICK, **descriptor_fields))
        self.failing_calls = failing_calls or {}
        self.always_failing = always_failing or {}
        self.call_counts: dict[str, int] = {}

    def _count_call(self: Self, method_name: str) -> None:
        """Count a call, then raise the failure scripted for it (if any)."""
        call_number = self.call_counts.get(method_name, 0) + 1
        self.call_counts[method_name] = call_number
        if method_name in self.always_failing:
            raise self.always_failing[method_name]
        failure = self.failing_calls.get(method_name, {}).get(call_number)
        if failure is not None:
            raise failure

    def init(self: Self) -> None:
        self._count_call('init')
        super().init()

    def get_id(self: Self) -> int:
        self._count_call('get_id')
        return super().get_id()

    def get_instance_id(self: Self) -> int:
        self._count_call('get_instance_id')
        return super().get_instance_id()

    def get_name(self: Self) -> str:
        self._count_call('get_name')
        return super().get_name()

    def get_guid(self: Self) -> str | None:
        self._count_call('get_guid')
        return super().get_guid()

    def get_power_level(self: Self) -> str:
        self._count_call('get_power_level')
        return super().get_power_level()


def _fake_joystick_hardware(mocker, *, joystick_count, joysticks=None, opens=None):
    """Fake SDL's joystick hardware under the real live devices door.

    Args:
        mocker: pytest-mock mocker fixture
        joystick_count: The count SDL reports.
        joysticks: The joystick every open returns (or None).
        opens: What successive opens return or raise (overrides ``joysticks``).

    Returns:
        The faked ``pygame.joystick.Joystick`` constructor.

    """
    mocker.patch('pygame.joystick.get_count', return_value=joystick_count)
    if opens is not None:
        return mocker.patch('pygame.joystick.Joystick', side_effect=opens)
    return mocker.patch('pygame.joystick.Joystick', return_value=joysticks)


class ReplayDeviceSources(LiveSources):
    """Live doors whose devices are a replay registry's stand-ins (no joystick hardware)."""

    def __init__(self: Self, *, registry: ReplayDeviceRegistry) -> None:
        """Create the doors around the registry."""
        super().__init__(random_seed=1)
        self.registry = registry

    def devices(self: Self) -> ReplayDeviceRegistry:  # type: ignore[override]
        return self.registry


def _joystick_descriptor(
    *, device_index: int, instance_id: int, **descriptor_fields: Any
) -> DeviceDescriptor:
    """Describe a stand-in joystick: PAD_JOYSTICK with the given fields.

    Returns:
        The descriptor.

    """
    return dataclasses.replace(
        PAD_JOYSTICK, device_index=device_index, instance_id=instance_id, **descriptor_fields
    )


def _install_joysticks(
    *, descriptors: list[DeviceDescriptor], counted_joysticks: int | None = None
) -> ReplayDeviceRegistry:
    """Install doors whose devices are stand-in joysticks.

    Args:
        descriptors: The recorded joysticks.
        counted_joysticks: How many joysticks the count reports (default: all of them;
            0 leaves them to be hot-plugged).

    Returns:
        The installed registry.

    """
    joystick_count = len(descriptors) if counted_joysticks is None else counted_joysticks
    registry = ReplayDeviceRegistry(
        descriptors=descriptors,
        enumeration_answers=[
            EnumerationAnswer(call=JOYSTICK_COUNT_CALL, device_index=None, value=joystick_count)
        ],
    )
    install_sources(sources=ReplayDeviceSources(registry=registry))
    return registry


def _manager_without_joysticks() -> tuple[JoystickEventManager, JoystickRecordingScene]:
    """Create a real manager that finds no joysticks.

    Returns:
        The manager and the scene it forwards to.

    """
    _install_joysticks(descriptors=[])
    scene = JoystickRecordingScene()
    return JoystickEventManager(game=scene), scene


def _manager_with_joystick(
    *, instance_id: int = 0
) -> tuple[JoystickEventManager, JoystickRecordingScene]:
    """Create a real manager with one stand-in joystick at device index 0.

    Returns:
        The manager and the scene it forwards to.

    """
    _install_joysticks(descriptors=[_joystick_descriptor(device_index=0, instance_id=instance_id)])
    scene = JoystickRecordingScene()
    manager = JoystickEventManager(game=scene)
    assert list(manager.joysticks) == [instance_id]
    return manager, scene


class TestJoystickManagerInitExceptionPaths:
    """Test JoystickEventManager.__init__ exception branches."""

    def test_init_set_allowed_pygame_error(self, mocker):
        """Test that pygame.error in set_allowed is caught (lines 275-276)."""
        # Simulated failure: pygame refusing to allow the events
        mocker.patch('pygame.event.set_allowed', side_effect=pygame.error('not init'))

        manager, scene = _manager_without_joysticks()

        assert manager.game is scene
        assert len(manager.joysticks) == 0

    def test_init_skips_a_joystick_that_vanished_before_it_opened(self, mocker, caplog):
        """Unplugged between the count and the open: that joystick is skipped, the next kept."""
        _fake_joystick_hardware(
            mocker,
            joystick_count=2,
            opens=[pygame.error('gone'), ScriptedJoystick(instance_id=5, device_index=1)],
        )

        with caplog.at_level('WARNING', logger='game.joysticks'):
            manager = JoystickEventManager(game=JoystickRecordingScene())

        assert 'Joystick 0 vanished before it could be opened' in caplog.text
        assert list(manager.joysticks) == [5]

    def test_opened_joysticks_need_no_deprecated_calls(self, mocker):
        """Startup never calls the deprecated init() or get_id(): an opened joystick is ready."""
        joystick = ScriptedJoystick(
            always_failing={
                'init': pygame.error('init() is deprecated'),
                'get_id': pygame.error('get_id() is deprecated'),
            }
        )
        _fake_joystick_hardware(mocker, joystick_count=1, joysticks=joystick)

        manager = JoystickEventManager(game=JoystickRecordingScene())

        assert len(manager.joysticks) == 1
        assert 'init' not in joystick.call_counts
        assert 'get_id' not in joystick.call_counts

    def test_init_joystick_get_instance_id_pygame_error(self, mocker):
        """Test that pygame.error in get_instance_id in the debug block is caught.

        The devices door's open describes the joystick (first call), the debug block calls
        get_instance_id() and catches pygame.error (second call), and the stable key block
        and the proxy call it again (third and fourth calls).
        """
        joystick = ScriptedJoystick(
            failing_calls={'get_instance_id': {2: pygame.error('no instance')}}
        )
        _fake_joystick_hardware(mocker, joystick_count=1, joysticks=joystick)

        manager = JoystickEventManager(game=JoystickRecordingScene())

        assert list(manager.joysticks) == [0]
        assert joystick.call_counts['get_instance_id'] == 4

    def test_init_joystick_get_name_pygame_error(self, mocker):
        """Test that pygame.error in get_name is caught (lines 307-308)."""
        # The second call is the debug block's (the first is the devices door's)
        joystick = ScriptedJoystick(failing_calls={'get_name': {2: pygame.error('no name')}})
        _fake_joystick_hardware(mocker, joystick_count=1, joysticks=joystick)

        manager = JoystickEventManager(game=JoystickRecordingScene())

        assert len(manager.joysticks) == 1
        assert manager.joysticks[0].get_name() == 'TestJoystick'

    def test_init_joystick_get_guid_pygame_error(self, mocker):
        """Test that pygame.error in get_guid is caught (lines 311-312)."""
        # The second call is the debug block's (the first is the devices door's)
        joystick = ScriptedJoystick(failing_calls={'get_guid': {2: pygame.error('no guid')}})
        _fake_joystick_hardware(mocker, joystick_count=1, joysticks=joystick)

        manager = JoystickEventManager(game=JoystickRecordingScene())

        assert len(manager.joysticks) == 1
        assert manager.joysticks[0]._guid == 'test-guid'

    def test_init_joystick_get_instance_id_attribute_error(self, mocker):
        """Test AttributeError fallback for get_instance_id at the stable key lookup.

        The debug block catches pygame.error but not AttributeError. The debug block's
        get_instance_id() call must succeed (as must the devices door's open, before it), but
        the stable key block's raises AttributeError; the proxy's own call then succeeds.
        """
        joystick = ScriptedJoystick(
            instance_id=6, failing_calls={'get_instance_id': {3: AttributeError('no method')}}
        )
        _fake_joystick_hardware(mocker, joystick_count=1, joysticks=joystick)

        manager = JoystickEventManager(game=JoystickRecordingScene())

        # Falls back to using the index (0) as the key, not the instance id (6)
        assert list(manager.joysticks) == [0]


class TestJoystickDeviceAddedExceptionPaths:
    """Test on_joy_device_added_event exception branches."""

    def test_device_added_joystick_open_error(self, mocker):
        """Test pygame.error opening joystick at device_index: keyed by the device index.

        The instance id lookup opens the device once, through the devices door; when that
        open fails the device index is the key, and the proxy opens the device again.
        """
        _fake_joystick_hardware(mocker, joystick_count=0)
        scene = JoystickRecordingScene()
        manager = JoystickEventManager(game=scene)

        # First open (the instance id lookup) raises pygame.error, the second (the proxy) works
        _fake_joystick_hardware(
            mocker,
            joystick_count=0,
            opens=[pygame.error('cannot open'), ScriptedJoystick(instance_id=42)],
        )

        event = HashableEvent(pygame.JOYDEVICEADDED, device_index=0)
        manager.on_joy_device_added_event(event)

        assert 0 in manager.joysticks
        assert manager.joysticks[0].joystick.get_instance_id() == 42
        assert _received(scene) == [('device_added', event)]

    def test_device_added_get_name_error(self, mocker):
        """Test pygame.error in get_name during device added (lines 456-457)."""
        _fake_joystick_hardware(mocker, joystick_count=0)
        manager = JoystickEventManager(game=JoystickRecordingScene())

        # The second call is the debug block's (the first is the devices door's)
        joystick = ScriptedJoystick(
            instance_id=10, failing_calls={'get_name': {2: pygame.error('no name')}}
        )
        _fake_joystick_hardware(mocker, joystick_count=0, joysticks=joystick)

        manager.on_joy_device_added_event(HashableEvent(pygame.JOYDEVICEADDED, device_index=0))

        assert 10 in manager.joysticks

    def test_device_added_get_guid_error(self, mocker):
        """Test pygame.error in get_guid during device added (lines 460-461)."""
        _fake_joystick_hardware(mocker, joystick_count=0)
        manager = JoystickEventManager(game=JoystickRecordingScene())

        # The second call is the debug block's (the first is the devices door's)
        joystick = ScriptedJoystick(
            instance_id=11, failing_calls={'get_guid': {2: pygame.error('no guid')}}
        )
        _fake_joystick_hardware(mocker, joystick_count=0, joysticks=joystick)

        manager.on_joy_device_added_event(HashableEvent(pygame.JOYDEVICEADDED, device_index=0))

        assert 11 in manager.joysticks

    def test_device_added_needs_no_deprecated_calls(self, mocker):
        """A hot-plugged joystick is tracked without the deprecated init() or get_id()."""
        _fake_joystick_hardware(mocker, joystick_count=0)
        manager = JoystickEventManager(game=JoystickRecordingScene())

        joystick = ScriptedJoystick(
            instance_id=12,
            always_failing={
                'init': pygame.error('init() is deprecated'),
                'get_id': pygame.error('get_id() is deprecated'),
            },
        )
        _fake_joystick_hardware(mocker, joystick_count=0, joysticks=joystick)

        manager.on_joy_device_added_event(HashableEvent(pygame.JOYDEVICEADDED, device_index=0))

        assert 12 in manager.joysticks
        assert 'init' not in joystick.call_counts
        assert 'get_id' not in joystick.call_counts

    def test_device_added_get_instance_id_error(self, mocker):
        """Test pygame.error in get_instance_id during device added (lines 468-469)."""
        _fake_joystick_hardware(mocker, joystick_count=0)
        scene = JoystickRecordingScene()
        manager = JoystickEventManager(game=scene)

        joystick = ScriptedJoystick(always_failing={'get_instance_id': pygame.error('no instance')})
        _fake_joystick_hardware(mocker, joystick_count=0, joysticks=joystick)

        manager.on_joy_device_added_event(HashableEvent(pygame.JOYDEVICEADDED, device_index=0))

        # The devices door cannot describe the device, so the instance id lookup's open
        # fails (falling back to event.device_index as the key) and so does the proxy's:
        # the device is gone, so nothing is tracked and the handler does not raise.
        assert manager.joysticks == {}
        assert _received(scene) == []

    def test_device_added_debug_info_survives_instance_id_error(self, mocker, caplog):
        """A get_instance_id failure in the debug log is logged as None; the device is tracked.

        The door's open describes the joystick (first call) and the instance id lookup reads it
        (second call); the third call is the debug block's.
        """
        _fake_joystick_hardware(mocker, joystick_count=0)
        manager = JoystickEventManager(game=JoystickRecordingScene())
        joystick = ScriptedJoystick(
            instance_id=7, failing_calls={'get_instance_id': {3: pygame.error('no instance')}}
        )
        _fake_joystick_hardware(mocker, joystick_count=0, joysticks=joystick)

        with caplog.at_level('DEBUG', logger='game.joysticks'):
            manager.on_joy_device_added_event(HashableEvent(pygame.JOYDEVICEADDED, device_index=0))

        assert 'DEVICEADDED index=0 instance_id=None' in caplog.text
        assert 7 in manager.joysticks

    def test_device_added_without_device_index_is_ignored(self, mocker, caplog):
        _fake_joystick_hardware(mocker, joystick_count=0)
        scene = JoystickRecordingScene()
        manager = JoystickEventManager(game=scene)
        joystick_constructor = _fake_joystick_hardware(mocker, joystick_count=0)

        with caplog.at_level('DEBUG', logger='game.joysticks'):
            manager.on_joy_device_added_event(HashableEvent(pygame.JOYDEVICEADDED))

        assert 'DEVICEADDED event has no device_index attribute' in caplog.text
        joystick_constructor.assert_not_called()
        assert manager.joysticks == {}
        assert _received(scene) == []


class TestJoystickDeviceAddedFallbackNotification:
    """Test on_joy_device_added_event fallback notification path (lines 517-518)."""

    def test_device_added_notification_via_instance_id(self):
        """Test that newly added joystick is notified via instance_id (lines 514-515).

        The normal flow always adds with instance_id as key, so lines 514-515
        are the primary notification path.
        """
        _install_joysticks(
            descriptors=[_joystick_descriptor(device_index=0, instance_id=99)],
            counted_joysticks=0,
        )
        scene = JoystickRecordingScene()
        manager = JoystickEventManager(game=scene)

        event = HashableEvent(pygame.JOYDEVICEADDED, device_index=0)
        manager.on_joy_device_added_event(event)

        assert 99 in manager.joysticks
        assert _received(scene) == [('device_added', event)]


# ---------------------------------------------------------------------------
# JoystickEventProxy direct method tests
# ---------------------------------------------------------------------------


def _create_proxy() -> tuple[Any, JoystickRecordingScene]:
    """Create a real JoystickEventProxy over a stand-in joystick.

    Returns:
        Tuple of (proxy, scene).

    """
    _install_joysticks(
        descriptors=[
            _joystick_descriptor(
                device_index=0,
                instance_id=0,
                name='Test Joystick',
                guid='test-guid-1234',
                axis_count=4,
                button_count=10,
                hat_count=1,
                ball_count=1,
            )
        ]
    )
    scene = JoystickRecordingScene()
    proxy = JoystickEventManager.JoystickEventProxy(game=scene, joystick_id=0, instance_id=0)
    return proxy, scene


class TestJoystickEventProxyDirectMethods:
    """Test JoystickEventProxy forwarding methods directly over a stand-in joystick."""

    def test_proxy_axis_motion_updates_and_forwards(self):
        """Axis motion should update axes state and forward to game."""
        proxy, scene = _create_proxy()

        event = HashableEvent(pygame.JOYAXISMOTION, axis=1, value=0.75)
        proxy.on_joy_axis_motion_event(event)

        assert math.isclose(proxy._axes[1], 0.75)
        assert _received(scene) == [('axis_motion', event)]

    def test_proxy_button_down_updates_and_forwards(self):
        """Button down should set button state to 1 and forward to game."""
        proxy, scene = _create_proxy()

        event = HashableEvent(pygame.JOYBUTTONDOWN, button=3)
        proxy.on_joy_button_down_event(event)

        assert proxy._buttons[3] == 1
        assert _received(scene) == [('button_down', event)]

    def test_proxy_button_down_negative_is_noop(self):
        """Button down with negative index should return early."""
        proxy, scene = _create_proxy()
        buttons_before = list(proxy._buttons)

        event = HashableEvent(pygame.JOYBUTTONDOWN, button=-1)
        proxy.on_joy_button_down_event(event)

        assert _received(scene) == []
        assert proxy._buttons == buttons_before

    def test_proxy_button_down_extends_list(self):
        """Button down with index beyond list should extend storage."""
        proxy, _scene = _create_proxy()

        original_length = len(proxy._buttons)
        event = HashableEvent(pygame.JOYBUTTONDOWN, button=original_length + 5)
        proxy.on_joy_button_down_event(event)

        assert len(proxy._buttons) > original_length
        assert proxy._buttons[original_length + 5] == 1

    def test_proxy_button_up_updates_and_forwards(self):
        """Button up should set button state to 0 and forward to game."""
        proxy, scene = _create_proxy()

        proxy._buttons[3] = 1

        event = HashableEvent(pygame.JOYBUTTONUP, button=3)
        proxy.on_joy_button_up_event(event)

        assert proxy._buttons[3] == 0
        assert _received(scene) == [('button_up', event)]

    def test_proxy_button_up_negative_is_noop(self):
        """Button up with negative index should return early."""
        proxy, scene = _create_proxy()

        event = HashableEvent(pygame.JOYBUTTONUP, button=-1)
        proxy.on_joy_button_up_event(event)

        assert _received(scene) == []

    def test_proxy_button_up_extends_list(self):
        """Button up with index beyond list should extend storage."""
        proxy, _scene = _create_proxy()

        original_length = len(proxy._buttons)
        event = HashableEvent(pygame.JOYBUTTONUP, button=original_length + 3)
        proxy.on_joy_button_up_event(event)

        assert len(proxy._buttons) > original_length
        assert proxy._buttons[original_length + 3] == 0

    def test_proxy_hat_motion_updates_and_forwards(self):
        """Hat motion should update hats state and forward to game."""
        proxy, scene = _create_proxy()

        event = HashableEvent(pygame.JOYHATMOTION, hat=0, value=(1, 0))
        proxy.on_joy_hat_motion_event(event)

        assert proxy._hats[0] == (1, 0)
        assert _received(scene) == [('hat_motion', event)]

    def test_proxy_ball_motion_updates_and_forwards(self):
        """Ball motion should update balls state and forward to game."""
        proxy, scene = _create_proxy()

        event = HashableEvent(pygame.JOYBALLMOTION, ball=0, rel=(5, -3))
        proxy.on_joy_ball_motion_event(event)

        assert proxy._balls[0] == (5, -3)
        assert _received(scene) == [('ball_motion', event)]

    def test_proxy_device_added_forwards(self):
        """Device added should forward to game."""
        proxy, scene = _create_proxy()

        event = HashableEvent(pygame.JOYDEVICEADDED, device_index=0, guid='test')
        proxy.on_joy_device_added_event(event)

        assert _received(scene) == [('device_added', event)]

    def test_proxy_device_removed_forwards(self):
        """Device removed should forward to game."""
        proxy, scene = _create_proxy()

        event = HashableEvent(pygame.JOYDEVICEREMOVED, device_index=0)
        proxy.on_joy_device_removed_event(event)

        assert _received(scene) == [('device_removed', event)]

    def test_proxy_get_name(self):
        """get_name should return the joystick name."""
        proxy, _scene = _create_proxy()

        assert proxy.get_name() == 'Test Joystick'

    def test_proxy_get_name_fallback_on_error(self, mocker):
        """get_name should fall back to cached name on pygame.error."""
        proxy, _scene = _create_proxy()

        # Simulated hardware fault: the device disconnected
        mocker.patch.object(
            proxy.joystick, 'get_name', side_effect=pygame.error('joystick disconnected')
        )

        assert proxy.get_name() == 'Test Joystick'

    def test_proxy_get_init(self):
        """get_init should return the cached init status."""
        proxy, _scene = _create_proxy()

        assert proxy.get_init() is True

    def test_proxy_get_numaxes(self):
        """get_numaxes should return the number of axes."""
        proxy, _scene = _create_proxy()

        assert proxy.get_numaxes() == 4

    def test_proxy_get_numballs(self):
        """get_numballs should return the number of trackballs."""
        proxy, _scene = _create_proxy()

        assert proxy.get_numballs() == 1

    def test_proxy_get_numbuttons(self):
        """get_numbuttons should return the number of buttons."""
        proxy, _scene = _create_proxy()

        assert proxy.get_numbuttons() == 10

    def test_proxy_get_numhats(self):
        """get_numhats should return the number of hats."""
        proxy, _scene = _create_proxy()

        assert proxy.get_numhats() == 1

    def test_proxy_str_representation(self):
        """str() should return a multi-line joystick info string."""
        proxy, _scene = _create_proxy()

        assert str(proxy).splitlines() == [
            'Joystick Name: Test Joystick',
            '\tJoystick Id: 0',
            '\tJoystick Inited: True',
            '\tJoystick Axis Count: 4',
            '\tJoystick Trackball Count: 1',
            '\tJoystick Button Count: 10',
            '\tJoystick Hat Count: 1',
        ]

    def test_proxy_repr(self):
        """repr() should return repr of underlying joystick."""
        proxy, _scene = _create_proxy()

        assert repr(proxy) == repr(proxy.joystick)


class TestJoystickEventProxyFallbacks:
    """Test JoystickEventProxy fallback behavior for instance_id, guid, and power_level."""

    def test_proxy_instance_id_preferred_over_joystick_id(self):
        """When instance_id is provided, it should be used as _id."""
        _install_joysticks(descriptors=[_joystick_descriptor(device_index=5, instance_id=42)])

        proxy = JoystickEventManager.JoystickEventProxy(
            game=JoystickRecordingScene(),
            joystick_id=5,
            instance_id=42,
        )

        assert proxy._id == 42
        assert proxy._device_id == 5

    def test_proxy_guid_attribute_error_fallback(self, mocker):
        """When get_guid raises AttributeError, _guid should be None."""
        _fake_joystick_hardware(
            mocker,
            joystick_count=0,
            joysticks=ScriptedJoystick(always_failing={'get_guid': AttributeError('get_guid')}),
        )

        proxy = JoystickEventManager.JoystickEventProxy(
            game=JoystickRecordingScene(), joystick_id=0
        )

        assert proxy._guid is None

    def test_proxy_power_level_attribute_error_fallback(self, mocker):
        """When get_power_level raises AttributeError, _power_level should be None."""
        _fake_joystick_hardware(
            mocker,
            joystick_count=0,
            joysticks=ScriptedJoystick(
                always_failing={'get_power_level': AttributeError('get_power_level')}
            ),
        )

        proxy = JoystickEventManager.JoystickEventProxy(
            game=JoystickRecordingScene(), joystick_id=0
        )

        assert proxy._power_level is None


class TestJoystickEventManagerRouting:
    """Test JoystickEventManager event routing to real proxies and on to the game."""

    def test_axis_motion_routes_via_instance_id(self):
        """Axis motion event should route to the correct joystick via instance_id."""
        manager, scene = _manager_with_joystick()

        event = HashableEvent(pygame.JOYAXISMOTION, axis=0, value=0.5, instance_id=0)
        manager.on_joy_axis_motion_event(event)

        assert _received(scene) == [('axis_motion', event)]
        assert math.isclose(manager.joysticks[0]._axes[0], 0.5)

    def test_axis_motion_routes_via_joy_fallback(self):
        """Axis motion should fall back to event.joy when instance_id is missing."""
        manager, scene = _manager_with_joystick()

        event = HashableEvent(pygame.JOYAXISMOTION, axis=0, value=0.5, joy=0)
        manager.on_joy_axis_motion_event(event)

        assert _received(scene) == [('axis_motion', event)]

    def test_button_down_routes_via_instance_id(self):
        """Button down event should route to the correct joystick."""
        manager, scene = _manager_with_joystick()

        event = HashableEvent(pygame.JOYBUTTONDOWN, button=0, instance_id=0)
        manager.on_joy_button_down_event(event)

        assert _received(scene) == [('button_down', event)]
        assert manager.joysticks[0]._buttons[0] is True

    def test_button_down_routes_via_joy_fallback(self):
        """Button down should fall back to event.joy when instance_id is missing."""
        manager, scene = _manager_with_joystick()

        event = HashableEvent(pygame.JOYBUTTONDOWN, button=0, joy=0)
        manager.on_joy_button_down_event(event)

        assert _received(scene) == [('button_down', event)]

    def test_button_up_routes_via_instance_id(self):
        """Button up event should route to the correct joystick."""
        manager, scene = _manager_with_joystick()

        event = HashableEvent(pygame.JOYBUTTONUP, button=0, instance_id=0)
        manager.on_joy_button_up_event(event)

        assert _received(scene) == [('button_up', event)]

    def test_button_up_routes_via_joy_fallback(self):
        """Button up should fall back to event.joy when instance_id is missing."""
        manager, scene = _manager_with_joystick()

        event = HashableEvent(pygame.JOYBUTTONUP, button=0, joy=0)
        manager.on_joy_button_up_event(event)

        assert _received(scene) == [('button_up', event)]

    def test_hat_motion_routes_via_instance_id(self):
        """Hat motion event should route to the correct joystick."""
        manager, scene = _manager_with_joystick()

        event = HashableEvent(pygame.JOYHATMOTION, hat=0, value=(1, 0), instance_id=0)
        manager.on_joy_hat_motion_event(event)

        assert _received(scene) == [('hat_motion', event)]
        assert manager.joysticks[0]._hats[0] == (1, 0)

    def test_hat_motion_routes_via_joy_fallback(self):
        """Hat motion should fall back to event.joy when instance_id is missing."""
        manager, scene = _manager_with_joystick()

        event = HashableEvent(pygame.JOYHATMOTION, hat=0, value=(1, 0), joy=0)
        manager.on_joy_hat_motion_event(event)

        assert _received(scene) == [('hat_motion', event)]

    def test_ball_motion_routes_via_instance_id(self):
        """Ball motion event should route to the correct joystick."""
        manager, scene = _manager_with_joystick()

        event = HashableEvent(pygame.JOYBALLMOTION, ball=0, rel=(5, -3), instance_id=0)
        manager.on_joy_ball_motion_event(event)

        assert _received(scene) == [('ball_motion', event)]
        assert manager.joysticks[0]._balls[0] == (5, -3)

    def test_ball_motion_routes_via_joy_fallback(self):
        """Ball motion should fall back to event.joy when instance_id is missing."""
        manager, scene = _manager_with_joystick()

        event = HashableEvent(pygame.JOYBALLMOTION, ball=0, rel=(5, -3), joy=0)
        manager.on_joy_ball_motion_event(event)

        assert _received(scene) == [('ball_motion', event)]

    def test_device_added_creates_proxy(self):
        """Device added should create a new joystick proxy."""
        _install_joysticks(
            descriptors=[_joystick_descriptor(device_index=0, instance_id=42, name='New Joystick')],
            counted_joysticks=0,
        )
        scene = JoystickRecordingScene()
        manager = JoystickEventManager(game=scene)

        event = HashableEvent(pygame.JOYDEVICEADDED, device_index=0, guid='guid')
        manager.on_joy_device_added_event(event)

        assert 42 in manager.joysticks
        assert manager.joysticks[42].get_name() == 'New Joystick'
        assert _received(scene) == [('device_added', event)]

    def test_device_added_duplicate_skipped(self):
        """Device added for existing instance_id should skip duplicate creation."""
        manager, scene = _manager_with_joystick(instance_id=42)
        existing_proxy = manager.joysticks[42]

        event = HashableEvent(pygame.JOYDEVICEADDED, device_index=0, guid='guid')
        manager.on_joy_device_added_event(event)

        # The existing proxy is not replaced, and the game is not told again
        assert manager.joysticks[42] is existing_proxy
        assert _received(scene) == []

    def test_device_removed_notifies_and_deletes(self):
        """Device removed should notify proxy then remove it."""
        manager, scene = _manager_with_joystick()

        event = HashableEvent(pygame.JOYDEVICEREMOVED, instance_id=0)
        manager.on_joy_device_removed_event(event)

        assert _received(scene) == [('device_removed', event)]
        assert 0 not in manager.joysticks

    def test_device_removed_missing_instance_is_noop(self):
        """Device removed for unknown instance_id should not crash."""
        manager, scene = _manager_without_joysticks()

        event = HashableEvent(pygame.JOYDEVICEREMOVED, instance_id=999)
        manager.on_joy_device_removed_event(event)

        assert _received(scene) == []

    def test_device_added_pygame_error_fallback(self, mocker):
        """Device added whose instance id lookup fails is keyed by its device index."""
        _fake_joystick_hardware(mocker, joystick_count=0)
        scene = JoystickRecordingScene()
        manager = JoystickEventManager(game=scene)

        # The device opens (the door's describe reads its instance id: call 1), but reading
        # the instance id for the key raises (call 2); the proxy's own open (a second device
        # object) works
        _fake_joystick_hardware(
            mocker,
            joystick_count=0,
            opens=[
                ScriptedJoystick(
                    device_index=7,
                    failing_calls={'get_instance_id': {2: pygame.error('no joystick')}},
                ),
                ScriptedJoystick(instance_id=70, device_index=7),
            ],
        )

        event = HashableEvent(pygame.JOYDEVICEADDED, device_index=7, guid='guid')
        manager.on_joy_device_added_event(event)

        # Should have created a proxy with device_index as key
        assert list(manager.joysticks) == [7]
        assert manager.joysticks[7].joystick.get_instance_id() == 70
        assert _received(scene) == [('device_added', event)]

    def test_manager_args_classmethod(self):
        """args() classmethod should return the parser with Joystick Options group."""
        parser = argparse.ArgumentParser()
        result = JoystickEventManager.args(parser)
        assert result is parser
        assert 'Joystick Options' in [group.title for group in parser._action_groups]


# ---------------------------------------------------------------------------
# Deeper coverage tests
# ---------------------------------------------------------------------------


class TestJoystickEventProxyWithoutInstanceId:
    """Test JoystickEventProxy initialization without instance_id."""

    def test_proxy_uses_joystick_id_when_no_instance_id(self):
        """Test proxy uses joystick_id as _id when instance_id is None."""
        _install_joysticks(descriptors=[_joystick_descriptor(device_index=3, instance_id=0)])

        proxy = JoystickEventManager.JoystickEventProxy(
            game=JoystickRecordingScene(), joystick_id=3
        )

        # When instance_id is None (default), should use joystick_id
        assert proxy._id == 3
        assert proxy._device_id == 3


class TestJoystickEventProxyOpensByDeviceIndex:
    """Test JoystickEventProxy opens by device index an instance id not opened yet."""

    def test_proxy_opens_an_unopened_instance_by_device_index(self, mocker):
        """Test proxy opens Joystick(joystick_id) through the devices door.

        pygame-ce has no Joystick.from_instance_id; an instance id the devices door has not
        opened yet is opened by its device index.
        """
        joystick_constructor = _fake_joystick_hardware(
            mocker, joystick_count=0, joysticks=ScriptedJoystick(name='Fallback Joystick')
        )

        proxy = JoystickEventManager.JoystickEventProxy(
            game=JoystickRecordingScene(),
            joystick_id=0,
            instance_id=99,
        )

        # Opened by device index, keyed by the instance id it was asked for
        joystick_constructor.assert_called_once_with(0)
        assert proxy._id == 99
        assert proxy.get_name() == 'Fallback Joystick'


class TestJoystickEventManagerInitWithJoysticks:
    """Test JoystickEventManager.__init__ when joysticks are present."""

    def test_init_creates_proxies_for_each_joystick(self):
        """Test __init__ creates proxy for each connected joystick."""
        _install_joysticks(
            descriptors=[
                _joystick_descriptor(device_index=0, instance_id=100),
                _joystick_descriptor(device_index=1, instance_id=101),
            ]
        )

        manager = JoystickEventManager(game=JoystickRecordingScene())

        assert list(manager.joysticks) == [100, 101]
        assert [proxy._device_id for proxy in manager.joysticks.values()] == [0, 1]


class TestJoystickEventManagerDeviceAddedFallbackIndex:
    """Test on_joy_device_added_event device_index fallback path."""

    def test_device_added_with_instance_id(self):
        """Test device added uses instance_id from get_instance_id."""
        _install_joysticks(
            descriptors=[_joystick_descriptor(device_index=5, instance_id=50)],
            counted_joysticks=0,
        )
        manager = JoystickEventManager(game=JoystickRecordingScene())

        event = HashableEvent(pygame.JOYDEVICEADDED, device_index=5, guid='guid-new')
        manager.on_joy_device_added_event(event)

        # Should have created proxy using instance_id as key
        assert list(manager.joysticks) == [50]


class TestJoystickEventManagerRoutingFallbacks:
    """Test JoystickEventManager routing fallback from instance_id to joy attribute."""

    def test_hat_motion_routes_via_joy(self):
        """Test hat motion falls back to event.joy."""
        manager, scene = _manager_with_joystick()
        event = HashableEvent(pygame.JOYHATMOTION, hat=0, value=(0, 1), joy=0)
        manager.on_joy_hat_motion_event(event)
        assert _received(scene) == [('hat_motion', event)]

    def test_ball_motion_routes_via_joy(self):
        """Test ball motion falls back to event.joy."""
        manager, scene = _manager_with_joystick()
        event = HashableEvent(pygame.JOYBALLMOTION, ball=0, rel=(1, -1), joy=0)
        manager.on_joy_ball_motion_event(event)
        assert _received(scene) == [('ball_motion', event)]

    def test_button_up_routes_via_joy(self):
        """Test button up falls back to event.joy."""
        manager, scene = _manager_with_joystick()
        event = HashableEvent(pygame.JOYBUTTONUP, button=2, joy=0)
        manager.on_joy_button_up_event(event)
        assert _received(scene) == [('button_up', event)]


class TestJoystickEventManagerDeviceRemovedEdge:
    """Test on_joy_device_removed_event edge cases."""

    def test_device_removed_clears_proxy(self):
        """Test device removed properly clears the proxy from joysticks dict."""
        manager, scene = _manager_with_joystick(instance_id=42)

        event = HashableEvent(pygame.JOYDEVICEREMOVED, instance_id=42)
        manager.on_joy_device_removed_event(event)

        assert _received(scene) == [('device_removed', event)]
        assert 42 not in manager.joysticks

    def test_device_removed_nonexistent_is_safe(self):
        """Test device removed for nonexistent instance_id does not crash."""
        manager, scene = _manager_without_joysticks()

        event = HashableEvent(pygame.JOYDEVICEREMOVED, instance_id=12345)
        manager.on_joy_device_removed_event(event)

        assert _received(scene) == []


# ---------------------------------------------------------------------------
# JoystickEvents interface tests, through the real manager
# ---------------------------------------------------------------------------


class TestJoystickEvents:
    """Test JoystickEvents interface functionality."""

    def test_joystick_events_interface(self):
        """Test JoystickEvents interface methods."""
        # Test that JoystickEvents has required abstract methods
        assert hasattr(JoystickEvents, 'on_joy_axis_motion_event')
        assert hasattr(JoystickEvents, 'on_joy_button_down_event')
        assert hasattr(JoystickEvents, 'on_joy_button_up_event')
        assert hasattr(JoystickEvents, 'on_joy_device_added_event')
        assert hasattr(JoystickEvents, 'on_joy_device_removed_event')
        assert hasattr(JoystickEvents, 'on_joy_hat_motion_event')
        assert hasattr(JoystickEvents, 'on_joy_ball_motion_event')

    def test_joystick_event_stubs_implementation(self, mocker):
        """A real Scene without its own joystick axis handler falls back to the stub.

        The stub raises UnhandledEventError under no_unhandled_events.
        """
        _install_joysticks(descriptors=[_joystick_descriptor(device_index=0, instance_id=0)])
        manager = JoystickEventManager(game=Scene(options=dict(NO_UNHANDLED_EVENTS_OPTIONS)))

        event = HashableEvent(pygame.JOYAXISMOTION, axis=0, value=0.5, instance_id=0)
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            manager.on_joy_axis_motion_event(event)

    def test_joy_axis_motion_event(self):
        """Test joystick axis motion event handling."""
        manager, scene = _manager_with_joystick()

        event = HashableEvent(pygame.JOYAXISMOTION, axis=0, value=0.5, instance_id=0)
        manager.on_joy_axis_motion_event(event)

        assert len(_received(scene)) == 1
        assert _received(scene)[0][1].axis == 0
        assert math.isclose(_received(scene)[0][1].value, 0.5)

    def test_joy_button_down_event(self):
        """Test joystick button down event handling."""
        manager, scene = _manager_with_joystick()

        manager.on_joy_button_down_event(
            HashableEvent(pygame.JOYBUTTONDOWN, button=0, instance_id=0)
        )

        assert len(_received(scene)) == 1
        assert _received(scene)[0][1].button == 0

    def test_joy_button_up_event(self):
        """Test joystick button up event handling."""
        manager, scene = _manager_with_joystick()

        manager.on_joy_button_up_event(HashableEvent(pygame.JOYBUTTONUP, button=0, instance_id=0))

        assert len(_received(scene)) == 1
        assert _received(scene)[0][1].button == 0

    def test_joy_hat_motion_event(self):
        """Test joystick hat motion event handling."""
        manager, scene = _manager_with_joystick()

        manager.on_joy_hat_motion_event(
            HashableEvent(pygame.JOYHATMOTION, hat=0, value=(0, 1), instance_id=0)
        )

        assert len(_received(scene)) == 1
        assert _received(scene)[0][1].hat == 0
        assert _received(scene)[0][1].value == (0, 1)

    def test_joy_ball_motion_event(self):
        """Test joystick ball motion event handling."""
        manager, scene = _manager_with_joystick()

        manager.on_joy_ball_motion_event(
            HashableEvent(pygame.JOYBALLMOTION, ball=0, rel=(10, 10), instance_id=0)
        )

        assert len(_received(scene)) == 1
        assert _received(scene)[0][1].type == pygame.JOYBALLMOTION
        assert _received(scene)[0][1].ball == 0
        assert _received(scene)[0][1].rel == (10, 10)

    def test_joy_device_added_event(self):
        """Test joystick device added event handling."""
        _install_joysticks(
            descriptors=[_joystick_descriptor(device_index=0, instance_id=0)],
            counted_joysticks=0,
        )
        scene = JoystickRecordingScene()
        manager = JoystickEventManager(game=scene)

        manager.on_joy_device_added_event(HashableEvent(pygame.JOYDEVICEADDED, device_index=0))

        assert len(_received(scene)) == 1
        assert _received(scene)[0][0] == 'device_added'
        assert _received(scene)[0][1].device_index == 0

    def test_joy_device_removed_event(self):
        """Test joystick device removed event handling."""
        manager, scene = _manager_with_joystick()

        manager.on_joy_device_removed_event(HashableEvent(pygame.JOYDEVICEREMOVED, instance_id=0))

        assert len(_received(scene)) == 1
        assert _received(scene)[0][0] == 'device_removed'
        assert _received(scene)[0][1].type == pygame.JOYDEVICEREMOVED
        assert _received(scene)[0][1].instance_id == 0

    def test_multiple_axis_events(self):
        """Test multiple axis motion events."""
        _install_joysticks(
            descriptors=[_joystick_descriptor(device_index=0, instance_id=0, axis_count=4)]
        )
        scene = JoystickRecordingScene()
        manager = JoystickEventManager(game=scene)

        for axis in range(4):  # Test first 4 axes
            manager.on_joy_axis_motion_event(
                HashableEvent(pygame.JOYAXISMOTION, axis=axis, value=0.5, instance_id=0)
            )

        assert [(received.type, received.axis) for _kind, received in _received(scene)] == [
            (pygame.JOYAXISMOTION, axis) for axis in range(4)
        ]
        assert all(math.isclose(value, 0.5) for value in manager.joysticks[0]._axes)

    def test_multiple_button_events(self):
        """Test multiple button events."""
        manager, scene = _manager_with_joystick()

        for button in range(8):  # Test first 8 buttons
            manager.on_joy_button_down_event(
                HashableEvent(pygame.JOYBUTTONDOWN, button=button, instance_id=0)
            )
            assert manager.joysticks[0]._buttons[button] is True
            manager.on_joy_button_up_event(
                HashableEvent(pygame.JOYBUTTONUP, button=button, instance_id=0)
            )
            assert manager.joysticks[0]._buttons[button] is False

        assert [(kind, received.type, received.button) for kind, received in _received(scene)] == [
            event
            for button in range(8)
            for event in (
                ('button_down', pygame.JOYBUTTONDOWN, button),
                ('button_up', pygame.JOYBUTTONUP, button),
            )
        ]

    def test_hat_directions(self):
        """Test joystick hat direction events."""
        manager, scene = _manager_with_joystick()

        # Every hat position pygame reports: centred, the four directions and the diagonals
        hat_directions = [
            (0, 0),
            (0, 1),
            (1, 0),
            (0, -1),
            (-1, 0),
            (1, 1),
            (1, -1),
            (-1, -1),
            (-1, 1),
        ]

        for direction in hat_directions:
            manager.on_joy_hat_motion_event(
                HashableEvent(pygame.JOYHATMOTION, hat=0, value=direction, instance_id=0)
            )
            assert manager.joysticks[0]._hats[0] == direction

        assert [received.value for _kind, received in _received(scene)] == hat_directions


class TestJoystickManager:
    """Test JoystickEventManager in isolation."""

    def test_joystick_manager_initialization(self):
        """Test JoystickEventManager initializes correctly."""
        manager, scene = _manager_without_joysticks()

        assert manager.game is scene
        assert manager.proxies == [scene]
        assert manager.joysticks == {}

    def test_joystick_manager_events(self):
        """Test joystick event handling through manager (events naming the joystick by joy)."""
        manager, scene = _manager_with_joystick()

        axis_event = HashableEvent(pygame.JOYAXISMOTION, joy=0, axis=0, value=0.5)
        down_event = HashableEvent(pygame.JOYBUTTONDOWN, joy=0, button=0)
        up_event = HashableEvent(pygame.JOYBUTTONUP, joy=0, button=0)
        manager.on_joy_axis_motion_event(axis_event)
        manager.on_joy_button_down_event(down_event)
        manager.on_joy_button_up_event(up_event)

        assert _received(scene) == [
            ('axis_motion', axis_event),
            ('button_down', down_event),
            ('button_up', up_event),
        ]


# ---------------------------------------------------------------------------
# The devices door (glitchygames/input/devices.py): opening and polling
# ---------------------------------------------------------------------------


class TestJoystickDevicesDoor:
    """Joysticks are opened through the registry and read from the frame's snapshot."""

    def test_joystick_proxy_opens_through_the_registry_and_reads_the_snapshot(self, mocker):
        """The proxy's caches come from the snapshot, by the opened device's instance id."""
        _install_joysticks(descriptors=[_joystick_descriptor(device_index=0, instance_id=9)])
        # Tripwire: the real joystick constructor (hardware) must never be reached
        real_joystick = mocker.patch('pygame.joystick.Joystick')
        set_current_input(
            snapshot=InputSnapshot(
                pressed_scancodes=frozenset(),
                modifiers=0,
                mouse_position=(0, 0),
                mouse_buttons=(False, False, False),
                mouse_focused=True,
                device_axes={9: (0.25, -1.0)},
                device_buttons={9: (True,)},
                device_hats={9: ((1, -1),)},
            )
        )

        proxy = JoystickEventManager.JoystickEventProxy(joystick_id=0, game=None)

        real_joystick.assert_not_called()
        assert proxy._axes == [0.25, -1.0]
        assert proxy._buttons == [True]
        assert proxy._hats == [(1, -1)]
        # Balls are not recorded: they read as still
        assert proxy._balls == [(0, 0)]

    def test_joystick_proxy_reuses_a_device_already_opened_for_its_instance_id(self, mocker):
        """A proxy for an instance id the registry already opened does not open it again."""
        registry = _install_joysticks(
            descriptors=[_joystick_descriptor(device_index=0, instance_id=9)]
        )
        opened = registry.open_joystick(device_index=0)
        open_spy = mocker.spy(registry, 'open_joystick')

        proxy = JoystickEventManager.JoystickEventProxy(joystick_id=0, instance_id=9, game=None)

        open_spy.assert_not_called()
        assert proxy.joystick is opened

    def test_joystick_manager_enumerates_and_opens_through_the_registry(self, mocker):
        """The manager counts and opens joysticks only through the registry."""
        _install_joysticks(descriptors=[_joystick_descriptor(device_index=0, instance_id=9)])
        # Tripwires: the real enumeration and constructor (hardware) must never be reached
        real_count = mocker.patch('pygame.joystick.get_count')
        real_joystick = mocker.patch('pygame.joystick.Joystick')

        manager = JoystickEventManager(game=JoystickRecordingScene())

        real_count.assert_not_called()
        real_joystick.assert_not_called()
        assert list(manager.joysticks) == [9]

    def test_joystick_device_added_resolves_the_instance_id_through_the_registry(self, mocker):
        """A hot-plugged joystick is opened once, through the registry, and keyed by instance."""
        registry = _install_joysticks(
            descriptors=[_joystick_descriptor(device_index=0, instance_id=9)]
        )
        manager = JoystickEventManager.__new__(JoystickEventManager)
        manager.joysticks = {}
        manager.game = JoystickRecordingScene()
        # Tripwire: the real joystick constructor (hardware) must never be reached
        real_joystick = mocker.patch('pygame.joystick.Joystick')
        open_spy = mocker.spy(registry, 'open_joystick')

        manager.on_joy_device_added_event(HashableEvent(pygame.JOYDEVICEADDED, device_index=0))

        real_joystick.assert_not_called()
        assert open_spy.call_count == 1
        assert list(manager.joysticks) == [9]

    def test_joystick_removal_makes_the_registry_forget_the_device(self):
        """A removed joystick is forgotten by the devices door, tracked or not."""
        registry = _install_joysticks(
            descriptors=[_joystick_descriptor(device_index=0, instance_id=9)]
        )
        registry.open_joystick(device_index=0)
        manager = JoystickEventManager.__new__(JoystickEventManager)
        manager.joysticks = {}
        manager.game = JoystickRecordingScene()

        manager.on_joy_device_removed_event(HashableEvent(pygame.JOYDEVICEREMOVED, instance_id=9))

        assert registry.joystick_for_instance(instance_id=9) is None

    def test_device_added_fallback_key_never_reuses_another_device(self, mocker):
        """When the instance id lookup fails, the device index is never used as an instance id.

        Device A (device index 0) has instance id 3. A device added at device index 3 whose
        first open fails must be opened by its device index, not handed device A.
        """
        # The default live doors, with SDL's joystick constructor faked (hardware)
        registry = active_sources().devices()
        device_a = ScriptedJoystick(instance_id=3)
        device_b = ScriptedJoystick(instance_id=7, device_index=3)
        _fake_joystick_hardware(
            mocker,
            joystick_count=0,
            opens=[device_a, pygame.error('not ready'), device_b],
        )
        registry.open_joystick(device_index=0)
        manager = JoystickEventManager.__new__(JoystickEventManager)
        manager.joysticks = {}
        manager.game = JoystickRecordingScene()

        manager.on_joy_device_added_event(HashableEvent(pygame.JOYDEVICEADDED, device_index=3))

        assert manager.joysticks[3].joystick is device_b
