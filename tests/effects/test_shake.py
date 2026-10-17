"""Tests for screen shake math."""

import math
import random

import pytest

from glitchygames.effects.shake import (
    RumbleSettings,
    ScreenShake,
    Shake,
    ShakeAxis,
    ShakeStyle,
)

SEED = 1234
ALL_STYLES = list(ShakeStyle)


def _shaker(**kwargs):
    return ScreenShake(random_source=random.Random(SEED), **kwargs)


class TestShakeValidation:
    """Constructor validation for shake settings."""

    @pytest.mark.parametrize(
        ('field', 'value'),
        [('strength', -1.0), ('duration', 0.0), ('duration', -0.1), ('frequency', 0.0)],
    )
    def test_invalid_values_raise(self, field, value):
        settings = {'style': ShakeStyle.NOISE, 'strength': 5.0, 'duration': 0.5, 'frequency': 10.0}
        settings[field] = value
        with pytest.raises(ValueError, match=field):
            Shake(**settings)

    @pytest.mark.parametrize('value', [-0.01, 1.01])
    def test_rumble_settings_range(self, value):
        with pytest.raises(ValueError, match='low_frequency'):
            RumbleSettings(low_frequency=value, high_frequency=0.5)

    @pytest.mark.parametrize('value', [-0.1, 1.1])
    def test_intensity_range(self, value):
        with pytest.raises(ValueError, match='intensity'):
            ScreenShake(intensity=value)


class TestShakeLifetime:
    """Shake duration, envelope limits, and clearing."""

    @pytest.mark.parametrize('style', ALL_STYLES)
    def test_offset_is_zero_at_and_after_duration(self, style):
        shaker = _shaker()
        shaker.add(Shake(style=style, strength=10.0, duration=0.5, frequency=12.0))
        shaker.update(0.5)
        assert shaker.offset == (0.0, 0.0)
        assert not shaker.is_active

    @pytest.mark.parametrize('style', ALL_STYLES)
    def test_one_large_dt_past_the_end_leaves_no_jolt(self, style):
        """Review focus 1: a dt that jumps past the end gives zero, never a final offset."""
        shaker = _shaker()
        shaker.add(
            Shake(
                style=style,
                strength=10.0,
                duration=0.2,
                frequency=12.0,
                rumble=RumbleSettings(low_frequency=1.0, high_frequency=1.0),
            )
        )
        shaker.update(0.15)
        shaker.update(0.5)
        assert shaker.offset == (0.0, 0.0)
        assert shaker.rumble_levels == (0.0, 0.0)
        assert shaker.rumble_remaining == 0.0

    @pytest.mark.parametrize('style', ALL_STYLES)
    def test_offset_never_exceeds_strength(self, style):
        shaker = _shaker()
        shaker.add(Shake(style=style, strength=10.0, duration=1.0, frequency=9.0))
        for _ in range(60):
            shaker.update(1.0 / 60.0)
            offset_x, offset_y = shaker.offset
            assert abs(offset_x) <= 10.0 + 1e-9
            assert abs(offset_y) <= 10.0 + 1e-9

    def test_clear_stops_everything(self):
        shaker = _shaker()
        shaker.add(Shake(style=ShakeStyle.JITTER, strength=5.0, duration=1.0, frequency=30.0))
        shaker.clear()
        assert shaker.offset == (0.0, 0.0)
        assert not shaker.is_active


class TestShakeStyles:
    """Per-style movement and axis restriction."""

    def test_bounce_starts_at_full_strength_and_decays_to_one_percent(self):
        shaker = _shaker()
        shaker.add(
            Shake(
                style=ShakeStyle.BOUNCE,
                strength=10.0,
                duration=1.0,
                frequency=5.0,
                axis=ShakeAxis.VERTICAL,
            )
        )
        assert shaker.offset == pytest.approx((0.0, 10.0))
        shaker.update(0.999999)
        assert abs(shaker.offset[1]) <= 0.1 + 1e-6

    def test_noise_magnitude_follows_remaining_squared(self):
        """Trauma model: the envelope is remaining**2 (offset bounded by it)."""
        shaker = _shaker()
        shaker.add(Shake(style=ShakeStyle.NOISE, strength=10.0, duration=1.0, frequency=20.0))
        shaker.update(0.5)
        bound = 10.0 * 0.5**2
        assert max(abs(value) for value in shaker.offset) <= bound + 1e-9

    def test_noise_is_smooth_between_frames(self):
        shaker = _shaker()
        shaker.add(Shake(style=ShakeStyle.NOISE, strength=10.0, duration=2.0, frequency=4.0))
        previous = shaker.offset
        for _ in range(30):
            shaker.update(1.0 / 240.0)
            current = shaker.offset
            assert math.dist(previous, current) < 2.0
            previous = current

    def test_jitter_holds_value_within_a_step(self):
        shaker = _shaker()
        shaker.add(Shake(style=ShakeStyle.JITTER, strength=10.0, duration=10.0, frequency=1.0))
        shaker.update(0.1)
        first = shaker.offset
        shaker.update(0.1)
        second = shaker.offset
        # Same step: same direction, magnitude shrinks only by the linear decay
        assert first[0] * second[0] >= 0
        assert first[1] * second[1] >= 0

    @pytest.mark.parametrize(
        ('axis', 'zero_index'), [(ShakeAxis.HORIZONTAL, 1), (ShakeAxis.VERTICAL, 0)]
    )
    def test_axis_restricts_movement(self, axis, zero_index):
        shaker = _shaker()
        shaker.add(
            Shake(style=ShakeStyle.JITTER, strength=10.0, duration=1.0, frequency=30.0, axis=axis)
        )
        shaker.update(0.01)
        assert shaker.offset[zero_index] == 0.0

    def test_same_seed_same_offsets(self):
        offsets = []
        for _ in range(2):
            shaker = _shaker()
            shaker.add(Shake(style=ShakeStyle.NOISE, strength=8.0, duration=1.0, frequency=10.0))
            shaker.update(0.3)
            offsets.append(shaker.offset)
        assert offsets[0] == offsets[1]


class TestStackingAndLimits:
    """Stacking, the offset cap, and player intensity."""

    def test_offsets_sum(self):
        single = _shaker()
        single.add(Shake(style=ShakeStyle.BOUNCE, strength=5.0, duration=1.0, frequency=2.0))
        double = _shaker()
        for _ in range(2):
            double.add(Shake(style=ShakeStyle.BOUNCE, strength=5.0, duration=1.0, frequency=2.0))
        assert double.offset == pytest.approx(tuple(2 * value for value in single.offset))

    def test_cap_holds_for_any_stack(self):
        shaker = _shaker(maximum_offset=12.0)
        for style in ALL_STYLES:
            for _ in range(5):
                shaker.add(Shake(style=style, strength=30.0, duration=1.0, frequency=7.0))
        for _ in range(30):
            shaker.update(1.0 / 60.0)
            assert all(abs(value) <= 12.0 for value in shaker.offset)

    def test_intensity_scales_and_zero_disables(self):
        shaker = _shaker()
        shaker.add(Shake(style=ShakeStyle.BOUNCE, strength=10.0, duration=1.0, frequency=2.0))
        full = shaker.offset
        shaker.intensity = 0.5
        assert shaker.offset == pytest.approx(tuple(value / 2 for value in full))
        shaker.intensity = 0.0
        assert shaker.offset == (0.0, 0.0)


class TestRumbleLevels:
    """Controller rumble levels and remaining time."""

    def test_per_motor_maximum_scaled_by_decay_and_strength(self):
        shaker = _shaker(maximum_offset=20.0)
        shaker.add(
            Shake(
                style=ShakeStyle.BOUNCE,
                strength=10.0,
                duration=1.0,
                frequency=2.0,
                rumble=RumbleSettings(low_frequency=1.0, high_frequency=0.2),
            )
        )
        shaker.add(
            Shake(
                style=ShakeStyle.JITTER,
                strength=20.0,
                duration=0.5,
                frequency=2.0,
                rumble=RumbleSettings(low_frequency=0.1, high_frequency=0.8),
            )
        )
        low, high = shaker.rumble_levels
        assert low == pytest.approx(1.0 * 1.0 * (10.0 / 20.0))
        assert high == pytest.approx(0.8 * 1.0 * 1.0)

    def test_remaining_is_longest_rumbling_shake(self):
        shaker = _shaker()
        shaker.add(
            Shake(
                style=ShakeStyle.NOISE,
                strength=5.0,
                duration=0.3,
                frequency=5.0,
                rumble=RumbleSettings(low_frequency=0.5, high_frequency=0.5),
            )
        )
        shaker.add(Shake(style=ShakeStyle.NOISE, strength=5.0, duration=0.9, frequency=5.0))
        shaker.update(0.1)
        assert shaker.rumble_remaining == pytest.approx(0.2)

    def test_rumble_decays_with_its_shake(self):
        shaker = _shaker(maximum_offset=10.0)
        shaker.add(
            Shake(
                style=ShakeStyle.JITTER,
                strength=10.0,
                duration=1.0,
                frequency=5.0,
                rumble=RumbleSettings(low_frequency=1.0, high_frequency=1.0),
            )
        )
        shaker.update(0.75)
        assert shaker.rumble_levels == pytest.approx((0.25, 0.25))
