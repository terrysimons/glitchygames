"""Test that save/load operations preserve pixel data correctly."""

import re
import tempfile
import tomllib
from pathlib import Path

from glitchygames.sprites.animated import AnimatedSprite, toml_pixel_block


def _strip_hitbox_sections(content: str) -> str:
    """Remove hitbox sections from TOML content for comparison.

    Strips [sprite.hitbox] and [animation.frame.hitbox] sections
    including their key-value pairs, so pixel preservation can be
    compared independently of auto-computed hitbox data.
    """
    # Remove [sprite.hitbox] and [animation.frame.hitbox] sections
    # Each section is a header followed by key=value lines until the next section or blank line
    pattern = r'\n?\[(?:sprite|animation\.frame)\.hitbox\]\n(?:[\w_]+ = \d+\n)*\n?'
    stripped = re.sub(pattern, '\n', content)
    # Collapse multiple blank lines to single
    stripped = re.sub(r'\n{3,}', '\n\n', stripped)
    return stripped.rstrip('\n')


# Candle sprite content from user
CANDLE_SPRITE_CONTENT = """[sprite]
name = "candle"
description = \"\"\"A 12 frame candle animation 16x16 pixels. \"\"\"

[[animation]]
namespace = "burn"
frame_interval = 0.5
loop = true

[[animation.frame]]
namespace = "burn"
frame_index = 0
pixels = \"\"\"
████████████████
████████████████
████████████████
███████..███████
██████.aa.██████
██████.aa.██████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 1
pixels = \"\"\"
████████████████
████████████████
███████.████████
██████.a.███████
██████.aa.██████
█████.aaaa.█████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 2
pixels = \"\"\"
████████████████
████████████████
████████.███████
███████.a.██████
██████.aaa.█████
██████.aaa.█████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 3
pixels = \"\"\"
████████████████
████████████████
███████.████████
██████.a.███████
██████.aa.██████
█████.aaaa.█████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 4
pixels = \"\"\"
████████████████
████████████████
████████████████
███████..███████
██████.aa.██████
██████.aa.██████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 5
pixels = \"\"\"
████████████████
████████████████
████████████████
██████..████████
██████.aa.██████
█████.aaaa.█████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 6
pixels = \"\"\"
████████████████
████████████████
████████████████
███████..███████
██████.aa.██████
██████.aa.██████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 7
pixels = \"\"\"
████████████████
████████████████
███████.████████
██████.a.███████
█████.aaa.██████
█████.aaa.██████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 8
pixels = \"\"\"
████████████████
████████████████
████████.███████
███████.a.██████
██████.aaa.█████
█████.aaaa.█████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 9
pixels = \"\"\"
████████████████
████████████████
███████.████████
██████.a.███████
██████.aa.██████
█████.aaaa.█████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 10
pixels = \"\"\"
████████████████
████████████████
████████████████
███████..███████
██████.aa.██████
██████.aa.██████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 11
pixels = \"\"\"
████████████████
████████████████
████████████████
██████..████████
█████.aaa.██████
█████.aaa.██████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[colors]
[colors."█"]
red = 255
green = 0
blue = 255

[colors."."]
red = 255
green = 200
blue = 0

[colors."a"]
red = 255
green = 150
blue = 0

[colors."A"]
red = 200
green = 100
blue = 0

[colors."b"]
red = 50
green = 40
blue = 30

[colors."B"]
red = 80
green = 60
blue = 40

[colors."c"]
red = 100
green = 80
blue = 50

[colors."C"]
red = 0
green = 0
blue = 0
"""

# Candle sprite with alpha section - all colors should have alpha fields when saved
CANDLE_SPRITE_WITH_ALPHA_CONTENT = """[sprite]
name = "candle"
description = \"\"\"A 12 frame candle animation 16x16 pixels. \"\"\"

[[animation]]
namespace = "burn"
frame_interval = 0.5
loop = true

[[animation.frame]]
namespace = "burn"
frame_index = 0
pixels = \"\"\"
████████████████
████████████████
████████████████
███████..███████
██████.aa.██████
██████.aa.██████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBddBb█████
█████bBddBb█████
█████bBddBb█████
█████bBddBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 1
pixels = \"\"\"
████████████████
████████████████
███████.████████
██████.a.███████
██████.aa.██████
█████.aaaa.█████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 2
pixels = \"\"\"
████████████████
████████████████
████████.███████
███████.a.██████
██████.aaa.█████
██████.aaa.█████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 3
pixels = \"\"\"
████████████████
████████████████
███████.████████
██████.a.███████
██████.aa.██████
█████.aaaa.█████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 4
pixels = \"\"\"
████████████████
████████████████
████████████████
███████..███████
██████.aa.██████
██████.aa.██████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 5
pixels = \"\"\"
████████████████
████████████████
████████████████
██████..████████
██████.aa.██████
█████.aaaa.█████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 6
pixels = \"\"\"
████████████████
████████████████
████████████████
███████..███████
██████.aa.██████
██████.aa.██████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 7
pixels = \"\"\"
████████████████
████████████████
███████.████████
██████.a.███████
█████.aaa.██████
█████.aaa.██████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 8
pixels = \"\"\"
████████████████
████████████████
████████.███████
███████.a.██████
██████.aaa.█████
█████.aaaa.█████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 9
pixels = \"\"\"
████████████████
████████████████
███████.████████
██████.a.███████
██████.aa.██████
█████.aaaa.█████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 10
pixels = \"\"\"
████████████████
████████████████
████████████████
███████..███████
██████.aa.██████
██████.aa.██████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[[animation.frame]]
namespace = "burn"
frame_index = 11
pixels = \"\"\"
████████████████
████████████████
████████████████
██████..████████
█████.aaa.██████
█████.aaa.██████
█████.aaaa.█████
█████.aAAa.█████
█████.aAAa.█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████bBccBb█████
█████CCCCCC█████
█████CCCCCC█████
████████████████
\"\"\"

[colors]
[colors."█"]
red = 255
green = 0
blue = 255

[colors."."]
red = 255
green = 200
blue = 0

[colors."a"]
red = 255
green = 150
blue = 0

[colors."A"]
red = 200
green = 100
blue = 0

[colors."b"]
red = 50
green = 40
blue = 30

[colors."B"]
red = 80
green = 60
blue = 40

[colors."c"]
red = 100
green = 80
blue = 50

[colors."C"]
red = 0
green = 0
blue = 0

[colors."d"]
red = 100
green = 80
blue = 50
alpha = 200
"""


class TestSaveLoadPixelPreservation:
    """Test that save/load operations preserve pixel data correctly."""

    def test_candle_sprite_save_load_preserves_pixels(self):
        """Test that loading, saving, and reloading a candle sprite preserves all pixels."""
        # Create temporary file with candle sprite
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.toml',
            delete=False,
            encoding='utf-8',
        ) as f:
            temp_input = f.name
            f.write(CANDLE_SPRITE_CONTENT)

        # Create temporary file for save output
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.toml',
            delete=False,
            encoding='utf-8',
        ) as f:
            temp_output = f.name

        try:
            # Read original file content
            original_content = Path(temp_input).read_text(encoding='utf-8')

            # Load using existing AnimatedSprite load method
            from glitchygames.sprites import AnimatedSprite

            sprite = AnimatedSprite(filename=temp_input)

            # Save using existing AnimatedSprite save method
            sprite.save(temp_output, 'toml')

            # Read saved file content
            saved_content = Path(temp_output).read_text(encoding='utf-8')

            # Compare content, stripping auto-computed hitbox sections
            # (the save pipeline now auto-computes hitboxes for sprites
            # that don't have them, so the saved output includes
            # [sprite.hitbox] and [animation.frame.hitbox] sections)
            original_normalized = _strip_hitbox_sections(original_content)
            saved_normalized = _strip_hitbox_sections(saved_content)
            assert original_normalized == saved_normalized, (
                'Saved file should match original file (ignoring hitbox sections).\n'
                f'Original length: {len(original_content)} '
                f'(normalized: {len(original_normalized)})\n'
                f'Saved length: {len(saved_content)} '
                f'(normalized: {len(saved_normalized)})'
            )

        finally:
            # Clean up
            for temp_file in [temp_input, temp_output]:
                temp_path = Path(temp_file)
                if temp_path.exists():
                    temp_path.unlink()

    def test_candle_sprite_with_alpha_section_preserves_alpha_fields(self):
        """Test that colors with alpha=0-254 (per-pixel alpha) are preserved when saved."""
        # Create temporary file with candle sprite that has
        # color 'd' with alpha=200 (per-pixel alpha)
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.toml',
            delete=False,
            encoding='utf-8',
        ) as f:
            temp_input = f.name
            f.write(CANDLE_SPRITE_WITH_ALPHA_CONTENT)

        # Create temporary file for save output
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.toml',
            delete=False,
            encoding='utf-8',
        ) as f:
            temp_output = f.name

        try:
            # Load using existing AnimatedSprite load method
            from glitchygames.sprites import AnimatedSprite

            sprite = AnimatedSprite(filename=temp_input)

            # Save using existing AnimatedSprite save method
            sprite.save(temp_output, 'toml')

            # Read saved file content
            saved_content = Path(temp_output).read_text(encoding='utf-8')

            # Color 'd' should have alpha field with value 200 (per-pixel alpha preserved)
            import re

            d_color_match = re.search(r'\[colors\."d"\][\s\S]*?(?=\[|$)', saved_content)
            assert d_color_match is not None, "Color 'd' should be present in saved file"
            d_section = d_color_match.group(0)
            assert 'alpha = 200' in d_section, (
                f"Color 'd' should have alpha=200 preserved. Section:\n{d_section}"
            )

            # Should NOT have [alpha] section (that format is deprecated)
            assert '[alpha]' not in saved_content, (
                'Should not have [alpha] section - use per-color alpha fields instead'
            )

        finally:
            # Clean up
            for temp_file in [temp_input, temp_output]:
                temp_path = Path(temp_file)
                if temp_path.exists():
                    temp_path.unlink()


# Glyphs that TOML gives meaning to inside a """ string. Written escaped here, as a file must
# write them: '\\' is a backslash glyph and '\"' a quote glyph
ESCAPE_GLYPH_COLORS_TOML = (
    '[colors."\\\\"]\nred = 200\ngreen = 10\nblue = 10\n\n'
    '[colors."\\""]\nred = 10\ngreen = 200\nblue = 10\n\n'
    '[colors."b"]\nred = 10\ngreen = 10\nblue = 200\n'
)
# Rows: 'b\' (ends in a backslash glyph, which unescaped joins the next row), 'bbb',
# '"""' (three quote glyphs, which unescaped end the string)
ESCAPE_GLYPH_ROWS_TOML = 'b\\\\\nbbb\n\\"\\"\\"\n'


class TestPixelRowsSurviveTomlEscapes:
    """Saving escapes pixel rows and palette keys, so TOML's own characters can be glyphs."""

    @staticmethod
    def _save_and_reload(
        tmp_path: Path, toml_content: str
    ) -> tuple[AnimatedSprite, AnimatedSprite]:
        original_file = tmp_path / 'original.toml'
        original_file.write_text(toml_content, encoding='utf-8')
        original = AnimatedSprite(str(original_file))
        saved_file = tmp_path / 'saved.toml'
        original.save(str(saved_file), 'toml')
        return original, AnimatedSprite(str(saved_file))

    def test_backslash_glyph_round_trips(self, tmp_path):
        """An animated sprite with a row ending in a backslash glyph saves and reloads as is."""
        frame = (
            f'[[animation.frame]]\nframe_index = 0\npixels = """\n{ESCAPE_GLYPH_ROWS_TOML}"""\n\n'
        )
        toml_content = (
            '[sprite]\nname = "escapes"\n\n'
            '[[animation]]\nnamespace = "walk"\nframe_interval = 1\n\n'
            f'{frame}{frame}{ESCAPE_GLYPH_COLORS_TOML}'
        )
        original, reloaded = self._save_and_reload(tmp_path, toml_content)
        original_frame = original.animation_data['walk'][0]
        reloaded_frame = reloaded.animation_data['walk'][0]
        assert reloaded_frame.image.get_size() == original_frame.image.get_size() == (3, 3)
        assert reloaded_frame.pixels == original_frame.pixels
        assert reloaded.pixel_row_repairs == []

    def test_quote_glyph_round_trips(self, tmp_path):
        """A static sprite with a row of three quote glyphs saves and reloads as is."""
        toml_content = (
            f'[sprite]\nname = "quotes"\npixels = """\n{ESCAPE_GLYPH_ROWS_TOML}"""\n\n'
            f'{ESCAPE_GLYPH_COLORS_TOML}'
        )
        original, reloaded = self._save_and_reload(tmp_path, toml_content)
        original_frame = original.get_current_frame()
        reloaded_frame = reloaded.get_current_frame()
        assert original_frame is not None
        assert reloaded_frame is not None
        assert reloaded_frame.pixels == original_frame.pixels
        assert reloaded.pixel_row_repairs == []

    def test_toml_pixel_block_escapes(self):
        """Each row is escaped like a basic string, and the newlines between rows stay real."""
        assert toml_pixel_block('a\\b\n"c') == '"""\na\\\\b\n\\"c\n"""'
        assert toml_pixel_block('ab\n') == '"""\nab\n"""'
        assert tomllib.loads(f'pixels = {toml_pixel_block("a\\\nb")}')['pixels'] == 'a\\\nb\n'
