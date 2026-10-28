"""Tests for text-to-speech backends (glitchygames/audio/tts.py).

The macOS ``say`` command is never run: ``shutil.which``, ``sys.platform`` and
``run_command`` (glitchygames.process, the engine's one child-process launcher) are the boundary
and are mocked.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from glitchygames import process
from glitchygames.audio import tts
from glitchygames.process import OutputCapture

FAKE_SAY_PATH = '/usr/bin/say'


@pytest.fixture
def macos_with_say(mocker):
    """Pretend to run on macOS with ``say`` on the PATH.

    Returns:
        The mock standing in for run_command (``say`` succeeds).

    """
    mocker.patch.object(tts.shutil, 'which', return_value=FAKE_SAY_PATH)
    mocker.patch.object(tts.sys, 'platform', 'darwin')
    return mocker.patch.object(
        tts,
        'run_command',
        return_value=process.CompletedProcess(args=[], returncode=0, stdout=''),
    )


class TestMacOSTTSAvailability:
    """A MacOS backend is available only on darwin with ``say`` installed."""

    def test_available_on_darwin_with_say(self, macos_with_say):
        """Darwin plus a found ``say`` is available."""
        backend = tts.MacOSTTS(voice='Alex', rate=150)

        assert backend.available is True
        assert backend.voice == 'Alex'

    def test_unavailable_without_say(self, mocker):
        """Without ``say`` on the PATH the backend is unavailable even on darwin."""
        mocker.patch.object(tts.shutil, 'which', return_value=None)
        mocker.patch.object(tts.sys, 'platform', 'darwin')

        assert tts.MacOSTTS().available is False

    def test_unavailable_on_other_platforms(self, mocker):
        """A ``say`` found on Linux is not the macOS command."""
        mocker.patch.object(tts.shutil, 'which', return_value=FAKE_SAY_PATH)
        mocker.patch.object(tts.sys, 'platform', 'linux')

        assert tts.MacOSTTS().available is False


class TestMacOSTTSSpeakToFile:
    """speak_to_file runs ``say`` with the voice, rate and output format, and reports failure."""

    def test_unavailable_backend_returns_none_without_running_say(self, mocker):
        """An unavailable backend never starts a process."""
        mocker.patch.object(tts.shutil, 'which', return_value=None)
        run = mocker.patch.object(tts, 'run_command')

        assert tts.MacOSTTS().speak_to_file('hello') is None
        run.assert_not_called()

    def test_writes_to_the_given_path(self, macos_with_say, tmp_path):
        """The command names the voice, rate, output file, 48 kHz LEI16 format and text."""
        output_path = tmp_path / 'speech.wav'
        backend = tts.MacOSTTS(voice='Samantha', rate=180)

        result = backend.speak_to_file('Hello, adventurer!', output_path=output_path)

        assert result == output_path
        macos_with_say.assert_called_once_with(
            command=[
                FAKE_SAY_PATH,
                '-v',
                'Samantha',
                '-r',
                '180',
                '-o',
                str(output_path),
                '--data-format=LEI16@48000',
                'Hello, adventurer!',
            ],
            environment=os.environ,
            timeout_seconds=30,
            capture_output=OutputCapture.TOGETHER,
        )

    def test_creates_a_temporary_wav_without_a_path(self, macos_with_say):
        """Without an output path a .wav temp file is created and returned."""
        result = tts.MacOSTTS().speak_to_file('temp please')

        assert result is not None
        try:
            assert result.suffix == '.wav'
            assert result.exists()
            command = macos_with_say.call_args.kwargs['command']
            assert command[command.index('-o') + 1] == str(result)
        finally:
            result.unlink()

    def test_failed_say_returns_none_and_logs_its_output(self, macos_with_say, tmp_path, caplog):
        """A ``say`` that exits non-zero gives None and an error log with its exit and output."""
        macos_with_say.return_value = process.CompletedProcess(
            args=[], returncode=1, stdout='Voice not found'
        )

        with caplog.at_level(logging.ERROR, logger='game.audio.tts'):
            result = tts.MacOSTTS().speak_to_file('oops', output_path=tmp_path / 'x.wav')

        assert result is None
        assert 'TTS generation failed' in caplog.text
        assert 'exit 1' in caplog.text
        assert 'Voice not found' in caplog.text

    @pytest.mark.parametrize(
        'failure',
        [
            process.TimeoutExpired(cmd='say', timeout=30),
            OSError('exec format error'),
        ],
    )
    def test_failures_return_none_and_log(self, macos_with_say, tmp_path, caplog, failure):
        """A hung or unstartable ``say`` gives None and an error log."""
        macos_with_say.side_effect = failure

        with caplog.at_level(logging.ERROR, logger='game.audio.tts'):
            result = tts.MacOSTTS().speak_to_file('oops', output_path=tmp_path / 'x.wav')

        assert result is None
        assert 'TTS generation failed' in caplog.text


class TestGetTTSBackend:
    """get_tts_backend picks the macOS backend when it works, else None."""

    def test_returns_macos_backend_when_available(self, macos_with_say):
        """On macOS with ``say`` the MacOSTTS backend is returned."""
        backend = tts.get_tts_backend()

        assert isinstance(backend, tts.MacOSTTS)
        assert backend.available is True

    def test_returns_none_and_warns_elsewhere(self, mocker, caplog):
        """With no working backend the result is None and a warning is logged."""
        mocker.patch.object(tts.shutil, 'which', return_value=None)

        with caplog.at_level(logging.WARNING, logger='game.audio.tts'):
            backend = tts.get_tts_backend()

        assert backend is None
        assert 'No TTS backend available' in caplog.text


def test_output_path_type_is_path(macos_with_say, tmp_path):
    """The returned value is a Path even when given one (no str round trip)."""
    output_path = tmp_path / 'typed.wav'

    assert isinstance(tts.MacOSTTS().speak_to_file('x', output_path=output_path), Path)
