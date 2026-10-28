"""Tests for FrameOperationManager in src/apps/bitmappy/src/bitmappy/frame_operations.py.

The manager runs against a small stand-in editor holding a real AnimatedSprite and a real
UndoRedoManager, so the tests check what copy/paste and pixel-change submission do to the
frames and the undo history. Panning is tested in the real editor (test_bitmappy_canvas_panning.py).
"""

import pygame
import pytest

from bitmappy.constants import PIXEL_CHANGE_DEBOUNCE_SECONDS
from bitmappy.frame_operations import FrameOperationManager
from bitmappy.history.undo_redo import UndoRedoManager
from glitchygames import sources
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

FRAME_WIDTH = 2
FRAME_HEIGHT = 2
PIXEL_COUNT = FRAME_WIDTH * FRAME_HEIGHT
RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)


def _make_frame(color, duration=0.5, width=FRAME_WIDTH, height=FRAME_HEIGHT):
    """Build a SpriteFrame filled with one color.

    Returns:
        SpriteFrame: The frame, with its pixel data set.

    """
    frame = SpriteFrame(surface=pygame.Surface((width, height), pygame.SRCALPHA), duration=duration)
    frame.set_pixel_data([color] * (width * height))
    return frame


class _Canvas:
    """Canvas stand-in with the state FrameOperationManager reads."""

    def __init__(self, animated_sprite):
        self.animated_sprite = animated_sprite
        self.pixels_across = FRAME_WIDTH
        self.pixels_tall = FRAME_HEIGHT
        self.pixels = [GREEN] * PIXEL_COUNT
        self.current_animation = 'idle'
        self.current_frame = 0
        self.redraw_count = 0


class _RedrawingCanvas(_Canvas):
    """Canvas stand-in that also counts forced redraws."""

    def force_redraw(self):
        """Count redraws."""
        self.redraw_count += 1


class _OperationTracker:
    """Canvas operation tracker stand-in recording what is submitted (the undo boundary)."""

    def __init__(self):
        self.frame_submissions = []
        self.global_submissions = []

    def add_frame_pixel_changes(self, animation, frame, pixels):
        """Record a frame-specific submission."""
        self.frame_submissions.append((animation, frame, list(pixels)))

    def add_pixel_changes(self, pixels):
        """Record a global submission."""
        self.global_submissions.append(list(pixels))


class _Editor:
    """Editor stand-in with the attributes FrameOperationManager reads."""

    def __init__(self, animated_sprite):
        self.applying_undo_redo = False
        self.canvas = _RedrawingCanvas(animated_sprite)
        self.selected_animation = 'idle'
        self.selected_frame = 0
        self.undo_redo_manager = UndoRedoManager(max_history=10)
        self.canvas_operation_tracker = _OperationTracker()
        self.current_pixel_changes = []
        self.current_pixel_changes_dict = {}
        self.pixel_change_timer = None


@pytest.fixture
def animated_sprite():
    """Build a sprite with an 'idle' animation of two frames (red, blue).

    Returns:
        AnimatedSprite: The sprite.

    """
    sprite = AnimatedSprite()
    sprite.add_animation('idle', [_make_frame(RED), _make_frame(BLUE, duration=1.5)])
    return sprite


@pytest.fixture
def editor(animated_sprite):
    """Build a stand-in editor around the sprite.

    Returns:
        _Editor: The editor.

    """
    return _Editor(animated_sprite)


@pytest.fixture
def manager(editor):
    """Build the manager under test.

    Returns:
        FrameOperationManager: The manager.

    """
    return FrameOperationManager(editor)


class TestCopyPasteFrame:
    """Test copying a frame to the clipboard and pasting it into another frame."""

    def test_copy_then_paste_replaces_frame_and_undo_restores_it(self, editor, manager):
        """Pasting a copied frame replaces pixels and duration; undo brings the old ones back."""
        editor.selected_frame = 1
        manager.handle_copy_frame()
        editor.selected_frame = 0

        manager.handle_paste_frame()

        target_frame = editor.canvas.animated_sprite._animations['idle'][0]
        assert target_frame.get_pixel_data() == [BLUE] * PIXEL_COUNT
        assert target_frame.duration == pytest.approx(1.5)
        assert editor.canvas.redraw_count == 1

        assert editor.undo_redo_manager.undo() is True
        assert target_frame.get_pixel_data() == [RED] * PIXEL_COUNT
        assert target_frame.duration == pytest.approx(0.5)

    def test_copy_with_nothing_selected_keeps_clipboard_empty(self, editor, manager):
        """Copying with no selected animation leaves the clipboard empty."""
        editor.selected_animation = None

        manager.handle_copy_frame()

        assert manager._frame_clipboard is None

    def test_copy_without_canvas_or_selection_keeps_clipboard_empty(self, editor, manager):
        """Copying with no canvas, or no selection attributes, leaves the clipboard empty."""
        animated_canvas = editor.canvas
        editor.canvas = None
        manager.handle_copy_frame()
        editor.canvas = animated_canvas
        del editor.selected_animation
        manager.handle_copy_frame()

        assert manager._frame_clipboard is None

    def test_paste_with_empty_clipboard_changes_nothing(self, editor, manager):
        """Pasting before anything was copied pushes no command."""
        manager.handle_paste_frame()

        assert editor.undo_redo_manager.undo_stack == []

    def test_copy_without_animated_sprite_keeps_clipboard_empty(self, editor, manager):
        """Copying from a canvas with no animated sprite leaves the clipboard empty."""
        editor.canvas.animated_sprite = None

        manager.handle_copy_frame()

        assert manager._frame_clipboard is None

    def test_copy_of_unknown_animation_or_frame_keeps_clipboard_empty(self, editor, manager):
        """Copying a missing animation or frame index leaves the clipboard empty."""
        editor.selected_animation = 'missing'
        manager.handle_copy_frame()
        editor.selected_animation = 'idle'
        editor.selected_frame = 4
        manager.handle_copy_frame()

        assert manager._frame_clipboard is None

    def test_paste_without_selection_attributes_changes_nothing(self, editor, manager):
        """An editor with no frame selection cannot paste."""
        manager.handle_copy_frame()
        del editor.selected_frame

        manager.handle_paste_frame()

        assert editor.undo_redo_manager.undo_stack == []

    def test_paste_without_canvas_changes_nothing(self, editor, manager):
        """Without a canvas nothing is pasted."""
        manager.handle_copy_frame()
        editor.canvas = None

        manager.handle_paste_frame()

        assert editor.undo_redo_manager.undo_stack == []

    @pytest.mark.parametrize(
        ('selected_animation', 'selected_frame'),
        [(None, 0), ('idle', None), ('missing', 0), ('idle', 7)],
    )
    def test_paste_to_missing_target_changes_nothing(
        self, editor, manager, selected_animation, selected_frame
    ):
        """A paste with no selection, an unknown animation or frame pushes no command."""
        manager.handle_copy_frame()
        editor.selected_animation = selected_animation
        editor.selected_frame = selected_frame

        manager.handle_paste_frame()

        assert editor.undo_redo_manager.undo_stack == []
        assert editor.canvas.animated_sprite._animations['idle'][0].pixels == [RED] * PIXEL_COUNT

    def test_paste_without_animated_sprite_changes_nothing(self, editor, manager):
        """A canvas with no animated sprite cannot be pasted into."""
        manager.handle_copy_frame()
        editor.canvas.animated_sprite = None

        manager.handle_paste_frame()

        assert editor.undo_redo_manager.undo_stack == []

    def test_paste_into_different_size_frame_is_refused(self, editor, manager):
        """A frame of a different size is not pasted into."""
        manager.handle_copy_frame()
        editor.canvas.animated_sprite._animations['idle'].append(
            _make_frame(GREEN, width=3, height=3),
        )
        editor.selected_frame = 2

        manager.handle_paste_frame()

        assert editor.undo_redo_manager.undo_stack == []

    def test_paste_into_canvas_without_redraw(self, editor, manager):
        """A canvas without force_redraw still gets the paste."""
        manager.handle_copy_frame()
        editor.selected_frame = 1
        editor.canvas = _Canvas(editor.canvas.animated_sprite)

        manager.handle_paste_frame()

        assert (
            editor.canvas.animated_sprite._animations['idle'][1].get_pixel_data()
            == [RED] * PIXEL_COUNT
        )


class TestSubmitPixelChanges:
    """Test submitting collected pixel changes to the undo tracker."""

    def test_dict_changes_go_to_the_current_frame(self, editor, manager):
        """Collected changes are submitted for the canvas's frame and then cleared."""
        change = (0, 0, RED, GREEN)
        editor.current_pixel_changes_dict = {(0, 0): change}
        editor.current_pixel_changes = [change]

        manager.submit_pixel_changes_if_ready()

        assert editor.canvas_operation_tracker.frame_submissions == [('idle', 0, [change])]
        assert editor.current_pixel_changes_dict == {}
        assert editor.current_pixel_changes == []

    def test_list_changes_without_frame_go_to_global_tracking(self, editor, manager):
        """Without a current frame, list changes go to the global history."""
        change = (1, 1, RED, BLUE)
        editor.current_pixel_changes = [change]
        editor.canvas = None

        manager.submit_pixel_changes_if_ready()

        assert editor.canvas_operation_tracker.global_submissions == [[change]]
        assert editor.current_pixel_changes == []

    def test_list_changes_without_dict_are_submitted(self, editor, manager):
        """An editor with only the list collection still submits and clears it."""
        change = (1, 0, RED, BLUE)
        del editor.current_pixel_changes_dict
        editor.current_pixel_changes = [change]

        manager.submit_pixel_changes_if_ready()

        assert editor.canvas_operation_tracker.frame_submissions == [('idle', 0, [change])]
        assert editor.current_pixel_changes == []

    def test_dict_changes_without_list_are_submitted(self, editor, manager):
        """An editor with only the dict collection still submits and clears it."""
        change = (0, 1, RED, BLUE)
        del editor.current_pixel_changes
        editor.current_pixel_changes_dict = {(0, 1): change}

        manager.submit_pixel_changes_if_ready()

        assert editor.canvas_operation_tracker.frame_submissions == [('idle', 0, [change])]

    def test_nothing_collected_submits_nothing(self, editor, manager):
        """With no collected changes nothing is submitted."""
        manager.submit_pixel_changes_if_ready()

        assert editor.canvas_operation_tracker.frame_submissions == []
        assert editor.canvas_operation_tracker.global_submissions == []


class TestCheckSingleClickTimer:
    """Test the single-click debounce timer."""

    def test_single_pixel_is_submitted_after_debounce(self, editor, manager):
        """A single changed pixel is submitted once the debounce time has passed."""
        change = (0, 0, RED, GREEN)
        editor.current_pixel_changes_dict = {(0, 0): change}
        editor.pixel_change_timer = 0.0
        sources.advance_frame_clock(seconds=PIXEL_CHANGE_DEBOUNCE_SECONDS * 2)

        manager.check_single_click_timer()

        assert editor.canvas_operation_tracker.frame_submissions == [('idle', 0, [change])]
        assert editor.pixel_change_timer is None

    def test_single_pixel_waits_during_debounce(self, editor, manager):
        """A single pixel inside the debounce window is not submitted yet."""
        editor.current_pixel_changes = [(0, 0, RED, GREEN)]
        editor.pixel_change_timer = 0.0

        manager.check_single_click_timer()

        assert editor.canvas_operation_tracker.frame_submissions == []
        assert editor.pixel_change_timer == pytest.approx(0.0)

    def test_several_pixels_are_left_for_the_drag(self, editor, manager):
        """More than one pixel is a drag, which the timer does not submit."""
        editor.current_pixel_changes_dict = {
            (0, 0): (0, 0, RED, GREEN),
            (1, 0): (1, 0, RED, GREEN),
        }
        editor.pixel_change_timer = 0.0
        sources.advance_frame_clock(seconds=PIXEL_CHANGE_DEBOUNCE_SECONDS * 2)

        manager.check_single_click_timer()

        assert editor.canvas_operation_tracker.frame_submissions == []

    def test_no_changes_submit_nothing(self, editor, manager):
        """With nothing collected the timer does nothing."""
        editor.pixel_change_timer = 0.0
        sources.advance_frame_clock(seconds=PIXEL_CHANGE_DEBOUNCE_SECONDS * 2)

        manager.check_single_click_timer()

        assert editor.canvas_operation_tracker.frame_submissions == []
        assert editor.pixel_change_timer == pytest.approx(0.0)
