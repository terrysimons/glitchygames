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
import sys
import re

from pygame import Color, Rect
import pygame
import pygame.freetype
import pygame.gfxdraw
import pygame.locals

from engine import RootScene, GameEngine, FontManager
from engine import black, white, blacklucent
from engine import JoystickManager
from engine import load_graphic_as_pixels

log = logging.getLogger('game')
log.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

log.addHandler(ch)

class RootSprite(pygame.sprite.DirtySprite):
    """
    This is a convenience class for handling all of the common sprite behaviors.
    """
    USE_GFXDRAW = False

    def __init__(self, *args, **kwargs):
        super().__init__()
        #self.name = 'Untitled'
        self.x = kwargs.get('x', 0)
        self.y = kwargs.get('y', 0)
        self.width = int(kwargs.get('width'))
        self.height = int(kwargs.get('height'))

        if not self.width:
            log.error(f'{type(self)} has 0 Width')

        if not self.height:
            log.error(f'{type(self)} has 0 Height')

        # Sprites can register callbacks for any event type.
        self.callbacks = {}

        # Each sprite maintains a reference to the screen.
        self.screen = pygame.display.get_surface()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()

        # This is the stuff pygame really cares about.
        self.image = pygame.Surface((self.width, self.height))  # noqua: 
        self.rect = self.image.get_rect()

        # Cause the sprite to update itself when it comes into existence.
        self.update()

    def update(self):
        pass

    def on_axis_motion_event(self, event):
        # JOYAXISMOTION    joy, axis, value
        log.debug(f'{type(self)}: {event}')

    def on_button_down_event(self, event):
        # JOYBUTTONDOWN    joy, button
        log.debug(f'{type(self)}: {event}')

    def on_button_up_event(self, event):
        # JOYBUTTONUP      joy, button
        log.debug(f'{type(self)}: {event}')

    def on_hat_motion_event(self, event):
        # JOYHATMOTION     joy, hat, value
        log.debug(f'{type(self)}: {event}')

    def on_ball_motion_event(self, event):
        # JOYBALLMOTION    joy, ball, rel
        log.debug(f'{type(self)}: {event}')

    def on_mouse_motion_event(self, event):
        # MOUSEMOTION      pos, rel, buttons
        log.debug(f'{type(self)}: {event}')

    def on_mouse_drag_down_event(self, event, trigger):
        log.debug(f'Mouse Drag Down Event: {type(self)}: event: {event}, trigger: {trigger}')

    def on_mouse_drag_up_event(self, event):
        log.debug(f'Mouse Drag Up Event: {type(self)}: {event}')

    def on_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button
        log.debug(f'{type(self)}: {event}')

    def on_left_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button        
        
        if self.callbacks:
            callback = self.callbacks.get('on_left_mouse_button_up_event', None)
            if callback:
                callback(event=event, trigger=self)
        else:
            log.debug(f'{type(self)}: Left Mouse Button Up Event: {event} @ {self}')


    def on_middle_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button        
        log.debug(f'{type(self)}: Middle Mouse Button Up Event: {event}')

    def on_right_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button        
        log.debug(f'{type(self)}: Right Mouse Button Up Event: {event}')

    def on_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button
        log.debug(f'{type(self)}: {event} @ {self}')

    def on_left_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button        
        callback = 'on_left_mouse_button_down_event'

        if self.callbacks:
            callback = self.callbacks.get('on_left_mouse_button_down_event', None)
            if callback:
                callback(event=event, trigger=self)
        else:
            log.debug(f'{type(self)}: Left Mouse Button Down Event: {event} @ {self}')


    def on_middle_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button        
        log.debug(f'{type(self)}: Middle Mouse Button Down Event: {event}')

    def on_right_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button        
        log.debug(f'{type(self)}: Right Mouse Button Down Event: {event}')

    def on_mouse_scroll_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button        
        log.debug(f'{type(self)}: Mouse Scroll Down Event: {event}')

    def on_mouse_scroll_up_event(self, event):
        # MOUSEBUTTONDOWN  pos, button        
        log.debug(f'{type(self)}: Mouse Scroll Up Event: {event}')

    def on_mouse_chord_up_event(self, event): 
        log.debug(f'{type(self)}: Mouse Chord Up Event: {event}')

    def on_mouse_chord_down_event(self, event):
        log.debug(f'{type(self)}: Mouse Chord Down Event: {event}')

    def on_key_down_event(self, event):
        # KEYDOWN          unicode, key, mod
        log.debug(f'{type(self)}: {event}')        
    
    def on_key_up_event(self, event):
        # KEYUP            key, mod
        log.debug(f'{type(self)}: {event}')

    def on_key_chord_down_event(self, event, keys):
        log.debug(f'{type(self)}: {event}, {keys}')

    def on_key_chord_up_event(self, event, keys):
        log.debug(f'{type(self)} KEYCHORDUP: {event}, {keys}')            

    def on_quit_event(self, event):
        # QUIT             none
        log.debug(f'{type(self)}: {event}')
        self.terminate()

    def on_active_event(self, event):
        # ACTIVEEVENT      gain, state        
        log.debug(f'{type(self)}: {event}')

    def on_video_resize_event(self, event):
        # VIDEORESIZE      size, w, h        
        log.debug(f'{type(self)}: {event}')

    def on_video_expose_event(self, event):
        # VIDEOEXPOSE      none        
        log.debug(f'{type(self)}: {event}')        
        
    def on_sys_wm_event(self, event):
        # SYSWMEVENT        
        log.debug(f'{type(self)}: {event}')

    def on_user_event(self, event):
        # USEREVENT        code
        log.debug(f'{type(self)}: {event}')

    def on_fps_event(self, event):
        # FPSEVENT is pygame.USEREVENT + 1
        log.debug(f'{type(self)}: {GameEngine.FPS}')

    def __str__(self):
        return f'{type(self)} "{self.name}" ({repr(self)})'

class ButtonSprite(RootSprite):
    """
    """

    def __init__(self, *args, **kwargs):
        self.text = None
        self.name = None
        self.background_color = (0, 0, 0)

        super().__init__(*args, **kwargs)

        self.name = kwargs.get('name', 'Untitled')
        self.background_color = (0, 0, 0)

        self.callbacks = kwargs.get('callbacks', None)

        self.rect = self.image.get_rect()
        self.rect.x = self.x
        self.rect.y = self.y

        self.text = TextSprite(background_color=self.background_color, x=self.rect.centerx, y=self.rect.centery, width=self.width, height=self.height, text=self.name)

    def update(self):
        if self.text:
            self.text.rect.center = self.rect.center

            self.text.background_color = self.background_color
            self.text.update()

            self.image.blit(self.text.image, (0, 0, self.width, self.height))

        pygame.draw.rect(self.image, (128, 128, 128), Rect(0, 0, self.width, self.height), 1)

    def on_left_mouse_button_down_event(self, event):
        self.dirty = 1
        self.background_color = (128, 128, 128)
        self.update()

    def on_left_mouse_button_up_event(self, event):
        self.dirty = 1
        self.background_color = (0, 0, 0)
        self.update()

class CheckboxSprite(ButtonSprite):
    """
    """

    def __init__(self, *args, **kwargs):
        self.checked = False
        self.color = (128, 128, 128)

        super().__init__(*args, **kwargs)

    def update(self):
        if not self.checked:
            self.image.fill((0, 0, 0))

        pygame.draw.rect(self.image, self.color, Rect(0, 0, self.width, self.height), 1)

        if self.checked:
            pygame.draw.line(self.image, self.color, (0, 0), (self.width - 1, self.height - 1), 1)
            pygame.draw.line(self.image, self.color, (0, self.height - 1), (self.width - 1, 0), 1)

        self.rect.x = self.x
        self.rect.y = self.y

    def on_left_mouse_button_down_event(self, event):
        pass

    def on_left_mouse_button_up_event(self, event):
        self.dirty = 1
        self.checked = not self.checked
        self.update()



class ScrollBarSprite(RootSprite):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def update(self):
        pass

class CanvasSprite(RootSprite):
    def __init__(self, *args, has_mini_view=True, **kwargs):
        self.character_sprite = False
        self.color = (128, 128, 128)

        self.border_thickness = 5
        self.border_margin = 5
        self.pixels_across = 32
        self.pixels_tall = 32
        self.grid_line_width = 1
        self.pixel_boxes = []
        self.pixel_width = 2
        self.pixel_height = 2
        self.has_mini_view = has_mini_view
        self.mini_view = None
        self.active_color = (255, 255, 255)

        class MiniView(CanvasSprite):
            def __init__(self, *args, border_thickness=0, pixels=None, **kwargs):
                self.pixels = pixels

                super().__init__(*args, has_mini_view=False, **kwargs)

                self.name = "Mini View"
                self.pixel_width = 5
                self.pixel_height = 5
                self.width = 32 * self.pixel_width
                self.height = 32 * self.pixel_height
                self.border_thickness = 0
                self.border_margin = 0

                self.grid_line_width = 0

                self.image = pygame.Surface((self.width, self.height))
                self.rect = self.image.get_rect()
                self.rect.x = self.screen_width - self.width
                self.rect.y = 0
                self.rect.width = self.width
                self.rect.height = self.height

                # Update our pixel boxes.
                #for pixel_box in self.pixel_boxes:
                #    pixel_box.border_thickness = 0
                #    print(f'Pixel Width: {pixel_box.width}')

                self.update()

            def update(self):
                self.dirty=2
                x = 0
                y = 0

                #self.image = pygame.Surface((self.width, self.height))
                #self.rect = self.image.get_rect()

                #self.rect.x = 240
                #self.rect.y = 240

                for pixel in self.pixels:
                    pygame.draw.rect(self.image, pixel, ((x, y), (self.pixel_width, self.pixel_height)))

                    if (x + self.pixel_width) % (self.pixels_across * self.pixel_width) == 0:
                        x = 0
                        y += self.pixel_height
                    else:
                        x += self.pixel_width
                        
                #super().update()
                self.screen.blit(self.image, (self.rect.x, self.rect.y))
                #pygame.draw.line(self.screen, (255, 0, 0), (0, 0), (240, 240))
                

            def __str__(self):
                return f'pixels across: {self.pixels_across}, pixels tall: {self.pixels_tall}, width: {self.width}, height: {self.height}, pixel width: {self.pixel_width}, pixel_height: {self.pixel_height}, pixels: {len(self.pixels)}, rect: {self.rect}'

        class BitmapPixelSprite(RootSprite):
            """
            """

            def __init__(self, *args, border_thickness=1, **kwargs):
                self.name = kwargs.get('name')
                self.pixel_width = kwargs.get('width', 0)
                self.pixel_height = kwargs.get('height', 0)
                self.border_thickness = border_thickness
                self.width = self.pixel_width + self.border_thickness * 2
                self.height = self.pixel_height + self.border_thickness * 2
                self.color = (128, 128, 128)
                self.pixel_color = (0, 0, 0)

                super().__init__(self, *args, width=self.width, height=self.height)

                self.rect = pygame.draw.rect(self.image, self.color, (0, 0, self.width, self.height), self.border_thickness)

            def update(self):
                pygame.draw.rect(self.image, self.pixel_color, (1, 1, self.width - self.border_thickness * 2, self.height - self.border_thickness * 2))

            def on_left_mouse_button_down_event(self, event):
                self.dirty = 1
                self.update()

            def on_mouse_drag_down_event(self, event, trigger):
                # There's not a good way to pass any useful info, so for now, pass None
                # since we're not using the event for anything in this class.
                self.on_left_mouse_button_down_event(None)

        super().__init__(*args, **kwargs)

        self.name = 'Bitmap Canvas'

        self.pixel_width = (self.width - self.border_margin - self.border_thickness - self.pixels_across) // self.pixels_across
        self.pixel_height = (self.height - self.border_margin - self.border_thickness - self.pixels_tall) // self.pixels_tall
        print(f'Pixels Across: {self.pixels_across}')
        print(f'Pixels Tall: {self.pixels_tall}')
        print(f'')

        self.pixels = self.load_graphic(path='resources/flower_tile1_32.raw')

        self.all_sprites = pygame.sprite.LayeredDirty()

        self.pixel_boxes = [BitmapPixelSprite(name=f'pixel {i}',
                                              x=0,
                                              y=0,
                                              height=self.pixel_width,
                                              width=self.pixel_height)
                                              for i in range(self.pixels_across * self.pixels_tall)]

        for i in range(self.pixels_across * self.pixels_tall):
            self.pixel_boxes[i].pixel_color = self.pixels[i]
            self.pixel_boxes[i].add(self.all_sprites)
            self.pixel_boxes[i].update()

        if self.has_mini_view:
            self.mini_view = MiniView(pixels=self.pixels, width=self.pixels_across, height=self.pixels_tall)
            self.mini_view.pixels = self.pixels
            self.mini_view.rect.x = self.screen_width - self.mini_view.width
            self.mini_view.rect.y = 0
            self.mini_view.add(self.all_sprites)

        # Do some cleanup
        # For some reason we have a double grid border, so let's wipe out the canvas.
        self.image.fill((0, 0, 0), rect=self.rect)

    def update(self):

        #if not self.mini_view:
            #self.draw_border()
        #    self.draw_pixels()
        #else:
        self.draw_border()
        self.draw_grid()
        self.draw_pixels()

        #if self.mini_view:
        #    self.mini_view.pixels = [pixel_box.pixel_color for pixel_box in self.pixel_boxes]
        #    self.mini_view.update()
            #print(pygame.image.tostring(self.mini_view.image, 'RGB'))
            #print(pygame.image.tostring(self.image, 'RGB'))
            #self.image.blit(self.mini_view.image, (0, 0))
            #print(f'BLIT: {self.mini_view}')
            #print(f'{self}')

    def draw_pixels(self):
        [pixel_box.update() for pixel_box in self.pixel_boxes]

    def draw_grid(self):
        x = 0
        y = 0
        for i, pixel_box in enumerate(self.pixel_boxes):
            pixel_x = self.border_margin + self.border_thickness + (x * pixel_box.pixel_width) + (x * pixel_box.border_thickness)
            pixel_y = self.border_margin + self.border_thickness + (y * pixel_box.pixel_height) + (y * pixel_box.border_thickness)

            # Note: We might be able to do this up above, and make this method super efficient.
            pixel_box.rect.x = pixel_x
            pixel_box.rect.y = pixel_y

            self.image.blit(pixel_box.image, (pixel_x, pixel_y))

            if (x + 1) % self.pixels_across == 0:
                x = 0
                y += 1
            else:
                x += 1

    def draw_border(self):
        pygame.draw.rect(self.image,
                         self.color,
                         Rect(
                              0,
                              0,
                              self.pixel_width * self.pixels_across + self.pixels_across + ((self.border_margin * 2) + (self.border_thickness * 2)) ,
                              self.pixel_height * self.pixels_tall + self.pixels_tall + ((self.border_margin * 2) + (self.border_thickness * 2)) 
                             ),
                              self.border_thickness)

    def load_graphic(self, path):
        return load_graphic_as_pixels(path=path)

    def on_left_mouse_button_down_event(self, event):
        # Check for a sprite collision against the mouse pointer.
        #
        # First, we need to create a pygame Sprite that represents the tip of the mouse.
        mouse = MouseSprite(x=event.pos[0],y=event.pos[1] , width=1, height=1)

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        print(f'collided sprites: {collided_sprites}')

        for sprite in collided_sprites:
            sprite.pixel_color = self.active_color
            sprite.on_left_mouse_button_down_event(event)

        print(f'Mouse @ {mouse.rect}')
        self.dirty = 1
        self.update()

    def on_mouse_drag_down_event(self, event, trigger):
        # Check for a sprite collision against the mouse pointer.
        #
        # First, we need to create a pygame Sprite that represents the tip of the mouse.
        #mouse = MouseSprite(x=event.pos[0],y=event.pos[1] , width=1, height=1)

        self.on_left_mouse_button_down_event(event)

        #collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        #print(f'collided sprites: {collided_sprites}')

        #for sprite in collided_sprites:
        #    sprite.on_mouse_drag_down_event(event, trigger)

        #print(f'Mouse @ {mouse.rect}')
        #self.dirty = 1
        #self.update()




class TextSprite(RootSprite):
    def __init__(self, *args, background_color=blacklucent, alpha=0, text='Text', **kwargs):
        self.background_color = (0, 0, 0)
        self.alpha = 0
        self.text = text
        self.font_manager = FontManager(self)
        self.joystick_manager = JoystickManager(self)
        self.joystick_count = len(self.joystick_manager.joysticks)

        class TextBox(object):
            def __init__(self, font_controller, x, y, line_height=15, text='Text'):
                self.image = None
                self.rect = None
                self.start_x = x
                self.start_y = y
                self.line_height = line_height

                super().__init__()


                pygame.freetype.set_default_resolution(font_controller.font_dpi)
                self.font = pygame.freetype.SysFont(name=font_controller.font,
                                                    size=font_controller.font_size)

            def print(self, surface, string):
                (self.image, self.rect) = self.font.render(string, white)
                
                #pygame.draw.rect(self.image, (255, 255, 0), self.rect, 0)

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

        self.text_box = TextBox(font_controller=self.font_manager, x=0, y=0, text=self.text)

        super().__init__(*args, **kwargs)

        self.text_box.start_x = self.rect.centerx - 10
        self.text_box.start_y = self.rect.centery - 5


        self.background_color = background_color
        self.alpha = alpha

        if not alpha:
            #self.image.set_colorkey(self.background_color)
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
        self.rect.x += self.x
        self.rect.y += self.y

        

        self.update()

    def update(self):
        self.dirty = 2
        self.image.fill(self.background_color)

        self.text_box.reset()
        self.text_box.print(self.image, f'{self.text}')

class TextBoxSprite(TextSprite):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class SliderSprite(RootSprite):
    def __init__(self, *args, **kwargs):
        self.name = kwargs.get('name', 'Untitled')
        self.height = kwargs.get('height')
        self.width = kwargs.get('width')
        self.x = kwargs.get('x')
        self.y = kwargs.get('y')
        self.text = TextSprite(background_color=(255, 0, 0), x=0, y=0, width=0, height=self.height, text=self.name)

        self.width = self.text.width + self.width
        self.height = self.text.height + self.height


        class SliderKnobSprite(RootSprite):
            def __init__(self, *args, **kwargs):
                self.name = kwargs.get('name', 'Untitled')
                self.value = 0

                super().__init__(*args, **kwargs)

                #self.image.set_colorkey((0, 0, 0))
                self.image.fill((0, 0, 0))

                self.rect = Rect(1, 1, self.width - 2, self.height - 2)

                self.update()

            def update(self):
                pygame.draw.rect(self.image, (127, 127, 127), self.rect)  
                #pygame.draw_rect(self.image, (0, 0, 0))

            def on_left_mouse_button_down_event(self, event):
                self.dirty = 1
                self.rect.x = event.pos[0]
                self.value = event.pos[0]
                self.update()
                super().on_left_mouse_button_down_event(event)

            def on_mouse_drag_down_event(self, event, trigger):
                # There's not a good way to pass any useful info, so for now, pass None
                # since we're not using the event for anything in this class.
                self.on_left_mouse_button_down_event(event)

        self.slider_knob = SliderKnobSprite(name=self.name, width=self.height//2, height=self.height//2)

        super().__init__(height=self.height, width=self.width, x=self.x, y=self.y)

        # This is the stuff pygame really cares about.
        self.image = pygame.Surface((self.width, self.height))
        self.background = pygame.Surface((self.width, self.height))
        self.image.fill((255,255,255))
        self.rect = self.image.get_rect()

        self.image.blit(self.text.image, (0, 0))
        self.rect.x = self.x
        self.rect.y = self.y
        self.text.start_x = 0
        self.text.start_y = 0

        #self.all_sprites = pygame.sprite.LayeredDirty((self.slider_knob))
        
        for i in range(255):
            if self.name == 'R':
                pygame.draw.line(self.image, (i, 0, 0), (self.text.width + i, self.height//2 - 1), (self.text.width + i, self.height//2), 1)
                pygame.draw.line(self.image, (i, 0, 0), (self.text.width + i, self.height//2), (self.text.width + i, self.height//2), 1)
                pygame.draw.line(self.image, (i, 0, 0), (self.text.width + i, self.height//2 + 1), (self.text.width + i, self.height//2), 1)

            elif self.name == 'G':
                pygame.draw.line(self.image, (0, i, 0), (self.text.width + i, self.height//2 - 1), (self.text.width + i, self.height//2), 1)
                pygame.draw.line(self.image, (0, i, 0), (self.text.width + i, self.height//2), (self.text.width + i, self.height//2), 1)
                pygame.draw.line(self.image, (0, i, 0), (self.text.width + i, self.height//2 + 1), (self.text.width + i, self.height//2), 1)
            elif self.name == 'B':
                pygame.draw.line(self.image, (0, 0, i), (self.text.width + i, self.height//2 - 1), (self.text.width + +i, self.height//2), 1)
                pygame.draw.line(self.image, (0, 0, i), (self.text.width + i, self.height//2), (self.text.width + +i, self.height//2), 1)
                pygame.draw.line(self.image, (0, 0, i), (self.text.width + i, self.height//2 + 1), (self.text.width + +i, self.height//2), 1)
            else:
                pygame.draw.line(self.image, (255, 255, 255), (self.text.width, self.height//2), (self.text.width + 255, self.height//2), 1)


    @property
    def value(self):
        return self.slider_knob.value

    def update(self):
        #pygame.draw.rect(self.image, (255, 0, 0), Rect(self.rect.centerx, self.rect.centery, self.rect.width, self.rect.height), 1)

        # Draw the knob
        self.image.blit(self.slider_knob.image, (self.slider_knob.value, self.rect.height//4))
        super().update()


    def on_left_mouse_button_down_event(self, event):
        self.dirty = 1

        print('Calling Slider Knob Callback')
        self.slider_knob.on_left_mouse_button_down_event(event)
        self.update()
        super().on_left_mouse_button_down_event(event)

    def on_mouse_drag_down_event(self, event, trigger):
        self.dirty = 1
        # There's not a good way to pass any useful info, so for now, pass None
        # since we're not using the event for anything in this class.
        self.slider_knob.on_mouse_drag_down_event(event, trigger)
        self.update()
        

class LabeledSliderSprite(SliderSprite):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class MouseSprite(RootSprite):
    def __init__(self, *args, **kwargs):
        self.x = kwargs.get('x')
        self.y = kwargs.get('y')

        super().__init__(*args, **kwargs)

        self.rect.x = self.x
        self.rect.y = self.y

class BitmapEditorScene(RootScene):
    def __init__(self):
        super().__init__()
        self.screen = pygame.display.get_surface()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()
        self.button_width = 75

        self.scroll_bar_sprite = ScrollBarSprite(name='File List', x=0, y=0, width=20, height=300)

        # We'll use the top left quartile of the screen to draw the canvas.
        # We want a square canvas, so we'll use the height as our input.
        self.canvas_sprite = CanvasSprite(name='Bitmap Canvas', x=0, y=0, width=int(self.screen_height * 0.75), height=int(self.screen_height * 0.75))
        self.new_button_sprite = ButtonSprite(name='New', x=self.screen_width - self.button_width, y=219, width=self.button_width, height=20)

        self.new_button_sprite.callbacks = {'on_left_mouse_button_down_event': self.on_new_file_event}

        self.save_button_sprite = ButtonSprite(name='Save', x=self.screen_width - self.button_width, y=249, width=self.button_width, height=20)

        self.new_button_sprite.callbacks = {'on_left_mouse_button_down_event': self.on_save_file_event}

        self.load_button_sprite = ButtonSprite(name='Load', x=self.screen_width - self.button_width, y=279, width=self.button_width, height=20)

        self.load_button_sprite.callbacks = {'on_left_mouse_button_down_event': self.on_load_file_event}

        self.quit_button_sprite = ButtonSprite(name='Quit', x=self.screen_width - self.button_width, y=309, width=self.button_width, height=20)

        self.quit_button_sprite.callbacks = {'on_left_mouse_button_down_event': self.on_quit_event}

        self.red_slider_sprite = LabeledSliderSprite(name='R', x=0, y=self.screen_height - 70, width=255, height=10)

        self.red_slider_sprite.callbacks = {'on_left_mouse_button_down_event': self.on_slider_event}

        self.blue_slider_sprite = LabeledSliderSprite(name='G', x=0, y=self.screen_height - 50, width=255, height=10)

        self.blue_slider_sprite.callbacks = {'on_left_mouse_button_down_event': self.on_slider_event}

        self.green_slider_sprite = LabeledSliderSprite(name='B', x=0, y=self.screen_height - 30, width=255, height=10)

        self.green_slider_sprite.callbacks = {'on_left_mouse_button_down_event': self.on_slider_event}

        self.checkbox_sprite = CheckboxSprite(name='Foo', x=400, y=240, width=48, height=48)
        

        #self.text_sprite = TextSprite(background_color=blacklucent, alpha=0, x=0, y=0)

        self.red = self.red_slider_sprite.value
        self.green = self.green_slider_sprite.value
        self.blue = self.blue_slider_sprite.value

        self.canvas_sprite.active_color = (self.red, self.green, self.blue)

        self.all_sprites = pygame.sprite.LayeredDirty(
            (
                #self.scroll_bar_sprite,
                self.canvas_sprite,
                self.canvas_sprite.mini_view,
                self.new_button_sprite,
                self.save_button_sprite,
                self.load_button_sprite,
                self.quit_button_sprite,
                self.red_slider_sprite,
                self.blue_slider_sprite,
                self.green_slider_sprite,
                self.checkbox_sprite
            )
        )

        self.all_sprites.clear(self.screen, self.background)

    def update(self):
        super().update()

    def render(self, screen):
        super().render(screen)

    def switch_to_scene(self, next_scene):
        super().switch_to_scene(next_scene)

    def on_new_file_event(self, event, trigger):
        log.info(f'New File: event: {event}, trigger: {trigger}')

    def on_load_file_event(self, event, trigger):
        log.info(f'Load File: event: {event}, trigger: {trigger}')

    def on_save_file_event(self, event, trigger):
        log.info(f'Safe File: event: {event}, trigger: {trigger}')

    def on_quit_event(self, event, trigger):
        log.info(f'Quit: event: {event}, trigger: {trigger}')

    def on_slider_event(self, event, trigger):
        if trigger.name == 'R':
            self.red = trigger.value
        elif trigger.name == 'G':
            self.green = trigger.value
        elif trigger.name == 'B':
            self.blue = trigger.value
        else:
            log.debug(f'Slider: event: {event}, trigger: {trigger} value: {trigger.value}')

        self.canvas_sprite.active_color = (self.red, self.green, self.blue)


    def on_key_up_event(self, event):
        # 1-8 selects Sprite Frame
        # Spacebar
        # Escape quits
        # c cycles through color boxes
        # r swap recent colors
        # n new bitmap
        # l load bitmap
        # s save bitmap
        pass

    def on_key_down_event(self, event):
        pass

    def on_right_mouse_button_down_event(self, event):
        pass

    def on_left_mouse_button_down_event(self, event):
        # Check for a sprite collision against the mouse pointer.
        #
        # First, we need to create a pygame Sprite that represents the tip of the mouse.
        mouse = MouseSprite(x=event.pos[0],y=event.pos[1] , width=1, height=1)

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for sprite in collided_sprites:
            sprite.on_left_mouse_button_down_event(event)

        print(f'Mouse @ {mouse.rect}')

    def on_left_mouse_button_up_event(self, event):
        # Check for a sprite collision against the mouse pointer.
        #
        # First, we need to create a pygame Sprite that represents the tip of the mouse.
        mouse = MouseSprite(x=event.pos[0],y=event.pos[1] , width=1, height=1)

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for sprite in collided_sprites:
            sprite.on_left_mouse_button_up_event(event)

        print(f'Mouse @ {mouse.rect}')

    def on_mouse_drag_down_event(self, event, trigger):
        # Check for a sprite collision against the mouse pointer.
        #
        # First, we need to create a pygame Sprite that represents the tip of the mouse.
        mouse = MouseSprite(x=event.pos[0],y=event.pos[1] , width=1, height=1)

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for sprite in collided_sprites:
            sprite.on_mouse_drag_down_event(event, trigger)

        print(f'Mouse Drag @ {mouse.rect}')

    def on_mouse_drag_up_event(self, event):
        # Check for a sprite collision against the mouse pointer.
        #
        # First, we need to create a pygame Sprite that represents the tip of the mouse.
        mouse = MouseSprite(x=event.pos[0],y=event.pos[1] , width=1, height=1)

        collided_sprites = pygame.sprite.spritecollide(mouse, self.all_sprites, False)

        for sprite in collided_sprites:
            sprite.on_mouse_drag_up_event(event)

        print(f'Mouse Drag @ {mouse.rect}')

class Game(GameEngine):
    # Set your game name/version here.
    NAME = "Bitmappy"
    VERSION = "0.0"

    def __init__(self, options):
        super().__init__(options=options)
        self.load_resources()

        # pygame.event.set_blocked(self.mouse_events)
        # pygame.event.set_blocked(self.joystick_events)
        # pygame.event.set_blocked(self.keyboard_events)

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

        # Note: Due to the way things are wired, you must set self.active_scene after
        # calling super().start() in this method.
        self.clock = pygame.time.Clock()
        self.active_scene = BitmapEditorScene()

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


    #def load_resources(self):
    #    for resource in glob.iglob('resources/*', recursive=True):
    #        try:
    #            pass
    #        except IsADirectoryError:
    #            pass

    def on_key_up_event(self, event):
        self.active_scene.on_key_up_event(event)

        # KEYUP            key, mod
        if event.key == pygame.K_q:
            log.info(f'User requested quit.')
            event = pygame.event.Event(pygame.QUIT, {})
            pygame.event.post(event)

    def on_save_event(self, event):
        log.info('Save!')
        self.active_scene.on_save_event(event)

    def on_load_event(self, event):
        log.info('Load!')
        self.active_scene.on_load_event(event)

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


