"""Tests for the audio route per engine context (glitchygames/audio/route.py)."""

from glitchygames.audio.engine import (
    AudioEngine,
    discard_audio_engine,
    existing_audio_engine,
    install_audio_engine,
)
from glitchygames.audio.route import AUDIO_ROUTE_SLOT, is_audible, set_audible
from glitchygames.engine_context import EngineContext, current_context, default_context
from tests.audio.library_support import stop_mixer
from tests.audio.voice_support import RecordingChannel, start_reserved_mixer


def test_the_default_context_is_audible():
    """An ordinary game is heard: the default context's route starts audible."""
    assert current_context() is default_context()
    assert is_audible()


def test_a_new_context_starts_audible():
    """A context nobody made silent is heard (InnerGame makes its own contexts silent)."""
    context = EngineContext(name='fresh')

    with context.active():
        assert is_audible()


def test_setting_the_flag_changes_only_the_current_context():
    """A context made silent and audible again; the default context stays audible throughout."""
    context = EngineContext(name='tile')

    with context.active():
        set_audible(audible=False)
        silent_reading = is_audible()
    default_reading = is_audible()
    with context.active():
        set_audible(audible=True)
        audible_reading = is_audible()

    assert silent_reading is False
    assert default_reading is True
    assert audible_reading is True
    assert context.value(slot=AUDIO_ROUTE_SLOT).audible is True


def test_going_silent_fades_the_contexts_voices_once_and_going_audible_starts_none(mocker):
    """The context's audio engine fades its voices over 50 ms as the context goes silent.

    A second silent setting fades nothing again, going audible starts nothing, and the silent
    engine's close neither touches a channel nor waits for the device.
    """
    partition = start_reserved_mixer()
    RecordingChannel.calls.clear()
    mocker.patch('pygame.mixer.Channel', RecordingChannel)
    sleep = mocker.patch('glitchygames.clock.raw_sleep')
    context = EngineContext(name='tile')
    try:
        with context.active():
            engine = install_audio_engine(engine=AudioEngine(partition=partition))
            handle = engine.beep(length=1.0)
            RecordingChannel.calls.clear()

            set_audible(audible=False)
            calls_going_silent = list(RecordingChannel.calls)
            set_audible(audible=False)
            set_audible(audible=True)
            set_audible(audible=False)
            playing_after = handle.is_playing
            discard_audio_engine()
    finally:
        stop_mixer()

    assert calls_going_silent == [(partition.library[0], 'fadeout', (50,))]
    assert RecordingChannel.calls == calls_going_silent
    assert playing_after is True
    sleep.assert_not_called()


def test_going_silent_without_an_audio_engine_makes_none():
    """A context that never asked for audio goes silent without an audio engine being made."""
    context = EngineContext(name='tile')

    with context.active():
        set_audible(audible=False)
        engine_after = existing_audio_engine()

    assert engine_after is None
