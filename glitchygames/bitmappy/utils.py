"""Utility functions for the Bitmappy pixel art editor."""

from __future__ import annotations

import sys
from pathlib import Path


def detect_file_format(filename: str) -> str:
    """Detect file format from filename extension.

    Note: Only TOML format is currently supported.

    Args:
        filename: The filename to analyze

    Returns:
        The detected format string (currently only "toml")

    Raises:
        ValueError: If the file extension is not a supported format

    """
    extension = Path(filename).suffix.lower().lstrip('.')
    if extension in {'toml', ''}:
        return 'toml'
    msg = f'Unsupported file format: .{extension} (only TOML is supported)'
    raise ValueError(msg)


def resource_path(*path_segments: str) -> Path:
    """Return the absolute Path to a resource.

    Args:
        *path_segments: Path segments to join

    Returns:
        Path: Absolute path to the resource

    """
    if hasattr(sys, '_MEIPASS'):
        # Running in PyInstaller bundle — _MEIPASS is set by PyInstaller at runtime
        base_path = Path(sys._MEIPASS)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]
        # Note: We used --add-data "...:glitchygames/assets", so we must include
        # glitchygames/assets in the final path segments, e.g.:
        return base_path.joinpath(*path_segments)
    # Running in normal Python environment
    return Path(__file__).parent.parent.joinpath(*path_segments[1:])


# Load sprite configuration files for AI training
SPRITE_CONFIG_DIR = resource_path('glitchygames', 'examples', 'resources', 'sprites')
