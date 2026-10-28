"""A game's own recordings: its goldens in the project and the demos bundled in its package.

What ``--verify`` with no paths replays (glitchygames/replay/tools/verify.py), found from the game
alone (its ``GameIdentity``) and the project's settings, so a game the engine has never seen finds
its recordings with nothing declared:

- **goldens**: the files the project's ``golden-globs`` match (``[tool.glitchygames]``; by
  default ``tests/fixtures/replays/**/*.jsonl.gz``) that this game's console script replays
  (``children.recording_console_script``: a workspace member's directory names its
  distribution, another project's ``fixtures/replays/<console-script>/`` its console script).
  A golden another game replays, or one whose console script can't be told, is not this game's;
- **demos**: ``<package>/demos/*.jsonl.gz`` in the game's own installed package
  (``glitchygames.bundled_demos.bundled_demos``, given that one package).

Bookmarked copies (``glitchygames.tracing.is_bookmarked_copy``) are neither. A game no console
script starts has no recordings found this way: no golden can be told to be its, and none could
be replayed by name.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Literal

from glitchygames.bundled_demos import bundled_demos
from glitchygames.replay.tools.children import recording_console_script
from glitchygames.tracing import is_bookmarked_copy

if TYPE_CHECKING:
    from pathlib import Path

    from glitchygames.replay.tools.identity import GameIdentity
    from glitchygames.replay.tools.settings import ProjectSettings

type RecordingKind = Literal['golden', 'demo']


@dataclasses.dataclass(frozen=True)
class Recording:
    """One of a game's own recordings.

    Attributes:
        console_script: The console script that replays it (the game's).
        path: Where it is.
        kind: A golden in the project, or a demo bundled in the game's package.

    """

    console_script: str
    path: Path
    kind: RecordingKind


def golden_paths(*, settings: ProjectSettings, project_root: Path) -> list[Path]:
    """Return every golden the project's ``golden-globs`` match, bookmarked copies left out.

    Args:
        settings: The project's settings.
        project_root: The project.

    Returns:
        The goldens' paths, sorted, each once.

    """
    return sorted({
        path
        for glob in settings.golden_globs
        for path in project_root.glob(glob)
        if not is_bookmarked_copy(path=path)
    })


def replaying_console_script(*, path: Path) -> str | None:
    """Return the console script that replays a golden, or None when it can't be told.

    Args:
        path: The golden.

    Returns:
        ``recording_console_script``'s answer, or None where it refuses (another layout, a
        distribution not installed, several console scripts none or more than one of which
        starts the recorded game).

    """
    try:
        return recording_console_script(path=path)
    except KeyError:
        return None


def game_recordings(
    *, identity: GameIdentity, settings: ProjectSettings, project_root: Path
) -> list[Recording]:
    """Return a game's own recordings: its goldens in the project, then its bundled demos.

    Args:
        identity: The game's identity (``identity.game_identity``).
        settings: The project's settings (``golden-globs``).
        project_root: The project the globs are read in.

    Returns:
        The goldens this game's console script replays (sorted by path), then the demos in its
        package (sorted by path); none for a game no console script starts.

    """
    console_script = identity.console_script
    if console_script is None:
        return []
    goldens = [
        Recording(console_script=console_script, path=path, kind='golden')
        for path in golden_paths(settings=settings, project_root=project_root)
        if replaying_console_script(path=path) == console_script
    ]
    demos = [
        Recording(console_script=console_script, path=demo.path, kind='demo')
        for demo in bundled_demos(packages=(identity.package,))
    ]
    return [*goldens, *demos]
