"""Read a mocked logger's calls as the messages logging would print.

The package logs lazily (`log.info('Loaded %s frames', count)`), so a mocked logger's call holds
the format string and its arguments; a test asserting on the text formats them first, as logging
does (only when there are arguments, so a bare `%` stays as written).
"""

from __future__ import annotations

from typing import Protocol


class LoggedCall(Protocol):
    """One recorded call of a mocked logger method (pytest-mock's ``call_args`` entries)."""

    @property
    def args(self) -> tuple[object, ...]:
        """The call's positional arguments: the format string, then its values."""
        ...


def logged_message(call: LoggedCall) -> str:
    """Return the message one mocked logging call would print.

    Args:
        call: A call of a mocked logger method (an entry of its ``call_args_list``).

    Returns:
        str: The formatted message.

    """
    message, *arguments = call.args
    return str(message) % tuple(arguments) if arguments else str(message)


def logged_messages(calls: list[LoggedCall]) -> list[str]:
    """Return the messages a mocked logger method's calls would print, in order.

    Args:
        calls: The method's ``call_args_list``.

    Returns:
        list[str]: The formatted messages.

    """
    return [logged_message(call) for call in calls]
