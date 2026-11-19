"""The exit door: shut until a stage's neighbors are all saved or lost, then open and glowing.

Feature plan 7, Task 7; the props BOM's exit door (``closed``; ``opening``, 3 frames of 0.08 s;
then ``open``, its glow pulsing).
"""

from __future__ import annotations

from zombies_aint_my_neighbors.exit_door import OPENING_SECONDS, ExitDoor

SIXTIETH = 1.0 / 60.0


def test_a_new_door_is_shut():
    """Closed, and not open."""
    door = ExitDoor(world_x=776.0, world_y=0.0, groups=None)
    door.dt_tick(0.0)

    assert door.current_animation == 'closed'
    assert not door.is_open


def test_an_opened_door_swings_open_then_glows():
    """Opening plays, then the open glow loops; it counts as open from the start."""
    door = ExitDoor(world_x=776.0, world_y=0.0, groups=None)
    door.open()
    door.dt_tick(SIXTIETH)

    assert door.is_open
    assert door.current_animation == 'opening'
    for _ in range(round(OPENING_SECONDS / SIXTIETH) + 1):
        door.dt_tick(SIXTIETH)
    assert door.current_animation == 'open'


def test_opening_twice_does_not_restart_the_swing():
    """A second open is nothing new."""
    door = ExitDoor(world_x=776.0, world_y=0.0, groups=None)
    door.open()
    for _ in range(round(OPENING_SECONDS / SIXTIETH) + 1):
        door.dt_tick(SIXTIETH)
    door.open()
    door.dt_tick(SIXTIETH)

    assert door.current_animation == 'open'
