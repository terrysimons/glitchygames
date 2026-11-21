"""Checks that code relies on, written so they still run under ``python -O``.

``python -O`` strips every ``assert``, so a check written as one is no check at all in an
optimized run, and bandit flags it (B101). Outside tests the engine, its members and its scripts
check with an explicit raise instead (the owner's rule, plans/future-work.md, "Replace ``assert``
outside tests with explicit raises").

``required(value, what=...)`` is the one way to say "this is never None here": it returns the
value, typed without None, or raises ``MissingValueError`` naming what was missing. One line
replaces ``assert value is not None`` and still narrows the type for the type checkers::

    screen = required(self.screen, what='the editor screen')

Any other condition is an explicit ``if ...: raise`` of the error that fits it (``ValueError``
for a bad argument, a module's own error for its own refusals).
"""

from __future__ import annotations


class MissingValueError(RuntimeError):
    """A value the code relies on is None: a bug in the code, not bad input from the user."""


def required[T](value: T | None, *, what: str) -> T:
    """Return a value the code relies on, or raise if it is None.

    Args:
        value: The value, which the caller relies on not being None.
        what: What the value is, for the message (``'the scene manager's game engine'``).

    Returns:
        The value, typed without None.

    Raises:
        MissingValueError: If the value is None, with the message ``'<what> is missing'``.

    """
    if value is None:
        message = f'{what} is missing'
        raise MissingValueError(message)
    return value
