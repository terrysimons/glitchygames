"""The join roster: which device holds which of the four player slots."""

from __future__ import annotations

import pydantic
import pytest

from zombies_aint_my_neighbors.roster import (
    MAXIMUM_PLAYERS,
    PLAYER_COLOURS,
    DeviceIdentity,
    DeviceKind,
    JoinRoster,
)

KEYBOARD = DeviceIdentity(kind=DeviceKind.KEYBOARD, instance_id=None)


def gamepad(instance_id: int) -> DeviceIdentity:
    """Return a gamepad's identity.

    Returns:
        The identity of the pad with this SDL instance id.

    """
    return DeviceIdentity(kind=DeviceKind.GAMEPAD, instance_id=instance_id)


# Join (+) and leave (-) sequences over the keyboard and pads 0 to 5, covering a full roster,
# repeated joins, leaving a device that never joined and rejoining after a leave
SEQUENCES: tuple[tuple[tuple[str, DeviceIdentity], ...], ...] = (
    (('+', KEYBOARD), ('+', KEYBOARD), ('+', gamepad(0))),
    tuple(('+', gamepad(instance_id)) for instance_id in range(6)),
    (('+', gamepad(1)), ('-', gamepad(1)), ('+', gamepad(1)), ('+', gamepad(1))),
    (('-', gamepad(3)), ('+', KEYBOARD), ('+', gamepad(0)), ('-', KEYBOARD), ('+', gamepad(2))),
    (
        ('+', gamepad(0)),
        ('+', gamepad(1)),
        ('+', gamepad(2)),
        ('+', KEYBOARD),
        ('+', gamepad(4)),
        ('-', gamepad(1)),
        ('+', gamepad(4)),
        ('+', gamepad(5)),
    ),
)


def apply(sequence: tuple[tuple[str, DeviceIdentity], ...]) -> list[JoinRoster]:
    """Return the roster after each step of a join and leave sequence.

    Returns:
        One roster per step.

    """
    roster = JoinRoster.empty()
    rosters = []
    for operation, device in sequence:
        roster = roster.join(device=device) if operation == '+' else roster.leave(device=device)
        rosters.append(roster)
    return rosters


@pytest.mark.parametrize('sequence', SEQUENCES)
def test_a_slot_is_never_held_by_two_devices_and_a_device_never_holds_two_slots(sequence):
    """Whatever joins and leaves happen, the devices in the slots are all different."""
    for roster in apply(sequence):
        devices = [player.device for player in roster.joined_players]

        assert len(devices) == len(set(devices))
        assert len(roster.slots) == MAXIMUM_PLAYERS
        for index, player in enumerate(roster.slots):
            assert player is None or player.slot_index == index


def test_the_first_device_takes_slot_one():
    """An empty roster's first join lands in the first slot."""
    roster = JoinRoster.empty().join(device=KEYBOARD)

    first = roster.slots[0]
    assert first is not None
    assert first.device == KEYBOARD
    assert roster.slots[1:] == (None, None, None)


def test_joining_twice_keeps_one_slot():
    """The same device pressing start twice keeps its one slot (Review Focus 1)."""
    once = JoinRoster.empty().join(device=gamepad(7))

    assert once.join(device=gamepad(7)) == once
    assert len(once.join(device=gamepad(7)).joined_players) == 1


def test_a_fifth_device_is_ignored():
    """With every slot taken, another device's join changes nothing."""
    full = JoinRoster.empty()
    for instance_id in range(MAXIMUM_PLAYERS):
        full = full.join(device=gamepad(instance_id))

    assert full.is_full
    assert full.join(device=KEYBOARD) == full
    assert not full.holds(device=KEYBOARD)


def test_leaving_frees_the_slot_and_the_next_join_takes_the_lowest_free_slot():
    """A device that leaves frees its slot, and the next new device takes the lowest free one."""
    roster = JoinRoster.empty()
    for instance_id in (10, 11, 12):
        roster = roster.join(device=gamepad(instance_id))

    roster = roster.leave(device=gamepad(11)).join(device=gamepad(13))

    second = roster.slots[1]
    assert second is not None
    assert second.device == gamepad(13)
    assert not roster.holds(device=gamepad(11))


def test_the_keyboard_and_a_pad_with_instance_id_zero_are_different_devices():
    """The keyboard has no instance id, so pad 0 never collides with it."""
    roster = JoinRoster.empty().join(device=KEYBOARD).join(device=gamepad(0))

    assert [player.device for player in roster.joined_players] == [KEYBOARD, gamepad(0)]


def test_leaving_a_device_that_never_joined_changes_nothing():
    """Unplugging a pad that held no slot leaves the roster as it was."""
    roster = JoinRoster.empty().join(device=KEYBOARD)

    assert roster.leave(device=gamepad(4)) == roster


def test_the_roster_is_immutable():
    """A roster can't be changed in place; join and leave return new rosters."""
    roster = JoinRoster.empty()

    with pytest.raises(pydantic.ValidationError):
        roster.slots = (None, None, None, None)


def test_a_roster_must_have_exactly_four_slots():
    """A roster built with the wrong number of slots is refused."""
    with pytest.raises(pydantic.ValidationError):
        JoinRoster(slots=(None, None))


def test_there_is_one_distinct_colour_per_player():
    """Each of the four slots has its own colour."""
    assert len(PLAYER_COLOURS) == MAXIMUM_PLAYERS
    assert len(set(PLAYER_COLOURS)) == MAXIMUM_PLAYERS
