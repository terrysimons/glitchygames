"""The kids' animations from the character BOM (section 3), and the pose of every frame.

A pose says where the legs and arms are, how far the upper body bobs and leans, and whether the
frame is one of the special ones (lying down, loading in). The rig draws a pose; the kids share
every pose, so they share the rig.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict


class Facing(StrEnum):
    """The drawn facings; right is left mirrored by the game (BOM section 1)."""

    DOWN = 'down'
    UP = 'up'
    LEFT = 'left'
    # The diagonals (owner, 2026-11-14: "I want a diagonal pose"): three-quarter front and back,
    # turned left; down-right and up-right are these mirrored, as right is left
    DOWN_LEFT = 'down-left'
    UP_LEFT = 'up-left'


class Legs(StrEnum):
    """Where the legs are."""

    STAND = 'stand'
    # Front and back views: one leg lifted
    LEFT_UP = 'left_up'
    RIGHT_UP = 'right_up'
    # Side view: a stride (the near or the far leg forward), and legs passing
    STRIDE_NEAR = 'stride_near'
    STRIDE_FAR = 'stride_far'
    PASSING = 'passing'
    # Both feet off the ground (a cheer's jump)
    TUCKED = 'tucked'


class Arms(StrEnum):
    """Where the hands are (the rig draws each arm from its shoulder to its hand)."""

    SIDES = 'sides'
    LEFT_FORWARD = 'left_forward'
    RIGHT_FORWARD = 'right_forward'
    AIM = 'aim'
    AIM_RECOIL = 'aim_recoil'
    BRACE = 'brace'
    BRACE_SHUDDER = 'brace_shudder'
    SWING_BACK = 'swing_back'
    SWING_ACROSS = 'swing_across'
    SWING_THROUGH = 'swing_through'
    SHOULDER = 'shoulder'
    THROW_WINDUP = 'throw_windup'
    THROW_RELEASE = 'throw_release'
    THROW_FOLLOW = 'throw_follow'
    FISTS_UP = 'fists_up'
    FISTS_HIGH = 'fists_high'
    HIGH_FIVE = 'high_five'
    HIGH_FIVE_UP = 'high_five_up'


class Special(StrEnum):
    """Frames that are not a standing kid."""

    LYING = 'lying'
    LYING_STARS = 'lying_stars'
    LOADING = 'loading'


class Pose(BaseModel):
    """One frame's pose."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    facing: Facing
    legs: Legs = Legs.STAND
    arms: Arms = Arms.SIDES
    # The upper body (head, torso, arms) moves down this many rows
    bob: int = 0
    # The upper body moves right this many columns
    lean: int = 0
    special: Special | None = None
    # LOADING: the rows below this one are not drawn yet (None: all of them are)
    loaded_rows: int | None = None
    sparkle: bool = False


class AnimationSpec(BaseModel):
    """One kid animation as the BOM lists it."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    state: str
    # The facings drawn; empty for an animation without a facing (down only)
    facings: tuple[Facing, ...]
    frame_interval: float
    loop: bool
    # The state played next, in the same facing, when it names a namespace in the same file
    then_state: str | None = None
    when: str = 'animation_complete'


ALL_FACINGS: Final = (Facing.DOWN, Facing.UP, Facing.LEFT)
DIAGONAL_FACINGS: Final = (Facing.DOWN_LEFT, Facing.UP_LEFT)
# Standing and walking have the diagonals too; the weapon poses get them with weapons
MOVE_FACINGS: Final = (*ALL_FACINGS, *DIAGONAL_FACINGS)

# BOM section 3, in its order
KID_ANIMATIONS: Final[tuple[AnimationSpec, ...]] = (
    AnimationSpec(state='idle', facings=MOVE_FACINGS, frame_interval=0.5, loop=True),
    AnimationSpec(state='walk', facings=MOVE_FACINGS, frame_interval=0.12, loop=True),
    AnimationSpec(
        state='shoot', facings=ALL_FACINGS, frame_interval=0.08, loop=False, then_state='idle'
    ),
    AnimationSpec(state='walk-shoot', facings=ALL_FACINGS, frame_interval=0.12, loop=True),
    AnimationSpec(state='spray', facings=ALL_FACINGS, frame_interval=0.08, loop=True),
    AnimationSpec(state='swing', facings=ALL_FACINGS, frame_interval=0.08, loop=True),
    AnimationSpec(
        state='launch', facings=ALL_FACINGS, frame_interval=0.08, loop=False, then_state='idle'
    ),
    AnimationSpec(
        state='throw', facings=ALL_FACINGS, frame_interval=0.08, loop=False, then_state='idle'
    ),
    AnimationSpec(
        state='knocked-out',
        facings=(),
        frame_interval=0.1,
        loop=False,
        then_state='respawn',
        when='animation_complete and lives_left > 0',
    ),
    AnimationSpec(
        state='respawn', facings=(), frame_interval=0.1, loop=False, then_state='idle_down'
    ),
    AnimationSpec(state='cheer', facings=(), frame_interval=0.25, loop=True),
    AnimationSpec(
        state='rescue', facings=(), frame_interval=0.1, loop=False, then_state='idle_down'
    ),
)

# A walk cycle: contact, pass, contact, pass (legs, upper-body bob, arm swing)
_FRONT_WALK_LEGS: Final = (Legs.STAND, Legs.LEFT_UP, Legs.STAND, Legs.RIGHT_UP)
_SIDE_WALK_LEGS: Final = (Legs.STRIDE_NEAR, Legs.PASSING, Legs.STRIDE_FAR, Legs.PASSING)
_WALK_BOB: Final = (1, 0, 1, 0)
_WALK_ARMS: Final = (Arms.LEFT_FORWARD, Arms.SIDES, Arms.RIGHT_FORWARD, Arms.SIDES)


def namespace(*, state: str, facing: Facing | None) -> str:
    """Return a BOM namespace: ``<state>_<facing>``, or ``<state>`` with no facing.

    Returns:
        The namespace.

    """
    return state if facing is None else f'{state}_{facing}'


def _walk(*, facing: Facing, arms: Arms | None) -> tuple[Pose, ...]:
    """Return a walk cycle's four poses, with the arms swinging or held in one pose.

    Returns:
        The poses.

    """
    legs = _SIDE_WALK_LEGS if facing is Facing.LEFT else _FRONT_WALK_LEGS
    return tuple(
        Pose(facing=facing, legs=leg, bob=bob, arms=swing if arms is None else arms)
        for leg, bob, swing in zip(legs, _WALK_BOB, _WALK_ARMS, strict=True)
    )


def kid_poses(*, state: str, facing: Facing | None) -> tuple[Pose, ...]:
    """Return the poses of one kid animation's frames, in order.

    Args:
        state: The BOM state (``walk``, ``knocked-out``).
        facing: The facing, or None for an animation without one (drawn facing down).

    Returns:
        One pose per frame.

    Raises:
        ValueError: For a state the BOM does not list.

    """
    drawn = Facing.DOWN if facing is None else facing
    poses: dict[str, tuple[Pose, ...]] = {
        'idle': (Pose(facing=drawn), Pose(facing=drawn, bob=1)),
        'walk': _walk(facing=drawn, arms=None),
        'shoot': (Pose(facing=drawn, arms=Arms.AIM), Pose(facing=drawn, arms=Arms.AIM_RECOIL)),
        'walk-shoot': _walk(facing=drawn, arms=Arms.AIM),
        'spray': (
            Pose(facing=drawn, arms=Arms.BRACE),
            Pose(facing=drawn, arms=Arms.BRACE_SHUDDER, bob=1),
        ),
        'swing': (
            Pose(facing=drawn, arms=Arms.SWING_BACK),
            Pose(facing=drawn, arms=Arms.SWING_ACROSS),
            Pose(facing=drawn, arms=Arms.SWING_THROUGH, bob=1),
        ),
        'launch': (
            Pose(facing=drawn, arms=Arms.SHOULDER),
            Pose(facing=drawn, arms=Arms.SHOULDER, lean=1),
            Pose(facing=drawn, arms=Arms.SHOULDER),
        ),
        'throw': (
            Pose(facing=drawn, arms=Arms.THROW_WINDUP),
            Pose(facing=drawn, arms=Arms.THROW_RELEASE),
            Pose(facing=drawn, arms=Arms.THROW_FOLLOW, bob=1),
        ),
        'knocked-out': (
            Pose(facing=Facing.DOWN, lean=1, arms=Arms.FISTS_UP),
            Pose(facing=Facing.UP, lean=1),
            Pose(facing=Facing.LEFT),
            Pose(facing=Facing.DOWN, special=Special.LYING),
            Pose(facing=Facing.DOWN, special=Special.LYING_STARS),
        ),
        'respawn': (
            Pose(facing=Facing.DOWN, special=Special.LOADING, loaded_rows=14),
            Pose(facing=Facing.DOWN, special=Special.LOADING, loaded_rows=26),
            Pose(facing=Facing.DOWN, special=Special.LOADING, loaded_rows=38),
            Pose(facing=Facing.DOWN),
        ),
        'cheer': (
            Pose(facing=Facing.DOWN, arms=Arms.FISTS_UP),
            Pose(facing=Facing.DOWN, arms=Arms.FISTS_HIGH, legs=Legs.TUCKED),
        ),
        'rescue': (
            Pose(facing=Facing.DOWN, arms=Arms.HIGH_FIVE),
            Pose(facing=Facing.DOWN, arms=Arms.HIGH_FIVE_UP, sparkle=True),
        ),
    }
    if state not in poses:
        message = f'the BOM lists no kid animation {state!r}'
        raise ValueError(message)
    return poses[state]


def kid_namespaces() -> dict[str, tuple[Pose, ...]]:
    """Return every kid namespace the BOM lists, with its frames' poses, in BOM order.

    Returns:
        Namespace -> poses.

    """
    return {
        namespace(state=spec.state, facing=facing): kid_poses(state=spec.state, facing=facing)
        for spec in KID_ANIMATIONS
        for facing in (spec.facings or (None,))
    }
