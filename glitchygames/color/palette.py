#!/usr/bin/env python3
"""GlitchyGames palette module.

palette: Manages the custom color palette file format used by the engine.
"""

from __future__ import annotations

import configparser
import json
import sys
from pathlib import Path
from typing import Any, ClassVar, Self, cast

from pygame import Color

# A color-like value: either a pygame Color or an RGB/RGBA tuple.
ColorLike = Color | tuple[int, int, int] | tuple[int, int, int, int]

VGA = 'vga'
SYSTEM = 'system'
NES = 'nes'


class ColorPalette:
    """Manages color palette data for Glitchy Games."""

    _BUILTIN_PALETTE_LOCATION: ClassVar = Path(__file__).parent / 'resources'
    _DEFAULT_EXTENSION: ClassVar = 'palette'

    def __init__(self: Self, colors: list[ColorLike] | None, filename: str | None = None) -> None:
        """Create a color palette object.

        Args:
            colors: A list of PyGame Colors or RGB/RGBA tuples.  Default: None
            filename: The name of the palette file to load.  Default: None

        """
        self._colors: list[ColorLike] | None = colors
        self._size = 0

        if not self._colors and filename:
            script_path = Path(sys.argv[0]).parent
            paths = [self._BUILTIN_PALETTE_LOCATION, script_path, Path(script_path) / 'resources']
            for path in paths:
                file_path = Path(path) / f'{filename}.{self._DEFAULT_EXTENSION}'
                if Path.exists(file_path):
                    self._colors = cast(
                        'list[ColorLike]',
                        PaletteUtility.load_palette_from_file(file_path),
                    )
                    break

        if self._colors:
            self._size = len(self._colors) - 1

    def get_color(self: Self, palette_index: int) -> ColorLike | None:
        """Return PyGame Color from the palette at the specified index.

        Args:
            palette_index: The index of the color to return.

        Returns:
            A PyGame Color object in the format tuple[R: int, G: int, B: int]

        """
        if self._size:
            return (
                self._colors[palette_index]
                if self._colors and palette_index <= self._size
                else None
            )

        # Return Magenta if our palette isn't set
        return Color(255, 0, 255)

    def set_color(self: Self, palette_index: int, new_color: ColorLike) -> None:
        """Set the indexed color to the new PyGame Color or RGB/RGBA tuple.

        Args:
            palette_index: The index of the color to set.
            new_color: A PyGame Color or RGB/RGBA tuple.

        """
        if self._colors is None:
            self._colors = []
        if palette_index < self._size:
            self._colors[palette_index] = new_color
        else:
            self._colors.append(new_color)


class PaletteUtility:
    """Utility class for working with Glitchy Games palettes."""

    @staticmethod
    def load_palette_from_config(config: configparser.ConfigParser) -> list[Color]:
        """Load a palette from a ConfigParser object.

        Args:
            config: A ConfigParser object containing palette data.

        Returns:
            A list of PyGame Colors in the format list[tuple[R: int, G: int, B: int]].

        """
        colors: list[Color] = []
        for index in range(int(config['default']['colors'])):
            color_index = str(index)
            section = config[color_index]
            tmp_color = Color(
                int(section.get('red', '0')),
                int(section.get('green', '0')),
                int(section.get('blue', '0')),
                int(section.get('alpha', '255')),
            )
            colors.append(tmp_color)

        return colors

    @staticmethod
    def load_palette_from_file(config_file_path: Path) -> list[Color]:
        """Load a palette from a GlitchyGames palette file.

        Args:
            config_file_path: The path to the palette file to load.

        Returns:
            A list of PyGame Colors in the format list[tuple[R: int, G: int, B: int]].

        """
        config = configparser.ConfigParser()
        # Read contents of file and close after
        with Path.open(Path(config_file_path)) as file_obj:
            config.read_file(file_obj)
        return PaletteUtility.load_palette_from_config(config)

    @staticmethod
    def write_palette_to_file(config_data: dict[str, Any], output_file: Path) -> None:
        """Write a GlitchyGames palette to a file.

        Args:
            config_data: A ConfigParser object containing palette data.
            output_file: The path to the palette file to write.

        """
        with Path.open(Path(output_file), 'w') as file_obj:
            file_obj.write(json.dumps(config_data))

    @staticmethod
    def parse_rgb_data_in_file(rgb_data_file: Path) -> list[Color]:
        """Read RGB data from a file.

        Args:
            rgb_data_file: The path to the file containing RGB data.

        Returns:
            A list of PyGame Colors in the format list[tuple[R: int, G: int, B: int]].

        """
        # Read input RGBA Values from file.  No duplicates
        colors: list[Color] = []
        with Path.open(rgb_data_file) as file_obj:
            for line in file_obj.readlines():
                tmp = [int(x) for x in line.strip().split(',')]
                color = Color(*tmp)
                if color not in colors:
                    colors.append(color)
        return colors

    @staticmethod
    def create_palette_data(colors: list[Color]) -> configparser.ConfigParser:
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
                'red': str(color.r),
                'green': str(color.g),
                'blue': str(color.b),
                'alpha': str(color.a),
            }
        return palette_data


# A Custom Color palette with named colors
class Default(ColorPalette):
    """A default set of colors used for Glitchy Games Examples."""

    def __init__(self: Self) -> None:
        """Create a default color palette object."""
        super().__init__(colors=[], filename='default')
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
        """Create a system color palette object."""
        super().__init__(colors=[], filename=SYSTEM)
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
        """Create a VGA color palette object."""
        super().__init__(colors=[], filename=VGA)
        # Color names not yet set. Tracked by GG-21:
        # https://glitchy-games.atlassian.net/browse/GG-21
