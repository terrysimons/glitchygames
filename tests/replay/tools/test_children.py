"""Games run as child processes (glitchygames/replay/tools/children.py), on stand-in games.

The console script lookups and the headless child replay moved here from
tests/replay/test_replay_plugin.py with the helpers (Part 3, Stage D, Task D1); ``resolve_game``
and ``launch_game`` are the ``glitchygames`` command's reading of ``GAME``.
"""

from __future__ import annotations

import os
import shutil
import sys
from importlib.metadata import EntryPoint
from pathlib import PureWindowsPath
from typing import TYPE_CHECKING

import pytest

from glitchygames.bundled_demos import CONSOLE_SCRIPTS_GROUP
from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, run_command
from glitchygames.replay.tools.children import (
    GAME_FORMS,
    GameLaunch,
    UnknownGameError,
    console_script_for_game_module,
    entry_point_command,
    game_entry_point,
    installed_console_scripts,
    launch_game,
    module_is_importable,
    rebaseline_recording_headless,
    recorded_game_module,
    recorded_games_console_script,
    recording_console_script,
    replay_recording_headless,
    resolve_game,
)
from glitchygames.replay.tools.settings import ProjectSettingsError
from glitchygames.tracing import REPLAY_FIXTURES_PATH_PARTS
from tests.replay.replay_helpers import tamper_first_sprite_rect
from tests.stand_in_games import (
    StandInGame,
    member_recording_path,
    record_stand_in_game,
    use_stand_in_game,
    write_header_only_recording,
    write_stand_in_distribution,
    write_stand_in_game,
)

if TYPE_CHECKING:
    from pathlib import Path

# The frame a tampered copy of the stand-in's recording first differs from the engine at (the
# stand-in game draws a sprite on it and every frame after it)
TAMPERED_FRAME = 10
# A child that only imports the tools ends in a second or two
CHILD_TIMEOUT_SECONDS = 120.0
# A stand-in distribution installed with no console script (a real one's could gain one)
SCRIPTLESS_DISTRIBUTION = 'scriptless-library'


@pytest.fixture
def stand_in_game(tmp_path_factory, monkeypatch) -> StandInGame:
    """Install the stand-in game (tests/stand_in_games.py) for this test and its children.

    Its facts: one console script (``stand-in-rally``) in package ``stand_in_rally``, one scene,
    a sprite on every frame, seeded and deterministic, no input; it quits itself after 20 frames.

    Returns:
        The stand-in game.

    """
    install_directory = tmp_path_factory.mktemp('site-packages')
    game = write_stand_in_game(directory=install_directory)
    use_stand_in_game(install_directory=install_directory, monkeypatch=monkeypatch)
    return game


@pytest.fixture
def stand_in_recording(stand_in_game, tmp_path_factory) -> Path:
    """Return a recording of the stand-in game's session, made by a child ``--record-trace``.

    Returns:
        Its path.

    """
    return record_stand_in_game(
        game=stand_in_game, path=tmp_path_factory.mktemp('recorded') / 'rally.jsonl.gz'
    )


def test_game_entry_point_reads_the_console_script(tmp_path, monkeypatch):
    """A console script's entry point comes from the package metadata.

    The stand-in distribution holds one console script, ``stand-in-game = stand_in_game:main``.
    """
    write_stand_in_distribution(
        directory=tmp_path,
        distribution='stand-in-game',
        console_scripts={'stand-in-game': 'stand_in_game:main'},
    )
    monkeypatch.syspath_prepend(tmp_path)

    entry_point = game_entry_point(console_script='stand-in-game')

    assert entry_point.value == 'stand_in_game:main'
    assert entry_point.group == 'console_scripts'


def test_replay_recording_headless_returns_the_finished_replay(
    tmp_path, stand_in_game, stand_in_recording
):
    """The child replay's exit code and output (with the divergence report) come back.

    The stand-in game has a sprite on TAMPERED_FRAME, so the tampered copy diverges there.
    """
    tampered_path = tmp_path / 'tampered.jsonl.gz'
    shutil.copy(stand_in_recording, tampered_path)
    tamper_first_sprite_rect(recording_path=tampered_path, frame_number=TAMPERED_FRAME)

    completed = replay_recording_headless(
        console_script=stand_in_game.console_script, path=tampered_path
    )

    assert completed.returncode == ExitCode.REPLAY_DIVERGED
    assert f'Replay diverged at frame {TAMPERED_FRAME}' in completed.stdout


def test_rebaseline_recording_headless_writes_the_new_recording(
    tmp_path, stand_in_game, stand_in_recording
):
    """The child rebaselines through the console script and prints its summary.

    The stand-in game is deterministic, so no frame differs.
    """
    new_path = tmp_path / 'rebaselined.jsonl.gz'

    completed = rebaseline_recording_headless(
        console_script=stand_in_game.console_script, path=stand_in_recording, new_path=new_path
    )

    assert completed.returncode == ExitCode.SUCCESS, completed.stdout
    assert f'to {new_path}: no frames differ' in completed.stdout
    assert new_path.is_file()


def test_game_entry_point_of_an_unknown_console_script_raises():
    """A name no installed package has as a console script is a KeyError naming it."""
    with pytest.raises(KeyError, match='no-such-game'):
        game_entry_point(console_script='no-such-game')


def test_a_member_with_several_console_scripts_replays_through_the_recorded_games_script(
    tmp_path, monkeypatch
):
    """The header's game (a logical name) names the module, whose console script replays it.

    A stand-in member with a console script per game (every real game is now a member with
    one script, or a launcher): its Papyrus recording is replayed by the script whose entry
    point's package holds the Papyrus game module.
    """
    installed = tmp_path / 'site-packages'
    write_stand_in_distribution(
        directory=installed,
        distribution='space-games',
        console_scripts={'classic': 'space_game:main', 'papyrus': 'space_game_papyrus:main'},
    )
    monkeypatch.syspath_prepend(installed)
    recording = member_recording_path(tmp_path=tmp_path, distribution='space-games')
    write_header_only_recording(
        path=recording, header={'game': 'space_game_papyrus.game:PapyrusScene'}
    )

    assert recording_console_script(path=recording) == 'papyrus'


def test_a_game_module_inside_the_entry_points_package_is_its_game():
    """A scene in <package>.game is the game of the console script <package>:main."""
    entry_points = [
        EntryPoint(name='classic', value='space_game:main', group=CONSOLE_SCRIPTS_GROUP),
        EntryPoint(name='papyrus', value='space_game_papyrus:main', group=CONSOLE_SCRIPTS_GROUP),
    ]

    assert (
        console_script_for_game_module(entry_points=entry_points, game_module='space_game.game')
        == 'classic'
    )
    assert (
        console_script_for_game_module(
            entry_points=entry_points, game_module='space_game_papyrus.game'
        )
        == 'papyrus'
    )


def test_a_game_module_no_console_script_starts_is_refused():
    """None of the scripts' entry points holds the game module: no game to replay it with."""
    entry_points = [
        EntryPoint(name='classic', value='space_game:main', group=CONSOLE_SCRIPTS_GROUP)
    ]

    with pytest.raises(KeyError, match=r"none of \['classic'\] starts other_game\.game"):
        console_script_for_game_module(entry_points=entry_points, game_module='other_game.game')


def test_a_game_module_several_console_scripts_start_is_refused():
    """Two scripts whose entry points both hold the game module: the choice is ambiguous."""
    entry_points = [
        EntryPoint(name='game', value='space_game:main', group=CONSOLE_SCRIPTS_GROUP),
        EntryPoint(name='scene', value='space_game.game:main', group=CONSOLE_SCRIPTS_GROUP),
    ]

    with pytest.raises(KeyError, match=r"\['game', 'scene'\] all start space_game\.game"):
        console_script_for_game_module(entry_points=entry_points, game_module='space_game.game')


def test_a_member_recording_whose_game_no_console_script_starts_is_refused(tmp_path):
    """A Mr. Muncher recording among the engine's scripts: none of them starts it."""
    recording = member_recording_path(tmp_path=tmp_path, distribution='glitchygames')
    write_header_only_recording(
        path=recording, header={'game': 'games.mr_muncher.game:MrMuncherScene'}
    )

    with pytest.raises(KeyError, match=r"'glitchygames': none of .* starts mr_muncher\.game"):
        recording_console_script(path=recording)


def test_a_member_recording_without_a_game_in_its_header_is_refused(tmp_path):
    """A recording made before logical names names no game to choose a console script by."""
    recording = member_recording_path(tmp_path=tmp_path, distribution='glitchygames')
    write_header_only_recording(
        path=recording, header={'game_module': 'glitchygames.examples.paddleslap'}
    )

    with pytest.raises(KeyError, match=r"no 'game' in its header"):
        recording_console_script(path=recording)


def test_a_member_recording_that_cannot_be_read_is_refused(tmp_path):
    """A missing recording of a several-script member: its header cannot choose the script."""
    recording = tmp_path.joinpath(
        'glitchygames', 'tests', *REPLAY_FIXTURES_PATH_PARTS, 'golden.jsonl.gz'
    )

    with pytest.raises(KeyError, match=r"header cannot be read to choose among 'glitchygames'"):
        recording_console_script(path=recording)


def install_distribution_without_console_scripts(*, tmp_path: Path, monkeypatch) -> str:
    """Install a stand-in distribution with no console script (not a real one's metadata).

    Returns:
        Its name.

    """
    installed = tmp_path / 'site-packages'
    write_stand_in_distribution(
        directory=installed, distribution=SCRIPTLESS_DISTRIBUTION, console_scripts={}
    )
    monkeypatch.syspath_prepend(installed)
    return SCRIPTLESS_DISTRIBUTION


def test_a_member_distribution_without_console_scripts_is_refused(tmp_path, monkeypatch):
    """An installed distribution with no console script names no game."""
    distribution = install_distribution_without_console_scripts(
        tmp_path=tmp_path, monkeypatch=monkeypatch
    )
    recording = member_recording_path(tmp_path=tmp_path, distribution=distribution)

    with pytest.raises(KeyError, match=f"'{distribution}' has no console scripts"):
        recording_console_script(path=recording)


def test_a_member_recording_whose_distribution_is_not_installed_names_what_was_looked_for(
    tmp_path,
):
    """The member directory names a distribution that isn't installed: the refusal names it.

    It names the console script's distribution it looked for, and no install command (an
    unseen project may use any installer).
    """
    recording = member_recording_path(tmp_path=tmp_path, distribution='never-installed-game')

    with pytest.raises(KeyError) as refused:
        recording_console_script(path=recording)

    message = refused.value.args[0]
    assert "a console script of 'never-installed-game'" in message
    assert 'no distribution of that name is installed' in message
    assert 'uv sync' not in message


def test_a_projects_golden_is_its_projects_game_whatever_the_checkout_is_called(
    tmp_path, stand_in_game
):
    """A golden directly in ``tests/fixtures/replays/`` is replayed by its project's game.

    The project's ``pyproject.toml`` names the distribution (``[project] name``), so a checkout
    named otherwise (a fork, a ``game-main`` clone, a CI path) still claims its golden.
    """
    recording = member_recording_path(tmp_path=tmp_path, distribution='game-main')
    (tmp_path / 'game-main' / 'pyproject.toml').write_text(
        f'[project]\nname = {stand_in_game.distribution!r}\n', encoding='utf-8'
    )

    assert recording_console_script(path=recording) == stand_in_game.console_script


def test_a_projects_name_that_is_not_installed_is_named_in_the_refusal(tmp_path):
    """The project's ``[project] name`` is looked for, and named when it isn't installed."""
    recording = member_recording_path(tmp_path=tmp_path, distribution='game-main')
    (tmp_path / 'game-main' / 'pyproject.toml').write_text(
        "[project]\nname = 'never-installed-game'\n", encoding='utf-8'
    )

    with pytest.raises(KeyError) as refused:
        recording_console_script(path=recording)

    message = refused.value.args[0]
    assert "a console script of 'never-installed-game'" in message
    assert 'its project names the distribution' in message


def test_a_project_whose_pyproject_cannot_be_read_claims_no_golden(tmp_path):
    """A ``pyproject.toml`` that is not TOML names no distribution: refused, naming the file."""
    recording = member_recording_path(tmp_path=tmp_path, distribution='game-main')
    pyproject = tmp_path / 'game-main' / 'pyproject.toml'
    pyproject.write_text('[project\n', encoding='utf-8')

    with pytest.raises(KeyError, match=r'is not valid TOML'):
        recording_console_script(path=recording)


def test_children_import_without_pytest():
    """children.py imports in a child where importing pytest fails (it is in the dev extra)."""
    check = (
        'import sys; '
        "sys.modules['pytest'] = None; "
        'import glitchygames.replay.tools.children, glitchygames.replay.tools.identity, '
        'glitchygames.replay.tools.settings; '
        "print('imported')"
    )

    finished = run_command(
        command=[sys.executable, '-c', check],
        environment=os.environ,
        timeout_seconds=CHILD_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
    )

    assert finished.returncode == ExitCode.SUCCESS, finished.stdout
    assert finished.stdout.splitlines()[-1] == 'imported'


def test_a_recording_whose_fixtures_are_not_under_tests_is_refused(tmp_path):
    """Only <member>/tests/fixtures/replays/ names a member: another project's layout does not.

    The plugin ships in the engine's wheel, so a project laid out otherwise
    (``<project>/integration/fixtures/replays/``) must not be read as a member named after the
    directory four levels up, even when a distribution of that name is installed.
    """
    recording = tmp_path.joinpath(
        'mr-muncher', 'integration', *REPLAY_FIXTURES_PATH_PARTS, 'golden.jsonl.gz'
    )

    with pytest.raises(KeyError, match=r"above fixtures/ is 'integration', not 'tests'"):
        recording_console_script(path=recording)


def test_game_resolves_each_form(tmp_path, monkeypatch, stand_in_game):
    """A script path, MODULE:CALLABLE, a console script and a module: each starts the game.

    The stand-in's console script is ``stand-in-rally``; its package, ``stand_in_rally``, is no
    console script's name, so it resolves as a module.
    """
    script = tmp_path / 'scripts' / 'game.py'
    script.parent.mkdir()
    script.write_text('', encoding='utf-8')
    monkeypatch.chdir(tmp_path)

    by_path = resolve_game(game='scripts/game.py')
    by_entry_point = resolve_game(game='stand_in_rally:main')
    by_console_script = resolve_game(game=stand_in_game.console_script)
    by_module = resolve_game(game=stand_in_game.package)

    assert by_path == GameLaunch(form='script', command=[sys.executable, str(script.resolve())])
    assert by_entry_point == GameLaunch(
        form='entry-point',
        command=entry_point_command(
            entry_point=EntryPoint(
                name='stand_in_rally:main', value='stand_in_rally:main', group=CONSOLE_SCRIPTS_GROUP
            )
        ),
    )
    assert by_console_script == GameLaunch(
        form='console-script',
        command=entry_point_command(
            entry_point=game_entry_point(console_script=stand_in_game.console_script)
        ),
    )
    assert by_module == GameLaunch(form='module', command=[sys.executable, '-m', 'stand_in_rally'])


def test_a_script_named_without_a_directory_is_a_script(tmp_path, monkeypatch):
    """``game.py`` (no ``/``) ends in .py: a script path, read from the current directory."""
    (tmp_path / 'game.py').write_text('', encoding='utf-8')
    monkeypatch.chdir(tmp_path)

    launch = resolve_game(game='game.py')

    assert launch.form == 'script'
    assert launch.command == [sys.executable, str((tmp_path / 'game.py').resolve())]


def test_a_plain_name_prefers_the_console_script_over_the_module(tmp_path, monkeypatch):
    """A name that is both an installed console script and a module is the console script."""
    install_directory = tmp_path / 'site-packages'
    write_stand_in_game(directory=install_directory, console_script='stand_in_rally')
    use_stand_in_game(install_directory=install_directory, monkeypatch=monkeypatch)
    assert module_is_importable(module='stand_in_rally')

    launch = resolve_game(game='stand_in_rally')

    assert launch.form == 'console-script'


def test_a_module_in_the_project_root_is_found_there(tmp_path):
    """A package in --project-root (a child started there imports it) is a module game."""
    (tmp_path / 'local_game').mkdir()
    (tmp_path / 'local_game' / '__init__.py').write_text('', encoding='utf-8')

    launch = resolve_game(game='local_game', project_root=tmp_path)

    assert launch == GameLaunch(form='module', command=[sys.executable, '-m', 'local_game'])


def test_an_unknown_game_names_all_three_forms():
    """A plain name that is no console script and no module: every form is named."""
    with pytest.raises(UnknownGameError) as error:
        resolve_game(game='no_such_game_anywhere')

    message = str(error.value)
    assert "'no_such_game_anywhere' is not a game" in message
    assert len(GAME_FORMS) == 3
    assert 'a script path (contains / or ends in .py)' in message
    assert 'an entry point MODULE:CALLABLE' in message
    assert 'an installed console script or an importable module' in message


def test_a_game_with_a_slash_and_a_colon_is_a_script(tmp_path, monkeypatch):
    """``/`` is read first: ``scripts/game.py:main`` is a script path, not an entry point.

    No such script exists, so the refusal names the script it looked for (an entry point's
    would name its module).
    """
    monkeypatch.chdir(tmp_path)

    with pytest.raises(UnknownGameError, match=r'no script at scripts/game\.py:main'):
        resolve_game(game='scripts/game.py:main')


@pytest.mark.parametrize(
    ('game', 'reason'),
    [
        ('missing/game.py', 'no script at missing/game.py'),
        ('no_such_module:main', "its module 'no_such_module' does not import"),
    ],
)
def test_a_script_or_entry_point_that_is_not_there_is_an_unknown_game(
    tmp_path, monkeypatch, game, reason
):
    """A missing script, or an entry point whose module does not import, names no game."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(UnknownGameError, match=reason):
        resolve_game(game=game)


@pytest.mark.parametrize(
    ('module', 'importable'),
    [
        ('glitchygames', True),
        ('glitchygames.replay.tools.children', True),
        ('glitchygames.replay.no_such_module', False),
        # children is a module, not a package: nothing is inside it
        ('glitchygames.replay.tools.children.inner', False),
        ('no_such_package_anywhere.game', False),
        ('not a module', False),
        ('__main__', False),
    ],
)
def test_module_is_importable_finds_modules_without_importing_them(module, importable):
    """Each part is looked up in the package above it; ``__main__`` (a script's) never imports."""
    assert module_is_importable(module=module) is importable


def test_the_first_installed_console_script_of_a_name_is_kept(tmp_path, monkeypatch):
    """Two distributions with one console script name: the first on ``sys.path`` is its."""
    for directory_name, value in (('first', 'first_game:main'), ('second', 'second_game:main')):
        write_stand_in_distribution(
            directory=tmp_path / directory_name,
            distribution=f'{directory_name}-game',
            console_scripts={'shared-game': value},
        )
    monkeypatch.syspath_prepend(tmp_path / 'second')
    monkeypatch.syspath_prepend(tmp_path / 'first')

    (shared,) = [
        entry_point
        for entry_point in installed_console_scripts()
        if entry_point.name == 'shared-game'
    ]

    assert shared.value == 'first_game:main'


def test_launch_game_runs_its_command_with_the_arguments_in_the_project_root(tmp_path):
    """The child gets the tool's arguments after its command, in the working directory given."""
    launch = GameLaunch(
        form='script',
        command=[sys.executable, '-c', 'import os, sys; print(sys.argv[1:], os.getcwd())'],
    )

    finished = launch_game(
        launch=launch,
        arguments=['--replay-trace', 'run.jsonl.gz'],
        working_directory=tmp_path,
        capture_output=OutputCapture.TOGETHER,
    )

    assert finished.returncode == ExitCode.SUCCESS
    assert finished.stdout.strip() == f"['--replay-trace', 'run.jsonl.gz'] {tmp_path.resolve()}"


# A member's recording as Windows names it (a WindowsPath's str() has backslashes). The
# messages name a recording with / on every platform (as_posix), as the report and resolve_game
# do. Typed as a Path for the functions; a PureWindowsPath cannot be read here, so what reads
# the file (the project's pyproject.toml, the recording's header) is patched where needed
WINDOWS_MEMBER_RECORDING = PureWindowsPath(
    'C:\\games\\space-games\\tests\\fixtures\\replays\\golden.jsonl.gz'
)
WINDOWS_MEMBER_RECORDING_NAME = 'C:/games/space-games/tests/fixtures/replays/golden.jsonl.gz'
CHILDREN_MODULE = 'glitchygames.replay.tools.children'


def refusal_of(call) -> str:
    """Return the KeyError message a call raises.

    Returns:
        The message.

    """
    with pytest.raises(KeyError) as refused:
        call()
    return refused.value.args[0]


def assert_named_with_slashes(message: str, *, name: str) -> None:
    """Check a message starts with the recording's /-separated name and holds no backslash."""
    assert message.startswith(f'{name}: '), message
    assert '\\' not in message, message


def test_a_windows_recording_not_under_tests_is_named_with_slashes():
    """The refusal of a fixtures/replays/ outside <project>/tests/ names the path with /."""
    recording = PureWindowsPath('C:\\games\\x\\integration\\fixtures\\replays\\g.jsonl.gz')

    message = refusal_of(lambda: recording_console_script(path=recording))  # type: ignore[arg-type]

    assert_named_with_slashes(message, name='C:/games/x/integration/fixtures/replays/g.jsonl.gz')


def test_a_windows_recording_whose_pyproject_cannot_be_read_is_named_with_slashes(mocker):
    """A project whose pyproject.toml is not TOML: the refusal names the recording with /."""
    mocker.patch(
        f'{CHILDREN_MODULE}.project_name', side_effect=ProjectSettingsError('not valid TOML')
    )

    message = refusal_of(
        lambda: recording_console_script(path=WINDOWS_MEMBER_RECORDING)  # type: ignore[arg-type]
    )

    assert_named_with_slashes(message, name=WINDOWS_MEMBER_RECORDING_NAME)


def test_a_windows_recording_of_an_uninstalled_project_is_named_with_slashes(mocker):
    """The project names a distribution that is not installed: the recording is named with /."""
    mocker.patch(f'{CHILDREN_MODULE}.project_name', return_value='never-installed-game')

    message = refusal_of(
        lambda: recording_console_script(path=WINDOWS_MEMBER_RECORDING)  # type: ignore[arg-type]
    )

    assert_named_with_slashes(message, name=WINDOWS_MEMBER_RECORDING_NAME)


def test_a_windows_recording_of_a_project_without_console_scripts_is_named_with_slashes(
    mocker, tmp_path, monkeypatch
):
    """An installed distribution with no console script (a stand-in's): named with /."""
    distribution = install_distribution_without_console_scripts(
        tmp_path=tmp_path, monkeypatch=monkeypatch
    )
    mocker.patch(f'{CHILDREN_MODULE}.project_name', return_value=distribution)

    message = refusal_of(
        lambda: recording_console_script(path=WINDOWS_MEMBER_RECORDING)  # type: ignore[arg-type]
    )

    assert_named_with_slashes(message, name=WINDOWS_MEMBER_RECORDING_NAME)


def test_a_windows_recording_in_a_folder_that_is_no_console_script_is_named_with_slashes():
    """fixtures/replays/<folder>/: a folder naming no console script, the recording named with /."""
    recording = PureWindowsPath('C:\\games\\fixtures\\replays\\no-such-game\\golden.jsonl.gz')

    message = refusal_of(lambda: recording_console_script(path=recording))  # type: ignore[arg-type]

    assert_named_with_slashes(
        message, name='C:/games/fixtures/replays/no-such-game/golden.jsonl.gz'
    )


def test_a_windows_recording_without_a_game_in_its_header_is_named_with_slashes(mocker):
    """A header naming no game: the recording is named with /."""
    reader = mocker.patch(f'{CHILDREN_MODULE}.TraceReader')
    reader.return_value.__enter__.return_value.header = {}

    message = refusal_of(
        lambda: recorded_game_module(path=WINDOWS_MEMBER_RECORDING)  # type: ignore[arg-type]
    )

    assert_named_with_slashes(message, name=WINDOWS_MEMBER_RECORDING_NAME)


def test_a_windows_recording_whose_header_cannot_be_read_is_named_with_slashes(mocker):
    """A header that cannot be read to choose among several scripts: named with /."""
    mocker.patch(f'{CHILDREN_MODULE}.recorded_game_module', side_effect=OSError('unreadable'))

    message = refusal_of(
        lambda: recorded_games_console_script(
            path=WINDOWS_MEMBER_RECORDING,  # type: ignore[arg-type]
            distribution_name='space-games',
            entry_points=[],
        )
    )

    assert_named_with_slashes(message, name=WINDOWS_MEMBER_RECORDING_NAME)


def test_a_windows_recording_whose_game_no_console_script_starts_is_named_with_slashes(mocker):
    """None of the member's scripts starts the recorded game: named with /."""
    mocker.patch(f'{CHILDREN_MODULE}.recorded_game_module', return_value='other_game.game')
    entry_points = [
        EntryPoint(name='classic', value='space_game:main', group=CONSOLE_SCRIPTS_GROUP),
        EntryPoint(name='papyrus', value='space_game_papyrus:main', group=CONSOLE_SCRIPTS_GROUP),
    ]

    message = refusal_of(
        lambda: recorded_games_console_script(
            path=WINDOWS_MEMBER_RECORDING,  # type: ignore[arg-type]
            distribution_name='space-games',
            entry_points=entry_points,
        )
    )

    assert_named_with_slashes(message, name=WINDOWS_MEMBER_RECORDING_NAME)
