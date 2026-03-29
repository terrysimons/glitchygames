"""Constants for the Bitmappy pixel art editor."""

from __future__ import annotations

import logging
from typing import Any

from glitchygames.sprites import BitmappySprite

# Logger
LOG = logging.getLogger('game.tools.bitmappy')

# Transparency
MAGENTA_TRANSPARENT = (255, 0, 255)  # Magenta color used for transparency
TRANSPARENT_GLYPH = '█'  # Block character used for transparent pixels

# Sprite dimensions
LARGE_SPRITE_DIMENSION = 128  # Sprites this size or larger get special handling
MIN_PIXEL_DISPLAY_SIZE = 2  # Minimum pixel display size for large sprites
MAX_PIXELS_ACROSS = 64
MIN_PIXELS_ACROSS = 1
MAX_PIXELS_TALL = 64
MIN_PIXELS_TALL = 1
MIN_COLOR_VALUE = 0
MAX_COLOR_VALUE = 255

# Timing and debouncing
MODEL_DOWNLOAD_TIME_THRESHOLD_SECONDS = 60  # AI model response time threshold
PIXEL_CHANGE_DEBOUNCE_SECONDS = 0.1  # Debounce timer for auto-submit

# Color and training
SPRITE_ASPECT_RATIO_TOLERANCE = 0.2  # Tolerance for AI training aspect ratio matching
COLOR_QUANTIZATION_GROUP_DISTANCE_THRESHOLD = 1000  # Squared Euclidean distance for color grouping
DEBUG_LOG_FIRST_N_PIXELS = 5  # How many non-magenta pixels to log for debugging
MIN_FILM_STRIPS_FOR_PANEL_POSITIONING = 2  # Minimum film strips before AI panel positioning
MAX_COLORS_FOR_AI_TRAINING = 64  # Max unique colors before quantization
PROGRESS_LOG_MIN_HEIGHT = 32  # Minimum image height to trigger progress logging

# Controller acceleration
CONTROLLER_ACCEL_LEVEL1_TIME = 0.8  # Acceleration timing thresholds
CONTROLLER_ACCEL_LEVEL2_TIME = 1.5
CONTROLLER_ACCEL_LEVEL3_TIME = 2.5
CONTROLLER_ACCEL_JUMP_LEVEL1 = 2  # Pixel jump sizes at acceleration levels
CONTROLLER_ACCEL_JUMP_LEVEL2 = 4
CONTROLLER_ACCEL_JUMP_LEVEL3 = 8

# Joystick mappings
HAT_INPUT_MAGNITUDE_THRESHOLD = 0.5  # Joystick hat dead zone
JOYSTICK_LEFT_SHOULDER_BUTTON = 9  # Joystick button mapping for left shoulder
JOYSTICK_HAT_RIGHT = 2  # Joystick hat bitmask for right direction
JOYSTICK_HAT_DOWN = 4  # Joystick hat bitmask for down direction
JOYSTICK_HAT_LEFT = 8  # Joystick hat bitmask for left direction

# AI training
AI_TRAINING_SINGLE_FRAME_EXAMPLE_COUNT = 2  # Threshold for single-frame sprite shortcut

# Color field parsing
MIN_COLOR_FIELD_VALUES_FOR_GREEN = 2  # Minimum parsed color field values for green
MIN_COLOR_FIELD_VALUES_FOR_BLUE = 3  # Minimum parsed color field values for blue

# AI validation
AI_CAPABILITY_RESPONSE_FIELD_COUNT = 2  # Expected field count for AI capability response
AI_VALIDATION_MAX_RETRIES = 2  # Maximum retries for AI response validation

# AI model configuration
AI_MODEL: str = 'anthropic:claude-sonnet-4-5'
AI_TIMEOUT = 600  # Seconds to wait for AI response (10 minutes for ollama models)
AI_QUEUE_SIZE = 10
AI_MAX_CONTEXT_SIZE = 65536  # Total context window size
AI_MAX_INPUT_TOKENS = 8192  # Maximum tokens for INPUT (prompts, examples)
AI_MAX_OUTPUT_TOKENS = 64000  # Maximum tokens for OUTPUT (AI response, large sprites)
AI_MAX_TRAINING_EXAMPLES = 1000  # Allow many more training examples for full context

# Retry configuration for AI requests
AI_MAX_RETRIES = 5  # Maximum number of retry attempts
AI_BASE_DELAY = 1.0  # Base delay in seconds for exponential backoff
AI_MAX_DELAY = 60.0  # Maximum delay between retries

# Model download timeout (much longer for initial model download)
AI_MODEL_DOWNLOAD_TIMEOUT = 1800  # 30 minutes for model download

# AI training state (module-level global)
ai_training_state: dict[str, list[dict[str, Any]] | str | None] = {
    'data': [],
    'format': None,  # Will be detected from training files
}

# Turn on sprite debugging
BitmappySprite.DEBUG = True
