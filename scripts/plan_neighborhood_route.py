"""Plan the Zombies Ain't My Neighbors neighborhood golden's stage-clear route by simulation.

Feature plan 7 (plans/2026-11-15-zombies-aint-my-neighbors-7-neighbors-and-lives.md). The
neighborhood golden plays a fixed opening (``scripts.golden_inputs.NEIGHBORHOOD_OPENING``),
then clears the stage: neighbor to neighbor, out through the gate, the cheer, the STAGE 2 card
and stage 2. Clearing depends on where the neighbors stand, when zombies spawn and how fast
they shamble, so the route is planned here by playing the stage under the goldens' seed
(``RANDOM_SEED``) at the recording's resolution and frame time: after the opening, Dex walks
toward the nearest neighbor still standing, holding J (his zaps clear what is ahead), and once
none stands, to the open gate. The held keys are written out as stretches.

Re-plan whenever gameplay changes (zombie speed, neighbor places, spawn timing, a new weapon),
paste the printed route into ``NEIGHBORHOOD_STAGE_CLEAR_ROUTE`` and re-record the golden with
the printed frame count. The game's test of the golden
(src/games/zombies-aint-my-neighbors/tests/test_zombies_aint_my_neighbors_golden_route.py) fails
when the committed route no longer matches this plan, or the golden no longer reaches stage 2.

The attract demo (feature plan 13) is planned here too, on the same stepping path: four kids,
moving as a group (the group's screen span holds them together), clear stage 1 under the same
seed until one reaches the open gate and all four cheer (``plan_demo``; ``--demo`` prints it for
``scripts.demo_inputs.ZOMBIES_DEMO_ROUTES``). Its test is
src/games/zombies-aint-my-neighbors/tests/test_zombies_aint_my_neighbors_demo_route.py.

Usage:
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python -m scripts.plan_neighborhood_route
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python -m scripts.plan_neighborhood_route \
        --demo
"""

from __future__ import annotations

import math
import os
import sys
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, cast, override

import pygame
from pydantic import BaseModel, ConfigDict

from glitchygames.events.base import HashableEvent
from glitchygames.input.state import InputSnapshot, set_current_input
from glitchygames.randomness import reset_streams
from glitchygames.replay.tools.golden_traces import RANDOM_SEED, qwerty_scancode
from scripts.golden_inputs import NEIGHBORHOOD_OPENING, HeldStretch

if TYPE_CHECKING:
    from collections.abc import Mapping

    from glitchygames.effects.shake import Shake
    from glitchygames.events.base import KeyEvent
    from zombies_aint_my_neighbors.neighborhood import NeighborhoodScene

# The golden's recording: 800x480 at 60 frames a second
RESOLUTION: Final = (800, 480)
FRAME_SECONDS: Final = 1.0 / 60.0
# Closer than this on an axis, Dex stops walking along it
ARRIVED_PIXELS: Final = 3.0
# Where Dex stands to leave: inside the gate's frame, below its top hedge
GATE_OFFSET: Final = (8.0, 8.0)
# Frames kept after the card begins: the card (2 s) and three seconds of stage 2
FRAMES_AFTER_THE_CARD: Final = round((2.0 + 3.0) / FRAME_SECONDS)
# A stage left uncleared this long is a failed plan
FRAME_LIMIT: Final = 6000
# Each held key's place on the keyboard (the neighborhood polls scancodes)
SCANCODES: Final = {
    'W': pygame.KSCAN_W,
    'A': pygame.KSCAN_A,
    'S': pygame.KSCAN_S,
    'D': pygame.KSCAN_D,
    'UP': pygame.KSCAN_UP,
    'DOWN': pygame.KSCAN_DOWN,
    'LEFT': pygame.KSCAN_LEFT,
    'RIGHT': pygame.KSCAN_RIGHT,
    'J': pygame.KSCAN_J,
    'K': pygame.KSCAN_K,
    'RSHIFT': pygame.KSCAN_RSHIFT,
}


class RoutePlan(BaseModel):
    """A planned route and what it reaches."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    route: tuple[HeldStretch, ...]
    # The frame the stage clears on, and the frame the STAGE 2 card begins on
    cleared_at: int
    card_at: int
    rescued: int
    # Frames on which a zombie stood within the lure's reach of a lit laser dot (feature plan 8)
    lured_frames: int
    # The frames to record (``--frames``): the card and three seconds of stage 2 included
    recording_frames: int


def _keys_toward(scene: NeighborhoodScene) -> tuple[str, ...]:
    """Return the keys Dex holds this frame: toward the nearest standing neighbor, else the gate.

    Returns:
        Key names (``scripts.golden_inputs.NEIGHBORHOOD_KEYS``), J always among them.

    """
    dex = scene.kids[0]
    standing = [neighbor for neighbor in scene.neighbors if neighbor.is_standing]
    if standing:
        target = min(
            standing,
            key=lambda neighbor: (
                (neighbor.world_x - dex.world_x) ** 2 + (neighbor.world_y - dex.world_y) ** 2
            ),
        )
        target_x, target_y = target.world_x, target.world_y
    elif scene.exit_door.is_open:
        target_x = scene.exit_door.world_x + GATE_OFFSET[0]
        target_y = scene.exit_door.world_y + GATE_OFFSET[1]
    else:
        target_x, target_y = dex.world_x, dex.world_y
    keys: list[str] = []
    offset_x, offset_y = target_x - dex.world_x, target_y - dex.world_y
    if offset_x > ARRIVED_PIXELS:
        keys.append('D')
    elif offset_x < -ARRIVED_PIXELS:
        keys.append('A')
    if offset_y > ARRIVED_PIXELS:
        keys.append('S')
    elif offset_y < -ARRIVED_PIXELS:
        keys.append('W')
    keys.append('J')
    return tuple(keys)


def _held_at(stretches: tuple[HeldStretch, ...], frame: int) -> tuple[str, ...]:
    """Return the keys stretches hold on a frame.

    Returns:
        Key names (none outside every stretch).

    """
    return next((keys for keys, start, end in stretches if start <= frame < end), ())


def _as_stretches(
    keys_by_frame: list[tuple[str, ...]], *, first_frame: int
) -> tuple[HeldStretch, ...]:
    """Return per-frame keys as stretches of frames holding the same keys (none left out).

    Returns:
        (keys, first frame, frame after the last) for each held run.

    """
    stretches: list[HeldStretch] = []
    start = 0
    for index in range(1, len(keys_by_frame) + 1):
        if index == len(keys_by_frame) or keys_by_frame[index] != keys_by_frame[start]:
            if keys_by_frame[start]:
                stretches.append((keys_by_frame[start], first_frame + start, first_frame + index))
            start = index
    return tuple(stretches)


def _planning_scene(*, demo: bool = False) -> NeighborhoodScene:
    """Return the neighborhood as the golden (or the demo) begins, without its world shake.

    The plan runs no scene manager, and a world shake needs the active scene; the shake is only
    seen, never felt by the game's logic, so skipping it changes nothing the route depends on.

    Args:
        demo: True for the attract demo's neighborhood (four kids, pads on the joystick layer,
            as the scripted-session recorder forces), False for the golden's (the keyboard).

    Returns:
        The scene (not set up).

    """
    # Imported here: the game is a workspace member, loaded only when a plan is made
    from glitchygames.effects.shake import ShakeTarget
    from zombies_aint_my_neighbors.demo_neighborhood import demo_roster
    from zombies_aint_my_neighbors.neighborhood import NeighborhoodScene

    class PlanningNeighborhood(NeighborhoodScene):
        """The neighborhood, its world shake skipped."""

        @override
        def shake(self, shake: Shake, *, targets: ShakeTarget = ShakeTarget.WORLD) -> None:
            """Skip the shake: only seen, never in the game's logic."""

    # The demo's neighborhood (DemoNeighborhoodScene) is this one with the demo's roster
    input_mode = 'joystick' if demo else 'auto'
    return PlanningNeighborhood(
        options={'input_mode': input_mode, 'no_unhandled_events': True},
        roster=demo_roster() if demo else None,
    )


def _snapshot(
    *,
    scancodes: frozenset[int],
    device_axes: Mapping[int, tuple[float, ...]] | None = None,
    device_buttons: Mapping[int, tuple[bool, ...]] | None = None,
) -> InputSnapshot:
    """Return a frame's polled input: held keys, and pads' axes and buttons by instance id.

    Returns:
        The snapshot.

    """
    return InputSnapshot(
        pressed_scancodes=scancodes,
        modifiers=0,
        mouse_position=(0, 0),
        mouse_buttons=(False, False, False),
        mouse_focused=True,
        device_axes=MappingProxyType(dict(device_axes or {})),
        device_buttons=MappingProxyType(dict(device_buttons or {})),
    )


def _step_stage(scene: NeighborhoodScene, *, snapshot: InputSnapshot) -> None:
    """Play one frame of the stage on this input: the one stepping path both plans share."""
    set_current_input(snapshot=snapshot)
    scene.advance_game_time(seconds=FRAME_SECONDS)
    scene.dt_tick(FRAME_SECONDS)


def _a_zombie_is_lured(scene: NeighborhoodScene) -> bool:
    """Return whether a living zombie's feet are within the lure's reach of a lit dot.

    Returns:
        True when one is.

    """
    from zombies_aint_my_neighbors.zombie import FRAME_HEIGHT, FRAME_WIDTH, LURE_DISTANCE

    dots = [kid.dot.centre() for kid in scene.kids.values() if kid.laser_lit]
    return any(
        math.hypot(zombie.world_x + FRAME_WIDTH / 2 - dot_x, zombie.world_y + FRAME_HEIGHT - dot_y)
        <= LURE_DISTANCE
        for zombie in scene.zombies
        if not zombie.is_dying
        for dot_x, dot_y in dots
    )


def _key_down(key: int) -> HashableEvent:
    """Return a key press as the recorded script delivers it (at its US QWERTY place).

    Returns:
        The event.

    """
    return HashableEvent(
        pygame.KEYDOWN, key=key, mod=0, unicode='', scancode=qwerty_scancode(key=key)
    )


def plan_route(
    *, opening: tuple[HeldStretch, ...] = NEIGHBORHOOD_OPENING, seed: int = RANDOM_SEED
) -> RoutePlan:
    """Play the stage under a seed: the opening, then the planned walk; return the route.

    Needs pygame's display (``main`` makes one; a test has the harness's).

    Args:
        opening: The golden's opening stretches.
        seed: The master random seed (the goldens').

    Returns:
        The plan.

    Raises:
        RuntimeError: When the stage is not cleared within ``FRAME_LIMIT`` frames.

    """
    reset_streams(seed=seed)
    scene = _planning_scene()
    scene.setup()
    first_planned_frame = max(end for _keys, _start, end in opening)
    planned: list[tuple[str, ...]] = []
    cleared_at: int | None = None
    held_before: tuple[str, ...] = ()
    lured_frames = 0
    for frame in range(FRAME_LIMIT):
        if frame < first_planned_frame:
            keys = _held_at(opening, frame)
        else:
            keys = () if scene.stage_cleared else _keys_toward(scene)
            planned.append(keys)
        _step_stage(scene, snapshot=_snapshot(scancodes=frozenset(SCANCODES[key] for key in keys)))
        if 'K' in keys and 'K' not in held_before:
            # K switches weapons on its press, an event (the neighborhood's action map), not a
            # polled key; the engine handles a frame's events after its logic, so it is
            # delivered after the frame's tick, as the recorded script's is
            scene.on_key_down_event(cast('KeyEvent', _key_down(pygame.K_k)))
        held_before = keys
        lured_frames += _a_zombie_is_lured(scene)
        if scene.stage_cleared and cleared_at is None:
            cleared_at = frame
        if scene.next_scene is not None:
            if cleared_at is None:
                message = f'the plan ended the stage without clearing it (frame {frame})'
                raise RuntimeError(message)
            return RoutePlan(
                route=_as_stretches(planned, first_frame=first_planned_frame),
                cleared_at=cleared_at,
                card_at=frame,
                rescued=len(scene.rescued),
                lured_frames=lured_frames,
                recording_frames=frame + FRAMES_AFTER_THE_CARD,
            )
    message = f'the stage was not cleared within {FRAME_LIMIT} frames'
    raise RuntimeError(message)


# The attract demo (feature plan 13): how far from a TV the TV hunter stands to zap it, and
# the fire button's index on a stand-in pad's joystick layer (``controls.FIRE_BUTTON``)
TV_STAND_OFF_PIXELS: Final = 72.0
DEMO_PAD_BUTTON_COUNT: Final = 12
# The keyboard kid's keys for each way (``NEIGHBORHOOD_KEYS`` names)
DEMO_KEYS_X: Final = {-1: 'A', 1: 'D'}
DEMO_KEYS_Y: Final = {-1: 'W', 1: 'S'}
# The slot that hunts TVs before it rescues
TV_HUNTER_SLOT: Final = 3
# The TV hunter goes for a TV this close to the group's middle (farther, the group's span would
# hold it back)
TV_HUNT_REACH: Final = 200.0
# Each kid's corner round the group's goal, by slot, so the four spread out a little; wider and
# the kids stand round a neighbor without touching it (twice this rescued one neighbor, not four)
DEMO_FORMATION: Final = ((-10.0, -6.0), (10.0, -6.0), (-10.0, 6.0), (10.0, 6.0))


class KidStretch(BaseModel):
    """Frames over which one kid holds the same direction and fire.

    Attributes:
        direction: Each axis -1, 0 or 1 (the screen's: x right, y down).
        fire: Whether fire is held.
        first_frame: The stretch's first frame.
        end_frame: The frame after its last.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    direction: tuple[int, int]
    fire: bool
    first_frame: int
    end_frame: int


class DemoPlan(BaseModel):
    """The attract demo's planned routes and what the run showed.

    Attributes:
        routes: One route a slot, in slot order (P1 the keyboard, P2 to P4 the stand-in pads).
        cleared_at: The frame the stage cleared on (a kid at the open gate).
        card_at: The frame the STAGE 2 card was made on, after the cheer.
        recording_frames: The frames to record: up to the card, which is never shown.
        rescued: Neighbors rescued.
        televisions_destroyed: TVs destroyed.
        zombies_zapped: Zombies zapped.
        fired_by_slot: Whether each slot's kid zapped.
        moved_by_slot: Whether each slot's kid walked.
        all_cheered: Whether every kid is cheering as the cheer ends.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    routes: tuple[tuple[KidStretch, ...], ...]
    cleared_at: int
    card_at: int
    recording_frames: int
    rescued: int
    televisions_destroyed: int
    zombies_zapped: int
    fired_by_slot: tuple[bool, ...]
    moved_by_slot: tuple[bool, ...]
    all_cheered: bool


def _toward(*, kid_x: float, kid_y: float, target_x: float, target_y: float) -> tuple[int, int]:
    """Return the direction from a kid toward a place, each axis stopping once it has arrived.

    Returns:
        (x, y), each -1, 0 or 1.

    """

    def axis(offset: float) -> int:
        if offset > ARRIVED_PIXELS:
            return 1
        if offset < -ARRIVED_PIXELS:
            return -1
        return 0

    return (axis(target_x - kid_x), axis(target_y - kid_y))


def _demo_steering(scene: NeighborhoodScene) -> dict[int, tuple[int, int]]:
    """Return each kid's direction this frame (every kid holds fire throughout).

    The kids move as a group, as the group's screen span makes them: all head for the standing
    neighbor nearest the group's middle, each kid to its own corner round it
    (``DEMO_FORMATION``), so they spread out instead of stacking. The TV hunter (slot 3)
    breaks off for the nearest TV still standing when one is within ``TV_HUNT_REACH`` of the
    group's middle, standing beside it to zap it. With no neighbor standing, every kid heads
    for the open gate, each to its own corner of it.

    Returns:
        Slot index -> direction.

    """
    kids = scene.kids
    middle_x = sum(kid.world_x for kid in kids.values()) / len(kids)
    middle_y = sum(kid.world_y for kid in kids.values()) / len(kids)

    def from_middle(world_x: float, world_y: float) -> float:
        return math.hypot(world_x - middle_x, world_y - middle_y)

    standing = [neighbor for neighbor in scene.neighbors if neighbor.is_standing]
    if standing:
        goal = min(standing, key=lambda neighbor: from_middle(neighbor.world_x, neighbor.world_y))
        goal_x, goal_y = goal.world_x, goal.world_y
    elif scene.exit_door.is_open:
        goal_x = scene.exit_door.world_x + GATE_OFFSET[0]
        goal_y = scene.exit_door.world_y + GATE_OFFSET[1]
    else:
        goal_x, goal_y = middle_x, middle_y
    live_tvs = [
        tv
        for tv in scene.tvs
        if not tv.is_destroyed and from_middle(tv.world_x, tv.world_y) <= TV_HUNT_REACH
    ]
    steering: dict[int, tuple[int, int]] = {}
    for slot_index, kid in sorted(kids.items()):
        if slot_index == TV_HUNTER_SLOT and standing and live_tvs:
            tv = min(live_tvs, key=lambda each: from_middle(each.world_x, each.world_y))
            side = -1 if kid.world_x < tv.world_x else 1
            target_x, target_y = tv.world_x + side * TV_STAND_OFF_PIXELS, tv.world_y
        else:
            offset_x, offset_y = DEMO_FORMATION[slot_index]
            target_x, target_y = goal_x + offset_x, goal_y + offset_y
        steering[slot_index] = _toward(
            kid_x=kid.world_x, kid_y=kid.world_y, target_x=target_x, target_y=target_y
        )
    return steering


def _demo_snapshot(
    *, steering: Mapping[int, tuple[int, int]], fire: bool, pad_ids: tuple[int, ...]
) -> InputSnapshot:
    """Return the frame's input: the keyboard kid's keys, each pad's stick and fire button.

    Returns:
        The snapshot.

    """
    from zombies_aint_my_neighbors.controls import FIRE_BUTTON

    keyboard_x, keyboard_y = steering.get(0, (0, 0))
    keys = [DEMO_KEYS_X[keyboard_x]] if keyboard_x else []
    keys += [DEMO_KEYS_Y[keyboard_y]] if keyboard_y else []
    keys += ['J'] if fire else []
    buttons = tuple(fire and button == FIRE_BUTTON for button in range(DEMO_PAD_BUTTON_COUNT))
    return _snapshot(
        scancodes=frozenset(SCANCODES[key] for key in keys),
        device_axes={
            instance_id: tuple(float(value) for value in steering.get(slot_index, (0, 0)))
            for slot_index, instance_id in enumerate(pad_ids, start=1)
        },
        device_buttons=dict.fromkeys(pad_ids, buttons),
    )


def _demo_stretches(
    held_by_frame: list[tuple[tuple[int, int], bool]],
) -> tuple[KidStretch, ...]:
    """Return one kid's per-frame direction and fire as stretches (idle frames left out).

    Returns:
        The stretches, in frame order.

    """
    stretches: list[KidStretch] = []
    start = 0
    for index in range(1, len(held_by_frame) + 1):
        if index == len(held_by_frame) or held_by_frame[index] != held_by_frame[start]:
            direction, fire = held_by_frame[start]
            if direction != (0, 0) or fire:
                stretches.append(
                    KidStretch(direction=direction, fire=fire, first_frame=start, end_frame=index)
                )
            start = index
    return tuple(stretches)


def plan_demo(*, seed: int = RANDOM_SEED) -> DemoPlan:
    """Play stage 1 with the demo's four kids under a seed; return their routes.

    Needs pygame's display (``main`` makes one; a test has the harness's).

    Args:
        seed: The master random seed (the goldens').

    Returns:
        The plan.

    Raises:
        RuntimeError: When the stage is not cleared within ``FRAME_LIMIT`` frames, or ends
            without being cleared.

    """
    from zombies_aint_my_neighbors.demo_neighborhood import DEMO_PAD_INSTANCE_IDS
    from zombies_aint_my_neighbors.kid import KidState

    reset_streams(seed=seed)
    scene = _planning_scene(demo=True)
    scene.setup()
    slots = sorted(scene.kids)
    held: dict[int, list[tuple[tuple[int, int], bool]]] = {slot: [] for slot in slots}
    starts = {slot: (kid.world_x, kid.world_y) for slot, kid in scene.kids.items()}
    fired: set[int] = set()
    dying_before: set[int] = set()
    zombies_zapped = 0
    cleared_at: int | None = None
    for frame in range(FRAME_LIMIT):
        playing = not scene.stage_cleared
        steering = _demo_steering(scene) if playing else {}
        for slot in slots:
            held[slot].append((steering.get(slot, (0, 0)), playing))
        _step_stage(
            scene,
            snapshot=_demo_snapshot(steering=steering, fire=playing, pad_ids=DEMO_PAD_INSTANCE_IDS),
        )
        fired.update(scene.zap_owners.values())
        dying_now = {id(zombie) for zombie in scene.zombies if zombie.is_dying}
        zombies_zapped += len(dying_now - dying_before)
        dying_before = dying_now
        if scene.stage_cleared and cleared_at is None:
            cleared_at = frame
        if scene.next_scene is not None:
            if cleared_at is None:
                message = f'the demo ended the stage without clearing it (frame {frame})'
                raise RuntimeError(message)
            return DemoPlan(
                routes=tuple(_demo_stretches(held[slot]) for slot in slots),
                cleared_at=cleared_at,
                card_at=frame,
                recording_frames=frame,
                rescued=len(scene.rescued),
                televisions_destroyed=sum(tv.is_destroyed for tv in scene.tvs),
                zombies_zapped=zombies_zapped,
                fired_by_slot=tuple(slot in fired for slot in slots),
                moved_by_slot=tuple(
                    (scene.kids[slot].world_x, scene.kids[slot].world_y) != starts[slot]
                    for slot in slots
                ),
                # At the cheer's end: a kid knocked out at the clear cheers once it is up
                all_cheered=all(kid.state is KidState.CHEERING for kid in scene.kids.values()),
            )
    message = f'the demo did not clear the stage within {FRAME_LIMIT} frames'
    raise RuntimeError(message)


def _print_demo_plan() -> None:  # pragma: no cover - run by hand; plan_demo is tested
    """Print the attract demo's routes as Python, with what the run showed."""
    plan = plan_demo()
    print('ZOMBIES_DEMO_ROUTES: tuple[tuple[KidStretch, ...], ...] = (')  # ruff: ignore[print]
    for route in plan.routes:
        print('    (')  # ruff: ignore[print]
        for stretch in route:
            print(  # ruff: ignore[print]
                f'        KidStretch(direction={stretch.direction}, fire={stretch.fire}, '
                f'first_frame={stretch.first_frame}, end_frame={stretch.end_frame}),'
            )
        print('    ),')  # ruff: ignore[print]
    print(')')  # ruff: ignore[print]
    print(f'ZOMBIES_DEMO_FRAME_COUNT = {plan.recording_frames}')  # ruff: ignore[print]
    print(  # ruff: ignore[print]
        f'# cleared at frame {plan.cleared_at}, the card at {plan.card_at}; '
        f'{plan.rescued} rescued, {plan.televisions_destroyed} TVs destroyed, '
        f'{plan.zombies_zapped} zombies zapped; every kid cheering: {plan.all_cheered}'
    )


def main() -> None:  # pragma: no cover - run by hand; plan_route is tested
    """Plan the golden's route (or, with ``--demo``, the attract demo's) and print it as Python."""
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
    pygame.init()
    pygame.display.set_mode(RESOLUTION)
    if '--demo' in sys.argv[1:]:
        _print_demo_plan()
        return
    plan = plan_route()
    print('NEIGHBORHOOD_STAGE_CLEAR_ROUTE: tuple[HeldStretch, ...] = (')  # ruff: ignore[print]
    for keys, start, end in plan.route:
        print(f'    ({keys!r}, {start}, {end}),')  # ruff: ignore[print]
    print(')')  # ruff: ignore[print]
    print(  # ruff: ignore[print]
        f'# cleared at frame {plan.cleared_at}, the card at {plan.card_at}, '
        f'{plan.rescued} rescued: record with --frames {plan.recording_frames}'
    )


if __name__ == '__main__':  # pragma: no cover
    main()
