"""Input during a scene transition: presses are discarded, releases and system events delivered.

Runs real games and scenes headless through the golden-trace harness
(``scripts/record_golden_traces.py``), which steps frames exactly as ``SceneManager.start()``
does, without pacing.
"""

from __future__ import annotations

import contextlib
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

import pygame
import pytest
from scripts.record_golden_traces import (
    FAKE_CLOCK_START_SECONDS,
    FRAME_SECONDS,
    SCREEN_RESOLUTION,
    FakeClock,
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    press,
    release,
)
from scripts.record_golden_traces import (
    _command_line as command_line,
)
from scripts.record_golden_traces import (
    _deterministic_environment as deterministic_environment,
)
from scripts.record_golden_traces import (
    _discard_environment_events as discard_environment_events,
)
from scripts.record_golden_traces import (
    _stand_on_first_elevator as stand_on_first_elevator,
)

from glitchygames.examples.clockwork_keep.game import ClockworkKeepScene
from glitchygames.input import ActionMap
from glitchygames.scenes import Scene
from glitchygames.scenes.scene import (
    TRANSITION_DISCARDED_EVENT_TYPES,
    is_discarded_during_transition,
)
from glitchygames.transitions import FadeTransition

if TYPE_CHECKING:
    from collections.abc import Generator

# Frames to wait for a requested transition to start, and for a ride to finish
TRANSITION_START_FRAME_LIMIT = 10
TRANSITION_END_FRAME_LIMIT = 600

# Clockwork Keep: frames to settle at spawn, and on the elevator before pressing interact
SPAWN_SETTLE_FRAMES = 30
ELEVATOR_SETTLE_FRAMES = 20
# Frames watched after the elevator arrives (a jump rises for far longer than this)
ARRIVAL_WATCH_FRAMES = 30

TEST_FADE_SECONDS = 0.25

# The stick pushes the tests use, against 'move_right' bound at STICK_ACTION_THRESHOLD
STICK_ACTION_THRESHOLD = 0.3
STICK_FULL_RIGHT = 1.0
STICK_CENTRED = 0.05  # Inside DEFAULT_DEADZONE (0.15): a stick at rest
TEST_JOYSTICK_INSTANCE_ID = 3


def new_shared_actions() -> ActionMap:
    """Build the game-level ActionMap both scenes of the generic transition tests share.

    Returns:
        An ActionMap with 'move_right' bound to the right arrow key.

    """
    actions = ActionMap(input_mode='joystick')
    actions.bind(
        'move_right',
        keyboard=pygame.K_RIGHT,
        controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, STICK_ACTION_THRESHOLD),
    )
    return actions


class ArrivalScene(Scene):
    """The scene a transition goes to; it feeds the shared ActionMap."""

    NAME = 'Arrival'
    VERSION = '1.0'

    # Replaced by running_game, so every test starts with nothing held
    shared_actions: ClassVar[ActionMap] = new_shared_actions()
    hat_values: ClassVar[dict[int, tuple[int, int]]] = {}

    @override
    def on_key_down_event(self: Self, event: Any) -> None:
        """Feed key presses to the shared ActionMap, then to the base Scene."""
        ArrivalScene.shared_actions.handle_event(event)
        super().on_key_down_event(event)

    @override
    def on_key_up_event(self: Self, event: Any) -> None:
        """Feed key releases to the shared ActionMap, then to the base Scene (quit keys)."""
        ArrivalScene.shared_actions.handle_event(event)
        super().on_key_up_event(event)

    @override
    def on_joy_axis_motion_event(self: Self, event: Any) -> None:
        """Feed stick motion to the shared ActionMap."""
        ArrivalScene.shared_actions.handle_event(event)

    @override
    def on_joy_hat_motion_event(self: Self, event: Any) -> None:
        """Remember each hat's position (the game-level controller state)."""
        ArrivalScene.hat_values[event.hat] = tuple(event.value)


class DepartureScene(ArrivalScene):
    """The scene a transition leaves; ``depart()`` starts a fade to an ArrivalScene."""

    NAME = 'Departure'

    def depart(self: Self) -> None:
        """Request a fade to a new ArrivalScene."""
        self.transition_to(
            ArrivalScene(options=self.options), FadeTransition(duration=TEST_FADE_SECONDS)
        )


@contextlib.contextmanager
def running_game(scene_class: type[Scene]) -> Generator[GoldenTraceSceneManager]:
    """Start a game headless in the harness's deterministic environment.

    Args:
        scene_class: The game's scene class.

    Yields:
        The scene manager with the game scene active.

    """
    clock = FakeClock(start_seconds=FAKE_CLOCK_START_SECONDS)
    ArrivalScene.shared_actions = new_shared_actions()
    ArrivalScene.hat_values = {}
    with (
        tempfile.TemporaryDirectory(prefix='transition-input-saves-') as save_directory,
        deterministic_environment(clock=clock, save_root=Path(save_directory)),
    ):
        manager = GoldenTraceSceneManager.install()
        try:
            with command_line([
                '--windowed',
                '--resolution',
                SCREEN_RESOLUTION,
                '--log-level',
                'warning',
                '--input-mode',
                'joystick',
            ]):
                engine = GoldenTraceEngine(game=scene_class)
            engine.install_game(scene_class=scene_class)
            yield manager
        finally:
            pygame.event.clear()
            GoldenTraceSceneManager.uninstall()


def step(manager: GoldenTraceSceneManager, *events: pygame.event.Event) -> None:
    """Post events, then run one frame.

    Args:
        manager: The running scene manager.
        *events: Events posted before the frame.

    """
    manager.dt = FRAME_SECONDS
    discard_environment_events()
    for event in events:
        pygame.event.post(event)
    manager.run_frame()


def step_until_transition_starts(manager: GoldenTraceSceneManager) -> None:
    """Run frames until a transition is active."""
    for _ in range(TRANSITION_START_FRAME_LIMIT):
        if manager._active_transition is not None:
            return
        step(manager)
    pytest.fail('The transition never started')


def step_until_transition_ends(manager: GoldenTraceSceneManager) -> None:
    """Run frames until no transition is active."""
    for _ in range(TRANSITION_END_FRAME_LIMIT):
        if manager._active_transition is None:
            return
        step(manager)
    pytest.fail('The transition never ended')


class ForwardingJoystick:
    """Stands in for a connected joystick: forwards its motion to the scene manager."""

    def __init__(self, *, manager: GoldenTraceSceneManager) -> None:
        """Forward to this scene manager."""
        self.manager = manager

    def on_joy_axis_motion_event(self, event: Any) -> None:
        """Forward axis motion."""
        self.manager.on_joy_axis_motion_event(event)

    def on_joy_hat_motion_event(self, event: Any) -> None:
        """Forward hat motion."""
        self.manager.on_joy_hat_motion_event(event)


def connect_test_joystick(manager: GoldenTraceSceneManager) -> None:
    """Register a stand-in joystick, so its events reach the active scene.

    Args:
        manager: The running scene manager.

    """
    assert manager.game_engine is not None
    manager.game_engine.joystick_manager.joysticks[TEST_JOYSTICK_INSTANCE_ID] = ForwardingJoystick(
        manager=manager
    )


def stick_x(value: float) -> pygame.event.Event:
    """Build a left-stick x motion from the test joystick.

    Args:
        value: The normalized stick position.

    Returns:
        The JOYAXISMOTION event.

    """
    return pygame.event.Event(
        pygame.JOYAXISMOTION,
        instance_id=TEST_JOYSTICK_INSTANCE_ID,
        axis=pygame.CONTROLLER_AXIS_LEFTX,
        value=value,
    )


def hat(value: tuple[int, int]) -> pygame.event.Event:
    """Build a hat 0 motion from the test joystick.

    Args:
        value: The hat position.

    Returns:
        The JOYHATMOTION event.

    """
    return pygame.event.Event(
        pygame.JOYHATMOTION, instance_id=TEST_JOYSTICK_INSTANCE_ID, hat=0, value=value
    )


def start_departure(manager: GoldenTraceSceneManager) -> None:
    """Start the fade from the DepartureScene and run until it is active."""
    departure = manager.active_scene
    assert isinstance(departure, DepartureScene)
    departure.depart()
    step_until_transition_starts(manager)


def test_discarded_event_types_are_presses_only():
    """The discard set holds every press and motion type, and no release."""
    assert {
        pygame.KEYDOWN,
        pygame.TEXTINPUT,
        pygame.MOUSEBUTTONDOWN,
        pygame.MOUSEMOTION,
        pygame.MOUSEWHEEL,
        pygame.JOYBUTTONDOWN,
        pygame.JOYAXISMOTION,
        pygame.JOYHATMOTION,
        pygame.JOYBALLMOTION,
        pygame.CONTROLLERBUTTONDOWN,
        pygame.CONTROLLERAXISMOTION,
        pygame.FINGERDOWN,
        pygame.FINGERMOTION,
    } == TRANSITION_DISCARDED_EVENT_TYPES
    released_types = {
        pygame.KEYUP,
        pygame.MOUSEBUTTONUP,
        pygame.JOYBUTTONUP,
        pygame.CONTROLLERBUTTONUP,
        pygame.FINGERUP,
    }
    assert not released_types & TRANSITION_DISCARDED_EVENT_TYPES


def test_jump_pressed_during_elevator_ride_does_not_jump_on_arrival():
    """A jump key pressed and released mid-ride is not delivered when the ride ends."""
    with running_game(ClockworkKeepScene) as manager:
        for _ in range(SPAWN_SETTLE_FRAMES):
            step(manager)
        assert manager.active_scene is not None
        stand_on_first_elevator(manager.active_scene)
        for _ in range(ELEVATOR_SETTLE_FRAMES):
            step(manager)
        step(manager, press(pygame.K_w))
        step(manager, release(pygame.K_w))
        step_until_transition_starts(manager)

        step(manager, press(pygame.K_UP))
        step(manager, release(pygame.K_UP))
        step_until_transition_ends(manager)

        arrival_floor = manager.active_scene
        assert isinstance(arrival_floor, ClockworkKeepScene)
        assert arrival_floor.floor_index == 1
        arrival_world_y = arrival_floor.player.world_y
        highest_world_y = arrival_world_y
        for _ in range(ARRIVAL_WATCH_FRAMES):
            step(manager)
            highest_world_y = min(highest_world_y, arrival_floor.player.world_y)

        # A jump moves the player up (smaller world_y); falling or standing never does
        assert highest_world_y >= arrival_world_y


def test_key_held_before_transition_and_released_during_it_is_not_held_after():
    """A release mid-transition reaches the ActionMap before the arrival scene's first tick."""
    with running_game(DepartureScene) as manager:
        step(manager, press(pygame.K_RIGHT))
        # Non-transition frames deliver presses as before
        assert ArrivalScene.shared_actions.is_held('move_right')

        start_departure(manager)
        step(manager, release(pygame.K_RIGHT))
        step_until_transition_ends(manager)

        # The arrival scene's first dt_tick runs before that frame's events: nothing may be held
        assert isinstance(manager.active_scene, ArrivalScene)
        assert not ArrivalScene.shared_actions.is_held('move_right')


def test_key_pressed_during_transition_is_never_delivered():
    """A press mid-transition is discarded, not queued for the arrival scene."""
    with running_game(DepartureScene) as manager:
        start_departure(manager)
        step(manager, press(pygame.K_RIGHT))
        step_until_transition_ends(manager)
        step(manager)

        assert not ArrivalScene.shared_actions.is_held('move_right')


def test_quit_during_transition_quits():
    """A quit event during a transition is processed in that frame."""
    with running_game(DepartureScene) as manager:
        start_departure(manager)
        step(manager, pygame.event.Event(pygame.QUIT))

        assert manager.quit_requested is True


def test_controller_disconnect_during_transition_is_processed(mocker):
    """A joystick removal during a transition reaches the engine's joystick manager."""
    with running_game(DepartureScene) as manager:
        assert manager.game_engine is not None
        removed_handler = mocker.patch.object(
            manager.game_engine.joystick_manager, 'on_joy_device_removed_event'
        )
        start_departure(manager)
        removal = pygame.event.Event(pygame.JOYDEVICEREMOVED, instance_id=7)
        # Post after the environment-event filter (which drops device events)
        manager.dt = FRAME_SECONDS
        discard_environment_events()
        pygame.event.post(removal)
        manager.run_frame()

        assert manager._active_transition is not None
        removed_handler.assert_called_once()
        assert removed_handler.call_args.args[0].instance_id == 7


def test_stick_pushed_before_transition_and_centred_during_it_is_not_held_after():
    """A stick back inside the deadzone mid-transition is a release: it is delivered."""
    with running_game(DepartureScene) as manager:
        connect_test_joystick(manager)
        step(manager, stick_x(STICK_FULL_RIGHT))
        assert ArrivalScene.shared_actions.is_held('move_right')

        start_departure(manager)
        step(manager, stick_x(STICK_CENTRED))
        step_until_transition_ends(manager)

        assert not ArrivalScene.shared_actions.is_held('move_right')


def test_stick_pushed_during_transition_is_discarded():
    """A stick pushed outside the deadzone mid-transition is a press: it is discarded."""
    with running_game(DepartureScene) as manager:
        connect_test_joystick(manager)
        start_departure(manager)
        step(manager, stick_x(STICK_FULL_RIGHT))
        step_until_transition_ends(manager)
        step(manager)

        assert not ArrivalScene.shared_actions.is_held('move_right')


def test_hat_centred_during_transition_is_delivered_and_pushed_hat_discarded():
    """A hat back at (0, 0) mid-transition is delivered; a pushed hat is not."""
    with running_game(DepartureScene) as manager:
        connect_test_joystick(manager)
        step(manager, hat((1, 0)))
        assert ArrivalScene.hat_values == {0: (1, 0)}

        start_departure(manager)
        step(manager, hat((0, 0)))
        assert ArrivalScene.hat_values == {0: (0, 0)}

        step(manager, hat((0, 1)))
        step_until_transition_ends(manager)
        step(manager)
        assert ArrivalScene.hat_values == {0: (0, 0)}


@pytest.mark.parametrize(
    ('event', 'is_discarded'),
    [
        # Controller axis values are raw SDL ints: 4000 / 32767 = 0.12 is inside the deadzone
        (pygame.event.Event(pygame.CONTROLLERAXISMOTION, axis=0, value=4000), False),
        (pygame.event.Event(pygame.CONTROLLERAXISMOTION, axis=0, value=-32767), True),
        (pygame.event.Event(pygame.JOYAXISMOTION, axis=0, value=-0.1), False),
        (pygame.event.Event(pygame.JOYAXISMOTION, axis=0, value=0.5), True),
        (pygame.event.Event(pygame.JOYHATMOTION, hat=0, value=(0, 0)), False),
        (pygame.event.Event(pygame.JOYHATMOTION, hat=0, value=(-1, 0)), True),
        (pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a), True),
        (pygame.event.Event(pygame.KEYUP, key=pygame.K_a), False),
    ],
)
def test_neutral_motion_is_delivered_and_other_presses_discarded(event, is_discarded):
    """Axis motion inside DEFAULT_DEADZONE and a centred hat are releases, not presses."""
    assert is_discarded_during_transition(event) is is_discarded


def test_quit_key_pressed_and_released_during_transition_does_not_quit():
    """Q pressed mid-transition is discarded, so its release must not quit."""
    with running_game(DepartureScene) as manager:
        start_departure(manager)
        step(manager, press(pygame.K_q))
        step(manager, release(pygame.K_q))
        step_until_transition_ends(manager)
        step(manager)
        step(manager)

        assert manager.quit_requested is False


def test_quit_key_pressed_before_transition_and_released_during_it_does_not_quit():
    """The arriving scene never saw the Q press, so the release reaching it does not quit.

    The departing scene saw the press but was cleaned up before the release; quitting from a
    scene that only sees half a key stroke would act on input meant for a scene that is gone.
    """
    with running_game(DepartureScene) as manager:
        step(manager, press(pygame.K_q))
        start_departure(manager)
        step(manager, release(pygame.K_q))
        step_until_transition_ends(manager)
        step(manager)
        step(manager)

        assert manager.quit_requested is False


def test_quit_key_pressed_and_released_in_a_scene_quits():
    """Outside transitions, Q pressed and released in the same scene quits as before."""
    with running_game(DepartureScene) as manager:
        step(manager, press(pygame.K_q))
        step(manager, release(pygame.K_q))
        step(manager)

        assert manager.quit_requested is True
