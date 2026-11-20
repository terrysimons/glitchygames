"""The attract demo's neighborhood: stage 1 with all four kids joined (feature plan 13).

The demo (``demos/neighborhood_four_kids.jsonl.gz``) shows four kids playing together from its
first frame. A recording's first scene is built from options alone (the scripted-session
recorder takes a scene class, not arguments), so this scene's default roster is the demo's four
players: the keyboard as P1 (Dex), then the three stand-in pads the recording holds, gamepads
``DEMO_PAD_INSTANCE_IDS``, as P2 to P4 (Marisol, Theo, June). Joined in that order, they take
slots 1 to 4 as live joins do. A replay rebuilds it from its recorded scene start, the roster
included; the launcher starts this scene for a recording made in it (``launcher.first_scene``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, override

from zombies_aint_my_neighbors import text
from zombies_aint_my_neighbors.neighborhood import NeighborhoodScene
from zombies_aint_my_neighbors.roster import JoinRoster
from zombies_aint_my_neighbors.roster_scene import KEYBOARD_IDENTITY, gamepad_identity

if TYPE_CHECKING:
    import pygame

    from zombies_aint_my_neighbors.run_state import RunState
    from zombies_aint_my_neighbors.sprite_kit import SpriteKit

# The demo's stand-in pads' SDL instance ids, P2 to P4 (the recipe's stand-ins and the roster
# both read this)
DEMO_PAD_INSTANCE_IDS: Final = (0, 1, 2)


def demo_roster() -> JoinRoster:
    """Return the demo's players: the keyboard, then the stand-in pads, in slot order.

    Returns:
        The roster.

    """
    roster = JoinRoster.empty().join(device=KEYBOARD_IDENTITY)
    for instance_id in DEMO_PAD_INSTANCE_IDS:
        roster = roster.join(device=gamepad_identity(instance_id=instance_id))
    return roster


class DemoNeighborhoodScene(NeighborhoodScene):
    """Stage 1, its default players the demo's four."""

    NAME = f'{text.GAME_NAME} - Demo'

    @override
    def __init__(
        self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
        roster: JoinRoster | dict[str, Any] | None = None,
        run: RunState | dict[str, Any] | None = None,
        kit: SpriteKit | None = None,
    ) -> None:
        """Make the stage for the demo's four players unless others are given.

        Args:
            options: The engine's options.
            groups: The sprite groups to draw into (a new LayeredDirty when None).
            roster: The players (its JSON form, as a replay passes it back), or None for the
                demo's four.
            run: The run this stage plays, or None for a new run.
            kit: The sprites built ahead, or None to build every sprite now.

        """
        super().__init__(
            options=options,
            groups=groups,
            roster=demo_roster() if roster is None else roster,
            run=run,
            kit=kit,
        )
