"""Tests for scene transition effects.

Tests focus on state machine behavior (progress, completion, lifecycle)
rather than pixel-level rendering, since pygame surfaces may not render
correctly in parallel test environments with mocked display surfaces.
"""

from __future__ import annotations

import pygame
import pytest

from glitchygames.transitions.base import Transition, TransitionState
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

    def test_completes_in_duration(self, surfaces: tuple) -> None:
        """Wipe completes after the specified duration."""
        old, new, _screen = surfaces
        wipe = WipeTransition(direction='left', duration=0.6)
        wipe.start(old, new)
        assert wipe.update(0.7) is True
