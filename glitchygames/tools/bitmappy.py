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
from typing import TYPE_CHECKING, ClassVar, Self

import pygame
import toml

# Try to import aisuite, but don't fail if it's not available
try:
    import aisuite as ai
except ImportError:
    ai = None

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
    [colors] section with colors.0 through colors.7
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
    - CRITICAL: Use triple-quoted block strings for multi-line pixel data
    - EFFICIENCY: Only define colors that appear in the pixel data (e.g., if pixels only use
      "0", only define [colors.0])
"""

LOG = logging.getLogger("game.tools.bitmappy")

# Set up logging
# if not LOG.handlers:
#     handler = logging.StreamHandler()
#     formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
#     handler.setFormatter(formatter)
#     LOG.addHandler(handler)

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
                    with config_file.open(encoding="utf-8") as f:
                        config_data = toml.load(f)

                    # Extract sprite data from TOML structure
                    sprite_data = {
                        "name": config_data.get("sprite", {}).get("name", "Unknown"),
                        "format": AI_TRAINING_FORMAT,
                        "sprite_type": "animated" if "animation" in config_data else "static",
                    }

                    # For static sprites, extract pixel data and colors
                    if "sprite" in config_data:
                        sprite_data["pixels"] = config_data["sprite"].get("pixels", "")
                        sprite_data["colors"] = config_data.get("colors", {})

                    # For animated sprites, extract animation data
                    if "animation" in config_data:
                        sprite_data["animations"] = config_data["animation"]


                AI_TRAINING_DATA.append(sprite_data)
                LOG.info(f"Successfully loaded sprite config: {config_file.name}")

            except (FileNotFoundError, PermissionError, ValueError, KeyError) as e:
                LOG.warning(f"Error loading sprite config {config_file}: {e}")
    else:
        LOG.warning(f"Sprite config directory not found: {SPRITE_CONFIG_DIR}")

    LOG.info(f"Total AI training data loaded: {len(AI_TRAINING_DATA)} sprites")
    LOG.debug(f"AI training data: {AI_TRAINING_DATA}")


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
        self.pixel_color = (0, 0, 0)
        self.x = x
        self.y = y

        self.rect = pygame.draw.rect(
            self.image, self.color, (self.x, self.y, self.width, self.height), self.border_thickness
        )

    @property
    def pixel_color(self: Self) -> tuple[int, int, int]:
        """Get the pixel color.

        Args:
            None

        Returns:
            tuple[int, int, int]: The pixel color.

        Raises:
            None

        """
        return self._pixel_color

    @pixel_color.setter
    def pixel_color(self: Self, new_pixel_color: tuple[int, int, int]) -> None:
        """Set the pixel color.

        Args:
            new_pixel_color (tuple): The new pixel color.

        Returns:
            None

        Raises:
            None

        """
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
    log.info("AI client initialized successfully")
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
        log.exception("Failed to query model capabilities")
        return {"max_tokens": None}


def _process_ai_request(request: AIRequest, client, log: logging.Logger) -> AIResponse:
    """Process a single AI request."""
    # Check if AI client is available
    if client is None:
        log.warning("AI client not available, returning empty response")
        return AIResponse(content="AI features not available")

    log.info("Making API call to AI service...")
    response = client.chat.completions.create(
        model=AI_MODEL, messages=request.messages, max_tokens=AI_MAX_TOKENS
    )

    log.info("AI response received from API")
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
                log.exception("Error processing AI request")
                if request:
                    response_queue.put((request.request_id, AIResponse(content=None, error=str(e))))
    except ImportError:
        log.exception("Failed to import aisuite")
        raise
    except (OSError, ValueError, KeyError, AttributeError):
        log.exception("Fatal error in AI worker process")
        raise


class FilmStripSprite(BitmappySprite):
    """Sprite wrapper for the film strip widget."""

    def __init__(self, film_strip_widget, x=0, y=0, width=800, height=100, groups=None):
        """Initialize the film strip sprite."""
        super().__init__(x=x, y=y, width=width, height=height, groups=groups)
        self.film_strip_widget = film_strip_widget
        self.name = "Film Strip"

        # Create initial surface
        self.image = pygame.Surface((width, height))
        self.rect = self.image.get_rect(x=x, y=y)

        # Force initial render
        self.dirty = 1

    def update(self):
        """Update the film strip sprite."""
        # Always redraw if dirty or if animations are running
        should_redraw = self.dirty

        # Check if animations are running and force redraw
        animations_running = (
            hasattr(self, "film_strip_widget")
            and hasattr(self.film_strip_widget, "animated_sprite")
            and self.film_strip_widget.animated_sprite
            and len(self.film_strip_widget.animated_sprite._animations) > 0
        )

        if animations_running:
            should_redraw = True

        if should_redraw:
            self.force_redraw()
            # Only reset dirty flag if animations are not running
            # This ensures continuous updates when animations are present
            if not animations_running:
                self.dirty = 0

    def force_redraw(self):
        """Force a redraw of the film strip."""
        # Clear the surface
        self.image.fill((40, 40, 40))  # Film background color

        # Render the film strip widget
        self.film_strip_widget.render(self.image)

    def on_left_mouse_button_down_event(self, event):
        """Handle mouse clicks on the film strip."""
        if self.rect.collidepoint(event.pos):
            # Convert screen coordinates to film strip coordinates
            film_x = event.pos[0] - self.rect.x
            film_y = event.pos[1] - self.rect.y

            # Handle click in the film strip widget
            clicked_frame = self.film_strip_widget.handle_click((film_x, film_y))

            if clicked_frame:
                animation, frame_idx = clicked_frame
                # Notify the canvas to change frame
                if hasattr(self, "parent_canvas") and self.parent_canvas:
                    self.parent_canvas.show_frame(animation, frame_idx)

    def set_parent_canvas(self, canvas):
        """Set the parent canvas for frame changes."""
        self.parent_canvas = canvas


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

        # Initialize canvas surface and UI components
        self._initialize_canvas_surface(x, y, width, height, groups)

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
        self.current_animation = (
            next(iter(animated_sprite._animations.keys()))
            if animated_sprite._animations
            else "idle"
        )
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
        # Initialize pixels with magenta as the transparent/background color
        self.pixels = [(255, 0, 255) for _ in range(self.pixels_across * self.pixels_tall)]
        self.dirty_pixels = [True] * len(self.pixels)
        self.background_color = (128, 128, 128)
        self.active_color = (0, 0, 0)
        self.border_thickness = 1

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

        # Create film strip widget - position to the right of the canvas
        film_strip_x = self.rect.right + 20  # 20px to the right of canvas
        film_strip_y = self.rect.y  # Same vertical position as canvas

        # Calculate required width for film strip (5.0 frames + spacing)
        required_width = int(5.0 * (64 + 2)) + 20  # 5.0 frames * (width + spacing) + padding
        film_strip_width = max(300, required_width)

        self.film_strip = FilmStripWidget(
            x=film_strip_x, y=film_strip_y, width=film_strip_width, height=100
        )
        self.film_strip.set_animated_sprite(self.animated_sprite)

        # Create film strip sprite for rendering (height will be updated dynamically)
        self.film_strip_sprite = FilmStripSprite(
            film_strip_widget=self.film_strip,
            x=film_strip_x,
            y=film_strip_y,
            width=film_strip_width,
            height=self.film_strip.rect.height,
            groups=groups,
        )

        # Connect the film strip to this canvas
        self.film_strip_sprite.set_parent_canvas(self)
        self.film_strip.set_parent_canvas(self)

        # Add FilmStripSprite to the sprite groups explicitly
        if groups:
            if isinstance(groups, (list, tuple)):
                for group in groups:
                    group.add(self.film_strip_sprite)
            else:
                groups.add(self.film_strip_sprite)

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
        self.mini_view = MiniView(
            pixels=current_frame_pixels,
            x=mini_map_x,
            y=mini_map_y,
            width=self.pixels_across,
            height=self.pixels_tall,
            groups=groups,
        )

        # Add MiniView to the sprite groups explicitly
        if groups:
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
        if hasattr(self, "mini_view"):
            current_frame_pixels = self._get_current_frame_pixels()
            self.log.debug(
                f"Updating mini view with {len(current_frame_pixels)} pixels, "
                f"first few: {current_frame_pixels[:5]}"
            )
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
                self.log.warning(
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
        frames = self.animated_sprite._animations
        if animation in frames and 0 <= frame < len(frames[animation]):
            self.current_animation = animation
            self.current_frame = frame

            # Update the animated sprite to the new animation and frame
            if animation != self.animated_sprite.current_animation:
                self.animated_sprite.set_animation(animation)
            self.animated_sprite.set_frame(frame)

            # Update the canvas interface
            self.canvas_interface.set_current_frame(animation, frame)

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
            if hasattr(self, "mini_view"):
                self.mini_view.pixels = self.pixels.copy()
                self.mini_view.dirty_pixels = [True] * len(self.pixels)
                self.mini_view.dirty = 1

            # Update film strip
            if hasattr(self, "film_strip"):
                self.film_strip.current_animation = animation
                self.film_strip.current_frame = frame
                self.film_strip.update_scroll_for_frame(frame)
                self.film_strip.update_layout()

            # Update film strip sprite
            if hasattr(self, "film_strip_sprite"):
                self.film_strip_sprite.dirty = 1

            # Note: Live preview functionality is now integrated into the film strip

    def next_frame(self) -> None:
        """Move to the next frame in the current animation."""
        frames = self.animated_sprite._animations
        if self.current_animation in frames:
            frame_list = frames[self.current_animation]
            self.current_frame = (self.current_frame + 1) % len(frame_list)
            self.show_frame(self.current_animation, self.current_frame)

    def previous_frame(self) -> None:
        """Move to the previous frame in the current animation."""
        frames = self.animated_sprite._animations
        if self.current_animation in frames:
            frame_list = frames[self.current_animation]
            self.current_frame = (self.current_frame - 1) % len(frame_list)
            self.show_frame(self.current_animation, self.current_frame)

    def next_animation(self) -> None:
        """Move to the next animation."""
        frames = self.animated_sprite._animations
        animations = list(frames.keys())
        if animations:
            current_index = animations.index(self.current_animation)
            next_index = (current_index + 1) % len(animations)
            self.show_frame(animations[next_index], 0)

    def previous_animation(self) -> None:
        """Move to the previous animation."""
        frames = self.animated_sprite._animations
        animations = list(frames.keys())
        if animations:
            current_index = animations.index(self.current_animation)
            prev_index = (current_index - 1) % len(animations)
            self.show_frame(animations[prev_index], 0)

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
        # Delegate to the sprite serializer
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
        ) and hasattr(self, "mini_view"):
            self.log.info("Mouse outside canvas/window, clearing miniview cursor")
            self.mini_view.clear_cursor()

        # Animation timing is handled by the scene's update_animation method

        if self.dirty:
            self.force_redraw()
            self.dirty = 0

    def update_animation(self, dt: float) -> None:
        """Update the animated sprite with delta time."""
        if hasattr(self, "animated_sprite") and self.animated_sprite:
            self.animated_sprite.update(dt)

    def force_redraw(self):
        """Force a complete redraw of the canvas."""
        # Use the interface-based rendering while maintaining existing behavior
        self.image = self.canvas_renderer.force_redraw(self)
        self.log.debug(f"Animated canvas force redraw complete with {len(self.pixels)} pixels")

    def on_left_mouse_button_down_event(self, event):
        """Handle the left mouse button down event."""
        self.log.info(f"AnimatedCanvasSprite mouse down event at {event.pos}, rect: {self.rect}")
        if self.rect.collidepoint(event.pos):
            x = (event.pos[0] - self.rect.x) // self.pixel_width
            y = (event.pos[1] - self.rect.y) // self.pixel_height
            self.log.info(f"AnimatedCanvasSprite clicked at pixel ({x}, {y})")

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
            if hasattr(self, "mini_view"):
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
            # Convert mouse position to pixel coordinates
            x = (event.pos[0] - self.rect.x) // self.pixel_width
            y = (event.pos[1] - self.rect.y) // self.pixel_height

            # Check if the coordinates are within valid range
            if 0 <= x < self.pixels_across and 0 <= y < self.pixels_tall:
                if hasattr(self, "mini_view"):
                    self.mini_view.update_canvas_cursor(x, y, self.active_color)
            elif hasattr(self, "mini_view"):
                self.mini_view.clear_cursor()
        elif hasattr(self, "mini_view"):
            self.mini_view.clear_cursor()

    def on_pixel_update_event(self, event, trigger):
        """Handle pixel update events."""
        if hasattr(trigger, "pixel_number"):
            pixel_num = trigger.pixel_number
            new_color = trigger.pixel_color
            self.log.info(f"Animated canvas updating pixel {pixel_num} to color {new_color}")

            self.pixels[pixel_num] = new_color
            self.dirty_pixels[pixel_num] = True
            self.dirty = 1

            # Update film strip when canvas content changes
            if hasattr(self, "film_strip_sprite"):
                self.film_strip_sprite.dirty = 1
            if hasattr(self, "film_strip"):
                self.film_strip.mark_dirty()

            # Update the animated sprite's frame data
            if hasattr(self, "animated_sprite"):
                self._update_animated_sprite_frame()

            # Update miniview
            self.mini_view.on_pixel_update_event(event, trigger)

    def on_mouse_leave_window_event(self, event):
        """Handle mouse leaving window event."""
        self.log.info("Mouse left window, clearing miniview cursor")
        if hasattr(self, "mini_view"):
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
        if hasattr(self, "mini_view"):
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
            self.log.exception("Error saving file")
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
        try:
            filename = event if isinstance(event, str) else event.text

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
            self.log.exception("File not found")
            # Show user-friendly error message instead of crashing
            if hasattr(self, "parent") and hasattr(self.parent, "debug_text"):
                self.parent.debug_text.text = f"Error: File not found - {e}"
        except Exception as e:
            self.log.exception("Error in on_load_file_event for animated sprite")
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
        if hasattr(self, "mini_view"):
            self.log.debug("Updating mini view after animation change")
            self._update_mini_view_from_current_frame()

        # Note: Live preview functionality is now integrated into the film strip

        # Update the film strip widget with the new animated sprite
        if hasattr(self, "film_strip") and self.film_strip is not None:
            self.log.debug("Updating film strip with new animated sprite")
            self.film_strip.set_animated_sprite(loaded_sprite)
            self.log.debug("Film strip updated with new animated sprite")

        # Update the film strip sprite to force redraw
        if hasattr(self, "film_strip_sprite") and self.film_strip_sprite is not None:
            self.film_strip_sprite.dirty = 1
            self.log.debug("Film strip sprite marked for redraw")

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

        # Reset AI textbox to prompt string after successful sprite loading
        if hasattr(self, "parent") and hasattr(self.parent, "debug_text"):
            self.parent.debug_text.text = "Enter a description of the sprite you want to create:"

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
        available_height = screen_height - 100 - 24  # Adjust for bottom margin and menu bar
        pixel_size = min(available_height // sprite_height, (screen_width * 2 // 3) // sprite_width)

        # Update pixel dimensions
        self.pixel_width = pixel_size
        self.pixel_height = pixel_size

        # Create new pixel arrays
        self.pixels = [(255, 0, 255)] * (sprite_width * sprite_height)  # Initialize with magenta
        self.dirty_pixels = [True] * (sprite_width * sprite_height)

        # Update surface dimensions
        actual_width = sprite_width * pixel_size
        actual_height = sprite_height * pixel_size
        self.image = pygame.Surface((actual_width, actual_height))
        self.rect = self.image.get_rect(x=self.rect.x, y=self.rect.y)

        # Update class dimensions
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
            self.mini_view.pixels = [(255, 0, 255)] * (width * height)
        self.mini_view.dirty_pixels = [True] * (width * height)

        # Don't update mini view pixels here - it will be updated later after animation is set
        self.log.debug("Mini view resized, will update pixels after animation is set")

        # Force redraw
        self.mini_view.dirty = 1
        self.mini_view.force_redraw()

        self.log.debug(
            f"Mini view resized to {width}x{height} at position ({mini_map_x}, {mini_map_y})"
        )
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
                # Create a new surface from the canvas pixels
                surface = pygame.Surface((self.pixels_across, self.pixels_tall))
                for y in range(self.pixels_tall):
                    for x in range(self.pixels_across):
                        pixel_num = y * self.pixels_across + x
                        if pixel_num < len(self.pixels):
                            color = self.pixels[pixel_num]
                            surface.set_at((x, y), color)

                # Update the frame's image
                frame.image = surface

                # Update the film strip
                if hasattr(self, "film_strip"):
                    self.film_strip.update_layout()
                    self.film_strip.mark_dirty()

                # Update film strip sprite
                if hasattr(self, "film_strip_sprite"):
                    self.film_strip_sprite.dirty = 1

    def get_canvas_surface(self):
        """Get the current canvas surface for the film strip."""
        # Create a surface from the current canvas pixels
        surface = pygame.Surface((self.pixels_across, self.pixels_tall))
        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                pixel_num = y * self.pixels_across + x
                if pixel_num < len(self.pixels):
                    color = self.pixels[pixel_num]
                    surface.set_at((x, y), color)
        return surface


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
            self.log.info(f"MiniView updating pixel {pixel_num} to color {new_color}")

            self.pixels[pixel_num] = new_color
            self.dirty_pixels[pixel_num] = True
            self.dirty = 1

    def force_redraw(self):
        """Force a complete redraw of the miniview."""
        self.log.info(f"Starting force_redraw with background color {self.background_color}")
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
    """Bitmap Editor Scene."""

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
        bottom_margin = 100  # Space needed for sliders and color well
        available_height = (
            self.screen_height - bottom_margin - menu_bar_height
        )  # Use menu_bar_height instead of 32

        # Calculate pixel size to fit the canvas in the available space
        width, height = options["size"].split("x")
        pixels_across = int(width)
        pixels_tall = int(height)

        pixel_size = min(
            available_height // pixels_tall,  # Height-based size
            # Width-based size (use 2/3 of screen width)
            (self.screen_width * 2 // 3) // pixels_across,
        )

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
        frame1.pixels = [(255, 0, 255)] * (pixels_across * pixels_tall)

        # Create animated sprite using proper initialization - single frame
        animated_sprite = AnimatedSprite()
        # Use the proper method to set up animations with single frame
        animation_name = "frame"  # Use a generic name for new sprites
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

        # Debug: Log canvas position and size
        self.log.info(
            f"AnimatedCanvasSprite created at position "
            f"({self.canvas.rect.x}, {self.canvas.rect.y}) with size {self.canvas.rect.size}"
        )
        self.log.info(f"AnimatedCanvasSprite groups: {self.canvas.groups()}")

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
        slider_x = 10
        label_width = 32  # Width of the text sprite
        label_padding = 10  # Padding between slider and label
        well_padding = 20  # Padding between labels and color well

        self.red_slider = SliderSprite(
            name="R",
            x=slider_x,
            y=self.screen_height - 70,
            width=slider_width,
            height=slider_height,
            parent=self,
            groups=self.all_sprites,
        )

        self.green_slider = SliderSprite(
            name="G",
            x=slider_x,
            y=self.screen_height - 50,
            width=slider_width,
            height=slider_height,
            parent=self,
            groups=self.all_sprites,
        )

        self.blue_slider = SliderSprite(
            name="B",
            x=slider_x,
            y=self.screen_height - 30,
            width=slider_width,
            height=slider_height,
            parent=self,
            groups=self.all_sprites,
        )

        # Create the color well to the right of the sliders AND their labels
        well_size = 64
        total_slider_width = (
            slider_width + label_padding + label_width  # Full width including label
        )

        self.color_well = ColorWellSprite(
            name="Color Well",
            # Position after sliders + labels + padding
            x=slider_x + total_slider_width + well_padding,
            y=self.screen_height - 70,  # Align with top slider
            width=well_size,
            height=well_size,
            parent=self,
            groups=self.all_sprites,
        )

        self.red_slider.value = 0
        self.blue_slider.value = 0
        self.green_slider.value = 0

        self.color_well.active_color = (
            self.red_slider.value,
            self.green_slider.value,
            self.blue_slider.value,
        )

        self.canvas.active_color = self.color_well.active_color

    def _setup_debug_text_box(self) -> None:
        """Set up the debug text box and AI label."""
        # Calculate debug text box position and size - align to bottom right corner
        debug_width = 300  # Fixed width for AI chat box
        debug_height = 200  # Fixed height for AI chat box
        debug_x = self.screen_width - debug_width  # Align to right edge
        debug_y = self.screen_height - debug_height  # Align to bottom edge

        # Create the AI label
        label_height = 20
        self.ai_label = TextSprite(
            x=debug_x,
            y=debug_y - label_height,
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

        # Set up all components
        self._setup_menu_bar()
        self._setup_canvas(options)
        self._setup_sliders_and_color_well()
        self._setup_debug_text_box()

        # Query model capabilities for optimal token usage
        try:
            capabilities = _get_model_capabilities(self.log)
            if capabilities.get("max_tokens"):
                self.log.info(f"Model max tokens detected: {capabilities['max_tokens']}")
                # Could update AI_MAX_TOKENS here if needed
        except (ValueError, ConnectionError, TimeoutError) as e:
            self.log.warning(f"Could not query model capabilities: {e}")

        self.all_sprites.clear(self.screen, self.background)

        # TODO: Plumb this into the scene manager
        # self.register_game_event('save', self.on_save_event)
        # self.register_game_event('load', self.on_load_event)

        self.new_canvas_dialog_scene = NewCanvasDialogScene(
            options=self.options, previous_scene=self
        )
        self.load_dialog_scene = LoadDialogScene(options=self.options, previous_scene=self)
        self.save_dialog_scene = SaveDialogScene(options=self.options, previous_scene=self)

        # These are set up in the GameEngine class.
        if not hasattr(self, "_initialized"):
            self.log.info(f"Game Options: {options}")

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
            available_height = self.screen_height - 100 - 24
            new_pixel_size = min(
                available_height // height,  # Height-based size
                (self.screen_width * 2 // 3) // width,  # Width-based size (use 2/3 of screen width)
            )
            self.log.info(f"Calculated new pixel size: {new_pixel_size}")

            # Resize the canvas
            self.canvas.pixels_across = width
            self.canvas.pixels_tall = height
            self.canvas.pixel_width = new_pixel_size
            self.canvas.pixel_height = new_pixel_size

            # Clear and resize the canvas
            self.canvas.pixels = [(255, 0, 255)] * (width * height)  # Use magenta as background
            self.canvas.dirty_pixels = [True] * len(self.canvas.pixels)

            # Update canvas image size
            self.canvas.image = pygame.Surface((width * new_pixel_size, height * new_pixel_size))
            self.canvas.rect = self.canvas.image.get_rect(x=0, y=24)  # Position below menu bar

            # Update mini map position for new size
            screen_info = pygame.display.Info()
            screen_width = screen_info.current_w
            pixel_width = 2  # MiniView uses 2x2 pixels per sprite pixel
            mini_map_width = width * pixel_width
            mini_map_x = max(screen_width - mini_map_width, 0)  # Flush to right edge
            mini_map_y = 24  # Flush to top

            # Update mini map
            if hasattr(self.canvas, "mini_view"):
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
            self.log.exception(f"Invalid dimensions format '{dimensions}'")
            self.log.exception("Expected format: WxH (e.g., '32x32')")

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
        self.new_canvas_dialog_scene.all_sprites.clear(
            self.new_canvas_dialog_scene.screen, self.screenshot
        )
        self.next_scene = self.new_canvas_dialog_scene
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
        self.load_dialog_scene.all_sprites.clear(self.load_dialog_scene.screen, self.screenshot)
        self.next_scene = self.load_dialog_scene
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
        self.save_dialog_scene.all_sprites.clear(self.save_dialog_scene.screen, self.screenshot)
        self.next_scene = self.save_dialog_scene
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

        # Debug: Log current slider values
        self.log.debug(
            f"Current slider values - R: {self.red_slider.value}, "
            f"G: {self.green_slider.value}, B: {self.blue_slider.value}"
        )

        self.color_well.active_color = (
            self.red_slider.value,
            self.green_slider.value,
            self.blue_slider.value,
        )
        self.canvas.active_color = (
            self.red_slider.value,
            self.green_slider.value,
            self.blue_slider.value,
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
        # If we're on the edge of an outside pixel, ignore
        # the right click so we don't crash.
        try:
            red, green, blue, alpha = self.screen.get_at(event.pos)
            self.log.info(f"Red: {red}, Green: {green}, Blue: {blue}, Alpha: {alpha}")

            # TODO: Make this a proper type.
            trigger = pygame.event.Event(0, {"name": "R", "value": red})
            self.on_slider_event(event=event, trigger=trigger)

            trigger = pygame.event.Event(0, {"name": "G", "value": green})
            self.on_slider_event(event=event, trigger=trigger)

            trigger = pygame.event.Event(0, {"name": "B", "value": blue})
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

        for sprite in sprites:
            sprite.on_left_mouse_button_down_event(event)

    def on_left_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the left mouse button up event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None

        """
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

    def on_text_submit_event(self, text: str) -> None:
        """Handle text submission from MultiLineTextBox."""
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
                        - [colors.X] sections ONLY for colors that are actually used "
                        "in the pixel data
                        - RGB values from 0-255 for each color
                        - Pixels using the SPRITE_GLYPHS character set
                        - For animated sprites: [[animation]] and [[animation.frame]] sections
                        - When "frame", "animation", "animated", "2-frame", or "
                        "multi-frame"
                          is mentioned, I will create an ANIMATED sprite with multiple frames
                        - IMPORTANT: Use triple-quoted block strings for multi-line pixel data
                        - EFFICIENCY: Only define colors that appear in the pixels "
                        "(e.g., if pixels=\"0\", only define [colors.0])
                """.strip()
        else:
            format_instruction = """
                    I understand. I will provide ONLY raw INI content without any
                    markdown formatting, code blocks, or explanations. The INI format
                    will include:
                        - [sprite] section containing name and pixel layout
                        - [0] through [7] for color definitions
                        - RGB values from 0-255 for each color
                        - Pixels using the SPRITE_GLYPHS character set
                """.strip()

        # Select relevant training examples
        relevant_examples = _select_relevant_training_examples(text)
        self.log.info(
            f"Using {len(relevant_examples)} training examples (max: {AI_MAX_TRAINING_EXAMPLES})"
        )

        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": f"""
                    You are a helpful assistant in a bitmap editor that can create
                    game content for game developers. You can create both static
                    single-frame sprites and animated multi-frame sprites.

                    Available character set for sprite pixels: {SPRITE_GLYPHS}
                """.strip(),
            },
            {
                "role": "user",
                "content": f"""
                            Here are some example sprites that I've created. Use these
                            as training data to understand how to create new sprites:

                            {"\n".join([str(data) for data in relevant_examples])}

                            Available character set: {SPRITE_GLYPHS}
                        """.strip(),
            },
            {
                "role": "assistant",
                "content": f"""
                    Thank you for providing those sprite examples. I understand
                    that each sprite consists of:

                    1. A name
                    2. A pixel layout using characters from: {SPRITE_GLYPHS}
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
            self.log.exception("Error submitting AI request")
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
                self.log.exception("Error initializing AI worker process")
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
                if "sprite" not in data:
                    data["sprite"] = {}
                data["sprite"]["description"] = original_prompt
                cleaned_content = toml.dumps(data)
                self.log.debug(f"Added description to TOML content: '{original_prompt}'")
            except (toml.TomlDecodeError, KeyError, ValueError) as e:
                self.log.warning(f"Failed to add description to TOML content: {e}")

        return cleaned_content

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
        if hasattr(self.canvas, "mini_view"):
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
        if hasattr(self.canvas, "mini_view"):
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

            # Update UI components
            self._update_ui_after_ai_load(request_id)

            # Clean up pending request
            self._cleanup_ai_request(request_id)

        except Exception as sprite_error:
            self.log.exception("Failed to load AI sprite")
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

            # Log animation state every 60 frames (about once per second at 60fps)
            if self._debug_animation_counter % 60 == 0:
                self.log.debug(
                    f"Animation update - is_playing={self.canvas.animated_sprite.is_playing}, "
                    f"current_frame={self.canvas.animated_sprite.current_frame}"
                )

            # Pass delta time to the canvas for animation updates
            self.canvas.update_animation(self.dt)

            # Update film strip preview animations
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
                self.log.exception("Error processing AI response")

    def _shutdown_ai_worker(self) -> None:
        """Signal AI worker to shut down."""
        if hasattr(self, "ai_request_queue") and self.ai_request_queue:
            try:
                self.log.info("Sending shutdown signal to AI worker...")
                self.ai_request_queue.put(None, timeout=1.0)  # Add timeout
                self.log.info("Shutdown signal sent successfully")
            except Exception:
                self.log.exception("Error sending shutdown signal")

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
            self.log.exception("Error during AI process cleanup")
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
                self.log.exception("Error closing request queue")

        if hasattr(self, "ai_response_queue") and self.ai_response_queue:
            try:
                self.ai_response_queue.close()
                self.log.info("AI response queue closed")
            except Exception:
                self.log.exception("Error closing response queue")

    def cleanup(self):
        """Clean up resources."""
        self.log.info("Starting AI cleanup...")

        self._shutdown_ai_worker()
        self._cleanup_ai_process()
        self._cleanup_queues()

        super().cleanup()

    def on_key_down_event(self, event: pygame.event.Event) -> None:
        """Handle keyboard events for frame navigation and text input."""
        self.log.debug(f"Key down event received: key={event.key}")

        # Check if debug text box is active and handle text input
        if hasattr(self, "debug_text") and self.debug_text.active:
            self.debug_text.on_key_down_event(event)
            return

        # Check if we have an animated canvas
        if hasattr(self, "canvas") and hasattr(self.canvas, "handle_keyboard_event"):
            self.log.debug("Routing keyboard event to canvas")
            self.canvas.handle_keyboard_event(event.key)
        else:
            # Fall back to parent class handling
            self.log.debug("No canvas found, using parent class handling")
            super().on_key_down_event(event)

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

    def handle_event(self, event):
        """Handle pygame events."""
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
                self.log.exception("Generator empty on first triplet!")
                raise

            # Now proceed with the rest of deflate
            raw_pixels = list(raw_pixels)
            self.log.debug(f"Converted {len(raw_pixels)} RGB triplets to list")

            # Continue with original deflate code...
            colors = set(raw_pixels)
            self.log.debug(f"Found {len(colors)} unique colors")

        except Exception:
            self.log.exception("Error in deflate")
            raise
        else:
            return config


def main() -> None:
    """Run the main function.

    Args:
        None

    Returns:
        None

    Raises:
        None

    """

    LOG.setLevel(logging.INFO)

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
