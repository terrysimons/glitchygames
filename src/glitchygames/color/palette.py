# GhettoGames
# palette: Manages the custom color palette file format used by the engine
#
# A color palette is contained in a CFG file with each color having a section with the
# R,G,B,A values.  This is designed for learning purposes.  Palette files are stored in
# the resources folder.
from collections import deque
import configparser
import os.path
from pygame import Color


class ColorPalette:

    def __init__(self, colors):
        self._colors = deque(colors)
        self._size = len(colors)

    # Shift colors in palette by number of slots
    def rotate(self, slots=1):
        self._colors.rotate(slots)

    # Return PyGame Color object at palette index
    def get_color(self, palette_index):
        if palette_index < self._size:
            return self._colors[palette_index]
        return None

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
        for color_index in range(int(config['palette']['colors'])):
            color_index = str(color_index)
            tmp_color = Color(
                config[color_index].getint('red'),
                config[color_index].getint('green'),
                config[color_index].getint('blue'),
                config[color_index].getint('alpha', 255)
            )
            colors.append(tmp_color)

        return colors

    # Load a palette from a GhettoGames CFG file. Returns a list of PyGame Color objects
    @staticmethod
    def load_palette_from_file(config_file_path):
        config = configparser.ConfigParser()
        # Read contents of file and close after
        with open(config_file_path) as file_obj:
            config.read_file(file_obj)
        return PaletteUtility.load_palette_from_config(config)

    # Write a GhettoGames palette to a file.  output_file extension should be .cfg
    @staticmethod
    def write_palette_to_file(config_data, output_file, mode='w'):
        with open(output_file, mode) as file_obj:
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
        palette_data['palette'] = {"colors": str(len(colors))}
        for count, color in enumerate(colors):
            palette_data[count] = {
                "red": color.r,
                "green": color.g,
                "blue": color.b,
                "alpha": color.a
            }
        return palette_data


# Nintendo Entertainment System color palette
class NES(ColorPalette):

    def __init__(self):
        super().__init__(
            PaletteUtility.load_palette_from_file(
                os.path.join(
                    os.path.dirname(__file__),
                    'resources/NES.cfg'
                )
            )
        )


# A Custom Color palette with named colors
class Custom(ColorPalette):

    def __init__(self):
        super().__init__(
            PaletteUtility.load_palette_from_file(
                os.path.join(
                    os.path.dirname(__file__),
                    'resources/custom.cfg'
                )
            )
        )
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
        super().__init__(
            PaletteUtility.load_palette_from_file(
                os.path.join(
                    os.path.dirname(__file__),
                    'resources/system.cfg'
                )
            )
        )
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
class VGA(ColorPalette):
    def __init__(self):
        super().__init__(
            PaletteUtility.load_palette_from_file(
                os.path.join(
                    os.path.dirname(__file__),
                    'resources/vga.cfg'
                )
            )
        )
