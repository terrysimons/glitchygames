#!/usr/bin/env python

import argparse
from collections import OrderedDict
import configparser
import logging
import struct

from pygame import Color, Rect
import pygame

from engine import GameEngine
from engine import RootScene
from engine import RootSprite

log = logging.getLogger('game')
log.setLevel(logging.INFO)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

log.addHandler(ch)

class BitmappyLegacySprite(RootSprite):
    def __init__(self, filename, *args, **kwargs):
        super().__init__(*args, width=0, height=0, **kwargs)
        self.image = None
        self.rect = None
        self.name = None

        (self.image, self.rect, self.name) = self.load(filename=filename, width=32, height=32)

        self.save(filename + '.cfg')

    def load(self, filename, width, height):
        """
        """
        image = None
        rect = None
        name = None
        data = []

        # Load the raw bits in.
        with open(filename, 'rb') as fh:
            data = fh.read()

        # Unpack the bytes into 565 triplets.
        # Read 2 bytes, unsigned.
        packed_rgb_data = struct.iter_unpack('<H', data)

        self.color_format_565 = True

        pixels = self.rgb_565_triplet_generator(data=packed_rgb_data)

        pixels = [pixel for pixel in pixels]

        for pixel in pixels:
            print(pixel)

        (image, rect) = self.inflate(width=width,
                                     height=height,
                                     pixels=pixels)

        return (image, rect, filename)

    def rgb_555_triplet_generator(self, data):
        try:
            # Construct RGB triplets.
            for packed_rgb_triplet in data:
                # struct unpacks as a 1 element tuple.
                rgb_data = bin(packed_rgb_triplet[0])

                print(f'Data: {rgb_data}')

                # binary conversions start with 0b, so chop that off.            
                rgb_data = rgb_data[2:]

                # Pad the data out.
                pad_bits = 16 - len(rgb_data)
                pad_data = '0' * pad_bits

                rgb_data = pad_data + rgb_data

                log.info(f'Padded {pad_bits} bits (now {rgb_data})')

                # red is 5 bits
                red = int(rgb_data[0:5] + '000', 2)

                if red:
                    red += 7

                # green is 6 bits
                green = int(rgb_data[5:10] + '000', 2)

                if green:
                    green += 7

                # blue is 5 bits
                blue = int(rgb_data[10:15] + '000', 2)

                # last bit is ignored or used for alpha.

                if blue:
                    blue += 7

                log.info(f'Packed RGB: {rgb_data}')
                log.info(f'Red: {red}')
                log.info(f'Green: {green}')
                log.info(f'Blue: {blue}')

                yield tuple([red, green, blue])
        except StopIteration:
            pass

    def rgb_565_triplet_generator(self, data):
        try:
            # Construct RGB triplets.
            for packed_rgb_triplet in data:
                # struct unpacks as a 1 element tuple.
                rgb_data = bin(packed_rgb_triplet[0])

                print(f'Data: {rgb_data}')

                # binary conversions start with 0b, so chop that off.            
                rgb_data = rgb_data[2:]

                # Pad the data out.
                pad_bits = 16 - len(rgb_data)
                pad_data = '0' * pad_bits

                rgb_data = pad_data + rgb_data

                log.info(f'Padded {pad_bits} bits (now {rgb_data})')

                # red is 5 bits
                red = int(rgb_data[0:5] + '000', 2)

                if red:
                    red += 7

                # green is 6 bits
                green = int(rgb_data[5:11] + '00', 2)

                if green:
                    green += 3

                # blue is 5 bits
                blue = int(rgb_data[11:] + '000', 2)

                if blue:
                    blue += 7

                log.info(f'Packed RGB: {rgb_data}')
                log.info(f'Red: {red}')
                log.info(f'Green: {green}')
                log.info(f'Blue: {blue}')

                yield tuple([red, green, blue])
        except StopIteration:
            pass

    def rgb_triplet_generator(self, data):
        iterator = iter(data)

        try:
            while True:
                # range(3) gives us 3 at a time, so r, g, b.
                yield tuple([next(iterator) for i in range(3)])
        except StopIteration:
            pass

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

            log.debug(f'Key: {color} -> {color_key}')
            
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
                log.debug(f'Row: {row}')
                pixels.append(''.join(row))
                row = []
                x = 0

        log.debug(pixels)

        config.set('sprite', 'pixels', '\n'.join(pixels))

        log.debug(f'Deflated Sprite: {config}')

        return config

    def __str__(self):
        description = f'Name: {self.name}\nDimensions: {self.width}x{self.height}\nColor Key: {self.color_key}\n'

        for y, row in enumerate(self.pixels):
            for x, pixel in enumerate(row):
                description += pixel
            description += '\n'

        return description

class GameScene(RootScene):
    def __init__(self, filename):
        super().__init__()
        self.screen = pygame.display.get_surface()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()
        self.filename = filename

        # Load the legacy sprite file.
        self.sprite = BitmappyLegacySprite(filename=self.filename)

        self.all_sprites = pygame.sprite.LayeredDirty((self.sprite))

        self.all_sprites.clear(self.screen, self.background)

    def update(self):
        super().update()

    def render(self, screen):
        super().render(screen)

    def switch_to_scene(self, next_scene):
        super().switch_to_scene(next_scene)

class Game(GameEngine):
    # Set your game name/version here.
    NAME = "Sprite Loader"
    VERSION = "1.0"

    def __init__(self, options):
        super().__init__(options=options)
        self.filename = options.get('filename')

    @classmethod
    def args(cls, parser):
        # Initialize the game engine's options first.
        # This ensures that our game's specific options
        # are listed last.
        parser = GameEngine.args(parser)

        group = parser.add_argument_group('Game Options')

        group.add_argument('-v', '--version',
                        action='store_true',
                        help='print the game version and exit')

        group.add_argument('--filename',
                           help='the file to load',
                           required=True)        

        return parser

    def start(self):
        # This is a simple class that will help us print to the screen
        # It has nothing to do with the joysticks, just outputting the
        # information.

        # Call the main game engine's start routine to initialize
        # the screen and set the self.screen_width, self.screen_height variables
        # and do a few other init related things.
        super().start()

        # Note: Due to the way things are wired, you must set self.active_scene after
        # calling super().start() in this method.
        self.clock = pygame.time.Clock()
        self.active_scene = GameScene(filename=self.filename)

        while self.active_scene != None:
            self.process_events()

            self.active_scene.update()

            self.active_scene.render(self.screen)

            if self.update_type == 'update':
                pygame.display.update(self.active_scene.rects)
            elif self.update_type == 'flip':
                pygame.display.flip()                                

            self.clock.tick(self.fps)

            self.active_scene = self.active_scene.next
    

def main():
    parser = argparse.ArgumentParser(f'{Game.NAME} version {Game.VERSION}')

    parser = Game.args(parser)
    args = parser.parse_args()
    game = Game(options=vars(args))
    game.start()

if __name__ == '__main__':
    main()
