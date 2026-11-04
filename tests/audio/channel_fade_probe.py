"""The recording side of tests/audio/test_channel_fades.py: channel fades on SDL's disk driver.

Run as ``python -m tests.audio.channel_fade_probe CASE`` from the repository root, with
``SDL_AUDIODRIVER=disk`` and ``SDL_DISKAUDIOFILE`` naming the recording (the way
scripts/audio_glitch_probe.py's ``dsp`` mode records). It plays a smooth pure tone on one mixer
channel, makes the mixer calls the voice table makes for CASE at a few moments (so at different
phases of the tone and of the mixer chunk), and lets each trial run out in silence before the
next. The parent test reads the recording and measures the steps (feature spec 16.1).

Cases (impl spec 7.1, 7.2 and 10.1: the [Open] items M1 verifies, Task 13 of
plans/2026-11-02-sound-engine-m1-implementation.md):

- ``steal-immediate``: ``Channel.fadeout(10)`` (a steal) and ``Channel.play`` of the stealer on
  the same channel at once.
- ``steal-delayed``: the same with one frame between them (the voice table's delayed play).
- ``bus-fade``: the channel's gains stepped once per frame from 1 to 0 over 50 ms, as a volume
  or bus fade reaches the channel through ``Channel.set_volume`` (``VoiceTable.advance``).
- ``crt-skip``: ``Channel.fadeout(20)`` on a 1 kHz tone (the CRT skip on the bars tone).

The tones are built here rather than compiled by the engine: the measurement is of the mixer's
handling of a channel, and a pure tone with a 20 ms raised-cosine attack has a known largest
step of its own to compare against.
"""

from __future__ import annotations

import sys

import numpy as np
import pygame

from glitchygames import clock
from glitchygames.audio.diagnostics import DEFAULT_BUFFER_SAMPLES, DEFAULT_SAMPLE_RATE
from glitchygames.audio.voices import (
    MILLISECONDS_PER_SECOND,
    STEAL_FADE_MILLISECONDS,
    constant_power_gains,
)
from glitchygames.crt_power_on_sound import BARS_TONE_HZ, SKIP_FADE_MILLISECONDS
from glitchygames.timing import DEFAULT_TARGET_FPS

STEAL_IMMEDIATE = 'steal-immediate'
STEAL_DELAYED = 'steal-delayed'
BUS_FADE = 'bus-fade'
CRT_SKIP = 'crt-skip'
CASES = (STEAL_IMMEDIATE, STEAL_DELAYED, BUS_FADE, CRT_SKIP)

# The stolen voice's tone and the stealer's (different, so the switch is a real change)
STOLEN_TONE_HZ = 440.0
STEALER_TONE_HZ = 660.0
# The tone the bus fade steps
BUS_FADE_TONE_HZ = 440.0
TONE_AMPLITUDE = 0.5
TONE_SECONDS = 2.0
# A raised-cosine attack this long adds under 3% to a 440 Hz tone's largest step
ATTACK_SECONDS = 0.020
# Impl spec 7.2: a bus fade of 50 ms, applied once per frame
BUS_FADE_SECONDS = 0.050
FRAME_SECONDS = 1.0 / DEFAULT_TARGET_FPS
# Trials per recording; each starts at another moment, so at another tone and chunk phase
TRIAL_COUNT = 6
# Playing time before a trial's action: a base plus a step that walks through the chunk phases
LEAD_SECONDS = 0.120
LEAD_STEP_SECONDS = 0.0137
# After the action: let the result play, fade it out slowly (a step far below the tone's own
# at SDL_mixer's per-chunk volume), then a silence that separates the trials
AFTER_ACTION_SECONDS = 0.150
CLOSING_FADE_MILLISECONDS = 400
SILENCE_SECONDS = 0.200
INT16_FULL_SCALE = 32767


def tone(*, frequency: float, sample_rate: int) -> np.ndarray:
    """A looping pure tone with a raised-cosine attack, as mono float samples.

    Returns:
        The samples, -1 to 1.
    """
    frame_count = round(TONE_SECONDS * sample_rate)
    time_points = np.arange(frame_count) / sample_rate
    attack_frames = round(ATTACK_SECONDS * sample_rate)
    envelope = np.ones(frame_count)
    envelope[:attack_frames] = 0.5 - 0.5 * np.cos(np.pi * np.arange(attack_frames) / attack_frames)
    return TONE_AMPLITUDE * envelope * np.sin(2.0 * np.pi * frequency * time_points)


def as_int16_stereo(samples: np.ndarray) -> np.ndarray:
    """Mono float samples as the mixer's signed 16-bit stereo frames.

    Returns:
        An (n, 2) int16 array.
    """
    mono = np.round(samples * INT16_FULL_SCALE).astype(np.int16)
    return np.ascontiguousarray(np.column_stack((mono, mono)))


def tones_for(case: str) -> tuple[float, ...]:
    """The tone frequencies a case plays (the first is the one sounding when the trial acts).

    Returns:
        The frequencies in Hz.
    """
    if case in {STEAL_IMMEDIATE, STEAL_DELAYED}:
        return (STOLEN_TONE_HZ, STEALER_TONE_HZ)
    if case == CRT_SKIP:
        return (BARS_TONE_HZ,)
    return (BUS_FADE_TONE_HZ,)


def start(channel: pygame.mixer.Channel, sound: pygame.mixer.Sound | None) -> None:
    """Play a looping sound the way ``VoiceTable._start`` does: play, then the gains.

    pygame resets a channel's volume on play, so the table sets the gains after it (impl spec
    7.2); here at full volume, centred.
    """
    channel.play(sound, loops=-1)
    channel.set_volume(*constant_power_gains(pan=0.0, gain=1.0))


def act(case: str, *, channel: pygame.mixer.Channel, stealer: pygame.mixer.Sound | None) -> None:
    """Make the mixer calls of ``case`` on the playing channel."""
    if case == STEAL_IMMEDIATE:
        channel.fadeout(STEAL_FADE_MILLISECONDS)
        start(channel, stealer)
    elif case == STEAL_DELAYED:
        channel.fadeout(STEAL_FADE_MILLISECONDS)
        clock.raw_sleep(FRAME_SECONDS)
        start(channel, stealer)
    elif case == BUS_FADE:
        # VoiceTable._step_volume_fade with one frame's dt per step, then _apply_gains
        elapsed = 0.0
        gain = 1.0
        while gain > 0.0:
            elapsed += FRAME_SECONDS
            gain = max(0.0, 1.0 - elapsed / BUS_FADE_SECONDS)
            channel.set_volume(*constant_power_gains(pan=0.0, gain=gain))
            clock.raw_sleep(FRAME_SECONDS)
    else:
        channel.fadeout(SKIP_FADE_MILLISECONDS)


def record(case: str) -> None:
    """Play the case's trials into the disk driver's recording."""
    pygame.mixer.init(
        frequency=DEFAULT_SAMPLE_RATE, size=-16, channels=2, buffer=DEFAULT_BUFFER_SAMPLES
    )
    sounds = [
        pygame.sndarray.make_sound(
            as_int16_stereo(tone(frequency=frequency, sample_rate=DEFAULT_SAMPLE_RATE))
        )
        for frequency in tones_for(case)
    ]
    stealer = sounds[1] if len(sounds) > 1 else None
    channel = pygame.mixer.Channel(0)
    for trial in range(TRIAL_COUNT):
        start(channel, sounds[0])
        clock.raw_sleep(LEAD_SECONDS + trial * LEAD_STEP_SECONDS)
        act(case, channel=channel, stealer=stealer)
        clock.raw_sleep(AFTER_ACTION_SECONDS)
        channel.fadeout(CLOSING_FADE_MILLISECONDS)
        clock.raw_sleep(CLOSING_FADE_MILLISECONDS / MILLISECONDS_PER_SECOND + SILENCE_SECONDS)
    pygame.mixer.quit()  # Flushes the recording


def own_largest_step(case: str) -> float:
    """The largest sample-to-sample step of the case's own tones, as the mixer receives them.

    The tones play centred, so each side carries ``cos(pi / 4)`` of the tone (impl spec 7.2).

    Returns:
        The step, in -1..1 units.
    """
    centre_gain = constant_power_gains(pan=0.0, gain=1.0)[0]
    steps = []
    for frequency in tones_for(case):
        left = as_int16_stereo(tone(frequency=frequency, sample_rate=DEFAULT_SAMPLE_RATE))[:, 0]
        steps.append(float(np.max(np.abs(np.diff(left.astype(np.float64))))) / INT16_FULL_SCALE)
    return max(steps) * centre_gain


def main(argv: list[str]) -> int:
    """Record one case (the disk driver's file is named by ``SDL_DISKAUDIOFILE``).

    Returns:
        0, or 2 for an unknown case.
    """
    if len(argv) != 1 or argv[0] not in CASES:
        sys.stderr.write(f'usage: python -m tests.audio.channel_fade_probe {"|".join(CASES)}\n')
        return 2
    record(argv[0])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
