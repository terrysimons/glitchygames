"""SpriteFactory for loading and saving sprites with automatic type detection.

This module contains the SpriteFactory class that provides a unified interface
for loading and saving both static and animated sprites.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from glitchygames.sprites.animated import AnimatedSprite

    from .bitmappy_sprite import BitmappySprite

from .constants import DEFAULT_FILE_FORMAT

# Error message constants for TRY003 compliance
_ERR_INVALID_SPRITE_FILE = 'Invalid sprite file'
_ERR_UNSUPPORTED_FORMAT_ANALYZE = (
    'Unsupported format: {file_format}. Only TOML is currently supported.'
)


class SpriteFactory:
    """Factory class for loading sprites with automatic type detection."""

    @staticmethod
    def load_sprite(*, filename: str | None = None) -> AnimatedSprite:
        """Load a sprite file, always returning an AnimatedSprite.

        Static sprites are automatically converted to single-frame animations
        for consistent internal representation.

        Args:
            filename: Path to sprite file. If None, loads default sprite (raspberry.toml).

        Returns:
            AnimatedSprite (static sprites are converted to single-frame animations).

        Raises:
            ValueError: If file format is invalid or contains mixed content.

        """
        # Handle default sprite loading
        if filename is None:
            filename = SpriteFactory._get_default_sprite_path()

        # Validate file content before loading
        analysis = SpriteFactory._analyze_file(filename)

        # Check if file has valid content
        if not (
            analysis['has_sprite_pixels']
            or analysis['has_animation_sections']
            or analysis['has_frame_sections']
        ):
            raise ValueError(_ERR_INVALID_SPRITE_FILE)

        # Check for mixed content (both static and animated data)
        if analysis['has_sprite_pixels'] and (
            analysis['has_animation_sections'] or analysis['has_frame_sections']
        ):
            raise ValueError(_ERR_INVALID_SPRITE_FILE)

        # Always return AnimatedSprite - it handles both static and animated content
        from glitchygames.sprites.animated import AnimatedSprite

        return AnimatedSprite(filename, groups=None)

    @staticmethod
    def detect_file_format(filename: str) -> str:
        """Detect file format based on extension.

        Returns:
            str: The resulting string.

        """
        # Convert Path objects to strings
        filename_str = str(filename)

        if filename_str.endswith('.toml'):
            return 'toml'
        if filename_str.endswith(('.yaml', '.yml')):
            return 'yaml'
        return 'unknown'

    @staticmethod
    def _analyze_file(filename: str) -> dict[str, Any]:
        """Analyze file content to determine sprite type.

        Currently only supports TOML format. To add new formats:
        1. Add format detection in _detect_file_format()
        2. Add analysis method here (e.g., _analyze_json_file())
        3. Add save/load methods in BitmappySprite and AnimatedSprite
        4. Update tests
        See LOADER_README.md for detailed implementation guide.

        Returns:
            dict: The result.

        Raises:
            ValueError: If the file format is not supported.

        """
        file_format = SpriteFactory.detect_file_format(filename)

        if file_format == 'toml':
            return SpriteFactory._analyze_toml_file(filename)

        raise ValueError(
            _ERR_UNSUPPORTED_FORMAT_ANALYZE.format(file_format=file_format),
        )

    @staticmethod
    def _analyze_toml_file(filename: str) -> dict[str, Any]:
        """Analyze TOML file content to determine sprite type.

        Returns:
            dict: The result.

        """
        with Path(filename).open('rb') as f:
            data = tomllib.load(f)

        has_sprite_pixels = False
        has_animation_sections = False
        has_frame_sections = False

        # Check for sprite.pixels (ignore empty strings and empty lists)
        if 'sprite' in data and 'pixels' in data['sprite']:
            pixels = data['sprite']['pixels']
            if (isinstance(pixels, str) and pixels.strip()) or (
                isinstance(pixels, list) and pixels
            ):
                has_sprite_pixels = True

        # Check for animation sections (both keys and arrays of tables)
        if (
            'animation' in data
            or 'animations' in data
            or (isinstance(data.get('animation'), list) and data['animation'])
        ):
            has_animation_sections = True

        # Check for frame sections (both keys and arrays of tables)
        if 'frame' in data or (isinstance(data.get('frame'), list) and data['frame']):
            has_frame_sections = True

        # Check for nested frame sections within animation arrays
        if isinstance(data.get('animation'), list):
            for animation in data['animation']:
                if isinstance(animation, dict) and 'frame' in animation:
                    has_frame_sections = True
                    break

        return {
            'has_sprite_pixels': has_sprite_pixels,
            'has_animation_sections': has_animation_sections,
            'has_frame_sections': has_frame_sections,
        }

    @staticmethod
    def _get_toml_data(filename: str) -> dict[str, Any]:
        """Get raw TOML data from file.

        Returns:
            dict: The toml data.

        """
        with Path(filename).open('rb') as f:
            return tomllib.load(f)

    @staticmethod
    def _determine_type(analysis: dict[str, Any]) -> str:
        """Determine sprite type based on file analysis.

        Returns:
            str: The resulting string.

        """
        # Prioritize animations over static content
        if analysis['has_frame_sections'] or analysis['has_animation_sections']:
            return 'animated'
        if analysis['has_sprite_pixels']:
            return 'static'
        return 'error'  # No recognizable content

    @staticmethod
    def _get_default_sprite_path() -> str:
        """Get the path to the default sprite (raspberry.toml).

        Returns:
            str: The default sprite path.

        """
        # Get the path to the assets directory
        assets_dir = Path(__file__).parent / '..' / 'assets'
        return str(assets_dir / 'raspberry.toml')

    @staticmethod
    def save_sprite(
        *,
        sprite: BitmappySprite | AnimatedSprite,
        filename: str,
        file_format: str = DEFAULT_FILE_FORMAT,
    ) -> None:
        """Save a sprite to a file with automatic type detection.

        Args:
            sprite: The sprite to save (BitmappySprite or AnimatedSprite).
            filename: Path where to save the sprite file.
            file_format: Output format ("ini", "yaml", or "toml"). Defaults to "toml".

        """
        if hasattr(sprite, 'animations'):  # It's an AnimatedSprite
            SpriteFactory._save_animated_sprite(sprite, filename, file_format)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
        else:  # It's a BitmappySprite
            SpriteFactory._save_static_sprite(sprite, filename, file_format)  # type: ignore[arg-type]

    @staticmethod
    def _save_static_sprite(sprite: BitmappySprite, filename: str, file_format: str) -> None:
        """Save a static sprite to a file."""
        sprite._save(filename, file_format)  # pyright: ignore[reportPrivateUsage]

    @staticmethod
    def _save_animated_sprite(sprite: AnimatedSprite, filename: str, file_format: str) -> None:
        """Save an animated sprite to a file."""
        sprite.save(filename, file_format)
