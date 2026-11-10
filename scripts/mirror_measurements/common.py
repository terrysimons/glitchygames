"""What the mirror measurements share: the recordings, a hooked headless replay, and percentiles.

The replay hook follows scripts/ai_behaviour/capture.py: it wraps ``ReplaySources.end_frame`` and
runs the game's console script in this process with ``--replay-trace PATH --headless``.
"""

from __future__ import annotations

import contextlib
import os
import statistics
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from glitchygames.process import OutputCapture, run_command

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Sequence

    from glitchygames.audio.accounting import AudioFrameAccount
    from glitchygames.scenes import Scene
    from glitchygames.supervision import ControlEvent

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# A child that runs longer than this is stuck: the longest golden replays in under 2 s
CHILD_TIMEOUT_SECONDS = 600.0


class Recording(BaseModel):
    """A recording the measurements replay, and the console script that replays it."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    name: str
    console_script: str
    path: Path

    @property
    def absolute_path(self) -> Path:
        """The recording's path from the repository's root."""
        return PROJECT_ROOT / self.path


# Every golden replay and the bundled demo
RECORDINGS: tuple[Recording, ...] = (
    Recording(
        name='paddleslap',
        console_script='paddleslap',
        path=Path('src/games/paddleslap/tests/fixtures/replays/golden.jsonl.gz'),
    ),
    Recording(
        name='paddleslap-rally',
        console_script='paddleslap',
        path=Path('src/games/paddleslap/src/paddleslap/demos/rally.jsonl.gz'),
    ),
    Recording(
        name='clockwork-keep',
        console_script='clockwork-keep',
        path=Path('src/games/clockwork-keep/tests/fixtures/replays/golden.jsonl.gz'),
    ),
    Recording(
        name='brave-classic',
        console_script='brave-adventurer',
        path=Path('src/games/brave-adventurer/tests/fixtures/replays/golden-classic.jsonl.gz'),
    ),
    Recording(
        name='brave-papyrus',
        console_script='brave-adventurer',
        path=Path('src/games/brave-adventurer/tests/fixtures/replays/golden-papyrus.jsonl.gz'),
    ),
    Recording(
        name='mr-muncher',
        console_script='mr-muncher',
        path=Path('src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz'),
    ),
    Recording(
        name='drawing-fire',
        console_script='drawing-fire',
        path=Path('src/games/drawing-fire/tests/fixtures/replays/golden.jsonl.gz'),
    ),
)
RECORDING_NAMES = tuple(recording.name for recording in RECORDINGS)


class Percentiles(BaseModel):
    """The median, 95th and 99th percentiles, the largest and the mean of some values."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    p50: float
    p95: float
    p99: float
    max: float
    mean: float


def recording_named(name: str) -> Recording:
    """The recording of that name.

    Returns:
        The recording.

    Raises:
        KeyError: If there is none.

    """
    for recording in RECORDINGS:
        if recording.name == name:
            return recording
    raise KeyError(name)


def percentiles(values: Sequence[float]) -> Percentiles:
    """Summarise some values (none: all zeros).

    Returns:
        Their percentiles.

    """
    if not values:
        return Percentiles(p50=0.0, p95=0.0, p99=0.0, max=0.0, mean=0.0)
    ordered = sorted(values)

    def at(fraction: float) -> float:
        return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]

    return Percentiles(
        p50=at(0.50), p95=at(0.95), p99=at(0.99), max=ordered[-1], mean=statistics.fmean(ordered)
    )


def in_milliseconds(summary: Percentiles) -> Percentiles:
    """The same percentiles of seconds, in milliseconds.

    Returns:
        The percentiles times 1000.

    """
    return Percentiles(
        p50=summary.p50 * 1000,
        p95=summary.p95 * 1000,
        p99=summary.p99 * 1000,
        max=summary.max * 1000,
        mean=summary.mean * 1000,
    )


def replace_attribute(*, owner: object, name: str, replacement: object) -> object:
    """Put ``replacement`` in place of ``owner``'s attribute, for the rest of the process.

    How the measurements time engine functions: the replacement wraps the original. By name,
    since a wrapper's type isn't the attribute's declared one.

    Returns:
        The original.

    """
    original = getattr(owner, name)
    setattr(owner, name, replacement)
    return original


@contextlib.contextmanager
def replaced(*, owner: object, name: str, replacement: object) -> Generator[None]:
    """Put ``replacement`` in place of ``owner``'s attribute, then the original back.

    Yields:
        None, while the replacement is in place.

    """
    original = replace_attribute(owner=owner, name=name, replacement=replacement)
    try:
        yield
    finally:
        setattr(owner, name, original)


def use_dummy_drivers() -> None:
    """Default SDL's drivers to dummy, as a clone runs (call before pygame starts)."""
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')


def replay_with_hook(
    *, recording: Recording, on_frame: Callable[[int, Scene | None, float | None], None]
) -> None:
    """Replay a recording headless in this process, calling ``on_frame`` at each frame's end.

    ``on_frame(frame, scene, processing_seconds)`` runs before the doors end the frame; frames
    are counted from 0 as the replay runs them.
    """
    from glitchygames.replay import driver
    from glitchygames.replay.tools.children import game_entry_point

    use_dummy_drivers()
    real_end = driver.ReplaySources.end_frame
    frame_counter = [0]

    # The doors' own signature, so a change to it fails the type check here
    def ending(  # ruff: ignore[too-many-arguments] - the EngineSources door's signature
        self: driver.ReplaySources,
        *,
        frame_number: int,
        dt: float,
        scene: Scene | None,
        control_events: list[ControlEvent],
        processing_seconds: float | None = None,
        audio_frame: AudioFrameAccount | None = None,
    ) -> None:
        on_frame(frame_counter[0], scene, processing_seconds)
        frame_counter[0] += 1
        real_end(
            self,
            frame_number=frame_number,
            dt=dt,
            scene=scene,
            control_events=control_events,
            processing_seconds=processing_seconds,
            audio_frame=audio_frame,
        )

    driver.ReplaySources.end_frame = ending
    saved_argv = sys.argv
    sys.argv = [
        recording.console_script,
        '--replay-trace',
        str(recording.absolute_path),
        '--headless',
        '--log-level',
        'error',
    ]
    try:
        with contextlib.suppress(SystemExit):
            game_entry_point(console_script=recording.console_script).load()()
    finally:
        sys.argv = saved_argv
        driver.ReplaySources.end_frame = real_end


def recorded_frame_seconds(*, path: Path) -> list[float]:
    """Each recorded frame's dt.

    Returns:
        The frame times, in seconds.

    """
    from glitchygames.tracing import read_trace

    return [frame['dt'] for frame in read_trace(path=path)['frames']]


def run_measurement(*, module: str, arguments: Sequence[str]) -> int:
    """Run one measurement as a child process of this interpreter, from the repository's root.

    Its output is captured and shown only when it fails.

    Returns:
        Its exit code.

    """
    completed = run_command(
        command=[sys.executable, '-m', module, *arguments],
        environment=os.environ,
        timeout_seconds=CHILD_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
        working_directory=PROJECT_ROOT,
    )
    if completed.returncode != 0:
        sys.stderr.write(f'{module} {" ".join(arguments)} failed ({completed.returncode}):\n')
        sys.stderr.write((completed.stdout or '')[-2000:])
    return completed.returncode
