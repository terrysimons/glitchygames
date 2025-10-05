#!/usr/bin/env python3
"""Glitchy Games Bitmap Editor."""

from __future__ import annotations

import collections
import configparser
import contextlib
import logging
import multiprocessing
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
    AnimatedSprite,
    BitmappySprite,
    SpriteFactory,
    SpriteFrame,
)
from glitchygames.sprites.constants import DEFAULT_FILE_FORMAT
from glitchygames.ui import (
    ColorWellSprite,
    InputDialog,
    MenuBar,
    MenuItem,
    MultiLineTextBox,
    SliderSprite,
    TextSprite,
)

from .canvas_interfaces import (
    AnimatedCanvasInterface,
    AnimatedCanvasRenderer,
    AnimatedSpriteSerializer,
    StaticCanvasInterface,
    StaticCanvasRenderer,
    StaticSpriteSerializer,
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

CRITICAL RULES:
    - ALWAYS include ALL 8 color definitions (colors.0 through colors.7)
    - ALWAYS include namespace in each [[animation.frame]] section
    - ALWAYS include frame_index in each [[animation.frame]] section
    - ALWAYS include frame_interval and loop in [[animation]] section
    - NEVER mix static and animated content in the same file!
    - Static sprites: [sprite] with pixels + [colors] sections ONLY
    - Animated sprites: [sprite] with NO pixels item + [colors] + [[animation]] sections ONLY
    - IMPORTANT: Animated sprites must NOT have a pixels item in the [sprite] section!
"""

LOG = logging.getLogger("game.bitmappy")

# Set up logging
LOG.setLevel(logging.DEBUG)
if not LOG.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    LOG.addHandler(handler)

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
    if filename_lower.endswith(".ini"):
        return "ini"
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
LOG.info(f"Loading AI training data from: {SPRITE_CONFIG_DIR}")
LOG.debug(f"Sprite config directory exists: {SPRITE_CONFIG_DIR.exists()}")

if SPRITE_CONFIG_DIR.exists():
    # Look for TOML files first (preferred), then fall back to INI
    toml_files = list(SPRITE_CONFIG_DIR.glob("*.toml"))
    ini_files = list(SPRITE_CONFIG_DIR.glob("*.ini"))

    if toml_files:
        config_files = toml_files
        AI_TRAINING_FORMAT = "toml"
        LOG.info(f"Found {len(config_files)} TOML sprite config files")
    elif ini_files:
        config_files = ini_files
        AI_TRAINING_FORMAT = "ini"
        LOG.info(f"Found {len(config_files)} INI sprite config files")
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

            else:  # INI format
                config = configparser.ConfigParser()
                config.read(config_file)

                # Extract sprite data from INI structure
                sprite_data = {
                    "name": config.get("sprite", "name", fallback="Unknown"),
                    "format": AI_TRAINING_FORMAT,
                    "sprite_type": "animated" if "animation" in config.sections() else "static",
                }

                # For static sprites, extract pixel data and colors
                if "sprite" in config:
                    sprite_data["pixels"] = config.get("sprite", "pixels", fallback="")
                    sprite_data["colors"] = {}
                    for i in range(8):
                        if str(i) in config:
                            sprite_data["colors"][str(i)] = {
                                "red": config.getint(str(i), "red", fallback=0),
                                "green": config.getint(str(i), "green", fallback=0),
                                "blue": config.getint(str(i), "blue", fallback=0),
                            }

                # For animated sprites, extract animation data
                if "animation" in config:
                    sprite_data["animations"] = dict(config["animation"])

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


class InputConfirmationDialogScene(Scene):
    """Input Confirmation Dialog Scene."""

    log = LOG
    NAME = "InputConfirmationDialog"
    DIALOG_TEXT = "Would you like to do a thing?"
    CONFIRMATION_TEXT = "Confirm"
    CANCEL_TEXT = "Cancel"
    VERSION = ""

    def __init__(
        self: Self,
        previous_scene: Scene,
        options: dict | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
        """Initialize the Input Confirmation Dialog Scene.

        Args:
            previous_scene (Scene): The previous scene.
            options (dict, optional): Options for the scene. Defaults to None.
            groups (pygame.sprite.LayeredDirty, optional): Sprite groups.
                   Defaults to pygame.sprite.LayeredDirty().

        Returns:
            None

        Raises:
            None

        """
        if groups is None:
            # Create a new LayeredDirty group specifically for the dialog
            groups = pygame.sprite.LayeredDirty()

        super().__init__(options=options, groups=groups)
        self.previous_scene = previous_scene

        # Create dialog with its own sprite group
        dialog_width = self.screen_width // 2
        dialog_height = self.screen_height // 2

        self.dialog = InputDialog(
            name=self.NAME,
            dialog_text=self.DIALOG_TEXT,  # Use this instance's DIALOG_TEXT
            confirm_text=self.CONFIRMATION_TEXT,
            cancel_text=self.CANCEL_TEXT,
            x=self.screen.get_rect().center[0] - (dialog_width // 2),
            y=self.screen.get_rect().center[1] - (dialog_height // 2),
            width=dialog_width,
            height=dialog_height,
            parent=self,
            groups=self.all_sprites,
        )
        # Set the dialog text
        # Use this instance's DIALOG_TEXT
        self.dialog.dialog_text_sprite.text_box.text = self.DIALOG_TEXT
        self.dialog.dialog_text_sprite.border_width = 0

    def setup(self: Self) -> None:
        """Set up the scene.

        Args:
            None

        Returns:
            None

        Raises:
            None

        """
        self.dialog.cancel_button.callbacks = {
            "on_left_mouse_button_up_event": self.on_cancel_event
        }
        self.dialog.confirm_button.callbacks = {
            "on_left_mouse_button_up_event": self.on_confirm_event
        }

        self.dialog.add(self.all_sprites)

    def cleanup(self: Self) -> None:
        """Cleanup the scene.

        Args:
            None

        Returns:
            None

        Raises:
            None

        """
        self.next_scene = self

    def dismiss(self: Self) -> None:
        """Dismiss the dialog.

        Args:
            None

        Returns:
            None

        Raises:
            None

        """
        # Set next scene before cleanup
        self.previous_scene.next_scene = self.previous_scene
        self.next_scene = self.previous_scene

        # Clear all sprites from our group
        self.all_sprites.empty()

        # Force the previous scene to redraw completely
        for sprite in self.previous_scene.all_sprites:
            sprite.dirty = 1

    def on_cancel_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle the cancel event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Returns:
            None

        Raises:
            None

        """
        self.log.info(f"Cancel: event: {event}, trigger: {trigger}")
        self.dismiss()

    def on_confirm_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle confirm events."""
        self.log.info(f"Confirm: event: {event}, trigger: {trigger}")
        # Get the text from input box before dismissing
        filename = self.dialog.input_box.text
        # Dismiss first to restore previous scene
        self.dismiss()
        # Then trigger appropriate canvas event based on dialog type
        if isinstance(self, SaveDialogScene):
            self.previous_scene.canvas.on_save_file_event(filename)
        elif isinstance(self, LoadDialogScene):
            self.previous_scene.canvas.on_load_file_event(filename)
        elif isinstance(self, NewCanvasDialogScene):
            self.previous_scene.canvas.on_new_file_event(filename)

    def on_input_box_submit_event(self: Self, control: object) -> None:
        """Handle the input box submit event.

        Args:
            control (object): The control object.

        Returns:
            None

        Raises:
            None

        """
        self.log.info(f"{self.name} Got text input from: {control.name}: {control.text}")

    def on_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the mouse button up event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None

        """
        self.dialog.input_box.activate()

    def on_key_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the key up event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None

        """
        if self.dialog.input_box.active:
            self.dialog.on_key_up_event(event)
        elif event.key == pygame.K_TAB:
            self.dialog.input_box.activate()
        else:
            super().on_key_up_event(event)

    def on_key_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle the key down event.

        Args:
            event (pygame.event.Event): The pygame event.

        Returns:
            None

        Raises:
            None

        """
        if self.dialog.input_box.active:
            self.dialog.on_key_down_event(event)
        else:
            super().on_key_up_event(event)


class NewCanvasDialogScene(InputConfirmationDialogScene):
    """New Canvas Dialog Scene."""

    log = LOG
    NAME = "New Canvas Dialog"
    DIALOG_TEXT = "Enter canvas size (WxH):"
    CONFIRMATION_TEXT = "Create"
    CANCEL_TEXT = "Cancel"

    def __init__(
        self: Self,
        previous_scene: Scene,
        options: dict | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
        """Initialize the New Canvas Dialog Scene.

        Args:
            previous_scene (Scene): The previous scene.
            options (dict, optional): Options for the scene. Defaults to None.
            groups (pygame.sprite.LayeredDirty, optional): Sprite groups.
                   Defaults to pygame.sprite.LayeredDirty().

        Returns:
            None

        Raises:
            None

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()
        super().__init__(previous_scene, options=options, groups=pygame.sprite.LayeredDirty())

    def on_confirm_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle the confirm event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Returns:
            None

        Raises:
            None

        """
        self.log.info(f"New Canvas: event: {event}, trigger: {trigger}")
        # Extract the text from the input box
        dimensions = self.dialog.input_box.text
        self.log.info(f"New Canvas dimensions: {dimensions}")
        self.log.info(f"Calling scene.on_new_file_event with dimensions: {dimensions}")
        self.previous_scene.on_new_file_event(dimensions)
        self.log.info("Scene.on_new_file_event completed")
        self.dismiss()


class LoadDialogScene(InputConfirmationDialogScene):
    """Load Dialog Scene."""

    log = LOG
    NAME = "Load Dialog"
    DIALOG_TEXT = "Enter filename to load:"
    CONFIRMATION_TEXT = "Load"
    CANCEL_TEXT = "Cancel"
    VERSION = ""

    def __init__(
        self: Self,
        previous_scene: Scene,
        options: dict | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
        """Initialize the Load Dialog Scene.

        Args:
            previous_scene (Scene): The previous scene.
            options (dict, optional): Options for the scene. Defaults to None.
            groups (pygame.sprite.LayeredDirty, optional): Sprite groups.
                   Defaults to pygame.sprite.LayeredDirty().

        Returns:
            None

        Raises:
            None

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(previous_scene, options=options, groups=pygame.sprite.LayeredDirty())

    def on_confirm_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle the confirm event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Returns:
            None

        Raises:
            None

        """
        self.log.info(f"Load File: event: {event}, trigger: {trigger}")
        self.previous_scene.canvas.on_load_file_event(self.dialog.input_box, self.dialog.input_box)
        self.dismiss()


class SaveDialogScene(InputConfirmationDialogScene):
    """Save Dialog Scene."""

    log = LOG
    NAME = "Save Dialog"
    DIALOG_TEXT = "Enter filename to save:"
    CONFIRMATION_TEXT = "Save"
    CANCEL_TEXT = "Cancel"
    VERSION = ""

    def __init__(
        self: Self,
        previous_scene: Scene,
        options: dict | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
        """Initialize the Save Dialog Scene.

        Args:
            previous_scene (Scene): The previous scene.
            options (dict, optional): Options for the scene. Defaults to None.
            groups (pygame.sprite.LayeredDirty, optional): Sprite groups.
                   Defaults to pygame.sprite.LayeredDirty().

        Returns:
            None

        Raises:
            None

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(previous_scene, options=options, groups=pygame.sprite.LayeredDirty())

    def on_confirm_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle the confirm event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Returns:
            None

        """
        self.log.info(f"Save File: event: {event}, trigger: {trigger}")
        # Get the filename from the input box
        filename = self.dialog.input_box.text
        # Call save with just the filename
        self.previous_scene.canvas.on_save_file_event(filename)
        self.dismiss()


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

    # def on_left_mouse_drag_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
    #     # There's not a good way to pass any useful info, so for now, pass None
    #     # since we're not using the event for anything in this class.
    #     self.on_left_mouse_button_down_event(None)


class Canvas(BitmappySprite):
    """Canvas."""

    def __init__(self: Self) -> None:
        """Create a Canvas."""

    def update(self: Self) -> None:
        """Update the canvas."""
        # Draw the miniview pixel canvas
        # Draw the pixel canvas
        # Draw the pixel canvas border
        # Draw the pixel canvas grid


class CanvasSprite(BitmappySprite):
    """Canvas Sprite."""

    log = LOG

    def __init__(
        self,
        name="Canvas",
        x=0,
        y=0,
        pixels_across=32,
        pixels_tall=32,
        pixel_width=16,
        pixel_height=16,
        groups=None,
    ):
        """Initialize the Canvas Sprite."""
        # Calculate dimensions first
        self.pixels_across = pixels_across
        self.pixels_tall = pixels_tall
        self.pixel_width = pixel_width
        self.pixel_height = pixel_height
        width = self.pixels_across * self.pixel_width
        height = pixels_tall * pixel_height

        # Initialize parent class first to create rect
        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            groups=groups,
        )

        # Store pixel-related attributes
        self.pixels_across = pixels_across
        self.pixels_tall = pixels_tall
        self.pixel_width = pixel_width
        self.pixel_height = pixel_height

        # Initialize pixels with magenta as the transparent/background color
        self.pixels = [(255, 0, 255) for _ in range(self.pixels_across * self.pixels_tall)]
        self.dirty_pixels = [True] * len(self.pixels)
        self.background_color = (128, 128, 128)
        self.active_color = (0, 0, 0)
        self.border_thickness = 1

        # Create initial surface
        self.image = pygame.Surface((self.width, self.height))
        self.rect = self.image.get_rect(x=x, y=y)

        # Initialize interface components for static sprites
        self.canvas_interface = StaticCanvasInterface(self)
        self.sprite_serializer = StaticSpriteSerializer()
        self.canvas_renderer = StaticCanvasRenderer(self)

        # Get screen dimensions from pygame
        screen_info = pygame.display.Info()
        screen_width = screen_info.current_w

        # Calculate mini map size (2x2 pixels per sprite pixel)
        pixel_width = 2  # MiniView uses 2x2 pixels per sprite pixel
        mini_map_width = self.pixels_across * pixel_width

        # Position mini map flush to the right edge and top
        mini_map_x = screen_width - mini_map_width  # Flush to right edge
        mini_map_y = 24  # Flush to top (below menu bar)

        # Ensure mini map doesn't go off screen
        if mini_map_x < 0:
            mini_map_x = 20  # Fallback to left side if too wide

        # Create miniview - position in top right corner
        self.mini_view = MiniView(
            pixels=self.pixels,
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

        # Force initial draw
        self.dirty = 1
        self.force_redraw()

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

        if self.dirty:
            self.force_redraw()
            self.dirty = 0

    def force_redraw(self):
        """Force a complete redraw of the canvas."""
        # Use the interface-based rendering while maintaining existing behavior
        self.image = self.canvas_renderer.force_redraw(self)
        self.log.debug(f"Canvas force redraw complete with {len(self.pixels)} pixels")

    def on_left_mouse_button_down_event(self, event):
        """Handle the left mouse button down event."""
        if self.rect.collidepoint(event.pos):
            x = (event.pos[0] - self.rect.x) // self.pixel_width
            y = (event.pos[1] - self.rect.y) // self.pixel_height

            # Use the interface to set the pixel
            self.canvas_interface.set_pixel_at(x, y, self.active_color)

            # Update miniview
            if hasattr(self, "mini_view"):
                self.mini_view.on_pixel_update_event(event, self)

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
            self.log.info(f"Canvas updating pixel {pixel_num} to color {new_color}")

            self.pixels[pixel_num] = new_color
            self.dirty_pixels[pixel_num] = True
            self.dirty = 1

            # Update miniview
            self.mini_view.on_pixel_update_event(event, trigger)

    def on_mouse_leave_window_event(self, event):
        """Handle mouse leaving window event."""
        self.log.info("Mouse left window, clearing miniview cursor")
        if hasattr(self, "mini_view"):
            self.mini_view.clear_cursor()

    def on_mouse_enter_sprite_event(self, event):
        """Handle mouse entering canvas."""
        self.log.info("Mouse entered canvas")
        if hasattr(self, "mini_view"):
            # Update cursor position immediately
            x = (event.pos[0] - self.rect.x) // self.pixel_width
            y = (event.pos[1] - self.rect.y) // self.pixel_height
            if 0 <= x < self.pixels_across and 0 <= y < self.pixels_tall:
                self.mini_view.update_canvas_cursor(x, y, self.active_color)

    def on_mouse_exit_sprite_event(self, event):
        """Handle mouse exiting canvas."""
        self.log.info("Mouse exited canvas")
        if hasattr(self, "mini_view"):
            self.mini_view.clear_cursor()

    def on_save_file_event(self: Self, filename: str) -> None:
        """Handle save file events.

        Args:
            filename (str): The filename to save to.

        Returns:
            None

        """
        self.log.info(f"Starting save to file: {filename}")
        try:
            # Detect file format from extension
            file_format = detect_file_format(filename)
            self.log.info(f"Detected file format: {file_format}")
            # Use the interface-based save method
            self.sprite_serializer.save(self, filename=filename, file_format=file_format)
        except (OSError, ValueError, KeyError):
            self.log.exception("Error saving file")
            raise

    def get_canvas_interface(self) -> StaticCanvasInterface:
        """Get the canvas interface for external access.

        Returns:
            The canvas interface instance

        """
        return self.canvas_interface

    def get_sprite_serializer(self) -> StaticSpriteSerializer:
        """Get the sprite serializer for external access.

        Returns:
            The sprite serializer instance

        """
        return self.sprite_serializer

    def get_canvas_renderer(self) -> StaticCanvasRenderer:
        """Get the canvas renderer for external access.

        Returns:
            The canvas renderer instance

        """
        return self.canvas_renderer

    def _load_file_content(self, filename: str) -> str | None:
        """Load and return file content."""
        if not Path(filename).exists():
            self.log.error(f"File not found: {filename}")
            return None

        try:
            with Path(filename).open("r", encoding="utf-8") as f:
                content = f.read()
            self.log.debug(f"Raw file content:\n{content}")
        except (FileNotFoundError, PermissionError, OSError):
            self.log.exception(f"Error reading file {filename}")
            return None
        else:
            return content

    @staticmethod
    def _parse_color_section(section: str) -> tuple[str, dict[str, str]] | None:
        """Parse a single color section."""
        lines = section.strip().split("\n")
        if not lines[0].startswith("[") or not lines[0].endswith("]"):
            return None

        color_key = lines[0][1:-1]  # Remove [ and ]
        if len(color_key) != 1:  # Single character color
            return None

        color_data = {}
        for line in lines[1:]:
            if "=" in line:
                key, value = line.split("=", 1)
                color_data[key.strip()] = value.strip()

        return color_key, color_data

    def _parse_sections(self, content: str) -> tuple[str | None, dict[str, dict[str, str]]]:
        """Parse content into sprite and color sections."""
        sections = content.split("\n\n")
        self.log.debug(f"Found {len(sections)} sections")

        sprite_section = None
        color_sections = {}

        for section in sections:
            if section.strip().startswith("[sprite]"):
                sprite_section = section
                self.log.debug(f"Sprite section: {sprite_section[:100]}...")
            elif section.strip().startswith("[") and len(section.strip()) > 1:
                # This is a color section
                result = self._parse_color_section(section)
                if result is not None:
                    color_key, color_data = result
                    color_sections[color_key] = color_data

        self.log.debug(f"Color sections: {color_sections}")
        return sprite_section, color_sections

    def _build_color_map(
        self, color_sections: dict[str, dict[str, str]]
    ) -> dict[str, tuple[int, int, int]]:
        """Build color map from color sections."""
        color_map = {}
        for color_key, color_data in color_sections.items():
            if "red" in color_data and "green" in color_data and "blue" in color_data:
                color_map[color_key] = (
                    int(color_data["red"]),
                    int(color_data["green"]),
                    int(color_data["blue"]),
                )
        self.log.debug(f"Color map: {color_map}")
        return color_map

    def _extract_pixel_data(self, sprite_section: str) -> list[str] | None:
        """Extract pixel data from sprite section."""
        if not sprite_section:
            self.log.error("No sprite section found in file")
            return None

        lines = sprite_section.split("\n")
        pixel_lines = []
        in_pixels = False
        for line in lines:
            if "pixels =" in line:
                in_pixels = True
            elif in_pixels and line.strip():
                pixel_lines.append(line.strip())
            elif in_pixels and not line.strip():
                break

        pixel_text = "\n".join(pixel_lines)
        self.log.debug(f"Extracted pixel text:\n{pixel_text}")

        # Split into rows and properly handle indentation
        rows = []
        for i, row in enumerate(pixel_text.splitlines()):
            processed_row = row.lstrip()  # Remove leading/trailing whitespace including tabs
            if processed_row:  # Only add non-empty rows
                rows.append(processed_row)
                self.log.debug(f"Row {i}: '{processed_row}' (len={len(processed_row)})")

        self.log.debug(f"Total rows found: {len(rows)}")

        if not rows:
            self.log.error("No pixel data found in file")
            return None

        return rows

    def _resize_canvas_if_needed(self, width: int, height: int) -> None:
        """Resize canvas if dimensions don't match."""
        if width == self.pixels_across and height == self.pixels_tall:
            return

        self.log.debug(
            f"Resizing canvas from {self.pixels_across}x{self.pixels_tall} to {width}x{height}"
        )
        self.pixels_across = width
        self.pixels_tall = height

        # Get screen dimensions directly from pygame display
        screen = pygame.display.get_surface()
        screen_width = screen.get_width()
        screen_height = screen.get_height()

        # Recalculate pixel dimensions to fit the screen
        available_height = screen_height - 100 - 24  # Adjust for bottom margin and menu bar
        pixel_size = min(available_height // height, (screen_width * 2 // 3) // width)

        # Update pixel dimensions
        self.pixel_width = pixel_size
        self.pixel_height = pixel_size

        # Create new pixel arrays
        self.pixels = [(255, 0, 255)] * (width * height)  # Initialize with magenta
        self.dirty_pixels = [True] * (width * height)

        # Update surface dimensions
        actual_width = width * pixel_size
        actual_height = height * pixel_size
        self.image = pygame.Surface((actual_width, actual_height))
        self.rect = self.image.get_rect(x=self.rect.x, y=self.rect.y)

        # Update class dimensions
        CanvasSprite.WIDTH = width
        CanvasSprite.HEIGHT = height

        # Reinitialize mini view if it exists
        if hasattr(self, "mini_view"):
            self._resize_mini_view(width, height)

    def _resize_mini_view(self, width: int, height: int) -> None:
        """Resize mini view for new canvas dimensions."""
        # Recalculate mini map position for new size
        screen_info = pygame.display.Info()
        screen_width = screen_info.current_w
        pixel_width = 2  # MiniView uses 2x2 pixels per sprite pixel
        mini_map_width = width * pixel_width
        mini_map_x = screen_width - mini_map_width  # Flush to right edge
        if mini_map_x < 0:
            mini_map_x = 20  # Fallback to left side if too wide

        self.mini_view.pixels_across = width
        self.mini_view.pixels_tall = height
        self.mini_view.pixels = self.pixels
        self.mini_view.dirty_pixels = [True] * len(self.pixels)
        pixel_width, pixel_height = self.mini_view.pixels_per_pixel(width, height)
        self.mini_view.image = pygame.Surface((width * pixel_width, height * pixel_height))
        # Flush to top
        self.mini_view.rect = self.mini_view.image.get_rect(x=mini_map_x, y=24)

    def _update_canvas_pixels(
        self, rows: list[str], color_map: dict[str, tuple[int, int, int]]
    ) -> None:
        """Update canvas pixels with new data."""
        for y, row in enumerate(rows):
            for x, char in enumerate(row):
                pixel_num = y * self.pixels_across + x
                if char in color_map:
                    self.pixels[pixel_num] = color_map[char]
                    self.dirty_pixels[pixel_num] = True

    def on_load_file_event(self, event: pygame.event.Event, trigger: object = None) -> None:
        """Handle load file event."""
        self.log.debug("=== Starting on_load_file_event ===")
        try:
            filename = event if isinstance(event, str) else event.text
            self.log.debug(f"Loading canvas from {filename}")

            # Load file content
            content = self._load_file_content(filename)
            if content is None:
                return

            # Parse sections
            sprite_section, color_sections = self._parse_sections(content)

            # Build color map
            color_map = self._build_color_map(color_sections)

            # Extract pixel data
            rows = self._extract_pixel_data(sprite_section)
            if rows is None:
                return

            # Calculate dimensions
            width = len(rows[0])
            height = len(rows)
            self.log.debug(f"Loading image with dimensions {width}x{height}")

            # Resize canvas if needed
            self._resize_canvas_if_needed(width, height)

            # Update canvas pixels
            self._update_canvas_pixels(rows, color_map)

            # Force a complete redraw
            self.dirty = 1
            self.force_redraw()

            # Update miniview if it exists
            if hasattr(self, "mini_view"):
                self.mini_view.dirty = 1
                self.mini_view.force_redraw()

        except Exception:
            self.log.exception("Error in on_load_file_event")
            raise


# class MiniView(BitmappySprite):
#     """Mini View."""

#     log = LOG
#     BACKGROUND_COLORS = [
#         (0, 255, 255),    # Cyan
#         (0, 0, 0),        # Black
#         (128, 128, 128),  # Gray
#         (255, 255, 255),  # White
#         (255, 0, 255),    # Magenta
#         (0, 255, 0),      # Green
#         (0, 0, 255),      # Blue
#         (255, 255, 0),    # Yellow
#         (64, 64, 64),     # Dark Gray
#         (192, 192, 192),  # Light Gray
#     ]

#     def __init__(self, pixels, x, y, width, height, name="Mini View", groups=None):
#         self.pixels_across = width
#         self.pixels_tall = height
#         pixel_width, pixel_height = self.pixels_per_pixel(width, height)
#         actual_width = width * pixel_width
#         actual_height = height * pixel_height

#         super().__init__(
#             x=x,
#             y=y,
#             width=actual_width,
#             height=actual_height,
#             name=name,
#             groups=groups
#         )

#         self.pixels = pixels
#         self.dirty_pixels = [True] * len(pixels)
#         self.background_color_index = 0
#         self.background_color = self.BACKGROUND_COLORS[self.background_color_index]

#         # Create initial surface
#         self.image = pygame.Surface((actual_width, actual_height))
#         self.rect = self.image.get_rect(x=x, y=y)

#         # Initialize cursor and mouse tracking state
#         self.canvas_cursor_pos = None
#         self.cursor_color = (0, 0, 0)  # Will be updated from canvas's active color
#         self.mouse_in_canvas = False

#         self.dirty = 1
#         self.force_redraw()
#         self.log.info("MiniView initialized")

#     def on_left_mouse_button_down_event(self, event):
#         """Handle left mouse button to cycle background color."""
#         if self.rect.collidepoint(event.pos):
#             self.log.info(f"MiniView clicked at {event.pos}, rect is {self.rect}")
#             old_color = self.background_color
#             self.background_color_index = (
#                 (self.background_color_index + 1) % len(self.BACKGROUND_COLORS)
#             )
#             self.background_color = self.BACKGROUND_COLORS[self.background_color_index]
#             self.log.info(
#                 f"MiniView background color changing from {old_color} to {self.background_color}"
#             )
#             self.dirty = 1
#             self.log.info("Setting dirty flag and calling force_redraw")
#             self.force_redraw()
#             return True
#         return False

#     def update_canvas_cursor(self, x, y, active_color=None):
#         """Update the cursor position and color from the main canvas."""
#         if x is None or y is None:
#             self.clear_cursor()
#             return

#         if not (0 <= x < self.pixels_across and 0 <= y < self.pixels_tall):
#             self.clear_cursor()
#             return

#         if active_color is not None:
#             self.cursor_color = active_color

#         old_pos = self.canvas_cursor_pos
#         self.canvas_cursor_pos = (x, y)

#         if old_pos != self.canvas_cursor_pos:
#             self.dirty = 1

#     def on_pixel_update_event(self, event, trigger):
#         """Handle pixel update events."""
#         if hasattr(trigger, "pixel_number"):
#             pixel_num = trigger.pixel_number
#             new_color = trigger.pixel_color
#             self.log.info(f"MiniView updating pixel {pixel_num} to color {new_color}")

#             self.pixels[pixel_num] = new_color
#             self.dirty_pixels[pixel_num] = True
#             self.dirty = 1

#     def force_redraw(self):
#         """Force a complete redraw of the miniview."""
#         self.log.info(f"Starting force_redraw with background color {self.background_color}")
#         self.image.fill(self.background_color)
#         pixel_width, pixel_height = self.pixels_per_pixel(self.pixels_across, self.pixels_tall)

#         # Draw all non-magenta pixels
#         for i, pixel in enumerate(self.pixels):
#             if pixel != (255, 0, 255):  # Skip magenta pixels
#                 x = (i % self.pixels_across) * pixel_width
#                 y = (i // self.pixels_across) * pixel_height
#                 pygame.draw.rect(
#                     self.image,
#                     pixel,
#                     (x, y, pixel_width, pixel_height)
#                 )

#         # # Only draw cursor if we have a valid position AND mouse is in canvas
#         # canvas = None
#         # for group in self.groups():
#         #     for sprite in group.sprites():
#         #         if isinstance(sprite, CanvasSprite):
#         #             canvas = sprite
#         #             break
#         #     if canvas:
#         #         break

#         # if (self.canvas_cursor_pos is not None and
#         #     canvas and
#         #     canvas.rect.collidepoint(pygame.mouse.get_pos())):
#         #     x = self.canvas_cursor_pos[0] * pixel_width
#         #     y = self.canvas_cursor_pos[1] * pixel_height
#         #     pygame.draw.rect(
#         #         self.image,
#         #         self.cursor_color,
#         #         (x, y, pixel_width, pixel_height),
#         #         1  # Border thickness
#         #     )

#         self.log.debug(f"MiniView force redraw complete with background {self.background_color}")

#     def update(self):
#         """Update the miniview display."""
#         # Get mouse position and window size

#         # Use existing attributes if they exist
#         if hasattr(self, "pixels_across") and hasattr(self, "pixels_tall"):
#             # Initialize pixels with magenta as the transparent/background color
#             self.pixels = [(255, 0, 255) for _ in range(self.pixels_across * self.pixels_tall)]
#             self.dirty_pixels = [True] * len(self.pixels)
#         self.background_color = (128, 128, 128)
#         self.active_color = (0, 0, 0)
#         self.border_thickness = 1

#         # Create initial surface
#         self.image = pygame.Surface((self.width, self.height))
#         self.rect = self.image.get_rect(x=self.x, y=self.y)

#         # Get screen dimensions from pygame
#         screen_info = pygame.display.Info()
#         screen_width = screen_info.current_w

#         # Calculate mini map size (2x2 pixels per sprite pixel)
#         pixel_width = 2  # MiniView uses 2x2 pixels per sprite pixel
#         mini_map_width = self.pixels_across * pixel_width

#         # Position mini map flush to the right edge and top
#         mini_map_x = screen_width - mini_map_width  # Flush to right edge
#         mini_map_y = 24  # Flush to top (below menu bar)

#         # Ensure mini map doesn't go off screen
#         if mini_map_x < 0:
#             mini_map_x = 20  # Fallback to left side if too wide

#         # Create miniview - position in top right corner
#         self.mini_view = MiniView(
#             pixels=self.pixels,
#             x=mini_map_x,
#             y=mini_map_y,
#             width=self.pixels_across,
#             height=self.pixels_tall,
#             groups=self.groups
#         )

#         # Add MiniView to the sprite groups explicitly
#         if self.groups:
#             if isinstance(self.groups, (list, tuple)):
#                 for group in self.groups:
#                     group.add(self.mini_view)
#             else:
#                 self.groups.add(self.mini_view)

#         # Force initial draw
#         self.dirty = 1
#         self.force_redraw()

#     def update(self):
#         """Update the canvas display."""
#         # Check if mouse is outside canvas
#         mouse_pos = pygame.mouse.get_pos()

#         # Get window size
#         screen_info = pygame.display.Info()
#         screen_rect = pygame.Rect(0, 0, screen_info.current_w, screen_info.current_h)

#         # If mouse is outside window or canvas, clear cursor
#         if ((not screen_rect.collidepoint(mouse_pos) or not self.rect.collidepoint(mouse_pos))
#             and hasattr(self, "mini_view")):
#             self.log.info("Mouse outside canvas/window, clearing miniview cursor")
#             self.mini_view.clear_cursor()

#         if self.dirty:
#             self.force_redraw()
#             self.dirty = 0

#     def force_redraw(self):
#         """Force a complete redraw of the canvas."""
#         self.image.fill(self.background_color)

#         # Draw all pixels, regardless of dirty state
#         for i, pixel in enumerate(self.pixels):
#             x = (i % self.pixels_across) * self.pixel_width
#             y = (i // self.pixels_across) * self.pixel_height
#             pygame.draw.rect(
#                 self.image,
#                 pixel,
#                 (x, y, self.pixel_width, self.pixel_height)
#             )
#             pygame.draw.rect(
#                 self.image,
#                 (64, 64, 64),
#                 (x, y, self.pixel_width, self.pixel_height),
#                 self.border_thickness
#             )
#             self.dirty_pixels[i] = False

#         self.log.debug(f"Canvas force redraw complete with {len(self.pixels)} pixels")

#     def on_left_mouse_button_down_event(self, event):
#         """Handle the left mouse button down event."""
#         if self.rect.collidepoint(event.pos):
#             x = (event.pos[0] - self.rect.x) // self.pixel_width
#             y = (event.pos[1] - self.rect.y) // self.pixel_height

#             # Check bounds to prevent IndexError
#             if 0 <= x < self.pixels_across and 0 <= y < self.pixels_tall:
#                 pixel_num = y * self.pixels_across + x
#                 self.pixels[pixel_num] = self.active_color
#                 self.dirty_pixels[pixel_num] = True
#                 self.dirty = 1

#             # Update miniview
#             if hasattr(self, "mini_view"):
#                 self.mini_view.on_pixel_update_event(event, self)

#     def on_left_mouse_drag_event(self, event, trigger):
#         """Handle mouse drag events."""
#         # For drag events, we treat them the same as button down
#         self.on_left_mouse_button_down_event(event)

#     def on_mouse_motion_event(self, event):
#         """Handle mouse motion events."""
#         if self.rect.collidepoint(event.pos):
#             # Convert mouse position to pixel coordinates
#             x = (event.pos[0] - self.rect.x) // self.pixel_width
#             y = (event.pos[1] - self.rect.y) // self.pixel_height

#             # Check if the coordinates are within valid range
#             if (0 <= x < self.pixels_across and 0 <= y < self.pixels_tall):
#                 if hasattr(self, "mini_view"):
#                     self.mini_view.update_canvas_cursor(x, y, self.active_color)
#             elif hasattr(self, "mini_view"):
#                 self.mini_view.clear_cursor()
#         elif hasattr(self, "mini_view"):
#             self.mini_view.clear_cursor()

#     def on_pixel_update_event(self, event, trigger):
#         """Handle pixel update events."""
#         if hasattr(trigger, "pixel_number"):
#             pixel_num = trigger.pixel_number
#             new_color = trigger.pixel_color
#             self.log.info(f"Canvas updating pixel {pixel_num} to color {new_color}")

#             self.pixels[pixel_num] = new_color
#             self.dirty_pixels[pixel_num] = True
#             self.dirty = 1

#             # Update miniview
#             self.mini_view.on_pixel_update_event(event, trigger)

#     def on_mouse_leave_window_event(self, event):
#         """Handle mouse leaving window event."""
#         self.log.info("Mouse left window, clearing miniview cursor")
#         if hasattr(self, "mini_view"):
#             self.mini_view.clear_cursor()

#     def on_mouse_enter_sprite_event(self, event):
#         """Handle mouse entering canvas."""
#         self.log.info("Mouse entered canvas")
#         if hasattr(self, "mini_view"):
#             # Update cursor position immediately
#             x = (event.pos[0] - self.rect.x) // self.pixel_width
#             y = (event.pos[1] - self.rect.y) // self.pixel_height
#             if 0 <= x < self.pixels_across and 0 <= y < self.pixels_tall:
#                 self.mini_view.update_canvas_cursor(x, y, self.active_color)

#     def on_mouse_exit_sprite_event(self, event):
#         """Handle mouse exiting canvas."""
#         self.log.info("Mouse exited canvas")
#         if hasattr(self, "mini_view"):
#             self.mini_view.clear_cursor()

#     def on_save_file_event(self: Self, filename: str) -> None:
#         """Handle save file events."""
#         self.log.info(f"Starting save to file: {filename}")
#         try:
#             self.save(filename=filename)
#         except (OSError, ValueError, KeyError):
#             self.log.exception("Error saving file")
#             raise

#     def on_load_file_event(self, event: pygame.event.Event, trigger: object = None) -> None:
#         """Handle load file event."""
#         self.log.debug("=== Starting on_load_file_event ===")
#         try:
#             filename = event if isinstance(event, str) else event.text
#             self.log.debug(f"Loading canvas from {filename}")

#             # Determine file format from extension
#             ext = Path(filename).suffix.lower()
#             if ext not in (".yml", ".yaml", ".ini"):
#                 self.log.error(f"Unsupported file format: {ext}. Use .yml, .yaml, or .ini")
#                 return

#             # Read the raw file content
#             with Path(filename).open("r") as f:
#                 content = f.read()
#             self.log.debug(f"Raw file content:\n{content}")

#             # Load based on format
#             if ext in (".yml", ".yaml"):
#                 # Load YAML format
#                 config = yaml.safe_load(content)
#                 self.log.debug("Loading YAML format")

#                 # Get color definitions from YAML format
#                 color_map = {}
#                 for char, color_def in config["colors"].items():
#                     color_map[char] = (
#                         color_def["red"],
#                         color_def["green"],
#                         color_def["blue"]
#                     )
#                 pixel_text = config["sprite"]["pixels"]

#             elif ext == ".ini":
#                 # Load INI format
#                 self.log.debug("Loading INI format")
#                 config = configparser.RawConfigParser()
#                 config.read_string(content)

#                 # Get color definitions from INI format
#                 color_map = {}
#                 for section in config.sections():
#                     if len(section) == 1:  # Color sections are single characters
#                         color_map[section] = (
#                             config.getint(section, "red"),
#                             config.getint(section, "green"),
#                             config.getint(section, "blue")
#                         )
#                 pixel_text = config.get("sprite", "pixels", raw=True)

#             # Process pixel data
#             rows = [row.strip() for row in pixel_text.splitlines() if row.strip()]

#             # Validate dimensions
#             width = len(rows[0])
#             height = len(rows)

#             # Check that all rows have the same width
#             for i, row in enumerate(rows):
#                 if len(row) != width:
#                     raise ValueError(
#                         f"Row {i} has width {len(row)} but expected {width}. "
#                         f"All rows must have the same width. "
#                         f"Row {i}: '{row}'"
#                     )

#             if width != self.pixels_across or height != self.pixels_tall:
#                 raise ValueError(
#                     f"Image dimensions {width}x{height} don't match canvas "
#                     f"{self.pixels_across}x{self.pixels_tall}"
#                 )

#             # Update canvas pixels
#             for y, row in enumerate(rows):
#                 for x, char in enumerate(row):
#                     if char in color_map:
#                         pixel_num = y * self.pixels_across + x
#                         self.pixels[pixel_num] = color_map[char]
#                         self.dirty_pixels[pixel_num] = True

#             # Force redraw
#             self.dirty = 1
#             self.force_redraw()

#             # Update miniview if it exists
#             if hasattr(self, "mini_view"):
#                 self.mini_view.dirty = 1
#                 self.mini_view.force_redraw()

#         except Exception:
#             self.log.exception("Error loading file")
#             raise

#     def on_new_file_event(self, event: pygame.event.Event, trigger: object = None) -> None:
#         """Handle new file event.

#         Args:
#             event (pygame.event.Event): The event to handle
#             trigger (object, optional): The trigger object. Defaults to None.

#         """
#         dimensions = event if isinstance(event, str) else event.text
#         self.log.info(f"CanvasSprite.on_new_file_event called with dimensions: {dimensions}")
#         self.log.info(f"Current canvas size: {self.pixels_across}x{self.pixels_tall}")
#         try:
#             width, height = map(int, dimensions.lower().split("x"))
#             self.log.info(f"Parsed dimensions: {width}x{height}")

#             # Resize the canvas
#             self.log.info(f"Setting pixels_across to {width}")
#             self.pixels_across = width
#             self.log.info(f"Setting pixels_tall to {height}")
#             self.pixels_tall = height

#             # Clear and resize the canvas
#             new_pixel_count = width * height
#             self.log.info(f"Creating {new_pixel_count} pixels")
#             self.pixels = [(255, 0, 255)] * new_pixel_count  # Use magenta as background
#             self.dirty_pixels = [True] * len(self.pixels)

#             # Update canvas dimensions and redraw
#             self.log.info("Calling self.update()")
#             self.update()
#             self.dirty = 1

#             self.log.info(
#                 f"Canvas resized to {width}x{height}, new pixel count: {len(self.pixels)}"
#             )

#         except ValueError:
#             self.log.exception(f"Invalid dimensions format '{dimensions}'")
#             self.log.exception("Expected format: WxH (e.g., '32x32')")
#         except (OSError, KeyError, AttributeError):
#             self.log.exception("Unexpected error in on_new_file_event")

#     def save(self, filename: str, format: str = None) -> None:
#         """Save sprite to a file.

#         Args:
#             filename (str): The filename to save to
#             format (str, optional): Format to save in ('yaml' or 'ini').
#                                   If None, determined by file extension.

#         """
#         try:
#             # Determine format from extension if not specified
#             if format is None:
#                 ext = Path(filename).suffix.lower()
#                 if ext in (".yml", ".yaml"):
#                     format = "yaml"
#                 elif ext == ".ini":
#                     format = "ini"
#                 else:
#                     raise ValueError(f"Unsupported file format: {ext}. Use .yml, .yaml, or .ini")

#             # Get the sprite data
#             pixel_data = self.deflate()

#             if format == "yaml":
#                 # Convert to YAML format
#                 yaml_data = {
#                     "colors": {},
#                     "sprite": {
#                         "name": pixel_data["sprite"]["name"],
#                         "pixels": "\n" + pixel_data["sprite"]["pixels"]  # Add leading newline
#                     }
#                 }

#                 # Convert color data to YAML format
#                 for char, rgb in pixel_data["colors"].items():
#                     yaml_data["colors"][char] = {
#                         "blue": rgb[2],
#                         "green": rgb[1],
#                         "red": rgb[0]
#                     }

#                 # Write YAML file
#                 with Path(filename).open("w") as f:
#                     yaml.dump(yaml_data, f, sort_keys=False, default_flow_style=False)

#             elif format == "ini":
#                 config = configparser.ConfigParser(
#                     dict_type=collections.OrderedDict,
#                     empty_lines_in_values=True,
#                     strict=True
#                 )

#                 # Add sprite section
#                 config["sprite"] = {
#                     "name": pixel_data["sprite"]["name"],
#                     "pixels": pixel_data["sprite"]["pixels"]
#                 }

#                 # Add color sections
#                 for char, rgb in pixel_data["colors"].items():
#                     config[char] = {
#                         "red": str(rgb[0]),
#                         "green": str(rgb[1]),
#                         "blue": str(rgb[2])
#                     }

#                 # Write INI file
#                 with Path(filename).open("w") as f:
#                     config.write(f)

#             else:
#                 raise ValueError(f"Unsupported format: {format}. Must be 'yaml' or 'ini'")

#             self.log.info(f"Saved sprite to {filename} in {format} format")

#         except Exception:
#             self.log.exception("Error saving file")
#             raise

#     def deflate(self) -> dict:
#         """Deflate sprite data to dictionary format."""
#         try:
#             self.log.debug(f"Starting deflate for {self.name}")
#             self.log.debug(f"Image dimensions: {self.image.get_size()}")

#             config = configparser.ConfigParser(
#                 dict_type=collections.OrderedDict, empty_lines_in_values=True, strict=True
#             )

#             # Get the raw pixel data and log its size
#             pixel_string = pygame.image.tostring(self.image, "RGB")
#             self.log.debug(f"Raw pixel string length: {len(pixel_string)}")

#             # Log the first few bytes of pixel data
#             self.log.debug(f"First 12 bytes of pixel data: {list(pixel_string[:12])}")

#             # Create the generator and log initial state
#             raw_pixels = rgb_triplet_generator(pixel_data=pixel_string)
#             self.log.debug("Created RGB triplet generator")

#             # Try to get the first triplet
#             try:
#                 first_triplet = next(raw_pixels)
#                 self.log.debug(f"First RGB triplet: {first_triplet}")
#                 # Reset generator
#                 raw_pixels = rgb_triplet_generator(pixel_data=pixel_string)
#             except StopIteration:
#                 self.log.exception("Generator empty on first triplet!")
#                 raise

#             # Now proceed with the rest of deflate
#             raw_pixels = list(raw_pixels)
#             self.log.debug(f"Converted {len(raw_pixels)} RGB triplets to list")

#             # Continue with original deflate code...
#             colors = set(raw_pixels)
#             self.log.debug(f"Found {len(colors)} unique colors")

#             return config

#         except Exception:
#             self.log.exception("Error in deflate")
#             raise

#         # Clear cursor if mouse is outside window
#         if not screen_rect.collidepoint(mouse_pos):
#             self.clear_cursor()

#         if self.dirty:
#             self.force_redraw()
#             self.dirty = 0

#     def clear_cursor(self):
#         """Clear the cursor and force a redraw."""
#         if self.canvas_cursor_pos is not None:
#             self.log.info("Clearing miniview cursor")
#             self.canvas_cursor_pos = None
#             self.dirty = 1
#             self.force_redraw()

#     @staticmethod
#     def pixels_per_pixel(pixels_across: int, pixels_tall: int) -> tuple[int, int]:
#         """Calculate the size of each pixel in the miniview."""
#         # Calculate pixel size based on available space and canvas dimensions
#         # For now, use a simple calculation that ensures the mini view fits
#         # You could make this more sophisticated based on screen size
#         max_pixel_size = min(4, max(1, 64 // max(pixels_across, pixels_tall)))
#         return (max_pixel_size, max_pixel_size)


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
        raise ImportError("aisuite not available")

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
        
        # Try to get model info through a simple test request
        test_messages = [
            {
                "role": "user", 
                "content": "What is your maximum token output limit? Please respond with just the number."
            }
        ]
        
        log.info("Querying model capabilities...")
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=test_messages,
            max_tokens=100  # Small response for capability query
        )
        
        if hasattr(response, 'choices') and response.choices:
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
        
    except Exception as e:
        log.error(f"Failed to query model capabilities: {e}")
        return {"max_tokens": None}


def _process_ai_request(request: AIRequest, client, log: logging.Logger) -> AIResponse:
    """Process a single AI request."""
    log.info("Making API call to AI service...")
    response = client.chat.completions.create(
        model=AI_MODEL, 
        messages=request.messages,
        max_tokens=AI_MAX_TOKENS
    )

    log.info("AI response received from API")
    return _extract_response_content(response, log)


def _select_relevant_training_examples(user_request: str, max_examples: int = AI_MAX_TRAINING_EXAMPLES) -> list:
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
        if any(keyword in user_lower for keyword in ["animated", "animation", "frame"]):
            if sprite_type == "animated":
                score += 10
        if any(keyword in user_lower for keyword in ["static", "single", "one"]):
            if sprite_type == "static":
                score += 10
                
        # Check for name similarity
        if any(word in name for word in user_lower.split()):
            score += 5
            
        scored_examples.append((score, example))
    
    # Sort by score and take top examples
    scored_examples.sort(key=lambda x: x[0], reverse=True)
    relevant_examples = [example for _, example in scored_examples[:max_examples]]
    
    # Fill remaining slots with random examples if needed
    if len(relevant_examples) < max_examples:
        remaining = [ex for ex in AI_TRAINING_DATA if ex not in relevant_examples]
        relevant_examples.extend(remaining[:max_examples - len(relevant_examples)])
    
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


class LivePreviewSprite(BitmappySprite):
    """A sprite that displays the current frame of an animated sprite in real-time."""

    def __init__(
        self,
        animated_sprite: AnimatedSprite,
        name: str = "Live Preview",
        x: int = 0,
        y: int = 0,
        groups: pygame.sprite.Group = None,
    ):
        # Initialize with BitmappySprite (64x64 for preview)
        super().__init__(
            name=name,
            x=x,
            y=y,
            width=64,
            height=64,
            groups=groups,
        )
        self.animated_sprite = animated_sprite
        self.log = logging.getLogger("game.bitmappy.live_preview")

        # Create a surface that's always dirty for real-time updates
        self.image = pygame.Surface((64, 64))  # Fixed size for preview
        self.image.fill((255, 0, 0))  # Red background so we can see it
        self.rect = self.image.get_rect(x=x, y=y)
        self.dirty = 2  # Always dirty for real-time updates

        # Set initial frame
        self._update_frame()

    def _update_frame(self, animated_sprite=None):
        """Update the preview with the current frame of the animated sprite."""
        self.log.debug("LivePreviewSprite._update_frame called")

        # Use the provided animated sprite if available, otherwise use self.animated_sprite
        sprite_to_use = animated_sprite if animated_sprite is not None else self.animated_sprite

        if sprite_to_use and hasattr(sprite_to_use, "frames"):
            # Get the current animation and frame from the animated sprite
            current_animation = sprite_to_use.current_animation
            frame_index = sprite_to_use.current_frame

            self.log.debug(
                f"LivePreviewSprite._update_frame: Animation: {current_animation}, Frame: {frame_index}"
            )

            # Check if frame has changed
            if not hasattr(self, "_last_frame_index") or self._last_frame_index != frame_index:
                self.log.debug(f"=== LIVE PREVIEW FRAME TRANSITION DETECTED ===")
                self.log.debug(f"Previous frame: {getattr(self, '_last_frame_index', 'None')}")
                self.log.debug(f"Current frame: {frame_index}")
                self.log.debug(f"Animation: {current_animation}")

                self._last_frame_index = frame_index

                if current_animation in sprite_to_use.frames:
                    # Get the current frame and create a fresh surface from its pixel data
                    frame = sprite_to_use.frames[current_animation][frame_index]
                    if hasattr(frame, "get_pixel_data"):
                        frame_pixels = frame.get_pixel_data()
                        # Create a fresh surface from the pixel data
                        frame_size = frame.get_size()
                        current_surface = pygame.Surface(frame_size)

                        # Draw each pixel to the surface
                        for i, pixel in enumerate(frame_pixels):
                            x = i % frame_size[0]
                            y = i // frame_size[0]
                            current_surface.set_at((x, y), pixel)

                        self.log.debug(
                            f"Created fresh surface from frame {frame_index} with {len(frame_pixels)} pixels"
                        )

                        if current_surface:
                            # Scale the frame to fit the preview size (64x64)
                            scaled_frame = pygame.transform.scale(current_surface, (64, 64))
                            self.image = scaled_frame
                            self.dirty = 1  # Only dirty when frame changes
                            self.log.debug(f"Live preview updated with frame {frame_index}")
                        else:
                            self.log.debug("Failed to create surface from frame data")
                    else:
                        self.log.debug("Frame has no get_pixel_data method")
                else:
                    self.log.debug(f"Animation {current_animation} not found in frames")

                self.log.debug(f"=== END FRAME TRANSITION ===")
            else:
                self.log.debug(f"Frame {frame_index} unchanged, skipping update")
        else:
            self.log.debug("No animated sprite or _animations attribute")

    def update(self):
        """Update the preview frame."""
        self.log.debug("LivePreviewSprite.update called")
        self._update_frame()
        # dirty is set in _update_frame() only when frame changes
        self.log.debug("LivePreviewSprite.update completed")

    def force_redraw(self):
        """Force a redraw of the preview."""
        self._update_frame()
        return self.image

    def _update_frame_from_canvas(self, canvas):
        """Update the preview with the canvas's current frame directly."""
        self.log.debug("LivePreviewSprite._update_frame_from_canvas called")

        # Get the canvas's current frame data
        current_animation = canvas.current_animation
        current_frame = canvas.current_frame

        self.log.debug(
            f"LivePreviewSprite._update_frame_from_canvas: Animation: {current_animation}, Frame: {current_frame}"
        )

        # Get the frame from the canvas's animated sprite
        if current_animation in canvas.animated_sprite.frames and current_frame < len(
            canvas.animated_sprite.frames[current_animation]
        ):
            frame = canvas.animated_sprite.frames[current_animation][current_frame]

            if hasattr(frame, "get_pixel_data"):
                frame_pixels = frame.get_pixel_data()
                # Create a fresh surface from the pixel data
                frame_size = frame.get_size()
                current_surface = pygame.Surface(frame_size)

                # Draw each pixel to the surface
                for i, pixel in enumerate(frame_pixels):
                    x = i % frame_size[0]
                    y = i // frame_size[0]
                    current_surface.set_at((x, y), pixel)

                if current_surface:
                    # Scale the frame to fit the preview size (64x64)
                    scaled_frame = pygame.transform.scale(current_surface, (64, 64))
                    self.image = scaled_frame
                    self.dirty = 1
                    self.log.debug(f"Live preview updated with canvas frame {current_frame}")
                else:
                    self.log.debug("Failed to create surface from canvas frame data")
            else:
                self.log.debug("Canvas frame has no get_pixel_data method")
        else:
            self.log.debug(
                f"Canvas frame {current_frame} not found in animation {current_animation}"
            )


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
        # Calculate dimensions first
        self.pixels_across = pixels_across
        self.pixels_tall = pixels_tall
        self.pixel_width = pixel_width
        self.pixel_height = pixel_height
        width = self.pixels_across * self.pixel_width
        height = pixels_tall * pixel_height

        # Initialize parent class first to create rect
        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            groups=groups,
        )

        # Store animated sprite and current frame info
        self.animated_sprite = animated_sprite
        self.current_animation = (
            next(iter(animated_sprite.frames.keys())) if animated_sprite.frames else "idle"
        )
        # Sync the canvas frame with the animated sprite's current frame
        self.current_frame = animated_sprite.current_frame
        self.log.debug(
            f"Canvas initialized - animated_sprite.current_frame={animated_sprite.current_frame}, canvas.current_frame={self.current_frame}"
        )

        # Initialize manual frame selection flag to allow automatic animation updates
        self._manual_frame_selected = False

        # Store pixel-related attributes
        self.pixels_across = pixels_across
        self.pixels_tall = pixels_tall
        self.pixel_width = pixel_width
        self.pixel_height = pixel_height

        # Initialize pixels with magenta as the transparent/background color
        self.pixels = [(255, 0, 255) for _ in range(self.pixels_across * self.pixels_tall)]
        self.dirty_pixels = [True] * len(self.pixels)
        self.background_color = (128, 128, 128)
        self.active_color = (0, 0, 0)
        self.border_thickness = 1

        # Create initial surface
        self.image = pygame.Surface((self.width, self.height))
        self.rect = self.image.get_rect(x=x, y=y)

        # Initialize interface components for animated sprites
        self.canvas_interface = AnimatedCanvasInterface(self)
        # Sync the canvas interface with the canvas's current frame
        self.canvas_interface.set_current_frame(self.current_animation, self.current_frame)
        self.sprite_serializer = AnimatedSpriteSerializer()
        self.canvas_renderer = AnimatedCanvasRenderer(self)

        # Create film strip widget
        self.film_strip = FilmStripWidget(x=0, y=self.rect.bottom + 10, width=800, height=100)
        self.film_strip.set_animated_sprite(animated_sprite)

        # Get screen dimensions from pygame
        screen_info = pygame.display.Info()
        screen_width = screen_info.current_w

        # Calculate mini map size using the same logic as MiniView
        pixel_width, pixel_height = MiniView.pixels_per_pixel(self.pixels_across, self.pixels_tall)
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
            # Use the canvas's current animation and frame (not the animated sprite's)
            current_animation = self.current_animation
            current_frame = self.current_frame
            if current_animation in self.animated_sprite.frames and current_frame < len(
                self.animated_sprite.frames[current_animation]
            ):
                frame = self.animated_sprite.frames[current_animation][current_frame]
                if hasattr(frame, "get_pixel_data"):
                    return frame.get_pixel_data()
        # Fallback to static pixels
        return self.pixels.copy()

    def _update_canvas_from_current_frame(self) -> None:
        """Update the canvas pixels with the current frame data."""
        if hasattr(self, "animated_sprite") and self.animated_sprite:
            # Use the canvas's current animation and frame (not the animated sprite's)
            current_animation = self.current_animation
            current_frame = self.current_frame
            if current_animation in self.animated_sprite.frames and current_frame < len(
                self.animated_sprite.frames[current_animation]
            ):
                frame = self.animated_sprite.frames[current_animation][current_frame]
                if hasattr(frame, "get_pixel_data"):
                    self.pixels = frame.get_pixel_data()
                    self.dirty_pixels = [True] * len(self.pixels)
                    self.log.debug(f"Updated canvas pixels from frame {current_frame}")

    def _update_mini_view_from_current_frame(self) -> None:
        """Update the mini view with pixel data from the current frame."""
        if hasattr(self, "mini_view"):
            current_frame_pixels = self._get_current_frame_pixels()
            self.mini_view.pixels = current_frame_pixels
            self.mini_view.dirty_pixels = [True] * len(current_frame_pixels)
            self.mini_view.dirty = 1

    def set_frame(self, frame_index: int) -> None:
        """Set the current frame index for the current animation."""
        if hasattr(self, "animated_sprite") and self.animated_sprite:
            frames = self.animated_sprite._animations
            if self.current_animation in frames and 0 <= frame_index < len(
                frames[self.current_animation]
            ):
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

                # Restart animation immediately from the beginning
                self.animated_sprite.play()
                self._manual_frame_selected = False

                self.dirty = 1
                self.log.debug(
                    f"Set frame to {frame_index} for animation '{self.current_animation}' (animation paused)"
                )

    def show_frame(self, animation: str, frame: int) -> None:
        """Show a specific frame of the animated sprite."""
        frames = self.animated_sprite._animations
        if animation in frames and 0 <= frame < len(frames[animation]):
            self.current_animation = animation
            self.current_frame = frame

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

                # Update live preview when animation state changes
                if hasattr(self, "live_preview") and self.live_preview is not None:
                    # Force live preview to update by clearing its frame tracking
                    if hasattr(self.live_preview, "_last_frame_index"):
                        delattr(self.live_preview, "_last_frame_index")

                    # Force the live preview to show the canvas's current frame directly
                    self.live_preview._update_frame_from_canvas(self)
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

            # Update live preview to reflect the changes
            if hasattr(self, "live_preview") and self.live_preview is not None:
                # Force live preview to update by clearing its frame tracking
                if hasattr(self.live_preview, "_last_frame_index"):
                    delattr(self.live_preview, "_last_frame_index")

                # Temporarily set the animated sprite to the canvas's current frame for the preview
                original_frame = self.animated_sprite.current_frame
                self.animated_sprite.set_frame(self.current_frame)
                self.live_preview._update_frame(animated_sprite=self.animated_sprite)
                # Restore the original frame
                self.animated_sprite.set_frame(original_frame)

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
            # Use the interface-based save method
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
            self.log.debug(f"Loading animated sprite from {filename}")

            # Load the animated sprite using the sprite serializer

            # Detect file format and load the sprite
            file_format = detect_file_format(filename)
            self.log.debug(f"Detected file format: {file_format}")

            # Create a new animated sprite and load it
            loaded_sprite = AnimatedSprite()
            loaded_sprite.load(filename)

            # Update our animated sprite with the loaded data
            self.animated_sprite = loaded_sprite

            # Update the canvas sprite's current animation to match the loaded sprite
            self.current_animation = loaded_sprite.current_animation

            # Debug: Print available animations
            available_animations = (
                list(loaded_sprite.frames.keys()) if hasattr(loaded_sprite, "frames") else []
            )
            self.log.info(f"AVAILABLE ANIMATIONS: {available_animations}")
            self.log.info(f"CURRENT CANVAS ANIMATION: '{self.current_animation}'")

            # Update the current frame display
            if hasattr(self, "mini_view"):
                self._update_mini_view_from_current_frame()

            # Update the live preview to reference the new animated sprite
            if hasattr(self, "live_preview") and self.live_preview is not None:
                self.log.debug(f"Updating live preview with new animated sprite: {loaded_sprite}")
                self.live_preview.animated_sprite = loaded_sprite
                self.live_preview._update_frame()
                self.log.debug("Updated live preview with new animated sprite")

            # Start the animation after loading
            if loaded_sprite.current_animation:
                loaded_sprite.play()
                self.log.debug(
                    f"Started animation '{loaded_sprite.current_animation}' using play() method"
                )

            # Force a complete redraw
            self.dirty = 1
            self.force_redraw()

            self.log.info(f"Successfully loaded animated sprite from {filename}")

        except Exception:
            self.log.exception("Error in on_load_file_event for animated sprite")
            raise


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

        # # Only draw cursor if we have a valid position AND mouse is in canvas
        # canvas = None
        # for group in self.groups():
        #     for sprite in group.sprites():
        #         if isinstance(sprite, CanvasSprite):
        #             canvas = sprite
        #             break
        #     if canvas:
        #         break

        # if (self.canvas_cursor_pos is not None and
        #     canvas and
        #     canvas.rect.collidepoint(pygame.mouse.get_pos())):
        #     x = self.canvas_cursor_pos[0] * pixel_width
        #     y = self.canvas_cursor_pos[1] * pixel_height
        #     pygame.draw.rect(
        #         self.image,
        #         self.cursor_color,
        #         (x, y, pixel_width, pixel_height),
        #         1  # Border thickness
        #     )

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
    def pixels_per_pixel(pixels_across: int, pixels_tall: int) -> tuple[int, int]:
        """Calculate the size of each pixel in the miniview."""
        # Calculate pixel size based on available space and canvas dimensions
        # For now, use a simple calculation that ensures the mini view fits
        # You could make this more sophisticated based on screen size
        max_pixel_size = min(4, max(1, 64 // max(pixels_across, pixels_tall)))
        return (max_pixel_size, max_pixel_size)


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

        # Create a simple animated sprite for testing
        # Create test frames
        surface1 = pygame.Surface((pixels_across, pixels_tall))
        surface1.fill((255, 0, 255))  # Magenta frame (transparent)
        frame1 = SpriteFrame(surface1)
        frame1.pixels = [(255, 0, 255)] * (pixels_across * pixels_tall)

        surface2 = pygame.Surface((pixels_across, pixels_tall))
        surface2.fill((255, 0, 255))  # Magenta frame (transparent)
        frame2 = SpriteFrame(surface2)
        frame2.pixels = [(255, 0, 255)] * (pixels_across * pixels_tall)

        # Create animated sprite using proper initialization
        animated_sprite = AnimatedSprite()
        # Use the proper method to set up animations
        animated_sprite._animations = {"idle": [frame1, frame2]}
        animated_sprite._current_animation = "idle"
        animated_sprite._current_frame = 0
        animated_sprite._frame_interval = 0.5
        animated_sprite._is_looping = True  # Enable looping for the animation

        # Initialize the sprite properly like a loaded sprite would be
        animated_sprite._update_surface_and_mark_dirty()

        # Start in a paused state initially
        animated_sprite.pause()

        # Don't start animation immediately - let the scene handle it

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

        # Create a live preview surface in the center of the screen
        try:
            self.log.debug(f"Creating LivePreviewSprite with all_sprites: {self.all_sprites}")
            self.live_preview = LivePreviewSprite(
                animated_sprite=animated_sprite,
                name="Live Preview",
                x=400,  # Center of screen
                y=220,  # Moved up 80 pixels from center
                groups=self.all_sprites,
            )
            self.log.info(
                f"LivePreviewSprite created at position ({self.live_preview.rect.x}, {self.live_preview.rect.y})"
            )

            # Force initial update of the live preview to show frame 0
            self.log.debug(
                f"Live preview initialization - animated_sprite.current_frame={animated_sprite.current_frame}"
            )

            # Ensure the live preview uses the same animated sprite as the canvas
            self.live_preview.animated_sprite = animated_sprite

            # Force the live preview to update by clearing its frame tracking
            if hasattr(self.live_preview, "_last_frame_index"):
                delattr(self.live_preview, "_last_frame_index")

            # Update the live preview to show the current frame
            self.log.debug(
                f"Before live preview update - canvas.current_frame={self.canvas.current_frame}, animated_sprite.current_frame={animated_sprite.current_frame}"
            )

            # Force the animated sprite to match the canvas's current frame
            animated_sprite.set_frame(self.canvas.current_frame)

            # Create a temporary animated sprite that uses the canvas's current frame
            temp_animated_sprite = AnimatedSprite()
            temp_animated_sprite._animations = animated_sprite._animations.copy()
            temp_animated_sprite._current_animation = self.canvas.current_animation
            temp_animated_sprite._current_frame = self.canvas.current_frame
            temp_animated_sprite._frame_interval = animated_sprite._frame_interval

            self.live_preview._update_frame(animated_sprite=temp_animated_sprite)
            self.log.debug(
                f"After live preview update - live_preview._last_frame_index={getattr(self.live_preview, '_last_frame_index', 'None')}"
            )
        except Exception as e:
            self.log.warning(f"Cannot create LivePreviewSprite: {type(e).__name__}: {e}")
            self.log.exception("Full traceback for LivePreviewSprite creation error:")
            self.live_preview = None

        # Start the animation after everything is set up
        animated_sprite.play()

        width, height = options.get("size").split("x")
        CanvasSprite.WIDTH = int(width)
        CanvasSprite.HEIGHT = int(height)

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
        except Exception as e:
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

    # def on_menu_item_event(self, event: pygame.event.Event) -> None:
    #     """Handle the menu item event.

    #     Args:
    #         event (pygame.event.Event): The pygame event.
    #         trigger (object): The trigger object.

    #     Returns:
    #         None
    #     """
    #     self.log.info(f'Scene got menu item event: {event}')

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
                    I understand. I will provide ONLY raw TOML content without any
                    markdown formatting, code blocks, or explanations. The TOML format
                    will include:
                        - [sprite] section containing name and pixels (using block strings)
                        - [colors.0] through [colors.7] for color definitions
                        - RGB values from 0-255 for each color
                        - Pixels using the SPRITE_GLYPHS character set
                        - For animated sprites: [[animation]] and [[animation.frame]] sections
                        - When "frame", "animation", "animated", "2-frame", or "multi-frame"
                          is mentioned, I will create an ANIMATED sprite with multiple frames
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
        self.log.info(f"Using {len(relevant_examples)} training examples (max: {AI_MAX_TRAINING_EXAMPLES})")
        
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": f"""
                    You are a helpful assistant in a bitmap editor that can create
                    game content for game developers. You can create both static
                    single-frame sprites and animated multi-frame sprites.

                    Available character set for sprite pixels: {SPRITE_GLYPHS.strip()}
                """.strip(),
            },
            {
                "role": "user",
                "content": f"""
                            Here are some example sprites that I've created. Use these
                            as training data to understand how to create new sprites:

                            {"\n".join([str(data) for data in relevant_examples])}

                            Available character set: {SPRITE_GLYPHS.strip()}
                        """.strip(),
            },
            {
                "role": "assistant",
                "content": f"""
                    Thank you for providing those sprite examples. I understand
                    that each sprite consists of:

                    1. A name
                    2. A pixel layout using characters from: {SPRITE_GLYPHS.strip()}
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
                "content": (
                    f"{text.strip()} (current dimensions: "
                    f"{self.canvas.pixels_across}x{self.canvas.pixels_tall})"
                ),
            },
        ]

        try:
            # Create unique request ID
            request_id = str(time.time())

            # # Combine original prompt with training messages
            # full_prompt = messages

            # messages.append({
            #     "role": "user",
            #     "content": full_prompt
            # })

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

    def _load_ai_sprite(self, request_id: str, content: str) -> None:
        """Load sprite from AI content using SpriteFactory APIs."""
        self.log.info(f"AI response received, content length: {len(content)}")

        # Debug: Dump the sprite content
        self.log.info("=== AI GENERATED SPRITE CONTENT ===")
        self.log.info(
            f"Content preview (first {CONTENT_PREVIEW_LENGTH} chars):\n"
            f"{content[:CONTENT_PREVIEW_LENGTH]}"
        )
        if len(content) > CONTENT_PREVIEW_LENGTH:
            self.log.info(f"... (content continues, total length: {len(content)})")
        self.log.info("=== END SPRITE CONTENT ===")

        # Clean up any markdown formatting from AI response
        cleaned_content = self._clean_ai_response(content)

        # Determine file extension based on training format
        file_extension = f".{AI_TRAINING_FORMAT}" if AI_TRAINING_FORMAT else ".toml"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=file_extension, delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(cleaned_content)
            tmp_path = tmp.name
            self.log.info(f"Saved AI response to temp file: {tmp_path}")

        # Detect sprite type and create appropriate canvas
        try:
            self.log.info("Detecting AI sprite type...")

            # Use SpriteFactory to detect the sprite type
            sprite = SpriteFactory.load_sprite(filename=tmp_path)
            is_animated = hasattr(sprite, "frames") and sprite.frames
            self.log.info(f"AI sprite type: {'Animated' if is_animated else 'Static'}")

            if is_animated:
                # For animated sprites, use the existing animated canvas load method
                self.log.info("Loading animated sprite into existing animated canvas...")

                class MockEvent:
                    def __init__(self, text):
                        self.text = text

                mock_event = MockEvent(tmp_path)
                self.canvas.on_load_file_event(mock_event)

                self.log.info("AI animated sprite loaded successfully")
            else:
                # For static sprites, we need to create a new static canvas
                # because the current canvas is always animated
                self.log.info("Creating new static canvas for AI static sprite...")

                # Create a new static canvas
                new_canvas = CanvasSprite(
                    name="Static Canvas",
                    x=self.canvas.rect.x,
                    y=self.canvas.rect.y,
                    pixels_across=self.canvas.pixels_across,
                    pixels_tall=self.canvas.pixels_tall,
                    pixel_width=self.canvas.pixel_width,
                    pixel_height=self.canvas.pixel_height,
                    groups=self.all_sprites,
                )

                # Replace the current canvas with the new static canvas
                self.canvas.kill()  # Remove old canvas from groups
                self.canvas = new_canvas

                # Load the static sprite into the new canvas
                class MockEvent:
                    def __init__(self, text):
                        self.text = text

                mock_event = MockEvent(tmp_path)
                self.canvas.on_load_file_event(mock_event)

                # Update mini map to show the new AI sprite
                if hasattr(self.canvas, "mini_view"):
                    # For static canvas, update mini view with current pixels
                    self.canvas.mini_view.pixels = self.canvas.pixels.copy()
                    self.canvas.mini_view.dirty_pixels = [True] * len(self.canvas.pixels)
                    self.canvas.mini_view.dirty = 1

                # Force canvas redraw to show the new sprite
                self.canvas.dirty = 1
                self.canvas.force_redraw()

                self.log.info("AI static sprite loaded successfully into new static canvas")

            if hasattr(self, "debug_text"):
                self.debug_text.text = "AI sprite loaded successfully"

        except Exception as sprite_error:
            self.log.exception("Failed to load AI sprite")
            if hasattr(self, "debug_text"):
                self.debug_text.text = f"Error loading AI sprite: {sprite_error}"
        # Note: Temp file is kept for debugging - remove this comment when done debugging

    def _clean_ai_response(self, content: str) -> str:
        """Clean up markdown formatting from AI response."""
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
            # Pass delta time to the canvas for animation updates
            self.canvas.update_animation(self.dt)

            # Check for frame transitions
            frame_index = self.canvas.animated_sprite.current_frame

            if (
                not hasattr(self, "_last_animation_frame")
                or self._last_animation_frame != frame_index
            ):
                self._last_animation_frame = frame_index

                # Don't update the canvas frame - it should stay on the frame being edited
                # Only the live preview should animate

                # Update live preview on frame transition
                # Pass the canvas's animated sprite to ensure they're in sync
                if hasattr(self, "live_preview") and self.live_preview is not None:
                    self.live_preview._update_frame(animated_sprite=self.canvas.animated_sprite)

                # Don't update the canvas - it should stay on the current frame being edited
                # Only the live preview should animate

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

    # Set up signal handling to prevent multiprocessing issues on macOS
    def signal_handler(signum):
        """Handle shutdown signals gracefully."""
        LOG.info(f"Received signal {signum}, shutting down gracefully...")
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Set multiprocessing start method to avoid macOS issues
    with contextlib.suppress(RuntimeError):
        multiprocessing.set_start_method("spawn", force=True)

    icon_path = Path(__file__).parent / "resources" / "bitmappy.png"

    GameEngine(game=BitmapEditorScene, icon=icon_path).start()


if __name__ == "__main__":
    main()
