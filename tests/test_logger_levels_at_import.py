"""Importing any module of the engine or of a member sets no logger's level (BUGS.md #235, #236).

A level set at import outlives the command line's: ``--log-level`` (the engine's
``logging.basicConfig``, ``GameEngine.initialize_arguments``) sets only the root logger's level,
so a module's ``logging.getLogger('game').setLevel(logging.DEBUG)`` made every ``game.*`` logger
log DEBUG in any process that imported it, the test suite included, where pytest kept the records
in memory until the serial Linux CI run was killed at 2 GB. A ``logging.basicConfig`` at import
does the same to the root logger and adds a handler before the engine's own call, which then does
nothing. A logger that emits nothing in a replay (``game.paddle``) escapes the replay guard
(tests/replay/test_replays_log_quietly.py), so this checks the levels themselves.

A fresh interpreter imports every module under the engine's package and each member's import
packages (``glitchygames.logical_names.MEMBER_LAYERS``), one at a time, and after each import
records every change it made: a logger's level (each change, not only the first), the root
logger's level or handlers, and ``logging.disable``. A logger whose name starts with an
installed package that is not the project's (``urllib3``) is a third party's: listed apart,
never blamed on the project module whose import created it. The result goes to a file, not
standard output (a module may print at exit). Modules named ``__main__`` are not imported
(importing one runs its program in some packages). By name only: this file imports no member.
"""

from __future__ import annotations

import json
import os
import sys
from typing import TYPE_CHECKING

from glitchygames.logical_names import MEMBER_LAYERS
from glitchygames.process import OutputCapture, run_command

if TYPE_CHECKING:
    from pathlib import Path

# Importing every module takes several seconds (pygame, FastAPI, numpy)
CHILD_TIMEOUT_SECONDS = 300.0
ENGINE_PACKAGE = 'glitchygames'

# The child: import each module, and after each name what it changed. Arguments: the result
# file, then the packages
PROBE = """\
import importlib
import importlib.util
import json
import logging
import pkgutil
import sys

result_path, *packages = sys.argv[1:]
project_prefixes = set(packages)
root = logging.getLogger()
manager = logging.root.manager


def root_state():
    return (root.level, len(root.handlers), manager.disable)


def project_logger(name):
    first = name.split('.', 1)[0]
    if first in project_prefixes or first == 'game':
        return True
    # A name no installed module has (a project's own logger name) is the project's
    try:
        return importlib.util.find_spec(first) is None
    except (ImportError, ValueError):
        return True


previous_root = root_state()
levels = {}
changes = []
third_party = []
failures = []


def note_changes(module):
    global previous_root
    current_root = root_state()
    if current_root != previous_root:
        level, handlers, disabled = current_root
        changes.append([
            module,
            'root',
            f'{logging.getLevelName(level)} ({handlers} handlers, disable {disabled})',
        ])
        previous_root = current_root
    for name, logger in list(manager.loggerDict.items()):
        if not isinstance(logger, logging.Logger):
            continue
        if logger.level == levels.get(name, logging.NOTSET):
            continue
        levels[name] = logger.level
        change = [module, name, logging.getLevelName(logger.level)]
        (changes if project_logger(name) else third_party).append(change)


for package_name in packages:
    package = importlib.import_module(package_name)
    note_changes(package_name)
    for module in pkgutil.walk_packages(package.__path__, prefix=package_name + '.'):
        if module.name.rsplit('.', 1)[-1] == '__main__':
            continue
        try:
            importlib.import_module(module.name)
        except Exception as error:
            failures.append([module.name, repr(error)])
        note_changes(module.name)
with open(result_path, 'w', encoding='utf-8') as result_file:
    json.dump(
        {'changes': changes, 'third_party': third_party, 'failures': failures}, result_file
    )
"""


def run_probe(
    *, packages: list[str], result_path: Path, environment: dict[str, str] | None = None
) -> dict[str, list[list[str]]]:
    """Import every module of ``packages`` in a fresh interpreter; return what each changed.

    Args:
        packages: Import packages (``glitchygames``, ``paddleslap``).
        result_path: Where the child writes its report.
        environment: The child's environment (this process's when None).

    Returns:
        ``changes``: ``[module, logger, level]`` for each change (``root`` for the root
        logger's level, handlers or ``logging.disable``); ``third_party``: the same for a third
        party's loggers; ``failures``: ``[module, error]`` for each module that did not import.

    """
    completed = run_command(
        command=[sys.executable, '-c', PROBE, str(result_path), *packages],
        environment=os.environ if environment is None else environment,
        timeout_seconds=CHILD_TIMEOUT_SECONDS,
        capture_output=OutputCapture.APART,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(result_path.read_text(encoding='utf-8'))


def test_importing_any_module_sets_no_logger_level(tmp_path):
    """No module of the engine or a member sets a logger's level, or configures the root, at import.

    The level is the command line's (``--log-level``); a module that needs to log only logs.
    """
    report = run_probe(
        packages=[ENGINE_PACKAGE, *MEMBER_LAYERS], result_path=tmp_path / 'report.json'
    )

    assert report['failures'] == []
    assert report['changes'] == [], '\n'.join(
        f'importing {module} set {logger} to {level}' for module, logger, level in report['changes']
    )


def test_the_probe_names_every_change_and_the_module_that_made_it(tmp_path):
    """A planted package: each level change (a second one too), the root, logging.disable."""
    package = tmp_path / 'chatty_package'
    package.mkdir()
    (package / '__init__.py').write_text('', encoding='utf-8')
    (package / 'noisy.py').write_text(
        "import logging\nlogging.getLogger('game').setLevel(logging.INFO)\n"
        'logging.basicConfig(level=logging.DEBUG)\n',
        encoding='utf-8',
    )
    (package / 'quiet.py').write_text(
        "import logging\nlogging.getLogger('game').setLevel(logging.ERROR)\n"
        'logging.disable(logging.INFO)\n',
        encoding='utf-8',
    )
    environment = {**os.environ, 'PYTHONPATH': str(tmp_path)}

    report = run_probe(
        packages=['chatty_package'],
        result_path=tmp_path / 'report.json',
        environment=environment,
    )

    assert report == {
        'changes': [
            ['chatty_package.noisy', 'root', 'DEBUG (1 handlers, disable 0)'],
            ['chatty_package.noisy', 'game', 'INFO'],
            ['chatty_package.quiet', 'root', 'DEBUG (1 handlers, disable 20)'],
            ['chatty_package.quiet', 'game', 'ERROR'],
        ],
        'third_party': [],
        'failures': [],
    }


def test_a_third_partys_logger_is_never_blamed_on_the_project(tmp_path):
    """A logger named after another installed package (here pytest) is listed apart.

    A module that prints at exit does not upset the report either: it goes to a file.
    """
    package = tmp_path / 'importer_package'
    package.mkdir()
    (package / '__init__.py').write_text(
        "import atexit, logging\nlogging.getLogger('pytest.thing').setLevel(logging.DEBUG)\n"
        "atexit.register(print, 'goodbye')\n",
        encoding='utf-8',
    )
    environment = {**os.environ, 'PYTHONPATH': str(tmp_path)}

    report = run_probe(
        packages=['importer_package'],
        result_path=tmp_path / 'report.json',
        environment=environment,
    )

    assert report['changes'] == []
    assert report['third_party'] == [['importer_package', 'pytest.thing', 'DEBUG']]
