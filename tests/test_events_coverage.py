"""Test coverage for missing events module functionality.

This module tests the unhandled_event function which is crucial for
debugging and error handling in the events system. The function handles
cases where events are not properly handled by any event handlers,
providing debug logging and optional system exit functionality.

The unhandled_event function is essential for:
1. Debug logging of unhandled events
2. Error handling when game options are missing
3. Optional system exit for unhandled events
4. Comprehensive event system coverage

Without these tests, the events module coverage remains incomplete
as these error handling and debug paths are not exercised.
"""

from unittest.mock import Mock, patch

import pygame
from glitchygames.events import unhandled_event


class TestEventsCoverage:
    """Test coverage for missing events functionality."""

    def test_unhandled_event_debug_events_true(self):  # noqa: PLR6301
        """Test unhandled_event with debug_events=True."""
        mock_game = Mock()
        mock_game.options = {"debug_events": True, "no_unhandled_events": False}

        mock_event = Mock()
        mock_event.type = pygame.KEYDOWN

        with patch("pygame.event.event_name", return_value="KEYDOWN") as mock_event_name, \
             patch("glitchygames.events.LOG") as mock_log:

            unhandled_event(mock_game, mock_event, "arg1", kwarg1="value1")

            mock_event_name.assert_called_once_with(pygame.KEYDOWN)
            mock_log.error.assert_called_once()
            # Check that the log message contains the expected content
            call_args = mock_log.error.call_args[0][0]
            assert "Unhandled Event: args: KEYDOWN" in call_args
            assert "arg1" in call_args
            assert "'kwarg1': 'value1'" in call_args

    def test_unhandled_event_debug_events_none(self):  # noqa: PLR6301
        """Test unhandled_event with debug_events=None."""
        mock_game = Mock()
        mock_game.options = {"debug_events": None, "no_unhandled_events": False}

        mock_event = Mock()
        mock_event.type = pygame.KEYDOWN

        with patch("glitchygames.events.LOG") as mock_log:
            unhandled_event(mock_game, mock_event)

            mock_log.error.assert_called_once_with(
                "Error: debug_events is missing from the game options. This shouldn't be possible."
            )

    def test_unhandled_event_no_unhandled_events_true(self):  # noqa: PLR6301
        """Test unhandled_event with no_unhandled_events=True."""
        mock_game = Mock()
        mock_game.options = {"debug_events": False, "no_unhandled_events": True}

        mock_event = Mock()
        mock_event.type = pygame.KEYDOWN

        with patch("pygame.event.event_name", return_value="KEYDOWN") as mock_event_name, \
             patch("glitchygames.events.LOG") as mock_log, \
             patch("sys.exit") as mock_exit:

            unhandled_event(mock_game, mock_event, "arg1", kwarg1="value1")

            mock_event_name.assert_called_once_with(pygame.KEYDOWN)
            mock_log.error.assert_called_once()
            mock_exit.assert_called_once_with(-1)

    def test_unhandled_event_no_unhandled_events_none(self):  # noqa: PLR6301
        """Test unhandled_event with no_unhandled_events=None."""
        mock_game = Mock()
        mock_game.options = {"debug_events": False, "no_unhandled_events": None}

        mock_event = Mock()
        mock_event.type = pygame.KEYDOWN

        with patch("glitchygames.events.LOG") as mock_log:
            unhandled_event(mock_game, mock_event)

            mock_log.error.assert_called_once_with(
                "Error: no_unhandled_events is missing from the game options. "
                "This shouldn't be possible."
            )

    def test_unhandled_event_both_false(self):  # noqa: PLR6301
        """Test unhandled_event with both options False."""
        mock_game = Mock()
        mock_game.options = {"debug_events": False, "no_unhandled_events": False}

        mock_event = Mock()
        mock_event.type = pygame.KEYDOWN

        with patch("glitchygames.events.LOG") as mock_log:
            unhandled_event(mock_game, mock_event)

            # Should not log anything when both are False
            mock_log.error.assert_not_called()

    def test_unhandled_event_both_true(self):  # noqa: PLR6301
        """Test unhandled_event with both options True."""
        mock_game = Mock()
        mock_game.options = {"debug_events": True, "no_unhandled_events": True}

        mock_event = Mock()
        mock_event.type = pygame.KEYDOWN

        with patch("pygame.event.event_name", return_value="KEYDOWN"), \
             patch("glitchygames.events.LOG") as mock_log, \
             patch("sys.exit") as mock_exit:

            unhandled_event(mock_game, mock_event, "arg1", kwarg1="value1")

            # Should log debug message AND exit (logs twice: once for debug_events,
            # once for no_unhandled_events)
            expected_call_count = 2
            assert mock_log.error.call_count == expected_call_count
            mock_exit.assert_called_once_with(-1)
