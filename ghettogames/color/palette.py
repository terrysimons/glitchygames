from collections import deque
import configparser
import os.path
from pygame import Color

class ColorPalette:

    def __init__(self, colors):
        self._colors = deque(colors)
        self._size = len(colors)
        print( self._size, self._colors)

    def rotate(self):
        self._colors.rotate(1)

    def get_color(self, palette_index):
        if palette_index < self._size:
            return self._colors[palette_index]
        return None
    
    @staticmethod
    # Load a palette from a file.
    def load_palette(path):
        file_obj = path
        config = configparser.ConfigParser()
        config.read_file(file_obj)
        file_obj.close()
        colors = []
        for color in range(int(config['palette']['colors'])):
            color = str(color)
            tmp_color = Color(config[color].getint('red'), config[color].getint('green'), config[color].getint('blue'))
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
        config['palette'] = {"count": str(len(colors)) }
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
        super().__init__(self.load_palette('resources/NES.cfg'))


ColorPalette.create_palette(os.path.join(os.path.dirname(__file__), 'resources/test.txt'))