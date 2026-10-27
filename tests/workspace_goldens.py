"""The workspace's goldens, read from it and checked against tests/workspace_expectations.py.

Which members are in the ``games`` layer, and where each keeps its goldens, are read from the
workspace (scripts/workspace_packages.py). The goldens found there are the same glob the tests'
own discovery uses, so on their own they would check little: they are always compared with
``EXPECTED_GOLDENS`` (``check_every_game_holds_a_golden``). Split from
tests/workspace_expectations.py (Part 3, Stage D, Task D9), so the hand-written expected sets
reach no ``scripts.*``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scripts.workspace_packages import members_in_layer

from glitchygames.tracing import is_bookmarked_copy
from tests.workspace_expectations import EXPECTED_GOLDENS, GAMES_LAYER, GOLDEN_SUFFIX

if TYPE_CHECKING:
    from pathlib import Path

    from scripts.workspace_packages import WorkspaceMember


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


def check_every_game_holds_a_golden(
    *, project_root: Path, expected: frozenset[tuple[str, str]] = EXPECTED_GOLDENS
) -> dict[str, list[Path]]:
    """Check that the games-layer members hold exactly the expected goldens.

    The workspace must have games, every one must hold at least one golden, and the goldens
    found, by ``(distribution, file name)``, must be exactly ``expected``: a lost or an extra
    golden fails, even in a member that still holds another.

    Args:
        project_root: The repository.
        expected: The goldens by ``(distribution, file name)``: ``EXPECTED_GOLDENS`` unless
            given (a planted workspace's own).

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
    found = {(distribution, path.name) for distribution, paths in goldens.items() for path in paths}
    assert found == expected, (
        f'goldens missing: {sorted(expected - found)}; goldens not expected: '
        f'{sorted(found - expected)}'
    )
    return goldens


def every_games_golden(
    *, project_root: Path, expected: frozenset[tuple[str, str]] = EXPECTED_GOLDENS
) -> list[Path]:
    """Return every ``games``-layer member's goldens, after ``check_every_game_holds_a_golden``.

    Args:
        project_root: The repository.
        expected: The goldens by ``(distribution, file name)``: ``EXPECTED_GOLDENS`` unless
            given.

    Returns:
        The goldens' paths, sorted.

    """
    goldens = check_every_game_holds_a_golden(project_root=project_root, expected=expected)
    return sorted(path for paths in goldens.values() for path in paths)
