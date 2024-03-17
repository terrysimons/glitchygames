#!/usr/bin/env python3
"""Delta Time Demo."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import argparse

import pygame
from glitchygames.color import WHITE
from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene

# Adapted from:
# https://github.com/ChristianD37/YoutubeTutorials/tree/master/Framerate%20Independence


class Game(Scene):
    """The main game class."""

    # Set your game name/version here.
    NAME = 'Delta Time Demo'
    VERSION = '1.0'

    def __init__(
        self: Self, options: dict, groups: pygame.sprite.LayeredDirty | None = None
    ) -> None:
        """Initialize the Game.

        Args:
            options (dict): The options passed to the game.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        Returns:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(options=options, groups=groups)
        self.font = pygame.font.SysFont('Calibri', 40)
        self.rect_pos = 0
        self.velocity = 5
        self.record = 0
        self.passed = False
        self.start = False

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> None:
        """Add game-specific arguments to the gloal parser.

        This class method will get called automatically by the GameEngine class.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            None
        """
        parser.add_argument(
            '-v', '--version', action='store_true', help='print the game version and exit'
        )

        parser.add_argument(
            '-b', '--balls', type=int, help='the number of balls to start with', default=1
        )

    # def setup(self):
    #     self.target_fps = 30

    def dt_tick(self: Self, dt: float) -> None:
        """Update the scene.

        This method will get called automatically by the GameEngine class.

        Args:
            dt: The delta time (float).

        Returns:
            None
        """
        # self.dt = dt
        # self.dt_timer += self.dt

        # for sprite in self.all_sprites:
        #     sprite.dt_tick(dt)

        if self.start:
            self.dt_timer += dt
            self.rect_pos += self.velocity * dt

    def update(self: Self) -> None:
        """Update the scene.

        This method will get called automatically by the GameEngine class.

        Args:
            None

        Returns:
            None
        """
        self.screen.fill((0, 0, 0))

        if self.rect_pos > self.screen_width and not self.passed:
            self.record = self.dt_timer / 100
            self.passed = True

        countdown = self.font.render(
            text='Time: ' + str(round(self.dt_timer / 100, 5)),
            antialias=False,
            color=(255, 255, 255),
        )
        fps_text = self.font.render(
            text=f'FPS: {round(self.fps, 2)}', antialias=False, color=(255, 255, 255)
        )

        self.screen.blit(countdown, (0, 0))
        self.screen.blit(fps_text, (0, 50))

        pygame.draw.rect(self.screen, WHITE, (self.rect_pos, (self.screen_height / 2) + 30, 40, 40))
        if self.record:
            record_text = self.font.render(
                text=f'Time: {round(self.record, 5)}', antialias=False, color=(255, 255, 255)
            )

            self.screen.blit(record_text, (self.screen_width / 4, self.screen_height / 2))

    def on_key_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle key down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        pressed_keys = pygame.key.get_pressed()

        if pressed_keys[pygame.K_SPACE]:
            self.start = True


def main() -> None:
    """The main entry point for the game."""
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()
