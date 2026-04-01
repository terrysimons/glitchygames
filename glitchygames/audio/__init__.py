"""Audio module for GlitchyGames.

Provides controller audio I/O (microphone + speaker), text-to-speech,
and a push-to-talk AI voice assistant for game controllers.

Usage:
    from glitchygames.audio import VoiceAssistant

    assistant = VoiceAssistant.for_controller('DualSense Wireless Controller')
    assistant.start_listening()       # On mic button press
    assistant.stop_listening_and_respond()  # On mic button release
"""

from glitchygames.audio.controller_audio import ControllerAudio
from glitchygames.audio.tts import MacOSTTS, get_tts_backend
from glitchygames.audio.voice_assistant import VoiceAssistant

__all__ = [
    'ControllerAudio',
    'MacOSTTS',
    'VoiceAssistant',
    'get_tts_backend',
]
