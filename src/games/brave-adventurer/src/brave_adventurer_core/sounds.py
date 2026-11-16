"""Brave Adventurer's sound effects: five effects, played through the engine's sound library.

Each is an ``Effect`` (glitchygames.audio.effects: tones mixed straight), so the library compiles
it once, caches it (on disk too, under ``--sound-cache disk``) and plays it on its own channels.
They were ``_generate_*_sound()`` functions on the synth toolkit; as effects their 16-bit samples
are byte-identical to what those made (tests/core/test_brave_adventurer_sounds.py), with
``normalize=False`` because the old functions scaled by ``PEAK`` and never rescaled the result,
and each plays at the volume the old function set. No external audio files are needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from glitchygames.audio.effects import Effect, Tone
from glitchygames.audio.library import Sound  # ruff: ignore[typing-only-first-party-import] - pydantic checks BraveAdventurerSounds' fields at runtime
from glitchygames.audio.synth import Envelope, Waveform

if TYPE_CHECKING:
    from glitchygames.audio.engine import AudioEngine

# Peak level as a fraction of full scale (the original 24000 of 32767, kept as written)
PEAK: Final[float] = 24000 / 32767


def _fade(*, attack: float, release: float) -> Envelope:
    """The original attack/fade-out envelope: ramp in, full level, ramp out at the end.

    Returns:
        The envelope.
    """
    return Envelope(attack=attack, decay=0.0, sustain_level=1.0, release=release)


def _sine(  # ruff: ignore[too-many-arguments] - one tone's settings, each named at every call
    frequency: float,
    *,
    duration: float,
    attack: float,
    release: float,
    end_frequency: float | None = None,
    offset: float = 0.0,
) -> Tone:
    """A sine tone at PEAK (a sweep when an end frequency is given), faded in and out.

    Returns:
        The tone.
    """
    return Tone(
        waveform=Waveform.SINE,
        start_frequency=frequency,
        end_frequency=end_frequency,
        duration=duration,
        envelope=_fade(attack=attack, release=release),
        volume=PEAK,
        offset=offset,
    )


# A quick rising sine sweep, fast attack and decay
JUMP: Final[Effect] = Effect(
    name='jump',
    tones=(_sine(220, end_frequency=660, duration=0.12, attack=0.005, release=0.08),),
    volume=0.35,
    normalize=False,
)
# A very short low thud
LAND: Final[Effect] = Effect(
    name='land',
    tones=(_sine(80, duration=0.06, attack=0.002, release=0.05),),
    volume=0.25,
    normalize=False,
)
# Three quick ascending notes, C5, E5 and G5 (523, 659 and 784 Hz: a major triad)
COLLECT: Final[Effect] = Effect(
    name='collect',
    tones=tuple(
        _sine(frequency, duration=0.06, attack=0.003, release=0.04, offset=index * 0.06)
        for index, frequency in enumerate((523, 659, 784))
    ),
    volume=0.3,
    normalize=False,
)
# A sine sweep dropping from high to low
DEATH: Final[Effect] = Effect(
    name='death',
    tones=(_sine(500, end_frequency=80, duration=0.3, attack=0.005, release=0.2),),
    volume=0.4,
    normalize=False,
)
# Three slow descending notes, E4, C4 and A3 (330, 262 and 220 Hz), the last held longer
GAME_OVER: Final[Effect] = Effect(
    name='game_over',
    tones=(
        _sine(330, duration=0.25, attack=0.01, release=0.15),
        _sine(262, duration=0.25, attack=0.01, release=0.15, offset=0.25),
        _sine(220, duration=0.375, attack=0.01, release=0.25, offset=0.5),
    ),
    volume=0.4,
    normalize=False,
)
EFFECTS: Final[dict[str, Effect]] = {
    effect.name: effect for effect in (JUMP, LAND, COLLECT, DEATH, GAME_OVER)
}


class BraveAdventurerSounds(BaseModel):
    """The game's five sounds, ready to play (each a ``Sound`` from the scene's audio engine)."""

    model_config = ConfigDict(frozen=True, extra='forbid', arbitrary_types_allowed=True)

    jump: Sound
    land: Sound
    collect: Sound
    death: Sound
    game_over: Sound


def request_sounds(*, audio: AudioEngine) -> BraveAdventurerSounds:
    """Ask the audio engine for each effect (compiled on its first request, cached after).

    Args:
        audio: The scene's audio engine (``scene_manager.audio``).

    Returns:
        The five sounds.
    """
    return BraveAdventurerSounds(**{name: audio.sound(effect) for name, effect in EFFECTS.items()})
