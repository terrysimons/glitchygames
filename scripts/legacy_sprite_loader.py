#!/usr/bin/env python

from collections import OrderedDict
import configparser
import logging
import struct

import pygame

from ghettogames.engine import GameEngine
from ghettogames.engine import vga_palette
from ghettogames.pixels import indexed_rgb_triplet_generator
from ghettogames.sprites import Sprite
from ghettogames.scenes import Scene

LOG = logging.getLogger('game')
LOG.setLevel(logging.INFO)


class BitmappyLegacySprite(Sprite):
    log = LOG

    def __init__(self, filename, palette, *args, **kwargs):
        super().__init__(*args, width=0, height=0, **kwargs)
        self.image = None
        self.rect = None
        self.name = None
        self.palette = palette

        (self.image, self.rect, self.name) = self.load(filename=filename,
                                                       palette=self.palette,
                                                       width=32,
                                                       height=32)

        self.save(filename + '.cfg')

    def load(self, filename, palette, width, height):
        """
        """
        # We need to load an 8-bit palette for color conversion.
        palette = palette
        image = None
        rect = None
        data = []
        rgb_pixels = []

        # Load the raw bits in.
        with open(filename, 'rb') as fh:
            data = fh.read()

        # Unpack the bytes.
        # Read 1 byte, unsigned.
        indexed_rgb_data = struct.iter_unpack('<B', data)

        pixels = indexed_rgb_triplet_generator(data=indexed_rgb_data)

        pixels = [pixel for pixel in pixels]

        for pixel in pixels[0:width * height]:
            rgb_pixels.append(palette[pixel])

        (image, rect) = self.inflate(width=width,
                                     height=height,
                                     pixels=rgb_pixels)

        return (image, rect, filename)

    def inflate(self, width, height, pixels):
        """
        """
        image = pygame.Surface((width, height))
        image.fill((0, 255, 0))
        image.convert()
        image.set_colorkey((255, 0, 255))

        x = 0
        y = 0
        for i, color in enumerate(pixels):
            pygame.draw.rect(image, color, (y, x, 0, 0))

            if x and x % width == 0:
                y += 1
                x = 1
            else:
                x += 1

        return (image, image.get_rect())

    def save(self, filename):
        """
        """
        config = self.deflate()

        with open(filename, 'w') as deflated_sprite:
            config.write(deflated_sprite)

    def deflate(self):
        config = configparser.ConfigParser(dict_type=OrderedDict)

        # Get the set of distinct pixels.
        color_map = {}
        pixels = []

        raw_pixels = self.rgb_triplet_generator(
            pygame.image.tostring(self.image, 'RGB')
        )

        # We're utilizing the generator to give us RGB triplets.
        # We need a list here becasue we'll use set() to pull out the
        # unique values, but we also need to consume the list again
        # down below, so we can't solely use a generator.
        raw_pixels = [raw_pixel for raw_pixel in raw_pixels]

        # This gives us the unique rgb triplets in the image.
        colors = set(raw_pixels)

        config.add_section('sprite')
        config.set('sprite', 'name', self.name)

        # Generate the color key
        color_key = chr(47)
        for i, color in enumerate(colors):
            # Characters above doublequote.
            color_key = chr(ord(color_key) + 1)
            config.add_section(color_key)

            color_map[color] = color_key

            self.log.debug(f'Key: {color} -> {color_key}')

            red = color[0]
            config.set(color_key, 'red', str(red))

            green = color[1]
            config.set(color_key, 'green', str(green))

            blue = color[2]
            config.set(color_key, 'blue', str(blue))

        x = 0
        row = []
        while raw_pixels:
            row.append(color_map[raw_pixels.pop(0)])
            x += 1

            if x % self.rect.width == 0:
                self.log.debug(f'Row: {row}')
                pixels.append(''.join(row))
                row = []
                x = 0

        self.log.debug(pixels)

        config.set('sprite', 'pixels', '\n'.join(pixels))

        self.log.debug(f'Deflated Sprite: {config}')

        return config

    def __str__(self):
        description = f'Name: {self.name}\nDimensions: {self.width}x{self.height}' \
            '\nColor Key: {self.color_key}\n'

        for y, row in enumerate(self.pixels):
            for x, pixel in enumerate(row):
                description += pixel
            description += '\n'

        return description


class GameScene(Scene):
    def __init__(self, filename, palette):
        super().__init__()
        self.screen = pygame.display.get_surface()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()
        self.filename = filename
        self.palette = palette

        # Load the legacy sprite file.
        self.sprite = BitmappyLegacySprite(filename=self.filename, palette=self.palette)

        self.all_sprites = pygame.sprite.LayeredDirty((self.sprite))

        self.all_sprites.clear(self.screen, self.background)


class Game(Scene):
    # Set your game name/version here.
    NAME = "Sprite Loader"
    VERSION = "1.0"

    def __init__(self, options):
        super().__init__(options=options)
        self.filename = options.get('filename')
        self.palette = vga_palette

        self.next_scene = GameScene()

    @classmethod
    def args(cls, parser):
        parser.add_argument('-v', '--version',
                            action='store_true',
                            help='print the game version and exit')

        parser.add_argument('--filename',
                            help='the file to load',
                            required=True)


def main():
    GameEngine(game=Game).start()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        raise e
    finally:
        pygame.display.quit()
        pygame.quit()
