"""The recorder's main-thread work per frame, in a live run on the real display.

The game plays its golden session (its script, controls tail and seed, as
scripts/record_scripted_session.py records it) paced, in a window on the machine's own video
driver; audio is SDL's dummy driver, so it plays no sound. Each piece of the recorder's work is
timed per frame:

- events: ``GameplayRecorder.record_event_batch`` (classifying and encoding the pumped batch)
- input: ``snapshot_changes`` (the polled-input diff)
- sample: ``recorded_frame`` (every sprite's id, rect and visibility, and the frame's fields)
- hash: ``add_frame_histories`` (the content hash, SHA-256 of the frame's content)
- write: ``TraceWriter.write_frame`` (delta encoding, JSON, gzip)
- record_frame: the whole of ``GameplayRecorder.record_frame`` (sample, hash, write and the rest)

A clone needs only the first two (and dt). With ``--clone-load NAME`` a stand-in clone
(clone_loop) replays that recording flat out beside the game for the whole run.

Usage:
    uv run python -m scripts.mirror_measurements.live_stream_cost --game mr_muncher --output DIR
        [--clone-load mr-muncher] [--video-driver cocoa]
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from scripts.mirror_measurements.common import (
    PROJECT_ROOT,
    RECORDING_NAMES,
    in_milliseconds,
    percentiles,
    replaced,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from glitchygames.audio.accounting import AudioFrameAccount
    from glitchygames.scenes import Scene
    from glitchygames.supervision import ControlEvent

PIECES = ('events', 'input', 'sample', 'hash', 'write', 'record_frame')
# Each golden session's script frames (scripts/record_scripted_session.py's docstring)
GOLDEN_SCRIPT_FRAMES = {
    'paddleslap': 600,
    'clockwork_keep': 330,
    'brave_adventurer': 400,
    'brave_adventurer_papyrus': 400,
    'mr_muncher': 1950,
    'drawing_fire': 1600,
}
NATIVE_VIDEO_DRIVERS = {'darwin': 'cocoa', 'win32': 'windows'}
CLONE_START_SECONDS = 1.0
FRAME_BUDGET_SECONDS = 1 / 60.01


def timed[**Parameters, Result](
    *, piece: str, function: Callable[Parameters, Result], frame_pieces: dict[str, float]
) -> Callable[Parameters, Result]:
    """Wrap a function so each call's time adds to the frame's total for its piece.

    Returns:
        The wrapper.

    """

    def wrapper(*arguments: Parameters.args, **keywords: Parameters.kwargs) -> Result:
        start = time.perf_counter()
        try:
            return function(*arguments, **keywords)
        finally:
            frame_pieces[piece] = frame_pieces.get(piece, 0.0) + time.perf_counter() - start

    return wrapper


def run_live(*, game: str, output: Path, clone_load: str | None) -> dict[str, Any]:
    """Play the golden session live with the recorder's pieces timed.

    Returns:
        The run: each frame's dt, processing time, sprite count and pieces.

    """
    import pygame

    from glitchygames import recording, tracing
    from glitchygames.process import start_command, stop_command
    from scripts.record_scripted_session import record_golden_session

    frame_pieces: dict[str, float] = {}
    frames: list[dict[str, float]] = []
    video_driver: list[str] = []
    # (owner, attribute, piece): each timed for the whole run
    timed_attributes: tuple[tuple[object, str, str], ...] = (
        (recording.GameplayRecorder, 'record_event_batch', 'events'),
        (recording.GameplayRecorder, 'record_frame', 'record_frame'),
        (recording, 'snapshot_changes', 'input'),
        (recording, 'recorded_frame', 'sample'),
        (recording, 'add_frame_histories', 'hash'),
        (tracing.TraceWriter, 'write_frame', 'write'),
    )
    real_end = recording.RecordingSources.end_frame

    def ending(  # ruff: ignore[too-many-arguments] - the EngineSources door's signature
        self: recording.RecordingSources,
        *,
        frame_number: int,
        dt: float,
        scene: Scene | None,
        control_events: list[ControlEvent],
        processing_seconds: float | None = None,
        audio_frame: AudioFrameAccount | None = None,
    ) -> None:
        real_end(
            self,
            frame_number=frame_number,
            dt=dt,
            scene=scene,
            control_events=control_events,
            processing_seconds=processing_seconds,
            audio_frame=audio_frame,
        )
        if not video_driver:
            video_driver.append(pygame.display.get_driver())
        frames.append({
            'dt': dt,
            'processing': processing_seconds or 0.0,
            'sprites': len(scene.all_sprites) if scene is not None else 0,
            **{piece: frame_pieces.get(piece, 0.0) for piece in PIECES},
        })
        frame_pieces.clear()

    clone = None
    with (
        contextlib.ExitStack() as replacements,
        tempfile.TemporaryFile(mode='w+', encoding='utf-8') as clone_output,
    ):
        for owner, attribute, piece in timed_attributes:
            replacements.enter_context(
                replaced(
                    owner=owner,
                    name=attribute,
                    replacement=timed(
                        piece=piece,
                        function=getattr(owner, attribute),
                        frame_pieces=frame_pieces,
                    ),
                )
            )
        replacements.enter_context(
            replaced(owner=recording.RecordingSources, name='end_frame', replacement=ending)
        )
        if clone_load is not None:
            clone = start_command(
                command=[
                    sys.executable,
                    '-m',
                    'scripts.mirror_measurements.clone_loop',
                    clone_load,
                ],
                environment=os.environ,
                output=clone_output,
            )
            time.sleep(CLONE_START_SECONDS)
        try:
            record_golden_session(
                game_key=game,
                frame_count=GOLDEN_SCRIPT_FRAMES[game],
                path=output / f'{label_for(game=game, clone_load=clone_load)}.jsonl.gz',
                exercise_controls=True,
            )
        finally:
            if clone is not None:
                stop_command(process=clone)
    return {
        'game': game,
        'clone_load': clone_load,
        'video_driver': video_driver[0] if video_driver else None,
        'frames': frames,
    }


def label_for(*, game: str, clone_load: str | None) -> str:
    """A run's file name, without its suffix.

    Returns:
        The label.

    """
    return f'{game}-with-clone' if clone_load else game


def summary(run: dict[str, Any]) -> str:
    """Each piece's and the frame time's percentiles, in milliseconds.

    Returns:
        The summary's lines.

    """
    # The first frame's dt runs from the clock's start
    frames = run['frames'][1:]
    lines = [
        (
            f'== {label_for(game=run["game"], clone_load=run["clone_load"])}: '
            f'{len(frames)} frames, sprites max {max(frame["sprites"] for frame in frames)}, '
            f'video driver {run["video_driver"]}'
        )
    ]
    for piece in (*PIECES, 'processing', 'dt'):
        values = in_milliseconds(percentiles([frame[piece] for frame in frames]))
        lines.append(
            f'  {piece:13} mean {values.mean:.3f}  p50 {values.p50:.3f}  p95 {values.p95:.3f}  '
            f'p99 {values.p99:.3f}  max {values.max:.3f} ms'
        )
    late = sum(1 for frame in frames if frame['dt'] > FRAME_BUDGET_SECONDS * 1.5)
    lines.append(f'  {late} frames over 1.5 times the 60 FPS budget')
    return '\n'.join(lines) + '\n'


def main(arguments: list[str] | None = None) -> int:
    """Play one game's golden session live, timing the recorder.

    Returns:
        0.

    """
    parser = argparse.ArgumentParser(
        description="The recorder's main-thread work per frame, live on the real display"
    )
    parser.add_argument('--game', required=True, choices=sorted(GOLDEN_SCRIPT_FRAMES))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--clone-load', choices=RECORDING_NAMES, default=None)
    parser.add_argument(
        '--video-driver',
        default=NATIVE_VIDEO_DRIVERS.get(sys.platform),
        help="SDL's video driver (default: this platform's own)",
    )
    options = parser.parse_args(arguments)
    # Set before anything imports scripts.record_scripted_session, which defaults it to dummy
    if options.video_driver:
        os.environ['SDL_VIDEODRIVER'] = options.video_driver
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    os.chdir(PROJECT_ROOT)
    options.output.mkdir(parents=True, exist_ok=True)
    run = run_live(game=options.game, output=options.output, clone_load=options.clone_load)
    path = options.output / f'{label_for(game=options.game, clone_load=options.clone_load)}.json'
    path.write_text(json.dumps(run), encoding='utf-8')
    sys.stdout.write(summary(run))
    return 0


if __name__ == '__main__':
    sys.exit(main())
