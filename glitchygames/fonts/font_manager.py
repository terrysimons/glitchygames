"""Font manager implementation.

This module contains the FontManager class for loading and managing fonts.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Literal,
    Protocol,
    Self,
    cast,
    override,
    runtime_checkable,
)

if TYPE_CHECKING:
    import argparse

    from glitchygames.events.base import HashableEvent

import pygame
import pygame.freetype


@runtime_checkable
class GameFont(Protocol):
    """Protocol describing the font interface used throughout GlitchyGames.

    Both pygame.font.Font and pygame.freetype.Font satisfy this protocol.
    """

    def render(
        self,
        text: str,
        fgcolor: tuple[int, ...] = ...,
        bgcolor: tuple[int, ...] | None = None,
        **kwargs: Any,
    ) -> pygame.Surface | tuple[pygame.Surface, pygame.Rect]:
        """Render text to a surface."""
        ...

    def render_to(
        self,
        surf: pygame.Surface,
        dest: tuple[int, int],
        text: str,
        fgcolor: tuple[int, ...] = ...,
        **kwargs: Any,
    ) -> pygame.Rect:
        """Render text directly onto a surface."""
        ...

    def get_rect(self, text: str, **kwargs: Any) -> pygame.Rect:
        """Get the bounding rectangle for rendered text."""
        ...

    def get_linesize(self) -> int:
        """Get the line height for the font."""
        ...

    def size(self, text: str) -> tuple[int, int]:
        """Get the size of rendered text."""
        ...


from glitchygames.events import FontEvents, ResourceManager  # noqa: E402

log = logging.getLogger('game.fonts')
log.addHandler(logging.NullHandler())


class FontManager(ResourceManager):
    """A font manager for handling fonts in the game.

    Supports both pygame.font and pygame.freetype font systems:

    Examples:
        # Use default font system (pygame.font)
        font = FontManager.get_font()

        # Force pygame.font
        font = FontManager.get_font(use_freetype=False)

        # Force pygame.freetype
        font = FontManager.get_font(use_freetype=True)

        # Change default system
        FontManager.set_font_system(use_freetype=True)
        font = FontManager.get_font()  # Now uses freetype by default

        # Check current system
        system = FontManager.get_font_system()  # Returns "pygame" or "freetype"

    """

    OPTIONS: ClassVar[dict[str, Any]] = {}
    RENDER_CACHE: ClassVar[dict[str, Any]] = {}
    _font_cache: ClassVar[dict[str, GameFont]] = {}

    class FontProxy(FontEvents, ResourceManager):
        """A font proxy."""

        def __init__(self: Self, game: object = None) -> None:
            """Initialize the font proxy.

            Args:
                game (object): The game object.

            """
            super().__init__(game=game)
            self.game: Any = game
            self.proxies: list[Any] = [self.game, pygame.freetype]

        @override
        def on_font_changed_event(self: Self, event: HashableEvent) -> None:
            """Handle font changed event.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            self.game.on_font_changed_event(event)

    def __init__(self: Self, game: object = None) -> None:
        """Initialize the font manager.

        Args:
            game (object): The game object.

        """
        super().__init__(game=game)
        self.game: Any = game

        # Register pygame.freetype if available
        try:
            pygame.freetype.init()
            log.info(f'Freetype Font Cache Size: {pygame.freetype.get_cache_size()}')
            log.info(
                f'Freetype Font Default Resolution: {pygame.freetype.get_default_resolution()}',
            )
        except AttributeError:
            log.warning('pygame.freetype not available, using pygame.font instead')
            pygame.font.init()

        # Set up the default options.
        FontManager.OPTIONS['font_name'] = self.game.OPTIONS['font_name']  # ty: ignore[unresolved-attribute]
        FontManager.OPTIONS['font_size'] = self.game.OPTIONS['font_size']  # ty: ignore[unresolved-attribute]
        FontManager.OPTIONS['font_bold'] = self.game.OPTIONS['font_bold']  # ty: ignore[unresolved-attribute]
        FontManager.OPTIONS['font_italic'] = self.game.OPTIONS['font_italic']  # ty: ignore[unresolved-attribute]
        FontManager.OPTIONS['font_antialias'] = self.game.OPTIONS['font_antialias']  # ty: ignore[unresolved-attribute]
        FontManager.OPTIONS['font_dpi'] = self.game.OPTIONS['font_dpi']  # ty: ignore[unresolved-attribute]

        # Set font system based on command line argument
        font_system: str = self.game.OPTIONS.get('font_system', 'freetype')  # ty: ignore[unresolved-attribute]
        FontManager.OPTIONS['use_freetype'] = font_system == 'freetype'
        log.info('Font system initialized: %s', font_system)

        pygame.freetype.set_default_resolution(FontManager.OPTIONS['font_dpi'])

        # Ideas:
        #
        # Pre-generate font cache based on settings that are provided.
        # Indexed by the letter they represent.
        # a -> <font name>
        # What about bold, italic, bold + italic, anti-aliased?
        # Maybe we can generate all combinations?
        # Allow caller to pass in a font settings blob and generate.
        # A progress bar class that integrates with tqdm?

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

        # Set up proxies based on available font system
        try:
            self.proxies: list[Any] = [FontManager.FontProxy(game=game), pygame.freetype]
        except AttributeError:
            # Fallback to pygame.font if freetype is not available
            self.proxies = [FontManager.FontProxy(game=game), pygame.font]

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add font options to the argument parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            argparse.ArgumentParser

        """
        group = parser.add_argument_group('Font Options')

        group.add_argument('--font-name', default='arial')
        group.add_argument('--font-size', type=int, default=14)
        group.add_argument('--font-bold', action='store_true', default=False)
        group.add_argument('--font-italic', action='store_true', default=False)
        group.add_argument('--font-antialias', action='store_true', default=False)
        group.add_argument('--font-dpi', type=int, default=72)
        group.add_argument(
            '--font-system',
            choices=['pygame', 'freetype'],
            default='freetype',
            help='Font system to use: freetype (enhanced, default) or pygame (built-in)',
        )

        return parser

    # PyInstaller-compiled games fall back to the bundled Vera.ttf font
    # since system font paths are not available in frozen environments.
    @classmethod
    def font(cls, font_config: dict[str, Any] | None = None) -> GameFont:
        """Return a font object.

        If the font requested can't be found then bitstream_vera will be loaded instead.

        Note that if you are trying to package your game with pyinstaller, you'll need to bundle
        your game's fonts with the pyinstaller invocation.  Make sure you have distribution
        rights to the fonts you're including with your game.

        bitstream_vera is a permissively licensed font that can be used with your game.

        Args:
            font_config (dict | None): The font configuration.

        Returns:
            GameFont

        """
        if not font_config:
            font_config = FontManager.OPTIONS

        # Provide default font configuration if not set
        if 'font_name' not in font_config:
            font_config['font_name'] = 'arial'
        if 'font_size' not in font_config:
            font_config['font_size'] = 14

        # Create cache key
        cache_key = f'{font_config["font_name"]}_{font_config["font_size"]}'

        # Check cache first
        if cache_key in FontManager._font_cache:
            return FontManager._font_cache[cache_key]

        log.info(f'Loading Font: {font_config["font_name"]}')
        log.info(f'Font Size: {font_config["font_size"]}')

        try:
            loaded_font: GameFont = cast(
                'GameFont',
                pygame.freetype.SysFont(
                    name=font_config['font_name'],
                    size=font_config['font_size'],
                ),
            )
        except TypeError, FileNotFoundError:
            # Note: Not sure why but pygame.freetype.SysFont doesn't
            # seem to work with pyinstaller packaged games.
            log.info('Loading Font: Built-In')

            # BUG: pygame's documentation claims that passing None as the font name
            # will load the default font, but this raises TypeError ("not a file object")
            # in PyInstaller-packaged games. Load the bundled Vera.ttf instead.
            font_path = Path(__file__).parent / 'fonts' / 'bitstream_vera' / 'Vera.ttf'
            loaded_font = cast(
                'GameFont',
                pygame.freetype.Font(file=font_path, size=12),
            )

        # Cache the result
        FontManager._font_cache[cache_key] = loaded_font
        return loaded_font

    @classmethod
    def pygame_font(cls, font_config: dict[str, Any] | None = None) -> GameFont:
        """Return a regular pygame font object for compatibility with UI components.

        Args:
            font_config (dict | None): The font configuration.

        Returns:
            GameFont: A regular pygame font object.

        """
        if not font_config:
            font_config = FontManager.OPTIONS

        # Provide default font configuration if not set
        if 'font_name' not in font_config:
            font_config['font_name'] = 'arial'
        if 'font_size' not in font_config:
            font_config['font_size'] = 14

        # Create cache key for pygame fonts
        cache_key = f'pygame_{font_config["font_name"]}_{font_config["font_size"]}'

        # Check cache first
        if cache_key in FontManager._font_cache:
            return FontManager._font_cache[cache_key]

        try:
            # Try to load system font
            loaded_font: GameFont = cast(
                'GameFont',
                pygame.font.SysFont(font_config['font_name'], font_config['font_size']),
            )
        except TypeError, FileNotFoundError:
            # Fall back to default font
            loaded_font = cast('GameFont', pygame.font.Font(None, font_config['font_size']))

        # Cache the result
        FontManager._font_cache[cache_key] = loaded_font
        return loaded_font

    @classmethod
    def get_font(
        cls,
        font_system: Literal['pygame', 'freetype'] | None = None,
        font_config: dict[str, Any] | None = None,
    ) -> GameFont:
        """Get a font object, choosing between pygame.font and pygame.freetype.

        Args:
            font_system: Either "pygame" or "freetype". If None, use the default preference.
            font_config: The font configuration.

        Returns:
            pygame.font.Font | pygame.freetype.Font: The requested font object.

        """
        if font_system is None:
            # Default to freetype
            use_freetype: bool = bool(FontManager.OPTIONS.get('use_freetype', True))
        else:
            use_freetype = font_system == 'freetype'

        # Try freetype first, fall back to pygame if it fails
        if use_freetype:
            try:
                return cls.font(font_config)
            except (TypeError, FileNotFoundError, OSError) as e:
                log.info('Freetype font failed, falling back to pygame: %s', e)
                return cls.pygame_font(font_config)
        else:
            return cls.pygame_font(font_config)

    @classmethod
    def set_font_system(cls, font_system: Literal['pygame', 'freetype']) -> None:
        """Set the default font system preference.

        Args:
            font_system: Either "pygame" or "freetype" to specify the font system.

        """
        FontManager.OPTIONS['use_freetype'] = font_system == 'freetype'
        log.info('Font system set to: %s', font_system)

    @classmethod
    def get_font_system(cls) -> str:
        """Get the current font system preference.

        Returns:
            str: "freetype" or "pygame" indicating the current font system.

        """
        return 'freetype' if FontManager.OPTIONS.get('use_freetype', False) else 'pygame'

    @classmethod
    def compare_font_systems(
        cls,
        text: str = 'Hello World',
        size: int = 24,
    ) -> dict[str, dict[str, Any]]:
        """Compare both font systems side by side.

        Args:
            text (str): Text to render for comparison.
            size (int): Font size for comparison.

        Returns:
            dict: Information about both font systems.

        """
        config: dict[str, Any] = {'font_size': size}

        # Get pygame.font
        pygame_font = cls.get_font('pygame', config)
        pygame_render_result = pygame_font.render(text, fgcolor=(255, 255, 255))
        pygame_surface: pygame.Surface = (  # ty: ignore[invalid-assignment]
            pygame_render_result[0]
            if isinstance(pygame_render_result, tuple)
            else pygame_render_result
        )

        # Get pygame.freetype
        freetype_font = cls.get_font('freetype', config)
        freetype_render_result = freetype_font.render(text, fgcolor=(255, 255, 255))
        freetype_surface: pygame.Surface = (  # ty: ignore[invalid-assignment]
            freetype_render_result[0]
            if isinstance(freetype_render_result, tuple)
            else freetype_render_result
        )

        return {
            'pygame': {
                'font': pygame_font,
                'surface': pygame_surface,
                'size': pygame_surface.get_size(),
                'type': 'pygame.font.Font',
            },
            'freetype': {
                'font': freetype_font,
                'surface': freetype_surface,
                'size': freetype_surface.get_size(),
                'type': 'pygame.freetype.Font',
            },
        }
