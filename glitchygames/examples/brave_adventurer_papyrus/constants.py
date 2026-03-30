"""Papyrus Edition constants.

Re-exports shared physics/gameplay constants from the original edition,
and defines papyrus-specific sprite dimensions for TOML pixel art.
"""

from __future__ import annotations

from pathlib import Path

# Re-export all shared constants from the original edition.
# Physics, camera, layers, parallax, scoring, terrain colors, HUD colors.
from glitchygames.examples.brave_adventurer.constants import (
    ANIMATION_SPEED,
    CAMERA_LEAD,
    COLLECTIBLE_SCORE_BONUS,
    DARK_SAND,
    DISTANCE_SCORE_DIVISOR,
    FALLING_VELOCITY_THRESHOLD,
    GRAVITY,
    GROUND_HEIGHT,
    GROUND_Y,
    HUD_SHADOW_COLOR,
    HUD_TEXT_COLOR,
    JUMP_VELOCITY,
    JUMPING_VELOCITY_THRESHOLD,
    LAYER_COLLECTIBLES,
    LAYER_ENEMIES,
    LAYER_FAR_BACKGROUND,
    LAYER_MID_BACKGROUND,
    LAYER_NEAR_BACKGROUND,
    LAYER_PLAYER,
    LAYER_SKY,
    LAYER_TERRAIN,
    MAX_FALL_SPEED,
    MOVING_VELOCITY_THRESHOLD,
    PARALLAX_FAR,
    PARALLAX_MID,
    PARALLAX_NEAR,
    PARALLAX_SKY,
    PIT_DEATH_THRESHOLD,
    PIT_EDGE_COLOR,
    PIT_FLOOR_COLOR,
    PIT_WALL_COLOR,
    PIT_WALL_HIGHLIGHT,
    PIT_WALL_SHADOW,
    PLAYER_RUN_SPEED,
    RESPAWN_OFFSET,
    SAND_COLOR,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SKY_COLOR,
    STARTING_LIVES,
    STONE_COLOR,
    STONE_MORTAR,
    STONE_WALL_WIDTH,
)

__all__ = [
    'ANIMATION_SPEED',
    'CAMERA_LEAD',
    'COLLECTIBLE_SCORE_BONUS',
    'DARK_SAND',
    'DISTANCE_SCORE_DIVISOR',
    'FALLING_VELOCITY_THRESHOLD',
    'GRAVITY',
    'GROUND_HEIGHT',
    'GROUND_Y',
    'HUD_SHADOW_COLOR',
    'HUD_TEXT_COLOR',
    'JUMPING_VELOCITY_THRESHOLD',
    'JUMP_VELOCITY',
    'LAYER_COLLECTIBLES',
    'LAYER_ENEMIES',
    'LAYER_FAR_BACKGROUND',
    'LAYER_MID_BACKGROUND',
    'LAYER_NEAR_BACKGROUND',
    'LAYER_PLAYER',
    'LAYER_SKY',
    'LAYER_TERRAIN',
    'MAGENTA_KEY',
    'MAX_FALL_SPEED',
    'MOVING_VELOCITY_THRESHOLD',
    'PAPYRUS_COBRA_HEIGHT',
    'PAPYRUS_COBRA_WIDTH',
    'PAPYRUS_GOLD_SCARAB_SIZE',
    'PAPYRUS_PLAYER_HEIGHT',
    'PAPYRUS_PLAYER_WIDTH',
    'PAPYRUS_SCARAB_HEIGHT',
    'PAPYRUS_SCARAB_WIDTH',
    'PAPYRUS_SCORPION_HEIGHT',
    'PAPYRUS_SCORPION_WIDTH',
    'PARALLAX_FAR',
    'PARALLAX_MID',
    'PARALLAX_NEAR',
    'PARALLAX_SKY',
    'PIT_DEATH_THRESHOLD',
    'PIT_EDGE_COLOR',
    'PIT_FLOOR_COLOR',
    'PIT_WALL_COLOR',
    'PIT_WALL_HIGHLIGHT',
    'PIT_WALL_SHADOW',
    'PLAYER_RUN_SPEED',
    'RESPAWN_OFFSET',
    'SAND_COLOR',
    'SCREEN_HEIGHT',
    'SCREEN_WIDTH',
    'SKY_COLOR',
    'SPRITES_DIR',
    'SPRITE_SCALE',
    'STARTING_LIVES',
    'STONE_COLOR',
    'STONE_MORTAR',
    'STONE_WALL_WIDTH',
]

# Display scale factor (TOML pixel art scaled up for visibility)
SPRITE_SCALE = 2

# Magenta transparency key
MAGENTA_KEY = (255, 0, 255)

# Papyrus sprite dimensions (native TOML size * SPRITE_SCALE for collision hitboxes)
# Player native image: 20x28. Visible feet end at row 25 in the tallest
# frames. Collision height uses feet position so the player stands on ground.
PAPYRUS_PLAYER_WIDTH = 20 * SPRITE_SCALE
PAPYRUS_PLAYER_HEIGHT = 25 * SPRITE_SCALE
PAPYRUS_COBRA_WIDTH = 12 * SPRITE_SCALE
PAPYRUS_COBRA_HEIGHT = 16 * SPRITE_SCALE
PAPYRUS_SCARAB_WIDTH = 10 * SPRITE_SCALE
PAPYRUS_SCARAB_HEIGHT = 8 * SPRITE_SCALE
PAPYRUS_SCORPION_WIDTH = 14 * SPRITE_SCALE
PAPYRUS_SCORPION_HEIGHT = 10 * SPRITE_SCALE
PAPYRUS_GOLD_SCARAB_SIZE = 10 * SPRITE_SCALE

# Path to TOML sprite files
SPRITES_DIR = Path(__file__).parent / 'sprites'
