"""The test harness silences the mixer after every test (tests/harness.py silence_every_channel).

A sound left playing leaks into the next test on the worker: audibly on a real audio driver, and
as a refusal when that test's engine partitions the mixer at construction (a host declaring
INNER_GAMES; BUGS.md #145's guard). A streamed sound keeps its next chunk queued on its channel,
and pygame starts a channel's queued sound the moment the channel is halted, so one stop leaves
the channel playing (2026-11-19: Mr. Muncher's golden recording, then Zombies Ain't My
Neighbors', on one shuffled worker).
"""

from __future__ import annotations

import gc
from pathlib import Path

import numpy as np
import pygame
import pytest

from tests.harness import (
    busy_mixer_channels,
    check_every_queued_sound_is_held_by_a_live_stream,
    end_of_test_sound_problems,
    silence_every_channel,
    unreleased_live_stream_problems,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUBPROCESS_TIMEOUT_SECONDS = 120.0

# One second of silence, in the mixer's format (44100 Hz, signed 16-bit, stereo)
SILENCE = bytes(44100 * 2 * 2)


@pytest.fixture
def a_channel_with_a_queued_sound() -> pygame.mixer.Channel:
    """Play a sound on a channel with another queued behind it, as a streamed sound does.

    Returns:
        The channel.

    """
    sound = pygame.mixer.Sound(buffer=SILENCE)
    channel = pygame.mixer.Channel(0)
    channel.play(sound)
    channel.queue(sound)
    return channel


def test_one_stop_starts_the_queued_sound(a_channel_with_a_queued_sound):
    """The pygame behaviour the harness allows for: a halted channel plays what it queued."""
    pygame.mixer.stop()

    assert a_channel_with_a_queued_sound.get_busy()
    pygame.mixer.stop()


@pytest.mark.usefixtures('a_channel_with_a_queued_sound')
def test_every_channel_is_silent_after_the_harness_silences_it():
    """The queued sound is stopped too: nothing plays on into the next test."""
    silence_every_channel()

    assert busy_mixer_channels() == []


def test_a_channel_still_playing_after_the_stops_fails_the_test_that_left_it(mocker):
    """Should a channel play on regardless, the harness says so after that test, naming it."""
    from tests import harness

    mocker.patch.object(harness, 'busy_mixer_channels', return_value=[3])

    with pytest.raises(pytest.fail.Exception, match=r'still playing after two stops: \[3\]'):
        silence_every_channel()


def test_a_stopped_mixer_has_nothing_to_silence(mocker):
    """With the mixer not running there is no channel to stop or to read."""
    mocker.patch.object(pygame.mixer, 'get_init', return_value=None)
    stop = mocker.patch.object(pygame.mixer, 'stop')

    silence_every_channel()

    stop.assert_not_called()
    assert busy_mixer_channels() == []


def test_a_queued_sound_no_live_stream_holds_fails_the_test_that_left_it():
    """The invariant: a channel with a queue names only Sounds a live stream holds.

    pygame-ce 2.5.8 frees a queued Sound twice when its table holds the only references and a
    play lands on the channel (bugs/2026-11-24-pygame-mixer-frees-a-queued-sound-twice.md).
    Here the test's own names hold them, so nothing is freed; no live stream does.
    """
    playing = pygame.mixer.Sound(buffer=SILENCE)
    queued = pygame.mixer.Sound(buffer=SILENCE)
    channel = pygame.mixer.Channel(0)
    channel.play(playing)
    channel.queue(queued)
    try:
        with pytest.raises(
            pytest.fail.Exception, match=r'no live stream holds on channel 0 with a queue'
        ):
            check_every_queued_sound_is_held_by_a_live_stream()
    finally:
        channel.stop()
        channel.stop()


def test_a_live_streams_queued_chunk_passes_the_check():
    """A live voice's chunks, playing and queued, are held by its stream."""
    voice = _live_voice_on_channel_zero()
    voice.stream.start()
    voice.stream.update()
    assert pygame.mixer.Channel(0).get_queue() is not None

    check_every_queued_sound_is_held_by_a_live_stream()

    voice.stream.stop_now()


def test_a_live_stream_left_playing_after_a_test_is_named_as_never_released():
    """A stream nobody released still holds its chunks; released, it holds none."""
    voice = _live_voice_on_channel_zero()
    voice.stream.start()
    voice.stream.update()

    assert unreleased_live_stream_problems() == [
        (
            'A live stream was never released (str on channel 0): it still holds 2 chunk(s) '
            '(release_voice, release_every_voice, stop_now or SceneManager.terminate)'
        )
    ]
    voice.stream.stop_now()
    assert unreleased_live_stream_problems() == []


def test_a_patched_stream_left_unreleased_is_still_named(mocker):
    """Patching a stream makes its ``__dict__``: the harness still finds it (exact enumeration)."""
    voice = _live_voice_on_channel_zero()
    voice.stream.start()
    voice.stream.update()
    mocker.patch.object(voice.stream, 'pause')

    assert len(unreleased_live_stream_problems()) == 1
    assert check_every_queued_sound_is_held_by_a_live_stream() is None
    voice.stream.stop_now()


def test_a_dropped_stream_is_reported_on_the_test_that_dropped_it():
    """Dropped unreleased in a reference cycle: found, collected and reported at once."""
    voice = _live_voice_on_channel_zero()
    voice.stream.start()
    del voice

    assert unreleased_live_stream_problems() == [
        (
            'A live stream was never released (str on channel 0): collected holding 1 chunk(s) '
            '(release_voice, release_every_voice, stop_now or SceneManager.terminate)'
        )
    ]


def test_a_report_of_a_stream_collected_late_names_an_earlier_test():
    """A report this test's streams cannot explain came from a stream an earlier test leaked."""
    voice = _live_voice_on_channel_zero()
    voice.stream.start()
    del voice
    gc.collect()  # as if collected later: the harness never saw it holding chunks

    assert unreleased_live_stream_problems() == [
        (
            'A live stream was collected during this test; leaked by an earlier test on this '
            'worker (str on channel 0): it held 1 chunk(s)'
        )
    ]


def test_a_silencing_failure_and_an_unreleased_stream_are_reported_together(mocker):
    """No report is lost when the silencing check fails too: both are in one failure."""
    from tests import harness

    voice = _live_voice_on_channel_zero()
    voice.stream.start()
    mocker.patch.object(harness, 'busy_mixer_channels', return_value=[3])

    problems = end_of_test_sound_problems()

    assert len(problems) == 2
    assert problems[0].startswith('A live stream was never released (str on channel 0)')
    assert problems[1] == 'Mixer channels still playing after two stops: [3]'
    voice.stream.stop_now()


# A test that leaks a live voice, then one that does nothing: only the first may fail
LEAKS_THEN_CLEAN = """
import numpy as np
import pygame

from glitchygames.audio.instrument import Instrument
from glitchygames.audio.live_instrument import InstrumentVoice


def test_a_leaks_a_live_stream():
    voice = InstrumentVoice(
        channel=pygame.mixer.Channel(0),
        owner='leaky test',
        instrument=Instrument(wave='sine', live=True),
        frequency=220.0,
        volume=0.5,
        sample_rate=44100,
        random_source=np.random.default_rng(5),
    )
    voice.stream.start()
    voice.stream.update()
    vars(voice.stream)  # makes the stream's __dict__, as patching it does


def test_b_is_clean():
    pass
"""


def test_a_leaked_live_stream_fails_only_the_test_that_leaked_it(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The harness's teardown wiring: the leak errors its own test; the next one passes."""
    monkeypatch.setenv('PYTHONPATH', str(PROJECT_ROOT))
    monkeypatch.setenv('SDL_VIDEODRIVER', 'dummy')
    monkeypatch.setenv('SDL_AUDIODRIVER', 'dummy')
    tests = pytester.makepyfile(test_leaks=LEAKS_THEN_CLEAN)

    # As tests/test_harness_every_item_starts_on_the_canvas.py runs the harness
    result = pytester.runpytest_subprocess(
        '-c',
        str(PROJECT_ROOT / 'pyproject.toml'),
        '--rootdir',
        str(pytester.path),
        '--confcutdir',
        str(pytester.path),
        '-p',
        'tests.harness',
        '-p',
        'no:cacheprovider',
        '-p',
        'no:xdist',
        '-p',
        'no:randomly',
        '-o',
        'addopts=',
        '-rE',
        str(tests),
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )

    result.assert_outcomes(passed=2, errors=1)
    result.stdout.fnmatch_lines([
        '*Failed: A live stream was never released (str on channel 0)*',
        '*ERROR test_leaks.py::test_a_leaks_a_live_stream*',
    ])
    result.stdout.no_fnmatch_line('*ERROR*test_b_is_clean*')


def _live_voice_on_channel_zero():
    """A stopped live sine on channel 0, outside any pool.

    Returns:
        The voice.
    """
    from glitchygames.audio.instrument import Instrument
    from glitchygames.audio.live_instrument import InstrumentVoice
    from glitchygames.audio.synth import mixer_sample_rate

    return InstrumentVoice(
        channel=pygame.mixer.Channel(0),
        owner='scene',
        instrument=Instrument(wave='sine', live=True),
        frequency=220.0,
        volume=0.5,
        sample_rate=mixer_sample_rate(),
        random_source=np.random.default_rng(5),
    )
