"""Tests for font event functionality.

This module tests font event interfaces, stubs, and event handling through a real
FontManager, and the FontManager's font loading with real pygame fonts.
"""

import argparse
from pathlib import Path

import pygame
import pygame.freetype
import pytest

from glitchygames.events import (
    FontEvents,
    HashableEvent,
    UnhandledEventError,
)
from glitchygames.fonts import FontManager
from glitchygames.scenes import Scene
from tests.harness import imported_engine_directory

# The imported engine's directory (installed: never the source tree by accident)
ENGINE_PACKAGE_DIRECTORY = imported_engine_directory()

EVENT_TEST_OPTIONS = {'debug_events': False, 'no_unhandled_events': True}

# The bundled font the system-font tests hand back in place of a system lookup
BUNDLED_VERA_PATH = ENGINE_PACKAGE_DIRECTORY / 'fonts' / 'bitstream_vera' / 'Vera.ttf'

FONT_OPTIONS = {
    'font_name': 'arial',
    'font_size': 14,
    'font_bold': False,
    'font_italic': False,
    'font_antialias': True,
    'font_dpi': 72,
    'font_system': 'freetype',
}


class FontRecordingScene(Scene):
    """A real scene with font options that records the font events it receives."""

    def __init__(self, options=None, groups=None):
        """Create the scene with the font options and no font events received yet."""
        super().__init__(
            options=options if options is not None else dict(EVENT_TEST_OPTIONS),
            groups=groups,
        )
        # FontManager reads the game's font options from OPTIONS
        self.OPTIONS = dict(FONT_OPTIONS)
        self.font_events_received: list[tuple[str, HashableEvent]] = []

    def on_font_changed_event(self, event):
        """Record a font changed event."""
        self.font_events_received.append(('font_changed', event))


class SceneWithoutFontHandler(Scene):
    """A real scene with font options but no font handler: the font stub handles events."""

    def __init__(self, options=None, groups=None):
        """Create the scene with the font options."""
        super().__init__(
            options=options if options is not None else dict(EVENT_TEST_OPTIONS),
            groups=groups,
        )
        self.OPTIONS = dict(FONT_OPTIONS)


def font_scene_and_manager():
    """Create a recording scene and a real FontManager delivering to it.

    Returns:
        tuple[FontRecordingScene, FontManager]: The scene and its manager.

    """
    scene = FontRecordingScene()
    return scene, FontManager(game=scene)


def bundled_freetype_font(*, size):
    """Load the bundled Vera with pygame.freetype.

    A system-font lookup (SysFont) depends on the machine's fonts and scans them, so the
    tests of the system-font path hand back this real font in its place.

    Returns:
        pygame.freetype.Font: The bundled Vera at the size.

    """
    return pygame.freetype.Font(file=BUNDLED_VERA_PATH, size=size)


def bundled_pygame_font(*, size):
    """Load the bundled Vera with pygame.font (see bundled_freetype_font).

    Returns:
        pygame.font.Font: The bundled Vera at the size.

    """
    return pygame.font.Font(BUNDLED_VERA_PATH, size)


class TestFontEvents:
    """Test FontEvents interface functionality."""

    def test_font_events_interface(self):
        """Test FontEvents interface methods."""
        # Test that FontEvents has required abstract methods
        assert hasattr(FontEvents, 'on_font_changed_event')

    def test_font_event_stubs_implementation(self, mocker):
        """Test FontEventStubs implementation."""
        # A real scene without a font handler falls back to the font stub
        manager = FontManager(game=SceneWithoutFontHandler())

        event = HashableEvent(pygame.USEREVENT + 1)
        # Silence the "Unhandled Event" log during testing
        mocker.patch('glitchygames.events.base.LOG.error')

        with pytest.raises(UnhandledEventError):
            manager.on_font_changed_event(event)
        # Expected to call unhandled_event and raise UnhandledEventError

    def test_font_changed_event(self):
        """Test font changed event handling."""
        scene, manager = font_scene_and_manager()

        # Test font changed event
        event = HashableEvent(pygame.USEREVENT + 1)  # Custom font change event
        manager.on_font_changed_event(event)

        assert len(scene.font_events_received) == 1
        assert scene.font_events_received[0][0] == 'font_changed'
        assert scene.font_events_received[0][1].type == pygame.USEREVENT + 1

    def test_font_changed_event_with_font_info(self):
        """Test font changed event with font information."""
        scene, manager = font_scene_and_manager()

        # Test font changed event with font information
        event = HashableEvent(pygame.USEREVENT + 1, font_name='Arial', font_size=12)
        manager.on_font_changed_event(event)

        assert len(scene.font_events_received) == 1
        assert scene.font_events_received[0][0] == 'font_changed'
        assert scene.font_events_received[0][1].type == pygame.USEREVENT + 1
        assert scene.font_events_received[0][1].font_name == 'Arial'
        assert scene.font_events_received[0][1].font_size == 12

    def test_font_changed_event_with_different_fonts(self):
        """Test font changed event with different font types."""
        scene, manager = font_scene_and_manager()

        # Test different font types
        font_scenarios = [
            {'font_name': 'Arial', 'font_size': 12},
            {'font_name': 'Times New Roman', 'font_size': 14},
            {'font_name': 'Courier New', 'font_size': 10},
            {'font_name': 'Helvetica', 'font_size': 16},
            {'font_name': 'Verdana', 'font_size': 18},
            {'font_name': 'Georgia', 'font_size': 20},
        ]

        for font_info in font_scenarios:
            event = HashableEvent(pygame.USEREVENT + 1, **font_info)
            manager.on_font_changed_event(event)

            assert len(scene.font_events_received) == 1
            assert scene.font_events_received[0][0] == 'font_changed'
            assert scene.font_events_received[0][1].type == pygame.USEREVENT + 1
            assert scene.font_events_received[0][1].font_name == font_info['font_name']
            assert scene.font_events_received[0][1].font_size == font_info['font_size']

            # Clear for next iteration
            scene.font_events_received.clear()

    def test_font_changed_event_with_different_sizes(self):
        """Test font changed event with different font sizes."""
        scene, manager = font_scene_and_manager()

        # Test different font sizes
        font_sizes = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 72]

        for size in font_sizes:
            event = HashableEvent(pygame.USEREVENT + 1, font_name='Arial', font_size=size)
            manager.on_font_changed_event(event)

            assert len(scene.font_events_received) == 1
            assert scene.font_events_received[0][0] == 'font_changed'
            assert scene.font_events_received[0][1].type == pygame.USEREVENT + 1
            assert scene.font_events_received[0][1].font_name == 'Arial'
            assert scene.font_events_received[0][1].font_size == size

            # Clear for next iteration
            scene.font_events_received.clear()

    def test_font_changed_event_with_style_info(self):
        """Test font changed event with style information."""
        scene, manager = font_scene_and_manager()

        # Test font changed event with style information
        style_scenarios = [
            {'font_name': 'Arial', 'font_size': 12, 'bold': True, 'italic': False},
            {'font_name': 'Arial', 'font_size': 12, 'bold': False, 'italic': True},
            {'font_name': 'Arial', 'font_size': 12, 'bold': True, 'italic': True},
            {'font_name': 'Arial', 'font_size': 12, 'bold': False, 'italic': False},
        ]

        for style_info in style_scenarios:
            event = HashableEvent(pygame.USEREVENT + 1, **style_info)
            manager.on_font_changed_event(event)

            assert len(scene.font_events_received) == 1
            assert scene.font_events_received[0][0] == 'font_changed'
            assert scene.font_events_received[0][1].type == pygame.USEREVENT + 1
            assert scene.font_events_received[0][1].font_name == style_info['font_name']
            assert scene.font_events_received[0][1].font_size == style_info['font_size']

            # Clear for next iteration
            scene.font_events_received.clear()

    def test_font_changed_event_with_color_info(self):
        """Test font changed event with color information."""
        scene, manager = font_scene_and_manager()

        # Test font changed event with color information
        color_scenarios = [
            {'font_name': 'Arial', 'font_size': 12, 'color': (255, 0, 0)},  # Red
            {'font_name': 'Arial', 'font_size': 12, 'color': (0, 255, 0)},  # Green
            {'font_name': 'Arial', 'font_size': 12, 'color': (0, 0, 255)},  # Blue
            {'font_name': 'Arial', 'font_size': 12, 'color': (255, 255, 255)},  # White
            {'font_name': 'Arial', 'font_size': 12, 'color': (0, 0, 0)},  # Black
        ]

        for color_info in color_scenarios:
            event = HashableEvent(pygame.USEREVENT + 1, **color_info)
            manager.on_font_changed_event(event)

            assert len(scene.font_events_received) == 1
            assert scene.font_events_received[0][0] == 'font_changed'
            assert scene.font_events_received[0][1].type == pygame.USEREVENT + 1
            assert scene.font_events_received[0][1].font_name == color_info['font_name']
            assert scene.font_events_received[0][1].font_size == color_info['font_size']

            # Clear for next iteration
            scene.font_events_received.clear()

    def test_font_changed_event_with_unicode_fonts(self):
        """Test font changed event with Unicode font names."""
        scene, manager = font_scene_and_manager()

        # Test Unicode font names
        unicode_fonts = [
            '宋体',  # Chinese font
            'メイリオ',  # Japanese font
            '맑은 고딕',  # Korean font
            'Times New Roman',  # English font
            'Arial Unicode MS',  # Unicode font
        ]

        for font_name in unicode_fonts:
            event = HashableEvent(pygame.USEREVENT + 1, font_name=font_name, font_size=12)
            manager.on_font_changed_event(event)

            assert len(scene.font_events_received) == 1
            assert scene.font_events_received[0][0] == 'font_changed'
            assert scene.font_events_received[0][1].type == pygame.USEREVENT + 1
            assert scene.font_events_received[0][1].font_name == font_name
            assert scene.font_events_received[0][1].font_size == 12

            # Clear for next iteration
            scene.font_events_received.clear()

    def test_font_changed_event_with_system_fonts(self):
        """Test font changed event with system fonts."""
        scene, manager = font_scene_and_manager()

        # Test system fonts
        system_fonts = [
            'system',  # System default
            'monospace',  # Monospace font
            'serif',  # Serif font
            'sans-serif',  # Sans-serif font
            'cursive',  # Cursive font
            'fantasy',  # Fantasy font
        ]

        for font_name in system_fonts:
            event = HashableEvent(pygame.USEREVENT + 1, font_name=font_name, font_size=12)
            manager.on_font_changed_event(event)

            assert len(scene.font_events_received) == 1
            assert scene.font_events_received[0][0] == 'font_changed'
            assert scene.font_events_received[0][1].type == pygame.USEREVENT + 1
            assert scene.font_events_received[0][1].font_name == font_name
            assert scene.font_events_received[0][1].font_size == 12

            # Clear for next iteration
            scene.font_events_received.clear()

    def test_font_changed_event_with_font_path(self):
        """Test font changed event with font file paths."""
        scene, manager = font_scene_and_manager()

        # Test font file paths
        font_paths = [
            '/System/Library/Fonts/Arial.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            'C:\\Windows\\Fonts\\arial.ttf',
            '/home/user/.fonts/custom-font.otf',
        ]

        for font_path in font_paths:
            event = HashableEvent(pygame.USEREVENT + 1, font_path=font_path, font_size=12)
            manager.on_font_changed_event(event)

            assert len(scene.font_events_received) == 1
            assert scene.font_events_received[0][0] == 'font_changed'
            assert scene.font_events_received[0][1].type == pygame.USEREVENT + 1
            assert scene.font_events_received[0][1].font_path == font_path
            assert scene.font_events_received[0][1].font_size == 12

            # Clear for next iteration
            scene.font_events_received.clear()


def cache_key(*, font_name: str, font_size: int) -> str:
    """Return the freetype cache key of a font with the engine's default style.

    Args:
        font_name: The font's name.
        font_size: The font's size.

    Returns:
        The key (a pygame.font font's is this with a 'pygame_' prefix).

    """
    return FontManager.font_settings({'font_name': font_name, 'font_size': font_size}).cache_key


class TestFontManagerCoverage:
    """Test coverage for FontManager class."""

    @pytest.fixture(autouse=True)
    def setup_font_manager(self):
        """Give each test a game with font options and an empty font cache."""
        self.game = FontRecordingScene()

        FontManager._font_cache.clear()
        FontManager.OPTIONS.clear()

    def test_font_manager_initialization_basic(self):
        """Test FontManager initializes correctly."""
        manager = FontManager(game=self.game)

        assert manager.game is self.game
        assert manager.proxies[1] is pygame.freetype
        assert isinstance(manager.proxies[0], FontManager.FontProxy)

    def test_font_manager_with_fallback(self, mocker):
        """A freetype font that fails to load falls back to a pygame.font font."""
        FontManager(game=self.game)
        # A broken font file cannot be produced portably: simulate freetype failing to load
        mocker.patch('pygame.freetype.Font', side_effect=OSError('unreadable font file'))

        font = FontManager.get_font(font_system='freetype', font_config={'font_name': 'Vera'})

        assert isinstance(font, pygame.font.Font)
        assert 'pygame_' + cache_key(font_name='Vera', font_size=14) in FontManager._font_cache

    def test_font_manager_initialization(self):
        """Test FontManager initialization."""
        expected_font_size = 14

        FontManager(self.game)

        assert pygame.freetype.get_init()
        assert pygame.freetype.get_default_resolution() == 72
        assert FontManager.OPTIONS['font_name'] == 'arial'
        assert FontManager.OPTIONS['font_size'] == expected_font_size
        assert FontManager.OPTIONS['use_freetype'] is True

    def test_font_proxy_initialization(self):
        """Test FontProxy initialization."""

        # Create a concrete subclass that implements the abstract method
        class ConcreteFontProxy(FontManager.FontProxy):
            def on_font_changed_event(self, event):
                pass

        FontManager(self.game)
        proxy = ConcreteFontProxy(self.game)

        assert proxy.game is self.game
        assert pygame.freetype in proxy.proxies  # ty: ignore[possibly-missing-submodule]

    def test_font_method_freetype_success(self, mocker):
        """Test font method with successful freetype loading."""
        system_font = bundled_freetype_font(size=16)
        system_font_lookup = mocker.patch('pygame.freetype.SysFont', return_value=system_font)

        font_config = {'font_name': 'arial', 'font_size': 16}
        result = FontManager.font(font_config)

        system_font_lookup.assert_called_once()
        lookup_arguments = system_font_lookup.call_args.kwargs
        assert (lookup_arguments['name'], lookup_arguments['size']) == ('arial', 16)
        assert (lookup_arguments['bold'], lookup_arguments['italic']) == (False, False)
        assert result is system_font
        assert FontManager._font_cache[cache_key(font_name='arial', font_size=16)] is system_font

    def test_font_method_freetype_fallback(self, mocker):
        """Test font method with freetype fallback to the bundled font."""
        # A missing system font cannot be produced portably: simulate SysFont failing
        mocker.patch('pygame.freetype.SysFont', side_effect=TypeError('Font not found'))

        font_config = {'font_name': 'arial', 'font_size': 16}
        result = FontManager.font(font_config)

        assert isinstance(result, pygame.freetype.Font)
        assert Path(result.path).name == 'Vera.ttf'
        assert FontManager._font_cache[cache_key(font_name='arial', font_size=16)] is result

    def test_pygame_font_method_success(self, mocker):
        """Test pygame_font method with successful system font loading."""
        system_font = bundled_pygame_font(size=16)
        system_font_lookup = mocker.patch('pygame.font.SysFont', return_value=system_font)

        font_config = {'font_name': 'arial', 'font_size': 16}
        result = FontManager.pygame_font(font_config)

        system_font_lookup.assert_called_once_with('arial', 16, bold=False, italic=False)
        assert result is system_font
        assert (
            FontManager._font_cache['pygame_' + cache_key(font_name='arial', font_size=16)]
            is system_font
        )

    def test_pygame_font_method_fallback(self, mocker):
        """Test pygame_font method with fallback to pygame's default font."""
        # A missing system font cannot be produced portably: simulate SysFont failing
        system_font_lookup = mocker.patch(
            'pygame.font.SysFont', side_effect=FileNotFoundError('Font not found')
        )

        font_config = {'font_name': 'arial', 'font_size': 16}
        result = FontManager.pygame_font(font_config)

        system_font_lookup.assert_called_once_with('arial', 16, bold=False, italic=False)
        assert isinstance(result, pygame.font.Font)
        # pygame's default font at the requested size
        assert result.get_height() == pygame.font.Font(None, 16).get_height()

    def test_pygame_font_method_default_config(self, mocker):
        """Test pygame_font method with default configuration."""
        FontManager.OPTIONS = {'font_name': 'arial', 'font_size': 16}

        system_font = bundled_pygame_font(size=16)
        system_font_lookup = mocker.patch('pygame.font.SysFont', return_value=system_font)

        result = FontManager.pygame_font(None)

        system_font_lookup.assert_called_once_with('arial', 16, bold=False, italic=False)
        assert result is system_font
        assert 'pygame_' + cache_key(font_name='arial', font_size=16) in FontManager._font_cache

    def test_args_method(self):
        """Test args class method."""
        parser = argparse.ArgumentParser()
        result = FontManager.args(parser)

        assert result is parser
        # Check that the Font Options group was added
        group_titles = [group.title for group in parser._action_groups]
        assert 'Font Options' in group_titles

    def test_font_method_with_default_config(self, mocker):
        """Test font method with default configuration."""
        FontManager.OPTIONS = {'font_name': 'arial', 'font_size': 16}

        system_font = bundled_freetype_font(size=16)
        mocker.patch('pygame.freetype.SysFont', return_value=system_font)

        result = FontManager.font()

        assert result is system_font
        assert cache_key(font_name='arial', font_size=16) in FontManager._font_cache

    def test_font_method_with_partial_config(self, mocker):
        """Test font method with partial configuration."""
        FontManager.OPTIONS = {'font_name': 'arial', 'font_size': 16}

        system_font = bundled_freetype_font(size=14)
        mocker.patch('pygame.freetype.SysFont', return_value=system_font)

        # Test with partial config (missing font_size)
        result = FontManager.font({'font_name': 'times'})

        assert result is system_font
        # The hard-coded default size, 14
        assert cache_key(font_name='times', font_size=14) in FontManager._font_cache

    def test_font_method_with_missing_font_name_config(self):
        """A config without a font name loads the default font, the bundled Vera (BUGS.md #156)."""
        FontManager.OPTIONS = {'font_name': 'arial', 'font_size': 16}

        # Test with config missing font_name: the hard-coded default name, not OPTIONS'
        result = FontManager.font({'font_size': 20})

        assert isinstance(result, pygame.freetype.Font)
        assert Path(result.path).name == 'Vera.ttf'
        assert result.size == 20
        assert FontManager._font_cache[cache_key(font_name='Vera', font_size=20)] is result

    def test_font_method_cache_hit(self):
        """Test font method cache hit behavior."""
        cached_font = bundled_freetype_font(size=14)
        FontManager._font_cache[cache_key(font_name='arial', font_size=14)] = cached_font

        config = {'font_name': 'arial', 'font_size': 14}

        result = FontManager.font(config)

        assert result is cached_font
