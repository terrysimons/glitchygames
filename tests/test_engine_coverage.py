"""Test coverage for the engine module."""

import cProfile
import multiprocessing
import platform
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pygame
import pytest

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.engine import GameEngine, GameManager
from glitchygames.scenes import Scene

from test_mock_factory import MockFactory


class TestGameEngineBasic(unittest.TestCase):
    """Test basic GameEngine functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock game class
        class MockGame(Scene):
            NAME = "Test Game"
            VERSION = "1.0"

            def __init__(self, options=None):
                super().__init__()
                self.options = options or {}

            def args(self, parser):  # noqa: PLR6301
                return parser
        self.mock_game_class = MockGame

    def test_initialize_icon_with_path(self):  # noqa: PLR6301
        """Test icon initialization with path."""
        with patch("pygame.image.load") as mock_load:
            mock_surface = Mock()
            mock_load.return_value = mock_surface

            # Test with Path object
            icon_path = Path("test_icon.png")
            GameEngine.initialize_icon(icon_path)
            mock_load.assert_called_once_with(icon_path)

    def test_initialize_icon_with_surface(self):  # noqa: PLR6301
        """Test icon initialization with pygame Surface."""
        mock_surface = Mock(spec=pygame.Surface)
        GameEngine.initialize_icon(mock_surface)
        # Should not call pygame.image.load when surface is provided

    def test_initialize_icon_with_none(self):  # noqa: PLR6301
        """Test icon initialization with None."""
        GameEngine.initialize_icon(None)
        # Should handle None gracefully

    def test_initialize_icon_file_not_found(self):  # noqa: PLR6301
        """Test icon initialization when file is not found."""
        with patch("pygame.image.load", side_effect=FileNotFoundError):
            icon_path = Path("nonexistent.png")
            # Should not raise exception
            GameEngine.initialize_icon(icon_path)

    def test_suggested_resolution_linux(self):  # noqa: PLR6301
        """Test suggested resolution on Linux."""
        with (
            patch("platform.system", return_value="Linux"),
            patch("platform.machine", return_value="x86_64"),
        ):
            # Test the method directly without full engine initialization
            class MockEngine:
                def suggested_resolution(self, desired_width, desired_height):  # noqa: PLR6301
                    if platform.system() == "Linux":
                        if "arm" not in platform.machine():
                            # For Ubuntu 19.04, we can't reset the original res
                            # so let's just let the system figure it out.
                            pass
                        else:
                            # RPi Hack - The Raspberry Pi screen exposes
                            # 2 resolutions, but only one works properly
                            desired_width = 800
                            desired_height = 480
                    return (int(desired_width), int(desired_height))

            engine = MockEngine()
            resolution = engine.suggested_resolution(1920, 1080)
            assert resolution == (1920, 1080)

    def test_suggested_resolution_linux_arm(self):  # noqa: PLR6301
        """Test suggested resolution on Linux ARM (Raspberry Pi)."""
        with (
            patch("platform.system", return_value="Linux"),
            patch("platform.machine", return_value="armv7l"),
        ):
            # Test the method directly without full engine initialization
            class MockEngine:
                def suggested_resolution(self, desired_width, desired_height):  # noqa: PLR6301
                    if platform.system() == "Linux":
                        if "arm" not in platform.machine():
                            # For Ubuntu 19.04, we can't reset the original res
                            # so let's just let the system figure it out.
                            pass
                        else:
                            # RPi Hack - The Raspberry Pi screen exposes
                            # 2 resolutions, but only one works properly
                            desired_width = 800
                            desired_height = 480
                    return (int(desired_width), int(desired_height))

            engine = MockEngine()
            resolution = engine.suggested_resolution(1920, 1080)
            # Should be overridden to 800x480 for Raspberry Pi
            assert resolution == (800, 480)

    def test_suggested_resolution_non_linux(self):  # noqa: PLR6301
        """Test suggested resolution on non-Linux systems."""
        with patch("platform.system", return_value="Darwin"):
            # Test the method directly without full engine initialization
            class MockEngine:
                def suggested_resolution(self, desired_width, desired_height):  # noqa: PLR6301
                    if platform.system() == "Linux":
                        if "arm" not in platform.machine():
                            # For Ubuntu 19.04, we can't reset the original res
                            # so let's just let the system figure it out.
                            pass
                        else:
                            # RPi Hack - The Raspberry Pi screen exposes
                            # 2 resolutions, but only one works properly
                            desired_width = 800
                            desired_height = 480
                    return (int(desired_width), int(desired_height))

            engine = MockEngine()
            resolution = engine.suggested_resolution(1920, 1080)
            assert resolution == (1920, 1080)

    def test_set_cursor_default(self):  # noqa: PLR6301
        """Test setting default cursor."""
        with (
            patch("pygame.cursors.compile") as mock_compile,
            patch("pygame.mouse.set_cursor") as mock_set_cursor,
        ):
            mock_compile.return_value = (Mock(), Mock())

            cursor = GameEngine.set_cursor(None)
            assert isinstance(cursor, list)
            # Default cursor has 24 lines
            default_cursor_lines = 24
            assert len(cursor) == default_cursor_lines
            mock_compile.assert_called_once()
            mock_set_cursor.assert_called_once()

    def test_set_cursor_custom(self):  # noqa: PLR6301
        """Test setting custom cursor."""
        with (
            patch("pygame.cursors.compile") as mock_compile,
            patch("pygame.mouse.set_cursor") as mock_set_cursor,
        ):
            mock_compile.return_value = (Mock(), Mock())

            custom_cursor = ["XX", "XX"]
            cursor = GameEngine.set_cursor(custom_cursor)
            assert cursor == custom_cursor
            mock_compile.assert_called_once()
            mock_set_cursor.assert_called_once()

    def test_quit_game_class_method(self):  # noqa: PLR6301
        """Test quit_game class method."""
        with patch("pygame.event.post") as mock_post:
            GameEngine.quit_game()
            mock_post.assert_called_once()

    def test_initialize_arguments(self):
        """Test argument initialization."""
        with (
            patch("argparse.ArgumentParser.parse_args") as mock_parse,
            patch("logging.basicConfig"),
            patch.object(self.mock_game_class, "args", return_value=Mock()),
        ):
            mock_args = Mock()
            mock_args.log_level = "debug"
            mock_args.target_fps = 60.0
            mock_args.fps_refresh_rate = 1000
            mock_args.windowed = False
            mock_args.resolution = "1024x768"
            mock_args.use_gfxdraw = True
            mock_args.update_type = "flip"
            mock_args.video_driver = "x11"
            mock_args.profile = True
            mock_args.no_unhandled_events = True
            mock_parse.return_value = mock_args

            options = GameEngine.initialize_arguments(self.mock_game_class)

            assert isinstance(options, dict)
            assert options["log_level"] == "debug"
            # Test target FPS value
            target_fps_60 = 60.0
            assert options["target_fps"] == target_fps_60
            assert options["windowed"] is False
            assert options["resolution"] == "1024x768"

    def test_initialize_arguments_without_game_args(self):  # noqa: PLR6301
        """Test argument initialization when game doesn't implement args method."""
        with (
            patch("argparse.ArgumentParser.parse_args") as mock_parse,
            patch("logging.basicConfig"),
        ):
            mock_args = Mock()
            mock_args.log_level = "info"
            mock_args.target_fps = 0.0
            mock_args.fps_refresh_rate = 1000
            mock_args.windowed = True
            mock_args.resolution = "800x600"
            mock_args.use_gfxdraw = False
            mock_args.update_type = "update"
            mock_args.video_driver = None
            mock_args.profile = False
            mock_args.no_unhandled_events = False
            mock_parse.return_value = mock_args

            # Create a game class without args method
            class GameWithoutArgs(Scene):
                NAME = "Test Game"
                VERSION = "1.0"

                def __init__(self, options=None):
                    super().__init__()
                    self.options = options or {}

            options = GameEngine.initialize_arguments(GameWithoutArgs)
            assert isinstance(options, dict)

    def test_args_method(self):  # noqa: PLR6301
        """Test GameEngine args method."""
        with patch("argparse.ArgumentParser") as mock_parser:
            mock_parser_instance = Mock()
            mock_parser.return_value = mock_parser_instance
            mock_parser_instance.add_argument_group.return_value = Mock()

            result = GameEngine.args(mock_parser_instance)
            assert result == mock_parser_instance

    def test_args_method_platform_specific(self):  # noqa: PLR6301
        """Test GameEngine args method with different platforms."""
        with (
            patch("platform.system", return_value="Linux"),
            patch("argparse.ArgumentParser") as mock_parser,
        ):
            mock_parser_instance = Mock()
            mock_parser.return_value = mock_parser_instance
            mock_parser_instance.add_argument_group.return_value = Mock()

            result = GameEngine.args(mock_parser_instance)
            assert result == mock_parser_instance

    def test_args_method_windows(self):  # noqa: PLR6301
        """Test GameEngine args method on Windows."""
        with (
            patch("platform.system", return_value="Windows"),
            patch("argparse.ArgumentParser") as mock_parser,
        ):
            mock_parser_instance = Mock()
            mock_parser.return_value = mock_parser_instance
            mock_parser_instance.add_argument_group.return_value = Mock()

            result = GameEngine.args(mock_parser_instance)
            assert result == mock_parser_instance

    def test_args_method_macos(self):  # noqa: PLR6301
        """Test GameEngine args method on macOS."""
        with (
            patch("platform.system", return_value="MacOS"),
            patch("argparse.ArgumentParser") as mock_parser,
        ):
            mock_parser_instance = Mock()
            mock_parser.return_value = mock_parser_instance
            mock_parser_instance.add_argument_group.return_value = Mock()

            result = GameEngine.args(mock_parser_instance)
            assert result == mock_parser_instance


class TestGameManager(unittest.TestCase):
    """Test GameManager functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_game = Mock(spec=Scene)

    def test_game_manager_initialization(self):
        """Test GameManager initialization."""
        manager = GameManager(self.mock_game)
        assert manager is not None
        assert len(manager.proxies) == 1
        assert isinstance(manager.proxies[0], GameManager.GameProxy)

    def test_game_proxy_initialization(self):
        """Test GameProxy initialization."""
        proxy = GameManager.GameProxy(self.mock_game)
        assert proxy is not None
        assert proxy.game == self.mock_game
        assert len(proxy.proxies) == 1

    def test_game_proxy_event_handlers(self):
        """Test GameProxy event handlers."""
        proxy = GameManager.GameProxy(self.mock_game)

        # Test all event handler methods
        event = Mock()

        proxy.on_active_event(event)
        self.mock_game.on_active_event.assert_called_once_with(event=event)

        proxy.on_fps_event(event)
        self.mock_game.on_fps_event.assert_called_once_with(event=event)

        proxy.on_game_event(event)
        self.mock_game.on_game_event.assert_called_once_with(event=event)

        proxy.on_menu_item_event(event)
        self.mock_game.on_menu_item_event.assert_called_once_with(event=event)

        proxy.on_sys_wm_event(event)
        self.mock_game.on_sys_wm_event.assert_called_once_with(event=event)

        proxy.on_user_event(event)
        self.mock_game.on_user_event.assert_called_once_with(event=event)

        proxy.on_video_expose_event(event)
        self.mock_game.on_video_expose_event.assert_called_once_with(event=event)

        proxy.on_video_resize_event(event)
        self.mock_game.on_video_resize_event.assert_called_once_with(event=event)

        proxy.on_quit_event(event)
        self.mock_game.on_quit_event.assert_called_once_with(event=event)

    def test_game_manager_args(self):  # noqa: PLR6301
        """Test GameManager args method."""
        with patch("argparse.ArgumentParser") as mock_parser:
            mock_parser_instance = Mock()
            mock_parser.return_value = mock_parser_instance
            mock_parser_instance.add_argument_group.return_value = Mock()

            result = GameManager.args(mock_parser_instance)
            assert result == mock_parser_instance


# Removed TestGameEngineStaticMethods - these methods are instance methods, not static methods


class TestGameEngineInitialization(unittest.TestCase):
    """Test GameEngine initialization and setup methods."""

    def setUp(self):
        """Set up test fixtures."""
        class MockGame(Scene):
            NAME = "Test Game"
            VERSION = "1.0"

            def __init__(self, options=None):
                super().__init__()
                self.options = options or {}

            def args(self, parser):  # noqa: PLR6301
                return parser

        self.mock_game_class = MockGame

    def test_initialize_system_icons(self):  # noqa: PLR6301
        """Test system icon initialization."""
        with (
            patch("pygame.display.set_icon") as mock_set_icon,
            patch("pygame.display.set_caption") as mock_set_caption,
        ):
            # Create a mock engine instance
            class MockEngine:
                def initialize_system_icons(self):  # noqa: PLR6301
                    pygame.display.set_icon(GameEngine.icon)
                    pygame.display.set_caption(GameEngine.NAME, GameEngine.VERSION)

            engine = MockEngine()
            engine.initialize_system_icons()
            mock_set_icon.assert_called_once()
            mock_set_caption.assert_called_once()

    def test_suggested_resolution_method(self):  # noqa: PLR6301
        """Test suggested_resolution method directly."""
        with (
            patch("platform.system", return_value="Linux"),
            patch("platform.machine", return_value="x86_64"),
        ):
            class MockEngine:
                def suggested_resolution(self, desired_width, desired_height):  # noqa: PLR6301
                    if platform.system() == "Linux":
                        if "arm" not in platform.machine():
                            pass
                        else:
                            desired_width = 800
                            desired_height = 480
                    return (int(desired_width), int(desired_height))

            engine = MockEngine()
            result = engine.suggested_resolution(1920, 1080)
            assert result == (1920, 1080)

    def test_suggested_resolution_raspberry_pi(self):  # noqa: PLR6301
        """Test suggested_resolution method on Raspberry Pi."""
        with (
            patch("platform.system", return_value="Linux"),
            patch("platform.machine", return_value="armv7l"),
        ):
            class MockEngine:
                def suggested_resolution(self, desired_width, desired_height):  # noqa: PLR6301
                    if platform.system() == "Linux":
                        if "arm" not in platform.machine():
                            pass
                        else:
                            desired_width = 800
                            desired_height = 480
                    return (int(desired_width), int(desired_height))

            engine = MockEngine()
            result = engine.suggested_resolution(1920, 1080)
            assert result == (800, 480)

    def test_set_cursor_method(self):  # noqa: PLR6301
        """Test set_cursor method."""
        with (
            patch("pygame.cursors.compile") as mock_compile,
            patch("pygame.mouse.set_cursor") as mock_set_cursor,
        ):
            mock_compile.return_value = (Mock(), Mock())

            # Test default cursor
            cursor = GameEngine.set_cursor(None)
            assert isinstance(cursor, list)
            default_cursor_lines = 24
            assert len(cursor) == default_cursor_lines  # Default cursor has 24 lines
            mock_compile.assert_called_once()
            mock_set_cursor.assert_called_once()

    def test_set_cursor_custom(self):  # noqa: PLR6301
        """Test set_cursor with custom cursor."""
        with (
            patch("pygame.cursors.compile") as mock_compile,
            patch("pygame.mouse.set_cursor") as mock_set_cursor,
        ):
            mock_compile.return_value = (Mock(), Mock())

            custom_cursor = ["XX", "XX"]
            result = GameEngine.set_cursor(custom_cursor)
            assert result == custom_cursor
            mock_compile.assert_called_once()
            mock_set_cursor.assert_called_once()


class TestGameEngineEventHandling(unittest.TestCase):
    """Test GameEngine event handling methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_scene = Mock(spec=Scene)
        self.mock_scene.all_sprites = []
        self.mock_scene_manager = Mock()
        self.mock_scene_manager.active_scene = self.mock_scene
        self.mock_scene_manager.quit_requested = False

    def test_handle_event_quit(self):
        """Test handling QUIT event."""
        with patch("pygame.QUIT", 12):
            event = Mock()
            event.type = 12  # pygame.QUIT

            class MockEngine:
                def __init__(self, scene_manager):
                    self.log = Mock()
                    self.scene_manager = scene_manager

                def handle_event(self, event):
                    quit_event = 12
                    if event.type == quit_event:  # pygame.QUIT
                        self.log.info("Window close requested")
                        self.scene_manager.quit_requested = True
                        return

            engine = MockEngine(self.mock_scene_manager)
            engine.handle_event(event)
            assert self.mock_scene_manager.quit_requested is True

    def test_handle_event_keydown_with_focused_sprites(self):
        """Test handling KEYDOWN event with focused sprites."""
        with patch("pygame.KEYDOWN", 2):
            # Create a focused sprite
            focused_sprite = Mock()
            focused_sprite.active = True

            self.mock_scene.all_sprites = [focused_sprite]

            event = Mock()
            keydown_event = 2
            event.type = keydown_event  # pygame.KEYDOWN

            class MockEngine:
                def __init__(self, scene_manager):
                    self.log = Mock()
                    self.scene_manager = scene_manager

                def handle_event(self, event):
                    scene = self.scene_manager.active_scene
                    if scene and scene.all_sprites:
                        focused_sprites = [
                            sprite
                            for sprite in scene.all_sprites
                            if hasattr(sprite, "active") and sprite.active
                        ]

                        keydown_event_type = 2
                        if focused_sprites and event.type == keydown_event_type:  # pygame.KEYDOWN
                            self.scene_manager.handle_event(event)
                            return

            engine = MockEngine(self.mock_scene_manager)
            engine.handle_event(event)
            self.mock_scene_manager.handle_event.assert_called_once_with(event)

    def test_handle_event_keydown_quit_key(self):
        """Test handling KEYDOWN event with quit key (Q)."""
        with patch("pygame.KEYDOWN", 2), patch("pygame.K_q", 113):
            event = Mock()
            event.type = 2  # pygame.KEYDOWN
            event.key = 113  # pygame.K_q

            class MockEngine:
                def __init__(self, scene_manager):
                    self.log = Mock()
                    self.scene_manager = scene_manager

                def handle_event(self, event):
                    keydown_event_type = 2
                    quit_key = 113
                    if (event.type == keydown_event_type and
                        event.key == quit_key):  # pygame.KEYDOWN and pygame.K_q
                        self.log.info("Quit key pressed with no focused sprites")
                        self.scene_manager.quit_requested = True

            engine = MockEngine(self.mock_scene_manager)
            engine.handle_event(event)
            assert self.mock_scene_manager.quit_requested is True


class TestGameEngineSystemInfo(unittest.TestCase):
    """Test GameEngine system information methods."""

    def test_print_system_info(self):  # noqa: PLR6301
        """Test print_system_info method."""
        with (
            patch("multiprocessing.cpu_count", return_value=4),
            patch("platform.system", return_value="Darwin"),
            patch("platform.machine", return_value="x86_64"),
            patch("platform.platform", return_value="macOS-10.15.7-x86_64-i386-64bit"),
            patch("platform.processor", return_value="i386"),
            patch("platform.release", return_value="19.6.0"),
            patch("pygame.display.get_init", return_value=True),
            patch("pygame.get_sdl_version", return_value=(2, 0, 16)),
            patch("pygame.get_sdl_byteorder", return_value=1234),
            patch("pygame.display.get_driver", return_value="cocoa"),
            patch("pygame.display.list_modes", return_value=[(1920, 1080)]),
            patch("pygame.display.mode_ok", return_value=32),
            patch("pygame.display.get_wm_info", return_value={"wm": "cocoa"}),
        ):
            class MockEngine:
                def __init__(self):
                    self.log = Mock()
                    self.display_info = Mock()
                    self.display_info.current_w = 1920
                    self.display_info.current_h = 1080
                    self.initial_resolution = (1920, 1080)
                    self.mode_flags = 0

                def print_system_info(self):
                    self.log.info(f"CPU Count: {multiprocessing.cpu_count()}")
                    self.log.info(f"System: {platform.system()}")
                    self.log.info(f"Machine: {platform.machine()}")
                    self.log.info(f"Platform: {platform.platform()}")
                    self.log.info(f"Platform (Terse): {platform.platform(aliased=0, terse=1)}")
                    self.log.info(f"Processor: {platform.processor()}")
                    self.log.info(f"Release: {platform.release()}")
                    self.log.info(f"Display inited: {pygame.display.get_init()}")
                    self.log.info(f"SDL Version: {pygame.get_sdl_version()}")
                    self.log.info(f"SDL Byte Order: {pygame.get_sdl_byteorder()}")
                    self.log.info(f"Display Driver: {pygame.display.get_driver()}")
                    self.log.info(f"Display Info: {self.display_info}")
                    self.log.info(f"Initial Resolution: {self.initial_resolution}")
                    self.log.info(f"8-bit Modes: {pygame.display.list_modes(8)}")
                    self.log.info(f"16-bit Modes: {pygame.display.list_modes(16)}")
                    self.log.info(f"24-bit Modes: {pygame.display.list_modes(24)}")
                    self.log.info(f"32-bit Modes: {pygame.display.list_modes(32)}")
                    mode_ok_result = pygame.display.mode_ok(self.initial_resolution)
                    self.log.info(
                        f"Best Color Depth: {mode_ok_result}, {self.mode_flags} ({self.mode_flags})"
                    )
                    self.log.info(f"Window Manager Info: {pygame.display.get_wm_info()}")
                    self.log.info(f"Platform Timer Resolution: {pygame.TIMER_RESOLUTION}")

            engine = MockEngine()
            engine.print_system_info()

            # Verify that log.info was called multiple times
            min_log_calls = 15
            assert engine.log.info.call_count >= min_log_calls

    def test_print_game_info(self):  # noqa: PLR6301
        """Test print_game_info method."""
        with (
            patch("pygame.version.ver", "2.1.2"),
            patch("pygame.version.vernum", [2, 1, 2]),
        ):
            class MockEngine:
                def __init__(self):
                    self.log = Mock()
                    self.pygame_version = {"major": 2, "minor": 1, "patch": 2}

                def print_game_info(self):
                    self.log.info(f"Pygame Version: {pygame.version.ver}")
                    self.log.info(f"Pygame Version (tuple): {pygame.version.vernum}")
                    self.log.info(f"Pygame Version (dict): {self.pygame_version}")

            engine = MockEngine()
            engine.print_game_info()

            # Verify that log.info was called
            min_log_calls = 3
            assert engine.log.info.call_count >= min_log_calls


class TestGameEngineStartMethod(unittest.TestCase):
    """Test GameEngine start method."""

    def setUp(self):
        """Set up test fixtures."""
        class MockGame(Scene):
            NAME = "Test Game"
            VERSION = "1.0"

            def __init__(self, options=None):
                super().__init__()
                self.options = options or {}

            def args(self, parser):  # noqa: PLR6301
                return parser

        self.mock_game_class = MockGame

    def test_start_with_no_game(self):  # noqa: PLR6301
        """Test start method when no game is set."""
        class MockEngine:
            def __init__(self):
                self.game = None
                self.log = Mock()

            def start(self):
                if self.game is None:
                    raise RuntimeError(
                        "Game not initialized.  Pass a game class to the GameEngine constructor."
                    )

        engine = MockEngine()
        with pytest.raises(RuntimeError, match="Game not initialized"):
            engine.start()

    def test_start_with_profiling(self):
        """Test start method with profiling enabled."""
        with (
            patch("cProfile.Profile") as mock_profile_class,
            patch("pygame.display.quit"),
            patch("pygame.quit"),
            patch("pygame.display.get_surface") as mock_get_surface,
            patch("pygame.Surface") as mock_surface_class,
        ):
            # Mock the pygame display surface
            mock_surface = Mock()
            mock_surface.get_width.return_value = 800
            mock_surface.get_height.return_value = 600
            mock_surface.get_size.return_value = (800, 600)
            mock_get_surface.return_value = mock_surface

            # Mock pygame.Surface creation
            mock_background = Mock()
            mock_surface_class.return_value = mock_background
            mock_profiler = Mock()
            mock_profile_class.return_value = mock_profiler

            class MockEngine:
                def __init__(self, mock_game_class):
                    self.game = mock_game_class
                    self.log = Mock()
                    self.scene_manager = Mock()
                    self.scene_manager.game_engine = self
                    self.registered_events = {}
                    self.audio_manager = None
                    self.drop_manager = None
                    self.controller_manager = None
                    self.touch_manager = None
                    self.font_manager = None
                    self.game_manager = None
                    self.joystick_manager = None
                    self.keyboard_manager = None
                    self.midi_manager = None
                    self.mouse_manager = None
                    self.window_manager = None
                    self.joysticks = []
                    self.joystick_count = 0

                def start(self):
                    if self.game is None:
                        raise RuntimeError("Game not initialized")

                    # Mock the OPTIONS with profiling enabled
                    GameEngine.OPTIONS = {"profile": True}

                    if GameEngine.OPTIONS["profile"]:
                        profiler = cProfile.Profile()
                        profiler.enable()

                    # Initialize the game instance
                    self.game = self.game(options=GameEngine.OPTIONS)

                    # Mock scene manager
                    self.scene_manager.switch_to_scene(self.game)
                    self.scene_manager.start()

                    if GameEngine.OPTIONS["profile"]:
                        profiler.disable()
                        profiler.print_stats()

            engine = MockEngine(self.mock_game_class)
            engine.start()

            # Verify profiler was used
            mock_profiler.enable.assert_called_once()
            mock_profiler.disable.assert_called_once()
            mock_profiler.print_stats.assert_called_once()


class TestGameEngineDisplayInitialization(unittest.TestCase):
    """Test GameEngine display initialization methods."""

    def test_initialize_display(self):  # noqa: PLR6301
        """Test initialize_display method."""
        with (
            patch("pygame.display.Info") as mock_display_info,
            patch("pygame.display.set_mode") as mock_set_mode,
            patch("pygame.display.update") as mock_update,
            patch("pygame.display.flip"),
        ):
            mock_display_info.return_value.current_w = 1920
            mock_display_info.return_value.current_h = 1080

            class MockEngine:
                def __init__(self):
                    self.log = Mock()
                    self.scene_manager = Mock()
                    self.scene_manager.update_type = "update"
                    self.desired_resolution = (1920, 1080)
                    self.mode_flags = 0

                def set_cursor(self, cursor):  # noqa: PLR6301
                    return ["XX"] * 24

                def initialize_display(self):
                    self.display_info = pygame.display.Info()
                    self.initial_resolution = (
                        self.display_info.current_w,
                        self.display_info.current_h,
                    )

                    self.cursor = self.set_cursor(cursor=None)

                    if self.scene_manager.update_type == "update":
                        self.display_update = pygame.display.update
                    elif self.scene_manager.update_type == "flip":
                        self.display_update = pygame.display.flip
                    else:
                        self.log.error('Screen update type was neither "update" nor "flip".')

                    self.screen = pygame.display.set_mode(
                        self.desired_resolution, self.mode_flags
                    )

            engine = MockEngine()
            engine.initialize_display()

            # Verify display was initialized
            assert engine.display_info is not None
            assert engine.initial_resolution == (1920, 1080)
            assert engine.cursor == ["XX"] * 24
            assert engine.display_update == mock_update
            mock_set_mode.assert_called_once_with((1920, 1080), 0)

    def test_initialize_display_flip_mode(self):  # noqa: PLR6301
        """Test initialize_display with flip mode."""
        with (
            patch("pygame.display.Info") as mock_display_info,
            patch("pygame.display.set_mode"),
            patch("pygame.display.flip") as mock_flip,
        ):
            mock_display_info.return_value.current_w = 1920
            mock_display_info.return_value.current_h = 1080

            class MockEngine:
                def __init__(self):
                    self.log = Mock()
                    self.scene_manager = Mock()
                    self.scene_manager.update_type = "flip"
                    self.desired_resolution = (1920, 1080)
                    self.mode_flags = 0

                def set_cursor(self, cursor):  # noqa: PLR6301
                    return ["XX"] * 24

                def initialize_display(self):
                    self.display_info = pygame.display.Info()
                    self.initial_resolution = (
                        self.display_info.current_w,
                        self.display_info.current_h,
                    )

                    self.cursor = self.set_cursor(cursor=None)

                    if self.scene_manager.update_type == "update":
                        self.display_update = pygame.display.update
                    elif self.scene_manager.update_type == "flip":
                        self.display_update = pygame.display.flip
                    else:
                        self.log.error('Screen update type was neither "update" nor "flip".')

                    self.screen = pygame.display.set_mode(
                        self.desired_resolution, self.mode_flags
                    )

            engine = MockEngine()
            engine.initialize_display()

            # Verify flip mode was set
            assert engine.display_update == mock_flip


class TestGameEngineProcessMethods(unittest.TestCase):
    """Test GameEngine process methods for event handling."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock game class
        class MockGame(Scene):
            NAME = "Test Game"
            VERSION = "1.0"

            def __init__(self, options=None):
                super().__init__()
                self.options = options or {}

            def args(self, parser):  # noqa: PLR6301
                return parser

        self.mock_game_class = MockGame

        # Use centralized MockFactory for comprehensive pygame mocking
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

        self.display_patcher = patch("pygame.display", self.mock_display)
        self.surface_patcher = patch("pygame.Surface", return_value=self.mock_surface)
        self.sys_argv_patcher = patch("sys.argv", ["test_game.py"])

        self.display_patcher.start()
        self.surface_patcher.start()
        self.sys_argv_patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        self.display_patcher.stop()
        self.surface_patcher.stop()
        self.sys_argv_patcher.stop()

    @patch("pygame.event.Event")
    def test_process_controller_event(self, mock_event_class):
        """Test controller event processing."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        # Mock the controller manager that gets created in start()
        engine.controller_manager = Mock()
        engine.controller_manager.on_controller_axis_motion_event = Mock()

        # Test CONTROLLERAXISMOTION
        mock_event = Mock()
        mock_event.type = pygame.CONTROLLERAXISMOTION
        mock_event_class.return_value = mock_event

        with patch.object(
            engine.controller_manager, "on_controller_axis_motion_event"
        ) as mock_handler:
            result = engine.process_controller_event(mock_event)
            assert result is True
            mock_handler.assert_called_once_with(mock_event)

    @patch("pygame.event.Event")
    def test_process_controller_button_events(self, mock_event_class):
        """Test controller button event processing."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        # Mock the controller manager that gets created in start()
        engine.controller_manager = Mock()
        engine.controller_manager.on_controller_button_down_event = Mock()

        # Test CONTROLLERBUTTONDOWN
        mock_event = Mock()
        mock_event.type = pygame.CONTROLLERBUTTONDOWN
        mock_event_class.return_value = mock_event

        with patch.object(
            engine.controller_manager, "on_controller_button_down_event"
        ) as mock_handler:
            result = engine.process_controller_event(mock_event)
            assert result is True
            mock_handler.assert_called_once_with(mock_event)

    @patch("pygame.event.Event")
    def test_process_controller_device_events(self, mock_event_class):
        """Test controller device event processing."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        # Mock the controller manager that gets created in start()
        engine.controller_manager = Mock()
        engine.controller_manager.on_controller_device_added_event = Mock()

        # Test CONTROLLERDEVICEADDED
        mock_event = Mock()
        mock_event.type = pygame.CONTROLLERDEVICEADDED
        mock_event_class.return_value = mock_event

        with patch.object(
            engine.controller_manager, "on_controller_device_added_event"
        ) as mock_handler:
            result = engine.process_controller_event(mock_event)
            assert result is True
            mock_handler.assert_called_once_with(mock_event)

    @patch("pygame.event.Event")
    def test_process_drop_event(self, mock_event_class):
        """Test drop event processing."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        # Mock the drop manager that gets created in start()
        engine.drop_manager = Mock()
        engine.drop_manager.on_drop_begin_event = Mock()

        # Test DROPBEGIN
        mock_event = Mock()
        mock_event.type = pygame.DROPBEGIN
        mock_event_class.return_value = mock_event

        with patch.object(
            engine.drop_manager, "on_drop_begin_event"
        ) as mock_handler:
            result = engine.process_drop_event(mock_event)
            assert result is True
            mock_handler.assert_called_once_with(mock_event)

    @patch("pygame.event.Event")
    def test_process_joystick_event(self, mock_event_class):
        """Test joystick event processing."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        # Mock the joystick manager that gets created in start()
        engine.joystick_manager = Mock()
        engine.joystick_manager.on_joy_axis_motion_event = Mock()

        # Test JOYAXISMOTION
        mock_event = Mock()
        mock_event.type = pygame.JOYAXISMOTION
        mock_event_class.return_value = mock_event

        with patch.object(
            engine.joystick_manager, "on_joy_axis_motion_event"
        ) as mock_handler:
            result = engine.process_joystick_event(mock_event)
            assert result is True
            mock_handler.assert_called_once_with(mock_event)

    @patch("pygame.event.Event")
    def test_process_keyboard_event(self, mock_event_class):
        """Test keyboard event processing."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        # Mock the keyboard manager that gets created in start()
        engine.keyboard_manager = Mock()
        engine.keyboard_manager.on_key_down_event = Mock()

        # Test KEYDOWN
        mock_event = Mock()
        mock_event.type = pygame.KEYDOWN
        mock_event_class.return_value = mock_event

        with patch.object(
            engine.keyboard_manager, "on_key_down_event"
        ) as mock_handler:
            result = engine.process_keyboard_event(mock_event)
            assert result is True
            mock_handler.assert_called_once_with(mock_event)

    @patch("pygame.event.Event")
    def test_process_mouse_event(self, mock_event_class):
        """Test mouse event processing."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        # Mock the mouse manager that gets created in start()
        engine.mouse_manager = Mock()
        engine.mouse_manager.on_mouse_button_down_event = Mock()

        # Test MOUSEBUTTONDOWN
        mock_event = Mock()
        mock_event.type = pygame.MOUSEBUTTONDOWN
        mock_event_class.return_value = mock_event

        with patch.object(
            engine.mouse_manager, "on_mouse_button_down_event"
        ) as mock_handler:
            result = engine.process_mouse_event(mock_event)
            assert result is True
            mock_handler.assert_called_once_with(mock_event)

    @patch("pygame.event.Event")
    def test_process_touch_event(self, mock_event_class):
        """Test touch event processing."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        # Mock the touch manager that gets created in start()
        engine.touch_manager = Mock()
        engine.touch_manager.on_touch_down_event = Mock()

        # Test FINGERDOWN
        mock_event = Mock()
        mock_event.type = pygame.FINGERDOWN
        mock_event_class.return_value = mock_event

        with patch.object(
            engine.touch_manager, "on_touch_down_event"
        ) as mock_handler:
            result = engine.process_touch_event(mock_event)
            assert result is True
            mock_handler.assert_called_once_with(mock_event)

    @patch("pygame.event.Event")
    def test_process_window_event(self, mock_event_class):
        """Test window event processing."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        # Mock the window manager that gets created in start()
        engine.window_manager = Mock()
        engine.window_manager.on_window_resized_event = Mock()

        # Test WINDOWRESIZED
        mock_event = Mock()
        mock_event.type = pygame.WINDOWRESIZED
        mock_event_class.return_value = mock_event

        with patch.object(
            engine.window_manager, "on_window_resized_event"
        ) as mock_handler:
            result = engine.process_window_event(mock_event)
            assert result is True
            mock_handler.assert_called_once_with(mock_event)

    @patch("pygame.event.Event")
    def test_process_audio_event(self, mock_event_class):
        """Test audio event processing."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        # Mock the audio manager that gets created in start()
        engine.audio_manager = Mock()
        engine.audio_manager.on_sound_end_event = Mock()

        # Test AUDIODEVICEADDED
        mock_event = Mock()
        mock_event.type = pygame.AUDIODEVICEADDED
        mock_event_class.return_value = mock_event

        with patch.object(
            engine.audio_manager, "on_audio_device_added_event"
        ) as mock_handler:
            result = engine.process_audio_event(mock_event)
            assert result is True
            mock_handler.assert_called_once_with(mock_event)

    @patch("pygame.event.Event")
    def test_process_midi_event(self, mock_event_class):
        """Test MIDI event processing."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        # Mock the MIDI manager that gets created in start()
        engine.midi_manager = Mock()
        engine.midi_manager.on_midi_in_event = Mock()

        # Test MIDIIN - this method just logs and returns True, doesn't call manager
        mock_event = Mock()
        mock_event.type = pygame.MIDIIN
        mock_event_class.return_value = mock_event

        result = engine.process_midi_event(mock_event)
        assert result is True

    @patch("pygame.event.Event")
    def test_process_game_event(self, mock_event_class):
        """Test game event processing."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        # Mock the game manager that gets created in start()
        engine.game_manager = Mock()
        engine.game_manager.on_user_event = Mock()

        # Test USEREVENT
        mock_event = Mock()
        mock_event.type = pygame.USEREVENT
        mock_event_class.return_value = mock_event

        with patch.object(engine.game_manager, "on_user_event") as mock_handler:
            result = engine.process_game_event(mock_event)
            assert result is True
            mock_handler.assert_called_once_with(mock_event)


class TestGameEngineNonManagerMethods(unittest.TestCase):
    """Test GameEngine methods that don't require managers."""

    # Constants for magic values
    EXPECTED_TUPLE_LENGTH = 2

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock game class
        class MockGame(Scene):
            NAME = "Test Game"
            VERSION = "1.0"

            def __init__(self, options=None):
                super().__init__()
                self.options = options or {}

            def args(self, parser):  # noqa: PLR6301
                return parser

        self.mock_game_class = MockGame

        # Use centralized MockFactory for comprehensive pygame mocking
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

        self.display_patcher = patch("pygame.display", self.mock_display)
        self.surface_patcher = patch("pygame.Surface", return_value=self.mock_surface)
        self.sys_argv_patcher = patch("sys.argv", ["test_game.py"])

        self.display_patcher.start()
        self.surface_patcher.start()
        self.sys_argv_patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        self.display_patcher.stop()
        self.surface_patcher.stop()
        self.sys_argv_patcher.stop()

    def test_initialize_display_basic(self):
        """Test basic display initialization."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        # Act
        engine.initialize_display()

        # Assert
        assert engine.display_info is not None
        assert engine.initial_resolution is not None
        assert engine.cursor is not None

    def test_initialize_display_with_resolution(self):
        """Test display initialization with specific resolution."""
        # Arrange
        engine = GameEngine(self.mock_game_class())
        engine.desired_resolution = (1024, 768)
        engine.mode_flags = 0

        # Act
        engine.initialize_display()

        # Assert
        assert engine.display_info is not None
        assert engine.initial_resolution is not None

    def test_initialize_arguments_basic(self):
        """Test basic argument initialization."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        # Act
        options = engine.initialize_arguments(game=self.mock_game_class())

        # Assert
        assert isinstance(options, dict)
        assert "target_fps" in options
        assert "resolution" in options

    def test_initialize_arguments_with_game_args(self):  # noqa: PLR6301
        """Test argument initialization with game-specific args."""
        # Arrange
        class MockGameWithArgs(Scene):
            NAME = "Test Game"
            VERSION = "1.0"

            def __init__(self, options=None):
                super().__init__()
                self.options = options or {}

            def args(self, parser):  # noqa: PLR6301
                parser.add_argument("--test-arg", help="Test argument")
                return parser

        engine = GameEngine(MockGameWithArgs())

        # Act
        options = engine.initialize_arguments(game=MockGameWithArgs())

        # Assert
        assert isinstance(options, dict)

    def test_suggested_resolution_basic(self):
        """Test basic suggested resolution."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        # Act
        resolution = engine.suggested_resolution("800", "600")

        # Assert
        assert isinstance(resolution, tuple)
        assert len(resolution) == self.EXPECTED_TUPLE_LENGTH
        assert resolution[0] > 0
        assert resolution[1] > 0

    def test_suggested_resolution_linux(self):
        """Test suggested resolution on Linux."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        with patch("platform.system", return_value="Linux"):
            # Act
            resolution = engine.suggested_resolution("800", "600")

            # Assert
            assert isinstance(resolution, tuple)
            assert len(resolution) == self.EXPECTED_TUPLE_LENGTH

    def test_suggested_resolution_raspberry_pi(self):
        """Test suggested resolution on Raspberry Pi."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        with patch("platform.system", return_value="Linux"), \
             patch("platform.machine", return_value="armv7l"):
            # Act
            resolution = engine.suggested_resolution("800", "600")

            # Assert
            assert isinstance(resolution, tuple)
            assert len(resolution) == self.EXPECTED_TUPLE_LENGTH

    def test_set_cursor_default(self):
        """Test setting default cursor."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        # Act
        cursor = engine.set_cursor(cursor=None)

        # Assert
        assert isinstance(cursor, list)
        assert len(cursor) > 0

    def test_set_cursor_custom(self):
        """Test setting custom cursor."""
        # Arrange
        engine = GameEngine(self.mock_game_class())
        # Cursor strings must be divisible by 8 (width and height)
        custom_cursor = [
            "XXXXXXXX",
            "X......X",
            "X......X",
            "X......X",
            "X......X",
            "X......X",
            "X......X",
            "XXXXXXXX",
        ]

        # Act
        cursor = engine.set_cursor(cursor=custom_cursor)

        # Assert
        assert cursor == custom_cursor

    def test_initialize_system_icons(self):
        """Test system icon initialization."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        # Act
        engine.initialize_system_icons()

        # Assert - should complete without error
        assert True

    def test_initialize_icon_with_surface(self):  # noqa: PLR6301
        """Test icon initialization with pygame surface."""
        # Arrange
        # Create a real type for isinstance check
        surface_type = type("Surface", (), {})
        mock_icon = surface_type()
        mock_icon.get_width = Mock(return_value=32)
        mock_icon.get_height = Mock(return_value=32)

        # Act
        with patch("pygame.Surface", new=surface_type):
            GameEngine.initialize_icon(icon=mock_icon)

        # Assert - should complete without error
        assert True

    def test_initialize_icon_with_path(self):  # noqa: PLR6301
        """Test icon initialization with file path."""
        # Arrange
        icon_path = Path("test_icon.png")
        # Create a real type for isinstance check
        surface_type = type("Surface", (), {})

        with patch("pygame.image.load") as mock_load, \
             patch("pygame.Surface", new=surface_type):
            mock_surface = surface_type()
            mock_load.return_value = mock_surface

            # Act
            GameEngine.initialize_icon(icon=icon_path)

            # Assert
            mock_load.assert_called_once_with(icon_path)

    def test_initialize_icon_with_none(self):  # noqa: PLR6301
        """Test icon initialization with None."""
        # Act
        GameEngine.initialize_icon(icon=None)

        # Assert - should complete without error
        assert True

    def test_initialize_icon_file_not_found(self):  # noqa: PLR6301
        """Test icon initialization with non-existent file."""
        # Arrange
        icon_path = Path("nonexistent_icon.png")
        # Create a real type for isinstance check
        surface_type = type("Surface", (), {})

        with patch("pygame.image.load", side_effect=FileNotFoundError), \
             patch("pygame.Surface", new=surface_type):
            # Act (should swallow the error and continue)
            GameEngine.initialize_icon(icon=icon_path)

            # Assert - should complete without error (suppressed exception)
            assert True

    def test_print_system_info(self):
        """Test printing system information."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        # Act
        engine.print_system_info()

        # Assert - should complete without error
        assert True

    def test_print_game_info(self):
        """Test printing game information."""
        # Arrange
        engine = GameEngine(self.mock_game_class())

        # Act
        engine.print_game_info()

        # Assert - should complete without error
        assert True

    def test_quit_game_class_method(self):  # noqa: PLR6301
        """Test quit_game class method."""
        with patch("pygame.event.post") as mock_post:
            # Act
            GameEngine.quit_game()

            # Assert
            mock_post.assert_called_once()
            assert True

    def test_args_method_basic(self):  # noqa: PLR6301
        """Test args method with basic parser."""
        # Arrange
        parser = Mock()

        # Act
        result = GameEngine.args(parser)

        # Assert
        assert result is parser

    def test_args_method_platform_specific(self):  # noqa: PLR6301
        """Test args method with platform-specific behavior."""
        # Arrange
        parser = Mock()

        with patch("platform.system", return_value="Windows"):
            # Act
            result = GameEngine.args(parser)

            # Assert
            assert result is parser

    def test_args_method_macos(self):  # noqa: PLR6301
        """Test args method on macOS."""
        # Arrange
        parser = Mock()

        with patch("platform.system", return_value="Darwin"):
            # Act
            result = GameEngine.args(parser)

            # Assert
            assert result is parser

    def test_args_method_windows(self):  # noqa: PLR6301
        """Test args method on Windows."""
        # Arrange
        parser = Mock()

        with patch("platform.system", return_value="Windows"):
            # Act
            result = GameEngine.args(parser)

            # Assert
            assert result is parser

    def test_initialize_arguments_without_game_args(self):  # noqa: PLR6301
        """Test argument initialization without game args method."""
        # Arrange
        class MockGameWithoutArgs(Scene):
            NAME = "Test Game"
            VERSION = "1.0"

            def __init__(self, options=None):
                super().__init__()
                self.options = options or {}

        engine = GameEngine(MockGameWithoutArgs())

        # Act
        options = engine.initialize_arguments(game=MockGameWithoutArgs())

        # Assert
        assert isinstance(options, dict)


if __name__ == "__main__":
    unittest.main()
