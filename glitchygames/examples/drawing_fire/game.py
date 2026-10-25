"""Drawing Fire: a pencil-on-paper stick-figure battle.

This cut is the battlefield (paper, and the ground with its hills) and a battle that plays
itself: every soldier is driven by the computer, the winner is announced, and the next battle
starts on its own.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

import pygame

from glitchygames.engine import GameEngine
from glitchygames.examples.drawing_fire.battle import ARMY_NAMES, SOLDIERS_PER_SIDE, Battle
from glitchygames.examples.drawing_fire.drivers import (
    ComputerSoldier,
    computer_intents,
    muster_battle,
)
from glitchygames.scenes import Scene

if TYPE_CHECKING:
    from random import Random

    from glitchygames.examples.drawing_fire.terrain import Terrain

PAPER_COLOR = (251, 248, 239)
PENCIL_COLOR = (58, 58, 64)
GROUND_LINE_WIDTH = 2
# How long the winner is announced before the next battle starts (s)
VICTORY_SECONDS = 3.0
VICTORY_FONT_SIZE = 56


class Phase(enum.Enum):
    """Where the scene is: fighting, or announcing the winner."""

    BATTLE = 'battle'
    VICTORY = 'victory'


class DrawingFireScene(Scene):
    """The battlefield: a sheet of paper with a hilly ground line."""

    NAME = 'Drawing Fire'
    VERSION = '0.1'
    # After a hitch (a window drag, focus loss) logic advances at most this much in one frame
    MAX_FRAME_SECONDS: ClassVar[float | None] = 0.05

    def __init__(
        self: Self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Build the battlefield: its paper and its seeded terrain.

        Args:
            options: Command-line options.
            groups: The sprite group (a new one when None).

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()
        super().__init__(options=options, groups=groups)
        self.background_color = PAPER_COLOR
        self.battle_number = 0
        self.phase = Phase.BATTLE
        self.victory_message = ''
        self.victory_seconds = 0.0
        self.start_battle()

    def start_battle(self: Self) -> None:
        """Start the next battle: new terrain, sandbags and soldiers from the seeded streams."""
        self.battle_number += 1
        battle, minds, streams = muster_battle(
            battle_number=self.battle_number,
            width=self.screen_width,
            height=self.screen_height,
            soldiers_per_side=SOLDIERS_PER_SIDE,
        )
        self.battle: Battle = battle
        self.terrain: Terrain = battle.terrain
        self.minds: dict[int, ComputerSoldier] = minds
        self.soldier_streams: dict[int, Random] = streams
        self.phase = Phase.BATTLE
        self.victory_message = ''
        self.victory_seconds = 0.0
        # The ground is pencilled onto clean paper, under every sprite
        self.background.fill(PAPER_COLOR)
        self._draw_ground()

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Play the battle (every soldier is the computer's), or count down the victory.

        Args:
            dt: The seconds to advance.

        """
        super().dt_tick(dt)
        if self.phase is Phase.BATTLE:
            intents = computer_intents(
                battle=self.battle, minds=self.minds, streams=self.soldier_streams
            )
            self.battle.step(dt=dt, intents=intents)
            winner = self.battle.winner
            if winner is not None:
                self.phase = Phase.VICTORY
                self.victory_message = f'{ARMY_NAMES[winner]} wins!'
        else:
            self.victory_seconds += dt
            if self.victory_seconds >= VICTORY_SECONDS:
                self.start_battle()

    def _draw_ground(self: Self) -> None:
        """Pencil the ground line onto the background."""
        pygame.draw.lines(
            surface=self.background,
            color=PENCIL_COLOR,
            closed=False,
            points=list(enumerate(self.terrain.ground)),
            width=GROUND_LINE_WIDTH,
        )

    def _draw_victory_message(self: Self, screen: pygame.Surface) -> None:
        """Write the winner on the paper, in the middle of the sky.

        Args:
            screen: The display surface.

        """
        font = pygame.font.Font(None, VICTORY_FONT_SIZE)
        text = font.render(self.victory_message, antialias=True, color=PENCIL_COLOR)
        screen.blit(text, text.get_rect(center=(self.screen_width // 2, self.screen_height // 4)))

    @override
    def render(self: Self, screen: pygame.Surface) -> None:
        """Draw the paper with its ground line, then every sprite.

        Args:
            screen: The display surface.

        """
        screen.blit(self.background, (0, 0))
        self.all_sprites.clear(screen, self.background)
        self.all_sprites.draw(screen)
        if self.victory_message:
            self._draw_victory_message(screen)
        self.rects = None  # The whole screen is presented


def main() -> None:
    """Run Drawing Fire."""
    GameEngine(game=DrawingFireScene).start()


if __name__ == '__main__':
    main()
