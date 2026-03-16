"""Tests for Scene lifecycle and state transition behaviors.

Focuses on verifying pause, resume, game_over, on_text_submit_event,
on_video_expose_event, on_video_resize_event, and on_sys_wm_event.
"""

from glitchygames.scenes import Scene


class TestScenePause:
    """Test Scene.pause() behavior."""

    def test_pause_creates_and_switches_to_pause_scene(self, mock_pygame_patches, mocker):
        """Test that pause() creates a PauseScene and switches to it."""
        scene = Scene()
        mock_switch = mocker.patch.object(scene.scene_manager, 'switch_to_scene')

        scene.pause()

        mock_switch.assert_called_once()
        # Verify the argument is a PauseScene instance
        from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene

        switched_scene = mock_switch.call_args[0][0]
        assert isinstance(switched_scene, PauseScene)

    def test_pause_passes_options_to_pause_scene(self, mock_pygame_patches, mocker):
        """Test that pause() passes the current scene's options to PauseScene."""
        scene = Scene()
        mock_switch = mocker.patch.object(scene.scene_manager, 'switch_to_scene')

        scene.pause()

        mock_switch.assert_called_once()
        switched_scene = mock_switch.call_args[0][0]
        # PauseScene should have received the scene's options
        assert switched_scene.options == scene.options


class TestSceneResume:
    """Test Scene.resume() behavior."""

    def test_resume_switches_to_previous_scene(self, mock_pygame_patches, mocker):
        """Test that resume() switches to the previous scene."""
        scene = Scene()
        previous_scene = Scene()
        scene.scene_manager.previous_scene = previous_scene
        mock_switch = mocker.patch.object(scene.scene_manager, 'switch_to_scene')

        scene.resume()

        mock_switch.assert_called_once_with(previous_scene)

    def test_resume_with_no_previous_scene_does_not_switch(self, mock_pygame_patches, mocker):
        """Test that resume() does nothing when no previous scene exists."""
        scene = Scene()
        scene.scene_manager.previous_scene = None
        mock_switch = mocker.patch.object(scene.scene_manager, 'switch_to_scene')

        scene.resume()

        mock_switch.assert_not_called()

    def test_resume_logs_warning_when_no_previous_scene(self, mock_pygame_patches, mocker):
        """Test that resume() logs a warning when no previous scene exists."""
        scene = Scene()
        scene.scene_manager.previous_scene = None
        mocker.patch.object(scene.scene_manager, 'switch_to_scene')

        mock_warning = mocker.patch.object(scene.log, 'warning')

        scene.resume()

        mock_warning.assert_called_once_with('No previous scene found to resume')


class TestSceneGameOver:
    """Test Scene.game_over() behavior."""

    def test_game_over_creates_and_switches_to_game_over_scene(self, mock_pygame_patches, mocker):
        """Test that game_over() creates a GameOverScene and switches to it."""
        scene = Scene()
        mock_switch = mocker.patch.object(scene.scene_manager, 'switch_to_scene')

        scene.game_over()

        mock_switch.assert_called_once()
        from glitchygames.scenes.builtin_scenes.game_over_scene import GameOverScene

        switched_scene = mock_switch.call_args[0][0]
        assert isinstance(switched_scene, GameOverScene)

    def test_game_over_passes_options_to_game_over_scene(self, mock_pygame_patches, mocker):
        """Test that game_over() passes the current scene's options."""
        scene = Scene()
        mock_switch = mocker.patch.object(scene.scene_manager, 'switch_to_scene')

        scene.game_over()

        mock_switch.assert_called_once()
        switched_scene = mock_switch.call_args[0][0]
        assert switched_scene.options == scene.options


class TestOnTextSubmitEvent:
    """Test Scene.on_text_submit_event() behavior."""

    def test_handles_text_without_error(self, mock_pygame_patches, mocker):
        """Test that on_text_submit_event handles text submission."""
        scene = Scene()

        # Should not raise
        scene.on_text_submit_event('Hello World')

    def test_handles_empty_text(self, mock_pygame_patches, mocker):
        """Test that on_text_submit_event handles empty text."""
        scene = Scene()

        scene.on_text_submit_event('')

    def test_logs_submitted_text(self, mock_pygame_patches, mocker):
        """Test that on_text_submit_event logs the text."""
        scene = Scene()
        mock_info = mocker.patch.object(scene.log, 'info')

        scene.on_text_submit_event('test input')

        mock_info.assert_called_once_with("Text submitted: 'test input'")


class TestOnVideoExposeEvent:
    """Test Scene.on_video_expose_event() behavior."""

    def test_handles_event_without_error(self, mock_pygame_patches, mocker):
        """Test that on_video_expose_event handles the event."""
        scene = Scene()
        event = mocker.Mock()

        scene.on_video_expose_event(event)

    def test_logs_debug_message(self, mock_pygame_patches, mocker):
        """Test that on_video_expose_event logs a debug message."""
        scene = Scene()
        mock_debug = mocker.patch.object(scene.log, 'debug')
        event = mocker.Mock()

        scene.on_video_expose_event(event)

        mock_debug.assert_called_once()
        logged_message = mock_debug.call_args[0][0]
        assert 'Video Expose Event' in logged_message


class TestOnVideoResizeEvent:
    """Test Scene.on_video_resize_event() behavior."""

    def test_handles_event_without_error(self, mock_pygame_patches, mocker):
        """Test that on_video_resize_event handles the event."""
        scene = Scene()
        event = mocker.Mock()

        scene.on_video_resize_event(event)

    def test_logs_debug_message(self, mock_pygame_patches, mocker):
        """Test that on_video_resize_event logs a debug message."""
        scene = Scene()
        mock_debug = mocker.patch.object(scene.log, 'debug')
        event = mocker.Mock()

        scene.on_video_resize_event(event)

        mock_debug.assert_called_once()
        logged_message = mock_debug.call_args[0][0]
        assert 'Video Resize Event' in logged_message


class TestOnSysWmEvent:
    """Test Scene.on_sys_wm_event() behavior."""

    def test_handles_event_without_error(self, mock_pygame_patches, mocker):
        """Test that on_sys_wm_event handles the event."""
        scene = Scene()
        event = mocker.Mock()

        scene.on_sys_wm_event(event)

    def test_logs_debug_message(self, mock_pygame_patches, mocker):
        """Test that on_sys_wm_event logs a debug message."""
        scene = Scene()
        mock_debug = mocker.patch.object(scene.log, 'debug')
        event = mocker.Mock()

        scene.on_sys_wm_event(event)

        mock_debug.assert_called_once()
        logged_message = mock_debug.call_args[0][0]
        assert 'Sys WM Event' in logged_message
