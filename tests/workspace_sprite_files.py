"""The workspace's sprite files, discovered, for the tests that run a check on every one.

The sprite files are every TOML sprite (a file with a ``sprite`` table) in any member's import
packages, read from the source tree by path: nothing here imports a member. It reads the workspace
(scripts/workspace_packages.py), so it lives in tests/ like tests/workspace_sources.py, not in
glitchygames.testing, which the engine ships and which reaches nothing outside the engine. The
checks themselves are glitchygames.testing.sprite_files; tests/test_workspace_sprite_files.py and
tests/sprites/test_sprite_toml.py and tests/sprites/test_sprite_text.py parametrize them over
these lists. Bitmappy's sprite library is a member's, so it is among them.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from scripts.workspace_packages import workspace_members

from glitchygames.testing import sprite_files

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# What makes a TOML file a sprite file: a [sprite] table (read as TOML, so a header written
# '[ sprite ]' or with a comment counts too)
SPRITE_TABLE = 'sprite'


def member_sprite_files(*, project_root: Path) -> list[Path]:
    """Return every sprite file in the workspace members' import packages, in path order.

    Args:
        project_root: The repository.

    Returns:
        The sprite files.

    """
    return sorted(
        toml_file
        for member in workspace_members(project_root=project_root)
        for package_directory in member.package_directories
        for toml_file in package_directory.rglob(sprite_files.SPRITE_FILE_PATTERN)
        if SPRITE_TABLE in tomllib.loads(toml_file.read_text(encoding='utf-8'))
    )


MEMBER_SPRITE_FILES = member_sprite_files(project_root=PROJECT_ROOT)
MEMBER_ANIMATED_SPRITE_FILES = [
    sprite_file
    for sprite_file in MEMBER_SPRITE_FILES
    if sprite_files.ANIMATION_MARKER in sprite_file.read_text(encoding='utf-8')
]


def sprite_file_id(sprite_file: Path) -> str:
    """Name a sprite file by its path below src/ (``games/drawing-fire/src/.../soldier.toml``).

    Returns:
        The path.

    """
    return sprite_file.relative_to(PROJECT_ROOT / 'src').as_posix()
