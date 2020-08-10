# GhettoGames
# ColorPalette: Manages the custom color palette file format used by the engine
#
# A color palette is contained in a CFG file with each color having a section with the
# R,G,B,A values.  This is designed for learning purposes.  Palette files are stored in
# the resource folder.
from collections import deque
import configparser
import os.path
from pygame import Color


class ColorPalette:

    def __init__(self, colors):
        self._colors = deque(colors)
        self._size = len(colors)

    def rotate(self):
        self._colors.rotate(1)

    def get_color(self, palette_index):
        if palette_index < self._size:
            return self._colors[palette_index]
        return None
    
    @staticmethod
    # Load a palette from a file.
    def load_palette(path):
        file_obj = open(path)
        config = configparser.ConfigParser()
        config.read_file(file_obj)
        file_obj.close()
        colors = []
        for color_index in range(int(config['palette']['colors'])):
            color_index = str(color_index)
            tmp_color = Color(config[color_index].getint('red'), config[color_index].getint('green'), config[color_index].getint('blue'), config[color_index].getint('alpha', 255))
            colors.append(tmp_color)
        
        return colors
 
    @staticmethod
    # Create a palette file using rgb color codes in a file.  One R,G,B color per line.  No blank lines
    # You can set an alpha value also by specifying it as R,G,B,A instead
    def create_palette(path):

        # Read input RGBA Values from file.  No duplicates
        file_obj = open(path)
        config = configparser.ConfigParser()
        colors = []
        for line in file_obj.readlines():
            tmp = [int(x) for x in line.strip().split(',')]
            color = Color(*tmp)
            if color not in colors:
                colors.append(color)
        
        # Create palette data
        config['palette'] = {"colors": str(len(colors)) }
        for count, color in enumerate(colors):
            config[count] = {
                "red": color.r,
                "green": color.g,
                "blue": color.b,
                "alpha": color.a
            }
        # Write palette file
        config.write(open(path[0:-3]+'cfg', 'w'))


class NESColorPalette(ColorPalette):

    def __init__(self):
        super().__init__(self.load_palette(os.path.join(os.path.dirname(__file__), 'resources/NES.cfg')))


class Basic(ColorPalette):

    def __init__(self):
        super().__init__(self.load_palette(os.path.join(os.path.dirname(__file__), 'resources/basic.cfg')))
        self.YELLOW = self.get_color(0)
        self.PURPLE = self.get_color(1)
        self.BLUE = self.get_color(2)
        self.GREEN = self.get_color(3)
        self.WHITE = self.get_color(4)
        self.BLACK = self.get_color(5)
        self.BLACKLUCENT = self.get_color(6)
        self.BLUELUCENT = self.get_color(7)
        self.RED = self.get_color(8)
