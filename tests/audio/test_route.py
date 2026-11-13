"""Tests for the audio route per engine context (glitchygames/audio/route.py)."""

from glitchygames.audio.route import AUDIO_ROUTE_SLOT, is_audible, set_audible
from glitchygames.engine_context import EngineContext, current_context, default_context


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
