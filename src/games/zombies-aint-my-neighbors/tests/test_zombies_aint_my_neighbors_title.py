"""The title screen: four slots blinking PRESS START, each in its player's colour.

Real pygame and the real display (800x480); what is drawn is checked by its pixels. Frames are
stepped as the scene manager steps them: game time advances, then ``dt_tick`` runs.
"""

from __future__ import annotations

import contextlib
import importlib
import itertools
import json
from typing import TYPE_CHECKING, Any

import pygame
import pytest

from glitchygames.events.base import HashableEvent
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene
from tests.input.stand_in_devices import STAND_IN_PAD
from zombies_aint_my_neighbors import text
from zombies_aint_my_neighbors.roster import (
    MAXIMUM_PLAYERS,
    PLAYER_COLOURS,
    DeviceIdentity,
    DeviceKind,
    JoinRoster,
)
from zombies_aint_my_neighbors.title import BLINK_SECONDS, TitleScene

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytest_mock import MockerFixture

    from glitchygames.replay.tools.golden_traces import GoldenTraceEngine

support = importlib.import_module('src.games.zombies-aint-my-neighbors.tests.screen_support')
SCREEN_SIZE = support.SCREEN_SIZE
FRAME_SECONDS = support.FRAME_SECONDS
KEYBOARD = support.KEYBOARD
gamepad = support.gamepad
tick_to = support.tick_to
rendered = support.rendered
exact_colour_count = support.exact_colour_count
joined_devices = support.joined_devices
press_key = support.press_key
controller_start = support.controller_start
joystick_start = support.joystick_start
plug_in_the_pad = support.plug_in_the_pad


@pytest.fixture
def scene() -> TitleScene:
    """A title screen, set up as the scene manager sets it up."""
    title = TitleScene(options={'input_mode': 'auto', 'no_unhandled_events': True})
    title.setup()
    return title


@contextlib.contextmanager
def running_title(**options: Any) -> Generator[tuple[GoldenTraceEngine, TitleScene]]:
    """Start the title on the real engine with a stand-in pad (screen_support.running_game).

    Yields:
        The engine and the title scene.

    """
    with support.running_game(scene_class=TitleScene, **options) as (engine, title):
        yield engine, title


def slot_shown(scene: TitleScene) -> list[bool]:
    """Return whether each slot's picture is shown.

    Returns:
        One flag per slot.

    """
    return [bool(picture.visible) for picture in scene.slot_pictures]


def test_each_unjoined_slot_shows_press_start_in_its_players_colour(scene):
    """Every slot draws in its own player's colour, and no other player's colour."""
    tick_to(scene, seconds=BLINK_SECONDS / 2)
    screen = rendered(scene)

    assert len(scene.slot_pictures) == MAXIMUM_PLAYERS
    for slot_index, picture in enumerate(scene.slot_pictures):
        for other_index, colour in enumerate(PLAYER_COLOURS):
            count = exact_colour_count(screen, picture.rect, colour)
            if other_index == slot_index:
                assert count > 0, f'slot {slot_index + 1} shows no pixels of its colour'
            else:
                assert count == 0, f'slot {slot_index + 1} shows player {other_index + 1}'


def test_the_slots_sit_side_by_side_without_overlapping(scene):
    """The four slots are laid out left to right in the bottom quarter of the screen."""
    rects = [picture.rect for picture in scene.slot_pictures]

    assert [rect.centerx for rect in rects] == sorted(rect.centerx for rect in rects)
    for left, right in itertools.pairwise(rects):
        assert left.right <= right.left
    for rect in rects:
        assert rect.top >= SCREEN_SIZE[1] * 3 // 4 - 1
        assert rect.bottom <= SCREEN_SIZE[1]


def test_unjoined_slots_blink_together_every_half_second(scene):
    """Shown for half a second, hidden for half a second, all four in step."""
    tick_to(scene, seconds=0.25)
    assert slot_shown(scene) == [True] * MAXIMUM_PLAYERS
    tick_to(scene, seconds=0.75)
    assert slot_shown(scene) == [False] * MAXIMUM_PLAYERS
    tick_to(scene, seconds=1.25)
    assert slot_shown(scene) == [True] * MAXIMUM_PLAYERS


def test_a_hidden_slot_draws_nothing(scene):
    """While hidden, a slot's area shows none of its colour."""
    tick_to(scene, seconds=0.75)
    screen = rendered(scene)

    for slot_index, picture in enumerate(scene.slot_pictures):
        assert exact_colour_count(screen, picture.rect, PLAYER_COLOURS[slot_index]) == 0


def test_a_joined_slot_is_steady():
    """A joined player's slot stays shown while the free slots blink."""
    first_pad = DeviceIdentity(kind=DeviceKind.GAMEPAD, instance_id=1)
    second_pad = DeviceIdentity(kind=DeviceKind.GAMEPAD, instance_id=3)
    # The second pad holds slot 2 (P2) once the first pad, in slot 1, has left
    roster = JoinRoster.empty().join(device=first_pad).join(device=second_pad)
    roster = roster.leave(device=first_pad)
    scene = TitleScene(options={'input_mode': 'joystick'}, roster=roster)
    scene.setup()

    tick_to(scene, seconds=0.75)

    assert slot_shown(scene) == [False, True, False, False]


def test_replay_arguments_rebuild_the_title_with_the_same_roster_through_json():
    """A replay rebuilds the title from its arguments as JSON gives them back (scene.py)."""
    roster = JoinRoster.empty().join(device=DeviceIdentity(kind=DeviceKind.GAMEPAD, instance_id=5))
    scene = TitleScene(options={'input_mode': 'joystick'}, roster=roster)

    arguments = json.loads(json.dumps(scene.replay_arguments()))
    rebuilt = TitleScene(options={'input_mode': 'joystick'}, **arguments)

    assert rebuilt.roster == roster


def test_the_title_scene_renders_no_text_after_setup(scene, mocker: MockerFixture):
    """Every text image is made in setup(); playing never renders text (decision 11)."""
    spy = mocker.spy(text, 'render_text')

    tick_to(scene, seconds=2.0)
    rendered(scene)

    assert spy.call_count == 0


def test_the_background_is_black(scene):
    """The title sets its background explicitly (black, not the TV test pattern)."""
    screen = rendered(scene)

    assert tuple(screen.get_at((2, 2)))[:3] == (0, 0, 0)


# --- Joining (feature plan 1, Task 4) ---------------------------------------------------------


def test_enter_joins_the_keyboard_in_slot_one(scene):
    """Enter is the keyboard's start: the keyboard takes the first free slot."""
    press_key(scene, pygame.K_RETURN)

    assert joined_devices(scene) == [KEYBOARD, None, None, None]


def test_keypad_enter_also_joins_the_keyboard(scene):
    """The keypad's Enter is the keyboard's start too."""
    press_key(scene, pygame.K_KP_ENTER)

    assert joined_devices(scene) == [KEYBOARD, None, None, None]


def test_a_controller_start_joins_that_pad(scene):
    """START on a mapped pad joins that pad, by its instance id."""
    press_key(scene, pygame.K_RETURN)
    controller_start(scene, instance_id=9)

    assert joined_devices(scene) == [KEYBOARD, gamepad(9), None, None]


def test_a_joystick_start_joins_that_pad_in_joystick_mode(scene):
    """START arriving on the joystick layer joins the pad the same way."""
    joystick_start(scene, instance_id=4)

    assert joined_devices(scene) == [gamepad(4), None, None, None]


@pytest.mark.parametrize('key', [pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_a, pygame.K_q])
def test_space_escape_and_other_keys_never_join(scene, key):
    """Only Enter joins from the keyboard; Space and Esc belong to the engine's screens."""
    press_key(scene, key)

    assert joined_devices(scene) == [None, None, None, None]


@pytest.mark.parametrize('button', [pygame.CONTROLLER_BUTTON_A, pygame.CONTROLLER_BUTTON_BACK])
def test_other_pad_buttons_never_join(scene, button):
    """Only START joins from a pad, on either layer."""
    scene.on_controller_button_down_event(
        HashableEvent(pygame.CONTROLLERBUTTONDOWN, instance_id=2, button=button)
    )
    scene.on_joy_button_down_event(
        HashableEvent(pygame.JOYBUTTONDOWN, instance_id=3, joy=3, button=button)
    )

    assert joined_devices(scene) == [None, None, None, None]


def test_a_pad_and_the_keyboard_on_the_same_frame_both_join_in_event_order(scene):
    """Two presses before the next frame both join, in the order they arrived (Review Focus 2)."""
    controller_start(scene, instance_id=6)
    press_key(scene, pygame.K_RETURN)
    tick_to(scene, seconds=FRAME_SECONDS)

    assert joined_devices(scene) == [gamepad(6), KEYBOARD, None, None]


def test_a_joined_slot_shows_ready_steadily_after_the_press(scene):
    """Once joined, a slot stops blinking from the next frame."""
    press_key(scene, pygame.K_RETURN)

    tick_to(scene, seconds=0.75)

    assert slot_shown(scene) == [True, False, False, False]


def test_p_pauses(scene):
    """P pauses the title (the shared pause screen resumes with Space)."""
    press_key(scene, pygame.K_p)

    assert isinstance(scene.next_scene, PauseScene)


def test_a_pad_plugged_in_before_the_game_starts_can_join():
    """A pad the title was never told about (no on_input_device_added) joins on START.

    Review Focus 4: pads plugged in before the game starts are never announced to the scene
    (game_engine.py: "no scene is running yet to be told"), so joining reads the press's
    instance id alone.
    """
    with running_title(plugged_in_at_start=True) as (_engine, title):
        controller_start(title, instance_id=STAND_IN_PAD.instance_id)

        assert joined_devices(title) == [gamepad(STAND_IN_PAD.instance_id), None, None, None]


def test_unplugging_a_pad_frees_its_slot_and_its_slot_blinks_again():
    """A pad that is unplugged gives up its slot, which goes back to PRESS START."""
    with running_title(plugged_in_at_start=False) as (engine, title):
        plug_in_the_pad(engine)
        pad_id = STAND_IN_PAD.instance_id
        controller_start(title, instance_id=pad_id)
        assert joined_devices(title) == [gamepad(pad_id), None, None, None]

        engine.process_joystick_event(HashableEvent(pygame.JOYDEVICEREMOVED, instance_id=pad_id))
        engine.process_controller_event(
            HashableEvent(pygame.CONTROLLERDEVICEREMOVED, instance_id=pad_id)
        )
        tick_to(title, seconds=0.75)

        assert joined_devices(title) == [None, None, None, None]
        assert slot_shown(title) == [False, False, False, False]


@pytest.mark.parametrize('input_mode', ['auto', 'joystick'])
def test_raw_device_events_are_handled_under_no_unhandled_events(input_mode):
    """Plugging, remapping and unplugging a pad raises nothing (Review Focus 5)."""
    with running_title(input_mode=input_mode, plugged_in_at_start=False) as (engine, title):
        pad_id = STAND_IN_PAD.instance_id
        plug_in_the_pad(engine)
        engine.process_controller_event(
            HashableEvent(pygame.CONTROLLERDEVICEREMAPPED, instance_id=pad_id)
        )
        engine.process_joystick_event(HashableEvent(pygame.JOYDEVICEREMOVED, instance_id=pad_id))
        engine.process_controller_event(
            HashableEvent(pygame.CONTROLLERDEVICEREMOVED, instance_id=pad_id)
        )

        assert joined_devices(title) == [None, None, None, None]


def test_sticks_hats_trackballs_touchpads_and_sensors_are_ignored():
    """Moving anything on a pad raises nothing and joins nobody, even with unhandled events on."""
    title = TitleScene(options={'input_mode': 'auto', 'no_unhandled_events': True})
    title.setup()

    title.on_joy_axis_motion_event(
        HashableEvent(pygame.JOYAXISMOTION, instance_id=1, joy=1, axis=0, value=0.5)
    )
    title.on_joy_ball_motion_event(
        HashableEvent(pygame.JOYBALLMOTION, instance_id=1, joy=1, ball=0, rel=(1, 0))
    )
    title.on_joy_hat_motion_event(
        HashableEvent(pygame.JOYHATMOTION, instance_id=1, joy=1, hat=0, value=(1, 0))
    )
    title.on_controller_axis_motion_event(
        HashableEvent(pygame.CONTROLLERAXISMOTION, instance_id=2, axis=0, value=1000)
    )
    for event_type, handler in (
        (pygame.CONTROLLERTOUCHPADDOWN, title.on_controller_touchpad_down_event),
        (pygame.CONTROLLERTOUCHPADMOTION, title.on_controller_touchpad_motion_event),
        (pygame.CONTROLLERTOUCHPADUP, title.on_controller_touchpad_up_event),
    ):
        handler(
            HashableEvent(
                event_type, instance_id=2, touchpad=0, finger=0, x=0.5, y=0.5, pressure=1.0
            )
        )
    title.on_controller_sensor_update_event(
        HashableEvent(pygame.CONTROLLERSENSORUPDATE, instance_id=2, sensor=1, data=(0.0, 0.0, 0.0))
    )

    assert joined_devices(title) == [None, None, None, None]


@pytest.mark.parametrize(
    ('input_mode', 'controller_joins', 'joystick_joins'),
    [('auto', True, True), ('joystick', False, True), ('controller', True, False)],
)
def test_start_follows_the_engines_input_mode(input_mode, controller_joins, joystick_joins):
    """A pad's START is read on the layers the engine delivers in each input mode.

    In joystick mode the engine blocks controller events, and in controller mode it drops the
    joystick layer's (game_engine.py, input modes), so the map binds only what can arrive.
    """
    title = TitleScene(options={'input_mode': input_mode, 'no_unhandled_events': True})
    title.setup()

    controller_start(title, instance_id=1)
    joystick_start(title, instance_id=2)

    expected = [
        device
        for device, joins in ((gamepad(1), controller_joins), (gamepad(2), joystick_joins))
        if joins
    ]
    assert [device for device in joined_devices(title) if device is not None] == expected


def test_setting_the_title_up_again_after_a_pause_keeps_one_set_of_sprites(scene):
    """Resuming from the pause screen sets the title up again; it makes no second set."""
    sprites_before = set(scene.all_sprites.sprites())

    scene.setup()

    assert set(scene.all_sprites.sprites()) == sprites_before


def test_a_font_that_never_fits_falls_back_to_the_smallest_size():
    """When no size fits the width, the smallest size is used (text clips rather than fails)."""
    font = text.fitted_title_font(texts=('PRESS START',), width=1, largest=24)

    assert font.get_height() == text.title_font(size=text.SMALLEST_FONT_SIZE).get_height()


def test_a_pad_unplugged_while_paused_frees_its_slot_on_resume():
    """The pause screen hears an unplug, not the title; resuming still frees the pad's slot.

    The engine tells only the active scene that a device left (SceneManager
    .on_input_device_removed), so a pad unplugged on the pause screen would otherwise keep its
    slot for the rest of the run, and, replugged with a new instance id, could not rejoin a
    full roster (final review, Important 1).
    """
    # The engine's PauseScene leaves the unplug unhandled (Engine wishlist #10), so this path
    # runs without --no-unhandled-events
    with running_title(plugged_in_at_start=False, unhandled_events_raise=False) as (
        engine,
        title,
    ):
        plug_in_the_pad(engine)
        controller_start(title, instance_id=STAND_IN_PAD.instance_id)
        press_key(title, pygame.K_RETURN)
        press_key(title, pygame.K_p)
        pause_screen = title.next_scene
        assert isinstance(pause_screen, PauseScene)
        engine.scene_manager.switch_to_scene(pause_screen)

        support.unplug_the_pad(engine)
        engine.scene_manager.switch_to_scene(title)
        # The resumed title's first frame
        rendered(title)

        # The pad's slot is free; the keyboard, never unplugged, keeps its slot
        assert joined_devices(title) == [None, KEYBOARD, None, None]


def test_pausing_and_resuming_keeps_every_connected_player():
    """A pause and a resume, with nothing unplugged, changes nobody's slot."""
    with running_title(plugged_in_at_start=False, unhandled_events_raise=False) as (
        engine,
        title,
    ):
        plug_in_the_pad(engine)
        controller_start(title, instance_id=STAND_IN_PAD.instance_id)
        press_key(title, pygame.K_p)
        engine.scene_manager.switch_to_scene(title.next_scene)

        engine.scene_manager.switch_to_scene(title)
        rendered(title)

        assert joined_devices(title) == [gamepad(STAND_IN_PAD.instance_id), None, None, None]


# The launch showing (feature plan 12, task 4): the opening title hands over to the intro on its
# first frame wherever the CRT power-on would play. The test harness turns the power-on off for
# every run (tests/sdl_defaults.py), so these pass --crt-power-on auto, which wins over it, and
# stand in a real video driver for the dummy one.
LAUNCH_OPTIONS = {'input_mode': 'auto', 'no_unhandled_events': True, 'crt_power_on': 'auto'}


def launching_title(mocker: MockerFixture, *, driver: str = 'cocoa', **options: Any) -> TitleScene:
    """Return an opening title as it starts on a driver someone can see, set up.

    Returns:
        The scene.
    """
    mocker.patch(
        'zombies_aint_my_neighbors.launch_showing.current_video_driver', return_value=driver
    )
    title = TitleScene(options={**LAUNCH_OPTIONS, **options})
    title.setup()
    return title


def test_the_opening_title_hands_over_to_the_intro_at_launch(mocker: MockerFixture):
    """On its first frame the opening title starts the intro, showing at launch."""
    from zombies_aint_my_neighbors.intro import IntroScene, IntroShowing

    title = launching_title(mocker)

    tick_to(title, seconds=FRAME_SECONDS)

    assert isinstance(title.next_scene, IntroScene)
    assert title.next_scene.showing is IntroShowing.LAUNCH


def test_the_launch_showing_plays_at_every_launch(mocker: MockerFixture):
    """Two launches in turn: each opening title starts the intro (nothing remembers the first)."""
    from zombies_aint_my_neighbors.intro import IntroScene

    for _ in range(2):
        title = launching_title(mocker)
        tick_to(title, seconds=FRAME_SECONDS)
        assert isinstance(title.next_scene, IntroScene)


@pytest.mark.parametrize(
    ('driver', 'options'),
    [
        ('dummy', {}),
        ('cocoa', {'replay_trace': 'run.jsonl.gz'}),
        ('cocoa', {'record_trace': 'run.jsonl.gz'}),
        ('cocoa', {'audit': ['run.jsonl.gz']}),
        ('cocoa', {'rebaseline': 'new.jsonl.gz'}),
        ('cocoa', {'crt_power_on': 'off'}),
    ],
    ids=['dummy-driver', 'replay', 'record', 'audit', 'rebaseline', 'power-on-off'],
)
def test_the_launch_showing_is_skipped_where_the_power_on_is(
    mocker: MockerFixture, driver: str, options: dict[str, Any]
):
    """Where the CRT power-on would not play, the opening title stays the title."""
    title = launching_title(mocker, driver=driver, **options)

    tick_to(title, seconds=1.0)

    assert title.next_scene is None


def test_a_title_that_is_not_the_opening_one_never_plays_the_intro(mocker: MockerFixture):
    """A title built after the launch (opening=False) stays the title, and replays as one."""
    mocker.patch(
        'zombies_aint_my_neighbors.launch_showing.current_video_driver', return_value='cocoa'
    )
    title = TitleScene(options=dict(LAUNCH_OPTIONS), opening=False)
    title.setup()

    tick_to(title, seconds=1.0)

    assert title.next_scene is None
    assert title.replay_arguments()['opening'] is False
    assert TitleScene(options=dict(LAUNCH_OPTIONS), **title.replay_arguments()).opening is False


def test_the_opening_title_replays_with_no_opening_key(scene):
    """The opening title's replay arguments are what they were before feature plan 12."""
    assert 'opening' not in scene.replay_arguments()
    assert scene.opening is True
