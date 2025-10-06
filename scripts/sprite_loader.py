#!/usr/bin/env python3
"""A simple sprite loader for Glitchy Games."""

from __future__ import annotations

import configparser
import logging
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import argparse

import pygame
from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene
from glitchygames.sprites import Sprite, SpriteFactory

log = logging.getLogger("game")
log.setLevel(logging.DEBUG)


class BitmappySprite(Sprite):
    """A sprite class for loading bitmappy sprites."""

    def __init__(self: Self, filename: str, *args, **kwargs) -> None:
        """Initialize a BitmappySprite.

        Args:
            *args: Arguments to pass to the parent class.
            filename (str): The filename to load.
            **kwargs: Keyword arguments to pass to the parent class.

        Returns:
            Self

        """
        super().__init__(*args, pos=(0, 0), size=(0, 0), **kwargs)
        self.image = None
        self.rect = None
        self.name = None

        (self.image, self.rect, self.name) = self.load(filename=filename)

    def load(self: Self, filename: str) -> tuple[pygame.Surface, pygame.Rect, str]:
        """Load a sprite from a config file.

        Args:
            filename (str): The filename to load.

        Returns:
            tuple[pygame.Surface, pygame.Rect, str]: The image, rect, and name.

        """
        config = configparser.ConfigParser(dict_type=OrderedDict)

        config.read(filename, encoding="utf-8")

        # Example config:
        # [sprite]
        # name = <name>
        name = config.get(section="sprite", option="name")

        # pixels = <pixels>
        pixels = config.get(section="sprite", option="pixels").split("\n")

        # Set our sprite's length and width.
        width = 0
        height = 0
        index = -1

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

        color_map = {}
        for section in config.sections():
            # This is checking the length of the section's name.
            # Colors are length 1.  This works with unicode, too.
            if len(section) == 1:
                red = config.getint(section=section, option="red")
                green = config.getint(section=section, option="green")
                blue = config.getint(section=section, option="blue")

                color_map[section] = (red, green, blue)

        (image, rect) = self.inflate(width=width, height=height, pixels=pixels, color_map=color_map)

        return (image, rect, name)

    @classmethod
    def rgb_triplet_generator(cls: Self, buffer: list) -> iter[tuple[int, int, int]]:
        """Yield (R, G, B) tuples for the provided pixel data.

        Args:
            buffer (list): The buffer to read from.

        Returns:
            iter[tuple[int, int, int]]: An iterator of RGB triplets.

        """
        iterator = iter(buffer)

        try:
            while True:
                # range(3) gives us 3 at a time, so r, g, b.
                yield tuple(next(iterator) for i in range(3))
        except StopIteration:
            pass

    @classmethod
    def inflate(
        cls: Self, width: int, height: int, pixels: list, color_map: dict
    ) -> tuple[pygame.Surface, pygame.Rect]:
        """Inflate a sprite from a list of pixels.

        Args:
            width (int): The width of the sprite.
            height (int): The height of the sprite.
            pixels (list): The list of pixels.
            color_map (dict): The color map.

        Returns:
            tuple[pygame.Surface, pygame.Rect]: The image and rect.

        """
        image = pygame.Surface((width, height))
        image.convert()

        raw_pixels = []
        for y, row in enumerate(pixels):
            for x, pixel in enumerate(row):
                color = color_map[pixel]
                raw_pixels.append(color)
                pygame.draw.rect(image, color, (x, y, 1, 1))

        return (image, image.get_rect())

    def save(self: Self, filename: str) -> None:
        """Save the sprite to a file.

        Args:
            filename (str): The filename to save to.

        Returns:
            None

        """
        config = self.deflate()

        with Path.open(filename, "w") as deflated_sprite:
            config.write(deflated_sprite)

    def deflate(self: Self) -> configparser.ConfigParser:
        """Deflate the sprite into a config file.

        Args:
            None

        Returns:
            configparser.ConfigParser: The config parser.

        """
        config = configparser.ConfigParser(dict_type=OrderedDict)

        # Get the set of distinct pixels.
        color_map = {}
        pixels = []

        raw_pixels = self.rgb_triplet_generator(pygame.image.tostring(self.image, "RGB"))

        # We're utilizing the generator to give us RGB triplets.
        # We need a list here becasue we'll use set() to pull out the
        # unique values, but we also need to consume the list again
        # down below, so we can't solely use a generator.
        raw_pixels = list(raw_pixels)

        # This gives us the unique rgb triplets in the image.
        colors = set(raw_pixels)

        config.add_section("sprite")
        config.set("sprite", "name", self.name)

        # Generate the color key
        color_key = chr(47)
        for color in colors:
            # Characters above doublequote.
            color_key = chr(ord(color_key) + 1)
            config.add_section(color_key)

            color_map[color] = color_key

            log.debug(f"Key: {color} -> {color_key}")

            red = color[0]
            config.set(color_key, "red", str(red))

            green = color[1]
            config.set(color_key, "green", str(green))

            blue = color[2]
            config.set(color_key, "blue", str(blue))

        x = 0
        row = []
        while raw_pixels:
            row.append(color_map[raw_pixels.pop(0)])
            x += 1

            if x % self.rect.width == 0:
                log.debug(f"Row: {row}")
                pixels.append("".join(row))
                row = []
                x = 0

        log.debug(pixels)

        config.set("sprite", "pixels", "\n".join(pixels))

        log.debug(f"Deflated Sprite: {config}")

        return config

    def __str__(self: Self) -> str:
        """Return a string representation of the sprite.

        Args:
            None

        Returns:
            str: The string representation of the sprite.

        """
        description = (
            f"Name: {self.name}\nDimensions: {self.width}x{self.height}"
            "\nColor Key: {self.color_key}\n"
        )

        for row in self.pixels:
            for pixel in row:
                description += pixel
            description += "\n"

        return description


class GameScene(Scene):
    """The main game scene.  This is where the magic happens."""

    def __init__(self: Self, filename: str) -> None:
        """Initialize the GameScene.

        Args:
            filename (str): The filename to load.

        Returns:
            None

        """
        super().__init__()
        self.screen = pygame.display.get_surface()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()
        self.filename = filename

        self.sprite = SpriteFactory.load_sprite(filename=self.filename)

        self.all_sprites = pygame.sprite.LayeredDirty(tuple(self.sprite))

        self.all_sprites.clear(self.screen, self.background)


class Game(Scene):
    """The main game class."""

    # Set your game name/version here.
    NAME = "Sprite Loader"
    VERSION = "1.0"

    def __init__(self: Self, options: dict) -> None:
        """Initialize the Game.

        Args:
            options (dict): The options passed to the game.

        Returns:
            None

        """
        super().__init__(options=options)
        self.filename = options.get("filename")

        self.next_scene = GameScene(filename=self.filename)

    @classmethod
    def args(cls: Self, parser: argparse.ArgumentParser) -> None:
        """Add arguments to the parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            None

        """
        parser.add_argument(
            "-v", "--version", action="store_true", help="print the game version and exit"
        )

        parser.add_argument("--filename", help="the file to load", required=True)


def main() -> None:
    """Run the main entry point for the game."""
    GameEngine(game=Game).start()


if __name__ == "__main__":
    main()
