"""SceneManager._finish_frame(): one start-to-start frame time per frame (engine audit #15).

Every frame ends in ``_finish_frame``: it paces with the timer backend (or the pygame clock),
then reads ``time.perf_counter()`` once. That reading ends this frame and starts the next, and
``self.dt`` is set once, to the full start-to-start period. Logic in the next frame, the FPS
statistics and the debug overlay all see that one value.

The loop runs on a fake clock: the perf counter, the timer backend's clock, the frame's work
and the pacing sleep all move the same fake time, in steps that are exact binary fractions
(1/64 s periods, 1/256 s of work, 1/512 s per clock reading, all whole nanoseconds), so sums
can be compared exactly.
Nothing waits on the wall clock.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Self, override

import pygame
import pytest

from glitchygames.scenes import SceneManager

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from pytest_mock import MockerFixture

NANOSECONDS_PER_SECOND = 1_000_000_000
CLOCK_START_SECONDS = 100.0
# Every perf_counter() reading takes a little fake time, as reading a real clock does
CLOCK_READING_SECONDS = 1 / 512
FRAME_WORK_SECONDS = 1 / 256
# 64 FPS: a period of exactly 15_625_000 ns (1/64 s), so every deadline is an exact binary fraction
EXACT_TARGET_FPS = 64.0
EXACT_PERIOD_NS = 15_625_000
HITCH_SECONDS = 2.0
FRAMES_TO_RUN = 10
FPS_LOG_INTERVAL_MS = 1000


class FakeClock:
    """One fake time source for the perf counter and the timer backend's clock."""

    def __init__(self) -> None:
        """Start the clock at CLOCK_START_SECONDS."""
        self.seconds = CLOCK_START_SECONDS

    def perf_counter(self) -> float:
        """Return the current time; every reading advances the clock by CLOCK_READING_SECONDS.

        Returns:
            The fake time in seconds.

        """
        reading = self.seconds
        self.seconds += CLOCK_READING_SECONDS
        return reading

    def advance(self, *, seconds: float) -> None:
        """Let fake time pass (the frame's work).

        Args:
            seconds: How long to advance the clock.

        """
        self.seconds += seconds


class FakeTimer:
    """A timer backend on the fake clock: sleeping moves the clock to the deadline."""

    def __init__(self, *, clock: FakeClock) -> None:
        """Create the timer on a fake clock.

        Args:
            clock: The fake clock the timer reads and advances.

        """
        self.clock = clock
        self.start_frame_targets: list[float] = []
        self.compute_deadline_calls: list[tuple[int | None, int]] = []
        self.sleep_deadlines: list[int] = []

    def ns_now(self) -> int:
        """Return the fake time in nanoseconds (without advancing it).

        Returns:
            The fake time in nanoseconds.

        """
        return round(self.clock.seconds * NANOSECONDS_PER_SECOND)

    def start_frame(self, target_fps: float) -> int:
        """Return the frame period, rounded as the real timer backends do.

        Returns:
            The frame period in nanoseconds (0 when the target is not positive).

        """
        self.start_frame_targets.append(target_fps)
        if target_fps > 0:
            return round(NANOSECONDS_PER_SECOND / target_fps)
        return 0

    def compute_deadline(self, prev_deadline_ns: int | None, period_ns: int) -> int:
        """Compute the next deadline as the real timer backends do, recording the call.

        Returns:
            The deadline in nanoseconds.

        """
        self.compute_deadline_calls.append((prev_deadline_ns, period_ns))
        if prev_deadline_ns is None:
            return self.ns_now() + period_ns
        return prev_deadline_ns + period_ns

    def sleep_until_next(self, deadline_ns: int) -> int:
        """Sleep (advance the fake clock) until the deadline, unless it has passed.

        Returns:
            The fake time in nanoseconds after sleeping.

        """
        self.sleep_deadlines.append(deadline_ns)
        deadline_seconds = deadline_ns / NANOSECONDS_PER_SECOND
        self.clock.seconds = max(self.clock.seconds, deadline_seconds)
        return self.ns_now()


class DtWriteRecordingSceneManager(SceneManager):
    """A SceneManager that records every write to ``dt`` in ``dt_writes``."""

    dt_writes: list[float]

    @override
    def __setattr__(self: Self, name: str, value: object) -> None:
        """Record writes to dt, then set the attribute as usual.

        Args:
            name: The attribute name.
            value: The new value.

        """
        if name == 'dt':
            self.__dict__.setdefault('dt_writes', []).append(value)
        super().__setattr__(name, value)


class FrameDriver:
    """Runs SceneManager.start() on the fake clock for a fixed number of frames."""

    def __init__(
        self,
        *,
        mocker: MockerFixture,
        target_fps: float,
        use_timer: bool = True,
        log_timer_jitter: bool = False,
    ) -> None:
        """Build the manager, the fake clock and timer, and the performance-manager spy.

        Args:
            mocker: The pytest-mock fixture.
            target_fps: The manager's target FPS.
            use_timer: Whether the engine has a timer backend.
            log_timer_jitter: The --log-timer-jitter option.

        """
        self.clock = FakeClock()
        self.timer = FakeTimer(clock=self.clock)
        mocker.patch(
            'glitchygames.scenes.scene.time', SimpleNamespace(perf_counter=self.clock.perf_counter)
        )
        mocker.patch.object(
            SceneManager,
            'OPTIONS',
            {'fps_log_interval_ms': FPS_LOG_INTERVAL_MS, 'log_timer_jitter': log_timer_jitter},
        )
        self.performance_manager = mocker.Mock()
        mocker.patch(
            'glitchygames.performance.performance_manager', self.performance_manager, create=True
        )
        self.post_event = mocker.patch('glitchygames.scenes.scene.post_event')

        self.mocker = mocker
        self.manager = DtWriteRecordingSceneManager()
        self.manager.target_fps = target_fps
        self.manager._game_engine = mocker.Mock(
            timer=self.timer if use_timer else None, controller_manager=None
        )
        # A scene stand-in without a camera, so the engine's camera steps are skipped
        self.manager.active_scene = mocker.Mock(camera=None)
        self.manager.clock = mocker.Mock()
        # terminate() switches to no scene, which resets dt after the loop; only the loop counts
        mocker.patch.object(self.manager, 'terminate')
        self.logic_dts: list[float] = []
        self.dt_writes_at_frame_start: list[int] = []
        self.frame_work_seconds: list[float] = []

    def run(
        self,
        *,
        frame_count: int,
        frame_body: Callable[[], None] | None = None,
        work_seconds: Callable[[int], float] | None = None,
    ) -> None:
        """Run frames until frame_count have run.

        Args:
            frame_count: How many frames to run.
            frame_body: Replaces _run_scene_frame (the default does nothing but the work).
            work_seconds: Fake seconds of work for each frame index (FRAME_WORK_SECONDS).

        """
        manager = self.manager

        def run_scene_frame() -> None:
            frame_index = len(self.logic_dts)
            self.logic_dts.append(manager.dt)
            self.dt_writes_at_frame_start.append(len(manager.dt_writes))
            seconds = FRAME_WORK_SECONDS if work_seconds is None else work_seconds(frame_index)
            self.clock.advance(seconds=seconds)
            if frame_body is not None:
                frame_body()
            if len(self.logic_dts) >= frame_count:
                manager.quit_requested = True

        self.mocker.patch.object(manager, '_run_scene_frame', side_effect=run_scene_frame)
        manager.dt_writes = []
        manager.start()

    def fps_samples(self) -> list[float]:
        """Return the FPS values recorded by the performance manager, in order.

        Returns:
            The recorded FPS values.

        """
        return [
            call.args[0] for call in self.performance_manager.track_fps_from_event.call_args_list
        ]

    def processing_samples(self) -> list[float]:
        """Return the processing times recorded by the performance manager, in order.

        Returns:
            The recorded processing times in seconds.

        """
        return [
            call.args[1] for call in self.performance_manager.track_fps_from_event.call_args_list
        ]


@pytest.fixture
def driver_factory(mocker: MockerFixture) -> Generator[Callable[..., FrameDriver]]:
    """Make FrameDrivers, resetting the recording manager's singleton around the test.

    Yields:
        A factory taking FrameDriver's keyword arguments (target_fps, use_timer).

    """
    DtWriteRecordingSceneManager._reset()

    def make_driver(**keyword_arguments: Any) -> FrameDriver:
        return FrameDriver(mocker=mocker, **keyword_arguments)

    yield make_driver
    DtWriteRecordingSceneManager._reset()


def _closing_samples(driver: FrameDriver) -> list[float]:
    """Return each frame's closing dt (every write after the one before the loop).

    Returns:
        The frame times set by _finish_frame, one per frame.

    """
    return driver.manager.dt_writes[1:]


class TestOneFrameTime:
    """One start-to-start frame time per frame, seen by logic, statistics and the overlay."""

    def test_recorded_frames_sum_exactly_to_elapsed_time(self, driver_factory):
        """Over 10 frames the recorded samples sum to the time from start() to the last close."""
        driver = driver_factory(target_fps=EXACT_TARGET_FPS)

        driver.run(frame_count=FRAMES_TO_RUN)

        samples = _closing_samples(driver)
        assert len(samples) == FRAMES_TO_RUN
        # start() read the clock first at CLOCK_START_SECONDS; the last frame's closing reading
        # was the last one taken (the clock has moved one reading past it since)
        last_closing_reading = driver.clock.seconds - CLOCK_READING_SECONDS
        assert sum(samples) == last_closing_reading - CLOCK_START_SECONDS
        # The FPS statistics recorded exactly these samples (1 / frame time)
        assert driver.fps_samples() == pytest.approx([1.0 / sample for sample in samples])
        # Paced at 64 FPS, every frame after the first lasts exactly one period
        assert samples[1:] == [EXACT_PERIOD_NS / NANOSECONDS_PER_SECOND] * (FRAMES_TO_RUN - 1)

    def test_logic_sees_the_previous_frames_recorded_sample(self, driver_factory):
        """Logic's dt in frame N is the sample frame N-1 closed with."""
        driver = driver_factory(target_fps=EXACT_TARGET_FPS)

        driver.run(frame_count=FRAMES_TO_RUN)

        samples = _closing_samples(driver)
        assert driver.logic_dts[1:] == samples[:-1]

    def test_first_frame_dt_is_the_short_time_before_the_loop(self, driver_factory):
        """The first frame's dt is the time between start()'s two readings, as today."""
        driver = driver_factory(target_fps=EXACT_TARGET_FPS)

        driver.run(frame_count=1)

        assert driver.logic_dts == [CLOCK_READING_SECONDS]

    def test_dt_is_written_exactly_once_per_frame(self, driver_factory):
        """One write before the loop (the first frame's dt), then one per frame."""
        driver = driver_factory(target_fps=EXACT_TARGET_FPS)

        driver.run(frame_count=FRAMES_TO_RUN)

        assert len(driver.manager.dt_writes) == FRAMES_TO_RUN + 1
        # Each frame body starts after exactly one more write than the frame before it
        assert driver.dt_writes_at_frame_start == list(range(1, FRAMES_TO_RUN + 1))

    def test_dt_is_written_once_in_a_frame_that_switches_scenes(self, driver_factory, mocker):
        """A scene switch seeds the new scene's dt without writing the manager's dt."""
        driver = driver_factory(target_fps=EXACT_TARGET_FPS)
        manager = driver.manager
        switch_frame_index = 3
        # A scene stand-in without a camera, so the engine's camera steps are skipped
        next_scene = mocker.Mock(camera=None)
        next_scene.dt = 0.5
        # The switch redraws the new scene's background onto the display
        next_scene.background = pygame.Surface((1, 1))

        def switch_in_one_frame() -> None:
            if len(driver.logic_dts) == switch_frame_index + 1:
                manager.switch_to_scene(next_scene)

        driver.run(frame_count=FRAMES_TO_RUN, frame_body=switch_in_one_frame)

        assert manager.active_scene is next_scene
        assert len(manager.dt_writes) == FRAMES_TO_RUN + 1
        assert driver.dt_writes_at_frame_start == list(range(1, FRAMES_TO_RUN + 1))
        # The new scene starts from a zero dt, as before; its first frame gets the real one
        assert next_scene.dt == 0.0
        assert (
            driver.logic_dts[switch_frame_index + 1] == _closing_samples(driver)[switch_frame_index]
        )

    def test_jitter_is_logged_with_the_deadline_and_wake_time(self, driver_factory, mocker):
        """With --log-timer-jitter, each paced frame logs its wake time against its deadline."""
        driver = driver_factory(target_fps=EXACT_TARGET_FPS, log_timer_jitter=True)
        log_jitter_stats = mocker.patch.object(driver.manager, '_log_jitter_stats')

        driver.run(frame_count=3)

        # The fake timer wakes exactly at each deadline
        assert [call.args for call in log_jitter_stats.call_args_list] == [
            (driver.timer, deadline_ns, deadline_ns) for deadline_ns in driver.timer.sleep_deadlines
        ]
        assert len(driver.timer.sleep_deadlines) == 3

    def test_processing_time_excludes_the_pacing_sleep(self, driver_factory):
        """The processing time given to the statistics is the frame's work, not its sleep."""
        driver = driver_factory(target_fps=EXACT_TARGET_FPS)

        driver.run(frame_count=FRAMES_TO_RUN)

        # The work plus the time of the previous close's own reading; the sleep never counts.
        # The first frame started at start()'s first reading, one reading earlier.
        processing_samples = driver.processing_samples()
        assert processing_samples[0] == 2 * CLOCK_READING_SECONDS + FRAME_WORK_SECONDS
        assert processing_samples[1:] == [CLOCK_READING_SECONDS + FRAME_WORK_SECONDS] * (
            FRAMES_TO_RUN - 1
        )

    def test_fps_event_reports_the_frame_just_closed(self, driver_factory):
        """FPSEVENT still fires on its wall-clock interval, reporting 1 / the closed frame."""
        driver = driver_factory(target_fps=EXACT_TARGET_FPS)
        # 1000 ms log interval: an event at least every 500 ms; 64 frames span one second
        frames_per_second = round(EXACT_TARGET_FPS)

        driver.run(frame_count=frames_per_second)

        posted_fps = [call.args[0].fps for call in driver.post_event.call_args_list]
        assert len(posted_fps) == 2
        assert posted_fps == pytest.approx([EXACT_TARGET_FPS, EXACT_TARGET_FPS])


class TestPacing:
    """Pacing uses the timer backend's clock and period, as before."""

    def test_fractional_target_paces_with_the_untruncated_period(self, driver_factory):
        """Target 60.01 FPS computes deadlines with round(1e9 / 60.01) ns."""
        driver = driver_factory(target_fps=60.01)

        driver.run(frame_count=3)

        expected_period_ns = round(NANOSECONDS_PER_SECOND / 60.01)
        assert driver.timer.start_frame_targets == [60.01, 60.01, 60.01]
        assert [period for _, period in driver.timer.compute_deadline_calls] == [
            expected_period_ns
        ] * 3
        # Each deadline follows on from the previous one (the timer's own clock)
        previous_deadlines = [previous for previous, _ in driver.timer.compute_deadline_calls]
        assert previous_deadlines[0] is None
        assert previous_deadlines[1:] == driver.timer.sleep_deadlines[:-1]

    def test_uncapped_target_never_sleeps(self, driver_factory):
        """Target 0 FPS never calls sleep_until_next; the clock ticks without a limit."""
        driver = driver_factory(target_fps=0.0)

        driver.run(frame_count=FRAMES_TO_RUN)

        assert driver.timer.sleep_deadlines == []
        assert driver.timer.compute_deadline_calls == []
        assert driver.manager.clock.tick.call_count == FRAMES_TO_RUN
        for tick_call in driver.manager.clock.tick.call_args_list:
            assert tick_call.args == ()
        # Uncapped frames are still measured start to start: the start reading, the work and
        # the processing reading (the first frame also spans start()'s second reading)
        samples = _closing_samples(driver)
        assert samples[0] == 3 * CLOCK_READING_SECONDS + FRAME_WORK_SECONDS
        assert samples[1:] == [2 * CLOCK_READING_SECONDS + FRAME_WORK_SECONDS] * (FRAMES_TO_RUN - 1)

    def test_no_timer_backend_paces_with_the_pygame_clock(self, driver_factory):
        """Without a timer backend, the pygame clock paces at the target FPS."""
        driver = driver_factory(target_fps=60.01, use_timer=False)

        driver.run(frame_count=3)

        assert [tick_call.args for tick_call in driver.manager.clock.tick.call_args_list] == [
            (60.01,)
        ] * 3
        assert len(_closing_samples(driver)) == 3

    def test_hitch_records_one_long_frame(self, driver_factory):
        """A 2 s hitch is one 2 s sample; the next deadline comes from compute_deadline."""
        driver = driver_factory(target_fps=EXACT_TARGET_FPS)
        hitch_frame_index = 4

        def work_seconds(frame_index: int) -> float:
            return HITCH_SECONDS if frame_index == hitch_frame_index else FRAME_WORK_SECONDS

        driver.run(frame_count=FRAMES_TO_RUN, work_seconds=work_seconds)

        samples = _closing_samples(driver)
        # The hitch frame: the start reading, 2 s of work, the processing reading, no sleep (its
        # deadline has passed), then the close
        assert samples[hitch_frame_index] == 2 * CLOCK_READING_SECONDS + HITCH_SECONDS
        assert [sample for sample in samples if sample > 1.0] == [samples[hitch_frame_index]]
        # Logic in the next frame receives the whole hitch as one dt
        assert driver.logic_dts[hitch_frame_index + 1] == samples[hitch_frame_index]
        # The following frame's deadline is computed by the timer backend from the hitch
        # frame's deadline, exactly as before (pacing policy belongs to the timer backend)
        hitch_deadline = driver.timer.sleep_deadlines[hitch_frame_index]
        assert driver.timer.compute_deadline_calls[hitch_frame_index + 1] == (
            hitch_deadline,
            EXACT_PERIOD_NS,
        )


class TestTransitionFrames:
    """The transition branch ends in _finish_frame too."""

    def test_transition_frames_are_paced_and_recorded_like_scene_frames(
        self, driver_factory, mocker
    ):
        """Transition frames are paced and measured start to start, like scene frames."""
        driver = driver_factory(target_fps=EXACT_TARGET_FPS)
        manager = driver.manager
        transition_dts: list[float] = []

        class FakeTransition:
            def update(self, dt: float) -> bool:
                transition_dts.append(dt)
                driver.clock.advance(seconds=FRAME_WORK_SECONDS)
                if len(transition_dts) >= FRAMES_TO_RUN:
                    manager.quit_requested = True
                return False

            def render(self, screen: object) -> None:
                """Draw nothing."""

        mocker.patch.object(manager, '_process_transition_events')
        mocker.patch.object(manager, '_update_frame_services')
        mocker.patch.object(manager, '_present_frame')
        manager._active_transition = FakeTransition()
        manager.dt_writes = []

        manager.start()

        samples = manager.dt_writes[1:]
        assert len(samples) == FRAMES_TO_RUN
        assert len(driver.timer.sleep_deadlines) == FRAMES_TO_RUN
        assert samples[1:] == [EXACT_PERIOD_NS / NANOSECONDS_PER_SECOND] * (FRAMES_TO_RUN - 1)
        assert transition_dts[1:] == samples[:-1]
        assert driver.fps_samples() == pytest.approx([1.0 / sample for sample in samples])


class TestFrameServicesSeeTheSameFrameTime:
    """The debug overlay and the trace recorder record the frame time logic received."""

    def test_debug_overlay_history_matches_the_performance_samples(self, driver_factory):
        """The overlay records, in frame N, the sample the statistics recorded for frame N-1."""
        driver = driver_factory(target_fps=EXACT_TARGET_FPS)
        manager = driver.manager

        driver.run(frame_count=FRAMES_TO_RUN, frame_body=manager._update_frame_services)

        samples = _closing_samples(driver)
        overlay_history = manager.debug_overlay.frame_times()
        # The first entry is the first frame's short dt; the rest are the closed frames
        assert overlay_history == [CLOCK_READING_SECONDS, *samples[:-1]]
        assert [1.0 / fps for fps in driver.fps_samples()[:-1]] == pytest.approx(
            overlay_history[1:]
        )

    def test_trace_recorder_gets_the_dt_logic_received_once_per_frame(self, driver_factory, mocker):
        """The --record-trace recorder writes one line per frame with logic's dt."""
        driver = driver_factory(target_fps=EXACT_TARGET_FPS)
        recorder = mocker.Mock()
        driver.manager.trace_recorder = recorder

        driver.run(frame_count=FRAMES_TO_RUN)

        recorded_dts = [call.kwargs['dt'] for call in recorder.record_frame.call_args_list]
        assert recorded_dts == driver.logic_dts
        assert len(recorded_dts) == FRAMES_TO_RUN


SCENE_FRAME_CAP_SECONDS = 0.05


class CappedSceneStandIn:
    """A scene stand-in with MAX_FRAME_SECONDS, a following camera and recorded logic dts."""

    MAX_FRAME_SECONDS = SCENE_FRAME_CAP_SECONDS

    def __init__(self) -> None:
        """Create the camera (following a still target) and an empty sprite group."""
        from glitchygames.camera import Camera2D

        self.camera = Camera2D(screen_width=800, screen_height=480)
        self.target = SimpleNamespace(world_x=500.0, world_y=300.0)
        self.camera.follow(target=self.target)
        self.all_sprites: list[object] = []
        self.logic_dts: list[float] = []

    def dt_tick(self, dt: float) -> None:
        """Record the dt logic received."""
        self.logic_dts.append(dt)

    def camera_target(self) -> tuple[float, float]:
        """Aim at the target, as Scene.camera_target does for a follow target.

        Returns:
            The target's world position.

        """
        return (self.target.world_x, self.target.world_y)


class TestSceneFrameCap:
    """Scene.MAX_FRAME_SECONDS caps the dt logic and the camera aim receive, nothing else."""

    def test_hitch_caps_logic_and_camera_but_records_one_long_frame(self, driver_factory, mocker):
        driver = driver_factory(target_fps=EXACT_TARGET_FPS)
        manager = driver.manager
        scene = CappedSceneStandIn()
        manager.active_scene = scene
        aim_spy = mocker.spy(scene.camera, 'aim_at')
        for frame_step in ('update_screen', '_render_scene', '_present_frame'):
            mocker.patch.object(manager, frame_step)
        mocker.patch.object(manager, '_switch_to_requested_scene')
        hitch_frame_index = 4

        def work_seconds(frame_index: int) -> float:
            return HITCH_SECONDS if frame_index == hitch_frame_index else FRAME_WORK_SECONDS

        driver.run(
            frame_count=FRAMES_TO_RUN,
            frame_body=lambda: SceneManager._run_scene_frame(manager),
            work_seconds=work_seconds,
        )

        samples = _closing_samples(driver)
        hitch_sample = samples[hitch_frame_index]
        # The hitch is still one long recorded frame: FPS statistics and the overlay see 2 s
        assert hitch_sample == 2 * CLOCK_READING_SECONDS + HITCH_SECONDS
        assert driver.fps_samples()[hitch_frame_index] == pytest.approx(1.0 / hitch_sample)
        assert manager.debug_overlay.frame_times()[hitch_frame_index + 1] == hitch_sample
        assert driver.logic_dts[hitch_frame_index + 1] == hitch_sample  # the manager's raw dt
        # Logic and the camera aim in the next frame both receive the cap
        aim_dts = [call.kwargs['dt'] for call in aim_spy.call_args_list]
        assert scene.logic_dts[hitch_frame_index + 1] == SCENE_FRAME_CAP_SECONDS
        assert aim_dts[hitch_frame_index + 1] == SCENE_FRAME_CAP_SECONDS
        # Frames under the cap pass through unchanged
        assert scene.logic_dts[: hitch_frame_index + 1] == driver.logic_dts[: hitch_frame_index + 1]
        assert aim_dts == scene.logic_dts

    def test_scene_without_a_cap_receives_the_raw_dt(self, driver_factory, mocker):
        driver = driver_factory(target_fps=EXACT_TARGET_FPS)
        manager = driver.manager
        scene = CappedSceneStandIn()
        scene.MAX_FRAME_SECONDS = None
        manager.active_scene = scene
        for frame_step in ('update_screen', '_render_scene', '_present_frame'):
            mocker.patch.object(manager, frame_step)
        mocker.patch.object(manager, '_switch_to_requested_scene')

        driver.run(
            frame_count=FRAMES_TO_RUN,
            frame_body=lambda: SceneManager._run_scene_frame(manager),
            work_seconds=lambda frame_index: HITCH_SECONDS if frame_index == 2 else 0.0,
        )

        assert scene.logic_dts == driver.logic_dts

    def test_scene_default_has_no_cap(self):
        from glitchygames.scenes import Scene

        assert Scene.MAX_FRAME_SECONDS is None
