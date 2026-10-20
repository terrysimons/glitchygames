"""The engine's clock exports (glitchygames/clock.py): live and replay providers."""

from __future__ import annotations

import importlib
import multiprocessing
import types
from datetime import UTC, datetime, timedelta

import pytest

from glitchygames import clock
from glitchygames import live_sources as live_sources_module
from glitchygames.live_sources import LiveSources
from glitchygames.sources import advance_frame_clock, install_sources

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
)


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


def test_live_elapsed_seconds_reads_monotonic_time(mocker):
    """Live elapsed seconds come from time.monotonic()."""
    # Patch the module-level `time` name live_sources uses, never the global time module
    fake_time = types.SimpleNamespace(monotonic=mocker.Mock(side_effect=[10.0, 10.5]))
    mocker.patch.object(live_sources_module, 'time', fake_time)
    first = clock.elapsed_seconds()
    second = clock.elapsed_seconds()
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
    """Stand-in for the replay providers Task 12 writes: start time + frame clock."""

    START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

    def wall_clock_time(self) -> datetime:
        """Return the fixed start plus the frame clock."""
        return self.START + timedelta(seconds=clock.frame_clock_seconds())

    def elapsed_seconds(self) -> float:
        """Return the frame clock."""
        return clock.frame_clock_seconds()


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
    process.join(timeout=60)
    assert process.exitcode == 0, f'importing {module_name} alone failed (see captured stderr)'


def test_clock_exports_read_the_active_sources():
    """Installed sources (here, replay-like providers) serve the clock exports."""
    install_sources(sources=FixedClockSources(random_seed=1))
    advance_frame_clock(seconds=2.0)
    assert clock.wall_clock_time() == FixedClockSources.START + timedelta(seconds=2)
    assert clock.elapsed_seconds() == pytest.approx(2.0)
