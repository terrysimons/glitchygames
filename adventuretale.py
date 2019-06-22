#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import copy
import logging
import time
import multiprocessing
import os
import subprocess
import re

from pygame import Color, Rect
import pygame
import pygame.freetype
import pygame.gfxdraw
import pygame.locals

log = logging.getLogger('game')
log.setLevel(logging.INFO)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

log.addHandler(ch)

# Note: I want to handle this a bit differently.
yellow = pygame.Color(128, 128, 0, 255)
purple = pygame.Color(121, 7, 242, 255)
blue = pygame.Color(0, 0, 255, 255)
green = pygame.Color(0, 255, 255)
white = pygame.Color(255, 255, 255, 255)
black = pygame.Color(0, 0, 0, 0)
blacklucent = pygame.Color(0, 0, 0, 127)
bluelucent = pygame.Color(0, 96, 255, 127)

class BaseEngine(object):
    def __init__(self, *args, **kwargs):
        self.ready = False

    @classmethod
    def args(cls, parser):
        return parser

    def start(self):
        pass

    def stop(self):
        pass

    def ready(self):
        return self.ready

    def quit(self):
        pass

class ResourceManager(object):
    def __init__(self, *args, **kwargs):
        super().__init__()

class FontManager(ResourceManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Music Options')

        return parser

class SoundManager(ResourceManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        class KeyboardProxy(object):
            def __init__(self):
                super().__init__()

            def on_key_down_event(self, event, game):
                game.on_key_down_event(event)

            def on_key_up_event(self, event, game):
                game.on_key_up_event(event)

            # This will allow calls to the keyboard which aren't implemented here.
            def __getattr__(self, attr):
                # TODO: If the attribute doesn't exist, throw an error.        
                return getattr(pygame.key, attr)        

        self.keyboard = KeyboardProxy()

    def key_down_event(self, event, game):
        # KEYDOWN          unicode, key, mod
        log.debug(f'KEYDOWN triggered: key_down_event(event, game)')
        self.keyboard.on_key_down_event(event)

    def key_up_event(self, event, game):
        # KEYUP            key, mod
        log.debug(f'KEYDOWN triggered: key_up_event(event, game)')        
        self.keyboard.on_key_up_event(event)

class MouseManager(ResourceManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        class MouseProxy(object):
            def __init__(self):
                super().__init__()

            def on_mouse_motion_event(self, event, game):
                game.on_mouse_motion_event(event)

            def on_mouse_button_up_event(self, event, game):
                game.on_mouse_button_up_event(event)

            def on_mouse_button_down_event(self, event, game):
                game.on_mouse_button_down_event(event)

            # This will allow calls to the mouse which aren't implemented here.
            def __getattr__(self, attr):
                # TODO: If the attribute doesn't exist, throw an error.
                return getattr(pygame.mouse, attr)    
        
        self.mouse = MouseProxy()

    def mouse_motion_event(self, event, game):
        # MOUSEMOTION      pos, rel, buttons
        log.debug(f'MOUSEMOTION triggered: mouse_motion_event({event})')        
        self.mouse.on_mouse_motion_event(event, game)
        
    def mouse_button_up_event(self, event, game):
        # MOUSEBUTTONUP    pos, button
        log.debug(f'MOUSEBUTTONUP triggered: mouse_button_up_event({event})')        
        self.mouse.on_mouse_button_up_event(event, game)
        
    def mouse_button_down_event(self, event, game):
        # MOUSEBUTTONDOWN  pos, button
        log.debug(f'MOUSEBUTTONDOWN triggered: mouse_button_down_event({event})')
        self.mouse.on_mouse_button_down_event(event, game)
    
class JoystickManager(ResourceManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.joysticks = []

        class JoystickProxy(object):
            """Some Joysticks are very slow reading certain attributes such as name, etc.  This fixes that.
            """
            def __init__(self, id):
                super().__init__()
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
            def on_axis_motion_event(self, event, game):
                # JOYAXISMOTION    joy, axis, value
                try:
                    self._axes[event.axis] = event.value
                    game.on_axis_motion_event(event)
                except AttributeError:
                    log.info(f'on_axis_motion_event(f{event})')
                    log.info(f'Axes: {self._axes}')            

            def on_button_down_event(self, event, game):
                # JOYBUTTONDOWN    joy, button                
                try:
                    self._buttons[event.button] = 1
                    game.on_button_down_event(event)
                except AttributeError:
                    log.info(f'on_button_down_event(f{event})')
                    log.info(f'Buttons: {self._buttons}')            

            def on_button_up_event(self, event, game):
                # JOYBUTTONUP      joy, button
                try:
                    self._buttons[event.button] = 0
                    game.on_button_up_event(event)
                except AttributeError:
                    log.info(f'on_button_up_event(f{event})')
                    log.info(f'Buttons: {self._buttons}')
            
            def on_hat_motion_event(self, event, game):
                # JOYHATMOTION     joy, hat, value
                try:
                    self._hats[event.hat] = event.value
                    game.on_hat_motion_event(event)
                except AttributeError:
                    log.info(f'on_hat_motion_event(f{event})')
                    log.info(f'Hats: {self._hats}')

            def on_ball_motion_event(self, event, game):
                # JOYBALLMOTION    joy, ball, rel
                try:
                    self._balls[event.ball] = rel
                    game.on_ball_motion_event(event)
                except AttributeError:
                    log.info(f'on_ball_motion_event(f{event})')
                    log.info(f'Balls: {self._balls}')

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

            # This will allow calls to the joystick which aren't implemented here.
            def __getattr__(self, attr):
                # TODO: If the attribute doesn't exist, throw an error.                
                return getattr(self.joystick, attr)

        # This must be called before other joystick methods,
        # and is safe to call more than once.
        pygame.joystick.init()
        
        log.info(f'Joystick Module Inited: {pygame.joystick.get_init()}')

        # Joystick Setup
        log.info(f'Joystick Count: {pygame.joystick.get_count()}')
        joysticks = [pygame.joystick.Joystick(x) for x in range(pygame.joystick.get_count())]

        for i, joystick in enumerate(joysticks):
            joystick.init()
            joystick_proxy = JoystickProxy(id=joystick.get_id())
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
    def axis_motion_event(self, event, game):
        # JOYAXISMOTION    joy, axis, value        
        log.debug(f'JOYAXISMOTION triggered: axis_motion_event({event})')
        self.joysticks[event.joy].on_axis_motion_event(event, game)

    def button_down_event(self, event, game):
        # JOYBUTTONDOWN    joy, button
        log.debug(f'JOYBUTTONDOWN triggered: button_down_event({event})')
        self.joysticks[event.joy].on_button_down_event(event, game)
        
    def button_up_event(self, event, game):
        # JOYBUTTONUP      joy, button
        log.debug(f'JOYBUTTONUP triggered: button_up_event({event})')
        self.joysticks[event.joy].on_button_up_event(event, game)        

    def hat_motion_event(self, event, game):
        # JOYHATMOTION     joy, hat, value
        log.debug(f'JOYHATMOTION triggered: hat_motion_event({event})')
        self.joysticks[event.joy].on_hat_motion_event(event, game)        

    def ball_motion_event(self, event, game):
        # JOYBALLMOTION    joy, ball, rel
        log.debug(f'JOYBALLMOTION triggered: ball_motion_event({event})')
        self.joysticks[event.joy].on_ball_motion_event(event, game)

class InputManager(ResourceManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.joystick_manager = JoystickManager(**kwargs)
        self.keyboard_manager = KeyboardManager(**kwargs)
        self.mouse_manager = MouseManager(**kwargs)

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Sound Mixer Options')

        return parser

    
class GameManager(ResourceManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        class GameProxy(object):
            def __init__(self, *args, **kwargs):
                super().__init__()

            def on_quit_event(self, event, game):
                # QUIT             none
                try:
                    game.on_quit_event(event)
                except AttributeError:
                    log.debug(f'QUIT: {event}')

            def on_active_event(self, event, game):
                # Note: Split these out into on_activated_event(), on_deactivated_event()
                # ACTIVEEVENT      gain, state
                try:
                    game.on_active_event(event)
                except AttributeError:
                    log.debug(f'ACTIVEEVENT: {event}')

            def on_video_resize_event(self, event, game):
                # VIDEORESIZE      size, w, h                
                try:
                    game.on_video_resize_event(event)
                except AttributeError:
                    log.debug(f'VIDEORESIZE: {event}')

            def on_video_expose_event(self, event, game):
                # VIDEOEXPOSE      none
                try:
                    game.on_video_expose_event(event)
                except AttributeError:
                    log.debug(f'VIDEOEXPOSE: {event}')

            def on_sys_wm_event(self, event, game):
                # SYSWMEVENT
                try:
                    game.on_sys_wm_event(event)
                except AttributeError:
                    log.debug(f'SYSWMEVENT: {event}')                

            def on_user_event(self, event, game):
                # USEREVENT        code
                try:
                    game.on_user_event(event)
                except AttributeError:
                    log.debug(f'USEREVENT: {event}')                

            def on_game_event(self, event, game):
                # This is a special non-pygame event type.        
                try:
                    game.on_game_event(event)
                except AttributeError:
                    log.debug(f'Game Event: {event}')

            def on_fps_event(self, event, game):
                # This is a special non-pygame event type.        
                try:
                    game.on_fps_event(event)
                except AttributeError:
                    log.debug(f'FPS Event: {event}')

            # This will allow calls to pygame which aren't implemented here.
            def __getattr__(self, attr):
                # TODO: If the attribute doesn't exist, throw an error.        
                return getattr(pygame, attr)    
        
        self.game = GameProxy()

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Game Options')

        return parser

    def quit_event(self, event, game):
        # QUIT             none
        log.debug(f'QUIT triggered: quit_event({event})')
        self.game.on_quit_event(event, game)

    def active_event(self, event, game):
        # ACTIVEEVENT      gain, state
        log.debug(f'ACTIVEEVENT triggered: active_event({event})')
        self.game.on_active_event(event, game)

    def video_resize_event(self, event, game):
        # VIDEORESIZE      size, w, h
        log.debug(f'VIDEORESIZE triggered: video_resize_event({event})')
        game.on_video_resize_event(event, game)

    def video_expose_event(self, event, game):
        # VIDEOEXPOSE      none
        log.debug(f'VIDEOEXPOSE triggered: video_expose_event({event})')        
        game.on_video_expose_event(event, game)

    def sys_wm_event(self, event, game):
        # SYSWMEVENT
        log.debug(f'SYSWMEVENT triggered: sys_wm_event({event})')
        self.game.on_sys_wm_event(event, game)

    def user_event(self, event, game):
        # USEREVENT        code
        log.debug(f'USEREVENT triggered: user_event({event})')
        self.game.on_user_event(event, game)
        
    def fps_event(self, event, game):
        # This is a special non-pygame event type.
        log.debug(f'FPSEVENT triggered: fps_event({event})')
        self.game.on_fps_event(event, game)

    def game_event(self, event, game):
        # This is a special non-pygame event type.
        log.debug(f'GAMEEVENT triggered: game_event({event})')
        self.game.on_game_event(event, game)
        

class GameEngine(BaseEngine):
    NAME = "Boilerplate Adventures"
    VERSION = "1.0"
    FPSEVENT = pygame.USEREVENT + 1
    GAMEEVENT = pygame.USEREVENT + 2
    FPS = 0
    
    def __init__(self, options=None):
        # General stuff.
        self.cpu_count = multiprocessing.cpu_count()

        # Pygame stuff.
        pygame.register_quit(self.quit)
        self.fps = options.get('fps', 0)
        self.update_type = options.get('update_type')
        self.use_gfxdraw = options.get('use_gfxdraw')
        self.video_driver = options.get('video_driver')
        self.windowed = options.get('windowed')
        self.desired_resolution = options.get('resolution')

        log.info(f'Game Title: {type(self).NAME}')
        log.info(f'Game Version: {type(self).VERSION}')

        # Initialize all of the Pygame modules.
        self.init_pass, self.init_fail = pygame.init()
        log.debug(f'Successfully loaded {self.init_pass} modules and failed loading {self.init_fail} modules.')

        # Enable fast events for multithreaded applications
        pygame.fastevent.init()

        self.font_manager = FontManager(**options)
        self.sound_manager = SoundManager(**options)
        self.music_manager = MusicManager(**options)
        self.input_manager = InputManager(**options)
        self.joystick_manager = self.input_manager.joystick_manager
        self.keyboard_manager = self.input_manager.keyboard_manager
        self.mouse_manager = self.input_manager.mouse_manager
        self.game_manager = GameManager(**options)
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
        pygame.display.set_caption(f'{type(self).NAME} (title)',
                                   f'{type(self).NAME} (icontitle)')


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
        group.add_argument('-w', '--windowed',
                           help='run the program in windowed mode',
                           action='store_true')
        group.add_argument('-r', '--resolution',
                           help='the resolution to use (default: 1024x768)',
                           default='1024x768')
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
        # The Pygame documentation recommends against using hardware accelerated blitting.
        #
        # Note that you can also get the screen with pygame.display.get_surface()
        self.screen = pygame.display.set_mode(self.desired_resolution, self.mode_flags, self.color_depth)

        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()
    
    def quit(self):
        pass

    def process_events(self):
        # To use events in a different thread, use the fastevent package from pygame.
        # You can create your own new events with the pygame.event.Event() function.
        for event in pygame.fastevent.get():
            if event.type == pygame.QUIT:
                # QUIT             none
                self.game_manager.quit_event(event, self)
            elif event.type == pygame.ACTIVEEVENT:
                # ACTIVEEVENT      gain, state
                self.game_manager.active_event(event, self)
            elif event.type == pygame.KEYDOWN:
                # KEYDOWN          unicode, key, mod
                self.keyboard_manager.key_down_event(event, self)
            elif event.type == pygame.KEYUP:
                # KEYUP            key, mod
                self.keyboard_manager.key_up_event(event, self)
            elif event.type == pygame.MOUSEMOTION:
                # MOUSEMOTION      pos, rel, buttons
                self.mouse_manager.mouse_motion_event(event, self)
            elif event.type == pygame.MOUSEBUTTONUP:
                # MOUSEBUTTONUP    pos, button
                self.mouse_manager.mouse_button_up_event(event, self)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.mouse_manager.mouse_button_down_event(event, self)
                # MOUSEBUTTONDOWN  pos, button                    
            elif event.type == pygame.JOYAXISMOTION:
                # JOYAXISMOTION    joy, axis, value
                self.joystick_manager.axis_motion_event(event, self)
            elif event.type == pygame.JOYBALLMOTION:
                # JOYBALLMOTION    joy, ball, rel
                self.joystick_.ball_motion_event(event, self)
            elif event.type == pygame.JOYHATMOTION:
                # JOYHATMOTION     joy, hat, value
                self.joystick_manager.hat_motion_event(event, self)
            elif event.type == pygame.JOYBUTTONUP:
                # JOYBUTTONUP      joy, button
                self.joystick_manager.button_up_event(event, self)
            elif event.type == pygame.JOYBUTTONDOWN:
                # JOYBUTTONDOWN    joy, button
                self.joystick_manager.button_down_event(event, self)
            elif event.type == pygame.VIDEORESIZE:
                # VIDEORESIZE      size, w, h
                self.game_manager.video_resize_event(event, self)
            elif event.type == pygame.VIDEOEXPOSE:
                # VIDEOEXPOSE      none                    
                self.game_manager.video_expose_event(event, self)
            elif event.type == pygame.SYSWMEVENT:
                # SYSWMEVENT
                self.game_manager.sys_wm_event(event, self)
            elif event.type == pygame.USEREVENT:
                # USEREVENT        code
                self.game_manager.user_event(event, self)                   
            elif event.type == GameEngine.FPSEVENT:
                # FPSEVENT is pygame.USEREVENT + 1
                self.game_manager.fps_event(event, self)
            elif event.type == GameEngine.GAMEEVENT:
                # GAMEEVENT is pygame.USEREVENT + 2
                self.game_manager.game_event(event, self)

    def register_game_event(self, event_type, callback):
        # This registers a subtype of type GAMEEVENT to call a callback.
        log.info(f'Registering event type "{event_type}" for {callback}')
        self.registered_events[event_type] = callback

    def post_game_event(self, event_type, event_data):
        event = event_data.copy()
        event['type'] = event_type
        pygame.event.post(
            pygame.event.Event(GameEngine.GAMEEVENT, event)
        )        

    # Hook up the input callbacks.
    def on_axis_motion_event(self, event):
        # JOYAXISMOTION    joy, axis, value
        log.info(f'JOYAXISMOTION: {event}')
        
    def on_button_down_event(self, event):
        # JOYBUTTONDOWN    joy, button
        log.info(f'JOYBUTTONDOWN: {event}')

    def on_button_up_event(self, event):
        # JOYBUTTONUP      joy, button
        log.info(f'JOYBUTTONUP: {event}')
        
    def on_hat_motion_event(self, event):
        # JOYHATMOTION     joy, hat, value
        log.info(f'JOYHATMOTION: {event}')

    def on_ball_motion_event(self, event):
        # JOYBALLMOTION    joy, ball, rel
        log.info(f'JOYBALLMOTION: {event}')

    def on_mouse_motion_event(self, event):
        # MOUSEMOTION      pos, rel, buttons        
        log.info(f'MOUSEMOTION: {event}')

    def on_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button
        log.info(f'MOUSEBUTTONUP: {event}')

    def on_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN    pos, button
        log.info('MOUSEBUTTONDOWN: {event}')

    def on_key_down_event(self, event):
        # KEYDOWN          unicode, key, mod
        log.info(f'KEYDOWN: {event}')

    def on_key_up_event(self, event):
        # KEYUP            key, mod
        log.info(f'KEYUP: {event}')

    def on_quit_event(self, event):
        self.done = True        

    def on_active_event(self, event):
        # ACTIVEEVENT      gain, state        
        log.info(f'ACTIVEEVENT: {event}')

    def on_video_resize_event(self, event):
        # VIDEORESIZE      size, w, h        
        log.debug(f'VIDEORESIZE: {event}')

    def on_video_expose_event(self, event):
        # VIDEOEXPOSE      none        
        log.debug(f'VIDEOEXPOSE: {event}')        

    def on_sys_wm_event(self, event):
        # SYSWMEVENT        
        log.debug(f'SYSWMEVENT: {event}')        

    def on_user_event(self, event):
        # USEREVENT        code
        log.debug(f'USEREVENT: {event}')        

    def on_fps_event(self, event):
        # FPSEVENT is pygame.USEREVENT + 1        
        log.debug(f'FPSEVENT: {event}')        
        log.info(f'FPS: {GameEngine.FPS}')

    def on_game_event(self, event):
        # GAMEEVENT is pygame.USEREVENT + 2
        log.info(f'GAMEEVENT: {event}')

        # Call the event callback if it's registered.
        try:
            self.registered_events[event.type](event)
        except AttributeError:
            pass

    
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
    def __init__(self, background_color=blacklucent, alpha=0):
        super().__init__()
        self.background_color = background_color
        self.alpha = alpha
        
        # Quick and dirty, for now.
        self.screen = pygame.Surface((400, 400))

        if not alpha:
            self.screen.set_colorkey(self.background_color)
            #self.screen.convert()
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
            #self.screen.convert_alpha()
            self.screen.set_alpha(self.alpha)

        self.image = self.screen
        self.rect = self.image.get_rect()
        self.font_manager = FontManager()
        self.joystick_manager = JoystickManager()
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

            def print(self, screen, string):
                (self.image, self.rect) = self.font.render(string, white)
                self.image
                screen.blit(self.image, (self.x, self.y))
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
        self.screen.fill(self.background_color)

        self.text_box.reset()
        self.text_box.print(self.screen, f'{Game.NAME} version {Game.VERSION}')

        self.text_box.print(self.screen, f'CPUs: {multiprocessing.cpu_count()}')
        
        self.text_box.print(self.screen, f'FPS: {Game.FPS}')

        self.text_box.print(self.screen, "Number of joysticks: {}".format(self.joystick_count) )        
        if self.joystick_count:
            for i, joystick in enumerate(self.joystick_manager.joysticks):
                self.text_box.print(self.screen, f'Joystick {i}')
                
                # Get the name from the OS for the controller/joystick
                self.text_box.indent()
                self.text_box.print(self.screen, f'Joystick name: {joystick.get_name()}')
        
                # Usually axis run in pairs, up/down for one, and left/right for
                # the other.
                axes = joystick.get_numaxes()
                self.text_box.print(self.screen, f'Number of axes: {axes}')
                
                self.text_box.indent()                
                for i in range(axes):
                    self.text_box.print(self.screen, 'Axis {} value: {:>6.3f}'.format(i, joystick.get_axis(i)))
                self.text_box.unindent()

                buttons = joystick.get_numbuttons()
                self.text_box.print(self.screen, f'Number of buttons: {joystick.get_numbuttons()}')
                
                self.text_box.indent()
                for i in range(buttons):
                    self.text_box.print(self.screen, 'Button {:>2} value: {}'.format(i, joystick.get_button(i)))
                self.text_box.unindent()
            
                # Hat switch. All or nothing for direction, not like joysticks.
                # Value comes back in an array.
                hats = 0
                self.text_box.print(self.screen, f'Number of hats: {hats}')
                
                self.text_box.indent()
                for i in range(hats):
                    self.text_box.print(self.screen, f'Hat {hat} value: {str(joystick.get_hat(i))}')
                    self.text_box.unindent()
                self.text_box.unindent()

        #self.text_box.print(self.screen, f'Remaining time: {remaining_time // 1000}')
        
    
class Game(GameEngine):
    # Set your game name/version here.
    NAME = "Adventure Tale"
    VERSION = "0.0"
    
    def __init__(self, options):
        super().__init__(options=options)

        self.done = False
        
        self.time = options.get('time')
        # TODO:
        # Write an FPS layer that uses time.ns_time()
        
        # Hook up pygame.display.get_active()
        # ACTIVEEVENT on the eventqueue

        # Hook up pygame.display.toggle_fullscreen()
        # Only available on X11
        # Setting a new displaymode will also allow this behavior on other OSes.
        
        # https://www.pygame.org/docs/ref/display.html#pygame.display.set_mode
        #
        # (0, 0), 0, 0 is the recommended setting for auto-configure.
        if self.windowed:
            self.mode_flags = 0
        else:
            self.mode_flags = pygame.FULLSCREEN 
            self.screen_width = 0
            self.screen_height = 0
        self.color_depth = 0


        # Uncomment to easily block a class of events, if you
        # don't want them to be processed by the event queue.
        #
        # pygame.event.set_blocked(self.mouse_events)
        # pygame.event.set_blocked(self.joystick_events)
        # pygame.event.set_blocked(self.keyboard_events)

        # Let's hook up the 'pew pew' event.
        self.register_game_event('pew pew', self.on_pew_pew_event)

    def update_cursor(self):
        # For giggles, we can draw two cursors.
        # This can cause extra flicker on the cursor.
        # 
        # We need to re-configure the various cursor attributes once we do this.
        self.cursor = [cursor_row * 2 for cursor_row in self.cursor]
        self.cursor_width = len(self.cursor[0])
        self.cursor_height = len(self.cursor)
        
        log.info(f'Custom cursor width: {self.cursor_width}, height: {self.cursor_height}')
        
        # Now call the GameEngine update_cursor method to compile and set the cursor.
        super().update_cursor()

    @classmethod
    def args(cls, parser):
        # Initialize the game engine's options first.
        # This ensures that our game's specific options
        # are listed last.
        parser = GameEngine.args(parser)

        group = parser.add_argument_group('Game Options')
        
        group.add_argument('--time',
                           type=int,
                           default=10)
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
        super().start()
        
        # Run framerate checks for 3 seconds.
        log.info(f'Framerate check (configured FPS: {self.fps})')
        
        # On Some platforms, pygame.USEREVENT is used to convey codes
        # so, we'll use USEREVENT + 1 to avoid confusion.
        pygame.time.set_timer(GameEngine.FPSEVENT, 1000)
        
        # run logic here
        clock = pygame.time.Clock()
        start_time = pygame.time.get_ticks()
        run_time = self.time * 1000

        # Initial screen state.
        self.background = pygame.Surface(self.screen.get_size())
        self.background.convert()
        self.background.fill(black)

        # http://n0nick.github.io/blog/2012/06/03/quick-dirty-using-pygames-dirtysprite-layered/
        self.shapes_sprite = ShapesSprite()
        self.text_sprite = TextSprite(background_color=blacklucent, alpha=0)
        
        self.all_sprites = pygame.sprite.LayeredDirty((self.shapes_sprite, self.text_sprite))

        self.all_sprites.clear(self.screen, self.background)

        # TODO:
        # https://web.archive.org/web/20150206045655/http://gafferongames.com/game-physics/fix-your-timestep/        
        while not self.done:
            elapsed_time = pygame.time.get_ticks() - start_time
            remaining_time = run_time - elapsed_time

            # Use tick_busy_loop if you want an accurate timer, and don't mind chewing CPU.
            # Better platform support, and better accuracy
            # at the expense of CPU.
            #
            # Only call once per frame.
            clock.tick(self.fps)
            GameEngine.FPS = clock.get_fps()

            rects = self.all_sprites.draw(self.screen)

            self.process_events()

            if remaining_time <= 0:
                break

            self.all_sprites.update()

            rects = self.all_sprites.draw(self.screen)
            pygame.display.update(rects)

        # sound = pygame.mixer.Sound(file='demo.wav')

        # sound.play()

        log.info(f'FPS: {GameEngine.FPS}')

    def quit(self):
        log.info('Quit was called.')
        
        # Call the GameEngine quit, so it will clean up.
        super().quit()

    def on_mouse_motion_event(self, event):
        # MOUSEMOTION      pos, rel, buttons
        self.shapes_sprite.move(event.pos)

    def on_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button
        self.post_game_event('pew pew', {})

    def on_key_up_event(self, event):
        # KEYUP            key, mod
        if event.key == pygame.K_q:
            log.info(f'User requested quit.')                        
            event = pygame.event.Event(pygame.QUIT, {})
            pygame.event.post(event)

    def on_game_event(self, event):
        # GAMEEVENT is pygame.USEREVENT + 2
        log.info(f'GAMEEVENT: {event}')
        if event.type == 'pew pew':
            self.on_pew_pew_event(event)

    def on_pew_pew_event(self, event):
        log.info(f'PEW PEW Event: {event}')
        
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


