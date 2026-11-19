"""Tests for StartupSounds: a game's declared sounds compiled in slices, then finished.

plans/2026-11-14-sound-migration.md, decision 6: the engine compiles every sound a game declares
during the CRT power-on's idle time (``compile_for`` each frame), then compiles what is left
before the game is built (``finish``).
"""

from __future__ import annotations

import pytest

from glitchygames.audio.effects import Effect, Tone
from glitchygames.audio.engine import AudioEngine
from glitchygames.audio.instrument import Instrument
from glitchygames.audio.mix import Mix, MixPart
from glitchygames.audio.startup import StartupSounds
from glitchygames.audio.synth import Envelope, Waveform
from glitchygames.audio.voices import ChannelPartition

NO_CHANNELS = ChannelPartition(live=(), library=(), legacy_count=0)


def _effect(name: str, frequency: float) -> Effect:
    """A short one-tone effect."""
    envelope = Envelope(attack=0.001, decay=0.0, sustain_level=1.0, release=0.01)
    tone = Tone(waveform=Waveform.SINE, start_frequency=frequency, duration=0.02, envelope=envelope)
    return Effect(name=name, tones=(tone,))


EFFECTS = tuple(_effect(f'tone_{index}', 220.0 + 20.0 * index) for index in range(5))


class CostlyAudio:
    """An audio engine stand-in whose every sound costs a fixed time on a fake counter."""

    def __init__(self, *, seconds_per_sound: float) -> None:
        """Start the counter at zero."""
        self.now = 0.0
        self.seconds_per_sound = seconds_per_sound
        self.requested: list[object] = []

    def sound(self, source: object) -> str:
        """Record the request and spend its time.

        Returns:
            A name for the sound.
        """
        self.requested.append(source)
        self.now += self.seconds_per_sound
        return f'sound {len(self.requested)}'

    def counter(self) -> float:
        """Return the fake time.

        Returns:
            Seconds.
        """
        return self.now


def _startup(audio: CostlyAudio) -> StartupSounds:
    return StartupSounds(audio=audio, sources=EFFECTS, counter=audio.counter)  # type: ignore[arg-type]


def test_a_slice_stops_once_its_time_is_used():
    """With 3 ms a sound and a 7 ms slice, three compile (the third crosses the budget)."""
    audio = CostlyAudio(seconds_per_sound=0.003)
    startup = _startup(audio)

    startup.compile_for(0.007)

    assert audio.requested == list(EFFECTS[:3])
    assert startup.remaining == 2


def test_a_slice_always_compiles_one_sound():
    """Even with no time, a slice makes progress (a sound longer than a frame delays it once)."""
    audio = CostlyAudio(seconds_per_sound=0.050)
    startup = _startup(audio)

    startup.compile_for(0.0)

    assert audio.requested == [EFFECTS[0]]


def test_finish_compiles_the_rest_once_in_order():
    """Finish takes what the slices left; each sound is asked for exactly once, in order."""
    audio = CostlyAudio(seconds_per_sound=0.003)
    startup = _startup(audio)
    startup.compile_for(0.004)

    startup.finish()
    startup.finish()
    startup.compile_for(1.0)

    assert audio.requested == list(EFFECTS)
    assert startup.remaining == 0


def test_with_nothing_declared_every_call_does_nothing():
    """A game that declares no sounds compiles none."""
    audio = CostlyAudio(seconds_per_sound=0.003)
    startup = StartupSounds(audio=audio, sources=(), counter=audio.counter)  # type: ignore[arg-type]

    startup.compile_for(1.0)
    startup.finish()

    assert audio.requested == []


def test_finished_sounds_are_the_engines_compiled_sounds():
    """On a real audio engine, every declared sound is compiled once finish returns."""
    audio = AudioEngine(partition=NO_CHANNELS)
    startup = StartupSounds(audio=audio, sources=EFFECTS)

    startup.finish()

    for effect in EFFECTS:
        assert audio.sound(effect).is_compiled
    assert audio.sounds.statistics().compiles == len(EFFECTS)


def test_the_default_counter_is_the_engines_raw_counter(mocker):
    """Without a counter it reads glitchygames.clock's, looked up when called."""
    counter = mocker.patch('glitchygames.clock.raw_counter_seconds', side_effect=[0.0, 1.0])
    audio = AudioEngine(partition=NO_CHANNELS)
    startup = StartupSounds(audio=audio, sources=EFFECTS)

    startup.compile_for(0.5)

    assert startup.remaining == len(EFFECTS) - 1
    assert counter.call_count == 2


@pytest.mark.parametrize('seconds', [-1.0, float('nan')])
def test_a_slice_of_no_real_length_still_compiles_one(seconds):
    """A negative or NaN budget is treated as none: one sound, then the slice ends."""
    audio = CostlyAudio(seconds_per_sound=0.001)
    startup = _startup(audio)

    startup.compile_for(seconds)

    assert len(audio.requested) == 1


def test_a_declared_mix_is_built_at_start_and_never_again():
    """A score declared as mixes is built before the game's first frame; its requests build none."""
    mix = Mix(
        name='score',
        parts=(MixPart(instrument=Instrument(wave='sine'), notes='A4:0.5 C5:0.5', volume=0.5),),
        loop_seconds=1.0,
    )
    audio = AudioEngine(partition=NO_CHANNELS)
    startup = StartupSounds(audio=audio, sources=(mix,))

    startup.finish()
    built = audio.sounds.statistics().compiles
    requested = audio.sound(mix)

    assert built == 1
    assert requested.is_compiled
    assert requested.length == 1.0
    assert audio.sounds.statistics().compiles == built
