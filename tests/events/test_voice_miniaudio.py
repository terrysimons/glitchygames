"""Tests for the miniaudio voice backend."""

import importlib.util
import threading

import pytest

miniaudio_available = importlib.util.find_spec('miniaudio') is not None
sr_available = importlib.util.find_spec('speech_recognition') is not None


class TestBlockingByteStream:
    """Tests for the _BlockingByteStream internal class."""

    @pytest.fixture
    def byte_stream(self):
        """Create a _BlockingByteStream instance.

        Returns:
            _BlockingByteStream: A fresh byte stream instance.

        """
        from glitchygames.events.voice_miniaudio import _BlockingByteStream

        return _BlockingByteStream()

    def test_initialization(self, byte_stream):
        """Test that stream initializes with empty state."""
        assert byte_stream._size == 0
        assert byte_stream._closed is False

    def test_write_and_read(self, byte_stream):
        """Test writing data and reading it back."""
        byte_stream.write(b'hello')
        result = byte_stream.read(5)
        assert result == b'hello'

    def test_write_empty_data_is_noop(self, byte_stream):
        """Test that writing empty bytes does nothing."""
        byte_stream.write(b'')
        assert byte_stream._size == 0

    def test_read_partial_chunk(self, byte_stream):
        """Test reading less data than available in a single chunk."""
        byte_stream.write(b'hello world')
        result = byte_stream.read(5)
        assert result == b'hello'
        # Remaining data should still be available
        result2 = byte_stream.read(6)
        assert result2 == b' world'

    def test_read_across_multiple_chunks(self, byte_stream):
        """Test reading data that spans multiple write chunks."""
        byte_stream.write(b'hel')
        byte_stream.write(b'lo')
        result = byte_stream.read(5)
        assert result == b'hello'

    def test_close_releases_waiting_readers(self, byte_stream):
        """Test that closing the stream unblocks pending reads."""
        results = []

        def reader():
            data = byte_stream.read(100)
            results.append(data)

        thread = threading.Thread(target=reader)
        thread.start()

        # Close the stream which should unblock the reader
        byte_stream.close()
        thread.join(timeout=2.0)

        assert not thread.is_alive()
        assert len(results) == 1
        assert results[0] == b''

    def test_write_multiple_reads(self, byte_stream):
        """Test multiple sequential reads after writes."""
        byte_stream.write(b'abcdef')
        assert byte_stream.read(2) == b'ab'
        assert byte_stream.read(2) == b'cd'
        assert byte_stream.read(2) == b'ef'

    def test_close_sets_closed_flag(self, byte_stream):
        """Test that close sets the _closed flag."""
        byte_stream.close()
        assert byte_stream._closed is True


@pytest.mark.skipif(not sr_available, reason='speech_recognition not installed')
class TestMiniaudioMicrophone:
    """Tests for the MiniaudioMicrophone class."""

    def test_init_without_miniaudio_raises(self):
        """Test that init raises RuntimeError when miniaudio is not available."""
        import glitchygames.events.voice_miniaudio as voice_mod
        from glitchygames.events.voice_miniaudio import MiniaudioMicrophone

        original_mi = voice_mod.mi
        voice_mod.mi = None
        try:
            with pytest.raises(RuntimeError, match='miniaudio is not installed'):
                MiniaudioMicrophone()
        finally:
            voice_mod.mi = original_mi

    @pytest.mark.skipif(not miniaudio_available, reason='miniaudio not installed')
    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        from glitchygames.events.voice_miniaudio import MiniaudioMicrophone

        mic = MiniaudioMicrophone()
        assert mic.SAMPLE_RATE == 16000
        assert mic.CHANNELS == 1
        assert mic.CHUNK == 1024
        assert mic.SAMPLE_WIDTH == 2
        assert mic.device_index is None
        assert mic.stream is None
        assert mic._device is None

    @pytest.mark.skipif(not miniaudio_available, reason='miniaudio not installed')
    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        from glitchygames.events.voice_miniaudio import MiniaudioMicrophone

        mic = MiniaudioMicrophone(
            device_index=1,
            sample_rate=44100,
            channels=2,
            chunk_size=2048,
            sample_width=4,
        )
        assert mic.device_index == 1
        assert mic.SAMPLE_RATE == 44100
        assert mic.CHANNELS == 2
        assert mic.CHUNK == 2048
        assert mic.SAMPLE_WIDTH == 4

    @pytest.mark.skipif(not miniaudio_available, reason='miniaudio not installed')
    def test_context_manager_enter_exit(self, mocker):
        """Test context manager creates and cleans up capture device."""
        from glitchygames.events.voice_miniaudio import MiniaudioMicrophone

        mock_device = mocker.Mock()
        mocker.patch(
            'glitchygames.events.voice_miniaudio.mi.CaptureDevice',
            return_value=mock_device,
        )

        mic = MiniaudioMicrophone()
        with mic as active_mic:
            assert active_mic is mic
            assert mic.stream is not None
            assert mic._device is mock_device
            mock_device.start.assert_called_once()

        mock_device.stop.assert_called_once()
        assert mic._device is None

    @pytest.mark.skipif(not miniaudio_available, reason='miniaudio not installed')
    def test_exit_handles_stop_exception(self, mocker):
        """Test that __exit__ cleans up even when device.stop() raises.

        The try/finally in __exit__ ensures stream.close() and device cleanup
        happen even if stop() raises, but the exception still propagates.
        """
        from glitchygames.events.voice_miniaudio import MiniaudioMicrophone

        mock_device = mocker.Mock()
        mock_device.stop.side_effect = RuntimeError('stop failed')
        mocker.patch(
            'glitchygames.events.voice_miniaudio.mi.CaptureDevice',
            return_value=mock_device,
        )

        mic = MiniaudioMicrophone()

        # The RuntimeError from stop() propagates through __exit__
        with pytest.raises(RuntimeError, match='stop failed'), mic:
            pass

        # Despite the exception, cleanup should have occurred
        assert mic._device is None
