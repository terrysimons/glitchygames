#!/usr/bin/env python3
"""GlitchyGames palette module.

palette: Manages the custom color palette file format used by the engine.
"""

from __future__ import annotations

import configparser
import sys
from pathlib import Path
from typing import ClassVar, Optional, Self

from pygame import Color

VGA = 'vga'
SYSTEM = 'system'
NES = 'nes'


class ColorPalette:
    """Manages color palette data for Glitchy Games."""

    _BUILTIN_PALETTE_LOCATION: ClassVar = Path(__file__).parent / 'resources'
    _DEFAULT_EXTENSION: ClassVar = 'palette'

    def __init__(
        self: Self, colors: Optional(list | None) = None, filename: Optional(str, None) = None
    ) -> None:
        """Create a color palette object.

        Args:
            colors: A list of PyGame Colors.  Default: None
            filename: The name of the palette file to load.  Default: None
        """
        self._colors = None

        if colors:
            self._colors = colors
        elif filename:
            script_path = Path(sys.argv[0]).parent
            paths = [self._BUILTIN_PALETTE_LOCATION, script_path, Path(script_path) / 'resources']
            for path in paths:
                file_path = Path(path) / f'{filename}.{self._DEFAULT_EXTENSION}'
                if Path.exists(file_path):
                    self._colors = PaletteUtility.load_palette_from_file(file_path)
                    break
        else:
            self._colors = []

        self._size = 0
        if self._colors:
            self._size = len(self._colors) - 1

    def get_color(self: Self, palette_index: int) -> tuple[int, int, int]:
        """Returns PyGame Color from the palette at the specified index.

        Args:
            palette_index: The index of the color to return.

        Returns:
            A PyGame Color object in the format tuple[R: int, G: int, B: int]
        """
        if self._size:
            return self._colors[palette_index] if palette_index <= self._size else None

        # Return Magenta if our palette isn't set
        return (255, 0, 255)

    def set_color(self: Self, palette_index: int, new_color: tuple) -> None:
        """Sets the indexed color to the new PyGame Color.

        Args:
            palette_index: The index of the color to set.
            new_color: A PyGame Color object in the format tuple[R: int, G: int, B: int]

        Returns:
            None
        """
        if palette_index < self._size:
            self._colors[palette_index] = new_color
        else:
            self._colors.append(new_color)


class PaletteUtility:
    """Utility class for working with Glitchy Games palettes."""

    @staticmethod
    def load_palette_from_config(config: dict) -> list:
        """Load a palette from a ConfigParser object.

        Args:
            config: A ConfigParser object containing palette data.

        Returns:
            A list of PyGame Colors in the format list[tuple[R: int, G: int, B: int]].
        """
        colors = []
        for index in range(int(config['default']['colors'])):
            color_index = str(index)
            tmp_color = Color(
                config[color_index].getint('red'),
                config[color_index].getint('green'),
                config[color_index].getint('blue'),
                config[color_index].getint('alpha', 255),
            )
            colors.append(tmp_color)

        return colors

    @staticmethod
    def load_palette_from_file(config_file_path: str) -> list:
        """Load a palette from a GlitchyGames palette file.

        Args:
            config_file_path: The path to the palette file to load.

        Returns:
            A list of PyGame Colors in the format list[tuple[R: int, G: int, B: int]].
        """
        config = configparser.ConfigParser()
        # Read contents of file and close after
        with Path.open(config_file_path) as file_obj:
            config.read_file(file_obj)
        return PaletteUtility.load_palette_from_config(config)

    @staticmethod
    def write_palette_to_file(config_data: dict, output_file: str) -> None:
        """Write a GlitchyGames palette to a file.

        Args:
            config_data: A ConfigParser object containing palette data.
            output_file: The path to the palette file to write.

        Returns:
            None
        """
        with Path.open(output_file, 'w') as file_obj:
            # MTS: This looks backwards?  Should it be config_data.write(file_obj)?
            # seems like it should be file_obj.write(config_data)
            config_data.write(file_obj)

    @staticmethod
    def parse_rgb_data_in_file(rgb_data_file: str) -> list:
        """Read RGB data from a file.

        Args:
            rgb_data_file: The path to the file containing RGB data.

        Returns:
            A list of PyGame Colors in the format list[tuple[R: int, G: int, B: int]].
        """
        # Read input RGBA Values from file.  No duplicates
        colors = []
        with Path.open(rgb_data_file) as file_obj:
            for line in file_obj.readlines():
                tmp = [int(x) for x in line.strip().split(',')]
                color = Color(*tmp)
                if color not in colors:
                    colors.append(color)
        return colors

    @staticmethod
    def create_palette_data(colors: list) -> configparser.ConfigParser:
        """Create a ConfigParser object containing palette data from a list of PyGame Colors.

        Args:
            colors: A list of PyGame Colors in the format list[tuple[R: int, G: int, B: int]].

        Returns:
            A ConfigParser object containing palette data.
        """
        palette_data = configparser.ConfigParser()
        palette_data['default'] = {'colors': str(len(colors))}
        for count, color in enumerate(colors):
            palette_data[str(count)] = {
                'red': color.r,
                'green': color.g,
                'blue': color.b,
                'alpha': color.a,
            }
        return palette_data


# A Custom Color palette with named colors
class Default(ColorPalette):
    """A default set of colors used for Glitchy Games Examples."""

    def __init__(self: Self) -> None:
        """Create a default color palette object.

        Returns:
            None
        """
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
    """A palette representing the 16 default system colors."""

    def __init__(self: Self) -> None:
        """Create a system color palette object.

        Returns:
            None
        """
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
    """The 256 VGA color palette."""

    def __init__(self: Self) -> None:
        """Create a VGA color palette object.

        Returns:
            None
        """
        super().__init__(filename=VGA)
        # TODO @<sabadam32@gmail.com>: Set Color Names (See rich.color for list of names to poach)
        # https://glitchy-games.atlassian.net/browse/GG-21
