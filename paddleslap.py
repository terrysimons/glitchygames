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
import random
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
log.setLevel(logging.INFO)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

log.addHandler(ch)

# TODO:
# Add --log-level flag.
# Package.
#
class Speed(object):
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y


class PaddleSprite(pygame.sprite.DirtySprite):
    def __init__(self, name):
        super().__init__()
        self.use_gfxdraw = True

        self.name = name
        self.screen = pygame.display.get_surface()
        self.screen_rect = self.screen.get_rect()
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
        self.speed = Speed()

        self.update()

    def update(self):
        self.dirty = 1

        # This prevents us from having the paddle bounce
        # at the edges.
        if self.rect.bottom + self.speed.y > self.screen_rect.bottom:
            self.rect.y = self.screen_rect.bottom - self.height
            self.stop()
        elif self.rect.top + self.speed.y < self.screen_rect.top:
            self.rect.y = 0
            self.stop()
        else:
            self.rect.y += self.speed.y
            
    def move_down(self):        
        self.speed.y = 10 
        
    def move_up(self):
        self.speed.y = -10 
        
    def stop(self):
        self.speed.x = 0
        self.speed.y = 0


class BallSprite(pygame.sprite.DirtySprite):
    def __init__(self):
        super().__init__()
        self.use_gfxdraw = True

        # Bouncy edges
        self.left_edge = False
        self.right_edge = False
        self.top_edge = True
        self.bottom_edge = True

        self.screen = pygame.display.get_surface()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()
        self.width = 20
        self.height = 20        
        self.image = pygame.Surface((self.width, self.height))
        self.image.convert()
        self.image.set_colorkey(0)
        self.rect = self.image.get_rect()
        self.speed = Speed(4, 2)

        # The ball always needs refreshing.
        # This saves us a set on dirty every update.
        self.dirty = 2        

        pygame.draw.circle(self.image, white, (self.width//2, self.height//2), 5, 0)

        self.reset()
        self.update()

    def _do_bounce(self):
        if self.top_edge and ( self.rect.y <= 0 ):
            self.rect.y = 0
            self.speed.y *= -1
        if self.bottom_edge and ( self.rect.y + self.height >= self.screen_height):
            self.rect.y = self.screen_height - self.height
            self.speed.y *= -1
        if self.left_edge and ( self.rect.x <= 0):
            self.rect.x = 0
            self.speed.x *= -1
        if self.right_edge and ( self.rect.x >= self.screen_width):
            self.rect.x = self.screen_width
            self.speed.x *= -1

    def reset(self):
        self.rect.x = self.screen_width // 2
        self.rect.y = self.screen_height // 2        

    def update(self):

        if GameEngine.FPS:
            self.rect.y += self.speed.y 
            self.rect.x += self.speed.x 

        self._do_bounce()

        if self.rect.x > self.screen_width or self.rect.x < 0:
            self.reset()


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
            def __init__(self, font_controller, pos, line_height=15):
                super().__init__()
                self.image = None
                self.start_pos = pos
                self.rect = pygame.Rect(pos, (640, 480))
                self.line_height = line_height
                
                pygame.freetype.set_default_resolution(font_controller.font_dpi)
                self.font = pygame.freetype.SysFont(name=font_controller.font,
                                                    size=font_controller.font_size)

            def print(self, surface, string):                
                (self.image, self.rect) = self.font.render(string, white)
                self.image
                surface.blit(self.image, self.rect.center)
                self.rect.center = surface.get_rect().center
                self.rect.y += self.line_height
        
            def reset(self):
                self.rect.center = self.start_pos
                
            def indent(self):
                self.x += 10
        
            def unindent(self):
                self.x -= 10

            def rect(self):
                return self.rect

        self.text_box = TextBox(font_controller=self.font_manager, pos=self.rect.center)

        self.update()
        
    def update(self):
        self.dirty = 2
        self.image.fill(self.background_color)

        self.text_box.reset()
        self.text_box.print(self.image, f'{Game.NAME} version {Game.VERSION}')
        self.text_box.print(self.image, f'FPS: {Game.FPS:.0f}')

class TableScene(RootScene):
    def __init__(self):
        super().__init__()
        self.screen = pygame.display.get_surface()        
        self.player1_sprite = PaddleSprite(name="Player 1")
        self.player2_sprite = PaddleSprite(name="Player 2")
        self.ball_sprite = BallSprite()
        self.info_sprite = TextSprite(background_color=black, alpha=0, x=0, y=0)
        #self.scoreboard_sprite = TextSprite(background_color=blacklucent, alpha=0, x=0, y=0)

        self.info_sprite.rect.center = self.screen.get_rect().center
        
        # Set player 2's position on the right side of the screen.
        self.player2_sprite.rect.x = self.player2_sprite.screen.get_width() - self.player2_sprite.width

        self.all_sprites = pygame.sprite.LayeredDirty(
            (
                self.player1_sprite,
                self.player2_sprite,
                self.ball_sprite,
                #self.info_sprite
                #self.scoreboard_sprite
            )
        )

        self.all_sprites.clear(self.screen, self.background)        

    def update(self):
        super().update()

        if pygame.sprite.collide_rect(self.player1_sprite, self.ball_sprite):
            self.ball_sprite.speed.x *= -1
            self.ball_sprite.speed.y *= 1

        if pygame.sprite.collide_rect(self.player2_sprite, self.ball_sprite):
            self.ball_sprite.speed.x *= -1
            self.ball_sprite.speed.y *= 1

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

                # Don't do anything until we know our framerate.
                while GameEngine.FPS == 0:
                    # Display the startup screen here?
                    self.clock.tick(self.fps)
                    GameEngine.FPS = self.clock.get_fps()
                
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


