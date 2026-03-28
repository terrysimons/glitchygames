#!/usr/bin/env python3
"""PortAudio wrapper exposing an AudioSource-like microphone.

Delegates to speech_recognition.Microphone but keeps a consistent surface
API with the miniaudio backend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self, override

if TYPE_CHECKING:
    import types

try:
    import speech_recognition as sr
except Exception as exc:  # pragma: no cover - optional
    message = 'speech_recognition is required for PortAudioMicrophone'
    raise RuntimeError(message) from exc


class PortAudioMicrophone(sr.AudioSource):
    """PortAudio-based microphone wrapping speech_recognition.Microphone."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the PortAudio microphone wrapper."""
        self._inner: Any = sr.Microphone(*args, **kwargs)
        # Attributes will be populated in __enter__ via the inner source
        self.stream = None
        self.SAMPLE_RATE = None
        self.CHANNELS = None
        self.CHUNK = None
        self.SAMPLE_WIDTH = None

    @override
    def __enter__(self) -> Self:
        """Enter the context manager, opening the inner microphone stream.

        Returns:
            PortAudioMicrophone: This microphone instance with stream attributes populated.

        """
        source = self._inner.__enter__()
        # Mirror essential attributes used by Recognizer.listen
        self.stream = source.stream
        self.SAMPLE_RATE = source.SAMPLE_RATE  # pyright: ignore[reportConstantRedefinition]
        self.CHANNELS = source.CHANNELS if hasattr(source, 'CHANNELS') else 1  # pyright: ignore[reportConstantRedefinition]
        self.CHUNK = source.CHUNK  # pyright: ignore[reportConstantRedefinition]
        self.SAMPLE_WIDTH = source.SAMPLE_WIDTH  # pyright: ignore[reportConstantRedefinition]
        return self

    @override
    def __exit__(  # ty: ignore[invalid-method-override]
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: types.TracebackType | None,
    ) -> bool | None:
        """Exit the context manager, closing the inner microphone stream.

        Returns:
            bool | None: Whether to suppress the exception, if any.

        """
        return self._inner.__exit__(exc_type, exc, tb)
