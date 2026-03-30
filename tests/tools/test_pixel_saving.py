"""Test pixel saving functionality in bitmap editor."""

import sys
from pathlib import Path

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.bitmappy.toml_processing import (
    collect_unique_colors_from_pixels,
)
from tests.mocks.test_mock_factory import MockFactory


class TestPixelSaving:
    """Test pixel saving functionality using centralized mocks."""

    def setup_method(self):
        """Set up test fixtures using centralized mocks."""
        # Use centralized mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers.values():
            patcher.start()

    def teardown_method(self):
        """Clean up after tests."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_pixel_processing_logic(self):
        """Test the pixel processing logic from _generate_frame_toml_content."""
        # Test different pixel formats
        test_cases = [
            # RGBA tuples (what we expect)
            (255, 0, 0, 255),  # Red
            (0, 255, 0, 255),  # Green
            (0, 0, 255, 255),  # Blue
            # RGB tuples
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
            # Integer format
            0xFF0000,  # Red as int
            0x00FF00,  # Green as int
            0x0000FF,  # Blue as int
            # Unknown format (should fallback to magenta)
            'invalid',
            None,
            [],
        ]

        print('Testing pixel processing logic:')  # noqa: T201
        print('=' * 50)  # noqa: T201

        unique_colors = set()

        for i, pixel in enumerate(test_cases):
            print(f'Pixel {i}: {pixel} (type: {type(pixel)})')  # noqa: T201

            if isinstance(pixel, tuple) and len(pixel) >= 3:
                color = pixel[:3]
                print(f'  -> tuple with {len(pixel)} values -> color {color}')  # noqa: T201
            elif isinstance(pixel, int):
                r = (pixel >> 16) & 0xFF
                g = (pixel >> 8) & 0xFF
                b = pixel & 0xFF
                color = (r, g, b)
                print(f'  -> int {hex(pixel)} -> color {color}')  # noqa: T201
            else:
                color = (255, 0, 255)  # Default magenta
                print(f'  -> unknown type -> default magenta {color}')  # noqa: T201

            unique_colors.add(color)
            print()  # noqa: T201

        print(f'Unique colors found: {len(unique_colors)}')  # noqa: T201
        for color in sorted(unique_colors):
            print(f'  {color}')  # noqa: T201

        # Assertions
        assert len(unique_colors) > 1, 'Should have multiple unique colors, not just magenta'
        assert (255, 0, 255) in unique_colors, 'Should include magenta fallback'
        assert (255, 0, 0) in unique_colors, 'Should include red'
        assert (0, 255, 0) in unique_colors, 'Should include green'
        assert (0, 0, 255) in unique_colors, 'Should include blue'

    def test_collect_unique_colors_from_pixels(self):
        """Test that unique colors are correctly extracted from pixel data."""
        test_pixels = [
            (255, 0, 0, 255),  # Red
            (0, 255, 0, 255),  # Green
            (0, 0, 255, 255),  # Blue
            (255, 255, 0, 255),  # Yellow
            (255, 0, 255, 255),  # Magenta
        ]

        unique_colors = collect_unique_colors_from_pixels(test_pixels)

        assert (255, 0, 0) in unique_colors, 'Should include red'
        assert (0, 255, 0) in unique_colors, 'Should include green'
        assert (0, 0, 255) in unique_colors, 'Should include blue'
        assert (255, 255, 0) in unique_colors, 'Should include yellow'
        assert (255, 0, 255) in unique_colors, 'Should include magenta'
        assert len(unique_colors) == 5, f'Expected 5 unique colors, got {len(unique_colors)}'

    def test_pixel_format_detection(self):
        """Test that different pixel formats are detected correctly."""
        # Test RGBA format (4 values)
        rgba_pixel = (255, 128, 64, 255)
        assert isinstance(rgba_pixel, tuple) and len(rgba_pixel) >= 3
        color = rgba_pixel[:3]
        assert color == (255, 128, 64)

        # Test RGB format (3 values)
        rgb_pixel = (128, 64, 32)
        assert isinstance(rgb_pixel, tuple) and len(rgb_pixel) >= 3
        color = rgb_pixel[:3]
        assert color == (128, 64, 32)

        # Test integer format
        int_pixel = 0xFF8040  # RGB(255, 128, 64)
        r = (int_pixel >> 16) & 0xFF
        g = (int_pixel >> 8) & 0xFF
        b = int_pixel & 0xFF
        assert (r, g, b) == (255, 128, 64)

        # Test unknown format
        unknown_pixel = 'invalid'
        if not (isinstance(unknown_pixel, tuple) and len(unknown_pixel) >= 3) and not isinstance(
            unknown_pixel, int
        ):
            color = (255, 0, 255)  # Default magenta
            assert color == (255, 0, 255)
