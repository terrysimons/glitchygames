"""Tests for mouse event functionality.

This module tests mouse event interfaces, stubs, and event handling.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import (
    HashableEvent,
    MouseEvents,
    MouseEventStubs,
    UnhandledEventError,
)

from tests.mocks.test_mock_factory import MockFactory


class TestMouseEvents:
    """Test MouseEvents interface functionality."""

    def test_mouse_events_interface(self, mock_pygame_patches):
        """Test MouseEvents interface methods."""
        # Test that MouseEvents has required abstract methods
        assert hasattr(MouseEvents, "on_mouse_motion_event")
        assert hasattr(MouseEvents, "on_mouse_drag_event")
        assert hasattr(MouseEvents, "on_mouse_drop_event")
        assert hasattr(MouseEvents, "on_left_mouse_drag_event")
        assert hasattr(MouseEvents, "on_left_mouse_drop_event")
        assert hasattr(MouseEvents, "on_middle_mouse_drag_event")
        assert hasattr(MouseEvents, "on_middle_mouse_drop_event")
        assert hasattr(MouseEvents, "on_right_mouse_drag_event")
        assert hasattr(MouseEvents, "on_right_mouse_drop_event")
        assert hasattr(MouseEvents, "on_mouse_button_down_event")
        assert hasattr(MouseEvents, "on_mouse_button_up_event")
        assert hasattr(MouseEvents, "on_mouse_wheel_event")

    def test_mouse_event_stubs_implementation(self, mock_pygame_patches):
        """Test MouseEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = MouseEventStubs()
        assert hasattr(stub, "on_mouse_motion_event")
        assert hasattr(stub, "on_mouse_drag_event")
        assert hasattr(stub, "on_mouse_drop_event")
        assert hasattr(stub, "on_mouse_button_down_event")
        assert hasattr(stub, "on_mouse_button_up_event")
        assert hasattr(stub, "on_mouse_wheel_event")

        # Test that stub methods can be called with proper game object
        self._setup_mock_game_for_stub(stub)

        # Test method calls
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):

                stub.on_mouse_motion_event(event)
        # Expected to call unhandled_event
        # Exception was raised as expected

    def test_mouse_button_down_event(self, mock_pygame_patches):
        """Test mouse button down event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_mouse_button_down_event": lambda event: scene.mouse_events_received.append(event) or True
            }
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100))
        result = scene.on_mouse_button_down_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.mouse_events_received) == 1
        assert scene.mouse_events_received[0].button == 1

    def test_mouse_button_up_event(self, mock_pygame_patches):
        """Test mouse button up event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_mouse_button_up_event": lambda event: scene.mouse_events_received.append(event) or True
            }
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=1, pos=(100, 100))
        result = scene.on_mouse_button_up_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.mouse_events_received) == 1
        assert scene.mouse_events_received[0].button == 1

    def test_mouse_motion_event(self, mock_pygame_patches):
        """Test mouse motion event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_mouse_motion_event": lambda event: scene.mouse_events_received.append(event) or True
            }
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        result = scene.on_mouse_motion_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.mouse_events_received) == 1
        assert scene.mouse_events_received[0].pos == (100, 100)

    def test_mouse_wheel_event(self, mock_pygame_patches):
        """Test mouse wheel event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test mouse wheel
        event = HashableEvent(pygame.MOUSEWHEEL, x=0, y=1)
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):

                stub.on_mouse_wheel_event(event)
        # Exception was raised as expected

    def test_mouse_drag_event(self, mock_pygame_patches):
        """Test mouse drag event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test mouse drag
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):

                stub.on_mouse_drag_event(event, trigger="test_trigger")
        # Exception was raised as expected

    def test_mouse_drop_event(self, mock_pygame_patches):
        """Test mouse drop event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test mouse drop
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=1, pos=(100, 100))
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):

                stub.on_mouse_drop_event(event, trigger="test_trigger")
        # Exception was raised as expected

    def test_left_mouse_drag_event(self, mock_pygame_patches):
        """Test left mouse drag event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test left mouse drag
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):

                stub.on_left_mouse_drag_event(event, trigger="test_trigger")
        # Exception was raised as expected

    def test_left_mouse_drop_event(self, mock_pygame_patches):
        """Test left mouse drop event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test left mouse drop
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=1, pos=(100, 100))
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):

                stub.on_left_mouse_drop_event(event, trigger="test_trigger")
        # Exception was raised as expected

    def test_middle_mouse_drag_event(self, mock_pygame_patches):
        """Test middle mouse drag event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test middle mouse drag
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):

                stub.on_middle_mouse_drag_event(event, trigger="test_trigger")
        # Exception was raised as expected

    def test_middle_mouse_drop_event(self, mock_pygame_patches):
        """Test middle mouse drop event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test middle mouse drop
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=2, pos=(100, 100))
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):

                stub.on_middle_mouse_drop_event(event, trigger="test_trigger")
        # Exception was raised as expected

    def test_right_mouse_drag_event(self, mock_pygame_patches):
        """Test right mouse drag event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test right mouse drag
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):

                stub.on_right_mouse_drag_event(event, trigger="test_trigger")
        # Exception was raised as expected

    def test_right_mouse_drop_event(self, mock_pygame_patches):
        """Test right mouse drop event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test right mouse drop
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=3, pos=(100, 100))
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):

                stub.on_right_mouse_drop_event(event, trigger="test_trigger")
        # Exception was raised as expected

    def _setup_mock_game_for_stub(self, stub):
        """Set up mock game object for event stubs."""
        mock_game = Mock()
        mock_game.options = {
            "debug_events": False,
            "no_unhandled_events": True
        }
        stub.options = mock_game.options
        return mock_game


class TestMouseEventManager:
    """Test MouseEventManager in isolation."""

    def test_mouse_manager_initialization(self, mock_pygame_patches):
        """Test MouseEventManager initializes correctly."""
        from glitchygames.events.mouse import MouseEventManager

        mock_game = Mock()
        manager = MouseEventManager(game=mock_game)

        assert manager.game == mock_game
        assert hasattr(manager, "on_mouse_motion_event")
        assert hasattr(manager, "on_mouse_button_down_event")

    def test_mouse_manager_events(self, mock_pygame_patches):
        """Test mouse event handling through manager."""
        from unittest.mock import patch

        from glitchygames.events.mouse import MouseEventManager

        from tests.mocks.test_mock_factory import MockFactory

        # Create a proper scene mock with all_sprites that's iterable
        scene_mock = MockFactory.create_event_test_scene_mock()

        # Create a mock sprite group that's iterable
        mock_sprites = [Mock(), Mock(), Mock()]  # List of mock sprites
        scene_mock.all_sprites = mock_sprites

        # Mock the scene's event handlers to prevent infinite loops
        scene_mock.on_mouse_motion_event = Mock()
        scene_mock.on_mouse_button_down_event = Mock()
        scene_mock.on_mouse_button_up_event = Mock()

        # self.game IS the scene, so we pass the scene directly
        manager = MouseEventManager(game=scene_mock)

        # Mock collided_sprites to prevent pygame.sprite.spritecollide calls
        with patch("glitchygames.events.mouse.collided_sprites", return_value=[]):
            # Test mouse motion - use patch to prevent recursive calls
            with patch.object(scene_mock, "on_mouse_motion_event") as mock_handler:
                motion_event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10), buttons=(0, 0, 0))
                manager.on_mouse_motion_event(motion_event)
                mock_handler.assert_called_once_with(motion_event)

            # Test mouse button down
            with patch.object(scene_mock, "on_mouse_button_down_event") as mock_handler:
                down_event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(100, 100), button=1)
                manager.on_mouse_button_down_event(down_event)
                mock_handler.assert_called_once_with(down_event)

            # Test mouse button up
            with patch.object(scene_mock, "on_mouse_button_up_event") as mock_handler:
                up_event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(100, 100), button=1)
                manager.on_mouse_button_up_event(up_event)
                mock_handler.assert_called_once_with(up_event)

    def test_mouse_down_order_generic_then_specific(self, mock_pygame_patches):
        """Left down should call generic scene handler first, then left-specific."""
        from glitchygames.events.mouse import MouseEventManager

        scene = MockFactory.create_event_test_scene_mock()
        call_order = []

        def left_down(event):
            call_order.append("left")
            return True

        def generic_down(event):
            call_order.append("generic")
            return True

        scene.on_left_mouse_button_down_event = left_down
        scene.on_mouse_button_down_event = generic_down

        manager = MouseEventManager(game=scene)

        with patch("glitchygames.events.mouse.collided_sprites", return_value=[]):
            event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=1)
            manager.on_mouse_button_down_event(event)

        assert call_order == ["generic", "left"]

    def test_mouse_up_order_specific_then_generic(self, mock_pygame_patches):
        """Left up should call left-specific then generic scene handler."""
        from glitchygames.events.mouse import MouseEventManager

        scene = MockFactory.create_event_test_scene_mock()
        call_order = []

        def left_up(event):
            call_order.append("left")
            return True

        def generic_up(event):
            call_order.append("generic")
            return True

        scene.on_left_mouse_button_up_event = left_up
        scene.on_mouse_button_up_event = generic_up

        manager = MouseEventManager(game=scene)

        with patch("glitchygames.events.mouse.collided_sprites", return_value=[]):
            event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(10, 10), button=1)
            manager.on_mouse_button_up_event(event)

        assert call_order == ["left", "generic"]

    def test_right_button_down_routes_to_right_specific(self, mock_pygame_patches):
        """Right button down should hit right-specific, not middle."""
        from glitchygames.events.mouse import MouseEventManager

        scene = MockFactory.create_event_test_scene_mock()
        scene.on_right_mouse_button_down_event = Mock(return_value=True)
        scene.on_middle_mouse_button_down_event = Mock(return_value=True)

        manager = MouseEventManager(game=scene)

        with patch("glitchygames.events.mouse.collided_sprites", return_value=[]):
            event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=3)
            manager.on_mouse_button_down_event(event)

        scene.on_right_mouse_button_down_event.assert_called_once()
        scene.on_middle_mouse_button_down_event.assert_not_called()

    def test_middle_mouse_down_up_order_generic_then_specific(self, mock_pygame_patches):
        """Middle button down: generic then specific; up: specific then generic."""
        from glitchygames.events.mouse import MouseEventManager

        scene = MockFactory.create_event_test_scene_mock()
        down_order, up_order = [], []

        scene.on_middle_mouse_button_down_event = lambda e: down_order.append("middle") or True
        scene.on_mouse_button_down_event = lambda e: down_order.append("generic") or True
        scene.on_middle_mouse_button_up_event = lambda e: up_order.append("middle") or True
        scene.on_mouse_button_up_event = lambda e: up_order.append("generic") or True

        manager = MouseEventManager(game=scene)
        with patch("glitchygames.events.mouse.collided_sprites", return_value=[]):
            md = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(1, 1), button=2)
            mu = HashableEvent(pygame.MOUSEBUTTONUP, pos=(1, 1), button=2)
            manager.on_mouse_button_down_event(md)
            manager.on_mouse_button_up_event(mu)

        assert down_order == ["generic", "middle"]
        assert up_order == ["middle", "generic"]

    def test_right_mouse_up_order_specific_then_generic(self, mock_pygame_patches):
        """Right button up should be specific then generic."""
        from glitchygames.events.mouse import MouseEventManager

        scene = MockFactory.create_event_test_scene_mock()
        order = []

        scene.on_right_mouse_button_up_event = lambda e: order.append("right") or True
        scene.on_mouse_button_up_event = lambda e: order.append("generic") or True

        manager = MouseEventManager(game=scene)
        with patch("glitchygames.events.mouse.collided_sprites", return_value=[]):
            mu = HashableEvent(pygame.MOUSEBUTTONUP, pos=(2, 2), button=3)
            manager.on_mouse_button_up_event(mu)

        assert order == ["right", "generic"]

    def test_right_mouse_down_order_generic_then_specific(self, mock_pygame_patches):
        """Right button down should be generic then specific."""
        from glitchygames.events.mouse import MouseEventManager

        scene = MockFactory.create_event_test_scene_mock()
        order = []

        scene.on_right_mouse_button_down_event = lambda e: order.append("right") or True
        scene.on_mouse_button_down_event = lambda e: order.append("generic") or True

        manager = MouseEventManager(game=scene)
        with patch("glitchygames.events.mouse.collided_sprites", return_value=[]):
            md = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(3, 3), button=3)
            manager.on_mouse_button_down_event(md)

        assert order == ["generic", "right"]

    def test_drag_drop_lifecycle_middle(self, mock_pygame_patches):
        """Middle button drag/drop lifecycle triggers generic drag/drop."""
        from glitchygames.events.mouse import MouseEventManager

        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_drag_event = Mock(return_value=True)
        scene.on_mouse_drop_event = Mock(return_value=True)
        scene.on_middle_mouse_button_down_event = Mock(return_value=True)
        scene.on_middle_mouse_button_up_event = Mock(return_value=True)
        scene.on_mouse_button_down_event = Mock(return_value=True)
        scene.on_mouse_button_up_event = Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        with patch("glitchygames.events.mouse.collided_sprites", return_value=[]):
            down = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=2)
            motion = HashableEvent(pygame.MOUSEMOTION, pos=(6, 6), rel=(1, 1), buttons=(0, 1, 0))
            up = HashableEvent(pygame.MOUSEBUTTONUP, pos=(7, 7), button=2)
            manager.on_mouse_button_down_event(down)
            manager.on_mouse_motion_event(motion)
            manager.on_mouse_button_up_event(up)

        scene.on_middle_mouse_button_down_event.assert_called_once()
        scene.on_middle_mouse_button_up_event.assert_called_once()
        scene.on_mouse_drag_event.assert_called()
        scene.on_mouse_drop_event.assert_called()

    def test_drag_drop_lifecycle_right(self, mock_pygame_patches):
        """Right button drag/drop lifecycle triggers generic drag/drop."""
        from glitchygames.events.mouse import MouseEventManager

        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_drag_event = Mock(return_value=True)
        scene.on_mouse_drop_event = Mock(return_value=True)
        scene.on_right_mouse_button_down_event = Mock(return_value=True)
        scene.on_right_mouse_button_up_event = Mock(return_value=True)
        scene.on_mouse_button_down_event = Mock(return_value=True)
        scene.on_mouse_button_up_event = Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        with patch("glitchygames.events.mouse.collided_sprites", return_value=[]):
            down = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=3)
            motion = HashableEvent(pygame.MOUSEMOTION, pos=(6, 6), rel=(1, 1), buttons=(0, 0, 1))
            up = HashableEvent(pygame.MOUSEBUTTONUP, pos=(7, 7), button=3)
            manager.on_mouse_button_down_event(down)
            manager.on_mouse_motion_event(motion)
            manager.on_mouse_button_up_event(up)

        scene.on_right_mouse_button_down_event.assert_called_once()
        scene.on_right_mouse_button_up_event.assert_called_once()
        scene.on_mouse_drag_event.assert_called()
        scene.on_mouse_drop_event.assert_called()

    def test_button4_5_scroll_mapping_on_mousedown(self, mock_pygame_patches):
        """Legacy scroll buttons 4/5 should route to scroll up/down handlers."""
        from glitchygames.events.mouse import MouseEventManager

        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_scroll_up_event = Mock(return_value=True)
        scene.on_mouse_scroll_down_event = Mock(return_value=True)
        scene.on_mouse_button_down_event = Mock(return_value=True)

        manager = MouseEventManager(game=scene)
        with patch("glitchygames.events.mouse.collided_sprites", return_value=[]):
            btn4 = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(0, 0), button=4)
            btn5 = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(0, 0), button=5)
            manager.on_mouse_button_down_event(btn4)
            manager.on_mouse_button_down_event(btn5)

        scene.on_mouse_scroll_down_event.assert_called_once()  # button 4 maps to scroll down in code
        scene.on_mouse_scroll_up_event.assert_called_once()    # button 5 maps to scroll up in code

    def test_focus_enter_unfocus_sequence_updates_state(self, mock_pygame_patches):
        """Entering focus should unfocus old, set current to new, and call handlers."""
        from glitchygames.events.mouse import MouseEventManager

        scene = MockFactory.create_event_test_scene_mock()
        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        old_target = Mock()
        new_target = Mock()

        # Seed current focus
        proxy.current_focus = old_target
        event = HashableEvent(pygame.MOUSEMOTION, pos=(0, 0), rel=(0, 0))

        proxy.on_mouse_focus_event(event, entering_focus=new_target)

        # Old target should get unfocus
        old_target.on_mouse_unfocus_event.assert_called_once_with(event)
        # New target should get focus with current_focus passed
        new_target.on_mouse_focus_event.assert_called_once()
        # State updated
        assert proxy.current_focus is new_target
        assert proxy.previous_focus is old_target

    def test_unfocus_clears_current_and_sets_previous(self, mock_pygame_patches):
        """Unfocus should call target unfocus, clear current, and record previous."""
        from glitchygames.events.mouse import MouseEventManager

        scene = MockFactory.create_event_test_scene_mock()
        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        target = Mock()
        proxy.current_focus = target
        event = HashableEvent(pygame.MOUSEMOTION, pos=(0, 0), rel=(0, 0))

        proxy.on_mouse_unfocus_event(event, leaving_focus=target)

        target.on_mouse_unfocus_event.assert_called_once_with(event)
        assert proxy.current_focus is None
        assert proxy.previous_focus is target

    def test_unfocus_no_target_is_noop(self, mock_pygame_patches):
        """Unfocus with None should not crash or change state significantly."""
        from glitchygames.events.mouse import MouseEventManager

        scene = MockFactory.create_event_test_scene_mock()
        manager = MouseEventManager(game=scene)
        proxy = manager.proxies[0]

        proxy.current_focus = None
        event = HashableEvent(pygame.MOUSEMOTION, pos=(0, 0), rel=(0, 0))

        # Should not raise
        proxy.on_mouse_unfocus_event(event, leaving_focus=None)

        assert proxy.current_focus is None

    def test_mouse_wheel_event_routes(self, mock_pygame_patches):
        """Wheel events should route to scene.on_mouse_wheel_event."""
        from glitchygames.events.mouse import MouseEventManager

        scene = MockFactory.create_event_test_scene_mock()
        scene.on_mouse_wheel_event = Mock(return_value=True)

        manager = MouseEventManager(game=scene)

        # pygame.MOUSEWHEEL delivers x,y deltas
        event = HashableEvent(pygame.MOUSEWHEEL, x=0, y=1)
        manager.on_mouse_wheel_event(event)
        scene.on_mouse_wheel_event.assert_called_once_with(event)

    def test_drag_drop_lifecycle_left(self, mock_pygame_patches):
        """Down -> motion -> up should trigger drag then drop lifecycle."""
        from glitchygames.events.mouse import MouseEventManager

        scene = MockFactory.create_event_test_scene_mock()

        # Track calls to generic drag/drop (MouseEventManager emits generic drag/drop)
        scene.on_mouse_drag_event = Mock(return_value=True)
        scene.on_mouse_drop_event = Mock(return_value=True)
        scene.on_left_mouse_button_down_event = Mock(return_value=True)
        scene.on_left_mouse_button_up_event = Mock(return_value=True)
        scene.on_mouse_button_down_event = Mock(return_value=True)
        scene.on_mouse_button_up_event = Mock(return_value=True)

        manager = MouseEventManager(game=scene)

        with patch("glitchygames.events.mouse.collided_sprites", return_value=[]):
            down = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(5, 5), button=1)
            motion = HashableEvent(pygame.MOUSEMOTION, pos=(6, 6), rel=(1, 1), buttons=(1, 0, 0))
            up = HashableEvent(pygame.MOUSEBUTTONUP, pos=(7, 7), button=1)

            manager.on_mouse_button_down_event(down)
            manager.on_mouse_motion_event(motion)
            manager.on_mouse_button_up_event(up)

        # Specifics called
        scene.on_left_mouse_button_down_event.assert_called_once()
        scene.on_left_mouse_button_up_event.assert_called_once()
        # Generic drag and drop called
        scene.on_mouse_drag_event.assert_called()
        scene.on_mouse_drop_event.assert_called()
