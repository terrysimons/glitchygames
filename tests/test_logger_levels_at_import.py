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
records any logger whose level became set, and the root logger's level and handlers if they
changed, naming the module that did it. Modules named ``__main__`` are not imported (importing
one runs its program in some packages). By name only: this file imports no member.
"""

from __future__ import annotations

import json
import os
import sys

from glitchygames.logical_names import MEMBER_LAYERS
from glitchygames.process import OutputCapture, run_command

# Importing every module takes several seconds (pygame, FastAPI, numpy)
CHILD_TIMEOUT_SECONDS = 300.0
ENGINE_PACKAGE = 'glitchygames'

# The child: import each module, and after each name the loggers whose level it set
PROBE = """\
import importlib
import json
import logging
import pkgutil
import sys

packages = sys.argv[1:]
root = logging.getLogger()
root_state = (root.level, len(root.handlers))
attributed = set()
changes = []
failures = []


def note_changes(module):
    global root_state
    current_root = (root.level, len(root.handlers))
    if current_root != root_state:
        changes.append([
            module,
            'root',
            logging.getLevelName(root.level) + f' ({len(root.handlers)} handlers)',
        ])
        root_state = current_root
    for name, logger in list(logging.root.manager.loggerDict.items()):
        if (
            isinstance(logger, logging.Logger)
            and logger.level != logging.NOTSET
            and name not in attributed
        ):
            attributed.add(name)
            changes.append([module, name, logging.getLevelName(logger.level)])


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
print(json.dumps({'changes': changes, 'failures': failures}))
"""


def import_every_module(*, packages: list[str]) -> dict[str, list[list[str]]]:
    """Import every module of ``packages`` in a fresh interpreter and report the levels set.

    Args:
        packages: Import packages (``glitchygames``, ``paddleslap``).

    Returns:
        ``changes``: ``[module, logger, level]`` for each logger whose level a module set
        (``root`` when the root logger's level or handlers changed); ``failures``:
        ``[module, error]`` for each module that did not import.

    """
    completed = run_command(
        command=[sys.executable, '-c', PROBE, *packages],
        environment=os.environ,
        timeout_seconds=CHILD_TIMEOUT_SECONDS,
        capture_output=OutputCapture.APART,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout.splitlines()[-1])


def test_importing_any_module_sets_no_logger_level():
    """No module of the engine or a member sets a logger's level, or configures the root, at import.

    The level is the command line's (``--log-level``); a module that needs to log only logs.
    """
    report = import_every_module(packages=[ENGINE_PACKAGE, *MEMBER_LAYERS])

    assert report['failures'] == []
    assert report['changes'] == [], '\n'.join(
        f'importing {module} set {logger} to {level}' for module, logger, level in report['changes']
    )


def test_the_probe_names_the_module_that_set_a_level(tmp_path):
    """A planted package whose module sets a level at import is named with the logger and level."""
    package = tmp_path / 'chatty_package'
    package.mkdir()
    (package / '__init__.py').write_text('', encoding='utf-8')
    (package / 'noisy.py').write_text(
        "import logging\nlogging.getLogger('game').setLevel(logging.INFO)\n"
        'logging.basicConfig(level=logging.DEBUG)\n',
        encoding='utf-8',
    )
    environment = {**os.environ, 'PYTHONPATH': str(tmp_path)}

    completed = run_command(
        command=[sys.executable, '-c', PROBE, 'chatty_package'],
        environment=environment,
        timeout_seconds=CHILD_TIMEOUT_SECONDS,
        capture_output=OutputCapture.APART,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout.splitlines()[-1])
    assert report == {
        'changes': [
            ['chatty_package.noisy', 'root', 'DEBUG (1 handlers)'],
            ['chatty_package.noisy', 'game', 'INFO'],
        ],
        'failures': [],
    }
