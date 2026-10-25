"""Tests for Drawing Fire's seats: joining, choosing a soldier, death takeovers and leaving."""

from __future__ import annotations

import random

import pygame
import pytest

from glitchygames.examples.drawing_fire.battle import Battle, Side
from glitchygames.examples.drawing_fire.players import KEYBOARD, Button, ButtonEdges, Device
from glitchygames.examples.drawing_fire.seats import (
    COMPUTER_DRIVER_NAME,
    LEAVE_HOLD_FRAMES,
    SEAT_LOG_LENGTH,
    PlayerSeat,
    SeatLogEntry,
    Seats,
    SideChoice,
    Stage,
)
from glitchygames.examples.drawing_fire.terrain import Terrain
from glitchygames.input.state import InputSnapshot

FIELD_WIDTH = 800
FIELD_HEIGHT = 480
FLAT_GROUND_Y = 400.0
SOLDIERS_PER_SIDE = 8
SEATS_SEED = 20261025
CONTROLLER_AXIS_COUNT = 6
CONTROLLER_BUTTON_COUNT = 21
CONTROLLER = Device(controller_id=3)
SECOND_CONTROLLER = Device(controller_id=4)

KEYBOARD_SCANCODES = {
    Button.START: pygame.KSCAN_RETURN,
    Button.BACK: pygame.KSCAN_ESCAPE,
    Button.LEFT: pygame.KSCAN_LEFT,
    Button.RIGHT: pygame.KSCAN_RIGHT,
}
CONTROLLER_BUTTONS = {
    Button.START: pygame.CONTROLLER_BUTTON_START,
    Button.BACK: pygame.CONTROLLER_BUTTON_BACK,
    Button.LEFT: pygame.CONTROLLER_BUTTON_DPAD_LEFT,
    Button.RIGHT: pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
}


def flat_battle() -> Battle:
    """Build a full battle (eight a side) on flat ground, with no sandbags.

    Returns:
        The battle.

    """
    terrain = Terrain(width=FIELD_WIDTH, height=FIELD_HEIGHT, ground=(FLAT_GROUND_Y,) * FIELD_WIDTH)
    return Battle(terrain=terrain, soldiers_per_side=SOLDIERS_PER_SIDE, sandbag_xs=())


def button_snapshot(*, held: dict[Device, set[Button]], controllers: tuple[Device, ...]):
    """Build a snapshot with these buttons held, on the keyboard and the plugged-in controllers.

    Returns:
        The snapshot.

    """
    scancodes = frozenset(KEYBOARD_SCANCODES[button] for button in held.get(KEYBOARD, set()))
    controller_axes = {}
    controller_buttons = {}
    for controller in controllers:
        assert controller.controller_id is not None
        indices = {CONTROLLER_BUTTONS[button] for button in held.get(controller, set())}
        controller_axes[controller.controller_id] = (0,) * CONTROLLER_AXIS_COUNT
        controller_buttons[controller.controller_id] = tuple(
            index in indices for index in range(CONTROLLER_BUTTON_COUNT)
        )
    return InputSnapshot(
        pressed_scancodes=scancodes,
        modifiers=0,
        mouse_position=(0, 0),
        mouse_buttons=(False, False, False),
        mouse_focused=True,
        controller_axes=controller_axes,
        controller_buttons=controller_buttons,
    )


class SeatsRig:
    """Seats over a flat battle, fed frame by frame with buttons held on real snapshots."""

    def __init__(self, *, controllers: tuple[Device, ...] = (), seed: int = SEATS_SEED) -> None:
        """Seat nobody yet; the keyboard and these controllers are plugged in."""
        self.seats = Seats(random=random.Random(seed))
        self.edges = ButtonEdges()
        self.battle = flat_battle()
        self.controllers = controllers
        self.seconds = 0.0

    def frame(self, held: dict[Device, set[Button]] | None = None) -> None:
        """Run one frame of the seats with these buttons held."""
        snapshot = button_snapshot(held=held or {}, controllers=self.controllers)
        self.edges.update(snapshot)
        devices = (KEYBOARD, *self.controllers)
        self.seats.update(
            edges=self.edges, devices=devices, battle=self.battle, seconds=self.seconds
        )
        self.seconds += 1 / 60

    def tap(self, device: Device, button: Button) -> None:
        """Press a button for one frame, then let it go."""
        self.frame({device: {button}})
        self.frame()

    def join(self, device: Device, *, side_presses: int = 0) -> PlayerSeat:
        """Press START, press RIGHT this many times on the side card and confirm.

        Returns:
            The player's seat, in CHOOSING_SOLDIER (or WAITING).

        """
        self.tap(device, Button.START)
        for _ in range(side_presses):
            self.tap(device, Button.RIGHT)
        self.tap(device, Button.START)
        seat = self.seats.seat_of(device)
        assert seat is not None
        return seat

    def take_highlighted(self, device: Device) -> int:
        """Take the soldier the player's highlight is on.

        Returns:
            The soldier's id.

        """
        self.tap(device, Button.START)
        seat = self.seats.seat_of(device)
        assert seat is not None
        assert seat.stage is Stage.PLAYING
        assert seat.soldier_id is not None
        return seat.soldier_id

    def kill(self, soldier_id: int) -> None:
        """Kill a soldier and tell the seats."""
        self.battle.soldier(soldier_id).health = 0
        self.seats.soldier_killed(soldier_id=soldier_id, battle=self.battle, seconds=self.seconds)

    def log_texts(self) -> list[str]:
        """The seat log's texts, oldest first.

        Returns:
            The texts.

        """
        return [entry.text for entry in self.seats.log]


def nearest_the_middle(battle: Battle, side: Side) -> int:
    """Find the side's living soldier nearest the middle of the field.

    Returns:
        His id.

    """
    middle = battle.terrain.width / 2
    return min(battle.living(side), key=lambda soldier: abs(soldier.x - middle)).soldier_id


def test_start_then_confirm_joins_a_random_side_and_takes_a_soldier():
    """START opens the side card, START draws a side from the seats stream, START takes one."""
    rig = SeatsRig()
    assert rig.seats.players == {}
    rig.tap(KEYBOARD, Button.START)
    seat = rig.seats.seat_of(KEYBOARD)
    assert seat is not None
    assert seat.name == 'P1'
    assert seat.stage is Stage.CHOOSING_SIDE
    assert seat.side_choice is SideChoice.RANDOM
    assert seat.side is None
    rig.tap(KEYBOARD, Button.START)
    assert seat.stage is Stage.CHOOSING_SOLDIER
    assert seat.side is not None
    assert seat.side is random.Random(SEATS_SEED).choice(list(Side))
    assert rig.log_texts()[-1] == f'P1 START → random → {seat.side.name}'
    # The highlight starts on the soldier nearest the middle of the field
    highlighted = rig.seats.highlighted_soldier(seat, battle=rig.battle)
    assert highlighted is not None
    assert highlighted.soldier_id == nearest_the_middle(rig.battle, seat.side)
    soldier_id = rig.take_highlighted(KEYBOARD)
    assert soldier_id == highlighted.soldier_id
    assert rig.seats.driver_of(soldier_id) == 'P1'
    assert rig.log_texts()[-1] == f'P1 took soldier {soldier_id}'
    assert isinstance(rig.seats.log[-1], SeatLogEntry)
    assert rig.seats.log[-1].seconds == pytest.approx(rig.seconds - 2 / 60)


def test_a_player_cannot_take_another_players_soldier():
    """A second player's highlight cycles over the computer's soldiers only."""
    rig = SeatsRig(controllers=(CONTROLLER,))
    rig.join(KEYBOARD, side_presses=1)
    first_soldier = rig.take_highlighted(KEYBOARD)
    seat = rig.join(CONTROLLER, side_presses=1)
    assert seat.name == 'P2'
    assert seat.side is Side.PLATOON
    highlighted_ids = set()
    for _ in range(SOLDIERS_PER_SIDE * 2):
        highlighted = rig.seats.highlighted_soldier(seat, battle=rig.battle)
        assert highlighted is not None
        highlighted_ids.add(highlighted.soldier_id)
        rig.tap(CONTROLLER, Button.RIGHT)
    assert first_soldier not in highlighted_ids
    assert len(highlighted_ids) == SOLDIERS_PER_SIDE - 1
    second_soldier = rig.take_highlighted(CONTROLLER)
    assert second_soldier != first_soldier
    assert rig.seats.driver_of(first_soldier) == 'P1'
    assert rig.seats.driver_of(second_soldier) == 'P2'


def test_the_highlight_cycles_left_and_right_in_order_across_the_field():
    """RIGHT moves the highlight to the next soldier to the right, LEFT back, wrapping round."""
    rig = SeatsRig()
    seat = rig.join(KEYBOARD, side_presses=2)
    assert seat.side is Side.BRIGADE

    def highlighted_x() -> float:
        highlighted = rig.seats.highlighted_soldier(seat, battle=rig.battle)
        assert highlighted is not None
        return highlighted.x

    start_x = highlighted_x()
    rig.tap(KEYBOARD, Button.RIGHT)
    assert highlighted_x() > start_x
    rig.tap(KEYBOARD, Button.LEFT)
    assert highlighted_x() == start_x
    # The Brigade's soldier nearest the middle is its leftmost: LEFT wraps to its rightmost
    rig.tap(KEYBOARD, Button.LEFT)
    assert highlighted_x() == max(soldier.x for soldier in rig.battle.living(Side.BRIGADE))


def test_the_side_card_cycles_and_a_chosen_side_is_kept():
    """LEFT and RIGHT cycle Random, Platoon, Brigade (wrapping); a chosen side is that side."""
    rig = SeatsRig()
    rig.tap(KEYBOARD, Button.START)
    seat = rig.seats.seat_of(KEYBOARD)
    assert seat is not None
    # No side yet, so no soldier to highlight
    assert rig.seats.highlighted_soldier(seat, battle=rig.battle) is None
    rig.tap(KEYBOARD, Button.LEFT)
    assert seat.side_choice is SideChoice.BRIGADE
    rig.tap(KEYBOARD, Button.RIGHT)
    assert seat.side_choice is SideChoice.RANDOM
    rig.tap(KEYBOARD, Button.RIGHT)
    assert seat.side_choice is SideChoice.PLATOON
    rig.tap(KEYBOARD, Button.START)
    assert seat.side is Side.PLATOON
    assert seat.stage is Stage.CHOOSING_SOLDIER
    assert rig.log_texts()[-1] == 'P1 START → PLATOON'


def test_the_start_that_opens_a_seat_does_not_also_confirm_it():
    """Holding START after joining stays on the side card; a seated device opens no second seat."""
    rig = SeatsRig()
    for _ in range(5):
        rig.frame({KEYBOARD: {Button.START}})
    seat = rig.seats.seat_of(KEYBOARD)
    assert seat is not None
    assert seat.stage is Stage.CHOOSING_SIDE
    rig.frame()
    rig.join(KEYBOARD)
    rig.take_highlighted(KEYBOARD)
    rig.tap(KEYBOARD, Button.START)
    assert list(rig.seats.players) == ['P1']
    assert seat.stage is Stage.PLAYING


def test_death_moves_the_player_to_a_random_soldier_of_their_side():
    """He takes a computer soldier of his side drawn from the seats stream: same seed, same one."""
    taken = []
    for _ in range(2):
        rig = SeatsRig()
        seat = rig.join(KEYBOARD, side_presses=1)
        first_soldier = rig.take_highlighted(KEYBOARD)
        rig.kill(first_soldier)
        assert seat.stage is Stage.PLAYING
        assert seat.soldier_id is not None
        assert seat.soldier_id != first_soldier
        new_soldier = rig.battle.soldier(seat.soldier_id)
        assert new_soldier.alive
        assert new_soldier.side is Side.PLATOON
        assert rig.seats.driver_of(first_soldier) == COMPUTER_DRIVER_NAME
        assert rig.seats.driver_of(seat.soldier_id) == 'P1'
        assert rig.log_texts()[-1] == f'P1 died → soldier {seat.soldier_id}'
        taken.append(seat.soldier_id)
    assert taken[0] == taken[1]


def test_a_computer_soldiers_death_moves_no_one():
    """A soldier no player drives dies: every seat stays where it was."""
    rig = SeatsRig()
    seat = rig.join(KEYBOARD, side_presses=1)
    soldier_id = rig.take_highlighted(KEYBOARD)
    log_length = len(rig.seats.log)
    other = next(
        soldier.soldier_id
        for soldier in rig.battle.living(Side.BRIGADE)
        if soldier.soldier_id != soldier_id
    )
    rig.kill(other)
    assert seat.soldier_id == soldier_id
    assert len(rig.seats.log) == log_length


def test_a_death_with_no_free_soldier_waits():
    """With his side's others dead or a player's, he waits, then takes the next one freed."""
    rig = SeatsRig(controllers=(CONTROLLER,))
    seat = rig.join(KEYBOARD, side_presses=1)
    first_soldier = rig.take_highlighted(KEYBOARD)
    second_seat = rig.join(CONTROLLER, side_presses=1)
    second_soldier = rig.take_highlighted(CONTROLLER)
    for soldier in rig.battle.living(Side.PLATOON):
        if soldier.soldier_id not in {first_soldier, second_soldier}:
            soldier.health = 0
    rig.kill(first_soldier)
    assert seat.stage is Stage.WAITING
    assert seat.soldier_id is None
    assert rig.log_texts()[-1] == 'P1 died → waiting'
    # Waiting stays waiting while nothing frees up
    rig.frame()
    assert seat.stage is Stage.WAITING
    # P2 leaves: his soldier is the next free one, and P1 takes him
    for _ in range(LEAVE_HOLD_FRAMES):
        rig.frame({CONTROLLER: {Button.BACK}})
    assert rig.seats.seat_of(CONTROLLER) is None
    assert second_seat.name not in rig.seats.players
    assert seat.stage is Stage.PLAYING
    assert seat.soldier_id == second_soldier
    assert rig.seats.driver_of(second_soldier) == 'P1'
    assert rig.log_texts()[-2:] == ['P2 left', f'P1 took soldier {second_soldier}']


def test_choosing_a_soldier_with_none_free_waits():
    """A player who confirms a side with no computer soldier left on it waits."""
    rig = SeatsRig(controllers=(CONTROLLER,))
    for soldier in rig.battle.living(Side.PLATOON)[1:]:
        soldier.health = 0
    rig.join(KEYBOARD, side_presses=1)
    rig.take_highlighted(KEYBOARD)
    # The Platoon's one soldier is P1's
    seat = rig.join(CONTROLLER, side_presses=1)
    assert seat.stage is Stage.WAITING
    assert rig.log_texts()[-1] == 'P2 waits for a soldier'
    assert rig.seats.highlighted_soldier(seat, battle=rig.battle) is None


def test_a_chooser_whose_last_free_soldier_is_taken_waits():
    """Two choose on one side with one free soldier: the first takes him, the other waits."""
    rig = SeatsRig(controllers=(CONTROLLER,))
    for soldier in rig.battle.living(Side.PLATOON)[1:]:
        soldier.health = 0
    first_seat = rig.join(KEYBOARD, side_presses=1)
    second_seat = rig.join(CONTROLLER, side_presses=1)
    assert second_seat.stage is Stage.CHOOSING_SOLDIER
    rig.take_highlighted(KEYBOARD)
    assert first_seat.stage is Stage.PLAYING
    assert second_seat.stage is Stage.WAITING


def test_holding_back_leaves_and_returns_the_soldier_to_the_computer():
    """BACK held for LEAVE_HOLD_FRAMES frames frees the seat and its name."""
    rig = SeatsRig()
    rig.join(KEYBOARD)
    soldier_id = rig.take_highlighted(KEYBOARD)
    for _ in range(LEAVE_HOLD_FRAMES - 1):
        rig.frame({KEYBOARD: {Button.BACK}})
    assert rig.seats.driver_of(soldier_id) == 'P1'
    rig.frame({KEYBOARD: {Button.BACK}})
    assert rig.seats.seat_of(KEYBOARD) is None
    assert rig.seats.driver_of(soldier_id) == COMPUTER_DRIVER_NAME
    assert rig.log_texts()[-1] == 'P1 left'
    # Still holding BACK does nothing more; letting go and pressing START is a new join as P1
    rig.frame({KEYBOARD: {Button.BACK}})
    rig.frame()
    rig.tap(KEYBOARD, Button.START)
    seat = rig.seats.seat_of(KEYBOARD)
    assert seat is not None
    assert seat.name == 'P1'


def test_an_unplugged_controller_leaves():
    """A controller missing from the devices leaves that frame; its soldier is the computer's."""
    rig = SeatsRig(controllers=(CONTROLLER,))
    rig.join(CONTROLLER)
    soldier_id = rig.take_highlighted(CONTROLLER)
    assert rig.seats.driver_of(soldier_id) == 'P1'
    rig.controllers = ()
    rig.frame()
    assert rig.seats.players == {}
    assert rig.seats.driver_of(soldier_id) == COMPUTER_DRIVER_NAME
    assert rig.log_texts()[-1] == 'P1 left'


def test_the_lowest_free_name_is_taken():
    """With P1 gone and P2 still seated, the next player is P1 again, then P3."""
    rig = SeatsRig(controllers=(CONTROLLER, SECOND_CONTROLLER))
    rig.tap(CONTROLLER, Button.START)
    rig.tap(SECOND_CONTROLLER, Button.START)
    rig.controllers = (SECOND_CONTROLLER,)
    rig.frame()
    assert list(rig.seats.players) == ['P2']
    rig.tap(KEYBOARD, Button.START)
    # Plugged back in, the controller is a new join
    rig.controllers = (CONTROLLER, SECOND_CONTROLLER)
    rig.tap(CONTROLLER, Button.START)
    names = {seat.device: name for name, seat in rig.seats.players.items()}
    assert names == {SECOND_CONTROLLER: 'P2', KEYBOARD: 'P1', CONTROLLER: 'P3'}


def test_the_seat_log_keeps_the_last_entries():
    """The log holds the last SEAT_LOG_LENGTH joins, takeovers and leaves."""
    rig = SeatsRig()
    for _ in range(SEAT_LOG_LENGTH):
        rig.tap(KEYBOARD, Button.START)
        rig.tap(KEYBOARD, Button.START)
        for _ in range(LEAVE_HOLD_FRAMES):
            rig.frame({KEYBOARD: {Button.BACK}})
        rig.frame()
    assert len(rig.seats.log) == SEAT_LOG_LENGTH
    assert rig.log_texts()[-1] == 'P1 left'


def test_choosing_when_the_battle_ends_waits_for_the_next():
    """An army falls while a player chooses: he waits, then chooses in the next battle."""
    rig = SeatsRig(controllers=(CONTROLLER,))
    seat = rig.join(KEYBOARD, side_presses=1)
    assert seat.stage is Stage.CHOOSING_SOLDIER
    rig.tap(CONTROLLER, Button.START)
    side_seat = rig.seats.seat_of(CONTROLLER)
    assert side_seat is not None
    for soldier in rig.battle.living(Side.BRIGADE):
        rig.kill(soldier.soldier_id)
    assert rig.battle.winner is Side.PLATOON
    rig.frame()
    assert seat.stage is Stage.WAITING
    assert seat.soldier_id is None
    assert rig.log_texts()[-1] == 'P1 waits for the next battle'
    # START does nothing while waiting; the side card still works and its choice waits too
    rig.tap(KEYBOARD, Button.START)
    assert seat.stage is Stage.WAITING
    rig.tap(CONTROLLER, Button.START)
    assert side_seat.stage is Stage.WAITING
    assert side_seat.side is not None
    # The next battle: both choose a soldier of their side again
    rig.battle = flat_battle()
    rig.seats.battle_started(battle=rig.battle)
    assert seat.stage is Stage.CHOOSING_SOLDIER
    assert seat.side is Side.PLATOON
    assert side_seat.stage is Stage.CHOOSING_SOLDIER
    highlighted = rig.seats.highlighted_soldier(seat, battle=rig.battle)
    assert highlighted is not None
    assert highlighted.soldier_id == nearest_the_middle(rig.battle, Side.PLATOON)


def test_a_player_still_choosing_a_side_keeps_choosing_in_the_next_battle():
    """battle_started moves only players with a side; the side card stays open."""
    rig = SeatsRig()
    rig.tap(KEYBOARD, Button.START)
    seat = rig.seats.seat_of(KEYBOARD)
    assert seat is not None
    rig.seats.battle_started(battle=flat_battle())
    assert seat.stage is Stage.CHOOSING_SIDE


def test_two_players_on_opposite_sides():
    """Milestone 3: P1 on the keyboard plays the Platoon, P2 on a controller the Brigade."""
    rig = SeatsRig(controllers=(CONTROLLER,))
    first_seat = rig.join(KEYBOARD, side_presses=1)
    second_seat = rig.join(CONTROLLER, side_presses=2)
    first_soldier = rig.take_highlighted(KEYBOARD)
    second_soldier = rig.take_highlighted(CONTROLLER)
    assert (first_seat.name, first_seat.side, first_seat.stage) == (
        'P1',
        Side.PLATOON,
        Stage.PLAYING,
    )
    assert (second_seat.name, second_seat.side, second_seat.stage) == (
        'P2',
        Side.BRIGADE,
        Stage.PLAYING,
    )
    assert rig.battle.soldier(first_soldier).side is Side.PLATOON
    assert rig.battle.soldier(second_soldier).side is Side.BRIGADE
    assert rig.seats.driver_of(first_soldier) == 'P1'
    assert rig.seats.driver_of(second_soldier) == 'P2'


def test_two_players_on_the_same_side():
    """Both players play the Platoon, each with his own soldier."""
    rig = SeatsRig(controllers=(CONTROLLER,))
    rig.join(KEYBOARD, side_presses=1)
    rig.join(CONTROLLER, side_presses=1)
    first_soldier = rig.take_highlighted(KEYBOARD)
    second_soldier = rig.take_highlighted(CONTROLLER)
    assert first_soldier != second_soldier
    for soldier_id in (first_soldier, second_soldier):
        assert rig.battle.soldier(soldier_id).side is Side.PLATOON
    drivers = {rig.seats.driver_of(soldier.soldier_id) for soldier in rig.battle.soldiers}
    assert drivers == {'P1', 'P2', COMPUTER_DRIVER_NAME}
