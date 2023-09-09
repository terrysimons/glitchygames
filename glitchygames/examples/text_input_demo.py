#!/usr/bin/env python3
"""Text Input Demo."""
from __future__ import annotations

import logging
from typing import Self

import pygame

from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene
from glitchygames.ui import InputBox

LOG = logging.getLogger('game')
LOG.setLevel(logging.DEBUG)


class Game(Scene):
    """The main game class."""

    log = LOG

    # Set your game name/version here.
    NAME = 'Input Demo'
    VERSION = '1.0'

    def __init__(self: Self, options: dict, groups: pygame.sprite.LayeredDirty | None = None) -> None:  # noqa: E501
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

        self.input_box = InputBox(
            x=320,
            y=240,
            width=200,
            height=20,
            text='Test',
            parent=self,
            groups=groups
        )

        self.background_color = (255, 255, 0)

        self.all_sprites = pygame.sprite.LayeredDirty(
            self.input_box
        )

        self.all_sprites.clear(self.screen, self.background)

    def setup(self: Self) -> None:
        """Set up the game.

        Args:
            None

        Returns:
            None
        """
        pygame.key.set_repeat(350)

    def update(self: Self) -> None:
        """Update the game.

        Args:
            None

        Returns:
            None
        """
        self.input_box.update()
        self.screen.blit(self.input_box.image, (320, 240))

    def on_input_box_submit_event(self: Self, control: object) -> None:
        """Handle input box submit events.

        Args:
            control (object): The control that submitted the event.

        Returns:
            None
        """
        self.log.info(f'{self.name} Got text input from: {control.name}: {control.text}')

    def on_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.input_box.activate()

    def on_key_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle key up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        if self.input_box.active:
            self.input_box.on_key_up_event(event)
        elif event.key == pygame.K_TAB:
            self.input_box.activate()
        else:
            super().on_key_up_event(event)

    def on_key_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle key down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        if self.input_box.active:
            self.input_box.on_key_down_event(event)
        else:
            super().on_key_up_event(event)


def main() -> None:
    """The main entry point for the game."""
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()
