"""The expected sets of the tests that find the workspace's members, read from the workspace.

A root test that discovers members (their golden replays, bundled demos and console scripts)
must assert it found each one it expects, so it can never pass on zero. Its expected set comes
from the workspace's shape (scripts/workspace_packages.py), never from the discovery it checks:
every ``games``-layer member holds at least one golden replay, and the bundled demos are known
by ``(package, name)``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scripts.workspace_packages import members_in_layer

from glitchygames.tracing import is_bookmarked_copy

if TYPE_CHECKING:
    from pathlib import Path

    from scripts.workspace_packages import WorkspaceMember

# The layer whose every member is a game with a golden replay (glitchygames.logical_names.LAYERS)
GAMES_LAYER = 'games'
# A golden replay's suffix (scripts/record_scripted_session.py REPLAY_FIXTURE_SUFFIX)
GOLDEN_SUFFIX = '.jsonl.gz'
# The bundled demos, by (package, name): PaddleSlap's rally is the one today
# (src/games/paddleslap/src/paddleslap/demos/rally.jsonl.gz). Never by path: nox's test sessions
# install the members non-editable, so a demo's path is in site-packages there
EXPECTED_BUNDLED_DEMOS = frozenset({('paddleslap', 'rally.jsonl.gz')})


def member_goldens(*, member: WorkspaceMember) -> list[Path]:
    """Return a member's golden replays: the recordings directly in its replay fixtures.

    A bookmarked copy (``glitchygames.tracing.is_bookmarked_copy``) is no golden.

    Args:
        member: The workspace member.

    Returns:
        The goldens' paths, sorted.

    """
    return sorted(
        path
        for path in member.replay_fixtures_directory.glob(f'*{GOLDEN_SUFFIX}')
        if not is_bookmarked_copy(path=path)
    )


def check_every_game_holds_a_golden(*, project_root: Path) -> dict[str, list[Path]]:
    """Check that the workspace has games and that every one holds at least one golden replay.

    Args:
        project_root: The repository.

    Returns:
        Each ``games``-layer member's distribution -> its goldens (none empty), in workspace
        order.

    """
    games = members_in_layer(project_root=project_root, layer=GAMES_LAYER)
    assert games, f'no {GAMES_LAYER}-layer member in the workspace at {project_root}'
    goldens = {member.distribution: member_goldens(member=member) for member in games}
    without_a_golden = [distribution for distribution, paths in goldens.items() if not paths]
    assert not without_a_golden, (
        f'{GAMES_LAYER}-layer members without a golden replay: {without_a_golden}'
    )
    return goldens


def every_games_golden(*, project_root: Path) -> list[Path]:
    """Return every ``games``-layer member's goldens, after ``check_every_game_holds_a_golden``.

    Args:
        project_root: The repository.

    Returns:
        The goldens' paths, sorted.

    """
    goldens = check_every_game_holds_a_golden(project_root=project_root)
    return sorted(path for paths in goldens.values() for path in paths)
