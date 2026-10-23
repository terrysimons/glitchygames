#!/usr/bin/env python3
"""Text Input Demo."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Self, override

if TYPE_CHECKING:
    from glitchygames.events.base import KeyEvent, MouseButtonEvent

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

    def __init__(
        self: Self,
        options: dict[str, object],
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize the Game.

        Args:
            options (dict[str, object]): The options passed to the game.
            groups (pygame.sprite.LayeredDirty[Any] | None): The sprite groups to add the sprite to.

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
            groups=groups,
        )

        self.background_color = (255, 255, 0)

        self.all_sprites = pygame.sprite.LayeredDirty(self.input_box)

        assert self.screen is not None
        self.all_sprites.clear(self.screen, self.background)

    @override
    def setup(self: Self) -> None:
        """Set up the game.

        Args:
            None

        """
        pygame.key.set_repeat(350)

    @override
    def update(self: Self) -> None:
        """Update the game.

        Args:
            None

        """
        self.input_box.update()
        assert self.screen is not None
        assert self.input_box.image is not None
        self.screen.blit(self.input_box.image, (320, 240))

    def on_input_box_submit_event(self: Self, control: InputBox) -> None:
        """Handle input box submit events.

        Args:
            control: The control that submitted the event.

        """
        self.log.info('%s Got text input from: %s: %s', self.name, control.name, control.text)

    @override
    def on_mouse_button_up_event(self: Self, event: MouseButtonEvent) -> None:
        """Handle mouse button up events.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        self.input_box.activate()

    @override
    def on_key_up_event(self: Self, event: KeyEvent) -> None:
        """Handle key up events.

        Args:
            event (KeyEvent): The event to handle.

        """
        if self.input_box.is_active:
            self.input_box.on_key_up_event(event)
        elif event.key == pygame.K_TAB:
            self.input_box.activate()
        else:
            super().on_key_up_event(event)

    @override
    def on_key_down_event(self: Self, event: KeyEvent) -> None:
        """Handle key down events.

        Args:
            event (KeyEvent): The event to handle.

        """
        if self.input_box.is_active:
            # Return submits the text (the box itself has no parent to tell)
            if event.key == pygame.K_RETURN:
                self.on_input_box_submit_event(control=self.input_box)
            self.input_box.on_key_down_event(event)
        else:
            # Key down, not key up: a quit key quits on its release, not its press
            super().on_key_down_event(event)


def main() -> None:
    """Run the main entry point for the game."""
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()
