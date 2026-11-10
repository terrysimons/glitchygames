"""The CRT power-on's sound: the engine's own instruments, cued by the power-on's frames.

Feature spec 12.1 is the timeline; impl spec 10.1 is the wiring. Every game opens with the CRT
power-on (glitchygames/crt_power_on.py); when its picture plays and ``--crt-power-on-sound`` is
not ``off``, ``GameEngine`` makes a ``CrtPowerOnSound`` (compiling these sounds, a few
milliseconds, the first time in the process) and passes it to the power-on as its
``sound_cues``. The cue points are the picture's own stage starts, as fractions of the sequence:

==========================  ==========================================================
Progress                    Sound
==========================  ==========================================================
0 (the switch)              the power switch's click, then the degauss coil's thump: a 60 Hz
                            hum with its 2nd and 3rd harmonics, swelling over 0.2 s and
                            decaying over 0.5 s
``DOT_STAGE_START``         the flyback whine fades in, reaching full level as the line
                            stage starts (``LINE_STAGE_START``); it fades out as the picture
                            settles
``OPEN_STAGE_START``        static as the picture opens: white noise through a band of FIR
                            filters, decaying until the warm-up (``WARM_UP_STAGE_START``),
                            then thinning out to nothing as the picture settles
``SETTLED_STAGE_START``     the test pattern's 1 kHz bars tone, or channel 3's soft hiss
==========================  ==========================================================

Rules (the power-on's, extended to sound):

- Every sound is an ``Instrument`` requested through ``audio.engine_sound(...)``, the engine's
  own sounds' ``audio.sound``: compiled once per process, on the first power-on that plays, and
  reused by every later power-on and engine context (a second game in one process, the Arcade),
  whatever the ``--sound-cache`` mode, never evicted (the owner, 2026-11-02; impl spec 10.1).
  They are played before any scene exists, so they belong to the audio engine's
  ``SYSTEM_OWNER`` (no scene clean-up stops them).
- No game random stream: the noises have their own fixed seeds (``STATIC_SEED``...), which
  the renderer turns into their own generators (impl spec 6.3).
- ``frame(dt)`` moves the voices by each power-on frame's measured time (impl spec 7.3: no game
  frame has run, and these voices are never game-visible) and takes that frame's audio account,
  so the power-on's work is in no game frame's.
- Each sound starts on the frame nearest its cue point (``at_progress`` predicts the next
  frame's progress from the last step): at 60 fps at most half a frame (8.3 ms) off.
- A skip (any key or button, or the window closing) fades every voice over
  ``SKIP_FADE_MILLISECONDS`` (``SoundHandle.stop``: ``Channel.fadeout``) and cues nothing more.
  SDL_mixer steps that fade once per mixer chunk (512 frames), so it is about two plateaus and
  a halt, not a ramp: whether that is heard is AUD-CRT-003's open question (ruling R41; the
  fallback is engine-rendered fade tails, impl spec risk R5).
- The tail (the bars tone or the hiss) loops and persists into the game:
  ``carry_tail_into_the_game`` asks the audio engine to fade it over ``TAIL_FADE_MILLISECONDS``
  from its next update, which is frame 0's (``AudioEngine.fade_out_at_next_update``).
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instrument import Filter, Instrument, Noise, Source
from glitchygames.audio.spec import EnvelopeSpec
from glitchygames.audio.waves import Harmonics, Wave
from glitchygames.backgrounds import BackgroundPattern
from glitchygames.crt_power_on import (
    DOT_STAGE_START,
    LINE_STAGE_START,
    OPEN_STAGE_START,
    SEQUENCE_SECONDS,
    SETTLED_STAGE_START,
    WARM_UP_STAGE_START,
)

if TYPE_CHECKING:
    from glitchygames.audio.engine import AudioEngine
    from glitchygames.audio.library import Sound
    from glitchygames.audio.voices import SoundHandle

# The sounds' names, in the order they start
POWER_CLICK: Final[str] = 'crt_power_click'
DEGAUSS: Final[str] = 'crt_degauss'
FLYBACK_WHINE: Final[str] = 'crt_flyback_whine'
STATIC: Final[str] = 'crt_static'
BARS_TONE: Final[str] = 'bars_tone'
CHANNEL_THREE_HISS: Final[str] = 'channel_three_hiss'

# Owner-tunable pitches (feature spec 12.1). The degauss coil hums at the mains frequency (60 Hz
# in NTSC lands) and colour bars carry the classic 1 kHz line-up tone
DEGAUSS_HUM_HZ: Final[float] = 60.0
BARS_TONE_HZ: Final[float] = 1000.0
# A real NTSC set's flyback whines at its line rate, 15,734 Hz, which many adults no longer hear.
# This is pitched well below it so more people hear the whine; the owner tunes it by ear (the
# listening sign-off, AUD-CRT-001)
FLYBACK_WHINE_HZ: Final[float] = 9000.0
# The noises' own fixed seeds (impl spec 6.3: never a game random stream). Any fixed values do;
# these are the NTSC colour standard's year, a power switch's and channel 3's (arbitrary)
STATIC_SEED: Final[int] = 1953
POWER_CLICK_SEED: Final[int] = 1938
CHANNEL_THREE_HISS_SEED: Final[int] = 3

# A skip fades everything in 20 ms with no click (AUD-CRT-003); the tail fades over 500 ms once
# the game's first frame runs (feature spec 12.1)
SKIP_FADE_MILLISECONDS: Final[int] = 20
TAIL_FADE_MILLISECONDS: Final[int] = 500
MILLISECONDS_PER_SECOND: Final[float] = 1000.0
# The power switch is thrown as the sequence starts
POWER_SWITCH_PROGRESS: Final[float] = 0.0
# The bus every CRT sound plays on
CRT_BUS: Final[str] = 'effects'

# The click: a high-passed noise snap over a short low body, gone in 30 ms
POWER_CLICK_BODY_HZ: Final[float] = 150.0
POWER_CLICK_SNAP_LOWEST_HZ: Final[float] = 2000.0
POWER_CLICK_SECONDS: Final[float] = 0.03
POWER_CLICK_ATTACK_SECONDS: Final[float] = 0.0005
# The two layers' levels sum to at most full scale, so the click never clips
POWER_CLICK_SNAP_LEVEL: Final[float] = 0.55
POWER_CLICK_BODY_LEVEL: Final[float] = 0.4
POWER_CLICK_VOLUME: Final[float] = 0.5
# The degauss thump: the hum swells, then decays (the brief's values)
DEGAUSS_SWELL_SECONDS: Final[float] = 0.2
DEGAUSS_DECAY_SECONDS: Final[float] = 0.5
DEGAUSS_HARMONICS: Final[Harmonics] = Harmonics(fundamental=1.0, octave=0.4, octave_and_fifth=0.2)
DEGAUSS_VOLUME: Final[float] = 0.5
# The whine fades in over the dot stage, holds until the picture settles, then fades out
FLYBACK_WHINE_FADE_IN_SECONDS: Final[float] = (
    LINE_STAGE_START - DOT_STAGE_START
) * SEQUENCE_SECONDS
FLYBACK_WHINE_HELD_SECONDS: Final[float] = (
    SETTLED_STAGE_START - DOT_STAGE_START
) * SEQUENCE_SECONDS
FLYBACK_WHINE_FADE_OUT_SECONDS: Final[float] = 0.25
FLYBACK_WHINE_VOLUME: Final[float] = 0.05
# The static: white noise band-passed by two FIR filters (high-pass, then low-pass), at full
# level as the picture opens, decaying to a quarter by the warm-up, then thinning out to nothing
# as the picture settles
STATIC_LOWEST_HZ: Final[float] = 400.0
STATIC_HIGHEST_HZ: Final[float] = 7000.0
STATIC_ATTACK_SECONDS: Final[float] = 0.005
STATIC_OPENING_SECONDS: Final[float] = (WARM_UP_STAGE_START - OPEN_STAGE_START) * SEQUENCE_SECONDS
STATIC_THINNING_SECONDS: Final[float] = (
    SETTLED_STAGE_START - WARM_UP_STAGE_START
) * SEQUENCE_SECONDS
STATIC_WARM_UP_LEVEL: Final[float] = 0.25
STATIC_VOLUME: Final[float] = 0.3
# The tail loops one buffer of this length: a whole number of the tone's cycles, so the loop has
# no seam (1000 cycles of 1 kHz)
TAIL_LOOP_SECONDS: Final[float] = 1.0
BARS_TONE_VOLUME: Final[float] = 0.12
CHANNEL_THREE_HISS_HIGHEST_HZ: Final[float] = 5000.0
# Low-passed white noise overshoots full scale now and then: the layer is at half level
CHANNEL_THREE_HISS_LEVEL: Final[float] = 0.5
CHANNEL_THREE_HISS_VOLUME: Final[float] = 0.24
# A level held from the first sample to the last, with no fades: the tail's buffer loops, so a
# fade at either end would be heard at every pass (hence also hard_edges on its instruments)
HELD_ENVELOPE: Final[EnvelopeSpec] = EnvelopeSpec(attack=0.0, decay=0.0, sustain=1.0, release=0.0)


@dataclasses.dataclass(frozen=True, slots=True)
class CrtSound:
    """One sound of the power-on and where it is cued.

    Attributes:
        name: The sound's name (the cue's).
        progress: The sequence's progress it starts at (0 to 1).
        instrument: How it sounds.
        pitch: Its pitch in hertz, or None for a noise.
        length: Seconds it is held before its release.
        volume: The play's volume, 0-1.
        is_tail: Whether it is the tail carried into the game (it loops and persists).
    """

    name: str
    progress: float
    instrument: Instrument
    pitch: float | None
    length: float
    volume: float
    is_tail: bool = False


POWER_CLICK_SOUND: Final[CrtSound] = CrtSound(
    name=POWER_CLICK,
    progress=POWER_SWITCH_PROGRESS,
    instrument=Instrument(
        sources={
            'snap': Source(
                Noise('white', seed=POWER_CLICK_SEED),
                level=POWER_CLICK_SNAP_LEVEL,
                filter=Filter('high_pass', POWER_CLICK_SNAP_LOWEST_HZ),
            ),
            'body': Source('sine', level=POWER_CLICK_BODY_LEVEL),
        },
        envelope=EnvelopeSpec(
            attack=POWER_CLICK_ATTACK_SECONDS,
            decay=POWER_CLICK_SECONDS - POWER_CLICK_ATTACK_SECONDS,
            sustain=0.0,
            release=0.0,
            curve='exponential',
        ),
    ),
    pitch=POWER_CLICK_BODY_HZ,
    length=POWER_CLICK_SECONDS,
    volume=POWER_CLICK_VOLUME,
)
DEGAUSS_SOUND: Final[CrtSound] = CrtSound(
    name=DEGAUSS,
    progress=POWER_SWITCH_PROGRESS,
    instrument=Instrument(
        wave=Wave.from_harmonics(DEGAUSS_HARMONICS),
        envelope=EnvelopeSpec(
            attack=DEGAUSS_SWELL_SECONDS, decay=DEGAUSS_DECAY_SECONDS, sustain=0.0, release=0.0
        ),
    ),
    pitch=DEGAUSS_HUM_HZ,
    length=DEGAUSS_SWELL_SECONDS + DEGAUSS_DECAY_SECONDS,
    volume=DEGAUSS_VOLUME,
)
FLYBACK_WHINE_SOUND: Final[CrtSound] = CrtSound(
    name=FLYBACK_WHINE,
    progress=DOT_STAGE_START,
    instrument=Instrument(
        wave='sine',
        envelope=EnvelopeSpec(
            attack=FLYBACK_WHINE_FADE_IN_SECONDS,
            decay=0.0,
            sustain=1.0,
            release=FLYBACK_WHINE_FADE_OUT_SECONDS,
        ),
    ),
    pitch=FLYBACK_WHINE_HZ,
    length=FLYBACK_WHINE_HELD_SECONDS,
    volume=FLYBACK_WHINE_VOLUME,
)
STATIC_SOUND: Final[CrtSound] = CrtSound(
    name=STATIC,
    progress=OPEN_STAGE_START,
    instrument=Instrument(
        sources={
            'static': Source(
                Noise('white', seed=STATIC_SEED), filter=Filter('high_pass', STATIC_LOWEST_HZ)
            )
        },
        filter=Filter('low_pass', STATIC_HIGHEST_HZ),
        envelope=EnvelopeSpec(
            attack=STATIC_ATTACK_SECONDS,
            decay=STATIC_OPENING_SECONDS - STATIC_ATTACK_SECONDS,
            sustain=STATIC_WARM_UP_LEVEL,
            release=STATIC_THINNING_SECONDS,
            curve='exponential',
        ),
    ),
    pitch=None,
    length=STATIC_OPENING_SECONDS,
    volume=STATIC_VOLUME,
)
BARS_TONE_SOUND: Final[CrtSound] = CrtSound(
    name=BARS_TONE,
    progress=SETTLED_STAGE_START,
    # A sine starts at 0 and, over whole cycles, ends a step before 0: no fade is needed at
    # either end, and none may be made (it loops)
    instrument=Instrument(wave='sine', envelope=HELD_ENVELOPE, hard_edges=True),
    pitch=BARS_TONE_HZ,
    length=TAIL_LOOP_SECONDS,
    volume=BARS_TONE_VOLUME,
    is_tail=True,
)
CHANNEL_THREE_HISS_SOUND: Final[CrtSound] = CrtSound(
    name=CHANNEL_THREE_HISS,
    progress=SETTLED_STAGE_START,
    # Noise has no seam to hide: each sample is a new step, the loop's included
    instrument=Instrument(
        noise=Noise('white', seed=CHANNEL_THREE_HISS_SEED, level=CHANNEL_THREE_HISS_LEVEL),
        filter=Filter('low_pass', CHANNEL_THREE_HISS_HIGHEST_HZ),
        envelope=HELD_ENVELOPE,
        hard_edges=True,
    ),
    pitch=None,
    length=TAIL_LOOP_SECONDS,
    volume=CHANNEL_THREE_HISS_VOLUME,
    is_tail=True,
)


def crt_sound_schedule(*, background: BackgroundPattern) -> tuple[CrtSound, ...]:
    """The power-on's sounds in cue order, ending on the background's tail.

    Args:
        background: The picture the sequence settles on (the default background).

    Returns:
        The sounds.
    """
    tail = (
        CHANNEL_THREE_HISS_SOUND
        if background is BackgroundPattern.CHANNEL_THREE
        else BARS_TONE_SOUND
    )
    return (POWER_CLICK_SOUND, DEGAUSS_SOUND, FLYBACK_WHINE_SOUND, STATIC_SOUND, tail)


class CrtPowerOnSound:
    """The power-on's sound cues (``crt_power_on.PowerOnSoundCues``) on an audio engine.

    Attributes:
        audio: The audio engine the sounds play on.
        schedule: The sounds in cue order.
        sounds: Each sound by name, compiled (or the process's compile reused) as the cues are
            made.
        tail_handle: The tail's voice once it started, else None.
    """

    def __init__(self, *, audio: AudioEngine, background: BackgroundPattern) -> None:
        """Get every sound of the sequence before it starts (impl spec 6.5): once per process.

        Args:
            audio: The audio engine (the context's, made with the game engine's options).
            background: The picture the sequence settles on: the bars tone for the test
                pattern, the hiss for channel 3.
        """
        self.audio = audio
        self.schedule = crt_sound_schedule(background=background)
        self.sounds: dict[str, Sound] = {
            crt_sound.name: audio.engine_sound(
                crt_sound.instrument, pitch=crt_sound.pitch, length=crt_sound.length
            )
            for crt_sound in self.schedule
        }
        self.tail_handle: SoundHandle | None = None
        self._started_count = 0
        # The progress the last frame cued: the step to the next frame is predicted from it
        self._previous_progress: float | None = None
        self._handles: list[SoundHandle] = []
        self._skipped = False

    def at_progress(self, progress: float) -> None:
        """Start, in order, every sound not started yet whose cue is nearest this frame (R42).

        A cue starts on this frame when its point is reached, or when it is nearer this frame
        than the next: the next frame's progress is predicted from this frame's step (the last
        frame's progress to this one's), so at a steady frame rate a sound starts at most half
        a frame from its point. The first frame has no step yet and starts only what it
        reached. Nothing starts after a skip.

        Args:
            progress: The progress the frame draws (0 to 1).
        """
        if self._skipped:
            return
        step = (
            0.0 if self._previous_progress is None else max(0.0, progress - self._previous_progress)
        )
        self._previous_progress = progress
        nearest_this_frame_up_to = progress + step / 2.0
        while (
            self._started_count < len(self.schedule)
            and self.schedule[self._started_count].progress <= nearest_this_frame_up_to
        ):
            self._start(self.schedule[self._started_count])
            self._started_count += 1

    def frame(self, dt: float) -> None:
        """Move the voices by a power-on frame's measured time, before any game frame.

        No scene exists: only the engine's own voices play. The frame's audio account is taken
        (and dropped) so the power-on's work is in no game frame's.

        Args:
            dt: The frame's measured seconds.
        """
        self.audio.update(
            dt=dt, active_scene=None, previous_scene=None, active_transitions=(), paused_owners=()
        )
        self.audio.take_frame_account()

    def skip(self) -> None:
        """Fade every voice the power-on started over 20 ms; cue nothing more."""
        self._skipped = True
        for handle in self._handles:
            handle.stop(fade=SKIP_FADE_MILLISECONDS / MILLISECONDS_PER_SECOND)

    def carry_tail_into_the_game(self) -> None:
        """Fade the tail over 500 ms from the audio engine's next update (frame 0's).

        After a skip (everything already fading) or before the tail started, nothing.
        """
        if self._skipped or self.tail_handle is None:
            return
        self.audio.fade_out_at_next_update(
            self.tail_handle, fade=TAIL_FADE_MILLISECONDS / MILLISECONDS_PER_SECOND
        )

    def _start(self, crt_sound: CrtSound) -> None:
        """Play one sound: the tail looping and persisting, the rest once."""
        handle = self.sounds[crt_sound.name].play(
            volume=crt_sound.volume,
            bus=CRT_BUS,
            loop=crt_sound.is_tail,
            persist=crt_sound.is_tail,
        )
        self._handles.append(handle)
        if crt_sound.is_tail:
            self.tail_handle = handle
