#!/usr/bin/env python3
"""Animated scene demo script that loads foo.toml and displays animated sprite."""

import logging
import sys
from pathlib import Path

import pygame

# Add the parent directory to the path so we can import glitchygames
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.scenes import Scene
from glitchygames.sprites.animated import AnimatedSprite

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class AnimationScene(Scene):
    """Scene for displaying animated sprites."""

    def __init__(self):
        """Initialize the animation scene."""
        super().__init__()

        # Create sprite group for the scene
        self.groups = pygame.sprite.LayeredDirty()

        # Load the animated sprite from foo.toml
        foo_toml_path = Path(__file__).parent.parent / "foo.toml"

        try:
            self.animated_sprite = AnimatedSprite(str(foo_toml_path), groups=self.groups)
            self.animated_sprite.play()
            self.animated_sprite.rect.center = (400, 300)  # Center of 800x600 screen
            logger.info(f"Loaded: {self.animated_sprite.name} "
                       f"({self.animated_sprite.frame_count} frames)")
            logger.info("Controls: ESC/Q=quit, SPACE=pause/resume, R=reset, 1/2=frame 0/1")
        except (FileNotFoundError, ValueError, RuntimeError):
            logger.exception("Failed to load animation")
            raise

    def update(self, dt=None):
        """Update the scene."""
        super().update()

        # Update the animated sprite with delta time
        if self.animated_sprite:
            # Default to ~60fps if no dt provided
            self.animated_sprite.update(dt or 0.016)

    def handle_event(self, event):
        """Handle scene events."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE or event.unicode.lower() == "q":
                return "quit"
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


def main():
    """Run the animation scene demo."""
    # Initialize pygame
    pygame.init()

    # Set up the display
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Animated Scene Demo - foo.toml")
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
                if result == "quit":
                    running = False

        # Update and render
        scene.update(dt)
        screen.fill((20, 20, 40))
        screen.blit(scene.animated_sprite.image, scene.animated_sprite.rect)
        pygame.display.flip()

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
