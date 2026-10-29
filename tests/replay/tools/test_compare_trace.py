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
import asyncio
import contextlib
import dataclasses
import importlib
import itertools
import logging
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any

import pygame
import pytest

from glitchygames.argument_types import percent_from_zero_to_one_hundred
from glitchygames.engine import GameEngine
from glitchygames.engine import game_engine as game_engine_module
from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, run_command
from glitchygames.replay import viewer as viewer_module
from glitchygames.replay.driver import ReplaySources
from glitchygames.replay.rebuild import ViewerState, restart_command
from glitchygames.replay.tools import compare
from glitchygames.replay.tools.children import running_game_command
from glitchygames.replay.tools.compare import (
    DEFAULT_COMPARE_ALPHA_PERCENT,
    FRAME_HEADER,
    FRAME_PIXEL_FORMAT,
    OLD_ENDED_LABEL,
    OLD_NOT_REPLAYED_LABEL,
    FrameStream,
    GhostCompositor,
    OnionSkin,
    decode_frame_pixels,
    first_streamed_frame,
    old_game_command,
    old_recording_refusal,
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
    copy_recording,
    record_stand_in_game,
    record_stand_in_game_once,
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
# Each frame's green is its own (frame k is FRAME_GREEN_STEP x (k + 1)): a frame's pixels sent
# under another frame's number show
FRAME_GREEN_STEP = 10
# Under PAUSING_SEED the color game pauses itself after its PAUSE_AFTER_FRAMES-th game frame,
# for PAUSE_FRAMES frames of the pause screen (D14)
PAUSING_SEED = 150
PAUSE_AFTER_FRAMES = 2
PAUSE_FRAMES = 3
# The game frame each frame of a pausing run shows (its logic's frames, the pause's left out):
# frames 0 and 1 are game frames 0 and 1, the pause screen's three show game frame 1 still
GAME_FRAME_OF_A_PAUSING_RUN = (0, 1, 1, 1, 1, 2, 3, 4, 5)
# The color game's floor, and its marker: a square drawn in the run's colors around the sample
# point (a few hundred pixels: never one of a frame's background colors, D16)
FLOOR_COLOR = (0, 0, 60)
MARKER_RECT = (0, 92, 16, 16)
# A pixel away from the status bar (bottom) and the OLD-ended label (top)
SAMPLE_POINT = (8, 100)
# The stand-in games' window size (tests/stand_in_games.py records at 320x240)
STAND_IN_SIZE = (320, 240)
# The frame stream token's length (compare.FRAME_STREAM_TOKEN_LENGTH), for parametrize ids
FRAME_STREAM_TOKEN_LENGTH_FOR_TESTS = 32
# How long the end-to-end children may run
CHILD_TIMEOUT_SECONDS = 120.0

COLOR_GAME_SOURCE = f'''\
"""A stand-in game: a plain floor with one marker on it, the seed's red and the frame's green."""

import pygame

from glitchygames.engine import GameEngine
from glitchygames.randomness import engine_random_seed
from glitchygames.scenes import Scene
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene

FRAMES_BEFORE_QUIT = {COLOR_GAME_FRAMES}
FRAME_GREEN_STEP = {FRAME_GREEN_STEP}
# The floor (most of the window: a background color of OLD's, D16) and the marker's square,
# small, around the tests' sample point
FLOOR_COLOR = {FLOOR_COLOR}
MARKER_RECT = {MARKER_RECT}
# Under this seed the game pauses itself once (the pause screen for PAUSE_FRAMES frames)
PAUSING_SEED = {PAUSING_SEED}
PAUSE_AFTER_FRAMES = {PAUSE_AFTER_FRAMES}
PAUSE_FRAMES = {PAUSE_FRAMES}


class AutoResumingPause(PauseScene):
    """The engine's pause screen, resuming by itself on its PAUSE_FRAMES-th frame."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pause_frames = 0

    def dt_tick(self, dt):
        super().dt_tick(dt)
        self.pause_frames += 1
        if self.pause_frames == PAUSE_FRAMES:
            self.resume()


class Backdrop(pygame.sprite.DirtySprite):
    """The whole window: a floor, and the marker's square, drawn on every frame."""

    def __init__(self, *, size):
        super().__init__()
        self.image = pygame.Surface(size)
        self.rect = self.image.get_rect()
        self.dirty = 2

    def update_nested_sprites(self):
        pass


class {SCENE_NAME}(Scene):
    """The one scene: the seed's red, and a green each frame of its own; it quits itself."""

    NAME = {SCENE_NAME!r}

    def __init__(self, options=None, groups=None):
        super().__init__(options=options, groups=groups)
        size = pygame.display.get_surface().get_size()
        self.red = engine_random_seed() % 256
        self.backdrop = Backdrop(size=size)
        self.all_sprites.add(self.backdrop)
        self.frames = 0

    def dt_tick(self, dt):
        self.frames += 1
        # Frame k (counted from 0) is painted with green FRAME_GREEN_STEP x (k + 1)
        self.backdrop.image.fill(FLOOR_COLOR)
        self.backdrop.image.fill(
            (self.red, FRAME_GREEN_STEP * self.frames % 256, 0), MARKER_RECT
        )
        if self.frames == FRAMES_BEFORE_QUIT:
            GameEngine.quit_game()
        elif engine_random_seed() == PAUSING_SEED and self.frames == PAUSE_AFTER_FRAMES:
            # As Scene.pause() does: the pause screen comes after this frame renders
            self.next_scene = AutoResumingPause(options=self.options)


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


def frame_color(*, seed: int, frame_index: int) -> tuple[int, int, int]:
    """Return the color game's picture on a frame: its seed's red, the frame's own green.

    Returns:
        The color.

    """
    return (seed % 256, FRAME_GREEN_STEP * (frame_index + 1) % 256, 0)


def recorded_frame_count(*, path: Path) -> int:
    """Return how many frames a recording holds.

    Returns:
        The count.

    """
    return len(read_trace_result(path=path).trace['frames'])


def install_color_game(*, install_directory: Path) -> StandInGame:
    """Install the color game (its package and its distribution's console script).

    Returns:
        The installed stand-in.

    """
    package_directory = install_directory / PACKAGE
    package_directory.mkdir(parents=True)
    (package_directory / '__init__.py').write_text(COLOR_GAME_SOURCE, encoding='utf-8')
    write_stand_in_distribution(
        directory=install_directory,
        distribution=CONSOLE_SCRIPT,
        console_scripts={CONSOLE_SCRIPT: f'{PACKAGE}:main'},
    )
    return StandInGame(
        package=PACKAGE,
        distribution=CONSOLE_SCRIPT,
        console_script=CONSOLE_SCRIPT,
        scene_name=SCENE_NAME,
        install_directory=install_directory,
        layer=None,
    )


@pytest.fixture(scope='module')
def recorded_old(tmp_path_factory) -> Path:
    """Record OLD once per module (and xdist worker), from a color game installed for it alone.

    Every test copies it (``color_game``): the color game is deterministic under its seed, so
    a test's own install would record the same frames.

    Returns:
        The recording.

    """
    root = tmp_path_factory.mktemp('recorded-old')
    # Paced: a watched replay presents OLD's frames by their recorded frame times (its viewer
    # runs as many recorded frames per 60 Hz tick as their times fill, up to 32), so an
    # uncapped OLD's frames would all go by in one tick
    return record_stand_in_game_once(
        game=install_color_game(install_directory=root / 'site-packages'),
        path=root / 'old.jsonl.gz',
        extra_arguments=('--random-seed', str(OLD_SEED)),
        paced=True,
    )


@pytest.fixture
def color_game(tmp_path, monkeypatch, mocker, recorded_old) -> ColorGame:
    """Install the color game for this test and its children, with its own copy of OLD.

    Returns:
        The color game.

    """
    game = install_color_game(install_directory=tmp_path / 'site-packages')
    use_stand_in_game(install_directory=game.install_directory, monkeypatch=monkeypatch)
    # Imported here for the watched replays; gone from sys.modules after the test
    mocker.patch.dict(sys.modules)
    module = importlib.import_module(PACKAGE)
    old = copy_recording(recording=recorded_old, path=tmp_path / 'old.jsonl.gz')
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
    expected_red = 150 if percent == DEFAULT_COMPARE_ALPHA_PERCENT else 125
    assert blended(new=NEW_RED, old=OLD_RED, percent=percent) == (expected_red, 0, 0)
    shown = [frame for frame in run.presented if frame.frame_index is not None]
    assert shown
    for frame in shown:
        assert frame.frame_index is not None
        # The same frame's green on both sides mixes to itself; another frame's would not
        assert frame.sample == (
            expected_red,
            *frame_color(seed=0, frame_index=frame.frame_index)[1:],
        )
        assert frame.sample == blended(
            new=frame_color(seed=NEW_SEED, frame_index=frame.frame_index),
            old=frame_color(seed=OLD_SEED, frame_index=frame.frame_index),
            percent=percent,
        ), frame
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
    shown = [frame for frame in run.presented if frame.frame_index is not None]
    assert shown
    for frame in shown:
        assert frame.frame_index is not None
        assert frame.sample == frame_color(seed=NEW_SEED, frame_index=frame.frame_index), frame


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
        address: Its ``PORT:TOKEN`` (``--replay-frame-stream``); a connection is read only
            after it sends the token.

    """

    def __init__(self, *, closes_at_once: bool = False) -> None:
        """Listen, and read on a thread from the first connection.

        Args:
            closes_at_once: Close the connection as soon as it is made, reading nothing.

        """
        self._listener = socket.create_server((compare.FRAME_STREAM_HOST, 0))
        self._token = 'a' * compare.FRAME_STREAM_TOKEN_LENGTH
        self.address = f'{self._listener.getsockname()[1]}:{self._token}'
        self._closes_at_once = closes_at_once
        self._frames: list[StreamedFrame] = []
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _read(self) -> None:
        connection, _ = self._listener.accept()
        with connection:
            if self._closes_at_once:
                return
            token = receive_exactly(connection=connection, count=len(self._token))
            assert token == self._token.encode('ascii')
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
        extra_arguments=('--replay-frame-stream', listener.address, *pause_arguments),
    )
    frames = listener.finish()

    assert replay.exit_status == ExitCode.SUCCESS
    assert [frame.frame_index for frame in frames] == list(
        range(first_frame, color_game.old_frame_count)
    )
    assert {frame.size for frame in frames} == {STAND_IN_SIZE}
    for frame in frames:
        # Each frame's own pixels under its own number
        assert frame.sample == frame_color(seed=OLD_SEED, frame_index=frame.frame_index), frame
    # The pause frame is the stream's to read: no warning that it is ignored
    assert 'is ignored with --headless' not in caplog.text


def test_a_stream_nobody_reads_any_more_ends_the_replay(color_game, mocker):
    """When the parent is gone, the child stops replaying instead of running on unseen."""
    listener = FrameStreamListener(closes_at_once=True)

    replay = replay_through_engine(
        mocker=mocker,
        scene_class=color_game.scene_class,
        path=color_game.old,
        extra_arguments=('--replay-frame-stream', listener.address),
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
    shown = [frame for frame in run.presented if frame.frame_index is not None]
    # The recorded game quits in its last frame, so the replay ends without presenting it
    assert {frame.frame_index for frame in shown} == set(range(1, color_game.old_frame_count - 1))
    for frame in shown:
        assert frame.frame_index is not None
        # OLD's last frame, its own green, stays over NEW's later ones
        assert frame.sample == blended(
            new=frame_color(seed=NEW_SEED, frame_index=frame.frame_index),
            old=frame_color(seed=OLD_SEED, frame_index=min(frame.frame_index, last_old_frame)),
            percent=DEFAULT_COMPARE_ALPHA_PERCENT,
        ), frame
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
        case='no-seed',
        exit_code=ExitCode.UNUSABLE_INPUT,
        message='not a readable recording (The recording header has no integer random_seed',
    ),
    Refusal(
        case='not-a-recording',
        exit_code=ExitCode.UNUSABLE_INPUT,
        message='not a readable recording',
    ),
)


def without_its_seed(*, old: Path, path: Path) -> Path:
    """Copy a recording to ``path`` without its header's ``random_seed``.

    Returns:
        The copy.

    """
    path.write_bytes(old.read_bytes())

    def drop_the_seed(trace: dict[str, Any]) -> None:
        del trace['random_seed']

    rewrite_recording(recording_path=path, change=drop_the_seed)
    return path


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
    elif case == 'no-seed':
        old = without_its_seed(old=color_game.old, path=tmp_path / 'no-seed.jsonl.gz')
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


def test_a_failing_stop_still_runs_the_rest_of_the_teardown(color_game, mocker, caplog):
    """The child is stopped, and the replay is still reported, though stopping it raised."""
    stop = OnionSkin.stop

    def stop_then_fail(onion_skin: OnionSkin) -> None:
        stop(onion_skin)
        message = 'the log file could not be removed'
        raise PermissionError(message)

    mocker.patch.object(OnionSkin, 'stop', stop_then_fail)
    report = mocker.spy(GoldenTraceEngine, '_report_replay_result')

    run = watched_replay(
        mocker=mocker,
        scene_class=color_game.scene_class,
        recording=color_game.old,
        arguments=('--random-seed', str(NEW_SEED), '--compare-trace', str(color_game.old)),
    )

    # A failed teardown is an internal error, after the rest of it ran
    assert run.exit_status == ExitCode.INTERNAL_ERROR
    assert report.call_count == 1
    assert 'The teardown failed' in caplog.text
    assert run.onion_skin.process is not None
    assert run.onion_skin.process.returncode is not None


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
    # Space runs it on to its end. OLD's child starts as the rebuild begins, so the two rebuild
    # at once
    started_while_rebuilding: list[bool] = []
    start = OnionSkin._start

    def start_noting_the_rebuild(onion_skin: OnionSkin) -> None:
        sources = active_sources()
        assert isinstance(sources, ReplaySources)
        started_while_rebuilding.append(sources.controls.rebuild_target_frame is not None)
        start(onion_skin)

    mocker.patch.object(OnionSkin, '_start', start_noting_the_rebuild)
    # The restart names the game frame it shows paused (frame 3: this game never pauses, so
    # its frames and game frames are one), as _restart_replay does
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
            '--replay-viewer-state',
            ViewerState(compare_first_game_frame=3).model_dump_json(),
        ),
    )

    assert run.exit_status == ExitCode.SUCCESS
    assert started_while_rebuilding == [True]
    command = run.onion_skin.command
    assert command[command.index('--replay-pause-at-frame') + 1] == '4'
    shown = [frame for frame in run.presented if frame.frame_index is not None]
    assert shown[0].frame_index == 3
    for frame in shown:
        assert frame.frame_index is not None
        assert frame.old_frame_index == frame.frame_index, frame
        assert frame.sample == blended(
            new=frame_color(seed=NEW_SEED, frame_index=frame.frame_index),
            old=frame_color(seed=OLD_SEED, frame_index=frame.frame_index),
            percent=DEFAULT_COMPARE_ALPHA_PERCENT,
        ), frame
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

    address = f'5:{"a" * compare.FRAME_STREAM_TOKEN_LENGTH}'
    assert game.parse_args(['--replay-frame-stream', address]).replay_frame_stream == address
    assert (
        command.parse_args([
            'replay-trace',
            'new',
            '--replay-frame-stream',
            address,
        ]).replay_frame_stream
        == address
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
        arguments=(
            '--replay-trace',
            str(color_game.old),
            '--replay-frame-stream',
            f'1:{"a" * compare.FRAME_STREAM_TOKEN_LENGTH}',
        ),
    )

    assert status == ExitCode.OPTIONS_REFUSED
    assert '--replay-frame-stream needs --headless' in caplog.text


@pytest.mark.parametrize(
    'address', ['5', 'port:' + 'a' * 32, '5:short', '5:' + 'g' * 32, '70000:' + 'a' * 32]
)
def test_a_frame_stream_address_that_is_not_port_and_token_is_refused(
    color_game, mocker, caplog, address
):
    """``--replay-frame-stream`` takes ``PORT:TOKEN`` (the token: the parent's, hex)."""
    status = constructed_exit_status(
        mocker=mocker,
        scene_class=color_game.scene_class,
        arguments=(
            '--replay-trace',
            str(color_game.old),
            '--headless',
            '--replay-frame-stream',
            address,
        ),
    )

    assert status == ExitCode.OPTIONS_REFUSED
    assert '--replay-frame-stream takes PORT:TOKEN' in caplog.text


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
            f'{port}:{"a" * compare.FRAME_STREAM_TOKEN_LENGTH}',
        ),
    )

    assert status == ExitCode.SERVICE_UNAVAILABLE
    assert f'Cannot stream frames to port {port}' in caplog.text


@pytest.mark.parametrize(
    ('arguments', 'message'),
    [
        (('--compare-alpha', '25'), '--compare-alpha is ignored without --compare-trace'),
        (('--replay-frame-stream', '5'), '--replay-frame-stream is ignored without --replay-trace'),
    ],
    ids=['compare-alpha', 'replay-frame-stream'],
)
def test_without_a_replay_or_old_the_compare_options_are_ignored_with_a_warning(
    color_game, mocker, caplog, arguments, message
):
    """A live run given them alone warns that they do nothing (as --replay-fps does).

    (``--compare-trace OLD`` itself plays live against OLD: the live-play tests below.)
    """
    with engine_environment(mocker):
        GoldenTraceSceneManager.install()
        try:
            with command_line(['--log-level', 'warning', '--headless', *arguments]):
                engine = GoldenTraceEngine(game=color_game.scene_class)
        finally:
            GoldenTraceSceneManager.uninstall()

    assert engine.onion_skin is None
    assert message in caplog.text
    assert '--compare-trace is ignored' not in caplog.text


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
    # INFO records: the level is the run's (--log-cli-level, WARNING in CI), never a module's
    # (BUGS.md #236; this passed in CI only while a script imported at collection set game to INFO)
    caplog.set_level(logging.INFO)
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


def test_frames_that_will_be_dropped_are_not_decoded(color_game, mocker):
    """Read past without building a picture; only a frame drawn is decoded (OLD's last too)."""
    decode = mocker.spy(compare, 'decode_frame_pixels')
    onion_skin = OnionSkin(
        old_path=color_game.old,
        alpha_percent=DEFAULT_COMPARE_ALPHA_PERCENT,
        game_command=old_game_command(old_path=color_game.old),
        pause_at_frame=None,
    )
    last_frame = color_game.old_frame_count - 1
    try:
        onion_skin.draw(surface=surface_of(color=NEW_RED), frame_index=0)
        onion_skin.draw(surface=surface_of(color=NEW_RED), frame_index=4)
        assert decode.call_count == 2
        onion_skin.draw(surface=surface_of(color=NEW_RED), frame_index=4)
        assert decode.call_count == 2
        # Past OLD's end: its last frame, read past while looking for the next, is decoded
        late = surface_of(color=NEW_RED)
        onion_skin.draw(surface=late, frame_index=last_frame + 3)
    finally:
        onion_skin.stop()

    assert decode.call_count == 3
    assert onion_skin.frames_received == color_game.old_frame_count
    assert onion_skin.held_frame_index == last_frame
    assert rgb_at(surface=late) == blended(
        new=NEW_RED,
        old=frame_color(seed=OLD_SEED, frame_index=last_frame),
        percent=DEFAULT_COMPARE_ALPHA_PERCENT,
    )


STALLING_CHILD = """\
import socket, sys, time
port, token = sys.argv[sys.argv.index('--replay-frame-stream') + 1].split(':')
connection = socket.create_connection(('127.0.0.1', int(port)))
connection.sendall(token.encode('ascii'))
# One frame (frame 0) at NEW's size, then nothing more, never closing
connection.sendall(b''.join(number.to_bytes(4, 'little') for number in (0, 320, 240)))
connection.sendall(bytes(320 * 240 * 3))
time.sleep(60)
"""

OVERSIZED_CHILD = """\
import socket, sys, time
port, token = sys.argv[sys.argv.index('--replay-frame-stream') + 1].split(':')
connection = socket.create_connection(('127.0.0.1', int(port)))
connection.sendall(token.encode('ascii'))
# A header claiming a 1000x1000 frame (not NEW's 320x240), and no pixels
connection.sendall(b''.join(number.to_bytes(4, 'little') for number in (0, 1000, 1000)))
time.sleep(60)
"""


def test_a_frame_of_another_size_than_new_ends_old_before_anything_is_read(
    color_game, mocker, caplog
):
    """A header whose size is not NEW's ends OLD at once: no pixels are awaited or allocated."""
    mocker.patch.object(compare, 'CHILD_READ_TIMEOUT_SECONDS', 0.5)
    receive = mocker.spy(compare, 'receive_exactly')
    onion_skin = OnionSkin(
        old_path=color_game.old,
        alpha_percent=DEFAULT_COMPARE_ALPHA_PERCENT,
        game_command=[sys.executable, '-c', OVERSIZED_CHILD],
        pause_at_frame=None,
    )
    surface = surface_of(color=NEW_RED)
    try:
        onion_skin.draw(surface=surface, frame_index=0)
    finally:
        onion_skin.stop()

    assert onion_skin.held_frame_index is None
    assert onion_skin.label == OLD_NOT_REPLAYED_LABEL
    assert "it sent a 1000x1000 frame, not NEW's 320x240" in caplog.text
    # The token, then the header: the pixels were never asked for
    assert [call.kwargs['count'] for call in receive.call_args_list] == [
        compare.FRAME_STREAM_TOKEN_LENGTH,
        FRAME_HEADER.size,
    ]
    assert rgb_at(surface=surface) == NEW_RED
    assert onion_skin.process is not None
    assert onion_skin.process.returncode not in {None, ExitCode.SUCCESS}


def test_an_old_that_stops_streaming_ends_there_and_the_replay_goes_on(color_game, mocker, caplog):
    """A child that stalls (alive, sending nothing) ends OLD there: stopped, not waited for."""
    mocker.patch.object(compare, 'CHILD_READ_TIMEOUT_SECONDS', 0.5)
    onion_skin = OnionSkin(
        old_path=color_game.old,
        alpha_percent=DEFAULT_COMPARE_ALPHA_PERCENT,
        game_command=[sys.executable, '-c', STALLING_CHILD],
        pause_at_frame=None,
    )
    try:
        onion_skin.draw(surface=surface_of(color=NEW_RED), frame_index=0)
        started = time.monotonic()
        onion_skin.draw(surface=surface_of(color=NEW_RED), frame_index=1)
        stalled_for = time.monotonic() - started
    finally:
        onion_skin.stop()

    assert onion_skin.held_frame_index == 0
    assert onion_skin.label == OLD_ENDED_LABEL.format(frame_index=0)
    assert 'it stopped streaming' in caplog.text
    # Stopped at once (a signal), not given STOP_GRACE_SECONDS to end on its own
    assert stalled_for < compare.STOP_GRACE_SECONDS / 2
    assert onion_skin.process is not None
    assert onion_skin.process.returncode not in {None, ExitCode.SUCCESS}


@pytest.mark.parametrize(
    'stranger_sends', [b'0' * FRAME_STREAM_TOKEN_LENGTH_FOR_TESTS, b''], ids=['wrong', 'nothing']
)
def test_a_connection_without_the_token_is_refused(color_game, caplog, stranger_sends):
    """Only OLD's own child is read: another local connection, without the token, is closed."""
    onion_skin = OnionSkin(
        old_path=color_game.old,
        alpha_percent=DEFAULT_COMPARE_ALPHA_PERCENT,
        game_command=old_game_command(old_path=color_game.old),
        pause_at_frame=None,
    )
    try:
        onion_skin.begin()
        address = onion_skin.command[onion_skin.command.index('--replay-frame-stream') + 1]
        port, token = address.split(':')
        assert len(token) == compare.FRAME_STREAM_TOKEN_LENGTH
        # Connects before the child (which is still importing the game)
        with socket.create_connection((compare.FRAME_STREAM_HOST, int(port))) as stranger:
            if stranger_sends:
                stranger.sendall(stranger_sends)
            else:
                # Gone before sending anything
                stranger.shutdown(socket.SHUT_WR)
            onion_skin.draw(surface=surface_of(color=NEW_RED), frame_index=0)
    finally:
        onion_skin.stop()

    assert onion_skin.held_frame_index == 0
    assert 'refused a frame stream connection without the token' in caplog.text
    assert compare.FRAME_STREAM_TOKEN_LENGTH == FRAME_STREAM_TOKEN_LENGTH_FOR_TESTS


def test_stopping_a_running_child_removes_no_file_by_name(color_game, mocker):
    """The child's output is never unlinked by name, which Windows refuses while it is held.

    On Windows CI the named output file could not be removed after the child was stopped
    (WinError 32: another process still held it). Here every removal by name fails the same
    way once the child has started, and ``stop`` still stops it: the output is a TemporaryFile,
    which the system removes when its last handle closes.
    """
    onion_skin = OnionSkin(
        old_path=color_game.old,
        alpha_percent=DEFAULT_COMPARE_ALPHA_PERCENT,
        game_command=old_game_command(old_path=color_game.old),
        pause_at_frame=None,
    )
    try:
        onion_skin.begin()
        # One frame read: the child is still streaming the rest when it is stopped
        onion_skin.draw(surface=surface_of(color=NEW_RED), frame_index=0)
        held_open = PermissionError(
            32, 'The process cannot access the file because it is being used by another process'
        )
        mocker.patch.object(os, 'unlink', side_effect=held_open)
        mocker.patch.object(os, 'remove', side_effect=held_open)
    finally:
        onion_skin.stop()

    assert onion_skin.is_stopped
    assert onion_skin.process is not None
    assert onion_skin.process.returncode is not None


def test_each_onion_skin_has_its_own_token(color_game):
    """Two runs never share a token."""
    tokens = []
    for _ in range(2):
        onion_skin = OnionSkin(
            old_path=color_game.old,
            alpha_percent=DEFAULT_COMPARE_ALPHA_PERCENT,
            game_command=[sys.executable, '-c', 'pass'],
            pause_at_frame=None,
        )
        try:
            onion_skin.begin()
        finally:
            onion_skin.stop()
        tokens.append(onion_skin.command[onion_skin.command.index('--replay-frame-stream') + 1])
    assert tokens[0].split(':')[1] != tokens[1].split(':')[1]


def test_sizes_that_cannot_be_compared_are_warned_about(color_game, tmp_path, caplog):
    """A header without a screen size (not the engine's recorder's) is let through, with a word."""
    unsized = tmp_path / 'unsized.jsonl.gz'
    unsized.write_bytes(color_game.old.read_bytes())

    def drop_the_screen_size(trace: dict[str, Any]) -> None:
        del trace['screen_size']

    rewrite_recording(recording_path=unsized, change=drop_the_screen_size)
    new_header = read_trace_result(path=color_game.old).trace

    assert old_recording_refusal(old_path=unsized, new_header=new_header) is None
    assert 'could not compare the screen sizes' in caplog.text


# A child that connects late (after the test's stranger), streams one frame at NEW's size and
# ends at once: it has ended before the stranger's token wait does
QUICK_CHILD = """\
import socket, sys, time
time.sleep(0.3)
port, token = sys.argv[sys.argv.index('--replay-frame-stream') + 1].split(':')
connection = socket.create_connection(('127.0.0.1', int(port)))
connection.sendall(token.encode('ascii'))
connection.sendall(b''.join(number.to_bytes(4, 'little') for number in (0, 320, 240)))
connection.sendall(bytes(320 * 240 * 3))
connection.close()
"""


def test_a_silent_connection_that_stays_open_is_refused_after_the_token_wait(
    color_game, mocker, caplog
):
    """A connection sending nothing, never closing, is refused once its wait ends; then the child.

    The child connected and ended during that wait: its connection, still waiting to be
    accepted, is read all the same (an ended child is not one that never connected).
    """
    mocker.patch.object(compare, 'TOKEN_TIMEOUT_SECONDS', 2.0)
    onion_skin = OnionSkin(
        old_path=color_game.old,
        alpha_percent=DEFAULT_COMPARE_ALPHA_PERCENT,
        game_command=[sys.executable, '-c', QUICK_CHILD],
        pause_at_frame=None,
    )
    try:
        onion_skin.begin()
        address = onion_skin.command[onion_skin.command.index('--replay-frame-stream') + 1]
        port, _ = address.split(':')
        # Connects before the child (which waits first), and stays open, silent
        with socket.create_connection((compare.FRAME_STREAM_HOST, int(port))):
            onion_skin.draw(surface=surface_of(color=NEW_RED), frame_index=0)
    finally:
        onion_skin.stop()

    assert 'refused a frame stream connection without the token' in caplog.text
    assert onion_skin.held_frame_index == 0
    assert onion_skin.process is not None
    assert onion_skin.process.returncode == ExitCode.SUCCESS


def test_a_silent_stranger_does_not_stretch_the_wait_for_the_child(color_game, mocker, caplog):
    """The connect deadline holds through a stranger's token wait: it never adds to the wait."""
    mocker.patch.object(compare, 'CHILD_CONNECT_TIMEOUT_SECONDS', 0.5)
    onion_skin = OnionSkin(
        old_path=color_game.old,
        alpha_percent=DEFAULT_COMPARE_ALPHA_PERCENT,
        # A child that never connects
        game_command=[sys.executable, '-c', 'import time; time.sleep(60)'],
        pause_at_frame=None,
    )
    try:
        onion_skin.begin()
        address = onion_skin.command[onion_skin.command.index('--replay-frame-stream') + 1]
        port, _ = address.split(':')
        with socket.create_connection((compare.FRAME_STREAM_HOST, int(port))):
            started = time.monotonic()
            onion_skin.draw(surface=surface_of(color=NEW_RED), frame_index=0)
            waited = time.monotonic() - started
    finally:
        onion_skin.stop()

    assert onion_skin.label == OLD_NOT_REPLAYED_LABEL
    assert 'refused a frame stream connection without the token' in caplog.text
    # The deadline (0.5 s), not the stranger's whole token wait (TOKEN_TIMEOUT_SECONDS)
    assert waited < compare.TOKEN_TIMEOUT_SECONDS / 2


def test_a_stranger_refused_past_the_deadline_ends_the_wait_for_the_child(
    color_game, mocker, caplog
):
    """A stranger refused once the connect deadline has passed ends the wait there.

    The clock is a stand-in: before the stranger's token wait it reads 0, after it the deadline
    has passed. The real-time test above can end the other way on Windows, whose socket
    timeouts may wake a little early on a coarse clock, so the loop sees time left, accepts
    again, times out and ends there instead; this one pins the refusal's own ending.
    """
    readings = itertools.chain([0.0, 0.0], itertools.repeat(compare.CHILD_CONNECT_TIMEOUT_SECONDS))
    mocker.patch.object(compare, 'measured_seconds', side_effect=lambda: next(readings))
    mocker.patch.object(compare, 'TOKEN_TIMEOUT_SECONDS', 0.2)
    onion_skin = OnionSkin(
        old_path=color_game.old,
        alpha_percent=DEFAULT_COMPARE_ALPHA_PERCENT,
        # A child that never connects
        game_command=[sys.executable, '-c', 'import time; time.sleep(60)'],
        pause_at_frame=None,
    )
    never_connected = mocker.spy(onion_skin, '_never_connected')
    try:
        onion_skin.begin()
        address = onion_skin.command[onion_skin.command.index('--replay-frame-stream') + 1]
        port, _ = address.split(':')
        with socket.create_connection((compare.FRAME_STREAM_HOST, int(port))):
            onion_skin.draw(surface=surface_of(color=NEW_RED), frame_index=0)
    finally:
        onion_skin.stop()

    assert onion_skin.label == OLD_NOT_REPLAYED_LABEL
    assert 'refused a frame stream connection without the token' in caplog.text
    never_connected.assert_called_once_with()


def test_a_frame_stream_whose_token_cannot_be_sent_closes_its_socket(mocker):
    """A failure sending the token leaves no socket open: it is closed, and the failure raised."""
    created: list[socket.socket] = []
    create_connection = socket.create_connection

    def noting_the_connection(*arguments: Any, **settings: Any) -> socket.socket:
        connection = create_connection(*arguments, **settings)
        created.append(connection)
        return connection

    with socket.create_server((compare.FRAME_STREAM_HOST, 0)) as listener:
        address = compare.FrameStreamAddress(
            port=listener.getsockname()[1], token='a' * compare.FRAME_STREAM_TOKEN_LENGTH
        )
        mocker.patch.object(compare.socket, 'create_connection', side_effect=noting_the_connection)
        mocker.patch.object(socket.socket, 'sendall', side_effect=ConnectionResetError)
        with pytest.raises(ConnectionResetError):
            FrameStream.connect(address=address, first_frame=0)

    assert len(created) == 1
    assert created[0].fileno() == -1


def test_an_onion_skin_that_fails_to_start_its_child_closes_its_listener(color_game, mocker):
    """A child that cannot start leaves no listener or output file open; begin() may retry.

    The output is a TemporaryFile, removed by the system once closed (never unlinked by name).
    """
    created: list[socket.socket] = []
    create_server = socket.create_server
    outputs: list[IO[str]] = []
    make_temporary_file = compare.tempfile.TemporaryFile
    start_command = compare.start_command

    def noting_the_listener(*arguments: Any, **settings: Any) -> socket.socket:
        listener = create_server(*arguments, **settings)
        created.append(listener)
        return listener

    def noting_the_output(*arguments: Any, **settings: Any) -> IO[str]:
        output = make_temporary_file(*arguments, **settings)
        outputs.append(output)
        return output

    mocker.patch.object(compare.socket, 'create_server', side_effect=noting_the_listener)
    mocker.patch.object(compare.tempfile, 'TemporaryFile', side_effect=noting_the_output)
    starting = mocker.patch.object(compare, 'start_command', side_effect=FileNotFoundError)
    onion_skin = OnionSkin(
        old_path=color_game.old,
        alpha_percent=DEFAULT_COMPARE_ALPHA_PERCENT,
        game_command=[sys.executable, '-c', 'pass'],
        pause_at_frame=None,
    )
    try:
        with pytest.raises(FileNotFoundError):
            onion_skin.begin()
        assert created[0].fileno() == -1
        assert outputs[0].closed
        assert onion_skin.process is None
        # A retry starts afresh, with a listener of its own
        starting.side_effect = start_command
        onion_skin.begin()
        assert created[1].fileno() != -1
        assert onion_skin.process is not None
    finally:
        onion_skin.stop()


# Live play against OLD (decision 19; Task D12): --compare-trace OLD without --replay-trace


@dataclasses.dataclass(frozen=True)
class LivePresented:
    """One presented frame of live play against OLD.

    Attributes:
        frame_index: The live frame shown: the one a recording of the run counts it as (the
            host's frames ended before it).
        sample: The pixel at ``SAMPLE_POINT``, as presented.
        old_frame_index: The OLD frame the onion skin held then (None: none yet).
        label: The onion skin's label then (None: none).

    """

    frame_index: int
    sample: tuple[int, int, int]
    old_frame_index: int | None
    label: str | None


@dataclasses.dataclass(frozen=True)
class LiveRun:
    """How live play in this process went.

    Attributes:
        exit_status: Its exit status (None: it ended without a SystemExit).
        engine: Its engine.
        presented: Every frame it presented, in order.

    """

    exit_status: object
    engine: GameEngine
    presented: list[LivePresented]

    @property
    def onion_skin(self) -> OnionSkin:
        """The run's onion skin (it must have one)."""
        onion_skin = self.engine.onion_skin
        assert onion_skin is not None
        return onion_skin


def live_play(
    *, mocker: MockerFixture, scene_class: type[Scene], arguments: tuple[str, ...]
) -> LiveRun:
    """Play the color game live, in this process, on SDL's dummy driver (it quits itself).

    Each presented frame's ``SAMPLE_POINT`` is kept (``pygame.display.flip`` is replaced:
    nothing is shown).

    Args:
        mocker: pytest-mock's fixture.
        scene_class: The game's scene class.
        arguments: More arguments for the game.

    Returns:
        How it went.

    """
    presented: list[LivePresented] = []
    engines: list[GameEngine] = []

    def flip() -> None:
        surface = pygame.display.get_surface()
        assert surface is not None
        engine = engines[0]
        assert engine.host is not None
        onion_skin = engine.onion_skin
        presented.append(
            LivePresented(
                frame_index=engine.host.sources.frames_ended,
                sample=rgb_at(surface=surface),
                old_frame_index=None if onion_skin is None else onion_skin.held_frame_index,
                label=None if onion_skin is None else onion_skin.label,
            )
        )

    mocker.patch.object(pygame.display, 'flip', side_effect=flip)
    exit_status: object = None
    with engine_environment(mocker):
        GoldenTraceSceneManager.install()
        try:
            with command_line([
                '--log-level',
                'info',
                '--resolution',
                f'{STAND_IN_SIZE[0]}x{STAND_IN_SIZE[1]}',
                *arguments,
            ]):
                engine = GoldenTraceEngine(game=scene_class)
            engines.append(engine)
            try:
                engine.start()
            except SystemExit as exit_request:
                exit_status = exit_request.code
        finally:
            GoldenTraceSceneManager.uninstall()
    return LiveRun(exit_status=exit_status, engine=engine, presented=presented)


def live_run_succeeded(*, run: LiveRun) -> bool:
    """Tell whether live play ended normally (no exit status, or SUCCESS).

    Returns:
        True when it did.

    """
    return run.exit_status in {None, ExitCode.SUCCESS}


@pytest.mark.parametrize(
    ('alpha_arguments', 'percent'),
    [((), DEFAULT_COMPARE_ALPHA_PERCENT), (('--compare-alpha', '25'), 25.0)],
    ids=['default-50', 'alpha-25'],
)
def test_live_play_blends_old_over_the_live_frame(color_game, mocker, alpha_arguments, percent):
    """Each live presented frame N is the live picture with OLD's frame N over it at the alpha."""
    run = live_play(
        mocker=mocker,
        scene_class=color_game.scene_class,
        arguments=(
            '--random-seed',
            str(NEW_SEED),
            '--compare-trace',
            str(color_game.old),
            *alpha_arguments,
        ),
    )

    assert live_run_succeeded(run=run), run.exit_status
    expected_red = 150 if percent == DEFAULT_COMPARE_ALPHA_PERCENT else 125
    assert run.presented
    for frame in run.presented:
        assert frame.sample == (
            expected_red,
            *frame_color(seed=0, frame_index=frame.frame_index)[1:],
        ), frame
        assert frame.sample == blended(
            new=frame_color(seed=NEW_SEED, frame_index=frame.frame_index),
            old=frame_color(seed=OLD_SEED, frame_index=frame.frame_index),
            percent=percent,
        ), frame
        assert frame.old_frame_index == frame.frame_index, frame
        assert frame.label is None
    assert [frame.frame_index for frame in run.presented] == list(range(len(run.presented)))


@dataclasses.dataclass(frozen=True)
class LiveSeedCase:
    """A live run's seed arguments, the seed it plays under, and what its log says.

    Attributes:
        case: The test id.
        seed_arguments: ``--random-seed N``, or nothing.
        live_seed: The seed live play runs under.
        logged: The seed's log line.

    """

    case: str
    seed_arguments: tuple[str, ...]
    live_seed: int
    logged: str


LIVE_SEED_CASES = (
    LiveSeedCase(
        case='olds-seed',
        seed_arguments=(),
        live_seed=OLD_SEED,
        logged=f"Random seed {OLD_SEED} (OLD's, from --compare-trace",
    ),
    LiveSeedCase(
        case='given-seed',
        seed_arguments=('--random-seed', str(NEW_SEED)),
        live_seed=NEW_SEED,
        logged=f'Random seed {NEW_SEED} (given; OLD was recorded under {OLD_SEED})',
    ),
)


@pytest.mark.parametrize('seed_case', LIVE_SEED_CASES, ids=[case.case for case in LIVE_SEED_CASES])
def test_live_play_uses_olds_seed_unless_one_is_given(
    color_game, mocker, caplog, tmp_path, seed_case
):
    """Live play starts in OLD's world (its recorded seed), unless --random-seed N is given.

    A recording of it holds the seed played.
    """
    # INFO records: the level is the run's (--log-cli-level, WARNING in CI), never a module's
    # (BUGS.md #236; this passed in CI only while a script imported at collection set game to INFO)
    caplog.set_level(logging.INFO)
    new = tmp_path / 'new.jsonl.gz'
    run = live_play(
        mocker=mocker,
        scene_class=color_game.scene_class,
        arguments=(
            *seed_case.seed_arguments,
            '--record-trace',
            str(new),
            '--compare-trace',
            str(color_game.old),
        ),
    )

    assert live_run_succeeded(run=run), run.exit_status
    assert run.engine.random_seed == seed_case.live_seed
    assert read_trace_result(path=new).trace['random_seed'] == seed_case.live_seed
    assert seed_case.logged in caplog.text
    assert run.presented
    for frame in run.presented:
        assert frame.sample == blended(
            new=frame_color(seed=seed_case.live_seed, frame_index=frame.frame_index),
            old=frame_color(seed=OLD_SEED, frame_index=frame.frame_index),
            percent=DEFAULT_COMPARE_ALPHA_PERCENT,
        ), frame


def test_live_play_frame_numbers_match_a_recording_of_the_same_run(color_game, mocker, tmp_path):
    """Recorded live against OLD, then replayed against OLD: each frame is paired with the same OLD.

    The live frame number is the one the recording counts, so the pairing a replay of the
    recording shows is the pairing live play showed.
    """
    new = tmp_path / 'new.jsonl.gz'
    live = live_play(
        mocker=mocker,
        scene_class=color_game.scene_class,
        arguments=(
            '--random-seed',
            str(NEW_SEED),
            '--record-trace',
            str(new),
            '--compare-trace',
            str(color_game.old),
        ),
    )
    assert live_run_succeeded(run=live), live.exit_status
    assert recorded_frame_count(path=new) == live.engine.host.sources.frames_ended

    replayed = watched_replay(
        mocker=mocker,
        scene_class=color_game.scene_class,
        recording=new,
        arguments=('--compare-trace', str(color_game.old)),
    )
    assert replayed.exit_status == ExitCode.SUCCESS

    live_pairs = {
        frame.frame_index: (frame.old_frame_index, frame.sample) for frame in live.presented
    }
    replayed_pairs = {
        frame.frame_index: (frame.old_frame_index, frame.sample)
        for frame in replayed.presented
        if frame.frame_index is not None
    }
    assert replayed_pairs
    # Every frame the replay shows was shown live, with the same OLD frame and the same picture
    for frame_index, pair in replayed_pairs.items():
        assert live_pairs[frame_index] == pair, frame_index
        assert pair[0] == frame_index


def test_live_play_holds_olds_last_frame_with_the_label(color_game, mocker, tmp_path):
    """OLD shorter than the play: its last frame stays, labelled, and play goes on."""
    short_old = tmp_path / 'short-old.jsonl.gz'
    short_old.write_bytes(color_game.old.read_bytes())
    last_old_frame = 2

    def keep_three_frames(trace: dict[str, Any]) -> None:
        trace['frames'] = trace['frames'][: last_old_frame + 1]

    rewrite_recording(recording_path=short_old, change=keep_three_frames)

    run = live_play(
        mocker=mocker,
        scene_class=color_game.scene_class,
        arguments=('--random-seed', str(NEW_SEED), '--compare-trace', str(short_old)),
    )

    assert live_run_succeeded(run=run), run.exit_status
    assert max(frame.frame_index for frame in run.presented) > last_old_frame
    for frame in run.presented:
        assert frame.sample == blended(
            new=frame_color(seed=NEW_SEED, frame_index=frame.frame_index),
            old=frame_color(seed=OLD_SEED, frame_index=min(frame.frame_index, last_old_frame)),
            percent=DEFAULT_COMPARE_ALPHA_PERCENT,
        ), frame
        if frame.frame_index <= last_old_frame:
            assert frame.old_frame_index == frame.frame_index, frame
            assert frame.label is None, frame
        else:
            assert frame.old_frame_index == last_old_frame, frame
            assert frame.label == OLD_ENDED_LABEL.format(frame_index=last_old_frame), frame


LIVE_REFUSALS = (
    Refusal(
        case='headless', exit_code=ExitCode.OPTIONS_REFUSED, message='an onion skin is watched'
    ),
    Refusal(
        case='different-size',
        exit_code=ExitCode.UNUSABLE_INPUT,
        message='OLD was recorded on a 160x120 display',
    ),
    Refusal(case='missing', exit_code=ExitCode.MISSING_INPUT, message='no such recording'),
    Refusal(
        case='no-seed',
        exit_code=ExitCode.UNUSABLE_INPUT,
        message='not a readable recording (The recording header has no integer random_seed',
    ),
    Refusal(
        case='not-a-recording',
        exit_code=ExitCode.UNUSABLE_INPUT,
        message='not a readable recording',
    ),
    Refusal(
        case='a-directory',
        exit_code=ExitCode.UNUSABLE_INPUT,
        message='not a readable recording',
    ),
)


@pytest.mark.parametrize('refusal', LIVE_REFUSALS, ids=[refusal.case for refusal in LIVE_REFUSALS])
def test_live_play_refusals(color_game, mocker, tmp_path, caplog, refusal):
    """Each is refused before anything runs: no child, nothing recorded."""
    case = refusal.case
    old = color_game.old
    extra: tuple[str, ...] = ()
    if case == 'headless':
        extra = ('--headless',)
    elif case == 'different-size':
        old = record_stand_in_game(
            game=color_game.game,
            path=tmp_path / 'small.jsonl.gz',
            extra_arguments=('--resolution', '160x120'),
        )
    elif case == 'missing':
        old = tmp_path / 'missing.jsonl.gz'
    elif case == 'no-seed':
        old = without_its_seed(old=color_game.old, path=tmp_path / 'no-seed.jsonl.gz')
    elif case == 'a-directory':
        # Unreadable as a file at all (an OSError, not a malformed recording)
        old = tmp_path / 'a-directory.jsonl.gz'
        old.mkdir()
    else:
        old = tmp_path / 'not-a-recording.jsonl.gz'
        old.write_text('not a recording\n', encoding='utf-8')
    new = tmp_path / 'new.jsonl.gz'
    start_command = mocker.spy(compare, 'start_command')

    status = constructed_exit_status(
        mocker=mocker,
        scene_class=color_game.scene_class,
        arguments=(
            '--resolution',
            f'{STAND_IN_SIZE[0]}x{STAND_IN_SIZE[1]}',
            '--record-trace',
            str(new),
            '--compare-trace',
            str(old),
            *extra,
        ),
    )

    assert status == refusal.exit_code
    assert f'Cannot play live against {old}: {refusal.message}' in caplog.text
    start_command.assert_not_called()
    assert not new.exists()


@pytest.mark.parametrize(
    ('ending', 'exit_code'),
    [('quits', None), ('fails', ExitCode.INTERNAL_ERROR), ('interrupted', ExitCode.INTERRUPTED)],
)
def test_live_play_reaps_the_child_on_quit_and_on_failure(color_game, mocker, ending, exit_code):
    """However live play ends, OLD's child has ended and been waited for."""
    if ending != 'quits':
        mocker.patch.object(
            color_game.scene_class,
            'dt_tick',
            raising_on_tick(
                scene_class=color_game.scene_class,
                tick_number=3,
                error=RuntimeError('the game failed') if ending == 'fails' else KeyboardInterrupt(),
            ),
        )

    run = live_play(
        mocker=mocker,
        scene_class=color_game.scene_class,
        arguments=('--compare-trace', str(color_game.old)),
    )

    if exit_code is None:
        assert live_run_succeeded(run=run), run.exit_status
    else:
        assert run.exit_status == exit_code
    onion_skin = run.onion_skin
    assert onion_skin.process is not None
    assert onion_skin.process.returncode is not None
    assert onion_skin.is_stopped


@pytest.mark.parametrize('run_kind', ['live', 'watched-replay'])
def test_compare_trace_is_refused_in_a_browser(color_game, mocker, caplog, run_kind):
    """start_async (a browser page) cannot start OLD's child: refused before anything starts."""
    start_command = mocker.spy(compare, 'start_command')
    replay_arguments = (
        ('--replay-trace', str(color_game.old), '--random-seed', str(NEW_SEED))
        if run_kind == 'watched-replay'
        else ()
    )

    async def wait_for_tick() -> float:
        await asyncio.sleep(0)
        message = 'no tick may be waited for: the run is refused before it starts'
        raise AssertionError(message)

    with engine_environment(mocker):
        GoldenTraceSceneManager.install()
        try:
            with command_line([
                '--log-level',
                'warning',
                '--resolution',
                f'{STAND_IN_SIZE[0]}x{STAND_IN_SIZE[1]}',
                *replay_arguments,
                '--compare-trace',
                str(color_game.old),
            ]):
                engine = GoldenTraceEngine(game=color_game.scene_class)
            with pytest.raises(SystemExit) as exit_info:
                asyncio.run(engine.start_async(wait_for_tick=wait_for_tick))
        finally:
            GoldenTraceSceneManager.uninstall()

    assert exit_info.value.code == ExitCode.OPTIONS_REFUSED
    assert f'Cannot compare with {color_game.old} here' in caplog.text
    assert 'which start_async (a browser page) cannot start' in caplog.text
    start_command.assert_not_called()
    assert engine.onion_skin is not None
    assert engine.onion_skin.process is None


# The ghost draws only OLD's own items (decision 18 amended; Task D13), told by OLD's background
# colors (Task D16): a color covering at least BACKGROUND_COLOR_SHARE of OLD's frame

# A small maze: a floor (most of it), a wall (two columns: 10%), and dots and sprites of a pixel
# or a few (each well under 5%)
GHOST_FRAME_SIZE = (20, 10)
FLOOR = (10, 20, 30)
WALL = (90, 90, 90)
WALL_COLUMNS = (0, 19)
DOT = (250, 250, 200)
NEW_ITEM = (200, 40, 40)
OLD_ITEM = (40, 200, 40)
# Where the dot is, and where NEW alone, OLD alone, and both have a sprite
DOT_AT = (5, 5)
NEW_ITEM_AT = (8, 2)
OLD_ITEM_AT = (11, 2)
BOTH_ITEMS_AT = (14, 2)


def ghost_frame(*, items: dict[tuple[int, int], tuple[int, int, int]]) -> pygame.Surface:
    """Return the maze (floor and wall) with ``items`` (pixel to color) on it.

    Returns:
        The frame.

    """
    surface = pygame.Surface(GHOST_FRAME_SIZE)
    surface.fill(FLOOR)
    for column in WALL_COLUMNS:
        surface.fill(WALL, (column, 0, 1, GHOST_FRAME_SIZE[1]))
    for position, color in items.items():
        surface.set_at(position, color)
    return surface


def old_pixels(*, surface: pygame.Surface):
    """Return a frame's pixels as OLD's stream carries them, decoded.

    Returns:
        Its rows of RGB.

    """
    return decode_frame_pixels(
        pixels=pygame.image.tobytes(surface, FRAME_PIXEL_FORMAT), size=surface.get_size()
    )


def rgb_of(*, surface: pygame.Surface, position: tuple[int, int]) -> tuple[int, int, int]:
    """Return a surface's red, green and blue at ``position``.

    Returns:
        The color.

    """
    color = surface.get_at(position)
    return (color.r, color.g, color.b)


def frame_bytes(*, surface: pygame.Surface) -> bytes:
    """Return a frame's pixels, to compare whole frames.

    Returns:
        Its RGB bytes.

    """
    return pygame.image.tobytes(surface, FRAME_PIXEL_FORMAT)


def started_together(*, percent: float) -> GhostCompositor:
    """Return a compositor that drew one frame both runs showed alike (the dot still there).

    Both runs of a game start alike, so a rule that learned from agreement (D13's) would have
    learned the dot as background by now; D16's keeps nothing between frames.

    Returns:
        The compositor.

    """
    compositor = GhostCompositor(alpha_percent=percent)
    start = ghost_frame(items={DOT_AT: DOT})
    compositor.draw(surface=start, old=old_pixels(surface=ghost_frame(items={DOT_AT: DOT})))
    return compositor


@dataclasses.dataclass(frozen=True)
class DotCase:
    """One row of the dot table: whether each run's dot is there, and what is drawn there.

    Attributes:
        case: The test id.
        new_has_the_dot: NEW's dot is there (else eaten: the floor shows).
        old_has_the_dot: OLD's dot is there.
        olds_dot_is_drawn: OLD's dot is drawn over NEW there (else NEW's pixel stays exact).

    """

    case: str
    new_has_the_dot: bool
    old_has_the_dot: bool
    olds_dot_is_drawn: bool


DOT_CASES = (
    DotCase(
        case='both-present', new_has_the_dot=True, old_has_the_dot=True, olds_dot_is_drawn=False
    ),
    DotCase(
        case='old-ate-it', new_has_the_dot=True, old_has_the_dot=False, olds_dot_is_drawn=False
    ),
    DotCase(case='new-ate-it', new_has_the_dot=False, old_has_the_dot=True, olds_dot_is_drawn=True),
    DotCase(
        case='both-ate-it', new_has_the_dot=False, old_has_the_dot=False, olds_dot_is_drawn=False
    ),
)


@pytest.mark.parametrize('percent', [DEFAULT_COMPARE_ALPHA_PERCENT, 25.0], ids=['50', '25'])
@pytest.mark.parametrize('dot_case', DOT_CASES, ids=[dot_case.case for dot_case in DOT_CASES])
def test_the_dot_table(dot_case, percent):
    """Each run's dot, there or eaten: only OLD's dot over NEW's floor is drawn, at the alpha.

    The user's report (live Mr. Muncher): an OLD that ate its dot made NEW's dot transparent,
    and NEW's eaten dot hid OLD's. Every other pixel of the frame is NEW's, exactly.
    """
    compositor = started_together(percent=percent)
    new = ghost_frame(items={DOT_AT: DOT} if dot_case.new_has_the_dot else {})
    old = ghost_frame(items={DOT_AT: DOT} if dot_case.old_has_the_dot else {})
    expected = ghost_frame(items={DOT_AT: DOT} if dot_case.new_has_the_dot else {})
    if dot_case.olds_dot_is_drawn:
        expected.set_at(DOT_AT, blended(new=FLOOR, old=DOT, percent=percent))

    compositor.draw(surface=new, old=old_pixels(surface=old))

    assert rgb_of(surface=new, position=DOT_AT) == rgb_of(surface=expected, position=DOT_AT)
    assert frame_bytes(surface=new) == frame_bytes(surface=expected)
    if dot_case.olds_dot_is_drawn:
        # Exact: (250, 250, 200) over (10, 20, 30)
        assert rgb_of(surface=new, position=DOT_AT) == (
            (130, 135, 115) if percent == DEFAULT_COMPARE_ALPHA_PERCENT else (70, 78, 73)
        )


@pytest.mark.parametrize('percent', [DEFAULT_COMPARE_ALPHA_PERCENT, 25.0], ids=['50', '25'])
def test_olds_sprite_is_drawn_at_the_alpha_over_new(percent):
    """OLD's sprite is blended over whatever NEW shows: the floor, or NEW's own sprite."""
    compositor = started_together(percent=percent)
    new = ghost_frame(items={NEW_ITEM_AT: NEW_ITEM, BOTH_ITEMS_AT: NEW_ITEM})
    old = ghost_frame(items={OLD_ITEM_AT: OLD_ITEM, BOTH_ITEMS_AT: OLD_ITEM})

    compositor.draw(surface=new, old=old_pixels(surface=old))

    assert rgb_of(surface=new, position=OLD_ITEM_AT) == blended(
        new=FLOOR, old=OLD_ITEM, percent=percent
    )
    assert rgb_of(surface=new, position=BOTH_ITEMS_AT) == blended(
        new=NEW_ITEM, old=OLD_ITEM, percent=percent
    )
    # NEW's own sprite, with OLD's floor there, stays solid
    assert rgb_of(surface=new, position=NEW_ITEM_AT) == NEW_ITEM
    expected_at_25 = (17, 65, 32)
    if percent == 25.0:
        assert rgb_of(surface=new, position=OLD_ITEM_AT) == expected_at_25


def test_new_is_never_altered_where_old_shows_a_background_color():
    """NEW's sprite over OLD's floor or wall stays exactly NEW's, whatever came before."""
    compositor = started_together(percent=DEFAULT_COMPARE_ALPHA_PERCENT)
    wall_at = (WALL_COLUMNS[0], 4)
    new = ghost_frame(items={NEW_ITEM_AT: NEW_ITEM, wall_at: NEW_ITEM})
    expected = ghost_frame(items={NEW_ITEM_AT: NEW_ITEM, wall_at: NEW_ITEM})

    compositor.draw(surface=new, old=old_pixels(surface=ghost_frame(items={})))

    assert frame_bytes(surface=new) == frame_bytes(surface=expected)


def test_identical_frames_draw_nothing():
    """A frame OLD and NEW share draws nothing, the first one and any after it."""
    compositor = GhostCompositor(alpha_percent=DEFAULT_COMPARE_ALPHA_PERCENT)
    for _ in range(2):
        new = ghost_frame(items={NEW_ITEM_AT: NEW_ITEM, DOT_AT: DOT})
        compositor.draw(
            surface=new,
            old=old_pixels(surface=ghost_frame(items={NEW_ITEM_AT: NEW_ITEM, DOT_AT: DOT})),
        )
        assert frame_bytes(surface=new) == frame_bytes(
            surface=ghost_frame(items={NEW_ITEM_AT: NEW_ITEM, DOT_AT: DOT})
        )


@pytest.mark.parametrize(
    ('pixels', 'is_background'),
    [(10, True), (9, False)],
    ids=['exactly-5-percent', 'under-5-percent'],
)
def test_a_color_at_exactly_the_share_is_a_background_color(pixels, is_background):
    """10 pixels of 200 (5%, BACKGROUND_COLOR_SHARE) is background; 9 (4.5%) is an item."""
    assert compare.BACKGROUND_COLOR_SHARE == 0.05
    old = ghost_frame(items={})
    # The color fills the wall's first column (10 pixels), or all but one of them
    old.fill(OLD_ITEM, (WALL_COLUMNS[0], 0, 1, pixels))
    new = ghost_frame(items={})
    compositor = GhostCompositor(alpha_percent=DEFAULT_COMPARE_ALPHA_PERCENT)

    compositor.draw(surface=new, old=old_pixels(surface=old))

    drawn = rgb_of(surface=new, position=(WALL_COLUMNS[0], 0))
    assert drawn == (WALL if is_background else blended(new=WALL, old=OLD_ITEM, percent=50.0))


def test_olds_sprite_pixels_in_a_background_color_are_not_shown():
    """The rule's known cost: OLD's sprite drawn in the wall's own color shows no ghost there."""
    compositor = GhostCompositor(alpha_percent=DEFAULT_COMPARE_ALPHA_PERCENT)
    new = ghost_frame(items={OLD_ITEM_AT: NEW_ITEM})
    old = ghost_frame(items={OLD_ITEM_AT: WALL})

    compositor.draw(surface=new, old=old_pixels(surface=old))

    assert rgb_of(surface=new, position=OLD_ITEM_AT) == NEW_ITEM


def test_an_old_frame_drawn_again_over_another_new_frame_draws_as_a_fresh_one():
    """OLD's colors, worked out once per OLD frame, give each NEW frame what a fresh draw would."""
    old = old_pixels(surface=ghost_frame(items={DOT_AT: DOT, OLD_ITEM_AT: OLD_ITEM}))
    reused = GhostCompositor(alpha_percent=DEFAULT_COMPARE_ALPHA_PERCENT)
    for new_items in ({}, {OLD_ITEM_AT: NEW_ITEM, NEW_ITEM_AT: NEW_ITEM}):
        drawn_again = ghost_frame(items=new_items)
        reused.draw(surface=drawn_again, old=old)
        fresh = ghost_frame(items=new_items)
        GhostCompositor(alpha_percent=DEFAULT_COMPARE_ALPHA_PERCENT).draw(surface=fresh, old=old)

        assert frame_bytes(surface=drawn_again) == frame_bytes(surface=fresh), new_items


@pytest.mark.parametrize('item_count', [1, 30], ids=['few-items', 'many-items'])
def test_few_and_many_items_blend_alike(item_count):
    """Gathered one by one (few) or blended whole and kept (many), OLD's items look the same.

    Each item has a color of its own, so none is a background color (each covers 1 pixel).
    """
    item_colors = [(40 + index * 6, 200, 40) for index in range(item_count)]
    positions = [(1 + index % 18, index // 18) for index in range(item_count)]
    old = ghost_frame(items=dict(zip(positions, item_colors, strict=True)))
    new = ghost_frame(items={})
    compositor = GhostCompositor(alpha_percent=DEFAULT_COMPARE_ALPHA_PERCENT)

    compositor.draw(surface=new, old=old_pixels(surface=old))

    expected = ghost_frame(items={})
    for position, color in zip(positions, item_colors, strict=True):
        expected.set_at(
            position, blended(new=FLOOR, old=color, percent=DEFAULT_COMPARE_ALPHA_PERCENT)
        )
    assert frame_bytes(surface=new) == frame_bytes(surface=expected)


# Pausing freezes the ghost (Task D14): OLD is paired by game frames, a pause screen's left out


def assert_old_follows_the_game_frames(*, pairs: dict[int, int | None]) -> None:
    """Assert each frame of a pausing run was paired with OLD's frame of its game frame.

    Args:
        pairs: The OLD frame held on each frame shown, by the frame's number.

    """
    assert pairs
    for frame_index, old_frame_index in pairs.items():
        assert old_frame_index == GAME_FRAME_OF_A_PAUSING_RUN[frame_index], frame_index


def test_pausing_freezes_old_in_live_play(color_game, mocker):
    """While the game is paused, OLD's frame stays; it moves on with the game's next frame."""
    run = live_play(
        mocker=mocker,
        scene_class=color_game.scene_class,
        arguments=('--random-seed', str(PAUSING_SEED), '--compare-trace', str(color_game.old)),
    )

    assert live_run_succeeded(run=run), run.exit_status
    assert run.engine.host is not None
    assert run.engine.host.sources.frames_ended == len(GAME_FRAME_OF_A_PAUSING_RUN)
    pairs = {frame.frame_index: frame.old_frame_index for frame in run.presented}
    assert set(pairs) == set(range(len(GAME_FRAME_OF_A_PAUSING_RUN)))
    assert_old_follows_the_game_frames(pairs=pairs)
    for frame in run.presented:
        # No label while paused: OLD has not ended, it waits
        assert frame.label is None, frame


def record_a_pausing_run(*, color_game: ColorGame, path: Path) -> Path:
    """Record the color game under ``PAUSING_SEED`` (it pauses itself once).

    Returns:
        The recording.

    """
    # Paced, as OLD is (color_game): the watched replays present its frames by their recorded
    # frame times
    recording = record_stand_in_game(
        game=color_game.game,
        path=path,
        extra_arguments=('--random-seed', str(PAUSING_SEED)),
        paced=True,
    )
    assert recorded_frame_count(path=recording) == len(GAME_FRAME_OF_A_PAUSING_RUN)
    return recording


def test_pausing_freezes_old_in_a_watched_replay(color_game, mocker, tmp_path):
    """A recorded pause holds OLD's frame in the replay as it did live."""
    new = record_a_pausing_run(color_game=color_game, path=tmp_path / 'new.jsonl.gz')

    run = watched_replay(
        mocker=mocker,
        scene_class=color_game.scene_class,
        recording=new,
        arguments=('--compare-trace', str(color_game.old)),
    )

    assert run.exit_status == ExitCode.SUCCESS
    pairs = {
        frame.frame_index: frame.old_frame_index
        for frame in run.presented
        if frame.frame_index is not None
    }
    # The replay ends in its last frame, unpresented
    assert set(pairs) == set(range(1, len(GAME_FRAME_OF_A_PAUSING_RUN) - 1))
    assert_old_follows_the_game_frames(pairs=pairs)


def test_a_run_recorded_with_a_pause_pairs_the_same_on_replay(color_game, mocker, tmp_path):
    """Recorded live with a pause against OLD, then replayed against OLD: the same pairs."""
    new = tmp_path / 'new.jsonl.gz'
    live = live_play(
        mocker=mocker,
        scene_class=color_game.scene_class,
        arguments=(
            '--random-seed',
            str(PAUSING_SEED),
            '--record-trace',
            str(new),
            '--compare-trace',
            str(color_game.old),
        ),
    )
    assert live_run_succeeded(run=live), live.exit_status

    replayed = watched_replay(
        mocker=mocker,
        scene_class=color_game.scene_class,
        recording=new,
        arguments=('--compare-trace', str(color_game.old)),
    )

    assert replayed.exit_status == ExitCode.SUCCESS
    live_pairs = {frame.frame_index: frame.old_frame_index for frame in live.presented}
    replayed_pairs = {
        frame.frame_index: frame.old_frame_index
        for frame in replayed.presented
        if frame.frame_index is not None
    }
    assert replayed_pairs
    for frame_index, old_frame_index in replayed_pairs.items():
        assert live_pairs[frame_index] == old_frame_index, frame_index
    assert_old_follows_the_game_frames(pairs=live_pairs)


def test_a_step_back_across_a_pause_keeps_old_in_step(color_game, mocker, tmp_path):
    """A step back after the pause restarts OLD's child at the game frame shown, not the frame.

    The first replay is paused near its end (rebuilt there) and steps back once; its restart
    command (captured) is then run as the restarted replay: rebuilt and paused at the frame
    before, then on to the end.
    """
    new = record_a_pausing_run(color_game=color_game, path=tmp_path / 'new.jsonl.gz')
    relaunch = mocker.patch.object(game_engine_module, 'relaunch_replay', return_value=0)

    first = watched_replay(
        mocker=mocker,
        scene_class=color_game.scene_class,
        recording=new,
        arguments=(
            '--compare-trace',
            str(color_game.old),
            '--replay-pause-at-frame',
            str(len(GAME_FRAME_OF_A_PAUSING_RUN) - 1),
        ),
        keys=(pygame.K_COMMA,),
    )

    assert first.exit_status == ExitCode.SUCCESS
    command = relaunch.call_args.kwargs['command']
    pause_at_frame = int(command[command.index('--replay-pause-at-frame') + 1])
    viewer_state = command[command.index('--replay-viewer-state') + 1]
    shown_after_the_restart = pause_at_frame - 1
    # After the pause: a frame number and its game frame differ there
    assert shown_after_the_restart > len(GAME_FRAME_OF_A_PAUSING_RUN) - COLOR_GAME_FRAMES
    first_game_frame = GAME_FRAME_OF_A_PAUSING_RUN[shown_after_the_restart]
    assert first_game_frame != shown_after_the_restart

    restarted = watched_replay(
        mocker=mocker,
        scene_class=color_game.scene_class,
        recording=new,
        arguments=(
            '--compare-trace',
            str(color_game.old),
            '--replay-pause-at-frame',
            str(pause_at_frame),
            '--replay-viewer-state',
            viewer_state,
        ),
    )

    assert restarted.exit_status == ExitCode.SUCCESS
    child_command = restarted.onion_skin.command
    # The child is told the game frame (as a pause frame: one past it, rule 8)
    assert child_command[child_command.index('--replay-pause-at-frame') + 1] == str(
        first_game_frame + 1
    )
    pairs = {
        frame.frame_index: frame.old_frame_index
        for frame in restarted.presented
        if frame.frame_index is not None
    }
    assert min(pairs) == shown_after_the_restart
    assert_old_follows_the_game_frames(pairs=pairs)
    # The child sent only the game frames shown from there on
    assert restarted.onion_skin.frames_received == len(set(pairs.values()))


def test_olds_own_pauses_are_skipped(color_game, mocker, tmp_path):
    """OLD paused where the live game did not: its pause screen's frames are never sent."""
    pausing_old = record_a_pausing_run(color_game=color_game, path=tmp_path / 'old.jsonl.gz')

    run = live_play(
        mocker=mocker,
        scene_class=color_game.scene_class,
        arguments=('--random-seed', str(NEW_SEED), '--compare-trace', str(pausing_old)),
    )

    assert live_run_succeeded(run=run), run.exit_status
    assert run.presented
    for frame in run.presented:
        # This game never pauses: its frame N is its game frame N, paired with OLD's
        assert frame.old_frame_index == frame.frame_index, frame
        assert frame.sample == blended(
            new=frame_color(seed=NEW_SEED, frame_index=frame.frame_index),
            old=frame_color(seed=PAUSING_SEED, frame_index=frame.frame_index),
            percent=DEFAULT_COMPARE_ALPHA_PERCENT,
        ), frame
    # OLD's six game frames came, none of its pause screen's three
    assert run.onion_skin.frames_received == COLOR_GAME_FRAMES


def test_the_child_streams_only_game_frames(color_game, mocker, tmp_path):
    """A headless replay of a pausing run streams its game frames, numbered 0 to N - 1, only."""
    pausing = record_a_pausing_run(color_game=color_game, path=tmp_path / 'pausing.jsonl.gz')
    listener = FrameStreamListener()

    replay = replay_through_engine(
        mocker=mocker,
        scene_class=color_game.scene_class,
        path=pausing,
        extra_arguments=('--replay-frame-stream', listener.address),
    )
    frames = listener.finish()

    assert replay.exit_status == ExitCode.SUCCESS
    assert [frame.frame_index for frame in frames] == list(range(COLOR_GAME_FRAMES))
    for frame in frames:
        # Each game frame's own picture, as presented (never a pause screen's)
        assert frame.sample == frame_color(seed=PAUSING_SEED, frame_index=frame.frame_index)
