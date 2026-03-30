"""Synthesized sound effects for Brave Adventurer.

All sounds are generated from waveform math at startup using numpy.
No external audio files are needed. Sounds are compatible with
the GlitchyGames mixer (22050 Hz, signed 16-bit, stereo).
"""

from __future__ import annotations

import logging

import numpy as np
import numpy.typing as npt
import pygame

log = logging.getLogger('game')

# Mixer settings (must match glitchygames/events/audio.py pre_init)
SAMPLE_RATE = 22050
MAX_AMPLITUDE = 24000  # Slightly below int16 max to avoid clipping


# ---------------------------------------------------------------------------
# Waveform primitives
# ---------------------------------------------------------------------------


def _sine_wave(
    frequency: float, duration: float, amplitude: float = MAX_AMPLITUDE
) -> npt.NDArray[np.int16]:
    """Generate a sine wave.

    Args:
        frequency: Frequency in Hz.
        duration: Duration in seconds.
        amplitude: Peak amplitude (0 to 32767).

    Returns:
        1D numpy array of int16 samples.

    """
    num_samples = int(SAMPLE_RATE * duration)
    time_array = np.linspace(0, duration, num_samples, endpoint=False)
    return (amplitude * np.sin(2.0 * np.pi * frequency * time_array)).astype(np.int16)


def _frequency_sweep(
    start_frequency: float,
    end_frequency: float,
    duration: float,
    amplitude: float = MAX_AMPLITUDE,
) -> npt.NDArray[np.int16]:
    """Generate a sine wave that sweeps from one frequency to another.

    Args:
        start_frequency: Starting frequency in Hz.
        end_frequency: Ending frequency in Hz.
        duration: Duration in seconds.
        amplitude: Peak amplitude.

    Returns:
        1D numpy array of int16 samples.

    """
    num_samples = int(SAMPLE_RATE * duration)
    # Linearly interpolate frequency over time
    frequencies = np.linspace(start_frequency, end_frequency, num_samples)
    # Integrate frequency to get phase (cumulative sum of instantaneous frequency)
    phase = 2.0 * np.pi * np.cumsum(frequencies) / SAMPLE_RATE
    return (amplitude * np.sin(phase)).astype(np.int16)


def _apply_envelope(
    samples: npt.NDArray[np.int16],
    attack: float = 0.01,
    decay: float = 0.0,
) -> npt.NDArray[np.int16]:
    """Apply an attack-decay amplitude envelope to a sample array.

    Args:
        samples: 1D array of audio samples.
        attack: Attack time in seconds (fade in).
        decay: Decay time in seconds (fade out from end). If 0, uses full length.

    Returns:
        Modified sample array with envelope applied.

    """
    num_samples = len(samples)
    envelope = np.ones(num_samples, dtype=np.float64)

    # Attack ramp
    attack_samples = int(SAMPLE_RATE * attack)
    if attack_samples > 0 and attack_samples < num_samples:
        envelope[:attack_samples] = np.linspace(0.0, 1.0, attack_samples)

    # Decay ramp (fade out to zero at the end)
    decay_samples = int(SAMPLE_RATE * decay) if decay > 0 else num_samples
    decay_samples = min(decay_samples, num_samples)

    if decay_samples > 0:
        fade_start = num_samples - decay_samples
        envelope[fade_start:] = np.linspace(1.0, 0.0, decay_samples)

    return (samples.astype(np.float64) * envelope).astype(np.int16)


def _to_stereo(mono_samples: npt.NDArray[np.int16]) -> npt.NDArray[np.int16]:
    """Convert a mono sample array to stereo by duplicating channels.

    Args:
        mono_samples: 1D array of mono samples.

    Returns:
        2D array of shape (num_samples, 2) for stereo playback.

    """
    return np.column_stack((mono_samples, mono_samples))


def _concat_samples(*sample_arrays: npt.NDArray[np.int16]) -> npt.NDArray[np.int16]:
    """Concatenate multiple sample arrays sequentially.

    Args:
        *sample_arrays: Variable number of 1D sample arrays.

    Returns:
        Single concatenated 1D array.

    """
    return np.concatenate(sample_arrays)


def _make_sound(mono_samples: npt.NDArray[np.int16], volume: float = 0.5) -> pygame.mixer.Sound:
    """Create a pygame Sound object from mono samples.

    Args:
        mono_samples: 1D array of int16 mono samples.
        volume: Playback volume (0.0 to 1.0).

    Returns:
        A pygame.mixer.Sound ready for playback.

    """
    stereo = _to_stereo(mono_samples)
    # pygame.sndarray.make_sound has incomplete type stubs for its ndarray parameter
    sound: pygame.mixer.Sound = pygame.sndarray.make_sound(stereo)  # pyright: ignore[reportUnknownMemberType]
    sound.set_volume(volume)
    return sound


# ---------------------------------------------------------------------------
# Sound effect generators
# ---------------------------------------------------------------------------


def _generate_jump_sound() -> pygame.mixer.Sound:
    """Generate a short rising tone for jumping.

    A quick sine sweep from low to high pitch with fast attack and decay.

    Returns:
        A pygame Sound object with the jump effect.

    """
    sweep = _frequency_sweep(
        start_frequency=220,
        end_frequency=660,
        duration=0.12,
        amplitude=MAX_AMPLITUDE,
    )
    shaped = _apply_envelope(sweep, attack=0.005, decay=0.08)
    return _make_sound(shaped, volume=0.35)


def _generate_land_sound() -> pygame.mixer.Sound:
    """Generate a brief low thud for landing.

    A very short burst of low-frequency tone with rapid decay.

    Returns:
        A pygame Sound object with the landing effect.

    """
    thud = _sine_wave(frequency=80, duration=0.06, amplitude=MAX_AMPLITUDE)
    shaped = _apply_envelope(thud, attack=0.002, decay=0.05)
    return _make_sound(shaped, volume=0.25)


def _generate_collect_sound() -> pygame.mixer.Sound:
    """Generate a cheerful ascending arpeggio for collecting a scarab.

    Three quick ascending notes (C5, E5, G5) played in rapid succession.

    Returns:
        A pygame Sound object with the collect effect.

    """
    note_duration = 0.06
    # C5=523, E5=659, G5=784 Hz (major triad)
    note_c = _sine_wave(frequency=523, duration=note_duration)
    note_e = _sine_wave(frequency=659, duration=note_duration)
    note_g = _sine_wave(frequency=784, duration=note_duration)

    note_c = _apply_envelope(note_c, attack=0.003, decay=0.04)
    note_e = _apply_envelope(note_e, attack=0.003, decay=0.04)
    note_g = _apply_envelope(note_g, attack=0.003, decay=0.04)

    arpeggio = _concat_samples(note_c, note_e, note_g)
    return _make_sound(arpeggio, volume=0.3)


def _generate_death_sound() -> pygame.mixer.Sound:
    """Generate a descending tone for player death.

    A sine sweep dropping from high to low pitch.

    Returns:
        A pygame Sound object with the death effect.

    """
    sweep = _frequency_sweep(
        start_frequency=500,
        end_frequency=80,
        duration=0.3,
        amplitude=MAX_AMPLITUDE,
    )
    shaped = _apply_envelope(sweep, attack=0.005, decay=0.2)
    return _make_sound(shaped, volume=0.4)


def _generate_game_over_sound() -> pygame.mixer.Sound:
    """Generate a slow descending tone sequence for game over.

    Three descending notes with longer sustain, creating a somber effect.

    Returns:
        A pygame Sound object with the game over effect.

    """
    note_duration = 0.25
    # Descending minor: E4=330, C4=262, A3=220
    note_e = _sine_wave(frequency=330, duration=note_duration)
    note_c = _sine_wave(frequency=262, duration=note_duration)
    note_a = _sine_wave(frequency=220, duration=note_duration * 1.5)

    note_e = _apply_envelope(note_e, attack=0.01, decay=0.15)
    note_c = _apply_envelope(note_c, attack=0.01, decay=0.15)
    note_a = _apply_envelope(note_a, attack=0.01, decay=0.25)

    sequence = _concat_samples(note_e, note_c, note_a)
    return _make_sound(sequence, volume=0.4)


# ---------------------------------------------------------------------------
# Public sound effect holder
# ---------------------------------------------------------------------------


class GameSounds:
    """Lazily-initialized container for all game sound effects.

    Call initialize() after pygame.mixer is ready. All sounds are
    generated from waveform math - no external files needed.
    """

    def __init__(self) -> None:
        """Initialize with placeholder None values."""
        self.jump: pygame.mixer.Sound | None = None
        self.land: pygame.mixer.Sound | None = None
        self.collect: pygame.mixer.Sound | None = None
        self.death: pygame.mixer.Sound | None = None
        self.game_over: pygame.mixer.Sound | None = None
        self._initialized: bool = False

    def initialize(self) -> None:
        """Generate all sound effects. Call after pygame.mixer.init()."""
        if self._initialized:
            return

        try:
            self.jump = _generate_jump_sound()
            self.land = _generate_land_sound()
            self.collect = _generate_collect_sound()
            self.death = _generate_death_sound()
            self.game_over = _generate_game_over_sound()
            self._initialized = True
            log.info('Brave Adventurer sounds generated successfully')
        except Exception:
            log.exception('Failed to generate sounds, playing without audio')

    def play_jump(self) -> None:
        """Play the jump sound effect."""
        if self.jump is not None:
            self.jump.play()

    def play_land(self) -> None:
        """Play the landing sound effect."""
        if self.land is not None:
            self.land.play()

    def play_collect(self) -> None:
        """Play the collectible pickup sound effect."""
        if self.collect is not None:
            self.collect.play()

    def play_death(self) -> None:
        """Play the player death sound effect."""
        if self.death is not None:
            self.death.play()

    def play_game_over(self) -> None:
        """Play the game over sound effect."""
        if self.game_over is not None:
            self.game_over.play()
