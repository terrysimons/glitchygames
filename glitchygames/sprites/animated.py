#!/usr/bin/env python3
"""
Animated sprite classes for GlitchyGames.

This module contains the animated sprite implementation that extends the
basic sprite functionality to support multi-frame animations with flexible
timing and playback control.
"""

import abc
import logging
from typing import Any, Self

import pygame

# Import constants
from .constants import DEFAULT_FILE_FORMAT, SPRITE_GLYPHS

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
    def add_animation(self: Self, name: str, frames: list["SpriteFrame"], metadata: dict | None = None) -> None:
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
        if hasattr(self, 'pixels'):
            return self.pixels.copy()
        else:
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
        """String representation of the frame."""
        return f"SpriteFrame(size={self._image.get_size()}, duration={self.duration})"


class AnimatedSprite(AnimatedSpriteInterface):
    """A prototype Sprite Animation class."""

    log = LOG

    def __init__(self: Self, filename: str | None = None) -> None:
        """Initialize the Sprite Animation prototype."""
        super().__init__()
        self.name = "animated_sprite"  # Default name
        self._animations = {}  # animation_name -> list of frames
        self._current_animation = ""
        self._current_frame = 0
        self._is_playing = False
        self._is_looping = False
        self._frame_timer = 0.0

        if filename:
            self.load(filename)

    def __getitem__(self: Self, animation_name: str) -> "SpriteFrame":
        """Return the current frame of the specified animation."""
        if animation_name in self._animations and self._animations[animation_name]:
            return self._animations[animation_name][self._current_frame]
        return None

    def get_current_frame(self: Self) -> "SpriteFrame":
        """Return the current frame as a "SpriteFrame"."""
        if self._current_animation in self._animations and self._animations[self._current_animation]:
            return self._animations[self._current_animation][self._current_frame]
        return None

    # Sprite properties - return current frame's surface information
    @property
    def image(self: Self) -> pygame.Surface:
        """Return current frame's surface."""
        frame = self.get_current_frame()
        if frame:
            return frame.surface
        return pygame.Surface((32, 32))  # Default empty surface

    @property
    def rect(self: Self) -> pygame.Rect:
        """Return current frame's rect."""
        frame = self.get_current_frame()
        if frame:
            return frame.rect
        return pygame.Rect(0, 0, 32, 32)  # Default rect

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
        return {name: {} for name in self._animations.keys()}

    @property
    def frame_interval(self: Self) -> float:
        """Return the frame interval for the current animation."""
        if self._current_animation in self._animations and self._animations[self._current_animation]:
            frame = self._animations[self._current_animation][self._current_frame]
            return frame.duration
        return 0.5  # Default frame interval

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
        current_index = animation_names.index(self._current_animation) if self._current_animation in animation_names else -1
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
                self._current_frame = frame_index
                self._frame_timer = 0.0

    def set_animation(self: Self, animation_name: str) -> None:
        """Set the current animation."""
        if animation_name in self._animations:
            self._current_animation = animation_name
            self._current_frame = 0
            self._frame_timer = 0.0

    # Animation data methods
    def add_animation(self: Self, name: str, frames: list["SpriteFrame"], metadata: dict | None = None) -> None:
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
                    self._current_animation = list(self._animations.keys())[0]
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
        from glitchygames.tools.bitmappy import detect_file_format

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
        import configparser
        import pygame

        config = configparser.ConfigParser()
        config.read(filename)

        # Check if this is an animated sprite
        if not config.has_section('sprite'):
            raise ValueError(f"File {filename} is not a valid sprite file")

        sprite_type = config.get('sprite', 'type', fallback='static')
        if sprite_type != 'animated':
            raise ValueError(f"File {filename} is not an animated sprite file")

        # Get sprite name
        self.name = config.get('sprite', 'name', fallback='animated_sprite')

        # Clear existing animations
        self._animations = {}

        # Find all animation sections
        animation_sections = [section for section in config.sections() if section.startswith('animation_')]

        for anim_section in animation_sections:
            anim_name = anim_section.replace('animation_', '')
            frame_count = config.getint(anim_section, 'frame_count', fallback=0)

            frames = []
            for i in range(frame_count):
                frame_section = f'frame_{anim_name}_{i}'
                if config.has_section(frame_section):
                    # Get frame data
                    width = config.getint(frame_section, 'width', fallback=8)
                    height = config.getint(frame_section, 'height', fallback=8)
                    pixels_str = config.get(frame_section, 'pixels', fallback='')

                    # Create surface
                    surface = pygame.Surface((width, height))
                    surface.fill((255, 0, 255))  # Magenta background

                    # Parse pixel data
                    pixel_rows = pixels_str.split('\n')
                    pixels = []

                    for y, row in enumerate(pixel_rows):
                        if y < height:
                            for x, char in enumerate(row):
                                if x < width:
                                    # Convert character to color
                                    if char == 'R':  # Red
                                        color = (255, 0, 0)
                                    elif char == 'G':  # Green
                                        color = (0, 255, 0)
                                    elif char == 'B':  # Blue
                                        color = (0, 0, 255)
                                    else:  # Default to magenta
                                        color = (255, 0, 255)

                                    surface.set_at((x, y), color)
                                    pixels.append(color)
                                else:
                                    pixels.append((255, 0, 255))
                        else:
                            # Fill remaining rows with magenta
                            for x in range(width):
                                pixels.append((255, 0, 255))

                    # Create frame
                    frame = SpriteFrame(surface)
                    frame.pixels = pixels
                    frames.append(frame)

            if frames:
                self._animations[anim_name] = frames

        # Set current animation to first available
        if self._animations:
            self._current_animation = list(self._animations.keys())[0]
            self._current_frame = 0
        else:
            self._current_animation = ""
            self._current_frame = 0

    def _load_yaml(self: Self, filename: str) -> None:
        """Load animated sprite from YAML file."""
        # TODO: Implement YAML loading
        raise NotImplementedError("YAML loading not yet implemented")

    def _load_toml(self: Self, filename: str) -> None:
        """Load animated sprite from TOML file."""
        import toml
        import pygame

        # Load TOML data
        with open(filename, 'r') as f:
            data = toml.load(f)

        # Get sprite name
        self.name = data.get('sprite', {}).get('name', 'animated_sprite')

        # Clear existing animations
        self._animations = {}

        # Build color map from colors section
        color_map = {}
        colors_section = data.get('colors', {})
        for char, color_data in colors_section.items():
            r = color_data.get('red', 0)
            g = color_data.get('green', 0)
            b = color_data.get('blue', 0)
            color_map[char] = (r, g, b)

        # Process animations - each animation has its frames grouped
        animations = data.get('animation', [])
        self.log.debug(f"Found {len(animations)} animation(s) in TOML file")

        for anim_data in animations:
            anim_name = anim_data.get('namespace', 'default')
            frames_data = anim_data.get('frame', [])
            self.log.debug(f"Processing animation '{anim_name}' with {len(frames_data)} frame(s)")

            # Debug: Show animation namespace metadata
            self.log.debug(f"  Animation '{anim_name}' metadata:")
            for key, value in anim_data.items():
                if key != 'frame':  # Don't show the frame array
                    self.log.debug(f"    {key}: {value}")

            frames = []
            for frame_idx, frame_data in enumerate(frames_data):
                frame_index = frame_data.get('frame_index', frame_idx)
                self.log.debug(f"  Processing frame {frame_index} (data index {frame_idx})")

                # Get frame dimensions from pixel data
                pixel_data = frame_data.get('pixels', '')
                raw_lines = pixel_data.split('\n')

                # Pre-trim each line and filter out empty lines
                pixel_lines = [line.strip() for line in raw_lines if line.strip()]

                if not pixel_lines:
                    self.log.debug(f"    Skipping empty frame {frame_index}")
                    continue

                # Validate that all lines are the same length
                expected_width = len(pixel_lines[0])
                for i, line in enumerate(pixel_lines):
                    if len(line) != expected_width:
                        self.log.error(f"    Frame {frame_index}: Line {i} has {len(line)} pixels, expected {expected_width}")
                        raise ValueError(f"Inconsistent line length in frame {frame_index}: line {i} has {len(line)} pixels, expected {expected_width}")

                height = len(pixel_lines)
                width = expected_width
                self.log.debug(f"    Frame {frame_index}: {width}x{height} pixels")
                self.log.debug(f"    Processed: {len(pixel_lines)} lines of {width} pixels each")

                # Create surface
                surface = pygame.Surface((width, height))
                surface.fill((255, 0, 255))  # Magenta background

                # Parse pixel data
                pixels = []
                for y, row in enumerate(pixel_lines):
                    for x, char in enumerate(row):
                        if x < width and y < height:
                            # Get color from character
                            color = color_map.get(char, (255, 0, 255))  # Default to magenta
                            surface.set_at((x, y), color)
                            pixels.append(color)
                        else:
                            pixels.append((255, 0, 255))

                # Create frame
                frame = SpriteFrame(surface)
                frame.pixels = pixels
                frames.append(frame)
                self.log.debug(f"    Frame {frame_index} loaded successfully")

                # Debug: Show sanitized pixel data with hex coordinates
                self.log.debug(f"    Sanitized pixel data for frame {frame_index}:")

                # Show each line with hex Y coordinate
                for y, line in enumerate(pixel_lines):
                    self.log.debug(f"      {y:02x}: {line}")

                # Debug: Show frame metadata
                self.log.debug(f"    Frame {frame_index} metadata:")
                for key, value in frame_data.items():
                    if key != 'pixels':  # Don't repeat the pixel data
                        self.log.debug(f"      {key}: {value}")

            if frames:
                # Sort frames by frame_index if available
                frames.sort(key=lambda f: getattr(f, 'frame_index', 0))
                self._animations[anim_name] = frames
                self.log.debug(f"Animation '{anim_name}' loaded with {len(frames)} frame(s)")
            else:
                self.log.debug(f"Animation '{anim_name}' has no valid frames")

        # Set current animation to first available
        if self._animations:
            self._current_animation = list(self._animations.keys())[0]
            self._current_frame = 0
            self.log.debug(f"TOML load complete: {len(self._animations)} animation(s) loaded")
            for anim_name, frames in self._animations.items():
                self.log.debug(f"  Animation '{anim_name}': {len(frames)} frame(s)")
        else:
            self._current_animation = ""
            self._current_frame = 0
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
        import configparser

        config = configparser.ConfigParser()

        # Add sprite section (optional, only if there's a name)
        if self.name and self.name != 'animated_sprite':
            config.add_section('sprite')
            config.set('sprite', 'name', self.name)

        # Build color map from all frames using universal character set
        color_map = {}  # Maps RGB tuples to characters

        # Import the universal character set
        universal_chars = SPRITE_GLYPHS.strip()

        # Collect all unique colors from all frames and assign characters sequentially
        char_index = 0
        for anim_name, frames in self._animations.items():
            for frame in frames:
                pixels = frame.get_pixel_data()
                for r, g, b in pixels:
                    color_tuple = (r, g, b)
                    if color_tuple not in color_map:
                        if char_index >= len(universal_chars):
                            raise ValueError(f"Too many colors (max {len(universal_chars)})")
                        color_map[color_tuple] = universal_chars[char_index]
                        char_index += 1

        # Add animation data
        for anim_name, frames in self._animations.items():
            anim_section = f'animation_{anim_name}'
            config.add_section(anim_section)
            config.set(anim_section, 'namespace', anim_name)
            config.set(anim_section, 'frame_interval', '0.5')
            config.set(anim_section, 'loop', 'true')

            # Add frame data
            for i, frame in enumerate(frames):
                frame_section = f'frame_{anim_name}_{i}'
                config.add_section(frame_section)
                config.set(frame_section, 'namespace', anim_name)
                config.set(frame_section, 'frame_index', str(i))

                # Get pixel data
                pixels = frame.get_pixel_data()
                width, height = frame.get_size()

                # Convert pixels to character representation
                pixel_chars = []
                for y in range(height):
                    row = []
                    for x in range(width):
                        pixel_idx = y * width + x
                        if pixel_idx < len(pixels):
                            r, g, b = pixels[pixel_idx]
                            color_char = color_map.get((r, g, b), '.')
                            row.append(color_char)
                        else:
                            row.append('.')
                    pixel_chars.append(''.join(row))

                config.set(frame_section, 'pixels', '\n'.join(pixel_chars))

        # Add color definitions
        for color_tuple, char in sorted(color_map.items(), key=lambda x: x[1]):
            config.add_section(char)
            config.set(char, 'red', str(color_tuple[0]))
            config.set(char, 'green', str(color_tuple[1]))
            config.set(char, 'blue', str(color_tuple[2]))

        # Write to file
        with open(filename, 'w') as f:
            config.write(f)

    def _save_yaml(self: Self, filename: str) -> None:
        """Save animated sprite in YAML format."""
        import yaml

        # Create color mapping using universal character set
        color_map = {}

        # Import the universal character set
        universal_chars = SPRITE_GLYPHS.strip()

        # Collect all unique colors from all frames and assign characters sequentially
        char_index = 0
        for anim_name, frames in self._animations.items():
            for frame in frames:
                pixels = frame.get_pixel_data()
                for r, g, b in pixels:
                    color_tuple = (r, g, b)
                    if color_tuple not in color_map:
                        if char_index >= len(universal_chars):
                            raise ValueError(f"Too many colors (max {len(universal_chars)})")
                        color_map[color_tuple] = universal_chars[char_index]
                        char_index += 1

        # Build YAML data structure
        data = {
            'sprite': {
                'name': self.name or 'animated_sprite'
            },
            'colors': {},
            'animations': {}
        }

        # Add color definitions
        for (r, g, b), char in color_map.items():
            data['colors'][char] = {
                'red': r,
                'green': g,
                'blue': b
            }

        # Add animation data with pixel strings
        for anim_name, frames in self._animations.items():
            animation_data = {
                'frames': []
            }

            for frame in frames:
                pixels = frame.get_pixel_data()
                width, height = frame.get_size()

                # Convert pixels to character strings
                pixel_strings = []
                for y in range(height):
                    row = ""
                    for x in range(width):
                        pixel_index = y * width + x
                        if pixel_index < len(pixels):
                            r, g, b = pixels[pixel_index]
                            char = color_map.get((r, g, b), '.')
                            row += char
                        else:
                            row += '.'
                    pixel_strings.append(row)

                # Join pixel rows with spaces for folded block scalar
                pixel_data = ' '.join(pixel_strings)

                frame_data = {
                    'pixels': pixel_data,
                    'duration': frame.duration
                }
                animation_data['frames'].append(frame_data)

            data['animations'][anim_name] = animation_data

        # Write YAML with folded block scalars for pixel data
        with open(filename, 'w') as f:
            # Write header sections
            f.write("sprite:\n")
            f.write(f"  name: {data['sprite']['name']}\n")
            f.write(f"  type: {data['sprite'].get('type', 'animated')}\n\n")

            # Write colors section
            if 'colors' in data and data['colors']:
                f.write("colors:\n")
                for char, color_info in data['colors'].items():
                    f.write(f"  {char}:\n")
                    f.write(f"    red: {color_info['red']}\n")
                    f.write(f"    green: {color_info['green']}\n")
                    f.write(f"    blue: {color_info['blue']}\n")
                f.write("\n")

            # Write animations section with literal block scalars
            f.write("animations:\n")
            for anim_name, anim_data in data['animations'].items():
                f.write(f"  {anim_name}:\n")
                f.write("    frames:\n")
                for frame in anim_data['frames']:
                    f.write("    - frame:\n")
                    f.write("        duration: {}\n".format(frame['duration']))
                    f.write("        pixels: |\n")
                    # Split pixel data into individual rows and write each on its own line
                    pixel_rows = frame['pixels'].split(' ')
                    for row in pixel_rows:
                        f.write(f"          {row}\n")
                    f.write("\n")

    def _save_toml(self: Self, filename: str) -> None:
        """Save animated sprite in TOML format."""
        import toml

        # Create color mapping using universal character set
        color_map = {}

        # Import the universal character set
        universal_chars = SPRITE_GLYPHS.strip()

        # Collect all unique colors from all frames and assign characters sequentially
        char_index = 0
        for anim_name, frames in self._animations.items():
            for frame in frames:
                pixels = frame.get_pixel_data()
                for r, g, b in pixels:
                    color_tuple = (r, g, b)
                    if color_tuple not in color_map:
                        if char_index >= len(universal_chars):
                            raise ValueError(f"Too many colors (max {len(universal_chars)})")
                        color_map[color_tuple] = universal_chars[char_index]
                        char_index += 1

        # Build TOML data structure
        data = {
            'sprite': {
                'name': self.name or 'animated_sprite'
            },
            'colors': {},
            'animation': []
        }

        # Add color definitions
        for (r, g, b), char in color_map.items():
            data['colors'][char] = {
                'red': r,
                'green': g,
                'blue': b
            }

        # Add animations - group frames under each animation
        for anim_name, frames in self._animations.items():
            animation_frames = []

            for i, frame in enumerate(frames):
                # Get pixel data
                pixels = frame.get_pixel_data()
                width, height = frame.get_size()

                # Convert pixels to character representation
                pixel_chars = []
                for y in range(height):
                    row = []
                    for x in range(width):
                        pixel_idx = y * width + x
                        if pixel_idx < len(pixels):
                            r, g, b = pixels[pixel_idx]
                            color_char = color_map.get((r, g, b), '.')
                            row.append(color_char)
                        else:
                            row.append('.')
                    pixel_chars.append(''.join(row))

                # Create frame data
                frame_data = {
                    'frame_index': i,
                    'pixels': '\n'.join(pixel_chars)
                }
                animation_frames.append(frame_data)

            # Create animation entry with all frames
            animation_entry = {
                'namespace': anim_name,
                'frame_interval': 0.5,
                'loop': True,
                'frame': animation_frames
            }

            data['animation'].append(animation_entry)

        # Write to file with proper formatting and block strings
        with open(filename, 'w') as f:
            # Write sprite section first
            f.write('[sprite]\n')
            f.write(f'name = "{data["sprite"]["name"]}"\n\n')

            # Write animations with proper TOML array syntax
            for animation in data['animation']:
                f.write('[[animation]]\n')
                f.write(f'namespace = "{animation["namespace"]}"\n')
                f.write(f'frame_interval = {animation["frame_interval"]}\n')
                f.write(f'loop = {str(animation["loop"]).lower()}\n\n')

                for frame in animation['frame']:
                    f.write('[[animation.frame]]\n')
                    f.write(f'namespace = "{animation["namespace"]}"\n')
                    f.write(f'frame_index = {frame["frame_index"]}\n')
                    f.write('pixels = """\n')
                    f.write(frame['pixels'])
                    f.write('\n"""\n\n')

            # Write colors section at the end
            if data['colors']:
                f.write('[colors]\n')
                for char, color in data['colors'].items():
                    f.write(f'[colors."{char}"]\n')
                    f.write(f'red = {color["red"]}\n')
                    f.write(f'green = {color["green"]}\n')
                    f.write(f'blue = {color["blue"]}\n\n')

    def update(self: Self, dt: float) -> None:
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
        current_frame = self.get_current_frame()

        if current_frame and self._frame_timer >= current_frame.duration:
            # Move to next frame
            self._frame_timer = 0.0
            self._current_frame += 1

            # Check if we've reached the end
            if self._current_frame >= len(frames):
                if self._is_looping:
                    self._current_frame = 0
                else:
                    self._current_frame = len(frames) - 1
                    self._is_playing = False
