"""Tests for glitchygames/bitmappy/controllers/canvas_operations.py.

The canvas delegate paints, erases, moves and jumps a controller's canvas cursor and
collects drag strokes for undo. These tests drive it through a real ControllerEventHandler,
a real ModeSwitcher and small stand-in canvases, and check the pixels, positions and undo
records that result.
"""

from __future__ import annotations

from typing import Any

import pytest

from glitchygames.bitmappy.controllers.event_handler import ControllerEventHandler
from glitchygames.bitmappy.controllers.manager import MultiControllerManager
from glitchygames.bitmappy.controllers.modes import ControllerMode, ModeSwitcher
from glitchygames.sources import advance_frame_clock

CONTROLLER_ID = 0
RED = (255, 0, 0)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)


@pytest.fixture(autouse=True)
def fresh_controller_manager(mocker):
    """Give each test its own MultiControllerManager singleton, restoring the shared one after."""
    mocker.patch.object(MultiControllerManager, '_instance', None)


class FakeCanvasInterface:
    """A canvas interface holding pixels in a dict (missing pixels read as white)."""

    def __init__(self, *, error_on_read: Exception | None = None) -> None:
        """Start with no painted pixels; optionally raise ``error_on_read`` on every read."""
        self.painted: dict[tuple[int, int], tuple[int, ...]] = {}
        self.error_on_read = error_on_read

    def get_pixel_at(self, x: int, y: int) -> tuple[int, ...]:
        """Return the pixel's color (white when never painted).

        Returns:
            The color tuple.

        """
        if self.error_on_read is not None:
            raise self.error_on_read
        return self.painted.get((x, y), WHITE)

    def set_pixel_at(self, x: int, y: int, color: tuple[int, ...]) -> None:
        """Record the pixel's new color."""
        self.painted[x, y] = color


class InterfaceCanvas:
    """A canvas reached through a canvas interface, like AnimatedCanvasSprite."""

    def __init__(
        self,
        *,
        pixels_across: int = 8,
        pixels_tall: int = 8,
        pixel_width: int = 1,
    ) -> None:
        """Make a canvas of the given pixel size, each pixel drawn ``pixel_width`` wide.

        As on AnimatedCanvasSprite, ``width``/``height`` are the on-screen size (pixel count
        times ``pixel_width``) and ``pixels_across``/``pixels_tall`` the pixel count.
        """
        self.canvas_interface = FakeCanvasInterface()
        self.pixels_across = pixels_across
        self.pixels_tall = pixels_tall
        self.width = pixels_across * pixel_width
        self.height = pixels_tall * pixel_width
        self.current_animation: str | None = 'idle'
        self.current_frame: int | None = 0
        self.redraw_count = 0

    def force_redraw(self) -> None:
        """Count redraw requests."""
        self.redraw_count += 1


class PixelListCanvas:
    """A canvas without a canvas interface: a flat pixel list with dirty flags."""

    def __init__(self, *, pixels_across: int = 4, pixels_tall: int = 4) -> None:
        """Make a white canvas of the given pixel size."""
        self.pixels_across = pixels_across
        self.pixels_tall = pixels_tall
        self.pixels: list[tuple[int, ...]] = [WHITE] * (pixels_across * pixels_tall)
        self.dirty_pixels = [False] * (pixels_across * pixels_tall)
        self.dirty = 0


class RecordedOperation:
    """An undo stack entry."""

    def __init__(self, *, operation_type: str, description: str) -> None:
        """Store the entry's type and description."""
        self.operation_type = operation_type
        self.description = description


class FakeUndoRedoManager:
    """An undo/redo manager holding only its undo stack."""

    def __init__(self, *, undo_stack: list[RecordedOperation]) -> None:
        """Hold the given undo stack."""
        self.undo_stack = undo_stack


class FakeCanvasOperationTracker:
    """Records the pixel changes submitted for undo."""

    def __init__(self) -> None:
        """Start with nothing submitted."""
        self.frame_changes: list[tuple[str, int, list[Any]]] = []
        self.global_changes: list[list[Any]] = []

    def add_frame_pixel_changes(self, animation: str, frame: int, changes: list[Any]) -> None:
        """Record frame-specific pixel changes."""
        self.frame_changes.append((animation, frame, changes))

    def add_pixel_changes(self, changes: list[Any]) -> None:
        """Record global pixel changes."""
        self.global_changes.append(changes)


class FakePositionTracker:
    """Records the controller position changes submitted for undo."""

    def __init__(self) -> None:
        """Start with nothing submitted."""
        self.position_changes: list[tuple[Any, ...]] = []

    def add_controller_position_change(
        self,
        controller_id: int,
        old_position: tuple[int, int],
        new_position: tuple[int, int],
        old_mode: str | None,
        new_mode: str | None,
    ) -> None:
        """Record one position change."""
        self.position_changes.append((
            controller_id,
            old_position,
            new_position,
            old_mode,
            new_mode,
        ))


class FakeEditor:
    """The parts of the editor the canvas delegate reads."""

    def __init__(self, *, canvas: Any) -> None:
        """Make an editor with the given canvas and RED as the current color."""
        self.canvas = canvas
        self.mode_switcher = ModeSwitcher()
        self.multi_controller_manager = MultiControllerManager()
        self.controller_selections: dict[int, Any] = {}
        self.current_color: tuple[int, ...] = RED
        self.undo_redo_manager = FakeUndoRedoManager(undo_stack=[])
        self.current_pixel_changes: list[Any] = []
        self.canvas_operation_tracker = FakeCanvasOperationTracker()
        self.controller_position_operation_tracker = FakePositionTracker()

    def get_current_color(self) -> tuple[int, ...]:
        """Return the color picker's color.

        Returns:
            The current color.

        """
        return self.current_color


def _make_handler(*, canvas: Any = None, position: tuple[int, int] | None = (2, 2)):
    """Build a handler over a FakeEditor with one canvas-mode controller at ``position``.

    Args:
        canvas: The editor's canvas (an InterfaceCanvas when None).
        position: The controller's canvas position, or None to leave it unregistered.

    Returns:
        The (handler, editor) pair.

    """
    editor = FakeEditor(canvas=InterfaceCanvas() if canvas is None else canvas)
    handler = ControllerEventHandler(editor=editor)  # type: ignore[arg-type]
    if position is not None:
        editor.mode_switcher.register_controller(CONTROLLER_ID, ControllerMode.CANVAS)
        editor.mode_switcher.save_controller_position(CONTROLLER_ID, position)
    return handler, editor


def _start_drag(handler: ControllerEventHandler, *, active: bool = True) -> dict[str, Any]:
    """Give the controller a drag record, as the A button does.

    Returns:
        The drag record.

    """
    drag_info: dict[str, Any] = {'active': active, 'pixels_drawn': [], 'start_time': 0.0}
    handler.controller_drags[CONTROLLER_ID] = drag_info
    return drag_info


def _position_of(editor: FakeEditor) -> tuple[int, int]:
    """Return the controller's saved canvas position.

    Returns:
        The (x, y) position.

    """
    position = editor.mode_switcher.get_controller_position(CONTROLLER_ID)
    assert position is not None
    return position.position


class TestHandleControllerDragEnd:
    """Ending a drag submits its pixels for undo."""

    def test_without_a_drag_record_nothing_happens(self):
        """A controller that never started a drag submits nothing."""
        handler, editor = _make_handler()

        handler.canvas.handle_controller_drag_end(CONTROLLER_ID)

        assert editor.canvas_operation_tracker.frame_changes == []
        assert editor.canvas_operation_tracker.global_changes == []

    def test_an_inactive_drag_is_left_alone(self):
        """A drag that already ended is not ended again."""
        handler, editor = _make_handler()
        drag_info = _start_drag(handler, active=False)

        handler.canvas.handle_controller_drag_end(CONTROLLER_ID)

        assert 'end_time' not in drag_info
        assert editor.canvas_operation_tracker.frame_changes == []

    def test_a_drag_without_pixels_ends_and_submits_nothing(self):
        """An empty drag is marked ended with its end position, and nothing is submitted."""
        handler, editor = _make_handler(position=(3, 4))
        drag_info = _start_drag(handler)

        handler.canvas.handle_controller_drag_end(CONTROLLER_ID)

        assert drag_info['active'] is False
        assert drag_info['end_position'].position == (3, 4)
        assert editor.canvas_operation_tracker.frame_changes == []

    def test_a_drag_submits_its_pixels_for_the_current_frame(self):
        """The drawn pixels become one frame-specific undo submission."""
        handler, editor = _make_handler()
        drag_info = _start_drag(handler)
        drag_info['pixels_drawn'].append({'position': (1, 2), 'color': RED, 'old_color': WHITE})
        drag_info['pixels_drawn'].append({'position': (2, 2), 'color': RED})

        handler.canvas.handle_controller_drag_end(CONTROLLER_ID)

        assert editor.canvas_operation_tracker.frame_changes == [
            ('idle', 0, [(1, 2, WHITE, RED), (2, 2, BLACK, RED)]),
        ]
        assert editor.canvas_operation_tracker.global_changes == []


class TestCollectDragPixelChanges:
    """Collecting a drag's pixels merges the pending A-press pixel into one undo step."""

    def test_pending_pixels_come_first_and_their_undo_entry_is_removed(self):
        """The A-press pixel is absorbed, cleared, and its separate undo entry popped."""
        handler, editor = _make_handler()
        earlier_operation = RecordedOperation(operation_type='fill', description='earlier')
        single_pixel_operation = RecordedOperation(operation_type='pixel', description='A press')
        editor.undo_redo_manager.undo_stack = [earlier_operation, single_pixel_operation]
        editor.current_pixel_changes = [(0, 0, WHITE, RED)]
        drag_info = {'pixels_drawn': [{'position': (1, 0), 'color': RED, 'old_color': WHITE}]}

        pixel_changes = handler.canvas._collect_drag_pixel_changes(CONTROLLER_ID, drag_info)

        assert pixel_changes == [(0, 0, WHITE, RED), (1, 0, WHITE, RED)]
        assert editor.current_pixel_changes == []
        assert editor.undo_redo_manager.undo_stack == [earlier_operation]

    def test_pending_pixels_with_an_empty_undo_stack(self):
        """Pending pixels are absorbed even when there is no undo entry to remove."""
        handler, editor = _make_handler()
        editor.current_pixel_changes = [(0, 0, WHITE, RED)]

        pixel_changes = handler.canvas._collect_drag_pixel_changes(
            CONTROLLER_ID,
            {'pixels_drawn': []},
        )

        assert pixel_changes == [(0, 0, WHITE, RED)]
        assert editor.undo_redo_manager.undo_stack == []

    def test_pending_pixels_without_an_undo_manager(self):
        """Without an undo manager the pending pixels are still absorbed."""
        handler, editor = _make_handler()
        editor.undo_redo_manager = None  # type: ignore[assignment]
        editor.current_pixel_changes = [(5, 5, WHITE, RED)]

        pixel_changes = handler.canvas._collect_drag_pixel_changes(
            CONTROLLER_ID,
            {'pixels_drawn': []},
        )

        assert pixel_changes == [(5, 5, WHITE, RED)]
        assert editor.current_pixel_changes == []

    def test_without_pending_pixels_the_undo_stack_is_kept(self):
        """With no pending pixel nothing is popped from the undo stack."""
        handler, editor = _make_handler()
        operation = RecordedOperation(operation_type='pixel', description='kept')
        editor.undo_redo_manager.undo_stack = [operation]

        pixel_changes = handler.canvas._collect_drag_pixel_changes(
            CONTROLLER_ID,
            {'pixels_drawn': [{'position': (1, 1), 'color': RED, 'old_color': WHITE}]},
        )

        assert pixel_changes == [(1, 1, WHITE, RED)]
        assert editor.undo_redo_manager.undo_stack == [operation]


class TestSubmitDragPixelChanges:
    """Submitting pixel changes picks frame-specific or global undo tracking."""

    def test_no_changes_submits_nothing(self):
        """An empty change list is not submitted."""
        handler, editor = _make_handler()

        handler.canvas._submit_drag_pixel_changes(CONTROLLER_ID, [])

        assert editor.canvas_operation_tracker.frame_changes == []
        assert editor.canvas_operation_tracker.global_changes == []

    def test_without_a_tracker_nothing_is_submitted(self):
        """An editor without an operation tracker is left alone."""
        handler, editor = _make_handler()
        tracker = editor.canvas_operation_tracker
        del editor.canvas_operation_tracker

        handler.canvas._submit_drag_pixel_changes(CONTROLLER_ID, [(0, 0, WHITE, RED)])

        assert tracker.frame_changes == []
        assert tracker.global_changes == []

    def test_a_canvas_without_frame_information_uses_global_tracking(self):
        """A canvas with no current frame falls back to global undo tracking."""
        canvas = InterfaceCanvas()
        canvas.current_frame = None
        handler, editor = _make_handler(canvas=canvas)

        handler.canvas._submit_drag_pixel_changes(CONTROLLER_ID, [(0, 0, WHITE, RED)])

        assert editor.canvas_operation_tracker.global_changes == [[(0, 0, WHITE, RED)]]
        assert editor.canvas_operation_tracker.frame_changes == []

    def test_no_canvas_uses_global_tracking(self):
        """Without a canvas there is no frame, so tracking is global."""
        handler, editor = _make_handler()
        editor.canvas = None

        handler.canvas._submit_drag_pixel_changes(CONTROLLER_ID, [(0, 0, WHITE, RED)])

        assert editor.canvas_operation_tracker.global_changes == [[(0, 0, WHITE, RED)]]


class TestCanvasPaintAtControllerPosition:
    """Painting at the controller's position."""

    def test_an_unregistered_controller_paints_nothing(self):
        """A controller without a canvas position paints nothing."""
        handler, editor = _make_handler(position=None)

        handler.canvas.canvas_paint_at_controller_position(CONTROLLER_ID)

        assert editor.canvas.canvas_interface.painted == {}

    def test_an_invalid_position_paints_nothing(self):
        """A position marked invalid paints nothing."""
        handler, editor = _make_handler()
        position = editor.mode_switcher.get_controller_position(CONTROLLER_ID)
        assert position is not None
        position.is_valid = False

        handler.canvas.canvas_paint_at_controller_position(CONTROLLER_ID)

        assert editor.canvas.canvas_interface.painted == {}

    def test_paints_and_tracks_the_old_color_in_the_drag(self):
        """The pixel is painted and the drag remembers its old color for undo."""
        handler, editor = _make_handler(position=(2, 3))
        drag_info = _start_drag(handler)

        handler.canvas.canvas_paint_at_controller_position(CONTROLLER_ID)

        assert editor.canvas.canvas_interface.painted == {(2, 3): RED}
        assert len(drag_info['pixels_drawn']) == 1
        assert drag_info['pixels_drawn'][0]['position'] == (2, 3)
        assert drag_info['pixels_drawn'][0]['color'] == RED
        assert drag_info['pixels_drawn'][0]['old_color'] == WHITE

    def test_a_pixel_already_in_the_color_is_not_repainted(self):
        """Debouncing: a pixel already in the current color is skipped."""
        handler, editor = _make_handler(position=(2, 3))
        editor.canvas.canvas_interface.painted[2, 3] = RED
        drag_info = _start_drag(handler)

        handler.canvas.canvas_paint_at_controller_position(CONTROLLER_ID)

        assert drag_info['pixels_drawn'] == []

    def test_force_repaints_a_pixel_already_in_the_color(self):
        """``force=True`` paints and tracks even a pixel already in the color."""
        handler, editor = _make_handler(position=(2, 3))
        editor.canvas.canvas_interface.painted[2, 3] = RED
        drag_info = _start_drag(handler)

        handler.canvas.canvas_paint_at_controller_position(CONTROLLER_ID, force=True)

        assert drag_info['pixels_drawn'][0]['old_color'] == RED

    def test_without_a_canvas_the_old_color_reads_as_black(self):
        """With no canvas nothing is painted, and the tracked old color defaults to black."""
        handler, editor = _make_handler()
        editor.canvas = None
        drag_info = _start_drag(handler)

        handler.canvas.canvas_paint_at_controller_position(CONTROLLER_ID)

        assert drag_info['pixels_drawn'][0]['old_color'] == BLACK

    def test_paints_a_pixel_list_canvas(self):
        """A canvas without an interface has its pixel list updated and marked dirty."""
        canvas = PixelListCanvas()
        handler, _editor = _make_handler(canvas=canvas, position=(1, 2))

        handler.canvas.canvas_paint_at_controller_position(CONTROLLER_ID)

        pixel_index = 2 * canvas.pixels_across + 1
        assert canvas.pixels[pixel_index] == RED
        assert canvas.dirty_pixels[pixel_index] is True
        assert canvas.dirty == 1


class TestCanvasPixelAccess:
    """Reading and writing single pixels through either canvas kind."""

    @pytest.mark.parametrize('error_type', [IndexError, AttributeError, TypeError])
    def test_an_interface_read_error_reads_as_black(self, error_type):
        """A canvas interface that fails to read gives black instead of raising."""
        canvas = InterfaceCanvas()
        canvas.canvas_interface = FakeCanvasInterface(error_on_read=error_type())
        handler, _editor = _make_handler(canvas=canvas)

        assert handler.canvas._get_canvas_pixel_color(0, 0) == BLACK

    def test_a_pixel_list_read_inside_and_outside_the_canvas(self):
        """A pixel list canvas gives the pixel inside its bounds and None outside."""
        canvas = PixelListCanvas()
        canvas.pixels[canvas.pixels_across + 2] = RED
        handler, _editor = _make_handler(canvas=canvas)

        assert handler.canvas._get_canvas_pixel_color(2, 1) == RED
        assert handler.canvas._get_canvas_pixel_color(canvas.pixels_across, 0) is None
        assert handler.canvas._get_canvas_pixel_color(0, -1) is None

    def test_a_pixel_list_write_outside_the_canvas_is_ignored(self):
        """Writing outside a pixel list canvas changes nothing."""
        canvas = PixelListCanvas()
        handler, _editor = _make_handler(canvas=canvas)

        handler.canvas._set_canvas_pixel(canvas.pixels_across, 0, RED)

        assert RED not in canvas.pixels
        assert canvas.dirty == 0


class TestTrackControllerDragPixel:
    """Only an active drag records painted pixels."""

    def test_an_inactive_drag_records_nothing(self):
        """A drag that is not active records no pixels."""
        handler, _editor = _make_handler()
        drag_info = _start_drag(handler, active=False)

        handler.canvas._track_controller_drag_pixel(CONTROLLER_ID, (0, 0), RED, WHITE)

        assert drag_info['pixels_drawn'] == []

    def test_without_a_drag_record_nothing_is_recorded(self):
        """A controller with no drag record does not get one."""
        handler, _editor = _make_handler()

        handler.canvas._track_controller_drag_pixel(CONTROLLER_ID, (0, 0), RED, WHITE)

        assert handler.controller_drags == {}


class TestCanvasEraseAtControllerPosition:
    """Erasing paints the background color (black)."""

    def test_erases_through_the_canvas_interface(self):
        """The pixel under the controller turns black."""
        handler, editor = _make_handler(position=(4, 5))
        editor.canvas.canvas_interface.painted[4, 5] = RED

        handler.canvas._canvas_erase_at_controller_position(CONTROLLER_ID)

        assert editor.canvas.canvas_interface.painted[4, 5] == BLACK

    def test_erases_a_pixel_list_canvas(self):
        """A pixel list canvas has the pixel set to black and marked dirty."""
        canvas = PixelListCanvas()
        handler, _editor = _make_handler(canvas=canvas, position=(3, 0))

        handler.canvas._canvas_erase_at_controller_position(CONTROLLER_ID)

        assert canvas.pixels[3] == BLACK
        assert canvas.dirty_pixels[3] is True
        assert canvas.dirty == 1

    def test_a_position_outside_a_pixel_list_canvas_erases_nothing(self):
        """A saved position beyond the pixel list leaves every pixel alone."""
        canvas = PixelListCanvas()
        handler, _editor = _make_handler(canvas=canvas, position=(canvas.pixels_across, 0))

        handler.canvas._canvas_erase_at_controller_position(CONTROLLER_ID)

        assert BLACK not in canvas.pixels
        assert canvas.dirty == 0

    def test_an_unregistered_controller_erases_nothing(self):
        """A controller without a canvas position erases nothing."""
        handler, editor = _make_handler(position=None)

        handler.canvas._canvas_erase_at_controller_position(CONTROLLER_ID)

        assert editor.canvas.canvas_interface.painted == {}

    def test_without_a_canvas_nothing_is_erased(self):
        """No canvas: the call returns without error."""
        handler, editor = _make_handler()
        editor.canvas = None

        handler.canvas._canvas_erase_at_controller_position(CONTROLLER_ID)

        assert editor.canvas is None


class TestCanvasMoveCursor:
    """Moving the canvas cursor clamps, records undo, and paints during a drag."""

    def test_moves_and_records_the_position_change(self):
        """A move updates the position and records it for undo with the mode."""
        handler, editor = _make_handler(position=(2, 2))

        handler.canvas._canvas_move_cursor(CONTROLLER_ID, 1, -1)

        assert _position_of(editor) == (3, 1)
        assert editor.controller_position_operation_tracker.position_changes == [
            (CONTROLLER_ID, (2, 2), (3, 1), 'canvas', 'canvas'),
        ]

    def test_clamps_to_the_canvas(self):
        """A move past the edge stops at the last pixel."""
        handler, editor = _make_handler(position=(7, 0))

        handler.canvas._canvas_move_cursor(CONTROLLER_ID, 5, -5)

        assert _position_of(editor) == (7, 0)
        assert editor.controller_position_operation_tracker.position_changes == []

    def test_clamps_to_the_pixel_count_not_the_screen_size(self):
        """An 8x8 canvas drawn at 16x clamps the cursor to pixel 7, not 127 (BUGS.md #97)."""
        canvas = InterfaceCanvas(pixels_across=8, pixels_tall=8, pixel_width=16)
        handler, editor = _make_handler(canvas=canvas, position=(6, 1))

        handler.canvas._canvas_move_cursor(CONTROLLER_ID, 50, 50)

        assert (canvas.width, canvas.height) == (128, 128)
        assert _position_of(editor) == (7, 7)

    def test_without_a_canvas_the_move_is_not_clamped(self):
        """No canvas: nothing to clamp against."""
        handler, editor = _make_handler(position=(2, 2))
        editor.canvas = None

        handler.canvas._canvas_move_cursor(CONTROLLER_ID, 40, 0)

        assert _position_of(editor) == (42, 2)

    def test_an_unregistered_controller_starts_at_the_origin(self):
        """A controller with no position is treated as at (0, 0) and records nothing."""
        handler, editor = _make_handler(position=None)

        handler.canvas._canvas_move_cursor(CONTROLLER_ID, 1, 1)

        assert editor.mode_switcher.get_controller_position(CONTROLLER_ID) is None
        assert editor.controller_position_operation_tracker.position_changes == []

    def test_no_undo_record_while_applying_undo(self):
        """A move made by undo/redo itself is not recorded again."""
        handler, editor = _make_handler(position=(2, 2))
        handler.applying_undo_redo = True  # type: ignore[attr-defined]

        handler.canvas._canvas_move_cursor(CONTROLLER_ID, 1, 0)

        assert _position_of(editor) == (3, 2)
        assert editor.controller_position_operation_tracker.position_changes == []

    def test_no_undo_record_during_continuous_movement(self):
        """Steps of a held D-pad are recorded once, when it is released, not here."""
        handler, editor = _make_handler(position=(2, 2))
        handler.canvas_continuous_movements[CONTROLLER_ID] = {}

        handler.canvas._canvas_move_cursor(CONTROLLER_ID, 1, 0)

        assert editor.controller_position_operation_tracker.position_changes == []

    def test_no_undo_record_during_slider_adjustment(self):
        """A controller adjusting a slider counts as in continuous movement too."""
        handler, editor = _make_handler(position=(2, 2))
        handler.slider_continuous_adjustments[CONTROLLER_ID] = {}

        handler.canvas._canvas_move_cursor(CONTROLLER_ID, 1, 0)

        assert editor.controller_position_operation_tracker.position_changes == []

    def test_without_a_position_tracker_the_move_still_happens(self):
        """An editor without a position tracker still moves the cursor."""
        handler, editor = _make_handler(position=(2, 2))
        del editor.controller_position_operation_tracker

        handler.canvas._canvas_move_cursor(CONTROLLER_ID, 0, 1)

        assert _position_of(editor) == (2, 3)

    def test_an_active_drag_paints_the_new_position(self):
        """Moving during a drag paints the pixel moved onto."""
        handler, editor = _make_handler(position=(2, 2))
        drag_info = _start_drag(handler)

        handler.canvas._canvas_move_cursor(CONTROLLER_ID, 1, 0)

        assert editor.canvas.canvas_interface.painted == {(3, 2): RED}
        assert [pixel['position'] for pixel in drag_info['pixels_drawn']] == [(3, 2)]

    def test_an_inactive_drag_does_not_paint(self):
        """Moving after a drag ended paints nothing."""
        handler, editor = _make_handler(position=(2, 2))
        _start_drag(handler, active=False)

        handler.canvas._canvas_move_cursor(CONTROLLER_ID, 1, 0)

        assert editor.canvas.canvas_interface.painted == {}


class TestContinuousCanvasMovement:
    """Holding the D-pad moves the cursor with acceleration."""

    def test_start_moves_once_and_records_the_movement(self):
        """Starting moves immediately and remembers where the movement began."""
        handler, editor = _make_handler(position=(2, 2))

        handler.canvas.start_canvas_continuous_movement(CONTROLLER_ID, 1, 0)

        assert _position_of(editor) == (3, 2)
        movement_data = handler.canvas_continuous_movements[CONTROLLER_ID]
        assert (movement_data['dx'], movement_data['dy']) == (1, 0)
        assert (movement_data['start_x'], movement_data['start_y']) == (3, 2)
        assert movement_data['acceleration_level'] == 0

    def test_start_for_an_unregistered_controller_begins_at_the_origin(self):
        """A controller without a position starts its movement at (0, 0)."""
        handler, _editor = _make_handler(position=None)

        handler.canvas.start_canvas_continuous_movement(CONTROLLER_ID, 0, 1)

        movement_data = handler.canvas_continuous_movements[CONTROLLER_ID]
        assert (movement_data['start_x'], movement_data['start_y']) == (0, 0)

    def test_stop_records_one_undo_step_for_the_whole_movement(self):
        """Stopping records the move from the start to the final position."""
        handler, editor = _make_handler(position=(2, 2))
        handler.canvas_continuous_movements[CONTROLLER_ID] = {'start_x': 0, 'start_y': 2}

        handler.canvas.stop_canvas_continuous_movement(CONTROLLER_ID)

        assert CONTROLLER_ID not in handler.canvas_continuous_movements
        assert editor.controller_position_operation_tracker.position_changes == [
            (CONTROLLER_ID, (0, 2), (2, 2), 'canvas', 'canvas'),
        ]

    def test_stop_without_a_change_records_nothing(self):
        """A movement that ended where it started records no undo step."""
        handler, editor = _make_handler(position=(2, 2))
        handler.canvas_continuous_movements[CONTROLLER_ID] = {'start_x': 2, 'start_y': 2}

        handler.canvas.stop_canvas_continuous_movement(CONTROLLER_ID)

        assert CONTROLLER_ID not in handler.canvas_continuous_movements
        assert editor.controller_position_operation_tracker.position_changes == []

    def test_stop_for_an_unregistered_controller_records_the_origin(self):
        """A controller whose position is gone counts as ending at (0, 0)."""
        handler, editor = _make_handler(position=None)
        handler.canvas_continuous_movements[CONTROLLER_ID] = {'start_x': 3, 'start_y': 3}

        handler.canvas.stop_canvas_continuous_movement(CONTROLLER_ID)

        assert editor.controller_position_operation_tracker.position_changes == [
            (CONTROLLER_ID, (3, 3), (0, 0), None, None),
        ]

    def test_stop_without_a_position_tracker_still_stops(self):
        """An editor without a position tracker still ends the movement."""
        handler, editor = _make_handler(position=(2, 2))
        del editor.controller_position_operation_tracker
        handler.canvas_continuous_movements[CONTROLLER_ID] = {'start_x': 0, 'start_y': 0}

        handler.canvas.stop_canvas_continuous_movement(CONTROLLER_ID)

        assert CONTROLLER_ID not in handler.canvas_continuous_movements

    def test_stop_without_a_movement_does_nothing(self):
        """Stopping a controller that is not moving records nothing."""
        handler, editor = _make_handler(position=(2, 2))

        handler.canvas.stop_canvas_continuous_movement(CONTROLLER_ID)

        assert editor.controller_position_operation_tracker.position_changes == []

    def test_update_without_movement_state_does_nothing(self):
        """A handler without the movement table is left alone."""
        handler, editor = _make_handler(position=(2, 2))
        del handler.canvas_continuous_movements

        handler.canvas.update_canvas_continuous_movements()

        assert _position_of(editor) == (2, 2)

    def test_update_waits_for_the_interval(self):
        """Before the first interval (0.15 s at level 0) the cursor does not move."""
        handler, editor = _make_handler(position=(2, 2))
        handler.canvas.start_canvas_continuous_movement(CONTROLLER_ID, 1, 0)
        advance_frame_clock(seconds=0.1)

        handler.canvas.update_canvas_continuous_movements()

        assert _position_of(editor) == (3, 2)

    @pytest.mark.parametrize(
        ('held_seconds', 'expected_level', 'expected_step'),
        [(0.2, 0, 1), (1.0, 1, 2), (2.0, 2, 4), (3.0, 3, 8)],
    )
    def test_update_accelerates_the_longer_the_dpad_is_held(
        self,
        held_seconds,
        expected_level,
        expected_step,
    ):
        """Each acceleration level doubles the step, capped at 8 pixels."""
        canvas = InterfaceCanvas(pixels_across=64, pixels_tall=64)
        handler, editor = _make_handler(canvas=canvas, position=(10, 10))
        handler.canvas.start_canvas_continuous_movement(CONTROLLER_ID, 1, 0)
        advance_frame_clock(seconds=held_seconds)

        handler.canvas.update_canvas_continuous_movements()

        movement_data = handler.canvas_continuous_movements[CONTROLLER_ID]
        assert movement_data['acceleration_level'] == expected_level
        assert _position_of(editor) == (11 + expected_step, 10)

    def test_update_paints_during_a_drag(self):
        """A held D-pad with an active drag paints the pixels moved onto."""
        handler, editor = _make_handler(position=(2, 2))
        handler.canvas.start_canvas_continuous_movement(CONTROLLER_ID, 0, 1)
        drag_info = _start_drag(handler)
        advance_frame_clock(seconds=0.2)

        handler.canvas.update_canvas_continuous_movements()

        assert _position_of(editor) == (2, 4)
        assert editor.canvas.canvas_interface.painted == {(2, 4): RED}
        assert [pixel['position'] for pixel in drag_info['pixels_drawn']] == [(2, 4)]


class TestCanvasPaintLines:
    """Shoulder + A paints an 8-pixel line and moves the cursor past it."""

    def test_horizontal_line_to_the_right(self):
        """A positive distance paints rightwards and ends one past the line."""
        canvas = InterfaceCanvas(pixels_across=16, pixels_tall=16)
        handler, editor = _make_handler(canvas=canvas, position=(2, 3))
        drag_info = _start_drag(handler)

        handler.canvas.canvas_paint_horizontal_line(CONTROLLER_ID, 4)

        assert sorted(canvas.canvas_interface.painted) == [(2, 3), (3, 3), (4, 3), (5, 3)]
        assert len(drag_info['pixels_drawn']) == 4
        assert canvas.redraw_count == 1
        assert _position_of(editor) == (6, 3)

    def test_horizontal_line_to_the_left_is_clamped(self):
        """A line past the left edge repaints the edge pixel and stops at column 0."""
        canvas = InterfaceCanvas(pixels_across=16, pixels_tall=16)
        handler, editor = _make_handler(canvas=canvas, position=(1, 3))

        handler.canvas.canvas_paint_horizontal_line(CONTROLLER_ID, -4)

        assert sorted(canvas.canvas_interface.painted) == [(0, 3), (1, 3)]
        assert _position_of(editor) == (0, 3)

    def test_vertical_line_down(self):
        """A positive distance paints downwards and ends one past the line."""
        canvas = InterfaceCanvas(pixels_across=16, pixels_tall=16)
        handler, editor = _make_handler(canvas=canvas, position=(2, 3))

        handler.canvas.canvas_paint_vertical_line(CONTROLLER_ID, 3)

        assert sorted(canvas.canvas_interface.painted) == [(2, 3), (2, 4), (2, 5)]
        assert canvas.redraw_count == 1
        assert _position_of(editor) == (2, 6)

    def test_vertical_line_up_is_clamped(self):
        """A line past the top edge stops at row 0."""
        canvas = InterfaceCanvas(pixels_across=16, pixels_tall=16)
        handler, editor = _make_handler(canvas=canvas, position=(2, 1))

        handler.canvas.canvas_paint_vertical_line(CONTROLLER_ID, -8)

        assert sorted(canvas.canvas_interface.painted) == [(2, 0), (2, 1)]
        assert _position_of(editor) == (2, 0)

    def test_lines_clamp_at_the_far_edges(self):
        """Lines past the right and bottom edges stop at the last pixel."""
        canvas = InterfaceCanvas(pixels_across=4, pixels_tall=4)
        handler, editor = _make_handler(canvas=canvas, position=(2, 2))

        handler.canvas.canvas_paint_horizontal_line(CONTROLLER_ID, 8)
        assert _position_of(editor) == (3, 2)

        handler.canvas.canvas_paint_vertical_line(CONTROLLER_ID, 8)
        assert _position_of(editor) == (3, 3)
        assert sorted(canvas.canvas_interface.painted) == [(2, 2), (3, 2), (3, 3)]

    @pytest.mark.parametrize(
        'line_method', ['canvas_paint_horizontal_line', 'canvas_paint_vertical_line']
    )
    def test_an_unregistered_controller_paints_no_line(self, line_method):
        """A controller without a canvas position paints nothing."""
        handler, editor = _make_handler(position=None)

        getattr(handler.canvas, line_method)(CONTROLLER_ID, 8)

        assert editor.canvas.canvas_interface.painted == {}
        assert editor.canvas.redraw_count == 0

    @pytest.mark.parametrize(
        ('line_method', 'expected_position'),
        [('canvas_paint_horizontal_line', (5, 2)), ('canvas_paint_vertical_line', (2, 5))],
    )
    def test_without_a_canvas_only_the_cursor_moves(self, line_method, expected_position):
        """No canvas: nothing is painted or tracked, and the cursor moves unclamped."""
        handler, editor = _make_handler(position=(2, 2))
        editor.canvas = None
        drag_info = _start_drag(handler)

        getattr(handler.canvas, line_method)(CONTROLLER_ID, 3)

        assert drag_info['pixels_drawn'] == []
        assert _position_of(editor) == expected_position


class TestCanvasJumps:
    """Shoulder buttons alone jump 8 pixels without painting."""

    def test_horizontal_jump_is_clamped(self):
        """A jump past the right edge lands on the last column."""
        handler, editor = _make_handler(position=(2, 2))

        handler.canvas.canvas_jump_horizontal(CONTROLLER_ID, 8)

        assert _position_of(editor) == (7, 2)
        assert editor.canvas.canvas_interface.painted == {}

    def test_vertical_jump_is_clamped(self):
        """A jump past the top edge lands on row 0."""
        handler, editor = _make_handler(position=(2, 2))

        handler.canvas.canvas_jump_vertical(CONTROLLER_ID, -8)

        assert _position_of(editor) == (2, 0)

    @pytest.mark.parametrize(
        ('jump_method', 'expected_position'),
        [('canvas_jump_horizontal', (10, 2)), ('canvas_jump_vertical', (2, 10))],
    )
    def test_without_a_canvas_jumps_are_not_clamped(self, jump_method, expected_position):
        """No canvas: nothing to clamp against."""
        handler, editor = _make_handler(position=(2, 2))
        editor.canvas = None

        getattr(handler.canvas, jump_method)(CONTROLLER_ID, 8)

        assert _position_of(editor) == expected_position

    @pytest.mark.parametrize('jump_method', ['canvas_jump_horizontal', 'canvas_jump_vertical'])
    def test_an_invalid_position_does_not_jump(self, jump_method):
        """A position marked invalid stays where it is."""
        handler, editor = _make_handler(position=(2, 2))
        position = editor.mode_switcher.get_controller_position(CONTROLLER_ID)
        assert position is not None
        position.is_valid = False

        getattr(handler.canvas, jump_method)(CONTROLLER_ID, 8)

        assert position.position == (2, 2)


class TestControllerPaintColorInTheRealEditor:
    """Controller painting uses the same RGBA color as mouse painting, in the real editor."""

    @staticmethod
    def _editor_with_half_transparent_red():
        """Build a real editor whose sliders pick (255, 0, 0, 128), with a canvas controller.

        Returns:
            The editor, with controller CONTROLLER_ID in canvas mode at (2, 2).

        """
        from glitchygames import events
        from glitchygames.bitmappy.editor import BitmapEditorScene

        editor = BitmapEditorScene(options={})
        for channel_name, channel_value in (('R', 255), ('G', 0), ('B', 0), ('A', 128)):
            editor.on_slider_event(
                event=events.HashableEvent(0),
                trigger=events.HashableEvent(0, name=channel_name, value=channel_value),
            )
        editor.mode_switcher.register_controller(CONTROLLER_ID, ControllerMode.CANVAS)
        editor.mode_switcher.save_controller_position(CONTROLLER_ID, (2, 2))
        return editor

    def test_controller_paints_the_alpha_the_mouse_paints(self):
        """A controller-painted pixel carries the alpha slider's value, like canvas.active_color.

        The controller used to paint the RGB slider values only, so its pixels were opaque.
        """
        editor = self._editor_with_half_transparent_red()

        editor.controller_handler.canvas_paint_at_controller_position(CONTROLLER_ID)

        assert editor.canvas.active_color == (255, 0, 0, 128)
        assert editor.canvas.canvas_interface.get_pixel_at(2, 2) == (255, 0, 0, 128)

    def test_controller_lines_paint_the_alpha_too(self):
        """Horizontal and vertical controller lines paint the RGBA color as well."""
        editor = self._editor_with_half_transparent_red()
        _start_drag(editor.controller_handler)

        editor.controller_handler.canvas.canvas_paint_horizontal_line(CONTROLLER_ID, 2)
        editor.controller_handler.canvas.canvas_paint_vertical_line(CONTROLLER_ID, 2)

        # The horizontal line paints (2, 2) and (3, 2) and leaves the cursor at (4, 2), where
        # the vertical line paints (4, 2) and (4, 3)
        canvas_interface = editor.canvas.canvas_interface
        for painted_position in ((2, 2), (3, 2), (4, 2), (4, 3)):
            assert canvas_interface.get_pixel_at(*painted_position) == (255, 0, 0, 128)

    def test_painting_a_pixel_already_that_color_is_skipped(self):
        """A second paint of the same pixel records nothing more for undo.

        The debounce compared the RGBA pixel with the RGB slider color, so it never matched
        and every repeat paint was tracked again.
        """
        editor = self._editor_with_half_transparent_red()
        drag_info = _start_drag(editor.controller_handler)

        editor.controller_handler.canvas_paint_at_controller_position(CONTROLLER_ID)
        editor.controller_handler.canvas_paint_at_controller_position(CONTROLLER_ID)

        assert len(drag_info['pixels_drawn']) == 1
