"""The cross-member tests' expected sets fail on a workspace missing what they expect.

tests/workspace_expectations.py is what keeps the tests that discover members from passing on
zero: these plant a workspace in tmp_path without a game, and with a game that holds no golden.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from scripts.workspace_packages import members_in_layer

from glitchygames.replay.driver import write_bookmarked_copy
from tests.stand_in_games import write_stand_in_recording
from tests.workspace_expectations import (
    check_every_game_holds_a_golden,
    every_games_golden,
    member_goldens,
)

if TYPE_CHECKING:
    from pathlib import Path

# A recording that is read, never replayed
STAND_IN_RECORDING_FRAMES = 3


def write_member(*, root: Path, member_path: str) -> Path:
    """Write a member with one flat package (no golden yet).

    Returns:
        The member's replay fixtures directory.

    """
    directory = root / member_path
    package = directory.name.replace('-', '_')
    (directory / package).mkdir(parents=True)
    (directory / 'pyproject.toml').write_text(
        f'[project]\nname = "{directory.name}"\n\n'
        f'[tool.hatch.build.targets.wheel]\npackages = ["{package}"]\n',
        encoding='utf-8',
    )
    return directory / 'tests' / 'fixtures' / 'replays'


def write_root(*, root: Path, member_paths: tuple[str, ...]) -> None:
    """Write the root pyproject listing the members."""
    members_toml = ', '.join(f'"{member_path}"' for member_path in member_paths)
    (root / 'pyproject.toml').write_text(
        f'[project]\nname = "stand-in"\n\n[tool.uv.workspace]\nmembers = [{members_toml}]\n',
        encoding='utf-8',
    )


def test_every_games_golden_is_found(tmp_path):
    """Two games with goldens (one with two) and a demo without: the games' goldens, sorted."""
    write_root(
        root=tmp_path,
        member_paths=('src/games/rock-game', 'src/demos/tiny-demo', 'src/games/space-game'),
    )
    rock_fixtures = write_member(root=tmp_path, member_path='src/games/rock-game')
    write_member(root=tmp_path, member_path='src/demos/tiny-demo')
    space_fixtures = write_member(root=tmp_path, member_path='src/games/space-game')
    goldens = [
        rock_fixtures / 'golden.jsonl.gz',
        space_fixtures / 'golden-one.jsonl.gz',
        space_fixtures / 'golden-two.jsonl.gz',
    ]
    for golden in goldens:
        write_stand_in_recording(path=golden, frame_count=STAND_IN_RECORDING_FRAMES)

    assert check_every_game_holds_a_golden(project_root=tmp_path) == {
        'rock-game': goldens[:1],
        'space-game': goldens[1:],
    }
    assert every_games_golden(project_root=tmp_path) == goldens


def test_a_game_without_a_golden_fails_the_check(tmp_path):
    """A planted games-layer member with no golden is named: the check cannot skip it."""
    write_root(root=tmp_path, member_paths=('src/games/rock-game', 'src/games/space-game'))
    rock_fixtures = write_member(root=tmp_path, member_path='src/games/rock-game')
    write_member(root=tmp_path, member_path='src/games/space-game')
    write_stand_in_recording(
        path=rock_fixtures / 'golden.jsonl.gz', frame_count=STAND_IN_RECORDING_FRAMES
    )

    with pytest.raises(AssertionError, match=r"without a golden replay: \['space-game'\]"):
        check_every_game_holds_a_golden(project_root=tmp_path)


def test_a_workspace_without_games_fails_the_check(tmp_path):
    """No games-layer member at all (only a demo) fails, instead of checking nothing."""
    write_root(root=tmp_path, member_paths=('src/demos/tiny-demo',))
    write_member(root=tmp_path, member_path='src/demos/tiny-demo')

    with pytest.raises(AssertionError, match='no games-layer member'):
        every_games_golden(project_root=tmp_path)


def test_a_bookmarked_copy_is_no_golden(tmp_path):
    """A bookmarked copy beside a golden (S in a watched replay saves one) is left out."""
    write_root(root=tmp_path, member_paths=('src/games/rock-game',))
    fixtures = write_member(root=tmp_path, member_path='src/games/rock-game')
    golden = fixtures / 'golden.jsonl.gz'
    write_stand_in_recording(path=golden, frame_count=STAND_IN_RECORDING_FRAMES)
    bookmarked = fixtures / 'golden.bookmarked.jsonl.gz'
    write_bookmarked_copy(recording_path=golden, bookmarks=[1], destination=bookmarked)
    (member,) = members_in_layer(project_root=tmp_path, layer='games')

    assert sorted(fixtures.iterdir()) == [bookmarked, golden]
    assert member_goldens(member=member) == [golden]
