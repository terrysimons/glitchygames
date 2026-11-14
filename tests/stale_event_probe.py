"""Triage probe: log every test that starts or ends with a custom event in SDL's queue.

Built for BUGS.md #276 (a watched replay that diverged at frame 0 once): an earlier run's
custom-type event left queued was taken for the next run's own internal event. Game engine runs
now drop such events at their start (``recording.discard_custom_events_queued_before_the_run``),
so a hit here no longer breaks a run, but it names the test that leaks one.

Opt-in, never loaded by the suite::

    STALE_EVENT_PROBE_LOG=stale-events.jsonl uv run pytest -p tests.stale_event_probe

The probe only peeks: each event it takes out of the queue is posted back, in order. Each hit is
one JSON line in ``STALE_EVENT_PROBE_LOG`` (default ``test-results/stale-event-probe.jsonl``):
the phase (``setup-start`` or ``teardown-end``), the test's node id, and each event's type and
attributes (as reprs). Under xdist every worker appends to the same file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pygame
import pytest

from glitchygames.recording import CUSTOM_EVENT_TYPES

DEFAULT_LOG_PATH = Path('test-results') / 'stale-event-probe.jsonl'


def _queued_custom_events() -> list[tuple[int, dict[str, str]]]:
    """Return the custom events in SDL's queue, leaving the queue as it was.

    Returns:
        (type, attributes as reprs) of each, in queue order; empty when there is no display.

    """
    if not pygame.display.get_init():
        return []
    events = pygame.event.get(eventtype=CUSTOM_EVENT_TYPES, pump=False)
    for event in events:
        pygame.event.post(event)
    return [
        (event.type, {key: repr(value) for key, value in event.dict.items()}) for event in events
    ]


def _note(*, phase: str, node_id: str) -> None:
    """Append one line to the log when custom events are queued now."""
    events = _queued_custom_events()
    if not events:
        return
    log_path = Path(os.environ.get('STALE_EVENT_PROBE_LOG', str(DEFAULT_LOG_PATH)))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('a', encoding='utf-8') as log:
        log.write(json.dumps({'phase': phase, 'test': node_id, 'events': events}) + '\n')


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    """Note what the test starts with, before any fixture runs."""
    _note(phase='setup-start', node_id=item.nodeid)


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item: pytest.Item) -> None:
    """Note what the test leaves, after its fixtures' teardown."""
    _note(phase='teardown-end', node_id=item.nodeid)
