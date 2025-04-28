#!/usr/bin/env python3
"""Bitrot Adventures."""
import argparse
import logging
import pathlib

import pygame
from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene

# Instantiate a logger called "game" to enable glitchygames
# logging module. This is optional, but recommended.
LOG = logging.getLogger('game')

# Think of a scene as an encapsulated pygame screen.
#
# Each scene can handle its own events, update its own
# state, and draw its own graphics.
#
# The engine will handle switching between scenes
# and passing events to the current scene.
#
# The engine will also handle drawing the current
# scene to the screen.
class BitrotAdventures(Scene):
    """Draws a pixel to the screen"""

    NAME = 'Bitrot Adventures'
    VERSION = '0.0.0'

    def __init__(self, options):
        super().__init__(options=options)
        self.pixel_pos = [400, 300]  # Start in the middle of the screen
        self.pixel_color = (255, 255, 255)  # White
        self.pixel_size = 4  # 4x4 pixel
        self.move_speed = 5

    # This is called by glitchygames.GameEngine before
    # the class is instantiated.
    #
    # Note that GameEngine defines a few command line
    # options that are intended to be common across all
    # games, so it's worth checking your game with --help
    # before adding new options to ensure that you haven't
    # clobbered an existing option.
    @classmethod
    def args(cls, parser: argparse.ArgumentParser):
        """Game specific command line arguments."""
        parser.add_argument('-s', '--some-game-specific-option',
                            help='foo help')
        return parser

    def on_key_down_event(self, event):
        """Handle key down events."""
        if event.key == pygame.K_LEFT:
            self.pixel_pos[0] -= self.move_speed
        elif event.key == pygame.K_RIGHT:
            self.pixel_pos[0] += self.move_speed
        elif event.key == pygame.K_UP:
            self.pixel_pos[1] -= self.move_speed
        elif event.key == pygame.K_DOWN:
            self.pixel_pos[1] += self.move_speed
        elif event.key == pygame.K_SPACE:
            # Change color on space
            r = (self.pixel_color[0] + 50) % 256
            g = (self.pixel_color[1] + 100) % 256
            b = (self.pixel_color[2] + 150) % 256
            self.pixel_color = (r, g, b)

    def draw(self, surface):
        """Draw the scene."""
        # Clear the screen
        surface.fill((0, 0, 0))
        
        # Draw the pixel
        pygame.draw.rect(surface, self.pixel_color, 
                         pygame.Rect(self.pixel_pos[0], self.pixel_pos[1], 
                                    self.pixel_size, self.pixel_size))

def main():
    # Note that the Scene (BitrotAdventures) is
    # passed in uninitialized - the engine
    # will initialize it for you.
    GameEngine(
        game=BitrotAdventures,
        icon=None  # Replace with path to icon if you have one
    ).start()

if __name__ == '__main__':
    main()