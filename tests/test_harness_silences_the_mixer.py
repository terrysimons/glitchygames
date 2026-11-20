"""The test harness silences the mixer after every test (tests/harness.py silence_every_channel).

A sound left playing leaks into the next test on the worker: audibly on a real audio driver, and
as a refusal when that test's engine partitions the mixer at construction (a host declaring
INNER_GAMES; BUGS.md #145's guard). A streamed sound keeps its next chunk queued on its channel,
and pygame starts a channel's queued sound the moment the channel is halted, so one stop leaves
the channel playing (2026-11-19: Mr. Muncher's golden recording, then Zombies Ain't My
Neighbors', on one shuffled worker).
"""

from __future__ import annotations

import pygame
import pytest

from tests.harness import busy_mixer_channels, silence_every_channel

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
