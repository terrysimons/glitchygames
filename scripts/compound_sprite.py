#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
# import collections
# import configparser
import logging

# from pygame import Rect
import pygame
import pygame.freetype
import pygame.gfxdraw
import pygame.locals

# from ghettogames.color import WHITE, BLACKLUCENT
# from ghettogames.engine import RootSprite, MousePointer, BitmappySprite
# from ghettogames.engine import SingletonBitmappySprite
from ghettogames.engine import BitmappySprite, RootScene, GameEngine
from ghettogames.ui import ButtonSprite, MenuBar, MenuItem
# from ghettogames.engine import JoystickManager
# from ghettogames.engine import pixels_from_data, pixels_from_path
# from ghettogames.engine import image_from_pixels
# from ghettogames.engine import rgb_triplet_generator

log = logging.getLogger('game')
log.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

log.addHandler(ch)

# Turn on sprite debugging
BitmappySprite.DEBUG = True


class GameScene(RootScene):
    def __init__(self, groups=pygame.sprite.LayeredDirty()):
        super().__init__(groups=groups)
        self.all_sprites = groups
        self.screen = pygame.display.get_surface()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()

        self.screen.fill((255, 255, 0))

        self.menu_bar = MenuBar(name='Menu Bar',
                                x=0,
                                y=0,
                                width=self.screen_width,
                                height=20,
                                groups=self.all_sprites)

        # Note: Why is the file menu 2 pixels down from the menu icon?
        self.menu_icon = MenuItem(name=None,
                                  filename='raspberry.cfg',
                                  x=0,
                                  y=0,
                                  width=16,
                                  height=self.menu_bar.height)

        # When we load the sprite, we set a name.
        # but the menu code needs to know that we're
        # trying to draw an icon.
        self.menu_icon.name = None

        self.menu_bar.add_menu_item(menu_item=self.menu_icon,
                                    menu=None)

        #self.file_menu = MenuItem(name='File',
        #                          x=self.menu_icon.width,
        #                          y=self.menu_icon.y,
        #                          width=50,
        #                          height=16)
        #self.file_save = MenuItem(name='Save', x=16, y=18, width=32, height=16)
        #self.file_load = MenuItem(name='Load', x=16, y=18, width=32, height=16)
        #self.menu_bar.add_menu_item(menu_item=self.file_menu, menu=None)
        #self.file_menu.add_menu_item(menu_item=self.file_save, menu=self.file_menu)
        #self.file_menu.add_menu_item(menu_item=self.file_load, menu=self.file_menu)

        #self.file_menu = MenuItem(name='File',
        #                          x=self.menu_icon.width,
        #                          y=self.menu_icon.y,
        #                          width=32,
        #                          height=16,
        #                          groups=self.all_sprites)
        self.save_menu_item = MenuItem(name='Save',
                                       x=self.menu_icon.width + 5,
                                       y=self.menu_icon.y,
                                       width=40,
                                       height=self.menu_bar.height,
                                       groups=self.all_sprites)
        self.load_menu_item = MenuItem(name='Load',
                                       x=self.menu_icon.width + self.save_menu_item.width + 5,
                                       y=self.menu_icon.y,
                                       width=40,
                                       height=self.menu_bar.height,
                                       groups=self.all_sprites)
        self.quit_menu_item = MenuItem(name='Quit',
                                       x=self.menu_icon.width + self.save_menu_item.width + self.load_menu_item.width + 5,
                                       y=self.menu_icon.y,
                                       width=40,
                                       height=self.menu_bar.height,
                                       groups=self.all_sprites)

        # Add the menu icon as a root level menu item.
        #self.menu_bar.add_menu_item(menu_item=self.menu_icon, menu=None)
        #self.menu_bar.add_menu_item(menu_item=self.file_menu, menu=None)

        #self.file_menu.add_menu_item(menu_item=self.save_menu_item, menu=None)
        #self.file_menu.add_menu_item(menu_item=self.load_menu_item, menu=None)
        #self.file_menu.add_menu_item(menu_item=self.spacer_menu_item, menu=None)
        #self.file_menu.add_menu_item(menu_item=self.quit_menu_item, menu=None)

        button_width = self.screen_width // 2 // 2
        button_height = self.screen_height // 2 // 2
        self.button = ButtonSprite(x=self.screen.get_rect().centerx - button_width // 2,
                                   y=self.screen.get_rect().centery - button_height // 2,
                                   width=button_width,
                                   height=button_height,
                                   name='Buttony McButtonface',
                                   groups=self.all_sprites)

        # self.button.border_color = (0, 255, 0)
        # self.button.background_color = (255, 0, 255)

        self.all_sprites.clear(self.screen, self.background)

    # def update(self):
    #     super().update()

    # def render(self, screen):
    #     super().render(screen)

    # def switch_to_scene(self, next_scene):
    #     super().switch_to_scene(next_scene)
    def on_mouse_up_event(self, event):
        log.info('fdasfdsafdsafdsa')


class Game(GameEngine):
    # Set your game name/version here.
    NAME = "Compound Sprite Demo"
    VERSION = "1.0"

    def __init__(self, options):
        super().__init__(options=options)

        # GameEngine.OPTIONS is set on initialization.
        log.info(f'Game Options: {Game.OPTIONS}')

    @classmethod
    def args(cls, parser):
        # Initialize the game engine's options first.
        # This ensures that our game's specific options
        # are listed last.
        parser = GameEngine.args(parser)

        group = parser.add_argument_group('Game Options')

        group.add_argument('-v', '--version',
                           action='store_true',
                           help='print the game version and exit')
        return parser

    def start(self):
        # Call the main game engine's start routine to initialize
        # the screen and set the self.screen_width, self.screen_height variables
        # and do a few other init related things.
        super().start()

        # Note: Due to the way things are wired, you must set self.active_scene after
        # calling super().start() in this method.
        self.clock = pygame.time.Clock()
        self.active_scene = GameScene()

        while self.active_scene is not None:
            self.process_events()

            self.active_scene.update()

            self.active_scene.render(self.screen)

            self.clock.tick(self.fps)

            if self.update_type == 'update':
                pygame.display.update(self.active_scene.rects)
            elif self.update_type == 'flip':
                pygame.display.flip()

            self.active_scene = self.active_scene.next

    # This will catch calls which our scene engine doesn't yet implement.
    def __getattr__(self, attr):
        try:
            if self.active_scene:  # noqa: R1705
                return getattr(self.active_scene, attr)
            else:
                raise Exception(f'Scene not activated in call to {attr}()')
        except AttributeError:
            raise AttributeError(f'{attr} is not implemented in Game {type(self)} '
                                 f'or active scene {type(self.active_scene)}.')


def main():
    parser = argparse.ArgumentParser(f"{Game.NAME} version {Game.VERSION}")

    # args is a class method, which allows us to call it before initializing a game
    # object, which allows us to query all of the game engine objects for their
    # command line parameters.
    parser = Game.args(parser)
    args = parser.parse_args()
    game = Game(options=vars(args))
    game.start()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        raise e
    finally:
        pygame.quit()
