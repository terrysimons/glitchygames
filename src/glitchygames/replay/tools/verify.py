"""The ``verify`` tool: replay recordings headless and say, one line each, whether they matched.

Each recording is replayed by the game in a child process (``--replay-trace PATH --headless``,
``children.headless_replay_arguments``), never with a seed of its own, so every replay compares
with its recording (Stage D's decision 17). One line per recording goes to standard output:

    PASS tests/fixtures/replays/rally/serve.jsonl.gz: Replay matched 450 frames (end of recording)
    FAIL tests/fixtures/replays/rally/lob.jsonl.gz: REPLAY_DIVERGED (1): Replay diverged at ...

then ``verify: N of M recordings passed``. A recording inside the project is named by its path
relative to the project, any other (a demo installed in site-packages) by its path. With no
recordings to verify it says so (``verify: no recordings found ...``) and succeeds.

The exit code (``verification_exit_code``):

- ``ExitCode.SUCCESS``: every recording matched, or there was none;
- ``ExitCode.REPLAY_DIVERGED``: some diverged, and nothing else went wrong;
- otherwise the first other failure's own code: ``MISSING_INPUT`` (no such recording),
  ``UNUSABLE_INPUT`` (not a recording, another game's, or settings that can't be read),
  ``OPTIONS_REFUSED`` (its game can't be found), ``INTERNAL_ERROR`` (a replay that crashed
  inside the engine, ran too long, or exited with a status that is no ``ExitCode``), and so on.

A replay that crashes before its engine starts (in the game's own code before
``GameEngine.start()``, where no exit code is mapped) exits with Python's 1, which is
``REPLAY_DIVERGED``'s: it counts as a divergence (the user's ruling, 2026-10-27: "Yes, crashes
count as divergences"). Its line still ends with the exception.

Both front ends find the project the same way (``verify_project_root``): ``--project-root`` when
the command is given it, else the nearest directory at or above the current one whose
``pyproject.toml`` has ``[tool.glitchygames]``, else the nearest with a ``pyproject.toml``
(``settings.find_project_root``: inside a workspace member, the workspace root), else the
current directory. When settings
are read there (no PATHs) and it has no ``pyproject.toml``, they say the defaults are used.

A seed is refused on both front ends (``seed_refusal``), before any replay runs, with
``ExitCode.OPTIONS_REFUSED``: a replay under another seed compares nothing and succeeds (rule 19
of glitchygames/replay/driver.py), so a tampered recording would pass. ``--random-seed`` given to
the tool, among the game's own arguments beside ``--verify``, or after the command's ``--`` is
refused alike (the user's rule: verify always compares).

Both pass the game's other arguments on to every game they start: the command those after a bare
``--``, the game those on its own command line beside ``--verify``
(``registry.tool_free_arguments``).

The two front ends (glitchygames/replay/tools/registry.py):

- **On the game**, ``--verify [PATH ...] [--only TEXT]`` (``verify_on_the_game``) runs from
  ``GameEngine.__init__``, before the engine starts pygame: the game is neither built nor shown.
  It replays each recording by starting itself again (``children.running_game_command``), so a
  game run as a script verifies too. With no PATHs: its own recordings
  (``recordings.game_recordings``) in the project.
- **The command**, ``glitchygames verify [PATH ...] [--only TEXT] [--game GAME ...]``
  (``verify_command``): with no PATHs, each game (``--game``, given once per game, else the
  project's ``[tool.glitchygames] games``) is started as a child with ``--verify`` and verifies
  its own; with PATHs, each is replayed by the game its header names (as ``replay-trace`` finds
  it), or by the one ``--game``. ``--game`` is the command's own: a game verifying itself needs
  none.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, TimeoutExpired, run_command
from glitchygames.replay.tools.children import (
    REPLAY_TIMEOUT_SECONDS,
    UnknownGameError,
    headless_replay_arguments,
    running_game_command,
)
from glitchygames.replay.tools.identity import game_identity
from glitchygames.replay.tools.recordings import game_recordings
from glitchygames.replay.tools.settings import (
    PYPROJECT_FILE_NAME,
    ProjectSettingsError,
    find_project_root,
    load_project_settings,
)
from glitchygames.replay.tools.traces import (
    FORM_DESCRIPTIONS,
    RecordedGameRefusal,
    find_recorded_game,
    project_root,
    refused,
    resolve_named_game,
    run_game_with_tool,
    say,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.process import CompletedProcess
    from glitchygames.replay.tools.registry import Tool
    from glitchygames.replay.tools.settings import ProjectSettings
    from glitchygames.scenes import Scene

# The first word of a recording's line
PASSED = 'PASS'
FAILED = 'FAIL'
# What every line that is not a recording's starts with
SUMMARY_PREFIX = 'verify:'
# How a headless replay's report starts (glitchygames/replay/driver.py ReplayResult.report)
REPLAY_REPORT_PREFIXES = (
    'Replay matched',
    'Replay diverged',
    'Replay ended early',
    'Replay still running',
)
# The option verify refuses (registry.RANDOM_SEED_OPTION's flag: the registry imports this module)
RANDOM_SEED_FLAG = '--random-seed'
# What a recording's line says of a child that printed nothing
NO_OUTPUT = 'no output'

# A recording, and the command that starts the game replaying it (the game's arguments follow),
# or why no game can replay it
type VerifyTarget = tuple[Path, list[str] | RecordedGameRefusal]


def write_line(*, line: str) -> None:
    """Write one line to standard output (the verify run's own; the replays' are captured).

    Args:
        line: The line.

    """
    sys.stdout.write(f'{line}\n')
    sys.stdout.flush()


def recording_name(*, path: Path, project_root: Path) -> str:
    """Return how a recording's line names it.

    Args:
        path: The recording.
        project_root: The project.

    Returns:
        Its path relative to the project, for one inside it; its path otherwise.

    """
    resolved = path.resolve()
    root = project_root.resolve()
    if resolved.is_relative_to(root):
        return resolved.relative_to(root).as_posix()
    return path.as_posix()


def selected(*, paths: Sequence[Path], only: str | None, project_root: Path) -> list[Path]:
    """Return the recordings ``--only TEXT`` keeps: those whose name contains TEXT.

    Args:
        paths: The recordings.
        only: The text, or None to keep every one.
        project_root: The project (names are relative to it, ``recording_name``).

    Returns:
        The recordings kept, in order.

    """
    if only is None:
        return list(paths)
    return [path for path in paths if only in recording_name(path=path, project_root=project_root)]


def replay_outcome(*, finished: CompletedProcess[str]) -> str:
    """Say in a line how a replay child went: its report, else its last words.

    Args:
        finished: The finished child (its standard output and error together in ``stdout``).

    Returns:
        The replay's report line (``Replay matched 450 frames ...``, ``Replay diverged at frame
        N: ...``), else the child's last line (a crash's exception), else ``NO_OUTPUT``.

    """
    lines = [line.strip() for line in (finished.stdout or '').splitlines() if line.strip()]
    for line in lines:
        if line.startswith(REPLAY_REPORT_PREFIXES):
            return line
    if lines:
        return lines[-1]
    return NO_OUTPUT


def verification_exit_code(*, statuses: Sequence[int]) -> ExitCode:
    """Return how a verify run exits, from each recording's (or each game's) exit status.

    Args:
        statuses: The exit statuses, in the order they were verified.

    Returns:
        ``ExitCode.SUCCESS`` when every one succeeded (or there was none);
        ``ExitCode.REPLAY_DIVERGED`` when every failure is a divergence; otherwise the first
        other failure's own code, or ``ExitCode.INTERNAL_ERROR`` for a status that is no
        ``ExitCode`` (a child killed by a signal, or one that exited with a number of its own).

    """
    failures = [status for status in statuses if status != ExitCode.SUCCESS]
    if not failures:
        return ExitCode.SUCCESS
    others = [status for status in failures if status != ExitCode.REPLAY_DIVERGED]
    if not others:
        return ExitCode.REPLAY_DIVERGED
    try:
        return ExitCode(others[0])
    except ValueError:
        return ExitCode.INTERNAL_ERROR


def verify_one(
    *,
    path: Path,
    game: list[str] | RecordedGameRefusal,
    project_root: Path,
    working_directory: Path | None,
    game_arguments: Sequence[str],
) -> int:
    """Replay one recording headless in a child, and write its line.

    Args:
        path: The recording.
        game: The command that starts the game (the replay's arguments follow it), or why no
            game can replay it.
        project_root: The project (for the line's name).
        working_directory: The child's working directory (None: this process's).
        game_arguments: More arguments for the game, after the replay's.

    Returns:
        The recording's exit status: the replay's, the refusal's, or ``ExitCode.INTERNAL_ERROR``
        for a replay still running after ``REPLAY_TIMEOUT_SECONDS`` (it is killed).

    """
    name = recording_name(path=path, project_root=project_root)
    if isinstance(game, RecordedGameRefusal):
        # The refusal's message, without the path it starts with: the line names the recording
        reason = game.reason.removeprefix(f'{path}: ')
        write_line(line=f'{FAILED} {name}: {game.exit_code.describe()}: {reason}')
        return game.exit_code
    try:
        finished = run_command(
            command=[*game, *headless_replay_arguments(recording=path), *game_arguments],
            environment=os.environ,
            timeout_seconds=REPLAY_TIMEOUT_SECONDS,
            capture_output=OutputCapture.TOGETHER,
            working_directory=working_directory,
        )
    except TimeoutExpired:
        write_line(
            line=(
                f'{FAILED} {name}: {ExitCode.INTERNAL_ERROR.describe()}: still replaying after '
                f'{REPLAY_TIMEOUT_SECONDS:g} seconds, so it was stopped'
            )
        )
        return ExitCode.INTERNAL_ERROR
    outcome = replay_outcome(finished=finished)
    if finished.returncode == ExitCode.SUCCESS:
        write_line(line=f'{PASSED} {name}: {outcome}')
    else:
        write_line(
            line=f'{FAILED} {name}: {ExitCode.describe_status(finished.returncode)}: {outcome}'
        )
    return finished.returncode


def verify_recordings(
    *,
    recordings: Sequence[VerifyTarget],
    project_root: Path,
    working_directory: Path | None = None,
    game_arguments: Sequence[str] = (),
) -> ExitCode:
    """Replay each recording headless in a child, one line each, then a summary line.

    Args:
        recordings: The recordings, each with the command that starts its game (or why none
            can replay it), at least one.
        project_root: The project (for the lines' names).
        working_directory: The children's working directory (None: this process's).
        game_arguments: More arguments for each replaying game.

    Returns:
        ``verification_exit_code`` of the recordings' exit statuses.

    """
    statuses = [
        verify_one(
            path=path,
            game=game,
            project_root=project_root,
            working_directory=working_directory,
            game_arguments=game_arguments,
        )
        for path, game in recordings
    ]
    passed = statuses.count(ExitCode.SUCCESS)
    write_line(line=f'{SUMMARY_PREFIX} {passed} of {len(statuses)} recordings passed')
    return verification_exit_code(statuses=statuses)


def no_recordings(*, looked_for: str, only: str | None) -> ExitCode:
    """Say that there are no recordings to verify; that is no failure.

    Args:
        looked_for: What was looked for.
        only: ``--only``'s text, or None.

    Returns:
        ``ExitCode.SUCCESS``.

    """
    kept = '' if only is None else f', or none of them contains {only!r} (--only)'
    write_line(line=f'{SUMMARY_PREFIX} no recordings found ({looked_for}{kept})')
    return ExitCode.SUCCESS


def verify_project_root(*, given: Path | None) -> Path:
    """Return the project a verify run works on, saying so when no project is found.

    Args:
        given: The command's ``--project-root``, or None (always, on the game).

    Returns:
        ``given``; else the project the current directory is in (``find_project_root``: the
        nearest ``pyproject.toml`` with ``[tool.glitchygames]``, else the nearest one); else the
        current directory.

    """
    if given is not None:
        return given
    current = Path.cwd()
    found = find_project_root(start=current)
    return current if found is None else found


def read_settings(*, project_root: Path) -> ProjectSettings:
    """Read the project's settings, saying so when it has no pyproject.toml (the defaults).

    Args:
        project_root: The project (``verify_project_root``'s).

    Returns:
        The settings (``load_project_settings``', which raises ``ProjectSettingsError`` for
        settings that can't be read).

    """
    if not (project_root / PYPROJECT_FILE_NAME).is_file():
        write_line(
            line=(
                f'{SUMMARY_PREFIX} no {PYPROJECT_FILE_NAME} in {project_root}: using the default '
                'settings'
            )
        )
    return load_project_settings(project_root=project_root)


def seed_given(*, arguments: Sequence[str]) -> bool:
    """Tell whether a command line gives ``--random-seed`` (as a game's parser would read it).

    Read by a parser of its own with argparse's abbreviations, so ``--random-seed=7`` and a
    prefix the game would take for it count too (an ambiguous prefix the game would refuse is
    refused here as well).

    Args:
        arguments: The arguments.

    Returns:
        True if a seed is among them.

    """
    parser = argparse.ArgumentParser(add_help=False, exit_on_error=False)
    parser.add_argument(RANDOM_SEED_FLAG)
    try:
        known, _ = parser.parse_known_args(list(arguments))
    except argparse.ArgumentError:
        # --random-seed with no value: still a seed asked for
        return True
    return known.random_seed is not None


def seed_refusal() -> str:
    """Say why verify refuses a seed, and what replays under one.

    Returns:
        The message.

    """
    return (
        'verify always replays each recording under its recorded seed, so that it compares '
        f'every frame: {RANDOM_SEED_FLAG} is refused (to play a recording out under another '
        f'seed: --replay-trace PATH {RANDOM_SEED_FLAG} N)'
    )


def verify_on_the_game(*, options: dict[str, Any], game: type[Scene] | Scene) -> ExitCode:
    """Run ``--verify [PATH ...]`` on a game: replay the recordings through the game itself.

    Runs in place of the game's run (``run_game_flag_tool``, from ``GameEngine.__init__``): the
    game is never built. Each recording is replayed by this game started again
    (``running_game_command``) in the current directory, with the game's arguments other than
    verify's own (``registry.tool_free_arguments``), as the command passes those after ``--``.
    The project is ``verify_project_root``'s.

    Args:
        options: The game's parsed options (``verify``: the PATHs given; ``only``).
        game: The game (its class, or a scene the game passed in).

    Returns:
        ``verification_exit_code``'s, ``ExitCode.SUCCESS`` with no recordings,
        ``ExitCode.UNUSABLE_INPUT`` when the project's settings can't be read (needed only
        with no PATHs), or ``ExitCode.INTERNAL_ERROR`` when this process can't tell how it was
        started (so it can't start itself again).

    """
    # Imported here: the tool table imports this module
    from glitchygames.replay.tools.registry import tool_free_arguments, tool_named

    if options.get('random_seed') is not None:
        return refused(message=f'--verify: {seed_refusal()}', exit_code=ExitCode.OPTIONS_REFUSED)
    root = verify_project_root(given=None)
    only: str | None = options.get('only')
    given: list[str] = options['verify']
    if given:
        paths = [Path(path) for path in given]
        looked_for = f'{len(paths)} given'
    else:
        try:
            settings = read_settings(project_root=root)
        except ProjectSettingsError as error:
            return refused(message=f'--verify: {error}', exit_code=ExitCode.UNUSABLE_INPUT)
        identity = game_identity(game=game)
        paths = [
            recording.path
            for recording in game_recordings(
                identity=identity, settings=settings, project_root=root
            )
        ]
        looked_for = (
            'no console script starts this game, so no golden or demo can be told to be its; '
            'name the recordings to verify'
            if identity.console_script is None
            else (
                f'the goldens of {list(settings.golden_globs)} in {root} that '
                f'{identity.console_script} replays, and the demos in {identity.package}/demos/'
            )
        )
    chosen = selected(paths=paths, only=only, project_root=root)
    if not chosen:
        return no_recordings(looked_for=looked_for, only=only)
    try:
        game_command = running_game_command()
    except RuntimeError as error:
        return refused(message=f'--verify: {error}', exit_code=ExitCode.INTERNAL_ERROR)
    return verify_recordings(
        recordings=[(path, game_command) for path in chosen],
        project_root=root,
        game_arguments=tool_free_arguments(arguments=sys.argv[1:], tool=tool_named(name='verify')),
    )


def verify_named_recordings(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """Run ``glitchygames verify PATH ...``: each recording replayed by its game.

    Its game is the one its header names (``find_recorded_game``, as ``replay-trace`` finds
    it), or the one ``--game``.

    Args:
        tool: The verify tool.
        arguments: The subcommand's parsed arguments.
        game_arguments: The arguments after a bare ``--``, for each replaying game.

    Returns:
        ``verify_recordings``' exit code, ``ExitCode.SUCCESS`` when ``--only`` keeps none, or
        ``ExitCode.OPTIONS_REFUSED`` for more than one ``--game`` or one that names no game.

    """
    root = project_root(arguments=arguments)
    games: list[str] | None = arguments.game
    named_game = None
    if games is not None:
        if len(games) > 1:
            say(
                tool=tool,
                message=(
                    'with PATHs, one --game at most: it names the game that replays them '
                    f'({len(games)} were given)'
                ),
            )
            return ExitCode.OPTIONS_REFUSED
        (game,) = games
        try:
            named_game = resolve_named_game(tool=tool, game=game, arguments=arguments)
        except UnknownGameError:
            return ExitCode.OPTIONS_REFUSED
        say(tool=tool, message=f'replaying with {game} ({FORM_DESCRIPTIONS[named_game.form]})')
    given: list[str] = arguments.verify
    chosen = selected(
        paths=[Path(path).absolute() for path in given], only=arguments.only, project_root=root
    )
    if not chosen:
        return no_recordings(looked_for=f'{len(given)} given', only=arguments.only)
    recordings: list[VerifyTarget] = []
    for path in chosen:
        if named_game is not None:
            recordings.append((path, named_game.command))
            continue
        found = find_recorded_game(recording=path, project_root=root)
        recordings.append((
            path,
            found if isinstance(found, RecordedGameRefusal) else found[1].command,
        ))
    return verify_recordings(
        recordings=recordings,
        project_root=root,
        working_directory=root,
        game_arguments=game_arguments,
    )


def verify_each_game(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """Run ``glitchygames verify``: each game started with ``--verify``, verifying its own.

    The games are ``--game``'s, else the project's ``[tool.glitchygames] games``; each runs in
    the project, with ``--only`` as given, and writes its own lines. When the games come from
    the settings, every golden and bundled demo of the project that none of them replays is a
    failure first, on a ``FAIL`` line naming it and why (``measure.unclaimed_recordings``, as
    ``measure`` fails them): a golden is never silently left out.

    Args:
        tool: The verify tool.
        arguments: The subcommand's parsed arguments.
        game_arguments: The arguments after a bare ``--``, for each game.

    Returns:
        ``verification_exit_code`` of the statuses: the unclaimed recordings'
        (``ExitCode.INTERNAL_ERROR`` each) and the games' (``ExitCode.OPTIONS_REFUSED`` for a
        game that names nothing, after every other game has run); ``ExitCode.SUCCESS`` with no
        games and nothing unclaimed, or ``ExitCode.UNUSABLE_INPUT`` when the project's settings
        can't be read.

    """
    # Imported here: measure imports this module (verify_project_root, seed_given)
    from glitchygames.replay.tools.measure import unclaimed_recordings

    root = project_root(arguments=arguments)
    games: list[str] | None = arguments.game
    statuses: list[int] = []
    if games is None:
        try:
            settings = read_settings(project_root=root)
        except ProjectSettingsError as error:
            say(tool=tool, message=str(error))
            return ExitCode.UNUSABLE_INPUT
        games = list(settings.games)
        for unclaimed in unclaimed_recordings(games=games, settings=settings, project_root=root):
            name = recording_name(path=unclaimed.path, project_root=root)
            if arguments.only is not None and arguments.only not in name:
                continue
            write_line(
                line=f'{FAILED} {name}: {ExitCode.INTERNAL_ERROR.describe()}: {unclaimed.reason}'
            )
            statuses.append(ExitCode.INTERNAL_ERROR)
    if not games:
        write_line(
            line=(
                f'{SUMMARY_PREFIX} no games to verify: the project names none in '
                '[tool.glitchygames] games (or [project.scripts]), and no --game was given'
            )
        )
        return verification_exit_code(statuses=statuses)
    for game in games:
        try:
            launch = resolve_named_game(tool=tool, game=game, arguments=arguments)
        except UnknownGameError:
            statuses.append(ExitCode.OPTIONS_REFUSED)
            continue
        statuses.append(
            run_game_with_tool(
                tool=tool,
                arguments=arguments,
                game_arguments=game_arguments,
                game=game,
                launch=launch,
            )
        )
    return verification_exit_code(statuses=statuses)


def verify_command(*, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]) -> int:
    """Run ``glitchygames verify [PATH ...] [--only TEXT] [--game GAME ...]``.

    Args:
        tool: The verify tool.
        arguments: The subcommand's parsed arguments.
        game_arguments: The arguments after a bare ``--``, for each game started.

    Returns:
        ``verify_named_recordings``' exit code with PATHs, ``verify_each_game``'s without.

    """
    if arguments.random_seed is not None or seed_given(arguments=game_arguments):
        say(tool=tool, message=seed_refusal())
        return ExitCode.OPTIONS_REFUSED
    # One project for everything below, found as the game finds it (verify_project_root)
    arguments.project_root = verify_project_root(given=arguments.project_root)
    if arguments.verify:
        return verify_named_recordings(
            tool=tool, arguments=arguments, game_arguments=game_arguments
        )
    return verify_each_game(tool=tool, arguments=arguments, game_arguments=game_arguments)
