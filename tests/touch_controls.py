"""What the browser games' touch buttons press, shared by the touch-control tests.

The page (browser/touch_controls.js) turns each button of a layout
(scripts/build_browser_bundle.py ``TOUCH_LAYOUTS``) into the key events of the key it names. The
engine's tests/test_browser_touch_controls.py checks the layouts and the boot config; each game's
own ``test_<distribution>_touch_controls.py`` checks that its buttons press keys its scenes bind.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from scripts.build_browser_bundle import TouchButton, TouchLayout

    from glitchygames.input import ActionMap

# The pygame scancode of each key a touch button can press (its DOM KeyboardEvent.code)
SCANCODE_BY_CODE = {
    'ArrowUp': pygame.KSCAN_UP,
    'ArrowDown': pygame.KSCAN_DOWN,
    'ArrowLeft': pygame.KSCAN_LEFT,
    'ArrowRight': pygame.KSCAN_RIGHT,
    'Space': pygame.KSCAN_SPACE,
    'Escape': pygame.KSCAN_ESCAPE,
    'KeyW': pygame.KSCAN_W,
    'KeyS': pygame.KSCAN_S,
    'KeyP': pygame.KSCAN_P,
    'ShiftLeft': pygame.KSCAN_LSHIFT,
}

# The shared pause and game-over screens' keys (scenes/builtin_scenes: Space, Esc)
SHARED_SCREEN_CODES = frozenset({'Space', 'Escape'})


def bound_scancodes(*action_maps: ActionMap) -> set[int]:
    """Return every scancode the action maps bind.

    Returns:
        The scancodes.

    """
    return {
        binding['scancode']
        for action_map in action_maps
        for bindings in action_map.to_dict().values()
        for binding in bindings
        if 'scancode' in binding
    }


def layout_buttons(layout: TouchLayout) -> list[TouchButton]:
    """Return every button of a layout (gaps left out).

    Returns:
        The buttons, cluster by cluster.

    """
    return [
        button
        for rows in (layout.left, layout.center, layout.right)
        for row in rows
        for button in row
        if button is not None
    ]


def assert_every_button_presses_a_key_its_scenes_read(
    *, layout: TouchLayout, scene_scancodes: list[set[int]]
) -> None:
    """Assert each button presses a key every one of the page's scenes reads.

    A key is read when the scene's action maps bind it, or when it is one of the shared pause
    and game-over screens' keys (``SHARED_SCREEN_CODES``).

    Args:
        layout: The game's touch layout.
        scene_scancodes: For each scene that takes the page's buttons, the scancodes it binds.

    """
    shared = {SCANCODE_BY_CODE[code] for code in SHARED_SCREEN_CODES}
    for scancodes in scene_scancodes:
        readable = scancodes | shared

        for button in layout_buttons(layout):
            assert SCANCODE_BY_CODE[button.code] in readable, button
