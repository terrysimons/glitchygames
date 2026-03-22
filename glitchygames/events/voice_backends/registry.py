#!/usr/bin/env python3
"""Voice microphone backend registry.

Provides factory functions for selecting the best available microphone backend
for speech_recognition, preferring miniaudio and falling back to PortAudio.
"""

from __future__ import annotations

import logging

LOG = logging.getLogger(__name__)


def _try_import_miniaudio() -> type[object] | None:
    """Try to import the MiniaudioMicrophone backend.

    Returns:
        type[object] | None: The MiniaudioMicrophone class, or None if unavailable.

    """
    try:
        from glitchygames.events.voice_miniaudio import MiniaudioMicrophone

        return MiniaudioMicrophone
    except ImportError:
        return None


def _try_import_portaudio() -> type[object] | None:
    """Try to import the PortAudioMicrophone backend.

    Returns:
        type[object] | None: The PortAudioMicrophone class, or None if unavailable.

    """
    try:
        from .voice_portaudio import PortAudioMicrophone

        return PortAudioMicrophone
    except (ImportError, RuntimeError):
        return None


def _probe_backend(backend_cls: type[object], name: str) -> type[object] | None:
    """Probe a microphone backend by attempting to instantiate it.

    Args:
        backend_cls: The backend class to probe.
        name: Human-readable name for log messages.

    Returns:
        type[object] | None: The backend class if probe succeeds, or None.

    """
    try:
        _ = backend_cls()
        return backend_cls
    except (OSError, RuntimeError):
        LOG.debug('%s probe failed, trying next backend', name)
        return None


def get_microphone_backend() -> type[object] | None:
    """Return an AudioSource-like microphone class or None.

    Priority order:
    1) MiniaudioMicrophone (if importable and probe succeeds)
    2) PortAudioMicrophone (if importable and probe succeeds)
    3) None

    Returns:
        type[object] | None: The microphone backend.

    """
    # Prefer miniaudio backend
    miniaudio_cls = _try_import_miniaudio()
    if miniaudio_cls is not None:
        result = _probe_backend(miniaudio_cls, 'MiniaudioMicrophone')
        if result is not None:
            return result
    else:
        LOG.debug('voice_miniaudio module not available')

    # Fallback to PortAudio wrapper
    portaudio_cls = _try_import_portaudio()
    if portaudio_cls is not None:
        result = _probe_backend(portaudio_cls, 'PortAudioMicrophone')
        if result is not None:
            return result
    else:
        LOG.debug('voice_portaudio module not available')

    return None
