"""Recording and measuring SDL_mixer's channel fades (tests/audio/channel_fade_probe.py's cases).

Shared by tests/audio/test_channel_fades.py (what holds whatever the machine's load) and
tests/benchmarks/test_channel_fade_relations.py (what depends on real-time scheduling, run only
under ``--benchmark-only``). A recording is made once per pytest run, not once per xdist worker:
the first worker to ask records it into the run's shared temporary directory and the others wait
for the file (``shared_recording``).
"""

from __future__ import annotations

import dataclasses
import operator
import os
import sys
from pathlib import Path
from typing import Protocol

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
# Where the steal benchmarks write each run's per-trial reports (test-results/ is untracked, as
# for every test artifact; the same place as tests/benchmarks/test_logging_cost.py's report)
TRIAL_REPORT_DIRECTORY = REPOSITORY_ROOT / 'test-results'
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
# Most of a recording's trials must show the voice table's delay: a mixer thread that runs late can
# put a trial's fadeout and play before the same chunk (CircleCI macOS, 2026-11-04: job 2844, one
# trial's stealer at level 0.21), while a delay that stopped working would show in all of them
MINIMUM_DELAYED_STEAL_TRIALS = TRIAL_COUNT // 2 + 1


# How often a worker waiting for another worker's recording looks for it
WAIT_POLL_SECONDS = 0.05
# How many times a case is recorded before a lost trial fails it (record). A stall long enough to
# swallow a 200 ms silence between trials is rare (seen twice, both on CircleCI's Windows job:
# 2026-11-11 and 2026-11-13), so three short recordings in a row point at the machine
RECORDING_ATTEMPTS = 3


class RecordingAttempt(Protocol):
    """Makes one recording of a probe case into a partial file (``record_attempt``)."""

    def __call__(self, case: str, *, partial: Path) -> str | None:
        """Record ``case`` into ``partial``.

        Returns:
            The failure's output when the recording could not be made, else None.

        """
        ...


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


def record(case: str, *, path: Path, failed: Path, attempt: RecordingAttempt | None = None) -> None:
    """Record a probe case through SDL's disk audio driver, again when a trial was lost.

    The child writes beside ``path``; the file is moved into place only when it finished and
    holds all TRIAL_COUNT trials. The disk driver writes nothing while its thread is starved, so
    on a loaded machine a silence between two trials can vanish and the two record as one
    (CircleCI Windows: the CRT skip 2026-11-11, job 3303's bus fade 2026-11-13, each 5 of 6).
    Such a recording is made again, up to RECORDING_ATTEMPTS times; the callers' exact trial
    count stays, so a merged trial is never analysed as one. A failure (the child's, or every
    attempt short) leaves its message in ``failed`` for the waiting workers.

    Args:
        case: The probe case.
        path: Where the finished recording goes.
        failed: Where a failure's message goes.
        attempt: Makes one recording into the partial file (tests pass a stand-in); None is
            ``record_attempt``, the probe's child process.

    Raises:
        AssertionError: The child failed, or every attempt lost a trial.

    """
    attempt = record_attempt if attempt is None else attempt
    partial = path.with_suffix('.partial')
    trial_counts: list[int] = []
    for _ in range(RECORDING_ATTEMPTS):
        child_failure = attempt(case, partial=partial)
        if child_failure is not None:
            failed.write_text(child_failure, encoding='utf-8')
        assert child_failure is None, child_failure
        trial_counts.append(len(trial_chunks(read_recording(partial))))
        if trial_counts[-1] == TRIAL_COUNT:
            partial.replace(path)
            return
        partial.unlink()
    message = (
        f'{RECORDING_ATTEMPTS} recordings of {case} each lost a trial (trial counts '
        f'{", ".join(str(count) for count in trial_counts)}, of {TRIAL_COUNT}): the disk audio '
        "driver's thread stalled through a silence between trials on every attempt"
    )
    failed.write_text(message, encoding='utf-8')
    raise AssertionError(message)


def record_attempt(case: str, *, partial: Path) -> str | None:
    """Record a probe case once, through SDL's disk audio driver in a child process.

    Returns:
        The child's output when it failed (or its exit status, when it printed nothing), else
        None: the recording is in ``partial``.

    """
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
        return result.stdout or f'exit {result.returncode}'
    return None


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
    its trial. Fewer such silences give fewer trials: ``record`` records such a recording again,
    and the callers' count check catches one that reaches them.
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


def delayed_steal_trials(
    *, stolen: np.ndarray, stealer: np.ndarray, recorded_trials: list[range]
) -> int:
    """Count the trials whose stealer is absent from the first chunk the fade changed.

    Returns:
        How many trials put the stealer after the fade's first chunk.
    """
    return sum(
        bool(stealer[action_chunk(stolen, chunks)] <= ABSENT_LEVEL) for chunks in recorded_trials
    )


def levels_after_the_action(levels: np.ndarray, chunks: range) -> np.ndarray:
    """A trial's chunk levels from its action chunk to its end.

    Returns:
        The levels.
    """
    return levels[action_chunk(levels, chunks) : chunks.stop]


@dataclasses.dataclass(frozen=True)
class TrialReportRow:
    """One trial's levels in the chunk the steal changed, and what followed.

    Attributes:
        trial: The trial's number, from 1.
        action_chunk: The recording's chunk the steal first changed (``action_chunk``).
        stolen_level: The stolen tone's level in that chunk.
        stealer_level: The stealer tone's level in that chunk.
        stealer_absent: Whether the stealer is absent from that chunk (a delayed steal).
        stealer_sounds_from_then_on: Whether the stealer sounds in a chunk from that one to the
            trial's end.

    """

    trial: int
    action_chunk: int
    stolen_level: float
    stealer_level: float
    stealer_absent: bool
    stealer_sounds_from_then_on: bool


def trial_report_rows(samples: np.ndarray) -> list[TrialReportRow]:
    """Describe every trial of a steal recording, whether or not its relation held.

    Returns:
        One row per recorded trial.
    """
    stolen = chunk_levels(samples, frequency=channel_fade_probe.STOLEN_TONE_HZ)
    stealer = chunk_levels(samples, frequency=channel_fade_probe.STEALER_TONE_HZ)
    rows = []
    for trial, chunks in enumerate(trial_chunks(samples), start=1):
        first_changed = action_chunk(stolen, chunks)
        rows.append(
            TrialReportRow(
                trial=trial,
                action_chunk=first_changed,
                stolen_level=float(stolen[first_changed]),
                stealer_level=float(stealer[first_changed]),
                stealer_absent=bool(stealer[first_changed] <= ABSENT_LEVEL),
                stealer_sounds_from_then_on=bool(
                    np.any(stealer[first_changed : chunks.stop] > ABSENT_LEVEL)
                ),
            )
        )
    return rows


def trial_report_path(*, case: str, directory: Path = TRIAL_REPORT_DIRECTORY) -> Path:
    """Return where a case's report goes: ``<directory>/channel-fade-<case>.md``.

    Returns:
        The report's path.
    """
    return directory / f'channel-fade-{case}.md'


def trial_report_text(*, rows: list[TrialReportRow], case: str) -> str:
    """Format the rows as a Markdown table.

    Returns:
        The report, ending in a newline.
    """
    lines = [
        f'Channel fade relations: {case}',
        '',
        (
            '| Trial | Action chunk | Stolen level | Stealer level | Stealer absent '
            '| Stealer sounds from then on |'
        ),
        '|---:|---:|---:|---:|---|---|',
        *(
            f'| {row.trial} | {row.action_chunk} | {row.stolen_level:.3f} '
            f'| {row.stealer_level:.3f} | {"yes" if row.stealer_absent else "no"} '
            f'| {"yes" if row.stealer_sounds_from_then_on else "no"} |'
            for row in rows
        ),
        '',
    ]
    return '\n'.join(lines)


def write_trial_report(
    samples: np.ndarray, *, case: str, directory: Path = TRIAL_REPORT_DIRECTORY
) -> tuple[Path, str]:
    """Write every trial of a recording to ``<directory>/channel-fade-<case>.md``.

    Returns:
        The report's path and its text.
    """
    text = trial_report_text(rows=trial_report_rows(samples), case=case)
    path = trial_report_path(case=case, directory=directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path, text
