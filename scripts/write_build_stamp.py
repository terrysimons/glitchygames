"""Write (or remove) the engine's build stamp, glitchygames/_build_info.json.

``nox -s build-wheel`` and ``build-binary`` run this before building, so a packaged engine
(wheel or PyInstaller binary), which has no git checkout, still knows the commit it was built
from and whether the checkout had uncommitted changes (glitchygames/build_info.py), and run it
with ``--remove`` afterwards, so no stale stamp is left for a later build to pick up.

A stamp already in the checkout is refused, not overwritten: another build is using it (its
``--remove`` would take the stamp from under this one), or a killed build left it behind
(BUGS.md #224.47). ``--remove`` clears a stale one.

``nox -s test`` stamps its installed copy instead (``--into`` its directory): the stamp never
appears in the checkout, so a test run and a build never share one. It runs this with the
session's own python, after installing: ``uv run`` there would sync the session's environment
again (editable), replacing the installed copy being stamped.

The revision is always read from the checkout this script is in (``PACKAGE_DIRECTORY``), not
from the ``glitchygames`` it imports: under the test session's python that is the installed
copy, which has no checkout to read.

Usage:
    uv run python scripts/write_build_stamp.py [--remove | --into DIRECTORY]
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from glitchygames.build_info import BUILD_STAMP_FILE_NAME, write_build_stamp

if TYPE_CHECKING:
    from collections.abc import Sequence

# The engine package in the checkout this script is in (scripts/../src/glitchygames): where the
# revision is read from, and where a build's stamp goes
PACKAGE_DIRECTORY = Path(__file__).resolve().parent.parent / 'src' / 'glitchygames'


def main(arguments: Sequence[str] | None = None) -> int:
    """Write the stamp (or remove it with ``--remove``) and say what was done.

    Args:
        arguments: The command line (None: ``sys.argv[1:]``).

    Returns:
        The exit status: 0, or 1 when a stamp is already in the checkout.

    """
    parser = argparse.ArgumentParser(description='Write or remove the engine build stamp.')
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--remove', action='store_true', help='remove the stamp')
    action.add_argument(
        '--into',
        type=Path,
        metavar='DIRECTORY',
        help="stamp an installed copy of the package (this checkout's revision)",
    )
    options = parser.parse_args(arguments)
    stamp_directory = PACKAGE_DIRECTORY if options.into is None else options.into
    stamp_path = stamp_directory / BUILD_STAMP_FILE_NAME
    if options.remove:
        stamp_path.unlink(missing_ok=True)
        sys.stdout.write(f'Removed {stamp_path}\n')
        return 0
    if options.into is None and stamp_path.exists():
        sys.stderr.write(
            f'{stamp_path} already exists: another build is using it, or a killed build left '
            f'it. Once no build is running, remove it with: '
            f'uv run python scripts/write_build_stamp.py --remove\n'
        )
        return 1
    stamp = write_build_stamp(
        package_directory=PACKAGE_DIRECTORY,
        built_at=datetime.now(tz=UTC).isoformat(),
        stamp_directory=stamp_directory,
    )
    sys.stdout.write(
        f'Wrote {stamp_path}: commit {stamp.commit}, '
        f'uncommitted changes {stamp.uncommitted_changes}\n'
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
