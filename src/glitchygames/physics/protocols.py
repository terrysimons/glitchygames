"""Pairwise protocols for cross-system physics communication.

Each protocol defines the minimal interface a system needs to read from
or write to another system. Sprites satisfy protocols via structural
subtyping -- no explicit inheritance required.

Example:
    A collision system needs HasVelocity to push objects apart.
    An animation state machine needs HasGroundState + HasFacing
    to pick the right animation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pygame


@runtime_checkable
class HasVelocity(Protocol):
    """Object with position and velocity for physics integration."""

    world_x: float
    world_y: float
    velocity_x: float
    velocity_y: float


@runtime_checkable
class HasGroundState(Protocol):
    """Object with ground contact state for collision response."""

    on_ground: bool


@runtime_checkable
class HasFacing(Protocol):
    """Object with facing direction for animation selection."""

    facing_right: bool
    velocity_x: float


@runtime_checkable
class HasMass(Protocol):
    """Object with mass for force-based physics."""

    mass: float


@runtime_checkable
class HasDirtyFlag(Protocol):
    """Object that supports dirty-rect rendering."""

    dirty: int


@runtime_checkable
class HasRect(Protocol):
    """Object with a pygame Rect for collision detection."""

    rect: pygame.Rect
