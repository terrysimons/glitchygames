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
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar, NoReturn, Self, cast, override

if TYPE_CHECKING:
    from collections.abc import Mapping

    from glitchygames.events.base import (
        HashableEvent,
        MouseButtonEvent,
        MouseMotionEvent,
        MouseWheelEvent,
    )

import pygame
import tomli_w

from glitchygames.color import MAGENTA_TRANSPARENCY_KEY

from .constants import DEFAULT_FILE_FORMAT, SPRITE_GLYPHS
from .pixel_utils import PADDING_GLYPH, normalize_pixel_rows
from .sprite import Sprite

LOG = logging.getLogger('game.sprites')


def _glyph_colors(rows: list[str], color_map: dict[str, Any]) -> list[list[Any]]:
    """Return each row's pixel colors, drawing a glyph missing from color_map as magenta.

    Magenta is the TOML transparency key, so an unknown glyph draws a transparent pixel. Both
    static loaders go through here, so they agree (BUGS.md #178 item 2); each unknown glyph is
    logged once per call.

    Args:
        rows: The pixel rows, one glyph per pixel.
        color_map: Glyph to color.

    Returns:
        The colors, row by row.

    """
    unknown_glyphs: set[str] = set()
    colors: list[list[Any]] = []
    for row in rows:
        row_colors: list[Any] = []
        for glyph in row:
            if glyph in color_map:
                row_colors.append(color_map[glyph])
            else:
                unknown_glyphs.add(glyph)
                row_colors.append(MAGENTA_TRANSPARENCY_KEY)
        colors.append(row_colors)
    if unknown_glyphs:
        LOG.warning(
            "Pixel glyphs %s are not in the sprite's colors; drawing them transparent (magenta)",
            sorted(unknown_glyphs),
        )
    return colors


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

    def __init__(  # ruff: ignore[too-many-arguments]
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
        # Pixel data (deflate and the TOML writers read it)
        self.pixels: list[tuple[int, ...]] = []
        self.pixels_across: int = int(width)
        self.pixels_tall: int = int(height)

        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            parent=parent,
            groups=groups,
        )

        # Try to load a file if one was specified, otherwise
        # if a width and height is specified, make a surface.
        if filename:
            (self.image, self.rect, self.name) = self.load(filename=filename)
            self.width = self.rect.width
            self.height = self.rect.height

        elif self.width and self.height:
            # Keep convert()'s result: the converted copy has the display's format (#173.5)
            self.image = pygame.Surface((self.width, self.height)).convert()
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
        from .factory import SpriteFactory

        try:
            animated_sprite = SpriteFactory.load_sprite(filename=filename)
        except ValueError as e:
            # If factory fails, fall back to old static-only loading
            self.log.debug('Factory failed, falling back to static-only loading: %s', e)
            assert filename is not None, 'filename must be provided for static-only loading'
            return self._load_static_only(filename)

        # Convert AnimatedSprite to BitmappySprite format: a copy of its current image
        assert animated_sprite.image is not None, 'AnimatedSprite must have an image'
        self.image = animated_sprite.image.copy()

        self.rect = self.image.get_rect()
        self.name = animated_sprite.name
        self.width = self.rect.width
        self.height = self.rect.height
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
        self.log.debug('Raw file content (%s bytes):\n%s', len(raw_content), raw_content)

        # Parse TOML
        data = tomllib.loads(raw_content)
        self.log.debug('TOML data keys: %s', list(data.keys()))

        try:
            (image, rect, name) = self._static_sprite_from_toml_data(data=data)
        except Exception:
            self.log.exception('Error in TOML load')
            raise

        # Return the successfully loaded sprite data
        return (image, rect, name)

    def _parse_static_toml_data(
        self: Self,
        data: dict[str, Any],
    ) -> tuple[str, list[str], dict[str, Any]]:
        """Read a static sprite's name, pixel rows and color map from parsed TOML.

        Shared by _load_static_toml and _inflate_toml. A missing sprite name or pixels, or a
        color's missing channel, raises KeyError.

        Args:
            data: The parsed TOML document.

        Returns:
            tuple[str, list[str], dict[str, Any]]: The sprite name, its non-empty pixel rows
                (stripped) and the map of each color character to its (red, green, blue).

        """
        name = data['sprite']['name']
        self.log.debug('Sprite name: %s', name)

        # Get pixel data
        pixel_text = str(data['sprite']['pixels'])
        self.log.debug('Raw pixel text (%s bytes):\n%s', len(pixel_text), pixel_text)

        # The engine's one pixel-row rule (normalize_pixel_rows), so this fallback draws what
        # AnimatedSprite draws: rows padded with transparent pixels to the longest
        palette_glyphs = [str(color_key) for color_key in data.get('colors', {})]
        normalized = normalize_pixel_rows(pixel_text, palette_glyphs)
        if normalized.repairs:
            self.log.warning('%s: pixel rows repaired: %s', name, '; '.join(normalized.repairs))
        rows = list(normalized.rows)
        self.log.debug('Total rows processed: %s', len(rows))

        # Get color definitions
        color_map: dict[str, Any] = {}
        if 'colors' in data:
            for color_key, color_data in data['colors'].items():
                red = color_data['red']
                green = color_data['green']
                blue = color_data['blue']
                if color_key == PADDING_GLYPH:
                    # normalize_pixel_rows pads with it, so it can't be a color
                    continue
                color_map[str(color_key)] = (red, green, blue)
                self.log.debug(
                    "Color map entry: '%s' -> RGB(%s, %s, %s)",
                    color_key,
                    red,
                    green,
                    blue,
                )

        # A padded pixel draws as the transparency key, as in AnimatedSprite
        color_map[PADDING_GLYPH] = MAGENTA_TRANSPARENCY_KEY
        self.log.debug('Total colors in map: %s', len(color_map))
        return (str(name), rows, color_map)

    def _static_sprite_from_toml_data(
        self: Self,
        data: dict[str, Any],
    ) -> tuple[pygame.Surface, pygame.Rect, str]:
        """Build a static sprite's image and rect from parsed TOML (the body of _load_static_toml).

        Args:
            data: The parsed TOML document.

        Returns:
            tuple[pygame.Surface, pygame.Rect, str]: The sprite's image, rect and name.

        """
        (name, rows, color_map) = self._parse_static_toml_data(data=data)

        # Calculate dimensions
        width = len(rows[0]) if rows else 0
        height = len(rows)
        self.log.debug('Calculated dimensions: %sx%s', width, height)

        # Create image and rect
        self.log.debug('Creating image and rect...')
        (image, rect) = self.inflate(
            width=width,
            height=height,
            pixels=rows,
            color_map=color_map,
        )
        self.log.debug('Created image size: %s', image.get_size())
        self.log.debug('Created rect: %s', rect)
        return (image, rect, name)

    @classmethod
    def inflate(
        cls: Any,
        width: int,
        height: int,
        pixels: list[str],
        color_map: dict[str, Any],
    ) -> tuple[pygame.Surface, pygame.Rect]:
        """Inflate a sprite from a list of pixels.

        A pixel character missing from the color map draws magenta, the transparency key, with
        a warning (BUGS.md #178 item 2; see _glyph_colors).

        Args:
            width: the width of the sprite.
            height: the height of the sprite.
            pixels: the list of pixels.
            color_map: the color map.

        Returns:
            A tuple containing the sprite's image and rect.

        """
        # Keep convert()'s result: the converted copy is the one in the display's format (#178.1)
        image = pygame.Surface((width, height)).convert()

        for y, row_colors in enumerate(_glyph_colors(pixels, color_map)):
            for x, color in enumerate(row_colors):
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
        1. Add format detection in SpriteFactory.detect_file_format()
        2. Add save logic here (e.g., _save_json(), _save_xml())
        3. Add load methods in _load_static_only()
        4. Update tests
        See LOADER_README.md for detailed implementation guide.
        """
        try:
            self._write_static_toml(filename=filename, file_format=file_format)
        except Exception:
            self.log.exception('Error in save')
            raise

    def _write_static_toml(self: Self, filename: str, file_format: str) -> None:
        """Deflate the sprite and write it as TOML (the body of _save_static_only).

        Args:
            filename: The file to write.
            file_format: The format to deflate to; deflate() refuses anything but TOML.

        """
        self.log.debug('Starting static-only save in %s format to %s', file_format, filename)
        config = self.deflate(file_format=file_format)
        self.log.debug('Got config from deflate: %s', config)

        # deflate() refused any other format, so this is TOML
        self.log.debug('About to write TOML')
        with Path(filename).open('wb') as toml_file:
            tomli_w.dump(config, toml_file)
        self.log.debug('TOML write complete')

        self.log.debug('Successfully saved to %s', filename)

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

        # Validate pixels list
        if len(self.pixels) != expected_pixels:
            self.log.error(
                'Pixels list length mismatch: %s vs expected %s',
                len(self.pixels),
                expected_pixels,
            )
            # Pad with default color if too short
            if len(self.pixels) < expected_pixels:
                self.pixels.extend([(255, 0, 255)] * (expected_pixels - len(self.pixels)))
            # Truncate if too long
            else:
                self.pixels = self.pixels[:expected_pixels]

    def deflate(self: Self, file_format: str = 'toml') -> dict[str, Any]:
        """Deflate a sprite to a configuration format.

        Currently only supports TOML format. To add new formats:
        1. Add format detection in SpriteFactory.detect_file_format()
        2. Add deflate logic here (e.g., _deflate_json(), _deflate_xml())
        3. Add inflate methods in _load_static_only()
        4. Update tests
        See LOADER_README.md for detailed implementation guide.

        Returns:
            dict: The result.

        """
        try:
            config = self._deflate_config(file_format=file_format)
        except Exception:
            self.log.exception('Error in deflate')
            raise

        # Return the successfully created configuration
        return config

    def _deflate_config(self: Self, file_format: str) -> dict[str, Any]:
        """Build the sprite's configuration (the body of deflate).

        Args:
            file_format: The configuration format; only TOML is supported.

        Returns:
            dict: The configuration.

        """
        self.log.debug('Starting deflate for %s in %s format', self.name, file_format)

        # Handle empty surfaces
        pixels_across: int = int(self.pixels_across)
        pixels_tall: int = int(self.pixels_tall)
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
        self.log.debug('Found %s unique colors', len(unique_colors))
        self.log.debug('Pixels list length: %s', len(self.pixels))
        self.log.debug('Expected pixels: %s', pixels_across * pixels_tall)
        self.log.debug('Sample pixels: %s', self.pixels[:10])

        # Check if there are too many colors
        if len(unique_colors) > len(SPRITE_GLYPHS):
            self._raise_too_many_colors_error(len(unique_colors))

        # Create color to character mapping using the helper method
        color_map = self._create_color_map()

        # Process pixels row by row
        pixel_rows = self._process_pixel_rows(color_map, pixels_across, pixels_tall)

        # Create configuration based on format
        if file_format != 'toml':
            self._raise_unsupported_format_error(file_format)
        return self._create_toml_config(pixel_rows, color_map)

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
            pixels_across = int(self.pixels_across)
        if pixels_tall is None:
            pixels_tall = int(self.pixels_tall)

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
            self.log.debug("Row %s: '%s' (len=%s)", y, row, len(row))
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
        pixels_tall: int = int(self.pixels_tall)
        pixels_across: int = int(self.pixels_across)

        for y in range(pixels_tall):
            row: str = ''
            for x in range(pixels_across):
                pixel_index = y * pixels_across + x
                if pixel_index < len(self.pixels):
                    pixel_color = self.pixels[pixel_index]
                    matched_char: str = cast('str', color_map.get(pixel_color, '.'))  # type: ignore[arg-type]
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
            if not self.pixels:
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
        if not self.pixels:
            return {}

        # Get unique colors from the pixels list
        unique_colors = set(self.pixels)
        color_map: dict[str, Any] = {}

        # Filter out dangerous characters that could break file formats
        dangerous_chars = {'\n', '\r', '\t', '\0', '\b', '\f', '\v', '\a'}
        printable_chars = ''.join(c for c in SPRITE_GLYPHS if c not in dangerous_chars)

        # Assign characters sequentially from SPRITE_CHARS (every glyph is printable and none is
        # dangerous, so each is used as it is); colors past the last glyph get none
        for char_index, color in enumerate(unique_colors):
            if char_index >= len(printable_chars):
                break
            color_map[printable_chars[char_index]] = color

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
        self.log.debug('Raw file content (%s bytes):\n%s', len(raw_content), raw_content)

        # Parse TOML
        data = tomllib.loads(raw_content)
        self.log.debug('TOML data keys: %s', list(data.keys()))

        try:
            sprite_data = self._sprite_data_from_toml_data(data=data)
        except Exception:
            self.log.exception('Error in TOML inflate')
            raise

        return sprite_data

    def _sprite_data_from_toml_data(self: Self, data: dict[str, Any]) -> dict[str, Any]:
        """Convert parsed TOML to sprite data (the body of _inflate_toml).

        Args:
            data: The parsed TOML document.

        Returns:
            dict: Sprite data dictionary (pixels, width, height and name).

        """
        (name, rows, color_map) = self._parse_static_toml_data(data=data)

        # Calculate dimensions
        width = len(rows[0]) if rows else 0
        height = len(rows)
        self.log.debug('Calculated dimensions: %sx%s', width, height)

        # Convert rows to pixels
        pixels: list[tuple[int, int, int]] = [
            color for row_colors in _glyph_colors(rows, color_map) for color in row_colors
        ]

        return {'pixels': pixels, 'width': width, 'height': height, 'name': name}

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
    def on_left_mouse_drag_event(
        self: Self, event: MouseMotionEvent, trigger: MouseButtonEvent
    ) -> None:
        """Handle a left mouse drag event.

        Args:
            event (MouseMotionEvent): The event to handle.
            trigger (MouseButtonEvent): The event that triggered the drag.

        """
        # Not logged: a drag arrives with every mouse motion while a button is held, so a log
        # line here would run every frame of a drag and drown out useful debug output.

    @override
    def on_middle_mouse_drag_event(
        self: Self,
        event: MouseMotionEvent,
        trigger: MouseButtonEvent,
    ) -> None:
        """Handle a middle mouse drag event.

        Args:
            event (MouseMotionEvent): The event to handle.
            trigger (MouseButtonEvent): The event that triggered the drag.

        """
        # Not logged: a drag arrives with every mouse motion while a button is held, so a log
        # line here would run every frame of a drag and drown out useful debug output.

    @override
    def on_right_mouse_drag_event(
        self: Self, event: MouseMotionEvent, trigger: MouseButtonEvent
    ) -> None:
        """Handle a right mouse drag event.

        Args:
            event (MouseMotionEvent): The event to handle.
            trigger (MouseButtonEvent): The event that triggered the drag.

        """
        # Not logged: a drag arrives with every mouse motion while a button is held, so a log
        # line here would run every frame of a drag and drown out useful debug output.

    @override
    def on_left_mouse_drop_event(
        self: Self, event: MouseButtonEvent, trigger: MouseButtonEvent
    ) -> None:
        """Handle a left mouse drop event.

        Args:
            event (MouseButtonEvent): The event to handle.
            trigger (MouseButtonEvent): The event that triggered the drop.

        """
        self.log.debug(
            '%s: Left Mouse Drop Event: %s @ %s for %s', type(self), event, self, trigger
        )

    @override
    def on_middle_mouse_drop_event(
        self: Self,
        event: MouseButtonEvent,
        trigger: MouseButtonEvent,
    ) -> None:
        """Handle a middle mouse drop event.

        Args:
            event (MouseButtonEvent): The event to handle.
            trigger (MouseButtonEvent): The event that triggered the drop.

        """
        self.log.debug(
            '%s: Middle Mouse Drop Event: %s @ %s for %s', type(self), event, self, trigger
        )

    @override
    def on_right_mouse_drop_event(
        self: Self, event: MouseButtonEvent, trigger: MouseButtonEvent
    ) -> None:
        """Handle a right mouse drop event.

        Args:
            event (MouseButtonEvent): The event to handle.
            trigger (MouseButtonEvent): The event that triggered the drop.

        """
        self.log.debug(
            '%s: Right Mouse Drop Event: %s @ %s for %s', type(self), event, self, trigger
        )

    @override
    def on_mouse_drag_event(self: Self, event: MouseMotionEvent, trigger: MouseButtonEvent) -> None:
        """Handle a mouse drag event.

        Args:
            event (MouseMotionEvent): The event to handle.
            trigger (MouseButtonEvent): The event that triggered the drag.

        """
        # Not logged: a drag arrives with every mouse motion while a button is held, so a log
        # line here would run every frame of a drag and drown out useful debug output.

    @override
    def on_mouse_drop_event(self: Self, event: MouseButtonEvent, trigger: MouseButtonEvent) -> None:
        """Handle a mouse drop event.

        Args:
            event (MouseButtonEvent): The event to handle.
            trigger (MouseButtonEvent): The event that triggered the drop.

        """
        self.log.debug('%s: Mouse Drop Event: %s @ %s for %s', type(self), event, self, trigger)

    @override
    def on_mouse_wheel_event(self: Self, event: MouseWheelEvent) -> None:
        """Handle a mouse wheel event.

        Args:
            event (MouseWheelEvent): The event to handle.

        """
        self.log.debug('%s: Mouse Wheel Event: %s @ %s', type(self), event, self)

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
        self.log.debug('%s: Mouse Chord Down Event: %s @ %s for %s', type(self), event, self, keys)

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
        self.log.debug('%s: Mouse Chord Up Event: %s @ %s for %s', type(self), event, self, keys)

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
        if not self.filename:
            return f'{type(self)} "{self.name}" (no file loaded)'

        try:
            return self._render_file_str(filename=self.filename)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            # Fallback to basic representation if rendering fails
            return f'{type(self)} "{self.name}" (error rendering: {e})'

    def _render_file_str(self: Self, filename: str) -> str:
        """Render a sprite file's TOML as a colorized ASCII string (the body of __str__).

        Args:
            filename: The sprite file to render.

        Returns:
            str: Colorized representation of the sprite (every frame, if animated).

        """
        # Import here to avoid circular imports
        from glitchygames.tools.ascii_renderer import ASCIIRenderer

        # Load TOML data from file
        with Path(filename).open('rb') as toml_file:
            toml_data = tomllib.load(toml_file)

        # Check if it's an animated sprite and show all frames
        if 'animation' in toml_data and len(toml_data['animation']) > 0:
            return self._render_animated_str(toml_data)
        # Static sprite - show normally
        renderer = ASCIIRenderer()
        return renderer.render_sprite(toml_data)


class Singleton:
    """A generic singleton class."""

    __instance__: ClassVar[Singleton | None] = None
    # Per-instance values are assigned in __new__; these immutable class-level defaults only
    # exist so the attributes are declared and initialized for type checkers.
    args: tuple[object, ...] = ()
    kwargs: Mapping[str, object] = MappingProxyType({})

    def __new__(cls, *args: object, **kwargs: object) -> Self:
        """Create a new instance of the Singleton.

        Args:
            *args: The arguments to pass to the constructor.
            **kwargs: The keyword arguments to pass to the constructor.

        Returns:
            Singleton: The instance of the Singleton.

        """
        # The isinstance check (rather than "is None") narrows the stored instance to Self
        # and ensures a subclass never receives an instance of a different class that was
        # found on a base class via attribute lookup.
        instance = cls.__instance__
        if not isinstance(instance, cls):
            instance = object.__new__(cls)
            cls.__instance__ = instance
        instance.args = args
        instance.kwargs = kwargs
        return instance


# This is a root class for sprites that should be singletons, like
#  MousePointer class.
class SingletonBitmappySprite(BitmappySprite):
    """A singleton class for handling singleton sprites, like mouse pointers."""

    __instance__: ClassVar[SingletonBitmappySprite | None] = None

    def __new__(cls, *_args: Any, **_kwargs: Any) -> Self:
        """Create a new instance of the SingletonBitmappySprite.

        Returns:
            SingletonBitmappySprite: The instance of the SingletonBitmappySprite.

        """
        # See Singleton.__new__ for why this is an isinstance check rather than "is None".
        instance = cls.__instance__
        if not isinstance(instance, cls):
            instance = object.__new__(cls)
            cls.__instance__ = instance
        return instance

    def __init__(  # ruff: ignore[too-many-arguments]
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

    __instance__: ClassVar[FocusableSingletonBitmappySprite | None] = None

    def __new__(cls, *_args: Any, **_kwargs: Any) -> Self:
        """Create a new instance of the FocusableSingletonBitmappySprite.

        Returns:
            FocusableSingletonBitmappySprite: The instance.

        """
        # See Singleton.__new__ for why this is an isinstance check rather than "is None".
        instance = cls.__instance__
        if not isinstance(instance, cls):
            instance = object.__new__(cls)
            cls.__instance__ = instance
        return instance

    def __init__(  # ruff: ignore[too-many-arguments]
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
    if not self.pixels:
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
    if not self.pixels:
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
