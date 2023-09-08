# GlitchyGames
# palette: Manages the custom color palette file format used by the engine

from __future__ import annotations

import configparser
import os.path
import sys
from typing import ClassVar, Optional, Self

from pygame import Color

VGA = 'vga'
SYSTEM = 'system'
NES = 'nes'


class ColorPalette:

    _BUILTIN_PALETTE_LOCATION: ClassVar = os.path.join(os.path.dirname(__file__), 'resources')
    _DEFAULT_EXTENSION: ClassVar = 'palette'

    def __init__(self: Self, colors: Optional(list | None) = None,
                 filename: Optional(str, None) = None) -> None:
        self._colors = None

        if colors:
            self._colors = colors
        elif filename:
            script_path = os.path.dirname(sys.argv[0])
            paths = [self._BUILTIN_PALETTE_LOCATION,
                     script_path,
                     os.path.join(script_path, 'resources')
                     ]
            for path in paths:
                file_path = os.path.join(path, f'{filename}.{self._DEFAULT_EXTENSION}')
                if os.path.exists(file_path):
                    self._colors = PaletteUtility.load_palette_from_file(file_path)
                    break
        else:
            self._colors = []

        self._size = 0
        if self._colors:
            self._size = len(self._colors) - 1

    def get_color(self, palette_index):
        """Returns PyGame Color at index"""
        if self._size:
            return self._colors[palette_index] if palette_index <= self._size else None

        # Return Magenta if our palette isn't set
        return (255, 0, 255)

    def set_color(self, palette_index, new_color):
        """Sets the indexed color to the new PyGame Color"""
        if palette_index < self._size:
            self._colors[palette_index] = new_color
        else:
            self._colors.append(new_color)


class PaletteUtility:

    @staticmethod
    def load_palette_from_config(config):
        """Load a palette from a ConfigParser object. Returns a list of PyGame Colors"""
        colors = []
        for index in range(int(config['default']['colors'])):
            color_index = str(index)
            tmp_color = Color(
                config[color_index].getint('red'),
                config[color_index].getint('green'),
                config[color_index].getint('blue'),
                config[color_index].getint('alpha', 255)
            )
            colors.append(tmp_color)

        return colors

    @staticmethod
    def load_palette_from_file(config_file_path):
        """Load a palette from a GlitchyGames palette file. Returns a list of PyGame Colors"""
        config = configparser.ConfigParser()
        # Read contents of file and close after
        with open(config_file_path) as file_obj:
            config.read_file(file_obj)
        return PaletteUtility.load_palette_from_config(config)

    @staticmethod
    def write_palette_to_file(config_data, output_file):
        """ Write a GlitchyGames palette to a file"""
        with open(output_file, 'w') as file_obj:
            config_data.write(file_obj)

    @staticmethod
    def parse_rgb_data_in_file(rgb_data_file):
        """Read RGB data from a file. Returns a list of PyGame Colors"""
        # Read input RGBA Values from file.  No duplicates
        colors = []
        with open(rgb_data_file) as file_obj:
            for line in file_obj.readlines():
                tmp = [int(x) for x in line.strip().split(',')]
                color = Color(*tmp)
                if color not in colors:
                    colors.append(color)
        return colors

    @staticmethod
    def create_palette_data(colors):
        """Create a ConfigParser object containing palette data from a list of PyGame Colors.

        Returns a ConfigParser

        """

        palette_data = configparser.ConfigParser()
        palette_data['default'] = {'colors': str(len(colors))}
        for count, color in enumerate(colors):
            palette_data[str(count)] = {
                'red': color.r,
                'green': color.g,
                'blue': color.b,
                'alpha': color.a
            }
        return palette_data


# A Custom Color palette with named colors
class Default(ColorPalette):
    """A default set of colors used for Glitchy Games Examples"""
    def __init__(self: Self) -> None:
        super().__init__(filename='default')
        self.YELLOW = self.get_color(0)
        self.PURPLE = self.get_color(1)
        self.BLUE = self.get_color(2)
        self.GREEN = self.get_color(3)
        self.WHITE = self.get_color(4)
        self.BLACK = self.get_color(5)
        self.BLACKLUCENT = self.get_color(6)
        self.BLUELUCENT = self.get_color(7)
        self.RED = self.get_color(8)


class System(ColorPalette):
    """A palette representing the 16 default system colors"""
    def __init__(self: Self) -> None:
        super().__init__(filename=SYSTEM)
        self.BLACK = self.get_color(0)
        self.MAROON = self.get_color(1)
        self.GREEN = self.get_color(2)
        self.OLIVE = self.get_color(3)
        self.NAVY = self.get_color(4)
        self.PURPLE = self.get_color(5)
        self.TEAL = self.get_color(6)
        self.SILVER = self.get_color(7)
        self.GREY = self.get_color(8)
        self.RED = self.get_color(9)
        self.LIME = self.get_color(10)
        self.YELLOW = self.get_color(11)
        self.BLUE = self.get_color(12)
        self.MAGENTA = self.get_color(13)
        self.CYAN = self.get_color(14)
        self.WHITE = self.get_color(15)


class Vga(ColorPalette):
    """The 256 VGA color palette"""

    def __init__(self: Self) -> None:
        super().__init__(filename=VGA)
        # TODO @<sabadam32@gmail.com>: Set Color Names (See rich.color for list of names to poach)
        # https://glitchy-games.atlassian.net/browse/GG-21
