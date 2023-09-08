#!/usr/bin/env python3
"""Contains GameEngine and helper classes for building a game."""
from __future__ import annotations

import argparse
import logging
import multiprocessing
import platform
import time
from pathlib import Path
from typing import Any, Callable, ClassVar, Literal, Self

import pygame
import pygame.freetype
import pygame.gfxdraw
import pygame.locals

from glitchygames import events
from glitchygames.color import PURPLE
from glitchygames.events.audio import AudioManager
from glitchygames.events.controller import ControllerManager
from glitchygames.events.drop import DropManager
from glitchygames.events.joystick import JoystickManager
from glitchygames.events.keyboard import KeyboardManager
from glitchygames.events.midi import MidiManager
from glitchygames.events.mouse import MouseManager
from glitchygames.events.window import WindowManager
from glitchygames.fonts import FontManager
from glitchygames.scenes import Scene, SceneManager
from glitchygames.sprites import Sprite

LOG: logging.Logger = logging.getLogger('game.engine')
LOG.addHandler(logging.NullHandler())

logging.basicConfig(format='%(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)

PACKAGE_PATH: str = Path(__file__).parent
ASSET_PATH: str = Path(__file__).parent / 'assets'


class GameManager(events.ResourceManager):
    log: logging.Logger = LOG

    class GameProxy(events.ResourceManager):
        log: logging.Logger = LOG

        def __init__(self: Self, **kwargs) -> None:
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
            self.game: object = kwargs.get('game')
            self.proxies = [self.game]

        def on_active_event(self: Self, event: pygame.event.Event) -> None:
            # ACTIVEEVENT      gain, state
            self.game.on_active_event(event=event)

        def on_fps_event(self: Self, event: pygame.event.Event) -> None:
            # FPSEVENT is pygame.USEREVENT + 1
            self.game.on_fps_event(event=event)

        def on_game_event(self: Self, event: pygame.event.Event) -> None:
            # GAMEEVENT is pygame.USEREVENT + 2
            self.game.on_game_event(event=event)

        def on_menu_item_event(self: Self, event: pygame.event.Event) -> None:
            # MENUEVENT is pygame.USEREVENT + 3
            self.game.on_menu_item_event(event=event)

        def on_sys_wm_event(self: Self, event: pygame.event.Event) -> None:
            # SYSWMEVENT
            self.game.on_sys_wm_event(event=event)

        def on_user_event(self: Self, event: pygame.event.Event) -> None:
            # USEREVENT        code
            self.game.on_user_event(event=event)

        def on_video_expose_event(self: Self, event: pygame.event.Event) -> None:
            # VIDEOEXPOSE      none
            self.game.on_video_expose_event(event=event)

        def on_video_resize_event(self: Self, event: pygame.event.Event) -> None:
            # VIDEORESIZE      size, w, h
            self.game.on_video_resize_event(event=event)

        def on_quit_event(self: Self, event: pygame.event.Event) -> None:
            # QUIT             none
            self.game.on_quit_event(event=event)

    def __init__(self: Self, game: object = None) -> None:
        """
        Game event manager.

        GameManager interfaces GameEngine with miscellaneous pygame events.

        Args:
        ----
        game - The game instance.

        """
        super().__init__(game=game)
        self.proxies: list[GameManager.GameProxy] = [GameManager.GameProxy(game=game)]

    @classmethod
    def args(cls: Self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        group = parser.add_argument_group('Game Options')  # noqa: F841

        return parser


class GameEngine(events.EventManager):
    log: logging.Logger = LOG
    game: object = None

    try:
        icon: pygame.Surface = pygame.image.load(Path(ASSET_PATH) / 'glitch.png')
    except FileNotFoundError:
        icon = None

    NAME: Literal['Boilerplate Adventures'] = 'Boilerplate Adventures'
    VERSION: Literal['1.0'] = '1.0'
    OPTIONS: ClassVar = None

    LAST_EVENT_MISS: ClassVar = None
    MISSING_EVENTS: ClassVar = []
    UNIMPLEMENTED_EVENTS: ClassVar = []

    # We add a layer of encapsulation here to simplify
    # the processing of events.  New event types added
    # to the events module need to be accounted for here
    # if they're not already handled
    #
    # These are wired up at the end of __init__()
    EVENT_HANDLERS: ClassVar = {
    }

    def __init__(self: Self, game: object, icon: pygame.Surface = None) -> None:
        """
        Set up pygame and handle events.

        Your game should subclass this class.

        Args:
        ----
        game - None, since it *is* the game.
        options - the configuration options passed via the command line.

        """
        super().__init__()

        if icon:
            GameEngine.icon = icon

        parser: argparse.ArgumentParser = argparse.ArgumentParser(
            f'{game.NAME} version {game.VERSION}'
        )

        parser = GameEngine.args(parser)

        # args is a class method, which allows us to call it before initializing a game
        # object, which allows us to query all of the game engine objects for their
        # command line parameters.
        try:
            game.args(parser.add_argument_group(f'{game.NAME} v{game.VERSION} Options'))
        except AttributeError:
            self.log.info(
                'Game does not implement arguments.  '
                'Add a def args(parser) class method.'
            )

        args: argparse.ArgumentParser = parser.parse_args()

        GameEngine.OPTIONS: dict[str, Any] = vars(args)
        options: dict[str, Any] = GameEngine.OPTIONS

        # TODO @<terry.simons@gmail.com>: Decouple game from event manager
        # so we can have clean separation for unhandled events
        # https://glitchy-games.atlassian.net/browse/GG-22
        super().__init__()

        self._active_scene: Scene = None

        # Pygame stuff.
        pygame.register_quit(self.quit_game)
        self.fps: float = options.get('fps', 0.0)
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

        # We are fully initialized now, so we can set up the scene.
        #
        # The scene will start once .start() is called on the GameEngine
        # object
        GameEngine.game = game
        self.scene_manager: SceneManager = SceneManager()

        # Resolution initialization.
        # Convert our resolution to a tuple
        (desired_width, desired_height) = self.desired_resolution.split('x')

        if self.windowed:
            self.mode_flags: int = 0
        else:
            self.mode_flags = pygame.FULLSCREEN

        self.desired_resolution: tuple[int, int] = self.suggested_resolution(
            desired_width,
            desired_height
        )

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
        self.initial_resolution: tuple[int, int] = (self.display_info.current_w,
                                   self.display_info.current_h)

        self.cursor: list[str] = self.set_cursor(cursor=None)

        # Set the screen update type.
        if self.scene_manager.update_type == 'update':
            self.display_update = pygame.display.update
        elif self.scene_manager.update_type == 'flip':
            self.display_update = pygame.display.flip
        else:
            self.log.error('Screen update type was neither "update" nor "flip".')

        # The Pygame documentation recommends against using hardware accelerated blitting.
        #
        # Note that you can also get the screen with pygame.display.get_surface()
        self.screen: pygame.Surface = pygame.display.set_mode(
            self.desired_resolution,
            self.mode_flags
        )

        self.initialize_event_handlers()

        self.print_system_info()

    def initialize_event_handlers(self: Self) -> None:
        # Event subsystem bootstrapping
        #
        # This gives us much faster event processing than
        # doing a lookup every time an event comes in since
        # we can just call the processing function directly.
        #
        # It's not as fast as a raw pygame fastevent loop,
        # but since we layer richer event types on top of
        # the pygame raw events, this gives us a nice balance
        # of extensibility with performance.
        for event_type in events.AUDIO_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_audio_event

        for event_type in events.MIDI_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_midi_event

        for event_type in events.WINDOW_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_window_event

        for event_type in events.GAME_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_game_event

        self.initialize_input_event_handlers()

    def initialize_input_event_handlers(self: Self) -> None:
        for event_type in events.CONTROLLER_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_controller_event

        for event_type in events.DROP_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_drop_event

        for event_type in events.FINGER_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_finger_event

        for event_type in events.JOYSTICK_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_joystick_event

        for event_type in events.KEYBOARD_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_keyboard_event

        for event_type in events.MOUSE_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_mouse_event

        for event_type in events.TEXT_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_text_event

    def __del__(self: Self) -> None:
        # This is the total # of sprites.
        self.log.info(f'Sprite Count: {Sprite.SPRITE_COUNT}')

        # This is a count of each type of sprite.
        for sprite_type, counters in Sprite.SPRITE_COUNTERS.items():
            # sprite_count = Sprite.SPRITE_COUNTERS[sprite_type][key]
            for key, value in counters.items():
                self.log.info(f'{sprite_type} Sprite {key}: {value}')

    @property
    def screen_width(self: Self) -> int:
        return self.screen.get_width()

    @property
    def screen_height(self: Self) -> int:
        return self.screen.get_height()

    def print_system_info(self: Self) -> None:
        # General Info
        self.log.info(f'CPU Count: {multiprocessing.cpu_count()}')
        self.log.info(f'System: {platform.system()}')
        self.log.info(f'Machine: {platform.machine()}')
        self.log.info(f'Platform: {platform.platform()}')
        self.log.info(f'Platform (Terse): {platform.platform(aliased=0, terse=1)}')
        self.log.info(f'Processor: {platform.processor()}')
        self.log.info(f'Release: {platform.release()}')

        # Set up a display mode.
        # Note: pygame.display.init() isn't necessary here
        # because we've already called pygame.init() which
        # initializes all available modules.
        #
        # Let's do a sanity check and make sure we're initialized.
        self.log.info(f'Display inited: {pygame.display.get_init()}')

        # Display some configuration information.
        self.log.info(f'SDL Version: {pygame.get_sdl_version()}')
        self.log.info(f'SDL Byte Order: {pygame.get_sdl_byteorder()}')

        # Dump a bit more info about the configured mode.
        self.log.info(
            'Display Driver: '
            f'{pygame.display.get_driver()}'
        )
        self.log.info(
            'Display Info: '
            f'{self.display_info}'
        )
        self.log.info(
            'Initial Resolution: '
            f'{self.initial_resolution}'
        )
        self.log.info(
            '8-bit Modes: '
            f'{pygame.display.list_modes(8)}'
        )
        self.log.info(
            '16-bit Modes: '
            f'{pygame.display.list_modes(16)}'
        )
        self.log.info(
            '24-bit Modes: '
            f'{pygame.display.list_modes(24)}'
        )
        self.log.info(
            '32-bit Modes: '
            f'{pygame.display.list_modes(32)}'
        )
        self.log.info(
            'Best Color Depth: '
            f'{pygame.display.mode_ok(self.initial_resolution), self.mode_flags}'
            f' ({self.mode_flags})'
        )
        self.log.info(
            'Window Manager Info: '
            f'{pygame.display.get_wm_info()}'
        )
        self.log.info(
            'Platform Timer Resolution: '
            f'{pygame.TIMER_RESOLUTION}'
        )

    def print_game_info(self: Self) -> None:
        self.log.debug(
            f'Successfully loaded {self.init_pass} modules '
            f'and failed loading {self.init_fail} modules.'
        )

        self.log.info(
            'Game Title: '
            f'{type(self).NAME}'
        )
        self.log.info(
            'Game Version: '
            f'{type(self).VERSION}'
        )

    def suggested_resolution(
            self: Self,
            desired_width: int = 0,
            desired_height: int = 0
    ) -> tuple[int, int]:
        # For Ubuntu 19.04, we can't reset the original res
        # so let's just let the system figure it out.
        if platform.system() == 'Linux':
            if 'arm' not in platform.machine():
                self.log.info('Ignoring full screen resolution change on Linux.')
            else:
                # RPi Hack
                #
                # The Raspberry Pi screen exposes
                # 2 resolutions, but only one works properly
                desired_width: Literal[800] = 800
                desired_height: Literal[480] = 480

        return (int(desired_width), int(desired_height))

    def set_cursor(self: Self, cursor: list[str], cursor_black: str = '.', cursor_white: str = 'X',
                   cursor_xor: str = 'o') -> list[str]:
        if not cursor:
            # Cursor setup.
            # Cursor width/height must be a multiple of 8
            cursor = [
                'XX                      ',
                'XXX                     ',
                'XXXX                    ',
                'XX.XX                   ',
                'XX..XX                  ',
                'XX...XX                 ',
                'XX....XX                ',
                'XX.....XX               ',
                'XX......XX              ',
                'XX.......XX             ',
                'XX........XX            ',
                'XX........XXX           ',
                'XX......XXXXX           ',
                'XX.XXX..XX              ',
                'XXXX XX..XX             ',
                'XX   XX..XX             ',
                '     XX..XX             ',
                '      XX..XX            ',
                '      XX..XX            ',
                '       XXXX             ',
                '       XX               ',
                '                        ',
                '                        ',
                '                        ']

        cursor_width: int = len(cursor[0])
        cursor_height: int = len(cursor)

        # cursor = cursor

        # Compile our cursor so we can draw it to the screen.
        cursor_data, cursor_mask = pygame.cursors.compile(
            cursor,
            black=cursor_black,
            white=cursor_white,
            xor=cursor_xor
        )

        # Now set the cursor as the active cursor.
        pygame.mouse.set_cursor(
            (cursor_width, cursor_height),
            (0, 0),
            cursor_data,
            cursor_mask
        )

        return cursor

    def initialize_system_icons(self: Self) -> None:
        # Set the window icon.
        #
        # Always call this before you call set_mode()

        icon: pygame.Surface = getattr(self.game, 'icon', GameEngine.icon)

        if icon is None:
            icon = pygame.Surface((32, 32))
            icon.fill(PURPLE)

        pygame.display.set_icon(icon)

        # Set the display caption.
        pygame.display.set_caption(f'{type(self).NAME} v{self.VERSION}',
                                   f'{type(self).NAME} v{self.VERSION}')

        # Get captions:
        (title, icontitle) = pygame.display.get_caption()
        self.log.info(f'Window Title: {title}')
        self.log.info(f'Icon Title: {icontitle}')

    @classmethod
    def args(cls: Self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        group = parser.add_argument_group('Graphics Options')

        group.add_argument('-f', '--target-fps',
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
            linux_videodriver_choices = [
                'x11',
                'dga',
                'fbcon',
                'directfb',
                'ggi',
                'vgl',
                'svgalib',
                'aalib'
            ]

            LOG.debug(f'Linux Video Driver Choices: {linux_videodriver_choices}')

            default_videodriver = linux_videodriver_choices

        elif platform.system() == 'MacOS':
            mac_videodriver_choices = []

            LOG.debug(f'Mac Video Driver Choices: {mac_videodriver_choices}')
            default_videodriver = mac_videodriver_choices
        elif platform.system() == 'Windows':
            windows_videodriver_choices = ['windib', 'directx']

            LOG.debug(f'Windows Video Driver Choices: {windows_videodriver_choices}')
            default_videodriver = windows_videodriver_choices

        group.add_argument('--video-driver',
                           default=None,
                           choices=default_videodriver)

        event_managers = (
            AudioManager,
            DropManager,
            ControllerManager,
            FontManager,
            GameManager,
            JoystickManager,
            KeyboardManager,
            MidiManager,
            MouseManager,
            WindowManager
        )

        for event_manager in event_managers:
            parser = event_manager.args(parser=parser)

        return parser

    def start(self: Self) -> None:
        try:
            # Initialize the game instance
            self.game = self.game(options=GameEngine.OPTIONS)

            self.scene_manager.game_engine = self

            self.registered_events = {}
            self.audio_manager = AudioManager(game=self.scene_manager)
            self.drop_manager = DropManager(game=self.scene_manager)
            self.controller_manager = ControllerManager(game=self.scene_manager)
            # TODO @<terry.simons@gmail.com>: Implement touch finger manager
            # self.finger_manager = FingerManager(game=self.scene_manager)
            # https://glitchy-games.atlassian.net/browse/GG-23
            self.font_manager = FontManager(game=self.scene_manager)
            self.game_manager = GameManager(game=self.scene_manager)
            self.joystick_manager = JoystickManager(game=self.scene_manager)
            self.keyboard_manager = KeyboardManager(game=self.scene_manager)
            self.midi_manager = MidiManager(game=self.scene_manager)
            self.mouse_manager = MouseManager(game=self.scene_manager)
            self.window_manager = WindowManager(game=self.scene_manager)

            # Get count of joysticks
            self.joysticks = []
            if self.joystick_manager:
                self.joysticks = self.joystick_manager.joysticks
            self.joystick_count = len(self.joysticks)

            self.scene_manager.switch_to_scene(self.game)
            self.scene_manager.start()
        except Exception:
            self.log.exception('Error starting game.')
        finally:
            pygame.display.quit()
            pygame.quit()

    def quit_game(self: Self) -> None:
        # put a quit event in the event queue.
        pygame.event.post(
            pygame.event.Event(pygame.QUIT, {})
        )

    def process_events(self: Self) -> bool:
        event_was_handled = False
        # To use events in a different thread, use the fastevent package from pygame.
        # You can create your own new events with the pygame.event.Event() object type.
        for event in pygame.fastevent.get():
            if event.type in GameEngine.EVENT_HANDLERS:
                event_was_handled = GameEngine.EVENT_HANDLERS[event.type](event)

            # If an event is in the event handler map, but the function
            # called didn't handle the event in question, we'll process it
            # as an uinimplemented event
            if not event_was_handled:
                self.process_unimplemented_event(event)

        return event_was_handled

    def process_audio_event(self: Self, event: pygame.event.Event) -> bool:
        if event.type == pygame.AUDIODEVICEADDED:
            # AUDIODEVICEADDED which, iscapture
            self.audio_manager.on_audio_device_added_event(event)
            return True

        if event.type == pygame.AUDIODEVICEREMOVED:
            # AUDIODEVICEREMOVED which, iscapture
            self.audio_manager.on_audio_device_removed_event(event)
            return True

        return False

    def process_controller_event(self: Self, event: pygame.event.Event) -> bool:
        if event.type == pygame.CONTROLLERAXISMOTION:
            self.controller_manager.on_controller_axis_motion_event(event)
            return True

        if event.type == pygame.CONTROLLERTOUCHPADMOTION:
            self.controller_manager.on_controller_touchpad_motion_event(event)
            return True

        if event.type == pygame.CONTROLLERBUTTONDOWN:
            self.controller_manager.on_controller_button_down_event(event)
            return True

        if event.type == pygame.CONTROLLERBUTTONUP:
            self.controller_manager.on_controller_button_up_event(event)
            return True

        if event.type == pygame.CONTROLLERTOUCHPADDOWN:
            self.controller_manager.on_controller_touchpad_down_event(event)
            return True

        if event.type == pygame.CONTROLLERTOUCHPADUP:
            self.controller_manager.on_controller_touchpad_up_event(event)
            return True

        if event.type == pygame.CONTROLLERDEVICEREMOVED:
            self.controller_manager.on_controller_device_removed_event(event)
            return True

        if event.type == pygame.CONTROLLERDEVICEADDED:
            self.controller_manager.on_controller_device_added_event(event)
            return True

        if event.type == pygame.CONTROLLERDEVICEREMAPPED:
            self.controller_manager.on_controller_device_remapped_event(event)
            return True

        # We haven't handled this event, so let's see if it's a controller init event
        return False

    def process_drop_event(self: Self, event: pygame.event.Event) -> bool:
        if event.type == pygame.DROPBEGIN:
            self.drop_manager.on_drop_begin_event(event)
            return True

        if event.type == pygame.DROPCOMPLETE:
            self.drop_manager.on_drop_complete_event(event)
            return True

        if event.type == pygame.DROPFILE:
            self.drop_manager.on_drop_file_event(event)
            return True

        if event.type == pygame.DROPTEXT:
            self.drop_manager.on_drop_text_event(event)
            return True

        return False

    def process_finger_event(self: Self, event: pygame.event.Event) -> bool:
        if event.type == pygame.FINGERDOWN:
            self.process_unimplemented_event(event)
            return True

        if event.type == pygame.FINGERUP:
            self.process_unimplemented_event(event)
            return True

        if event.type == pygame.FINGERMOTION:
            self.process_unimplemented_event(event)
            return True

        return False

    def process_midi_event(self: Self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MIDIIN:
            self.process_unimplemented_event(event)
            return True

        if event.type == pygame.MIDIOUT:
            self.process_unimplemented_event(event)
            return True

        return False

    def process_mouse_event(self: Self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            # MOUSEMOTION      pos, rel, buttons
            self.mouse_manager.on_mouse_motion_event(event)
            return True

        if event.type == pygame.MOUSEBUTTONUP:
            # MOUSEBUTTONUP    pos, button
            self.mouse_manager.on_mouse_button_up_event(event)
            return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            # MOUSEBUTTONDOWN  pos, button
            self.mouse_manager.on_mouse_button_down_event(event)
            return True

        if event.type == pygame.MOUSEWHEEL:
            self.mouse_manager.on_mouse_wheel_event(event)
            return True

        return False

    def process_keyboard_event(self: Self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            # KEYDOWN          unicode, key, mod
            self.keyboard_manager.on_key_down_event(event)
            return True

        if event.type == pygame.KEYUP:
            # KEYUP            key, mod
            self.keyboard_manager.on_key_up_event(event)
            return True

        return False

    def process_joystick_event(self: Self, event: pygame.event.Event) -> bool:
        if event.type == pygame.JOYAXISMOTION:
            # JOYAXISMOTION    joy, axis, value
            self.joystick_manager.on_joy_axis_motion_event(event)
            return True

        if event.type == pygame.JOYBALLMOTION:
            # JOYBALLMOTION    joy, ball, rel
            self.joystick_manager.on_joy_ball_motion_event(event)
            return True

        if event.type == pygame.JOYHATMOTION:
            # JOYHATMOTION     joy, hat, value
            self.joystick_manager.on_joy_hat_motion_event(event)
            return True

        if event.type == pygame.JOYBUTTONUP:
            # JOYBUTTONUP      joy, button
            self.joystick_manager.on_joy_button_up_event(event)
            return True

        if event.type == pygame.JOYBUTTONDOWN:
            # JOYBUTTONDOWN    joy, button
            self.joystick_manager.on_joy_button_down_event(event)
            return True

        if event.type == pygame.JOYDEVICEADDED:
            self.joystick_manager.on_joy_device_added_event(event)
            return True

        if event.type == pygame.JOYDEVICEREMOVED:
            self.joystick_manager.on_joy_device_removed_event(event)
            return True

        return False

    def process_text_event(self: Self, event: pygame.event.Event) -> None:
        if event.type == pygame.TEXTEDITING:
            self.process_unimplemented_event(event)
            return True

        if event.type == pygame.TEXTINPUT:
            self.process_unimplemented_event(event)
            return True

        return False

    def process_window_focus_event(self: Self, event: pygame.event.Event) -> bool:
        if event.type == pygame.WINDOWSHOWN:
            self.window_manager.on_window_shown_event(event)
            return True

        if event.type == pygame.WINDOWLEAVE:
            self.window_manager.on_window_leave_event(event)
            return True

        if event.type == pygame.WINDOWFOCUSGAINED:
            self.window_manager.on_window_focus_gained_event(event)
            return True

        if event.type == pygame.WINDOWFOCUSLOST:
            self.window_manager.on_window_focus_lost_event(event)
            return True

        if event.type == pygame.WINDOWENTER:
            self.window_manager.on_window_enter_event(event)
            return True

        if event.type == pygame.WINDOWTAKEFOCUS:
            self.window_manager.on_window_take_focus_event(event)
            return True

        return False

    def process_window_event(self: Self, event: pygame.event.Event) -> None:
        if event.type == pygame.WINDOWSIZECHANGED:
            # WINDOWSIZECHANGED x, y
            self.window_manager.on_window_size_changed_event(event)
            return True

        if event.type == pygame.WINDOWRESTORED:
            self.window_manager.on_window_restored_event(event)
            return True

        if event.type == pygame.WINDOWHITTEST:
            self.window_manager.on_window_hit_test_event(event)
            return True

        if event.type == pygame.WINDOWHIDDEN:
            self.window_manager.on_window_hidden_event(event)
            return True

        if event.type == pygame.WINDOWMINIMIZED:
            self.window_manager.on_window_minimized_event(event)
            return True

        if event.type == pygame.WINDOWMAXIMIZED:
            self.window_manager.on_window_maximized_event(event)
            return True

        if event.type == pygame.WINDOWMOVED:
            # WINDOWMOVED x, y
            self.window_manager.on_window_moved_event(event)
            return True

        if event.type == pygame.WINDOWCLOSE:
            self.window_manager.on_window_close_event(event)
            return True

        if event.type == pygame.WINDOWEXPOSED:
            self.window_manager.on_window_exposed_event(event)
            return True

        if event.type == pygame.WINDOWRESIZED:
            # WINDOWRESIZED x, y
            self.window_manager.on_window_resized_event(event)
            return True

        return False

    def process_game_event(self: Self, event: pygame.event.Event) -> None:
        # Game events are listed in the order they're most
        # likely to occur in.
        if event.type == events.FPSEVENT:
            # FPSEVENT is pygame.USEREVENT + 1
            self.game_manager.on_fps_event(event)
            return True

        if event.type == events.GAMEEVENT:
            # GAMEEVENT is pygame.USEREVENT + 2
            self.game_manager.on_game_event(event)
            return True

        if event.type == events.MENUEVENT:
            # MENUEVENT is pygame.USEREVENT + 3
            self.game_manager.on_menu_item_event(event)
            return True

        if event.type == pygame.ACTIVEEVENT:
            # ACTIVEEVENT      gain, state
            self.game_manager.on_active_event(event)
            return True

        if event.type == pygame.USEREVENT:
            # USEREVENT        code
            self.game_manager.on_user_event(event)
            return True

        if event.type == pygame.VIDEORESIZE:
            # VIDEORESIZE      size, w, h
            self.game_manager.on_video_resize_event(event)
            return True

        if event.type == pygame.VIDEOEXPOSE:
            # VIDEOEXPOSE      none
            self.game_manager.on_video_expose_event(event)
            return True

        if event.type == pygame.SYSWMEVENT:
            # SYSWMEVENT
            self.game_manager.on_sys_wm_event(event)
            return True

        if event.type == pygame.QUIT:
            # QUIT             none
            self.game_manager.on_quit_event(event)
            return True

        return False

    def process_unimplemented_event(self: Self, event: pygame.event.Event) -> None:
        if event.type not in self.UNIMPLEMENTED_EVENTS:
            self.log.debug('(UNIMPLEMENTED) '
                           f'{pygame.event.event_name(event.type).upper()}: {event}')
            self.UNIMPLEMENTED_EVENTS.append(event.type)

    def post_game_event(self: Self, event_subtype: pygame.event.EventType,
                        event_data: dict) -> None:
        event: pygame.event.Event = event_data.copy()
        event['subtype'] = event_subtype
        pygame.event.post(
            pygame.event.Event(events.GAMEEVENT, event)
        )
        self.log.debug(f'Posted Event: {event}')

    def suppress_event(self: Self, *args, attr: str, **kwargs) -> None:
        self.log.debug(f'Suppressing event: {attr}({args}, {kwargs})')

    def register_game_event(self: Self, event_type: pygame.event.EventType,
                            callback: Callable) -> None:
        # This registers a subtype of type GAMEEVENT to call a callback.
        self.log.info(f'Registering event type "{event_type}" for {callback}')
        self.registered_events[event_type] = callback

    def missing_event(self: Self, *args, **kwargs) -> None:
        if self.LAST_EVENT_MISS not in self.MISSING_EVENTS:
            self.MISSING_EVENTS.append(self.LAST_EVENT_MISS)

            self.log.info(f'Unimplemented method called: {self.LAST_EVENT_MISS}{args}, {kwargs}')
            self.suppress_event(
                *args,
                attr=self.LAST_EVENT_MISS,
                **kwargs
            )

        # Ensures we can always ctrl-c in cases where event spam occurs.
        time.sleep(0)

    # If the game hasn't hooked a call, we should check if the scene manager has.
    #
    # This will allow scenes to get pygame events directly, but we can still
    # hook those events in this engine, or in the subclassed game object, too.
    #
    # This allows maximum flexibility of event processing, with low overhead
    # at the expense of a slight layer violation.
    def __getattr__(self: Self, attr: str) -> Callable:
        #
        if attr.startswith('on_') and attr.endswith('_event'):
            self.LAST_EVENT_MISS = attr

            return self.missing_event

        raise AttributeError(f"'{type(self)}' object has no attribute '{attr}'")
