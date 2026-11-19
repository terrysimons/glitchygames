"""SpriteFactory for loading and saving sprites with automatic type detection.

This module contains the SpriteFactory class that provides a unified interface
for loading and saving both static and animated sprites.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from glitchygames.sprites.animated import AnimatedSprite

    from .bitmappy_sprite import BitmappySprite

from .constants import DEFAULT_FILE_FORMAT
from .sprite_toml import analyze_sprite_content, parse_sprite_toml

# Error message constants for TRY003 compliance
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
            ValueError: If the file is not TOML, or holds no sprite, or a static sprite and
                animations both.

        """
        # Handle default sprite loading
        if filename is None:
            filename = SpriteFactory._get_default_sprite_path()

        file_format = SpriteFactory.detect_file_format(filename)
        if file_format != 'toml':
            raise ValueError(_ERR_UNSUPPORTED_FORMAT_ANALYZE.format(file_format=file_format))

        # Always return AnimatedSprite - it handles both static and animated content. The load
        # checks the content on its own parse, or on its compile's record of it: no parse twice
        from glitchygames.sprites.animated import AnimatedSprite

        sprite = AnimatedSprite(groups=None)
        sprite.load(filename, require_sprite_content=True)
        return sprite

    @staticmethod
    def load_sprite_from_text(*, text: str, source_name: str) -> AnimatedSprite:
        """Load a sprite from the text of a sprite file, as load_sprite loads a file.

        The text gets the content checks a file gets, on the load's own parse, and loads by the
        one path a file's load takes (``AnimatedSprite.load_text``), so the two give the same
        sprite.

        Args:
            text: The sprite file's TOML text.
            source_name: What the text came from (a file name, a console), named in errors and in
                the warnings about pixel rows the loader repaired.

        Returns:
            AnimatedSprite (static text is converted to a single-frame animation).
            Text that is not valid TOML, or is invalid or mixed content, is refused with a
            ValueError.

        """
        from glitchygames.sprites.animated import AnimatedSprite

        # sprite_from_text's load, with the content check on its one parse
        sprite = AnimatedSprite(groups=None)
        sprite.load_text(text=text, source_name=source_name, require_sprite_content=True)
        return sprite

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
        1. Add format detection in SpriteFactory.detect_file_format()
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
        return SpriteFactory._analyze_toml_document(SpriteFactory._get_toml_data(filename))

    @staticmethod
    def _analyze_toml_document(data: dict[str, Any]) -> dict[str, Any]:
        """Analyze a parsed sprite document to determine sprite type.

        Returns:
            dict: The result (``sprite_toml.analyze_sprite_content``).

        """
        return dict(analyze_sprite_content(data))

    @staticmethod
    def _get_toml_data(filename: str) -> dict[str, Any]:
        """Get raw TOML data from file, parsed as the text load parses text.

        Returns:
            dict: The toml data. A file that is not valid TOML raises the ValueError
            ``parse_sprite_toml`` raises for the same text, naming the file.

        """
        # Bytes decoded, as AnimatedSprite._load_toml reads a file: the same text, the same error
        text = Path(filename).read_bytes().decode('utf-8')
        return parse_sprite_toml(text=text, source_name=filename)

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
            file_format: Output format. Only "toml" (the default) is supported; the sprite's
                save raises ValueError for any other.

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
