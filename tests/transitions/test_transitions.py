"""Tests for scene transition effects.

Tests focus on state machine behavior (progress, completion, lifecycle)
rather than pixel-level rendering, since pygame surfaces may not render
correctly in parallel test environments with mocked display surfaces.
"""

from __future__ import annotations

import math

import pygame
import pytest

from glitchygames.transitions.base import Transition, TransitionState
from glitchygames.transitions.elevator import ElevatorTransition
from glitchygames.transitions.fade import CrossfadeTransition, FadeTransition
from glitchygames.transitions.slide import SlideTransition
from glitchygames.transitions.wipe import WipeTransition


@pytest.fixture
def surfaces() -> tuple[pygame.Surface, pygame.Surface, pygame.Surface]:
    """Create test surfaces: old, new, screen."""
    if not pygame.get_init():
        pygame.init()
    old = pygame.Surface((200, 150))
    new = pygame.Surface((200, 150))
    screen = pygame.Surface((200, 150))
    return old, new, screen


class TestTransitionLifecycle:
    """Tests for the Transition base class lifecycle."""

    def test_initial_state_is_idle(self) -> None:
        """New transition starts in IDLE state."""
        transition = Transition()
        assert transition.state == TransitionState.IDLE

    def test_start_sets_running(self, surfaces: tuple) -> None:
        """Starting a transition sets state to RUNNING."""
        old, new, _screen = surfaces
        transition = Transition(duration=1.0)
        transition.start(old, new)
        assert transition.state == TransitionState.RUNNING

    def test_progress_starts_at_zero(self, surfaces: tuple) -> None:
        """Progress is 0 after start, before first update."""
        old, new, _screen = surfaces
        transition = Transition(duration=1.0)
        transition.start(old, new)
        assert transition.progress == 0.0

    def test_update_advances_progress(self, surfaces: tuple) -> None:
        """Update advances progress toward completion."""
        old, new, _screen = surfaces
        transition = Transition(duration=1.0)
        transition.start(old, new)
        transition.update(0.5)
        assert 0.4 < transition.progress < 0.6

    def test_update_returns_false_while_running(self, surfaces: tuple) -> None:
        """Update returns False while still in progress."""
        old, new, _screen = surfaces
        transition = Transition(duration=1.0)
        transition.start(old, new)
        assert transition.update(0.3) is False
        assert transition.state == TransitionState.RUNNING

    def test_update_returns_true_when_complete(self, surfaces: tuple) -> None:
        """Update returns True when duration is exceeded."""
        old, new, _screen = surfaces
        transition = Transition(duration=0.5)
        transition.start(old, new)
        assert transition.update(0.6) is True
        assert transition.state == TransitionState.COMPLETE

    def test_zero_duration_completes_immediately(self, surfaces: tuple) -> None:
        """Zero-duration transition completes on first update."""
        old, new, _screen = surfaces
        transition = Transition(duration=0.0)
        transition.start(old, new)
        assert transition.update(0.001) is True
        assert transition.state == TransitionState.COMPLETE

    def test_multiple_updates_accumulate(self, surfaces: tuple) -> None:
        """Multiple updates accumulate elapsed time."""
        old, new, _screen = surfaces
        transition = Transition(duration=1.0, easing='linear')
        transition.start(old, new)
        transition.update(0.3)
        transition.update(0.3)
        transition.update(0.3)
        assert transition.progress > 0.8

    def test_eased_progress_differs_from_raw(self, surfaces: tuple) -> None:
        """Eased progress differs from raw for non-linear easing."""
        old, new, _screen = surfaces
        transition = Transition(duration=1.0, easing='ease_in_quad')
        transition.start(old, new)
        transition.update(0.5)
        # ease_in_quad at 0.5 = 0.25 (not 0.5)
        assert transition.eased_progress < transition.progress

    def test_update_after_completion_reports_done_without_advancing(
        self, surfaces: tuple, mocker
    ) -> None:
        """A completed transition stays complete and no longer calls on_update."""
        old, new, _screen = surfaces
        on_update = mocker.Mock()
        transition = Transition(duration=0.5, on_update=on_update)
        transition.start(old, new)
        assert transition.update(0.5) is True
        on_update.reset_mock()
        assert transition.update(0.5) is True
        assert transition.state == TransitionState.COMPLETE
        on_update.assert_not_called()

    def test_update_before_start_reports_done(self) -> None:
        """An idle transition has nothing to run, so update reports it finished."""
        transition = Transition(duration=1.0)
        assert transition.update(0.1) is True
        assert transition.state == TransitionState.IDLE
        assert transition.progress == 0.0

    def test_render_does_not_crash_before_start(self, surfaces: tuple) -> None:
        """Render before start is a no-op (no crash)."""
        _old, _new, screen = surfaces
        transition = Transition()
        transition.render(screen)  # Should not raise

    def test_render_does_not_crash_during(self, surfaces: tuple) -> None:
        """Render during transition does not crash."""
        old, new, screen = surfaces
        transition = Transition(duration=1.0)
        transition.start(old, new)
        transition.update(0.5)
        transition.render(screen)  # Should not raise


class TestFadeTransition:
    """Tests for FadeTransition lifecycle and rendering."""

    def test_completes_in_duration(self, surfaces: tuple) -> None:
        """Fade completes after the specified duration."""
        old, new, _screen = surfaces
        fade = FadeTransition(duration=0.5)
        fade.start(old, new)
        assert fade.update(0.6) is True

    def test_render_does_not_crash(self, surfaces: tuple) -> None:
        """Render at various progress points does not crash."""
        old, new, screen = surfaces
        fade = FadeTransition(duration=1.0, color=(0, 0, 0))
        fade.start(old, new)
        for dt in (0.1, 0.2, 0.2, 0.3, 0.2):
            fade.update(dt)
            fade.render(screen)

    def test_custom_color(self, surfaces: tuple) -> None:
        """Custom fade color is accepted without error."""
        old, new, screen = surfaces
        fade = FadeTransition(duration=0.5, color=(255, 255, 255))
        fade.start(old, new)
        fade.update(0.25)
        fade.render(screen)


class TestCrossfadeTransition:
    """Tests for CrossfadeTransition lifecycle."""

    def test_completes_in_duration(self, surfaces: tuple) -> None:
        """Crossfade completes after the specified duration."""
        old, new, _screen = surfaces
        crossfade = CrossfadeTransition(duration=0.8)
        crossfade.start(old, new)
        assert crossfade.update(0.9) is True

    def test_render_does_not_crash(self, surfaces: tuple) -> None:
        """Render at various progress points does not crash."""
        old, new, screen = surfaces
        crossfade = CrossfadeTransition(duration=1.0)
        crossfade.start(old, new)
        for dt in (0.2, 0.3, 0.3, 0.2):
            crossfade.update(dt)
            crossfade.render(screen)


class TestSlideTransition:
    """Tests for SlideTransition lifecycle and directions."""

    def test_all_directions_accepted(self, surfaces: tuple) -> None:
        """All four directions create valid transitions."""
        old, new, screen = surfaces
        for direction in ('left', 'right', 'up', 'down'):
            slide = SlideTransition(direction=direction, duration=0.5)
            slide.start(old, new)
            slide.update(0.25)
            slide.render(screen)

    def test_completes_in_duration(self, surfaces: tuple) -> None:
        """Slide completes after the specified duration."""
        old, new, _screen = surfaces
        slide = SlideTransition(direction='up', duration=0.8)
        slide.start(old, new)
        assert slide.update(0.9) is True

    def test_unknown_direction_is_refused(self) -> None:
        """A direction the slide does not know raises ValueError (#138.4)."""
        with pytest.raises(ValueError, match="'diagonal'"):
            SlideTransition(direction='diagonal')

    def test_slide_up_for_elevator(self, surfaces: tuple) -> None:
        """Slide up (elevator transition) works without error."""
        old, new, screen = surfaces
        slide = SlideTransition(direction='up', duration=0.8, easing='ease_in_out_quad')
        slide.start(old, new)
        for _ in range(10):
            slide.update(0.08)
            slide.render(screen)


class TestWipeTransition:
    """Tests for WipeTransition lifecycle and directions."""

    def test_all_directions_accepted(self, surfaces: tuple) -> None:
        """All four directions create valid transitions."""
        old, new, screen = surfaces
        for direction in ('left', 'right', 'up', 'down'):
            wipe = WipeTransition(direction=direction, duration=0.5)
            wipe.start(old, new)
            wipe.update(0.25)
            wipe.render(screen)

    def test_unknown_direction_is_refused(self) -> None:
        """A direction the wipe does not know raises ValueError (#138.4)."""
        with pytest.raises(ValueError, match="'diagonal'"):
            WipeTransition(direction='diagonal')

    def test_completes_in_duration(self, surfaces: tuple) -> None:
        """Wipe completes after the specified duration."""
        old, new, _screen = surfaces
        wipe = WipeTransition(direction='left', duration=0.6)
        wipe.start(old, new)
        assert wipe.update(0.7) is True


class TestTransitionHooks:
    """Tests for on_update, cue firing, and easing slope hooks."""

    def test_on_update_called_every_frame_with_transition(self, surfaces, mocker):
        on_update = mocker.Mock()
        transition = Transition(duration=1.0, on_update=on_update)
        transition.start(surfaces[0], surfaces[1])
        transition.update(0.1)
        transition.update(0.1)
        assert on_update.call_count == 2
        on_update.assert_called_with(transition)

    def test_cue_fires_once_when_crossed(self, surfaces, mocker):
        callback = mocker.Mock()
        transition = Transition(duration=1.0)
        transition.add_cue(0.5, callback)
        transition.start(surfaces[0], surfaces[1])
        transition.update(0.4)
        callback.assert_not_called()
        transition.update(0.1)  # progress == 0.5 exactly: "<=" fires
        transition.update(0.1)
        callback.assert_called_once()

    def test_cue_at_zero_fires_on_first_update(self, surfaces, mocker):
        callback = mocker.Mock()
        transition = Transition(duration=1.0)
        transition.add_cue(0.0, callback)
        transition.start(surfaces[0], surfaces[1])
        transition.update(0.0)
        callback.assert_called_once()

    def test_large_dt_fires_all_passed_cues_in_order(self, surfaces):
        order = []
        transition = Transition(duration=1.0)
        transition.add_cue(1.0, lambda: order.append('end'))
        transition.add_cue(0.2, lambda: order.append('early'))
        transition.add_cue(0.6, lambda: order.append('middle'))
        transition.start(surfaces[0], surfaces[1])
        assert transition.update(5.0) is True
        assert order == ['early', 'middle', 'end']

    def test_cues_fire_before_on_update(self, surfaces):
        order = []
        transition = Transition(duration=1.0, on_update=lambda _transition: order.append('update'))
        transition.add_cue(1.0, lambda: order.append('cue'))
        transition.start(surfaces[0], surfaces[1])
        transition.update(1.0)
        assert order == ['cue', 'update']

    @pytest.mark.parametrize('progress', [-0.01, 1.01])
    def test_cue_progress_validated(self, progress):
        with pytest.raises(ValueError, match='progress'):
            Transition().add_cue(progress, lambda: None)

    def test_eased_velocity_of_linear_is_one(self):
        assert Transition(easing='linear').eased_velocity_at(0.5) == pytest.approx(1.0)

    def test_eased_velocity_at_ends_is_one_sided(self):
        transition = Transition(easing='ease_in_sine')
        assert transition.eased_velocity_at(1.0) == pytest.approx(math.pi / 2, rel=1e-2)
        assert transition.eased_velocity_at(0.0) == pytest.approx(0.0, abs=1e-2)


class BlitAreaRecordingSurface(pygame.Surface):
    """Surface that records the area of every blit.

    pygame's C-level Surface.blit is read-only, so mocker.spy cannot wrap it.
    """

    def __init__(self, size: tuple[int, int]) -> None:
        """Initialize the recording surface."""
        super().__init__(size)
        self.blit_areas: list[pygame.Rect | None] = []

    def blit(
        self,
        source: pygame.Surface,
        dest: tuple[int, int] | pygame.Rect,
        area: pygame.Rect | None = None,
        special_flags: int = 0,
    ) -> pygame.Rect:
        """Record the area argument, then blit normally."""
        self.blit_areas.append(area)
        return super().blit(source, dest, area=area, special_flags=special_flags)


class TestElevatorTransitionClamp:
    """Tests that the elevator keeps its scroll offset inside the composite."""

    @pytest.mark.parametrize('easing', ['ease_in_back', 'ease_in_elastic', 'ease_out_back'])
    def test_overshooting_easing_stays_inside_composite(self, surfaces, easing):
        old, new, _screen = surfaces
        screen = BlitAreaRecordingSurface((200, 150))
        transition = ElevatorTransition(duration=1.0, easing=easing)
        transition.start(old, new)
        for _ in range(20):
            transition.update(0.05)
            transition.render(screen)
            area = screen.blit_areas[0]
            assert 0 <= area.top <= transition._total_scroll
            screen.blit_areas.clear()


# A 32-bit format with an alpha mask: cocoa's display format (glitchygames/opacity.py). Its
# screenshots carry it, so the elevator's surfaces made in their format carry alpha as on macOS
PER_PIXEL_ALPHA_MASKS = (0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
OLD_FLOOR_COLOR = (110, 75, 45)
NEW_FLOOR_COLOR = (30, 30, 35)


def per_pixel_alpha_surface(
    *, size: tuple[int, int], color: tuple[int, int, int]
) -> pygame.Surface:
    """Return an opaque surface in cocoa's display format, as its screenshots are.

    Returns:
        The surface, filled with the colour at alpha 255.

    """
    surface = pygame.Surface(size, pygame.SRCALPHA, depth=32, masks=PER_PIXEL_ALPHA_MASKS)
    surface.fill((*color, 255))
    return surface


class TestElevatorTransitionOnPerPixelAlphaDisplays:
    """The ride on a display whose pixels carry alpha (macOS): no black box around the player.

    The composite was a plain Surface: on cocoa it takes the display's format (an alpha mask
    without SRCALPHA), and blending the screenshots onto it left alpha 0 (BUGS.md #142). The
    display then held alpha 0 under the player, where pygame's blit copies a source pixel
    outright, so the player's transparent pixels were drawn as black.
    """

    def test_the_player_shows_the_floor_through_its_transparent_pixels(self):
        """Around the player's one opaque pixel the old floor shows, opaque."""
        old = per_pixel_alpha_surface(size=(200, 150), color=OLD_FLOOR_COLOR)
        new = per_pixel_alpha_surface(size=(200, 150), color=NEW_FLOOR_COLOR)
        player = pygame.Surface((10, 20), pygame.SRCALPHA)
        player.set_at((5, 10), (200, 0, 0, 255))
        screen = per_pixel_alpha_surface(size=(200, 150), color=(0, 0, 0))
        transition = ElevatorTransition(duration=1.0, player_surface=player)
        transition.start(old, new)

        transition.render(screen)

        # The platform is centred, a third of the height up; the player stands on it, centred
        player_left = (200 - 60) // 2 + (60 - 10) // 2
        player_top = 150 - 150 // 3 - 20
        assert screen.get_at((player_left, player_top)) == (*OLD_FLOOR_COLOR, 255)
        assert screen.get_at((player_left + 5, player_top + 10)) == (200, 0, 0, 255)

    def test_the_composite_is_opaque_in_the_screenshots_format(self):
        """Every composite pixel has alpha 255, in the format the screenshots came in."""
        old = per_pixel_alpha_surface(size=(200, 150), color=OLD_FLOOR_COLOR)
        new = per_pixel_alpha_surface(size=(200, 150), color=NEW_FLOOR_COLOR)
        transition = ElevatorTransition(duration=1.0, shaft_height=40)
        transition.start(old, new)

        composite = transition._composite
        assert composite is not None
        assert composite.get_masks() == PER_PIXEL_ALPHA_MASKS
        alpha_values = pygame.image.tobytes(composite, 'RGBA')[3::4]
        assert set(alpha_values) == {255}
