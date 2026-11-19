"""Tests for glitchygames/render_target.py: an inner context draws on a surface of its own.

An inner context is one with a render target (decision 1 of
plans/2026-11-12-arcade-3-inner-game.md). The default context has none, so it draws on the
display; an inner context's sprites, scenes and frames use its target and never the window.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, override

import pygame

from glitchygames.engine_context import EngineContext
from glitchygames.live_sources import LiveSources
from glitchygames.opacity import OPAQUE
from glitchygames.render_target import (
    display_surface,
    hosted_start_requested,
    is_inner_context,
    render_target,
    request_hosted_start,
    set_render_target,
    take_started_engine,
)
from glitchygames.scenes import SceneManager
from glitchygames.sources import install_sources
from glitchygames.sprites import Sprite

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

# An inner context's render target: smaller than any test display, so a size read from the
# window could never pass for it
TARGET_SIZE = (64, 48)
# A 32-bit format with an alpha mask and without SRCALPHA: cocoa's display format, which a
# render target made in the display's format has there (glitchygames/opacity.py)
ALPHA_MASKS = (0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
# A colour whose alpha is 0: a black hole in a window showing per-pixel alpha
TRANSPARENT_BLUE = (0, 0, 255, 0)
# The sprite an inner context makes
SPRITE_WIDTH = 2
SPRITE_HEIGHT = 1


class PresentingDoors(LiveSources):
    """Live doors that present every frame even in an inner context (a headless replay's do)."""

    @property
    @override
    def presents_frames(self: Self) -> bool:
        """Present every frame.

        Returns:
            True.

        """
        return True


def target_with_alpha() -> pygame.Surface:
    """Return a render target in cocoa's display format, every pixel's alpha 0.

    Returns:
        The surface.

    """
    target = pygame.Surface(TARGET_SIZE, depth=32, masks=ALPHA_MASKS)
    target.fill(TRANSPARENT_BLUE)
    return target


class TestTheDefaultContext:
    """The default context owns the display: it has no render target and is not inner."""

    def test_the_default_context_draws_on_the_display(self):
        """display_surface() is the display's surface, and the context is not inner."""
        assert render_target() is None
        assert not is_inner_context()
        assert display_surface() is pygame.display.get_surface()

    def test_the_default_context_starts_games_as_it_always_did(self):
        """No hosted start is asked for, and no started engine is waiting."""
        assert not hosted_start_requested()
        assert take_started_engine() is None

    def test_live_play_in_the_default_context_presents_its_frames(self):
        """The live doors present every frame of a game that owns the window."""
        assert LiveSources(random_seed=1).presents_frames


class TestAnInnerContext:
    """A context with a render target draws on it and is inner."""

    def test_an_inner_context_reads_its_own_target(self):
        """Inside, the target is what it draws on; the default context still has the window."""
        context = EngineContext(name='inner')
        target = pygame.Surface(TARGET_SIZE)
        with context.active():
            set_render_target(surface=target)
            inner_reading = (render_target(), is_inner_context(), display_surface())

        assert inner_reading == (target, True, target)
        assert display_surface() is pygame.display.get_surface()

    def test_clearing_the_target_gives_the_display_back(self):
        """set_render_target(surface=None) makes the context an ordinary one again."""
        context = EngineContext(name='inner')
        with context.active():
            set_render_target(surface=pygame.Surface(TARGET_SIZE))
            set_render_target(surface=None)
            reading = (render_target(), is_inner_context(), display_surface())

        assert reading == (None, False, pygame.display.get_surface())

    def test_a_sprite_made_inner_measures_against_the_target(self):
        """A sprite's screen, and its width and height, are the render target's."""
        context = EngineContext(name='inner')
        target = pygame.Surface(TARGET_SIZE)
        with context.active():
            set_render_target(surface=target)
            sprite = Sprite(x=0, y=0, width=SPRITE_WIDTH, height=SPRITE_HEIGHT)

        assert sprite.screen is target
        assert (sprite.screen_width, sprite.screen_height) == TARGET_SIZE

    def test_an_inner_context_asks_for_a_hosted_start(self):
        """start() in an inner context hands its engine to the host; the default's does not."""
        context = EngineContext(name='inner')
        with context.active():
            set_render_target(surface=pygame.Surface(TARGET_SIZE))
            inner_requested = hosted_start_requested()

        assert inner_requested
        assert not hosted_start_requested()

    def test_a_context_that_owns_the_window_may_ask_for_a_hosted_start(self):
        """request_hosted_start() asks for one in a context without a render target."""
        context = EngineContext(name='hosted')
        with context.active():
            request_hosted_start()
            reading = (is_inner_context(), hosted_start_requested())

        assert reading == (False, True)
        assert not hosted_start_requested()

    def test_inner_live_play_never_presents_its_frames(self):
        """The live doors in an inner context present nothing: the host shows the target."""
        context = EngineContext(name='inner')
        with context.active():
            set_render_target(surface=pygame.Surface(TARGET_SIZE))
            presents = LiveSources(random_seed=1).presents_frames

        assert not presents


class TestAnInnerFrame:
    """An inner frame stays on the render target, made opaque (decision 6, Review Focus 5)."""

    def test_an_inner_frame_on_a_target_with_alpha_leaves_no_alpha_below_opaque(
        self, mocker: MockerFixture
    ):
        """Every pixel is opaque after the frame, its colour kept, and the window untouched."""
        flip = mocker.spy(pygame.display, 'flip')
        update = mocker.spy(pygame.display, 'update')
        context = EngineContext(name='inner')
        target = target_with_alpha()
        with context.active():
            set_render_target(surface=target)
            manager = SceneManager()
            manager.screen = target
            manager._present_frame(full_update=False)

        alphas = {
            target.get_at((x, y)).a for x in range(TARGET_SIZE[0]) for y in range(TARGET_SIZE[1])
        }
        assert alphas == {OPAQUE}
        assert tuple(target.get_at((0, 0))) == (0, 0, 255, OPAQUE)
        flip.assert_not_called()
        update.assert_not_called()

    def test_an_inner_frame_is_never_presented_whatever_its_doors_say(self, mocker: MockerFixture):
        """Doors that present every frame still present nothing inner, even a full update."""
        flip = mocker.spy(pygame.display, 'flip')
        context = EngineContext(name='inner')
        target = target_with_alpha()
        with context.active():
            set_render_target(surface=target)
            install_sources(sources=PresentingDoors(random_seed=1))
            manager = SceneManager()
            manager.screen = target
            manager._present_frame(full_update=True)

        assert target.get_at((TARGET_SIZE[0] - 1, TARGET_SIZE[1] - 1)).a == OPAQUE
        flip.assert_not_called()
