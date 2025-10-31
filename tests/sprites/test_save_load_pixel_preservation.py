"""Test that save/load operations preserve pixel data correctly."""

import tempfile
from pathlib import Path
import pytest
import pygame

from glitchygames.tools.bitmappy import AnimatedCanvasSprite
from tests.mocks.test_mock_factory import MockFactory


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

    def setup_method(self):
        """Set up test fixtures using centralized mocks."""
        # Ensure pygame is properly initialized for mocks
        if not pygame.get_init():
            pygame.init()

        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()

    def teardown_method(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_candle_sprite_save_load_preserves_pixels(self):
        """Test that loading, saving, and reloading a candle sprite preserves all pixels."""
        # Create temporary file with candle sprite
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False, encoding='utf-8') as f:
            temp_input = f.name
            f.write(CANDLE_SPRITE_CONTENT)
        
        # Create temporary file for save output
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            temp_output = f.name

        try:
            # Read original file content
            original_content = Path(temp_input).read_text(encoding="utf-8")
            
            # Load using existing AnimatedSprite load method
            from glitchygames.sprites import AnimatedSprite
            sprite = AnimatedSprite(filename=temp_input)
            
            # Save using existing AnimatedSprite save method
            sprite.save(temp_output, "toml")
            
            # Read saved file content
            saved_content = Path(temp_output).read_text(encoding="utf-8")
            
            # Files should be byte-for-byte identical (normalize trailing newlines)
            original_normalized = original_content.rstrip("\n")
            saved_normalized = saved_content.rstrip("\n")
            assert original_normalized == saved_normalized, (
                "Saved file should match original file.\n"
                f"Original length: {len(original_content)} (normalized: {len(original_normalized)})\n"
                f"Saved length: {len(saved_content)} (normalized: {len(saved_normalized)})"
            )
        
        finally:
            # Clean up
            for temp_file in [temp_input, temp_output]:
                temp_path = Path(temp_file)
                if temp_path.exists():
                    temp_path.unlink()

    def test_candle_sprite_with_alpha_section_preserves_alpha_fields(self):
        """Test that colors with alpha=0-254 (per-pixel alpha) are preserved when saved."""
        # Create temporary file with candle sprite that has color 'd' with alpha=200 (per-pixel alpha)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False, encoding='utf-8') as f:
            temp_input = f.name
            f.write(CANDLE_SPRITE_WITH_ALPHA_CONTENT)
        
        # Create temporary file for save output
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            temp_output = f.name

        try:
            # Load using existing AnimatedSprite load method
            from glitchygames.sprites import AnimatedSprite
            sprite = AnimatedSprite(filename=temp_input)
            
            # Save using existing AnimatedSprite save method
            sprite.save(temp_output, "toml")
            
            # Read saved file content
            saved_content = Path(temp_output).read_text(encoding="utf-8")
            
            # Color 'd' should have alpha field with value 200 (per-pixel alpha preserved)
            import re
            d_color_match = re.search(r'\[colors\."d"\][\s\S]*?(?=\[|$)', saved_content)
            assert d_color_match is not None, "Color 'd' should be present in saved file"
            d_section = d_color_match.group(0)
            assert "alpha = 200" in d_section, (
                f"Color 'd' should have alpha=200 preserved. Section:\n{d_section}"
            )
            
            # Should NOT have [alpha] section (that format is deprecated)
            assert "[alpha]" not in saved_content, "Should not have [alpha] section - use per-color alpha fields instead"
        
        finally:
            # Clean up
            for temp_file in [temp_input, temp_output]:
                temp_path = Path(temp_file)
                if temp_path.exists():
                    temp_path.unlink()

