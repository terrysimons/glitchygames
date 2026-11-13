"""A render target per engine context: an inner game draws on its own surface.

An inner context (an Arcade tile; plans/2026-11-12-arcade-3-inner-game.md) renders into an
offscreen surface of its own and never opens, resizes, captions, presents or sets the icon of the
window, nor changes SDL's driver variables (rows S1 and S2 of plans/2026-10-25-engine-context.md).
A context is inner exactly when it has a render target (``is_inner_context()``). The default
context has none, so every ordinary game draws on the display as before.

``display_surface()`` is what the engine reads instead of ``pygame.display.get_surface()``: the
context's render target when it has one, else the display surface.

A hosted start: ``GameEngine.start()`` in an inner context (or in a context that asked with
``request_hosted_start()``) builds the game up to its first frame and returns instead of running
its blocking loop, keeping the engine for its host (``note_started_engine``), which takes it with
``take_started_engine()`` and steps the engine's frames itself. The host can so call any game's
or launcher's own entry point unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import pygame

from glitchygames.engine_context import ContextSlot, current_context

if TYPE_CHECKING:
    from glitchygames.engine.game_engine import GameEngine


class RenderTarget:
    """One context's render target and its hosted start.

    A plain class, not a frozen model: it holds a Surface and is changed in place.

    Attributes:
        surface: The context's offscreen surface; None when the context owns the display (an
            ordinary game).
        started_engine: The engine a hosted start built in the context, until its host takes it.
        hosted_start_requested: True when ``GameEngine.start()`` hands its engine to a host
            although the context has no render target.

    """

    def __init__(self: Self) -> None:
        """Start with no render target, no started engine and no hosted start asked for."""
        self.surface: pygame.Surface | None = None
        self.started_engine: GameEngine | None = None
        self.hosted_start_requested: bool = False


RENDER_TARGET_SLOT: ContextSlot[RenderTarget] = ContextSlot(
    name='glitchygames.render_target.target', factory=RenderTarget
)


def set_render_target(*, surface: pygame.Surface | None) -> None:
    """Make a surface the current context's render target.

    Args:
        surface: The surface the context draws on; None to draw on the display again.

    """
    current_context().value(slot=RENDER_TARGET_SLOT).surface = surface


def render_target() -> pygame.Surface | None:
    """Return the current context's render target.

    Returns:
        The render target, or None when the context owns the display.

    """
    return current_context().value(slot=RENDER_TARGET_SLOT).surface


def is_inner_context() -> bool:
    """Tell whether the current context is inner: it draws on a render target of its own.

    Returns:
        True when the context has a render target (it owns no window or process service).

    """
    return render_target() is not None


def display_surface() -> pygame.Surface | None:
    """Return what the current context draws on.

    Returns:
        The context's render target, else the display surface (None before a display exists).

    """
    target = render_target()
    return target if target is not None else pygame.display.get_surface()


def request_hosted_start() -> None:
    """Make ``GameEngine.start()`` in the current context a hosted start (build, then return)."""
    current_context().value(slot=RENDER_TARGET_SLOT).hosted_start_requested = True


def hosted_start_requested() -> bool:
    """Tell whether ``GameEngine.start()`` in the current context hands its engine to a host.

    Returns:
        True in an inner context, or when ``request_hosted_start()`` asked for it.

    """
    target = current_context().value(slot=RENDER_TARGET_SLOT)
    return target.surface is not None or target.hosted_start_requested


def note_started_engine(*, engine: GameEngine) -> None:
    """Keep the engine a hosted start built in the current context, for its host.

    Args:
        engine: The engine, built up to its first frame.

    """
    current_context().value(slot=RENDER_TARGET_SLOT).started_engine = engine


def take_started_engine() -> GameEngine | None:
    """Return the engine a hosted start built in the current context, and forget it.

    Returns:
        The engine, once; None when no hosted start built one since it was last taken.

    """
    target = current_context().value(slot=RENDER_TARGET_SLOT)
    engine = target.started_engine
    target.started_engine = None
    return engine
