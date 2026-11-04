"""Recording and measuring SDL_mixer's channel fades (tests/audio/channel_fade_probe.py's cases).

Shared by tests/audio/test_channel_fades.py (what holds whatever the machine's load) and
tests/benchmarks/test_channel_fade_relations.py (what depends on real-time scheduling, run only
under ``--benchmark-only``). A recording is made once per pytest run, not once per xdist worker:
the first worker to ask records it into the run's shared temporary directory and the others wait
for the file (``shared_recording``).
"""

from __future__ import annotations

import operator
import os
import sys
from pathlib import Path

import numpy as np

from glitchygames import clock
from glitchygames.audio.diagnostics import (
    DEFAULT_BUFFER_SAMPLES,
    DEFAULT_SAMPLE_RATE,
    find_silent_gaps,
)
from glitchygames.process import OutputCapture, run_command
from tests.audio import channel_fade_probe
from tests.audio.channel_fade_probe import TONE_AMPLITUDE, TRIAL_COUNT, own_largest_step

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
# Feature spec 16.1's metric: no step larger than the tones' own largest (the spec names no
# number; tests/test_crt_power_on_sound.py uses the same threshold)
DISCONTINUITY_THRESHOLD = 1.0
# The silence between trials is 200 ms; a halted fade leaves a few silent chunks inside a trial,
# and on a loaded machine a late sleep leaves more (104 ms on CircleCI macOS, 2026-11-03). So a
# silence of 100 ms or more may separate trials, and the TRIAL_COUNT - 1 longest of them do
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


# How often a worker waiting for another worker's recording looks for it
WAIT_POLL_SECONDS = 0.05


def recording_directory(base_temporary: Path) -> Path:
    """The directory this pytest run's workers share for the recordings.

    Under xdist each worker's base temporary directory (``popen-gwN``) sits inside the run's own
    directory, which the workers share; without xdist the base directory is the run's.

    Args:
        base_temporary: ``tmp_path_factory.getbasetemp()``.

    Returns:
        The directory, made if needed.
    """
    root = base_temporary.parent if os.environ.get('PYTEST_XDIST_WORKER') else base_temporary
    directory = root / 'channel-fade-recordings'
    directory.mkdir(exist_ok=True)
    return directory


def shared_recording(case: str, directory: Path) -> np.ndarray:
    """A case's recording, made once for every worker of the run.

    The first worker to create ``<case>.lock`` (exclusively) records; the others wait until the
    finished file appears (it is moved into place whole) or the recorder leaves ``<case>.failed``.

    Returns:
        The recording's left channel, -1..1.
    """
    path = directory / f'{case}.raw'
    failed = directory / f'{case}.failed'
    try:
        os.close(os.open(directory / f'{case}.lock', os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except FileExistsError:
        waited = 0.0
        while not path.exists():
            assert not failed.exists(), failed.read_text(encoding='utf-8')
            assert waited < RECORDING_TIMEOUT_SECONDS, f'no recording of {case} appeared'
            clock.raw_sleep(WAIT_POLL_SECONDS)
            waited += WAIT_POLL_SECONDS
    else:
        record(case, path=path, failed=failed)
    return read_recording(path)


def record(case: str, *, path: Path, failed: Path) -> None:
    """Record a probe case through SDL's disk audio driver in a child process.

    The child writes beside ``path``; the file is moved into place only when it finished, and a
    failure leaves its output in ``failed`` for the waiting workers.
    """
    partial = path.with_suffix('.partial')
    environment = {
        **os.environ,
        'SDL_AUDIODRIVER': 'disk',
        'SDL_DISKAUDIOFILE': str(partial),
        'SDL_VIDEODRIVER': 'dummy',
    }
    result = run_command(
        command=[sys.executable, '-m', channel_fade_probe.__name__, case],
        environment=environment,
        timeout_seconds=RECORDING_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
        working_directory=REPOSITORY_ROOT,
    )
    if result.returncode != 0:
        failed.write_text(result.stdout or f'exit {result.returncode}', encoding='utf-8')
    assert result.returncode == 0, result.stdout
    partial.replace(path)


def read_recording(path: Path) -> np.ndarray:
    """The disk driver's raw signed 16-bit stereo file as its left channel.

    Returns:
        The left channel, -1..1.
    """
    raw = np.fromfile(path, dtype='<i2')
    return raw[: raw.size - raw.size % 2].reshape(-1, 2)[:, 0].astype(np.float64) / INT16_SCALE


def trial_chunks(samples: np.ndarray) -> list[range]:
    """The mixer chunks of each trial, split at the silences between the trials.

    The probe plays TRIAL_COUNT trials, so the TRIAL_COUNT - 1 longest silences of at least
    TRIAL_SEPARATING_SAMPLES separate them; a shorter one (a late sleep inside a trial) stays in
    its trial. Fewer such silences give fewer trials, which the callers' count check catches.
    The disk driver writes whole chunks from the file's start, so chunk ``i`` is samples
    ``i * 512 .. (i + 1) * 512``.

    Returns:
        Each trial's chunk indices, from its first sounding chunk to its last.
    """
    sounding = np.flatnonzero(samples)
    candidates = find_silent_gaps(samples, minimum_samples=TRIAL_SEPARATING_SAMPLES)
    longest = sorted(candidates, key=operator.itemgetter(1), reverse=True)[: TRIAL_COUNT - 1]
    gaps = sorted(longest)
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
    changed. A late mixer thread can miss a short fade's plateaus: the channel halts, the halt's
    silence separates the trials, and no chunk of the trial is below full level.

    Returns:
        The chunk's index in the recording, or ``chunks.stop`` if no chunk is below full level.
    """
    trial = levels[chunks.start : chunks.stop]
    at_full = trial >= 1.0 - LEVEL_TOLERANCE
    first_full = int(np.argmax(at_full))
    below_full = ~at_full[first_full:]
    if not below_full.any():
        return chunks.stop
    return chunks.start + first_full + int(np.argmax(below_full))


def levels_after_the_action(levels: np.ndarray, chunks: range) -> np.ndarray:
    """A trial's chunk levels from its action chunk to its end.

    Returns:
        The levels.
    """
    return levels[action_chunk(levels, chunks) : chunks.stop]
