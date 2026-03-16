"""Tests for voice_backends registry module.

Verifies the get_microphone_backend factory function selects the correct
backend in various availability scenarios.
"""

from glitchygames.events.voice_backends import get_microphone_backend
from glitchygames.events.voice_backends.registry import (
    get_microphone_backend as get_microphone_backend_direct,
)

_REGISTRY = 'glitchygames.events.voice_backends.registry'


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
