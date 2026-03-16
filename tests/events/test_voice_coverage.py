"""Additional coverage tests for voice event handling.

Tests cover: VoiceEventProxy, _probe_microphone_backend edge cases,
_setup_microphone, _listen_loop, start/stop listening with active threads,
and has_microphone.
"""

import pytest

from glitchygames.events.voice import VoiceEventManager

pytestmark = pytest.mark.usefixtures('mock_pygame_patches')


class TestVoiceEventProxy:
    """Test VoiceEventProxy delegation methods."""

    def test_proxy_start_listening_delegates(self, mocker):
        """Test that VoiceEventProxy.start_listening delegates to the manager."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()
        proxy = manager.proxies[0]

        mock_start = mocker.patch.object(manager, 'start_listening')
        proxy.start_listening()
        mock_start.assert_called_once()

    def test_proxy_stop_listening_delegates(self, mocker):
        """Test that VoiceEventProxy.stop_listening delegates to the manager."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()
        proxy = manager.proxies[0]

        mock_stop = mocker.patch.object(manager, 'stop_listening')
        proxy.stop_listening()
        mock_stop.assert_called_once()

    def test_proxy_register_command_delegates(self, mocker):
        """Test that VoiceEventProxy.register_command delegates to the manager."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()
        proxy = manager.proxies[0]

        callback = mocker.Mock()
        mock_register = mocker.patch.object(manager, 'register_command')
        proxy.register_command('test', callback)
        mock_register.assert_called_once_with('test', callback)


class TestProbeMicrophoneBackend:
    """Test _probe_microphone_backend edge cases."""

    def test_probe_success_with_context_manager(self, mocker):
        """Test probing a backend that supports __enter__/__exit__."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)
        mock_sr = mocker.patch('glitchygames.events.voice.sr')
        mock_sr.Recognizer = mocker.Mock()
        mock_sr.Microphone = mocker.Mock()

        # Create a mock backend class that supports context manager protocol
        mock_mic_cls = mocker.Mock()
        mock_probe_instance = mocker.Mock()
        mock_probe_instance.__enter__ = mocker.Mock(return_value=mock_probe_instance)
        mock_probe_instance.__exit__ = mocker.Mock(return_value=False)
        mock_final_instance = mocker.Mock()
        mock_mic_cls.side_effect = [mock_probe_instance, mock_final_instance]

        mocker.patch('glitchygames.events.voice.get_microphone_backend', return_value=None)

        manager = VoiceEventManager.__new__(VoiceEventManager)
        manager.log = mocker.Mock()

        result = manager._probe_microphone_backend(mock_mic_cls)

        assert result is mock_final_instance

    def test_probe_oserror_returns_none(self, mocker):
        """Test probing a backend that raises OSError."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)

        mock_mic_cls = mocker.Mock(side_effect=OSError('no audio device'))
        mock_mic_cls.__name__ = 'FakeBackend'

        manager = VoiceEventManager.__new__(VoiceEventManager)
        manager.log = mocker.Mock()

        result = manager._probe_microphone_backend(mock_mic_cls)

        assert result is None

    def test_probe_exit_oserror_is_suppressed(self, mocker):
        """Test that OSError during __exit__ cleanup is suppressed."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)

        mock_probe_instance = mocker.Mock()
        mock_probe_instance.__enter__ = mocker.Mock(return_value=mock_probe_instance)
        mock_probe_instance.__exit__ = mocker.Mock(side_effect=OSError('cleanup failed'))

        mock_final_instance = mocker.Mock()

        mock_mic_cls = mocker.Mock()
        mock_mic_cls.side_effect = [mock_probe_instance, mock_final_instance]
        mock_mic_cls.__name__ = 'TestBackend'

        manager = VoiceEventManager.__new__(VoiceEventManager)
        manager.log = mocker.Mock()

        result = manager._probe_microphone_backend(mock_mic_cls)

        assert result is mock_final_instance

    def test_probe_without_context_manager(self, mocker):
        """Test probing a backend that does not support __enter__/__exit__."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)

        # Instance without __enter__ or __exit__
        mock_probe_instance = mocker.Mock(spec=[])
        mock_final_instance = mocker.Mock()

        mock_mic_cls = mocker.Mock()
        mock_mic_cls.side_effect = [mock_probe_instance, mock_final_instance]
        mock_mic_cls.__name__ = 'SimpleBackend'

        manager = VoiceEventManager.__new__(VoiceEventManager)
        manager.log = mocker.Mock()

        result = manager._probe_microphone_backend(mock_mic_cls)

        assert result is mock_final_instance


class TestSetupMicrophone:
    """Test _setup_microphone edge cases."""

    def test_setup_microphone_oserror(self, mocker):
        """Test _setup_microphone handles OSError gracefully."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)
        mock_sr = mocker.patch('glitchygames.events.voice.sr')
        mock_sr.Microphone.side_effect = OSError('No audio device')

        manager = VoiceEventManager.__new__(VoiceEventManager)
        manager.log = mocker.Mock()

        manager._setup_microphone()

        assert manager.microphone is None
        manager.log.error.assert_called_once()

    def test_setup_microphone_not_available(self, mocker):
        """Test _setup_microphone when speech recognition is not available."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)

        manager = VoiceEventManager.__new__(VoiceEventManager)
        manager.log = mocker.Mock()

        manager._setup_microphone()

        assert manager.microphone is None


class TestListenLoop:
    """Test _listen_loop edge cases."""

    def test_listen_loop_no_speech_recognition(self, mocker):
        """Test _listen_loop exits immediately when speech recognition unavailable."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()

        # Should exit immediately without error
        manager._listen_loop()

    def test_listen_loop_no_microphone(self, mocker):
        """Test _listen_loop exits when microphone is None."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)
        mock_sr = mocker.patch('glitchygames.events.voice.sr')
        mock_sr.Recognizer = mocker.Mock()
        mocker.patch('glitchygames.events.voice.get_microphone_backend', return_value=None)
        mock_sr.Microphone = mocker.Mock()
        mock_sr.Microphone.return_value = mocker.Mock()

        manager = VoiceEventManager()
        manager.microphone = None

        # Should exit immediately without error
        manager._listen_loop()


class TestStartStopListening:
    """Test start_listening and stop_listening edge cases."""

    def test_start_listening_already_listening(self, mocker):
        """Test start_listening when already listening logs warning."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)
        mock_sr = mocker.patch('glitchygames.events.voice.sr')
        mock_sr.Recognizer = mocker.Mock()

        mock_mic_cls = mocker.Mock()
        mock_mic_cls.return_value = mocker.Mock()
        mocker.patch('glitchygames.events.voice.get_microphone_backend', return_value=mock_mic_cls)

        manager = VoiceEventManager()
        manager.is_listening = True

        manager.start_listening()

        # Should not have created a thread
        assert manager.listen_thread is None

    def test_stop_listening_thread_alive_after_join(self, mocker):
        """Test stop_listening warns when thread does not stop cleanly."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()

        manager.is_listening = True

        mock_thread = mocker.Mock()
        mock_thread.is_alive.return_value = True
        manager.listen_thread = mock_thread

        manager.stop_listening()

        assert manager.is_listening is False
        mock_thread.join.assert_called_once_with(timeout=2.0)


class TestHasMicrophone:
    """Test has_microphone method."""

    def test_has_microphone_true(self, mocker):
        """Test has_microphone returns True when microphone exists."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()
        manager.microphone = mocker.Mock()

        assert manager.has_microphone() is True

    def test_has_microphone_false(self, mocker):
        """Test has_microphone returns False when microphone is None."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()

        assert manager.has_microphone() is False


class TestProcessCommandEdgeCases:
    """Test _process_command edge cases."""

    def test_partial_match_callback_error(self, mocker):
        """Test _process_command handles errors in partial-match callbacks."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)

        mock_get_logger = mocker.patch('glitchygames.events.voice.logging.getLogger')
        mock_log = mocker.Mock()
        mock_get_logger.return_value = mock_log

        manager = VoiceEventManager()
        callback = mocker.Mock(side_effect=RuntimeError('boom'))

        manager.register_command('save file', callback)

        # "please save file now" contains "save file" as a partial match
        manager._process_command('please save file now')

        callback.assert_called_once()
        mock_log.exception.assert_called_once()
