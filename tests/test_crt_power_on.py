"""The CRT power-on sequence before every game (glitchygames/crt_power_on.py)."""

from __future__ import annotations

import pytest

from glitchygames.crt_power_on import CrtPowerOnMode, should_play


@pytest.mark.parametrize(
    ('mode', 'video_driver', 'options', 'plays'),
    [
        # Someone is watching a live run
        (CrtPowerOnMode.AUTO, 'cocoa', {}, True),
        # Nobody sees SDL's dummy driver: --headless, and every test
        (CrtPowerOnMode.AUTO, 'dummy', {}, False),
        # Before frame 0 of a replay, an audit, a rebaseline or a recording: never
        (CrtPowerOnMode.AUTO, 'cocoa', {'replay_trace': 'run.jsonl.gz'}, False),
        (CrtPowerOnMode.AUTO, 'cocoa', {'record_trace': 'run.jsonl.gz'}, False),
        (CrtPowerOnMode.AUTO, 'cocoa', {'audit': True}, False),
        (CrtPowerOnMode.AUTO, 'cocoa', {'rebaseline': 'new.jsonl.gz'}, False),
        # Options left at their defaults (None, False) are not set
        (CrtPowerOnMode.AUTO, 'cocoa', {'replay_trace': None, 'audit': False}, True),
        (CrtPowerOnMode.OFF, 'cocoa', {}, False),
        # The sequence's own tests force it on the dummy driver
        (CrtPowerOnMode.ON, 'dummy', {}, True),
    ],
)
def test_when_the_sequence_plays(mode, video_driver, options, plays):
    """Auto plays only where someone watches and nothing is recorded or replayed."""
    assert should_play(mode=mode, video_driver=video_driver, options=options) is plays
