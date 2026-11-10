"""When SDL_mixer's mixer thread runs relative to the game: the steal's ordering on the device.

Impl spec 7.1's question (risk R4), measured through SDL's disk audio driver with
tests/audio/channel_fade_probe.py and tests/audio/channel_fade_analysis.py: does ``Channel.play``
straight after ``Channel.fadeout(10)`` cut the fade, and does the voice table's one-frame wait
put the stealer after the fade? Both answers depend on real-time scheduling: whether ``fadeout``
and ``play`` land in the same 512-frame mixer chunk, and whether a frame's wait (16.7 ms) spans a
chunk (11.6 ms). Under heavy load (xdist beside the native run, a one-CPU CI) those relations can
flip, so the tests run only under ``--benchmark-only`` (ruling R44; as
tests/benchmarks/test_logging_cost.py, ``nox -s performance-test``) and are skipped otherwise.
What holds under any load (where levels change, the plateaus, the unmet smoothness criterion)
stays in the normal suite, tests/audio/test_channel_fades.py.

Measured 2026-11-02 (pygame-ce 2.5.8, SDL 2.32.10, SDL_mixer 2.8.2): ``play`` at once replaces
the fading sound at the next chunk (worst step 10.3 times the tone's own), so the voice table
keeps its one-frame delayed play; with the wait, the stealer starts after the fade's first chunk.
"""

from __future__ import annotations

import numpy as np
import pytest

from tests.audio.channel_fade_analysis import (
    ABSENT_LEVEL,
    DISCONTINUITY_THRESHOLD,
    MINIMUM_DELAYED_STEAL_TRIALS,
    action_chunk,
    chunk_levels,
    delayed_steal_trials,
    recording_directory,
    shared_recording,
    trial_chunks,
    worst_step_ratio,
)
from tests.audio.channel_fade_probe import (
    STEAL_DELAYED,
    STEAL_IMMEDIATE,
    STEALER_TONE_HZ,
    STOLEN_TONE_HZ,
    TRIAL_COUNT,
)

SKIP_REASON = 'depends on real-time scheduling of the mixer thread: run with --benchmark-only'


def recorded(case: str, *, benchmark, request, tmp_path_factory) -> np.ndarray:
    """Record a case under the benchmark (once), or skip outside ``--benchmark-only``.

    Returns:
        The recording's left channel.
    """
    if not request.config.getoption('benchmark_only'):
        pytest.skip(SKIP_REASON)
    directory = recording_directory(tmp_path_factory.getbasetemp())
    return benchmark.pedantic(shared_recording, args=(case, directory), rounds=1, iterations=1)


def test_fadeout_then_play_at_once_cuts_the_stolen_voice(benchmark, request, tmp_path_factory):
    """Impl spec 7.1's open question, answered: ``play`` right after ``fadeout(10)`` cuts the fade.

    ``play`` on a channel straight after its ``fadeout(10)`` replaces the fading sound at the
    next chunk, so the fade is never heard. In every trial the chunk where the stolen tone
    leaves full level already holds the stealer (and no stolen tone), and the switch steps far
    above the metric. The voice table therefore keeps its one-frame delayed play
    (src/glitchygames/audio/voices.py).
    """
    samples = recorded(
        STEAL_IMMEDIATE, benchmark=benchmark, request=request, tmp_path_factory=tmp_path_factory
    )
    stolen = chunk_levels(samples, frequency=STOLEN_TONE_HZ)
    stealer = chunk_levels(samples, frequency=STEALER_TONE_HZ)
    recorded_trials = trial_chunks(samples)

    assert len(recorded_trials) == TRIAL_COUNT
    for chunks in recorded_trials:
        first_changed = action_chunk(stolen, chunks)
        assert stolen[first_changed] <= ABSENT_LEVEL
        assert stealer[first_changed] > ABSENT_LEVEL
    assert worst_step_ratio(samples, case=STEAL_IMMEDIATE) > DISCONTINUITY_THRESHOLD


def test_a_delayed_steal_starts_the_stealer_after_the_fades_first_chunk(
    benchmark, request, tmp_path_factory
):
    """The voice table's delayed play: the stealer starts only after the fade's first chunk.

    In most trials the first chunk below the stolen tone's full level (a plateau of the 10 ms
    fade, or the halt) holds no stealer: a late mixer thread can put both calls before one chunk
    in a trial, which one late wake-up must not fail, while a delay that stopped working shows in
    all of them. In every trial the stealer sounds from that chunk on.
    """
    samples = recorded(
        STEAL_DELAYED, benchmark=benchmark, request=request, tmp_path_factory=tmp_path_factory
    )
    stolen = chunk_levels(samples, frequency=STOLEN_TONE_HZ)
    stealer = chunk_levels(samples, frequency=STEALER_TONE_HZ)
    recorded_trials = trial_chunks(samples)

    assert len(recorded_trials) == TRIAL_COUNT
    for chunks in recorded_trials:
        first_changed = action_chunk(stolen, chunks)
        assert np.any(stealer[first_changed : chunks.stop] > ABSENT_LEVEL)
    delayed = delayed_steal_trials(stolen=stolen, stealer=stealer, recorded_trials=recorded_trials)
    assert delayed >= MINIMUM_DELAYED_STEAL_TRIALS
