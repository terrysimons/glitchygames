"""``--compare-trace OLD``, the onion skin (glitchygames/replay/tools/compare.py).

A stand-in game whose whole window is one color, named by the run's seed, gives every frame a
known picture: OLD recorded under ``OLD_SEED`` is red ``OLD_SEED``, and NEW (OLD replayed under
``NEW_SEED``: the seed rule's row 5, which compares and writes nothing) is red ``NEW_SEED``. So a
pixel of the presented frame is exactly the mix of the two at the compare alpha.

The watched replays run in this process on SDL's dummy driver (the test session's), their
viewer's clock faked (``WatchedReplay``): the viewer's keys are posted whenever it waits for
them. OLD is replayed by a real child process, as it always is.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import importlib
import os
import socket
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pygame
import pytest

from glitchygames.argument_types import percent_from_zero_to_one_hundred
from glitchygames.engine import GameEngine
from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, run_command
from glitchygames.replay import viewer as viewer_module
from glitchygames.replay.driver import ReplaySources
from glitchygames.replay.rebuild import restart_command
from glitchygames.replay.tools import compare
from glitchygames.replay.tools.children import running_game_command
from glitchygames.replay.tools.compare import (
    DEFAULT_COMPARE_ALPHA_PERCENT,
    FRAME_HEADER,
    OLD_ENDED_LABEL,
    OLD_NOT_REPLAYED_LABEL,
    FrameStream,
    OnionSkin,
    first_streamed_frame,
    old_game_command,
)
from glitchygames.replay.tools.golden_traces import (
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    command_line,
)
from glitchygames.replay.tools.registry import (
    TOOLS,
    build_command_parser,
    tool_named,
    tool_summary,
)
from glitchygames.sources import active_sources
from glitchygames.tracing import read_trace_result
from tests.demo_runs import engine_run_environment
from tests.replay.replay_helpers import replay_through_engine, rewrite_recording
from tests.stand_in_games import (
    StandInGame,
    record_stand_in_game,
    use_stand_in_game,
    write_stand_in_distribution,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from glitchygames.scenes import Scene

# tests/demo_runs.py's engine environment (a generator its fixtures yield from), as a context
engine_environment = contextlib.contextmanager(engine_run_environment)
# The color game: its package, console script and scene
PACKAGE = 'stand_in_colors'
CONSOLE_SCRIPT = 'stand-in-colors'
SCENE_NAME = 'StandInColorsScene'
# It quits itself after this many frames: enough to step past and run on from a pause. A replay
# of it ends in its last frame (the recorded quit), so that frame is never presented
COLOR_GAME_FRAMES = 6
# The seeds OLD is recorded under and NEW is replayed under: each is the red of its picture
OLD_SEED = 200
NEW_SEED = 100
OLD_RED = (OLD_SEED, 0, 0)
NEW_RED = (NEW_SEED, 0, 0)
# A pixel away from the status bar (bottom) and the OLD-ended label (top)
SAMPLE_POINT = (8, 100)
# The stand-in games' window size (tests/stand_in_games.py records at 320x240)
STAND_IN_SIZE = (320, 240)
# How long the end-to-end children may run
CHILD_TIMEOUT_SECONDS = 120.0

COLOR_GAME_SOURCE = f'''\
"""A stand-in game whose whole window is one color, named by the run's seed."""

import pygame

from glitchygames.engine import GameEngine
from glitchygames.randomness import engine_random_seed
from glitchygames.scenes import Scene

FRAMES_BEFORE_QUIT = {COLOR_GAME_FRAMES}


def seed_color(seed):
    """The seed's color: its low three bytes as red, green and blue."""
    return (seed % 256, seed // 256 % 256, seed // 65536 % 256)


class Backdrop(pygame.sprite.DirtySprite):
    """The whole window, in one color, drawn on every frame."""

    def __init__(self, *, size, color):
        super().__init__()
        self.image = pygame.Surface(size)
        self.image.fill(color)
        self.rect = self.image.get_rect()
        self.dirty = 2

    def update_nested_sprites(self):
        pass


class {SCENE_NAME}(Scene):
    """The one scene: the window in the seed's color; it quits itself."""

    NAME = {SCENE_NAME!r}

    def __init__(self, options=None, groups=None):
        super().__init__(options=options, groups=groups)
        size = pygame.display.get_surface().get_size()
        self.all_sprites.add(Backdrop(size=size, color=seed_color(engine_random_seed())))
        self.frames = 0

    def dt_tick(self, dt):
        self.frames += 1
        if self.frames == FRAMES_BEFORE_QUIT:
            GameEngine.quit_game()


def main():
    """The console script's entry point."""
    GameEngine(game={SCENE_NAME}).start()
'''


@dataclasses.dataclass(frozen=True)
class ColorGame:
    """The color game, installed for one test, and OLD, a recording of it.

    Attributes:
        game: The installed stand-in.
        scene_class: Its scene class, imported in this process (the watched replays run here).
        old: Its recording under ``OLD_SEED``.
        old_frame_count: How many frames OLD holds.

    """

    game: StandInGame
    scene_class: type[Scene]
    old: Path
    old_frame_count: int


def recorded_frame_count(*, path: Path) -> int:
    """Return how many frames a recording holds.

    Returns:
        The count.

    """
    return len(read_trace_result(path=path).trace['frames'])


@pytest.fixture
def color_game(tmp_path, monkeypatch, mocker) -> ColorGame:
    """Install the color game for this test and its children, and record OLD.

    Returns:
        The color game.

    """
    install_directory = tmp_path / 'site-packages'
    package_directory = install_directory / PACKAGE
    package_directory.mkdir(parents=True)
    (package_directory / '__init__.py').write_text(COLOR_GAME_SOURCE, encoding='utf-8')
    write_stand_in_distribution(
        directory=install_directory,
        distribution=CONSOLE_SCRIPT,
        console_scripts={CONSOLE_SCRIPT: f'{PACKAGE}:main'},
    )
    use_stand_in_game(install_directory=install_directory, monkeypatch=monkeypatch)
    # Imported here for the watched replays; gone from sys.modules after the test
    mocker.patch.dict(sys.modules)
    module = importlib.import_module(PACKAGE)
    game = StandInGame(
        package=PACKAGE,
        distribution=CONSOLE_SCRIPT,
        console_script=CONSOLE_SCRIPT,
        scene_name=SCENE_NAME,
        install_directory=install_directory,
        layer=None,
    )
    old = record_stand_in_game(
        game=game,
        path=tmp_path / 'old.jsonl.gz',
        extra_arguments=('--random-seed', str(OLD_SEED)),
    )
    return ColorGame(
        game=game,
        scene_class=getattr(module, SCENE_NAME),
        old=old,
        old_frame_count=recorded_frame_count(path=old),
    )


@dataclasses.dataclass(frozen=True)
class Presented:
    """One presented outer frame of a watched replay.

    Attributes:
        frame_index: The replayed frame whose picture it shows, or None when it shows none of
            its own (before the first frame, rebuilding, or behind the start screen's message).
        sample: The pixel at ``SAMPLE_POINT``, as presented.
        old_frame_index: The OLD frame the onion skin held then (None: none yet).
        label: The onion skin's label then (None: none).

    """

    frame_index: int | None
    sample: tuple[int, int, int]
    old_frame_index: int | None
    label: str | None


@dataclasses.dataclass(frozen=True)
class WatchedRun:
    """How a watched replay in this process went.

    Attributes:
        exit_status: Its exit status (SystemExit's code).
        engine: Its engine.
        presented: Every outer frame it presented, in order.

    """

    exit_status: object
    engine: GameEngine
    presented: list[Presented]

    @property
    def onion_skin(self) -> OnionSkin:
        """The run's onion skin (it must have one)."""
        onion_skin = self.engine.onion_skin
        assert onion_skin is not None
        return onion_skin


def rgb_at(*, surface: pygame.Surface) -> tuple[int, int, int]:
    """Return a surface's red, green and blue at ``SAMPLE_POINT``.

    Returns:
        The color.

    """
    color = surface.get_at(SAMPLE_POINT)
    return (color.r, color.g, color.b)


def presented_frame_index(*, sources: ReplaySources) -> int | None:
    """Return the replayed frame a watched replay presents now.

    Returns:
        The last frame run, or None before any ran, while rebuilding and at the start screen
        (frame 0's picture is behind its message).

    """
    controls = sources.controls
    if (
        controls.rebuild_target_frame is not None
        or controls.awaiting_start
        or controls.current_frame == 0
    ):
        return None
    return sources.controls.current_frame - 1


def watched_replay(
    *,
    mocker: MockerFixture,
    scene_class: type[Scene],
    recording: Path,
    arguments: tuple[str, ...],
    keys: tuple[int, ...] = (pygame.K_SPACE,),
) -> WatchedRun:
    """Replay a recording watched, in this process, on SDL's dummy driver.

    The viewer's clock is faked: its sleeps take no time. Whenever the replay waits for the
    viewer (its start screen, or paused), the next of ``keys`` is pressed; a wait after the last
    fails the test. Each presented frame's ``SAMPLE_POINT`` is kept (``pygame.display.flip``
    is replaced: nothing is shown).

    Args:
        mocker: pytest-mock's fixture.
        scene_class: The game's scene class.
        recording: The recording.
        arguments: More arguments for the game.
        keys: The keys pressed, one per wait.

    Returns:
        How it went.

    """
    remaining_keys = list(keys)
    presented: list[Presented] = []
    clock = {'now': 1000.0}
    engines: list[GameEngine] = []

    def read_clock() -> float:
        return clock['now']

    def wait(*, seconds: float) -> None:
        clock['now'] += seconds
        sources = active_sources()
        assert isinstance(sources, ReplaySources)
        if not (sources.controls.awaiting_start or sources.controls.paused):
            return
        assert remaining_keys, 'the replay waited for the viewer after every key was pressed'
        key = remaining_keys.pop(0)
        for event_type in (pygame.KEYDOWN, pygame.KEYUP):
            pygame.event.post(
                pygame.event.Event(event_type, key=key, mod=0, unicode='', scancode=0, window=None)
            )

    def flip() -> None:
        sources = active_sources()
        assert isinstance(sources, ReplaySources)
        surface = pygame.display.get_surface()
        assert surface is not None
        onion_skin = engines[0].onion_skin if engines else None
        held = None if onion_skin is None else onion_skin.held_frame_index
        presented.append(
            Presented(
                frame_index=presented_frame_index(sources=sources),
                sample=rgb_at(surface=surface),
                old_frame_index=held,
                label=None if onion_skin is None else onion_skin.label,
            )
        )

    mocker.patch.object(viewer_module, 'measured_seconds', side_effect=read_clock)
    mocker.patch.object(viewer_module, 'sleep_for', side_effect=wait)
    mocker.patch.object(viewer_module, 'sleep_coarsely', side_effect=wait)
    mocker.patch.object(pygame.display, 'flip', side_effect=flip)
    with engine_environment(mocker):
        GoldenTraceSceneManager.install()
        try:
            with command_line([
                '--log-level',
                'warning',
                '--replay-trace',
                str(recording),
                *arguments,
            ]):
                engine = GoldenTraceEngine(game=scene_class)
            engines.append(engine)
            with pytest.raises(SystemExit) as exit_info:
                engine.start()
        finally:
            GoldenTraceSceneManager.uninstall()
    return WatchedRun(exit_status=exit_info.value.code, engine=engine, presented=presented)


def blended(*, new: tuple[int, int, int], old: tuple[int, int, int], percent: float) -> tuple:
    """Return OLD drawn over NEW at ``percent``, as an alpha blit mixes them (8-bit alpha).

    Returns:
        The mixed color.

    """
    alpha = round(255 * percent / 100)
    return tuple(
        new_value + (((old_value - new_value) * alpha + old_value) >> 8)
        for new_value, old_value in zip(new, old, strict=True)
    )


@pytest.mark.parametrize(
    ('alpha_arguments', 'percent'),
    [((), DEFAULT_COMPARE_ALPHA_PERCENT), (('--compare-alpha', '25'), 25.0)],
    ids=['default-50', 'alpha-25'],
)
def test_one_blended_frame_has_the_expected_pixels(color_game, mocker, alpha_arguments, percent):
    """Every presented frame is NEW with OLD's same frame over it at the alpha (row 5's colors)."""
    run = watched_replay(
        mocker=mocker,
        scene_class=color_game.scene_class,
        recording=color_game.old,
        arguments=(
            '--random-seed',
            str(NEW_SEED),
            '--compare-trace',
            str(color_game.old),
            *alpha_arguments,
        ),
    )

    assert run.exit_status == ExitCode.SUCCESS
    expected = blended(new=NEW_RED, old=OLD_RED, percent=percent)
    assert expected == ((150, 0, 0) if percent == DEFAULT_COMPARE_ALPHA_PERCENT else (125, 0, 0))
    shown = [frame for frame in run.presented if frame.frame_index is not None]
    assert shown
    for frame in shown:
        assert frame.sample == expected, frame
        assert frame.old_frame_index == frame.frame_index, frame
        assert frame.label is None


def test_without_compare_trace_the_frame_is_new_alone(color_game, mocker):
    """The control: NEW's own picture is NEW's red (so the mix above is OLD's doing)."""
    run = watched_replay(
        mocker=mocker,
        scene_class=color_game.scene_class,
        recording=color_game.old,
        arguments=('--random-seed', str(NEW_SEED)),
    )

    assert run.exit_status == ExitCode.SUCCESS
    assert run.engine.onion_skin is None
    shown = [frame.sample for frame in run.presented if frame.frame_index is not None]
    assert shown
    assert set(shown) == {NEW_RED}


@dataclasses.dataclass(frozen=True)
class StreamedFrame:
    """A frame read from a frame stream.

    Attributes:
        frame_index: Its number.
        size: Its width and height.
        sample: Its pixel at ``SAMPLE_POINT``.

    """

    frame_index: int
    size: tuple[int, int]
    sample: tuple[int, int, int]


def receive_exactly(*, connection: socket.socket, count: int) -> bytes | None:
    """Read ``count`` bytes from a connection, or None at its end.

    Returns:
        The bytes.

    """
    received = bytearray()
    while len(received) < count:
        chunk = connection.recv(count - len(received))
        if not chunk:
            return None
        received.extend(chunk)
    return bytes(received)


class FrameStreamListener:
    """A frame stream's other end: it listens on a port and reads every frame on a thread.

    Attributes:
        port: The port it listens on (``--replay-frame-stream PORT``).

    """

    def __init__(self, *, closes_at_once: bool = False) -> None:
        """Listen, and read on a thread from the first connection.

        Args:
            closes_at_once: Close the connection as soon as it is made, reading nothing.

        """
        self._listener = socket.create_server((compare.FRAME_STREAM_HOST, 0))
        self.port: int = self._listener.getsockname()[1]
        self._closes_at_once = closes_at_once
        self._frames: list[StreamedFrame] = []
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _read(self) -> None:
        connection, _ = self._listener.accept()
        with connection:
            if self._closes_at_once:
                return
            while (
                header := receive_exactly(connection=connection, count=FRAME_HEADER.size)
            ) is not None:
                frame_index, width, height = FRAME_HEADER.unpack(header)
                pixels = receive_exactly(connection=connection, count=width * height * 3)
                assert pixels is not None
                image = pygame.image.frombytes(pixels, (width, height), 'RGB')
                self._frames.append(
                    StreamedFrame(
                        frame_index=frame_index,
                        size=(width, height),
                        sample=rgb_at(surface=image),
                    )
                )

    def finish(self) -> list[StreamedFrame]:
        """Wait for the stream's end and stop listening.

        Returns:
            Every frame read, in order.

        """
        self._thread.join(timeout=CHILD_TIMEOUT_SECONDS)
        assert not self._thread.is_alive()
        self._listener.close()
        return self._frames


@pytest.mark.parametrize(
    ('pause_arguments', 'first_frame'),
    [((), 0), (('--replay-pause-at-frame', '4'), 3)],
    ids=['from-frame-0', 'restarted-at-frame-4'],
)
def test_the_child_streams_one_frame_per_frame_in_order(
    color_game, mocker, caplog, pause_arguments, first_frame
):
    """A headless replay with a frame stream writes each frame once, in order, as presented.

    Restarted at a pause frame N, it writes from the frame a watched restart shows paused there
    (N - 1): the frames before it are rebuilt by the watched replay unshown.
    """
    listener = FrameStreamListener()

    replay = replay_through_engine(
        mocker=mocker,
        scene_class=color_game.scene_class,
        path=color_game.old,
        extra_arguments=('--replay-frame-stream', str(listener.port), *pause_arguments),
    )
    frames = listener.finish()

    assert replay.exit_status == ExitCode.SUCCESS
    assert [frame.frame_index for frame in frames] == list(
        range(first_frame, color_game.old_frame_count)
    )
    assert {frame.size for frame in frames} == {STAND_IN_SIZE}
    assert {frame.sample for frame in frames} == {OLD_RED}
    # The pause frame is the stream's to read: no warning that it is ignored
    assert 'is ignored with --headless' not in caplog.text


def test_a_stream_nobody_reads_any_more_ends_the_replay(color_game, mocker):
    """When the parent is gone, the child stops replaying instead of running on unseen."""
    listener = FrameStreamListener(closes_at_once=True)

    replay = replay_through_engine(
        mocker=mocker,
        scene_class=color_game.scene_class,
        path=color_game.old,
        extra_arguments=('--replay-frame-stream', str(listener.port)),
    )
    listener.finish()

    assert replay.exit_status == ExitCode.SUCCESS
    assert replay.result.end_reason == 'quit'
    assert replay.result.frames_replayed < color_game.old_frame_count


def test_a_shorter_old_holds_its_last_frame_with_the_label(color_game, mocker, tmp_path):
    """OLD's last frame stays over NEW's later ones, labelled with the frame it ended at."""
    short_old = tmp_path / 'short-old.jsonl.gz'
    short_old.write_bytes(color_game.old.read_bytes())
    last_old_frame = 2

    def keep_three_frames(trace: dict[str, Any]) -> None:
        trace['frames'] = trace['frames'][: last_old_frame + 1]

    rewrite_recording(recording_path=short_old, change=keep_three_frames)

    run = watched_replay(
        mocker=mocker,
        scene_class=color_game.scene_class,
        recording=color_game.old,
        arguments=('--random-seed', str(NEW_SEED), '--compare-trace', str(short_old)),
    )

    assert run.exit_status == ExitCode.SUCCESS
    expected = blended(new=NEW_RED, old=OLD_RED, percent=DEFAULT_COMPARE_ALPHA_PERCENT)
    shown = [frame for frame in run.presented if frame.frame_index is not None]
    # The recorded game quits in its last frame, so the replay ends without presenting it
    assert {frame.frame_index for frame in shown} == set(range(1, color_game.old_frame_count - 1))
    for frame in shown:
        assert frame.frame_index is not None
        assert frame.sample == expected, frame
        if frame.frame_index <= last_old_frame:
            assert frame.old_frame_index == frame.frame_index, frame
            assert frame.label is None, frame
        else:
            assert frame.old_frame_index == last_old_frame, frame
            assert frame.label == OLD_ENDED_LABEL.format(frame_index=last_old_frame), frame


def constructed_exit_status(
    *, mocker: MockerFixture, scene_class: type[Scene], arguments: tuple[str, ...]
) -> object:
    """Construct the engine on a command line it refuses in ``__init__``.

    Returns:
        The status it exits with.

    """
    with engine_environment(mocker):
        GoldenTraceSceneManager.install()
        try:
            with (
                command_line(['--log-level', 'warning', *arguments]),
                pytest.raises(SystemExit) as exit_info,
            ):
                GoldenTraceEngine(game=scene_class)
        finally:
            GoldenTraceSceneManager.uninstall()
    return exit_info.value.code


@dataclasses.dataclass(frozen=True)
class Refusal:
    """A --compare-trace the engine refuses, and how.

    Attributes:
        case: What is wrong (the test id).
        exit_code: What it exits with.
        message: What its log says.

    """

    case: str
    exit_code: ExitCode
    message: str


REFUSALS = (
    Refusal(
        case='headless', exit_code=ExitCode.OPTIONS_REFUSED, message='an onion skin is watched'
    ),
    Refusal(case='audit', exit_code=ExitCode.OPTIONS_REFUSED, message='not with --audit'),
    Refusal(case='rebaseline', exit_code=ExitCode.OPTIONS_REFUSED, message='not with --rebaseline'),
    Refusal(
        case='different-size',
        exit_code=ExitCode.UNUSABLE_INPUT,
        message='OLD was recorded on a 160x120 display',
    ),
    Refusal(case='missing', exit_code=ExitCode.MISSING_INPUT, message='no such recording'),
    Refusal(
        case='not-a-recording',
        exit_code=ExitCode.UNUSABLE_INPUT,
        message='not a readable recording',
    ),
)


@pytest.mark.parametrize('refusal', REFUSALS, ids=[refusal.case for refusal in REFUSALS])
def test_compare_trace_refuses_headless_audit_rebaseline_and_different_sizes(
    color_game, mocker, tmp_path, caplog, refusal
):
    """Each is refused before anything runs: no window, no child, nothing written."""
    case = refusal.case
    old = color_game.old
    rebaselined = tmp_path / 'rebaselined.jsonl.gz'
    extra: tuple[str, ...] = ()
    if case == 'headless':
        extra = ('--headless',)
    elif case == 'audit':
        extra = ('--audit',)
    elif case == 'rebaseline':
        extra = ('--rebaseline', str(rebaselined))
    elif case == 'different-size':
        old = record_stand_in_game(
            game=color_game.game,
            path=tmp_path / 'small.jsonl.gz',
            extra_arguments=('--resolution', '160x120'),
        )
    elif case == 'missing':
        old = tmp_path / 'missing.jsonl.gz'
    else:
        old = tmp_path / 'not-a-recording.jsonl.gz'
        old.write_text('not a recording\n', encoding='utf-8')
    start_command = mocker.spy(compare, 'start_command')

    status = constructed_exit_status(
        mocker=mocker,
        scene_class=color_game.scene_class,
        arguments=('--replay-trace', str(color_game.old), '--compare-trace', str(old), *extra),
    )

    assert status == refusal.exit_code
    assert refusal.message in caplog.text
    start_command.assert_not_called()
    assert not rebaselined.exists()


def test_the_command_passes_the_compare_options_to_the_game(tmp_path):
    """``glitchygames replay-trace NEW --compare-trace OLD --compare-alpha 25`` passes them on."""
    arguments = build_command_parser().parse_args([
        'replay-trace',
        'new.jsonl.gz',
        '--compare-trace',
        'old.jsonl.gz',
        '--compare-alpha',
        '25',
        '--project-root',
        str(tmp_path),
    ])

    assert tool_named(name='replay-trace').child_arguments(arguments=arguments) == [
        '--replay-trace',
        str(Path('new.jsonl.gz').absolute()),
        '--compare-trace',
        str(Path('old.jsonl.gz').absolute()),
        '--compare-alpha',
        '25.0',
    ]


@pytest.mark.parametrize('front_end', ['game-flag', 'command'])
def test_compare_trace_through_both_front_ends(color_game, front_end):
    """The options reach the game either way: here the game refuses a headless onion skin.

    A watched compare runs to its end only when someone presses Space, which a child cannot be
    given; the watched runs above are this process's, through the game flag.
    """
    compare_arguments = [
        str(color_game.old),
        '--compare-trace',
        str(color_game.old),
        '--compare-alpha',
        '25',
        '--headless',
    ]
    if front_end == 'game-flag':
        command = [
            sys.executable,
            '-c',
            f'import {PACKAGE}; {PACKAGE}.main()',
            '--replay-trace',
            *compare_arguments,
        ]
    else:
        command = [sys.executable, '-m', 'glitchygames', 'replay-trace', *compare_arguments]

    completed = run_command(
        command=command,
        environment=os.environ,
        timeout_seconds=CHILD_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
    )

    assert completed.returncode == ExitCode.OPTIONS_REFUSED, completed.stdout
    assert 'an onion skin is watched' in completed.stdout


def raising_on_tick(*, scene_class: type[Scene], tick_number: int, error: BaseException) -> Any:
    """Return a ``dt_tick`` running the scene's own until its ``tick_number``-th call, then raising.

    Returns:
        The replacement.

    """
    original = scene_class.dt_tick
    calls = {'count': 0}

    def dt_tick(self: Scene, dt: float) -> None:
        calls['count'] += 1
        if calls['count'] == tick_number:
            raise error
        original(self, dt)

    return dt_tick


@pytest.mark.parametrize(
    ('ending', 'exit_code'),
    [
        ('ends', ExitCode.SUCCESS),
        ('fails-before-a-frame-is-shown', ExitCode.INTERNAL_ERROR),
        ('interrupted', ExitCode.INTERRUPTED),
    ],
)
def test_the_child_is_reaped_when_the_replay_ends_or_fails(color_game, mocker, ending, exit_code):
    """However the replay ends, OLD's child has ended and been waited for."""
    if ending == 'fails-before-a-frame-is-shown':
        mocker.patch.object(
            color_game.scene_class,
            'dt_tick',
            raising_on_tick(
                scene_class=color_game.scene_class,
                tick_number=1,
                error=RuntimeError('the game failed'),
            ),
        )
    elif ending == 'interrupted':
        mocker.patch.object(
            color_game.scene_class,
            'dt_tick',
            raising_on_tick(
                scene_class=color_game.scene_class, tick_number=3, error=KeyboardInterrupt()
            ),
        )

    run = watched_replay(
        mocker=mocker,
        scene_class=color_game.scene_class,
        recording=color_game.old,
        arguments=('--random-seed', str(NEW_SEED), '--compare-trace', str(color_game.old)),
    )

    assert run.exit_status == exit_code
    onion_skin = run.onion_skin
    if ending == 'fails-before-a-frame-is-shown':
        # Nothing was drawn, so OLD was never started
        assert onion_skin.process is None
    else:
        assert onion_skin.process is not None
        assert onion_skin.process.returncode is not None
    assert onion_skin.is_stopped


def test_a_step_back_restarts_the_child_at_the_same_frame(color_game, mocker):
    """A restart keeps --compare-trace; its child starts at the frame the restart pauses on."""
    restarted = restart_command(
        original=[
            'python',
            'game.py',
            '--replay-trace',
            'new.jsonl.gz',
            '--compare-trace',
            'old.jsonl.gz',
            '--compare-alpha',
            '25',
        ],
        recording_path=Path('new.jsonl.gz'),
        pause_at_frame=4,
        debug_overlay_visible=False,
    )
    assert restarted[2:6] == ['--compare-trace', 'old.jsonl.gz', '--compare-alpha', '25']
    assert restarted[-2:] == ['--replay-pause-at-frame', '4']

    # The restarted replay itself: rebuilt to frame 4 unshown, paused with frame 3 shown, then
    # Space runs it on to its end
    run = watched_replay(
        mocker=mocker,
        scene_class=color_game.scene_class,
        recording=color_game.old,
        arguments=(
            '--random-seed',
            str(NEW_SEED),
            '--compare-trace',
            str(color_game.old),
            '--replay-pause-at-frame',
            '4',
        ),
    )

    assert run.exit_status == ExitCode.SUCCESS
    command = run.onion_skin.command
    assert command[command.index('--replay-pause-at-frame') + 1] == '4'
    shown = [frame for frame in run.presented if frame.frame_index is not None]
    assert shown[0].frame_index == 3
    for frame in shown:
        assert frame.old_frame_index == frame.frame_index, frame
    # The child skipped the frames the restart rebuilt unshown: none of them was sent, only
    # each frame shown
    assert run.onion_skin.frames_received == len({frame.frame_index for frame in shown})


def test_first_streamed_frame_is_the_frame_a_restart_shows_paused():
    """No pause frame: 0; pause frame N: N - 1 (a pause frame of 0 pauses after frame 0)."""
    assert first_streamed_frame(pause_at_frame=None) == 0
    assert first_streamed_frame(pause_at_frame=0) == 0
    assert first_streamed_frame(pause_at_frame=1) == 0
    assert first_streamed_frame(pause_at_frame=4) == 3


@pytest.mark.parametrize(
    ('text', 'parsed'), [('0', 0.0), ('25', 25.0), ('100', 100.0), ('12.5', 12.5)]
)
def test_the_compare_alpha_is_a_percent_from_0_to_100(text, parsed):
    """The values from 0 to 100 are read; the game and the command read it alike."""
    assert percent_from_zero_to_one_hundred(text) == parsed
    game = GameEngine.args(argparse.ArgumentParser())
    assert game.parse_args(['--compare-alpha', text]).compare_alpha == parsed


@pytest.mark.parametrize('text', ['-1', '100.5', 'nan', 'inf', 'half'])
def test_a_compare_alpha_outside_0_to_100_is_refused(text, capsys):
    """Refused by the parser, on the game and on the command, before anything runs."""
    with pytest.raises(argparse.ArgumentTypeError):
        percent_from_zero_to_one_hundred(text)
    with pytest.raises(SystemExit) as exit_info:
        GameEngine.args(argparse.ArgumentParser()).parse_args(['--compare-alpha', text])
    assert exit_info.value.code == ExitCode.ARGUMENT_PARSER_ERROR
    with pytest.raises(SystemExit) as exit_info:
        build_command_parser().parse_args(['replay-trace', 'new', '--compare-alpha', text])
    assert exit_info.value.code == ExitCode.ARGUMENT_PARSER_ERROR
    assert '--compare-alpha' in capsys.readouterr().err


def test_the_frame_stream_option_is_hidden_on_both_front_ends():
    """``--replay-frame-stream`` is internal: parsed on both front ends, shown in neither's help."""
    game = GameEngine.args(argparse.ArgumentParser())
    command = build_command_parser()
    replay_trace = tool_named(name='replay-trace')

    assert game.parse_args(['--replay-frame-stream', '5']).replay_frame_stream == 5
    assert (
        command.parse_args([
            'replay-trace',
            'new',
            '--replay-frame-stream',
            '5',
        ]).replay_frame_stream
        == 5
    )
    assert '--replay-frame-stream' not in game.format_help()
    assert '--replay-frame-stream' not in command.format_help()
    assert '--replay-frame-stream' not in tool_summary(tool=replay_trace)
    assert '--compare-trace' in tool_summary(tool=replay_trace)
    assert {tool.name for tool in TOOLS if any(option.hidden for option in tool.options)} == {
        'replay-trace'
    }


def test_a_frame_stream_needs_headless(color_game, mocker, caplog):
    """The frame stream is a headless replay's: a watched one is refused."""
    status = constructed_exit_status(
        mocker=mocker,
        scene_class=color_game.scene_class,
        arguments=('--replay-trace', str(color_game.old), '--replay-frame-stream', '1'),
    )

    assert status == ExitCode.OPTIONS_REFUSED
    assert '--replay-frame-stream needs --headless' in caplog.text


def test_a_frame_stream_with_nobody_listening_is_refused(color_game, mocker, caplog):
    """No parent on the port: the child says so and exits before replaying anything."""
    with socket.create_server((compare.FRAME_STREAM_HOST, 0)) as unused:
        port = unused.getsockname()[1]

    status = constructed_exit_status(
        mocker=mocker,
        scene_class=color_game.scene_class,
        arguments=(
            '--replay-trace',
            str(color_game.old),
            '--headless',
            '--replay-frame-stream',
            str(port),
        ),
    )

    assert status == ExitCode.SERVICE_UNAVAILABLE
    assert f'Cannot stream frames to port {port}' in caplog.text


@pytest.mark.parametrize(
    'arguments',
    [
        ('--compare-trace', 'old.jsonl.gz'),
        ('--compare-alpha', '25'),
        ('--replay-frame-stream', '5'),
    ],
)
def test_without_a_replay_the_compare_options_are_ignored_with_a_warning(
    color_game, mocker, caplog, arguments
):
    """A live run given them warns that they do nothing (as --replay-fps does)."""
    with engine_environment(mocker):
        GoldenTraceSceneManager.install()
        try:
            with command_line(['--log-level', 'warning', '--headless', *arguments]):
                GoldenTraceEngine(game=color_game.scene_class)
        finally:
            GoldenTraceSceneManager.uninstall()

    assert f'{arguments[0]} is ignored without --replay-trace' in caplog.text


def test_a_compare_alpha_without_compare_trace_is_ignored_with_a_warning(
    color_game, mocker, caplog
):
    """A replay given --compare-alpha alone draws nothing over NEW, and says so."""
    with engine_environment(mocker):
        GoldenTraceSceneManager.install()
        try:
            with command_line([
                '--log-level',
                'warning',
                '--replay-trace',
                str(color_game.old),
                '--compare-alpha',
                '25',
            ]):
                engine = GoldenTraceEngine(game=color_game.scene_class)
        finally:
            GoldenTraceSceneManager.uninstall()

    assert engine.onion_skin is None
    assert '--compare-alpha is ignored without --compare-trace' in caplog.text


def surface_of(*, color: tuple[int, int, int]) -> pygame.Surface:
    """Return a stand-in-sized surface of one color (NEW's presented frame).

    Returns:
        The surface.

    """
    surface = pygame.Surface(STAND_IN_SIZE)
    surface.fill(color)
    return surface


@dataclasses.dataclass(frozen=True)
class SilentChild:
    """A child that streams no frame.

    Attributes:
        name: The test id.
        game_command: Its command.
        connect_timeout_seconds: How long the onion skin waits for it to connect.
        status: The exit status it ends with (None: stopped, by a signal).

    """

    name: str
    game_command: tuple[str, ...]
    connect_timeout_seconds: float
    status: ExitCode | None


SILENT_CHILDREN = (
    SilentChild(
        name='exits-without-connecting',
        game_command=(sys.executable, '-c', 'raise SystemExit(65)'),
        connect_timeout_seconds=60.0,
        status=ExitCode.UNUSABLE_INPUT,
    ),
    SilentChild(
        name='never-connects',
        game_command=(sys.executable, '-c', 'import time; time.sleep(60)'),
        connect_timeout_seconds=0.5,
        status=None,
    ),
)


@pytest.mark.parametrize('child', SILENT_CHILDREN, ids=[child.name for child in SILENT_CHILDREN])
def test_an_old_that_streams_nothing_is_labelled_and_nothing_is_drawn(
    color_game, mocker, caplog, child
):
    """A child that ends (or never connects) before streaming: the label says OLD did not replay."""
    mocker.patch.object(compare, 'CHILD_CONNECT_TIMEOUT_SECONDS', child.connect_timeout_seconds)
    onion_skin = OnionSkin(
        old_path=color_game.old,
        alpha_percent=DEFAULT_COMPARE_ALPHA_PERCENT,
        game_command=child.game_command,
        pause_at_frame=None,
    )
    surface = surface_of(color=NEW_RED)
    try:
        onion_skin.draw(surface=surface, frame_index=0)
        onion_skin.draw(surface=surface, frame_index=1)
    finally:
        onion_skin.stop()

    assert onion_skin.held_frame_index is None
    assert onion_skin.label == OLD_NOT_REPLAYED_LABEL
    assert rgb_at(surface=surface) == NEW_RED
    assert onion_skin.process is not None
    assert onion_skin.process.returncode is not None
    if child.status is not None:
        assert onion_skin.process.returncode == child.status
    assert 'OLD could not be replayed' in caplog.text


def test_an_old_that_diverges_ends_there_with_its_output_logged(color_game, caplog):
    """OLD replayed on this code stops at its first divergence: it ends there, and says why."""

    def move_the_backdrop(trace: dict[str, Any]) -> None:
        trace['frames'][2]['sprites'][0]['rect'][0] += 1

    rewrite_recording(recording_path=color_game.old, change=move_the_backdrop)
    onion_skin = OnionSkin(
        old_path=color_game.old,
        alpha_percent=DEFAULT_COMPARE_ALPHA_PERCENT,
        game_command=old_game_command(old_path=color_game.old),
        pause_at_frame=None,
    )
    surface = surface_of(color=NEW_RED)
    try:
        for frame_index in range(4):
            onion_skin.draw(surface=surface, frame_index=frame_index)
    finally:
        onion_skin.stop()
    onion_skin.stop()

    assert onion_skin.held_frame_index == 2
    assert onion_skin.label == OLD_ENDED_LABEL.format(frame_index=2)
    assert onion_skin.process is not None
    assert onion_skin.process.returncode == ExitCode.REPLAY_DIVERGED
    assert 'Replay diverged at frame 2' in caplog.text


def test_a_stream_cut_off_by_an_error_ends_old_there(color_game, mocker, caplog):
    """A read that fails part way through a frame (the connection reset) is OLD's end there.

    Its child, which nobody reads any more, stops itself promptly.
    """
    onion_skin = OnionSkin(
        old_path=color_game.old,
        alpha_percent=DEFAULT_COMPARE_ALPHA_PERCENT,
        game_command=old_game_command(old_path=color_game.old),
        pause_at_frame=None,
    )
    surface = surface_of(color=NEW_RED)
    onion_skin.draw(surface=surface, frame_index=0)
    # Frame 1's header arrives; its pixels do not
    mocker.patch.object(
        socket.socket,
        'recv',
        side_effect=[FRAME_HEADER.pack(1, *STAND_IN_SIZE), ConnectionResetError()],
    )
    try:
        onion_skin.draw(surface=surface, frame_index=1)
    finally:
        onion_skin.stop()

    assert onion_skin.held_frame_index == 0
    assert onion_skin.label == OLD_ENDED_LABEL.format(frame_index=0)
    assert onion_skin.process is not None
    # It stopped itself once nobody read (a quit: SUCCESS), not stopped by a signal
    assert onion_skin.process.returncode == ExitCode.SUCCESS
    assert 'its stream ended part way through a frame' in caplog.text


def test_old_is_replayed_by_its_own_game_else_by_this_one(color_game, tmp_path):
    """OLD's header names its game's console script; one that names none: this game again."""
    assert old_game_command(old_path=color_game.old)[:2] == [sys.executable, '-c']
    assert CONSOLE_SCRIPT in old_game_command(old_path=color_game.old)[2]
    assert old_game_command(old_path=tmp_path / 'missing.jsonl.gz') == running_game_command()


def test_a_frame_before_the_first_streamed_one_draws_nothing(color_game):
    """A restart that paused earlier than asked (a divergence on the way) shows NEW alone."""
    onion_skin = OnionSkin(
        old_path=color_game.old,
        alpha_percent=DEFAULT_COMPARE_ALPHA_PERCENT,
        game_command=old_game_command(old_path=color_game.old),
        pause_at_frame=4,
    )
    surface = surface_of(color=NEW_RED)
    try:
        onion_skin.draw(surface=surface, frame_index=1)
    finally:
        onion_skin.stop()

    assert onion_skin.held_frame_index == 3
    assert onion_skin.label is None
    assert rgb_at(surface=surface) == NEW_RED


def test_a_frame_stream_writes_nothing_before_its_first_frame():
    """Frames before the first are not sent; the others are, header then RGB rows; close once."""
    writing_end, reading_end = socket.socketpair()
    stream = FrameStream(connection=writing_end, first_frame=1)
    surface = pygame.Surface((2, 1))
    surface.fill(OLD_RED)
    try:
        assert stream.write_frame(frame_index=0, surface=surface)
        assert stream.write_frame(frame_index=1, surface=surface)
        stream.close()
        stream.close()
        received = receive_exactly(connection=reading_end, count=FRAME_HEADER.size + 2 * 3)
        assert received is not None
        assert receive_exactly(connection=reading_end, count=1) is None
    finally:
        reading_end.close()

    assert FRAME_HEADER.unpack(received[: FRAME_HEADER.size]) == (1, 2, 1)
    assert received[FRAME_HEADER.size :] == bytes(OLD_RED * 2)
    assert not stream.write_frame(frame_index=2, surface=surface)
