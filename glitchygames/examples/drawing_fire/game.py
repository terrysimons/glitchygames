"""Drawing Fire: a pencil-on-paper stick-figure battle.

This cut is the battlefield (paper, and the ground with its hills) and a battle that plays
itself: every soldier is driven by the computer, the winner is announced, and the next battle
starts on its own. ``drawing`` draws it all in pencil.
"""

from __future__ import annotations

import enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

import pygame

from glitchygames.engine import GameEngine
from glitchygames.examples.drawing_fire.battle import ARMY_NAMES, SOLDIERS_PER_SIDE, Battle
from glitchygames.examples.drawing_fire.drawing import (
    draw_banner,
    draw_bullet,
    draw_hud,
    draw_sandbag,
    draw_soldier,
    draw_terrain,
    load_soldier_frames,
)
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
SOLDIER_SPRITE_PATH = Path(__file__).parent / 'sprites' / 'soldier.toml'
# How long the winner is announced before the next battle starts (s)
VICTORY_SECONDS = 3.0


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
        # The soldier sprite, scaled once and recoloured once per army
        self.soldier_frames = load_soldier_frames(path=SOLDIER_SPRITE_PATH)
        self.walking_soldier_ids: set[int] = set()
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
        self.walking_soldier_ids = set()
        # The ground is pencilled onto clean paper, under every sprite (it never changes in a
        # battle, and LayeredDirty repaints the background, so it has to be on the background)
        self.background.fill(PAPER_COLOR)
        draw_terrain(self.background, self.terrain)

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
            walked_from = {soldier.soldier_id: soldier.x for soldier in self.battle.soldiers}
            self.battle.step(dt=dt, intents=intents)
            # A soldier whose x changed this step is walking
            self.walking_soldier_ids = {
                soldier.soldier_id
                for soldier in self.battle.soldiers
                if soldier.alive and soldier.x != walked_from[soldier.soldier_id]
            }
            winner = self.battle.winner
            if winner is not None:
                self.phase = Phase.VICTORY
                self.victory_message = f'{ARMY_NAMES[winner]} wins!'
        else:
            self.victory_seconds += dt
            if self.victory_seconds >= VICTORY_SECONDS:
                self.start_battle()

    @override
    def render(self: Self, screen: pygame.Surface) -> None:
        """Draw the paper and ground, then the sandbags, soldiers and bullets in pencil.

        Args:
            screen: The display surface.

        """
        screen.blit(self.background, (0, 0))
        self.all_sprites.clear(screen, self.background)
        self.all_sprites.draw(screen)
        for sandbag in self.battle.sandbags:
            draw_sandbag(screen, sandbag, self.terrain)
        # The fallen are drawn first, so the standing are never hidden behind them
        for soldier in sorted(self.battle.soldiers, key=lambda soldier: soldier.alive):
            draw_soldier(
                screen,
                soldier,
                frames=self.soldier_frames,
                marked=None,
                walking=soldier.soldier_id in self.walking_soldier_ids,
                seconds=self.battle.seconds,
            )
        for bullet in self.battle.bullets:
            draw_bullet(screen, bullet)
        draw_hud(screen, self.battle)
        if self.victory_message:
            draw_banner(screen, self.victory_message)
        self.rects = None  # The whole screen is presented


def main() -> None:
    """Run Drawing Fire."""
    GameEngine(game=DrawingFireScene).start()


if __name__ == '__main__':
    main()
