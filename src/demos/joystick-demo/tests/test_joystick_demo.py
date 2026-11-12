"""Test the joystick demo (the joystick_demo package): real pygame, the real display.

The demo runs with its ``joystick-demo`` console script or ``python -m joystick_demo``.
It draws a header and one column per device the engine sees, from the frame's input snapshot.
Devices are hardware, so the engine here runs on stand-in devices through the real devices door
(tests/input/stand_in_devices.py): an unmapped flight stick and a mapped game pad. Everything
else is real: the engine and its event managers, the device registry, the demo's drawing.
"""

from __future__ import annotations

import contextlib
import dataclasses
from typing import TYPE_CHECKING, cast

import pygame
import pytest

import joystick_demo
from glitchygames.color import BLACK, WHITE, YELLOW
from glitchygames.events.base import HashableEvent
from glitchygames.fonts import FontManager
from glitchygames.fonts.font_manager import DEFAULT_FONT_NAME
from glitchygames.input.devices import ReplayJoystick
from glitchygames.input.input_devices import CONTROLLER_INPUT_EVENT_TYPES, ConnectedInputDevice
from glitchygames.input.state import InputSnapshot, set_current_input
from glitchygames.replay.tools.golden_traces import (
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    command_line,
)
from glitchygames.sources import active_sources
from glitchygames.ui import TextSprite
from tests.demo_runs import engine_run_environment, run_demo_main
from tests.input.stand_in_devices import STAND_IN_PAD, STAND_IN_STICK, install_stand_in_devices

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from pytest_mock import MockerFixture

    from glitchygames.input.devices import DeviceDescriptor

# Wide enough for two device columns
DEMO_RESOLUTION = '800x600'

PAD_LINES = [
    'Stand-in Game Pad',
    'GUID: 03000000cccc0000dddd000000000000',
    'Instance 9, device index 1',
    'Events: controller layer',
    'Axis 0: 100',
    'Axis 1: -200',
    'Axis 2: 0',
    'Axis 3: 0',
    'Axis 4: 32767',
    'Axis 5: 0',
    'Buttons held: 0, 3',
]
STICK_LINES = [
    'Stand-in Flight Stick',
    'GUID: 03000000aaaa0000bbbb000000000000',
    'Instance 5, device index 0',
    'Events: joystick layer',
    'Axis 0: 0.5',
    'Axis 1: -1.0',
    'Axis 2: 0.25',
    'Buttons held: 1, 3',
    'Hat 0: (1, 0)',
]


@contextlib.contextmanager
def running_demo(
    *,
    input_mode: str = 'auto',
    descriptors: Sequence[DeviceDescriptor] = (STAND_IN_STICK, STAND_IN_PAD),
    plugged_in_at_start: bool = True,
) -> Generator[tuple[GoldenTraceEngine, joystick_demo.Game]]:
    """Start the demo on the real engine (without its frame loop) with stand-in devices.

    Yields:
        The engine and the demo's scene.

    """
    blocked_before = [
        pygame.event.get_blocked(event_type) for event_type in range(pygame.NUMEVENTS)
    ]
    manager = GoldenTraceSceneManager.install()
    try:
        with command_line([
            '--windowed',
            '--resolution',
            DEMO_RESOLUTION,
            '--log-level',
            'warning',
            '--input-mode',
            input_mode,
        ]):
            engine = GoldenTraceEngine(game=joystick_demo.Game)
        install_stand_in_devices(descriptors=descriptors, plugged_in_at_start=plugged_in_at_start)
        engine.install_game(scene_class=joystick_demo.Game)
        scene = manager.active_scene
        assert isinstance(scene, joystick_demo.Game)
        # The first frame, as the engine's frame loop would draw it
        _draw_frame(scene)
        yield engine, scene
    finally:
        pygame.event.clear()
        GoldenTraceSceneManager.uninstall()
        # The controller manager allows controller events, joystick mode blocks them
        for event_type, was_blocked in enumerate(blocked_before):
            if was_blocked:
                pygame.event.set_blocked(event_type)
            else:
                pygame.event.set_allowed(event_type)


def _set_device_positions() -> None:
    """Make this frame's snapshot hold the stand-ins' positions PAD_LINES and STICK_LINES show."""
    set_current_input(
        snapshot=InputSnapshot(
            pressed_scancodes=frozenset(),
            modifiers=0,
            mouse_position=(0, 0),
            mouse_buttons=(False, False, False),
            mouse_focused=True,
            device_axes={STAND_IN_STICK.instance_id: (0.5, -1.0, 0.25)},
            device_buttons={STAND_IN_STICK.instance_id: (False, True, False, True)},
            device_hats={STAND_IN_STICK.instance_id: ((1, 0),)},
            controller_axes={STAND_IN_PAD.instance_id: (100, -200, 0, 0, 32767, 0)},
            controller_buttons={STAND_IN_PAD.instance_id: (True, False, False, True)},
        )
    )


def _hold_inputs(
    *,
    stick_axes: tuple[float, ...] = (0.0, 0.0, 0.0),
    stick_buttons: tuple[bool, ...] = (False, False, False, False),
    stick_hat: tuple[int, int] = (0, 0),
    pad_axes: tuple[int, ...] = (0, 0, 0, 0, 0, 0),
) -> None:
    """Make this frame's snapshot hold these stand-in positions (the pad's buttons released)."""
    set_current_input(
        snapshot=InputSnapshot(
            pressed_scancodes=frozenset(),
            modifiers=0,
            mouse_position=(0, 0),
            mouse_buttons=(False, False, False),
            mouse_focused=True,
            device_axes={STAND_IN_STICK.instance_id: stick_axes},
            device_buttons={STAND_IN_STICK.instance_id: stick_buttons},
            device_hats={STAND_IN_STICK.instance_id: (stick_hat,)},
            controller_axes={STAND_IN_PAD.instance_id: pad_axes},
        )
    )


def _draw_frame(scene: joystick_demo.Game) -> None:
    """Draw one frame as the scene manager does: the scene's update, then its sprite group."""
    scene.update()
    assert scene.screen is not None
    scene.render(scene.screen)


def _rgb(screen: pygame.Surface, position: tuple[int, int]) -> tuple[int, int, int]:
    """Return the colour of one screen pixel, without its alpha.

    Returns:
        The red, green and blue values.

    """
    color = screen.get_at(position)
    return (color.r, color.g, color.b)


def _demo_font() -> pygame.font.Font:
    """Return the demo's font: the bundled one at the demo's size (FontManager caches it).

    Returns:
        The font.

    """
    return cast(
        'pygame.font.Font',
        FontManager.pygame_font(
            font_config={'font_name': DEFAULT_FONT_NAME, 'font_size': joystick_demo.FONT_SIZE}
        ),
    )


def _demo_text(text: str, *, color: tuple[int, int, int] = WHITE) -> pygame.Surface:
    """Render ``text`` as the demo draws it: the demo's font, antialiased.

    Returns:
        The rendered text.

    """
    return _demo_font().render(text, antialias=True, color=color)


def _line_height() -> int:
    """Return the height of one line of the demo's text (its spacing included).

    Returns:
        The height in pixels.

    """
    return _demo_font().get_linesize() + joystick_demo.LINE_SPACING


def _shows(
    screen: pygame.Surface,
    *,
    text: str,
    topleft: tuple[int, int],
    color: tuple[int, int, int] = WHITE,
) -> bool:
    """Return whether ``screen`` shows ``text`` on black at ``topleft`` (any pixel format).

    Returns:
        True when every pixel of that region matches.

    """
    image = _demo_text(text, color=color)
    expected = pygame.Surface(image.get_size())
    expected.fill(BLACK)
    expected.blit(image, (0, 0))
    actual = screen.subsurface(pygame.Rect(topleft, image.get_size()))
    return pygame.image.tobytes(expected, 'RGB') == pygame.image.tobytes(actual, 'RGB')


def _header_line_topleft(line_number: int) -> tuple[int, int]:
    """Return where the demo draws header line ``line_number``.

    Returns:
        The top-left corner.

    """
    return (joystick_demo.MARGIN, joystick_demo.MARGIN + line_number * _line_height())


def _shows_column(screen: pygame.Surface, *, column: int, lines: list[str]) -> bool:
    """Return whether ``screen`` shows a device's ``lines`` in its column (the name in yellow).

    Returns:
        True when every line is drawn where the demo draws it.

    """
    header_line_count = 5
    columns_top = joystick_demo.MARGIN + (header_line_count + 1) * _line_height()
    column_left = joystick_demo.MARGIN + column * joystick_demo.COLUMN_WIDTH
    return all(
        _shows(
            screen,
            text=line,
            topleft=(column_left, columns_top + line_number * _line_height()),
            color=YELLOW if line_number == 0 else WHITE,
        )
        for line_number, line in enumerate(lines)
    )


def _shows_header(screen: pygame.Surface, *, lines: list[str]) -> bool:
    """Return whether ``screen`` shows the header ``lines`` at the top.

    Returns:
        True when every header line is drawn.

    """
    return all(
        _shows(screen, text=line, topleft=_header_line_topleft(line_number))
        for line_number, line in enumerate(lines)
    )


class TestReadout:
    """The demo draws every device's live inputs from the frame's snapshot."""

    def test_every_device_gets_a_column_with_its_event_layer(self):
        """The mapped pad shows its controller layer, the stick its joystick layer."""
        with running_demo() as (engine, scene):
            _set_device_positions()

            _draw_frame(scene)

            assert scene.screen is not None
            assert _shows_header(
                scene.screen,
                lines=[
                    'Joystick Demo 1.0',
                    'Input mode: auto',
                    'Devices: 2',
                    joystick_demo.NO_DEVICE_CHANGE,
                    joystick_demo.NO_INPUT_EVENT,
                ],
            )
            # The pad was added first (its controller arrived with the managers' start)
            assert [device.instance_id for device in engine.input_devices] == [9, 5]
            assert _shows_column(scene.screen, column=0, lines=PAD_LINES)
            assert _shows_column(scene.screen, column=1, lines=STICK_LINES)

    def test_device_lines_name_the_device_and_list_its_event_layer(self):
        """device_lines() is the column's text: who the device is, then its positions."""
        with running_demo() as (engine, _scene):
            _set_device_positions()

            columns = [joystick_demo.device_lines(device) for device in engine.input_devices]

            assert columns == [PAD_LINES, STICK_LINES]

    def test_a_device_without_a_guid_or_held_buttons_says_so(self):
        """An unknown GUID and no held button are spelled out."""
        no_guid_stick = dataclasses.replace(STAND_IN_STICK, guid=None)
        device = ConnectedInputDevice(
            descriptor=no_guid_stick,
            joystick=ReplayJoystick(descriptor=no_guid_stick),
            controller=None,
        )
        set_current_input(
            snapshot=InputSnapshot(
                pressed_scancodes=frozenset(),
                modifiers=0,
                mouse_position=(0, 0),
                mouse_buttons=(False, False, False),
                mouse_focused=True,
            )
        )

        lines = joystick_demo.device_lines(device)

        assert lines[1] == 'GUID: unknown'
        assert 'Buttons held: none' in lines

    def test_a_device_with_an_empty_name_still_gets_a_column(self):
        """An empty name is a line of no text, not a sprite too narrow to make."""
        unnamed_stick = dataclasses.replace(STAND_IN_STICK, name='')
        device = ConnectedInputDevice(
            descriptor=unnamed_stick,
            joystick=ReplayJoystick(descriptor=unnamed_stick),
            controller=None,
        )
        _hold_inputs()
        group: pygame.sprite.LayeredDirty[pygame.sprite.DirtySprite] = pygame.sprite.LayeredDirty()

        readout = joystick_demo.DeviceReadout(device=device, font=_demo_font(), groups=group)

        assert not readout.text_lines[0].text
        assert readout.text_lines[0].rect.width == _demo_font().size('')[0]
        assert len(group) == len(readout.sprites())

    def test_joystick_mode_shows_every_device_on_its_joystick_layer(self):
        """--input-mode joystick: the pad's column is its joystick layer."""
        with running_demo(input_mode='joystick') as (engine, scene):
            _set_device_positions()

            _draw_frame(scene)

            assert scene.screen is not None
            assert _shows(
                scene.screen, text='Input mode: joystick', topleft=_header_line_topleft(1)
            )
            assert [device.event_layer.kind for device in engine.input_devices] == [
                'joystick',
                'joystick',
            ]

    def test_without_devices_the_header_asks_for_one(self):
        """No device: the header says so and no column is drawn."""
        with running_demo(descriptors=()) as (_engine, scene):
            _draw_frame(scene)

            assert scene.screen is not None
            assert _shows(
                scene.screen, text='No devices: plug one in', topleft=_header_line_topleft(2)
            )


class TestGauges:
    """Below each device's text, sprites show its axes, held buttons and hats."""

    @pytest.mark.parametrize(('value', 'offset'), [(-1.0, 0), (0.0, 50), (1.0, 100)])
    def test_an_axis_marker_moves_with_its_axis(self, value, offset):
        """A joystick-layer axis puts its marker at the track's left, middle or right."""
        with running_demo() as (_engine, scene):
            readout = scene.device_readouts[STAND_IN_STICK.instance_id]
            _hold_inputs(stick_axes=(0.0, value, 0.0))

            _draw_frame(scene)

            track = readout.axis_tracks[1]
            assert track.rect.width == joystick_demo.AXIS_TRACK_WIDTH
            assert readout.axis_markers[1].rect.centerx == track.rect.left + offset
            assert readout.axis_markers[0].rect.centerx == track.rect.left + 50
            assert scene.screen is not None
            assert _rgb(scene.screen, readout.axis_markers[1].rect.center) == YELLOW[:3]

    @pytest.mark.parametrize(
        ('value', 'offset'), [(-32768, 0), (-32767, 0), (0, 50), (16384, 75), (32767, 100)]
    )
    def test_a_controller_axis_marker_spans_pygames_int_scale(self, value, offset):
        """A controller-layer axis (pygame's int scale) spans the same track."""
        with running_demo() as (_engine, scene):
            readout = scene.device_readouts[STAND_IN_PAD.instance_id]
            _hold_inputs(pad_axes=(0, 0, value, 0, 0, 0))

            _draw_frame(scene)

            track_left = readout.axis_tracks[2].rect.left
            assert readout.axis_markers[2].rect.centerx == track_left + offset

    def test_a_button_lamp_is_visible_only_while_held(self):
        """A button's lamp shows while it is held and goes when it is released."""
        with running_demo() as (_engine, scene):
            readout = scene.device_readouts[STAND_IN_STICK.instance_id]
            lamp = readout.button_lamps[2]
            assert scene.screen is not None
            _hold_inputs(stick_buttons=(False, False, True, False))

            _draw_frame(scene)

            assert lamp.visible
            assert not readout.button_lamps[1].visible
            assert _rgb(scene.screen, lamp.rect.center) == YELLOW[:3]

            _hold_inputs()
            _draw_frame(scene)

            assert not lamp.visible
            assert _rgb(scene.screen, lamp.rect.center) == BLACK[:3]

    def test_the_hat_dot_moves_with_the_hat(self):
        """The hat's dot sits HAT_STEP pixels from its centre toward each direction held."""
        with running_demo() as (_engine, scene):
            dot = scene.device_readouts[STAND_IN_STICK.instance_id].hat_dots[0]
            _hold_inputs(stick_hat=(0, 0))
            _draw_frame(scene)
            centre_x, centre_y = dot.rect.center
            step = joystick_demo.HAT_STEP

            for hat_x, hat_y in [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (0, 0)]:
                _hold_inputs(stick_hat=(hat_x, hat_y))
                _draw_frame(scene)

                assert dot.rect.center == (centre_x + step * hat_x, centre_y - step * hat_y)

    def test_the_gauges_sit_below_the_devices_text(self):
        """Every gauge is below the device's last line of text, inside its column."""
        with running_demo() as (engine, scene):
            _set_device_positions()
            _draw_frame(scene)

            for column, device in enumerate(engine.input_devices):
                readout = scene.device_readouts[device.instance_id]
                text_bottom = max(line.rect.bottom for line in readout.text_lines)
                column_left = joystick_demo.MARGIN + column * joystick_demo.COLUMN_WIDTH
                gauges = [
                    *readout.axis_tracks,
                    *readout.axis_markers,
                    *readout.button_lamps,
                    *readout.hat_dots,
                ]
                assert gauges
                for gauge in gauges:
                    assert gauge.rect.top >= text_bottom
                    assert column_left <= gauge.rect.left
                    assert gauge.rect.right <= column_left + joystick_demo.COLUMN_WIDTH
                    assert gauge in scene.all_sprites

    def test_a_pad_mapped_after_it_arrived_gets_its_controller_layers_gauges(self, mocker):
        """A pad first seen on its joystick layer and mapped later shows its controller layer.

        SDL could not say the pad was a game controller when it arrived (``is_controller``
        failed: hardware, so injected), so the engine added it on its joystick layer; its
        controller then arrived, and the engine moved it to the controller layer without telling
        the scene (``InputDevices.synchronize``, ``attach_controller``).
        """
        with running_demo(plugged_in_at_start=False) as (engine, scene):
            pad_id = STAND_IN_PAD.instance_id
            devices = active_sources().devices()
            mocker.patch.object(
                devices, 'is_controller', side_effect=pygame.error('cannot say yet')
            )
            engine.process_joystick_event(
                HashableEvent(pygame.JOYDEVICEADDED, device_index=1, guid='g')
            )
            joystick_layer_readout = scene.device_readouts[pad_id]
            assert joystick_layer_readout.text_lines[3].text == 'Events: joystick layer'
            mocker.stopall()
            engine.process_controller_event(
                HashableEvent(pygame.CONTROLLERDEVICEADDED, device_index=1, guid='g')
            )
            pad = next(device for device in engine.input_devices if device.instance_id == pad_id)
            assert pad.event_layer.kind == 'controller'
            _hold_inputs(pad_axes=(0, 0, 0, 0, 32767, 0))

            _draw_frame(scene)

            readout = scene.device_readouts[pad_id]
            assert readout is not joystick_layer_readout
            assert not any(
                sprite in scene.all_sprites for sprite in joystick_layer_readout.sprites()
            )
            assert readout.text_lines[3].text == 'Events: controller layer'
            assert len(readout.axis_markers) == len(pad.event_layer.axes)
            assert len(readout.button_lamps) == len(pad.event_layer.buttons)
            assert readout.hat_dots == []
            track_left = readout.axis_tracks[4].rect.left
            assert readout.axis_markers[4].rect.centerx == track_left + 100
            assert scene.screen is not None
            assert _shows_column(scene.screen, column=0, lines=joystick_demo.device_lines(pad))

    def test_a_removed_devices_sprites_are_gone(self):
        """A device's text and gauges come with it and go with it."""
        with running_demo(plugged_in_at_start=False) as (engine, scene):
            assert scene.device_readouts == {}
            engine.process_joystick_event(
                HashableEvent(pygame.JOYDEVICEADDED, device_index=0, guid='g')
            )
            readout = scene.device_readouts[STAND_IN_STICK.instance_id]
            sprites = readout.sprites()
            assert len(sprites) == (
                len(readout.text_lines)
                + 2 * STAND_IN_STICK.axis_count
                + STAND_IN_STICK.button_count
                + STAND_IN_STICK.hat_count
            )
            assert all(sprite in scene.all_sprites for sprite in sprites)

            engine.process_joystick_event(
                HashableEvent(pygame.JOYDEVICEREMOVED, instance_id=STAND_IN_STICK.instance_id)
            )

            assert scene.device_readouts == {}
            assert not any(sprite in scene.all_sprites for sprite in sprites)

    def test_the_text_lines_are_text_sprites(self):
        """The header and every device line are text sprites, their text replaced as it changes."""
        with running_demo() as (_engine, scene):
            readout = scene.device_readouts[STAND_IN_STICK.instance_id]
            _hold_inputs(stick_axes=(0.0, 1.0, 0.0))
            _draw_frame(scene)

            assert all(isinstance(line, TextSprite) for line in scene.header_text)
            assert all(isinstance(line, TextSprite) for line in readout.text_lines)
            assert readout.text_lines[5].text == 'Axis 1: 1.0'

            _hold_inputs(stick_axes=(0.0, -0.5, 0.0))
            _draw_frame(scene)

            assert readout.text_lines[5].text == 'Axis 1: -0.5'

    def test_update_draws_only_sprites(self):
        """update() draws nothing on the screen: everything shown is the sprite group's."""
        with running_demo() as (_engine, scene):
            assert scene.screen is not None
            assert scene.background_color is not None
            assert scene.background_color[:3] == BLACK[:3]
            scene.screen.fill(BLACK)
            _set_device_positions()

            scene.update()

            width, height = scene.screen.get_size()
            expected = bytes(BLACK[:3]) * (width * height)
            assert pygame.image.tobytes(scene.screen, 'RGB') == expected

            # Drawing the group (all of it: the fill above wiped what it drew) shows the frame
            scene.all_sprites.repaint_rect(scene.screen.get_rect())
            scene.render(scene.screen)

            assert _shows_column(scene.screen, column=0, lines=PAD_LINES)


class TestHotPlug:
    """Devices plugged in and out are reported in the header and get or lose their column."""

    def test_a_joystick_plugged_in_and_out_is_reported(self):
        """The joystick's added and removed events reach the demo as device notices."""
        with running_demo(plugged_in_at_start=False) as (engine, scene):
            stick_id = STAND_IN_STICK.instance_id
            engine.process_joystick_event(
                HashableEvent(pygame.JOYDEVICEADDED, device_index=0, guid='g')
            )
            _draw_frame(scene)
            assert scene.screen is not None
            assert _shows(
                scene.screen,
                text='Connected: Stand-in Flight Stick',
                topleft=_header_line_topleft(3),
            )
            assert _shows(scene.screen, text='Devices: 1', topleft=_header_line_topleft(2))

            engine.process_joystick_event(
                HashableEvent(pygame.JOYDEVICEREMOVED, instance_id=stick_id)
            )
            _draw_frame(scene)

            assert _shows(
                scene.screen,
                text='Disconnected: Stand-in Flight Stick',
                topleft=_header_line_topleft(3),
            )
            assert _shows(
                scene.screen, text='No devices: plug one in', topleft=_header_line_topleft(2)
            )

    def test_a_game_pad_plugged_in_and_out_is_reported_once_each_way(self):
        """A mapped pad arrives and leaves on both layers; the demo hears of it once each way."""
        with running_demo(plugged_in_at_start=False) as (engine, scene):
            pad_id = STAND_IN_PAD.instance_id
            engine.process_joystick_event(
                HashableEvent(pygame.JOYDEVICEADDED, device_index=1, guid='g')
            )
            assert scene.last_device_change == joystick_demo.NO_DEVICE_CHANGE
            engine.process_controller_event(
                HashableEvent(pygame.CONTROLLERDEVICEADDED, device_index=1, guid='g')
            )
            assert scene.last_device_change == 'Connected: Stand-in Game Pad'
            engine.process_controller_event(
                HashableEvent(pygame.CONTROLLERDEVICEREMAPPED, instance_id=pad_id)
            )
            engine.process_joystick_event(
                HashableEvent(pygame.JOYDEVICEREMOVED, instance_id=pad_id)
            )
            assert scene.last_device_change == 'Connected: Stand-in Game Pad'
            engine.process_controller_event(
                HashableEvent(pygame.CONTROLLERDEVICEREMOVED, instance_id=pad_id)
            )

            _draw_frame(scene)

            assert scene.screen is not None
            assert _shows(
                scene.screen,
                text='Disconnected: Stand-in Game Pad',
                topleft=_header_line_topleft(3),
            )


# One input event of each kind the demo reports, from the device whose event layer sends it
REPORTED_EVENTS = [
    (
        HashableEvent(pygame.JOYAXISMOTION, instance_id=5, axis=0, value=0.5),
        'on_joy_axis_motion_event from instance 5',
    ),
    (
        HashableEvent(pygame.JOYBALLMOTION, instance_id=5, ball=0, rel=(1, 1)),
        'on_joy_ball_motion_event from instance 5',
    ),
    (
        HashableEvent(pygame.JOYHATMOTION, instance_id=5, hat=0, value=(0, 1)),
        'on_joy_hat_motion_event from instance 5',
    ),
    (
        HashableEvent(pygame.JOYBUTTONDOWN, instance_id=5, button=2),
        'on_joy_button_down_event from instance 5',
    ),
    (
        HashableEvent(pygame.JOYBUTTONUP, instance_id=5, button=2),
        'on_joy_button_up_event from instance 5',
    ),
    (
        HashableEvent(pygame.CONTROLLERAXISMOTION, instance_id=9, axis=0, value=1000),
        'on_controller_axis_motion_event from instance 9',
    ),
    (
        HashableEvent(pygame.CONTROLLERBUTTONDOWN, instance_id=9, button=0),
        'on_controller_button_down_event from instance 9',
    ),
    (
        HashableEvent(pygame.CONTROLLERBUTTONUP, instance_id=9, button=0),
        'on_controller_button_up_event from instance 9',
    ),
]


class TestInputEvents:
    """Each press reaches the demo once, from the device's event layer, and is shown."""

    @pytest.mark.parametrize(('event', 'report'), REPORTED_EVENTS)
    def test_the_last_input_event_is_shown(self, event, report):
        """The header's last line names the handler the event reached and its device."""
        with running_demo() as (engine, scene):
            dispatcher = (
                engine.process_controller_event
                if event.type in CONTROLLER_INPUT_EVENT_TYPES
                else engine.process_joystick_event
            )
            dispatcher(event)
            _draw_frame(scene)

            assert scene.screen is not None
            assert _shows(scene.screen, text=report, topleft=_header_line_topleft(4))

    def test_a_mapped_pads_joystick_layer_press_never_reaches_the_demo(self):
        """The pad's joystick-layer copy of a press is dropped: only its controller one shows."""
        with running_demo() as (engine, scene):
            engine.process_joystick_event(
                HashableEvent(pygame.JOYBUTTONDOWN, instance_id=STAND_IN_PAD.instance_id, button=0)
            )
            assert scene.last_input_event == joystick_demo.NO_INPUT_EVENT

            engine.process_controller_event(
                HashableEvent(
                    pygame.CONTROLLERBUTTONDOWN, instance_id=STAND_IN_PAD.instance_id, button=0
                )
            )

            assert scene.last_input_event == 'on_controller_button_down_event from instance 9'


@pytest.fixture
def engine_run(mocker: MockerFixture) -> Generator[None]:
    """Let the test start a real engine (see demo_runs.engine_run_environment).

    Yields:
        None, while the environment is in place.

    """
    yield from engine_run_environment(mocker)


@pytest.mark.usefixtures('engine_run')
def test_main_runs_the_demo_headless(mocker: MockerFixture) -> None:
    """main() starts the demo on the real engine; it runs until quit."""
    script = run_demo_main(mocker=mocker, module=joystick_demo, main=joystick_demo.main)

    assert any(isinstance(scene, joystick_demo.Game) for scene in script.scenes_seen)
