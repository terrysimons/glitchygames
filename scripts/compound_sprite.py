#!/usr/bin/env python3
"""Compound Sprite Demo."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    import argparse

import pygame

from glitchygames.bitmappy import resource_path
from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene
from glitchygames.sprites import BitmappySprite
from glitchygames.ui import ButtonSprite, MenuBar, MenuItem

log = logging.getLogger('game')
log.setLevel(logging.DEBUG)

# Turn on sprite debugging
BitmappySprite.DEBUG = True


class GameScene(Scene):
    """The intro scene.

    Args:
        None

    Returns:
        None

    """

    def __init__(self: Self, groups: pygame.sprite.LayeredDirty[Any] | None = None) -> None:
        """Initialize the intro scene.

        Args:
            groups (pygame.sprite.LayeredDirty[Any] | None): The sprite groups.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(groups=groups)
        self.all_sprites: pygame.sprite.LayeredDirty[Any] = groups
        screen = pygame.display.get_surface()
        assert screen is not None
        self.screen: pygame.Surface = screen
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()

        self.screen.fill((255, 255, 0))

        self.menu_bar = MenuBar(
            name='Menu Bar', x=0, y=0, width=self.screen_width, height=20, groups=self.all_sprites,
        )

        # Note: Why is the file menu 2 pixels down from the menu icon?

        self.menu_icon = MenuItem(
            name=None,
            filename=str(resource_path('glitchygames', 'assets', 'raspberry.toml')),
            x=0,
            y=0,
            width=16,
            height=self.menu_bar.height,
        )

        # When we load the sprite, we set a name.
        # but the menu code needs to know that we're
        # trying to draw an icon.
        self.menu_icon.name = None
        assert self.menu_icon.rect is not None

        self.menu_bar.add_menu_item(menu_item=self.menu_icon, menu=None)

        # self.file_menu = MenuItem(name='File',
        #                          x=self.menu_icon.width,
        #                          y=self.menu_icon.y,
        #                          width=50,
        #                          height=16)
        # self.file_save = MenuItem(name='Save', x=16, y=18, width=32, height=16)
        # self.file_load = MenuItem(name='Load', x=16, y=18, width=32, height=16)
        # self.menu_bar.add_menu_item(menu_item=self.file_menu, menu=None)
        # self.file_menu.add_menu_item(menu_item=self.file_save, menu=self.file_menu)
        # self.file_menu.add_menu_item(menu_item=self.file_load, menu=self.file_menu)

        # self.file_menu = MenuItem(name='File',
        #                          x=self.menu_icon.width,
        #                          y=self.menu_icon.y,
        #                          width=32,
        #                          height=16,
        #                          groups=self.all_sprites)
        self.save_menu_item = MenuItem(
            name='Save',
            x=self.menu_icon.width + 5,
            y=int(self.menu_icon.rect.y),
            width=40,
            height=self.menu_bar.height,
            groups=self.all_sprites,
        )
        self.load_menu_item = MenuItem(
            name='Load',
            x=self.menu_icon.width + self.save_menu_item.width + 5,
            y=int(self.menu_icon.rect.y),
            width=40,
            height=self.menu_bar.height,
            groups=self.all_sprites,
        )
        self.quit_menu_item = MenuItem(
            name='Quit',
            x=self.menu_icon.width + self.save_menu_item.width + self.load_menu_item.width + 5,
            y=int(self.menu_icon.rect.y),
            width=40,
            height=self.menu_bar.height,
            groups=self.all_sprites,
        )

        # Add the menu icon as a root level menu item.
        # self.menu_bar.add_menu_item(menu_item=self.menu_icon, menu=None)
        # self.menu_bar.add_menu_item(menu_item=self.file_menu, menu=None)

        # self.file_menu.add_menu_item(menu_item=self.save_menu_item, menu=None)
        # self.file_menu.add_menu_item(menu_item=self.load_menu_item, menu=None)
        # self.file_menu.add_menu_item(menu_item=self.spacer_menu_item, menu=None)
        # self.file_menu.add_menu_item(menu_item=self.quit_menu_item, menu=None)

        button_width = self.screen_width // 2 // 2
        button_height = self.screen_height // 2 // 2
        screen_rect = self.screen.get_rect()
        self.button = ButtonSprite(
            x=(screen_rect.centerx - button_width) // 4,
            y=(screen_rect.centery - button_height) // 4,
            width=button_width,
            height=button_height,
            name='Buttony McButtonface',
            groups=self.all_sprites,
        )

        self.button.x = screen_rect.centerx // 2
        self.button.y = screen_rect.centery // 2

        # self.button.border_color = (0, 255, 0)
        # self.button.background_color = (255, 0, 255)

        self.all_sprites.clear(self.screen, self.background)

    # def update(self):
    #     super().update()

    # def render(self, screen):
    #     super().render(screen)

    # def switch_to_scene(self, next_scene):
    #     super().switch_to_scene(next_scene)
    def on_mouse_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse up events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.info('Mouse Up Event: %s', event)


class Game(Scene):
    """The main game class.  This is where the magic happens."""

    # Set your game name/version here.
    NAME = 'Compound Sprite Demo'
    VERSION = '1.0'

    def __init__(self: Self, options: dict[str, Any]) -> None:
        """Initialize the game.

        Args:
            options (dict[str, Any]): The options passed to the game.

        """
        super().__init__(options=options)

        # GameEngine.OPTIONS is set on initialization.
        log.info('Game Options: %s', options)

        self.next_scene = GameScene()

    @classmethod
    def args(cls: type[Game], parser: argparse.ArgumentParser) -> None:
        """Add arguments to the argument parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        """
        parser.add_argument(
            '-v', '--version', action='store_true', help='print the game version and exit',
        )


def main() -> None:
    """Run the main entry point for the game."""
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()
