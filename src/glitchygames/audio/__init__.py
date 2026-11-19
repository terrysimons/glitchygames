"""Audio module for GlitchyGames.

Provides the sound engine (``scene_manager.audio``, an ``AudioEngine``: one-call sounds from
names, paths, instruments and mixes of instrument parts, with pitches, waves and noise),
controller audio I/O (microphone + speaker), text-to-speech, and a push-to-talk AI voice
assistant for game controllers.

Usage:
    coin = self.scene_manager.audio.sound('coin')   # in setup(): compiled once, cached
    coin.play()                                     # in gameplay

    from glitchygames.audio import render_to_file

    render_to_file(coin, 'out/coin.wav')            # offline, no audio device

    from glitchygames.audio import VoiceAssistant

    assistant = VoiceAssistant.for_controller('DualSense Wireless Controller')
    assistant.start_listening()       # On mic button press
    assistant.stop_listening_and_respond()  # On mic button release
"""

from typing import TYPE_CHECKING

from glitchygames.audio.controller_audio import ControllerAudio
from glitchygames.audio.effects import (
    Effect,
    Tone,
    Tremolo,
    load_effects,
)
from glitchygames.audio.engine import AudioEngine
from glitchygames.audio.exceptions import (
    AudioUnavailableError,
    EffectError,
    SoundAssetError,
    SoundRenderError,
)
from glitchygames.audio.instrument import Instrument, Noise
from glitchygames.audio.library import CacheMode, Sound
from glitchygames.audio.live import LiveAudio
from glitchygames.audio.live_controls import Parameter, Route
from glitchygames.audio.live_instrument import LiveSoundHandle
from glitchygames.audio.mix import Mix, MixPart
from glitchygames.audio.offline import OfflineEvent, RenderReport, render_to_file
from glitchygames.audio.pitch import Hz, Midi, Note, PitchTable, Scale, Tuning
from glitchygames.audio.synth import Envelope, Waveform
from glitchygames.audio.tts import MacOSTTS, get_tts_backend
from glitchygames.audio.voices import (
    ChannelsHeldError,
    InnerGameChannelLayout,
    InnerGameChannelsError,
    MixerBusyError,
    PlayingSound,
    SoundHandle,
    reserve_inner_game_channels,
)
from glitchygames.audio.waves import CYCLE, LEVEL, Harmonics, Wave, WavePoint

if TYPE_CHECKING:
    from glitchygames.audio.voice_assistant import VoiceAssistant

__all__ = [
    'CYCLE',
    'LEVEL',
    'AudioEngine',
    'AudioUnavailableError',
    'CacheMode',
    'ChannelsHeldError',
    'ControllerAudio',
    'Effect',
    'EffectError',
    'Envelope',
    'Harmonics',
    'Hz',
    'InnerGameChannelLayout',
    'InnerGameChannelsError',
    'Instrument',
    'LiveAudio',
    'LiveSoundHandle',
    'MacOSTTS',
    'Midi',
    'Mix',
    'MixPart',
    'MixerBusyError',
    'Noise',
    'Note',
    'OfflineEvent',
    'Parameter',
    'PitchTable',
    'PlayingSound',
    'RenderReport',
    'Route',
    'Scale',
    'Sound',
    'SoundAssetError',
    'SoundHandle',
    'SoundRenderError',
    'Tone',
    'Tremolo',
    'Tuning',
    'VoiceAssistant',
    'Wave',
    'WavePoint',
    'Waveform',
    'get_tts_backend',
    'load_effects',
    'render_to_file',
    'reserve_inner_game_channels',
]


def __getattr__(name: str) -> object:
    """Import ``VoiceAssistant`` when it is first asked for (a module ``__getattr__``, PEP 562).

    Its module imports speech recognition, which is slow to import, and every engine
    run imports this package (``glitchygames.audio.live``, its live voices), every child process
    the tools start included: a run that never asks for the voice assistant no longer imports it.
    ``from glitchygames.audio import VoiceAssistant`` works as it always did.

    Args:
        name: The attribute asked for.

    Returns:
        ``VoiceAssistant``, for that name.

    Raises:
        AttributeError: For any other name, as for any module.

    """
    if name == 'VoiceAssistant':
        from glitchygames.audio.voice_assistant import VoiceAssistant

        return VoiceAssistant
    message = f'module {__name__!r} has no attribute {name!r}'
    raise AttributeError(message)
