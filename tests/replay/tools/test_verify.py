"""The ``verify`` tool (glitchygames/replay/tools/verify.py): every recording replayed and judged.

``--verify [PATH ...] [--only TEXT]`` on a game and ``glitchygames verify [PATH ...] [--only TEXT]
[--game NAME ...]``: each recording is replayed headless in a child process, one line says how
each went, and the run exits ``SUCCESS`` only when every one matched. The end-to-end cases run the
stand-in game (tests/stand_in_games.py) in children; the in-process cases cover the rest.
"""

from __future__ import annotations

import os
import shutil
import signal
import sys
from typing import TYPE_CHECKING

import pygame
import pytest

from glitchygames.exit_codes import ExitCode
from glitchygames.process import CompletedProcess, OutputCapture, TimeoutExpired, run_command
from glitchygames.replay.tools import command, registry, traces, verify
from glitchygames.replay.tools.children import GameLaunch, running_game_command
from glitchygames.replay.tools.identity import GameIdentity
from glitchygames.replay.tools.settings import ProjectSettings
from glitchygames.replay.tools.verify import (
    recording_name,
    replay_outcome,
    verification_exit_code,
)
from tests.replay.replay_helpers import tamper_first_sprite_rect
from tests.stand_in_games import (
    NEVER_ENDING_GAME_TIMEOUT_SECONDS,
    RECORD_TIMEOUT_SECONDS,
    STAND_IN_GAME_FRAMES,
    STAND_IN_GAME_RESOLUTION,
    GameThatIsNeverBuilt,
    StandInGame,
    record_stand_in_game,
    stand_in_game_source,
    use_stand_in_game,
    write_header_only_recording,
    write_never_ending_game_project,
    write_stand_in_game,
)

if TYPE_CHECKING:
    from pathlib import Path

# The frame the tampered recording's sprite moves on (the stand-in draws one on every frame)
TAMPERED_FRAME = 10
# Where the stand-in's goldens go in its project: another project's layout,
# tests/fixtures/replays/<console-script>/, which the default golden-globs read
GOLDEN_DIRECTORY_PARTS = ('tests', 'fixtures', 'replays')
# What the engine logs once per engine it builds (print_game_info): the game verifying builds none
ONE_LINE_PER_ENGINE = 'Game Title: '
# What a child's replay prints when it diverges
DIVERGED_AT_THE_TAMPERED_FRAME = f'Replay diverged at frame {TAMPERED_FRAME}'


@pytest.fixture
def stand_in_game(tmp_path_factory, monkeypatch) -> StandInGame:
    """Install the stand-in game for this test and its children.

    Its facts: one console script (``stand-in-rally``) in package ``stand_in_rally``, a sprite
    on every frame, seeded and deterministic; it quits itself after 20 frames.

    Returns:
        The stand-in game.

    """
    install_directory = tmp_path_factory.mktemp('site-packages')
    game = write_stand_in_game(directory=install_directory)
    use_stand_in_game(install_directory=install_directory, monkeypatch=monkeypatch)
    return game


@pytest.fixture
def stand_in_project(tmp_path, stand_in_game) -> Path:
    """A project whose settings name the stand-in game, with one good and one tampered golden.

    Returns:
        The project's root.

    """
    project = tmp_path / 'project'
    goldens = project.joinpath(*GOLDEN_DIRECTORY_PARTS, stand_in_game.console_script)
    goldens.mkdir(parents=True)
    good = record_stand_in_game(game=stand_in_game, path=goldens / 'good.jsonl.gz')
    shutil.copyfile(good, goldens / 'tampered.jsonl.gz')
    tamper_first_sprite_rect(recording_path=goldens / 'tampered.jsonl.gz', frame_number=10)
    (project / 'pyproject.toml').write_text(
        f'[tool.glitchygames]\ngames = [{stand_in_game.console_script!r}]\n', encoding='utf-8'
    )
    return project


def run_game_flag(
    *, game: StandInGame, arguments: list[str], working_directory: Path
) -> tuple[int, str]:
    """Run the stand-in game in a child with a tool flag, its log at info level.

    Returns:
        The child's exit status and its output (standard output and error together).

    """
    completed = run_command(
        command=[
            sys.executable,
            '-c',
            f'import {game.package}; {game.package}.main()',
            '--log-level',
            'info',
            '--resolution',
            STAND_IN_GAME_RESOLUTION,
            '--headless',
            *arguments,
        ],
        environment=os.environ,
        timeout_seconds=RECORD_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
        working_directory=working_directory,
    )
    return completed.returncode, completed.stdout or ''


def golden_name(*, game: StandInGame, name: str) -> str:
    """Return how a verify line names a golden of the stand-in project (relative to its root).

    Returns:
        The name.

    """
    return '/'.join((*GOLDEN_DIRECTORY_PARTS, game.console_script, name))


def assert_one_line_each(*, output: str, game: StandInGame, names: tuple[str, ...]) -> None:
    """Assert the good golden passed and the tampered one failed, each on its own line.

    Args:
        output: What the verify run printed.
        game: The stand-in game.
        names: The goldens it verified (``good.jsonl.gz``, ``tampered.jsonl.gz``).

    """
    lines = output.splitlines()
    if 'good.jsonl.gz' in names:
        good = golden_name(game=game, name='good.jsonl.gz')
        assert f'PASS {good}: Replay matched {STAND_IN_GAME_FRAMES} frames' in '\n'.join(lines)
    if 'tampered.jsonl.gz' in names:
        tampered = golden_name(game=game, name='tampered.jsonl.gz')
        (failed,) = [line for line in lines if line.startswith(f'FAIL {tampered}: ')]
        assert failed.startswith(
            f'FAIL {tampered}: REPLAY_DIVERGED (1): {DIVERGED_AT_THE_TAMPERED_FRAME}'
        ), failed
    passed_or_failed = [line for line in lines if line.startswith(('PASS ', 'FAIL '))]
    assert len(passed_or_failed) == len(names), output


def test_verify_passes_and_fails_per_recording_as_a_flag_and_a_command(
    stand_in_game, stand_in_project, capfd
):
    """One good and one tampered golden: a PASS line and a FAIL line, and REPLAY_DIVERGED.

    On the game, with no paths: the game's own goldens (the project's, which its console script
    replays), each replayed by a child; the game itself builds no engine (no "Game Title"). With
    ``--only good``: that one alone, and SUCCESS. On the command: every configured game's
    (``[tool.glitchygames] games``), the same named with ``--game``, and recordings named by
    path, whose game comes from their header.
    """
    both = ('good.jsonl.gz', 'tampered.jsonl.gz')
    flag_status, flag_output = run_game_flag(
        game=stand_in_game, arguments=['--verify'], working_directory=stand_in_project
    )
    only_status, only_output = run_game_flag(
        game=stand_in_game,
        arguments=['--verify', '--only', 'good'],
        working_directory=stand_in_project,
    )
    configured_status = command.main(['verify', '--project-root', str(stand_in_project)])
    configured = capfd.readouterr()
    named_status = command.main([
        'verify',
        '--game',
        stand_in_game.console_script,
        '--project-root',
        str(stand_in_project),
    ])
    named = capfd.readouterr()
    goldens = stand_in_project.joinpath(*GOLDEN_DIRECTORY_PARTS, stand_in_game.console_script)
    by_path_status = command.main([
        'verify',
        str(goldens / 'good.jsonl.gz'),
        str(goldens / 'tampered.jsonl.gz'),
        '--project-root',
        str(stand_in_project),
    ])
    by_path = capfd.readouterr()

    assert flag_status == ExitCode.REPLAY_DIVERGED, flag_output
    assert_one_line_each(output=flag_output, game=stand_in_game, names=both)
    assert 'verify: 1 of 2 recordings passed' in flag_output
    assert ONE_LINE_PER_ENGINE not in flag_output
    assert only_status == ExitCode.SUCCESS, only_output
    assert_one_line_each(output=only_output, game=stand_in_game, names=('good.jsonl.gz',))
    assert ONE_LINE_PER_ENGINE not in only_output
    for status, captured in (
        (configured_status, configured),
        (named_status, named),
        (by_path_status, by_path),
    ):
        assert status == ExitCode.REPLAY_DIVERGED, captured.out + captured.err
        assert_one_line_each(output=captured.out, game=stand_in_game, names=both)
    for captured in (configured, named):
        assert (
            f'glitchygames verify: running {stand_in_game.console_script} '
            '(an installed console script)'
        ) in captured.err


def test_a_golden_no_configured_game_claims_fails_and_the_projects_own_is_verified(
    stand_in_game, tmp_path, capfd
):
    """Games from the settings: every golden is verified, or failed with why; none is skipped.

    A single-game project checked out in a directory named otherwise than its distribution
    (``game-main``): its golden directly in ``tests/fixtures/replays/`` is its game's (the
    project's ``[project] name`` says which distribution), so it is replayed. A golden no
    configured game replays (its folder names no console script) is a FAIL line naming it and
    why, ``INTERNAL_ERROR`` (70), as ``measure`` fails it. ``--only`` leaves out what it doesn't
    keep, that line included.
    """
    project = tmp_path / 'game-main'
    goldens = project.joinpath(*GOLDEN_DIRECTORY_PARTS)
    goldens.mkdir(parents=True)
    good = record_stand_in_game(game=stand_in_game, path=goldens / 'good.jsonl.gz')
    stray = goldens / 'no-such-console-script' / 'stray.jsonl.gz'
    stray.parent.mkdir()
    shutil.copyfile(good, stray)
    (project / 'pyproject.toml').write_text(
        f'[project]\nname = {stand_in_game.distribution!r}\n\n[project.scripts]\n'
        f"{stand_in_game.console_script!r} = '{stand_in_game.package}:main'\n",
        encoding='utf-8',
    )

    every_status = command.main(['verify', '--project-root', str(project)])
    every = capfd.readouterr()
    only_status = command.main(['verify', '--only', 'good', '--project-root', str(project)])
    only = capfd.readouterr()

    assert every_status == ExitCode.INTERNAL_ERROR, every.out + every.err
    assert (
        f'PASS tests/fixtures/replays/good.jsonl.gz: Replay matched {STAND_IN_GAME_FRAMES} frames'
    ) in every.out
    assert (
        'FAIL tests/fixtures/replays/no-such-console-script/stray.jsonl.gz: INTERNAL_ERROR (70): '
        "the directory 'no-such-console-script' is not a console script"
    ) in every.out
    assert only_status == ExitCode.SUCCESS, only.out + only.err
    assert 'stray.jsonl.gz' not in only.out
    assert 'PASS tests/fixtures/replays/good.jsonl.gz' in only.out


def test_verify_with_no_recordings_says_so(stand_in_game, tmp_path, capfd):
    """No recordings to verify is no failure: it is said, and the run exits SUCCESS.

    The game in a project with no goldens (the stand-in's package has no demos), the command
    naming it, and the command in a project that configures no game at all.
    """
    project = tmp_path / 'empty-project'
    project.mkdir()
    (project / 'pyproject.toml').write_text('', encoding='utf-8')
    no_games = tmp_path / 'no-games'
    no_games.mkdir()
    (no_games / 'pyproject.toml').write_text('[tool.glitchygames]\ngames = []\n', encoding='utf-8')

    flag_status, flag_output = run_game_flag(
        game=stand_in_game, arguments=['--verify'], working_directory=project
    )
    command_status = command.main([
        'verify',
        '--game',
        stand_in_game.console_script,
        '--project-root',
        str(project),
    ])
    named = capfd.readouterr()
    no_games_status = command.main(['verify', '--project-root', str(no_games)])
    unconfigured = capfd.readouterr()

    assert flag_status == ExitCode.SUCCESS, flag_output
    assert 'verify: no recordings found' in flag_output
    assert command_status == ExitCode.SUCCESS, named.out + named.err
    assert 'verify: no recordings found' in named.out
    assert no_games_status == ExitCode.SUCCESS, unconfigured.out + unconfigured.err
    assert 'no games to verify' in unconfigured.out


def write_script_game(*, directory: Path) -> Path:
    """Write the stand-in game as a script (``python game.py``): no console script starts it.

    Returns:
        The script.

    """
    script = directory / 'script_game.py'
    source = stand_in_game_source(
        package='script_game',
        scene_name='ScriptGameScene',
        frames_before_quit=STAND_IN_GAME_FRAMES,
        layer=None,
    )
    script.write_text(f"{source}\n\nif __name__ == '__main__':\n    main()\n", encoding='utf-8')
    return script


def test_a_game_run_as_a_script_verifies_the_paths_it_is_given(tmp_path):
    """A game started as ``python game.py --verify PATH`` replays PATH by starting itself again.

    No console script starts it, so it has no recordings of its own to find; the one named is
    replayed by the same script, and matches.
    """
    script = write_script_game(directory=tmp_path)
    recording = tmp_path / 'script.jsonl.gz'
    arguments = ['--headless', '--resolution', STAND_IN_GAME_RESOLUTION, '--log-level', 'error']
    recorded = run_command(
        command=[sys.executable, str(script), *arguments, '--record-trace', str(recording)],
        environment=os.environ,
        timeout_seconds=RECORD_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
        working_directory=tmp_path,
    )
    assert recorded.returncode == ExitCode.SUCCESS, recorded.stdout

    verified = run_command(
        command=[sys.executable, str(script), *arguments, '--verify', str(recording)],
        environment=os.environ,
        timeout_seconds=RECORD_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
        working_directory=tmp_path,
    )
    found = run_command(
        command=[sys.executable, str(script), *arguments, '--verify'],
        environment=os.environ,
        timeout_seconds=RECORD_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
        working_directory=tmp_path,
    )

    assert verified.returncode == ExitCode.SUCCESS, verified.stdout
    assert f'PASS script.jsonl.gz: Replay matched {STAND_IN_GAME_FRAMES}' in verified.stdout
    assert found.returncode == ExitCode.SUCCESS, found.stdout
    assert 'verify: no recordings found' in found.stdout
    assert 'no console script starts this game' in found.stdout


@pytest.mark.parametrize(
    ('statuses', 'expected'),
    [
        ([], ExitCode.SUCCESS),
        ([ExitCode.SUCCESS, ExitCode.SUCCESS], ExitCode.SUCCESS),
        ([ExitCode.SUCCESS, ExitCode.REPLAY_DIVERGED], ExitCode.REPLAY_DIVERGED),
        (
            [ExitCode.REPLAY_DIVERGED, ExitCode.MISSING_INPUT, ExitCode.UNUSABLE_INPUT],
            ExitCode.MISSING_INPUT,
        ),
        ([ExitCode.SUCCESS, ExitCode.PROCESSING_SLOWER], ExitCode.PROCESSING_SLOWER),
        # Not an exit code of the engine's (killed by a signal, or a number of its own)
        ([ExitCode.SUCCESS, -9], ExitCode.INTERNAL_ERROR),
        ([ExitCode.REPLAY_DIVERGED, 42], ExitCode.INTERNAL_ERROR),
    ],
)
def test_the_exit_code_says_whether_every_recording_matched_and_else_why_not(statuses, expected):
    """SUCCESS when all matched, else REPLAY_DIVERGED or the first other failure's code.

    REPLAY_DIVERGED when the only failures are divergences; INTERNAL_ERROR for a status that is
    not one of the engine's. None found is SUCCESS.
    """
    assert verification_exit_code(statuses=statuses) == expected


@pytest.mark.parametrize(
    ('output', 'reason'),
    [
        ('starting\nReplay matched 5 frames (end of recording)\n', 'Replay matched 5 frames'),
        (
            'Replay diverged at frame 3: sprite A\nA, last 20 frames:\n',
            'Replay diverged at frame 3',
        ),
        ('Traceback (most recent call last):\nRuntimeError: boom\n\n', 'RuntimeError: boom'),
        ('', 'no output'),
    ],
)
def test_a_replays_line_gives_its_report_else_its_last_words(output, reason):
    """The replay's own report line (``Replay ...``), else the child's last line, else none."""
    finished = CompletedProcess(args=[], returncode=0, stdout=output)

    assert replay_outcome(finished=finished).startswith(reason)


def test_a_recording_is_named_relative_to_the_project_else_by_its_path(tmp_path):
    """Inside the project, its project-relative path; outside it (an installed demo), its path."""
    project = tmp_path / 'project'
    inside = project / 'tests' / 'run.jsonl.gz'
    outside = tmp_path / 'site-packages' / 'game' / 'demos' / 'demo.jsonl.gz'

    assert recording_name(path=inside, project_root=project) == 'tests/run.jsonl.gz'
    assert recording_name(path=outside, project_root=project) == outside.as_posix()


def test_a_replay_that_runs_too_long_is_killed_and_fails(tmp_path, mocker, capsys):
    """A child still replaying after the timeout fails its recording INTERNAL_ERROR."""
    recording = tmp_path / 'run.jsonl.gz'
    recording.write_bytes(b'')
    mocker.patch.object(
        verify,
        'run_command',
        side_effect=TimeoutExpired(cmd=['game'], timeout=1.0),
    )

    status = verify.verify_recordings(recordings=[(recording, ['game'])], project_root=tmp_path)

    assert status == ExitCode.INTERNAL_ERROR
    assert (
        'FAIL run.jsonl.gz: INTERNAL_ERROR (70): still replaying after' in capsys.readouterr().out
    )


def test_the_game_flag_verifies_without_building_the_game(mocker, tmp_path, monkeypatch):
    """``--verify`` on a game runs while the engine is built: no pygame, no scene, its exit code.

    The children are stood in for: the replay of one recording is reported diverged.
    """
    from glitchygames.replay.tools.golden_traces import GoldenTraceEngine

    monkeypatch.chdir(tmp_path)
    recording = tmp_path / 'run.jsonl.gz'
    recording.write_bytes(b'')
    replayed = mocker.patch.object(
        verify,
        'run_command',
        return_value=CompletedProcess(
            args=[], returncode=ExitCode.REPLAY_DIVERGED, stdout='Replay diverged at frame 1\n'
        ),
    )
    mocker.patch.object(verify, 'running_game_command', return_value=['the-game'])
    pygame_started = mocker.spy(pygame, 'init')
    mocker.patch.object(
        sys,
        'argv',
        ['the-game', '--target-fps', '30', '--verify', str(recording), '--only', 'run'],
    )

    with pytest.raises(SystemExit) as exit_information:
        GoldenTraceEngine(game=GameThatIsNeverBuilt)

    assert exit_information.value.code == ExitCode.REPLAY_DIVERGED
    pygame_started.assert_not_called()
    (call,) = replayed.call_args_list
    assert call.kwargs['command'][:3] == ['the-game', '--replay-trace', str(recording)]
    # The game's other arguments reach its replays, as the command's after -- do; verify's own
    # (--verify, its paths, --only) do not
    assert call.kwargs['command'][-2:] == ['--target-fps', '30']
    assert '--verify' not in call.kwargs['command']
    assert '--only' not in call.kwargs['command']
    # Decision 17: verify never passes a seed, so every replay compares
    assert '--random-seed' not in call.kwargs['command']


def test_the_game_flag_finds_this_games_recordings_in_the_current_directory(
    mocker, tmp_path, monkeypatch, capsys
):
    """With no paths, the game's own: ``game_recordings`` of its identity, in the project here."""
    (tmp_path / 'pyproject.toml').write_text('', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    identity = GameIdentity(
        package='a_game', package_directory=None, console_script='a-game', distribution=None
    )
    mocker.patch.object(verify, 'game_identity', return_value=identity)
    found = mocker.patch.object(verify, 'game_recordings', return_value=[])

    status = verify.verify_on_the_game(
        options={'verify': [], 'only': None}, game=GameThatIsNeverBuilt
    )

    assert status == ExitCode.SUCCESS
    assert found.call_args.kwargs['identity'] == identity
    assert found.call_args.kwargs['project_root'] == tmp_path
    assert isinstance(found.call_args.kwargs['settings'], ProjectSettings)
    assert 'verify: no recordings found' in capsys.readouterr().out


def test_settings_that_cannot_be_read_refuse_the_run(tmp_path, monkeypatch, capsys, caplog):
    """A ``[tool.glitchygames]`` that can't be read is unusable input, on both front ends."""
    (tmp_path / 'pyproject.toml').write_text('[tool.glitchygames]\nno-such-setting = 1\n')
    monkeypatch.chdir(tmp_path)

    flag_status = verify.verify_on_the_game(
        options={'verify': [], 'only': None}, game=GameThatIsNeverBuilt
    )
    command_status = command.main(['verify', '--project-root', str(tmp_path)])

    assert flag_status == ExitCode.UNUSABLE_INPUT
    assert command_status == ExitCode.UNUSABLE_INPUT
    assert "unknown setting 'no-such-setting'" in caplog.text
    assert "unknown setting 'no-such-setting'" in capsys.readouterr().err


def test_recordings_named_on_the_command_that_cannot_be_replayed_fail_on_their_line(
    tmp_path, capsys
):
    """A path that is missing, not a recording, or names no game: a FAIL line each, and why."""
    missing = tmp_path / 'missing.jsonl.gz'
    not_a_recording = tmp_path / 'text.jsonl.gz'
    not_a_recording.write_text('not a recording')
    no_game = tmp_path / 'no-game.jsonl.gz'
    write_header_only_recording(path=no_game, header={})

    status = command.main([
        'verify',
        str(missing),
        str(not_a_recording),
        str(no_game),
        '--project-root',
        str(tmp_path),
    ])

    output = capsys.readouterr().out
    assert status == ExitCode.MISSING_INPUT
    assert 'FAIL missing.jsonl.gz: MISSING_INPUT (66): no such recording' in output
    assert 'FAIL text.jsonl.gz: UNUSABLE_INPUT (65): not a readable recording' in output
    assert 'FAIL no-game.jsonl.gz: OPTIONS_REFUSED (64): ' in output
    assert 'name the game with --game GAME' in output
    assert 'verify: 0 of 3 recordings passed' in output


def test_the_command_replays_named_recordings_with_the_game_named(tmp_path, mocker, capsys):
    """``verify PATH --game GAME``: that game replays each path, whatever its header says."""
    recording = tmp_path / 'run.jsonl.gz'
    write_header_only_recording(path=recording, header={})
    mocker.patch.object(
        verify,
        'resolve_named_game',
        return_value=GameLaunch(form='console-script', command=['the-game']),
    )
    replayed = mocker.patch.object(
        verify,
        'run_command',
        return_value=CompletedProcess(
            args=[], returncode=ExitCode.SUCCESS, stdout='Replay matched 3 frames\n'
        ),
    )

    status = command.main([
        'verify',
        str(recording),
        '--game',
        'the-game',
        '--project-root',
        str(tmp_path),
    ])

    captured = capsys.readouterr()
    assert status == ExitCode.SUCCESS
    assert replayed.call_args.kwargs['command'][:2] == ['the-game', '--replay-trace']
    assert replayed.call_args.kwargs['working_directory'] == tmp_path
    assert 'PASS run.jsonl.gz: Replay matched 3 frames' in captured.out
    assert (
        'glitchygames verify: replaying with the-game (an installed console script)' in captured.err
    )


def test_named_recordings_take_one_game_at_most(tmp_path, capsys):
    """With paths, ``--game`` names the one game that replays them: two are refused."""
    status = command.main([
        'verify',
        str(tmp_path / 'run.jsonl.gz'),
        '--game',
        'one',
        '--game',
        'two',
        '--project-root',
        str(tmp_path),
    ])

    assert status == ExitCode.OPTIONS_REFUSED
    assert 'one --game at most' in capsys.readouterr().err


def test_a_game_that_names_nothing_fails_and_the_others_still_run(tmp_path, mocker, capsys):
    """``--game`` naming no game: OPTIONS_REFUSED for it, after every other game verified."""
    launched = mocker.patch.object(
        traces,
        'launch_game',
        return_value=CompletedProcess(args=[], returncode=ExitCode.SUCCESS),
    )
    mocker.patch.object(
        verify,
        'resolve_named_game',
        side_effect=[
            verify.UnknownGameError('no such game'),
            GameLaunch(form='module', command=['python', '-m', 'a_module']),
        ],
    )

    status = command.main([
        'verify',
        '--game',
        'no_such_game_anywhere',
        '--game',
        'a_module',
        '--only',
        'gold',
        '--project-root',
        str(tmp_path),
    ])

    assert status == ExitCode.OPTIONS_REFUSED
    (call,) = launched.call_args_list
    assert call.kwargs['arguments'] == ['--verify', '--only', 'gold']
    assert call.kwargs['working_directory'] == tmp_path
    assert 'glitchygames verify: running a_module (a module)' in capsys.readouterr().err


def test_this_games_command_is_how_this_process_was_started(mocker):
    """The interpreter, then what started the program (a script, ``-m``, ``-c``), no arguments."""
    for original, arguments, expected in (
        (['python3', 'game.py', '--verify'], ['game.py', '--verify'], ['game.py']),
        (
            ['python3', '-X', 'dev', '-m', 'game', '--verify'],
            ['/x/game.py', '--verify'],
            [
                '-X',
                'dev',
                '-m',
                'game',
            ],
        ),
        (['python3', '-c', 'code', '--verify', 'a'], ['-c', '--verify', 'a'], ['-c', 'code']),
    ):
        mocker.patch.object(sys, 'orig_argv', original)
        mocker.patch.object(sys, 'argv', arguments)

        assert running_game_command() == [sys.executable, *expected]


def test_this_games_command_is_refused_when_its_arguments_were_changed(mocker):
    """Arguments this process changed can't tell where its program ends: refused, not guessed."""
    mocker.patch.object(sys, 'orig_argv', ['python3', 'game.py', '--verify'])
    mocker.patch.object(sys, 'argv', ['game.py', '--something-else'])

    with pytest.raises(RuntimeError, match='cannot tell how this game was started'):
        running_game_command()


def test_a_game_that_cannot_start_itself_again_is_refused(tmp_path, mocker, monkeypatch, caplog):
    """When this process can't tell how it was started, nothing is replayed: INTERNAL_ERROR."""
    monkeypatch.chdir(tmp_path)
    mocker.patch.object(
        verify,
        'running_game_command',
        side_effect=RuntimeError('cannot tell how this game was started'),
    )

    status = verify.verify_on_the_game(
        options={'verify': ['run.jsonl.gz'], 'only': None}, game=GameThatIsNeverBuilt
    )

    assert status == ExitCode.INTERNAL_ERROR
    assert 'cannot tell how this game was started' in caplog.text


def test_verify_is_one_tool_on_both_front_ends():
    """Listed once: its paths optional, ``--only`` its option, ``--game`` the command's own."""
    tool = registry.tool_named(name='verify')

    assert tool.runs_game
    assert tool.value_kind == 'paths'
    assert [option.flag for option in tool.options] == ['--only', '--random-seed']
    assert [argument.flag for argument in tool.command_arguments] == ['--game']
    assert tool.command_arguments[0].kind == 'games'


def test_only_keeping_none_of_the_named_recordings_is_no_failure(tmp_path, capsys):
    """``--only`` matching none of the PATHs: nothing to verify, said, and SUCCESS."""
    status = command.main([
        'verify',
        str(tmp_path / 'serve.jsonl.gz'),
        '--only',
        'lob',
        '--project-root',
        str(tmp_path),
    ])

    assert status == ExitCode.SUCCESS
    assert (
        "verify: no recordings found (1 given, or none of them contains 'lob' (--only))"
        in capsys.readouterr().out
    )


def test_named_recordings_with_a_game_that_names_nothing_are_refused(tmp_path, capsys):
    """``verify PATH --game GAME`` naming no game: OPTIONS_REFUSED, every form named."""
    status = command.main([
        'verify',
        str(tmp_path / 'serve.jsonl.gz'),
        '--game',
        'no_such_game_anywhere',
        '--project-root',
        str(tmp_path),
    ])

    assert status == ExitCode.OPTIONS_REFUSED
    assert "'no_such_game_anywhere' is not a game" in capsys.readouterr().err


def test_a_game_argument_after_dash_dash_reaches_the_children_on_the_command(tmp_path, mocker):
    """``glitchygames verify ... -- ARGS``: ARGS reach each replay, or each game's ``--verify``.

    With PATHs the command replays each itself; without, each game verifies its own and passes
    its arguments on to its replays (``test_the_game_flag_verifies_without_building_the_game``).
    """
    (tmp_path / 'pyproject.toml').write_text('', encoding='utf-8')
    recording = tmp_path / 'run.jsonl.gz'
    write_header_only_recording(path=recording, header={})
    mocker.patch.object(
        verify,
        'resolve_named_game',
        return_value=GameLaunch(form='console-script', command=['the-game']),
    )
    replayed = mocker.patch.object(
        verify,
        'run_command',
        return_value=CompletedProcess(args=[], returncode=ExitCode.SUCCESS, stdout=''),
    )
    launched = mocker.patch.object(
        traces,
        'launch_game',
        return_value=CompletedProcess(args=[], returncode=ExitCode.SUCCESS),
    )
    game_arguments = ['--', '--target-fps', '30']

    by_path = command.main([
        'verify',
        str(recording),
        '--game',
        'the-game',
        '--project-root',
        str(tmp_path),
        *game_arguments,
    ])
    per_game = command.main([
        'verify',
        '--game',
        'the-game',
        '--project-root',
        str(tmp_path),
        *game_arguments,
    ])

    assert by_path == ExitCode.SUCCESS
    assert per_game == ExitCode.SUCCESS
    assert replayed.call_args.kwargs['command'][-2:] == ['--target-fps', '30']
    assert launched.call_args.kwargs['arguments'] == ['--verify', '--target-fps', '30']


def test_both_front_ends_find_the_project_from_a_subdirectory(
    stand_in_game, stand_in_project, capfd, monkeypatch
):
    """Run from inside the project, the nearest directory above with a pyproject.toml is it.

    The game flag and the command (no ``--project-root``) both find the project's goldens.
    """
    inside = stand_in_project / 'tests' / 'fixtures'
    flag_status, flag_output = run_game_flag(
        game=stand_in_game, arguments=['--verify'], working_directory=inside
    )
    monkeypatch.chdir(inside)
    command_status = command.main(['verify'])
    captured = capfd.readouterr()

    assert flag_status == ExitCode.REPLAY_DIVERGED, flag_output
    assert_one_line_each(
        output=flag_output, game=stand_in_game, names=('good.jsonl.gz', 'tampered.jsonl.gz')
    )
    assert command_status == ExitCode.REPLAY_DIVERGED, captured.out + captured.err
    assert_one_line_each(
        output=captured.out, game=stand_in_game, names=('good.jsonl.gz', 'tampered.jsonl.gz')
    )


def test_no_project_above_the_current_directory_is_said(tmp_path, mocker, monkeypatch, capsys):
    """No pyproject.toml here or above: said on both front ends, and the current directory used."""
    mocker.patch.object(verify, 'find_project_root', return_value=None)
    monkeypatch.chdir(tmp_path)
    identity = GameIdentity(
        package='a_game', package_directory=None, console_script='a-game', distribution=None
    )
    mocker.patch.object(verify, 'game_identity', return_value=identity)
    found = mocker.patch.object(verify, 'game_recordings', return_value=[])

    flag_status = verify.verify_on_the_game(
        options={'verify': [], 'only': None}, game=GameThatIsNeverBuilt
    )
    command_status = command.main(['verify'])

    output = capsys.readouterr().out
    assert flag_status == ExitCode.SUCCESS
    assert command_status == ExitCode.SUCCESS
    assert found.call_args.kwargs['project_root'] == tmp_path
    assert output.count(f'verify: no pyproject.toml in {tmp_path}: using the default settings') == 2


def test_no_project_is_not_said_when_recordings_are_named(tmp_path, mocker, monkeypatch, capsys):
    """With PATHs no settings are read, so a missing pyproject.toml is not mentioned."""
    mocker.patch.object(verify, 'find_project_root', return_value=None)
    monkeypatch.chdir(tmp_path)
    mocker.patch.object(verify, 'running_game_command', return_value=['the-game'])
    mocker.patch.object(
        verify,
        'run_command',
        return_value=CompletedProcess(args=[], returncode=ExitCode.SUCCESS, stdout=''),
    )
    mocker.patch.object(
        verify,
        'resolve_named_game',
        return_value=GameLaunch(form='console-script', command=['the-game']),
    )
    mocker.patch.object(sys, 'argv', ['the-game', '--verify', 'run.jsonl.gz'])

    flag_status = verify.verify_on_the_game(
        options={'verify': ['run.jsonl.gz'], 'only': None}, game=GameThatIsNeverBuilt
    )
    command_status = command.main(['verify', 'run.jsonl.gz', '--game', 'the-game'])

    output = capsys.readouterr().out
    assert flag_status == ExitCode.SUCCESS
    assert command_status == ExitCode.SUCCESS
    assert 'pyproject.toml' not in output


# What a refusal of a seed says, on both front ends
SEED_REFUSAL = 'verify always replays each recording under its recorded seed'


def test_verify_refuses_a_random_seed_on_both_front_ends_so_it_always_compares(
    stand_in_game, stand_in_project, capfd
):
    """A seed would make each replay a reseeded one, which compares nothing (decision 17).

    So ``--random-seed`` is refused, OPTIONS_REFUSED before any replay runs, whether given to the
    tool or among the game arguments passed on to the replays; without it the golden tampered at
    frame 10 fails.
    """
    tampered = stand_in_project.joinpath(
        *GOLDEN_DIRECTORY_PARTS, stand_in_game.console_script, 'tampered.jsonl.gz'
    )
    flag_status, flag_output = run_game_flag(
        game=stand_in_game,
        arguments=['--random-seed', '7', '--verify', str(tampered)],
        working_directory=stand_in_project,
    )
    refused_on_the_command = [
        command.main(arguments)
        for arguments in (
            ['verify', str(tampered), '--random-seed', '7'],
            ['verify', str(tampered), '--', '--random-seed', '7'],
            ['verify', '--game', stand_in_game.console_script, '--', '--random-seed=7'],
        )
    ]
    refused = capfd.readouterr()
    compared_status = command.main(['verify', str(tampered)])
    compared = capfd.readouterr()

    assert flag_status == ExitCode.OPTIONS_REFUSED, flag_output
    assert SEED_REFUSAL in flag_output
    assert '--replay-trace PATH --random-seed N' in flag_output
    assert refused_on_the_command == [ExitCode.OPTIONS_REFUSED] * 3
    assert refused.err.count(SEED_REFUSAL) == 3
    for output in (flag_output, refused.out, refused.err):
        assert 'PASS ' not in output
        assert 'FAIL ' not in output
        assert 'running ' not in output
    assert compared_status == ExitCode.REPLAY_DIVERGED, compared.out + compared.err
    assert f'REPLAY_DIVERGED (1): {DIVERGED_AT_THE_TAMPERED_FRAME}' in compared.out


@pytest.mark.parametrize(
    ('arguments', 'expected'),
    [
        (['--random-seed', '7'], True),
        (['--random-seed=7'], True),
        # A prefix a game's parser takes for it (argparse's abbreviations)
        (['--target-fps', '30', '--random-s', '7'], True),
        # Asked for with no value: still refused, not left to the game
        (['--random-seed'], True),
        (['--target-fps', '30'], False),
        ([], False),
    ],
)
def test_a_seed_is_found_among_game_arguments_as_a_game_would_read_it(arguments, expected):
    """``seed_given`` reads the arguments as the game's own parser would."""
    assert verify.seed_given(arguments=arguments) is expected


def test_the_game_flag_refuses_a_seed_before_looking_for_recordings(mocker, caplog):
    """On the game a seed is refused at once: nothing is looked for or replayed."""
    found = mocker.patch.object(verify, 'game_recordings')
    replayed = mocker.patch.object(verify, 'run_command')

    status = verify.verify_on_the_game(
        options={'verify': [], 'only': None, 'random_seed': 7}, game=GameThatIsNeverBuilt
    )

    assert status == ExitCode.OPTIONS_REFUSED
    assert SEED_REFUSAL in caplog.text
    found.assert_not_called()
    replayed.assert_not_called()


def test_a_game_stopped_at_its_timeout_is_named_on_every_platform(tmp_path, capsys, mocker):
    """The stop at ``game-timeout-seconds`` fails the run and names the game, Windows included.

    The real never-ending game (the test below) checks the child is gone with signal 0, which
    is POSIX; here the launch's timeout is injected, so every platform checks the outcome.
    """
    script = write_never_ending_game_project(directory=tmp_path / 'project')
    mocker.patch.object(
        traces,
        'launch_game',
        side_effect=TimeoutExpired(cmd=str(script), timeout=NEVER_ENDING_GAME_TIMEOUT_SECONDS),
    )

    status = command.main([
        'verify',
        '--game',
        str(script),
        '--project-root',
        str(script.parent),
    ])

    assert status == ExitCode.INTERNAL_ERROR
    assert (
        f'glitchygames verify: {script} was stopped: still running after '
        f'{NEVER_ENDING_GAME_TIMEOUT_SECONDS:g} seconds ([tool.glitchygames] game-timeout-seconds)'
    ) in capsys.readouterr().err


@pytest.mark.skipif(sys.platform == 'win32', reason='signal 0 to a process id is POSIX')
def test_a_game_that_never_ends_is_stopped_at_the_projects_timeout_and_fails(tmp_path, capsys):
    """A game still running after ``game-timeout-seconds`` is stopped, reaped and fails, named.

    The never-ending game stands for an editor or a server among a project's console scripts,
    started with ``--verify``: never a hang with no word of which game it waits on.
    """
    script = write_never_ending_game_project(directory=tmp_path / 'project')

    status = command.main([
        'verify',
        '--game',
        str(script),
        '--project-root',
        str(script.parent),
    ])

    assert status == ExitCode.INTERNAL_ERROR
    assert (
        f'glitchygames verify: {script} was stopped: still running after '
        f'{NEVER_ENDING_GAME_TIMEOUT_SECONDS:g} seconds ([tool.glitchygames] game-timeout-seconds)'
    ) in capsys.readouterr().err
    child_pid = int((script.parent / 'never-ending.pid').read_text(encoding='utf-8'))
    try:
        os.kill(child_pid, 0)
    except ProcessLookupError:
        child_left_running = False
    else:
        child_left_running = True
        os.kill(child_pid, signal.SIGKILL)
    assert not child_left_running
