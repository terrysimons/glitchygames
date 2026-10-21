"""Physical key positions for fabricated key events (scripts, tests, recordings patched by them).

A real keyboard's KEYDOWN and KEYUP carry a ``scancode``: the key's physical position, the same
on every layout. ``ActionMap.bind(scancode=...)`` binds positional controls to it
(glitchygames/input/action_map.py), so code that fabricates key events (the golden input
scripts, tests, the replay fixtures they recorded) must give each event the position its key
has. ``qwerty_scancode`` answers with the US QWERTY position, by pygame's own names (``K_w`` is
in the ``KSCAN_W`` position, ``K_LSHIFT`` in ``KSCAN_LSHIFT``): what the scripts mean by "press
W", and the same answer on every machine, whatever its layout. It is not this machine's keymap,
which a fabricated event has no keyboard to consult.
"""

from __future__ import annotations

import pygame

KEY_CODE_PREFIX = 'K_'
SCANCODE_PREFIX = 'KSCAN_'

# Every pygame key code with a scancode of the same name: its US QWERTY position
QWERTY_SCANCODES: dict[int, int] = {
    getattr(pygame, name): getattr(
        pygame, f'{SCANCODE_PREFIX}{name[len(KEY_CODE_PREFIX) :].upper()}'
    )
    for name in dir(pygame)
    if name.startswith(KEY_CODE_PREFIX)
    and hasattr(pygame, f'{SCANCODE_PREFIX}{name[len(KEY_CODE_PREFIX) :].upper()}')
}


def qwerty_scancode(*, key: int) -> int:
    """Return the US QWERTY position of a key, for a fabricated key event.

    Args:
        key: A pygame key code (``pygame.K_*``).

    Returns:
        Its scancode (``pygame.KSCAN_*``), or ``pygame.KSCAN_UNKNOWN`` (0) for a key pygame
        names no position for, as SDL reports a key it cannot place.

    """
    return QWERTY_SCANCODES.get(key, pygame.KSCAN_UNKNOWN)
