"""Camera system for viewport tracking and world-to-screen coordinate conversion."""

from __future__ import annotations

from glitchygames.examples.brave_adventurer.constants import CAMERA_LEAD


class Camera:
    """Tracks the player and converts world coordinates to screen coordinates.

    The camera keeps the player a fixed distance from the left edge of the
    viewport. It only scrolls horizontally (vertical is always 0).
    """

    def __init__(self, screen_width: int, screen_height: int) -> None:
        """Initialize the camera.

        Args:
            screen_width: The width of the display in pixels.
            screen_height: The height of the display in pixels.

        """
        self.world_x: float = 0.0
        self.world_y: float = 0.0
        self.screen_width = screen_width
        self.screen_height = screen_height

    def update(self, player_world_x: float) -> None:
        """Update camera position to track the player.

        Keeps the player CAMERA_LEAD pixels from the left edge of the viewport.
        The camera never scrolls left past the world origin.

        Args:
            player_world_x: The player's X position in world coordinates.

        """
        self.world_x = max(0.0, player_world_x - CAMERA_LEAD)

    def apply(self, world_x: float, world_y: float) -> tuple[int, int]:
        """Convert world coordinates to screen coordinates.

        Args:
            world_x: X position in world space.
            world_y: Y position in world space.

        Returns:
            A tuple of (screen_x, screen_y) pixel coordinates.

        """
        return (round(world_x - self.world_x), round(world_y - self.world_y))

    def is_visible(self, world_x: float, width: float) -> bool:
        """Check if a world-space object is within the visible viewport.

        Includes a margin to allow sprites to be drawn just before they
        scroll into view.

        Args:
            world_x: The left edge X position in world space.
            width: The width of the object.

        Returns:
            True if the object overlaps the visible area (with margin).

        """
        margin = 64
        return (
            world_x + width > self.world_x - margin
            and world_x < self.world_x + self.screen_width + margin
        )
