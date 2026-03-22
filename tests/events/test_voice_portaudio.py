"""Tests for the PortAudio voice backend."""

import importlib.util

import pytest

sr_available = importlib.util.find_spec('speech_recognition') is not None


@pytest.mark.skipif(not sr_available, reason='speech_recognition not installed')
class TestPortAudioMicrophone:
    """Tests for the PortAudioMicrophone class."""

    def test_initialization(self, mocker):
        """Test that PortAudioMicrophone wraps sr.Microphone."""
        mock_microphone = mocker.Mock()
        mocker.patch(
            'glitchygames.events.voice_backends.voice_portaudio.sr.Microphone',
            return_value=mock_microphone,
        )

        from glitchygames.events.voice_backends.voice_portaudio import PortAudioMicrophone

        mic = PortAudioMicrophone()
        assert mic._inner is mock_microphone
        assert mic.stream is None
        assert mic.SAMPLE_RATE is None
        assert mic.CHANNELS is None
        assert mic.CHUNK is None
        assert mic.SAMPLE_WIDTH is None

    def test_context_manager_mirrors_attributes(self, mocker):
        """Test that entering context mirrors attributes from inner microphone."""
        mock_inner_source = mocker.Mock()
        mock_inner_source.stream = mocker.Mock()
        mock_inner_source.SAMPLE_RATE = 44100
        mock_inner_source.CHANNELS = 2
        mock_inner_source.CHUNK = 1024
        mock_inner_source.SAMPLE_WIDTH = 2

        mock_microphone = mocker.Mock()
        mock_microphone.__enter__ = mocker.Mock(return_value=mock_inner_source)
        mock_microphone.__exit__ = mocker.Mock(return_value=None)

        mocker.patch(
            'glitchygames.events.voice_backends.voice_portaudio.sr.Microphone',
            return_value=mock_microphone,
        )

        from glitchygames.events.voice_backends.voice_portaudio import PortAudioMicrophone

        mic = PortAudioMicrophone()
        with mic as active_mic:
            assert active_mic is mic
            assert mic.stream is mock_inner_source.stream
            assert mic.SAMPLE_RATE == 44100
            assert mic.CHANNELS == 2
            assert mic.CHUNK == 1024
            assert mic.SAMPLE_WIDTH == 2

    def test_context_manager_without_channels_attribute(self, mocker):
        """Test that entering context defaults CHANNELS to 1 if not on inner source."""
        mock_inner_source = mocker.Mock(spec=['stream', 'SAMPLE_RATE', 'CHUNK', 'SAMPLE_WIDTH'])
        mock_inner_source.stream = mocker.Mock()
        mock_inner_source.SAMPLE_RATE = 16000
        mock_inner_source.CHUNK = 512
        mock_inner_source.SAMPLE_WIDTH = 2

        mock_microphone = mocker.Mock()
        mock_microphone.__enter__ = mocker.Mock(return_value=mock_inner_source)
        mock_microphone.__exit__ = mocker.Mock(return_value=None)

        mocker.patch(
            'glitchygames.events.voice_backends.voice_portaudio.sr.Microphone',
            return_value=mock_microphone,
        )

        from glitchygames.events.voice_backends.voice_portaudio import PortAudioMicrophone

        mic = PortAudioMicrophone()
        with mic:
            assert mic.CHANNELS == 1

    def test_exit_delegates_to_inner(self, mocker):
        """Test that exiting context delegates to the inner microphone."""
        mock_microphone = mocker.Mock()
        mock_microphone.__exit__ = mocker.Mock(return_value=False)

        mocker.patch(
            'glitchygames.events.voice_backends.voice_portaudio.sr.Microphone',
            return_value=mock_microphone,
        )

        from glitchygames.events.voice_backends.voice_portaudio import PortAudioMicrophone

        mic = PortAudioMicrophone()
        result = mic.__exit__(None, None, None)

        mock_microphone.__exit__.assert_called_once_with(None, None, None)
        assert result is False

    def test_init_passes_args_to_inner(self, mocker):
        """Test that constructor arguments are passed to sr.Microphone."""
        mock_microphone_cls = mocker.patch(
            'glitchygames.events.voice_backends.voice_portaudio.sr.Microphone',
        )

        from glitchygames.events.voice_backends.voice_portaudio import PortAudioMicrophone

        PortAudioMicrophone(device_index=2, sample_rate=48000)
        mock_microphone_cls.assert_called_once_with(device_index=2, sample_rate=48000)
