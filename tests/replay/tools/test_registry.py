"""The tool table (glitchygames/replay/tools/registry.py) and both front ends built from it.

Every tool is ``--<name>`` on a game's command line and ``glitchygames <name>``; the sync tests
walk ``TOOLS``, so they hold as later tasks add tools. The tools that run a game are run end to
end on a stand-in game (tests/stand_in_games.py): through the command, which starts it as a child.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from glitchygames import __main__ as glitchygames_main
from glitchygames.argument_types import non_negative_int, non_negative_percent
from glitchygames.engine import GameEngine
from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, run_command
from glitchygames.replay.tools import command, registry
from glitchygames.replay.tools.children import entry_point_command, game_entry_point
from glitchygames.replay.tools.registry import (
    TOOLS,
    Tool,
    ToolOption,
    add_game_flags,
    build_command_parser,
    run_game_flag_tool,
    tool_named,
)
from glitchygames.scenes import Scene
from tests.stand_in_games import (
    STAND_IN_GAME_FRAMES,
    STAND_IN_GAME_RESOLUTION,
    STAND_IN_GAME_TARGET_FPS,
    StandInGame,
    record_stand_in_game,
    stand_in_game_source,
    use_stand_in_game,
    write_header_only_recording,
    write_stand_in_game,
)
from tests.workspace_expectations import EXPECTED_ALL_CONSOLE_SCRIPTS

if TYPE_CHECKING:
    from glitchygames.replay.tools.registry import ToolOptionKind

# A child that only prints its help, or replays a stand-in's few frames, ends in seconds
CHILD_TIMEOUT_SECONDS = 120.0
# The game arguments a recording child of the stand-in gets after --, as record_stand_in_game's
STAND_IN_RECORDING_ARGUMENTS = (
    '--headless',
    '--log-level',
    'error',
    '--resolution',
    STAND_IN_GAME_RESOLUTION,
    '--target-fps',
    STAND_IN_GAME_TARGET_FPS,
)
# pygame's banner variable, which the command sets before pygame is imported
PYGAME_BANNER_VARIABLE = 'PYGAME_HIDE_SUPPORT_PROMPT'
# The three forms GAME takes, written out (children.GAME_FORMS must keep naming each)
THE_THREE_GAME_FORMS = (
    'a script path (contains / or ends in .py)',
    'an entry point MODULE:CALLABLE',
    'an installed console script or an importable module',
)
# The command's console script ([project.scripts])
COMMAND_CONSOLE_SCRIPT = 'glitchygames'
# The command has two options no game flag has, and the sync test skips each by name:
# - --game, a tool's own command argument (Tool.command_arguments), which names the game to run
#   (replay-trace's game when its recording's no longer imports; verify's, measure's and
#   unmeasured's games, repeatable). A
#   game needs no --game: it is the game. COMMAND_ONLY_FLAGS holds it, and only it;
# - --project-root (registry.PROJECT_ROOT_FLAG), the command's own flag on every subcommand, which
#   no tool lists (a game finds its project from its current directory).
# Every other option is the same on both front ends
COMMAND_ONLY_FLAGS = frozenset({'--game'})


class FlagToolScene(Scene):
    """A game for the parser tests: built only as a parser, never run."""

    NAME = 'FlagToolScene'
    VERSION = '1.0'


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


def game_parser() -> argparse.ArgumentParser:
    """Return a game's command line as the engine builds it (``GameEngine.args``).

    Returns:
        The parser.

    """
    return GameEngine.args(argparse.ArgumentParser(prog=FlagToolScene.NAME))


def subcommand_parsers(*, parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    """Return the command's subcommand parsers, by name.

    Args:
        parser: The command's parser.

    Returns:
        Each subcommand's parser.

    """
    (subparsers,) = [
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    ]
    return dict(subparsers.choices)


def action_for(*, parser: argparse.ArgumentParser, flag: str) -> argparse.Action:
    """Return the parser's action for a flag.

    Returns:
        The action.

    """
    (action,) = [action for action in parser._actions if flag in action.option_strings]
    return action


def described(*, action: argparse.Action) -> dict[str, Any]:
    """Return what a front end makes of an option, apart from ``required``.

    Returns:
        The action's settings.

    """
    return {
        'option_strings': action.option_strings,
        'dest': action.dest,
        'default': action.default,
        'type': action.type,
        'choices': action.choices,
        'nargs': action.nargs,
        'metavar': action.metavar,
        'help': action.help,
        'action': type(action),
    }


def run_child(*, command: list[str], environment: dict[str, str] | None = None) -> Any:
    """Run a child to its end, its output captured.

    Returns:
        The finished child.

    """
    return run_command(
        command=command,
        environment=os.environ if environment is None else environment,
        timeout_seconds=CHILD_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
    )


def test_every_tool_is_a_game_flag_and_a_command():
    """The tool flags on a game's parser, the subcommands and TOOLS name the same tools."""
    subcommands = set(subcommand_parsers(parser=build_command_parser()))
    game_flags = {
        flag
        for action in game_parser()._actions
        for flag in action.option_strings
        if flag.removeprefix('--') in subcommands
    }

    assert subcommands == {tool.name for tool in TOOLS}
    assert game_flags == {f'--{name}' for name in subcommands}
    for tool in TOOLS:
        flag_action = action_for(parser=game_parser(), flag=tool.flag)
        assert flag_action.dest == tool.destination
        assert flag_action.help == tool.help


def test_each_tools_options_match_on_both_front_ends():
    """Per tool: every option's flag, kind (action, type, choices), default and help agree.

    ``required`` is the command's own: a game flag is never required by argparse (the game runs
    without the tool), so ``run_game_flag_tool`` refuses a tool given without it.
    """
    game = game_parser()
    subcommands = subcommand_parsers(parser=build_command_parser())
    every_command_only_flag: set[str] = set()
    for tool in TOOLS:
        subcommand = subcommands[tool.name]
        # Each option's first flag (a switch's second is its --no- form)
        tool_flags = {
            action.option_strings[0]
            for action in subcommand._actions
            if action.option_strings
            and action.option_strings[0] not in {'-h', registry.PROJECT_ROOT_FLAG}
        }
        command_only = {
            argument.flag for argument in tool.command_arguments if not argument.positional
        }
        # The documented exemption, and only it (COMMAND_ONLY_FLAGS)
        assert command_only <= COMMAND_ONLY_FLAGS, tool.name
        every_command_only_flag |= command_only
        assert tool_flags - command_only == {option.flag for option in tool.options}, tool.name
        for option in tool.options:
            on_the_game = action_for(parser=game, flag=option.flag)
            on_the_command = action_for(parser=subcommand, flag=option.flag)
            assert described(action=on_the_game) == described(action=on_the_command), option.flag
            assert on_the_command.required is option.required
            assert on_the_game.required is False
        # The command's own arguments (--game) are not game flags
        assert not command_only & {
            flag for action in game._actions for flag in action.option_strings
        }
    # The exemption names nothing no tool needs
    assert every_command_only_flag == COMMAND_ONLY_FLAGS


def test_the_existing_trace_flags_are_unchanged():
    """--record-trace, --replay-trace and --rebaseline parse to the OPTIONS they always did.

    The values are those GameEngine.args gave before the table (written out by hand).
    """
    parser = game_parser()
    trace_keys = (
        'record_trace',
        'replay_trace',
        'replay_fps',
        'audit',
        'compare_processing',
        'max_processing_slowdown',
        'replay_pause_at_frame',
        'replay_restart_handoff',
        'replay_viewer_state',
        'rebaseline',
        'replay_digest',
        'headless',
        'random_seed',
    )
    nothing_given = dict.fromkeys(trace_keys)
    nothing_given.update(audit=False, headless=False)

    recording = vars(parser.parse_args(['--record-trace', 'run.jsonl.gz']))
    rebaselining = vars(
        parser.parse_args(['--replay-trace', 'old.jsonl.gz', '--rebaseline', 'new.jsonl.gz'])
    )

    assert {key: recording[key] for key in trace_keys} == {
        **nothing_given,
        'record_trace': 'run.jsonl.gz',
    }
    assert {key: rebaselining[key] for key in trace_keys} == {
        **nothing_given,
        'replay_trace': 'old.jsonl.gz',
        'rebaseline': 'new.jsonl.gz',
    }
    for flag, metavar in (
        ('--record-trace', 'PATH'),
        ('--replay-trace', 'PATH'),
        ('--rebaseline', 'NEW'),
    ):
        assert action_for(parser=parser, flag=flag).metavar == metavar
    assert action_for(parser=parser, flag='--record-trace').help == (
        'record the session (sprites, frame times, input events, random seed) to a '
        'gzip JSON Lines trace for inspection and later replay (default: off)'
    )


# Each moved option as GameEngine.args defined it before the table, written out by hand:
# (flag, help, choices, type, default, action class)
MOVED_OPTIONS_AS_THEY_WERE = (
    (
        '--replay-fps',
        (
            'with --replay-trace: post FPS events from the recorded frame times (recorded, '
            "the default: exact, and compared with the recording) or from this machine's "
            'measured frame times (real: what this machine achieves; FPS events are then '
            'not compared, and sprites that draw the FPS value may diverge)'
        ),
        ('recorded', 'real'),
        None,
        None,
        argparse._StoreAction,
    ),
    (
        '--audit',
        (
            'with --replay-trace: instead of replaying, replay the recording twice in fresh '
            'headless processes with different hash seeds and compare every frame with the '
            'recording and between the runs; exits 0 when both match, 3 otherwise, 70 if '
            'a run could not finish'
        ),
        None,
        None,
        False,
        argparse.BooleanOptionalAction,
    ),
    (
        '--compare-processing',
        (
            "with --replay-trace --headless: measure each frame's processing time (its "
            'work, without presenting or pacing) and report how it compares with the '
            "recording's (only meaningful on the machine that recorded)"
        ),
        None,
        None,
        None,
        argparse._StoreTrueAction,
    ),
    (
        '--max-processing-slowdown',
        (
            'with --replay-trace --headless (implies --compare-processing): a replay that '
            "matched but took more than PERCENT longer than the recording's processing time "
            'exits 8; a recording without processing times exits 65'
        ),
        None,
        non_negative_percent,
        None,
        argparse._StoreAction,
    ),
    (
        '--replay-pause-at-frame',
        (
            'with --replay-trace, watched: skip the start screen, run frames 0 to N - 1 '
            'without showing them, then pause with frame N next (what step back restarts '
            'with; ignored with --headless)'
        ),
        None,
        non_negative_int,
        None,
        argparse._StoreAction,
    ),
    (
        '--rebaseline',
        (
            'with --replay-trace OLD and --headless: replay OLD on the current code without '
            "stopping at divergences, write the run's recording (OLD's inputs, the current "
            'sprites) to NEW, print a summary of the frames and sprites that changed and '
            'exit 0'
        ),
        None,
        None,
        None,
        argparse._StoreAction,
    ),
    (
        '--replay-digest',
        (
            'with --replay-trace: write a SHA-256 of every replayed frame, then the '
            'divergence, to PATH as JSON lines (used by --audit)'
        ),
        None,
        None,
        None,
        argparse._StoreAction,
    ),
    (
        '--headless',
        (
            "run on SDL's dummy video and audio drivers: no window, no sound. With "
            '--replay-trace the replay also runs unpaced and prints its report to stdout '
            '(exit 0 when it matches, 1 when it diverges, 65 for a truncated recording)'
        ),
        None,
        None,
        False,
        argparse._StoreTrueAction,
    ),
    (
        '--random-seed',
        (
            # The user's seed rule (2026-10-26): tests/replay/tools/test_random_seed.py
            'master seed for every engine random stream. Not given, a run or recording rolls a '
            "random 64-bit seed (logged in the recording) and a replay uses the recording's. "
            "Given, a run or recording uses it, and a replay given the recording's own compares "
            "as always; a replay given another plays the recording's inputs out under it "
            'without comparing or writing anything (headless, it prints what differed and exits '
            '0); --replay-trace OLD --rebaseline NEW --random-seed N records them under it in '
            'NEW; --audit under another seed is refused, and so is any seed given to --verify '
            '(it always compares) or --measure (it rebaselines each recording under its '
            'recorded seed)'
        ),
        None,
        int,
        None,
        argparse._StoreAction,
    ),
)


@pytest.mark.parametrize(
    'as_it_was', MOVED_OPTIONS_AS_THEY_WERE, ids=[flag for flag, *_ in MOVED_OPTIONS_AS_THEY_WERE]
)
def test_each_moved_option_is_unchanged_on_the_game(as_it_was):
    """Every option moved into the table keeps its help, choices, type, default and action."""
    flag, help_text, choices, value_type, default, action_class = as_it_was
    action = action_for(parser=game_parser(), flag=flag)

    assert action.help == help_text
    assert (tuple(action.choices) if action.choices is not None else None) == choices
    assert action.type is value_type
    assert action.default == default
    assert type(action) is action_class
    assert action.dest == flag.removeprefix('--').replace('-', '_')


def test_an_option_listed_under_several_tools_is_one_game_flag_and_each_tools_option():
    """A shared option (--headless: every tool that runs the game) is one flag on the game.

    Each tool that lists it has it as a subcommand option; every tool that records or replays
    also shares --random-seed, and record-golden-trace and record-session share
    --input-script and --frame-count.
    """
    game = game_parser()
    subcommands = subcommand_parsers(parser=build_command_parser())
    tools_by_flag: dict[str, list[str]] = {}
    for tool in TOOLS:
        for option in tool.options:
            tools_by_flag.setdefault(option.flag, []).append(tool.name)
    shared = {flag: names for flag, names in tools_by_flag.items() if len(names) > 1}

    every_game_runner = ['record-trace', 'replay-trace', 'record-golden-trace', 'record-session']
    assert shared['--headless'] == every_game_runner
    # verify and measure list it only to refuse it (they always replay under the recorded seed:
    # test_verify.py, test_measure.py)
    assert shared['--random-seed'] == [*every_game_runner, 'verify', 'measure']
    assert shared['--input-script'] == ['record-golden-trace', 'record-session']
    assert shared['--frame-count'] == ['record-golden-trace', 'record-session']
    for flag, names in shared.items():
        on_the_game = [action for action in game._actions if flag in action.option_strings]
        assert len(on_the_game) == 1, flag
        for name in names:
            assert described(action=action_for(parser=subcommands[name], flag=flag)) == (
                described(action=on_the_game[0])
            )
    record_trace_flags = {option.flag for option in tool_named(name='record-trace').options}
    assert record_trace_flags == {'--random-seed', '--headless'}


def test_glitchygames_help_lists_every_tool(capsys):
    """``glitchygames --help`` names every tool and every option (--rebaseline, --audit too)."""
    with pytest.raises(SystemExit) as exit_information:
        command.main(['--help'])

    output = capsys.readouterr().out
    assert exit_information.value.code == ExitCode.SUCCESS
    for tool in TOOLS:
        assert tool.name in output
        for option in tool.options:
            assert option.flag in output
    replay_line = output[output.index('  replay-trace PATH') :]
    assert '[--rebaseline]' in replay_line
    assert '[--audit]' in replay_line


def test_a_game_help_lists_every_tool(stand_in_game):
    """A game's own --help (the stand-in's, through its console script) lists every tool."""
    entry_point = game_entry_point(console_script=stand_in_game.console_script)

    finished = run_child(command=[*entry_point_command(entry_point=entry_point), '--help'])

    assert finished.returncode == ExitCode.SUCCESS, finished.stdout
    for tool in TOOLS:
        assert tool.flag in finished.stdout
        for option in tool.options:
            assert option.flag in finished.stdout


def test_importing_the_replay_tools_imports_no_pytest():
    """The tools and the command import without pytest (it is in the dev extra only)."""
    check = (
        'import sys; '
        'import glitchygames.__main__, glitchygames.replay.tools.command, '
        'glitchygames.replay.tools.children, glitchygames.replay.tools.registry, '
        'glitchygames.replay.tools.traces; '
        "print(sorted(name for name in sys.modules if name.partition('.')[0] == 'pytest'))"
    )

    finished = run_child(command=[sys.executable, '-c', check])

    assert finished.returncode == ExitCode.SUCCESS, finished.stdout
    assert finished.stdout.splitlines()[-1] == '[]'


def test_the_command_prints_no_pygame_banner():
    """The console script's --help starts with the usage: pygame's banner is hidden first.

    The child loads the registered console script as its installed script does, with the
    banner variable unset, so the command itself has to set it.
    """
    environment = {
        name: value for name, value in os.environ.items() if name != PYGAME_BANNER_VARIABLE
    }
    entry_point = game_entry_point(console_script=COMMAND_CONSOLE_SCRIPT)

    finished = run_child(
        command=[*entry_point_command(entry_point=entry_point), '--help'],
        environment=environment,
    )

    assert finished.returncode == ExitCode.SUCCESS, finished.stdout
    assert finished.stdout.startswith('usage: glitchygames '), finished.stdout


def test_python_m_glitchygames_is_the_command():
    """``python -m glitchygames`` is the console script: the same help, no banner."""
    environment = {
        name: value for name, value in os.environ.items() if name != PYGAME_BANNER_VARIABLE
    }
    entry_point = game_entry_point(console_script=COMMAND_CONSOLE_SCRIPT)

    as_module = run_child(
        command=[sys.executable, '-m', 'glitchygames', '--help'], environment=environment
    )
    as_script = run_child(
        command=[*entry_point_command(entry_point=entry_point), '--help'],
        environment=environment,
    )

    assert entry_point.value == 'glitchygames.__main__:main'
    assert as_module.returncode == ExitCode.SUCCESS
    assert as_module.stdout == as_script.stdout


def test_the_main_module_runs_the_command(mocker, monkeypatch, capsys):
    """glitchygames/__main__.py hides the banner, then runs the command with sys.argv."""
    monkeypatch.delenv(PYGAME_BANNER_VARIABLE, raising=False)
    mocker.patch.object(sys, 'argv', ['glitchygames', '--help'])

    with pytest.raises(SystemExit) as exit_information:
        glitchygames_main.main()

    assert exit_information.value.code == ExitCode.SUCCESS
    assert os.environ[PYGAME_BANNER_VARIABLE] == '1'
    assert capsys.readouterr().out.startswith('usage: glitchygames ')


@pytest.mark.parametrize('console_script', sorted(EXPECTED_ALL_CONSOLE_SCRIPTS))
def test_no_tool_option_clashes_with_any_of_our_games_arguments(console_script):
    """Every member's game parser builds with the tool flags added: its --help lists them.

    A game argument with a tool's flag would make argparse refuse to build the parser, so the
    game's --help would fail. Run as the installed console script runs it, in a child.
    """
    entry_point = game_entry_point(console_script=console_script)

    finished = run_child(command=[*entry_point_command(entry_point=entry_point), '--help'])

    assert finished.returncode == ExitCode.SUCCESS, finished.stdout
    for tool in TOOLS:
        assert tool.flag in finished.stdout, console_script


def test_glitchygames_record_trace_runs_the_game_as_a_child(stand_in_game, tmp_path, capfd):
    """``glitchygames record-trace GAME PATH --random-seed N --headless -- ...``: in a child.

    The recording's header names the stand-in's scene; the command's --random-seed and
    --headless (record-trace's options) and the arguments after -- all reach the game.
    """
    recording = tmp_path / 'recorded.jsonl.gz'

    exit_status = command.main([
        'record-trace',
        stand_in_game.console_script,
        str(recording),
        '--random-seed',
        '5',
        '--headless',
        '--',
        *(argument for argument in STAND_IN_RECORDING_ARGUMENTS if argument != '--headless'),
    ])

    errors = capfd.readouterr().err
    assert exit_status == ExitCode.SUCCESS, errors
    assert (
        f'glitchygames record-trace: running {stand_in_game.console_script} '
        '(an installed console script)'
    ) in errors
    with gzip.open(recording, 'rt', encoding='utf-8') as recorded:
        header = json.loads(recorded.readline())
    assert header['game'] == stand_in_game.logical_name
    assert header['options']['random_seed'] == 5
    assert header['options']['headless'] is True
    assert header['options']['resolution'] == STAND_IN_GAME_RESOLUTION


def test_glitchygames_replay_trace_finds_the_game_from_the_recording(
    stand_in_game, tmp_path, capfd
):
    """``glitchygames replay-trace PATH``: the console script starting the recorded game replays.

    The stand-in's recording names its scene, in package ``stand_in_rally``, whose console
    script is ``stand-in-rally``. The replay matches every frame.
    """
    recording = record_stand_in_game(game=stand_in_game, path=tmp_path / 'rally.jsonl.gz')

    exit_status = command.main(['replay-trace', str(recording), '--headless'])

    captured = capfd.readouterr()
    assert exit_status == ExitCode.SUCCESS, captured.out + captured.err
    assert (
        f'glitchygames replay-trace: running {stand_in_game.console_script} '
        '(an installed console script)'
    ) in captured.err
    assert f'Replay matched {STAND_IN_GAME_FRAMES}' in captured.out


def write_script_game(*, directory: Path) -> Path:
    """Write the stand-in game as a script (``python game.py``): its module is ``__main__``.

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


def test_replay_trace_asks_for_game_when_the_recorded_module_is_gone(tmp_path, capfd):
    """A game recorded as a script names ``__main__``: the command asks for --game GAME.

    Recorded through the command's script form, then replayed: first without --game (refused,
    naming --game and every form GAME takes), then with the script as --game (it matches).
    """
    script = write_script_game(directory=tmp_path)
    recording = tmp_path / 'script.jsonl.gz'
    recorded = command.main([
        'record-trace',
        str(script),
        str(recording),
        '--',
        *STAND_IN_RECORDING_ARGUMENTS,
    ])
    assert recorded == ExitCode.SUCCESS, capfd.readouterr().err
    capfd.readouterr()

    asked = command.main(['replay-trace', str(recording), '--headless'])
    asking = capfd.readouterr().err
    replayed = command.main(['replay-trace', str(recording), '--headless', '--game', str(script)])
    replaying = capfd.readouterr()

    assert asked == ExitCode.OPTIONS_REFUSED
    assert "its game's module '__main__' no longer imports" in asking
    assert 'name the game with --game GAME' in asking
    for form in THE_THREE_GAME_FORMS:
        assert form in asking
    assert replayed == ExitCode.SUCCESS, replaying.out + replaying.err
    assert f'running {script} (a script)' in replaying.err
    assert f'Replay matched {STAND_IN_GAME_FRAMES}' in replaying.out


@pytest.mark.parametrize(
    ('header', 'expected_line'),
    [
        ({}, "no 'game' in its header (a recording made before logical names), so it names"),
        (
            {'game': 'glitchygames.scenes:Scene'},
            'no one console script starts it (none of',
        ),
    ],
)
def test_replay_trace_asks_for_game_when_no_console_script_is_found(
    tmp_path, capfd, header, expected_line
):
    """A header naming no game, or a game no console script starts, needs --game too.

    ``glitchygames.scenes`` imports, but none of the installed console scripts starts it.
    """
    recording = tmp_path / 'header-only.jsonl.gz'
    write_header_only_recording(path=recording, header=header)

    exit_status = command.main(['replay-trace', str(recording)])

    errors = capfd.readouterr().err
    assert exit_status == ExitCode.OPTIONS_REFUSED
    assert expected_line in errors
    assert 'name the game with --game GAME' in errors


def test_replay_trace_of_a_missing_recording_is_missing_input(tmp_path, capfd):
    """No recording at PATH: MISSING_INPUT, as the engine's own replay exits."""
    exit_status = command.main(['replay-trace', str(tmp_path / 'absent.jsonl.gz')])

    assert exit_status == ExitCode.MISSING_INPUT
    assert 'absent.jsonl.gz: no such recording' in capfd.readouterr().err


def test_replay_trace_of_a_file_that_is_no_recording_is_unusable_input(tmp_path, capfd):
    """A file that is not a recording: UNUSABLE_INPUT."""
    not_a_recording = tmp_path / 'notes.jsonl.gz'
    not_a_recording.write_text('not gzip', encoding='utf-8')

    exit_status = command.main(['replay-trace', str(not_a_recording)])

    assert exit_status == ExitCode.UNUSABLE_INPUT
    assert 'notes.jsonl.gz: not a readable recording' in capfd.readouterr().err


@pytest.mark.parametrize(
    'arguments',
    [
        ['record-trace', 'no_such_game_anywhere', 'run.jsonl.gz'],
        ['replay-trace', 'run.jsonl.gz', '--game', 'no_such_game_anywhere'],
    ],
)
def test_a_game_that_names_nothing_is_refused(capfd, arguments):
    """GAME or --game naming no game: OPTIONS_REFUSED, every form named, no child started."""
    exit_status = command.main(arguments)

    errors = capfd.readouterr().err
    assert exit_status == ExitCode.OPTIONS_REFUSED
    assert "'no_such_game_anywhere' is not a game" in errors
    for form in THE_THREE_GAME_FORMS:
        assert form in errors


def test_replay_trace_options_reach_the_game_as_its_flags(stand_in_game, tmp_path):
    """Each option given to the command is passed on as the game's flag, paths made absolute.

    Options left at their defaults are not passed; ``--project-root`` is the child's directory.
    """
    arguments = build_command_parser().parse_args([
        'replay-trace',
        'old.jsonl.gz',
        '--rebaseline',
        'new.jsonl.gz',
        '--replay-fps',
        'real',
        '--max-processing-slowdown',
        '5',
        '--audit',
        '--headless',
        '--project-root',
        str(tmp_path),
    ])

    child_arguments = tool_named(name='replay-trace').child_arguments(arguments=arguments)

    assert child_arguments == [
        '--replay-trace',
        str(Path('old.jsonl.gz').absolute()),
        '--replay-fps',
        'real',
        '--audit',
        '--max-processing-slowdown',
        '5.0',
        '--rebaseline',
        str(Path('new.jsonl.gz').absolute()),
        '--headless',
    ]
    assert arguments.project_root == tmp_path


def recording_handler(*, calls: list[dict[str, Any]], exit_code: ExitCode) -> Any:
    """Return a game handler that records how it was called and returns ``exit_code``.

    Returns:
        The handler.

    """

    def handle(*, options: dict[str, Any], game: type[Scene] | Scene) -> ExitCode:
        calls.append({'options': options, 'game': game})
        return exit_code

    return handle


def command_handler_not_called(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """A command handler for tools whose command is never run here.

    Raises:
        AssertionError: Always.

    """
    raise AssertionError(tool.name)


def stand_in_tool(
    *,
    name: str = 'report-thing',
    options: tuple[ToolOption, ...] = (),
    runs_game: bool = False,
    game_handler: Any = None,
    value_kind: Any = 'path',
) -> Tool:
    """A tool for the table's own tests (the real table holds only tools that run the game).

    A tool that runs no game gets a handler that returns SUCCESS unless one is given.

    Returns:
        The tool.

    """
    if game_handler is None and not runs_game:
        game_handler = recording_handler(calls=[], exit_code=ExitCode.SUCCESS)
    return Tool(
        name=name,
        help=f'{name} help',
        options=options,
        runs_game=runs_game,
        game_handler=game_handler,
        command_handler=command_handler_not_called,
        value_kind=value_kind,
        value_help=f'{name} value',
    )


def test_no_tool_flag_runs_the_game():
    """No tool flag given: None, so the game runs."""
    options = vars(game_parser().parse_args([]))

    assert run_game_flag_tool(options=options, game=FlagToolScene) is None


def test_a_tool_the_game_runs_for_runs_the_game():
    """--replay-trace runs the game (its run replays): None."""
    options = vars(game_parser().parse_args(['--replay-trace', 'run.jsonl.gz']))

    assert run_game_flag_tool(options=options, game=FlagToolScene) is None


def test_a_tool_that_runs_no_game_runs_in_its_place():
    """A tool flag whose tool doesn't run the game: its handler's exit code, with the options."""
    calls: list[dict[str, Any]] = []
    tool = stand_in_tool(
        game_handler=recording_handler(calls=calls, exit_code=ExitCode.UNUSABLE_INPUT)
    )
    options = {'report_thing': 'run.jsonl.gz'}

    exit_code = run_game_flag_tool(options=options, game=FlagToolScene, tools=(tool,))

    assert exit_code == ExitCode.UNUSABLE_INPUT
    assert calls == [{'options': options, 'game': FlagToolScene}]


def test_a_tool_without_its_required_option_is_refused(caplog):
    """A required option missing from a game flag tool: OPTIONS_REFUSED, naming it; not run."""
    calls: list[dict[str, Any]] = []
    required = ToolOption(flag='--frames', kind='count', help='frames', required=True)
    tool = stand_in_tool(
        options=(required,),
        game_handler=recording_handler(calls=calls, exit_code=ExitCode.SUCCESS),
    )

    exit_code = run_game_flag_tool(
        options={'report_thing': 'run.jsonl.gz', 'frames': None},
        game=FlagToolScene,
        tools=(tool,),
    )

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert '--report-thing needs --frames' in caplog.text
    assert calls == []


def test_an_option_two_tools_share_is_one_game_flag():
    """The same ToolOption in two tools is added to the game once."""
    shared = ToolOption(flag='--shared', kind='flag', help='shared', default=False)
    parser = argparse.ArgumentParser()

    add_game_flags(
        parser=parser,
        tools=(
            stand_in_tool(name='first-tool', options=(shared,)),
            stand_in_tool(name='second-tool', options=(shared,)),
        ),
    )

    assert vars(parser.parse_args(['--shared'])) == {
        'first_tool': None,
        'second_tool': None,
        'shared': True,
    }


def test_two_tools_describing_one_flag_differently_are_refused():
    """One flag, two descriptions: the table is wrong, so building the game's flags fails."""
    with pytest.raises(ValueError, match='--shared is described twice, differently'):
        add_game_flags(
            parser=argparse.ArgumentParser(),
            tools=(
                stand_in_tool(
                    name='first-tool',
                    options=(ToolOption(flag='--shared', kind='flag', help='one'),),
                ),
                stand_in_tool(
                    name='second-tool',
                    options=(ToolOption(flag='--shared', kind='flag', help='two'),),
                ),
            ),
        )


EVERY_KIND_OPTIONS: tuple[tuple[ToolOptionKind, list[str], object, list[str]], ...] = (
    # kind, given on the command line, parsed value, passed on to the game
    ('path', ['--a-path', 'x.txt'], 'x.txt', ['--a-path', str(Path('x.txt').absolute())]),
    (
        'paths',
        ['--a-paths', 'a', 'b'],
        ['a', 'b'],
        ['--a-paths', str(Path('a').absolute()), str(Path('b').absolute())],
    ),
    ('int', ['--a-int', '-3'], -3, ['--a-int', '-3']),
    ('count', ['--a-count', '4'], 4, ['--a-count', '4']),
    ('percent', ['--a-percent', '2.5'], 2.5, ['--a-percent', '2.5']),
    ('number', ['--a-number', '-0.5'], -0.5, ['--a-number', '-0.5']),
    ('choice', ['--a-choice', 'two'], 'two', ['--a-choice', 'two']),
    ('flag', ['--a-flag'], True, ['--a-flag']),
    ('switch', ['--a-switch'], True, ['--a-switch']),
    ('reference', ['--a-reference', 'm:n'], 'm:n', ['--a-reference', 'm:n']),
    ('game', ['--a-game', 'g'], 'g', ['--a-game', 'g']),
    (
        'games',
        ['--a-games', 'g', '--a-games', 'h'],
        ['g', 'h'],
        ['--a-games', 'g', '--a-games', 'h'],
    ),
    ('text', ['--a-text', 'gold'], 'gold', ['--a-text', 'gold']),
)


def every_kind_tool(*, value_kind: Any) -> Tool:
    """A tool with one option of each kind (``EVERY_KIND_OPTIONS``).

    Returns:
        The tool.

    """
    options = tuple(
        ToolOption(
            flag=f'--a-{kind}',
            kind=kind,
            help=kind,
            choices=('one', 'two') if kind == 'choice' else (),
            default=False if kind in {'flag', 'switch'} else None,
        )
        for kind, *_ in EVERY_KIND_OPTIONS
    )
    return stand_in_tool(name='every-kind', options=options, value_kind=value_kind)


@pytest.mark.parametrize(
    ('kind', 'given', 'parsed', 'passed_on'),
    EVERY_KIND_OPTIONS,
    ids=[kind for kind, *_ in EVERY_KIND_OPTIONS],
)
def test_each_kind_of_option_reads_the_same_on_both_front_ends(kind, given, parsed, passed_on):
    """Each kind parses alike on the game and the command, and is passed on to the game as given."""
    tool = every_kind_tool(value_kind='flag')
    game = argparse.ArgumentParser()
    add_game_flags(parser=game, tools=(tool,))
    command_parser = build_command_parser(tools=(tool,))
    destination = f'a_{kind}'

    on_the_game = vars(game.parse_args(given))[destination]
    on_the_command = command_parser.parse_args(['every-kind', *given])

    assert on_the_game == parsed
    assert getattr(on_the_command, destination) == parsed
    assert tool.child_arguments(arguments=on_the_command) == ['--every-kind', *passed_on]


@pytest.mark.parametrize(
    ('value_kind', 'game_flag', 'command_line', 'parsed', 'passed_on'),
    [
        ('path', ['--every-kind', 'a'], ['a'], 'a', [str(Path('a').absolute())]),
        (
            'paths',
            ['--every-kind', 'a', 'b'],
            ['a', 'b'],
            ['a', 'b'],
            [str(Path('a').absolute()), str(Path('b').absolute())],
        ),
        ('flag', ['--every-kind'], [], True, []),
    ],
)
def test_each_kind_of_tool_value_reads_the_same_on_both_front_ends(
    value_kind, game_flag, command_line, parsed, passed_on
):
    """A tool's own value: a path, several or none, as a game flag and as the command's."""
    tool = every_kind_tool(value_kind=value_kind)
    game = argparse.ArgumentParser()
    add_game_flags(parser=game, tools=(tool,))
    on_the_command = build_command_parser(tools=(tool,)).parse_args(['every-kind', *command_line])

    assert vars(game.parse_args(game_flag))['every_kind'] == parsed
    assert tool.child_arguments(arguments=on_the_command) == ['--every-kind', *passed_on]
    assert tool.destination_value(arguments=on_the_command) == parsed


def test_the_help_shows_how_each_kind_of_tool_value_is_given():
    """The command's help writes a path tool's PATH, a paths tool's [PATH ...], a flag's none."""
    tools = (
        stand_in_tool(name='one-path', value_kind='path'),
        stand_in_tool(name='many-paths', value_kind='paths'),
        stand_in_tool(name='no-value', value_kind='flag'),
    )

    help_text = build_command_parser(tools=tools).format_help()

    assert '  one-path PATH\n' in help_text
    assert '  many-paths [PATH ...]\n' in help_text
    assert '  no-value\n' in help_text


def test_arguments_after_a_bare_dash_dash_need_a_tool_that_runs_the_game(capsys):
    """A tool that runs no game has nothing to give them to: a usage error."""
    with pytest.raises(SystemExit) as exit_information:
        command.main(
            ['report-thing', 'run.jsonl.gz', '--', '--resolution', '320x240'],
            tools=(stand_in_tool(),),
        )

    assert exit_information.value.code == ExitCode.ARGUMENT_PARSER_ERROR
    assert 'report-thing runs no game' in capsys.readouterr().err


def test_a_name_no_tool_has_is_a_key_error():
    """tool_named: only the table's names."""
    with pytest.raises(KeyError, match='no-such-tool'):
        tool_named(name='no-such-tool')


def test_a_switch_given_off_is_passed_on_off():
    """A switch defaulting to on, given as --no-x, reaches the game as --no-x (not --x)."""
    switch = ToolOption(flag='--fancy', kind='switch', help='fancy', default=True)
    tool = stand_in_tool(name='switch-tool', options=(switch,), value_kind='flag')
    parsed = build_command_parser(tools=(tool,)).parse_args(['switch-tool', '--no-fancy'])

    assert tool.child_arguments(arguments=parsed) == ['--switch-tool', '--no-fancy']


def test_two_tools_given_at_once_are_refused_naming_both(caplog):
    """--record-trace with --replay-trace: OPTIONS_REFUSED, naming both; neither runs."""
    options = vars(
        game_parser().parse_args([
            '--record-trace',
            'new.jsonl.gz',
            '--replay-trace',
            'old.jsonl.gz',
        ])
    )

    exit_code = run_game_flag_tool(options=options, game=FlagToolScene)

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert (
        'one tool at a time: --record-trace and --replay-trace were given together' in caplog.text
    )


def test_a_tool_given_with_one_that_runs_no_game_is_refused(caplog):
    """A tool that runs no game is never skipped because another tool was given first."""
    calls: list[dict[str, Any]] = []
    first = stand_in_tool(name='first-tool', runs_game=True)
    second = stand_in_tool(
        name='second-tool',
        game_handler=recording_handler(calls=calls, exit_code=ExitCode.SUCCESS),
    )

    exit_code = run_game_flag_tool(
        options={'first_tool': 'a.jsonl.gz', 'second_tool': 'b.jsonl.gz'},
        game=FlagToolScene,
        tools=(first, second),
    )

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert '--first-tool and --second-tool were given together' in caplog.text
    assert calls == []


def test_a_tool_that_runs_no_game_needs_a_game_handler():
    """Without one, the game would run in its place: refused when the table is built."""
    with pytest.raises(ValueError, match='report-thing runs no game, so it needs a game handler'):
        Tool(
            name='report-thing',
            help='report',
            options=(),
            runs_game=False,
            game_handler=None,
            command_handler=command_handler_not_called,
        )
