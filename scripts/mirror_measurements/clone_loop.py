"""A stand-in clone under load: replay one recording headless and uncapped, again and again.

The worst case for the live game beside it (a clone catching up); a real clone idles at the live
edge. Each replay is a child process (a game runs once per process); it runs until stopped
(live_stream_cost stops its whole process group).

Usage:
    uv run python -m scripts.mirror_measurements.clone_loop NAME
"""

from __future__ import annotations

import argparse
import sys

from scripts.mirror_measurements.common import (
    RECORDING_NAMES,
    recording_named,
    replay_with_hook,
    run_measurement,
)

MODULE = 'scripts.mirror_measurements.clone_loop'


def main(arguments: list[str] | None = None) -> int:
    """Replay the recording until stopped, or (``--once``) once in this process.

    Returns:
        0 after one replay, or a failed replay's exit code (the loop never ends otherwise).

    """
    parser = argparse.ArgumentParser(
        description='Replay one recording headless and uncapped, again and again'
    )
    parser.add_argument('name', choices=RECORDING_NAMES)
    parser.add_argument('--once', action='store_true', help=argparse.SUPPRESS)
    options = parser.parse_args(arguments)
    if options.once:
        replay_with_hook(
            recording=recording_named(options.name), on_frame=lambda _frame, _scene, _seconds: None
        )
        return 0
    while True:
        exit_code = run_measurement(module=MODULE, arguments=[options.name, '--once'])
        if exit_code:
            return exit_code


if __name__ == '__main__':
    sys.exit(main())
