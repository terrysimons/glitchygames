#!/usr/bin/env python3
"""Glitchy Games Bitmap Editor."""

from __future__ import annotations

import collections
import configparser
import contextlib
import logging
import multiprocessing
import operator
import signal
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from queue import Empty
from typing import TYPE_CHECKING, ClassVar, Self, Dict

import pygame
import toml



# Try to import aisuite, but don't fail if it's not available
try:
    import aisuite as ai
except ImportError:
    ai = None

# Try to import voice recognition, but don't fail if it's not available
try:
    from glitchygames.events.voice import VoiceRecognitionManager
except ImportError:
    VoiceRecognitionManager = None

from glitchygames import events
from glitchygames.engine import GameEngine
from glitchygames.pixels import rgb_triplet_generator
from glitchygames.scenes import Scene
from glitchygames.sprites import (
    SPRITE_GLYPHS,
    BitmappySprite,
    SpriteFactory,
)
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from glitchygames.sprites.constants import DEFAULT_FILE_FORMAT
from glitchygames.ui import (
    ColorWellSprite,
    MenuBar,
    MenuItem,
    MultiLineTextBox,
    SliderSprite,
    TabControlSprite,
    TextSprite,
)
from glitchygames.ui.dialogs import (
    LoadDialogScene,
    NewCanvasDialogScene,
    SaveDialogScene,
)

from .canvas_interfaces import (
    AnimatedCanvasInterface,
    AnimatedCanvasRenderer,
    AnimatedSpriteSerializer,
)
from .film_strip import FilmStripWidget
from .multi_controller_manager import MultiControllerManager
from .controller_selection import ControllerSelection
from .visual_collision_manager import VisualCollisionManager
from .controller_mode_system import ControllerMode
from .undo_redo_manager import UndoRedoManager
from .operation_history import (
    CanvasOperationTracker,
    FilmStripOperationTracker,
    CrossAreaOperationTracker,
)

if TYPE_CHECKING:
    import argparse

# Constants
CONTENT_PREVIEW_LENGTH = 500

# Complete TOML format template for AI instructions
COMPLETE_TOML_FORMAT = """
COMPLETE TOML FORMAT REQUIREMENTS:

STATIC SPRITES (single-frame):
    [sprite] section with name and pixels
    [colors] section with colors.0 through colors.7
    Each color has red, green, blue values (0-255)

ANIMATED SPRITES (multi-frame):
    [sprite] section with name only (NO pixels item)
    [colors] section with 'colors."X"' section keys, where X is the character used in the pixels
    [[animation]] section with namespace, frame_interval, loop
    [[animation.frame]] sections with namespace, frame_index, pixels
    PER-FRAME TIMING: When asked to generate per-frame frame_intervals, add a frame_interval
    parameter to each frame where the frame's draw interval is different from the global
    animation namespace frame_interval

CRITICAL RULES:
    - ONLY include color definitions for colors that are actually used in the pixels
    - ALWAYS include namespace in each [[animation.frame]] section
    - ALWAYS include frame_index in each [[animation.frame]] section
    - ALWAYS include frame_interval and loop in [[animation]] section
    - NEVER mix static and animated content in the same file!
    - Static sprites: [sprite] with pixels + [colors] sections ONLY
    - Animated sprites: [sprite] with NO pixels item + [colors] + [[animation]] sections
      ONLY
    - IMPORTANT: Animated sprites must NOT have a pixels item in the [sprite] section!
    - CRITICAL: Use triple-quoted block strings for multi-line pixel data, never use single quotes
    - EFFICIENCY: Only define colors that appear in the pixel data (e.g., if pixels only use
      "0", only define [colors."0"])
"""

LOG = logging.getLogger("game.tools.bitmappy")

# Set up logging
if not LOG.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    LOG.addHandler(handler)
    LOG.setLevel(logging.DEBUG)

# Turn on sprite debugging
BitmappySprite.DEBUG = True
MAX_PIXELS_ACROSS = 64
MIN_PIXELS_ACROSS = 1
MAX_PIXELS_TALL = 64
MIN_PIXELS_TALL = 1
MIN_COLOR_VALUE = 0
MAX_COLOR_VALUE = 255


def detect_file_format(filename: str) -> str:
    """Detect file format from filename extension.

    Args:
        filename: The filename to analyze

    Returns:
        The detected file format ("ini", "yaml", "toml")

    """
    filename_lower = filename.lower()
    if filename_lower.endswith((".yaml", ".yml")):
        return "yaml"
    return "toml"  # Default to toml


def resource_path(*path_segments) -> Path:
    """Return the absolute Path to a resource.

    Args:
        *path_segments: Path segments to join

    Returns:
        Path: Absolute path to the resource

    """
    if hasattr(sys, "_MEIPASS"):
        # Running in PyInstaller bundle
        base_path = Path(sys._MEIPASS)
        # Note: We used --add-data "...:glitchygames/assets", so we must include
        # glitchygames/assets in the final path segments, e.g.:
        return base_path.joinpath(*path_segments)
    # Running in normal Python environment
    return Path(__file__).parent.parent.joinpath(*path_segments[1:])


AI_MODEL = "anthropic:claude-sonnet-4-5"
AI_TIMEOUT = 30  # Seconds to wait for AI response
AI_QUEUE_SIZE = 10
AI_MAX_TOKENS = 64000  # Maximum tokens for response (Claude Sonnet 4.5 limit)
AI_MAX_TRAINING_EXAMPLES = 1000  # Allow many more training examples for full context
# Load sprite files for AI training using SpriteFactory
AI_TRAINING_DATA = []
AI_TRAINING_FORMAT = None  # Will be detected from training files

# Load sprite configuration files for AI training
SPRITE_CONFIG_DIR = resource_path("glitchygames", "examples", "resources", "sprites")
def _detect_alpha_channel(colors: dict) -> bool:
    """Detect if colors contain alpha channel information or magenta transparency.

    Args:
        colors: Dictionary of color definitions

    Returns:
        bool: True if alpha channel is detected or magenta transparency is present
    """
    for color_key, color_data in colors.items():
        if isinstance(color_data, dict):
            # Check for alpha key or RGBA values
            if 'alpha' in color_data or 'a' in color_data:
                return True
            # Check if we have 4 values (RGBA) instead of 3 (RGB)
            if len(color_data) == 4:
                return True
            # Check for magenta transparency (255, 0, 255)
            r = color_data.get('red', color_data.get('r', 0))
            g = color_data.get('green', color_data.get('g', 0))
            b = color_data.get('blue', color_data.get('b', 0))
            if r == 255 and g == 0 and b == 255:
                return True
    return False


def _detect_alpha_channel_in_animation(animation_data: dict) -> bool:
    """Detect if animation frames contain alpha channel information.

    Args:
        animation_data: Animation configuration data

    Returns:
        bool: True if alpha channel is detected in any frame
    """
    # Handle different animation data structures
    if isinstance(animation_data, dict):
        for frame_name, frame_data in animation_data.items():
            if isinstance(frame_data, dict) and 'colors' in frame_data:
                if _detect_alpha_channel(frame_data['colors']):
                    return True
    elif isinstance(animation_data, list):
        # Handle list-based animation data
        for frame_data in animation_data:
            if isinstance(frame_data, dict) and 'colors' in frame_data:
                if _detect_alpha_channel(frame_data['colors']):
                    return True
    return False


def _convert_sprite_to_alpha_format(sprite_data: dict) -> dict:
    """Convert sprite data to proper alpha format.

    Args:
        sprite_data: Original sprite data

    Returns:
        dict: Converted sprite data with alpha support
    """
    converted_data = sprite_data.copy()

    if sprite_data.get("has_alpha", False):
        # Convert colors to RGBA format if needed
        if "colors" in converted_data:
            converted_data["colors"] = _convert_colors_to_rgba(converted_data["colors"])

        # Convert animation colors if present
        if "animations" in converted_data:
            converted_data["animations"] = _convert_animation_colors_to_rgba(converted_data["animations"])

    return converted_data


def _convert_colors_to_rgba(colors: dict) -> dict:
    """Convert color definitions to RGBA format with magenta transparency.

    Args:
        colors: Original color definitions

    Returns:
        dict: Colors converted to RGBA format
    """
    converted_colors = {}

    for color_key, color_data in colors.items():
        if isinstance(color_data, dict):
            # Extract RGB values
            r = color_data.get('red', color_data.get('r', 0))
            g = color_data.get('green', color_data.get('g', 0))
            b = color_data.get('blue', color_data.get('b', 0))

            # Check for magenta transparency (255, 0, 255) = alpha 0
            if r == 255 and g == 0 and b == 255:
                a = 0  # Fully transparent
            else:
                a = color_data.get('alpha', color_data.get('a', 255))  # Default to opaque

            converted_colors[color_key] = {
                'red': r,
                'green': g,
                'blue': b,
                'alpha': a
            }
        else:
            converted_colors[color_key] = color_data

    return converted_colors


def _convert_animation_colors_to_rgba(animations: dict) -> dict:
    """Convert animation frame colors to RGBA format.

    Args:
        animations: Animation data with color definitions

    Returns:
        dict: Animation data with RGBA colors
    """
    converted_animations = {}

    for frame_name, frame_data in animations.items():
        if isinstance(frame_data, dict) and 'colors' in frame_data:
            converted_animations[frame_name] = frame_data.copy()
            converted_animations[frame_name]['colors'] = _convert_colors_to_rgba(frame_data['colors'])
        else:
            converted_animations[frame_name] = frame_data

    return converted_animations


def load_ai_training_data():
    """Load AI training data from sprite config files."""
    global AI_TRAINING_DATA, AI_TRAINING_FORMAT

    LOG.info(f"Loading AI training data from: {SPRITE_CONFIG_DIR}")
    LOG.debug(f"Sprite config directory exists: {SPRITE_CONFIG_DIR.exists()}")

    if SPRITE_CONFIG_DIR.exists():
        # Look for TOML files
        toml_files = list(SPRITE_CONFIG_DIR.glob("*.toml"))

        if toml_files:
            config_files = toml_files
            AI_TRAINING_FORMAT = "toml"
            LOG.info(f"Found {len(config_files)} TOML sprite config files")
        else:
            config_files = []
            LOG.warning("No sprite config files found")

        for config_file in config_files:
            LOG.debug(f"Processing config file: {config_file}")
            try:
                # Parse the file directly instead of using SpriteFactory to avoid display requirements
                if AI_TRAINING_FORMAT == "toml":
                    import toml
                    with config_file.open(encoding="utf-8") as f:
                        config_data = toml.load(f)

                    # Normalize the TOML data to convert escaped newlines to actual newlines
                    config_data = _normalize_toml_data(config_data)

                    # Extract sprite data from TOML structure
                    sprite_data = {
                        "name": config_data.get("sprite", {}).get("name", "Unknown"),
                        "format": AI_TRAINING_FORMAT,
                        "sprite_type": "animated" if "animation" in config_data else "static",
                        "has_alpha": False,  # Will be determined from color data
                    }

                    # For static sprites, extract pixel data and colors
                    if "sprite" in config_data:
                        sprite_data["pixels"] = config_data["sprite"].get("pixels", "")
                        sprite_data["colors"] = config_data.get("colors", {})

                        # Check for alpha channel support in colors
                        sprite_data["has_alpha"] = _detect_alpha_channel(config_data.get("colors", {}))

                    # For animated sprites, extract animation data
                    if "animation" in config_data:
                        sprite_data["animations"] = config_data["animation"]
                        # Check for alpha in animation frames
                        sprite_data["has_alpha"] = _detect_alpha_channel_in_animation(config_data["animation"])


                # Convert sprite to proper alpha format if needed
                converted_sprite_data = _convert_sprite_to_alpha_format(sprite_data)

                AI_TRAINING_DATA.append(converted_sprite_data)
                LOG.info(f"Successfully loaded sprite config: {config_file.name} (alpha: {converted_sprite_data.get('has_alpha', False)})")

                # Create colorized ASCII output using dimensions from TOML data
                try:
                    from glitchygames.tools.ascii_renderer import ASCIIRenderer
                    renderer = ASCIIRenderer()

                    # Calculate dimensions from pixel data
                    if 'sprite' in config_data and 'pixels' in config_data['sprite']:
                        pixels_str = config_data['sprite']['pixels']
                        pixel_lines = pixels_str.strip().split('\n')
                        height = len(pixel_lines)
                        width = len(pixel_lines[0]) if pixel_lines else 0

                        # Add dimensions to config_data for ASCIIRenderer
                        config_data['sprite']['width'] = width
                        config_data['sprite']['height'] = height

                    colorized_output = renderer.render_sprite(config_data)
                    print(f"\n🎨 Colorized ASCII Output for {config_file.name}:")
                    print(colorized_output)
                except Exception as e:
                    LOG.debug(f"Could not create colorized output for {config_file.name}: {e}")

            except (FileNotFoundError, PermissionError, ValueError, KeyError) as e:
                LOG.warning(f"Error loading sprite config {config_file}: {e}")
    else:
        LOG.warning(f"Sprite config directory not found: {SPRITE_CONFIG_DIR}")

    LOG.info(f"Total AI training data loaded: {len(AI_TRAINING_DATA)} sprites")
    print(f"\n📊 Total AI training data loaded: {len(AI_TRAINING_DATA)} sprites")


class GGUnhandledMenuItemError(Exception):
    """Glitchy Games Unhandled Menu Item Error."""


class BitmapPixelSprite(BitmappySprite):
    """Bitmap Pixel Sprite."""

    log = LOG
    PIXEL_CACHE: ClassVar = {}

    def __init__(
        self: Self,
        x: int = 0,
        y: int = 0,
        width: int = 1,
        height: int = 1,
        name: str | None = None,
        pixel_number: int = 0,
        border_thickness: int = 1,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
        """Initialize the Bitmap Pixel Sprite."""
        super().__init__(x=x, y=y, width=width, height=height, name=name, groups=groups)

        self.pixel_number = pixel_number
        self.pixel_width = width
        self.pixel_height = height
        self.border_thickness = border_thickness
        self.color = (96, 96, 96)
        self.pixel_color = (0, 0, 0, 255)
        self.x = x
        self.y = y

        self.rect = pygame.draw.rect(
            self.image, self.color, (self.x, self.y, self.width, self.height), self.border_thickness
        )

    @property
    def pixel_color(self: Self) -> tuple[int, int, int, int]:
        """Get the pixel color.

        Args:
            None

        Returns:
            tuple[int, int, int, int]: The pixel color with alpha.

        Raises:
            None

        """
        return self._pixel_color

    @pixel_color.setter
    def pixel_color(self: Self, new_pixel_color: tuple[int, int, int] | tuple[int, int, int, int]) -> None:
        """Set the pixel color.

        Args:
            new_pixel_color (tuple): The new pixel color (RGB or RGBA).

        Returns:
            None

        Raises:
            None

        """
        # Convert RGB to RGBA if needed
        if len(new_pixel_color) == 3:
            self._pixel_color = (new_pixel_color[0], new_pixel_color[1], new_pixel_color[2], 255)
        else:
            self._pixel_color = new_pixel_color
        self.dirty = 1

    def update(self: Self) -> None:
        """Update the sprite.

        Args:
            None

        Returns:
            None

        Raises:
            None

        """
        cache_key = (self.pixel_color, self.border_thickness)
        cached_image = BitmapPixelSprite.PIXEL_CACHE.get(cache_key)

        if not cached_image:
            self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self.image.fill((0, 0, 0, 0))  # Start with transparent

            # Draw main pixel
            pygame.draw.rect(self.image, self.pixel_color, (0, 0, self.width, self.height))

            # Draw border if needed
            if self.border_thickness:
                pygame.draw.rect(
                    self.image, self.color, (0, 0, self.width, self.height), self.border_thickness
                )

            # Convert surface for better performance
            self.image = self.image.convert_alpha()
            BitmapPixelSprite.PIXEL_CACHE[cache_key] = self.image
        else:
            self.image = cached_image  # No need to copy since we converted the surface

        self.rect = self.image.get_rect(x=self.rect.x, y=self.rect.y)

    def on_pixel_update_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the pixel update event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None

        """
        if self.callbacks:
            callback = self.callbacks.get("on_pixel_update_event", None)

            if callback:
                callback(event=event, trigger=self)

    def on_left_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the left mouse button down event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None

        """
        self.dirty = 1
        self.on_pixel_update_event(event)


@dataclass
class AIRequest:
    """Data structure for AI requests."""

    prompt: str
    request_id: str
    messages: list[dict[str, str]]


@dataclass
class AIResponse:
    """Data structure for AI responses."""

    content: str | None
    error: str | None = None


def _setup_ai_worker_logging() -> logging.Logger:
    """Set up logging for AI worker process."""
    log = logging.getLogger("game.ai")
    log.setLevel(logging.INFO)

    if not log.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        log.addHandler(handler)

    log.info("AI worker process initializing...")
    log.debug(f"AI_MODEL: {AI_MODEL}")
    log.debug(f"AI_TIMEOUT: {AI_TIMEOUT}")
    return log


def _initialize_ai_client(log: logging.Logger):
    """Initialize AI client."""
    if ai is None:
        log.error("aisuite not available - AI features disabled")
        return None

    log.info("aisuite is available")
    log.debug(f"aisuite version: {getattr(ai, '__version__', 'unknown')}")

    log.info("Initializing AI client...")
    client = ai.Client()

    # Configure timeout for the underlying HTTP client
    try:
        # Access the underlying provider clients and set timeout
        if hasattr(client, "_providers"):
            for provider_name, provider in client._providers.items():
                if hasattr(provider, "client") and hasattr(provider.client, "timeout"):
                    provider.client.timeout = 300.0  # 5 minutes
                    log.debug(f"Set 5-minute timeout for {provider_name} provider")
                elif hasattr(provider, "client") and hasattr(provider.client, "_client"):
                    # For some providers, the timeout is on the underlying HTTP client
                    if hasattr(provider.client._client, "timeout"):
                        provider.client._client.timeout = 300.0
                        log.debug(f"Set 5-minute timeout for {provider_name} provider HTTP client")

        log.info("AI client initialized successfully with 5-minute timeout")
    except Exception as e:
        log.warning(f"Could not configure timeout: {e}")
        log.info("AI client initialized with default timeout")

    log.debug(f"Client type: {type(client)}")
    return client


def _get_model_capabilities(log: logging.Logger) -> dict:
    """Query the model's capabilities including max tokens."""
    try:
        client = _initialize_ai_client(log)

        # Check if AI client is available
        if client is None:
            log.warning("AI client not available, using default capabilities")
            return {"max_tokens": 4096}  # Default fallback

        # Try to get model info through a simple test request
        test_messages = [
            {
                "role": "user",
                "content": (
                    "What is your maximum token output limit? Please respond with just the number."
                ),
            }
        ]

        log.info("Querying model capabilities...")
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=test_messages,
            max_tokens=100,  # Small response for capability query
        )

        if hasattr(response, "choices") and response.choices:
            content = response.choices[0].message.content
            log.info(f"Model response about capabilities: {content}")

            # Try to extract max tokens from response
            try:
                max_tokens = int(content.strip())
                log.info(f"Detected max tokens: {max_tokens}")
                return {"max_tokens": max_tokens}
            except ValueError:
                log.warning(f"Could not parse max tokens from response: {content}")

        return {"max_tokens": None}

    except (ValueError, ConnectionError, TimeoutError):
        log.error("Failed to query model capabilities")
        return {"max_tokens": None}


def _process_ai_request(request: AIRequest, client, log: logging.Logger) -> AIResponse:
    """Process a single AI request."""
    # Check if AI client is available
    if client is None:
        log.warning("AI client not available, returning empty response")
        return AIResponse(content="AI features not available")

    log.info("Making API call to AI service...")
    start_time = time.time()

    try:
        response = client.chat.completions.create(
            model=AI_MODEL, messages=request.messages, max_tokens=AI_MAX_TOKENS
        )

        end_time = time.time()
        duration = end_time - start_time
        log.info(f"AI response received from API in {duration:.2f} seconds")

    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        log.error(f"AI request failed after {duration:.2f} seconds: {e}")
        raise

    return _extract_response_content(response, log)


def _select_relevant_training_examples(
    user_request: str, max_examples: int = AI_MAX_TRAINING_EXAMPLES
) -> list:
    """Select the most relevant training examples based on user request."""
    if len(AI_TRAINING_DATA) <= max_examples:
        return AI_TRAINING_DATA

    # Simple keyword matching for now - could be enhanced with semantic similarity
    user_lower = user_request.lower()
    relevant_examples = []

    # Score examples based on keyword matches
    scored_examples = []
    for example in AI_TRAINING_DATA:
        score = 0
        name = example.get("name", "").lower()
        sprite_type = example.get("sprite_type", "").lower()

        # Check for keyword matches
        if (
            any(keyword in user_lower for keyword in ["animated", "animation", "frame"])
            and sprite_type == "animated"
        ):
            score += 10
        if (
            any(keyword in user_lower for keyword in ["static", "single", "one"])
            and sprite_type == "static"
        ):
            score += 10

        # Check for name similarity
        if any(word in name for word in user_lower.split()):
            score += 5

        scored_examples.append((score, example))

    # Sort by score and take top examples
    scored_examples.sort(key=operator.itemgetter(0), reverse=True)
    relevant_examples = [example for _, example in scored_examples[:max_examples]]

    # Fill remaining slots with random examples if needed
    if len(relevant_examples) < max_examples:
        remaining = [ex for ex in AI_TRAINING_DATA if ex not in relevant_examples]
        relevant_examples.extend(remaining[: max_examples - len(relevant_examples)])

    return relevant_examples


def _normalize_toml_data(config_data: dict) -> dict:
    """Normalize TOML data by converting triple-quoted strings to proper format.

    Args:
        config_data: Raw TOML data loaded from file

    Returns:
        Normalized TOML data with proper string formatting

    """
    try:
        # Create a copy to avoid modifying the original
        normalized_data = config_data.copy()

        # Handle sprite pixels
        if "sprite" in normalized_data and "pixels" in normalized_data["sprite"]:
            pixels = normalized_data["sprite"]["pixels"]
            if isinstance(pixels, str):
                # Convert escaped newlines to actual newlines
                # Handle both \\n (double escaped) and \n (single escaped)
                pixels = pixels.replace("\\\\n", "\n").replace("\\n", "\n")
                normalized_data["sprite"]["pixels"] = pixels

        # Handle animation frame pixels
        if "animation" in normalized_data:
            for animation in normalized_data["animation"]:
                if isinstance(animation, dict) and "frame" in animation:
                    for frame in animation["frame"]:
                        if isinstance(frame, dict) and "pixels" in frame:
                            pixels = frame["pixels"]
                            if isinstance(pixels, str):
                                # Convert escaped newlines to actual newlines
                                # Handle both \\n (double escaped) and \n (single escaped)
                                pixels = pixels.replace("\\\\n", "\n").replace("\\n", "\n")
                                frame["pixels"] = pixels

        return normalized_data

    except Exception as e:
        LOG.warning(f"Error normalizing TOML data: {e}")
        return config_data  # Return original if normalization fails


def _extract_response_content(response, log: logging.Logger) -> AIResponse:
    """Extract content from AI response."""
    if not hasattr(response, "choices") or not response.choices:
        log.error("No choices in response or empty choices")
        return AIResponse(content=None, error="No choices in response")

    first_choice = response.choices[0]
    if not hasattr(first_choice, "message"):
        log.error("No 'message' attribute in choice")
        return AIResponse(content=None, error="No message in response choice")

    message = first_choice.message
    if not hasattr(message, "content"):
        log.error("No 'content' attribute in message")
        return AIResponse(content=None, error="No content in response message")

    content = message.content
    log.info(f"Response content length: {len(content) if content else 0}")
    return AIResponse(content=content)


def ai_worker(
    request_queue: multiprocessing.Queue[AIRequest],
    response_queue: multiprocessing.Queue[tuple[str, AIResponse]],
) -> None:
    """Worker process for handling AI requests.

    Args:
        request_queue: Queue to receive requests from
        response_queue: Queue to send responses to

    """
    log = _setup_ai_worker_logging()

    try:
        client = _initialize_ai_client(log)
        request_count = 0

        while True:
            try:
                request = request_queue.get()
                request_count += 1
                log.info(f"Processing AI request #{request_count}")

                if request is None:  # Shutdown signal
                    log.info("Received shutdown signal, closing AI worker")
                    break

                ai_response = _process_ai_request(request, client, log)
                response_data = (request.request_id, ai_response)
                response_queue.put(response_data)
                log.info("Response sent successfully")

            except (ValueError, KeyError, AttributeError, OSError) as e:
                log.error("Error processing AI request")
                if request:
                    response_queue.put((request.request_id, AIResponse(content=None, error=str(e))))
    except ImportError:
        log.error("Failed to import aisuite")
        raise
    except (OSError, ValueError, KeyError, AttributeError):
        log.error("Fatal error in AI worker process")
        raise


class ScrollArrowSprite(BitmappySprite):
    """Sprite for scroll arrows."""

    def __init__(self, x=0, y=0, width=20, height=20, groups=None, direction="up"):
        """Initialize the scroll arrow sprite."""
        super().__init__(x=x, y=y, width=width, height=height, groups=groups)
        self.direction = direction
        self.name = f"Scroll {direction} Arrow"

        # Create arrow surface
        self.image = pygame.Surface((width, height))
        self.rect = self.image.get_rect(x=x, y=y)

        # Draw the arrow
        self._draw_arrow()

        # Initially hidden
        self.visible = False
        self.dirty = 1

    def _draw_arrow(self):
        """Draw the arrow on the surface."""
        self.image.fill((255, 255, 255))  # White background

        if self.direction == "up":
            # Up arrow: triangle pointing up
            pygame.draw.polygon(self.image, (0, 0, 0), [(10, 5), (5, 15), (15, 15)])
        elif self.direction == "down":
            # Down arrow: triangle pointing down
            pygame.draw.polygon(self.image, (0, 0, 0), [(10, 15), (5, 5), (15, 5)])
        elif self.direction == "plus":
            # Plus sign for adding new frames
            pygame.draw.line(self.image, (0, 0, 0), (10, 5), (10, 15), 2)  # Vertical line
            pygame.draw.line(self.image, (0, 0, 0), (5, 10), (15, 10), 2)  # Horizontal line

    def set_direction(self, direction):
        """Change the arrow direction and redraw."""
        if self.direction != direction:
            self.direction = direction
            self._draw_arrow()
            self.dirty = 1


class FilmStripSprite(BitmappySprite):
    """Sprite wrapper for the film strip widget.

    CRITICAL ARCHITECTURE NOTE:
    This sprite is the bridge between the film strip widget and the pygame sprite system.
    It MUST be updated continuously (every frame) to ensure preview animations run smoothly.

    KEY RESPONSIBILITIES:
    1. Continuous Animation Updates:
       - Updates film_strip_widget.update_animations() every frame
       - Passes delta time from the scene for smooth animation timing
       - Ensures preview animations run independently of user interaction

    2. Dirty Flag Management:
       - Marks itself as dirty when animations are running
       - This triggers redraws in the sprite group system
       - Ensures visual updates when animation frames advance

    3. Rendering Coordination:
       - Calls force_redraw() when needed (dirty or animations running)
       - Manages the relationship between animation state and visual updates

    DEBUGGING NOTES:
    - If animations stop: Check that this sprite's update() is called every frame
    - If animations are choppy: Verify _last_dt contains reasonable values
    - If no visual updates: Check that dirty flag is being set when animations run
    - If wrong timing: Verify delta time is being passed from scene update loop
    """

    def __init__(self, film_strip_widget, x=0, y=0, width=800, height=100, groups=None):
        """Initialize the film strip sprite."""
        super().__init__(x=x, y=y, width=width, height=height, groups=groups)
        self.film_strip_widget = film_strip_widget
        self.name = "Film Strip"

        # Create initial surface with alpha support
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.rect = self.image.get_rect(x=x, y=y)

        # Force initial render
        self.dirty = 1

    def update(self):
        """Update the film strip sprite.

        CRITICAL: This method is called continuously by the scene update loop
        to ensure preview animations run smoothly. The key insight is that film
        strip sprites need to update every frame, not just when dirty, because
        they contain independent animation timing that must advance continuously.
        """
        # Check if this sprite has been killed - if so, don't update
        if not hasattr(self, "groups") or not self.groups() or len(self.groups()) == 0:
            LOG.debug(f"DEBUG: FilmStripSprite update skipped - not in groups: {hasattr(self, 'groups')}, groups: {self.groups() if hasattr(self, 'groups') else 'None'}")
            # Clear the widget reference to prevent any lingering updates
            if hasattr(self, "film_strip_widget"):
                self.film_strip_widget = None
            return

        # Debug: Track if this sprite is being updated
        if not hasattr(self, "_update_count"):
            self._update_count = 0
        self._update_count += 1

        # Debug: Print update count every 100 updates for initial strip
        if self._update_count % 100 == 0:
            pass  # Debug logging removed

        # Update animations first to advance frame timing
        # This is the core of the preview animation system - it advances the
        # animation frames based on delta time, allowing smooth preview playback
        if hasattr(self, "film_strip_widget") and self.film_strip_widget:
            # Get delta time from the scene or use a default
            # DEBUGGING: If animations are choppy, check that _last_dt is being set
            # by the scene update loop and contains reasonable values (0.016 = 60fps)
            dt = getattr(self, "_last_dt", 0.016)  # Default to ~60 FPS
            self.film_strip_widget.update_animations(dt)

        # Check if animations are running and force redraw
        # This determines whether we need continuous updates for preview animations
        animations_running = (
            hasattr(self, "film_strip_widget")
            and hasattr(self.film_strip_widget, "animated_sprite")
            and self.film_strip_widget.animated_sprite
            and len(self.film_strip_widget.animated_sprite._animations) > 0
        )

        # Always redraw if dirty or if animations are running
        # This ensures the film strip redraws both for user interactions (dirty)
        # and for continuous animation updates (animations_running)
        should_redraw = self.dirty or animations_running

        if should_redraw:
            self.force_redraw()
            # CRITICAL: Always mark as dirty when animations are running for continuous updates
            # This ensures the sprite group will redraw this sprite every frame when
            # animations are present, creating the smooth preview effect
            if animations_running:
                self.dirty = 1  # Keep dirty for continuous animation updates
            else:
                self.dirty = 0  # Reset dirty when no animations (normal sprite behavior)

    def force_redraw(self):
        """Force a redraw of the film strip."""
        # Clear the surface with copper brown to match film strip
        self.image.fill((100, 70, 55))  # Copper brown background

        # Render the film strip widget
        self.film_strip_widget.render(self.image)

    def kill(self):
        """Kill the sprite and clean up the widget reference."""
        # Clear the widget reference to prevent any lingering updates
        if hasattr(self, "film_strip_widget"):
            self.film_strip_widget = None
        # Call the parent kill method
        super().kill()

    def on_left_mouse_button_down_event(self, event):
        """Handle mouse clicks on the film strip."""
        LOG.debug(f"FilmStripSprite: Mouse click at {event.pos}, rect: {self.rect}")
        if self.rect.collidepoint(event.pos) and self.film_strip_widget and self.visible:
            LOG.debug("FilmStripSprite: Click is within bounds and sprite is visible, converting coordinates")
            # Convert screen coordinates to film strip coordinates
            film_x = event.pos[0] - self.rect.x
            film_y = event.pos[1] - self.rect.y

            # Check for shift-click using pygame's current key state
            is_shift_click = pygame.key.get_pressed()[pygame.K_LSHIFT] or pygame.key.get_pressed()[pygame.K_RSHIFT]

            # Handle click in the film strip widget
            LOG.debug(f"FilmStripSprite: Calling handle_click with coordinates ({film_x}, {film_y}), shift={is_shift_click}")
            clicked_frame = self.film_strip_widget.handle_click((film_x, film_y), is_shift_click=is_shift_click)
            LOG.debug(f"FilmStripSprite: Clicked frame: {clicked_frame}")

            if clicked_frame:
                animation, frame_idx = clicked_frame
                LOG.debug(f"FilmStripSprite: Loading frame {frame_idx} of animation {animation}")

                # Notify the canvas to change frame
                if hasattr(self, "parent_canvas") and self.parent_canvas:
                    self.parent_canvas.show_frame(animation, frame_idx)

                # Notify the parent scene about the selection change
                if hasattr(self, "parent_scene") and self.parent_scene:
                    self.parent_scene._on_film_strip_frame_selected(self.film_strip_widget, animation, frame_idx)
            else:
                LOG.debug("FilmStripSprite: No frame clicked, handle_click returned None")
        else:
            LOG.debug("FilmStripSprite: Click is outside bounds or no widget")

    def on_right_mouse_button_up_event(self, event):
        """Handle right mouse clicks on the film strip for onion skinning and color sampling."""
        LOG.info(f"FilmStripSprite: Right mouse UP at {event.pos}, rect: {self.rect}")
        if self.rect.collidepoint(event.pos) and self.film_strip_widget and self.visible:
            LOG.info("FilmStripSprite: Right click UP is within bounds and sprite is visible, converting coordinates")
            # Convert screen coordinates to film strip coordinates
            film_x = event.pos[0] - self.rect.x
            film_y = event.pos[1] - self.rect.y

            # Check for shift-right-click (screen sampling)
            is_shift_click = pygame.key.get_pressed()[pygame.K_LSHIFT] or pygame.key.get_pressed()[pygame.K_RSHIFT]

            # First check if we clicked on a frame for color sampling
            clicked_frame = self.film_strip_widget.get_frame_at_position((film_x, film_y))
            if clicked_frame:
                animation, frame_idx = clicked_frame
                LOG.info(f"FilmStripSprite: Right-clicked frame {animation}[{frame_idx}] for color sampling")

                if is_shift_click:
                    # Shift-right-click: sample screen directly (RGB only)
                    LOG.info("FilmStripSprite: Shift-right-click detected - sampling screen directly")
                    if hasattr(self, 'parent_scene') and self.parent_scene:
                        self.parent_scene._sample_color_from_screen(event.pos)
                else:
                    # Regular right-click: sample from sprite frame pixel data (RGBA)
                    self._sample_color_from_frame(animation, frame_idx, film_x, film_y)
                LOG.info("FilmStripSprite: Color sampling completed, returning early")
                return True  # Event was handled

            # Handle right-click in the film strip widget for onion skinning
            LOG.debug(f"FilmStripSprite: Calling handle_click with coordinates ({film_x}, {film_y}), right_click=True")
            clicked_frame = self.film_strip_widget.handle_click((film_x, film_y), is_right_click=True)
            LOG.debug(f"FilmStripSprite: Right-clicked frame: {clicked_frame}")
            return True  # Event was handled
        else:
            LOG.debug("FilmStripSprite: Right click UP is outside bounds or no widget")
            return False  # Event not handled

    def _sample_color_from_frame(self, animation: str, frame_idx: int, film_x: int, film_y: int) -> None:
        """Sample color from a sprite frame pixel data.

        Args:
            animation: Animation name
            frame_idx: Frame index
            film_x: X coordinate within the film strip
            film_y: Y coordinate within the film strip
        """
        try:
            # Get the frame from the animated sprite
            if not self.film_strip_widget.animated_sprite:
                LOG.debug("FilmStripSprite: No animated sprite available for color sampling")
                return

            frames = self.film_strip_widget.animated_sprite._animations.get(animation, [])
            if frame_idx >= len(frames):
                LOG.debug(f"FilmStripSprite: Frame index {frame_idx} out of range")
                return

            frame = frames[frame_idx]

            # Get the frame's pixel data directly
            if hasattr(frame, 'get_pixel_data'):
                pixel_data = frame.get_pixel_data()
            elif hasattr(frame, 'pixels'):
                pixel_data = frame.pixels
            else:
                LOG.debug("FilmStripSprite: Frame has no pixel data available")
                return

            if not pixel_data:
                LOG.debug("FilmStripSprite: Frame pixel data is empty")
                return

            # Get frame dimensions from the pixel data length
            # We need to determine the frame dimensions to calculate the pixel index
            if hasattr(frame, 'image') and frame.image:
                actual_width, actual_height = frame.image.get_size()
            else:
                # Fallback to canvas dimensions
                actual_width = self.film_strip_widget.parent_canvas.pixels_across if self.film_strip_widget.parent_canvas else 32
                actual_height = self.film_strip_widget.parent_canvas.pixels_tall if self.film_strip_widget.parent_canvas else 32

            # Find the frame layout to get the click position within the frame
            frame_layout = None
            for (anim_name, frame_idx_check), frame_rect in self.film_strip_widget.frame_layouts.items():
                if anim_name == animation and frame_idx_check == frame_idx:
                    frame_layout = frame_rect
                    break

            if not frame_layout:
                LOG.debug(f"FilmStripSprite: Could not find frame layout for {animation}[{frame_idx}]")
                return

            # Calculate relative position within the frame
            relative_x = film_x - frame_layout.x
            relative_y = film_y - frame_layout.y

            # Check if click is within frame bounds
            if not (0 <= relative_x < frame_layout.width and 0 <= relative_y < frame_layout.height):
                LOG.debug(f"FilmStripSprite: Click outside frame bounds")
                return

            # Calculate which pixel was clicked based on the frame's actual dimensions
            # Account for frame border (4px on each side)
            frame_content_width = frame_layout.width - 8
            frame_content_height = frame_layout.height - 8

            # Calculate pixel coordinates within the frame content area
            pixel_x = int((relative_x - 4) * actual_width / frame_content_width)
            pixel_y = int((relative_y - 4) * actual_height / frame_content_height)

            # Clamp to valid range
            pixel_x = max(0, min(pixel_x, actual_width - 1))
            pixel_y = max(0, min(pixel_y, actual_height - 1))

            # Get pixel index
            pixel_num = pixel_y * actual_width + pixel_x

            if pixel_num < len(pixel_data):
                color = pixel_data[pixel_num]

                # Handle both RGB and RGBA pixel formats
                if len(color) == 4:
                    red, green, blue, alpha = color
                else:
                    red, green, blue = color
                    alpha = 255  # Default to opaque for RGB pixels

                LOG.debug(f"FilmStripSprite: Sampled color from frame {animation}[{frame_idx}] pixel ({pixel_x}, {pixel_y}) - R:{red}, G:{green}, B:{blue}, A:{alpha}")

                # Update sliders in the parent scene
                if hasattr(self, 'parent_scene') and self.parent_scene:
                    # Create trigger events for each slider
                    trigger_r = pygame.event.Event(0, {"name": "R", "value": red})
                    self.parent_scene.on_slider_event(event=pygame.event.Event(0), trigger=trigger_r)

                    trigger_g = pygame.event.Event(0, {"name": "G", "value": green})
                    self.parent_scene.on_slider_event(event=pygame.event.Event(0), trigger=trigger_g)

                    trigger_b = pygame.event.Event(0, {"name": "B", "value": blue})
                    self.parent_scene.on_slider_event(event=pygame.event.Event(0), trigger=trigger_b)

                    trigger_a = pygame.event.Event(0, {"name": "A", "value": alpha})
                    self.parent_scene.on_slider_event(event=pygame.event.Event(0), trigger=trigger_a)

                    LOG.info(f"FilmStripSprite: Updated sliders with sampled color R:{red}, G:{green}, B:{blue}, A:{alpha}")
            else:
                LOG.debug(f"FilmStripSprite: Pixel index {pixel_num} out of range for pixel data length {len(pixel_data)}")

        except Exception as e:
            LOG.error(f"FilmStripSprite: Error sampling color from frame: {e}")
            LOG.exception("Full traceback:")

    def on_key_down_event(self, event):
        """Handle keyboard events for copy/paste functionality."""
        if not self.film_strip_widget:
            return

        # Check for Ctrl+C (copy)
        if event.key == pygame.K_c and (event.get('mod', 0) & pygame.KMOD_CTRL):
            LOG.debug("FilmStripSprite: Ctrl+C detected - copying current frame")
            success = self.film_strip_widget.copy_current_frame()
            if success:
                LOG.debug("FilmStripSprite: Frame copied successfully")
            else:
                LOG.debug("FilmStripSprite: Failed to copy frame")
            return True

        # Check for Ctrl+V (paste)
        if event.key == pygame.K_v and (event.get('mod', 0) & pygame.KMOD_CTRL):
            LOG.debug("FilmStripSprite: Ctrl+V detected - pasting to current frame")
            success = self.film_strip_widget.paste_to_current_frame()
            if success:
                LOG.debug("FilmStripSprite: Frame pasted successfully")
            else:
                LOG.debug("FilmStripSprite: Failed to paste frame")
            return True

        return False

    def set_parent_canvas(self, canvas):
        """Set the parent canvas for frame changes."""
        self.parent_canvas = canvas

    def on_drop_file_event(self, event):
        """Handle drop file event on film strip.

        Args:
            event: The pygame event containing the dropped file information.

        Returns:
            True if the drop was handled, False otherwise.
        """
        # Get current mouse position since drop events don't include position
        mouse_pos = pygame.mouse.get_pos()

        # Check if the drop is within the film strip bounds
        if not self.rect.collidepoint(mouse_pos):
            return False

        # Get the file path from the event
        file_path = event.file
        LOG.debug(f"FilmStripSprite: File dropped on film strip: {file_path}")

        # Check if it's an image file we can handle
        if not file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
            LOG.debug(f"FilmStripSprite: Unsupported file type: {file_path}")
            return False

        # Convert screen coordinates to film strip coordinates
        film_x = mouse_pos[0] - self.rect.x
        film_y = mouse_pos[1] - self.rect.y

        # Check if drop is on a specific frame
        clicked_frame = self.film_strip_widget.get_frame_at_position((film_x, film_y))

        if clicked_frame:
            # Drop on existing frame - replace its contents
            animation, frame_idx = clicked_frame
            LOG.debug(f"FilmStripSprite: Dropping on frame {animation}[{frame_idx}]")
            return self._replace_frame_with_image(file_path, animation, frame_idx)
        else:
            # Drop on film strip but not on a frame - insert new frame
            LOG.debug(f"FilmStripSprite: Dropping on film strip area, inserting new frame")
            return self._insert_image_as_new_frame(file_path, film_x, film_y)

    def on_mouse_motion_event(self, event):
        """Handle mouse motion events for drag hover effects.

        Args:
            event: The pygame mouse motion event.
        """
        # Check if we're currently dragging a file (this would need to be tracked by the scene)
        # For now, we'll implement basic hover detection
        if self.rect.collidepoint(event.pos):
            # Convert screen coordinates to film strip coordinates
            film_x = event.pos[0] - self.rect.x
            film_y = event.pos[1] - self.rect.y

            # Handle all hover effects (frames, previews, removal buttons)
            self.film_strip_widget.handle_hover((film_x, film_y))

            # Check if hovering over a specific frame
            hovered_frame = self.film_strip_widget.get_frame_at_position((film_x, film_y))

            if hovered_frame:
                # Hovering over a frame - show frame hover effect
                self._show_frame_hover_effect(hovered_frame)
            else:
                # Check if hovering over preview area
                hovered_preview = self.film_strip_widget.get_preview_at_position((film_x, film_y))
                if hovered_preview:
                    # Hovering over preview - show preview hover effect
                    self._show_preview_hover_effect(hovered_preview)
                else:
                    # Not hovering over preview - clear preview hover if it was set
                    if self.film_strip_widget.hovered_preview is not None:
                        self.film_strip_widget.hovered_preview = None
                        self.film_strip_widget.mark_dirty()
                        self.dirty = 1
                    # Hovering over film strip area - show strip hover effect
                    self._show_strip_hover_effect()

            # Mark as dirty if any hover state changed
            self.dirty = 1
        else:
            # Not hovering over film strip - clear hover effects
            self._clear_hover_effects()

    def _show_frame_hover_effect(self, frame_info):
        """Show visual feedback for hovering over a frame.

        Args:
            frame_info: Tuple of (animation, frame_idx) for the hovered frame.
        """
        animation, frame_idx = frame_info
        LOG.debug(f"FilmStripSprite: Hovering over frame {animation}[{frame_idx}]")

        # Set hover state in the film strip widget
        self.film_strip_widget.hovered_frame = frame_info
        # Keep strip hover active even when hovering over frame
        self.film_strip_widget.mark_dirty()

        # Mark this sprite as dirty to trigger redraw
        self.dirty = 1

    def _show_preview_hover_effect(self, animation_name: str):
        """Show visual feedback for hovering over a preview area.

        Args:
            animation_name: Name of the animation being previewed.
        """
        LOG.debug(f"FilmStripSprite: Hovering over preview {animation_name}")

        # Set hover state in the film strip widget
        self.film_strip_widget.hovered_preview = animation_name
        # Keep strip hover active even when hovering over preview
        self.film_strip_widget.mark_dirty()

        # Mark this sprite as dirty to trigger redraw
        self.dirty = 1

    def _show_strip_hover_effect(self):
        """Show visual feedback for hovering over the film strip area."""
        LOG.debug("FilmStripSprite: Hovering over film strip area")

        # Set hover state in the film strip widget
        self.film_strip_widget.hovered_frame = None
        self.film_strip_widget.is_hovering_strip = True
        self.film_strip_widget.mark_dirty()

        # Mark this sprite as dirty to trigger redraw
        self.dirty = 1

    def _clear_hover_effects(self):
        """Clear all hover effects."""

        # Clear hover state in the film strip widget
        self.film_strip_widget.hovered_frame = None
        self.film_strip_widget.hovered_preview = None
        self.film_strip_widget.is_hovering_strip = False
        self.film_strip_widget.hovered_removal_button = None
        self.film_strip_widget.mark_dirty()

        # Mark this sprite as dirty to trigger redraw
        self.dirty = 1

    def _convert_image_to_sprite_frame(self, file_path: str):
        """Convert an image file to a SpriteFrame.

        Args:
            file_path: Path to the image file to convert.

        Returns:
            SpriteFrame object or None if conversion failed.
        """
        try:
            # Load the image
            image = pygame.image.load(file_path)

            # Get current canvas size for resizing
            canvas_width, canvas_height = 32, 32  # Default fallback
            if hasattr(self, "parent_canvas") and self.parent_canvas:
                canvas_width = self.parent_canvas.pixels_across
                canvas_height = self.parent_canvas.pixels_tall
            elif hasattr(self, "parent_scene") and self.parent_scene and hasattr(self.parent_scene, "canvas"):
                canvas_width = self.parent_scene.canvas.pixels_across
                canvas_height = self.parent_scene.canvas.pixels_tall

            # Resize image to match canvas size
            if image.get_size() != (canvas_width, canvas_height):
                image = pygame.transform.scale(image, (canvas_width, canvas_height))

            # Convert to RGBA if needed, preserving transparency
            if image.get_flags() & pygame.SRCALPHA:
                # Image already has alpha - keep it
                pass
            else:
                # Convert RGB to RGBA by adding alpha channel
                rgba_image = pygame.Surface((canvas_width, canvas_height), pygame.SRCALPHA)
                rgba_image.blit(image, (0, 0))
                image = rgba_image

            # Get pixel data with alpha support
            if image.get_flags() & pygame.SRCALPHA:
                # Image has alpha channel - use array4d to preserve alpha
                pixel_array = pygame.surfarray.array4d(image)
                pixels = []
                for y in range(canvas_height):
                    for x in range(canvas_width):
                        r, g, b, a = pixel_array[x, y]
                        pixels.append((int(r), int(g), int(b), int(a)))
            else:
                # Image has no alpha channel - use array3d and add alpha
                pixel_array = pygame.surfarray.array3d(image)
                pixels = []
                for y in range(canvas_height):
                    for x in range(canvas_width):
                        r, g, b = pixel_array[x, y]
                        pixels.append((int(r), int(g), int(b), 255))  # Add full alpha

            # Create a new SpriteFrame with the surface
            from glitchygames.sprites import SpriteFrame
            frame = SpriteFrame(image, duration=0.1)  # 0.1 second duration
            frame.set_pixel_data(pixels)

            LOG.debug(f"FilmStripSprite: Successfully converted image to sprite frame")
            return frame

        except Exception as e:
            LOG.error(f"FilmStripSprite: Failed to convert image {file_path}: {e}")
            return None

    def _replace_frame_with_image(self, file_path: str, animation: str, frame_idx: int) -> bool:
        """Replace an existing frame with image content.

        Args:
            file_path: Path to the image file.
            animation: Animation name.
            frame_idx: Frame index to replace.

        Returns:
            True if successful, False otherwise.
        """
        LOG.debug(f"FilmStripSprite: Replacing frame {animation}[{frame_idx}] with image")

        # Convert image to sprite frame
        new_frame = self._convert_image_to_sprite_frame(file_path)
        if not new_frame:
            return False

        # Get the current frame and replace it
        if not self.film_strip_widget.animated_sprite:
            LOG.error("FilmStripSprite: No animated sprite available")
            return False

        frames = self.film_strip_widget.animated_sprite._animations.get(animation, [])
        if frame_idx >= len(frames):
            LOG.error(f"FilmStripSprite: Frame index {frame_idx} out of range")
            return False

        # Replace the frame
        frames[frame_idx] = new_frame

        # Mark as dirty for redraw
        self.film_strip_widget.mark_dirty()

        # Update canvas if this is the current frame
        if (hasattr(self, "parent_scene") and self.parent_scene and
            hasattr(self.parent_scene, "selected_animation") and
            hasattr(self.parent_scene, "selected_frame") and
            self.parent_scene.selected_animation == animation and
            self.parent_scene.selected_frame == frame_idx):

            if hasattr(self.parent_scene, "canvas") and self.parent_scene.canvas:
                self.parent_scene.canvas.show_frame(animation, frame_idx)

        LOG.debug(f"FilmStripSprite: Successfully replaced frame {animation}[{frame_idx}]")
        return True

    def _insert_image_as_new_frame(self, file_path: str, film_x: int, film_y: int) -> bool:
        """Insert image as a new frame in the film strip.

        Args:
            file_path: Path to the image file.
            film_x: X coordinate of drop position.
            film_y: Y coordinate of drop position.

        Returns:
            True if successful, False otherwise.
        """
        LOG.debug(f"FilmStripSprite: Inserting new frame from image")

        # Convert image to sprite frame
        new_frame = self._convert_image_to_sprite_frame(file_path)
        if not new_frame:
            return False

        # Determine which animation to add to
        current_animation = self.film_strip_widget.current_animation
        if not current_animation:
            LOG.error("FilmStripSprite: No current animation selected")
            return False

        # Determine insertion position based on drop location
        # For now, insert at the end of the animation
        # TODO: Could be enhanced to insert at specific position based on drop location
        insert_index = len(self.film_strip_widget.animated_sprite._animations[current_animation])

        # Insert the frame
        self.film_strip_widget.animated_sprite.add_frame(current_animation, new_frame, insert_index)

        # Mark as dirty for redraw
        self.film_strip_widget.mark_dirty()

        # Notify the parent scene about the frame insertion
        if hasattr(self, "parent_scene") and self.parent_scene:
            if hasattr(self.parent_scene, "_on_frame_inserted"):
                self.parent_scene._on_frame_inserted(current_animation, insert_index)

        # Select the newly created frame
        self.film_strip_widget.set_current_frame(current_animation, insert_index)

        LOG.debug(f"FilmStripSprite: Successfully inserted new frame at {current_animation}[{insert_index}]")
        return True


class AnimatedCanvasSprite(BitmappySprite):
    """Animated Canvas Sprite for editing animated sprites."""

    log = LOG

    def __init__(
        self,
        animated_sprite,
        name="Animated Canvas",
        x=0,
        y=0,
        pixels_across=32,
        pixels_tall=32,
        pixel_width=16,
        pixel_height=16,
        groups=None,
    ):
        """Initialize the Animated Canvas Sprite."""
        # Initialize dimensions and get canvas size
        width, height = self._initialize_dimensions(
            pixels_across, pixels_tall, pixel_width, pixel_height
        )

        # Initialize parent class first to create rect
        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            groups=groups,
        )

        # Override pixels_across and pixels_tall with correct pixel dimensions
        # (BitmappySprite.__init__ sets them to screen dimensions)
        self.pixels_across = pixels_across
        self.pixels_tall = pixels_tall

        # Initialize sprite data and frame management
        self._initialize_sprite_data(animated_sprite)

        # Initialize pixel arrays and color settings
        self._initialize_pixel_arrays()

        # Initialize panning system
        self._initialize_simple_panning()

        # Initialize canvas surface and UI components
        self._initialize_canvas_surface(x, y, width, height, groups)

        # Initialize backward compatibility properties for tests
        self.film_strip = None
        self.film_strip_sprite = None

        # Initialize hover tracking for pixel hover effects
        self.hovered_pixel = None

        # Initialize hover tracking for canvas border effect
        self.is_hovered = False

    def _initialize_dimensions(
        self, pixels_across: int, pixels_tall: int, pixel_width: int, pixel_height: int
    ) -> tuple[int, int]:
        """Initialize canvas dimensions and pixel sizing.

        Args:
            pixels_across: Number of pixels across the canvas
            pixels_tall: Number of pixels tall the canvas
            pixel_width: Width of each pixel in screen coordinates
            pixel_height: Height of each pixel in screen coordinates

        Returns:
            Tuple of (width, height) for the canvas surface

        """
        self.pixels_across = pixels_across
        self.pixels_tall = pixels_tall
        self.pixel_width = pixel_width
        self.pixel_height = pixel_height
        width = self.pixels_across * self.pixel_width
        height = self.pixels_tall * self.pixel_height
        return width, height

    def _initialize_sprite_data(self, animated_sprite) -> None:
        """Initialize animated sprite and frame data.

        Args:
            animated_sprite: The animated sprite to associate with this canvas

        """
        self.animated_sprite = animated_sprite
        # Use the sprite's current animation if set and not empty, otherwise start empty
        if hasattr(animated_sprite, "current_animation") and animated_sprite.current_animation and animated_sprite.current_animation != "":
            self.current_animation = animated_sprite.current_animation
        else:
            self.current_animation = ""  # Start with empty animation
        # Sync the canvas frame with the animated sprite's current frame
        self.current_frame = animated_sprite.current_frame
        self.log.debug(
            f"Canvas initialized - animated_sprite.current_frame="
            f"{animated_sprite.current_frame}, canvas.current_frame={self.current_frame}"
        )

        # Initialize manual frame selection flag to allow automatic animation updates
        self._manual_frame_selected = False

    def _initialize_pixel_arrays(self) -> None:
        """Initialize pixel arrays and color settings."""
        # Initialize pixels with magenta as the transparent/background color (RGBA)
        self.pixels = [(255, 0, 255, 255) for _ in range(self.pixels_across * self.pixels_tall)]
        self.dirty_pixels = [True] * len(self.pixels)
        self.background_color = (128, 128, 128)
        self.active_color = (0, 0, 0, 255)
        # Set border thickness using the internal method
        self._update_border_thickness()

    def _update_border_thickness(self) -> None:
        """Update border thickness based on pixel size.

        For large sprites where pixel size becomes very small, use no border
        to prevent grid from consuming all space. This happens when the 320x320
        constraint kicks in, making pixel size 2x2 or smaller.

        For very large sprites (128x128), also disable borders to prevent visual clutter.
        """
        # Disable borders for very small pixels (2x2 or smaller) or very large sprites (128x128)
        should_disable_borders = (
            (self.pixel_width <= 2 and self.pixel_height <= 2) or  # Very small pixels
            (self.pixels_across >= 128 or self.pixels_tall >= 128)  # Very large sprites
        )

        old_border_thickness = getattr(self, "border_thickness", 1)
        self.border_thickness = 0 if should_disable_borders else 1

        # Clear pixel cache if border thickness changed
        if old_border_thickness != self.border_thickness:
            BitmapPixelSprite.PIXEL_CACHE.clear()
            self.log.info(f"Cleared pixel cache due to border thickness change ({old_border_thickness} -> {self.border_thickness})")

        self.log.info(f"Border thickness set to {self.border_thickness} (pixel size: {self.pixel_width}x{self.pixel_height}, sprite size: {self.pixels_across}x{self.pixels_tall})")

    def _pan_frame_data(self) -> None:
        """Pan the frame data directly by shifting pixels within the frame."""
        if not hasattr(self, 'animated_sprite') or not self.animated_sprite:
            return

        current_animation = self.current_animation
        current_frame = self.current_frame

        if current_animation in self.animated_sprite.frames and current_frame < len(self.animated_sprite.frames[current_animation]):
            frame = self.animated_sprite._animations[current_animation][current_frame]
            if hasattr(frame, "get_pixel_data") and hasattr(frame, "set_pixel_data"):
                # Get current frame pixels
                frame_pixels = frame.get_pixel_data()

                # Create a new pixel array with panned data
                panned_pixels = []

                for y in range(self.pixels_tall):
                    for x in range(self.pixels_across):
                        # Calculate source coordinates (where to read from)
                        source_x = x - self.pan_offset_x
                        source_y = y - self.pan_offset_y

                        # Check if source is within bounds of the frame data
                        frame_width = len(frame_pixels) // self.pixels_tall if self.pixels_tall > 0 else 0
                        frame_height = self.pixels_tall

                        if (0 <= source_x < frame_width and
                            0 <= source_y < frame_height):
                            source_index = source_y * frame_width + source_x
                            if source_index < len(frame_pixels):
                                panned_pixels.append(frame_pixels[source_index])
                            else:
                                panned_pixels.append((255, 0, 255))  # Transparent
                        else:
                            # Outside bounds - use transparent
                            panned_pixels.append((255, 0, 255))

                # Update the frame with panned pixels
                frame.set_pixel_data(panned_pixels)

                # Update canvas pixels to match
                self.pixels = panned_pixels.copy()
                self.dirty_pixels = [True] * len(self.pixels)

                # Clear surface cache
                if hasattr(self.animated_sprite, "_surface_cache"):
                    cache_key = f"{current_animation}_{current_frame}"
                    if cache_key in self.animated_sprite._surface_cache:
                        del self.animated_sprite._surface_cache[cache_key]

                self.log.debug(f"Frame data panned: offset=({self.pan_offset_x}, {self.pan_offset_y})")

    def _initialize_simple_panning(self) -> None:
        """Initialize the simple panning system for the canvas."""
        # Frame-specific panning state - each frame has its own panning
        self._frame_panning = {}  # {frame_key: {'pan_x': int, 'pan_y': int, 'original_pixels': list, 'active': bool}}

        self.log.debug("Simple panning system initialized with frame-specific state")

    def _get_current_frame_key(self) -> str:
        """Get a unique key for the current frame."""
        return f"{self.current_animation}_{self.current_frame}"

    def _store_original_frame_data_for_frame(self, frame_key: str) -> None:
        """Store the original frame data for a specific frame."""
        if hasattr(self, 'pixels') and self.pixels:
            self._frame_panning[frame_key]['original_pixels'] = list(self.pixels)
            self.log.debug(f"Stored original frame data for {frame_key}")

    def _apply_panning_view_for_frame(self, frame_key: str) -> None:
        """Apply panning transformation for a specific frame."""
        frame_state = self._frame_panning[frame_key]
        if frame_state['original_pixels'] is None:
            return

        # Create panned view by shifting pixels
        panned_pixels = []

        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                # Calculate source coordinates (where to read from in original)
                source_x = x - frame_state['pan_x']
                source_y = y - frame_state['pan_y']

                # Check if source is within bounds
                if (0 <= source_x < self.pixels_across and
                     0 <= source_y < self.pixels_tall):
                    source_index = source_y * self.pixels_across + source_x
                    if source_index < len(frame_state['original_pixels']):
                        panned_pixels.append(frame_state['original_pixels'][source_index])
                    else:
                        panned_pixels.append((255, 0, 255))  # Transparent
                else:
                    panned_pixels.append((255, 0, 255))  # Transparent

        # Update canvas pixels with panned view
        self.pixels = panned_pixels
        self.dirty_pixels = [True] * len(self.pixels)

        self.log.debug(f"Applied panning view for {frame_key}: offset=({frame_state['pan_x']}, {frame_state['pan_y']})")

    def reset_panning(self) -> None:
        """Reset panning for the current frame."""
        frame_key = self._get_current_frame_key()

        # Clear panning state for current frame
        if frame_key in self._frame_panning:
            self._frame_panning[frame_key] = {
                'pan_x': 0,
                'pan_y': 0,
                'original_pixels': None,
                'active': False
            }

        # Reload the original frame data
        if hasattr(self, 'animated_sprite') and self.animated_sprite:
            current_animation = self.current_animation
            current_frame = self.current_frame

            if current_animation in self.animated_sprite.frames and current_frame < len(self.animated_sprite.frames[current_animation]):
                frame = self.animated_sprite._animations[current_animation][current_frame]
                if hasattr(frame, "get_pixel_data"):
                    self.pixels = frame.get_pixel_data().copy()
                    self.dirty_pixels = [True] * len(self.pixels)
                    self.dirty = 1

        self.log.debug(f"Panning reset for frame {frame_key}")

    def is_panning_active(self) -> bool:
        """Check if panning is active for the current frame."""
        frame_key = self._get_current_frame_key()
        if frame_key in self._frame_panning:
            return self._frame_panning[frame_key]['active']
        return False

    def _initialize_canvas_surface(self, x: int, y: int, width: int, height: int, groups) -> None:
        """Initialize canvas surface and interface components.

        Args:
            x: X position of the canvas
            y: Y position of the canvas
            width: Width of the canvas surface
            height: Height of the canvas surface
            groups: Sprite groups to add components to

        """
        # Create initial surface
        self.image = pygame.Surface((self.width, self.height))
        self.rect = self.image.get_rect(x=x, y=y)

        # Initialize interface components for animated sprites
        self.canvas_interface = AnimatedCanvasInterface(self)
        # Sync the canvas interface with the canvas's current frame
        self.canvas_interface.set_current_frame(self.current_animation, self.current_frame)
        self.sprite_serializer = AnimatedSpriteSerializer()
        self.canvas_renderer = AnimatedCanvasRenderer(self)

        # Create multiple independent film strips - one for each animation
        film_strip_x = self.rect.right + 4  # 4 pixels to the right of canvas edge
        film_strip_y = self.rect.y  # Start at same vertical position as canvas

        # Calculate required width for film strip - extend to end of screen
        screen_width = pygame.display.get_surface().get_width()
        available_width = screen_width - film_strip_x  # Extend to end of screen
        film_strip_width = max(300, available_width)

        # Multiple film strips disabled - only showing first animation

        # Film strips will be created in the main scene after canvas setup

        # Film strip sprites are added to groups in _create_multiple_film_strips

        # Get screen dimensions from pygame
        screen_info = pygame.display.Info()
        screen_width = screen_info.current_w

        # Calculate mini map size using the same logic as MiniView
        pixel_width, _ = MiniView.pixels_per_pixel(self.pixels_across, self.pixels_tall)
        mini_map_width = self.pixels_across * pixel_width

        # Position mini map flush to the right edge and top
        mini_map_x = screen_width - mini_map_width  # Flush to right edge
        mini_map_y = 24  # Flush to top (below menu bar)

        # Ensure mini map doesn't go off screen
        if mini_map_x < 0:
            mini_map_x = 20  # Fallback to left side if too wide

        # Get current frame pixels for the mini view
        current_frame_pixels = self._get_current_frame_pixels()

        # Create miniview - position in top right corner
        # self.mini_view = MiniView(
        #     pixels=current_frame_pixels,
        #     x=mini_map_x,
        #     y=mini_map_y,
        #     width=self.pixels_across,
        #     height=self.pixels_tall,
        #     groups=groups,
        # )
        self.mini_view = None

        # Add MiniView to the sprite groups explicitly
        if groups and self.mini_view is not None:
            if isinstance(groups, (list, tuple)):
                for group in groups:
                    group.add(self.mini_view)
            else:
                groups.add(self.mini_view)

        # Show the first frame
        self.show_frame(self.current_animation, self.current_frame)

        # Force initial draw
        self.dirty = 1
        self.force_redraw()

    def _get_current_frame_pixels(self) -> list[tuple[int, int, int]]:
        """Get pixel data from the current frame of the animated sprite."""
        if hasattr(self, "animated_sprite") and self.animated_sprite:
            # Check if this is a static sprite (no frames)
            if (
                not hasattr(self.animated_sprite, "_animations")
                or not self.animated_sprite._animations
            ):
                # Static sprite - get pixels directly
                if hasattr(self.animated_sprite, "get_pixel_data"):
                    pixels = self.animated_sprite.get_pixel_data()
                    self.log.debug(
                        f"Got pixels from animated_sprite.get_pixel_data(): {len(pixels)} pixels, "
                        f"first few: {pixels[:5]}"
                    )
                    return pixels
                if hasattr(self.animated_sprite, "pixels"):
                    pixels = self.animated_sprite.pixels.copy()
                    self.log.debug(
                        f"Got pixels from animated_sprite.pixels: {len(pixels)} pixels, "
                        f"first few: {pixels[:5]}"
                    )
                    return pixels

            # Animated sprite with frames
            current_animation = self.current_animation
            current_frame = self.current_frame
            self.log.debug(
                f"Getting frame pixels for animation '{current_animation}', frame {current_frame}"
            )

            if current_animation in self.animated_sprite._animations and current_frame < len(
                self.animated_sprite._animations[current_animation]
            ):
                frame = self.animated_sprite._animations[current_animation][current_frame]
                if hasattr(frame, "get_pixel_data"):
                    pixels = frame.get_pixel_data()
                    self.log.debug(
                        f"Got pixels from frame.get_pixel_data(): {len(pixels)} pixels, "
                        f"first few: {pixels[:5]}"
                    )
                    return pixels
                self.log.warning("Frame has no get_pixel_data method")
            else:
                self.log.warning(
                    f"Animation '{current_animation}' or frame {current_frame} not found"
                )

        # Fallback to static pixels
        pixels = self.pixels.copy()
        self.log.debug(
            f"Using fallback canvas pixels: {len(pixels)} pixels, first few: {pixels[:5]}"
        )
        return pixels

    def _update_canvas_from_current_frame(self) -> None:
        """Update the canvas pixels with the current frame data."""
        if hasattr(self, "animated_sprite") and self.animated_sprite:
            # Use the canvas's current animation and frame (not the animated sprite's)
            current_animation = self.current_animation
            current_frame = self.current_frame
            if current_animation in self.animated_sprite._animations and current_frame < len(
                self.animated_sprite._animations[current_animation]
            ):
                frame = self.animated_sprite._animations[current_animation][current_frame]
                if hasattr(frame, "get_pixel_data"):
                    self.pixels = frame.get_pixel_data()
                    self.dirty_pixels = [True] * len(self.pixels)
                    self.log.debug(f"Updated canvas pixels from frame {current_frame}")

    def _update_mini_view_from_current_frame(self) -> None:
        """Update the mini view with pixel data from the current frame."""
        if hasattr(self, "mini_view") and self.mini_view is not None:
            current_frame_pixels = self._get_current_frame_pixels()
            self.log.debug(
                f"Updating mini view with {len(current_frame_pixels)} pixels, "
                f"first few: {current_frame_pixels[:5]}"
            )
            if hasattr(self, "mini_view") and self.mini_view is not None:
                self.log.debug(
                    f"Mini view dimensions: {self.mini_view.pixels_across}x{self.mini_view.pixels_tall}"
                )
                self.log.debug(
                    f"Expected pixels: {self.mini_view.pixels_across * self.mini_view.pixels_tall}"
                )

                if (
                    len(current_frame_pixels)
                    == self.mini_view.pixels_across * self.mini_view.pixels_tall
                ):
                    self.mini_view.pixels = current_frame_pixels
                    self.mini_view.dirty_pixels = [True] * len(current_frame_pixels)
                    self.mini_view.dirty = 1
                    self.mini_view.force_redraw()
                    self.log.debug("Mini view updated successfully with frame pixels")
                else:
                    self.log.debug(
                        f"Frame pixels don't match mini view dimensions: "
                        f"{len(current_frame_pixels)} vs "
                        f"{self.mini_view.pixels_across * self.mini_view.pixels_tall}"
                    )
                # Don't update if dimensions don't match

    def set_frame(self, frame_index: int) -> None:
        """Set the current frame index for the current animation."""
        if hasattr(self, "animated_sprite") and self.animated_sprite:
            frames = self.animated_sprite._animations
            if self.current_animation in frames and 0 <= frame_index < len(
                frames[self.current_animation]
            ):
                # Store the current playing state
                was_playing = self.animated_sprite.is_playing

                # Pause the animation when manually selecting frames
                self.animated_sprite.pause()

                self.current_frame = frame_index
                self.animated_sprite.set_frame(frame_index)

                # Mark that user manually selected a frame
                self._manual_frame_selected = True

                # Update the canvas interface
                self.canvas_interface.set_current_frame(self.current_animation, frame_index)

                # Update the undo/redo manager with the current frame for frame-specific operations
                if hasattr(self, "parent_scene") and self.parent_scene and hasattr(self.parent_scene, "undo_redo_manager"):
                    self.parent_scene.undo_redo_manager.set_current_frame(self.current_animation, frame_index)

                # Update mini view and mark as dirty
                if hasattr(self, "mini_view"):
                    self._update_mini_view_from_current_frame()

                # Only restart animation if it was playing before
                if was_playing:
                    self.animated_sprite.play()
                    self._manual_frame_selected = False
                else:
                    # Keep it paused if it was already paused
                    self.log.debug(
                        f"Animation was paused, keeping it paused at frame {frame_index}"
                    )

                self.dirty = 1
                self.log.debug(
                    f"Set frame to {frame_index} for animation "
                    f"'{self.current_animation}' (was_playing: {was_playing})"
                )

    def show_frame(self, animation: str, frame: int) -> None:
        """Show a specific frame of the animated sprite."""
        self.log.debug(f"show_frame called: animation={animation}, frame={frame}")
        frames = self.animated_sprite._animations
        if animation in frames and 0 <= frame < len(frames[animation]):
            self.current_animation = animation
            self.current_frame = frame
            self.log.debug(f"Canvas updated: current_animation={self.current_animation}, current_frame={self.current_frame}")

            # Update the animated sprite to the new animation and frame
            if animation != self.animated_sprite.current_animation:
                self.animated_sprite.set_animation(animation)
            self.animated_sprite.set_frame(frame)

            # Update the canvas interface
            self.canvas_interface.set_current_frame(animation, frame)

            # Update the undo/redo manager with the current frame for frame-specific operations
            if hasattr(self, "parent_scene") and self.parent_scene and hasattr(self.parent_scene, "undo_redo_manager"):
                # Only track frame selection if we're not in the middle of an undo/redo operation
                # or creating a frame (which has its own undo tracking)
                # Also don't track frame selection if we're in the middle of film strip operations
                if (not getattr(self.parent_scene, "_applying_undo_redo", False) and
                    not getattr(self.parent_scene, "_creating_frame", False) and
                    not getattr(self.parent_scene, "_creating_animation", False)):
                    # Track frame selection as a film strip operation instead of global
                    self.parent_scene.film_strip_operation_tracker.add_frame_selection(animation, frame)

            # Force the canvas to redraw with the new frame
            self.force_redraw()

            # Notify the parent scene about the frame change
            if hasattr(self, "parent_scene") and self.parent_scene:
                self.log.debug(f"Notifying parent scene about frame change: {animation}[{frame}]")
                self.parent_scene._update_film_strips_for_frame(animation, frame)
            else:
                self.log.debug("No parent scene found to notify about frame change")

            # Get the frame data
            frame_obj = frames[animation][frame]
            if hasattr(frame_obj, "get_pixel_data"):
                self.pixels = frame_obj.get_pixel_data()
            else:
                # Fallback to frame pixels if available
                self.pixels = getattr(
                    frame_obj, "pixels", [(255, 0, 255)] * (self.pixels_across * self.pixels_tall)
                )

            # Mark all pixels as dirty
            self.dirty_pixels = [True] * len(self.pixels)
            self.dirty = 1

            # Update mini view
            if hasattr(self, "mini_view") and self.mini_view is not None:
                self.mini_view.pixels = self.pixels.copy()
                self.mini_view.dirty_pixels = [True] * len(self.pixels)
                self.mini_view.dirty = 1

            # Notify parent scene to update film strips
            if hasattr(self, "parent_scene") and self.parent_scene:
                self.parent_scene._update_film_strips_for_frame(animation, frame)

            # Note: Live preview functionality is now integrated into the film strip

    def next_frame(self) -> None:
        """Move to the next frame in the current animation."""
        frames = self.animated_sprite._animations
        if self.current_animation in frames:
            frame_list = frames[self.current_animation]
            self.current_frame = (self.current_frame + 1) % len(frame_list)
            self.show_frame(self.current_animation, self.current_frame)

            # Notify the parent scene about the frame change
            if hasattr(self, "parent_scene") and self.parent_scene:
                self.log.debug(f"Notifying parent scene about frame change: {self.current_animation}[{self.current_frame}]")
                self.parent_scene._switch_to_film_strip(self.current_animation, self.current_frame)

    def previous_frame(self) -> None:
        """Move to the previous frame in the current animation."""
        frames = self.animated_sprite._animations
        if self.current_animation in frames:
            frame_list = frames[self.current_animation]
            self.current_frame = (self.current_frame - 1) % len(frame_list)
            self.show_frame(self.current_animation, self.current_frame)

            # Notify the parent scene about the frame change
            if hasattr(self, "parent_scene") and self.parent_scene:
                self.log.debug(f"Notifying parent scene about frame change: {self.current_animation}[{self.current_frame}]")
                self.parent_scene._switch_to_film_strip(self.current_animation, self.current_frame)

    def next_animation(self) -> None:
        """Move to the next animation."""
        self.log.debug(f"next_animation called, current_animation={self.current_animation}")
        frames = self.animated_sprite._animations
        animations = list(frames.keys())
        self.log.debug(f"Available animations: {animations}")
        if animations:
            current_index = animations.index(self.current_animation)
            next_index = (current_index + 1) % len(animations)
            next_animation = animations[next_index]

            # Preserve the current frame number when switching animations
            preserved_frame = self.current_frame
            # Ensure the frame number is within bounds for the new animation
            if next_animation in frames and len(frames[next_animation]) > 0:
                max_frame = len(frames[next_animation]) - 1
                preserved_frame = min(preserved_frame, max_frame)
            else:
                preserved_frame = 0
            self.log.debug(f"Moving from animation {self.current_animation} (index {current_index}) to {next_animation} (index {next_index}), preserving frame {preserved_frame}")
            self.show_frame(next_animation, preserved_frame)
            self.log.debug(f"After show_frame: current_animation={self.current_animation}, current_frame={self.current_frame}")

            # Notify the parent scene to switch film strips
            if hasattr(self, "parent_scene") and self.parent_scene:
                self.log.debug(f"Notifying parent scene to switch to film strip {next_animation}")
                self.parent_scene._switch_to_film_strip(next_animation, preserved_frame)

    def previous_animation(self) -> None:
        """Move to the previous animation."""
        self.log.debug(f"previous_animation called, current_animation={self.current_animation}")
        frames = self.animated_sprite._animations
        animations = list(frames.keys())
        self.log.debug(f"Available animations: {animations}")
        if animations:
            current_index = animations.index(self.current_animation)
            prev_index = (current_index - 1) % len(animations)
            prev_animation = animations[prev_index]

            # Preserve the current frame number when switching animations
            preserved_frame = self.current_frame
            # Ensure the frame number is within bounds for the new animation
            if prev_animation in frames and len(frames[prev_animation]) > 0:
                max_frame = len(frames[prev_animation]) - 1
                preserved_frame = min(preserved_frame, max_frame)
            else:
                preserved_frame = 0
            self.log.debug(f"Moving from animation {self.current_animation} (index {current_index}) to {prev_animation} (index {prev_index}), preserving frame {preserved_frame}")
            self.show_frame(prev_animation, preserved_frame)
            self.log.debug(f"After show_frame: current_animation={self.current_animation}, current_frame={self.current_frame}")

            # Notify the parent scene to switch film strips
            if hasattr(self, "parent_scene") and self.parent_scene:
                self.log.debug(f"Notifying parent scene to switch to film strip {prev_animation}")
                self.parent_scene._switch_to_film_strip(prev_animation, preserved_frame)

    def handle_keyboard_event(self, key: int) -> None:
        """Handle keyboard navigation events."""
        self.log.debug(f"Keyboard event received: key={key}")

        if key == pygame.K_LEFT:
            self.log.debug("LEFT arrow pressed")
            self.previous_frame()
        elif key == pygame.K_RIGHT:
            self.log.debug("RIGHT arrow pressed")
            self.next_frame()
        elif key == pygame.K_UP:
            self.log.debug("UP arrow pressed")
            self.previous_animation()
        elif key == pygame.K_DOWN:
            self.log.debug("DOWN arrow pressed")
            self.next_animation()
        elif pygame.K_0 <= key <= pygame.K_9:
            # Handle 0-9 keys for frame selection
            frame_index = key - pygame.K_0
            self.log.debug(f"Number key {frame_index} pressed")
            self.set_frame(frame_index)
        elif key == pygame.K_SPACE:
            # Toggle animation play/pause
            self.log.debug("SPACE key pressed")
            if hasattr(self, "animated_sprite") and self.animated_sprite:
                current_state = self.animated_sprite.is_playing
                self.log.debug(f"Current animation state: is_playing={current_state}")
                if self.animated_sprite.is_playing:
                    self.animated_sprite.pause()
                    self.log.debug("Animation paused")
                else:
                    # Restart animation from current frame
                    self.animated_sprite.play()
                    self.log.debug("Animation restarted")
                self.log.debug(f"New animation state: is_playing={self.animated_sprite.is_playing}")

                # Note: Live preview functionality is now integrated into the film strip
        else:
            self.log.debug(f"Unhandled key: {key}")

    def copy_current_frame(self) -> None:
        """Copy the current frame to clipboard."""
        # Get the current frame data
        frames = self.animated_sprite._animations
        if self.current_animation in frames and self.current_frame < len(
            frames[self.current_animation]
        ):
            frame = frames[self.current_animation][self.current_frame]
            # Store the pixel data in a simple clipboard attribute
            self._clipboard = frame.get_pixel_data().copy()

    def paste_to_current_frame(self) -> None:
        """Paste clipboard content to current frame."""
        if hasattr(self, "_clipboard") and self._clipboard:
            # Get the current frame
            frames = self.animated_sprite._animations
            if self.current_animation in frames and self.current_frame < len(
                frames[self.current_animation]
            ):
                frame = frames[self.current_animation][self.current_frame]
                # Set the pixel data
                frame.set_pixel_data(self._clipboard)
                # Update the canvas pixels
                self.pixels = self._clipboard.copy()
                # Mark as dirty
                self.dirty_pixels = [True] * len(self.pixels)
                self.dirty = 1

    def save_animated_sprite(self, filename: str) -> None:
        """Save the animated sprite to a file."""
        if self.is_panning_active():
            # Save viewport only when panning is active
            self.log.info("Saving viewport only due to active panning")
            self._save_viewport_sprite(filename)
        else:
            # Save full sprite when not panning
            self.sprite_serializer.save(self.animated_sprite, filename, DEFAULT_FILE_FORMAT)

    @classmethod
    def from_file(
        cls,
        filename: str,
        x: int = 0,
        y: int = 0,
        pixels_across: int = 32,
        pixels_tall: int = 32,
        pixel_width: int = 16,
        pixel_height: int = 16,
        groups=None,
    ):
        """Create an AnimatedCanvasSprite from a file."""
        # Load the animated sprite
        animated_sprite = SpriteFactory.load_sprite(filename=filename)

        if not hasattr(animated_sprite, "frames"):
            raise ValueError(f"File {filename} does not contain animated sprite data")

        return cls(
            animated_sprite=animated_sprite,
            name="Animated Canvas",
            x=x,
            y=y,
            pixels_across=pixels_across,
            pixels_tall=pixels_tall,
            pixel_width=pixel_width,
            pixel_height=pixel_height,
            groups=groups,
        )

    def update(self):
        """Update the canvas display."""
        # Check if mouse is outside canvas
        mouse_pos = pygame.mouse.get_pos()

        # Get window size
        screen_info = pygame.display.Info()
        screen_rect = pygame.Rect(0, 0, screen_info.current_w, screen_info.current_h)

        # If mouse is outside window or canvas, clear cursor
        if (
            not screen_rect.collidepoint(mouse_pos) or not self.rect.collidepoint(mouse_pos)
        ) and hasattr(self, "mini_view") and self.mini_view is not None:
            self.log.info("Mouse outside canvas/window, clearing miniview cursor")
            self.mini_view.clear_cursor()

        # Animation timing is handled by the scene's update_animation method

        if self.dirty:
            self.force_redraw()
            self.dirty = 0

    def pan_canvas(self, delta_x: int, delta_y: int) -> None:
        """Pan the canvas by the given delta values.

        Args:
            delta_x: Horizontal panning delta (-1, 0, or 1)
            delta_y: Vertical panning delta (-1, 0, or 1)
        """
        # Calculate new pan offset
        new_pan_x = self.pan_offset_x + delta_x
        new_pan_y = self.pan_offset_y + delta_y

        # Check if panning is within bounds
        if self._can_pan(new_pan_x, new_pan_y):
            self.pan_offset_x = new_pan_x
            self.pan_offset_y = new_pan_y
            self._panning_active = True

            # Update the frame data directly with panned pixels
            self._pan_frame_data()

            # Mark canvas as dirty for redraw
            self.dirty = 1

            self.log.debug(f"Canvas panned: offset=({self.pan_offset_x}, {self.pan_offset_y})")
        else:
            self.log.debug(f"Panning blocked: would exceed bounds at ({new_pan_x}, {new_pan_y})")

    def _can_pan(self, new_pan_x: int, new_pan_y: int) -> bool:
        """Check if panning to the new coordinates is allowed.

        Args:
            new_pan_x: New horizontal pan offset
            new_pan_y: New vertical pan offset

        Returns:
            True if panning is allowed, False otherwise
        """
        # For now, allow panning within reasonable bounds
        # Later we can add more sophisticated bounds checking
        max_pan = 10  # Maximum pan distance
        return (abs(new_pan_x) <= max_pan and abs(new_pan_y) <= max_pan)

    def _update_viewport_pixels(self) -> None:
        """Update the viewport pixels based on current panning offset."""
        if not self._panning_active:
            return

        # Clear viewport pixels
        viewport_pixels = []

        # Calculate buffer center offset
        buffer_center_x = (self.buffer_width - self.pixels_across) // 2
        buffer_center_y = (self.buffer_height - self.pixels_tall) // 2

        # Fill viewport with pixels from buffer at pan offset
        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                buffer_x = buffer_center_x + x + self.pan_offset_x
                buffer_y = buffer_center_y + y + self.pan_offset_y

                # Check if buffer coordinates are within bounds
                if (0 <= buffer_x < self.buffer_width and
                    0 <= buffer_y < self.buffer_height):
                    pixel_index = buffer_y * self.buffer_width + buffer_x
                    if pixel_index < len(self._buffer_pixels):
                        viewport_pixels.append(self._buffer_pixels[pixel_index])
                    else:
                        viewport_pixels.append((255, 0, 255))  # Transparent
                else:
                    viewport_pixels.append((255, 0, 255))  # Transparent

        # Update canvas pixels with viewport data
        self.pixels = viewport_pixels
        self.dirty_pixels = [True] * len(self.pixels)

        # Force redraw to update the visual display including borders
        self.force_redraw()

    def reset_panning(self) -> None:
        """Reset panning to original position."""
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        self._panning_active = False

        # Restore original viewport (center of buffer)
        self._update_viewport_pixels()
        self.dirty = 1

        self.log.debug("Panning reset to original position")

    def is_panning_active(self) -> bool:
        """Check if panning is currently active.

        Returns:
            True if panning is active, False otherwise
        """
        return self._panning_active

    def _save_viewport_sprite(self, filename: str) -> None:
        """Save only the viewport area when panning is active."""
        from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

        # Create a new animated sprite with viewport data
        viewport_sprite = AnimatedSprite()
        viewport_sprite.name = self.animated_sprite.name + "_viewport"
        viewport_sprite.description = f"Viewport of {self.animated_sprite.name} (panned)"

        # Copy viewport data for each animation
        for anim_name, frames in self.animated_sprite._animations.items():
            viewport_frames = []
            for frame in frames:
                viewport_frame = self._create_viewport_frame(frame)
                viewport_frames.append(viewport_frame)
            viewport_sprite._animations[anim_name] = viewport_frames

        # Set current animation and frame
        viewport_sprite.current_animation = self.current_animation
        viewport_sprite.current_frame = self.current_frame

        # Save the viewport sprite
        viewport_sprite.save(filename, DEFAULT_FILE_FORMAT)
        self.log.info(f"Saved viewport sprite to {filename}")

    def _create_viewport_frame(self, original_frame) -> 'SpriteFrame':
        """Create a frame containing only the viewport data."""
        from glitchygames.sprites.animated import SpriteFrame

        # Get viewport pixel data
        viewport_pixels = self._get_viewport_pixels_from_frame(original_frame)

        # Create new frame with viewport dimensions
        new_frame = SpriteFrame(
            surface=pygame.Surface((self.pixels_across, self.pixels_tall), pygame.SRCALPHA),
            duration=original_frame.duration
        )

        # Set viewport pixel data
        new_frame.set_pixel_data(viewport_pixels)

        return new_frame

    def _get_viewport_pixels_from_frame(self, frame) -> list[tuple[int, int, int]]:
        """Get viewport pixels from a frame based on current panning offset."""
        # Get the frame's pixel data
        frame_pixels = frame.get_pixel_data()
        frame_width, frame_height = frame.get_size()

        # Get current frame panning offset
        frame_key = self._get_current_frame_key()
        if frame_key in self._frame_panning and self._frame_panning[frame_key]['active']:
            pan_offset_x = self._frame_panning[frame_key]['pan_x']
            pan_offset_y = self._frame_panning[frame_key]['pan_y']
        else:
            pan_offset_x = 0
            pan_offset_y = 0

        # Create viewport pixels
        viewport_pixels = []
        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                buffer_x = x + pan_offset_x
                buffer_y = y + pan_offset_y

                # Check if buffer coordinates are within frame bounds
                if (0 <= buffer_x < frame_width and 0 <= buffer_y < frame_height):
                    pixel_index = buffer_y * frame_width + buffer_x
                    if pixel_index < len(frame_pixels):
                        viewport_pixels.append(frame_pixels[pixel_index])
                    else:
                        viewport_pixels.append((255, 0, 255))  # Transparent
                else:
                    viewport_pixels.append((255, 0, 255))  # Transparent

        return viewport_pixels

    def update_animation(self, dt: float) -> None:
        """Update the animated sprite with delta time."""
        if hasattr(self, "animated_sprite") and self.animated_sprite:
            self.animated_sprite.update(dt)

    def force_redraw(self):
        """Force a complete redraw of the canvas."""
        # Use the interface-based rendering while maintaining existing behavior
        self.image = self.canvas_renderer.force_redraw(self)


    def on_left_mouse_button_down_event(self, event):
        """Handle the left mouse button down event."""
        self.log.debug(f"AnimatedCanvasSprite mouse down event at {event.pos}, rect: {self.rect}")
        if self.rect.collidepoint(event.pos):
            x = (event.pos[0] - self.rect.x) // self.pixel_width
            y = (event.pos[1] - self.rect.y) // self.pixel_height
            self.log.debug(f"AnimatedCanvasSprite clicked at pixel ({x}, {y})")

            # Check for control-click (flood fill mode)
            is_control_click = pygame.key.get_pressed()[pygame.K_LCTRL] or pygame.key.get_pressed()[pygame.K_RCTRL]

            if is_control_click:
                # Flood fill mode
                self.log.info(f"Control-click detected - performing flood fill at ({x}, {y})")
                self._flood_fill(x, y, self.active_color)
            else:
                # Normal click mode
                # Mark that user is editing (manual frame selection)
                self._manual_frame_selected = True

                # Don't sync the canvas frame - keep it on the frame being edited
                # The canvas should stay on the current frame, only the live preview should animate

                # Use the interface to set the pixel
                self.canvas_interface.set_pixel_at(x, y, self.active_color)

            # Force redraw the canvas to show the changes
            self.force_redraw()

            # Update miniview with current frame data
            self._update_mini_view_from_current_frame()

            # Note: Live preview functionality is now integrated into the film strip

            # Update miniview
            if hasattr(self, "mini_view") and self.mini_view is not None:
                self.mini_view.on_pixel_update_event(event, self)
        else:
            self.log.info(
                f"AnimatedCanvasSprite click missed - pos {event.pos} not in rect {self.rect}"
            )

    def on_left_mouse_drag_event(self, event, trigger):
        """Handle mouse drag events."""
        # For drag events, we treat them the same as button down
        self.on_left_mouse_button_down_event(event)

    def on_mouse_motion_event(self, event):
        """Handle mouse motion events."""
        if self.rect.collidepoint(event.pos):
            # Mouse is over canvas - set hover state
            if not self.is_hovered:
                self.is_hovered = True
                self.dirty = 1  # Mark for redraw to show canvas border
                # Hide mouse cursor when entering canvas
                pygame.mouse.set_visible(False)

            # Convert mouse position to pixel coordinates
            x = (event.pos[0] - self.rect.x) // self.pixel_width
            y = (event.pos[1] - self.rect.y) // self.pixel_height

            # Check if the coordinates are within valid range
            if 0 <= x < self.pixels_across and 0 <= y < self.pixels_tall:
                # Update hovered pixel for white border effect
                self.hovered_pixel = (x, y)
                self.dirty = 1  # Mark for redraw to show hover effect

                if hasattr(self, "mini_view") and self.mini_view is not None:
                    self.mini_view.update_canvas_cursor(x, y, self.active_color)
            else:
                # Mouse is over canvas but outside pixel grid - clear pixel hover
                if hasattr(self, "hovered_pixel") and self.hovered_pixel is not None:
                    self.hovered_pixel = None
                    self.dirty = 1  # Mark for redraw to remove pixel hover effect

                if hasattr(self, "mini_view") and self.mini_view is not None:
                    self.mini_view.clear_cursor()
        else:
            # Mouse is outside canvas - clear all hover effects
            if self.is_hovered:
                self.is_hovered = False
                self.dirty = 1  # Mark for redraw to remove canvas border
                # Show mouse cursor when leaving canvas
                pygame.mouse.set_visible(True)

            if hasattr(self, "hovered_pixel") and self.hovered_pixel is not None:
                self.hovered_pixel = None
                self.dirty = 1  # Mark for redraw to remove pixel hover effect

            if hasattr(self, "mini_view") and self.mini_view is not None:
                self.mini_view.clear_cursor()

    def on_pixel_update_event(self, event, trigger):
        """Handle pixel update events."""
        if hasattr(trigger, "pixel_number"):
            pixel_num = trigger.pixel_number
            new_color = trigger.pixel_color
            self.log.debug(f"Animated canvas updating pixel {pixel_num} to color {new_color}")

            self.pixels[pixel_num] = new_color
            self.dirty_pixels[pixel_num] = True
            self.dirty = 1

            # Notify parent scene to update film strips
            if hasattr(self, "parent_scene") and self.parent_scene:
                self.parent_scene._update_film_strips_for_pixel_update()

            # Update the animated sprite's frame data
            if hasattr(self, "animated_sprite"):
                self._update_animated_sprite_frame()

            # Update miniview
            if hasattr(self, "mini_view") and self.mini_view is not None:
                self.mini_view.on_pixel_update_event(event, trigger)

    def on_mouse_leave_window_event(self, event):
        """Handle mouse leaving window event."""
        self.log.info("Mouse left window, clearing miniview cursor")
        if hasattr(self, "mini_view") and self.mini_view is not None:
            self.mini_view.clear_cursor()

    def on_mouse_enter_sprite_event(self, event):
        """Handle mouse entering canvas."""
        self.log.info("Mouse entered animated canvas")
        if hasattr(self, "mini_view"):
            # Update cursor position immediately
            x = (event.pos[0] - self.rect.x) // self.pixel_width
            y = (event.pos[1] - self.rect.y) // self.pixel_height
            if 0 <= x < self.pixels_across and 0 <= y < self.pixels_tall:
                self.mini_view.update_canvas_cursor(x, y, self.active_color)

    def on_mouse_exit_sprite_event(self, event):
        """Handle mouse exiting canvas."""
        self.log.info("Mouse exited animated canvas")
        if hasattr(self, "mini_view") and self.mini_view is not None:
            self.mini_view.clear_cursor()

    def on_save_file_event(self, filename: str) -> None:
        """Handle save file events."""
        self.log.info(f"Starting save to file: {filename}")
        try:
            # Detect file format from extension
            file_format = detect_file_format(filename)
            self.log.info(f"Detected file format: {file_format}")

            # Check if this is a single-frame animation (converted from static sprite)
            if self._is_single_frame_animation():
                self.log.info("Detected single-frame animation, saving as static sprite")
                self._save_as_static_sprite(filename, file_format)
            else:
                # Use the interface-based save method for multi-frame animations
                self.sprite_serializer.save(
                    self.animated_sprite, filename=filename, file_format=file_format
                )
        except (OSError, ValueError, KeyError):
            self.log.error("Error saving file")
            raise

    def get_canvas_interface(self) -> AnimatedCanvasInterface:
        """Get the canvas interface for external access."""
        return self.canvas_interface

    def get_sprite_serializer(self) -> AnimatedSpriteSerializer:
        """Get the sprite serializer for external access."""
        return self.sprite_serializer

    def get_canvas_renderer(self) -> AnimatedCanvasRenderer:
        """Get the canvas renderer for external access."""
        return self.canvas_renderer

    def on_load_file_event(self, event: pygame.event.Event, trigger: object = None) -> None:
        """Handle load file event for animated sprites."""
        self.log.debug("=== Starting on_load_file_event for animated sprite ===")
        LOG.debug(f"DEBUG: Canvas on_load_file_event called with event: {event}")
        try:
            filename = event if isinstance(event, str) else event.text
            LOG.debug(f"DEBUG: Loading sprite from filename: {filename}")

            # Load the sprite from file
            loaded_sprite = self._load_sprite_from_file(filename)

            # Set the loaded sprite as the current animated sprite
            self.animated_sprite = loaded_sprite

            # Check if canvas needs resizing and resize if necessary
            self._check_and_resize_canvas(loaded_sprite)

            # Set up animation state
            self._setup_animation_state(loaded_sprite)

            # Update UI components
            self._update_ui_components(loaded_sprite)

            # Finalize the loading process
            self._finalize_sprite_loading(loaded_sprite, filename)

        except FileNotFoundError as e:
            self.log.error("File not found")
            # Show user-friendly error message instead of crashing
            if hasattr(self, "parent") and hasattr(self.parent, "debug_text"):
                self.parent.debug_text.text = f"Error: File not found - {e}"
        except Exception as e:
            self.log.error(f"Error in on_load_file_event for animated sprite: {e}")
            self.log.error(f"Exception type: {type(e).__name__}")
            import traceback
            self.log.error(f"Traceback: {traceback.format_exc()}")
            # Show user-friendly error message instead of crashing
            if hasattr(self, "parent") and hasattr(self.parent, "debug_text"):
                self.parent.debug_text.text = f"Error loading sprite: {e}"

    def _load_sprite_from_file(self, filename: str) -> AnimatedSprite:
        """Load an animated sprite from a file.

        Args:
            filename: Path to the sprite file to load

        Returns:
            Loaded AnimatedSprite instance

        Raises:
            FileNotFoundError: If the file doesn't exist
            Exception: For other loading errors

        """
        self.log.debug(f"Loading animated sprite from {filename}")

        # Check if this is a PNG file and convert it first
        if filename.lower().endswith(".png"):
            self.log.info("PNG file detected - converting to bitmappy format first")
            converted_toml_path = self._convert_png_to_bitmappy(filename)
            if converted_toml_path:
                filename = converted_toml_path
                self.log.info(f"Using converted TOML file: {filename}")
            else:
                raise Exception("Failed to convert PNG to bitmappy format")

        # Detect file format and load the sprite
        file_format = detect_file_format(filename)
        self.log.debug(f"Detected file format: {file_format}")

        # Create a new animated sprite and load it
        loaded_sprite = AnimatedSprite()
        loaded_sprite.load(filename)

        # Debug: Check what was loaded
        self.log.debug(f"Loaded sprite has _animations: {hasattr(loaded_sprite, '_animations')}")
        if hasattr(loaded_sprite, "_animations"):
            self.log.debug(f"Loaded sprite _animations: {list(loaded_sprite._animations.keys())}")
            self.log.debug(f"Loaded sprite current_animation: {loaded_sprite.current_animation}")
            self.log.debug(f"Loaded sprite is_playing: {loaded_sprite.is_playing}")

        return loaded_sprite

    def _check_and_resize_canvas(self, loaded_sprite: AnimatedSprite) -> None:
        """Check if canvas needs resizing and resize if necessary.

        Args:
            loaded_sprite: The loaded sprite to check dimensions against

        """
        # Check if the loaded sprite has different dimensions than the canvas
        if (
            loaded_sprite._animations
            and loaded_sprite.current_animation in loaded_sprite._animations
        ):
            first_frame = loaded_sprite._animations[loaded_sprite.current_animation][0]
            sprite_width, sprite_height = first_frame.get_size()
            self.log.debug(f"Loaded sprite dimensions: {sprite_width}x{sprite_height}")
            self.log.debug(f"Canvas dimensions: {self.pixels_across}x{self.pixels_tall}")

            # If sprite has different dimensions than canvas, resize canvas to match
            if sprite_width != self.pixels_across or sprite_height != self.pixels_tall:
                self.log.info(
                    f"Resizing canvas from {self.pixels_across}x{self.pixels_tall} to "
                    f"{sprite_width}x{sprite_height}"
                )
                self._resize_canvas_to_sprite_size(sprite_width, sprite_height)
        else:
            # No frames or animation - but the animated sprite loader already converted it
            self.log.info("Using already-converted animated sprite from static sprite")

            # Check if we need to resize the canvas
            if hasattr(loaded_sprite, "get_size"):
                sprite_width, sprite_height = loaded_sprite.get_size()
                self.log.debug(f"Static sprite dimensions: {sprite_width}x{sprite_height}")
                self.log.debug(f"Canvas dimensions: {self.pixels_across}x{self.pixels_tall}")

                # If sprite has different dimensions than canvas, resize canvas to match
                if sprite_width != self.pixels_across or sprite_height != self.pixels_tall:
                    self.log.info(
                        f"Resizing canvas from {self.pixels_across}x{self.pixels_tall} to "
                        f"{sprite_width}x{sprite_height}"
                    )
                    self._resize_canvas_to_sprite_size(sprite_width, sprite_height)

    def _update_ui_components(self, loaded_sprite: AnimatedSprite) -> None:
        """Update UI components after loading a sprite.

        Args:
            loaded_sprite: The loaded sprite to update UI components with

        """
        # Update the current frame display - this happens after the sprite is fully loaded
        if hasattr(self, "mini_view") and self.mini_view is not None:
            self.log.debug("Updating mini view after animation change")
            self._update_mini_view_from_current_frame()
        else:
            # Mini view is disabled, update film strips instead
            self.log.debug("Mini view disabled, updating film strips instead")
            # Update multiple film strips
            if hasattr(self, "film_strips") and self.film_strips:
                for film_strip in self.film_strips.values():
                    film_strip.mark_dirty()
            if hasattr(self, "film_strip_sprites") and self.film_strip_sprites:
                for film_strip_sprite in self.film_strip_sprites.values():
                    film_strip_sprite.dirty = 1

        # Note: Live preview functionality is now integrated into the film strip

        # Clear existing multiple film strips and recreate them
        if hasattr(self, "film_strips") and self.film_strips:
            # Clear existing film strips
            for film_strip_sprite in self.film_strip_sprites.values():
                if hasattr(film_strip_sprite, "groups") and film_strip_sprite.groups():
                    for group in film_strip_sprite.groups():
                        group.remove(film_strip_sprite)
            self.film_strips.clear()
            self.film_strip_sprites.clear()

        # Film strips will be created by the parent scene

        # Notify parent scene about sprite load
        LOG.debug(f"DEBUG: Checking callbacks - hasattr(parent_scene): {hasattr(self, 'parent_scene')}, hasattr(on_sprite_loaded): {hasattr(self, 'on_sprite_loaded')}")
        if hasattr(self, "parent_scene") and self.parent_scene:
            self.log.debug("Calling parent scene _on_sprite_loaded")
            LOG.debug(f"DEBUG: Calling parent scene _on_sprite_loaded")
            self.parent_scene._on_sprite_loaded(loaded_sprite)
        elif hasattr(self, "on_sprite_loaded") and self.on_sprite_loaded:
            self.log.debug("Calling on_sprite_loaded callback")
            LOG.debug(f"DEBUG: Calling on_sprite_loaded callback")
            self.on_sprite_loaded(loaded_sprite)
        else:
            LOG.debug(f"DEBUG: No callback found - hasattr(parent_scene): {hasattr(self, 'parent_scene')}, hasattr(on_sprite_loaded): {hasattr(self, 'on_sprite_loaded')}")
            self.log.debug("No parent scene or callback found")

    def _setup_animation_state(self, loaded_sprite: AnimatedSprite) -> None:
        """Set up animation state after loading a sprite.

        Args:
            loaded_sprite: The loaded sprite to set up animation for

        """
        # Update the canvas sprite's current animation to match the loaded sprite
        self.current_animation = loaded_sprite.current_animation
        self.log.debug(f"Updated canvas animation to: {self.current_animation}")

        # Debug: Print available animations
        available_animations = (
            list(loaded_sprite._animations.keys()) if hasattr(loaded_sprite, "_animations") else []
        )
        self.log.info(f"AVAILABLE ANIMATIONS: {available_animations}")
        self.log.info(f"CURRENT CANVAS ANIMATION: '{self.current_animation}'")

        # Start the animation after loading
        if loaded_sprite.current_animation:
            # Ensure looping is enabled before starting
            loaded_sprite._is_looping = True
            loaded_sprite.play()
            self.log.debug(
                f"Started animation '{loaded_sprite.current_animation}' using play() method"
            )
            # Verify animation state immediately after starting
            self.log.debug(
                f"Animation state after play(): is_playing={loaded_sprite.is_playing}, "
                f"is_looping={loaded_sprite._is_looping}, "
                f"current_frame={loaded_sprite.current_frame}"
            )

    def _finalize_sprite_loading(self, loaded_sprite: AnimatedSprite, filename: str) -> None:
        """Finalize sprite loading process.

        Args:
            loaded_sprite: The loaded sprite
            filename: The filename that was loaded

        """
        # Now copy the sprite data to canvas with the correct animation
        self._copy_sprite_to_canvas()
        self.dirty = 1
        self.force_redraw()

        # Force a complete redraw
        self.dirty = 1
        self.force_redraw()

        self.log.info(f"Successfully loaded animated sprite from {filename}")

        # Final mini view update to ensure it has the correct data
        if hasattr(self, "mini_view"):
            self.log.debug("Final mini view update after sprite load")
            self._update_mini_view_from_current_frame()

        # Update AI textbox with sprite description or default prompt
        self.log.debug("Checking parent and debug_text access...")
        self.log.debug(f"hasattr(self, 'parent_scene'): {hasattr(self, 'parent_scene')}")
        if hasattr(self, "parent_scene"):
            self.log.debug(f"hasattr(self.parent_scene, 'debug_text'): {hasattr(self.parent_scene, 'debug_text')}")
            self.log.debug(f"self.parent_scene type: {type(self.parent_scene)}")

        if hasattr(self, "parent_scene") and hasattr(self.parent_scene, "debug_text"):
            # Get description from loaded sprite, or use default prompt if empty
            description = getattr(loaded_sprite, "description", "")
            self.log.debug(f"Loaded sprite description: '{description}'")
            self.log.debug(f"Description is not empty: {bool(description and description.strip())}")
            if description and description.strip():
                self.log.info(f"Setting AI textbox to description: '{description}'")
                self.parent_scene.debug_text.text = description
            else:
                self.log.info("Setting AI textbox to default prompt")
                self.parent_scene.debug_text.text = "Enter a description of the sprite you want to create:"
        else:
            self.log.warning("Cannot access parent or debug_text - description not updated")

    def _resize_canvas_to_sprite_size(self, sprite_width, sprite_height):
        """Resize the canvas to match the sprite dimensions."""
        self.log.debug(f"Resizing canvas to {sprite_width}x{sprite_height}")

        # Update canvas dimensions
        self.pixels_across = sprite_width
        self.pixels_tall = sprite_height

        # Get screen dimensions directly from pygame display
        screen = pygame.display.get_surface()
        screen_width = screen.get_width()
        screen_height = screen.get_height()

        # Recalculate pixel dimensions to fit the screen
        available_height = screen_height - 80 - 24  # Adjust for bottom margin and menu bar
        # ===== DEBUG: CANVAS SIZING CALCULATIONS =====
        LOG.debug("===== DEBUG: CANVAS SIZING CALCULATIONS =====")
        LOG.debug(f"Screen: {screen_width}x{screen_height}, Sprite: {sprite_width}x{sprite_height}")
        LOG.debug(f"Available height: {available_height}")
        LOG.debug(f"Height constraint: {available_height // sprite_height}")
        LOG.debug(f"Width constraint: {(screen_width * 1 // 2) // sprite_width}")
        LOG.debug(f"320x320 constraint: {320 // max(sprite_width, sprite_height)}")

        # For large sprites (128x128), ensure we get at least 2x2 pixel size
        if sprite_width >= 128 and sprite_height >= 128:
            pixel_size = 2  # Force 2x2 pixel size for 128x128
            LOG.debug("*** FORCING 2x2 pixel size for 128x128 sprite ***")
        else:
            pixel_size = min(
                available_height // sprite_height,
                (screen_width * 1 // 2) // sprite_width,
                # Maximum canvas size constraint: 320x320
                320 // max(sprite_width, sprite_height)
            )
            LOG.debug(f"Calculated pixel_size: {pixel_size}")
        # Ensure minimum pixel size of 1x1
        pixel_size = max(pixel_size, 1)

        LOG.debug(f"Final pixel_size: {pixel_size}")
        LOG.debug(f"Canvas will be: {sprite_width * pixel_size}x{sprite_height * pixel_size}")
        LOG.debug("===== END DEBUG =====\n")

        # Update pixel dimensions
        self.pixel_width = pixel_size
        self.pixel_height = pixel_size

        # Create new pixel arrays
        self.pixels = [(255, 0, 255, 255)] * (sprite_width * sprite_height)  # Initialize with magenta
        self.dirty_pixels = [True] * (sprite_width * sprite_height)

        # Update surface dimensions
        actual_width = sprite_width * pixel_size
        actual_height = sprite_height * pixel_size
        LOG.debug("===== DEBUG: SURFACE CREATION =====")
        LOG.debug(f"Creating surface: {actual_width}x{actual_height}")
        LOG.debug(f"pixel_size: {pixel_size}, sprite: {sprite_width}x{sprite_height}")
        self.image = pygame.Surface((actual_width, actual_height))
        LOG.debug("Surface created successfully")
        LOG.debug("===== END DEBUG =====\n")
        self.rect = self.image.get_rect(x=self.rect.x, y=self.rect.y)

        # Update class dimensions

        # Update AI sprite positioning after canvas resize
        if hasattr(self, "parent_scene") and self.parent_scene:
            self.parent_scene._update_ai_sprite_position()
        AnimatedCanvasSprite.WIDTH = sprite_width
        AnimatedCanvasSprite.HEIGHT = sprite_height

        # Reinitialize mini view if it exists and has the resize method
        if hasattr(self, "mini_view") and hasattr(self, "_resize_mini_view"):
            self._resize_mini_view(sprite_width, sprite_height)

        self.log.info(
            f"Canvas resized to {sprite_width}x{sprite_height} with pixel size {pixel_size}"
        )

    def _convert_static_to_animated(self, static_sprite, width: int, height: int) -> AnimatedSprite:
        """Convert a static sprite to an animated sprite with 1 frame."""
        # Create new animated sprite
        animated_sprite = AnimatedSprite()

        # Get pixel data from static sprite
        if hasattr(static_sprite, "get_pixel_data"):
            pixel_data = static_sprite.get_pixel_data()
            self.log.debug(
                f"Got pixel data from get_pixel_data(): {len(pixel_data)} pixels, "
                f"first few: {pixel_data[:5]}"
            )
        elif hasattr(static_sprite, "pixels"):
            pixel_data = static_sprite.pixels.copy()
            self.log.debug(
                f"Got pixel data from pixels attribute: {len(pixel_data)} pixels, "
                f"first few: {pixel_data[:5]}"
            )
        else:
            # Fallback - create magenta pixels
            pixel_data = [(255, 0, 255)] * (width * height)
            self.log.debug(f"Using fallback magenta pixels: {len(pixel_data)} pixels")

        # Create a single frame with the static sprite data
        frame = SpriteFrame(width, height)
        frame.set_pixel_data(pixel_data)

        # Get the animation name from the static sprite if available
        animation_name = "idle"  # Default fallback
        if hasattr(static_sprite, "name") and static_sprite.name:
            animation_name = static_sprite.name
        elif hasattr(static_sprite, "animation_name") and static_sprite.animation_name:
            animation_name = static_sprite.animation_name

        # Add the frame to the animated sprite with the correct animation name
        animated_sprite.add_frame(animation_name, frame)

        # Set the current animation to the actual animation name
        animated_sprite.current_animation = animation_name
        animated_sprite.current_frame = 0

        # Debug: Verify the conversion worked
        self.log.debug(
            f"Converted static sprite to animated format with 1 frame: {len(pixel_data)} pixels"
        )
        self.log.debug(f"Animated sprite has frames: {hasattr(animated_sprite, 'frames')}")
        if hasattr(animated_sprite, "frames"):
            self.log.debug(f"Available animations: {list(animated_sprite._animations.keys())}")
            if "idle" in animated_sprite._animations:
                self.log.debug(
                    f"Idle animation has {len(animated_sprite._animations['idle'])} frames"
                )
                if animated_sprite._animations["idle"]:
                    frame_pixels = animated_sprite._animations["idle"][0].get_pixel_data()
                    self.log.debug(
                        f"First frame pixels: {len(frame_pixels)} pixels, "
                        f"first few: {frame_pixels[:5]}"
                    )

        return animated_sprite

    def _is_single_frame_animation(self) -> bool:
        """Check if this is a single-frame animation (converted from static sprite)."""
        if not hasattr(self, "animated_sprite") or not self.animated_sprite:
            return False

        # Check if there's only one animation with one frame
        if hasattr(self.animated_sprite, "_animations") and self.animated_sprite._animations:
            animations = list(self.animated_sprite._animations.keys())
            if len(animations) == 1 and len(self.animated_sprite._animations[animations[0]]) == 1:
                return True

        return False

    def _save_as_static_sprite(self, filename: str, file_format: str) -> None:
        """Save a single-frame animation as a static sprite."""
        if not hasattr(self, "animated_sprite") or not self.animated_sprite:
            raise ValueError("No animated sprite to save")

        # Get the single frame
        animations = list(self.animated_sprite._animations.keys())
        if not animations:
            raise ValueError("No animations found")

        animation_name = animations[0]
        frames = self.animated_sprite._animations[animation_name]
        if not frames:
            raise ValueError("No frames found in animation")

        frame = frames[0]  # Get the first (and only) frame

        # Create an AnimatedSprite from the frame (since everything is AnimatedSprite now)
        # Create a new AnimatedSprite with the frame data
        animated_sprite = AnimatedSprite()

        # Set up the frame data using the sprite's name or a default
        animation_name = getattr(frame, "name", "frame") or "frame"
        animated_sprite._animations = {animation_name: [frame]}
        animated_sprite.frame_manager.current_animation = animation_name
        animated_sprite.frame_manager.current_frame = 0

        # Preserve the description from the original sprite
        if hasattr(self.animated_sprite, "description"):
            animated_sprite.description = self.animated_sprite.description
            self.log.debug(f"Preserved description: '{animated_sprite.description}'")

        # Update the sprite's image to match the frame
        animated_sprite.image = frame.image.copy()
        animated_sprite.rect = animated_sprite.image.get_rect()

        # Save using the animated sprite's save method
        animated_sprite.save(filename, file_format)
        self.log.info(f"Saved single-frame animation as static sprite to {filename}")

    def _copy_sprite_to_canvas(self) -> None:
        """Copy the current frame of the animated sprite to the canvas."""
        if not hasattr(self, "animated_sprite") or not self.animated_sprite:
            return

        # Get the current frame pixels from the animated sprite
        current_frame_pixels = self._get_current_frame_pixels()
        if current_frame_pixels:
            # Copy the pixels to the canvas
            self.pixels = current_frame_pixels.copy()
            self.dirty_pixels = [True] * len(self.pixels)
            self.log.debug(f"Copied {len(current_frame_pixels)} pixels to canvas")
            self.log.debug(
                f"Canvas pixels after copy: {self.pixels[:5] if self.pixels else 'None'}"
            )
        else:
            self.log.warning("No current frame pixels to copy to canvas")

    def _resize_mini_view(self, width: int, height: int) -> None:
        """Resize mini view for new canvas dimensions."""
        if not hasattr(self, "mini_view") or not self.mini_view:
            return

        self.log.debug(f"Resizing mini view to {width}x{height}")

        # Get screen dimensions from pygame
        screen_info = pygame.display.Info()
        screen_width = screen_info.current_w

        # Calculate mini map size using the same logic as MiniView
        pixel_width, pixel_height = MiniView.pixels_per_pixel(width, height)
        mini_map_width = width * pixel_width

        # Position mini map flush to the right edge and top
        mini_map_x = screen_width - mini_map_width  # Flush to right edge
        mini_map_y = 24  # Flush to top (below menu bar)

        # Ensure mini map doesn't go off screen
        if mini_map_x < 0:
            mini_map_x = 20  # Fallback to left side if too wide

        # Update mini view dimensions and position
        if hasattr(self, "mini_view") and self.mini_view is not None:
            self.mini_view.pixels_across = width
            self.mini_view.pixels_tall = height
            self.mini_view.rect.x = mini_map_x
            self.mini_view.rect.y = mini_map_y

            # Update mini view surface
            self.mini_view.image = pygame.Surface((mini_map_width, height * pixel_height))
            self.mini_view.rect = self.mini_view.image.get_rect(x=mini_map_x, y=mini_map_y)

            # Update pixel arrays - copy from the current canvas pixels
            if hasattr(self, "pixels") and len(self.pixels) == width * height:
                self.mini_view.pixels = self.pixels.copy()
            else:
                # Fallback to magenta if dimensions don't match
                self.mini_view.pixels = [(255, 0, 255, 255)] * (width * height)
            self.mini_view.dirty_pixels = [True] * (width * height)

            # Don't update mini view pixels here - it will be updated later after animation is set
            self.log.debug("Mini view resized, will update pixels after animation is set")

            # Force redraw
            self.mini_view.dirty = 1
            self.mini_view.force_redraw()

        self.log.debug(
            f"Mini view resized to {width}x{height} at position ({mini_map_x}, {mini_map_y})"
        )
        if hasattr(self, "mini_view") and self.mini_view is not None:
            self.log.debug(
                f"Mini view pixels: {len(self.mini_view.pixels)} pixels, "
                f"first few: {self.mini_view.pixels[:5] if self.mini_view.pixels else 'None'}"
            )

    def _update_animated_sprite_frame(self):
        """Update the animated sprite's current frame with canvas data."""
        if (
            hasattr(self, "animated_sprite")
            and hasattr(self, "current_animation")
            and hasattr(self, "current_frame")
        ):
            # Get current animation and frame
            current_anim = self.current_animation
            current_frame = self.current_frame

            if (
                current_anim
                and current_frame is not None
                and current_anim in self.animated_sprite._animations
                and 0 <= current_frame < len(self.animated_sprite._animations[current_anim])
                and hasattr(self.animated_sprite._animations[current_anim][current_frame], "image")
            ):
                # Update the frame's pixel data
                frames = self.animated_sprite._animations[current_anim]
                # Update the frame's image with current canvas data
                frame = frames[current_frame]
                # Create a new surface from the canvas pixels with alpha support
                surface = pygame.Surface((self.pixels_across, self.pixels_tall), pygame.SRCALPHA)
                for y in range(self.pixels_tall):
                    for x in range(self.pixels_across):
                        pixel_num = y * self.pixels_across + x
                        if pixel_num < len(self.pixels):
                            color = self.pixels[pixel_num]
                            surface.set_at((x, y), color)

                # Update the frame's image
                frame.image = surface

                # Notify parent scene to update film strips
                if hasattr(self, "parent_scene") and self.parent_scene:
                    self.parent_scene._update_film_strips_for_animated_sprite_update()

    def get_canvas_surface(self):
        """Get the current canvas surface for the film strip."""
        # Create a surface from the current canvas pixels with alpha support
        surface = pygame.Surface((self.pixels_across, self.pixels_tall), pygame.SRCALPHA)
        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                pixel_num = y * self.pixels_across + x
                if pixel_num < len(self.pixels):
                    color = self.pixels[pixel_num]
                    surface.set_at((x, y), color)
        return surface

    def _flood_fill(self, start_x: int, start_y: int, fill_color: tuple[int, int, int]) -> None:
        """Perform flood fill algorithm starting from the given coordinates.

        Args:
            start_x: Starting X coordinate
            start_y: Starting Y coordinate
            fill_color: Color to fill with
        """
        # Check bounds
        if not (0 <= start_x < self.pixels_across and 0 <= start_y < self.pixels_tall):
            self.log.warning(f"Flood fill coordinates out of bounds: ({start_x}, {start_y})")
            return

        # Get the target color (the color we're replacing)
        target_color = self.canvas_interface.get_pixel_at(start_x, start_y)

        # If target color is the same as fill color, no work needed
        if target_color == fill_color:
            self.log.info("Target color same as fill color, no flood fill needed")
            return

        self.log.info(f"Flood fill: replacing {target_color} with {fill_color} starting at ({start_x}, {start_y})")

        # Use iterative flood fill with a stack to avoid recursion depth issues
        stack = [(start_x, start_y)]
        filled_pixels = 0

        while stack:
            x, y = stack.pop()

            # Check bounds and color match
            if (0 <= x < self.pixels_across and 0 <= y < self.pixels_tall and
                self.canvas_interface.get_pixel_at(x, y) == target_color):

                # Fill this pixel
                self.canvas_interface.set_pixel_at(x, y, fill_color)
                filled_pixels += 1

                # Add adjacent pixels to stack (4-connected)
                stack.append((x + 1, y))  # Right
                stack.append((x - 1, y))  # Left
                stack.append((x, y + 1))  # Down
                stack.append((x, y - 1))  # Up

        self.log.info(f"Flood fill completed: filled {filled_pixels} pixels")

    def _initialize_panning_system(self) -> None:
        """Initialize the panning system for the canvas."""
        # Panning state
        self.pan_offset_x = 0  # Horizontal pan offset in pixels
        self.pan_offset_y = 0  # Vertical pan offset in pixels

        # Buffer dimensions (larger than canvas to allow panning)
        # Add extra space around the canvas for panning
        self.buffer_width = self.pixels_across + 20  # Extra 10 pixels on each side
        self.buffer_height = self.pixels_tall + 20   # Extra 10 pixels on each side

        # Viewport dimensions (same as canvas dimensions)
        self.viewport_width = self.pixels_across
        self.viewport_height = self.pixels_tall

        # Panning state flag
        self._panning_active = False

        # Initialize buffer with transparent pixels
        self._buffer_pixels = [(255, 0, 255, 255) for _ in range(self.buffer_width * self.buffer_height)]

        # Copy current canvas pixels to center of buffer
        if hasattr(self, 'pixels') and self.pixels:
            buffer_center_x = (self.buffer_width - self.pixels_across) // 2
            buffer_center_y = (self.buffer_height - self.pixels_tall) // 2

            for y in range(self.pixels_tall):
                for x in range(self.pixels_across):
                    buffer_x = buffer_center_x + x
                    buffer_y = buffer_center_y + y
                    buffer_index = buffer_y * self.buffer_width + buffer_x
                    canvas_index = y * self.pixels_across + x

                    if buffer_index < len(self._buffer_pixels) and canvas_index < len(self.pixels):
                        self._buffer_pixels[buffer_index] = self.pixels[canvas_index]

        self.log.debug(f"Panning system initialized: buffer={self.buffer_width}x{self.buffer_height}, viewport={self.viewport_width}x{self.viewport_height}")

    def pan_canvas(self, delta_x: int, delta_y: int) -> None:
        """Pan the canvas by the given delta values.

        Args:
            delta_x: Horizontal panning delta (-1, 0, or 1)
            delta_y: Vertical panning delta (-1, 0, or 1)
        """
        # Get current frame key
        frame_key = self._get_current_frame_key()

        # Get current pan offset from frame state (or default to 0, 0)
        if frame_key in self._frame_panning:
            current_pan_x = self._frame_panning[frame_key]['pan_x']
            current_pan_y = self._frame_panning[frame_key]['pan_y']
        else:
            current_pan_x = 0
            current_pan_y = 0

        # Calculate new pan offset
        new_pan_x = current_pan_x + delta_x
        new_pan_y = current_pan_y + delta_y

        # Check if panning is within bounds
        if self._can_pan(new_pan_x, new_pan_y):
            # Initialize frame panning state if needed
            if frame_key not in self._frame_panning:
                self._frame_panning[frame_key] = {
                    'pan_x': 0,
                    'pan_y': 0,
                    'original_pixels': None,
                    'active': False
                }

            frame_state = self._frame_panning[frame_key]
            frame_state['pan_x'] = new_pan_x
            frame_state['pan_y'] = new_pan_y
            frame_state['active'] = True

            # Store original frame data if this is the first pan for this frame
            if frame_state['original_pixels'] is None:
                self._store_original_frame_data_for_frame(frame_key)

            # Apply panning transformation to show panned view
            self._apply_panning_view_for_frame(frame_key)
            self.dirty = 1
        else:
            self.log.debug(f"Cannot pan to ({new_pan_x}, {new_pan_y}) - out of bounds.")

    def _store_original_frame_data(self) -> None:
        """Store the original frame data before any panning."""
        if hasattr(self, 'pixels') and self.pixels:
            self._original_frame_pixels = list(self.pixels)
            self.log.debug("Stored original frame data for panning")

    def _apply_panning_view(self) -> None:
        """Apply panning transformation to show the panned view."""
        if not hasattr(self, '_original_frame_pixels'):
            return

        # Create panned view by shifting pixels
        panned_pixels = []

        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                # Calculate source coordinates (where to read from in original)
                source_x = x - self.pan_offset_x
                source_y = y - self.pan_offset_y

                # Check if source is within bounds
                if (0 <= source_x < self.pixels_across and
                    0 <= source_y < self.pixels_tall):
                    source_index = source_y * self.pixels_across + source_x
                    if source_index < len(self._original_frame_pixels):
                        panned_pixels.append(self._original_frame_pixels[source_index])
                    else:
                        panned_pixels.append((255, 0, 255))  # Transparent
                else:
                    panned_pixels.append((255, 0, 255))  # Transparent

        # Update canvas pixels with panned view
        self.pixels = panned_pixels
        self.dirty_pixels = [True] * len(self.pixels)

        self.log.debug(f"Applied panning view: offset=({self.pan_offset_x}, {self.pan_offset_y})")

    def reset_panning(self) -> None:
        """Reset panning to center position."""
        self.pan_offset_x = 0
        self.pan_offset_y = 0
        self._panning_active = False

        # Restore original frame data if it exists
        if hasattr(self, '_original_frame_pixels'):
            self.pixels = list(self._original_frame_pixels)
            self.dirty_pixels = [True] * len(self.pixels)
            delattr(self, '_original_frame_pixels')
            self.log.debug("Restored original frame data")

        self.dirty = 1
        self.log.debug("Panning reset to center")

    def _can_pan(self, new_pan_x: int, new_pan_y: int) -> bool:
        """Check if the new pan offset is within the allowed bounds."""
        # For now, allow panning within reasonable bounds
        # Later we can add more sophisticated bounds checking
        max_pan = 10  # Maximum pan distance
        return (abs(new_pan_x) <= max_pan and abs(new_pan_y) <= max_pan)

    def _update_viewport_pixels(self) -> None:
        """Update the viewport pixels based on current panning offset."""
        if not self._panning_active:
            return

        # Clear viewport pixels
        viewport_pixels = []

        # Calculate buffer center offset
        buffer_center_x = (self.buffer_width - self.pixels_across) // 2
        buffer_center_y = (self.buffer_height - self.pixels_tall) // 2

        # Fill viewport with pixels from buffer at pan offset
        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                buffer_x = buffer_center_x + x + self.pan_offset_x
                buffer_y = buffer_center_y + y + self.pan_offset_y

                # Check if buffer coordinates are within bounds
                if (0 <= buffer_x < self.buffer_width and
                    0 <= buffer_y < self.buffer_height):
                    pixel_index = buffer_y * self.buffer_width + buffer_x
                    if pixel_index < len(self._buffer_pixels):
                        viewport_pixels.append(self._buffer_pixels[pixel_index])
                    else:
                        viewport_pixels.append((255, 0, 255))  # Transparent
                else:
                    viewport_pixels.append((255, 0, 255))  # Transparent

        # Update canvas pixels with viewport data
        self.pixels = viewport_pixels
        self.dirty_pixels = [True] * len(self.pixels)

        # Force redraw to update the visual display including borders
        self.force_redraw()

    def save_animated_sprite(self, filename: str) -> None:
        """Save the animated sprite to a file."""
        if self.is_panning_active():
            # Save viewport only when panning is active
            self.log.info("Saving viewport only due to active panning")
            self._save_viewport_sprite(filename)
        else:
            # Save full sprite when not panning
            self.sprite_serializer.save(self.animated_sprite, filename, DEFAULT_FILE_FORMAT)

    def _save_viewport_sprite(self, filename: str) -> None:
        """Save only the viewport area when panning is active."""
        from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

        # Create a new animated sprite with viewport data
        viewport_sprite = AnimatedSprite()
        viewport_sprite.name = self.animated_sprite.name + "_viewport"
        viewport_sprite.description = f"Viewport of {self.animated_sprite.name} (panned)"

        # Copy viewport data for each animation
        for anim_name, frames in self.animated_sprite._animations.items():
            viewport_frames = []
            for frame in frames:
                viewport_frame = self._create_viewport_frame(frame)
                viewport_frames.append(viewport_frame)
            viewport_sprite.add_animation(anim_name, viewport_frames)

        # Save the newly created viewport sprite
        self.sprite_serializer.save(viewport_sprite, filename, DEFAULT_FILE_FORMAT)
        self.log.info(f"Viewport sprite saved to {filename}")

    def _create_viewport_frame(self, original_frame) -> 'SpriteFrame':
        """Create a frame containing only the viewport data."""
        from glitchygames.sprites.animated import SpriteFrame

        # Get viewport pixel data
        viewport_pixels = self._get_viewport_pixels_from_frame(original_frame)

        # Create new frame with viewport dimensions
        new_frame = SpriteFrame(
            surface=pygame.Surface((self.pixels_across, self.pixels_tall), pygame.SRCALPHA),
            duration=original_frame.duration
        )

        # Set viewport pixel data
        new_frame.set_pixel_data(viewport_pixels)

        return new_frame

    def _get_viewport_pixels_from_frame(self, frame) -> list[tuple[int, int, int]]:
        """Get viewport pixels from a frame based on current panning offset."""
        # Get the frame's pixel data
        frame_pixels = frame.get_pixel_data()
        frame_width, frame_height = frame.get_size()

        # Get current frame panning offset
        frame_key = self._get_current_frame_key()
        if frame_key in self._frame_panning and self._frame_panning[frame_key]['active']:
            pan_offset_x = self._frame_panning[frame_key]['pan_x']
            pan_offset_y = self._frame_panning[frame_key]['pan_y']
        else:
            pan_offset_x = 0
            pan_offset_y = 0

        # Create viewport pixels
        viewport_pixels = []
        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                buffer_x = x + pan_offset_x
                buffer_y = y + pan_offset_y

                # Check if buffer coordinates are within frame bounds
                if (0 <= buffer_x < frame_width and 0 <= buffer_y < frame_height):
                    pixel_index = buffer_y * frame_width + buffer_x
                    if pixel_index < len(frame_pixels):
                        viewport_pixels.append(frame_pixels[pixel_index])
                    else:
                        viewport_pixels.append((255, 0, 255))  # Transparent
                else:
                    viewport_pixels.append((255, 0, 255))  # Transparent

        return viewport_pixels


class MiniView(BitmappySprite):
    """Mini View."""

    log = LOG
    BACKGROUND_COLORS: ClassVar[list[tuple[int, int, int]]] = [
        (0, 255, 255),  # Cyan
        (0, 0, 0),  # Black
        (128, 128, 128),  # Gray
        (255, 255, 255),  # White
        (255, 0, 255),  # Magenta
        (0, 255, 0),  # Green
        (0, 0, 255),  # Blue
        (255, 255, 0),  # Yellow
        (64, 64, 64),  # Dark Gray
        (192, 192, 192),  # Light Gray
    ]

    def __init__(self, pixels, x, y, width, height, name="Mini View", groups=None):
        """Initialize the MiniView sprite.

        Args:
            pixels: List of pixel colors
            x: X position
            y: Y position
            width: Width in pixels
            height: Height in pixels
            name: Sprite name
            groups: Sprite groups

        """
        self.pixels_across = width
        self.pixels_tall = height
        pixel_width, pixel_height = self.pixels_per_pixel(width, height)
        actual_width = width * pixel_width
        actual_height = height * pixel_height

        super().__init__(
            x=x, y=y, width=actual_width, height=actual_height, name=name, groups=groups
        )

        self.pixels = pixels
        self.dirty_pixels = [True] * len(pixels)
        self.background_color_index = 0
        self.background_color = self.BACKGROUND_COLORS[self.background_color_index]

        # Create initial surface
        self.image = pygame.Surface((actual_width, actual_height))
        self.rect = self.image.get_rect(x=x, y=y)

        # Initialize cursor and mouse tracking state
        self.canvas_cursor_pos = None
        self.cursor_color = (0, 0, 0)  # Will be updated from canvas's active color
        self.mouse_in_canvas = False

        self.dirty = 1
        self.force_redraw()
        self.log.info("MiniView initialized")

    def on_left_mouse_button_down_event(self, event):
        """Handle left mouse button to cycle background color."""
        if self.rect.collidepoint(event.pos):
            self.log.info(f"MiniView clicked at {event.pos}, rect is {self.rect}")
            old_color = self.background_color
            self.background_color_index = (self.background_color_index + 1) % len(
                self.BACKGROUND_COLORS
            )
            self.background_color = self.BACKGROUND_COLORS[self.background_color_index]
            self.log.info(
                f"MiniView background color changing from {old_color} to {self.background_color}"
            )
            self.dirty = 1
            self.log.info("Setting dirty flag and calling force_redraw")
            self.force_redraw()
            return True
        return False

    def update_canvas_cursor(self, x, y, active_color=None):
        """Update the cursor position and color from the main canvas."""
        if x is None or y is None:
            self.clear_cursor()
            return

        if not (0 <= x < self.pixels_across and 0 <= y < self.pixels_tall):
            self.clear_cursor()
            return

        if active_color is not None:
            self.cursor_color = active_color

        old_pos = self.canvas_cursor_pos
        self.canvas_cursor_pos = (x, y)

        if old_pos != self.canvas_cursor_pos:
            self.dirty = 1

    def on_pixel_update_event(self, event, trigger):
        """Handle pixel update events."""
        if hasattr(trigger, "pixel_number"):
            pixel_num = trigger.pixel_number
            new_color = trigger.pixel_color
            self.log.debug(f"MiniView updating pixel {pixel_num} to color {new_color}")

            self.pixels[pixel_num] = new_color
            self.dirty_pixels[pixel_num] = True
            self.dirty = 1

    def force_redraw(self):
        """Force a complete redraw of the miniview."""
        self.log.debug(f"Starting force_redraw with background color {self.background_color}")
        self.image.fill(self.background_color)
        pixel_width, pixel_height = self.pixels_per_pixel(self.pixels_across, self.pixels_tall)

        # Draw all non-magenta pixels
        for i, pixel in enumerate(self.pixels):
            if pixel != (255, 0, 255):  # Skip magenta pixels
                x = (i % self.pixels_across) * pixel_width
                y = (i // self.pixels_across) * pixel_height
                pygame.draw.rect(self.image, pixel, (x, y, pixel_width, pixel_height))

        self.log.debug(f"MiniView force redraw complete with background {self.background_color}")

    def update(self):
        """Update the miniview display."""
        # Get mouse position and window size
        mouse_pos = pygame.mouse.get_pos()
        screen_info = pygame.display.Info()
        screen_rect = pygame.Rect(0, 0, screen_info.current_w, screen_info.current_h)

        # Clear cursor if mouse is outside window
        if not screen_rect.collidepoint(mouse_pos):
            self.clear_cursor()

        if self.dirty:
            self.force_redraw()
            self.dirty = 0

    def clear_cursor(self):
        """Clear the cursor and force a redraw."""
        if self.canvas_cursor_pos is not None:
            self.log.info("Clearing miniview cursor")
            self.canvas_cursor_pos = None
            self.dirty = 1
            self.force_redraw()

    @staticmethod
    def pixels_per_pixel(_pixels_across: int, _pixels_tall: int) -> tuple[int, int]:
        """Calculate the size of each pixel in the miniview."""
        # Use consistent 2x2 pixel doubling for best ergonomic experience
        return (2, 2)


class BitmapEditorScene(Scene):
    """Bitmap Editor Scene.

    The scene expects a 'size' option in the format "WIDTHxHEIGHT" (e.g., "800x600")
    when initialized. This corresponds to the -s command line parameter.
    """

    log = LOG

    # Set your game name/version here.
    NAME = "Bitmappy"
    VERSION = "1.0"

    def _setup_menu_bar(self) -> None:
        """Set up the menu bar and menu items."""
        menu_bar_height = 24  # Taller menu bar

        # Different heights for icon vs text items
        icon_height = 16  # Smaller height for icon
        menu_item_height = menu_bar_height  # Full height for text items

        # Different vertical offsets for icon vs text
        icon_y = (menu_bar_height - icon_height) // 2 - 2  # Center the icon and move up 2px
        menu_item_y = 0  # Text items use full height

        # Create the menu bar using the UI library's MenuBar
        self.menu_bar = MenuBar(
            name="Menu Bar",
            x=0,
            y=0,
            width=self.screen_width,
            height=menu_bar_height,
            groups=self.all_sprites,
        )

        # Add the raspberry icon with its specific height
        icon_path = resource_path("glitcygames", "assets", "raspberry.toml")
        self.menu_icon = MenuItem(
            name=None,
            x=4,  # Add 4px offset from left edge
            y=icon_y,
            width=16,
            height=icon_height,  # Use icon-specific height
            filename=icon_path,
            groups=self.all_sprites,
        )
        self.menu_bar.add_menu(self.menu_icon)

        # Add all menus with full height
        menu_item_x = 0  # Start at left edge
        icon_width = 16  # Width of the raspberry icon
        menu_spacing = 2  # Reduced spacing between items
        menu_item_width = 48
        border_offset = self.menu_bar.border_width  # Usually 2px

        # Start after icon, compensating for border
        menu_item_x = (icon_width + menu_spacing) - border_offset

        new_menu = MenuItem(
            name="New",
            x=menu_item_x,
            y=menu_item_y - border_offset,  # Compensate for y border too
            width=menu_item_width,
            height=menu_item_height,
            groups=self.all_sprites,
        )
        self.menu_bar.add_menu(new_menu)

        # Move to next position
        menu_item_x += menu_item_width + menu_spacing

        save_menu = MenuItem(
            name="Save",
            x=menu_item_x,
            y=menu_item_y - border_offset,
            width=menu_item_width,
            height=menu_item_height,
            groups=self.all_sprites,
        )
        self.menu_bar.add_menu(save_menu)

        # Move to next position
        menu_item_x += menu_item_width + menu_spacing

        load_menu = MenuItem(
            name="Load",
            x=menu_item_x,
            y=menu_item_y - border_offset,
            width=menu_item_width,
            height=menu_item_height,
            groups=self.all_sprites,
        )
        self.menu_bar.add_menu(load_menu)

    def _setup_canvas(self, options: dict) -> None:
        """Set up the canvas sprite."""
        # Calculate canvas dimensions and pixel size
        pixels_across, pixels_tall, pixel_size = self._calculate_canvas_dimensions(options)

        # Create animated sprite with single frame
        animated_sprite = self._create_animated_sprite(pixels_across, pixels_tall)

        # Create the main canvas sprite
        self._create_canvas_sprite(animated_sprite, pixels_across, pixels_tall, pixel_size)

        # Finalize setup and start animation
        self._finalize_canvas_setup(animated_sprite, options)

    def _calculate_canvas_dimensions(self, options: dict) -> tuple[int, int, int]:
        """Calculate canvas dimensions and pixel size.

        Args:
            options: Dictionary containing canvas configuration

        Returns:
            Tuple of (pixels_across, pixels_tall, pixel_size)

        """
        menu_bar_height = 24
        bottom_margin = 80  # Space needed for sliders and color well
        available_height = (
            self.screen_height - bottom_margin - menu_bar_height
        )  # Use menu_bar_height instead of 32

        # Calculate pixel size to fit the canvas in the available space
        width, height = options["size"].split("x")
        pixels_across = int(width)
        pixels_tall = int(height)

        # ===== DEBUG: INITIAL CANVAS SIZING =====
        LOG.debug("===== DEBUG: INITIAL CANVAS SIZING =====")
        LOG.debug(f"Screen: {self.screen_width}x{self.screen_height}, Sprite: {pixels_across}x{pixels_tall}")
        LOG.debug(f"Available height: {available_height}")
        LOG.debug(f"Height constraint: {available_height // pixels_tall}")
        LOG.debug(f"Width constraint: {(self.screen_width * 1 // 2) // pixels_across}")
        LOG.debug(f"350px width constraint: {350 // pixels_across}")
        LOG.debug(f"320x320 constraint: {320 // max(pixels_across, pixels_tall)}")

        # Calculate pixel size based on available space
        pixel_size = min(
            available_height // pixels_tall,  # Height-based size
            # Width-based size (use 1/2 of screen width)
            (self.screen_width * 1 // 2) // pixels_across,
            # Maximum width constraint: 350px
            350 // pixels_across,
        )
        LOG.debug(f"Calculated pixel_size: {pixel_size}")

        # For very large sprites, ensure we get at least 2x2 pixel size
        if pixel_size < 2:
            pixel_size = 2  # Force minimum 2x2 pixel size for very large sprites
            LOG.debug("*** FORCING minimum 2x2 pixel size for large sprite ***")

        LOG.debug(f"Final pixel_size: {pixel_size}")
        LOG.debug(f"Canvas will be: {pixels_across * pixel_size}x{pixels_tall * pixel_size}")
        LOG.debug("===== END DEBUG =====\n")
        # Ensure minimum pixel size of 1x1
        pixel_size = max(pixel_size, 1)

        return pixels_across, pixels_tall, pixel_size

    @staticmethod
    def _create_animated_sprite(pixels_across: int, pixels_tall: int) -> AnimatedSprite:
        """Create animated sprite with single frame.

        Args:
            pixels_across: Number of pixels across the canvas
            pixels_tall: Number of pixels tall the canvas

        Returns:
            Configured AnimatedSprite instance

        """
        # Create single test frame
        surface1 = pygame.Surface((pixels_across, pixels_tall))
        surface1.fill((255, 0, 255))  # Magenta frame (transparent)
        frame1 = SpriteFrame(surface1)
        frame1.pixels = [(255, 0, 255, 255)] * (pixels_across * pixels_tall)

        # Create animated sprite using proper initialization - single frame
        animated_sprite = AnimatedSprite()
        # Use the proper method to set up animations with single frame
        animation_name = "strip_1"  # Use a generic name for new sprites
        animated_sprite._animations = {animation_name: [frame1]}
        animated_sprite._frame_interval = 0.5
        animated_sprite._is_looping = True  # Enable looping for the animation

        # Set up the frame manager properly
        animated_sprite.frame_manager.current_animation = animation_name
        animated_sprite.frame_manager.current_frame = 0

        # Initialize the sprite properly like a loaded sprite would be
        animated_sprite._update_surface_and_mark_dirty()

        # Start in a paused state initially
        animated_sprite.pause()

        return animated_sprite

    def _create_canvas_sprite(
        self, animated_sprite: AnimatedSprite, pixels_across: int, pixels_tall: int, pixel_size: int
    ) -> None:
        """Create the main animated canvas sprite.

        Args:
            animated_sprite: The animated sprite to use
            pixels_across: Number of pixels across the canvas
            pixels_tall: Number of pixels tall the canvas
            pixel_size: Size of each pixel in screen coordinates

        """
        menu_bar_height = 24

        # Create the animated canvas with the calculated pixel dimensions
        self.canvas = AnimatedCanvasSprite(
            animated_sprite=animated_sprite,
            name="Animated Bitmap Canvas",
            x=0,
            y=menu_bar_height,  # Position canvas right below menu bar
            pixels_across=pixels_across,
            pixels_tall=pixels_tall,
            pixel_width=pixel_size,
            pixel_height=pixel_size,
            groups=self.all_sprites,
        )

        # Set parent scene reference for canvas
        self.canvas.parent_scene = self

        # Add backward compatibility properties for tests
        self.canvas.film_strip = None  # Will be set when film strips are created
        self.canvas.film_strip_sprite = None  # Will be set when film strips are created

        # Debug: Log canvas position and size
        self.log.info(
            f"AnimatedCanvasSprite created at position "
            f"({self.canvas.rect.x}, {self.canvas.rect.y}) with size {self.canvas.rect.size}"
        )
        self.log.info(f"AnimatedCanvasSprite groups: {self.canvas.groups()}")

    def _create_film_strips(self, groups) -> None:
        """Create film strips for the current animated sprite - handles all loading scenarios."""
        LOG.debug(f"DEBUG: _create_film_strips called")
        LOG.debug(f"DEBUG: hasattr(self, 'canvas'): {hasattr(self, 'canvas')}")
        if hasattr(self, "canvas"):
            LOG.debug(f"DEBUG: self.canvas: {self.canvas}")
            if self.canvas:
                LOG.debug(f"DEBUG: hasattr(self.canvas, 'animated_sprite'): {hasattr(self.canvas, 'animated_sprite')}")
                if hasattr(self.canvas, "animated_sprite"):
                    LOG.debug(f"DEBUG: self.canvas.animated_sprite: {self.canvas.animated_sprite}")
                    if self.canvas.animated_sprite:
                        LOG.debug(f"DEBUG: hasattr(self.canvas.animated_sprite, '_animations'): {hasattr(self.canvas.animated_sprite, '_animations')}")
                        if hasattr(self.canvas.animated_sprite, "_animations"):
                            LOG.debug(f"DEBUG: self.canvas.animated_sprite._animations: {self.canvas.animated_sprite._animations}")

        if not hasattr(self, "canvas") or not self.canvas or not hasattr(self.canvas, "animated_sprite") or not self.canvas.animated_sprite or not self.canvas.animated_sprite._animations:
            LOG.debug(f"DEBUG: _create_film_strips returning early - conditions not met")
            return

        animated_sprite = self.canvas.animated_sprite
        LOG.debug(f"DEBUG: _create_film_strips proceeding with animated_sprite: {animated_sprite}")

        # Calculate film strip dimensions
        # Position film strip so its left x is 2 pixels to the right of color well's right edge
        if hasattr(self, "color_well") and self.color_well:
            film_strip_x = self.color_well.rect.right + 1  # Film strip left x = color well right x + 1
        else:
            # Fallback: position to the right of the canvas
            film_strip_x = self.canvas.rect.right + 4  # 4 pixels to the right of canvas edge

        film_strip_y_start = self.canvas.rect.y  # Start at same vertical position as canvas

        screen_width = pygame.display.get_surface().get_width()
        available_width = screen_width - film_strip_x  # Extend to end of screen
        film_strip_width = max(300, available_width)

        # Calculate vertical spacing between strips
        strip_spacing = -19
        strip_height = 180  # Height of each film strip (increased by 20 pixels to accommodate delete button and proper spacing)
        current_y = film_strip_y_start  # Start at canvas Y position

        # Create a separate film strip for each animation
        LOG.debug(f"DEBUG: Starting film strip creation loop")
        for strip_index, (anim_name, frames) in enumerate(animated_sprite._animations.items()):
            LOG.debug(f"DEBUG: Creating film strip {strip_index} for animation {anim_name} with {len(frames)} frames")
            LOG.debug(f"Creating film strip {strip_index} for animation {anim_name} with {len(frames)} frames")
            # Create a single animated sprite with just this animation
            # Use the proper constructor to ensure all attributes are initialized
            single_anim_sprite = AnimatedSprite()
            single_anim_sprite._animations = {anim_name: frames}
            single_anim_sprite._animation_order = [anim_name]  # Set animation order

            # Properly initialize the frame manager state
            single_anim_sprite.frame_manager.current_animation = anim_name
            single_anim_sprite.frame_manager.current_frame = 0

            # Set up the sprite to be ready for animation
            single_anim_sprite.set_animation(anim_name)
            single_anim_sprite.is_looping = True
            single_anim_sprite.play()

            # DEBUG: Log the sprite state
            LOG.debug(f"Created single_anim_sprite for {anim_name}:")
            LOG.debug(f"  _animations: {list(single_anim_sprite._animations.keys())}")
            LOG.debug(f"  _animation_order: {single_anim_sprite._animation_order}")
            LOG.debug(f"  current_animation: {single_anim_sprite.current_animation}")
            LOG.debug(f"  is_playing: {single_anim_sprite.is_playing}")
            LOG.debug(f"  is_looping: {single_anim_sprite.is_looping}")

            # Animation setup will be handled by set_animated_sprite method

            # The animated sprite should use the original animation frames, not canvas content
            # The canvas content is only used for individual frame thumbnails, not the animated preview

            # Calculate Y position with scrolling
            base_y = film_strip_y_start + (strip_index * (strip_height + strip_spacing))
            scroll_y = base_y - (self.film_strip_scroll_offset * (strip_height + strip_spacing))

            # Create film strip widget for this animation
            film_strip = FilmStripWidget(
                x=film_strip_x,
                y=scroll_y,
                width=film_strip_width,
                height=strip_height
            )
            film_strip.set_animated_sprite(single_anim_sprite)
            film_strip.strip_index = strip_index  # Track which strip this is

            # Update the layout to calculate frame positions
            LOG.debug(f"Updating layout for film strip {strip_index} ({anim_name})")
            film_strip.update_layout()
            LOG.debug(f"Film strip {strip_index} layout updated, frame_layouts has {len(film_strip.frame_layouts)} entries")

            # Set parent scene reference for selection handling
            film_strip.parent_scene = self

            # Store the strip in the film strips dictionary
            self.film_strips[anim_name] = film_strip

            # Create film strip sprite for rendering
            film_strip_sprite = FilmStripSprite(
                film_strip_widget=film_strip,
                x=film_strip_x,
                y=scroll_y,
                width=film_strip_width,
                height=film_strip.rect.height,
                groups=groups,
            )

            # Debug: Check if film strip sprite was added to groups
            self.log.debug(f"Created film strip sprite for {anim_name}, groups: {film_strip_sprite.groups()}")
            LOG.debug(f"DEBUG: Film strip sprite {anim_name} added to {len(film_strip_sprite.groups())} groups: {film_strip_sprite.groups()}")

            # Connect the film strip to the canvas
            film_strip_sprite.set_parent_canvas(self.canvas)
            film_strip.set_parent_canvas(self.canvas)

            # Set parent scene reference for the film strip sprite
            film_strip_sprite.parent_scene = self

            # Set parent scene reference for the film strip widget
            film_strip.parent_scene = self

            # Set up bidirectional reference between film strip widget and sprite
            film_strip.film_strip_sprite = film_strip_sprite
            film_strip_sprite.film_strip_widget = film_strip

            # Store the film strip sprite
            self.film_strip_sprites[anim_name] = film_strip_sprite

            # Set backward compatibility attributes (for tests) - use first film strip
            if not hasattr(self.canvas, "film_strip") or self.canvas.film_strip is None:
                self.canvas.film_strip = film_strip
                self.canvas.film_strip_sprite = film_strip_sprite

            # CRITICAL: Mark film strip sprite as dirty and force initial redraw
            # This ensures the film strip updates properly on first load
            film_strip_sprite.dirty = 2  # Full surface blit
            film_strip.mark_dirty()
            film_strip_sprite.force_redraw()

            # Move to next strip position
            current_y += film_strip.rect.height + strip_spacing

        # Create scroll arrows
        self._create_scroll_arrows()

        # CRITICAL: Ensure all film strip sprites are marked as dirty for initial render
        # This fixes the issue where film strips don't update on first load
        for film_strip_sprite in self.film_strip_sprites.values():
            film_strip_sprite.dirty = 2  # Full surface blit
            film_strip_sprite.force_redraw()

        # Update visibility to show only 2 strips at a time
        self._update_film_strip_visibility()

        # Select the first film strip and set its frame 0 as active
        LOG.debug(f"DEBUG: About to call _select_initial_film_strip")
        self._select_initial_film_strip()

        # OLD SYSTEM REMOVED - Using new multi-controller system instead

        LOG.debug(f"DEBUG: _create_film_strips completed successfully")

        # Reinitialize multi-controller system for existing controllers AFTER film strips are fully set up
        # Pass preserved controller selections if available
        preserved_selections = getattr(self, '_preserved_controller_selections', None)
        self._reinitialize_multi_controller_system(preserved_selections)

    def _select_initial_film_strip(self):
        """Select the first film strip and set its frame 0 as active on initialization."""
        if not hasattr(self, "film_strips") or not self.film_strips:
            return

        # Get all animation names in order
        if hasattr(self, "canvas") and self.canvas and hasattr(self.canvas, "animated_sprite"):
            animation_names = list(self.canvas.animated_sprite._animations.keys())
        else:
            animation_names = list(self.film_strips.keys())

        if animation_names:
            first_animation = animation_names[0]

            # Select this animation and frame 0
            if hasattr(self, "canvas") and self.canvas:
                self.canvas.show_frame(first_animation, 0)

            # Update global selection state
            self.selected_animation = first_animation
            self.selected_frame = 0

            # Mark all film strips as dirty so they redraw with correct selection state
            if hasattr(self, "film_strips") and self.film_strips:
                for strip_name, strip_widget in self.film_strips.items():
                    strip_widget.mark_dirty()

    def _update_film_strip_visibility(self):
        """Update which film strips are visible based on scroll offset."""
        if not hasattr(self, "film_strips") or not self.film_strips:
            return

        # Get all animation names in order
        if hasattr(self, "canvas") and self.canvas and hasattr(self.canvas, "animated_sprite"):
            animation_names = list(self.canvas.animated_sprite._animations.keys())
        else:
            animation_names = list(self.film_strips.keys())

        # Show only the visible range of strips
        start_index = self.film_strip_scroll_offset
        end_index = min(start_index + self.max_visible_strips, len(animation_names))

        # Get canvas position for reference
        film_strip_y_start = self.canvas.rect.y if hasattr(self, "canvas") and self.canvas else 0
        strip_height = 145
        strip_spacing = -19

        # Hide all strips first
        for anim_name, film_strip in self.film_strips.items():
            if hasattr(self, "film_strip_sprites") and anim_name in self.film_strip_sprites:
                self.film_strip_sprites[anim_name].visible = False

        # Show only the visible strips and position them in fixed slots
        for i in range(start_index, end_index):
            if i < len(animation_names):
                anim_name = animation_names[i]
                if anim_name in self.film_strips and anim_name in self.film_strip_sprites:
                    film_strip = self.film_strips[anim_name]
                    film_strip_sprite = self.film_strip_sprites[anim_name]

                    # Position in fixed slot (0 or 1)
                    slot_index = i - start_index
                    fixed_y = film_strip_y_start + (slot_index * (strip_height + strip_spacing))

                    # Update positions
                    film_strip.rect.y = fixed_y
                    film_strip_sprite.rect.y = fixed_y
                    film_strip_sprite.visible = True

                    # Mark as dirty to ensure redraw
                    film_strip_sprite.dirty = 2
                    film_strip.mark_dirty()
                    # Force complete redraw to clear any old sprockets
                    film_strip._force_redraw = True

        # Update scroll arrows
        self._update_scroll_arrows()

    def _create_scroll_arrows(self):
        """Create scroll arrow sprites."""
        if not hasattr(self, "canvas") or not self.canvas:
            return

        # Get canvas position for reference
        # Position film strip so its left x is 2 pixels to the right of color well's right edge
        if hasattr(self, "color_well") and self.color_well:
            film_strip_x = self.color_well.rect.right + 1  # Film strip left x = color well right x + 1
        else:
            # Fallback: position to the right of the canvas
            film_strip_x = self.canvas.rect.right + 4  # 4 pixels to the right of canvas edge
        film_strip_y_start = self.canvas.rect.y if hasattr(self, "canvas") and self.canvas else 0
        strip_height = 145
        strip_spacing = -19

        # Create up arrow (above first strip)
        up_arrow_y = film_strip_y_start - 30
        self.scroll_up_arrow = ScrollArrowSprite(
            x=film_strip_x + 10,
            y=up_arrow_y,
            width=20,
            height=20,
            groups=self.all_sprites,
            direction="up"
        )


    def _update_scroll_arrows(self):
        """Update scroll arrow visibility based on scroll state."""
        if not hasattr(self, "canvas") or not self.canvas or not hasattr(self.canvas, "animated_sprite"):
            return

        total_animations = len(self.canvas.animated_sprite._animations)

        # Show up arrow if we can scroll up
        if hasattr(self, "scroll_up_arrow") and self.scroll_up_arrow:
            should_show = (self.film_strip_scroll_offset > 0)
            if self.scroll_up_arrow.visible != should_show:
                self.scroll_up_arrow.visible = should_show
                self.scroll_up_arrow.dirty = 1


    def _add_new_animation(self, insert_after_index=None):
        """Add a new animation (film strip) and scroll to it.

        Args:
            insert_after_index: Index to insert the new strip after (None for end)

        """
        if not hasattr(self, "canvas") or not self.canvas or not hasattr(self.canvas, "animated_sprite"):
            return

        # Create a new animation (film strip)
        new_animation_name = f"strip_{len(self.canvas.animated_sprite._animations) + 1}"

        # Create a blank frame for the new animation
        if hasattr(self, "canvas") and self.canvas:
            # Get the canvas pixel dimensions (same as original canvas)
            pixels_across = self.canvas.pixels_across
            pixels_tall = self.canvas.pixels_tall

            # Create a blank frame surface with magenta background
            frame_surface = pygame.Surface((pixels_across, pixels_tall))
            frame_surface.fill((255, 0, 255))  # Magenta background

            # Create a proper animated sprite frame object
            from glitchygames.sprites.animated import SpriteFrame
            animated_frame = SpriteFrame(
                surface=frame_surface,
                duration=1.0  # 1 second duration
            )

            # Initialize the pixel data for the new frame
            animated_frame.pixels = [(255, 0, 255, 255)] * (pixels_across * pixels_tall)

            # Insert the new animation at the specified position
            if insert_after_index is not None:
                # Get current animations as a list to maintain order
                current_animations = list(self.canvas.animated_sprite._animations.items())

                # Create new ordered dict with the new animation inserted
                new_animations = {}
                for i, (anim_name, frames) in enumerate(current_animations):
                    new_animations[anim_name] = frames
                    if i == insert_after_index:
                        # Insert the new animation after this one
                        new_animations[new_animation_name] = [animated_frame]

                # If we didn't insert yet (insert_after_index >= len), add at end
                if insert_after_index >= len(current_animations):
                    new_animations[new_animation_name] = [animated_frame]

                # Replace the animations dict
                self.canvas.animated_sprite._animations = new_animations
            else:
                # Add at the end (original behavior)
                self.canvas.animated_sprite._animations[new_animation_name] = [animated_frame]

            # Track animation creation for undo/redo
            if hasattr(self, "film_strip_operation_tracker"):
                # Set flag to prevent frame selection tracking during animation creation
                self._creating_animation = True
                try:
                    # Create animation data for undo/redo
                    animation_data = {
                        "frames": [{
                            "width": animated_frame.image.get_width(),
                            "height": animated_frame.image.get_height(),
                            "pixels": animated_frame.pixels.copy() if hasattr(animated_frame, 'pixels') else [],
                            "duration": animated_frame.duration
                        }],
                        "frame_count": 1
                    }

                    # Track animation addition for undo/redo
                    self.film_strip_operation_tracker.add_animation_added(
                        new_animation_name, animation_data
                    )
                finally:
                    self._creating_animation = False

            # Recreate film strips to include the new animation
            self._on_sprite_loaded(self.canvas.animated_sprite)

            # Select the 0th frame of the new animation so the user can immediately start editing it
            LOG.debug(f"BitmapEditorScene: Selecting frame 0 of newly created animation '{new_animation_name}'")
            # Set flag to prevent frame selection tracking during animation creation
            self._creating_frame = True
            try:
                self.canvas.show_frame(new_animation_name, 0)

                # Update the undo/redo manager with the current frame for frame-specific operations
                if hasattr(self, "undo_redo_manager"):
                    self.undo_redo_manager.set_current_frame(new_animation_name, 0)
                    LOG.debug(f"BitmapEditorScene: Updated undo/redo manager to track frame 0 of '{new_animation_name}'")
            finally:
                self._creating_frame = False

            # Scroll to the new animation (last one)
            total_animations = len(self.canvas.animated_sprite._animations)
            max_scroll = max(0, total_animations - self.max_visible_strips)
            self.film_strip_scroll_offset = max_scroll

            # Update visibility and scroll arrows with the new offset
            self._update_film_strip_visibility()
            self._update_scroll_arrows()

            # Select the new frame and notify the canvas
            self.selected_animation = new_animation_name
            self.selected_frame = 0

            # Notify the canvas to switch to the new frame
            if hasattr(self, "canvas") and self.canvas:
                LOG.debug(f"DEBUG: Switching to new animation '{new_animation_name}', frame 0")
                LOG.debug(f"DEBUG: Animated sprite current animation: {self.canvas.animated_sprite.current_animation}")
                LOG.debug(f"DEBUG: Animated sprite current frame: {self.canvas.animated_sprite.current_frame}")
                self.canvas.show_frame(new_animation_name, 0)
                LOG.debug(f"DEBUG: After switch - current animation: {self.canvas.animated_sprite.current_animation}")
                LOG.debug(f"DEBUG: After switch - current frame: {self.canvas.animated_sprite.current_frame}")
                LOG.debug(f"DEBUG: New frame surface size: {self.canvas.animated_sprite.image.get_size()}")

                # Force the animated sprite to update its surface
                self.canvas.animated_sprite._update_surface_and_mark_dirty()

                # Force the canvas to redraw with the new frame
                self.canvas.dirty = 1
                self.canvas.force_redraw()

    def _delete_animation(self, animation_name: str):
        """Delete an animation (film strip).

        Args:
            animation_name: The name of the animation to delete

        """
        if not hasattr(self, "canvas") or not self.canvas or not hasattr(self.canvas, "animated_sprite"):
            return

        # Check if we have more than one animation
        animations = list(self.canvas.animated_sprite._animations.keys())
        if len(animations) <= 1:
            self.log.warning("Cannot delete the last remaining animation")
            return

        # Remove the animation from the sprite
        if animation_name in self.canvas.animated_sprite._animations:
            # Get the position of the deleted animation before deletion
            all_animations = list(self.canvas.animated_sprite._animations.keys())
            deleted_index = all_animations.index(animation_name)

            # Capture animation data for undo/redo before deletion
            animation_data = None
            if hasattr(self, "film_strip_operation_tracker"):
                # Get the animation data before deletion
                animation = self.canvas.animated_sprite._animations[animation_name]
                animation_data = {
                    "frames": [],
                    "frame_count": len(animation)
                }

                # Capture frame data for each frame in the animation
                for i, frame in enumerate(animation):
                    frame_data = {
                        "width": frame.image.get_width(),
                        "height": frame.image.get_height(),
                        "pixels": frame.pixels.copy() if hasattr(frame, 'pixels') else [],
                        "duration": frame.duration
                    }
                    animation_data["frames"].append(frame_data)

                # Track animation deletion for undo/redo
                self.film_strip_operation_tracker.add_animation_deleted(
                    animation_name, animation_data
                )

            del self.canvas.animated_sprite._animations[animation_name]
            self.log.info(f"Deleted animation: {animation_name} at index {deleted_index}")

            # Switch to the first remaining animation and select the previous frame
            remaining_animations = list(self.canvas.animated_sprite._animations.keys())
            if remaining_animations:
                new_animation = remaining_animations[0]

                # Try to select the previous frame in the remaining animation
                # If the deleted animation had frames, try to select a frame at a similar position
                if hasattr(self, "selected_frame") and self.selected_frame > 0:
                    # Select the previous frame if available
                    target_frame = max(0, self.selected_frame - 1)
                else:
                    # If no previous frame, select the last frame of the remaining animation
                    target_frame = max(0, len(self.canvas.animated_sprite._animations[new_animation]) - 1)

                # Ensure the target frame is within bounds
                max_frame = len(self.canvas.animated_sprite._animations[new_animation]) - 1
                target_frame = min(target_frame, max_frame)

                self.canvas.show_frame(new_animation, target_frame)

                # Update selection state
                self.selected_animation = new_animation
                self.selected_frame = target_frame

                self.log.info(f"Selected frame {target_frame} in animation '{new_animation}' after deleting '{animation_name}'")

                # Recreate film strips to reflect the deletion
                self.log.debug(f"Recreating film strips after animation deletion. Remaining animations: {remaining_animations}")
                self._on_sprite_loaded(self.canvas.animated_sprite)
            else:
                # No remaining animations - clear selection
                self.log.info("No remaining animations after deletion")
                self.selected_animation = None
                self.selected_frame = None

                # Force update of all film strip widgets to ensure they reflect the deletion
                if hasattr(self, "film_strip_sprites") and self.film_strip_sprites:
                    for film_strip_sprite in self.film_strip_sprites.values():
                        if hasattr(film_strip_sprite, "film_strip_widget") and film_strip_sprite.film_strip_widget:
                            # Force the film strip widget to update its layout
                            film_strip_sprite.film_strip_widget.update_layout()
                            film_strip_sprite.film_strip_widget._create_film_tabs()
                            film_strip_sprite.film_strip_widget.mark_dirty()
                            film_strip_sprite.dirty = 1

                # Ensure we show up to 2 strips after deletion
                if len(remaining_animations) <= 2:
                    # If we have 2 or fewer strips, show them all starting from index 0
                    self.film_strip_scroll_offset = 0
                else:
                    # If we deleted the last strip, show the previous 2 strips
                    if deleted_index == len(all_animations) - 1:
                        # We deleted the last strip, show the previous 2 strips
                        self.film_strip_scroll_offset = max(0, len(remaining_animations) - 2)
                    else:
                        # We deleted a strip that wasn't the last, show current and one more
                        self.film_strip_scroll_offset = max(0, deleted_index - 1)

                # Update visibility and scroll arrows
                self._update_film_strip_visibility()
                self._update_scroll_arrows()

                self.log.info(f"Switched to remaining animation: {new_animation}, deleted_index: {deleted_index}, scroll_offset: {self.film_strip_scroll_offset}")

    @staticmethod
    def _finalize_canvas_setup(animated_sprite: AnimatedSprite, options: dict) -> None:
        """Finalize canvas setup and start animation.

        Args:
            animated_sprite: The animated sprite to finalize
            options: Dictionary containing canvas configuration

        """
        # Start the animation after everything is set up
        animated_sprite.play()

        width, height = options.get("size").split("x")
        AnimatedCanvasSprite.WIDTH = int(width)
        AnimatedCanvasSprite.HEIGHT = int(height)

    def _setup_sliders_and_color_well(self) -> None:
        """Set up the color sliders and color well."""
        # First create the sliders
        slider_height = 9
        slider_width = 256
        slider_x = 13  # Moved 3 pixels to the right
        label_width = 32  # Width of the text sprite
        label_padding = 10  # Padding between slider and label
        well_padding = 20  # Padding between labels and color well

        # Create the sliders - positioned so blue slider bottom touches screen bottom
        # Account for bounding box height (slider_height + 4) in positioning
        # Blue slider bottom should be at screen_height - 2 (one pixel up from last visible row)
        bbox_height = slider_height + 4
        blue_slider_y = self.screen_height - slider_height - 2  # Bottom edge at screen_height - 2
        green_slider_y = blue_slider_y - bbox_height  # Use bounding box height for spacing
        red_slider_y = green_slider_y - bbox_height   # Use bounding box height for spacing
        alpha_slider_y = red_slider_y - bbox_height   # Alpha slider above red slider

        # Create text labels for each slider
        label_x = slider_x - 13  # Position labels to the left of sliders (moved 7 pixels right total)
        label_width = 16  # Width for text labels
        label_height = 16  # Height for text labels

        # Alpha slider label
        self.alpha_label = TextSprite(
            text="A",
            x=label_x - 2,  # Move A label 2 pixels left (same as R and G)
            y=alpha_slider_y + (slider_height - label_height) // 2,  # Center vertically with slider
            width=label_width,
            height=label_height,
            background_color=(0, 0, 0, 0),  # Transparent background
            text_color=(255, 255, 255),  # White text
            alpha=0,  # Transparent
            groups=self.all_sprites,
        )
        # Set monospaced font for the label
        from glitchygames.fonts import FontManager
        monospace_config = {"font_name": "Courier", "font_size": 14}
        self.alpha_label.font = FontManager.get_font(font_config=monospace_config)

        # Red slider label
        self.red_label = TextSprite(
            text="R",
            x=label_x - 2,  # Move R label 2 pixels left
            y=red_slider_y + (slider_height - label_height) // 2,  # Center vertically with slider
            width=label_width,
            height=label_height,
            background_color=(0, 0, 0, 0),  # Transparent background
            text_color=(255, 255, 255),  # White text
            alpha=0,  # Transparent
            groups=self.all_sprites,
        )
        # Set monospaced font for the label
        from glitchygames.fonts import FontManager
        monospace_config = {"font_name": "Courier", "font_size": 14}
        self.red_label.font = FontManager.get_font(font_config=monospace_config)

        # Green slider label
        self.green_label = TextSprite(
            text="G",
            x=label_x - 2,  # Move G label 2 pixels left
            y=green_slider_y + (slider_height - label_height) // 2,  # Center vertically with slider
            width=label_width,
            height=label_height,
            background_color=(0, 0, 0, 0),  # Transparent background
            text_color=(255, 255, 255),  # White text
            alpha=0,  # Transparent
            groups=self.all_sprites,
        )
        # Set monospaced font for the label
        self.green_label.font = FontManager.get_font(font_config=monospace_config)

        # Blue slider label
        self.blue_label = TextSprite(
            text="B",
            x=label_x - 1,  # Adjust B label 1 pixel left to align with R and G
            y=blue_slider_y + (slider_height - label_height) // 2,  # Center vertically with slider
            width=label_width,
            height=label_height,
            background_color=(0, 0, 0, 0),  # Transparent background
            text_color=(255, 255, 255),  # White text
            alpha=0,  # Transparent
            groups=self.all_sprites,
        )
        # Set monospaced font for the label
        self.blue_label.font = FontManager.get_font(font_config=monospace_config)

        self.alpha_slider = SliderSprite(
            name="A",
            x=slider_x,
            y=alpha_slider_y,
            width=slider_width,
            height=slider_height,
            parent=self,
            groups=self.all_sprites,
        )

        self.red_slider = SliderSprite(
            name="R",
            x=slider_x,
            y=red_slider_y,
            width=slider_width,
            height=slider_height,
            parent=self,
            groups=self.all_sprites,
        )

        self.green_slider = SliderSprite(
            name="G",
            x=slider_x,
            y=green_slider_y,
            width=slider_width,
            height=slider_height,
            parent=self,
            groups=self.all_sprites,
        )

        self.blue_slider = SliderSprite(
            name="B",
            x=slider_x,
            y=blue_slider_y,
            width=slider_width,
            height=slider_height,
            parent=self,
            groups=self.all_sprites,
        )

        # Create bounding boxes around the sliders for hover effects (initially hidden)
        self.alpha_slider_bbox = BitmappySprite(
            x=slider_x - 2,
            y=alpha_slider_y - 2,
            width=slider_width + 4,
            height=slider_height + 4,
            name="Alpha Slider BBox",
            groups=self.all_sprites,
        )
        # Create transparent surface (no border initially)
        self.alpha_slider_bbox.image = pygame.Surface((slider_width + 4, slider_height + 4), pygame.SRCALPHA)
        self.alpha_slider_bbox.visible = False  # Start hidden

        self.red_slider_bbox = BitmappySprite(
            x=slider_x - 2,
            y=red_slider_y - 2,
            width=slider_width + 4,
            height=slider_height + 4,
            name="Red Slider BBox",
            groups=self.all_sprites,
        )
        # Create transparent surface (no border initially)
        self.red_slider_bbox.image = pygame.Surface((slider_width + 4, slider_height + 4), pygame.SRCALPHA)
        self.red_slider_bbox.visible = False  # Start hidden

        self.green_slider_bbox = BitmappySprite(
            x=slider_x - 2,
            y=green_slider_y - 2,
            width=slider_width + 4,
            height=slider_height + 4,
            name="Green Slider BBox",
            groups=self.all_sprites,
        )
        # Create transparent surface (no border initially)
        self.green_slider_bbox.image = pygame.Surface((slider_width + 4, slider_height + 4), pygame.SRCALPHA)
        self.green_slider_bbox.visible = False  # Start hidden

        self.blue_slider_bbox = BitmappySprite(
            x=slider_x - 2,
            y=blue_slider_y - 2,
            width=slider_width + 4,
            height=slider_height + 4,
            name="Blue Slider BBox",
            groups=self.all_sprites,
        )
        # Create transparent surface (no border initially)
        self.blue_slider_bbox.image = pygame.Surface((slider_width + 4, slider_height + 4), pygame.SRCALPHA)
        self.blue_slider_bbox.visible = False  # Start hidden

        # Update bounding box positions to match new slider positions
        self.alpha_slider_bbox.rect.y = alpha_slider_y - 2
        self.red_slider_bbox.rect.y = red_slider_y - 2
        self.green_slider_bbox.rect.y = green_slider_y - 2
        self.blue_slider_bbox.rect.y = blue_slider_y - 2

        # Create the color well positioned to the right of the text labels
        # Calculate x position to the right of the text labels
        # Text labels are at: slider_x + slider_width + label_padding
        text_label_x = slider_x + slider_width + label_padding
        color_well_x = text_label_x + well_padding  # Add padding after text labels

        # Position colorwell so its top y matches R slider's top y
        # and its bottom y is shorter than blue slider's bottom y
        red_slider_top_y = red_slider_y
        blue_slider_bottom_y = blue_slider_y + slider_height
        color_well_y = red_slider_top_y - 5  # Add some padding above
        color_well_height = (blue_slider_bottom_y - color_well_y) + 2  # 2 pixels taller than B slider's bottom y

        # Calculate canvas right edge position
        if hasattr(self, "canvas") and self.canvas:
            canvas_right_x = self.canvas.pixels_across * self.canvas.pixel_width
        else:
            # Fallback for tests or when canvas isn't initialized yet
            canvas_right_x = self.screen_width - 20
        # Set colorwell width so its right edge aligns with canvas right edge
        color_well_width = canvas_right_x - color_well_x
        # Ensure minimum width to prevent invalid surface creation
        color_well_width = max(color_well_width, 50)
        # Ensure minimum height to prevent invalid surface creation (reduced from 50)
        color_well_height = max(color_well_height, 20)

        self.color_well = ColorWellSprite(
            name="Color Well",
            x=color_well_x,
            y=color_well_y,  # Top y matches R slider's top y
            width=color_well_width,
            height=color_well_height,  # Height spans from R top to G bottom
            parent=self,
            groups=self.all_sprites,
        )

        # Create tab control positioned above the color well
        tab_control_width = min(80, color_well_width) + 1  # Limit width to 80px or color well width, plus 1 pixel
        tab_control_height = 20
        tab_control_x = color_well_x + (color_well_width - tab_control_width) // 2  # Center horizontally
        tab_control_y = color_well_y - tab_control_height  # Position so bottom touches top of color well

        self.tab_control = TabControlSprite(
            name="Format Tab Control",
            x=tab_control_x,
            y=tab_control_y,
            width=tab_control_width,
            height=tab_control_height,
            parent=self,
            groups=self.all_sprites,
        )

        # Initialize slider input format (default to decimal)
        self.slider_input_format = "%d"

        # Update text box widths to fit between slider end and color well start
        text_box_width = color_well_x - text_label_x + 4  # Make 4 pixels wider
        # Shrink text boxes vertically by 4 pixels
        text_box_height = 16  # Original was 20, now 16 (4 pixels smaller)
        self.alpha_slider.text_sprite.width = text_box_width
        self.alpha_slider.text_sprite.height = text_box_height
        self.red_slider.text_sprite.width = text_box_width
        self.red_slider.text_sprite.height = text_box_height
        self.green_slider.text_sprite.width = text_box_width
        self.green_slider.text_sprite.height = text_box_height
        self.blue_slider.text_sprite.width = text_box_width
        self.blue_slider.text_sprite.height = text_box_height
        # Force text sprites to update with new dimensions
        self.alpha_slider.text_sprite.update_text(self.alpha_slider.text_sprite.text)
        self.red_slider.text_sprite.update_text(self.red_slider.text_sprite.text)
        self.green_slider.text_sprite.update_text(self.green_slider.text_sprite.text)
        self.blue_slider.text_sprite.update_text(self.blue_slider.text_sprite.text)


        self.alpha_slider.value = 255
        self.red_slider.value = 0
        self.blue_slider.value = 0
        self.green_slider.value = 0

        self.color_well.active_color = (
            self.red_slider.value,
            self.green_slider.value,
            self.blue_slider.value,
            self.alpha_slider.value,
        )

        if hasattr(self, "canvas") and self.canvas:
            self.canvas.active_color = self.color_well.active_color

    def _setup_debug_text_box(self) -> None:
        """Set up the debug text box and AI label."""
        # Calculate debug text box position and size - align to bottom right corner
        debug_height = 186  # Fixed height for AI chat box

        # Calculate film strip left x position (should be less than color well's right x - 1)
        if hasattr(self, "color_well") and self.color_well:
            film_strip_left_x = self.color_well.rect.right + 1  # Film strip left x = color well right x + 1
        else:
            # Fallback if color well not available
            film_strip_left_x = self.screen_width - 200

        # AI sprite box should be clamped to right side of screen and grow left
        # but not grow left more than the film strip left x
        debug_x = film_strip_left_x  # Start from film strip left x
        debug_width = self.screen_width - debug_x  # Extend to right edge of screen

        # Position below the 2nd film strip if it exists, otherwise clamp to bottom of screen
        if hasattr(self, "film_strips") and self.film_strips and len(self.film_strips) >= 2:
            # Find the bottom of the 2nd film strip
            second_strip_bottom = 0
            # Safely get the second film strip to handle race conditions during sprite loading
            try:
                # Convert to list to safely access by index
                film_strip_list = list(self.film_strips.values())
                if len(film_strip_list) >= 2 and hasattr(film_strip_list[1], "rect"):
                    second_strip_bottom = film_strip_list[1].rect.bottom
            except (IndexError, KeyError, AttributeError):
                # Handle race condition where film strips are in transition
                second_strip_bottom = 0
            debug_y = second_strip_bottom + 30  # 30 pixels below the 2nd strip
            # Ensure it doesn't go above the bottom of the screen
            debug_y = min(debug_y, self.screen_height - debug_height)
        else:
            # Fallback: clamp to bottom of screen
            debug_y = self.screen_height - debug_height

        # Create the AI label
        label_height = 20
        self.ai_label = TextSprite(
            x=debug_x,
            y=debug_y - label_height,  # Position above the text box
            width=debug_width,
            height=label_height,
            text="AI Sprite",
            text_color=(255, 255, 255),  # White text
            background_color=(0, 0, 0),  # Solid black background like color well
            groups=self.all_sprites,
        )

        # Create the debug text box
        self.debug_text = MultiLineTextBox(
            name="Debug Output",
            x=debug_x,
            y=debug_y,
            width=debug_width,
            height=debug_height,
            text="",  # Changed to empty string
            parent=self,  # Pass self as parent
            groups=self.all_sprites,
        )

    def _update_ai_sprite_position(self) -> None:
        """Update AI sprite positioning when canvas changes."""
        if not hasattr(self, "ai_label") or not hasattr(self, "debug_text"):
            return  # AI sprites not initialized yet

        # Calculate new position using same logic as _setup_debug_text_box
        debug_height = 186  # Fixed height for AI chat box

        # Calculate film strip left x position (should be less than color well's right x - 1)
        if hasattr(self, "color_well") and self.color_well:
            film_strip_left_x = self.color_well.rect.right + 1  # Film strip left x = color well right x + 1
        else:
            # Fallback if color well not available
            film_strip_left_x = self.screen_width - 200

        # AI sprite box should be clamped to right side of screen and grow left
        # but not grow left more than the film strip left x
        debug_x = film_strip_left_x  # Start from film strip left x
        debug_width = self.screen_width - debug_x  # Extend to right edge of screen

        # Position below the 2nd film strip if it exists, otherwise clamp to bottom of screen
        if hasattr(self, "film_strips") and self.film_strips and len(self.film_strips) >= 2:
            # Find the bottom of the 2nd film strip
            second_strip_bottom = 0
            # Safely get the second film strip to handle race conditions during sprite loading
            try:
                # Convert to list to safely access by index
                film_strip_list = list(self.film_strips.values())
                if len(film_strip_list) >= 2 and hasattr(film_strip_list[1], "rect"):
                    second_strip_bottom = film_strip_list[1].rect.bottom
            except (IndexError, KeyError, AttributeError):
                # Handle race condition where film strips are in transition
                second_strip_bottom = 0
            debug_y = second_strip_bottom + 30  # 30 pixels below the 2nd strip
            # Ensure it doesn't go above the bottom of the screen
            debug_y = min(debug_y, self.screen_height - debug_height)
        else:
            # Fallback: clamp to bottom of screen
            debug_y = self.screen_height - debug_height

        # Update AI label position
        self.ai_label.rect.x = debug_x
        self.ai_label.rect.y = debug_y - 20  # Position above the text box
        self.ai_label.rect.width = debug_width
        self.ai_label.rect.height = 20

        # Update debug text position
        self.debug_text.rect.x = debug_x
        self.debug_text.rect.y = debug_y
        self.debug_text.rect.width = debug_width
        self.debug_text.rect.height = debug_height

    def _setup_voice_recognition(self) -> None:
        """Set up voice recognition for voice commands."""
        try:
            self.voice_manager = VoiceRecognitionManager(logger=self.log)

            if self.voice_manager.is_available():
                # Register voice commands
                self.voice_manager.register_command(
                    "clear the ai sprite box",
                    self._clear_ai_sprite_box
                )
                self.voice_manager.register_command(
                    "clear ai sprite box",
                    self._clear_ai_sprite_box
                )
                self.voice_manager.register_command(
                    "clear ai box",
                    self._clear_ai_sprite_box
                )
                # Add commands for what speech recognition actually hears
                self.voice_manager.register_command(
                    "clear the ai sprite",
                    self._clear_ai_sprite_box
                )
                self.voice_manager.register_command(
                    "clear ai sprite",
                    self._clear_ai_sprite_box
                )
                # Add command for "window" variation
                self.voice_manager.register_command(
                    "clear the ai sprite window",
                    self._clear_ai_sprite_box
                )
                self.voice_manager.register_command(
                    "clear ai sprite window",
                    self._clear_ai_sprite_box
                )

                # Start listening for voice commands
                self.voice_manager.start_listening()
                self.log.info("Voice recognition initialized and started")
            else:
                self.log.warning("Voice recognition not available - microphone not found")
                self.voice_manager = None

        except Exception as e:
            self.log.error(f"Failed to initialize voice recognition: {e}")
            self.voice_manager = None

    def _clear_ai_sprite_box(self) -> None:
        """Clear the AI sprite text box."""
        if hasattr(self, "debug_text") and self.debug_text:
            self.debug_text.text = ""
            self.log.info("AI sprite box cleared via voice command")
        else:
            self.log.warning("Cannot clear AI sprite box - debug_text not available")

    def _is_mouse_in_film_strip_area(self, mouse_pos: tuple[int, int]) -> bool:
        """Check if mouse position is within the film strip area.

        Args:
            mouse_pos: (x, y) mouse position

        Returns:
            True if mouse is in film strip area, False otherwise

        """
        if not hasattr(self, "film_strip_sprites") or not self.film_strip_sprites:
            self.log.debug(f"No film strip sprites available for mouse pos {mouse_pos}")
            return False

        # Check if mouse is within any film strip sprite bounds
        for anim_name, film_strip_sprite in self.film_strip_sprites.items():
            if film_strip_sprite.rect.collidepoint(mouse_pos):
                self.log.debug(f"Mouse {mouse_pos} is in film strip '{anim_name}' at {film_strip_sprite.rect}")
                return True

        self.log.debug(f"Mouse {mouse_pos} is not in any film strip area")
        return False

    def _handle_film_strip_drag_scroll(self, mouse_y: int) -> None:
        """Handle mouse drag scrolling for film strips.

        Args:
            mouse_y: Current mouse Y position

        """
        if not self.is_dragging_film_strips or self.film_strip_drag_start_y is None:
            self.log.debug("Not dragging film strips or no start Y")
            return

        # Calculate drag distance
        drag_distance = mouse_y - self.film_strip_drag_start_y
        self.log.debug(f"Drag distance: {drag_distance}, start Y: {self.film_strip_drag_start_y}, current Y: {mouse_y}")

        # Convert drag distance to scroll offset change
        # Each film strip is approximately 100 pixels tall, so we scroll by 1 for every 100 pixels
        strip_height = 100
        scroll_change = int(drag_distance / strip_height)

        # Calculate new scroll offset
        new_offset = self.film_strip_drag_start_offset + scroll_change

        # Clamp to valid range
        if hasattr(self, "canvas") and self.canvas and hasattr(self.canvas, "animated_sprite") and self.canvas.animated_sprite:
            total_animations = len(self.canvas.animated_sprite._animations)
            max_scroll = max(0, total_animations - self.max_visible_strips)
            new_offset = max(0, min(new_offset, max_scroll))
            self.log.debug(f"Scroll change: {scroll_change}, new offset: {new_offset}, max scroll: {max_scroll}")

        # Update scroll offset if it changed
        if new_offset != self.film_strip_scroll_offset:
            self.log.debug(f"Updating scroll offset from {self.film_strip_scroll_offset} to {new_offset}")
            self.film_strip_scroll_offset = new_offset
            self._update_film_strip_visibility()
            self._update_scroll_arrows()
        else:
            self.log.debug("No scroll offset change needed")

    def _setup_film_strips(self) -> None:
        """Set up film strips for the current animated sprite."""
        # Initialize film strip storage
        self.film_strips = {}
        self.film_strip_sprites = {}

        # Create film strips if we have an animated sprite
        LOG.debug(f"DEBUG: Checking conditions for _create_film_strips")
        LOG.debug(f"DEBUG: hasattr(canvas): {hasattr(self, 'canvas')}")
        if hasattr(self, "canvas"):
            LOG.debug(f"DEBUG: self.canvas: {self.canvas}")
            if self.canvas:
                LOG.debug(f"DEBUG: hasattr(animated_sprite): {hasattr(self.canvas, 'animated_sprite')}")
                if hasattr(self.canvas, "animated_sprite"):
                    LOG.debug(f"DEBUG: self.canvas.animated_sprite: {self.canvas.animated_sprite}")
                    if self.canvas.animated_sprite:
                        LOG.debug(f"DEBUG: hasattr(_animations): {hasattr(self.canvas.animated_sprite, '_animations')}")
                        if hasattr(self.canvas.animated_sprite, "_animations"):
                            LOG.debug(f"DEBUG: _animations: {self.canvas.animated_sprite._animations}")
        if hasattr(self, "canvas") and self.canvas and hasattr(self.canvas, "animated_sprite") and self.canvas.animated_sprite and self.canvas.animated_sprite._animations:
            LOG.debug(f"DEBUG: About to call _create_film_strips (first call)")
            self._create_film_strips(self.all_sprites)
            LOG.debug(f"DEBUG: Finished calling _create_film_strips (first call)")

        # Set up parent scene reference for canvas
        if hasattr(self, "canvas") and self.canvas:
            self.canvas.parent_scene = self

    def _on_sprite_loaded(self, loaded_sprite: AnimatedSprite) -> None:
        """Handle when a new sprite is loaded - recreate film strips."""
        self.log.debug("=== _on_sprite_loaded called ===")
        LOG.debug(f"DEBUG: _on_sprite_loaded called with sprite: {loaded_sprite}")
        LOG.debug(f"DEBUG: Sprite has animations: {hasattr(loaded_sprite, '_animations')}")
        if hasattr(loaded_sprite, '_animations'):
            LOG.debug(f"DEBUG: Sprite animations: {list(loaded_sprite._animations.keys())}")

        # Preserve controller selections before clearing film strips
        preserved_controller_selections = {}
        if hasattr(self, "controller_selections"):
            for controller_id, controller_selection in self.controller_selections.items():
                if controller_selection.is_active():
                    animation, frame = controller_selection.get_selection()
                    preserved_controller_selections[controller_id] = (animation, frame)

        # Store preserved selections for use in _create_film_strips
        self._preserved_controller_selections = preserved_controller_selections

        # Clear existing film strips
        LOG.debug(f"DEBUG: Checking film_strips - hasattr: {hasattr(self, 'film_strips')}")
        if hasattr(self, "film_strips") and self.film_strips:
            self.log.debug(f"Clearing {len(self.film_strips)} existing film strips")
            LOG.debug(f"DEBUG: Clearing {len(self.film_strips)} existing film strips")
            for film_strip_sprite in self.film_strip_sprites.values():
                film_strip_sprite.kill()
            self.film_strips.clear()
            self.film_strip_sprites.clear()

        # Create new film strips for the loaded sprite
        if loaded_sprite and loaded_sprite._animations:
            self.log.debug(f"Creating new film strips for loaded sprite with {len(loaded_sprite._animations)} animations")
            LOG.debug(f"DEBUG: _on_sprite_loaded recreating {len(loaded_sprite._animations)} film strips")

            # Update the canvas to use the loaded sprite's animations
            if hasattr(self, "canvas") and self.canvas:
                self.canvas.animated_sprite = loaded_sprite

                # Check if canvas needs resizing and resize if necessary
                self.canvas._check_and_resize_canvas(loaded_sprite)

                # Set the canvas to show the first frame of the first animation
                first_animation = list(loaded_sprite._animations.keys())[0]
                self.canvas.current_animation = first_animation
                self.canvas.current_frame = 0

                # Update the canvas interface to sync with the new sprite
                self.canvas.canvas_interface.set_current_frame(first_animation, 0)

                # Force the canvas to redraw with the new sprite
                self.canvas.force_redraw()

                # Note: The loaded sprite will be configured to play by the film strip widgets
                # The canvas should remain static for editing

                # Initialize pixels if needed (for mock sprites)
                self.log.debug(f"Checking canvas pixels: has_pixels={hasattr(self.canvas, 'pixels')}, is_list={isinstance(getattr(self.canvas, 'pixels', None), list)}")
                if not hasattr(self.canvas, "pixels") or not isinstance(self.canvas.pixels, list):
                    self.log.debug("Initializing canvas pixels")
                    # Create a blank pixel array
                    pixel_count = self.canvas.pixels_across * self.canvas.pixels_tall
                    self.canvas.pixels = [(255, 0, 255, 255)] * pixel_count  # Magenta background
                    self.canvas.dirty_pixels = [True] * pixel_count
                    self.log.debug(f"Canvas pixels initialized: len={len(self.canvas.pixels)}")

            LOG.debug(f"DEBUG: About to call _create_film_strips (second call)")
            self._create_film_strips(self.all_sprites)
            LOG.debug(f"DEBUG: Finished calling _create_film_strips (second call)")
            self.log.debug("Film strips created for loaded sprite")

            # Initialize global selection to first frame of first animation
            first_animation = list(loaded_sprite._animations.keys())[0]
            self.selected_animation = first_animation
            self.selected_frame = 0
            self.selected_strip = None  # Will be set when first frame is selected
        else:
            self.log.debug("No animations found in loaded sprite")

    def _on_film_strip_frame_selected(self, film_strip_widget, animation, frame):
        """Handle frame selection in a film strip."""
        # Find the strip name by looking up the film_strip_widget in film_strips
        strip_name = "unknown"
        if hasattr(self, "film_strips") and self.film_strips:
            for name, strip in self.film_strips.items():
                if strip == film_strip_widget:
                    strip_name = name
                    break
        LOG.debug(f"BitmapEditorScene: Frame selected - {animation}[{frame}] in strip '{strip_name}'")

        # Update canvas to show the selected frame
        if hasattr(self, "canvas") and self.canvas:
            LOG.debug(f"BitmapEditorScene: Updating canvas to show {animation}[{frame}]")
            self.canvas.show_frame(animation, frame)

        # Store global selection state
        self.selected_animation = animation
        self.selected_frame = frame

        # Update keyboard selection in all film strips using SelectionManager
        # OLD SYSTEM REMOVED - Using new multi-controller system instead
        # OLD SYSTEM DISABLED - Using new multi-controller system instead
        # The old SelectionManager system has been replaced by the new multi-controller system
        # Update film strip selection state
        self._update_film_strip_selection_state()
        self.selected_strip = film_strip_widget

        # OLD SYSTEM REMOVED - Using new multi-controller system instead

        # Mark all film strips as dirty so they redraw with correct selection state
        if hasattr(self, "film_strips") and self.film_strips:
            for strip_name, strip_widget in self.film_strips.items():
                strip_widget.mark_dirty()
                # Mark the film strip sprite as dirty=2 for full surface blit
                if hasattr(self, "film_strip_sprites") and strip_name in self.film_strip_sprites:
                    self.film_strip_sprites[strip_name].dirty = 2

                # Mark the animated sprite as dirty to ensure animation updates
                if hasattr(strip_widget, "animated_sprite") and strip_widget.animated_sprite:
                    strip_widget.animated_sprite.dirty = 2

    def _on_frame_inserted(self, animation: str, frame_index: int) -> None:
        """Handle when a new frame is inserted into an animation.

        Args:
            animation: The animation name where the frame was inserted
            frame_index: The index where the frame was inserted

        """
        LOG.debug(f"BitmapEditorScene: Frame inserted at {animation}[{frame_index}]")

        # Update canvas to show the new frame if it's the current animation
        if hasattr(self, "canvas") and self.canvas and self.selected_animation == animation:
            LOG.debug(f"BitmapEditorScene: Updating canvas to show new frame {animation}[{frame_index}]")
            self.canvas.show_frame(animation, frame_index)
            self.selected_frame = frame_index

        # Update the selected_frame in the film strip widget for the current animation
        if hasattr(self, "film_strips") and self.film_strips:
            for strip_name, strip_widget in self.film_strips.items():
                if strip_name == animation:
                    # Update the selected_frame in the film strip widget
                    strip_widget.selected_frame = frame_index
                    LOG.debug(f"BitmapEditorScene: Updated film strip {strip_name} selected_frame to {frame_index}")

                strip_widget.mark_dirty()
                # Mark the film strip sprite as dirty=2 for full surface blit
                if hasattr(self, "film_strip_sprites") and strip_name in self.film_strip_sprites:
                    self.film_strip_sprites[strip_name].dirty = 2

                # Mark the animated sprite as dirty to ensure animation updates
                if hasattr(strip_widget, "animated_sprite") and strip_widget.animated_sprite:
                    strip_widget.animated_sprite.dirty = 2

    def _on_frame_removed(self, animation: str, frame_index: int) -> None:
        """Handle when a frame is removed from an animation.

        Args:
            animation: The animation name where the frame was removed
            frame_index: The index where the frame was removed

        """
        LOG.debug(f"BitmapEditorScene: Frame removed at {animation}[{frame_index}]")

        # Adjust selected frame if necessary
        if hasattr(self, "selected_animation") and self.selected_animation == animation:
            if hasattr(self, "selected_frame") and self.selected_frame >= frame_index:
                # If we removed a frame before or at the current position, adjust the selected frame
                if self.selected_frame > 0:
                    self.selected_frame -= 1
                else:
                    # If we were at frame 0 and removed it, stay at frame 0 (which is now the next frame)
                    self.selected_frame = 0

                # Ensure the selected frame is within bounds
                if hasattr(self, "canvas") and self.canvas and hasattr(self.canvas, "animated_sprite"):
                    if animation in self.canvas.animated_sprite._animations:
                        max_frame = len(self.canvas.animated_sprite._animations[animation]) - 1
                        if self.selected_frame > max_frame:
                            self.selected_frame = max(0, max_frame)

                # Update canvas to show the adjusted frame
                if hasattr(self, "canvas") and self.canvas:
                    LOG.debug(f"BitmapEditorScene: Updating canvas to show adjusted frame {animation}[{self.selected_frame}]")
                    try:
                        self.canvas.show_frame(animation, self.selected_frame)
                    except (IndexError, KeyError) as e:
                        LOG.debug(f"BitmapEditorScene: Error updating canvas: {e}")
                        # Fallback to frame 0 if there's an error
                        self.selected_frame = 0
                        if animation in self.canvas.animated_sprite._animations and len(self.canvas.animated_sprite._animations[animation]) > 0:
                            self.canvas.show_frame(animation, 0)

        # Update the selected_frame in the film strip widget for the current animation
        if hasattr(self, "film_strips") and self.film_strips:
            for strip_name, strip_widget in self.film_strips.items():
                if strip_name == animation:
                    # Update the selected_frame in the film strip widget
                    strip_widget.selected_frame = self.selected_frame if hasattr(self, "selected_frame") else 0
                    LOG.debug(f"BitmapEditorScene: Updated film strip {strip_name} selected_frame to {strip_widget.selected_frame}")

                strip_widget.mark_dirty()
                # Mark the film strip sprite as dirty=2 for full surface blit
                if hasattr(self, "film_strip_sprites") and strip_name in self.film_strip_sprites:
                    self.film_strip_sprites[strip_name].dirty = 2

                # Mark the animated sprite as dirty to ensure animation updates
                if hasattr(strip_widget, "animated_sprite") and strip_widget.animated_sprite:
                    strip_widget.animated_sprite.dirty = 2

    def on_key_down_event(self, event):
        """Handle keyboard events for copy/paste functionality."""
        LOG.debug(f"BitmapEditorScene: on_key_down_event called with key={event.key}, mod={event.get('mod', 0)}")

        # Check for Ctrl+C (copy) - handle this BEFORE calling parent method
        if event.key == pygame.K_c and (event.get('mod', 0) & pygame.KMOD_CTRL):
            LOG.debug("BitmapEditorScene: [SCENE HANDLER] Ctrl+C detected - copying current frame")
            LOG.debug(f"BitmapEditorScene: [SCENE HANDLER] Current selected_animation: {getattr(self, 'selected_animation', 'None')}")
            LOG.debug(f"BitmapEditorScene: [SCENE HANDLER] Current selected_frame: {getattr(self, 'selected_frame', 'None')}")
            success = self._copy_current_frame()
            if success:
                LOG.debug("BitmapEditorScene: [SCENE HANDLER] Frame copied successfully")
            else:
                LOG.debug("BitmapEditorScene: [SCENE HANDLER] Failed to copy frame")
            return True

        # Check for Ctrl+V (paste) - handle this BEFORE calling parent method
        if event.key == pygame.K_v and (event.get('mod', 0) & pygame.KMOD_CTRL):
            LOG.debug("BitmapEditorScene: [SCENE HANDLER] Ctrl+V detected - pasting to current frame")
            LOG.debug(f"BitmapEditorScene: [SCENE HANDLER] Current selected_animation: {getattr(self, 'selected_animation', 'None')}")
            LOG.debug(f"BitmapEditorScene: [SCENE HANDLER] Current selected_frame: {getattr(self, 'selected_frame', 'None')}")
            success = self._paste_to_current_frame()
            if success:
                LOG.debug("BitmapEditorScene: [SCENE HANDLER] Frame pasted successfully")
            else:
                LOG.debug("BitmapEditorScene: [SCENE HANDLER] Failed to paste frame")
            return True

        # Call the parent method for other keyboard events
        return super().on_key_down_event(event)

    def _copy_current_frame(self) -> bool:
        """Copy the currently selected frame from the active film strip."""
        LOG.debug("BitmapEditorScene: [SCENE COPY] _copy_current_frame called")

        if not hasattr(self, "film_strips") or not self.film_strips:
            LOG.debug("BitmapEditorScene: [SCENE COPY] No film strips available for copying")
            return False

        LOG.debug(f"BitmapEditorScene: [SCENE COPY] Found {len(self.film_strips)} film strips")
        LOG.debug(f"BitmapEditorScene: [SCENE COPY] Looking for animation: {getattr(self, 'selected_animation', 'None')}")

        # Find the active film strip (the one with the current animation)
        active_film_strip = None
        if hasattr(self, "selected_animation") and self.selected_animation:
            for strip_name, film_strip in self.film_strips.items():
                LOG.debug(f"BitmapEditorScene: [SCENE COPY] Checking film strip '{strip_name}' with animation '{getattr(film_strip, 'current_animation', 'None')}'")
                if (hasattr(film_strip, "current_animation") and
                    film_strip.current_animation == self.selected_animation):
                    active_film_strip = film_strip
                    LOG.debug(f"BitmapEditorScene: [SCENE COPY] Found active film strip: '{strip_name}'")
                    break

        if not active_film_strip:
            LOG.debug("BitmapEditorScene: [SCENE COPY] No active film strip found for copying")
            return False

        LOG.debug("BitmapEditorScene: [SCENE COPY] Calling film strip copy method")
        # Call the film strip's copy method
        return active_film_strip.copy_current_frame()

    def _paste_to_current_frame(self) -> bool:
        """Paste the copied frame to the currently selected frame in the active film strip."""
        LOG.debug("BitmapEditorScene: [SCENE PASTE] _paste_to_current_frame called")

        if not hasattr(self, "film_strips") or not self.film_strips:
            LOG.debug("BitmapEditorScene: [SCENE PASTE] No film strips available for pasting")
            return False

        LOG.debug(f"BitmapEditorScene: [SCENE PASTE] Found {len(self.film_strips)} film strips")
        LOG.debug(f"BitmapEditorScene: [SCENE PASTE] Looking for animation: {getattr(self, 'selected_animation', 'None')}")

        # Find the active film strip (the one with the current animation)
        active_film_strip = None
        if hasattr(self, "selected_animation") and self.selected_animation:
            for strip_name, film_strip in self.film_strips.items():
                LOG.debug(f"BitmapEditorScene: [SCENE PASTE] Checking film strip '{strip_name}' with animation '{getattr(film_strip, 'current_animation', 'None')}'")
                if (hasattr(film_strip, "current_animation") and
                    film_strip.current_animation == self.selected_animation):
                    active_film_strip = film_strip
                    LOG.debug(f"BitmapEditorScene: [SCENE PASTE] Found active film strip: '{strip_name}'")
                    break

        if not active_film_strip:
            LOG.debug("BitmapEditorScene: [SCENE PASTE] No active film strip found for pasting")
            return False

        LOG.debug("BitmapEditorScene: [SCENE PASTE] Calling film strip paste method")
        # Call the film strip's paste method
        return active_film_strip.paste_to_current_frame()

    def _update_film_strip_selection_state(self):
        """Update the selection state of all film strips based on current selection."""
        if not hasattr(self, "film_strips") or not self.film_strips:
            return

        current_animation = getattr(self, "selected_animation", "")
        current_frame = getattr(self, "selected_frame", 0)

        for strip_name, strip_widget in self.film_strips.items():
            # Each film strip should have its current_animation set to its own animation name
            # for proper sprocket rendering
            strip_widget.current_animation = strip_name

            if strip_name == current_animation:
                # This is the selected strip - mark it as selected
                strip_widget.is_selected = True
                strip_widget.selected_frame = current_frame
                LOG.debug(f"BitmapEditorScene: Marking strip {strip_name} as selected with frame {current_frame}")
            else:
                # This is not the selected strip - deselect it but preserve its selected_frame
                strip_widget.is_selected = False
                # Don't reset selected_frame - each strip maintains its own selection
                LOG.debug(f"BitmapEditorScene: Deselecting strip {strip_name} (preserving selected_frame={strip_widget.selected_frame})")

            # Mark the strip as dirty to trigger full redraw
            strip_widget.mark_dirty()
            # Also mark the film strip sprite as dirty=2 for full surface blit
            if hasattr(self, "film_strip_sprites") and strip_name in self.film_strip_sprites:
                self.film_strip_sprites[strip_name].dirty = 2

            # Mark the animated sprite as dirty to ensure animation updates
            if hasattr(strip_widget, "animated_sprite") and strip_widget.animated_sprite:
                strip_widget.animated_sprite.dirty = 2

    def _switch_to_film_strip(self, animation_name: str, frame: int = 0):
        """Switch to a specific film strip and frame, deselecting the previous one."""
        LOG.debug(f"BitmapEditorScene: Switching to film strip {animation_name}[{frame}]")

        # Deselect the current strip if there is one
        if hasattr(self, "selected_strip") and self.selected_strip:
            LOG.debug("BitmapEditorScene: Deselecting current strip")
            self.selected_strip.is_selected = False
            self.selected_strip.current_animation = ""
            self.selected_strip.current_frame = 0
            self.selected_strip.mark_dirty()
            # Mark the film strip sprite as dirty=2 for full surface blit
            if hasattr(self, "film_strip_sprites"):
                for strip_name, strip_sprite in self.film_strip_sprites.items():
                    if strip_sprite.film_strip_widget == self.selected_strip:
                        strip_sprite.dirty = 2
                        break

            # Mark the animated sprite as dirty to ensure animation updates
            if hasattr(self.selected_strip, "animated_sprite") and self.selected_strip.animated_sprite:
                self.selected_strip.animated_sprite.dirty = 2

        # Select the new strip
        if hasattr(self, "film_strips") and animation_name in self.film_strips:
            new_strip = self.film_strips[animation_name]
            new_strip.is_selected = True
            # Set current_animation to the strip's own animation name for sprocket rendering
            new_strip.current_animation = animation_name
            new_strip.current_frame = frame
            new_strip.mark_dirty()

            # Mark the new film strip sprite as dirty=2 for full surface blit
            if hasattr(self, "film_strip_sprites") and animation_name in self.film_strip_sprites:
                self.film_strip_sprites[animation_name].dirty = 2

            # Mark the animated sprite as dirty to ensure animation updates
            if hasattr(new_strip, "animated_sprite") and new_strip.animated_sprite:
                new_strip.animated_sprite.dirty = 2

            # Update global selection state
            self.selected_animation = animation_name
            self.selected_frame = frame
            self.selected_strip = new_strip

            # Update canvas to show the selected frame
            if hasattr(self, "canvas") and self.canvas:
                self.canvas.show_frame(animation_name, frame)

            LOG.debug(f"BitmapEditorScene: Selected strip {animation_name} with frame {frame}")
        else:
            LOG.debug(f"BitmapEditorScene: Film strip {animation_name} not found")

    def _scroll_to_current_animation(self):
        """Scroll the film strip view to show the currently selected animation if it's not visible."""
        if not hasattr(self, "canvas") or not self.canvas or not hasattr(self.canvas, "animated_sprite"):
            return

        # Get the current animation name
        current_animation = self.canvas.current_animation
        if not current_animation:
            return

        # Get all animation names in order
        animation_names = list(self.canvas.animated_sprite._animations.keys())
        if current_animation not in animation_names:
            return

        # Find the index of the current animation
        current_index = animation_names.index(current_animation)

        # Calculate the scroll offset needed to show this animation
        # We want to show the current animation in the visible area
        if current_index < self.film_strip_scroll_offset:
            # Current animation is above the visible area, scroll up
            self.film_strip_scroll_offset = current_index
            self.log.debug(f"Scrolling up to show animation {current_animation} at index {current_index}")
        elif current_index >= self.film_strip_scroll_offset + self.max_visible_strips:
            # Current animation is below the visible area, scroll down
            self.film_strip_scroll_offset = current_index - self.max_visible_strips + 1
            self.log.debug(f"Scrolling down to show animation {current_animation} at index {current_index}")
        else:
            # Current animation is already visible, no scrolling needed
            self.log.debug(f"Animation {current_animation} is already visible at index {current_index}")
            return

        # Update visibility and scroll arrows
        self._update_film_strip_visibility()
        self._update_scroll_arrows()

        # Update the film strip selection to show the current frame
        self._update_film_strip_selection()

    def scroll_film_strips_up(self):
        """Scroll film strips up (show earlier animations)."""
        if hasattr(self, "film_strip_scroll_offset") and self.film_strip_scroll_offset > 0:
            self.film_strip_scroll_offset -= 1
            self._update_film_strip_visibility()

    def _select_first_visible_film_strip(self):
        """Select the first visible film strip and set its frame 0 as active."""
        if not hasattr(self, "film_strips") or not self.film_strips:
            return

        # Get all animation names in order
        if hasattr(self, "canvas") and self.canvas and hasattr(self.canvas, "animated_sprite"):
            animation_names = list(self.canvas.animated_sprite._animations.keys())
        else:
            animation_names = list(self.film_strips.keys())

        # Find the first visible animation
        start_index = self.film_strip_scroll_offset
        if start_index < len(animation_names):
            first_visible_animation = animation_names[start_index]

            # Select this animation and frame 0
            if hasattr(self, "canvas") and self.canvas:
                self.canvas.show_frame(first_visible_animation, 0)

            # Update the film strip widget to show the correct frame selection
            if first_visible_animation in self.film_strips:
                film_strip_widget = self.film_strips[first_visible_animation]
                film_strip_widget.set_current_frame(first_visible_animation, 0)

            # Update global selection state
            self.selected_animation = first_visible_animation
            self.selected_frame = 0

            # Mark all film strips as dirty so they redraw with correct selection state
            if hasattr(self, "film_strips") and self.film_strips:
                for strip_name, strip_widget in self.film_strips.items():
                    strip_widget.mark_dirty()

    def scroll_film_strips_down(self):
        """Scroll film strips down (show later animations)."""
        if hasattr(self, "canvas") and self.canvas and hasattr(self.canvas, "animated_sprite"):
            total_animations = len(self.canvas.animated_sprite._animations)
            max_scroll = max(0, total_animations - self.max_visible_strips)

            # Check if there are more strips below that we can scroll to
            if hasattr(self, "film_strip_scroll_offset") and self.film_strip_scroll_offset < max_scroll:
                self.film_strip_scroll_offset += 1
                self._update_film_strip_visibility()

    def _select_last_visible_film_strip(self):
        """Select the last visible film strip and set its frame 0 as active."""
        if not hasattr(self, "film_strips") or not self.film_strips:
            return

        # Get all animation names in order
        if hasattr(self, "canvas") and self.canvas and hasattr(self.canvas, "animated_sprite"):
            animation_names = list(self.canvas.animated_sprite._animations.keys())
        else:
            animation_names = list(self.film_strips.keys())

        # Find the last visible animation
        start_index = self.film_strip_scroll_offset
        end_index = min(start_index + self.max_visible_strips, len(animation_names))

        if end_index > start_index:
            last_visible_animation = animation_names[end_index - 1]

            # Select this animation and frame 0
            if hasattr(self, "canvas") and self.canvas:
                self.canvas.show_frame(last_visible_animation, 0)

            # Update the film strip widget to show the correct frame selection
            if last_visible_animation in self.film_strips:
                film_strip_widget = self.film_strips[last_visible_animation]
                film_strip_widget.set_current_frame(last_visible_animation, 0)

            # Update global selection state
            self.selected_animation = last_visible_animation
            self.selected_frame = 0

            # Mark all film strips as dirty so they redraw with correct selection state
            if hasattr(self, "film_strips") and self.film_strips:
                for strip_name, strip_widget in self.film_strips.items():
                    strip_widget.mark_dirty()

    def _update_film_strips_for_frame(self, animation: str, frame: int) -> None:
        """Update film strips when frame changes."""
        self.log.debug(f"_update_film_strips_for_frame called: animation={animation}, frame={frame}")
        if hasattr(self, "film_strips") and self.film_strips:
            self.log.debug(f"Found {len(self.film_strips)} film strips: {list(self.film_strips.keys())}")
            # Update the film strip for the current animation
            if animation in self.film_strips:
                film_strip = self.film_strips[animation]
                self.log.debug(f"Updating film strip for animation {animation}")
                # Directly update the selection without triggering handlers to avoid infinite loops
                film_strip.current_animation = animation
                film_strip.current_frame = frame
                film_strip.update_scroll_for_frame(frame)
                film_strip.update_layout()
                film_strip.mark_dirty()
                self.log.debug(f"Film strip updated: current_animation={film_strip.current_animation}, current_frame={film_strip.current_frame}")
            else:
                self.log.debug(f"Animation {animation} not found in film strips")

            # Mark all film strip sprites as dirty
            if hasattr(self, "film_strip_sprites") and self.film_strip_sprites:
                for film_strip_sprite in self.film_strip_sprites.values():
                    film_strip_sprite.dirty = 1

    def _update_film_strips_for_pixel_update(self) -> None:
        """Update film strips when pixel data changes."""
        if hasattr(self, "film_strip_sprites") and self.film_strip_sprites:
            for film_strip_sprite in self.film_strip_sprites.values():
                film_strip_sprite.dirty = 1
        if hasattr(self, "film_strips") and self.film_strips:
            for film_strip in self.film_strips.values():
                film_strip.mark_dirty()

        # Film strip animated sprites should use original animation frames, not canvas content

    def _update_film_strips_for_animated_sprite_update(self) -> None:
        """Update film strips when animated sprite frame data changes."""
        if hasattr(self, "film_strips") and self.film_strips:
            for film_strip in self.film_strips.values():
                film_strip.update_layout()
                film_strip.mark_dirty()
        if hasattr(self, "film_strip_sprites") and self.film_strip_sprites:
            for film_strip_sprite in self.film_strip_sprites.values():
                film_strip_sprite.dirty = 1

        # Also mark film strip sprites as dirty for animation updates
        self._mark_film_strip_sprites_dirty()

    def _mark_film_strip_sprites_dirty(self) -> None:
        """Mark all film strip sprites as dirty for animation updates.

        This is a backup mechanism to ensure film strip sprites are marked as dirty
        when animations are running. The primary dirty marking happens in the
        FilmStripSprite.update() method, but this provides an additional safety net.

        DEBUGGING NOTES:
        - If film strips don't redraw: Check that this method is being called
        - If animations are choppy: Verify dirty flag is being set consistently
        - If performance is poor: Consider reducing frequency of this call
        """
        if hasattr(self, "film_strip_sprites") and self.film_strip_sprites:
            for film_strip_sprite in self.film_strip_sprites.values():
                film_strip_sprite.dirty = 1


    def _update_film_strip_selection(self) -> None:
        """Update film strip selection to show the current animation and frame."""
        if not hasattr(self, "canvas") or not self.canvas:
            return

        # Get the current animation and frame
        current_animation = self.canvas.current_animation
        current_frame = self.canvas.current_frame

        # Update all film strips
        if hasattr(self, "film_strips") and self.film_strips:
            for strip_name, strip_widget in self.film_strips.items():
                if strip_name == current_animation:
                    # This is the current animation - set it as selected
                    strip_widget.set_current_frame(current_animation, current_frame)
                    # Call the selection handler to update the scene state
                    self._on_film_strip_frame_selected(strip_widget, current_animation, current_frame)
                else:
                    # This is not the current animation - clear selection
                    strip_widget.current_animation = ""
                    strip_widget.current_frame = 0
                    strip_widget.mark_dirty()

    def __init__(self, options: dict, groups: pygame.sprite.LayeredDirty | None = None) -> None:
        """Initialize the Bitmap Editor Scene.

        Args:
            options: Dictionary of configuration options for the scene.
            groups: Optional pygame sprite groups for sprite management.

        Returns:
            None

        Raises:
            None

        """
        if options is None:
            options = {}

        # Set default size if not provided
        if "size" not in options:
            options["size"] = "32x32"  # Default canvas size

        super().__init__(options=options, groups=groups)

        # Initialize film strip scrolling attributes
        self.film_strip_scroll_offset = 0
        self.max_visible_strips = 2

        # Initialize scroll arrows
        self.scroll_up_arrow = None

        # Initialize mouse drag scrolling state
        self.film_strip_drag_start_y = None
        self.film_strip_drag_start_offset = None
        self.is_dragging_film_strips = False

        # Initialize selection state for multi-selection system
        self.selected_animation = ""
        self.selected_frame = 0

        # OLD SYSTEM REMOVED - Using new multi-controller system instead

        # Debug state tracking to prevent redundant logging
        self._last_debug_controller_animation = ""
        self._last_debug_controller_frame = -1
        self._last_debug_keyboard_animation = ""
        self._last_debug_keyboard_frame = -1

        # Initialize multi-controller system
        self.multi_controller_manager = MultiControllerManager()
        self.controller_selections: Dict[int, ControllerSelection] = {}

        # Initialize mode switching system
        from glitchygames.tools.controller_mode_system import ModeSwitcher

        # Initialize undo/redo system
        self.undo_redo_manager = UndoRedoManager(max_history=50)
        self.canvas_operation_tracker = CanvasOperationTracker(self.undo_redo_manager)
        self.film_strip_operation_tracker = FilmStripOperationTracker(self.undo_redo_manager)
        self.cross_area_operation_tracker = CrossAreaOperationTracker(self.undo_redo_manager)
        from glitchygames.tools.operation_history import ControllerPositionOperationTracker
        self.controller_position_operation_tracker = ControllerPositionOperationTracker(self.undo_redo_manager)

        # Set up pixel change callback for undo/redo
        self.undo_redo_manager.set_pixel_change_callback(self._apply_pixel_change_for_undo_redo)

        # Set up film strip operation callbacks for undo/redo
        self.undo_redo_manager.set_film_strip_callbacks(
            add_frame_callback=self._add_frame_for_undo_redo,
            delete_frame_callback=self._delete_frame_for_undo_redo,
            reorder_frame_callback=self._reorder_frame_for_undo_redo,
            add_animation_callback=self._add_animation_for_undo_redo,
            delete_animation_callback=self._delete_animation_for_undo_redo
        )

        # Set up frame selection callback for undo/redo
        self.undo_redo_manager.set_frame_selection_callback(self._apply_frame_selection_for_undo_redo)

        # Set up controller position callbacks for undo/redo
        self.undo_redo_manager.set_controller_position_callback(self._apply_controller_position_for_undo_redo)
        self.undo_redo_manager.set_controller_mode_callback(self._apply_controller_mode_for_undo_redo)

        # Set up frame paste callback for undo/redo
        self.undo_redo_manager.set_frame_paste_callback(self._apply_frame_paste_for_undo_redo)

        # Initialize pixel change tracking
        self._current_pixel_changes = []
        self._is_drag_operation = False
        self._pixel_change_timer = None
        self._applying_undo_redo = False

        # Initialize frame clipboard for copy/paste operations
        self._frame_clipboard = None

        self.mode_switcher = ModeSwitcher()
        self.visual_collision_manager = VisualCollisionManager()

        # Selected frame visibility toggle for canvas comparison
        self.selected_frame_visible = True

        # Controller input state tracking to prevent jittery behavior
        self._controller_axis_deadzone = 500  # Only respond to values beyond this threshold (for larger scale values)
        self._controller_axis_hat_threshold = 500  # Threshold for hat-like behavior (0.5 in normalized scale)
        self._controller_axis_last_values = {}  # Track last axis values
        self._controller_axis_cooldown = {}  # Track cooldown timers for each axis
        self._controller_axis_cooldown_duration = 0.2  # 200ms cooldown between actions

        # Set up all components
        self._setup_menu_bar()
        self._setup_canvas(options)
        self._setup_sliders_and_color_well()
        self._setup_debug_text_box()

        # Set up film strips after canvas is ready
        self._setup_film_strips()

        # Set up callback for when sprites are loaded
        if hasattr(self, "canvas") and self.canvas:
            # Set up the callback on the canvas to call the main scene
            self.canvas.on_sprite_loaded = self._on_sprite_loaded
            self.log.debug("Set up on_sprite_loaded callback for canvas")
            LOG.debug(f"DEBUG: Set up on_sprite_loaded callback for canvas")

        # Controller selection will be initialized when START button is pressed

        # Query model capabilities for optimal token usage
        try:
            capabilities = _get_model_capabilities(self.log)
            if capabilities.get("max_tokens"):
                self.log.info(f"Model max tokens detected: {capabilities['max_tokens']}")
                # Could update AI_MAX_TOKENS here if needed
        except (ValueError, ConnectionError, TimeoutError) as e:
            self.log.warning(f"Could not query model capabilities: {e}")

        # Set up voice recognition
        # TODO: Re-enable voice recognition when ready
        # self._setup_voice_recognition()

        self.all_sprites.clear(self.screen, self.background)

        # TODO: Plumb this into the scene manager

    def _handle_undo(self) -> None:
        """Handle undo operation.

        Returns:
            None
        """
        if self.undo_redo_manager.can_undo():
            success = self.undo_redo_manager.undo()
            if success:
                undo_description = self.undo_redo_manager.get_undo_description()
                LOG.debug(f"Undo successful: {undo_description}")
                # Force redraw of affected areas
                self._force_redraw_after_undo_redo()
            else:
                LOG.warning("Undo operation failed")
        else:
            LOG.debug("No operations to undo")

    def _handle_redo(self) -> None:
        """Handle redo operation.

        Returns:
            None
        """
        if self.undo_redo_manager.can_redo():
            success = self.undo_redo_manager.redo()
            if success:
                redo_description = self.undo_redo_manager.get_redo_description()
                LOG.debug(f"Redo successful: {redo_description}")
                # Force redraw of affected areas
                self._force_redraw_after_undo_redo()
            else:
                LOG.warning("Redo operation failed")
        else:
            LOG.debug("No operations to redo")

    def _force_redraw_after_undo_redo(self) -> None:
        """Force redraw of affected areas after undo/redo operations.

        Returns:
            None
        """
        # Force canvas redraw
        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.dirty = 1
            self.canvas.force_redraw()
            LOG.debug("Forced canvas redraw after undo/redo")

        # Force film strip redraw
        if hasattr(self, 'film_strips') and self.film_strips:
            for film_strip in self.film_strips:
                if hasattr(film_strip, 'dirty'):
                    film_strip.dirty = 1
            LOG.debug("Forced film strip redraw after undo/redo")

        # Force mini view redraw if it exists
        if hasattr(self, 'canvas') and self.canvas and hasattr(self.canvas, 'mini_view') and self.canvas.mini_view:
            self.canvas.mini_view.dirty = 1
            self.canvas.mini_view.force_redraw()
            LOG.debug("Forced mini view redraw after undo/redo")
        # self.register_game_event('save', self.on_save_event)
        # self.register_game_event('load', self.on_load_event)

        # Dialog scenes are now created fresh each time they're needed
        # No need to store persistent dialog scene instances

        # These are set up in the GameEngine class.
        if not hasattr(self, "_initialized"):
            self.log.info(f"Game Options: {self.options}")

            # Override font to use a cleaner system font
            self.options["font_name"] = "arial"
            self.log.info(f"Font overridden to: {self.options['font_name']}")
            self._initialized = True

    def on_menu_item_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the menu item event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None

        """
        self.log.info(f"Scene got menu item event: {event}")
        if not event.menu.name:
            # This is for the system menu.
            self.log.info("System Menu Clicked")
        elif event.menu.name == "New":
            self.on_new_canvas_dialog_event(event=event)
        elif event.menu.name == "Save":
            self.on_save_dialog_event(event=event)
        elif event.menu.name == "Load":
            self.on_load_dialog_event(event=event)
        elif event.menu.name == "Quit":
            self.log.info("User quit from menu item.")
            self.scene_manager.quit()
        else:
            self.log.info(f"Unhandled Menu Item: {event.menu.name}")
        self.dirty = 1

    # NB: Keepings this around causes GG-7 not to manifest... curious.
    # This function is extraneous now that on_new_canvas_dialog_event exists.
    #
    # There is also some dialog drawing goofiness when keeping this which
    # goes away when we remove it.
    #
    # Keeping as a workaround for GG-7 for now.
    def on_new_file_event(self: Self, dimensions: str) -> None:
        """Handle the new file event.

        Args:
            dimensions (str): The canvas dimensions in WxH format.

        Returns:
            None

        Raises:
            None

        """
        self.log.info(f"Creating new canvas with dimensions: {dimensions}")

        try:
            # Parse WxH format (e.g., "32x32")
            width, height = map(int, dimensions.lower().split("x"))
            self.log.info(f"Parsed dimensions: {width}x{height}")

            # Calculate new pixel size to fit the canvas in the available space
            # Adjust for bottom margin and menu bar
            available_height = self.screen_height - 80 - 24
            new_pixel_size = min(
                available_height // height,  # Height-based size
                (self.screen_width * 1 // 2) // width,  # Width-based size (use 1/2 of screen width)
                350 // width,  # Maximum width constraint: 350px
            )
            self.log.info(f"Calculated new pixel size: {new_pixel_size}")

            # Resize the canvas
            self.canvas.pixels_across = width
            self.canvas.pixels_tall = height
            self.canvas.pixel_width = new_pixel_size
            self.canvas.pixel_height = new_pixel_size

            # Clear and resize the canvas
            self.canvas.pixels = [(255, 0, 255, 255)] * (width * height)  # Use magenta as background
            self.canvas.dirty_pixels = [True] * len(self.canvas.pixels)

            # Reset viewport/panning system for new canvas
            if hasattr(self.canvas, 'reset_panning'):
                self.canvas.reset_panning()
            if hasattr(self.canvas, '_panning_active'):
                self.canvas._panning_active = False
            if hasattr(self.canvas, 'pan_offset_x'):
                self.canvas.pan_offset_x = 0
            if hasattr(self.canvas, 'pan_offset_y'):
                self.canvas.pan_offset_y = 0

            # Create a fresh animated sprite for the new canvas
            from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
            fresh_animated_sprite = AnimatedSprite()
            fresh_animated_sprite.name = "new_canvas"
            fresh_animated_sprite.description = "New canvas sprite"

            # Create a single frame with the new dimensions
            fresh_frame = SpriteFrame(
                surface=pygame.Surface((width, height))
            )

            # Set the frame to match the cleared canvas pixels
            fresh_frame.set_pixel_data([(255, 0, 255)] * (width * height))

            # Add the frame to the default animation
            fresh_animated_sprite._animations["default"] = [fresh_frame]
            fresh_animated_sprite.frame_manager.current_animation = "default"
            fresh_animated_sprite.frame_manager.current_frame = 0

            # Replace the canvas's animated sprite with the fresh one
            self.canvas.animated_sprite = fresh_animated_sprite

            # Update canvas image size
            self.canvas.image = pygame.Surface((width * new_pixel_size, height * new_pixel_size))
            self.canvas.rect = self.canvas.image.get_rect(x=0, y=24)  # Position below menu bar

            # Update border thickness based on new dimensions (after all initialization)
            self.canvas._update_border_thickness()

            # Force the canvas to redraw with the new dimensions and cleared pixels
            self.canvas.force_redraw()

            # Clear existing film strips for new canvas
            if hasattr(self, "film_strips") and self.film_strips:
                self.log.info("Clearing existing film strips for new canvas")
                # Remove film strip sprites from groups
                for film_strip_sprite in self.film_strip_sprites.values():
                    if hasattr(film_strip_sprite, "groups") and film_strip_sprite.groups():
                        for group in film_strip_sprite.groups():
                            group.remove(film_strip_sprite)
                # Clear film strip collections
                self.film_strips.clear()
                self.film_strip_sprites.clear()

            # Create a new film strip with a single frame for the new canvas
            self.log.info("Creating new film strip for new canvas")
            # Use existing film strip creation method
            self._create_film_strips(self.all_sprites)

            # Clear the AI sprite dialog for new canvas
            self._clear_ai_sprite_box()

            # Update AI sprite positioning for new canvas size
            self._update_ai_sprite_position()

            # Update mini map position for new size
            screen_info = pygame.display.Info()
            screen_width = screen_info.current_w
            pixel_width = 2  # MiniView uses 2x2 pixels per sprite pixel
            mini_map_width = width * pixel_width
            mini_map_x = max(screen_width - mini_map_width, 0)  # Flush to right edge
            mini_map_y = 24  # Flush to top

            # Update mini map
            if hasattr(self.canvas, "mini_view") and self.canvas.mini_view is not None:
                self.canvas.mini_view.pixels_across = width
                self.canvas.mini_view.pixels_tall = height
                self.canvas.mini_view.pixels = self.canvas.pixels
                self.canvas.mini_view.dirty_pixels = [True] * len(self.canvas.pixels)
                pixel_width, pixel_height = self.canvas.mini_view.pixels_per_pixel(width, height)
                self.canvas.mini_view.image = pygame.Surface((
                    width * pixel_width,
                    height * pixel_height,
                ))
                self.canvas.mini_view.rect = self.canvas.mini_view.image.get_rect(
                    x=mini_map_x, y=mini_map_y
                )

            # Update canvas dimensions and redraw
            self.canvas.update()
            self.canvas.dirty = 1

            self.log.info(f"Canvas resized to {width}x{height} with pixel size {new_pixel_size}")

        except ValueError:
            self.log.error(f"Invalid dimensions format '{dimensions}'")
            self.log.error("Expected format: WxH (e.g., '32x32')")

        self.dirty = 1

    def on_new_canvas_dialog_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the new canvas dialog event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None

        """
        # Create a fresh dialog scene each time
        new_canvas_dialog_scene = NewCanvasDialogScene(
            options=self.options, previous_scene=self
        )
        # Set the dialog's background to the screenshot
        new_canvas_dialog_scene.background = self.screenshot
        self.next_scene = new_canvas_dialog_scene
        self.dirty = 1

    def on_load_dialog_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the load dialog event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None

        """
        # Create a fresh dialog scene each time
        load_dialog_scene = LoadDialogScene(options=self.options, previous_scene=self)
        # Set the dialog's background to the screenshot
        load_dialog_scene.background = self.screenshot
        self.next_scene = load_dialog_scene
        self.dirty = 1

    def on_save_dialog_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the save dialog event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None

        """
        # Create a fresh dialog scene each time
        save_dialog_scene = SaveDialogScene(options=self.options, previous_scene=self)
        # Set the dialog's background to the screenshot
        save_dialog_scene.background = self.screenshot
        self.next_scene = save_dialog_scene
        self.dirty = 1

    def on_color_well_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle the color well event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Returns:
            None

        Raises:
            None

        """
        self.log.info("COLOR WELL EVENT")

    def _sample_color_from_screen(self, screen_pos):
        """Sample color directly from the screen (RGB only, ignores alpha).

        Args:
            screen_pos: Screen coordinates (x, y) to sample from
        """
        try:
            # Sample directly from the screen
            color = self.screen.get_at(screen_pos)

            # Handle both RGB and RGBA screen formats
            if len(color) == 4:
                red, green, blue, _ = color  # Ignore alpha from screen
            else:
                red, green, blue = color
            alpha = 255  # Screen has no meaningful alpha, default to opaque

            self.log.info(f"Screen pixel sampled - Red: {red}, Green: {green}, Blue: {blue}, Alpha: {alpha} (default)")

            # Update all sliders with the sampled RGB values and default alpha
            trigger = pygame.event.Event(0, {"name": "R", "value": red})
            self.on_slider_event(event=pygame.event.Event(0), trigger=trigger)

            trigger = pygame.event.Event(0, {"name": "G", "value": green})
            self.on_slider_event(event=pygame.event.Event(0), trigger=trigger)

            trigger = pygame.event.Event(0, {"name": "B", "value": blue})
            self.on_slider_event(event=pygame.event.Event(0), trigger=trigger)

            trigger = pygame.event.Event(0, {"name": "A", "value": alpha})
            self.on_slider_event(event=pygame.event.Event(0), trigger=trigger)

            self.log.info(f"Updated sliders with screen color R:{red}, G:{green}, B:{blue}, A:{alpha}")

        except Exception as e:
            self.log.error(f"Error sampling color from screen: {e}")
            self.log.exception("Full traceback:")

    def on_slider_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle the slider event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Returns:
            None

        Raises:
            None

        """
        value = trigger.value

        self.log.debug(f"Slider: event: {event}, trigger: {trigger} value: {value}")

        if value < MIN_COLOR_VALUE:
            value = MIN_COLOR_VALUE
            trigger.value = MIN_COLOR_VALUE
        elif value > MAX_COLOR_VALUE:
            value = MAX_COLOR_VALUE
            trigger.value = MAX_COLOR_VALUE

        if trigger.name == "R":
            self.red_slider.value = value
            self.log.debug(f"Updated red slider to: {value}")
        elif trigger.name == "G":
            self.green_slider.value = value
            self.log.debug(f"Updated green slider to: {value}")
        elif trigger.name == "B":
            self.blue_slider.value = value
            self.log.debug(f"Updated blue slider to: {value}")
        elif trigger.name == "A":
            self.alpha_slider.value = value
            self.log.debug(f"Updated alpha slider to: {value}")

        # Update slider text to reflect current tab format
        # This handles slider clicks - text input is handled by SliderSprite itself
        self._update_slider_text_format()

        # Debug: Log current slider values
        self.log.debug(
            f"Current slider values - R: {self.red_slider.value}, "
            f"G: {self.green_slider.value}, B: {self.blue_slider.value}, A: {self.alpha_slider.value}"
        )

        self.color_well.active_color = (
            self.red_slider.value,
            self.green_slider.value,
            self.blue_slider.value,
            self.alpha_slider.value,
        )
        self.canvas.active_color = (
            self.red_slider.value,
            self.green_slider.value,
            self.blue_slider.value,
            self.alpha_slider.value,
        )

    def on_right_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the right mouse button up event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None

        """
        # Check for shift-right-click (screen sampling)
        is_shift_click = pygame.key.get_pressed()[pygame.K_LSHIFT] or pygame.key.get_pressed()[pygame.K_RSHIFT]

        # First, check if any sprites have handled the event
        collided_sprites = self.sprites_at_position(pos=event.pos)
        for sprite in collided_sprites:
            if hasattr(sprite, "on_right_mouse_button_up_event"):
                result = sprite.on_right_mouse_button_up_event(event)
                if result:  # Event was handled by sprite
                    return

        # If no sprite handled the event, proceed with scene-level handling
        # Check if the click is on the canvas to sample canvas pixel data
        if hasattr(self, "canvas") and self.canvas and self.canvas.rect.collidepoint(event.pos):
            if is_shift_click:
                # Shift-right-click: sample screen directly (RGB only)
                self.log.info("Shift-right-click detected on canvas - sampling screen directly")
                self._sample_color_from_screen(event.pos)
                return
            else:
                # Regular right-click: sample from canvas pixel data (RGBA)
                canvas_x = (event.pos[0] - self.canvas.rect.x) // self.canvas.pixel_width
                canvas_y = (event.pos[1] - self.canvas.rect.y) // self.canvas.pixel_height

                # Check bounds
                if (0 <= canvas_x < self.canvas.pixels_across and
                    0 <= canvas_y < self.canvas.pixels_tall):
                    pixel_num = canvas_y * self.canvas.pixels_across + canvas_x
                    if pixel_num < len(self.canvas.pixels):
                        color = self.canvas.pixels[pixel_num]

                        # Handle both RGB and RGBA pixel formats
                        if len(color) == 4:
                            red, green, blue, alpha = color
                        else:
                            red, green, blue = color
                            alpha = 255  # Default to opaque for RGB pixels

                        self.log.info(f"Canvas pixel sampled - Red: {red}, Green: {green}, Blue: {blue}, Alpha: {alpha}")

                        # Update all sliders with the sampled RGBA values
                        trigger = pygame.event.Event(0, {"name": "R", "value": red})
                        self.on_slider_event(event=event, trigger=trigger)

                        trigger = pygame.event.Event(0, {"name": "G", "value": green})
                        self.on_slider_event(event=event, trigger=trigger)

                        trigger = pygame.event.Event(0, {"name": "B", "value": blue})
                        self.on_slider_event(event=event, trigger=trigger)

                        trigger = pygame.event.Event(0, {"name": "A", "value": alpha})
                        self.on_slider_event(event=event, trigger=trigger)
                        return

        # Fallback to screen sampling (RGB only)
        try:
            color = self.screen.get_at(event.pos)
            if len(color) == 4:
                red, green, blue, _ = color  # Ignore alpha from screen
            else:
                red, green, blue = color
            alpha = 255  # Screen has no alpha, default to opaque
            self.log.info(f"Screen pixel sampled - Red: {red}, Green: {green}, Blue: {blue}, Alpha: {alpha} (default)")

            # Update sliders with RGB values and default alpha
            trigger = pygame.event.Event(0, {"name": "R", "value": red})
            self.on_slider_event(event=event, trigger=trigger)

            trigger = pygame.event.Event(0, {"name": "G", "value": green})
            self.on_slider_event(event=event, trigger=trigger)

            trigger = pygame.event.Event(0, {"name": "B", "value": blue})
            self.on_slider_event(event=event, trigger=trigger)

            trigger = pygame.event.Event(0, {"name": "A", "value": alpha})
            self.on_slider_event(event=event, trigger=trigger)
        except IndexError:
            pass

    def on_left_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the left mouse button down event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None

        """
        sprites = self.sprites_at_position(pos=event.pos)

        # Check for clicks on scroll arrows first (only if visible)
        for sprite in sprites:
            if hasattr(sprite, "direction") and hasattr(sprite, "visible") and sprite.visible:
                LOG.debug(f"Scroll arrow clicked: direction={sprite.direction}, visible={sprite.visible}")
                if sprite.direction == "up":
                    # Clicked on up arrow - navigate to previous animation and scroll if needed
                    LOG.debug("Navigating to previous animation")
                    if hasattr(self, "canvas") and self.canvas:
                        self.canvas.previous_animation()
                        # Scroll to show the current animation if needed
                        self._scroll_to_current_animation()
                        # Update film strips to reflect the animation change
                        self._update_film_strips_for_animated_sprite_update()
                    return

        # Check if click is on any slider text box and deactivate others
        clicked_slider = None
        if hasattr(self, "red_slider") and hasattr(self.red_slider, "text_sprite"):
            if self.red_slider.text_sprite.rect.collidepoint(event.pos):
                clicked_slider = "red"
        if hasattr(self, "green_slider") and hasattr(self.green_slider, "text_sprite"):
            if self.green_slider.text_sprite.rect.collidepoint(event.pos):
                clicked_slider = "green"
        if hasattr(self, "blue_slider") and hasattr(self.blue_slider, "text_sprite"):
            if self.blue_slider.text_sprite.rect.collidepoint(event.pos):
                clicked_slider = "blue"

        # Deactivate all slider text boxes except the one clicked (if any)
        # Also commit values when clicking outside of any slider text box
        if hasattr(self, "red_slider") and hasattr(self.red_slider, "text_sprite"):
            if self.red_slider.text_sprite.active and (clicked_slider != "red" or clicked_slider is None):
                # Commit any uncommitted value before deactivating
                if self.red_slider.text_sprite.text.strip() == "":
                    # If empty, restore original value
                    self.red_slider.text_sprite.text = str(self.red_slider.original_value)
                else:
                    # Try to commit the current text value - parse as hex if contains letters, otherwise decimal
                    try:
                        text = self.red_slider.text_sprite.text.strip().lower()
                        if any(c in "abcdef" for c in text):
                            # Contains hex characters, parse as hex
                            new_value = int(text, 16)
                        else:
                            # No hex characters, parse as decimal
                            new_value = int(text)

                        if 0 <= new_value <= 255:
                            self.red_slider.value = new_value
                            # Update original value for future validations
                            self.red_slider.original_value = new_value
                            # Convert text to appropriate format based on selected tab
                            LOG.debug(f"DEBUG: Current slider_input_format: {self.slider_input_format}")
                            if self.slider_input_format == "%X":
                                self.red_slider.text_sprite.text = f"{new_value:02X}"
                                LOG.debug(f"DEBUG: Converting {new_value} to hex: {self.red_slider.text_sprite.text}")
                            else:
                                self.red_slider.text_sprite.text = str(new_value)
                                LOG.debug(f"DEBUG: Converting {new_value} to decimal: {self.red_slider.text_sprite.text}")
                            self.red_slider.text_sprite.update_text(self.red_slider.text_sprite.text)
                            self.red_slider.text_sprite.dirty = 2  # Force redraw
                        else:
                            # Invalid range, restore original
                            self.red_slider.text_sprite.text = str(self.red_slider.original_value)
                    except ValueError:
                        # Invalid input, restore original
                        self.red_slider.text_sprite.text = str(self.red_slider.original_value)

                self.red_slider.text_sprite.active = False
                self.red_slider.text_sprite.update_text(self.red_slider.text_sprite.text)
        if hasattr(self, "green_slider") and hasattr(self.green_slider, "text_sprite"):
            if self.green_slider.text_sprite.active and (clicked_slider != "green" or clicked_slider is None):
                # Commit any uncommitted value before deactivating
                if self.green_slider.text_sprite.text.strip() == "":
                    # If empty, restore original value
                    self.green_slider.text_sprite.text = str(self.green_slider.original_value)
                else:
                    # Try to commit the current text value - parse as hex if contains letters, otherwise decimal
                    try:
                        text = self.green_slider.text_sprite.text.strip().lower()
                        if any(c in "abcdef" for c in text):
                            # Contains hex characters, parse as hex
                            new_value = int(text, 16)
                        else:
                            # No hex characters, parse as decimal
                            new_value = int(text)

                        if 0 <= new_value <= 255:
                            self.green_slider.value = new_value
                            # Update original value for future validations
                            self.green_slider.original_value = new_value
                            # Convert text to appropriate format based on selected tab
                            if self.slider_input_format == "%X":
                                self.green_slider.text_sprite.text = f"{new_value:02X}"
                            else:
                                self.green_slider.text_sprite.text = str(new_value)
                            self.green_slider.text_sprite.update_text(self.green_slider.text_sprite.text)
                            self.green_slider.text_sprite.dirty = 2  # Force redraw
                        else:
                            # Invalid range, restore original
                            self.green_slider.text_sprite.text = str(self.green_slider.original_value)
                    except ValueError:
                        # Invalid input, restore original
                        self.green_slider.text_sprite.text = str(self.green_slider.original_value)

                self.green_slider.text_sprite.active = False
                self.green_slider.text_sprite.update_text(self.green_slider.text_sprite.text)
        if hasattr(self, "blue_slider") and hasattr(self.blue_slider, "text_sprite"):
            if self.blue_slider.text_sprite.active and (clicked_slider != "blue" or clicked_slider is None):
                # Commit any uncommitted value before deactivating
                if self.blue_slider.text_sprite.text.strip() == "":
                    # If empty, restore original value
                    self.blue_slider.text_sprite.text = str(self.blue_slider.original_value)
                else:
                    # Try to commit the current text value - parse as hex if contains letters, otherwise decimal
                    try:
                        text = self.blue_slider.text_sprite.text.strip().lower()
                        if any(c in "abcdef" for c in text):
                            # Contains hex characters, parse as hex
                            new_value = int(text, 16)
                        else:
                            # No hex characters, parse as decimal
                            new_value = int(text)

                        if 0 <= new_value <= 255:
                            self.blue_slider.value = new_value
                            # Update original value for future validations
                            self.blue_slider.original_value = new_value
                            # Convert text to appropriate format based on selected tab
                            if self.slider_input_format == "%X":
                                self.blue_slider.text_sprite.text = f"{new_value:02X}"
                            else:
                                self.blue_slider.text_sprite.text = str(new_value)
                            self.blue_slider.text_sprite.update_text(self.blue_slider.text_sprite.text)
                            self.blue_slider.text_sprite.dirty = 2  # Force redraw
                        else:
                            # Invalid range, restore original
                            self.blue_slider.text_sprite.text = str(self.blue_slider.original_value)
                    except ValueError:
                        # Invalid input, restore original
                        self.blue_slider.text_sprite.text = str(self.blue_slider.original_value)

                self.blue_slider.text_sprite.active = False
                self.blue_slider.text_sprite.update_text(self.blue_slider.text_sprite.text)

        # If a slider text box was clicked, also trigger the slider's normal behavior
        if clicked_slider == "red" and hasattr(self, "red_slider"):
            self.red_slider.on_left_mouse_button_down_event(event)
        elif clicked_slider == "green" and hasattr(self, "green_slider"):
            self.green_slider.on_left_mouse_button_down_event(event)
        elif clicked_slider == "blue" and hasattr(self, "blue_slider"):
            self.blue_slider.on_left_mouse_button_down_event(event)

        # Handle other sprite clicks
        for sprite in sprites:
            sprite.on_left_mouse_button_down_event(event)

        # Check if click is in film strip area for drag scrolling (only if no sprite handled it)
        if self._is_mouse_in_film_strip_area(event.pos):
            self.is_dragging_film_strips = True
            self.film_strip_drag_start_y = event.pos[1]
            self.film_strip_drag_start_offset = self.film_strip_scroll_offset
            self.log.debug(f"Started film strip drag at Y={event.pos[1]}, offset={self.film_strip_scroll_offset}")

    def on_tab_change_event(self, tab_format):
        """Handle tab control format change.

        Args:
            tab_format (str): The selected format ("%d" or "%H")

        Returns:
            None

        """
        self.log.info(f"Tab control changed to format: {tab_format}")

        # Store the current format for slider text input
        self.slider_input_format = tab_format

        # Update slider text display format if they have values
        self._update_slider_text_format(tab_format)

    def _update_slider_text_format(self, tab_format=None):
        """Update slider text display format.

        Args:
            tab_format (str): The format to use ("%X" for hex, "%d" for decimal).
                             If None, uses the current slider_input_format.

        """
        if tab_format is None:
            tab_format = getattr(self, "slider_input_format", "%d")

        if hasattr(self, "red_slider") and hasattr(self.red_slider, "text_sprite"):
            if tab_format == "%X":
                # Convert to hex
                self.red_slider.text_sprite.text = f"{self.red_slider.value:02X}"
            else:
                # Convert to decimal
                self.red_slider.text_sprite.text = str(self.red_slider.value)
            self.red_slider.text_sprite.update_text(self.red_slider.text_sprite.text)

        if hasattr(self, "green_slider") and hasattr(self.green_slider, "text_sprite"):
            if tab_format == "%X":
                # Convert to hex
                self.green_slider.text_sprite.text = f"{self.green_slider.value:02X}"
            else:
                # Convert to decimal
                self.green_slider.text_sprite.text = str(self.green_slider.value)
            self.green_slider.text_sprite.update_text(self.green_slider.text_sprite.text)

        if hasattr(self, "blue_slider") and hasattr(self.blue_slider, "text_sprite"):
            if tab_format == "%X":
                # Convert to hex
                self.blue_slider.text_sprite.text = f"{self.blue_slider.value:02X}"
            else:
                # Convert to decimal
                self.blue_slider.text_sprite.text = str(self.blue_slider.value)
            self.blue_slider.text_sprite.update_text(self.blue_slider.text_sprite.text)

    def on_left_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the left mouse button up event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None

        """
        # Stop film strip drag scrolling if active
        if self.is_dragging_film_strips:
            self.is_dragging_film_strips = False
            self.film_strip_drag_start_y = None
            self.film_strip_drag_start_offset = None
            self.log.debug("Stopped film strip drag scrolling")

        sprites = self.sprites_at_position(pos=event.pos)

        for sprite in sprites:
            sprite.on_left_mouse_button_up_event(event)

    def on_left_mouse_drag_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle the left mouse drag event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Returns:
            None

        Raises:
            None

        """
        # Handle film strip drag scrolling
        if self.is_dragging_film_strips:
            self.log.debug(f"Handling film strip drag at Y={event.pos[1]}")
            self._handle_film_strip_drag_scroll(event.pos[1])
            return  # Don't process other drag events when dragging film strips

        # Don't set drag flag here - let the pixel collection logic handle it

        self.canvas.on_left_mouse_drag_event(event, trigger)

        try:
            sprites = self.sprites_at_position(pos=event.pos)

            for sprite in sprites:
                sprite.on_left_mouse_drag_event(event, trigger)
        except AttributeError:
            pass

    def on_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse button up events."""
        # Check if debug text box should handle the event
        if hasattr(self, "debug_text") and self.debug_text.rect.collidepoint(event.pos):
            self.debug_text.on_mouse_up_event(event)
            return

        # Submit collected pixel changes for undo/redo tracking
        self._submit_pixel_changes_if_ready()

        # Reset drag operation flag
        self._is_drag_operation = False

        # Always release all sliders on mouse up to prevent stickiness
        if hasattr(self, "red_slider") and hasattr(self.red_slider, "dragging"):
            if self.red_slider.dragging:
                self.red_slider.dragging = False
                self.red_slider.on_left_mouse_button_up_event(event)
        if hasattr(self, "green_slider") and hasattr(self.green_slider, "dragging"):
            if self.green_slider.dragging:
                self.green_slider.dragging = False
                self.green_slider.on_left_mouse_button_up_event(event)
        if hasattr(self, "blue_slider") and hasattr(self.blue_slider, "dragging"):
            if self.blue_slider.dragging:
                self.blue_slider.dragging = False
                self.blue_slider.on_left_mouse_button_up_event(event)

        # Pass to other sprites
        for sprite in self.all_sprites:
            if hasattr(sprite, "on_mouse_button_up_event") and sprite.rect.collidepoint(event.pos):
                sprite.on_mouse_button_up_event(event)

    def on_mouse_drag_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle
            trigger (object): The trigger object

        """
        for sprite in self.all_sprites:
            if hasattr(sprite, "on_mouse_drag_event"):
                sprite.on_mouse_drag_event(event, trigger)

    def on_mouse_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse motion events.

        Args:
            event (pygame.event.Event): The event to handle

        """
        # Handle slider hover effects
        self._update_slider_hover_effects(event.pos)

        for sprite in self.all_sprites:
            if hasattr(sprite, "on_mouse_motion_event"):
                sprite.on_mouse_motion_event(event)

    def _update_slider_hover_effects(self, mouse_pos: tuple[int, int]) -> None:
        """Update slider hover effects based on mouse position.

        Args:
            mouse_pos: The current mouse position (x, y)
        """
        # Check if mouse is hovering over any slider
        alpha_hover = (hasattr(self, 'alpha_slider') and
                      self.alpha_slider.rect.collidepoint(mouse_pos))
        red_hover = (hasattr(self, 'red_slider') and
                    self.red_slider.rect.collidepoint(mouse_pos))
        green_hover = (hasattr(self, 'green_slider') and
                      self.green_slider.rect.collidepoint(mouse_pos))
        blue_hover = (hasattr(self, 'blue_slider') and
                     self.blue_slider.rect.collidepoint(mouse_pos))

        # Check if mouse is hovering over any slider text boxes
        # Use absolute coordinates for text sprites
        alpha_text_hover = (hasattr(self, 'alpha_slider') and hasattr(self.alpha_slider, 'text_sprite') and
                           self.alpha_slider.text_sprite.rect.collidepoint(mouse_pos))
        red_text_hover = (hasattr(self, 'red_slider') and hasattr(self.red_slider, 'text_sprite') and
                         self.red_slider.text_sprite.rect.collidepoint(mouse_pos))
        green_text_hover = (hasattr(self, 'green_slider') and hasattr(self.green_slider, 'text_sprite') and
                           self.green_slider.text_sprite.rect.collidepoint(mouse_pos))
        blue_text_hover = (hasattr(self, 'blue_slider') and hasattr(self.blue_slider, 'text_sprite') and
                          self.blue_slider.text_sprite.rect.collidepoint(mouse_pos))



        # Update alpha slider border
        if hasattr(self, 'alpha_slider_bbox'):
            if alpha_hover and not self.alpha_slider_bbox.visible:
                # Show alpha border (magenta color based on slider value)
                alpha_value = self.alpha_slider.value if hasattr(self, 'alpha_slider') else 0
                alpha_color = (alpha_value, 0, alpha_value)  # Equal parts red and blue
                self.alpha_slider_bbox.image.fill((0, 0, 0, 0))  # Clear surface
                pygame.draw.rect(self.alpha_slider_bbox.image, alpha_color,
                               (0, 0, self.alpha_slider_bbox.rect.width, self.alpha_slider_bbox.rect.height), 2)
                self.alpha_slider_bbox.visible = True
                self.alpha_slider_bbox.dirty = 1
            elif not alpha_hover and self.alpha_slider_bbox.visible:
                # Hide alpha border
                self.alpha_slider_bbox.image.fill((0, 0, 0, 0))  # Clear surface
                self.alpha_slider_bbox.visible = False
                self.alpha_slider_bbox.dirty = 1

        # Update red slider border
        if hasattr(self, 'red_slider_bbox'):
            if red_hover and not self.red_slider_bbox.visible:
                # Show red border
                self.red_slider_bbox.image.fill((0, 0, 0, 0))  # Clear surface
                pygame.draw.rect(self.red_slider_bbox.image, (255, 0, 0),
                               (0, 0, self.red_slider_bbox.rect.width, self.red_slider_bbox.rect.height), 2)
                self.red_slider_bbox.visible = True
                self.red_slider_bbox.dirty = 1
            elif not red_hover and self.red_slider_bbox.visible:
                # Hide red border
                self.red_slider_bbox.image.fill((0, 0, 0, 0))  # Clear surface
                self.red_slider_bbox.visible = False
                self.red_slider_bbox.dirty = 1

        # Update green slider border
        if hasattr(self, 'green_slider_bbox'):
            if green_hover and not self.green_slider_bbox.visible:
                # Show green border
                self.green_slider_bbox.image.fill((0, 0, 0, 0))  # Clear surface
                pygame.draw.rect(self.green_slider_bbox.image, (0, 255, 0),
                               (0, 0, self.green_slider_bbox.rect.width, self.green_slider_bbox.rect.height), 2)
                self.green_slider_bbox.visible = True
                self.green_slider_bbox.dirty = 1
            elif not green_hover and self.green_slider_bbox.visible:
                # Hide green border
                self.green_slider_bbox.image.fill((0, 0, 0, 0))  # Clear surface
                self.green_slider_bbox.visible = False
                self.green_slider_bbox.dirty = 1

        # Update blue slider border
        if hasattr(self, 'blue_slider_bbox'):
            if blue_hover and not self.blue_slider_bbox.visible:
                # Show blue border
                self.blue_slider_bbox.image.fill((0, 0, 0, 0))  # Clear surface
                pygame.draw.rect(self.blue_slider_bbox.image, (0, 0, 255),
                               (0, 0, self.blue_slider_bbox.rect.width, self.blue_slider_bbox.rect.height), 2)
                self.blue_slider_bbox.visible = True
                self.blue_slider_bbox.dirty = 1
            elif not blue_hover and self.blue_slider_bbox.visible:
                # Hide blue border
                self.blue_slider_bbox.image.fill((0, 0, 0, 0))  # Clear surface
                self.blue_slider_bbox.visible = False
                self.blue_slider_bbox.dirty = 1

        # Update text box hover effects (white borders)
        # Alpha slider text box
        if hasattr(self, 'alpha_slider') and hasattr(self.alpha_slider, 'text_sprite'):
            if alpha_text_hover:
                # Add white border to text sprite
                if not hasattr(self.alpha_slider.text_sprite, 'hover_border_added'):
                    # Create a white border by drawing on the text sprite's image
                    pygame.draw.rect(self.alpha_slider.text_sprite.image, (255, 255, 255),
                                   (0, 0, self.alpha_slider.text_sprite.rect.width, self.alpha_slider.text_sprite.rect.height), 2)
                    self.alpha_slider.text_sprite.hover_border_added = True
                    self.alpha_slider.text_sprite.dirty = 1
            else:
                # Remove white border
                if hasattr(self.alpha_slider.text_sprite, 'hover_border_added') and self.alpha_slider.text_sprite.hover_border_added:
                    # Force text sprite to redraw without border
                    self.alpha_slider.text_sprite.update_text(self.alpha_slider.text_sprite.text)
                    self.alpha_slider.text_sprite.hover_border_added = False
                    self.alpha_slider.text_sprite.dirty = 1

        # Red slider text box
        if hasattr(self, 'red_slider') and hasattr(self.red_slider, 'text_sprite'):
            if red_text_hover:
                # Add white border to text sprite
                if not hasattr(self.red_slider.text_sprite, 'hover_border_added'):
                    # Create a white border by drawing on the text sprite's image
                    pygame.draw.rect(self.red_slider.text_sprite.image, (255, 255, 255),
                                   (0, 0, self.red_slider.text_sprite.rect.width, self.red_slider.text_sprite.rect.height), 2)
                    self.red_slider.text_sprite.hover_border_added = True
                    self.red_slider.text_sprite.dirty = 1
            else:
                # Remove white border
                if hasattr(self.red_slider.text_sprite, 'hover_border_added') and self.red_slider.text_sprite.hover_border_added:
                    # Force text sprite to redraw without border
                    self.red_slider.text_sprite.update_text(self.red_slider.text_sprite.text)
                    self.red_slider.text_sprite.hover_border_added = False
                    self.red_slider.text_sprite.dirty = 1

        # Green slider text box
        if hasattr(self, 'green_slider') and hasattr(self.green_slider, 'text_sprite'):
            if green_text_hover:
                # Add white border to text sprite
                if not hasattr(self.green_slider.text_sprite, 'hover_border_added'):
                    # Create a white border by drawing on the text sprite's image
                    pygame.draw.rect(self.green_slider.text_sprite.image, (255, 255, 255),
                                   (0, 0, self.green_slider.text_sprite.rect.width, self.green_slider.text_sprite.rect.height), 2)
                    self.green_slider.text_sprite.hover_border_added = True
                    self.green_slider.text_sprite.dirty = 1
            else:
                # Remove white border
                if hasattr(self.green_slider.text_sprite, 'hover_border_added') and self.green_slider.text_sprite.hover_border_added:
                    # Force text sprite to redraw without border
                    self.green_slider.text_sprite.update_text(self.green_slider.text_sprite.text)
                    self.green_slider.text_sprite.hover_border_added = False
                    self.green_slider.text_sprite.dirty = 1

        # Blue slider text box
        if hasattr(self, 'blue_slider') and hasattr(self.blue_slider, 'text_sprite'):
            if blue_text_hover:
                # Add white border to text sprite
                if not hasattr(self.blue_slider.text_sprite, 'hover_border_added'):
                    # Create a white border by drawing on the text sprite's image
                    pygame.draw.rect(self.blue_slider.text_sprite.image, (255, 255, 255),
                                   (0, 0, self.blue_slider.text_sprite.rect.width, self.blue_slider.text_sprite.rect.height), 2)
                    self.blue_slider.text_sprite.hover_border_added = True
                    self.blue_slider.text_sprite.dirty = 1
            else:
                # Remove white border
                if hasattr(self.blue_slider.text_sprite, 'hover_border_added') and self.blue_slider.text_sprite.hover_border_added:
                    # Force text sprite to redraw without border
                    self.blue_slider.text_sprite.update_text(self.blue_slider.text_sprite.text)
                    self.blue_slider.text_sprite.hover_border_added = False
                    self.blue_slider.text_sprite.dirty = 1

    def _update_sprite_description(self, description: str) -> None:
        """Update the sprite description when the AI text box content changes.

        Args:
            description: The new description text

        """
        if hasattr(self, "canvas") and self.canvas and hasattr(self.canvas, "animated_sprite") and self.canvas.animated_sprite:
            self.canvas.animated_sprite.description = description
            self.log.debug(f"Updated sprite description: '{description}'")
        else:
            self.log.debug("No animated sprite available to update description")

    def _on_debug_text_change(self, new_text: str) -> None:
        """Callback for when the debug text changes.

        Args:
            new_text: The new text content

        """
        self._update_sprite_description(new_text)

    def on_text_submit_event(self, text: str) -> None:
        """Handle text submission from MultiLineTextBox."""
        # Don't update sprite description here - only update when AI generation actually happens
        self.log.info(f"AI Sprite Generation Request: '{text}'")
        self.log.debug(f"Text length: {len(text)}")
        self.log.debug(f"Text type: {type(text)}")

        # Only process AI requests if we have an active queue
        if not self.ai_request_queue:
            self.log.error("AI request queue is not available")
            if hasattr(self, "debug_text"):
                self.debug_text.text = "AI processing not available"
            return

        # Check AI process status
        if hasattr(self, "ai_process") and self.ai_process and not self.ai_process.is_alive():
            self.log.error("AI process is not alive")
            if hasattr(self, "debug_text"):
                self.debug_text.text = "AI process not available"
            return

        # Determine the format to use based on training data
        format_instruction = ""
        if AI_TRAINING_FORMAT == "toml":
            format_instruction = """
                    I understand. I will provide ONLY raw TOML content "
                    "without any
                    markdown formatting, code blocks, or explanations. The TOML "
                    "format
                    will include:
                        - [sprite] section containing name and pixels "
                        "(using triple-quoted block strings)
                        - [colors."X"] sections ONLY for colors that are actually used in the pixel data
                        - RGB values from 0-255 for each color
                        - Pixels using the SPRITE_GLYPHS character set
                        - For animated sprites: [[animation]] and [[animation.frame]] sections
                        - When "frame", "animation", "animated", "2-frame", or "multi-frame"
                          is mentioned, I will create an ANIMATED sprite with multiple frames
                        - IMPORTANT: Use triple-quoted block strings for multi-line pixel data
                        - EFFICIENCY: Only define colors that appear in the pixels "
                            (e.g., if pixels="0", only define [colors."0"])
                """.strip()
        else:
            format_instruction = """
                    I understand. I will provide ONLY raw INI content without any
                    markdown formatting, code blocks, or explanations. The INI format
                    will include:
                        - [sprite] section containing name and pixel layout
                        - RGB values from 0-255 for each color
                        - Pixels using the SPRITE_GLYPHS character set
                """.strip()

        # Check if current frame has content (not all magenta)
        current_frame_has_content = self._check_current_frame_has_content()
        self.log.info(f"Frame content check result: {current_frame_has_content}")

        if current_frame_has_content:
            # Save both current frame and current strip to temporary TOML files
            frame_toml_path = self._save_current_frame_to_temp_toml()
            strip_toml_path = self._save_current_strip_to_temp_toml()

            examples = []

            # Load current frame as training example
            if frame_toml_path:
                frame_example = self._load_temp_toml_as_example(frame_toml_path)
                if frame_example:
                    frame_example["name"] = "selected_frame"
                    examples.append(frame_example)
                    self.log.info("Added current frame as training example")

            # Load current strip as training example
            if strip_toml_path:
                strip_example = self._load_temp_toml_as_example(strip_toml_path)
                if strip_example:
                    strip_example["name"] = "selected_strip"
                    examples.append(strip_example)
                    self.log.info("Added current strip as training example")

            if examples:
                # Check if we have only one film strip with one frame - if so, just send the frame
                if (len(examples) == 2 and
                    hasattr(self, "canvas") and self.canvas and
                    hasattr(self.canvas, "animated_sprite") and self.canvas.animated_sprite and
                    len(self.canvas.animated_sprite._animations) == 1):

                    # Check if the single animation has only one frame
                    single_animation = list(self.canvas.animated_sprite._animations.values())[0]
                    # Handle both list of frames and object with frames attribute
                    if hasattr(single_animation, "frames"):
                        frame_count = len(single_animation.frames)
                    else:
                        frame_count = len(single_animation)

                    if frame_count == 1:
                        # Only send the frame, not the strip
                        relevant_examples = [examples[0]]  # Just the frame
                        self.log.info("Optimization: Single frame in single strip - using only frame data")
                    else:
                        # Multiple frames, send both
                        relevant_examples = examples
                        self.log.info(f"Using {len(examples)} context examples (frame + strip, no regular examples)")
                else:
                    # Use both current frame and strip as training examples (no regular examples)
                    relevant_examples = examples
                    self.log.info(f"Using {len(examples)} context examples (frame + strip, no regular examples)")
            else:
                relevant_examples = _select_relevant_training_examples(text)
                self.log.info(f"Failed to load context examples, using {len(relevant_examples)} regular examples")
        else:
            # Frame is empty (all magenta), use regular examples
            relevant_examples = _select_relevant_training_examples(text)
            self.log.info(f"Frame is empty, using {len(relevant_examples)} regular examples")

        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": f"""
                    You are a helpful assistant in a bitmap editor that can create
                    game content for game developers. You can create both static
                    single-frame sprites and animated multi-frame sprites.

                    Available character set for sprite pixels: {len(SPRITE_GLYPHS[:512])} colors: {SPRITE_GLYPHS[:512]}
                """.strip(),
            },
            {
                "role": "user",
                "content": f"""
                            Here is the context for your sprite generation:

                            {"\n".join([str(data) for data in relevant_examples])}

                            Available character set: {len(SPRITE_GLYPHS[:512])} colors: {SPRITE_GLYPHS[:512]}

                            IMPORTANT: The examples above include both the selected frame and the selected strip from the current sprite. Use this context to understand what the user is asking for and determine the appropriate response based on their request.
                        """.strip(),
            },
            {
                "role": "assistant",
                "content": f"""
                    Thank you for providing those sprite examples. I understand
                    that each sprite consists of:

                    1. A name
                    2. A pixel layout using characters from: {len(SPRITE_GLYPHS[:512])} colors: {SPRITE_GLYPHS[:512]}
                    3. A color palette mapping characters to RGB values
                    4. For animated sprites: multiple frames with timing information

                    I'll use the {AI_TRAINING_FORMAT.upper()} format when suggesting new sprites.
                """.strip(),
            },
            {
                "role": "user",
                "content": f"""
                    Great! When I ask you to create a sprite, please provide ONLY the
                    {AI_TRAINING_FORMAT.upper()} content without any markdown formatting,
                    code blocks, or explanations. Just the raw {AI_TRAINING_FORMAT.upper()}
                    file content.

                    {COMPLETE_TOML_FORMAT}

                    IMPORTANT: Return ONLY the {AI_TRAINING_FORMAT.upper()} content,
                    no markdown code blocks, no explanations, no ```toml or ``` markers.
                """.strip(),
            },
            {
                "role": "assistant",
                "content": format_instruction,
            },
            {
                "role": "user",
                "content": text.strip(),
            },
        ]

        try:
            # Create unique request ID
            request_id = str(time.time())

            # Send request to worker with full conversation context
            request = AIRequest(prompt=messages, request_id=request_id, messages=messages)
            self.log.info(f"Submitting AI request: {request}")

            self.ai_request_queue.put(request)

            # Store request ID
            self.pending_ai_requests[request_id] = text

            # Update UI to show pending state
            if hasattr(self, "debug_text"):
                self.debug_text.text = f"Processing AI request... (ID: {request_id})"

        except Exception:
            self.log.error("Error submitting AI request")
            if hasattr(self, "debug_text"):
                self.debug_text.text = "Error: Failed to submit AI request"

    def setup(self):
        """Set up the bitmap editor scene."""
        super().setup()

        # Initialize AI processing components
        self.pending_ai_requests = {}
        self.ai_request_queue = None
        self.ai_response_queue = None
        self.ai_process = None

        # Check if we're in the main process
        if multiprocessing.current_process().name == "MainProcess":
            self.log.info("Initializing AI worker process...")

            try:
                self.ai_request_queue = multiprocessing.Queue()
                self.ai_response_queue = multiprocessing.Queue()

                self.ai_process = multiprocessing.Process(
                    target=ai_worker,
                    args=(self.ai_request_queue, self.ai_response_queue),
                    daemon=True,
                )

                self.ai_process.start()
                self.log.info(f"AI worker process started with PID: {self.ai_process.pid}")

            except Exception:
                self.log.error("Error initializing AI worker process")
                self.ai_request_queue = None
                self.ai_response_queue = None
                self.ai_process = None
        else:
            self.log.warning("Not in main process, AI processing not available")

    def _process_ai_response(self, request_id: str, response) -> None:
        """Process an AI response."""
        self.log.info(f"Got AI response for request {request_id}")

        if response.content is not None:
            self._load_ai_sprite(request_id, response.content)
        else:
            self.log.error("AI response content is None, cannot save sprite")
            if hasattr(self, "debug_text"):
                self.debug_text.text = "AI response was empty"

        # Remove from pending requests
        if request_id in self.pending_ai_requests:
            del self.pending_ai_requests[request_id]

    def _log_ai_response_content(self, content: str) -> None:
        """Log AI response content for debugging."""
        self.log.info(f"AI response received, content length: {len(content)}")

        # Debug: Dump the sprite content
        self.log.info("=== AI GENERATED SPRITE CONTENT ===")
        self.log.info(
            f"AI Generated Content:\n"
            f"{content}"
        )
        self.log.info("=== END SPRITE CONTENT ===")

    def _prepare_ai_content(self, request_id: str, content: str) -> str:
        """Clean AI response content and add description if needed."""
        # Get the original user prompt from the request
        original_prompt = ""
        if request_id in self.pending_ai_requests:
            original_prompt = self.pending_ai_requests[request_id]
            self.log.debug(f"Using original prompt: '{original_prompt}'")

        # Clean up any markdown formatting from AI response
        cleaned_content = self._clean_ai_response(content)

        # Check if this is an error message - if so, return it as-is
        if cleaned_content.strip() in ["AI features not available", "AI features not available."]:
            self.log.warning("AI returned error message, skipping TOML processing")
            return cleaned_content

        # Add description to the content if we have an original prompt
        if original_prompt and AI_TRAINING_FORMAT == "toml":
            # Parse the TOML content and add description
            try:
                data = toml.loads(cleaned_content)
                # Normalize the TOML data to convert escaped newlines to actual newlines
                data = _normalize_toml_data(data)
                if "sprite" not in data:
                    data["sprite"] = {}
                data["sprite"]["description"] = original_prompt

                # Manually construct TOML to preserve formatting instead of using toml.dumps()
                cleaned_content = self._construct_toml_with_preserved_formatting(data)
                self.log.debug(f"Added description to TOML content: '{original_prompt}'")
            except (toml.TomlDecodeError, KeyError, ValueError) as e:
                self.log.warning(f"Failed to add description to TOML content: {e}")

        return cleaned_content

    def _construct_toml_with_preserved_formatting(self, data: dict) -> str:
        """Construct TOML content while preserving original formatting for pixel data.

        Args:
            data: Parsed TOML data

        Returns:
            TOML content string with preserved formatting

        """
        lines = []

        # Add sprite section
        if "sprite" in data:
            lines.append("[sprite]")
            sprite_data = data["sprite"]
            if "name" in sprite_data:
                lines.append(f'name = "{sprite_data["name"]}"')
            if "description" in sprite_data:
                lines.append(f'description = """{sprite_data["description"]}"""')
            if "pixels" in sprite_data:
                lines.append('pixels = """')
                lines.append(sprite_data["pixels"])
                lines.append('"""')
            lines.append("")

        # Add animation sections
        if "animation" in data:
            for animation in data["animation"]:
                lines.append("[[animation]]")
                lines.append(f'namespace = "{animation["namespace"]}"')
                lines.append(f"frame_interval = {animation['frame_interval']}")
                lines.append(f"loop = {str(animation['loop']).lower()}")
                lines.append("")

                for frame in animation.get("frame", []):
                    lines.append("[[animation.frame]]")
                    lines.append(f'namespace = "{animation["namespace"]}"')
                    lines.append(f"frame_index = {frame['frame_index']}")
                    lines.append('pixels = """')
                    lines.append(frame["pixels"])
                    lines.append('"""')
                    lines.append("")

        # Add colors section
        if "colors" in data:
            lines.append("[colors]")
            for color_key, color_data in data["colors"].items():
                lines.append(f'[colors."{color_key}"]')
                lines.append(f"red = {color_data['red']}")
                lines.append(f"green = {color_data['green']}")
                lines.append(f"blue = {color_data['blue']}")
                lines.append("")

        return "\n".join(lines)

    def _create_temp_file_from_content(self, content: str) -> str:
        """Create temporary file from AI content and return the path."""
        # Determine file extension based on training format
        file_extension = f".{AI_TRAINING_FORMAT}" if AI_TRAINING_FORMAT else ".toml"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=file_extension, delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
            self.log.info(f"Saved AI response to temp file: {tmp_path}")
            return tmp_path

    def _load_animated_ai_sprite(self, tmp_path: str) -> None:
        """Load animated AI sprite into canvas."""
        self.log.info("Loading animated sprite into existing animated canvas...")

        class MockEvent:
            def __init__(self, text):
                self.text = text

        mock_event = MockEvent(tmp_path)
        self.canvas.on_load_file_event(mock_event)

        # Ensure mini map is updated for animated sprites
        if hasattr(self.canvas, "mini_view") and self.canvas.mini_view is not None:
            self.canvas._update_mini_view_from_current_frame()
            self.canvas.mini_view.dirty = 1
            self.canvas.mini_view.force_redraw()

        # Animation will be started by on_load_file_event, no need to start here
        self.log.info("AI animated sprite loaded successfully")

    def _load_static_ai_sprite(self, tmp_path: str) -> None:
        """Load static AI sprite into canvas."""
        self.log.info("Loading static sprite into animated canvas...")

        # Load the static sprite into the current animated canvas
        class MockEvent:
            def __init__(self, text):
                self.text = text

        mock_event = MockEvent(tmp_path)
        self.canvas.on_load_file_event(mock_event)

        # Animation will be started by on_load_file_event, no need to start here
        # Just verify the state after loading
        if hasattr(self.canvas, "animated_sprite") and self.canvas.animated_sprite:
            self.log.debug(
                f"AI sprite loaded - animated_sprite state: "
                f"current_animation='{self.canvas.animated_sprite.current_animation}', "
                f"is_playing={self.canvas.animated_sprite.is_playing}"
            )
            animations = (
                list(self.canvas.animated_sprite._animations.keys())
                if hasattr(self.canvas.animated_sprite, "_animations")
                else "No _animations"
            )
            self.log.debug(f"AI sprite animations: {animations}")

            # Note: Live preview functionality is now integrated into the film strip

        # Force canvas redraw to show the new sprite
        self.canvas.dirty = 1
        self.canvas.force_redraw()

        # Update mini view to match the new canvas size
        if hasattr(self.canvas, "mini_view") and self.canvas.mini_view is not None:
            self.log.debug("Updating mini view for resized canvas")
            self.canvas.mini_view.pixels = self.canvas.pixels.copy()
            self.canvas.mini_view.dirty_pixels = [True] * len(self.canvas.pixels)
            self.canvas.mini_view.dirty = 1
            self.canvas.mini_view.force_redraw()

        # Also force a scene update to ensure everything is redrawn
        if hasattr(self, "all_sprites"):
            for sprite in self.all_sprites:
                if hasattr(sprite, "dirty"):
                    sprite.dirty = 1

        self.log.info("AI static sprite loaded successfully into animated canvas")

    def _update_ui_after_ai_load(self, request_id: str) -> None:
        """Update UI components after AI sprite load."""
        if hasattr(self, "debug_text"):
            # Restore the original prompt text that was submitted
            original_prompt = self.pending_ai_requests.get(
                request_id, "Enter a description of the sprite you want to create:"
            )
            self.debug_text.text = original_prompt

    def _cleanup_ai_request(self, request_id: str) -> None:
        """Clean up pending AI request."""
        # Clean up the pending request
        if request_id in self.pending_ai_requests:
            del self.pending_ai_requests[request_id]

    def _check_current_frame_has_content(self) -> bool:
        """Check if the current frame has any non-magenta pixels.

        Returns:
            True if frame has content (non-magenta pixels), False if all magenta

        """
        try:
            # Get current frame pixels
            if hasattr(self, "canvas") and hasattr(self.canvas, "pixels"):
                pixels = self.canvas.pixels
                self.log.debug(f"Checking frame content: {len(pixels)} pixels")
                if not pixels:
                    self.log.debug("No pixels found, returning False")
                    return False

                # Check if any pixel is not magenta (255, 0, 255)
                non_magenta_count = 0
                for i, pixel in enumerate(pixels):
                    if isinstance(pixel, tuple) and len(pixel) >= 3:
                        if pixel[:3] != (255, 0, 255):
                            non_magenta_count += 1
                            if non_magenta_count <= 5:  # Log first few non-magenta pixels
                                self.log.debug(f"Found non-magenta pixel {i}: {pixel[:3]}")
                    elif isinstance(pixel, int):
                        # Convert integer color to RGB
                        r = (pixel >> 16) & 0xFF
                        g = (pixel >> 8) & 0xFF
                        b = pixel & 0xFF
                        if (r, g, b) != (255, 0, 255):
                            non_magenta_count += 1
                            if non_magenta_count <= 5:  # Log first few non-magenta pixels
                                self.log.debug(f"Found non-magenta pixel {i}: ({r}, {g}, {b})")

                self.log.debug(f"Found {non_magenta_count} non-magenta pixels out of {len(pixels)} total")
                return non_magenta_count > 0
            else:
                self.log.debug("No canvas or canvas.pixels found, returning False")
                return False
        except Exception as e:
            self.log.error(f"Error checking frame content: {e}")
            return False

    def _save_current_frame_to_temp_toml(self) -> str | None:
        """Save the current frame to a temporary TOML file.

        Returns:
            Path to the temporary TOML file, or None if failed

        """
        try:
            import os
            import tempfile

            # Get current frame data
            if not hasattr(self, "canvas") or not hasattr(self.canvas, "pixels"):
                return None

            pixels = self.canvas.pixels
            if not pixels:
                return None

            # Create temporary file
            temp_fd, temp_path = tempfile.mkstemp(suffix=".toml", prefix="bitmappy_frame_")
            os.close(temp_fd)  # Close the file descriptor, we'll use the path

            # Generate TOML content with single-char glyphs only
            # This ensures the AI sees only single-character glyphs in the training data
            toml_content = self._generate_frame_toml_content(pixels, force_single_char_glyphs=True)

            # Write to temporary file
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(toml_content)

            self.log.info(f"Saved current frame to temporary TOML: {temp_path}")
            return temp_path

        except Exception as e:
            self.log.error(f"Error saving frame to temp TOML: {e}")
            return None

    def _save_current_strip_to_temp_toml(self) -> str | None:
        """Save the current animation strip to a temporary TOML file.

        Returns:
            Path to the temporary TOML file, or None if failed

        """
        try:
            import os
            import tempfile

            # Get current animation data
            if not hasattr(self, "canvas") or not hasattr(self.canvas, "animated_sprite"):
                return None

            animated_sprite = self.canvas.animated_sprite
            if not animated_sprite or not hasattr(animated_sprite, "_animations"):
                return None

            current_animation = getattr(self.canvas, "current_animation", None)
            if not current_animation or current_animation not in animated_sprite._animations:
                return None

            # Create a new AnimatedSprite with just the current animation
            from glitchygames.sprites.animated import AnimatedSprite

            # Get the current animation frames
            current_frames = animated_sprite._animations[current_animation]

            # Create new sprite with the current animation
            new_sprite = AnimatedSprite()
            new_sprite.name = f"current_strip_{current_animation}"
            new_sprite.description = f"Current animation strip: {current_animation}"

            # Copy the animation data
            new_sprite._animations = {current_animation: current_frames}
            new_sprite.current_animation = current_animation

            # Create temporary file
            temp_fd, temp_path = tempfile.mkstemp(suffix=".toml", prefix="bitmappy_strip_")
            os.close(temp_fd)  # Close the file descriptor, we'll use the path

            # Save the sprite to TOML using the existing save method
            new_sprite.save(temp_path)

            self.log.info(f"Saved current strip to temporary TOML: {temp_path}")
            return temp_path

        except Exception as e:
            self.log.error(f"Error saving strip to temp TOML: {e}")
            return None

    def _generate_frame_toml_content(self, pixels: list, force_single_char_glyphs: bool = False) -> str:
        """Generate TOML content for the current frame.

        Args:
            pixels: List of pixel colors
            force_single_char_glyphs: If True, limit to 64 single-character glyphs for AI training

        Returns:
            TOML content string

        """
        try:
            # Get canvas dimensions
            width = self.canvas.pixels_across
            height = self.canvas.pixels_tall

            # First pass: collect all unique colors
            unique_colors = set()
            for pixel in pixels:
                if isinstance(pixel, tuple) and len(pixel) >= 3:
                    color = pixel[:3]
                elif isinstance(pixel, int):
                    r = (pixel >> 16) & 0xFF
                    g = (pixel >> 8) & 0xFF
                    b = pixel & 0xFF
                    color = (r, g, b)
                else:
                    color = (255, 0, 255)  # Default magenta
                unique_colors.add(color)

            # If forcing single-char glyphs and we have too many colors, quantize
            if force_single_char_glyphs and len(unique_colors) > 64:
                self.log.info(f"Quantizing {len(unique_colors)} colors down to 64 for AI training")
                # Use simple color quantization: pick the 64 most common colors
                color_counts = {}
                for pixel in pixels:
                    if isinstance(pixel, tuple) and len(pixel) >= 3:
                        color = pixel[:3]
                    elif isinstance(pixel, int):
                        r = (pixel >> 16) & 0xFF
                        g = (pixel >> 8) & 0xFF
                        b = pixel & 0xFF
                        color = (r, g, b)
                    else:
                        color = (255, 0, 255)
                    color_counts[color] = color_counts.get(color, 0) + 1

                # Sort by frequency and take top 64
                sorted_by_frequency = sorted(color_counts.items(), key=lambda x: x[1], reverse=True)
                unique_colors = set([color for color, _ in sorted_by_frequency[:64]])
                self.log.info(f"Quantized to {len(unique_colors)} colors")

            # Create consistent color-to-glyph mapping
            color_to_glyph = {}
            available_glyphs = list(SPRITE_GLYPHS[:64])

            # Sort colors to ensure consistent ordering
            sorted_colors = sorted(unique_colors)

            for i, color in enumerate(sorted_colors):
                if i < len(available_glyphs):
                    color_to_glyph[color] = available_glyphs[i]
                else:
                    # If we run out of glyphs, log a warning (should not happen if force_single_char_glyphs=True)
                    if force_single_char_glyphs:
                        self.log.warning(f"Ran out of single-char glyphs at color {i}, this should not happen!")
                    color_to_glyph[color] = f"X{i-len(available_glyphs)+1}"

            # Second pass: generate pixel string
            pixel_string = ""
            for y in range(height):
                for x in range(width):
                    pixel_index = y * width + x
                    if pixel_index < len(pixels):
                        pixel = pixels[pixel_index]

                        # Convert pixel to color tuple
                        if isinstance(pixel, tuple) and len(pixel) >= 3:
                            color = pixel[:3]
                        elif isinstance(pixel, int):
                            r = (pixel >> 16) & 0xFF
                            g = (pixel >> 8) & 0xFF
                            b = pixel & 0xFF
                            color = (r, g, b)
                        else:
                            color = (255, 0, 255)  # Default magenta

                        # Get glyph for this color
                        if color in color_to_glyph:
                            glyph = color_to_glyph[color]
                        else:
                            # If quantized, find nearest color in palette
                            if force_single_char_glyphs:
                                min_distance = float("inf")
                                closest_color = sorted_colors[0]
                                for palette_color in sorted_colors:
                                    r1, g1, b1 = color
                                    r2, g2, b2 = palette_color
                                    distance = (r1 - r2)**2 + (g1 - g2)**2 + (b1 - b2)**2
                                    if distance < min_distance:
                                        min_distance = distance
                                        closest_color = palette_color
                                glyph = color_to_glyph[closest_color]
                            else:
                                # Should not happen, but fallback to first glyph
                                glyph = available_glyphs[0]

                        pixel_string += glyph
                    else:
                        pixel_string += "."  # Default empty glyph

                if y < height - 1:  # Add newline except for last row
                    pixel_string += "\n"

            # Generate color definitions using the consistent mapping
            color_definitions = ""
            for color in sorted_colors:
                if isinstance(color, tuple) and len(color) >= 3:
                    r, g, b = color[:3]
                    glyph = color_to_glyph[color]
                    color_definitions += f'[colors."{glyph}"]\nred = {r}\ngreen = {g}\nblue = {b}\n\n'

            # Build complete TOML
            toml_content = f"""[sprite]
name = "current_frame"
pixels = \"\"\"
{pixel_string}
\"\"\"

{color_definitions}"""

            return toml_content

        except Exception as e:
            self.log.error(f"Error generating frame TOML content: {e}")
            return ""

    def _get_glyph_for_color(self, color: tuple[int, int, int] | int) -> str:
        """Get a glyph for a specific color.

        Args:
            color: RGB color tuple or integer color value

        Returns:
            Single character glyph from first 64 characters of SPRITE_GLYPHS

        """
        # Use only first 64 characters for consistent, manageable palette
        available_glyphs = SPRITE_GLYPHS[:64]
        # Simple hash-based assignment to ensure consistent glyph for same color
        color_hash = hash(color) % len(available_glyphs)
        return available_glyphs[color_hash]

    def _load_temp_toml_as_example(self, temp_toml_path: str) -> dict | None:
        """Load a temporary TOML file as a training example.

        Args:
            temp_toml_path: Path to the temporary TOML file

        Returns:
            Training example dict, or None if failed

        """
        try:
            import toml

            # Read the file as text first to preserve newlines
            with open(temp_toml_path, "r", encoding="utf-8") as f:
                file_content = f.read()

            # Extract pixel data directly from the text to preserve newlines
            pixels_data = ""
            in_pixels_section = False
            for line in file_content.split("\n"):
                if line.strip() == 'pixels = """':
                    in_pixels_section = True
                    continue
                elif line.strip() == '"""' and in_pixels_section:
                    in_pixels_section = False
                    break
                elif in_pixels_section:
                    pixels_data += line + "\n"

            # Remove the trailing newline
            if pixels_data.endswith("\n"):
                pixels_data = pixels_data[:-1]

            # Load the TOML file for other data (colors, etc.)
            with open(temp_toml_path, "r", encoding="utf-8") as f:
                config_data = toml.load(f)

            # Convert to training example format
            sprite_data = {
                "name": config_data.get("sprite", {}).get("name", "current_frame"),
                "sprite_type": "static",
                "pixels": pixels_data,  # Use the directly extracted pixel data
                "colors": config_data.get("colors", {})
            }

            # Clean up temporary file
            import os
            try:
                os.unlink(temp_toml_path)
                self.log.debug(f"Cleaned up temporary file: {temp_toml_path}")
            except Exception as cleanup_error:
                self.log.warning(f"Failed to clean up temp file {temp_toml_path}: {cleanup_error}")

            self.log.info(f"Loaded current frame as training example: {sprite_data['name']}")
            return sprite_data

        except Exception as e:
            self.log.error(f"Error loading temp TOML as example: {e}")
            return None

    def _load_ai_sprite(self, request_id: str, content: str) -> None:
        """Load sprite from AI content using SpriteFactory APIs."""
        # Log AI response content for debugging
        self._log_ai_response_content(content)

        # Check if this is an error message
        if content.strip() in ["AI features not available", "AI features not available."]:
            self.log.warning("AI returned error message, cannot load sprite")
            if hasattr(self, "debug_text"):
                self.debug_text.text = "AI features not available. Please check your AI configuration."
            # Clean up pending request
            self._cleanup_ai_request(request_id)
            return

        # Prepare AI content (clean and add description if needed)
        cleaned_content = self._prepare_ai_content(request_id, content)

        # Get the original prompt to update sprite description
        original_prompt = ""
        if request_id in self.pending_ai_requests:
            original_prompt = self.pending_ai_requests[request_id]

        # Create temporary file from content
        tmp_path = self._create_temp_file_from_content(cleaned_content)

        # Detect sprite type and load appropriately
        try:
            self.log.info("Detecting AI sprite type...")

            # Use SpriteFactory to detect the sprite type
            sprite = SpriteFactory.load_sprite(filename=tmp_path)
            is_animated = hasattr(sprite, "_animations") and sprite._animations
            self.log.info(f"AI sprite type: {'Animated' if is_animated else 'Static'}")
            self.log.debug(f"AI sprite has _animations: {hasattr(sprite, '_animations')}")
            if hasattr(sprite, "_animations"):
                self.log.debug(f"AI sprite _animations: {list(sprite._animations.keys())}")
                self.log.debug(f"AI sprite current_animation: {sprite.current_animation}")
                self.log.debug(f"AI sprite is_playing: {sprite.is_playing}")

            # Load sprite based on type
            if is_animated:
                self._load_animated_ai_sprite(tmp_path)
            else:
                self._load_static_ai_sprite(tmp_path)

            # Update the sprite's description with the original prompt
            if original_prompt and hasattr(self, "canvas") and self.canvas and hasattr(self.canvas, "animated_sprite") and self.canvas.animated_sprite:
                self.canvas.animated_sprite.description = original_prompt
                self.log.info(f"Updated sprite description with generation prompt: '{original_prompt}'")

            # Update UI components
            self._update_ui_after_ai_load(request_id)

            # Clean up pending request
            self._cleanup_ai_request(request_id)

        except Exception as sprite_error:
            self.log.error("Failed to load AI sprite")
            if hasattr(self, "debug_text"):
                self.debug_text.text = f"Error loading AI sprite: {sprite_error}"
        # Note: Temp file is kept for debugging - remove this comment when done debugging

    def _clean_ai_response(self, content: str) -> str:
        """Clean up markdown formatting from AI response."""
        # Check if this is an error message instead of valid content
        if content.strip() in ["AI features not available", "AI features not available."]:
            self.log.warning("AI returned error message instead of sprite content")
            return content  # Return as-is for error handling upstream

        cleaned_content = content

        # Handle various markdown code block patterns
        markdown_patterns = [
            ("```toml", "```"),
            ("```", "```"),
            ("```ini", "```"),
        ]

        for start_marker, end_marker in markdown_patterns:
            if start_marker in content:
                start_idx = content.find(start_marker)
                if start_idx != -1:
                    start_idx += len(start_marker)
                    end_idx = content.find(end_marker, start_idx)
                    if end_idx != -1:
                        cleaned_content = content[start_idx:end_idx].strip()
                        self.log.info(
                            f"Extracted content from markdown code block ({start_marker})"
                        )
                        break

        # Remove any remaining markdown artifacts
        if cleaned_content.startswith("```") or cleaned_content.endswith("```"):
            cleaned_content = cleaned_content.strip("`")

        # Remove any explanatory text before the actual content
        lines = cleaned_content.split("\n")
        content_start = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("[") and ("sprite" in line or "animation" in line):
                content_start = i
                break
        return "\n".join(lines[content_start:])

    def update(self):
        """Update scene state."""
        super().update()  # Call the base Scene.update() method

        # Update continuous slider adjustments
        self._update_slider_continuous_adjustments()

        # Update continuous canvas movements
        self._update_canvas_continuous_movements()

        # Check for single click timer
        self._check_single_click_timer()

        # Update the animated canvas with delta time
        if (
            hasattr(self, "canvas")
            and hasattr(self.canvas, "animated_sprite")
            and self.canvas.animated_sprite
        ):
            # Debug animation state
            if hasattr(self, "_debug_animation_counter"):
                self._debug_animation_counter += 1
            else:
                self._debug_animation_counter = 1

            # Log animation state approximately once per second, regardless of fps
            if not hasattr(self, "_last_animation_log_time"):
                self._last_animation_log_time = time.time()
            current_time = time.time()
            if current_time - self._last_animation_log_time >= 1.0:
                self._last_animation_log_time = current_time

            # Pass delta time to the canvas for animation updates
            self.canvas.update_animation(self.dt)

            # CRITICAL: Update film strip preview animations for backward compatibility
            # This handles the legacy single film strip case (canvas.film_strip)
            # NOTE: The main animation updates now happen in the scene update loop
            # for better performance and cleaner separation of concerns
            if (
                hasattr(self.canvas, "film_strip")
                and self.canvas.film_strip
                and hasattr(self.canvas, "film_strip_sprite")
                and self.canvas.film_strip_sprite
            ):
                self.canvas.film_strip.update_animations(self.dt)
                # Mark film strip sprite as dirty to redraw with new animation frames
                # Always mark as dirty when animations are present to ensure continuous updates
                if (
                    hasattr(self.canvas.film_strip, "animated_sprite")
                    and self.canvas.film_strip.animated_sprite
                    and len(self.canvas.film_strip.animated_sprite._animations) > 0
                ):
                    self.canvas.film_strip_sprite.dirty = 2

            # Update multiple film strip animations (new multi-strip system)
            # This ensures each film strip has its own independent animation timing
            if hasattr(self, "film_strips") and self.film_strips:
                for film_strip in self.film_strips.values():
                    if hasattr(film_strip, "update_animations"):
                        film_strip.update_animations(self.dt)

            # Mark all film strip sprites as dirty for animation updates (every frame)
            # This ensures the sprite group redraws film strips when animations advance
            if hasattr(self, "film_strip_sprites") and self.film_strip_sprites:
                for film_strip_sprite in self.film_strip_sprites.values():
                    film_strip_sprite.dirty = 1

            # Also mark film strip sprites as dirty for continuous animation updates
            # This is a backup mechanism to ensure film strips stay dirty when needed
            self._mark_film_strip_sprites_dirty()

            # Mark the main scene as dirty every frame to ensure sprite groups are updated
            self.dirty = 1

            # Render visual indicators for multi-controller system
            self._render_visual_indicators()

            # Debug: Check if film strip sprites are being updated
            if hasattr(self, "film_strip_sprites") and self.film_strip_sprites:
                for anim_name, film_strip_sprite in self.film_strip_sprites.items():
                    if hasattr(film_strip_sprite, "dirty") and film_strip_sprite.dirty:
                        pass

            # Check for frame transitions
            frame_index = self.canvas.animated_sprite.current_frame

            if (
                not hasattr(self, "_last_animation_frame")
                or self._last_animation_frame != frame_index
            ):
                self._last_animation_frame = frame_index

                # Don't update the canvas frame - it should stay on the frame being edited
                # Only the live preview should animate

                # Note: Live preview functionality is now integrated into the film strip

        # Check for AI responses
        if hasattr(self, "ai_response_queue") and self.ai_response_queue:
            try:
                response_data = self.ai_response_queue.get_nowait()

                if response_data:
                    request_id, response = response_data
                    self._process_ai_response(request_id, response)

            except Empty:
                # This is normal - no responses available
                pass
            except Exception:
                self.log.error("Error processing AI response")

    def _shutdown_ai_worker(self) -> None:
        """Signal AI worker to shut down."""
        if hasattr(self, "ai_request_queue") and self.ai_request_queue:
            try:
                self.log.info("Sending shutdown signal to AI worker...")
                self.ai_request_queue.put(None, timeout=1.0)  # Add timeout
                self.log.info("Shutdown signal sent successfully")
            except Exception:
                self.log.error("Error sending shutdown signal")

    def _cleanup_ai_process(self) -> None:
        """Clean up AI process."""
        if not hasattr(self, "ai_process") or not self.ai_process:
            return

        try:
            self.log.info("Waiting for AI process to finish...")
            self.ai_process.join(timeout=2.0)  # Increased timeout
            if self.ai_process.is_alive():
                self.log.info("AI process still alive, terminating...")
                self.ai_process.terminate()
                self.ai_process.join(timeout=1.0)  # Longer timeout for terminate
                if self.ai_process.is_alive():
                    self.log.info("AI process still alive, force killing...")
                    self.ai_process.kill()  # Force kill if still alive
                    self.ai_process.join(timeout=0.5)  # Final cleanup
            self.log.info("AI process cleanup completed")
        except Exception:
            self.log.error("Error during AI process cleanup")
        finally:
            # Ensure process is cleaned up
            if hasattr(self, "ai_process") and self.ai_process:
                try:
                    if self.ai_process.is_alive():
                        self.log.info("Force killing remaining AI process...")
                        self.ai_process.kill()
                except (OSError, AttributeError, RuntimeError):
                    self.log.debug("Error during final AI process cleanup (ignored)")

    def _cleanup_queues(self) -> None:
        """Clean up AI queues."""
        if hasattr(self, "ai_request_queue") and self.ai_request_queue:
            try:
                self.ai_request_queue.close()
                self.log.info("AI request queue closed")
            except Exception:
                self.log.error("Error closing request queue")

        if hasattr(self, "ai_response_queue") and self.ai_response_queue:
            try:
                self.ai_response_queue.close()
                self.log.info("AI response queue closed")
            except Exception:
                self.log.error("Error closing response queue")

    def _cleanup_voice_recognition(self) -> None:
        """Clean up voice recognition resources."""
        if hasattr(self, "voice_manager") and self.voice_manager:
            try:
                self.log.info("Stopping voice recognition...")
                self.voice_manager.stop_listening()
                self.voice_manager = None
                self.log.info("Voice recognition stopped successfully")
            except Exception:
                self.log.error("Error stopping voice recognition")

    def cleanup(self):
        """Clean up resources."""
        self.log.info("Starting AI cleanup...")

        self._shutdown_ai_worker()
        self._cleanup_ai_process()
        self._cleanup_queues()

        # Clean up voice recognition
        self._cleanup_voice_recognition()

        super().cleanup()

    def on_key_up_event(self, event: pygame.event.Event) -> None:
        """Handle key release events."""
        # Get modifier keys
        mod = event.mod if hasattr(event, 'mod') else 0

        # Check if this is a Ctrl+Shift+Arrow key release
        if (mod & pygame.KMOD_CTRL) and (mod & pygame.KMOD_SHIFT) and hasattr(self, "canvas") and self.canvas:
            if event.key in [pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN]:
                self.log.debug(f"Ctrl+Shift+Arrow key released - committing panned buffer")
                self._commit_panned_buffer()
                return

        # Call parent class handler
        super().on_key_up_event(event)

    def _commit_panned_buffer(self) -> None:
        """Commit the panned buffer back to the real frame data."""
        if not hasattr(self, "canvas") or not self.canvas:
            return

        # Get current frame key
        frame_key = self.canvas._get_current_frame_key()

        # Check if this frame has active panning
        if frame_key not in self.canvas._frame_panning:
            self.log.debug("No panning state for current frame")
            return

        frame_state = self.canvas._frame_panning[frame_key]
        if not frame_state['active']:
            self.log.debug("No active panning to commit")
            return

        # Commit the current panned pixels back to the frame
        if hasattr(self.canvas, 'animated_sprite') and self.canvas.animated_sprite:
            current_animation = self.canvas.current_animation
            current_frame = self.canvas.current_frame


            if current_animation in self.canvas.animated_sprite._animations and current_frame < len(self.canvas.animated_sprite._animations[current_animation]):
                frame = self.canvas.animated_sprite._animations[current_animation][current_frame]
                if hasattr(frame, 'pixels'):
                    # The current self.canvas.pixels already has the panned view
                    frame.pixels = list(self.canvas.pixels)

                    # Also update the frame.image surface for film strip thumbnails with alpha support
                    surface = pygame.Surface((self.canvas.pixels_across, self.canvas.pixels_tall), pygame.SRCALPHA)
                    for y in range(self.canvas.pixels_tall):
                        for x in range(self.canvas.pixels_across):
                            pixel_num = y * self.canvas.pixels_across + x
                            if pixel_num < len(self.canvas.pixels):
                                color = self.canvas.pixels[pixel_num]
                                surface.set_at((x, y), color)

                    # Update the frame's image
                    frame.image = surface
                    self.log.debug(f"Committed panned pixels and image to frame {current_animation}[{current_frame}]")

                # Update the film strip's animated sprite frame data as well
                if hasattr(self, "film_strips") and self.film_strips:
                    if current_animation in self.film_strips:
                        film_strip = self.film_strips[current_animation]
                        if hasattr(film_strip, "animated_sprite") and film_strip.animated_sprite:
                            # Update the film strip's animated sprite frame data
                            if (current_animation in film_strip.animated_sprite._animations and
                                current_frame < len(film_strip.animated_sprite._animations[current_animation])):
                                film_strip_frame = film_strip.animated_sprite._animations[current_animation][current_frame]
                                if hasattr(film_strip_frame, 'pixels'):
                                    film_strip_frame.pixels = list(self.canvas.pixels)

                                    # Also update the film strip frame's image surface with alpha support
                                    film_strip_surface = pygame.Surface((self.canvas.pixels_across, self.canvas.pixels_tall), pygame.SRCALPHA)
                                    for y in range(self.canvas.pixels_tall):
                                        for x in range(self.canvas.pixels_across):
                                            pixel_num = y * self.canvas.pixels_across + x
                                            if pixel_num < len(self.canvas.pixels):
                                                color = self.canvas.pixels[pixel_num]
                                                film_strip_surface.set_at((x, y), color)

                                    # Update the film strip frame's image
                                    film_strip_frame.image = film_strip_surface
                                    self.log.debug(f"Updated film strip animated sprite frame {current_animation}[{current_frame}] with pixels and image")

                # Update the film strip to reflect the pixel data changes
                self._update_film_strips_for_animated_sprite_update()
                self.log.debug(f"Updated film strip for frame {current_animation}[{current_frame}]")

        # Keep the panning state active so user can continue panning
        # Don't clear _original_frame_pixels, pan_offset_x, pan_offset_y, or _panning_active
        # The viewport will continue to show the panned view

        self.log.debug("Panned buffer committed, panning state preserved for continued panning")

    def on_key_down_event(self, event: pygame.event.Event) -> None:
        """Handle keyboard events for frame navigation and text input."""
        self.log.debug(f"Key down event received: key={event.key}")

        # Check if debug text box is active and handle text input
        if hasattr(self, "debug_text") and self.debug_text.active:
            self.debug_text.on_key_down_event(event)
            return

        # Check if any slider text box is active and handle text input
        if hasattr(self, "red_slider") and hasattr(self.red_slider, "text_sprite") and self.red_slider.text_sprite.active:
            self.red_slider.text_sprite.on_key_down_event(event)
            # If escape was pressed, consume the event to prevent game quit
            if event.key == pygame.K_ESCAPE:
                return True
            return
        if hasattr(self, "green_slider") and hasattr(self.green_slider, "text_sprite") and self.green_slider.text_sprite.active:
            self.green_slider.text_sprite.on_key_down_event(event)
            # If escape was pressed, consume the event to prevent game quit
            if event.key == pygame.K_ESCAPE:
                return True
            return
        if hasattr(self, "blue_slider") and hasattr(self.blue_slider, "text_sprite") and self.blue_slider.text_sprite.active:
            self.blue_slider.text_sprite.on_key_down_event(event)
            # If escape was pressed, consume the event to prevent game quit
            if event.key == pygame.K_ESCAPE:
                return True
            return

        # Handle onion skinning keyboard shortcuts
        if event.key == pygame.K_o:
            self.log.debug("O key pressed - toggling global onion skinning")
            from .onion_skinning import get_onion_skinning_manager
            onion_manager = get_onion_skinning_manager()
            new_state = onion_manager.toggle_global_onion_skinning()
            print(f"Onion skinning {'enabled' if new_state else 'disabled'}")
            # Force canvas redraw to show/hide onion skinning
            if hasattr(self, "canvas") and self.canvas:
                self.canvas.force_redraw()
            return

        # Handle undo/redo keyboard shortcuts
        # Get modifier keys from HashableEvent (which wraps pygame events)
        mod = getattr(event, 'mod', 0)

        if event.key == pygame.K_z and (mod & pygame.KMOD_CTRL):
            if mod & pygame.KMOD_SHIFT:
                # Ctrl+Shift+Z: Redo
                self.log.debug("Ctrl+Shift+Z pressed - redo")
                self._handle_redo()
            else:
                # Ctrl+Z: Undo
                self.log.debug("Ctrl+Z pressed - undo")
                self._handle_undo()
            return

        # Handle Ctrl+Y for redo (alternative shortcut)
        if event.key == pygame.K_y and (mod & pygame.KMOD_CTRL):
            self.log.debug("Ctrl+Y pressed - redo")
            self._handle_redo()
            return

        # Handle copy/paste keyboard shortcuts
        if event.key == pygame.K_c and (mod & pygame.KMOD_CTRL):
            self.log.debug("Ctrl+C pressed - copying frame")
            self._handle_copy_frame()
            return
        elif event.key == pygame.K_v and (mod & pygame.KMOD_CTRL):
            self.log.debug("Ctrl+V pressed - pasting frame")
            self._handle_paste_frame()
            return

        # Handle panning with Ctrl+Shift+Arrow keys
        if (mod & pygame.KMOD_CTRL) and (mod & pygame.KMOD_SHIFT) and hasattr(self, "canvas") and self.canvas:
            if event.key == pygame.K_LEFT:
                self.log.debug("Ctrl+Shift+LEFT arrow pressed - panning left")
                self._handle_canvas_panning(-1, 0)
                return
            elif event.key == pygame.K_RIGHT:
                self.log.debug("Ctrl+Shift+RIGHT arrow pressed - panning right")
                self._handle_canvas_panning(1, 0)
                return
            elif event.key == pygame.K_UP:
                self.log.debug("Ctrl+Shift+UP arrow pressed - panning up")
                self._handle_canvas_panning(0, -1)
                return
            elif event.key == pygame.K_DOWN:
                self.log.debug("Ctrl+Shift+DOWN arrow pressed - panning down")
                self._handle_canvas_panning(0, 1)
                return

        # Check if any controller is in slider mode for arrow key navigation
        any_controller_in_slider_mode = False
        if hasattr(self, 'mode_switcher'):
            for controller_id in self.mode_switcher.controller_modes:
                controller_mode = self.mode_switcher.get_controller_mode(controller_id)
                if controller_mode and controller_mode.value in ["r_slider", "g_slider", "b_slider"]:
                    any_controller_in_slider_mode = True
                    break


        # Handle slider mode navigation with arrow keys
        if any_controller_in_slider_mode:
            if event.key == pygame.K_UP:
                self.log.debug("UP arrow pressed - navigating to previous slider mode")
                self._handle_slider_mode_navigation("up")
                return
            elif event.key == pygame.K_DOWN:
                self.log.debug("DOWN arrow pressed - navigating to next slider mode")
                self._handle_slider_mode_navigation("down")
            return

        # Handle animation navigation and film strip scrolling (UP/DOWN arrows)
        if event.key == pygame.K_UP:
            self.log.debug("UP arrow pressed - navigating to previous animation")
            if hasattr(self, "canvas") and self.canvas:
                # Navigate to previous animation
                self.canvas.previous_animation()

                # Check if we need to scroll the film strip view to show the selected animation
                self._scroll_to_current_animation()
            return
        elif event.key == pygame.K_DOWN:
            self.log.debug("DOWN arrow pressed - navigating to next animation")
            if hasattr(self, "canvas") and self.canvas:
                # Navigate to next animation
                self.canvas.next_animation()

                # Check if we need to scroll the film strip view to show the selected animation
                self._scroll_to_current_animation()
            return

        # Check if we have an animated canvas (only if not in slider mode)
        if not any_controller_in_slider_mode:
            if hasattr(self, "canvas") and hasattr(self.canvas, "handle_keyboard_event"):
                self.log.debug("Routing keyboard event to canvas")
                self.canvas.handle_keyboard_event(event.key)
            else:
                # Fall back to parent class handling
                self.log.debug("No canvas found, using parent class handling")
                super().on_key_down_event(event)

    def _handle_undo(self) -> None:
        """Handle undo operation."""
        if not hasattr(self, 'undo_redo_manager'):
            self.log.warning("Undo/redo manager not initialized")
            return

        # Get current frame information
        current_animation = None
        current_frame = None
        if hasattr(self, "canvas") and self.canvas:
            current_animation = getattr(self.canvas, "current_animation", None)
            current_frame = getattr(self.canvas, "current_frame", None)

        # Try frame-specific undo first if we have a current frame
        if current_animation is not None and current_frame is not None:
            if self.undo_redo_manager.can_undo_frame(current_animation, current_frame):
                success = self.undo_redo_manager.undo_frame(current_animation, current_frame)
                if success:
                    self.log.info(f"Frame-specific undo successful for {current_animation}[{current_frame}]")
                    # Force canvas redraw to show the undone changes
                    if hasattr(self, "canvas") and self.canvas:
                        self.canvas.force_redraw()
                    return
                else:
                    self.log.warning(f"Frame-specific undo failed for {current_animation}[{current_frame}]")
            else:
                self.log.warning("No frame-specific undo operations available")

        # Fall back to global undo for film strip operations
        if self.undo_redo_manager.can_undo():
            success = self.undo_redo_manager.undo()
            if success:
                self.log.info("Global undo successful")

                # CRITICAL: Ensure canvas state is valid after film strip operations
                self._synchronize_canvas_state_after_undo()

                # Force canvas redraw to show the undone changes
                if hasattr(self, "canvas") and self.canvas:
                    self.canvas.force_redraw()
            else:
                self.log.warning("Global undo failed")
        else:
            self.log.debug("No operations available to undo")

    def _synchronize_canvas_state_after_undo(self) -> None:
        """Synchronize canvas state after undo operations to prevent invalid states.

        This method ensures that:
        1. The canvas is pointing to a valid animation
        2. The canvas is pointing to a valid frame index
        3. The canvas state is consistent with the current animation structure
        """
        if not hasattr(self, "canvas") or not self.canvas:
            self.log.warning("No canvas available for state synchronization")
            return

        if not hasattr(self.canvas, "animated_sprite") or not self.canvas.animated_sprite:
            self.log.warning("No animated sprite available for state synchronization")
            return

        animations = self.canvas.animated_sprite._animations
        current_animation = getattr(self.canvas, "current_animation", None)
        current_frame = getattr(self.canvas, "current_frame", None)

        self.log.debug(f"Canvas state before sync: animation={current_animation}, frame={current_frame}")
        self.log.debug(f"Available animations: {list(animations.keys())}")

        # Check if current animation still exists
        if current_animation not in animations:
            self.log.warning(f"Current animation '{current_animation}' no longer exists, switching to first available")
            if animations:
                # Switch to the first available animation
                first_animation = list(animations.keys())[0]
                self.canvas.show_frame(first_animation, 0)
                self.log.info(f"Switched to animation '{first_animation}', frame 0")
                return
            else:
                self.log.error("No animations available - this should not happen")
                return

        # Check if current frame index is valid
        frames = animations[current_animation]
        if current_frame is None or current_frame < 0 or current_frame >= len(frames):
            self.log.warning(f"Current frame {current_frame} is invalid for animation '{current_animation}' with {len(frames)} frames")
            # Switch to the last valid frame
            valid_frame = max(0, len(frames) - 1)
            self.canvas.show_frame(current_animation, valid_frame)
            self.log.info(f"Switched to frame {valid_frame} of animation '{current_animation}'")
            return

        # If we get here, the canvas state is valid
        self.log.debug(f"Canvas state is valid: animation='{current_animation}', frame={current_frame}")

        # Force a complete canvas refresh to ensure everything is in sync
        self.canvas.force_redraw()

        # Update film strips to reflect the current state
        if hasattr(self, "_update_film_strips_for_frame"):
            self._update_film_strips_for_frame(current_animation, current_frame)

    def _handle_redo(self) -> None:
        """Handle redo operation."""
        if not hasattr(self, 'undo_redo_manager'):
            self.log.warning("Undo/redo manager not initialized")
            return

        # Get current frame information
        current_animation = None
        current_frame = None
        if hasattr(self, "canvas") and self.canvas:
            current_animation = getattr(self.canvas, "current_animation", None)
            current_frame = getattr(self.canvas, "current_frame", None)

        # Try frame-specific redo first if we have a current frame
        if current_animation is not None and current_frame is not None:
            if self.undo_redo_manager.can_redo_frame(current_animation, current_frame):
                success = self.undo_redo_manager.redo_frame(current_animation, current_frame)
                if success:
                    self.log.info(f"Frame-specific redo successful for {current_animation}[{current_frame}]")
                    # Force canvas redraw to show the redone changes
                    if hasattr(self, "canvas") and self.canvas:
                        self.canvas.force_redraw()
                    return
                else:
                    self.log.warning(f"Frame-specific redo failed for {current_animation}[{current_frame}]")
            else:
                self.log.warning("No frame-specific redo operations available")

        # Fall back to global redo for film strip operations
        if self.undo_redo_manager.can_redo():
            success = self.undo_redo_manager.redo()
            if success:
                self.log.info("Global redo successful")

                # CRITICAL: Ensure canvas state is valid after film strip operations
                self._synchronize_canvas_state_after_undo()

                # Force canvas redraw to show the redone changes
                if hasattr(self, "canvas") and self.canvas:
                    self.canvas.force_redraw()
            else:
                self.log.warning("Global redo failed")
        else:
            self.log.debug("No operations available to redo")

    def _handle_canvas_panning(self, delta_x: int, delta_y: int) -> None:
        """Handle canvas panning with the given delta values.

        Args:
            delta_x: Horizontal panning delta (-1, 0, or 1)
            delta_y: Vertical panning delta (-1, 0, or 1)
        """
        if not hasattr(self, "canvas") or not self.canvas:
            self.log.warning("No canvas available for panning")
            return

        # Delegate to canvas panning method
        if hasattr(self.canvas, "pan_canvas"):
            self.canvas.pan_canvas(delta_x, delta_y)
        else:
            self.log.warning("Canvas does not support panning")

    def _handle_copy_frame(self) -> None:
        """Handle copying the current frame to clipboard."""
        if not hasattr(self, "canvas") or not self.canvas:
            self.log.warning("No canvas available for frame copying")
            return

        if not hasattr(self, "selected_animation") or not hasattr(self, "selected_frame"):
            self.log.warning("No frame selected for copying")
            return

        animation = self.selected_animation
        frame = self.selected_frame

        if not hasattr(self.canvas, "animated_sprite") or not self.canvas.animated_sprite:
            self.log.warning("No animated sprite available for frame copying")
            return

        # Get the frame data
        if animation not in self.canvas.animated_sprite._animations:
            self.log.warning(f"Animation '{animation}' not found for copying")
            return

        frames = self.canvas.animated_sprite._animations[animation]
        if frame >= len(frames):
            self.log.warning(f"Frame {frame} not found in animation '{animation}'")
            return

        frame_obj = frames[frame]

        # Create a deep copy of the frame data for the clipboard
        from copy import deepcopy
        import pygame

        # Get pixel data
        pixels = frame_obj.get_pixel_data()

        # Get frame dimensions
        width, height = frame_obj.get_size()

        # Get frame duration
        duration = frame_obj.duration

        # Store frame data in clipboard
        self._frame_clipboard = {
            "pixels": pixels.copy(),
            "width": width,
            "height": height,
            "duration": duration,
            "animation": animation,
            "frame": frame
        }

        self.log.debug(f"Copied frame {frame} from animation '{animation}' to clipboard")

    def _handle_paste_frame(self) -> None:
        """Handle pasting a frame from clipboard to the current frame."""
        if not hasattr(self, "canvas") or not self.canvas:
            self.log.warning("No canvas available for frame pasting")
            return

        if not hasattr(self, "selected_animation") or not hasattr(self, "selected_frame"):
            self.log.warning("No frame selected for pasting")
            return

        if not self._frame_clipboard:
            self.log.warning("No frame data in clipboard to paste")
            return

        animation = self.selected_animation
        frame = self.selected_frame

        if not hasattr(self.canvas, "animated_sprite") or not self.canvas.animated_sprite:
            self.log.warning("No animated sprite available for frame pasting")
            return

        # Get the target frame
        if animation not in self.canvas.animated_sprite._animations:
            self.log.warning(f"Animation '{animation}' not found for pasting")
            return

        frames = self.canvas.animated_sprite._animations[animation]
        if frame >= len(frames):
            self.log.warning(f"Frame {frame} not found in animation '{animation}'")
            return

        target_frame = frames[frame]

        # Check if dimensions match
        clipboard_width = self._frame_clipboard["width"]
        clipboard_height = self._frame_clipboard["height"]
        target_width, target_height = target_frame.get_size()

        if clipboard_width != target_width or clipboard_height != target_height:
            self.log.warning(f"Cannot paste frame: dimension mismatch (clipboard: {clipboard_width}x{clipboard_height}, target: {target_width}x{target_height})")
            return

        # Create undo/redo operation for the paste
        from glitchygames.tools.undo_redo_manager import OperationType

        # Store original frame data for undo
        original_pixels = target_frame.get_pixel_data()
        original_duration = target_frame.duration

        # Apply the paste operation
        self._apply_frame_paste_for_undo_redo(
            animation, frame,
            self._frame_clipboard["pixels"],
            self._frame_clipboard["duration"]
        )

        # Add to undo stack
        self.undo_redo_manager.add_operation(
            operation_type=OperationType.FRAME_PASTE,
            description=f"Paste frame from {self._frame_clipboard['animation']}[{self._frame_clipboard['frame']}] to {animation}[{frame}]",
            undo_data={
                "animation": animation,
                "frame": frame,
                "pixels": original_pixels,
                "duration": original_duration
            },
            redo_data={
                "animation": animation,
                "frame": frame,
                "pixels": self._frame_clipboard["pixels"],
                "duration": self._frame_clipboard["duration"]
            }
        )

        # Update canvas display
        if hasattr(self.canvas, "force_redraw"):
            self.canvas.force_redraw()

        self.log.debug(f"Pasted frame from clipboard to {animation}[{frame}]")

    def _apply_frame_paste_for_undo_redo(self, animation: str, frame: int, pixels: list, duration: float) -> bool:
        """Apply frame paste for undo/redo operations.

        Args:
            animation: Name of the animation
            frame: Frame index
            pixels: Pixel data to apply
            duration: Frame duration

        Returns:
            True if successful, False otherwise
        """
        try:
            if not hasattr(self, "canvas") or not self.canvas or not hasattr(self.canvas, "animated_sprite"):
                self.log.warning("Canvas or animated sprite not available for frame paste")
                return False

            # Get the target frame
            if animation not in self.canvas.animated_sprite._animations:
                self.log.warning(f"Animation '{animation}' not found for frame paste")
                return False

            frames = self.canvas.animated_sprite._animations[animation]
            if frame >= len(frames):
                self.log.warning(f"Frame {frame} not found in animation '{animation}'")
                return False

            target_frame = frames[frame]

            # Apply the pixel data and duration
            target_frame.set_pixel_data(pixels)
            target_frame.duration = duration

            # Update the canvas pixels if this is the currently displayed frame
            if (hasattr(self, "selected_animation") and hasattr(self, "selected_frame") and
                self.selected_animation == animation and self.selected_frame == frame):
                if hasattr(self.canvas, "pixels"):
                    self.canvas.pixels = pixels.copy()
                    if hasattr(self.canvas, "dirty_pixels"):
                        self.canvas.dirty_pixels = [True] * len(pixels)
                    if hasattr(self.canvas, "dirty"):
                        self.canvas.dirty = 1

            self.log.debug(f"Applied frame paste to {animation}[{frame}]")
            return True

        except Exception as e:
            self.log.error(f"Error applying frame paste: {e}")
            return False

    def _apply_pixel_change_for_undo_redo(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        """Apply a pixel change for undo/redo operations.

        Args:
            x: X coordinate of the pixel
            y: Y coordinate of the pixel
            color: Color to set the pixel to
        """
        if hasattr(self, "canvas") and self.canvas and hasattr(self.canvas, "canvas_interface"):
            # Set flag to prevent undo tracking during undo/redo operations
            self._applying_undo_redo = True
            try:
                # Use the canvas interface to set the pixel
                self.canvas.canvas_interface.set_pixel_at(x, y, color)
                self.log.debug(f"Applied undo/redo pixel change at ({x}, {y}) to color {color}")
            finally:
                # Always reset the flag
                self._applying_undo_redo = False
        else:
            self.log.warning("Canvas or canvas interface not available for undo/redo")

    def _apply_frame_selection_for_undo_redo(self, animation: str, frame: int) -> bool:
        """Apply a frame selection for undo/redo operations.

        Args:
            animation: Name of the animation to select
            frame: Frame index to select

        Returns:
            True if the frame selection was applied successfully, False otherwise
        """
        try:
            if hasattr(self, "canvas") and self.canvas:
                # Set flag to prevent undo tracking during undo/redo operations
                self._applying_undo_redo = True
                try:
                    # Switch to the specified frame
                    self.canvas.show_frame(animation, frame)
                    self.log.debug(f"Applied undo/redo frame selection: {animation}[{frame}]")
                    return True
                finally:
                    # Always reset the flag
                    self._applying_undo_redo = False
            else:
                self.log.warning("Canvas not available for frame selection undo/redo")
                return False
        except Exception as e:
            self.log.error(f"Error applying frame selection undo/redo: {e}")
            return False

    def _add_frame_for_undo_redo(self, frame_index: int, animation_name: str, frame_data: dict) -> bool:
        """Add a frame for undo/redo operations.

        Args:
            frame_index: Index where the frame should be added
            animation_name: Name of the animation
            frame_data: Data about the frame to add

        Returns:
            True if the frame was added successfully, False otherwise
        """
        try:
            if not hasattr(self, "canvas") or not self.canvas or not hasattr(self.canvas, "animated_sprite"):
                self.log.warning("Canvas or animated sprite not available for frame addition")
                return False

            # Create a new frame from the frame data
            from glitchygames.sprites.animated import SpriteFrame
            import pygame

            # Create surface from frame data
            surface = pygame.Surface((frame_data["width"], frame_data["height"]))
            if "pixels" in frame_data and frame_data["pixels"]:
                # Convert pixel data to surface
                pixel_array = pygame.PixelArray(surface)
                for i, pixel in enumerate(frame_data["pixels"]):
                    if i < len(pixel_array.flat):
                        pixel_array.flat[i] = pixel
                del pixel_array  # Release the pixel array

            # Create the frame object
            new_frame = SpriteFrame(
                surface=surface,
                duration=frame_data.get("duration", 1.0)
            )

            # Add the frame to the animation
            self.canvas.animated_sprite.add_frame(animation_name, new_frame, frame_index)

            # Update the canvas's selected frame index if necessary
            if (hasattr(self, "canvas") and self.canvas and
                hasattr(self.canvas, "animated_sprite") and
                self.canvas.animated_sprite.frame_manager.current_animation == animation_name):

                # If we're adding a frame at or before the current position, increment the frame index
                if self.canvas.animated_sprite.frame_manager.current_frame >= frame_index:
                    self.canvas.animated_sprite.frame_manager.current_frame += 1

                # Ensure the frame index is within bounds
                max_frame = len(self.canvas.animated_sprite._animations[animation_name]) - 1
                if self.canvas.animated_sprite.frame_manager.current_frame > max_frame:
                    self.canvas.animated_sprite.frame_manager.current_frame = max(0, max_frame)

                # Update the canvas to show the correct frame
                self.canvas.show_frame(animation_name, self.canvas.animated_sprite.frame_manager.current_frame)

            # Update the film strip if it exists
            if hasattr(self, "film_strip_widget") and self.film_strip_widget:
                self.film_strip_widget._initialize_preview_animations()
                self.film_strip_widget.update_layout()
                self.film_strip_widget._create_film_tabs()
                self.film_strip_widget.mark_dirty()

            # Force update of all film strip widgets to ensure they reflect the change
            if hasattr(self, "film_strip_sprites") and self.film_strip_sprites:
                for film_strip_sprite in self.film_strip_sprites.values():
                    if hasattr(film_strip_sprite, "film_strip_widget") and film_strip_sprite.film_strip_widget:
                        # Completely refresh the film strip widget to ensure it shows current data
                        film_strip_sprite.film_strip_widget._initialize_preview_animations()
                        film_strip_sprite.film_strip_widget._calculate_layout()
                        film_strip_sprite.film_strip_widget.update_layout()
                        film_strip_sprite.film_strip_widget._create_film_tabs()
                        film_strip_sprite.film_strip_widget.mark_dirty()
                        film_strip_sprite.dirty = 1

                        # Update the film strip to show the current frame selection
                        if (hasattr(self.canvas, "current_animation") and
                            hasattr(self.canvas, "current_frame") and
                            self.canvas.current_animation == animation_name):
                            film_strip_sprite.film_strip_widget.set_frame_index(self.canvas.current_frame)

            # Notify the scene about the frame insertion for proper UI updates
            self._on_frame_inserted(animation_name, frame_index)

            self.log.debug(f"Added frame {frame_index} to animation '{animation_name}' for undo/redo")
            return True

        except Exception as e:
            self.log.error(f"Error adding frame for undo/redo: {e}")
            return False

    def _delete_frame_for_undo_redo(self, frame_index: int, animation_name: str) -> bool:
        """Delete a frame for undo/redo operations.

        Args:
            frame_index: Index of the frame to delete
            animation_name: Name of the animation

        Returns:
            True if the frame was deleted successfully, False otherwise
        """
        try:
            if not hasattr(self, "canvas") or not self.canvas or not hasattr(self.canvas, "animated_sprite"):
                self.log.warning("Canvas or animated sprite not available for frame deletion")
                return False

            # Remove the frame from the animation
            if animation_name in self.canvas.animated_sprite._animations:
                frames = self.canvas.animated_sprite._animations[animation_name]
                if 0 <= frame_index < len(frames):
                    # Stop animation to prevent race conditions during frame deletion
                    if (hasattr(self.canvas.animated_sprite, "frame_manager") and
                        self.canvas.animated_sprite.frame_manager.current_animation == animation_name):
                        self.canvas.animated_sprite._is_playing = False

                        # Adjust current frame index if necessary
                        if self.canvas.animated_sprite.frame_manager.current_frame >= frame_index:
                            if self.canvas.animated_sprite.frame_manager.current_frame > 0:
                                self.canvas.animated_sprite.frame_manager.current_frame -= 1
                            else:
                                self.canvas.animated_sprite.frame_manager.current_frame = 0

                    frames.pop(frame_index)

                    # Update the canvas's selected frame index if necessary and select the previous frame
                    if (hasattr(self, "canvas") and self.canvas and
                        hasattr(self.canvas, "animated_sprite") and
                        self.canvas.animated_sprite.frame_manager.current_animation == animation_name):

                        # Adjust the canvas's current frame index to select the previous frame
                        if self.canvas.animated_sprite.frame_manager.current_frame >= frame_index:
                            if self.canvas.animated_sprite.frame_manager.current_frame > 0:
                                # Select the previous frame
                                self.canvas.animated_sprite.frame_manager.current_frame -= 1
                                self.log.debug(f"Selected previous frame {self.canvas.animated_sprite.frame_manager.current_frame} after frame deletion")
                            else:
                                # If we were at frame 0 and removed it, stay at frame 0 (which is now the next frame)
                                self.canvas.animated_sprite.frame_manager.current_frame = 0
                                self.log.debug(f"Stayed at frame 0 after deleting frame 0")

                        # Ensure the frame index is within bounds
                        max_frame = len(self.canvas.animated_sprite._animations[animation_name]) - 1
                        if self.canvas.animated_sprite.frame_manager.current_frame > max_frame:
                            self.canvas.animated_sprite.frame_manager.current_frame = max(0, max_frame)

                        # Update the canvas to show the correct frame
                        self.canvas.show_frame(animation_name, self.canvas.animated_sprite.frame_manager.current_frame)

                    # Update the film strip if it exists
                    if hasattr(self, "film_strip_widget") and self.film_strip_widget:
                        self.film_strip_widget._initialize_preview_animations()
                        self.film_strip_widget.update_layout()
                        self.film_strip_widget._create_film_tabs()
                        self.film_strip_widget.mark_dirty()

                    # Force update of all film strip widgets to ensure they reflect the change
                    if hasattr(self, "film_strip_sprites") and self.film_strip_sprites:
                        for film_strip_sprite in self.film_strip_sprites.values():
                            if hasattr(film_strip_sprite, "film_strip_widget") and film_strip_sprite.film_strip_widget:
                                # Completely refresh the film strip widget to ensure it shows current data
                                film_strip_sprite.film_strip_widget._initialize_preview_animations()
                                film_strip_sprite.film_strip_widget._calculate_layout()
                                film_strip_sprite.film_strip_widget.update_layout()
                                film_strip_sprite.film_strip_widget._create_film_tabs()
                                film_strip_sprite.film_strip_widget.mark_dirty()
                                film_strip_sprite.dirty = 1

                                # Update the film strip to show the current frame selection
                                if (hasattr(self.canvas, "current_animation") and
                                    hasattr(self.canvas, "current_frame") and
                                    self.canvas.current_animation == animation_name):
                                    film_strip_sprite.film_strip_widget.set_frame_index(self.canvas.current_frame)

                    # Notify the scene about the frame removal for proper UI updates
                    self._on_frame_removed(animation_name, frame_index)

                    self.log.debug(f"Deleted frame {frame_index} from animation '{animation_name}' for undo/redo")
                    return True
                else:
                    self.log.warning(f"Frame index {frame_index} out of range for animation '{animation_name}'")
                    return False
            else:
                self.log.warning(f"Animation '{animation_name}' not found")
                return False

        except Exception as e:
            self.log.error(f"Error deleting frame for undo/redo: {e}")
            return False

    def _reorder_frame_for_undo_redo(self, old_index: int, new_index: int, animation_name: str) -> bool:
        """Reorder frames for undo/redo operations.

        Args:
            old_index: Original index of the frame
            new_index: New index of the frame
            animation_name: Name of the animation

        Returns:
            True if the frame was reordered successfully, False otherwise
        """
        try:
            if not hasattr(self, "canvas") or not self.canvas or not hasattr(self.canvas, "animated_sprite"):
                self.log.warning("Canvas or animated sprite not available for frame reordering")
                return False

            # Reorder frames in the animation
            if animation_name in self.canvas.animated_sprite._animations:
                frames = self.canvas.animated_sprite._animations[animation_name]
                if 0 <= old_index < len(frames) and 0 <= new_index < len(frames):
                    # Move the frame from old_index to new_index
                    frame = frames.pop(old_index)
                    frames.insert(new_index, frame)

                    # Update the film strip if it exists
                    if hasattr(self, "film_strip_widget") and self.film_strip_widget:
                        self.film_strip_widget._initialize_preview_animations()
                        self.film_strip_widget.update_layout()
                        self.film_strip_widget._create_film_tabs()
                        self.film_strip_widget.mark_dirty()

                    self.log.debug(f"Reordered frame from {old_index} to {new_index} in animation '{animation_name}' for undo/redo")
                    return True
                else:
                    self.log.warning(f"Frame indices out of range for animation '{animation_name}'")
                    return False
            else:
                self.log.warning(f"Animation '{animation_name}' not found")
                return False

        except Exception as e:
            self.log.error(f"Error reordering frame for undo/redo: {e}")
            return False

    def _add_animation_for_undo_redo(self, animation_name: str, animation_data: dict) -> bool:
        """Add an animation for undo/redo operations.

        Args:
            animation_name: Name of the animation to add
            animation_data: Data about the animation to add

        Returns:
            True if the animation was added successfully, False otherwise
        """
        try:
            if not hasattr(self, "canvas") or not self.canvas or not hasattr(self.canvas, "animated_sprite"):
                self.log.warning("Canvas or animated sprite not available for animation addition")
                return False

            # Create the animation with its frames
            for frame_data in animation_data.get("frames", []):
                from glitchygames.sprites.animated import SpriteFrame
                import pygame

                # Create surface from frame data
                surface = pygame.Surface((frame_data["width"], frame_data["height"]))
                if "pixels" in frame_data and frame_data["pixels"]:
                    # Convert pixel data to surface
                    pixel_array = pygame.PixelArray(surface)
                    for i, pixel in enumerate(frame_data["pixels"]):
                        if i < len(pixel_array.flat):
                            pixel_array.flat[i] = pixel
                    del pixel_array  # Release the pixel array

                # Create the frame object
                new_frame = SpriteFrame(
                    surface=surface,
                    duration=frame_data.get("duration", 1.0)
                )

                # Add the frame to the animation
                self.canvas.animated_sprite._animations[animation_name] = self.canvas.animated_sprite._animations.get(animation_name, [])
                self.canvas.animated_sprite._animations[animation_name].append(new_frame)

            # Update the film strip if it exists
            if hasattr(self, "film_strip_widget") and self.film_strip_widget:
                self.film_strip_widget._initialize_preview_animations()
                self.film_strip_widget.update_layout()
                self.film_strip_widget._create_film_tabs()
                self.film_strip_widget.mark_dirty()

            # Force update of all film strip widgets
            if hasattr(self, "film_strip_sprites") and self.film_strip_sprites:
                for film_strip_sprite in self.film_strip_sprites.values():
                    if hasattr(film_strip_sprite, "film_strip_widget") and film_strip_sprite.film_strip_widget:
                        # Completely refresh the film strip widget to ensure it shows current data
                        film_strip_sprite.film_strip_widget._initialize_preview_animations()
                        film_strip_sprite.film_strip_widget._calculate_layout()
                        film_strip_sprite.film_strip_widget.update_layout()
                        film_strip_sprite.film_strip_widget._create_film_tabs()
                        film_strip_sprite.film_strip_widget.mark_dirty()
                        film_strip_sprite.dirty = 1

            self.log.debug(f"Added animation '{animation_name}' for undo/redo")
            return True

        except Exception as e:
            self.log.error(f"Error adding animation for undo/redo: {e}")
            return False

    def _delete_animation_for_undo_redo(self, animation_name: str) -> bool:
        """Delete an animation for undo/redo operations.

        Args:
            animation_name: Name of the animation to delete

        Returns:
            True if the animation was deleted successfully, False otherwise
        """
        try:
            if not hasattr(self, "canvas") or not self.canvas or not hasattr(self.canvas, "animated_sprite"):
                self.log.warning("Canvas or animated sprite not available for animation deletion")
                return False

            # Remove the animation
            if animation_name in self.canvas.animated_sprite._animations:
                del self.canvas.animated_sprite._animations[animation_name]

                # Update the film strip if it exists
                if hasattr(self, "film_strip_widget") and self.film_strip_widget:
                    self.film_strip_widget._initialize_preview_animations()
                    self.film_strip_widget.update_layout()
                    self.film_strip_widget._create_film_tabs()
                    self.film_strip_widget.mark_dirty()

                # Force update of all film strip widgets
                if hasattr(self, "film_strip_sprites") and self.film_strip_sprites:
                    for film_strip_sprite in self.film_strip_sprites.values():
                        if hasattr(film_strip_sprite, "film_strip_widget") and film_strip_sprite.film_strip_widget:
                            # Completely refresh the film strip widget to ensure it shows current data
                            film_strip_sprite.film_strip_widget._initialize_preview_animations()
                            film_strip_sprite.film_strip_widget._calculate_layout()
                            film_strip_sprite.film_strip_widget.update_layout()
                            film_strip_sprite.film_strip_widget._create_film_tabs()
                            film_strip_sprite.film_strip_widget.mark_dirty()
                            film_strip_sprite.dirty = 1

                # CRITICAL: Recreate film strips to reflect the deleted animation
                self._on_sprite_loaded(self.canvas.animated_sprite)

                self.log.debug(f"Deleted animation '{animation_name}' for undo/redo")
                return True
            else:
                self.log.warning(f"Animation '{animation_name}' not found")
                return False

        except Exception as e:
            self.log.error(f"Error deleting animation for undo/redo: {e}")
            return False

    def _apply_controller_position_for_undo_redo(self, controller_id: int, position: tuple[int, int], mode: str = None) -> bool:
        """Apply a controller position change for undo/redo operations.

        Args:
            controller_id: ID of the controller
            position: New position (x, y)
            mode: Controller mode (optional)

        Returns:
            True if the position was applied successfully, False otherwise
        """
        try:
            # Set flag to prevent undo tracking during undo/redo operations
            self._applying_undo_redo = True
            try:
                # Update controller position in mode switcher
                if hasattr(self, "mode_switcher") and self.mode_switcher:
                    self.mode_switcher.save_controller_position(controller_id, position)

                    # Update visual indicator
                    if hasattr(self, "_update_controller_canvas_visual_indicator"):
                        self._update_controller_canvas_visual_indicator(controller_id)

                    self.log.debug(f"Applied undo/redo controller position: {controller_id} -> {position}")
                    return True
                else:
                    self.log.warning("Mode switcher not available for controller position undo/redo")
                    return False
            finally:
                # Always reset the flag
                self._applying_undo_redo = False
        except Exception as e:
            self.log.error(f"Error applying controller position undo/redo: {e}")
            return False

    def _apply_controller_mode_for_undo_redo(self, controller_id: int, mode: str) -> bool:
        """Apply a controller mode change for undo/redo operations.

        Args:
            controller_id: ID of the controller
            mode: New controller mode

        Returns:
            True if the mode was applied successfully, False otherwise
        """
        try:
            # Set flag to prevent undo tracking during undo/redo operations
            self._applying_undo_redo = True
            try:
                # Update controller mode in mode switcher
                if hasattr(self, "mode_switcher") and self.mode_switcher:
                    from glitchygames.tools.controller_mode_system import ControllerMode

                    # Convert string to ControllerMode enum
                    try:
                        controller_mode = ControllerMode(mode)
                    except ValueError:
                        self.log.warning(f"Invalid controller mode: {mode}")
                        return False

                    # Switch to the new mode
                    import time
                    current_time = time.time()
                    self.mode_switcher.controller_modes[controller_id].switch_to_mode(controller_mode, current_time)

                    # Update visual indicator
                    if hasattr(self, "_update_controller_visual_indicator_for_mode"):
                        self._update_controller_visual_indicator_for_mode(controller_id, controller_mode)

                    self.log.debug(f"Applied undo/redo controller mode: {controller_id} -> {mode}")
                    return True
                else:
                    self.log.warning("Mode switcher not available for controller mode undo/redo")
                    return False
            finally:
                # Always reset the flag
                self._applying_undo_redo = False
        except Exception as e:
            self.log.error(f"Error applying controller mode undo/redo: {e}")
            return False

    def _submit_pixel_changes_if_ready(self) -> None:
        """Submit collected pixel changes if they're ready (single click or drag ended)."""
        if hasattr(self, "_current_pixel_changes") and self._current_pixel_changes:
            if hasattr(self, "canvas_operation_tracker"):
                pixel_count = len(self._current_pixel_changes)

                # Get current frame information for frame-specific tracking
                current_animation = None
                current_frame = None
                if hasattr(self, "canvas") and self.canvas:
                    current_animation = getattr(self.canvas, "current_animation", None)
                    current_frame = getattr(self.canvas, "current_frame", None)


                # Use frame-specific tracking if we have frame information
                if current_animation is not None and current_frame is not None:
                    self.canvas_operation_tracker.add_frame_pixel_changes(
                        current_animation, current_frame, self._current_pixel_changes
                    )
                    self.log.debug(f"Submitted {pixel_count} pixel changes for frame {current_animation}[{current_frame}] undo/redo tracking")
                else:
                    # Fall back to global tracking
                    self.canvas_operation_tracker.add_pixel_changes(self._current_pixel_changes)
                    self.log.debug(f"Submitted {pixel_count} pixel changes for global undo/redo tracking")

                self._current_pixel_changes = []  # Clear the collection

    def _check_single_click_timer(self) -> None:
        """Check if we should submit a single click based on timer."""
        if (hasattr(self, "_current_pixel_changes") and self._current_pixel_changes and
            hasattr(self, "_pixel_change_timer") and self._pixel_change_timer and
            len(self._current_pixel_changes) == 1):  # Only for single pixels

            import time
            current_time = time.time()
            # If more than 0.1 seconds have passed since the first pixel change, submit it
            if current_time - self._pixel_change_timer > 0.1:
                self._submit_pixel_changes_if_ready()
                self._pixel_change_timer = None


    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> None:
        """Add command line arguments.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            None

        Raises:
            None

        """
        parser.add_argument(
            "-v", "--version", action="store_true", help="print the game version and exit"
        )
        parser.add_argument("-s", "--size", default="32x32")

    def _handle_scene_key_events(self, event: events.HashableEvent) -> None:
        """Handle scene-level key events."""
        self.log.debug(f"Scene-level key event: {event.key}")

        # Call our custom keyboard handler
        self.on_key_down_event(event)

    def on_drop_file_event(self, event: events.HashableEvent) -> None:
        """Handle drop file event.

        Args:
            event: The pygame event containing the dropped file information.

        Returns:
            None

        """
        # Get the file path from the event
        file_path = event.file
        self.log.info(f"File dropped: {file_path}")

        # Get file size
        try:
            file_size = Path(file_path).stat().st_size
            self.log.info(f"File size: {file_size} bytes")
        except OSError:
            self.log.error("Could not get file size")
            return

        # First, check if any film strip sprites can handle the drop
        if hasattr(self, "film_strip_sprites") and self.film_strip_sprites:
            for strip_name, film_strip_sprite in self.film_strip_sprites.items():
                if hasattr(film_strip_sprite, "on_drop_file_event"):
                    try:
                        # Check if the film strip can handle this drop
                        if film_strip_sprite.on_drop_file_event(event):
                            self.log.info(f"Film strip '{strip_name}' handled the drop")
                            return
                    except Exception as e:
                        self.log.error(f"Error in film strip drop handler: {e}")
                        continue

        # If no film strip handled it, check if drop is on the canvas
        # Get current mouse position since drop events don't include position
        mouse_pos = pygame.mouse.get_pos()
        if hasattr(self, "canvas") and self.canvas and self.canvas.rect.collidepoint(mouse_pos):
            self.log.info(f"Drop detected on canvas at {mouse_pos}")
            # Check if it's a PNG file
            if file_path.lower().endswith(".png"):
                self.log.info("PNG file detected - converting to bitmappy format")
                converted_toml_path = self._convert_png_to_bitmappy(file_path)
                if converted_toml_path:
                    # Auto-load the converted TOML file
                    self._load_converted_sprite(converted_toml_path)
                else:
                    self.log.error("Failed to convert PNG to bitmappy format")
            elif file_path.lower().endswith(".toml"):
                self.log.info("TOML file detected - loading directly")
                # Load the TOML file directly
                self._load_converted_sprite(file_path)
            else:
                self.log.info(f"Unsupported file type dropped on canvas: {file_path}")
        else:
            self.log.info(f"Drop not on canvas or film strip - ignoring drop at {mouse_pos}")
            return

    def _convert_png_to_bitmappy(self, file_path: str) -> str | None:
        """Convert a PNG file to bitmappy TOML format.

        Args:
            file_path: Path to the PNG file to convert.

        Returns:
            Path to the converted TOML file, or None if conversion failed.

        """
        try:
            # Load the PNG image
            self.log.info(f"Loading PNG image: {file_path}")
            image = pygame.image.load(file_path)

            # Get image dimensions
            width, height = image.get_size()
            self.log.info(f"Image dimensions: {width}x{height}")

            # Get current canvas size for resizing
            canvas_width, canvas_height = 32, 32  # Default fallback
            if hasattr(self, "canvas") and self.canvas:
                canvas_width = self.canvas.pixels_across
                canvas_height = self.canvas.pixels_tall
                self.log.info(f"Using current canvas size: {canvas_width}x{canvas_height}")
            else:
                self.log.info("No canvas found, using default size: 32x32")

            # Check if image needs resizing to match canvas size
            if width != canvas_width or height != canvas_height:
                self.log.info(f"Resizing image from {width}x{height} to {canvas_width}x{canvas_height} to match canvas")

                # Resize the image to match canvas size
                resized_image = pygame.transform.scale(image, (canvas_width, canvas_height))
                image = resized_image
                width, height = canvas_width, canvas_height
                self.log.info(f"Resized image to {width}x{height}")

            # Convert to RGB if needed, handling transparency
            if image.get_flags() & pygame.SRCALPHA:
                # Image has alpha channel, convert to RGB with transparency handling
                rgb_image = pygame.Surface((width, height))
                rgb_image.fill((255, 255, 255))  # White background
                rgb_image.blit(image, (0, 0))
                image = rgb_image
                self.log.info("Converted image with alpha channel to RGB")

            # Get pixel data
            pixel_array = pygame.surfarray.array3d(image)
            self.log.info(f"Pixel array shape: {pixel_array.shape}")

            # Handle transparency - check if original image had alpha
            has_transparency = False
            if image.get_flags() & pygame.SRCALPHA:
                # Get the original image with alpha for transparency detection
                original_image = pygame.image.load(file_path)
                if original_image.get_flags() & pygame.SRCALPHA:
                    has_transparency = True
                    self.log.info("Image has transparency - will map transparent pixels to magenta (255, 0, 255)")

            # Use a more efficient approach for large images
            # Sample pixels to find representative colors
            sample_step = max(1, (width * height) // 10000)  # Sample up to 10k pixels
            self.log.info(f"Sampling every {sample_step} pixels for color analysis")

            # Find unique colors by sampling
            unique_colors = set()
            sample_count = 0
            transparent_pixels = 0

            for y in range(0, height, sample_step):
                for x in range(0, width, sample_step):
                    r, g, b = pixel_array[x, y]
                    # Ensure we're working with Python ints, not numpy types
                    color = (int(r), int(g), int(b))
                    unique_colors.add(color)
                    sample_count += 1

                    # Check for transparency if we have the original image
                    if has_transparency:
                        # Get the original pixel with alpha
                        original_pixel = original_image.get_at((x, y))
                        if original_pixel.a < 128:  # Semi-transparent or fully transparent
                            transparent_pixels += 1
                            # Map transparent pixels to magenta
                            unique_colors.discard(color)  # Remove the current color
                            unique_colors.add((255, 0, 255))  # Add magenta for transparency

            if has_transparency:
                self.log.info(f"Found {transparent_pixels} transparent pixels, mapped to magenta (255, 0, 255)")

            self.log.info(f"Sampled {sample_count} pixels, found {len(unique_colors)} unique colors")

            # If we still have too many colors, use k-means-like approach
            # Reserve one slot for transparency if we have transparent pixels
            reserved_for_transparency = 1 if has_transparency else 0
            # Limit to 1000 colors maximum for practical file sizes
            max_colors = 1000
            available_colors = max_colors - reserved_for_transparency

            if len(unique_colors) > available_colors:
                self.log.info("Too many colors detected, using color quantization...")
                # Group similar colors together
                color_groups = {}
                for color in unique_colors:
                    # Find the closest existing group
                    closest_group = None
                    min_distance = float("inf")

                    for group_color in color_groups:
                        distance = sum((a - b) ** 2 for a, b in zip(color, group_color))
                        if distance < min_distance:
                            min_distance = distance
                            closest_group = group_color

                    # If no close group exists and we have space, create new group
                    if closest_group is None or min_distance > 1000:  # Lower threshold for better color separation
                        if len(color_groups) < available_colors:
                            color_groups[color] = [color]
                        else:
                            # Add to closest existing group
                            color_groups[closest_group].append(color)
                    else:
                        color_groups[closest_group].append(color)

                # Create representative colors for each group
                representative_colors = []
                for group_color, colors in color_groups.items():
                    if colors:
                        # Use the most common color in the group as representative
                        representative_colors.append(group_color)

                unique_colors = set(representative_colors)
                self.log.info(f"Quantized to {len(unique_colors)} representative colors")
                self.log.info(f"Available colors: {available_colors}, Color groups created: {len(color_groups)}")

            # Map colors to bitmappy palette using first 1000 SPRITE_GLYPHS characters
            # Reserve one slot for transparency if we have transparent pixels
            max_glyphs = 1000
            available_glyphs = list(SPRITE_GLYPHS[:max_glyphs])  # Use first 1000 characters
            reserved_for_transparency = 1 if has_transparency else 0
            available_colors = len(available_glyphs) - reserved_for_transparency

            self.log.info(f"Mapping colors: {len(unique_colors)} unique colors to {available_colors} available glyphs")
            if has_transparency:
                self.log.info("Reserved 1 glyph for transparency")

            color_mapping = {}
            glyph_index = 0

            # First, ensure magenta (transparency) gets a glyph if we have transparency
            if has_transparency and (255, 0, 255) in unique_colors:
                color_mapping[(255, 0, 255)] = "@"  # Use @ for transparency
                self.log.info("Reserved glyph '@' for transparency (magenta)")

            # Map other colors to available glyphs
            for color in sorted(unique_colors):
                if color == (255, 0, 255) and has_transparency:
                    continue  # Already handled above

                if glyph_index < available_colors:  # Only use available glyphs
                    color_mapping[color] = available_glyphs[glyph_index]
                    glyph_index += 1
                else:
                    # Map to closest existing color using safe distance calculation
                    def color_distance(c1, c2):
                        """Calculate color distance safely."""
                        return sum((int(a) - int(b)) ** 2 for a, b in zip(c1, c2, strict=True))

                    closest_color = min(color_mapping.keys(), key=lambda c: color_distance(color, c))
                    color_mapping[color] = color_mapping[closest_color]

            self.log.info(f"Final color mapping: {len(color_mapping)} colors mapped to glyphs")

            # Generate pixel string more efficiently
            self.log.info("Generating pixel string...")
            pixel_string = ""
            for y in range(height):
                for x in range(width):
                    r, g, b = pixel_array[x, y]
                    # Convert to int tuple for consistent lookup
                    color_key = (int(r), int(g), int(b))

                    # Handle transparency - check if this pixel should be transparent
                    if has_transparency:
                        original_pixel = original_image.get_at((x, y))
                        if original_pixel.a < 128:  # Semi-transparent or fully transparent
                            color_key = (255, 0, 255)  # Use magenta for transparency

                    # If color is not in mapping, find closest mapped color
                    if color_key not in color_mapping:
                        def color_distance(c1, c2):
                            """Calculate color distance safely."""
                            return sum((int(a) - int(b)) ** 2 for a, b in zip(c1, c2, strict=True))

                        closest_color = min(color_mapping.keys(), key=lambda c: color_distance(color_key, c))
                        color_mapping[color_key] = color_mapping[closest_color]
                        self.log.debug(f"Mapped unmapped color {color_key} to {closest_color}")

                    pixel_string += color_mapping[color_key]
                if y < height - 1:  # Add newline except for last row
                    pixel_string += "\n"

                # Log progress for large images
                if height > 32 and y % (height // 10) == 0:
                    self.log.info(f"Progress: {y}/{height} rows processed")

            # Generate TOML content
            toml_content = f'[sprite]\nname = "imported_from_{Path(file_path).stem}"\npixels = """\n{pixel_string}\n"""\n\n[colors]\n'

            # Add color definitions - collect unique glyphs first
            unique_glyphs = set(color_mapping.values())
            self.log.info(f"Unique glyphs to define: {sorted(unique_glyphs)}")

            for glyph in sorted(unique_glyphs):
                # Find the first color that maps to this glyph
                for color, mapped_glyph in color_mapping.items():
                    if mapped_glyph == glyph:
                        r, g, b = color
                        # Quote the glyph to handle special characters like '.'
                        toml_content += f'[colors."{glyph}"]\nred = {r}\ngreen = {g}\nblue = {b}\n\n'
                        self.log.info(f"Defined color {glyph}: RGB({r}, {g}, {b})")
                        break

            # Validate that we have color definitions
            if not unique_glyphs:
                self.log.error("No colors to define - this will cause display issues!")
                raise ValueError("No colors found in the converted sprite")

            self.log.info(f"Generated {len(unique_glyphs)} color definitions")

            # Save the TOML file
            output_path = Path(file_path).with_suffix(".toml")
            Path(output_path).write_text(toml_content, encoding="utf-8")

            # Validate the generated TOML file by checking content directly
            self.log.info("Validating generated TOML file...")
            try:
                # Read the file content to check for basic structure
                with output_path.open(encoding="utf-8") as f:
                    content = f.read()

                # Check for required sections
                if "[sprite]" not in content:
                    self.log.error("TOML file missing [sprite] section!")
                    raise ValueError("Generated TOML file has no [sprite] section")

                if "[colors]" not in content:
                    self.log.error("TOML file missing [colors] section!")
                    raise ValueError("Generated TOML file has no [colors] section")

                # Count color definitions by counting [colors."..."] lines
                color_count = content.count('[colors."')
                if color_count == 0:
                    self.log.error("TOML file has no color definitions!")
                    raise ValueError("Generated TOML file has no color definitions")

                self.log.info(f"TOML validation passed: {color_count} colors defined")

            except Exception as e:
                self.log.error(f"TOML validation failed: {e}")
                raise

            self.log.info(f"Successfully converted PNG to bitmappy format: {output_path}")

            # Return the path to the converted TOML file
            return str(output_path)

        except Exception:
            self.log.error("Error converting PNG to bitmappy format")
            return None

    def _load_converted_sprite(self, toml_path: str) -> None:
        """Load a converted TOML sprite into the editor.

        Args:
            toml_path: Path to the converted TOML file.

        Returns:
            None

        """
        try:
            self.log.info("=== STARTING _load_converted_sprite ===")
            # Find the canvas sprite in the scene
            self.log.info(f"Searching for canvas sprite in {len(self.all_sprites)} sprites...")
            canvas_sprite = None
            for i, sprite in enumerate(self.all_sprites):
                self.log.info(f"Sprite {i}: {type(sprite)} - has on_load_file_event: {hasattr(sprite, 'on_load_file_event')}")
                if hasattr(sprite, "on_load_file_event"):
                    canvas_sprite = sprite
                    self.log.info(f"Found canvas sprite: {type(canvas_sprite)}")
                    break

            if canvas_sprite:
                self.log.info(f"Loading converted sprite: {toml_path}")
                self.log.info(f"Found canvas sprite: {type(canvas_sprite)}")

                # Create a mock event for loading
                class MockEvent:
                    def __init__(self, text):
                        self.text = text

                mock_event = MockEvent(toml_path)
                self.log.info("Calling on_load_file_event...")
                canvas_sprite.on_load_file_event(mock_event)
                self.log.info("on_load_file_event completed")

                # Update border thickness after loading (in case canvas was resized)
                self.log.info("Updating border thickness after sprite load...")
                canvas_sprite._update_border_thickness()

                # Force a complete redraw to apply the new border settings
                self.log.info("Forcing canvas redraw with new border settings...")
                canvas_sprite.force_redraw()

                # Debug: Check what was loaded
                self.log.info(f"Canvas sprite type: {type(canvas_sprite)}")
                self.log.info(f"Canvas sprite has animated_sprite: {hasattr(canvas_sprite, 'animated_sprite')}")
                if hasattr(canvas_sprite, "animated_sprite"):
                    self.log.info(f"animated_sprite value: {canvas_sprite.animated_sprite}")
                if hasattr(canvas_sprite, "animated_sprite") and canvas_sprite.animated_sprite:
                    self.log.info(f"Animated sprite loaded: {canvas_sprite.animated_sprite}")
                    if hasattr(canvas_sprite.animated_sprite, "_animations"):
                        animations = list(canvas_sprite.animated_sprite._animations.keys())
                        self.log.info(f"Animations: {animations}")
                        if animations:
                            first_anim = animations[0]
                            frames = canvas_sprite.animated_sprite._animations[first_anim]
                            self.log.info(f"First animation '{first_anim}' has {len(frames)} frames")
                            if frames:
                                first_frame = frames[0]
                                self.log.info(f"First frame size: {first_frame.size}")

                                # Transfer pixel data from the loaded sprite to the canvas
                                self.log.info("Transferring pixel data from loaded sprite to canvas...")
                                if hasattr(first_frame, "image") and first_frame.image:
                                    # Get the pixel data from the frame image
                                    frame_surface = first_frame.image
                                    frame_width, frame_height = frame_surface.get_size()
                                    self.log.info(f"Frame surface size: {frame_width}x{frame_height}")

                                    # Convert the frame surface to pixel data
                                    pixel_data = []
                                    for y in range(frame_height):
                                        for x in range(frame_width):
                                            color = frame_surface.get_at((x, y))
                                            # Convert to RGB (ignore alpha)
                                            pixel_data.append((color.r, color.g, color.b))

                                    # Update canvas pixels
                                    canvas_sprite.pixels = pixel_data
                                    canvas_sprite.dirty_pixels = [True] * len(pixel_data)
                                    self.log.info(f"Transferred {len(pixel_data)} pixels to canvas")

                                    # Update mini view pixels too
                                    if hasattr(canvas_sprite, "mini_view") and canvas_sprite.mini_view is not None:
                                        canvas_sprite.mini_view.pixels = pixel_data.copy()
                                        canvas_sprite.mini_view.dirty_pixels = [True] * len(pixel_data)
                                        self.log.info("Updated mini view pixels")

                # Force canvas redraw to show the new sprite
                self.log.info("Forcing canvas redraw after loading...")
                canvas_sprite.dirty = 1
                canvas_sprite.force_redraw()

                # Update mini view if it exists
                if hasattr(canvas_sprite, "mini_view") and canvas_sprite.mini_view is not None:
                    self.log.info("Updating mini view...")
                    canvas_sprite.mini_view.pixels = canvas_sprite.pixels.copy()
                    canvas_sprite.mini_view.dirty_pixels = [True] * len(canvas_sprite.pixels)
                    canvas_sprite.mini_view.dirty = 1
                    canvas_sprite.mini_view.force_redraw()

                # Initialize onion skinning for the loaded sprite
                if hasattr(canvas_sprite, "animated_sprite") and canvas_sprite.animated_sprite:
                    self._initialize_onion_skinning_for_sprite(canvas_sprite.animated_sprite)

                self.log.info("Converted sprite loaded successfully into editor")
            else:
                self.log.warning("Could not find canvas sprite to load converted file")

        except Exception:
            self.log.error("Error loading converted sprite into editor")

    def _initialize_onion_skinning_for_sprite(self, loaded_sprite: AnimatedSprite) -> None:
        """Initialize onion skinning for a newly loaded sprite.

        Args:
            loaded_sprite: The loaded animated sprite
        """
        try:
            from .onion_skinning import get_onion_skinning_manager

            onion_manager = get_onion_skinning_manager()

            # Clear any existing onion skinning state for this sprite
            if hasattr(loaded_sprite, '_animations') and loaded_sprite._animations:
                for animation_name in loaded_sprite._animations.keys():
                    onion_manager.clear_animation_onion_skinning(animation_name)
                    self.log.debug(f"Cleared onion skinning state for animation: {animation_name}")

            # Initialize onion skinning for all animations in the loaded sprite
            if hasattr(loaded_sprite, '_animations') and loaded_sprite._animations:
                for animation_name, frames in loaded_sprite._animations.items():
                    # Enable onion skinning for all frames except the first one
                    frame_states = {}
                    for frame_idx in range(len(frames)):
                        # Enable onion skinning for all frames except frame 0
                        frame_states[frame_idx] = frame_idx != 0

                    onion_manager.set_animation_onion_state(animation_name, frame_states)
                    self.log.debug(f"Initialized onion skinning for animation '{animation_name}' with {len(frames)} frames")

            # Ensure global onion skinning is enabled
            if not onion_manager.is_global_onion_skinning_enabled():
                onion_manager.toggle_global_onion_skinning()
                self.log.debug("Enabled global onion skinning for new sprite")

            self.log.info("Onion skinning initialized for loaded sprite")

        except Exception as e:
            self.log.error(f"Failed to initialize onion skinning for loaded sprite: {e}")

    def handle_event(self, event):
        """Handle pygame events."""
        # Debug logging for keyboard events
        if event.type == pygame.KEYDOWN:
            self.log.debug(f"KEYDOWN event received in handle_event: key={event.key}")

        super().handle_event(event)

        if event.type == pygame.WINDOWLEAVE:
            # Notify sprites that mouse left window
            for sprite in self.all_sprites:
                if hasattr(sprite, "on_mouse_leave_window_event"):
                    sprite.on_mouse_leave_window_event(event)

    def deflate(self: Self) -> dict:
        """Deflate a sprite to a Bitmappy config file."""
        try:
            self.log.debug(f"Starting deflate for {self.name}")
            self.log.debug(f"Image dimensions: {self.image.get_size()}")

            config = configparser.ConfigParser(
                dict_type=collections.OrderedDict, empty_lines_in_values=True, strict=True
            )

            # Get the raw pixel data and log its size
            pixel_string = pygame.image.tostring(self.image, "RGB")
            self.log.debug(f"Raw pixel string length: {len(pixel_string)}")

            # Log the first few bytes of pixel data
            self.log.debug(f"First 12 bytes of pixel data: {list(pixel_string[:12])}")

            # Create the generator and log initial state
            raw_pixels = rgb_triplet_generator(pixel_data=pixel_string)
            self.log.debug("Created RGB triplet generator")

            # Try to get the first triplet
            try:
                first_triplet = next(raw_pixels)
                self.log.debug(f"First RGB triplet: {first_triplet}")
                # Reset generator
                raw_pixels = rgb_triplet_generator(pixel_data=pixel_string)
            except StopIteration:
                self.log.error("Generator empty on first triplet!")
                raise

            # Now proceed with the rest of deflate
            raw_pixels = list(raw_pixels)
            self.log.debug(f"Converted {len(raw_pixels)} RGB triplets to list")

            # Continue with original deflate code...
            colors = set(raw_pixels)
            self.log.debug(f"Found {len(colors)} unique colors")

        except Exception:
            self.log.error("Error in deflate")
            raise
        else:
            return config

    # Controller Support Methods
    def on_controller_button_down_event(self, event: pygame.event.Event) -> None:
        """Handle controller button down events for multi-controller system.

        Args:
            event (pygame.event.Event): The controller button down event.

        Returns:
            None

        """
        # Scan for controllers and update manager
        self.multi_controller_manager.scan_for_controllers()

        # Get controller info
        instance_id = event.instance_id
        controller_info = self.multi_controller_manager.get_controller_info(instance_id)

        if not controller_info:
            return

        LOG.debug(f"Controller button down: {event.button}")

        # Handle controller assignment on first button press
        if controller_info.status.value == "connected":
            controller_id = self.multi_controller_manager.assign_controller(instance_id)
            if controller_id is not None:
                # Create controller selection for this controller
                self.controller_selections[controller_id] = ControllerSelection(controller_id, instance_id)

        # Get controller ID for this instance
        controller_id = self.multi_controller_manager.get_controller_id(instance_id)
        if controller_id is None:
            return

        # Get or create controller selection
        if controller_id not in self.controller_selections:
            self.controller_selections[controller_id] = ControllerSelection(controller_id, instance_id)

        controller_selection = self.controller_selections[controller_id]

        # Update controller activity
        self.multi_controller_manager.update_controller_activity(instance_id)
        controller_selection.update_activity()

        # Handle button presses

        # Get controller mode for mode-specific handling
        controller_mode = self.mode_switcher.get_controller_mode(controller_id)

        # Handle mode-specific button presses
        if controller_mode and controller_mode.value == "canvas":
            self._handle_canvas_button_press(controller_id, event.button)
        elif controller_mode and controller_mode.value in ["r_slider", "g_slider", "b_slider"]:
            self._handle_slider_button_press(controller_id, event.button)
        else:
            # Default to film strip mode handling
            self._handle_film_strip_button_press(controller_id, event.button)


    def _handle_film_strip_button_press(self, controller_id: int, button: int) -> None:
        """Handle button presses for film strip mode."""
        if button == pygame.CONTROLLER_BUTTON_A:
            # A button: Select current frame
            LOG.debug(f"Controller {controller_id}: A button pressed - selecting current frame")
            self._multi_controller_select_current_frame(controller_id)
        elif button == pygame.CONTROLLER_BUTTON_B:
            # B button (Circle): Undo operations
            LOG.debug(f"Controller {controller_id}: B button pressed - UNDO")
            self._handle_undo()
        elif button == pygame.CONTROLLER_BUTTON_Y:
            # Y button (Triangle): Toggle onion skinning for selected frame
            LOG.debug(f"Controller {controller_id}: Y button pressed - toggling onion skinning")
            self._multi_controller_toggle_onion_skinning(controller_id)
        elif button == pygame.CONTROLLER_BUTTON_X:
            # X button (Square): RESERVED for redo operations (only when selected frame is visible)
            if self.selected_frame_visible:
                LOG.debug(f"Controller {controller_id}: X button pressed - REDO")
                self._handle_redo()
            else:
                LOG.debug(f"Controller {controller_id}: X button pressed - DISABLED (selected frame hidden)")
                # X button disabled when selected frame is hidden
        elif button == pygame.CONTROLLER_BUTTON_DPAD_LEFT:
            # D-pad left: Previous frame
            LOG.debug(f"Controller {controller_id}: D-pad left pressed - previous frame")
            self._multi_controller_previous_frame(controller_id)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_RIGHT:
            # D-pad right: Next frame
            LOG.debug(f"Controller {controller_id}: D-pad right pressed - next frame")
            self._multi_controller_next_frame(controller_id)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_UP:
            # D-pad up: Previous animation
            LOG.debug(f"Controller {controller_id}: D-pad up pressed - previous animation")
            self._multi_controller_previous_animation(controller_id)
        elif button == pygame.CONTROLLER_BUTTON_START:
            # Start button: Activate controller
            LOG.debug(f"Controller {controller_id}: Start button pressed - activate controller")
            self._multi_controller_activate(controller_id)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_DOWN:
            # D-pad down: Next animation
            LOG.debug(f"Controller {controller_id}: D-pad down pressed - next animation")
            self._multi_controller_next_animation(controller_id)
        elif button == pygame.CONTROLLER_BUTTON_LEFTSHOULDER:
            # Left shoulder button: Move controller indicator left (like D-pad left)
            LOG.debug(f"Controller {controller_id}: LEFT SHOULDER button pressed - moving indicator left")
            self._multi_controller_previous_frame(controller_id)
        elif button == pygame.CONTROLLER_BUTTON_RIGHTSHOULDER:
            # Right shoulder button: Move controller indicator right (like D-pad right)
            LOG.debug(f"Controller {controller_id}: RIGHT SHOULDER button pressed - moving indicator right")
            self._multi_controller_next_frame(controller_id)
        elif button == pygame.CONTROLLER_BUTTON_LEFTSTICK:
            # Left stick button: Currently unhandled
            LOG.debug(f"Controller {controller_id}: LEFT STICK button pressed - UNHANDLED")
        elif button == pygame.CONTROLLER_BUTTON_RIGHTSTICK:
            # Right stick button: Currently unhandled
            LOG.debug(f"Controller {controller_id}: RIGHT STICK button pressed - UNHANDLED")
        elif button == pygame.CONTROLLER_BUTTON_X:
            # X button: Currently unhandled
            LOG.debug(f"Controller {controller_id}: X button pressed - UNHANDLED")
        elif button == pygame.CONTROLLER_BUTTON_Y:
            # Y button: Currently unhandled
            LOG.debug(f"Controller {controller_id}: Y button pressed - UNHANDLED")
        elif button == pygame.CONTROLLER_BUTTON_BACK:
            # Back button: Currently unhandled
            LOG.debug(f"Controller {controller_id}: BACK button pressed - UNHANDLED")
        elif button == pygame.CONTROLLER_BUTTON_GUIDE:
            # Guide button: Currently unhandled
            LOG.debug(f"Controller {controller_id}: GUIDE button pressed - UNHANDLED")
        else:
            # Unknown button
            LOG.debug(f"Controller {controller_id}: UNKNOWN button {button} pressed - UNHANDLED")

    def _handle_canvas_button_press(self, controller_id: int, button: int) -> None:
        """Handle button presses for canvas mode."""
        if button == pygame.CONTROLLER_BUTTON_A:
            # A button: Start controller drag operation (only when selected frame is visible)
            if self.selected_frame_visible:
                LOG.debug(f"Controller {controller_id}: A button pressed - starting controller drag")

                # Initialize controller drag tracking if not exists
                if not hasattr(self, 'controller_drags'):
                    self.controller_drags = {}

                # Start drag operation for this controller
                self.controller_drags[controller_id] = {
                    'active': True,
                    'start_position': self.mode_switcher.get_controller_position(controller_id),
                    'pixels_drawn': [],
                    'start_time': time.time()
                }

                # Paint at the current position
                self._canvas_paint_at_controller_position(controller_id)
            else:
                LOG.debug(f"Controller {controller_id}: A button pressed - DISABLED (selected frame hidden)")
                # A button disabled when selected frame is hidden
        elif button == pygame.CONTROLLER_BUTTON_B:
            # B button (Circle): Undo operations
            LOG.debug(f"Controller {controller_id}: B button pressed - UNDO")
            self._handle_undo()
        elif button == pygame.CONTROLLER_BUTTON_Y:
            # Y button (Triangle): Toggle selected frame visibility on canvas
            LOG.debug(f"Controller {controller_id}: Y button pressed - toggling selected frame visibility")
            self._multi_controller_toggle_selected_frame_visibility(controller_id)
        elif button == pygame.CONTROLLER_BUTTON_X:
            # X button (Square): RESERVED for redo operations (only when selected frame is visible)
            if self.selected_frame_visible:
                LOG.debug(f"Controller {controller_id}: X button pressed - REDO")
                self._handle_redo()
            else:
                LOG.debug(f"Controller {controller_id}: X button pressed - DISABLED (selected frame hidden)")
                # X button disabled when selected frame is hidden
        elif button == pygame.CONTROLLER_BUTTON_DPAD_LEFT:
            # D-pad left: Start continuous movement left
            LOG.debug(f"Controller {controller_id}: D-pad left pressed - start continuous movement left")
            self._start_canvas_continuous_movement(controller_id, -1, 0)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_RIGHT:
            # D-pad right: Start continuous movement right
            LOG.debug(f"Controller {controller_id}: D-pad right pressed - start continuous movement right")
            self._start_canvas_continuous_movement(controller_id, 1, 0)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_UP:
            # D-pad up: Start continuous movement up
            LOG.debug(f"Controller {controller_id}: D-pad up pressed - start continuous movement up")
            self._start_canvas_continuous_movement(controller_id, 0, -1)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_DOWN:
            # D-pad down: Start continuous movement down
            LOG.debug(f"Controller {controller_id}: D-pad down pressed - start continuous movement down")
            self._start_canvas_continuous_movement(controller_id, 0, 1)
        elif button == pygame.CONTROLLER_BUTTON_LEFTSHOULDER:
            # Left shoulder button: Move or paint 8 pixels based on controller's fill direction and B button state
            if hasattr(self, 'controller_selections') and controller_id in self.controller_selections:
                fill_direction = self.controller_selections[controller_id].get_fill_direction()
                # Check if A button (X on PS5) is currently held down
                a_button_held = self._is_controller_button_held(controller_id, pygame.CONTROLLER_BUTTON_A)

                if fill_direction == "HORIZONTAL":
                    if a_button_held:
                        LOG.debug(f"Controller {controller_id}: LEFT SHOULDER + A - paint 8 pixels left")
                        self._canvas_paint_horizontal_line(controller_id, -8)
                    else:
                        LOG.debug(f"Controller {controller_id}: LEFT SHOULDER - jump 8 pixels left")
                        self._canvas_jump_horizontal(controller_id, -8)
                else:  # VERTICAL
                    if a_button_held:
                        LOG.debug(f"Controller {controller_id}: LEFT SHOULDER + A - paint 8 pixels up")
                        self._canvas_paint_vertical_line(controller_id, -8)
                    else:
                        LOG.debug(f"Controller {controller_id}: LEFT SHOULDER - jump 8 pixels up")
                        self._canvas_jump_vertical(controller_id, -8)
        elif button == pygame.CONTROLLER_BUTTON_RIGHTSHOULDER:
            # Right shoulder button: Move or paint 8 pixels based on controller's fill direction and B button state
            if hasattr(self, 'controller_selections') and controller_id in self.controller_selections:
                fill_direction = self.controller_selections[controller_id].get_fill_direction()
                # Check if A button (X on PS5) is currently held down
                a_button_held = self._is_controller_button_held(controller_id, pygame.CONTROLLER_BUTTON_A)

                if fill_direction == "HORIZONTAL":
                    if a_button_held:
                        LOG.debug(f"Controller {controller_id}: RIGHT SHOULDER + A - paint 8 pixels right")
                        self._canvas_paint_horizontal_line(controller_id, 8)
                    else:
                        LOG.debug(f"Controller {controller_id}: RIGHT SHOULDER - jump 8 pixels right")
                        self._canvas_jump_horizontal(controller_id, 8)
                else:  # VERTICAL
                    if a_button_held:
                        LOG.debug(f"Controller {controller_id}: RIGHT SHOULDER + A - paint 8 pixels down")
                        self._canvas_paint_vertical_line(controller_id, 8)
                    else:
                        LOG.debug(f"Controller {controller_id}: RIGHT SHOULDER - jump 8 pixels down")
                        self._canvas_jump_vertical(controller_id, 8)
        elif button == pygame.CONTROLLER_BUTTON_Y:
            # Y button: Toggle fill direction between HORIZONTAL and VERTICAL for this controller
            if hasattr(self, 'controller_selections') and controller_id in self.controller_selections:
                current_direction = self.controller_selections[controller_id].get_fill_direction()
                if current_direction == "HORIZONTAL":
                    self.controller_selections[controller_id].set_fill_direction("VERTICAL")
                    print(f"DEBUG: Controller {controller_id}: Y button pressed - switched to VERTICAL fill")
                    LOG.debug(f"Controller {controller_id}: Y button pressed - switched to VERTICAL fill")
                else:
                    self.controller_selections[controller_id].set_fill_direction("HORIZONTAL")
                    print(f"DEBUG: Controller {controller_id}: Y button pressed - switched to HORIZONTAL fill")
                    LOG.debug(f"Controller {controller_id}: Y button pressed - switched to HORIZONTAL fill")
        else:
            # Other buttons not handled in canvas mode
            print(f"DEBUG: Controller {controller_id}: Button {button} not handled in canvas mode")
            LOG.debug(f"Controller {controller_id}: Button {button} not handled in canvas mode")

    def _handle_slider_button_press(self, controller_id: int, button: int) -> None:
        """Handle button presses for slider mode."""
        print(f"DEBUG: _handle_slider_button_press called for controller {controller_id}, button {button}")

        if button == pygame.CONTROLLER_BUTTON_A:
            # A button: No action in slider mode
            print(f"DEBUG: Controller {controller_id}: A button pressed - no action in slider mode")
            LOG.debug(f"Controller {controller_id}: A button pressed - no action in slider mode")
        elif button == pygame.CONTROLLER_BUTTON_DPAD_LEFT:
            # D-pad left: Start continuous decrease
            print(f"DEBUG: Controller {controller_id}: D-pad left pressed - start continuous decrease")
            LOG.debug(f"Controller {controller_id}: D-pad left pressed - start continuous decrease")
            self._start_slider_continuous_adjustment(controller_id, -1)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_RIGHT:
            # D-pad right: Start continuous increase
            print(f"DEBUG: Controller {controller_id}: D-pad right pressed - start continuous increase")
            LOG.debug(f"Controller {controller_id}: D-pad right pressed - start continuous increase")
            self._start_slider_continuous_adjustment(controller_id, 1)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_UP:
            # D-pad up: Navigate to previous slider mode (B -> G -> R)
            print(f"DEBUG: Controller {controller_id}: D-pad up pressed - navigate to previous slider mode")
            LOG.debug(f"Controller {controller_id}: D-pad up pressed - navigate to previous slider mode")
            self._handle_slider_mode_navigation("up", controller_id)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_DOWN:
            # D-pad down: Navigate to next slider mode (R -> G -> B)
            print(f"DEBUG: Controller {controller_id}: D-pad down pressed - navigate to next slider mode")
            LOG.debug(f"Controller {controller_id}: D-pad down pressed - navigate to next slider mode")
            self._handle_slider_mode_navigation("down", controller_id)
        elif button == pygame.CONTROLLER_BUTTON_LEFTSHOULDER:
            # Left shoulder (L1): Start continuous decrease by 8
            print(f"DEBUG: Controller {controller_id}: Left shoulder pressed - start continuous decrease by 8")
            LOG.debug(f"Controller {controller_id}: Left shoulder pressed - start continuous decrease by 8")
            self._start_slider_continuous_adjustment(controller_id, -8)
        elif button == pygame.CONTROLLER_BUTTON_RIGHTSHOULDER:
            # Right shoulder (R1): Start continuous increase by 8
            print(f"DEBUG: Controller {controller_id}: Right shoulder pressed - start continuous increase by 8")
            LOG.debug(f"Controller {controller_id}: Right shoulder pressed - start continuous increase by 8")
            self._start_slider_continuous_adjustment(controller_id, 8)
        else:
            # Other buttons not handled in slider mode (including B button)
            print(f"DEBUG: Controller {controller_id}: Button {button} not handled in slider mode")
            LOG.debug(f"Controller {controller_id}: Button {button} not handled in slider mode")

    def on_controller_button_up_event(self, event: pygame.event.Event) -> None:
        """Handle controller button up events.

        Args:
            event (pygame.event.Event): The controller button up event.

        Returns:
            None

        """
        instance_id = event.instance_id

        # Get controller ID for this instance
        controller_id = self.multi_controller_manager.get_controller_id(instance_id)
        if controller_id is None:
            return

        # Handle button releases for continuous slider adjustment (D-pad and shoulder buttons)
        if event.button in [pygame.CONTROLLER_BUTTON_DPAD_LEFT, pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
                           pygame.CONTROLLER_BUTTON_LEFTSHOULDER, pygame.CONTROLLER_BUTTON_RIGHTSHOULDER]:
            self._stop_slider_continuous_adjustment(controller_id)

            # Update color well when slider adjustment is finished (only if controller is in slider mode)
            controller_mode = self.mode_switcher.get_controller_mode(controller_id)
            if controller_mode and controller_mode.value in ["r_slider", "g_slider", "b_slider"]:
                self._update_color_well_from_sliders()

        # Handle button releases for continuous canvas movement (D-pad buttons)
        if event.button in [pygame.CONTROLLER_BUTTON_DPAD_LEFT, pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
                           pygame.CONTROLLER_BUTTON_DPAD_UP, pygame.CONTROLLER_BUTTON_DPAD_DOWN]:
            self._stop_canvas_continuous_movement(controller_id)

        # Handle A button release in canvas mode (end controller drag)
        if event.button == pygame.CONTROLLER_BUTTON_A:
            if hasattr(self, 'controller_drags') and controller_id in self.controller_drags:
                drag_info = self.controller_drags[controller_id]
                if drag_info['active']:
                    # End the drag operation
                    drag_info['active'] = False
                    drag_info['end_time'] = time.time()
                    drag_info['end_position'] = self.mode_switcher.get_controller_position(controller_id)

                    print(f"DEBUG: Controller {controller_id}: Drag operation drew {len(drag_info['pixels_drawn'])} pixels")

                    # Submit collected pixels for undo/redo functionality
                    if drag_info['pixels_drawn']:
                        LOG.debug(f"Controller {controller_id}: Drag operation completed with {len(drag_info['pixels_drawn'])} pixels drawn")

                        # Convert controller drag pixels to undo/redo format
                        pixel_changes = []
                        for pixel_info in drag_info['pixels_drawn']:
                            position = pixel_info['position']
                            color = pixel_info['color']
                            old_color = pixel_info.get('old_color', (0, 0, 0))  # Use stored old color
                            x, y = position[0], position[1]

                            pixel_changes.append((x, y, old_color, color))

                        # Debug: Show undo stack before merging
                        if hasattr(self, 'undo_redo_manager') and self.undo_redo_manager:
                            print(f"DEBUG: Undo stack before merging has {len(self.undo_redo_manager.undo_stack)} operations")
                            for i, op in enumerate(self.undo_redo_manager.undo_stack):
                                print(f"DEBUG:   Operation {i}: {op.operation_type} - {op.description}")

                        # Absorb any pending single pixel operation from canvas interface
                        # This merges the initial A button pixel with the drag pixels
                        if hasattr(self, '_current_pixel_changes') and self._current_pixel_changes:
                            print(f"DEBUG: Absorbing {len(self._current_pixel_changes)} pending pixel(s) from canvas interface")
                            print(f"DEBUG: Pending pixels: {self._current_pixel_changes}")
                            # Add the pending pixels to the beginning of the controller drag pixels
                            pixel_changes = self._current_pixel_changes + pixel_changes
                            print(f"DEBUG: Merged pixel_changes now has {len(pixel_changes)} pixels")
                            # Clear the pending pixels to prevent duplicate undo operation
                            self._current_pixel_changes = []

                            # Remove the old single pixel entry from the undo stack
                            # This prevents having two separate undo operations
                            if hasattr(self, 'undo_redo_manager') and self.undo_redo_manager:
                                # Pop the most recent operation from the undo stack (the single pixel)
                                if self.undo_redo_manager.undo_stack:
                                    removed_operation = self.undo_redo_manager.undo_stack.pop()
                                    print(f"DEBUG: Removed single pixel operation from undo stack: {removed_operation.operation_type}")
                                    print(f"DEBUG: Undo stack after removal has {len(self.undo_redo_manager.undo_stack)} operations")
                                else:
                                    print(f"DEBUG: No operations in undo stack to remove")
                        else:
                            print(f"DEBUG: No pending pixels to absorb from canvas interface")

                        # Submit the pixel changes to the undo/redo system
                        if pixel_changes and hasattr(self, 'canvas_operation_tracker'):
                            # Get current frame information for frame-specific tracking
                            current_animation = None
                            current_frame = None
                            if hasattr(self, "canvas") and self.canvas:
                                current_animation = getattr(self.canvas, "current_animation", None)
                                current_frame = getattr(self.canvas, "current_frame", None)

                            # Use frame-specific tracking if we have frame information
                            if current_animation is not None and current_frame is not None:
                                self.canvas_operation_tracker.add_frame_pixel_changes(
                                    current_animation, current_frame, pixel_changes
                                )
                                LOG.debug(f"Controller {controller_id}: Submitted {len(pixel_changes)} pixel changes for frame {current_animation}[{current_frame}] undo/redo")
                            else:
                                # Fall back to global tracking
                                self.canvas_operation_tracker.add_pixel_changes(pixel_changes)
                                LOG.debug(f"Controller {controller_id}: Submitted {len(pixel_changes)} pixel changes for global undo/redo")

    # Canvas Mode Implementation Methods
    def _canvas_paint_at_controller_position(self, controller_id: int, force: bool = False) -> None:
        """Paint at the controller's current canvas position.

        Args:
            controller_id: The ID of the controller
            force: If True, always paint regardless of current pixel color
        """
        # Get controller's canvas position
        position = self.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            print(f"DEBUG: Controller {controller_id} has no valid canvas position")
            return

        # Get current color from the color picker
        current_color = self._get_current_color()
        print(f"DEBUG: _canvas_paint_at_controller_position() got color: {current_color}")

        # Check if pixel is already the selected color (debouncing)
        if not force and hasattr(self, 'canvas') and self.canvas:
            x, y = position.position[0], position.position[1]
            # Get current pixel color
            if hasattr(self.canvas, 'canvas_interface'):
                current_pixel_color = self.canvas.canvas_interface.get_pixel_at(x, y)
            else:
                # Fallback: directly get pixel if interface not available
                if 0 <= x < self.canvas.pixels_across and 0 <= y < self.canvas.pixels_tall:
                    pixel_num = y * self.canvas.pixels_across + x
                    current_pixel_color = self.canvas.pixels[pixel_num]
                else:
                    current_pixel_color = None

            # Skip painting if the pixel is already the selected color
            if current_pixel_color == current_color:
                print(f"DEBUG: Pixel at {position.position} is already {current_color}, skipping paint")
                return

        # Get the old color BEFORE changing the pixel for undo functionality
        old_color = None
        if hasattr(self, 'canvas') and self.canvas and hasattr(self.canvas, 'canvas_interface'):
            try:
                old_color = self.canvas.canvas_interface.get_pixel_at(position.position[0], position.position[1])
            except:
                old_color = (0, 0, 0)  # Default to black if we can't get the color
        else:
            old_color = (0, 0, 0)  # Default to black

        # Paint at the position
        if hasattr(self, 'canvas') and self.canvas:
            # Use the canvas interface to set the pixel
            if hasattr(self.canvas, 'canvas_interface'):
                self.canvas.canvas_interface.set_pixel_at(position.position[0], position.position[1], current_color)
            else:
                # Fallback: directly set pixel if interface not available
                x, y = position.position[0], position.position[1]
                if 0 <= x < self.canvas.pixels_across and 0 <= y < self.canvas.pixels_tall:
                    pixel_num = y * self.canvas.pixels_across + x
                    self.canvas.pixels[pixel_num] = current_color
                    self.canvas.dirty_pixels[pixel_num] = True
                    self.canvas.dirty = 1

            # Track this pixel in the controller drag operation
            if hasattr(self, 'controller_drags') and controller_id in self.controller_drags:
                drag_info = self.controller_drags[controller_id]
                if drag_info['active']:
                    # Record the pixel that was drawn for undo functionality
                    pixel_info = {
                        'position': position.position,
                        'color': current_color,
                        'old_color': old_color,  # Store the original color for undo
                        'timestamp': time.time()
                    }
                    drag_info['pixels_drawn'].append(pixel_info)
                    print(f"DEBUG: Controller drag tracking pixel at {position.position}, total pixels: {len(drag_info['pixels_drawn'])}")
                else:
                    print(f"DEBUG: Controller drag not active for controller {controller_id}")
            else:
                print(f"DEBUG: No controller drags or controller {controller_id} not in controller_drags")

            print(f"DEBUG: Painted at canvas position {position.position} with color {current_color}")

    def _canvas_erase_at_controller_position(self, controller_id: int) -> None:
        """Erase at the controller's current canvas position."""
        # Get controller's canvas position
        position = self.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            print(f"DEBUG: Controller {controller_id} has no valid canvas position")
            return

        # Erase at the position (paint with background color)
        if hasattr(self, 'canvas') and self.canvas:
            background_color = (0, 0, 0)  # Black background
            # Use the canvas interface to set the pixel
            if hasattr(self.canvas, 'canvas_interface'):
                self.canvas.canvas_interface.set_pixel_at(position.position[0], position.position[1], background_color)
            else:
                # Fallback: directly set pixel if interface not available
                x, y = position.position[0], position.position[1]
                if 0 <= x < self.canvas.pixels_across and 0 <= y < self.canvas.pixels_tall:
                    pixel_num = y * self.canvas.pixels_across + x
                    self.canvas.pixels[pixel_num] = background_color
                    self.canvas.dirty_pixels[pixel_num] = True
                    self.canvas.dirty = 1
            print(f"DEBUG: Erased at canvas position {position.position}")

    def _canvas_move_cursor(self, controller_id: int, dx: int, dy: int) -> None:
        """Move the controller's canvas cursor."""
        # Get current position
        position = self.mode_switcher.get_controller_position(controller_id)
        if not position:
            # Initialize at (0, 0) if no position
            old_position = (0, 0)
            new_position = (0, 0)
        else:
            old_position = position.position
            new_position = (position.position[0] + dx, position.position[1] + dy)

        # Clamp to canvas bounds
        if hasattr(self, 'canvas') and self.canvas:
            canvas_width = getattr(self.canvas, 'width', 32)
            canvas_height = getattr(self.canvas, 'height', 32)
            new_position = (
                max(0, min(canvas_width - 1, new_position[0])),
                max(0, min(canvas_height - 1, new_position[1]))
            )

        # Track controller position change for undo/redo (only if position actually changed and not in continuous movement)
        if (old_position != new_position and
            not getattr(self, '_applying_undo_redo', False) and
            not self._is_controller_in_continuous_movement(controller_id)):
            if hasattr(self, 'controller_position_operation_tracker'):
                # Get current mode for context
                current_mode = self.mode_switcher.get_controller_mode(controller_id)
                mode_str = current_mode.value if current_mode else None

                self.controller_position_operation_tracker.add_controller_position_change(
                    controller_id, old_position, new_position, mode_str, mode_str
                )

        # Update position
        self.mode_switcher.save_controller_position(controller_id, new_position)

        # If controller is in an active drag operation, paint at the new position
        # (the paint method will check if the pixel needs painting)
        if hasattr(self, 'controller_drags') and controller_id in self.controller_drags:
            drag_info = self.controller_drags[controller_id]
            if drag_info['active']:
                print(f"DEBUG: Controller {controller_id}: In active drag, painting at new position {new_position}")
                self._canvas_paint_at_controller_position(controller_id)

        # Update visual indicator
        self._update_controller_canvas_visual_indicator(controller_id)

        print(f"DEBUG: Controller {controller_id} canvas cursor moved to {new_position}")

    def _is_controller_in_continuous_movement(self, controller_id: int) -> bool:
        """Check if a controller is currently in continuous movement mode."""
        # Check for canvas continuous movement
        if hasattr(self, 'canvas_continuous_movements') and controller_id in self.canvas_continuous_movements:
            return True

        # Check for slider continuous adjustment
        if hasattr(self, 'slider_continuous_adjustments') and controller_id in self.slider_continuous_adjustments:
            return True

        return False

    def _update_controller_canvas_visual_indicator(self, controller_id: int) -> None:
        """Update the visual indicator for a controller's canvas position."""
        # Get controller info
        controller_info = self.multi_controller_manager.get_controller_info(controller_id)
        if not controller_info:
            return

        # Get current canvas position
        position = self.mode_switcher.get_controller_position(controller_id)
        if not position:
            return

        # Update visual indicator
        if hasattr(self, 'visual_collision_manager'):
            # Remove old indicator
            self.visual_collision_manager.remove_controller_indicator(controller_id)

            # Add new canvas indicator
            from glitchygames.tools.visual_collision_manager import LocationType
            self.visual_collision_manager.add_controller_indicator(
                controller_id, controller_info.instance_id,
                controller_info.color, position.position, LocationType.CANVAS)

    def _get_current_color(self) -> tuple:
        """Get the current color from the color picker."""
        # Get color from sliders if available
        if hasattr(self, 'red_slider') and hasattr(self, 'green_slider') and hasattr(self, 'blue_slider'):
            try:
                red = int(self.red_slider.value)
                green = int(self.green_slider.value)
                blue = int(self.blue_slider.value)
                print(f"DEBUG: _get_current_color() returning color from sliders: ({red}, {green}, {blue})")
                return (red, green, blue)
            except (ValueError, AttributeError) as e:
                print(f"DEBUG: _get_current_color() error getting slider values: {e}")
                pass

        # Default to white if sliders not available
        print(f"DEBUG: _get_current_color() sliders not available, returning white")
        return (255, 255, 255)

    # Slider Mode Implementation Methods
    def _update_color_well_from_sliders(self) -> None:
        """Update the color well with current slider values."""
        print(f"DEBUG: _update_color_well_from_sliders called")
        if hasattr(self, 'color_well') and self.color_well:
            # Get current slider values
            red_value = self.red_slider.value if hasattr(self, 'red_slider') else 0
            green_value = self.green_slider.value if hasattr(self, 'green_slider') else 0
            blue_value = self.blue_slider.value if hasattr(self, 'blue_slider') else 0
            alpha_value = self.alpha_slider.value if hasattr(self, 'alpha_slider') else 0

            print(f"DEBUG: Slider values - R:{red_value}, G:{green_value}, B:{blue_value}, A:{alpha_value}")
            print(f"DEBUG: Color well before update: {self.color_well.active_color}")

            # Update color well
            self.color_well.active_color = (red_value, green_value, blue_value, alpha_value)

            # Force color well to redraw
            if hasattr(self.color_well, 'dirty'):
                self.color_well.dirty = 1

            # Also dirty the main scene to ensure redraw
            self.dirty = 1

            # Force color well to update its display
            if hasattr(self.color_well, 'force_redraw'):
                self.color_well.force_redraw()

            print(f"DEBUG: Updated color well to ({red_value}, {green_value}, {blue_value})")
        else:
            print(f"DEBUG: No color_well found or color_well is None")

    def _handle_slider_mode_navigation(self, direction: str, controller_id: int = None) -> None:
        """Handle arrow key navigation between slider modes."""
        if not hasattr(self, 'mode_switcher'):
            return

        # If no specific controller provided, find the first controller in slider mode (for keyboard navigation)
        if controller_id is None:
            target_controller_id = None
            for cid in self.mode_switcher.controller_modes:
                controller_mode = self.mode_switcher.get_controller_mode(cid)
                if controller_mode and controller_mode.value in ["r_slider", "g_slider", "b_slider"]:
                    target_controller_id = cid
                    break
        else:
            # Use the specific controller (for D-pad navigation)
            target_controller_id = controller_id

        if target_controller_id is None:
            return

        current_mode = self.mode_switcher.get_controller_mode(target_controller_id)
        if not current_mode:
            return

        # Define the slider mode cycle
        slider_cycle = [
            ControllerMode.R_SLIDER,
            ControllerMode.G_SLIDER,
            ControllerMode.B_SLIDER
        ]

        # Find current position in cycle
        if current_mode not in slider_cycle:
            return

        current_index = slider_cycle.index(current_mode)

        # Calculate new index based on direction
        if direction == "up":
            # B -> G -> R
            new_index = (current_index - 1) % len(slider_cycle)
        else:  # direction == "down"
            # R -> G -> B
            new_index = (current_index + 1) % len(slider_cycle)

        new_mode = slider_cycle[new_index]

        # Switch to new mode
        current_time = time.time()
        self.mode_switcher.controller_modes[target_controller_id].switch_to_mode(new_mode, current_time)

        print(f"DEBUG: Slider mode navigation - switched controller {target_controller_id} from {current_mode.value} to {new_mode.value}")
        self.log.debug(f"Slider mode navigation - switched controller {target_controller_id} from {current_mode.value} to {new_mode.value}")

    def _slider_adjust_value(self, controller_id: int, delta: int) -> None:
        """Adjust the current slider's value."""
        print(f"DEBUG: _slider_adjust_value called for controller {controller_id}, delta {delta}")

        # Get the controller's current mode to determine which slider
        if hasattr(self, 'mode_switcher'):
            controller_mode = self.mode_switcher.get_controller_mode(controller_id)
            print(f"DEBUG: Controller {controller_id} mode: {controller_mode.value if controller_mode else 'None'}")

            # Adjust the appropriate slider based on mode
            if controller_mode and controller_mode.value == "r_slider":
                old_value = self.red_slider.value
                new_value = max(0, min(255, old_value + delta))
                print(f"DEBUG: R slider: {old_value} -> {new_value}")
                # Update the slider value
                self.red_slider.value = new_value
                # Create a trigger event to properly update the color well
                trigger = pygame.event.Event(0, {"name": "R", "value": new_value})
                self.on_slider_event(pygame.event.Event(0), trigger)
                print(f"DEBUG: Adjusted R slider to {new_value}")
            elif controller_mode and controller_mode.value == "g_slider":
                old_value = self.green_slider.value
                new_value = max(0, min(255, old_value + delta))
                print(f"DEBUG: G slider: {old_value} -> {new_value}")
                # Update the slider value
                self.green_slider.value = new_value
                # Create a trigger event to properly update the color well
                trigger = pygame.event.Event(0, {"name": "G", "value": new_value})
                self.on_slider_event(pygame.event.Event(0), trigger)
                print(f"DEBUG: Adjusted G slider to {new_value}")
            elif controller_mode and controller_mode.value == "b_slider":
                old_value = self.blue_slider.value
                new_value = max(0, min(255, old_value + delta))
                print(f"DEBUG: B slider: {old_value} -> {new_value}")
                # Update the slider value
                self.blue_slider.value = new_value
                # Create a trigger event to properly update the color well
                trigger = pygame.event.Event(0, {"name": "B", "value": new_value})
                self.on_slider_event(pygame.event.Event(0), trigger)
                print(f"DEBUG: Adjusted B slider to {new_value}")
            else:
                print(f"DEBUG: No matching slider mode for {controller_mode.value if controller_mode else 'None'}")
        else:
            print(f"DEBUG: No mode_switcher found")

    def _start_slider_continuous_adjustment(self, controller_id: int, direction: int) -> None:
        """Start continuous slider adjustment with acceleration."""
        if not hasattr(self, 'slider_continuous_adjustments'):
            self.slider_continuous_adjustments = {}

        # Do the first tick immediately for responsive feel
        self._slider_adjust_value(controller_id, direction)

        # Initialize continuous adjustment for this controller
        # Set last_adjustment to current time so the next adjustment waits for the full interval
        current_time = time.time()
        self.slider_continuous_adjustments[controller_id] = {
            'direction': direction,
            'start_time': current_time,
            'last_adjustment': current_time,
            'acceleration_level': 0
        }
        print(f"DEBUG: Started continuous slider adjustment for controller {controller_id}, direction {direction} (immediate first tick)")

    def _stop_slider_continuous_adjustment(self, controller_id: int) -> None:
        """Stop continuous slider adjustment."""
        if hasattr(self, 'slider_continuous_adjustments') and controller_id in self.slider_continuous_adjustments:
            del self.slider_continuous_adjustments[controller_id]
            print(f"DEBUG: Stopped continuous slider adjustment for controller {controller_id}")

    def _update_slider_continuous_adjustments(self) -> None:
        """Update continuous slider adjustments with acceleration."""
        if not hasattr(self, 'slider_continuous_adjustments'):
            return

        current_time = time.time()

        for controller_id, adjustment_data in list(self.slider_continuous_adjustments.items()):
            # Calculate time since start and since last adjustment
            time_since_start = current_time - adjustment_data['start_time']
            time_since_last = current_time - adjustment_data['last_adjustment']

            # Calculate acceleration level (0-3)
            # 0-0.8s: level 0 (1 tick per 0.15s) - longer delay for precision
            # 0.8-1.5s: level 1 (2 ticks per 0.1s)
            # 1.5-2.5s: level 2 (4 ticks per 0.05s)
            # 2.5s+: level 3 (8 ticks per 0.025s)
            if time_since_start < 0.8:
                acceleration_level = 0
                interval = 0.15  # ~6.7 ticks per second
            elif time_since_start < 1.5:
                acceleration_level = 1
                interval = 0.1  # 10 ticks per second
            elif time_since_start < 2.5:
                acceleration_level = 2
                interval = 0.05  # 20 ticks per second
            else:
                acceleration_level = 3
                interval = 0.025  # 40 ticks per second

            # Update acceleration level if changed
            if acceleration_level != adjustment_data['acceleration_level']:
                adjustment_data['acceleration_level'] = acceleration_level
                print(f"DEBUG: Controller {controller_id} slider acceleration level {acceleration_level}")

            # Check if enough time has passed for next adjustment
            if time_since_last >= interval:
                # Calculate delta based on acceleration level (1, 2, 4, 8)
                delta = adjustment_data['direction'] * (2 ** acceleration_level)
                delta = max(-8, min(8, delta))  # Cap at ±8

                # Apply the adjustment
                self._slider_adjust_value(controller_id, delta)

                # Update color well during continuous adjustment
                controller_mode = self.mode_switcher.get_controller_mode(controller_id)
                print(f"DEBUG: Continuous adjustment - controller {controller_id} mode: {controller_mode.value if controller_mode else 'None'}")
                if controller_mode and controller_mode.value in ["r_slider", "g_slider", "b_slider"]:
                    print(f"DEBUG: Calling _update_color_well_from_sliders during continuous adjustment")
                    self._update_color_well_from_sliders()
                else:
                    print(f"DEBUG: Not updating color well - controller not in slider mode")

                # Update last adjustment time
                adjustment_data['last_adjustment'] = current_time

    def _start_canvas_continuous_movement(self, controller_id: int, dx: int, dy: int) -> None:
        """Start continuous canvas movement with acceleration."""
        if not hasattr(self, 'canvas_continuous_movements'):
            self.canvas_continuous_movements = {}

        # Do the first movement immediately for responsive feel
        self._canvas_move_cursor(controller_id, dx, dy)

        # Get starting position for undo/redo tracking
        start_position = self.mode_switcher.get_controller_position(controller_id)
        start_x, start_y = start_position.position if start_position else (0, 0)

        # Initialize continuous movement for this controller
        current_time = time.time()
        self.canvas_continuous_movements[controller_id] = {
            'dx': dx,
            'dy': dy,
            'start_time': current_time,
            'last_movement': current_time,
            'acceleration_level': 0,
            'start_x': start_x,
            'start_y': start_y
        }
        print(f"DEBUG: Started continuous canvas movement for controller {controller_id}, direction ({dx}, {dy}) (immediate first movement)")

    def _stop_canvas_continuous_movement(self, controller_id: int) -> None:
        """Stop continuous canvas movement."""
        if hasattr(self, 'canvas_continuous_movements') and controller_id in self.canvas_continuous_movements:
            # Track the final position change for undo/redo
            if hasattr(self, 'controller_position_operation_tracker'):
                # Get the starting position from the movement data
                movement_data = self.canvas_continuous_movements[controller_id]
                start_position = (movement_data.get('start_x', 0), movement_data.get('start_y', 0))

                # Get current position
                current_position = self.mode_switcher.get_controller_position(controller_id)
                if current_position:
                    current_pos = current_position.position
                else:
                    current_pos = (0, 0)

                # Only track if position actually changed
                if start_position != current_pos:
                    current_mode = self.mode_switcher.get_controller_mode(controller_id)
                    mode_str = current_mode.value if current_mode else None

                    self.controller_position_operation_tracker.add_controller_position_change(
                        controller_id, start_position, current_pos, mode_str, mode_str
                    )

            del self.canvas_continuous_movements[controller_id]
            print(f"DEBUG: Stopped continuous canvas movement for controller {controller_id}")

    def _update_canvas_continuous_movements(self) -> None:
        """Update continuous canvas movements with acceleration."""
        if not hasattr(self, 'canvas_continuous_movements'):
            return

        current_time = time.time()

        for controller_id, movement_data in list(self.canvas_continuous_movements.items()):
            # Calculate time since start and since last movement
            time_since_start = current_time - movement_data['start_time']
            time_since_last = current_time - movement_data['last_movement']

            # Calculate acceleration level (same as sliders)
            if time_since_start < 0.8:
                acceleration_level = 0
                interval = 0.15  # ~6.7 movements per second
            elif time_since_start < 1.5:
                acceleration_level = 1
                interval = 0.1  # 10 movements per second
            elif time_since_start < 2.5:
                acceleration_level = 2
                interval = 0.05  # 20 movements per second
            else:
                acceleration_level = 3
                interval = 0.025  # 40 movements per second

            # Update acceleration level if changed
            if acceleration_level != movement_data['acceleration_level']:
                movement_data['acceleration_level'] = acceleration_level
                print(f"DEBUG: Controller {controller_id} canvas movement acceleration level {acceleration_level}")

            # Check if enough time has passed for next movement
            if time_since_last >= interval:
                # Calculate movement delta based on acceleration level (1, 2, 4, 8)
                dx = movement_data['dx'] * (2 ** acceleration_level)
                dy = movement_data['dy'] * (2 ** acceleration_level)
                dx = max(-8, min(8, dx))  # Cap at ±8
                dy = max(-8, min(8, dy))  # Cap at ±8

                # Apply the movement
                self._canvas_move_cursor(controller_id, dx, dy)

                # If this controller has an active drag operation, paint at the new position
                if (hasattr(self, 'controller_drags') and
                    controller_id in self.controller_drags and
                    self.controller_drags[controller_id]['active']):
                    self._canvas_paint_at_controller_position(controller_id)

                # Update last movement time
                movement_data['last_movement'] = current_time

    def _canvas_paint_horizontal_line(self, controller_id: int, distance: int) -> None:
        """Paint a horizontal line of pixels starting from the controller's current position."""
        print(f"DEBUG: _canvas_paint_horizontal_line called for controller {controller_id}, distance {distance}")

        # Get controller position from mode switcher
        position = self.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            print(f"DEBUG: No valid position found for controller {controller_id}")
            return

        start_x, start_y = position.position
        current_color = self._get_current_color()

        print(f"DEBUG: Painting horizontal line from ({start_x}, {start_y}) with distance {distance}, color {current_color}")

        # Get canvas dimensions for boundary checking
        canvas_width = 0
        canvas_height = 0
        if hasattr(self, 'canvas') and self.canvas:
            canvas_width = getattr(self.canvas, 'pixels_across', 0)
            canvas_height = getattr(self.canvas, 'pixels_tall', 0)

        print(f"DEBUG: Canvas dimensions: {canvas_width}x{canvas_height}")

        # Paint pixels in a horizontal line
        for i in range(abs(distance)):
            if distance > 0:
                # Moving right
                pixel_x = start_x + i
            else:
                # Moving left
                pixel_x = start_x - i

            pixel_y = start_y

            # Clamp coordinates to canvas bounds
            if canvas_width > 0:
                pixel_x = max(0, min(pixel_x, canvas_width - 1))
            if canvas_height > 0:
                pixel_y = max(0, min(pixel_y, canvas_height - 1))

            # Get the old color BEFORE changing the pixel for undo functionality
            old_color = None
            if hasattr(self, 'canvas') and self.canvas and hasattr(self.canvas, 'canvas_interface'):
                try:
                    old_color = self.canvas.canvas_interface.get_pixel_at(pixel_x, pixel_y)
                except:
                    old_color = (0, 0, 0)  # Default to black if we can't get the color
            else:
                old_color = (0, 0, 0)  # Default to black

            # Paint the pixel using the canvas interface
            if hasattr(self, 'canvas') and self.canvas and hasattr(self.canvas, 'canvas_interface'):
                self.canvas.canvas_interface.set_pixel_at(pixel_x, pixel_y, current_color)
                print(f"DEBUG: Painted pixel at ({pixel_x}, {pixel_y}) with color {current_color}")

                # Track this pixel in the controller drag operation
                if hasattr(self, 'controller_drags') and controller_id in self.controller_drags:
                    drag_info = self.controller_drags[controller_id]
                    if drag_info['active']:
                        # Record the pixel that was drawn for undo functionality
                        pixel_info = {
                            'position': (pixel_x, pixel_y),
                            'color': current_color,
                            'old_color': old_color,  # Store the original color for undo
                            'timestamp': time.time()
                        }
                        drag_info['pixels_drawn'].append(pixel_info)
            else:
                print(f"DEBUG: No canvas or canvas_interface available")

        # Force canvas redraw
        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.force_redraw()

        # Update controller position to the end of the line (clamped to canvas bounds)
        end_x = start_x + distance
        if canvas_width > 0:
            end_x = max(0, min(end_x, canvas_width - 1))
        if canvas_height > 0:
            start_y = max(0, min(start_y, canvas_height - 1))

        self.mode_switcher.save_controller_position(controller_id, (end_x, start_y))
        print(f"DEBUG: Updated controller {controller_id} position to ({end_x}, {start_y}) (clamped to canvas bounds)")

    def _canvas_paint_vertical_line(self, controller_id: int, distance: int) -> None:
        """Paint a vertical line of pixels starting from the controller's current position."""
        print(f"DEBUG: _canvas_paint_vertical_line called for controller {controller_id}, distance {distance}")

        # Get controller position from mode switcher
        position = self.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            print(f"DEBUG: No valid position found for controller {controller_id}")
            return

        start_x, start_y = position.position
        current_color = self._get_current_color()

        print(f"DEBUG: Painting vertical line from ({start_x}, {start_y}) with distance {distance}, color {current_color}")

        # Get canvas dimensions for boundary checking
        canvas_width = 0
        canvas_height = 0
        if hasattr(self, 'canvas') and self.canvas:
            canvas_width = getattr(self.canvas, 'pixels_across', 0)
            canvas_height = getattr(self.canvas, 'pixels_tall', 0)

        print(f"DEBUG: Canvas dimensions: {canvas_width}x{canvas_height}")

        # Paint pixels in a vertical line
        for i in range(abs(distance)):
            if distance > 0:
                # Moving down
                pixel_y = start_y + i
            else:
                # Moving up
                pixel_y = start_y - i

            pixel_x = start_x

            # Clamp coordinates to canvas bounds
            if canvas_width > 0:
                pixel_x = max(0, min(pixel_x, canvas_width - 1))
            if canvas_height > 0:
                pixel_y = max(0, min(pixel_y, canvas_height - 1))

            # Get the old color BEFORE changing the pixel for undo functionality
            old_color = None
            if hasattr(self, 'canvas') and self.canvas and hasattr(self.canvas, 'canvas_interface'):
                try:
                    old_color = self.canvas.canvas_interface.get_pixel_at(pixel_x, pixel_y)
                except:
                    old_color = (0, 0, 0)  # Default to black if we can't get the color
            else:
                old_color = (0, 0, 0)  # Default to black

            # Paint the pixel using the canvas interface
            if hasattr(self, 'canvas') and self.canvas and hasattr(self.canvas, 'canvas_interface'):
                self.canvas.canvas_interface.set_pixel_at(pixel_x, pixel_y, current_color)
                print(f"DEBUG: Painted pixel at ({pixel_x}, {pixel_y}) with color {current_color}")

                # Track this pixel in the controller drag operation
                if hasattr(self, 'controller_drags') and controller_id in self.controller_drags:
                    drag_info = self.controller_drags[controller_id]
                    if drag_info['active']:
                        # Record the pixel that was drawn for undo functionality
                        pixel_info = {
                            'position': (pixel_x, pixel_y),
                            'color': current_color,
                            'old_color': old_color,  # Store the original color for undo
                            'timestamp': time.time()
                        }
                        drag_info['pixels_drawn'].append(pixel_info)
            else:
                print(f"DEBUG: No canvas or canvas_interface available")

        # Force canvas redraw
        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.force_redraw()

        # Update controller position to the end of the line (clamped to canvas bounds)
        end_y = start_y + distance
        if canvas_width > 0:
            start_x = max(0, min(start_x, canvas_width - 1))
        if canvas_height > 0:
            end_y = max(0, min(end_y, canvas_height - 1))

        self.mode_switcher.save_controller_position(controller_id, (start_x, end_y))
        print(f"DEBUG: Updated controller {controller_id} position to ({start_x}, {end_y}) (clamped to canvas bounds)")

    def _is_controller_button_held(self, controller_id: int, button: int) -> bool:
        """Check if a controller button is currently held down."""
        try:
            # Get the controller instance
            controller = pygame.joystick.Joystick(controller_id)
            return controller.get_button(button)
        except (pygame.error, ValueError):
            return False

    def _canvas_jump_horizontal(self, controller_id: int, distance: int) -> None:
        """Jump horizontally without painting pixels."""
        print(f"DEBUG: _canvas_jump_horizontal called for controller {controller_id}, distance {distance}")

        # Get controller position from mode switcher
        position = self.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            print(f"DEBUG: No valid position found for controller {controller_id}")
            return

        start_x, start_y = position.position

        # Get canvas dimensions for boundary checking
        canvas_width = 0
        if hasattr(self, 'canvas') and self.canvas:
            canvas_width = getattr(self.canvas, 'pixels_across', 0)

        # Calculate new position
        end_x = start_x + distance

        # Clamp to canvas bounds
        if canvas_width > 0:
            end_x = max(0, min(end_x, canvas_width - 1))

        # Update controller position
        self.mode_switcher.save_controller_position(controller_id, (end_x, start_y))
        print(f"DEBUG: Controller {controller_id} jumped from ({start_x}, {start_y}) to ({end_x}, {start_y})")

    def _canvas_jump_vertical(self, controller_id: int, distance: int) -> None:
        """Jump vertically without painting pixels."""
        print(f"DEBUG: _canvas_jump_vertical called for controller {controller_id}, distance {distance}")

        # Get controller position from mode switcher
        position = self.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            print(f"DEBUG: No valid position found for controller {controller_id}")
            return

        start_x, start_y = position.position

        # Get canvas dimensions for boundary checking
        canvas_height = 0
        if hasattr(self, 'canvas') and self.canvas:
            canvas_height = getattr(self.canvas, 'pixels_tall', 0)

        # Calculate new position
        end_y = start_y + distance

        # Clamp to canvas bounds
        if canvas_height > 0:
            end_y = max(0, min(end_y, canvas_height - 1))

        # Update controller position
        self.mode_switcher.save_controller_position(controller_id, (start_x, end_y))
        print(f"DEBUG: Controller {controller_id} jumped from ({start_x}, {start_y}) to ({start_x}, {end_y})")

    def _slider_previous(self, controller_id: int) -> None:
        """Move to the previous slider (now handled by L2/R2 mode switching)."""
        print(f"DEBUG: Controller {controller_id} moved to previous slider")
        # This is now handled by L2/R2 mode switching, so this is just for D-pad compatibility
        pass

    def _slider_next(self, controller_id: int) -> None:
        """Move to the next slider (now handled by L2/R2 mode switching)."""
        print(f"DEBUG: Controller {controller_id} moved to next slider")
        # This is now handled by L2/R2 mode switching, so this is just for D-pad compatibility
        pass

    def on_joy_button_down_event(self, event: pygame.event.Event) -> None:
        """Handle joystick button down events (for controllers detected as joysticks).

        Args:
            event (pygame.event.Event): The joystick button down event.

        Returns:
            None

        """
        # print(f"DEBUG: Joystick button down event received: button={event.button}")
        # print(f"DEBUG: Joystick instance_id: {getattr(event, 'instance_id', 'N/A')}")
        # print(f"DEBUG: Joystick joy: {getattr(event, 'joy', 'N/A')}")
        # print(f"DEBUG: This could be the source of the reset behavior!")
        # LOG.debug(f"Joystick button down: {event.button}")

        # Map joystick buttons to controller actions
        # Button 9 is likely LEFT SHOULDER button, not START
        if event.button == 9:  # LEFT SHOULDER button
            # print("DEBUG: Joystick LEFT SHOULDER button pressed - UNHANDLED")
            # Left shoulder button: Currently unhandled to prevent reset behavior
            # controller_id = getattr(event, 'instance_id', 0)
            # self._multi_controller_activate(controller_id)
            pass
        elif event.button == 0:  # A button
            # print("DEBUG: Joystick A button pressed - selecting current frame with multi-controller system")
            # Use new multi-controller system instead of old single-controller system
            controller_id = getattr(event, 'instance_id', 0)
            self._multi_controller_select_current_frame(controller_id)
        elif event.button == 1:  # B button
            # print("DEBUG: Joystick B button pressed - cancel")
            self._controller_cancel()
        else:
            # Unknown joystick button - this might be the shoulder button!
            # print(f"DEBUG: Joystick UNKNOWN button {event.button} pressed - UNHANDLED")
            # print(f"DEBUG: This could be the left shoulder button causing the reset!")
            # LOG.debug(f"Joystick unknown button: {event.button}")
            pass

    def on_joy_button_up_event(self, event: pygame.event.Event) -> None:
        """Handle joystick button up events.

        Args:
            event (pygame.event.Event): The joystick button up event.

        Returns:
            None

        """
        # print(f"DEBUG: Joystick button up event received: button={event.button}")
        # LOG.debug(f"Joystick button up: {event.button}")

    def on_joy_hat_motion_event(self, event: pygame.event.Event) -> None:
        """Handle joystick hat motion events - requires threshold to prevent jittery behavior.

        Args:
            event (pygame.event.Event): The joystick hat motion event.

        Returns:
            None

        """
        print(f"DEBUG: Joystick hat motion: hat={event.hat}, value={event.value}")

        # Only respond to strong hat inputs (threshold > 0.5)
        # Hat values: 0=center, 1=up, 2=right, 4=down, 8=left, etc.
        if abs(event.value) < 0.5:
            print("DEBUG: Joystick hat motion below threshold, ignoring")
            return

        # Map hat directions to controller actions
        if event.value == 1:  # Up
            print("DEBUG: Joystick hat up - DISABLED (use multi-controller system)")
            # OLD SYSTEM DISABLED - Use multi-controller system instead
            return
        elif event.value == 2:  # Right
            print("DEBUG: Joystick hat right - DISABLED (use multi-controller system)")
            # OLD SYSTEM DISABLED - Use multi-controller system instead
            return
        elif event.value == 4:  # Down
            print("DEBUG: Joystick hat down - DISABLED (use multi-controller system)")
            # OLD SYSTEM DISABLED - Use multi-controller system instead
            return
        elif event.value == 8:  # Left
            print("DEBUG: Joystick hat left - DISABLED (use multi-controller system)")
            # OLD SYSTEM DISABLED - Use multi-controller system instead
            return

    def on_joy_axis_motion_event(self, event: pygame.event.Event) -> None:
        """Handle joystick axis motion events - disabled to prevent jittery behavior.

        Args:
            event (pygame.event.Event): The joystick axis motion event.

        Returns:
            None

        """
        # Handle trigger axis motion for mode switching (axes 4 and 5)
        if event.axis in [4, 5]:  # TRIGGERLEFT and TRIGGERRIGHT
            print(f"DEBUG: Trigger axis motion detected: axis={event.axis}, value={event.value}")
            self._handle_trigger_axis_motion(event)
            return

        print(f"DEBUG: Joystick axis motion (DISABLED): axis={event.axis}, value={event.value}")
        # Disabled to prevent jittery behavior
        pass

    def on_joy_ball_motion_event(self, event: pygame.event.Event) -> None:
        """Handle joystick ball motion events - disabled to prevent jittery behavior.

        Args:
            event (pygame.event.Event): The joystick ball motion event.

        Returns:
            None

        """
        print(f"DEBUG: Joystick ball motion (DISABLED): ball={event.ball}, rel={event.rel}")
        # Disabled to prevent jittery behavior
        pass

    def on_controller_axis_motion_event(self, event: pygame.event.Event) -> None:
        """Handle controller axis motion events.

        Args:
            event (pygame.event.Event): The controller axis motion event.

        Returns:
            None

        """
        # Handle trigger axis motion for mode switching
        if event.axis in [pygame.CONTROLLER_AXIS_TRIGGERLEFT, pygame.CONTROLLER_AXIS_TRIGGERRIGHT]:
            self._handle_trigger_axis_motion(event)
            return

        # REMOVE: Disabled to prevent jittery behavior for stick axes
        return
        print(f"DEBUG: Controller axis motion: axis={event.axis}, value={event.value}")
        print(f"DEBUG: LEFT_X axis constant: {pygame.CONTROLLER_AXIS_LEFTX}")
        print(f"DEBUG: LEFT_Y axis constant: {pygame.CONTROLLER_AXIS_LEFTY}")
        print(f"DEBUG: RIGHT_X axis constant: {pygame.CONTROLLER_AXIS_RIGHTX}")
        print(f"DEBUG: RIGHT_Y axis constant: {pygame.CONTROLLER_AXIS_RIGHTY}")
        print(f"DEBUG: Controller selection active: {getattr(self, 'controller_selection_active', False)}")

        # Left stick for fine frame navigation (only if controller selection is active)
        if not hasattr(self, 'controller_selection_active') or not self.controller_selection_active:
            print("DEBUG: Controller selection not active, ignoring analog stick input")
            return

        # Get current time for cooldown tracking
        import time
        current_time = time.time()

        if event.axis == pygame.CONTROLLER_AXIS_LEFTX:
            # Apply deadzone and cooldown to prevent jittery behavior
            if abs(event.value) < self._controller_axis_deadzone:
                # Within deadzone - reset cooldown and last value
                self._controller_axis_cooldown[event.axis] = 0
                self._controller_axis_last_values[event.axis] = 0
                return

            # Check cooldown
            if (event.axis in self._controller_axis_cooldown and
                current_time - self._controller_axis_cooldown[event.axis] < self._controller_axis_cooldown_duration):
                return

            # Check if direction changed (prevents rapid back-and-forth)
            last_value = self._controller_axis_last_values.get(event.axis, 0)
            if (last_value < 0 and event.value > 0) or (last_value > 0 and event.value < 0):
                # Direction changed, reset cooldown
                self._controller_axis_cooldown[event.axis] = current_time
                self._controller_axis_last_values[event.axis] = event.value
                return

            if event.value < -self._controller_axis_hat_threshold:  # Left stick left (hat-like behavior)
                print("DEBUG: Left stick left - DISABLED (use multi-controller system)")
                # OLD SYSTEM DISABLED - Use multi-controller system instead
                return
            elif event.value > self._controller_axis_hat_threshold:  # Left stick right (hat-like behavior)
                print("DEBUG: Left stick right - DISABLED (use multi-controller system)")
                # OLD SYSTEM DISABLED - Use multi-controller system instead
                return

            self._controller_axis_last_values[event.axis] = event.value

        elif event.axis == pygame.CONTROLLER_AXIS_LEFTY:
            # Apply same anti-jitter logic to Y axis
            if abs(event.value) < self._controller_axis_deadzone:
                self._controller_axis_cooldown[event.axis] = 0
                self._controller_axis_last_values[event.axis] = 0
                return

            if (event.axis in self._controller_axis_cooldown and
                current_time - self._controller_axis_cooldown[event.axis] < self._controller_axis_cooldown_duration):
                return

            last_value = self._controller_axis_last_values.get(event.axis, 0)
            if (last_value < 0 and event.value > 0) or (last_value > 0 and event.value < 0):
                self._controller_axis_cooldown[event.axis] = current_time
                self._controller_axis_last_values[event.axis] = event.value
                return

            if event.value < -self._controller_axis_hat_threshold:  # Left stick up (hat-like behavior)
                print("DEBUG: Left stick up - DISABLED (use multi-controller system)")
                # OLD SYSTEM DISABLED - Use multi-controller system instead
                return
            elif event.value > self._controller_axis_hat_threshold:  # Left stick down (hat-like behavior)
                print("DEBUG: Left stick down - DISABLED (use multi-controller system)")
                # OLD SYSTEM DISABLED - Use multi-controller system instead
                return

            self._controller_axis_last_values[event.axis] = event.value

    def _handle_trigger_axis_motion(self, event: pygame.event.Event) -> None:
        """Handle trigger axis motion for mode switching.

        Args:
            event (pygame.event.Event): The controller/joystick axis motion event.
        """
        # Get controller ID for this instance
        # For joystick events, we need to find the controller by device index
        if hasattr(event, 'instance_id') and event.instance_id is not None:
            # Controller event
            instance_id = event.instance_id
            controller_id = self.multi_controller_manager.get_controller_id(instance_id)
            print(f"DEBUG: Controller event - instance_id={instance_id}, controller_id={controller_id}")
        else:
            # Joystick event - use device index directly
            device_index = event.joy
            controller_id = device_index

            print(f"DEBUG: Joystick event - using device index {device_index} as controller ID {controller_id}")

        if controller_id is None:
            print(f"DEBUG: No controller ID found for event")
            return

        # Register controller with mode switcher if not already registered
        if controller_id not in self.mode_switcher.controller_modes:
            from glitchygames.tools.controller_mode_system import ControllerMode
            self.mode_switcher.register_controller(controller_id, ControllerMode.FILM_STRIP)
            print(f"DEBUG: Registered controller {controller_id} with mode switcher")

        # Get current time
        import time
        current_time = time.time()

        # Get trigger values
        l2_value = 0.0
        r2_value = 0.0

        # Get current trigger values
        if hasattr(event, 'instance_id'):
            # Controller event - get from controller object
            if hasattr(self, 'multi_controller_manager'):
                controller_info = self.multi_controller_manager.get_controller_info(event.instance_id)
                print(f"DEBUG: Controller info lookup - instance_id={event.instance_id}, controller_info={controller_info}")
                if controller_info:
                    # Get the controller object directly from pygame using instance_id
                    try:
                        controller = pygame.joystick.Joystick(event.instance_id)
                        # Convert pygame trigger values (-1.0 to 1.0) to our expected range (0.0 to 1.0)
                        l2_raw = controller.get_axis(pygame.CONTROLLER_AXIS_TRIGGERLEFT)
                        r2_raw = controller.get_axis(pygame.CONTROLLER_AXIS_TRIGGERRIGHT)
                        l2_value = (l2_raw + 1.0) / 2.0  # Convert -1.0..1.0 to 0.0..1.0
                        r2_value = (r2_raw + 1.0) / 2.0  # Convert -1.0..1.0 to 0.0..1.0
                        print(f"DEBUG: Controller {controller_id} triggers - L2: {l2_value:.2f}, R2: {r2_value:.2f}")
                    except Exception as e:
                        print(f"DEBUG: Error getting controller object for instance_id={event.instance_id}: {e}")
                        l2_value = 0.0
                        r2_value = 0.0
                else:
                    print(f"DEBUG: No controller info found for instance_id={event.instance_id}")
        else:
            # Joystick event - get both trigger values from joystick
            print(f"DEBUG: Processing joystick event for controller {controller_id}, joy={event.joy}")
            try:
                joystick = pygame.joystick.Joystick(event.joy)
                print(f"DEBUG: Created joystick object for joy {event.joy}")
                l2_raw = joystick.get_axis(4)  # TRIGGERLEFT
                r2_raw = joystick.get_axis(5)  # TRIGGERRIGHT

                # Convert joystick raw values to 0.0..1.0 range
                # Joystick values are typically in the range -32768 to 32767
                # We need to normalize them to 0.0 to 1.0
                l2_value = max(0.0, min(1.0, (l2_raw + 32768.0) / 65535.0))
                r2_value = max(0.0, min(1.0, (r2_raw + 32768.0) / 65535.0))

                print(f"DEBUG: Joystick {controller_id} raw values - L2: {l2_raw:.2f}, R2: {r2_raw:.2f}")
                print(f"DEBUG: Joystick {controller_id} triggers - L2: {l2_value:.2f}, R2: {r2_value:.2f}")
            except Exception as e:
                print(f"DEBUG: Error getting joystick trigger values: {e}")
                l2_value = 0.0
                r2_value = 0.0

        # Handle mode switching
        new_mode = self.mode_switcher.handle_trigger_input(
            controller_id, l2_value, r2_value, current_time)

        if new_mode:
            print(f"DEBUG: Controller {controller_id} switched to mode: {new_mode.value}")

            # Track controller mode change for undo/redo
            if not getattr(self, '_applying_undo_redo', False):
                if hasattr(self, 'controller_position_operation_tracker'):
                    # Get the old mode before switching
                    old_mode = self.mode_switcher.get_controller_mode(controller_id)
                    if old_mode:
                        self.controller_position_operation_tracker.add_controller_mode_change(
                            controller_id, old_mode.value, new_mode.value
                        )

            self._update_controller_visual_indicator_for_mode(controller_id, new_mode)
        else:
            print(f"DEBUG: No mode switch for controller {controller_id} - L2: {l2_value:.2f}, R2: {r2_value:.2f}")

    def _update_controller_visual_indicator_for_mode(self, controller_id: int, new_mode) -> None:
        """Update visual indicator for controller's new mode.

        Args:
            controller_id: Controller ID
            new_mode: New mode (ControllerMode enum)
        """
        print(f"DEBUG: Updating visual indicator for controller {controller_id} to mode {new_mode.value} (selected controller)")

        # Import LocationType
        from glitchygames.tools.visual_collision_manager import LocationType

        # Get controller info
        controller_info = self.multi_controller_manager.get_controller_info(controller_id)
        if not controller_info:
            print(f"DEBUG: No controller info found for controller {controller_id}")
            return

        # Get location type for new mode
        location_type = self.mode_switcher.get_controller_location_type(controller_id)
        if not location_type:
            print(f"DEBUG: No location type found for controller {controller_id}")
            return

        print(f"DEBUG: Location type for controller {controller_id}: {location_type}")

        # Get current position for the new mode
        position_data = self.mode_switcher.get_controller_position(controller_id)
        if position_data and position_data.is_valid:
            position = position_data.position
            print(f"DEBUG: Using saved position for controller {controller_id}: {position}")
        else:
            # Default position based on mode
            if new_mode.value == "canvas":
                position = (0, 0)  # Start at top-left of canvas
            elif new_mode.value in ["r_slider", "g_slider", "b_slider"]:
                position = (0, 0)  # Start at top of slider
            else:  # film_strip
                position = (100, 100)  # Default position
            print(f"DEBUG: Using default position for controller {controller_id}: {position}")

        # Update visual indicator
        if hasattr(self, 'visual_collision_manager'):
            print(f"DEBUG: Adding new indicator for controller {controller_id} at {position} with location type {location_type}")
            # Remove any existing indicator for this controller first
            self.visual_collision_manager.remove_controller_indicator(controller_id)
            # Add new indicator for the new mode
            self.visual_collision_manager.add_controller_indicator(
                controller_id, controller_info.instance_id,
                controller_info.color, position, location_type)

            print(f"DEBUG: Updated visual indicator for controller {controller_id} to {new_mode.value} mode at {position}")

            # Mark the appropriate area as dirty to trigger redraw
            print(f"DEBUG: Checking location_type {location_type} for dirty marking")
            print(f"DEBUG: LocationType.CANVAS = {LocationType.CANVAS}")
            print(f"DEBUG: location_type == LocationType.CANVAS: {location_type == LocationType.CANVAS}")
            if location_type == LocationType.CANVAS:
                print(f"DEBUG: Canvas check - hasattr(self, 'canvas'): {hasattr(self, 'canvas')}")
                if hasattr(self, 'canvas'):
                    # Force a complete redraw to update visual indicators
                    self.canvas.force_redraw()
                    print(f"DEBUG: Forced canvas redraw for controller {controller_id}")
                else:
                    print(f"DEBUG: No canvas object found for controller {controller_id}")
            elif location_type == LocationType.SLIDER:
                # Mark all sliders as dirty
                if hasattr(self, 'red_slider'):
                    self.red_slider.text_sprite.dirty = 2
                if hasattr(self, 'green_slider'):
                    self.green_slider.text_sprite.dirty = 2
                if hasattr(self, 'blue_slider'):
                    self.blue_slider.text_sprite.dirty = 2
                # Mark the main scene as dirty to trigger proper redraw
                self.dirty = 1
                print(f"DEBUG: Marked sliders and scene as dirty for controller {controller_id}")
            elif location_type == LocationType.FILM_STRIP:
                # Mark film strips as dirty
                if hasattr(self, 'film_strips'):
                    for strip_widget in self.film_strips.values():
                        strip_widget.mark_dirty()
                print(f"DEBUG: Marked film strips as dirty for controller {controller_id}")

            # Also mark film strips as dirty to ensure old triangles are removed
            # This is needed because film strips use controller_selections, not VisualCollisionManager
            if hasattr(self, 'film_strips'):
                for strip_widget in self.film_strips.values():
                    strip_widget.mark_dirty()
                print(f"DEBUG: Marked film strips as dirty to remove old indicators")

            # Also force canvas redraw to ensure old canvas indicators are removed
            # This is needed because canvas visual indicators are drawn on the canvas surface
            if hasattr(self, 'canvas'):
                self.canvas.force_redraw()
                print(f"DEBUG: Forced canvas redraw to remove old indicators")

        else:
            print(f"DEBUG: No visual_collision_manager found")

    def _render_visual_indicators(self) -> None:
        """Render visual indicators for multi-controller system."""
        # Initialize controller selections if needed
        if not hasattr(self, 'controller_selections'):
            self.controller_selections = {}

        # Initialize mode switcher if needed
        if not hasattr(self, 'mode_switcher'):
            from glitchygames.tools.controller_mode_system import ModeSwitcher
            self.mode_switcher = ModeSwitcher()

        # Initialize multi-controller manager if needed
        if not hasattr(self, 'multi_controller_manager'):
            from glitchygames.tools.multi_controller_manager import MultiControllerManager
            self.multi_controller_manager = MultiControllerManager()

        # Scan for new controllers
        if hasattr(self, 'multi_controller_manager'):
            self.multi_controller_manager.scan_for_controllers()

        # Register any new controllers
        self._register_new_controllers()

        # Initialize slider indicators dictionary if needed
        if not hasattr(self, 'slider_indicators'):
            self.slider_indicators = {}

        # Get the screen surface
        screen = pygame.display.get_surface()
        if not screen:
            return

        # Update all slider indicators with collision avoidance
        self._update_all_slider_indicators()

        # Update film strip controller selections
        self._update_film_strip_controller_selections()

        # Update canvas indicators
        self._update_canvas_indicators()

    def _create_slider_indicator_sprite(self, controller_id: int, color: tuple, slider_rect: pygame.Rect) -> BitmappySprite:
        """Create a proper Bitmappy sprite for slider indicator."""
        # Create a circular indicator sprite
        indicator_size = 16
        center_x = slider_rect.x + slider_rect.width // 2
        center_y = slider_rect.y + slider_rect.height // 2

        # Create the sprite
        indicator = BitmappySprite(
            name=f"SliderIndicator_{controller_id}",
            x=center_x - indicator_size // 2,
            y=center_y - indicator_size // 2,
            width=indicator_size,
            height=indicator_size,
            groups=self.all_sprites,
        )

        # Make the background transparent
        indicator.image.set_colorkey((0, 0, 0))  # Make black transparent
        indicator.image.fill((0, 0, 0))  # Fill with black first

        # Draw the indicator on the sprite surface
        pygame.draw.circle(indicator.image, color, (indicator_size // 2, indicator_size // 2), 8)
        pygame.draw.circle(indicator.image, (255, 255, 255), (indicator_size // 2, indicator_size // 2), 8, 2)

        return indicator

    def _update_slider_indicator(self, controller_id: int, color: tuple) -> None:
        """Update or create slider indicator for a controller."""
        # Remove any existing indicator for this controller
        self._remove_slider_indicator(controller_id)

        # Get the controller's current mode to determine which slider
        if hasattr(self, 'mode_switcher'):
            controller_mode = self.mode_switcher.get_controller_mode(controller_id)

            # Create indicator on the appropriate slider based on mode
            if controller_mode and controller_mode.value == "r_slider" and hasattr(self, 'red_slider'):
                indicator = self._create_slider_indicator_sprite(controller_id, color, self.red_slider.rect)
                self.slider_indicators[controller_id] = indicator

            elif controller_mode and controller_mode.value == "g_slider" and hasattr(self, 'green_slider'):
                indicator = self._create_slider_indicator_sprite(controller_id, color, self.green_slider.rect)
                self.slider_indicators[controller_id] = indicator

            elif controller_mode and controller_mode.value == "b_slider" and hasattr(self, 'blue_slider'):
                indicator = self._create_slider_indicator_sprite(controller_id, color, self.blue_slider.rect)
                self.slider_indicators[controller_id] = indicator

    def _update_all_slider_indicators(self) -> None:
        """Update all slider indicators with collision avoidance."""
        # Clear all existing slider indicators
        for controller_id in list(self.slider_indicators.keys()):
            self._remove_slider_indicator(controller_id)

        # Group controllers by slider
        slider_groups = {
            'r_slider': [],
            'g_slider': [],
            'b_slider': []
        }

        # Collect all active controllers in slider modes
        for controller_id, controller_selection in self.controller_selections.items():
            # Check if controller is active in controller_selections
            if controller_selection.is_active():
                if hasattr(self, 'mode_switcher'):
                    controller_mode = self.mode_switcher.get_controller_mode(controller_id)
                    if controller_mode and controller_mode.value in slider_groups:
                        # Get controller color
                        controller_info = None
                        if hasattr(self, "multi_controller_manager"):
                            for instance_id, info in self.multi_controller_manager.controllers.items():
                                if info.controller_id == controller_id:
                                    controller_info = info
                                    break

                        if controller_info:
                            slider_groups[controller_mode.value].append({
                                'controller_id': controller_id,
                                'color': controller_info.color
                            })

        # Create indicators for each slider with collision avoidance
        for slider_mode, controllers in slider_groups.items():
            if controllers and len(controllers) > 0:
                self._create_slider_indicators_with_collision_avoidance(slider_mode, controllers)

    def _create_slider_indicators_with_collision_avoidance(self, slider_mode: str, controllers: list) -> None:
        """Create slider indicators with collision avoidance for multiple controllers."""
        # Get the appropriate slider
        slider = None
        if slider_mode == "r_slider" and hasattr(self, 'red_slider'):
            slider = self.red_slider
        elif slider_mode == "g_slider" and hasattr(self, 'green_slider'):
            slider = self.green_slider
        elif slider_mode == "b_slider" and hasattr(self, 'blue_slider'):
            slider = self.blue_slider

        if not slider:
            return

        # Sort controllers by color priority (same as film strip)
        def get_color_priority(controller):
            color = controller['color']
            if color == (255, 0, 0):    # Red
                return 0
            elif color == (0, 255, 0):  # Green
                return 1
            elif color == (0, 0, 255):  # Blue
                return 2
            elif color == (255, 255, 0): # Yellow
                return 3
            else:
                return 999  # Unknown colors go last

        controllers.sort(key=get_color_priority)

        # Calculate positioning with collision avoidance
        indicator_size = 16
        indicator_spacing = 20  # Space between indicator centers

        # Calculate total width needed for all indicators
        total_width = (len(controllers) - 1) * indicator_spacing

        # Calculate starting position to center the group
        slider_rect = slider.rect
        start_x = slider_rect.centerx - (total_width // 2)
        center_y = slider_rect.centery

        # Create indicators with proper spacing
        current_x = start_x
        for controller in controllers:
            # Create indicator at calculated position
            indicator = BitmappySprite(
                name=f"SliderIndicator_{controller['controller_id']}",
                x=current_x - indicator_size // 2,
                y=center_y - indicator_size // 2,
                width=indicator_size,
                height=indicator_size,
                groups=self.all_sprites,
            )

            # Make the background transparent
            indicator.image.set_colorkey((0, 0, 0))
            indicator.image.fill((0, 0, 0))

            # Draw the indicator
            pygame.draw.circle(indicator.image, controller['color'], (indicator_size // 2, indicator_size // 2), 8)
            pygame.draw.circle(indicator.image, (255, 255, 255), (indicator_size // 2, indicator_size // 2), 8, 2)

            # Store the indicator
            self.slider_indicators[controller['controller_id']] = indicator

            # Move to next position
            current_x += indicator_spacing

    def _update_film_strip_controller_selections(self) -> None:
        """Update film strip controller selections for all animations."""
        # Initialize film strip controller selections if needed
        if not hasattr(self, 'film_strip_controller_selections'):
            self.film_strip_controller_selections = {}

        # Clear existing selections
        self.film_strip_controller_selections.clear()

        # Collect all active controllers in film strip mode
        if hasattr(self, 'controller_selections'):
            for controller_id, controller_selection in self.controller_selections.items():
                # Check if controller is active in controller_selections
                if controller_selection.is_active():
                    # Only include controllers in FILM_STRIP mode
                    controller_mode = None
                    if hasattr(self, 'mode_switcher'):
                        controller_mode = self.mode_switcher.get_controller_mode(controller_id)

                    if controller_mode and controller_mode.value == "film_strip":
                        animation, frame = controller_selection.get_selection()

                        # Get controller color
                        controller_info = None
                        if hasattr(self, "multi_controller_manager"):
                            for instance_id, info in self.multi_controller_manager.controllers.items():
                                if info.controller_id == controller_id:
                                    controller_info = info
                                    break

                        if controller_info and animation:
                            # Only include controllers that have been properly initialized (not default gray)
                            if controller_info.color != (128, 128, 128):
                                # Group by animation
                                if animation not in self.film_strip_controller_selections:
                                    self.film_strip_controller_selections[animation] = []

                                self.film_strip_controller_selections[animation].append({
                                    'controller_id': controller_id,
                                    'frame': frame,
                                    'color': controller_info.color
                                })

    def _update_canvas_indicators(self) -> None:
        """Update canvas indicators for controllers in canvas mode."""
        if not hasattr(self, 'canvas') or not self.canvas:
            return

        # Get all active controllers in canvas mode
        canvas_controllers = []
        for controller_id, controller_selection in self.controller_selections.items():
            # Check if controller is active in controller_selections
            if controller_selection.is_active():
                # Only include controllers in CANVAS mode
                controller_mode = None
                if hasattr(self, 'mode_switcher'):
                    controller_mode = self.mode_switcher.get_controller_mode(controller_id)

                if controller_mode and controller_mode.value == "canvas":
                    # Get controller color
                    controller_info = None
                    if hasattr(self, "multi_controller_manager"):
                        for instance_id, info in self.multi_controller_manager.controllers.items():
                            if info.controller_id == controller_id:
                                controller_info = info
                                break

                    if controller_info:
                        # Get controller position
                        position = self.mode_switcher.get_controller_position(controller_id)
                        if position and position.is_valid:
                            canvas_controllers.append({
                                'controller_id': controller_id,
                                'position': position.position,
                                'color': controller_info.color
                            })

        # Update canvas with controller indicators
        if canvas_controllers:
            # Store controller data for canvas to use
            self.canvas_controller_indicators = canvas_controllers
            # Pass controller data to canvas for drawing
            if hasattr(self.canvas, 'canvas_interface'):
                self.canvas.canvas_interface.controller_indicators = canvas_controllers
            # Force canvas redraw to show indicators
            self.canvas.force_redraw()
        else:
            # Clear controller indicators if no controllers in canvas mode
            self.canvas_controller_indicators = []
            if hasattr(self.canvas, 'canvas_interface'):
                self.canvas.canvas_interface.controller_indicators = []

    def _register_new_controllers(self) -> None:
        """Register any new controllers that have been detected."""
        if not hasattr(self, 'multi_controller_manager'):
            return

        # Check for any controllers that aren't registered yet
        for instance_id, controller_info in self.multi_controller_manager.controllers.items():
            controller_id = controller_info.controller_id
            if controller_id not in self.controller_selections:
                # Register new controller
                from glitchygames.tools.controller_selection import ControllerSelection
                self.controller_selections[controller_id] = ControllerSelection(controller_id, instance_id)

                # Activate the controller
                self.controller_selections[controller_id].activate()

                # Register with mode switcher
                if hasattr(self, 'mode_switcher'):
                    from glitchygames.tools.controller_mode_system import ControllerMode
                    self.mode_switcher.register_controller(controller_id, ControllerMode.FILM_STRIP)

                print(f"DEBUG BitmapEditorScene: Registered and activated new controller {controller_id} (instance {instance_id})")

    def _remove_slider_indicator(self, controller_id: int) -> None:
        """Remove slider indicator for a controller."""
        if hasattr(self, 'slider_indicators') and controller_id in self.slider_indicators:
            indicator = self.slider_indicators[controller_id]
            # Remove from sprite groups
            if hasattr(self, 'all_sprites'):
                self.all_sprites.remove(indicator)
            # Remove from tracking
            del self.slider_indicators[controller_id]

    def render(self, screen: pygame.Surface) -> None:
        """Render the scene with visual indicators."""
        # Call the parent render method first
        super().render(screen)


        # Then render visual indicators on top
        self._render_visual_indicators()

    def _draw_visual_indicator(self, screen, indicator) -> None:
        """Draw a single visual indicator on the screen."""
        if not indicator.is_visible:
            print(f"DEBUG: Indicator for controller {indicator.controller_id} is not visible")
            return

        # Calculate final position with offset
        final_x = indicator.position[0] + indicator.offset[0]
        final_y = indicator.position[1] + indicator.offset[1]

        print(f"DEBUG: Drawing indicator for controller {indicator.controller_id} at ({final_x}, {final_y}) with shape {indicator.shape.value}")

        # Set transparency
        color = (*indicator.color, int(255 * indicator.transparency))

        # Draw based on shape
        if indicator.shape.value == "triangle":
            # Draw triangle (film strip indicator)
            points = [
                (final_x, final_y - indicator.size // 2),
                (final_x - indicator.size // 2, final_y + indicator.size // 2),
                (final_x + indicator.size // 2, final_y + indicator.size // 2)
            ]
            pygame.draw.polygon(screen, indicator.color, points)
        elif indicator.shape.value == "square":
            # Draw square (canvas indicator)
            rect = pygame.Rect(final_x - indicator.size // 2, final_y - indicator.size // 2,
                             indicator.size, indicator.size)
            pygame.draw.rect(screen, indicator.color, rect)
        elif indicator.shape.value == "circle":
            # Draw circle (slider indicator)
            pygame.draw.circle(screen, indicator.color, (final_x, final_y), indicator.size // 2)

    def _select_current_frame(self) -> None:
        """Select the currently highlighted frame."""
        if not hasattr(self, 'selected_animation') or not hasattr(self, 'selected_frame'):
            return

        # Find the active film strip
        if hasattr(self, 'film_strips') and self.film_strips:
            for strip_name, strip_widget in self.film_strips.items():
                if strip_name == self.selected_animation:
                    # Trigger frame selection
                    self._on_film_strip_frame_selected(strip_widget, self.selected_animation, self.selected_frame)
                    break

    def _controller_cancel(self) -> None:
        """Handle controller cancel action."""
        # For now, just log the action
        LOG.debug("Controller cancel action")

    def _controller_select_current_frame(self) -> None:
        """DEPRECATED: Old single-controller system - now disabled in favor of multi-controller system."""
        print("DEBUG: _controller_select_current_frame called but DISABLED - use multi-controller system instead")
        # OLD SYSTEM DISABLED - Use multi-controller system instead
        return

    def _controller_previous_frame(self) -> None:
        """DEPRECATED: Old single-controller system - now disabled in favor of multi-controller system."""
        print("DEBUG: _controller_previous_frame called but DISABLED - use multi-controller system instead")
        # OLD SYSTEM DISABLED - Use multi-controller system instead
        return

    def _controller_next_frame(self) -> None:
        """DEPRECATED: Old single-controller system - now disabled in favor of multi-controller system."""
        print("DEBUG: _controller_next_frame called but DISABLED - use multi-controller system instead")
        # OLD SYSTEM DISABLED - Use multi-controller system instead
        return

    def _controller_previous_animation(self) -> None:
        """DEPRECATED: Old single-controller system - now disabled in favor of multi-controller system."""
        print("DEBUG: _controller_previous_animation called but DISABLED - use multi-controller system instead")
        # OLD SYSTEM DISABLED - Use multi-controller system instead
        return

    def _controller_next_animation(self) -> None:
        """DEPRECATED: Old single-controller system - now disabled in favor of multi-controller system."""
        print("DEBUG: _controller_next_animation called but DISABLED - use multi-controller system instead")
        # OLD SYSTEM DISABLED - Use multi-controller system instead
        return

    def _scroll_to_controller_animation(self, animation_name: str) -> None:
        """Scroll film strips to show the specified animation for multi-controller system."""
        if not hasattr(self, "film_strips") or not self.film_strips:
            return

        # Get all animation names in order
        animation_names = list(self.film_strips.keys())
        if animation_name not in animation_names:
            return

        # Find the index of the target animation
        target_index = animation_names.index(animation_name)

        # Calculate the scroll offset needed to show this animation
        # We want to show the target animation in the visible area
        if target_index < self.film_strip_scroll_offset:
            # Target animation is above the visible area, scroll up
            self.film_strip_scroll_offset = target_index
        elif target_index >= self.film_strip_scroll_offset + self.max_visible_strips:
            # Target animation is below the visible area, scroll down
            self.film_strip_scroll_offset = target_index - self.max_visible_strips + 1

        # Update visibility and scroll arrows
        self._update_film_strip_visibility()
        self._update_scroll_arrows()

        print(f"DEBUG: Scrolled to show animation '{animation_name}' at index {target_index}, scroll offset: {self.film_strip_scroll_offset}")

    def _validate_controller_selection(self) -> None:
        """DEPRECATED: Old single-controller system - now disabled in favor of multi-controller system."""
        print("DEBUG: _validate_controller_selection called but DISABLED - use multi-controller system instead")
        # OLD SYSTEM DISABLED - Use multi-controller system instead
        return

    def _initialize_controller_selection(self) -> None:
        """DEPRECATED: Old single-controller system - now disabled in favor of multi-controller system."""
        print("DEBUG: _initialize_controller_selection called but DISABLED - use multi-controller system instead")
        # OLD SYSTEM DISABLED - Use multi-controller system instead
        return

    def _controller_select_frame(self, animation: str, frame: int) -> None:
        """DEPRECATED: Old single-controller system - now disabled in favor of multi-controller system.

        This method is kept for compatibility but should not be used.
        Use the new multi-controller system instead.
        """
        print(f"DEBUG: _controller_select_frame called but DISABLED - use multi-controller system instead")
        # OLD SYSTEM DISABLED - Use multi-controller system instead
        return

    # Multi-Controller System Methods
    def _multi_controller_activate(self, controller_id: int) -> None:
        """Activate a controller for navigation.

        Args:
            controller_id: Controller ID to activate
        """
        if controller_id not in self.controller_selections:
            print(f"DEBUG: Controller {controller_id} not found for activation")
            return

        controller_selection = self.controller_selections[controller_id]
        controller_selection.activate()

        # Assign color based on activation order using singleton
        from .multi_controller_manager import MultiControllerManager
        manager = MultiControllerManager.get_instance()
        print(f"DEBUG: About to assign color to controller {controller_id}")
        print(f"DEBUG: Available controllers in manager: {list(manager.controllers.keys())}")
        for instance_id, info in manager.controllers.items():
            print(f"DEBUG: Controller instance_id={instance_id}, controller_id={info.controller_id}, color={info.color}")
        manager.assign_color_to_controller(controller_id)

        # Initialize to first available animation if not set
        if not controller_selection.get_animation():
            if hasattr(self, 'film_strips') and self.film_strips:
                first_animation = list(self.film_strips.keys())[0]
                controller_selection.set_selection(first_animation, 0)
                print(f"DEBUG: Controller {controller_id} initialized to '{first_animation}', frame 0")

        # Update visual collision manager
        self._update_controller_visual_indicator(controller_id)

        # Mark all film strips as dirty to update colors
        if hasattr(self, 'film_strips') and self.film_strips:
            for film_strip in self.film_strips.values():
                film_strip.mark_dirty()
        if hasattr(self, 'film_strip_sprites') and self.film_strip_sprites:
            for film_strip_sprite in self.film_strip_sprites.values():
                film_strip_sprite.dirty = 1

        print(f"DEBUG: Controller {controller_id} activated")

    def _multi_controller_previous_frame(self, controller_id: int) -> None:
        """Move to previous frame for a controller.

        Args:
            controller_id: Controller ID
        """
        if controller_id not in self.controller_selections:
            print(f"DEBUG: Controller {controller_id} not found for previous frame")
            return

        controller_selection = self.controller_selections[controller_id]
        animation, frame = controller_selection.get_selection()

        if not animation or animation not in self.film_strips:
            print(f"DEBUG: Controller {controller_id} has no valid animation for previous frame")
            return

        strip_widget = self.film_strips[animation]
        if hasattr(strip_widget, 'animated_sprite') and strip_widget.animated_sprite:
            frame_count = strip_widget.animated_sprite.current_animation_frame_count
            new_frame = (frame - 1) % frame_count
            controller_selection.set_frame(new_frame)

            # Scroll the film strip to show the selected frame if it's off-screen
            if hasattr(strip_widget, 'update_scroll_for_frame'):
                strip_widget.update_scroll_for_frame(new_frame)
                print(f"DEBUG: Controller {controller_id} previous frame: Scrolled film strip to show frame {new_frame}")

            # Update visual indicator
            self._update_controller_visual_indicator(controller_id)

            print(f"DEBUG: Controller {controller_id} previous frame: {frame} -> {new_frame}")

    def _multi_controller_next_frame(self, controller_id: int) -> None:
        """Move to next frame for a controller.

        Args:
            controller_id: Controller ID
        """
        if controller_id not in self.controller_selections:
            print(f"DEBUG: Controller {controller_id} not found for next frame")
            return

        controller_selection = self.controller_selections[controller_id]
        animation, frame = controller_selection.get_selection()

        if not animation or animation not in self.film_strips:
            print(f"DEBUG: Controller {controller_id} has no valid animation for next frame")
            return

        strip_widget = self.film_strips[animation]
        if hasattr(strip_widget, 'animated_sprite') and strip_widget.animated_sprite:
            frame_count = strip_widget.animated_sprite.current_animation_frame_count
            new_frame = (frame + 1) % frame_count
            controller_selection.set_frame(new_frame)

            # Scroll the film strip to show the selected frame if it's off-screen
            if hasattr(strip_widget, 'update_scroll_for_frame'):
                strip_widget.update_scroll_for_frame(new_frame)
                print(f"DEBUG: Controller {controller_id} next frame: Scrolled film strip to show frame {new_frame}")

            # Update visual indicator
            self._update_controller_visual_indicator(controller_id)

            print(f"DEBUG: Controller {controller_id} next frame: {frame} -> {new_frame}")

    def _multi_controller_previous_animation(self, controller_id: int) -> None:
        """Move to previous animation for a controller.

        Args:
            controller_id: Controller ID
        """
        if controller_id not in self.controller_selections:
            print(f"DEBUG: Controller {controller_id} not found for previous animation")
            return

        controller_selection = self.controller_selections[controller_id]
        current_animation, current_frame = controller_selection.get_selection()

        if not hasattr(self, 'film_strips') or not self.film_strips:
            print(f"DEBUG: No film strips available for controller {controller_id} previous animation")
            return

        # Get all animation names in order
        animation_names = list(self.film_strips.keys())
        if not animation_names:
            print(f"DEBUG: No animations available for controller {controller_id} previous animation")
            return

        # Find current animation index
        try:
            current_index = animation_names.index(current_animation)
        except ValueError:
            current_index = 0

        # Move to previous animation
        new_index = (current_index - 1) % len(animation_names)
        new_animation = animation_names[new_index]

        # Try to preserve the frame index from the previous animation
        target_frame = controller_selection.preserve_frame_for_animation(
            new_animation,
            self.film_strips[new_animation].animated_sprite.current_animation_frame_count
        )

        print(f"DEBUG: Controller {controller_id} previous animation: Moving to '{new_animation}', frame {target_frame}")
        controller_selection.set_selection(new_animation, target_frame)

        # Scroll the film strip view to show the selected animation if it's off-screen
        self._scroll_to_controller_animation(new_animation)

        # Update visual indicator
        self._update_controller_visual_indicator(controller_id)

    def _multi_controller_next_animation(self, controller_id: int) -> None:
        """Move to next animation for a controller.

        Args:
            controller_id: Controller ID
        """
        if controller_id not in self.controller_selections:
            print(f"DEBUG: Controller {controller_id} not found for next animation")
            return

        controller_selection = self.controller_selections[controller_id]
        current_animation, current_frame = controller_selection.get_selection()

        if not hasattr(self, 'film_strips') or not self.film_strips:
            print(f"DEBUG: No film strips available for controller {controller_id} next animation")
            return

        # Get all animation names in order
        animation_names = list(self.film_strips.keys())
        if not animation_names:
            print(f"DEBUG: No animations available for controller {controller_id} next animation")
            return

        # Find current animation index
        try:
            current_index = animation_names.index(current_animation)
        except ValueError:
            current_index = 0

        # Move to next animation
        new_index = (current_index + 1) % len(animation_names)
        new_animation = animation_names[new_index]

        # Try to preserve the frame index from the previous animation
        target_frame = controller_selection.preserve_frame_for_animation(
            new_animation,
            self.film_strips[new_animation].animated_sprite.current_animation_frame_count
        )

        print(f"DEBUG: Controller {controller_id} next animation: Moving to '{new_animation}', frame {target_frame}")
        controller_selection.set_selection(new_animation, target_frame)

        # Scroll the film strip view to show the selected animation if it's off-screen
        self._scroll_to_controller_animation(new_animation)

        # Update visual indicator
        self._update_controller_visual_indicator(controller_id)

    def _update_controller_visual_indicator(self, controller_id: int) -> None:
        """Update visual indicator for a controller.

        Args:
            controller_id: Controller ID
        """
        if controller_id not in self.controller_selections:
            return

        controller_selection = self.controller_selections[controller_id]
        animation, frame = controller_selection.get_selection()

        if not animation or animation not in self.film_strips:
            return

        # Get controller color
        controller_info = None
        for instance_id, info in self.multi_controller_manager.controllers.items():
            if info.controller_id == controller_id:
                controller_info = info
                break

        if not controller_info:
            return

        # Calculate position (this would need to be implemented based on your UI layout)
        # For now, we'll use a placeholder position
        position = (100 + controller_id * 50, 100)

        # Add or update visual indicator
        if controller_id not in self.visual_collision_manager.indicators:
            self.visual_collision_manager.add_controller_indicator(
                controller_id,
                controller_info.instance_id,
                controller_info.color,
                position
            )
        else:
            self.visual_collision_manager.update_controller_position(controller_id, position)

    def _multi_controller_toggle_onion_skinning(self, controller_id: int) -> None:
        """Toggle onion skinning for the controller's selected frame.

        Args:
            controller_id: Controller ID to toggle onion skinning for
        """
        if controller_id not in self.controller_selections:
            print(f"DEBUG: Controller {controller_id} not found for onion skinning toggle")
            return

        controller_selection = self.controller_selections[controller_id]
        animation, frame = controller_selection.get_selection()

        if not animation or frame is None:
            print(f"DEBUG: Controller {controller_id} has no valid selection for onion skinning toggle")
            return

        # Get onion skinning manager
        from .onion_skinning import get_onion_skinning_manager
        onion_manager = get_onion_skinning_manager()

        # Toggle onion skinning for this frame
        is_enabled = onion_manager.toggle_frame_onion_skinning(animation, frame)
        status = "enabled" if is_enabled else "disabled"

        print(f"DEBUG: Controller {controller_id}: Onion skinning {status} for {animation}[{frame}]")
        LOG.debug(f"Controller {controller_id}: Onion skinning {status} for {animation}[{frame}]")

        # Force redraw of the canvas to show the change
        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.force_redraw()

    def _multi_controller_toggle_selected_frame_visibility(self, controller_id: int) -> None:
        """Toggle visibility of the selected frame on the canvas for comparison.

        Args:
            controller_id: Controller ID (not used but kept for consistency)
        """
        # Toggle the selected frame visibility
        self.selected_frame_visible = not self.selected_frame_visible
        status = "visible" if self.selected_frame_visible else "hidden"

        print(f"DEBUG: Controller {controller_id}: Selected frame {status} on canvas")
        LOG.debug(f"Controller {controller_id}: Selected frame {status} on canvas")

        # Force redraw of the canvas to show the change
        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.force_redraw()

    def _multi_controller_select_current_frame(self, controller_id: int) -> None:
        """Select the current frame that the controller is pointing to.

        Args:
            controller_id: The ID of the controller.
        """
        print(f"DEBUG: _multi_controller_select_current_frame called for controller {controller_id}")

        if controller_id not in self.controller_selections:
            print(f"DEBUG: Controller {controller_id} not found in selections")
            return

        controller_selection = self.controller_selections[controller_id]
        if not controller_selection.is_active():
            print(f"DEBUG: Controller {controller_id} is not active")
            return

        animation, frame = controller_selection.get_selection()
        print(f"DEBUG: Controller {controller_id} selecting frame {frame} in animation '{animation}'")
        print(f"DEBUG: Current global selection before update: animation='{getattr(self, 'selected_animation', 'None')}', frame={getattr(self, 'selected_frame', 'None')}")

        # Update the canvas to show this frame
        if animation in self.film_strips:
            strip_widget = self.film_strips[animation]
            if hasattr(strip_widget, 'animated_sprite') and strip_widget.animated_sprite:
                if animation in strip_widget.animated_sprite._animations:
                    if frame < len(strip_widget.animated_sprite._animations[animation]):
                        # Update the canvas to show this frame using the same mechanism as keyboard selection
                        print(f"DEBUG: Updating canvas to show animation '{animation}', frame {frame}")
                        self.canvas.show_frame(animation, frame)

                        # Store global selection state (same as keyboard selection)
                        print(f"DEBUG: Setting global selection state to animation '{animation}', frame {frame}")
                        self.selected_animation = animation
                        self.selected_frame = frame

                        # Update film strip selection state (same as keyboard selection)
                        print(f"DEBUG: Calling _update_film_strip_selection_state()")
                        self._update_film_strip_selection_state()

                        print(f"DEBUG: Controller selection updated keyboard selection to animation '{animation}', frame {frame}")
                        print(f"DEBUG: Final global selection: animation='{self.selected_animation}', frame={self.selected_frame}")
                    else:
                        print(f"DEBUG: Frame {frame} is out of bounds for animation '{animation}' (max: {len(strip_widget.animated_sprite._animations[animation])-1})")
                else:
                    print(f"DEBUG: Animation '{animation}' not found in strip_widget.animated_sprite._animations")
            else:
                print(f"DEBUG: strip_widget has no animated_sprite or animated_sprite is None")
        else:
            print(f"DEBUG: Animation '{animation}' not found in film_strips")

    def _multi_controller_cancel(self, controller_id: int) -> None:
        """Cancel controller selection.

        Args:
            controller_id: The ID of the controller.
        """
        if controller_id not in self.controller_selections:
            return

        controller_selection = self.controller_selections[controller_id]
        controller_selection.deactivate()
        print(f"DEBUG: Controller {controller_id} cancelled")

    def _reinitialize_multi_controller_system(self, preserved_controller_selections=None) -> None:
        """Reinitialize the multi-controller system when film strips are reconstructed.

        This ensures that existing controller selections are preserved and properly
        initialized when film strips are recreated (e.g., when loading an animation file).

        Args:
            preserved_controller_selections: Optional dict of preserved controller selections
                from before film strip reconstruction.
        """
        print("DEBUG: Reinitializing multi-controller system")
        print(f"DEBUG: Current controller_selections: {list(self.controller_selections.keys())}")
        print(f"DEBUG: Current film_strips: {list(self.film_strips.keys()) if hasattr(self, 'film_strips') and self.film_strips else 'None'}")

        # Check if controller_selections is empty (scene was recreated)
        if not self.controller_selections:
            print("DEBUG: controller_selections is empty - scene was likely recreated")
            # If scene was recreated, we can't preserve controller selections
            # Controllers will need to be reactivated manually
            return

        # Use preserved controller selections if provided, otherwise use current ones
        if preserved_controller_selections is not None:
            active_controllers = preserved_controller_selections
            print(f"DEBUG: Using preserved controller selections: {active_controllers}")
        else:
            # Store the active state of controllers before reconstruction
            active_controllers = {}
            print(f"DEBUG: Checking {len(self.controller_selections)} existing controller selections")
            for controller_id, controller_selection in self.controller_selections.items():
                is_active = controller_selection.is_active()
                print(f"DEBUG: Controller {controller_id} is_active: {is_active}")
                if is_active:
                    animation, frame = controller_selection.get_selection()
                    active_controllers[controller_id] = (animation, frame)
                    print(f"DEBUG: Storing active controller {controller_id} with animation '{animation}', frame {frame}")

        print(f"DEBUG: Found {len(active_controllers)} active controllers to preserve")

        # Scan for controllers and update manager
        self.multi_controller_manager.scan_for_controllers()
        print(f"DEBUG: Found {len(self.multi_controller_manager.controllers)} controllers in manager")

        # Reinitialize controller selections for existing controllers
        for instance_id, controller_info in self.multi_controller_manager.controllers.items():
            print(f"DEBUG: Processing controller {instance_id}, status: {controller_info.status.value}")
            # Accept controllers with any status (connected, assigned, or active)
            if controller_info.status.value in ["connected", "assigned", "active"]:
                controller_id = controller_info.controller_id

                # Check if controller selection already exists
                if controller_id not in self.controller_selections:
                    # Create new controller selection (but don't activate it)
                    self.controller_selections[controller_id] = ControllerSelection(controller_id, instance_id)
                    print(f"DEBUG: Created new controller selection for controller {controller_id} (inactive)")
                else:
                    # Update existing controller selection
                    controller_selection = self.controller_selections[controller_id]
                    controller_selection.update_activity()
                    print(f"DEBUG: Updated existing controller selection for controller {controller_id}")

                # Get the controller_selection reference for activation
                controller_selection = self.controller_selections[controller_id]

                # Restore active state if controller was active before reconstruction
                if controller_id in active_controllers:
                    if self.film_strips:
                        # Always reset to first strip and frame 0 when loading new files
                        # since animation names and structure will be different
                        first_animation = list(self.film_strips.keys())[0]
                        controller_selection.set_selection(first_animation, 0)
                        controller_selection.activate()
                        print(f"DEBUG: Reset active controller {controller_id} to first animation '{first_animation}', frame 0 (ignoring previous selection)")
                        print(f"DEBUG: Controller {controller_id} is now active: {controller_selection.is_active()}")
                        print(f"DEBUG: Controller {controller_id} selection: {controller_selection.get_selection()}")
                        print(f"DEBUG: Available film strips: {list(self.film_strips.keys())}")
                    else:
                        print(f"DEBUG: No film strips available for active controller {controller_id}")
                else:
                    print(f"DEBUG: Controller {controller_id} was not active before reconstruction, keeping it inactive")

        print(f"DEBUG: Multi-controller system reinitialized with {len(self.controller_selections)} controller selections")


def main() -> None:
    """Run the main function.

    Args:
        None

    Returns:
        None

    Raises:
        None

    """

    LOG.setLevel(logging.DEBUG)

    # Set up signal handling to prevent multiprocessing issues on macOS
    def signal_handler(signum):
        """Handle shutdown signals gracefully."""
        LOG.info(f"Received signal {signum}, shutting down gracefully...")
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    load_ai_training_data()

    # Set multiprocessing start method to avoid macOS issues
    with contextlib.suppress(RuntimeError):
        multiprocessing.set_start_method("spawn", force=True)

    icon_path = Path(__file__).parent / "resources" / "bitmappy.png"

    GameEngine(game=BitmapEditorScene, icon=icon_path).start()


if __name__ == "__main__":
    main()
