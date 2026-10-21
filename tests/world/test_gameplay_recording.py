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
import platform
import signal
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
from glitchygames.randomness import engine_random
from glitchygames.recording import (
    DT_FIELD,
    EVENT_BATCHES_FIELD,
    EXTERNAL_ORIGIN,
    INTERNAL_ORIGIN,
    RECORDING_SOURCE,
    UnrepresentableValue,
    event_from_record,
)
from glitchygames.scenes import Scene, SceneManager
from glitchygames.scenes import scene as scene_module
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


def call_sigterm_handler() -> None:
    """Call the installed SIGTERM handler the way a delivered SIGTERM would."""
    handler = signal.getsignal(signal.SIGTERM)
    assert callable(handler), f'No SIGTERM handler is installed (found {handler!r})'
    handler(signal.SIGTERM, None)


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
        assert engine.scene_manager.trace_recorder is None
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

    def test_sigterm_ends_the_run_and_closes_the_recording(self, mocker, tmp_path):
        """SIGTERM while recording unwinds through the shutdown path; the file is complete."""
        path = tmp_path / 'session.jsonl.gz'
        previous_handler = signal.signal(signal.SIGTERM, signal.SIG_DFL)
        try:
            with engine_run_environment(mocker):
                # Call the installed handler as the signal would (a real SIGTERM with no
                # handler installed would kill the test worker)
                Script.action_frame = 2
                Script.action = call_sigterm_handler
                with pytest.raises(SystemExit) as exit_info:
                    run_engine('--record-trace', str(path))
            handler_after_run = signal.getsignal(signal.SIGTERM)
        finally:
            signal.signal(signal.SIGTERM, previous_handler)

        result = read_trace_result(path=path)
        assert exit_info.value.code == 128 + signal.SIGTERM
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
            with pytest.raises(KeyboardInterrupt):
                run_engine('--record-trace', str(path))

        result = read_trace_result(path=path)
        assert result.is_complete
        assert [frame['frame'] for frame in result.trace['frames']] == [0]

    def test_existing_sigterm_handler_is_left_alone(self, mocker, tmp_path):
        """A game that installed its own SIGTERM handler (Bitmappy) keeps it."""
        path = tmp_path / 'session.jsonl.gz'
        observed_handlers: list[object] = []

        def game_handler(_signal_number: int, _frame: object) -> None:
            return None

        previous_handler = signal.signal(signal.SIGTERM, game_handler)
        try:
            with engine_run_environment(mocker):
                Script.events_by_frame = {2: [pygame.event.Event(pygame.QUIT)]}
                Script.action_frame = 1
                Script.action = lambda: observed_handlers.append(signal.getsignal(signal.SIGTERM))
                run_engine('--record-trace', str(path))
            handler_after_run = signal.getsignal(signal.SIGTERM)
        finally:
            signal.signal(signal.SIGTERM, previous_handler)

        assert observed_handlers == [game_handler]
        assert handler_after_run is game_handler


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
        {
            field: value
            for field, value in frame.items()
            if field not in {DT_FIELD, EVENT_BATCHES_FIELD}
        }
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

    def test_sigterm_handler_is_skipped_off_the_main_thread(self):
        """signal.signal only works on the main thread; elsewhere recording goes on without it."""
        with constructed_engine() as engine:
            original_handler = signal.getsignal(signal.SIGTERM)
            install_thread = threading.Thread(target=engine._install_sigterm_handler)
            install_thread.start()
            install_thread.join()

            assert engine._installed_sigterm_handler is False
            assert signal.getsignal(signal.SIGTERM) == original_handler

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

        assert exit_info.value.code == 128 + signal.SIGTERM
        assert handler_after_signal == signal.SIG_IGN

    def test_stop_without_a_recording_does_nothing(self):
        """stop_trace_recording is safe to call when nothing is recording (every teardown)."""
        with constructed_engine() as engine:
            engine.stop_trace_recording()

            assert engine.trace_recorder is None
