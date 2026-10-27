"""Games run as child processes: finding a game, and starting it with the engine's flags.

Every tool that has to run a game (``glitchygames record-trace``, ``glitchygames replay-trace``,
the replay pytest plugin, the measurement run) starts it as a child process, with the tool's
flag on its command line (``--replay-trace PATH``). The game's ``GameEngine(game=Game)`` adds
those flags to its own command line (glitchygames/replay/tools/registry.py), so the game never
knows how it was started.

Two ways to name the game:

- **By a console script** (``[project.scripts]``): ``game_entry_point`` finds its entry point,
  and ``replay_command`` loads and calls it in the child the way the installed console script
  would. ``recording_console_script`` tells which console script replays a recording under a
  ``fixtures/replays/`` directory; ``console_script_for_game_module`` which of several starts a
  recorded game's module.
- **By what the user typed** (the command's ``GAME``): ``resolve_game`` reads it as a script
  path, an entry point ``MODULE:CALLABLE``, an installed console script or an importable module
  (``GameLaunch``), and ``launch_game`` starts it with the tool's arguments.

A console script is never run as its installed executable (``bin/<script>``). Its entry point
is loaded and called in a ``python -c`` child (``entry_point_command``) instead, which is what
that executable does. It runs on this interpreter (the one whose packages were searched for the
entry point), needs no executable on ``PATH``, and works wherever the metadata is installed:
a non-editable install in nox's sessions, or a stand-in game's dist-info in the engine's tests,
which has no executable at all. The replay pytest plugin has always started games this way.

``replay_recording_headless`` and ``rebaseline_recording_headless`` run a recording's replay
(or rebaseline) headless through a console script; the replay pytest plugin
(glitchygames/testing/replays.py), the bundled demos' test and the measurement run use them.

Moved from glitchygames/testing/replays.py (Part 3, Stage D, Task D1), unchanged in behavior:
that module imports pytest, and the ``glitchygames`` command must not. Importing this module
never imports pytest; it imports pygame (through ``glitchygames.replay``), a required
dependency, but opens no display.
"""

from __future__ import annotations

import dataclasses
import importlib.machinery
import importlib.metadata
import importlib.util
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from glitchygames.bundled_demos import CONSOLE_SCRIPTS_GROUP
from glitchygames.logical_names import module_for_logical_module
from glitchygames.process import OutputCapture, run_command, with_options_appended
from glitchygames.replay.driver import GAME_HEADER_FIELD
from glitchygames.tracing import TraceReader

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from glitchygames.process import CompletedProcess

# A recording is collected from .../fixtures/replays/<console-script>/<name>.jsonl.gz, or from a
# workspace member's <member>/tests/fixtures/replays/<name>.jsonl.gz
REPLAY_FIXTURES_PATH_PARTS = ('fixtures', 'replays')
# The directory a workspace member's fixtures/ is in: <member>/tests/
MEMBER_TESTS_DIRECTORY_NAME = 'tests'
# Kill a replay child that runs longer than this (a headless replay of a few hundred frames
# takes a second or two)
REPLAY_TIMEOUT_SECONDS = 300.0
# The forms GAME may take, in the order resolve_game tries them (named in its errors)
GAME_FORMS = (
    'a script path (contains / or ends in .py)',
    'an entry point MODULE:CALLABLE',
    'an installed console script or an importable module',
)
# A GAME containing either of these is a script path
SCRIPT_PATH_SEPARATOR = '/'
SCRIPT_SUFFIX = '.py'
# A GAME containing this is an entry point MODULE:CALLABLE
ENTRY_POINT_SEPARATOR = ':'
# The module a script's classes are in (python mygame.py): no other process can import it
SCRIPT_MODULE = '__main__'

type GameForm = Literal['script', 'entry-point', 'console-script', 'module']


class UnknownGameError(LookupError):
    """``GAME`` names no game in any of the forms ``resolve_game`` reads (``GAME_FORMS``)."""


@dataclasses.dataclass(frozen=True)
class GameLaunch:
    """How to start a game as a child process.

    Attributes:
        form: Which of the forms ``GAME`` was read as.
        command: The child's command before the tool's arguments (``launch_game`` appends
            them).

    """

    form: GameForm
    command: list[str]


def game_entry_point(*, console_script: str) -> importlib.metadata.EntryPoint:
    """Return a console script's entry point from the installed package metadata.

    Every distribution on ``sys.path`` is searched, in order. ``importlib.metadata.entry_points``
    is not used: it keeps only the first distribution of each name, so stale metadata of the same
    package earlier on ``sys.path`` (an old ``<package>.egg-info`` in a source checkout's root,
    which pytest puts first) would hide the installed package's console scripts.

    Args:
        console_script: The console script's name (``[project.scripts]``), for example
            ``paddleslap``.

    Returns:
        The entry point (``value`` is ``'module:function'``).

    Raises:
        KeyError: If no installed package has a console script of that name.

    """
    for distribution in importlib.metadata.distributions():
        for entry_point in distribution.entry_points.select(
            group=CONSOLE_SCRIPTS_GROUP, name=console_script
        ):
            return entry_point
    raise KeyError(console_script)


def installed_console_scripts() -> list[importlib.metadata.EntryPoint]:
    """Return every installed console script's entry point, each name once (the first found).

    Searched as ``game_entry_point`` searches: every distribution on ``sys.path``, in order.

    Returns:
        The entry points.

    """
    found: dict[str, importlib.metadata.EntryPoint] = {}
    for distribution in importlib.metadata.distributions():
        for entry_point in distribution.entry_points.select(group=CONSOLE_SCRIPTS_GROUP):
            found.setdefault(entry_point.name, entry_point)
    return list(found.values())


def recording_console_script(*, path: Path) -> str:
    """Return the console script that replays a recording under a ``fixtures/replays/`` directory.

    Two layouts: a workspace member's recordings lie directly in
    ``<member>/tests/fixtures/replays/`` and are replayed by the member distribution's console
    script (the member's directory is named after its distribution: ``src/games/mr-muncher``):
    its one (``src/games/brave-adventurer``'s launcher starts whichever of its games the
    recording's header names), or, for a member with a console script per game, the one that
    starts the game the recording's header names (``recorded_games_console_script``); another
    project's (this one's games are all members) lie in
    ``fixtures/replays/<console-script>/``, whose folder names the script.

    Args:
        path: The recording.

    Returns:
        The console script's name.

    Raises:
        KeyError: If a recording directly in ``fixtures/replays/`` is not in a member's
            ``tests/`` (the directory above ``fixtures/`` is not ``tests``: another project's
            layout, whose directory four levels up names no member), the member's distribution
            is not installed or has no console script, its several console scripts do not
            include exactly one starting the recorded game (``recorded_games_console_script``),
            or the folder names no installed console script.

    """
    if path.parent.parts[-len(REPLAY_FIXTURES_PATH_PARTS) :] == REPLAY_FIXTURES_PATH_PARTS:
        tests_directory = path.parent.parent.parent
        if tests_directory.name != MEMBER_TESTS_DIRECTORY_NAME:
            message = (
                f'{path}: a recording directly in {"/".join(REPLAY_FIXTURES_PATH_PARTS)}/ is a '
                f"workspace member's, in <member>/{MEMBER_TESTS_DIRECTORY_NAME}/, but the "
                f'directory above fixtures/ is {tests_directory.name!r}, not '
                f'{MEMBER_TESTS_DIRECTORY_NAME!r}'
            )
            raise KeyError(message)
        distribution_name = tests_directory.parent.name
        try:
            distribution = importlib.metadata.distribution(distribution_name)
        except importlib.metadata.PackageNotFoundError:
            # The member's directory names its distribution; the installer is the project's
            # business, so none is named
            message = (
                f'{path}: looked for a console script of {distribution_name!r} (the directory '
                f'its {MEMBER_TESTS_DIRECTORY_NAME}/ is in names the distribution), but no '
                'distribution of that name is installed'
            )
            raise KeyError(message) from None
        console_scripts = [
            entry_point
            for entry_point in distribution.entry_points
            if entry_point.group == CONSOLE_SCRIPTS_GROUP
        ]
        if not console_scripts:
            message = f'{path}: {distribution_name!r} has no console scripts'
            raise KeyError(message)
        if len(console_scripts) == 1:
            return console_scripts[0].name
        return recorded_games_console_script(
            path=path, distribution_name=distribution_name, entry_points=console_scripts
        )
    try:
        game_entry_point(console_script=path.parent.name)
    except KeyError:
        message = f'{path}: the directory {path.parent.name!r} is not a console script'
        raise KeyError(message) from None
    return path.parent.name


def console_script_for_game_module(
    *, entry_points: Iterable[importlib.metadata.EntryPoint], game_module: str
) -> str:
    """Return the console script among several whose entry point starts a game module.

    A console script starts the game whose module is its entry point's module or inside it:
    ``brave_adventurer:main`` (Brave Adventurer's Classic, before its launcher) starts
    ``brave_adventurer.game``, not ``brave_adventurer_papyrus.game``.

    Args:
        entry_points: The console scripts' entry points (``value`` is ``'module:function'``).
        game_module: The game's module (``brave_adventurer.game``).

    Returns:
        The console script's name.

    Raises:
        KeyError: If none of them, or more than one, starts the game module.

    """
    entry_points = list(entry_points)
    starting = [
        entry_point.name
        for entry_point in entry_points
        if game_module == (module := entry_point.value.partition(':')[0])
        or game_module.startswith(f'{module}.')
    ]
    if len(starting) == 1:
        return starting[0]
    if not starting:
        names = sorted(entry_point.name for entry_point in entry_points)
        message = f'none of {names} starts {game_module}'
        raise KeyError(message)
    message = f'{sorted(starting)} all start {game_module}'
    raise KeyError(message)


def recorded_game_module(*, path: Path) -> str:
    """Return the module holding the game a recording's header names (by logical name).

    Args:
        path: The recording.

    Returns:
        The module today (``module_for_logical_module`` of the header's ``game``).

    Reading the header raises ``OSError`` for a recording that can't be read and a
    ``TraceFormatError`` (a ValueError) for a file that is not a recording.

    Raises:
        KeyError: If the header names no game (a recording made before logical names).

    """
    with TraceReader(path=path) as reader:
        header = reader.header
    recorded_game = header.get(GAME_HEADER_FIELD)
    if not isinstance(recorded_game, str):
        message = (
            f'{path}: no {GAME_HEADER_FIELD!r} in its header (a recording made before logical '
            'names)'
        )
        raise KeyError(message)
    return module_for_logical_module(logical_module=recorded_game.partition(':')[0])


def recorded_games_console_script(
    *, path: Path, distribution_name: str, entry_points: list[importlib.metadata.EntryPoint]
) -> str:
    """Return which of a member's several console scripts replays a recording.

    The recording's header names its game by logical name (``game``:
    ``games.brave_adventurer.game:BraveAdventurerScene``, glitchygames/logical_names.py); the
    module holding that logical module today (``brave_adventurer.game``) chooses the script
    (``console_script_for_game_module``).

    Args:
        path: The recording.
        distribution_name: The member's distribution (for the messages).
        entry_points: The distribution's console scripts' entry points (more than one).

    Returns:
        The console script's name.

    Raises:
        KeyError: If the recording's header cannot be read or names no game, or not exactly
            one of the scripts starts the recorded game.

    """
    try:
        game_module = recorded_game_module(path=path)
    # A TraceFormatError is a ValueError
    except OSError, ValueError:
        message = (
            f"{path}: its header cannot be read to choose among {distribution_name!r}'s "
            f'{len(entry_points)} console scripts'
        )
        raise KeyError(message) from None
    except KeyError as error:
        message = f"{error.args[0]} to choose among {distribution_name!r}'s console scripts by"
        raise KeyError(message) from None
    try:
        return console_script_for_game_module(entry_points=entry_points, game_module=game_module)
    except KeyError as error:
        message = f'{path}: {distribution_name!r}: {error.args[0]}'
        raise KeyError(message) from None


def entry_point_command(*, entry_point: importlib.metadata.EntryPoint) -> list[str]:
    """Build a child command that loads an entry point and calls it, as a console script does.

    The child loads the entry point with ``EntryPoint.load()``, as its installed console script
    does, and calls it. Python places the arguments after ``-c``'s code in the child's
    ``sys.argv[1:]``, where the engine's option parser reads them.

    Args:
        entry_point: The entry point (``value`` is ``'module:callable'``).

    Returns:
        The command, as an argument list, without the game's arguments.

    """
    load_and_call = (
        'from importlib.metadata import EntryPoint; '
        f'EntryPoint(name={entry_point.name!r}, value={entry_point.value!r}, '
        f'group={entry_point.group!r}).load()()'
    )
    return [sys.executable, '-c', load_and_call]


def headless_replay_arguments(*, recording: Path) -> list[str]:
    """Return a game's arguments that replay a recording headless, its log quiet.

    No ``--random-seed``: the replay takes the recording's own, so it compares every frame
    (Stage D's decision 17).

    Args:
        recording: The recording to replay.

    Returns:
        ``--replay-trace``, the recording, ``--headless`` and a quiet log level.

    """
    return ['--replay-trace', str(recording), '--headless', '--log-level', 'warning']


def replay_command(*, entry_point: importlib.metadata.EntryPoint, recording: Path) -> list[str]:
    """Build the child command that replays a recording headless through a game's entry point.

    The child is ``entry_point_command``'s, with ``headless_replay_arguments``.

    Args:
        entry_point: The game's console script entry point.
        recording: The recording to replay.

    Returns:
        The command, as an argument list.

    """
    return [
        *entry_point_command(entry_point=entry_point),
        *headless_replay_arguments(recording=recording),
    ]


def running_game_command() -> list[str]:
    """Return the command that starts this process's game again, without the game's arguments.

    This process's interpreter (``sys.executable``), then what its command line named before the
    game's own arguments (``sys.orig_argv``, whose tail is ``sys.argv[1:]``): a script
    (``game.py``), a module (``-m game``), code (``-c ...``) or an installed console script's
    executable, with any interpreter options before them. A game given a tool flag uses it to
    replay recordings through itself, however it was started, console script or not.

    Returns:
        The command, as an argument list.

    Raises:
        RuntimeError: If this process's arguments are no longer the tail of its command line
            (changed after it started), so where the program ends can't be told.

    """
    game_arguments = sys.argv[1:]
    program_end = len(sys.orig_argv) - len(game_arguments)
    if program_end < 1 or sys.orig_argv[program_end:] != game_arguments:
        message = (
            'cannot tell how this game was started: its arguments are not the end of its '
            f'command line ({sys.orig_argv!r})'
        )
        raise RuntimeError(message)
    return [sys.executable, *sys.orig_argv[1:program_end]]


def replay_recording_headless(*, console_script: str, path: Path) -> CompletedProcess[str]:
    """Replay a recording headless through a game's console script, in a child process.

    The child is ``replay_command``'s, started with ``run_command`` with this process's
    environment (``--headless`` puts it on SDL's dummy drivers). A child still running after
    REPLAY_TIMEOUT_SECONDS is killed, and run_command's ``subprocess.TimeoutExpired`` is raised.

    Args:
        console_script: The game's console script (``[project.scripts]``), for example
            ``paddleslap``.
        path: The recording.

    Returns:
        The finished child: ``returncode`` is the replay's ``ExitCode`` (``SUCCESS`` when every
        frame matched) and ``stdout`` its standard output and error together (the divergence
        report, or why the recording was refused).

    """
    entry_point = game_entry_point(console_script=console_script)
    return run_command(
        command=replay_command(entry_point=entry_point, recording=path),
        environment=os.environ,
        timeout_seconds=REPLAY_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
    )


def rebaseline_recording_headless(
    *,
    console_script: str,
    path: Path,
    new_path: Path,
    game_arguments: Sequence[str] = (),
) -> CompletedProcess[str]:
    """Rebaseline a recording headless through a game's console script, in a child process.

    The child is ``replay_command``'s plus ``--rebaseline NEW`` (glitchygames/replay/rebaseline.py):
    it replays ``path`` on the current code, measuring each frame's processing time, and writes
    the run into ``new_path``. Started and timed out as ``replay_recording_headless`` is.

    Args:
        console_script: The game's console script (``[project.scripts]``).
        path: The recording.
        new_path: Where the rebaselined recording goes (never ``path``: refused).
        game_arguments: More arguments for the game, after the rebaseline's (the game's own,
            which ``--measure`` passes on as verify does; none by default).

    Returns:
        The finished child: ``returncode`` is the rebaseline's ``ExitCode`` and ``stdout`` its
        standard output and error together (the rebaseline's summary line).

    """
    entry_point = game_entry_point(console_script=console_script)
    return run_command(
        command=[
            *with_options_appended(
                arguments=replay_command(entry_point=entry_point, recording=path),
                appended=['--rebaseline', str(new_path)],
            ),
            *game_arguments,
        ],
        environment=os.environ,
        timeout_seconds=REPLAY_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
    )


def module_is_importable(*, module: str, search_directory: Path | None = None) -> bool:
    """Tell whether a module can be imported, without importing it or any package above it.

    The top-level package is looked up with ``importlib.util.find_spec`` (``sys.path`` and its
    finders), then in ``search_directory``; each part below it inside the package found.

    Args:
        module: The module's dotted name (``paddleslap.game``).
        search_directory: A directory to look for the top-level package in as well (the
            project root, which a child started there has on its ``sys.path``), or None.

    Returns:
        True if every part of the name is found (never for ``__main__``, a script's module).

    """
    top_level, *inner_parts = module.split('.')
    if not top_level.isidentifier() or not all(part.isidentifier() for part in inner_parts):
        return False
    # A game started as a script (python mygame.py) records its module as __main__, which names
    # whatever this process was started as (find_spec raises for a __main__ without a spec)
    if top_level == SCRIPT_MODULE:
        return False
    specification = importlib.util.find_spec(top_level)
    if specification is None and search_directory is not None:
        specification = importlib.machinery.PathFinder.find_spec(top_level, [str(search_directory)])
    for part in inner_parts:
        if specification is None or specification.submodule_search_locations is None:
            return False
        specification = importlib.machinery.PathFinder.find_spec(
            part, list(specification.submodule_search_locations)
        )
    return specification is not None


def unknown_game_message(*, game: str, reason: str) -> str:
    """Describe a ``GAME`` that names no game, with every form it may take.

    Args:
        game: What was given.
        reason: Why it is not a game.

    Returns:
        The message.

    """
    forms = '; '.join(GAME_FORMS)
    return f'{game!r} is not a game: {reason}. GAME is one of: {forms}'


def resolve_game(*, game: str, project_root: Path | None = None) -> GameLaunch:
    """Read ``GAME`` as a script path, an entry point, a console script or a module.

    In this order (stage D's "How GAME is resolved"):

    - contains ``/`` or ends in ``.py``: a script path, run as ``python <path>``;
    - contains ``:``: an entry point ``MODULE:CALLABLE``, loaded and called in a ``python -c``
      child (``entry_point_command``), its module importable;
    - a plain name: an installed console script (``game_entry_point``), loaded the same way,
      else an importable module, run as ``python -m <module>``.

    Args:
        game: What the user typed.
        project_root: The directory the child runs in (``--project-root``), where a module
            may be found too (a ``python -m`` child started there imports from it). None: the
            current directory. A relative script path is read from the current directory, as
            the command's other paths are.

    Returns:
        How to start it.

    Raises:
        UnknownGameError: If it names nothing in its form, naming all three forms.

    """
    root = Path.cwd() if project_root is None else project_root
    if SCRIPT_PATH_SEPARATOR in game or game.endswith(SCRIPT_SUFFIX):
        script = Path(game)
        if not script.is_file():
            raise UnknownGameError(unknown_game_message(game=game, reason=f'no script at {script}'))
        return GameLaunch(form='script', command=[sys.executable, str(script.resolve())])
    if ENTRY_POINT_SEPARATOR in game:
        module = game.partition(ENTRY_POINT_SEPARATOR)[0]
        if not module_is_importable(module=module, search_directory=root):
            raise UnknownGameError(
                unknown_game_message(game=game, reason=f'its module {module!r} does not import')
            )
        entry_point = importlib.metadata.EntryPoint(
            name=game, value=game, group=CONSOLE_SCRIPTS_GROUP
        )
        return GameLaunch(form='entry-point', command=entry_point_command(entry_point=entry_point))
    try:
        entry_point = game_entry_point(console_script=game)
    except KeyError:
        pass
    else:
        return GameLaunch(
            form='console-script', command=entry_point_command(entry_point=entry_point)
        )
    if module_is_importable(module=game, search_directory=root):
        return GameLaunch(form='module', command=[sys.executable, '-m', game])
    raise UnknownGameError(
        unknown_game_message(
            game=game, reason='no installed console script or importable module has that name'
        )
    )


def launch_game(
    *,
    launch: GameLaunch,
    arguments: Sequence[str],
    working_directory: Path | None = None,
    capture_output: OutputCapture = OutputCapture.NONE,
) -> CompletedProcess[str]:
    """Start a game as a child process with a tool's arguments, and wait for it to end.

    The child gets this process's environment (the ``glitchygames`` command has hidden pygame's
    banner there, so the child prints none either), and no timeout: a recording lasts as long
    as the player plays.

    Args:
        launch: How to start the game (``resolve_game``).
        arguments: The game's command-line arguments (the tool's flag first).
        working_directory: The child's working directory (None: this process's).
        capture_output: What is captured of its output (``process.OutputCapture``; none: it
            writes to this process's).

    Returns:
        The finished child: ``returncode`` is the game's exit status.

    """
    return run_command(
        command=[*launch.command, *arguments],
        environment=os.environ,
        timeout_seconds=None,
        capture_output=capture_output,
        working_directory=working_directory,
    )
