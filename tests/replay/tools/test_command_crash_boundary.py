"""The ``glitchygames`` command runs its tools inside the engine's crash boundary.

The game flags run every tool inside ``GameEngine``'s boundary (``_run_game_flag_tool``): an
uncaught exception exits ``INTERNAL_ERROR`` (70), Ctrl-C ``INTERRUPTED`` and a terminating
signal its own code, with any child stopped and reaped first. The command
(glitchygames/replay/tools/command.py) runs its tools inside the same boundary
(``game_engine.run_inside_tool_crash_boundary``), and reports a child killed by a signal as a
shell does (128 + the signal), never as Python's 256 - N. A required option missing is refused
alike on both front ends (``ExitCode.OPTIONS_REFUSED``, 64).
"""

from __future__ import annotations

import contextlib
import logging
import os
import signal
import sys
import time
from typing import TYPE_CHECKING, Any

import pytest

from glitchygames.exit_codes import BUG_REPORT_HINT, SIGNAL_EXIT_STATUS_BASE, ExitCode
from glitchygames.process import start_command
from glitchygames.replay.tools import command
from glitchygames.replay.tools.registry import Tool, ToolOption, run_game_flag_tool
from glitchygames.scenes import Scene

if TYPE_CHECKING:
    import argparse
    from pathlib import Path

# How long the command may take to start its child, and to end once signalled
COMMAND_DEADLINE_SECONDS = 60.0
# How often a deadline loop looks again
POLL_SECONDS = 0.05
# A game that writes its process id next to itself, then never ends on its own
SLEEPING_GAME_SOURCE = """\
import os
import pathlib
import time

pathlib.Path(__file__).with_name('child.pid').write_text(str(os.getpid()), encoding='utf-8')
while True:
    time.sleep(1)
"""
# A game that kills itself with SIGKILL, as a native crash or the OOM killer would end it
SELF_KILLING_GAME_SOURCE = """\
import os
import signal

os.kill(os.getpid(), signal.SIGKILL)
"""
POSIX_SIGNALS_ONLY = pytest.mark.skipif(
    sys.platform == 'win32', reason='SIGKILL and signals sent to one process are POSIX'
)


class GameThatIsNeverRun(Scene):
    """The game a game-flag tool is given; the tools here never run it."""

    NAME = 'GameThatIsNeverRun'
    VERSION = '1.0'


def never_run_on_the_game(*, options: dict[str, Any], game: type[Scene] | Scene) -> ExitCode:
    """A game handler the tests here never reach.

    Raises:
        AssertionError: Always.

    """
    del options, game
    message = 'the game handler was run'
    raise AssertionError(message)


def command_tool(*, error: BaseException) -> Tool:
    """A tool whose subcommand raises ``error``, as a bug in the command's own process would.

    Returns:
        The tool.

    """

    def raise_error(*, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]) -> int:
        del tool, arguments, game_arguments
        raise error

    return Tool(
        name='broken-thing',
        help='a tool whose command raises',
        options=(),
        runs_game=False,
        game_handler=never_run_on_the_game,
        command_handler=raise_error,
        value_kind='flag',
    )


def test_a_tool_that_crashes_exits_internal_error_as_on_the_game(caplog):
    """An uncaught exception in the command's tool: INTERNAL_ERROR, logged as the engine logs it.

    Never Python's 1 with a bare traceback, which is ``REPLAY_DIVERGED``'s code.
    """
    caplog.set_level(logging.ERROR)

    status = command.main(['broken-thing'], tools=(command_tool(error=RuntimeError('it broke')),))

    assert status == ExitCode.INTERNAL_ERROR
    (record,) = [
        record
        for record in caplog.records
        if record.getMessage() == "Runtime error during game execution @ tool '--broken-thing'"
    ]
    assert record.exc_info is not None
    assert 'it broke' in caplog.text
    # The command has no --log-level, so it never tells a player to rerun it with one
    assert BUG_REPORT_HINT not in caplog.text


def test_ctrl_c_in_the_commands_tool_exits_interrupted():
    """KeyboardInterrupt in the command's tool: INTERRUPTED, as on the game."""
    status = command.main(['broken-thing'], tools=(command_tool(error=KeyboardInterrupt()),))

    assert status == ExitCode.INTERRUPTED


def child_is_running(*, process_id: int) -> bool:
    """Tell whether a process is still running (a zombie counts: nobody reaped it).

    Returns:
        True while the process exists.

    """
    try:
        os.kill(process_id, 0)
    except ProcessLookupError:
        return False
    return True


def wait_for_file(*, path: Path, deadline_seconds: float) -> str:
    """Wait for a file to have text in it.

    Returns:
        Its text.

    Raises:
        AssertionError: If it has none by the deadline.

    """
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        if path.is_file() and (text := path.read_text(encoding='utf-8')):
            return text
        time.sleep(POLL_SECONDS)
    message = f'{path} was never written'
    raise AssertionError(message)


@POSIX_SIGNALS_ONLY
@pytest.mark.parametrize('signal_number', [signal.SIGTERM, signal.SIGINT])
def test_a_signal_stops_and_reaps_the_commands_child_and_exits_with_its_code(
    tmp_path, signal_number
):
    """SIGTERM or SIGINT to ``glitchygames record-trace``: the game it started is ended first.

    The command exits with the signal's code (143, 130), and its child is gone: killed and
    reaped before the command ended, never left running without its parent.
    """
    game = tmp_path / 'sleeping_game.py'
    game.write_text(SLEEPING_GAME_SOURCE, encoding='utf-8')
    child_pid_file = tmp_path / 'child.pid'
    with (tmp_path / 'command-output.txt').open('w', encoding='utf-8') as output:
        running = start_command(
            command=[
                sys.executable,
                '-m',
                'glitchygames',
                'record-trace',
                str(game),
                str(tmp_path / 'run.jsonl.gz'),
            ],
            environment=os.environ,
            output=output,
        )
        child_pid = 0
        try:
            child_pid = int(
                wait_for_file(path=child_pid_file, deadline_seconds=COMMAND_DEADLINE_SECONDS)
            )
            os.kill(running.pid, signal_number)
            status = running.wait(timeout=COMMAND_DEADLINE_SECONDS)
            child_left_running = child_is_running(process_id=child_pid)
        finally:
            if running.poll() is None:
                running.kill()
                running.wait()
            if child_pid and child_is_running(process_id=child_pid):
                with contextlib.suppress(ProcessLookupError):
                    os.kill(child_pid, signal.SIGKILL)

    output_text = (tmp_path / 'command-output.txt').read_text(encoding='utf-8')
    assert status == ExitCode.for_signal(signal_number), output_text
    assert not child_left_running


@POSIX_SIGNALS_ONLY
def test_a_child_killed_by_a_signal_is_reported_as_128_plus_the_signal(tmp_path):
    """A game killed by SIGKILL: the command exits 137, as the shell reports the game run alone.

    Not 247 (``sys.exit(-9)``), a code the project does not document.
    """
    game = tmp_path / 'self_killing_game.py'
    game.write_text(SELF_KILLING_GAME_SOURCE, encoding='utf-8')

    status = command.main(['record-trace', str(game), str(tmp_path / 'run.jsonl.gz')])

    assert status == SIGNAL_EXIT_STATUS_BASE + signal.SIGKILL


def required_option_tool() -> Tool:
    """A tool with a required option, as record-session's ``--frame-count``.

    Returns:
        The tool.

    """

    def never_run(*, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]) -> int:
        del tool, arguments, game_arguments
        message = 'the command handler was run'
        raise AssertionError(message)

    return Tool(
        name='needy-thing',
        help='a tool with a required option',
        options=(ToolOption(flag='--frames', kind='count', help='frames', required=True),),
        runs_game=False,
        game_handler=never_run_on_the_game,
        command_handler=never_run,
        value_kind='flag',
    )


def test_a_missing_required_option_is_refused_alike_on_both_front_ends(capsys, caplog):
    """``--frames`` missing: OPTIONS_REFUSED (64, EX_USAGE) on the game and on the command.

    The command names the option as the game does, and runs nothing.
    """
    tool = required_option_tool()

    on_the_game = run_game_flag_tool(
        options={'needy_thing': True, 'frames': None}, game=GameThatIsNeverRun, tools=(tool,)
    )
    on_the_command = command.main(['needy-thing'], tools=(tool,))

    assert on_the_game == on_the_command == ExitCode.OPTIONS_REFUSED
    assert '--needy-thing needs --frames' in caplog.text
    assert 'glitchygames needy-thing: --needy-thing needs --frames' in capsys.readouterr().err


def test_a_real_tools_missing_required_option_is_refused_on_the_command(tmp_path, capsys):
    """``glitchygames record-session GAME PATH`` without ``--frame-count``: 64, not argparse's 2."""
    status = command.main([
        'record-session',
        'no_such_game_anywhere',
        str(tmp_path / 'session.jsonl.gz'),
        '--input-script',
        'a_module:a_script',
    ])

    assert status == ExitCode.OPTIONS_REFUSED
    assert '--record-session needs --frame-count' in capsys.readouterr().err
