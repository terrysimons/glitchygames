#!/usr/bin/env python3
"""PortAudio wrapper exposing an AudioSource-like microphone.

Delegates to speech_recognition.Microphone but keeps a consistent surface
API with the miniaudio backend.
"""

from __future__ import annotations

try:
    import speech_recognition as sr
except Exception as exc:  # pragma: no cover - optional
    raise RuntimeError("speech_recognition is required for PortAudioMicrophone") from exc


class PortAudioMicrophone(sr.AudioSource):  # type: ignore[misc]
    def __init__(self, *args, **kwargs) -> None:  # noqa: D401 - mirror sr.Microphone
        self._inner = sr.Microphone(*args, **kwargs)
        # Attributes will be populated in __enter__ via the inner source
        self.stream = None
        self.SAMPLE_RATE = None
        self.CHANNELS = None
        self.CHUNK = None
        self.SAMPLE_WIDTH = None

    def __enter__(self):  # noqa: D401
        source = self._inner.__enter__()
        # Mirror essential attributes used by Recognizer.listen
        self.stream = source.stream
        self.SAMPLE_RATE = source.SAMPLE_RATE
        self.CHANNELS = source.CHANNELS if hasattr(source, "CHANNELS") else 1
        self.CHUNK = source.CHUNK
        self.SAMPLE_WIDTH = source.SAMPLE_WIDTH
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: D401, ANN001
        return self._inner.__exit__(exc_type, exc, tb)


