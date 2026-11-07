"""Capture snapshots from a real recording, for the AI behaviour tests' stand-in tools.

A snapshot is what the AI's tools would see at one frame of a game, read with
``glitchygames.ai_introspection`` as the clone will read it (properties on, plumbing off):

- ``scene``: the scene (the paused game, under a pause screen) and ``facts``, its
  ``describe_for_ai()``
- ``sprites``: every sprite, by stable id, one level deep
- ``objects``: the scene three levels deep, for ``get_object`` (a game's non-sprite state)
- ``window``: the frames just before, each sprite's position and speed, and the events pumped
- ``log``: every change to the scene's whole numbers, strings, flags and lists since frame 0,
  every change of scene, and whether a demo is playing (``demo_playing``), which is how history
  questions (the longest rally) are answered

Frames are counted as the replay runs them, a demo's played frames included, so a moment's frame
is the same every time: recordings replay exactly.

Usage:
    uv run python -m scripts.ai_behaviour.capture paddleslap
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from glitchygames.ai_introspection import ReadOptions, read_object
from glitchygames.replay import driver
from glitchygames.replay.tools.children import game_entry_point
from glitchygames.tracing import StableSpriteIds

if TYPE_CHECKING:
    import pygame

    from glitchygames.audio.accounting import AudioFrameAccount
    from glitchygames.scenes import Scene
    from glitchygames.supervision import ControlEvent

PACKAGE_DIRECTORY = Path(__file__).parent
FIXTURES_DIRECTORY = PACKAGE_DIRECTORY / 'fixtures'
PROJECT_ROOT = PACKAGE_DIRECTORY.parent.parent
OPTIONS = ReadOptions(include_properties=True)
WINDOW_FRAMES = 60
OBJECTS_DEPTH = 3
# Window entries keep only these of each sprite: enough to see motion, small enough for a prompt
WINDOW_SPRITE_KEYS = ('world_x', 'world_y', 'rect', 'speed', 'velocity_x', 'velocity_y', 'visible')


class Moment(BaseModel):
    """One frame of one recording to snapshot."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    name: str
    console_script: str
    recording: str
    frame: int
    # A deeper read of the scene, for the checks only, never for the tools: a game drawn without
    # sprites (Drawing Fire) keeps its state in objects the tools can't read yet
    check_depth: int = 0


GOLDEN = 'src/games/paddleslap/tests/fixtures/replays/golden.jsonl.gz'
NO_INPUT = 'scripts/ai_behaviour/recordings/paddleslap-no-input.jsonl.gz'
CLOCKWORK_GOLDEN = 'src/games/clockwork-keep/tests/fixtures/replays/golden.jsonl.gz'
MUNCHER_GOLDEN = 'src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz'
FIRE_GOLDEN = 'src/games/drawing-fire/tests/fixtures/replays/golden.jsonl.gz'
BRAVE_HAZARDS = 'scripts/ai_behaviour/recordings/brave-adventurer-hazards.jsonl.gz'
MOMENTS: dict[str, tuple[Moment, ...]] = {
    'paddleslap': (
        Moment(
            name='two-balls-after-a-hit', console_script='paddleslap', recording=GOLDEN, frame=60
        ),
        Moment(
            name='ball-heading-for-player-2',
            console_script='paddleslap',
            recording=GOLDEN,
            frame=330,
        ),
        Moment(name='four-balls', console_script='paddleslap', recording=GOLDEN, frame=600),
        Moment(name='closest-two-balls', console_script='paddleslap', recording=GOLDEN, frame=621),
        Moment(name='game-over', console_script='paddleslap', recording=NO_INPUT, frame=100),
        Moment(name='after-the-demo', console_script='paddleslap', recording=NO_INPUT, frame=1600),
    ),
    'clockwork-keep': (
        # Tinker jumped from frame 10, rose up through the platform at world y 880 and landed
        Moment(
            name='after-jumping-up-through',
            console_script='clockwork-keep',
            recording=CLOCKWORK_GOLDEN,
            frame=52,
        ),
        Moment(
            name='climbing', console_script='clockwork-keep', recording=CLOCKWORK_GOLDEN, frame=300
        ),
    ),
    'mr-muncher': (
        Moment(name='playing', console_script='mr-muncher', recording=MUNCHER_GOLDEN, frame=400),
        Moment(name='sugar-rush', console_script='mr-muncher', recording=MUNCHER_GOLDEN, frame=900),
        # Caught at frame 1469, dying until 1650
        Moment(name='just-died', console_script='mr-muncher', recording=MUNCHER_GOLDEN, frame=1500),
    ),
    'brave-adventurer': (
        # Running at the first pit (x 3550), which the recording walks into on purpose at 1047
        Moment(
            name='before-the-first-pit',
            console_script='brave-adventurer',
            recording=BRAVE_HAZARDS,
            frame=1030,
        ),
        # Lost a life in that pit at 1082, respawned at 1094
        Moment(
            name='just-missed-the-pit',
            console_script='brave-adventurer',
            recording=BRAVE_HAZARDS,
            frame=1092,
        ),
        Moment(
            name='past-the-first-pit',
            console_script='brave-adventurer',
            recording=BRAVE_HAZARDS,
            frame=1200,
        ),
    ),
    'drawing-fire': (
        Moment(
            name='mid-battle',
            console_script='drawing-fire',
            recording=FIRE_GOLDEN,
            frame=600,
            check_depth=3,
        ),
        # Battle 1 ended at frame 1232
        Moment(
            name='battle-won',
            console_script='drawing-fire',
            recording=FIRE_GOLDEN,
            frame=1240,
            check_depth=3,
        ),
    ),
}


def window_entry(*, frame: int, scene: Scene, sprite_ids: StableSpriteIds) -> dict[str, Any]:
    """Describe one frame briefly: each sprite's position and speed.

    Returns:
        The frame's entry.

    """
    subject = scene.debug_subject
    sprites = {}
    for sprite in subject.all_sprites:
        read = read_object(value=sprite, depth=1, sprite_ids=sprite_ids, options=OPTIONS)
        sprites[str(read['id'])] = {key: read[key] for key in WINDOW_SPRITE_KEYS if key in read}
    return {'frame': frame, 'scene': type(scene).__qualname__, 'sprites': sprites}


def loggable(state: dict[str, Any]) -> dict[str, Any]:
    """Keep what a log of changes should follow: no floats, which change every frame.

    Returns:
        The scene's whole numbers, strings, flags, lists and empty values.

    """
    return {key: value for key, value in state.items() if not isinstance(value, float)}


def capture(*, moments: tuple[Moment, ...], output: Path) -> list[Path]:
    """Replay each recording once, saving a snapshot at each of its moments.

    Returns:
        The snapshot files written.

    """
    written: list[Path] = []
    by_recording: dict[tuple[str, str], list[Moment]] = collections.defaultdict(list)
    for moment in moments:
        by_recording[moment.console_script, moment.recording].append(moment)
    for (console_script, recording), wanted in by_recording.items():
        written += replay_and_snapshot(
            console_script=console_script, recording=recording, moments=wanted, output=output
        )
    return written


def replay_and_snapshot(
    *, console_script: str, recording: str, moments: list[Moment], output: Path
) -> list[Path]:
    """Replay one recording headless, keeping a window and a log, and snapshot each moment.

    Returns:
        The snapshot files written.

    Raises:
        ValueError: If the recording ended before a moment's frame.

    """
    recorder = SnapshotRecorder(
        console_script=console_script, recording=recording, moments=moments, output=output
    )
    real_end = driver.ReplaySources.end_frame
    real_pump = driver.ReplaySources.pump_events

    # The doors' own signatures, so a change to them fails the type check here
    def pumping(
        self: driver.ReplaySources, *, real_events: list[pygame.event.Event] | None = None
    ) -> list[pygame.event.Event]:
        pumped = real_pump(self, real_events=real_events)
        recorder.keep_events(events=pumped)
        return pumped

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
        if scene is not None:
            recorder.follow_frame(scene=scene)
        recorder.end_frame()
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
    driver.ReplaySources.pump_events = pumping
    arguments = [console_script, '--replay-trace', recording, '--headless', '--log-level', 'error']
    saved_argv = sys.argv
    sys.argv = arguments
    try:
        with contextlib.suppress(SystemExit):
            game_entry_point(console_script=console_script).load()()
    finally:
        sys.argv = saved_argv
        driver.ReplaySources.end_frame = real_end
        driver.ReplaySources.pump_events = real_pump
    missing = sorted(set(recorder.frames_wanted) - recorder.frames_written)
    if missing:
        message = f'{recording} ended before frames {missing}'
        raise ValueError(message)
    return recorder.written


class SnapshotRecorder:
    """What one replay keeps as it runs: the window, the log, and a snapshot at each moment."""

    def __init__(
        self, *, console_script: str, recording: str, moments: list[Moment], output: Path
    ) -> None:
        """Start at frame 0 with nothing kept."""
        self.console_script = console_script
        self.recording = recording
        self.output = output
        self.frames_wanted = {moment.frame: moment for moment in moments}
        self.sprite_ids = StableSpriteIds()
        self.window: collections.deque[dict[str, Any]] = collections.deque(maxlen=WINDOW_FRAMES)
        self.log: list[dict[str, Any]] = []
        self.previous: dict[str, Any] = {}
        self.events: list[dict[str, Any]] = []
        self.frame = 0
        self.written: list[Path] = []
        self.frames_written: set[int] = set()

    def keep_events(self, *, events: list[pygame.event.Event]) -> None:
        """Keep the frame's pumped events, with their plain fields."""
        for event in events:
            fields = {
                key: value
                for key, value in getattr(event, '__dict__', {}).items()
                if isinstance(value, (int, float, str, bool))
            }
            self.events.append({'type': event.type, **fields})

    def follow_frame(self, *, scene: Scene) -> None:
        """Log what changed, add the frame to the window, and snapshot it if it's a moment."""
        subject = scene.debug_subject
        state = read_object(value=subject, depth=0, sprite_ids=self.sprite_ids, options=OPTIONS)
        followed = {
            'scene': type(scene).__qualname__,
            # A demo or instant replay playing: the engine knows, and so will the clone
            'demo_playing': bool(scene.scene_manager.in_playback_scope),
            **loggable(state),
        }
        changed = {key: value for key, value in followed.items() if self.previous.get(key) != value}
        if changed:
            self.log.append({'frame': self.frame, **changed})
            self.previous.update(changed)
        entry = window_entry(frame=self.frame, scene=scene, sprite_ids=self.sprite_ids)
        if self.events:
            entry['events'] = list(self.events)
        self.window.append(entry)
        moment = self.frames_wanted.get(self.frame)
        if moment is not None:
            self.write_snapshot(moment=moment, subject=subject, state=state)

    def write_snapshot(self, *, moment: Moment, subject: Scene, state: dict[str, Any]) -> None:
        """Write the moment's snapshot: the scene, its sprites, objects, window and log."""
        snapshot = {
            'game': self.console_script,
            'moment': moment.name,
            'recording': self.recording,
            'frame': self.frame,
            'scene': state,
            'facts': subject.describe_for_ai(),
            'sprites': {
                str(read['id']): read
                for read in (
                    read_object(value=sprite, depth=1, sprite_ids=self.sprite_ids, options=OPTIONS)
                    for sprite in subject.all_sprites
                )
            },
            'window': list(self.window),
            'log': list(self.log),
            # What get_object reads: the scene's objects, three levels down
            'objects': read_object(
                value=subject, depth=OBJECTS_DEPTH, sprite_ids=self.sprite_ids, options=OPTIONS
            ),
        }
        if moment.check_depth:
            snapshot['for_checks'] = read_object(
                value=subject, depth=moment.check_depth, sprite_ids=self.sprite_ids, options=OPTIONS
            )
        path = self.output / self.console_script / f'{moment.name}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snapshot, indent=1), encoding='utf-8')
        self.written.append(path)
        self.frames_written.add(self.frame)

    def end_frame(self) -> None:
        """Move on to the next frame."""
        self.events.clear()
        self.frame += 1


def main(arguments: list[str] | None = None) -> int:
    """Capture a game's moments.

    Returns:
        The exit code.

    """
    parser = argparse.ArgumentParser(description='Capture AI behaviour test snapshots.')
    parser.add_argument('game', choices=sorted(MOMENTS))
    parser.add_argument('--output', type=Path, default=FIXTURES_DIRECTORY)
    options = parser.parse_args(arguments)
    for path in capture(moments=MOMENTS[options.game], output=options.output):
        sys.stdout.write(f'{path.relative_to(PROJECT_ROOT)} ({path.stat().st_size} bytes)\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
