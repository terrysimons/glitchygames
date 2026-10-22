"""Tests for the rumble controller."""

import random

import pygame
import pytest

from glitchygames.effects.shake import RumbleSettings, ScreenShake, Shake, ShakeStyle
from glitchygames.input.devices import (
    JOYSTICK_COUNT_CALL,
    DeviceDescriptor,
    EnumerationAnswer,
    ReplayDeviceRegistry,
)
from glitchygames.input.rumble import ConnectedRumbleDevices, RumbleController
from glitchygames.sources import active_sources

SHAKER_SEED = 3


def _rumbling_shaker(duration=1.0, low=1.0, high=0.5, strength=32.0):
    """Build a ScreenShake holding one rumbling JITTER shake."""
    shaker = ScreenShake(random_source=random.Random(SHAKER_SEED))
    shaker.add(
        Shake(
            style=ShakeStyle.JITTER,
            strength=strength,
            duration=duration,
            frequency=10.0,
            rumble=RumbleSettings(low_frequency=low, high_frequency=high),
        )
    )
    return shaker


@pytest.fixture
def devices(mocker):
    """Two mock rumble devices."""
    return [mocker.Mock(), mocker.Mock()]


class TestRumbleController:
    """Test the combined-level rumble sending."""

    def test_sends_levels_to_every_device(self, devices):
        controller = RumbleController()
        controller.update(shakers=[_rumbling_shaker()], dt=0.0, devices=lambda: devices)
        for device in devices:
            device.rumble.assert_called_once_with(1.0, 0.5, 1000)

    def test_duration_is_never_zero(self, devices):
        """0 ms means rumble forever in SDL, so tiny remainders round up to 1 ms."""
        controller = RumbleController()
        shaker = _rumbling_shaker(duration=0.0001)
        controller.update(shakers=[shaker], dt=0.0, devices=lambda: devices)
        assert devices[0].rumble.call_args.args[2] == 1

    def test_does_not_resend_small_changes(self, devices):
        controller = RumbleController()
        shaker = _rumbling_shaker(duration=10.0)
        controller.update(shakers=[shaker], dt=0.0, devices=lambda: devices)
        shaker.update(0.1)  # JITTER decays linearly: 1% change
        controller.update(shakers=[shaker], dt=0.1, devices=lambda: devices)
        assert devices[0].rumble.call_count == 1

    def test_resends_when_levels_drop(self, devices):
        controller = RumbleController()
        shaker = _rumbling_shaker(duration=1.0)
        controller.update(shakers=[shaker], dt=0.0, devices=lambda: devices)
        shaker.update(0.2)
        controller.update(shakers=[shaker], dt=0.2, devices=lambda: devices)
        assert devices[0].rumble.call_count == 2

    def test_resends_before_sent_rumble_expires(self, devices):
        """No gap mid-shake: refresh when the sent rumble is about to run out."""
        controller = RumbleController()
        shaker = _rumbling_shaker(duration=10.0)
        controller.update(shakers=[shaker], dt=0.0, devices=lambda: devices)
        # Same level, but the sent 10 s rumble has only 0.04 s left (inside the margin)
        shaker.update(9.96)
        controller.update(shakers=[shaker], dt=9.96, devices=lambda: devices)
        assert devices[0].rumble.call_count == 2

    def test_no_resend_while_time_left_above_margin(self, devices):
        controller = RumbleController()
        shaker = _rumbling_shaker(duration=10.0)
        controller.update(shakers=[shaker], dt=0.0, devices=lambda: devices)
        for _ in range(4):
            shaker.update(0.1)
            controller.update(shakers=[shaker], dt=0.1, devices=lambda: devices)
        assert devices[0].rumble.call_count == 1

    def test_longer_same_level_shake_extends_rumble(self, devices):
        controller = RumbleController()
        short_shaker = _rumbling_shaker(duration=1.0)
        controller.update(shakers=[short_shaker], dt=0.0, devices=lambda: devices)
        long_shaker = _rumbling_shaker(duration=5.0)
        controller.update(shakers=[short_shaker, long_shaker], dt=0.0, devices=lambda: devices)
        assert devices[0].rumble.call_count == 2
        assert devices[0].rumble.call_args.args[2] == 5000

    def test_stops_when_shakes_end(self, devices):
        controller = RumbleController()
        shaker = _rumbling_shaker(duration=0.1)
        controller.update(shakers=[shaker], dt=0.0, devices=lambda: devices)
        shaker.update(0.2)
        controller.update(shakers=[shaker], dt=0.2, devices=lambda: devices)
        for device in devices:
            device.stop_rumble.assert_called_once()

    def test_intensity_zero_sends_nothing(self, devices):
        controller = RumbleController(intensity=0.0)
        controller.update(shakers=[_rumbling_shaker()], dt=0.0, devices=lambda: devices)
        devices[0].rumble.assert_not_called()

    def test_combines_shakers_per_motor(self, devices):
        controller = RumbleController()
        controller.update(
            shakers=[_rumbling_shaker(low=0.2, high=0.9), _rumbling_shaker(low=0.7, high=0.1)],
            dt=0.0,
            devices=lambda: devices,
        )
        devices[0].rumble.assert_called_once_with(0.7, 0.9, 1000)

    def test_device_errors_are_skipped(self, mocker):
        """Review focus 4: an unplugged device must not stop rumble on the others."""
        broken = mocker.Mock()
        broken.rumble.side_effect = pygame.error('device gone')
        working = mocker.Mock()
        controller = RumbleController()
        controller.update(shakers=[_rumbling_shaker()], dt=0.0, devices=lambda: [broken, working])
        working.rumble.assert_called_once()

    def test_stop_errors_are_skipped(self, mocker):
        """An unplugged device must not stop the stop signal reaching the others."""
        broken = mocker.Mock()
        broken.stop_rumble.side_effect = pygame.error('device gone')
        working = mocker.Mock()
        controller = RumbleController()
        shaker = _rumbling_shaker(duration=0.1)
        controller.update(shakers=[shaker], dt=0.0, devices=lambda: [broken, working])
        shaker.update(0.2)
        controller.update(shakers=[shaker], dt=0.2, devices=lambda: [broken, working])
        working.stop_rumble.assert_called_once()

    def test_intensity_out_of_range_raises(self):
        with pytest.raises(ValueError, match='intensity'):
            RumbleController(intensity=1.5)

    def test_sent_levels_reflects_last_send(self, devices):
        """sent_levels reports the (low, high) levels last sent to the devices."""
        controller = RumbleController()
        assert controller.sent_levels == (0.0, 0.0)
        controller.update(shakers=[_rumbling_shaker()], dt=0.0, devices=lambda: devices)
        assert controller.sent_levels == (1.0, 0.5)


class TestSustainedRumble:
    """A held level (e.g. the elevator hum) combined with shakes."""

    def test_sustained_alone_sends_short_slices_and_refreshes_before_expiry(self, devices):
        controller = RumbleController()
        controller.set_sustained(low_frequency=0.25, high_frequency=0.05)
        controller.update(shakers=[], dt=0.0, devices=lambda: devices)
        devices[0].rumble.assert_called_once_with(0.25, 0.05, 250)

        controller.update(shakers=[], dt=0.1, devices=lambda: devices)  # 0.15 s left
        assert devices[0].rumble.call_count == 1
        controller.update(shakers=[], dt=0.1, devices=lambda: devices)  # 0.05 s left: refresh
        assert devices[0].rumble.call_count == 2
        assert devices[0].rumble.call_args.args == (0.25, 0.05, 250)

    def test_sustained_and_shake_take_per_motor_maximum(self, devices):
        controller = RumbleController()
        controller.set_sustained(low_frequency=0.25, high_frequency=0.9)
        controller.update(shakers=[_rumbling_shaker()], dt=0.0, devices=lambda: devices)
        # Shake gives (1.0, 0.5): low from the shake, high from the sustained level
        devices[0].rumble.assert_called_once_with(1.0, 0.9, 1000)

    def test_clear_sustained_stops_rumble_when_no_shakes_remain(self, devices):
        controller = RumbleController()
        controller.set_sustained(low_frequency=0.25, high_frequency=0.05)
        controller.update(shakers=[], dt=0.0, devices=lambda: devices)
        controller.clear_sustained()
        assert controller.sustained_levels == (0.0, 0.0)
        controller.update(shakers=[], dt=0.016, devices=lambda: devices)
        devices[0].stop_rumble.assert_called_once()

    def test_clear_sustained_leaves_shake_rumble(self, devices):
        controller = RumbleController()
        controller.set_sustained(low_frequency=0.25, high_frequency=0.05)
        controller.clear_sustained()
        controller.update(shakers=[_rumbling_shaker()], dt=0.0, devices=lambda: devices)
        devices[0].rumble.assert_called_once_with(1.0, 0.5, 1000)

    @pytest.mark.parametrize(
        ('low_frequency', 'high_frequency'), [(-0.1, 0.0), (1.1, 0.0), (0.0, -0.1), (0.0, 1.1)]
    )
    def test_set_sustained_validates_range(self, low_frequency, high_frequency):
        controller = RumbleController()
        with pytest.raises(ValueError, match=r'between 0\.0 and 1\.0'):
            controller.set_sustained(low_frequency=low_frequency, high_frequency=high_frequency)
        assert controller.sustained_levels == (0.0, 0.0)

    def test_intensity_scales_sustained(self, devices):
        controller = RumbleController(intensity=0.5)
        controller.set_sustained(low_frequency=0.4, high_frequency=0.2)
        controller.update(shakers=[], dt=0.0, devices=lambda: devices)
        devices[0].rumble.assert_called_once_with(0.2, 0.1, 250)


class TestRumblePulse:
    """A finite one-shot rumble that fades linearly to zero."""

    def test_pulse_alone_sends_levels_then_fades_and_stops_at_duration(self, devices):
        controller = RumbleController()
        controller.pulse(low_frequency=1.0, high_frequency=0.5, duration=1.0)
        controller.update(shakers=[], dt=0.0, devices=lambda: devices)
        devices[0].rumble.assert_called_once_with(1.0, 0.5, 1000)

        controller.update(shakers=[], dt=0.5, devices=lambda: devices)  # half duration
        assert devices[0].rumble.call_args.args[:2] == (0.5, 0.25)

        controller.update(shakers=[], dt=0.5, devices=lambda: devices)  # exactly the duration
        devices[0].stop_rumble.assert_called_once()

    def test_pulse_contributes_exactly_zero_at_duration(self, devices):
        controller = RumbleController()
        controller.pulse(low_frequency=1.0, high_frequency=1.0, duration=0.5)
        controller.update(shakers=[], dt=0.5, devices=lambda: devices)
        devices[0].rumble.assert_not_called()

    def test_one_large_dt_past_the_end_leaves_no_final_rumble(self, devices):
        controller = RumbleController()
        controller.pulse(low_frequency=1.0, high_frequency=1.0, duration=0.5)
        controller.update(shakers=[], dt=0.0, devices=lambda: devices)
        controller.update(shakers=[], dt=10.0, devices=lambda: devices)
        assert devices[0].rumble.call_count == 1
        devices[0].stop_rumble.assert_called_once()

    def test_pulse_sustained_and_shake_take_per_motor_maximum(self, devices):
        controller = RumbleController()
        controller.set_sustained(low_frequency=0.25, high_frequency=0.9)
        controller.pulse(low_frequency=0.6, high_frequency=0.1, duration=2.0)
        shaker = _rumbling_shaker(duration=1.0, low=0.4, high=0.3)
        controller.update(shakers=[shaker], dt=0.0, devices=lambda: devices)
        # low: pulse 0.6 beats shake 0.4 and sustained 0.25; high: sustained 0.9
        # The send lasts as long as the longest remaining pulse (2.0 s)
        devices[0].rumble.assert_called_once_with(0.6, 0.9, 2000)

    @pytest.mark.parametrize(
        ('low_frequency', 'high_frequency'), [(-0.1, 0.0), (1.1, 0.0), (0.0, -0.1), (0.0, 1.1)]
    )
    def test_pulse_validates_levels(self, low_frequency, high_frequency):
        controller = RumbleController()
        with pytest.raises(ValueError, match=r'between 0\.0 and 1\.0'):
            controller.pulse(
                low_frequency=low_frequency, high_frequency=high_frequency, duration=1.0
            )

    @pytest.mark.parametrize('duration', [0.0, -1.0])
    def test_pulse_validates_duration(self, duration):
        controller = RumbleController()
        with pytest.raises(ValueError, match='duration'):
            controller.pulse(low_frequency=0.5, high_frequency=0.5, duration=duration)

    def test_intensity_scales_pulse(self, devices):
        controller = RumbleController(intensity=0.5)
        controller.pulse(low_frequency=0.8, high_frequency=0.4, duration=1.0)
        controller.update(shakers=[], dt=0.0, devices=lambda: devices)
        devices[0].rumble.assert_called_once_with(0.4, 0.2, 1000)

    def test_clear_sustained_leaves_pulse_running(self, devices):
        controller = RumbleController()
        controller.set_sustained(low_frequency=0.25, high_frequency=0.05)
        controller.pulse(low_frequency=0.8, high_frequency=0.4, duration=1.0)
        controller.clear_sustained()
        controller.update(shakers=[], dt=0.0, devices=lambda: devices)
        devices[0].rumble.assert_called_once_with(0.8, 0.4, 1000)

    def test_clear_pulses_stops_the_pulse(self, devices):
        controller = RumbleController()
        controller.pulse(low_frequency=0.8, high_frequency=0.4, duration=1.0)
        controller.update(shakers=[], dt=0.0, devices=lambda: devices)
        controller.clear_pulses()
        controller.update(shakers=[], dt=0.016, devices=lambda: devices)
        devices[0].stop_rumble.assert_called_once()


class TestConnectedRumbleDevices:
    """Test device discovery in controller and joystick modes."""

    def test_controller_mode_uses_controller_proxies(self, mocker):
        manager = mocker.Mock()
        manager.controllers = {3: 'proxy-a', 7: 'proxy-b'}
        assert ConnectedRumbleDevices().find(controller_manager=manager) == ['proxy-a', 'proxy-b']

    def test_joystick_mode_opens_every_joystick(self, mocker):
        registry = mocker.Mock()
        registry.joystick_count.return_value = 2
        registry.open_joystick.side_effect = ['first', 'second']
        mocker.patch.object(active_sources(), 'devices', return_value=registry)
        assert ConnectedRumbleDevices().find(controller_manager=None) == ['first', 'second']
        assert registry.open_joystick.call_args_list == [
            mocker.call(device_index=0),
            mocker.call(device_index=1),
        ]

    def test_joystick_vanishing_before_open_is_skipped(self, mocker):
        registry = mocker.Mock()
        registry.joystick_count.return_value = 2
        registry.open_joystick.side_effect = [pygame.error('device gone'), 'second']
        mocker.patch.object(active_sources(), 'devices', return_value=registry)
        assert ConnectedRumbleDevices().find(controller_manager=None) == ['second']

    def test_joysticks_are_opened_once_while_the_count_holds(self, mocker):
        """Each send asks the count only: the joysticks opened before are rumbled again."""
        registry = mocker.Mock()
        registry.joystick_count.return_value = 2
        registry.open_joystick.side_effect = ['first', 'second', 'third']
        mocker.patch.object(active_sources(), 'devices', return_value=registry)
        finder = ConnectedRumbleDevices()
        assert finder.find(controller_manager=None) == ['first', 'second']
        assert finder.find(controller_manager=None) == ['first', 'second']
        assert registry.open_joystick.call_count == 2
        assert registry.joystick_count.call_count == 2

    def test_a_changed_count_or_other_doors_open_the_joysticks_again(self, mocker):
        registry = mocker.Mock()
        registry.joystick_count.return_value = 1
        registry.open_joystick.side_effect = ['first', 'first again', 'second']
        devices_door = mocker.patch.object(active_sources(), 'devices', return_value=registry)
        finder = ConnectedRumbleDevices()
        assert finder.find(controller_manager=None) == ['first']
        registry.joystick_count.return_value = 2
        assert finder.find(controller_manager=None) == ['first again', 'second']
        other_registry = mocker.Mock()
        other_registry.joystick_count.return_value = 2
        other_registry.open_joystick.side_effect = ['other first', 'other second']
        devices_door.return_value = other_registry
        assert finder.find(controller_manager=None) == ['other first', 'other second']

    def test_joystick_mode_in_a_replay_rumbles_stand_ins_not_hardware(self, mocker):
        descriptor = DeviceDescriptor(
            kind='joystick',
            device_index=0,
            instance_id=5,
            name='Pad',
            guid=None,
            axis_count=0,
            button_count=0,
            hat_count=0,
            ball_count=0,
        )
        registry = ReplayDeviceRegistry(
            descriptors=[descriptor],
            enumeration_answers=[
                EnumerationAnswer(call=JOYSTICK_COUNT_CALL, device_index=None, value=1)
            ],
        )
        mocker.patch.object(active_sources(), 'devices', return_value=registry)
        real_count = mocker.patch('pygame.joystick.get_count')
        real_joystick = mocker.patch('pygame.joystick.Joystick')

        devices = ConnectedRumbleDevices().find(controller_manager=None)

        assert [device.get_instance_id() for device in devices] == [5]
        assert devices[0].rumble(1.0, 1.0, 100) is True
        real_count.assert_not_called()
        real_joystick.assert_not_called()
