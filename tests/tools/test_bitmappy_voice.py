"""Bitmappy's voice integration (split from tests/events/test_voice.py; they move with Bitmappy)."""

import logging
import threading

import pytest

from glitchygames.bitmappy.controllers.manager import MultiControllerManager
from glitchygames.bitmappy.editor import BitmapEditorScene
from glitchygames.bitmappy.editor_setup import EditorSetup
from glitchygames.events.voice import VoiceEventManager

TIMEOUT_2_SECONDS = 2

VOICE_COMMAND_PHRASES = (
    'clear the ai sprite box',
    'clear ai sprite box',
    'clear ai box',
    'clear the ai sprite',
    'clear ai sprite',
    'clear the ai sprite window',
    'clear ai sprite window',
)


@pytest.fixture
def editor_scene(mocker):
    """Create a real bitmappy editor scene (real canvas, real text boxes, the real display).

    Returns:
        BitmapEditorScene: The editor scene.

    """
    # A fresh controller manager for this editor (it is a singleton)
    mocker.patch.object(MultiControllerManager, '_instance', None)
    return BitmapEditorScene(options={})


def fake_speech_recognition(mocker, *, microphone_available: bool) -> None:
    """Fake the speech recognition library and the microphone (no real hardware is probed).

    The listen loop is replaced by one that waits for the stop signal, so a started manager runs
    a real listening thread that hears nothing.

    Args:
        mocker: The pytest-mock fixture.
        microphone_available: Whether the fake library finds a microphone.

    """
    mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=True)
    fake_speech_library = mocker.patch('glitchygames.events.voice.sr')
    if microphone_available:
        fake_speech_library.Microphone.return_value = object()
    else:
        fake_speech_library.Microphone.side_effect = OSError('No microphone')
    mocker.patch('glitchygames.events.voice.get_microphone_backend', return_value=None)

    def wait_for_stop(manager: VoiceEventManager) -> None:
        manager.stop_listening_event.wait(timeout=TIMEOUT_2_SECONDS)

    mocker.patch.object(VoiceEventManager, '_listen_loop', autospec=True, side_effect=wait_for_stop)


class TestBitmapEditorSceneVoiceIntegrationNegative:
    """Test voice recognition integration with BitmapEditorScene.

    Tests behavior when speech recognition is NOT available.
    """

    def test_voice_recognition_setup_without_speech_recognition(self, editor_scene, mocker):
        """Test that voice recognition setup fails gracefully without speech recognition."""
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)

        # Call the setup method via the delegate
        setup_delegate = EditorSetup(editor=editor_scene)
        setup_delegate.setup_voice_recognition()

        # Should handle missing speech recognition gracefully
        assert editor_scene.voice_manager is None

    def test_clear_ai_sprite_box_without_voice_recognition(self, editor_scene, caplog):
        """Test that clear AI sprite box works without voice recognition."""
        editor_scene.debug_text.text = 'A sprite description'

        with caplog.at_level(logging.INFO):
            # Call the clear command
            editor_scene.clear_ai_sprite_box()

        # Should work even without voice recognition
        assert not editor_scene.debug_text.text
        assert 'AI sprite box cleared via voice command' in caplog.messages

    def test_voice_recognition_cleanup_without_manager(self, editor_scene):
        """Test voice recognition cleanup when no manager exists."""
        assert getattr(editor_scene, 'voice_manager', None) is None

        # Call cleanup - should not raise exception
        editor_scene._cleanup_voice_recognition()

        assert getattr(editor_scene, 'voice_manager', None) is None


class TestBitmapEditorSceneVoiceIntegrationPositive:
    """Test voice recognition integration with BitmapEditorScene.

    Tests behavior when speech recognition IS available.
    """

    def test_voice_recognition_setup_with_mocked_dependencies(self, editor_scene, mocker):
        """Test that voice recognition setup works when speech recognition is available."""
        fake_speech_recognition(mocker, microphone_available=True)

        setup_delegate = EditorSetup(editor=editor_scene)
        setup_delegate.setup_voice_recognition()
        try:
            assert isinstance(editor_scene.voice_manager, VoiceEventManager)
            assert editor_scene.voice_manager.is_available()
            assert editor_scene.voice_manager.has_microphone()
        finally:
            editor_scene._cleanup_voice_recognition()

    def test_voice_recognition_setup_without_speech_recognition_expected(
        self, editor_scene, mocker
    ):
        """Test that voice recognition setup handles missing speech recognition gracefully.

        This test should pass when speech recognition is not available.
        """
        mocker.patch('glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE', new=False)

        # Call the setup method via the delegate
        setup_delegate = EditorSetup(editor=editor_scene)
        setup_delegate.setup_voice_recognition()

        # Should handle missing speech recognition gracefully
        assert editor_scene.voice_manager is None, (
            'Voice manager should be None when speech recognition is not available'
        )

    def test_voice_recognition_setup(self, editor_scene, mocker):
        """Setup registers every clear command, starts listening, and a command clears the box."""
        fake_speech_recognition(mocker, microphone_available=True)

        # Call the setup method via the delegate
        setup_delegate = EditorSetup(editor=editor_scene)
        setup_delegate.setup_voice_recognition()
        voice_manager = editor_scene.voice_manager
        try:
            # The manager logs to the editor's logger and listens on a real thread
            assert isinstance(voice_manager, VoiceEventManager)
            assert voice_manager.log is editor_scene.log
            assert voice_manager.is_listening
            assert voice_manager.listen_thread is not None
            assert voice_manager.listen_thread.is_alive()
            assert sorted(voice_manager.get_available_commands()) == sorted(VOICE_COMMAND_PHRASES)

            # Each command clears the editor's real AI sprite box
            for phrase in VOICE_COMMAND_PHRASES:
                editor_scene.debug_text.text = 'A sprite description'
                voice_manager._process_command(phrase)
                assert not editor_scene.debug_text.text
        finally:
            editor_scene._cleanup_voice_recognition()

    def test_voice_recognition_setup_no_microphone(self, editor_scene, mocker):
        """Test voice recognition setup when microphone is not available."""
        fake_speech_recognition(mocker, microphone_available=False)
        thread_count_before = threading.active_count()

        # Call the setup method via the delegate
        setup_delegate = EditorSetup(editor=editor_scene)
        setup_delegate.setup_voice_recognition()

        # The manager was dropped without registering commands or starting a listening thread
        assert editor_scene.voice_manager is None
        assert threading.active_count() == thread_count_before

    def test_clear_ai_sprite_box_command(self, editor_scene, caplog):
        """Test the clear AI sprite box voice command."""
        editor_scene.debug_text.text = 'A sprite description'

        with caplog.at_level(logging.INFO):
            # Call the clear command
            editor_scene.clear_ai_sprite_box()

        # Verify text was cleared
        assert not editor_scene.debug_text.text
        assert 'AI sprite box cleared via voice command' in caplog.messages

    def test_clear_ai_sprite_box_no_debug_text(self, editor_scene, caplog):
        """Test clear AI sprite box when debug_text is not available."""
        del editor_scene.debug_text

        # Call the clear command
        with caplog.at_level(logging.WARNING):
            editor_scene.clear_ai_sprite_box()

        # Verify warning was logged
        assert 'Cannot clear AI sprite box - debug_text not available' in caplog.messages

    def test_voice_recognition_cleanup(self, editor_scene, mocker):
        """Test voice recognition cleanup."""
        fake_speech_recognition(mocker, microphone_available=True)
        EditorSetup(editor=editor_scene).setup_voice_recognition()
        voice_manager = editor_scene.voice_manager
        assert voice_manager is not None
        listen_thread = voice_manager.listen_thread
        assert listen_thread is not None
        assert listen_thread.is_alive()

        # Call cleanup
        editor_scene._cleanup_voice_recognition()

        # The voice manager was stopped (its thread ended) before being set to None
        assert voice_manager.is_listening is False
        assert voice_manager.stop_listening_event.is_set()
        assert not listen_thread.is_alive()
        assert editor_scene.voice_manager is None

    def test_voice_recognition_cleanup_no_manager(self, editor_scene):
        """Test voice recognition cleanup when no manager exists."""
        editor_scene.voice_manager = None

        # Call cleanup - should not raise exception
        editor_scene._cleanup_voice_recognition()

        assert editor_scene.voice_manager is None
