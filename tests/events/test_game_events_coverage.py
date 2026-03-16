"""Extended test coverage for GameEventManager proxy forwarding and args classmethod."""

import argparse
import sys
from pathlib import Path

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.engine import GameEventManager
from tests.mocks import MockFactory


class TestGameEventProxyForwarding:
    """Tests for GameEventProxy event forwarding methods."""

    def _create_proxy_with_mock_game(self, mocker):
        """Create a GameEventProxy with a mock game that tracks event calls.

        Returns:
            tuple: (proxy, mock_game) pair.

        """
        mock_game = MockFactory.create_game_mock()
        proxy = GameEventManager.GameEventProxy(game=mock_game)
        return proxy, mock_game

    def _create_mock_event(self, mocker):
        """Create a mock hashable event.

        Returns:
            object: A mock event object.

        """
        return mocker.Mock()

    def test_on_active_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_active_event forwards the event to game.on_active_event."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_active_event(event)

        mock_game.on_active_event.assert_called_once_with(event=event)

    def test_on_fps_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_fps_event forwards the event to game.on_fps_event."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_fps_event(event)

        mock_game.on_fps_event.assert_called_once_with(event=event)

    def test_on_game_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_game_event forwards the event to game.on_game_event."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_game_event(event)

        mock_game.on_game_event.assert_called_once_with(event=event)

    def test_on_menu_item_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_menu_item_event forwards the event to game.on_menu_item_event."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_menu_item_event(event)

        mock_game.on_menu_item_event.assert_called_once_with(event=event)

    def test_on_sys_wm_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_sys_wm_event forwards the event to game.on_sys_wm_event."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_sys_wm_event(event)

        mock_game.on_sys_wm_event.assert_called_once_with(event=event)

    def test_on_user_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_user_event forwards the event to game.on_user_event."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_user_event(event)

        mock_game.on_user_event.assert_called_once_with(event=event)

    def test_on_video_expose_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_video_expose_event forwards the event to game.on_video_expose_event."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_video_expose_event(event)

        mock_game.on_video_expose_event.assert_called_once_with(event=event)

    def test_on_video_resize_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_video_resize_event forwards the event to game.on_video_resize_event."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_video_resize_event(event)

        mock_game.on_video_resize_event.assert_called_once_with(event=event)

    def test_on_quit_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_quit_event forwards the event to game.on_quit_event."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_quit_event(event)

        mock_game.on_quit_event.assert_called_once_with(event=event)

    def test_on_render_device_reset_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_render_device_reset_event forwards to game."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_render_device_reset_event(event)

        mock_game.on_render_device_reset_event.assert_called_once_with(event=event)

    def test_on_render_targets_reset_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_render_targets_reset_event forwards to game."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_render_targets_reset_event(event)

        mock_game.on_render_targets_reset_event.assert_called_once_with(event=event)

    def test_on_clipboard_update_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_clipboard_update_event forwards to game."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_clipboard_update_event(event)

        mock_game.on_clipboard_update_event.assert_called_once_with(event=event)

    def test_on_locale_changed_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """Test on_locale_changed_event forwards to game."""
        proxy, mock_game = self._create_proxy_with_mock_game(mocker)
        event = self._create_mock_event(mocker)

        proxy.on_locale_changed_event(event)

        mock_game.on_locale_changed_event.assert_called_once_with(event=event)


class TestGameEventManagerForwarding:
    """Tests for GameEventManager forwarding to proxies."""

    def _create_manager_with_mock_proxy(self, mocker):
        """Create a GameEventManager with a mocked proxy.

        Returns:
            tuple: (manager, mock_proxy) pair.

        """
        mock_game = MockFactory.create_game_mock()
        manager = GameEventManager(game=mock_game)
        # Replace the proxy with a mock to verify forwarding
        mock_proxy = mocker.Mock()
        manager.proxies = [mock_proxy]
        return manager, mock_proxy

    def test_manager_on_active_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_active_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_active_event(event)

        mock_proxy.on_active_event.assert_called_once_with(event)

    def test_manager_on_fps_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_fps_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_fps_event(event)

        mock_proxy.on_fps_event.assert_called_once_with(event)

    def test_manager_on_game_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_game_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_game_event(event)

        mock_proxy.on_game_event.assert_called_once_with(event)

    def test_manager_on_menu_item_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_menu_item_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_menu_item_event(event)

        mock_proxy.on_menu_item_event.assert_called_once_with(event)

    def test_manager_on_sys_wm_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_sys_wm_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_sys_wm_event(event)

        mock_proxy.on_sys_wm_event.assert_called_once_with(event)

    def test_manager_on_user_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_user_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_user_event(event)

        mock_proxy.on_user_event.assert_called_once_with(event)

    def test_manager_on_video_expose_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_video_expose_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_video_expose_event(event)

        mock_proxy.on_video_expose_event.assert_called_once_with(event)

    def test_manager_on_video_resize_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_video_resize_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_video_resize_event(event)

        mock_proxy.on_video_resize_event.assert_called_once_with(event)

    def test_manager_on_quit_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_quit_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_quit_event(event)

        mock_proxy.on_quit_event.assert_called_once_with(event)

    def test_manager_on_clipboard_update_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_clipboard_update_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_clipboard_update_event(event)

        mock_proxy.on_clipboard_update_event.assert_called_once_with(event)

    def test_manager_on_locale_changed_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_locale_changed_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_locale_changed_event(event)

        mock_proxy.on_locale_changed_event.assert_called_once_with(event)

    def test_manager_on_render_device_reset_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_render_device_reset_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_render_device_reset_event(event)

        mock_proxy.on_render_device_reset_event.assert_called_once_with(event)

    def test_manager_on_render_targets_reset_event(self, mock_pygame_patches, mocker):
        """Test GameEventManager.on_render_targets_reset_event forwards to proxies."""
        manager, mock_proxy = self._create_manager_with_mock_proxy(mocker)
        event = mocker.Mock()

        manager.on_render_targets_reset_event(event)

        mock_proxy.on_render_targets_reset_event.assert_called_once_with(event)


class TestGameEventManagerArgs:
    """Tests for GameEventManager.args classmethod."""

    def test_args_adds_log_level_argument(self, mock_pygame_patches):
        """Test that args adds the --log-level argument."""
        parser = argparse.ArgumentParser()
        result = GameEventManager.args(parser)

        assert result is parser
        args = parser.parse_args(['--log-level', 'debug'])
        assert args.log_level == 'debug'

    def test_args_log_level_choices(self, mock_pygame_patches):
        """Test that --log-level accepts valid choices."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        for level in ['debug', 'info', 'warning', 'error', 'critical']:
            args = parser.parse_args(['--log-level', level])
            assert args.log_level == level

    def test_args_log_level_case_insensitive(self, mock_pygame_patches):
        """Test that --log-level accepts uppercase input via type=str.lower."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args(['--log-level', 'DEBUG'])
        assert args.log_level == 'debug'

    def test_args_adds_no_unhandled_events_flag(self, mock_pygame_patches):
        """Test that args adds the --no-unhandled-events flag."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args(['--no-unhandled-events'])
        assert args.no_unhandled_events is True

    def test_args_no_unhandled_events_default_false(self, mock_pygame_patches):
        """Test that --no-unhandled-events defaults to False."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args([])
        assert args.no_unhandled_events is False

    def test_args_adds_profile_flag(self, mock_pygame_patches):
        """Test that args adds the --profile flag."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args(['--profile'])
        assert args.profile is True

    def test_args_profile_short_flag(self, mock_pygame_patches):
        """Test that -p is the short form for --profile."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args(['-p'])
        assert args.profile is True

    def test_args_profile_default_false(self, mock_pygame_patches):
        """Test that --profile defaults to False."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args([])
        assert args.profile is False

    def test_args_log_level_short_flag(self, mock_pygame_patches):
        """Test that -l is the short form for --log-level."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args(['-l', 'warning'])
        assert args.log_level == 'warning'

    def test_args_defaults_all(self, mock_pygame_patches):
        """Test all default values from args."""
        parser = argparse.ArgumentParser()
        GameEventManager.args(parser)

        args = parser.parse_args([])
        assert args.log_level == 'info'
        assert args.no_unhandled_events is False
        assert args.profile is False
