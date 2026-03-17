"""Additional coverage tests for voice event handling.

Tests cover: VoiceEventProxy, _probe_microphone_backend edge cases,
_setup_microphone, _listen_loop with speech recognition, _process_command
matching paths, start/stop listening with active threads, exception handling,
and has_microphone.
"""

import threading

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

    def test_proxy_has_game_reference(self, mocker):
        """Test that VoiceEventProxy stores reference to the manager."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()
        proxy = manager.proxies[0]

        assert proxy.game is manager

    def test_proxy_proxies_list_contains_game(self, mocker):
        """Test that VoiceEventProxy.proxies contains the game reference."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()
        proxy = manager.proxies[0]

        assert manager in proxy.proxies


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

    def test_probe_logs_selected_backend_name(self, mocker):
        """Test probing logs the selected backend name on success."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)

        mock_probe_instance = mocker.Mock(spec=[])
        mock_final_instance = mocker.Mock()

        mock_mic_cls = mocker.Mock()
        mock_mic_cls.side_effect = [mock_probe_instance, mock_final_instance]
        mock_mic_cls.__name__ = 'CustomBackend'

        manager = VoiceEventManager.__new__(VoiceEventManager)
        manager.log = mocker.Mock()

        manager._probe_microphone_backend(mock_mic_cls)

        manager.log.info.assert_called_once()
        assert 'CustomBackend' in manager.log.info.call_args[0][0]

    def test_probe_oserror_logs_exception_with_backend_name(self, mocker):
        """Test probing logs exception with backend name on failure."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)

        mock_mic_cls = mocker.Mock(side_effect=OSError('device error'))
        mock_mic_cls.__name__ = 'FailingBackend'

        manager = VoiceEventManager.__new__(VoiceEventManager)
        manager.log = mocker.Mock()

        manager._probe_microphone_backend(mock_mic_cls)

        manager.log.exception.assert_called_once()
        assert 'FailingBackend' in manager.log.exception.call_args[0][0]


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

    def test_setup_microphone_attribute_error(self, mocker):
        """Test _setup_microphone handles AttributeError gracefully."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)
        mock_sr = mocker.patch('glitchygames.events.voice.sr')
        mock_sr.Microphone.side_effect = AttributeError('missing attribute')

        manager = VoiceEventManager.__new__(VoiceEventManager)
        manager.log = mocker.Mock()

        manager._setup_microphone()

        assert manager.microphone is None
        manager.log.error.assert_called_once()

    def test_setup_microphone_success(self, mocker):
        """Test _setup_microphone succeeds when microphone initializes properly."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)
        mock_sr = mocker.patch('glitchygames.events.voice.sr')
        mock_microphone = mocker.Mock()
        mock_sr.Microphone.return_value = mock_microphone

        manager = VoiceEventManager.__new__(VoiceEventManager)
        manager.log = mocker.Mock()

        manager._setup_microphone()

        assert manager.microphone is mock_microphone
        manager.log.info.assert_called_once()


class TestListenLoop:
    """Test _listen_loop edge cases and speech recognition paths."""

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

    def test_listen_loop_recognizes_speech_and_processes_command(self, mocker):
        """Test _listen_loop recognizes speech and calls _process_command."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)
        mock_sr = mocker.patch('glitchygames.events.voice.sr')

        # Set up real exception classes before creating manager
        mock_sr.UnknownValueError = type('UnknownValueError', (Exception,), {})
        mock_sr.RequestError = type('RequestError', (Exception,), {})
        mock_sr.WaitTimeoutError = type('WaitTimeoutError', (Exception,), {})

        mock_recognizer = mocker.Mock()
        mock_sr.Recognizer.return_value = mock_recognizer

        mocker.patch('glitchygames.events.voice.get_microphone_backend', return_value=None)
        mock_microphone = mocker.Mock()
        mock_sr.Microphone.return_value = mock_microphone
        mock_microphone.__enter__ = mocker.Mock(return_value=mock_microphone)
        mock_microphone.__exit__ = mocker.Mock(return_value=False)

        manager = VoiceEventManager()
        # Ensure the manager has a valid microphone and recognizer for the loop
        manager.microphone = mock_microphone
        manager.recognizer = mock_recognizer
        manager.is_listening = True
        mock_process_command = mocker.patch.object(manager, '_process_command')

        mock_audio = mocker.Mock()
        mock_recognizer.recognize_google.return_value = 'Hello World'

        # After one iteration, stop listening
        call_count = [0]

        def stop_after_first(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 1:
                manager.is_listening = False
            return mock_audio

        mock_recognizer.listen.side_effect = stop_after_first

        manager._listen_loop()

        mock_process_command.assert_called_with('hello world')

    def test_listen_loop_handles_unknown_value_error(self, mocker):
        """Test _listen_loop handles UnknownValueError from recognizer."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)
        mock_sr = mocker.patch('glitchygames.events.voice.sr')

        mock_sr.UnknownValueError = type('UnknownValueError', (Exception,), {})
        mock_sr.RequestError = type('RequestError', (Exception,), {})
        mock_sr.WaitTimeoutError = type('WaitTimeoutError', (Exception,), {})

        mock_recognizer = mocker.Mock()
        mock_sr.Recognizer.return_value = mock_recognizer

        mocker.patch('glitchygames.events.voice.get_microphone_backend', return_value=None)
        mock_microphone = mocker.Mock()
        mock_sr.Microphone.return_value = mock_microphone
        mock_microphone.__enter__ = mocker.Mock(return_value=mock_microphone)
        mock_microphone.__exit__ = mocker.Mock(return_value=False)

        manager = VoiceEventManager()
        mock_audio = mocker.Mock()
        mock_recognizer.recognize_google.side_effect = mock_sr.UnknownValueError()

        call_count = [0]

        def stop_after_first(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 1:
                manager.is_listening = False
            return mock_audio

        mock_recognizer.listen.side_effect = stop_after_first

        # Should not raise
        manager._listen_loop()

    def test_listen_loop_handles_request_error(self, mocker):
        """Test _listen_loop handles RequestError and waits before retrying."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)
        mock_sr = mocker.patch('glitchygames.events.voice.sr')

        mock_sr.UnknownValueError = type('UnknownValueError', (Exception,), {})
        mock_sr.RequestError = type('RequestError', (Exception,), {})
        mock_sr.WaitTimeoutError = type('WaitTimeoutError', (Exception,), {})

        mock_recognizer = mocker.Mock()
        mock_sr.Recognizer.return_value = mock_recognizer

        mocker.patch('glitchygames.events.voice.get_microphone_backend', return_value=None)
        mock_microphone = mocker.Mock()
        mock_sr.Microphone.return_value = mock_microphone
        mock_microphone.__enter__ = mocker.Mock(return_value=mock_microphone)
        mock_microphone.__exit__ = mocker.Mock(return_value=False)

        manager = VoiceEventManager()
        # Ensure manager has microphone and recognizer set for the loop
        manager.microphone = mock_microphone
        manager.recognizer = mock_recognizer
        manager.is_listening = True
        mock_audio = mocker.Mock()
        mock_recognizer.recognize_google.side_effect = mock_sr.RequestError('service unavailable')

        mock_sleep = mocker.patch('glitchygames.events.voice.time.sleep')

        call_count = [0]

        def stop_after_first(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 1:
                manager.is_listening = False
            return mock_audio

        mock_recognizer.listen.side_effect = stop_after_first

        manager._listen_loop()

        mock_sleep.assert_called_with(2)

    def test_listen_loop_handles_wait_timeout_error(self, mocker):
        """Test _listen_loop handles WaitTimeoutError by continuing."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)
        mock_sr = mocker.patch('glitchygames.events.voice.sr')

        mock_sr.UnknownValueError = type('UnknownValueError', (Exception,), {})
        mock_sr.RequestError = type('RequestError', (Exception,), {})
        mock_sr.WaitTimeoutError = type('WaitTimeoutError', (Exception,), {})

        mock_recognizer = mocker.Mock()
        mock_sr.Recognizer.return_value = mock_recognizer

        mocker.patch('glitchygames.events.voice.get_microphone_backend', return_value=None)
        mock_microphone = mocker.Mock()
        mock_sr.Microphone.return_value = mock_microphone
        mock_microphone.__enter__ = mocker.Mock(return_value=mock_microphone)
        mock_microphone.__exit__ = mocker.Mock(return_value=False)

        manager = VoiceEventManager()

        call_count = [0]

        def timeout_then_stop(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 1:
                manager.is_listening = False
                raise mock_sr.WaitTimeoutError
            raise mock_sr.WaitTimeoutError

        mock_recognizer.listen.side_effect = timeout_then_stop

        # Should not raise
        manager._listen_loop()

    def test_listen_loop_handles_oserror(self, mocker):
        """Test _listen_loop handles OSError and sleeps before retrying."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)
        mock_sr = mocker.patch('glitchygames.events.voice.sr')

        mock_sr.UnknownValueError = type('UnknownValueError', (Exception,), {})
        mock_sr.RequestError = type('RequestError', (Exception,), {})
        mock_sr.WaitTimeoutError = type('WaitTimeoutError', (Exception,), {})

        mock_recognizer = mocker.Mock()
        mock_sr.Recognizer.return_value = mock_recognizer

        mocker.patch('glitchygames.events.voice.get_microphone_backend', return_value=None)
        mock_microphone = mocker.Mock()
        mock_sr.Microphone.return_value = mock_microphone
        mock_microphone.__enter__ = mocker.Mock(return_value=mock_microphone)
        mock_microphone.__exit__ = mocker.Mock(return_value=False)

        manager = VoiceEventManager()
        # Ensure manager has microphone and recognizer set for the loop
        manager.microphone = mock_microphone
        manager.recognizer = mock_recognizer
        manager.is_listening = True
        mock_sleep = mocker.patch('glitchygames.events.voice.time.sleep')

        call_count = [0]

        def oserror_then_stop(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 1:
                manager.is_listening = False
            raise OSError('device error')

        mock_recognizer.listen.side_effect = oserror_then_stop

        manager._listen_loop()

        mock_sleep.assert_called_with(1)

    def test_listen_loop_stops_when_stop_event_set(self, mocker):
        """Test _listen_loop stops when stop_listening_event is set."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)
        mock_sr = mocker.patch('glitchygames.events.voice.sr')

        mock_sr.WaitTimeoutError = type('WaitTimeoutError', (Exception,), {})

        mock_recognizer = mocker.Mock()
        mock_sr.Recognizer.return_value = mock_recognizer

        mocker.patch('glitchygames.events.voice.get_microphone_backend', return_value=None)
        mock_microphone = mocker.Mock()
        mock_sr.Microphone.return_value = mock_microphone
        mock_microphone.__enter__ = mocker.Mock(return_value=mock_microphone)
        mock_microphone.__exit__ = mocker.Mock(return_value=False)

        manager = VoiceEventManager()
        manager.stop_listening_event.set()

        # Loop should exit immediately since stop event is set
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

    def test_start_listening_no_microphone(self, mocker):
        """Test start_listening logs error when microphone not available."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)
        mock_sr = mocker.patch('glitchygames.events.voice.sr')
        mock_sr.Recognizer = mocker.Mock()
        mocker.patch('glitchygames.events.voice.get_microphone_backend', return_value=None)
        mock_sr.Microphone.side_effect = OSError('no mic')

        manager = VoiceEventManager()
        manager.microphone = None

        manager.start_listening()

        assert manager.is_listening is False

    def test_start_listening_no_speech_recognition(self, mocker):
        """Test start_listening warns when speech recognition unavailable."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)

        manager = VoiceEventManager()

        manager.start_listening()

        assert manager.is_listening is False

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

    def test_stop_listening_when_not_listening(self, mocker):
        """Test stop_listening returns early when not listening."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()
        manager.is_listening = False

        # Should return immediately without any error
        manager.stop_listening()
        assert manager.is_listening is False

    def test_stop_listening_thread_stops_cleanly(self, mocker):
        """Test stop_listening when thread is alive and stops cleanly within timeout."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()
        manager.is_listening = True

        mock_thread = mocker.Mock()
        # Thread is alive, so join will be called; then is_alive returns False (stopped cleanly)
        mock_thread.is_alive.side_effect = [True, False]
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


class TestIsAvailable:
    """Test is_available method."""

    def test_is_available_true_when_speech_and_microphone(self, mocker):
        """Test is_available returns True when both SR and mic are available."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)
        mock_sr = mocker.patch('glitchygames.events.voice.sr')
        mock_sr.Recognizer = mocker.Mock()
        mocker.patch('glitchygames.events.voice.get_microphone_backend', return_value=None)
        mock_sr.Microphone.return_value = mocker.Mock()

        manager = VoiceEventManager()

        assert manager.is_available() is True

    def test_is_available_false_when_no_speech_recognition(self, mocker):
        """Test is_available returns False when SR not available."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()

        assert manager.is_available() is False

    def test_is_available_false_when_no_microphone(self, mocker):
        """Test is_available returns False when microphone is None."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)
        mock_sr = mocker.patch('glitchygames.events.voice.sr')
        mock_sr.Recognizer = mocker.Mock()
        mocker.patch('glitchygames.events.voice.get_microphone_backend', return_value=None)
        mock_sr.Microphone.side_effect = OSError('no mic')

        manager = VoiceEventManager()

        assert manager.is_available() is False


class TestGetAvailableCommands:
    """Test get_available_commands method."""

    def test_get_available_commands_empty(self, mocker):
        """Test get_available_commands returns empty list when no commands registered."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()

        result = manager.get_available_commands()
        assert result == []

    def test_get_available_commands_with_registered_commands(self, mocker):
        """Test get_available_commands returns registered command phrases."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()

        manager.register_command('save', mocker.Mock())
        manager.register_command('undo', mocker.Mock())

        result = manager.get_available_commands()
        assert 'save' in result
        assert 'undo' in result
        assert len(result) == 2


class TestRegisterCommand:
    """Test register_command method."""

    def test_register_command_lowercases_phrase(self, mocker):
        """Test register_command stores the phrase in lowercase."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()
        callback = mocker.Mock()

        manager.register_command('SAVE FILE', callback)

        assert 'save file' in manager.commands
        assert manager.commands['save file'] is callback

    def test_register_command_overwrites_existing(self, mocker):
        """Test register_command overwrites existing command with same phrase."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()
        first_callback = mocker.Mock()
        second_callback = mocker.Mock()

        manager.register_command('undo', first_callback)
        manager.register_command('undo', second_callback)

        assert manager.commands['undo'] is second_callback


class TestProcessCommandEdgeCases:
    """Test _process_command edge cases."""

    def test_exact_match_executes_callback(self, mocker):
        """Test _process_command executes exact match callback."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()
        callback = mocker.Mock()

        manager.register_command('save', callback)
        manager._process_command('save')

        callback.assert_called_once()

    def test_exact_match_callback_error_is_logged(self, mocker):
        """Test _process_command logs exception when exact match callback raises."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)

        mock_get_logger = mocker.patch('glitchygames.events.voice.logging.getLogger')
        mock_log = mocker.Mock()
        mock_get_logger.return_value = mock_log

        manager = VoiceEventManager()
        callback = mocker.Mock(side_effect=RuntimeError('boom'))

        manager.register_command('crash', callback)
        manager._process_command('crash')

        callback.assert_called_once()
        mock_log.exception.assert_called_once()

    def test_partial_match_executes_callback(self, mocker):
        """Test _process_command executes partial match callback."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()
        callback = mocker.Mock()

        manager.register_command('save file', callback)

        # "please save file now" contains "save file" as a partial match
        manager._process_command('please save file now')

        callback.assert_called_once()

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

    def test_no_match_logs_debug(self, mocker):
        """Test _process_command logs debug message when no match found."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)

        mock_get_logger = mocker.patch('glitchygames.events.voice.logging.getLogger')
        mock_log = mocker.Mock()
        mock_get_logger.return_value = mock_log

        manager = VoiceEventManager()
        manager.register_command('save', mocker.Mock())

        manager._process_command('completely different text')

        mock_log.debug.assert_called()

    def test_exact_match_takes_priority_over_partial(self, mocker):
        """Test _process_command prefers exact match over partial match."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()
        exact_callback = mocker.Mock()
        partial_callback = mocker.Mock()

        manager.register_command('save', exact_callback)
        manager.register_command('sav', partial_callback)

        manager._process_command('save')

        exact_callback.assert_called_once()
        partial_callback.assert_not_called()


class TestVoiceEventManagerInitialization:
    """Test VoiceEventManager initialization paths."""

    def test_init_without_logger(self, mocker):
        """Test initialization without providing a logger uses default."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()

        assert manager.log is not None

    def test_init_with_custom_logger(self, mocker):
        """Test initialization with a custom logger."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        custom_logger = mocker.Mock()
        manager = VoiceEventManager(logger=custom_logger)

        assert manager.log is custom_logger

    def test_init_with_sr_available_and_backend(self, mocker):
        """Test initialization when speech recognition is available with a backend."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)
        mock_sr = mocker.patch('glitchygames.events.voice.sr')
        mock_sr.Recognizer = mocker.Mock()

        mock_mic_cls = mocker.Mock()
        mock_probe_instance = mocker.Mock(spec=[])
        mock_final_instance = mocker.Mock()
        mock_mic_cls.side_effect = [mock_probe_instance, mock_final_instance]
        mocker.patch('glitchygames.events.voice.get_microphone_backend', return_value=mock_mic_cls)

        manager = VoiceEventManager()

        assert manager.microphone is mock_final_instance

    def test_init_with_sr_available_no_backend_fallback(self, mocker):
        """Test initialization falls back to sr.Microphone when no backend available."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)
        mock_sr = mocker.patch('glitchygames.events.voice.sr')
        mock_sr.Recognizer = mocker.Mock()
        mock_microphone = mocker.Mock()
        mock_sr.Microphone.return_value = mock_microphone

        mocker.patch('glitchygames.events.voice.get_microphone_backend', return_value=None)

        manager = VoiceEventManager()

        assert manager.microphone is mock_microphone

    def test_init_stop_listening_event_created(self, mocker):
        """Test initialization creates a threading Event for stop signaling."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)
        manager = VoiceEventManager()

        assert isinstance(manager.stop_listening_event, threading.Event)
        assert not manager.stop_listening_event.is_set()
