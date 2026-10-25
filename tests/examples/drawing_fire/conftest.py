"""Fixtures shared by the Drawing Fire tests."""

import pygame
import pytest


@pytest.fixture(autouse=True)
def empty_event_queue_afterwards():
    """Clear SDL's event queue after each test.

    The scene posts its own GAMEEVENTs (a soldier killed, a seat changed) as it ticks, and most
    tests never pump them. Left queued, they would be pumped by a later test on the same worker:
    one recording a session would record them as its own internal events, and its replay, which
    never posts them, would diverge ("missing internal event").

    Yields:
        Nothing: the test runs, then the queue is cleared.

    """
    yield
    if pygame.display.get_init():
        pygame.event.clear()
