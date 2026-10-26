"""The engine's clock exports (glitchygames/clock.py): live and replay providers."""

from __future__ import annotations

import importlib
import multiprocessing
import types
from datetime import UTC, datetime, timedelta

import pygame
import pytest

from glitchygames import clock
from glitchygames.engine_context import EngineContext
from glitchygames.input.devices import JOYSTICK_COUNT_CALL, EnumerationAnswer
from glitchygames.live_sources import LiveSources
from glitchygames.randomness import seed_engine_random
from glitchygames.replay.driver import ReplaySources
from glitchygames.sources import (
    SourcesAlreadyRunningError,
    active_sources,
    advance_frame_clock,
    has_scoped_sources,
    install_sources,
    mark_frames_started,
    notify_device_answer,
    notify_save_store_opened,
    observe_device_answers,
    observe_save_store_openings,
    pending_redelivered_events,
    push_scoped_sources,
    redeliver_events,
    reset_sources,
)
from glitchygames.state import MemorySaveManager

# Every door and clock module, each imported first and alone in a fresh interpreter: an import
# cycle between them fails here instead of at game start (layering rule, core Task 2)
DOOR_MODULES = (
    'glitchygames.sources',
    'glitchygames.clock',
    'glitchygames.live_sources',
    'glitchygames.input.state',
    'glitchygames.input.devices',
    'glitchygames.input.rumble',
    'glitchygames.state.sandbox',
    'glitchygames.state.manager',
    'glitchygames.recording',
    'glitchygames.supervision',
    'glitchygames.replay.driver',
)

# How long one import-alone child may take before it is killed and the test fails
IMPORT_ALONE_TIMEOUT_SECONDS = 60


def test_live_wall_clock_is_aware_utc_now():
    """The live wall clock is now, as a timezone-aware UTC datetime."""
    before = datetime.now(tz=UTC)
    reading = LiveSources(random_seed=1).wall_clock_time()
    after = datetime.now(tz=UTC)
    assert reading.tzinfo is UTC
    assert before <= reading <= after


def test_wall_clock_epoch_seconds_matches_wall_clock_time(mocker):
    """wall_clock_epoch_seconds() is the active wall-clock time as epoch seconds."""
    fixed = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
    mocker.patch.object(LiveSources, 'wall_clock_time', return_value=fixed)
    assert clock.wall_clock_epoch_seconds() == fixed.timestamp()


def test_live_elapsed_seconds_is_the_frame_clock():
    """Live elapsed seconds are the frame clock, so live and replayed timers read the same."""
    install_sources(sources=LiveSources(random_seed=1))
    advance_frame_clock(seconds=0.25)
    advance_frame_clock(seconds=0.5)
    assert clock.elapsed_seconds() == clock.frame_clock_seconds() == 0.75


def test_replay_elapsed_seconds_is_the_frame_clock():
    """In a replay, elapsed seconds are the frame clock too (the replayed frame times)."""
    header = {
        'game_class': 'SomeGame',
        'random_seed': 1,
        'recorded_at': '2026-10-19T12:00:00',
        'options': {},
    }
    install_sources(sources=ReplaySources(header=header, frames=[], format_version=3))
    advance_frame_clock(seconds=1.5)
    assert clock.elapsed_seconds() == clock.frame_clock_seconds() == 1.5


def test_measured_seconds_reads_monotonic_time(mocker):
    """measured_seconds() reads time.monotonic() (real time, never replayed)."""
    # Patch the module-level `time` name glitchygames.clock uses, never the global time module
    fake_time = types.SimpleNamespace(monotonic=mocker.Mock(side_effect=[10.0, 10.5]))
    mocker.patch.object(clock, 'time', fake_time)
    first = clock.measured_seconds()
    advance_frame_clock(seconds=3.0)
    second = clock.measured_seconds()
    assert second - first == 0.5


def test_frame_clock_milliseconds():
    """The frame clock in whole milliseconds, rounded half to even."""
    advance_frame_clock(seconds=1.25)
    advance_frame_clock(seconds=0.0625)
    assert clock.frame_clock_milliseconds() == 1312  # 1312.5 rounds to even


def test_frame_clock_is_the_sum_of_frame_times():
    """The frame clock adds up every closed frame's dt."""
    advance_frame_clock(seconds=0.25)
    advance_frame_clock(seconds=0.5)
    assert clock.frame_clock_seconds() == 0.75


class FixedClockSources(LiveSources):
    """Stand-in for the replay's wall-clock provider: start time + frame clock."""

    START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

    def wall_clock_time(self) -> datetime:
        """Return the fixed start plus the frame clock."""
        return self.START + timedelta(seconds=clock.frame_clock_seconds())


@pytest.mark.parametrize('module_name', DOOR_MODULES)
def test_door_module_imports_alone(module_name):
    """Each door module imports first and alone in a fresh interpreter (no import cycle).

    A spawned process starts a fresh interpreter, and its target (importlib.import_module)
    loads nothing of the package before the module under test. On failure the child's
    traceback is on stderr, which pytest captures.
    """
    spawn_context = multiprocessing.get_context('spawn')
    process = spawn_context.Process(target=importlib.import_module, args=(module_name,))
    process.start()
    process.join(timeout=IMPORT_ALONE_TIMEOUT_SECONDS)
    if process.is_alive():
        process.kill()
        process.join()
        pytest.fail(
            f'importing {module_name} alone did not finish in {IMPORT_ALONE_TIMEOUT_SECONDS} s'
        )
    assert process.exitcode == 0, f'importing {module_name} alone failed (see captured stderr)'


def test_clock_exports_read_the_active_sources():
    """Installed sources (here, a replay-like provider) serve the wall clock."""
    install_sources(sources=FixedClockSources(random_seed=1))
    advance_frame_clock(seconds=2.0)
    assert clock.wall_clock_time() == FixedClockSources.START + timedelta(seconds=2)


# Master seeds of the contexts' doors below
DEFAULT_DOORS_SEED = 11
SECOND_DOORS_SEED = 22


class HeardAnswers:
    """Keeps every save-store opening and device answer it is told of."""

    def __init__(self) -> None:
        """Start having heard nothing."""
        self.save_namespaces: list[str] = []
        self.device_answers: list[EnumerationAnswer] = []

    def on_save_store_opened(self, *, namespace, store) -> None:
        """Keep the namespace."""
        self.save_namespaces.append(namespace)

    def on_device_answer(self, *, answer, opened) -> None:
        """Keep the answer."""
        self.device_answers.append(answer)


def test_each_engine_context_has_its_own_doors_frame_clock_and_held_events():
    """Doors, frames started, the frame clock and held events are per context (audit C5)."""
    second = EngineContext(name='second')
    default_doors = LiveSources(random_seed=DEFAULT_DOORS_SEED)
    install_sources(sources=default_doors)
    advance_frame_clock(seconds=0.25)
    mark_frames_started()
    redeliver_events(events=[(pygame.event.Event(pygame.USEREVENT, code=1), 'internal')])

    with second.active():
        assert clock.frame_clock_seconds() == 0.0
        assert pending_redelivered_events() == []
        # This context's frames have not started, whatever the default context's did
        second_doors = LiveSources(random_seed=SECOND_DOORS_SEED)
        install_sources(sources=second_doors)
        push_scoped_sources(sources=FixedClockSources(random_seed=SECOND_DOORS_SEED))
        assert has_scoped_sources()
        advance_frame_clock(seconds=1.0)

    assert active_sources() is default_doors
    assert not has_scoped_sources()
    assert clock.frame_clock_seconds() == 0.25
    assert [event.code for event, _origin in pending_redelivered_events()] == [1]
    with pytest.raises(SourcesAlreadyRunningError):
        install_sources(sources=LiveSources(random_seed=DEFAULT_DOORS_SEED))
    with second.active():
        assert has_scoped_sources()
        assert clock.frame_clock_seconds() == 1.0
        reset_sources()
        assert active_sources() is not second_doors


def test_a_contexts_first_live_doors_take_that_contexts_master_seed():
    """Review Focus 5: doors made on first use read the master seed of their own context."""
    second = EngineContext(name='second')
    seed_engine_random(seed=DEFAULT_DOORS_SEED)

    with second.active():
        seed_engine_random(seed=SECOND_DOORS_SEED)
        assert active_sources().random_seed == SECOND_DOORS_SEED
        reset_sources()

    assert active_sources().random_seed == DEFAULT_DOORS_SEED


def test_observers_hear_only_their_own_contexts_openings_and_answers():
    """A save-store or device-answer observer is told only of its own context's."""
    second = EngineContext(name='second')
    heard = HeardAnswers()
    observe_save_store_openings(observer=heard)
    observe_device_answers(observer=heard)
    answer = EnumerationAnswer(call=JOYSTICK_COUNT_CALL, device_index=None, value=1)

    with second.active():
        notify_save_store_opened(
            namespace='second-game', store=MemorySaveManager(app_name='second-game', snapshot={})
        )
        notify_device_answer(answer=answer, opened=None)
    notify_save_store_opened(
        namespace='default-game', store=MemorySaveManager(app_name='default-game', snapshot={})
    )
    notify_device_answer(answer=answer, opened=None)

    assert heard.save_namespaces == ['default-game']
    assert heard.device_answers == [answer]
