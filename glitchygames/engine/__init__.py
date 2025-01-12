#!/usr/bin/env python3
"""Contains GameEngine and helper classes for building a game."""

from __future__ import annotations

import argparse
import contextlib
import cProfile
import logging
import multiprocessing
import platform
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self

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
from glitchygames.events.touch import TouchManager
from glitchygames.events.window import WindowManager
from glitchygames.fonts import FontManager
from glitchygames.scenes import Scene, SceneManager
from glitchygames.sprites import Sprite

if TYPE_CHECKING:
    from collections.abc import Callable

LOG: logging.Logger = logging.getLogger('game.engine')
LOG.addHandler(logging.NullHandler())

# logging.basicConfig(format='%(name)s - %(levelname)s - %(message)s', level=logging.INFO)

PACKAGE_PATH: Path = Path(__file__).parent
ASSET_PATH: Path = Path(__file__).parent / 'assets'
TEST_MODE = False


class GameManager(events.ResourceManager):
    """Game event manager."""

    log: logging.Logger = LOG

    class GameProxy(events.ResourceManager):
        """Game event proxy."""

        log: logging.Logger = LOG

        def __init__(self: Self, game: Scene) -> None:
            """Initialize the game proxy.

            Args:
                game: the game instance

            Returns:
                None
            """
            super().__init__(game=game)
            self.game: Scene = game
            self.proxies: list = [self.game]

        def on_active_event(self: Self, event: events.HashableEvent) -> None:
            """Handle active event.

            Args:
                event: The pygame event.

            Returns:
                None
            """
            # ACTIVEEVENT      gain, state
            self.game.on_active_event(event=event)

        def on_fps_event(self: Self, event: events.HashableEvent) -> None:
            """Handle fps event.

            Args:
                event: The pygame event.

            Returns:
                None
            """
            # FPSEVENT is pygame.USEREVENT + 1
            self.game.on_fps_event(event=event)

        def on_game_event(self: Self, event: events.HashableEvent) -> None:
            """Handle game event.

            Args:
                event: The pygame event.

            Returns:
                None
            """
            # GAMEEVENT is pygame.USEREVENT + 2
            self.game.on_game_event(event=event)

        def on_menu_item_event(self: Self, event: events.HashableEvent) -> None:
            """Handle menu item event.

            Args:
                event: The pygame event.

            Returns:
                None
            """
            # MENUEVENT is pygame.USEREVENT + 3
            self.game.on_menu_item_event(event=event)

        def on_sys_wm_event(self: Self, event: events.HashableEvent) -> None:
            """Handle sys wm event.

            Args:
                event: The pygame event.

            Returns:
                None
            """
            # SYSWMEVENT
            self.game.on_sys_wm_event(event=event)

        def on_user_event(self: Self, event: events.HashableEvent) -> None:
            """Handle user event.

            Args:
                event: The pygame event.

            Returns:
                None
            """
            # USEREVENT        code
            self.game.on_user_event(event=event)

        def on_video_expose_event(self: Self, event: events.HashableEvent) -> None:
            """Handle video expose event.

            Args:
                event: The pygame event.

            Returns:
                None
            """
            # VIDEOEXPOSE      none
            self.game.on_video_expose_event(event=event)

        def on_video_resize_event(self: Self, event: events.HashableEvent) -> None:
            """Handle video resize event.

            Args:
                event: The pygame event.

            Returns:
                None
            """
            # VIDEORESIZE      size, w, h
            self.game.on_video_resize_event(event=event)

        def on_quit_event(self: Self, event: events.HashableEvent) -> None:
            """Handle quit event.

            Args:
                event: The pygame event.

            Returns:
                None
            """
            # QUIT             none
            self.game.on_quit_event(event=event)

    def __init__(self: Self, game: Scene) -> None:
        """Initialize the game event manager.

        Args:
            game: The game instance.

        Returns:
            None
        """
        super().__init__(game=game)
        self.proxies: list[GameManager.GameProxy] = [GameManager.GameProxy(game=game)]

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add arguments to the argument parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            None
        """
        group = parser.add_argument_group('Game Options')
        group.add_argument(
            '-l',
            '--log-level',
            help='set the logging level',
            choices=['debug', 'info', 'warning', 'error', 'critical'],
            default='info',
        )
        group.add_argument(
            '--no-unhandled-events',
            help='fail on unhandled events',
            action='store_true',
            default=False,
        )
        group.add_argument(
            '-p', '--profile', help='enable profiling', action='store_true', default=False
        )

        return parser


class GameEngine(events.EventManager):
    """Glitchy Games' Game engine.

    The game engine is responsible for initializing pygame and
    handling events.  It also provides a number of helper methods
    for common tasks such as setting the screen resolution and
    setting the cursor.

    Every Glitchy Game game inherits the GameEngine command line
    options, so you can add your own command line options by
    implementing the args() class method in your Scene class.
    """

    log: logging.Logger = LOG
    game: object = None

    try:
        icon: pygame.Surface = pygame.image.load(Path(ASSET_PATH) / 'glitch.png')
    except FileNotFoundError:
        icon = pygame.Surface((32, 32))

    NAME: Literal['Boilerplate Adventures'] = 'Boilerplate Adventures'
    VERSION: Literal['1.0'] = '1.0'
    OPTIONS: ClassVar = {}

    LAST_EVENT_MISS: ClassVar = ''
    MISSING_EVENTS: ClassVar = []
    UNIMPLEMENTED_EVENTS: ClassVar = []
    USE_FASTEVENTS: ClassVar = False

    # We add a layer of encapsulation here to simplify
    # the processing of events.  New event types added
    # to the events module need to be accounted for here
    # if they're not already handled
    #
    # These are wired up at the end of __init__()
    EVENT_HANDLERS: ClassVar = {}

    @classmethod
    def initialize_icon(cls: Any, icon: pygame.Surface | Path | None = None) -> None:
        """Initialize the game icon.

        Args:
            cls: the GlitchyGames GameEngine class.
            icon: a pygame.Surface, Path, str path, or None.

        Returns:
            None
        """
        # If it's not a pygame.Surface, assume it's a path
        if icon and not isinstance(icon, pygame.Surface):
            icon_path: Path = Path(icon)

            with contextlib.suppress(FileNotFoundError):
                GameEngine.icon: pygame.Surface = pygame.image.load(icon_path)

    @classmethod
    def args(cls: Any, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add Glitchy Games arguments to the argument parser.

        All Glitchy Games will inherit these arguments.

        Supported Arguments:
            -f, --target-fps
            --fps-refresh-rate
            -w, --windowed
            -r, --resolution
            --use-gfxdraw
            --update-type
            --video-driver

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            None
        """
        group = parser.add_argument_group('Graphics Options')

        group.add_argument(
            '-f',
            '--target-fps',
            help='cap the framerate (default: infinite)',
            type=float,
            default=0.0,
        )
        group.add_argument(
            '--fps-refresh-rate',
            help='how often to update the FPS counter in ms (default: 1000)',
            default=1000,
        )
        group.add_argument(
            '-w',
            '--windowed',
            help='run the program in windowed mode',
            action='store_true',
            default=True,
        )
        group.add_argument(
            '-r',
            '--resolution',
            help='the resolution to use (default: 1024x768)',
            default='800x480',
        )
        group.add_argument('--use-gfxdraw', action='store_true', default=False)
        group.add_argument(
            '--update-type',
            help='update or flip (default: update)',
            choices=['update', 'flip'],
            default='update',
        )

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
                'aalib',
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

        group.add_argument('--video-driver', default=None, choices=default_videodriver)

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
            WindowManager,
        )

        for event_manager in event_managers:
            parser = event_manager.args(parser=parser)

        return parser

    @classmethod
    def initialize_arguments(cls, game: Scene) -> dict[str, Any]:
        """Initialize the game arguments.

        Args:
            game: The game instance.

        Returns:
            options (dict[str, Any]): The game arguments.
        """
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
            cls.log.info(
                'Game does not implement arguments.  ' 'Add a def args(parser) class method.'
            )

        args: argparse.ArgumentParser = parser.parse_args()

        # Set the logging level
        logging.basicConfig(
            format='%(name)s - %(levelname)s - %(message)s', level=args.log_level.upper()
        )

        GameEngine.OPTIONS: dict[str, Any] = vars(args)

        # Some optimizations to reduce the number of lookups
        if GameEngine.OPTIONS['log_level'] in ['DEBUG', 'CRITICAL', 'ERROR']:
            GameEngine.OPTIONS['debug_events'] = True
        else:
            GameEngine.OPTIONS['debug_events'] = False

        options: dict[str, Any] = GameEngine.OPTIONS

        # Back propagate the options
        game.options = options

        return options

    def __init__(self: Self, game: object, icon: pygame.Surface | Path | str | None = None) -> Self:
        """Initialize the game engine.

        Args:
            game: The game instance.
            icon: The game icon.
        """
        super().__init__()

        self.initialize_icon(icon=icon)

        options = self.initialize_arguments(game=game)

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
        self.pygame_version = {'major': 0, 'minor': 0, 'patch': 0}

        self.pygame_version['major'] = pygame.version.vernum[0]
        self.pygame_version['minor'] = pygame.version.vernum[1]
        self.pygame_version['patch'] = pygame.version.vernum[2]

        # For compatibility with older versions of pygame, use fast events
        #
        # For versions >= 2.2, we can use the new event loop
        if pygame.version.vernum[0] < 2 and pygame.version.vernum[1] < 2:  # noqa: PLR2004
            self.USE_FASTEVENTS = True

        # Initialize all of the Pygame modules.
        self.init_pass, self.init_fail = pygame.init()
        self.print_game_info()

        # Enable fast events for multithreaded applications on older
        # versions of pygame, or use the new event loop for newer
        # versions of pygame >= 2.2
        if self.USE_FASTEVENTS:
            self.log.info(f'Using pygame.fastevents for pygame version {pygame.version.ver}')
            pygame.fastevent.init()
        else:
            # This is the default mode when USE_FASTEVENTS is disabled.
            #
            # pygame.event doesn't have an init() method, so nothing to do.
            self.log.info(f'Using pygame.events for pygame version {pygame.version.ver}')

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
            desired_width, desired_height
        )

        # window icon and system tray/dock icon
        self.initialize_system_icons()

        # Initialize display
        self.initialize_display()

        self.initialize_event_handlers()

        self.print_system_info()

    def initialize_display(self: Self) -> None:
        """Initialize the display.

        Returns:
            None
        """
        # Let's try to set a resolution to the most compatible for
        # the system.  If we don't provide any parameters, we'll get
        # a reasonble default, but you should consider whether that's
        # a good idea for your particular application.
        #
        # There are various caveats for hardware accelerated blitting
        # that make it undesirable in a lot of cases, so we'll just use
        # software.
        self.display_info = pygame.display.Info()
        self.initial_resolution: tuple[int, int] = (
            self.display_info.current_w,
            self.display_info.current_h,
        )

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
            self.desired_resolution, self.mode_flags
        )

    def initialize_event_handlers(self: Self) -> None:
        """Initialize event handlers.

        The engine calls this on your behalf.

        Event subsystem bootstrapping

        This gives us much faster event processing than
        doing a lookup every time an event comes in since
        we can just call the processing function directly.

        It's not as fast as a raw pygame event loop,
        but since we layer richer event types on top of
        the pygame raw events, this gives us a nice balance
        of extensibility with performance.

        Returns:
            None
        """
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
        """Initialize input event handlers.

        The engine calls this on your behalf.

        This initializes the input event handlers.

        Returns:
            None
        """
        for event_type in events.CONTROLLER_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_controller_event

        for event_type in events.DROP_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_drop_event

        for event_type in events.TOUCH_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_touch_event

        for event_type in events.JOYSTICK_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_joystick_event

        for event_type in events.KEYBOARD_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_keyboard_event

        for event_type in events.MOUSE_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_mouse_event

        for event_type in events.TEXT_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_text_event

    def __del__(self: Self) -> None:
        """Delete the game engine.

        Returns:
            None
        """
        # This is the total # of sprites.
        self.log.info(f'Sprite Count: {Sprite.SPRITE_COUNT}')

        # This is a count of each type of sprite.
        for sprite_type, counters in Sprite.SPRITE_COUNTERS.items():
            # sprite_count = Sprite.SPRITE_COUNTERS[sprite_type][key]
            for key, value in counters.items():
                self.log.info(f'{sprite_type} Sprite {key}: {value}')

    @property
    def screen_width(self: Self) -> int:
        """Get the screen width.

        Returns:
            int: The screen width.
        """
        return self.screen.get_width()

    @property
    def screen_height(self: Self) -> int:
        """Get the screen height.

        Returns:
            int: The screen height.
        """
        return self.screen.get_height()

    def print_system_info(self: Self) -> None:
        """Print system information.

        Returns:
            None
        """
        # General Info
        # TODO: put pygame version in here, too.
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
        self.log.info('Display Driver: ' f'{pygame.display.get_driver()}')
        self.log.info('Display Info: ' f'{self.display_info}')
        self.log.info('Initial Resolution: ' f'{self.initial_resolution}')
        self.log.info('8-bit Modes: ' f'{pygame.display.list_modes(8)}')
        self.log.info('16-bit Modes: ' f'{pygame.display.list_modes(16)}')
        self.log.info('24-bit Modes: ' f'{pygame.display.list_modes(24)}')
        self.log.info('32-bit Modes: ' f'{pygame.display.list_modes(32)}')
        self.log.info(
            'Best Color Depth: '
            f'{pygame.display.mode_ok(self.initial_resolution), self.mode_flags}'
            f' ({self.mode_flags})'
        )
        self.log.info('Window Manager Info: ' f'{pygame.display.get_wm_info()}')
        self.log.info('Platform Timer Resolution: ' f'{pygame.TIMER_RESOLUTION}')

    def print_game_info(self: Self) -> None:
        """Print game information.

        Returns:
            None
        """
        self.log.debug(
            f'Successfully loaded {self.init_pass} modules '
            f'and failed loading {self.init_fail} modules.'
        )

        self.log.info('Game Title: ' f'{type(self).NAME}')
        self.log.info('Game Version: ' f'{type(self).VERSION}')

    def suggested_resolution(
        self: Self, desired_width: int = 0, desired_height: int = 0
    ) -> tuple[int, int]:
        """Suggest a resolution.

        Args:
            desired_width (int): The desired width.
            desired_height (int): The desired height.

        Returns:
            tuple[int, int]: The suggested resolution.
        """
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

    @classmethod
    def set_cursor(
        cls,
        cursor: list[str],
        cursor_black: str = '.',
        cursor_white: str = 'X',
        cursor_xor: str = 'o',
    ) -> list[str]:
        """Set the cursor.

        Args:
            cursor (list[str]): The cursor.
            cursor_black (str): The black cursor.
            cursor_white (str): The white cursor.
            cursor_xor (str): The xor cursor.

        Returns:
            list[str]: The cursor.
        """
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
                '                        ',
            ]

        cursor_width: int = len(cursor[0])
        cursor_height: int = len(cursor)

        # cursor = cursor

        # Compile our cursor so we can draw it to the screen.
        cursor_data, cursor_mask = pygame.cursors.compile(
            cursor, black=cursor_black, white=cursor_white, xor=cursor_xor
        )

        # Now set the cursor as the active cursor.
        pygame.mouse.set_cursor((cursor_width, cursor_height), (0, 0), cursor_data, cursor_mask)

        return cursor

    def initialize_system_icons(self: Self) -> None:
        """Initialize system icons.

        Returns:
            None
        """
        # Set the window icon.
        #
        # Always call this before you call set_mode()

        icon: pygame.Surface = getattr(self.game, 'icon', GameEngine.icon)

        if icon is None:
            icon = pygame.Surface((32, 32))
            icon.fill(PURPLE)

        pygame.display.set_icon(icon)

        # Set the display caption.
        pygame.display.set_caption(
            f'{type(self).NAME} v{self.VERSION}', f'{type(self).NAME} v{self.VERSION}'
        )

        # Get captions:
        (title, icontitle) = pygame.display.get_caption()
        self.log.info(f'Window Title: {title}')
        self.log.info(f'Icon Title: {icontitle}')

    def start(self: Self) -> None:
        """Start the game engine.

        Returns:
            None
        """
        if self.game is None:
            raise RuntimeError(
                'Game not initialized.  Pass a game class to the GameEngine constructor.'
            )

        try:
            if GameEngine.OPTIONS['profile']:
                profiler = cProfile.Profile()
                profiler.enable()

            # Initialize the game instance
            self.game = self.game(options=GameEngine.OPTIONS)

            self.scene_manager.game_engine = self

            self.registered_events = {}
            self.audio_manager = AudioManager(game=self.scene_manager)
            self.drop_manager = DropManager(game=self.scene_manager)
            self.controller_manager = ControllerManager(game=self.scene_manager)
            self.touch_manager = TouchManager(game=self.scene_manager)
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

            if GameEngine.OPTIONS['profile']:
                profiler.disable()
                profiler.print_stats()

    @classmethod
    def quit_game(cls) -> None:
        """Quit the game.

        Emits a events.HashableEvent(pygame.QUIT, {}) event.

        Returns:
            None
        """
        # put a quit event in the event queue.
        pygame.event.post(events.HashableEvent(pygame.QUIT, {}))

    def handle_event(self, event: events.HashableEvent) -> None:
        """Handle pygame events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # First check for system-level QUIT event (window close button)
        if event.type == pygame.QUIT:
            self.log.info("Window close requested")
            self.scene_manager.quit_requested = True
            return

        # Check if there are any focused sprites in the current scene
        scene = self.scene_manager.active_scene
        if scene and scene.all_sprites:
            focused_sprites = [sprite for sprite in scene.all_sprites
                             if hasattr(sprite, 'active') and sprite.active]

            # If we have focused sprites, ALL key events go to the scene
            if focused_sprites and event.type == pygame.KEYDOWN:
                self.scene_manager.handle_event(event)
                return

        # Only handle engine-level key events if no focused sprites
        if event.type == pygame.KEYDOWN and event.key == pygame.K_q:
            self.log.info("Quit key pressed with no focused sprites")
            self.scene_manager.quit_requested = True
            return

        # Pass other events to the scene manager
        self.scene_manager.handle_event(event)

    def process_events(self: Self) -> bool:
        """Process events.

        Returns:
            bool: True if the event was handled, False otherwise.
        """
        event_was_handled = False
        # To use events in a different thread, use the fastevent package from pygame.
        # if you're using pygame < 2.2, you'll need to use pygame.fastevent.
        # if you're using pygame >= 2.2, you can use the new pygame.event.
        # You can create your own new events with the events.HashableEvent() object type.
        pump_events = pygame.event.get

        if self.USE_FASTEVENTS:
            pump_events = pygame.fastevent.get

        for raw_event in pump_events():
            # Support scenes processing pygame raw events, bypassing
            # the glitchygames.engine event processing altogether
            if hasattr(self._active_scene, 'process_event'):
                self._active_scene.process_event(raw_event)
                return True

            event: events.HashableEvent = events.HashableEvent(type=raw_event.type)
            event.__dict__.update(raw_event.dict)

            if event.type in GameEngine.EVENT_HANDLERS:
                event_was_handled = GameEngine.EVENT_HANDLERS[event.type](event)

            # If an event is in the event handler map, but the function
            # called didn't handle the event in question, we'll process it
            # as an uinimplemented event
            if not event_was_handled:
                self.process_unimplemented_event(event)
                return False

        return event_was_handled

    def process_audio_event(self: Self, event: events.HashableEvent) -> bool:
        """Process an audio event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.
        """
        if event.type == pygame.AUDIODEVICEADDED:
            # AUDIODEVICEADDED which, iscapture
            self.audio_manager.on_audio_device_added_event(event)
            return True

        if event.type == pygame.AUDIODEVICEREMOVED:
            # AUDIODEVICEREMOVED which, iscapture
            self.audio_manager.on_audio_device_removed_event(event)
            return True

        return False

    def process_controller_event(self: Self, event: events.HashableEvent) -> bool:
        """Process a controller event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.
        """
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

    def process_drop_event(self: Self, event: events.HashableEvent) -> bool:
        """Process a drop event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.
        """
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

    def process_touch_event(self: Self, event: events.HashableEvent) -> bool:
        """Process a touch event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.
        """
        if event.type == pygame.FINGERDOWN:
            self.touch_manager.on_touch_down_event(event)
            return True

        if event.type == pygame.FINGERUP:
            self.touch_manager.on_touch_up_event(event)
            return True

        if event.type == pygame.FINGERMOTION:
            self.touch_manager.on_touch_motion_event(event)
            return True

        return False

    def process_midi_event(self: Self, event: events.HashableEvent) -> bool:
        """Process a midi event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.
        """
        if event.type == pygame.MIDIIN:
            self.log.info(f'MIDIIN: {event} NOT IMPLEMENTED')
            return True

        if event.type == pygame.MIDIOUT:
            self.log.info(f'MIDIOUT: {event} NOT IMPLEMENTED')
            return True

        return False

    def process_mouse_event(self: Self, event: events.HashableEvent) -> bool:
        """Process a mouse event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.
        """
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

    def process_keyboard_event(self: Self, event: events.HashableEvent) -> bool:
        """Process a keyboard event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.
        """
        if event.type == pygame.KEYDOWN:
            # KEYDOWN          unicode, key, mod
            self.keyboard_manager.on_key_down_event(event)
            return True

        if event.type == pygame.KEYUP:
            # KEYUP            key, mod
            self.keyboard_manager.on_key_up_event(event)
            return True

        return False

    def process_joystick_event(self: Self, event: events.HashableEvent) -> bool:
        """Process a joystick event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.
        """
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

    def process_text_event(self: Self, event: events.HashableEvent) -> None:
        """Process a text event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.
        """
        if event.type == pygame.TEXTEDITING:
            self.process_unimplemented_event(event)
            return True

        if event.type == pygame.TEXTINPUT:
            self.process_unimplemented_event(event)
            return True

        return False

    def process_window_focus_event(self: Self, event: events.HashableEvent) -> bool:
        """Process a window focus event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.
        """
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

    def process_window_event(self: Self, event: events.HashableEvent) -> None:  # noqa: PLR0912
        """Process a window event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.
        """
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
            # WINDOWHIDDEN x, y
            self.window_manager.on_window_hidden_event(event)
            return True

        if event.type == pygame.WINDOWMINIMIZED:
            # WINDOWMINIMIZED x, y
            self.window_manager.on_window_minimized_event(event)
            return True

        if event.type == pygame.WINDOWMAXIMIZED:
            # WINDOWMAXIMIZED x, y
            self.window_manager.on_window_maximized_event(event)
            return True

        if event.type == pygame.WINDOWMOVED:
            # WINDOWMOVED x, y
            self.window_manager.on_window_moved_event(event)
            return True

        if event.type == pygame.WINDOWCLOSE:
            # WINDOWCLOSE
            self.window_manager.on_window_close_event(event)
            return True

        if event.type == pygame.WINDOWEXPOSED:
            self.window_manager.on_window_exposed_event(event)
            return True

        if event.type == pygame.WINDOWFOCUSLOST:
            # WINDOWFOCUSLOST
            self.window_manager.on_window_focus_lost_event(event)
            return True

        if event.type == pygame.WINDOWFOCUSGAINED:
            # WINDOWFOCUSGAINED
            self.window_manager.on_window_focus_gained_event(event)
            return True

        if event.type == pygame.WINDOWRESIZED:
            # WINDOWRESIZED x, y
            self.window_manager.on_window_resized_event(event)
            return True

        if event.type == pygame.WINDOWLEAVE:
            # WINDOWLEAVE
            self.window_manager.on_window_leave_event(event)
            return True

        if event.type == pygame.WINDOWENTER:
            # WINDOWENTER
            self.window_manager.on_window_enter_event(event)
            return True

        if event.type == pygame.WINDOWSHOWN:
            # WINDOWSHOWN
            self.window_manager.on_window_shown_event(event)
            return True

        return False

    def process_game_event(self: Self, event: events.HashableEvent) -> None:
        """Process a game event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.
        """
        # Game events are listed in the order they're most
        # likely to occur in.
        match event.type:
            case events.FPSEVENT:
                # FPSEVENT is pygame.USEREVENT + 1
                self.game_manager.on_fps_event(event)
                return True

            case events.GAMEEVENT:
                # GAMEEVENT is pygame.USEREVENT + 2
                self.game_manager.on_game_event(event)
                return True

            case events.MENUEVENT:
                # MENUEVENT is pygame.USEREVENT + 3
                self.game_manager.on_menu_item_event(event)
                return True

            case pygame.ACTIVEEVENT:
                # ACTIVEEVENT      gain, state
                self.game_manager.on_active_event(event)
                return True

            case pygame.USEREVENT:
                # USEREVENT        code
                self.game_manager.on_user_event(event)
                return True

            case pygame.VIDEORESIZE:
                # VIDEORESIZE      size, w, h
                self.game_manager.on_video_resize_event(event)
                return True

            case pygame.VIDEOEXPOSE:
                # VIDEOEXPOSE      none
                self.game_manager.on_video_expose_event(event)
                return True

            case pygame.SYSWMEVENT:
                # SYSWMEVENT
                self.game_manager.on_sys_wm_event(event)
                return True

            case pygame.QUIT:
                # QUIT             none
                self.game_manager.on_quit_event(event)
                return True

        return False

    def process_unimplemented_event(self: Self, event: events.HashableEvent) -> None:
        """Process an unimplemented event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            None
        """
        if event.type not in self.UNIMPLEMENTED_EVENTS:
            self.log.debug(
                '(UNIMPLEMENTED) ' f'{pygame.event.event_name(event.type).upper()}: {event}'
            )
            self.UNIMPLEMENTED_EVENTS.append(event.type)

    def post_game_event(
        self: Self, event_subtype: events.HashableEventType, event_data: dict
    ) -> None:
        """Post a game event.

        Args:
            event_subtype (events.HashableEventType): The event subtype.
            event_data (dict): The event data.

        Returns:
            None
        """
        event: events.HashableEvent = event_data.copy()
        event['subtype'] = event_subtype
        pygame.event.post(events.HashableEvent(events.GAMEEVENT, event))
        self.log.debug(f'Posted Event: {event}')

    def suppress_event(self: Self, *args: list, attr: str, **kwargs: dict) -> None:
        """Suppress an event.

        Args:
            *args: The args.
            attr (str): The attribute.
            **kwargs: The kwargs.

        Returns:
            None
        """
        self.log.debug(f'Suppressing event: {attr}({args}, {kwargs})')

    def register_game_event(
        self: Self, event_type: events.HashableEventType, callback: Callable
    ) -> None:
        """Register a game event.

        Args:
            event_type (events.HashableEventType): The event type.
            callback (Callable): The callback.

        Returns:
            None
        """
        # This registers a subtype of type GAMEEVENT to call a callback.
        self.log.info(f'Registering event type "{event_type}" for {callback}')
        self.registered_events[event_type] = callback

    def missing_event(self: Self, *args: list, **kwargs: dict) -> None:
        """Suppress unhandled on_*_event methods.

        We only want to log this once per event type.

        Args:
            *args: The args.
            **kwargs: The kwargs.

        Returns:
            None
        """
        # TODO: Add options that can be enabled in the engine to raise an exception
        #       when an unimplemented event is called.
        if self.LAST_EVENT_MISS not in self.MISSING_EVENTS:
            self.MISSING_EVENTS.append(self.LAST_EVENT_MISS)

            self.log.info(f'Unimplemented method called: {self.LAST_EVENT_MISS}{args}, {kwargs}')
            self.suppress_event(*args, attr=self.LAST_EVENT_MISS, **kwargs)

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
        """Suppress unhandled on_*_event methods.

        If the attribute being looked up is not an on_*_event
        attribute, raise AttributeError as usual.

        Args:
            attr (str): The attribute to proxy.

        Returns:
            Callable: The callable object.
        """
        if attr.startswith('on_') and attr.endswith('_event'):
            self.LAST_EVENT_MISS: str = attr

            return self.missing_event

        raise AttributeError(f"'{type(self)}' object has no attribute '{attr}'")
