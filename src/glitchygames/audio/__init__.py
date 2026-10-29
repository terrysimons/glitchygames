"""Audio module for GlitchyGames.

Provides controller audio I/O (microphone + speaker), text-to-speech,
and a push-to-talk AI voice assistant for game controllers.

Usage:
    from glitchygames.audio import VoiceAssistant

    assistant = VoiceAssistant.for_controller('DualSense Wireless Controller')
    assistant.start_listening()       # On mic button press
    assistant.stop_listening_and_respond()  # On mic button release
"""

from typing import TYPE_CHECKING

from glitchygames.audio.controller_audio import ControllerAudio
from glitchygames.audio.exceptions import AudioUnavailableError, SoundRecipeError
from glitchygames.audio.live import LiveAudio, LiveVoice
from glitchygames.audio.recipes import (
    SoundBank,
    SoundRecipe,
    Tone,
    Tremolo,
    load_sound_recipes,
)
from glitchygames.audio.synth import Envelope, Waveform
from glitchygames.audio.tts import MacOSTTS, get_tts_backend

if TYPE_CHECKING:
    from glitchygames.audio.voice_assistant import VoiceAssistant

__all__ = [
    'AudioUnavailableError',
    'ControllerAudio',
    'Envelope',
    'LiveAudio',
    'LiveVoice',
    'MacOSTTS',
    'SoundBank',
    'SoundRecipe',
    'SoundRecipeError',
    'Tone',
    'Tremolo',
    'VoiceAssistant',
    'Waveform',
    'get_tts_backend',
    'load_sound_recipes',
]


def __getattr__(name: str) -> object:
    """Import ``VoiceAssistant`` when it is first asked for (a module ``__getattr__``, PEP 562).

    Its module imports aisuite (about 150 ms, with the AI providers' clients), and every engine
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
