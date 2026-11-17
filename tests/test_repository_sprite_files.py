"""Every sprite file tracked in the repository passes the sprite file schema, wherever it lives.

The four sprite-file sites (the engine's sprites, Bitmappy's library, Papyrus's, every workspace
member's: glitchygames.testing.sprite_files) check the files a package ships. A sprite file
elsewhere had no check: ``scripts/animated.toml`` wrote its frames as ``[[animation.frames]]``,
a key the loader ignores, so it loaded with no animation at all and ``scripts/animation_demo.py``
showed nothing (found 2026-11-17 by the schema's audit). This walks every tracked TOML file that
holds a sprite.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from glitchygames.process import OutputCapture, run_command
from glitchygames.testing import sprite_files
from tests.ledger_repositories import environment_without_git_variables

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
GIT_TIMEOUT_SECONDS = 60.0


def tracked_sprite_files() -> list[Path]:
    """Every TOML file git tracks that holds a sprite (a ``[sprite]`` or ``[[animation]]``).

    Returns:
        The files, in path order.

    Raises:
        RuntimeError: If git cannot list the files (a walk of nothing would pass every test).
    """
    # Without git's variables: a hook's GIT_DIR would aim git at another tree
    finished = run_command(
        command=['git', 'ls-files', '*.toml'],
        environment=environment_without_git_variables(),
        timeout_seconds=GIT_TIMEOUT_SECONDS,
        capture_output=OutputCapture.APART,
        working_directory=REPOSITORY_ROOT,
    )
    if finished.returncode != 0:
        message = f'git ls-files failed: {finished.stderr}'
        raise RuntimeError(message)
    listed = (finished.stdout or '').split()
    files = []
    for relative in listed:
        path = REPOSITORY_ROOT / relative
        try:
            data = tomllib.loads(path.read_text(encoding='utf-8'))
        except tomllib.TOMLDecodeError:
            continue  # not a sprite file's concern (a deliberately broken fixture, a template)
        if 'sprite' in data or 'animation' in data:
            files.append(path)
    return sorted(files)


TRACKED_SPRITE_FILES = tracked_sprite_files()


def test_the_walk_finds_the_sprites_outside_the_packages():
    """The walk reaches what the package checks do not: a guard against walking nothing."""
    relative = {path.relative_to(REPOSITORY_ROOT).as_posix() for path in TRACKED_SPRITE_FILES}

    assert 'scripts/animated.toml' in relative
    assert len(TRACKED_SPRITE_FILES) > 90  # 102 on 2026-11-17


@pytest.mark.parametrize(
    'sprite_file',
    TRACKED_SPRITE_FILES,
    ids=lambda path: path.relative_to(REPOSITORY_ROOT).as_posix(),
)
def test_every_tracked_sprite_file_matches_the_schema(sprite_file):
    """A tracked sprite file the loaders would refuse, or would read only in part, fails here."""
    sprite_files.check_values_match_the_schema(sprite_file=sprite_file)
