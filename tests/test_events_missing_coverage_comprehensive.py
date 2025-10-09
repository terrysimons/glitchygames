"""Comprehensive test coverage for missing Events module functionality."""

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


class TestEventsMissingCoverageComprehensive(unittest.TestCase):
    """Comprehensive test coverage for missing Events module functionality."""

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

    def test_event_manager_getattr_exception_handling(self):
        """Test EventManager.__getattr__ exception handling (lines 287-289)."""
        # Create EventManager with empty proxies list
        event_manager = EventManager()
        event_manager.proxies = []
        event_manager.log = Mock()
        
        # Test that AttributeError is raised when no proxies exist
        with self.assertRaises(AttributeError) as context:
            _ = event_manager.non_existent_method
        
        self.assertIn("No proxies for", str(context.exception))
        self.assertTrue(event_manager.log.exception.called)

    def test_event_manager_getattr_with_proxy_exception(self):
        """Test EventManager.__getattr__ with proxy that raises AttributeError."""
        # Create EventManager with proxy that raises AttributeError
        event_manager = EventManager()
        mock_proxy = Mock()
        mock_proxy.side_effect = AttributeError("Proxy method not found")
        event_manager.proxies = [mock_proxy]
        event_manager.log = Mock()
        
        # Test that the exception is logged and re-raised
        with self.assertRaises(AttributeError):
            _ = event_manager.test_method
        
        self.assertTrue(event_manager.log.exception.called)

    def test_hashable_event_init_with_type(self):
        """Test HashableEvent.__init__ with type parameter."""
        # Test HashableEvent initialization with type
        event = HashableEvent(type=1, data="test")
        self.assertEqual(event["type"], 1)
        self.assertEqual(event["data"], "test")

    def test_hashable_event_init_without_type(self):
        """Test HashableEvent.__init__ without type parameter."""
        # Test HashableEvent initialization without type (should raise TypeError)
        with self.assertRaises(TypeError):
            HashableEvent()

    def test_hashable_event_delattr(self):
        """Test HashableEvent.__delattr__ method."""
        event = HashableEvent(type=1, data="test")
        del event["data"]
        self.assertNotIn("data", event)

    def test_hashable_event_getattr(self):
        """Test HashableEvent.__getattr__ method."""
        event = HashableEvent(type=1, data="test")
        self.assertEqual(event.data, "test")

    def test_hashable_event_setattr(self):
        """Test HashableEvent.__setattr__ method."""
        event = HashableEvent(type=1)
        event.new_attr = "new_value"
        self.assertEqual(event.new_attr, "new_value")

    def test_hashable_event_eq(self):
        """Test HashableEvent.__eq__ method."""
        event1 = HashableEvent(type=1, data="test")
        event2 = HashableEvent(type=1, data="test")
        event3 = HashableEvent(type=2, data="test")
        
        self.assertEqual(event1, event2)
        self.assertNotEqual(event1, event3)

    def test_hashable_event_ne(self):
        """Test HashableEvent.__ne__ method."""
        event1 = HashableEvent(type=1, data="test")
        event2 = HashableEvent(type=2, data="test")
        
        self.assertNotEqual(event1, event2)

    def test_hashable_event_hash(self):
        """Test HashableEvent.__hash__ method."""
        event = HashableEvent(type=1, data="test")
        # Hash should be consistent
        hash1 = hash(event)
        hash2 = hash(event)
        self.assertEqual(hash1, hash2)

    def test_hashable_event_str(self):
        """Test HashableEvent.__str__ method."""
        event = HashableEvent(type=1, data="test")
        str_repr = str(event)
        self.assertIsInstance(str_repr, str)
        self.assertIn("HashableEvent", str_repr)

    def test_hashable_event_repr(self):
        """Test HashableEvent.__repr__ method."""
        event = HashableEvent(type=1, data="test")
        repr_str = repr(event)
        self.assertIsInstance(repr_str, str)
        self.assertIn("HashableEvent", repr_str)

    def test_resource_manager_init(self):
        """Test ResourceManager.__init__ method."""
        mock_game = Mock()
        resource_manager = ResourceManager(game=mock_game)
        self.assertEqual(resource_manager.game, mock_game)

    def test_resource_manager_init_without_game(self):
        """Test ResourceManager.__init__ without game parameter."""
        with self.assertRaises(TypeError):
            ResourceManager()

    def test_resource_manager_register(self):
        """Test ResourceManager.register method."""
        mock_game = Mock()
        resource_manager = ResourceManager(game=mock_game)
        
        # Test registering a resource
        resource_manager.register("test_resource", Mock())
        self.assertIn("test_resource", resource_manager._resources)

    def test_resource_manager_process_events(self):
        """Test ResourceManager.process_events method."""
        mock_game = Mock()
        resource_manager = ResourceManager(game=mock_game)
        
        # Test processing events
        resource_manager.process_events()
        # Should not raise any exceptions

    def test_resource_manager_cleanup(self):
        """Test ResourceManager.cleanup method."""
        mock_game = Mock()
        resource_manager = ResourceManager(game=mock_game)
        
        # Test cleanup
        resource_manager.cleanup()
        # Should not raise any exceptions

    def test_dump_cache_info_with_func(self):
        """Test dump_cache_info function with func parameter."""
        mock_func = Mock()
        mock_func.cache_info.return_value = Mock()
        
        # Test dump_cache_info with func
        dump_cache_info(mock_func)
        mock_func.cache_info.assert_called_once()

    def test_dump_cache_info_with_all_parameters(self):
        """Test dump_cache_info function with all parameters."""
        mock_func = Mock()
        mock_func.cache_info.return_value = Mock()
        
        # Test dump_cache_info with all parameters
        dump_cache_info(
            mock_func, 
            file=Mock(), 
            sep=",", 
            end="\n", 
            flush=True
        )
        mock_func.cache_info.assert_called_once()

    def test_dump_cache_info_with_file(self):
        """Test dump_cache_info function with file parameter."""
        mock_func = Mock()
        mock_func.cache_info.return_value = Mock()
        mock_file = Mock()
        
        dump_cache_info(mock_func, file=mock_file)
        mock_func.cache_info.assert_called_once()

    def test_dump_cache_info_with_sep(self):
        """Test dump_cache_info function with sep parameter."""
        mock_func = Mock()
        mock_func.cache_info.return_value = Mock()
        
        dump_cache_info(mock_func, sep="|")
        mock_func.cache_info.assert_called_once()

    def test_dump_cache_info_with_end(self):
        """Test dump_cache_info function with end parameter."""
        mock_func = Mock()
        mock_func.cache_info.return_value = Mock()
        
        dump_cache_info(mock_func, end="\r\n")
        mock_func.cache_info.assert_called_once()

    def test_dump_cache_info_with_flush(self):
        """Test dump_cache_info function with flush parameter."""
        mock_func = Mock()
        mock_func.cache_info.return_value = Mock()
        
        dump_cache_info(mock_func, flush=True)
        mock_func.cache_info.assert_called_once()

    def test_supported_events_with_regex_pattern(self):
        """Test supported_events function with regex pattern."""
        # Test with regex pattern
        events = supported_events(pattern=".*KEY.*")
        self.assertIsInstance(events, list)

    def test_supported_events_with_specific_pattern(self):
        """Test supported_events function with specific pattern."""
        # Test with specific pattern
        events = supported_events(pattern="KEYDOWN")
        self.assertIsInstance(events, list)

    def test_supported_events_with_default_pattern(self):
        """Test supported_events function with default pattern."""
        # Test with default pattern
        events = supported_events()
        self.assertIsInstance(events, list)

    def test_unhandled_event_with_debug_events_true(self):
        """Test unhandled_event function with debug_events=True."""
        mock_logger = Mock()
        
        with patch("glitchygames.events.logger", mock_logger):
            unhandled_event(Mock(), debug_events=True)
            mock_logger.debug.assert_called()

    def test_unhandled_event_with_debug_events_false(self):
        """Test unhandled_event function with debug_events=False."""
        mock_logger = Mock()
        
        with patch("glitchygames.events.logger", mock_logger):
            unhandled_event(Mock(), debug_events=False)
            # Should not call debug

    def test_unhandled_event_with_no_unhandled_events_true(self):
        """Test unhandled_event function with no_unhandled_events=True."""
        mock_logger = Mock()
        
        with patch("glitchygames.events.logger", mock_logger):
            unhandled_event(Mock(), no_unhandled_events=True)
            # Should not log anything

    def test_unhandled_event_with_no_unhandled_events_false(self):
        """Test unhandled_event function with no_unhandled_events=False."""
        mock_logger = Mock()
        
        with patch("glitchygames.events.logger", mock_logger):
            unhandled_event(Mock(), no_unhandled_events=False)
            mock_logger.error.assert_called()

    def test_unhandled_event_with_both_options_missing(self):
        """Test unhandled_event function with both options missing."""
        mock_logger = Mock()
        
        with patch("glitchygames.events.logger", mock_logger):
            unhandled_event(Mock())
            mock_logger.error.assert_called()

    def test_unhandled_event_with_missing_debug_events(self):
        """Test unhandled_event function with missing debug_events."""
        mock_logger = Mock()
        
        with patch("glitchygames.events.logger", mock_logger):
            unhandled_event(Mock(), no_unhandled_events=True)
            # Should not log anything

    def test_unhandled_event_with_missing_no_unhandled_events(self):
        """Test unhandled_event function with missing no_unhandled_events."""
        mock_logger = Mock()
        
        with patch("glitchygames.events.logger", mock_logger):
            unhandled_event(Mock(), debug_events=True)
            mock_logger.debug.assert_called()

    def test_unhandled_event_with_missing_options(self):
        """Test unhandled_event function with missing options."""
        mock_logger = Mock()
        
        with patch("glitchygames.events.logger", mock_logger):
            unhandled_event(Mock())
            mock_logger.error.assert_called()


if __name__ == "__main__":
    unittest.main()
