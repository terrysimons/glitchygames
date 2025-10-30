#!/usr/bin/env python3
"""Voice microphone backend factory.

Returns an AudioSource-compatible microphone class for speech_recognition,
preferring miniaudio and falling back to PortAudio (via speech_recognition).
"""

from __future__ import annotations

from typing import Type


def get_microphone_backend() -> Type[object] | None:
    """Return an AudioSource-like microphone class or None.

    Priority order:
    1) MiniaudioMicrophone (if importable)
    2) PortAudioMicrophone (wrapper around speech_recognition.Microphone)
    3) None
    """
    # Prefer miniaudio backend
    try:
        from .voice_miniaudio import MiniaudioMicrophone

        # Light probe: try to instantiate; if fails, skip
        try:
            _ = MiniaudioMicrophone()  # noqa: F841
            return MiniaudioMicrophone
        except Exception:
            pass
    except Exception:
        pass

    # Fallback to PortAudio wrapper if speech_recognition is installed
    try:
        from .voice_portaudio import PortAudioMicrophone

        try:
            _ = PortAudioMicrophone()  # noqa: F841
            return PortAudioMicrophone
        except Exception:
            pass
    except Exception:
        pass

    return None


