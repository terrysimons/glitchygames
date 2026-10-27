"""A game the engine has never seen: every tool, both front ends, all three GAME forms.

The proof of Stage D's goal (the user, 2026-10-26: "A game we've never seen should be able to be
recorded, replayed, etc..."). A stand-in game (tests/stand_in_games.py) lives in its own project
in ``tmp_path``: its own git repository, its package under ``src/``, a launcher script, an input
script module, its golden recording, and a local bare repository standing in for where its
ledger is published. Its distribution is "installed" as an editable install is: a dist-info
holding its console script, and a launcher executable for that console script, outside the
project.

Every tool in ``TOOLS`` runs on it, in child processes started in the project, with nothing from
this repository on their path (only the installed engine): through the game's own flag
(``<game> --<tool>``) and through the command (``glitchygames <tool>``), with the game named in
each of the three ``GAME`` forms (its script path, its ``MODULE:main`` and its console script).
The whole grid runs twice: in a project with a ``[tool.glitchygames]`` table naming every
setting away from its default, and in one with no table at all (a player's own project, on the
defaults). Each case checks the tool's exit status, exactly which files in the project it wrote
or changed (nothing else), that the rows and recordings it wrote name the stand-in repository's
commit, and that no child imported anything of this repository (``scripts``, ``tests`` or a
workspace member). The seed rules (decision 17's seven rows) get one representative case each:
tests/replay/tools/test_random_seed.py has the full grid.

A meta-test walks ``TOOLS``: a tool without a case here, on either front end, fails it.
"""

from __future__ import annotations

import dataclasses
import gzip
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from glitchygames.exit_codes import ExitCode
from glitchygames.logical_names import LAYERS, MEMBER_LAYERS
from glitchygames.process import OutputCapture, run_command
from glitchygames.recording_metrics import LedgerOrigin, LedgerRow, ledger_text, read_ledger_file
from glitchygames.replay.tools.performance_pages import graph_page_name
from glitchygames.replay.tools.registry import TOOLS
from glitchygames.replay.tools.settings import (
    GITIGNORE_FILE_NAME,
    LOCAL_DIRECTORY_GITIGNORE,
    LOCAL_DIRECTORY_NAME,
    ensure_local_directory,
)
from glitchygames.tracing import read_trace_result
from tests.ledger_repositories import git
from tests.stand_in_games import (
    STAND_IN_GAME_FRAMES,
    stand_in_game_source,
    write_stand_in_distribution,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from glitchygames.process import CompletedProcess

# The stand-in game: its package, its distribution's one console script and its one scene
PACKAGE = 'stand_in_rally'
CONSOLE_SCRIPT = 'stand-in-rally'
SCENE_NAME = 'StandInRallyScene'
# The logical name its recordings give its scene: a plain module name (no layer: it is no member)
LOGICAL_NAME = f'{PACKAGE}:{SCENE_NAME}'
# The project's launcher script (``python run_rally.py``) and its input-script module
LAUNCH_SCRIPT = 'run_rally.py'
INPUTS_MODULE = 'rally_inputs'
# The three GAME forms, as the command is given each (children.GAME_FORMS), and how the command
# says it read each (traces.FORM_DESCRIPTIONS)
SCRIPT_FORM = 'script'
ENTRY_POINT_FORM = 'entry-point'
CONSOLE_SCRIPT_FORM = 'console-script'
GAME_FORMS = {
    SCRIPT_FORM: LAUNCH_SCRIPT,
    ENTRY_POINT_FORM: f'{PACKAGE}:main',
    CONSOLE_SCRIPT_FORM: CONSOLE_SCRIPT,
}
FORM_DESCRIPTIONS = {
    SCRIPT_FORM: 'a script',
    ENTRY_POINT_FORM: 'an entry point',
    CONSOLE_SCRIPT_FORM: 'an installed console script',
}
# A command given no game: verify, measure and unmeasured take the project's games
# ([tool.glitchygames] games, else its [project.scripts]), replay-trace the recording's (its
# header's module, started by the console script that starts it)
UNNAMED_GAME = 'unnamed'
# The two front ends
FLAG = 'flag'
COMMAND = 'command'

# The input scripts (glitchygames.replay.tools.golden_traces), as the harness's and the session
# recorder's own tests write theirs (tests/replay/tools/test_golden_trace_harness.py
# STAND_IN_INPUTS_SOURCE, test_scripted_sessions.py STAND_IN_INPUTS_SOURCE): the golden trace's
# places a nudge on the mover before frame NUDGE_FRAME; the session's presses and releases a key
# the game ignores, and its controls tail presses Q, which ends the game (the base scene quits on Q)
NUDGE_FRAME = 5
NUDGE_PIXELS = 7
INPUTS_SOURCE = f'''\
"""The stand-in project's input scripts (tests/replay/tools/test_an_unseen_game.py)."""

import pygame

from glitchygames.replay.tools.golden_traces import InputScript, press, release


def nudge_mover(scene):
    """Move the mover down."""
    scene.mover.rect.y += {NUDGE_PIXELS}


def rally_script():
    """Return the golden trace's input script: one nudge."""
    script = InputScript()
    script.place({NUDGE_FRAME}, nudge_mover)
    return script


def session_script():
    """Return the session's input script: the right arrow, pressed then released."""
    script = InputScript()
    script.at(2, press(pygame.K_RIGHT))
    script.at(5, release(pygame.K_RIGHT))
    return script


def quit_tail():
    """Return the session's controls tail: Q, which quits the game."""
    tail = InputScript()
    tail.at(2, press(pygame.K_q))
    tail.at(4, release(pygame.K_q))
    return tail
'''
GOLDEN_TRACE_FRAMES = 12
SESSION_FRAMES = 8
# The project's launcher: what an unseen project's README says to run
LAUNCH_SCRIPT_SOURCE = f'"""Run the stand-in rally."""\n\nfrom {PACKAGE} import main\n\nmain()\n'
# The console script's launcher executable, as an installer writes one (pip's template)
LAUNCHER_SOURCE = f"""\
#!{sys.executable}
import sys

from {PACKAGE} import main

if __name__ == '__main__':
    sys.exit(main())
"""

# Where the tools write in each project (none of it matches a golden glob)
OUTPUT_DIRECTORY = 'out'
# The published ledger: a branch of a local bare repository, fetched as a remote's
PUBLISHED_REMOTE = 'published'
PUBLISHED_BRANCH = 'pages'
PUBLISHED_PATH = 'ledger.jsonl'
# A seed given to a recording, and another given to a replay in place of the recorded one
GIVEN_SEED = 41
OTHER_SEED = 7
# A child of the stand-in game ends in seconds; a hung one is killed after this long
CHILD_TIMEOUT_SECONDS = 120.0
# What the children must never import: this repository's scripts and tests, and its members
# (by their import packages, and the layer directories an editable install leaves importable)
FORBIDDEN_IMPORTS = frozenset({'scripts', 'tests', *LAYERS, *MEMBER_LAYERS})
# The environment variables the import watch reads
IMPORT_LOG_VARIABLE = 'GLITCHYGAMES_UNSEEN_GAME_IMPORT_LOG'
FORBIDDEN_IMPORTS_VARIABLE = 'GLITCHYGAMES_UNSEEN_GAME_FORBIDDEN_IMPORTS'
# The import watch: a sitecustomize every child (and its children) loads at start-up, which
# writes each forbidden top-level module it sees imported to the log
IMPORT_WATCH_SOURCE = f"""\
'''Log every import of this repository's code (tests/replay/tools/test_an_unseen_game.py).'''

import os
import sys

_LOG = os.environ[{IMPORT_LOG_VARIABLE!r}]
_FORBIDDEN = frozenset(os.environ[{FORBIDDEN_IMPORTS_VARIABLE!r}].split(','))


def _watch(event, arguments):
    if event == 'import' and arguments[0].partition('.')[0] in _FORBIDDEN:
        with open(_LOG, 'a', encoding='utf-8') as log:
            log.write(f'{{arguments[0]}} in {{sys.argv}}\\n')


sys.addaudithook(_watch)
"""


@dataclasses.dataclass(frozen=True)
class Layout:
    """Where one kind of project keeps its goldens and ledgers.

    Attributes:
        name: The test id.
        tool_settings: Its ``[tool.glitchygames]`` table, or ``''`` for none.
        golden: Its golden recording, relative to the project.
        pending: Its pending ledger, relative to the project.
        publishes: Whether it publishes its ledger (``published-ledger``).
        pages_ledger: The ledger file performance-pages writes.
        local_directory: Whether its pending ledger is in the git-ignored ``.glitchygames/``.

    """

    name: str
    tool_settings: str
    golden: str
    pending: str
    publishes: bool
    pages_ledger: str
    local_directory: bool


# A project naming every setting the tools read away from its default
WITH_SETTINGS = Layout(
    name='with-settings',
    tool_settings=(
        '\n[tool.glitchygames]\n'
        f'games = [{CONSOLE_SCRIPT!r}]\n'
        "golden-globs = ['recordings/**/*.jsonl.gz']\n"
        "ledger-directory = 'metrics/rows'\n"
        "pending-ledger = 'metrics/pending.jsonl'\n"
        f"published-ledger = '{PUBLISHED_REMOTE}/{PUBLISHED_BRANCH}:{PUBLISHED_PATH}'\n"
        "landed-ref = 'published/main'\n"
        "measured-paths = ['src', 'recordings']\n"
    ),
    golden=f'recordings/{CONSOLE_SCRIPT}/golden.jsonl.gz',
    pending='metrics/pending.jsonl',
    publishes=True,
    pages_ledger=PUBLISHED_PATH,
    local_directory=False,
)
# A player's project with no tool.glitchygames table: every tool runs on the defaults that
# ProjectSettings gives (glitchygames/replay/tools/settings.py)
ON_THE_DEFAULTS = Layout(
    name='no-settings',
    tool_settings='',
    golden=f'tests/fixtures/replays/{CONSOLE_SCRIPT}/golden.jsonl.gz',
    pending=f'{LOCAL_DIRECTORY_NAME}/pending-ledger.jsonl',
    publishes=False,
    pages_ledger='replay-ledger.jsonl',
    local_directory=True,
)


@dataclasses.dataclass(frozen=True)
class Template:
    """A stand-in project built once per layout, copied into each test.

    Attributes:
        layout: Its layout.
        project: The project (a git repository).
        install_directory: Where its distribution's metadata is (a ``sys.path`` entry).
        launcher: Its console script's launcher executable.
        import_watch_directory: Where the import watch's ``sitecustomize`` is.
        game_commit: The commit that added the game.
        golden_commit: The commit that added its golden (recorded on ``game_commit``).
        head_commit: Its HEAD, the commit the tools run on (after the published row's).
        published_row: The ledger row it published (measured on ``golden_commit``).

    """

    layout: Layout
    project: Path
    install_directory: Path
    launcher: Path
    import_watch_directory: Path
    game_commit: str
    golden_commit: str
    head_commit: str
    published_row: LedgerRow


@dataclasses.dataclass(frozen=True)
class World:
    """One test's copy of a template project, and the environment its children run in.

    Attributes:
        template: The template it was copied from.
        project: The copy.
        environment: The children's environment: the installed engine, the stand-in's
            distribution and package, the import watch, and nothing of this repository.
        import_log: Where the import watch writes (outside the project).

    """

    template: Template
    project: Path
    environment: dict[str, str]
    import_log: Path

    @property
    def layout(self) -> Layout:
        """The project's layout."""
        return self.template.layout

    @property
    def stand_in_commits(self) -> frozenset[str]:
        """Every commit of the stand-in repository's history."""
        return frozenset({
            self.template.game_commit,
            self.template.golden_commit,
            self.template.head_commit,
        })


def game_command(*, form: str, launcher: Path) -> list[str]:
    """Return how a player starts the stand-in game in one of the three forms.

    Args:
        form: The form: its script, its ``MODULE:main``, or its installed console script.
        launcher: The console script's launcher executable.

    Returns:
        The command line, without the game's arguments.

    """
    if form == SCRIPT_FORM:
        return [sys.executable, LAUNCH_SCRIPT]
    if form == ENTRY_POINT_FORM:
        return [sys.executable, '-c', f'from {PACKAGE} import main; main()']
    # Windows runs a console script through an .exe wrapper no test writes: there, the
    # launcher runs through the interpreter, as the wrapper does
    if sys.platform == 'win32':
        return [sys.executable, str(launcher)]
    return [str(launcher)]


def glitchygames_command() -> str:
    """Return the installed ``glitchygames`` console script, beside this interpreter.

    Returns:
        Its path.

    """
    found = shutil.which('glitchygames', path=str(Path(sys.executable).parent))
    assert found is not None, f'no glitchygames console script beside {sys.executable}'
    return found


def child_environment(
    *, project: Path, install_directory: Path, import_watch_directory: Path, import_log: Path
) -> dict[str, str]:
    """Return the environment the children run in: nothing of this repository on their path.

    ``PYTHONPATH`` holds only the import watch, the stand-in's distribution metadata and its
    project's ``src/`` (an editable install's path); this process's own ``PYTHONPATH`` is
    dropped. No bytecode is written, so ``__pycache__`` never shows up as a written file.

    Returns:
        The environment.

    """
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in {'PYTHONPATH', 'PYTHONSTARTUP'}
    }
    environment['PYTHONPATH'] = os.pathsep.join(
        str(directory) for directory in (import_watch_directory, install_directory, project / 'src')
    )
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    environment[IMPORT_LOG_VARIABLE] = str(import_log)
    environment[FORBIDDEN_IMPORTS_VARIABLE] = ','.join(sorted(FORBIDDEN_IMPORTS))
    return environment


def run_child(
    *, command: list[str], environment: dict[str, str], project: Path
) -> CompletedProcess[str]:
    """Run a child in the project, its output captured apart.

    Returns:
        The finished child.

    """
    return run_command(
        command=command,
        environment=environment,
        timeout_seconds=CHILD_TIMEOUT_SECONDS,
        capture_output=OutputCapture.APART,
        working_directory=project,
    )


def recording_header(*, path: Path) -> dict[str, object]:
    """Return a recording's header (its first line).

    Returns:
        The header.

    """
    with gzip.open(path, 'rt', encoding='utf-8') as recording:
        return json.loads(recording.readline())


def newest_game_commit(*, header: dict[str, object]) -> str:
    """Return the game's commit of a recording's newest run.

    Returns:
        ``measurement_runs[0].game_source_revision.commit``.

    """
    runs = header['measurement_runs']
    assert isinstance(runs, list)
    newest = runs[0]
    assert isinstance(newest, dict)
    return newest['game_source_revision']['commit']


def write_project(*, project: Path, layout: Layout) -> None:
    """Write the stand-in project's files: its game, launcher, input scripts and pyproject."""
    package_directory = project / 'src' / PACKAGE
    package_directory.mkdir(parents=True)
    (package_directory / '__init__.py').write_text(
        stand_in_game_source(
            package=PACKAGE,
            scene_name=SCENE_NAME,
            frames_before_quit=STAND_IN_GAME_FRAMES,
            layer=None,
        ),
        encoding='utf-8',
    )
    (project / LAUNCH_SCRIPT).write_text(LAUNCH_SCRIPT_SOURCE, encoding='utf-8')
    (project / f'{INPUTS_MODULE}.py').write_text(INPUTS_SOURCE, encoding='utf-8')
    (project / 'pyproject.toml').write_text(
        f'[project]\nname = {CONSOLE_SCRIPT!r}\nversion = "1.0.0"\n\n'
        f'[project.scripts]\n{CONSOLE_SCRIPT} = "{PACKAGE}:main"\n{layout.tool_settings}',
        encoding='utf-8',
    )


def install_stand_in(*, root: Path) -> tuple[Path, Path]:
    """Install the stand-in's distribution: its metadata, and its console script's launcher.

    Returns:
        The install directory (a ``sys.path`` entry) and the launcher.

    """
    install_directory = root / 'site-packages'
    write_stand_in_distribution(
        directory=install_directory,
        distribution=CONSOLE_SCRIPT,
        console_scripts={CONSOLE_SCRIPT: f'{PACKAGE}:main'},
    )
    launcher = root / 'bin' / CONSOLE_SCRIPT
    launcher.parent.mkdir()
    launcher.write_text(LAUNCHER_SOURCE, encoding='utf-8')
    launcher.chmod(0o755)
    return install_directory, launcher


def commit_all(*, project: Path, message: str) -> str:
    """Commit everything in the project.

    Returns:
        The new commit.

    """
    git(repository=project, arguments=['add', '--all'])
    git(repository=project, arguments=['commit', '--quiet', '-m', message])
    return git(repository=project, arguments=['rev-parse', 'HEAD']).strip()


def publish_ledger(*, root: Path, project: Path, rows: list[LedgerRow]) -> None:
    """Publish a ledger to a local bare repository, and fetch it into the project as a remote.

    Args:
        root: Where the bare repository and the publisher's checkout go.
        project: The project (its remote ``published`` is the bare repository).
        rows: The published ledger's rows.

    """
    published = root / 'published.git'
    git(repository=root, arguments=['init', '--quiet', '--bare', str(published)])
    publisher = root / 'publisher'
    publisher.mkdir()
    git(repository=publisher, arguments=['init', '--quiet', '--initial-branch', PUBLISHED_BRANCH])
    (publisher / PUBLISHED_PATH).write_text(ledger_text(rows=rows), encoding='utf-8')
    git(repository=publisher, arguments=['add', PUBLISHED_PATH])
    git(repository=publisher, arguments=['commit', '--quiet', '-m', 'publish'])
    git(repository=publisher, arguments=['push', '--quiet', str(published), PUBLISHED_BRANCH])
    git(repository=project, arguments=['remote', 'add', PUBLISHED_REMOTE, str(published)])
    git(repository=project, arguments=['fetch', '--quiet', PUBLISHED_REMOTE])


def build_template(*, root: Path, layout: Layout) -> Template:
    """Build a stand-in project: its game, a golden of it, and a published row.

    1. The game is committed.
    2. Its console script records a live run (``--record-trace``): the golden, committed.
    3. Its console script measures the golden into a ledger outside the project; that row is
       published, and the project fetches the published branch.
    4. One more commit, so the tools run on a commit the published row does not measure.

    Returns:
        The template.

    """
    project = root / 'project'
    write_project(project=project, layout=layout)
    install_directory, launcher = install_stand_in(root=root)
    import_watch_directory = root / 'import-watch'
    import_watch_directory.mkdir()
    (import_watch_directory / 'sitecustomize.py').write_text(IMPORT_WATCH_SOURCE, encoding='utf-8')
    import_log = root / 'imports.log'
    environment = child_environment(
        project=project,
        install_directory=install_directory,
        import_watch_directory=import_watch_directory,
        import_log=import_log,
    )
    launch = game_command(form=CONSOLE_SCRIPT_FORM, launcher=launcher)
    git(repository=project, arguments=['init', '--quiet', '--initial-branch', 'main'])
    game_commit = commit_all(project=project, message='The stand-in rally')

    recorded = run_child(
        command=[*launch, '--log-level', 'error', '--headless', '--record-trace', layout.golden],
        environment=environment,
        project=project,
    )
    assert recorded.returncode == ExitCode.SUCCESS, recorded.stderr
    golden_commit = commit_all(project=project, message='A golden')

    published_rows = root / 'published-rows.jsonl'
    measured = run_child(
        command=[*launch, '--measure', '--pending', str(published_rows)],
        environment=environment,
        project=project,
    )
    assert measured.returncode == ExitCode.SUCCESS, measured.stderr
    (published_row,) = read_ledger_file(path=published_rows).rows
    assert published_row.commit == golden_commit
    publish_ledger(root=root, project=project, rows=[published_row])
    (project / 'README').write_text('The stand-in rally.\n', encoding='utf-8')
    head_commit = commit_all(project=project, message='A README')

    assert not git(repository=project, arguments=['status', '--porcelain', '--untracked-files=all'])
    assert not import_log.exists(), import_log.read_text(encoding='utf-8')
    return Template(
        layout=layout,
        project=project,
        install_directory=install_directory,
        launcher=launcher,
        import_watch_directory=import_watch_directory,
        game_commit=game_commit,
        golden_commit=golden_commit,
        head_commit=head_commit,
        published_row=published_row,
    )


@pytest.fixture(scope='module', params=[WITH_SETTINGS, ON_THE_DEFAULTS], ids=lambda it: it.name)
def template(request, tmp_path_factory) -> Template:
    """A stand-in project in one layout, built once per module (and per xdist worker).

    Returns:
        The template.

    """
    layout: Layout = request.param
    return build_template(root=tmp_path_factory.mktemp(f'unseen-{layout.name}'), layout=layout)


@pytest.fixture
def world(template, tmp_path) -> World:
    """This test's own copy of the template project (its git history included).

    Returns:
        The world.

    """
    project = tmp_path / 'project'
    shutil.copytree(template.project, project, symlinks=True)
    import_log = tmp_path / 'imports.log'
    return World(
        template=template,
        project=project,
        environment=child_environment(
            project=project,
            install_directory=template.install_directory,
            import_watch_directory=template.import_watch_directory,
            import_log=import_log,
        ),
        import_log=import_log,
    )


def project_files(*, project: Path) -> dict[str, str]:
    """Return every file in the project but its ``.git``, with a digest of its bytes.

    Returns:
        Relative POSIX path -> SHA-256.

    """
    return {
        path.relative_to(project).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(project.rglob('*'))
        if path.is_file() and path.relative_to(project).parts[0] != '.git'
    }


def written_files(*, before: dict[str, str], after: dict[str, str]) -> set[str]:
    """Return the files written (added or changed) or removed between two listings.

    Returns:
        Their relative paths.

    """
    return {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}


@dataclasses.dataclass(frozen=True)
class Run:
    """A tool's run, and what it left in the project.

    Attributes:
        status: The exit status.
        output: Its standard output.
        errors: Its standard error.
        written: The files it added, changed or removed in the project.

    """

    status: int
    output: str
    errors: str
    written: set[str]


@dataclasses.dataclass(frozen=True)
class Scenario:
    """One way a tool is used: its arguments, what it is expected to do, and its checks.

    Attributes:
        name: The test id (the tool's name, or the tool's name and its variant).
        tool: The tool's name in ``TOOLS``.
        values: The tool's value (``--<tool> VALUE``, the subcommand's positional), per project.
        options: The tool's options, the same on both front ends.
        game_on_the_command: How the command is given the game: ``'positional'``
            (``GAME``), ``'option'`` (``--game GAME``) or ``None`` (it takes none).
        expected_written: The files it writes or changes, per project.
        check: More checks on the run, per project.
        prepare: Files written before it runs (not counted as its own).
        command_starts: The GAME forms the command starts the game in, saying so ("running
            GAME (form)"); a form not listed is read in place, the game never started.

    """

    name: str
    tool: str
    values: Callable[[World], list[str]]
    options: tuple[str, ...]
    game_on_the_command: str | None
    expected_written: Callable[[World], set[str]]
    check: Callable[[World, Run], None]
    prepare: Callable[[World], None] = lambda _world: None
    command_starts: frozenset[str] = frozenset(GAME_FORMS)


def no_values(_world: World) -> list[str]:
    """The tool takes no value."""
    return []


def nothing_written(_world: World) -> set[str]:
    """The tool writes nothing."""
    return set()


def output_path(name: str) -> str:
    """Return a path under the project's output directory.

    Returns:
        ``out/<name>``.

    """
    return f'{OUTPUT_DIRECTORY}/{name}'


RECORDED_TRACE = output_path('trace.jsonl.gz')
REBASELINED = output_path('rebaselined.jsonl.gz')
GOLDEN_TRACE = output_path('golden-trace.jsonl.gz')
SESSION = output_path('session.jsonl.gz')
PAGES = output_path('pages')


def check_recording(world: World, run: Run, *, path: str, frames: int) -> dict[str, object]:
    """Check a recording the game wrote: its game, its frames, and its run's commit.

    Returns:
        Its trace.

    """
    assert run.status == ExitCode.SUCCESS, run.errors
    trace = read_trace_result(path=world.project / path).trace
    assert trace['game'] == LOGICAL_NAME
    assert len(trace['frames']) == frames
    assert newest_game_commit(header=recording_header(path=world.project / path)) == (
        world.template.head_commit
    )
    return trace


def check_record_trace(world: World, run: Run) -> None:
    """The game's own run is recorded until it quits itself, on the stand-in's HEAD."""
    trace = check_recording(world, run, path=RECORDED_TRACE, frames=STAND_IN_GAME_FRAMES)
    assert isinstance(trace['random_seed'], int)


def check_replay(world: World, run: Run) -> None:
    """The golden replays and matches every frame."""
    assert run.status == ExitCode.SUCCESS, run.errors
    assert f'Replay matched {STAND_IN_GAME_FRAMES} frames' in run.output, run.output


def check_rebaseline(world: World, run: Run) -> None:
    """The golden is replayed into NEW, whose newest run names the stand-in's HEAD."""
    check_recording(world, run, path=REBASELINED, frames=STAND_IN_GAME_FRAMES)
    golden_header = recording_header(path=world.project / world.layout.golden)
    new_header = recording_header(path=world.project / REBASELINED)
    assert new_header['random_seed'] == golden_header['random_seed']


def check_audit(world: World, run: Run) -> None:
    """Two fresh replays both match the recording and each other."""
    assert run.status == ExitCode.SUCCESS, run.errors
    assert run.output.count(f'Replay matched {STAND_IN_GAME_FRAMES} frames') == 2, run.output


def check_golden_trace(world: World, run: Run) -> None:
    """The harness records the input script's frames, its nudge showing from NUDGE_FRAME on."""
    assert run.status == ExitCode.SUCCESS, run.errors
    trace = read_trace_result(path=world.project / GOLDEN_TRACE).trace
    assert trace['game'] == LOGICAL_NAME
    rows = [frame['sprites'][0]['rect'][1] for frame in trace['frames']]
    assert rows == [0] * NUDGE_FRAME + [NUDGE_PIXELS] * (GOLDEN_TRACE_FRAMES - NUDGE_FRAME)


def check_session(world: World, run: Run) -> None:
    """The scripted session ends when its controls tail quits the game, on the stand-in's HEAD."""
    assert run.status == ExitCode.SUCCESS, run.errors
    trace = read_trace_result(path=world.project / SESSION).trace
    assert trace['game'] == LOGICAL_NAME
    # The script's frames, then the tail's until its Q quits the game: fewer than the game's
    # own STAND_IN_GAME_FRAMES, so the tail is what ended it
    frame_count = len(trace['frames'])
    assert SESSION_FRAMES < frame_count < STAND_IN_GAME_FRAMES, frame_count
    assert newest_game_commit(header=recording_header(path=world.project / SESSION)) == (
        world.template.head_commit
    )


def check_verify(world: World, run: Run) -> None:
    """The game's own golden is found from the project's settings (or defaults) and passes."""
    assert run.status == ExitCode.SUCCESS, run.output + run.errors
    assert f'PASS {world.layout.golden}: Replay matched' in run.output, run.output
    assert 'verify: 1 of 1 recordings passed' in run.output, run.output


def check_measure(world: World, run: Run) -> None:
    """The golden is measured into the project's pending ledger, naming the stand-in's HEAD."""
    assert run.status == ExitCode.SUCCESS, run.output + run.errors
    rows = read_ledger_file(path=world.project / world.layout.pending).rows
    (row,) = [row for row in rows if row.origin == LedgerOrigin.REPLAY_METRICS]
    assert row.recording == world.layout.golden
    assert row.console_script == CONSOLE_SCRIPT
    assert row.commit == world.template.head_commit
    assert row.run.game_source_revision is not None
    assert row.run.game_source_revision.commit == world.template.head_commit
    assert not row.allowed_uncommitted_changes
    if world.layout.local_directory:
        assert (world.project / LOCAL_DIRECTORY_NAME / GITIGNORE_FILE_NAME).read_text(
            encoding='utf-8'
        ) == LOCAL_DIRECTORY_GITIGNORE


def measured_files(world: World) -> set[str]:
    """The pending ledger, and the git-ignore of the local directory it is in on the defaults.

    Returns:
        The files measure writes.

    """
    if world.layout.local_directory:
        return {world.layout.pending, f'{LOCAL_DIRECTORY_NAME}/{GITIGNORE_FILE_NAME}'}
    return {world.layout.pending}


def check_unmeasured(world: World, run: Run) -> None:
    """The golden is listed as not measured at the stand-in's HEAD (one line on stdout)."""
    assert run.status == ExitCode.SUCCESS, run.output + run.errors
    assert world.layout.golden in run.output.splitlines(), run.output
    assert '1 of 1 recording not measured' in run.errors, run.errors


def unpublished_row(world: World) -> LedgerRow:
    """Return a row measured on the golden's commit after the publish: pending, unpublished.

    Returns:
        The row.

    """
    published = world.template.published_row
    return published.model_copy(
        update={'run': published.run.model_copy(update={'measured_at': 'unpublished'})}
    )


def write_pending(world: World, rows: list[LedgerRow]) -> None:
    """Write the project's pending ledger, as an earlier measurement would have."""
    pending = world.project / world.layout.pending
    if world.layout.local_directory:
        ensure_local_directory(directory=pending.parent)
    pending.parent.mkdir(parents=True, exist_ok=True)
    pending.write_text(ledger_text(rows=rows), encoding='utf-8')


def pend_the_published_and_an_unpublished_row(world: World) -> None:
    """The pending ledger holds the published row and one measured after the publish."""
    write_pending(world, [world.template.published_row, unpublished_row(world)])


def cleared_files(world: World) -> set[str]:
    """The pending ledger, when the project publishes (on the defaults nothing is published).

    Returns:
        The files clear-published changes.

    """
    return {world.layout.pending} if world.layout.publishes else set()


def check_clear_published(world: World, run: Run) -> None:
    """The published row leaves the pending ledger; nothing does where nothing is published."""
    assert run.status == ExitCode.SUCCESS, run.output + run.errors
    rows = read_ledger_file(path=world.project / world.layout.pending).rows
    if world.layout.publishes:
        assert rows == (unpublished_row(world),)
        assert '1 published row removed' in run.output, run.output
    else:
        assert rows == (world.template.published_row, unpublished_row(world))


def check_report(world: World, run: Run) -> None:
    """The golden's one run is reported, naming the commit it was recorded on."""
    assert run.status == ExitCode.SUCCESS, run.output + run.errors
    assert f'{world.layout.golden}: {STAND_IN_GAME_FRAMES} frames, 1 runs' in run.output
    assert f'run 0: {world.template.game_commit[:7]},' in run.output, run.output


def pend_an_unpublished_row(world: World) -> None:
    """The pending ledger holds one row measured after the publish."""
    write_pending(world, [unpublished_row(world)])


def page_files(world: World) -> set[str]:
    """The merged ledger and the golden's graph page.

    Returns:
        The files performance-pages writes.

    """
    page = graph_page_name(recording=world.layout.golden, console_script=CONSOLE_SCRIPT)
    return {f'{PAGES}/{world.layout.pages_ledger}', f'{PAGES}/{page}'}


def check_performance_pages(world: World, run: Run) -> None:
    """The pages graph the pending row, and the published one where the project publishes."""
    assert run.status == ExitCode.SUCCESS, run.output + run.errors
    rows = read_ledger_file(path=world.project / PAGES / world.layout.pages_ledger).rows
    expected = [unpublished_row(world)]
    if world.layout.publishes:
        expected.insert(0, world.template.published_row)
    assert sorted(row.run.measured_at for row in rows) == sorted(
        row.run.measured_at for row in expected
    )
    assert {row.commit for row in rows} == {world.template.golden_commit}


SCENARIOS = (
    Scenario(
        name='record-trace',
        tool='record-trace',
        values=lambda _world: [RECORDED_TRACE],
        options=('--headless',),
        game_on_the_command='positional',
        expected_written=lambda _world: {RECORDED_TRACE},
        check=check_record_trace,
    ),
    Scenario(
        name='replay-trace',
        tool='replay-trace',
        values=lambda world: [world.layout.golden],
        options=('--headless',),
        game_on_the_command='option',
        expected_written=nothing_written,
        check=check_replay,
    ),
    Scenario(
        name='replay-trace-rebaseline',
        tool='replay-trace',
        values=lambda world: [world.layout.golden],
        options=('--headless', '--rebaseline', REBASELINED),
        game_on_the_command='option',
        expected_written=lambda _world: {REBASELINED},
        check=check_rebaseline,
    ),
    Scenario(
        name='replay-trace-audit',
        tool='replay-trace',
        values=lambda world: [world.layout.golden],
        options=('--audit',),
        game_on_the_command='option',
        expected_written=nothing_written,
        check=check_audit,
    ),
    Scenario(
        name='record-golden-trace',
        tool='record-golden-trace',
        values=lambda _world: [GOLDEN_TRACE],
        options=(
            '--input-script',
            f'{INPUTS_MODULE}:rally_script',
            '--frame-count',
            str(GOLDEN_TRACE_FRAMES),
            '--headless',
        ),
        game_on_the_command='positional',
        expected_written=lambda _world: {GOLDEN_TRACE},
        check=check_golden_trace,
    ),
    Scenario(
        name='record-session',
        tool='record-session',
        values=lambda _world: [SESSION],
        options=(
            '--input-script',
            f'{INPUTS_MODULE}:session_script',
            '--frame-count',
            str(SESSION_FRAMES),
            '--controls-tail',
            f'{INPUTS_MODULE}:quit_tail',
            '--headless',
        ),
        game_on_the_command='positional',
        expected_written=lambda _world: {SESSION},
        check=check_session,
    ),
    Scenario(
        name='verify',
        tool='verify',
        values=no_values,
        options=(),
        game_on_the_command='option',
        expected_written=nothing_written,
        check=check_verify,
    ),
    Scenario(
        name='measure',
        tool='measure',
        values=no_values,
        options=(),
        game_on_the_command='option',
        expected_written=measured_files,
        check=check_measure,
    ),
    Scenario(
        name='unmeasured',
        tool='unmeasured',
        values=no_values,
        options=(),
        game_on_the_command='option',
        expected_written=nothing_written,
        check=check_unmeasured,
        # A console script's recordings are listed from its entry point without starting it
        # (measure.unmeasured_command); a game named another way lists them in a child
        command_starts=frozenset({SCRIPT_FORM, ENTRY_POINT_FORM}),
    ),
    Scenario(
        name='clear-published',
        tool='clear-published',
        values=no_values,
        options=(),
        game_on_the_command=None,
        expected_written=cleared_files,
        check=check_clear_published,
        prepare=pend_the_published_and_an_unpublished_row,
    ),
    Scenario(
        name='report',
        tool='report',
        values=lambda world: [world.layout.golden],
        options=(),
        game_on_the_command=None,
        expected_written=nothing_written,
        check=check_report,
    ),
    Scenario(
        name='performance-pages',
        tool='performance-pages',
        values=lambda _world: [PAGES],
        options=(),
        game_on_the_command=None,
        expected_written=page_files,
        check=check_performance_pages,
        prepare=pend_an_unpublished_row,
    ),
)


@dataclasses.dataclass(frozen=True)
class Case:
    """A scenario through one front end, with the game named in one form.

    Attributes:
        scenario: The scenario.
        front_end: ``FLAG`` (``<game> --<tool>``) or ``COMMAND`` (``glitchygames <tool>``).
        form: The GAME form; ``UNNAMED_GAME`` for a command that finds the game itself; None
            for a command that takes no game.

    """

    scenario: Scenario
    front_end: str
    form: str | None

    @property
    def id(self) -> str:
        """The test id: ``<scenario>-<front end>[-<form>]``."""
        parts = (self.scenario.name, self.front_end, self.form)
        return '-'.join(part for part in parts if part is not None)


def every_case() -> list[Case]:
    """Return each scenario through each front end, in each GAME form that front end takes.

    The game flag is always given to the game, started in each form; the command names the game
    in each form only when the tool takes one (record-trace's ``GAME``, verify's ``--game``).

    Returns:
        The cases.

    """
    cases: list[Case] = []
    for scenario in SCENARIOS:
        cases.extend(Case(scenario=scenario, front_end=FLAG, form=form) for form in GAME_FORMS)
        if scenario.game_on_the_command is None:
            cases.append(Case(scenario=scenario, front_end=COMMAND, form=None))
            continue
        cases.extend(Case(scenario=scenario, front_end=COMMAND, form=form) for form in GAME_FORMS)
        if scenario.game_on_the_command == 'option':
            cases.append(Case(scenario=scenario, front_end=COMMAND, form=UNNAMED_GAME))
    return cases


CASES = every_case()


def command_line(*, case: Case, world: World) -> list[str]:
    """Return the case's command line.

    Returns:
        ``<game> --<tool> VALUE OPTIONS`` (the flag), or ``glitchygames <tool> [GAME] VALUE
        OPTIONS [--game GAME]`` (the command).

    """
    scenario = case.scenario
    values = scenario.values(world)
    if case.front_end == FLAG:
        assert case.form is not None
        return [
            *game_command(form=case.form, launcher=world.template.launcher),
            f'--{scenario.tool}',
            *values,
            *scenario.options,
        ]
    game = [] if case.form in {None, UNNAMED_GAME} else [GAME_FORMS[case.form]]
    if scenario.game_on_the_command == 'positional':
        return [glitchygames_command(), scenario.tool, *game, *values, *scenario.options]
    named = ['--game', *game] if game else []
    return [glitchygames_command(), scenario.tool, *values, *scenario.options, *named]


def run_case(*, case: Case, world: World) -> Run:
    """Prepare the project, run the case in it, and list what it wrote.

    Returns:
        The run.

    """
    case.scenario.prepare(world)
    before = project_files(project=world.project)
    completed = run_child(
        command=command_line(case=case, world=world),
        environment=world.environment,
        project=world.project,
    )
    return Run(
        status=completed.returncode,
        output=completed.stdout or '',
        errors=completed.stderr or '',
        written=written_files(before=before, after=project_files(project=world.project)),
    )


def assert_nothing_of_this_repository_was_imported(*, world: World) -> None:
    """No child imported this repository's scripts, tests or members (the import watch's log)."""
    imported = world.import_log.read_text(encoding='utf-8') if world.import_log.exists() else ''
    assert not imported, imported


@pytest.mark.parametrize('case', CASES, ids=[case.id for case in CASES])
def test_every_tool_runs_an_unseen_game(case, world):
    """Each tool, through each front end and GAME form, in a project with and without settings.

    Checked for each: the exit status and the tool's own checks (its recording, rows or
    output, and the stand-in repository's commit wherever a row or run names one), exactly the
    files it wrote in the project, the form the command read GAME as, and that no child
    imported anything of this repository.
    """
    run = run_case(case=case, world=world)

    case.scenario.check(world, run)
    assert run.written == case.scenario.expected_written(world), run.output + run.errors
    if case.front_end == COMMAND and case.form is not None:
        # The game a command finds itself is the project's, or the recording's: its console script
        form = CONSOLE_SCRIPT_FORM if case.form == UNNAMED_GAME else case.form
        form_line = f'running {GAME_FORMS[form]} ({FORM_DESCRIPTIONS[form]})'
        if form in case.scenario.command_starts:
            assert form_line in run.errors, run.errors
        else:
            assert 'running' not in run.errors, run.errors
    assert_nothing_of_this_repository_was_imported(world=world)


def test_every_tool_has_a_case_on_both_front_ends():
    """Walk ``TOOLS``: a tool without a case here, on either front end, is named."""
    covered = {(case.scenario.tool, case.front_end) for case in CASES}
    missing = [
        f'{tool.name} ({front_end})'
        for tool in TOOLS
        for front_end in (FLAG, COMMAND)
        if (tool.name, front_end) not in covered
    ]

    assert missing == [], f'tools without an unseen-game case: {missing}'


def test_every_game_taking_command_names_the_game_in_all_three_forms():
    """A tool whose command takes a game has a case for each GAME form on both front ends."""
    for scenario in SCENARIOS:
        flag_forms = {
            case.form for case in CASES if case.scenario is scenario and case.front_end == FLAG
        }
        command_forms = {
            case.form for case in CASES if case.scenario is scenario and case.front_end == COMMAND
        }
        assert flag_forms == set(GAME_FORMS), scenario.name
        expected = {
            None: {None},
            'positional': set(GAME_FORMS),
            'option': {*GAME_FORMS, UNNAMED_GAME},
        }[scenario.game_on_the_command]
        assert command_forms == expected, scenario.name


def test_replay_trace_is_exercised_with_rebaseline_and_audit():
    """``--rebaseline`` and ``--audit`` are replay-trace's options: each has its own scenario."""
    replay_options = {
        option
        for scenario in SCENARIOS
        if scenario.tool == 'replay-trace'
        for option in scenario.options
    }

    assert {'--rebaseline', '--audit'} <= replay_options


def golden_seed(world: World) -> int:
    """Return the seed the golden was recorded under (rolled: none was given).

    Returns:
        Its header's ``random_seed``.

    """
    seed = recording_header(path=world.project / world.layout.golden)['random_seed']
    assert isinstance(seed, int)
    return seed


@dataclasses.dataclass(frozen=True)
class SeedRow:
    """One row of the seed rule (decision 17), run once, through one front end and GAME form.

    Attributes:
        name: The test id.
        front_end: The front end it runs through.
        form: The GAME form it names the game in.
        tool: The tool.
        arguments: The tool's value and options, given the world (a replay's seed is the
            golden's, read from it).
        expected_status: Its exit status.
        expected_written: The files it writes in the project.
        check: More checks on the run.

    """

    name: str
    front_end: str
    form: str
    tool: str
    arguments: Callable[[World], tuple[str, ...]]
    expected_status: ExitCode
    expected_written: frozenset[str]
    check: Callable[[World, Run], None]

    def case(self, *, world: World) -> Case:
        """Return the row as a case of the grid's runner.

        Returns:
            The case.

        """
        scenario = Scenario(
            name=self.name,
            tool=self.tool,
            values=no_values,
            options=self.arguments(world),
            game_on_the_command='option' if self.tool == 'replay-trace' else 'positional',
            expected_written=lambda _world: set(self.expected_written),
            check=self.check,
        )
        return Case(scenario=scenario, front_end=self.front_end, form=self.form)


def check_a_rolled_seed_is_logged_and_recorded(world: World, run: Run) -> None:
    """Row 1: no seed given, one is rolled, logged, and named in the recording."""
    seed = recording_header(path=world.project / RECORDED_TRACE)['random_seed']
    assert isinstance(seed, int)
    assert f'Random seed {seed} (rolled)' in run.errors, run.errors


def check_the_given_seed_is_recorded(world: World, _run: Run) -> None:
    """Row 2: the given seed is the recording's."""
    assert recording_header(path=world.project / RECORDED_TRACE)['random_seed'] == GIVEN_SEED


def check_the_replay_compared_and_matched(_world: World, run: Run) -> None:
    """Rows 3 and 4: the replay ran under the recording's own seed and matched every frame."""
    assert f'Replay matched {STAND_IN_GAME_FRAMES} frames' in run.output, run.output
    assert 'Nothing was recorded' not in run.output


def check_another_seed_plays_out_and_records_nothing(_world: World, run: Run) -> None:
    """Row 5: another seed plays the inputs out without comparing, and says nothing was written."""
    assert 'Nothing was recorded' in run.output, run.output


def check_the_rebaseline_keeps_the_recordings_seed(world: World, _run: Run) -> None:
    """Row 6: NEW is recorded under OLD's seed."""
    new_seed = recording_header(path=world.project / REBASELINED)['random_seed']
    assert new_seed == golden_seed(world)


def check_the_rebaseline_records_the_given_seed(world: World, _run: Run) -> None:
    """Row 7: NEW is recorded under the given seed (OLD is untouched: nothing else written)."""
    new_header = recording_header(path=world.project / REBASELINED)
    assert new_header['random_seed'] == GIVEN_SEED
    options = new_header['options']
    assert isinstance(options, dict)
    assert options['random_seed'] == GIVEN_SEED


def check_the_audit_is_refused(_world: World, run: Run) -> None:
    """An audit under another seed is refused before anything runs."""
    assert 'Replay matched' not in run.output


SEED_ROWS = (
    SeedRow(
        name='1-record-without-a-seed-rolls-one',
        front_end=FLAG,
        form=SCRIPT_FORM,
        tool='record-trace',
        arguments=lambda _world: (RECORDED_TRACE, '--headless', '--log-level', 'info'),
        expected_status=ExitCode.SUCCESS,
        expected_written=frozenset({RECORDED_TRACE}),
        check=check_a_rolled_seed_is_logged_and_recorded,
    ),
    SeedRow(
        name='2-record-with-a-seed-uses-it',
        front_end=COMMAND,
        form=ENTRY_POINT_FORM,
        tool='record-trace',
        arguments=lambda _world: (RECORDED_TRACE, '--headless', '--random-seed', str(GIVEN_SEED)),
        expected_status=ExitCode.SUCCESS,
        expected_written=frozenset({RECORDED_TRACE}),
        check=check_the_given_seed_is_recorded,
    ),
    SeedRow(
        name='3-replay-without-a-seed-uses-the-recordings',
        front_end=FLAG,
        form=CONSOLE_SCRIPT_FORM,
        tool='replay-trace',
        arguments=lambda world: (world.layout.golden, '--headless'),
        expected_status=ExitCode.SUCCESS,
        expected_written=frozenset(),
        check=check_the_replay_compared_and_matched,
    ),
    SeedRow(
        name='4-replay-with-the-recordings-seed-compares',
        front_end=COMMAND,
        form=SCRIPT_FORM,
        tool='replay-trace',
        arguments=lambda world: (
            world.layout.golden,
            '--headless',
            '--random-seed',
            str(golden_seed(world)),
        ),
        expected_status=ExitCode.SUCCESS,
        expected_written=frozenset(),
        check=check_the_replay_compared_and_matched,
    ),
    SeedRow(
        name='5-replay-with-another-seed-writes-nothing',
        front_end=FLAG,
        form=ENTRY_POINT_FORM,
        tool='replay-trace',
        arguments=lambda world: (
            world.layout.golden,
            '--headless',
            '--random-seed',
            str(OTHER_SEED),
        ),
        expected_status=ExitCode.SUCCESS,
        expected_written=frozenset(),
        check=check_another_seed_plays_out_and_records_nothing,
    ),
    SeedRow(
        name='6-rebaseline-without-a-seed-keeps-the-recordings',
        front_end=COMMAND,
        form=CONSOLE_SCRIPT_FORM,
        tool='replay-trace',
        arguments=lambda world: (world.layout.golden, '--headless', '--rebaseline', REBASELINED),
        expected_status=ExitCode.SUCCESS,
        expected_written=frozenset({REBASELINED}),
        check=check_the_rebaseline_keeps_the_recordings_seed,
    ),
    SeedRow(
        name='7-rebaseline-with-a-seed-records-it',
        front_end=FLAG,
        form=SCRIPT_FORM,
        tool='replay-trace',
        arguments=lambda world: (
            world.layout.golden,
            '--headless',
            '--rebaseline',
            REBASELINED,
            '--random-seed',
            str(GIVEN_SEED),
        ),
        expected_status=ExitCode.SUCCESS,
        expected_written=frozenset({REBASELINED}),
        check=check_the_rebaseline_records_the_given_seed,
    ),
    SeedRow(
        name='audit-with-another-seed-is-refused',
        front_end=COMMAND,
        form=ENTRY_POINT_FORM,
        tool='replay-trace',
        arguments=lambda world: (world.layout.golden, '--audit', '--random-seed', str(OTHER_SEED)),
        expected_status=ExitCode.OPTIONS_REFUSED,
        expected_written=frozenset(),
        check=check_the_audit_is_refused,
    ),
)


# The seed rule does not depend on the project's settings: one layout is enough
@pytest.mark.parametrize('template', [WITH_SETTINGS], ids=lambda it: it.name, indirect=True)
@pytest.mark.parametrize('row', SEED_ROWS, ids=[row.name for row in SEED_ROWS])
def test_the_seed_rule_holds_for_an_unseen_game(row, world):
    """Each row of the seed rule once, on the unseen game (the full grid: test_random_seed.py)."""
    case = row.case(world=world)

    run = run_case(case=case, world=world)

    assert run.status == row.expected_status, run.output + run.errors
    assert run.written == set(row.expected_written), run.output + run.errors
    row.check(world, run)
    assert_nothing_of_this_repository_was_imported(world=world)


# The import watch is checked on one layout: it does not depend on the project's settings
@pytest.mark.parametrize('template', [WITH_SETTINGS], ids=lambda it: it.name, indirect=True)
def test_the_import_watch_sees_a_child_reach_for_this_repository(world):
    """A child that imports a member, or tries to import scripts/, is in the watch's log.

    Without this, a watch that saw nothing would pass every case above. A member is importable
    in the children (this environment installs the workspace's members); scripts/ is not, and
    even the failed attempt is logged.
    """
    member = next(iter(MEMBER_LAYERS))
    reaching = run_child(
        command=[
            sys.executable,
            '-c',
            f'import {member}\ntry:\n    import scripts\nexcept ImportError:\n    pass\n',
        ],
        environment=world.environment,
        project=world.project,
    )

    assert reaching.returncode == ExitCode.SUCCESS, reaching.stderr
    logged = [
        line.split(' ')[0] for line in world.import_log.read_text(encoding='utf-8').splitlines()
    ]
    assert member in logged
    assert 'scripts' in logged
