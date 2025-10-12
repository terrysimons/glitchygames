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

    # Scale up the sprite by 20x for better visibility on large monitors
    scale_factor = 20
    scaled_size = None

    try:
        animated_sprite = AnimatedSprite(str(foo_toml_path))
        animated_sprite.play()

        # Calculate scaled size based on original sprite size
        original_size = animated_sprite.image.get_size()
        scaled_size = (original_size[0] * scale_factor, original_size[1] * scale_factor)

        # Set up the sprite rect for the scaled size and center it on screen
        animated_sprite.rect = pygame.Rect(0, 0, scaled_size[0], scaled_size[1])
        animated_sprite.rect.center = (400, 300)  # Center of 800x600 screen

        logger.info(f"Loaded: {animated_sprite.name} ({animated_sprite.frame_count} frames)")
        logger.info(f"Scaled from {original_size} to {scaled_size} (5x upscale)")
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

        # Scale the current frame for display
        current_frame = animated_sprite.image
        scaled_frame = pygame.transform.scale(current_frame, scaled_size)

        # Calculate position to center the scaled frame on screen
        screen_center = (400, 300)  # Center of 800x600 screen
        frame_rect = scaled_frame.get_rect()
        frame_rect.center = screen_center

        screen.fill((20, 20, 40))
        screen.blit(scaled_frame, frame_rect)
        pygame.display.flip()

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
