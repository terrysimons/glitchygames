"""A project's settings for the engine's tools (glitchygames/replay/tools/settings.py).

They live in ``[tool.glitchygames]`` in the project's ``pyproject.toml``. A project without that
table (a player's own local runs) gets defaults that fit a standard layout; ours names this
repository's layout, and its values are pinned here against the module constants they replaced.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from glitchygames.code_tree import CodeTreePaths
from glitchygames.logical_names import LAYERS
from glitchygames.process import OutputCapture, run_command
from glitchygames.replay.tools.settings import (
    LOCAL_DIRECTORY_GITIGNORE,
    PYPROJECT_FILE_NAME,
    ProjectSettings,
    ProjectSettingsError,
    ensure_local_directory,
    find_project_root,
    load_project_settings,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
# How long each git command in a throwaway repository may take
GIT_TIMEOUT_SECONDS = 60.0

# Today's values of the module constants these settings replaced, copied by hand from
# glitchygames/code_tree.py and glitchygames/recording_metrics.py before they were deleted
# (Part 3, Stage D, Task D2): our [tool.glitchygames] must give exactly these
OLD_LEDGER_DIRECTORY = 'quality/replay-ledger'
OLD_MEASURED_PATHS = (
    'src',
    'tests/fixtures/replays',
    'uv.lock',
    'pyproject.toml',
)
# code_tree.unmeasured_member_test_pathspecs(): the members' tests, less their recordings
OLD_MEMBER_TEST_PATHSPECS = (
    ':(glob)src/games/*/tests/**',
    ':(glob)src/demos/*/tests/**',
    ':(glob)src/apps/*/tests/**',
    ':(exclude,glob)src/games/*/tests/fixtures/replays/**',
    ':(exclude,glob)src/demos/*/tests/fixtures/replays/**',
    ':(exclude,glob)src/apps/*/tests/fixtures/replays/**',
)
OLD_ORIGIN_MAIN = 'origin/main'
OLD_PUBLISHED_LEDGER_PATH = 'quality/metrics/replay-ledger.jsonl'
OLD_PUBLISHED_LEDGER_REF = 'origin/gh-pages'
OLD_PENDING_LEDGER_RELATIVE_PATH = 'test-results/replay-metrics/pending.jsonl'
OLD_RECORDING_PATH_RENAMES = {
    'glitchygames/examples/paddleslap_demos/rally.jsonl.gz': (
        'src/games/paddleslap/src/paddleslap/demos/rally.jsonl.gz'
    ),
    'src/glitchygames/examples/paddleslap_demos/rally.jsonl.gz': (
        'src/games/paddleslap/src/paddleslap/demos/rally.jsonl.gz'
    ),
    'src/games/paddleslap/paddleslap/demos/rally.jsonl.gz': (
        'src/games/paddleslap/src/paddleslap/demos/rally.jsonl.gz'
    ),
    'tests/fixtures/replays/mr-muncher/golden.jsonl.gz': (
        'src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz'
    ),
    'tests/fixtures/replays/brave-adventurer/golden.jsonl.gz': (
        'src/games/brave-adventurer/tests/fixtures/replays/golden-classic.jsonl.gz'
    ),
    'tests/fixtures/replays/brave-adventurer-papyrus/golden.jsonl.gz': (
        'src/games/brave-adventurer/tests/fixtures/replays/golden-papyrus.jsonl.gz'
    ),
    'tests/fixtures/replays/clockwork-keep/golden.jsonl.gz': (
        'src/games/clockwork-keep/tests/fixtures/replays/golden.jsonl.gz'
    ),
    'tests/fixtures/replays/paddleslap/golden.jsonl.gz': (
        'src/games/paddleslap/tests/fixtures/replays/golden.jsonl.gz'
    ),
    'tests/fixtures/replays/drawing-fire/golden.jsonl.gz': (
        'src/games/drawing-fire/tests/fixtures/replays/golden.jsonl.gz'
    ),
}
# Our games, written out by hand: every member's console script (stage D's settings table: "the
# nine console scripts")
OUR_GAMES = (
    'bitmappy',
    'brave-adventurer',
    'clockwork-keep',
    'drawing-fire',
    'dt-demo',
    'joystick-demo',
    'mr-muncher',
    'paddleslap',
    'text-input-demo',
)
# Our goldens: directly in each member's tests/fixtures/replays/
OUR_GOLDEN_GLOBS = ('src/*/*/tests/fixtures/replays/golden*.jsonl.gz',)
# The defaults for a project the engine has never seen (stage D's settings table)
DEFAULT_GOLDEN_GLOBS = ('tests/fixtures/replays/**/*.jsonl.gz',)
DEFAULT_LEDGER_DIRECTORY = 'replay-ledger'
DEFAULT_PENDING_LEDGER = '.glitchygames/pending-ledger.jsonl'
DEFAULT_LANDED_REF = 'origin/main'
DEFAULT_MEASURED_PATHS = ('src', 'tests/fixtures/replays', 'pyproject.toml')


def write_pyproject(*, project_root: Path, text: str) -> None:
    """Write a project's pyproject.toml."""
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / PYPROJECT_FILE_NAME).write_text(text, encoding='utf-8')


def assert_the_defaults_apart_from_games(settings: ProjectSettings) -> None:
    """Every setting but ``games`` is the unseen project's default."""
    assert settings.golden_globs == DEFAULT_GOLDEN_GLOBS
    assert settings.ledger_directory == DEFAULT_LEDGER_DIRECTORY
    assert settings.pending_ledger == DEFAULT_PENDING_LEDGER
    assert settings.published_ledger is None
    assert settings.published_ledger_ref is None
    assert settings.published_ledger_path is None
    assert settings.landed_ref == DEFAULT_LANDED_REF
    assert settings.measured_paths == DEFAULT_MEASURED_PATHS
    assert settings.unmeasured_paths == ()
    assert settings.recording_renames == {}
    assert settings.code_tree_paths == CodeTreePaths(measured=DEFAULT_MEASURED_PATHS, unmeasured=())


def test_a_project_without_tool_glitchygames_gets_the_defaults(tmp_path):
    """No [tool.glitchygames]: the defaults, and the games are the project's console scripts."""
    write_pyproject(
        project_root=tmp_path,
        text=(
            '[project]\nname = "my-game"\nversion = "1.0"\n\n'
            '[project.scripts]\nmy-game = "my_game:main"\nmy-editor = "my_game.editor:main"\n'
        ),
    )

    settings = load_project_settings(project_root=tmp_path)

    assert settings.games == ('my-game', 'my-editor')
    assert_the_defaults_apart_from_games(settings)


def test_a_project_without_a_pyproject_or_console_scripts_gets_the_defaults_and_no_games(tmp_path):
    """No pyproject.toml at all (a loose script's directory), or one without console scripts."""
    assert load_project_settings(project_root=tmp_path).games == ()
    assert_the_defaults_apart_from_games(load_project_settings(project_root=tmp_path))
    write_pyproject(project_root=tmp_path, text='[project]\nname = "my-game"\n')
    assert load_project_settings(project_root=tmp_path).games == ()


def test_settings_are_read_by_their_kebab_case_names(tmp_path):
    """Each key in [tool.glitchygames] sets its setting; the others keep their defaults."""
    write_pyproject(
        project_root=tmp_path,
        text=(
            '[project.scripts]\nignored = "my_game:main"\n\n'
            '[tool.glitchygames]\n'
            'games = ["my-game"]\n'
            'golden-globs = ["goldens/*.jsonl.gz"]\n'
            'ledger-directory = "measurements"\n'
            'pending-ledger = "measurements/waiting.jsonl"\n'
            'published-ledger = "origin/pages:metrics/ledger.jsonl"\n'
            'landed-ref = "origin/trunk"\n'
            'measured-paths = ["game"]\n'
            'unmeasured-paths = [":(glob)game/tests/**"]\n'
            'recording-renames = { "old.jsonl.gz" = "new.jsonl.gz" }\n'
        ),
    )

    settings = load_project_settings(project_root=tmp_path)

    assert settings == ProjectSettings(
        games=('my-game',),
        golden_globs=('goldens/*.jsonl.gz',),
        ledger_directory='measurements',
        pending_ledger='measurements/waiting.jsonl',
        published_ledger='origin/pages:metrics/ledger.jsonl',
        landed_ref='origin/trunk',
        measured_paths=('game',),
        unmeasured_paths=(':(glob)game/tests/**',),
        recording_renames={'old.jsonl.gz': 'new.jsonl.gz'},
    )
    assert settings.published_ledger_ref == 'origin/pages'
    assert settings.published_ledger_path == 'metrics/ledger.jsonl'
    assert settings.code_tree_paths == CodeTreePaths(
        measured=('game',), unmeasured=(':(glob)game/tests/**',)
    )


def test_an_unknown_setting_is_refused_by_name(tmp_path):
    """A misspelt key is an error naming it, the file and the settings there are."""
    write_pyproject(project_root=tmp_path, text='[tool.glitchygames]\nledger-directroy = "rows"\n')

    with pytest.raises(ProjectSettingsError) as refused:
        load_project_settings(project_root=tmp_path)

    message = str(refused.value)
    assert "unknown setting 'ledger-directroy'" in message
    assert str(tmp_path / PYPROJECT_FILE_NAME) in message
    assert 'ledger-directory' in message


def test_a_setting_spelled_with_underscores_is_unknown(tmp_path):
    """Only the kebab-case names are settings (``ledger_directory`` is a misspelling)."""
    write_pyproject(project_root=tmp_path, text='[tool.glitchygames]\nledger_directory = "rows"\n')

    with pytest.raises(ProjectSettingsError, match="unknown setting 'ledger_directory'"):
        load_project_settings(project_root=tmp_path)


@pytest.mark.parametrize(
    ('table', 'refusal'),
    [
        ('games = "my-game"', 'games'),
        ('published-ledger = "quality/ledger.jsonl"', 'published-ledger'),
        ('published-ledger = ":quality/ledger.jsonl"', 'published-ledger'),
        ('published-ledger = "origin/gh-pages:"', 'published-ledger'),
        ('ledger-directory = "/var/ledger"', 'ledger-directory'),
        ('recording-renames = ["old"]', 'recording-renames'),
    ],
)
def test_a_setting_with_a_value_of_the_wrong_shape_is_refused_by_name(tmp_path, table, refusal):
    """A value that is no setting of its kind names the setting and the file."""
    write_pyproject(project_root=tmp_path, text=f'[tool.glitchygames]\n{table}\n')

    with pytest.raises(ProjectSettingsError) as refused:
        load_project_settings(project_root=tmp_path)

    assert refusal in str(refused.value)
    assert str(tmp_path / PYPROJECT_FILE_NAME) in str(refused.value)


def test_a_pyproject_that_is_not_toml_is_refused_naming_the_file(tmp_path):
    """A broken pyproject.toml is an error naming it, not a traceback from the TOML reader."""
    write_pyproject(project_root=tmp_path, text='[tool.glitchygames\n')

    with pytest.raises(ProjectSettingsError, match='is not valid TOML'):
        load_project_settings(project_root=tmp_path)


def test_a_tool_glitchygames_that_is_not_a_table_is_refused(tmp_path):
    """``[tool] glitchygames = 1`` is no settings table."""
    write_pyproject(project_root=tmp_path, text='[tool]\nglitchygames = 1\n')

    with pytest.raises(ProjectSettingsError, match=r'\[tool.glitchygames\] is not a table'):
        load_project_settings(project_root=tmp_path)


def test_settings_resolve_no_paths_on_disk(tmp_path):
    """A setting naming a directory that doesn't exist yet is read as given (no ledger yet).

    The tools that write there create it or report it; reading the settings touches nothing.
    """
    settings = load_project_settings(project_root=tmp_path)

    assert not (tmp_path / settings.ledger_directory).exists()
    assert list(tmp_path.iterdir()) == []


def test_our_settings_equal_the_old_constants():
    """Our [tool.glitchygames] gives exactly the values of the constants it replaced."""
    settings = load_project_settings(project_root=PROJECT_ROOT)

    assert settings.ledger_directory == OLD_LEDGER_DIRECTORY
    assert settings.measured_paths == OLD_MEASURED_PATHS
    assert settings.unmeasured_paths == OLD_MEMBER_TEST_PATHSPECS
    assert settings.landed_ref == OLD_ORIGIN_MAIN
    assert settings.pending_ledger == OLD_PENDING_LEDGER_RELATIVE_PATH
    assert settings.published_ledger_ref == OLD_PUBLISHED_LEDGER_REF
    assert settings.published_ledger_path == OLD_PUBLISHED_LEDGER_PATH
    assert settings.recording_renames == OLD_RECORDING_PATH_RENAMES
    assert settings.games == OUR_GAMES
    assert settings.golden_globs == OUR_GOLDEN_GLOBS


def test_our_unmeasured_paths_name_every_layer():
    """Each layer's members' tests are unmeasured, but for their recordings.

    A new layer needs its two pathspecs in our [tool.glitchygames] too.
    """
    unmeasured = load_project_settings(project_root=PROJECT_ROOT).unmeasured_paths

    for layer in LAYERS:
        assert f':(glob)src/{layer}/*/tests/**' in unmeasured
        assert f':(exclude,glob)src/{layer}/*/tests/fixtures/replays/**' in unmeasured


def test_settings_made_in_code_take_the_field_names_and_nothing_published():
    """A tool building settings itself names fields in snake case; None publishes nothing."""
    settings = ProjectSettings(ledger_directory='rows', published_ledger=None)

    assert settings.ledger_directory == 'rows'
    assert settings.published_ledger_ref is None
    assert settings.published_ledger_path is None


@pytest.mark.parametrize(
    ('text', 'key'),
    [
        ('tool = 1\n', 'tool'),
        ('project = 1\n', 'project'),
        ('[project]\nscripts = 1\n', 'project.scripts'),
    ],
)
def test_a_table_that_is_not_a_table_is_refused_by_name(tmp_path, text, key):
    """``tool = 1``, ``project = 1`` or ``[project] scripts = 1``: an error naming it."""
    write_pyproject(project_root=tmp_path, text=text)

    with pytest.raises(ProjectSettingsError) as refused:
        load_project_settings(project_root=tmp_path)

    assert f'[{key}] is not a table' in str(refused.value)
    assert str(tmp_path / PYPROJECT_FILE_NAME) in str(refused.value)


def test_the_default_pending_ledger_is_outside_the_default_ledger_directory():
    """An unseen project's pending rows never sit among its committed row files."""
    defaults = ProjectSettings()
    pending = Path(defaults.pending_ledger)

    assert not pending.is_relative_to(defaults.ledger_directory)
    assert pending.parent == Path('.glitchygames')


def test_the_local_directory_gets_a_gitignore_once(tmp_path):
    """The directory and its ``*`` .gitignore are made; an existing .gitignore is kept."""
    directory = tmp_path / '.glitchygames'

    assert ensure_local_directory(directory=directory) == directory
    assert (directory / '.gitignore').read_text(encoding='utf-8') == LOCAL_DIRECTORY_GITIGNORE
    assert LOCAL_DIRECTORY_GITIGNORE.splitlines()[-1] == '*'
    (directory / '.gitignore').write_text('# mine\n', encoding='utf-8')
    ensure_local_directory(directory=directory)
    assert (directory / '.gitignore').read_text(encoding='utf-8') == '# mine\n'


def test_a_file_in_the_local_directory_is_not_seen_by_git(tmp_path):
    """Pending rows written there never show in ``git status`` (nothing to commit by mistake)."""
    run_command(
        command=['git', 'init', '--quiet'],
        environment=os.environ,
        timeout_seconds=GIT_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
        working_directory=tmp_path,
    )
    directory = ensure_local_directory(directory=tmp_path / '.glitchygames')
    (directory / 'pending-ledger.jsonl').write_text('{}\n', encoding='utf-8')

    status = run_command(
        command=['git', 'status', '--porcelain', '--untracked-files=all'],
        environment=os.environ,
        timeout_seconds=GIT_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
        working_directory=tmp_path,
    )

    assert status.returncode == 0, status.stdout
    assert not status.stdout


def test_the_project_is_the_nearest_directory_above_with_a_pyproject(tmp_path):
    """From inside a project, its root; from a project nested in another, the inner one."""
    outer = tmp_path / 'outer'
    inner = outer / 'packages' / 'inner'
    deep = inner / 'tests' / 'fixtures'
    deep.mkdir(parents=True)
    (outer / PYPROJECT_FILE_NAME).write_text('', encoding='utf-8')
    (inner / PYPROJECT_FILE_NAME).write_text('', encoding='utf-8')

    assert find_project_root(start=deep) == inner
    assert find_project_root(start=inner) == inner
    assert find_project_root(start=outer / 'packages') == outer


def test_a_member_without_settings_belongs_to_the_project_above_that_has_them(tmp_path):
    """Inside a workspace member, the root whose pyproject has [tool.glitchygames] is the project.

    The controller's ruling (Task D5's fix round): the member's own pyproject would otherwise
    own the ledger and name recordings relative to the member.
    """
    root = tmp_path / 'workspace'
    member = root / 'src' / 'games' / 'rally'
    deep = member / 'src' / 'rally'
    deep.mkdir(parents=True)
    (root / PYPROJECT_FILE_NAME).write_text(
        '[project]\nname = "workspace"\n\n[tool.glitchygames]\ngames = ["rally"]\n',
        encoding='utf-8',
    )
    (member / PYPROJECT_FILE_NAME).write_text('[project]\nname = "rally"\n', encoding='utf-8')

    assert find_project_root(start=deep) == root
    assert find_project_root(start=member) == root
    # A member with settings of its own is its own project
    (member / PYPROJECT_FILE_NAME).write_text(
        '[project]\nname = "rally"\n\n[tool.glitchygames]\n', encoding='utf-8'
    )
    assert find_project_root(start=deep) == member


def test_a_pyproject_that_is_not_toml_has_no_settings_table_when_looking_up(tmp_path):
    """A pyproject that is not TOML is still the nearest: refused when its settings are read."""
    outer = tmp_path / 'outer'
    inner = outer / 'inner'
    inner.mkdir(parents=True)
    (outer / PYPROJECT_FILE_NAME).write_text('[project\n', encoding='utf-8')
    (inner / PYPROJECT_FILE_NAME).write_text('not toml = = =\n', encoding='utf-8')

    assert find_project_root(start=inner) == inner


def test_no_project_above_is_none(tmp_path, mocker):
    """No pyproject.toml in the directory or any above it: None."""
    mocker.patch.object(Path, 'is_file', return_value=False)

    assert find_project_root(start=tmp_path) is None
