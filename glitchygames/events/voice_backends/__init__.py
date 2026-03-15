#!/usr/bin/env python3
"""Voice microphone backend factory.

Returns an AudioSource-compatible microphone class for speech_recognition,
preferring miniaudio and falling back to PortAudio (via speech_recognition).
"""

from glitchygames.events.voice_backends.registry import get_microphone_backend

__all__ = [
    'get_microphone_backend',
]
