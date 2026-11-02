"""The CRT power-on's sound (glitchygames/crt_power_on_sound.py; feature spec 12.1, impl spec 10.1).

The cues are driven the way the power-on's frames drive them (``at_progress`` with the drawn
progress, ``frame`` with the frame's time, ``skip`` on a press), against a recording stand-in for
the audio engine whose sounds are real compiled sounds, against a real ``AudioEngine`` on SDL's
dummy mixer, and inside real engine runs.
"""

from __future__ import annotations

import asyncio
import itertools
import math
import sys
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np
import pytest

from glitchygames import crt_power_on, crt_power_on_sound, randomness
from glitchygames.audio import OfflineEvent, render_to_file
from glitchygames.audio.engine import SYSTEM_OWNER, AudioEngine, discard_audio_engine
from glitchygames.audio.library import CacheMode
from glitchygames.audio.voices import VoiceTable
from glitchygames.backgrounds import BackgroundPattern
from glitchygames.crt_power_on import (
    DOT_STAGE_START,
    FRAME_SECONDS,
    OPEN_STAGE_START,
    SEQUENCE_SECONDS,
    SETTLED_STAGE_START,
    PowerOnOutcome,
)
from glitchygames.crt_power_on_sound import (
    BARS_TONE,
    BARS_TONE_HZ,
    CHANNEL_THREE_HISS,
    DEGAUSS,
    DEGAUSS_HUM_HZ,
    FLYBACK_WHINE,
    FLYBACK_WHINE_HZ,
    POWER_CLICK,
    SKIP_FADE_MILLISECONDS,
    STATIC,
    TAIL_FADE_MILLISECONDS,
    CrtPowerOnSound,
)
from glitchygames.engine import game_engine as game_engine_module
from glitchygames.engine_context import EngineContext
from glitchygames.replay.tools.golden_traces import GoldenTraceEngine
from glitchygames.scenes import Scene
from tests import demo_runs
from tests.audio.library_support import make_library, stop_mixer
from tests.audio.voice_support import RecordingChannel, calls_named, start_reserved_mixer

if TYPE_CHECKING:
    from pathlib import Path

    from glitchygames.audio.library import Sound

# 60 frames a second over the 1.2 s sequence: the progress each frame draws
SIXTY_FRAMES_A_SECOND = 73
# Feature spec 12.1: (progress point, the sounds that start there), the test pattern's timeline
TEST_PATTERN_TIMELINE = (
    (0.0, POWER_CLICK),
    (0.0, DEGAUSS),
    (DOT_STAGE_START, FLYBACK_WHINE),
    (OPEN_STAGE_START, STATIC),
    (SETTLED_STAGE_START, BARS_TONE),
)
# AUD-CRT-001: each onset within 10 ms of its progress point
ONSET_TOLERANCE_SECONDS = 0.010
# A sound is heard from its first sample above -60 dBFS (the de-click threshold, 1/1024)
AUDIBLE_LEVEL = 1.0 / 1024.0
# AUD-CRT-003: a simulated key at 0.4 s
SKIP_SECONDS = 0.4
MILLISECONDS_PER_SECOND = 1000
# The engine's mixer buffer, frames per mixing callback (CLAUDE.md, Sound Synthesis: 512)
MIXER_CHUNK_FRAMES = 512
# SDL_mixer's full channel volume (SDL_mixer.h, MIX_MAX_VOLUME)
MIX_MAX_VOLUME = 128
# The discontinuity threshold of this test: no step while fading larger than the tone's own
# largest step (feature spec 16.1's metric; the spec names no number)
DISCONTINUITY_THRESHOLD = 1.0
# How long a cued sound's attack takes to reach the audible level (the onsets measured: < 1 ms)
ATTACK_HEARD_SECONDS = 0.001
ENGINE_ARGUMENTS = ('--resolution', '320x240', '--log-level', 'warning', '--target-fps', '0')


@pytest.fixture(autouse=True)
def _own_context_and_mixer_stopped_afterwards():
    """Each test in its own engine context (its own sounds and waves); the mixer stopped after."""
    with EngineContext(name='crt power-on sound test').active():
        yield
        discard_audio_engine(wait_seconds=0.0)
    stop_mixer()


class RecordedHandle:
    """A recorded play's handle: it records the fades asked of it."""

    def __init__(self) -> None:
        """Start with no fade asked."""
        self.fades: list[float] = []

    def stop(self, *, fade: float) -> bool:
        """Record the fade.

        Returns:
            True: the stand-in voice was playing.
        """
        self.fades.append(fade)
        return True


class RecordingAudioEngine:
    """Stands in for ``AudioEngine``: real compiled sounds, recorded plays, updates and fades.

    ``progress`` is set by the test before each cue, so each play records the progress it
    started at.
    """

    def __init__(self) -> None:
        """Start with a library over the current context and nothing recorded."""
        self.library, _accountant = make_library()
        self.progress = 0.0
        self.plays: list[dict[str, Any]] = []
        self.updates: list[dict[str, Any]] = []
        self.frame_accounts_taken = 0
        self.fades_at_next_update: list[tuple[RecordedHandle, float]] = []

    def sound(self, source, *, pitch=None, length=None) -> Sound:
        """Compile the sound for real; its plays come here.

        Returns:
            The sound.
        """
        sound = self.library.sound(source, scene_sound_directory=None, pitch=pitch, length=length)
        sound.attach_player(self._play)
        return sound

    def _play(self, sound, **playback) -> RecordedHandle:
        handle = RecordedHandle()
        self.plays.append({
            'sound': sound,
            'progress': self.progress,
            'handle': handle,
            **playback,
        })
        return handle

    def update(self, **arguments) -> None:
        """Record an update."""
        self.updates.append(arguments)

    def take_frame_account(self, **_arguments) -> None:
        """Count the frame accounts taken."""
        self.frame_accounts_taken += 1

    def fade_out_at_next_update(self, handle, *, fade: float) -> None:
        """Record the pending fade."""
        self.fades_at_next_update.append((handle, fade))

    def started_names(self, cues: CrtPowerOnSound) -> list[str]:
        """The names of the sounds played, in order (each sound is the cues' by identity).

        Returns:
            The names.
        """
        names = {id(sound): name for name, sound in cues.sounds.items()}
        return [names[id(play['sound'])] for play in self.plays]


def recording_audio_engine() -> RecordingAudioEngine:
    """A recording stand-in for the audio engine.

    Returns:
        The stand-in.
    """
    return RecordingAudioEngine()


def drive(cues: CrtPowerOnSound, audio: RecordingAudioEngine, *, progresses) -> None:
    """Cue each progress, as the power-on's frames do, stamping it on the plays it starts."""
    for progress in progresses:
        audio.progress = float(progress)
        cues.at_progress(float(progress))
        cues.frame(FRAME_SECONDS)


def frame_progresses():
    """The progress drawn at each frame of a 60 fps power-on, the settled moment last.

    Returns:
        The progresses, 0 to 1.
    """
    return np.linspace(0.0, 1.0, SIXTY_FRAMES_A_SECOND)


def read_float_wave(path: Path) -> np.ndarray:
    """Read a mono float32 WAV file render_to_file wrote (its data chunk is last).

    Returns:
        The samples.
    """
    data = path.read_bytes()
    data_chunk = data.rindex(b'data')
    size = int.from_bytes(data[data_chunk + 4 : data_chunk + 8], 'little')
    return np.frombuffer(data[data_chunk + 8 : data_chunk + 8 + size], dtype='<f4').astype(
        np.float64
    )


def rendered_mix(plays, path: Path, *, silence: Sound) -> np.ndarray:
    """Render the plays offline (each at its progress's time and volume) and read the mix.

    ``silence`` is the render's own sound at offset 0 (a sound of level 0), so every play is an
    event at its own time.

    Returns:
        The mix's samples.
    """
    render_to_file(
        silence,
        path,
        sample_format='float32',
        events=[
            OfflineEvent(
                seconds=play['progress'] * SEQUENCE_SECONDS,
                sound=play['sound'],
                volume=play['volume'],
            )
            for play in plays
        ],
    )
    return read_float_wave(path)


def silent_sound(audio: RecordingAudioEngine) -> Sound:
    """A sound of level 0, the offline render's own sound.

    Returns:
        The sound.
    """
    from glitchygames.audio.instrument import Instrument, Source

    return audio.sound(
        Instrument(sources={'nothing': Source('sine', level=0.0)}), pitch=440.0, length=0.01
    )


# --- The cues ---


def test_cues_start_each_sound_at_its_progress_point():
    """Driven through the sequence at 60 fps, the five sounds start in the timeline's order."""
    audio = recording_audio_engine()
    cues = CrtPowerOnSound(audio=audio, background=BackgroundPattern.TEST_PATTERN)
    for progress in np.linspace(0.0, 1.0, SIXTY_FRAMES_A_SECOND):
        cues.at_progress(float(progress))

    assert audio.started_names(cues) == [
        'crt_power_click',
        'crt_degauss',
        'crt_flyback_whine',
        'crt_static',
        'bars_tone',
    ]


def test_each_sound_starts_on_the_frame_nearest_its_point():
    """At 60 fps a cue starts on the frame nearest its point: at most half a frame off (R42)."""
    audio = recording_audio_engine()
    cues = CrtPowerOnSound(audio=audio, background=BackgroundPattern.TEST_PATTERN)

    drive(cues, audio, progresses=frame_progresses())

    step = 1.0 / (SIXTY_FRAMES_A_SECOND - 1)
    assert audio.started_names(cues) == [name for _point, name in TEST_PATTERN_TIMELINE]
    for (point, name), play in zip(TEST_PATTERN_TIMELINE, audio.plays, strict=True):
        assert abs(play['progress'] - point) <= step / 2 + 1e-12, name
    # The whine's point (0.08) is nearer frame 6 (0.0833) than frame 5 (0.0694): not early
    by_name = dict(zip(audio.started_names(cues), audio.plays, strict=True))
    assert by_name[FLYBACK_WHINE]['progress'] == pytest.approx(6 * step)


def test_a_cue_nearer_this_frame_than_the_next_starts_early():
    """Half a frame early beats more than half a frame late.

    The next frame's progress is predicted from the last frame's step.
    """
    audio = recording_audio_engine()
    cues = CrtPowerOnSound(audio=audio, background=BackgroundPattern.TEST_PATTERN)

    # Frames 0.1 apart: the static (0.30) is 0.02 after the frame at 0.28, 0.08 before 0.38
    drive(cues, audio, progresses=[0.0, 0.18, 0.28])

    assert audio.started_names(cues)[-1] == STATIC


def test_the_first_frame_starts_only_what_it_reached():
    """With no step yet to predict from, the first frame starts only cues at or before it."""
    audio = recording_audio_engine()
    cues = CrtPowerOnSound(audio=audio, background=BackgroundPattern.TEST_PATTERN)

    cues.at_progress(0.07)

    assert audio.started_names(cues) == [POWER_CLICK, DEGAUSS]


def test_channel_three_gets_the_hiss_not_the_tone():
    """Settling on channel 3, the tail is a soft hiss; the tone is never even compiled."""
    audio = recording_audio_engine()
    cues = CrtPowerOnSound(audio=audio, background=BackgroundPattern.CHANNEL_THREE)

    drive(cues, audio, progresses=frame_progresses())

    assert audio.started_names(cues) == [
        'crt_power_click',
        'crt_degauss',
        'crt_flyback_whine',
        'crt_static',
        'channel_three_hiss',
    ]
    assert BARS_TONE not in cues.sounds


def test_a_late_frame_starts_every_sound_it_passed_once_in_order():
    """A long first frame (or the sequence ending) catches up; no sound ever starts twice."""
    audio = recording_audio_engine()
    cues = CrtPowerOnSound(audio=audio, background=BackgroundPattern.TEST_PATTERN)

    cues.at_progress(1.0)
    cues.at_progress(1.0)

    assert audio.started_names(cues) == [name for _point, name in TEST_PATTERN_TIMELINE]


def test_only_the_tail_persists_and_loops():
    """The tone (or hiss) is carried into the game; everything else ends on its own."""
    audio = recording_audio_engine()
    cues = CrtPowerOnSound(audio=audio, background=BackgroundPattern.TEST_PATTERN)

    cues.at_progress(1.0)

    by_name = dict(zip(audio.started_names(cues), audio.plays, strict=True))
    assert by_name[BARS_TONE]['persist'] is True
    assert by_name[BARS_TONE]['loop'] is True
    for name in (POWER_CLICK, DEGAUSS, FLYBACK_WHINE, STATIC):
        assert by_name[name]['persist'] is False
        assert by_name[name]['loop'] is False


def test_each_frame_moves_the_engines_voices_by_its_time():
    """``frame`` is the audio update before frame 0: no scene, the frame's own measured time."""
    audio = recording_audio_engine()
    cues = CrtPowerOnSound(audio=audio, background=BackgroundPattern.TEST_PATTERN)

    cues.frame(0.02)

    assert audio.updates == [
        {
            'dt': 0.02,
            'active_scene': None,
            'previous_scene': None,
            'active_transitions': (),
            'paused_owners': (),
        }
    ]
    # The power-on's audio work belongs to no game frame: each power-on frame takes its own
    assert audio.frame_accounts_taken == 1


def test_the_sounds_are_compiled_before_the_sequence_starts():
    """Impl spec 6.5 item 4: the CRT's sounds compile as the cues are made, not as they play."""
    audio = recording_audio_engine()

    cues = CrtPowerOnSound(audio=audio, background=BackgroundPattern.TEST_PATTERN)

    assert all(sound.is_compiled for sound in cues.sounds.values())
    assert audio.plays == []


# --- The sounds themselves ---


def test_the_sounds_are_the_timelines():
    """The hum is 60 Hz, the tone 1 kHz, the whine below a real set's 15,734 Hz but audible."""
    audio = recording_audio_engine()
    cues = CrtPowerOnSound(audio=audio, background=BackgroundPattern.TEST_PATTERN)
    rate = cues.sounds[BARS_TONE].sample_rate

    assert DEGAUSS_HUM_HZ == 60.0
    assert BARS_TONE_HZ == 1000.0
    assert 8000.0 <= FLYBACK_WHINE_HZ <= 10_000.0
    assert strongest_frequency(cues.sounds[BARS_TONE], rate=rate) == pytest.approx(1000.0, abs=1)
    assert strongest_frequency(cues.sounds[FLYBACK_WHINE], rate=rate) == pytest.approx(
        FLYBACK_WHINE_HZ, abs=2
    )
    assert strongest_frequency(cues.sounds[DEGAUSS], rate=rate) == pytest.approx(60.0, abs=2)


def strongest_frequency(sound: Sound, *, rate: int) -> float:
    """The frequency of a sound's strongest spectral bin.

    Returns:
        Hertz.
    """
    assert sound.samples_float is not None
    magnitudes = np.abs(np.fft.rfft(sound.samples_float))
    return float(np.fft.rfftfreq(len(sound.samples_float), 1.0 / rate)[np.argmax(magnitudes)])


def test_the_tail_loops_without_a_seam():
    """The tone's buffer is whole cycles: its last sample runs into its first without a step."""
    audio = recording_audio_engine()
    for background, name in (
        (BackgroundPattern.TEST_PATTERN, BARS_TONE),
        (BackgroundPattern.CHANNEL_THREE, CHANNEL_THREE_HISS),
    ):
        cues = CrtPowerOnSound(audio=audio, background=background)
        samples = cues.sounds[name].samples_float
        assert samples is not None
        steps = np.abs(np.diff(samples))
        seam = abs(samples[0] - samples[-1])
        assert seam <= steps.max()
    # The tone's seam is a sine's own step
    tone = CrtPowerOnSound(audio=audio, background=BackgroundPattern.TEST_PATTERN)
    samples = tone.sounds[BARS_TONE].samples_float
    assert samples is not None
    assert abs(samples[0] - samples[-1]) == pytest.approx(abs(samples[1] - samples[0]), rel=0.01)


def test_the_static_never_draws_from_engine_random_streams(mocker):
    """The static has its own fixed seed: the game's streams are untouched (feature spec 12.1)."""
    randomness.reset_streams(seed=1234)
    randomness.random_stream('gameplay')
    randomness.numpy_stream('gameplay')
    before = randomness.capture_stream_states()
    random_stream = mocker.spy(randomness, 'random_stream')
    numpy_stream = mocker.spy(randomness, 'numpy_stream')
    audio = recording_audio_engine()

    cues = CrtPowerOnSound(audio=audio, background=BackgroundPattern.TEST_PATTERN)
    drive(cues, audio, progresses=frame_progresses())

    assert randomness.capture_stream_states() == before
    random_stream.assert_not_called()
    numpy_stream.assert_not_called()
    # The same static every time, in any context
    first_static = cues.sounds[STATIC].samples_float
    with EngineContext(name='another run').active():
        again = CrtPowerOnSound(
            audio=recording_audio_engine(), background=BackgroundPattern.TEST_PATTERN
        )
        assert np.array_equal(again.sounds[STATIC].samples_float, first_static)


# --- AUD-CRT-001: the offline render ---


def test_offline_render_of_the_sequence_puts_onsets_within_10_ms_of_their_cues(tmp_path):
    """Each sound is first heard within 10 ms of its progress point (feature spec 12.1)."""
    audio = recording_audio_engine()
    cues = CrtPowerOnSound(audio=audio, background=BackgroundPattern.TEST_PATTERN)
    drive(cues, audio, progresses=frame_progresses())
    silence = silent_sound(audio)
    mix = rendered_mix(audio.plays, tmp_path / 'sequence.wav', silence=silence)
    rate = silence.sample_rate

    for index, (point, name) in enumerate(TEST_PATTERN_TIMELINE):
        others = [play for position, play in enumerate(audio.plays) if position != index]
        without = rendered_mix(others, tmp_path / f'without_{name}.wav', silence=silence)
        shared = min(len(mix), len(without))
        heard = np.flatnonzero(np.abs(mix[:shared] - without[:shared]) > AUDIBLE_LEVEL)
        onset_seconds = heard[0] / rate
        assert abs(onset_seconds - point * SEQUENCE_SECONDS) <= ONSET_TOLERANCE_SECONDS, name
        # Cued on the nearest frame (R42): within half a 60 fps frame, plus the 1 ms its attack
        # takes to be heard
        assert abs(onset_seconds - point * SEQUENCE_SECONDS) <= (
            FRAME_SECONDS / 2 + ATTACK_HEARD_SECONDS
        ), name


# --- AUD-CRT-003: a skip ---


def test_a_skip_fades_every_voice_over_20_ms_and_cues_nothing_more():
    """Each started voice is asked for a 20 ms fade; later cues and the tail's carry do nothing."""
    audio = recording_audio_engine()
    cues = CrtPowerOnSound(audio=audio, background=BackgroundPattern.TEST_PATTERN)
    drive(cues, audio, progresses=[0.0, 0.1, 0.2])

    cues.skip()
    cues.at_progress(1.0)
    cues.carry_tail_into_the_game()

    assert SKIP_FADE_MILLISECONDS == 20
    assert [play['handle'].fades for play in audio.plays] == [[0.02]] * 3
    assert audio.started_names(cues) == [POWER_CLICK, DEGAUSS, FLYBACK_WHINE]
    # Nothing is left to carry into the game
    assert audio.fades_at_next_update == []


def sdl_mixer_fade_out_gains(
    *, frame_count: int, fade_asked_at_frame: int, fade_milliseconds: int, sample_rate: int
) -> np.ndarray:
    """The gain SDL_mixer gives each output frame of a channel faded out with ``fadeout(ms)``.

    A model of SDL_mixer 2.8 (the version pygame-ce 2.5.8 links: ``pygame.mixer.
    get_sdl_mixer_version()`` gives (2, 8, 2)), src/mixer.c: ``Mix_FadeOutChannel`` notes
    ``SDL_GetTicks()`` and the channel's volume; ``mix_channels``, the mixing callback, runs
    once per chunk of the mixer's buffer and, for a fading channel, computes
    ``ticks = SDL_GetTicks() - ticks_fade`` once: at ``ticks >= fade_length`` it halts the
    channel, else it sets the volume to ``fade_volume * (fade_length - ticks) / fade_length``
    (integer arithmetic, volumes 0-``MIX_MAX_VOLUME`` = 128), applied to the whole chunk. So the
    fade is a few plateaus, one per chunk, then a halt: not a ramp.

    Assumptions: the voice's level is its panning (pygame-ce's two-argument
    ``Channel.set_volume`` is ``Mix_SetPanning``), so the fading volume starts at 128; each
    chunk is mixed at its own start time (no device latency); a chunk mixed at or before the
    fade was asked plays at full volume.

    Returns:
        One gain per frame, 0 to 1.
    """
    gains = np.ones(frame_count)
    milliseconds_asked = math.floor(fade_asked_at_frame * MILLISECONDS_PER_SECOND / sample_rate)
    for chunk_start in range(0, frame_count, MIXER_CHUNK_FRAMES):
        if chunk_start <= fade_asked_at_frame:
            continue
        ticks = math.floor(chunk_start * MILLISECONDS_PER_SECOND / sample_rate) - milliseconds_asked
        if ticks >= fade_milliseconds:
            gains[chunk_start:] = 0.0
            break
        volume = MIX_MAX_VOLUME * (fade_milliseconds - ticks) // fade_milliseconds
        gains[chunk_start : chunk_start + MIXER_CHUNK_FRAMES] = volume / MIX_MAX_VOLUME
    return gains


def skip_phases(*, skip_frame: int) -> list[int]:
    """Frames to skip at: around ``skip_frame``, at eight places within one mixer chunk.

    Returns:
        The frames.
    """
    return [skip_frame + MIXER_CHUNK_FRAMES * phase // 8 for phase in range(8)]


def test_a_skip_ends_every_crt_voice_within_20_ms_and_one_mixer_chunk(tmp_path):
    """AUD-CRT-003's ending, on the device's real fade (modelled).

    A key at 0.4 s silences the CRT within 20 ms plus one mixer chunk (SDL_mixer halts a faded
    channel at its first chunk past the fade), wherever in a chunk the key falls.
    """
    audio = recording_audio_engine()
    cues = CrtPowerOnSound(audio=audio, background=BackgroundPattern.TEST_PATTERN)
    frame_times = np.arange(0.0, SKIP_SECONDS, FRAME_SECONDS)
    drive(cues, audio, progresses=frame_times / SEQUENCE_SECONDS)
    cues.skip()
    (fade_seconds,) = {fade for play in audio.plays for fade in play['handle'].fades}
    silence = silent_sound(audio)
    mix = rendered_mix(audio.plays, tmp_path / 'skipped.wav', silence=silence)
    rate = silence.sample_rate
    fade_milliseconds = round(fade_seconds * MILLISECONDS_PER_SECOND)
    skip_frame = round(SKIP_SECONDS * rate)
    # Something was sounding when the key came
    assert np.max(np.abs(mix[skip_frame - MIXER_CHUNK_FRAMES : skip_frame])) > AUDIBLE_LEVEL

    for fade_asked_at_frame in skip_phases(skip_frame=skip_frame):
        heard = mix * sdl_mixer_fade_out_gains(
            frame_count=len(mix),
            fade_asked_at_frame=fade_asked_at_frame,
            fade_milliseconds=fade_milliseconds,
            sample_rate=rate,
        )
        silent_from = (
            fade_asked_at_frame
            + round(SKIP_FADE_MILLISECONDS / MILLISECONDS_PER_SECOND * rate)
            + MIXER_CHUNK_FRAMES
        )
        assert np.all(heard[silent_from:] == 0.0), fade_asked_at_frame


def device_fade_discontinuity(*, tone: np.ndarray, frequency: float, sample_rate: int) -> float:
    """The worst step SDL_mixer's 20 ms fade puts in a pure tone, over the key's chunk phases.

    The discontinuity metric of feature spec 16.1: the largest sample-to-sample step while
    fading, relative to the tone's own largest step (its peak slope, 2 pi f / rate times its
    amplitude). A smooth fade stays at or below 1; a gain step at a crest stands out.

    Returns:
        The worst ratio.
    """
    amplitude = float(np.max(np.abs(tone)))
    own_largest_step = 2.0 * math.pi * frequency / sample_rate * amplitude
    fade_asked = len(tone) // 2
    worst = 0.0
    for fade_asked_at_frame in skip_phases(skip_frame=fade_asked):
        heard = tone * sdl_mixer_fade_out_gains(
            frame_count=len(tone),
            fade_asked_at_frame=fade_asked_at_frame,
            fade_milliseconds=SKIP_FADE_MILLISECONDS,
            sample_rate=sample_rate,
        )
        fading = heard[fade_asked_at_frame : fade_asked_at_frame + 4 * MIXER_CHUNK_FRAMES]
        worst = max(worst, float(np.max(np.abs(np.diff(fading)))) / own_largest_step)
    return worst


def bars_tone_samples() -> tuple[np.ndarray, int]:
    """The bars tone's compiled samples (a pure 1 kHz sine) and their rate.

    Returns:
        The samples and the sample rate.
    """
    cues = CrtPowerOnSound(
        audio=recording_audio_engine(), background=BackgroundPattern.TEST_PATTERN
    )
    tone = cues.sounds[BARS_TONE]
    assert tone.samples_float is not None
    return np.asarray(tone.samples_float), tone.sample_rate


def test_the_device_fade_steps_a_pure_tone_in_chunk_plateaus():
    """Measured on a pure tone, not the noisy mix: SDL_mixer's fade is per-chunk plateaus.

    Each gain change falls on a chunk boundary, there are at most three (two plateaus and the
    halt), and the worst step is several times the tone's own: this is AUD-CRT-003's open
    question (feature spec 15, impl spec 10.1), measured.
    """
    tone, rate = bars_tone_samples()
    gains = sdl_mixer_fade_out_gains(
        frame_count=len(tone),
        fade_asked_at_frame=len(tone) // 2,
        fade_milliseconds=SKIP_FADE_MILLISECONDS,
        sample_rate=rate,
    )
    changes = np.flatnonzero(np.diff(gains)) + 1

    assert len(changes) <= 3
    assert all(change % MIXER_CHUNK_FRAMES == 0 for change in changes)
    assert device_fade_discontinuity(tone=tone, frequency=BARS_TONE_HZ, sample_rate=rate) > 1.0


@pytest.mark.xfail(
    strict=True,
    reason=(
        'AUD-CRT-003 [Open] (ruling R41): SDL_mixer steps a fade once per 512-frame chunk, so a '
        '20 ms fade is about two plateaus and a halt. Pending Task 13 (disk-driver probe and the '
        "owner's listening check); the fallback is engine-rendered fade tails (impl spec risk R5)"
    ),
)
def test_a_skip_fades_a_pure_tone_without_a_step_above_threshold():
    """AUD-CRT-003's "no step above threshold" on the device's fade: not met by SDL_mixer."""
    tone, rate = bars_tone_samples()

    assert (
        device_fade_discontinuity(tone=tone, frequency=BARS_TONE_HZ, sample_rate=rate)
        <= DISCONTINUITY_THRESHOLD
    )


# --- On a real audio engine: the tail into frame 0 ---


@pytest.fixture
def channel_calls(mocker):
    """Record every call the voice table makes on a mixer channel (the channels stay real).

    Returns:
        The list of (channel index, call, arguments).
    """
    RecordingChannel.calls.clear()
    mocker.patch('pygame.mixer.Channel', RecordingChannel)
    return RecordingChannel.calls


class GameScene(Scene):
    """A stand-in game's first scene."""

    NAME = 'GameScene'


def test_the_tail_persists_into_frame_zero_then_fades(channel_calls):
    """The tone is the engine's own voice; frame 0's first audio update fades it over 500 ms."""
    audio = AudioEngine(partition=start_reserved_mixer())
    cues = CrtPowerOnSound(audio=audio, background=BackgroundPattern.TEST_PATTERN)
    for progress in frame_progresses():
        cues.at_progress(float(progress))
        cues.frame(FRAME_SECONDS)
    tail = cues.tail_handle
    assert tail is not None
    fades_before = len(calls_named(channel_calls, 'fadeout'))

    cues.carry_tail_into_the_game()
    # Building the game takes as long as it takes: nothing fades before frame 0
    assert tail.is_playing
    game_scene = GameScene()
    audio.update(
        dt=FRAME_SECONDS,
        active_scene=game_scene,
        previous_scene=None,
        active_transitions=(None, None),
        paused_owners=(),
    )

    assert TAIL_FADE_MILLISECONDS == 500
    assert calls_named(channel_calls, 'fadeout')[fades_before:] == [
        (tail_channel(audio), (TAIL_FADE_MILLISECONDS,))
    ]
    assert not tail.is_playing
    # Once only: later frames fade nothing more
    audio.update(
        dt=FRAME_SECONDS,
        active_scene=game_scene,
        previous_scene=None,
        active_transitions=(None, None),
        paused_owners=(),
    )
    assert len(calls_named(channel_calls, 'fadeout')) == fades_before + 1
    audio.close(wait_seconds=0.0)


def tail_channel(audio: AudioEngine) -> int:
    """The library channel the tail fades on: the only library channel still playing.

    Returns:
        Its index.
    """
    (channel,) = [
        channel.index
        for channel in audio.snapshot().channels
        if channel.group == 'library' and channel.state == 'fading'
    ]
    return channel


def test_a_skip_on_the_engine_fades_each_voice_with_the_device_fade(channel_calls):
    """Skip asks the device for a 20 ms fade (``Channel.fadeout(20)``) on every CRT voice."""
    audio = AudioEngine(partition=start_reserved_mixer())
    cues = CrtPowerOnSound(audio=audio, background=BackgroundPattern.TEST_PATTERN)
    for progress in frame_progresses()[:30]:
        cues.at_progress(float(progress))
        cues.frame(FRAME_SECONDS)
    playing = audio.diagnostics().voices_playing

    cues.skip()

    fades = calls_named(channel_calls, 'fadeout')
    assert playing >= 1
    assert [arguments for _index, arguments in fades][-playing:] == [
        (SKIP_FADE_MILLISECONDS,)
    ] * playing
    assert audio.diagnostics().voices_playing == 0
    audio.close(wait_seconds=0.0)


# --- In real engine runs (AUD-CRT-002 and the wiring) ---


@pytest.fixture
def engine_run_environment(mocker):
    """Let the test start a real engine, leaving pygame usable for later tests.

    Yields:
        None, while the environment is in place.
    """
    yield from demo_runs.engine_run_environment(mocker)


class FirstFrameGame(Scene):
    """A stand-in game that notes its audio engine in its first frame, then quits."""

    NAME = 'CrtFirstFrameGame'
    VERSION = '1.0'
    seen: ClassVar[dict[str, Any]] = {}

    def dt_tick(self, dt: float) -> None:
        """Note the audio engine (made on first use, or the power-on's), then quit."""
        super().dt_tick(dt)
        FirstFrameGame.seen['audio'] = self.scene_manager.audio
        self.scene_manager.quit()


def build_engine(mocker, *, extra_arguments: tuple[str, ...] = ()) -> GoldenTraceEngine:
    """Construct a real engine for FirstFrameGame (not started).

    Returns:
        The engine.
    """
    FirstFrameGame.seen.clear()
    mocker.patch.object(
        sys, 'argv', ['test_crt_power_on_sound', *ENGINE_ARGUMENTS, *extra_arguments]
    )
    return GoldenTraceEngine(game=FirstFrameGame)


def someone_is_watching(mocker) -> None:
    """Decide the power-on as if a real window were watched (SDL's dummy driver is not).

    Only the driver is replaced: the rest of ``should_play``'s rule (the options) decides.
    """
    real_should_play = crt_power_on.should_play

    def should_play_on_a_watched_window(**arguments):
        return real_should_play(**{**arguments, 'video_driver': 'cocoa'})

    mocker.patch.object(
        game_engine_module, 'should_play', side_effect=should_play_on_a_watched_window
    )


def system_voices_started(voice_plays) -> int:
    """How many plays the voice table started for the engine's own (system) owner.

    Returns:
        The count.
    """
    return sum(1 for call in voice_plays.call_args_list if call.kwargs['owner'] is SYSTEM_OWNER)


def play_the_real_sequence_without_waiting(mocker) -> None:
    """Play the real power-on, its frames back to back on a measured clock of 60 fps."""
    mocker.patch(
        'glitchygames.clock.measured_seconds',
        side_effect=itertools.count(start=0.0, step=FRAME_SECONDS),
    )
    real_play = crt_power_on.play_power_on

    def play_without_waiting(**arguments):
        return real_play(**arguments, sleep=lambda _seconds: None)

    mocker.patch.object(game_engine_module, 'play_power_on', side_effect=play_without_waiting)


@pytest.mark.usefixtures('engine_run_environment')
class TestInRealRuns:
    """The engine plays the sound with the picture, and only then (AUD-CRT-002)."""

    def test_the_power_on_plays_its_sound_and_carries_the_tail_into_the_game(
        self, mocker, channel_calls
    ):
        engine = build_engine(mocker, extra_arguments=('--crt-power-on', 'on'))
        play_the_real_sequence_without_waiting(mocker)
        voice_plays = mocker.spy(VoiceTable, 'play')

        engine.start()

        assert system_voices_started(voice_plays) == 5
        fades = [arguments for _index, arguments in calls_named(channel_calls, 'fadeout')]
        assert (TAIL_FADE_MILLISECONDS,) in fades

    def test_the_power_ons_audio_engine_is_the_games(self, mocker):
        """Made before the power-on from the engine's options and partition (rulings R34, R35)."""
        engine = build_engine(
            mocker,
            extra_arguments=(
                '--crt-power-on',
                'on',
                '--sound-cache',
                'none',
                '--sound-channels',
                '12',
            ),
        )
        cues_seen: list[Any] = []

        def remember_the_cues(**arguments):
            cues_seen.append(arguments['sound_cues'])
            return PowerOnOutcome.FINISHED

        mocker.patch.object(game_engine_module, 'play_power_on', side_effect=remember_the_cues)

        engine.start()

        (cues,) = cues_seen
        assert isinstance(cues, CrtPowerOnSound)
        assert cues.audio is FirstFrameGame.seen['audio']
        assert cues.audio.cache_mode is CacheMode.NONE
        assert cues.audio.diagnostics().voices_limit == 12
        assert engine.channel_partition is not None
        assert len(engine.channel_partition.library) == 12

    def test_the_async_start_gets_the_cues_too(self, mocker):
        engine = build_engine(mocker, extra_arguments=('--crt-power-on', 'on'))
        cues_seen: list[Any] = []

        async def remember_the_cues(**arguments):
            await asyncio.sleep(0)
            cues_seen.append(arguments['sound_cues'])
            return PowerOnOutcome.FINISHED

        mocker.patch.object(
            game_engine_module, 'play_power_on_async', side_effect=remember_the_cues
        )

        async def wait_for_tick() -> float:
            await asyncio.sleep(0)
            return 0.0

        asyncio.run(engine.start_async(wait_for_tick=wait_for_tick))

        (cues,) = cues_seen
        assert isinstance(cues, CrtPowerOnSound)

    def test_the_sound_follows_the_configured_background(self, mocker):
        engine = build_engine(
            mocker,
            extra_arguments=('--crt-power-on', 'on', '--default-background', 'channel-3'),
        )
        cues_seen: list[Any] = []
        mocker.patch.object(
            game_engine_module,
            'play_power_on',
            side_effect=lambda **arguments: (
                cues_seen.append(arguments['sound_cues']) or PowerOnOutcome.FINISHED
            ),
        )

        engine.start()

        (cues,) = cues_seen
        assert CHANNEL_THREE_HISS in cues.sounds

    def test_no_sound_with_the_option_off(self, mocker):
        """``--crt-power-on-sound off`` silences it; the picture still plays."""
        engine = build_engine(
            mocker, extra_arguments=('--crt-power-on', 'on', '--crt-power-on-sound', 'off')
        )
        player = mocker.patch.object(
            game_engine_module, 'play_power_on', return_value=PowerOnOutcome.FINISHED
        )
        voice_plays = mocker.spy(VoiceTable, 'play')

        engine.start()

        assert player.call_args.kwargs['sound_cues'] is None
        assert system_voices_started(voice_plays) == 0

    def test_no_sound_under_headless(self, mocker):
        engine = build_engine(mocker, extra_arguments=('--crt-power-on', 'auto', '--headless'))
        player = mocker.spy(game_engine_module, 'play_power_on')
        made = mocker.spy(crt_power_on_sound.CrtPowerOnSound, '__init__')
        voice_plays = mocker.spy(VoiceTable, 'play')

        engine.start()

        player.assert_not_called()
        made.assert_not_called()
        assert system_voices_started(voice_plays) == 0

    def test_no_sound_with_a_recording_or_its_replay(self, mocker, tmp_path):
        """Even where someone watches, a recorded or replayed run has nothing before frame 0."""
        recording = tmp_path / 'run.jsonl.gz'
        someone_is_watching(mocker)
        player = mocker.spy(game_engine_module, 'play_power_on')
        made = mocker.spy(crt_power_on_sound.CrtPowerOnSound, '__init__')
        voice_plays = mocker.spy(VoiceTable, 'play')

        build_engine(
            mocker, extra_arguments=('--crt-power-on', 'auto', '--record-trace', str(recording))
        ).start()
        replay = build_engine(
            mocker,
            extra_arguments=(
                '--crt-power-on',
                'auto',
                '--replay-trace',
                str(recording),
                '--headless',
            ),
        )
        with pytest.raises(SystemExit):
            replay.start()

        assert recording.exists()
        player.assert_not_called()
        made.assert_not_called()
        assert system_voices_started(voice_plays) == 0

    def test_without_the_power_on_no_audio_engine_is_made_early(self, mocker):
        """No power-on, no CRT: the game's audio engine is made on first use, as before."""
        engine = build_engine(mocker, extra_arguments=('--crt-power-on', 'off'))
        made = mocker.spy(crt_power_on_sound.CrtPowerOnSound, '__init__')

        engine.start()

        made.assert_not_called()
        assert isinstance(FirstFrameGame.seen['audio'], AudioEngine)


@pytest.mark.parametrize('background', list(BackgroundPattern), ids=lambda pattern: pattern.value)
def test_no_sound_of_the_sequence_clips(background):
    """Each sound peaks at or below full scale, so none is clipped (or logged as clipped)."""
    cues = CrtPowerOnSound(audio=recording_audio_engine(), background=background)

    assert {name: sound.peak <= 1.0 for name, sound in cues.sounds.items()} == dict.fromkeys(
        cues.sounds, True
    )
