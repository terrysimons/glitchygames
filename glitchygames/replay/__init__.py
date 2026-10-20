"""Gameplay replay: ``--replay-trace PATH`` replays a recording exactly through the engine.

See glitchygames/replay/driver.py.
"""

from glitchygames.replay.driver import (
    EVENT_DIVERGENCE,
    LENGTH_DIVERGENCE,
    REPLAY_LOCAL_OPTIONS,
    REPLAY_UNUSABLE_EXIT_CODE,
    SCENE_DIVERGENCE,
    SPRITE_DIVERGENCE,
    Divergence,
    ReplayRefusedError,
    ReplayResult,
    ReplaySources,
    apply_recorded_options,
    start_replay,
)

__all__ = [
    'EVENT_DIVERGENCE',
    'LENGTH_DIVERGENCE',
    'REPLAY_LOCAL_OPTIONS',
    'REPLAY_UNUSABLE_EXIT_CODE',
    'SCENE_DIVERGENCE',
    'SPRITE_DIVERGENCE',
    'Divergence',
    'ReplayRefusedError',
    'ReplayResult',
    'ReplaySources',
    'apply_recorded_options',
    'start_replay',
]
