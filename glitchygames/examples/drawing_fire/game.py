"""Drawing Fire: a pencil-on-paper stick-figure battle.

This first cut is an empty battlefield: paper, and the ground with its hills.
"""

from __future__ import annotations

from typing import Any, ClassVar, Self, override

import pygame

from glitchygames.engine import GameEngine
from glitchygames.examples.drawing_fire.terrain import Terrain, build_terrain
from glitchygames.randomness import random_stream
from glitchygames.scenes import Scene

PAPER_COLOR = (251, 248, 239)
PENCIL_COLOR = (58, 58, 64)
GROUND_LINE_WIDTH = 2


class DrawingFireScene(Scene):
    """The battlefield: a sheet of paper with a hilly ground line."""

    NAME = 'Drawing Fire'
    VERSION = '0.1'
    # After a hitch (a window drag, focus loss) logic advances at most this much in one frame
    MAX_FRAME_SECONDS: ClassVar[float | None] = 0.05

    def __init__(
        self: Self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Build the battlefield: its paper and its seeded terrain.

        Args:
            options: Command-line options.
            groups: The sprite group (a new one when None).

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()
        super().__init__(options=options, groups=groups)
        self.background_color = PAPER_COLOR
        self.terrain: Terrain = build_terrain(
            width=self.screen_width,
            height=self.screen_height,
            random=random_stream('drawing_fire.terrain'),
        )
        # The ground is pencilled onto the paper, under every sprite
        self._draw_ground()

    def _draw_ground(self: Self) -> None:
        """Pencil the ground line onto the background."""
        pygame.draw.lines(
            surface=self.background,
            color=PENCIL_COLOR,
            closed=False,
            points=list(enumerate(self.terrain.ground)),
            width=GROUND_LINE_WIDTH,
        )

    @override
    def render(self: Self, screen: pygame.Surface) -> None:
        """Draw the paper with its ground line, then every sprite.

        Args:
            screen: The display surface.

        """
        screen.blit(self.background, (0, 0))
        self.all_sprites.clear(screen, self.background)
        self.all_sprites.draw(screen)
        self.rects = None  # The whole screen is presented


def main() -> None:
    """Run Drawing Fire."""
    GameEngine(game=DrawingFireScene).start()


if __name__ == '__main__':
    main()
