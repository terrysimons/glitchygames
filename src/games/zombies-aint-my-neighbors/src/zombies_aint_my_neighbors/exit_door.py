"""The exit door: a garden gate in the top hedge that opens when a stage's neighbors are done.

Feature plan 7 (plans/2026-11-15-zombies-aint-my-neighbors-7-neighbors-and-lives.md), Task 7;
the props BOM's exit door. It stands shut (``closed``) until the scene opens it: then it swings
open (``opening``, 3 frames of 0.08 s) and glows (``open``, pulsing). A kid touching it once it
has swung all the way open (``is_passable``) clears the stage (the scene's to check), so a kid
waiting at the gate always sees it open. Not solid. Like every sprite here, it poses in
``dt_tick`` and ``update`` does nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, Self, override

from glitchygames.sprites import AnimatedSprite
from glitchygames.world import CoordinateSpace
from zombies_aint_my_neighbors.kid import SPRITES_DIRECTORY, TIME_TOLERANCE

if TYPE_CHECKING:
    import pygame

# The props BOM: opening is 3 frames of 0.08 s
OPENING_SECONDS: Final = 3 * 0.08
DOOR_SIZE: Final = 48


class ExitDoor(AnimatedSprite):
    """The garden gate out of the yard."""

    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(
        self, *, world_x: float, world_y: float, groups: pygame.sprite.LayeredDirty[Any] | None
    ) -> None:
        """Load the door, shut, and place it.

        Args:
            world_x: Its frame's left edge in the world.
            world_y: Its frame's top edge in the world.
            groups: The sprite group to join (a group of its own when None).

        """
        super().__init__(filename=str(SPRITES_DIRECTORY / 'exit_door.toml'), groups=groups)
        self.world_x = world_x
        self.world_y = world_y
        # Seconds since it began opening (None: shut)
        self._opened_seconds: float | None = None
        self._started_animation: str | None = None

    @property
    def is_open(self) -> bool:
        """Whether the door has been opened (it may still be swinging)."""
        return self._opened_seconds is not None

    @property
    def is_passable(self) -> bool:
        """Whether a kid may leave through it: it has swung all the way open, so it is seen to."""
        return (
            self._opened_seconds is not None
            and self._opened_seconds >= OPENING_SECONDS - TIME_TOLERANCE
        )

    def open(self) -> None:
        """Swing the door open (nothing new if it already is)."""
        if self._opened_seconds is None:
            self._opened_seconds = 0.0

    def dt_tick(self, dt: float) -> None:
        """Pose the door: shut, swinging open, or glowing.

        Args:
            dt: The frame's time, in seconds.

        """
        if self._opened_seconds is None:
            name = 'closed'
        else:
            self._opened_seconds += dt
            swinging = self._opened_seconds < OPENING_SECONDS - TIME_TOLERANCE
            name = 'opening' if swinging else 'open'
        if name != self._started_animation:
            self.play(name)
            self._started_animation = name
        AnimatedSprite.update(self, dt)

    @override
    def update(self: Self, dt: float = 0.016) -> None:
        """Do nothing: it poses in ``dt_tick`` only."""
