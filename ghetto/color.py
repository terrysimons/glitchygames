from pygame import Color
from collections import deque

# Note: I want to handle this a bit differently.
YELLOW = Color(128, 128, 0, 255)
PURPLE = Color(121, 7, 242, 255)
BLUE = Color(0, 0, 255, 255)
GREEN = Color(0, 255, 255)
WHITE = Color(255, 255, 255, 255)
BLACK = Color(0, 0, 0, 0)
BLACKLUCENT = Color(0, 0, 0, 127)
BLUELUCENT = Color(0, 96, 255, 127)
RED = Color(255, 0, 0)


class ColorPallet:

    def __init__(self, colors):
        self._colors = deque(colors)
        self._size = len(colors)

    def rotate(self):
        self._colors.rotate(1)

    def get_color(self, ord):
        if ord < self._size:
            return self._colors[ord]
        return None

