"""Tests for screen shake math."""

import math
import random

import pygame
import pytest

from glitchygames.effects import shake as shake_module
from glitchygames.effects.shake import (
    RumbleSettings,
    ScreenShake,
    Shake,
    ShakeAxis,
    ShakeStyle,
)
from glitchygames.randomness import RANDOM_STREAM_KIND, reset_streams, stream_seed
from glitchygames.scenes import SceneManager

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

    def test_default_random_source_is_the_shake_stream(self, mocker):
        """Without a random_source, a shake draws from random_stream('shake') of the run seed.

        The stream is looked up when the shake starts, so a ScreenShake created before the
        engine seeded (the SceneManager's) still follows the run's seed.
        """
        stream_lookup = mocker.patch(
            'glitchygames.effects.shake.random_stream', wraps=shake_module.random_stream
        )
        shaker = ScreenShake()
        reset_streams(seed=SEED)
        shaker.add(Shake(style=ShakeStyle.JITTER, strength=10.0, duration=1.0, frequency=30.0))
        shaker.update(0.01)

        reference = ScreenShake(
            random_source=random.Random(
                stream_seed(kind=RANDOM_STREAM_KIND, master_seed=SEED, name='shake')
            )
        )
        reference.add(Shake(style=ShakeStyle.JITTER, strength=10.0, duration=1.0, frequency=30.0))
        reference.update(0.01)
        assert shaker.offset == reference.offset
        stream_lookup.assert_called_once_with('shake')


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


@pytest.fixture
def scene_manager_with_screen(mocker):
    """Provide a SceneManager with a real surface and patched display flip/update.

    Yields:
        The manager, the flip mock and the update mock.

    """
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((64, 48))
    manager = SceneManager()
    manager.screen = pygame.Surface((64, 48))
    manager.active_scene = mocker.Mock(rects=[])
    flip = mocker.patch('pygame.display.flip')
    update = mocker.patch('pygame.display.update')
    yield manager, flip, update
    manager.screen_shake.clear()


class TestRumbleStrengthScaling:
    """scale_with_strength=False makes rumble absolute."""

    @staticmethod
    def _levels(*, strength, scale_with_strength=None):
        shaker = _shaker(maximum_offset=32.0)
        rumble_arguments = {'low_frequency': 1.0, 'high_frequency': 0.5}
        if scale_with_strength is not None:
            rumble_arguments['scale_with_strength'] = scale_with_strength
        shaker.add(
            Shake(
                style=ShakeStyle.JITTER,
                strength=strength,
                duration=1.0,
                frequency=5.0,
                rumble=RumbleSettings(**rumble_arguments),
            )
        )
        shaker.update(0.5)  # Decay 0.5
        return shaker.rumble_levels

    @pytest.mark.parametrize('strength', [1.0, 14.0, 32.0, 100.0])
    def test_absolute_rumble_ignores_strength(self, strength):
        assert self._levels(strength=strength, scale_with_strength=False) == pytest.approx((
            0.5,
            0.25,
        ))

    def test_default_still_scales_with_strength(self):
        assert RumbleSettings(low_frequency=1.0, high_frequency=1.0).scale_with_strength is True
        assert self._levels(strength=16.0) == pytest.approx((0.25, 0.125))


class TestScreenShakePresentation:
    """SCREEN shake is applied at present time and never leaks into the display surface."""

    def _paint_marker(self, screen):
        screen.fill((0, 0, 255))
        screen.set_at((10, 10), (255, 0, 0))

    def test_shaken_frame_is_presented_shifted_and_screen_restored(
        self, scene_manager_with_screen, mocker
    ):
        manager, flip, _update = scene_manager_with_screen
        self._paint_marker(manager.screen)
        manager.screen_shake.add(
            Shake(
                style=ShakeStyle.BOUNCE,
                strength=4.0,
                duration=1.0,
                frequency=1.0,
                axis=ShakeAxis.VERTICAL,
            )
        )
        presented = {}

        def capture_flip():
            presented['marker_moved'] = manager.screen.get_at((10, 14))[:3] == (255, 0, 0)
            presented['top_strip_black'] = manager.screen.get_at((30, 1))[:3] == (0, 0, 0)

        flip.side_effect = capture_flip
        manager._present_frame(full_update=False)
        assert presented == {'marker_moved': True, 'top_strip_black': True}
        # Between presents the display surface holds the unshifted frame
        assert manager.screen.get_at((10, 10))[:3] == (255, 0, 0)
        assert manager.screen.get_at((30, 1))[:3] == (0, 0, 255)

    def test_first_frame_after_shake_is_a_full_flip(self, scene_manager_with_screen):
        manager, flip, update = scene_manager_with_screen
        manager.screen_shake.add(
            Shake(style=ShakeStyle.BOUNCE, strength=4.0, duration=0.1, frequency=1.0)
        )
        manager._present_frame(full_update=False)
        manager.screen_shake.update(0.2)
        flip.reset_mock()
        manager._present_frame(full_update=False)
        flip.assert_called_once()
        update.assert_not_called()
        flip.reset_mock()
        manager._present_frame(full_update=False)  # Back to normal dirty-rect updates
        flip.assert_not_called()

    def test_unshaken_frame_uses_existing_update_path(self, scene_manager_with_screen, mocker):
        manager, flip, _update = scene_manager_with_screen
        update_display = mocker.patch.object(manager, '_update_display')
        manager._present_frame(full_update=False)
        update_display.assert_called_once()
        flip.assert_not_called()


class TestRumbleIndependentOfScreenShakeIntensity:
    """Players can turn off on-screen motion and keep rumble (spec revision 3)."""

    def test_zero_intensity_gives_no_offset_but_keeps_rumble(self):
        shaker = _shaker(intensity=0.0)
        shaker.add(
            Shake(
                style=ShakeStyle.JITTER,
                strength=10.0,
                duration=1.0,
                frequency=5.0,
                rumble=RumbleSettings(low_frequency=1.0, high_frequency=0.5),
            )
        )
        shaker.update(0.1)
        assert shaker.offset == (0, 0)
        assert max(shaker.rumble_levels) > 0.0


class TestTransitionScreenshotIsUnshaken:
    """The old-scene screenshot of a transition is taken with the WORLD shake cleared."""

    def test_world_shake_cleared_and_sprites_repositioned_before_capture(
        self, scene_manager_with_screen, mocker
    ):
        from glitchygames.scenes import Scene

        manager, _flip, _update = scene_manager_with_screen
        manager.screen = pygame.display.get_surface()
        assert manager.screen is not None

        class CameraScene(Scene):
            """A scene whose single marker is positioned through its camera."""

            def __init__(self):
                super().__init__()
                self.marker_world_x = 20.0

            def apply_camera_to_sprites(self):
                self.marker_screen_x, _ = self.camera.apply(self.marker_world_x, 0.0)

            def render(self, screen):
                screen.fill((0, 0, 0))
                screen.set_at((self.marker_screen_x, 10), (255, 0, 0))

        old_scene = CameraScene()
        manager.active_scene = old_scene
        old_scene.apply_camera_to_sprites()
        old_scene.camera.shake_effect.add(
            Shake(
                style=ShakeStyle.BOUNCE,
                strength=8.0,
                duration=1.0,
                frequency=1.0,
                axis=ShakeAxis.HORIZONTAL,
            )
        )
        old_scene.camera.shake_effect.update(0.1)
        old_scene.apply_camera_to_sprites()
        assert old_scene.marker_screen_x != 20  # Shaken before the transition starts

        order = []
        real_apply = old_scene.apply_camera_to_sprites

        def spy_apply():
            order.append('apply_camera_to_sprites')
            real_apply()

        mocker.patch.object(old_scene, 'apply_camera_to_sprites', side_effect=spy_apply)
        transition = mocker.Mock()
        transition.start.side_effect = lambda old, new: order.append('transition.start')
        captured = {}
        transition.start.side_effect = lambda old, new: (
            order.append('transition.start'),
            captured.update(old=old),
        )
        mocker.patch.object(manager, '_cleanup_current_scene')
        mocker.patch.object(manager, '_setup_new_scene')
        mocker.patch.object(manager, '_configure_active_scene')

        manager._start_transition(Scene(), transition)

        assert not old_scene.camera.shake_effect.is_active
        assert order.index('apply_camera_to_sprites') < order.index('transition.start')
        assert captured['old'].get_at((20, 10))[:3] == (255, 0, 0)
