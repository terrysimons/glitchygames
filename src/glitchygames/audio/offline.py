"""Offline rendering: a sound, or a mix of sounds, written to a WAV file with no audio device.

``render_to_file`` (impl spec 8 and 9; feature spec W9, 10 and AUD-FUNC-008) mixes compiled
float buffers the way the device path plays them, but at exact sample offsets, and writes the
result as a 16-bit PCM or 32-bit float WAV file. It never opens or touches the mixer: a sound not
compiled yet (cache ``none``) is compiled on a copy through the library's one compile path
(``library.compile_sound``), so the render is the compiled buffer itself.

The rules:

- **Parity:** a sound rendered alone (``loops=1``, no events) at its own rate is written exactly
  as its compiled int16 buffer: the mix of one event at offset 0 and volume 1 is its float
  buffer, converted as the library converts it (``synth.to_pcm16``).
- **Events:** each ``OfflineEvent`` adds its sound's float buffer at ``round(seconds x rate)``,
  times its volume. The output is stereo when any event pans or ``stems`` is asked for, and then
  every event (the sound itself included, at the centre) takes the voices' constant-power pan
  law (``voices.constant_power_gains``, impl spec 7.2); otherwise it is mono.
- **Loops:** the sound plays ``loops`` times back to back, as the device replays a baked buffer.
- **Tail:** the render stops once the output has stayed below -90 dBFS for 100 ms after the last
  event's nominal end (an instrument sound's last note release, where its held part ends; the
  end of any other sound's buffer), keeping those 100 ms, or ``tail_seconds`` after that nominal
  end if that is sooner. A quiet stretch the buffers end before 100 ms stops nothing: the whole
  mix is written.
- **Clipping:** the report gives the peak and the number of samples beyond full scale. A float32
  file keeps them; an int16 file clips them (never silently: they are counted).
- **Stems:** with ``stems=True`` each bus's events (by the sound's playback bus) are also written
  to ``<stem>.<bus><suffix>`` beside the mix, the same length and format.

Live sounds (and so ``parameter_timeline``) arrive in M2.
"""

from __future__ import annotations

import math
import struct
import wave
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Final

import numpy as np

from glitchygames.audio.library import compile_sound
from glitchygames.audio.render import gate_end_frame
from glitchygames.audio.synth import to_pcm16
from glitchygames.audio.voices import constant_power_gains
from glitchygames.output_files import write_aside_then_replace

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from glitchygames.audio.library import Sound
    from glitchygames.audio.synth import FloatArray

# The tail ends once the output stays below -90 dBFS for 100 ms (impl spec 9)
QUIET_LEVEL: Final[float] = 10.0 ** (-90.0 / 20.0)
QUIET_SECONDS: Final[float] = 0.1
SAMPLE_FORMATS: Final[tuple[str, ...]] = ('int16', 'float32')
LIVE_SOUNDS_MESSAGE: Final[str] = 'live sounds arrive in M2'
FULL_SCALE: Final[float] = 1.0
PAN_LOWEST: Final[float] = -1.0
PAN_HIGHEST: Final[float] = 1.0
STEREO_CHANNELS: Final[int] = 2
PCM16_SAMPLE_WIDTH_BYTES: Final[int] = 2
FLOAT32_SAMPLE_WIDTH_BYTES: Final[int] = 4
# The WAVE format tag of IEEE floating-point samples, which the standard library's wave module
# cannot write (it writes PCM only). The layout written for it (a RIFF WAVE file with an 18-byte
# 'fmt ' chunk, cbSize 0, and the 'fact' chunk every non-PCM file needs) follows Microsoft/IBM,
# "Multimedia Programming Interface and Data Specifications 1.0" (1991), and its summary in P.
# Kabal, "Audio File Format Specifications: WAVE", McGill University,
# https://www-mmsp.ece.mcgill.ca/Documents/AudioFormats/WAVE/WAVE.html
WAVE_FORMAT_IEEE_FLOAT: Final[int] = 3
FLOAT_FORMAT_CHUNK_SIZE: Final[int] = 18
FACT_CHUNK_SIZE: Final[int] = 4


@dataclass(frozen=True)
class OfflineEvent:
    """A sound placed in an offline mix.

    Attributes:
        seconds: When it starts, from the mix's start (at ``round(seconds x rate)``).
        sound: The sound (compiled or not).
        volume: Its gain, 0 or more (not the sound file's playback default: given here).
        pan: -1 (left) to 1 (right); any pan but 0 makes the output stereo.
    """

    seconds: float
    sound: Sound
    volume: float = 1.0
    pan: float = 0.0

    def __post_init__(self) -> None:
        """Refuse a time before the start, a negative volume or a pan outside -1..1.

        Raises:
            ValueError: Naming the value.
        """
        if not (math.isfinite(self.seconds) and self.seconds >= 0.0):
            message = f'an event starts at 0 seconds or later, got {self.seconds}'
            raise ValueError(message)
        if not self.volume >= 0.0:
            message = f'an event volume is 0 or more, got {self.volume}'
            raise ValueError(message)
        if not PAN_LOWEST <= self.pan <= PAN_HIGHEST:
            message = f'pan must be between {PAN_LOWEST} and {PAN_HIGHEST}, got {self.pan}'
            raise ValueError(message)


@dataclass(frozen=True)
class RenderReport:
    """What an offline render wrote.

    Attributes:
        path: The mix's file.
        frames: Its frames (samples per channel), after the tail was cut.
        peak: The loudest sample's magnitude, before any int16 clipping.
        clip_count: The samples (over every channel) beyond full scale: kept in a float32 file,
            clipped in an int16 one.
        stem_paths: Each bus stem's file, by bus name order (none without ``stems``).
    """

    path: Path
    frames: int
    peak: float
    clip_count: int
    stem_paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class _Placed:
    """One buffer in the mix: where it starts, its gains, its bus and its nominal end."""

    offset: int
    samples: FloatArray
    volume: float
    pan: float
    bus: str
    nominal_end: int


def render_to_file(  # ruff: ignore[too-many-arguments] - impl spec 8's signature
    sound: Sound,
    path: Path | str,
    *,
    sample_rate: int | None = None,
    sample_format: str = 'int16',
    loops: int = 1,
    tail_seconds: float | None = None,
    stems: bool = False,
    parameter_timeline: Mapping[str, Sequence[tuple[float, float]]] | None = None,
    events: Sequence[OfflineEvent] = (),
) -> RenderReport:
    """Render a sound (and any events) to a WAV file, opening no audio device.

    Args:
        sound: The sound, at offset 0, centred, at volume 1.
        path: The WAV file to write (written aside, then moved into place).
        sample_rate: The rate to render at (default: the sound's). Sounds at another rate are
            compiled at this one (a recorded file is resampled linearly).
        sample_format: ``'int16'`` (PCM) or ``'float32'`` (IEEE float, overs kept).
        loops: How many times the sound plays, back to back.
        tail_seconds: The most the render runs past the last nominal end, or None for the
            -90 dBFS rule alone.
        stems: Also write each bus's events to a file of its own (the output is then stereo).
        parameter_timeline: Live parameters over time; must be None until live sounds (M2).
        events: More sounds placed in the mix.

    Returns:
        What was written.

    Raises:
        ValueError: For a parameter timeline (live sounds arrive in M2) or an argument out of
            its range; nothing is written. An unwritable path raises ``OSError`` (no partial file
            is left behind).
    """
    if parameter_timeline is not None:
        raise ValueError(LIVE_SOUNDS_MESSAGE)
    _check_arguments(
        sample_rate=sample_rate, sample_format=sample_format, loops=loops, tail_seconds=tail_seconds
    )
    destination = Path(path)
    rate = sound.sample_rate if sample_rate is None else sample_rate
    placed = _placed_buffers(sound, rate=rate, loops=loops, events=events)
    stereo = stems or any(abs(event.pan) > 0.0 for event in events)
    total = max(entry.offset + len(entry.samples) for entry in placed)
    mix = _mixed(placed, total=total, stereo=stereo)
    end = _render_end(
        mix,
        nominal_end=max(entry.nominal_end for entry in placed),
        sample_rate=rate,
        tail_seconds=tail_seconds,
    )
    mix = mix[:end]
    _write_wave(destination, mix, sample_rate=rate, sample_format=sample_format)
    stem_paths: list[Path] = []
    if stems:
        for bus in sorted({entry.bus for entry in placed}):
            stem_path = destination.with_name(f'{destination.stem}.{bus}{destination.suffix}')
            on_the_bus = [entry for entry in placed if entry.bus == bus]
            stem = _mixed(on_the_bus, total=total, stereo=True)[:end]
            _write_wave(stem_path, stem, sample_rate=rate, sample_format=sample_format)
            stem_paths.append(stem_path)
    return RenderReport(
        path=destination,
        frames=len(mix),
        peak=float(np.max(np.abs(mix), initial=0.0)),
        clip_count=int(np.count_nonzero(np.abs(mix) > FULL_SCALE)),
        stem_paths=tuple(stem_paths),
    )


def nominal_end_frame(sound: Sound, *, sample_rate: int) -> int:
    """Where a sound's nominal end is, at a rate: the tail rule counts quiet from here.

    Args:
        sound: The sound.
        sample_rate: The rate.

    Returns:
        An instrument sound's last note release frame; any other sound's buffer length.
    """
    return _nominal_end(sound, _samples_at(sound, rate=sample_rate), rate=sample_rate)


def _check_arguments(
    *, sample_rate: int | None, sample_format: str, loops: int, tail_seconds: float | None
) -> None:
    """Refuse an argument out of its range.

    Raises:
        ValueError: Naming the argument.
    """
    if sample_format not in SAMPLE_FORMATS:
        message = f"sample_format must be 'int16' or 'float32', got {sample_format!r}"
        raise ValueError(message)
    if loops < 1:
        message = f'loops must be at least 1, got {loops}'
        raise ValueError(message)
    if tail_seconds is not None and not tail_seconds >= 0.0:
        message = f'tail_seconds must be at least 0, got {tail_seconds}'
        raise ValueError(message)
    if sample_rate is not None and sample_rate <= 0:
        message = f'sample_rate must be positive, got {sample_rate}'
        raise ValueError(message)


def _placed_buffers(
    sound: Sound, *, rate: int, loops: int, events: Sequence[OfflineEvent]
) -> list[_Placed]:
    """Place the sound's loops and every event's buffer.

    Returns:
        The buffers, the sound's loops first.
    """
    samples = _samples_at(sound, rate=rate)
    end = _nominal_end(sound, samples, rate=rate)
    placed = [
        _Placed(
            offset=index * len(samples),
            samples=samples,
            volume=1.0,
            pan=0.0,
            bus=sound.playback_defaults.bus,
            nominal_end=index * len(samples) + end,
        )
        for index in range(loops)
    ]
    for event in events:
        event_samples = _samples_at(event.sound, rate=rate)
        offset = round(event.seconds * rate)
        placed.append(
            _Placed(
                offset=offset,
                samples=event_samples,
                volume=event.volume,
                pan=event.pan,
                bus=event.sound.playback_defaults.bus,
                nominal_end=offset + _nominal_end(event.sound, event_samples, rate=rate),
            )
        )
    return placed


def _samples_at(sound: Sound, *, rate: int) -> FloatArray:
    """A sound's float samples at a rate, compiling a copy when the sound holds none at it.

    Returns:
        Mono float64 samples (the sound's own array when it is compiled at the rate).
    """
    if sound.is_compiled and sound.sample_rate == rate:
        assert sound.samples_float is not None
        return sound.samples_float
    copy = sound.fresh_copy(sample_rate=rate)
    compile_sound(copy)
    assert copy.samples_float is not None
    if copy.sample_rate == rate:
        return copy.samples_float
    return _resampled(copy.samples_float, from_rate=copy.sample_rate, to_rate=rate)


def _resampled(samples: FloatArray, *, from_rate: int, to_rate: int) -> FloatArray:
    """Resample by linear interpolation, as the library resamples a held sound for a new mixer.

    Returns:
        The samples at the new rate.
    """
    new_length = round(len(samples) * to_rate / from_rate)
    positions = np.arange(new_length) * (from_rate / to_rate)
    return np.interp(positions, np.arange(len(samples)), samples)


def _nominal_end(sound: Sound, samples: FloatArray, *, rate: int) -> int:
    """The nominal end of a sound whose samples at the rate are known.

    Returns:
        The frame (see ``nominal_end_frame``).
    """
    spec = sound.spec
    if spec is None:
        return len(samples)
    if spec.sample_rate != rate:
        spec = replace(spec, sample_rate=rate)
    return gate_end_frame(spec)


def _mixed(placed: Sequence[_Placed], *, total: int, stereo: bool) -> FloatArray:
    """Sum buffers at their offsets: mono, or stereo through the constant-power pan law.

    Returns:
        ``(total,)`` mono or ``(total, 2)`` stereo float64 samples.
    """
    if not stereo:
        mono = np.zeros(total)
        for entry in placed:
            mono[entry.offset : entry.offset + len(entry.samples)] += entry.volume * entry.samples
        return mono
    both = np.zeros((total, STEREO_CHANNELS))
    for entry in placed:
        left, right = constant_power_gains(pan=entry.pan, gain=entry.volume)
        span = slice(entry.offset, entry.offset + len(entry.samples))
        both[span, 0] += left * entry.samples
        both[span, 1] += right * entry.samples
    return both


def _render_end(
    mix: FloatArray, *, nominal_end: int, sample_rate: int, tail_seconds: float | None
) -> int:
    """Where the render stops (impl spec 9's tail rule).

    After the nominal end, the first stretch below -90 dBFS (on every channel) at least 100 ms
    long ends the render 100 ms into it; ``tail_seconds`` past the nominal end ends it sooner.

    Returns:
        The frame count to keep.
    """
    total = len(mix)
    end = total
    window = round(QUIET_SECONDS * sample_rate)
    levels = np.abs(mix) if mix.ndim == 1 else np.max(np.abs(mix), axis=1)
    loud = np.flatnonzero(levels[nominal_end:] >= QUIET_LEVEL) + nominal_end
    # A quiet stretch starts at the nominal end and after each loud frame, and runs to the next
    # loud frame (or the end of the mix)
    starts = np.concatenate(([nominal_end], loud + 1))
    stops = np.concatenate((loud, [total]))
    long_enough = np.flatnonzero(stops - starts >= window)
    if len(long_enough):
        end = int(starts[long_enough[0]]) + window
    if tail_seconds is not None:
        end = min(end, nominal_end + round(tail_seconds * sample_rate))
    return end


def _write_wave(
    destination: Path, frames: FloatArray, *, sample_rate: int, sample_format: str
) -> None:
    """Write mono or stereo float frames as a WAV file, aside first, then moved into place."""
    channels = 1 if frames.ndim == 1 else frames.shape[1]
    if sample_format == 'int16':
        # WAV data is little-endian by definition
        data = to_pcm16(frames).astype('<i2').tobytes()

        def write_pcm(aside: Path) -> None:
            with wave.open(str(aside), 'wb') as wave_file:
                wave_file.setnchannels(channels)
                wave_file.setsampwidth(PCM16_SAMPLE_WIDTH_BYTES)
                wave_file.setframerate(sample_rate)
                wave_file.writeframes(data)

        write_aside_then_replace(destination=destination, write=write_pcm)
        return
    data = frames.astype('<f4').tobytes()
    block_align = channels * FLOAT32_SAMPLE_WIDTH_BYTES
    format_chunk = struct.pack(
        '<HHIIHHH',
        WAVE_FORMAT_IEEE_FLOAT,
        channels,
        sample_rate,
        sample_rate * block_align,
        block_align,
        FLOAT32_SAMPLE_WIDTH_BYTES * 8,
        0,  # cbSize: no extension
    )
    chunks = b''.join((
        b'fmt ' + struct.pack('<I', FLOAT_FORMAT_CHUNK_SIZE) + format_chunk,
        b'fact' + struct.pack('<I', FACT_CHUNK_SIZE) + struct.pack('<I', len(frames)),
        # Four-byte samples: the data chunk is never odd-sized, so it needs no pad byte
        b'data' + struct.pack('<I', len(data)) + data,
    ))
    riff = b'RIFF' + struct.pack('<I', len(b'WAVE') + len(chunks)) + b'WAVE' + chunks
    write_aside_then_replace(destination=destination, write=lambda aside: aside.write_bytes(riff))
