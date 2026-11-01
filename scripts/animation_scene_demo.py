#!/usr/bin/env python3
"""Animated scene demo script that loads animated.toml and displays animated sprite."""

import logging
import sys
from pathlib import Path
from typing import Any, override

import pygame

from glitchygames.exit_codes import ExitCode
from glitchygames.scenes import Scene
from glitchygames.sprites.animated import AnimatedSprite

logger = logging.getLogger(__name__)

# The sprite the demo shows: scripts/animated.toml, next to this script (it was foo.toml, a
# static sprite with no palette that drew nothing, BUGS.md #244). The demos looked for it in
# the repository root, where there is none, so they always stopped with MISSING_INPUT
# (BUGS.md #245).
SPRITE_PATH = Path(__file__).parent / 'animated.toml'


class AnimationScene(Scene):
    """Scene for displaying animated sprites."""

    def __init__(self) -> None:
        """Initialize the animation scene.

        Raises:
            FileNotFoundError: If the animation TOML file is not found.
            ValueError: If the animation data is invalid.
            RuntimeError: If the animation system fails to initialize.

        """
        super().__init__()

        # Create sprite group for the scene
        self.groups: pygame.sprite.LayeredDirty[Any] = pygame.sprite.LayeredDirty()

        # Load the animated sprite from animated.toml
        sprite_path = SPRITE_PATH

        try:
            self.animated_sprite = AnimatedSprite(str(sprite_path), groups=self.groups)
        except FileNotFoundError, ValueError, RuntimeError:
            logger.exception('Failed to load animation')
            raise
        self.animated_sprite.play()
        assert self.animated_sprite.rect is not None
        self.animated_sprite.rect.center = (400, 300)  # Center of 800x600 screen
        logger.info(
            'Loaded: %s (%s frames)',
            self.animated_sprite.name,
            self.animated_sprite.frame_count,
        )
        logger.info('Controls: ESC/Q=quit, SPACE=pause/resume, R=reset, 1/2=frame 0/1')

    @override
    def update(self, dt: float | None = None) -> None:
        """Update the scene."""
        super().update()

        # Update the animated sprite with delta time
        if self.animated_sprite:
            # Default to ~60fps if no dt provided
            self.animated_sprite.update(dt or 0.016)

    def handle_event(self, event: pygame.event.Event) -> str | None:
        """Handle scene events.

        Returns:
            object: The result.

        """
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE or event.unicode.lower() == 'q':
                return 'quit'
            if event.key == pygame.K_SPACE:
                if self.animated_sprite.is_playing:
                    self.animated_sprite.pause()
                else:
                    self.animated_sprite.play()
            if event.key == pygame.K_r:
                self.animated_sprite.stop()
                self.animated_sprite.play()
            if event.key == pygame.K_1:
                self.animated_sprite.set_frame(0)
            if event.key == pygame.K_2:
                self.animated_sprite.set_frame(1)
        return None


def main() -> int:
    """Run the animation scene demo.

    Returns:
        int: Exit code (0 for success).

    """
    # Configured as the demo starts, never at import (BUGS.md #236)
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    # Initialize pygame
    pygame.init()

    # Set up the display
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption('Animated Scene Demo - animated.toml')
    clock = pygame.time.Clock()

    # Create and run the scene
    scene = AnimationScene()

    # Main game loop
    running = True
    while running:
        # Calculate delta time
        dt = clock.tick(60) / 1000.0

        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            else:
                result = scene.handle_event(event)
                if result == 'quit':
                    running = False

        # Update and render
        scene.update(dt)
        screen.fill((20, 20, 40))
        assert scene.animated_sprite.image is not None
        assert scene.animated_sprite.rect is not None
        screen.blit(scene.animated_sprite.image, scene.animated_sprite.rect)
        pygame.display.flip()

    pygame.quit()
    return ExitCode.SUCCESS


if __name__ == '__main__':
    sys.exit(main())
