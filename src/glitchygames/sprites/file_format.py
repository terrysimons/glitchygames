"""Sprite file-format detection, shared by the engine's animated sprites and the editors."""

from __future__ import annotations

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
