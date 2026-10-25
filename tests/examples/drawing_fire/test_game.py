"""Tests for the Drawing Fire scene, on real pygame (the dummy driver)."""

from __future__ import annotations

import pygame
import pytest

from glitchygames.camera import Camera2D
from glitchygames.display_mode import set_display_mode
from glitchygames.events import GAMEEVENT
from glitchygames.events.base import GameEvent
from glitchygames.examples import drawing_fire
from glitchygames.examples.drawing_fire import drawing as drawing_module
from glitchygames.examples.drawing_fire import game as drawing_fire_game
from glitchygames.examples.drawing_fire.battle import (
    ARMY_NAMES,
    SAND_PER_HIT,
    SOLDIERS_PER_SIDE,
    WALK_SPEED,
    Battle,
    Bullet,
    Side,
)
from glitchygames.examples.drawing_fire.drawing import ARMY_COLORS, ARMY_LIVERIES, PENCIL_COLOR
from glitchygames.examples.drawing_fire.drivers import ComputerSoldier
from glitchygames.examples.drawing_fire.game import (
    DRAW_LINES,
    NO_SOLDIER_ID,
    PAPER_COLOR,
    SEAT_CHANGED_SUBTYPE,
    SOLDIER_KILLED_SUBTYPE,
    VICTORY_SECONDS,
    DrawingFireScene,
    Phase,
    held_keys_line,
    seats_panel_lines,
)
from glitchygames.examples.drawing_fire.players import KEYBOARD, Device
from glitchygames.examples.drawing_fire.seat_drawing import (
    CARD_COLOR,
    NOTE_COLOR,
    SEAT_TAG_ABOVE_FEET_PIXELS,
    SEAT_TAG_STAGGER_PIXELS,
    join_note_rect,
    seat_card_rect,
    seats_panel_rect,
)
from glitchygames.examples.drawing_fire.seats import PlayerSeat, SeatChange, SeatLogEntry, Stage
from glitchygames.examples.drawing_fire.terrain import Terrain
from glitchygames.input.state import InputSnapshot, set_current_input
from glitchygames.randomness import reset_streams

SCREEN_SIZE = (800, 480)
TEST_SEED = 20261025


@pytest.fixture(autouse=True)
def display():
    """The game's display: 800x480."""
    if not pygame.get_init():
        pygame.init()
    surface = pygame.display.get_surface()
    if surface is None or surface.get_size() != SCREEN_SIZE:
        set_display_mode(size=SCREEN_SIZE)


@pytest.fixture
def scene():
    """A new battlefield, its random streams seeded."""
    reset_streams(seed=TEST_SEED)
    return DrawingFireScene(options={'input_mode': 'joystick'})


def test_the_scene_draws_paper_and_ground(scene):
    """The paper fills the screen and the ground line is pencilled on it."""
    scene.render(scene.screen)
    assert scene.screen.get_at((5, 5))[:3] == PAPER_COLOR
    ground_x = 400
    ground_y = round(scene.terrain.ground_y(ground_x))
    column = [scene.screen.get_at((ground_x, y))[:3] for y in range(ground_y - 2, ground_y + 3)]
    assert PENCIL_COLOR in column


def test_the_terrain_fits_the_screen_and_is_seeded(scene):
    """The terrain has a ground y per screen pixel, from the seeded stream."""
    assert len(scene.terrain.ground) == SCREEN_SIZE[0]
    reset_streams(seed=TEST_SEED)
    assert DrawingFireScene(options={'input_mode': 'joystick'}).terrain == scene.terrain


def test_main_runs_the_scene(mocker):
    """main() starts the engine with the Drawing Fire scene."""
    engine = mocker.patch.object(drawing_fire_game, 'GameEngine')
    drawing_fire.main()
    engine.assert_called_once_with(game=DrawingFireScene)
    engine.return_value.start.assert_called_once_with()


def test_the_scene_uses_the_sprite_group_it_is_given():
    """A given sprite group is the scene's group."""
    reset_streams(seed=TEST_SEED)
    groups = pygame.sprite.LayeredDirty()
    assert DrawingFireScene(options={'input_mode': 'joystick'}, groups=groups).all_sprites is groups


def kill_army(scene, side):
    """Take every soldier of an army out of the fight."""
    for soldier in scene.battle.soldiers:
        if soldier.side is side:
            soldier.health = 0


def test_the_scene_starts_in_battle_one_with_both_armies(scene):
    """A new scene is battle 1, in the battle phase, with every soldier standing."""
    assert scene.battle_number == 1
    assert scene.phase is Phase.BATTLE
    assert len(scene.battle.living(Side.PLATOON)) == SOLDIERS_PER_SIDE
    assert len(scene.battle.living(Side.BRIGADE)) == SOLDIERS_PER_SIDE


def test_the_battle_plays_itself_in_dt_tick(scene):
    """Stepping the scene moves the battle's clock and its soldiers."""
    starting_xs = [soldier.x for soldier in scene.battle.soldiers]
    for _ in range(60):
        scene.dt_tick(1 / 60)
    assert scene.battle.seconds == pytest.approx(1.0)
    assert [soldier.x for soldier in scene.battle.soldiers] != starting_xs


def test_a_win_announces_the_army_then_the_next_battle_starts(scene):
    """The victory message names the winner; after VICTORY_SECONDS battle 2 begins."""
    first_terrain = scene.terrain
    kill_army(scene, Side.BRIGADE)
    scene.dt_tick(1 / 60)
    assert scene.phase is Phase.VICTORY
    assert scene.victory_lines == (f'{ARMY_NAMES[Side.PLATOON]} wins!',)
    scene.dt_tick(VICTORY_SECONDS / 2)
    assert scene.battle_number == 1
    assert scene.phase is Phase.VICTORY
    scene.dt_tick(VICTORY_SECONDS)
    assert scene.battle_number == 2
    assert scene.phase is Phase.BATTLE
    assert not scene.victory_lines
    assert len(scene.battle.living(Side.BRIGADE)) == SOLDIERS_PER_SIDE
    assert scene.terrain != first_terrain


def last_two_standing_face_to_face(scene):
    """Leave one soldier a side, at health 1, facing each other on flat ground, ready to fire.

    The scene's battle is swapped for a one-a-side battle on flat ground (ids 0 and 1, whose
    minds and streams the scene already has), each soldier's target set and his reaction done.
    """
    flat = Terrain(width=SCREEN_SIZE[0], height=SCREEN_SIZE[1], ground=(400.0,) * SCREEN_SIZE[0])
    battle = Battle(terrain=flat, soldiers_per_side=1, sandbag_xs=())
    platoon, brigade = battle.soldiers
    platoon.x, brigade.x = 300.0, 500.0
    platoon.health = brigade.health = 1
    scene.battle = battle
    scene.terrain = flat
    scene.minds[platoon.soldier_id] = ComputerSoldier(target_id=brigade.soldier_id)
    scene.minds[brigade.soldier_id] = ComputerSoldier(target_id=platoon.soldier_id)


def test_a_draw_announces_nobody_wins_then_the_next_battle_starts(scene, mocker):
    """The last two soldiers shoot each other at once: a two-line draw banner, then battle 2."""
    last_two_standing_face_to_face(scene)
    lettered = mocker.spy(drawing_module, '_banner_surface')
    for _ in range(60):
        scene.dt_tick(1 / 60)
        if scene.phase is Phase.VICTORY:
            break
    assert scene.phase is Phase.VICTORY
    assert scene.battle.over
    assert scene.battle.winner is None
    assert scene.victory_lines == DRAW_LINES == ('Nobody wins!', 'Everybody loses!')
    scene.render(scene.screen)
    assert [call.args[0] for call in lettered.call_args_list] == list(DRAW_LINES)
    scene.dt_tick(VICTORY_SECONDS)
    assert scene.battle_number == 2
    assert scene.phase is Phase.BATTLE
    assert not scene.victory_lines


def test_the_victory_picture_holds_still(scene):
    """At the win, the bullets in flight are gone and nobody is drawn mid-stride."""
    for _ in range(30):
        scene.dt_tick(1 / 60)
    assert scene.walking_soldier_ids
    scene.battle.bullets.append(
        Bullet(
            x=400.0,
            y=60.0,
            velocity_x=600.0,
            velocity_y=0.0,
            side=Side.PLATOON,
            distance_left=100.0,
        )
    )
    kill_army(scene, Side.BRIGADE)
    scene.dt_tick(1 / 60)
    assert scene.phase is Phase.VICTORY
    assert not scene.battle.bullets
    assert not scene.walking_soldier_ids


def test_the_victory_message_is_drawn_on_the_paper(scene, mocker):
    """The announcement is pencilled in the sky, which was blank before."""
    sky = pygame.Rect(SCREEN_SIZE[0] // 4, 60, SCREEN_SIZE[0] // 2, SCREEN_SIZE[1] // 4)

    def sky_colors():
        return {
            tuple(scene.screen.get_at((x, y)))[:3]
            for x in range(sky.left, sky.right)
            for y in range(sky.top, sky.bottom)
        }

    scene.render(scene.screen)
    assert PENCIL_COLOR not in sky_colors()
    kill_army(scene, Side.PLATOON)
    scene.dt_tick(1 / 60)
    scene.render(scene.screen)
    assert PENCIL_COLOR in sky_colors()
    # The font is built once and kept
    font_constructor = mocker.spy(pygame.font, 'Font')
    scene.render(scene.screen)
    assert font_constructor.call_count == 0


def test_the_battle_is_drawn_in_each_armys_colour(scene):
    """Every living soldier's helmet is pencil yellow or graphite grey, where he stands."""
    scene.render(scene.screen)
    for soldier in scene.battle.soldiers:
        helmet = (round(soldier.x), round(soldier.y) - 34)
        assert tuple(scene.screen.get_at(helmet))[:3] == ARMY_COLORS[soldier.side]


def test_walking_soldiers_are_found_by_their_step(scene):
    """A soldier who walked this step is walking; one who stood still is not."""
    assert not scene.walking_soldier_ids
    for _ in range(30):
        scene.dt_tick(1 / 60)
    assert scene.walking_soldier_ids
    assert scene.walking_soldier_ids <= {soldier.soldier_id for soldier in scene.battle.soldiers}
    scene.start_battle()
    assert not scene.walking_soldier_ids


def test_bullets_and_sandbags_are_drawn(scene):
    """A bullet in flight is a pencil dash, and every sandbag is on the paper."""
    scene.render(scene.screen)
    blank = pygame.image.tobytes(scene.screen, 'RGB')
    bullet = Bullet(
        x=400.0, y=60.0, velocity_x=600.0, velocity_y=0.0, side=Side.PLATOON, distance_left=100.0
    )
    scene.battle.bullets.append(bullet)
    scene.render(scene.screen)
    assert tuple(scene.screen.get_at((396, 60)))[:3] == PENCIL_COLOR
    assert pygame.image.tobytes(scene.screen, 'RGB') != blank
    sandbag = scene.battle.sandbags[0]
    top = round(scene.terrain.ground_y(sandbag.x) - sandbag.height) + 4
    assert tuple(scene.screen.get_at((round(sandbag.x), top)))[:3] != PAPER_COLOR


def test_drawing_the_same_battle_twice_gives_the_same_picture(scene):
    """Nothing in the drawing is random."""
    for _ in range(90):
        scene.dt_tick(1 / 60)
    scene.render(scene.screen)
    first = pygame.image.tobytes(scene.screen, 'RGB')
    scene.render(scene.screen)
    assert pygame.image.tobytes(scene.screen, 'RGB') == first


def test_the_soldier_frames_are_scaled_once_for_the_scene(scene):
    """The scene keeps one set of frames, and each army's livery is built once."""
    frames = scene.soldier_frames
    scene.render(scene.screen)
    scheme_frames = frames.frames_for(ARMY_LIVERIES[Side.PLATOON])
    scene.render(scene.screen)
    assert scene.soldier_frames is frames
    assert frames.frames_for(ARMY_LIVERIES[Side.PLATOON]) is scheme_frames


def test_a_new_battle_redraws_the_ground(scene):
    """The ground line follows the new battle's terrain."""
    scene.start_battle()
    scene.render(scene.screen)
    ground_x = 400
    ground_y = round(scene.terrain.ground_y(ground_x))
    column = [scene.screen.get_at((ground_x, y))[:3] for y in range(ground_y - 2, ground_y + 3)]
    assert PENCIL_COLOR in column


def test_battles_replay_from_the_same_seed():
    """The same seed gives the same battle after the same ticks."""
    snapshots = []
    for _ in range(2):
        reset_streams(seed=TEST_SEED)
        scene = DrawingFireScene(options={'input_mode': 'joystick'})
        for _ in range(120):
            scene.dt_tick(1 / 60)
        snapshots.append([(soldier.x, soldier.health) for soldier in scene.battle.soldiers])
    assert snapshots[0] == snapshots[1]


# --- Seats: players join, choose, play and leave (milestones 2 and 3) ---

CONTROLLER_ID = 5
CONTROLLER_AXIS_COUNT = 6
CONTROLLER_BUTTON_COUNT = 21
FULL_DEFLECTION = 32767
# A soldier's helmet top is this far above his feet (px); the highlight's label and a pennant
# are drawn above it
HELMET_TOP_PIXELS = 36


def keyboard_input(*, scancodes=()):
    """Build a snapshot with these keyboard scancodes held and no controller.

    Returns:
        The snapshot.

    """
    return InputSnapshot(
        pressed_scancodes=frozenset(scancodes),
        modifiers=0,
        mouse_position=(0, 0),
        mouse_buttons=(False, False, False),
        mouse_focused=True,
    )


def controller_input(*, buttons=(), axes=None):
    """Build a snapshot with controller 5 plugged in, holding these buttons and axes.

    Returns:
        The snapshot.

    """
    axis_values = [0] * CONTROLLER_AXIS_COUNT
    for axis, value in (axes or {}).items():
        axis_values[axis] = value
    return InputSnapshot(
        pressed_scancodes=frozenset(),
        modifiers=0,
        mouse_position=(0, 0),
        mouse_buttons=(False, False, False),
        mouse_focused=True,
        controller_axes={CONTROLLER_ID: tuple(axis_values)},
        controller_buttons={
            CONTROLLER_ID: tuple(index in buttons for index in range(CONTROLLER_BUTTON_COUNT))
        },
    )


def tick_with(scene, snapshot, frames=1):
    """Make this the frame's input and step the scene that many frames."""
    set_current_input(snapshot=snapshot)
    for _ in range(frames):
        scene.dt_tick(1 / 60)


def keyboard_tap(scene, scancode):
    """Press a key for a frame, then let it go for a frame."""
    tick_with(scene, keyboard_input(scancodes={scancode}))
    tick_with(scene, keyboard_input())


def controller_tap(scene, button):
    """Press a controller button for a frame, then let it go for a frame."""
    tick_with(scene, controller_input(buttons={button}))
    tick_with(scene, controller_input())


def keyboard_joins_and_plays(scene):
    """The keyboard player presses Enter three times: join, a random side, the highlighted soldier.

    Returns:
        The player's seat, playing.

    """
    for _ in range(3):
        keyboard_tap(scene, pygame.KSCAN_RETURN)
    seat = scene.seats.seat_of(KEYBOARD)
    assert seat is not None
    assert seat.stage is Stage.PLAYING
    return seat


def colors_in(surface, rect):
    """Collect the colours in a rectangle of a surface.

    Returns:
        The set of (r, g, b) colours.

    """
    clipped = rect.clip(surface.get_rect())
    return {
        tuple(surface.get_at((x, y)))[:3]
        for x in range(clipped.left, clipped.right)
        for y in range(clipped.top, clipped.bottom)
    }


def test_the_join_prompt_shows_while_a_device_is_unseated(scene):
    """The sticky note is on the paper until every device (here the keyboard) has a seat."""
    note = join_note_rect(scene.screen)
    corner = (note.right - 3, note.bottom - 3)
    scene.render(scene.screen)
    assert tuple(scene.screen.get_at(corner))[:3] == NOTE_COLOR
    keyboard_tap(scene, pygame.KSCAN_RETURN)
    scene.render(scene.screen)
    assert tuple(scene.screen.get_at(corner))[:3] != NOTE_COLOR
    # A controller plugged in is a device without a seat: the note is back
    tick_with(scene, controller_input())
    scene.render(scene.screen)
    assert tuple(scene.screen.get_at(corner))[:3] == NOTE_COLOR


def test_a_player_choosing_a_side_sees_the_side_card(scene):
    """START opens a card beside the note; the soldier choice keeps a card, playing has none."""
    card = seat_card_rect(scene.screen, slot=0)
    scene.render(scene.screen)
    assert CARD_COLOR not in colors_in(scene.screen, card)
    keyboard_tap(scene, pygame.KSCAN_RETURN)
    scene.render(scene.screen)
    assert CARD_COLOR in colors_in(scene.screen, card)
    keyboard_tap(scene, pygame.KSCAN_RIGHT)
    scene.render(scene.screen)
    # The chosen line (Pencil Platoon) is marked with its army's colour
    assert ARMY_COLORS[Side.PLATOON] in colors_in(scene.screen, card)
    keyboard_tap(scene, pygame.KSCAN_RETURN)
    scene.render(scene.screen)
    assert CARD_COLOR in colors_in(scene.screen, card)
    keyboard_tap(scene, pygame.KSCAN_RETURN)
    scene.render(scene.screen)
    assert CARD_COLOR not in colors_in(scene.screen, card)


def test_a_waiting_player_has_a_card(scene):
    """A player who has no soldier yet is told he waits."""
    keyboard_tap(scene, pygame.KSCAN_RETURN)
    seat = scene.seats.seat_of(KEYBOARD)
    assert seat is not None
    kill_army(scene, Side.PLATOON)
    kill_army(scene, Side.BRIGADE)
    keyboard_tap(scene, pygame.KSCAN_RETURN)
    assert seat.stage is Stage.WAITING
    scene.render(scene.screen)
    assert CARD_COLOR in colors_in(scene.screen, seat_card_rect(scene.screen, slot=0))


def test_the_highlight_marks_the_soldier_being_chosen(scene):
    """In CHOOSING_SOLDIER a pencil ring and the player's name mark the highlighted soldier."""
    keyboard_tap(scene, pygame.KSCAN_RETURN)
    keyboard_tap(scene, pygame.KSCAN_RETURN)
    seat = scene.seats.seat_of(KEYBOARD)
    assert seat is not None
    assert seat.stage is Stage.CHOOSING_SOLDIER
    highlighted = scene.seats.highlighted_soldier(seat, battle=scene.battle)
    assert highlighted is not None
    above_head = pygame.Rect(0, 0, 40, 40)
    above_head.midbottom = (round(highlighted.x), round(highlighted.y) - HELMET_TOP_PIXELS - 8)
    scene.render(scene.screen)
    assert PENCIL_COLOR in colors_in(scene.screen, above_head)
    keyboard_tap(scene, pygame.KSCAN_RETURN)
    assert seat.stage is Stage.PLAYING
    scene.render(scene.screen)
    # Playing, he flies his pennant instead: his army's colour over his helmet
    assert ARMY_COLORS[highlighted.side] in colors_in(scene.screen, above_head)


def test_no_highlight_is_drawn_when_the_last_free_soldier_has_just_died(scene):
    """A chooser's side lost its free soldiers this step: the next update sends him to wait."""
    keyboard_tap(scene, pygame.KSCAN_RETURN)
    keyboard_tap(scene, pygame.KSCAN_RETURN)
    seat = scene.seats.seat_of(KEYBOARD)
    assert seat is not None
    assert seat.side is not None
    kill_army(scene, seat.side)
    scene.render(scene.screen)
    assert scene.seats.highlighted_soldier(seat, battle=scene.battle) is None
    tick_with(scene, keyboard_input())
    assert seat.stage is Stage.WAITING


def test_a_new_battle_highlights_a_soldier_in_it(scene):
    """The highlight is drawn over the new battle's soldier after battle_started."""
    seat = keyboard_joins_and_plays(scene)
    scene.start_battle()
    assert seat.stage is Stage.CHOOSING_SOLDIER
    highlighted = scene.seats.highlighted_soldier(seat, battle=scene.battle)
    assert highlighted is not None
    assert highlighted.soldier_id == seat.highlighted_soldier_id
    above_head = pygame.Rect(0, 0, 40, 40)
    above_head.midbottom = (round(highlighted.x), round(highlighted.y) - HELMET_TOP_PIXELS - 8)
    scene.render(scene.screen)
    assert PENCIL_COLOR in colors_in(scene.screen, above_head)


def test_a_joined_player_plays_the_next_battle(scene):
    """After the victory the player chooses a soldier of the same side in battle 2."""
    seat = keyboard_joins_and_plays(scene)
    side = seat.side
    assert side is not None
    soldier_id = seat.soldier_id
    assert soldier_id is not None
    kill_army(scene, side.opponent)
    tick_with(scene, keyboard_input())
    assert scene.phase is Phase.VICTORY
    # During the victory his soldier stands, still his, and START still opens a seat
    tick_with(scene, controller_input(buttons={pygame.CONTROLLER_BUTTON_START}))
    tick_with(scene, controller_input())
    assert scene.battle.soldier(soldier_id).alive
    assert scene.seats.driver_of(soldier_id) == seat.name
    second_seat = scene.seats.seat_of(Device(controller_id=CONTROLLER_ID))
    assert second_seat is not None
    assert second_seat.stage is Stage.CHOOSING_SIDE
    tick_with(scene, controller_input(), frames=round(VICTORY_SECONDS * 60) + 1)
    assert scene.battle_number == 2
    assert seat.stage is Stage.CHOOSING_SOLDIER
    assert seat.side is side
    assert seat.soldier_id is None


def test_the_scene_drives_a_players_soldier_from_their_device(scene):
    """A controller player on the Brigade pushes the left stick right: his soldier walks right."""
    controller_tap(scene, pygame.CONTROLLER_BUTTON_START)
    controller_tap(scene, pygame.CONTROLLER_BUTTON_DPAD_RIGHT)
    controller_tap(scene, pygame.CONTROLLER_BUTTON_DPAD_RIGHT)
    controller_tap(scene, pygame.CONTROLLER_BUTTON_START)
    controller_tap(scene, pygame.CONTROLLER_BUTTON_START)
    seat = scene.seats.seat_of(Device(controller_id=CONTROLLER_ID))
    assert seat is not None
    assert seat.stage is Stage.PLAYING
    assert seat.side is Side.BRIGADE
    assert seat.soldier_id is not None
    soldier = scene.battle.soldier(seat.soldier_id)
    start_x = soldier.x
    tick_with(
        scene, controller_input(axes={pygame.CONTROLLER_AXIS_LEFTX: FULL_DEFLECTION}), frames=30
    )
    # The computer would have walked him left, toward the Platoon
    assert soldier.x > start_x
    assert soldier.x == pytest.approx(start_x + 30 * WALK_SPEED / 60)
    # The computer keeps his mind thinking (a target) while the player drives him
    assert scene.minds[seat.soldier_id].target_id is not None


def test_an_unplugged_controller_hands_the_soldier_back_that_frame(scene):
    """Unplugged, the player leaves and the computer walks his soldier toward the enemy at once."""
    controller_tap(scene, pygame.CONTROLLER_BUTTON_START)
    controller_tap(scene, pygame.CONTROLLER_BUTTON_START)
    controller_tap(scene, pygame.CONTROLLER_BUTTON_START)
    seat = scene.seats.seat_of(Device(controller_id=CONTROLLER_ID))
    assert seat is not None
    assert seat.soldier_id is not None
    soldier = scene.battle.soldier(seat.soldier_id)
    tick_with(scene, controller_input(), frames=5)
    standing_x = soldier.x
    tick_with(scene, keyboard_input())
    assert scene.seats.players == {}
    assert scene.seats.driver_of(soldier.soldier_id) == 'CPU'
    toward_enemy = 1.0 if soldier.side is Side.PLATOON else -1.0
    assert (soldier.x - standing_x) * toward_enemy > 0


def test_a_players_death_moves_him_to_another_soldier(scene):
    """An enemy bullet kills the player's soldier: the scene hands him another of his side."""
    seat = keyboard_joins_and_plays(scene)
    assert seat.side is not None
    assert seat.soldier_id is not None
    soldier = scene.battle.soldier(seat.soldier_id)
    soldier.health = 1
    chest_x, chest_y = soldier.chest
    scene.battle.bullets.append(
        Bullet(
            x=chest_x - 1.0,
            y=chest_y,
            velocity_x=600.0,
            velocity_y=0.0,
            side=seat.side.opponent,
            distance_left=100.0,
        )
    )
    # A sandbag flattened in the same step moves no one
    sandbag = scene.battle.sandbags[0]
    sandbag.sand = SAND_PER_HIT
    sandbag_top = scene.terrain.ground_y(sandbag.x) - sandbag.height
    scene.battle.bullets.append(
        Bullet(
            x=sandbag.x,
            y=sandbag_top - 1.0,
            velocity_x=0.0,
            velocity_y=600.0,
            side=Side.PLATOON,
            distance_left=100.0,
        )
    )
    tick_with(scene, keyboard_input())
    assert sandbag.flattened
    assert not soldier.alive
    assert seat.stage is Stage.PLAYING
    assert seat.soldier_id != soldier.soldier_id
    assert scene.battle.soldier(seat.soldier_id).side is seat.side
    assert scene.seats.log[-1].text == f'{seat.name} died → soldier {seat.soldier_id}'


def test_seats_draw_only_from_their_own_stream(scene):
    """Joining, choosing a random side and taking a soldier never move a soldier's stream."""
    stream_states = {
        soldier_id: stream.getstate() for soldier_id, stream in scene.soldier_streams.items()
    }
    edges = scene.button_edges
    for held in ({pygame.KSCAN_RETURN}, set(), {pygame.KSCAN_RETURN}, set()):
        edges.update(keyboard_input(scancodes=held), dt=1 / 60)
        scene.seats.update(
            edges=edges, devices=(KEYBOARD,), battle=scene.battle, seconds=scene.game_time
        )
    seat = scene.seats.seat_of(KEYBOARD)
    assert seat is not None
    assert seat.side is not None
    assert {
        soldier_id: stream.getstate() for soldier_id, stream in scene.soldier_streams.items()
    } == stream_states


def test_the_seat_texts_are_rendered_once(scene, mocker):
    """The note, the card and the highlight's label make no font and render no text twice."""
    keyboard_tap(scene, pygame.KSCAN_RETURN)
    tick_with(scene, controller_input())
    scene.render(scene.screen)
    font_constructor = mocker.spy(pygame.font, 'Font')
    rendered = mocker.spy(drawing_module, '_font')
    scene.render(scene.screen)
    assert font_constructor.call_count == 0
    assert rendered.call_count == 0


def test_releasing_escape_never_quits_but_q_does(scene):
    """Escape is the keyboard's Back (held to leave a seat): its release must not quit; Q quits."""
    pygame.event.clear()  # the real queue: only this test's posts
    scene.record_key_press(key=pygame.K_ESCAPE)
    scene.on_key_up_event(
        pygame.event.Event(pygame.KEYUP, key=pygame.K_ESCAPE, scancode=pygame.KSCAN_ESCAPE, mod=0)
    )
    assert pygame.event.get(eventtype=pygame.QUIT) == []
    # The release still consumes its press, as every other key's does
    assert pygame.K_ESCAPE not in scene._keys_pressed_in_scene
    scene.record_key_press(key=pygame.K_q)
    scene.on_key_up_event(
        pygame.event.Event(pygame.KEYUP, key=pygame.K_q, scancode=pygame.KSCAN_Q, mod=0)
    )
    assert len(pygame.event.get(eventtype=pygame.QUIT)) == 1


# The debug overlay's pink, the colour of the seat tags' outline and the panel's
DEBUG_PINK = (212, 0, 106)


def living_count(scene, side):
    """Count a side's living soldiers.

    Returns:
        The count.

    """
    return len(scene.battle.living(side))


def pink_in(scene, rect):
    """Say whether the debug pink is anywhere in a rectangle of the scene's screen.

    Returns:
        Whether it is.

    """
    return DEBUG_PINK in colors_in(scene.screen, rect)


def test_the_panel_lists_each_army_its_drivers_and_the_seat_log(scene):
    """One keyboard player: his army shows him and its seven computer soldiers."""
    platoon_soldier = scene.battle.living(Side.PLATOON)[0]
    scene.seats.players['P1'] = PlayerSeat(
        name='P1',
        device=KEYBOARD,
        stage=Stage.PLAYING,
        side=Side.PLATOON,
        soldier_id=platoon_soldier.soldier_id,
    )
    scene.seats.log.append(
        SeatLogEntry(
            seconds=4.0,
            text='P1 START → random → PLATOON',
            change=SeatChange.SIDE_CHOSEN,
            player='P1',
        )
    )
    assert seats_panel_lines(scene.seats, scene.battle) == [
        'PLATOON  P1 · CPU ×7',  # ruff: ignore[ambiguous-unicode-character-string] - the panel's count sign, a multiplication sign (COMPUTER_COUNT_MARK)
        'BRIGADE  CPU ×8',  # ruff: ignore[ambiguous-unicode-character-string] - the panel's count sign, a multiplication sign (COMPUTER_COUNT_MARK)
        '0:04  P1 START → random → PLATOON',
    ]


def test_the_panel_counts_only_living_soldiers_and_formats_minutes(scene):
    """Dead soldiers are not counted; the log's times are m:ss."""
    scene.battle.soldier(0).health = 0
    scene.seats.log.append(
        SeatLogEntry(seconds=75.9, text='P1 left', change=SeatChange.LEFT, player='P1')
    )
    lines = seats_panel_lines(scene.seats, scene.battle)
    first_platoon_count = living_count(scene, Side.PLATOON)
    assert lines[0] == f'PLATOON  CPU ×{first_platoon_count}'  # ruff: ignore[ambiguous-unicode-character-string] - the panel's count sign, a multiplication sign (COMPUTER_COUNT_MARK)
    assert lines[-1] == '1:15  P1 left'


def test_an_army_with_no_computer_soldiers_shows_only_its_players(scene):
    """No computer soldiers left: the army's line is the players alone."""
    seat = keyboard_joins_and_plays(scene)
    assert seat.soldier_id is not None
    for soldier in scene.battle.living(seat.side):
        if soldier.soldier_id != seat.soldier_id:
            soldier.health = 0
    lines = seats_panel_lines(scene.seats, scene.battle)
    assert f'{seat.side.name}  P1' in lines
    assert not any('CPU' in line for line in lines if line.startswith(seat.side.name))


def test_an_army_with_neither_players_nor_soldiers_shows_no_computer_soldiers(scene):
    """A wiped-out army with no players still gets its line, CPU count 0."""
    kill_army(scene, Side.BRIGADE)
    expected = 'BRIGADE  CPU ×0'  # ruff: ignore[ambiguous-unicode-character-string] - the panel's count sign, a multiplication sign (COMPUTER_COUNT_MARK)
    assert expected in seats_panel_lines(scene.seats, scene.battle)


def test_waiting_and_choosing_players_are_listed_on_their_side_marked(scene):
    """A chooser and a waiting player are on their side's line, marked; one with no side is not."""
    scene.seats.players['P2'] = PlayerSeat(
        name='P2', device=Device(controller_id=2), stage=Stage.WAITING, side=Side.BRIGADE
    )
    scene.seats.players['P3'] = PlayerSeat(
        name='P3', device=Device(controller_id=3), stage=Stage.CHOOSING_SOLDIER, side=Side.PLATOON
    )
    scene.seats.players['P4'] = PlayerSeat(name='P4', device=Device(controller_id=4))
    lines = seats_panel_lines(scene.seats, scene.battle)
    assert lines[0] == 'PLATOON  P3 (choosing) · CPU ×8'  # ruff: ignore[ambiguous-unicode-character-string] - the panel's count sign, a multiplication sign (COMPUTER_COUNT_MARK)
    assert lines[1] == 'BRIGADE  P2 (waiting) · CPU ×8'  # ruff: ignore[ambiguous-unicode-character-string] - the panel's count sign, a multiplication sign (COMPUTER_COUNT_MARK)
    assert len(lines) == 2


def tag_area_over(soldier, *, raised, width=30):
    """Find the rectangle a soldier's tag fills (a little larger than the tag).

    Returns:
        The rectangle.

    """
    area = pygame.Rect(0, 0, width, 12)
    area.midbottom = (
        round(soldier.x),
        round(soldier.y) - SEAT_TAG_ABOVE_FEET_PIXELS - raised * SEAT_TAG_STAGGER_PIXELS,
    )
    return area


def test_the_debug_overlay_tags_every_living_soldier_and_draws_the_panel(scene):
    """debug_draw tags each living soldier with his driver and lists the seats in a corner."""
    keyboard_joins_and_plays(scene)
    scene.battle.soldier(0).health = 0
    scene.render(scene.screen)
    before = scene.screen.copy()
    scene.debug_draw(
        scene.screen, Camera2D(screen_width=SCREEN_SIZE[0], screen_height=SCREEN_SIZE[1])
    )
    standing = sorted(
        scene.battle.living(Side.PLATOON) + scene.battle.living(Side.BRIGADE),
        key=lambda soldier: (soldier.x, soldier.soldier_id),
    )
    for rank, soldier in enumerate(standing):
        assert pink_in(scene, tag_area_over(soldier, raised=rank % 2))
    # Where the fallen soldier stood there is no tag (a sliver, clear of his neighbours' tags)
    assert not pink_in(scene, tag_area_over(scene.battle.soldier(0), raised=0, width=4))
    corner = pygame.Rect(0, 0, 200, 100)
    corner.bottomright = scene.screen.get_rect().bottomright
    assert pink_in(scene, corner)
    assert not pink_in(scene, join_note_rect(scene.screen))
    assert before.get_at((0, 0)) == scene.screen.get_at((0, 0))


def test_held_keys_line_names_the_held_keys_and_mouse_buttons():
    """The held-keys line names keys by scancode (in scancode order), then the mouse buttons."""
    snapshot = InputSnapshot(
        pressed_scancodes=frozenset({pygame.KSCAN_ESCAPE, pygame.KSCAN_A}),
        modifiers=0,
        mouse_position=(0, 0),
        mouse_buttons=(True, False, True),
        mouse_focused=True,
    )
    assert held_keys_line(snapshot) == 'held: A ESCAPE mouse left mouse right'


def test_held_keys_line_says_when_nothing_is_held():
    """With no key or button held, the line says so instead of trailing off."""
    assert held_keys_line(keyboard_input()) == 'held: (nothing)'


def test_held_keys_line_shows_an_unnamed_scancode_as_its_number():
    """A scancode pygame has no KSCAN_ name for is shown as its number, never dropped."""
    unnamed = 499
    assert not any(
        getattr(pygame, name) == unnamed for name in dir(pygame) if name.startswith('KSCAN_')
    )
    assert held_keys_line(keyboard_input(scancodes=(unnamed,))) == 'held: 499'


def test_the_debug_panel_ends_with_the_held_keys(scene):
    """debug_draw's panel has one more line than the seats: the keys this frame's input holds."""
    keyboard_joins_and_plays(scene)
    set_current_input(snapshot=keyboard_input(scancodes=(pygame.KSCAN_ESCAPE,)))
    seat_lines = seats_panel_lines(scene.seats, scene.battle)
    with_held_keys = seats_panel_rect(scene.screen, lines=[*seat_lines, 'held: ESCAPE'])
    without_held_keys = seats_panel_rect(scene.screen, lines=seat_lines)
    assert with_held_keys.top < without_held_keys.top
    scene.render(scene.screen)
    scene.debug_draw(
        scene.screen, Camera2D(screen_width=SCREEN_SIZE[0], screen_height=SCREEN_SIZE[1])
    )
    # The panel's outline runs along the top of the taller panel, the one with the held keys
    outline_row = pygame.Rect(with_held_keys.left, with_held_keys.top, with_held_keys.width, 1)
    assert pink_in(scene, outline_row)


def test_the_panel_does_not_cover_the_join_note_or_cards(scene):
    """The panel's corner is the bottom right; the note and cards sit at the bottom left."""
    panel = seats_panel_rect(scene.screen, lines=['0:04  P1 START → random → PLATOON'] * 10)
    assert panel.right <= scene.screen.get_width()
    assert panel.bottom <= scene.screen.get_height()
    assert not panel.colliderect(join_note_rect(scene.screen))
    assert not panel.colliderect(seat_card_rect(scene.screen, slot=1))


def test_the_panel_spells_arrows_the_font_cannot_draw(scene):
    """The panel draws '->' for the log's arrow, so it is the width of the spelled-out text."""
    arrow_lines = ['P1 START → random → PLATOON']
    spelled_lines = ['P1 START -> random -> PLATOON']
    arrow_panel = seats_panel_rect(scene.screen, lines=arrow_lines)
    assert arrow_panel == seats_panel_rect(scene.screen, lines=spelled_lines)


def posted_game_events():
    """Drain SDL's queue and return the GAMEEVENTs in it, as dicts, in order.

    Returns:
        Each game event's attributes.

    """
    return [dict(event.dict) for event in pygame.event.get() if event.type == GAMEEVENT]


def test_a_death_and_a_takeover_are_posted_as_game_events(scene):
    """The player's soldier dies: a soldier-killed event naming him, then his takeover's."""
    seat = keyboard_joins_and_plays(scene)
    assert seat.side is not None
    assert seat.soldier_id is not None
    soldier = scene.battle.soldier(seat.soldier_id)
    soldier.health = 1
    chest_x, chest_y = soldier.chest
    scene.battle.bullets.append(
        Bullet(
            x=chest_x - 1.0,
            y=chest_y,
            velocity_x=600.0,
            velocity_y=0.0,
            side=seat.side.opponent,
            distance_left=100.0,
        )
    )
    pygame.event.clear()

    tick_with(scene, keyboard_input())

    assert posted_game_events() == [
        {
            'subtype': SOLDIER_KILLED_SUBTYPE,
            'soldier_id': soldier.soldier_id,
            'side': seat.side.value,
            'driver': seat.name,
        },
        {
            'subtype': SEAT_CHANGED_SUBTYPE,
            'change': SeatChange.TOOK_OVER.value,
            'player': seat.name,
            'soldier_id': seat.soldier_id,
            'text': f'{seat.name} died → soldier {seat.soldier_id}',
        },
    ]


def test_every_seat_log_entry_is_posted_once(scene):
    """Joining posts the side choice (no soldier) and the soldier taken, each once."""
    pygame.event.clear()
    seat = keyboard_joins_and_plays(scene)
    assert seat.side is not None

    seat_events = [
        event for event in posted_game_events() if event['subtype'] == SEAT_CHANGED_SUBTYPE
    ]

    assert [(event['change'], event['soldier_id']) for event in seat_events] == [
        (SeatChange.SIDE_CHOSEN.value, NO_SOLDIER_ID),
        (SeatChange.TOOK_SOLDIER.value, seat.soldier_id),
    ]
    assert [event['text'] for event in seat_events] == [entry.text for entry in scene.seats.log]
    assert scene.seats.take_new_entries() == []


def test_setup_registers_the_scenes_own_game_events(scene, mocker):
    """setup() registers each of the scene's subtypes, with a callback that takes the marker."""
    register = mocker.patch.object(scene.scene_manager, 'register_game_event')
    scene.setup()
    registered = {
        call.kwargs['event_type']: call.kwargs['callback'] for call in register.call_args_list
    }
    assert set(registered) == {SOLDIER_KILLED_SUBTYPE, SEAT_CHANGED_SUBTYPE}
    for subtype, callback in registered.items():
        assert callback(GameEvent(GAMEEVENT, subtype=subtype)) is None
