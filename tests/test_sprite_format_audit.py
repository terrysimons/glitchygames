"""Audit script to analyze sprite formats in the examples directory.

This script analyzes all TOML sprite files to determine:
1. How many use single-frame legacy format
2. How many are animated
3. Format distribution and patterns
"""

import os
import tempfile
import unittest
from collections import Counter, defaultdict
from pathlib import Path

import pygame
import pytest
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

        print(f"🔍 Auditing {len(self.toml_files)} TOML sprite files...")

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

                print(
                    f"✅ {sprite_name}: {'Animated' if is_animated else 'Single-frame'} ({width}x{height})"
                )

            except Exception as e:
                failed_sprites.append({"name": sprite_file.name, "error": str(e)})
                format_stats["failed"] += 1
                print(f"❌ {sprite_file.name}: {e}")

        # Generate detailed report
        self._generate_report(single_frame_sprites, animated_sprites, failed_sprites, format_stats)

    def _generate_report(
        self, single_frame_sprites, animated_sprites, failed_sprites, format_stats
    ):
        """Generate detailed format audit report."""
        total_sprites = len(single_frame_sprites) + len(animated_sprites) + len(failed_sprites)

        print(f"\n📊 SPRITE FORMAT AUDIT REPORT")
        print(f"=" * 50)
        print(f"Total sprites analyzed: {total_sprites}")
        print(f"Successfully loaded: {len(single_frame_sprites) + len(animated_sprites)}")
        print(f"Failed to load: {len(failed_sprites)}")
        print(
            f"Success rate: {((len(single_frame_sprites) + len(animated_sprites)) / total_sprites * 100):.1f}%"
        )

        print(f"\n🎬 ANIMATED SPRITES: {len(animated_sprites)}")
        print(f"=" * 30)
        if animated_sprites:
            for sprite in animated_sprites:
                print(
                    f"  • {sprite['name']}: {sprite['size']} - {sprite['animations']} animation(s), {sprite['total_frames']} total frames"
                )
        else:
            print("  No animated sprites found")

        print(f"\n🖼️  SINGLE-FRAME SPRITES: {len(single_frame_sprites)}")
        print(f"=" * 30)
        if single_frame_sprites:
            # Group by size for better analysis
            size_groups = defaultdict(list)
            for sprite in single_frame_sprites:
                size_groups[sprite["size"]].append(sprite["name"])

            for size, names in size_groups.items():
                print(f"  {size} ({len(names)} sprites):")
                for name in sorted(names):
                    print(f"    • {name}")
        else:
            print("  No single-frame sprites found")

        print(f"\n❌ FAILED SPRITES: {len(failed_sprites)}")
        print(f"=" * 30)
        if failed_sprites:
            for sprite in failed_sprites:
                print(f"  • {sprite['name']}: {sprite['error']}")
        else:
            print("  No failed sprites")

        print(f"\n📈 FORMAT DISTRIBUTION")
        print(f"=" * 30)
        for format_type, count in format_stats.items():
            percentage = (count / total_sprites * 100) if total_sprites > 0 else 0
            print(f"  {format_type.replace('_', ' ').title()}: {count} ({percentage:.1f}%)")

        # Additional analysis
        self._analyze_patterns(single_frame_sprites, animated_sprites)

    def _analyze_patterns(self, single_frame_sprites, animated_sprites):
        """Analyze patterns in sprite usage."""
        print(f"\n🔍 PATTERN ANALYSIS")
        print(f"=" * 30)

        # Size analysis
        single_sizes = [sprite["size"] for sprite in single_frame_sprites]
        animated_sizes = [sprite["size"] for sprite in animated_sprites]

        if single_sizes:
            single_size_counts = Counter(single_sizes)
            print(f"Single-frame sprite sizes:")
            for size, count in single_size_counts.most_common():
                print(f"  • {size}: {count} sprites")

        if animated_sizes:
            animated_size_counts = Counter(animated_sizes)
            print(f"Animated sprite sizes:")
            for size, count in animated_size_counts.most_common():
                print(f"  • {size}: {count} sprites")

        # Animation complexity analysis
        if animated_sprites:
            total_animations = sum(sprite["animations"] for sprite in animated_sprites)
            total_frames = sum(sprite["total_frames"] for sprite in animated_sprites)
            avg_frames_per_animation = (
                total_frames / total_animations if total_animations > 0 else 0
            )

            print(f"\nAnimation complexity:")
            print(f"  • Total animations: {total_animations}")
            print(f"  • Total frames: {total_frames}")
            print(f"  • Average frames per animation: {avg_frames_per_animation:.1f}")

            # Most complex animations
            complex_animations = sorted(
                animated_sprites, key=lambda x: x["total_frames"], reverse=True
            )[:5]
            print(f"  • Most complex animations:")
            for sprite in complex_animations:
                print(f"    - {sprite['name']}: {sprite['total_frames']} frames")

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
                sprite = SpriteFactory.load_sprite(filename=str(sprite_file))
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

            except Exception as e:
                categories["other"].append(f"{sprite_file.name} (failed)")

        print(f"\n📂 SPRITE CATEGORIES")
        print(f"=" * 30)
        for category, sprites in categories.items():
            if sprites:
                print(f"{category.title()}: {len(sprites)} sprites")
                for sprite in sorted(sprites):
                    print(f"  • {sprite}")


if __name__ == "__main__":
    unittest.main()
