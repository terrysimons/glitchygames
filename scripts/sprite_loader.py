#!/usr/bin/env python3
"""A simple sprite loader for Glitchy Games."""

from __future__ import annotations

import configparser
import logging
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self, override

if TYPE_CHECKING:
    import argparse
    from collections.abc import Iterator

import pygame

from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene
from glitchygames.sprites import Sprite, SpriteFactory

log: logging.Logger = logging.getLogger('game')
log.setLevel(logging.DEBUG)


class BitmappySprite(Sprite):
    """A sprite class for loading bitmappy sprites."""

    def __init__(self: Self, filename: str) -> None:
        """Initialize a BitmappySprite.

        Args:
            filename (str): The filename to load.

        """
        super().__init__(x=0, y=0, width=0, height=0)
        self.image: pygame.Surface | None = None
        self.rect: pygame.Rect | None = None
        self.name: str | None = None

        (self.image, self.rect, self.name) = self.load(filename=filename)

    def load(self: Self, filename: str) -> tuple[pygame.Surface, pygame.Rect, str]:
        """Load a sprite from a config file.

        Args:
            filename (str): The filename to load.

        Returns:
            tuple[pygame.Surface, pygame.Rect, str]: The image, rect, and name.

        """
        config: configparser.ConfigParser = configparser.ConfigParser(dict_type=OrderedDict)

        config.read(filename, encoding='utf-8')

        name: str = config.get(section='sprite', option='name')

        pixels: list[str] = config.get(section='sprite', option='pixels').split('\n')

        # Set our sprite's length and width.
        width: int = 0
        height: int = 0
        index: int = -1

        # This is a bit of a cleanup in case the config contains something like:
        #
        # pixels = \n
        #  .........
        #
        while not width:
            index += 1
            width = len(pixels[index])
            height = len(pixels[index:])

        # Trim any dead whitespace.
        # We're off by one since we increment the
        pixels = pixels[index:]

        color_map: dict[str, tuple[int, int, int]] = {}
        for section in config.sections():
            # This is checking the length of the section's name.
            # Colors are length 1.  This works with unicode, too.
            if len(section) == 1:
                red: int = config.getint(section=section, option='red')
                green: int = config.getint(section=section, option='green')
                blue: int = config.getint(section=section, option='blue')

                color_map[section] = (red, green, blue)

        (image, rect) = self.inflate(width=width, height=height, pixels=pixels, color_map=color_map)

        return (image, rect, name)

    @classmethod
    def rgb_triplet_generator(
        cls: type[BitmappySprite],
        buffer: list[int],
    ) -> Iterator[tuple[int, ...]]:
        """Yield (R, G, B) tuples for the provided pixel data.

        Args:
            buffer (list[int]): The buffer to read from.

        Yields:
            tuple[int, int, int]: An RGB triplet.

        """
        iterator: Iterator[int] = iter(buffer)

        try:
            while True:
                # range(3) gives us 3 at a time, so r, g, b.
                yield tuple(next(iterator) for _ in range(3))
        except StopIteration:
            pass

    @classmethod
    def inflate(
        cls: type[BitmappySprite],
        width: int,
        height: int,
        pixels: list[str],
        color_map: dict[str, tuple[int, int, int]],
    ) -> tuple[pygame.Surface, pygame.Rect]:
        """Inflate a sprite from a list of pixels.

        Args:
            width (int): The width of the sprite.
            height (int): The height of the sprite.
            pixels (list[str]): The list of pixels.
            color_map (dict[str, tuple[int, int, int]]): The color map.

        Returns:
            tuple[pygame.Surface, pygame.Rect]: The image and rect.

        """
        image: pygame.Surface = pygame.Surface((width, height))
        image.convert()

        raw_pixels: list[tuple[int, int, int]] = []
        for y, row in enumerate(pixels):
            for x_pos, pixel in enumerate(row):
                color: tuple[int, int, int] = color_map[pixel]
                raw_pixels.append(color)
                pygame.draw.rect(image, color, (x_pos, y, 1, 1))

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
        color_map: dict[tuple[int, ...], str] = {}
        pixels: list[str] = []

        if self.image is None:
            config.add_section('sprite')
            config.set('sprite', 'name', self.name or '')
            config.set('sprite', 'pixels', '')
            return config

        raw_pixels_iter = self.rgb_triplet_generator(
            list(pygame.image.tobytes(self.image, 'RGB')),
        )

        # We're utilizing the generator to give us RGB triplets.
        # We need a list here because we'll use set() to pull out the
        # unique values, but we also need to consume the list again
        # down below, so we can't solely use a generator.
        raw_pixels: list[tuple[int, ...]] = list(raw_pixels_iter)

        # This gives us the unique rgb triplets in the image.
        colors: set[tuple[int, ...]] = set(raw_pixels)

        config.add_section('sprite')
        config.set('sprite', 'name', self.name or '')

        # Generate the color key
        color_key: str = chr(47)
        for color in colors:
            # Characters above doublequote.
            color_key = chr(ord(color_key) + 1)
            config.add_section(color_key)

            color_map[color] = color_key

            log.debug('Key: %s -> %s', color, color_key)

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
                log.debug('Row: %s', row)
                pixels.append(''.join(row))
                row = []
                x = 0

        log.debug(pixels)

        config.set('sprite', 'pixels', '\n'.join(pixels))

        log.debug('Deflated Sprite: %s', config)

        return config

    @override
    def __str__(self: Self) -> str:
        """Return a string representation of the sprite.

        Returns:
            str: The string representation of the sprite.

        """
        return f'Name: {self.name}\nDimensions: {self.width}x{self.height}\n'


class GameScene(Scene):
    """The main game scene.  This is where the magic happens."""

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

        self.sprite = SpriteFactory.load_sprite(filename=self.filename)

        self.all_sprites: pygame.sprite.LayeredDirty[Any] = pygame.sprite.LayeredDirty(self.sprite)

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
        assert self.filename is not None, 'filename is required'

        self.next_scene = GameScene(filename=self.filename)

    @classmethod
    def args(cls: type[Game], parser: argparse.ArgumentParser) -> None:
        """Add arguments to the parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        """
        parser.add_argument(
            '-v',
            '--version',
            action='store_true',
            help='print the game version and exit',
        )

        parser.add_argument('--filename', help='the file to load', required=True)


def main() -> None:
    """Run the main entry point for the game."""
    GameEngine(game=Game).start()


if __name__ == '__main__':
    main()
