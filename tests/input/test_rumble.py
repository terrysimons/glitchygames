"""Tests for the rumble controller."""

import random

import pygame
import pytest

from glitchygames.effects.shake import RumbleSettings, ScreenShake, Shake, ShakeStyle
from glitchygames.input.rumble import RumbleController, connected_rumble_devices

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


class TestConnectedRumbleDevices:
    """Test device discovery in controller and joystick modes."""

    def test_controller_mode_uses_controller_proxies(self, mocker):
        manager = mocker.Mock()
        manager.controllers = {3: 'proxy-a', 7: 'proxy-b'}
        assert connected_rumble_devices(manager) == ['proxy-a', 'proxy-b']

    def test_joystick_mode_opens_every_joystick(self, mocker):
        mocker.patch('pygame.joystick.get_count', return_value=2)
        joystick = mocker.patch('pygame.joystick.Joystick', side_effect=['first', 'second'])
        assert connected_rumble_devices(None) == ['first', 'second']
        assert joystick.call_count == 2

    def test_joystick_vanishing_before_open_is_skipped(self, mocker):
        mocker.patch('pygame.joystick.get_count', return_value=2)
        mocker.patch(
            'pygame.joystick.Joystick', side_effect=[pygame.error('device gone'), 'second']
        )
        assert connected_rumble_devices(None) == ['second']
