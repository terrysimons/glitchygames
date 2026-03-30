"""Papyrus Edition level manager.

Subclasses the original LevelManager to create papyrus (TOML) sprites
for enemies and collectibles while keeping the same level data.
"""

from __future__ import annotations

from typing import override

from glitchygames.examples.brave_adventurer.levels import LEVEL_1, LevelManager, ScreenData
from glitchygames.examples.brave_adventurer.terrain import GroundSegment, StoneWall
from glitchygames.examples.brave_adventurer_papyrus.constants import SCREEN_WIDTH
from glitchygames.examples.brave_adventurer_papyrus.terrain import PapyrusGoldScarab

# Re-export for use by game.py
__all__ = ['LEVEL_1', 'PapyrusLevelManager', 'ScreenData']


class PapyrusLevelManager(LevelManager):
    """Level manager that creates papyrus (TOML) sprites.

    Overrides the enemy class map and collectible creation to use
    TOML-animated sprite classes instead of primitive-drawn ones.
    """

    @override
    def _get_enemy_class_map(self) -> dict[str, type]:
        """Return papyrus enemy classes instead of primitive ones.

        Returns:
            Dict mapping string names to papyrus enemy sprite classes.

        """
        from glitchygames.examples.brave_adventurer_papyrus.enemies import (
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
    def _build(self) -> None:
        """Create all sprites from level data, using papyrus collectibles."""
        enemy_class_map = self._get_enemy_class_map()

        for screen_index, screen in enumerate(self.level_data):
            base_x = screen_index * SCREEN_WIDTH

            # Ground segments (reused from original - primitives)
            for segment_x, segment_width in screen.ground_segments:
                ground = GroundSegment(
                    world_x=base_x + segment_x,
                    segment_width=segment_width,
                    groups=self.groups,
                )
                self.ground_sprites.append(ground)

            # Stone walls (reused from original - primitives)
            for wall_x, wall_height in screen.walls:
                wall = StoneWall(
                    world_x=base_x + wall_x,
                    wall_height=wall_height,
                    groups=self.groups,
                )
                self.wall_sprites.append(wall)

            # Enemies (papyrus TOML sprites)
            for enemy_type, enemy_x, enemy_kwargs in screen.enemies:
                if enemy_type in enemy_class_map:
                    enemy_class = enemy_class_map[enemy_type]
                    enemy = enemy_class(
                        world_x=base_x + enemy_x,
                        groups=self.groups,
                        **enemy_kwargs,
                    )
                    self.enemy_sprites.append(enemy)

            # Collectibles (papyrus TOML sprites instead of primitive GoldScarab)
            for collectible_x, collectible_y in screen.collectibles:
                collectible = PapyrusGoldScarab(
                    world_x=base_x + collectible_x,
                    world_y=collectible_y,
                    groups=self.groups,
                )
                self.collectible_sprites.append(collectible)
