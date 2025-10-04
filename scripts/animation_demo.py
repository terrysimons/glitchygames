#!/usr/bin/env python3
"""Animation demo script that loads foo.toml and displays the animated sprite."""

import logging
import sys
from pathlib import Path

import pygame

# Add the parent directory to the path so we can import glitchygames
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.sprites.animated import AnimatedSprite

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main():
    """Run the animation demo."""
    # Initialize pygame
    pygame.init()

    # Set up the display
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Animation Demo - foo.toml")
    clock = pygame.time.Clock()

    # Load the animated sprite from foo.toml
    foo_toml_path = Path(__file__).parent.parent / "foo.toml"

    try:
        animated_sprite = AnimatedSprite(str(foo_toml_path))
        animated_sprite.play()
        animated_sprite.rect.center = (400, 300)  # Center of 800x600 screen
        logger.info(f"Loaded: {animated_sprite.name} ({animated_sprite.frame_count} frames)")
        logger.info("Controls: ESC/Q=quit, SPACE=pause/resume, R=reset, 1/2=frame 0/1")
    except (FileNotFoundError, ValueError, RuntimeError):
        logger.exception("Failed to load animation")
        return 1

    # Main game loop
    running = True
    while running:
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or event.unicode.lower() == "q":
                    running = False
                elif event.key == pygame.K_SPACE:
                    if animated_sprite.is_playing:
                        animated_sprite.pause()
                    else:
                        animated_sprite.play()
                elif event.key == pygame.K_r:
                    animated_sprite.stop()
                    animated_sprite.play()
                elif event.key == pygame.K_1:
                    animated_sprite.set_frame(0)
                elif event.key == pygame.K_2:
                    animated_sprite.set_frame(1)

        # Update and render
        animated_sprite.update(clock.tick(60) / 1000.0)
        screen.fill((20, 20, 40))
        screen.blit(animated_sprite.image, animated_sprite.rect)
        pygame.display.flip()

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
