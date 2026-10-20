"""Gameplay recording through the real engine (``--record-trace``, ``--random-seed``).

The engine tests run ``GameEngine.start()`` and ``SceneManager.start()`` headless, with the
scene manager's clock replaced by a fake one and input posted into pygame's real event queue,
so every recorded value goes through the real frame loop and event dispatch. The golden test
runs a game's golden-trace script (``scripts/record_golden_traces.py``) with recording on and
checks the recording's sprites against the golden harness's own frames.
"""

from __future__ import annotations

import contextlib
import gzip
import importlib.metadata
import json
import os
import platform
import signal
import sys
import threading
import types
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

import pygame
import pytest
from scripts.record_golden_traces import (
    FRAME_SECONDS,
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    command_line,
    record_trace,
)

from glitchygames.engine import game_engine as game_engine_module
from glitchygames.events import FPSEVENT
from glitchygames.examples import paddleslap
from glitchygames.exit_codes import ExitCode
from glitchygames.input import devices as devices_module
from glitchygames.input.state import IDLE_INPUT, apply_snapshot_changes
from glitchygames.live_sources import LiveSources
from glitchygames.randomness import engine_random
from glitchygames.recording import (
    CONTROL_EVENTS_FIELD,
    DEVICE_ENUMERATION_FIELD,
    DEVICES_OPENED_FIELD,
    DT_FIELD,
    EVENT_BATCHES_FIELD,
    EXTERNAL_ORIGIN,
    INPUT_CHANGES_FIELD,
    INTERNAL_ORIGIN,
    RECORDING_SOURCE,
    SAVES_HEADER_FIELD,
    SAVES_OPENED_FIELD,
    RecordingSources,
    TraceRecordingAlreadyStartedError,
    UnrepresentableValue,
    event_from_record,
)
from glitchygames.replay.audit import HEADLESS_ENVIRONMENT_VARIABLES, run_command
from glitchygames.scenes import Scene, SceneManager
from glitchygames.scenes import scene as scene_module
from glitchygames.sources import active_sources, install_sources
from glitchygames.state import DiskSaveManager, MemorySaveManager
from glitchygames.state.sandbox import open_saves
from glitchygames.supervision import BREAKPOINT_KIND
from glitchygames.tracing import read_trace_result
from glitchygames.transitions import FadeTransition

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path

# Each perf_counter() read advances the fake clock by this much, so frame times differ by
# frame (a frame reads the clock a different number of times than the loop's first read)
FAKE_CLOCK_STEP_SECONDS = 0.004
RECORDING_RESOLUTION = '320x240'
RANDOM_SEED = 123

# The departure scene starts its transition in this frame; the transition runs this many frames
TRANSITION_START_FRAME = 3
TRANSITION_FRAME_COUNT = 4
# The arrival scene posts QUIT in its frame with this index (0 = its first frame)
ARRIVAL_QUIT_FRAME = 2

# Key and mouse events are the scripted input; the host environment posts others (window events)
# A type no handler takes: the engine reports it as unhandled
UNHANDLED_EVENT_TYPE = pygame.USEREVENT + 40

SCRIPTED_EVENT_TYPES = frozenset({
    UNHANDLED_EVENT_TYPE,
    pygame.KEYDOWN,
    pygame.KEYUP,
    pygame.MOUSEMOTION,
    pygame.MOUSEBUTTONDOWN,
    pygame.MOUSEBUTTONUP,
    pygame.QUIT,
})

# The fields a recording adds to each sprite frame (each format-3 field only where not empty)
RECORDING_FRAME_FIELDS = frozenset({
    DT_FIELD,
    EVENT_BATCHES_FIELD,
    INPUT_CHANGES_FIELD,
    CONTROL_EVENTS_FIELD,
    DEVICES_OPENED_FIELD,
    SAVES_OPENED_FIELD,
    DEVICE_ENUMERATION_FIELD,
})

# The whole Clockwork Keep golden script: the elevator ride (frames 352-592) and a pause (740-790)
CLOCKWORK_KEEP_RECORDED_FRAMES = 900


class FakePerfCounter:
    """A perf_counter() that advances a fixed step on every read."""

    def __init__(self) -> None:
        """Start at 100 seconds."""
        self.now_seconds = 100.0

    def __call__(self) -> float:
        """Advance, then return the time.

        Returns:
            The fake time in seconds.

        """
        self.now_seconds += FAKE_CLOCK_STEP_SECONDS
        return self.now_seconds


class Script:
    """Input and observations shared by the test scenes (reset by each test)."""

    # Logic frame number -> events the scene or transition posts at the start of that frame
    events_by_frame: ClassVar[dict[int, list[pygame.event.Event]]] = {}
    # The dt each frame's logic received, in frame order (Scene.dt_tick or Transition.update)
    logic_dts: ClassVar[list[float]] = []
    # Called by the departure scene in the frame with this number, if set
    action_frame: ClassVar[int | None] = None
    action: ClassVar[Callable[[], None] | None] = None

    @classmethod
    def reset(cls) -> None:
        """Clear the script and the observations."""
        cls.events_by_frame = {}
        cls.logic_dts = []
        cls.action_frame = None
        cls.action = None

    @classmethod
    def start_logic_frame(cls, dt: float) -> int:
        """Record the frame's dt and post its scripted events.

        Args:
            dt: The dt the frame's logic received.

        Returns:
            The frame number.

        """
        frame_number = len(cls.logic_dts)
        cls.logic_dts.append(dt)
        for event in cls.events_by_frame.get(frame_number, []):
            pygame.event.post(event)
        if cls.action is not None and cls.action_frame == frame_number:
            cls.action()
        return frame_number


class Marker(pygame.sprite.DirtySprite):
    """A small sprite that moves one pixel right every logic frame."""

    def __init__(self, *, x: int) -> None:
        """Create the sprite at (x, 10)."""
        super().__init__()
        self.image = pygame.Surface((4, 4))
        self.rect = self.image.get_rect(topleft=(x, 10))

    def update_nested_sprites(self) -> None:
        """Do nothing: Scene.update() calls this on every sprite, and this one has none."""


class ScriptedTransition(FadeTransition):
    """A fade that lasts exactly TRANSITION_FRAME_COUNT frames and posts the script's events."""

    def __init__(self) -> None:
        """Create a fade long enough that only the frame count ends it."""
        super().__init__(duration=1000.0)
        self.updates = 0

    @override
    def update(self, dt: float) -> bool:
        """Record dt and post events like a scene frame; finish after the scripted frames.

        Returns:
            True on the last scripted frame.

        """
        Script.start_logic_frame(dt)
        super().update(dt)
        self.updates += 1
        return self.updates >= TRANSITION_FRAME_COUNT


class ArrivalRecordedScene(Scene):
    """The scene after the transition: its sprite keeps moving; it quits when scripted."""

    NAME = 'Arrival'
    VERSION = '1.0'

    def __init__(self: Self, options: dict[str, Any] | None = None, groups: Any = None) -> None:
        """Add the marker sprite."""
        super().__init__(options=options, groups=groups)
        self.marker = Marker(x=100)
        self.all_sprites.add(self.marker)

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Run one logic frame, ignoring the engine's capture tick when a transition starts."""
        # SceneManager._start_transition ticks the incoming scene once (0.001 s) to capture its
        # screenshot, inside the frame that requested the transition: not a frame of its own
        if SceneManager()._pending_transition is not None:
            super().dt_tick(dt)
            return
        super().dt_tick(dt)
        Script.start_logic_frame(dt)
        self.marker.rect.x += 1
        self.marker.dirty = 1


class DepartureRecordedScene(ArrivalRecordedScene):
    """The game scene: starts a transition to an ArrivalRecordedScene in a scripted frame."""

    NAME = 'Departure'

    def __init__(self: Self, options: dict[str, Any] | None = None, groups: Any = None) -> None:
        """Add the marker sprite at x=0."""
        super().__init__(options=options, groups=groups)
        self.marker.rect.x = 0

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Run one logic frame; start the transition in TRANSITION_START_FRAME."""
        super().dt_tick(dt)
        if len(Script.logic_dts) - 1 == TRANSITION_START_FRAME:
            self.transition_to(ArrivalRecordedScene(options=self.options), ScriptedTransition())


# A child game that sends itself SIGTERM in its third frame (a real signal, delivered by the OS)
SELF_TERMINATING_GAME_SOURCE = """\
import os
import signal

from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene

SIGNAL_FRAME = 3


class SelfTerminatingGame(Scene):
    NAME = 'SelfTerminatingGame'

    def __init__(self, options=None, groups=None):
        super().__init__(options=options, groups=groups)
        self.frames = 0

    def dt_tick(self, dt):
        self.frames += 1
        if self.frames == SIGNAL_FRAME:
            os.kill(os.getpid(), signal.SIGTERM)


if __name__ == '__main__':
    GameEngine(game=SelfTerminatingGame).start()
"""
# A child game that only runs a few frames is killed after this long
SIGNAL_CHILD_TIMEOUT_SECONDS = 120.0


def run_self_terminating_game(*, game_file: Path, extra_arguments: tuple[str, ...]):
    """Run SELF_TERMINATING_GAME_SOURCE headless as a child, without a preset SDL signal hint.

    Returns:
        The finished process (subprocess.CompletedProcess, output captured).

    """
    environment = {
        name: value for name, value in os.environ.items() if name != 'SDL_NO_SIGNAL_HANDLERS'
    }
    return run_command(
        command=[
            sys.executable,
            str(game_file),
            '--target-fps',
            '0',
            '--log-level',
            'error',
            '--resolution',
            '320x240',
            *extra_arguments,
        ],
        environment={**environment, **HEADLESS_ENVIRONMENT_VARIABLES},
        timeout_seconds=SIGNAL_CHILD_TIMEOUT_SECONDS,
        capture_output=True,
    )


def call_signal_handler(*, signal_number: int) -> None:
    """Call the installed handler of a signal the way the delivered signal would."""
    handler = signal.getsignal(signal_number)
    assert callable(handler), f'No handler is installed for {signal_number} (found {handler!r})'
    handler(signal_number, None)


def platform_signal(signal_name: str) -> int:
    """Return a signal's number, skipping the test where this platform does not have it.

    Returns:
        The signal number.

    """
    if not hasattr(signal, signal_name):
        pytest.skip(f'signal.{signal_name} does not exist on this platform')
    return getattr(signal, signal_name)


def _key(event_type: int, key: int, *, unicode: str = '') -> pygame.event.Event:
    return pygame.event.Event(event_type, key=key, mod=0, unicode=unicode, scancode=0, window=None)


def _mouse_button(event_type: int, *, pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(event_type, pos=pos, button=1, touch=False, window=None)


@contextlib.contextmanager
def engine_run_environment(mocker) -> Generator[FakePerfCounter]:
    """Prepare a real engine run: fake clock, fresh singletons, pygame left initialized.

    Args:
        mocker: pytest-mock's fixture.

    Yields:
        The fake clock the scene manager reads.

    """
    Script.reset()
    fake_perf_counter = FakePerfCounter()
    mocker.patch.object(scene_module, 'time', types.SimpleNamespace(perf_counter=fake_perf_counter))
    # GameEngine._shutdown quits pygame; later tests on this worker still need it
    mocker.patch.object(pygame, 'quit')
    mocker.patch.object(pygame.display, 'quit')
    GoldenTraceSceneManager.install()
    try:
        yield fake_perf_counter
    finally:
        pygame.event.clear()
        GoldenTraceSceneManager.uninstall()


def run_engine(*arguments: str) -> GoldenTraceEngine:
    """Construct and start the engine with DepartureRecordedScene until the game quits.

    Args:
        *arguments: Extra command-line arguments.

    Returns:
        The engine, after GameEngine.start() returned (shut down).

    """
    with command_line([
        '--resolution',
        RECORDING_RESOLUTION,
        '--log-level',
        'warning',
        '--input-mode',
        'joystick',
        '--target-fps',
        '0',
        '--fps-log-interval-ms',
        '1000000000',
        *arguments,
    ]):
        engine = GoldenTraceEngine(game=DepartureRecordedScene)
    engine.start()
    return engine


def _scripted_events(frame: dict[str, Any]) -> list[pygame.event.Event]:
    """Decode the scripted events of a frame's single batch (environment events left out)."""
    (batch,) = frame[EVENT_BATCHES_FIELD]
    return [event_from_record(record) for record in batch if record['type'] in SCRIPTED_EVENT_TYPES]


def _origins(frame: dict[str, Any], event_type: int) -> set[str]:
    return {
        record['origin']
        for batch in frame[EVENT_BATCHES_FIELD]
        for record in batch
        if record['type'] == event_type
    }


def _event_summary(events: list[pygame.event.Event]) -> list[tuple[int, dict[str, Any]]]:
    return [(event.type, event.dict) for event in events]


def _schedule_quit_in_arrival() -> None:
    quit_frame = TRANSITION_START_FRAME + TRANSITION_FRAME_COUNT + 1 + ARRIVAL_QUIT_FRAME
    Script.events_by_frame.setdefault(quit_frame, []).append(pygame.event.Event(pygame.QUIT))


def _assert_recording_header(header: dict[str, Any]) -> None:
    """Check a run_engine recording's header: seed, versions, screen size and options."""
    assert header['source'] == RECORDING_SOURCE
    assert header['frame_seconds'] is None
    assert header['random_seed'] == RANDOM_SEED
    assert header['game_class'] == 'DepartureRecordedScene'
    assert header['scene_class'] == 'DepartureRecordedScene'
    assert header['engine_version'] == importlib.metadata.version('glitchygames')
    assert header['pygame_version'] == pygame.version.ver
    assert header['python_version'] == platform.python_version()
    assert header['screen_size'] == [320, 240]
    assert datetime.fromisoformat(header['recorded_at']).tzinfo is not None
    options = header['options']
    assert options['target_fps'] == 0.0
    assert options['timer_backend'] == 'fast'
    assert options['input_mode'] == 'joystick'
    assert options['resolution'] == RECORDING_RESOLUTION
    assert options['random_seed'] == RANDOM_SEED


class PayloadObject:
    """A Python object in an event payload, which a recording cannot store."""


PAYLOAD_TYPE_NAME = f'{PayloadObject.__module__}.PayloadObject'


class TestRecordingThroughTheEngine:
    """--record-trace records the real loop: header, dt and the raw event batches."""

    def test_recording_holds_header_dt_and_events(self, mocker, tmp_path):
        """A run with a transition and scripted input is recorded frame by frame."""
        path = tmp_path / 'session.jsonl.gz'
        with engine_run_environment(mocker):
            first_frame_events = [
                _key(pygame.KEYDOWN, pygame.K_a, unicode='é'),
                _key(pygame.KEYUP, pygame.K_a, unicode='é'),
            ]
            motion = pygame.event.Event(
                pygame.MOUSEMOTION,
                pos=(10, 20),
                rel=(1, 2),
                buttons=(0, 0, 0),
                touch=False,
                window=None,
            )
            # Transition frames: presses and motion are discarded, releases delivered
            first_transition_frame = TRANSITION_START_FRAME + 1
            transition_presses = [
                _key(pygame.KEYDOWN, pygame.K_b),
                _mouse_button(pygame.MOUSEBUTTONDOWN, pos=(5, 6)),
            ]
            transition_releases = [
                _key(pygame.KEYUP, pygame.K_b),
                _mouse_button(pygame.MOUSEBUTTONUP, pos=(5, 6)),
            ]
            unhandled = pygame.event.Event(UNHANDLED_EVENT_TYPE, payload=PayloadObject())
            Script.events_by_frame = {
                1: first_frame_events,
                2: [motion, unhandled],
                first_transition_frame + 1: [
                    transition_presses[0],
                    transition_releases[0],
                    transition_presses[1],
                    transition_releases[1],
                ],
            }
            _schedule_quit_in_arrival()

            engine = run_engine('--record-trace', str(path), '--random-seed', str(RANDOM_SEED))

            result = read_trace_result(path=path)

        assert result.is_complete
        header = result.trace
        _assert_recording_header(header)

        frames = header['frames']
        # One recorded frame per logic frame, each with the dt that logic received
        assert [frame[DT_FIELD] for frame in frames] == Script.logic_dts
        assert len({frame[DT_FIELD] for frame in frames}) > 1
        assert [frame['frame'] for frame in frames] == list(range(len(frames)))

        # The engine reads SDL's queue once per frame, transition frames included
        assert all(len(frame[EVENT_BATCHES_FIELD]) == 1 for frame in frames)
        assert _event_summary(_scripted_events(frames[1])) == _event_summary(first_frame_events)
        # The unhandled event is in its raw batch; its payload object is marked, not dropped
        assert _event_summary(_scripted_events(frames[2])) == [
            (pygame.MOUSEMOTION, motion.dict),
            (UNHANDLED_EVENT_TYPE, {'payload': UnrepresentableValue(type_name=PAYLOAD_TYPE_NAME)}),
        ]
        assert UNHANDLED_EVENT_TYPE in engine.unhandled_events
        # The transition frame's drained batch is recorded raw, in queue order: the presses the
        # transition discarded and the releases it delivered
        transition_frame = frames[first_transition_frame + 1]
        assert _event_summary(_scripted_events(transition_frame)) == _event_summary([
            transition_presses[0],
            transition_releases[0],
            transition_presses[1],
            transition_releases[1],
        ])
        assert [event.type for event in _scripted_events(frames[-1])] == [pygame.QUIT]
        # Posted here as stand-ins for SDL input: external (except the custom type)
        assert _origins(frames[1], pygame.KEYDOWN) == {EXTERNAL_ORIGIN}
        assert _origins(frames[-1], pygame.QUIT) == {EXTERNAL_ORIGIN}
        assert _origins(frames[2], UNHANDLED_EVENT_TYPE) == {INTERNAL_ORIGIN}

        # The departure scene is recorded up to the frame that started the transition; the
        # arrival scene (already active during the transition) from then on
        scenes = [frame['scene'] for frame in frames]
        assert scenes[:TRANSITION_START_FRAME] == ['DepartureRecordedScene'] * 3
        assert set(scenes[TRANSITION_START_FRAME:]) == {'ArrivalRecordedScene'}
        marker_x = [frame['sprites'][0]['rect'][0] for frame in frames]
        assert marker_x[:TRANSITION_START_FRAME] == [1, 2, 3]
        assert marker_x[-1] == 100 + ARRIVAL_QUIT_FRAME + 1

    def test_engine_posted_events_are_internal(self, mocker, tmp_path):
        """FPS events and quit_game()'s QUIT, posted by the engine, are recorded as internal."""
        path = tmp_path / 'session.jsonl.gz'
        with engine_run_environment(mocker):
            Script.action_frame = 2
            Script.action = lambda: SceneManager().quit_game()
            # A 1 ms FPS interval posts an FPS event almost every frame
            run_engine('--record-trace', str(path), '--fps-log-interval-ms', '1')

        frames = read_trace_result(path=path).trace['frames']
        fps_origins = set().union(*(_origins(frame, FPSEVENT) for frame in frames))
        assert fps_origins == {INTERNAL_ORIGIN}
        # quit_game() posts from frame 2's logic, before that frame's pump, which returns it;
        # the game ends after frame 2
        assert _origins(frames[-1], pygame.QUIT) == {INTERNAL_ORIGIN}
        assert len(frames) == 3

    def test_scene_change_starts_a_keyframe(self, mocker, tmp_path):
        """The frame whose scene differs from the one before is a keyframe on disk."""
        path = tmp_path / 'session.jsonl.gz'
        with engine_run_environment(mocker):
            _schedule_quit_in_arrival()
            run_engine('--record-trace', str(path))

        with gzip_lines(path) as lines:
            kinds = [line['kind'] for line in lines[1:]]

        expected_keyframes = {0, TRANSITION_START_FRAME}
        assert [index for index, kind in enumerate(kinds) if kind == 'keyframe'] == sorted(
            expected_keyframes
        )

    def test_teardown_logs_path_and_frame_count(self, mocker, tmp_path, caplog):
        """The recorder logs where it wrote and how many frames, once, at teardown."""
        path = tmp_path / 'session.jsonl.gz'
        with engine_run_environment(mocker), caplog.at_level('INFO', logger='game.recording'):
            _schedule_quit_in_arrival()
            run_engine('--record-trace', str(path))

        frame_count = len(read_trace_result(path=path).trace['frames'])
        recording_messages = [
            record.getMessage() for record in caplog.records if record.name == 'game.recording'
        ]
        assert recording_messages == [f'Recorded {frame_count} frames to {path}']

    def test_off_by_default(self, mocker, tmp_path, monkeypatch):
        """Without --record-trace no recorder is constructed and no file is written."""
        monkeypatch.chdir(tmp_path)
        recorder_class = mocker.patch.object(game_engine_module, 'GameplayRecorder')
        with engine_run_environment(mocker):
            _schedule_quit_in_arrival()
            engine = run_engine()

        recorder_class.assert_not_called()
        assert engine.trace_recorder is None
        assert list(tmp_path.iterdir()) == []
        assert len(Script.logic_dts) == TRANSITION_START_FRAME + TRANSITION_FRAME_COUNT + 4

    def test_frame_ending_with_no_scene_is_still_recorded(self, mocker, tmp_path):
        """A transition to None ends the game; that last frame is written with no scene."""
        path = tmp_path / 'session.jsonl.gz'

        def transition_to_nothing() -> None:
            active_scene = SceneManager().active_scene
            assert active_scene is not None
            active_scene.transition_to(None, ScriptedTransition())

        with engine_run_environment(mocker):
            Script.action_frame = 1
            Script.action = transition_to_nothing
            run_engine('--record-trace', str(path))

        result = read_trace_result(path=path)
        frames = result.trace['frames']
        assert result.is_complete
        assert [frame['frame'] for frame in frames] == [0, 1]
        assert frames[1]['scene'] is None
        assert frames[1]['sprites'] == []

    @pytest.mark.parametrize(
        ('signal_name', 'expected_exit_code'),
        [
            ('SIGTERM', ExitCode.TERMINATED),
            ('SIGHUP', ExitCode.HANGUP),
            ('SIGBREAK', ExitCode.BREAK),
        ],
    )
    def test_a_terminating_signal_ends_the_run_and_closes_the_recording(
        self, mocker, tmp_path, signal_name, expected_exit_code
    ):
        """The signal while recording unwinds through the shutdown path; the file is complete."""
        signal_number = platform_signal(signal_name)
        path = tmp_path / 'session.jsonl.gz'
        previous_handler = signal.signal(signal_number, signal.SIG_DFL)
        try:
            with engine_run_environment(mocker):
                # Call the installed handler as the signal would (a real signal with no
                # handler installed would kill the test worker)
                Script.action_frame = 2
                Script.action = lambda: call_signal_handler(signal_number=signal_number)
                with pytest.raises(SystemExit) as exit_info:
                    run_engine('--record-trace', str(path))
            handler_after_run = signal.getsignal(signal_number)
        finally:
            signal.signal(signal_number, previous_handler)

        result = read_trace_result(path=path)
        assert exit_info.value.code == expected_exit_code
        assert result.is_complete
        # Frames 0 and 1 finished; frame 2 was interrupted inside its logic
        assert [frame['frame'] for frame in result.trace['frames']] == [0, 1]
        assert handler_after_run == signal.SIG_DFL

    def test_sigint_ends_the_run_and_closes_the_recording(self, mocker, tmp_path):
        """Ctrl-C (KeyboardInterrupt) while recording still closes the file at teardown."""
        path = tmp_path / 'session.jsonl.gz'

        def interrupt() -> None:
            raise KeyboardInterrupt

        with engine_run_environment(mocker):
            Script.action_frame = 1
            Script.action = interrupt
            with pytest.raises(SystemExit) as exit_info:
                run_engine('--record-trace', str(path))

        result = read_trace_result(path=path)
        assert exit_info.value.code == ExitCode.INTERRUPTED
        assert result.is_complete
        assert [frame['frame'] for frame in result.trace['frames']] == [0]

    @pytest.mark.parametrize('signal_name', ['SIGTERM', 'SIGHUP', 'SIGBREAK'])
    def test_existing_signal_handler_is_left_alone(self, mocker, tmp_path, signal_name):
        """A game that installed its own handler for a signal (Bitmappy) keeps it."""
        signal_number = platform_signal(signal_name)
        path = tmp_path / 'session.jsonl.gz'
        observed_handlers: list[object] = []

        def game_handler(_signal_number: int, _frame: object) -> None:
            return None

        previous_handler = signal.signal(signal_number, game_handler)
        try:
            with engine_run_environment(mocker):
                Script.events_by_frame = {2: [pygame.event.Event(pygame.QUIT)]}
                Script.action_frame = 1
                Script.action = lambda: observed_handlers.append(signal.getsignal(signal_number))
                run_engine('--record-trace', str(path))
            handler_after_run = signal.getsignal(signal_number)
        finally:
            signal.signal(signal_number, previous_handler)

        assert observed_handlers == [game_handler]
        assert handler_after_run is game_handler

    def test_recording_holds_input_changes_and_control_events(self, mocker, tmp_path):
        """Control events land in their frame; polled input is recorded as changes."""
        recording_path = tmp_path / 'session.jsonl.gz'
        served_snapshots = mocker.spy(LiveSources, 'input_snapshot')
        # engine_run_environment resets Script, so the script is set inside it
        with engine_run_environment(mocker):
            Script.events_by_frame = {
                1: [_key(pygame.KEYDOWN, pygame.K_a, unicode='a')],
                2: [_key(pygame.KEYUP, pygame.K_a)],
            }
            Script.action_frame = 1
            Script.action = lambda: SceneManager().record_control_event(
                kind=BREAKPOINT_KIND, data={'label': 'scripted'}
            )
            _schedule_quit_in_arrival()
            run_engine('--record-trace', str(recording_path), '--random-seed', str(RANDOM_SEED))
        trace = read_trace_result(path=recording_path).trace
        frames = trace['frames']
        assert frames[1][CONTROL_EVENTS_FIELD] == [{'kind': 'breakpoint', 'label': 'scripted'}]
        assert all(CONTROL_EVENTS_FIELD not in frame for frame in frames if frame['frame'] != 1)
        # Folding each frame's input_changes onto the previous frame's snapshot (IDLE_INPUT
        # before the first) rebuilds exactly the snapshot the doors served in that frame.
        # (Posted keys do not change the dummy driver's key state, so which fields change is
        # up to the environment, e.g. mouse focus in frame 0; the fold must hold either way.)
        rebuilt_snapshot = IDLE_INPUT
        for frame, served_snapshot in zip(
            frames, served_snapshots.spy_return_list[: len(frames)], strict=True
        ):
            rebuilt_snapshot = apply_snapshot_changes(
                previous=rebuilt_snapshot, changes=frame.get(INPUT_CHANGES_FIELD, {})
            )
            assert rebuilt_snapshot == served_snapshot

    def test_saves_opened_after_recording_started_are_snapshotted_in_their_frame(
        self, mocker, tmp_path
    ):
        """A save namespace first opened during the run is recorded in that frame."""
        save_directory = tmp_path / 'saves'
        mocker.patch(
            'glitchygames.state.manager.get_save_directory',
            side_effect=lambda app_name: save_directory / app_name,
        )
        DiskSaveManager(app_name='recording-test').save('high_scores', {'scores': [{'score': 900}]})
        recording_path = tmp_path / 'session.jsonl.gz'
        with engine_run_environment(mocker):
            Script.action_frame = 0
            Script.action = lambda: open_saves(app_name='recording-test')
            _schedule_quit_in_arrival()
            run_engine('--record-trace', str(recording_path), '--random-seed', str(RANDOM_SEED))
        frames = read_trace_result(path=recording_path).trace['frames']
        # Opened in frame 0, after recording started: snapshotted into that frame
        (opened,) = [frame[SAVES_OPENED_FIELD] for frame in frames if SAVES_OPENED_FIELD in frame]
        assert opened['recording-test']['high_scores']['data'] == {'scores': [{'score': 900}]}
        assert frames[0]['frame'] == 0
        assert SAVES_OPENED_FIELD in frames[0]

    def test_saves_opened_before_recording_are_in_the_header(self, tmp_path):
        """A store the game opened before recording started is snapshotted into the header."""
        recording_path = tmp_path / 'session.jsonl.gz'

        def write_a_score(scene: Scene) -> None:
            # PaddleSlap opened its saves in __init__, before recording starts
            assert isinstance(scene, paddleslap.Game)
            scene.saves.save('high_scores', {'scores': [{'score': 7}]})

        record_trace(
            'paddleslap',
            frame_count=2,
            recording_path=recording_path,
            before_recording=write_a_score,
        )
        header = read_trace_result(path=recording_path).trace
        assert header[SAVES_HEADER_FIELD]['paddleslap']['high_scores']['data'] == {
            'scores': [{'score': 7}]
        }
        assert all(SAVES_OPENED_FIELD not in frame for frame in header['frames'])

    def test_devices_opened_are_recorded(self, mocker, tmp_path):
        """A device opened during the run: its descriptor, its open answer and its positions."""
        fake_device = mocker.Mock(**{
            'get_instance_id.return_value': 5,
            'get_name.return_value': 'Fake Pad',
            'get_guid.return_value': 'guid',
            'get_numaxes.return_value': 2,
            'get_numbuttons.return_value': 4,
            'get_numhats.return_value': 1,
            'get_numballs.return_value': 0,
            # Polled into the input snapshot every frame from the frame it was opened
            'get_axis.return_value': 0.5,
            'get_button.return_value': False,
            'get_hat.return_value': (0, 1),
        })
        mocker.patch.object(devices_module.pygame.joystick, 'Joystick', return_value=fake_device)
        recording_path = tmp_path / 'session.jsonl.gz'
        with engine_run_environment(mocker):
            Script.action_frame = 1
            Script.action = lambda: active_sources().devices().open_joystick(device_index=0)
            _schedule_quit_in_arrival()
            run_engine('--record-trace', str(recording_path), '--random-seed', str(RANDOM_SEED))
        frames = read_trace_result(path=recording_path).trace['frames']
        assert frames[1][DEVICES_OPENED_FIELD] == [
            {
                'kind': 'joystick',
                'device_index': 0,
                'instance_id': 5,
                'name': 'Fake Pad',
                'guid': 'guid',
                'axis_count': 2,
                'button_count': 4,
                'hat_count': 1,
                'ball_count': 0,
            }
        ]
        assert frames[1][DEVICE_ENUMERATION_FIELD] == [
            {'call': 'open_joystick', 'device_index': 0, 'value': 5, 'error': None}
        ]
        assert all(DEVICES_OPENED_FIELD not in frame for frame in frames if frame['frame'] != 1)
        # Opened in frame 1's logic, before its pump: frame 1's snapshot holds its positions,
        # and later frames, where nothing changed, record no change
        frame_one_changes = frames[1][INPUT_CHANGES_FIELD]
        assert frame_one_changes['device_axes'] == {'5': [0.5, 0.5]}
        assert frame_one_changes['device_hats'] == {'5': [[0, 1]]}
        assert all('device_axes' not in frame.get(INPUT_CHANGES_FIELD, {}) for frame in frames[2:])


@contextlib.contextmanager
def gzip_lines(path: Path) -> Generator[list[dict[str, Any]]]:
    """Read a trace file's raw JSON lines (header first).

    Args:
        path: The trace file.

    Yields:
        The decoded lines.

    """
    with gzip.open(path, 'rt', encoding='utf-8') as trace_file:
        yield [json.loads(line) for line in trace_file]


class TestRandomSeed:
    """--random-seed seeds engine_random(); the seed is the engine's random_seed."""

    def test_same_seed_reproduces_engine_random(self):
        """Two engines started with --random-seed 123 draw the same numbers."""
        draws = []
        for _ in range(2):
            GoldenTraceSceneManager.install()
            try:
                with command_line(['--log-level', 'warning', '--random-seed', '123']):
                    engine = GoldenTraceEngine(game=DepartureRecordedScene)
                assert engine.random_seed == RANDOM_SEED
                draws.append([engine_random().random() for _ in range(10)])
            finally:
                GoldenTraceSceneManager.uninstall()

        assert draws[0] == draws[1]

    def test_no_seed_comes_from_secrets(self, mocker):
        """Without --random-seed the engine draws a 64-bit seed from secrets."""
        mocker.patch('glitchygames.randomness.secrets.randbits', return_value=55)
        GoldenTraceSceneManager.install()
        try:
            with command_line(['--log-level', 'warning']):
                engine = GoldenTraceEngine(game=DepartureRecordedScene)
        finally:
            GoldenTraceSceneManager.uninstall()

        assert engine.random_seed == 55


def test_recording_matches_the_golden_harness_frames(mocker, tmp_path):
    """Recording a golden script gives the harness's own sprite frames, plus dt and events.

    The Clockwork Keep script runs 900 frames with an elevator ride (a transition) and a pause:
    the recording holds exactly one frame per main-loop frame, numbered 0..899.
    """
    path = tmp_path / 'clockwork_keep.jsonl.gz'
    transition_frames = mocker.spy(SceneManager, '_process_transition_events')

    golden = record_trace(
        'clockwork_keep', frame_count=CLOCKWORK_KEEP_RECORDED_FRAMES, recording_path=path
    )
    result = read_trace_result(path=path)

    assert result.is_complete
    recorded_frames = result.trace['frames']
    assert [frame['frame'] for frame in recorded_frames] == list(
        range(CLOCKWORK_KEEP_RECORDED_FRAMES)
    )
    # The run really contains transition frames and paused frames
    assert transition_frames.call_count > 0
    assert 'PauseScene' in {frame['scene'] for frame in recorded_frames}
    sprite_frames = [
        {field: value for field, value in frame.items() if field not in RECORDING_FRAME_FIELDS}
        for frame in recorded_frames
    ]
    assert sprite_frames == golden['frames']
    assert {frame[DT_FIELD] for frame in recorded_frames} == {FRAME_SECONDS}
    # The script taps K_UP before frame 10 and presses K_RIGHT before frame 70
    assert [(event.type, event.dict['key']) for event in _scripted_events(recorded_frames[10])] == [
        (pygame.KEYDOWN, pygame.K_UP)
    ]
    assert [(event.type, event.dict['key']) for event in _scripted_events(recorded_frames[70])] == [
        (pygame.KEYDOWN, pygame.K_RIGHT)
    ]


@contextlib.contextmanager
def constructed_engine(*arguments: str) -> Generator[GoldenTraceEngine]:
    """Construct (not start) an engine with DepartureRecordedScene as its game.

    Args:
        *arguments: Extra command-line arguments.

    Yields:
        The engine.

    """
    GoldenTraceSceneManager.install()
    try:
        with command_line(['--log-level', 'warning', *arguments]):
            yield GoldenTraceEngine(game=DepartureRecordedScene)
    finally:
        GoldenTraceSceneManager.uninstall()


class TestRecordingEdgeCases:
    """Recording set-up that the normal run does not reach."""

    def test_the_engine_turns_off_sdls_signal_handlers(self, monkeypatch):
        """SDL must not turn SIGINT/SIGTERM into QUIT events: the engine owns the signals."""
        monkeypatch.delenv('SDL_NO_SIGNAL_HANDLERS', raising=False)
        with constructed_engine():
            assert os.environ['SDL_NO_SIGNAL_HANDLERS'] == '1'

    def test_a_preset_sdl_signal_handler_hint_is_kept(self, monkeypatch):
        monkeypatch.setenv('SDL_NO_SIGNAL_HANDLERS', '0')
        with constructed_engine():
            assert os.environ['SDL_NO_SIGNAL_HANDLERS'] == '0'

    def test_pygame_initialized_before_the_engine_is_warned_about(self, mocker, caplog):
        mocker.patch.object(game_engine_module.pygame, 'get_init', return_value=True)
        with constructed_engine():
            pass
        assert 'SDL may own SIGINT and SIGTERM' in caplog.text

    def test_a_real_sigterm_ends_a_live_run_as_terminated_not_as_a_quit(self, tmp_path):
        """End to end, without recording: the engine's handler, not SDL's QUIT, ends the run."""
        game_file = tmp_path / 'self_terminating_game.py'
        game_file.write_text(SELF_TERMINATING_GAME_SOURCE, encoding='utf-8')
        process = run_self_terminating_game(game_file=game_file, extra_arguments=())
        assert process.returncode == ExitCode.TERMINATED, process.stdout

    def test_a_real_sigterm_ends_a_recording_run_as_terminated_not_as_a_quit(self, tmp_path):
        """End to end: a delivered SIGTERM is never an SDL QUIT event, in the run or the file."""
        game_file = tmp_path / 'self_terminating_game.py'
        game_file.write_text(SELF_TERMINATING_GAME_SOURCE, encoding='utf-8')
        recording_path = tmp_path / 'terminated.jsonl.gz'
        process = run_self_terminating_game(
            game_file=game_file, extra_arguments=('--record-trace', str(recording_path))
        )

        assert process.returncode == ExitCode.TERMINATED, process.stdout
        result = read_trace_result(path=recording_path)
        assert result.is_complete
        recorded_events = [
            event
            for frame in result.trace['frames']
            for batch in frame['event_batches']
            for event in batch
        ]
        assert all(event['type'] != pygame.QUIT for event in recorded_events)

    def test_signal_handlers_are_skipped_off_the_main_thread(self):
        """signal.signal only works on the main thread; elsewhere recording goes on without it."""
        with constructed_engine() as engine:
            original_handlers = {
                signal_number: signal.getsignal(signal_number)
                for signal_number in game_engine_module.terminating_signals()
            }
            install_thread = threading.Thread(target=engine._install_signal_handlers)
            install_thread.start()
            install_thread.join()

            assert engine._installed_signal_handlers == []
            assert {
                signal_number: signal.getsignal(signal_number)
                for signal_number in original_handlers
            } == original_handlers

    def test_header_without_installed_package_metadata(self, mocker):
        """Running from a source tree without package metadata records engine_version null."""
        mocker.patch.object(
            game_engine_module.importlib.metadata,
            'version',
            side_effect=importlib.metadata.PackageNotFoundError('glitchygames'),
        )
        with constructed_engine() as engine:
            assert engine.trace_recording_header()['engine_version'] is None

    def test_signal_handler_ignores_repeats_until_restored(self):
        """After the first SIGTERM, more SIGTERMs are ignored so teardown can finish."""
        previous_handler = signal.signal(signal.SIGTERM, game_engine_module.exit_on_signal)
        try:
            with pytest.raises(SystemExit) as exit_info:
                game_engine_module.exit_on_signal(signal.SIGTERM, None)
            handler_after_signal = signal.getsignal(signal.SIGTERM)
        finally:
            signal.signal(signal.SIGTERM, previous_handler)

        assert exit_info.value.code == ExitCode.TERMINATED
        assert handler_after_signal == signal.SIG_IGN

    def test_starting_a_second_recording_is_refused(self, tmp_path):
        """A second start_trace_recording would wrap the doors twice: it raises instead."""
        with constructed_engine() as engine:
            engine.start_trace_recording(path=tmp_path / 'first.jsonl.gz')
            try:
                with pytest.raises(TraceRecordingAlreadyStartedError):
                    engine.start_trace_recording(path=tmp_path / 'second.jsonl.gz')
                installed_sources = active_sources()
            finally:
                engine.stop_trace_recording()

        assert isinstance(installed_sources, RecordingSources)
        assert isinstance(installed_sources.inner, LiveSources)
        assert not (tmp_path / 'second.jsonl.gz').exists()

    def test_recording_records_saves_opened_by_any_doors(self, tmp_path, mocker):
        """Header saves come from the doors' opened_save_namespaces, whatever doors they are."""
        # Doors that are not LiveSources (a replay's hand out memory stores)
        store = MemorySaveManager(app_name='other-doors', snapshot={})
        store.save('progress', {'level': 4})
        live_sources = LiveSources(random_seed=RANDOM_SEED)
        other_sources = mocker.Mock(
            wraps=live_sources,
            random_seed=RANDOM_SEED,
            opened_save_namespaces={'other-doors': store},
        )
        path = tmp_path / 'session.jsonl.gz'
        with constructed_engine() as engine:
            install_sources(sources=other_sources)
            engine.start_trace_recording(path=path)
            engine.stop_trace_recording()

        header = read_trace_result(path=path).trace
        assert header[SAVES_HEADER_FIELD]['other-doors']['progress']['data'] == {'level': 4}

    def test_stop_without_a_recording_does_nothing(self):
        """stop_trace_recording is safe to call when nothing is recording (every teardown)."""
        with constructed_engine() as engine:
            engine.stop_trace_recording()

            assert engine.trace_recorder is None
