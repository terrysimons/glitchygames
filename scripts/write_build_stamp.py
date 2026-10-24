"""Write (or remove) the engine's build stamp, glitchygames/_build_info.json.

``nox -s build-wheel`` and ``build-binary`` run this before building, so a packaged engine
(wheel or PyInstaller binary), which has no git checkout, still knows the commit it was built
from and whether the checkout had uncommitted changes (glitchygames/build_info.py), and run it
with ``--remove`` afterwards, so no stale stamp is left for a later build to pick up.

Usage:
    uv run python scripts/write_build_stamp.py [--remove]
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from glitchygames.build_info import BUILD_STAMP_FILE_NAME, PACKAGE_DIRECTORY, write_build_stamp

if TYPE_CHECKING:
    from collections.abc import Sequence


def main(arguments: Sequence[str] | None = None) -> int:
    """Write the stamp (or remove it with ``--remove``) and say what was done.

    Args:
        arguments: The command line (None: ``sys.argv[1:]``).

    Returns:
        The exit status (0).

    """
    parser = argparse.ArgumentParser(description='Write or remove the engine build stamp.')
    parser.add_argument('--remove', action='store_true', help='remove the stamp')
    options = parser.parse_args(arguments)
    stamp_path = PACKAGE_DIRECTORY / BUILD_STAMP_FILE_NAME
    if options.remove:
        stamp_path.unlink(missing_ok=True)
        sys.stdout.write(f'Removed {stamp_path}\n')
        return 0
    stamp = write_build_stamp(
        package_directory=PACKAGE_DIRECTORY, built_at=datetime.now(tz=UTC).isoformat()
    )
    sys.stdout.write(
        f'Wrote {stamp_path}: commit {stamp.commit}, '
        f'uncommitted changes {stamp.uncommitted_changes}\n'
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
