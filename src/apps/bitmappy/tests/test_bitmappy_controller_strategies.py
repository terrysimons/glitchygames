"""Tests for src/apps/bitmappy/src/bitmappy/controllers/strategies.py.

Each mode strategy maps controller buttons to editor actions. These tests press and release
buttons through the strategies a real ModeSwitcher hands out for a real
ControllerEventHandler, over a stand-in editor, and check the canvas, slider and undo state
that results.
"""

from __future__ import annotations

from typing import Any

import pygame
import pytest

from bitmappy.controllers.event_handler import ControllerEventHandler
from bitmappy.controllers.manager import (
    ControllerInfo,
    ControllerStatus,
    MultiControllerManager,
)
from bitmappy.controllers.modes import ControllerMode, ModeSwitcher
from bitmappy.controllers.selection import ControllerSelection
from glitchygames.input.state import InputSnapshot, set_current_input

CONTROLLER_ID = 0
INSTANCE_ID = 12
RED = (255, 0, 0)


@pytest.fixture(autouse=True)
def fresh_controller_manager(mocker):
    """Give each test its own MultiControllerManager singleton, restoring the shared one after."""
    mocker.patch.object(MultiControllerManager, '_instance', None)


class FakeCanvasInterface:
    """A canvas interface holding pixels in a dict."""

    def __init__(self) -> None:
        """Start with no painted pixels."""
        self.painted: dict[tuple[int, int], tuple[int, ...]] = {}

    def get_pixel_at(self, x: int, y: int) -> tuple[int, ...]:
        """Return the pixel's color (white when never painted).

        Returns:
            The color tuple.

        """
        return self.painted.get((x, y), (255, 255, 255))

    def set_pixel_at(self, x: int, y: int, color: tuple[int, ...]) -> None:
        """Record the pixel's new color."""
        self.painted[x, y] = color


class FakeCanvas:
    """A 32 x 32 canvas reached through a canvas interface."""

    def __init__(self) -> None:
        """Make the canvas."""
        self.canvas_interface = FakeCanvasInterface()
        self.pixels_across = 32
        self.pixels_tall = 32
        self.width = 32
        self.height = 32
        self.current_animation = 'idle'
        self.current_frame = 0

    def force_redraw(self) -> None:
        """Redraw requests need no work here."""


class FakeSlider:
    """A slider holding only its value."""

    def __init__(self, *, value: int) -> None:
        """Start at ``value``."""
        self.value = value


class FakeCanvasOperationTracker:
    """Records the pixel changes submitted for undo."""

    def __init__(self) -> None:
        """Start with nothing submitted."""
        self.frame_changes: list[tuple[str, int, list[Any]]] = []

    def add_frame_pixel_changes(self, animation: str, frame: int, changes: list[Any]) -> None:
        """Record frame-specific pixel changes."""
        self.frame_changes.append((animation, frame, changes))

    def add_pixel_changes(self, changes: list[Any]) -> None:
        """Global changes are not expected in these tests.

        Raises:
            AssertionError: Always, naming the unexpected changes.

        """
        raise AssertionError(changes)


class FakePositionTracker:
    """Records the controller position changes submitted for undo."""

    def __init__(self) -> None:
        """Start with nothing submitted."""
        self.position_changes: list[tuple[Any, ...]] = []

    def add_controller_position_change(self, *change: Any) -> None:
        """Record one position change."""
        self.position_changes.append(change)


class FakeEditor:
    """The parts of the editor the strategies reach."""

    def __init__(self) -> None:
        """Make an editor with a canvas, sliders at 100 and the selected frame visible."""
        self.canvas = FakeCanvas()
        self.mode_switcher = ModeSwitcher()
        self.multi_controller_manager = MultiControllerManager()
        self.controller_selections: dict[int, ControllerSelection] = {}
        self.selected_frame_visible = True
        self.red_slider = FakeSlider(value=100)
        self.green_slider = FakeSlider(value=100)
        self.blue_slider = FakeSlider(value=100)
        self.current_pixel_changes: list[Any] = []
        self.canvas_operation_tracker = FakeCanvasOperationTracker()
        self.controller_position_operation_tracker = FakePositionTracker()
        self.undo_count = 0
        self.redo_count = 0
        self.slider_events: list[tuple[str, int]] = []

    def get_current_color(self) -> tuple[int, ...]:
        """Return the color picker's color.

        Returns:
            Red.

        """
        return RED

    def handle_undo(self) -> None:
        """Count undo requests."""
        self.undo_count += 1

    def handle_redo(self) -> None:
        """Count redo requests."""
        self.redo_count += 1

    def on_slider_event(self, event: Any, trigger: Any) -> None:
        """Record the slider events (each updates the color well)."""
        self.slider_events.append((trigger.name, trigger.value))


def _make_handler(*, mode: ControllerMode, position: tuple[int, int] = (10, 10)):
    """Build a handler with one controller in ``mode`` at ``position``.

    The controller is known to the manager (slot 0, instance 12) and has a selection.

    Returns:
        The (handler, editor) pair.

    """
    editor = FakeEditor()
    handler = ControllerEventHandler(editor=editor)  # type: ignore[arg-type]
    editor.mode_switcher.set_handler(handler)
    editor.mode_switcher.register_controller(CONTROLLER_ID, mode)
    editor.mode_switcher.save_controller_position(CONTROLLER_ID, position)
    editor.multi_controller_manager.controllers[INSTANCE_ID] = ControllerInfo(
        controller_id=CONTROLLER_ID,
        instance_id=INSTANCE_ID,
        status=ControllerStatus.ACTIVE,
    )
    editor.controller_selections[CONTROLLER_ID] = ControllerSelection(
        controller_id=CONTROLLER_ID,
        instance_id=INSTANCE_ID,
    )
    return handler, editor


def _strategy(editor: FakeEditor) -> Any:
    """Return the strategy for the controller's current mode.

    Returns:
        The mode strategy.

    """
    strategy = editor.mode_switcher.get_strategy(CONTROLLER_ID)
    assert strategy is not None
    return strategy


def _position_of(editor: FakeEditor) -> tuple[int, int]:
    """Return the controller's saved position in its current mode.

    Returns:
        The (x, y) position.

    """
    position = editor.mode_switcher.get_controller_position(CONTROLLER_ID)
    assert position is not None
    return position.position


def _hold_a_button(*, held: bool) -> None:
    """Make this frame's input snapshot hold (or not) the A button of the controller."""
    buttons = [False] * (pygame.CONTROLLER_BUTTON_A + 1)
    buttons[pygame.CONTROLLER_BUTTON_A] = held
    set_current_input(
        snapshot=InputSnapshot(
            pressed_scancodes=frozenset(),
            modifiers=0,
            mouse_position=(0, 0),
            mouse_buttons=(False, False, False),
            mouse_focused=True,
            device_buttons={INSTANCE_ID: tuple(buttons)},
        ),
    )


class TestFilmStripModeStrategy:
    """Film strip mode buttons."""

    def test_x_redoes_while_the_selected_frame_is_visible(self):
        """X is redo when the selected frame is shown."""
        _handler, editor = _make_handler(mode=ControllerMode.FILM_STRIP)

        _strategy(editor).handle_button_down(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_X)

        assert editor.redo_count == 1

    def test_x_does_nothing_while_the_selected_frame_is_hidden(self):
        """X is disabled when the selected frame is hidden."""
        _handler, editor = _make_handler(mode=ControllerMode.FILM_STRIP)
        editor.selected_frame_visible = False

        _strategy(editor).handle_button_down(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_X)

        assert editor.redo_count == 0

    def test_b_undoes(self):
        """B is undo."""
        _handler, editor = _make_handler(mode=ControllerMode.FILM_STRIP)

        _strategy(editor).handle_button_down(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_B)

        assert editor.undo_count == 1

    @pytest.mark.parametrize(
        ('button', 'handler_method'),
        [
            (pygame.CONTROLLER_BUTTON_DPAD_RIGHT, 'multi_controller_next_frame'),
            (pygame.CONTROLLER_BUTTON_RIGHTSHOULDER, 'multi_controller_next_frame'),
            (pygame.CONTROLLER_BUTTON_DPAD_UP, 'multi_controller_previous_animation'),
            (pygame.CONTROLLER_BUTTON_START, 'multi_controller_activate'),
        ],
    )
    def test_navigation_buttons_reach_the_film_strip(self, mocker, button, handler_method):
        """Navigation buttons call the film strip action for this controller."""
        handler, editor = _make_handler(mode=ControllerMode.FILM_STRIP)
        film_strip_action = mocker.patch.object(handler, handler_method)

        _strategy(editor).handle_button_down(CONTROLLER_ID, button)

        film_strip_action.assert_called_once_with(CONTROLLER_ID)

    def test_an_unmapped_button_and_any_release_do_nothing(self):
        """Back is not mapped, and releases are no-ops in film strip mode."""
        _handler, editor = _make_handler(mode=ControllerMode.FILM_STRIP)

        _strategy(editor).handle_button_down(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_BACK)
        _strategy(editor).handle_button_up(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_A)

        assert (editor.undo_count, editor.redo_count) == (0, 0)


class TestCanvasModeStrategyButtonDown:
    """Canvas mode button presses."""

    def test_a_starts_a_drag_and_paints(self):
        """A starts a drag and paints the pixel under the cursor."""
        handler, editor = _make_handler(mode=ControllerMode.CANVAS)

        _strategy(editor).handle_button_down(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_A)

        assert handler.controller_drags[CONTROLLER_ID]['active'] is True
        assert editor.canvas.canvas_interface.painted == {(10, 10): RED}

    def test_a_does_nothing_while_the_selected_frame_is_hidden(self):
        """A is disabled when the selected frame is hidden."""
        handler, editor = _make_handler(mode=ControllerMode.CANVAS)
        editor.selected_frame_visible = False

        _strategy(editor).handle_button_down(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_A)

        assert handler.controller_drags == {}
        assert editor.canvas.canvas_interface.painted == {}

    def test_b_undoes_and_x_redoes(self):
        """B is undo and X is redo while the selected frame is visible."""
        _handler, editor = _make_handler(mode=ControllerMode.CANVAS)

        _strategy(editor).handle_button_down(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_B)
        _strategy(editor).handle_button_down(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_X)

        assert (editor.undo_count, editor.redo_count) == (1, 1)

    def test_x_does_nothing_while_the_selected_frame_is_hidden(self):
        """X is disabled when the selected frame is hidden."""
        _handler, editor = _make_handler(mode=ControllerMode.CANVAS)
        editor.selected_frame_visible = False

        _strategy(editor).handle_button_down(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_X)

        assert editor.redo_count == 0

    def test_y_toggles_the_selected_frame_visibility(self, mocker):
        """Y asks the film strip to toggle the selected frame's visibility."""
        handler, editor = _make_handler(mode=ControllerMode.CANVAS)
        toggle = mocker.patch.object(handler, 'multi_controller_toggle_selected_frame_visibility')

        _strategy(editor).handle_button_down(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_Y)

        toggle.assert_called_once_with(CONTROLLER_ID)

    @pytest.mark.parametrize(
        ('button', 'expected_position'),
        [
            (pygame.CONTROLLER_BUTTON_DPAD_LEFT, (9, 10)),
            (pygame.CONTROLLER_BUTTON_DPAD_RIGHT, (11, 10)),
            (pygame.CONTROLLER_BUTTON_DPAD_UP, (10, 9)),
            (pygame.CONTROLLER_BUTTON_DPAD_DOWN, (10, 11)),
        ],
    )
    def test_dpad_starts_continuous_movement(self, button, expected_position):
        """A D-pad press moves one pixel at once and starts continuous movement."""
        handler, editor = _make_handler(mode=ControllerMode.CANVAS)

        _strategy(editor).handle_button_down(CONTROLLER_ID, button)

        assert _position_of(editor) == expected_position
        assert CONTROLLER_ID in handler.canvas_continuous_movements

    def test_an_unmapped_button_changes_nothing(self):
        """Back is not handled in canvas mode."""
        handler, editor = _make_handler(mode=ControllerMode.CANVAS)

        _strategy(editor).handle_button_down(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_BACK)

        assert _position_of(editor) == (10, 10)
        assert handler.controller_drags == {}
        assert (editor.undo_count, editor.redo_count) == (0, 0)


class TestCanvasModeStrategyShoulderButtons:
    """Shoulder buttons jump 8 pixels, or paint 8 while A is held, along the fill direction."""

    @pytest.mark.parametrize(
        ('button', 'fill_direction', 'expected_position'),
        [
            (pygame.CONTROLLER_BUTTON_LEFTSHOULDER, 'HORIZONTAL', (2, 10)),
            (pygame.CONTROLLER_BUTTON_RIGHTSHOULDER, 'HORIZONTAL', (18, 10)),
            (pygame.CONTROLLER_BUTTON_LEFTSHOULDER, 'VERTICAL', (10, 2)),
            (pygame.CONTROLLER_BUTTON_RIGHTSHOULDER, 'VERTICAL', (10, 18)),
        ],
    )
    def test_without_a_jumps_without_painting(self, button, fill_direction, expected_position):
        """Shoulder alone jumps along the fill direction and paints nothing."""
        _handler, editor = _make_handler(mode=ControllerMode.CANVAS)
        editor.controller_selections[CONTROLLER_ID].set_fill_direction(fill_direction)
        _hold_a_button(held=False)

        _strategy(editor).handle_button_down(CONTROLLER_ID, button)

        assert _position_of(editor) == expected_position
        assert editor.canvas.canvas_interface.painted == {}

    @pytest.mark.parametrize(
        ('button', 'fill_direction', 'expected_pixels', 'expected_position'),
        [
            (
                pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
                'HORIZONTAL',
                [(x, 10) for x in range(10, 18)],
                (18, 10),
            ),
            (
                pygame.CONTROLLER_BUTTON_LEFTSHOULDER,
                'HORIZONTAL',
                [(x, 10) for x in range(3, 11)],
                (2, 10),
            ),
            (
                pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
                'VERTICAL',
                [(10, y) for y in range(10, 18)],
                (10, 18),
            ),
            (
                pygame.CONTROLLER_BUTTON_LEFTSHOULDER,
                'VERTICAL',
                [(10, y) for y in range(3, 11)],
                (10, 2),
            ),
        ],
    )
    def test_with_a_held_paints_a_line(
        self,
        button,
        fill_direction,
        expected_pixels,
        expected_position,
    ):
        """Shoulder with A held paints 8 pixels along the fill direction."""
        _handler, editor = _make_handler(mode=ControllerMode.CANVAS)
        editor.controller_selections[CONTROLLER_ID].set_fill_direction(fill_direction)
        _hold_a_button(held=True)

        _strategy(editor).handle_button_down(CONTROLLER_ID, button)

        assert sorted(editor.canvas.canvas_interface.painted) == sorted(expected_pixels)
        assert _position_of(editor) == expected_position

    def test_a_controller_without_a_selection_does_nothing(self):
        """No controller selection: no fill direction, so the shoulder does nothing."""
        _handler, editor = _make_handler(mode=ControllerMode.CANVAS)
        del editor.controller_selections[CONTROLLER_ID]

        _strategy(editor).handle_button_down(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_LEFTSHOULDER)

        assert _position_of(editor) == (10, 10)


class TestCanvasModeStrategyButtonUp:
    """Canvas mode button releases."""

    def test_dpad_release_stops_the_movement_and_records_it(self):
        """Releasing the D-pad ends continuous movement as one undo step."""
        handler, editor = _make_handler(mode=ControllerMode.CANVAS)
        strategy = _strategy(editor)
        strategy.handle_button_down(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_DPAD_RIGHT)
        handler.canvas._canvas_move_cursor(CONTROLLER_ID, 1, 0)

        strategy.handle_button_up(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_DPAD_RIGHT)

        assert CONTROLLER_ID not in handler.canvas_continuous_movements
        assert editor.controller_position_operation_tracker.position_changes[-1] == (
            CONTROLLER_ID,
            (11, 10),
            (12, 10),
            'canvas',
            'canvas',
        )

    def test_a_release_ends_the_drag_and_submits_its_pixels(self):
        """Releasing A ends the drag and submits the painted pixels for undo."""
        handler, editor = _make_handler(mode=ControllerMode.CANVAS)
        strategy = _strategy(editor)
        strategy.handle_button_down(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_A)

        strategy.handle_button_up(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_A)

        assert handler.controller_drags[CONTROLLER_ID]['active'] is False
        assert editor.canvas_operation_tracker.frame_changes == [
            ('idle', 0, [(10, 10, (255, 255, 255), RED)]),
        ]

    def test_another_release_changes_nothing(self):
        """Releasing B neither stops a movement nor ends a drag."""
        handler, editor = _make_handler(mode=ControllerMode.CANVAS)
        strategy = _strategy(editor)
        strategy.handle_button_down(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_DPAD_DOWN)
        strategy.handle_button_down(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_A)

        strategy.handle_button_up(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_B)

        assert CONTROLLER_ID in handler.canvas_continuous_movements
        assert handler.controller_drags[CONTROLLER_ID]['active'] is True


class TestSliderModeStrategy:
    """Slider mode buttons."""

    @pytest.mark.parametrize(
        ('button', 'expected_value'),
        [
            (pygame.CONTROLLER_BUTTON_DPAD_LEFT, 99),
            (pygame.CONTROLLER_BUTTON_DPAD_RIGHT, 101),
            (pygame.CONTROLLER_BUTTON_LEFTSHOULDER, 92),
            (pygame.CONTROLLER_BUTTON_RIGHTSHOULDER, 108),
        ],
    )
    def test_adjusting_buttons_start_continuous_adjustment(self, button, expected_value):
        """D-pad left/right adjust by 1 and the shoulders by 8, continuing while held."""
        handler, editor = _make_handler(mode=ControllerMode.R_SLIDER)

        _strategy(editor).handle_button_down(CONTROLLER_ID, button)

        assert editor.red_slider.value == expected_value
        assert CONTROLLER_ID in handler.slider_continuous_adjustments

    @pytest.mark.parametrize(
        ('button', 'expected_mode'),
        [
            (pygame.CONTROLLER_BUTTON_DPAD_UP, ControllerMode.R_SLIDER),
            (pygame.CONTROLLER_BUTTON_DPAD_DOWN, ControllerMode.B_SLIDER),
        ],
    )
    def test_dpad_up_and_down_switch_sliders(self, button, expected_mode):
        """D-pad up/down move between the R, G and B sliders."""
        _handler, editor = _make_handler(mode=ControllerMode.G_SLIDER)

        _strategy(editor).handle_button_down(CONTROLLER_ID, button)

        assert editor.mode_switcher.get_controller_mode(CONTROLLER_ID) == expected_mode

    @pytest.mark.parametrize('button', [pygame.CONTROLLER_BUTTON_A, pygame.CONTROLLER_BUTTON_BACK])
    def test_a_and_unmapped_buttons_do_nothing(self, button):
        """A has no slider action, and Back is not mapped."""
        handler, editor = _make_handler(mode=ControllerMode.R_SLIDER)

        _strategy(editor).handle_button_down(CONTROLLER_ID, button)

        assert editor.red_slider.value == 100
        assert handler.slider_continuous_adjustments == {}

    def test_releasing_an_adjusting_button_stops_the_adjustment(self):
        """Releasing a D-pad or shoulder button ends the adjustment; its step set the color."""
        handler, editor = _make_handler(mode=ControllerMode.R_SLIDER)
        strategy = _strategy(editor)
        strategy.handle_button_down(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_RIGHTSHOULDER)

        strategy.handle_button_up(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_RIGHTSHOULDER)

        assert handler.slider_continuous_adjustments == {}
        assert editor.slider_events == [('R', 108)]

    def test_releasing_another_button_keeps_the_adjustment(self):
        """Releasing A leaves a held adjustment running."""
        handler, editor = _make_handler(mode=ControllerMode.R_SLIDER)
        strategy = _strategy(editor)
        strategy.handle_button_down(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_DPAD_LEFT)

        strategy.handle_button_up(CONTROLLER_ID, pygame.CONTROLLER_BUTTON_A)

        assert CONTROLLER_ID in handler.slider_continuous_adjustments
        assert editor.slider_events == [('R', 99)]
