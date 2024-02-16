#!/usr/bin/env python3
"""Fonts.

This is a simple font manager that can be used to load fonts.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Self

if TYPE_CHECKING:
    import argparse

import pygame
from glitchygames.events import FontEvents, ResourceManager

log = logging.getLogger('game.fonts')
log.addHandler(logging.NullHandler())


class FontManager(ResourceManager):
    """A font manager."""

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

        log.info('Freetype Font Cache Size: '
                 f'{pygame.freetype.get_cache_size()}')
        log.info('Freetype Font Default Resolution: '
                 f'{pygame.freetype.get_default_resolution()}')

        # Set up the default options.
        FontManager.OPTIONS['font_name'] = game.OPTIONS['font_name']
        FontManager.OPTIONS['font_size'] = game.OPTIONS['font_size']
        FontManager.OPTIONS['font_bold'] = game.OPTIONS['font_bold']
        FontManager.OPTIONS['font_italic'] = game.OPTIONS['font_italic']
        FontManager.OPTIONS['font_antialias'] = game.OPTIONS['font_antialias']
        FontManager.OPTIONS['font_dpi'] = game.OPTIONS['font_dpi']

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
    def args(cls: Self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add font options to the argument parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            argparse.ArgumentParser
        """
        group = parser.add_argument_group('Font Options')

        group.add_argument('--font-name',
                           default=pygame.freetype.get_default_font())
        group.add_argument('--font-size',
                           type=int,
                           default=14)
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

    # TODO: Make it so that we can run pyinstaller compiled games
    # with a system font by passing an explicit path.
    #
    # We can also use a config file to specify the font path.
    @classmethod
    def font(cls: Self, font_config: dict | None = None) -> pygame.freetype.Font | pygame.freetype.SysFont:  # noqa: E501
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

        # try:
        log.info(f'Loading Font: {font_config["font_name"]}')
        log.info(f'Font Size: {font_config["font_size"]}')

        try:
            return pygame.freetype.SysFont(name=font_config['font_name'],
                                            size=font_config['font_size'])
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
