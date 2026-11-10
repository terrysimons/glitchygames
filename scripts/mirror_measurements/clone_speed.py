"""How fast a clone replays each recording, and how far behind the live game it would stay.

Each run is a child process of this interpreter (as a game would start its clone), which replays
the recording headless and unpaced and times each frame's end; the parent passes its spawn time,
so the start-up counts. The lag model: the live game reaches frame i at the sum of its recorded
dt (starting as the clone's process does, since the clone starts with the game); the clone can't
run frame i before the live game has finished it, so
``clone_end[i] = max(clone_end[i-1], live_end[i]) + clone_cost[i]`` and the lag is
``clone_end - live_end``.

Usage:
    uv run python -m scripts.mirror_measurements.clone_speed --output DIR [--repeats 3]
        [--only NAME ...]
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from scripts.mirror_measurements.common import (
    RECORDING_NAMES,
    in_milliseconds,
    percentiles,
    recorded_frame_seconds,
    recording_named,
    replay_with_hook,
    run_measurement,
)

if TYPE_CHECKING:
    from glitchygames.scenes import Scene

MODULE = 'scripts.mirror_measurements.clone_speed'


def measure(*, name: str, spawned_at: float) -> dict[str, Any]:
    """Replay one recording, timing each frame, and model the lag behind the live game.

    Args:
        name: The recording.
        spawned_at: When the parent started this process (``time.time()``).

    Returns:
        The run's result.

    """
    recording = recording_named(name)
    frame_ends: list[float] = []
    first_frame_at: list[float] = []

    def on_frame(_frame: int, _scene: Scene | None, _processing: float | None) -> None:
        if not first_frame_at:
            first_frame_at.append(time.time())
        frame_ends.append(time.perf_counter())

    replay_start = time.perf_counter()
    replay_with_hook(recording=recording, on_frame=on_frame)
    costs = [frame_ends[0] - replay_start] + [
        later - earlier for earlier, later in itertools.pairwise(frame_ends)
    ]
    # The first frame's cost includes building the game: it's the start-up, reported apart
    steady_costs = costs[1:]
    recorded = recorded_frame_seconds(path=recording.absolute_path)
    start_up_seconds = first_frame_at[0] - spawned_at
    live_end = 0.0
    clone_end = start_up_seconds
    lags: list[float] = []
    for index, cost in enumerate(costs):
        live_end += recorded[index] if index < len(recorded) else 0.0
        clone_end = max(clone_end, live_end) + (cost if index else 0.0)
        lags.append(clone_end - live_end)
    replay_seconds = sum(steady_costs)
    return {
        'name': name,
        'frames': len(costs),
        'recorded_seconds': sum(recorded),
        'start_up_to_first_frame_seconds': start_up_seconds,
        'speed_times_real_time': (sum(recorded) - recorded[0]) / replay_seconds,
        'frame_cost_ms': in_milliseconds(percentiles(steady_costs)).model_dump(),
        'lag_seconds': percentiles(lags).model_dump(),
        'frames_slower_than_recorded': sum(
            1
            for index, cost in enumerate(costs[1:], start=1)
            if index < len(recorded) and cost > recorded[index]
        ),
    }


def summary_line(result: dict[str, Any], *, repeat: int) -> str:
    """One run's line.

    Returns:
        The line.

    """
    frame_cost = result['frame_cost_ms']
    return (
        f'{result["name"]} #{repeat}: {result["frames"]} frames, '
        f'start-up {result["start_up_to_first_frame_seconds"]:.2f} s, '
        f'{result["speed_times_real_time"]:.1f}x real time, frame p50 {frame_cost["p50"]:.2f} ms '
        f'p99 {frame_cost["p99"]:.2f} max {frame_cost["max"]:.2f}, lag max '
        f'{result["lag_seconds"]["max"]:.2f} s, {result["frames_slower_than_recorded"]} frames '
        'slower than recorded\n'
    )


def main(arguments: list[str] | None = None) -> int:
    """Run every recording's measurement, or (``--child``) one.

    Returns:
        0, or the first failed run's exit code.

    """
    parser = argparse.ArgumentParser(
        description='How fast a clone replays each recording, and how far behind it would stay'
    )
    parser.add_argument('--output', type=Path, required=True, help='where each run writes JSON')
    parser.add_argument('--repeats', type=int, default=3, help='runs per recording')
    parser.add_argument('--only', nargs='+', choices=RECORDING_NAMES, default=RECORDING_NAMES)
    parser.add_argument('--child', choices=RECORDING_NAMES, help=argparse.SUPPRESS)
    parser.add_argument('--spawned-at', type=float, help=argparse.SUPPRESS)
    parser.add_argument('--result', type=Path, help=argparse.SUPPRESS)
    options = parser.parse_args(arguments)
    if options.child is not None:
        result = measure(name=options.child, spawned_at=options.spawned_at)
        options.result.write_text(json.dumps(result, indent=1), encoding='utf-8')
        return 0
    options.output.mkdir(parents=True, exist_ok=True)
    for name in options.only:
        for repeat in range(options.repeats):
            path = options.output / f'{name}-{repeat}.json'
            exit_code = run_measurement(
                module=MODULE,
                arguments=[
                    '--output',
                    str(options.output),
                    '--child',
                    name,
                    '--spawned-at',
                    repr(time.time()),
                    '--result',
                    str(path),
                ],
            )
            if exit_code:
                return exit_code
            result = json.loads(path.read_text(encoding='utf-8'))
            sys.stdout.write(summary_line(result, repeat=repeat))
            sys.stdout.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
