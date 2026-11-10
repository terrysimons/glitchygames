"""Tests for the GlitchyGames palette module (glitchygames/color/palette.py)."""

import configparser
import sys

import pytest
from pygame import Color

from glitchygames.color.palette import ColorPalette, Default, PaletteUtility, System, Vga

MAGENTA = Color(255, 0, 255)


def _write_palette_file(path, colors):
    """Write colors to path in the GlitchyGames palette (ConfigParser) format."""
    palette_data = PaletteUtility.create_palette_data(colors=colors)
    with path.open('w') as file_object:
        palette_data.write(file_object)


class TestColorPaletteLookup:
    """get_color answers from the palette, or magenta when no palette is loaded."""

    def test_palette_without_colors_or_file_answers_magenta(self):
        """With no colors and no file, every lookup answers the magenta 'unset' color."""
        palette = ColorPalette(colors=None)

        assert palette.get_color(palette_index=0) == MAGENTA
        assert palette.get_color(palette_index=99) == MAGENTA

    def test_missing_palette_file_leaves_the_palette_unset(self, tmp_path, monkeypatch):
        """A filename found in none of the search paths loads nothing (magenta answers)."""
        monkeypatch.setattr(sys, 'argv', [str(tmp_path / 'game.py')])

        palette = ColorPalette(colors=None, filename='no-such-palette')

        assert palette.get_color(palette_index=0) == MAGENTA

    def test_index_past_the_end_answers_none(self):
        """An index beyond the last color answers None, not an IndexError."""
        palette = ColorPalette(colors=[Color(1, 2, 3), Color(4, 5, 6)])

        assert palette.get_color(palette_index=1) == Color(4, 5, 6)
        assert palette.get_color(palette_index=2) is None

    def test_palette_file_is_found_in_the_scripts_resources_directory(self, tmp_path, monkeypatch):
        """After the built-in and script directories, the script's resources/ is searched."""
        resources_directory = tmp_path / 'resources'
        resources_directory.mkdir()
        _write_palette_file(
            path=resources_directory / 'mine.palette',
            colors=[Color(10, 20, 30), Color(40, 50, 60, 70)],
        )
        monkeypatch.setattr(sys, 'argv', [str(tmp_path / 'game.py')])

        palette = ColorPalette(colors=None, filename='mine')

        assert palette.get_color(palette_index=0) == Color(10, 20, 30)
        assert palette.get_color(palette_index=1) == Color(40, 50, 60, 70)

    def test_given_colors_win_over_a_filename(self):
        """A non-empty color list is used as-is; the filename is not loaded."""
        palette = ColorPalette(colors=[Color(1, 1, 1), Color(2, 2, 2)], filename='system')

        assert palette.get_color(palette_index=0) == Color(1, 1, 1)


class TestColorPaletteSetColor:
    """set_color replaces an existing entry or appends a new one."""

    def test_set_color_on_an_unset_palette_starts_a_color_list(self):
        """With no colors at all, set_color creates the list holding the new color."""
        palette = ColorPalette(colors=None)

        palette.set_color(palette_index=0, new_color=Color(9, 9, 9))

        assert palette._colors == [Color(9, 9, 9)]

    def test_set_color_replaces_an_entry_before_the_last(self):
        """An index before the last color replaces that color in place."""
        palette = ColorPalette(colors=[Color(1, 1, 1), Color(2, 2, 2), Color(3, 3, 3)])

        palette.set_color(palette_index=0, new_color=Color(7, 7, 7))

        assert palette.get_color(palette_index=0) == Color(7, 7, 7)
        assert palette._colors is not None
        assert len(palette._colors) == 3

    def test_set_color_replaces_the_last_entry(self):
        """The last index is replaced in place, not appended to (BUGS.md #103)."""
        palette = ColorPalette(colors=[Color(1, 1, 1), Color(2, 2, 2)])

        palette.set_color(palette_index=1, new_color=Color(7, 7, 7))

        assert palette._colors == [Color(1, 1, 1), Color(7, 7, 7)]

    def test_appended_color_can_be_read_back(self):
        """A color appended by set_color is seen by get_color (BUGS.md #103)."""
        palette = ColorPalette(colors=[Color(1, 1, 1), Color(2, 2, 2)])

        palette.set_color(palette_index=2, new_color=Color(8, 8, 8))

        assert palette.get_color(palette_index=2) == Color(8, 8, 8)
        assert palette.get_color(palette_index=3) is None

    def test_one_color_palette_answers_its_color(self):
        """A one-color palette answers that color, not magenta (BUGS.md #103)."""
        palette = ColorPalette(colors=[Color(5, 6, 7)])

        assert palette.get_color(palette_index=0) == Color(5, 6, 7)
        assert palette.get_color(palette_index=1) is None

    def test_set_color_past_the_end_appends(self):
        """An index past the last color appends the new color."""
        palette = ColorPalette(colors=[Color(1, 1, 1), Color(2, 2, 2)])

        palette.set_color(palette_index=5, new_color=Color(8, 8, 8))

        assert palette._colors == [Color(1, 1, 1), Color(2, 2, 2), Color(8, 8, 8)]


class TestPaletteUtility:
    """Reading, writing and building palette data."""

    def test_palette_data_round_trips_through_a_config(self):
        """create_palette_data then load_palette_from_config gives back the same colors."""
        colors = [Color(0, 0, 0), Color(255, 128, 1, 7)]

        palette_data = PaletteUtility.create_palette_data(colors=colors)

        assert palette_data['default']['colors'] == '2'
        assert PaletteUtility.load_palette_from_config(config=palette_data) == colors

    def test_missing_channels_default_to_opaque_black(self):
        """A color section without keys reads as (0, 0, 0, 255)."""
        config = configparser.ConfigParser()
        config.read_dict({'default': {'colors': '1'}, '0': {}})

        assert PaletteUtility.load_palette_from_config(config=config) == [Color(0, 0, 0, 255)]

    def test_palette_file_round_trips(self, tmp_path):
        """A palette written in ConfigParser format loads back from the file."""
        palette_path = tmp_path / 'round.palette'
        colors = [Color(3, 4, 5), Color(6, 7, 8, 9)]
        _write_palette_file(path=palette_path, colors=colors)

        assert PaletteUtility.load_palette_from_file(config_file_path=palette_path) == colors

    def test_written_palette_data_loads_back(self, tmp_path):
        """write_palette_to_file writes the format load_palette_from_file reads (BUGS.md #104)."""
        output_path = tmp_path / 'written.palette'
        colors = [Color(3, 4, 5), Color(6, 7, 8, 9)]

        PaletteUtility.write_palette_to_file(
            config_data=PaletteUtility.create_palette_data(colors=colors),
            output_file=output_path,
        )

        assert PaletteUtility.load_palette_from_file(config_file_path=output_path) == colors

    def test_written_palette_dictionary_loads_back(self, tmp_path):
        """A plain dictionary of sections is written in the same palette file format."""
        output_path = tmp_path / 'written.palette'
        palette_dictionary = {
            'default': {'colors': '1'},
            '0': {'red': '1', 'green': '2', 'blue': '3'},
        }

        PaletteUtility.write_palette_to_file(
            config_data=palette_dictionary, output_file=output_path
        )

        assert PaletteUtility.load_palette_from_file(config_file_path=output_path) == [
            Color(1, 2, 3, 255)
        ]

    def test_rgb_data_file_is_parsed_without_duplicates(self, tmp_path):
        """Each line is one color (RGB or RGBA); repeated colors are kept once, in order."""
        rgb_path = tmp_path / 'colors.txt'
        rgb_path.write_text('1,2,3\n4,5,6,7\n1,2,3\n')

        colors = PaletteUtility.parse_rgb_data_in_file(rgb_data_file=rgb_path)

        assert colors == [Color(1, 2, 3), Color(4, 5, 6, 7)]

    def test_rgb_data_file_with_a_bad_value_raises(self, tmp_path):
        """A non-numeric channel is a ValueError, not a silently skipped line."""
        rgb_path = tmp_path / 'bad.txt'
        rgb_path.write_text('1,two,3\n')

        with pytest.raises(ValueError, match='invalid literal'):
            PaletteUtility.parse_rgb_data_in_file(rgb_data_file=rgb_path)


class TestBuiltinPalettes:
    """The bundled palettes load from glitchygames/color/resources."""

    def test_system_palette_has_sixteen_colors(self):
        """The System palette loads all 16 entries of system.palette."""
        palette = System()

        assert palette._colors is not None
        assert len(palette._colors) == 16
        black = palette.BLACK
        assert black == Color(0, 0, 0)

    def test_system_color_names_match_their_colors(self):
        """Every named System color is the color its name says (BUGS.md #102)."""
        palette = System()

        named_colors = {
            'BLACK': palette.BLACK,
            'WHITE': palette.WHITE,
            'RED': palette.RED,
            'LIME': palette.LIME,
            'BLUE': palette.BLUE,
            'YELLOW': palette.YELLOW,
            'CYAN': palette.CYAN,
            'MAGENTA': palette.MAGENTA,
            'SILVER': palette.SILVER,
            'GREY': palette.GREY,
            'MAROON': palette.MAROON,
            'OLIVE': palette.OLIVE,
            'GREEN': palette.GREEN,
            'PURPLE': palette.PURPLE,
            'TEAL': palette.TEAL,
            'NAVY': palette.NAVY,
        }

        assert named_colors == {
            'BLACK': Color(0, 0, 0),
            'WHITE': Color(255, 255, 255),
            'RED': Color(255, 0, 0),
            'LIME': Color(0, 255, 0),
            'BLUE': Color(0, 0, 255),
            'YELLOW': Color(255, 255, 0),
            'CYAN': Color(0, 255, 255),
            'MAGENTA': Color(255, 0, 255),
            'SILVER': Color(192, 192, 192),
            'GREY': Color(128, 128, 128),
            'MAROON': Color(128, 0, 0),
            'OLIVE': Color(128, 128, 0),
            'GREEN': Color(0, 128, 0),
            'PURPLE': Color(128, 0, 128),
            'TEAL': Color(0, 128, 128),
            'NAVY': Color(0, 0, 128),
        }

    def test_default_color_names_match_their_colors(self):
        """YELLOW is yellow, GREEN green and BLACK opaque (BUGS.md #111: olive, cyan, alpha 0)."""
        palette = Default()

        named_colors = {
            'YELLOW': palette.YELLOW,
            'PURPLE': palette.PURPLE,
            'BLUE': palette.BLUE,
            'GREEN': palette.GREEN,
            'WHITE': palette.WHITE,
            'BLACK': palette.BLACK,
            'BLACKLUCENT': palette.BLACKLUCENT,
            'BLUELUCENT': palette.BLUELUCENT,
            'RED': palette.RED,
        }

        assert named_colors == {
            'YELLOW': Color(255, 255, 0, 255),
            'PURPLE': Color(121, 7, 242, 255),
            'BLUE': Color(0, 0, 255, 255),
            'GREEN': Color(0, 255, 0, 255),
            'WHITE': Color(255, 255, 255, 255),
            'BLACK': Color(0, 0, 0, 255),
            'BLACKLUCENT': Color(0, 0, 0, 127),
            'BLUELUCENT': Color(0, 96, 255, 127),
            'RED': Color(255, 0, 0, 255),
        }

    def test_vga_palette_has_256_colors(self):
        """The VGA palette loads 256 colors; index 256 is past the end."""
        palette = Vga()

        assert palette.get_color(palette_index=255) is not None
        assert palette.get_color(palette_index=256) is None
