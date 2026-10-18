"""Synthesized sound effects for Brave Adventurer.

All sounds are generated from waveform math at startup, at the mixer's
sample rate, by the engine synthesizer (glitchygames.audio.synth).
No external audio files are needed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from glitchygames.audio.exceptions import AudioUnavailableError
from glitchygames.audio.synth import (
    Envelope,
    FloatArray,
    Waveform,
    apply_envelope,
    concatenate,
    frequency_curve,
    oscillator,
    to_sound,
)

if TYPE_CHECKING:
    import pygame

log = logging.getLogger('game')

# Peak level as a fraction of full scale (the original 24000 of 32767, kept as written)
PEAK = 24000 / 32767


# ---------------------------------------------------------------------------
# Waveform primitives
# ---------------------------------------------------------------------------


def _sine(frequency: float, duration: float) -> FloatArray:
    return oscillator(Waveform.SINE, frequency, duration)[0] * PEAK


def _sweep(start_frequency: float, end_frequency: float, duration: float) -> FloatArray:
    frequencies = frequency_curve(start_frequency, end_frequency, duration)
    return oscillator(Waveform.SINE, frequencies, duration)[0] * PEAK


def _fade(samples: FloatArray, *, attack: float, release: float) -> FloatArray:
    """The original attack/fade-out envelope: ramp in, full level, ramp out at the end.

    Returns:
        The shaped samples.

    """
    return apply_envelope(
        samples, Envelope(attack=attack, decay=0.0, sustain_level=1.0, release=release)
    )


# ---------------------------------------------------------------------------
# Sound effect generators
# ---------------------------------------------------------------------------


def _generate_jump_sound() -> pygame.mixer.Sound:
    """Generate a short rising tone for jumping.

    A quick sine sweep from low to high pitch with fast attack and decay.

    Returns:
        A pygame Sound object with the jump effect.

    """
    shaped = _fade(_sweep(220, 660, 0.12), attack=0.005, release=0.08)
    return to_sound(shaped, volume=0.35)


def _generate_land_sound() -> pygame.mixer.Sound:
    """Generate a brief low thud for landing.

    A very short burst of low-frequency tone with rapid decay.

    Returns:
        A pygame Sound object with the landing effect.

    """
    shaped = _fade(_sine(80, 0.06), attack=0.002, release=0.05)
    return to_sound(shaped, volume=0.25)


def _generate_collect_sound() -> pygame.mixer.Sound:
    """Generate a cheerful ascending arpeggio for collecting a scarab.

    Three quick ascending notes (C5, E5, G5) played in rapid succession.

    Returns:
        A pygame Sound object with the collect effect.

    """
    note_duration = 0.06
    # C5=523, E5=659, G5=784 Hz (major triad)
    notes = [
        _fade(_sine(frequency, note_duration), attack=0.003, release=0.04)
        for frequency in (523, 659, 784)
    ]
    return to_sound(concatenate(*notes), volume=0.3)


def _generate_death_sound() -> pygame.mixer.Sound:
    """Generate a descending tone for player death.

    A sine sweep dropping from high to low pitch.

    Returns:
        A pygame Sound object with the death effect.

    """
    shaped = _fade(_sweep(500, 80, 0.3), attack=0.005, release=0.2)
    return to_sound(shaped, volume=0.4)


def _generate_game_over_sound() -> pygame.mixer.Sound:
    """Generate a slow descending tone sequence for game over.

    Three descending notes with longer sustain, creating a somber effect.

    Returns:
        A pygame Sound object with the game over effect.

    """
    note_duration = 0.25
    # Descending minor: E4=330, C4=262, A3=220
    note_e = _fade(_sine(330, note_duration), attack=0.01, release=0.15)
    note_c = _fade(_sine(262, note_duration), attack=0.01, release=0.15)
    note_a = _fade(_sine(220, note_duration * 1.5), attack=0.01, release=0.25)
    return to_sound(concatenate(note_e, note_c, note_a), volume=0.4)


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
        except AudioUnavailableError:
            log.warning('Audio unavailable, Brave Adventurer plays without sound')

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
