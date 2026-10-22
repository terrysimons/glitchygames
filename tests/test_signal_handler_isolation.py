"""Signal handlers never leak from one test into the next (tests/signal_handlers.py)."""

import signal

from tests.signal_handlers import ISOLATED_SIGNAL_NAMES, preserved_signal_handlers


def stand_in_handler(_signal_number: int, _frame: object) -> None:
    """A handler a test installs and forgets to remove."""


def test_a_handler_left_installed_is_put_back_on_exit():
    """What a test installs is gone once the block (the autouse fixture) ends."""
    handler_before = signal.getsignal(signal.SIGTERM)
    with preserved_signal_handlers():
        signal.signal(signal.SIGTERM, stand_in_handler)
    assert signal.getsignal(signal.SIGTERM) == handler_before


def test_only_signals_this_platform_has_are_preserved():
    """SIGHUP and SIGBREAK are looked up, as each exists on one platform only."""
    with preserved_signal_handlers() as saved_handlers:
        pass
    expected = {getattr(signal, name) for name in ISOLATED_SIGNAL_NAMES if hasattr(signal, name)}
    assert set(saved_handlers) == expected
    assert signal.SIGINT in saved_handlers
    assert signal.SIGTERM in saved_handlers
