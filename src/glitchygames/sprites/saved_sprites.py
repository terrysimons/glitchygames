"""Saving a generated sprite under the running game's package, safely and never overwriting.

The AI console's ``/sprite`` saves each sprite it makes as ``<game package>/sprites/<name>.toml``
(plans/2026-11-17-sprite-command.md). The name comes from the model, so it is never trusted as a
path: the file's stem keeps only lowercase letters, digits, ``-`` and ``_``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from glitchygames.output_files import write_aside_then_replace
from glitchygames.replay.tools.identity import package_directory_of

if TYPE_CHECKING:
    from pathlib import Path

SPRITES_FOLDER_NAME = 'sprites'
SPRITE_FILE_SUFFIX = '.toml'
DEFAULT_FILE_STEM = 'sprite'
MAXIMUM_FILE_STEM_LENGTH = 64
# Runs of anything a file stem does not keep, and what a stem may not start or end with
_NOT_KEPT = re.compile(r'[^a-z0-9_-]+')
# Names Windows reserves for devices, whatever the extension
_RESERVED_STEMS = frozenset(
    {'con', 'prn', 'aux', 'nul'}
    | {f'com{number}' for number in range(1, 10)}
    | {f'lpt{number}' for number in range(1, 10)}
)


def _file_stem(text: str) -> str:
    stem = _NOT_KEPT.sub('_', text.casefold()).strip('_-')[:MAXIMUM_FILE_STEM_LENGTH].strip('_-')
    if stem in _RESERVED_STEMS:
        return f'{stem}_{DEFAULT_FILE_STEM}'
    return stem


def sprite_file_name(*, sprite_name: str | None, description: str) -> str:
    """Make a sprite file's stem from the sprite's name, else the description, else ``sprite``.

    Args:
        sprite_name: The name in the sprite's own text (the model's choice), or None.
        description: What the player asked for.

    Returns:
        A stem of lowercase letters, digits, ``-`` and ``_`` only: never empty, never a path,
        never a name Windows reserves.

    """
    for text in (sprite_name or '', description):
        stem = _file_stem(text)
        if stem:
            return stem
    return DEFAULT_FILE_STEM


def save_sprite(*, toml_text: str, file_stem: str, sprites_folder: Path) -> Path:
    """Write a sprite's text to a new file in ``sprites_folder``, never over an existing one.

    The folder is created if missing; a name already taken gets a number (``dragon_001.toml``);
    the file is written aside, then moved into place.

    Args:
        toml_text: The sprite file's text.
        file_stem: A stem from ``sprite_file_name``.
        sprites_folder: The folder to write into.

    Returns:
        The file written. When the folder or the file cannot be written (an installed,
        read-only package), the OSError propagates.

    """
    # The sprite client's numbering, one copy (imported here: the client brings its HTTP stack)
    from glitchygames.api.client import find_available_path

    sprites_folder.mkdir(parents=True, exist_ok=True)
    destination = find_available_path(sprites_folder / f'{file_stem}{SPRITE_FILE_SUFFIX}')
    write_aside_then_replace(
        destination=destination, write=lambda aside: aside.write_text(toml_text, encoding='utf-8')
    )
    return destination


def game_sprites_folder(*, package: str) -> Path | None:
    """Return the running game's sprites folder: ``<package directory>/sprites``.

    Looks the package up through the import system, so it is called off the main thread.

    Args:
        package: The game's top-level package (``replay.tools.identity.game_package``).

    Returns:
        The folder (which may not exist yet), or None when the package has no directory.

    """
    directory = package_directory_of(package=package)
    return None if directory is None else directory / SPRITES_FOLDER_NAME
