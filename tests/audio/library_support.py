"""Helpers for the sound library's tests: a library over the current context, WAV files, a mixer."""

import wave
from pathlib import Path

import numpy as np
import pygame

from glitchygames.audio.accounting import AudioAccountant
from glitchygames.audio.instrument import Instrument
from glitchygames.audio.library import CacheMode, SoundLibrary
from glitchygames.audio.pitch import Tuning
from glitchygames.audio.waves import current_wave_registry

PULSE_INSTRUMENT = Instrument(wave='square', envelope='pluck')
FIXTURE_SOUNDS = Path(__file__).parent / 'fixtures' / 'sounds'
FIXTURES = Path(__file__).parent / 'fixtures'


def make_library(
    cache=CacheMode.RAM,
    *,
    memory_limit_bytes=256 * 1024 * 1024,
    tuning_source=None,
    is_playing=None,
) -> tuple[SoundLibrary, AudioAccountant]:
    """Build a library over the current context's wave registry.

    Returns:
        The library and its accountant.
    """
    accountant = AudioAccountant()
    default_tuning = Tuning()
    library = SoundLibrary(
        cache=cache,
        accountant=accountant,
        waves=current_wave_registry(),
        tuning_source=tuning_source if tuning_source is not None else (lambda: default_tuning),
        memory_limit_bytes=memory_limit_bytes,
        **({'is_playing': is_playing} if is_playing is not None else {}),
    )
    return library, accountant


def write_wave_file(
    path: Path, *, frames: int = 441, sample_rate: int = 44100, channels: int = 1, width: int = 2
) -> Path:
    """Write a ramp as a PCM WAV file.

    Returns:
        The path.
    """
    ramp = np.linspace(-20000, 20000, frames).astype(np.int16)
    data = np.repeat(ramp[:, np.newaxis], channels, axis=1) if channels > 1 else ramp
    with wave.open(str(path), 'wb') as wave_file:
        wave_file.setnchannels(channels)
        wave_file.setsampwidth(width)
        wave_file.setframerate(sample_rate)
        wave_file.writeframes(data.tobytes() if width == 2 else bytes(frames * channels * width))
    return path


def start_mixer(*, frequency: int = 44100, channels: int = 1) -> None:
    """Start the mixer on the test run's dummy audio driver, replacing any running mixer."""
    pygame.mixer.quit()
    pygame.mixer.init(frequency=frequency, size=-16, channels=channels, buffer=512)


def stop_mixer() -> None:
    """Stop the mixer."""
    pygame.mixer.quit()
