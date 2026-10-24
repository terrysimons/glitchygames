#!/usr/bin/env python3
"""Tests for RGB/RGBA auto-detection functionality in sprite system."""

import tempfile
from pathlib import Path

import pygame
import pytest

from glitchygames.sprites.animated import (
    AnimatedSprite,
    convert_pixels_to_rgb_if_possible,
    convert_pixels_to_rgba_if_needed,
    needs_alpha_channel,
)
from glitchygames.sprites.frame import SpriteFrame


def _frame_with_pixels(pixels, width=2):
    """Create a real SpriteFrame, ``width`` pixels wide, drawn with the given pixels.

    The surface has per-pixel alpha when any pixel has an alpha component.

    Returns:
        SpriteFrame: The frame (its ``pixels`` and its surface both hold the pixels).

    """
    height = len(pixels) // width
    has_alpha = any(len(pixel) == 4 for pixel in pixels)
    surface = pygame.Surface((width, height), pygame.SRCALPHA if has_alpha else 0)
    frame = SpriteFrame(surface)
    frame.set_pixel_data(pixels)
    return frame


def _drawn_over_black(image):
    """Blit an image onto opaque black and return what shows, row by row (RGB).

    The background is a 32-bit surface without per-pixel alpha, so the result does not
    depend on the display's pixel format.

    Returns:
        list[list[list[int]]]: ``rows[y][x]``.

    """
    background = pygame.Surface(image.get_size(), depth=32)
    background.fill((0, 0, 0))
    background.blit(image, (0, 0))
    return pygame.surfarray.array3d(background).transpose(1, 0, 2).tolist()


class TestAlphaDetectionHelpers:
    """Test the helper functions for alpha detection and conversion."""

    def test_needs_alpha_channel_rgb_opaque_only(self):
        """Test that RGB pixels with no transparency don't need alpha."""
        pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (128, 128, 128)]
        assert not needs_alpha_channel(pixels)

    def test_needs_alpha_channel_rgb_with_transparent(self):
        """Test that RGB pixels with magenta transparency need alpha."""
        pixels = [(255, 0, 0), (255, 0, 255), (0, 0, 255)]  # Magenta = transparent
        assert needs_alpha_channel(pixels)

    def test_needs_alpha_channel_rgba_opaque_only(self):
        """Test that RGBA pixels with all opaque alphas don't need alpha."""
        pixels = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]
        assert not needs_alpha_channel(pixels)

    def test_needs_alpha_channel_rgba_with_transparency(self):
        """Test that RGBA pixels with transparency need alpha."""
        pixels = [(255, 0, 0, 255), (0, 255, 0, 128), (0, 0, 255, 255)]  # Semi-transparent
        assert needs_alpha_channel(pixels)

    def test_needs_alpha_channel_rgba_fully_transparent(self):
        """Test that RGBA pixels with fully transparent alpha need alpha."""
        pixels = [(255, 0, 0, 255), (0, 255, 0, 0), (0, 0, 255, 255)]  # Fully transparent
        assert needs_alpha_channel(pixels)

    def test_needs_alpha_channel_mixed_formats(self):
        """Test mixed RGB/RGBA pixel formats."""
        pixels = [(255, 0, 0), (0, 255, 0, 128), (0, 0, 255)]  # Mixed with transparency
        assert needs_alpha_channel(pixels)

    def test_convert_pixels_to_rgb_if_possible_no_alpha_needed(self):
        """Test converting RGBA to RGB when no alpha is needed."""
        pixels = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]
        result = convert_pixels_to_rgb_if_possible(pixels)
        expected = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        assert result == expected

    def test_convert_pixels_to_rgb_if_possible_with_transparency(self):
        """Test that RGBA with transparency stays RGBA."""
        pixels = [(255, 0, 0, 255), (0, 255, 0, 128), (0, 0, 255, 255)]
        result = convert_pixels_to_rgb_if_possible(pixels)
        assert result == pixels  # Should remain unchanged

    def test_convert_pixels_to_rgb_if_possible_transparent_pixels(self):
        """Test converting transparent RGBA pixels to magenta."""
        pixels = [(255, 0, 0, 255), (0, 255, 0, 0), (0, 0, 255, 255)]
        result = convert_pixels_to_rgb_if_possible(pixels)
        # Since there's transparency (alpha=0), it should stay RGBA
        expected = pixels  # Should remain unchanged due to transparency
        assert result == expected

    def test_convert_pixels_to_rgb_if_possible_rgb_input(self):
        """Test that RGB input remains RGB."""
        pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        result = convert_pixels_to_rgb_if_possible(pixels)
        assert result == pixels

    def test_convert_pixels_to_rgb_if_possible_alpha_255_converts_to_rgb(self):
        """Test that RGBA pixels with alpha=255 convert to RGB."""
        pixels = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]
        result = convert_pixels_to_rgb_if_possible(pixels)
        expected = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        assert result == expected

    def test_needs_alpha_channel_alpha_255_does_not_need_alpha(self):
        """Test that RGBA pixels with alpha=255 don't need alpha channel."""
        pixels = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]
        assert not needs_alpha_channel(pixels)

    def test_convert_pixels_to_rgba_if_needed_rgb_to_rgba(self):
        """Test converting RGB pixels to RGBA."""
        pixels = [(255, 0, 0), (255, 0, 255), (0, 0, 255)]
        result = convert_pixels_to_rgba_if_needed(pixels)
        expected = [(255, 0, 0, 255), (255, 0, 255, 255), (0, 0, 255, 255)]
        assert result == expected

    def test_convert_pixels_to_rgba_if_needed_rgba_input(self):
        """Test that RGBA input remains RGBA."""
        pixels = [(255, 0, 0, 255), (255, 0, 255, 0), (0, 0, 255, 128)]
        result = convert_pixels_to_rgba_if_needed(pixels)
        assert result == pixels


class TestAnimatedSpriteRGBRGBA:
    """Test AnimatedSprite RGB/RGBA auto-detection functionality."""

    def test_build_toml_color_map_rgb_only(self):
        """Test color map building with RGB-only pixels."""
        sprite = AnimatedSprite()

        # Create a real 3x1 frame with RGB pixels
        frame = _frame_with_pixels([(255, 0, 0), (0, 255, 0), (0, 0, 255)], width=3)

        sprite._animations = {'test': [frame]}

        color_map = sprite._build_toml_color_map()

        # Should create RGB color tuples
        assert (255, 0, 0) in color_map
        assert (0, 255, 0) in color_map
        assert (0, 0, 255) in color_map
        assert len(color_map[255, 0, 0]) == 1  # Character mapping

    def test_build_toml_color_map_rgba_with_transparency(self):
        """Test color map building with RGBA pixels that have transparency."""
        sprite = AnimatedSprite()

        # Create a real 3x1 frame with RGBA pixels including transparency
        frame = _frame_with_pixels([(255, 0, 0, 255), (0, 255, 0, 128), (0, 0, 255, 255)], width=3)

        sprite._animations = {'test': [frame]}

        color_map = sprite._build_toml_color_map()

        # Should create RGBA color tuples for transparent pixels
        assert (255, 0, 0, 255) in color_map
        assert (0, 255, 0, 128) in color_map
        assert (0, 0, 255, 255) in color_map

    def test_build_toml_color_map_rgba_all_opaque_converts_to_rgb(self):
        """Test that RGBA pixels with all opaque alphas convert to RGB."""
        sprite = AnimatedSprite()

        # Create a real 3x1 frame with all opaque RGBA pixels
        frame = _frame_with_pixels([(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)], width=3)

        sprite._animations = {'test': [frame]}

        color_map = sprite._build_toml_color_map()

        # Should convert to RGB tuples
        assert (255, 0, 0) in color_map
        assert (0, 255, 0) in color_map
        assert (0, 0, 255) in color_map
        # Should not have RGBA tuples
        assert (255, 0, 0, 255) not in color_map

    def test_build_color_map_from_toml_rgb_only(self):
        """Test loading color map from RGB-only TOML."""
        data = {
            'colors': {
                'R': {'red': 255, 'green': 0, 'blue': 0},
                'G': {'red': 0, 'green': 255, 'blue': 0},
                'B': {'red': 0, 'green': 0, 'blue': 255},
            },
        }

        color_map, color_order, original_alpha_values = AnimatedSprite.build_color_map(data)

        assert color_map['R'] == (255, 0, 0)
        assert color_map['G'] == (0, 255, 0)
        assert color_map['B'] == (0, 0, 255)
        # RGB-only colors have no per-pixel alpha
        assert original_alpha_values == {}
        # Color order preserves insertion order
        assert color_order == ['R', 'G', 'B']

    def test_build_color_map_from_toml_rgba(self):
        """Test loading color map from RGBA TOML."""
        data = {
            'colors': {
                'R': {'red': 255, 'green': 0, 'blue': 0, 'alpha': 255},
                'G': {'red': 0, 'green': 255, 'blue': 0, 'alpha': 128},
                'B': {'red': 0, 'green': 0, 'blue': 255, 'alpha': 255},
            },
        }

        color_map, color_order, original_alpha_values = AnimatedSprite.build_color_map(data)

        # Explicit alpha=255 is stored as RGBA 4-tuple to preserve the explicit declaration
        assert color_map['R'] == (255, 0, 0, 255)  # Explicit alpha=255 -> RGBA
        assert color_map['G'] == (0, 255, 0, 128)  # Transparent -> RGBA
        assert color_map['B'] == (0, 0, 255, 255)  # Explicit alpha=255 -> RGBA
        # Only per-pixel alpha (0-254) is tracked; alpha=255 is not
        assert original_alpha_values == {'G': 128}
        assert color_order == ['R', 'G', 'B']

    def test_build_color_map_from_toml_alpha_not_set(self):
        """Test loading color map when alpha is not specified (defaults to opaque)."""
        data = {
            'colors': {
                'R': {'red': 255, 'green': 0, 'blue': 0},  # No alpha specified
                'G': {'red': 0, 'green': 255, 'blue': 0},  # No alpha specified
            },
        }

        color_map, color_order, original_alpha_values = AnimatedSprite.build_color_map(data)

        # Should be RGB since alpha was not specified (indexed color)
        assert color_map['R'] == (255, 0, 0)  # RGB
        assert color_map['G'] == (0, 255, 0)  # RGB
        assert original_alpha_values == {}
        assert color_order == ['R', 'G']

    def test_build_color_map_from_toml_alpha_255_explicit(self):
        """Test loading color map when alpha is explicitly set to 255."""
        data = {
            'colors': {
                'R': {'red': 255, 'green': 0, 'blue': 0, 'alpha': 255},  # Explicit alpha=255
                'G': {'red': 0, 'green': 255, 'blue': 0, 'alpha': 255},  # Explicit alpha=255
            },
        }

        color_map, color_order, original_alpha_values = AnimatedSprite.build_color_map(data)

        # Explicit alpha=255 is stored as RGBA 4-tuple to preserve the explicit declaration
        assert color_map['R'] == (255, 0, 0, 255)  # RGBA
        assert color_map['G'] == (0, 255, 0, 255)  # RGBA
        # alpha=255 is not per-pixel alpha, so not tracked
        assert original_alpha_values == {}
        assert color_order == ['R', 'G']

    def test_build_color_map_from_toml_mixed_rgb_rgba(self):
        """Test loading color map from mixed RGB/RGBA TOML."""
        data = {
            'colors': {
                'R': {'red': 255, 'green': 0, 'blue': 0},  # RGB only
                'G': {'red': 0, 'green': 255, 'blue': 0, 'alpha': 128},  # RGBA
                'B': {'red': 0, 'green': 0, 'blue': 255},  # RGB only
            },
        }

        color_map, color_order, original_alpha_values = AnimatedSprite.build_color_map(data)

        assert color_map['R'] == (255, 0, 0)  # RGB
        assert color_map['G'] == (0, 255, 0, 128)  # RGBA
        assert color_map['B'] == (0, 0, 255)  # RGB
        # Only the per-pixel alpha color is tracked
        assert original_alpha_values == {'G': 128}
        assert color_order == ['R', 'G', 'B']


class TestSpriteSaveLoadRGBRGBA:
    """Test sprite save/load with RGB/RGBA auto-detection."""

    def test_save_single_frame_rgb_only(self):
        """Test saving a single frame sprite with RGB-only pixels."""
        sprite = AnimatedSprite()

        # Create a single 2x2 frame with RGB pixels
        frame = _frame_with_pixels([(255, 0, 0), (0, 255, 0), (0, 0, 255), (128, 128, 128)])

        sprite._animations = {'test': [frame]}
        sprite.name = 'test_sprite'

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.toml',
            delete=False,
            encoding='utf-8',
        ) as f:
            temp_path = f.name

        try:
            sprite._save_toml_single_frame(temp_path)

            # Read the saved file
            content = Path(temp_path).read_text(encoding='utf-8')

            # Should contain RGB colors only
            assert 'red = 255' in content
            assert 'green = 255' in content
            assert 'blue = 255' in content
            # Should not contain alpha
            assert 'alpha =' not in content

        finally:
            Path(temp_path).unlink()

    def test_save_single_frame_rgba_with_transparency(self):
        """Test saving a single frame sprite with RGBA pixels."""
        sprite = AnimatedSprite()

        # Create a single frame with RGBA pixels including transparency
        frame = _frame_with_pixels([
            (255, 0, 0, 255),
            (0, 255, 0, 128),
            (0, 0, 255, 255),
            (128, 128, 128, 0),
        ])

        sprite._animations = {'test': [frame]}
        sprite.name = 'test_sprite'

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.toml',
            delete=False,
            encoding='utf-8',
        ) as f:
            temp_path = f.name

        try:
            sprite._save_toml_single_frame(temp_path)

            # Read the saved file
            content = Path(temp_path).read_text(encoding='utf-8')

            # Should contain alpha values
            assert 'alpha = 255' in content
            assert 'alpha = 128' in content
            assert 'alpha = 0' in content

        finally:
            Path(temp_path).unlink()

    def test_save_animated_sprite_rgb_only(self):
        """Test saving an animated sprite with RGB-only pixels."""
        sprite = AnimatedSprite()

        # Create frames with RGB pixels
        frame1 = _frame_with_pixels([(255, 0, 0), (0, 255, 0)])

        frame2 = _frame_with_pixels([(0, 0, 255), (128, 128, 128)])

        sprite._animations = {'test': [frame1, frame2]}
        sprite.name = 'test_sprite'

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.toml',
            delete=False,
            encoding='utf-8',
        ) as f:
            temp_path = f.name

        try:
            sprite._save_toml(temp_path)

            # Read the saved file
            content = Path(temp_path).read_text(encoding='utf-8')

            # Should contain RGB colors only
            assert 'red = 255' in content
            assert 'green = 255' in content
            assert 'blue = 255' in content
            # Should not contain alpha
            assert 'alpha =' not in content

        finally:
            Path(temp_path).unlink()

    def test_save_animated_sprite_rgba_with_transparency(self):
        """Test saving an animated sprite with RGBA pixels."""
        sprite = AnimatedSprite()

        # Create frames with RGBA pixels including transparency
        frame1 = _frame_with_pixels([(255, 0, 0, 255), (0, 255, 0, 128)])

        frame2 = _frame_with_pixels([(0, 0, 255, 255), (128, 128, 128, 0)])

        sprite._animations = {'test': [frame1, frame2]}
        sprite.name = 'test_sprite'

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.toml',
            delete=False,
            encoding='utf-8',
        ) as f:
            temp_path = f.name

        try:
            sprite._save_toml(temp_path)

            # Read the saved file
            content = Path(temp_path).read_text(encoding='utf-8')

            # Should contain per-pixel alpha values (0-254) only
            # alpha=255 (opaque) is omitted as an optimization since it's the default
            assert 'alpha = 255' not in content
            assert 'alpha = 128' in content
            assert 'alpha = 0' in content

        finally:
            Path(temp_path).unlink()

    def test_load_toml_rgb_only(self):
        """Test loading a TOML file with RGB-only colors."""
        toml_content = """[sprite]
name = "test_sprite"

pixels = \"\"\"
RR
GG
\"\"\"

[colors]
R = { red = 255, green = 0, blue = 0 }
G = { red = 0, green = 255, blue = 0 }
"""

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.toml',
            delete=False,
            encoding='utf-8',
        ) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            sprite = AnimatedSprite(temp_path)

            # Should load RGB colors
            assert sprite._color_map['R'] == (255, 0, 0)
            assert sprite._color_map['G'] == (0, 255, 0)

            # And draws them: a red row over a green row
            assert _drawn_over_black(sprite.image) == [
                [[255, 0, 0], [255, 0, 0]],
                [[0, 255, 0], [0, 255, 0]],
            ]

        finally:
            Path(temp_path).unlink()

    def test_load_toml_rgba(self):
        """Test loading a TOML file with RGBA colors."""
        toml_content = """[sprite]
name = "test_sprite"

pixels = \"\"\"
RG
GB
\"\"\"

[colors]
R = { red = 255, green = 0, blue = 0, alpha = 255 }
G = { red = 0, green = 255, blue = 0, alpha = 128 }
B = { red = 0, green = 0, blue = 255, alpha = 255 }
"""

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.toml',
            delete=False,
            encoding='utf-8',
        ) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            sprite = AnimatedSprite(temp_path)

            # Should load RGBA colors appropriately
            # Explicit alpha=255 in TOML is preserved as RGBA 4-tuple
            assert sprite._color_map['R'] == (255, 0, 0, 255)  # Explicit alpha=255 -> RGBA
            assert sprite._color_map['G'] == (0, 255, 0, 128)  # Transparent -> RGBA
            assert sprite._color_map['B'] == (0, 0, 255, 255)  # Explicit alpha=255 -> RGBA

            # The drawn image blends the alpha-128 green at half strength
            assert _drawn_over_black(sprite.image) == [
                [[255, 0, 0], [0, 128, 0]],
                [[0, 128, 0], [0, 0, 255]],
            ]

        finally:
            Path(temp_path).unlink()

    def test_load_toml_mixed_rgb_rgba(self):
        """Test loading a TOML file with mixed RGB/RGBA colors."""
        toml_content = """[sprite]
name = "test_sprite"

pixels = \"\"\"
RG
BB
\"\"\"

[colors]
R = { red = 255, green = 0, blue = 0 }
G = { red = 0, green = 255, blue = 0, alpha = 128 }
B = { red = 0, green = 0, blue = 255 }
"""

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.toml',
            delete=False,
            encoding='utf-8',
        ) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            sprite = AnimatedSprite(temp_path)

            # Should handle mixed formats correctly
            assert sprite._color_map['R'] == (255, 0, 0)  # RGB
            assert sprite._color_map['G'] == (0, 255, 0, 128)  # RGBA
            assert sprite._color_map['B'] == (0, 0, 255)  # RGB

            # The drawn image blends the alpha-128 green; the opaque colors stay solid
            assert _drawn_over_black(sprite.image) == [
                [[255, 0, 0], [0, 128, 0]],
                [[0, 0, 255], [0, 0, 255]],
            ]

        finally:
            Path(temp_path).unlink()


class TestRGBRGBAIntegration:
    """Integration tests for RGB/RGBA auto-detection."""

    def test_roundtrip_rgb_only(self):
        """Test saving and loading RGB-only sprite maintains format."""
        # Create sprite with RGB pixels
        sprite = AnimatedSprite()
        frame = _frame_with_pixels([(255, 0, 0), (0, 255, 0), (0, 0, 255), (128, 128, 128)])

        sprite._animations = {'test': [frame]}
        sprite.name = 'test_sprite'

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.toml',
            delete=False,
            encoding='utf-8',
        ) as f:
            temp_path = f.name

        try:
            # Save
            sprite._save_toml_single_frame(temp_path)

            loaded_sprite = AnimatedSprite(temp_path)

            # Should maintain RGB format
            # Check what animations are available
            assert len(loaded_sprite._animations) > 0, 'No animations loaded'
            animation_name = next(iter(loaded_sprite._animations.keys()))
            loaded_frame = loaded_sprite._animations[animation_name][0]
            loaded_pixels = loaded_frame.get_pixel_data()

            # All pixels should be RGB (no alpha component)
            for pixel in loaded_pixels:
                assert len(pixel) == 3, f'Expected RGB pixel, got {pixel}'

        finally:
            Path(temp_path).unlink()

    def test_roundtrip_rgba_with_transparency(self):
        """Test saving and loading RGBA sprite maintains transparency."""
        # Create sprite with RGBA pixels including transparency
        # Use alpha values 0-254 to ensure RGBA format is preserved
        sprite = AnimatedSprite()
        frame = _frame_with_pixels([
            (255, 0, 0, 254),
            (0, 255, 0, 128),
            (0, 0, 255, 200),
            (128, 128, 128, 0),
        ])

        sprite._animations = {'test': [frame]}
        sprite.name = 'test_sprite'

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.toml',
            delete=False,
            encoding='utf-8',
        ) as f:
            temp_path = f.name

        try:
            # Save
            sprite._save_toml_single_frame(temp_path)

            loaded_sprite = AnimatedSprite(temp_path)

            # Should maintain RGBA format with transparency
            # Check what animations are available
            assert len(loaded_sprite._animations) > 0, 'No animations loaded'
            animation_name = next(iter(loaded_sprite._animations.keys()))
            loaded_frame = loaded_sprite._animations[animation_name][0]
            loaded_pixels = loaded_frame.get_pixel_data()

            # Should have RGBA pixels with correct alpha values
            # All pixels should remain RGBA since none have alpha=255
            assert (255, 0, 0, 254) in loaded_pixels  # Nearly opaque red -> RGBA
            assert (0, 255, 0, 128) in loaded_pixels  # Semi-transparent green -> RGBA
            assert (0, 0, 255, 200) in loaded_pixels  # Semi-transparent blue -> RGBA
            assert (128, 128, 128, 0) in loaded_pixels  # Fully transparent -> RGBA

        finally:
            Path(temp_path).unlink()

    def test_file_size_optimization(self):
        """Test that RGB-only sprites produce smaller files than RGBA."""
        # Create RGB-only sprite
        rgb_sprite = AnimatedSprite()
        rgb_frame = _frame_with_pixels([(255, 0, 0), (0, 255, 0), (0, 0, 255), (128, 128, 128)])
        rgb_sprite._animations = {'test': [rgb_frame]}
        rgb_sprite.name = 'rgb_sprite'

        # Create RGBA sprite
        rgba_sprite = AnimatedSprite()
        rgba_frame = _frame_with_pixels([
            (255, 0, 0, 255),
            (0, 255, 0, 128),
            (0, 0, 255, 255),
            (128, 128, 128, 0),
        ])
        rgba_sprite._animations = {'test': [rgba_frame]}
        rgba_sprite.name = 'rgba_sprite'

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.toml',
            delete=False,
            encoding='utf-8',
        ) as rgb_file:
            rgb_path = rgb_file.name

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.toml',
            delete=False,
            encoding='utf-8',
        ) as rgba_file:
            rgba_path = rgba_file.name

        try:
            # Save both
            rgb_sprite._save_toml_single_frame(rgb_path)
            rgba_sprite._save_toml_single_frame(rgba_path)

            # RGB file should be smaller (no alpha values)
            rgb_size = Path(rgb_path).stat().st_size
            rgba_size = Path(rgba_path).stat().st_size

            assert rgb_size < rgba_size, (
                f'RGB file ({rgb_size}) should be smaller than RGBA file ({rgba_size})'
            )

        finally:
            Path(rgb_path).unlink()
            Path(rgba_path).unlink()


if __name__ == '__main__':
    pytest.main([__file__])
