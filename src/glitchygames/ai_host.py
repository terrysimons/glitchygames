"""The AI's layer around the game: ``GameHost``'s doors, with AI input added.

``GameHost`` is the wrapper around every live run, and ``host.py`` doesn't change for AI. This is
a subclass of its doors, built instead of ``HostSources`` for a run that has AI (``create_link``).
A run without AI never imports this module, so it adds nothing to that run's frames.

These doors sit beneath the recorder, so an AI proposal added here is recorded as outside input,
and a replay serves it with no AI, no model and no service (probed on Bitmappy,
plans/lucid-circuit.md).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Self, override

import pygame

from glitchygames.host import HostSources

if TYPE_CHECKING:
    from glitchygames.ai_link import AiLink
    from glitchygames.replay.driver import FrameOverlay
    from glitchygames.sources import EngineSources

LOG = logging.getLogger('game.ai_host')

# What a proposal may post, for now. A service, or anything answering on its port, gets no more than
# this: other event types could quit the game or reach the event system's internals
ALLOWED_INPUT_EVENT_TYPES = frozenset({pygame.KEYDOWN, pygame.KEYUP})


def input_event_from(*, message: dict[str, Any]) -> pygame.event.Event | None:
    """Build the input event a message proposes, refusing anything else.

    Args:
        message: A message from the service.

    Returns:
        The event, or None if the message isn't a valid input proposal.

    """
    if message.get('type') != 'input_event':
        LOG.debug('Ignoring a message the game has no use for yet: %s', message.get('type'))
        return None
    event_type = message.get('event_type')
    key = message.get('key')
    scancode = message.get('scancode')
    if (
        event_type not in ALLOWED_INPUT_EVENT_TYPES
        or not isinstance(event_type, int)
        or type(key) is not int
        or type(scancode) is not int
    ):
        LOG.warning('Refusing an invalid input proposal from the AI service')
        return None
    return pygame.event.Event(
        event_type, key=key, scancode=scancode, mod=0, unicode='', window=None
    )


class AiHostSources(HostSources):
    """``HostSources``, with what the AI proposes added to each event batch."""

    def __init__(
        self: Self, *, inner: EngineSources, link: AiLink, overlay: FrameOverlay | None = None
    ) -> None:
        """Wrap ``inner``.

        Args:
            inner: The doors to read through.
            link: The session with the service.
            overlay: Drawn over each presented frame (never recorded), or None.

        """
        super().__init__(inner=inner, overlay=overlay)
        self.link = link

    @override
    def pump_events(self: Self) -> list[pygame.event.Event]:
        """Return the host's batch, with what the AI proposed since the last one after it.

        Returns:
            The batch, in queue order.

        """
        events = super().pump_events()
        messages = self.link.take_messages()
        if not messages:
            return events
        proposed = [input_event_from(message=message) for message in messages]
        return [*events, *(event for event in proposed if event is not None)]
