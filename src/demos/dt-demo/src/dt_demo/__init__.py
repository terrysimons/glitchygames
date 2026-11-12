"""Delta Time Demo: a square crossing the screen at a speed independent of the frame rate.

Run it with the ``dt-demo`` console script or ``python -m dt_demo``; Space starts the square.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self, cast, override

if TYPE_CHECKING:
    import argparse

    from glitchygames.events.base import KeyEvent

import pygame

from glitchygames.color import BLACK, WHITE
from glitchygames.engine import GameEngine
from glitchygames.fonts import FontManager
from glitchygames.fonts.font_manager import DEFAULT_FONT_NAME
from glitchygames.input.state import current_input
from glitchygames.scenes import Scene
from glitchygames.sprites import Sprite
from glitchygames.ui import TextSprite

# Adapted from:
# https://github.com/ChristianD37/YoutubeTutorials/tree/master/Framerate%20Independence

# The demo's text: the bundled font at this size
FONT_SIZE = 40
# Where the FPS line starts, below the time line
FPS_LINE_TOP = 50
# The widest text the FPS line is sized for, once: the FPS is measured (a replay under
# --replay-fps real serves this machine's), so the line's rect must not follow it. The bundled
# font's digits are all one width, and five integer digits cover an uncapped run
# (--target-fps 0); anything wider is cut off at the line's right edge, never resized (Ruling R14)
FPS_LINE_WIDEST_TEXT = 'FPS: 99999.99'
# The square: this many pixels a side, its top this far below the middle of the screen
SQUARE_SIZE = 40
SQUARE_BELOW_MIDDLE = 30


class TextLine(TextSprite):
    """One line of the demo's text: a TextSprite in the demo's font, starting at its top-left.

    TextSprite draws the engine's default font centred in a box of fixed size; the demo's lines
    keep the font they were drawn in when they were blitted straight onto the screen, starting
    at their top-left corner, so the demo looks as it did. A replay compares the line's rect:
    a line of replayed values (game time) is exactly as big as its text, so its width follows
    the text; a subclass naming ``WIDEST_TEXT`` (``FpsLine``: the measured FPS) is sized once
    for that text and keeps that rect whatever it shows, the text drawn at its left.
    """

    # The widest text the line can show, for a line of a fixed size; None for a line exactly as
    # big as its text
    WIDEST_TEXT: str | None = None

    def __init__(
        self: Self,
        *,
        font: pygame.font.Font,
        text: str,
        topleft: tuple[int, int],
        name: str,
        groups: pygame.sprite.LayeredDirty[Any],
    ) -> None:
        """Show a line of white text with its top-left corner at ``topleft``.

        Args:
            font: The font to draw the text in.
            text: The text (never empty: a sprite is made at least a pixel wide).
            topleft: Where the text starts on the screen.
            name: The sprite's name.
            groups: The sprite group to add it to.

        """
        # Set before TextSprite's __init__, which draws the text (update_text)
        self.line_font = font
        self.fixed_size: tuple[int, int] | None = (
            None if self.WIDEST_TEXT is None else font.size(self.WIDEST_TEXT)
        )
        width, height = font.size(text) if self.fixed_size is None else self.fixed_size
        super().__init__(
            x=topleft[0],
            y=topleft[1],
            width=width,
            height=height,
            name=name,
            text_color=WHITE,
            text=text,
            groups=groups,
        )

    @override
    def update_text(self: Self, text: str) -> None:
        """Draw the text in the line's font: the sprite takes the text's size, or keeps its own.

        Args:
            text: The text.

        """
        rendered_text = self.line_font.render(text, FontManager.antialias(), self.text_color)
        if self.fixed_size is None:
            self.image = rendered_text
            self.rect.size = self.image.get_size()
            return
        # A transparent surface of the line's fixed size, the text copied in at its left: the
        # maximum of each channel against all zeroes is the text's own pixels, alpha included,
        # so the line looks exactly as the rendered text does, and its rect never changes
        self.image = pygame.Surface(self.fixed_size, pygame.SRCALPHA)
        self.image.blit(rendered_text, (0, 0), special_flags=pygame.BLEND_RGBA_MAX)


class FpsLine(TextLine):
    """The FPS line: one fixed size, sized for ``FPS_LINE_WIDEST_TEXT``, whatever the FPS."""

    WIDEST_TEXT = FPS_LINE_WIDEST_TEXT


class Game(Scene):
    """The main game class."""

    # Set your game name/version here.
    NAME = 'Delta Time Demo'
    VERSION = '1.0'

    def __init__(
        self: Self,
        options: dict[str, object],
        groups: pygame.sprite.LayeredDirty | None = None,  # type: ignore[type-arg]
    ) -> None:
        """Initialize the Game.

        Args:
            options (dict[str, object]): The options passed to the game.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()  # type: ignore[type-arg]

        super().__init__(options=options, groups=groups)  # type: ignore[arg-type]
        # The bundled default font, loaded from its file through FontManager (cached): never a
        # system font scan (BUGS.md #156, #173 item 3: this asked for Calibri). It is a
        # pygame.font font: render() below takes (text, antialias, color).
        self.font = cast(
            'pygame.font.Font',
            FontManager.pygame_font(
                font_config={'font_name': DEFAULT_FONT_NAME, 'font_size': FONT_SIZE}
            ),
        )
        self.rect_pos = 0
        # Pixels per second; use a visible speed
        self.velocity = 300
        self.record = 0
        self.passed = False
        self.start = False
        # Everything shown is a sprite on black, so a replay compares what the demo shows: the
        # time and record lines' widths follow their text (game time, which a replay serves),
        # the FPS line keeps one size (the FPS is measured), the square's x its position, and
        # the record line is hidden until the square has crossed (screen-space sprites: their
        # rect and visible are the demo's to set)
        self.background_color = BLACK
        self.time_line = TextLine(
            font=self.font,
            text=self._time_text(),
            topleft=(0, 0),
            name='Time',
            groups=self.all_sprites,
        )
        self.fps_line = FpsLine(
            font=self.font,
            text=self._fps_text(),
            topleft=(0, FPS_LINE_TOP),
            name='FPS',
            groups=self.all_sprites,
        )
        self.square = Sprite(
            x=0,
            y=self.screen_height // 2 + SQUARE_BELOW_MIDDLE,
            width=SQUARE_SIZE,
            height=SQUARE_SIZE,
            name='Square',
            groups=self.all_sprites,
        )
        self.square.image.fill(WHITE)
        # Drawn every frame: it moves every frame once started
        self.square.dirty = 2
        self.record_line = TextLine(
            font=self.font,
            text=self._record_text(),
            topleft=(self.screen_width // 4, self.screen_height // 2),
            name='Record',
            groups=self.all_sprites,
        )
        self.record_line.visible = False

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> None:
        """Add game-specific arguments to the global parser.

        This class method will get called automatically by the GameEngine class.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        """
        # argparse's version action prints and exits; store_true did nothing, and the demo has
        # no balls for the old -b/--balls to count (BUGS.md #178 items 25 and 31)
        parser.add_argument(
            '-v',
            '--version',
            action='version',
            version=f'{cls.NAME} {cls.VERSION}',
            help='print the game version and exit',
        )

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Update the scene.

        This method will get called automatically by the GameEngine class.

        Args:
            dt: The delta time (float).

        """
        if self.start:
            self.dt_timer += dt
            self.rect_pos += self.velocity * dt
        # The square's pose: the whole pixel of its position (screen space)
        self.square.rect.x = int(self.rect_pos)

        if self.rect_pos > self.screen_width and not self.passed:
            self.record = self.dt_timer
            self.passed = True
            self.record_line.text = self._record_text()
            self.record_line.visible = True

    @override
    def update(self: Self) -> None:
        """Show this frame's time and FPS (visual only: drawing is the sprite group's).

        This method will get called automatically by the GameEngine class.

        """
        self.time_line.text = self._time_text()
        self.fps_line.text = self._fps_text()
        super().update()

    def _time_text(self: Self) -> str:
        """Return the time line: the seconds since Space.

        Returns:
            The text.

        """
        return f'Time: {round(self.dt_timer, 2)}'

    def _fps_text(self: Self) -> str:
        """Return the FPS line.

        Returns:
            The text.

        """
        return f'FPS: {round(self.fps, 2)}'

    def _record_text(self: Self) -> str:
        """Return the record line: the seconds the square took to cross the screen.

        Returns:
            The text.

        """
        return f'Time: {round(self.record, 2)}'

    @override
    def on_key_down_event(self: Self, event: KeyEvent) -> None:
        """Handle key down events.

        Args:
            event (KeyEvent): The event to handle.

        """
        if current_input().key_pressed(pygame.K_SPACE):
            self.start = True


def main() -> None:
    """Run the main entry point for the game."""
    GameEngine(game=Game).start()
