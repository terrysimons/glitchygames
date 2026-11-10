"""Who's connected, and stopping the models once nobody is."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

LOG = logging.getLogger(__name__)


class SessionTracker:
    """Counts live game sessions, and shuts down a grace period after the last one closes.

    The grace period keeps a quick relaunch from reloading a model. A crashed game's socket closes
    like any other, so a crash can't leave the models holding memory.
    """

    def __init__(
        self, *, grace_seconds: float, on_last_session_gone: Callable[[], Awaitable[None]]
    ) -> None:
        """Start with no sessions.

        Args:
            grace_seconds: How long after the last session closes to shut down.
            on_last_session_gone: What shutting down does.

        """
        self.grace_seconds = grace_seconds
        self.on_last_session_gone = on_last_session_gone
        self.count = 0
        self.shutdown_task: asyncio.Task[None] | None = None

    def opened(self) -> None:
        """Record a new session, cancelling any pending shutdown."""
        self.count += 1
        if self.shutdown_task is not None:
            self.shutdown_task.cancel()
            self.shutdown_task = None

    def closed(self) -> None:
        """Record a closed session, and schedule the shutdown if it was the last."""
        self.count -= 1
        if self.count == 0:
            self.shutdown_task = asyncio.create_task(self._shut_down_after_grace())

    async def _shut_down_after_grace(self) -> None:
        """Wait out the grace period, then shut down."""
        await asyncio.sleep(self.grace_seconds)
        LOG.info('The last session closed %s s ago: stopping the models', self.grace_seconds)
        await self.on_last_session_gone()
