"""Coverage tests for glitchygames/events/touch.py.

This module targets uncovered proxy forwarding methods in TouchEventProxy,
including multi-touch event handlers.
"""

import sys
from pathlib import Path

import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import HashableEvent
from glitchygames.events.touch import TouchEventManager


class TestTouchEventProxyForwarding:
    """Test each TouchEventProxy forwarding method individually."""

    def _create_manager(self, mocker):
        """Create a TouchEventManager with a mock game.

        Returns:
            Tuple of (manager, mock_game).
        """
        mock_game = mocker.Mock()
        manager = TouchEventManager(game=mock_game)
        return manager, mock_game

    def test_proxy_on_touch_down_event(self, mock_pygame_patches, mocker):
        """Touch down event should forward to game."""
        manager, mock_game = self._create_manager(mocker)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.FINGERDOWN, finger_id=1, x=100, y=100)
        proxy.on_touch_down_event(event)

        mock_game.on_touch_down_event.assert_called_once_with(event)

    def test_proxy_on_touch_motion_event(self, mock_pygame_patches, mocker):
        """Touch motion event should forward to game."""
        manager, mock_game = self._create_manager(mocker)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.FINGERMOTION, finger_id=1, x=110, y=110, dx=10, dy=10)
        proxy.on_touch_motion_event(event)

        mock_game.on_touch_motion_event.assert_called_once_with(event)

    def test_proxy_on_touch_up_event(self, mock_pygame_patches, mocker):
        """Touch up event should forward to game."""
        manager, mock_game = self._create_manager(mocker)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.FINGERUP, finger_id=1, x=100, y=100)
        proxy.on_touch_up_event(event)

        mock_game.on_touch_up_event.assert_called_once_with(event)

    def test_proxy_on_multi_touch_down_event(self, mock_pygame_patches, mocker):
        """Multi-touch down event should forward to game."""
        manager, mock_game = self._create_manager(mocker)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.FINGERDOWN, finger_id=2, x=200, y=200)
        proxy.on_multi_touch_down_event(event)

        mock_game.on_multi_touch_down_event.assert_called_once_with(event)

    def test_proxy_on_multi_touch_motion_event(self, mock_pygame_patches, mocker):
        """Multi-touch motion event should forward to game."""
        manager, mock_game = self._create_manager(mocker)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.FINGERMOTION, finger_id=2, x=210, y=210, dx=10, dy=10)
        proxy.on_multi_touch_motion_event(event)

        mock_game.on_multi_touch_motion_event.assert_called_once_with(event)

    def test_proxy_on_multi_touch_up_event(self, mock_pygame_patches, mocker):
        """Multi-touch up event should forward to game."""
        manager, mock_game = self._create_manager(mocker)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.FINGERUP, finger_id=2, x=200, y=200)
        proxy.on_multi_touch_up_event(event)

        mock_game.on_multi_touch_up_event.assert_called_once_with(event)

    def test_proxy_init_without_sdl2_touch(self, mock_pygame_patches, mocker):
        """TouchEventProxy should handle missing pygame._sdl2.touch gracefully."""
        # Patch pygame._sdl2 to not have touch attribute
        mocker.patch.object(pygame, '_sdl2', mocker.Mock(spec=[]))

        mock_game = mocker.Mock()
        manager = TouchEventManager(game=mock_game)
        proxy = manager.proxies[0]

        # The proxy should still work, just without the SDL2 touch in proxies
        assert proxy.game is mock_game
