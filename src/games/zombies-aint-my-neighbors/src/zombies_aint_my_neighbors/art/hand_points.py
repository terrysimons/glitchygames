"""Where a weapon sits in each kid weapon frame, computed from the rig's poses.

BOM section 1: hand points live in game code, never in the TOML (which has no point fields),
and the four kids share them (one rig). They come from the same poses the rig draws, so a pose
change moves the hand point with the hand. Weapons are drawn only while attacking (BOM decision
9), so only the weapon animations have points. The weapon hand is the right hand as the viewer
sees it (both hands meet there when aiming), or the near hand in the side view. A mirrored
(right-facing) frame's point is ``x' = 31 - x`` (BOM section 1).
"""

from __future__ import annotations

from typing import Final

from zombies_aint_my_neighbors.art import poses, rig

# The kid animations that hold a weapon
WEAPON_STATES: Final = ('shoot', 'walk-shoot', 'spray', 'swing', 'launch', 'throw')


def _weapon_hand_points() -> dict[str, tuple[rig.Point, ...]]:
    """Return each weapon namespace's hand point per frame.

    Returns:
        Namespace -> one (x, y) per frame, in native pixels.

    """
    return {
        name: tuple(rig.hand_positions(pose=pose)[-1] for pose in frame_poses)
        for name, frame_poses in poses.kid_namespaces().items()
        if name.rpartition('_')[0] in WEAPON_STATES
    }


KID_HAND_POINTS: Final[dict[str, tuple[rig.Point, ...]]] = _weapon_hand_points()
