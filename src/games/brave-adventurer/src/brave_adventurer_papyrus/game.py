"""Brave Adventurer: Papyrus Edition - TOML sprite art variant.

Same gameplay as the primitives edition, but all character and entity
sprites use the GlitchyGames TOML animation system with hand-drawn
pixel art. Backgrounds and terrain keep primitives.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Self, override

from brave_adventurer_core.scene import BraveAdventurerSceneBase
from brave_adventurer_papyrus.constants import (
    GROUND_Y,
    PAPYRUS_PLAYER_HEIGHT,
)
from brave_adventurer_papyrus.levels import PapyrusLevelManager
from brave_adventurer_papyrus.player import PapyrusPlayer
from glitchygames.collision.detection import snapped_world_position
from glitchygames.engine import GameEngine

if TYPE_CHECKING:
    import pygame

    from brave_adventurer_papyrus.enemies import PapyrusScarab

log = logging.getLogger('game')


class PapyrusBraveAdventurerScene(BraveAdventurerSceneBase):
    """Papyrus Edition game scene.

    Identical gameplay to the primitives edition, but uses TOML sprite
    animations for the player, enemies, and collectibles. Backgrounds
    and terrain reuse the primitives drawing system.
    """

    NAME = 'Brave Adventurer: Papyrus Edition'
    LEVEL_MANAGER_CLASS = PapyrusLevelManager
    PLAYER_CLASS = PapyrusPlayer
    PLAYER_START_WORLD_Y = GROUND_Y - PAPYRUS_PLAYER_HEIGHT
    # Papyrus's own save namespace: its players' saved high scores live there
    SAVE_APP_NAME = 'brave-adventurer-papyrus'

    def _snapped_player_top(self: Self) -> int:
        """Return the player's world y snapped as the engine draws it (before draw_offset).

        Papyrus stands the player on a fixed foot line PAPYRUS_PLAYER_HEIGHT below this; each
        anchored frame is drawn its draw_offset lower, so its visible feet meet that line.

        Returns:
            int: The snapped world y.

        """
        _, snapped_y = snapped_world_position(self.player, self.player.world_x, self.player.world_y)
        return snapped_y

    @override
    def _player_top_and_foot_line(self: Self, player_rect: pygame.Rect) -> tuple[int, int]:
        """Return the snapped world y and the fixed foot line PAPYRUS_PLAYER_HEIGHT below it.

        Args:
            player_rect: The player's collision rect (unused: Papyrus's foot line is fixed).

        Returns:
            tuple[int, int]: The snapped world y and the foot line.

        """
        player_top = self._snapped_player_top()
        return player_top, player_top + PAPYRUS_PLAYER_HEIGHT

    @override
    def _player_world_y_standing_on(self: Self, surface_y: int) -> int:
        """Return the world y that stands the fixed foot line on a surface (an int).

        Args:
            surface_y: The world y of the ground's or a wall's top.

        Returns:
            int: The player's world y.

        """
        return surface_y - PAPYRUS_PLAYER_HEIGHT

    @override
    def _scarab_class(self: Self) -> type[PapyrusScarab]:
        """Return this game's scarab (imported here, where the terrain collision imported it).

        Returns:
            type[PapyrusScarab]: The scarab class.

        """
        from brave_adventurer_papyrus.enemies import PapyrusScarab

        return PapyrusScarab


def main() -> None:
    """Run Brave Adventurer: Papyrus Edition."""
    GameEngine(game=PapyrusBraveAdventurerScene).start()


if __name__ == '__main__':
    main()
