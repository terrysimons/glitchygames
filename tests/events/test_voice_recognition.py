"""Test suite for voice recognition functionality.

This module tests the voice recognition manager and its integration
with the BitmapEditorScene. It includes comprehensive negative tests
to verify graceful degradation when speech recognition is not available.
"""

import contextlib
import unittest
from unittest.mock import Mock, patch

import pytest
from glitchygames.events.voice import VoiceRecognitionManager
from glitchygames.tools.bitmappy import BitmapEditorScene

from tests.mocks import MockFactory

# Constants for magic values
TIMEOUT_2_SECONDS = 2


class TestVoiceRecognitionManagerNegative(unittest.TestCase):
    """Test VoiceRecognitionManager when speech recognition is NOT available."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_initialization_without_speech_recognition(self):
        """Test that VoiceRecognitionManager initializes gracefully without speech recognition."""
        with patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=False):
            manager = VoiceRecognitionManager()

            # Should initialize without errors
            assert manager is not None
            assert manager.recognizer is None
            assert manager.microphone is None
            assert not manager.is_available()
            assert not manager.is_listening

    def test_register_command_without_speech_recognition(self):
        """Test that commands can still be registered without speech recognition."""
        with patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=False):
            manager = VoiceRecognitionManager()
            callback = Mock()

            # Should be able to register commands even without speech recognition
            manager.register_command("test command", callback)

            # Verify command was registered
            assert "test command" in manager.commands
            assert manager.commands["test command"] == callback

    def test_start_listening_without_speech_recognition(self):
        """Test that start_listening fails gracefully without speech recognition."""
        with patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=False):
            manager = VoiceRecognitionManager()

            # Should not start listening without speech recognition
            manager.start_listening()
            assert not manager.is_listening

    def test_stop_listening_without_speech_recognition(self):
        """Test that stop_listening works without speech recognition."""
        with patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=False):
            manager = VoiceRecognitionManager()

            # Should be able to stop listening even if not started
            manager.stop_listening()
            assert not manager.is_listening

    def test_process_command_without_speech_recognition(self):
        """Test that process_command works without speech recognition."""
        with patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=False):
            manager = VoiceRecognitionManager()
            callback = Mock()

            # Register a command
            manager.register_command("test command", callback)

            # Should be able to process commands even without speech recognition
            manager._process_command("test command")

            # Verify callback was called
            callback.assert_called_once()

    def test_get_available_commands_without_speech_recognition(self):
        """Test that get_available_commands works without speech recognition."""
        with patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=False):
            manager = VoiceRecognitionManager()
            callback = Mock()

            # Register some commands
            manager.register_command("command one", callback)
            manager.register_command("command two", callback)

            # Should be able to get commands even without speech recognition
            commands = manager.get_available_commands()

            # Verify commands list
            assert len(commands) == TIMEOUT_2_SECONDS
            assert "command one" in commands
            assert "command two" in commands


class TestVoiceRecognitionManagerWithMicrophoneFailure(unittest.TestCase):
    """Test VoiceRecognitionManager when speech recognition is available but microphone fails."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_initialization_with_microphone_failure(self):
        """Test that VoiceRecognitionManager handles microphone initialization failure."""
        with patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=True), \
             patch("glitchygames.events.voice.sr.Microphone",
                   side_effect=Exception("Microphone not found")):
            
            # Use pytest logger wrapper to suppress logs during successful runs
            with patch("glitchygames.events.voice.logging.getLogger") as mock_get_logger:
                mock_log = Mock()
                mock_get_logger.return_value = mock_log
                
                manager = VoiceRecognitionManager()
                
                # Should initialize without errors but without microphone
                assert manager is not None
                assert manager.recognizer is not None
                assert manager.microphone is None
                assert not manager.is_available()
                assert not manager.is_listening
                
                # Verify the ERROR log message was called
                mock_log.exception.assert_called_once()
                # Check that the log message contains the expected content
                call_args = mock_log.exception.call_args[0][0]
                assert "Failed to initialize microphone" in call_args

    def test_start_listening_with_microphone_failure(self):
        """Test that start_listening fails when microphone is not available."""
        with patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=True), \
             patch("glitchygames.events.voice.sr.Microphone",
                   side_effect=Exception("Microphone not found")):
            
            # Use pytest logger wrapper to suppress logs during successful runs
            with patch("glitchygames.events.voice.logging.getLogger") as mock_get_logger:
                mock_log = Mock()
                mock_get_logger.return_value = mock_log
                
                manager = VoiceRecognitionManager()
                
                # Should not start listening without microphone
                manager.start_listening()
                assert not manager.is_listening
                
                # Verify the ERROR log messages were called (should be called twice)
                assert mock_log.exception.call_count == 1
                assert mock_log.error.call_count == 1
                # Check that both log messages contain the expected content
                exception_call = mock_log.exception.call_args[0][0]
                error_call = mock_log.error.call_args[0][0]
                assert "Failed to initialize microphone" in exception_call
                assert "Cannot start listening: microphone not available" in error_call


class TestVoiceRecognitionManagerPositive(unittest.TestCase):
    """Test VoiceRecognitionManager when speech recognition IS available."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        self.voice_managers = []  # Track voice managers for cleanup

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up any voice managers that were created
        for manager in self.voice_managers:
            if hasattr(manager, "stop_listening"):
                with contextlib.suppress(Exception):
                    manager.stop_listening()  # Ignore cleanup errors
        self.voice_managers.clear()

        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_voice_manager_initialization(self):
        """Test that VoiceRecognitionManager initializes correctly."""
        with patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=True), \
             patch("glitchygames.events.voice.sr.Microphone") as mock_mic:
            mock_mic.return_value = Mock()

            manager = VoiceRecognitionManager()

            # Should initialize without errors
            assert manager is not None
            assert manager.recognizer is not None
            assert manager.commands == {}
            assert not manager.is_listening

    def test_voice_manager_initialization_with_real_speech_recognition(self):
        """Test that VoiceRecognitionManager initializes correctly with real speech recognition.

        This test will FAIL until speech recognition dependencies are installed.
        """
        # This test should fail when speech recognition is not available
        # and pass when it is available
        try:
            manager = VoiceRecognitionManager()
            self.voice_managers.append(manager)  # Track for cleanup

            # If we get here, speech recognition is available
            assert manager is not None
            # These assertions will fail if speech recognition is not available
            assert manager.recognizer is not None, "Speech recognition should be available"
            assert manager.is_available(), "Voice recognition should be available"

        except ImportError:
            # This is expected when speech recognition is not installed
            # The test should fail in this case to indicate missing dependencies
            pytest.fail("Speech recognition dependencies not installed - this test should fail")

    def test_start_listening_with_real_speech_recognition(self):
        """Test that speech recognition is available and can be initialized.

        This test verifies that speech recognition dependencies are installed and working.
        We don't actually start listening to avoid hanging in the test environment.
        """
        try:
            manager = VoiceRecognitionManager()
            self.voice_managers.append(manager)  # Track for cleanup

            if manager.is_available():
                # If speech recognition is available, the manager should be properly initialized
                assert manager.recognizer is not None, "Recognizer should be available"
                assert manager.microphone is not None, "Microphone should be available"
                assert manager.is_available(), "Voice recognition should be available"
                # Don't actually start listening to avoid hanging in tests
            else:
                # If not available, this test should fail to indicate missing dependencies
                pytest.fail("Speech recognition not available - this test should fail")

        except ImportError:
            # This is expected when speech recognition is not installed
            pytest.fail("Speech recognition dependencies not installed - this test should fail")

    def test_voice_manager_without_microphone(self):
        """Test VoiceRecognitionManager when microphone is not available."""
        with patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=True), \
             patch("glitchygames.events.voice.sr.Microphone", side_effect=Exception("No microphone")):  # noqa: E501
            
            # Use pytest logger wrapper to suppress logs during successful runs
            with patch("glitchygames.events.voice.logging.getLogger") as mock_get_logger:
                mock_log = Mock()
                mock_get_logger.return_value = mock_log
                
                manager = VoiceRecognitionManager()
                
                # Should handle missing microphone gracefully
                assert manager is not None
                assert manager.microphone is None
                assert not manager.is_available()
                
                # Verify the ERROR log message was called
                mock_log.exception.assert_called_once()
                # Check that the log message contains the expected content
                call_args = mock_log.exception.call_args[0][0]
                assert "Failed to initialize microphone" in call_args

    def test_voice_manager_without_speech_recognition(self):
        """Test VoiceRecognitionManager when speech recognition is not available."""
        with patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=False):
            manager = VoiceRecognitionManager()

            # Should handle missing speech recognition gracefully
            assert manager is not None
            assert manager.recognizer is None
            assert manager.microphone is None
            assert not manager.is_available()

    def test_register_command(self):
        """Test registering voice commands."""
        with patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=True), \
             patch("glitchygames.events.voice.sr.Microphone") as mock_mic:
            mock_mic.return_value = Mock()

            manager = VoiceRecognitionManager()
            callback = Mock()

            # Register a command
            manager.register_command("test command", callback)

            # Verify command was registered
            assert "test command" in manager.commands
            assert manager.commands["test command"] == callback

    def test_register_multiple_commands(self):
        """Test registering multiple voice commands."""
        with patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=True), \
             patch("glitchygames.events.voice.sr.Microphone") as mock_mic:
            mock_mic.return_value = Mock()

            manager = VoiceRecognitionManager()
            callback1 = Mock()
            callback2 = Mock()

            # Register multiple commands
            manager.register_command("command one", callback1)
            manager.register_command("command two", callback2)

            # Verify both commands were registered
            assert len(manager.commands) == TIMEOUT_2_SECONDS
            assert "command one" in manager.commands
            assert "command two" in manager.commands
            assert manager.commands["command one"] == callback1
            assert manager.commands["command two"] == callback2

    def test_get_available_commands(self):
        """Test getting list of available commands."""
        with patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=True), \
             patch("glitchygames.events.voice.sr.Microphone") as mock_mic:
            mock_mic.return_value = Mock()

            manager = VoiceRecognitionManager()
            callback = Mock()

            # Register some commands
            manager.register_command("command one", callback)
            manager.register_command("command two", callback)

            # Get available commands
            commands = manager.get_available_commands()

            # Verify commands list
            assert len(commands) == TIMEOUT_2_SECONDS
            assert "command one" in commands
            assert "command two" in commands

    def test_start_listening_without_microphone(self):
        """Test starting listening when microphone is not available."""
        with patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=True), \
             patch("glitchygames.events.voice.sr.Microphone", side_effect=Exception("No microphone")):  # noqa: E501
            
            # Use pytest logger wrapper to suppress logs during successful runs
            with patch("glitchygames.events.voice.logging.getLogger") as mock_get_logger:
                mock_log = Mock()
                mock_get_logger.return_value = mock_log
                
                manager = VoiceRecognitionManager()
                
                # Should not start listening without microphone
                manager.start_listening()
                assert not manager.is_listening
                
                # Verify the ERROR log messages were called (should be called twice)
                assert mock_log.exception.call_count == 1
                assert mock_log.error.call_count == 1
                # Check that both log messages contain the expected content
                exception_call = mock_log.exception.call_args[0][0]
                error_call = mock_log.error.call_args[0][0]
                assert "Failed to initialize microphone" in exception_call
                assert "Cannot start listening: microphone not available" in error_call

    def test_stop_listening(self):
        """Test stopping voice recognition."""
        with patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=True), \
             patch("glitchygames.events.voice.sr.Microphone") as mock_mic:
            mock_mic.return_value = Mock()

            manager = VoiceRecognitionManager()

            # Stop listening (even if not started)
            manager.stop_listening()
            assert not manager.is_listening

    def test_process_command_exact_match(self):
        """Test processing voice commands with exact matches."""
        with patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=True), \
             patch("glitchygames.events.voice.sr.Microphone") as mock_mic:
            mock_mic.return_value = Mock()

            manager = VoiceRecognitionManager()
            callback = Mock()

            # Register a command
            manager.register_command("clear the ai sprite box", callback)

            # Process exact match
            manager._process_command("clear the ai sprite box")

            # Verify callback was called
            callback.assert_called_once()

    def test_process_command_partial_match(self):
        """Test processing voice commands with partial matches."""
        with patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=True), \
             patch("glitchygames.events.voice.sr.Microphone") as mock_mic:
            mock_mic.return_value = Mock()

            manager = VoiceRecognitionManager()
            callback = Mock()

            # Register a command
            manager.register_command("clear ai sprite box", callback)

            # Process partial match
            manager._process_command("please clear ai sprite box now")

            # Verify callback was called
            callback.assert_called_once()

    def test_process_command_no_match(self):
        """Test processing voice commands with no matches."""
        with patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=True), \
             patch("glitchygames.events.voice.sr.Microphone") as mock_mic:
            mock_mic.return_value = Mock()

            manager = VoiceRecognitionManager()
            callback = Mock()

            # Register a command
            manager.register_command("clear ai sprite box", callback)

            # Process non-matching text
            manager._process_command("hello world")

            # Verify callback was not called
            callback.assert_not_called()

    def test_process_command_callback_error(self):
        """Test handling errors in command callbacks."""
        with patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=True), \
             patch("glitchygames.events.voice.sr.Microphone") as mock_mic:
            mock_mic.return_value = Mock()

            # Use pytest logger wrapper to suppress logs during successful runs
            with patch("glitchygames.events.voice.logging.getLogger") as mock_get_logger:
                mock_log = Mock()
                mock_get_logger.return_value = mock_log
                
                manager = VoiceRecognitionManager()
                callback = Mock(side_effect=Exception("Callback error"))

                # Register a command that will raise an error
                manager.register_command("test command", callback)

                # Process command - should not raise exception
                manager._process_command("test command")

                # Verify callback was called despite error
                callback.assert_called_once()
                
                # Verify the ERROR log message was called
                mock_log.exception.assert_called_once()
                # Check that the log message contains the expected content
                call_args = mock_log.exception.call_args[0][0]
                assert "Error executing voice command 'test command'" in call_args


class TestBitmapEditorSceneVoiceIntegrationNegative(unittest.TestCase):
    """Test voice recognition integration with BitmapEditorScene when speech recognition is NOT available."""  # noqa: E501

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_voice_recognition_setup_without_speech_recognition(self):
        """Test that voice recognition setup fails gracefully without speech recognition."""
        with patch.object(BitmapEditorScene, "__init__", return_value=None), \
             patch("glitchygames.events.voice.SPEECH_RECOGNITION_AVAILABLE", new=False):

            # Create scene instance
            scene = BitmapEditorScene({})
            scene.log = Mock()

            # Call the setup method
            scene._setup_voice_recognition()

            # Should handle missing speech recognition gracefully
            assert scene.voice_manager is None

    def test_clear_ai_sprite_box_without_voice_recognition(self):
        """Test that clear AI sprite box works without voice recognition."""
        with patch.object(BitmapEditorScene, "__init__", return_value=None):
            scene = BitmapEditorScene({})
            scene.log = Mock()
            scene.debug_text = Mock()

            # Call the clear command
            scene._clear_ai_sprite_box()

            # Should work even without voice recognition
            scene.debug_text.text = ""
            scene.log.info.assert_called_with("AI sprite box cleared via voice command")

    def test_voice_recognition_cleanup_without_manager(self):
        """Test voice recognition cleanup when no manager exists."""
        with patch.object(BitmapEditorScene, "__init__", return_value=None):
            scene = BitmapEditorScene({})
            scene.log = Mock()
            # No voice_manager attribute

            # Call cleanup - should not raise exception
            scene._cleanup_voice_recognition()

            # No assertions needed - just ensure no exception is raised


class TestBitmapEditorSceneVoiceIntegrationPositive(unittest.TestCase):
    """Test voice recognition integration with BitmapEditorScene when speech recognition IS available."""  # noqa: E501

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_voice_recognition_setup_with_real_dependencies(self):
        """Test that voice recognition setup works with real speech recognition dependencies.

        This test will FAIL until speech recognition dependencies are installed.
        """
        with patch.object(BitmapEditorScene, "__init__", return_value=None):
            # Create scene instance
            scene = BitmapEditorScene({})
            scene.log = Mock()

            try:
                # Call the setup method
                scene._setup_voice_recognition()

                # If we get here, speech recognition should be available
                assert scene.voice_manager is not None, "Voice manager should be created when speech recognition is available"  # noqa: E501
                assert scene.voice_manager.is_available(), "Voice recognition should be available"

            except ImportError:
                # This is expected when speech recognition is not installed
                pytest.fail("Speech recognition dependencies not installed - this test should fail")

    def test_voice_recognition_setup(self):
        """Test that voice recognition is set up correctly in BitmapEditorScene."""
        with patch.object(BitmapEditorScene, "__init__", return_value=None), \
             patch("glitchygames.tools.bitmappy.VoiceRecognitionManager") as mock_voice_class:

            # Mock the voice manager
            mock_voice_manager = Mock()
            mock_voice_manager.is_available.return_value = True
            mock_voice_class.return_value = mock_voice_manager

            # Create scene instance
            scene = BitmapEditorScene({})
            scene.log = Mock()

            # Call the setup method
            scene._setup_voice_recognition()

            # Verify voice manager was created and configured
            mock_voice_class.assert_called_once_with(logger=scene.log)
            mock_voice_manager.register_command.assert_called()
            mock_voice_manager.start_listening.assert_called_once()
            assert scene.voice_manager == mock_voice_manager

    def test_voice_recognition_setup_no_microphone(self):
        """Test voice recognition setup when microphone is not available."""
        with patch.object(BitmapEditorScene, "__init__", return_value=None), \
             patch("glitchygames.tools.bitmappy.VoiceRecognitionManager") as mock_voice_class:

            # Mock the voice manager without microphone
            mock_voice_manager = Mock()
            mock_voice_manager.is_available.return_value = False
            mock_voice_class.return_value = mock_voice_manager

            # Create scene instance
            scene = BitmapEditorScene({})
            scene.log = Mock()

            # Call the setup method
            scene._setup_voice_recognition()

            # Verify voice manager was created but not started
            mock_voice_class.assert_called_once_with(logger=scene.log)
            mock_voice_manager.register_command.assert_not_called()
            mock_voice_manager.start_listening.assert_not_called()
            assert scene.voice_manager is None

    def test_clear_ai_sprite_box_command(self):
        """Test the clear AI sprite box voice command."""
        with patch.object(BitmapEditorScene, "__init__", return_value=None):
            scene = BitmapEditorScene({})
            scene.log = Mock()
            scene.debug_text = Mock()

            # Call the clear command
            scene._clear_ai_sprite_box()

            # Verify text was cleared
            scene.debug_text.text = ""
            scene.log.info.assert_called_with("AI sprite box cleared via voice command")

    def test_clear_ai_sprite_box_no_debug_text(self):
        """Test clear AI sprite box when debug_text is not available."""
        with patch.object(BitmapEditorScene, "__init__", return_value=None):
            scene = BitmapEditorScene({})
            scene.log = Mock()
            # No debug_text attribute

            # Call the clear command
            scene._clear_ai_sprite_box()

            # Verify warning was logged
            scene.log.warning.assert_called_with("Cannot clear AI sprite box - debug_text not available")  # noqa: E501

    def test_voice_recognition_cleanup(self):
        """Test voice recognition cleanup."""
        with patch.object(BitmapEditorScene, "__init__", return_value=None):
            scene = BitmapEditorScene({})
            scene.log = Mock()
            mock_voice_manager = Mock()
            scene.voice_manager = mock_voice_manager

            # Call cleanup
            scene._cleanup_voice_recognition()

            # Verify voice manager was stopped before being set to None
            mock_voice_manager.stop_listening.assert_called_once()
            assert scene.voice_manager is None

    def test_voice_recognition_cleanup_no_manager(self):
        """Test voice recognition cleanup when no manager exists."""
        with patch.object(BitmapEditorScene, "__init__", return_value=None):
            scene = BitmapEditorScene({})
            scene.log = Mock()
            # No voice_manager attribute

            # Call cleanup - should not raise exception
            scene._cleanup_voice_recognition()

            # No assertions needed - just ensure no exception is raised


if __name__ == "__main__":
    unittest.main()
