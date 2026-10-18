"""Level data definitions and level manager for Brave Adventurer.

Levels are defined as sequences of screen-width segments. Each segment
specifies ground platforms, walls, enemies, and collectibles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from glitchygames.examples.brave_adventurer.constants import (
    SCREEN_WIDTH,
)
from glitchygames.examples.brave_adventurer.terrain import (
    GoldScarab,
    GroundSegment,
    StoneWall,
)

if TYPE_CHECKING:
    import pygame

    from glitchygames.sprites import Sprite


@dataclass
class ScreenData:
    """Definition of one screen-width of level content.

    All x/y values are local to the screen (0 to SCREEN_WIDTH).
    The LevelManager translates them to world coordinates.

    Attributes:
        ground_segments: List of (local_x, width) tuples for ground platforms.
        walls: List of (local_x, height) tuples for stone walls.
        enemies: List of (type_name, local_x, kwargs) tuples for enemy placement.
        collectibles: List of (local_x, local_y) tuples for gold scarab positions.

    """

    ground_segments: list[tuple[int, int]] = field(default_factory=list)
    walls: list[tuple[int, int]] = field(default_factory=list)
    enemies: list[tuple[str, int, dict[str, Any]]] = field(default_factory=list)
    collectibles: list[tuple[int, int]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Level 1: "The Path of the Pharaoh"
#
# 20 screens of progressively increasing difficulty.
# Screen width = 800px. Ground at y=400, height=80.
# ---------------------------------------------------------------------------

LEVEL_1: list[ScreenData] = [
    # Screen 0: Flat ground, intro area - no hazards
    ScreenData(
        ground_segments=[(0, 800)],
        collectibles=[(300, 370), (350, 370), (400, 370)],
    ),
    # Screen 1: Flat ground with a couple of collectibles placed higher
    ScreenData(
        ground_segments=[(0, 800)],
        collectibles=[(200, 340), (500, 340), (600, 370)],
    ),
    # Screen 2: First short wall to teach jumping
    ScreenData(
        ground_segments=[(0, 800)],
        walls=[(400, 48)],
        collectibles=[(400, 320)],
    ),
    # Screen 3: Two walls
    ScreenData(
        ground_segments=[(0, 800)],
        walls=[(250, 48), (550, 64)],
        collectibles=[(250, 310), (550, 300)],
    ),
    # Screen 4: First small pit
    ScreenData(
        ground_segments=[(0, 350), (450, 350)],
        collectibles=[(400, 320)],
    ),
    # Screen 5: First cobra
    ScreenData(
        ground_segments=[(0, 800)],
        enemies=[('cobra', 500, {})],
        collectibles=[(300, 370), (700, 370)],
    ),
    # Screen 6: Wall + cobra combo
    ScreenData(
        ground_segments=[(0, 800)],
        walls=[(300, 64)],
        enemies=[('cobra', 600, {})],
        collectibles=[(300, 300), (650, 370)],
    ),
    # Screen 7: First scarab beetle (rolling enemy)
    ScreenData(
        ground_segments=[(0, 800)],
        enemies=[('scarab', 700, {'speed': -120.0})],
        collectibles=[(200, 370), (400, 370)],
    ),
    # Screen 8: Wider pit
    ScreenData(
        ground_segments=[(0, 280), (480, 320)],
        collectibles=[(380, 300)],
    ),
    # Screen 9: Pit + wall after landing
    ScreenData(
        ground_segments=[(0, 300), (450, 350)],
        walls=[(550, 48)],
        collectibles=[(375, 310), (550, 320)],
    ),
    # Screen 10: First scorpion (patrolling enemy)
    ScreenData(
        ground_segments=[(0, 800)],
        enemies=[('scorpion', 400, {'patrol_range': 200})],
        collectibles=[(200, 370), (700, 370)],
    ),
    # Screen 11: Two pits with collectibles between
    ScreenData(
        ground_segments=[(0, 200), (300, 200), (600, 200)],
        collectibles=[(250, 310), (550, 310)],
    ),
    # Screen 12: Tall wall + scarab
    ScreenData(
        ground_segments=[(0, 800)],
        walls=[(350, 80)],
        enemies=[('scarab', 700, {'speed': -150.0})],
        collectibles=[(350, 280)],
    ),
    # Screen 13: Cobra + scorpion gauntlet
    ScreenData(
        ground_segments=[(0, 800)],
        enemies=[('cobra', 300, {}), ('scorpion', 550, {'patrol_range': 150})],
        collectibles=[(150, 370), (450, 370), (750, 370)],
    ),
    # Screen 14: Pit + cobra on the far side
    ScreenData(
        ground_segments=[(0, 300), (480, 320)],
        enemies=[('cobra', 550, {})],
        collectibles=[(390, 300)],
    ),
    # Screen 15: Multiple walls and a scarab
    ScreenData(
        ground_segments=[(0, 800)],
        walls=[(200, 48), (400, 64), (600, 48)],
        enemies=[('scarab', 750, {'speed': -100.0})],
        collectibles=[(200, 320), (400, 300), (600, 320)],
    ),
    # Screen 16: Triple pit challenge
    ScreenData(
        ground_segments=[(0, 150), (250, 120), (470, 130), (700, 100)],
        collectibles=[(200, 310), (400, 310), (600, 310)],
    ),
    # Screen 17: Wall + pit combo
    ScreenData(
        ground_segments=[(0, 400), (550, 250)],
        walls=[(250, 64)],
        enemies=[('scorpion', 600, {'patrol_range': 180})],
        collectibles=[(250, 300), (475, 310)],
    ),
    # Screen 18: Full gauntlet - enemies and obstacles
    ScreenData(
        ground_segments=[(0, 350), (450, 350)],
        walls=[(150, 48)],
        enemies=[
            ('cobra', 250, {}),
            ('scarab', 750, {'speed': -140.0}),
        ],
        collectibles=[(150, 320), (400, 300), (650, 370)],
    ),
    # Screen 19: Victory stretch - collectible bonanza
    ScreenData(
        ground_segments=[(0, 800)],
        collectibles=[
            (100, 370),
            (200, 350),
            (300, 330),
            (400, 310),
            (500, 330),
            (600, 350),
            (700, 370),
        ],
    ),
]


class LevelManager:
    """Instantiates terrain, enemy, and collectible sprites from level data.

    Takes a list of ScreenData definitions and creates the corresponding
    sprite objects positioned in world coordinates.
    """

    def __init__(
        self,
        level_data: list[ScreenData],
        groups: pygame.sprite.LayeredDirty[Sprite],
    ) -> None:
        """Initialize the level manager and build all sprites.

        Args:
            level_data: List of screen definitions for the level.
            groups: The sprite group to add all created sprites to.

        """
        self.level_data = level_data
        self.groups = groups
        self.ground_sprites: list[GroundSegment] = []
        self.wall_sprites: list[StoneWall] = []
        self.enemy_sprites: list[Any] = []
        self.collectible_sprites: list[Any] = []
        self._build()

    def _build(self) -> None:
        """Create all sprites from level data."""
        # Import enemies here to avoid circular imports
        # (enemies module will be created in Phase 4)
        enemy_class_map = self._get_enemy_class_map()

        for screen_index, screen in enumerate(self.level_data):
            base_x = screen_index * SCREEN_WIDTH

            # Ground segments
            for segment_x, segment_width in screen.ground_segments:
                ground = GroundSegment(
                    world_x=base_x + segment_x,
                    segment_width=segment_width,
                    groups=self.groups,
                )
                self.ground_sprites.append(ground)

            # Stone walls
            for wall_x, wall_height in screen.walls:
                wall = StoneWall(
                    world_x=base_x + wall_x,
                    wall_height=wall_height,
                    groups=self.groups,
                )
                self.wall_sprites.append(wall)

            # Enemies
            for enemy_type, enemy_x, enemy_kwargs in screen.enemies:
                if enemy_type in enemy_class_map:
                    enemy_class = enemy_class_map[enemy_type]
                    enemy = enemy_class(
                        world_x=base_x + enemy_x,
                        groups=self.groups,
                        **enemy_kwargs,
                    )
                    self.enemy_sprites.append(enemy)

            # Collectibles
            for collectible_x, collectible_y in screen.collectibles:
                collectible = GoldScarab(
                    world_x=base_x + collectible_x,
                    world_y=collectible_y,
                    groups=self.groups,
                )
                self.collectible_sprites.append(collectible)

    def _get_enemy_class_map(self) -> dict[str, type]:
        """Return a mapping of enemy type names to their classes.

        Uses lazy import to avoid circular dependency with the enemies module.

        Returns:
            Dict mapping string names to enemy sprite classes.

        """
        try:
            from glitchygames.examples.brave_adventurer.enemies import (
                Cobra,
                Scarab,
                Scorpion,
            )
        except ImportError:
            return {}
        else:
            return {
                'cobra': Cobra,
                'scarab': Scarab,
                'scorpion': Scorpion,
            }

    @property
    def level_width(self) -> int:
        """Total width of the level in world pixels."""
        return len(self.level_data) * SCREEN_WIDTH
