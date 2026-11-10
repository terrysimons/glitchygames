"""A stand-in install of the local AI service, for the tests of what reaches it.

``install`` lays out what a real install holds that a game or client reads: the control script
(``bin/ai-service.sh``), here a real one that records each call and exits as told, and the key
clients send. The real control script is a POSIX shell script (the service is macOS only), and
Windows can't run one (``WinError 193``), so each stand-in has a Python twin doing the same: on
Windows the harness fixture ``stand_in_ai_control_scripts`` runs the twin in its place, through
the engine's one launcher (``glitchygames.process.run_command``), so the code under test runs
unchanged on every platform.
"""

from __future__ import annotations

import stat
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

SERVICE_KEY = 'service-token'
CONTROL_SCRIPT_NAME = 'ai-service.sh'
PYTHON_TWIN_SUFFIX = '.py'


def python_twin(*, control_script: Path) -> Path:
    """Name the Python twin of a stand-in control script.

    Returns:
        The twin's path, beside the script.

    """
    return control_script.with_suffix(PYTHON_TWIN_SUFFIX)


def install(*, root: Path, exit_code: int = 0, waits_for: Path | None = None) -> Path:
    """Lay out an install: a real control script that records its calls, its twin, and the key.

    Args:
        root: Where the install goes.
        exit_code: What the control script exits with.
        waits_for: A file the control script waits to exist before it exits, or None.

    Returns:
        The file the control script records its calls in.

    """
    calls = root / 'control-calls'
    script = root / 'bin' / CONTROL_SCRIPT_NAME
    script.parent.mkdir(parents=True)
    shell_wait = '' if waits_for is None else f'while [ ! -e "{waits_for}" ]; do sleep 0.01; done\n'
    script.write_text(
        f'#!/bin/sh\necho "$1" >> "{calls}"\n{shell_wait}exit {exit_code}\n', encoding='utf-8'
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    python_wait = (
        ''
        if waits_for is None
        else (
            'import os, time\n'
            f'while not os.path.exists({str(waits_for)!r}):\n'
            '    time.sleep(0.01)\n'
        )
    )
    python_twin(control_script=script).write_text(
        'import sys\n'
        f'with open({str(calls)!r}, "a", encoding="utf-8") as calls:\n'
        '    calls.write(sys.argv[1] + "\\n")\n'
        f'{python_wait}'
        f'sys.exit({exit_code})\n',
        encoding='utf-8',
    )
    key = root / 'config' / 'service-api-key'
    key.parent.mkdir(parents=True)
    key.write_text(f'{SERVICE_KEY}\n', encoding='utf-8')
    return calls
