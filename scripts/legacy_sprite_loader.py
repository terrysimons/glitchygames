#!/usr/bin/env python3
"""A simple game that loads a legacy sprite file."""

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
from pygame import Color

from glitchygames.color.palette import Vga
from glitchygames.engine import GameEngine
from glitchygames.pixels import indexed_rgb_triplet_generator, rgb_triplet_generator
from glitchygames.scenes import Scene
from glitchygames.sprites import Sprite

LOG: logging.Logger = logging.getLogger('game')
LOG.setLevel(logging.INFO)


class BitmappyLegacySprite(Sprite):
    """A sprite class for loading legacy bitmappy sprites."""

    log: logging.Logger = LOG

    def __init__(
        self: Self,
        filename: str,
        palette: list[Color],
        *args: object,
        **kwargs: object,
    ) -> None:
        """Initialize a BitmappySprite.

        Args:
            *args: Arguments to pass to the parent class.
            filename (str): The filename to load.
            palette (list[Color]): The palette to use for color conversion.
            **kwargs: Keyword arguments to pass to the parent class.

        """
        super().__init__(*args, width=0, height=0, **kwargs)  # type: ignore[arg-type]
        self.image: pygame.Surface | None = None
        self.rect: pygame.Rect | None = None
        self.name: str | None = None
        self.palette: list[Color] = palette

        (self.image, self.rect, self.name) = self.load(
            filename=filename, palette=self.palette, width=32, height=32
        )

        self.save(filename + '.cfg')

    def load(
        self: Self,
        filename: str,
        palette: list[Color],
        width: int,
        height: int,
    ) -> tuple[pygame.Surface, pygame.Rect, str]:
        """Load a sprite from a config file.

        Args:
            filename (str): The filename to load.
            palette (list[Color]): The palette to use for color conversion.
            width (int): The width of the sprite.
            height (int): The height of the sprite.

        Returns:
            tuple[pygame.Surface, pygame.Rect, str]: The image, rect, and name.

        """
        rgb_pixels: list[tuple[int, int, int]] = []

        # Load the raw bits in.
        data: bytes = Path(filename).read_bytes()

        # Unpack the bytes.
        # Read 1 byte, unsigned.
        indexed_rgb_data = struct.iter_unpack('<B', data)

        pixels: list[tuple[int, int, int]] = list(
            indexed_rgb_triplet_generator(pixel_data=indexed_rgb_data)
        )

        # NOTE: This code replaces the below for loop but hasn't been tested.
        palette_colors: list[tuple[int, int, int]] = [
            palette[pixel] for pixel in pixels[0 : width * height]  # type: ignore[index]
        ]
        rgb_pixels.extend(palette_colors)

        (image, rect) = self.inflate(width=width, height=height, pixels=rgb_pixels)

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
            pixels (list[tuple[int, int, int]]): The list of pixels.

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

        """
        config: configparser.ConfigParser = configparser.ConfigParser(dict_type=OrderedDict)

        # Get the set of distinct pixels.
        color_map: dict[tuple[int, int, int], str] = {}
        pixels: list[str] = []

        if self.image is None:
            config.add_section('sprite')
            config.set('sprite', 'name', self.name or '')
            config.set('sprite', 'pixels', '')
            return config

        # TODO: migrate to tobytes once test mocks provide real Surfaces
        raw_pixels: list[tuple[int, int, int]] = list(
            rgb_triplet_generator(
                pygame.image.tostring(self.image, 'RGB')  # pyright: ignore[reportDeprecated]  # ty: ignore[deprecated]
            )
        )

        # This gives us the unique rgb triplets in the image.
        colors: set[tuple[int, int, int]] = set(raw_pixels)

        config.add_section('sprite')
        config.set('sprite', 'name', self.name or '')

        # Generate the color key
        color_key: str = chr(47)
        for color in colors:
            # Characters above doublequote.
            color_key = chr(ord(color_key) + 1)
            config.add_section(color_key)

            color_map[color] = color_key

            self.log.debug(f'Key: {color} -> {color_key}')

            red: int = color[0]
            config.set(color_key, 'red', str(red))

            green: int = color[1]
            config.set(color_key, 'green', str(green))

            blue: int = color[2]
            config.set(color_key, 'blue', str(blue))

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

        self.log.debug(f'Deflated Sprite: {config}')

        return config

    @override
    def __str__(self: Self) -> str:
        """Return a string representation of the sprite.

        Returns:
            str: The string representation.

        """
        return f'Name: {self.name}\nDimensions: {self.width}x{self.height}\n'


class GameScene(Scene):
    """The main game scene."""

    def __init__(self: Self, filename: str, palette: list[Color]) -> None:
        """Initialize the GameScene.

        Args:
            filename (str): The filename to load.
            palette (list[Color]): The palette to use for color conversion.

        """
        super().__init__()
        screen = pygame.display.get_surface()
        assert screen is not None
        self.screen: pygame.Surface = screen
        self.screen_width: int = self.screen.get_width()
        self.screen_height: int = self.screen.get_height()
        self.filename: str = filename
        self.palette: list[Color] = palette

        # Load the legacy sprite file.
        self.sprite: BitmappyLegacySprite = BitmappyLegacySprite(
            filename=self.filename, palette=self.palette
        )

        self.all_sprites: pygame.sprite.LayeredDirty[Any] = pygame.sprite.LayeredDirty(
            self.sprite
        )

        self.all_sprites.clear(self.screen, self.background)


class Game(Scene):
    """The main game class."""

    # Set your game name/version here.
    NAME: str = 'Sprite Loader'
    VERSION: str = '1.0'

    def __init__(self: Self, options: dict[str, Any]) -> None:
        """Initialize the Game.

        Args:
            options (dict[str, Any]): The options passed to the game.

        """
        super().__init__(options=options)
        self.filename: str | None = options.get('filename')
        self.palette: Vga = Vga()

        self.next_scene = GameScene(filename=self.filename or '', palette=self.palette)  # type: ignore[arg-type]

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
