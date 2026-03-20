#!/usr/bin/env python3
"""Miniaudio-backed AudioSource compatible with speech_recognition.

This module provides a drop-in replacement for `speech_recognition.Microphone`
that uses `miniaudio` instead of PortAudio/PyAudio or sounddevice.
"""

from __future__ import annotations

import threading
from collections import deque
from typing import TYPE_CHECKING, Any, Self, override

if TYPE_CHECKING:
    import types
    from collections.abc import Generator

try:
    import miniaudio as mi
except ImportError:  # pragma: no cover - optional dependency
    mi = None  # ty: ignore[invalid-assignment]

try:
    import speech_recognition as sr
except ImportError:  # pragma: no cover - test environments may skip
    sr = None  # ty: ignore[invalid-assignment]


class _BlockingByteStream:
    """Simple blocking byte stream with read(size) -> bytes."""

    def __init__(self) -> None:
        self._buf: deque[bytes] = deque()
        self._size: int = 0
        self._cv = threading.Condition()
        self._closed = False

    def write(self, data: bytes) -> None:
        if not data:
            return
        with self._cv:
            self._buf.append(data)
            self._size += len(data)
            self._cv.notify_all()

    def read(self, size: int) -> bytes:
        with self._cv:
            while self._size < size and not self._closed:
                self._cv.wait(timeout=0.5)
            if self._size == 0 and self._closed:
                return b''
            chunks: list[bytes] = []
            remaining = size
            while self._buf and remaining > 0:
                chunk = self._buf[0]
                if len(chunk) <= remaining:
                    chunks.append(chunk)
                    self._buf.popleft()
                    self._size -= len(chunk)
                    remaining -= len(chunk)
                else:
                    chunks.append(chunk[:remaining])
                    self._buf[0] = chunk[remaining:]
                    self._size -= remaining
                    remaining = 0
            # If we still didn't get enough and closed, return what we have
            return b''.join(chunks)

    def close(self) -> None:
        with self._cv:
            self._closed = True
            self._cv.notify_all()


class MiniaudioMicrophone(sr.AudioSource):  # type: ignore[union-attr]
    """Miniaudio-based microphone compatible with speech_recognition.AudioSource."""

    def __init__(
        self,
        device_index: int | None = None,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 1024,
        sample_width: int = 2,
    ) -> None:
        """Initialize the miniaudio microphone capture device.

        Raises:
            RuntimeError: If miniaudio is not installed.

        """
        if mi is None:
            raise RuntimeError('miniaudio is not installed')
        self.device_index = device_index
        self.SAMPLE_RATE = sample_rate
        self.CHANNELS = channels
        self.CHUNK = chunk_size
        self.SAMPLE_WIDTH = sample_width  # bytes per sample
        self.stream: _BlockingByteStream | None = None
        self._device: Any = None

    @override
    def __enter__(self) -> Self:
        """Enter the context manager, starting audio capture.

        Returns:
            MiniaudioMicrophone: The result.

        """
        self.stream = _BlockingByteStream()

        def _capture_generator() -> Generator[None, bytes | None]:
            """Generator that receives captured audio data and writes to the stream."""
            while True:
                data = yield
                if self.stream and data:
                    self.stream.write(bytes(data))

        # Configure capture device
        self._device = mi.CaptureDevice(  # type: ignore[union-attr]
            input_format=mi.SampleFormat.SIGNED16,  # type: ignore[union-attr]
            nchannels=self.CHANNELS,
            sample_rate=self.SAMPLE_RATE,
            device_id=self.device_index,
        )
        generator = _capture_generator()
        next(generator)  # Prime the generator
        self._device.start(generator)  # ty: ignore[invalid-argument-type]
        return self

    @override
    def __exit__(  # ty: ignore[invalid-method-override]
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: types.TracebackType | None,
    ) -> None:
        """Exit the context manager, stopping audio capture and cleaning up."""
        try:
            if self._device is not None:
                self._device.stop()
        finally:
            if self.stream is not None:
                self.stream.close()
            self._device = None
