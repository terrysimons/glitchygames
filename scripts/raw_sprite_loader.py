#!/usr/bin/env python3
"""A simple legacy bitmappy sprite loader."""

from __future__ import annotations

import configparser
import logging
import struct
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self, override

if TYPE_CHECKING:
    import argparse

import pygame

from glitchygames.engine import GameEngine
from glitchygames.pixels import rgb_565_triplet_generator, rgb_triplet_generator
from glitchygames.scenes import Scene
from glitchygames.sprites import SPRITE_GLYPHS, Sprite

LOG = logging.getLogger('game')
LOG.setLevel(logging.INFO)


class BitmappyLegacySprite(Sprite):
    """A sprite class for loading legacy bitmappy sprites."""

    log: logging.Logger = LOG

    def __init__(self: Self, filename: str, *args: object, **kwargs: object) -> None:
        """Initialize a BitmappySprite.

        Args:
            *args: Arguments to pass to the parent class.
            filename (str): The filename to load.
            **kwargs: Keyword arguments to pass to the parent class.

        """
        super().__init__(*args, width=0, height=0, **kwargs)  # type: ignore[arg-type]
        self.image: pygame.Surface | None = None
        self.rect: pygame.Rect | None = None
        self.name: str | None = None

        (self.image, self.rect, self.name) = self.load(filename=filename, width=32, height=32)

        self.save(filename + '.cfg')

    def load(
        self: Self, filename: str, width: int, height: int
    ) -> tuple[pygame.Surface, pygame.Rect, str]:
        """Load a sprite from a config file.

        Args:
            filename (str): The filename to load.
            width (int): The width of the sprite.
            height (int): The height of the sprite.

        Returns:
            tuple[pygame.Surface, pygame.Rect, str]: The image, rect, and name.

        """
        # Load the raw bits in.
        data: bytes = Path(filename).read_bytes()

        # Unpack the bytes into 565 triplets.
        # Read 2 bytes, unsigned.
        packed_rgb_data = struct.iter_unpack('<H', data)

        pixels: list[tuple[int, int, int]] = list(
            rgb_565_triplet_generator(pixel_data=packed_rgb_data)
        )

        for pixel in pixels:
            LOG.info(pixel)

        (image, rect) = self.inflate(width=width, height=height, pixels=pixels)

        return (image, rect, filename)

    @classmethod
    def inflate(
        cls: type[BitmappyLegacySprite],
        width: int,
        height: int,
        pixels: list[tuple[int, int, int]],
    ) -> tuple[pygame.Surface, pygame.Rect]:
        """Inflate the sprite.

        Args:
            width (int): The width of the sprite.
            height (int): The height of the sprite.
            pixels (list): The list of pixels.

        Returns:
            tuple[pygame.Surface, pygame.Rect]: The image and rect.

        """
        image: pygame.Surface = pygame.Surface((width, height))
        image.fill((0, 255, 0))
        image.convert()
        image.set_colorkey((255, 0, 255))

        x: int = 0
        y: int = 0
        for color in pixels:
            pygame.draw.rect(image, color, (y, x, 0, 0))

            if x and x % width == 0:
                y += 1
                x = 1
            else:
                x += 1

        return (image, image.get_rect())

    def save(self: Self, filename: str) -> None:
        """Save the sprite to a file.

        Args:
            filename (str): The filename to save to.

        """
        config: configparser.ConfigParser = self.deflate()

        with Path(filename).open('w', encoding='utf-8') as deflated_sprite:
            config.write(deflated_sprite)

    def deflate(self: Self) -> configparser.ConfigParser:
        """Deflate the sprite into a config file.

        Returns:
            configparser.ConfigParser: The config parser.

        Raises:
            ValueError: If there are too many unique colors to map to characters.

        """
        config: configparser.ConfigParser = configparser.ConfigParser(dict_type=OrderedDict)

        # Get the set of distinct pixels.
        color_map: dict[tuple[int, int, int], str] = {}
        pixels: list[str] = []

        # Handle empty surfaces
        has_surface = (
            self.rect is not None
            and self.rect.width > 0
            and self.rect.height > 0
            and self.image is not None
        )

        if not has_surface:
            raw_pixels: list[tuple[int, int, int]] = []
            colors: set[tuple[int, int, int]] = set()
        else:
            try:
                # TODO: migrate to tobytes once test mocks provide real Surfaces
                assert self.image is not None  # narrowing for type checker
                raw_pixels = list(
                    rgb_triplet_generator(
                        pygame.image.tostring(self.image, 'RGB')  # pyright: ignore[reportDeprecated]  # ty: ignore[deprecated]
                    )
                )
                # This gives us the unique rgb triplets in the image.
                colors = set(raw_pixels)
            except ValueError as e:
                # Handle empty pixel data
                if 'Empty pixel data' in str(e):
                    raw_pixels = []
                    colors = set()
                else:
                    raise

        config.add_section('sprite')
        config.set('sprite', 'name', self.name or '')

        # Generate the color key using universal character set
        universal_chars: str = SPRITE_GLYPHS

        # Assign characters sequentially from SPRITE_GLYPHS
        for char_index, color in enumerate(colors):
            if char_index >= len(universal_chars):
                raise ValueError(f'Too many colors (max {len(universal_chars)})')

            color_key: str = universal_chars[char_index]
            config.add_section(color_key)
            color_map[color] = color_key

            self.log.debug(f'Key: {color} -> {color_key}')

            red: int = color[0]
            config.set(color_key, 'red', str(red))

            green: int = color[1]
            config.set(color_key, 'green', str(green))

            blue: int = color[2]
            config.set(color_key, 'blue', str(blue))

        # Process pixels only if we have any
        if raw_pixels:
            x: int = 0
            row: list[str] = []
            while raw_pixels:
                row.append(color_map[raw_pixels.pop(0)])
                x += 1

                if self.rect is not None and x % self.rect.width == 0:
                    self.log.debug(f'Row: {row}')
                    pixels.append(''.join(row))
                    row = []
                    x = 0

            self.log.debug(pixels)
            config.set('sprite', 'pixels', '\n'.join(pixels))
        else:
            # Empty surface - set empty pixels
            config.set('sprite', 'pixels', '')

        self.log.debug(f'Deflated Sprite: {config}')

        return config

    @override
    def __str__(self: Self) -> str:
        """Return a string representation of the sprite.

        Returns:
            str: A string representation of the sprite.

        """
        return f'Name: {self.name}\nDimensions: {self.width}x{self.height}\n'


class GameScene(Scene):
    """The main game scene."""

    log: logging.Logger = LOG

    def __init__(self: Self, filename: str) -> None:
        """Initialize the GameScene.

        Args:
            filename (str): The filename to load.

        """
        super().__init__()
        screen = pygame.display.get_surface()
        assert screen is not None
        self.screen: pygame.Surface = screen
        self.screen_width: int = self.screen.get_width()
        self.screen_height: int = self.screen.get_height()
        self.filename: str = filename

        # Load the legacy sprite file.
        self.sprite: BitmappyLegacySprite = BitmappyLegacySprite(filename=self.filename)

        self.all_sprites: pygame.sprite.LayeredDirty[Any] = pygame.sprite.LayeredDirty(
            self.sprite
        )

        self.all_sprites.clear(self.screen, self.background)


class Game(Scene):
    """The main game class."""

    # Set your game name/version here.
    NAME: str = 'Raw Sprite Loader'
    VERSION: str = '1.0'

    def __init__(self: Self, options: dict[str, Any]) -> None:
        """Initialize the Game.

        Args:
            options (dict): The options passed to the game.

        """
        super().__init__(options=options)
        self.filename: str | None = options.get('filename')

    @classmethod
    def args(cls: type[Game], parser: argparse.ArgumentParser) -> None:
        """Add arguments to the argument parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        """
        parser.add_argument(
            '-v', '--version', action='store_true', help='print the game version and exit'
        )

        parser.add_argument('--filename', help='the file to load', required=True)


def main() -> None:
    """Run the main entry point for the game."""
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()
