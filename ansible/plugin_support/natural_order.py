"""Hold results by host and release them host by host in natural order (4gb, 8gb, 16gb).

Plain Python with no Ansible import, so this project's tests run it directly
(tests/test_ansible_natural_order_output.py); ansible/callback_plugins/natural_order.py loads it
by path and feeds it each host's results.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def natural_key(name: str) -> tuple[tuple[int, int | str], ...]:
    """Return a sort key that orders runs of digits by their value: 4gb, 8gb, 16gb.

    Plain sorting compares character by character, so raspberry-pi-5-16gb sorts before
    raspberry-pi-5-8gb ("1" before "8"). Each part is tagged (0 for a number, 1 for text) so a
    number and text in the same place still compare.

    Returns:
        The key.

    """
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part) for part in re.split(r'(\d+)', name) if part
    )


class ResultBuffer:
    """Results held per host, in the order they came, until released."""

    def __init__(self) -> None:
        """Start empty."""
        self._held: dict[str, list[Callable[[], None]]] = {}

    def hold(self, *, host: str, show: Callable[[], None]) -> None:
        """Hold one result: ``show`` prints it when released.

        Args:
            host: The host the result is for.
            show: Prints the result.

        """
        self._held.setdefault(host, []).append(show)

    def release(self) -> None:
        """Print every held result, host by host in natural order, then forget them."""
        held, self._held = self._held, {}
        for host in sorted(held, key=natural_key):
            for show in held[host]:
                show()
