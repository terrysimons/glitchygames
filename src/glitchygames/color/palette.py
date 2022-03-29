# GlitchyGames
# palette: Manages the custom color palette file format used by the engine

import configparser
import os.path
import sys

from pygame import Color

VGA = 'vga'
SYSTEM = 'system'
NES = 'nes'


class ColorPalette:

    _BUILTIN_PALETTE_LOCATION = os.path.join(os.path.dirname(__file__), 'resources')
    _DEFAULT_EXTENSION = 'palette'

    def __init__(self, colors=None, filename=None):
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
        self._size = len(self._colors) - 1

    # Return PyGame Color object at palette index
    def get_color(self, palette_index):
        return self._colors[palette_index] if palette_index <= self._size else None

    # Replace color at palette index with a new PyGame color object
    def set_color(self, palette_index, new_color):
        if palette_index < self._size:
            self._colors[palette_index] = new_color
        else:
            self._colors.append(new_color)


class PaletteUtility:

    # Load a palette from a ConfigParser object. Returns a list of PyGame Color objects
    @staticmethod
    def load_palette_from_config(config):
        colors = []
        for color_index in range(int(config['default']['colors'])):
            color_index = str(color_index)
            tmp_color = Color(
                config[color_index].getint('red'),
                config[color_index].getint('green'),
                config[color_index].getint('blue'),
                config[color_index].getint('alpha', 255)
            )
            colors.append(tmp_color)

        return colors

    # Load a palette from a GlitchyGames CFG file. Returns a list of PyGame Color objects
    @staticmethod
    def load_palette_from_file(config_file_path):
        config = configparser.ConfigParser()
        # Read contents of file and close after
        with open(config_file_path) as file_obj:
            config.read_file(file_obj)
        return PaletteUtility.load_palette_from_config(config)

    # Write a GlitchyGames palette to a file
    @staticmethod
    def write_palette_to_file(config_data, output_file):
        with open(output_file, 'w') as file_obj:
            config_data.write(file_obj)

    # Read RGB data from a file, 1 per line. No blank lines. Use RGBA to specify transparency.
    # Returns a list of PyGame Colors
    @staticmethod
    def parse_rgb_data_in_file(rgb_data_file):
        # Read input RGBA Values from file.  No duplicates
        colors = []
        with open(rgb_data_file) as file_obj:
            for line in file_obj.readlines():
                tmp = [int(x) for x in line.strip().split(',')]
                color = Color(*tmp)
                if color not in colors:
                    colors.append(color)
        return colors

    # Create a ConfigParser object containing palette data.  Returns a ConfigParser
    @staticmethod
    def create_palette_data(colors):
        palette_data = configparser.ConfigParser()
        palette_data['default'] = {"colors": str(len(colors))}
        for count, color in enumerate(colors):
            palette_data[str(count)] = {
                "red": color.r,
                "green": color.g,
                "blue": color.b,
                "alpha": color.a
            }
        return palette_data


# A Custom Color palette with named colors
class Default(ColorPalette):

    def __init__(self):
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


# A palette representing the 16 default system colors
class System(ColorPalette):
    def __init__(self):
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


# The 256 VGA color palette
class Vga(ColorPalette):
    def __init__(self):
        super().__init__(filename=VGA)
