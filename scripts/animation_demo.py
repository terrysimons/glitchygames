#!/usr/bin/env python3
"""Animation demo script that loads animated.toml and displays the animated sprite."""

import logging
import sys
from pathlib import Path

import pygame

from glitchygames.exit_codes import ExitCode
from glitchygames.sprites.animated import AnimatedSprite

logger = logging.getLogger(__name__)

# The sprite the demo shows: scripts/animated.toml, next to this script (it was foo.toml, a
# static sprite with no palette that drew nothing, BUGS.md #244). The demos looked for it in
# the repository root, where there is none, so they always stopped with MISSING_INPUT
# (BUGS.md #245).
SPRITE_PATH = Path(__file__).parent / 'animated.toml'


def _handle_event(event: pygame.event.Event, animated_sprite: AnimatedSprite) -> bool:
    """Handle a single pygame event.

    Args:
        event: The pygame event to handle.
        animated_sprite: The animated sprite to control.

    Returns:
        bool: True if the application should continue running, False to quit.

    """
    if event.type == pygame.QUIT:
        return False

    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE or event.unicode.lower() == 'q':
            return False
        if event.key == pygame.K_SPACE:
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

    return True


def main() -> int:
    """Run the animation demo.

    Returns:
        int: Exit code (0 for success, 1 for failure).

    """
    # Configured as the demo starts, never at import (BUGS.md #236)
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    # Initialize pygame
    pygame.init()

    # Set up the display
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption('Animation Demo - animated.toml')
    clock = pygame.time.Clock()

    # Load the animated sprite from animated.toml
    sprite_path = SPRITE_PATH

    # Scale up the sprite by 20x for better visibility on large monitors
    scale_factor = 20
    scaled_size = None

    try:
        animated_sprite = AnimatedSprite(str(sprite_path))
    except FileNotFoundError:
        logger.exception('Failed to load animation')
        return ExitCode.MISSING_INPUT
    except ValueError, RuntimeError:
        logger.exception('Failed to load animation')
        return ExitCode.UNUSABLE_INPUT
    animated_sprite.play()

    # Calculate scaled size based on original sprite size
    assert animated_sprite.image is not None
    original_size = animated_sprite.image.get_size()
    scaled_size = (original_size[0] * scale_factor, original_size[1] * scale_factor)

    # Set up the sprite rect for the scaled size and center it on screen
    animated_sprite.rect = pygame.Rect(0, 0, scaled_size[0], scaled_size[1])
    assert animated_sprite.rect is not None
    animated_sprite.rect.center = (400, 300)  # Center of 800x600 screen

    logger.info('Loaded: %s (%s frames)', animated_sprite.name, animated_sprite.frame_count)
    logger.info('Scaled from %s to %s (5x upscale)', original_size, scaled_size)
    logger.info('Controls: ESC/Q=quit, SPACE=pause/resume, R=reset, 1/2=frame 0/1')

    # Main game loop
    running = True
    while running:
        # Handle events
        for event in pygame.event.get():
            if not _handle_event(event, animated_sprite):
                running = False

        # Update and render
        animated_sprite.update(clock.tick(60) / 1000.0)

        # Scale the current frame for display
        current_frame = animated_sprite.image
        assert current_frame is not None
        assert scaled_size is not None
        scaled_frame = pygame.transform.scale(current_frame, scaled_size)

        # Calculate position to center the scaled frame on screen
        screen_center = (400, 300)  # Center of 800x600 screen
        frame_rect = scaled_frame.get_rect()
        frame_rect.center = screen_center

        screen.fill((20, 20, 40))
        screen.blit(scaled_frame, frame_rect)
        pygame.display.flip()

    pygame.quit()
    return ExitCode.SUCCESS


if __name__ == '__main__':
    sys.exit(main())
