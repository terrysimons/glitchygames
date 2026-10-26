"""Constants and tuning values both Brave Adventurer games share.

Screen and world, physics, camera, parallax, layers, scoring, terrain and background colours, HUD
colours, lives and the death and game-over rumbles. Each game's own sprite sizes and colours
are in its constants module (brave_adventurer.constants, brave_adventurer_papyrus.constants).
"""

from __future__ import annotations

# Screen / world
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 480
GROUND_Y = 400
GROUND_HEIGHT = 80

# Physics (pixels per second, pixels per second squared)
GRAVITY = 1200.0
JUMP_VELOCITY = -500.0
PLAYER_RUN_SPEED = 200.0
PLAYER_ACCELERATION = 1600.0  # pixels/sec^2 when ramping toward target speed
PLAYER_DECELERATION = 1200.0  # pixels/sec^2 when slowing to a stop
MAX_FALL_SPEED = 800.0

# Velocity thresholds for animation state detection
JUMPING_VELOCITY_THRESHOLD = -10.0
FALLING_VELOCITY_THRESHOLD = 10.0
MOVING_VELOCITY_THRESHOLD = 0.1

# Camera
CAMERA_LEAD = 250

# Parallax scroll factors (multiplied by camera.x)
PARALLAX_SKY = 0.0
PARALLAX_FAR = 0.1
PARALLAX_MID = 0.3
PARALLAX_NEAR = 0.7

# Rendering layer depths (higher = drawn on top)
LAYER_SKY = 0
LAYER_FAR_BACKGROUND = 1
LAYER_MID_BACKGROUND = 2
LAYER_NEAR_BACKGROUND = 3
LAYER_TERRAIN = 4
LAYER_COLLECTIBLES = 5
LAYER_ENEMIES = 6
LAYER_PLAYER = 7

# Animation tuning
# Speed: radians per second for sin-based animation (~0.8 cycles/sec)
ANIMATION_SPEED = 5.0

# Stone wall
STONE_WALL_WIDTH = 32

# Lives
STARTING_LIVES = 3

# Scoring
DISTANCE_SCORE_DIVISOR = 10
COLLECTIBLE_SCORE_BONUS = 100

# Respawn
RESPAWN_OFFSET = 200

# Pit death threshold (how far below screen before death)
PIT_DEATH_THRESHOLD = 100

# Egyptian color palette
SKY_COLOR = (135, 180, 220)
HORIZON_COLOR = (210, 190, 140)
SAND_COLOR = (210, 180, 120)
DARK_SAND = (180, 150, 95)
PYRAMID_COLOR = (190, 170, 110)
PYRAMID_SHADOW = (160, 140, 90)
STONE_COLOR = (140, 130, 115)
STONE_MORTAR = (120, 110, 100)
PIT_WALL_COLOR = (90, 70, 50)
PIT_WALL_HIGHLIGHT = (110, 90, 65)
PIT_WALL_SHADOW = (70, 50, 35)
PIT_FLOOR_COLOR = (40, 25, 15)
PIT_EDGE_COLOR = (130, 110, 80)
OASIS_GREEN = (60, 140, 50)
OASIS_TRUNK = (100, 70, 30)
OASIS_WATER = (70, 130, 170)
HUD_TEXT_COLOR = (255, 255, 255)
HUD_SHADOW_COLOR = (0, 0, 0)

# Rock and grass detail colors
ROCK_COLOR = (160, 145, 125)
GRASS_COLOR = (120, 160, 70)

# Death rumble pulses (RumbleController.pulse), tuned by feel. The game-over pulse is heavier
# and longer; it survives the switch to the game-over scene because pulses are finite.
DEATH_RUMBLE_LOW = 0.7
DEATH_RUMBLE_HIGH = 0.4
DEATH_RUMBLE_DURATION = 0.35
GAME_OVER_RUMBLE_LOW = 1.0
GAME_OVER_RUMBLE_HIGH = 0.6
GAME_OVER_RUMBLE_DURATION = 0.8
