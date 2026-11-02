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
result never rests on one phase of the tone.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

from glitchygames.audio.diagnostics import (
    DEFAULT_BUFFER_SAMPLES,
    DEFAULT_SAMPLE_RATE,
    find_discontinuities,
    find_silent_gaps,
)
from glitchygames.process import OutputCapture, run_command
from tests.audio import channel_fade_probe
from tests.audio.channel_fade_probe import (
    BUS_FADE,
    CRT_SKIP,
    STEAL_DELAYED,
    STEAL_IMMEDIATE,
    STEALER_TONE_HZ,
    STOLEN_TONE_HZ,
    TONE_AMPLITUDE,
    TRIAL_COUNT,
    own_largest_step,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
# Feature spec 16.1's metric: no step larger than the tones' own largest (the spec names no
# number; tests/test_crt_power_on_sound.py uses the same threshold)
DISCONTINUITY_THRESHOLD = 1.0
# The silence between trials is 200 ms; a halted fade leaves at most a few silent chunks inside a
# trial, so 100 ms of zeros separates trials and nothing else
TRIAL_SEPARATING_SAMPLES = 4410
# A recording of six trials takes about six seconds; this is far beyond it
RECORDING_TIMEOUT_SECONDS = 120.0
# The level of a centred tone at full volume (impl spec 7.2: -3 dB each side)
CENTRED_FULL_LEVEL = TONE_AMPLITUDE * np.cos(np.pi / 4)
# A chunk counts as at full level, or silent, within this fraction of the full level
LEVEL_TOLERANCE = 0.03
# The bus fade's per-frame gains over 50 ms at 60 frames a second (channel_fade_probe.act)
BUS_FADE_GAINS = (1.0, 2.0 / 3.0, 1.0 / 3.0, 0.0)
# A fade of 20 ms spans at most two chunks before SDL_mixer halts the channel (11.6 ms each)
MAXIMUM_CRT_FADE_PLATEAUS = 2
INT16_SCALE = 32768.0
RATE = DEFAULT_SAMPLE_RATE
# A tone below a tenth of its full level in a chunk is absent from it (the other tone's leakage
# through the Hann window is a few percent)
ABSENT_LEVEL = 0.1


def record(case: str, directory: Path) -> np.ndarray:
    """Record a probe case through SDL's disk audio driver in a child process.

    Returns:
        The recording's left channel, -1..1.
    """
    path = directory / f'{case}.raw'
    environment = {
        **os.environ,
        'SDL_AUDIODRIVER': 'disk',
        'SDL_DISKAUDIOFILE': str(path),
        'SDL_VIDEODRIVER': 'dummy',
    }
    result = run_command(
        command=[sys.executable, '-m', channel_fade_probe.__name__, case],
        environment=environment,
        timeout_seconds=RECORDING_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
        working_directory=REPOSITORY_ROOT,
    )
    assert result.returncode == 0, result.stdout
    raw = np.fromfile(path, dtype='<i2')
    return raw[: raw.size - raw.size % 2].reshape(-1, 2)[:, 0].astype(np.float64) / INT16_SCALE


@pytest.fixture(scope='module')
def recordings(tmp_path_factory):
    """Each case's recording, made once for the module (a few seconds each).

    Returns:
        A function from a case to its left channel.
    """
    directory = tmp_path_factory.mktemp('channel-fades')
    made: dict[str, np.ndarray] = {}

    def recording(case: str) -> np.ndarray:
        if case not in made:
            made[case] = record(case, directory)
        return made[case]

    return recording


def trial_chunks(samples: np.ndarray) -> list[range]:
    """The mixer chunks of each trial, split at the silences between the trials.

    The disk driver writes whole chunks from the file's start, so chunk ``i`` is samples
    ``i * 512 .. (i + 1) * 512``.

    Returns:
        Each trial's chunk indices, from its first sounding chunk to its last.
    """
    sounding = np.flatnonzero(samples)
    gaps = find_silent_gaps(samples, minimum_samples=TRIAL_SEPARATING_SAMPLES)
    starts = [int(sounding[0])] + [start + length for start, length in gaps]
    ends = [start for start, _ in gaps] + [int(sounding[-1]) + 1]
    return [
        range(start // DEFAULT_BUFFER_SAMPLES, -(-end // DEFAULT_BUFFER_SAMPLES))
        for start, end in zip(starts, ends, strict=True)
    ]


def worst_step_ratio(samples: np.ndarray, *, case: str) -> float:
    """Feature spec 16.1's discontinuity metric over a recording.

    Returns:
        The largest sample-to-sample step relative to the case's tones' own largest step.
    """
    return float(np.max(np.abs(np.diff(samples)))) / own_largest_step(case)


def chunk_levels(samples: np.ndarray, *, frequency: float | None = None) -> np.ndarray:
    """The level of each mixer chunk, as a fraction of a centred tone's full level.

    Without a frequency, the chunk's peak. With one, that tone's amplitude in the chunk: a
    single-frequency DFT under a Hann window (the window keeps the other probe tone, 220 Hz and
    more than two DFT bins away, out of the estimate).

    Returns:
        One level per chunk.
    """
    whole = samples[: samples.size - samples.size % DEFAULT_BUFFER_SAMPLES]
    chunks = whole.reshape(-1, DEFAULT_BUFFER_SAMPLES)
    if frequency is None:
        return np.max(np.abs(chunks), axis=1) / CENTRED_FULL_LEVEL
    window = np.hanning(DEFAULT_BUFFER_SAMPLES)
    oscillator = np.exp(-2j * np.pi * frequency * np.arange(DEFAULT_BUFFER_SAMPLES) / RATE)
    # An elementwise sum, not ``chunks @ ...``: the complex matmul goes through the system BLAS
    # (Accelerate on macOS), which raises a spurious "divide by zero encountered in matmul" on
    # chunks of silence (reproduced on numpy's own zeros, 2026-11-02)
    amplitudes = 2.0 * np.abs(np.sum(chunks * (window * oscillator), axis=1)) / np.sum(window)
    return amplitudes / CENTRED_FULL_LEVEL


def action_chunk(levels: np.ndarray, chunks: range) -> int:
    """The trial's first chunk below full level after its tone reached full level.

    A trial's tone plays at full level until the case acts; this chunk is the first the action
    changed.

    Returns:
        The chunk's index in the recording.
    """
    trial = levels[chunks.start : chunks.stop]
    at_full = trial >= 1.0 - LEVEL_TOLERANCE
    first_full = int(np.argmax(at_full))
    return chunks.start + first_full + int(np.argmax(~at_full[first_full:]))


def levels_after_the_action(levels: np.ndarray, chunks: range) -> np.ndarray:
    """A trial's chunk levels from its action chunk to its end.

    Returns:
        The levels.
    """
    return levels[action_chunk(levels, chunks) : chunks.stop]


@pytest.mark.parametrize('case', [STEAL_IMMEDIATE, STEAL_DELAYED, BUS_FADE, CRT_SKIP])
def test_the_mixer_changes_a_channels_level_only_between_chunks(recordings, case):
    """Every step the recording shows falls on a mixer chunk boundary.

    The file starts on a chunk boundary, so a step between samples k - 1 and k is at a boundary
    when k is a multiple of the chunk length (diagnostics' second-difference spikes are centred
    on k - 1 and k).
    """
    samples = recordings(case)
    steps = np.flatnonzero(np.abs(np.diff(samples)) > own_largest_step(case)) + 1
    spikes = find_discontinuities(samples)

    assert steps.size >= TRIAL_COUNT
    assert all(step % DEFAULT_BUFFER_SAMPLES == 0 for step in steps)
    assert spikes
    assert all(
        spike % DEFAULT_BUFFER_SAMPLES in {0, DEFAULT_BUFFER_SAMPLES - 1} for spike in spikes
    )


def test_fadeout_then_play_at_once_cuts_the_stolen_voice(recordings):
    """Impl spec 7.1's open question, answered: ``play`` right after ``fadeout(10)`` cuts the fade.

    ``play`` on a channel straight after its ``fadeout(10)`` replaces the fading sound at the
    next chunk, so the fade is never heard. In every trial the chunk where the stolen tone
    leaves full level already holds the stealer (and no stolen tone), and the switch steps far
    above the metric. The voice table therefore keeps its one-frame delayed play
    (src/glitchygames/audio/voices.py).
    """
    samples = recordings(STEAL_IMMEDIATE)
    stolen = chunk_levels(samples, frequency=STOLEN_TONE_HZ)
    stealer = chunk_levels(samples, frequency=STEALER_TONE_HZ)
    recorded_trials = trial_chunks(samples)

    assert len(recorded_trials) == TRIAL_COUNT
    for chunks in recorded_trials:
        first_changed = action_chunk(stolen, chunks)
        assert stolen[first_changed] <= ABSENT_LEVEL
        assert stealer[first_changed] > ABSENT_LEVEL
    assert worst_step_ratio(samples, case=STEAL_IMMEDIATE) > DISCONTINUITY_THRESHOLD


def test_a_steal_with_the_one_frame_delay_lets_the_fade_run_before_the_stealer(recordings):
    """The delayed path the voice table uses: the stolen channel's fade runs first.

    The fade is a plateau or a halt (SDL_mixer's 10 ms fade is shorter than a chunk), and only
    then does the stealer start. In every trial the chunk where the stolen tone leaves full
    level holds no stealer: the frame of waiting (16.7 ms) is longer than a chunk (11.6 ms).
    """
    samples = recordings(STEAL_DELAYED)
    stolen = chunk_levels(samples, frequency=STOLEN_TONE_HZ)
    stealer = chunk_levels(samples, frequency=STEALER_TONE_HZ)
    recorded_trials = trial_chunks(samples)

    assert len(recorded_trials) == TRIAL_COUNT
    for chunks in recorded_trials:
        first_changed = action_chunk(stolen, chunks)
        assert stealer[first_changed] <= ABSENT_LEVEL
        assert np.any(stealer[first_changed : chunks.stop] > ABSENT_LEVEL)


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
        assert after.size > 0
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
