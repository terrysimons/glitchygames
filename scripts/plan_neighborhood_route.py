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

Usage:
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python -m scripts.plan_neighborhood_route
"""

from __future__ import annotations

import math
import os
from typing import TYPE_CHECKING, Final, cast, override

import pygame
from pydantic import BaseModel, ConfigDict

from glitchygames.events.base import HashableEvent
from glitchygames.input.state import InputSnapshot, set_current_input
from glitchygames.randomness import reset_streams
from glitchygames.replay.tools.golden_traces import RANDOM_SEED, qwerty_scancode
from scripts.golden_inputs import NEIGHBORHOOD_OPENING, HeldStretch

if TYPE_CHECKING:
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


def _planning_scene() -> NeighborhoodScene:
    """Return the neighborhood as the golden begins, without its world shake.

    The plan runs no scene manager, and a world shake needs the active scene; the shake is only
    seen, never felt by the game's logic, so skipping it changes nothing the route depends on.

    Returns:
        The scene (not set up).

    """
    # Imported here: the game is a workspace member, loaded only when a plan is made
    from glitchygames.effects.shake import ShakeTarget
    from zombies_aint_my_neighbors.neighborhood import NeighborhoodScene

    class PlanningNeighborhood(NeighborhoodScene):
        """The neighborhood, its world shake skipped."""

        @override
        def shake(self, shake: Shake, *, targets: ShakeTarget = ShakeTarget.WORLD) -> None:
            """Skip the shake: only seen, never in the game's logic."""

    return PlanningNeighborhood(options={'input_mode': 'auto', 'no_unhandled_events': True})


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
        set_current_input(
            snapshot=InputSnapshot(
                pressed_scancodes=frozenset(SCANCODES[key] for key in keys),
                modifiers=0,
                mouse_position=(0, 0),
                mouse_buttons=(False, False, False),
                mouse_focused=True,
            )
        )
        scene.advance_game_time(seconds=FRAME_SECONDS)
        scene.dt_tick(FRAME_SECONDS)
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


def main() -> None:  # pragma: no cover - run by hand; plan_route is tested
    """Plan the route and print it as Python, with the frame count to record."""
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
    pygame.init()
    pygame.display.set_mode(RESOLUTION)
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
