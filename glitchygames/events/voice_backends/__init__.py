#!/usr/bin/env python3
"""Voice microphone backend factory.

Returns an AudioSource-compatible microphone class for speech_recognition,
preferring miniaudio and falling back to PortAudio (via speech_recognition).
"""

from __future__ import annotations

import logging

LOG = logging.getLogger(__name__)


def get_microphone_backend() -> type[object] | None:
    """Return an AudioSource-like microphone class or None.

    Priority order:
    1) MiniaudioMicrophone (if importable)
    2) PortAudioMicrophone (wrapper around speech_recognition.Microphone)
    3) None

    Returns:
        type[object] | None: The microphone backend.

    """
    # Prefer miniaudio backend
    try:
        from .voice_miniaudio import MiniaudioMicrophone

        # Light probe: try to instantiate; if fails, skip
        try:
            _ = MiniaudioMicrophone()
            return MiniaudioMicrophone
        except (OSError, RuntimeError):
            LOG.debug("MiniaudioMicrophone probe failed, trying next backend")
    except ImportError:
        LOG.debug("voice_miniaudio module not available")

    # Fallback to PortAudio wrapper if speech_recognition is installed
    try:
        from .voice_portaudio import PortAudioMicrophone

        try:
            _ = PortAudioMicrophone()
            return PortAudioMicrophone
        except (OSError, RuntimeError):
            LOG.debug("PortAudioMicrophone probe failed")
    except ImportError:
        LOG.debug("voice_portaudio module not available")

    return None
