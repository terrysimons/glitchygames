"""The intro (feature plan 12): its timeline of cues, and the scene that plays it.

The plan (plans/2026-11-19-zombies-aint-my-neighbors-12-intro-and-idle-loop.md) is the spec: the
cue times below are copied from its table, not read from the code.
"""

from __future__ import annotations

import importlib

import pygame
import pytest
from pydantic import ValidationError

from glitchygames.effects.shake import ShakeTarget
from glitchygames.events.base import HashableEvent
from zombies_aint_my_neighbors.art import intro_rig
from zombies_aint_my_neighbors.intro import (
    INTRO_BURST_SHAKE,
    INTRO_RUMBLE_HIGH,
    INTRO_RUMBLE_LOW,
    INTRO_RUMBLE_MILLISECONDS,
    OVAL_COLOUR,
    IntroScene,
    IntroShowing,
)
from zombies_aint_my_neighbors.intro_timeline import (
    INTRO_SECONDS,
    INTRO_TIMELINE,
    CueKind,
    IntroCue,
    cues_crossed,
)

support = importlib.import_module('src.games.zombies-aint-my-neighbors.tests.screen_support')
FRAME_SECONDS = support.FRAME_SECONDS
OPTIONS = {'input_mode': 'auto', 'no_unhandled_events': True}
# The plan's table: every time a cue fires at
PLAN_CUE_TIMES = (0.0, 4.0, 5.5, 6.0, 6.3, 6.8, 8.0)
BAGS = tuple(f'intro_bag_{name}' for name in ('dex', 'marisol', 'theo', 'june'))


def test_the_timeline_is_in_order_and_ends_once():
    """Sorted by time, at the plan's times, with one END, last, at 8 s."""
    times = [cue.at_seconds for cue in INTRO_TIMELINE]

    assert times == sorted(times)
    assert sorted(set(times)) == list(PLAN_CUE_TIMES)
    ends = [cue for cue in INTRO_TIMELINE if cue.kind is CueKind.END]
    assert ends == [INTRO_TIMELINE[-1]]
    assert INTRO_SECONDS == ends[0].at_seconds == 8.0


def test_the_burst_is_at_six_seconds_with_the_shake_the_rumble_and_the_kids_startled():
    """6.0 s: the TV bursts, the four kids start, the screen shakes and the pads rumble."""
    at_six = [cue for cue in INTRO_TIMELINE if cue.at_seconds == 6.0]

    assert {cue.kind for cue in at_six} == {CueKind.ANIMATE, CueKind.SHAKE, CueKind.RUMBLE}
    animated = {(cue.actor, cue.animation) for cue in at_six if cue.kind is CueKind.ANIMATE}
    assert animated == {('intro_tv', 'burst'), *((bag, 'startled') for bag in BAGS)}


def test_each_cue_fires_once_frame_by_frame():
    """Stepping 0 to 9 s a 60th at a time fires the whole timeline once, in order."""
    fired: list[IntroCue] = []
    before = 0.0
    for frame in range(1, 9 * 60 + 1):
        now = frame * FRAME_SECONDS
        fired.extend(cues_crossed(timeline=INTRO_TIMELINE, before_seconds=before, now_seconds=now))
        before = now

    assert fired == list(INTRO_TIMELINE)


def test_a_long_frame_fires_every_cue_it_crosses_in_order():
    """One frame from 3.9 to 6.5 s fires the 4.0, 5.5, 6.0 and 6.3 cues, in timeline order."""
    crossed = cues_crossed(timeline=INTRO_TIMELINE, before_seconds=3.9, now_seconds=6.5)

    assert crossed == tuple(cue for cue in INTRO_TIMELINE if 3.9 <= cue.at_seconds < 6.5)
    assert {cue.at_seconds for cue in crossed} == {4.0, 5.5, 6.0, 6.3}


def test_a_cue_on_a_frame_boundary_fires_on_the_frame_that_starts_at_it():
    """A frame starting at 6.0 fires the 6.0 cues; the frame ending at 6.0 does not."""
    ending_at_six = cues_crossed(timeline=INTRO_TIMELINE, before_seconds=5.9, now_seconds=6.0)
    starting_at_six = cues_crossed(timeline=INTRO_TIMELINE, before_seconds=6.0, now_seconds=6.1)

    assert all(cue.at_seconds != 6.0 for cue in ending_at_six)
    assert {cue.at_seconds for cue in starting_at_six} == {6.0}


@pytest.mark.parametrize(
    'arguments',
    [
        {'kind': CueKind.ANIMATE},
        {'kind': CueKind.ANIMATE, 'actor': 'intro_tv'},
        {'kind': CueKind.ANIMATE, 'animation': 'burst'},
        {'kind': CueKind.SHAKE, 'actor': 'intro_tv'},
        {'kind': CueKind.END, 'animation': 'burst'},
    ],
    ids=[
        'animate-bare',
        'animate-no-animation',
        'animate-no-actor',
        'shake-actor',
        'end-animation',
    ],
)
def test_a_cue_needs_an_actor_and_animation_exactly_when_it_animates(arguments):
    """ANIMATE needs both; every other kind takes neither."""
    with pytest.raises(ValidationError):
        IntroCue(at_seconds=1.0, **arguments)


def test_every_animate_cue_names_a_sprite_and_an_animation_it_has():
    """Each ANIMATE cue's actor is an intro sprite, and its animation is one of that sprite's."""
    for cue in INTRO_TIMELINE:
        if cue.kind is CueKind.ANIMATE:
            assert cue.actor in intro_rig.INTRO_ANIMATIONS, cue
            states = {spec.state for spec in intro_rig.INTRO_ANIMATIONS[cue.actor]}
            assert cue.animation in states, cue


def test_every_intro_sprite_starts_at_zero():
    """At 0 s every actor that shows from the start gets its first animation.

    The hands and the zombie wait for their own cues.
    """
    started = {cue.actor for cue in INTRO_TIMELINE if cue.at_seconds == 0.0 and cue.actor}

    assert started == set(intro_rig.INTRO_ANIMATIONS) - {'intro_hands', 'intro_zombie'}


# The scene (task 3)


def intro(showing: IntroShowing = IntroShowing.LOOP) -> IntroScene:
    """Return the intro, set up as the scene manager sets it up.

    Returns:
        The scene.
    """
    scene = IntroScene(options=dict(OPTIONS), showing=showing)
    scene.setup()
    return scene


def run(scene: IntroScene, *, seconds: float) -> None:
    """Run the intro's logic frame by frame for some seconds."""
    support.tick_to(scene, seconds=scene.game_time + seconds)


def connected_pads(mocker, count: int) -> list:
    """Stand two (or ``count``) pads in for the devices the scene sees.

    Returns:
        The pads (doubles of ``InputDevice``: only ``rumble`` is asked of them).
    """
    pads = [mocker.Mock(name=f'pad {index}') for index in range(count)]
    mocker.patch.object(
        IntroScene, 'input_devices', new_callable=mocker.PropertyMock, return_value=pads
    )
    return pads


def test_the_intro_fires_its_timeline_and_hands_over_to_the_title():
    """At launch, run to the end: every cue fired once, in order, then the title."""
    from zombies_aint_my_neighbors.title import TitleScene

    scene = intro(IntroShowing.LAUNCH)
    run(scene, seconds=INTRO_SECONDS - 0.1)
    assert scene.next_scene is None

    run(scene, seconds=0.2)

    assert scene.fired == INTRO_TIMELINE
    assert isinstance(scene.next_scene, TitleScene)
    assert not scene.next_scene.opening


def test_the_loop_intro_ends_into_a_title_that_shows_the_demo_next():
    """In the idle loop, the intro's end hands back to the title, which owes the demo next.

    The demo and the intro take turns at the title's idles (the owner, 2026-11-19): the intro
    never leads straight into the demo.
    """
    from zombies_aint_my_neighbors.title import Attraction, TitleScene

    scene = intro(IntroShowing.LOOP)
    run(scene, seconds=INTRO_SECONDS + 0.1)

    assert scene.fired == INTRO_TIMELINE
    assert isinstance(scene.next_scene, TitleScene)
    assert not scene.next_scene.opening
    assert scene.next_scene.next_attraction is Attraction.DEMO


def test_a_skip_from_the_loop_intro_goes_to_the_title_not_the_demo():
    """A press during the loop's intro is someone wanting to play: straight to the title."""
    from zombies_aint_my_neighbors.title import TitleScene

    scene = intro(IntroShowing.LOOP)
    run(scene, seconds=1.0)

    scene.on_key_down_event(key_down(pygame.K_SPACE))

    assert isinstance(scene.next_scene, TitleScene)
    assert scene.next_scene.replay_arguments().get('awaiting_release') is True


def test_at_six_seconds_the_tv_bursts_the_kids_start_and_the_screen_shakes(mocker):
    """The burst: the TV and the kids change animation, and one screen shake is asked for."""
    scene = intro()
    shake = mocker.patch.object(scene, 'shake')
    run(scene, seconds=6.05)

    assert scene.actors['intro_tv'].current_animation == 'burst'
    assert {scene.actors[bag].current_animation for bag in BAGS} == {'startled'}
    shake.assert_called_once_with(INTRO_BURST_SHAKE, targets=ShakeTarget.SCREEN)


def test_the_hands_and_the_zombie_wait_hidden_for_their_cues():
    """Hidden until 6.3 s and 6.8 s, then shown, reaching and climbing out."""
    scene = intro()
    run(scene, seconds=6.25)
    assert not scene.actors['intro_hands'].visible
    assert not scene.actors['intro_zombie'].visible

    run(scene, seconds=0.6)

    assert scene.actors['intro_hands'].visible
    assert scene.actors['intro_hands'].current_animation == 'reach'
    assert scene.actors['intro_zombie'].visible
    assert scene.actors['intro_zombie'].current_animation == 'climb-out'


def test_the_launch_showing_rumbles_every_pad_once_at_the_burst(mocker):
    """At launch, each connected pad rumbles once, with the intro's strength and length."""
    pads = connected_pads(mocker, 2)
    scene = intro(IntroShowing.LAUNCH)
    run(scene, seconds=5.9)
    assert all(not pad.rumble.called for pad in pads)

    run(scene, seconds=2.0)

    for pad in pads:
        pad.rumble.assert_called_once_with(
            low_frequency=INTRO_RUMBLE_LOW,
            high_frequency=INTRO_RUMBLE_HIGH,
            duration_milliseconds=INTRO_RUMBLE_MILLISECONDS,
        )


def test_the_loop_rumbles_nothing(mocker):
    """Unattended (the idle loop), the burst rumbles no pad."""
    pads = connected_pads(mocker, 2)
    scene = intro(IntroShowing.LOOP)

    run(scene, seconds=INTRO_SECONDS)

    assert all(not pad.rumble.called for pad in pads)


def test_no_pad_no_rumble_and_nothing_raises(mocker):
    """No pad connected: the launch showing's burst rumbles nothing, and runs on."""
    connected_pads(mocker, 0)
    scene = intro(IntroShowing.LAUNCH)

    run(scene, seconds=INTRO_SECONDS + 0.1)

    assert scene.next_scene is not None


def key_down(key: int) -> HashableEvent:
    """Return a key press as the engine delivers it.

    Returns:
        The event.
    """
    return support.key_event(pygame.KEYDOWN, key)


SKIPS = {
    'key': lambda scene: scene.on_key_down_event(key_down(pygame.K_SPACE)),
    'pad-a': lambda scene: scene.on_controller_button_down_event(
        HashableEvent(pygame.CONTROLLERBUTTONDOWN, instance_id=1, button=pygame.CONTROLLER_BUTTON_A)
    ),
    'pad-start': lambda scene: support.controller_start(scene, instance_id=1),
    'joystick-button': lambda scene: scene.on_joy_button_down_event(
        HashableEvent(pygame.JOYBUTTONDOWN, instance_id=1, joy=1, button=3)
    ),
}


@pytest.mark.parametrize('press', SKIPS.values(), ids=SKIPS.keys())
@pytest.mark.parametrize('at_seconds', [0.0, 4.5, 7.9])
def test_a_key_or_button_skips_at_any_moment(press, at_seconds):
    """Any key or pad button ends the intro on that frame, to the title."""
    from zombies_aint_my_neighbors.title import TitleScene

    scene = intro()
    run(scene, seconds=at_seconds)

    press(scene)

    assert isinstance(scene.next_scene, TitleScene)
    assert not scene.next_scene.opening


@pytest.mark.parametrize('press', SKIPS.values(), ids=SKIPS.keys())
def test_a_press_on_the_hand_over_frame_still_returns_to_the_title(press):
    """A press on the frame the loop's intro ends gets a title that waits for its release.

    The intro hands over in a frame's logic; the frame's events come after it, so the title
    chosen at the end must already wait for the release of a press that comes then.
    """
    from zombies_aint_my_neighbors.title import TitleScene

    scene = intro(IntroShowing.LOOP)
    run(scene, seconds=INTRO_SECONDS + 0.01)
    title = scene.next_scene

    press(scene)

    assert isinstance(title, TitleScene)
    assert scene.next_scene is title
    assert title.replay_arguments().get('awaiting_release') is True


def test_the_loop_intros_end_never_replaces_a_skip():
    """A skip chose the title: the intro's end, reached before the switch, leaves it chosen."""
    from zombies_aint_my_neighbors.title import TitleScene

    scene = intro(IntroShowing.LOOP)
    run(scene, seconds=1.0)
    scene.on_key_down_event(key_down(pygame.K_SPACE))
    title = scene.next_scene

    run(scene, seconds=INTRO_SECONDS)

    assert isinstance(title, TitleScene)
    assert scene.next_scene is title


def test_the_pause_key_skips_like_any_other():
    """P pauses a stage, but the intro has no pause: it skips, as every key does."""
    from zombies_aint_my_neighbors.title import TitleScene

    scene = intro()
    run(scene, seconds=1.0)

    scene.on_key_down_event(key_down(pygame.K_p))

    assert isinstance(scene.next_scene, TitleScene)
    assert not scene.next_scene.opening


def test_key_releases_and_stick_moves_do_not_skip():
    """Only a press skips: a release, a stick or a hat moving leaves the intro playing."""
    scene = intro()
    run(scene, seconds=1.0)

    scene.on_key_up_event(support.key_event(pygame.KEYUP, pygame.K_SPACE))
    scene.on_controller_button_up_event(
        HashableEvent(pygame.CONTROLLERBUTTONUP, instance_id=1, button=pygame.CONTROLLER_BUTTON_A)
    )
    scene.on_joy_button_up_event(HashableEvent(pygame.JOYBUTTONUP, instance_id=1, joy=1, button=3))
    scene.on_controller_axis_motion_event(
        HashableEvent(pygame.CONTROLLERAXISMOTION, instance_id=1, axis=0, value=20000)
    )
    scene.on_joy_hat_motion_event(
        HashableEvent(pygame.JOYHATMOTION, instance_id=1, joy=1, hat=0, value=(1, 0))
    )

    assert scene.next_scene is None


def test_a_hitch_across_the_burst_fires_each_cue_once_and_hands_over_once(mocker):
    """A 7-second frame (0.5 to 7.5 s) fires each cue it crosses once; the end follows at 8 s."""
    from zombies_aint_my_neighbors.title import TitleScene

    scene = intro(IntroShowing.LAUNCH)
    shake = mocker.patch.object(scene, 'shake')
    run(scene, seconds=0.5)

    scene.advance_game_time(seconds=7.0)
    scene.dt_tick(7.0)
    assert scene.next_scene is None
    run(scene, seconds=0.6)

    assert scene.fired == INTRO_TIMELINE
    shake.assert_called_once()
    assert isinstance(scene.next_scene, TitleScene)
    assert not scene.next_scene.opening


def test_a_pad_plugged_in_or_out_during_the_intro_changes_nothing(mocker):
    """A pad arriving or leaving mid-intro is no press: the intro plays on, nothing raises."""
    scene = intro()
    run(scene, seconds=1.0)
    pad = mocker.Mock(instance_id=7)

    scene.on_input_device_added(device=pad)
    scene.on_controller_device_added_event(
        HashableEvent(pygame.CONTROLLERDEVICEADDED, device_index=0, instance_id=7)
    )
    scene.on_input_device_removed(device=pad)
    scene.on_controller_device_removed_event(
        HashableEvent(pygame.CONTROLLERDEVICEREMOVED, instance_id=7)
    )
    run(scene, seconds=1.0)

    assert scene.next_scene is None


def test_the_oval_darkens_the_corners_and_shows_the_middle():
    """Once faded in, the screen's corners are the oval's dark; the TV's case shows through."""
    scene = intro()
    run(scene, seconds=1.0)

    screen = support.rendered(scene)
    tv = scene.actors['intro_tv'].rect

    assert screen.get_at((0, 0))[:3] == OVAL_COLOUR
    assert screen.get_at((screen.get_width() - 1, screen.get_height() - 1))[:3] == OVAL_COLOUR
    # The case's wood, a little inside its left edge and below the screen
    assert screen.get_at((tv.left + tv.width // 10, tv.top + tv.height * 5 // 8))[:3] != OVAL_COLOUR


@pytest.mark.parametrize('showing', list(IntroShowing))
def test_the_intro_replays_as_it_began(showing):
    """Rebuilt from its replay arguments, the intro shows the same way."""
    scene = intro(showing)

    rebuilt = IntroScene(options=dict(OPTIONS), **scene.replay_arguments())

    assert rebuilt.showing is showing


def test_setting_the_intro_up_again_keeps_its_sprites():
    """A second setup (a pause's return) stages nothing twice: the same sprites, no more."""
    scene = intro()
    actors = dict(scene.actors)
    sprite_count = len(scene.all_sprites)

    scene.setup()

    assert scene.actors == actors
    assert len(scene.all_sprites) == sprite_count


def test_a_zero_length_first_frame_fires_nothing_and_shows_no_oval():
    """A frame that takes no time crosses no cue: nothing starts, the oval has not begun."""
    scene = intro()

    scene.dt_tick(0.0)

    assert scene.fired == ()
    assert support.rendered(scene).get_at((0, 0))[:3] != OVAL_COLOUR


def test_a_press_after_the_hand_over_builds_no_second_title():
    """The launch intro has ended: a press then keeps the title it already handed over to."""
    scene = intro(IntroShowing.LAUNCH)
    run(scene, seconds=INTRO_SECONDS + 0.1)
    title = scene.next_scene

    scene.on_key_down_event(key_down(pygame.K_SPACE))

    assert scene.next_scene is title
