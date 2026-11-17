"""The listening-* tools: each command and game flag over the listening renders.

The renders' own rules are tested in tests/audio/test_listening.py; these check what each tool
adds: its options, what it prints (each file's path on standard output, the summary on standard
error), its exit code, and the refusal without a disk cache. Each tool on both front ends, on an
unseen game, is in tests/replay/tools/test_an_unseen_game.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from glitchygames.audio.disk_cache import SOUND_CACHE_ROOT_VARIABLE
from glitchygames.audio.listening import listening_directory
from glitchygames.exit_codes import ExitCode
from glitchygames.replay.tools import command
from glitchygames.replay.tools.listening_tools import (
    listening_instruments_on_the_game,
    listening_pipes_on_the_game,
)
from glitchygames.scenes import Scene


@pytest.fixture
def cache_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The sound cache's root, a fresh folder.

    Returns:
        The root.
    """
    root = tmp_path / 'sound-cache'
    root.mkdir()
    monkeypatch.setenv(SOUND_CACHE_ROOT_VARIABLE, str(root))
    return root


def test_listening_pipes_prints_each_file_written_then_kept(cache_root, capsys):
    """The paths go to standard output (a player opens them), the summary to standard error."""
    directory = listening_directory(root=cache_root) / 'pipes'
    expected = [
        str(directory / 'highland_chanter_A.wav'),
        str(directory / 'uilleann_chanter_A.wav'),
    ]

    first = command.main(['listening-pipes', '--only', 'chanter_A'])
    first_output = capsys.readouterr()
    again = command.main(['listening-pipes', '--only', 'chanter_A'])
    again_output = capsys.readouterr()

    assert (first, again) == (ExitCode.SUCCESS, ExitCode.SUCCESS)
    assert first_output.out.splitlines() == expected
    assert '2 written, 0 already kept' in first_output.err
    assert again_output.out.splitlines() == expected
    assert '0 written, 2 already kept' in again_output.err


def test_listening_instruments_takes_a_family_and_a_name(cache_root, capsys):
    """--family and --only together: the uilleann pipes of the bagpipes family."""
    status = command.main([
        'listening-instruments',
        '--family',
        'bagpipes',
        '--only',
        'uilleann',
    ])

    assert status == ExitCode.SUCCESS
    paths = capsys.readouterr().out.splitlines()
    assert paths
    # Compared by parts: a printed path is native (backslashes on Windows)
    assert all(
        Path(path).parent.name == 'bagpipes' and 'uilleann' in Path(path).stem for path in paths
    )


def test_an_unknown_family_is_an_argument_error(cache_root):
    """Argparse refuses it, naming the families."""
    with pytest.raises(SystemExit) as refusal:
        command.main(['listening-instruments', '--family', 'kazoos'])

    assert refusal.value.code == ExitCode.ARGUMENT_PARSER_ERROR


@pytest.mark.parametrize(
    ('handler', 'options'),
    [
        (listening_pipes_on_the_game, {'only': 'uilleann_chanter'}),
        (listening_instruments_on_the_game, {'family': 'bagpipes', 'only': 'highland'}),
    ],
    ids=['pipes', 'instruments'],
)
def test_on_a_game_the_flag_renders_the_same_files(handler, options, cache_root, capsys):
    """The listening files are no game's: a game's flag renders them as the command does."""
    status = handler(options=options, game=Scene)

    assert status == ExitCode.SUCCESS
    paths = capsys.readouterr().out.splitlines()
    assert paths
    assert all(path.startswith(str(listening_directory(root=cache_root))) for path in paths)


@pytest.mark.parametrize('tool', ['listening-instruments', 'listening-pipes'])
def test_without_a_disk_cache_each_tool_is_refused(tool, monkeypatch, capsys):
    """An empty root variable means no cache root to render into: refused, saying why."""
    monkeypatch.setenv(SOUND_CACHE_ROOT_VARIABLE, '')

    assert command.main([tool]) == ExitCode.OPTIONS_REFUSED
    assert f'{SOUND_CACHE_ROOT_VARIABLE} is empty' in capsys.readouterr().err


@pytest.mark.parametrize(
    ('handler', 'flag'),
    [
        (listening_instruments_on_the_game, '--listening-instruments'),
        (listening_pipes_on_the_game, '--listening-pipes'),
    ],
)
def test_without_a_disk_cache_each_game_flag_is_refused(handler, flag, monkeypatch, caplog):
    """On a game the refusal is logged as an error, naming the flag and the variable."""
    monkeypatch.setenv(SOUND_CACHE_ROOT_VARIABLE, '')

    assert handler(options={}, game=Scene) == ExitCode.OPTIONS_REFUSED
    assert f'{flag}: {SOUND_CACHE_ROOT_VARIABLE} is empty' in caplog.text
