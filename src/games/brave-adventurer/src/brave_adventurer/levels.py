"""Brave Adventurer's level manager: the shared level data, built with its drawn sprites.

The level data (``LEVEL_1``, ``ScreenData``) and the building (``LevelManager``) both games share
are in brave_adventurer_core.levels.
"""

from __future__ import annotations

from typing import override

from brave_adventurer.enemies import Cobra, Scarab, Scorpion
from brave_adventurer.terrain import GoldScarab
from brave_adventurer_core.levels import LevelManager


class ClassicLevelManager(LevelManager):
    """Level manager that creates the classic edition's sprites, drawn from primitives."""

    @override
    def _get_enemy_class_map(self) -> dict[str, type]:
        """Return the classic edition's enemy classes.

        Returns:
            Dict mapping string names to enemy sprite classes.

        """
        return {
            'cobra': Cobra,
            'scarab': Scarab,
            'scorpion': Scorpion,
        }

    @override
    def _get_collectible_class(self) -> type:
        """Return the classic edition's gold scarab.

        Returns:
            The collectible sprite class.

        """
        return GoldScarab
