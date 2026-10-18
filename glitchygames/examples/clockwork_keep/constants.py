"""Constants for Clockwork Keep — a steampunk vertical tower climb."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Screen / World
# ---------------------------------------------------------------------------
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 480

# Tower layout: playfield is centered, walls on each side
WALL_WIDTH = 100
PLAYFIELD_LEFT = WALL_WIDTH
PLAYFIELD_RIGHT = SCREEN_WIDTH - WALL_WIDTH
PLAYFIELD_WIDTH = PLAYFIELD_RIGHT - PLAYFIELD_LEFT  # 600px

# ---------------------------------------------------------------------------
# Physics (pixels/sec or pixels/sec²)
# ---------------------------------------------------------------------------
GRAVITY = 1200.0
JUMP_VELOCITY = -480.0  # Normal jump — reaches ~96px up
JUMP_VELOCITY_RUNNING = -580.0  # Running jump — reaches ~140px up
MAX_FALL_SPEED = 800.0
PLAYER_WALK_SPEED = 160.0  # Normal movement
PLAYER_RUN_SPEED = 280.0  # Holding run button
PLAYER_ACCELERATION = 1600.0
PLAYER_DECELERATION = 1200.0
FALLING_VELOCITY_THRESHOLD = 50.0

# ---------------------------------------------------------------------------
# Player dimensions
# ---------------------------------------------------------------------------
PLAYER_WIDTH = 28
PLAYER_HEIGHT = 44

# ---------------------------------------------------------------------------
# Enemy dimensions
# ---------------------------------------------------------------------------
STEAM_SPRITE_WIDTH = 24
STEAM_SPRITE_HEIGHT = 24
GEAR_GOLEM_WIDTH = 32
GEAR_GOLEM_HEIGHT = 36

# ---------------------------------------------------------------------------
# Terrain dimensions
# ---------------------------------------------------------------------------
PLATFORM_HEIGHT = 12
ELEVATOR_WIDTH = 60
ELEVATOR_HEIGHT = 8

# ---------------------------------------------------------------------------
# Collectible dimensions
# ---------------------------------------------------------------------------
COG_SIZE = 16

# ---------------------------------------------------------------------------
# Camera (vertical only — no horizontal scroll)
# ---------------------------------------------------------------------------
CAMERA_LEAD_X = 0
CAMERA_LEAD_Y = 200  # Look ahead upward

# Parallax scroll factors (vertical)
PARALLAX_FAR = 0.1
PARALLAX_MID = 0.3
PARALLAX_NEAR = 0.7

# ---------------------------------------------------------------------------
# Layer depths (for LayeredDirty rendering order)
# ---------------------------------------------------------------------------
LAYER_FAR_BACKGROUND = 0
LAYER_MID_BACKGROUND = 1
LAYER_NEAR_BACKGROUND = 2
LAYER_WALLS = 3
LAYER_TERRAIN = 4
LAYER_COLLECTIBLES = 5
LAYER_ENEMIES = 6
LAYER_PLAYER = 7
LAYER_HUD = 8

# ---------------------------------------------------------------------------
# Animation
# ---------------------------------------------------------------------------
ANIMATION_SPEED = 8.0
LEG_SWING_AMPLITUDE = 3
ARM_SWING_AMPLITUDE = 2

# ---------------------------------------------------------------------------
# Gameplay
# ---------------------------------------------------------------------------
STARTING_LIVES = 3
PIT_DEATH_THRESHOLD = 100
INVINCIBILITY_DURATION = 1.5
ELEVATOR_SNAP_TOLERANCE = 5
GROUND_SNAP_TOLERANCE = 20

# Cog point values
COG_BRONZE_POINTS = 10
COG_SILVER_POINTS = 50
COG_GOLD_POINTS = 100

# Platform spacing — vertical gap between platforms for comfortable jumping
# Normal jump reaches ~96px, running jump ~140px
PLATFORM_GAP_EASY = 60  # Comfortable walking jump
PLATFORM_GAP_MEDIUM = 80  # Needs a good jump or short run
PLATFORM_GAP_HARD = 100  # Needs a running jump

# ---------------------------------------------------------------------------
# Floor themes: (bg_color, platform_color, platform_top, wall_color,
#                wall_accent, window_sky, led_color)
# ---------------------------------------------------------------------------

# Floor 0: Boiler Room — dark, warm, furnace glow
BOILER_BG = (30, 20, 12)
BOILER_PLATFORM = (90, 60, 35)
BOILER_PLATFORM_TOP = (110, 75, 45)
BOILER_WALL = (60, 40, 25)
BOILER_WALL_ACCENT = (80, 55, 30)
BOILER_WINDOW_SKY = (40, 60, 90)
BOILER_LED = (255, 100, 0)
BOILER_GLOW = (200, 100, 20)

# Floor 1: Gear Works — grey, metallic, copper accents
GEAR_BG = (30, 30, 35)
GEAR_PLATFORM = (80, 80, 90)
GEAR_PLATFORM_TOP = (100, 100, 110)
GEAR_WALL = (55, 55, 60)
GEAR_WALL_ACCENT = (75, 70, 65)
GEAR_WINDOW_SKY = (80, 120, 160)
GEAR_LED = (180, 120, 60)
GEAR_COPPER = (180, 120, 60)

# Floor 2: Clock Face — midnight blue, brass gold
CLOCK_BG = (12, 12, 30)
CLOCK_PLATFORM = (130, 110, 60)
CLOCK_PLATFORM_TOP = (160, 140, 80)
CLOCK_WALL = (40, 35, 55)
CLOCK_WALL_ACCENT = (60, 50, 75)
CLOCK_WINDOW_SKY = (140, 160, 200)
CLOCK_LED = (255, 200, 50)
CLOCK_BRASS = (200, 170, 60)

# ---------------------------------------------------------------------------
# Player colors
# ---------------------------------------------------------------------------
PLAYER_SKIN = (220, 180, 140)
PLAYER_VEST = (100, 60, 30)
PLAYER_GOGGLE_FRAME = (80, 80, 80)
PLAYER_GOGGLE_LENS = (120, 200, 220)
PLAYER_BOOTS = (60, 40, 20)
PLAYER_WRENCH = (160, 160, 170)

# ---------------------------------------------------------------------------
# HUD colors
# ---------------------------------------------------------------------------
HUD_TEXT_COLOR = (240, 220, 180)
HUD_SHADOW_COLOR = (40, 30, 20)

# ---------------------------------------------------------------------------
# DualSense mic button
# ---------------------------------------------------------------------------
MIC_BUTTON_CONTROLLER = 15
MIC_BUTTON_JOYSTICK = 16

# ---------------------------------------------------------------------------
# Elevator ride feel (tuned by eye and ear)
# ---------------------------------------------------------------------------
ELEVATOR_RIDE_DURATION = 4.0
ELEVATOR_RIDE_EASING = 'ease_in_sine'  # Arrives at speed so the stop reads as a slam
ELEVATOR_SPEED_SAMPLES = 100  # Points used to find the easing's peak slope
ELEVATOR_MOTOR_IDLE_FREQUENCY = 45.0  # Hz, motor at rest
ELEVATOR_MOTOR_PEAK_FREQUENCY = 110.0  # Hz, motor at full speed
ELEVATOR_MOTOR_MINIMUM_VOLUME = 0.15
ELEVATOR_MOTOR_MAXIMUM_VOLUME = 0.6
ELEVATOR_MOTOR_LOW_PASS_CUTOFF = 600.0  # Hz, keeps the sawtooth deep
ELEVATOR_MOTOR_TREMOLO_RATE = 8.0  # Hz, the motor's chug
ELEVATOR_MOTOR_TREMOLO_DEPTH = 0.4
ELEVATOR_BOUNCE_STRENGTH = 14.0  # Pixels
ELEVATOR_BOUNCE_DURATION = 0.6
ELEVATOR_BOUNCE_FREQUENCY = 7.0  # Hz
ELEVATOR_RATTLE_STRENGTH = 5.0
ELEVATOR_RATTLE_DURATION = 0.35
ELEVATOR_RATTLE_FREQUENCY = 25.0
