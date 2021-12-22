#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contains GameEngine and helper classes for building a game."""
import logging
import multiprocessing
import platform
import re

import pygame
import pygame.freetype
import pygame.gfxdraw
import pygame.locals

# Backwards compatibility
#
# TODO: Refactor code to use classes directly
from ghettogames.events import KeyboardEvents
from ghettogames.events import MouseEvents
from ghettogames.events import JoystickEvents
from ghettogames.mouse import MousePointer
from ghettogames.sprites import BitmappySprite
from ghettogames.sprites import RootSprite
from ghettogames.scenes import RootScene
from ghettogames.sprites import RootRootSprite
from ghettogames.sprites import SingletonBitmappySprite
##########################

from ghettogames.color import PURPLE, BLACK, VGA
from ghettogames.pixels import *
from ghettogames.events import ResourceManager, EventManager

from ghettogames.audio import AudioManager
# from ghettogames.controllers import ControllerManager
from ghettogames.fonts import FontManager
from ghettogames.joysticks import JoystickManager
from ghettogames.keyboard import KeyboardManager
from ghettogames.midi import MidiManager
from ghettogames.mouse import MouseManager


log = logging.getLogger('game.engine')
log.addHandler(logging.NullHandler())

logging.basicConfig(format='%(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)

vga_palette = VGA

class GameManager(ResourceManager):
    class GameProxy(ResourceManager):
        def __init__(self, **kwargs):
            """
            Game event proxy.

            GameProxy facilitates custom and otherwise unhandled pygame
            events between pygame and your game.

            Args:
            ----
            joystick_id - the id of the joystick to init
            game - The game instance.

            """
            super().__init__(**kwargs)
            self.game = kwargs.get('game')
            self.proxies = [self.game]

        def on_active_event(self, event):
            self.game.on_active_event(event)

    def __init__(self, game=None):
        """
        Game event manager.

        GameManager interfaces GameEngine with miscellaneous pygame events.

        Args:
        ----
        game - The game instance.

        """
        super().__init__(game=game)
        self.proxies = [GameManager.GameProxy(game=game)]

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Game Options')  # noqa: W0612

        return parser

def supported_events(like='.*'):
    # Get a list of all of the events
    # by name, but ignore duplicates.
    event_names = [*set(pygame.event.event_name(event_num)
                        for event_num in range(0, pygame.NUMEVENTS))]
    event_names = set(event_names) - set('Unknown')
    event_list = []

    for event_name in list(event_names):
        try:
            if re.match(like, event_name.upper()):
                event_list.append(getattr(pygame, event_name.upper()))
                log.info(event_name.upper())
        except AttributeError as e:
            log.error(f'Failed to init: {e}')

    return event_list
class GameEngine(EventManager):
    NAME = "Boilerplate Adventures"
    VERSION = "1.0"
    FPS = 0
    OPTIONS = None

    FPSEVENT = pygame.USEREVENT + 1
    GAMEEVENT = pygame.USEREVENT + 2
    MENUEVENT = pygame.USEREVENT + 3

    AUDIO_EVENTS = supported_events(like='AUDIO.*?')
    # TODO: CONTROLLER_EVENTS = supported_events(like='CONTROLLER.*?')
    DROP_EVENTS = supported_events(like='DROP.*?')
    FINGER_EVENTS = supported_events(like='(FINGER|MULTI).*?')
    JOYSTICK_EVENTS = supported_events(like='JOY.*?')
    KEYBOARD_EVENTS = supported_events(like='KEY.*?')
    MIDI_EVENTS = supported_events(like='MIDI.*?')
    MOUSE_EVENTS = supported_events(like='MOUSE.*?')
    TEXT_EVENTS = supported_events(like='TEXT.*?')
    WINDOW_EVENTS = supported_events(like='WINDOW.*?')
    ALL_EVENTS = supported_events()
    GAME_EVENTS = list(set(ALL_EVENTS) -
                       set(AUDIO_EVENTS) -
                       set(DROP_EVENTS) -
                       set(FINGER_EVENTS) -
                       set(JOYSTICK_EVENTS) - 
                       set(KEYBOARD_EVENTS) -
                       set(MIDI_EVENTS) -
                       set(MOUSE_EVENTS) -
                       set(TEXT_EVENTS) -
                       set(WINDOW_EVENTS))

    GAME_EVENTS.append(FPSEVENT)
    GAME_EVENTS.append(GAMEEVENT)
    GAME_EVENTS.append(MENUEVENT)

    def __init__(self, game=None, options=None):
        """
        Set up pygame and handle events.

        Your game should subclass this class.

        Args:
        ----
        game - None, since it *is* the game.
        options - the configuration options passed via the command line.

        """
        # Persist this game's options.
        GameEngine.OPTIONS = options

        super().__init__(game=self)

        self._active_scene = None

        # Pygame stuff.
        pygame.register_quit(self.quit)
        self.fps = options.get('fps', 0)
        self.update_type = options.get('update_type')
        self.use_gfxdraw = options.get('use_gfxdraw')
        self.windowed = options.get('windowed')
        self.desired_resolution = options.get('resolution')
        self.fps_refresh_rate = options.get('fps_refresh_rate')

        # Initialize all of the Pygame modules.
        self.init_pass, self.init_fail = pygame.init()
        self.print_game_info()

        # Enable fast events for multithreaded applications
        pygame.fastevent.init()

        self.clock = pygame.time.Clock()

        self.registered_events = {}
        self.audio_manager = AudioManager(self)
        # TODO: self.controller_manager = ControllerManager(self)
        # TODO: self.finger_manager = FingerManager(self)
        self.font_manager = FontManager(self)
        self.game_manager = GameManager(self)
        self.joystick_manager = JoystickManager(self)
        self.keyboard_manager = KeyboardManager(self)
        self.midi_manager = MidiManager(self)
        self.mouse_manager = MouseManager(self)
        # TODO: self.window_manager = WindowManager(self)

        # TODO: Something similar for controllers?
        # self.controllers = []
        # if self.controller_manager:
        #     self.controllers = self.controller_manager.controllers
        # self.controller_count = len(self.controllers)

        # Get count of joysticks
        self.joysticks = []
        if self.joystick_manager:
            self.joysticks = self.joystick_manager.joysticks
        self.joystick_count = len(self.joysticks)

        # Resolution initialization.
        # Convert our resolution to a tuple
        (desired_width, desired_height) = self.desired_resolution.split('x')

        if self.windowed:
            self.mode_flags = 0
        else:
            self.mode_flags = pygame.FULLSCREEN

        self.desired_resolution = self.suggested_resolution(desired_width, desired_height)

        # window icon and system tray/dock icon
        self.initialize_system_icons()

        # Let's try to set a resolution to the most compatible for
        # the system.  If we don't provide any parameters, we'll get
        # a reasonble default, but you should consider whether that's
        # a good idea for your particular application.
        #
        # There are various caveats for hardware accelerated blitting
        # that make it undesirable in a lot of cases, so we'll just use
        # software.
        self.display_info = pygame.display.Info()
        self.initial_resolution = (self.display_info.current_w,
                                   self.display_info.current_h)

        self.cursor = self.set_cursor(cursor=None)

        # Set the screen update type.
        if self.update_type == 'update':
            self.display_update = pygame.display.update
        elif self.update_type == 'flip':
            self.display_update = pygame.display.flip
        else:
            log.error('Screen update type was neither "update" nor "flip".')

        # The Pygame documentation recommends against using hardware accelerated blitting.
        #
        # Note that you can also get the screen with pygame.display.get_surface()
        self.screen = pygame.display.set_mode(self.desired_resolution,
                                              self.mode_flags)

        self.print_system_info()

    def __del__(self):
        # This is the total # of sprites.
        log.info(f'Sprite Count: {RootSprite.SPRITE_COUNT}')

        # This is a count of each type of sprite.
        for sprite_type, counters in RootSprite.SPRITE_COUNTERS.items():
            #sprite_count = RootSprite.SPRITE_COUNTERS[sprite_type][key]            
            for key, value in counters.items():
                log.info(f'{sprite_type} Sprite {key}: {value}')
    @property
    def screen_width(self):
        return self.screen.get_width()

    @property
    def screen_height(self):
        return self.screen.get_height()

    def print_system_info(self):
        # General Info
        log.info(f'CPU Count: {multiprocessing.cpu_count()}')
        log.info(f'System: {platform.system()}')
        log.info(f'Machine: {platform.machine()}')
        log.info(f'Platform: {platform.platform()}')
        log.info(f'Platform (Terse): {platform.platform(aliased=0, terse=1)}')
        log.info(f'Processor: {platform.processor()}')
        log.info(f'Release: {platform.release()}')

        # Set up a display mode.
        # Note: pygame.display.init() isn't necessary here
        # because we've already called pygame.init() which
        # initializes all available modules.
        #
        # Let's do a sanity check and make sure we're initialized.
        log.info(f'Display inited: {pygame.display.get_init()}')

        # Display some configuration information.
        log.info(f'SDL Version: {pygame.get_sdl_version()}')
        log.info(f'SDL Byte Order: {pygame.get_sdl_byteorder()}')

        # Dump a bit more info about the configured mode.
        log.info('Display Driver: '
                 f'{pygame.display.get_driver()}')
        log.info('Display Info: '
                 f'{self.display_info}')
        log.info('Initial Resolution: '
                 f'{self.initial_resolution}')
        log.info('8-bit Modes: '
                 f'{pygame.display.list_modes(8)}')
        log.info('16-bit Modes: '
                 f'{pygame.display.list_modes(16)}')
        log.info('24-bit Modes: '
                 f'{pygame.display.list_modes(24)}')
        log.info('32-bit Modes: '
                 f'{pygame.display.list_modes(32)}')
        log.info('Best Color Depth: '
                 f'{pygame.display.mode_ok(self.initial_resolution), self.mode_flags}'
                 f' ({self.mode_flags})')
        log.info('Window Manager Info: '
                 f'{pygame.display.get_wm_info()}')
        log.info('Platform Timer Resolution: '
                 f'{pygame.TIMER_RESOLUTION}')

    def print_game_info(self):
        log.debug(f'Successfully loaded {self.init_pass} modules '
                  f'and failed loading {self.init_fail} modules.')

        log.info('Game Title: '
                 f'{type(self).NAME}')
        log.info('Game Version: '
                 f'{type(self).VERSION}')

    def suggested_resolution(self, desired_width=0, desired_height=0):  # noqa: R0201
        # For Ubuntu 19.04, we can't reset the original res
        # so let's just let the system figure it out.
        if platform.system() == 'Linux':
            if 'arm' not in platform.machine():
                log.info('Ignoring full screen resolution change on Linux.')
            else:
                # RPi Hack
                #
                # The Raspberry Pi screen exposes
                # 2 resolutions, but only one works properly
                desired_width = 800
                desired_height = 480

        return (int(desired_width), int(desired_height))

    def set_cursor(self, cursor=None, cursor_black='.', cursor_white='X', cursor_xor='o'):  # noqa R0201
        if not cursor:
            # Cursor setup.
            # Cursor width/height must be a multiple of 8
            cursor = [
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

        cursor_width = len(cursor[0])
        cursor_height = len(cursor)

        # cursor = cursor

        # Compile our cursor so we can draw it to the screen.
        cursor_data, cursor_mask = pygame.cursors.compile(cursor,
                                                          black=cursor_black,
                                                          white=cursor_white,
                                                          xor=cursor_xor)

        # Now set the cursor as the active cursor.
        pygame.mouse.set_cursor((cursor_width, cursor_height),
                                (0, 0),
                                cursor_data,
                                cursor_mask)

        return cursor

    def initialize_system_icons(self):
        # Set the window icon.
        #
        # Always call this before you call set_mode()
        icon = pygame.Surface((32, 32))
        icon.fill(PURPLE)
        pygame.display.set_icon(icon)

        # Set the display caption.
        pygame.display.set_caption(f'{type(self).NAME}',
                                   f'{type(self).NAME}')

        # Get captions:
        (title, icontitle) = pygame.display.get_caption()
        log.info(f'Window Title: {title}')
        log.info(f'Icon Title: {icontitle}')

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
                           default='800x480')
        group.add_argument('--use-gfxdraw',
                           action='store_true',
                           default=False)
        group.add_argument('--update-type',
                           help='update or flip (default: update)',
                           choices=['update', 'flip'],
                           default='update')

        # See https://www.pygame.org/docs/ref/display.html#pygame.display.set_mode
        default_videodriver = []
        if platform.system() == 'Linux':
            linux_videodriver_choices = ['x11',
                                         'dga',
                                         'fbcon',
                                         'directfb',
                                         'ggi',
                                         'vgl',
                                         'svgalib',
                                         'aalib']

            log.debug(f'Linux Video Driver Choices: {linux_videodriver_choices}')

            default_videodriver = linux_videodriver_choices

        elif platform.system() == 'MacOS':
            mac_videodriver_choices = []

            log.debug(f'Mac Video Driver Choices: {mac_videodriver_choices}')
            default_videodriver = mac_videodriver_choices
        elif platform.system() == 'Windows':
            windows_videodriver_choices = ['windib', 'directx']

            log.debug(f'Windows Video Driver Choices: {windows_videodriver_choices}')
            default_videodriver = windows_videodriver_choices

        group.add_argument('--video-driver',
                           default=None,
                           choices=default_videodriver)

        # Init Font Options
        parser = FontManager.args(parser=parser)

        # Init Sound Options
        parser = AudioManager.args(parser=parser)

        # Init Music Options
        parser = MidiManager.args(parser=parser)

        return parser

    def start(self):
        log.info(f'Framerate check (configured FPS: {self.fps})')

        # On Some platforms, pygame.USEREVENT is used to convey codes
        # so, we'll use USEREVENT + 1 to avoid confusion.
        pygame.time.set_timer(
            GameEngine.FPSEVENT,
            self.fps_refresh_rate
        )

        self._active_scene = None

    def quit(self):  # noqa: R0201
        # put a quit event in the event queue.
        pygame.event.post(
            pygame.event.Event(pygame.QUIT, {})
        )

    @property
    def active_scene(self):
        return self._active_scene

    @active_scene.setter
    def active_scene(self, new_scene):
        if new_scene != self._active_scene:
            log.debug(f'Active Scene change from {type(self._active_scene)}->{type(new_scene)}')
            self._active_scene = new_scene
            self.proxies = [self, self._active_scene]

    def load_resources(self):  # noqa: R0201
        log.info('Implement load_resource() in your subclass.')

    def process_events(self):
        # To use events in a different thread, use the fastevent package from pygame.
        # You can create your own new events with the pygame.event.Event() function.
        for event in pygame.fastevent.get():
            if event.type in GameEngine.AUDIO_EVENTS:
                self.process_audio_event(event)
            # elif event.type in GameEngine.CONTROLLER_EVENTS:
            #     self.process_controller_event(event)
            # elif event.type in GameEngine.DROP_EVENTS:
            #     self.process_drop_event(event)
            # elif event.type in GameEngine.FINGER_EVENTS:
            #     self.process_finger_event(event)
            elif event.type in GameEngine.GAME_EVENTS:
                self.process_game_event(event)
            elif event.type in GameEngine.JOYSTICK_EVENTS:
                self.process_joystick_event(event)
            elif event.type in GameEngine.MIDI_EVENTS:
                self.process_midi_event(event)
            elif event.type in GameEngine.MOUSE_EVENTS:
                self.process_mouse_event(event)
            elif event.type in GameEngine.KEYBOARD_EVENTS:
                self.process_keyboard_event(event)
            elif event.type in GameEngine.TEXT_EVENTS:
                self.process_text_event(event)
            elif event.type in GameEngine.WINDOW_EVENTS:
                self.process_window_event(event)
            else:
                # This will catch any unimplemented event types that we see.
                log.error(f'Unknown Event Type: {pygame.event.event_name(event.type).upper()}: {event.type}: {event} {GameEngine.ALL_EVENTS}')

    def process_audio_event(self, event):
        if event.type == pygame.AUDIODEVICEADDED:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.AUDIODEVICEREMOVED:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')

    def process_controller_event(self, event):
        if event.type == pygame.CONTROLLERAXISMOTION:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.CONTROLLERBUTTONDOWN:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.CONTROLLERBUTTONUP:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.CONTROLLERDEVICEADDED:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.CONTROLLERDEVICEADDED:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.CONTROLLERDEVICEREMAPPED:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.CONTROLLERDEVICEREMOVED:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')

    def process_drop_event(self, event):
        if event.type == pygame.DROPBEGIN:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.DROPCOMPLETE:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.DROPFILE:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.DROPTEXT:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')

    def process_finger_event(self, event):
        if event.type == pygame.FINGERDOWN:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.FINGERUP:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.FINGERMOTION:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')

    def process_midi_event(self, event):
        if event.type == pygame.MIDIIN:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.MIDIOUT:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')

    def process_mouse_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            # MOUSEMOTION      pos, rel, buttons
            self.mouse_manager.on_mouse_motion_event(event)
        elif event.type == pygame.MOUSEBUTTONUP:
            # MOUSEBUTTONUP    pos, button
            self.mouse_manager.on_mouse_button_up_event(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            # MOUSEBUTTONDOWN  pos, button
            self.mouse_manager.on_mouse_button_down_event(event)
        elif event.type == pygame.MOUSEWHEEL:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')

    def process_keyboard_event(self, event):
        if event.type == pygame.KEYDOWN:
            # KEYDOWN          unicode, key, mod
            self.keyboard_manager.on_key_down_event(event)
        elif event.type == pygame.KEYUP:
            # KEYUP            key, mod
            self.keyboard_manager.on_key_up_event(event)

    def process_joystick_event(self, event):
        if event.type == pygame.JOYAXISMOTION:
            # JOYAXISMOTION    joy, axis, value
            self.joystick_manager.on_axis_motion_event(event)
        elif event.type == pygame.JOYBALLMOTION:
            # JOYBALLMOTION    joy, ball, rel
            self.joystick_.on_ball_motion_event(event)
        elif event.type == pygame.JOYBUTTONUP:
            # JOYBUTTONUP      joy, button
            self.joystick_manager.on_button_up_event(event)
        elif event.type == pygame.JOYBUTTONDOWN:
            # JOYBUTTONDOWN    joy, button
            self.joystick_manager.on_button_down_event(event)
        elif event.type == pygame.JOYHATMOTION:
            # JOYHATMOTION     joy, hat, value
            self.joystick_manager.on_hat_motion_event(event)
        elif event.type == pygame.JOYDEVICEADDED:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.JOYDEVICEREMOVED:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')

    def process_text_event(self, event):
        if event.type == pygame.TEXTEDITING:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.TEXTINPUT:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')

    def process_window_event(self, event):
        if event.type == pygame.WINDOWSHOWN:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.WINDOWLEAVE:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.WINDOWSIZECHANGED:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.WINDOWENTER:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.WINDOWFOCUSGAINED:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.WINDOWRESTORED:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.WINDOWHITTEST:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.WINDOWHIDDEN:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.WINDOWFOCUSLOST:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.WINDOWMINIMIZED:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.WINDOWMAXIMIZED:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.WINDOWCLOSE:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.WINDOWEXPOSED:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.WINDOWTAKEFOCUS:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.WINDOWMOVED:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')
        elif event.type == pygame.WINDOWRESIZED:
            log.debug(f'(UNIMPLEMENTED) {pygame.event.event_name(event.type).upper()}: {event}')

    def process_game_event(self, event):
        # Game events are listed in the order they're most
        # likely to occur in.
        if event.type == GameEngine.FPSEVENT:
            # FPSEVENT is pygame.USEREVENT + 1
            self.game_manager.on_fps_event(event)
        elif event.type == GameEngine.GAMEEVENT:
            # GAMEEVENT is pygame.USEREVENT + 2
            self.game_manager.on_game_event(event)
        elif event.type == GameEngine.MENUEVENT:
            # MENUEVENT is pygame.USEREVENT + 3
            self.game_manager.on_menu_item_event(event)
        elif event.type == pygame.ACTIVEEVENT:
            # ACTIVEEVENT      gain, state
            self.game_manager.on_active_event(event)
        elif event.type == pygame.USEREVENT:
            # USEREVENT        code
            self.game_manager.on_user_event(event)
        elif event.type == pygame.VIDEORESIZE:
            # VIDEORESIZE      size, w, h
            self.game_manager.on_video_resize_event(event)
        elif event.type == pygame.VIDEOEXPOSE:
            # VIDEOEXPOSE      none
            self.game_manager.on_video_expose_event(event)
        elif event.type == pygame.SYSWMEVENT:
            # SYSWMEVENT
            self.game_manager.on_sys_wm_event(event)
        elif event.type == pygame.QUIT:
            # QUIT             none
            self.game_manager.on_quit_event(event)            

    def register_game_event(self, event_type, callback):
        # This registers a subtype of type GAMEEVENT to call a callback.
        log.info(f'Registering event type "{event_type}" for {callback}')
        self.registered_events[event_type] = callback

    def post_game_event(self, event_subtype, event_data):  # noqa: R0201
        event = event_data.copy()
        event['subtype'] = event_subtype
        pygame.event.post(
            pygame.event.Event(GameEngine.GAMEEVENT, event)
        )
        log.debug(f'Posted Event: {event}')

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
            log.error(f'Unregistered Event: {event} '
                      '(call self.register_game_event(<event subtype>, <event data>))')

    def on_key_up_event(self, event):
        # Wire up quit by default for escape and q.
        #
        # If a game implements on_key_up_event themselves
        # they'll have to map their quit keys or call super().on_key_up_event()
        if event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
            log.info('User requested quit.')
            self.quit()

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
            log.info(f'ACTIVE SCENE: {attr} for {type(self)}')
            return getattr(self.active_scene, attr)
        except AttributeError:
            log.info(f'{attr} is not implemented for {type(self)} or '
                     'for the active scene {type(self.active_scene)}')
            return getattr(super(), attr)


