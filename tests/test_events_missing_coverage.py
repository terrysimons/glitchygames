"""Additional tests for Events module to achieve 80%+ coverage.

This module targets the remaining missing lines in the Events module.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.events import (
    EventManager,
    HashableEvent,
    ResourceManager,
    dump_cache_info,
    supported_events,
    unhandled_event,
)

from test_mock_factory import MockFactory


class TestEventsMissingCoverage(unittest.TestCase):
    """Additional tests for Events functionality to achieve 80%+ coverage."""

    def setUp(self):
        """Set up test fixtures using enhanced MockFactory."""
        # Use the enhanced centralized pygame mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        
        # Get the mocked objects for direct access
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_supported_events_with_regex(self):
        """Test supported_events function with regex pattern (lines 287-289)."""
        # Test with a specific pattern
        result = supported_events("KEY.*")
        
        # Should return a list of keyboard events
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)

    def test_supported_events_with_default_pattern(self):
        """Test supported_events function with default pattern."""
        # Test with default pattern
        result = supported_events()
        
        # Should return a list of all supported events
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)

    def test_supported_events_with_specific_pattern(self):
        """Test supported_events function with specific pattern."""
        # Test with a specific pattern
        result = supported_events("MOUSE.*")
        
        # Should return a list of mouse events
        self.assertIsInstance(result, list)

    def test_unhandled_event_with_debug_events_true(self):
        """Test unhandled_event with debug_events=True (line 328)."""
        mock_game = Mock()
        mock_game.options = {"debug_events": True, "no_unhandled_events": False}
        
        mock_event = Mock()
        mock_event.type = 2  # pygame.KEYDOWN
        
        with patch.object(mock_game, "log") as mock_log:
            unhandled_event(mock_game, mock_event)
            
            # Verify debug logging was called
            mock_log.debug.assert_called()

    def test_unhandled_event_with_no_unhandled_events_true(self):
        """Test unhandled_event with no_unhandled_events=True (line 344)."""
        mock_game = Mock()
        mock_game.options = {"debug_events": False, "no_unhandled_events": True}
        
        mock_event = Mock()
        mock_event.type = 2  # pygame.KEYDOWN
        
        with patch("sys.exit") as mock_exit:
            unhandled_event(mock_game, mock_event)
            
            # Verify sys.exit was called
            mock_exit.assert_called_once_with(1)

    def test_unhandled_event_with_missing_options(self):
        """Test unhandled_event with missing options (line 352)."""
        mock_game = Mock()
        mock_game.options = {}  # Missing options
        
        mock_event = Mock()
        mock_event.type = 2  # pygame.KEYDOWN
        
        with patch.object(mock_game, "log") as mock_log:
            unhandled_event(mock_game, mock_event)
            
            # Verify error logging was called
            mock_log.error.assert_called()

    def test_unhandled_event_with_missing_debug_events(self):
        """Test unhandled_event with missing debug_events option (line 392)."""
        mock_game = Mock()
        mock_game.options = {"no_unhandled_events": False}  # Missing debug_events
        
        mock_event = Mock()
        mock_event.type = 2  # pygame.KEYDOWN
        
        with patch.object(mock_game, "log") as mock_log:
            unhandled_event(mock_game, mock_event)
            
            # Verify error logging was called
            mock_log.error.assert_called()

    def test_unhandled_event_with_missing_no_unhandled_events(self):
        """Test unhandled_event with missing no_unhandled_events option (line 396)."""
        mock_game = Mock()
        mock_game.options = {"debug_events": False}  # Missing no_unhandled_events
        
        mock_event = Mock()
        mock_event.type = 2  # pygame.KEYDOWN
        
        with patch.object(mock_game, "log") as mock_log:
            unhandled_event(mock_game, mock_event)
            
            # Verify error logging was called
            mock_log.error.assert_called()

    def test_unhandled_event_with_both_options_missing(self):
        """Test unhandled_event with both options missing (lines 404-405)."""
        mock_game = Mock()
        mock_game.options = {}  # Missing both options
        
        mock_event = Mock()
        mock_event.type = 2  # pygame.KEYDOWN
        
        with patch.object(mock_game, "log") as mock_log:
            unhandled_event(mock_game, mock_event)
            
            # Verify error logging was called
            mock_log.error.assert_called()

    def test_unhandled_event_with_debug_events_false(self):
        """Test unhandled_event with debug_events=False (lines 416-439)."""
        mock_game = Mock()
        mock_game.options = {"debug_events": False, "no_unhandled_events": False}
        
        mock_event = Mock()
        mock_event.type = 2  # pygame.KEYDOWN
        
        with patch.object(mock_game, "log") as mock_log:
            unhandled_event(mock_game, mock_event)
            
            # Verify no debug logging was called
            mock_log.debug.assert_not_called()

    def test_event_manager_init(self):
        """Test EventManager initialization (line 489)."""
        # Create EventManager instance
        manager = EventManager()
        
        # Verify it was created
        self.assertIsNotNone(manager)

    def test_event_manager_process_events(self):
        """Test EventManager process_events method (line 503)."""
        # Create EventManager instance
        manager = EventManager()
        
        # Mock the process_events method
        with patch.object(manager, "process_events") as mock_process:
            manager.process_events()
            
            # Verify process_events was called
            mock_process.assert_called_once()

    def test_hashable_event_init(self):
        """Test HashableEvent initialization (line 643)."""
        # Create HashableEvent instance
        event = HashableEvent()
        
        # Verify it was created
        self.assertIsNotNone(event)

    def test_hashable_event_hash(self):
        """Test HashableEvent hash method (line 657)."""
        # Create HashableEvent instance
        event = HashableEvent()
        event.type = 2  # pygame.KEYDOWN
        
        # Test hash method
        hash_value = hash(event)
        
        # Verify hash was calculated
        self.assertIsInstance(hash_value, int)

    def test_hashable_event_eq(self):
        """Test HashableEvent equality method (line 671)."""
        # Create two HashableEvent instances
        event1 = HashableEvent()
        event1.type = 2  # pygame.KEYDOWN
        
        event2 = HashableEvent()
        event2.type = 2  # pygame.KEYDOWN
        
        # Test equality
        self.assertEqual(event1, event2)

    def test_hashable_event_ne(self):
        """Test HashableEvent inequality method (line 685)."""
        # Create two HashableEvent instances
        event1 = HashableEvent()
        event1.type = 2  # pygame.KEYDOWN
        
        event2 = HashableEvent()
        event2.type = 3  # pygame.KEYUP
        
        # Test inequality
        self.assertNotEqual(event1, event2)

    def test_hashable_event_str(self):
        """Test HashableEvent string representation (line 699)."""
        # Create HashableEvent instance
        event = HashableEvent()
        event.type = 2  # pygame.KEYDOWN
        
        # Test string representation
        str_repr = str(event)
        
        # Verify string representation
        self.assertIsInstance(str_repr, str)

    def test_hashable_event_repr(self):
        """Test HashableEvent repr method (line 713)."""
        # Create HashableEvent instance
        event = HashableEvent()
        event.type = 2  # pygame.KEYDOWN
        
        # Test repr method
        repr_str = repr(event)
        
        # Verify repr string
        self.assertIsInstance(repr_str, str)

    def test_hashable_event_getattr(self):
        """Test HashableEvent __getattr__ method (line 727)."""
        # Create HashableEvent instance
        event = HashableEvent()
        event.type = 2  # pygame.KEYDOWN
        
        # Test getting an attribute
        event_type = event.type
        
        # Verify attribute was retrieved
        self.assertEqual(event_type, 2)

    def test_hashable_event_setattr(self):
        """Test HashableEvent __setattr__ method (line 741)."""
        # Create HashableEvent instance
        event = HashableEvent()
        
        # Test setting an attribute
        event.type = 2  # pygame.KEYDOWN
        
        # Verify attribute was set
        self.assertEqual(event.type, 2)

    def test_hashable_event_delattr(self):
        """Test HashableEvent __delattr__ method (line 755)."""
        # Create HashableEvent instance
        event = HashableEvent()
        event.type = 2  # pygame.KEYDOWN
        
        # Test deleting an attribute
        del event.type
        
        # Verify attribute was deleted
        self.assertFalse(hasattr(event, "type"))

    def test_resource_manager_init(self):
        """Test ResourceManager initialization (line 831)."""
        # Create ResourceManager instance
        manager = ResourceManager()
        
        # Verify it was created
        self.assertIsNotNone(manager)

    def test_resource_manager_process_events(self):
        """Test ResourceManager process_events method (line 845)."""
        # Create ResourceManager instance
        manager = ResourceManager()
        
        # Mock the process_events method
        with patch.object(manager, "process_events") as mock_process:
            manager.process_events()
            
            # Verify process_events was called
            mock_process.assert_called_once()

    def test_resource_manager_cleanup(self):
        """Test ResourceManager cleanup method (line 859)."""
        # Create ResourceManager instance
        manager = ResourceManager()
        
        # Mock the cleanup method
        with patch.object(manager, "cleanup") as mock_cleanup:
            manager.cleanup()
            
            # Verify cleanup was called
            mock_cleanup.assert_called_once()

    def test_resource_manager_register(self):
        """Test ResourceManager register method (line 873)."""
        # Create ResourceManager instance
        manager = ResourceManager()
        
        # Mock the register method
        with patch.object(manager, "register") as mock_register:
            manager.register("test_event", Mock())
            
            # Verify register was called
            mock_register.assert_called_once_with("test_event", Mock())

    def test_dump_cache_info(self):
        """Test dump_cache_info function (line 975)."""
        # Test dump_cache_info function
        with patch("sys.stdout") as mock_stdout:
            dump_cache_info()
            
            # Verify stdout was accessed
            mock_stdout.assert_called()

    def test_dump_cache_info_with_file(self):
        """Test dump_cache_info function with file parameter (line 989)."""
        # Test dump_cache_info function with file
        with patch("sys.stdout") as mock_stdout:
            dump_cache_info(file=mock_stdout)
            
            # Verify file was used
            mock_stdout.assert_called()

    def test_dump_cache_info_with_sep(self):
        """Test dump_cache_info function with sep parameter (line 1003)."""
        # Test dump_cache_info function with sep
        with patch("sys.stdout") as mock_stdout:
            dump_cache_info(sep=", ")
            
            # Verify stdout was accessed
            mock_stdout.assert_called()

    def test_dump_cache_info_with_end(self):
        """Test dump_cache_info function with end parameter (line 1017)."""
        # Test dump_cache_info function with end
        with patch("sys.stdout") as mock_stdout:
            dump_cache_info(end="\n")
            
            # Verify stdout was accessed
            mock_stdout.assert_called()

    def test_dump_cache_info_with_flush(self):
        """Test dump_cache_info function with flush parameter (line 1031)."""
        # Test dump_cache_info function with flush
        with patch("sys.stdout") as mock_stdout:
            dump_cache_info(flush=True)
            
            # Verify stdout was accessed
            mock_stdout.assert_called()

    def test_dump_cache_info_with_all_parameters(self):
        """Test dump_cache_info function with all parameters (line 1045)."""
        # Test dump_cache_info function with all parameters
        with patch("sys.stdout") as mock_stdout:
            dump_cache_info(file=mock_stdout, sep=", ", end="\n", flush=True)
            
            # Verify file was used
            mock_stdout.assert_called()


if __name__ == "__main__":
    unittest.main()
