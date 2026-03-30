"""Test suite for automatic alpha mode detection in sprite save/load.

This module tests the automatic detection of per-pixel alpha vs indexed color modes
and ensures sprites are saved/loaded with the correct format.
"""

import tempfile
import unittest
from pathlib import Path

import pygame

from glitchygames.color import MAGENTA_TRANSPARENCY_KEY
from glitchygames.sprites import DEFAULT_FILE_FORMAT, AnimatedSprite, SpriteFrame
from tests.mocks import MockFactory


class TestAlphaModeDetection(unittest.TestCase):
    """Test automatic detection of per-pixel alpha vs indexed color modes."""

    def setUp(self):
        """Set up test fixtures."""
        # Ensure pygame is properly initialized for mocks
        if not pygame.get_init():
            pygame.init()
        pygame.display.set_mode((100, 100))  # Minimal display for tests

        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers.values():
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_indexed_color_mode_detection(self):
        """Test that sprites with only opaque colors use indexed color mode (RGB)."""
        # Create TOML content with only opaque colors (no alpha or alpha=255)
        toml_content = """[sprite]
name = "indexed_sprite"

pixels = \"\"\"
R█
█G
\"\"\"

[colors]
R = { red = 255, green = 0, blue = 0 }
G = { red = 0, green = 255, blue = 0 }
"█" = { red = 255, green = 0, blue = 255 }
"""

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.toml', delete=False, encoding='utf-8'
        ) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            # Load the sprite
            sprite = AnimatedSprite(temp_path)

            # Should use RGB format (indexed color mode)
            frame = sprite._animations['indexed_sprite'][0]
            pixels = frame.get_pixel_data()

            # All pixels should be RGB tuples (3 components)
            for pixel in pixels:
                assert len(pixel) == 3, f'Expected RGB tuple, got {pixel}'

        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_per_pixel_alpha_mode_detection(self):
        """Test that sprites with semi-transparent colors use per-pixel alpha mode (RGBA)."""
        # Create TOML content with semi-transparent colors
        toml_content = """[sprite]
name = "per_pixel_alpha_sprite"

pixels = \"\"\"
R█
█G
\"\"\"

[colors]
R = { red = 255, green = 0, blue = 0, alpha = 128 }
G = { red = 0, green = 255, blue = 0, alpha = 200 }
"█" = { red = 255, green = 0, blue = 255 }
"""

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.toml', delete=False, encoding='utf-8'
        ) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            # Load the sprite
            sprite = AnimatedSprite(temp_path)

            # Should use RGBA format (per-pixel alpha mode)
            frame = sprite._animations['per_pixel_alpha_sprite'][0]
            pixels = frame.get_pixel_data()

            # All pixels should be RGBA tuples (4 components)
            for pixel in pixels:
                assert len(pixel) == 4, f'Expected RGBA tuple, got {pixel}'

        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_mixed_alpha_values_detection(self):
        """Test that sprites with mixed alpha values use per-pixel alpha mode.

        Sprites with some opaque and some transparent colors should use per-pixel alpha mode.
        """
        # Create TOML content with mixed alpha values
        toml_content = """[sprite]
name = "mixed_alpha_sprite"

pixels = \"\"\"
R█
█G
\"\"\"

[colors]
R = { red = 255, green = 0, blue = 0, alpha = 255 }  # Opaque
G = { red = 0, green = 255, blue = 0, alpha = 128 }  # Semi-transparent
"█" = { red = 255, green = 0, blue = 255 }           # No alpha (defaults to 255)
"""

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.toml', delete=False, encoding='utf-8'
        ) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            # Load the sprite
            sprite = AnimatedSprite(temp_path)

            # Should use RGBA format (per-pixel alpha mode) because G has alpha=128
            frame = sprite._animations['mixed_alpha_sprite'][0]
            pixels = frame.get_pixel_data()

            # All pixels should be RGBA tuples (4 components)
            for pixel in pixels:
                assert len(pixel) == 4, f'Expected RGBA tuple, got {pixel}'

        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_save_load_roundtrip_indexed_color(self):
        """Test save/load roundtrip for indexed color mode sprites."""
        # Create a sprite with RGB pixels only
        sprite = AnimatedSprite()
        sprite.name = 'roundtrip_indexed'

        # Create a 2x2 frame with RGB pixels
        surface = pygame.Surface((2, 2))
        surface.fill(MAGENTA_TRANSPARENCY_KEY)  # Magenta background
        surface.set_at((0, 0), (255, 0, 0))  # Red
        surface.set_at((1, 1), (0, 255, 0))  # Green

        frame = SpriteFrame(surface)
        frame.pixels = [
            (255, 0, 0),
            MAGENTA_TRANSPARENCY_KEY,  # Row 0: Red, Magenta
            MAGENTA_TRANSPARENCY_KEY,
            (0, 255, 0),  # Row 1: Magenta, Green
        ]

        sprite.add_animation('idle', [frame])

        # Save and load
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.toml', delete=False, encoding='utf-8'
        ) as f:
            temp_path = f.name

        try:
            sprite.save(temp_path, DEFAULT_FILE_FORMAT)
            loaded_sprite = AnimatedSprite(temp_path)

            # Verify loaded sprite uses RGB format
            loaded_frame = loaded_sprite._animations['roundtrip_indexed'][0]
            loaded_pixels = loaded_frame.get_pixel_data()

            # All pixels should be RGB tuples
            for pixel in loaded_pixels:
                assert len(pixel) == 3, f'Expected RGB tuple, got {pixel}'

            # Verify specific colors
            assert loaded_pixels[0] == (255, 0, 0)  # Red
            assert loaded_pixels[3] == (0, 255, 0)  # Green
            assert loaded_pixels[1][:3] == MAGENTA_TRANSPARENCY_KEY  # Magenta
            assert loaded_pixels[2][:3] == MAGENTA_TRANSPARENCY_KEY  # Magenta

        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_save_load_roundtrip_per_pixel_alpha(self):
        """Test save/load roundtrip for per-pixel alpha mode sprites."""
        # Create a sprite with RGBA pixels
        sprite = AnimatedSprite()
        sprite.name = 'roundtrip_per_pixel_alpha'

        # Create a 2x2 frame with RGBA pixels
        surface = pygame.Surface((2, 2), pygame.SRCALPHA)
        surface.fill((255, 0, 255, 255))  # Magenta background (opaque)
        surface.set_at((0, 0), (255, 0, 0, 128))  # Red (semi-transparent)
        surface.set_at((1, 1), (0, 255, 0, 200))  # Green (semi-transparent)

        frame = SpriteFrame(surface)
        frame.pixels = [
            (255, 0, 0, 128),
            (255, 0, 255, 255),  # Row 0: Red (semi), Magenta (opaque)
            (255, 0, 255, 255),
            (0, 255, 0, 200),  # Row 1: Magenta (opaque), Green (semi)
        ]

        sprite.add_animation('idle', [frame])

        # Save and load
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.toml', delete=False, encoding='utf-8'
        ) as f:
            temp_path = f.name

        try:
            sprite.save(temp_path, DEFAULT_FILE_FORMAT)
            loaded_sprite = AnimatedSprite(temp_path)

            # Verify loaded sprite uses RGBA format
            loaded_frame = loaded_sprite._animations['roundtrip_per_pixel_alpha'][0]
            loaded_pixels = loaded_frame.get_pixel_data()

            # All pixels should be RGBA tuples
            for pixel in loaded_pixels:
                assert len(pixel) == 4, f'Expected RGBA tuple, got {pixel}'

            # Verify specific colors with alpha
            assert loaded_pixels[0] == (255, 0, 0, 128)  # Red (semi-transparent)
            assert loaded_pixels[3] == (0, 255, 0, 200)  # Green (semi-transparent)
            assert loaded_pixels[1] == (255, 0, 255, 255)  # Magenta (opaque)
            assert loaded_pixels[2] == (255, 0, 255, 255)  # Magenta (opaque)

        finally:
            Path(temp_path).unlink(missing_ok=True)


if __name__ == '__main__':
    unittest.main()
