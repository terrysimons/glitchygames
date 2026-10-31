"""Tests for Bitmappy's undo/redo command classes.

The classes are in src/apps/bitmappy/src/bitmappy/history/commands.py.

Each command runs against a small stand-in editor holding a real AnimatedSprite, so the
tests check what execute and undo do to the frames, pixels and controller state.
"""

import pygame
import pytest

from bitmappy.controllers.modes import ControllerMode, ModeSwitcher
from bitmappy.history.commands import (
    AnimationAddCommand,
    AnimationDeleteCommand,
    AnimationRenameCommand,
    BrushStrokeCommand,
    ControllerModeCommand,
    ControllerPositionCommand,
    FloodFillCommand,
    FrameAddCommand,
    FrameCopyCommand,
    FrameDeleteCommand,
    FramePasteCommand,
    FrameReorderCommand,
    FrameSelectionCommand,
)
from bitmappy.history.undo_redo import OperationType
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

FRAME_WIDTH = 2
FRAME_HEIGHT = 2
RED = (255, 0, 0, 255)
GREEN = (0, 255, 0, 255)
BLUE = (0, 0, 255, 255)


def _make_frame(color, duration=0.5):
    """Build a 2x2 SpriteFrame filled with one color.

    Returns:
        SpriteFrame: The frame, with its pixel data set.

    """
    frame = SpriteFrame(
        surface=pygame.Surface((FRAME_WIDTH, FRAME_HEIGHT), pygame.SRCALPHA),
        duration=duration,
    )
    frame.set_pixel_data([color] * (FRAME_WIDTH * FRAME_HEIGHT))
    return frame


class _CanvasInterface:
    """Records each pixel the commands set, optionally failing every write."""

    def __init__(self):
        self.pixels = {}
        self.error_to_raise = None

    def set_pixel_at(self, x, y, color):
        """Store the pixel, or raise the configured error."""
        if self.error_to_raise is not None:
            raise self.error_to_raise
        self.pixels[x, y] = color


class _Canvas:
    """Canvas stand-in holding a real AnimatedSprite."""

    def __init__(self, animated_sprite):
        self.animated_sprite = animated_sprite
        self.canvas_interface = _CanvasInterface()
        self.pixels = [RED] * (FRAME_WIDTH * FRAME_HEIGHT)
        self.dirty_pixels = [False] * (FRAME_WIDTH * FRAME_HEIGHT)
        self.dirty = 0
        self.shown_frames = []

    def show_frame(self, animation, frame):
        """Record the shown frame and select it in the sprite's frame manager."""
        self.shown_frames.append((animation, frame))
        self.animated_sprite.frame_manager.current_animation = animation
        self.animated_sprite.frame_manager.current_frame = frame


class _FilmStripCoordinator:
    """Coordinator stand-in recording the notifications commands send."""

    def __init__(self, animated_sprite):
        self.animated_sprite = animated_sprite
        self.notifications = []

    def refresh_all_film_strip_widgets(self, animation_name):
        """Record a refresh."""
        self.notifications.append(('refresh', animation_name))

    def on_frame_inserted(self, animation_name, frame_index):
        """Record an insertion."""
        self.notifications.append(('inserted', animation_name, frame_index))

    def on_frame_removed(self, animation_name, frame_index):
        """Record a removal."""
        self.notifications.append(('removed', animation_name, frame_index))

    def on_sprite_loaded(self, animated_sprite):
        """Record a sprite reload."""
        self.notifications.append(('sprite_loaded', animated_sprite))

    def on_animation_rename(self, old_name, new_name):
        """Rename the animation in the sprite, as the real coordinator does."""
        self.animated_sprite.rename_animation(old_name=old_name, new_name=new_name)


class _FilmStripWidget:
    """Film strip widget stand-in recording its refresh calls.

    FilmStripWidget.refresh itself is tested on a real widget in test_bitmappy_film_strip_layout.py
    (TestRefresh).
    """

    def __init__(self):
        self.refresh_count = 0

    def refresh(self):
        """Record a refresh."""
        self.refresh_count += 1


class _FilmStripSprite:
    """Film strip sprite stand-in holding a widget."""

    def __init__(self, film_strip_widget):
        self.film_strip_widget = film_strip_widget
        self.dirty = 0


class _ControllerHandler:
    """Controller handler stand-in recording indicator updates."""

    def __init__(self):
        self.canvas_indicator_updates = []
        self.mode_indicator_updates = []

    def update_controller_canvas_visual_indicator(self, controller_id):
        """Record a canvas indicator update."""
        self.canvas_indicator_updates.append(controller_id)

    def update_controller_visual_indicator_for_mode(self, controller_id, controller_mode):
        """Record a mode indicator update."""
        self.mode_indicator_updates.append((controller_id, controller_mode))


class _Editor:
    """Editor stand-in with the attributes the commands read."""

    def __init__(self, animated_sprite):
        self.applying_undo_redo = False
        self.canvas = _Canvas(animated_sprite)
        self.film_strip_coordinator = _FilmStripCoordinator(animated_sprite)
        self.selected_animation = 'idle'
        self.selected_frame = 0


@pytest.fixture
def animated_sprite():
    """Build a sprite with an 'idle' animation of three frames (red, green, blue).

    Returns:
        AnimatedSprite: The sprite, showing idle[0].

    """
    sprite = AnimatedSprite()
    sprite.add_animation('idle', [_make_frame(RED), _make_frame(GREEN), _make_frame(BLUE)])
    sprite.frame_manager.current_animation = 'idle'
    sprite.frame_manager.current_frame = 0
    return sprite


@pytest.fixture
def editor(animated_sprite):
    """Build a stand-in editor around the sprite.

    Returns:
        _Editor: The editor.

    """
    return _Editor(animated_sprite)


def _first_pixel_colors(sprite, animation_name):
    """Return the first pixel's color of each frame in an animation.

    Returns:
        list[tuple[int, ...]]: One color per frame.

    """
    return [frame.get_pixel_data()[0] for frame in sprite.animation_data[animation_name]]


class TestBrushStrokeCommand:
    """Test the brush-stroke command."""

    def test_description_names_single_pixel_and_stroke(self, editor):
        """A one-pixel stroke names the pixel; a longer one counts its pixels."""
        single_pixel = BrushStrokeCommand(
            editor=editor,
            pixels=[(1, 0, RED, GREEN)],
            operation_type=OperationType.CANVAS_PIXEL_CHANGE,
        )
        stroke = BrushStrokeCommand(
            editor=editor,
            pixels=[(0, 0, RED, GREEN), (1, 0, RED, GREEN)],
            operation_type=OperationType.CANVAS_PIXEL_CHANGE,
        )

        assert single_pixel.description == 'Pixel change at (1, 0)'
        assert stroke.description == 'Brush stroke (2 pixels)'

    def test_execute_sets_new_colors_and_undo_restores_old(self, editor):
        """Execute paints the new colors; undo paints the old ones back."""
        command = BrushStrokeCommand(
            editor=editor,
            pixels=[(0, 0, RED, GREEN), (1, 1, BLUE, GREEN)],
            operation_type=OperationType.CANVAS_PIXEL_CHANGE,
        )

        assert command.execute() is True
        assert editor.canvas.canvas_interface.pixels == {(0, 0): GREEN, (1, 1): GREEN}
        assert command.undo() is True
        assert editor.canvas.canvas_interface.pixels == {(0, 0): RED, (1, 1): BLUE}
        assert editor.applying_undo_redo is False

    def test_undo_without_canvas_fails(self, editor):
        """Without a canvas nothing can be painted, so undo reports failure."""
        command = BrushStrokeCommand(
            editor=editor,
            pixels=[(0, 0, RED, GREEN)],
            operation_type=OperationType.CANVAS_PIXEL_CHANGE,
        )
        editor.canvas = None

        assert command.undo() is False
        assert command.execute() is False

    def test_failing_pixel_write_fails_the_command(self, editor):
        """A pixel write that raises makes the command report failure, not raise."""
        command = BrushStrokeCommand(
            editor=editor,
            pixels=[(0, 0, RED, GREEN)],
            operation_type=OperationType.CANVAS_PIXEL_CHANGE,
        )
        editor.canvas.canvas_interface.error_to_raise = IndexError('outside the canvas')

        assert command.execute() is False
        assert editor.applying_undo_redo is False


class TestFloodFillCommand:
    """Test the flood-fill command."""

    def test_execute_fills_and_undo_restores(self, editor):
        """Execute fills every affected pixel; undo puts the old color back."""
        command = FloodFillCommand(
            editor,
            start_x=0,
            start_y=0,
            old_color=RED,
            new_color=BLUE,
            affected_pixels=[(0, 0), (1, 0)],
        )

        assert command.description == 'Flood fill at (0, 0) - 2 pixels'
        assert command.operation_type == OperationType.CANVAS_FLOOD_FILL
        assert command.execute() is True
        assert editor.canvas.canvas_interface.pixels == {(0, 0): BLUE, (1, 0): BLUE}
        assert command.undo() is True
        assert editor.canvas.canvas_interface.pixels == {(0, 0): RED, (1, 0): RED}

    def test_fill_without_canvas_fails(self, editor):
        """Without a canvas both directions report failure."""
        command = FloodFillCommand(
            editor,
            start_x=0,
            start_y=0,
            old_color=RED,
            new_color=BLUE,
            affected_pixels=[(0, 0)],
        )
        editor.canvas = None

        assert command.execute() is False
        assert command.undo() is False

    def test_failing_pixel_write_fails_the_fill(self, editor):
        """A pixel write that raises makes the fill report failure."""
        command = FloodFillCommand(
            editor,
            start_x=0,
            start_y=0,
            old_color=RED,
            new_color=BLUE,
            affected_pixels=[(0, 0)],
        )
        editor.canvas.canvas_interface.error_to_raise = ValueError('bad color')

        assert command.undo() is False


class TestFrameSelectionCommand:
    """Test the frame-selection command."""

    def test_execute_and_undo_switch_frames(self, editor):
        """Execute shows the new frame; undo shows the old one."""
        command = FrameSelectionCommand(
            editor=editor,
            old_animation='idle',
            old_frame=0,
            new_animation='idle',
            new_frame=2,
        )

        assert command.execute() is True
        assert command.undo() is True
        assert editor.canvas.shown_frames == [('idle', 2), ('idle', 0)]

    def test_selection_without_canvas_fails(self, editor):
        """Without a canvas the selection cannot be shown."""
        command = FrameSelectionCommand(
            editor=editor,
            old_animation='idle',
            old_frame=0,
            new_animation='idle',
            new_frame=1,
        )
        editor.canvas = None

        assert command.execute() is False

    def test_show_frame_error_fails_the_selection(self, editor, mocker):
        """An error from show_frame makes the selection report failure."""
        command = FrameSelectionCommand(
            editor=editor,
            old_animation='idle',
            old_frame=0,
            new_animation='missing',
            new_frame=1,
        )
        mocker.patch.object(editor.canvas, 'show_frame', side_effect=KeyError('missing'))

        assert command.execute() is False


class TestFramePasteCommand:
    """Test the frame-paste command."""

    def test_paste_into_displayed_frame_updates_canvas_and_undo_restores(self, editor):
        """Pasting into the shown frame repaints the canvas; undo restores frame and canvas."""
        frame = editor.canvas.animated_sprite.animation_data['idle'][0]
        old_pixels = frame.get_pixel_data()
        new_pixels = [BLUE] * (FRAME_WIDTH * FRAME_HEIGHT)
        command = FramePasteCommand(
            editor,
            animation='idle',
            frame=0,
            old_pixels=old_pixels,
            old_duration=0.5,
            new_pixels=new_pixels,
            new_duration=2.0,
        )

        assert command.execute() is True
        assert frame.get_pixel_data() == new_pixels
        assert frame.duration == pytest.approx(2.0)
        assert editor.canvas.pixels == new_pixels
        assert editor.canvas.dirty_pixels == [True] * len(new_pixels)
        assert editor.canvas.dirty == 1

        assert command.undo() is True
        assert frame.get_pixel_data() == old_pixels
        assert frame.duration == pytest.approx(0.5)
        assert editor.canvas.pixels == old_pixels

    def test_paste_into_other_frame_leaves_canvas_alone(self, editor):
        """Pasting into a frame that is not shown changes only that frame."""
        canvas_pixels_before = list(editor.canvas.pixels)
        new_pixels = [GREEN] * (FRAME_WIDTH * FRAME_HEIGHT)
        command = FramePasteCommand(
            editor,
            animation='idle',
            frame=2,
            old_pixels=[BLUE] * 4,
            old_duration=0.5,
            new_pixels=new_pixels,
            new_duration=0.5,
        )

        assert command.execute() is True
        assert (
            editor.canvas.animated_sprite.animation_data['idle'][2].get_pixel_data() == new_pixels
        )
        assert editor.canvas.pixels == canvas_pixels_before

    def test_paste_without_canvas_fails(self, editor):
        """Without a canvas the paste reports failure."""
        command = FramePasteCommand(
            editor,
            animation='idle',
            frame=0,
            old_pixels=[RED] * 4,
            old_duration=0.5,
            new_pixels=[BLUE] * 4,
            new_duration=0.5,
        )
        editor.canvas = None

        assert command.execute() is False

    def test_paste_of_malformed_pixels_fails(self, editor):
        """Pixel data that is not color tuples is reported as a failure."""
        command = FramePasteCommand(
            editor,
            animation='idle',
            frame=2,
            old_pixels=[RED] * 4,
            old_duration=0.5,
            new_pixels=[None],
            new_duration=0.5,
        )

        assert command.execute() is False

    def test_paste_into_unknown_animation_or_frame_fails(self, editor):
        """A paste aimed at a missing animation or frame index fails."""
        unknown_animation = FramePasteCommand(
            editor,
            animation='missing',
            frame=0,
            old_pixels=[RED] * 4,
            old_duration=0.5,
            new_pixels=[BLUE] * 4,
            new_duration=0.5,
        )
        unknown_frame = FramePasteCommand(
            editor,
            animation='idle',
            frame=3,
            old_pixels=[RED] * 4,
            old_duration=0.5,
            new_pixels=[BLUE] * 4,
            new_duration=0.5,
        )

        assert unknown_animation.execute() is False
        assert unknown_frame.execute() is False

    def test_paste_into_canvas_without_dirty_tracking(self, editor):
        """A canvas with no dirty flags still gets the pasted pixels."""
        del editor.canvas.dirty_pixels
        del editor.canvas.dirty
        new_pixels = [GREEN] * 4
        command = FramePasteCommand(
            editor,
            animation='idle',
            frame=0,
            old_pixels=[RED] * 4,
            old_duration=0.5,
            new_pixels=new_pixels,
            new_duration=0.5,
        )

        assert command.execute() is True
        assert editor.canvas.pixels == new_pixels


class TestFrameAddCommand:
    """Test the frame-add command."""

    def _frame_data(self, color=GREEN, **extra):
        return {
            'pixels': [color] * (FRAME_WIDTH * FRAME_HEIGHT),
            'width': FRAME_WIDTH,
            'height': FRAME_HEIGHT,
            'duration': 0.25,
            **extra,
        }

    def test_execute_inserts_frame_and_moves_current_frame(self, editor, animated_sprite):
        """Adding a frame before the shown one shifts the shown frame along with it."""
        animated_sprite.frame_manager.current_frame = 1
        command = FrameAddCommand(
            editor, 1, 'idle', self._frame_data(color=BLUE, hitbox=(0, 0, 1, 1))
        )

        assert command.execute() is True
        frames = animated_sprite.animation_data['idle']
        assert len(frames) == 4
        assert frames[1].get_pixel_data() == [BLUE] * 4
        assert frames[1].duration == pytest.approx(0.25)
        assert frames[1].hitbox == pygame.Rect(0, 0, 1, 1)
        # The green frame the canvas showed moved to index 2, and the canvas follows it
        assert animated_sprite.frame_manager.current_frame == 2
        assert editor.canvas.shown_frames[-1] == ('idle', 2)
        assert editor.film_strip_coordinator.notifications == [
            ('refresh', 'idle'),
            ('inserted', 'idle', 1),
        ]

    def test_undo_removes_the_added_frame(self, editor, animated_sprite):
        """Undo removes the frame execute added, leaving the original frames."""
        command = FrameAddCommand(editor, 3, 'idle', self._frame_data())

        assert command.execute() is True
        assert command.undo() is True
        assert _first_pixel_colors(animated_sprite, 'idle') == [RED, GREEN, BLUE]
        assert editor.film_strip_coordinator.notifications[-1] == ('removed', 'idle', 3)

    def test_undoing_an_add_before_the_shown_frame_keeps_showing_it(self, editor, animated_sprite):
        """Undoing an add before the shown frame returns the canvas to the same (blue) frame.

        Undo deletes through the same helpers as FrameDeleteCommand (BUGS.md #94).
        """
        animated_sprite.frame_manager.current_frame = 2
        command = FrameAddCommand(editor, 0, 'idle', self._frame_data())

        assert command.execute() is True
        assert animated_sprite.frame_manager.current_frame == 3
        assert command.undo() is True
        assert animated_sprite.frame_manager.current_frame == 2
        assert animated_sprite.animation_data['idle'][2].get_pixel_data()[0] == BLUE

    def test_add_to_other_animation_leaves_current_frame(self, editor, animated_sprite):
        """Adding to an animation the canvas is not showing does not move the canvas."""
        command = FrameAddCommand(editor, 0, 'walk', self._frame_data())

        assert command.execute() is True
        assert len(animated_sprite.animation_data['walk']) == 1
        assert animated_sprite.frame_manager.current_animation == 'idle'
        assert editor.canvas.shown_frames == []

    def test_add_clamps_a_stale_current_frame(self, editor, animated_sprite):
        """A current frame past the end of the animation is clamped to its last frame."""
        animated_sprite.frame_manager.current_frame = 9
        command = FrameAddCommand(editor, 0, 'idle', self._frame_data())

        assert command.execute() is True
        assert animated_sprite.frame_manager.current_frame == 3
        assert editor.canvas.shown_frames[-1] == ('idle', 3)

    def test_add_without_pixels_keeps_blank_frame(self, editor, animated_sprite):
        """Frame data without pixels adds a blank frame of the recorded size."""
        frame_data = {'width': FRAME_WIDTH, 'height': FRAME_HEIGHT}
        command = FrameAddCommand(editor, 3, 'idle', frame_data)

        assert command.execute() is True
        added_frame = animated_sprite.animation_data['idle'][3]
        assert added_frame.get_size() == (FRAME_WIDTH, FRAME_HEIGHT)
        assert added_frame.duration == pytest.approx(1.0)

    def test_add_without_canvas_fails(self, editor):
        """Without a canvas the frame cannot be added."""
        command = FrameAddCommand(editor, 0, 'idle', self._frame_data())
        editor.canvas = None

        assert command.execute() is False

    def test_add_with_missing_size_fails(self, editor, animated_sprite):
        """Frame data without a size is reported as a failure and adds nothing."""
        command = FrameAddCommand(editor, 0, 'idle', {'pixels': [RED]})

        assert command.execute() is False
        assert len(animated_sprite.animation_data['idle']) == 3

    def test_undo_without_canvas_fails(self, editor):
        """Without a canvas the frame cannot be removed."""
        command = FrameAddCommand(editor, 0, 'idle', self._frame_data())
        editor.canvas = None

        assert command.undo() is False

    def test_undo_for_unknown_animation_fails(self, editor):
        """Removing a frame from an animation that does not exist fails."""
        command = FrameAddCommand(editor, 0, 'missing', self._frame_data())

        assert command.undo() is False

    def test_undo_out_of_range_fails(self, editor, animated_sprite):
        """Removing a frame index past the end fails and keeps every frame."""
        command = FrameAddCommand(editor, 7, 'idle', self._frame_data())

        assert command.undo() is False
        assert len(animated_sprite.animation_data['idle']) == 3

    def test_undo_error_while_refreshing_fails(self, editor, mocker):
        """An error from the film strip refresh is reported as a failure."""
        command = FrameAddCommand(editor, 0, 'idle', self._frame_data())
        mocker.patch.object(
            editor.film_strip_coordinator,
            'refresh_all_film_strip_widgets',
            side_effect=AttributeError('no film strip'),
        )

        assert command.undo() is False


class TestFrameDeleteCommand:
    """Test the frame-delete command (the inverse of a frame add)."""

    def test_execute_deletes_and_undo_restores_frame(self, editor, animated_sprite):
        """Execute removes the frame; undo puts it back with its pixels."""
        frame_data = {
            'pixels': [GREEN] * 4,
            'width': FRAME_WIDTH,
            'height': FRAME_HEIGHT,
            'duration': 0.5,
        }
        command = FrameDeleteCommand(editor, 1, 'idle', frame_data)

        assert command.operation_type == OperationType.FILM_STRIP_FRAME_DELETE
        assert command.execute() is True
        assert _first_pixel_colors(animated_sprite, 'idle') == [RED, BLUE]
        assert command.undo() is True
        assert _first_pixel_colors(animated_sprite, 'idle') == [RED, GREEN, BLUE]

    def test_deleting_shown_first_frame_keeps_frame_zero(self, editor, animated_sprite):
        """Deleting frame 0 while it is shown keeps the canvas on frame 0 and stops playback."""
        animated_sprite.play()
        command = FrameDeleteCommand(editor, 0, 'idle', {'width': 2, 'height': 2})

        assert command.execute() is True
        assert animated_sprite.is_playing is False
        assert animated_sprite.frame_manager.current_frame == 0
        assert editor.canvas.shown_frames[-1] == ('idle', 0)

    def test_deleting_last_frame_of_animation_shows_frame_zero(self, editor):
        """Deleting an animation's only frame leaves the canvas on frame 0."""
        single_frame_sprite = AnimatedSprite()
        single_frame_sprite.add_animation('solo', [_make_frame(RED)])
        single_frame_sprite.frame_manager.current_animation = 'solo'
        single_frame_editor = _Editor(single_frame_sprite)
        command = FrameDeleteCommand(single_frame_editor, 0, 'solo', {'width': 2, 'height': 2})

        assert command.execute() is True
        assert single_frame_sprite.animation_data['solo'] == []
        assert single_frame_sprite.frame_manager.current_frame == 0

    def test_deleting_frame_after_shown_frame_keeps_shown_frame(self, editor, animated_sprite):
        """Deleting a frame after the shown one leaves the shown frame where it is."""
        command = FrameDeleteCommand(editor, 2, 'idle', {'width': 2, 'height': 2})

        assert command.execute() is True
        assert animated_sprite.frame_manager.current_frame == 0

    def test_deleting_from_other_animation_leaves_canvas(self, editor, animated_sprite):
        """Deleting from an animation the canvas does not show leaves the canvas alone."""
        animated_sprite.add_animation('walk', [_make_frame(RED), _make_frame(GREEN)])
        command = FrameDeleteCommand(editor, 0, 'walk', {'width': 2, 'height': 2})

        assert command.execute() is True
        assert len(animated_sprite.animation_data['walk']) == 1
        assert editor.canvas.shown_frames == []

    def test_deleting_shown_frame_shows_the_frame_before_it(self, editor, animated_sprite):
        """Deleting the shown last frame moves the canvas to the frame before it."""
        animated_sprite.frame_manager.current_frame = 2
        command = FrameDeleteCommand(editor, 2, 'idle', {'width': 2, 'height': 2})

        assert command.execute() is True
        assert animated_sprite.frame_manager.current_frame == 1
        assert editor.canvas.shown_frames[-1] == ('idle', 1)

    def test_deleting_frame_before_shown_frame_keeps_showing_it(self, editor, animated_sprite):
        """Deleting a frame before the shown one keeps the canvas on the same (blue) frame.

        Both deletion helpers used to decrement current_frame (BUGS.md #94).
        """
        animated_sprite.frame_manager.current_frame = 2
        command = FrameDeleteCommand(editor, 0, 'idle', {'width': 2, 'height': 2})

        assert command.execute() is True
        shown_frame_index = animated_sprite.frame_manager.current_frame
        assert animated_sprite.animation_data['idle'][shown_frame_index].get_pixel_data()[0] == BLUE
        assert editor.canvas.shown_frames[-1] == ('idle', 1)

    def test_deleting_shown_middle_frame_shows_the_frame_before_it(self, editor, animated_sprite):
        """Deleting the shown middle frame moves the canvas to the (red) frame before it."""
        animated_sprite.frame_manager.current_frame = 1
        command = FrameDeleteCommand(editor, 1, 'idle', {'width': 2, 'height': 2})

        assert command.execute() is True
        assert animated_sprite.frame_manager.current_frame == 0
        assert editor.canvas.shown_frames[-1] == ('idle', 0)


class TestFrameReorderCommand:
    """Test the frame-reorder command."""

    def test_execute_moves_frame_and_undo_moves_it_back(self, editor, animated_sprite):
        """Execute moves the frame; undo restores the original order."""
        film_strip_widget = _FilmStripWidget()
        editor.film_strip_widget = film_strip_widget
        command = FrameReorderCommand(editor, 0, 2, 'idle')

        assert command.description == "Moved frame 0 to 2 in 'idle'"
        assert command.execute() is True
        assert _first_pixel_colors(animated_sprite, 'idle') == [GREEN, BLUE, RED]
        assert film_strip_widget.refresh_count == 1
        assert command.undo() is True
        assert _first_pixel_colors(animated_sprite, 'idle') == [RED, GREEN, BLUE]

    def test_reorder_without_film_strip_widget(self, editor, animated_sprite):
        """An editor without a film strip widget still reorders the frames."""
        assert FrameReorderCommand(editor, 2, 0, 'idle').execute() is True
        assert _first_pixel_colors(animated_sprite, 'idle') == [BLUE, RED, GREEN]

    def test_reorder_without_canvas_fails(self, editor):
        """Without a canvas nothing can be reordered."""
        editor.canvas = None

        assert FrameReorderCommand(editor, 0, 1, 'idle').execute() is False

    def test_reorder_of_unknown_animation_fails(self, editor):
        """Reordering an animation that does not exist fails."""
        assert FrameReorderCommand(editor, 0, 1, 'missing').execute() is False

    def test_reorder_out_of_range_fails(self, editor, animated_sprite):
        """An index past the end fails and keeps the order."""
        assert FrameReorderCommand(editor, 0, 5, 'idle').execute() is False
        assert _first_pixel_colors(animated_sprite, 'idle') == [RED, GREEN, BLUE]

    def test_reorder_widget_error_fails(self, editor, mocker):
        """An error while refreshing the widget is reported as a failure."""
        film_strip_widget = _FilmStripWidget()
        mocker.patch.object(film_strip_widget, 'refresh', side_effect=TypeError('layout'))
        editor.film_strip_widget = film_strip_widget

        assert FrameReorderCommand(editor, 0, 1, 'idle').execute() is False


class TestAnimationAddCommand:
    """Test the animation-add command."""

    def _animation_data(self):
        return {
            'frames': [
                {'pixels': [GREEN] * 4, 'width': 2, 'height': 2, 'duration': 0.2},
                {'width': 2, 'height': 2},
            ],
        }

    def test_execute_adds_frames_and_refreshes_widgets(self, editor, animated_sprite):
        """Execute adds the animation's frames and refreshes every film strip widget."""
        film_strip_widget = _FilmStripWidget()
        sprite_widget = _FilmStripWidget()
        film_strip_sprite = _FilmStripSprite(sprite_widget)
        editor.film_strip_widget = film_strip_widget
        editor.film_strip_sprites = {
            'walk': film_strip_sprite,
            'empty': _FilmStripSprite(None),
        }
        command = AnimationAddCommand(editor, 'walk', self._animation_data())

        assert command.execute() is True
        walk_frames = animated_sprite.animation_data['walk']
        assert len(walk_frames) == 2
        assert walk_frames[0].get_pixel_data() == [GREEN] * 4
        assert walk_frames[0].duration == pytest.approx(0.2)
        assert walk_frames[1].duration == pytest.approx(1.0)
        assert film_strip_widget.refresh_count == 1
        assert sprite_widget.refresh_count == 1
        assert film_strip_sprite.dirty == 1

    def test_undo_deletes_animation_and_reloads_film_strips(self, editor, animated_sprite):
        """Undo removes the animation and tells the coordinator to rebuild."""
        command = AnimationAddCommand(editor, 'walk', self._animation_data())
        command.execute()

        assert command.undo() is True
        assert 'walk' not in animated_sprite.animation_data
        assert editor.film_strip_coordinator.notifications == [
            ('sprite_loaded', animated_sprite),
        ]

    def test_add_without_canvas_fails(self, editor):
        """Without a canvas the animation cannot be added."""
        editor.canvas = None

        assert AnimationAddCommand(editor, 'walk', self._animation_data()).execute() is False

    def test_add_with_missing_size_fails(self, editor):
        """Frame data without a size is reported as a failure."""
        command = AnimationAddCommand(editor, 'walk', {'frames': [{'pixels': [RED]}]})

        assert command.execute() is False

    def test_delete_without_canvas_fails(self, editor):
        """Without a canvas the animation cannot be removed."""
        editor.canvas = None

        assert AnimationAddCommand(editor, 'walk', {}).undo() is False

    def test_delete_of_unknown_animation_fails(self, editor):
        """Removing an animation that does not exist fails."""
        assert AnimationAddCommand(editor, 'missing', {}).undo() is False

    def test_delete_error_while_reloading_fails(self, editor, mocker):
        """An error while rebuilding the film strips is reported as a failure."""
        mocker.patch.object(
            editor.film_strip_coordinator,
            'on_sprite_loaded',
            side_effect=AttributeError('no film strips'),
        )

        assert AnimationAddCommand(editor, 'idle', {}).undo() is False


class TestAnimationDeleteCommand:
    """Test the animation-delete command."""

    def test_delete_drops_settings_and_undo_restores_them(self, editor, animated_sprite):
        """Execute drops the animation and its transitions; undo puts all of it back."""
        animated_sprite.add_animation('walk', [_make_frame(BLUE)])
        animated_sprite._loop_flags['idle'] = False
        animated_sprite._animation_frame_intervals['idle'] = 0.3
        transition = {'from': 'idle', 'to': 'walk', 'on': 'move'}
        animated_sprite.transition_data = [transition]
        animation_data = {
            'frames': [
                {'pixels': [color] * 4, 'width': 2, 'height': 2, 'duration': 0.5}
                for color in (RED, GREEN, BLUE)
            ],
            'position': 0,
            'loop_flag': False,
            'frame_interval': 0.3,
            'transitions': animated_sprite.transitions_for_animation('idle'),
        }
        command = AnimationDeleteCommand(editor, 'idle', animation_data)

        assert command.execute() is True
        assert list(animated_sprite.animation_data) == ['walk']
        assert animated_sprite.transition_data == []
        assert 'idle' not in animated_sprite._loop_flags

        assert command.undo() is True
        assert list(animated_sprite.animation_data) == ['idle', 'walk']
        assert _first_pixel_colors(animated_sprite, 'idle') == [RED, GREEN, BLUE]
        assert animated_sprite._loop_flags['idle'] is False
        assert animated_sprite._animation_frame_intervals['idle'] == pytest.approx(0.3)
        assert animated_sprite.transition_data == [transition]

    def test_undo_of_old_capture_restores_only_frames(self, editor, animated_sprite):
        """A capture without a position restores the frames at the end of the order."""
        animation_data = {'frames': [{'pixels': [RED] * 4, 'width': 2, 'height': 2}]}
        command = AnimationDeleteCommand(editor, 'walk', animation_data)

        assert command.undo() is True
        assert list(animated_sprite.animation_data) == ['idle', 'walk']

    def test_execute_of_unknown_animation_fails(self, editor):
        """Deleting an animation that does not exist fails."""
        assert AnimationDeleteCommand(editor, 'missing', {}).execute() is False

    def test_undo_without_canvas_fails(self, editor):
        """Without a canvas the animation cannot be restored."""
        editor.canvas = None

        assert AnimationDeleteCommand(editor, 'idle', {'frames': []}).undo() is False


class TestAnimationRenameCommand:
    """Test the animation-rename command."""

    def test_execute_renames_and_undo_renames_back(self, editor, animated_sprite):
        """Execute gives the new name; undo gives the old name back."""
        command = AnimationRenameCommand(editor, 'idle', 'rest')

        assert command.execute() is True
        assert list(animated_sprite.animation_data) == ['rest']
        assert command.undo() is True
        assert list(animated_sprite.animation_data) == ['idle']

    def test_rename_without_canvas_fails(self, editor):
        """Without a canvas there is nothing to rename."""
        editor.canvas = None

        assert AnimationRenameCommand(editor, 'idle', 'rest').execute() is False

    def test_rename_onto_existing_name_fails(self, editor, animated_sprite):
        """Renaming onto a name already in use fails and keeps both animations."""
        animated_sprite.add_animation('walk', [_make_frame(RED)])

        assert AnimationRenameCommand(editor, 'idle', 'walk').execute() is False
        assert list(animated_sprite.animation_data) == ['idle', 'walk']


class TestControllerPositionCommand:
    """Test the controller-position command."""

    def _editor_with_controller(self, editor):
        mode_switcher = ModeSwitcher()
        mode_switcher.register_controller(0, ControllerMode.CANVAS)
        editor.mode_switcher = mode_switcher
        editor.controller_handler = _ControllerHandler()
        return mode_switcher

    def test_execute_and_undo_move_the_controller(self, editor):
        """Execute saves the new position; undo saves the old one; indicators update."""
        mode_switcher = self._editor_with_controller(editor)
        command = ControllerPositionCommand(
            editor,
            0,
            old_position=(1, 1),
            new_position=(5, 6),
        )

        assert command.execute() is True
        assert mode_switcher.get_controller_position(0).position == (5, 6)
        assert command.undo() is True
        assert mode_switcher.get_controller_position(0).position == (1, 1)
        assert editor.controller_handler.canvas_indicator_updates == [0, 0]

    def test_position_without_controller_handler(self, editor):
        """Without a controller handler the position is still saved."""
        mode_switcher = self._editor_with_controller(editor)
        del editor.controller_handler
        command = ControllerPositionCommand(editor, 0, old_position=(0, 0), new_position=(3, 2))

        assert command.execute() is True
        assert mode_switcher.get_controller_position(0).position == (3, 2)

    def test_position_without_mode_switcher_fails(self, editor):
        """Without a mode switcher the position cannot be applied."""
        command = ControllerPositionCommand(editor, 0, old_position=(0, 0), new_position=(1, 1))

        assert command.execute() is False

    def test_position_error_fails(self, editor, mocker):
        """An error from the mode switcher is reported as a failure."""
        self._editor_with_controller(editor)
        mocker.patch.object(
            editor.mode_switcher,
            'save_controller_position',
            side_effect=KeyError(0),
        )
        command = ControllerPositionCommand(editor, 0, old_position=(0, 0), new_position=(1, 1))

        assert command.execute() is False
        assert editor.applying_undo_redo is False


class TestControllerModeCommand:
    """Test the controller-mode command."""

    def _editor_with_controller(self, editor):
        mode_switcher = ModeSwitcher()
        mode_switcher.register_controller(0, ControllerMode.CANVAS)
        editor.mode_switcher = mode_switcher
        editor.controller_handler = _ControllerHandler()
        return mode_switcher

    def test_execute_and_undo_switch_modes(self, editor):
        """Execute switches to the new mode; undo switches back."""
        mode_switcher = self._editor_with_controller(editor)
        command = ControllerModeCommand(editor, 0, 'canvas', 'film_strip')

        assert command.execute() is True
        assert mode_switcher.get_controller_mode(0) == ControllerMode.FILM_STRIP
        assert command.undo() is True
        assert mode_switcher.get_controller_mode(0) == ControllerMode.CANVAS
        assert editor.controller_handler.mode_indicator_updates == [
            (0, ControllerMode.FILM_STRIP),
            (0, ControllerMode.CANVAS),
        ]

    def test_mode_without_controller_handler(self, editor):
        """Without a controller handler the mode still switches."""
        mode_switcher = self._editor_with_controller(editor)
        del editor.controller_handler

        assert ControllerModeCommand(editor, 0, 'canvas', 'r_slider').execute() is True
        assert mode_switcher.get_controller_mode(0) == ControllerMode.R_SLIDER

    def test_invalid_mode_fails(self, editor):
        """A mode name that is not a ControllerMode fails and keeps the mode."""
        mode_switcher = self._editor_with_controller(editor)

        assert ControllerModeCommand(editor, 0, 'canvas', 'not_a_mode').execute() is False
        assert mode_switcher.get_controller_mode(0) == ControllerMode.CANVAS

    def test_mode_without_mode_switcher_fails(self, editor):
        """Without a mode switcher the mode cannot be applied."""
        assert ControllerModeCommand(editor, 0, 'canvas', 'film_strip').execute() is False

    def test_unregistered_controller_fails(self, editor):
        """A controller the mode switcher does not know is reported as a failure."""
        self._editor_with_controller(editor)

        assert ControllerModeCommand(editor, 9, 'canvas', 'film_strip').execute() is False


class TestFrameCopyCommand:
    """Test the informational frame-copy command."""

    def test_copy_is_informational(self, editor, animated_sprite):
        """Execute and undo succeed without changing any frame."""
        command = FrameCopyCommand(editor, 1, 'idle', {'pixels': [GREEN] * 4})

        assert command.description == "Copied frame 1 from 'idle'"
        assert command.execute() is True
        assert command.undo() is True
        assert _first_pixel_colors(animated_sprite, 'idle') == [RED, GREEN, BLUE]
