"""The game host (glitchygames/host.py): its doors, its tick pacer and its frame drivers."""

from __future__ import annotations

import asyncio
import itertools
import logging
import subprocess  # ruff: ignore[suspicious-subprocess-import] - runs this interpreter on a fixed program
import sys
import textwrap
from datetime import UTC, datetime
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Self

import pygame
import pytest

from glitchygames.host import TICKS_BEFORE_LOGGING_RATE, GameHost, HostSources, TickPacer
from glitchygames.input.state import IDLE_INPUT
from glitchygames.live_sources import LiveSources
from glitchygames.scenes import Scene, SceneManager
from glitchygames.sources import install_sources

if TYPE_CHECKING:
    from glitchygames.state.manager import SaveManager

SIXTY_HERTZ_SECONDS = 1 / 60
HUNDRED_TWENTY_HERTZ_SECONDS = 1 / 120
HUNDRED_FORTY_FOUR_HERTZ_SECONDS = 1 / 144


class RecordingDoors:
    """Stand-in inner doors that record every call and return a distinct answer for each."""

    def __init__(self: Self) -> None:
        """Start with no calls recorded."""
        self.random_seed = 1234
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.registry = object()
        self.store = object()
        self.snapshot = IDLE_INPUT
        self.now = datetime(2026, 10, 23, tzinfo=UTC)

    def _record(self: Self, name: str, **arguments: Any) -> None:
        self.calls.append((name, arguments))

    @property
    def opened_save_namespaces(self: Self) -> dict[str, SaveManager]:
        self._record('opened_save_namespaces')
        return {'game': self.store}  # type: ignore[dict-item]

    @property
    def captures_scene_starts(self: Self) -> bool:
        self._record('captures_scene_starts')
        return True

    @property
    def stop_requested(self: Self) -> bool:
        self._record('stop_requested')
        return True

    def on_installed(self: Self) -> None:
        self._record('on_installed')

    def on_uninstalled(self: Self) -> None:
        self._record('on_uninstalled')

    def pump_events(self: Self) -> list[pygame.event.Event]:
        self._record('pump_events')
        return [pygame.event.Event(pygame.USEREVENT, marker='pumped')]

    def frame_seconds(self: Self, *, measured: float) -> float:
        self._record('frame_seconds', measured=measured)
        return measured * 2

    def performance_frame_seconds(self: Self, *, measured: float, frame_seconds: float) -> float:
        self._record('performance_frame_seconds', measured=measured, frame_seconds=frame_seconds)
        return measured + frame_seconds

    def paced_frame_seconds(self: Self) -> float | None:
        self._record('paced_frame_seconds')
        return 0.25

    def hold_frame(self: Self) -> bool:
        self._record('hold_frame')
        return True

    @property
    def presents_frames(self: Self) -> bool:
        self._record('presents_frames')
        return False

    @property
    def draws_overlay(self: Self) -> bool:
        self._record('draws_overlay')
        return True

    def draw_overlay(self: Self, *, surface: pygame.Surface) -> None:
        self._record('draw_overlay', surface=surface)

    def input_snapshot(self: Self) -> object:
        self._record('input_snapshot')
        return self.snapshot

    def devices(self: Self) -> object:
        self._record('devices')
        return self.registry

    def saves(self: Self, *, namespace: str) -> object:
        self._record('saves', namespace=namespace)
        return self.store

    def wall_clock_time(self: Self) -> datetime:
        self._record('wall_clock_time')
        return self.now

    def control_events_for_frame(self: Self, *, frame_number: int) -> list[Any]:
        self._record('control_events_for_frame', frame_number=frame_number)
        return ['control']

    def end_frame(self: Self, **arguments: Any) -> None:
        self._record('end_frame', **arguments)


class TestHostSources:
    """Every door member forwards to the inner doors, arguments and answers unchanged."""

    def test_every_member_forwards_to_inner(self):
        inner = RecordingDoors()
        host = HostSources(inner=inner)  # type: ignore[arg-type]
        surface = pygame.Surface((2, 2))

        assert host.random_seed == 1234
        assert host.opened_save_namespaces == {'game': inner.store}
        assert host.captures_scene_starts is True
        assert host.stop_requested is True
        host.on_installed()
        host.on_uninstalled()
        (event,) = host.pump_events()
        assert event.marker == 'pumped'
        assert host.frame_seconds(measured=0.5) == 1.0
        assert host.performance_frame_seconds(measured=0.5, frame_seconds=0.25) == 0.75
        assert host.paced_frame_seconds() == 0.25
        assert host.hold_frame() is True
        assert host.presents_frames is False
        assert host.draws_overlay is True
        host.draw_overlay(surface=surface)
        assert host.input_snapshot() is inner.snapshot
        assert host.devices() is inner.registry
        assert host.saves(namespace='game') is inner.store
        assert host.wall_clock_time() == inner.now
        assert host.control_events_for_frame(frame_number=7) == ['control']
        host.end_frame(
            frame_number=7, dt=0.5, scene=None, control_events=[], processing_seconds=0.1
        )

        assert inner.calls == [
            ('opened_save_namespaces', {}),
            ('captures_scene_starts', {}),
            ('stop_requested', {}),
            ('on_installed', {}),
            ('on_uninstalled', {}),
            ('pump_events', {}),
            ('frame_seconds', {'measured': 0.5}),
            ('performance_frame_seconds', {'measured': 0.5, 'frame_seconds': 0.25}),
            ('paced_frame_seconds', {}),
            ('hold_frame', {}),
            ('presents_frames', {}),
            ('draws_overlay', {}),
            ('draw_overlay', {'surface': surface}),
            ('input_snapshot', {}),
            ('devices', {}),
            ('saves', {'namespace': 'game'}),
            ('wall_clock_time', {}),
            ('control_events_for_frame', {'frame_number': 7}),
            (
                'end_frame',
                {
                    'frame_number': 7,
                    'dt': 0.5,
                    'scene': None,
                    'control_events': [],
                    'processing_seconds': 0.1,
                },
            ),
        ]

    def test_first_open_save_snapshots_are_the_live_doors(self):
        """Over live doors, the recorder reads their first-open snapshots through the host."""
        live = LiveSources(random_seed=1, captures_scene_starts=True)
        host = HostSources(inner=live)

        assert host.first_open_save_snapshots == live.first_open_save_snapshots

    def test_first_open_save_snapshots_are_empty_over_other_doors(self):
        """Doors other than live ones keep no first-open snapshots."""
        host = HostSources(inner=RecordingDoors())  # type: ignore[arg-type]

        assert host.first_open_save_snapshots == MappingProxyType({})


class BatchDoors(RecordingDoors):
    """Stand-in inner doors whose next batch is given."""

    def __init__(self: Self, *, batch: list[pygame.event.Event]) -> None:
        """Serve ``batch`` from pump_events."""
        super().__init__()
        self.batch = batch

    def pump_events(self: Self) -> list[pygame.event.Event]:
        return list(self.batch)


def active_event(*, gain: int, state: int) -> pygame.event.Event:
    """Return an ACTIVEEVENT: ``gain`` 0 takes ``state`` (APP*) from the window, 1 gives it."""
    return pygame.event.Event(pygame.ACTIVEEVENT, gain=gain, state=state)


def window_event(event_type: int) -> pygame.event.Event:
    """Return a window event of ``event_type`` for the one window (``window`` None)."""
    return pygame.event.Event(event_type, window=None)


def recreated_window_events() -> list[pygame.event.Event]:
    """What one SDL window recreation queues: everything lost, then everything given back."""
    return [
        active_event(gain=0, state=pygame.APPMOUSEFOCUS),
        window_event(pygame.WINDOWLEAVE),
        active_event(gain=0, state=pygame.APPINPUTFOCUS),
        window_event(pygame.WINDOWFOCUSLOST),
        window_event(pygame.WINDOWHIDDEN),
        active_event(gain=1, state=pygame.APPMOUSEFOCUS),
        window_event(pygame.WINDOWENTER),
        active_event(gain=1, state=pygame.APPINPUTFOCUS),
        window_event(pygame.WINDOWFOCUSGAINED),
        window_event(pygame.WINDOWSHOWN),
    ]


def new_window_events() -> list[pygame.event.Event]:
    """What a new window queues: entered, focused and shown."""
    return [
        active_event(gain=1, state=pygame.APPMOUSEFOCUS),
        window_event(pygame.WINDOWENTER),
        active_event(gain=1, state=pygame.APPINPUTFOCUS),
        window_event(pygame.WINDOWFOCUSGAINED),
        window_event(pygame.WINDOWSHOWN),
    ]


def described(events: list[pygame.event.Event]) -> list[tuple[str, int | None]]:
    """Return each event's name and ACTIVEEVENT gain (None for other events), to compare batches."""
    return [(pygame.event.event_name(event.type), getattr(event, 'gain', None)) for event in events]


class TestWindowRecreationBursts:
    """A loss given back in the same batch never reaches the game (SDL recreating the window).

    A SCALED display makes SDL recreate the window when its renderer needs an OpenGL window
    (SDL 2.32.10 ``GLES2_CreateRenderer`` calls ``SDL_RecreateWindow``, which hides the window,
    destroys it and creates it again). Batches measured 2026-10-24: the browser queues one
    recreation after the new window's events, the dummy driver two.
    """

    def test_one_recreation_after_a_new_window_leaves_the_new_window(self):
        """The browser's first batch (Chromium 141 and WebKit 26, pygame-ce 2.5.7 SCALED)."""
        device = pygame.event.Event(pygame.AUDIODEVICEADDED, which=0, iscapture=0)
        motion = pygame.event.Event(pygame.MOUSEMOTION, pos=(1, 1), rel=(0, 0), buttons=(0, 0, 0))
        host = HostSources(
            inner=BatchDoors(  # type: ignore[arg-type]
                batch=[device, *new_window_events(), *recreated_window_events(), motion]
            )
        )

        assert described(host.pump_events()) == described([
            device,
            *new_window_events(),
            motion,
        ])

    def test_two_recreations_leave_the_new_window(self):
        """The dummy driver's first batch: SDL tries two OpenGL renderers before software."""
        host = HostSources(
            inner=BatchDoors(  # type: ignore[arg-type]
                batch=[*new_window_events(), *recreated_window_events(), *recreated_window_events()]
            )
        )

        assert described(host.pump_events()) == described(new_window_events())

    def test_a_loss_not_given_back_in_the_batch_reaches_the_game(self):
        lost = [
            active_event(gain=0, state=pygame.APPINPUTFOCUS),
            window_event(pygame.WINDOWFOCUSLOST),
        ]
        host = HostSources(inner=BatchDoors(batch=lost))  # type: ignore[arg-type]

        assert described(host.pump_events()) == described(lost)

    def test_a_gain_then_a_loss_both_reach_the_game(self):
        """Only a loss followed by its gain cancels out: the reverse ends the batch unfocused."""
        batch = [window_event(pygame.WINDOWFOCUSGAINED), window_event(pygame.WINDOWFOCUSLOST)]
        host = HostSources(inner=BatchDoors(batch=batch))  # type: ignore[arg-type]

        assert described(host.pump_events()) == described(batch)

    def test_a_loss_is_given_back_only_by_its_own_kind_and_window(self):
        other_window = object()
        batch = [
            window_event(pygame.WINDOWFOCUSLOST),
            window_event(pygame.WINDOWSHOWN),
            pygame.event.Event(pygame.WINDOWFOCUSGAINED, window=other_window),
            active_event(gain=0, state=pygame.APPINPUTFOCUS),
            active_event(gain=1, state=pygame.APPMOUSEFOCUS),
        ]
        host = HostSources(inner=BatchDoors(batch=batch))  # type: ignore[arg-type]

        assert described(host.pump_events()) == described(batch)

    def test_a_scaled_window_on_the_dummy_driver_never_reports_a_focus_loss(self):
        """Real pygame in a fresh process: the first batch through the host keeps no loss."""
        script = textwrap.dedent("""
            import os
            os.environ['SDL_VIDEODRIVER'] = 'dummy'
            os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
            import pygame
            from glitchygames.host import HostSources
            from glitchygames.live_sources import LiveSources
            pygame.init()
            pygame.display.set_mode((64, 48), pygame.SCALED)
            live = LiveSources(random_seed=1, captures_scene_starts=False)
            raw = []
            live_pump_events = live.pump_events
            def pump_events():
                batch = live_pump_events()
                raw.extend(pygame.event.event_name(event.type) for event in batch)
                return batch
            live.pump_events = pump_events
            host = HostSources(inner=live)
            hosted = [pygame.event.event_name(event.type) for event in host.pump_events()]
            print(raw.count('WindowFocusLost'), hosted.count('WindowFocusLost'))
            print(hosted.count('WindowFocusGained'), hosted.count('WindowShown'))
        """)
        result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - this interpreter, a fixed program
            [sys.executable, '-c', script], capture_output=True, text=True, check=True
        )

        raw_losses, *hosted_counts = result.stdout.split()
        assert int(raw_losses) > 0, 'the dummy driver no longer recreates SCALED windows'
        assert hosted_counts == ['0', '1', '1']


class TestTickPacer:
    """When the outer ticks run inner frames."""

    @staticmethod
    def frames_run(*, tick_seconds: float, period_seconds: float, ticks: int) -> list[bool]:
        pacer = TickPacer()
        return [
            pacer.should_run_frame(tick_seconds=index * tick_seconds, period_seconds=period_seconds)
            for index in range(ticks)
        ]

    def test_the_first_tick_runs_a_frame(self):
        assert TickPacer().should_run_frame(tick_seconds=12.5, period_seconds=1.0) is True

    def test_sixty_fps_on_sixty_hertz_runs_every_tick(self):
        frames = self.frames_run(
            tick_seconds=SIXTY_HERTZ_SECONDS, period_seconds=SIXTY_HERTZ_SECONDS, ticks=120
        )

        assert all(frames)

    def test_sixty_fps_on_one_hundred_twenty_hertz_runs_every_second_tick(self):
        frames = self.frames_run(
            tick_seconds=HUNDRED_TWENTY_HERTZ_SECONDS, period_seconds=SIXTY_HERTZ_SECONDS, ticks=240
        )

        assert frames == [index % 2 == 0 for index in range(240)]

    def test_sixty_fps_on_one_hundred_forty_four_hertz_averages_sixty(self):
        """144 Hz does not divide by 60: two or three ticks per frame, 60 frames a second."""
        frames = self.frames_run(
            tick_seconds=HUNDRED_FORTY_FOUR_HERTZ_SECONDS,
            period_seconds=SIXTY_HERTZ_SECONDS,
            ticks=144 * 10,
        )
        run_indices = [index for index, ran in enumerate(frames) if ran]
        gaps = {later - earlier for earlier, later in itertools.pairwise(run_indices)}

        assert abs(len(run_indices) - 600) <= 1
        assert gaps <= {2, 3}

    def test_a_target_slower_than_the_ticks_runs_on_whole_ticks(self):
        """12 FPS on 120 Hz: every tenth tick."""
        frames = self.frames_run(
            tick_seconds=HUNDRED_TWENTY_HERTZ_SECONDS, period_seconds=1 / 12, ticks=120
        )

        assert [index for index, ran in enumerate(frames) if ran] == list(range(0, 120, 10))

    def test_an_uncapped_period_runs_every_tick(self):
        frames = self.frames_run(
            tick_seconds=HUNDRED_TWENTY_HERTZ_SECONDS, period_seconds=0.0, ticks=30
        )

        assert all(frames)

    def test_a_stall_runs_one_frame_then_resumes_the_cadence(self):
        """After a one-second stall (a background tab) the cadence resumes, with no catch-up.

        60 FPS on 120 Hz runs every second tick. Without re-anchoring, the second owed would
        run a frame on every tick for about a second (the game at double speed).
        """
        pacer = TickPacer()
        tick = 0.0
        for _ in range(10):
            pacer.should_run_frame(tick_seconds=tick, period_seconds=SIXTY_HERTZ_SECONDS)
            tick += HUNDRED_TWENTY_HERTZ_SECONDS
        tick += 1.0

        after_stall = []
        for _ in range(8):
            after_stall.append(
                pacer.should_run_frame(tick_seconds=tick, period_seconds=SIXTY_HERTZ_SECONDS)
            )
            tick += HUNDRED_TWENTY_HERTZ_SECONDS

        assert after_stall == [True, False, True, False, True, False, True, False]

    def test_measured_tick_seconds_is_the_median_interval(self):
        pacer = TickPacer()
        assert pacer.measured_tick_seconds() == 0.0
        for tick in [0.0, 0.008, 0.017, 0.025, 0.100, 0.108]:
            pacer.should_run_frame(tick_seconds=tick, period_seconds=SIXTY_HERTZ_SECONDS)

        assert pacer.tick_count == 5
        assert pacer.measured_tick_seconds() == pytest.approx(0.008)


class HostedCountingScene(Scene):
    """A real scene that counts its logic frames and quits after QUIT_AFTER_FRAMES."""

    NAME = 'HostedCountingScene'
    QUIT_AFTER_FRAMES = 10

    def __init__(self) -> None:
        """Paint a background so the frames draw something."""
        super().__init__()
        self.background_color = (0, 0, 255)
        self.frames_run = 0

    def dt_tick(self, dt: float) -> None:
        """Count the frame; end the run after QUIT_AFTER_FRAMES.

        As the QUIT event's handler does (SceneManager.on_quit_event): the hosted scene manager
        here has no event managers, so a posted QUIT would never be handled.
        """
        super().dt_tick(dt)
        self.frames_run += 1
        if self.frames_run >= self.QUIT_AFTER_FRAMES:
            self.scene_manager.quit_requested = True


@pytest.fixture
def hosted_scene_manager(mocker):
    """A real scene manager running HostedCountingScene through host doors over live doors.

    Returns:
        The scene manager and its host.

    """
    mocker.patch.object(SceneManager, 'OPTIONS', SceneManager.OPTIONS)
    host = GameHost(sources=HostSources(inner=LiveSources(random_seed=7)))
    install_sources(sources=host.sources)
    manager = SceneManager()
    engine = mocker.Mock()
    engine.OPTIONS = {'update_type': 'update', 'fps_log_interval_ms': 1000, 'target_fps': 60}
    engine.timer = None
    manager.game_engine = engine
    manager.target_fps = 60
    # The stand-in engine has no event managers; every other frame step runs for real
    mocker.patch.object(manager, '_process_events', return_value=None)
    return manager, host


# More ticks than any test here needs: a run still going after this many fails instead of hanging
TICK_LIMIT = 1000


class TickLimitExceededError(AssertionError):
    """An async run took more outer ticks than TICK_LIMIT."""


def limited(ticks: list[float]) -> None:
    """Fail once ``ticks`` holds more than TICK_LIMIT ticks.

    Raises:
        TickLimitExceededError: When the limit is passed.

    """
    if len(ticks) > TICK_LIMIT:
        message = f'the run was still going after {TICK_LIMIT} ticks'
        raise TickLimitExceededError(message)


class TestGameHost:
    """The host drives the inner game's frames: blocking, or one per awaited tick."""

    def test_run_is_the_blocking_loop(self, hosted_scene_manager, mocker):
        manager, host = hosted_scene_manager
        start = mocker.spy(manager, 'start')
        scene = HostedCountingScene()
        manager.switch_to_scene(scene)

        host.run(scene_manager=manager)

        start.assert_called_once_with()
        assert scene.frames_run == HostedCountingScene.QUIT_AFTER_FRAMES

    def test_run_async_runs_a_frame_every_second_tick_at_one_hundred_twenty_hertz(
        self, hosted_scene_manager
    ):
        """60 FPS on 120 Hz ticks: ten frames take twenty ticks, then the game quits."""
        manager, host = hosted_scene_manager
        scene = HostedCountingScene()
        manager.switch_to_scene(scene)
        ticks: list[float] = []

        async def wait_for_tick() -> float:
            await asyncio.sleep(0)
            ticks.append(len(ticks) * HUNDRED_TWENTY_HERTZ_SECONDS)
            limited(ticks)
            return ticks[-1]

        asyncio.run(host.run_async(scene_manager=manager, wait_for_tick=wait_for_tick))

        assert scene.frames_run == HostedCountingScene.QUIT_AFTER_FRAMES
        # Frame 1 on tick 1, then every second tick: frame 10 on tick 19
        assert len(ticks) == 19
        assert manager.active_scene is None

    def test_run_async_logs_the_measured_tick_rate_once(self, hosted_scene_manager, mocker, caplog):
        manager, host = hosted_scene_manager
        mocker.patch.object(HostedCountingScene, 'QUIT_AFTER_FRAMES', TICKS_BEFORE_LOGGING_RATE + 5)
        manager.target_fps = 0
        manager.switch_to_scene(HostedCountingScene())
        ticks: list[float] = []

        async def wait_for_tick() -> float:
            await asyncio.sleep(0)
            ticks.append(len(ticks) * SIXTY_HERTZ_SECONDS)
            limited(ticks)
            return ticks[-1]

        with caplog.at_level(logging.INFO, logger='game.host'):
            asyncio.run(host.run_async(scene_manager=manager, wait_for_tick=wait_for_tick))

        rate_lines = [record for record in caplog.records if 'Outer ticks at' in record.message]
        assert len(rate_lines) == 1
        assert 'Outer ticks at 60.0 Hz' in rate_lines[0].message
        assert 'target 0 FPS' in rate_lines[0].message

    def test_run_async_follows_the_doors_pacing(self, hosted_scene_manager, mocker):
        """Doors that pace (a positive period) set the frame period, not the target FPS."""
        manager, host = hosted_scene_manager
        mocker.patch.object(host.sources.inner, 'paced_frame_seconds', return_value=1 / 30)
        scene = HostedCountingScene()
        manager.switch_to_scene(scene)
        ticks: list[float] = []

        async def wait_for_tick() -> float:
            await asyncio.sleep(0)
            ticks.append(len(ticks) * HUNDRED_TWENTY_HERTZ_SECONDS)
            limited(ticks)
            return ticks[-1]

        asyncio.run(host.run_async(scene_manager=manager, wait_for_tick=wait_for_tick))

        # 30 FPS on 120 Hz: every fourth tick, frame 10 on tick 37
        assert len(ticks) == 37


class RecordingOverlay:
    """An overlay that notes each frame it is asked to draw over."""

    def __init__(self) -> None:
        """Start with nothing drawn."""
        self.frames_drawn: list[int] = []

    def begin(self) -> None:
        """Nothing to start."""

    def draw(self, *, surface: pygame.Surface, frame_index: int) -> None:
        assert surface is not None
        self.frames_drawn.append(frame_index)


class TestHostOverlay:
    """An overlay (live play against OLD) is drawn over each frame, numbered as recorded."""

    def test_the_overlay_draws_over_each_frame_by_the_frames_ended(self):
        inner = RecordingDoors()
        overlay = RecordingOverlay()
        host = HostSources(inner=inner, overlay=overlay)  # type: ignore[arg-type]
        surface = pygame.Surface((2, 2))

        assert host.frames_ended == 0
        host.draw_overlay(surface=surface)
        host.end_frame(frame_number=0, dt=0.1, scene=None, control_events=[])
        host.draw_overlay(surface=surface)
        host.draw_overlay(surface=surface)
        host.end_frame(frame_number=1, dt=0.1, scene=None, control_events=[])

        assert host.frames_ended == 2
        assert overlay.frames_drawn == [0, 1, 1]
        # The inner doors' overlay is still asked for, after this one
        assert [name for name, _ in inner.calls].count('draw_overlay') == 3

    def test_an_overlay_makes_the_doors_draw_one(self):
        live = LiveSources(random_seed=1, captures_scene_starts=False)

        assert HostSources(inner=live).draws_overlay is False
        assert HostSources(inner=live, overlay=RecordingOverlay()).draws_overlay is True
