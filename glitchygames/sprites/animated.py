"""Animated sprite classes for GlitchyGames.

This module contains the animated sprite implementation that extends the
basic sprite functionality to support multi-frame animations with flexible
timing and playback control.
"""

import abc
import hashlib
import logging
from pathlib import Path
from typing import Self

import pygame
import toml

# YAML support removed - TOML only
# Import constants
from .constants import DEFAULT_FILE_FORMAT, SPRITE_GLYPHS

# Import detect_file_format function
try:
    from glitchygames.tools.bitmappy import detect_file_format
except ImportError:
    # Fallback if bitmappy module is not available
    def detect_file_format(_filename: str) -> str:
        """Detect file format based on extension.

        Currently only supports TOML format. To add new formats:
        1. Add file extension detection here
        2. Add analysis method in _analyze_file()
        3. Add save/load methods in AnimatedSprite
        4. Update tests
        See LOADER_README.md for detailed implementation guide.
        """
        # TODO: Add new format detection here
        # if filename.lower().endswith(".json"):
        #     return "json"
        # if filename.lower().endswith(".xml"):
        #     return "xml"

        return "toml"  # Default to TOML only


# Import BitmappySprite for static sprite saving
try:
    from glitchygames.sprites import BitmappySprite
except ImportError:
    BitmappySprite = None


LOG = logging.getLogger("game.sprites.animated")

# Constants
PIXEL_ARRAY_SHAPE_DIMENSIONS = 3


class FrameManager:
    """Centralized frame state management for animation system."""

    def __init__(self, animated_sprite):
        """Initialize with reference to the animated sprite."""
        self.animated_sprite = animated_sprite
        self._current_animation = ""
        self._current_frame = 0
        self._observers = []  # Components that need to be notified of frame changes

    def add_observer(self, observer):
        """Add an observer that will be notified of frame changes."""
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer):
        """Remove an observer."""
        if observer in self._observers:
            self._observers.remove(observer)

    def notify_observers(self, change_type, old_value, new_value):
        """Notify all observers of a frame change."""
        for observer in self._observers:
            if hasattr(observer, "on_frame_change"):
                observer.on_frame_change(change_type, old_value, new_value)

    @property
    def current_animation(self):
        """Get the current animation name."""
        return self._current_animation

    @current_animation.setter
    def current_animation(self, value):
        """Set the current animation and notify observers."""
        if value != self._current_animation:
            old_value = self._current_animation
            self._current_animation = value
            self._current_frame = 0  # Reset frame when animation changes
            self.notify_observers("animation", old_value, value)

    @property
    def current_frame(self):
        """Get the current frame index."""
        return self._current_frame

    @current_frame.setter
    def current_frame(self, value):
        """Set the current frame and notify observers."""
        if value != self._current_frame:
            old_value = self._current_frame
            self._current_frame = value
            self.notify_observers("frame", old_value, value)

    def set_frame(self, frame_index):
        """Set the current frame with bounds checking."""
        if self._current_animation in self.animated_sprite._animations:
            max_frames = len(self.animated_sprite._animations[self._current_animation])
            if 0 <= frame_index < max_frames:
                self.current_frame = frame_index
                return True
        return False

    def set_animation(self, animation_name):
        """Set the current animation with validation."""
        if animation_name in self.animated_sprite._animations:
            self.current_animation = animation_name
            return True
        return False

    def get_frame_data(self):
        """Get the current frame data."""
        if (
            self._current_animation in self.animated_sprite._animations
            and self._current_frame < len(self.animated_sprite._animations[self._current_animation])
        ):
            return self.animated_sprite._animations[self._current_animation][self._current_frame]
        return None

    def get_frame_count(self):
        """Get the number of frames in the current animation."""
        if self._current_animation in self.animated_sprite._animations:
            return len(self.animated_sprite._animations[self._current_animation])
        return 0


class AnimatedSpriteInterface(abc.ABC):
    """A formal interface for animated sprites."""

    # Animation state properties (read-only)
    @property
    @abc.abstractmethod
    def current_animation(self: Self) -> str:
        """Return the current animation name."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def current_frame(self: Self) -> int:
        """Return the current frame index."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def is_playing(self: Self) -> bool:
        """Return whether animation is currently playing."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def is_looping(self: Self) -> bool:
        """Return whether current animation loops."""
        raise NotImplementedError

    # Animation information properties
    @property
    @abc.abstractmethod
    def frames(self: Self) -> dict[str, list["SpriteFrame"]]:
        """Return all frames for all animations (including interpolated)."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def animations(self: Self) -> dict[str, dict]:
        """Return animation metadata for all animations."""
        raise NotImplementedError

    # Direct animation metadata access (current animation)
    @property
    @abc.abstractmethod
    def frame_interval(self: Self) -> float:
        """Return the frame interval for the current animation."""
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def loop(self: Self) -> bool:
        """Return whether the current animation loops."""
        raise NotImplementedError

    # Animation control methods
    @abc.abstractmethod
    def play(self: Self, animation_name: str | None = None) -> None:
        """Start playing the specified animation (or current if None)."""
        raise NotImplementedError

    @abc.abstractmethod
    def pause(self: Self) -> None:
        """Pause the current animation."""
        raise NotImplementedError

    @abc.abstractmethod
    def stop(self: Self) -> None:
        """Stop the current animation and reset to frame 0."""
        raise NotImplementedError

    @abc.abstractmethod
    def set_frame(self: Self, frame_index: int) -> None:
        """Set the current frame index."""
        raise NotImplementedError

    @abc.abstractmethod
    def set_animation(self: Self, animation_name: str) -> None:
        """Set the current animation."""
        raise NotImplementedError

    # Animation data methods
    @abc.abstractmethod
    def add_animation(
        self: Self, name: str, frames: list["SpriteFrame"], metadata: dict | None = None
    ) -> None:
        """Add a new animation."""
        raise NotImplementedError

    @abc.abstractmethod
    def remove_animation(self: Self, name: str) -> None:
        """Remove an animation."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_frame(self: Self, animation_name: str, frame_index: int) -> "SpriteFrame":
        """Get a specific frame from a specific animation."""
        raise NotImplementedError

    # File I/O methods
    @abc.abstractmethod
    def load(self: Self, filename: str) -> None:
        """Load animated sprite from a file."""
        raise NotImplementedError

    @abc.abstractmethod
    def save(self: Self, filename: str, file_format: str = DEFAULT_FILE_FORMAT) -> None:
        """Save animated sprite to a file."""
        raise NotImplementedError

    # Update method for animation timing
    @abc.abstractmethod
    def update(self: Self, dt: float) -> None:
        """Update animation timing."""
        raise NotImplementedError


class SpriteFrame:
    """Represents a single frame of an animated sprite."""

    def __init__(self, surface: pygame.Surface, duration: float = 0.5):
        """Initialize a sprite frame.

        Args:
            surface: The pygame surface for this frame
            duration: How long this frame should be displayed (in seconds)

        """
        self._image = surface
        self._rect = pygame.Rect((0, 0), surface.get_size())
        self.duration = duration

    @property
    def image(self) -> pygame.Surface:
        """Return the flattened sprite stack image."""
        return self._image

    @image.setter
    def image(self, new_image: pygame.Surface) -> None:
        """Set the image."""
        self._image = new_image

    @property
    def rect(self) -> pygame.Rect:
        """Return the sprite stack pygame.Rect."""
        return self._rect

    @rect.setter
    def rect(self, new_rect: pygame.Rect) -> None:
        """Set the rect."""
        self._rect = new_rect

    def __getitem__(self, index: int) -> "SpriteFrame":
        """Return a sprite from the stack."""
        return self

    def get_size(self) -> tuple[int, int]:
        """Return the size of the surface."""
        return self._image.get_size()

    def get_alpha(self) -> int:
        """Return the alpha value of the surface."""
        return self._image.get_alpha()

    def get_colorkey(self) -> int | None:
        """Return the colorkey of the surface."""
        return self._image.get_colorkey()

    def get_pixel_data(self) -> list[tuple[int, int, int]]:
        """Get pixel data as a list of RGB tuples."""
        if hasattr(self, "pixels"):
            return self.pixels.copy()
        # Extract pixels from the surface
        width, height = self._image.get_size()
        pixels = []
        for y in range(height):
            for x in range(width):
                color = self._image.get_at((x, y))
                pixels.append((color.r, color.g, color.b))
        return pixels

    def set_pixel_data(self, pixels: list[tuple[int, int, int]]) -> None:
        """Set pixel data from a list of RGB tuples."""
        self.pixels = pixels.copy()
        # Update the surface with the new pixel data
        width, height = self._image.get_size()
        for i, (r, g, b) in enumerate(pixels):
            if i < width * height:
                x = i % width
                y = i // width
                self._image.set_at((x, y), (r, g, b))

    def __repr__(self) -> str:
        """Return string representation of the frame."""
        return f"SpriteFrame(size={self._image.get_size()}, duration={self.duration})"


class AnimatedSprite(AnimatedSpriteInterface, pygame.sprite.DirtySprite):
    """A prototype Sprite Animation class with proper dirty sprite integration."""

    log = LOG

    def __init__(
        self: Self, filename: str | None = None, groups: pygame.sprite.LayeredDirty | None = None
    ) -> None:
        """Initialize the Sprite Animation prototype."""
        super().__init__()

        # Initialize pygame.sprite.DirtySprite
        if groups is None:
            groups = pygame.sprite.LayeredDirty()
        pygame.sprite.DirtySprite.__init__(self, groups)

        # Animation state
        self.name = "animated_sprite"  # Default name
        self.description = ""  # Description field for metadata
        self._animations = {}  # animation_name -> list of frames
        self._is_playing = False
        self._is_looping = False
        self._frame_timer = 0.0
        self._color_map = {}  # Color mapping for TOML files

        # Initialize frame manager as the single source of truth
        self.frame_manager = FrameManager(self)

        # Dirty sprite properties
        self.dirty = 1  # Start dirty to ensure initial render
        self._last_frame_index = -1  # Track frame changes for dirty flag
        self._surface_cache = {}  # Cache for frame surfaces

        # Initialize with default surface
        self.image = pygame.Surface((32, 32))
        self.rect = pygame.Rect(0, 0, 32, 32)

        if filename:
            self.load(filename)

    def __getitem__(self: Self, animation_name: str) -> "SpriteFrame":
        """Return the current frame of the specified animation."""
        return self._animations.get(animation_name, [None])[self.frame_manager.current_frame]

    def get_current_frame(self: Self) -> "SpriteFrame":
        """Return the current frame as a "SpriteFrame"."""
        return self.frame_manager.get_frame_data()

    # Sprite properties - return current frame's surface information
    def _get_current_surface(self: Self) -> pygame.Surface:
        """Get the current frame's surface with caching."""
        frame = self.get_current_frame()
        if not frame:
            # Use cached default surface if available
            cache_key = "default_surface"
            if cache_key in self._surface_cache:
                return self._surface_cache[cache_key]

            # Create and cache default surface
            surface = pygame.Surface((32, 32))
            self._surface_cache[cache_key] = surface
            return surface

        # Use cached surface if available
        cache_key = f"{self.frame_manager.current_animation}_{self.frame_manager.current_frame}"
        if cache_key in self._surface_cache:
            return self._surface_cache[cache_key]

        # Create and cache surface if not available
        surface = self._create_optimized_surface(frame)
        self._surface_cache[cache_key] = surface
        return surface

    @staticmethod
    def _create_optimized_surface(frame: "SpriteFrame") -> pygame.Surface:
        """Create an optimized surface from frame data."""
        if hasattr(frame, "pixels") and frame.pixels:
            # Create surface from pixel data
            width, height = frame.image.get_size()
            surface = pygame.Surface((width, height))

            # Apply pixels efficiently
            for i, (r, g, b) in enumerate(frame.pixels):
                if i < width * height:
                    x = i % width
                    y = i // width
                    surface.set_at((x, y), (r, g, b))

            return surface

        # Fallback to frame's existing surface
        return frame.image.copy()

    # Animation state properties (read-only)
    @property
    def current_animation(self: Self) -> str:
        """Return the current animation name."""
        return self.frame_manager.current_animation

    @property
    def current_frame(self: Self) -> int:
        """Return the current frame index."""
        return self.frame_manager.current_frame

    @property
    def is_playing(self: Self) -> bool:
        """Return whether animation is currently playing."""
        return self._is_playing

    @property
    def is_looping(self: Self) -> bool:
        """Return whether current animation loops."""
        return self._is_looping

    @property
    def frames(self: Self) -> dict[str, list["SpriteFrame"]]:
        """Return all frames for all animations."""
        return self._animations.copy()

    @property
    def animations(self: Self) -> dict[str, list]:
        """Return animation frames for all animations."""
        return self._animations.copy()

    @property
    def frame_interval(self: Self) -> float:
        """Return the frame interval for the current animation."""
        if not self.frame_manager.current_animation:
            return 0.5  # Default frame interval

        frames = self._animations.get(self.frame_manager.current_animation, [])
        if not frames or self.frame_manager.current_frame >= len(frames):
            return 0.5  # Default frame interval

        frame = frames[self.frame_manager.current_frame]
        return frame.duration if frame else 0.5  # Default frame interval

    @property
    def loop(self: Self) -> bool:
        """Return whether the current animation loops."""
        return self._is_looping

    # Animation metadata properties (read-only)
    @property
    def animation_count(self: Self) -> int:
        """Return the number of animations."""
        return len(self._animations)

    @property
    def current_animation_frame_count(self: Self) -> int:
        """Return the number of frames in the current animation."""
        if not self.frame_manager.current_animation:
            return 0
        return len(self._animations.get(self.frame_manager.current_animation, []))

    @property
    def current_animation_total_duration(self: Self) -> float:
        """Return the total duration of the current animation."""
        if not self.frame_manager.current_animation:
            return 0.0
        frames = self._animations.get(self.frame_manager.current_animation, [])
        return sum(f.duration for f in frames)

    @property
    def animation_names(self: Self) -> list[str]:
        """Return list of animation names."""
        return list(self._animations.keys())

    # Animation metadata properties (read/write)
    @is_looping.setter
    def is_looping(self: Self, value: bool) -> None:
        """Set whether animations loop."""
        self._is_looping = value

    @property
    def frame_count(self: Self) -> int:
        """Return the number of frames in the current animation."""
        return self.frame_manager.get_frame_count()

    @property
    def next_animation(self: Self) -> str:
        """Return the next animation in the sequence."""
        if not self._animations:
            return ""
        animation_names = list(self._animations.keys())
        if not animation_names:
            return ""
        current_index = (
            animation_names.index(self._current_animation)
            if self._current_animation in animation_names
            else -1
        )
        next_index = (current_index + 1) % len(animation_names)
        return animation_names[next_index]

    # Animation control methods
    def play(self: Self, animation_name: str | None = None) -> None:
        """Start playing the specified animation (or current if None)."""
        if animation_name:
            self.set_animation(animation_name)
        self._is_playing = True
        self._frame_timer = 0.0

    def play_animation(self: Self, animation_name: str | None = None) -> None:
        """Alias for play method for backwards compatibility."""
        self.play(animation_name)

    def pause(self: Self) -> None:
        """Pause the current animation."""
        self._is_playing = False

    def stop(self: Self) -> None:
        """Stop the current animation and reset to frame 0."""
        self._is_playing = False
        self.frame_manager.current_frame = 0
        self._frame_timer = 0.0

    def set_frame(self: Self, frame_index: int) -> None:
        """Set the current frame index."""
        if not self.frame_manager.current_animation:
            raise ValueError("No animation is currently set")

        if not self.frame_manager.set_frame(frame_index):
            frames = self._animations.get(self.frame_manager.current_animation, [])
            raise IndexError(
                f"Frame index {frame_index} out of range for animation "
                f"'{self.frame_manager.current_animation}' (0-{len(frames) - 1})"
            )

        self._frame_timer = 0.0
        self._update_surface_and_mark_dirty()

    def set_animation(self: Self, animation_name: str) -> None:
        """Set the current animation."""
        if animation_name not in self._animations:
            available = list(self._animations.keys())
            raise ValueError(
                f"Animation '{animation_name}' not found. Available animations: {available}"
            )

        if not self.frame_manager.set_animation(animation_name):
            raise ValueError(f"Failed to set animation '{animation_name}'")

        self._frame_timer = 0.0
        self._update_surface_and_mark_dirty()

    # Animation data methods
    def add_animation(
        self: Self, name: str, frames: list["SpriteFrame"], metadata: dict | None = None
    ) -> None:
        """Add a new animation."""
        self._animations[name] = frames.copy()
        if not self.frame_manager.current_animation:
            self.frame_manager.current_animation = name

    def remove_animation(self: Self, name: str) -> None:
        """Remove an animation."""
        if name in self._animations:
            del self._animations[name]
            if self.frame_manager.current_animation == name:
                # Switch to first available animation
                if self._animations:
                    self.frame_manager.current_animation = next(iter(self._animations.keys()))
                    self.frame_manager.current_frame = 0
                else:
                    self.frame_manager.current_animation = ""
                    self.frame_manager.current_frame = 0

    def get_frame(self: Self, animation_name: str, frame_index: int) -> "SpriteFrame":
        """Get a specific frame from a specific animation."""
        if animation_name not in self._animations:
            raise ValueError(f"Animation '{animation_name}' not found")
        frames = self._animations[animation_name]
        if not 0 <= frame_index < len(frames):
            raise IndexError(
                f"Frame index {frame_index} out of range for animation '{animation_name}'"
            )
        return frames[frame_index]

    def add_frame(self: Self, animation_name: str, frame: "SpriteFrame", index: int = -1) -> None:
        """Add a frame to an animation."""
        if animation_name not in self._animations:
            self._animations[animation_name] = []

        frames = self._animations[animation_name]
        if index == -1:
            frames.append(frame)
        else:
            frames.insert(index, frame)

        # Update surface if this is the current animation
        if self.frame_manager.current_animation == animation_name:
            self._update_surface_and_mark_dirty()

    def remove_frame(self: Self, animation_name: str, frame_index: int) -> None:
        """Remove a frame from an animation."""
        if animation_name not in self._animations:
            raise ValueError(f"Animation '{animation_name}' not found")

        frames = self._animations[animation_name]
        if not 0 <= frame_index < len(frames):
            raise IndexError(
                f"Frame index {frame_index} out of range for animation '{animation_name}'"
            )

        frames.pop(frame_index)

        # Adjust current frame if needed
        if (
            self.frame_manager.current_animation == animation_name
            and self.frame_manager.current_frame >= len(frames)
        ):
            self.frame_manager.current_frame = max(0, len(frames) - 1)
            self._update_surface_and_mark_dirty()

    def get_animation_metadata(self: Self, animation_name: str) -> dict:
        """Get metadata for a specific animation."""
        if animation_name not in self._animations:
            raise ValueError(f"Animation '{animation_name}' not found")

        frames = self._animations[animation_name]
        return {
            "frame_count": len(frames),
            "total_duration": sum(f.duration for f in frames),
            "is_looping": self._is_looping,
        }

    def set_animation_metadata(self: Self, animation_name: str, metadata: dict) -> None:
        """Set metadata for a specific animation."""
        if animation_name not in self._animations:
            raise ValueError(f"Animation '{animation_name}' not found")

        # Update looping state if provided
        if "is_looping" in metadata:
            self._is_looping = metadata["is_looping"]

    # File I/O methods
    def load(self: Self, filename: str) -> None:
        """Load animated sprite from a file.

        Currently only supports TOML format. To add new formats:
        1. Add format detection in _detect_file_format()
        2. Add load logic here (e.g., _load_json(), _load_xml())
        3. Add save methods in save()
        4. Update tests
        See LOADER_README.md for detailed implementation guide.
        """
        file_format = detect_file_format(filename)

        if file_format == "toml":
            self._load_toml(filename)
        else:
            raise ValueError(
                f"Unsupported format: {file_format}. Only TOML is currently supported."
            )

    def _set_initial_animation(self: Self) -> None:
        """Set the initial animation and frame."""
        if self._animations:
            # First try to find "idle" animation, then fall back to first animation in file order
            if "idle" in self._animations:
                self.frame_manager.current_animation = "idle"
                self.log.debug(
                    f"Set initial animation to 'idle' with {len(self._animations['idle'])} frames"
                )
            else:
                # Use the first animation as it appears in the file
                initial_animation = (
                    self._animation_order[0]
                    if self._animation_order
                    else next(iter(self._animations.keys()))
                )
                self.frame_manager.current_animation = initial_animation
                self.log.debug(
                    f"No 'idle' animation found, using first animation in file: "
                    f"'{initial_animation}' with {len(self._animations[initial_animation])} frames"
                )
            self.frame_manager.current_frame = 0
        else:
            self.frame_manager.current_animation = ""
            self.frame_manager.current_frame = 0
            self.log.debug("No animations available, set to empty")

    def _load_toml(self: Self, filename: str) -> None:
        """Load animated sprite from TOML file."""
        try:
            with Path(filename).open(encoding="utf-8") as f:
                data = toml.load(f)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Sprite file not found: {filename}") from e
        except Exception as e:
            raise ValueError(f"Error loading TOML file {filename}: {e}") from e

        self.name = data.get("sprite", {}).get("name", "animated_sprite")
        self.description = data.get("sprite", {}).get("description", "")
        self._animations = {}
        self._animation_order = []  # Track order of animations as they appear in file

        color_map = self._build_color_map(data)
        self._color_map = color_map  # Store color map for later use
        animations = data.get("animation", [])

        self.log.debug(f"Found {len(animations)} animation(s) in TOML file")

        # Check if this is a legacy static sprite (has sprite.pixels but no animations)
        if not animations and "sprite" in data and "pixels" in data["sprite"]:
            self.log.debug("Detected legacy static sprite, converting to single-frame animation")
            self._convert_legacy_static_sprite(data, color_map)
        else:
            # Process normal animated sprite
            for anim_data in animations:
                anim_name = anim_data.get("namespace", "default")
                frames = self._process_toml_animation(anim_data, color_map)
                if frames:
                    self._animations[anim_name] = frames
                    self._animation_order.append(anim_name)  # Track order

        # Log the first namespace found in the file
        if animations:
            first_anim = animations[0]
            first_namespace = first_anim.get("namespace", "default")
            self.log.info(f"FIRST ANIMATION NAMESPACE: '{first_namespace}'")
        elif self._animations:
            # For legacy static sprites, log the converted animation
            first_anim_name = next(iter(self._animations.keys()))
            self.log.info(f"LEGACY STATIC SPRITE CONVERTED TO ANIMATION: '{first_anim_name}'")
        else:
            self.log.info("NO ANIMATIONS FOUND IN FILE")

        self._set_initial_animation()
        self._log_toml_load_results()

        # Initialize the sprite surface with the first frame
        if (
            self.frame_manager.current_animation
            and self.frame_manager.current_animation in self._animations
        ):
            self.log.debug(
                f"INITIAL FRAME STATE: animation='{self.frame_manager.current_animation}', "
                f"frame={self.frame_manager.current_frame}"
            )
            # Force initial surface update by resetting frame tracking
            self._last_frame_index = -1  # Force update regardless of previous state
            self._update_surface_and_mark_dirty()

    def _convert_legacy_static_sprite(self: Self, data: dict, color_map: dict) -> None:
        """Convert a legacy static sprite to a single-frame animation."""
        sprite_data = data["sprite"]
        pixels = sprite_data["pixels"]

        # Parse pixel rows
        pixel_rows = pixels.strip().split("\n")
        height = len(pixel_rows)
        width = len(pixel_rows[0]) if pixel_rows else 0

        # Create a surface from the pixel data
        surface = pygame.Surface((width, height))
        surface.convert()

        # Convert character pixels to actual colors
        for y, row in enumerate(pixel_rows):
            for x, char in enumerate(row):
                if char in color_map:
                    color = color_map[char]
                    surface.set_at((x, y), color)
                else:
                    # Default to magenta for unknown characters
                    surface.set_at((x, y), (255, 0, 255))

        # Create a single frame from the surface
        frame = SpriteFrame(surface)
        frame.pixels = []
        for y in range(height):
            for x in range(width):
                color = surface.get_at((x, y))
                frame.pixels.append((color[0], color[1], color[2]))

        # Create a single animation with one frame
        animation_name = sprite_data.get("name", "idle")
        self._animations[animation_name] = [frame]
        self._animation_order.append(animation_name)

        self.log.debug(
            f"Converted legacy static sprite to single-frame animation "
            f"'{animation_name}' ({width}x{height})"
        )

    @staticmethod
    def _build_color_map(data: dict) -> dict:
        """Build color map from TOML colors section."""
        color_map = {}
        colors_section = data.get("colors", {})
        for char, color_data in colors_section.items():
            r = color_data.get("red", 0)
            g = color_data.get("green", 0)
            b = color_data.get("blue", 0)
            color_map[char] = (r, g, b)
        return color_map

    def _process_toml_animation(self: Self, anim_data: dict, color_map: dict) -> list:
        """Process a single animation from TOML data."""
        anim_name = anim_data.get("namespace", "default")
        frames_data = anim_data.get("frame", [])

        # Set loop property from TOML data
        loop_setting = anim_data.get("loop", True)
        self._is_looping = loop_setting

        # Set frame interval from TOML data
        frame_interval = anim_data.get("frame_interval", 0.5)
        self._frame_interval = frame_interval

        self.log.debug(f"Processing animation '{anim_name}' with {len(frames_data)} frame(s)")
        self._log_animation_metadata(anim_data, anim_name)

        frames = []
        for frame_idx, frame_data in enumerate(frames_data):
            frame = self._create_toml_frame(frame_data, frame_idx, color_map, frame_interval)
            if frame:
                frames.append(frame)

        if frames:
            frames.sort(key=lambda f: getattr(f, "frame_index", 0))
            self.log.debug(f"Animation '{anim_name}' loaded with {len(frames)} frame(s)")
        else:
            self.log.debug(f"Animation '{anim_name}' has no valid frames")

        return frames

    def _log_animation_metadata(self: Self, anim_data: dict, anim_name: str) -> None:
        """Log animation metadata for debugging."""
        self.log.debug(f"  Animation '{anim_name}' metadata:")
        for key, value in anim_data.items():
            if key != "frame":  # Don't show the frame array
                self.log.debug(f"    {key}: {value}")

    def _create_toml_frame(
        self: Self, frame_data: dict, frame_idx: int, color_map: dict, frame_interval: float = 0.5
    ) -> SpriteFrame:
        """Create a SpriteFrame from TOML frame data."""
        frame_index = frame_data.get("frame_index", frame_idx)
        self.log.debug(f"  Processing frame {frame_index} (data index {frame_idx})")

        pixel_data = frame_data.get("pixels", "")
        pixel_lines = AnimatedSprite._parse_toml_pixel_lines(pixel_data)

        if not pixel_lines:
            self.log.debug(f"    Skipping empty frame {frame_index}")
            return None

        width, height, normalized_lines = self._validate_toml_frame_dimensions(pixel_lines, frame_index)
        surface = AnimatedSprite._create_toml_surface(width, height, normalized_lines, color_map)

        # Check for per-frame frame_interval, otherwise use global frame_interval
        frame_duration = frame_data.get("frame_interval", frame_interval)
        if "frame_interval" in frame_data:
            self.log.debug(f"    Using per-frame frame_interval: {frame_duration}")
        else:
            self.log.debug(f"    Using global frame_interval: {frame_duration}")

        frame = SpriteFrame(surface, duration=frame_duration)
        frame.pixels = AnimatedSprite._extract_toml_pixels(normalized_lines, width, height, color_map)

        self._log_frame_debug_info(frame_index, pixel_lines, frame_data)
        return frame

    @staticmethod
    def _parse_toml_pixel_lines(pixel_data: str) -> list:
        """Parse pixel data string into lines."""
        raw_lines = pixel_data.split("\n")
        return [line.strip() for line in raw_lines if line.strip()]

    def _validate_toml_frame_dimensions(
        self: Self, pixel_lines: list, frame_index: int
    ) -> tuple[int, int, list]:
        """Validate and return frame dimensions and normalized lines."""
        # Normalize line lengths by trimming whitespace and ensuring consistency
        # This helps handle AI-generated content with inconsistent formatting
        normalized_lines = []
        for line in pixel_lines:
            # Strip trailing whitespace and normalize the line
            normalized_line = line.rstrip()
            normalized_lines.append(normalized_line)
        
        # Find the most common line length (mode) to handle AI inconsistencies
        line_lengths = [len(line) for line in normalized_lines]
        from collections import Counter
        length_counts = Counter(line_lengths)
        most_common_length = length_counts.most_common(1)[0][0]
        
        # If there are inconsistencies, try to normalize to the most common length
        if len(set(line_lengths)) > 1:
            self.log.warning(
                f"    Frame {frame_index}: Inconsistent line lengths detected. "
                f"Most common length: {most_common_length}, lengths found: {set(line_lengths)}"
            )
            
            # Normalize lines to the most common length
            normalized_lines = []
            for line in pixel_lines:
                line = line.rstrip()
                if len(line) > most_common_length:
                    # Truncate if too long
                    line = line[:most_common_length]
                elif len(line) < most_common_length:
                    # Pad with the last character if too short
                    if line:
                        line = line + line[-1] * (most_common_length - len(line))
                    else:
                        line = "M" * most_common_length  # Default to 'M' for empty lines
                normalized_lines.append(line)
            
            self.log.info(f"    Frame {frame_index}: Normalized to {most_common_length} characters per line")
        
        # Use normalized lines for validation
        expected_width = len(normalized_lines[0])
        for i, line in enumerate(normalized_lines):
            if len(line) != expected_width:
                self.log.error(
                    f"    Frame {frame_index}: Line {i} has {len(line)} pixels, "
                    f"expected {expected_width}"
                )
                raise ValueError(
                    f"Inconsistent line length in frame {frame_index}: "
                    f"line {i} has {len(line)} pixels, expected {expected_width}"
                )

        height = len(normalized_lines)
        width = expected_width
        self.log.debug(f"    Frame {frame_index}: {width}x{height} pixels")
        self.log.debug(f"    Processed: {len(normalized_lines)} lines of {width} pixels each")
        return width, height, normalized_lines

    @staticmethod
    def _create_toml_surface(
        width: int, height: int, pixel_lines: list, color_map: dict
    ) -> pygame.Surface:
        """Create pygame surface from TOML pixel data."""
        surface = pygame.Surface((width, height))
        surface.fill((255, 0, 255))  # Magenta background

        for y, row in enumerate(pixel_lines):
            for x, char in enumerate(row):
                if x < width and y < height:
                    color = color_map.get(char, (255, 0, 255))  # Default to magenta
                    surface.set_at((x, y), color)

        return surface

    @staticmethod
    def _extract_toml_pixels(pixel_lines: list, width: int, height: int, color_map: dict) -> list:
        """Extract pixel data as RGB tuples."""
        pixels = []
        for y, row in enumerate(pixel_lines):
            for x, char in enumerate(row):
                if x < width and y < height:
                    color = color_map.get(char, (255, 0, 255))  # Default to magenta
                    pixels.append(color)
                else:
                    pixels.append((255, 0, 255))
        return pixels

    def _log_frame_debug_info(
        self: Self, frame_index: int, pixel_lines: list, frame_data: dict
    ) -> None:
        """Log debug information for a frame."""
        self.log.debug(f"    Frame {frame_index} loaded successfully")
        self.log.debug(f"    Sanitized pixel data for frame {frame_index}:")

        for y, line in enumerate(pixel_lines):
            self.log.debug(f"      {y:02x}: {line}")

        self.log.debug(f"    Frame {frame_index} metadata:")
        for key, value in frame_data.items():
            if key != "pixels":  # Don't repeat the pixel data
                self.log.debug(f"      {key}: {value}")

    def _log_toml_load_results(self: Self) -> None:
        """Log the results of TOML loading."""
        if self._animations:
            self.log.debug(f"TOML load complete: {len(self._animations)} animation(s) loaded")
            for anim_name, frames in self._animations.items():
                self.log.debug(f"  Animation '{anim_name}': {len(frames)} frame(s)")
        else:
            self.log.debug("TOML load complete: No animations loaded")

    def save(self: Self, filename: str, file_format: str = DEFAULT_FILE_FORMAT) -> None:
        """Save animated sprite to a file.

        Currently only supports TOML format. To add new formats:
        1. Add format detection in _detect_file_format()
        2. Add save logic here (e.g., _save_json(), _save_xml())
        3. Add load methods in _load()
        4. Update tests
        See LOADER_README.md for detailed implementation guide.
        """
        # Check if this is a single animation with a single frame
        if self._is_single_frame_sprite():
            self.log.info("Detected single-frame sprite, saving in legacy static format")
            self._save_as_static_sprite(filename, file_format)
        elif file_format == "toml":
            self._save_toml(filename)
        else:
            raise ValueError(
                f"Unsupported format: {file_format}. Only TOML is currently supported."
            )

    def _is_single_frame_sprite(self: Self) -> bool:
        """Check if this sprite has only one animation with one frame."""
        if len(self._animations) != 1:
            return False

        # Get the first (and only) animation
        animation_frames = next(iter(self._animations.values()))
        return len(animation_frames) == 1

    def _save_as_static_sprite(self: Self, filename: str, file_format: str) -> None:
        """Save as a legacy static sprite format using existing TOML save methods."""
        if file_format == "toml":
            # Use the existing TOML save method but modify it for single frame
            self._save_toml_single_frame(filename)
        else:
            # For unsupported formats, raise an error
            raise ValueError(
                f"Unsupported format: {file_format}. Only TOML is currently supported."
            )

    def _save_toml_single_frame(self: Self, filename: str) -> None:
        """Save single frame as static TOML using existing TOML infrastructure."""
        # Get the single frame from the single animation
        animation_name = next(iter(self._animations.keys()))
        frame = self._animations[animation_name][0]

        # Build color map for the single frame
        color_map = self._build_toml_color_map()

        # Get frame dimensions and pixel data
        width, height = frame.get_size()
        pixels = frame.get_pixel_data()

        # Convert pixels to character representation
        pixel_rows = []
        for y in range(height):
            row = ""
            for x in range(width):
                pixel_index = y * width + x
                if pixel_index < len(pixels):
                    pixel = pixels[pixel_index]
                    # Find the character for this color
                    char = None
                    for color, char_val in color_map.items():
                        if color == pixel:
                            char = char_val
                            break
                    if char is None:
                        char = "."  # Default character
                    row += char
                else:
                    row += "."  # Default character
            pixel_rows.append(row)

        # Write TOML file with proper block string format
        with Path(filename).open("w", encoding="utf-8") as f:
            f.write("[sprite]\n")
            f.write(f'name = "{self.name}"\n')
            f.write('pixels = """\n')
            f.write("\n".join(pixel_rows))
            f.write('\n"""\n\n')

            # Write colors section
            f.write("[colors]\n")
            for color_tuple, char in color_map.items():
                r, g, b = color_tuple
                f.write(f'"{char}" = {{ red = {r}, green = {g}, blue = {b} }}\n')

    def _save_toml(self: Self, filename: str) -> None:
        """Save animated sprite in TOML format.

        This is the main TOML save method for animated sprites. To add new formats:
        1. Create similar methods like _save_json(), _save_xml()
        2. Add format detection in _detect_file_format()
        3. Add save logic in save() method
        4. Update tests
        See LOADER_README.md for detailed implementation guide.
        """
        color_map = self._build_toml_color_map()
        data = self._build_toml_data_structure(color_map)

        with Path(filename).open("w", encoding="utf-8") as f:
            AnimatedSprite._write_toml_sprite_section(f, data)
            AnimatedSprite._write_toml_animations(f, data)
            AnimatedSprite._write_toml_colors(f, data)

    def _build_toml_color_map(self: Self) -> dict:
        """Build color map for TOML format.

        This method creates a mapping from RGB colors to characters for TOML format.
        To add new formats, create similar methods like _build_json_color_map(),
        _build_xml_color_map()
        See LOADER_README.md for detailed implementation guide.
        """
        color_map = {}
        universal_chars = SPRITE_GLYPHS
        char_index = 0

        for frames in self._animations.values():
            for frame in frames:
                pixels = frame.get_pixel_data()
                for r, g, b in pixels:
                    color_tuple = (r, g, b)
                    if color_tuple not in color_map:
                        if char_index >= len(universal_chars):
                            raise ValueError(f"Too many colors (max {len(universal_chars)})")
                        color_map[color_tuple] = universal_chars[char_index]
                        char_index += 1

        return color_map

    def _build_toml_data_structure(self: Self, color_map: dict) -> dict:
        """Build TOML data structure."""
        data = {
            "sprite": {
                "name": self.name or "animated_sprite",
                "description": self.description or "",
            },
            "colors": {},
            "animation": [],
        }

        # Add color definitions
        for (r, g, b), char in color_map.items():
            data["colors"][char] = {"red": r, "green": g, "blue": b}

        # Add animations
        for anim_name, frames in self._animations.items():
            animation_frames = AnimatedSprite._create_toml_animation_frames(frames, color_map)
            animation_entry = {
                "namespace": anim_name,
                "frame_interval": 0.5,
                "loop": True,
                "frame": animation_frames,
            }
            data["animation"].append(animation_entry)

        return data

    @staticmethod
    def _create_toml_animation_frames(frames: list, color_map: dict) -> list:
        """Create TOML animation frames."""
        animation_frames = []
        for i, frame in enumerate(frames):
            frame_data = AnimatedSprite._create_toml_frame_data(frame, i, color_map)
            animation_frames.append(frame_data)
        return animation_frames

    @staticmethod
    def _create_toml_frame_data(frame: SpriteFrame, frame_index: int, color_map: dict) -> dict:
        """Create TOML frame data."""
        pixels = frame.get_pixel_data()
        width, height = frame.get_size()
        pixel_chars = AnimatedSprite._convert_pixels_to_toml_chars(pixels, width, height, color_map)
        return {"frame_index": frame_index, "pixels": "\n".join(pixel_chars)}

    @staticmethod
    def _convert_pixels_to_toml_chars(
        pixels: list, width: int, height: int, color_map: dict
    ) -> list:
        """Convert pixels to TOML character representation."""
        pixel_chars = []
        for y in range(height):
            row = []
            for x in range(width):
                pixel_idx = y * width + x
                if pixel_idx < len(pixels):
                    r, g, b = pixels[pixel_idx]
                    color_char = color_map.get((r, g, b), ".")
                    row.append(color_char)
                else:
                    row.append(".")
            pixel_chars.append("".join(row))
        return pixel_chars

    @staticmethod
    def _write_toml_sprite_section(f, data: dict) -> None:
        """Write TOML sprite section."""
        f.write("[sprite]\n")
        f.write(f'name = "{data["sprite"]["name"]}"\n')
        if data["sprite"].get("description"):
            f.write(f'description = """{data["sprite"]["description"]}"""\n')
        f.write("\n")

    @staticmethod
    def _write_toml_animations(f, data: dict) -> None:
        """Write TOML animations section."""
        for animation in data["animation"]:
            f.write("[[animation]]\n")
            f.write(f'namespace = "{animation["namespace"]}"\n')
            f.write(f"frame_interval = {animation['frame_interval']}\n")
            f.write(f"loop = {str(animation['loop']).lower()}\n\n")

            for frame in animation["frame"]:
                f.write("[[animation.frame]]\n")
                f.write(f'namespace = "{animation["namespace"]}"\n')
                f.write(f"frame_index = {frame['frame_index']}\n")
                f.write('pixels = """\n')
                f.write(frame["pixels"])
                f.write('\n"""\n\n')

    @staticmethod
    def _write_toml_colors(f, data: dict) -> None:
        """Write TOML colors section."""
        if data["colors"]:
            f.write("[colors]\n")
            for char, color in data["colors"].items():
                f.write(f'[colors."{char}"]\n')
                f.write(f"red = {color['red']}\n")
                f.write(f"green = {color['green']}\n")
                f.write(f"blue = {color['blue']}\n\n")

    def update(self: Self, dt: float = 0.016) -> None:
        """Update animation timing."""
        if not self._is_playing or not self.frame_manager.current_animation:
            return

        if self.frame_manager.current_animation not in self._animations:
            return

        frames = self._animations[self.frame_manager.current_animation]
        if not frames:
            return

        # Update frame timer
        self._frame_timer += dt

        # Use the current frame's duration for timing
        current_frame = frames[self.frame_manager.current_frame]
        frame_interval = current_frame.duration

        if self._frame_timer >= frame_interval:
            self._advance_frame(frames)
            self._update_surface_and_mark_dirty()
            self._debug_frame_info(frames)

    def _advance_frame(self: Self, frames: list) -> None:
        """Advance to the next frame in the animation."""
        old_frame = self.frame_manager.current_frame
        self._frame_timer = 0.0
        self.frame_manager.current_frame += 1

        # Log only on frame transitions
        self.log.debug(f"Frame advance: {old_frame} -> {self.frame_manager.current_frame}")
        if old_frame == 0 and self.frame_manager.current_frame == 1:
            self.log.debug("FIRST FRAME ADVANCE: 0 -> 1")

        # Check if we've reached the end
        if self.frame_manager.current_frame >= len(frames):
            if self._is_looping:
                self.frame_manager.current_frame = 0
                self.log.debug(f"Looping back to frame 0 (total frames: {len(frames)})")
            else:
                self.frame_manager.current_frame = len(frames) - 1
                self._is_playing = False
                self.log.debug(
                    f"Animation ended, stopped at frame {self.frame_manager.current_frame}"
                )

    def _debug_frame_info(self: Self, frames: list) -> None:
        """Debug frame information for development."""
        if (
            not self.frame_manager.current_animation
            or self.frame_manager.current_animation not in self._animations
        ):
            self.log.debug(
                f"ANIMATION FRAME DUMP: animation '{self.frame_manager.current_animation}' "
                f"not found or no animation"
            )
            return

        if self.frame_manager.current_frame >= len(frames):
            self.log.debug(
                f"ANIMATION FRAME DUMP: frame_index {self.frame_manager.current_frame} "
                f"out of range for {len(frames)} frames"
            )
            return

        frame = frames[self.frame_manager.current_frame]
        self.log.debug(
            f"ANIMATION FRAME DUMP: animation='{self.frame_manager.current_animation}', "
            f"frame_index={self.frame_manager.current_frame}, frame={frame}, "
            f"has_surface={hasattr(frame, 'surface')}"
        )

        self._debug_frame_pixel_data(frame)

    def _debug_frame_pixel_data(self: Self, frame: "SpriteFrame") -> None:
        """Debug pixel data for a frame."""
        if hasattr(frame, "pixels") and frame.pixels:
            # Create hash of frame pixel data for debugging
            pixel_data_str = str(frame.pixels)
            pixel_hash = hashlib.sha256(pixel_data_str.encode()).hexdigest()[:8]
            self.log.debug(f"  Frame {self.frame_manager.current_frame} pixel hash: {pixel_hash}")
            self.log.debug(f"  Total pixels: {len(frame.pixels)}")
        elif hasattr(frame, "image"):
            self._debug_frame_image_data(frame)
        else:
            self.log.debug("  No pixel data available")

    def _debug_frame_image_data(self: Self, frame: "SpriteFrame") -> None:
        """Debug image data for a frame."""
        try:
            pixel_array = pygame.surfarray.array3d(frame.image)
            self.log.debug(f"  Image surface size: {frame.image.get_size()}")
            self.log.debug(f"  Pixel array shape: {pixel_array.shape}")
            # Show a small sample of pixel data
            if pixel_array.size > 0:
                sample_pixels = (
                    pixel_array[0, 0, :]
                    if len(pixel_array.shape) == PIXEL_ARRAY_SHAPE_DIMENSIONS
                    else pixel_array[0]
                )
                self.log.debug(f"  Sample pixel data: {sample_pixels}")
        except (ValueError, pygame.error) as e:
            self.log.debug(f"  Could not get pixel data from image: {e}")

    def _update_surface_and_mark_dirty(self) -> None:
        """Update the sprite's surface and mark as dirty for efficient rendering."""
        if (
            not self.frame_manager.current_animation
            or self.frame_manager.current_animation not in self._animations
        ):
            return

        frames = self._animations[self.frame_manager.current_animation]
        if self.frame_manager.current_frame >= len(frames):
            return

        # Check if frame actually changed
        if self._last_frame_index == self.frame_manager.current_frame:
            return  # No change needed

        # Update the sprite's image and rect
        new_surface = self._get_current_surface()
        self.image = new_surface

        # Preserve the current position when updating rect
        old_center = self.rect.center
        self.rect = new_surface.get_rect()
        self.rect.center = old_center

        # Update frame tracking
        self._last_frame_index = self.frame_manager.current_frame

        # Mark as dirty for pygame's dirty sprite system
        self.dirty = 1

        self.log.debug(
            f"Updated surface for frame {self.frame_manager.current_frame} "
            f"of animation '{self.frame_manager.current_animation}'"
        )

    @staticmethod
    def _create_surface_from_toml_pixels(width: int, height: int, pixels: list) -> pygame.Surface:
        """Create a pygame surface from TOML RGB pixel data."""
        surface = pygame.Surface((width, height))

        # Set each pixel on the surface from the pixel data
        for i, (r, g, b) in enumerate(pixels):
            if i < width * height:
                x = i % width
                y = i // width
                surface.set_at((x, y), (r, g, b))

        return surface

    def update_nested_sprites(self: Self) -> None:
        """Update nested sprites (required by SpriteInterface)."""
        # AnimatedSprite doesn't have nested sprites, so this is a no-op

    def clear_surface_cache(self: Self) -> None:
        """Clear the surface cache to free memory."""
        self._surface_cache.clear()
        self.log.debug("Surface cache cleared")

    def _get_animation_data(self: Self) -> dict:
        """Get animation data for AI training."""
        if not hasattr(self, "_animations") or not self._animations:
            return {}

        animation_data = {}
        for anim_name, frames in self._animations.items():
            animation_data[anim_name] = {
                "frames": len(frames),
                "frame_interval": 0.5,  # Default frame interval
                "loop": True,  # Default loop setting
            }

        return animation_data
