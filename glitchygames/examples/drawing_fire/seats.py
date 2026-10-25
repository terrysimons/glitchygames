"""Seats: players join a running battle, choose a side and a soldier, take over and leave.

A player presses START on a device with no seat, chooses a side (Random by default, then the
Pencil Platoon or the Graphite Brigade), then chooses one of that side's computer soldiers and
drives him. When he dies the player takes another of his side, picked from the seats' own random
stream (or waits when there is none). Holding BACK, or unplugging the controller, leaves, and the
soldier goes back to the computer at once.

Nothing here draws or reads pygame input: it works on ``ButtonEdges`` and ``Device``s, and its
only randomness is the stream it is given, so a seat changing hands never shifts a soldier's
stream.
"""

from __future__ import annotations

import collections
import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING

from glitchygames.examples.drawing_fire.battle import Side
from glitchygames.examples.drawing_fire.players import Button

if TYPE_CHECKING:
    import random
    from collections.abc import Sequence

    from glitchygames.examples.drawing_fire.battle import Battle, Soldier
    from glitchygames.examples.drawing_fire.players import ButtonEdges, Device

# BACK held this many frames (a second at 60 fps) leaves
LEAVE_HOLD_FRAMES = 60
# The seat log keeps this many of the latest joins, takeovers and leaves
SEAT_LOG_LENGTH = 8
# driver_of names the computer this way
COMPUTER_DRIVER_NAME = 'CPU'
PLAYER_NAME_PREFIX = 'P'


class Stage(enum.Enum):
    """Where a player is: choosing a side, choosing a soldier, playing, or waiting for one."""

    CHOOSING_SIDE = enum.auto()
    CHOOSING_SOLDIER = enum.auto()
    PLAYING = enum.auto()
    WAITING = enum.auto()


class SideChoice(enum.Enum):
    """The side card's lines, in the order LEFT and RIGHT cycle them."""

    RANDOM = enum.auto()
    PLATOON = enum.auto()
    BRIGADE = enum.auto()


SIDE_CHOICES = tuple(SideChoice)
CHOSEN_SIDES = {SideChoice.PLATOON: Side.PLATOON, SideChoice.BRIGADE: Side.BRIGADE}


@dataclass
class PlayerSeat:
    """One player: his name, his device, and where he is in joining and playing."""

    name: str
    device: Device
    stage: Stage = Stage.CHOOSING_SIDE
    side: Side | None = None
    soldier_id: int | None = None
    # The soldier the highlight is on while he chooses: kept by id, so it stays on that soldier
    # whoever overtakes him or dies beside him
    highlighted_soldier_id: int | None = None
    side_choice: SideChoice = SideChoice.RANDOM
    # Whether BACK has been up since the seat opened: a BACK still held from leaving a seat
    # never counts toward leaving this one
    back_released: bool = True


class SeatChange(enum.StrEnum):
    """What a seat log entry records."""

    SIDE_CHOSEN = 'side_chosen'
    TOOK_SOLDIER = 'took_soldier'
    # His soldier died and he took over another of his side
    TOOK_OVER = 'took_over'
    # His soldier died and none of his side was free
    DIED_WAITING = 'died_waiting'
    WAITING = 'waiting'
    LEFT = 'left'


@dataclass(frozen=True)
class SeatLogEntry:
    """A join, takeover or leave, and when it happened (the scene's game time).

    Attributes:
        seconds: The scene's game time.
        text: The panel's line (``P1 died → soldier 4``).
        change: What happened.
        player: The player it happened to (his name).
        soldier_id: The soldier he took, when he took one; else None.

    """

    seconds: float
    text: str
    change: SeatChange
    player: str
    soldier_id: int | None = None


class Seats:
    """Every player's seat, and the log of joins, takeovers and leaves."""

    def __init__(self, *, random: random.Random) -> None:
        """Seat nobody yet.

        Args:
            random: The seats' own stream (the scene's ``random_stream('drawing_fire.seats')``):
                random sides and the soldier taken over on a death are drawn from it alone.

        """
        self.random = random
        self.players: dict[str, PlayerSeat] = {}
        self.log: collections.deque[SeatLogEntry] = collections.deque(maxlen=SEAT_LOG_LENGTH)
        # Every entry since the scene last took them (take_new_entries), uncapped
        self._new_entries: list[SeatLogEntry] = []

    def seat_of(self, device: Device) -> PlayerSeat | None:
        """Find the seat a device has (a device has at most one).

        Returns:
            The seat, or None when the device has none.

        """
        return next((seat for seat in self.players.values() if seat.device == device), None)

    def driver_of(self, soldier_id: int) -> str:
        """Name who drives a soldier.

        Returns:
            The playing player's name, or ``COMPUTER_DRIVER_NAME``.

        """
        for seat in self.players.values():
            if seat.stage is Stage.PLAYING and seat.soldier_id == soldier_id:
                return seat.name
        return COMPUTER_DRIVER_NAME

    def free_soldiers(self, side: Side, *, battle: Battle) -> list[Soldier]:
        """Find a side's living soldiers the computer drives, left to right.

        Returns:
            The soldiers a player may take.

        """
        return sorted(
            (
                soldier
                for soldier in battle.living(side)
                if self.driver_of(soldier.soldier_id) == COMPUTER_DRIVER_NAME
            ),
            key=lambda soldier: (soldier.x, soldier.soldier_id),
        )

    def highlighted_soldier(self, seat: PlayerSeat, *, battle: Battle) -> Soldier | None:
        """Find the soldier a choosing player's highlight is on.

        While the highlighted soldier is free, it is him. Once he dies or is taken, it is the
        free soldier nearest where he stands (and with no highlight yet, the one nearest the
        field's middle).

        Returns:
            The soldier, or None when the player has no side or it has no free soldier.

        """
        if seat.side is None:
            return None
        candidates = self.free_soldiers(seat.side, battle=battle)
        for candidate in candidates:
            if candidate.soldier_id == seat.highlighted_soldier_id:
                return candidate
        if not candidates:
            return None
        if seat.highlighted_soldier_id is None:
            near_x = battle.terrain.width / 2
        else:
            near_x = battle.soldier(seat.highlighted_soldier_id).x
        return min(candidates, key=lambda soldier: (abs(soldier.x - near_x), soldier.soldier_id))

    def update(
        self, *, edges: ButtonEdges, devices: Sequence[Device], battle: Battle, seconds: float
    ) -> None:
        """Play one frame of the seats: leaves first, then each device's buttons.

        Each device does at most one thing a frame, so the START that opens a seat never also
        confirms its side.

        Args:
            edges: This frame's button presses and holds.
            devices: The devices plugged in (the keyboard first).
            battle: The battle being fought.
            seconds: The scene's game time, for the log.

        """
        for seat in list(self.players.values()):
            back_frames = edges.held_frames(seat.device, Button.BACK)
            if back_frames == 0:
                seat.back_released = True
            if seat.device not in devices or (
                seat.back_released and back_frames >= LEAVE_HOLD_FRAMES
            ):
                self._leave(seat, battle=battle, seconds=seconds)
        for device in devices:
            seat = self.seat_of(device)
            if seat is None:
                if edges.pressed(device, Button.START):
                    self._open_seat(device, back_held=edges.held_frames(device, Button.BACK) > 0)
            elif seat.stage is Stage.CHOOSING_SIDE:
                self._choose_side(seat, edges=edges, battle=battle, seconds=seconds)
            elif seat.stage is Stage.CHOOSING_SOLDIER:
                self._choose_soldier(seat, edges=edges, battle=battle, seconds=seconds)

    def soldier_killed(self, *, soldier_id: int, battle: Battle, seconds: float) -> None:
        """Move the player whose soldier died to a random computer soldier of his side.

        Args:
            soldier_id: The soldier who died.
            battle: The battle.
            seconds: The scene's game time, for the log.

        """
        seat = next(
            (
                seat
                for seat in self.players.values()
                if seat.stage is Stage.PLAYING and seat.soldier_id == soldier_id
            ),
            None,
        )
        if seat is None or seat.side is None:
            return
        # Ordered by id, so the draw from the seats' stream depends on no one's position
        candidates = sorted(
            self.free_soldiers(seat.side, battle=battle), key=lambda soldier: soldier.soldier_id
        )
        if not candidates:
            seat.stage = Stage.WAITING
            seat.soldier_id = None
            self._record(
                seconds=seconds,
                text=f'{seat.name} died → waiting',
                change=SeatChange.DIED_WAITING,
                player=seat.name,
            )
            return
        seat.soldier_id = self.random.choice(candidates).soldier_id
        self._record(
            seconds=seconds,
            text=f'{seat.name} died → soldier {seat.soldier_id}',
            change=SeatChange.TOOK_OVER,
            player=seat.name,
            soldier_id=seat.soldier_id,
        )

    def battle_started(self, *, battle: Battle) -> None:
        """Send every player who has a side back to choosing a soldier of it in the new battle.

        Args:
            battle: The new battle.

        """
        choosers = [seat for seat in self.players.values() if seat.side is not None]
        for seat in choosers:
            seat.stage = Stage.CHOOSING_SOLDIER
            seat.soldier_id = None
            seat.highlighted_soldier_id = None
        # One at a time, so each chooser starts on a soldier no one before him is on
        for seat in choosers:
            seat.highlighted_soldier_id = self._starting_soldier_id(seat, battle=battle)

    def _open_seat(self, device: Device, *, back_held: bool) -> None:
        """Seat a device under the lowest free name, on the side card at Random."""
        number = 1
        while f'{PLAYER_NAME_PREFIX}{number}' in self.players:
            number += 1
        name = f'{PLAYER_NAME_PREFIX}{number}'
        self.players[name] = PlayerSeat(name=name, device=device, back_released=not back_held)

    def _choose_side(
        self, seat: PlayerSeat, *, edges: ButtonEdges, battle: Battle, seconds: float
    ) -> None:
        """Cycle the side card with LEFT and RIGHT; START confirms (Random draws a side)."""
        step = _left_right_step(edges=edges, device=seat.device)
        if step:
            index = SIDE_CHOICES.index(seat.side_choice)
            seat.side_choice = SIDE_CHOICES[(index + step) % len(SIDE_CHOICES)]
            return
        if not edges.pressed(seat.device, Button.START):
            return
        if seat.side_choice is SideChoice.RANDOM:
            side = self.random.choice(list(Side))
            self._record(
                seconds=seconds,
                text=f'{seat.name} START → random → {side.name}',
                change=SeatChange.SIDE_CHOSEN,
                player=seat.name,
            )
        else:
            side = CHOSEN_SIDES[seat.side_choice]
            self._record(
                seconds=seconds,
                text=f'{seat.name} START → {side.name}',
                change=SeatChange.SIDE_CHOSEN,
                player=seat.name,
            )
        seat.side = side
        seat.stage = Stage.CHOOSING_SOLDIER
        seat.highlighted_soldier_id = self._starting_soldier_id(seat, battle=battle)
        self._wait_if_nothing_to_choose(seat, battle=battle, seconds=seconds)

    def _choose_soldier(
        self, seat: PlayerSeat, *, edges: ButtonEdges, battle: Battle, seconds: float
    ) -> None:
        """Move the highlight with LEFT and RIGHT; START takes the highlighted soldier."""
        if self._wait_if_nothing_to_choose(seat, battle=battle, seconds=seconds):
            return
        assert seat.side is not None  # only a player with a side chooses a soldier
        soldier = self.highlighted_soldier(seat, battle=battle)
        assert soldier is not None  # _wait_if_nothing_to_choose found a free soldier
        # LEFT and RIGHT step from where he is among the free soldiers, left to right
        step = _left_right_step(edges=edges, device=seat.device)
        if step:
            candidates = self.free_soldiers(seat.side, battle=battle)
            soldier = candidates[(candidates.index(soldier) + step) % len(candidates)]
        seat.highlighted_soldier_id = soldier.soldier_id
        if not edges.pressed(seat.device, Button.START):
            return
        seat.stage = Stage.PLAYING
        seat.soldier_id = soldier.soldier_id
        self._record(
            seconds=seconds,
            text=f'{seat.name} took soldier {soldier.soldier_id}',
            change=SeatChange.TOOK_SOLDIER,
            player=seat.name,
            soldier_id=soldier.soldier_id,
        )

    def _wait_if_nothing_to_choose(
        self, seat: PlayerSeat, *, battle: Battle, seconds: float
    ) -> bool:
        """Send a chooser to WAITING when the battle is over or his side has no free soldier.

        Returns:
            Whether he now waits.

        """
        assert seat.side is not None  # only a player with a side chooses a soldier
        if battle.winner is not None:
            text = f'{seat.name} waits for the next battle'
        elif not self.free_soldiers(seat.side, battle=battle):
            text = f'{seat.name} waits for a soldier'
        else:
            return False
        seat.stage = Stage.WAITING
        self._record(seconds=seconds, text=text, change=SeatChange.WAITING, player=seat.name)
        return True

    def _leave(self, seat: PlayerSeat, *, battle: Battle, seconds: float) -> None:
        """Free a seat and its name; his soldier goes to a waiting player of his side, if any."""
        del self.players[seat.name]
        self._record(
            seconds=seconds, text=f'{seat.name} left', change=SeatChange.LEFT, player=seat.name
        )
        if seat.stage is not Stage.PLAYING or seat.soldier_id is None:
            return
        # His soldier is the next one free: the first player of his side waiting takes him
        waiting = next(
            (
                other
                for other in self.players.values()
                if other.stage is Stage.WAITING and other.side is seat.side
            ),
            None,
        )
        # After a win the battle is over: a waiter waits for the next battle, not this soldier
        if waiting is not None and battle.winner is None and battle.soldier(seat.soldier_id).alive:
            waiting.stage = Stage.PLAYING
            waiting.soldier_id = seat.soldier_id
            self._record(
                seconds=seconds,
                text=f'{waiting.name} took soldier {seat.soldier_id}',
                change=SeatChange.TOOK_SOLDIER,
                player=waiting.name,
                soldier_id=seat.soldier_id,
            )

    def _starting_soldier_id(self, seat: PlayerSeat, *, battle: Battle) -> int | None:
        """Find where a chooser's highlight starts: the free soldier nearest the field's middle.

        A soldier another chooser of his side is on is passed over while another is free, so
        two rings (and their names) are never drawn over one soldier.

        Returns:
            The soldier's id, or None when his side has no free soldier.

        """
        assert seat.side is not None  # only a player with a side chooses a soldier
        candidates = self.free_soldiers(seat.side, battle=battle)
        others_on = {
            other.highlighted_soldier_id
            for other in self.players.values()
            if other is not seat
            and other.stage is Stage.CHOOSING_SOLDIER
            and other.side is seat.side
        }
        unclaimed = [soldier for soldier in candidates if soldier.soldier_id not in others_on]
        middle = battle.terrain.width / 2
        start = min(
            unclaimed or candidates,
            key=lambda soldier: (abs(soldier.x - middle), soldier.soldier_id),
            default=None,
        )
        return None if start is None else start.soldier_id

    def take_new_entries(self) -> list[SeatLogEntry]:
        """Hand over the entries recorded since the last call (the scene posts them as events).

        Returns:
            The new entries, oldest first; the next call starts empty.

        """
        new_entries, self._new_entries = self._new_entries, []
        return new_entries

    def _record(
        self,
        *,
        seconds: float,
        text: str,
        change: SeatChange,
        player: str,
        soldier_id: int | None = None,
    ) -> None:
        """Add an entry to the seat log and to the new entries."""
        entry = SeatLogEntry(
            seconds=seconds, text=text, change=change, player=player, soldier_id=soldier_id
        )
        self.log.append(entry)
        self._new_entries.append(entry)


def _left_right_step(*, edges: ButtonEdges, device: Device) -> int:
    """Read a press of LEFT (-1) or RIGHT (1) this frame.

    Returns:
        -1, 1, or 0 for neither (or both).

    """
    return int(edges.pressed(device, Button.RIGHT)) - int(edges.pressed(device, Button.LEFT))
