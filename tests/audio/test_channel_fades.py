"""SDL_mixer's channel fades, recorded through SDL's disk audio driver (M1's verification).

The implementation spec leaves three channel behaviours open until they are measured: whether
``Channel.play`` straight after ``Channel.fadeout(10)`` on the same channel cuts the steal's fade
(impl spec 7.1, risk R4), whether a bus or volume fade stepped once per frame over 50 ms steps
audibly (7.2, risk R5), and what the CRT skip's ``Channel.fadeout(20)`` does on the device
(10.1, AUD-CRT-003). Each is played by tests/audio/channel_fade_probe.py in a child process on
the disk driver (as scripts/audio_glitch_probe.py's ``dsp`` mode records), and the recording is
measured here with feature spec 16.1's discontinuity metric: the largest sample-to-sample step,
relative to the largest step of the tones themselves. At or below 1 the change is smooth.

What the recordings show (2026-11-02, pygame-ce 2.5.8, SDL 2.32.10, SDL_mixer 2.8.2): SDL_mixer
changes a channel's level only between mixer chunks (512 frames, 11.6 ms). A fade of 10 or
20 ms is at most one or two plateaus and then a halt, a per-frame gain step is a step at the
next chunk, and ``Channel.play`` on a fading channel replaces the fading sound at the next chunk
(the fade is never heard). None of them meets the metric; the criteria that are not met are
strict xfails below, so a mixer that starts ramping inside a chunk shows up as an XPASS.

The recordings are real time (the disk driver sleeps a buffer's length per chunk), but nothing
here asserts on time: only on the recorded samples, with several trials per recording so a
result never rests on one phase of the tone, and only what holds however the machine is loaded
(where a level changes, which levels a fade passes through, how many plateaus a fade has). What
depends on when the mixer thread runs (whether ``play`` lands in the fading chunk, whether a
frame's wait spans a chunk) is in tests/benchmarks/test_channel_fade_relations.py, run only under
``--benchmark-only`` (ruling R44). Each recording is made once per run, shared by the xdist
workers (tests/audio/channel_fade_analysis.py).
"""

from __future__ import annotations

import numpy as np
import pytest

from glitchygames.audio.diagnostics import DEFAULT_BUFFER_SAMPLES, find_discontinuities
from tests.audio.channel_fade_analysis import (
    BUS_FADE_GAINS,
    DISCONTINUITY_THRESHOLD,
    LEVEL_TOLERANCE,
    MAXIMUM_CRT_FADE_PLATEAUS,
    action_chunk,
    chunk_levels,
    levels_after_the_action,
    recording_directory,
    shared_recording,
    trial_chunks,
    worst_step_ratio,
)
from tests.audio.channel_fade_probe import (
    BUS_FADE,
    CRT_SKIP,
    STEAL_DELAYED,
    STEAL_IMMEDIATE,
    TRIAL_COUNT,
    own_largest_step,
)


@pytest.fixture(scope='module')
def recordings(tmp_path_factory):
    """Each case's recording, made once for the run (a few seconds each).

    Returns:
        A function from a case to its left channel.
    """
    directory = recording_directory(tmp_path_factory.getbasetemp())
    made: dict[str, np.ndarray] = {}

    def recording(case: str) -> np.ndarray:
        if case not in made:
            made[case] = shared_recording(case, directory)
        return made[case]

    return recording


@pytest.mark.parametrize('case', [STEAL_IMMEDIATE, STEAL_DELAYED, BUS_FADE, CRT_SKIP])
def test_the_mixer_changes_a_channels_level_only_between_chunks(recordings, case):
    """Every step the recording shows falls on a mixer chunk boundary.

    The file starts on a chunk boundary, so a step between samples k - 1 and k is at a boundary
    when k is a multiple of the chunk length (diagnostics' second-difference spikes are centred
    on k - 1 and k). Not every trial steps above the tones' own largest step: a cut that lands
    near a zero crossing of the tone is smaller (seen in the native run: 4 of 6 trials), so the
    test asks for at least one step and checks where every step falls.
    """
    samples = recordings(case)
    steps = np.flatnonzero(np.abs(np.diff(samples)) > own_largest_step(case)) + 1
    spikes = find_discontinuities(samples)

    assert steps.size > 0
    assert all(step % DEFAULT_BUFFER_SAMPLES == 0 for step in steps)
    assert spikes
    assert all(
        spike % DEFAULT_BUFFER_SAMPLES in {0, DEFAULT_BUFFER_SAMPLES - 1} for spike in spikes
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        'Impl spec 7.1 [Open] (risk R4): SDL_mixer applies a fade per 512-frame chunk, so a '
        "10 ms steal fade is a plateau or a halt, never a ramp; the delay doesn't make it smooth. "
        'Fallback: engine-rendered fade tails (risk R5), the owner decides'
    ),
)
def test_a_steal_with_the_one_frame_delay_has_no_step_above_threshold(recordings):
    """Feature spec 16.1's criterion on a steal (the delayed path): not met by SDL_mixer."""
    samples = recordings(STEAL_DELAYED)

    assert worst_step_ratio(samples, case=STEAL_DELAYED) <= DISCONTINUITY_THRESHOLD


def test_a_bus_fade_reaches_the_channel_as_per_chunk_gain_steps(recordings):
    """Impl spec 7.2: a 50 ms fade applied once per frame is three gain steps of a third.

    Each chunk after the fade begins plays at one of the frame gains (1, 2/3, 1/3, 0), never in
    between: the mixer applies ``Channel.set_volume`` from the next chunk, whole.
    """
    samples = recordings(BUS_FADE)
    levels = chunk_levels(samples)
    recorded_trials = trial_chunks(samples)

    assert len(recorded_trials) == TRIAL_COUNT
    for chunks in recorded_trials:
        after = levels_after_the_action(levels, chunks)
        for level in after:
            assert min(abs(level - gain) for gain in BUS_FADE_GAINS) <= LEVEL_TOLERANCE, after


@pytest.mark.xfail(
    strict=True,
    reason=(
        'Impl spec 7.2 [Open] (risk R5): per-frame gain steps reach the channel whole at the '
        "next chunk, about 5x the tone's own largest step on a 440 Hz tone; audible or not is "
        "the owner's listening check. Fallback: rendered fade tails"
    ),
)
def test_a_bus_fade_stepped_per_frame_over_50_ms_has_no_step_above_threshold(recordings):
    """Feature spec 16.1's criterion on a 50 ms bus fade: not met by per-frame steps."""
    samples = recordings(BUS_FADE)

    assert worst_step_ratio(samples, case=BUS_FADE) <= DISCONTINUITY_THRESHOLD


def test_the_crt_skip_fade_on_the_device_is_a_plateau_or_two_then_a_halt(recordings):
    """AUD-CRT-003 on the device: the model in tests/test_crt_power_on_sound.py, confirmed.

    ``Channel.fadeout(20)`` on a 1 kHz tone: after the last full chunk come at most two chunks
    at a lower level, then silence (the channel halted) to the trial's end.
    """
    samples = recordings(CRT_SKIP)
    levels = chunk_levels(samples)
    recorded_trials = trial_chunks(samples)

    assert len(recorded_trials) == TRIAL_COUNT
    for chunks in recorded_trials:
        after = levels_after_the_action(levels, chunks)
        plateaus = after[after > LEVEL_TOLERANCE]
        assert plateaus.size <= MAXIMUM_CRT_FADE_PLATEAUS, after
        # Everything after the plateaus is silence: the halt
        assert np.all(after[plateaus.size :] == 0.0), after


@pytest.mark.xfail(
    strict=True,
    reason=(
        'AUD-CRT-003 [Open] (ruling R41): the device steps the 20 ms skip fade per chunk, as '
        "modelled. Pending the owner's listening check; fallback: engine-rendered fade tails"
    ),
)
def test_a_crt_skip_on_the_device_has_no_step_above_threshold(recordings):
    """AUD-CRT-003's "no step above threshold", measured on the device's fade: not met."""
    samples = recordings(CRT_SKIP)

    assert worst_step_ratio(samples, case=CRT_SKIP) <= DISCONTINUITY_THRESHOLD


def test_a_fade_that_halts_within_one_chunk_has_no_level_after_the_action():
    """A trial that never drops below full level has no action chunk to measure from.

    When the mixer thread runs late, a 20 ms fade can elapse between two chunks: the channel
    halts with no plateau (CircleCI macOS, 2026-11-04: 16 chunks at full level, then silence).
    The halt's silence separates the trials, so every chunk of the trial is at full level, and
    none of them is a plateau of the fade.
    """
    levels = np.ones(16)

    assert action_chunk(levels, range(16)) == 16
    assert levels_after_the_action(levels, range(16)).size == 0


def test_a_stalled_trial_stays_one_trial():
    """A long stall inside a trial does not split it: trials split at their separating silences.

    On a loaded machine the probe's one-frame sleep can run long (CircleCI macOS, 2026-11-03: a
    104 ms silence inside a steal-delayed trial), longer than the 100 ms that once marked a trial
    boundary. The recording still has TRIAL_COUNT trials, each silence between them the longest.
    """
    sounding = np.full(DEFAULT_BUFFER_SAMPLES * 20, 0.5)
    between_trials = np.zeros(round(0.300 * 44100))
    stall = np.zeros(4608)
    trials = [sounding] * TRIAL_COUNT
    trials[4] = np.concatenate([sounding, stall, sounding])
    pieces: list[np.ndarray] = []
    for trial in trials:
        pieces.extend([trial, between_trials])
    samples = np.concatenate(pieces[:-1])

    recorded_trials = trial_chunks(samples)

    assert len(recorded_trials) == TRIAL_COUNT
    stalled = recorded_trials[4]
    assert len(stalled) >= 2 * 20 + stall.size // DEFAULT_BUFFER_SAMPLES
