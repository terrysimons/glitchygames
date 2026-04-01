"""Text-to-speech with pluggable backends.

Generates audio files from text for playback through controller
speakers or system audio. Ships with a macOS backend using the
``say`` command; cross-platform backends can be added later.

Usage:
    tts = get_tts_backend()
    if tts:
        path = tts.speak_to_file('Hello, adventurer!')
        controller_audio.play_file(path)
"""

from __future__ import annotations

import logging
import shutil
import subprocess  # noqa: S404 — used for macOS 'say' command only
import sys
import tempfile
from pathlib import Path
from typing import Protocol

log: logging.Logger = logging.getLogger('game.audio.tts')


class TTSBackend(Protocol):
    """Protocol for text-to-speech backends."""

    def speak_to_file(self, text: str, output_path: Path | None = None) -> Path | None:
        """Generate an audio file from text.

        Args:
            text: The text to speak.
            output_path: Optional output path. If None, a temp file is created.

        Returns:
            Path to the generated audio file, or None on failure.

        """
        ...

    @property
    def available(self) -> bool:
        """Whether this TTS backend is functional."""
        ...


class MacOSTTS:
    """macOS text-to-speech using the ``say`` command.

    Generates AIFF audio files that miniaudio can play.
    """

    def __init__(self, voice: str = 'Samantha', rate: int = 200) -> None:
        """Initialize macOS TTS.

        Args:
            voice: The macOS voice name (see ``say -v '?'``).
            rate: Speech rate in words per minute.

        """
        self.voice = voice
        self._rate = rate
        self._say_path = shutil.which('say')

    @property
    def available(self) -> bool:
        """Whether the ``say`` command is available."""
        return sys.platform == 'darwin' and self._say_path is not None

    def speak_to_file(self, text: str, output_path: Path | None = None) -> Path | None:
        """Generate a WAV audio file from text using macOS ``say``.

        Args:
            text: The text to speak.
            output_path: Optional output path. If None, a temp file is created.

        Returns:
            Path to the generated WAV file, or None on failure.

        """
        if not self.available:
            return None

        if output_path is None:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_fd:
                output_path = Path(temp_fd.name)

        say_path = self._say_path or 'say'
        try:
            subprocess.run(  # noqa: S603 — 'say' is a trusted macOS system command
                [
                    say_path,
                    '-v',
                    self.voice,
                    '-r',
                    str(self._rate),
                    '-o',
                    str(output_path),
                    '--data-format=LEI16@48000',
                    text,
                ],
                check=True,
                capture_output=True,
                timeout=30,
            )
        except subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError:
            log.exception('TTS generation failed')
            return None
        else:
            log.info('TTS generated: %s (%d chars)', output_path.name, len(text))
            return output_path


def get_tts_backend() -> TTSBackend | None:
    """Get the best available TTS backend for the current platform.

    Returns:
        A TTSBackend instance, or None if no backend is available.

    """
    # macOS: use the built-in 'say' command
    macos_tts = MacOSTTS()
    if macos_tts.available:
        log.info('Using macOS TTS backend (voice: %s)', macos_tts.voice)
        return macos_tts

    # Future: add Windows SAPI, espeak, etc.
    log.warning('No TTS backend available on this platform')
    return None
