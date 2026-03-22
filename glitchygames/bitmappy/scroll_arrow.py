"""ScrollArrowSprite — directional arrow sprites for film strip scrolling."""

from __future__ import annotations

import pygame

from glitchygames.sprites import BitmappySprite


class ScrollArrowSprite(BitmappySprite):
    """Sprite for scroll arrows."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 20,
        height: int = 20,
        groups: pygame.sprite.LayeredDirty | None = None,  # type: ignore[type-arg]
        direction: str = 'up',
    ) -> None:
        """Initialize the scroll arrow sprite."""
        super().__init__(x=x, y=y, width=width, height=height, groups=groups)  # type: ignore[arg-type]
        self.direction = direction
        self.name = f'Scroll {direction} Arrow'

        # Create arrow surface
        self.image = pygame.Surface((width, height))
        self.rect = self.image.get_rect(x=x, y=y)

        # Draw the arrow
        self._draw_arrow()

        # Initially hidden
        self.visible = False
        self.dirty = 1

    def _draw_arrow(self) -> None:
        """Draw the arrow on the surface."""
        self.image.fill((255, 255, 255))  # White background

        if self.direction == 'up':
            # Up arrow: triangle pointing up
            pygame.draw.polygon(self.image, (0, 0, 0), [(10, 5), (5, 15), (15, 15)])
        elif self.direction == 'down':
            # Down arrow: triangle pointing down
            pygame.draw.polygon(self.image, (0, 0, 0), [(10, 15), (5, 5), (15, 5)])
        elif self.direction == 'plus':
            # Plus sign for adding new frames
            pygame.draw.line(self.image, (0, 0, 0), (10, 5), (10, 15), 2)  # Vertical line
            pygame.draw.line(self.image, (0, 0, 0), (5, 10), (15, 10), 2)  # Horizontal line

    def set_direction(self, direction: str) -> None:
        """Change the arrow direction and redraw."""
        if self.direction != direction:
            self.direction = direction
            self._draw_arrow()
            self.dirty = 1
