#!/usr/bin/env python3
"""Contains GameEngine and helper classes for building a game."""

from __future__ import annotations

import argparse
import contextlib
import cProfile
import functools
import logging
import math
import multiprocessing
import os
import platform
import signal
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal, NoReturn, Self, override

import pygame

from glitchygames import events
from glitchygames.backgrounds import (
    DEFAULT_BACKGROUND_PATTERN,
    BackgroundPattern,
    paint_default_background,
    set_active_default_background_pattern,
)
from glitchygames.build_info import engine_source_revision
from glitchygames.clock import elapsed_seconds
from glitchygames.color import PURPLE
from glitchygames.crt_power_on import (
    CrtPowerOnMode,
    PowerOnOutcome,
    play_power_on,
    play_power_on_async,
    should_play,
)
from glitchygames.display_mode import set_display_mode
from glitchygames.events.app import AppEventManager
from glitchygames.events.audio import AudioEventManager
from glitchygames.events.controller import ControllerEventManager
from glitchygames.events.drop import DropEventManager
from glitchygames.events.game import GameEventManager
from glitchygames.events.joystick import JoystickEventManager
from glitchygames.events.keyboard import KeyboardEventManager
from glitchygames.events.midi import MidiEventManager
from glitchygames.events.mouse import MouseEventManager
from glitchygames.events.touch import TouchEventManager
from glitchygames.events.window import WindowEventManager
from glitchygames.exit_codes import ExitCode
from glitchygames.fonts import FontManager
from glitchygames.host import GameHost, HostSources
from glitchygames.input.device_listing import list_input_devices
from glitchygames.input.input_devices import InputDevices, InputMode
from glitchygames.input.state import current_input, reset_current_input, set_current_input
from glitchygames.live_sources import LiveSources
from glitchygames.machine_state import current_machine_state
from glitchygames.output_files import output_refusal, partial_path
from glitchygames.randomness import seed_engine_random
from glitchygames.recording import (
    DEVICE_ENUMERATION_FIELD,
    DEVICES_HEADER_FIELD,
    RECORDED_AT_HEADER_FIELD,
    SAVES_HEADER_FIELD,
    GameplayRecorder,
    RecordingSources,
    RecordingWriteError,
    TraceRecordingAlreadyStartedError,
    forget_pending_posts,
    json_safe_value,
    pending_internal_posts,
    post_event,
    post_input_event,
    reset_internal_post_tracking,
    start_tracking_internal_posts,
)
from glitchygames.recording_history import (
    CONTENT_HASH_SCHEME,
    MEASUREMENT_RUNS_HEADER_FIELD,
    MeasurementRun,
)
from glitchygames.replay.audit import (
    AuditRunError,
    audit_command,
    audit_recording,
    environment_reaches_children,
)
from glitchygames.replay.driver import (
    REAL_REPLAY_FPS,
    REPLAY_FPS_CHOICES,
    RUNNING_END_REASON,
    ReplayRefusedError,
    ReplaySources,
    announce_replay,
    display_size_refusal,
    installed_engine_version,
    replayed_batch_origins,
    start_replay,
)
from glitchygames.replay.processing import machine_description
from glitchygames.replay.rebaseline import Rebaseline, rebaseline_refusal
from glitchygames.replay.rebuild import (
    ViewerState,
    parse_viewer_state,
    relaunch_replay,
    restart_command,
)
from glitchygames.replay.viewer import run_watched_replay_async
from glitchygames.scenes import Scene, SceneManager
from glitchygames.sources import (
    active_sources,
    install_sources,
    reset_sources,
    take_redelivered_events,
)
from glitchygames.sprites import Sprite
from glitchygames.state.sandbox import save_namespace_snapshot
from glitchygames.supervision import BREAKPOINT_KIND
from glitchygames.timing import (
    DEFAULT_SLEEP_GRANULARITY_NS,
    DEFAULT_TARGET_FPS,
    GIL_SWITCH_INTERVAL_SECONDS,
    TIMER_BACKEND_AUTO,
    TIMER_BACKEND_FAST,
    TIMER_BACKEND_PYGAME,
    create_timer,
    pacing_timer_for_options,
)
from glitchygames.tracing import TraceFormatError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Generator, Mapping
    from types import FrameType

    from glitchygames.input.state import InputSnapshot

LOG: logging.Logger = logging.getLogger('game.engine')
LOG.addHandler(logging.NullHandler())


# The glitchygames package directory, and its assets (the default window icon). This module is
# glitchygames/engine/game_engine.py: both were Path(__file__).parent-based when the engine was
# glitchygames/engine.py, and pointed into glitchygames/engine/ after it became a package, so
# the default icon was never found
PACKAGE_PATH: Path = Path(__file__).parent.parent
ASSET_PATH: Path = PACKAGE_PATH / 'assets'
TEST_MODE = False

PYGAME_MIN_MAJOR_VERSION = 2
PYGAME_MIN_MINOR_VERSION = 2
UNKNOWN_SDL2_EVENT_TYPE_1543 = 1543

GAME_NOT_INITIALIZED_MSG = 'Game not initialized.  Pass a game class to the GameEngine constructor.'
ASYNC_RUN_NEEDS_HOST_MSG = (
    'start_async() runs live games and watched replays only: a headless replay never gives '
    'control back between frames; run it with start()'
)
MISSING_ATTRIBUTE_MSG = "'{cls}' object has no attribute '{attr}'"

DEFAULT_SCREEN_SHAKE_INTENSITY = 1.0
DEFAULT_RUMBLE_INTENSITY = 1.0
DEFAULT_LIVE_VOICE_POOL = 4
# The SDL video and audio driver --headless runs on (no window, no sound)
HEADLESS_SDL_DRIVER = 'dummy'
# The environment variables that choose SDL's video and audio drivers (--headless sets both)
SDL_DRIVER_VARIABLES = ('SDL_VIDEODRIVER', 'SDL_AUDIODRIVER')
# --video-driver's choices: SDL 2's video drivers by platform.system() name (SDL's own list,
# src/video/SDL_video.c bootstrap[]; checked on macOS: cocoa, offscreen and dummy start, metal and
# x11 are not drivers of pygame-ce's SDL there), then the ones SDL builds on every platform
PLATFORM_VIDEO_DRIVERS: dict[str, tuple[str, ...]] = {
    'Darwin': ('cocoa',),
    'Windows': ('windows',),
    'Linux': ('x11', 'wayland', 'kmsdrm'),
}
PORTABLE_VIDEO_DRIVERS = ('offscreen', 'dummy')

# The signals that end a run through the normal teardown (exit_on_signal), by name:
# SIGHUP exists only on Unix and SIGBREAK only on Windows, so each is looked up where it runs.
# SIGINT needs no handler (KeyboardInterrupt); see glitchygames/exit_codes.py for those not wired
TERMINATING_SIGNAL_NAMES = ('SIGTERM', 'SIGHUP', 'SIGBREAK')


def pygame_needs_fastevents() -> bool:
    """Report whether this pygame is older than 2.2 and so reads events with pygame.fastevent.

    Returns:
        True for pygame < 2.2.

    """
    return (
        pygame.version.vernum[0] < PYGAME_MIN_MAJOR_VERSION
        and pygame.version.vernum[1] < PYGAME_MIN_MINOR_VERSION
    )


def unit_interval(value: str) -> float:
    """Argparse type: a float from 0.0 to 1.0 inclusive.

    Args:
        value: The command-line text.

    Returns:
        The parsed float.

    Raises:
        argparse.ArgumentTypeError: If the text is not a number in 0.0-1.0.

    """
    try:
        number = float(value)
    except ValueError as error:
        message = f'{value!r} is not a number'
        raise argparse.ArgumentTypeError(message) from error
    if not 0.0 <= number <= 1.0:  # Also rejects NaN, which fails every comparison
        message = f'{value!r} must be between 0.0 and 1.0'
        raise argparse.ArgumentTypeError(message)
    return number


def target_fps_value(value: str) -> float:
    """Argparse type: a finite float >= 0 (0 means uncapped).

    Args:
        value: The command-line text.

    Returns:
        The parsed float.

    Raises:
        argparse.ArgumentTypeError: If the text is not a finite number >= 0.

    """
    try:
        number = float(value)
    except ValueError as error:
        message = f'{value!r} is not a number'
        raise argparse.ArgumentTypeError(message) from error
    if not math.isfinite(number) or number < 0.0:
        message = f'{value!r} must be a finite number >= 0 (0 = uncapped)'
        raise argparse.ArgumentTypeError(message)
    return number


def non_negative_percent(value: str) -> float:
    """Argparse type: a finite percentage >= 0.

    Args:
        value: The command-line text.

    Returns:
        The parsed percentage.

    Raises:
        argparse.ArgumentTypeError: If the text is not a finite number >= 0.

    """
    try:
        number = float(value)
    except ValueError as error:
        message = f'{value!r} is not a number'
        raise argparse.ArgumentTypeError(message) from error
    if not math.isfinite(number) or number < 0:
        message = f'{value!r} must be a finite number >= 0'
        raise argparse.ArgumentTypeError(message)
    return number


def non_negative_int(value: str) -> int:
    """Argparse type: an integer >= 0.

    Args:
        value: The command-line text.

    Returns:
        The parsed integer.

    Raises:
        argparse.ArgumentTypeError: If the text is not an integer >= 0.

    """
    try:
        number = int(value)
    except ValueError as error:
        message = f'{value!r} is not an integer'
        raise argparse.ArgumentTypeError(message) from error
    if number < 0:
        message = f'{value!r} must be >= 0'
        raise argparse.ArgumentTypeError(message)
    return number


def terminating_signals() -> list[int]:
    """Return the TERMINATING_SIGNAL_NAMES this platform has, as signal numbers.

    Returns:
        SIGTERM, plus SIGHUP on Unix or SIGBREAK on Windows.

    """
    return [getattr(signal, name) for name in TERMINATING_SIGNAL_NAMES if hasattr(signal, name)]


def exit_on_signal(signal_number: int, _frame: FrameType | None) -> None:
    """End the run with SystemExit, so GameEngine.start()'s teardown still runs.

    Installed by ``GameEngine.start`` for each of ``terminating_signals()`` that nothing else
    handles, for the whole run, so a recording is closed by ``_shutdown``. It ignores further
    signals of the same kind before raising: a second SIGTERM (``uv run`` forwards one to its
    child as well, and ``pkill`` can match both) would otherwise raise again inside the teardown
    and leave the recording unclosed. ``_shutdown`` restores the default handling after closing
    the recording. It does nothing else: logging here could fail with "reentrant call" if the
    signal interrupted a write to the same stream.

    Args:
        signal_number: The signal received.
        _frame: The interrupted frame (unused).

    Raises:
        SystemExit: Always, with ``ExitCode.for_signal(signal_number)`` (``TERMINATED`` for
            SIGTERM, ``HANGUP`` for SIGHUP, ``BREAK`` for SIGBREAK).

    """
    signal.signal(signal_number, signal.SIG_IGN)
    raise SystemExit(ExitCode.for_signal(signal_number))


def input_device_prompt() -> Callable[[str], None] | None:
    """Return how --list-input-devices prompts for a device, or None when it must not wait.

    It prompts only when stdin and stdout are a terminal: a person is there to plug a device in
    (or press Ctrl-C). A script, a pipe or CI gets the listing at once, never a wait.

    Returns:
        A writer of the prompt line (to stdout, flushed), or None.

    """
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return None

    def write_prompt(message: str) -> None:
        sys.stdout.write(f'{message}\n')
        sys.stdout.flush()

    return write_prompt


def exit_with(*, exit_code: ExitCode, cause: BaseException | None = None) -> NoReturn:
    """Log the exit code the engine exits with (``ExitCode.describe()``) and exit with it.

    Args:
        exit_code: The code.
        cause: The exception that led to the exit, chained as the SystemExit's cause.

    Raises:
        SystemExit: Always, with ``exit_code``.

    """
    LOG.info('Exiting with %s', exit_code.describe())
    raise SystemExit(exit_code) from cause


@dataclass
class UnhandledEventRecord:
    """Statistics for one unhandled event type over a whole run.

    Attributes:
        count: How many events of this type went unhandled.
        first_seen_seconds: When the first one arrived, in seconds since the engine started.
        attribute_names: The first event's attribute names, sorted (never their values).

    """

    count: int
    first_seen_seconds: float
    attribute_names: tuple[str, ...]


class GameEngine(events.EventManager):  # ruff: ignore[too-many-public-methods]
    """Glitchy Games' Game engine.

    The game engine is responsible for initializing pygame and
    handling events.  It also provides a number of helper methods
    for common tasks such as setting the screen resolution and
    setting the cursor.

    Every Glitchy Game game inherits the GameEngine command line
    options, so you can add your own command line options by
    implementing the args() class method in your Scene class.
    """

    log: ClassVar[logging.Logger] = LOG
    game: Any = None

    _icon_path = Path(ASSET_PATH) / 'glitch.png'
    icon: pygame.Surface = (
        pygame.image.load(_icon_path) if _icon_path.exists() else pygame.Surface((32, 32))
    )

    NAME: Literal['Boilerplate Adventures'] = 'Boilerplate Adventures'
    VERSION: Literal['1.0'] = '1.0'
    OPTIONS: ClassVar[dict[str, Any]] = {}

    LAST_EVENT_MISS: ClassVar[str] = ''
    MISSING_EVENTS: ClassVar[list[str]] = []
    UNIMPLEMENTED_EVENTS: ClassVar[list[int]] = []
    USE_FASTEVENTS: ClassVar[bool] = False

    # We add a layer of encapsulation here to simplify
    # the processing of events.  New event types added
    # to the events module need to be accounted for here
    # if they're not already handled
    #
    # These are wired up at the end of __init__()
    EVENT_HANDLERS: ClassVar[dict[int, Callable[..., Any]]] = {}

    # The --record-trace recorder while recording (start_trace_recording), else None; the
    # RecordingSources it installs write to it. A class default so it reads None on an engine
    # whose __init__ did not run.
    trace_recorder: GameplayRecorder | None = None
    # True once a recording's file could not be written (GameplayRecorder.write_failed, read as
    # it is closed): the run then exits CANNOT_WRITE_OUTPUT (BUGS.md #82). Set on the instance
    # only; the class default reads False on an engine whose __init__ did not run.
    recording_write_failed: bool = False
    # The --replay-trace doors while replaying (installed in __init__ before the first frame),
    # else None. A class default so it reads None on an engine whose __init__ did not run.
    replay_sources: ReplaySources | None = None
    # The --rebaseline writer while rebaselining (glitchygames/replay/rebaseline.py), else None.
    # A class default so it reads None on an engine whose __init__ did not run.
    rebaseline: Rebaseline | None = None

    @classmethod
    def initialize_icon(cls: Any, icon: pygame.Surface | Path | str | None = None) -> None:
        """Initialize the game icon.

        Args:
            cls: the GlitchyGames GameEngine class.
            icon: a pygame.Surface, Path, str path, or None.

        """
        if icon is None:
            return

        # If it's already a pygame.Surface, use it directly
        if isinstance(icon, pygame.Surface):
            GameEngine.icon = icon
        else:
            # If it's not a pygame.Surface, assume it's a path
            icon_path: Path = Path(icon)

            with contextlib.suppress(FileNotFoundError):
                GameEngine.icon = pygame.image.load(icon_path)

    @classmethod
    def args(cls: Any, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add Glitchy Games arguments to the argument parser.

        All Glitchy Games will inherit these arguments.

        The effective target FPS is resolved in initialize_arguments: an explicit
        --target-fps (including 0 = uncapped) wins, then the game scene class's
        TARGET_FPS if it is not None, then DEFAULT_TARGET_FPS (60.01).

        Supported Arguments:
            -f, --target-fps (default: the game's TARGET_FPS, else 60.01; 0 = uncapped)
            --fps-log-interval-ms
            -w, --windowed, --no-windowed (default: windowed)
            -r, --resolution
            --use-gfxdraw
            --update-type
            --video-driver
            --debug-events

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            argparse.ArgumentParser: The result.

        """
        group = parser.add_argument_group('Graphics Options')
        # How any run is watched, recorded, replayed or diagnosed, whatever the game
        diagnostics_group = parser.add_argument_group('Diagnostics Options')

        group.add_argument(
            '-f',
            '--target-fps',
            help="cap the framerate (default: the game's TARGET_FPS, else 60.01; 0 = uncapped)",
            type=target_fps_value,
            default=None,
        )
        group.add_argument(
            '--fps-log-interval-ms',
            help='how often to log the FPS counter in ms (default: 1000)',
            type=float,
            default=1000,
        )
        # A store_true flag defaulting to True could never ask for fullscreen (BUGS.md #76):
        # --no-windowed does, and -w/--windowed keep the command lines from before working
        group.add_argument(
            '-w',
            '--windowed',
            help='run in a window; --no-windowed runs fullscreen (default: windowed)',
            action=argparse.BooleanOptionalAction,
            default=True,
        )
        group.add_argument(
            '-r',
            '--resolution',
            help='the resolution to use (default: %(default)s)',
            default='800x480',
        )
        # Kept as GameEngine.use_gfxdraw, but nothing reads it (Ball and Paddle set their own)
        group.add_argument(
            '--use-gfxdraw',
            help='not used yet: stored, but nothing draws with pygame.gfxdraw because of it',
            action='store_true',
            default=False,
        )
        group.add_argument(
            '--update-type',
            help='update or flip (default: update)',
            choices=['update', 'flip'],
            default='update',
        )
        group.add_argument(
            '--timer-backend',
            help=(
                'timer backend for draw loop pacing (default: auto, the fast backend with this '
                "machine's sleep delay measured, so each sleep wakes in time; fast assumes sleeps "
                'wake on time; pygame is the legacy backend)'
            ),
            choices=[TIMER_BACKEND_AUTO, TIMER_BACKEND_FAST, TIMER_BACKEND_PYGAME],
            default=TIMER_BACKEND_AUTO,
        )
        group.add_argument(
            '--sleep-granularity-ns',
            type=int,
            help=(
                'how long before each frame deadline the fast backend is to wake from its sleep '
                'and spin (ns); 0 spins only'
            ),
            default=DEFAULT_SLEEP_GRANULARITY_NS,
        )
        group.add_argument(
            '--windows-timer-1ms',
            help='on Windows, request 1ms system timer resolution',
            action='store_true',
            default=False,
        )
        diagnostics_group.add_argument(
            '--log-timer-jitter',
            help='log frame pacing jitter statistics periodically',
            action='store_true',
            default=False,
        )
        diagnostics_group.add_argument(
            '--perf-trim-percent',
            type=float,
            help='percent of frames to trim from top and bottom in global FPS report',
            default=5.0,
        )
        diagnostics_group.add_argument(
            '--fps-histogram',
            choices=['equal-range', 'target-relative'],
            help=(
                'FPS histogram buckets in the shutdown report: equal-range (10 equal buckets '
                'spanning the analyzed min to max, default) or target-relative (10%% steps of '
                'the target FPS)'
            ),
            default='equal-range',
        )
        diagnostics_group.add_argument(
            '--debug-overlay',
            help='show the debug overlay at startup (F3 toggles, F4 cycles panels)',
            action=argparse.BooleanOptionalAction,
            default=False,
        )
        # Read by events.unhandled_event (glitchygames/events/base.py); how this run is
        # diagnosed, not what the game does, so a replay keeps its own (REPLAY_LOCAL_OPTIONS)
        diagnostics_group.add_argument(
            '--debug-events',
            help=(
                'log a warning the first time each unhandled event type arrives '
                '(--no-unhandled-events raises on one instead)'
            ),
            action='store_true',
            default=False,
        )
        diagnostics_group.add_argument(
            '--record-trace',
            metavar='PATH',
            help=(
                'record the session (sprites, frame times, input events, random seed) to a '
                'gzip JSON Lines trace for inspection and later replay (default: off)'
            ),
            default=None,
        )
        diagnostics_group.add_argument(
            '--replay-trace',
            metavar='PATH',
            help=(
                'replay a --record-trace recording exactly through the engine, comparing every '
                'frame with it and reporting the first divergence (default: off)'
            ),
            default=None,
        )
        diagnostics_group.add_argument(
            '--replay-fps',
            choices=REPLAY_FPS_CHOICES,
            help=(
                'with --replay-trace: post FPS events from the recorded frame times (recorded, '
                "the default: exact, and compared with the recording) or from this machine's "
                'measured frame times (real: what this machine achieves; FPS events are then '
                'not compared, and sprites that draw the FPS value may diverge)'
            ),
            # None (not RECORDED_REPLAY_FPS) so that giving it without --replay-trace can be
            # warned about; start_replay reads None as recorded
            default=None,
        )
        diagnostics_group.add_argument(
            '--audit',
            action=argparse.BooleanOptionalAction,
            help=(
                'with --replay-trace: instead of replaying, replay the recording twice in fresh '
                'headless processes with different hash seeds and compare every frame with the '
                f'recording and between the runs; exits {ExitCode.SUCCESS:d} when both match, '
                f'{ExitCode.AUDIT_NONDETERMINISTIC:d} otherwise, {ExitCode.INTERNAL_ERROR:d} if '
                'a run could not finish'
            ),
            default=False,
        )
        diagnostics_group.add_argument(
            '--compare-processing',
            action='store_true',
            help=(
                "with --replay-trace --headless: measure each frame's processing time (its "
                'work, without presenting or pacing) and report how it compares with the '
                "recording's (only meaningful on the machine that recorded)"
            ),
            # None (not False) so that giving it without --replay-trace can be warned about
            default=None,
        )
        diagnostics_group.add_argument(
            '--max-processing-slowdown',
            metavar='PERCENT',
            type=non_negative_percent,
            help=(
                'with --replay-trace --headless (implies --compare-processing): a replay that '
                "matched but took more than PERCENT longer than the recording's processing time "
                f'exits {ExitCode.PROCESSING_SLOWER:d}; a recording without processing times '
                f'exits {ExitCode.UNUSABLE_INPUT:d}'
            ),
            default=None,
        )
        diagnostics_group.add_argument(
            '--replay-pause-at-frame',
            metavar='N',
            type=non_negative_int,
            help=(
                'with --replay-trace, watched: skip the start screen, run frames 0 to N - 1 '
                'without showing them, then pause with frame N next (what step back restarts '
                'with; ignored with --headless)'
            ),
            default=None,
        )
        diagnostics_group.add_argument(
            '--replay-restart-handoff',
            metavar='PATH',
            # Internal: the supervising replay process passes it to each replay it restarts,
            # as glitchygames/replay/rebuild.py describes
            help=argparse.SUPPRESS,
            default=None,
        )
        diagnostics_group.add_argument(
            '--replay-viewer-state',
            metavar='JSON',
            type=parse_viewer_state,
            # Internal: a restarted replay's viewer state (speed, debug panel, divergence frame),
            # as glitchygames/replay/rebuild.py describes
            help=argparse.SUPPRESS,
            default=None,
        )
        diagnostics_group.add_argument(
            '--rebaseline',
            metavar='NEW',
            help=(
                'with --replay-trace OLD and --headless: replay OLD on the current code without '
                "stopping at divergences, write the run's recording (OLD's inputs, the current "
                'sprites) to NEW, print a summary of the frames and sprites that changed and '
                f'exit {ExitCode.SUCCESS:d}'
            ),
            default=None,
        )
        diagnostics_group.add_argument(
            '--replay-digest',
            metavar='PATH',
            help=(
                'with --replay-trace: write a SHA-256 of every replayed frame, then the '
                'divergence, to PATH as JSON lines (used by --audit)'
            ),
            default=None,
        )
        group.add_argument(
            '--random-seed',
            type=int,
            help=(
                'master seed for every engine random stream (default: a random 64-bit seed, '
                'logged in recordings)'
            ),
            default=None,
        )
        group.add_argument(
            '--screen-shake-intensity',
            type=unit_interval,
            help='screen shake strength from 0.0 (off) to 1.0 (default: 1.0)',
            default=DEFAULT_SCREEN_SHAKE_INTENSITY,
        )
        group.add_argument(
            '--rumble-intensity',
            type=unit_interval,
            help='controller rumble strength from 0.0 (off) to 1.0 (default: 1.0)',
            default=DEFAULT_RUMBLE_INTENSITY,
        )
        group.add_argument(
            '--live-voice-pool',
            type=non_negative_int,
            help='mixer channels reserved for real-time synth voices (default: 4)',
            default=DEFAULT_LIVE_VOICE_POOL,
        )
        group.add_argument(
            '--crt-power-on',
            choices=[mode.value for mode in CrtPowerOnMode],
            help=(
                "show the game's canvas switching on like a CRT before the game starts: auto "
                "(default: when someone can see it, so not on SDL's dummy driver or before a "
                'replay, audit, rebaseline or recording), on (always; refused with a replay or '
                'a recording) or off'
            ),
            default=CrtPowerOnMode.AUTO.value,
        )
        group.add_argument(
            '--default-background',
            choices=[pattern.value for pattern in BackgroundPattern],
            help=(
                'the background of a scene that sets none: the TV test pattern or the channel 3 '
                f'blue screen (default: {DEFAULT_BACKGROUND_PATTERN.value})'
            ),
            default=None,
        )

        # SDL 2's video drivers for this platform (SDL_VIDEODRIVER names; the old list held SDL 1's,
        # and its macOS branch compared with 'MacOS', which platform.system() never returns:
        # macOS is 'Darwin', BUGS.md #76). offscreen and dummy are built into SDL everywhere.
        video_driver_choices = [
            *PLATFORM_VIDEO_DRIVERS.get(platform.system(), ()),
            *PORTABLE_VIDEO_DRIVERS,
        ]
        LOG.debug('Video Driver Choices: %s', video_driver_choices)
        # Parsed and recorded, but never handed to SDL: nothing sets SDL_VIDEODRIVER from it
        group.add_argument(
            '--video-driver',
            help=(
                'not applied yet: stored, but SDL picks its video driver from SDL_VIDEODRIVER '
                '(or --headless) instead'
            ),
            default=None,
            choices=video_driver_choices,
        )

        diagnostics_group.add_argument(
            '--list-input-devices',
            action='store_true',
            help=(
                'print every joystick and game controller the game would see (index, instance '
                'id, name, GUID, whether SDL maps it as a game controller, its axes, buttons, '
                'hats and balls; how many SDL counted before its queue was pumped and each '
                'device added or removed while listening, with when), then exit '
                f'{ExitCode.SUCCESS:d} without running the game. At a terminal, when none is '
                'found it asks you to plug one in and waits for it (Ctrl-C stops). Refused with '
                '--replay-trace or --record-trace'
            ),
            default=False,
        )

        diagnostics_group.add_argument(
            '--headless',
            action='store_true',
            help=(
                "run on SDL's dummy video and audio drivers: no window, no sound. With "
                '--replay-trace the replay also runs unpaced and prints its report to stdout '
                f'(exit {ExitCode.SUCCESS:d} when it matches, {ExitCode.REPLAY_DIVERGED:d} '
                f'when it diverges, {ExitCode.UNUSABLE_INPUT:d} for a truncated recording)'
            ),
            default=False,
        )

        event_managers = (
            AppEventManager,
            AudioEventManager,
            ControllerEventManager,
            DropEventManager,
            FontManager,
            GameEventManager,
            JoystickEventManager,
            KeyboardEventManager,
            MidiEventManager,
            MouseEventManager,
            TouchEventManager,
            WindowEventManager,
        )

        for event_manager in event_managers:
            parser = event_manager.args(parser=parser)

        return parser

    @staticmethod
    def resolve_target_fps(
        *,
        command_line_target_fps: float | None,
        game: type[Scene] | Scene,
    ) -> float:
        """Resolve the effective target FPS.

        Order: explicit command line value (0 = uncapped) > the game's TARGET_FPS
        (when not None) > DEFAULT_TARGET_FPS.

        Args:
            command_line_target_fps: The --target-fps value, or None if it was not passed.
            game: The game scene class or instance, which may declare TARGET_FPS.

        Returns:
            float: The effective target FPS (0 means uncapped).

        Raises:
            TypeError: If the game's TARGET_FPS is neither None nor a (non-bool) number.
            ValueError: If the game's TARGET_FPS is negative, NaN or infinite.

        """
        if command_line_target_fps is not None:
            return float(command_line_target_fps)

        # Looked up by name: TARGET_FPS is optional on a game (Scene does not declare it)
        game_target_fps = getattr(game, 'TARGET_FPS', None)
        if game_target_fps is None:
            return DEFAULT_TARGET_FPS

        scene_class = game if isinstance(game, type) else type(game)
        # bool is a subclass of int, so it must be rejected explicitly.
        if isinstance(game_target_fps, bool) or not isinstance(game_target_fps, (int, float)):
            message = (
                f'{scene_class.__name__}.TARGET_FPS must be a number or None, '
                f'got {game_target_fps!r}'
            )
            raise TypeError(message)
        if not math.isfinite(game_target_fps) or game_target_fps < 0:
            message = (
                f'{scene_class.__name__}.TARGET_FPS must be a finite number >= 0 '
                f'(0 = uncapped), got {game_target_fps!r}'
            )
            raise ValueError(message)

        return float(game_target_fps)

    @classmethod
    def initialize_arguments(cls, game: type[Scene] | Scene) -> dict[str, Any]:
        """Initialize the game arguments.

        Args:
            game: The game instance.

        Returns:
            options (dict[str, Any]): The game arguments.

        """
        parser: argparse.ArgumentParser = argparse.ArgumentParser(
            f'{game.NAME} version {game.VERSION}',
        )

        parser = GameEngine.args(parser)

        # args is a class method, which allows us to call it before initializing a game
        # object, which allows us to query all of the game engine objects for their
        # command line parameters. It is optional (Scene does not declare it): looked up by name
        game_args_method: Callable[..., Any] | None = getattr(game, 'args', None)
        if game_args_method is not None:
            game_args_method(parser.add_argument_group(f'{game.NAME} v{game.VERSION} Options'))
        else:
            cls.log.info('Game does not implement arguments.  Add a def args(parser) class method.')

        args: argparse.Namespace = parser.parse_args()

        # Set the logging level
        logging.basicConfig(
            format='%(name)s - %(levelname)s - %(message)s',
            level=args.log_level.upper(),
        )

        GameEngine.OPTIONS = vars(args)  # type: ignore[reportConstantRedefinition]

        # Resolve the effective target FPS; --target-fps defaults to None so that an explicit
        # value (including 0 = uncapped) can be told apart from "not passed".
        GameEngine.OPTIONS['target_fps'] = cls.resolve_target_fps(
            command_line_target_fps=GameEngine.OPTIONS.get('target_fps'),
            game=game,
        )

        options: dict[str, Any] = GameEngine.OPTIONS

        # Back propagate the options
        game.options = options

        return options

    def __init__(  # ruff: ignore[too-many-statements]
        self: Self,
        game: type[Scene] | Scene,
        icon: pygame.Surface | Path | str | None = None,
    ) -> None:
        """Initialize the game engine.

        Args:
            game: The game instance.
            icon: The game icon.

        """
        super().__init__()
        # The frame-pacing timer, created as the run starts (_configure_timer_and_performance);
        # declared first, as a rebaseline names its run (measurement_run) before then
        self.timer: Any = None

        self.initialize_icon(icon=icon)

        options = self.initialize_arguments(game=game)
        # The SDL driver variables as they were before --headless set them (by name; None: the
        # variable was not set), put back when the run ends (_restore_sdl_driver_variables);
        # None when the run is not headless and changed nothing
        self._sdl_driver_variables_before_headless: dict[str, str | None] | None = None
        # Before anything starts the display or the mixer (pygame.init() below)
        if options.get('headless'):
            self._enter_headless_mode()

        # NOTE: Game is coupled to event manager for unhandled event routing.
        # Decoupling tracked in https://glitchy-games.atlassian.net/browse/GG-22
        super().__init__()

        self._active_scene: Scene | None = None
        # The signals exit_on_signal is installed for (by start(), and around a wait for child
        # processes: _waiting_for_child_processes, which --audit uses before start() runs)
        self._installed_signal_handlers: list[int] = []

        # A replay's recorded options and seed are in place from here on (start_replay), so
        # everything below reads the options as the recorded run did
        self.replay_sources = self._start_requested_replay(game=game, options=options)
        # --rebaseline NEW records the replay into NEW (glitchygames/replay/rebaseline.py); its
        # options were checked with the replay's
        rebaseline_path = options.get('rebaseline')
        self.rebaseline = (
            None
            if self.replay_sources is None or rebaseline_path is None
            else Rebaseline(
                replay_sources=self.replay_sources,
                source_path=Path(options['replay_trace']),
                destination=Path(rebaseline_path),
                # A headless replay: its frames are not paced
                measurement_run=self.measurement_run(
                    processing_paced=False, rebaselined_from=options['replay_trace']
                ),
            )
        )
        # Set the master seed of the engine random streams before any game code runs
        # (see glitchygames/randomness.py); start_replay already seeded them with the recorded
        # seed
        self.random_seed: int = (
            self.replay_sources.random_seed
            if self.replay_sources is not None
            else seed_engine_random(seed=options.get('random_seed'))
        )
        # The background a scene that sets none shows (glitchygames/backgrounds.py); without
        # the option the process's default (the test pattern) stays
        default_background = options.get('default_background')
        if default_background is not None:
            set_active_default_background_pattern(pattern=BackgroundPattern(default_background))

        # Unhandled events by type, reported at teardown (see unhandled_event_report); their
        # first-seen times are elapsed_seconds() readings, the frame clock that
        # reset_sources() below restarts, so they count from this engine's start
        self.unhandled_events: dict[int, UnhandledEventRecord] = {}

        # Pygame stuff.
        pygame.register_quit(self.quit_game)
        self.fps: float = options.get('target_fps', DEFAULT_TARGET_FPS)
        self.update_type: str = options.get('update_type', 'update')
        self.use_gfxdraw = options.get('use_gfxdraw')
        self.windowed = options.get('windowed')
        self.desired_resolution: Any = options.get('resolution')
        self.fps_log_interval_ms = options.get('fps_log_interval_ms')
        self.pygame_version = {'major': 0, 'minor': 0, 'patch': 0}

        self.pygame_version['major'] = pygame.version.vernum[0]
        self.pygame_version['minor'] = pygame.version.vernum[1]
        self.pygame_version['patch'] = pygame.version.vernum[2]

        # For compatibility with older versions of pygame, use fast events
        #
        # For versions >= 2.2, we can use the new event loop
        if pygame_needs_fastevents():
            GameEngine.USE_FASTEVENTS = True  # type: ignore[reportConstantRedefinition]

        # Ensure Linux/X11 sends DOWN on focus clicks
        os.environ.setdefault('SDL_MOUSE_FOCUS_CLICKTHROUGH', '1')

        # The engine alone owns the process's signals. By default SDL installs a C-level
        # SIGINT/SIGTERM handler at init (wherever the signal is still SIG_DFL) that turns the
        # signal into a QUIT event, which signal.getsignal cannot see (it still reports
        # SIG_DFL): SIGTERM would end the run as a normal quit, exit SUCCESS and be recorded as
        # an external QUIT. A value set beforehand wins. SDL_HINT_NO_SIGNAL_HANDLERS:
        # https://wiki.libsdl.org/SDL2/SDL_HINT_NO_SIGNAL_HANDLERS
        if pygame.get_init():
            self.log.warning(
                'pygame was initialized before the engine, so SDL may own SIGINT and SIGTERM '
                '(turning them into QUIT events); the engine still installs its own handlers '
                "when it starts, which replace SDL's"
            )
        os.environ.setdefault('SDL_NO_SIGNAL_HANDLERS', '1')

        # Shorten the GIL switch interval before audio starts: the mixer's channel-finished
        # callback needs the GIL to queue the next live-voice chunk (BUGS.md #27).
        sys.setswitchinterval(GIL_SWITCH_INTERVAL_SECONDS)
        self.log.debug('GIL switch interval set to %s seconds', GIL_SWITCH_INTERVAL_SECONDS)

        # Initialize all of the Pygame modules.
        self.init_pass, self.init_fail = pygame.init()
        self.print_game_info()

        # Enable fast events for multithreaded applications on older
        # versions of pygame, or use the new event loop for newer
        # versions of pygame >= 2.2
        if self.USE_FASTEVENTS and hasattr(pygame, 'fastevent'):
            self.log.info('Using pygame.fastevents for pygame version %s', pygame.version.ver)
            pygame.fastevent.init()  # type: ignore[attr-defined]
        else:
            # This is the default mode when USE_FASTEVENTS is disabled.
            #
            # pygame.event doesn't have an init() method, so nothing to do.
            self.log.info('Using pygame.events for pygame version %s', pygame.version.ver)

        # Fresh doors for this run (glitchygames/sources.py): the replay's when --replay-trace
        # is given, else live ones
        reset_sources()
        # reset_sources() leaves the polled input alone (glitchygames/sources.py is a leaf)
        reset_current_input()
        # ...and the internal-post tracker (glitchygames/recording.py): no owners, none pending.
        # Then the engine owns it for the whole run, so every code-posted event's origin is
        # known whenever it is needed (an instant-replay journal begun mid-run, a recording
        # started late); _pump_events forgets the posts after each pump
        reset_internal_post_tracking()
        start_tracking_internal_posts()
        # A live run is hosted: the outer game (glitchygames/host.py) reads through the live
        # doors and drives the frames. A replay has no host (its viewer is its outer game)
        self.host: GameHost | None = None
        if self.replay_sources is None:
            self.host = GameHost(
                sources=HostSources(
                    inner=LiveSources(
                        random_seed=self.random_seed,
                        use_fastevents=GameEngine.USE_FASTEVENTS,
                        # A recorded run captures scene starts from its first scene on, which
                        # is built before recording starts (glitchygames/scene_start.py)
                        captures_scene_starts=options.get('record_trace') is not None,
                    )
                )
            )
            install_sources(sources=self.host.sources)
        else:
            install_sources(sources=self.replay_sources)

        # We are fully initialized now, so we can set up the scene.
        #
        # The scene will start once .start() is called on the GameEngine
        # object
        GameEngine.game = game

        # SceneManager is a singleton.
        self.scene_manager: SceneManager = SceneManager()
        # A watched replay's F3/F4 (and its pause at a divergence) act on the scene manager's
        # debug overlay, the one drawn (glitchygames/replay/controls.py)
        if self.replay_sources is not None:
            # With the panel a restarted replay's viewer had chosen (ReplayOptions.viewer_state)
            self.scene_manager.debug_overlay.panel = (
                self.replay_sources.controls.debug_overlay.panel
            )
            self.replay_sources.controls.debug_overlay = self.scene_manager.debug_overlay
        # The singleton outlives an earlier engine in this process: this run starts fresh (its
        # frames numbered from 0, as reset_sources() above restarted the frame clock, and no
        # supervision, quit request, shake or playback state left from an earlier run)
        self.scene_manager.begin_run()
        # A watched replay pauses at each recorded breakpoint, such as a saved bookmark (rule 16
        # of glitchygames/replay/driver.py); nobody could unpause a headless one
        if self.replay_sources is not None and not self.replay_sources.options.headless:
            self.scene_manager.add_control_event_handler(
                kind=BREAKPOINT_KIND, handler=self.replay_sources.controls.pause_at_breakpoint
            )

        # Update the scene manager's update_type from the engine's options
        self.scene_manager.update_type = self.update_type

        # Resolution initialization.
        # Convert our resolution to a tuple
        resolution_parts: list[str] = str(self.desired_resolution).split('x')
        desired_width: str = resolution_parts[0]
        desired_height: str = resolution_parts[1]

        if self.windowed:
            self.mode_flags: int = pygame.DOUBLEBUF | pygame.SCALED | pygame.RESIZABLE
        else:
            self.mode_flags = (
                pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.SCALED | pygame.RESIZABLE
            )

        self.desired_resolution = self.suggested_resolution(
            int(desired_width),
            int(desired_height),
        )

        # window icon and system tray/dock icon
        self.initialize_system_icons()

        # Initialize display
        self.initialize_display()
        # A replay's window opened at the recorded size (start_replay asked for it), or the
        # replay is refused: the game would be set up on another size (rule 1 of
        # glitchygames/replay/driver.py)
        self._refuse_a_replay_display_of_another_size(options=options)

        self.initialize_event_handlers()

        self.print_system_info()

        # Declare instance variables that are initialized later by _initialize_event_managers()
        # (called from start()) and by start() itself. Declaring them here satisfies
        # basedpyright's reportUninitializedInstanceVariable check.
        self.registered_events: dict[int, Callable[..., Any]] = {}
        self.app_manager: AppEventManager
        self.audio_manager: AudioEventManager
        self.live_voice_channels: tuple[int, ...] = ()
        self.drop_manager: DropEventManager
        self.controller_manager: ControllerEventManager | None = None
        self.touch_manager: TouchEventManager
        self.font_manager: FontManager
        self.game_manager: GameEventManager
        self.joystick_manager: JoystickEventManager
        self.keyboard_manager: KeyboardEventManager
        self.midi_manager: MidiEventManager
        self.mouse_manager: MouseEventManager
        self.window_manager: WindowEventManager
        # Every joystick and game controller the game sees (glitchygames/input/input_devices.py),
        # following the joystick and controller managers; built with them
        self.input_devices: InputDevices = InputDevices()

    def initialize_display(self: Self) -> None:
        """Initialize the display."""
        # Let's try to set a resolution to the most compatible for
        # the system.  If we don't provide any parameters, we'll get
        # a reasonble default, but you should consider whether that's
        # a good idea for your particular application.
        #
        # There are various caveats for hardware accelerated blitting
        # that make it undesirable in a lot of cases, so we'll just use
        # software.
        self.display_info = pygame.display.Info()
        self.initial_resolution: tuple[int, int] = (
            self.display_info.current_w,
            self.display_info.current_h,
        )

        self.cursor: list[str] = self.set_cursor(cursor=None)

        # Set the screen update type.
        if self.scene_manager.update_type == 'update':
            self.display_update = pygame.display.update
        elif self.scene_manager.update_type == 'flip':
            self.display_update = pygame.display.flip
        else:
            self.log.error('Screen update type was neither "update" nor "flip".')

        # The Pygame documentation recommends against using hardware accelerated blitting.
        #
        # Note that you can also get the screen with pygame.display.get_surface()
        #
        # An existing window (a test's, or one a game opened first) may take its new size
        # only after set_mode returns (x11): the game is set up on the size it really has
        self.screen: pygame.Surface = set_display_mode(
            size=self.desired_resolution,
            flags=self.mode_flags,
        )
        # A new display is black, which cannot be told from "nothing rendered": until the
        # first scene draws, it shows the default background (glitchygames/backgrounds.py)
        paint_default_background(surface=self.screen)
        # A scene manager made before this display (pygame started first) holds the surface
        # of the display it saw then, which a --headless restart closed: it draws on this one
        self.scene_manager.screen = self.screen

    def initialize_event_handlers(self: Self) -> None:
        """Initialize event handlers.

        The engine calls this on your behalf.

        Event subsystem bootstrapping

        This gives us much faster event processing than
        doing a lookup every time an event comes in since
        we can just call the processing function directly.

        It's not as fast as a raw pygame event loop,
        but since we layer richer event types on top of
        the pygame raw events, this gives us a nice balance
        of extensibility with performance.

        """
        for event_type in events.AUDIO_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_audio_event

        for event_type in events.APP_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_app_event

        for event_type in events.MIDI_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_midi_event

        for event_type in events.WINDOW_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_window_event

        for event_type in events.GAME_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_game_event

        self.initialize_input_event_handlers()

        # Enable all events, except the window system's raw messages (SYSWMEVENT) unless the
        # game declares NATIVE_WINDOW_MESSAGES = True.
        # Note that glitchygames will auto-suppress events not handled
        # by the game once they are encountered, so it is recommended to enable all.
        events.allow_every_event_type(
            native_window_messages=self.native_window_messages(game=self.game)
        )

    @staticmethod
    def native_window_messages(*, game: type[Scene] | Scene) -> bool:
        """Read whether the game asks for the window system's raw messages (SYSWMEVENT).

        Args:
            game: The game scene class or instance, which may declare NATIVE_WINDOW_MESSAGES.

        Returns:
            bool: The game's NATIVE_WINDOW_MESSAGES (False when it declares none).

        Raises:
            TypeError: If the game's NATIVE_WINDOW_MESSAGES is not a bool.

        """
        # Looked up by name: a game need not be a Scene subclass
        native_window_messages = getattr(game, 'NATIVE_WINDOW_MESSAGES', False)
        if not isinstance(native_window_messages, bool):
            scene_class = game if isinstance(game, type) else type(game)
            message = (
                f'{scene_class.__name__}.NATIVE_WINDOW_MESSAGES must be a bool, '
                f'got {native_window_messages!r}'
            )
            raise TypeError(message)
        return native_window_messages

    def initialize_input_event_handlers(self: Self) -> None:
        """Initialize input event handlers.

        The engine calls this on your behalf.

        This initializes the input event handlers.

        """
        for event_type in events.CONTROLLER_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_controller_event

        for event_type in events.DROP_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_drop_event

        for event_type in events.TOUCH_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_touch_event

        for event_type in events.JOYSTICK_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_joystick_event

        for event_type in events.KEYBOARD_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_keyboard_event

        for event_type in events.MOUSE_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_mouse_event

        for event_type in events.TEXT_EVENTS:
            GameEngine.EVENT_HANDLERS[event_type] = self.process_text_event

    @property
    def input(self: Self) -> InputSnapshot:
        """The polled input captured at the latest pump (glitchygames/input/state.py).

        Read in ``dt_tick``, which runs before the frame's pump, it is the previous frame's
        snapshot; see ``current_input``.

        Returns:
            The snapshot.

        """
        return current_input()

    @property
    def screen_width(self: Self) -> int:
        """The screen width.

        Returns:
            int: The screen width.

        """
        return self.screen.get_width()

    @property
    def screen_height(self: Self) -> int:
        """The screen height.

        Returns:
            int: The screen height.

        """
        return self.screen.get_height()

    def print_system_info(self: Self) -> None:
        """Print system information."""
        # General Info
        self.log.info('Pygame Version: %s', pygame.version.ver)
        self.log.info('CPU Count: %s', multiprocessing.cpu_count())
        self.log.info('System: %s', platform.system())
        self.log.info('Machine: %s', platform.machine())
        self.log.info('Platform: %s', platform.platform())
        self.log.info('Platform (Terse): %s', platform.platform(aliased=False, terse=True))
        self.log.info('Processor: %s', platform.processor())
        self.log.info('Release: %s', platform.release())

        # Set up a display mode.
        # Note: pygame.display.init() isn't necessary here
        # because we've already called pygame.init() which
        # initializes all available modules.
        #
        # Let's do a sanity check and make sure we're initialized.
        self.log.info('Display inited: %s', pygame.display.get_init())

        # Display some configuration information.
        self.log.info('SDL Version: %s', pygame.get_sdl_version())
        self.log.info('SDL Byte Order: %s', pygame.get_sdl_byteorder())

        # Dump a bit more info about the configured mode.
        self.log.info('Display Driver: %s', pygame.display.get_driver())
        # Formatted here, not by logging: LogRecord checks isinstance(args[0], Mapping), and
        # pygame-ce's VidInfo raises AttributeError for __class__, which CPython 3.14.2
        # (Pyodide 314's) lets through isinstance (fixed in the pygame-ce fork; see
        # plans/2026-10-23-game-host-and-browser-runner.md)
        self.log.info('Display Info: %s', str(self.display_info))  # ruff: ignore[logging-eager-conversion] - VidInfo breaks LogRecord's isinstance (above)
        self.log.info('Initial Resolution: %s', self.initial_resolution)
        self.log.info('8-bit Modes: %s', pygame.display.list_modes(8))
        self.log.info('16-bit Modes: %s', pygame.display.list_modes(16))
        self.log.info('24-bit Modes: %s', pygame.display.list_modes(24))
        self.log.info('32-bit Modes: %s', pygame.display.list_modes(32))
        self.log.info(
            'Best Color Depth: %s (%s)',
            (pygame.display.mode_ok(self.initial_resolution), self.mode_flags),
            self.mode_flags,
        )
        self.log.info('Window Manager Info: %s', pygame.display.get_wm_info())
        self.log.info('Platform Timer Resolution: %s', pygame.TIMER_RESOLUTION)

    def print_game_info(self: Self) -> None:
        """Print game information."""
        self.log.debug(
            'Successfully loaded %s modules and failed loading %s modules.',
            self.init_pass,
            self.init_fail,
        )

        self.log.info('Game Title: %s', type(self).NAME)
        self.log.info('Game Version: %s', type(self).VERSION)

    def suggested_resolution(
        self: Self,
        desired_width: int = 0,
        desired_height: int = 0,
    ) -> tuple[int, int]:
        """Suggest a resolution.

        Args:
            desired_width (int): The desired width.
            desired_height (int): The desired height.

        Returns:
            tuple[int, int]: The suggested resolution.

        """
        # For Ubuntu 19.04, we can't reset the original res
        # so let's just let the system figure it out.
        if platform.system() == 'Linux':
            if 'arm' not in platform.machine():
                self.log.info('Ignoring full screen resolution change on Linux.')
            else:
                # RPi Hack
                #
                # The Raspberry Pi screen exposes
                # 2 resolutions, but only one works properly
                desired_width = 800
                desired_height = 480

        return (int(desired_width), int(desired_height))

    @classmethod
    def set_cursor(
        cls,
        cursor: list[str] | None,
        cursor_black: str = '.',
        cursor_white: str = 'X',
        cursor_xor: str = 'o',
    ) -> list[str]:
        """Set the cursor.

        Args:
            cursor (list[str]): The cursor.
            cursor_black (str): The black cursor.
            cursor_white (str): The white cursor.
            cursor_xor (str): The xor cursor.

        Returns:
            list[str]: The cursor.

        """
        if not cursor:
            # Cursor setup.
            # Cursor width/height must be a multiple of 8
            cursor = [
                'XX                      ',
                'XXX                     ',
                'XXXX                    ',
                'XX.XX                   ',
                'XX..XX                  ',
                'XX...XX                 ',
                'XX....XX                ',
                'XX.....XX               ',
                'XX......XX              ',
                'XX.......XX             ',
                'XX........XX            ',
                'XX........XXX           ',
                'XX......XXXXX           ',
                'XX.XXX..XX              ',
                'XXXX XX..XX             ',
                'XX   XX..XX             ',
                '     XX..XX             ',
                '      XX..XX            ',
                '      XX..XX            ',
                '       XXXX             ',
                '       XX               ',
                '                        ',
                '                        ',
                '                        ',
            ]

        cursor_width: int = len(cursor[0])
        cursor_height: int = len(cursor)

        # Compile our cursor so we can draw it to the screen.
        cursor_data, cursor_mask = pygame.cursors.compile(
            cursor,
            black=cursor_black,
            white=cursor_white,
            xor=cursor_xor,
        )

        # Now set the cursor as the active cursor.
        pygame.mouse.set_cursor((cursor_width, cursor_height), (0, 0), cursor_data, cursor_mask)

        return cursor

    def initialize_system_icons(self: Self) -> None:
        """Initialize system icons."""
        # Set the window icon.
        #
        # Always call this before you call set_mode()

        # Looked up by name: icon is optional on a game (Scene does not declare it)
        icon_attr: pygame.Surface | None = getattr(self.game, 'icon', GameEngine.icon)

        if icon_attr is None:
            icon_attr = pygame.Surface((32, 32))
            icon_attr.fill(PURPLE)

        icon: pygame.Surface = icon_attr

        pygame.display.set_icon(icon)

        # Set the display caption.
        pygame.display.set_caption(
            f'{type(self).NAME} v{self.VERSION}',
            f'{type(self).NAME} v{self.VERSION}',
        )

        # Get captions:
        (title, icontitle) = pygame.display.get_caption()
        self.log.info('Window Title: %s', title)
        self.log.info('Icon Title: %s', icontitle)

    def _initialize_event_managers(self: Self) -> None:
        """Initialize all event managers for the game engine."""
        self.registered_events = {}
        # The managers are shared instances (ResourceManager): this run builds its own, opening
        # devices through its own doors, instead of getting an earlier run's in this process
        events.ResourceManager.release_shared_instances()
        from glitchygames.events.app import AppEventManager

        self.app_manager = AppEventManager(game=self.scene_manager)
        self.audio_manager = AudioEventManager(game=self.scene_manager)

        # Reserve live synth voice channels now, before anything can play (see audio/live.py)
        from glitchygames.audio.live import reserve_live_voice_pool

        self.live_voice_channels = reserve_live_voice_pool(
            int(GameEngine.OPTIONS.get('live_voice_pool', DEFAULT_LIVE_VOICE_POOL))
        )

        self.drop_manager = DropEventManager(game=self.scene_manager)

        # Which devices and events the game sees (glitchygames/input/input_devices.py, rule 2):
        # auto (the default) both layers, a mapped pad dispatching its controller events and
        # any other device its joystick events; joystick the joystick layer only; controller
        # mapped pads only. Joystick events are never blocked at SDL: blocking them interferes
        # with CONTROLLERDEVICEADDED/REMOVED on macOS (they are dropped at dispatch instead)
        input_mode = InputMode(GameEngine.OPTIONS.get('input_mode', InputMode.AUTO))

        if input_mode is InputMode.JOYSTICK:
            self.controller_manager = None
            pygame.event.set_blocked(events.CONTROLLER_EVENTS)
            LOG.info('Input mode: joystick (controller events blocked)')
        else:
            self.controller_manager = ControllerEventManager(game=self.scene_manager)
            LOG.info('Input mode: %s (SDL Game Controller API)', input_mode)

        self.touch_manager = TouchEventManager(game=self.scene_manager)
        # https://glitchy-games.atlassian.net/browse/GG-23
        self.font_manager = FontManager(game=self.scene_manager)
        self.game_manager = GameEventManager(game=self.scene_manager)
        self.joystick_manager = JoystickEventManager(game=self.scene_manager)
        self.keyboard_manager = KeyboardEventManager(game=self.scene_manager)
        self.midi_manager = MidiEventManager(game=self.scene_manager)
        self.mouse_manager = MouseEventManager(game=self.scene_manager)
        self.window_manager = WindowEventManager(game=self.scene_manager)

        # The devices the managers just opened (no scene is running yet to be told)
        self.input_devices = InputDevices(input_mode=input_mode)
        self._synchronize_input_devices()

    def _synchronize_input_devices(self: Self) -> None:
        """Follow the managers' devices, telling the active scene which came and went.

        Called once the managers are made and after every device event they handle
        (glitchygames/input/input_devices.py, rule 3).
        """
        controller_manager = self.controller_manager
        changes = self.input_devices.synchronize(
            joysticks={
                proxy.instance_id: proxy.joystick
                for proxy in self.joystick_manager.joysticks.values()
            },
            controllers=(
                {}
                if controller_manager is None
                else {
                    proxy.instance_id: proxy.controller
                    for proxy in controller_manager.controllers.values()
                }
            ),
        )
        for device in changes.removed:
            self.scene_manager.on_input_device_removed(device=device)
        for device in changes.added:
            self.scene_manager.on_input_device_added(device=device)

    def _resolve_scene_name_for_error(self: Self) -> str:
        """Resolve the current or previous scene name for error reporting.

        Returns:
            The scene name string for error messages.

        """
        # The scene that was running, else (none active: the run ended before a scene began,
        # or after the last one) the scene before it
        scene = self.scene_manager.active_scene
        if scene is None:
            scene = self.scene_manager.previous_scene
        if scene is None:
            return 'None'
        # A scene without a name (an empty NAME) is named by its class
        return scene.NAME or scene.__class__.__name__

    def measurement_run(
        self: Self, *, processing_paced: bool, rebaselined_from: str | None
    ) -> MeasurementRun:
        """Return this run's provenance for a recording's ``measurement_runs`` (newest first).

        Its ``measured_at`` is the real time now: provenance only, never replayed or served to
        the game (tests/test_engine_doors.py allows this read for that reason).

        Args:
            processing_paced: Whether the run paces its frames (a live run with a target FPS; a
                rebaseline, a headless replay, is not paced).
            rebaselined_from: The recording this run rebaselines, or None for a fresh recording.

        Returns:
            The run.

        """
        # Every run names its timer, paced or not: the one it has, or (a rebaseline names its run
        # while the engine starts, before any timer exists; a timer that failed to start) the
        # one its options make, uncalibrated
        pacing_timer = (
            pacing_timer_for_options(options=GameEngine.OPTIONS)
            if self.timer is None
            else self.timer.pacing_timer()
        )
        return MeasurementRun(
            machine=machine_description(),
            processing_paced=processing_paced,
            engine_version=installed_engine_version(),
            pygame_version=pygame.version.ver,
            python_version=platform.python_version(),
            measured_at=datetime.now(tz=UTC).isoformat(),
            rebaselined_from=rebaselined_from,
            hash_scheme=CONTENT_HASH_SCHEME,
            pacing_timer=pacing_timer,
            source_revision=engine_source_revision(),
            machine_state=current_machine_state(),
        )

    def trace_recording_header(self: Self) -> dict[str, Any]:
        """Build the header of a --record-trace recording.

        Returns:
            The game and scene class names, engine, pygame and Python versions, the screen
            size, every command-line option (JSON-safe), the start time and the random seed.

        """
        active_scene = self.scene_manager.active_scene
        engine_version = installed_engine_version()
        return {
            'game_class': type(self.game).__name__,
            # With the class name, tells apart two games whose classes share a name
            'game_module': type(self.game).__module__,
            'scene_class': None if active_scene is None else type(active_scene).__name__,
            'engine_version': engine_version,
            'pygame_version': pygame.version.ver,
            'python_version': platform.python_version(),
            'screen_size': [self.screen_width, self.screen_height],
            'options': {
                str(name): json_safe_value(value) for name, value in GameEngine.OPTIONS.items()
            },
            # The origin of the run's wall clock from here on, recorded and replayed alike:
            # recorded_at plus the frame clock (RecordingSources.wall_clock_time; rule 9 of
            # glitchygames/replay/driver.py), so game code reading it replays exactly
            RECORDED_AT_HEADER_FIELD: datetime.now(tz=UTC).isoformat(),
            'random_seed': self.random_seed,
            # Each run's provenance, newest first (glitchygames/recording_history.py): this one
            # paces its frames when it has a target FPS (0 is uncapped)
            MEASUREMENT_RUNS_HEADER_FIELD: [
                self.measurement_run(
                    processing_paced=self.scene_manager.target_fps > 0, rebaselined_from=None
                ).to_json()
            ],
        }

    def start_trace_recording(self: Self, *, path: Path) -> GameplayRecorder:
        """Start recording the session to a trace file (before the first frame).

        The header also holds what the run took in before recording started: a snapshot of
        every save store the doors opened (``saves``), the descriptors of devices opened
        (``devices``) and the enumeration answers given (``device_enumeration``). Then
        ``RecordingSources`` are installed around the active doors and record every frame
        from what passes through them (glitchygames/recording.py). SIGTERM (and SIGHUP on
        Unix, SIGBREAK on Windows) ends a started run through the normal teardown
        (``exit_on_signal``, installed by ``start``), and so does SIGINT (KeyboardInterrupt).
        ``stop_trace_recording`` (called by ``_shutdown``) closes the file.

        Recording must start before the first frame: afterwards installing its doors raises
        ``SourcesAlreadyRunningError`` (from ``install_sources``; glitchygames/sources.py).

        Args:
            path: The recording's file.

        Returns:
            The recorder.

        Raises:
            TraceRecordingAlreadyStartedError: If this engine is already recording.

        """
        if self.trace_recorder is not None:
            message = (
                f'start_trace_recording() was called while recording to '
                f'{self.trace_recorder.path}; one run records once'
            )
            raise TraceRecordingAlreadyStartedError(message)
        inner = active_sources()
        registry = inner.devices()
        # A store a run started with --record-trace opened before recording started is in the
        # header as first opened: the first scene's setup() may have written to it since, and
        # the replay runs that setup() again (LiveSources.first_open_save_snapshots, read
        # through the host's doors in a hosted run)
        first_open_snapshots: Mapping[str, dict[str, Any]] = (
            inner.first_open_save_snapshots if isinstance(inner, LiveSources | HostSources) else {}
        )
        # A rebaseline copies these fields from the replayed recording instead (rebaseline.py)
        header = {
            **self.trace_recording_header(),
            SAVES_HEADER_FIELD: {
                namespace: (
                    first_open_snapshots[namespace]
                    if namespace in first_open_snapshots
                    else save_namespace_snapshot(saves=store)
                )
                for namespace, store in inner.opened_save_namespaces.items()
            },
            DEVICES_HEADER_FIELD: [
                descriptor.to_json() for descriptor in registry.take_opened_descriptors()
            ],
            DEVICE_ENUMERATION_FIELD: [
                answer.to_json() for answer in registry.take_enumeration_answers()
            ],
        }
        recorder = GameplayRecorder(path=path, header=header)
        install_sources(sources=RecordingSources(inner=inner, recorder=recorder))
        self.trace_recorder = recorder
        self.log.info('Recording gameplay to %s (random seed %s)', path, self.random_seed)
        return recorder

    def _start_requested_trace_recording(self: Self) -> None:
        """Start recording if --record-trace or --rebaseline was given (off by default).

        A rebaseline records over the replay (glitchygames/replay/rebaseline.py), with the
        replayed recording's header; ``stop_trace_recording`` closes it like any recording.
        """
        if self.rebaseline is not None:
            self.trace_recorder = self.rebaseline.start_recording()
            return
        record_trace_path = GameEngine.OPTIONS.get('record_trace')
        if record_trace_path is not None:
            self.start_trace_recording(path=Path(record_trace_path))

    def stop_trace_recording(self: Self) -> None:
        """Close the recording, if one is running.

        The ``RecordingSources`` stay installed (the run is ending); with the recorder closed
        they only delegate.
        """
        recorder = self.trace_recorder
        if recorder is None:
            return
        self.trace_recorder = None
        recorder.close()
        if recorder.write_failed:
            self.recording_write_failed = True

    def _install_signal_handlers(self: Self) -> None:
        """Make each of terminating_signals() raise SystemExit, if nothing else handles it yet.

        Limitation: Python sets signal handlers from the main thread only. An engine started on
        another thread installs none, and SDL's own handler is off (SDL_NO_SIGNAL_HANDLERS), so
        SIGTERM (or SIGHUP, SIGBREAK) then kills the process the system's default way, without
        the teardown: a recording is left unclosed (it still reads up to its last full frame).
        """
        for signal_number in terminating_signals():
            try:
                # Limitation: a C-level handler (SDL's, when pygame was initialized before the
                # engine set SDL_NO_SIGNAL_HANDLERS) is invisible here, as getsignal still
                # reports SIG_DFL; installing then replaces it, which is what the engine wants
                if signal.getsignal(signal_number) == signal.SIG_DFL:
                    signal.signal(signal_number, exit_on_signal)
                    self._installed_signal_handlers.append(signal_number)
            except ValueError as signal_error:
                # Signal handlers can only be set from the main thread
                self.log.debug('Signal %d handler not installed: %s', signal_number, signal_error)

    def _restore_signal_handlers(self: Self) -> None:
        """Put back the default handling of each signal _install_signal_handlers claimed."""
        installed, self._installed_signal_handlers = self._installed_signal_handlers, []
        for signal_number in installed:
            signal.signal(signal_number, signal.SIG_DFL)

    @contextlib.contextmanager
    def _waiting_for_child_processes(self: Self) -> Generator[None]:
        """Install the engine's signal handlers while this process waits for child processes.

        The one way the engine waits for children (``--audit``'s replays, which run in
        ``__init__`` before ``start`` installs the handlers; a watched replay's restarts, after
        ``_shutdown`` restored them): a SIGTERM (or SIGHUP, SIGBREAK) raises SystemExit
        (``exit_on_signal``), so ``subprocess.run`` kills and reaps the child instead of leaving
        it running, and this process exits with the signal's ``ExitCode``. The default handling
        comes back afterwards.

        Yields:
            Nothing: the wait runs inside.

        """
        self._install_signal_handlers()
        try:
            yield
        finally:
            self._restore_signal_handlers()

    def _start_requested_replay(
        self: Self, *, game: type[Scene] | Scene, options: dict[str, Any]
    ) -> ReplaySources | None:
        """Prepare the replay if --replay-trace was given (rule 1 of glitchygames/replay/driver.py).

        With --audit the recording is audited instead (glitchygames/replay/audit.py), once it is
        known to be replayable, and the process exits with the audit's outcome
        (``_audit_replay``).

        Refusals exit (``exit_with``) with ``ExitCode.UNUSABLE_INPUT`` when the recording cannot
        be replayed (a recording of another game, an unsupported format version, an unreadable
        file), ``ExitCode.MISSING_INPUT`` when it does not exist, and
        ``ExitCode.OPTIONS_REFUSED`` when --record-trace is given too (recording over a replay
        is --rebaseline's job), --rebaseline's options are unsound (``rebaseline_refusal``) or
        it or --audit is given without --replay-trace, or --audit with --replay-fps real or
        to an interpreter started with -E or -I. Auditing a truncated recording exits with
        ``ExitCode.UNUSABLE_INPUT`` too (an audit needs the whole recording).

        Args:
            game: The game scene class or instance (its class name must match the recording's).
            options: The parsed options; a replay puts the recorded ones in place.

        Returns:
            The replay's sources (not installed yet), or None when not replaying.

        """
        self._refuse_listing_input_devices_during_a_run(options=options)
        self._refuse_a_forced_power_on_during_a_run(options=options)
        replay_trace_path = options.get('replay_trace')
        if replay_trace_path is None:
            self._check_replay_options_without_a_recording(options=options)
            self._refuse_unwritable_outputs(options=options)
            return None
        self._refuse_an_unsound_recording_over_the_replay(
            replay_trace_path=replay_trace_path, options=options
        )
        self._refuse_an_unsound_processing_comparison(
            replay_trace_path=replay_trace_path, options=options
        )
        if options.get('audit'):
            self._refuse_an_unsound_audit(replay_trace_path=replay_trace_path, options=options)
        game_class = game if isinstance(game, type) else type(game)
        try:
            sources = start_replay(
                path=Path(replay_trace_path),
                game_class_name=game_class.__name__,
                game_module=game_class.__module__,
                options=options,
                # Set by the version check this __init__ runs later, so pygame's version is
                # asked here too
                use_fastevents=GameEngine.USE_FASTEVENTS or pygame_needs_fastevents(),
            )
        except (ReplayRefusedError, TraceFormatError, OSError) as error:
            refusal = error
        else:
            if options.get('audit'):
                self._refuse_auditing_a_truncated_recording(
                    replay_trace_path=replay_trace_path, sources=sources
                )
                self._audit_replay(path=Path(replay_trace_path))
            self._refuse_unwritable_outputs(options=options)
            announce_replay(path=Path(replay_trace_path), sources=sources)
            return sources
        # Logged without a traceback: the message says what is wrong with the recording
        self.log.error('Cannot replay %s: %s', replay_trace_path, refusal)
        # Only a file that does not exist is missing input; one that cannot be read (no
        # permission, a directory, not gzip: gzip.BadGzipFile is an OSError) is unusable
        exit_with(
            exit_code=(
                ExitCode.MISSING_INPUT
                if isinstance(refusal, FileNotFoundError)
                else ExitCode.UNUSABLE_INPUT
            ),
            cause=refusal,
        )

    def _refuse_a_replay_display_of_another_size(self: Self, *, options: dict[str, Any]) -> None:
        """Exit with ExitCode.UNUSABLE_INPUT if the replay's window has another size than recorded.

        The replay asked for the recorded ``screen_size`` (``start_replay``); a window manager
        that gave the window another size would set the game up on it, and the replay would
        diverge from its first frame.

        Args:
            options: The parsed options (``replay_trace`` names the recording).

        """
        if self.replay_sources is None:
            return
        refusal = display_size_refusal(
            header=self.replay_sources.header, display_size=self.screen.get_size()
        )
        if refusal is None:
            return
        self.log.error('Cannot replay %s: %s', options['replay_trace'], refusal)
        exit_with(exit_code=ExitCode.UNUSABLE_INPUT)

    def _check_replay_options_without_a_recording(self: Self, *, options: dict[str, Any]) -> None:
        """Refuse --audit and --rebaseline without --replay-trace; warn about ignored options.

        Exits (``exit_with``) with ``ExitCode.OPTIONS_REFUSED`` for --audit or --rebaseline;
        --replay-fps, --replay-digest and --replay-pause-at-frame are only warned about.

        Args:
            options: The parsed options (no ``replay_trace``).

        """
        if options.get('audit'):
            self.log.error('--audit needs --replay-trace PATH: the recording to audit')
            exit_with(exit_code=ExitCode.OPTIONS_REFUSED)
        if options.get('rebaseline') is not None:
            self.log.error('--rebaseline needs --replay-trace OLD: the recording to rebaseline')
            exit_with(exit_code=ExitCode.OPTIONS_REFUSED)
        for option_name, flag in (
            ('replay_fps', '--replay-fps'),
            ('replay_digest', '--replay-digest'),
            ('replay_pause_at_frame', '--replay-pause-at-frame'),
            ('compare_processing', '--compare-processing'),
            ('max_processing_slowdown', '--max-processing-slowdown'),
        ):
            if options.get(option_name) is not None:
                self.log.warning('%s is ignored without --replay-trace', flag)

    def _refuse_unwritable_outputs(self: Self, *, options: dict[str, Any]) -> None:
        """Exit with ExitCode.CANNOT_WRITE_OUTPUT if an output file of the run cannot be written.

        Checked before any game code runs (``glitchygames.output_files.output_refusal``):
        ``--record-trace``'s recording, ``--rebaseline``'s partial file (NEW itself is only
        moved into place at the end: glitchygames/replay/rebaseline.py, rule 4) and
        ``--replay-digest``'s digest file. The refusal is logged on one line, without a
        traceback.

        Args:
            options: The parsed options (a recording over a replay already refused).

        """
        outputs: list[tuple[str, Path]] = []
        record_trace_path = options.get('record_trace')
        if record_trace_path is not None:
            outputs.append(('--record-trace', Path(record_trace_path)))
        rebaseline_path = options.get('rebaseline')
        if rebaseline_path is not None:
            outputs.append(('--rebaseline', partial_path(destination=Path(rebaseline_path))))
        replay_digest_path = options.get('replay_digest')
        if replay_digest_path is not None:
            outputs.append(('--replay-digest', Path(replay_digest_path)))
        for flag, path in outputs:
            refusal_reason = output_refusal(path=path)
            if refusal_reason is not None:
                self.log.error('Cannot write %s: %s', flag, refusal_reason)
                exit_with(exit_code=ExitCode.CANNOT_WRITE_OUTPUT)

    def _refuse_a_forced_power_on_during_a_run(self: Self, *, options: dict[str, Any]) -> None:
        """Exit with ExitCode.OPTIONS_REFUSED for --crt-power-on on with a replay or recording.

        Nothing may happen before frame 0 of a recorded or replayed run: events pumped then would
        be input the game never saw (glitchygames/crt_power_on.py).

        Args:
            options: The parsed options.

        """
        if options.get('crt_power_on') != CrtPowerOnMode.ON.value:
            return
        for flag, option_name in (
            ('--replay-trace', 'replay_trace'),
            ('--record-trace', 'record_trace'),
        ):
            if options.get(option_name) is not None:
                self.log.error('Cannot play the CRT power-on sequence with %s', flag)
                exit_with(exit_code=ExitCode.OPTIONS_REFUSED)

    def _refuse_listing_input_devices_during_a_run(self: Self, *, options: dict[str, Any]) -> None:
        """Exit with ExitCode.OPTIONS_REFUSED for --list-input-devices with a replay or recording.

        The listing replaces the game's run (glitchygames/input/device_listing.py): there is no
        run to replay, audit, rebaseline or record.

        Args:
            options: The parsed options.

        """
        if not options.get('list_input_devices'):
            return
        for flag, option_name in (
            ('--replay-trace', 'replay_trace'),
            ('--record-trace', 'record_trace'),
        ):
            if options.get(option_name) is not None:
                self.log.error(
                    'Cannot list input devices with %s: the listing replaces the run', flag
                )
                exit_with(exit_code=ExitCode.OPTIONS_REFUSED)

    def _refuse_an_unsound_recording_over_the_replay(
        self: Self, *, replay_trace_path: str, options: dict[str, Any]
    ) -> None:
        """Exit with ExitCode.OPTIONS_REFUSED for a recording over the replay that cannot run.

        That is --rebaseline with unsound options (``rebaseline_refusal``), or --record-trace:
        a recording over a replay takes the replay's event origins and recorded fields, which
        only --rebaseline (headless, never stopping at a divergence) wires.

        Args:
            replay_trace_path: The recording to replay.
            options: The parsed options.

        """
        if options.get('rebaseline') is not None:
            refusal_reason = rebaseline_refusal(options=options)
            if refusal_reason is not None:
                self.log.error('Cannot rebaseline %s: %s', replay_trace_path, refusal_reason)
                exit_with(exit_code=ExitCode.OPTIONS_REFUSED)
        elif options.get('record_trace') is not None:
            self.log.error(
                'Cannot replay %s with --record-trace: record over a replay '
                'with --rebaseline NEW --headless',
                replay_trace_path,
            )
            exit_with(exit_code=ExitCode.OPTIONS_REFUSED)

    def _refuse_an_unsound_processing_comparison(
        self: Self, *, replay_trace_path: str, options: dict[str, Any]
    ) -> None:
        """Exit with ExitCode.OPTIONS_REFUSED if processing times could not be compared.

        A comparison (``--compare-processing``, or ``--max-processing-slowdown``, which implies
        it) needs a headless replay (a watched one presents, steps and rebuilds frames as its
        viewer asks), and is refused with --audit (its children's exit codes are the audit's
        verdict) and --rebaseline (which exits on what it wrote; its NEW records this run's
        processing times anyway). glitchygames/replay/processing.py.

        Args:
            replay_trace_path: The recording to replay.
            options: The parsed options.

        """
        if (
            options.get('compare_processing') is None
            and options.get('max_processing_slowdown') is None
        ):
            return
        if not options.get('headless'):
            reason = '--compare-processing needs --headless'
        elif options.get('audit'):
            reason = 'not with --audit'
        elif options.get('rebaseline') is not None:
            reason = 'not with --rebaseline'
        else:
            return
        self.log.error('Cannot compare the processing times of %s: %s', replay_trace_path, reason)
        exit_with(exit_code=ExitCode.OPTIONS_REFUSED)

    def _refuse_an_unsound_audit(
        self: Self, *, replay_trace_path: str, options: dict[str, Any]
    ) -> None:
        """Exit with ExitCode.OPTIONS_REFUSED if an audit's two runs could not be compared.

        That is under --replay-fps real (FPS events from measured frame times differ between the
        runs), or when Python was started with -E or -I (the children run this interpreter's
        options again, so they would ignore PYTHONHASHSEED).

        Args:
            replay_trace_path: The recording to audit.
            options: The parsed options.

        """
        if options.get('replay_fps') == REAL_REPLAY_FPS:
            self.log.error(
                'Cannot audit %s with --replay-fps %s: --audit compares recorded FPS events',
                replay_trace_path,
                REAL_REPLAY_FPS,
            )
            exit_with(exit_code=ExitCode.OPTIONS_REFUSED)
        if not environment_reaches_children():
            self.log.error(
                'Cannot audit %s: Python was started with -E or -I, so the '
                'audit replays would ignore their PYTHONHASHSEED; run without those options',
                replay_trace_path,
            )
            exit_with(exit_code=ExitCode.OPTIONS_REFUSED)

    def _refuse_auditing_a_truncated_recording(
        self: Self, *, replay_trace_path: str, sources: ReplaySources
    ) -> None:
        """Exit with ExitCode.UNUSABLE_INPUT if the recording to audit is truncated.

        An audit needs the whole recording: its child replays would end at the cut-off (exit
        ``ExitCode.UNUSABLE_INPUT``), which the audit could only report as a run that did not
        finish.

        Args:
            replay_trace_path: The recording to audit.
            sources: Its replay sources (read, not installed).

        """
        if sources.recording.is_truncated:
            self.log.error(
                'Cannot audit %s: the recording is truncated after '
                '%s complete frames, and an audit needs the whole '
                'recording',
                replay_trace_path,
                sources.recording.frame_count,
            )
            exit_with(exit_code=ExitCode.UNUSABLE_INPUT)

    def _audit_replay(self: Self, *, path: Path) -> NoReturn:
        """Audit the recording in two child replays and exit with the outcome (--audit).

        It exits (``exit_with``) with ``ExitCode.SUCCESS`` when the audit passes,
        ``ExitCode.AUDIT_NONDETERMINISTIC`` when it fails and ``ExitCode.INTERNAL_ERROR`` when
        it could not run (``AuditRunError``: a child that could not start, hung, crashed or
        wrote no digests).

        Args:
            path: The recording.

        """
        self.log.info('Auditing %s: two replays in fresh processes', path)
        try:
            with self._waiting_for_child_processes():
                result = audit_recording(
                    command=audit_command(original_argv=sys.orig_argv), path=path
                )
        except AuditRunError as error:
            run_error = error
        else:
            if result.is_deterministic():
                self.log.info(result.summary())
                exit_with(exit_code=ExitCode.SUCCESS)
            self.log.error(result.summary())
            exit_with(exit_code=ExitCode.AUDIT_NONDETERMINISTIC)
        # Logged without a traceback: the message says which run failed and how
        self.log.error('Audit could not run: %s', run_error)
        exit_with(exit_code=ExitCode.INTERNAL_ERROR, cause=run_error)

    def _report_replay_result(self: Self, *, run_ended_by: str | None) -> None:
        """Settle the replay's result and report it, if replaying (rule 11).

        The report (``ReplayResult.report``) is printed to stdout under ``--headless``, where it
        is the run's output, and logged otherwise (as an error when the replay diverged).

        Any early end of the run (a crash, Ctrl-C, a signal, or any SystemExit, a game's own
        ``sys.exit(0)`` included) is reported by what ended it: before the replay reached its
        result, only where the replay stopped (``Replay stopped at frame N: the run ended with
        ...``), since its result would call that a length divergence; after the replay reached
        its result (a late crash or signal, during the teardown of the last scene), that result
        and then ``then the run ended with ...`` on the next line.

        A rebaseline (glitchygames/replay/rebaseline.py) that ended normally writes its new
        recording and reports its summary instead; one that ended early writes nothing and
        says so after the report.

        Args:
            run_ended_by: What ended the run early (an exit status as
                ``ExitCode.describe_status`` gives it), or None when the run ended normally.

        """
        if self.replay_sources is None:
            return
        result = self.replay_sources.result
        # Read before finish_run, which turns a replay still running into a length divergence
        replay_had_ended = result.end_reason != RUNNING_END_REASON
        self.replay_sources.finish_run()
        if run_ended_by is not None and replay_had_ended:
            report = f'{result.report()}\nthen the run ended with {run_ended_by}'
            is_failure = True
        elif run_ended_by is not None:
            report = (
                f'Replay stopped at frame {result.frames_replayed}: the run ended with '
                f'{run_ended_by}'
            )
            is_failure = True
        else:
            report = result.report()
            is_failure = result.divergence is not None
        if self.rebaseline is not None:
            if run_ended_by is None:
                # The divergences are what the rebaseline reports, not a failure
                report = self.rebaseline.write(result=result)
                is_failure = False
            else:
                self.rebaseline.discard()
                report = f'{report}\n{self.rebaseline.destination} was not written'
        if result.processing is not None:
            # After the replay's own report (glitchygames/replay/processing.py)
            report = f'{report}\n{result.processing.describe()}'
        if self.replay_sources.options.headless:
            sys.stdout.write(f'{report}\n')
            sys.stdout.flush()
        elif is_failure:
            self.log.error(report)
        else:
            self.log.info(report)

    def _enter_headless_mode(self: Self) -> None:
        """--headless: run on SDL's dummy video and audio drivers (no window, no sound).

        Called right after the options are read, before ``pygame.init()`` and the display. If
        pygame was started before the engine (at import, by a game's own code), its display and
        mixer already run on the drivers chosen then, and each that is not on the dummy driver is
        restarted on it, with one warning naming what was restarted:

        - The display is stopped; ``pygame.init()`` starts it again and the engine opens its
          window on it, as it always does.
        - The mixer is stopped and started again at once with the same frequency, sample size
          and output channels (``pygame.mixer.get_init()``) and the same number of mixing
          channels. Anything playing stops; sounds loaded before keep the format they were
          converted to, which still matches. The buffer size cannot be read back, so it is
          pygame's default. If the dummy mixer cannot start, the run goes on without audio
          (logged).

        The variables' earlier values are kept and put back when the run ends
        (``_restore_sdl_driver_variables``), so a process that goes on after a headless run
        starts pygame on its own drivers again.
        """
        self._sdl_driver_variables_before_headless = {
            name: os.environ.get(name) for name in SDL_DRIVER_VARIABLES
        }
        for name in SDL_DRIVER_VARIABLES:
            os.environ[name] = HEADLESS_SDL_DRIVER
        restarted: list[str] = []
        if pygame.display.get_init() and pygame.display.get_driver() != HEADLESS_SDL_DRIVER:
            restarted.append(f'the display (video driver {pygame.display.get_driver()!r})')
            pygame.display.quit()
        mixer_format = pygame.mixer.get_init()
        if mixer_format is not None and pygame.mixer.get_driver() != HEADLESS_SDL_DRIVER:
            frequency, size, output_channels = mixer_format
            mixing_channel_count = pygame.mixer.get_num_channels()
            restarted.append(
                f'the mixer (audio driver {pygame.mixer.get_driver()!r}; kept: {frequency} Hz, '
                f'size {size}, {output_channels} output channels, {mixing_channel_count} '
                'mixing channels)'
            )
            pygame.mixer.quit()
            try:
                # The environment now names the dummy driver, so this opens the dummy device
                pygame.mixer.init(frequency=frequency, size=size, channels=output_channels)
            except pygame.error as error:
                # The run goes on without a mixer: sounds and live voices are silent no-ops
                self.log.warning(
                    '--headless: the mixer could not start on the dummy audio driver (%s); '
                    'running without audio',
                    error,
                )
            else:
                pygame.mixer.set_num_channels(mixing_channel_count)
        if restarted:
            self.log.warning(
                '--headless: pygame was started before the engine; restarting '
                '%s on the dummy driver, so there is no window and '
                'audio is muted',
                ' and '.join(restarted),
            )

    def _restore_sdl_driver_variables(self: Self) -> None:
        """Put back the SDL driver variables --headless set, as they were before it (idempotent).

        SDL reads them only when the display or mixer starts, so this changes nothing that is
        running: it is called after ``_shutdown`` quit pygame, so a process that goes on (runs a
        headless replay, then opens a window) starts pygame on its own drivers, not the dummy
        ones. A variable that was not set before is removed.
        """
        variables_before, self._sdl_driver_variables_before_headless = (
            self._sdl_driver_variables_before_headless,
            None,
        )
        if variables_before is None:
            return
        for name, value in variables_before.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def _shutdown(self: Self, *, run_ended_by: str | None = None) -> None:
        """Close any recording, report any replay, print performance reports, shut down pygame.

        Args:
            run_ended_by: What ended the run early (``_report_replay_result``), or None.

        """
        try:
            # First, so the recording is complete even if a report below fails
            self.stop_trace_recording()
        finally:
            # After closing: until then a repeated signal must stay ignored (exit_on_signal).
            # Even when closing failed, the replay is settled (its blocked input restored) and
            # reported; the closing error then propagates (the teardown failed)
            self._restore_signal_handlers()
            self._report_replay_result(run_ended_by=run_ended_by)
        # The run is over, a restart included (its process makes its own timer): give back what
        # the timer holds here, not in its finaliser, which must not log (BUGS.md #188)
        if self.timer is not None:
            self.timer.close()
        # A step back restarts the replay (glitchygames/replay/rebuild.py): not the end of the
        # run, so the end-of-run reports wait for the last replay
        if self.replay_sources is not None and self.replay_sources.result.restart_frame is not None:
            pygame.display.quit()
            pygame.quit()
            return

        # Print performance report before shutdown
        try:
            from glitchygames.performance import performance_manager
        except ImportError:
            pass  # Performance module not available
        else:
            # Configure performance manager with the same log interval as FPS
            if self.fps_log_interval_ms is not None:
                performance_manager.set_fps_log_interval(self.fps_log_interval_ms)
            # Configure performance manager with target FPS for grading
            performance_manager.set_target_fps(self.fps)
            performance_manager.print_shutdown_report()
            performance_manager.print_per_scene_shutdown_report()

        self._log_sprite_count_report()
        self._log_unhandled_event_report()

        pygame.display.quit()
        pygame.quit()

    def _configure_timer_and_performance(self: Self, *, paced_by_timer: bool) -> None:
        """Create the frame-pacing timer and configure the performance manager from the options.

        Each part is guarded on its own: a bad option falls back (the pygame clock, the
        performance defaults) and is logged at debug level, never ending the run.

        Args:
            paced_by_timer: Whether the run's frames wait on this timer (``start()``); False for
                ``start_async()``, whose outer tick is the wait. Only a timer that paces is
                calibrated; the timer is made either way (a recording names it).

        """
        # Initialize timer backend for draw-loop pacing (after options exist)
        try:
            self.timer = create_timer(
                GameEngine.OPTIONS.get('timer_backend'),
                GameEngine.OPTIONS,
            )
            self.log.info('Timer backend: %s', GameEngine.OPTIONS.get('timer_backend'))
            # auto measures this machine's sleep model now for a paced live game, so no frame
            # pays for it (and logs what it chose); a replay and an async run never pace with
            # the timer, and an uncapped run calibrates only if it starts pacing (at its first
            # paced frame)
            if (
                paced_by_timer
                and GameEngine.OPTIONS.get('target_fps', 0) > 0
                and self.replay_sources is None
            ):
                self.timer.calibrate()
        except (ValueError, TypeError, OSError) as timer_error:
            self.timer = None
            self.log.debug(
                'Timer backend failed to initialize; using pygame clock only: %s',
                timer_error,
            )
        # Configure performance trim percent and histogram mode, each guarded on its own so
        # a bad value for one cannot silently skip the other.
        try:
            from glitchygames.performance import performance_manager

            trim = float(GameEngine.OPTIONS.get('perf_trim_percent', 5.0))
            performance_manager.set_trim_percent(trim)
        except (ImportError, ValueError, TypeError, AttributeError) as perf_error:
            LOG.debug('Performance trim percent configuration failed: %s', perf_error)
        try:
            from glitchygames.performance import performance_manager

            performance_manager.set_histogram_mode(
                GameEngine.OPTIONS.get('fps_histogram', 'equal-range')
            )
        except (ImportError, ValueError, TypeError, AttributeError) as perf_error:
            LOG.debug('Performance FPS histogram mode configuration failed: %s', perf_error)

    def _tear_down_run(
        self: Self, *, profiler: cProfile.Profile | None, run_ended_by: str | None
    ) -> Exception | None:
        """Run the teardown after a run, whatever ended it, and report how it went.

        Args:
            profiler: The run's profiler (--profile), stopped and printed here, or None.
            run_ended_by: What ended the run early (an exit status described), or None when it
                ended normally.

        Returns:
            The exception ``_shutdown`` raised (logged with its traceback), or None.

        """
        teardown_error: Exception | None = None
        try:
            self._shutdown(run_ended_by=run_ended_by)
        except Exception as error:
            self.log.exception('The teardown failed')
            teardown_error = error
        finally:
            # Again (it is idempotent): _shutdown restores them, but not if it failed first
            self._restore_signal_handlers()
            # After _shutdown quit pygame: whatever starts it next does so on these drivers
            self._restore_sdl_driver_variables()
        if GameEngine.OPTIONS['profile'] and profiler is not None:
            profiler.disable()
            profiler.print_stats()
        return teardown_error

    def start(self: Self) -> None:
        """Start the game engine.

        However the run ends, the teardown (``_shutdown``: recordings closed) runs first; if the
        teardown itself raises, the run exits ``ExitCode.INTERNAL_ERROR`` (both errors logged).
        An exception raised before start(), in ``__init__``, is not mapped: it exits with
        Python's default 1 (each game has its own entry point, so there is no one place to wrap;
        see glitchygames/exit_codes.py). A replay (``--replay-trace``) that ends normally exits
        with its own code (``ReplayResult.exit_code`` under its exit policy), watched or
        headless.

        How it ends (``_begin_start`` and ``_crash_boundary`` raise these): RuntimeError if the
        game is not initialized; SystemExit with ``ExitCode.INTERNAL_ERROR`` after an uncaught
        exception (logged with its traceback), ``ExitCode.INTERRUPTED`` after Ctrl-C
        (KeyboardInterrupt), or whatever status a SystemExit raised during the run carries (a
        signal handler's, a game's own), except a game's own successful exit that cuts a replay
        short (``ExitCode.REPLAY_DIVERGED``; a rebaseline ends normally then, with what the game
        ran); at the normal end of a replay, with the replay's exit code (``ExitCode.SUCCESS``,
        ``ExitCode.REPLAY_DIVERGED`` or ``ExitCode.UNUSABLE_INPUT`` for a truncated recording).
        """
        profiler = self._begin_start()
        with self._crash_boundary(profiler=profiler):
            self._run_game()

    async def start_async(self: Self, *, wait_for_tick: Callable[[], Awaitable[float]]) -> None:
        """Start the game engine, giving control back to the caller between frames.

        For a host that must not block (a browser: glitchygames/host.py). The run is
        ``start()``'s, inside the same crash boundary (the same teardown and exit codes), but
        its frames are driven by one awaited ``wait_for_tick()`` per outer tick: a live game's
        by ``GameHost.run_async`` (an inner frame on the ticks ``TickPacer`` picks for the
        target FPS), a watched replay's by its viewer (``run_watched_replay_async``: the tick's
        inner frames, then the viewer's outer frame).

        Args:
            wait_for_tick: Waits for the next outer tick (a browser animation frame) and
                returns its timestamp in seconds.

        It ends as ``start()`` does (see there).

        Raises:
            RuntimeError: If the run is a headless replay (it never holds between frames, so
                it would never give control back), or (from ``_begin_start``) the game is not
                initialized.

        """
        # Chosen first (a run start_async cannot drive is refused before anything starts), but
        # called inside the boundary
        run_frames: Callable[[], Awaitable[None]]
        if self.host is not None:
            run_frames = functools.partial(
                self.host.run_async, scene_manager=self.scene_manager, wait_for_tick=wait_for_tick
            )
        elif self.replay_sources is not None and not self.replay_sources.options.headless:
            run_frames = functools.partial(
                run_watched_replay_async,
                scene_manager=self.scene_manager,
                viewer=self.replay_sources.viewer,
                wait_for_tick=wait_for_tick,
            )
        else:
            raise RuntimeError(ASYNC_RUN_NEEDS_HOST_MSG)
        profiler = self._begin_start()
        with self._crash_boundary(profiler=profiler):
            if self._begin_run():
                if self._power_on_plays():
                    self._hand_back_power_on(
                        outcome=await play_power_on_async(
                            screen=self.screen,
                            sources=active_sources(),
                            wait_for_tick=wait_for_tick,
                        )
                    )
                self._build_game(paced_by_timer=False)
                await run_frames()

    def _begin_start(self: Self) -> cProfile.Profile | None:
        """Log the start, check there is a game and start the profiler (``--profile``).

        Returns:
            The running profiler, or None.

        Raises:
            RuntimeError: If the game is not initialized.

        """
        # This ensures that logging is enabled as soon as the game object is created.
        logging.getLogger('game')

        self.log.info('Starting game engine for game: %s', type(self).NAME)
        if self.game is None:
            raise RuntimeError(GAME_NOT_INITIALIZED_MSG)

        profiler = None
        if GameEngine.OPTIONS['profile']:
            # Enabled before the crash boundary, so the teardown prints only a profiler that ran
            profiler = cProfile.Profile()
            profiler.enable()
        return profiler

    @contextlib.contextmanager
    def _crash_boundary(self: Self, *, profiler: cProfile.Profile | None) -> Generator[None]:
        """Turn however the run in the ``with`` block ends into an exit code, after the teardown.

        Shared by ``start()`` and ``start_async()`` (a synchronous ``with`` holds an ``await``
        too). An exception it handles ends the run with its exit code; a SystemExit it does not
        turn into one propagates, after the teardown. See ``start()``.

        Args:
            profiler: The run's profiler (``--profile``), printed by the teardown; or None.

        Yields:
            Nothing: the run goes in the ``with`` block.

        Raises:
            SystemExit: A SystemExit raised in the block that does not cut a replay short,
                again after the teardown (``start()`` lists the endings).

        """
        # Set when the run ends in a way that start() turns into an exit code
        exit_code: ExitCode | None = None
        run_error: Exception | None = None
        # What ended the run early, described for the replay report (None: a normal end)
        run_ended_by: str | None = None
        try:
            # The crash boundary: anything the run raises is turned into an exit code below
            yield
        except KeyboardInterrupt:
            # Ctrl-C: never an internal error; exits INTERRUPTED once the teardown has run
            exit_code = ExitCode.INTERRUPTED
            run_ended_by = exit_code.describe()
        except SystemExit as exit_request:
            # A deliberate exit (a signal handler's, a game's) keeps its status
            run_ended_by = self._describe_exit_request(exit_status=exit_request.code)
            if not self._exit_cuts_a_replay_short(exit_status=exit_request.code):
                raise
            exit_code, run_ended_by = self._outcome_of_a_replay_cut_short(run_ended_by=run_ended_by)
        except RecordingWriteError as error:
            # The disk filled part way: logged on one line by the recorder (BUGS.md #82)
            exit_code = ExitCode.CANNOT_WRITE_OUTPUT
            run_ended_by = exit_code.describe()
            run_error = error
        except Exception as error:
            scene_name = self._resolve_scene_name_for_error()
            self.log.exception("Runtime error during game execution @ scene '%s'", scene_name)
            exit_code = ExitCode.INTERNAL_ERROR
            run_ended_by = exit_code.describe()
            run_error = error
        finally:
            teardown_error = self._tear_down_run(profiler=profiler, run_ended_by=run_ended_by)
            if teardown_error is not None:
                # Replaces whatever was ending the run: a failed teardown is an internal error
                exit_with(exit_code=ExitCode.INTERNAL_ERROR, cause=teardown_error)
        self._end_run(exit_code=exit_code, run_error=run_error)

    def _run_game(self: Self) -> None:
        """Construct the game and run its scenes: the whole run inside start()'s crash boundary."""
        if not self._begin_run():
            return
        if self._power_on_plays():
            self._hand_back_power_on(
                outcome=play_power_on(screen=self.screen, sources=active_sources())
            )
        self._build_game(paced_by_timer=True)
        if self.host is not None:
            self.host.run(scene_manager=self.scene_manager)
        else:
            # A replay: its doors (and watched, its viewer) drive the blocking loop
            self.scene_manager.start()

    def _begin_run(self: Self) -> bool:
        """Start the run inside the crash boundary: signal handlers, then the game or a listing.

        With --list-input-devices the listing replaces the game: it is printed and nothing is
        built, so no frame runs.

        Returns:
            Whether the game is to be built and run (False after --list-input-devices).

        """
        # For the whole run, so a signal always ends it through start()'s teardown
        self._install_signal_handlers()

        if GameEngine.OPTIONS.get('list_input_devices'):
            # In place of the game: its scene is never built, nothing is recorded
            lines = list_input_devices(
                sources=active_sources(),
                input_mode=InputMode(GameEngine.OPTIONS.get('input_mode', InputMode.AUTO)).value,
                prompt=input_device_prompt(),
            )
            sys.stdout.write('\n'.join(lines) + '\n')
            return False
        return True

    def _power_on_plays(self: Self) -> bool:
        """Return whether the CRT power-on sequence plays before the game (``--crt-power-on``).

        Returns:
            True to play it (glitchygames/crt_power_on.py ``should_play``).

        """
        return should_play(
            mode=CrtPowerOnMode(GameEngine.OPTIONS.get('crt_power_on', CrtPowerOnMode.AUTO)),
            video_driver=pygame.display.get_driver(),
            options=GameEngine.OPTIONS,
        )

    def _hand_back_power_on(self: Self, *, outcome: PowerOnOutcome) -> None:
        """Give the game what the power-on sequence ended with: a window closed during it quits.

        Args:
            outcome: How the sequence ended.

        """
        self.log.debug('CRT power-on sequence: %s', outcome)
        if outcome is PowerOnOutcome.QUIT:
            post_input_event(event=pygame.event.Event(pygame.QUIT))

    def _build_game(self: Self, *, paced_by_timer: bool) -> None:
        """Construct the game and its first scene, up to the first frame (inside the boundary).

        Args:
            paced_by_timer: Whether the frames wait on the engine's timer (``start()``), which
                is then calibrated; False for ``start_async()``.

        """
        # Initialize the game instance
        self.game = self.game(options=GameEngine.OPTIONS)

        # Set the scene manager's OPTIONS class variable for managers that expect it
        SceneManager.OPTIONS = GameEngine.OPTIONS
        self.scene_manager.game_engine = self

        self._initialize_event_managers()

        self.scene_manager.switch_to_scene(self.game)
        self._configure_timer_and_performance(paced_by_timer=paced_by_timer)
        self._start_requested_trace_recording()

    def _describe_exit_request(self: Self, *, exit_status: object) -> str:
        """Describe a SystemExit that ended the run, for the log and the replay report.

        Args:
            exit_status: The SystemExit's code.

        Returns:
            ``ExitCode.describe_status`` of an integer status (logged as ``Exiting with ...``),
            else ``SystemExit(<code>)``.

        """
        if isinstance(exit_status, int):
            description = ExitCode.describe_status(exit_status)
            self.log.info('Exiting with %s', description)
            return description
        return f'SystemExit({exit_status!r})'

    def _end_run(self: Self, *, exit_code: ExitCode | None, run_error: Exception | None) -> None:
        """Exit as the run ended, once its teardown has run (the recording is closed).

        Args:
            exit_code: The code the run ends with (None: it ended normally).
            run_error: The exception that ended it, chained as the exit's cause, or None.

        """
        exit_code = self._exit_code_after_recording(exit_code=exit_code)
        if exit_code is not None:
            exit_with(exit_code=exit_code, cause=run_error)
        if self.replay_sources is not None:
            self._end_replay_run(replay_sources=self.replay_sources)

    def _exit_code_after_recording(self: Self, *, exit_code: ExitCode | None) -> ExitCode | None:
        """Return the run's exit code, made ``CANNOT_WRITE_OUTPUT`` if its recording failed.

        A recording whose last write failed as it was closed in the teardown (the gzip trailer)
        turns a run that otherwise ended normally into ``CANNOT_WRITE_OUTPUT``; a run already
        ending with a code (a crash, a signal) keeps it.

        Args:
            exit_code: The code the run ends with so far (None: it ended normally).

        Returns:
            The exit code (None: the run ends normally).

        """
        if exit_code is None and self.recording_write_failed:
            return ExitCode.CANNOT_WRITE_OUTPUT
        return exit_code

    def _outcome_of_a_replay_cut_short(
        self: Self, *, run_ended_by: str
    ) -> tuple[ExitCode | None, str | None]:
        """Return how a run ends when a game's own successful exit cut its replay short.

        A plain replay ends as diverged: ``SUCCESS`` would say it matched (the report says
        where it stopped). A rebaseline takes it as the game ending early, as ``quit_game()``
        would: the run ends normally, NEW is written with the frames that ran and the run exits
        ``REBASELINE_INPUT_LOST`` (glitchygames/replay/rebaseline.py, rule 4).

        Args:
            run_ended_by: The exit, described (``_describe_exit_request``).

        Returns:
            The exit code ``start`` exits with (None: the normal end of a replay) and what
            ended the run early (None: it ended normally).

        """
        if self.rebaseline is not None:
            return None, None
        return ExitCode.REPLAY_DIVERGED, run_ended_by

    def _exit_cuts_a_replay_short(self: Self, *, exit_status: object) -> bool:
        """Report whether a successful SystemExit ended a replay before it reached its result.

        A game's own ``sys.exit(0)`` (or ``sys.exit()``) during a replay that is still running
        would end the run ``SUCCESS``, which says the replay matched: ``start`` exits
        ``REPLAY_DIVERGED`` instead. Any other status (a signal's, a game's failure) is kept, as
        it already says the run did not succeed.

        Args:
            exit_status: The SystemExit's code.

        Returns:
            True while replaying, the replay still running and the status 0 or None.

        """
        return (
            self.replay_sources is not None
            and self.replay_sources.result.end_reason == RUNNING_END_REASON
            and (
                exit_status is None
                or (isinstance(exit_status, int) and exit_status == ExitCode.SUCCESS)
            )
        )

    def _end_replay_run(self: Self, *, replay_sources: ReplaySources) -> NoReturn:
        """Exit a replay's run that ended normally, after the teardown.

        A replay exits with its own code (a divergence is ``REPLAY_DIVERGED``; never the
        ``INTERNAL_ERROR`` or ``INTERRUPTED`` of an early end), unless the viewer stepped back:
        then the replay restarts (``_restart_replay``), its window already closed. A rebaseline
        whose new recording could not be moved into place (glitchygames/replay/rebaseline.py,
        rule 4), and a replay whose digest file could not be written (rule 12 of
        glitchygames/replay/driver.py), exit ``CANNOT_WRITE_OUTPUT``.

        Args:
            replay_sources: The replay's sources.

        """
        restart_frame = replay_sources.result.restart_frame
        if restart_frame is not None:
            self._restart_replay(replay_sources=replay_sources, restart_frame=restart_frame)
        rebaseline_write_failed = self.rebaseline is not None and self.rebaseline.write_failed
        if rebaseline_write_failed or replay_sources.digest_write_failed:
            exit_with(exit_code=ExitCode.CANNOT_WRITE_OUTPUT)
        exit_with(
            exit_code=replay_sources.result.exit_code(policy=replay_sources.options.exit_policy)
        )

    def _restart_replay(
        self: Self, *, replay_sources: ReplaySources, restart_frame: int
    ) -> NoReturn:
        """Restart the torn-down watched replay at ``restart_frame`` and exit with the outcome.

        The restart (glitchygames/replay/rebuild.py) runs this process's own command line with
        the pause frame, keeping whether the debug overlay was shown; this process either hands
        it to the supervising replay process or supervises the restarted replays itself. With
        bookmarks, the bookmarked copy is saved first and the restart replays it, so the
        bookmarks survive (rule 16 of glitchygames/replay/driver.py); if it cannot be saved,
        the restart replays this run's recording without them, with a warning naming them.

        Args:
            replay_sources: The torn-down replay's sources.
            restart_frame: The frame the restarted replay pauses at.

        Raises:
            SystemExit: Always, with the status ``relaunch_replay`` returns.

        """
        self.log.info('Restarting the replay at frame %s', restart_frame)
        debug_overlay = self.scene_manager.debug_overlay
        controls = replay_sources.controls
        recording_path = Path(GameEngine.OPTIONS['replay_trace'])
        if controls.bookmarks:
            bookmarked_copy = replay_sources.bookmarks.save()
            if bookmarked_copy is None:
                self.log.warning(
                    'Restarting without the bookmarks %s: the bookmarked copy '
                    'of %s could not be saved',
                    controls.bookmarks,
                    recording_path,
                )
            else:
                recording_path = bookmarked_copy
        command = restart_command(
            original=sys.orig_argv,
            recording_path=recording_path,
            pause_at_frame=restart_frame,
            debug_overlay_visible=debug_overlay.is_visible,
            viewer_state=ViewerState(
                speed=controls.speed,
                debug_panel=debug_overlay.panel,
                divergence_frame=controls.divergence_frame,
            ),
        )
        # _shutdown put the default handling back: while supervising, SIGTERM and SIGHUP end the
        # run with SystemExit again, so subprocess.run kills and reaps the child
        with self._waiting_for_child_processes():
            status = relaunch_replay(
                command=command,
                handoff_path=replay_sources.options.restart_handoff_path,
                result_exit_code=replay_sources.result.exit_code(
                    policy=replay_sources.options.exit_policy
                ),
            )
        try:
            exit_code = ExitCode(status)
        except ValueError:
            # A status no member names (a game's own exit status, a signal without a member)
            self.log.info('Exiting with %s', ExitCode.describe_status(status))
            raise SystemExit(status) from None
        exit_with(exit_code=exit_code)

    @classmethod
    def quit_game(cls) -> None:
        """Quit the game.

        Emits a events.HashableEvent(pygame.QUIT, {}) event.

        """
        # put a quit event in the event queue.
        post_event(pygame.event.Event(pygame.QUIT, {}))

    def handle_event(self, event: events.HashableEvent) -> None:
        """Handle pygame events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # First check for system-level QUIT event (window close button)
        if event.type == pygame.QUIT:
            self.log.info('Window close requested')
            self.scene_manager.quit_requested = True
            return

        # Check if there are any focused sprites in the current scene
        scene = self.scene_manager.active_scene
        if scene and scene.all_sprites:
            focused_sprites = [
                sprite
                for sprite in scene.all_sprites
                if hasattr(sprite, 'is_active') and sprite.is_active
            ]

            # If we have focused sprites, ALL key events go to the scene
            if focused_sprites and event.type == pygame.KEYDOWN:
                self.scene_manager.handle_event(event)
                return

        # Only handle engine-level key events if no focused sprites
        if event.type == pygame.KEYDOWN and getattr(event, 'key', None) == pygame.K_q:
            self.log.info('Quit key pressed with no focused sprites')
            self.scene_manager.quit_requested = True
            return

        # Pass other events to the scene manager
        self.scene_manager.handle_event(event)

    def process_events(
        self: Self, *, should_discard: Callable[[pygame.event.Event], bool] | None = None
    ) -> bool:
        """Process every event queued this frame.

        ``pygame.event.get()`` removes the whole batch from SDL's queue at once, so every event
        of the batch is handled here: none may be dropped. Each event is judged on its own; an
        event whose type has no entry in ``EVENT_HANDLERS``, or whose handler did not handle
        it, goes to ``process_unimplemented_event``.

        Args:
            should_discard: Returns True for an event to remove from the batch without
                processing it (not counted as unhandled). SceneManager passes
                ``is_discarded_during_transition`` during a transition.

        Returns:
            bool: True if at least one event was dispatched and every dispatched event was
            handled (a raw-event scene's ``process_event`` counts as handled). False if any
            dispatched event was unhandled, or if nothing was dispatched: an empty batch, or
            one whose events were all discarded.

        """
        raw_events = self._pump_events()
        # Polled input is read once per frame, right after the pump, so it agrees with this
        # frame's events; it stays fixed until the next frame's pump, so dt_tick (which runs
        # before this) reads the previous frame's snapshot (glitchygames/input/state.py)
        set_current_input(snapshot=active_sources().input_snapshot())
        dispatched_event_count = 0
        every_event_was_handled = True
        for pygame_event in raw_events:
            if should_discard is not None and should_discard(pygame_event):
                continue
            dispatched_event_count += 1

            # Support scenes processing pygame raw events, bypassing
            # the glitchygames.engine event processing altogether
            if hasattr(self._active_scene, 'process_event'):
                self._active_scene.process_event(pygame_event)  # type: ignore[union-attr] # ty: ignore[call-non-callable]
                continue

            event = events.HashableEvent.from_pygame(pygame_event)

            # Decided per event: a type missing from the map is unhandled
            event_was_handled = False
            if event.type in GameEngine.EVENT_HANDLERS:
                event_was_handled = bool(GameEngine.EVENT_HANDLERS[event.type](event))

            # If an event is not in the event handler map, or the function
            # called didn't handle the event in question, we'll process it
            # as an unimplemented event
            if not event_was_handled:
                self.process_unimplemented_event(event)
                every_event_was_handled = False

        return dispatched_event_count > 0 and every_event_was_handled

    def _pump_events(self: Self) -> list[pygame.event.Event]:
        """Take the next batch from the active sources' event pump: the one place it is read.

        Live sources read SDL's queue; a replay's sources hand back a recorded batch instead;
        ``--record-trace``'s ``RecordingSources`` record the batch exactly as the pump returned
        it, before any dispatch or discarding (glitchygames/sources.py). Events a playback scope
        held for the live game come first (``take_redelivered_events``, taken after the doors'
        pump so a recording can write them into this frame's ``redelivered_events``). The
        scene manager's instant-replay journal gets the batch too, classified as a recorder
        classifies it (glitchygames/instant_replay.py, rule 4): by a replay's merge when the
        doors are a replay's (``ReplaySources.last_batch_origins``), else by the code-posted
        events pending before the pump. Then the posts the pump did not return are forgotten
        (the engine owns the internal-post tracker for the whole run).

        Returns:
            The batch, in queue order.

        """
        posts_before_pump = list(pending_internal_posts())
        doors = active_sources()
        batch = doors.pump_events()
        redelivered_events = take_redelivered_events()
        self.scene_manager.journal_pumped_events(
            raw_events=batch,
            posts_before_pump=posts_before_pump,
            origins=replayed_batch_origins(doors=doors),
            redelivered_events=redelivered_events,
        )
        # Matched or not returned, the posts made before this pump are done with (a recorder
        # or a replay pumping underneath has already consumed them)
        forget_pending_posts()
        return [*(event for event, _origin in redelivered_events), *batch]

    def process_audio_event(self: Self, event: events.HashableEvent) -> bool:
        """Process an audio event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.

        """
        if event.type == pygame.AUDIODEVICEADDED:
            # AUDIODEVICEADDED which, iscapture
            self.audio_manager.on_audio_device_added_event(event)
            return True

        if event.type == pygame.AUDIODEVICEREMOVED:
            # AUDIODEVICEREMOVED which, iscapture
            self.audio_manager.on_audio_device_removed_event(event)
            return True

        return False

    def process_app_event(self: Self, event: events.HashableEvent) -> bool:  # ruff: ignore[too-many-return-statements]
        """Process an app event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.

        """
        if event.type == pygame.APP_DIDENTERBACKGROUND:
            self.app_manager.on_app_did_enter_background_event(event)
            return True

        if event.type == pygame.APP_DIDENTERFOREGROUND:
            self.app_manager.on_app_did_enter_foreground_event(event)
            return True

        if event.type == pygame.APP_WILLENTERBACKGROUND:
            self.app_manager.on_app_will_enter_background_event(event)
            return True

        if event.type == pygame.APP_WILLENTERFOREGROUND:
            self.app_manager.on_app_will_enter_foreground_event(event)
            return True

        if event.type == pygame.APP_LOWMEMORY:
            self.app_manager.on_app_low_memory_event(event)
            return True

        if event.type == pygame.APP_TERMINATING:
            self.app_manager.on_app_terminating_event(event)
            return True

        return False

    def process_controller_event(self: Self, event: events.HashableEvent) -> bool:
        """Process a controller event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.

        """
        if self.controller_manager is None:
            return False

        # Each device's input events come from one layer only: a controller event of a device
        # the game does not see on its controller layer is dropped (handled: deliberately not
        # dispatched; glitchygames/input/input_devices.py, rules 1 and 2)
        if not self.input_devices.dispatches(
            event_type=event.type, instance_id=self._device_event_instance_id(event=event)
        ):
            return True

        # Matched by class (the type's class from events.EVENT_CLASSES, which every event of
        # the type is, however it was built) and then by type where a class covers several
        manager = self.controller_manager
        match event:
            case events.ControllerAxisEvent():
                manager.on_controller_axis_motion_event(event)
            case events.ControllerTouchpadEvent(type=pygame.CONTROLLERTOUCHPADMOTION):
                manager.on_controller_touchpad_motion_event(event)
            case events.ControllerButtonEvent(type=pygame.CONTROLLERBUTTONDOWN):
                manager.on_controller_button_down_event(event)
            case events.ControllerButtonEvent(type=pygame.CONTROLLERBUTTONUP):
                manager.on_controller_button_up_event(event)
            case events.ControllerTouchpadEvent(type=pygame.CONTROLLERTOUCHPADDOWN):
                manager.on_controller_touchpad_down_event(event)
            case events.ControllerTouchpadEvent(type=pygame.CONTROLLERTOUCHPADUP):
                manager.on_controller_touchpad_up_event(event)
            case events.HashableEvent(type=pygame.CONTROLLERSENSORUPDATE):
                manager.on_controller_sensor_update_event(event)
            case _:
                return self._process_controller_device_event(manager=manager, event=event)
        return True

    def _process_controller_device_event(
        self: Self, *, manager: ControllerEventManager, event: events.HashableEvent
    ) -> bool:
        """Process a controller's added, removed or remapped event (``process_controller_event``).

        Returns:
            bool: True if the event was handled, False otherwise.

        """
        match event:
            case events.ControllerDeviceEvent(type=pygame.CONTROLLERDEVICEREMOVED):
                manager.on_controller_device_removed_event(event)
                self._synchronize_input_devices()
            case events.ControllerDeviceAddedEvent():
                manager.on_controller_device_added_event(event)
                self._synchronize_input_devices()
            case events.ControllerDeviceEvent(type=pygame.CONTROLLERDEVICEREMAPPED):
                manager.on_controller_device_remapped_event(event)
            case _:
                # We haven't handled this event, so let's see if it's a controller init event
                return False
        return True

    def process_drop_event(self: Self, event: events.HashableEvent) -> bool:
        """Process a drop event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.

        """
        if event.type == pygame.DROPBEGIN:
            self.drop_manager.on_drop_begin_event(event)
            return True

        if event.type == pygame.DROPCOMPLETE:
            self.drop_manager.on_drop_complete_event(event)
            return True

        if event.type == pygame.DROPFILE:
            self.drop_manager.on_drop_file_event(event)
            return True

        if event.type == pygame.DROPTEXT:
            self.drop_manager.on_drop_text_event(event)
            return True

        return False

    def process_touch_event(self: Self, event: events.HashableEvent) -> bool:
        """Process a touch event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.

        """
        if event.type == pygame.FINGERDOWN:
            self.touch_manager.on_touch_down_event(event)
            return True

        if event.type == pygame.FINGERUP:
            self.touch_manager.on_touch_up_event(event)
            return True

        if event.type == pygame.FINGERMOTION:
            self.touch_manager.on_touch_motion_event(event)
            return True

        return False

    def process_midi_event(self: Self, event: events.HashableEvent) -> bool:
        """Process a midi event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.

        """
        if event.type == pygame.MIDIIN:
            # MIDIIN device_id, status, data1, data2
            self.scene_manager.handle_event(event)
            return True

        if event.type == pygame.MIDIOUT:
            # MIDIOUT device_id, status, data1, data2
            self.scene_manager.handle_event(event)
            return True

        return False

    def process_mouse_event(self: Self, event: events.HashableEvent) -> bool:
        """Process a mouse event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.

        """
        if event.type == pygame.MOUSEMOTION:
            # MOUSEMOTION      pos, rel, buttons
            self.mouse_manager.on_mouse_motion_event(event)
            return True

        if event.type == pygame.MOUSEBUTTONUP:
            # MOUSEBUTTONUP    pos, button
            self.mouse_manager.on_mouse_button_up_event(event)
            return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            # MOUSEBUTTONDOWN  pos, button
            self.log.debug(
                'ENGINE: MOUSEBUTTONDOWN received: button=%s, pos=%s',
                getattr(event, 'button', None),
                getattr(event, 'pos', None),
            )
            self.mouse_manager.on_mouse_button_down_event(event)
            return True

        if event.type == pygame.MOUSEWHEEL:
            self.mouse_manager.on_mouse_wheel_event(event)
            return True

        return False

    def process_keyboard_event(self: Self, event: events.HashableEvent) -> bool:
        """Process a keyboard event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.

        """
        if event.type == pygame.KEYDOWN:
            # KEYDOWN          unicode, key, mod
            self.keyboard_manager.on_key_down_event(event)
            return True

        if event.type == pygame.KEYUP:
            # KEYUP            key, mod
            self.keyboard_manager.on_key_up_event(event)
            return True

        return False

    def process_joystick_event(self: Self, event: events.HashableEvent) -> bool:
        """Process a joystick event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.

        """
        # Each device's input events come from one layer only: a mapped pad's joystick-layer
        # events are dropped (handled: deliberately not dispatched), as are the events of a
        # device the game does not see (glitchygames/input/input_devices.py, rules 1 and 2)
        if not self.input_devices.dispatches(
            event_type=event.type, instance_id=self._device_event_instance_id(event=event)
        ):
            return True

        # Matched by class (the type's class from events.EVENT_CLASSES), then by type for
        # the button class's two types
        match event:
            case events.JoyAxisEvent():
                # JOYAXISMOTION    instance_id, axis, value
                self.joystick_manager.on_joy_axis_motion_event(event)
            case events.JoyBallEvent():
                # JOYBALLMOTION    instance_id, ball, rel
                self.joystick_manager.on_joy_ball_motion_event(event)
            case events.JoyHatEvent():
                # JOYHATMOTION     instance_id, hat, value
                self.joystick_manager.on_joy_hat_motion_event(event)
            case events.JoyButtonEvent(type=pygame.JOYBUTTONUP):
                # JOYBUTTONUP      instance_id, button
                self.joystick_manager.on_joy_button_up_event(event)
            case events.JoyButtonEvent(type=pygame.JOYBUTTONDOWN):
                # JOYBUTTONDOWN    instance_id, button
                self.joystick_manager.on_joy_button_down_event(event)
            case events.JoyDeviceAddedEvent():
                self.joystick_manager.on_joy_device_added_event(event)
                self._synchronize_input_devices()
            case events.JoyDeviceRemovedEvent():
                self.joystick_manager.on_joy_device_removed_event(event)
                self._synchronize_input_devices()
            case _:
                return False
        return True

    @staticmethod
    def _device_event_instance_id(*, event: events.HashableEvent) -> int | None:
        """Return the instance id of a joystick or controller event, None when it has none.

        An added event names a device index instead (``device_index``): it is a device
        event, which always passes (``InputDevices.dispatches``).

        Returns:
            The instance id, or None.

        """
        instance_id = event.dict.get('instance_id')
        return None if instance_id is None else int(instance_id)

    def process_text_event(self: Self, event: events.HashableEvent) -> bool:
        """Process a text event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.

        """
        # To the active scene's on_text_*_event (BUGS.md #200 item 1: both went to
        # process_unimplemented_event, so Scene's text handlers were never called)
        if event.type == pygame.TEXTEDITING:
            self.scene_manager.on_text_editing_event(event)
            return True

        if event.type == pygame.TEXTINPUT:
            self.scene_manager.on_text_input_event(event)
            return True

        return False

    def process_window_focus_event(self: Self, event: events.HashableEvent) -> bool:  # ruff: ignore[too-many-return-statements]
        """Process a window focus event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.

        """
        if event.type == pygame.WINDOWSHOWN:
            self.window_manager.on_window_shown_event(event)
            return True

        if event.type == pygame.WINDOWLEAVE:
            self.window_manager.on_window_leave_event(event)
            return True

        if event.type == pygame.WINDOWFOCUSGAINED:
            self.window_manager.on_window_focus_gained_event(event)
            with contextlib.suppress(Exception):
                pygame.event.set_grab(True)
            return True

        if event.type == pygame.WINDOWFOCUSLOST:
            self.window_manager.on_window_focus_lost_event(event)
            with contextlib.suppress(Exception):
                pygame.event.set_grab(False)
            return True

        if event.type == pygame.WINDOWENTER:
            self.window_manager.on_window_enter_event(event)
            return True

        if event.type == pygame.WINDOWTAKEFOCUS:
            self.window_manager.on_window_take_focus_event(event)
            return True

        return False

    def _build_window_event_dispatch(self: Self) -> dict[int, Callable[..., Any]]:
        """Build dispatch table mapping window event types to handler methods.

        Returns:
            Dictionary mapping pygame window event types to handler callables.

        """
        return {
            pygame.WINDOWSIZECHANGED: self.window_manager.on_window_size_changed_event,
            pygame.WINDOWRESTORED: self.window_manager.on_window_restored_event,
            pygame.WINDOWHITTEST: self.window_manager.on_window_hit_test_event,
            pygame.WINDOWHIDDEN: self.window_manager.on_window_hidden_event,
            pygame.WINDOWMINIMIZED: self.window_manager.on_window_minimized_event,
            pygame.WINDOWMAXIMIZED: self.window_manager.on_window_maximized_event,
            pygame.WINDOWMOVED: self.window_manager.on_window_moved_event,
            pygame.WINDOWCLOSE: self.window_manager.on_window_close_event,
            pygame.WINDOWEXPOSED: self.window_manager.on_window_exposed_event,
            pygame.WINDOWFOCUSLOST: self.window_manager.on_window_focus_lost_event,
            pygame.WINDOWFOCUSGAINED: self.window_manager.on_window_focus_gained_event,
            pygame.WINDOWRESIZED: self.window_manager.on_window_resized_event,
            pygame.WINDOWLEAVE: self.window_manager.on_window_leave_event,
            pygame.WINDOWENTER: self.window_manager.on_window_enter_event,
            pygame.WINDOWSHOWN: self.window_manager.on_window_shown_event,
            # BUGS.md #200 item 1: it had a handler but no entry, so it was never routed
            pygame.WINDOWTAKEFOCUS: self.window_manager.on_window_take_focus_event,
        }

    def process_window_event(self: Self, event: events.HashableEvent) -> bool:
        """Process a window event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.

        """
        dispatch: dict[int, Callable[..., Any]] = self._build_window_event_dispatch()
        handler = dispatch.get(event.type)
        if handler:
            handler(event)
            return True

        return False

    def process_game_event(self: Self, event: events.HashableEvent) -> bool:  # ruff: ignore[too-many-return-statements]
        """Process a game event.

        Args:
            event (events.HashableEvent): The event.

        Returns:
            bool: True if the event was handled, False otherwise.

        """
        # Game events are listed in the order they're most
        # likely to occur in; matched by class (the type's class from events.EVENT_CLASSES),
        # or by type for the types without a class of their own
        match event:
            case events.FpsEvent():
                # FPSEVENT is pygame.USEREVENT + 1
                self.game_manager.on_fps_event(event)
                return True

            case events.GameEvent():
                # GAMEEVENT is pygame.USEREVENT + 2
                self.game_manager.on_game_event(event)
                return True

            case events.HashableEvent(type=events.MENUEVENT):
                # MENUEVENT is pygame.USEREVENT + 3
                self.game_manager.on_menu_item_event(event)
                return True

            case events.ActiveEvent():
                # ACTIVEEVENT      gain, state
                self.game_manager.on_active_event(event)
                return True

            case events.HashableEvent(type=pygame.USEREVENT):
                # USEREVENT        code
                self.game_manager.on_user_event(event)
                return True

            case events.VideoResizeEvent():
                # VIDEORESIZE      size, w, h
                self.game_manager.on_video_resize_event(event)
                return True

            case events.HashableEvent(type=pygame.VIDEOEXPOSE):
                # VIDEOEXPOSE      none
                self.game_manager.on_video_expose_event(event)
                return True

            case events.HashableEvent(type=pygame.SYSWMEVENT):
                # SYSWMEVENT
                self.game_manager.on_sys_wm_event(event)
                return True

            case events.HashableEvent(type=pygame.QUIT):
                # QUIT             none
                self.game_manager.on_quit_event(event)
                return True

            case _:
                pass

        return False

    def process_unimplemented_event(self: Self, event: events.HashableEvent) -> None:
        """Process an unimplemented event.

        Args:
            event (events.HashableEvent): The event.

        """
        self._record_unhandled_event(event)

        # Debug: Special handling for event type 1543
        if event.type == UNKNOWN_SDL2_EVENT_TYPE_1543:
            event_name = pygame.event.event_name(event.type)
            LOG.debug(
                'process_unimplemented_event received event type %s (%s): %s',
                event.type,
                event_name,
                event,
            )
            LOG.debug('Event dict contents: %s', dict(event))
            LOG.debug(
                'Event attributes: %s',
                [attr for attr in dir(event) if not attr.startswith('_')],
            )

            # Check if this might be a controller event by looking at controller count
            # (through the devices door, glitchygames/input/devices.py)
            try:
                current_controller_count: int = active_sources().devices().controller_count()
                LOG.debug(
                    'Current controller count when event 1543 received: %s',
                    current_controller_count,
                )
            except pygame.error:
                LOG.debug('Controller system not initialized — skipping controller count check')

            # Check if this event has any controller-related attributes
            LOG.debug('Event has device_index: %s', hasattr(event, 'device_index'))
            LOG.debug('Event has guid: %s', hasattr(event, 'guid'))
            LOG.debug('Event has instance_id: %s', hasattr(event, 'instance_id'))

            # Try to get the raw event object if possible
            LOG.debug('Event type: %s', type(event))
            LOG.debug('Event repr: %r', event)
            LOG.debug(
                'pygame.event.event_name(event.type): %s',
                pygame.event.event_name(event.type),
            )

        if event.type not in self.UNIMPLEMENTED_EVENTS:
            self.log.debug(
                '(UNIMPLEMENTED) %s: %s',
                pygame.event.event_name(event.type).upper(),
                event,
            )
            self.UNIMPLEMENTED_EVENTS.append(event.type)

    def _record_unhandled_event(self: Self, event: events.HashableEvent) -> None:
        """Count an unhandled event under its type, keeping the first one's time and names.

        Args:
            event (events.HashableEvent): The event.

        """
        record = self.unhandled_events.get(event.type)
        if record is not None:
            record.count += 1
            return
        # Names only: values can be large or private. 'type' is the key itself, and names
        # starting with '_' are internals (HashableEvent's cached hash)
        attribute_names = tuple(
            sorted(
                name
                for name in getattr(event, '__dict__', {})
                if name != 'type' and not name.startswith('_')
            )
        )
        self.unhandled_events[event.type] = UnhandledEventRecord(
            count=1,
            # The frame clock, which reset_sources() restarted in __init__
            first_seen_seconds=elapsed_seconds(),
            attribute_names=attribute_names,
        )

    def unhandled_event_report(self: Self) -> list[str]:
        """Describe every unhandled event type, most frequent first.

        Each line names the type (pygame's event name and its number, so custom and unknown
        types still show), its count, when it was first seen and the first event's attribute
        names, e.g. ``JOYDEVICEADDED (1541) x1, first at 0.3 s, attributes: device_index, guid``.

        Returns:
            One line per type; empty when every event was handled.

        """
        records = sorted(
            self.unhandled_events.items(),
            key=lambda item: item[1].count,
            reverse=True,
        )
        return [
            f'{pygame.event.event_name(event_type).upper()} ({event_type}) x{record.count}, '
            f'first at {record.first_seen_seconds:.1f} s, '
            f'attributes: {", ".join(record.attribute_names) or "none"}'
            for event_type, record in records
        ]

    def _log_sprite_count_report(self: Self) -> None:
        """Log the sprite counts at teardown: the total, then each sprite type's counters.

        Logged here, not from a finaliser: a ``__del__`` runs whenever the garbage collector
        does, possibly in the middle of a write to the stream the log goes to, where a second
        write raises ``RuntimeError: reentrant call`` (BUGS.md #188).
        """
        self.log.info('Sprite Count: %s', Sprite.SPRITE_COUNT)
        for sprite_type, counters in Sprite.SPRITE_COUNTERS.items():
            for counter_name, counter_value in counters.items():
                self.log.info('%s Sprite %s: %s', sprite_type, counter_name, counter_value)

    def _log_unhandled_event_report(self: Self) -> None:
        """Log the unhandled event table at teardown; log nothing if there were none."""
        report_lines = self.unhandled_event_report()
        if not report_lines:
            return
        # Framed like the performance shutdown reports logged just before it
        self.log.info('\n%s', '=' * 80)
        self.log.info('Unhandled events:')
        for report_line in report_lines:
            self.log.info('  %s', report_line)
        self.log.info('=' * 80)

    def post_game_event(self: Self, event_subtype: int, event_data: dict[str, Any]) -> None:
        """Post a game event.

        Args:
            event_subtype (int): The event subtype.
            event_data (dict[str, Any]): The event data.

        """
        event: dict[str, Any] = event_data.copy()
        event['subtype'] = event_subtype
        post_event(pygame.event.Event(events.GAMEEVENT, event))
        self.log.debug('Posted Event: %s', event)

    def suppress_event(self: Self, *args: Any, attr: str, **kwargs: Any) -> None:
        """Suppress an event.

        Args:
            *args: The args.
            attr (str): The attribute.
            **kwargs: The kwargs.

        """
        self.log.debug('Suppressing event: %s(%s, %s)', attr, args, kwargs)

    def register_game_event(self: Self, event_type: int, callback: Callable[..., Any]) -> None:
        """Register a game event.

        Args:
            event_type (int): The event type.
            callback (Callable[..., Any]): The callback.

        """
        # This registers a subtype of type GAMEEVENT to call a callback.
        self.log.info('Registering event type "%s" for %s', event_type, callback)
        self.registered_events[event_type] = callback

    def missing_event(self: Self, *args: Any, **kwargs: Any) -> None:
        """Suppress unhandled on_*_event methods.

        We only want to log this once per event type.

        Args:
            *args: The args.
            **kwargs: The kwargs.

        """
        # NOTE: Consider adding an engine option to raise an exception
        #       when an unimplemented event is called.
        if self.LAST_EVENT_MISS not in self.MISSING_EVENTS:
            self.MISSING_EVENTS.append(self.LAST_EVENT_MISS)

            self.log.info(
                'Unimplemented method called: %s%s, %s', self.LAST_EVENT_MISS, args, kwargs
            )
            self.suppress_event(*args, attr=self.LAST_EVENT_MISS, **kwargs)

        # Ensures we can always ctrl-c in cases where event spam occurs.
        time.sleep(0)

    # If the game hasn't hooked a call, we should check if the scene manager has.
    #
    # This will allow scenes to get pygame events directly, but we can still
    # hook those events in this engine, or in the subclassed game object, too.
    #
    # This allows maximum flexibility of event processing, with low overhead
    # at the expense of a slight layer violation.
    @override
    def __getattr__(self: Self, attr: str) -> Callable[..., Any]:
        """Suppress unhandled on_*_event methods.

        If the attribute being looked up is not an on_*_event
        attribute, raise AttributeError as usual.

        Args:
            attr (str): The attribute to proxy.

        Returns:
            Callable: The callable object.

        Raises:
            AttributeError: If the attribute is not an on_*_event method.

        """
        if attr.startswith('on_') and attr.endswith('_event'):
            GameEngine.LAST_EVENT_MISS = attr  # type: ignore[reportConstantRedefinition]

            return self.missing_event

        raise AttributeError(MISSING_ATTRIBUTE_MSG.format(cls=type(self), attr=attr))
