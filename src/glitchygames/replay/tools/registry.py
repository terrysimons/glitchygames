"""The table of the engine's tools (``TOOLS``) and the two front ends built from it.

Every recording, replay and measurement tool is described once, as a ``Tool`` with its
``ToolOption`` s, and both front ends are generated from that description, so a tool's name,
options, defaults and help can't differ between them (tests/replay/tools/test_registry.py walks
the table to check):

- **On the game** (``add_game_flags``): ``GameEngine.args`` adds each tool to the game's own
  command line as ``--<name>`` (with the tool's options as flags of their own), so any game the
  engine runs has them without declaring anything. A tool with a game handler runs in place of
  the game's own run (``run_game_flag_tool``, from ``GameEngine.__init__``, before the engine
  starts pygame): one that runs no game, or one that runs the game in a harness of its own
  (``--record-golden-trace``, ``--record-session``). A tool without one is the game's run, which
  the engine already handles (``--record-trace``, ``--replay-trace``).
- **As the ``glitchygames`` command** (``build_command_parser``, glitchygames/replay/tools/
  command.py): each tool is a subcommand with the same name and options, plus the command's own
  arguments (the game to run, ``--project-root``). A subcommand whose tool runs the game starts
  it as a child process with the tool's flag (glitchygames/replay/tools/children.py).

An option may be listed under several tools (the same ``ToolOption``: ``--headless`` is
record-trace's and replay-trace's); it is one flag on the game and an option of each tool's
subcommand. The engine's general flags that no tool lists (``--resolution``, ...) stay in
``GameEngine.args``; the command passes them to the game after a bare ``--``. Only one tool runs
at a time: a game given two tool flags is refused (``run_game_flag_tool``).
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast

from glitchygames.argument_types import non_negative_int, non_negative_percent
from glitchygames.exit_codes import ExitCode
from glitchygames.replay.driver import REPLAY_FPS_CHOICES
from glitchygames.replay.tools.children import GAME_FORMS
from glitchygames.replay.tools.measure import (
    clear_published_command,
    clear_published_on_the_game,
    measure_command,
    measure_on_the_game,
    unmeasured_command,
    unmeasured_on_the_game,
)
from glitchygames.replay.tools.performance_pages import (
    performance_pages_command,
    performance_pages_on_the_game,
)
from glitchygames.replay.tools.report import (
    DEFAULT_MINIMUM_MS,
    DEFAULT_SPAN_LIMIT,
    DEFAULT_THRESHOLD_PERCENT,
    report_command,
    report_on_the_game,
)
from glitchygames.replay.tools.traces import (
    record_golden_trace_command,
    record_golden_trace_on_the_game,
    record_session_command,
    record_session_on_the_game,
    record_trace_command,
    replay_trace_command,
)
from glitchygames.replay.tools.verify import verify_command, verify_on_the_game

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.scenes import Scene

LOG = logging.getLogger('game.tools')

# The command's name (its console script, [project.scripts]) and its parser's prog
COMMAND_NAME = 'glitchygames'
# The command's option every subcommand has: the project the tool works on
PROJECT_ROOT_FLAG = '--project-root'
# The width the command's help lists the tools in (argparse's default terminal width)
HELP_WIDTH = 80

# How a ToolOption's value is read: a path, several paths, an integer, a count (an integer >= 0),
# a percentage >= 0, a number (any float), one of its choices, an on flag (store_true), an on/off
# switch (--x/--no-x), a MODULE:NAME reference, a game (children.GAME_FORMS), games (the option
# given once per game: --game a --game b), or plain text
type ToolOptionKind = Literal[
    'path',
    'paths',
    'int',
    'count',
    'percent',
    'number',
    'choice',
    'flag',
    'switch',
    'reference',
    'game',
    'games',
    'text',
]
# What a tool's own flag takes: one path (--replay-trace PATH), several (--verify [PATH ...]) or
# no value at all (--unmeasured)
type ToolValueKind = Literal['path', 'paths', 'flag']
# Which front end an option is being added to
type FrontEnd = Literal['game', 'command']
# The add_argument settings that read each kind of option value (a choice's choices are its own)
KIND_SETTINGS: dict[ToolOptionKind, dict[str, Any]] = {
    'path': {},
    'paths': {'nargs': '*'},
    'int': {'type': int},
    'count': {'type': non_negative_int},
    'percent': {'type': non_negative_percent},
    'number': {'type': float},
    'choice': {},
    'flag': {'action': 'store_true'},
    'switch': {'action': argparse.BooleanOptionalAction},
    'reference': {},
    'game': {},
    'games': {'action': 'append'},
    'text': {},
}


class ArgumentContainer(Protocol):
    """Anything options are added to: an ``argparse.ArgumentParser`` or one of its groups."""

    def add_argument(self, *name_or_flags: str, **settings: Any) -> argparse.Action:
        """Add an argument (``argparse``'s own signature)."""
        ...


class GameHandler(Protocol):
    """Runs a tool given as a game flag, in place of the game (``run_game_flag_tool``)."""

    def __call__(self, *, options: dict[str, Any], game: type[Scene] | Scene) -> ExitCode:
        """Run the tool with the game's parsed options; return how the run ends."""
        ...


class CommandHandler(Protocol):
    """Runs a ``glitchygames <tool>`` subcommand (glitchygames/replay/tools/command.py)."""

    def __call__(
        self, *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
    ) -> int:
        """Run the subcommand; return its exit status (a child game's, when one ran)."""
        ...


@dataclasses.dataclass(frozen=True)
class ToolOption:
    """One option of a tool, the same on the game and on the command.

    Attributes:
        flag: The option (``--rebaseline``); a name without dashes is a positional argument,
            which only a command argument may be (``Tool.command_arguments``) and which is
            always required.
        help: Its help text (argparse's ``help``).
        kind: How its value is read (``ToolOptionKind``).
        required: Whether the tool needs it. On the command argparse requires it; a game flag
            is never required by argparse (the game runs without the tool), so
            ``run_game_flag_tool`` refuses the tool without it.
        metavar: Its value's name in the help (None: argparse's own, or the choices).
        default: Its value when not given.
        choices: The values a ``choice`` option takes.

    """

    flag: str
    help: str
    kind: ToolOptionKind
    required: bool = False
    metavar: str | None = None
    default: object = None
    choices: tuple[str, ...] = ()

    @property
    def destination(self) -> str:
        """The option's key in the parsed options (``--replay-fps`` -> ``replay_fps``).

        Returns:
            argparse's ``dest`` for it.

        """
        return self.flag.lstrip('-').replace('-', '_')

    @property
    def positional(self) -> bool:
        """Whether it is a positional argument (no leading dash)."""
        return not self.flag.startswith('-')


@dataclasses.dataclass(frozen=True)
class Tool:
    """One tool: ``--<name>`` on every game and ``glitchygames <name>``.

    Attributes:
        name: Its name, the same on both front ends (``replay-trace``).
        help: Its help text: the game flag's and the subcommand's.
        options: Its options, the same on both front ends, in order.
        runs_game: Whether the game runs for it (``--replay-trace``) or not (``--report``).
        game_handler: What runs it given as a game flag, in place of the game; None for a tool
            the game's own run handles (``runs_game``). A tool that runs no game must have one
            (refused when it is made: the game would otherwise run in its place).
        command_handler: What runs ``glitchygames <name>``.
        value_kind: What its own flag takes (``ToolValueKind``).
        value_metavar: That value's name in the help (``PATH``).
        value_help: That value's help as the command's positional argument.
        command_arguments: The command's arguments that the game flag has no need of (the game
            to run: ``GAME``, ``--game``): positional ones go before the value, the others after
            the options.

    """

    name: str
    help: str
    options: tuple[ToolOption, ...]
    runs_game: bool
    game_handler: GameHandler | None
    command_handler: CommandHandler
    value_kind: ToolValueKind = 'path'
    value_metavar: str = 'PATH'
    value_help: str = ''
    command_arguments: tuple[ToolOption, ...] = ()

    def __post_init__(self) -> None:
        """Refuse a tool that runs no game and has no game handler.

        Raises:
            ValueError: If ``runs_game`` is False and ``game_handler`` is None.

        """
        if not self.runs_game and self.game_handler is None:
            message = (
                f'{self.name} runs no game, so it needs a game handler (without one the game '
                'would run in its place)'
            )
            raise ValueError(message)

    @property
    def flag(self) -> str:
        """The tool's game flag (``--replay-trace``)."""
        return f'--{self.name}'

    @property
    def destination(self) -> str:
        """The tool's key in the parsed options, on both front ends (``replay_trace``)."""
        return self.name.replace('-', '_')

    def child_arguments(self, *, arguments: argparse.Namespace) -> list[str]:
        """Return the game flags that run this tool as the command was asked to.

        The tool's flag and value come first, then each option given a value other than its
        default. Paths are made absolute, so they mean the same in a child started in another
        directory (``--project-root``).

        Args:
            arguments: The subcommand's parsed arguments.

        Returns:
            The arguments for the game's command line.

        """
        child = [
            self.flag,
            *flag_values(kind=self.value_kind, value=self.destination_value(arguments=arguments)),
        ]
        for option in self.options:
            value = getattr(arguments, option.destination)
            if value == option.default:
                continue
            child.extend(option_on_the_command_line(option=option, value=value))
        return child

    def destination_value(self, *, arguments: argparse.Namespace) -> object:
        """Return the tool's own value from the subcommand's parsed arguments.

        Args:
            arguments: The subcommand's parsed arguments.

        Returns:
            The value (True for a ``flag`` tool, whose subcommand has no value).

        """
        if self.value_kind == 'flag':
            return True
        return getattr(arguments, self.destination)


def option_on_the_command_line(*, option: ToolOption, value: object) -> list[str]:
    """Return an option as a child's command line gives it, for a value other than its default.

    A switch given off (``--no-x``, whatever its default) is passed on off.

    Args:
        option: The option.
        value: Its parsed value.

    Returns:
        The flag and what follows it.

    """
    if option.kind == 'switch' and value is False:
        return [f'--no-{option.flag.removeprefix("--")}']
    if option.kind == 'games':
        # argparse's action='append': the option once per game, as it was given
        games = cast('list[str]', value)
        return [part for game in games for part in (option.flag, game)]
    return [option.flag, *flag_values(kind=option.kind, value=value)]


def flag_values(*, kind: ToolOptionKind | ToolValueKind, value: object) -> list[str]:
    """Return what follows a flag on a child's command line for a parsed value.

    Args:
        kind: How the value is read.
        value: The parsed value (not the option's default).

    Returns:
        Nothing for a flag or a switch (on: ``option_on_the_command_line`` writes a switch
        given off), the absolute path(s) for a path, else the value as text.

    """
    match kind:
        case 'flag' | 'switch':
            return []
        case 'path':
            return [str(Path(str(value)).absolute())]
        case 'paths':
            # argparse's nargs='*': a list of the strings given
            paths = cast('list[str]', value)
            return [str(Path(path).absolute()) for path in paths]
        case _:
            return [str(value)]


def option_settings(*, option: ToolOption, front_end: FrontEnd) -> dict[str, Any]:
    """Return ``add_argument``'s settings for an option on one front end.

    Both front ends get the same settings, apart from ``required``: argparse requires a required
    option on the command only (a game runs without the tool).

    Args:
        option: The option.
        front_end: Where it is being added.

    Returns:
        The keyword arguments for ``add_argument``.

    """
    settings: dict[str, Any] = {'help': option.help, **kind_settings(option=option)}
    if not option.positional:
        settings['default'] = option.default
        settings['required'] = option.required and front_end == 'command'
    if option.metavar is not None:
        settings['metavar'] = option.metavar
    return settings


def kind_settings(*, option: ToolOption) -> dict[str, Any]:
    """Return the ``add_argument`` settings that read an option's kind of value.

    Args:
        option: The option.

    Returns:
        The action, ``nargs``, ``type`` or ``choices`` its kind needs (``KIND_SETTINGS``; none
        for a path, a reference or a game: a string).

    """
    settings = dict(KIND_SETTINGS[option.kind])
    if option.kind == 'choice':
        settings['choices'] = option.choices
    return settings


def tool_flag_settings(*, tool: Tool) -> dict[str, Any]:
    """Return ``add_argument``'s settings for a tool's own game flag (``--replay-trace PATH``).

    Args:
        tool: The tool.

    Returns:
        The keyword arguments for ``add_argument``.

    """
    if tool.value_kind == 'flag':
        return {'help': tool.help, 'action': 'store_true', 'default': False}
    if tool.value_kind == 'paths':
        return {'help': tool.help, 'metavar': tool.value_metavar, 'nargs': '*', 'default': None}
    return {'help': tool.help, 'metavar': tool.value_metavar, 'default': None}


def add_game_flags(*, parser: ArgumentContainer, tools: Sequence[Tool] | None = None) -> None:
    """Add every tool to a game's command line: ``--<name>``, then each tool's options.

    Called by ``GameEngine.args`` with its Diagnostics Options group. The tools' flags come
    first, in the table's order, then their options; an option two tools share (the same
    ``ToolOption``) is added once.

    Args:
        parser: The parser or group to add them to.
        tools: The tools (``TOOLS`` unless given).

    Raises:
        ValueError: If two tools describe an option with the same flag differently.

    """
    tools = TOOLS if tools is None else tools
    for tool in tools:
        parser.add_argument(tool.flag, **tool_flag_settings(tool=tool))
    added: dict[str, ToolOption] = {}
    for tool in tools:
        for option in tool.options:
            if option.flag in added:
                if added[option.flag] != option:
                    message = f'{option.flag} is described twice, differently'
                    raise ValueError(message)
                continue
            added[option.flag] = option
            parser.add_argument(option.flag, **option_settings(option=option, front_end='game'))


def tool_summary(*, tool: Tool) -> str:
    """Describe a subcommand's command line on one line, for ``glitchygames --help``.

    Args:
        tool: The tool.

    Returns:
        ``<name> <arguments> [options]``, with every option's flag.

    """
    positional = [
        argument.metavar or argument.flag.upper()
        for argument in tool.command_arguments
        if argument.positional
    ]
    if tool.value_kind == 'path':
        positional.append(tool.value_metavar)
    elif tool.value_kind == 'paths':
        positional.append(f'[{tool.value_metavar} ...]')
    flags = [
        option.flag for option in (*tool.options, *tool.command_arguments) if not option.positional
    ]
    return ' '.join([tool.name, *positional, *(f'[{flag}]' for flag in flags)])


def build_command_parser(*, tools: Sequence[Tool] | None = None) -> argparse.ArgumentParser:
    """Build the ``glitchygames`` command's parser: one subcommand per tool.

    Each subcommand has the command's positional arguments (``GAME``), the tool's value, its
    options (as on the game), its other command arguments (``--game``) and ``--project-root``.
    The parser's help lists every tool with all its options (``--rebaseline`` and ``--audit``
    under ``replay-trace``).

    Args:
        tools: The tools (``TOOLS`` unless given).

    Returns:
        The parser; ``tool`` in its result names the subcommand given.

    """
    tools = TOOLS if tools is None else tools
    epilog_lines = [
        'every tool, with its options (glitchygames TOOL --help describes them):',
        *(
            textwrap.fill(
                tool_summary(tool=tool),
                width=HELP_WIDTH,
                initial_indent='  ',
                subsequent_indent='      ',
                break_on_hyphens=False,
            )
            for tool in tools
        ),
        '',
        'Each tool is also a flag on any game built on the engine (mygame --TOOL ...). Arguments',
        'after a bare -- go to the game (glitchygames record-trace GAME PATH -- --resolution',
        '640x480).',
    ]
    parser = argparse.ArgumentParser(
        prog=COMMAND_NAME,
        description="The glitchygames engine's recording, replay and measurement tools.",
        epilog='\n'.join(epilog_lines),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest='tool', required=True, metavar='TOOL', title='tools')
    for tool in tools:
        subparser = subparsers.add_parser(tool.name, help=tool.help, description=tool.help)
        for argument in tool.command_arguments:
            if argument.positional:
                subparser.add_argument(
                    argument.flag, **option_settings(option=argument, front_end='command')
                )
        if tool.value_kind != 'flag':
            subparser.add_argument(
                tool.destination,
                metavar=tool.value_metavar,
                help=tool.value_help,
                nargs='*' if tool.value_kind == 'paths' else None,
            )
        for option in tool.options:
            subparser.add_argument(
                option.flag, **option_settings(option=option, front_end='command')
            )
        for argument in tool.command_arguments:
            if not argument.positional:
                subparser.add_argument(
                    argument.flag, **option_settings(option=argument, front_end='command')
                )
        subparser.add_argument(
            PROJECT_ROOT_FLAG,
            metavar='DIR',
            type=Path,
            default=None,
            help=(
                'the project the tool works on, where a game it starts runs and may be found as '
                'a module (default: the current directory)'
            ),
        )
    return parser


def tool_named(*, name: str, tools: Sequence[Tool] | None = None) -> Tool:
    """Return the tool of a name.

    Args:
        name: Its name (a subcommand's).
        tools: The tools (``TOOLS`` unless given).

    Returns:
        The tool.

    Raises:
        KeyError: If no tool has that name.

    """
    tools = TOOLS if tools is None else tools
    for tool in tools:
        if tool.name == name:
            return tool
    raise KeyError(name)


def given(*, value: object) -> bool:
    """Tell whether a parsed game flag was given: neither its absent default None nor False.

    An empty list is given (``--verify`` with no paths).

    Args:
        value: The parsed value.

    Returns:
        True if it was given.

    """
    return value is not None and value is not False


def given_tools(*, options: dict[str, Any], tools: Sequence[Tool] | None = None) -> list[Tool]:
    """Return the tools a game's parsed options give as flags, in the table's order.

    Args:
        options: The game's parsed options (``GameEngine.OPTIONS``).
        tools: The tools (``TOOLS`` unless given).

    Returns:
        Each tool whose flag was given (``given``).

    """
    tools = TOOLS if tools is None else tools
    return [tool for tool in tools if given(value=options.get(tool.destination))]


def tool_free_arguments(*, arguments: Sequence[str], tool: Tool) -> list[str]:
    """Return a game's command line without one tool's own flag, value and options.

    What a tool that starts the game again (``--verify``) passes on as the game's arguments, as
    the command passes those after a bare ``--``. The tool's flag and options are read by a
    parser of their own (``add_game_flags`` with that tool alone, no abbreviations); everything
    it does not know is the game's.

    Args:
        arguments: The game's command line, without the program (``sys.argv[1:]``).
        tool: The tool.

    Returns:
        The other arguments, in order.

    """
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    add_game_flags(parser=parser, tools=(tool,))
    _, others = parser.parse_known_args(list(arguments))
    return others


def run_game_flag_tool(
    *,
    options: dict[str, Any],
    game: type[Scene] | Scene,
    tools: Sequence[Tool] | None = None,
) -> ExitCode | None:
    """Run the tool given as a game flag in place of the game's run, if it has a game handler.

    Called by ``GameEngine.__init__`` (``_run_game_flag_tool``) before the engine starts pygame,
    opens its window or builds the game's scene. One tool at a time: two tool flags given
    together are refused, so neither is silently skipped.

    Args:
        options: The game's parsed options (``GameEngine.OPTIONS``).
        game: The game (its class, or a scene the game passed in).
        tools: The tools (``TOOLS`` unless given).

    Returns:
        The tool's exit code; ``ExitCode.OPTIONS_REFUSED`` when it lacks a required option or
        another tool was given too; or None when the game is to run (no tool flag was given,
        or the tool given has no game handler: the game's own run handles it).

    """
    tools = TOOLS if tools is None else tools
    tools_given = given_tools(options=options, tools=tools)
    if not tools_given:
        return None
    if len(tools_given) > 1:
        LOG.error(
            'one tool at a time: %s were given together',
            ' and '.join(tool.flag for tool in tools_given),
        )
        return ExitCode.OPTIONS_REFUSED
    (tool,) = tools_given
    missing = [
        option.flag
        for option in tool.options
        if option.required and not given(value=options.get(option.destination))
    ]
    if missing:
        LOG.error('%s needs %s', tool.flag, ', '.join(missing))
        return ExitCode.OPTIONS_REFUSED
    if tool.game_handler is None:
        return None
    return tool.game_handler(options=options, game=game)


# --replay-trace's options, as GameEngine.args described them before the table (help text,
# destinations and defaults unchanged)
REPLAY_FPS_OPTION = ToolOption(
    flag='--replay-fps',
    kind='choice',
    choices=REPLAY_FPS_CHOICES,
    help=(
        'with --replay-trace: post FPS events from the recorded frame times (recorded, '
        "the default: exact, and compared with the recording) or from this machine's "
        'measured frame times (real: what this machine achieves; FPS events are then '
        'not compared, and sprites that draw the FPS value may diverge)'
    ),
    # None (not RECORDED_REPLAY_FPS) so that giving it without --replay-trace can be
    # warned about; start_replay reads None as recorded
    default=None,
)
AUDIT_OPTION = ToolOption(
    flag='--audit',
    kind='switch',
    help=(
        'with --replay-trace: instead of replaying, replay the recording twice in fresh '
        'headless processes with different hash seeds and compare every frame with the '
        f'recording and between the runs; exits {ExitCode.SUCCESS:d} when both match, '
        f'{ExitCode.AUDIT_NONDETERMINISTIC:d} otherwise, {ExitCode.INTERNAL_ERROR:d} if '
        'a run could not finish'
    ),
    default=False,
)
COMPARE_PROCESSING_OPTION = ToolOption(
    flag='--compare-processing',
    kind='flag',
    help=(
        "with --replay-trace --headless: measure each frame's processing time (its "
        'work, without presenting or pacing) and report how it compares with the '
        "recording's (only meaningful on the machine that recorded)"
    ),
    # None (not False) so that giving it without --replay-trace can be warned about
    default=None,
)
MAX_PROCESSING_SLOWDOWN_OPTION = ToolOption(
    flag='--max-processing-slowdown',
    kind='percent',
    metavar='PERCENT',
    help=(
        'with --replay-trace --headless (implies --compare-processing): a replay that '
        "matched but took more than PERCENT longer than the recording's processing time "
        f'exits {ExitCode.PROCESSING_SLOWER:d}; a recording without processing times '
        f'exits {ExitCode.UNUSABLE_INPUT:d}'
    ),
    default=None,
)
REPLAY_PAUSE_AT_FRAME_OPTION = ToolOption(
    flag='--replay-pause-at-frame',
    kind='count',
    metavar='N',
    help=(
        'with --replay-trace, watched: skip the start screen, run frames 0 to N - 1 '
        'without showing them, then pause with frame N next (what step back restarts '
        'with; ignored with --headless)'
    ),
    default=None,
)
REBASELINE_OPTION = ToolOption(
    flag='--rebaseline',
    kind='path',
    metavar='NEW',
    help=(
        'with --replay-trace OLD and --headless: replay OLD on the current code without '
        "stopping at divergences, write the run's recording (OLD's inputs, the current "
        'sprites) to NEW, print a summary of the frames and sprites that changed and '
        f'exit {ExitCode.SUCCESS:d}'
    ),
    default=None,
)
REPLAY_DIGEST_OPTION = ToolOption(
    flag='--replay-digest',
    kind='path',
    metavar='PATH',
    help=(
        'with --replay-trace: write a SHA-256 of every replayed frame, then the '
        'divergence, to PATH as JSON lines (used by --audit)'
    ),
    default=None,
)
# Listed by record-trace and replay-trace (the stage's tools table and the controller's
# shared-option ruling), and a general engine flag too: every game has it, once
HEADLESS_OPTION = ToolOption(
    flag='--headless',
    kind='flag',
    help=(
        "run on SDL's dummy video and audio drivers: no window, no sound. With "
        '--replay-trace the replay also runs unpaced and prints its report to stdout '
        f'(exit {ExitCode.SUCCESS:d} when it matches, {ExitCode.REPLAY_DIVERGED:d} '
        f'when it diverges, {ExitCode.UNUSABLE_INPUT:d} for a truncated recording)'
    ),
    default=False,
)
# Listed by every tool that records or replays (the stage's tools table, the controller's
# shared-option ruling and the user's seed rule, 2026-10-26), and a general engine flag too:
# every game has it, as GameEngine.args defined it before the table (it moved from its Graphics
# Options group to the tools' Diagnostics Options). None by default for every tool and a plain
# run (the user: "If none, we roll random, if something, we use the something"); a replay under
# another seed plays out without comparing ("we can replay the game but just not record a new
# version"), and only a rebaseline records it (rule 19 of glitchygames/replay/driver.py)
RANDOM_SEED_OPTION = ToolOption(
    flag='--random-seed',
    kind='int',
    help=(
        'master seed for every engine random stream. Not given, a run or recording rolls a '
        "random 64-bit seed (logged in the recording) and a replay uses the recording's. "
        "Given, a run or recording uses it, and a replay given the recording's own compares "
        "as always; a replay given another plays the recording's inputs out under it "
        'without comparing or writing anything (headless, it prints what differed and exits '
        f'{ExitCode.SUCCESS:d}); --replay-trace OLD --rebaseline NEW --random-seed N records '
        'them under it in NEW; --audit under another seed is refused, and so is any seed '
        'given to --verify (it always compares) or --measure (it rebaselines each recording '
        'under its recorded seed)'
    ),
    default=None,
)
# record-golden-trace's and record-session's options: the input script
# (golden_traces.load_input_script reads it: a callable taking no arguments that returns an
# InputScript) and how many of its frames run
INPUT_SCRIPT_OPTION = ToolOption(
    flag='--input-script',
    kind='reference',
    metavar='MODULE:NAME',
    required=True,
    help=(
        'with --record-golden-trace or --record-session: the input script, a callable taking '
        'no arguments that returns an InputScript (glitchygames.replay.tools.golden_traces); '
        'MODULE is looked for in the current directory first'
    ),
)
FRAME_COUNT_OPTION = ToolOption(
    flag='--frame-count',
    kind='count',
    metavar='N',
    required=True,
    help=(
        "with --record-golden-trace or --record-session: how many of the input script's "
        'frames to record (a golden trace runs each for 1/60 second; a session runs them at '
        "the game's own pace)"
    ),
)
# record-session's own options (glitchygames/replay/tools/scripted_sessions.py)
CONTROLS_TAIL_OPTION = ToolOption(
    flag='--controls-tail',
    kind='reference',
    metavar='MODULE:NAME',
    help=(
        "with --record-session: key events played after the input script's frames, ending "
        "with the game's own quit control, so the session ends when the game quits (named as "
        "--input-script is); without it the session ends after the script's frames"
    ),
)
POLLED_INPUT_OPTION = ToolOption(
    flag='--polled-input',
    kind='flag',
    help=(
        "with --record-session: the game reads its controls from the frame's polled input "
        "(current_input()), so the session's snapshots show the script's posted input, as a "
        "real player's would"
    ),
    default=False,
)
INPUT_ONLY_PLACEMENTS_OPTION = ToolOption(
    flag='--input-only-placements',
    kind='flag',
    help=(
        "with --record-session: the input script's placements only steer its own input (they "
        'move no sprite), so they may run inside the session; otherwise a session stops '
        "before the script's first placement"
    ),
    default=False,
)
# The command's GAME (children.resolve_game reads it)
GAME_FORMS_TEXT = '; '.join(GAME_FORMS)
GAME_ARGUMENT = ToolOption(
    flag='game',
    kind='game',
    metavar='GAME',
    required=True,
    help=f'the game to run: {GAME_FORMS_TEXT}',
)
# replay-trace's game comes from the recording; --game names it when that game's module no
# longer imports (a moved script)
GAME_OVERRIDE_OPTION = ToolOption(
    flag='--game',
    kind='game',
    metavar='GAME',
    help=(
        "the game to replay with, when the recording's own no longer imports (default: the "
        f"game the recording's header names): {GAME_FORMS_TEXT}"
    ),
)
# verify's and measure's option: which of the recordings to verify or measure (one option for
# both: the controller's note to Task D6)
ONLY_OPTION = ToolOption(
    flag='--only',
    kind='text',
    metavar='TEXT',
    help=(
        'with --verify or --measure: only the recordings whose name (the path relative to the '
        'project, for one inside it) contains TEXT'
    ),
)
# measure's options (glitchygames/replay/tools/measure.py), as scripts/replay_metrics.py's
# measure command described them (help reworded for the game's own revision)
FORCE_OPTION = ToolOption(
    flag='--force',
    kind='flag',
    help='with --measure: measure even what this commit (or --code-tree) already measured',
    default=False,
)
ALLOW_DIRTY_OPTION = ToolOption(
    flag='--allow-dirty',
    kind='flag',
    help=(
        "with --measure: measure despite the game's uncommitted changes or unknown commit (a "
        'trial: its rows say so, and never count as measuring the commit); not with '
        '--skip-dirty'
    ),
    default=False,
)
SKIP_DIRTY_OPTION = ToolOption(
    flag='--skip-dirty',
    kind='flag',
    help=(
        'with --measure: when the game has uncommitted changes or an unknown commit, measure '
        'nothing and succeed; not with --allow-dirty'
    ),
    default=False,
)
CODE_TREE_OPTION = ToolOption(
    flag='--code-tree',
    kind='text',
    metavar='TREE',
    help=(
        'with --measure or --unmeasured: the code measured, as a git tree of what can change '
        'the replays (glitchygames/code_tree.py): the measured run names it, and a recording '
        'measured for it on this machine is skipped (default: judged by the commit)'
    ),
)
ROWS_DIRECTORY_OPTION = ToolOption(
    flag='--rows-directory',
    kind='path',
    metavar='DIRECTORY',
    help=(
        'with --measure or --unmeasured: the rows are row files there (the ledger directory), '
        'written instead of appended to the pending ledger, and read as measured'
    ),
)
PENDING_OPTION = ToolOption(
    flag='--pending',
    kind='path',
    metavar='PATH',
    help=(
        'with --measure, --unmeasured or --clear-published: the pending ledger file (default: '
        "the project's [tool.glitchygames] pending-ledger)"
    ),
)
# The command's verify, measure and unmeasured take the games whose recordings they work on
# (none given: the project's [tool.glitchygames] games); a game working on itself needs none
GAMES_OPTION = ToolOption(
    flag='--game',
    kind='games',
    metavar='GAME',
    help=(
        "a game whose own recordings to work on, given once per game (default: the project's "
        '[tool.glitchygames] games); with PATHs, the one game that replays them (default: the '
        f"game each recording's header names): {GAME_FORMS_TEXT}"
    ),
)

# report's options (glitchygames/replay/tools/report.py), as scripts/recording_report.py's parser
# described them: the same types (any number, any integer) and defaults
THRESHOLD_OPTION = ToolOption(
    flag='--threshold',
    kind='number',
    metavar='PERCENT',
    help='with --report: percent a same-work frame must change by to count as slower or faster',
    default=DEFAULT_THRESHOLD_PERCENT,
)
MINIMUM_MS_OPTION = ToolOption(
    flag='--minimum-ms',
    kind='number',
    metavar='MS',
    help='with --report: milliseconds it must change by too (smaller changes are timer noise)',
    default=DEFAULT_MINIMUM_MS,
)
SPANS_OPTION = ToolOption(
    flag='--spans',
    kind='int',
    metavar='N',
    help='with --report: how many spans each comparison lists',
    default=DEFAULT_SPAN_LIMIT,
)
# performance-pages' option (glitchygames/replay/tools/performance_pages.py): the build a deploy
# publishes, as our docs site's mkdocs hook builds it for gh-deploy
PUBLISHED_OPTION = ToolOption(
    flag='--published',
    kind='flag',
    help=(
        'with --performance-pages: build what a deploy publishes, leaving out rows measured on '
        'uncommitted changes and row files whose code has not landed (default: a local build, '
        'which shows them, labelled)'
    ),
    default=False,
)

TOOLS: tuple[Tool, ...] = (
    Tool(
        name='record-trace',
        help=(
            'record the session (sprites, frame times, input events, random seed) to a '
            'gzip JSON Lines trace for inspection and later replay (default: off)'
        ),
        options=(RANDOM_SEED_OPTION, HEADLESS_OPTION),
        runs_game=True,
        # The game's own run records (GameEngine._start_requested_trace_recording)
        game_handler=None,
        command_handler=record_trace_command,
        value_help='where the recording goes',
        command_arguments=(GAME_ARGUMENT,),
    ),
    Tool(
        name='replay-trace',
        help=(
            'replay a --record-trace recording exactly through the engine, comparing every '
            'frame with it and reporting the first divergence (default: off)'
        ),
        options=(
            REPLAY_FPS_OPTION,
            AUDIT_OPTION,
            COMPARE_PROCESSING_OPTION,
            MAX_PROCESSING_SLOWDOWN_OPTION,
            REPLAY_PAUSE_AT_FRAME_OPTION,
            REBASELINE_OPTION,
            REPLAY_DIGEST_OPTION,
            HEADLESS_OPTION,
            RANDOM_SEED_OPTION,
        ),
        runs_game=True,
        # The game's own run replays (GameEngine._start_requested_replay)
        game_handler=None,
        command_handler=replay_trace_command,
        value_help='the recording to replay',
        command_arguments=(GAME_OVERRIDE_OPTION,),
    ),
    Tool(
        name='record-golden-trace',
        help=(
            "record a golden trace: the game's scene driven headless by a scripted input for a "
            'fixed number of 1/60-second frames, every sprite sampled each frame (default: off)'
        ),
        options=(INPUT_SCRIPT_OPTION, FRAME_COUNT_OPTION, RANDOM_SEED_OPTION, HEADLESS_OPTION),
        runs_game=True,
        # The game runs in the golden-trace harness, in place of its own run
        game_handler=record_golden_trace_on_the_game,
        command_handler=record_golden_trace_command,
        value_help='where the golden trace goes',
        command_arguments=(GAME_ARGUMENT,),
    ),
    Tool(
        name='record-session',
        help=(
            'record a scripted session: the game run for real (its own frame loop and pace) '
            "with --record-trace while a supervisor plays an input script as a player's input, "
            'then an optional controls tail ending with its quit (default: off)'
        ),
        options=(
            INPUT_SCRIPT_OPTION,
            FRAME_COUNT_OPTION,
            CONTROLS_TAIL_OPTION,
            POLLED_INPUT_OPTION,
            INPUT_ONLY_PLACEMENTS_OPTION,
            RANDOM_SEED_OPTION,
            HEADLESS_OPTION,
        ),
        runs_game=True,
        # The game runs in the scripted-session recorder, in place of its own run
        game_handler=record_session_on_the_game,
        command_handler=record_session_command,
        value_help='where the recording goes',
        command_arguments=(GAME_ARGUMENT,),
    ),
    Tool(
        name='verify',
        help=(
            'replay recordings headless, each in a child process, and print one line per '
            "recording saying whether it matched (default: the game's own goldens and bundled "
            f'demos); exits {ExitCode.SUCCESS:d} only when every one matched (or none was '
            f'found), {ExitCode.REPLAY_DIVERGED:d} when the only failures are divergences, '
            "otherwise the first other failure's exit code (default: off)"
        ),
        # --random-seed is listed only to be refused, on both front ends alike (verify.py)
        options=(ONLY_OPTION, RANDOM_SEED_OPTION),
        runs_game=True,
        # The game's recordings are replayed by children; the game itself never runs
        game_handler=verify_on_the_game,
        command_handler=verify_command,
        value_kind='paths',
        value_help=("the recordings to verify (default: the games' own goldens and bundled demos)"),
        command_arguments=(GAMES_OPTION,),
    ),
    Tool(
        name='measure',
        help=(
            "rebaseline recordings headless, each in a child process, measuring every frame's "
            "processing time into the run ledger (default: the game's own goldens and bundled "
            "demos not yet measured for the game's commit on this machine); exits "
            f'{ExitCode.SUCCESS:d} when every one was measured or already was, '
            f"{ExitCode.OPTIONS_REFUSED:d} for a game's uncommitted changes or unknown commit, "
            f'{ExitCode.INTERNAL_ERROR:d} when one could not be measured (default: off)'
        ),
        # --random-seed is listed only to be refused, on both front ends alike (measure.py)
        options=(
            FORCE_OPTION,
            ALLOW_DIRTY_OPTION,
            SKIP_DIRTY_OPTION,
            ONLY_OPTION,
            CODE_TREE_OPTION,
            ROWS_DIRECTORY_OPTION,
            PENDING_OPTION,
            RANDOM_SEED_OPTION,
        ),
        runs_game=True,
        # The recordings are rebaselined by children; the game itself never runs
        game_handler=measure_on_the_game,
        command_handler=measure_command,
        value_kind='paths',
        value_help="the recordings to measure (default: the games' own goldens and bundled demos)",
        command_arguments=(GAMES_OPTION,),
    ),
    Tool(
        name='unmeasured',
        help=(
            'list the recordings --measure would measure, one per line (the summary goes to '
            'standard error); runs no game (default: off)'
        ),
        options=(CODE_TREE_OPTION, ROWS_DIRECTORY_OPTION, PENDING_OPTION),
        runs_game=False,
        game_handler=unmeasured_on_the_game,
        command_handler=unmeasured_command,
        value_kind='flag',
        command_arguments=(GAMES_OPTION,),
    ),
    Tool(
        name='clear-published',
        help=(
            'remove the pending rows the published ledger now holds (after a publish); runs no '
            'game (default: off)'
        ),
        options=(PENDING_OPTION,),
        runs_game=False,
        game_handler=clear_published_on_the_game,
        command_handler=clear_published_command,
        value_kind='flag',
    ),
    Tool(
        name='report',
        help=(
            "print a recording's runs (provenance and summary), how the same work's processing "
            'time changed between adjacent runs, and where its behaviour changed (the frames '
            f'whose content hash differs); exits {ExitCode.SUCCESS:d}, '
            f'{ExitCode.MISSING_INPUT:d} for a missing file or {ExitCode.UNUSABLE_INPUT:d} for '
            'one that is no recording; runs no game (default: off)'
        ),
        options=(THRESHOLD_OPTION, MINIMUM_MS_OPTION, SPANS_OPTION),
        runs_game=False,
        game_handler=report_on_the_game,
        command_handler=report_command,
        value_help='the recording (.jsonl.gz)',
    ),
    Tool(
        name='performance-pages',
        help=(
            "write the project's performance pages into DIRECTORY: its run ledger (row files, "
            'published and pending rows, merged) and one graph page per recording, processing '
            'and frame times by commit; runs no game (default: off)'
        ),
        options=(PUBLISHED_OPTION,),
        runs_game=False,
        game_handler=performance_pages_on_the_game,
        command_handler=performance_pages_command,
        value_metavar='DIRECTORY',
        value_help='where the pages go (created when missing)',
    ),
)
