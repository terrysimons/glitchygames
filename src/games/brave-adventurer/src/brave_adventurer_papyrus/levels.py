"""Papyrus Edition level manager.

Subclasses the shared LevelManager to create papyrus (TOML) sprites
for enemies and collectibles while keeping the same level data.
"""

from __future__ import annotations

from typing import override

from brave_adventurer_core.levels import LEVEL_1, LevelManager, ScreenData
from brave_adventurer_papyrus.terrain import PapyrusGoldScarab

# Re-export for use by game.py
__all__ = ['LEVEL_1', 'PapyrusLevelManager', 'ScreenData']


class PapyrusLevelManager(LevelManager):
    """Level manager that creates papyrus (TOML) sprites.

    Gives the enemy class map and the collectible class as TOML-animated
    sprite classes instead of primitive-drawn ones.
    """

    @override
    def _get_enemy_class_map(self) -> dict[str, type]:
        """Return papyrus enemy classes instead of primitive ones.

        Returns:
            Dict mapping string names to papyrus enemy sprite classes.

        """
        from brave_adventurer_papyrus.enemies import (
            PapyrusCobra,
            PapyrusScarab,
            PapyrusScorpion,
        )

        return {
            'cobra': PapyrusCobra,
            'scarab': PapyrusScarab,
            'scorpion': PapyrusScorpion,
        }

    @override
    def _get_collectible_class(self) -> type:
        """Return the papyrus (TOML) gold scarab instead of the primitive one.

        Returns:
            The collectible sprite class.

        """
        return PapyrusGoldScarab
