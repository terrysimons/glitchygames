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

vga_palette = [(0, 0, 0),
               (0, 0, 170),
               (0, 170, 0),
               (0, 170, 170),
               (170, 0, 0),
               (170, 0, 170),
               (170, 85, 0),
               (170, 170, 170),
               (85, 85, 85),
               (85, 85, 255),
               (85, 255, 85),
               (85, 255, 255),
               (255, 85, 85),
               (255, 85, 255),
               (255, 255, 85),
               (255, 255, 255),
               (0, 0, 0),
               (20, 20, 20),
               (32, 32, 32),
               (44, 44, 44),
               (56, 56, 56),
               (69, 69, 69),
               (81, 81, 81),
               (97, 97, 97),
               (113, 113, 113),
               (130, 130, 130),
               (146, 146, 146),
               (162, 162, 162),
               (182, 182, 182),
               (203, 203, 203),
               (227, 227, 227),
               (255, 255, 255),
               (0, 0, 255),
               (65, 0, 255),
               (125, 0, 255),
               (190, 0, 255),
               (255, 0, 255),
               (255, 0, 190),
               (255, 0, 125),
               (255, 0, 65),
               (255, 0, 0),
               (255, 65, 0),
               (255, 125, 0),
               (255, 190, 0),
               (255, 255, 0),
               (190, 255, 0),
               (125, 255, 0),
               (65, 255, 0),
               (0, 255, 0),
               (0, 255, 65),
               (0, 255, 125),
               (0, 255, 190),
               (0, 255, 255),
               (0, 190, 255),
               (0, 125, 255),
               (0, 65, 255),
               (125, 125, 255),
               (158, 125, 255),
               (190, 125, 255),
               (223, 125, 255),
               (255, 125, 255),
               (255, 125, 223),
               (255, 125, 190),
               (255, 125, 158),
               (255, 125, 125),
               (255, 158, 125),
               (255, 190, 125),
               (255, 223, 125),
               (255, 255, 125),
               (223, 255, 125),
               (190, 255, 125),
               (158, 255, 125),
               (125, 255, 125),
               (125, 255, 158),
               (125, 255, 190),
               (125, 255, 223),
               (125, 255, 255),
               (125, 223, 255),
               (125, 190, 255),
               (125, 158, 255),
               (182, 182, 255),
               (199, 182, 255),
               (219, 182, 255),
               (235, 182, 255),
               (255, 182, 255),
               (255, 182, 235),
               (255, 182, 219),
               (255, 182, 199),
               (255, 182, 182),
               (255, 199, 182),
               (255, 219, 182),
               (255, 235, 182),
               (255, 255, 182),
               (235, 255, 182),
               (219, 255, 182),
               (199, 255, 182),
               (182, 255, 182),
               (182, 255, 199),
               (182, 255, 219),
               (182, 255, 235),
               (182, 255, 255),
               (182, 235, 255),
               (182, 219, 255),
               (182, 199, 255),
               (0, 0, 113),
               (28, 0, 113),
               (56, 0, 113),
               (85, 0, 113),
               (113, 0, 113),
               (113, 0, 85),
               (113, 0, 56),
               (113, 0, 28),
               (113, 0, 0),
               (113, 28, 0),
               (113, 56, 0),
               (113, 85, 0),
               (113, 113, 0),
               (85, 113, 0),
               (56, 113, 0),
               (28, 113, 0),
               (0, 113, 0),
               (0, 113, 28),
               (0, 113, 56),
               (0, 113, 85),
               (0, 113, 113),
               (0, 85, 113),
               (0, 56, 113),
               (0, 28, 113),
               (56, 56, 113),
               (69, 56, 113),
               (85, 56, 113),
               (97, 56, 113),
               (113, 56, 113),
               (113, 56, 97),
               (113, 56, 85),
               (113, 56, 69),
               (113, 56, 56),
               (113, 69, 56),
               (113, 85, 56),
               (113, 97, 56),
               (113, 113, 56),
               (97, 113, 56),
               (85, 113, 56),
               (69, 113, 56),
               (56, 113, 56),
               (56, 113, 69),
               (56, 113, 85),
               (56, 113, 97),
               (56, 113, 113),
               (56, 97, 113),
               (56, 85, 113),
               (56, 69, 113),
               (81, 81, 113),
               (89, 81, 113),
               (97, 81, 113),
               (105, 81, 113),
               (113, 81, 113),
               (113, 81, 105),
               (113, 81, 97),
               (113, 81, 89),
               (113, 81, 81),
               (113, 89, 81),
               (113, 97, 81),
               (113, 105, 81),
               (113, 113, 81),
               (105, 113, 81),
               (97, 113, 81),
               (89, 113, 81),
               (81, 113, 81),
               (81, 113, 89),
               (81, 113, 97),
               (81, 113, 105),
               (81, 113, 113),
               (81, 105, 113),
               (81, 97, 113),
               (81, 89, 113),
               (0, 0, 65),
               (16, 0, 65),
               (32, 0, 65),
               (48, 0, 65),
               (65, 0, 65),
               (65, 0, 48),
               (65, 0, 32),
               (65, 0, 16),
               (65, 0, 0),
               (65, 16, 0),
               (65, 32, 0),
               (65, 48, 0),
               (65, 65, 0),
               (48, 65, 0),
               (32, 65, 0),
               (16, 65, 0),
               (0, 65, 0),
               (0, 65, 16),
               (0, 65, 32),
               (0, 65, 48),
               (0, 65, 65),
               (0, 48, 65),
               (0, 32, 65),
               (0, 16, 65),
               (32, 32, 65),
               (40, 32, 65),
               (48, 32, 65),
               (56, 32, 65),
               (65, 32, 65),
               (65, 32, 56),
               (65, 32, 48),
               (65, 32, 40),
               (65, 32, 32),
               (65, 40, 32),
               (65, 48, 32),
               (65, 56, 32),
               (65, 65, 32),
               (56, 65, 32),
               (48, 65, 32),
               (40, 65, 32),
               (32, 65, 32),
               (32, 65, 40),
               (32, 65, 48),
               (32, 65, 56),
               (32, 65, 65),
               (32, 56, 65),
               (32, 48, 65),
               (32, 40, 65),
               (44, 44, 65),
               (48, 44, 65),
               (52, 44, 65),
               (60, 44, 65),
               (65, 44, 65),
               (65, 44, 60),
               (65, 44, 52),
               (65, 44, 48),
               (65, 44, 44),
               (65, 48, 44),
               (65, 52, 44),
               (65, 60, 44),
               (65, 65, 44),
               (60, 65, 44),
               (52, 65, 44),
               (48, 65, 44),
               (44, 65, 44),
               (44, 65, 48),
               (44, 65, 52),
               (44, 65, 60),
               (44, 65, 65),
               (44, 60, 65),
               (44, 52, 65),
               (44, 48, 65),
               (0, 0, 0),
               (0, 0, 0),
               (0, 0, 0),
               (0, 0, 0),
               (0, 0, 0),
               (0, 0, 0),
               (0, 0, 0),
               (0, 0, 0)]


def build_palette(step):
    return vga_palette
    
    "build a palette. that is a list with 256 RGB triplets"
    loop = range(256)
    #first we create a 256-element array. it goes from 0, to 255, and back to 0
    ramp = [abs((x+step*3)%511-255) for x in loop]
    #using the previous ramp and some other crude math, we make some different
    #values for each R, G, and B color planes
    return [(ramp[x], ramp[(x+32)%256], (x+step)%256) for x in loop]

class BitmappyLegacySprite(RootSprite):
    def __init__(self, filename, palette, *args, **kwargs):
        super().__init__(*args, width=0, height=0, **kwargs)
        self.image = None
        self.rect = None
        self.name = None
        self.palette = palette

        (self.image, self.rect, self.name) = self.load(filename=filename, palette=1, width=32, height=32)

        self.save(filename + '.cfg')

    def load(self, filename, palette, width, height):
        """
        """
        # We need to load an 8-bit palette for color conversion.
        #image = pygame.Surface((width, height), 0, 8)
        palette = build_palette(palette)
        image = None
        rect = None
        name = None
        data = []
        rgb_pixels = []

        # Load the raw bits in.
        with open(filename, 'rb') as fh:
            data = fh.read()

        # Unpack the bytes.
        # Read 1 byte, unsigned.
        indexed_rgb_data = struct.iter_unpack('<B', data)

        pixels = self.indexed_rgb_triplet_generator(data=indexed_rgb_data)

        pixels = [pixel for pixel in pixels]

        for pixel in pixels[0:width*height]:
            rgb_pixels.append(palette[pixel])

        (image, rect) = self.inflate(width=width,
                                     height=height,
                                     pixels=rgb_pixels)

        return (image, rect, filename)

    def indexed_rgb_triplet_generator(self, data):
        try:
            for datum in data:
                yield datum[0]
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
        self.palette = options.get('palette')

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

        group.add_argument('--palette',
                           type=int,
                           default=0)

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
        self.active_scene = GameScene(filename=self.filename, palette=self.palette)

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
