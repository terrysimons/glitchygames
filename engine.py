#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import copy
import glob
import inspect
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

log = logging.getLogger('game.engine')
log.addHandler(logging.NullHandler())

# Note: I want to handle this a bit differently.
yellow = pygame.Color(128, 128, 0, 255)
purple = pygame.Color(121, 7, 242, 255)
blue = pygame.Color(0, 0, 255, 255)
green = pygame.Color(0, 255, 255)
white = pygame.Color(255, 255, 255, 255)
black = pygame.Color(0, 0, 0, 0)
blacklucent = pygame.Color(0, 0, 0, 127)
bluelucent = pygame.Color(0, 96, 255, 127)
red = pygame.Color(255, 0, 0)

def load_graphic_as_pixels(path):
    data = None

    print(f'Loading: {path}')
    
    with open(path, 'rb') as fh:
        data = fh.read()

    fmt = "<%dc" % (len(data))
    image = list(struct.unpack(fmt, data))

    pixels = []
    subpixels = [int(subpixel) for subpixel in data]    
    while subpixels:
        pixel = (subpixels.pop(0), subpixels.pop(0), subpixels.pop(0))
        pixels.append(pixel)

    return pixels


def load_graphic(path):
    #data = None

    #print(f'Loading: {path}')
    
    #with open(path, 'rb') as fh:
    #    data = fh.read()

    #fmt = "<%dc" % (len(data))
    #image = list(struct.unpack(fmt, data))

    #pixels = []
    #subpixels = [int(subpixel) for subpixel in data]    
    #while subpixels:
    #    pixel = (subpixels.pop(0), subpixels.pop(0), subpixels.pop(0))
    #    pixels.append(pixel)

    pixels = load_graphic_as_pixels(path)

    graphic = pygame.Surface((32, 32))
    y = 0
    x = 0
    for pixel in pixels:
        graphic.fill(pixel, ((x, y), (1, 1)))

        if (x + 1) % 32 == 0:
            x = 0
            y += 1
        else:
            x += 1

    return graphic



#class BaseEngine(object):
#    def __init__(self, *args, **kwargs):
#        self.ready = False

#    @classmethod
#    def args(cls, parser):
#        return parser

#    def start(self):
#        pass

class ResourceManager(object):
    def __init__(self, game, **kwargs):
        super().__init__()
        self.game = game

class FontManager(ResourceManager):
    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        
        # Register pygame.freetype
        pygame.freetype.init()
        pygame.font.init()

        self.font = kwargs.get('font', pygame.freetype.get_default_font())
        self.font_size = kwargs.get('font_size', 12)
        self.font_bold = kwargs.get('font_bold', False)
        self.font_italic = kwargs.get('font_italic', False)
        self.font_antialias = kwargs.get('font_antialias', False)
        self.font_dpi = kwargs.get('font_dpi', 72)
        self.ready = True

        # Ideally, I'd like to support both modes.
        # 
        # https://www.pygame.org/docs/ref/font.html
        # To use the pygame.freetypeEnhanced pygame module for loading
        # and rendering computer fonts based pygame.ftfont as pygame.fontpygame
        # module for loading and rendering fonts define the environment variable
        # PYGAME_FREETYPE before the first import of pygamethe top level pygame
        # package. Module pygame.ftfont is a pygame.fontpygame module for loading
        # and rendering fonts compatible module that passes all but one of the font
        # module unit tests: it does not have the UCS-2 limitation of the SDL_ttf
        # based font module, so fails to raise an exception for a code point greater
        # than 'uFFFF'. If pygame.freetypeEnhanced pygame module for loading and
        # rendering computer fonts is unavailable then the SDL_ttf font module
        # will be loaded instead.
        #pygame.ftfont.init()

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Font Options')        
        
        group.add_argument('--font',
                           default=None)
        group.add_argument('--font-size',
                           type=int,
                           default=16)
        group.add_argument('--font-bold',
                           action='store_true',
                           default=False)
        group.add_argument('--font-italic',
                           action='store_true',
                           default=False)
        group.add_argument('--font-antialias',
                           action='store_true',
                           default=False)
        group.add_argument('--font-dpi',
                           type=int,
                           default=72)

        return parser

class MusicManager(ResourceManager):
    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)        

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Music Options')

        return parser

class SoundManager(ResourceManager):
    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        
        # Set the mixer pre-init settings
        pygame.mixer.pre_init(22050, -16, 2, 1024)

        # Sound Stuff
        # pygame.mixer.get_init() -> (frequency, format, channels)
        (frequency, format, channels) = pygame.mixer.get_init()
        log.info('Mixer Settings:')
        log.info(f'Frequency: {frequency}, Format: {format}, Channels: {channels}')
        self.ready = True

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Sound Mixer Options')

        return parser

class KeyboardManager(ResourceManager):
    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)

        class KeyboardProxy(object):
            def __init__(self, game, **kwargs):
                super().__init__()
                self.game = game
                self.keys = {}

            def on_key_down_event(self, event):
                # The KEYUP and KEYDOWN events are
                # different.  KEYDOWN contains an extra
                # key in its dictionary (unicode), which
                # KEYUP does not contain, so we'll make
                # a copy of the dictionary, and then
                # delete the key "unicode" so we can track
                # both sets of events.
                keyboard_key = event.dict.copy()
                del(keyboard_key['unicode'])
                
                # This makes it possible to use
                # a dictionary as a key, which is
                # normally not possible.
                self.keys[
                    tuple(
                        sorted(
                            frozenset(keyboard_key.items())
                        )
                    )
                ] = event

                self.game.on_key_down_event(event)
                self.on_key_chord_down_event(event)                

            def on_key_up_event(self, event):
                # This makes it possible to use
                # a dictionary as a key, which is
                # normally not possible.                
                self.keys[
                    tuple(
                        sorted(
                            frozenset(event.dict.items())
                        )
                    )
                ] = event
                
                self.game.on_key_up_event(event)
                self.on_key_chord_up_event(event)                

            def on_key_chord_down_event(self, event):
                keys_down = [self.keys[key]
                             for key in self.keys
                             if self.keys[key].type == pygame.KEYDOWN]

                self.game.on_key_chord_down_event(event, keys_down)

            def on_key_chord_up_event(self, event):
                keys_down = [self.keys[key]
                             for key in self.keys
                             if self.keys[key].type == pygame.KEYDOWN]

                self.game.on_key_chord_up_event(event, keys_down)

            # This will allow calls to the keyboard which aren't implemented here.
            def __getattr__(self, attr):
                error = None
                
                try:
                    try:
                        return getattr(self.game, attr)
                    except AttributeError as e:
                        error = e
                        return getattr(pygame.key, attr)
                except AttributeError:
                    raise error

        self.keyboard = KeyboardProxy(game=self.game)

    def __getattr__(self, attr):
        try:
            return getattr(self.keyboard, attr)
        except AttributeError:
            raise AttributeError(f'{attr} is not implemented in {type(self.game)}')    

class MouseManager(ResourceManager):
    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        self.game = game

        class MouseProxy(object):
            def __init__(self, game, **kwargs):
                super().__init__()                
                self.game = game
                self.mouse_state = {}

            def on_mouse_motion_event(self, event):
                self.mouse_state[event.type] = event
                
                self.game.on_mouse_motion_event(event)

            def on_mouse_button_up_event(self, event):
                self.mouse_state[event.button] = event
                
                self.game.on_mouse_button_up_event(event)

            def on_mouse_button_down_event(self, event):
                self.mouse_state[event.button] = event

                self.game.on_mouse_button_down_event(event)

            # For any unimplemented attributes, we'll first try to call out
            # to the game.  If that fails, we'll try calling pygame.
            #
            # Specifically
            # on_mouse_chord_up_event
            # on_mouse_chord_down_event
            # on_mouse_scroll_up_event
            # on_mouse_scroll_down_event
            def __getattr__(self, attr):
                error = None
                
                try:
                    try:
                        return getattr(self.game, attr)
                    except AttributeError as e:
                        error = e
                        return getattr(pygame.mouse, attr)
                except AttributeError:
                    raise error
        
        self.mouse = MouseProxy(game=self.game)

    def __getattr__(self, attr):                
        try:
            return getattr(self.mouse, attr)
        except AttributeError:
            raise AttributeError(f'{attr} is not implemented in Game {type(self.game)}')
    
    
class JoystickManager(ResourceManager):
    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        self.game = game
        self.joysticks = []

        class JoystickProxy(object):
            """Some Joysticks are very slow reading certain attributes such as name, etc.  This fixes that.
            """
            def __init__(self, game, id):
                super().__init__()
                self.game = game
                self._id = id
                self.joystick = pygame.joystick.Joystick(self._id)
                self.joystick.init()
                self._name = self.joystick.get_name()
                self._init = self.joystick.get_init()

                self._numaxes = self.joystick.get_numaxes()
                self._numballs = self.joystick.get_numballs()
                self._numbuttons = self.joystick.get_numbuttons()
                self._numhats = self.joystick.get_numhats()

                # Initialize button state.
                self._axes = [self.joystick.get_axis(i) for i in range(self.get_numaxes())]
                self._balls = [self.joystick.get_ball(i) for i in range(self.get_numballs())]
                self._buttons = [self.joystick.get_button(i) for i in range(self.get_numbuttons())]
                self._hats = [self.joystick.get_hat(i) for i in range(self.get_numhats())]

            # Define some high level APIs
            def on_axis_motion_event(self, event):
                # JOYAXISMOTION    joy, axis, value
                self._axes[event.axis] = event.value
                self.game.on_axis_motion_event(event)

            def on_button_down_event(self, event):
                # JOYBUTTONDOWN    joy, button                
                self._buttons[event.button] = 1
                self.game.on_button_down_event(event)

            def on_button_up_event(self, event):
                # JOYBUTTONUP      joy, button
                self._buttons[event.button] = 0
                self.game.on_button_up_event(event)
            
            def on_hat_motion_event(self, event):
                # JOYHATMOTION     joy, hat, value
                self._hats[event.hat] = event.value
                self.game.on_hat_motion_event(event)

            def on_ball_motion_event(self, event):
                # JOYBALLMOTION    joy, ball, rel
                self._balls[event.ball] = rel
                self.game.on_ball_motion_event(event)

            # We can't make these properties, because then they
            # wouldn't be callable as functions.
            def get_name(self):
                return self._name

            def get_init(self):
                return self._init

            def get_numaxes(self):
                return self._numaxes

            def get_numballs(self):
                return self._numballs

            def get_numbuttons(self):
                return self._numbuttons

            def get_numhats(self):
                return self._numhats

            def __str__(self):
                joystick_info = []
                joystick_info.append(f'Joystick Name: self.get_name()')
                joystick_info.append(f'\tJoystick Id: {self.get_id()}')
                joystick_info.append(f'\tJoystick Inited: {self.get_init()}')
                joystick_info.append(f'\tJoystick Axis Count: {self.get_numaxes()}')
                joystick_info.append(f'\tJoystick Trackball Count: {self.get_numballs()}')
                joystick_info.append(f'\tJoystick Button Count: {self.get_numbuttons()}')
                joystick_info.append(f'\tJoystick Hat Count: {self.get_numhats()}')        
                return '\n'.join(joystick_info)

            def __repr__(self):
                return repr(self.joystick)

            # For any unimplemented attributes, we'll first try to call out
            # to the game.  If that fails, we'll try calling pygame.            
            def __getattr__(self, attr):
                error = None
                
                try:
                    try:
                        return getattr(self.game, attr)
                    except AttributeError as e:
                        error = e
                        return getattr(self.joystick, attr)
                except AttributeError:
                    raise error

        # This must be called before other joystick methods,
        # and is safe to call more than once.
        pygame.joystick.init()
        
        log.info(f'Joystick Module Inited: {pygame.joystick.get_init()}')

        # Joystick Setup
        log.info(f'Joystick Count: {pygame.joystick.get_count()}')
        joysticks = [pygame.joystick.Joystick(x) for x in range(pygame.joystick.get_count())]

        for i, joystick in enumerate(joysticks):
            joystick.init()
            joystick_proxy = JoystickProxy(game=self.game, id=joystick.get_id())
            self.joysticks.append(joystick_proxy)

            # The joystick proxy overrides the joystick object
            log.info(joystick_proxy)

        self.ready = True

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Joystick Options')

        return parser

    def start(self):
        pass

    # Define some high level APIs
    #
    # Note that we can't pass these through the way
    # we do for other event types because
    # we need to know which joystick the event is intended for.
    def on_axis_motion_event(self, event):
        # JOYAXISMOTION    joy, axis, value        
        log.debug(f'JOYAXISMOTION triggered: axis_motion_event({event})')
        self.joysticks[event.joy].on_axis_motion_event(event)

    def on_button_down_event(self, event):
        # JOYBUTTONDOWN    joy, button
        log.debug(f'JOYBUTTONDOWN triggered: button_down_event({event})')
        self.joysticks[event.joy].on_button_down_event(event)
        
    def on_button_up_event(self, event):
        # JOYBUTTONUP      joy, button
        log.debug(f'JOYBUTTONUP triggered: button_up_event({event})')
        self.joysticks[event.joy].on_button_up_event(event)        

    def on_hat_motion_event(self, event):
        # JOYHATMOTION     joy, hat, value
        log.debug(f'JOYHATMOTION triggered: hat_motion_event({event})')
        self.joysticks[event.joy].on_hat_motion_event(event)        

    def on_ball_motion_event(self, event):
        # JOYBALLMOTION    joy, ball, rel
        log.debug(f'JOYBALLMOTION triggered: ball_motion_event({event})')
        self.joysticks[event.joy].on_ball_motion_event(event)

# NB: Do we even need this, really?
class InputManager(ResourceManager):
    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        self.game = game
        self.joystick_manager = JoystickManager(game, **kwargs)
        self.keyboard_manager = KeyboardManager(game, **kwargs)
        self.mouse_manager = MouseManager(game, **kwargs)

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Input Options')

        return parser

    
class GameManager(ResourceManager):
    def __init__(self, game, **kwargs):
        super().__init__(game, **kwargs)
        self.game = game
        
        class GameProxy(object):
            def __init__(self, game, **kwargs):
                super().__init__()
                self.game = game

            # For any unimplemented attributes, we'll first try to call out
            # to the game.  If that fails, we'll try calling pygame.  If
            # that fails, then we'll surface the error from the game access error.
            def __getattr__(self, attr):
                error = None
                
                try:
                    try:
                        return getattr(self.game, attr)
                    except AttributeError as e:
                        error = e
                        return getattr(pygame, attr)
                except AttributeError:
                    raise error

        self.game = GameProxy(game=self.game)

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Game Options')

        return parser

    def __getattr__(self, attr):
        try:
            return getattr(self.game, attr)
        except AttributeError:
            raise  AttributeError(f'The game {type(self.game.game)} has not implemented "{attr}"')

class GameEngine(object):
    NAME = "Boilerplate Adventures"
    VERSION = "1.0"
    FPSEVENT = pygame.USEREVENT + 1
    GAMEEVENT = pygame.USEREVENT + 2
    FPS = 0
    
    def __init__(self, options=None):
        # General stuff.
        self.cpu_count = multiprocessing.cpu_count()
        self.system = platform.system()
        self.machine = platform.machine()
        self.platform = platform.platform(aliased=0, terse=0)
        self.platform_terse = platform.platform(aliased=0, terse=1)
        self.processor = platform.processor()
        self.release = platform.release()

        log.info(f'CPU Count: {self.cpu_count}')
        log.info(f'System: {self.system}')
        log.info(f'Machine: {self.machine}')
        log.info(f'Platform: {self.platform}')
        log.info(f'Platform (Terse): {self.platform_terse}')
        log.info(f'Processor: {self.processor}')
        log.info(f'Release: {self.release}')

        # Pygame stuff.
        pygame.register_quit(self.quit)
        self.fps = options.get('fps', 0)
        self.update_type = options.get('update_type')
        self.use_gfxdraw = options.get('use_gfxdraw')
        self.video_driver = options.get('video_driver')
        self.windowed = options.get('windowed')
        self.desired_resolution = options.get('resolution')
        self.fps_refresh_rate = options.get('fps_refresh_rate')

        log.info(f'Game Title: {type(self).NAME}')
        log.info(f'Game Version: {type(self).VERSION}')

        # Initialize all of the Pygame modules.
        self.init_pass, self.init_fail = pygame.init()
        log.debug(f'Successfully loaded {self.init_pass} modules and failed loading {self.init_fail} modules.')

        # Enable fast events for multithreaded applications
        pygame.fastevent.init()

        self.clock = pygame.time.Clock()

        self.font_manager = FontManager(self, **options)
        self.sound_manager = SoundManager(self, **options)
        self.music_manager = MusicManager(self, **options)
        self.input_manager = InputManager(self, **options)
        self.joystick_manager = self.input_manager.joystick_manager
        self.keyboard_manager = self.input_manager.keyboard_manager
        self.mouse_manager = self.input_manager.mouse_manager
        self.game_manager = GameManager(self, **options)
        self.registered_events = {}

        # Get count of joysticks
        if self.joystick_manager:
            self.joysticks = self.joystick_manager.joysticks
            self.joystick_count = len(self.joysticks)

        # Resolution initialization.
        # Convert our resolution to a tuple
        (self.desired_width, self.desired_height) = self.desired_resolution.split('x')
        if self.windowed:
            self.mode_flags = 0
        else:
            self.mode_flags = pygame.FULLSCREEN

            # For Ubuntu 19.04, we can't reset the original res
            # so let's just let the system figure it out.
            if self.system == 'Linux':
                log.info('Ignoring full screen resolution change on Linux.')
                self.desired_width = 0
                self.desired_height = 0                
        self.color_depth = 0
        self.desired_resolution = (int(self.desired_width), int(self.desired_height))

        # Event Handling Shortcuts
        self.mouse_events = [pygame.MOUSEMOTION,
                             pygame.MOUSEBUTTONDOWN,
                             pygame.MOUSEBUTTONUP]

        self.joystick_events = [pygame.JOYAXISMOTION,
                                pygame.JOYBALLMOTION,
                                pygame.JOYHATMOTION,
                                pygame.JOYBUTTONUP,
                                pygame.JOYBUTTONDOWN]

        self.keyboard_events = [pygame.KEYDOWN,
                                pygame.KEYUP]

        # Display some configuration information.
        log.info(f'SDL Version: {pygame.get_sdl_version()}')
        log.info(f'SDL Byte Order: {pygame.get_sdl_byteorder()}')

        # Set up a display mode.
        # Note: pygame.display.init() isn't necessary here
        # because we've already called pygame.init() which
        # initializes all available modules.
        #
        # Let's do a sanity check and make sure we're initialized.
        log.info(f'Display inited: {pygame.display.get_init()}')

        # Set the window icon.
        #
        # Always call this before you call set_mode()
        icon = pygame.Surface((32, 32))
        icon.fill(purple)
        pygame.display.set_icon(icon)

        # Set the display caption.
        pygame.display.set_caption(f'{type(self).NAME}        ',
                                   f'{type(self).NAME}')

        # Get captions:
        (title, icontitle) = pygame.display.get_caption()
        log.info(f'Window Title: {title}')
        log.info(f'Icon Title: {icontitle}')        

        # Let's try to set a resolution to the most compatible for
        # the system.  If we don't provide any parameters, we'll get
        # a reasonble default, but you should consider whether that's
        # a good idea for your particular application.
        #
        # We'll cover how to set modes in  different tutorial.
        #
        # This tutorial aims for maximum compatibility.
        #
        # There are various caveats for hardware accelerated blitting
        # that make it undesirable in a lot of cases, so we'll just use
        # software.
        self.display_info = pygame.display.Info()
        self.initial_resolution = (self.display_info.current_w,
                                   self.display_info.current_h)

        # Dump a bit more info about the configured mode.
        log.info(f'Display Driver: {pygame.display.get_driver()}')
        log.info(f'Display Info: {self.display_info}')
        log.info(f'Initial Resolution: {self.initial_resolution}')
        log.info(f"8-bit Modes: {pygame.display.list_modes(8)}")
        log.info(f"16-bit Modes: {pygame.display.list_modes(16)}")
        log.info(f"24-bit Modes: {pygame.display.list_modes(24)}")
        log.info(f"32-bit Modes: {pygame.display.list_modes(32)}")
        log.info(f"Best Color Depth: {pygame.display.mode_ok(self.initial_resolution), self.mode_flags} ({self.mode_flags})")
        log.info(f'Window Manager Info: {pygame.display.get_wm_info()}')
        log.info(f'Platform Timer Resolution: {pygame.TIMER_RESOLUTION}')

        # Cursor setup.
        # Cursor width/height must be a multiple of 8
        self.cursor = [
            "XX                      ",
            "XXX                     ",
            "XXXX                    ",
            "XX.XX                   ",
            "XX..XX                  ",
            "XX...XX                 ",
            "XX....XX                ",
            "XX.....XX               ",
            "XX......XX              ",
            "XX.......XX             ",
            "XX........XX            ",
            "XX........XXX           ",
            "XX......XXXXX           ",
            "XX.XXX..XX              ",
            "XXXX XX..XX             ",
            "XX   XX..XX             ",
            "     XX..XX             ",
            "      XX..XX            ",
            "      XX..XX            ",
            "       XXXX             ",
            "       XX               ",
            "                        ",
            "                        ",
            "                        "]

        self.cursor_width = len(self.cursor[0])
        self.cursor_height = len(self.cursor)
        self.cursor_data = None
        self.cursor_mask = None
        self.cursor_black = '.'
        self.cursor_white = 'X'
        self.cursor_xor = 'o'

        # Compile and set our cursor for drawing.
        self.update_cursor()

        # Set the screen update type.
        if self.update_type == 'update':
            self.display_update = pygame.display.update
        elif self.update_type == 'flip':
            self.display_update = pygame.display.flip
        else:
            log.error('Screen update type was neither "update" nor "flip".')

        # If a video driver was set, use it.
        if self.video_driver:
            os.environ['SDL_VIDEODRIVER'] = self.video_driver
        else:
            self.video_driver = os.environ.get('SDL_VIDEODRIVER', None)

        if self.video_driver:
            log.info(f'SDL_VIDEODRIVER == {os.environ["SDL_VIDEODRIVER"]}')

        # The Pygame documentation recommends against using hardware accelerated blitting.
        #
        # Note that you can also get the screen with pygame.display.get_surface()
        self.screen = pygame.display.set_mode(self.desired_resolution, self.mode_flags, self.color_depth)

        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()

    def update_cursor(self):
        # Compile our cursor so we can draw it to the screen.
        self.cursor_data, self.cursor_mask = pygame.cursors.compile(self.cursor,
                                                                    black=self.cursor_black,
                                                                    white=self.cursor_white,
                                                                    xor=self.cursor_xor)

        # Now set the cursor as the active cursor.
        pygame.mouse.set_cursor((self.cursor_width, self.cursor_height),
                                (0, 0),
                                self.cursor_data,
                                self.cursor_mask)

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Graphics Options')
        
        group.add_argument('-f', '--fps',
                           help='cap the framerate (default: infinite)',
                           type=float,
                           default=0.0)
        group.add_argument('--fps-refresh-rate',
                           help='how often to update the FPS counter in ms (default: 1000)',
                           default=1000)
        group.add_argument('-w', '--windowed',
                           help='run the program in windowed mode',
                           action='store_true',
                           default=True)
        group.add_argument('-r', '--resolution',
                           help='the resolution to use (default: 1024x768)',
                           default='640x480')
        group.add_argument('--use-gfxdraw',
                            action='store_true',
                            default=False)
        group.add_argument('--update-type',
                            help='update or flip (default: update)',
                            choices=['update', 'flip'],
                            default='update')


        # See https://www.pygame.org/docs/ref/display.html#pygame.display.set_mode
        windows_videodriver_choices = ['windib', 'directx']

        linux_videodriver_choices = ['x11',
                                     'dga',
                                     'fbcon',
                                     'directfb',
                                     'ggi',
                                     'vgl',
                                     'svgalib',
                                     'aalib']

        mac_videodriver_choices = []
        
        group.add_argument('--video-driver',
                           default=None,
                           choices=linux_videodriver_choices)

        # Init Font Options
        parser = FontManager.args(parser=parser)

        # Init Sound Options
        parser = SoundManager.args(parser=parser)

        # Init Music Options
        parser = MusicManager.args(parser=parser)

        return parser

    def start(self):
        log.info(f'Framerate check (configured FPS: {self.fps})')

        # On Some platforms, pygame.USEREVENT is used to convey codes
        # so, we'll use USEREVENT + 1 to avoid confusion.
        pygame.time.set_timer(GameEngine.FPSEVENT, self.fps_refresh_rate)

        self.active_scene = None

    def quit(self):
        # put a quit event in the event queue.
        pygame.event.post(
            pygame.event.Event(pygame.QUIT, {})
        )

    def load_resources(self):
        log.info('Implement load_resource() in your subclass.')

    def process_events(self):
        # To use events in a different thread, use the fastevent package from pygame.
        # You can create your own new events with the pygame.event.Event() function.
        for event in pygame.fastevent.get():
            if event.type == GameEngine.FPSEVENT:
                # FPSEVENT is pygame.USEREVENT + 1
                self.game_manager.on_fps_event(event)
            elif event.type == GameEngine.GAMEEVENT:
                # GAMEEVENT is pygame.USEREVENT + 2
                self.game_manager.on_game_event(event)
            elif event.type == pygame.MOUSEMOTION:
                # MOUSEMOTION      pos, rel, buttons
                self.mouse_manager.on_mouse_motion_event(event)
            elif event.type == pygame.MOUSEBUTTONUP:
                # MOUSEBUTTONUP    pos, button
                self.mouse_manager.on_mouse_button_up_event(event)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.mouse_manager.on_mouse_button_down_event(event)
                # MOUSEBUTTONDOWN  pos, button                            
            elif event.type == pygame.KEYDOWN:
                # KEYDOWN          unicode, key, mod
                self.keyboard_manager.on_key_down_event(event)
            elif event.type == pygame.KEYUP:
                # KEYUP            key, mod
                self.keyboard_manager.on_key_up_event(event)
            elif event.type == pygame.JOYAXISMOTION:
                 # JOYAXISMOTION    joy, axis, value
                self.joystick_manager.on_axis_motion_event(event)
            elif event.type == pygame.JOYBALLMOTION:
                # JOYBALLMOTION    joy, ball, rel
                self.joystick_.on_ball_motion_event(event)
            elif event.type == pygame.JOYHATMOTION:
                # JOYHATMOTION     joy, hat, value
                self.joystick_manager.on_hat_motion_event(event)
            elif event.type == pygame.JOYBUTTONUP:
                # JOYBUTTONUP      joy, button
                self.joystick_manager.on_button_up_event(event)
            elif event.type == pygame.JOYBUTTONDOWN:
                # JOYBUTTONDOWN    joy, button
                self.joystick_manager.on_button_down_event(event)
            elif event.type == pygame.USEREVENT:
                # USEREVENT        code
                self.game_manager.on_user_event(event)                                   
            elif event.type == pygame.QUIT:
                # QUIT             none
                self.game_manager.on_quit_event(event)
            elif event.type == pygame.ACTIVEEVENT:
                # ACTIVEEVENT      gain, state
                self.game_manager.on_active_event(event)
            elif event.type == pygame.VIDEORESIZE:
                # VIDEORESIZE      size, w, h
                self.game_manager.on_video_resize_event(event)
            elif event.type == pygame.VIDEOEXPOSE:
                # VIDEOEXPOSE      none                    
                self.game_manager.on_video_expose_event(event)
            elif event.type == pygame.SYSWMEVENT:
                # SYSWMEVENT
                self.game_manager.on_sys_wm_event(event)

    def register_game_event(self, event_type, callback):
        # This registers a subtype of type GAMEEVENT to call a callback.
        log.info(f'Registering event type "{event_type}" for {callback}')
        self.registered_events[event_type] = callback

    def post_game_event(self, event_subtype, event_data):
        event = event_data.copy()
        event['subtype'] = event_subtype
        pygame.event.post(
            pygame.event.Event(GameEngine.GAMEEVENT, event)
        )
        log.debug(f'Posted Event: {event}')

    def on_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button
        log.debug(f'MOUSEBUTTONUP: {event}')

        if event.button == 1:
            self.on_left_mouse_button_up_event(event)
        if event.button == 2:
            self.on_middle_mouse_button_up_event(event)
        if event.button == 3:
            self.on_right_mouse_button_up_event(event)
        if event.button == 4:
            # It doesn't really make sense to hook this
            pass
        if event.button == 5:
            # It doesn't really make sense to hook this
            pass

        self.active_scene.on_mouse_button_up_event(event)
            
    def on_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button
        log.debug(f'MOUSEBUTTONDOWN: {event}')        
        if event.button == 1:
            self.on_left_mouse_button_down_event(event)
        if event.button == 2:
            self.on_middle_mouse_button_down_event(event)
        if event.button == 3:
            self.on_right_mouse_button_down_event(event)
        if event.button == 4:
            self.on_mouse_scroll_down_event(event)
        if event.button == 5:
            self.on_mouse_scroll_up_event(event)

        self.active_scene.on_mouse_button_down_event(event)

    def on_fps_event(self, event):
        # FPSEVENT is pygame.USEREVENT + 1
        GameEngine.FPS = self.clock.get_fps()
        self.active_scene.on_fps_event(event)

    def on_game_event(self, event):
        # GAMEEVENT is pygame.USEREVENT + 2
        # Call the event callback if it's registered.
        try:
            self.registered_events[event.subtype](event)
        except KeyError:
            log.error(f'Unregistered Event: {event} (call self.register_game_event(<event subtype>, <event data>))')

    # If the game hasn't hooked a call, we should check if the scene manager has.
    #
    # This will allow scenes to get pygame events directly, but we can still
    # hook those events in this engine, or in the subclassed game object, too.
    #
    # This allows maximum flexibility of event processing, with low overhead
    # at the expense of a slight layer violation.
    def __getattr__(self, attr):

        # Attempt to proxy the call to the active scene.
        try:
            return getattr(self.active_scene)
        except AttributeError:
            # This will only happen if the game doesn't intercept the callback.
            raise AttributeError(f'{attr} is not implemented in {type(self)} or in {type(self.active_scene)}.')

class RootScene(object):
    def __init__(self):
        super().__init__()
        # This will resolve to the class name of any subclass.
        self.name = type(self)
        self.background_color = black
        self.next = self
        self.rects = None

        # This returns <class 'engine.RootScene'>
        self.root_scene = type(self).__mro__[-2]
        
        # http://n0nick.github.io/blog/2012/06/03/quick-dirty-using-pygames-dirtysprite-layered/
        self.all_sprites = pygame.sprite.LayeredDirty()

        # Initial screen state.
        self.screen = pygame.display.get_surface()
        self.background = pygame.Surface(self.screen.get_size())
        self.background.convert()
        self.background.fill(self.background_color)

        self.all_sprites.clear(self.screen, self.background)

    def update(self):
        self.rects = self.all_sprites.draw(self.screen)

    def render(self, screen):
        self.all_sprites.update()

    def switch_to_scene(self, next_scene):
        self.next = next_scene

    def terminate(self):
        self.switch_to_scene(None)

    def on_axis_motion_event(self, event):
        # JOYAXISMOTION    joy, axis, value
        log.debug(f'{self.root_scene}: {event}')

    def on_button_down_event(self, event):
        # JOYBUTTONDOWN    joy, button
        log.debug(f'{self.root_scene}: {event}')

    def on_button_up_event(self, event):
        # JOYBUTTONUP      joy, button
        log.debug(f'{self.root_scene}: {event}')

    def on_hat_motion_event(self, event):
        # JOYHATMOTION     joy, hat, value
        log.debug(f'{self.root_scene}: {event}')

    def on_ball_motion_event(self, event):
        # JOYBALLMOTION    joy, ball, rel
        log.debug(f'{type(self)}: {event}')

    def on_mouse_motion_event(self, event):
        # MOUSEMOTION      pos, rel, buttons
        log.debug(f'{self.root_scene}: {event}')        

    def on_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button
        log.debug(f'{self.root_scene}: {event}')

    def on_left_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button        
        log.debug(f'{self.root_scene}: Left Mouse Button Up Event: {event}')
        self.on_mouse_button_up_event(event)

    def on_middle_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button        
        log.debug(f'{self.root_scene}: Middle Mouse Button Up Event: {event}')

    def on_right_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button        
        log.debug(f'{self.root_scene}: Right Mouse Button Up Event: {event}')

    def on_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button
        log.debug(f'{self.root_scene}: {event}')

    def on_left_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button        
        log.debug(f'{self.root_scene}: Left Mouse Button Down Event: {event}')

    def on_middle_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button        
        log.debug(f'{self.root_scene}: Middle Mouse Button Down Event: {event}')

    def on_right_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button        
        log.debug(f'{self.root_scene}: Right Mouse Button Down Event: {event}')

    def on_mouse_scroll_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button        
        log.debug(f'{self.root_scene}: Mouse Scroll Down Event: {event}')

    def on_mouse_scroll_up_event(self, event):
        # MOUSEBUTTONDOWN  pos, button        
        log.debug(f'{self.root_scene}: Mouse Scroll Up Event: {event}')

    def on_mouse_chord_up_event(self, event): 
        log.debug(f'{self.root_scene}: Mouse Chord Up Event: {event}')

    def on_mouse_chord_down_event(self, event):
        log.debug(f'{self.root_scene}: Mouse Chord Down Event: {event}')

    def on_key_down_event(self, event):
        # KEYDOWN          unicode, key, mod
        log.debug(f'{self.root_scene}: {event}')        
    
    def on_key_up_event(self, event):
        # KEYUP            key, mod
        log.debug(f'{self.root_scene}: {event}')

    def on_key_chord_down_event(self, event, keys):
        log.debug(f'{self.root_scene}: {event}, {keys}')

    def on_key_chord_up_event(self, event, keys):
        log.debug(f'{self.root_scene} KEYCHORDUP: {event}, {keys}')            

    def on_quit_event(self, event):
        # QUIT             none
        log.debug(f'{self.root_scene}: {event}')
        self.terminate()

    def on_active_event(self, event):
        # ACTIVEEVENT      gain, state        
        log.debug(f'{self.root_scene}: {event}')

    def on_video_resize_event(self, event):
        # VIDEORESIZE      size, w, h        
        log.debug(f'{self.root_scene}: {event}')

    def on_video_expose_event(self, event):
        # VIDEOEXPOSE      none        
        log.debug(f'{self.root_scene}: {event}')        
        
    def on_sys_wm_event(self, event):
        # SYSWMEVENT        
        log.debug(f'{self.root_scene}: {event}')

    def on_user_event(self, event):
        # USEREVENT        code
        log.debug(f'{self.root_scene}: {event}')

    def on_fps_event(self, event):
        # FPSEVENT is pygame.USEREVENT + 1
        log.debug(f'{self.root_scene}: {GameEngine.FPS}')

    #def __getattr__(self, event):
    #    print(event)
        
    
