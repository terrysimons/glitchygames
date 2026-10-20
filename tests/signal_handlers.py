"""Keep signal handlers from leaking between tests (used by the autouse fixture in conftest.py).

``GameEngine.start`` installs ``exit_on_signal`` and ``_shutdown`` restores the defaults; a test
that mocks ``_shutdown`` (or Bitmappy's ``main``, which installs its own) would otherwise leave
a handler on the worker for every later test, so a stray SIGTERM would raise SystemExit
somewhere unrelated.
"""

from __future__ import annotations

import contextlib
import signal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from types import FrameType

# The signals the engine (or a game) may claim; SIGHUP is Unix only and SIGBREAK Windows only
ISOLATED_SIGNAL_NAMES = ('SIGINT', 'SIGTERM', 'SIGHUP', 'SIGBREAK')

type SignalHandler = Callable[[int, FrameType | None], object] | int | signal.Handlers | None


@contextlib.contextmanager
def preserved_signal_handlers() -> Generator[dict[int, SignalHandler]]:
    """Put back each of ``ISOLATED_SIGNAL_NAMES``' handlers (where the platform has it) on exit.

    Yields:
        The saved handlers, by signal number.

    """
    saved_handlers: dict[int, SignalHandler] = {
        getattr(signal, name): signal.getsignal(getattr(signal, name))
        for name in ISOLATED_SIGNAL_NAMES
        if hasattr(signal, name)
    }
    try:
        yield saved_handlers
    finally:
        for signal_number, handler in saved_handlers.items():
            # None: a handler not set from Python; it cannot be put back, so leave it alone
            if handler is not None:
                signal.signal(signal_number, handler)
