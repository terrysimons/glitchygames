#!/usr/bin/env python3
"""Full glitchygames scene demo script that loads foo.toml and displays animated sprite."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self, override

import pygame

from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene
from glitchygames.sprites.animated import AnimatedSprite

if TYPE_CHECKING:
    import argparse

# Set up logging
# Its level is the command line's (--log-level; debug shows this demo's debug lines): never
# set here, where at import it reached every game.* logger of a process importing it (BUGS.md #236)
LOG = logging.getLogger('game')

# The sprite the demo shows: scripts/foo.toml, next to this script. The demos looked for it in
# the repository root, where there is none, so they always stopped with MISSING_INPUT
# (BUGS.md #245).
FOO_TOML_PATH = Path(__file__).parent / 'foo.toml'


class AnimationGame(Scene):
    """Full glitchygames scene for displaying animated sprites."""

    NAME = 'Animation Scene Demo'
    log = LOG

    def __init__(
        self: Self,
        options: dict[str, Any],
        groups: pygame.sprite.AbstractGroup[Any] | None = None,
    ) -> None:
        """Initialize the animation game."""
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(options=options, groups=groups)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]

        # Set up the scene
        self.background_color = (20, 20, 40)
        self.fps = 60

        # Load animated sprite
        self._load_animated_sprite()

        # Clear the screen with background
        assert self.screen is not None
        self.all_sprites.clear(self.screen, self.background)

    @override
    def update(self: Self) -> None:
        """Update the scene."""
        super().update()

        if self.animated_sprite:
            self.animated_sprite.update(self.dt)

    def on_keydown_event(self: Self, event: pygame.event.Event) -> None:
        """Handle keydown events."""
        if event.key == pygame.K_ESCAPE or event.unicode.lower() == 'q':
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
        """Load the animated sprite from foo.toml.

        Raises:
            FileNotFoundError: If the animation TOML file is not found.
            ValueError: If the animation data is invalid.
            RuntimeError: If the animation system fails to initialize.

        """
        foo_toml_path = FOO_TOML_PATH

        try:
            self.animated_sprite = AnimatedSprite(str(foo_toml_path), groups=self.all_sprites)
        except FileNotFoundError, ValueError, RuntimeError:
            self.log.exception('Failed to load animation')
            raise
        self.animated_sprite.play()
        # Center on screen dynamically
        assert self.animated_sprite.rect is not None
        assert self.screen is not None
        self.animated_sprite.rect.center = self.screen.get_rect().center
        self.log.info(
            'Loaded: %s (%s frames)',
            self.animated_sprite.name,
            self.animated_sprite.frame_count,
        )
        self.log.info('Controls: ESC/Q=quit, SPACE=pause/resume, R=reset, 1/2=frame 0/1')

    @classmethod
    def args(cls: type[AnimationGame], parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add game-specific arguments to the global parser.

        Returns:
            argparse.ArgumentParser: The result.

        """
        parser.add_argument(
            '-v',
            '--version',
            action='store_true',
            help='print the game version and exit',
        )
        return parser


def main() -> None:
    """Run the full glitchygames animation demo."""
    # Use the GameEngine to run the game
    GameEngine(game=AnimationGame).start()


if __name__ == '__main__':
    main()
