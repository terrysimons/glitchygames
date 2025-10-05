"""Audit script to analyze sprite formats in the examples directory.

This script analyzes all TOML sprite files to determine:
1. How many use single-frame legacy format
2. How many are animated
3. Format distribution and patterns
"""

import unittest
from collections import defaultdict
from pathlib import Path

import pygame
from glitchygames.sprites import SpriteFactory


class SpriteFormatAudit(unittest.TestCase):
    """Audit sprite formats in the examples directory."""

    def setUp(self):
        """Set up test fixtures."""
        pygame.init()
        pygame.display.set_mode((800, 600))

        # Path to the examples sprites directory
        self.sprites_dir = Path("glitchygames/examples/resources/sprites")

        # Get all TOML files in the directory
        self.toml_files = []
        if self.sprites_dir.exists():
            for file_path in self.sprites_dir.glob("*.toml"):
                self.toml_files.append(file_path)

    @staticmethod
    def tearDown():
        """Clean up test fixtures."""
        pygame.quit()

    def test_audit_sprite_formats(self):
        """Audit all sprite formats in the examples directory."""
        if not self.sprites_dir.exists():
            self.skipTest(f"Sprites directory {self.sprites_dir} not found")

        # Categories for analysis
        single_frame_sprites = []
        animated_sprites = []
        failed_sprites = []
        format_stats = defaultdict(int)

        for sprite_file in self.toml_files:
            try:
                # Load the sprite
                sprite = SpriteFactory.load_sprite(filename=str(sprite_file))

                # Determine sprite type
                sprite_name = sprite_file.name
                width, height = sprite.image.get_size()

                # Check if it's truly animated (has multiple frames in any animation)
                is_animated = False
                if hasattr(sprite, "animations") and sprite.animations:
                    # Check if any animation has more than 1 frame
                    total_frames = sum(len(frames) for frames in sprite.animations.values())
                    is_animated = total_frames > len(
                        sprite.animations
                    )  # More frames than animations = multi-frame

                if is_animated:
                    animated_sprites.append({
                        "name": sprite_name,
                        "size": f"{width}x{height}",
                        "animations": len(sprite.animations),
                        "total_frames": sum(len(frames) for frames in sprite.animations.values()),
                    })
                    format_stats["animated"] += 1
                else:
                    single_frame_sprites.append({"name": sprite_name, "size": f"{width}x{height}"})
                    format_stats["single_frame"] += 1

            except (ValueError, FileNotFoundError, AttributeError) as e:
                failed_sprites.append({"name": sprite_file.name, "error": str(e)})
                format_stats["failed"] += 1

        # Generate detailed report
        self._generate_report(single_frame_sprites, animated_sprites, failed_sprites, format_stats)

    def _generate_report(
        self, single_frame_sprites, animated_sprites, failed_sprites, format_stats
    ):
        """Generate detailed format audit report."""
        total_sprites = len(single_frame_sprites) + len(animated_sprites) + len(failed_sprites)

        # Verify we have some sprites
        assert total_sprites > 0, "Should have found some sprites to analyze"
        assert len(single_frame_sprites) + len(animated_sprites) > 0, (
            "Should have successfully loaded some sprites"
        )

        # Additional analysis
        self._analyze_patterns(single_frame_sprites, animated_sprites)

    @staticmethod
    def _analyze_patterns(single_frame_sprites, animated_sprites):
        """Analyze patterns in sprite usage."""
        # Size analysis
        single_sizes = [sprite["size"] for sprite in single_frame_sprites]
        animated_sizes = [sprite["size"] for sprite in animated_sprites]

        # Verify we have some data to analyze
        assert len(single_sizes) + len(animated_sizes) > 0, "Should have some sprites to analyze"

        # Animation complexity analysis
        if animated_sprites:
            total_animations = sum(sprite["animations"] for sprite in animated_sprites)
            total_frames = sum(sprite["total_frames"] for sprite in animated_sprites)
            avg_frames_per_animation = (
                total_frames / total_animations if total_animations > 0 else 0
            )

            # Verify animation data is reasonable
            assert total_animations > 0, "Should have some animations"
            assert total_frames > 0, "Should have some frames"
            assert avg_frames_per_animation > 0, "Should have reasonable frame count"

    def test_analyze_sprite_categories(self):
        """Analyze sprites by category/type."""
        if not self.sprites_dir.exists():
            self.skipTest(f"Sprites directory {self.sprites_dir} not found")

        # Define categories based on naming patterns
        categories = {
            "weapons": [],
            "environment": [],
            "items": [],
            "characters": [],
            "buildings": [],
            "other": [],
        }

        for sprite_file in self.toml_files:
            try:
                SpriteFactory.load_sprite(filename=str(sprite_file))
                sprite_name = sprite_file.name

                # Categorize based on name patterns
                if any(
                    word in sprite_name.lower()
                    for word in ["sword", "axe", "bow", "flail", "scepter"]
                ):
                    categories["weapons"].append(sprite_name)
                elif any(
                    word in sprite_name.lower()
                    for word in ["dirt", "grass", "brick", "hedge", "tree", "bush"]
                ):
                    categories["environment"].append(sprite_name)
                elif any(
                    word in sprite_name.lower()
                    for word in ["key", "gold", "jewel", "book", "scroll", "heart"]
                ):
                    categories["items"].append(sprite_name)
                elif any(
                    word in sprite_name.lower() for word in ["door", "throne", "exit", "stairs"]
                ):
                    categories["buildings"].append(sprite_name)
                elif any(word in sprite_name.lower() for word in ["colors", "checker"]):
                    categories["characters"].append(sprite_name)
                else:
                    categories["other"].append(sprite_name)

            except (ValueError, FileNotFoundError, AttributeError):
                categories["other"].append(f"{sprite_file.name} (failed)")

        # Verify we have some categorized sprites
        total_categorized = sum(len(sprites) for sprites in categories.values())
        assert total_categorized > 0, "Should have categorized some sprites"


if __name__ == "__main__":
    unittest.main()
