"""Papyrus Edition constants.

Re-exports shared physics/gameplay constants from brave_adventurer_core,
and defines papyrus-specific sprite dimensions for TOML pixel art.
"""

from __future__ import annotations

from pathlib import Path

# Re-export all shared constants from brave_adventurer_core.
# Physics, camera, layers, parallax, scoring, terrain colors, HUD colors.
from brave_adventurer_core.constants import (
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
    PLAYER_ACCELERATION,
    PLAYER_DECELERATION,
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
    'PAPYRUS_PLAYER_HEIGHT',
    'PAPYRUS_SCARAB_HEIGHT',
    'PAPYRUS_SCORPION_HEIGHT',
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
    'PLAYER_ACCELERATION',
    'PLAYER_DECELERATION',
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

# Papyrus sprite heights (native TOML size * SPRITE_SCALE) place feet on the ground and walls
# (game.py); the engine culls world sprites by their rects, so no widths are needed.
# Horizontal terrain contact and sprite-vs-sprite hits use each sprite's collision rect: the
# TOML [hitbox] sections, scaled by AnimatedSprite.hitbox_scale.
# Player native image: 20x28. Visible feet end at row 27 in the tallest frames (idle),
# row 25 in falling and rows 24-25 in running and jumping. The player sets
# frame_anchor = FrameAnchor.BOTTOM: each frame is drawn lower so its feet sit on the
# 27-row foot line, which is what the player stands on.
PAPYRUS_PLAYER_HEIGHT = 27 * SPRITE_SCALE
PAPYRUS_COBRA_HEIGHT = 16 * SPRITE_SCALE
PAPYRUS_SCARAB_HEIGHT = 8 * SPRITE_SCALE
PAPYRUS_SCORPION_HEIGHT = 10 * SPRITE_SCALE

# Path to TOML sprite files
SPRITES_DIR = Path(__file__).parent / 'sprites'
