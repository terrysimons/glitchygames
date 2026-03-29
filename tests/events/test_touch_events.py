"""Tests for touch event functionality.

This module combines tests for:
- TouchEvents interface and TouchEventStubs
- TouchEventProxy forwarding and delegation
- TouchEventManager initialization and event routing
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import (
    HashableEvent,
    TouchEvents,
    TouchEventStubs,
    UnhandledEventError,
)
from glitchygames.events.touch import TouchEventManager
from tests.mocks.test_mock_factory import MockFactory

# ---------------------------------------------------------------------------
# Fixtures (from test_touch_events_manager_coverage.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_game_fixture(mocker):
    """Create a mock game object with all required event handlers."""
    return mocker.Mock()


@pytest.fixture
def mock_event(mocker):
    """Create a mock pygame event."""
    return mocker.Mock(spec=pygame.event.Event)


# ---------------------------------------------------------------------------
# TouchEvents interface tests (from test_events_touch_events.py)
# ---------------------------------------------------------------------------


class TestTouchEvents:
    """Test TouchEvents interface functionality."""

    def test_touch_events_interface(self, mock_pygame_patches):
        """Test TouchEvents interface methods."""
        # Test that TouchEvents has required abstract methods
        assert hasattr(TouchEvents, 'on_touch_down_event')
        assert hasattr(TouchEvents, 'on_touch_motion_event')
        assert hasattr(TouchEvents, 'on_touch_up_event')
        assert hasattr(TouchEvents, 'on_multi_touch_down_event')
        assert hasattr(TouchEvents, 'on_multi_touch_motion_event')
        assert hasattr(TouchEvents, 'on_multi_touch_up_event')

    def test_touch_event_stubs_implementation(self, mock_pygame_patches, mocker):
        """Test TouchEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = TouchEventStubs()
        assert hasattr(stub, 'on_touch_down_event')
        assert hasattr(stub, 'on_touch_motion_event')
        assert hasattr(stub, 'on_touch_up_event')

        # Test that stub methods can be called with proper game object
        self._setup_mock_game_for_stub(stub, mocker)

        # Test method calls — should raise UnhandledEventError (no logging before raise)
        event = HashableEvent(pygame.FINGERDOWN, finger_id=1, x=100, y=100)
        with pytest.raises(UnhandledEventError, match='Unhandled event'):
            stub.on_touch_down_event(event)

    def test_touch_down_event(self, mock_pygame_patches):
        """Test touch down event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_touch_down_event': lambda event: (
                    scene.touch_events_received.append(('touch_down', event)) or True
                ),
            },
        )

        # Test touch down
        event = HashableEvent(pygame.FINGERDOWN, finger_id=1, x=100, y=100)
        scene.on_touch_down_event(event)

        # Verify the event was handled
        assert len(scene.touch_events_received) == 1
        assert scene.touch_events_received[0][0] == 'touch_down'
        assert scene.touch_events_received[0][1].type == pygame.FINGERDOWN

    def test_touch_motion_event(self, mock_pygame_patches):
        """Test touch motion event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_touch_motion_event': lambda event: (
                    scene.touch_events_received.append(('touch_motion', event)) or True
                ),
            },
        )

        # Test touch motion
        event = HashableEvent(pygame.FINGERMOTION, finger_id=1, x=100, y=100, dx=10, dy=10)
        scene.on_touch_motion_event(event)

        # Verify the event was handled
        assert len(scene.touch_events_received) == 1
        assert scene.touch_events_received[0][0] == 'touch_motion'
        assert scene.touch_events_received[0][1].type == pygame.FINGERMOTION

    def test_touch_up_event(self, mock_pygame_patches):
        """Test touch up event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_touch_up_event': lambda event: (
                    scene.touch_events_received.append(('touch_up', event)) or True
                ),
            },
        )

        # Test touch up
        event = HashableEvent(pygame.FINGERUP, finger_id=1, x=100, y=100)
        scene.on_touch_up_event(event)

        # Verify the event was handled
        assert len(scene.touch_events_received) == 1
        assert scene.touch_events_received[0][0] == 'touch_up'
        assert scene.touch_events_received[0][1].type == pygame.FINGERUP

    def test_multi_touch_down_event(self, mock_pygame_patches):
        """Test multi touch down event handling."""
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_multi_touch_down_event': lambda event: (
                    scene.touch_events_received.append(('multi_touch_down', event)) or True
                ),
            },
        )

        event = HashableEvent(pygame.FINGERDOWN, finger_id=1, x=100, y=100)
        scene.on_multi_touch_down_event(event)

        assert len(scene.touch_events_received) == 1
        assert scene.touch_events_received[0][0] == 'multi_touch_down'
        assert scene.touch_events_received[0][1].type == pygame.FINGERDOWN

    def test_multi_touch_motion_event(self, mock_pygame_patches):
        """Test multi touch motion event handling."""
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_multi_touch_motion_event': lambda event: (
                    scene.touch_events_received.append(('multi_touch_motion', event)) or True
                ),
            },
        )

        event = HashableEvent(pygame.FINGERMOTION, finger_id=1, x=100, y=100, dx=10, dy=10)
        scene.on_multi_touch_motion_event(event)

        assert len(scene.touch_events_received) == 1
        assert scene.touch_events_received[0][0] == 'multi_touch_motion'
        assert scene.touch_events_received[0][1].type == pygame.FINGERMOTION

    def test_multi_touch_up_event(self, mock_pygame_patches):
        """Test multi touch up event handling."""
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_multi_touch_up_event': lambda event: (
                    scene.touch_events_received.append(('multi_touch_up', event)) or True
                ),
            },
        )

        event = HashableEvent(pygame.FINGERUP, finger_id=1, x=100, y=100)
        scene.on_multi_touch_up_event(event)

        assert len(scene.touch_events_received) == 1
        assert scene.touch_events_received[0][0] == 'multi_touch_up'
        assert scene.touch_events_received[0][1].type == pygame.FINGERUP

    def test_multiple_finger_events(self, mock_pygame_patches):
        """Test multiple finger touch events."""
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_touch_down_event': lambda event: (
                    scene.touch_events_received.append(('touch_down', event)) or True
                ),
                'on_touch_motion_event': lambda event: (
                    scene.touch_events_received.append(('touch_motion', event)) or True
                ),
                'on_touch_up_event': lambda event: (
                    scene.touch_events_received.append(('touch_up', event)) or True
                ),
            },
        )

        for finger_id in range(5):
            event = HashableEvent(pygame.FINGERDOWN, finger_id=finger_id, x=100, y=100)
            scene.on_touch_down_event(event)
            event = HashableEvent(
                pygame.FINGERMOTION,
                finger_id=finger_id,
                x=100,
                y=100,
                dx=10,
                dy=10,
            )
            scene.on_touch_motion_event(event)
            event = HashableEvent(pygame.FINGERUP, finger_id=finger_id, x=100, y=100)
            scene.on_touch_up_event(event)

        assert len(scene.touch_events_received) == 15

    def test_touch_events_with_pressure(self, mock_pygame_patches):
        """Test touch events with pressure values."""
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_touch_down_event': lambda event: (
                    scene.touch_events_received.append(('touch_down', event)) or True
                ),
                'on_touch_motion_event': lambda event: (
                    scene.touch_events_received.append(('touch_motion', event)) or True
                ),
                'on_touch_up_event': lambda event: (
                    scene.touch_events_received.append(('touch_up', event)) or True
                ),
            },
        )

        event = HashableEvent(pygame.FINGERDOWN, finger_id=1, x=100, y=100, pressure=0.8)
        scene.on_touch_down_event(event)
        event = HashableEvent(
            pygame.FINGERMOTION,
            finger_id=1,
            x=100,
            y=100,
            dx=10,
            dy=10,
            pressure=0.6,
        )
        scene.on_touch_motion_event(event)
        event = HashableEvent(pygame.FINGERUP, finger_id=1, x=100, y=100, pressure=0.0)
        scene.on_touch_up_event(event)

        assert len(scene.touch_events_received) == 3
        assert scene.touch_events_received[0][0] == 'touch_down'
        assert scene.touch_events_received[1][0] == 'touch_motion'
        assert scene.touch_events_received[2][0] == 'touch_up'

    def test_touch_events_with_different_positions(self, mock_pygame_patches):
        """Test touch events with different positions."""
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_touch_down_event': lambda event: (
                    scene.touch_events_received.append(('touch_down', event)) or True
                ),
                'on_touch_motion_event': lambda event: (
                    scene.touch_events_received.append(('touch_motion', event)) or True
                ),
                'on_touch_up_event': lambda event: (
                    scene.touch_events_received.append(('touch_up', event)) or True
                ),
            },
        )

        positions = [(0, 0), (100, 100), (200, 200), (50, 150), (150, 50)]

        for x, y in positions:
            event = HashableEvent(pygame.FINGERDOWN, finger_id=1, x=x, y=y)
            scene.on_touch_down_event(event)
            event = HashableEvent(pygame.FINGERMOTION, finger_id=1, x=x, y=y, dx=5, dy=5)
            scene.on_touch_motion_event(event)
            event = HashableEvent(pygame.FINGERUP, finger_id=1, x=x, y=y)
            scene.on_touch_up_event(event)

        assert len(scene.touch_events_received) == 15

    def _setup_mock_game_for_stub(self, stub, mocker):
        """Set up mock game object for event stubs."""
        mock_game = mocker.Mock()
        mock_game.options = {'debug_events': False, 'no_unhandled_events': True}
        stub.options = mock_game.options
        return mock_game


# ---------------------------------------------------------------------------
# TouchEventProxy forwarding tests (from test_touch_events_coverage.py)
# ---------------------------------------------------------------------------


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
        mocker.patch.object(pygame, '_sdl2', mocker.Mock(spec=[]))

        mock_game = mocker.Mock()
        manager = TouchEventManager(game=mock_game)
        proxy = manager.proxies[0]

        assert proxy.game is mock_game


# ---------------------------------------------------------------------------
# TouchEventProxy delegation tests (from test_touch_events_manager_coverage.py)
# ---------------------------------------------------------------------------


class TestTouchEventProxy:
    """Test TouchEventProxy event delegation."""

    def test_proxy_init(self, mock_game_fixture):
        proxy = TouchEventManager.TouchEventProxy(game=mock_game_fixture)
        assert proxy.game is mock_game_fixture
        assert mock_game_fixture in proxy.proxies

    def test_on_touch_down_event(self, mock_game_fixture, mock_event):
        proxy = TouchEventManager.TouchEventProxy(game=mock_game_fixture)
        proxy.on_touch_down_event(mock_event)
        mock_game_fixture.on_touch_down_event.assert_called_once_with(mock_event)

    def test_on_touch_motion_event(self, mock_game_fixture, mock_event):
        proxy = TouchEventManager.TouchEventProxy(game=mock_game_fixture)
        proxy.on_touch_motion_event(mock_event)
        mock_game_fixture.on_touch_motion_event.assert_called_once_with(mock_event)

    def test_on_touch_up_event(self, mock_game_fixture, mock_event):
        proxy = TouchEventManager.TouchEventProxy(game=mock_game_fixture)
        proxy.on_touch_up_event(mock_event)
        mock_game_fixture.on_touch_up_event.assert_called_once_with(mock_event)

    def test_on_multi_touch_down_event(self, mock_game_fixture, mock_event):
        proxy = TouchEventManager.TouchEventProxy(game=mock_game_fixture)
        proxy.on_multi_touch_down_event(mock_event)
        mock_game_fixture.on_multi_touch_down_event.assert_called_once_with(mock_event)

    def test_on_multi_touch_motion_event(self, mock_game_fixture, mock_event):
        proxy = TouchEventManager.TouchEventProxy(game=mock_game_fixture)
        proxy.on_multi_touch_motion_event(mock_event)
        mock_game_fixture.on_multi_touch_motion_event.assert_called_once_with(mock_event)

    def test_on_multi_touch_up_event(self, mock_game_fixture, mock_event):
        proxy = TouchEventManager.TouchEventProxy(game=mock_game_fixture)
        proxy.on_multi_touch_up_event(mock_event)
        mock_game_fixture.on_multi_touch_up_event.assert_called_once_with(mock_event)


# ---------------------------------------------------------------------------
# TouchEventManager tests (from test_touch_events_manager_coverage.py + test_events_touch_events.py)
# ---------------------------------------------------------------------------


class TestTouchEventManager:
    """Test TouchEventManager initialization."""

    def test_init(self, mock_game_fixture):
        manager = TouchEventManager(game=mock_game_fixture)
        assert len(manager.proxies) == 1


class TestTouchManager:
    """Test TouchEventManager in isolation."""

    def test_touch_manager_initialization(self, mock_pygame_patches, mocker):
        """Test TouchEventManager initializes correctly."""
        mock_game = mocker.Mock()
        manager = TouchEventManager(game=mock_game)

        assert manager.game == mock_game
        assert hasattr(manager, 'proxies')
        assert isinstance(manager.proxies, list)

    def test_touch_manager_events(self, mock_pygame_patches, mocker):
        """Test touch event handling through manager."""
        mock_game = mocker.Mock()
        manager = TouchEventManager(game=mock_game)

        # Test touch finger down
        touch_down_event = HashableEvent(
            pygame.FINGERDOWN,
            touch_id=1,
            finger_id=1,
            x=100,
            y=100,
            dx=0,
            dy=0,
        )
        manager.on_touch_finger_down_event(touch_down_event)

        # Test touch finger up
        touch_up_event = HashableEvent(
            pygame.FINGERUP,
            touch_id=1,
            finger_id=1,
            x=100,
            y=100,
            dx=0,
            dy=0,
        )
        manager.on_touch_finger_up_event(touch_up_event)

        # Test touch finger motion
        touch_motion_event = HashableEvent(
            pygame.FINGERMOTION,
            touch_id=1,
            finger_id=1,
            x=110,
            y=110,
            dx=10,
            dy=10,
        )
        manager.on_touch_finger_motion_event(touch_motion_event)
