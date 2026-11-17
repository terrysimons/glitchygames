"""The sound-cache-* tools: each command and game flag over the cache API (sound_cache_tools.py).

The API's own rules are tested in tests/audio/test_cache_inventory.py; these check what each tool
adds: which folders it works on, what it prints, its exit code, and the refusal when there is no
disk cache. A command naming a game runs it as a child: tests/replay/tools/test_an_unseen_game.py
covers that, in all three GAME forms.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import numpy as np
import pytest

from glitchygames.audio.disk_cache import (
    SOUND_CACHE_ROOT_VARIABLE,
    DiskSoundCache,
    sounds_directory,
)
from glitchygames.audio.effects import Effect, Tone
from glitchygames.audio.library import ENGINE_SOUND_CACHE
from glitchygames.audio.synth import Envelope, Waveform
from glitchygames.exit_codes import ExitCode
from glitchygames.replay.tools import command
from glitchygames.replay.tools.sound_cache_tools import (
    sound_cache_clear_on_the_game,
    sound_cache_fill_on_the_game,
    sound_cache_list_on_the_game,
    sound_cache_size_on_the_game,
    sound_cache_verify_on_the_game,
)
from glitchygames.scenes import Scene

if TYPE_CHECKING:
    from pathlib import Path

CURRENT = 5
RATE = 44100
# A scene class defined here is in package ``tests``: its folder (identity.game_package)
THIS_GAME = 'tests'
OTHER_GAME = 'paddleslap'
COMMANDS = (
    'sound-cache-list',
    'sound-cache-size',
    'sound-cache-verify',
    'sound-cache-clear',
    'sound-cache-fill',
)
GAME_HANDLERS = (
    sound_cache_list_on_the_game,
    sound_cache_size_on_the_game,
    sound_cache_verify_on_the_game,
    sound_cache_clear_on_the_game,
    sound_cache_fill_on_the_game,
)


class GameWithOneSound(Scene):
    """A stand-in game declaring one short effect."""

    SOUNDS: ClassVar = (
        Effect(
            name='blip',
            tones=(
                Tone(
                    waveform=Waveform.SINE,
                    start_frequency=440.0,
                    duration=0.02,
                    envelope=Envelope(attack=0.001, decay=0.0, sustain_level=1.0, release=0.01),
                ),
            ),
        ),
    )


@pytest.fixture(autouse=True)
def current_render_version(mocker):
    """Render version 5 is current, so versions below it are stale."""
    mocker.patch('glitchygames.audio.cache_inventory.AUDIO_RENDER_VERSION', CURRENT)
    mocker.patch('glitchygames.audio.engine.AUDIO_RENDER_VERSION', CURRENT)


@pytest.fixture
def cache_root(tmp_path, monkeypatch) -> Path:
    """The sound cache's root, a fresh folder (a clear may leave it empty, which is the point).

    Returns:
        The root.
    """
    root = tmp_path / 'sound-cache'
    root.mkdir()
    monkeypatch.setenv(SOUND_CACHE_ROOT_VARIABLE, str(root))
    return root


def _write_sounds(root: Path, *, game: str, version: int, count: int) -> list[Path]:
    """Write ``count`` sounds into a game's folder for a render version, as a game would.

    Returns:
        Their files.
    """
    directory = sounds_directory(root=root, game=game, render_version=version)
    cache = DiskSoundCache(directory=directory, limit_bytes=64 * 1024 * 1024)
    for index in range(count):
        cache.write(
            identity_key=f'{index:02x}' + 'a' * 30,
            samples_int16=np.zeros(100, dtype=np.int16),
            peak=0.5,
            sample_rate=RATE,
        )
    return sorted(directory.rglob('*.wav'))


def _two_games(root: Path) -> None:
    """This game: two current sounds and one stale; another game: three current."""
    _write_sounds(root, game=THIS_GAME, version=CURRENT, count=2)
    _write_sounds(root, game=THIS_GAME, version=CURRENT - 1, count=1)
    _write_sounds(root, game=OTHER_GAME, version=CURRENT, count=3)


# --- The commands, with no game: the whole root ---


def test_list_names_every_folder_then_the_total(cache_root, capsys):
    """One line per game and render version, the stale one marked, then the total."""
    _two_games(cache_root)

    assert command.main(['sound-cache-list']) == ExitCode.SUCCESS

    lines = capsys.readouterr().out.splitlines()
    assert [line.split(':')[0] for line in lines] == [
        f'{OTHER_GAME} render {CURRENT}',
        f'{THIS_GAME} render {CURRENT - 1}',
        f'{THIS_GAME} render {CURRENT}',
        'total',
    ]
    assert lines[1].endswith('(stale)')
    assert not lines[2].endswith('(stale)')
    assert lines[3].startswith('total: 3 folders')


def test_size_counts_every_sound_and_the_stale_bytes_apart(cache_root, capsys):
    """Six sounds; the one stale sound's bytes are said apart."""
    _two_games(cache_root)
    (stale,) = (cache_root / THIS_GAME / 'sounds' / str(CURRENT - 1)).rglob('*.wav')
    stale_kilobytes = stale.stat().st_size / 1024

    assert command.main(['sound-cache-size']) == ExitCode.SUCCESS

    line = capsys.readouterr().out.strip()
    assert line.startswith('6 sounds, ')
    assert f'({stale_kilobytes:.1f} KB stale)' in line


def test_verify_lists_a_damaged_file_and_exits_unusable_input(cache_root, capsys):
    """So a CI step or a script can rely on the exit code, not the text."""
    _two_games(cache_root)
    damaged = _write_sounds(cache_root, game=OTHER_GAME, version=CURRENT, count=1)[0]
    damaged.write_bytes(b'not a sound')

    assert command.main(['sound-cache-verify']) == ExitCode.UNUSABLE_INPUT

    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith(f'{damaged}: not a WAV file')
    assert lines[-1] == 'checked 6 sounds: 1 damaged'
    assert damaged.exists()  # verify removes nothing


def test_verify_of_a_sound_cache_in_good_order_exits_success(cache_root, capsys):
    """Nothing damaged: success, and the count said."""
    _two_games(cache_root)

    assert command.main(['sound-cache-verify']) == ExitCode.SUCCESS
    assert capsys.readouterr().out.strip() == 'checked 6 sounds: 0 damaged'


def test_clear_removes_every_games_folders(cache_root, capsys):
    """With no game named, every game's folders go; the root itself stays."""
    _two_games(cache_root)

    assert command.main(['sound-cache-clear']) == ExitCode.SUCCESS

    assert capsys.readouterr().out.startswith('removed 6 sounds')
    assert cache_root.is_dir()
    assert list(cache_root.iterdir()) == []


def test_clear_stale_only_keeps_the_current_versions(cache_root, capsys):
    """Only the older render version goes."""
    _two_games(cache_root)

    assert command.main(['sound-cache-clear', '--stale-only']) == ExitCode.SUCCESS

    assert capsys.readouterr().out.startswith('removed 1 sounds')
    assert len(list(cache_root.rglob('*.wav'))) == 5


def test_fill_with_no_game_runs_the_projects_games(cache_root, tmp_path, capsys):
    """Fill needs each game's sounds, so it runs the settings' games, never the whole root.

    The games named here are not installed, so each is refused by name: proof the command read
    them from the settings without starting anything.
    """
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'pyproject.toml').write_text(
        '[project]\nname = "project"\n\n'
        '[tool.glitchygames]\ngames = ["not-installed-one", "not-installed-two"]\n',
        encoding='utf-8',
    )

    status = command.main(['sound-cache-fill', '--project-root', str(project)])

    assert status == ExitCode.OPTIONS_REFUSED
    errors = capsys.readouterr().err
    assert 'not-installed-one' in errors
    assert 'not-installed-two' in errors
    assert list(cache_root.iterdir()) == []


def _game_script(directory: Path, *, name: str, exit_code: int) -> Path:
    """A stand-in game started as a child: it records the arguments it got, then exits.

    The game's side of the contract is only this: it is started with the tool's flag and
    options, and its exit code is the command's to combine.

    Returns:
        The script.
    """
    script = directory / f'{name}.py'
    script.write_text(
        'import json, pathlib, sys\n'
        f'pathlib.Path(sys.argv[0]).with_suffix(".json").write_text(json.dumps(sys.argv[1:]))\n'
        f'sys.exit({exit_code})\n',
        encoding='utf-8',
    )
    return script


def test_a_command_runs_each_named_game_with_its_flag(cache_root, tmp_path, capsys):
    """Each --game is started with the tool's flag and options; the worst exit code wins."""
    import json

    first = _game_script(tmp_path, name='first', exit_code=ExitCode.SUCCESS)
    second = _game_script(tmp_path, name='second', exit_code=ExitCode.UNUSABLE_INPUT)

    status = command.main([
        'sound-cache-clear',
        '--stale-only',
        '--game',
        str(first),
        '--game',
        str(second),
    ])

    assert status == ExitCode.UNUSABLE_INPUT
    for script in (first, second):
        started_with = json.loads(script.with_suffix('.json').read_text(encoding='utf-8'))
        assert started_with == ['--sound-cache-clear', '--stale-only']
    assert f'running {first}' in capsys.readouterr().err


def test_fill_in_a_project_naming_no_games_says_so(cache_root, tmp_path, capsys):
    """Nothing to fill is said, not passed over as a silent success."""
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'pyproject.toml').write_text('[project]\nname = "project"\n', encoding='utf-8')

    status = command.main(['sound-cache-fill', '--project-root', str(project)])

    assert status == ExitCode.SUCCESS
    assert 'no games to fill' in capsys.readouterr().err


@pytest.mark.parametrize('tool', [tool for tool in COMMANDS if tool != 'sound-cache-fill'])
def test_only_fill_reads_the_projects_settings(tool, cache_root, tmp_path, monkeypatch):
    """The other four never read the project's settings.

    They work on the cache root or the games named: a broken pyproject.toml in the current
    directory is none of their business.
    """
    (tmp_path / 'pyproject.toml').write_text('[tool.glitchygames\n', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    game = _game_script(tmp_path, name='game', exit_code=ExitCode.SUCCESS)

    assert command.main([tool]) == ExitCode.SUCCESS
    assert command.main([tool, '--game', str(game)]) == ExitCode.SUCCESS


def test_a_command_with_unreadable_settings_is_unusable_input(cache_root, tmp_path, capsys):
    """Fill reads the project's games from its settings; settings that can't be read refuse."""
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'pyproject.toml').write_text('[tool.glitchygames\n', encoding='utf-8')

    status = command.main(['sound-cache-fill', '--project-root', str(project)])

    assert status == ExitCode.UNUSABLE_INPUT


@pytest.mark.parametrize('tool', COMMANDS)
@pytest.mark.parametrize('games', [[], ['--game', 'not-installed']], ids=['no game', 'a game'])
def test_every_command_without_a_disk_cache_is_refused(tool, games, monkeypatch, capsys):
    """An empty root variable means no disk cache: refused up front, before any game starts."""
    monkeypatch.setenv(SOUND_CACHE_ROOT_VARIABLE, '')

    status = command.main([tool, *games])

    assert status == ExitCode.OPTIONS_REFUSED
    errors = capsys.readouterr().err
    assert f'{SOUND_CACHE_ROOT_VARIABLE} is empty' in errors
    assert 'not-installed' not in errors  # no game was looked up


# --- The game flags: one game's own folders ---


def test_list_on_the_game_names_only_its_folders(cache_root, capsys):
    """Another game's folder is left out, and so is its size from the total."""
    _two_games(cache_root)

    status = sound_cache_list_on_the_game(options={}, game=GameWithOneSound)

    assert status == ExitCode.SUCCESS
    lines = capsys.readouterr().out.splitlines()
    assert all(line.startswith(THIS_GAME) for line in lines[:-1])
    assert lines[-1].startswith('total: 2 folders')


def test_size_on_the_game_counts_only_its_sounds(cache_root, capsys):
    """Three of the six sounds are this game's."""
    _two_games(cache_root)

    status = sound_cache_size_on_the_game(options={}, game=GameWithOneSound())

    assert status == ExitCode.SUCCESS
    assert capsys.readouterr().out.startswith('3 sounds, ')


def test_verify_on_the_game_checks_only_its_files(cache_root, capsys):
    """Another game's damaged file is not this game's to report."""
    _two_games(cache_root)
    _write_sounds(cache_root, game=OTHER_GAME, version=CURRENT, count=1)[0].write_bytes(b'x')

    status = sound_cache_verify_on_the_game(options={}, game=GameWithOneSound)

    assert status == ExitCode.SUCCESS
    assert capsys.readouterr().out.strip() == 'checked 3 sounds: 0 damaged'


def test_verify_on_the_game_reports_its_damaged_file(cache_root, capsys):
    """Its own damaged file: listed, and the exit code says so."""
    damaged = _write_sounds(cache_root, game=THIS_GAME, version=CURRENT, count=1)[0]
    damaged.write_bytes(b'x')

    status = sound_cache_verify_on_the_game(options={}, game=GameWithOneSound)

    assert status == ExitCode.UNUSABLE_INPUT
    assert capsys.readouterr().out.startswith(f'{damaged}: not a WAV file')


@pytest.mark.parametrize(
    ('options', 'left'),
    [({}, {OTHER_GAME}), ({'stale_only': True}, {OTHER_GAME, THIS_GAME})],
    ids=['all its versions', 'stale only'],
)
def test_clear_on_the_game_removes_only_its_folders(cache_root, options, left, capsys):
    """Another game's folder stays; with stale_only, so does its own current version."""
    _two_games(cache_root)

    status = sound_cache_clear_on_the_game(options=options, game=GameWithOneSound)

    assert status == ExitCode.SUCCESS
    assert {path.name for path in cache_root.iterdir()} == left
    assert capsys.readouterr().out.startswith('removed ')


def test_fill_on_the_game_writes_its_sounds_into_its_folder(cache_root, capsys):
    """Its declared sound plus the CRT power-on's six, in its own folder."""
    ENGINE_SOUND_CACHE.clear()

    status = sound_cache_fill_on_the_game(options={}, game=GameWithOneSound)

    assert status == ExitCode.SUCCESS
    folder = sounds_directory(root=cache_root, game=THIS_GAME, render_version=CURRENT)
    assert len(list(folder.rglob('*.wav'))) == 1 + 6
    assert capsys.readouterr().out.startswith(f'{THIS_GAME}: 7 sounds written, 0 already kept')


@pytest.mark.parametrize('handler', GAME_HANDLERS, ids=lambda handler: handler.__name__)
def test_every_game_flag_without_a_disk_cache_is_refused(handler, monkeypatch, caplog):
    """The refusal is logged as an error, naming the flag and the variable."""
    monkeypatch.setenv(SOUND_CACHE_ROOT_VARIABLE, '')

    status = handler(options={}, game=GameWithOneSound)

    assert status == ExitCode.OPTIONS_REFUSED
    flag = '--' + handler.__name__.removesuffix('_on_the_game').replace('_', '-')
    assert f'{flag}: {SOUND_CACHE_ROOT_VARIABLE} is empty' in caplog.text
