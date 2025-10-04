"""Animated sprite classes for GlitchyGames.

This module contains the animated sprite implementation that extends the
basic sprite functionality to support multi-frame animations with flexible
timing and playback control.
"""

import abc
import configparser
import logging
import operator
from pathlib import Path
from typing import Self

import pygame
import toml

# import yaml  # Unused import removed
# Import constants
from .constants import DEFAULT_FILE_FORMAT, SPRITE_GLYPHS

# Import detect_file_format function
try:
    from glitchygames.tools.bitmappy import detect_file_format
except ImportError:
    # Fallback if bitmappy module is not available
    def detect_file_format(filename: str) -> str:
        """Detect file format based on extension."""
        filename_lower = filename.lower()
        if filename_lower.endswith((".yaml", ".yml")):
            return "yaml"
        if filename_lower.endswith(".ini"):
            return "ini"
        return "toml"  # Default to toml

LOG = logging.getLogger("game.sprites.animated")


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
        self: Self, 
        filename: str | None = None, 
        groups: pygame.sprite.LayeredDirty | None = None
    ) -> None:
        """Initialize the Sprite Animation prototype."""
        super().__init__()

        # Initialize pygame.sprite.DirtySprite
        if groups is None:
            groups = pygame.sprite.LayeredDirty()
        pygame.sprite.DirtySprite.__init__(self, groups)

        # Animation state
        self.name = "animated_sprite"  # Default name
        self._animations = {}  # animation_name -> list of frames
        self._current_animation = ""
        self._current_frame = 0
        self._is_playing = False
        self._is_looping = False
        self._frame_timer = 0.0
        self._color_map = {}  # Color mapping for TOML files

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
        return self._animations.get(animation_name, [None])[self._current_frame]

    def get_current_frame(self: Self) -> "SpriteFrame":
        """Return the current frame as a "SpriteFrame"."""
        if not self._current_animation or self._current_animation not in self._animations:
            return None
        frames = self._animations[self._current_animation]
        if not frames or self._current_frame >= len(frames):
            return None
        return frames[self._current_frame]

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
        cache_key = f"{self._current_animation}_{self._current_frame}"
        if cache_key in self._surface_cache:
            return self._surface_cache[cache_key]
        
        # Create and cache surface if not available
        surface = self._create_optimized_surface(frame)
        self._surface_cache[cache_key] = surface
        return surface

    @staticmethod
    def _create_optimized_surface(frame: "SpriteFrame") -> pygame.Surface:
        """Create an optimized surface from frame data."""
        if hasattr(frame, 'pixels') and frame.pixels:
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
        else:
            # Fallback to frame's existing surface
            return frame.image.copy()

    # Animation state properties (read-only)
    @property
    def current_animation(self: Self) -> str:
        """Return the current animation name."""
        return self._current_animation

    @property
    def current_frame(self: Self) -> int:
        """Return the current frame index."""
        return self._current_frame

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
    def animations(self: Self) -> dict[str, dict]:
        """Return animation metadata for all animations."""
        # For now, return empty metadata - can be extended later
        return {name: {} for name in self._animations}

    @property
    def frame_interval(self: Self) -> float:
        """Return the frame interval for the current animation."""
        frame = self._animations.get(self._current_animation, [None])[self._current_frame]
        return frame.duration if frame else 0.5  # Default frame interval

    @property
    def loop(self: Self) -> bool:
        """Return whether the current animation loops."""
        return self._is_looping

    @property
    def frame_count(self: Self) -> int:
        """Return the number of frames in the current animation."""
        if self._current_animation in self._animations:
            return len(self._animations[self._current_animation])
        return 0

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
        self._current_frame = 0
        self._frame_timer = 0.0

    def set_frame(self: Self, frame_index: int) -> None:
        """Set the current frame index."""
        if self._current_animation in self._animations:
            max_frames = len(self._animations[self._current_animation])
            if 0 <= frame_index < max_frames:
                old_frame = self._current_frame
                self._current_frame = frame_index
                self._frame_timer = 0.0
                
                # Mark dirty if frame actually changed
                if old_frame != frame_index:
                    self._update_surface_and_mark_dirty()

    def set_animation(self: Self, animation_name: str) -> None:
        """Set the current animation."""
        if animation_name in self._animations:
            old_animation = self._current_animation
            self._current_animation = animation_name
            self._current_frame = 0
            self._frame_timer = 0.0
            
            # Mark dirty if animation actually changed
            if old_animation != animation_name:
                self._update_surface_and_mark_dirty()

    # Animation data methods
    def add_animation(
        self: Self, name: str, frames: list["SpriteFrame"], metadata: dict | None = None
    ) -> None:
        """Add a new animation."""
        self._animations[name] = frames.copy()
        if not self._current_animation:
            self._current_animation = name

    def remove_animation(self: Self, name: str) -> None:
        """Remove an animation."""
        if name in self._animations:
            del self._animations[name]
            if self._current_animation == name:
                # Switch to first available animation
                if self._animations:
                    self._current_animation = next(iter(self._animations.keys()))
                    self._current_frame = 0
                else:
                    self._current_animation = ""
                    self._current_frame = 0

    def get_frame(self: Self, animation_name: str, frame_index: int) -> "SpriteFrame":
        """Get a specific frame from a specific animation."""
        if animation_name in self._animations:
            frames = self._animations[animation_name]
            if 0 <= frame_index < len(frames):
                return frames[frame_index]
        return None

    # File I/O methods
    def load(self: Self, filename: str) -> None:
        """Load animated sprite from a file."""
        # Detect file format from extension
        # Import moved to top level

        file_format = detect_file_format(filename)

        if file_format == "ini":
            self._load_ini(filename)
        elif file_format == "yaml":
            self._load_yaml(filename)
        elif file_format == "toml":
            self._load_toml(filename)
        else:
            raise ValueError(f"Unsupported file format: {file_format}")

    def _load_ini(self: Self, filename: str) -> None:
        """Load animated sprite from INI file."""
        config = configparser.ConfigParser()
        config.read(filename)

        self._validate_ini_sprite(config, filename)
        self.name = config.get("sprite", "name", fallback="animated_sprite")
        self._animations = {}

        animation_sections = [
            section for section in config.sections() if section.startswith("animation_")
        ]

        for anim_section in animation_sections:
            anim_name = anim_section.replace("animation_", "")
            frames = self._load_animation_frames(config, anim_name)
            if frames:
                self._animations[anim_name] = frames

        self._set_initial_animation()

    @staticmethod
    def _validate_ini_sprite(config: configparser.ConfigParser, filename: str) -> None:
        """Validate that the INI file contains an animated sprite."""
        if not config.has_section("sprite"):
            raise ValueError(f"File {filename} is not a valid sprite file")

        sprite_type = config.get("sprite", "type", fallback="static")
        if sprite_type != "animated":
            raise ValueError(f"File {filename} is not an animated sprite file")

    @staticmethod
    def _load_animation_frames(config: configparser.ConfigParser, anim_name: str) -> list:
        """Load frames for a specific animation from INI config."""
        frame_count = config.getint(f"animation_{anim_name}", "frame_count", fallback=0)
        frames = []

        for i in range(frame_count):
            frame_section = f"frame_{anim_name}_{i}"
            if config.has_section(frame_section):
                frame = AnimatedSprite._create_frame_from_ini(config, frame_section)
                if frame:
                    frames.append(frame)

        return frames

    @staticmethod
    def _create_frame_from_ini(
        config: configparser.ConfigParser, frame_section: str
    ) -> SpriteFrame:
        """Create a SpriteFrame from INI frame section."""
        width = config.getint(frame_section, "width", fallback=8)
        height = config.getint(frame_section, "height", fallback=8)
        pixels_str = config.get(frame_section, "pixels", fallback="")

        surface = pygame.Surface((width, height))
        surface.fill((255, 0, 255))  # Magenta background

        pixels = AnimatedSprite._parse_pixel_data(pixels_str, width, height)
        AnimatedSprite._draw_pixels_to_surface(surface, pixels, width, height)

        frame = SpriteFrame(surface)
        frame.pixels = pixels
        return frame

    @staticmethod
    def _parse_pixel_data(pixels_str: str, width: int, height: int) -> list:
        """Parse pixel data string into RGB tuples."""
        pixel_rows = pixels_str.split("\n")
        pixels = []

        for y, row in enumerate(pixel_rows):
            if y < height:
                for x, char in enumerate(row):
                    if x < width:
                        color = AnimatedSprite._char_to_color(char)
                        pixels.append(color)
                    else:
                        pixels.append((255, 0, 255))
            else:
                pixels.extend([(255, 0, 255)] * width)

        return pixels

    @staticmethod
    def _char_to_color(char: str) -> tuple[int, int, int]:
        """Convert character to RGB color."""
        color_map = {
            "R": (255, 0, 0),    # Red
            "G": (0, 255, 0),    # Green
            "B": (0, 0, 255),    # Blue
        }
        return color_map.get(char, (255, 0, 255))  # Default to magenta

    @staticmethod
    def _draw_pixels_to_surface(
        surface: pygame.Surface, pixels: list, width: int, height: int
    ) -> None:
        """Draw pixels to pygame surface."""
        for i, color in enumerate(pixels):
            x = i % width
            y = i // width
            if y < height:
                surface.set_at((x, y), color)

    def _set_initial_animation(self: Self) -> None:
        """Set the initial animation and frame."""
        if self._animations:
            # First try to find "idle" animation, then fall back to first animation in file order
            if "idle" in self._animations:
                self._current_animation = "idle"
                self.log.debug(f"Set initial animation to 'idle' with {len(self._animations['idle'])} frames")
            else:
                # Use the first animation as it appears in the file
                self._current_animation = self._animation_order[0] if self._animation_order else next(iter(self._animations.keys()))
                self.log.debug(f"No 'idle' animation found, using first animation in file: '{self._current_animation}' with {len(self._animations[self._current_animation])} frames")
            self._current_frame = 0
        else:
            self._current_animation = ""
            self._current_frame = 0
            self.log.debug("No animations available, set to empty")

    def _load_yaml(self: Self, filename: str) -> None:
        """Load animated sprite from YAML file."""
        # TODO: Implement YAML loading
        raise NotImplementedError("YAML loading not yet implemented")

    def _load_toml(self: Self, filename: str) -> None:
        """Load animated sprite from TOML file."""
        with Path(filename).open(encoding="utf-8") as f:
            data = toml.load(f)

        self.name = data.get("sprite", {}).get("name", "animated_sprite")
        self._animations = {}
        self._animation_order = []  # Track order of animations as they appear in file

        color_map = self._build_color_map(data)
        self._color_map = color_map  # Store color map for later use
        animations = data.get("animation", [])

        self.log.debug(f"Found {len(animations)} animation(s) in TOML file")

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
        else:
            self.log.info("NO ANIMATIONS FOUND IN FILE")

        self._set_initial_animation()
        self._log_toml_load_results()

        # Initialize the sprite surface with the first frame
        if self._current_animation and self._current_animation in self._animations:
            self.log.debug(f"INITIAL FRAME STATE: animation='{self._current_animation}', frame={self._current_frame}")
            # Force initial surface update
            self._update_surface_and_mark_dirty()

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

        width, height = self._validate_toml_frame_dimensions(pixel_lines, frame_index)
        surface = AnimatedSprite._create_toml_surface(width, height, pixel_lines, color_map)

        frame = SpriteFrame(surface, duration=frame_interval)
        frame.pixels = AnimatedSprite._extract_toml_pixels(pixel_lines, width, height, color_map)

        self._log_frame_debug_info(frame_index, pixel_lines, frame_data)
        return frame

    @staticmethod
    def _parse_toml_pixel_lines(pixel_data: str) -> list:
        """Parse pixel data string into lines."""
        raw_lines = pixel_data.split("\n")
        return [line.strip() for line in raw_lines if line.strip()]

    def _validate_toml_frame_dimensions(
        self: Self, pixel_lines: list, frame_index: int
    ) -> tuple[int, int]:
        """Validate and return frame dimensions."""
        expected_width = len(pixel_lines[0])
        for i, line in enumerate(pixel_lines):
            if len(line) != expected_width:
                self.log.error(
                    f"    Frame {frame_index}: Line {i} has {len(line)} pixels, "
                    f"expected {expected_width}"
                )
                raise ValueError(
                    f"Inconsistent line length in frame {frame_index}: "
                    f"line {i} has {len(line)} pixels, expected {expected_width}"
                )

        height = len(pixel_lines)
        width = expected_width
        self.log.debug(f"    Frame {frame_index}: {width}x{height} pixels")
        self.log.debug(f"    Processed: {len(pixel_lines)} lines of {width} pixels each")
        return width, height

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
    def _extract_toml_pixels(
        pixel_lines: list, width: int, height: int, color_map: dict
    ) -> list:
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
        """Save animated sprite to a file."""
        if file_format == "ini":
            self._save_ini(filename)
        elif file_format == "yaml":
            self._save_yaml(filename)
        elif file_format == "toml":
            self._save_toml(filename)
        else:
            raise ValueError(f"Unsupported file format: {file_format}")

    def _save_ini(self: Self, filename: str) -> None:
        """Save animated sprite in INI format."""
        config = configparser.ConfigParser()

        self._add_sprite_section(config)
        color_map = self._build_ini_color_map()
        self._add_animation_sections(config, color_map)
        AnimatedSprite._add_color_definitions(config, color_map)

        with Path(filename).open("w", encoding="utf-8") as f:
            config.write(f)

    def _add_sprite_section(self: Self, config: configparser.ConfigParser) -> None:
        """Add sprite section to INI config."""
        if self.name and self.name != "animated_sprite":
            config.add_section("sprite")
            config.set("sprite", "name", self.name)

    def _build_ini_color_map(self: Self) -> dict:
        """Build color map from all frames using universal character set."""
        color_map = {}
        universal_chars = SPRITE_GLYPHS.strip()
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

    def _add_animation_sections(
        self: Self, config: configparser.ConfigParser, color_map: dict
    ) -> None:
        """Add animation sections to INI config."""
        for anim_name, frames in self._animations.items():
            AnimatedSprite._add_animation_section(config, anim_name, frames, color_map)

    @staticmethod
    def _add_animation_section(
        config: configparser.ConfigParser, anim_name: str, frames: list, color_map: dict
    ) -> None:
        """Add a single animation section to INI config."""
        anim_section = f"animation_{anim_name}"
        config.add_section(anim_section)
        config.set(anim_section, "namespace", anim_name)
        config.set(anim_section, "frame_interval", "0.5")
        config.set(anim_section, "loop", "true")

        for i, frame in enumerate(frames):
            AnimatedSprite._add_frame_section(config, anim_name, i, frame, color_map)

    @staticmethod
    def _add_frame_section(
        config: configparser.ConfigParser,
        anim_name: str,
        frame_index: int,
        frame: SpriteFrame,
        color_map: dict,
    ) -> None:
        """Add a single frame section to INI config."""
        frame_section = f"frame_{anim_name}_{frame_index}"
        config.add_section(frame_section)
        config.set(frame_section, "namespace", anim_name)
        config.set(frame_section, "frame_index", str(frame_index))

        pixels = frame.get_pixel_data()
        width, height = frame.get_size()
        pixel_chars = AnimatedSprite._convert_pixels_to_chars(pixels, width, height, color_map)
        config.set(frame_section, "pixels", "\n".join(pixel_chars))

    @staticmethod
    def _convert_pixels_to_chars(
        pixels: list, width: int, height: int, color_map: dict
    ) -> list:
        """Convert pixel data to character representation."""
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
    def _add_color_definitions(
        config: configparser.ConfigParser, color_map: dict
    ) -> None:
        """Add color definitions to INI config."""
        for color_tuple, char in sorted(color_map.items(), key=operator.itemgetter(1)):
            config.add_section(char)
            config.set(char, "red", str(color_tuple[0]))
            config.set(char, "green", str(color_tuple[1]))
            config.set(char, "blue", str(color_tuple[2]))

    def _save_yaml(self: Self, filename: str) -> None:
        """Save animated sprite in YAML format."""
        color_map = self._build_yaml_color_map()
        data = self._build_yaml_data_structure(color_map)

        with Path(filename).open("w", encoding="utf-8") as f:
            AnimatedSprite._write_yaml_header(f, data)
            AnimatedSprite._write_yaml_colors(f, data)
            AnimatedSprite._write_yaml_animations(f, data)

    def _build_yaml_color_map(self: Self) -> dict:
        """Build color map for YAML format."""
        color_map = {}
        universal_chars = SPRITE_GLYPHS.strip()
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

    def _build_yaml_data_structure(self: Self, color_map: dict) -> dict:
        """Build YAML data structure."""
        data = {"sprite": {"name": self.name or "animated_sprite"}, "colors": {}, "animations": {}}

        # Add color definitions
        for (r, g, b), char in color_map.items():
            data["colors"][char] = {"red": r, "green": g, "blue": b}

        # Add animation data
        for anim_name, frames in self._animations.items():
            animation_data = {"frames": []}
            for frame in frames:
                frame_data = AnimatedSprite._create_yaml_frame_data(frame, color_map)
                animation_data["frames"].append(frame_data)
            data["animations"][anim_name] = animation_data

        return data

    @staticmethod
    def _create_yaml_frame_data(frame: SpriteFrame, color_map: dict) -> dict:
        """Create frame data for YAML format."""
        pixels = frame.get_pixel_data()
        width, height = frame.get_size()
        pixel_strings = AnimatedSprite._convert_pixels_to_yaml_strings(
            pixels, width, height, color_map
        )
        pixel_data = " ".join(pixel_strings)
        return {"pixels": pixel_data, "duration": frame.duration}

    @staticmethod
    def _convert_pixels_to_yaml_strings(
        pixels: list, width: int, height: int, color_map: dict
    ) -> list:
        """Convert pixels to YAML string representation."""
        pixel_strings = []
        for y in range(height):
            row = ""
            for x in range(width):
                pixel_index = y * width + x
                if pixel_index < len(pixels):
                    r, g, b = pixels[pixel_index]
                    char = color_map.get((r, g, b), ".")
                    row += char
                else:
                    row += "."
            pixel_strings.append(row)
        return pixel_strings

    @staticmethod
    def _write_yaml_header(f, data: dict) -> None:
        """Write YAML header sections."""
        f.write("sprite:\n")
        f.write(f"  name: {data['sprite']['name']}\n")
        f.write(f"  type: {data['sprite'].get('type', 'animated')}\n\n")

    @staticmethod
    def _write_yaml_colors(f, data: dict) -> None:
        """Write YAML colors section."""
        if data.get("colors"):
            f.write("colors:\n")
            for char, color_info in data["colors"].items():
                f.write(f"  {char}:\n")
                f.write(f"    red: {color_info['red']}\n")
                f.write(f"    green: {color_info['green']}\n")
                f.write(f"    blue: {color_info['blue']}\n")
            f.write("\n")

    @staticmethod
    def _write_yaml_animations(f, data: dict) -> None:
        """Write YAML animations section."""
        f.write("animations:\n")
        for anim_name, anim_data in data["animations"].items():
            f.write(f"  {anim_name}:\n")
            f.write("    frames:\n")
            for frame in anim_data["frames"]:
                f.write("    - frame:\n")
                f.write("        duration: {}\n".format(frame["duration"]))
                f.write("        pixels: |\n")
                pixel_rows = frame["pixels"].split(" ")
                for row in pixel_rows:
                    f.write(f"          {row}\n")
                f.write("\n")

    def _save_toml(self: Self, filename: str) -> None:
        """Save animated sprite in TOML format."""
        color_map = self._build_toml_color_map()
        data = self._build_toml_data_structure(color_map)

        with Path(filename).open("w", encoding="utf-8") as f:
            AnimatedSprite._write_toml_sprite_section(f, data)
            AnimatedSprite._write_toml_animations(f, data)
            AnimatedSprite._write_toml_colors(f, data)

    def _build_toml_color_map(self: Self) -> dict:
        """Build color map for TOML format."""
        color_map = {}
        universal_chars = SPRITE_GLYPHS.strip()
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
        data = {"sprite": {"name": self.name or "animated_sprite"}, "colors": {}, "animation": []}

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
    def _create_toml_frame_data(
        frame: SpriteFrame, frame_index: int, color_map: dict
    ) -> dict:
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
        f.write(f'name = "{data["sprite"]["name"]}"\n\n')

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
        if not self._is_playing or not self._current_animation:
            return

        if self._current_animation not in self._animations:
            return

        frames = self._animations[self._current_animation]
        if not frames:
            return

        # Update frame timer
        self._frame_timer += dt

        # Use the animation's frame interval instead of individual frame duration
        frame_interval = getattr(self, '_frame_interval', 0.5)
        
        if self._frame_timer >= frame_interval:
            # Move to next frame
            old_frame = self._current_frame
            self._frame_timer = 0.0
            self._current_frame += 1

            # Log only on frame transitions
            self.log.debug(f"Frame advance: {old_frame} -> {self._current_frame}")
            if old_frame == 0 and self._current_frame == 1:
                self.log.debug("FIRST FRAME ADVANCE: 0 -> 1")

            # Check if we've reached the end
            if self._current_frame >= len(frames):
                if self._is_looping:
                    self._current_frame = 0
                    self.log.debug(f"Looping back to frame 0 (total frames: {len(frames)})")
                else:
                    self._current_frame = len(frames) - 1
                    self._is_playing = False
                    self.log.debug(f"Animation ended, stopped at frame {self._current_frame}")

            # Update the surface with the new frame's pixel data
            self._update_surface_and_mark_dirty()

            # Debug: Dump current frame info only on transitions (after loop correction)
            if self._current_animation and self._current_animation in self._animations:
                frames = self._animations[self._current_animation]
                if self._current_frame < len(frames):
                    frame = frames[self._current_frame]
                    self.log.debug(f"ANIMATION FRAME DUMP: animation='{self._current_animation}', frame_index={self._current_frame}, frame={frame}, has_surface={hasattr(frame, 'surface')}")

                    # Get pixel data from the frame
                    if hasattr(frame, 'pixels') and frame.pixels:
                        # Show first few pixels of the frame
                        pixel_preview = frame.pixels[:10] if len(frame.pixels) > 10 else frame.pixels
                        self.log.debug(f"  Frame pixels (first 10): {pixel_preview}")
                        self.log.debug(f"  Total pixels: {len(frame.pixels)}")

                        # Show pixels from the middle where the sprite content is
                        if len(frame.pixels) > 500:
                            middle_start = 500
                            middle_end = min(510, len(frame.pixels))
                            self.log.debug(f"  Frame pixels (middle 500-510): {frame.pixels[middle_start:middle_end]}")
                    elif hasattr(frame, 'image'):
                        # Try to get pixel data from the image surface
                        try:
                            pixel_array = pygame.surfarray.array3d(frame.image)
                            self.log.debug(f"  Image surface size: {frame.image.get_size()}")
                            self.log.debug(f"  Pixel array shape: {pixel_array.shape}")
                            # Show a small sample of pixel data
                            if pixel_array.size > 0:
                                sample_pixels = pixel_array[0, 0, :] if len(pixel_array.shape) == 3 else pixel_array[0]
                                self.log.debug(f"  Sample pixel data: {sample_pixels}")
                        except Exception as e:
                            self.log.debug(f"  Could not get pixel data from image: {e}")
                    else:
                        self.log.debug(f"  No pixel data available")
                else:
                    self.log.debug(f"ANIMATION FRAME DUMP: frame_index {self._current_frame} out of range for {len(frames)} frames")
            else:
                self.log.debug(f"ANIMATION FRAME DUMP: animation '{self._current_animation}' not found or no animation")

    def _update_surface_and_mark_dirty(self) -> None:
        """Update the sprite's surface and mark as dirty for efficient rendering."""
        if not self._current_animation or self._current_animation not in self._animations:
            return

        frames = self._animations[self._current_animation]
        if self._current_frame >= len(frames):
            return

        # Check if frame actually changed
        if self._last_frame_index == self._current_frame:
            return  # No change needed

        # Update the sprite's image and rect
        new_surface = self._get_current_surface()
        self.image = new_surface
        
        # Preserve the current position when updating rect
        old_center = self.rect.center
        self.rect = new_surface.get_rect()
        self.rect.center = old_center

        # Update frame tracking
        self._last_frame_index = self._current_frame

        # Mark as dirty for pygame's dirty sprite system
        self.dirty = 1

        self.log.debug(f"Updated surface for frame {self._current_frame} of animation '{self._current_animation}'")

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
        pass

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
