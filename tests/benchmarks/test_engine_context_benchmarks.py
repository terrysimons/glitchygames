"""What engine contexts cost per call and per read: the benchmarks and limits of Task 17's gate.

plans/2026-10-27-engine-context-2-engine-state.md: Task 16 made this module with
``READ_RATIO_LIMITS`` only; Task 17 adds the benchmarks its gate (c) measures.

- Per call (``-k per_call``): ``GameEngine.process_events`` dispatching one scripted batch and
  ``SceneManager.run_frame_step`` running one unpaced frame. They use only what exists on main
  before the plan's first task, so this file is copied into a worktree of that commit and the
  two are compared run against run (pytest-benchmark's ``--benchmark-compare``).
- Per read (``-k reading``, the branch only): an engine attribute, a slot read
  (``current_context().value(slot=...)``), a class-level read-only view (``GameEngine.OPTIONS``)
  and ``current_engine()``. A read is compared with the slot read taken in the same run, so the
  limits are ratios, not nanoseconds: heat, load or another machine move every read alike. The
  names those tests need are imported inside them: at the base commit they do not exist, and a
  top-level import would fail the file's collection there even under ``-k per_call``.

Each benchmarked function makes exactly one read, so every per-read median includes the same one
Python function call. The engine context page's "Performance" table
(docs/architecture/engine_context.md) holds these medians and is checked against
``READ_RATIO_LIMITS`` by tests/test_read_only_views.py, so the documented costs never drift past
the gate. In the normal suite (under xdist) pytest-benchmark runs each benchmark once, untimed.
"""

from __future__ import annotations

import pygame
import pytest

from glitchygames.scenes import Scene
from glitchygames.sources import install_sources
from glitchygames.testing.keys import qwerty_scancode
from tests.events.test_events_integration import ScriptedBatchSources, start_engine_with_scene

# Each read's limit, as a multiple of a slot read, by its row label in the engine context page's
# "Performance" table (about twice the ratios Task 1 measured: a view about 2.1 slot reads)
READ_RATIO_LIMITS: dict[str, float] = {'read-only view': 4.0, 'current_engine()': 2.0}


class EngineContextBenchmarkScene(Scene):
    """A real scene that counts the key presses and audio devices it is handed."""

    def __init__(self, options=None, groups=None):
        """Create the scene with nothing counted yet."""
        super().__init__(options=options, groups=groups)
        self.key_down_count = 0
        self.audio_device_added_count = 0

    def on_key_down_event(self, event):
        """Count the key press."""
        self.key_down_count += 1

    def on_audio_device_added_event(self, event):
        """Count the audio device."""
        self.audio_device_added_count += 1


class RepeatingBatchSources(ScriptedBatchSources):
    """Live doors whose every pump returns the same scripted batch (one per process_events)."""

    def __init__(self, *, batch):
        """Create the doors that return ``batch`` on every pump."""
        super().__init__(batch=batch)
        self.repeated_batch = tuple(batch)

    def pump_events(self):
        """Drain SDL's queue, then return the scripted batch.

        Returns:
            list[pygame.event.Event]: The batch.

        """
        pygame.event.get()
        return list(self.repeated_batch)


def key_down_and_audio_device_added_batch():
    """Return one batch of a KEYDOWN (the A key) and an AUDIODEVICEADDED.

    Returns:
        list[pygame.event.Event]: The batch.

    """
    return [
        pygame.event.Event(
            pygame.KEYDOWN,
            key=pygame.K_a,
            scancode=qwerty_scancode(key=pygame.K_a),
            mod=pygame.KMOD_NONE,
            unicode='a',
            window=None,
        ),
        pygame.event.Event(pygame.AUDIODEVICEADDED, which=1, iscapture=0),
    ]


def test_process_events_per_call(benchmark):
    """Benchmark the engine dispatching one batch of a key press and an audio device."""
    engine, scene = start_engine_with_scene(scene_class=EngineContextBenchmarkScene)
    install_sources(sources=RepeatingBatchSources(batch=key_down_and_audio_device_added_batch()))

    result = benchmark(engine.process_events)

    assert result is True
    assert scene.key_down_count >= 1
    assert scene.audio_device_added_count == scene.key_down_count


# Timed (--benchmark-only), pytest-benchmark calibrates its rounds from how long each takes, so
# the number of frames this test presents differs from run to run and between drivers
@pytest.mark.frames_vary(reason='the timed rounds present as many frames as calibration chooses')
def test_run_frame_step_per_call(benchmark):
    """Benchmark one unpaced frame step of the scene manager with an active scene."""
    engine, scene = start_engine_with_scene(scene_class=EngineContextBenchmarkScene)
    manager = engine.scene_manager
    frame_start = {'seconds': manager.begin_frames()}

    def run_one_frame_step():
        frame_start['seconds'] = manager.run_frame_step(
            frame_start_seconds=frame_start['seconds'], paced=False
        )

    benchmark(run_one_frame_step)

    assert manager.active_scene is scene
    assert manager.dt > 0


def test_reading_an_engine_attribute(benchmark):
    """Benchmark reading the engine's own options (``engine.options``), for the record."""
    engine, _scene = start_engine_with_scene(scene_class=EngineContextBenchmarkScene)

    def read_the_engines_options():
        return engine.options

    assert benchmark(read_the_engines_options) is engine.options


def test_reading_a_slot(benchmark):
    """Benchmark a slot read (``current_context().value(slot=...)``), the gate's reference."""
    from glitchygames.engine.game_engine import CURRENT_ENGINE_SLOT
    from glitchygames.engine_context import current_context

    engine, _scene = start_engine_with_scene(scene_class=EngineContextBenchmarkScene)

    def read_the_current_engine_slot():
        return current_context().value(slot=CURRENT_ENGINE_SLOT)

    assert benchmark(read_the_current_engine_slot).engine is engine


def test_reading_a_class_view(benchmark):
    """Benchmark a class-level read-only view (``GameEngine.OPTIONS``) with an engine running."""
    from glitchygames.engine import GameEngine

    engine, _scene = start_engine_with_scene(scene_class=EngineContextBenchmarkScene)

    def read_the_options_view():
        return GameEngine.OPTIONS

    assert benchmark(read_the_options_view) is engine.options


def test_reading_the_current_engine(benchmark):
    """Benchmark ``current_engine()`` with an engine running."""
    from glitchygames.engine import current_engine

    engine, _scene = start_engine_with_scene(scene_class=EngineContextBenchmarkScene)

    def read_the_current_engine():
        return current_engine()

    assert benchmark(read_the_current_engine) is engine
