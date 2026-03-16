"""Coverage tests for glitchygames/events/window.py.

This module targets uncovered proxy forwarding methods in WindowEventProxy.
"""

import sys
from pathlib import Path

import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import HashableEvent
from glitchygames.events.window import WindowEventManager


class TestWindowEventProxyForwarding:
    """Test each WindowEventProxy forwarding method individually."""

    def _create_manager(self, mocker):
        """Create a WindowEventManager with a mock game.

        Returns:
            Tuple of (manager, mock_game).
        """
        mock_game = mocker.Mock()
        manager = WindowEventManager(game=mock_game)
        return manager, mock_game

    def test_proxy_on_window_hidden_event(self, mock_pygame_patches, mocker):
        """Window hidden event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWHIDDEN)
        manager.on_window_hidden_event(event)

        mock_game.on_window_hidden_event.assert_called_once_with(event)

    def test_proxy_on_window_hit_test_event(self, mock_pygame_patches, mocker):
        """Window hit test event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWHITTEST)
        manager.on_window_hit_test_event(event)

        mock_game.on_window_hit_test_event.assert_called_once_with(event)

    def test_proxy_on_window_maximized_event(self, mock_pygame_patches, mocker):
        """Window maximized event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWMAXIMIZED)
        manager.on_window_maximized_event(event)

        mock_game.on_window_maximized_event.assert_called_once_with(event)

    def test_proxy_on_window_minimized_event(self, mock_pygame_patches, mocker):
        """Window minimized event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWMINIMIZED)
        manager.on_window_minimized_event(event)

        mock_game.on_window_minimized_event.assert_called_once_with(event)

    def test_proxy_on_window_moved_event(self, mock_pygame_patches, mocker):
        """Window moved event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWMOVED, x=100, y=200)
        manager.on_window_moved_event(event)

        mock_game.on_window_moved_event.assert_called_once_with(event)

    def test_proxy_on_window_resized_event(self, mock_pygame_patches, mocker):
        """Window resized event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWRESIZED, x=1024, y=768)
        manager.on_window_resized_event(event)

        mock_game.on_window_resized_event.assert_called_once_with(event)

    def test_proxy_on_window_restored_event(self, mock_pygame_patches, mocker):
        """Window restored event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWRESTORED)
        manager.on_window_restored_event(event)

        mock_game.on_window_restored_event.assert_called_once_with(event)

    def test_proxy_on_window_shown_event(self, mock_pygame_patches, mocker):
        """Window shown event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWSHOWN)
        manager.on_window_shown_event(event)

        mock_game.on_window_shown_event.assert_called_once_with(event)

    def test_proxy_on_window_size_changed_event(self, mock_pygame_patches, mocker):
        """Window size changed event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWSIZECHANGED, x=800, y=600)
        manager.on_window_size_changed_event(event)

        mock_game.on_window_size_changed_event.assert_called_once_with(event)

    def test_proxy_on_window_take_focus_event(self, mock_pygame_patches, mocker):
        """Window take focus event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWTAKEFOCUS)
        manager.on_window_take_focus_event(event)

        mock_game.on_window_take_focus_event.assert_called_once_with(event)

    def test_proxy_on_window_exposed_event(self, mock_pygame_patches, mocker):
        """Window exposed event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWEXPOSED)
        manager.on_window_exposed_event(event)

        mock_game.on_window_exposed_event.assert_called_once_with(event)

    def test_proxy_on_window_leave_event(self, mock_pygame_patches, mocker):
        """Window leave event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWLEAVE)
        manager.on_window_leave_event(event)

        mock_game.on_window_leave_event.assert_called_once_with(event)

    def test_proxy_on_window_focus_lost_event(self, mock_pygame_patches, mocker):
        """Window focus lost event should forward to game."""
        manager, mock_game = self._create_manager(mocker)

        event = HashableEvent(pygame.WINDOWFOCUSLOST)
        manager.on_window_focus_lost_event(event)

        mock_game.on_window_focus_lost_event.assert_called_once_with(event)

    def test_manager_args_classmethod(self, mock_pygame_patches, mocker):
        """args() classmethod should return the parser with Window Options group."""
        import argparse

        parser = argparse.ArgumentParser()
        result = WindowEventManager.args(parser)
        assert result is parser
