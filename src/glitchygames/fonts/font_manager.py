"""Font manager implementation.

This module contains the FontManager class for loading and managing fonts.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
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
    from collections.abc import Callable

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

    def get_metrics(self, text: str, size: float = 0) -> list[tuple[float, ...] | None]:
        """Get each character's metrics (pygame.freetype; the advance is at index 4)."""
        ...

    def metrics(self, text: str) -> list[tuple[int, ...] | None]:
        """Get each character's metrics (pygame.font; the advance is at index 4)."""
        ...


from glitchygames.events import FontEvents, ResourceManager  # ruff: ignore[module-import-not-at-top-of-file]

log = logging.getLogger('game.fonts')
log.addHandler(logging.NullHandler())

# The bundled Bitstream Vera fonts (permissively licensed, see bitstream_vera/COPYRIGHT.TXT).
# This module lives in glitchygames/fonts/, next to bitstream_vera/ (bitmappy.spec bundles it
# at glitchygames/fonts/bitstream_vera for PyInstaller builds).
BUNDLED_FONT_DIRECTORY = Path(__file__).parent / 'bitstream_vera'

# The engine's default font: the bundled Vera, loaded from its file. Loading it never asks
# pygame for system fonts, so it needs no fontconfig scan (which warns when fc-list is missing
# or times out under load) and renders the same on every machine (BUGS.md #156).
DEFAULT_FONT_NAME = 'Vera'

# Bundled font names (lowercase) and their files. A font_name matching one of these (in any
# case) loads the bundled file; any other name is a system font, looked up with SysFont.
BUNDLED_FONT_FILE_NAMES: dict[str, str] = {
    'vera': 'Vera.ttf',
    'verabd': 'VeraBd.ttf',
    'verait': 'VeraIt.ttf',
    'verabi': 'VeraBI.ttf',
}


# The size a font configuration that names none gets
DEFAULT_FONT_SIZE = 14

# pygame.freetype's own default resolution, at which a size in points is a size in pixels.
# pygame.font has no resolution, so a pygame font's size is scaled by font_dpi / BASE_FONT_DPI
# (BUGS.md #210), and both font systems draw the same size at any --font-dpi.
BASE_FONT_DPI = 72

# The style options a font configuration may give, and the values used when neither it nor the
# engine's options (FontManager.OPTIONS) give one. Antialiasing is on, as pygame.freetype's is.
FONT_STYLE_DEFAULTS: dict[str, bool | int] = {
    'font_bold': False,
    'font_italic': False,
    'font_antialias': True,
    'font_dpi': BASE_FONT_DPI,
}


@dataclass(frozen=True)
class FontSettings:
    """Everything a loaded font depends on: its name, size and style.

    Attributes:
        name: The font's name (a bundled font or a system font).
        size: The size in points (pixels at BASE_FONT_DPI).
        bold: Drawn bold (pygame.freetype's strong, pygame.font's set_bold).
        italic: Drawn italic (pygame.freetype's oblique, pygame.font's set_italic).
        antialias: pygame.freetype's antialiased; pygame.font antialiases per render call,
            so its callers pass FontManager.antialias().
        dpi: The resolution sizes are scaled at.

    """

    name: str
    size: int
    bold: bool
    italic: bool
    antialias: bool
    dpi: int

    @property
    def cache_key(self) -> str:
        """The font cache key: two configurations share a font only if all fields match.

        Returns:
            The key (without the font system's prefix).

        """
        return (
            f'{self.name}_{self.size}_bold{int(self.bold)}_italic{int(self.italic)}'
            f'_antialias{int(self.antialias)}_dpi{self.dpi}'
        )

    @property
    def pygame_font_size(self) -> int:
        """The size to give pygame.font, which has no resolution of its own.

        Returns:
            The size scaled by dpi / BASE_FONT_DPI (at least 1).

        """
        return max(1, round(self.size * self.dpi / BASE_FONT_DPI))


def bundled_font_path(*, font_name: str) -> Path | None:
    """Return the file of a bundled font, or None when the name is not a bundled font.

    Args:
        font_name: A font name, in any case (e.g. 'Vera', 'VeraBd').

    Returns:
        The bundled font's file, or None for any other name (a system font).

    """
    file_name = BUNDLED_FONT_FILE_NAMES.get(font_name.lower())
    if file_name is None:
        return None
    return BUNDLED_FONT_DIRECTORY / file_name


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

        # A proxy belongs to its manager: each construction is a new one (ResourceManager)
        SHARES_INSTANCE: ClassVar[bool] = False

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

        # Register pygame.freetype (imported at module top, so always available)
        pygame.freetype.init()
        log.info('Freetype Font Cache Size: %s', pygame.freetype.get_cache_size())
        log.info(
            'Freetype Font Default Resolution: %s',
            pygame.freetype.get_default_resolution(),
        )

        # Set up the default options.
        FontManager.OPTIONS['font_name'] = self.game.OPTIONS['font_name']
        FontManager.OPTIONS['font_size'] = self.game.OPTIONS['font_size']
        # A style option the game's options leave out gets the engine's default (antialiasing
        # on), so options not built by the engine's parser still load fonts
        for style_option, default_value in FONT_STYLE_DEFAULTS.items():
            FontManager.OPTIONS[style_option] = self.game.OPTIONS.get(style_option, default_value)

        # Set font system based on command line argument
        font_system: str = self.game.OPTIONS.get('font_system', 'freetype')
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

        # Set up proxies: the font proxy first, then pygame.freetype
        self.proxies: list[Any] = [FontManager.FontProxy(game=game), pygame.freetype]

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add font options to the argument parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            argparse.ArgumentParser

        """
        group = parser.add_argument_group('Font Options')

        group.add_argument(
            '--font-name',
            default=DEFAULT_FONT_NAME,
            help=(
                f'Font to use (default: the bundled {DEFAULT_FONT_NAME}; the bundled variants are '
                "Vera, VeraBd, VeraIt and VeraBI; any other name is looked up among the system's "
                'fonts)'
            ),
        )
        group.add_argument(
            '--font-size',
            type=int,
            default=14,
            help=(
                'size of the default font, used by text that asks for no font of its own '
                '(default: %(default)s)'
            ),
        )
        # The style options apply to every font the manager loads, unless the font's own
        # configuration gives a value (BUGS.md #210)
        group.add_argument(
            '--font-bold',
            action='store_true',
            default=FONT_STYLE_DEFAULTS['font_bold'],
            help='draw text bold',
        )
        group.add_argument(
            '--font-italic',
            action='store_true',
            default=FONT_STYLE_DEFAULTS['font_italic'],
            help='draw text italic',
        )
        # On by default (pygame.freetype's own default), so --no-font-antialias turns it off
        group.add_argument(
            '--font-antialias',
            action=argparse.BooleanOptionalAction,
            default=FONT_STYLE_DEFAULTS['font_antialias'],
            # Every text the engine, its games and its tools draw follows it, except the
            # channel 3 screen's digit (backgrounds.py), hard-edged on purpose
            help='antialias text (default: %(default)s)',
        )
        group.add_argument(
            '--font-dpi',
            type=int,
            default=FONT_STYLE_DEFAULTS['font_dpi'],
            help=(
                'the resolution, in dots per inch, font sizes are scaled at (a size is in pixels '
                f'at {BASE_FONT_DPI}) (default: %(default)s)'
            ),
        )
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
        settings = cls.font_settings(font_config)
        cache_key = settings.cache_key

        # Check cache first
        if cache_key in FontManager._font_cache:
            return FontManager._font_cache[cache_key]

        log.info('Loading Font: %s', settings.name)
        log.info('Font Size: %s', settings.size)

        # A bundled font loads from its file: no system font scan (BUGS.md #156).
        font_path = bundled_font_path(font_name=settings.name)
        if font_path is not None:
            loaded_font: GameFont = cast(
                'GameFont', _styled_freetype_font(font_path=font_path, settings=settings)
            )
            FontManager._font_cache[cache_key] = loaded_font
            return loaded_font

        try:
            # SysFont picks a bold or italic face when the system has one and asks the
            # constructor to embolden or slant only when it has none
            loaded_font = cast(
                'GameFont',
                pygame.freetype.SysFont(
                    name=settings.name,
                    size=settings.size,
                    bold=settings.bold,
                    italic=settings.italic,
                    constructor=_freetype_font_constructor(settings=settings),
                ),
            )
        except TypeError, FileNotFoundError:
            # Note: Not sure why but pygame.freetype.SysFont doesn't
            # seem to work with pyinstaller packaged games.
            log.info('Loading Font: Built-In')

            # BUG: pygame's documentation claims that passing None as the font name
            # will load the default font, but this raises TypeError ("not a file object")
            # in PyInstaller-packaged games. Load the bundled Vera.ttf instead.
            # (BUNDLED_FONT_DIRECTORY says where bitmappy.spec bundles it.) The fallback keeps
            # the requested size (it used to load at 12 whatever was asked for).
            loaded_font = cast(
                'GameFont',
                _styled_freetype_font(
                    font_path=BUNDLED_FONT_DIRECTORY / BUNDLED_FONT_FILE_NAMES['vera'],
                    settings=settings,
                ),
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
        settings = cls.font_settings(font_config)
        cache_key = f'pygame_{settings.cache_key}'

        # Check cache first
        if cache_key in FontManager._font_cache:
            return FontManager._font_cache[cache_key]

        # A bundled font loads from its file: no system font scan (BUGS.md #156).
        font_path = bundled_font_path(font_name=settings.name)
        if font_path is not None:
            pygame_font = pygame.font.Font(font_path, settings.pygame_font_size)
            pygame_font.set_bold(settings.bold)
            pygame_font.set_italic(settings.italic)
            loaded_font: GameFont = cast('GameFont', pygame_font)
            FontManager._font_cache[cache_key] = loaded_font
            return loaded_font

        try:
            # SysFont picks a bold or italic face when the system has one, and emboldens or
            # slants the font itself when it has none
            loaded_font = cast(
                'GameFont',
                pygame.font.SysFont(
                    settings.name,
                    settings.pygame_font_size,
                    bold=settings.bold,
                    italic=settings.italic,
                ),
            )
        except TypeError, FileNotFoundError:
            # Fall back to default font
            fallback_font = pygame.font.Font(None, settings.pygame_font_size)
            fallback_font.set_bold(settings.bold)
            fallback_font.set_italic(settings.italic)
            loaded_font = cast('GameFont', fallback_font)

        # Cache the result
        FontManager._font_cache[cache_key] = loaded_font
        return loaded_font

    @classmethod
    def antialias(cls) -> bool:
        """Return whether text is antialiased: --font-antialias, on unless turned off.

        pygame.font chooses antialiasing on each render call, so every caller that draws
        with a pygame.font font passes this (freetype fonts carry it themselves). Text that
        must stay hard-edged whatever the setting passes False with a comment saying why.

        Returns:
            The engine's antialias setting (True when no engine has set the options).

        """
        return cls.font_settings().antialias

    @classmethod
    def font_settings(cls, font_config: dict[str, Any] | None = None) -> FontSettings:
        """Return the settings a font configuration asks for, without changing the configuration.

        An empty or missing configuration asks for the engine's default font
        (FontManager.OPTIONS). A name or size the configuration leaves out gets
        DEFAULT_FONT_NAME or DEFAULT_FONT_SIZE; a style option it leaves out gets the engine's
        option, then FONT_STYLE_DEFAULTS, so --font-bold and the rest reach every font.

        Args:
            font_config: The font configuration.

        Returns:
            The font's settings.

        """
        source = font_config or FontManager.OPTIONS

        def option(key: str, *, default: bool | int) -> bool | int:
            for options in (source, FontManager.OPTIONS):
                value = options.get(key)
                if value is not None:
                    return value
            return default

        return FontSettings(
            name=source.get('font_name') or DEFAULT_FONT_NAME,
            size=source.get('font_size') or DEFAULT_FONT_SIZE,
            bold=bool(option('font_bold', default=FONT_STYLE_DEFAULTS['font_bold'])),
            italic=bool(option('font_italic', default=FONT_STYLE_DEFAULTS['font_italic'])),
            antialias=bool(option('font_antialias', default=FONT_STYLE_DEFAULTS['font_antialias'])),
            dpi=int(option('font_dpi', default=FONT_STYLE_DEFAULTS['font_dpi'])),
        )

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

        # Get pygame.font. Its render takes (text, antialias, color) positionally, not
        # freetype's fgcolor keyword (which raised TypeError on a real pygame.font.Font).
        pygame_font = cast('pygame.font.Font', cls.get_font('pygame', config))
        pygame_surface: pygame.Surface = pygame_font.render(text, cls.antialias(), (255, 255, 255))

        # Get pygame.freetype
        freetype_font = cls.get_font('freetype', config)
        freetype_render_result = freetype_font.render(text, fgcolor=(255, 255, 255))
        freetype_surface: pygame.Surface = (
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


def _styled_freetype_font(
    *, font_path: Path | str | None, settings: FontSettings
) -> pygame.freetype.Font:
    """Return a freetype font from a file, at the settings' size, resolution and style.

    Args:
        font_path: The font file (None: pygame's own default font).
        settings: The font's settings.

    Returns:
        The font.

    """
    freetype_font = pygame.freetype.Font(
        file=font_path, size=settings.size, resolution=settings.dpi
    )
    freetype_font.strong = settings.bold
    freetype_font.oblique = settings.italic
    freetype_font.antialiased = settings.antialias
    return freetype_font


def _freetype_font_constructor(*, settings: FontSettings) -> Callable[..., pygame.freetype.Font]:
    """Return a constructor for pygame.freetype.SysFont that keeps the settings' resolution.

    SysFont calls it with the matched file, the size and whether it must embolden or slant
    (False when it found a bold or italic face; pygame's sysfont.SysFont).

    Args:
        settings: The font's settings.

    Returns:
        The constructor.

    """

    def construct(
        font_path: str | None,
        size: int,
        # SysFont calls it positionally
        bold: bool,  # ruff: ignore[boolean-type-hint-positional-argument]
        italic: bool,  # ruff: ignore[boolean-type-hint-positional-argument]
    ) -> pygame.freetype.Font:
        freetype_font = pygame.freetype.Font(file=font_path, size=size, resolution=settings.dpi)
        freetype_font.strong = bold
        freetype_font.oblique = italic
        freetype_font.antialiased = settings.antialias
        return freetype_font

    return construct
