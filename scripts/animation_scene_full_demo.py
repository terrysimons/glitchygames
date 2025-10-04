#!/usr/bin/env python3
"""Full glitchygames scene demo script that loads foo.toml and displays animated sprite."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Self

import pygame

# Add the parent directory to the path so we can import glitchygames
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene
from glitchygames.sprites.animated import AnimatedSprite

if TYPE_CHECKING:
    import argparse

# Set up logging
LOG = logging.getLogger("game")
LOG.setLevel(logging.INFO)


class AnimationGame(Scene):
    """Full glitchygames scene for displaying animated sprites."""

    NAME = "Animation Scene Demo"
    log = LOG

    def __init__(self: Self, options: dict, groups: pygame.sprite.Group | None = None) -> None:
        """Initialize the animation game."""
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(options=options, groups=groups)

        # Set up the scene
        self.background_color = (20, 20, 40)
        self.fps = 60

        # Load animated sprite
        self._load_animated_sprite()

        # Clear the screen with background
        self.all_sprites.clear(self.screen, self.background)

    def update(self: Self) -> None:
        """Update the scene."""
        super().update()

        if self.animated_sprite:
            self.animated_sprite.update(self.dt)

    def on_keydown_event(self: Self, event: pygame.event.Event) -> None:
        """Handle keydown events."""
        if event.key == pygame.K_ESCAPE or event.unicode.lower() == "q":
            self.scene_manager.quit()
            return

        if event.key == pygame.K_SPACE:
            if self.animated_sprite.is_playing:
                self.animated_sprite.pause()
            else:
                self.animated_sprite.play()
            return

        if event.key == pygame.K_r:
            self.animated_sprite.stop()
            self.animated_sprite.play()
            return

        if event.key == pygame.K_1:
            self.animated_sprite.set_frame(0)
            return

        if event.key == pygame.K_2:
            self.animated_sprite.set_frame(1)

    def _load_animated_sprite(self: Self) -> None:
        """Load the animated sprite from foo.toml."""
        foo_toml_path = Path(__file__).parent.parent / "foo.toml"

        try:
            self.animated_sprite = AnimatedSprite(str(foo_toml_path), groups=self.all_sprites)
            self.animated_sprite.play()
            # Center on screen dynamically
            self.animated_sprite.rect.center = self.screen.get_rect().center
            self.log.info(f"Loaded: {self.animated_sprite.name} "
                         f"({self.animated_sprite.frame_count} frames)")
            self.log.info("Controls: ESC/Q=quit, SPACE=pause/resume, R=reset, 1/2=frame 0/1")
        except (FileNotFoundError, ValueError, RuntimeError):
            self.log.exception("Failed to load animation")
            raise

    @classmethod
    def args(cls: Self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add game-specific arguments to the global parser."""
        parser.add_argument(
            "-v", "--version", action="store_true", help="print the game version and exit"
        )
        return parser


def main() -> None:
    """Run the full glitchygames animation demo."""
    # Use the GameEngine to run the game
    GameEngine(game=AnimationGame).start()


if __name__ == "__main__":
    main()
