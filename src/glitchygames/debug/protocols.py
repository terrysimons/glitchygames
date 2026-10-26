"""Protocols the debug overlay recognises (structural typing, no inheritance needed)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import pygame

    from glitchygames.camera import Camera2D


@runtime_checkable
class PhysicsState(Protocol):
    """Read-only physics state (matches glitchygames.physics.body.PhysicsBody).

    Attributes:
        velocity_x (float): Horizontal velocity in world units per second.
        velocity_y (float): Vertical velocity in world units per second.
        world_x (float): Horizontal world position.
        world_y (float): Vertical world position.
        on_ground (bool): Whether the body is resting on a surface.

    """

    velocity_x: float
    velocity_y: float
    world_x: float
    world_y: float
    on_ground: bool


@runtime_checkable
class HasPhysicsBody(Protocol):
    """An object exposing a physics body as `physics`.

    Attributes:
        physics (PhysicsState): The object's physics body.

    """

    physics: PhysicsState


class InspectedScene(Protocol):
    """The scene the overlay inspects (normally a glitchygames.scenes.Scene).

    The overlay reads its camera; `all_sprites` and `collisions` are optional and read with
    getattr, so they are not members.
    """

    @property
    def camera(self) -> Camera2D:
        """The scene's camera, for the camera panel and the debug_draw hooks."""
        ...


@runtime_checkable
class DebugDrawable(Protocol):
    """A scene or sprite that adds its own debug annotations."""

    def debug_draw(self, surface: pygame.Surface, camera: Camera2D) -> None:
        """Draw game-specific debug annotations onto the presented frame.

        Args:
            surface (pygame.Surface): The frame being presented; draw onto it in place.
            camera (Camera2D): The active camera, for converting world coordinates to screen.

        """
        ...
