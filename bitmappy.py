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

from engine import *

log = logging.getLogger('game.bitmappy')
log.setLevel(logging.INFO)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

log.addHandler(ch)

class ShapesSprite(pygame.sprite.DirtySprite):
    def __init__(self):
        super().__init__()
        self.use_gfxdraw = True

        self.screen = pygame.Surface(pygame.display.get_surface().get_size())
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()
        self.screen.convert()
        self.screen.fill(black)
        self.image = self.screen
        self.rect = self.image.get_rect()

        self.point = None
        self.circle = None
        self.triangle = None

        self.update()

    def move(self, pos):
        self.rect.center = pos
        self.dirty = 1
            
    def update(self):
        self.dirty = 1

        self._draw_point()
        self._draw_triangle()        
        self._draw_circle()
        self._draw_rectangle()

    def _draw_point(self):
        # Draw a yellow point.
        # There's no point API, so we'll fake
        # it with the line API.
        if self.use_gfxdraw:
            pygame.gfxdraw.pixel(self.screen,
                                 self.screen_width//2,
                                 self.screen_height//2,
                                 yellow)

            self.point = (self.screen_width//2, self.screen_height//2)
        else:
            self.point = pygame.draw.line(self.screen,
                                          yellow,
                                          (self.screen_width//2, self.screen_height//2),
                                          (self.screen_width//2, self.screen_height//2))    

    def _draw_circle(self):
        # Draw a blue circle.
        if self.use_gfxdraw:
            circle = pygame.gfxdraw.circle(self.screen, self.screen_width//2, self.screen_height//2, self.screen_height//2, blue)
        else:
            circle = pygame.draw.circle(self.screen, blue, (self.screen_width//2, self.screen_height//2), self.screen_height//2, 1)        

    def _draw_triangle(self):
        # Draw a green triangle.
        # polygon(Surface, color, pointlist, width=0) -> Rect
        x1 = self.screen_width//2
        y1 = 0
        x2 = self.rectangle.bottomleft[0]
        y2 = self.rectangle.bottomleft[1] - 1
        x3 = self.rectangle.bottomright[0]
        y3 = self.rectangle.bottomright[1] - 1

        top_point = (x1, y1)
        left_point = (x2, y2)
        right_point = (x3, y3)
        pointlist = (top_point, left_point, right_point)

        if self.use_gfxdraw:
            pygame.gfxdraw.polygon(self.screen, pointlist, green)
                
            # You could also use:
            # pygame.gfxdraw.trigon(self.screen, x1, y1, x2, y2, x3, y3, green)
            
            self.triangle = pointlist
        else:
            self.triangle = pygame.draw.polygon(self.screen, green, pointlist, 1)

    @property
    def rectangle(self):
        rect = Rect(0, 0, self.screen_height, self.screen_height)
        rect.center = (self.screen_width/2, self.screen_height/2)

        return rect

    def _draw_rectangle(self):
        # Draw a purple rectangle.
        # Note that the pygame documentation has a typo
        # Do not use width=1, use 1 instead.
        if self.use_gfxdraw:
            pygame.gfxdraw.rectangle(self.screen, self.rectangle, purple)
            #log.info(f'gfxdraw rectangle: {self.rectangle}')
        else:
            self.rectangle = pygame.draw.rect(self.screen, purple, self.rectangle, 1)
            #log.info(f'pygame rectangle: {self.rectangle}')
        

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

class BitmapEditorScene(Scene):
    def __init__(self):
        super().__init__()
        self.shapes_sprite = ShapesSprite()
        self.text_sprite = TextSprite(background_color=blacklucent, alpha=0, x=0, y=0)

        self.all_sprites = pygame.sprite.LayeredDirty(
            (
                self.shapes_sprite,
                self.text_sprite
            )
        )

    def update(self):
        super().update()

    def render(self, screen):
        super().render(screen)

    def switch_to_scene(self, next_scene):
        super().switch_to_scene(next_scene)

    #def on_key_up_event(self, event):
    #    print("BitmapEditorScene.on_key_up_event(event)")

    #def on_key_down_event(self, event):
    #    print("BitMapEditorScene.on_key_down_event(event)")

    #def on_mouse_down_event(self, event):
    #    print("OH MY GOD")

    #def on_active_event(self, event):
    #    pass
        #print("HOLY SHIT")

    #def on_active_event(self, event):
    #    print("Active!")
        

class Game(GameEngine):
    # Set your game name/version here.
    NAME = "Bitmappy"
    VERSION = "0.0"
    
    def __init__(self, options):
        super().__init__(options=options)
        self.starting_scene = BitmapEditorScene()
        self.clock = pygame.time.Clock()
        self.active_scene = self.starting_scene
        self.load_resources()

        pygame.event.set_blocked(self.mouse_events)
        pygame.event.set_blocked(self.joystick_events)
        pygame.event.set_blocked(self.keyboard_events)
        

        # Hook up some events.
        self.register_game_event('save', self.on_save_event)
        self.register_game_event('load', self.on_load_event)

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

        while self.active_scene != None:
            self.process_events()

            self.active_scene.update()

            self.active_scene.render(self.screen)

            pygame.display.update(self.active_scene.rects)

            self.clock.tick(self.fps)
            
            self.active_scene = self.active_scene.next

        log.info(f'FPS: {GameEngine.FPS}')

    # Pass any unknown calls to the current scene.

    def load_resources(self):
        for resource in glob.iglob('resources/*', recursive=True):
            try:
                pass
            except IsADirectoryError:
                pass

    #def on_mouse_motion_event(self, event):
        # MOUSEMOTION      pos, rel, buttons
    #    print('GAME MOUSEMOTION')
    #    super().on_mouse_motion_event(event)
        #self.shapes_sprite.move(event.pos)

    #def on_left_mouse_button_up(self, event):
    #    super().on_left_mouse_button_up(event)
        #self.post_game_event('recharge', {'item': 'bullet', 'rate': 1})
        
    #def on_left_mouse_button_down(self, event):
     #   super().on_left_mouse_button_down(event)
        #self.post_game_event('pew pew', {'bullet': 'big boomies'})

    #def on_key_down_event(self, event):
    #    print('fdafdasfdsfdafddsa')

    def on_key_up_event(self, event):
        # KEYUP            key, mod
        if event.key == pygame.K_q:
            log.info(f'User requested quit.')                        
            event = pygame.event.Event(pygame.QUIT, {})
            pygame.event.post(event)
        else:
            # If you want some keys to be handled by
            # the game and some to be handled by the
            # scene, you need to call the scene when
            # an event you don't need is caught by
            # your event handler.
            self.active_scene.on_key_up_event(event)

    def on_save_event(self, event):
        log.info('Save!')

    def on_load_event(self, event):
        log.info('Load!')

    def on_quit_event(self, event):
        log.info('Quit was called.')

        # Should we call the scene manager here to let it know?

        # Call the GameEngine quit, so it will clean up.
        super().on_quit_event(event)

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


