#!/usr/bin/env python3
"""Delta Time Demo."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, override

if TYPE_CHECKING:
    import argparse

    from glitchygames.events.core import HashableEvent

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
        self: Self,
        options: dict[str, object],
        groups: pygame.sprite.LayeredDirty | None = None,  # type: ignore[type-arg]
    ) -> None:
        """Initialize the Game.

        Args:
            options (dict[str, object]): The options passed to the game.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()  # type: ignore[type-arg]

        super().__init__(options=options, groups=groups)  # type: ignore[arg-type]
        self.font = pygame.font.SysFont('Calibri', 40)
        self.rect_pos = 0
        # Pixels per second; use a visible speed
        self.velocity = 300
        self.record = 0
        self.passed = False
        self.start = False

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> None:
        """Add game-specific arguments to the gloal parser.

        This class method will get called automatically by the GameEngine class.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        """
        parser.add_argument(
            '-v', '--version', action='store_true', help='print the game version and exit'
        )

        parser.add_argument(
            '-b', '--balls', type=int, help='the number of balls to start with', default=1
        )

    # def setup(self):
    #     self.target_fps = 30

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Update the scene.

        This method will get called automatically by the GameEngine class.

        Args:
            dt: The delta time (float).

        """
        # self.dt = dt
        # self.dt_timer += self.dt

        # for sprite in self.all_sprites:
        #     sprite.dt_tick(dt)

        if self.start:
            self.dt_timer += dt
            self.rect_pos += self.velocity * dt

    @override
    def update(self: Self) -> None:
        """Update the scene.

        This method will get called automatically by the GameEngine class.

        """
        assert self.screen is not None
        self.screen.fill((0, 0, 0))

        if self.rect_pos > self.screen_width and not self.passed:
            self.record = self.dt_timer
            self.passed = True

        countdown = self.font.render(
            'Time: ' + str(round(self.dt_timer, 2)),
            False,  # noqa: FBT003
            (255, 255, 255),
        )
        fps_text = self.font.render(f'FPS: {round(self.fps, 2)}', False, (255, 255, 255))  # noqa: FBT003

        self.screen.blit(countdown, (0, 0))
        self.screen.blit(fps_text, (0, 50))

        pygame.draw.rect(self.screen, WHITE, (self.rect_pos, (self.screen_height / 2) + 30, 40, 40))
        if self.record:
            record_text = self.font.render(f'Time: {round(self.record, 2)}', False, (255, 255, 255))  # noqa: FBT003

            self.screen.blit(record_text, (self.screen_width / 4, self.screen_height / 2))

    @override
    def on_key_down_event(self: Self, event: HashableEvent) -> None:
        """Handle key down events.

        Args:
            event (HashableEvent): The event to handle.

        """
        pressed_keys = pygame.key.get_pressed()

        if pressed_keys[pygame.K_SPACE]:
            self.start = True


def main() -> None:
    """Run the main entry point for the game."""
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()
