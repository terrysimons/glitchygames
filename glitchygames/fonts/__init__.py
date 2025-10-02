#!/usr/bin/env python3
"""Fonts.

This is a simple font manager that can be used to load fonts.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Self, Dict, Any

if TYPE_CHECKING:
    import argparse

import pygame
from glitchygames.events import FontEvents, ResourceManager

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

    OPTIONS: ClassVar = {}
    RENDER_CACHE: ClassVar = {}

    class FontProxy(FontEvents, ResourceManager):
        """A font proxy."""

        def __init__(self: Self, game: object = None) -> None:
            """Initialize the font proxy.

            Args:
                game (object): The game object.

            Returns:
                None
            """
            super().__init__(game=game)
            self.game = game
            self.proxies = [self.game, pygame.freetype]

    def __init__(self: Self, game: object = None) -> None:
        """Initialize the font manager.

        Args:
            game (object): The game object.

        Returns:
            None
        """
        super().__init__(game=game)

        # Register pygame.freetype
        pygame.freetype.init()
        # pygame.font.init()
        # pygame.ftfont.init()

        log.info('Freetype Font Cache Size: ' f'{pygame.freetype.get_cache_size()}')
        log.info('Freetype Font Default Resolution: ' f'{pygame.freetype.get_default_resolution()}')

        # Set up the default options.
        FontManager.OPTIONS['font_name'] = game.OPTIONS['font_name']
        FontManager.OPTIONS['font_size'] = game.OPTIONS['font_size']
        FontManager.OPTIONS['font_bold'] = game.OPTIONS['font_bold']
        FontManager.OPTIONS['font_italic'] = game.OPTIONS['font_italic']
        FontManager.OPTIONS['font_antialias'] = game.OPTIONS['font_antialias']
        FontManager.OPTIONS['font_dpi'] = game.OPTIONS['font_dpi']
        
        # Set font system based on command line argument
        font_system = game.OPTIONS.get('font_system', 'pygame')
        FontManager.OPTIONS['use_freetype'] = (font_system == 'freetype')
        log.info(f'Font system initialized: {font_system}')

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
        # pygame.ftfont.init()

        # self.proxies = [FontManager.FontProxy(game=game), pygame.freetype]

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
        group.add_argument('--font-system', choices=['pygame', 'freetype'], default='pygame',
                          help='Font system to use: pygame (built-in) or freetype (enhanced)')

        return parser

    # TODO: Make it so that we can run pyinstaller compiled games
    # with a system font by passing an explicit path.
    #
    # We can also use a config file to specify the font path.
    @classmethod
    def font(
        cls, font_config: dict | None = None
    ) -> pygame.freetype.Font | pygame.freetype.SysFont:
        """Return a font object.

        If the font requested can't be found then bitstream_vera will be loaded instead.

        Note that if you are trying to package your game with pyinstaller, you'll need to bundle
        your game's fonts with the pyinstaller invocation.  Make sure you have distribution
        rights to the fonts you're including with your game.

        bitstream_vera is a permissively licensed font that can be used with your game.

        Args:
            font_config (dict | None): The font configuration.

        Returns:
            pygame.freetype.Font | pygame.freetype.SysFont
        """
        if not font_config:
            font_config = FontManager.OPTIONS
        
        # Provide default font configuration if not set
        if 'font_name' not in font_config:
            font_config['font_name'] = 'arial'
        if 'font_size' not in font_config:
            font_config['font_size'] = 14

        # try:
        log.info(f'Loading Font: {font_config["font_name"]}')
        log.info(f'Font Size: {font_config["font_size"]}')

        try:
            return pygame.freetype.SysFont(
                name=font_config['font_name'], size=font_config['font_size']
            )
        except (TypeError, FileNotFoundError):
            # Note: Not sure why but pygame.freetype.SysFont doesn't
            # seem to work with pyinstaller packaged games.
            log.info('Loading Font: Built-In')

            # BUG: pygame's documentation claims that passing None
            # as the font name will load the default font.  However,
            # this emits an error when running a pyinstaller packaged
            # pygame game.
            #
            # File "glitchygames/fonts.py", line 131, in font
            #     return pygame.freetype.SysFont(name=None, size=12)
            #         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
            # File "pygame/freetype.py", line 78, in SysFont
            # File "pygame/sysfont.py", line 462, in SysFont
            # File "pygame/freetype.py", line 73, in constructor
            # TypeError: not a file object
            font_path = Path(__file__).parent / 'fonts' / 'bitstream_vera' / 'Vera.ttf'
            return pygame.freetype.Font(file=font_path, size=12)
    
    @classmethod
    def pygame_font(cls, font_config: dict | None = None) -> pygame.font.Font:
        """Return a regular pygame font object for compatibility with UI components.
        
        Args:
            font_config (dict | None): The font configuration.
            
        Returns:
            pygame.font.Font: A regular pygame font object.
        """
        if not font_config:
            font_config = FontManager.OPTIONS
        
        # Provide default font configuration if not set
        if 'font_name' not in font_config:
            font_config['font_name'] = 'arial'
        if 'font_size' not in font_config:
            font_config['font_size'] = 14
            
        try:
            # Try to load system font
            return pygame.font.SysFont(font_config['font_name'], font_config['font_size'])
        except (TypeError, FileNotFoundError):
            # Fall back to default font
            return pygame.font.Font(None, font_config['font_size'])
    
    @classmethod
    def get_font(cls, use_freetype: bool | None = None, font_config: dict | None = None) -> pygame.font.Font | pygame.freetype.Font:
        """Get a font object, choosing between pygame.font and pygame.freetype.
        
        Args:
            use_freetype (bool | None): If True, return pygame.freetype.Font, if False pygame.font.Font.
                                       If None, use the default preference from OPTIONS.
            font_config (dict | None): The font configuration.
            
        Returns:
            pygame.font.Font | pygame.freetype.Font: The requested font object.
        """
        if use_freetype is None:
            use_freetype = FontManager.OPTIONS.get('use_freetype', False)
        
        if use_freetype:
            return cls.font(font_config)
        else:
            return cls.pygame_font(font_config)
    
    @classmethod
    def set_font_system(cls, use_freetype: bool):
        """Set the default font system preference.
        
        Args:
            use_freetype (bool): If True, use pygame.freetype by default, otherwise pygame.font.
        """
        FontManager.OPTIONS['use_freetype'] = use_freetype
        log.info(f'Font system set to: {"pygame.freetype" if use_freetype else "pygame.font"}')
    
    @classmethod
    def get_font_system(cls) -> str:
        """Get the current font system preference.
        
        Returns:
            str: "freetype" or "pygame" indicating the current font system.
        """
        return "freetype" if FontManager.OPTIONS.get('use_freetype', False) else "pygame"
    
    @classmethod
    def compare_font_systems(cls, text: str = "Hello World", size: int = 24) -> Dict[str, Dict[str, Any]]:
        """Compare both font systems side by side.
        
        Args:
            text (str): Text to render for comparison.
            size (int): Font size for comparison.
            
        Returns:
            dict: Information about both font systems.
        """
        config = {'font_size': size}
        
        # Get pygame.font
        pygame_font = cls.pygame_font(config)
        pygame_surface = pygame_font.render(text, True, (255, 255, 255))
        
        # Get pygame.freetype
        freetype_font = cls.font(config)
        freetype_surface, freetype_rect = freetype_font.render(text, (255, 255, 255))
        
        return {
            'pygame': {
                'font': pygame_font,
                'surface': pygame_surface,
                'size': pygame_surface.get_size(),
                'type': 'pygame.font.Font'
            },
            'freetype': {
                'font': freetype_font,
                'surface': freetype_surface,
                'size': freetype_surface.get_size(),
                'type': 'pygame.freetype.Font'
            }
        }
