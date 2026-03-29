"""BitmappySprite and singleton sprite classes for Glitchy Games Engine.

This module contains:
- BitmappySprite: Sprite that loads from TOML config files
- Singleton: Generic singleton pattern
- SingletonBitmappySprite: Singleton sprite for mouse pointers, etc.
- FocusableSingletonBitmappySprite: Singleton sprite with keyboard focus
"""

from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, Self, cast, override

if TYPE_CHECKING:
    from glitchygames.events.base import HashableEvent

import pygame
import tomli_w

from .constants import DEFAULT_FILE_FORMAT, SPRITE_GLYPHS
from .sprite import Sprite

LOG = logging.getLogger('game.sprites')

# Error message constants for TRY003 compliance
_ERR_CANNOT_CREATE_SURFACE = "Can't create Surface(({width}, {height}))."
_ERR_ANIMATED_SPRITE_USE_CORRECT_CLASS = (
    'File {filename} contains animated sprite data. '
    'Use AnimatedSprite class instead of BitmappySprite.'
)
_ERR_UNSUPPORTED_FORMAT_TOML_ONLY = (
    'Unsupported file format: {file_format}. Only TOML format is supported.'
)
_ERR_TOO_MANY_COLORS = 'Too many colors: {color_count} > {max_glyphs}'
_ERR_UNSUPPORTED_FORMAT = 'Unsupported format: {file_format}'


class BitmappySprite(Sprite):
    """A sprite that loads from a Bitmappy config file."""

    DEBUG: bool = False
    DEFAULT_SURFACE_W = 42
    DEFAULT_SURFACE_H = 42
    DEFAULT_SURFACE = pygame.Surface((DEFAULT_SURFACE_W, DEFAULT_SURFACE_H))

    # Use the universal character set from constants
    from .constants import SPRITE_GLYPHS

    def __init__(  # noqa: PLR0913
        self: Self,
        x: float = 0,
        y: float = 0,
        width: float = 32,
        height: float = 32,
        *,
        name: str | None = None,
        filename: str | None = None,
        focusable: bool = False,
        parent: object | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Subclass to load sprite files.

        Args:
            x: the x coordinate of the sprite.
            y: the y coordinate of the sprite.
            width: the width of the sprite.
            height: the height of the sprite.
            name: optional, the name of the sprite.
            filename: optional, the BitmappySprite config to load.
            focusable: optional, whether or not the sprite can receive focus.
            parent: optional, the parent of the sprite.
            groups: optional, the sprite groups to add the sprite to.

        Raises:
            error: If a Surface cannot be created with the given dimensions.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        # Initialize before super().__init__() because subclass __init__
        # methods may call update_text() or update() before returning,
        # and those methods check is_active.
        self.is_active: bool = False
        self.focusable: bool = focusable
        self.filename: str = filename or ''

        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            parent=parent,
            groups=groups,
        )

        # Initialize pixel data attributes
        self.pixels: list[tuple[int, ...]] = []
        self.pixels_across: int = int(width)
        self.pixels_tall: int = int(height)

        # Try to load a file if one was specified, otherwise
        # if a width and height is specified, make a surface.
        if filename:
            (self.image, self.rect, self.name) = self.load(filename=filename)
            self.width = self.rect.width
            self.height = self.rect.height

        elif self.width and self.height:
            self.image = pygame.Surface((self.width, self.height))
            self.image.convert()
        else:
            raise pygame.error(
                _ERR_CANNOT_CREATE_SURFACE.format(width=self.width, height=self.height),
            )

        self.rect = self.image.get_rect()
        self.parent = parent
        self.rect.x = x
        self.rect.y = y
        self.proxies = [self.parent]

    def load(
        self: Self,
        filename: str | None = None,
    ) -> tuple[pygame.Surface, pygame.FRect | pygame.Rect, str]:
        """Load a sprite from a Bitmappy config file using the factory.

        Returns:
            tuple[pygame.Surface, pygame.FRect | pygame.Rect, str]: The result.

        """
        self.log.debug('=== Starting load from %s ===', filename)

        # Use the factory to load sprite (always returns AnimatedSprite now)
        try:
            from .factory import SpriteFactory

            animated_sprite = SpriteFactory.load_sprite(filename=filename)

            # Convert AnimatedSprite to BitmappySprite format
            # Get the current frame surface from the animated sprite
            current_frame = animated_sprite.get_current_frame()
            if current_frame and hasattr(current_frame, 'surface'):
                self.image = cast('pygame.Surface', current_frame.surface)  # type: ignore[attr-defined]
            else:
                # Fallback: create surface from animated sprite's image
                assert animated_sprite.image is not None, 'AnimatedSprite must have an image'
                self.image = animated_sprite.image.copy()

            self.rect = self.image.get_rect()
            self.name = animated_sprite.name
            self.width = self.rect.width
            self.height = self.rect.height
        except ValueError as e:
            # If factory fails, fall back to old static-only loading
            self.log.debug('Factory failed, falling back to static-only loading: %s', e)
            assert filename is not None, 'filename must be provided for static-only loading'
            return self._load_static_only(filename)
        else:
            return (self.image, self.rect, self.name)

    @staticmethod
    def _raise_animated_sprite_error(filename: str) -> None:
        """Raise an error for animated sprite files.

        Raises:
            ValueError: Always raised to indicate an animated sprite was loaded incorrectly.

        """
        raise ValueError(
            _ERR_ANIMATED_SPRITE_USE_CORRECT_CLASS.format(filename=filename),
        )

    def _load_static_only(self: Self, filename: str) -> tuple[pygame.Surface, pygame.Rect, str]:
        """Load a static sprite from a Bitmappy config file (legacy method).

        Returns:
            tuple[pygame.Surface, pygame.Rect, str]: The result.

        Raises:
            ValueError: If the file format is not supported.

        """
        self.log.debug('=== Starting static-only load from %s ===', filename)

        # Detect file format and handle accordingly
        from .factory import SpriteFactory

        file_format = SpriteFactory.detect_file_format(filename)

        if file_format == 'toml':
            return self._load_static_toml(filename)
        raise ValueError(
            _ERR_UNSUPPORTED_FORMAT_TOML_ONLY.format(file_format=file_format),
        )

    def _raise_too_many_colors_error(self, color_count: int) -> None:
        """Raise an error for too many colors.

        Raises:
            ValueError: If the color count exceeds the maximum number of sprite glyphs.

        """
        raise ValueError(
            _ERR_TOO_MANY_COLORS.format(color_count=color_count, max_glyphs=len(SPRITE_GLYPHS)),
        )

    def _load_static_toml(self: Self, filename: str) -> tuple[pygame.Surface, pygame.Rect, str]:
        """Load a static sprite from a TOML file.

        Returns:
            tuple[pygame.Surface, pygame.Rect, str]: The result.

        """
        # Read the raw file content first
        raw_content = Path(filename).read_text(encoding='utf-8')
        self.log.debug(f'Raw file content ({len(raw_content)} bytes):\n{raw_content}')

        # Parse TOML
        data = tomllib.loads(raw_content)
        self.log.debug(f'TOML data keys: {list(data.keys())}')

        try:
            name = data['sprite']['name']
            self.log.debug('Sprite name: %s', name)

            # Get pixel data
            pixel_text = str(data['sprite']['pixels'])
            self.log.debug(f'Raw pixel text ({len(pixel_text)} bytes):\n{pixel_text}')

            # Split into rows and process each row
            rows: list[str] = []
            for i, raw_row in enumerate(pixel_text.split('\n')):
                row = raw_row.strip()
                if row:  # Only add non-empty rows
                    rows.append(row)
                    self.log.debug(f"Row {i}: '{row}' (len={len(row)})")

            self.log.debug(f'Total rows processed: {len(rows)}')

            # Calculate dimensions
            width = len(rows[0]) if rows else 0
            height = len(rows)
            self.log.debug('Calculated dimensions: %sx%s', width, height)

            # Get color definitions
            color_map: dict[str, Any] = {}
            if 'colors' in data:
                for color_key, color_data in data['colors'].items():
                    red = color_data['red']
                    green = color_data['green']
                    blue = color_data['blue']
                    color_map[str(color_key)] = (red, green, blue)
                    self.log.debug(
                        "Color map entry: '%s' -> RGB(%s, %s, %s)",
                        color_key,
                        red,
                        green,
                        blue,
                    )

            self.log.debug(f'Total colors in map: {len(color_map)}')

            # Create image and rect
            self.log.debug('Creating image and rect...')
            (image, rect) = self.inflate(
                width=width,
                height=height,
                pixels=rows,
                color_map=color_map,
            )
            self.log.debug(f'Created image size: {image.get_size()}')
            self.log.debug('Created rect: %s', rect)

        except Exception:
            self.log.exception('Error in TOML load')
            raise
        else:
            # Return the successfully loaded sprite data
            return (image, rect, str(name))

    @classmethod
    def inflate(
        cls: Any,
        width: int,
        height: int,
        pixels: list[str],
        color_map: dict[str, Any],
    ) -> tuple[pygame.Surface, pygame.Rect]:
        """Inflate a sprite from a list of pixels.

        Args:
            width: the width of the sprite.
            height: the height of the sprite.
            pixels: the list of pixels.
            color_map: the color map.

        Returns:
            A tuple containing the sprite's image and rect.

        Raises:
            None

        """
        image = pygame.Surface((width, height))
        image.convert()

        raw_pixels: list[Any] = []
        for y, row in enumerate(pixels):
            for x, pixel in enumerate(row):
                color = color_map[pixel]
                raw_pixels.append(color)
                pygame.draw.rect(image, color, (x, y, 1, 1))

        return (image, image.get_rect())

    def save(self: Self, filename: str, file_format: str = DEFAULT_FILE_FORMAT) -> None:
        """Save a sprite to a file using the factory for backwards compatibility."""
        self.log.debug('Starting save in %s format to %s', file_format, filename)

        # Use the factory to save the sprite
        from .factory import SpriteFactory

        SpriteFactory.save_sprite(sprite=self, filename=filename, file_format=file_format)

        self.log.debug('Successfully saved to %s', filename)

    def _save(self: Self, filename: str, file_format: str = DEFAULT_FILE_FORMAT) -> None:
        """Save static sprite to file."""
        self._save_static_only(filename, file_format)

    def _load(self: Self, filename: str) -> tuple[pygame.Surface, pygame.Rect, str]:
        """Load static sprite from file.

        Returns:
            tuple[pygame.Surface, pygame.Rect, str]: The result.

        """
        return self._load_static_only(filename)

    def _save_static_only(
        self: Self,
        filename: str,
        file_format: str = DEFAULT_FILE_FORMAT,
    ) -> None:
        """Save a static sprite to a file (legacy method).

        Currently only supports TOML format. To add new formats:
        1. Add format detection in _detect_file_format()
        2. Add save logic here (e.g., _save_json(), _save_xml())
        3. Add load methods in _load_static_only()
        4. Update tests
        See LOADER_README.md for detailed implementation guide.
        """
        try:
            self.log.debug('Starting static-only save in %s format to %s', file_format, filename)
            config = self.deflate(file_format=file_format)
            self.log.debug('Got config from deflate: %s', config)

            if file_format == 'toml':
                self.log.debug('About to write TOML')
                with Path(filename).open('wb') as toml_file:
                    tomli_w.dump(config, toml_file)
                self.log.debug('TOML write complete')
            else:
                self._raise_unsupported_format_error(file_format)

            self.log.debug('Successfully saved to %s', filename)

        except Exception:
            self.log.exception('Error in save')
            raise

    def _validate_and_normalize_pixels(
        self: Self,
        pixels_across: int,
        pixels_tall: int,
    ) -> None:
        """Validate and normalize the pixel list to match expected dimensions.

        Pads with magenta (255, 0, 255) if too short, truncates if too long.

        Args:
            pixels_across: Number of pixels across.
            pixels_tall: Number of pixels tall.

        """
        expected_pixels = pixels_across * pixels_tall

        # Ensure pixels attribute exists
        if not hasattr(self, 'pixels'):
            self.pixels = []

        # Validate pixels list
        if len(self.pixels) != expected_pixels:
            self.log.error(
                f'Pixels list length mismatch: {len(self.pixels)} vs expected {expected_pixels}',
            )
            # Pad with default color if too short
            if len(self.pixels) < expected_pixels:
                self.pixels.extend([(255, 0, 255)] * (expected_pixels - len(self.pixels)))
            # Truncate if too long
            elif len(self.pixels) > expected_pixels:
                self.pixels = self.pixels[:expected_pixels]

    def deflate(self: Self, file_format: str = 'toml') -> dict[str, Any]:
        """Deflate a sprite to a configuration format.

        Currently only supports TOML format. To add new formats:
        1. Add format detection in _detect_file_format()
        2. Add deflate logic here (e.g., _deflate_json(), _deflate_xml())
        3. Add inflate methods in _load_static_only()
        4. Update tests
        See LOADER_README.md for detailed implementation guide.

        Returns:
            dict: The result.

        """
        try:
            self.log.debug(f'Starting deflate for {self.name} in {file_format} format')

            # Handle empty surfaces
            pixels_across: int = int(getattr(self, 'pixels_across', self.width))
            pixels_tall: int = int(getattr(self, 'pixels_tall', self.height))
            expected_pixels = pixels_across * pixels_tall

            if expected_pixels == 0:
                # Return minimal config for empty surface
                if file_format == 'toml':
                    return {
                        'sprite': {
                            'name': self.name,
                            'pixels_across': 0,
                            'pixels_tall': 0,
                            'pixels': [],
                        },
                    }
                self._raise_unsupported_format_error(file_format)

            self._validate_and_normalize_pixels(pixels_across, pixels_tall)

            # Get unique colors from the pixels list
            unique_colors = set(self.pixels)
            self.log.debug(f'Found {len(unique_colors)} unique colors')
            self.log.debug(f'Pixels list length: {len(self.pixels)}')
            self.log.debug(f'Expected pixels: {pixels_across * pixels_tall}')
            self.log.debug(f'Sample pixels: {self.pixels[:10]}')

            # Check if there are too many colors
            if len(unique_colors) > len(SPRITE_GLYPHS):
                self._raise_too_many_colors_error(len(unique_colors))

            # Create color to character mapping using the helper method
            color_map = self._create_color_map()

            # Process pixels row by row
            pixel_rows = self._process_pixel_rows(color_map, pixels_across, pixels_tall)

            # Create configuration based on format
            if file_format == 'toml':
                config = self._create_toml_config(pixel_rows, color_map)
            else:
                self._raise_unsupported_format_error(file_format)

        except Exception:
            self.log.exception('Error in deflate')
            raise
        else:
            # Return the successfully created configuration
            return config

    def _process_pixel_rows(
        self,
        color_map: dict[str, Any],
        pixels_across: int | None = None,
        pixels_tall: int | None = None,
    ) -> list[str]:
        """Process pixels into rows of characters.

        Args:
            color_map: Mapping of colors to characters
            pixels_across: Number of pixels across
                (optional, uses self.pixels_across if not provided)
            pixels_tall: Number of pixels tall
                (optional, uses self.pixels_tall if not provided)

        Returns:
            List of pixel rows as strings

        """
        if pixels_across is None:
            pixels_across = int(getattr(self, 'pixels_across', self.width))
        if pixels_tall is None:
            pixels_tall = int(getattr(self, 'pixels_tall', self.height))

        # These are guaranteed to be int after the fallbacks above
        assert pixels_across is not None, 'pixels_across must be set'
        assert pixels_tall is not None, 'pixels_tall must be set'

        pixel_rows: list[str] = []
        for y in range(pixels_tall):
            row = ''
            for x in range(pixels_across):
                pixel_color = self.pixels[y * pixels_across + x]
                # Find the character for this color
                char = '.'
                for ch, color in color_map.items():
                    if color == pixel_color:
                        char = ch
                        break
                else:
                    self.log.error('Color %s not found in color_map', pixel_color)
                row += char
            pixel_rows.append(row)
            self.log.debug(f"Row {y}: '{row}' (len={len(row)})")
        return pixel_rows

    def _generate_pixel_rows(
        self,
        color_map: dict[str, Any] | None = None,
    ) -> tuple[list[str], dict[str, Any]]:
        """Generate pixel rows from the sprite's pixel data.

        Args:
            color_map: Mapping of colors to characters (optional, will be generated if not provided)

        Returns:
            Tuple of (pixel_rows list, color_map dict)

        """
        if color_map is None:
            color_map = self._create_color_map()

        # Process pixels into rows
        pixel_rows: list[str] = []
        # Use height and width if pixels_tall/pixels_across not available
        pixels_tall: int = int(getattr(self, 'pixels_tall', self.height))
        pixels_across: int = int(getattr(self, 'pixels_across', self.width))

        for y in range(pixels_tall):
            row: str = ''
            for x in range(pixels_across):
                pixel_index = y * pixels_across + x
                if pixel_index < len(self.pixels):
                    pixel_color = self.pixels[pixel_index]
                    matched_char: str = cast('str', color_map.get(pixel_color, '.'))  # type: ignore[arg-type] # ty: ignore[no-matching-overload]
                    row += matched_char
                else:
                    row += '.'  # Default character for missing pixels
            pixel_rows.append(row)

        return pixel_rows, color_map

    def _create_toml_config(
        self,
        pixel_rows: list[str] | None = None,
        color_map: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create TOML configuration.

        Args:
            pixel_rows: List of pixel rows as strings (optional, will be generated if not provided)
            color_map: Mapping of colors to characters (optional, will be generated if not provided)

        Returns:
            TOML configuration dictionary

        To add new formats, create similar methods like _create_json_config(), _create_xml_config()
        See LOADER_README.md for detailed implementation guide.

        """
        # Generate pixel_rows and color_map if not provided
        if pixel_rows is None:
            if not hasattr(self, 'pixels') or not self.pixels:
                pixel_rows = []
            else:
                pixel_rows, color_map = self._generate_pixel_rows(color_map)

        if color_map is None:
            color_map = self._create_color_map()

        pixels_str = '\n'.join(pixel_rows)
        return {
            'sprite': {'name': self.name or 'unnamed', 'pixels': pixels_str},
            'colors': {
                char: {'red': color[0], 'green': color[1], 'blue': color[2]}
                for char, color in color_map.items()
            },
        }

    @staticmethod
    def _raise_unsupported_format_error(file_format: str) -> NoReturn:
        """Raise an error for unsupported file format.

        Raises:
            ValueError: Always raised to indicate an unsupported file format.

        """
        raise ValueError(_ERR_UNSUPPORTED_FORMAT.format(file_format=file_format))

    def _create_color_map(self: Self) -> dict[str, Any]:
        """Create a color map from the sprite's pixels.

        Returns:
            dict: Mapping of colors to characters

        """
        if not hasattr(self, 'pixels') or not self.pixels:
            return {}

        # Get unique colors from the pixels list
        unique_colors = set(self.pixels)
        color_map: dict[str, Any] = {}

        # Filter out dangerous characters that could break file formats
        dangerous_chars = {'\n', '\r', '\t', '\0', '\b', '\f', '\v', '\a'}
        printable_chars = ''.join(c for c in SPRITE_GLYPHS if c not in dangerous_chars)

        # Assign characters sequentially from SPRITE_CHARS
        for char_index, color in enumerate(unique_colors):
            if char_index >= len(printable_chars):
                break
            char = printable_chars[char_index]
            # Double-check that the character is safe
            if char in dangerous_chars or not char.isprintable():
                char = '.'
            color_map[char] = color

        # Always include the magenta padding color (255, 0, 255) with a special character
        padding_color = (255, 0, 255)
        if padding_color in unique_colors and padding_color not in color_map.values():
            # Use a special character for padding (like 'X' or '#')
            padding_char = 'X' if 'X' not in color_map else '#'
            color_map[padding_char] = padding_color

        return color_map

    def _inflate_toml(self: Self, filename: str) -> dict[str, Any]:
        """Inflate a sprite from a TOML file.

        Args:
            filename: Path to the TOML file

        Returns:
            dict: Sprite data dictionary

        """
        # Read the raw file content first
        raw_content = Path(filename).read_text(encoding='utf-8')
        self.log.debug(f'Raw file content ({len(raw_content)} bytes):\n{raw_content}')

        # Parse TOML
        data = tomllib.loads(raw_content)
        self.log.debug(f'TOML data keys: {list(data.keys())}')

        try:
            name = data['sprite']['name']
            self.log.debug('Sprite name: %s', name)

            # Get pixel data
            pixel_text = str(data['sprite']['pixels'])
            self.log.debug(f'Raw pixel text ({len(pixel_text)} bytes):\n{pixel_text}')

            # Split into rows and process each row
            rows: list[str] = []
            for i, raw_row in enumerate(pixel_text.split('\n')):
                row = raw_row.strip()
                if row:  # Only add non-empty rows
                    rows.append(row)
                    self.log.debug(f"Row {i}: '{row}' (len={len(row)})")

            self.log.debug(f'Total rows processed: {len(rows)}')

            # Calculate dimensions
            width = len(rows[0]) if rows else 0
            height = len(rows)
            self.log.debug('Calculated dimensions: %sx%s', width, height)

            # Get color definitions
            color_map: dict[str, Any] = {}
            if 'colors' in data:
                for color_key, color_data in data['colors'].items():
                    red = color_data['red']
                    green = color_data['green']
                    blue = color_data['blue']
                    color_map[str(color_key)] = (red, green, blue)
                    self.log.debug(
                        "Color map entry: '%s' -> RGB(%s, %s, %s)",
                        color_key,
                        red,
                        green,
                        blue,
                    )

            self.log.debug(f'Total colors in map: {len(color_map)}')

            # Convert rows to pixels
            pixels: list[tuple[int, int, int]] = []
            for row in rows:
                for char in row:
                    if char in color_map:
                        pixels.append(color_map[char])
                    else:
                        # Default color for unknown characters
                        pixels.append((255, 0, 255))

            return {'pixels': pixels, 'width': width, 'height': height, 'name': str(name)}

        except Exception:
            self.log.exception('Error in TOML inflate')
            raise

    def inflate_from_file(self: Self, filename: str) -> dict[str, Any]:
        """Inflate a sprite from a file.

        Args:
            filename: Path to the sprite file

        Returns:
            dict: Sprite data dictionary

        Raises:
            ValueError: If the file format is not supported.

        """
        # Detect file format and handle accordingly
        from .factory import SpriteFactory

        file_format = SpriteFactory.detect_file_format(filename)

        if file_format == 'toml':
            return self._inflate_toml(filename)
        raise ValueError(_ERR_UNSUPPORTED_FORMAT.format(file_format=file_format))

    @override
    def on_left_mouse_drag_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle a left mouse drag event.

        Args:
            event (HashableEvent): The event to handle.
            trigger (HashableEvent): The event that triggered the drag.

        """
        self.log.debug(f'{type(self)}: Left Mouse Drag Event: {event} @ {self} for {trigger}')

    @override
    def on_middle_mouse_drag_event(
        self: Self,
        event: HashableEvent,
        trigger: HashableEvent,
    ) -> None:
        """Handle a middle mouse drag event.

        Args:
            event (HashableEvent): The event to handle.
            trigger (HashableEvent): The event that triggered the drag.

        """
        self.log.debug(f'{type(self)}: Middle Mouse Drag Event: {event} @ {self} for {trigger}')

    @override
    def on_right_mouse_drag_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle a right mouse drag event.

        Args:
            event (HashableEvent): The event to handle.
            trigger (HashableEvent): The event that triggered the drag.

        """
        self.log.debug(f'{type(self)}: Right Mouse Drag Event: {event} @ {self} for {trigger}')

    @override
    def on_left_mouse_drop_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle a left mouse drop event.

        Args:
            event (HashableEvent): The event to handle.
            trigger (HashableEvent): The event that triggered the drop.

        """
        self.log.debug(f'{type(self)}: Left Mouse Drop Event: {event} @ {self} for {trigger}')

    @override
    def on_middle_mouse_drop_event(
        self: Self,
        event: HashableEvent,
        trigger: HashableEvent,
    ) -> None:
        """Handle a middle mouse drop event.

        Args:
            event (HashableEvent): The event to handle.
            trigger (HashableEvent): The event that triggered the drop.

        """
        self.log.debug(f'{type(self)}: Middle Mouse Drop Event: {event} @ {self} for {trigger}')

    @override
    def on_right_mouse_drop_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle a right mouse drop event.

        Args:
            event (HashableEvent): The event to handle.
            trigger (HashableEvent): The event that triggered the drop.

        """
        self.log.debug(f'{type(self)}: Right Mouse Drop Event: {event} @ {self} for {trigger}')

    @override
    def on_mouse_drag_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle a mouse drag event.

        Args:
            event (HashableEvent): The event to handle.
            trigger (HashableEvent): The event that triggered the drag.

        """
        self.log.debug(f'{type(self)}: Mouse Drag Event: {event} @ {self} for {trigger}')

    @override
    def on_mouse_drop_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle a mouse drop event.

        Args:
            event (HashableEvent): The event to handle.
            trigger (HashableEvent): The event that triggered the drop.

        """
        self.log.debug(f'{type(self)}: Mouse Drop Event: {event} @ {self} for {trigger}')

    @override
    def on_mouse_wheel_event(self: Self, event: HashableEvent) -> None:
        """Handle a mouse wheel event.

        Args:
            event (HashableEvent): The event to handle.

        """
        self.log.debug(f'{type(self)}: Mouse Wheel Event: {event} @ {self}')

    @override
    def on_mouse_chord_down_event(
        self: Self,
        event: HashableEvent,
        keys: list[int] | None = None,
    ) -> None:
        """Handle a mouse chord down event.

        Args:
            event (HashableEvent): The event to handle.
            keys (list[int] | None): The keys that were pressed.

        """
        self.log.debug(f'{type(self)}: Mouse Chord Down Event: {event} @ {self} for {keys}')

    @override
    def on_mouse_chord_up_event(
        self: Self,
        event: HashableEvent,
        keys: list[int] | None = None,
    ) -> None:
        """Handle a mouse chord up event.

        Args:
            event (HashableEvent): The event to handle.
            keys (list[int] | None): The keys that were pressed.

        """
        self.log.debug(f'{type(self)}: Mouse Chord Up Event: {event} @ {self} for {keys}')

    def _render_animated_str(self: Self, toml_data: dict[str, Any]) -> str:
        """Render an animated sprite's TOML data to a colorized ASCII string.

        Args:
            toml_data: Parsed TOML data containing animation and colors sections.

        Returns:
            str: Colorized representation of all animation frames.

        """
        from glitchygames.tools.ascii_renderer import ASCIIRenderer

        output_lines: list[str] = []

        # Show sprite header once
        if 'sprite' in toml_data and 'name' in toml_data['sprite']:
            output_lines.extend((
                '[sprite]',
                f'name = "{toml_data["sprite"]["name"]}"',
                '',
            ))

        # Show all animations and frames
        animations: list[dict[str, Any]] = list(toml_data['animation'])
        for anim_idx, animation in enumerate(animations):
            namespace: str = animation.get('namespace', f'animation_{anim_idx}')
            output_lines.extend((
                f'# Namespace: {namespace}',
                '',
            ))

            if 'frame' not in animation:
                output_lines.extend(('# No frames found in this animation', ''))
                continue

            frames: list[dict[str, Any]] = list(animation['frame'])
            for frame_idx, frame in enumerate(frames):
                output_lines.append(f'# Frame {frame_idx}:')

                if 'pixels' not in frame:
                    output_lines.extend(('# No pixels data in this frame', ''))
                    continue

                # Create a temporary sprite data for this frame
                frame_data: dict[str, Any] = {
                    'sprite': {
                        'name': toml_data.get('sprite', {}).get('name', 'unnamed'),
                        'pixels': frame['pixels'],
                    },
                    'colors': toml_data.get('colors', {}),
                }

                # Render this frame with colorized output
                renderer = ASCIIRenderer()
                frame_result = renderer.render_sprite(frame_data)
                output_lines.extend((frame_result, ''))

        return '\n'.join(output_lines)

    @override
    def __str__(self: Self) -> str:
        """Return a colorized ASCII representation of the sprite.

        Returns:
            str: Colorized TOML representation of the sprite with all frames

        """
        try:
            # Import here to avoid circular imports
            from glitchygames.tools.ascii_renderer import ASCIIRenderer

            # Load TOML data from file
            if not self.filename:
                return f'{type(self)} "{self.name}" (no file loaded)'

            with Path(self.filename).open('rb') as f:
                toml_data = tomllib.load(f)

            # Check if it's an animated sprite and show all frames
            if 'animation' in toml_data and len(toml_data['animation']) > 0:
                return self._render_animated_str(toml_data)
            # Static sprite - show normally
            renderer = ASCIIRenderer()
            return renderer.render_sprite(toml_data)

        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            # Fallback to basic representation if rendering fails
            return f'{type(self)} "{self.name}" (error rendering: {e})'


class Singleton:
    """A generic singleton class."""

    __instance__ = None

    def __new__(cls: Any, *args: object, **kwargs: object) -> Self:  # type: ignore[reportGeneralTypeIssues]
        """Create a new instance of the Singleton.

        Args:
            *args: The arguments to pass to the constructor.
            **kwargs: The keyword arguments to pass to the constructor.

        Returns:
            Singleton: The instance of the Singleton.

        """
        if cls.__instance__ is None:
            cls.__instance__ = object.__new__(cls)
        cls.__instance__.args = args
        cls.__instance__.kwargs = kwargs
        return cast('Singleton', cls.__instance__)  # type: ignore[return-value] # ty: ignore[invalid-return-type]


# This is a root class for sprites that should be singletons, like
#  MousePointer class.
class SingletonBitmappySprite(BitmappySprite):
    """A singleton class for handling singleton sprites, like mouse pointers."""

    __instance__ = None

    def __new__(cls: Any, *_args: Any, **_kwargs: Any) -> Self:  # type: ignore[reportGeneralTypeIssues]
        """Create a new instance of the SingletonBitmappySprite.

        Returns:
            SingletonBitmappySprite: The instance of the SingletonBitmappySprite.

        """
        if cls.__instance__ is None:
            cls.__instance__ = object.__new__(cls)
        return cast('SingletonBitmappySprite', cls.__instance__)  # type: ignore[return-value] # ty: ignore[invalid-return-type]

    def __init__(  # noqa: PLR0913
        self: Self,
        x: int = 0,
        y: int = 0,
        width: int = 32,
        height: int = 32,
        *,
        name: str | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize the SingletonBitmappySprite.

        Args:
            x (int): The x coordinate of the sprite.
            y (int): The y coordinate of the sprite.
            width (int): The width of the sprite.
            height (int): The height of the sprite.
            name (str): The name of the sprite.
            groups (pygame.sprite.LayeredDirty[Any]): The sprite groups.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(x=x, y=y, width=width, height=height, name=name, groups=groups)


# This is a root class for focusable sprites that should be singletons, like
# the MenuBar class.
class FocusableSingletonBitmappySprite(BitmappySprite):
    """A singleton class for handling all of the focusable sprite behaviors."""

    __instance__ = None

    def __new__(cls: Any, *_args: Any, **_kwargs: Any) -> Self:  # type: ignore[reportGeneralTypeIssues]
        """Create a new instance of the FocusableSingletonBitmappySprite.

        Returns:
            FocusableSingletonBitmappySprite: The instance.

        """
        if cls.__instance__ is None:
            cls.__instance__ = object.__new__(cls)
        return cast('FocusableSingletonBitmappySprite', cls.__instance__)  # type: ignore[return-value] # ty: ignore[invalid-return-type]

    def __init__(  # noqa: PLR0913
        self: Self,
        x: float = 0,
        y: float = 0,
        width: float = 32,
        height: float = 32,
        *,
        name: str | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize the FocusableSingletonBitmappySprite.

        Args:
            x (int | float): The x coordinate of the sprite.
            y (int | float): The y coordinate of the sprite.
            width (int): The width of the sprite.
            height (int): The height of the sprite.
            name (str): The name of the sprite.
            groups (pygame.sprite.LayeredDirty[Any]): The sprite groups.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            focusable=True,
            groups=groups,
        )


# Add helper methods to BitmappySprite for AI training data extraction
def _get_pixel_string(self: BitmappySprite) -> str:
    """Get pixel data as a string for AI training.

    Returns:
        str: The pixel string.

    """
    if not hasattr(self, 'pixels') or not self.pixels:
        return ''

    # Convert pixels to character representation
    pixel_string = ''
    for y in range(self.pixels_tall):
        for x in range(self.pixels_across):
            pixel_index = y * self.pixels_across + x
            if pixel_index < len(self.pixels):
                # For now, just use a placeholder - this would need proper character mapping
                pixel_string += '.'
            else:
                pixel_string += '.'
        if y < self.pixels_tall - 1:  # Don't add newline after last row
            pixel_string += '\n'

    return pixel_string


def _get_color_map(self: BitmappySprite) -> dict[str, Any]:
    """Get color mapping for AI training.

    Returns:
        dict[str, Any]: The color map.

    """
    if not hasattr(self, 'pixels') or not self.pixels:
        return {}

    # Get unique colors and create mapping
    unique_colors = list(set(self.pixels))
    color_map: dict[str, Any] = {}

    max_colors = 8  # Limit to 8 colors
    for i, color in enumerate(unique_colors):
        if i < max_colors:
            color_map[str(i)] = {
                'red': color[0],
                'green': color[1],
                'blue': color[2],
            }

    return color_map


# Add methods to BitmappySprite class
BitmappySprite._get_pixel_string = _get_pixel_string  # type: ignore[attr-defined] # ty: ignore[unresolved-attribute]
BitmappySprite._get_color_map = _get_color_map  # type: ignore[attr-defined] # ty: ignore[unresolved-attribute]
