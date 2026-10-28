"""The workspace's source files and member packages, for the guards that scan every member.

Read from the workspace (scripts/workspace_packages.py), so only a guard over this repository's
source imports it: split from tests/ast_scanning.py (Part 3, Stage D, Task D9 fix round 1), which
keeps the AST helpers every guard shares and imports no ``scripts.*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scripts.workspace_packages import source_package_directories

from tests.engine_source import ENGINE_DIRECTORY

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from scripts.workspace_packages import WorkspaceMember


def member_import_packages(*, members: Sequence[WorkspaceMember]) -> frozenset[str]:
    """Return every import package the members hold."""
    return frozenset(package for member in members for package in member.import_packages)


def scanned_source_files(*, project_root: Path) -> list[tuple[str, Path]]:
    """Return every Python file the guards scan, with the key the allowlists spell it by.

    The engine's files are keyed relative to ``src/glitchygames/`` (``clock.py``); a workspace
    member's files relative to the repository (``src/games/mr-muncher/src/mr_muncher/game.py``), so
    the two never clash.

    Args:
        project_root: The repository.

    Returns:
        ``(allowlist key, path)`` for each file, in scan order.

    """
    engine_directory = project_root / ENGINE_DIRECTORY
    scanned: list[tuple[str, Path]] = []
    for package_directory in source_package_directories(project_root=project_root):
        key_base = engine_directory if package_directory == engine_directory else project_root
        scanned.extend(
            (source_path.relative_to(key_base).as_posix(), source_path)
            for source_path in sorted(package_directory.rglob('*.py'))
        )
    return scanned


def write_project_with_member_module(*, project_root: Path, source: str) -> str:
    """Write a small workspace project whose one member module holds ``source``.

    The project has an empty ``src/glitchygames/`` and the member ``src/games/space-game`` with
    the package ``space_game`` and its module ``game.py``.

    Args:
        project_root: Where to write the project (a temporary directory).
        source: The member module's source.

    Returns:
        The key the guards' allowlists would spell the member module by.

    """
    (project_root / ENGINE_DIRECTORY).mkdir(parents=True)
    (project_root / 'pyproject.toml').write_text(
        '[tool.uv.workspace]\nmembers = ["src/games/space-game"]\n', encoding='utf-8'
    )
    member_directory = project_root / 'src' / 'games' / 'space-game'
    (member_directory / 'space_game').mkdir(parents=True)
    (member_directory / 'pyproject.toml').write_text(
        '[project]\nname = "space-game"\n\n'
        '[tool.hatch.build.targets.wheel]\npackages = ["space_game"]\n',
        encoding='utf-8',
    )
    (member_directory / 'space_game' / 'game.py').write_text(source, encoding='utf-8')
    return 'src/games/space-game/space_game/game.py'
