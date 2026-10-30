"""Every committed recording names its game and scenes by logical names that resolve.

And every recording in the repository is replayed by a test (a golden replay or a bundled demo)
or listed in ``RECORDINGS_NOT_REPLAYED`` with what reads it.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from scripts.git_checkout import files_not_ignored, run_git
from scripts.workspace_packages import workspace_members

from glitchygames.bundled_demos import bundled_demos
from glitchygames.logical_names import module_for_logical_module
from glitchygames.recording import SCENE_START_FIELD
from glitchygames.replay.driver import GAME_HEADER_FIELD
from glitchygames.testing.replays import (
    RECORDING_SUFFIX,
    bundled_demo_paths,
    is_under_replay_fixtures,
)
from glitchygames.tracing import TraceReader, is_bookmarked_copy, read_trace
from tests.workspace_expectations import EXPECTED_BUNDLED_DEMOS, MEMBER_PACKAGES
from tests.workspace_goldens import every_games_golden

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
COMMITTED_RECORDINGS = sorted([
    *PROJECT_ROOT.glob('tests/fixtures/replays/*/*.jsonl.gz'),
    *(
        recording
        for member in workspace_members(project_root=PROJECT_ROOT)
        for recording in member.replay_fixtures_directory.glob('*.jsonl.gz')
    ),
    *(path for _console_script, path in bundled_demo_paths(packages=MEMBER_PACKAGES)),
])

# The golden traces' baselines (tests/world/test_golden_traces.py), compared sprite by sprite
# but never replayed as recordings: left out of the replayed-recordings check whole
GOLDEN_TRACES_DIRECTORY = Path('tests') / 'world' / 'golden'
# Committed recordings that are neither a golden replay nor a bundled demo, by repository path,
# each with what reads it instead of replaying it
RECORDINGS_NOT_REPLAYED = {
    'tests/fixtures/provenance/clockwork-keep-golden-before-game-source-revision.jsonl.gz': (
        "tests/replay/tools/test_provenance.py reads its runs: a frozen copy of Clockwork Keep's "
        'golden from before game_source_revision existed'
    ),
}


def recordings_no_test_replays(*, project_root: Path, demo_install_names: set[str]) -> list[str]:
    """Return the repository's recordings that no test replays, by repository path.

    A recording is replayed when the golden-replay plugin collects it (under
    ``fixtures/replays/``, not a bookmarked copy: glitchygames/testing/replays.py) or when it is
    a bundled demo of a member package (tests/replay/test_bundled_demos.py replays each).

    Args:
        project_root: The repository.
        demo_install_names: The bundled demos' paths relative to their package's parent
            (``paddleslap/demos/rally.jsonl.gz``: ``BundledDemo.install_name``).

    Returns:
        The other recordings' repository paths, sorted.

    """
    package_directories = [
        package_directory
        for member in workspace_members(project_root=project_root)
        for package_directory in member.package_directories
    ]
    searched = [
        project_root / relative_path
        for relative_path in files_not_ignored(directory=project_root)
        if relative_path.name.endswith(RECORDING_SUFFIX)
    ]
    unreplayed: list[str] = []
    for path in searched:
        relative_path = path.relative_to(project_root)
        if relative_path.is_relative_to(GOLDEN_TRACES_DIRECTORY):
            continue
        collected = is_under_replay_fixtures(directory=relative_path.parent) and not (
            is_bookmarked_copy(path=path)
        )
        bundled = any(
            path.is_relative_to(package_directory)
            and path.relative_to(package_directory.parent).as_posix() in demo_install_names
            for package_directory in package_directories
        )
        if not (collected or bundled):
            unreplayed.append(relative_path.as_posix())
    return sorted(unreplayed)


def resolves(logical: str) -> bool:
    """Whether ``layer.module:qualname`` names a class of a real module in the workspace.

    Returns:
        True when the module imports and the qualified name inside it is a class.

    """
    logical_module, _, qualified_name = logical.partition(':')
    try:
        target: object = importlib.import_module(
            module_for_logical_module(logical_module=logical_module)
        )
    except ImportError:
        return False
    for attribute in qualified_name.split('.'):
        target = getattr(target, attribute, None)
    return isinstance(target, type)


def recording_id(path: Path) -> str:
    """The recording's repository path (the bundled demo, in the installed engine: its name).

    Returns:
        The id pytest shows for the recording.

    """
    return (
        path.relative_to(PROJECT_ROOT).as_posix()
        if path.is_relative_to(PROJECT_ROOT)
        else path.name
    )


@pytest.mark.parametrize('recording', COMMITTED_RECORDINGS, ids=recording_id)
def test_every_logical_name_in_the_recording_resolves(recording):
    """The header's ``game`` and every scene start's ``scene`` name a class that exists."""
    trace = read_trace(path=recording)
    names = [trace.get('game')] + [
        frame[SCENE_START_FIELD].get('scene')
        for frame in trace['frames']
        if SCENE_START_FIELD in frame
    ]

    unresolved = [name for name in names if name is None or not resolves(name)]
    assert not unresolved, f'{recording}: logical names missing or unresolved: {unresolved}'


def test_the_committed_recordings_are_all_checked():
    """Exactly every games-layer member's goldens and every bundled demo, each game resolving.

    The expected set is the workspace's: every games-layer member holds at least one golden, and
    the bundled demos are known by ``(package, name)`` (nox installs non-editable copies, so not
    by path). An empty parametrization above would skip, not fail; this cannot pass on zero.
    """
    goldens = every_games_golden(project_root=PROJECT_ROOT)
    demos = bundled_demos(packages=MEMBER_PACKAGES)
    unresolved: list[tuple[Path, object]] = []
    for recording in [*goldens, *(demo.path for demo in demos)]:
        with TraceReader(path=recording) as reader:
            game = reader.header.get(GAME_HEADER_FIELD)
        if not isinstance(game, str) or not resolves(game):
            unresolved.append((recording, game))

    assert {(demo.package, demo.path.name) for demo in demos} == EXPECTED_BUNDLED_DEMOS
    assert sorted([*goldens, *(demo.path for demo in demos)]) == COMMITTED_RECORDINGS
    assert not unresolved


def test_every_committed_recording_is_replayed_by_a_test():
    """Each recording in the repository is a golden replay or a bundled demo, or is listed.

    Read from git (tracked, or untracked and not ignored), not from the directories goldens and
    demos are kept in, so a recording committed anywhere else is found.
    """
    demo_install_names = {demo.install_name for demo in bundled_demos(packages=MEMBER_PACKAGES)}

    assert demo_install_names, 'no bundled demo found: this check would pass on zero'
    assert recordings_no_test_replays(
        project_root=PROJECT_ROOT, demo_install_names=demo_install_names
    ) == sorted(RECORDINGS_NOT_REPLAYED)


def test_a_recording_kept_elsewhere_is_one_no_test_replays(tmp_path):
    """A planted workspace: its golden and demo are replayed, a stray recording is not."""
    returncode, output = run_git(arguments=['init', '--quiet'], directory=tmp_path)
    assert returncode == 0, output
    (tmp_path / 'pyproject.toml').write_text(
        '[project]\nname = "glitchygames"\n\n'
        '[tool.uv.workspace]\nmembers = ["src/games/space-game"]\n',
        encoding='utf-8',
    )
    member = tmp_path / 'src' / 'games' / 'space-game'
    (member / 'pyproject.toml').parent.mkdir(parents=True)
    (member / 'pyproject.toml').write_text(
        '[project]\nname = "space-game"\n\n'
        '[tool.hatch.build.targets.wheel]\npackages = ["src/space_game"]\n',
        encoding='utf-8',
    )
    planted = {
        'golden': member / 'tests' / 'fixtures' / 'replays' / 'golden.jsonl.gz',
        'demo': member / 'src' / 'space_game' / 'demos' / 'attract.jsonl.gz',
        'stray': member / 'tests' / 'fixtures' / 'recordings' / 'stray.jsonl.gz',
        'trace': tmp_path / GOLDEN_TRACES_DIRECTORY / 'space_game.jsonl.gz',
    }
    for path in planted.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'')

    assert recordings_no_test_replays(
        project_root=tmp_path, demo_install_names={'space_game/demos/attract.jsonl.gz'}
    ) == ['src/games/space-game/tests/fixtures/recordings/stray.jsonl.gz']
