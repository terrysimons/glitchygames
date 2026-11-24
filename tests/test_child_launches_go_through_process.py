"""Every child process outside the tests is started through glitchygames/process.py.

``process.run_command`` and ``run_command_stopped_at_timeout`` hold the child until it is
reaped, however the wait ends (bugs/2026-11-20-process-stop-tests-failed-under-load.md:
``subprocess.run`` answers Ctrl-C with SIGKILL and no wait, and ``glitchygames record-trace``
exited with its game a zombie). A direct ``subprocess.run`` or ``Popen`` elsewhere would bring
that back, so this fails on any call that starts a process (``subprocess``'s, ``os``'s spawns,
forks and execs, ``asyncio``'s subprocesses) in a tracked Python file outside the tests, unless
it is in ALLOWED_LAUNCHES with its reason.

The tests (``tests/``, each member's ``tests/``) start processes as they need to; the AI service
(``services/ai-service/``) is its own project that shares no code with the engine.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path, PurePosixPath

from glitchygames.process import OutputCapture, run_command
from tests.ast_scanning import PROJECT_ROOT, import_bindings, qualified_name

GIT_TIMEOUT_SECONDS = 60
# The modules whose process-starting calls are looked for
WATCHED_MODULES = frozenset({'subprocess', 'os', 'asyncio'})
# The calls that start a process
LAUNCHING_CALLS = frozenset({
    'subprocess.run',
    'subprocess.Popen',
    'subprocess.call',
    'subprocess.check_call',
    'subprocess.check_output',
    'subprocess.getoutput',
    'subprocess.getstatusoutput',
    'os.system',
    'os.popen',
    'os.fork',
    'os.forkpty',
    'os.posix_spawn',
    'os.posix_spawnp',
    'os.spawnl',
    'os.spawnle',
    'os.spawnlp',
    'os.spawnlpe',
    'os.spawnv',
    'os.spawnve',
    'os.spawnvp',
    'os.spawnvpe',
    'os.execl',
    'os.execle',
    'os.execlp',
    'os.execlpe',
    'os.execv',
    'os.execve',
    'os.execvp',
    'os.execvpe',
    'asyncio.create_subprocess_exec',
    'asyncio.create_subprocess_shell',
})
# Where tracked Python files may start processes their own way: the tests, and the AI service
UNSCANNED_GLOBS = ('tests/**', 'src/*/*/tests/**', 'services/**')
# Each launch allowed outside process.py, by file: the calls, and why it is not process.py's
ALLOWED_LAUNCHES: dict[str, tuple[frozenset[str], str]] = {
    'src/glitchygames/process.py': (
        frozenset({'subprocess.run', 'subprocess.Popen'}),
        'the launchers themselves, start_command, and its one ps listing',
    ),
    'ansible/roles/ai_service/files/smoke_test.py': (
        frozenset({'subprocess.run', 'subprocess.Popen'}),
        'copied to a host and run alone, where the engine is not installed',
    ),
    'scripts/ai_behaviour/paired.py': (
        frozenset({'subprocess.Popen'}),
        'a long-lived child it talks to over pipes and stops itself',
    ),
    'scripts/audio_glitch_probe.py': (
        frozenset({'subprocess.run'}),
        'a hand-run probe; to move to run_command',
    ),
    'scripts/build_browser_bundle.py': (
        frozenset({'subprocess.run'}),
        'git and the submodule build script, outside the engine; to move to run_command',
    ),
    'scripts/generate_sbom.py': (
        frozenset({'subprocess.run'}),
        'syft, a third-party tool; to move to run_command',
    ),
    'scripts/measure_on_raspberry_pi.py': (
        frozenset({'subprocess.Popen'}),
        'ssh fed through its standard input',
    ),
}
# A file that starts a process each way the scan must see
LAUNCHING_SOURCE = (
    'import os\n'
    'import subprocess as sp\n'
    'from subprocess import run as run_it\n'
    'sp.Popen(["game"])\n'
    'run_it(["game"])\n'
    'os.system("game")\n'
)


def launches(*, source: str) -> list[tuple[int, str]]:
    """Find every call in a module's source that starts a process.

    Returns:
        Each call's line and qualified name, in the source's order.

    """
    tree = ast.parse(source)
    bindings = import_bindings(tree=tree, watched_modules=WATCHED_MODULES)
    found = [
        (node.lineno, name)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            name := qualified_name(
                node=node.func, bindings=bindings, watched_modules=WATCHED_MODULES
            )
        )
        in LAUNCHING_CALLS
    ]
    return sorted(found)


def scanned_files(*, project_root: Path) -> list[str]:
    """Return every tracked Python file outside UNSCANNED_GLOBS, relative to the repository.

    Returns:
        The paths, POSIX-style.

    """
    completed = run_command(
        command=['git', 'ls-files', '-z', '--', '*.py'],
        environment=os.environ,
        working_directory=project_root,
        capture_output=OutputCapture.APART,
        timeout_seconds=GIT_TIMEOUT_SECONDS,
    )
    names = [name for name in completed.stdout.split('\0') if name]
    return [
        name
        for name in names
        if not any(PurePosixPath(name).full_match(glob) for glob in UNSCANNED_GLOBS)
    ]


def launches_not_allowed(*, project_root: Path, files: list[str]) -> dict[str, list[str]]:
    """Find the launches in ``files`` that ALLOWED_LAUNCHES does not allow.

    Returns:
        Each one as "line: call", by file, for each file holding one.

    """
    found: dict[str, list[str]] = {}
    for name in files:
        allowed, _reason = ALLOWED_LAUNCHES.get(name, (frozenset(), ''))
        source = (project_root / name).read_text(encoding='utf-8')
        refused = [
            f'{line}: {call}' for line, call in launches(source=source) if call not in allowed
        ]
        if refused:
            found[name] = refused
    return found


def test_every_child_process_outside_the_tests_is_started_through_process():
    """Use ``process.run_command`` (or ``run_command_stopped_at_timeout``, ``start_command``)."""
    found = launches_not_allowed(
        project_root=PROJECT_ROOT, files=scanned_files(project_root=PROJECT_ROOT)
    )

    assert found == {}, f'start these through glitchygames.process (file: line: call): {found}'


def test_every_allowed_launch_is_still_there():
    """An allowance whose launch has gone (moved to run_command) is removed, not left open."""
    files = scanned_files(project_root=PROJECT_ROOT)
    found_by_file = {
        name: {call for _line, call in launches(source=(PROJECT_ROOT / name).read_text('utf-8'))}
        for name in ALLOWED_LAUNCHES
        if name in files
    }

    assert {name: calls for name, (calls, _reason) in ALLOWED_LAUNCHES.items()} == found_by_file


def test_a_launch_is_found_however_it_is_imported():
    """Through a module alias, a name imported from the module, and ``os``."""
    assert launches(source=LAUNCHING_SOURCE) == [
        (4, 'subprocess.Popen'),
        (5, 'subprocess.run'),
        (6, 'os.system'),
    ]


def test_a_launch_outside_the_allowances_is_refused_and_one_inside_is_not(tmp_path: Path):
    """A planted launch in a game is refused; the same calls in process.py are allowed."""
    for name in ('src/games/rally/src/rally/game.py', 'src/glitchygames/process.py'):
        path = tmp_path / name
        path.parent.mkdir(parents=True)
        path.write_text(LAUNCHING_SOURCE, encoding='utf-8')

    found = launches_not_allowed(
        project_root=tmp_path,
        files=['src/games/rally/src/rally/game.py', 'src/glitchygames/process.py'],
    )

    assert found == {
        'src/games/rally/src/rally/game.py': [
            '4: subprocess.Popen',
            '5: subprocess.run',
            '6: os.system',
        ],
        'src/glitchygames/process.py': ['6: os.system'],
    }


def test_the_scan_covers_the_scripts_and_skips_the_tests():
    """The scripts and the engine are scanned; the engine's and the members' tests are not."""
    files = scanned_files(project_root=PROJECT_ROOT)

    assert 'scripts/generate_sbom.py' in files
    assert 'src/glitchygames/process.py' in files
    assert 'tests/test_process.py' not in files
    assert not [name for name in files if name.startswith('src/games/paddleslap/tests/')]
