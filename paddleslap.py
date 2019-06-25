#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import copy
import glob
import logging
import time
import multiprocessing
import os
import platform
import struct
import subprocess
import re

from pygame import Color, Rect
import pygame
import pygame.freetype
import pygame.gfxdraw
import pygame.locals

from engine import RootScene, GameEngine, FontManager
from engine import black, white, blacklucent, red
from engine import JoystickManager

log = logging.getLogger('game')
log.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

log.addHandler(ch)

# TODO:
# Add --log-level flag.
# Package.
# 


class PaddleSprite(pygame.sprite.DirtySprite):
    def __init__(self, name):
        super().__init__()
        self.use_gfxdraw = True

        self.name = name
        self.screen = pygame.display.get_surface()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()        
        self.width = 20
        self.height = 80       
        self.image = pygame.Surface((self.width, self.height))
        self.image.convert()
        self.rect = self.image.get_rect()

        pygame.draw.rect(self.image, white, (0, 0, self.width, self.height), 0)        

        self.rect.x = 0
        self.rect.y = 320
        self.moving = False
        self.speed = 0

        self.update()

    def update(self):
        self.dirty = 1

        self.rect.y += self.speed

        if self.rect.bottom > self.screen_height:
            self.rect.bottom = self.screen_height

        if self.rect.y < 0:
            self.rect.y = 0

    def move_down(self):        
        self.speed = 2
        
    def move_up(self):
        self.speed = -2

    def stop(self):
        self.speed = 0

class BallSprite(pygame.sprite.DirtySprite):
    def __init__(self):
        super().__init__()
        self.use_gfxdraw = True

        self.screen = pygame.display.get_surface()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()
        self.width = 10
        self.height = 10        
        self.image = pygame.Surface((self.width, self.height))
        self.image.convert()
        self.rect = self.image.get_rect()

        pygame.draw.circle(self.image, white, (self.width//2, self.height//2), 5, 0)

        self.rect.x = self.screen_width // 2
        self.rect.y = self.screen_height // 2

        self.update()

    def update(self):
        pass

class TextSprite(pygame.sprite.DirtySprite):
    def __init__(self, background_color=blacklucent, alpha=0, x=0, y=0):
        super().__init__()
        self.background_color = background_color
        self.alpha = alpha
        self.x = x
        self.y = y
        
        # Quick and dirty, for now.
        self.image = pygame.Surface((400, 400))
        self.screen = pygame.display.get_surface()

        if not alpha:
            self.image.set_colorkey(self.background_color)
            self.image.convert()
        else:
            # Enabling set_alpha() and also setting a color
            # key will let you hide the background
            # but things that are blited otherwise will
            # be translucent.  This can be an easy
            # hack to get a translucent image which
            # does not have a border, but it causes issues
            # with edge-bleed.
            #
            # What if we blitted the translucent background
            # to the screen, then copied it and used the copy
            # to write the text on top of when translucency
            # is set?  That would allow us to also control
            # whether the text is opaque or translucent, and
            # it would also allow a different translucency level
            # on the text than the window.
            self.image.convert_alpha()
            self.image.set_alpha(self.alpha)
            
        self.rect = self.image.get_rect()
        self.rect.x += x
        self.rect.y += y
        self.font_manager = FontManager(self)
        self.joystick_manager = JoystickManager(self)
        self.joystick_count = len(self.joystick_manager.joysticks)

        class TextBox(object):
            def __init__(self, font_controller, x, y, line_height=15):
                super().__init__()
                self.image = None
                self.rect = None
                self.start_x = x
                self.start_y = y
                self.line_height = line_height
                
                pygame.freetype.set_default_resolution(font_controller.font_dpi)
                self.font = pygame.freetype.SysFont(name=font_controller.font,
                                                    size=font_controller.font_size)

            def print(self, surface, string):
                (self.image, self.rect) = self.font.render(string, white)
                self.image
                surface.blit(self.image, (self.x, self.y))
                self.rect.x = self.x
                self.rect.y = self.y
                self.y += self.line_height
        
            def reset(self):
                self.x = self.start_x
                self.y = self.start_y
                
            def indent(self):
                self.x += 10
        
            def unindent(self):
                self.x -= 10

            def rect(self):
                return self.rect

        self.text_box = TextBox(font_controller=self.font_manager, x=10, y=10)

        self.update()
        
    def update(self):
        self.dirty = 2
        self.image.fill(self.background_color)

        pygame.draw.rect(self.image, white, self.image.get_rect(), 7)        

        self.text_box.reset()
        self.text_box.print(self.image, f'{Game.NAME} version {Game.VERSION}')

        self.text_box.print(self.image, f'CPUs: {multiprocessing.cpu_count()}')
        
        self.text_box.print(self.image, f'FPS: {Game.FPS:.0f}')

        self.text_box.print(self.image, "Number of joysticks: {}".format(self.joystick_count) )        
        if self.joystick_count:
            for i, joystick in enumerate(self.joystick_manager.joysticks):
                self.text_box.print(self.image, f'Joystick {i}')
                
                # Get the name from the OS for the controller/joystick
                self.text_box.indent()
                self.text_box.print(self.image, f'Joystick name: {joystick.get_name()}')
        
                # Usually axis run in pairs, up/down for one, and left/right for
                # the other.
                axes = joystick.get_numaxes()
                self.text_box.print(self.image, f'Number of axes: {axes}')
                
                self.text_box.indent()                
                for i in range(axes):
                    self.text_box.print(self.image, 'Axis {} value: {:>6.3f}'.format(i, joystick.get_axis(i)))
                self.text_box.unindent()

                buttons = joystick.get_numbuttons()
                self.text_box.print(self.image, f'Number of buttons: {joystick.get_numbuttons()}')
                
                self.text_box.indent()
                for i in range(buttons):
                    self.text_box.print(self.image, 'Button {:>2} value: {}'.format(i, joystick.get_button(i)))
                self.text_box.unindent()
            
                # Hat switch. All or nothing for direction, not like joysticks.
                # Value comes back in an array.
                hats = 0
                self.text_box.print(self.image, f'Number of hats: {hats}')
                
                self.text_box.indent()
                for i in range(hats):
                    self.text_box.print(self.image, f'Hat {hat} value: {str(joystick.get_hat(i))}')
                    self.text_box.unindent()
                self.text_box.unindent()

class TableScene(RootScene):
    def __init__(self):
        super().__init__()
        self.player1_sprite = PaddleSprite(name="Player 1")
        self.player2_sprite = PaddleSprite(name="Player 2")
        self.ball_sprite = BallSprite()
        #self.scoreboard_sprite = TextSprite(background_color=blacklucent, alpha=0, x=0, y=0)
        
        # Set player 2's position on the right side of the screen.
        self.player2_sprite.rect.x = self.player2_sprite.screen.get_width() - self.player2_sprite.width

        self.all_sprites = pygame.sprite.LayeredDirty(
            (
                self.player1_sprite,
                self.player2_sprite,
                self.ball_sprite,
                #self.scoreboard_sprite
            )
        )

        self.all_sprites.clear(self.screen, self.background)        

    def update(self):
        super().update()

    def render(self, screen):
        super().render(screen)

    def switch_to_scene(self, next_scene):
        super().switch_to_scene(next_scene)

    def on_key_up_event(self, event):
        # KEYDOWN            key, mod
        if event.key == pygame.K_UP:
            self.player1_sprite.stop()
        if event.key == pygame.K_DOWN:
            self.player1_sprite.stop()            
        if event.key == pygame.K_w:
            self.player2_sprite.stop()
        if event.key == pygame.K_s:
            self.player2_sprite.stop()            
            
    def on_key_down_event(self, event):
        # KEYDOWN            key, mod
        if event.key == pygame.K_UP:
            self.player1_sprite.move_up()
        if event.key == pygame.K_DOWN:
            self.player1_sprite.move_down()
        if event.key == pygame.K_w:
            self.player2_sprite.move_up()
        if event.key == pygame.K_s:
            self.player2_sprite.move_down()
    

class Game(GameEngine):
    # Set your game name/version here.
    NAME = "Paddle Slap"
    VERSION = "1.0"
    
    def __init__(self, options):
        super().__init__(options=options)
        self.load_resources()

        # pygame.event.set_blocked(self.mouse_events)
        # pygame.event.set_blocked(self.joystick_events)
        # pygame.event.set_blocked(self.keyboard_events)

        # Hook up some events.
        #self.register_game_event('save', self.on_save_event)
        #self.register_game_event('load', self.on_load_event)

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
        # This is a simple class that will help us print to the screen
        # It has nothing to do with the joysticks, just outputting the
        # information.

        # Call the main game engine's start routine to initialize
        # the screen and set the self.screen_width, self.screen_height variables
        # and do a few other init related things.
        super().start()

        # Note: Due to the way things are wired, you must set self.active_scene after
        # calling super().start() in this method.
        self.clock = pygame.time.Clock()
        self.active_scene = TableScene()        

        while self.active_scene != None:
                self.process_events()                
            
                self.active_scene.update()

                self.active_scene.render(self.screen)

                if self.update_type == 'update':
                    pygame.display.update(self.active_scene.rects)
                elif self.update_type == 'flip':
                    pygame.display.flip()

                self.clock.tick(self.fps)
            
                self.active_scene = self.active_scene.next

    def on_key_up_event(self, event):
        self.active_scene.on_key_up_event(event)
        
        # KEYUP            key, mod
        if event.key == pygame.K_q:
            log.info(f'User requested quit.')
            event = pygame.event.Event(pygame.QUIT, {})
            pygame.event.post(event)

    # This will catch calls which our scene engine doesn't yet implement.
    def __getattr__(self, attr):
        try:
            if self.active_scene:
                return getattr(self.active_scene, attr)
            else:
                raise Exception(f'Scene not activated in call to {attr}()')                
        except AttributeError:
            raise AttributeError(f'{attr} is not implemented in Game {type(self)} or active scene {type(self.active_scene)}.')

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
        log.info('Done')
    except Exception as e:
        raise e
    finally:
        log.info('Shutting down pygame.')
        pygame.quit()


