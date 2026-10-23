"""Tests for FilmStripCoordinator (glitchygames/bitmappy/film_strip_coordinator.py).

The coordinator is driven against a small stand-in editor that holds real
AnimatedSprite and SpriteFrame objects, so each test checks the editor state
the coordinator leaves behind (selection, scroll offset, frames, strips).
"""

import logging
from types import SimpleNamespace

import pygame
import pytest

from glitchygames.bitmappy.film_strip_coordinator import FilmStripCoordinator
from glitchygames.bitmappy.history.operations import FilmStripOperationTracker
from glitchygames.bitmappy.history.undo_redo import UndoRedoManager
from glitchygames.display_mode import set_display_mode
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

FRAME_WIDTH = 4
FRAME_HEIGHT = 4
MAGENTA = (255, 0, 255, 255)
FRAME_COLOR = (10, 20, 30, 255)


@pytest.fixture(autouse=True)
def _display_surface():
    """Give the coordinator a display surface (it sizes film strips from it)."""
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=(800, 600))


# ---------------------------------------------------------------------------
# Stand-ins
# ---------------------------------------------------------------------------


def _make_frame(*, color=FRAME_COLOR, duration=0.5):
    """Create a real SpriteFrame filled with one color.

    Returns:
        SpriteFrame: A FRAME_WIDTH x FRAME_HEIGHT frame with pixel data.

    """
    surface = pygame.Surface((FRAME_WIDTH, FRAME_HEIGHT), pygame.SRCALPHA)
    surface.fill(color)
    frame = SpriteFrame(surface=surface, duration=duration)
    frame.set_pixel_data([color] * (FRAME_WIDTH * FRAME_HEIGHT))
    return frame


def _make_animated_sprite(*, frame_counts):
    """Create a real AnimatedSprite with the given animations.

    Args:
        frame_counts: Mapping of animation name to its number of frames.

    Returns:
        AnimatedSprite: The sprite, showing frame 0 of its first animation.

    """
    animated_sprite = AnimatedSprite()
    animated_sprite._animations = {
        animation_name: [_make_frame() for _ in range(frame_count)]
        for animation_name, frame_count in frame_counts.items()
    }
    animated_sprite._animation_order = list(frame_counts)
    animated_sprite.frame_manager.current_animation = next(iter(frame_counts))
    animated_sprite.frame_manager.current_frame = 0
    return animated_sprite


class _CanvasInterfaceStandIn:
    """Canvas interface stand-in that remembers the frame it was told to show."""

    def __init__(self):
        self.current_frame = None

    def set_current_frame(self, animation, frame):
        """Remember the frame the canvas interface now shows."""
        self.current_frame = (animation, frame)


class _CanvasStandIn:
    """Canvas stand-in that shows frames of a real AnimatedSprite."""

    def __init__(self, *, animated_sprite):
        self.animated_sprite = animated_sprite
        self.rect = pygame.Rect(0, 24, 320, 320)
        self.pixels_across = FRAME_WIDTH
        self.pixels_tall = FRAME_HEIGHT
        self.current_animation = next(iter(animated_sprite._animations), '')
        self.current_frame = 0
        self.dirty = 0
        self.redraw_count = 0
        self.resize_checks = []
        self.canvas_interface = _CanvasInterfaceStandIn()
        self.pixels = [MAGENTA] * (FRAME_WIDTH * FRAME_HEIGHT)
        self.shown_frames = []

    def show_frame(self, animation, frame):
        """Show a frame, raising like the real canvas for a missing one.

        Raises:
            IndexError: The frame index is out of range.

        """
        frames = self.animated_sprite._animations[animation]
        if not 0 <= frame < len(frames):
            raise IndexError(frame)
        self.shown_frames.append((animation, frame))
        self.current_animation = animation
        self.current_frame = frame

    def force_redraw(self):
        """Count redraw requests."""
        self.redraw_count += 1

    def _check_and_resize_canvas(self, loaded_sprite):
        """Remember which sprite the canvas was asked to fit."""
        self.resize_checks.append(loaded_sprite)


class _ControllerHandlerStandIn:
    """Controller handler stand-in that remembers the preserved selections."""

    def __init__(self):
        self.reinitialized_with = []
        # The film strips read this when they render (no controller in film strip mode)
        self.film_strip_controller_selections = {}

    def reinitialize_multi_controller_system(self, preserved_selections):
        """Remember each reinitialization."""
        self.reinitialized_with.append(preserved_selections)


class _EditorStandIn:
    """Editor stand-in carrying the state the coordinator reads and writes."""

    def __init__(self, *, animated_sprite=None):
        self.canvas = (
            _CanvasStandIn(animated_sprite=animated_sprite) if animated_sprite is not None else None
        )
        self.film_strips = {}
        self.film_strip_sprites = {}
        self.film_strip_scroll_offset = 0
        self.max_visible_strips = 2
        self.selected_animation = None
        self.selected_frame = None
        self.all_sprites = pygame.sprite.LayeredDirty()
        self.controller_handler = _ControllerHandlerStandIn()
        self.color_well = None
        self.dt = 0.016
        self.is_dragging_film_strips = False
        self.film_strip_drag_start_y = None
        self.film_strip_drag_start_offset = None
        self.screenshot = None


class _StripWidgetStandIn:
    """Film strip widget stand-in that records what the coordinator asks of it."""

    def __init__(self, *, animated_sprite=None, copy_result=True, paste_result=True):
        self.animated_sprite = animated_sprite
        self.rect = pygame.Rect(400, 0, 300, 145)
        self.current_animation = ''
        self.current_frame = 0
        self.selected_frame = 0
        self.is_selected = False
        self.dirty_marks = 0
        self.layout_updates = 0
        self.tab_creations = 0
        self.tab_resets = 0
        self.hovered_removal_button = None
        self.removed_frames = []
        self.frame_index = None
        self.animation_updates = []
        self.copy_result = copy_result
        self.paste_result = paste_result

    def mark_dirty(self):
        """Count redraw requests."""
        self.dirty_marks += 1

    def set_current_frame(self, animation, frame):
        """Show a frame."""
        self.current_animation = animation
        self.current_frame = frame

    def update_layout(self):
        """Count layout updates."""
        self.layout_updates += 1

    def _create_film_tabs(self):
        """Count tab rebuilds."""
        self.tab_creations += 1

    def _initialize_preview_animations(self):
        """No preview animations to set up."""

    def _calculate_layout(self):
        """No layout to calculate."""

    def reset_all_tab_states(self):
        """Count tab state resets."""
        self.tab_resets += 1

    def _remove_frame(self, animation, frame_index):
        """Remember the removed frame."""
        self.removed_frames.append((animation, frame_index))

    def set_frame_index(self, frame_index):
        """Remember the frame index shown."""
        self.frame_index = frame_index

    def update_animations(self, dt):
        """Remember each animation update."""
        self.animation_updates.append(dt)

    def copy_current_frame(self):
        """Report the copy result.

        Returns:
            bool: The configured result.

        """
        return self.copy_result

    def paste_to_current_frame(self):
        """Report the paste result.

        Returns:
            bool: The configured result.

        """
        return self.paste_result


def _strip_sprite(*, widget=None, visible=True):
    """Create a film strip sprite stand-in.

    Returns:
        SimpleNamespace: An object with the film strip sprite attributes.

    """
    return SimpleNamespace(
        film_strip_widget=widget,
        visible=visible,
        dirty=0,
        rect=pygame.Rect(400, 0, 300, 145),
        image=None,
    )


def _editor_with_strip_stand_ins(*, frame_counts):
    """Create an editor whose strips are stand-ins, one per animation.

    Returns:
        _EditorStandIn: The editor, its strips and sprites keyed by animation.

    """
    editor = _EditorStandIn(animated_sprite=_make_animated_sprite(frame_counts=frame_counts))
    for animation_name in frame_counts:
        widget = _StripWidgetStandIn()
        editor.film_strips[animation_name] = widget
        editor.film_strip_sprites[animation_name] = _strip_sprite(widget=widget)
    return editor


def _editor_with_real_film_strips(*, frame_counts, with_undo_history=False):
    """Create an editor and build its real film strips through the coordinator.

    Returns:
        tuple: (editor, coordinator).

    """
    editor = _EditorStandIn(animated_sprite=_make_animated_sprite(frame_counts=frame_counts))
    if with_undo_history:
        editor.undo_redo_manager = UndoRedoManager(max_history=50)
        editor.film_strip_operation_tracker = FilmStripOperationTracker(
            editor.undo_redo_manager,
            editor=editor,
        )
    coordinator = FilmStripCoordinator(editor)
    editor.film_strip_coordinator = coordinator
    coordinator.setup_film_strips()
    return editor, coordinator


# ---------------------------------------------------------------------------
# Film strip creation
# ---------------------------------------------------------------------------


class TestCreateFilmStripsWithoutSprite:
    """_create_film_strips makes nothing until the canvas has an animated sprite."""

    @pytest.mark.parametrize(
        'canvas',
        [
            pytest.param('missing', id='no_canvas_attribute'),
            pytest.param(None, id='canvas_is_none'),
            pytest.param(SimpleNamespace(), id='canvas_without_animated_sprite'),
            pytest.param(SimpleNamespace(animated_sprite=None), id='animated_sprite_is_none'),
        ],
    )
    def test_no_strips_are_created(self, canvas):
        """Without a canvas sprite no strip is made and controllers are not reset."""
        editor = _EditorStandIn()
        if canvas == 'missing':
            del editor.canvas
        else:
            editor.canvas = canvas
        coordinator = FilmStripCoordinator(editor)

        coordinator._create_film_strips(editor.all_sprites)

        assert editor.film_strips == {}
        assert editor.controller_handler.reinitialized_with == []


class TestSetupFilmStrips:
    """setup_film_strips builds one real strip per animation."""

    def test_each_animation_gets_a_strip_and_the_first_is_selected(self):
        """Two animations make two strips; frame 0 of the first is selected."""
        editor, _coordinator = _editor_with_real_film_strips(frame_counts={'idle': 2, 'walk': 3})

        assert list(editor.film_strips) == ['idle', 'walk']
        assert list(editor.film_strip_sprites) == ['idle', 'walk']
        assert editor.selected_animation == 'idle'
        assert editor.selected_frame == 0
        assert editor.canvas.parent_scene is editor
        # The strips start at the color-well-less fallback, right of the canvas
        assert editor.film_strips['idle'].rect.x == editor.canvas.rect.right + 4

    def test_film_strip_x_follows_the_color_well(self):
        """With a color well, the strips start one pixel right of it."""
        editor = _EditorStandIn(animated_sprite=_make_animated_sprite(frame_counts={'idle': 1}))
        editor.color_well = SimpleNamespace(rect=pygame.Rect(330, 24, 50, 50))
        coordinator = FilmStripCoordinator(editor)

        coordinator.setup_film_strips()

        assert editor.film_strips['idle'].rect.x == 381
        assert editor.scroll_up_arrow.rect.x == 391

    def test_empty_animations_are_left_alone(self):
        """A sprite without animations gets no strips from setup."""
        animated_sprite = AnimatedSprite()
        animated_sprite._animations = {}
        editor = _EditorStandIn(animated_sprite=animated_sprite)
        coordinator = FilmStripCoordinator(editor)

        coordinator.setup_film_strips()

        assert editor.film_strips == {}


class TestCreateScrollArrows:
    """_create_scroll_arrows needs a canvas."""

    def test_no_arrow_without_a_canvas(self):
        """Without a canvas no scroll arrow is made."""
        editor = _EditorStandIn()
        coordinator = FilmStripCoordinator(editor)

        coordinator._create_scroll_arrows()

        assert not hasattr(editor, 'scroll_up_arrow')


class TestFrameImageRepair:
    """Frames without an image get one built from their pixels or a magenta fill."""

    def test_image_is_built_from_pixel_data(self):
        """The new image holds the frame's pixels in row-major order; extras are dropped."""
        frame = _make_frame(color=MAGENTA)
        frame.pixels = [(index, 0, 0, 255) for index in range(FRAME_WIDTH * FRAME_HEIGHT + 1)]
        coordinator = FilmStripCoordinator(_EditorStandIn())

        coordinator._create_frame_image_from_pixels(frame, 0)

        assert frame.image.get_at((1, 0)) == (1, 0, 0, 255)
        assert frame.image.get_at((0, 1)) == (FRAME_WIDTH, 0, 0, 255)

    def test_empty_pixel_data_keeps_the_old_image(self):
        """A frame with no pixel data keeps its image."""
        original_image = pygame.Surface((2, 2))
        frame = SimpleNamespace(get_pixel_data=list, image=original_image)
        coordinator = FilmStripCoordinator(_EditorStandIn())

        coordinator._create_frame_image_from_pixels(frame, 0)

        assert frame.image is original_image

    def test_invalid_pixel_data_is_logged_not_raised(self):
        """A pixel that is not a color is logged and the image is left alone."""
        original_image = pygame.Surface((2, 2))
        frame = SimpleNamespace(
            get_pixel_data=lambda: ['not a color'],
            get_size=lambda: (2, 2),
            image=original_image,
        )
        coordinator = FilmStripCoordinator(_EditorStandIn())

        coordinator._create_frame_image_from_pixels(frame, 0)

        assert frame.image is original_image

    def test_default_frame_is_magenta(self):
        """The default frame image and pixels are all opaque magenta."""
        frame = _make_frame()
        coordinator = FilmStripCoordinator(_EditorStandIn())

        coordinator._create_default_magenta_frame(frame, 0)

        assert frame.image.get_at((3, 3)) == MAGENTA
        assert frame.pixels == [MAGENTA] * (FRAME_WIDTH * FRAME_HEIGHT)

    def test_default_frame_failure_is_logged_not_raised(self):
        """A frame that has no size is logged and left without an image."""
        frame = SimpleNamespace()
        coordinator = FilmStripCoordinator(_EditorStandIn())

        coordinator._create_default_magenta_frame(frame, 0)

        assert not hasattr(frame, 'image')

    def test_frames_without_images_are_repaired(self):
        """Missing frames are skipped; imageless frames get pixels or magenta."""
        frame_with_pixels = SimpleNamespace(
            image=None,
            get_pixel_data=lambda: [FRAME_COLOR] * 4,
            get_size=lambda: (2, 2),
        )
        frame_without_pixels = SimpleNamespace(
            image=None,
            get_pixel_data=lambda: None,
            get_size=lambda: (2, 2),
            set_pixel_data=lambda pixels: setattr(frame_without_pixels, 'pixels', pixels),
        )
        animated_sprite = SimpleNamespace(
            _animations={'idle': [None, frame_with_pixels, frame_without_pixels]},
        )
        coordinator = FilmStripCoordinator(_EditorStandIn())

        coordinator._ensure_frames_have_image_data(animated_sprite)

        assert frame_with_pixels.image.get_at((1, 1)) == FRAME_COLOR
        assert frame_without_pixels.image.get_at((1, 1)) == MAGENTA
        assert frame_without_pixels.pixels == [MAGENTA] * 4

    def test_sprite_without_animations_is_left_alone(self):
        """A sprite with no animations is returned from without change."""
        animated_sprite = SimpleNamespace(_animations={})
        coordinator = FilmStripCoordinator(_EditorStandIn())

        coordinator._ensure_frames_have_image_data(animated_sprite)

        assert animated_sprite._animations == {}


# ---------------------------------------------------------------------------
# Initial selection and visibility
# ---------------------------------------------------------------------------


class TestSelectInitialFilmStrip:
    """_select_initial_film_strip picks frame 0 of the first animation."""

    def test_uses_strip_order_without_a_canvas_sprite(self):
        """Without a canvas sprite, the first strip key is selected."""
        editor = _EditorStandIn()
        editor.film_strips = {'walk': _StripWidgetStandIn(), 'idle': _StripWidgetStandIn()}
        coordinator = FilmStripCoordinator(editor)

        coordinator._select_initial_film_strip()

        assert editor.selected_animation == 'walk'
        assert editor.selected_frame == 0
        assert editor.film_strips['idle'].dirty_marks == 1

    def test_nothing_is_selected_when_the_sprite_has_no_animations(self):
        """An empty animation list selects nothing."""
        animated_sprite = AnimatedSprite()
        animated_sprite._animations = {}
        editor = _EditorStandIn(animated_sprite=animated_sprite)
        editor.film_strips = {'walk': _StripWidgetStandIn()}
        coordinator = FilmStripCoordinator(editor)

        coordinator._select_initial_film_strip()

        assert editor.selected_animation is None


class TestUpdateFilmStripVisibility:
    """update_film_strip_visibility shows only the scrolled-to strips."""

    def test_strip_order_is_used_without_a_canvas(self):
        """Without a canvas the strips are placed in their own order from y 0."""
        editor = _EditorStandIn()
        for animation_name in ('idle', 'walk', 'jump'):
            widget = _StripWidgetStandIn()
            editor.film_strips[animation_name] = widget
            editor.film_strip_sprites[animation_name] = _strip_sprite(widget=widget)
        editor.film_strip_scroll_offset = 1
        coordinator = FilmStripCoordinator(editor)

        coordinator.update_film_strip_visibility()

        assert [
            film_strip_sprite.visible for film_strip_sprite in editor.film_strip_sprites.values()
        ] == [False, True, True]
        assert editor.film_strips['walk'].rect.y == 0
        assert editor.film_strips['jump'].rect.y == 145 - 19

    def test_strip_without_a_sprite_is_not_shown(self):
        """A strip widget with no sprite is not positioned."""
        editor = _EditorStandIn()
        editor.film_strips = {'idle': _StripWidgetStandIn()}
        coordinator = FilmStripCoordinator(editor)

        coordinator.update_film_strip_visibility()

        assert editor.film_strips['idle'].dirty_marks == 0


class TestUpdateScrollArrows:
    """update_scroll_arrows shows the up arrow only when scrolled down."""

    def test_arrow_visibility_follows_the_scroll_offset(self):
        """The arrow shows at offset 1 and hides again at offset 0."""
        editor = _editor_with_strip_stand_ins(frame_counts={'idle': 1})
        editor.scroll_up_arrow = SimpleNamespace(visible=False, dirty=0)
        coordinator = FilmStripCoordinator(editor)

        editor.film_strip_scroll_offset = 1
        coordinator.update_scroll_arrows()
        shown_after_scrolling = editor.scroll_up_arrow.visible
        editor.film_strip_scroll_offset = 0
        coordinator.update_scroll_arrows()

        assert shown_after_scrolling is True
        assert editor.scroll_up_arrow.visible is False
        assert editor.scroll_up_arrow.dirty == 1

    def test_no_canvas_leaves_the_arrow_alone(self):
        """Without a canvas the arrow is not touched."""
        editor = _EditorStandIn()
        editor.scroll_up_arrow = SimpleNamespace(visible=False, dirty=0)
        editor.film_strip_scroll_offset = 3
        coordinator = FilmStripCoordinator(editor)

        coordinator.update_scroll_arrows()

        assert editor.scroll_up_arrow.visible is False


# ---------------------------------------------------------------------------
# Adding animations
# ---------------------------------------------------------------------------


class TestAddNewAnimation:
    """_add_new_animation adds a blank strip and selects it."""

    def test_no_canvas_adds_nothing(self):
        """Without a canvas nothing is added."""
        editor = _EditorStandIn()
        coordinator = FilmStripCoordinator(editor)

        coordinator._add_new_animation()

        assert editor.film_strips == {}

    def test_appended_animation_is_selected_and_undoable(self):
        """A new strip is added at the end, selected, scrolled to and undoable."""
        editor, coordinator = _editor_with_real_film_strips(
            frame_counts={'idle': 1, 'walk': 1},
            with_undo_history=True,
        )

        coordinator._add_new_animation()

        animations = editor.canvas.animated_sprite._animations
        assert list(animations) == ['idle', 'walk', 'strip_3']
        assert animations['strip_3'][0].pixels == [MAGENTA] * (FRAME_WIDTH * FRAME_HEIGHT)
        assert editor.selected_animation == 'strip_3'
        assert editor.selected_frame == 0
        assert editor.canvas.current_animation == 'strip_3'
        assert editor.film_strip_scroll_offset == 1
        assert 'strip_3' in editor.film_strips
        assert editor.undo_redo_manager.undo_stack[-1].animation_name == 'strip_3'

    def test_insert_after_index_places_the_animation(self):
        """insert_after_index=0 puts the new strip second."""
        editor, coordinator = _editor_with_real_film_strips(frame_counts={'idle': 1, 'walk': 1})

        coordinator._add_new_animation(insert_after_index=0)

        assert list(editor.canvas.animated_sprite._animations) == ['idle', 'strip_3', 'walk']

    def test_insert_after_index_past_the_end_appends(self):
        """An index past the last animation appends the new strip."""
        editor, coordinator = _editor_with_real_film_strips(frame_counts={'idle': 1})

        coordinator._add_new_animation(insert_after_index=5)

        assert list(editor.canvas.animated_sprite._animations) == ['idle', 'strip_2']
        assert editor.selected_animation == 'strip_2'


# ---------------------------------------------------------------------------
# Deleting animations
# ---------------------------------------------------------------------------


class TestDeleteAnimation:
    """_delete_animation removes an animation once confirmed."""

    def test_no_canvas_deletes_nothing(self):
        """Without a canvas the call does nothing."""
        editor = _EditorStandIn()
        coordinator = FilmStripCoordinator(editor)

        coordinator._delete_animation('idle', confirmed=True)

        assert editor.selected_animation is None

    def test_last_animation_is_kept(self):
        """The only animation cannot be deleted."""
        editor, coordinator = _editor_with_real_film_strips(frame_counts={'idle': 1})

        coordinator._delete_animation('idle', confirmed=True)

        assert list(editor.canvas.animated_sprite._animations) == ['idle']

    def test_unknown_animation_is_ignored(self):
        """A confirmed delete of a missing animation changes nothing."""
        editor, coordinator = _editor_with_real_film_strips(frame_counts={'idle': 1, 'walk': 1})

        coordinator._delete_animation('missing', confirmed=True)

        assert list(editor.canvas.animated_sprite._animations) == ['idle', 'walk']

    def test_unconfirmed_delete_asks_first(self, mocker):
        """Without confirmation the dialog is shown and nothing is deleted yet."""
        editor, coordinator = _editor_with_real_film_strips(frame_counts={'idle': 1, 'walk': 1})
        shown_confirmations = []
        mocker.patch.object(
            coordinator,
            '_show_delete_animation_confirmation',
            side_effect=shown_confirmations.append,
        )

        coordinator._delete_animation('walk')

        assert shown_confirmations == ['walk']
        assert list(editor.canvas.animated_sprite._animations) == ['idle', 'walk']

    def test_confirmed_delete_selects_the_previous_frame_and_rebuilds_strips(self):
        """With frame 2 selected, frame 1 of the first remaining animation is selected."""
        editor, coordinator = _editor_with_real_film_strips(
            frame_counts={'idle': 3, 'walk': 3},
            with_undo_history=True,
        )
        editor.selected_animation = 'walk'
        editor.selected_frame = 2

        coordinator._delete_animation('walk', confirmed=True)

        assert list(editor.canvas.animated_sprite._animations) == ['idle']
        assert editor.selected_animation == 'idle'
        assert list(editor.film_strips) == ['idle']
        assert ('idle', 1) in editor.canvas.shown_frames
        assert editor.undo_redo_manager.undo_stack[-1].animation_name == 'walk'
        # BUGS.md #99: rebuilding the strips reset the selection to frame 0 afterwards
        assert editor.selected_frame == 1
        assert (editor.canvas.current_animation, editor.canvas.current_frame) == ('idle', 1)

    def test_confirmed_delete_without_history_still_deletes(self):
        """An editor with no undo tracker still deletes the animation."""
        editor, coordinator = _editor_with_real_film_strips(frame_counts={'idle': 2, 'walk': 1})
        editor.selected_frame = 0

        coordinator._delete_animation('idle', confirmed=True)

        assert list(editor.canvas.animated_sprite._animations) == ['walk']
        assert editor.selected_animation == 'walk'
        assert editor.selected_frame == 0

    def test_select_after_deletion_clamps_to_the_last_frame(self):
        """A selected frame past the remaining animation's end is clamped."""
        editor, coordinator = _editor_with_real_film_strips(frame_counts={'idle': 2})
        editor.selected_frame = 5

        coordinator._select_animation_after_deletion(['idle'], 'walk')

        assert ('idle', 1) in editor.canvas.shown_frames
        assert editor.selected_frame == 1
        assert (editor.canvas.current_animation, editor.canvas.current_frame) == ('idle', 1)


class TestHandleNoRemainingAnimations:
    """_handle_no_remaining_animations clears the selection and fixes the scroll."""

    def test_few_strips_scroll_to_the_top(self):
        """Two or fewer strips left: the offset returns to 0 and widgets rebuild."""
        editor = _editor_with_strip_stand_ins(frame_counts={'idle': 1, 'walk': 1})
        editor.film_strip_sprites['no_widget'] = _strip_sprite(widget=None)
        editor.film_strip_scroll_offset = 3
        editor.selected_animation = 'idle'
        editor.selected_frame = 0
        coordinator = FilmStripCoordinator(editor)

        coordinator._handle_no_remaining_animations(['idle', 'walk'], ['idle', 'walk', 'x'], 2)

        assert editor.selected_animation is None
        assert editor.selected_frame is None
        assert editor.film_strip_scroll_offset == 0
        assert editor.film_strips['idle'].tab_creations == 1
        assert editor.film_strip_sprites['idle'].dirty == 1

    def test_deleting_the_last_strip_shows_the_previous_two(self):
        """Deleting the last of five strips scrolls to show the last two left."""
        remaining = ['a', 'b', 'c', 'd']
        editor = _editor_with_strip_stand_ins(frame_counts=dict.fromkeys(remaining, 1))
        coordinator = FilmStripCoordinator(editor)

        coordinator._handle_no_remaining_animations(remaining, [*remaining, 'e'], 4)

        assert editor.film_strip_scroll_offset == 2

    def test_deleting_a_middle_strip_shows_the_one_before(self):
        """Deleting the fourth of five strips scrolls to the third."""
        remaining = ['a', 'b', 'c', 'e']
        editor = _editor_with_strip_stand_ins(frame_counts=dict.fromkeys(remaining, 1))
        coordinator = FilmStripCoordinator(editor)

        coordinator._handle_no_remaining_animations(remaining, ['a', 'b', 'c', 'd', 'e'], 3)

        assert editor.film_strip_scroll_offset == 2


# ---------------------------------------------------------------------------
# Confirmation dialogs
# ---------------------------------------------------------------------------


def _captured_dialog_callbacks(dialog_class_mock):
    """Return the confirm and cancel callbacks a dialog was built with.

    Returns:
        tuple: (on_confirm_callback, on_cancel_callback).

    """
    keyword_arguments = dialog_class_mock.call_args.kwargs
    return keyword_arguments['on_confirm_callback'], keyword_arguments['on_cancel_callback']


def test_delete_animation_dialog_opens_from_a_new_coordinator(mocker):
    """An unconfirmed delete on a freshly built coordinator opens the dialog (BUGS.md #90)."""
    dialog_class_mock = mocker.patch('glitchygames.ui.dialogs.DeleteAnimationDialogScene')
    editor, coordinator = _editor_with_real_film_strips(frame_counts={'idle': 1, 'walk': 1})

    coordinator._delete_animation('walk')

    assert editor.next_scene is dialog_class_mock.return_value
    assert list(editor.canvas.animated_sprite._animations) == ['idle', 'walk']


def test_delete_frame_dialog_opens_from_a_new_coordinator(mocker):
    """Asking to delete a frame on a freshly built coordinator opens the dialog (BUGS.md #90)."""
    dialog_class_mock = mocker.patch('glitchygames.ui.dialogs.DeleteFrameDialogScene')
    editor, coordinator = _editor_with_real_film_strips(frame_counts={'walk': 2})

    coordinator._show_delete_frame_confirmation('walk', 1)

    assert editor.next_scene is dialog_class_mock.return_value
    assert len(editor.canvas.animated_sprite._animations['walk']) == 2


class TestDeleteAnimationConfirmation:
    """The delete animation dialog deletes on confirm and resets tabs on cancel."""

    def _open_dialog(self, mocker):
        """Open the dialog on an editor with two animations.

        Returns:
            tuple: (editor, dialog class mock).

        """
        dialog_class_mock = mocker.patch('glitchygames.ui.dialogs.DeleteAnimationDialogScene')
        editor, coordinator = _editor_with_real_film_strips(frame_counts={'idle': 1, 'walk': 1})
        editor.screenshot = pygame.Surface((8, 8))

        coordinator._show_delete_animation_confirmation('walk')

        return editor, dialog_class_mock

    def test_dialog_is_shown_over_the_screenshot(self, mocker):
        """The dialog names the animation, uses the screenshot and is the editor's next scene."""
        editor, dialog_class_mock = self._open_dialog(mocker)

        assert dialog_class_mock.call_args.kwargs['animation_name'] == 'walk'
        assert editor.next_scene is dialog_class_mock.return_value
        assert dialog_class_mock.return_value.background is editor.screenshot

    def test_confirm_deletes_the_animation(self, mocker):
        """Confirming deletes the animation."""
        editor, dialog_class_mock = self._open_dialog(mocker)
        on_confirm, _on_cancel = _captured_dialog_callbacks(dialog_class_mock)

        on_confirm()

        assert list(editor.canvas.animated_sprite._animations) == ['idle']

    def test_cancel_resets_the_tab_states(self, mocker):
        """Cancelling keeps the animation and resets every strip's tabs."""
        editor, dialog_class_mock = self._open_dialog(mocker)
        _on_confirm, on_cancel = _captured_dialog_callbacks(dialog_class_mock)
        widget = _StripWidgetStandIn()
        editor.film_strip_sprites = {
            'walk': _strip_sprite(widget=widget),
            'no_widget': _strip_sprite(widget=None),
        }

        on_cancel()

        assert widget.tab_resets == 1
        assert editor.film_strip_sprites['walk'].dirty == 1
        assert editor.film_strip_sprites['no_widget'].dirty == 0
        assert list(editor.canvas.animated_sprite._animations) == ['idle', 'walk']


class TestDeleteFrameConfirmation:
    """The delete frame dialog removes the frame on confirm and clears hover on cancel."""

    def _open_dialog(self, mocker):
        """Open the dialog for walk[1].

        Returns:
            tuple: (editor, strip widget, dialog class mock).

        """
        dialog_class_mock = mocker.patch('glitchygames.ui.dialogs.DeleteFrameDialogScene')
        editor = _editor_with_strip_stand_ins(frame_counts={'walk': 2})
        editor.film_strip_sprites['other'] = _strip_sprite(widget=None)
        coordinator = FilmStripCoordinator(editor)

        coordinator._show_delete_frame_confirmation('walk', 1)

        return editor, editor.film_strips['walk'], dialog_class_mock

    def test_dialog_is_shown(self, mocker):
        """The dialog names the frame and is the editor's next scene."""
        editor, _widget, dialog_class_mock = self._open_dialog(mocker)

        assert dialog_class_mock.call_args.kwargs['frame_index'] == 1
        assert editor.next_scene is dialog_class_mock.return_value

    def test_confirm_removes_the_frame(self, mocker):
        """Confirming asks the strip widget to remove the frame."""
        _editor, widget, dialog_class_mock = self._open_dialog(mocker)
        on_confirm, _on_cancel = _captured_dialog_callbacks(dialog_class_mock)

        on_confirm()

        assert widget.removed_frames == [('walk', 1)]

    def test_cancel_clears_the_removal_hover(self, mocker):
        """Cancelling clears the hovered removal button and redraws the strip."""
        editor, widget, dialog_class_mock = self._open_dialog(mocker)
        _on_confirm, on_cancel = _captured_dialog_callbacks(dialog_class_mock)
        widget.hovered_removal_button = 1

        on_cancel()

        assert widget.hovered_removal_button is None
        assert editor.film_strip_sprites['walk'].dirty == 1
        assert widget.removed_frames == []

    def test_callbacks_do_nothing_for_a_strip_without_a_widget(self, mocker):
        """With the strip's widget gone, confirm and cancel change nothing."""
        editor, widget, dialog_class_mock = self._open_dialog(mocker)
        on_confirm, on_cancel = _captured_dialog_callbacks(dialog_class_mock)
        editor.film_strip_sprites['walk'].film_strip_widget = None
        widget.hovered_removal_button = 1

        on_confirm()
        on_cancel()

        assert widget.removed_frames == []
        assert widget.hovered_removal_button == 1

    def test_callbacks_do_nothing_for_a_removed_strip(self, mocker):
        """With the strip gone, confirm and cancel change nothing."""
        editor, widget, dialog_class_mock = self._open_dialog(mocker)
        on_confirm, on_cancel = _captured_dialog_callbacks(dialog_class_mock)
        del editor.film_strip_sprites['walk']

        on_confirm()
        on_cancel()

        assert widget.removed_frames == []


# ---------------------------------------------------------------------------
# Drag scrolling
# ---------------------------------------------------------------------------


class TestFilmStripDragScroll:
    """handle_film_strip_drag_scroll scrolls one strip per 100 pixels dragged."""

    def test_drag_without_start_offset_does_nothing(self):
        """A drag with no recorded start offset leaves the scroll alone."""
        editor = _editor_with_strip_stand_ins(frame_counts={'a': 1, 'b': 1, 'c': 1})
        editor.is_dragging_film_strips = True
        editor.film_strip_drag_start_y = 0
        coordinator = FilmStripCoordinator(editor)

        coordinator.handle_film_strip_drag_scroll(250)

        assert editor.film_strip_scroll_offset == 0

    def test_drag_without_canvas_sprite_is_not_clamped(self):
        """Without a canvas sprite the new offset is used unclamped."""
        editor = _EditorStandIn()
        editor.is_dragging_film_strips = True
        editor.film_strip_drag_start_y = 0
        editor.film_strip_drag_start_offset = 0
        coordinator = FilmStripCoordinator(editor)

        coordinator.handle_film_strip_drag_scroll(350)

        assert editor.film_strip_scroll_offset == 3

    def test_small_drag_keeps_the_offset(self):
        """A drag shorter than one strip does not scroll."""
        editor = _editor_with_strip_stand_ins(frame_counts={'a': 1, 'b': 1, 'c': 1})
        editor.is_dragging_film_strips = True
        editor.film_strip_drag_start_y = 100
        editor.film_strip_drag_start_offset = 0
        coordinator = FilmStripCoordinator(editor)

        coordinator.handle_film_strip_drag_scroll(150)

        assert editor.film_strip_scroll_offset == 0


# ---------------------------------------------------------------------------
# Loading sprites
# ---------------------------------------------------------------------------


class TestOnSpriteLoaded:
    """on_sprite_loaded replaces the strips with ones for the loaded sprite."""

    def test_loaded_sprite_replaces_strips_and_keeps_active_controllers(self):
        """Old strips go, new ones come, and active controller selections are kept."""
        editor, coordinator = _editor_with_real_film_strips(frame_counts={'old': 1})
        old_strip_sprite = editor.film_strip_sprites['old']
        editor.controller_selections = {
            0: SimpleNamespace(is_active=lambda: True, get_selection=lambda: ('old', 0)),
            1: SimpleNamespace(is_active=lambda: False, get_selection=lambda: ('old', 0)),
        }
        editor.canvas.pixels = None
        loaded_sprite = _make_animated_sprite(frame_counts={'run': 2, 'jump': 1})

        coordinator.on_sprite_loaded(loaded_sprite)

        assert list(editor.film_strips) == ['run', 'jump']
        assert not old_strip_sprite.alive()
        assert editor.canvas.animated_sprite is loaded_sprite
        assert editor.canvas.resize_checks == [loaded_sprite]
        assert editor.canvas.canvas_interface.current_frame == ('run', 0)
        assert editor.canvas.pixels == [MAGENTA] * (FRAME_WIDTH * FRAME_HEIGHT)
        assert editor.selected_animation == 'run'
        assert editor.selected_frame == 0
        assert editor.controller_handler.reinitialized_with[-1] == {0: ('old', 0)}

    def test_sprite_without_animations_keeps_nothing(self):
        """A loaded sprite with no animations clears the old strips and makes none."""
        editor, coordinator = _editor_with_real_film_strips(frame_counts={'old': 1})
        empty_sprite = SimpleNamespace(_animations={})

        coordinator.on_sprite_loaded(empty_sprite)

        assert editor.film_strips == {}
        assert editor.canvas.animated_sprite is not empty_sprite

    def test_sprite_without_animation_attribute_is_ignored(self):
        """A loaded object with no animations attribute and no truth makes no strips."""
        editor = _EditorStandIn()
        coordinator = FilmStripCoordinator(editor)

        coordinator.on_sprite_loaded(None)

        assert editor.film_strips == {}

    def test_loading_without_a_canvas_still_makes_strips_state(self):
        """With no canvas the strips cannot be built, but the selection is set."""
        editor = _EditorStandIn()
        coordinator = FilmStripCoordinator(editor)
        loaded_sprite = _make_animated_sprite(frame_counts={'run': 1})

        coordinator.on_sprite_loaded(loaded_sprite)

        assert editor.film_strips == {}
        assert editor.selected_animation == 'run'


# ---------------------------------------------------------------------------
# Frame selection
# ---------------------------------------------------------------------------


class TestOnFilmStripFrameSelected:
    """on_film_strip_frame_selected makes the clicked frame the selection."""

    def test_selection_without_a_canvas(self):
        """Without a canvas or strips, the selection is still recorded."""
        editor = _EditorStandIn()
        editor.film_strips = {}
        widget = _StripWidgetStandIn()
        coordinator = FilmStripCoordinator(editor)

        coordinator.on_film_strip_frame_selected(widget, 'walk', 2)

        assert editor.selected_animation == 'walk'
        assert editor.selected_frame == 2
        assert coordinator.selected_strip is widget

    def test_unregistered_widget_is_still_selected(self):
        """A widget not in the strips selects its frame on the canvas."""
        editor = _editor_with_strip_stand_ins(frame_counts={'idle': 1, 'walk': 3})
        stray_widget = _StripWidgetStandIn()
        coordinator = FilmStripCoordinator(editor)

        coordinator.on_film_strip_frame_selected(stray_widget, 'walk', 2)

        assert editor.canvas.current_frame == 2
        assert editor.film_strips['walk'].is_selected is True
        assert editor.film_strips['walk'].selected_frame == 2


# ---------------------------------------------------------------------------
# Renaming
# ---------------------------------------------------------------------------


class TestOnAnimationRename:
    """on_animation_rename renames the animation everywhere it is keyed."""

    def test_rename_moves_strips_selection_and_history(self):
        """The sprite, strips, sprites, selection and undo history follow the new name."""
        editor, coordinator = _editor_with_real_film_strips(
            frame_counts={'idle': 1, 'walk': 2},
            with_undo_history=True,
        )
        editor.selected_animation = 'walk'
        walk_widget = editor.film_strips['walk']

        coordinator.on_animation_rename('walk', 'stroll')

        assert list(editor.canvas.animated_sprite._animations) == ['idle', 'stroll']
        assert list(editor.film_strips) == ['idle', 'stroll']
        assert editor.film_strips['stroll'] is walk_widget
        assert 'stroll' in editor.film_strip_sprites
        assert list(walk_widget.animated_sprite._animations) == ['stroll']
        assert walk_widget.animated_sprite.frame_manager.current_animation == 'stroll'
        assert editor.selected_animation == 'stroll'
        assert editor.film_strip_sprites['stroll'].rect.size == walk_widget.rect.size
        assert editor.undo_redo_manager.undo_stack[-1].new_name == 'stroll'

    def test_rename_onto_an_existing_animation_is_refused(self):
        """Renaming onto a taken name keeps both animations."""
        editor, coordinator = _editor_with_real_film_strips(frame_counts={'idle': 1, 'walk': 2})

        coordinator.on_animation_rename('walk', 'idle')

        assert list(editor.canvas.animated_sprite._animations) == ['idle', 'walk']
        assert len(editor.canvas.animated_sprite._animations['walk']) == 2

    def test_rename_of_a_missing_animation_changes_nothing(self):
        """Renaming an unknown animation keeps the strips."""
        editor, coordinator = _editor_with_real_film_strips(frame_counts={'idle': 1})

        coordinator.on_animation_rename('missing', 'other')

        assert list(editor.film_strips) == ['idle']

    def test_rename_without_a_canvas_only_redraws(self):
        """With no canvas sprite there is nothing to rename."""
        editor = _EditorStandIn()
        widget = _StripWidgetStandIn()
        editor.film_strips = {'walk': widget}
        coordinator = FilmStripCoordinator(editor)

        coordinator.on_animation_rename('walk', 'stroll')

        assert list(editor.film_strips) == ['walk']
        assert widget.dirty_marks == 1

    def test_rename_of_a_strip_not_in_the_dictionary(self):
        """Renaming with no strip for the animation still renames the sprite."""
        editor = _EditorStandIn(animated_sprite=_make_animated_sprite(frame_counts={'walk': 1}))
        coordinator = FilmStripCoordinator(editor)

        coordinator._rename_in_film_strips_dict('walk', 'stroll')
        coordinator.on_animation_rename('walk', 'stroll')

        assert list(editor.canvas.animated_sprite._animations) == ['stroll']
        assert editor.film_strips == {}

    def test_widget_internals_follow_only_a_matching_sprite(self):
        """A widget sprite without the old name, or without an order, is handled."""
        coordinator = FilmStripCoordinator(_EditorStandIn())
        unrelated_widget = _StripWidgetStandIn(
            animated_sprite=_make_animated_sprite(frame_counts={'other': 1}),
        )
        frames = [_make_frame()]
        # Never loaded from a file: it keeps no animation order of its own
        unordered_sprite = AnimatedSprite()
        unordered_sprite.add_animation('walk', frames)
        assert not unordered_sprite.has_own_animation_order
        unordered_widget = _StripWidgetStandIn(animated_sprite=unordered_sprite)
        other_current_sprite = _make_animated_sprite(frame_counts={'idle': 1, 'walk': 1})
        other_current_widget = _StripWidgetStandIn(animated_sprite=other_current_sprite)

        coordinator._rename_film_strip_widget_internals(unrelated_widget, 'walk', 'stroll')
        coordinator._rename_film_strip_widget_internals(unordered_widget, 'walk', 'stroll')
        coordinator._rename_film_strip_widget_internals(other_current_widget, 'walk', 'stroll')

        assert list(unrelated_widget.animated_sprite._animations) == ['other']
        assert unordered_sprite._animations == {'stroll': frames}
        assert not unordered_sprite.has_own_animation_order
        assert other_current_sprite.frame_manager.current_animation == 'idle'

    def test_layout_failure_after_rename_is_logged(self):
        """A widget whose layout update fails is still marked dirty."""

        class _BrokenLayoutWidget(_StripWidgetStandIn):
            """Widget whose layout cannot be updated."""

            def update_layout(self):
                """Fail like a widget with missing layout data.

                Raises:
                    KeyError: Always.

                """
                missing_key = 'layout'
                raise KeyError(missing_key)

        editor = _EditorStandIn()
        widget = _BrokenLayoutWidget()
        coordinator = FilmStripCoordinator(editor)

        coordinator._update_film_strip_layout_after_rename(widget, 'stroll')

        assert widget.dirty_marks == 1

    def test_rename_tracking_needs_a_tracker(self):
        """With no tracker, a rename records nothing and does not fail."""
        editor = _EditorStandIn()
        coordinator = FilmStripCoordinator(editor)

        coordinator._track_animation_rename_for_undo(old_name='walk', new_name='stroll')

        assert not hasattr(editor, 'film_strip_operation_tracker')

    def test_mark_all_dirty_reaches_strip_sprites_and_their_animations(self):
        """Each strip, its sprite and its animated sprite are marked for redraw."""
        animated_sprite = _make_animated_sprite(frame_counts={'walk': 1})
        animated_sprite.dirty = 0
        editor = _EditorStandIn()
        widget = _StripWidgetStandIn(animated_sprite=animated_sprite)
        editor.film_strips = {'walk': widget, 'loose': _StripWidgetStandIn()}
        editor.film_strip_sprites = {'walk': _strip_sprite(widget=widget)}
        coordinator = FilmStripCoordinator(editor)

        coordinator._mark_all_film_strips_dirty()

        assert widget.dirty_marks == 1
        assert editor.film_strip_sprites['walk'].dirty == 1
        assert animated_sprite.dirty == 1
        assert editor.film_strips['loose'].dirty_marks == 1


# ---------------------------------------------------------------------------
# Frame insertion and removal notifications
# ---------------------------------------------------------------------------


class TestOnFrameInserted:
    """on_frame_inserted selects the new frame in its animation."""

    def test_new_frame_is_selected_in_its_strip(self):
        """The current animation's strip selects the new frame; others only redraw."""
        animated_sprite = _make_animated_sprite(frame_counts={'idle': 1, 'walk': 3})
        editor = _EditorStandIn(animated_sprite=animated_sprite)
        walk_animation_sprite = _make_animated_sprite(frame_counts={'walk': 3})
        walk_animation_sprite.dirty = 0
        walk_widget = _StripWidgetStandIn(animated_sprite=walk_animation_sprite)
        idle_widget = _StripWidgetStandIn()
        editor.film_strips = {'idle': idle_widget, 'walk': walk_widget}
        editor.film_strip_sprites = {'walk': _strip_sprite(widget=walk_widget)}
        editor.selected_animation = 'walk'
        coordinator = FilmStripCoordinator(editor)

        coordinator.on_frame_inserted('walk', 2)

        assert editor.canvas.current_frame == 2
        assert editor.selected_frame == 2
        assert walk_widget.selected_frame == 2
        assert idle_widget.selected_frame == 0
        assert idle_widget.dirty_marks == 1
        assert editor.film_strip_sprites['walk'].dirty == 1
        assert walk_animation_sprite.dirty == 1

    def test_insert_in_another_animation_keeps_the_canvas(self):
        """A frame added to an unselected animation does not move the canvas."""
        editor = _EditorStandIn(animated_sprite=_make_animated_sprite(frame_counts={'idle': 2}))
        editor.selected_animation = 'other'
        editor.film_strips = {}
        coordinator = FilmStripCoordinator(editor)

        coordinator.on_frame_inserted('idle', 1)

        assert editor.canvas.current_frame == 0


class TestOnFrameRemoved:
    """on_frame_removed moves the selection back one frame."""

    def test_selection_moves_back_and_strip_follows(self):
        """Removing frame 1 with frame 2 selected selects frame 1."""
        editor = _EditorStandIn(animated_sprite=_make_animated_sprite(frame_counts={'walk': 2}))
        walk_animation_sprite = _make_animated_sprite(frame_counts={'walk': 2})
        walk_animation_sprite.dirty = 0
        walk_widget = _StripWidgetStandIn(animated_sprite=walk_animation_sprite)
        idle_widget = _StripWidgetStandIn()
        editor.film_strips = {'walk': walk_widget, 'idle': idle_widget}
        editor.film_strip_sprites = {'walk': _strip_sprite(widget=walk_widget)}
        editor.selected_animation = 'walk'
        editor.selected_frame = 2
        coordinator = FilmStripCoordinator(editor)

        coordinator.on_frame_removed('walk', 1)

        assert editor.selected_frame == 1
        assert editor.canvas.current_frame == 1
        assert walk_widget.selected_frame == 1
        assert idle_widget.dirty_marks == 1
        assert editor.film_strip_sprites['walk'].dirty == 1
        assert walk_animation_sprite.dirty == 1

    def test_selection_past_the_end_is_clamped(self):
        """A selection still past the end after the step back is clamped."""
        editor = _EditorStandIn(animated_sprite=_make_animated_sprite(frame_counts={'walk': 2}))
        editor.selected_animation = 'walk'
        editor.selected_frame = 5
        coordinator = FilmStripCoordinator(editor)

        coordinator.on_frame_removed('walk', 0)

        assert editor.selected_frame == 1

    def test_strip_falls_back_to_frame_zero_without_a_selection(self):
        """A strip gets frame 0 when the editor has no selected frame."""
        editor = _EditorStandIn()
        widget = _StripWidgetStandIn()
        widget.selected_frame = 4
        editor.film_strips = {'walk': widget}
        editor.selected_animation = 'walk'
        editor.selected_frame = None
        coordinator = FilmStripCoordinator(editor)

        coordinator.on_frame_removed('walk', 0)

        assert widget.selected_frame == 0

    def test_selection_at_frame_zero_stays_without_a_canvas(self):
        """Removing frame 0 while it is selected keeps frame 0."""
        editor = _EditorStandIn()
        editor.film_strips = {}
        editor.selected_animation = 'walk'
        editor.selected_frame = 0
        coordinator = FilmStripCoordinator(editor)

        coordinator.on_frame_removed('walk', 0)

        assert editor.selected_frame == 0

    def test_canvas_error_falls_back_to_frame_zero(self):
        """If the canvas cannot show the adjusted frame, frame 0 is shown."""

        class _CanvasRefusingFrameOne(_CanvasStandIn):
            """Canvas that fails to show frame 1."""

            def show_frame(self, animation, frame):
                """Fail for frame 1, like a stale canvas.

                Raises:
                    KeyError: For frame 1.

                """
                if frame == 1:
                    raise KeyError(frame)
                super().show_frame(animation, frame)

        animated_sprite = _make_animated_sprite(frame_counts={'walk': 3})
        editor = _EditorStandIn()
        editor.canvas = _CanvasRefusingFrameOne(animated_sprite=animated_sprite)
        editor.canvas.current_frame = 2
        editor.selected_animation = 'walk'
        editor.selected_frame = 2
        coordinator = FilmStripCoordinator(editor)

        coordinator.on_frame_removed('walk', 1)

        assert editor.selected_frame == 0
        assert editor.canvas.current_frame == 0

    def test_canvas_error_with_an_empty_animation_shows_nothing(self):
        """The fallback skips showing frame 0 of an animation with no frames."""

        class _CanvasAlwaysFailing(_CanvasStandIn):
            """Canvas that cannot show any frame."""

            def show_frame(self, animation, frame):
                """Fail always.

                Raises:
                    IndexError: Always.

                """
                raise IndexError(frame)

        animated_sprite = _make_animated_sprite(frame_counts={'walk': 1})
        animated_sprite._animations['walk'] = []
        editor = _EditorStandIn()
        editor.canvas = _CanvasAlwaysFailing(animated_sprite=animated_sprite)
        editor.selected_animation = 'walk'
        editor.selected_frame = 1
        coordinator = FilmStripCoordinator(editor)

        coordinator.on_frame_removed('walk', 0)

        assert editor.selected_frame == 0


# ---------------------------------------------------------------------------
# Copy and paste
# ---------------------------------------------------------------------------


class TestCopyAndPaste:
    """_copy_current_frame and _paste_to_current_frame use the active strip."""

    @pytest.mark.parametrize('method_name', ['_copy_current_frame', '_paste_to_current_frame'])
    def test_no_strips_reports_failure(self, method_name):
        """Without strips nothing can be copied or pasted."""
        coordinator = FilmStripCoordinator(_EditorStandIn())

        assert getattr(coordinator, method_name)() is False

    @pytest.mark.parametrize('method_name', ['_copy_current_frame', '_paste_to_current_frame'])
    def test_no_selected_animation_reports_failure(self, method_name):
        """Without a selected animation there is no active strip."""
        editor = _EditorStandIn()
        editor.film_strips = {'walk': _StripWidgetStandIn()}
        coordinator = FilmStripCoordinator(editor)

        assert getattr(coordinator, method_name)() is False

    @pytest.mark.parametrize('method_name', ['_copy_current_frame', '_paste_to_current_frame'])
    def test_no_matching_strip_reports_failure(self, method_name):
        """With no strip showing the selected animation, nothing happens."""
        editor = _EditorStandIn()
        widget = _StripWidgetStandIn()
        widget.current_animation = 'idle'
        editor.film_strips = {'idle': widget}
        editor.selected_animation = 'walk'
        coordinator = FilmStripCoordinator(editor)

        assert getattr(coordinator, method_name)() is False

    def test_active_strip_result_is_returned(self):
        """The active strip's copy and paste results are passed back."""
        editor = _EditorStandIn()
        idle_widget = _StripWidgetStandIn()
        idle_widget.current_animation = 'idle'
        walk_widget = _StripWidgetStandIn(copy_result=True, paste_result=False)
        walk_widget.current_animation = 'walk'
        editor.film_strips = {'idle': idle_widget, 'walk': walk_widget}
        editor.selected_animation = 'walk'
        coordinator = FilmStripCoordinator(editor)

        assert coordinator._copy_current_frame() is True
        assert coordinator._paste_to_current_frame() is False


# ---------------------------------------------------------------------------
# Switching strips and scrolling
# ---------------------------------------------------------------------------


class TestSwitchToFilmStrip:
    """switch_to_film_strip deselects the old strip and selects the new one."""

    def test_switch_moves_the_selection(self):
        """The previous strip is cleared and the new one shows the frame."""
        editor = _editor_with_strip_stand_ins(frame_counts={'idle': 1, 'walk': 3})
        old_sprite = _make_animated_sprite(frame_counts={'idle': 1})
        old_sprite.dirty = 0
        new_sprite = _make_animated_sprite(frame_counts={'walk': 3})
        new_sprite.dirty = 0
        editor.film_strips['idle'].animated_sprite = old_sprite
        editor.film_strips['walk'].animated_sprite = new_sprite
        coordinator = FilmStripCoordinator(editor)
        coordinator.selected_strip = editor.film_strips['idle']
        coordinator.selected_strip.is_selected = True

        coordinator.switch_to_film_strip('walk', 2)

        assert editor.film_strips['idle'].is_selected is False
        assert not editor.film_strips['idle'].current_animation
        assert editor.film_strip_sprites['idle'].dirty == 1
        assert old_sprite.dirty == 1
        assert editor.film_strips['walk'].is_selected is True
        assert editor.film_strips['walk'].current_frame == 2
        assert editor.film_strip_sprites['walk'].dirty == 1
        assert new_sprite.dirty == 1
        assert editor.selected_animation == 'walk'
        assert editor.selected_frame == 2
        assert editor.canvas.current_frame == 2
        assert coordinator.selected_strip is editor.film_strips['walk']

    def test_switch_to_a_missing_strip_only_deselects(self):
        """A missing strip leaves nothing selected and the selection unchanged."""
        editor = _EditorStandIn()
        old_widget = _StripWidgetStandIn()
        editor.film_strips = {'idle': old_widget}
        editor.film_strip_sprites = {'other': _strip_sprite(widget=_StripWidgetStandIn())}
        coordinator = FilmStripCoordinator(editor)
        coordinator.selected_strip = old_widget

        coordinator.switch_to_film_strip('missing')

        assert old_widget.is_selected is False
        assert editor.selected_animation is None
        assert editor.film_strip_sprites['other'].dirty == 0

    def test_switch_without_a_canvas_or_sprites(self):
        """Without a canvas or strip sprites the strip is still selected."""
        editor = _EditorStandIn()
        widget = _StripWidgetStandIn()
        editor.film_strips = {'walk': widget}
        del editor.film_strip_sprites
        coordinator = FilmStripCoordinator(editor)
        coordinator.selected_strip = _StripWidgetStandIn()

        coordinator.switch_to_film_strip('walk', 1)

        assert widget.is_selected is True
        assert editor.selected_frame == 1


class TestScrollToCurrentAnimation:
    """scroll_to_current_animation brings the canvas animation into view."""

    def test_animation_above_the_view_scrolls_up(self):
        """An animation above the visible strips scrolls up to it."""
        editor = _editor_with_strip_stand_ins(frame_counts={'a': 1, 'b': 1, 'c': 1, 'd': 1})
        editor.film_strip_scroll_offset = 2
        editor.canvas.current_animation = 'a'
        coordinator = FilmStripCoordinator(editor)

        coordinator.scroll_to_current_animation()

        assert editor.film_strip_scroll_offset == 0
        assert editor.selected_animation == 'a'
        assert editor.film_strips['a'].current_animation == 'a'
        assert not editor.film_strips['b'].current_animation

    def test_animation_below_the_view_scrolls_down(self):
        """An animation below the visible strips scrolls down to show it last."""
        editor = _editor_with_strip_stand_ins(frame_counts={'a': 1, 'b': 1, 'c': 1, 'd': 1})
        editor.canvas.current_animation = 'd'
        coordinator = FilmStripCoordinator(editor)

        coordinator.scroll_to_current_animation()

        assert editor.film_strip_scroll_offset == 2

    def test_visible_animation_keeps_the_scroll(self):
        """An already visible animation does not scroll."""
        editor = _editor_with_strip_stand_ins(frame_counts={'a': 1, 'b': 1, 'c': 1})
        editor.canvas.current_animation = 'b'
        coordinator = FilmStripCoordinator(editor)

        coordinator.scroll_to_current_animation()

        assert editor.film_strip_scroll_offset == 0
        assert editor.selected_animation is None

    @pytest.mark.parametrize('current_animation', ['', 'missing'])
    def test_no_or_unknown_animation_keeps_the_scroll(self, current_animation):
        """With no current animation, or one not in the sprite, nothing scrolls."""
        editor = _editor_with_strip_stand_ins(frame_counts={'a': 1, 'b': 1, 'c': 1})
        editor.film_strip_scroll_offset = 1
        editor.canvas.current_animation = current_animation
        coordinator = FilmStripCoordinator(editor)

        coordinator.scroll_to_current_animation()

        assert editor.film_strip_scroll_offset == 1

    def test_no_canvas_keeps_the_scroll(self):
        """Without a canvas nothing scrolls."""
        editor = _EditorStandIn()
        editor.film_strip_scroll_offset = 1
        coordinator = FilmStripCoordinator(editor)

        coordinator.scroll_to_current_animation()

        assert editor.film_strip_scroll_offset == 1


class TestScrollUpAndDown:
    """scroll_film_strips_up and scroll_film_strips_down move one strip."""

    def test_scroll_down_then_up(self):
        """Down moves to the last page and stops; up returns to the top and stops."""
        editor = _editor_with_strip_stand_ins(frame_counts={'a': 1, 'b': 1, 'c': 1})
        coordinator = FilmStripCoordinator(editor)

        coordinator.scroll_film_strips_down()
        coordinator.scroll_film_strips_down()
        offset_after_scrolling_down = editor.film_strip_scroll_offset
        coordinator.scroll_film_strips_up()
        coordinator.scroll_film_strips_up()

        assert offset_after_scrolling_down == 1
        assert editor.film_strip_scroll_offset == 0

    def test_scroll_down_without_a_canvas_does_nothing(self):
        """Without a canvas there is nothing to scroll to."""
        editor = _EditorStandIn()
        coordinator = FilmStripCoordinator(editor)

        coordinator.scroll_film_strips_down()

        assert editor.film_strip_scroll_offset == 0


class TestSelectVisibleFilmStrips:
    """The first and last visible strips can be selected at frame 0."""

    @pytest.mark.parametrize(
        ('method_name', 'expected_animation'),
        [('_select_first_visible_film_strip', 'b'), ('_select_last_visible_film_strip', 'c')],
    )
    def test_visible_strip_is_selected(self, method_name, expected_animation):
        """At offset 1 the first visible strip is b and the last is c."""
        editor = _editor_with_strip_stand_ins(frame_counts={'a': 1, 'b': 1, 'c': 1})
        editor.film_strip_scroll_offset = 1
        coordinator = FilmStripCoordinator(editor)

        getattr(coordinator, method_name)()

        assert editor.selected_animation == expected_animation
        assert editor.selected_frame == 0
        assert editor.film_strips[expected_animation].current_animation == expected_animation
        assert editor.film_strips['a'].dirty_marks == 1

    @pytest.mark.parametrize(
        'method_name',
        ['_select_first_visible_film_strip', '_select_last_visible_film_strip'],
    )
    def test_strip_order_is_used_without_a_canvas(self, method_name):
        """Without a canvas the strip order is used, and a missing strip is skipped."""
        editor = _EditorStandIn()
        editor.film_strips = {'only': _StripWidgetStandIn()}
        coordinator = FilmStripCoordinator(editor)

        getattr(coordinator, method_name)()

        assert editor.selected_animation == 'only'

    @pytest.mark.parametrize(
        'method_name',
        ['_select_first_visible_film_strip', '_select_last_visible_film_strip'],
    )
    def test_offset_past_the_end_selects_nothing(self, method_name):
        """A scroll offset past every strip selects nothing."""
        editor = _editor_with_strip_stand_ins(frame_counts={'a': 1})
        editor.film_strip_scroll_offset = 4
        coordinator = FilmStripCoordinator(editor)

        getattr(coordinator, method_name)()

        assert editor.selected_animation is None

    @pytest.mark.parametrize(
        'method_name',
        ['_select_first_visible_film_strip', '_select_last_visible_film_strip'],
    )
    def test_animation_without_a_strip_is_selected_on_the_canvas(self, method_name):
        """An animation with no strip widget is still selected."""
        editor = _EditorStandIn(animated_sprite=_make_animated_sprite(frame_counts={'a': 1}))
        editor.film_strips = {'other': _StripWidgetStandIn()}
        coordinator = FilmStripCoordinator(editor)

        getattr(coordinator, method_name)()

        assert editor.selected_animation == 'a'
        assert editor.canvas.current_animation == 'a'

    @pytest.mark.parametrize(
        'method_name',
        ['_select_first_visible_film_strip', '_select_last_visible_film_strip'],
    )
    def test_no_strips_selects_nothing(self, method_name):
        """Without strips nothing is selected."""
        editor = _EditorStandIn()
        coordinator = FilmStripCoordinator(editor)

        getattr(coordinator, method_name)()

        assert editor.selected_animation is None


class TestNavigateFrame:
    """_navigate_frame steps through frames with wrapping."""

    def test_animation_without_frames_does_not_move(self):
        """An animation with no frames keeps the selection."""
        animated_sprite = _make_animated_sprite(frame_counts={'walk': 1})
        animated_sprite._animations['walk'] = []
        editor = _EditorStandIn(animated_sprite=animated_sprite)
        editor.selected_frame = 0
        coordinator = FilmStripCoordinator(editor)

        coordinator._navigate_frame(1)

        assert editor.selected_animation is None

    def test_navigation_without_strips_still_moves(self):
        """Without strips or strip sprites the canvas still moves to the next frame."""
        editor = _EditorStandIn(animated_sprite=_make_animated_sprite(frame_counts={'walk': 3}))
        editor.selected_frame = 2
        del editor.film_strips
        del editor.film_strip_sprites
        coordinator = FilmStripCoordinator(editor)

        coordinator._navigate_frame(1)

        assert editor.selected_frame == 0
        assert editor.canvas.current_frame == 0


# ---------------------------------------------------------------------------
# Display updates
# ---------------------------------------------------------------------------


class TestUpdateFilmStripsForFrame:
    """update_film_strips_for_frame marks the visible strips for redraw."""

    def test_unknown_animation_still_redraws_visible_sprites(self):
        """An animation with no strip leaves strips alone but redraws visible sprites."""
        editor = _editor_with_strip_stand_ins(frame_counts={'idle': 1})
        editor.film_strip_sprites['hidden'] = _strip_sprite(visible=False)
        coordinator = FilmStripCoordinator(editor)

        coordinator.update_film_strips_for_frame('missing', 3)

        assert editor.film_strips['idle'].current_frame == 0
        assert editor.film_strip_sprites['idle'].dirty == 1
        assert editor.film_strip_sprites['hidden'].dirty == 0

    def test_known_animation_without_strip_sprites(self):
        """The strip follows the frame even with no strip sprites."""

        class _ScrollingWidget(_StripWidgetStandIn):
            """Widget that remembers the frame it scrolled to."""

            def update_scroll_for_frame(self, frame):
                """Remember the frame."""
                self.scrolled_to = frame

        editor = _EditorStandIn()
        widget = _ScrollingWidget()
        editor.film_strips = {'idle': widget}
        coordinator = FilmStripCoordinator(editor)

        coordinator.update_film_strips_for_frame('idle', 2)

        assert widget.current_frame == 2
        assert widget.scrolled_to == 2


class TestHiddenStripsAreNotUpdated:
    """Pixel, sprite and timing updates skip hidden strips."""

    def _editor_with_hidden_strip(self):
        """Create an editor with one visible and one hidden strip.

        Returns:
            _EditorStandIn: The editor.

        """
        editor = _editor_with_strip_stand_ins(frame_counts={'shown': 1, 'hidden': 1})
        editor.film_strip_sprites['hidden'].visible = False
        return editor

    def test_pixel_update_skips_hidden_strips(self):
        """Only the visible strip is marked dirty."""
        editor = self._editor_with_hidden_strip()
        coordinator = FilmStripCoordinator(editor)

        coordinator._update_film_strips_for_pixel_update()

        assert editor.film_strips['shown'].dirty_marks == 1
        assert editor.film_strips['hidden'].dirty_marks == 0

    def test_sprite_update_skips_hidden_strips(self):
        """Only the visible strip's layout is updated."""
        editor = self._editor_with_hidden_strip()
        coordinator = FilmStripCoordinator(editor)

        coordinator.update_film_strips_for_animated_sprite_update()

        assert editor.film_strips['shown'].layout_updates == 1
        assert editor.film_strips['hidden'].layout_updates == 0

    def test_timing_update_skips_hidden_strips(self):
        """Only the visible strip's animations advance, by the editor's dt."""
        editor = self._editor_with_hidden_strip()
        editor.film_strips['plain'] = SimpleNamespace()
        coordinator = FilmStripCoordinator(editor)

        coordinator.update_film_strip_animation_timing()

        assert editor.film_strips['shown'].animation_updates == [editor.dt]
        assert editor.film_strips['hidden'].animation_updates == []

    def test_timing_update_without_strips_does_nothing(self):
        """Without strips there is nothing to update."""
        editor = _EditorStandIn()
        coordinator = FilmStripCoordinator(editor)

        coordinator.update_film_strip_animation_timing()

        assert editor.film_strips == {}


class TestUpdateFilmStripSelection:
    """_update_film_strip_selection needs a canvas."""

    def test_no_canvas_changes_nothing(self):
        """Without a canvas no strip changes."""
        editor = _EditorStandIn()
        widget = _StripWidgetStandIn()
        widget.current_animation = 'walk'
        editor.film_strips = {'walk': widget}
        coordinator = FilmStripCoordinator(editor)

        coordinator._update_film_strip_selection()

        assert widget.current_animation == 'walk'


class TestClearFilmStripsForNewCanvas:
    """clear_film_strips_for_new_canvas removes old strips from their groups."""

    def test_old_strips_leave_their_groups_and_new_ones_are_made(self):
        """The old strip sprite is removed from all groups and a new strip is built."""
        editor, coordinator = _editor_with_real_film_strips(frame_counts={'idle': 1})
        old_strip_sprite = editor.film_strip_sprites['idle']
        groupless_sprite = _strip_sprite()
        groupless_sprite.groups = list
        editor.film_strip_sprites['groupless'] = groupless_sprite

        coordinator.clear_film_strips_for_new_canvas()

        assert old_strip_sprite.groups() == []
        assert editor.film_strip_sprites['idle'] is not old_strip_sprite
        assert 'groupless' not in editor.film_strip_sprites


class TestRefreshAllFilmStripWidgets:
    """refresh_all_film_strip_widgets rebuilds every strip widget."""

    def test_legacy_widget_and_strip_sprites_are_refreshed(self):
        """The single legacy widget and each strip sprite's widget are rebuilt."""
        editor = _editor_with_strip_stand_ins(frame_counts={'walk': 2})
        editor.canvas.current_frame = 1
        editor.canvas.current_animation = 'walk'
        legacy_widget = _StripWidgetStandIn()
        editor.film_strip_widget = legacy_widget
        editor.film_strip_sprites['no_widget'] = _strip_sprite(widget=None)
        coordinator = FilmStripCoordinator(editor)

        coordinator.refresh_all_film_strip_widgets('walk')

        assert legacy_widget.tab_creations == 1
        assert legacy_widget.dirty_marks == 1
        assert editor.film_strips['walk'].tab_creations == 1
        assert editor.film_strips['walk'].frame_index == 1
        assert editor.film_strip_sprites['walk'].dirty == 1
        assert editor.film_strip_sprites['no_widget'].dirty == 0


class TestEnsureDefaultAnimationExists:
    """_ensure_default_animation_exists gives an empty sprite one magenta frame."""

    def test_empty_sprite_gets_a_default_animation(self):
        """A sprite without animations gets 'default' with one canvas-sized frame."""
        animated_sprite = AnimatedSprite()
        animated_sprite._animations = {}
        editor = _EditorStandIn(animated_sprite=animated_sprite)
        coordinator = FilmStripCoordinator(editor)

        coordinator._ensure_default_animation_exists(animated_sprite)

        assert list(animated_sprite._animations) == ['default']
        default_frame = animated_sprite._animations['default'][0]
        assert default_frame.get_size() == (FRAME_WIDTH, FRAME_HEIGHT)
        assert default_frame.pixels == [(255, 0, 255)] * (FRAME_WIDTH * FRAME_HEIGHT)
        assert animated_sprite.frame_manager.current_animation == 'default'

    def test_sprite_with_animations_is_kept(self):
        """A sprite that has animations keeps them."""
        animated_sprite = _make_animated_sprite(frame_counts={'walk': 2})
        coordinator = FilmStripCoordinator(_EditorStandIn(animated_sprite=animated_sprite))

        coordinator._ensure_default_animation_exists(animated_sprite)

        assert list(animated_sprite._animations) == ['walk']


class TestSetupWithoutCanvasSprite:
    """setup_film_strips without a usable canvas sprite only resets the strips."""

    def test_no_canvas_resets_the_strips(self):
        """Without a canvas, old strips are dropped and none are made."""
        editor = _EditorStandIn()
        editor.film_strips = {'old': _StripWidgetStandIn()}
        coordinator = FilmStripCoordinator(editor)

        coordinator.setup_film_strips()

        assert editor.film_strips == {}

    def test_sprite_without_animations_attribute_makes_no_strips(self):
        """A canvas sprite with no animations attribute makes no strips."""
        editor = _EditorStandIn()
        editor.canvas = SimpleNamespace(animated_sprite=SimpleNamespace())
        coordinator = FilmStripCoordinator(editor)

        coordinator.setup_film_strips()

        assert editor.film_strips == {}
        assert editor.canvas.parent_scene is editor


class TestSelectInitialFilmStripWithoutStrips:
    """_select_initial_film_strip needs strips."""

    def test_no_strips_selects_nothing(self):
        """Without strips nothing is selected."""
        editor = _EditorStandIn(animated_sprite=_make_animated_sprite(frame_counts={'a': 1}))
        coordinator = FilmStripCoordinator(editor)

        coordinator._select_initial_film_strip()

        assert editor.selected_animation is None


class TestNoRemainingAnimationsWithoutSprites:
    """_handle_no_remaining_animations works with no strip sprites."""

    def test_selection_is_cleared(self):
        """The selection is cleared and the scroll returns to the top."""
        editor = _EditorStandIn()
        editor.selected_animation = 'walk'
        editor.film_strip_scroll_offset = 1
        coordinator = FilmStripCoordinator(editor)

        coordinator._handle_no_remaining_animations([], ['walk'], 0)

        assert editor.selected_animation is None
        assert editor.film_strip_scroll_offset == 0


class TestCancelWithoutStripSprites:
    """Cancelling the animation dialog with no strip sprites changes nothing."""

    def test_cancel_without_strip_sprites(self, mocker):
        """The cancel callback copes with an editor that has no strip sprites."""
        dialog_class_mock = mocker.patch('glitchygames.ui.dialogs.DeleteAnimationDialogScene')
        editor = _EditorStandIn(animated_sprite=_make_animated_sprite(frame_counts={'a': 1}))
        coordinator = FilmStripCoordinator(editor)
        coordinator._show_delete_animation_confirmation('a')
        _on_confirm, on_cancel = _captured_dialog_callbacks(dialog_class_mock)
        del editor.film_strip_sprites

        on_cancel()

        assert list(editor.canvas.animated_sprite._animations) == ['a']


class TestIsMouseInFilmStripArea:
    """is_mouse_in_film_strip_area hit-tests the strip sprites."""

    def test_point_inside_a_strip(self):
        """A point inside a strip sprite is in the area."""
        editor = _editor_with_strip_stand_ins(frame_counts={'walk': 1})
        coordinator = FilmStripCoordinator(editor)

        assert coordinator.is_mouse_in_film_strip_area((410, 10)) is True

    def test_point_outside_every_strip(self):
        """A point outside every strip sprite is not in the area."""
        editor = _editor_with_strip_stand_ins(frame_counts={'walk': 1})
        coordinator = FilmStripCoordinator(editor)

        assert coordinator.is_mouse_in_film_strip_area((10, 10)) is False


class TestDragScrollNotDragging:
    """handle_film_strip_drag_scroll ignores moves when not dragging."""

    def test_moves_without_a_drag_do_not_scroll(self):
        """Mouse motion with no drag in progress keeps the scroll."""
        editor = _editor_with_strip_stand_ins(frame_counts={'a': 1, 'b': 1, 'c': 1})
        editor.film_strip_drag_start_offset = 0
        coordinator = FilmStripCoordinator(editor)

        coordinator.handle_film_strip_drag_scroll(500)

        assert editor.film_strip_scroll_offset == 0

    def test_drag_scroll_is_clamped_to_the_last_page(self):
        """A long drag scrolls only as far as the last page of strips."""
        editor = _editor_with_strip_stand_ins(frame_counts={'a': 1, 'b': 1, 'c': 1})
        editor.is_dragging_film_strips = True
        editor.film_strip_drag_start_y = 0
        editor.film_strip_drag_start_offset = 0
        coordinator = FilmStripCoordinator(editor)

        coordinator.handle_film_strip_drag_scroll(900)

        assert editor.film_strip_scroll_offset == 1


class TestRenameLayoutEdges:
    """Layout updates after a rename cope with plain widgets."""

    def test_widget_without_height_or_sprite_or_dirty_marking(self):
        """A widget with only update_layout is updated without a strip sprite."""
        editor = _EditorStandIn()
        widget = SimpleNamespace(layout_updates=[])
        widget.update_layout = lambda: widget.layout_updates.append(True)
        coordinator = FilmStripCoordinator(editor)

        coordinator._update_film_strip_layout_after_rename(widget, 'stroll')

        assert widget.layout_updates == [True]

    def test_strip_showing_another_animation_and_without_a_sprite(self):
        """A strip showing another animation keeps it; a missing sprite is skipped."""
        editor = _EditorStandIn()
        widget = _StripWidgetStandIn()
        widget.current_animation = 'idle'
        editor.film_strips = {'walk': widget}
        coordinator = FilmStripCoordinator(editor)

        coordinator._rename_in_film_strips_dict('walk', 'stroll')

        assert editor.film_strips == {'stroll': widget}
        assert widget.current_animation == 'idle'
        assert editor.film_strip_sprites == {}


class TestUpdateFilmStripSelectionState:
    """update_film_strip_selection_state marks one strip selected."""

    def test_selected_strip_and_sprites_are_marked(self):
        """The selected strip gets the frame; sprites and animated sprites redraw."""
        animated_sprite = _make_animated_sprite(frame_counts={'walk': 1})
        animated_sprite.dirty = 0
        editor = _editor_with_strip_stand_ins(frame_counts={'idle': 1, 'walk': 2})
        editor.film_strips['walk'].animated_sprite = animated_sprite
        editor.film_strips['loose'] = _StripWidgetStandIn()
        editor.selected_animation = 'walk'
        editor.selected_frame = 1
        coordinator = FilmStripCoordinator(editor)

        coordinator.update_film_strip_selection_state()

        assert editor.film_strips['walk'].is_selected is True
        assert editor.film_strips['walk'].selected_frame == 1
        assert editor.film_strips['idle'].is_selected is False
        assert editor.film_strips['loose'].current_animation == 'loose'
        assert editor.film_strip_sprites['idle'].dirty == 1
        assert animated_sprite.dirty == 1


class TestNavigateFrameGuards:
    """_navigate_frame needs a canvas animation with frames."""

    def test_no_canvas_does_not_move(self):
        """Without a canvas nothing moves."""
        editor = _EditorStandIn()
        coordinator = FilmStripCoordinator(editor)

        coordinator._navigate_frame(1)

        assert editor.selected_animation is None

    @pytest.mark.parametrize('current_animation', ['', 'missing'])
    def test_no_or_unknown_animation_does_not_move(self, current_animation):
        """With no current animation, or one not in the sprite, nothing moves."""
        editor = _EditorStandIn(animated_sprite=_make_animated_sprite(frame_counts={'walk': 2}))
        editor.canvas.current_animation = current_animation
        coordinator = FilmStripCoordinator(editor)

        coordinator._navigate_frame(1)

        assert editor.selected_animation is None

    def test_previous_frame_wraps_and_updates_the_strip(self):
        """Stepping back from frame 0 wraps to the last frame in strip and sprite."""
        editor = _editor_with_strip_stand_ins(frame_counts={'walk': 3})
        editor.selected_frame = 0
        coordinator = FilmStripCoordinator(editor)

        coordinator._navigate_frame(-1)

        assert editor.selected_frame == 2
        assert editor.film_strips['walk'].current_frame == 2
        assert editor.film_strips['walk'].dirty_marks == 1
        assert editor.film_strip_sprites['walk'].dirty == 1


class TestClearWithoutStrips:
    """clear_film_strips_for_new_canvas with no strips just builds new ones."""

    def test_new_strips_are_made(self):
        """With no old strips, strips for the canvas sprite are created."""
        editor = _EditorStandIn(animated_sprite=_make_animated_sprite(frame_counts={'walk': 1}))
        coordinator = FilmStripCoordinator(editor)

        coordinator.clear_film_strips_for_new_canvas()

        assert list(editor.film_strips) == ['walk']


class TestRefreshWithoutLegacyWidget:
    """refresh_all_film_strip_widgets without the legacy widget."""

    def test_no_strip_sprites_does_nothing(self):
        """Without strip sprites nothing is refreshed."""
        editor = _EditorStandIn()
        widget = _StripWidgetStandIn()
        editor.film_strips = {'walk': widget}
        coordinator = FilmStripCoordinator(editor)

        coordinator.refresh_all_film_strip_widgets('walk')

        assert widget.tab_creations == 0

    def test_other_animation_keeps_the_frame_index(self):
        """Refreshing for another animation rebuilds but keeps the frame index."""
        editor = _editor_with_strip_stand_ins(frame_counts={'walk': 2})
        editor.canvas.current_animation = 'walk'
        coordinator = FilmStripCoordinator(editor)

        coordinator.refresh_all_film_strip_widgets('idle')

        assert editor.film_strips['walk'].tab_creations == 1
        assert editor.film_strips['walk'].frame_index is None


class TestCallsWithoutStrips:
    """Strip queries and updates with no strips at all."""

    def test_mouse_is_never_in_the_area(self):
        """With no strip sprites no point is in the film strip area."""
        coordinator = FilmStripCoordinator(_EditorStandIn())

        assert coordinator.is_mouse_in_film_strip_area((410, 10)) is False

    def test_switch_without_a_previous_strip(self):
        """The first switch selects the strip without a previous one to clear."""
        editor = _editor_with_strip_stand_ins(frame_counts={'walk': 2})
        coordinator = FilmStripCoordinator(editor)

        coordinator.switch_to_film_strip('walk', 1)

        assert editor.film_strips['walk'].is_selected is True
        assert coordinator.selected_strip is editor.film_strips['walk']

    def test_frame_and_selection_updates_change_nothing(self):
        """Frame and selection updates with no strips leave the editor alone."""
        editor = _EditorStandIn(animated_sprite=_make_animated_sprite(frame_counts={'walk': 2}))
        coordinator = FilmStripCoordinator(editor)

        coordinator.update_film_strips_for_frame('walk', 1)
        coordinator._update_film_strip_selection()

        assert editor.film_strips == {}
        assert editor.selected_animation is None


class TestLogFilmStripDebugState:
    """_log_film_strip_debug_state reports what the canvas offers for film strip creation."""

    def test_sprite_without_animations_attribute_logs_no_animations(self, caplog):
        """A canvas sprite with no _animations attribute is reported, but its animations are not."""
        editor = _EditorStandIn()
        editor.canvas = SimpleNamespace(animated_sprite=SimpleNamespace())
        coordinator = FilmStripCoordinator(editor)

        with caplog.at_level(logging.DEBUG, logger='game.tools.bitmappy'):
            coordinator._log_film_strip_debug_state()

        messages = [record.getMessage() for record in caplog.records]
        assert (
            "DEBUG: hasattr(self.editor.canvas.animated_sprite, '_animations'): False" in messages
        )
        assert not any(
            message.startswith('DEBUG: self.editor.canvas.animated_sprite._animations:')
            for message in messages
        )

    def test_sprite_with_animations_logs_them(self, caplog):
        """A canvas sprite with animations has them logged."""
        editor = _EditorStandIn(animated_sprite=_make_animated_sprite(frame_counts={'walk': 1}))
        coordinator = FilmStripCoordinator(editor)

        with caplog.at_level(logging.DEBUG, logger='game.tools.bitmappy'):
            coordinator._log_film_strip_debug_state()

        assert any(
            record.getMessage().startswith('DEBUG: self.editor.canvas.animated_sprite._animations:')
            for record in caplog.records
        )
