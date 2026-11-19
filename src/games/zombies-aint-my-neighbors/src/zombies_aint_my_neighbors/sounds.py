"""The game's sounds: their names in ``sounds/sounds.toml``, and how the engine finds them.

Feature plan 10 (plans/2026-11-15-zombies-aint-my-neighbors-10-first-sounds.md). Every sound is an
``[effects.*]`` table in one sound file (TOML version 1; master plan decision 3), named by its
absolute path (``sound_reference``), and declared in ``SOUNDS`` (on ``RosterScene``) so the engine
compiles it while the game starts (decision 11).

The engine has no vibrato in a baked sound yet (milestone M4), so each warble is a chain of short
tones, each sweeping its pitch with ``ease_in_out_sine``: the chain traces a near-vibrato.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

SOUND_DIRECTORY_NAME: Final = 'sounds'
SOUND_FILE: Final = Path(__file__).parent / SOUND_DIRECTORY_NAME / 'sounds.toml'
# The remote's zap: warbly theremin radio waves (the owner, 2026-11-15)
ZAP: Final = 'zap'
# The laser pointer's wheee: rising while it warms up, wobbling high while the dot shines
LASER_RISE: Final = 'laser-rise'
LASER_SHINE: Final = 'laser-shine'
# A zombie's moans, one picked at random when it groans
GROANS: Final = ('groan-1', 'groan-2', 'groan-3')
# Feature plan 11 (plans/2026-11-18-zombies-aint-my-neighbors-11-the-rest-of-the-sounds.md):
# a zombie climbing out of a TV, and what a zap does to a TV, from the least to the most
TV_SPAWN: Final = 'tv-spawn'
TV_HIT: Final = 'tv-hit'
TV_BREAK: Final = 'tv-break'
TV_DESTROYED: Final = 'tv-destroyed'
# A neighbor rescued or lost, a kid knocked out, the gate opening, and the TV switching off
RESCUE: Final = 'rescue'
LOSS: Final = 'loss'
KNOCKOUT: Final = 'knockout'
GATE: Final = 'gate'
SWITCH_OFF: Final = 'switch-off'


def sound_reference(name: str) -> str:
    """Return how the engine names one of the game's sounds: the file's path and the sound.

    The path is absolute: a relative one resolves against the active scene's package, and falls
    back to the working directory where no scene is active (a test, a tool). ``SOUNDS`` and every
    play use these same strings, so each play finds the sound compiled at start.

    Returns:
        ``<path to sounds.toml>#<name>``.

    """
    return f'{SOUND_FILE}#{name}'


# Every sound, as the engine's SOUNDS takes them
EVERY_SOUND: Final = (
    ZAP,
    LASER_RISE,
    LASER_SHINE,
    *GROANS,
    TV_SPAWN,
    TV_HIT,
    TV_BREAK,
    TV_DESTROYED,
    RESCUE,
    LOSS,
    KNOCKOUT,
    GATE,
    SWITCH_OFF,
)
SOUND_REFERENCES: Final = tuple(sound_reference(name) for name in EVERY_SOUND)
