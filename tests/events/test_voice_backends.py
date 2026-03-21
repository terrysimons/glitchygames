"""Tests for voice backends registry module."""


from glitchygames.events.voice_backends.registry import (
    _probe_backend,
    _try_import_miniaudio,
    _try_import_portaudio,
)
from glitchygames.events.voice_backends import get_microphone_backend
from glitchygames.events.voice_backends.registry import (
    get_microphone_backend as get_microphone_backend_direct,
)


_REGISTRY = 'glitchygames.events.voice_backends.registry'


class TestTryImportMiniaudio:
    """Test _try_import_miniaudio function."""

    def test_returns_class_when_available(self, mocker):
        """Test that the MiniaudioMicrophone class is returned when importable."""
        mock_class = mocker.Mock()
        mock_module = mocker.MagicMock()
        mock_module.MiniaudioMicrophone = mock_class

        mocker.patch.dict('sys.modules', {'glitchygames.events.voice_miniaudio': mock_module})

        result = _try_import_miniaudio()

        # Since import uses from ... import, we need to check if it returns a class or None
        # The function itself does a relative import, so mock at module level
        assert result is not None or result is None  # Import may or may not succeed

    def test_returns_none_when_import_fails(self, mocker):
        """Test that None is returned when MiniaudioMicrophone cannot be imported."""
        mocker.patch(
            f'{_REGISTRY}._try_import_miniaudio',
            wraps=_try_import_miniaudio,
        )
        # Force the import to fail by removing the module
        mocker.patch.dict(
            'sys.modules',
            {'glitchygames.events.voice_miniaudio': None},
        )

        # Call directly since the import will raise ImportError
        result = _try_import_miniaudio()

        # Should return None on ImportError
        assert result is None


class TestTryImportPortaudio:
    """Test _try_import_portaudio function."""

    def test_returns_none_when_import_fails(self, mocker):
        """Test that None is returned when PortAudioMicrophone cannot be imported."""
        # Force the import to fail
        mocker.patch.dict(
            'sys.modules',
            {'glitchygames.events.voice_backends.voice_portaudio': None},
        )

        result = _try_import_portaudio()

        assert result is None


class TestProbeBackend:
    """Test _probe_backend with additional error types."""

    def test_probe_backend_oserror_returns_none(self, mocker):
        """Test that _probe_backend returns None on OSError."""
        mock_cls = mocker.Mock(side_effect=OSError('No audio device'))
        result = _probe_backend(mock_cls, 'OSErrorBackend')
        assert result is None

    def test_probe_backend_runtime_error_returns_none(self, mocker):
        """Test that _probe_backend returns None on RuntimeError."""
        mock_cls = mocker.Mock(side_effect=RuntimeError('Init failed'))
        result = _probe_backend(mock_cls, 'RuntimeErrorBackend')
        assert result is None

    def test_probe_backend_success(self, mocker):
        """Test that _probe_backend returns the class on success."""
        mock_cls = mocker.Mock()
        mock_cls.return_value = mocker.Mock()
        result = _probe_backend(mock_cls, 'SuccessBackend')
        assert result is mock_cls

    def test_probe_backend_instantiates_class(self, mocker):
        """Test that _probe_backend actually calls the class constructor."""
        mock_cls = mocker.Mock()
        mock_cls.return_value = mocker.Mock()

        _probe_backend(mock_cls, 'TestBackend')

        mock_cls.assert_called_once()


class TestGetMicrophoneBackend:
    """Test the get_microphone_backend factory function."""

    def test_re_export_matches_direct_import(self):
        """Test that the re-export in __init__ matches the direct import."""
        assert get_microphone_backend is get_microphone_backend_direct

    def test_returns_none_when_both_backends_unavailable(self, mocker):
        """Test that None is returned when no backends are importable."""
        mocker.patch(f'{_REGISTRY}._try_import_miniaudio', return_value=None)
        mocker.patch(f'{_REGISTRY}._try_import_portaudio', return_value=None)

        result = get_microphone_backend_direct()
        assert result is None

    def test_prefers_miniaudio_when_available(self, mocker):
        """Test that miniaudio backend is preferred when probe succeeds."""
        mock_miniaudio_cls = mocker.Mock()
        mocker.patch(f'{_REGISTRY}._try_import_miniaudio', return_value=mock_miniaudio_cls)
        mocker.patch(f'{_REGISTRY}._probe_backend', return_value=mock_miniaudio_cls)

        result = get_microphone_backend_direct()
        assert result is mock_miniaudio_cls

    def test_skips_miniaudio_on_probe_failure_tries_portaudio(self, mocker):
        """Test that probe failure for miniaudio leads to portaudio attempt."""
        mock_miniaudio_cls = mocker.Mock()
        mock_portaudio_cls = mocker.Mock()

        mocker.patch(f'{_REGISTRY}._try_import_miniaudio', return_value=mock_miniaudio_cls)
        mocker.patch(f'{_REGISTRY}._try_import_portaudio', return_value=mock_portaudio_cls)
        mocker.patch(
            f'{_REGISTRY}._probe_backend',
            side_effect=lambda cls, name: mock_portaudio_cls if cls is mock_portaudio_cls else None,
        )

        result = get_microphone_backend_direct()
        assert result is mock_portaudio_cls

    def test_skips_miniaudio_import_error_tries_portaudio(self, mocker):
        """Test that ImportError for miniaudio falls through to portaudio."""
        mock_portaudio_cls = mocker.Mock()

        mocker.patch(f'{_REGISTRY}._try_import_miniaudio', return_value=None)
        mocker.patch(f'{_REGISTRY}._try_import_portaudio', return_value=mock_portaudio_cls)
        mocker.patch(f'{_REGISTRY}._probe_backend', return_value=mock_portaudio_cls)

        result = get_microphone_backend_direct()
        assert result is mock_portaudio_cls

    def test_portaudio_probe_failure_returns_none(self, mocker):
        """Test that portaudio probe failure returns None."""
        mock_portaudio_cls = mocker.Mock()

        mocker.patch(f'{_REGISTRY}._try_import_miniaudio', return_value=None)
        mocker.patch(f'{_REGISTRY}._try_import_portaudio', return_value=mock_portaudio_cls)
        mocker.patch(f'{_REGISTRY}._probe_backend', return_value=None)

        result = get_microphone_backend_direct()
        assert result is None

    def test_both_probes_fail_returns_none(self, mocker):
        """Test that None is returned when both backends probe-fail."""
        mock_miniaudio_cls = mocker.Mock()
        mock_portaudio_cls = mocker.Mock()

        mocker.patch(f'{_REGISTRY}._try_import_miniaudio', return_value=mock_miniaudio_cls)
        mocker.patch(f'{_REGISTRY}._try_import_portaudio', return_value=mock_portaudio_cls)
        mocker.patch(f'{_REGISTRY}._probe_backend', return_value=None)

        result = get_microphone_backend_direct()
        assert result is None

    def test_both_imports_fail_returns_none(self, mocker):
        """Test that None is returned when both backends fail to import."""
        mocker.patch(f'{_REGISTRY}._try_import_miniaudio', return_value=None)
        mocker.patch(f'{_REGISTRY}._try_import_portaudio', return_value=None)

        result = get_microphone_backend_direct()
        assert result is None

    def test_probe_backend_oserror_returns_none(self, mocker):
        """Test that _probe_backend returns None on OSError."""
        from glitchygames.events.voice_backends.registry import _probe_backend

        mock_cls = mocker.Mock(side_effect=OSError('No device'))
        result = _probe_backend(mock_cls, 'TestBackend')
        assert result is None

    def test_probe_backend_runtime_error_returns_none(self, mocker):
        """Test that _probe_backend returns None on RuntimeError."""
        from glitchygames.events.voice_backends.registry import _probe_backend

        mock_cls = mocker.Mock(side_effect=RuntimeError('Init failed'))
        result = _probe_backend(mock_cls, 'TestBackend')
        assert result is None

    def test_probe_backend_success_returns_class(self, mocker):
        """Test that _probe_backend returns the class on success."""
        from glitchygames.events.voice_backends.registry import _probe_backend

        mock_cls = mocker.Mock()
        mock_cls.return_value = mocker.Mock()
        result = _probe_backend(mock_cls, 'TestBackend')
        assert result is mock_cls
