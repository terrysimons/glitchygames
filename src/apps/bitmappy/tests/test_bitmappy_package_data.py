"""Bitmappy's sprite library ships inside its package, where the installed app reads it."""

from __future__ import annotations

from pathlib import Path

import bitmappy
from bitmappy import SPRITE_CONFIG_DIR, utils

# The sprite library's size when it moved with Bitmappy (2026-10-26)
SPRITE_LIBRARY_FILE_COUNT = 71


def test_the_sprite_library_is_package_data():
    """The sprite library is inside the package, read through the package's own path."""
    package_directory = Path(bitmappy.__file__).resolve().parent

    assert SPRITE_CONFIG_DIR.resolve().is_relative_to(package_directory)
    assert Path(utils.__file__).parent / 'resources' / 'sprites' == SPRITE_CONFIG_DIR
    assert len(list(SPRITE_CONFIG_DIR.glob('*.toml'))) == SPRITE_LIBRARY_FILE_COUNT
