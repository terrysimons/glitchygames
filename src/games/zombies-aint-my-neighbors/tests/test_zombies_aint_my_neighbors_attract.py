"""The attract scene: the idle loop's demo, replayed inside the game (feature plan 13).

The scene replays the shipped demo (``demos/neighborhood_four_kids.jsonl.gz``) as an inner game
(``glitchygames.inner_game``), draws it scaled to the screen under a DEMO label, and hands over
to the title when the demo ends, fails, or anyone presses a key or a pad button. Most tests use a
short demo: the shipped one cut to its first frames (a recording is a header line, then a line a
frame, so its first frames are a recording of their own).
"""

from __future__ import annotations

import gzip
import importlib
import json
from typing import TYPE_CHECKING

import pygame
import pytest

from glitchygames.audio import reserve_inner_game_channels
from glitchygames.audio.engine import DEFAULT_LIBRARY_CHANNELS, DEFAULT_LIVE_POOL, LEGACY_CHANNELS
from glitchygames.audio.voices import reserve_channels
from glitchygames.events.base import HashableEvent
from glitchygames.inner_game import InnerGame, InnerGameState
from zombies_aint_my_neighbors import attract
from zombies_aint_my_neighbors.attract import (
    DEMO_SIZE,
    LABEL_COLOUR,
    LETTERBOX_COLOUR,
    AttractScene,
    DemoPicture,
    attract_demo_path,
    fitted_rect,
)
from zombies_aint_my_neighbors.demo_neighborhood import DemoNeighborhoodScene
from zombies_aint_my_neighbors.title import Attraction, TitleScene

if TYPE_CHECKING:
    from pathlib import Path

support = importlib.import_module('src.games.zombies-aint-my-neighbors.tests.screen_support')
OPTIONS = {'input_mode': 'auto', 'no_unhandled_events': True}
FRAME_SECONDS = support.FRAME_SECONDS
# The short demo's length, in frames
SHORT_DEMO_FRAMES = 40


@pytest.fixture(autouse=True)
def one_inner_game_declared() -> None:
    """Partition the mixer and declare one inner game, as the game's title does at startup."""
    reserve_channels(
        live_pool=DEFAULT_LIVE_POOL,
        library_channels=DEFAULT_LIBRARY_CHANNELS,
        legacy_channels=LEGACY_CHANNELS,
    )
    reserve_inner_game_channels(games=1)


def write_recording(path: Path, *, header_changes: dict | None = None, frames: int) -> Path:
    """Write the shipped demo's first frames to ``path``, its header changed as asked.

    Returns:
        The path.

    """
    shipped = attract_demo_path()
    assert shipped is not None
    with gzip.open(shipped, 'rt', encoding='utf-8') as recording:
        lines = recording.read().splitlines()
    header = {**json.loads(lines[0]), **(header_changes or {})}
    with gzip.open(path, 'wt', encoding='utf-8') as recording:
        recording.write('\n'.join([json.dumps(header), *lines[1 : frames + 1]]) + '\n')
    return path


@pytest.fixture
def short_demo(tmp_path, mocker) -> Path:
    """The attract scene replays a short demo: the shipped one's first frames.

    Returns:
        Its path.

    """
    path = write_recording(tmp_path / 'short.jsonl.gz', frames=SHORT_DEMO_FRAMES)
    mocker.patch.object(attract, 'attract_demo_path', return_value=path)
    return path


def attract_scene() -> AttractScene:
    """Return the attract scene, set up as the scene manager sets it up.

    Returns:
        The scene.

    """
    scene = AttractScene(options=dict(OPTIONS))
    scene.setup()
    return scene


def run_frames(scene: AttractScene, *, frames: int) -> None:
    """Run the scene's logic for some frames, as the scene manager does."""
    for _ in range(frames):
        if scene.next_scene is not None:
            return
        scene.advance_game_time(seconds=FRAME_SECONDS)
        scene.dt_tick(FRAME_SECONDS)


def run_to_the_hand_over(scene: AttractScene) -> None:
    """Run the scene until it hands over (a frame limit fails the test)."""
    run_frames(scene, frames=SHORT_DEMO_FRAMES * 4)
    assert scene.next_scene is not None


def test_the_shipped_demo_is_found_where_it_is_installed():
    """The demo is looked up as every bundled demo is (glitchygames.bundled_demos)."""
    path = attract_demo_path()

    assert path is not None
    assert path.name == 'neighborhood_four_kids.jsonl.gz'
    assert path.is_file()


@pytest.mark.parametrize(
    ('screen', 'expected'),
    [
        ((800, 480), pygame.Rect(0, 0, 800, 480)),
        ((1600, 960), pygame.Rect(0, 0, 1600, 960)),
        ((1280, 720), pygame.Rect(40, 0, 1200, 720)),
        ((800, 600), pygame.Rect(0, 60, 800, 480)),
    ],
)
def test_the_picture_fits_the_screen_keeping_its_shape(screen, expected):
    """The 800x480 demo fills a screen of its shape and is letterboxed in one of another."""
    assert fitted_rect(picture_size=DEMO_SIZE, screen_size=screen) == expected


def test_the_picture_is_scaled_into_a_screen_of_another_size():
    """On a 1280x720 screen the 800x480 picture is scaled to 1200x720, with bars either side."""
    group = pygame.sprite.LayeredDirty()
    picture = DemoPicture(size=(1280, 720), groups=group)
    frame = pygame.Surface(DEMO_SIZE)
    frame.fill((40, 160, 60))

    picture.show(picture=frame)

    assert picture.image.get_at((20, 360))[:3] == LETTERBOX_COLOUR
    assert picture.image.get_at((1260, 360))[:3] == LETTERBOX_COLOUR
    assert picture.image.get_at((40, 0))[:3] == (40, 160, 60)
    assert picture.image.get_at((1239, 719))[:3] == (40, 160, 60)


@pytest.mark.usefixtures('short_demo')
def test_a_demo_failing_part_way_returns_to_the_title_with_a_warning(mocker, caplog):
    """A replay that breaks on a later frame is caught by the inner game: back to the title."""
    original = DemoNeighborhoodScene.dt_tick
    calls = {'count': 0}

    def breaks_on_the_fifth_frame(scene, dt):
        calls['count'] += 1
        if calls['count'] == 5:
            message = 'a demo that breaks part way'
            raise RuntimeError(message)
        original(scene, dt)

    mocker.patch.object(DemoNeighborhoodScene, 'dt_tick', breaks_on_the_fifth_frame)
    with caplog.at_level('WARNING', logger=attract.LOG.name):
        scene = attract_scene()
        run_frames(scene, frames=20)

    assert isinstance(scene.next_scene, TitleScene)
    assert scene.inner_game is None
    warnings = [record.getMessage() for record in caplog.records if record.name == attract.LOG.name]
    assert len(warnings) == 1
    assert 'the demo failed' in warnings[0]


def test_a_scene_that_gave_up_ticks_harmlessly_until_the_switch(mocker):
    """With no demo the title is chosen in setup; a frame before the switch changes nothing."""
    mocker.patch.object(attract, 'attract_demo_path', return_value=None)
    scene = attract_scene()
    title = scene.next_scene

    scene.advance_game_time(seconds=FRAME_SECONDS)
    scene.dt_tick(FRAME_SECONDS)

    assert scene.next_scene is title
    assert scene.inner_game is None


@pytest.mark.usefixtures('short_demo')
def test_a_press_after_the_hand_over_builds_no_second_title():
    """The first press hands over; another before the switch changes nothing."""
    scene = attract_scene()
    PRESSES['space'](scene)
    title = scene.next_scene

    PRESSES['pad-a'](scene)

    assert scene.next_scene is title


@pytest.mark.draws_frames
@pytest.mark.usefixtures('short_demo')
def test_the_attract_scene_shows_the_demo_and_its_label():
    """The screen shows the replay's picture, letterboxed to the test display, and DEMO."""
    scene = attract_scene()
    run_frames(scene, frames=5)

    screen = support.rendered(scene)
    assert scene.inner_game is not None
    picture = scene.inner_game.surface
    area = fitted_rect(picture_size=DEMO_SIZE, screen_size=screen.get_size())
    label = scene.label.rect

    # The lawn the replay draws, at the same place in the fitted picture (the test display is
    # 800x600: the picture is not scaled, only moved down between the bars)
    point = (10, DEMO_SIZE[1] - 10)
    assert screen.get_at((area.x + point[0], area.y + point[1])) == picture.get_at(point)
    if area.top > 0:
        assert screen.get_at((0, 0))[:3] == LETTERBOX_COLOUR
    assert any(
        screen.get_at((x, y))[:3] == LABEL_COLOUR
        for x in range(label.left, label.right)
        for y in range(label.top, label.bottom)
    )


@pytest.mark.usefixtures('short_demo')
def test_the_demo_ends_into_a_fresh_title():
    """At the demo's end, the title that loops: not the opening one, nothing to wait for."""
    scene = attract_scene()

    run_to_the_hand_over(scene)

    assert isinstance(scene.next_scene, TitleScene)
    assert not scene.next_scene.opening
    assert scene.next_scene.replay_arguments().get('awaiting_release') is None
    assert scene.next_scene.next_attraction is Attraction.INTRO


def unreadable(tmp_path: Path) -> Path:
    """Return a file that is no recording.

    Returns:
        Its path.

    """
    path = tmp_path / 'broken.jsonl.gz'
    path.write_bytes(b'not a recording')
    return path


FAILING_DEMOS = {
    'not-installed': lambda tmp_path: None,
    'unreadable': unreadable,
    'another-size': lambda tmp_path: write_recording(
        tmp_path / 'small.jsonl.gz', header_changes={'screen_size': [640, 400]}, frames=10
    ),
}


@pytest.mark.parametrize('demo', FAILING_DEMOS.values(), ids=FAILING_DEMOS.keys())
def test_a_missing_or_failing_demo_returns_to_the_title_with_a_warning(
    demo, tmp_path, mocker, caplog
):
    """No demo, or one that can't play, goes straight back to the title, with one warning.

    That title owes the intro next, as after a demo that played: a broken demo is not tried
    again at every idle, and the intro still gets its turn.
    """
    mocker.patch.object(attract, 'attract_demo_path', return_value=demo(tmp_path))

    with caplog.at_level('WARNING', logger=attract.LOG.name):
        scene = attract_scene()
        run_frames(scene, frames=2)

    assert isinstance(scene.next_scene, TitleScene)
    assert not scene.next_scene.opening
    assert scene.next_scene.next_attraction is Attraction.INTRO
    assert [record.levelname for record in caplog.records if record.name == attract.LOG.name] == [
        'WARNING'
    ]
    assert scene.inner_game is None


PRESSES = {
    'space': lambda scene: scene.on_key_down_event(
        support.key_event(pygame.KEYDOWN, pygame.K_SPACE)
    ),
    'p': lambda scene: scene.on_key_down_event(support.key_event(pygame.KEYDOWN, pygame.K_p)),
    'escape': lambda scene: scene.on_key_down_event(
        support.key_event(pygame.KEYDOWN, pygame.K_ESCAPE)
    ),
    'pad-a': lambda scene: scene.on_controller_button_down_event(
        HashableEvent(pygame.CONTROLLERBUTTONDOWN, instance_id=1, button=pygame.CONTROLLER_BUTTON_A)
    ),
    'joystick-button': lambda scene: scene.on_joy_button_down_event(
        HashableEvent(pygame.JOYBUTTONDOWN, instance_id=1, joy=1, button=3)
    ),
}


@pytest.mark.usefixtures('short_demo')
@pytest.mark.parametrize('press', PRESSES.values(), ids=PRESSES.keys())
@pytest.mark.parametrize('after_frames', [0, SHORT_DEMO_FRAMES // 2, SHORT_DEMO_FRAMES - 2])
def test_any_key_or_pad_button_returns_to_the_title(press, after_frames):
    """A press on any frame hands over at once to a title that waits for its release."""
    scene = attract_scene()
    run_frames(scene, frames=after_frames)
    assert scene.next_scene is None

    press(scene)

    assert isinstance(scene.next_scene, TitleScene)
    assert not scene.next_scene.opening
    assert scene.next_scene.replay_arguments().get('awaiting_release') is True
    assert scene.next_scene.next_attraction is Attraction.INTRO


@pytest.mark.usefixtures('short_demo')
def test_releases_sticks_and_pads_arriving_change_nothing():
    """Only a press ends the demo: releases, sticks, hats and devices come and go unheeded."""
    scene = attract_scene()
    run_frames(scene, frames=3)

    scene.on_key_up_event(support.key_event(pygame.KEYUP, pygame.K_SPACE))
    scene.on_controller_button_up_event(
        HashableEvent(pygame.CONTROLLERBUTTONUP, instance_id=1, button=pygame.CONTROLLER_BUTTON_A)
    )
    scene.on_joy_button_up_event(HashableEvent(pygame.JOYBUTTONUP, instance_id=1, joy=1, button=3))
    scene.on_joy_axis_motion_event(
        HashableEvent(pygame.JOYAXISMOTION, instance_id=1, joy=1, axis=0, value=1.0)
    )
    scene.on_joy_hat_motion_event(
        HashableEvent(pygame.JOYHATMOTION, instance_id=1, joy=1, hat=0, value=(1, 0))
    )
    scene.on_joy_device_added_event(HashableEvent(pygame.JOYDEVICEADDED, device_index=0))
    run_frames(scene, frames=3)

    assert scene.next_scene is None
    assert scene.inner_game is not None


@pytest.mark.usefixtures('short_demo')
def test_skipping_the_demo_silences_it():
    """The demo is heard while it plays; a skip finishes it, and a finished game is silent."""
    scene = attract_scene()
    run_frames(scene, frames=3)
    game = scene.inner_game
    assert game is not None
    assert game.audible

    PRESSES['space'](scene)

    assert not game.audible
    assert game.outcome.state is not InnerGameState.RUNNING
    assert scene.inner_game is None


def end_by_running_out(scene: AttractScene) -> None:
    """End the demo by playing it to its end."""
    run_to_the_hand_over(scene)


def end_by_a_skip(scene: AttractScene) -> None:
    """End the demo with a press."""
    PRESSES['space'](scene)


def end_by_quitting(scene: AttractScene) -> None:
    """End the demo as the game quitting does: the scene manager cleans the active scene up."""
    scene.cleanup()


ENDINGS = {'its-end': end_by_running_out, 'a-skip': end_by_a_skip, 'quitting': end_by_quitting}


@pytest.mark.usefixtures('short_demo')
@pytest.mark.parametrize('end', ENDINGS.values(), ids=ENDINGS.keys())
def test_the_demo_plays_again_after_each_way_it_can_end(end, mocker):
    """However the demo ends, it is finished exactly once and the next showing plays."""
    finish = mocker.spy(InnerGame, 'finish')
    scene = attract_scene()
    run_frames(scene, frames=2)

    end(scene)
    scene.cleanup()

    assert finish.call_count == 1
    again = attract_scene()
    run_frames(again, frames=2)
    assert again.inner_game is not None
    assert again.inner_game.outcome.state is InnerGameState.RUNNING
    assert again.inner_game.outcome.frames_run >= 1
    again.cleanup()


def test_a_failed_demo_plays_again_next_time(tmp_path, mocker):
    """A demo that failed gives its channels back too: the next showing plays."""
    mocker.patch.object(attract, 'attract_demo_path', return_value=unreadable(tmp_path))
    failed = attract_scene()
    failed.cleanup()
    mocker.patch.object(
        attract,
        'attract_demo_path',
        return_value=write_recording(tmp_path / 'short.jsonl.gz', frames=SHORT_DEMO_FRAMES),
    )

    again = attract_scene()
    run_frames(again, frames=2)

    assert again.inner_game is not None
    assert again.inner_game.outcome.state is InnerGameState.RUNNING
    again.cleanup()


def test_no_pad_rumbles_while_the_demo_plays(mocker):
    """The whole demo destroys TVs, which rumble a pad in play, but no pad at the cabinet rumbles.

    Two pads are connected to the game showing the demo (doubles of the devices the scene sees:
    only ``rumble`` is asked of them); the demo's own pads are the recording's stand-ins, inside
    its inner game.
    """
    pads = [mocker.Mock(name=f'pad {index}') for index in range(2)]
    mocker.patch.object(
        AttractScene, 'input_devices', new_callable=mocker.PropertyMock, return_value=pads
    )
    scene = attract_scene()

    run_frames(scene, frames=3000)

    assert isinstance(scene.next_scene, TitleScene)
    for pad in pads:
        pad.rumble.assert_not_called()


def test_the_title_declares_one_inner_game():
    """The title, the scene a live run starts on, has the engine set the demo's channels aside."""
    assert TitleScene.INNER_GAMES == 1


@pytest.mark.usefixtures('short_demo')
def test_setting_the_scene_up_again_builds_no_second_demo(mocker):
    """A second setup (a resume) keeps the demo it has."""
    replay = mocker.spy(InnerGame, 'replay')
    scene = attract_scene()

    scene.setup()

    assert replay.call_count == 1
    scene.cleanup()


@pytest.mark.usefixtures('short_demo')
def test_the_attract_scene_replays_as_it_began():
    """A recording rebuilds it with no arguments: it always plays the shipped demo."""
    assert AttractScene(options=dict(OPTIONS)).replay_arguments() == {}
