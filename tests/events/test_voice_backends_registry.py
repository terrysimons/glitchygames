"""Tests for voice_backends registry module.

Verifies the get_microphone_backend factory function selects the correct
backend in various availability scenarios.
"""

import importlib
import sys
from types import ModuleType

import pytest

from glitchygames.events.voice_backends import get_microphone_backend
from glitchygames.events.voice_backends.registry import (
    get_microphone_backend as get_microphone_backend_direct,
)

# Module keys that we need to control during tests
_MINIAUDIO_KEY = 'glitchygames.events.voice_backends.voice_miniaudio'
_PORTAUDIO_KEY = 'glitchygames.events.voice_backends.voice_portaudio'
_REGISTRY_KEY = 'glitchygames.events.voice_backends.registry'


@pytest.fixture
def _clean_backend_modules():
    """Remove cached voice backend modules so each test starts fresh.

    Saves and restores any pre-existing entries after the test.
    Also reloads the registry module so imports inside the function
    pick up the faked sys.modules entries.
    """
    saved = {}
    for key in (_MINIAUDIO_KEY, _PORTAUDIO_KEY):
        if key in sys.modules:
            saved[key] = sys.modules.pop(key)
    yield
    # Restore originals (or remove fakes injected by the test)
    for key in (_MINIAUDIO_KEY, _PORTAUDIO_KEY):
        sys.modules.pop(key, None)
    for key, module in saved.items():
        sys.modules[key] = module
    # Reload registry so future calls use real modules
    if _REGISTRY_KEY in sys.modules:
        importlib.reload(sys.modules[_REGISTRY_KEY])


def _make_backend_module(class_name, mock_cls):
    """Create a fake module containing a single backend class.

    Args:
        class_name: Attribute name for the class (e.g. 'MiniaudioMicrophone').
        mock_cls: The mock class object to attach.

    Returns:
        ModuleType: A synthetic module with the class attribute set.

    """
    module = ModuleType(f'fake_{class_name}')
    setattr(module, class_name, mock_cls)
    return module


def _reload_and_call():
    """Reload the registry module and call get_microphone_backend.

    This ensures that relative imports inside the function resolve against
    the current sys.modules state, not cached imports from a prior call.

    Returns:
        type[object] | None: The selected microphone backend class, or None.

    """
    registry = importlib.reload(sys.modules[_REGISTRY_KEY])
    return registry.get_microphone_backend()


@pytest.mark.usefixtures('_clean_backend_modules')
class TestGetMicrophoneBackend:
    """Test the get_microphone_backend factory function."""

    def test_re_export_matches_direct_import(self):
        """Test that the re-export in __init__ matches the direct import."""
        assert get_microphone_backend is get_microphone_backend_direct

    def test_returns_none_when_both_backends_unavailable(self, mocker):
        """Test that None is returned when no backends are importable."""
        # Setting a module entry to None tells Python's import machinery
        # that the module does not exist, causing ImportError on import.
        sys.modules[_MINIAUDIO_KEY] = None
        sys.modules[_PORTAUDIO_KEY] = None

        result = _reload_and_call()
        assert result is None

    def test_prefers_miniaudio_when_available(self, mocker):
        """Test that miniaudio backend is preferred when probe succeeds."""
        mock_miniaudio_cls = mocker.Mock()
        mock_miniaudio_cls.return_value = mocker.Mock()  # Probe succeeds

        sys.modules[_MINIAUDIO_KEY] = _make_backend_module(
            'MiniaudioMicrophone', mock_miniaudio_cls
        )

        result = _reload_and_call()
        assert result is mock_miniaudio_cls

    def test_skips_miniaudio_on_oserror_tries_portaudio(self, mocker):
        """Test that OSError during miniaudio probe leads to portaudio attempt."""
        mock_miniaudio_cls = mocker.Mock(side_effect=OSError('No device'))
        mock_portaudio_cls = mocker.Mock()
        mock_portaudio_cls.return_value = mocker.Mock()  # Probe succeeds

        sys.modules[_MINIAUDIO_KEY] = _make_backend_module(
            'MiniaudioMicrophone', mock_miniaudio_cls
        )
        sys.modules[_PORTAUDIO_KEY] = _make_backend_module(
            'PortAudioMicrophone', mock_portaudio_cls
        )

        result = _reload_and_call()
        assert result is mock_portaudio_cls

    def test_skips_miniaudio_on_runtime_error_tries_portaudio(self, mocker):
        """Test that RuntimeError during miniaudio probe falls through to portaudio."""
        mock_miniaudio_cls = mocker.Mock(side_effect=RuntimeError('Init failed'))
        mock_portaudio_cls = mocker.Mock()
        mock_portaudio_cls.return_value = mocker.Mock()

        sys.modules[_MINIAUDIO_KEY] = _make_backend_module(
            'MiniaudioMicrophone', mock_miniaudio_cls
        )
        sys.modules[_PORTAUDIO_KEY] = _make_backend_module(
            'PortAudioMicrophone', mock_portaudio_cls
        )

        result = _reload_and_call()
        assert result is mock_portaudio_cls

    def test_skips_miniaudio_import_error_tries_portaudio(self, mocker):
        """Test that ImportError for miniaudio falls through to portaudio."""
        mock_portaudio_cls = mocker.Mock()
        mock_portaudio_cls.return_value = mocker.Mock()

        # Do NOT put miniaudio in sys.modules -> ImportError
        sys.modules[_MINIAUDIO_KEY] = None  # Force ImportError
        sys.modules[_PORTAUDIO_KEY] = _make_backend_module(
            'PortAudioMicrophone', mock_portaudio_cls
        )

        result = _reload_and_call()
        assert result is mock_portaudio_cls

    def test_portaudio_probe_oserror_returns_none(self, mocker):
        """Test that portaudio probe OSError returns None."""
        mock_portaudio_cls = mocker.Mock(side_effect=OSError('No device'))

        sys.modules[_MINIAUDIO_KEY] = None  # Force ImportError
        sys.modules[_PORTAUDIO_KEY] = _make_backend_module(
            'PortAudioMicrophone', mock_portaudio_cls
        )

        result = _reload_and_call()
        assert result is None

    def test_portaudio_probe_runtime_error_returns_none(self, mocker):
        """Test that portaudio probe RuntimeError returns None."""
        mock_portaudio_cls = mocker.Mock(side_effect=RuntimeError('No device'))

        sys.modules[_MINIAUDIO_KEY] = None  # Force ImportError
        sys.modules[_PORTAUDIO_KEY] = _make_backend_module(
            'PortAudioMicrophone', mock_portaudio_cls
        )

        result = _reload_and_call()
        assert result is None

    def test_both_probes_fail_returns_none(self, mocker):
        """Test that None is returned when both backends probe-fail."""
        mock_miniaudio_cls = mocker.Mock(side_effect=RuntimeError('No device'))
        mock_portaudio_cls = mocker.Mock(side_effect=OSError('No device'))

        sys.modules[_MINIAUDIO_KEY] = _make_backend_module(
            'MiniaudioMicrophone', mock_miniaudio_cls
        )
        sys.modules[_PORTAUDIO_KEY] = _make_backend_module(
            'PortAudioMicrophone', mock_portaudio_cls
        )

        result = _reload_and_call()
        assert result is None
