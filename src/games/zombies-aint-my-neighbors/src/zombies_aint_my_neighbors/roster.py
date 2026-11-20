"""The join roster: which device holds which of the four player slots.

A pure, immutable model: the title screen turns presses into ``join`` and unplugged devices
into ``leave``, and draws the result. The rules (feature plan 1, decisions table):

* A device that holds no slot takes the lowest free slot when it joins.
* A device never holds two slots, and a slot never holds two devices.
* With every slot taken, another device's join changes nothing.
* A device that leaves frees its slot for the next new device.

Joins happen on presses, not every frame, so the pydantic models cost nothing that matters.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, ConfigDict, field_validator

# Four players at most: one per slot on the title screen
MAXIMUM_PLAYERS: Final = 4

# One colour per slot, far apart on the colour wheel and readable on black: ghoul green,
# pumpkin orange, seance violet, TV-glow cyan (feature plan 1, decisions table)
PLAYER_COLOURS: Final[tuple[tuple[int, int, int], ...]] = (
    (92, 230, 92),
    (255, 140, 26),
    (176, 97, 255),
    (51, 214, 255),
)


class DeviceKind(StrEnum):
    """What a player plays with."""

    KEYBOARD = 'keyboard'
    GAMEPAD = 'gamepad'


class DeviceIdentity(BaseModel):
    """One input device: the keyboard, or a gamepad by its SDL instance id."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    kind: DeviceKind
    # None for the keyboard; a gamepad's SDL instance id otherwise
    instance_id: int | None


class JoinedPlayer(BaseModel):
    """A device holding a player slot."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    slot_index: int
    device: DeviceIdentity


class JoinRoster(BaseModel):
    """Which device holds each of the four slots (None: the slot is free)."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    slots: tuple[JoinedPlayer | None, ...]

    @field_validator('slots')
    @classmethod
    def _has_one_entry_per_player(
        cls, slots: tuple[JoinedPlayer | None, ...]
    ) -> tuple[JoinedPlayer | None, ...]:
        """Refuse a roster without exactly one entry per player slot.

        Returns:
            The slots, unchanged.

        Raises:
            ValueError: When there are not exactly ``MAXIMUM_PLAYERS`` slots.

        """
        if len(slots) != MAXIMUM_PLAYERS:
            message = f'a roster has {MAXIMUM_PLAYERS} slots, got {len(slots)}'
            raise ValueError(message)
        return slots

    @classmethod
    def empty(cls) -> Self:
        """Return a roster with every slot free.

        Returns:
            The empty roster.

        """
        return cls(slots=(None,) * MAXIMUM_PLAYERS)

    @property
    def joined_players(self) -> tuple[JoinedPlayer, ...]:
        """The players holding slots, in slot order."""
        return tuple(player for player in self.slots if player is not None)

    @property
    def is_full(self) -> bool:
        """Whether every slot is taken."""
        return all(player is not None for player in self.slots)

    def holds(self, *, device: DeviceIdentity) -> bool:
        """Return whether a device holds a slot.

        Returns:
            True when the device holds a slot.

        """
        return any(player.device == device for player in self.joined_players)

    def join(self, *, device: DeviceIdentity) -> Self:
        """Return the roster with a device in the lowest free slot.

        Returns:
            The new roster, or this one when the device already holds a slot or none is free.

        """
        if self.holds(device=device) or self.is_full:
            return self
        slot_index = self.slots.index(None)
        slots = list(self.slots)
        slots[slot_index] = JoinedPlayer(slot_index=slot_index, device=device)
        return self.model_copy(update={'slots': tuple(slots)})

    def leave(self, *, device: DeviceIdentity) -> Self:
        """Return the roster with a device's slot freed.

        Returns:
            The new roster, or this one when the device held no slot.

        """
        if not self.holds(device=device):
            return self
        slots = tuple(
            None if player is not None and player.device == device else player
            for player in self.slots
        )
        return self.model_copy(update={'slots': slots})
