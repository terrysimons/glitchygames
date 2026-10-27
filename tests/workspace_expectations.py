"""The expected sets of the tests that find the workspace's members.

A root test that discovers members (their golden replays, bundled demos and console scripts)
must assert it found each one it expects, so it can never pass on zero, and so a lost or extra
recording fails. Two kinds of expectation, kept apart:

- **Written out by hand** (read from the repository on 2026-10-26, edited deliberately when a
  game, golden, demo or console script is added or removed): ``EXPECTED_GOLDENS`` (the six
  goldens by ``(distribution, file name)``), ``EXPECTED_GAME_CONSOLE_SCRIPTS`` (the five
  games-layer console scripts), ``EXPECTED_ALL_CONSOLE_SCRIPTS`` (the nine members' console
  scripts: the games, the demos and Bitmappy) and ``EXPECTED_BUNDLED_DEMOS`` (by
  ``(package, name)``).
- **Read from the workspace** (scripts/workspace_packages.py): which members are in the
  ``games`` layer, and where each keeps its goldens. The goldens found there are the same glob
  the tests' own discovery uses, so on their own they would check little: they are always
  compared with ``EXPECTED_GOLDENS`` (``check_every_game_holds_a_golden``).
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
# The goldens, by (games-layer distribution, file name), written out by hand: every games-layer
# member holds at least one, Brave Adventurer one per game (5 games, 6 goldens)
EXPECTED_GOLDENS = frozenset({
    ('brave-adventurer', 'golden-classic.jsonl.gz'),
    ('brave-adventurer', 'golden-papyrus.jsonl.gz'),
    ('clockwork-keep', 'golden.jsonl.gz'),
    ('drawing-fire', 'golden.jsonl.gz'),
    ('mr-muncher', 'golden.jsonl.gz'),
    ('paddleslap', 'golden.jsonl.gz'),
})
# The games-layer members' console scripts, written out by hand (one per game member: Brave
# Adventurer's launcher starts both its games)
EXPECTED_GAME_CONSOLE_SCRIPTS = frozenset({
    'brave-adventurer',
    'clockwork-keep',
    'drawing-fire',
    'mr-muncher',
    'paddleslap',
})
# Every member's console script, written out by hand: the five games, the three demos and Bitmappy
EXPECTED_ALL_CONSOLE_SCRIPTS = frozenset({
    'bitmappy',
    'brave-adventurer',
    'clockwork-keep',
    'drawing-fire',
    'dt-demo',
    'joystick-demo',
    'mr-muncher',
    'paddleslap',
    'text-input-demo',
})


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
