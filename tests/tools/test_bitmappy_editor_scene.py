"""Tests for BitmapEditorScene methods in glitchygames/tools/bitmappy.py.

Covers uncovered regions including:
- Film strip management methods
- Event handlers (slider, keyboard, menu, controller)
- Frame navigation and selection
- Undo/redo operations
- AI-related methods
- Canvas operations
- Multi-controller methods
"""

import argparse
import logging
import time
from types import SimpleNamespace

import pygame
import pytest

from glitchygames.bitmappy import editor as bitmappy
from glitchygames.bitmappy import editor_setup as bitmappy_setup
from glitchygames.bitmappy.ai_manager import AIManager
from glitchygames.bitmappy.controllers.event_handler import ControllerEventHandler
from glitchygames.bitmappy.editor import BitmapEditorScene
from glitchygames.bitmappy.models import AIRequestState, AIResponse
from glitchygames.bitmappy.slider_manager import SliderManager


def _make_event(**kwargs):
    """Create a simple namespace event that supports attribute access like HashableEvent.

    Returns:
        SimpleNamespace: Event-like object with the given attributes.

    """
    return SimpleNamespace(**kwargs)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _setup_sliders(editor, mocker):
    """Configure mock sliders and their bounding boxes on the editor."""
    slider_configs = [
        ('red_slider', 128, '128', (13, 550, 256, 9), 'red_slider_bbox', (10, 548, 260, 13)),
        ('green_slider', 64, '64', (13, 560, 256, 9), 'green_slider_bbox', (10, 558, 260, 13)),
        ('blue_slider', 32, '32', (13, 570, 256, 9), 'blue_slider_bbox', (10, 568, 260, 13)),
        ('alpha_slider', 255, '255', (13, 540, 256, 9), 'alpha_slider_bbox', (10, 538, 260, 13)),
    ]

    # Create a SliderManager for the editor (bypass __init__ to avoid real setup)
    slider_manager = SliderManager.__new__(SliderManager)
    slider_manager.editor = editor
    slider_manager.log = mocker.Mock()

    for slider_name, value, text, text_rect, bbox_name, bbox_rect in slider_configs:
        slider = mocker.Mock()
        slider.value = value
        slider.text_sprite = mocker.Mock()
        slider.text_sprite.is_active = False
        slider.text_sprite.text = text
        slider.text_sprite.rect = pygame.Rect(*text_rect)
        setattr(editor, slider_name, slider)

        bbox = mocker.Mock()
        bbox.visible = False
        bbox.rect = pygame.Rect(*bbox_rect)
        # A real, fully transparent surface, as setup_sliders_and_color_well gives each box
        bbox.image = pygame.Surface(bbox.rect.size, flags=pygame.SRCALPHA, depth=32)
        bbox.image.fill((0, 0, 0, 0))
        # Bounding boxes are now owned by the SliderManager
        setattr(slider_manager, bbox_name, bbox)

    # Initialize SliderManager labels as None (they'd be created during setup)
    slider_manager.alpha_label = None
    slider_manager.red_label = None
    slider_manager.green_label = None
    slider_manager.blue_label = None

    editor._slider_manager = slider_manager


def _setup_canvas(editor, mocker):
    """Configure mock canvas and animated sprite on the editor."""
    editor.canvas = mocker.Mock()
    editor.canvas.pixels_across = 32
    editor.canvas.pixels_tall = 32
    editor.canvas.active_color = (128, 64, 32, 255)
    editor.canvas.canvas_interface = mocker.Mock()
    editor.canvas.pixels = [(255, 0, 255)] * (32 * 32)
    editor.canvas.dirty_pixels = [False] * (32 * 32)
    editor.canvas.current_animation = 'default'
    editor.canvas.current_frame = 0
    editor.canvas.pixel_width = 10
    editor.canvas.pixel_height = 10
    editor.canvas.rect = pygame.Rect(0, 24, 320, 320)

    mock_frame_0 = mocker.Mock()
    mock_frame_0.get_pixel_data.return_value = [(255, 0, 255)] * (32 * 32)
    mock_frame_0.get_size.return_value = (32, 32)
    mock_frame_0.duration = 0.5

    mock_frame_1 = mocker.Mock()
    mock_frame_1.get_pixel_data.return_value = [(255, 0, 255)] * (32 * 32)
    mock_frame_1.get_size.return_value = (32, 32)
    mock_frame_1.duration = 0.5

    editor.canvas.animated_sprite = mocker.Mock()
    editor.canvas.animated_sprite._animations = {
        'default': [mock_frame_0, mock_frame_1],
    }
    editor.canvas.animated_sprite._animation_order = ['default']
    editor.canvas.animated_sprite.frame_manager = mocker.Mock()
    editor.canvas.animated_sprite.frame_manager.current_animation = 'default'
    editor.canvas.animated_sprite.frame_manager.current_frame = 0


def _setup_editor_state(editor, mocker):
    """Configure controller, undo/redo, film strip, and miscellaneous state."""
    editor.multi_controller_manager = mocker.Mock()
    editor.controller_selections = {}
    editor.mode_switcher = mocker.Mock()
    editor.mode_switcher.controller_modes = {}
    editor.visual_collision_manager = mocker.Mock()

    editor.undo_redo_manager = mocker.Mock()
    editor.undo_redo_manager.undo_stack = []
    editor.canvas_operation_tracker = mocker.Mock()
    editor.film_strip_operation_tracker = mocker.Mock()
    editor.cross_area_operation_tracker = mocker.Mock()
    editor.controller_position_operation_tracker = mocker.Mock()
    editor.current_pixel_changes = []
    editor._is_drag_operation = False
    editor.applying_undo_redo = False
    editor.pixel_change_timer = None

    editor.controller_handler = ControllerEventHandler(editor)
    # Controller handler code references self.editor.* for state
    editor.controller_drags = editor.controller_handler.controller_drags
    editor.canvas_continuous_movements = editor.controller_handler.canvas_continuous_movements
    editor.slider_continuous_adjustments = editor.controller_handler.slider_continuous_adjustments
    editor.film_strips = {}
    editor.film_strip_sprites = {}
    editor.film_strip_scroll_offset = 0
    editor.max_visible_strips = 2
    editor.is_dragging_film_strips = False
    editor.film_strip_drag_start_y = None
    editor.film_strip_drag_start_offset = None
    editor.animated_sprite = mocker.Mock()
    editor.selected_animation = 'default'
    editor.selected_frame = 0
    editor.selected_frame_visible = True
    editor.selected_strip = None

    # Frame operations manager (extracted subsystem)
    from glitchygames.bitmappy.frame_operations import FrameOperationManager

    editor._frame_operations = FrameOperationManager(editor)

    editor.screen = mocker.Mock()
    editor.all_sprites = mocker.Mock()
    editor.scene_manager = mocker.Mock()
    editor.game_engine = mocker.Mock()
    editor.game_engine.scene_manager = mocker.Mock()
    editor.next_scene = None
    editor.sprites_at_position = mocker.Mock(return_value=[])

    editor._last_debug_controller_animation = ''
    editor._last_debug_controller_frame = -1
    editor._last_debug_keyboard_animation = ''
    editor._last_debug_keyboard_frame = -1


def _setup_ai_state(editor, mocker):
    """Configure AI-related and debug text state on the editor."""
    editor.debug_text = mocker.Mock()
    editor.debug_text.text = ''
    editor.debug_text.rect = pygame.Rect(400, 400, 300, 186)

    editor.ai_label = mocker.Mock()
    editor.ai_label.rect = pygame.Rect(400, 380, 300, 20)

    # Set up AI integration manager (extracted subsystem)
    ai_integration = AIManager.__new__(AIManager)
    ai_integration.editor = editor
    ai_integration.log = mocker.Mock()
    ai_integration.pending_ai_requests = {}
    ai_integration.ai_request_queue = None
    ai_integration.ai_response_queue = None
    ai_integration.ai_process = None
    ai_integration.last_successful_sprite_content = None
    ai_integration.last_conversation_history = None
    editor._ai_integration = ai_integration

    editor.slider_input_format = '%d'


@pytest.fixture
def mock_editor(mocker):
    """Create a minimal BitmapEditorScene with heavy dependencies mocked out.

    Returns:
        BitmapEditorScene: A mock editor scene instance with all dependencies mocked.

    """
    mocker.patch.object(BitmapEditorScene, '__init__', return_value=None)

    # Mock the screenshot property from Scene base class so it can be set as an attribute
    from glitchygames.scenes.scene import Scene

    mocker.patch.object(
        Scene,
        'screenshot',
        new_callable=lambda: property(
            fget=lambda self: getattr(self, '_screenshot', mocker.Mock()),
            fset=lambda self, value: setattr(self, '_screenshot', value),
        ),
    )

    editor = BitmapEditorScene.__new__(BitmapEditorScene)
    editor._screenshot = mocker.Mock()

    editor.options = {'size': '32x32', 'debug_events': False, 'no_unhandled_events': True}
    editor.dirty = 0
    editor.log = bitmappy.LOG
    editor.screen_width = 800
    editor.screen_height = 600
    editor.dt = 0.016

    editor.color_well = mocker.Mock()
    editor.color_well.active_color = (128, 64, 32, 255)
    editor.color_well.dirty = 0
    editor.color_well.rect = pygame.Rect(300, 540, 40, 40)

    _setup_sliders(editor, mocker)
    _setup_canvas(editor, mocker)
    _setup_editor_state(editor, mocker)
    _setup_ai_state(editor, mocker)

    # -- Film strip coordinator (extracted subsystem) --
    from glitchygames.bitmappy.film_strip_coordinator import FilmStripCoordinator

    editor.film_strip_coordinator = FilmStripCoordinator(editor)

    return editor


# ===========================================================================
# 1. Slider Event Handling (on_slider_event)
# ===========================================================================


class TestOnSliderEvent:
    """Tests for on_slider_event."""

    def test_slider_event_red(self, mock_editor):
        """Red slider event updates red slider value."""
        trigger = _make_event(name='R', value=200)
        event = _make_event()
        mock_editor.on_slider_event(event=event, trigger=trigger)
        assert mock_editor.red_slider.value == 200

    def test_slider_event_green(self, mock_editor):
        """Green slider event updates green slider value."""
        trigger = _make_event(name='G', value=100)
        event = _make_event()
        mock_editor.on_slider_event(event=event, trigger=trigger)
        assert mock_editor.green_slider.value == 100

    def test_slider_event_blue(self, mock_editor):
        """Blue slider event updates blue slider value."""
        trigger = _make_event(name='B', value=50)
        event = _make_event()
        mock_editor.on_slider_event(event=event, trigger=trigger)
        assert mock_editor.blue_slider.value == 50

    def test_slider_event_alpha(self, mock_editor):
        """Alpha slider event updates alpha slider value."""
        trigger = _make_event(name='A', value=128)
        event = _make_event()
        mock_editor.on_slider_event(event=event, trigger=trigger)
        assert mock_editor.alpha_slider.value == 128

    def test_slider_event_clamps_below_zero(self, mock_editor):
        """Slider value is clamped to minimum 0."""
        trigger = _make_event(name='R', value=-10)
        event = _make_event()
        mock_editor.on_slider_event(event=event, trigger=trigger)
        assert mock_editor.red_slider.value == 0
        assert trigger.value == 0

    def test_slider_event_clamps_above_255(self, mock_editor):
        """Slider value is clamped to maximum 255."""
        trigger = _make_event(name='G', value=300)
        event = _make_event()
        mock_editor.on_slider_event(event=event, trigger=trigger)
        assert mock_editor.green_slider.value == 255
        assert trigger.value == 255

    def test_slider_event_updates_color_well(self, mock_editor):
        """Slider event updates the color well active_color."""
        trigger = _make_event(name='R', value=200)
        event = _make_event()
        mock_editor.on_slider_event(event=event, trigger=trigger)
        assert mock_editor.color_well.active_color == (200, 64, 32, 255)

    def test_slider_event_updates_canvas_active_color(self, mock_editor):
        """Slider event updates the canvas active_color."""
        trigger = _make_event(name='B', value=100)
        event = _make_event()
        mock_editor.on_slider_event(event=event, trigger=trigger)
        assert mock_editor.canvas.active_color == (128, 64, 100, 255)


# ===========================================================================
# 2. Clear AI Sprite Box
# ===========================================================================


class TestClearAiSpriteBox:
    """Tests for clear_ai_sprite_box."""

    def test_clears_debug_text(self, mock_editor):
        """Clears the debug text box content."""
        mock_editor.debug_text.text = 'some content'
        mock_editor.clear_ai_sprite_box()
        assert not mock_editor.debug_text.text

    def test_no_debug_text_attribute(self, mock_editor):
        """Handles missing debug_text gracefully."""
        del mock_editor.debug_text
        # Should not raise
        mock_editor.clear_ai_sprite_box()

    def test_debug_text_is_none(self, mock_editor):
        """Handles None debug_text gracefully."""
        mock_editor.debug_text = None
        # Should not raise
        mock_editor.clear_ai_sprite_box()


# ===========================================================================
# 3. Film Strip Mouse Area Detection
# ===========================================================================


class TestIsMouseInFilmStripArea:
    """Tests for _is_mouse_in_film_strip_area."""

    def test_no_film_strip_sprites(self, mock_editor):
        """Returns False when no film strip sprites exist."""
        mock_editor.film_strip_sprites = {}
        result = mock_editor.film_strip_coordinator.is_mouse_in_film_strip_area((500, 100))
        assert result is False

    def test_mouse_inside_film_strip(self, mock_editor, mocker):
        """Returns True when mouse is inside a film strip sprite."""
        film_strip_sprite = mocker.Mock()
        # Use a real Rect that will contain the test point (500, 100)
        film_strip_sprite.rect = pygame.Rect(400, 24, 400, 180)
        mock_editor.film_strip_sprites = {'default': film_strip_sprite}
        result = mock_editor.film_strip_coordinator.is_mouse_in_film_strip_area((500, 100))
        assert result is True

    def test_mouse_outside_film_strip(self, mock_editor, mocker):
        """Returns False when mouse is outside all film strip sprites."""
        film_strip_sprite = mocker.Mock()
        film_strip_sprite.rect = pygame.Rect(400, 24, 400, 180)
        mock_editor.film_strip_sprites = {'default': film_strip_sprite}
        result = mock_editor.film_strip_coordinator.is_mouse_in_film_strip_area((100, 100))
        assert result is False


# ===========================================================================
# 4. Film Strip Drag Scroll
# ===========================================================================


class TestHandleFilmStripDragScroll:
    """Tests for _handle_film_strip_drag_scroll."""

    def test_not_dragging(self, mock_editor):
        """Does nothing when not dragging."""
        mock_editor.is_dragging_film_strips = False
        mock_editor.film_strip_coordinator.handle_film_strip_drag_scroll(200)
        # Should not raise and nothing changes

    def test_no_start_y(self, mock_editor):
        """Does nothing when drag_start_y is None."""
        mock_editor.is_dragging_film_strips = True
        mock_editor.film_strip_drag_start_y = None
        mock_editor.film_strip_coordinator.handle_film_strip_drag_scroll(200)

    def test_no_start_offset(self, mock_editor, mocker):
        """Does nothing when drag_start_offset is None."""
        mock_editor.is_dragging_film_strips = True
        mock_editor.film_strip_drag_start_y = 100
        mock_editor.film_strip_drag_start_offset = None
        mocker.patch.object(mock_editor, 'update_film_strip_visibility')
        mocker.patch.object(mock_editor, 'update_scroll_arrows')
        mock_editor.film_strip_coordinator.handle_film_strip_drag_scroll(200)
        # Should return early without updating

    def test_drag_scrolls_down(self, mock_editor, mocker):
        """Dragging downward increases scroll offset."""
        mock_editor.is_dragging_film_strips = True
        mock_editor.film_strip_drag_start_y = 100
        mock_editor.film_strip_drag_start_offset = 0
        mock_editor.canvas.animated_sprite._animations = {
            'anim1': [mocker.Mock()],
            'anim2': [mocker.Mock()],
            'anim3': [mocker.Mock()],
            'anim4': [mocker.Mock()],
        }
        mocker.patch.object(mock_editor, 'update_film_strip_visibility')
        mocker.patch.object(mock_editor, 'update_scroll_arrows')
        mock_editor.film_strip_coordinator.handle_film_strip_drag_scroll(300)
        assert mock_editor.film_strip_scroll_offset == 2


# ===========================================================================
# 5. Select Initial Film Strip
# ===========================================================================


class TestSelectInitialFilmStrip:
    """Tests for _select_initial_film_strip."""

    def test_no_film_strips(self, mock_editor):
        """Does nothing when no film strips exist."""
        mock_editor.film_strips = {}
        mock_editor.film_strip_coordinator._select_initial_film_strip()
        # Should not raise

    def test_selects_first_animation(self, mock_editor, mocker):
        """Selects the first animation and frame 0."""
        mock_strip = mocker.Mock()
        mock_editor.film_strips = {'walk': mock_strip}
        mock_editor.canvas.animated_sprite._animations = {
            'walk': [mocker.Mock()],
        }
        mock_editor.film_strip_coordinator._select_initial_film_strip()
        assert mock_editor.selected_animation == 'walk'
        assert mock_editor.selected_frame == 0
        mock_editor.canvas.show_frame.assert_called_once_with('walk', 0)

    def test_marks_strips_dirty(self, mock_editor, mocker):
        """Marks all film strip widgets as dirty after selection."""
        mock_strip = mocker.Mock()
        mock_editor.film_strips = {'idle': mock_strip}
        mock_editor.canvas.animated_sprite._animations = {
            'idle': [mocker.Mock()],
        }
        mock_editor.film_strip_coordinator._select_initial_film_strip()
        mock_strip.mark_dirty.assert_called_once()


# ===========================================================================
# 6. Update Film Strip Visibility
# ===========================================================================


class TestUpdateFilmStripVisibility:
    """Tests for update_film_strip_visibility."""

    def test_no_film_strips_does_nothing(self, mock_editor):
        """Does nothing when no film strips exist."""
        mock_editor.film_strips = {}
        mock_editor.update_film_strip_visibility()

    def test_hides_all_then_shows_visible(self, mock_editor, mocker):
        """Hides all strips then shows only visible range."""
        strip1 = mocker.Mock()
        strip1.rect = pygame.Rect(400, 24, 400, 145)
        strip2 = mocker.Mock()
        strip2.rect = pygame.Rect(400, 150, 400, 145)
        strip3 = mocker.Mock()
        strip3.rect = pygame.Rect(400, 276, 400, 145)

        sprite1 = mocker.Mock()
        sprite1.rect = pygame.Rect(400, 24, 400, 145)
        sprite2 = mocker.Mock()
        sprite2.rect = pygame.Rect(400, 150, 400, 145)
        sprite3 = mocker.Mock()
        sprite3.rect = pygame.Rect(400, 276, 400, 145)

        mock_editor.film_strips = {'a': strip1, 'b': strip2, 'c': strip3}
        mock_editor.film_strip_sprites = {'a': sprite1, 'b': sprite2, 'c': sprite3}
        mock_editor.canvas.animated_sprite._animations = {
            'a': [mocker.Mock()],
            'b': [mocker.Mock()],
            'c': [mocker.Mock()],
        }
        mocker.patch.object(mock_editor, 'update_scroll_arrows')
        mock_editor.update_film_strip_visibility()

        # With scroll_offset=0 and max_visible=2, only 'a' and 'b' should be visible
        assert sprite1.visible is True
        assert sprite2.visible is True
        assert sprite3.visible is False


# ===========================================================================
# 7. Navigate Frame
# ===========================================================================


class TestNavigateFrame:
    """Tests for _navigate_frame."""

    def test_no_canvas_does_nothing(self, mock_editor):
        """Does nothing when canvas is not available."""
        mock_editor.canvas = None
        mock_editor.film_strip_coordinator._navigate_frame(1)

    def test_no_current_animation(self, mock_editor):
        """Does nothing when no animation is selected."""
        mock_editor.canvas.current_animation = ''
        mock_editor.film_strip_coordinator._navigate_frame(1)
        mock_editor.canvas.show_frame.assert_not_called()

    def test_navigate_forward(self, mock_editor, mocker):
        """Navigates to next frame."""
        mock_strip = mocker.Mock()
        mock_editor.film_strips = {'default': mock_strip}
        mock_editor.film_strip_sprites = {'default': mocker.Mock()}
        mock_editor.film_strip_coordinator._navigate_frame(1)
        assert mock_editor.selected_frame == 1
        mock_editor.canvas.show_frame.assert_called_with('default', 1)

    def test_navigate_backward_wraps(self, mock_editor, mocker):
        """Navigates backward with wrapping."""
        mock_strip = mocker.Mock()
        mock_editor.film_strips = {'default': mock_strip}
        mock_editor.film_strip_sprites = {'default': mocker.Mock()}
        mock_editor.selected_frame = 0
        mock_editor.film_strip_coordinator._navigate_frame(-1)
        # 2 frames, (0 + -1) % 2 = 1
        assert mock_editor.selected_frame == 1

    def test_navigate_forward_wraps(self, mock_editor, mocker):
        """Navigates forward with wrapping past the last frame."""
        mock_strip = mocker.Mock()
        mock_editor.film_strips = {'default': mock_strip}
        mock_editor.film_strip_sprites = {'default': mocker.Mock()}
        mock_editor.selected_frame = 1
        mock_editor.film_strip_coordinator._navigate_frame(1)
        # 2 frames, (1 + 1) % 2 = 0
        assert mock_editor.selected_frame == 0

    def test_animation_not_in_sprite(self, mock_editor):
        """Does nothing when animation name is not in animated sprite."""
        mock_editor.canvas.current_animation = 'nonexistent'
        mock_editor.film_strip_coordinator._navigate_frame(1)
        mock_editor.canvas.show_frame.assert_not_called()


# ===========================================================================
# 8. Scroll Film Strips
# ===========================================================================


class TestScrollFilmStrips:
    """Tests for scroll_film_strips_up and scroll_film_strips_down."""

    def test_scroll_up_decreases_offset(self, mock_editor, mocker):
        """Scrolling up decreases offset."""
        mock_editor.film_strip_scroll_offset = 1
        mocker.patch.object(mock_editor, 'update_film_strip_visibility')
        mock_editor.scroll_film_strips_up()
        assert mock_editor.film_strip_scroll_offset == 0

    def test_scroll_up_stops_at_zero(self, mock_editor, mocker):
        """Scrolling up does not go below zero."""
        mock_editor.film_strip_scroll_offset = 0
        mock_editor.scroll_film_strips_up()
        assert mock_editor.film_strip_scroll_offset == 0

    def test_scroll_down_increases_offset(self, mock_editor, mocker):
        """Scrolling down increases offset."""
        mock_editor.film_strip_scroll_offset = 0
        mock_editor.canvas.animated_sprite._animations = {
            'a': [mocker.Mock()],
            'b': [mocker.Mock()],
            'c': [mocker.Mock()],
            'd': [mocker.Mock()],
        }
        mocker.patch.object(mock_editor, 'update_film_strip_visibility')
        mock_editor.scroll_film_strips_down()
        assert mock_editor.film_strip_scroll_offset == 1

    def test_scroll_down_stops_at_max(self, mock_editor, mocker):
        """Scrolling down does not exceed max scroll."""
        mock_editor.film_strip_scroll_offset = 1
        mock_editor.canvas.animated_sprite._animations = {
            'a': [mocker.Mock()],
            'b': [mocker.Mock()],
            'c': [mocker.Mock()],
        }
        # max_scroll = max(0, 3 - 2) = 1, already at 1
        mock_editor.scroll_film_strips_down()
        assert mock_editor.film_strip_scroll_offset == 1


# ===========================================================================
# 9. Select First/Last Visible Film Strip
# ===========================================================================


class TestSelectVisibleFilmStrips:
    """Tests for _select_first_visible_film_strip and _select_last_visible_film_strip."""

    def test_select_first_visible_no_strips(self, mock_editor):
        """Does nothing with no film strips."""
        mock_editor.film_strips = {}
        mock_editor.film_strip_coordinator._select_first_visible_film_strip()

    def test_select_first_visible(self, mock_editor, mocker):
        """Selects the first visible strip based on scroll offset."""
        mock_strip = mocker.Mock()
        mock_editor.film_strips = {'a': mocker.Mock(), 'b': mock_strip}
        mock_editor.canvas.animated_sprite._animations = {
            'a': [mocker.Mock()],
            'b': [mocker.Mock()],
        }
        mock_editor.film_strip_scroll_offset = 1
        mock_editor.film_strip_coordinator._select_first_visible_film_strip()
        assert mock_editor.selected_animation == 'b'
        assert mock_editor.selected_frame == 0

    def test_select_last_visible_no_strips(self, mock_editor):
        """Does nothing with no film strips."""
        mock_editor.film_strips = {}
        mock_editor.film_strip_coordinator._select_last_visible_film_strip()

    def test_select_last_visible(self, mock_editor, mocker):
        """Selects the last visible strip."""
        mock_strip_a = mocker.Mock()
        mock_strip_b = mocker.Mock()
        mock_editor.film_strips = {'a': mock_strip_a, 'b': mock_strip_b}
        mock_editor.canvas.animated_sprite._animations = {
            'a': [mocker.Mock()],
            'b': [mocker.Mock()],
        }
        mock_editor.film_strip_scroll_offset = 0
        mock_editor.film_strip_coordinator._select_last_visible_film_strip()
        assert mock_editor.selected_animation == 'b'
        assert mock_editor.selected_frame == 0


# ===========================================================================
# 10. Copy/Paste Current Frame
# ===========================================================================


class TestCopyPasteFrame:
    """Tests for _copy_current_frame and _paste_to_current_frame."""

    def test_copy_no_film_strips(self, mock_editor):
        """Returns False when no film strips exist."""
        mock_editor.film_strips = {}
        result = mock_editor.film_strip_coordinator._copy_current_frame()
        assert result is False

    def test_copy_no_active_strip(self, mock_editor, mocker):
        """Returns False when no active film strip matches selected animation."""
        mock_strip = mocker.Mock()
        mock_strip.current_animation = 'other'
        mock_editor.film_strips = {'other': mock_strip}
        mock_editor.selected_animation = 'default'
        result = mock_editor.film_strip_coordinator._copy_current_frame()
        assert result is False

    def test_copy_success(self, mock_editor, mocker):
        """Copies frame when active strip is found."""
        mock_strip = mocker.Mock()
        mock_strip.current_animation = 'default'
        mock_strip.copy_current_frame.return_value = True
        mock_editor.film_strips = {'default': mock_strip}
        mock_editor.selected_animation = 'default'
        result = mock_editor.film_strip_coordinator._copy_current_frame()
        assert result is True
        mock_strip.copy_current_frame.assert_called_once()

    def test_paste_no_film_strips(self, mock_editor):
        """Returns False when no film strips exist."""
        mock_editor.film_strips = {}
        result = mock_editor.film_strip_coordinator._paste_to_current_frame()
        assert result is False

    def test_paste_no_active_strip(self, mock_editor, mocker):
        """Returns False when no active film strip matches."""
        mock_strip = mocker.Mock()
        mock_strip.current_animation = 'other'
        mock_editor.film_strips = {'other': mock_strip}
        mock_editor.selected_animation = 'default'
        result = mock_editor.film_strip_coordinator._paste_to_current_frame()
        assert result is False

    def test_paste_success(self, mock_editor, mocker):
        """Pastes frame when active strip is found."""
        mock_strip = mocker.Mock()
        mock_strip.current_animation = 'default'
        mock_strip.paste_to_current_frame.return_value = True
        mock_editor.film_strips = {'default': mock_strip}
        mock_editor.selected_animation = 'default'
        result = mock_editor.film_strip_coordinator._paste_to_current_frame()
        assert result is True


# ===========================================================================
# 11. Update Film Strip Selection State
# ===========================================================================


class TestUpdateFilmStripSelectionState:
    """Tests for update_film_strip_selection_state."""

    def test_no_film_strips(self, mock_editor):
        """Does nothing when no film strips exist."""
        mock_editor.film_strips = {}
        mock_editor.update_film_strip_selection_state()

    def test_marks_selected_strip(self, mock_editor, mocker):
        """Marks the selected strip and deselects others."""
        strip_default = mocker.Mock()
        strip_default.selected_frame = 0
        strip_other = mocker.Mock()
        strip_other.selected_frame = 0
        mock_editor.film_strips = {'default': strip_default, 'other': strip_other}
        mock_editor.film_strip_sprites = {
            'default': mocker.Mock(),
            'other': mocker.Mock(),
        }
        mock_editor.selected_animation = 'default'
        mock_editor.selected_frame = 1
        mock_editor.update_film_strip_selection_state()
        assert strip_default.is_selected is True
        assert strip_default.selected_frame == 1
        assert strip_other.is_selected is False


# ===========================================================================
# 12. Switch to Film Strip
# ===========================================================================


class TestSwitchToFilmStrip:
    """Tests for _switch_to_film_strip."""

    def test_switch_to_existing_strip(self, mock_editor, mocker):
        """Switches to an existing film strip."""
        new_strip = mocker.Mock()
        mock_editor.film_strips = {'walk': new_strip}
        mock_editor.film_strip_sprites = {'walk': mocker.Mock()}
        mock_editor.film_strip_coordinator.switch_to_film_strip('walk', 2)
        assert mock_editor.selected_animation == 'walk'
        assert mock_editor.selected_frame == 2
        assert mock_editor.film_strip_coordinator.selected_strip == new_strip
        mock_editor.canvas.show_frame.assert_called_with('walk', 2)

    def test_switch_deselects_previous(self, mock_editor, mocker):
        """Deselects the previous strip before selecting new one."""
        old_strip = mocker.Mock()
        old_strip.animated_sprite = mocker.Mock()
        mock_editor.film_strip_coordinator.selected_strip = old_strip

        new_strip = mocker.Mock()
        old_sprite = mocker.Mock()
        old_sprite.film_strip_widget = old_strip
        mock_editor.film_strips = {'walk': new_strip}
        mock_editor.film_strip_sprites = {'walk': mocker.Mock(), 'idle': old_sprite}
        mock_editor.film_strip_coordinator.switch_to_film_strip('walk', 0)
        assert old_strip.is_selected is False

    def test_switch_to_nonexistent_strip(self, mock_editor):
        """Handles switch to nonexistent strip gracefully."""
        mock_editor.film_strips = {}
        mock_editor.film_strip_coordinator.switch_to_film_strip('nonexistent', 0)
        # Should not raise, selected_animation unchanged if strip not found


# ===========================================================================
# 13. Scroll to Current Animation
# ===========================================================================


class TestScrollToCurrentAnimation:
    """Tests for _scroll_to_current_animation."""

    def test_no_canvas(self, mock_editor):
        """Does nothing when canvas is not available."""
        mock_editor.canvas = None
        mock_editor.film_strip_coordinator.scroll_to_current_animation()

    def test_no_current_animation(self, mock_editor):
        """Does nothing when no animation is selected."""
        mock_editor.canvas.current_animation = ''
        mock_editor.film_strip_coordinator.scroll_to_current_animation()

    def test_scrolls_up_when_above_visible(self, mock_editor, mocker):
        """Scrolls up when animation is above visible area."""
        mock_editor.canvas.animated_sprite._animations = {
            'a': [mocker.Mock()],
            'b': [mocker.Mock()],
            'c': [mocker.Mock()],
            'd': [mocker.Mock()],
        }
        mock_editor.canvas.current_animation = 'a'
        mock_editor.film_strip_scroll_offset = 2
        mocker.patch.object(mock_editor, 'update_film_strip_visibility')
        mocker.patch.object(mock_editor, 'update_scroll_arrows')
        mocker.patch.object(mock_editor.film_strip_coordinator, '_update_film_strip_selection')
        mock_editor.film_strip_coordinator.scroll_to_current_animation()
        assert mock_editor.film_strip_scroll_offset == 0

    def test_scrolls_down_when_below_visible(self, mock_editor, mocker):
        """Scrolls down when animation is below visible area."""
        mock_editor.canvas.animated_sprite._animations = {
            'a': [mocker.Mock()],
            'b': [mocker.Mock()],
            'c': [mocker.Mock()],
            'd': [mocker.Mock()],
        }
        mock_editor.canvas.current_animation = 'd'
        mock_editor.film_strip_scroll_offset = 0
        mocker.patch.object(mock_editor, 'update_film_strip_visibility')
        mocker.patch.object(mock_editor, 'update_scroll_arrows')
        mocker.patch.object(mock_editor.film_strip_coordinator, '_update_film_strip_selection')
        mock_editor.film_strip_coordinator.scroll_to_current_animation()
        assert mock_editor.film_strip_scroll_offset == 2

    def test_no_scroll_when_visible(self, mock_editor, mocker):
        """Does not scroll when animation is already visible."""
        mock_editor.canvas.animated_sprite._animations = {
            'a': [mocker.Mock()],
            'b': [mocker.Mock()],
        }
        mock_editor.canvas.current_animation = 'a'
        mock_editor.film_strip_scroll_offset = 0
        mock_editor.film_strip_coordinator.scroll_to_current_animation()
        assert mock_editor.film_strip_scroll_offset == 0


# ===========================================================================
# 14. On Frame Inserted/Removed
# ===========================================================================


class TestFrameInsertedRemoved:
    """Tests for _on_frame_inserted and _on_frame_removed."""

    def test_on_frame_inserted_updates_canvas(self, mock_editor, mocker):
        """Updates canvas to show inserted frame."""
        mock_strip = mocker.Mock()
        mock_strip.animated_sprite = mocker.Mock()
        mock_editor.film_strips = {'default': mock_strip}
        mock_editor.film_strip_sprites = {'default': mocker.Mock()}
        mock_editor.film_strip_coordinator.on_frame_inserted('default', 1)
        mock_editor.canvas.show_frame.assert_called_with('default', 1)
        assert mock_editor.selected_frame == 1

    def test_on_frame_inserted_different_animation(self, mock_editor, mocker):
        """Does not update canvas if inserted in different animation."""
        mock_strip = mocker.Mock()
        mock_strip.animated_sprite = mocker.Mock()
        mock_editor.film_strips = {'other': mock_strip}
        mock_editor.film_strip_sprites = {'other': mocker.Mock()}
        mock_editor.selected_animation = 'default'
        mock_editor.film_strip_coordinator.on_frame_inserted('other', 0)
        mock_editor.canvas.show_frame.assert_not_called()

    def test_on_frame_removed_adjusts_selection(self, mock_editor, mocker):
        """Adjusts selected frame when a frame before it is removed."""
        mock_strip = mocker.Mock()
        mock_strip.animated_sprite = mocker.Mock()
        mock_editor.film_strips = {'default': mock_strip}
        mock_editor.film_strip_sprites = {'default': mocker.Mock()}
        mock_editor.selected_frame = 1
        mock_editor.film_strip_coordinator.on_frame_removed('default', 0)
        assert mock_editor.selected_frame == 0

    def test_on_frame_removed_at_frame_zero(self, mock_editor, mocker):
        """Stays at frame 0 when frame 0 is removed."""
        mock_strip = mocker.Mock()
        mock_strip.animated_sprite = mocker.Mock()
        mock_editor.film_strips = {'default': mock_strip}
        mock_editor.film_strip_sprites = {'default': mocker.Mock()}
        mock_editor.selected_frame = 0
        mock_editor.film_strip_coordinator.on_frame_removed('default', 0)
        assert mock_editor.selected_frame == 0


# ===========================================================================
# 15. Undo/Redo Operations
# ===========================================================================


class TestUndoRedo:
    """Tests for handle_undo and _handle_redo."""

    def test_handle_undo_no_manager(self, mock_editor):
        """Warns when undo/redo manager is not initialized."""
        del mock_editor.undo_redo_manager
        mock_editor.handle_undo()
        # Should not raise

    def test_handle_undo_frame_specific(self, mock_editor, mocker):
        """Performs frame-specific undo when available."""
        mock_editor.undo_redo_manager.can_undo_frame.return_value = True
        mock_editor.undo_redo_manager.undo_frame.return_value = True
        mock_editor.handle_undo()
        mock_editor.undo_redo_manager.undo_frame.assert_called_once_with('default', 0)

    def test_handle_undo_global_fallback(self, mock_editor, mocker):
        """Falls back to global undo when frame-specific is not available."""
        mock_editor.undo_redo_manager.can_undo_frame.return_value = False
        mock_editor.undo_redo_manager.can_undo.return_value = True
        mock_editor.undo_redo_manager.undo.return_value = True
        mocker.patch.object(mock_editor, '_synchronize_canvas_state_after_undo')
        mock_editor.handle_undo()
        mock_editor.undo_redo_manager.undo.assert_called_once()

    def test_handle_undo_nothing_to_undo(self, mock_editor):
        """Does nothing when there is nothing to undo."""
        mock_editor.undo_redo_manager.can_undo_frame.return_value = False
        mock_editor.undo_redo_manager.can_undo.return_value = False
        mock_editor.handle_undo()

    def test_handle_redo_no_manager(self, mock_editor):
        """Warns when undo/redo manager is not initialized."""
        del mock_editor.undo_redo_manager
        mock_editor.handle_redo()

    def test_handle_redo_frame_specific(self, mock_editor, mocker):
        """Performs frame-specific redo when available."""
        mock_editor.undo_redo_manager.can_redo_frame.return_value = True
        mock_editor.undo_redo_manager.redo_frame.return_value = True
        mock_editor.handle_redo()
        mock_editor.undo_redo_manager.redo_frame.assert_called_once_with('default', 0)

    def test_handle_redo_global_fallback(self, mock_editor, mocker):
        """Falls back to global redo when frame-specific is not available."""
        mock_editor.undo_redo_manager.can_redo_frame.return_value = False
        mock_editor.undo_redo_manager.can_redo.return_value = True
        mock_editor.undo_redo_manager.redo.return_value = True
        mocker.patch.object(mock_editor, '_synchronize_canvas_state_after_undo')
        mock_editor.handle_redo()
        mock_editor.undo_redo_manager.redo.assert_called_once()


# ===========================================================================
# 16. Synchronize Canvas State After Undo
# ===========================================================================


class TestSynchronizeCanvasState:
    """Tests for _synchronize_canvas_state_after_undo."""

    def test_no_canvas(self, mock_editor):
        """Does nothing when canvas is missing."""
        mock_editor.canvas = None
        mock_editor._synchronize_canvas_state_after_undo()

    def test_no_animated_sprite(self, mock_editor):
        """Does nothing when animated sprite is missing."""
        mock_editor.canvas.animated_sprite = None
        mock_editor._synchronize_canvas_state_after_undo()

    def test_current_animation_missing_switches_to_first(self, mock_editor, mocker):
        """Switches to first animation when current one is missing."""
        mock_editor.canvas.current_animation = 'deleted_anim'
        mock_editor.canvas.animated_sprite._animations = {
            'walk': [mocker.Mock()],
        }
        mock_editor._synchronize_canvas_state_after_undo()
        mock_editor.canvas.show_frame.assert_called_with('walk', 0)

    def test_frame_index_out_of_bounds(self, mock_editor, mocker):
        """Adjusts frame index when it's out of bounds."""
        mock_editor.canvas.current_animation = 'default'
        mock_editor.canvas.current_frame = 5
        mock_editor.canvas.animated_sprite._animations = {
            'default': [mocker.Mock(), mocker.Mock()],
        }
        mocker.patch.object(mock_editor.film_strip_coordinator, 'update_film_strips_for_frame')
        mock_editor._synchronize_canvas_state_after_undo()
        mock_editor.canvas.show_frame.assert_called_with('default', 1)

    def test_valid_state_forces_redraw(self, mock_editor, mocker):
        """Forces redraw when canvas state is valid."""
        mock_editor.canvas.current_animation = 'default'
        mock_editor.canvas.current_frame = 0
        mock_editor.canvas.animated_sprite._animations = {
            'default': [mocker.Mock(), mocker.Mock()],
        }
        update_film_strips = mocker.patch.object(
            mock_editor.film_strip_coordinator, 'update_film_strips_for_frame'
        )
        mock_editor._synchronize_canvas_state_after_undo()
        mock_editor.canvas.force_redraw.assert_called()
        # BUGS.md #98: the refresh was guarded by a hasattr on the editor, always False
        update_film_strips.assert_called_once_with('default', 0)


class TestSingleClickTimer:
    """Tests for FrameOperationManager.check_single_click_timer (frame-clock debounce)."""

    def test_click_on_the_first_frame_is_submitted_after_the_debounce(self, mock_editor, mocker):
        """A timer started while the frame clock still reads 0.0 is a real timer, not 'unset'."""
        from glitchygames import sources
        from glitchygames.bitmappy.constants import PIXEL_CHANGE_DEBOUNCE_SECONDS

        frame_operations = mock_editor._frame_operations
        submit = mocker.patch.object(frame_operations, 'submit_pixel_changes_if_ready')
        mock_editor.current_pixel_changes = [(0, 0, (255, 0, 0), (0, 0, 0))]
        mock_editor.pixel_change_timer = 0.0

        sources.advance_frame_clock(seconds=PIXEL_CHANGE_DEBOUNCE_SECONDS * 2)
        frame_operations.check_single_click_timer()

        submit.assert_called_once_with()
        assert mock_editor.pixel_change_timer is None

    def test_click_is_held_until_the_debounce_passes(self, mock_editor, mocker):
        """Within the debounce the single pixel waits (it may become a drag)."""
        frame_operations = mock_editor._frame_operations
        submit = mocker.patch.object(frame_operations, 'submit_pixel_changes_if_ready')
        mock_editor.current_pixel_changes = [(0, 0, (255, 0, 0), (0, 0, 0))]
        mock_editor.pixel_change_timer = 0.0

        frame_operations.check_single_click_timer()

        submit.assert_not_called()
        assert mock_editor.pixel_change_timer == 0.0


class TestAxisCooldown:
    """Tests for ControllerEventHandler._check_axis_deadzone_and_cooldown."""

    def test_stick_back_from_the_deadzone_has_no_cooldown_at_any_reading(self, mock_editor, mocker):
        """After the deadzone clears the cooldown, a push counts even at elapsed 0.1 (replay)."""
        handler = mock_editor.controller_handler
        axis = (0, pygame.CONTROLLER_AXIS_LEFTX)

        centered = handler._check_axis_deadzone_and_cooldown(mocker.Mock(axis=axis, value=0), 0.0)
        pushed = handler._check_axis_deadzone_and_cooldown(mocker.Mock(axis=axis, value=20000), 0.1)

        assert centered is False
        assert pushed is True


# ===========================================================================
# 18. Handle Copy/Paste Frame Operations
# ===========================================================================


class TestHandleCopyPasteFrame:
    """Tests for FrameOperationManager.handle_copy_frame and handle_paste_frame."""

    def test_copy_frame_no_canvas(self, mock_editor):
        """Does nothing when canvas is not available."""
        mock_editor.canvas = None
        mock_editor._frame_operations.handle_copy_frame()

    def test_copy_frame_no_selection(self, mock_editor):
        """Does nothing when no animation/frame is selected."""
        mock_editor.selected_animation = None
        mock_editor.selected_frame = None
        mock_editor._frame_operations.handle_copy_frame()

    def test_copy_frame_stores_clipboard(self, mock_editor, mocker):
        """Copies frame data to clipboard."""
        mock_frame = mocker.Mock()
        mock_frame.get_pixel_data.return_value = [(100, 50, 25)] * 1024
        mock_frame.get_size.return_value = (32, 32)
        mock_frame.duration = 0.5
        mock_editor.canvas.animated_sprite._animations = {
            'default': [mock_frame],
        }
        mock_editor.selected_frame = 0
        mock_editor._frame_operations.handle_copy_frame()
        assert mock_editor._frame_operations._frame_clipboard is not None
        assert mock_editor._frame_operations._frame_clipboard['width'] == 32
        assert mock_editor._frame_operations._frame_clipboard['height'] == 32

    def test_paste_frame_no_clipboard(self, mock_editor):
        """Does nothing when clipboard is empty."""
        mock_editor._frame_operations._frame_clipboard = None
        mock_editor._frame_operations.handle_paste_frame()

    def test_paste_frame_dimension_mismatch(self, mock_editor, mocker):
        """Does nothing when clipboard dimensions do not match target."""
        mock_editor._frame_operations._frame_clipboard = {
            'pixels': [(100, 50, 25)] * 256,
            'width': 16,
            'height': 16,
            'duration': 0.5,
            'animation': 'default',
            'frame': 0,
        }
        mock_frame = mocker.Mock()
        mock_frame.get_size.return_value = (32, 32)
        mock_editor.canvas.animated_sprite._animations = {
            'default': [mock_frame],
        }
        mock_editor._frame_operations.handle_paste_frame()
        # Should not call set_pixel_data due to dimension mismatch


# ===========================================================================
# 19. BrushStrokeCommand Undo/Redo
# ===========================================================================


class TestBrushStrokeCommandUndoRedo:
    """Tests for BrushStrokeCommand (replaces _apply_pixel_change_for_undo_redo)."""

    def test_execute_sets_pixel(self, mock_editor):
        """Execute sets pixel via canvas interface."""
        from glitchygames.bitmappy.history.commands import BrushStrokeCommand
        from glitchygames.bitmappy.history.undo_redo import OperationType

        command = BrushStrokeCommand(
            mock_editor,
            [(5, 10, (0, 0, 0), (255, 0, 0))],
            OperationType.CANVAS_PIXEL_CHANGE,
        )
        result = command.execute()
        assert result is True
        mock_editor.canvas.canvas_interface.set_pixel_at.assert_called_once_with(5, 10, (255, 0, 0))

    def test_execute_sets_and_resets_flag(self, mock_editor):
        """Sets applying_undo_redo during operation and resets after."""
        from glitchygames.bitmappy.history.commands import BrushStrokeCommand
        from glitchygames.bitmappy.history.undo_redo import OperationType

        assert mock_editor.applying_undo_redo is False
        command = BrushStrokeCommand(
            mock_editor,
            [(0, 0, (0, 0, 0), (255, 255, 255))],
            OperationType.CANVAS_PIXEL_CHANGE,
        )
        command.execute()
        assert mock_editor.applying_undo_redo is False

    def test_no_canvas_returns_false(self, mock_editor):
        """Returns False when canvas is not available."""
        from glitchygames.bitmappy.history.commands import BrushStrokeCommand
        from glitchygames.bitmappy.history.undo_redo import OperationType

        mock_editor.canvas = None
        command = BrushStrokeCommand(
            mock_editor,
            [(0, 0, (0, 0, 0), (255, 255, 255))],
            OperationType.CANVAS_PIXEL_CHANGE,
        )
        result = command.execute()
        assert result is False


# ===========================================================================
# 20. FrameSelectionCommand Undo/Redo
# ===========================================================================


class TestFrameSelectionCommandUndoRedo:
    """Tests for FrameSelectionCommand (replaces _apply_frame_selection_for_undo_redo)."""

    def test_execute_applies_selection(self, mock_editor):
        """Execute switches to new frame via canvas."""
        from glitchygames.bitmappy.history.commands import FrameSelectionCommand

        command = FrameSelectionCommand(mock_editor, 'default', 0, 'default', 1)
        result = command.execute()
        assert result is True
        mock_editor.canvas.show_frame.assert_called_once_with('default', 1)

    def test_undo_resets_flag_after_operation(self, mock_editor):
        """Resets applying_undo_redo flag after undo."""
        from glitchygames.bitmappy.history.commands import FrameSelectionCommand

        command = FrameSelectionCommand(mock_editor, 'default', 0, 'default', 1)
        command.undo()
        assert mock_editor.applying_undo_redo is False

    def test_no_canvas_returns_false(self, mock_editor):
        """Returns False when canvas is not available."""
        from glitchygames.bitmappy.history.commands import FrameSelectionCommand

        mock_editor.canvas = None
        command = FrameSelectionCommand(mock_editor, 'default', 0, 'default', 1)
        result = command.execute()
        assert result is False

    def test_handles_exception(self, mock_editor):
        """Returns False on exception."""
        from glitchygames.bitmappy.history.commands import FrameSelectionCommand

        mock_editor.canvas.show_frame.side_effect = IndexError('test')
        command = FrameSelectionCommand(mock_editor, 'default', 0, 'default', 99)
        result = command.execute()
        assert result is False


# ===========================================================================
# 21. Menu Item Event Handling
# ===========================================================================


class TestOnMenuItemEvent:
    """Tests for on_menu_item_event."""

    def test_new_menu(self, mock_editor, mocker):
        """'New' dispatches to dialog."""
        menu_mock = mocker.Mock()
        menu_mock.name = 'New'
        mocker.patch.object(mock_editor, 'on_new_canvas_dialog_event')
        mock_editor.on_menu_item_event(_make_event(menu=menu_mock))
        mock_editor.on_new_canvas_dialog_event.assert_called_once()

    def test_save_menu(self, mock_editor, mocker):
        """'Save' dispatches to dialog."""
        menu_mock = mocker.Mock()
        menu_mock.name = 'Save'
        mocker.patch.object(mock_editor, 'on_save_dialog_event')
        mock_editor.on_menu_item_event(_make_event(menu=menu_mock))
        mock_editor.on_save_dialog_event.assert_called_once()

    def test_load_menu(self, mock_editor, mocker):
        """'Load' dispatches to dialog."""
        menu_mock = mocker.Mock()
        menu_mock.name = 'Load'
        mocker.patch.object(mock_editor, 'on_load_dialog_event')
        mock_editor.on_menu_item_event(_make_event(menu=menu_mock))
        mock_editor.on_load_dialog_event.assert_called_once()

    def test_quit_menu(self, mock_editor, mocker):
        """'Quit' calls scene_manager.quit()."""
        menu_mock = mocker.Mock()
        menu_mock.name = 'Quit'
        mock_editor.on_menu_item_event(_make_event(menu=menu_mock))
        mock_editor.scene_manager.quit.assert_called_once()

    def test_unhandled_menu(self, mock_editor, mocker):
        """Unhandled menu name logs but does not crash."""
        menu_mock = mocker.Mock()
        menu_mock.name = 'CustomMenu'
        mock_editor.on_menu_item_event(_make_event(menu=menu_mock))
        assert mock_editor.dirty == 1

    def test_system_menu_no_name(self, mock_editor, mocker):
        """System menu with no name."""
        menu_mock = mocker.Mock()
        menu_mock.name = None
        mock_editor.on_menu_item_event(_make_event(menu=menu_mock))
        assert mock_editor.dirty == 1


# ===========================================================================
# 22. Dialog Events
# ===========================================================================


class TestDialogEvents:
    """Tests for on_new_canvas_dialog_event, on_load_dialog_event, on_save_dialog_event."""

    def test_on_new_canvas_dialog(self, mock_editor, mocker):
        """Creates new canvas dialog scene."""
        mocker.patch('glitchygames.bitmappy.editor.NewCanvasDialogScene')
        event = _make_event()
        mock_editor.on_new_canvas_dialog_event(event)
        assert mock_editor.next_scene is not None
        assert mock_editor.dirty == 1

    def test_on_load_dialog(self, mock_editor, mocker):
        """Creates load dialog scene."""
        mocker.patch('glitchygames.bitmappy.editor.LoadDialogScene')
        event = _make_event()
        mock_editor.on_load_dialog_event(event)
        assert mock_editor.next_scene is not None
        assert mock_editor.dirty == 1

    def test_on_save_dialog(self, mock_editor, mocker):
        """Creates save dialog scene."""
        mocker.patch('glitchygames.bitmappy.editor.SaveDialogScene')
        event = _make_event()
        mock_editor.on_save_dialog_event(event)
        assert mock_editor.next_scene is not None
        assert mock_editor.dirty == 1


# ===========================================================================
# 24. Update Film Strips Methods
# ===========================================================================


class TestUpdateFilmStrips:
    """Tests for various film strip update methods."""

    def test_update_for_frame(self, mock_editor, mocker):
        """Updates film strip for specific frame change."""
        mock_strip = mocker.Mock()
        mock_editor.film_strips = {'default': mock_strip}
        mock_editor.film_strip_sprites = {'default': mocker.Mock()}
        mock_editor.film_strip_coordinator.update_film_strips_for_frame('default', 1)
        mock_strip.update_scroll_for_frame.assert_called_once_with(1)

    def test_update_for_pixel_update(self, mock_editor, mocker):
        """Marks visible film strips dirty on pixel update."""
        mock_sprite = mocker.Mock()
        mock_sprite.visible = True
        mock_strip = mocker.Mock()
        mock_editor.film_strip_sprites = {'default': mock_sprite}
        mock_editor.film_strips = {'default': mock_strip}
        mock_editor.film_strip_coordinator._update_film_strips_for_pixel_update()
        mock_strip.mark_dirty.assert_called_once()

    def test_update_for_animated_sprite_update(self, mock_editor, mocker):
        """Updates layout and marks dirty on animated sprite update."""
        mock_strip = mocker.Mock()
        mock_sprite = mocker.Mock()
        mock_editor.film_strips = {'default': mock_strip}
        mock_editor.film_strip_sprites = {'default': mock_sprite}
        mock_editor.film_strip_coordinator.update_film_strips_for_animated_sprite_update()
        mock_strip.update_layout.assert_called_once()

    def test_mark_all_film_strips_dirty(self, mock_editor, mocker):
        """Marks all film strips and sprites dirty."""
        mock_strip = mocker.Mock()
        mock_strip.animated_sprite = mocker.Mock()
        mock_sprite = mocker.Mock()
        mock_editor.film_strips = {'default': mock_strip}
        mock_editor.film_strip_sprites = {'default': mock_sprite}
        mock_editor.film_strip_coordinator._mark_all_film_strips_dirty()
        mock_strip.mark_dirty.assert_called_once()
        assert mock_sprite.dirty == 1

    def test_mark_all_no_film_strips(self, mock_editor):
        """Does nothing when no film strips exist."""
        mock_editor.film_strips = {}
        mock_editor.film_strip_coordinator._mark_all_film_strips_dirty()


# ===========================================================================
# 25. Animation Rename Methods
# ===========================================================================


class TestAnimationRename:
    """Tests for on_animation_rename and helper methods."""

    def test_rename_animation(self, mock_editor, mocker):
        """Renames animation in sprite and film strips."""
        mock_strip = mocker.Mock()
        mock_strip.current_animation = 'old_name'
        mock_strip.animated_sprite = mocker.Mock()
        mock_strip.animated_sprite._animations = {'old_name': [mocker.Mock()]}
        mock_strip.animated_sprite._animation_order = ['old_name']
        mock_strip.animated_sprite.frame_manager = mocker.Mock()
        mock_strip.animated_sprite.frame_manager.current_animation = 'old_name'

        mock_editor.film_strips = {'old_name': mock_strip}
        mock_editor.film_strip_sprites = {'old_name': mocker.Mock()}
        mock_editor.canvas.animated_sprite._animations = {'old_name': [mocker.Mock()]}
        mock_editor.canvas.animated_sprite._animation_order = ['old_name']
        mock_editor.selected_animation = 'old_name'

        mocker.patch.object(
            mock_editor.film_strip_coordinator,
            'update_film_strips_for_animated_sprite_update',
        )
        mocker.patch.object(
            mock_editor.film_strip_coordinator,
            '_update_film_strip_layout_after_rename',
        )
        mock_editor.on_animation_rename('old_name', 'new_name')

        # The sprite moves its own per-animation data (real-sprite tests:
        # TestFilmStripAnimationTransitions in tests/tools/test_bitmappy_film_strips.py)
        mock_editor.canvas.animated_sprite.rename_animation.assert_called_once_with(
            old_name='old_name', new_name='new_name'
        )
        assert 'new_name' in mock_editor.film_strips
        assert mock_editor.selected_animation == 'new_name'

    def test_rename_nonexistent_animation(self, mock_editor, mocker):
        """Warns when trying to rename nonexistent animation."""
        mock_editor.canvas.animated_sprite._animations = {'default': [mocker.Mock()]}
        mocker.patch.object(
            mock_editor.film_strip_coordinator,
            'update_film_strips_for_animated_sprite_update',
        )
        mock_editor.on_animation_rename('nonexistent', 'new_name')
        # Should not raise

    def test_get_sprite_to_update(self, mock_editor):
        """Returns canvas animated_sprite for rename."""
        result = mock_editor.film_strip_coordinator._get_sprite_to_update_for_rename()
        assert result == mock_editor.canvas.animated_sprite


# ===========================================================================
# 26. AI-Related Methods
# ===========================================================================


class TestAiMethods:
    """Tests for AI-related methods."""

    def test_handle_ai_unavailable(self, mock_editor):
        """Updates debug text when AI is unavailable."""
        mock_editor._ai_integration._handle_ai_unavailable('req-123')
        assert 'not available' in mock_editor.debug_text.text

    def test_handle_ai_error_message(self, mock_editor):
        """Handles AI error message by showing in debug text."""
        mock_editor.debug_text.text = ''
        mock_editor._ai_integration._handle_ai_error_message(
            'req-123',
            'Sorry I cannot generate sprites',
        )
        assert 'Sorry I cannot generate sprites' in mock_editor.debug_text.text

    def test_handle_ai_error_with_original_prompt(self, mock_editor, mocker):
        """Includes original prompt when handling AI error."""
        request_state = mocker.Mock()
        request_state.original_prompt = 'draw a cat'
        mock_editor._ai_integration.pending_ai_requests = {'req-123': request_state}
        mock_editor.debug_text.text = ''
        mock_editor._ai_integration._handle_ai_error_message('req-123', 'Error content')
        assert 'draw a cat' in mock_editor.debug_text.text

    def test_cleanup_ai_request(self, mock_editor, mocker):
        """Removes request from pending requests."""
        mock_editor._ai_integration.pending_ai_requests = {'req-123': mocker.Mock()}
        mock_editor._ai_integration._cleanup_ai_request('req-123')
        assert 'req-123' not in mock_editor._ai_integration.pending_ai_requests

    def test_cleanup_nonexistent_request(self, mock_editor):
        """Does nothing when request does not exist."""
        mock_editor._ai_integration.pending_ai_requests = {}
        mock_editor._ai_integration._cleanup_ai_request('req-123')

    def test_get_original_prompt(self, mock_editor, mocker):
        """Gets original prompt from pending request."""
        request_state = mocker.Mock()
        request_state.original_prompt = 'draw a dog'
        mock_editor._ai_integration.pending_ai_requests = {'req-456': request_state}
        result = mock_editor._ai_integration._get_original_prompt_for_request('req-456')
        assert result == 'draw a dog'

    def test_get_original_prompt_missing(self, mock_editor):
        """Returns empty string when request is not found."""
        mock_editor._ai_integration.pending_ai_requests = {}
        result = mock_editor._ai_integration._get_original_prompt_for_request('req-789')
        assert not result

    def test_log_ai_response_content(self, mock_editor):
        """Logs AI response content details."""
        content = '[sprite]\n[[animation]]\n[[animation.frame]]\n[[animation.frame]]'
        mock_editor._ai_integration._log_ai_response_content(content)
        # Should not raise

    def test_update_sprite_description(self, mock_editor):
        """Updates animated sprite description."""
        mock_editor._ai_integration._update_sprite_description('a beautiful cat sprite')
        assert mock_editor.canvas.animated_sprite.description == 'a beautiful cat sprite'

    def test_update_sprite_description_empty(self, mock_editor):
        """Does nothing with empty prompt."""
        mock_editor._ai_integration._update_sprite_description('')

    def test_update_sprite_description_no_canvas(self, mock_editor):
        """Does nothing when canvas is not available."""
        mock_editor.canvas = None
        mock_editor._ai_integration._update_sprite_description('test')

    def test_update_conversation_history(self, mock_editor, mocker):
        """Updates conversation history for AI refinement."""
        request_state = mocker.Mock()
        request_state.conversation_history = []
        mock_editor._ai_integration.pending_ai_requests = {'req-1': request_state}
        mock_editor._ai_integration._update_conversation_history(
            'req-1',
            'draw a cat',
            '[sprite]...',
        )
        assert mock_editor._ai_integration.last_conversation_history is not None
        assert len(mock_editor._ai_integration.last_conversation_history) == 2

    def test_update_conversation_history_with_prior(self, mock_editor, mocker):
        """Appends to existing conversation history."""
        request_state = mocker.Mock()
        request_state.conversation_history = [
            {'role': 'user', 'content': 'first request'},
            {'role': 'assistant', 'content': 'first response'},
        ]
        mock_editor._ai_integration.pending_ai_requests = {'req-1': request_state}
        mock_editor._ai_integration._update_conversation_history(
            'req-1',
            'refine it',
            '[sprite]...',
        )
        assert len(mock_editor._ai_integration.last_conversation_history) == 4

    def test_update_ui_after_ai_load(self, mock_editor, mocker):
        """Restores original prompt text after AI load."""
        request_state = mocker.Mock()
        request_state.original_prompt = 'original prompt text'
        mock_editor._ai_integration.pending_ai_requests = {'req-1': request_state}
        mock_editor._ai_integration._update_ui_after_ai_load('req-1')
        assert mock_editor.debug_text.text == 'original prompt text'

    def test_update_ui_after_ai_load_no_request(self, mock_editor):
        """Uses default text when request is not found."""
        mock_editor._ai_integration.pending_ai_requests = {}
        mock_editor._ai_integration._update_ui_after_ai_load('req-1')
        assert 'Enter a description' in mock_editor.debug_text.text

    def test_handle_ai_sprite_load_error(self, mock_editor, mocker):
        """Shows error in debug text."""
        error = ValueError('parse error')
        mock_editor._ai_integration._handle_ai_sprite_load_error(error, 'req-1', 'bad content')
        assert 'parse error' in mock_editor.debug_text.text

    def test_clean_ai_response_error_message(self, mock_editor, mocker):
        """Returns error message as-is."""
        result = mock_editor._ai_integration._clean_ai_response('AI features not available')
        assert result == 'AI features not available'


# ===========================================================================
# 27. Update AI Sprite Position
# ===========================================================================


class TestUpdateAiSpritePosition:
    """Tests for _update_ai_sprite_position."""

    def test_updates_positions_with_color_well(self, mock_editor):
        """Updates AI sprite positions based on color well position."""
        mock_editor._update_ai_sprite_position()
        # Should update rect positions without raising

    def test_updates_positions_without_color_well(self, mock_editor):
        """Updates positions when color well is not available."""
        mock_editor.color_well = None
        mock_editor._update_ai_sprite_position()

    def test_no_ai_label(self, mock_editor):
        """Does nothing when AI label is not initialized."""
        del mock_editor.ai_label
        mock_editor._update_ai_sprite_position()

    def test_positions_below_second_strip(self, mock_editor, mocker):
        """Positions AI sprite below second film strip."""
        strip1 = mocker.Mock()
        strip1.rect = pygame.Rect(400, 24, 400, 145)
        strip2 = mocker.Mock()
        strip2.rect = pygame.Rect(400, 150, 400, 145)
        mock_editor.film_strips = {'a': strip1, 'b': strip2}
        mock_editor._update_ai_sprite_position()
        # Should calculate position below second strip


# ===========================================================================
# 28. Voice Recognition Setup
# ===========================================================================


class TestVoiceRecognition:
    """Tests for EditorSetup.setup_voice_recognition."""

    def test_voice_exception_handling(self, mock_editor, mocker):
        """Handles exceptions during voice setup."""
        mocker.patch.object(bitmappy_setup, 'VoiceEventManager', side_effect=ImportError)
        setup_delegate = bitmappy_setup.EditorSetup(editor=mock_editor)
        setup_delegate.setup_voice_recognition()
        assert mock_editor.voice_manager is None


# ===========================================================================
# 29. New File Event
# ===========================================================================


class TestOnNewFileEvent:
    """Tests for on_new_file_event."""

    def test_creates_new_canvas(self, mock_editor, mocker):
        """Creates new canvas with valid dimensions."""
        mocker.patch.object(mock_editor, '_reset_canvas_for_new_file')
        mocker.patch.object(mock_editor, '_create_fresh_animated_sprite')
        mocker.patch.object(mock_editor.film_strip_coordinator, 'clear_film_strips_for_new_canvas')
        mocker.patch.object(mock_editor, 'clear_ai_sprite_box')
        mocker.patch.object(mock_editor, '_update_ai_sprite_position')
        mock_editor.on_new_file_event('16x16')
        mock_editor._reset_canvas_for_new_file.assert_called_once()

    def test_invalid_dimensions(self, mock_editor, mocker):
        """Handles invalid dimensions format."""
        mocker.patch.object(mock_editor, '_reset_canvas_for_new_file')
        mock_editor.on_new_file_event('invalid')
        assert mock_editor.dirty == 1

    def test_clears_ai_requests(self, mock_editor, mocker):
        """Clears pending AI requests on new file."""
        mock_editor._ai_integration.pending_ai_requests = {'req-1': mocker.Mock()}
        mocker.patch.object(mock_editor, '_reset_canvas_for_new_file')
        mocker.patch.object(mock_editor, '_create_fresh_animated_sprite')
        mocker.patch.object(mock_editor.film_strip_coordinator, 'clear_film_strips_for_new_canvas')
        mocker.patch.object(mock_editor, 'clear_ai_sprite_box')
        mocker.patch.object(mock_editor, '_update_ai_sprite_position')
        mock_editor.on_new_file_event('32x32')
        assert len(mock_editor._ai_integration.pending_ai_requests) == 0


# ===========================================================================
# 30. Apply Frame Paste for Undo/Redo
# ===========================================================================


class TestFramePasteCommandUndoRedo:
    """Tests for FramePasteCommand (replaces _apply_frame_paste_for_undo_redo)."""

    def test_execute_applies_paste(self, mock_editor, mocker):
        """Execute applies pixel data and duration to target frame."""
        from glitchygames.bitmappy.history.commands import FramePasteCommand

        mock_frame = mocker.Mock()
        mock_editor.canvas.animated_sprite.animation_data = {'default': [mock_frame]}
        new_pixels = [(100, 50, 25)] * 1024
        command = FramePasteCommand(
            editor=mock_editor,
            animation='default',
            frame=0,
            old_pixels=[(0, 0, 0)] * 1024,
            old_duration=0.1,
            new_pixels=new_pixels,
            new_duration=0.3,
        )
        result = command.execute()
        assert result is True
        mock_frame.set_pixel_data.assert_called_once_with(new_pixels)
        assert abs(mock_frame.duration - 0.3) < 1e-9

    def test_no_canvas_returns_false(self, mock_editor):
        """Returns False when canvas is not available."""
        from glitchygames.bitmappy.history.commands import FramePasteCommand

        mock_editor.canvas = None
        command = FramePasteCommand(
            editor=mock_editor,
            animation='default',
            frame=0,
            old_pixels=[],
            old_duration=0.1,
            new_pixels=[],
            new_duration=0.5,
        )
        result = command.execute()
        assert result is False

    def test_animation_not_found(self, mock_editor):
        """Returns False when animation is not found."""
        from glitchygames.bitmappy.history.commands import FramePasteCommand

        mock_editor.canvas.animated_sprite.animation_data = {}
        command = FramePasteCommand(
            editor=mock_editor,
            animation='missing',
            frame=0,
            old_pixels=[],
            old_duration=0.1,
            new_pixels=[],
            new_duration=0.5,
        )
        result = command.execute()
        assert result is False

    def test_frame_index_out_of_range(self, mock_editor, mocker):
        """Returns False when frame index is out of range."""
        from glitchygames.bitmappy.history.commands import FramePasteCommand

        mock_editor.canvas.animated_sprite.animation_data = {'default': [mocker.Mock()]}
        command = FramePasteCommand(
            editor=mock_editor,
            animation='default',
            frame=5,
            old_pixels=[],
            old_duration=0.1,
            new_pixels=[],
            new_duration=0.5,
        )
        result = command.execute()
        assert result is False

    def test_updates_canvas_pixels_if_current(self, mock_editor, mocker):
        """Updates canvas pixels when pasting to currently displayed frame."""
        from glitchygames.bitmappy.history.commands import FramePasteCommand

        mock_frame = mocker.Mock()
        mock_editor.canvas.animated_sprite.animation_data = {'default': [mock_frame]}
        mock_editor.selected_animation = 'default'
        mock_editor.selected_frame = 0
        new_pixels = [(100, 50, 25)] * 10
        mock_editor.canvas.pixels = [(0, 0, 0)] * 10
        mock_editor.canvas.dirty_pixels = [False] * 10
        command = FramePasteCommand(
            editor=mock_editor,
            animation='default',
            frame=0,
            old_pixels=[(0, 0, 0)] * 10,
            old_duration=0.1,
            new_pixels=new_pixels,
            new_duration=0.5,
        )
        result = command.execute()
        assert result is True
        assert mock_editor.canvas.pixels == new_pixels


# ===========================================================================
# 31. Slider Text Format Update
# ===========================================================================


class TestUpdateSliderTextFormat:
    """Tests for SliderManager._update_slider_text_format."""

    def test_decimal_format(self, mock_editor):
        """Updates slider text in decimal format."""
        mock_editor.slider_input_format = '%d'
        mock_editor._slider_manager._update_slider_text_format()
        assert mock_editor.red_slider.text_sprite.text == '128'
        assert mock_editor.green_slider.text_sprite.text == '64'
        assert mock_editor.blue_slider.text_sprite.text == '32'

    def test_hex_format(self, mock_editor):
        """Updates slider text in hex format."""
        mock_editor.slider_input_format = '%X'
        mock_editor._slider_manager._update_slider_text_format()
        assert mock_editor.red_slider.text_sprite.text == '80'
        assert mock_editor.green_slider.text_sprite.text == '40'
        assert mock_editor.blue_slider.text_sprite.text == '20'


# ===========================================================================
# 32. Left Mouse Button Up Event
# ===========================================================================


class TestOnLeftMouseButtonUpEvent:
    """Tests for on_left_mouse_button_up_event."""

    def test_stops_film_strip_dragging(self, mock_editor, mocker):
        """Stops film strip drag scrolling."""
        mock_editor.is_dragging_film_strips = True
        event = _make_event(pos=(100, 100))
        mock_editor.on_left_mouse_button_up_event(event)
        assert mock_editor.is_dragging_film_strips is False
        assert mock_editor.film_strip_drag_start_y is None

    def test_delegates_to_sprites(self, mock_editor, mocker):
        """Delegates event to sprites at position."""
        mock_sprite = mocker.Mock()
        mock_editor.sprites_at_position.return_value = [mock_sprite]
        event = _make_event(pos=(100, 100))
        mock_editor.on_left_mouse_button_up_event(event)
        mock_sprite.on_left_mouse_button_up_event.assert_called_once_with(event)


# ===========================================================================
# 33. Mouse Button Up Event
# ===========================================================================


class TestOnMouseButtonUpEvent:
    """Tests for on_mouse_button_up_event."""

    def test_debug_text_handles_event(self, mock_editor, mocker):
        """Delegates to debug text when click is in its area."""
        mock_editor.debug_text.rect = pygame.Rect(400, 400, 300, 186)
        event = _make_event(pos=(450, 450))
        mock_editor.on_mouse_button_up_event(event)
        mock_editor.debug_text.on_mouse_up_event.assert_called_once()

    def test_mouse_up_resets_drag_state(self, mock_editor, mocker):
        """Mouse button up always resets the drag operation flag."""
        mock_editor._is_drag_operation = True
        mock_editor.current_pixel_changes = []
        # all_sprites is iterated in on_mouse_button_up_event, make it iterable
        mock_editor.all_sprites = []
        event = _make_event(pos=(0, 0))
        mock_editor.on_mouse_button_up_event(event)
        assert mock_editor._is_drag_operation is False


# ===========================================================================
# 34. Left Mouse Drag Event
# ===========================================================================


class TestOnLeftMouseDragEvent:
    """Tests for on_left_mouse_drag_event."""

    def test_film_strip_drag(self, mock_editor, mocker):
        """Handles film strip drag scrolling."""
        mock_editor.is_dragging_film_strips = True
        event = _make_event(pos=(500, 200))
        trigger = mocker.Mock()
        mocker.patch.object(mock_editor.film_strip_coordinator, 'handle_film_strip_drag_scroll')
        mock_editor.on_left_mouse_drag_event(event, trigger)
        mock_editor.film_strip_coordinator.handle_film_strip_drag_scroll.assert_called_once_with(
            200,
        )

    def test_canvas_drag_optimized(self, mock_editor, mocker):
        """Optimizes drag on canvas by skipping sprite iteration."""
        event = _make_event(pos=(100, 100))  # Inside canvas rect
        trigger = mocker.Mock()
        mock_editor.on_left_mouse_drag_event(event, trigger)
        mock_editor.canvas.on_left_mouse_drag_event.assert_called_once_with(event, trigger)


# ===========================================================================
# 35. Slider Hover Effects
# ===========================================================================


class TestSliderBboxHover:
    """Tests for SliderManager._update_slider_bbox_hover."""

    def test_hover_shows_border(self, mock_editor, mocker):
        """Hovering draws a 2-pixel border in the colour and leaves the inside transparent."""
        mock_editor._slider_manager._update_slider_bbox_hover(
            'red_slider_bbox',
            is_hovered=True,
            border_color=(255, 0, 0),
        )
        bbox = mock_editor._slider_manager.red_slider_bbox
        assert bbox.visible is True
        assert bbox.dirty == 1
        width, height = bbox.rect.size
        for border_pixel in ((0, 0), (1, 1), (width - 1, height - 1), (width // 2, 0)):
            assert tuple(bbox.image.get_at(border_pixel)) == (255, 0, 0, 255)
        # Alpha is the point here: the box must not cover the slider it surrounds
        assert bbox.image.get_at((width // 2, height // 2)).a == 0

    def test_unhover_hides_border(self, mock_editor, mocker):
        """Hides border on unhover."""
        mock_editor._slider_manager.red_slider_bbox.visible = True
        mock_editor._slider_manager._update_slider_bbox_hover(
            'red_slider_bbox',
            is_hovered=False,
            border_color=(255, 0, 0),
        )
        assert mock_editor._slider_manager.red_slider_bbox.visible is False

    def test_already_visible_no_change(self, mock_editor, mocker):
        """No change when already hovered and still hovering: nothing is redrawn."""
        bbox = mock_editor._slider_manager.red_slider_bbox
        bbox.visible = True
        bbox.dirty = 0
        mock_editor._slider_manager._update_slider_bbox_hover(
            'red_slider_bbox',
            is_hovered=True,
            border_color=(255, 0, 0),
        )
        assert bbox.visible is True
        assert bbox.dirty == 0
        assert bbox.image.get_at((0, 0)).a == 0

    def test_nonexistent_bbox(self, mock_editor):
        """Does nothing when bbox attribute does not exist."""
        mock_editor._slider_manager._update_slider_bbox_hover(
            'nonexistent_bbox',
            is_hovered=True,
            border_color=(255, 0, 0),
        )


# ===========================================================================
# 36. Slider Text Hover Border
# ===========================================================================


class TestSliderTextHoverBorder:
    """Tests for SliderManager._update_slider_text_hover_border."""

    def test_add_hover_border(self, mock_editor, mocker):
        """Adds white border on hover."""
        mock_editor.red_slider.text_sprite.hover_border_added = False
        del mock_editor.red_slider.text_sprite.hover_border_added
        text_image = pygame.Surface((50, 10), flags=0, depth=32)
        text_image.fill((0, 0, 0))
        mock_editor.red_slider.text_sprite.image = text_image
        mock_editor.red_slider.text_sprite.rect = pygame.Rect(0, 0, 50, 10)
        mock_editor._slider_manager._update_slider_text_hover_border(
            'red_slider',
            is_text_hovered=True,
        )
        assert mock_editor.red_slider.text_sprite.hover_border_added is True
        assert mock_editor.red_slider.text_sprite.dirty == 1
        # A white 2-pixel border around the text, the inside left as it was
        for border_pixel in ((0, 0), (1, 1), (49, 9), (25, 0), (0, 5)):
            assert tuple(text_image.get_at(border_pixel))[:3] == (255, 255, 255)
        assert tuple(text_image.get_at((25, 5)))[:3] == (0, 0, 0)

    def test_remove_hover_border(self, mock_editor, mocker):
        """Removes hover border when no longer hovering."""
        mock_editor.red_slider.text_sprite.hover_border_added = True
        mock_editor._slider_manager._update_slider_text_hover_border(
            'red_slider',
            is_text_hovered=False,
        )
        assert mock_editor.red_slider.text_sprite.hover_border_added is False

    def test_nonexistent_slider(self, mock_editor):
        """Does nothing for nonexistent slider."""
        mock_editor._slider_manager._update_slider_text_hover_border(
            'nonexistent_slider',
            is_text_hovered=True,
        )


# ===========================================================================
# 37. Has Single Animation Canvas
# ===========================================================================


class TestHasSingleAnimationCanvas:
    """Tests for _has_single_animation_canvas."""

    def test_single_animation(self, mock_editor, mocker):
        """Returns True for single animation."""
        mock_editor.canvas.animated_sprite.animations = {'only': [mocker.Mock()]}
        assert mock_editor._ai_integration._has_single_animation_canvas() is True

    def test_multiple_animations(self, mock_editor, mocker):
        """Returns False for multiple animations."""
        mock_editor.canvas.animated_sprite.animations = {
            'a': [mocker.Mock()],
            'b': [mocker.Mock()],
        }
        assert mock_editor._ai_integration._has_single_animation_canvas() is False

    def test_no_canvas(self, mock_editor):
        """Returns False when canvas is not available."""
        mock_editor.canvas = None
        assert mock_editor._ai_integration._has_single_animation_canvas() is False

    def test_no_animated_sprite(self, mock_editor):
        """Returns False when animated sprite is not available."""
        mock_editor.canvas.animated_sprite = None
        assert mock_editor._ai_integration._has_single_animation_canvas() is False


# ===========================================================================
# 38. On Debug Text Change
# ===========================================================================


class TestOnDebugTextChange:
    """Tests for _on_debug_text_change."""

    def test_calls_update_sprite_description(self, mock_editor, mocker):
        """Delegates to _update_sprite_description."""
        mocker.patch.object(mock_editor._ai_integration, '_update_sprite_description')
        mock_editor._ai_integration._on_debug_text_change('new description')
        mock_editor._ai_integration._update_sprite_description.assert_called_once_with(
            'new description',
        )


# ===========================================================================
# 39. Check Current Frame Has Content
# ===========================================================================


class TestCheckCurrentFrameHasContent:
    """Tests for _check_current_frame_has_content."""

    def test_all_magenta_returns_false(self, mock_editor, mocker):
        """Returns False when all pixels are magenta."""
        mock_editor.canvas.pixels = [(255, 0, 255)] * 100
        # _pixel_to_rgb is called by the method - attach it to the instance
        mock_editor._pixel_to_rgb = lambda pixel: pixel[:3] if isinstance(pixel, tuple) else pixel
        result = mock_editor._ai_integration._check_current_frame_has_content()
        assert result is False

    def test_has_non_magenta_returns_true(self, mock_editor, mocker):
        """Returns True when there are non-magenta pixels."""
        mock_editor.canvas.pixels = [(255, 0, 255)] * 99 + [(100, 50, 25)]
        mock_editor._pixel_to_rgb = lambda pixel: pixel[:3] if isinstance(pixel, tuple) else pixel
        result = mock_editor._ai_integration._check_current_frame_has_content()
        assert result is True

    def test_no_canvas(self, mock_editor):
        """Returns False when canvas is not available."""
        del mock_editor.canvas
        result = mock_editor._ai_integration._check_current_frame_has_content()
        assert result is False

    def test_empty_pixels(self, mock_editor, mocker):
        """Returns False when pixels list is empty."""
        mock_editor.canvas.pixels = []
        result = mock_editor._ai_integration._check_current_frame_has_content()
        assert result is False


# ===========================================================================
# 40. Refresh All Film Strip Widgets
# ===========================================================================


class TestRefreshAllFilmStripWidgets:
    """Tests for _refresh_all_film_strip_widgets."""

    def test_no_film_strip_sprites(self, mock_editor):
        """Does nothing when no film strip sprites exist."""
        mock_editor.film_strip_sprites = {}
        mock_editor.film_strip_coordinator.refresh_all_film_strip_widgets()

    def test_refreshes_all_sprites(self, mock_editor, mocker):
        """Refreshes all film strip sprite widgets."""
        mock_widget = mocker.Mock()
        mock_sprite = mocker.Mock()
        mock_sprite.film_strip_widget = mock_widget
        mock_editor.film_strip_sprites = {'default': mock_sprite}
        mock_editor.film_strip_coordinator.refresh_all_film_strip_widgets()
        mock_widget._initialize_preview_animations.assert_called_once()
        mock_widget.update_layout.assert_called_once()

    def test_refreshes_with_animation_name(self, mock_editor, mocker):
        """Updates frame selection when animation_name is provided."""
        mock_widget = mocker.Mock()
        mock_sprite = mocker.Mock()
        mock_sprite.film_strip_widget = mock_widget
        mock_editor.film_strip_sprites = {'default': mock_sprite}
        mock_editor.canvas.current_animation = 'default'
        mock_editor.canvas.current_frame = 1
        mock_editor.film_strip_coordinator.refresh_all_film_strip_widgets(animation_name='default')
        mock_widget.set_frame_index.assert_called_once_with(1)


# ===========================================================================
# 41. Canvas Operation Methods
# ===========================================================================


class TestResetCanvasForNewFile:
    """Tests for _reset_canvas_for_new_file."""

    def test_resets_dimensions(self, mock_editor, mocker):
        """Resets canvas dimensions and pixels."""
        mock_editor._reset_canvas_for_new_file(16, 16, 20)
        assert mock_editor.canvas.pixels_across == 16
        assert mock_editor.canvas.pixels_tall == 16
        assert mock_editor.canvas.pixel_width == 20
        assert len(mock_editor.canvas.pixels) == 256

    def test_ends_the_pan_in_progress(self, mock_editor):
        """Ends the old canvas's pan gesture."""
        mock_editor._reset_canvas_for_new_file(32, 32, 10)
        mock_editor.canvas.end_panning.assert_called_once()


# ===========================================================================
# 42. Clear Film Strips for New Canvas
# ===========================================================================


class TestClearFilmStripsForNewCanvas:
    """Tests for _clear_film_strips_for_new_canvas."""

    def test_clears_existing_strips(self, mock_editor, mocker):
        """Clears and recreates film strips."""
        mock_sprite = mocker.Mock()
        mock_group = mocker.Mock()
        mock_sprite.groups.return_value = [mock_group]
        mock_editor.film_strips = {'default': mocker.Mock()}
        mock_editor.film_strip_sprites = {'default': mock_sprite}
        mocker.patch.object(mock_editor.film_strip_coordinator, '_create_film_strips')
        mock_editor.film_strip_coordinator.clear_film_strips_for_new_canvas()
        assert len(mock_editor.film_strips) == 0
        assert len(mock_editor.film_strip_sprites) == 0

    def test_no_existing_strips(self, mock_editor, mocker):
        """Creates film strips even when none exist."""
        mock_editor.film_strips = {}
        mock_editor.film_strip_sprites = {}
        mocker.patch.object(mock_editor.film_strip_coordinator, '_create_film_strips')
        mock_editor.film_strip_coordinator.clear_film_strips_for_new_canvas()
        mock_editor.film_strip_coordinator._create_film_strips.assert_called_once()


# ===========================================================================
# 43. Continuous Movement/Adjustment Methods
# ===========================================================================


class TestContinuousMovement:
    """Tests for continuous canvas movement and slider adjustment methods."""

    def test_start_canvas_continuous_movement(self, mock_editor, mocker):
        """Starts continuous canvas movement."""
        mock_editor.mode_switcher.get_controller_position.return_value = mocker.Mock(
            position=(5, 10),
        )
        mocker.patch.object(mock_editor.controller_handler.canvas, '_canvas_move_cursor')
        mock_editor.controller_handler.canvas.start_canvas_continuous_movement(0, 1, 0)
        assert 0 in mock_editor.controller_handler.canvas_continuous_movements
        mock_editor.controller_handler.canvas._canvas_move_cursor.assert_called_once_with(0, 1, 0)

    def test_stop_canvas_continuous_movement(self, mock_editor, mocker):
        """Stops continuous canvas movement."""
        movements = {
            0: {
                'dx': 1,
                'dy': 0,
                'start_time': time.time(),
                'last_movement': time.time(),
                'acceleration_level': 0,
                'start_x': 5,
                'start_y': 10,
            },
        }
        mock_editor.controller_handler.canvas_continuous_movements = movements
        mock_editor.canvas_continuous_movements = movements
        mock_editor.mode_switcher.get_controller_position.return_value = mocker.Mock(
            position=(6, 10),
        )
        mock_editor.mode_switcher.get_controller_mode.return_value = mocker.Mock(value='canvas')
        mock_editor.controller_handler.canvas.stop_canvas_continuous_movement(0)
        assert 0 not in mock_editor.controller_handler.canvas_continuous_movements

    def test_stop_nonexistent_movement(self, mock_editor):
        """Does nothing when stopping nonexistent movement."""
        mock_editor.controller_handler.canvas_continuous_movements = {}
        mock_editor.controller_handler.canvas.stop_canvas_continuous_movement(0)

    def test_update_canvas_no_movements(self, mock_editor):
        """Does nothing when no continuous movements exist."""
        mock_editor.controller_handler.canvas_continuous_movements = {}
        mock_editor.controller_handler.canvas.update_canvas_continuous_movements()


# ===========================================================================
# 44. Detect Clicked Slider
# ===========================================================================


class TestDetectClickedSlider:
    """Tests for SliderManager.detect_clicked_slider."""

    def test_detects_red_slider(self, mock_editor):
        """Detects click on red slider text sprite."""
        mock_editor.red_slider.text_sprite.rect = pygame.Rect(270, 550, 50, 10)
        result = mock_editor._slider_manager.detect_clicked_slider((280, 555))
        assert result is mock_editor.red_slider

    def test_detects_green_slider(self, mock_editor):
        """Detects click on green slider text sprite."""
        mock_editor.green_slider.text_sprite.rect = pygame.Rect(270, 560, 50, 10)
        result = mock_editor._slider_manager.detect_clicked_slider((280, 565))
        assert result is mock_editor.green_slider

    def test_detects_blue_slider(self, mock_editor):
        """Detects click on blue slider text sprite."""
        mock_editor.blue_slider.text_sprite.rect = pygame.Rect(270, 570, 50, 10)
        result = mock_editor._slider_manager.detect_clicked_slider((280, 575))
        assert result is mock_editor.blue_slider

    def test_no_slider_clicked(self, mock_editor):
        """Returns None when no slider is clicked."""
        result = mock_editor._slider_manager.detect_clicked_slider((0, 0))
        assert result is None


# ===========================================================================
# 45. Rename Film Strip Dict Methods
# ===========================================================================


class TestRenameFilmStripDict:
    """Tests for _rename_in_film_strips_dict."""

    def test_renames_entry(self, mock_editor, mocker):
        """Renames film strip dict entry."""
        mock_strip = mocker.Mock()
        mock_strip.current_animation = 'old'
        mock_strip.animated_sprite = mocker.Mock()
        mock_strip.animated_sprite._animations = {'old': [mocker.Mock()]}
        mock_strip.animated_sprite._animation_order = ['old']
        mock_strip.animated_sprite.frame_manager = mocker.Mock()
        mock_strip.animated_sprite.frame_manager.current_animation = 'old'
        mock_editor.film_strips = {'old': mock_strip}
        mock_editor.film_strip_sprites = {'old': mocker.Mock()}
        mocker.patch.object(
            mock_editor.film_strip_coordinator,
            '_update_film_strip_layout_after_rename',
        )
        mock_editor.film_strip_coordinator._rename_in_film_strips_dict('old', 'new')
        assert 'new' in mock_editor.film_strips
        assert 'old' not in mock_editor.film_strips

    def test_rename_nonexistent(self, mock_editor):
        """Does nothing when old name does not exist."""
        mock_editor.film_strips = {}
        mock_editor.film_strip_coordinator._rename_in_film_strips_dict('old', 'new')


# ===========================================================================
# 46. Film Strip Animation Timing
# ===========================================================================


class TestUpdateFilmStripAnimationTiming:
    """Tests for _update_film_strip_animation_timing."""

    def test_updates_animations(self, mock_editor, mocker):
        """Updates animations on all film strips."""
        mock_strip = mocker.Mock()
        mock_editor.film_strips = {'default': mock_strip}
        mock_editor.film_strip_coordinator.update_film_strip_animation_timing()
        mock_strip.update_animations.assert_called_once()

    def test_no_film_strips(self, mock_editor, mocker):
        """Does nothing with no film strips."""
        mock_editor.film_strips = {}
        mock_editor.film_strip_sprites = {}
        mock_editor.film_strip_coordinator.update_film_strip_animation_timing()


# ===========================================================================
# 47. Is AI Error Message
# ===========================================================================


class TestIsAiErrorMessage:
    """Tests for _is_ai_error_message."""

    def test_valid_sprite_content(self, mock_editor, mocker):
        """Returns False for valid sprite content."""
        mocker.patch(
            'glitchygames.bitmappy.ai_manager.validate_ai_response',
            return_value=(True, None),
        )
        result = mock_editor._ai_integration._is_ai_error_message('[sprite]\nname = "test"')
        assert result is False

    def test_error_content(self, mock_editor, mocker):
        """Returns True for error/apology content."""
        mocker.patch(
            'glitchygames.bitmappy.ai_manager.validate_ai_response',
            return_value=(False, 'Missing sprite section'),
        )
        result = mock_editor._ai_integration._is_ai_error_message(
            'I apologize, I cannot generate that',
        )
        assert result is True


class TestProcessAiResponseErrors:
    """Tests for _process_ai_response when the worker reports an error."""

    def test_worker_error_is_shown_to_user(self, mock_editor):
        """Shows the worker's error text instead of a generic 'empty' message."""
        mock_editor._ai_integration.pending_ai_requests['req_1'] = AIRequestState(
            original_prompt='draw a cat',
        )
        response = AIResponse(
            content=None,
            error='BadRequestError: Your credit balance is too low to access the Anthropic API.',
        )

        mock_editor._ai_integration._process_ai_response('req_1', response)

        assert 'credit balance is too low' in mock_editor.debug_text.text
        assert 'req_1' not in mock_editor._ai_integration.pending_ai_requests

    def test_empty_response_without_error_keeps_generic_message(self, mock_editor):
        """Falls back to the generic message when no error detail is available."""
        response = AIResponse(content=None)

        mock_editor._ai_integration._process_ai_response('req_2', response)

        assert mock_editor.debug_text.text == 'AI response was empty'


# ===========================================================================
# 48. Ensure Default Animation Exists
# ===========================================================================


class TestEnsureDefaultAnimationExists:
    """Tests for _ensure_default_animation_exists."""

    def test_already_has_animations(self, mock_editor, mocker):
        """Does nothing when animations already exist."""
        animated_sprite = mocker.Mock()
        animated_sprite._animations = {'walk': [mocker.Mock()]}
        mock_editor.film_strip_coordinator._ensure_default_animation_exists(animated_sprite)
        # Should not modify existing animations

    def test_creates_default_animation(self, mock_editor, mocker):
        """Creates default animation when none exist."""
        animated_sprite = mocker.Mock()
        animated_sprite._animations = {}
        mock_editor.canvas.pixels_across = 16
        mock_editor.canvas.pixels_tall = 16
        mock_editor.film_strip_coordinator._ensure_default_animation_exists(animated_sprite)
        assert 'default' in animated_sprite._animations


# ===========================================================================
# 49. Calculate Film Strip Dimensions
# ===========================================================================


class TestCalculateFilmStripDimensions:
    """Tests for _calculate_film_strip_dimensions."""

    def test_with_color_well(self, mock_editor):
        """Calculates dimensions using color well position."""
        film_strip_x, _film_strip_width = (
            mock_editor.film_strip_coordinator._calculate_film_strip_dimensions()
        )
        # Color well right is 340 (300 + 40), so film_strip_x = 341
        assert film_strip_x == 341

    def test_without_color_well(self, mock_editor):
        """Calculates dimensions using canvas position."""
        mock_editor.color_well = None
        film_strip_x, _film_strip_width = (
            mock_editor.film_strip_coordinator._calculate_film_strip_dimensions()
        )
        # Canvas rect right is 320, so film_strip_x = 324
        assert film_strip_x == 324


# ===========================================================================
# 50. Finalize Canvas Setup
# ===========================================================================


class TestFinalizeCanvasSetup:
    """Tests for EditorSetup._finalize_canvas_setup (static method)."""

    def test_starts_animation(self, mocker):
        """Starts animation and leaves no class-wide canvas size (BUGS.md #110 item 2)."""
        animated_sprite = mocker.Mock()
        bitmappy_setup.EditorSetup._finalize_canvas_setup(animated_sprite)
        animated_sprite.play.assert_called_once()
        assert 'WIDTH' not in vars(bitmappy_setup.AnimatedCanvasSprite)
        assert 'HEIGHT' not in vars(bitmappy_setup.AnimatedCanvasSprite)


# ===========================================================================
# 51. Adjust Selected Frame After Removal
# ===========================================================================


class TestAdjustSelectedFrameAfterRemoval:
    """Tests for _adjust_selected_frame_after_removal."""

    def test_decrements_frame_index(self, mock_editor, mocker):
        """Decrements selected frame when frame before it is removed."""
        mock_editor.selected_frame = 2
        mock_editor.canvas.animated_sprite._animations = {
            'default': [mocker.Mock(), mocker.Mock(), mocker.Mock()],
        }
        mock_editor.film_strip_coordinator._adjust_selected_frame_after_removal('default', 1)
        assert mock_editor.selected_frame == 1

    def test_stays_at_zero(self, mock_editor, mocker):
        """Stays at frame 0 when frame 0 is removed."""
        mock_editor.selected_frame = 0
        mock_editor.canvas.animated_sprite._animations = {
            'default': [mocker.Mock()],
        }
        mock_editor.film_strip_coordinator._adjust_selected_frame_after_removal('default', 0)
        assert mock_editor.selected_frame == 0

    def test_clamps_to_max_frame(self, mock_editor, mocker):
        """Clamps to max frame when out of bounds."""
        mock_editor.selected_frame = 5
        mock_editor.canvas.animated_sprite._animations = {
            'default': [mocker.Mock()],
        }
        mock_editor.film_strip_coordinator._adjust_selected_frame_after_removal('default', 0)
        assert mock_editor.selected_frame == 0


# ===========================================================================
# 52. Get Glyph for Color
# ===========================================================================


class TestGetGlyphForColor:
    """Tests for _get_glyph_for_color."""

    def test_returns_single_char(self, mock_editor):
        """Returns a single character glyph."""
        result = mock_editor._ai_integration._get_glyph_for_color((255, 0, 0))
        assert len(result) == 1

    def test_consistent_mapping(self, mock_editor):
        """Same color always returns same glyph."""
        result1 = mock_editor._ai_integration._get_glyph_for_color((100, 200, 50))
        result2 = mock_editor._ai_integration._get_glyph_for_color((100, 200, 50))
        assert result1 == result2

    def test_different_colors_may_differ(self, mock_editor):
        """Different colors can return different glyphs."""
        result1 = mock_editor._ai_integration._get_glyph_for_color((0, 0, 0))
        result2 = mock_editor._ai_integration._get_glyph_for_color((255, 255, 255))
        # They could potentially hash to the same slot, but likely different
        assert isinstance(result1, str)
        assert isinstance(result2, str)


# ===========================================================================
# 53. AI Sprite Position With Film Strips In Transition
# ===========================================================================


class TestUpdateAiSpritePositionDuringTransition:
    """Tests for _update_ai_sprite_position while film strips are being rebuilt."""

    def test_second_strip_without_rect_places_the_box_at_the_top(self, mock_editor):
        """A second strip that has no rect yet counts as ending at y=0."""
        mock_editor.film_strips = {
            'idle': SimpleNamespace(rect=pygame.Rect(400, 24, 400, 145)),
            'walk': SimpleNamespace(),
        }

        mock_editor._update_ai_sprite_position()

        assert mock_editor.debug_text.rect.y == 30
        assert mock_editor.ai_label.rect.y == 10

    def test_film_strips_failing_mid_read_place_the_box_at_the_top(self, mock_editor, mocker):
        """A film strip mapping that fails while being read counts as ending at y=0."""
        film_strips = mocker.MagicMock()
        film_strips.__bool__.return_value = True
        film_strips.__len__.return_value = 2
        film_strips.values.side_effect = KeyError('strip removed')
        mock_editor.film_strips = film_strips

        mock_editor._update_ai_sprite_position()

        assert mock_editor.debug_text.rect.y == 30

    def test_box_below_second_strip_spans_from_color_well_to_screen_edge(self, mock_editor):
        """The box starts right of the color well and sits 30 pixels below the second strip."""
        mock_editor.film_strips = {
            'idle': SimpleNamespace(rect=pygame.Rect(400, 24, 400, 100)),
            'walk': SimpleNamespace(rect=pygame.Rect(400, 124, 400, 100)),
        }

        mock_editor._update_ai_sprite_position()

        assert mock_editor.debug_text.rect.x == mock_editor.color_well.rect.right + 1
        assert mock_editor.debug_text.rect.width == 800 - (mock_editor.color_well.rect.right + 1)
        assert mock_editor.debug_text.rect.y == 224 + 30


# ===========================================================================
# 54. New Canvas Creation
# ===========================================================================


class TestNewCanvasCreation:
    """Tests for _reset_canvas_for_new_file, _create_fresh_animated_sprite and on_new_file_event."""

    def test_fresh_animated_sprite_is_one_magenta_frame(self, mock_editor):
        """The fresh sprite has a single magenta 'default' frame and a matching canvas image."""
        mock_editor._create_fresh_animated_sprite(3, 2, 10)

        fresh_sprite = mock_editor.canvas.animated_sprite
        assert fresh_sprite.name == 'new_canvas'
        assert list(fresh_sprite._animations) == ['default']
        frames = fresh_sprite._animations['default']
        assert len(frames) == 1
        assert frames[0].get_pixel_data() == [(255, 0, 255)] * 6
        assert fresh_sprite.frame_manager.current_animation == 'default'
        assert mock_editor.canvas.image.get_size() == (30, 20)
        assert mock_editor.canvas.rect.topleft == (0, 24)
        mock_editor.canvas.force_redraw.assert_called_once()

    def test_new_file_without_ai_integration(self, mock_editor, mocker):
        """A new file still resets the canvas when no AI integration exists."""
        del mock_editor._ai_integration
        mock_editor.debug_text.text = 'previous prompt'
        mocker.patch.object(mock_editor.film_strip_coordinator, 'clear_film_strips_for_new_canvas')
        mocker.patch.object(mock_editor, '_update_ai_sprite_position')

        mock_editor.on_new_file_event('8x4')

        assert mock_editor.canvas.pixels_across == 8
        assert mock_editor.canvas.pixels_tall == 4
        assert len(mock_editor.canvas.animated_sprite._animations['default']) == 1
        assert not mock_editor.debug_text.text
        assert mock_editor.dirty == 1


# ===========================================================================
# 55. Right Mouse Button Colour Sampling
# ===========================================================================


def _held_keys(*keys):
    """Build a polled-input stand-in with the given keys held.

    Args:
        *keys: The pygame key codes that are held.

    Returns:
        SimpleNamespace: An object answering key_pressed(key).

    """
    return SimpleNamespace(key_pressed=lambda key: key in keys)


def _slider_values(editor):
    """Read the four slider values.

    Args:
        editor: The editor scene.

    Returns:
        tuple: (red, green, blue, alpha).

    """
    return (
        editor.red_slider.value,
        editor.green_slider.value,
        editor.blue_slider.value,
        editor.alpha_slider.value,
    )


class TestRightMouseButtonSampling:
    """Tests for on_right_mouse_button_up_event and _sample_canvas_pixel."""

    @pytest.fixture(autouse=True)
    def _no_held_keys(self, mocker):
        """Answer polled input with no keys held."""
        mocker.patch.object(bitmappy, 'current_input', return_value=_held_keys())

    def test_sprite_that_handles_the_click_stops_sampling(self, mock_editor, mocker):
        """A sprite that handles the right click keeps the sliders unchanged."""
        handling_sprite = mocker.Mock()
        handling_sprite.on_right_mouse_button_up_event.return_value = True
        mock_editor.sprites_at_position = mocker.Mock(return_value=[handling_sprite])

        mock_editor.on_right_mouse_button_up_event(_make_event(pos=(5, 30)))

        assert _slider_values(mock_editor) == (128, 64, 32, 255)

    def test_sprite_without_a_right_click_handler_is_skipped(self, mock_editor, mocker):
        """A sprite under the cursor with no right click handler lets the canvas sample."""
        mock_editor.sprites_at_position = mocker.Mock(return_value=[SimpleNamespace()])
        mock_editor.canvas.pixels[0] = (11, 22, 33, 44)

        mock_editor.on_right_mouse_button_up_event(_make_event(pos=(1, 25)))

        assert _slider_values(mock_editor) == (11, 22, 33, 44)

    def test_canvas_rgba_pixel_sets_all_four_sliders(self, mock_editor, mocker):
        """A right click on the canvas samples the RGBA pixel under the cursor."""
        unhandling_sprite = mocker.Mock()
        unhandling_sprite.on_right_mouse_button_up_event.return_value = False
        mock_editor.sprites_at_position = mocker.Mock(return_value=[unhandling_sprite])
        # Pixel (2, 1) on a 32-wide canvas of 10-pixel cells at (0, 24)
        mock_editor.canvas.pixels[1 * 32 + 2] = (10, 20, 30, 40)

        mock_editor.on_right_mouse_button_up_event(_make_event(pos=(25, 24 + 15)))

        assert _slider_values(mock_editor) == (10, 20, 30, 40)

    def test_canvas_rgb_pixel_samples_as_opaque(self, mock_editor):
        """An RGB canvas pixel is sampled with alpha 255."""
        mock_editor.alpha_slider.value = 7
        mock_editor.canvas.pixels[0] = (1, 2, 3)

        mock_editor.on_right_mouse_button_up_event(_make_event(pos=(1, 25)))

        assert _slider_values(mock_editor) == (1, 2, 3, 255)

    def test_shift_right_click_on_canvas_samples_the_screen(self, mock_editor, mocker):
        """Shift held while right clicking the canvas samples the screen instead."""
        mocker.patch.object(bitmappy, 'current_input', return_value=_held_keys(pygame.K_RSHIFT))
        sample_from_screen = mocker.patch.object(
            mock_editor._slider_manager,
            'sample_color_from_screen',
        )

        mock_editor.on_right_mouse_button_up_event(_make_event(pos=(5, 30)))

        sample_from_screen.assert_called_once_with((5, 30))
        assert _slider_values(mock_editor) == (128, 64, 32, 255)

    def test_click_off_canvas_samples_the_screen_as_opaque(self, mock_editor):
        """Outside the canvas, the screen pixel is sampled and alpha set to 255."""
        screen = pygame.Surface((800, 600), pygame.SRCALPHA)
        screen.fill((90, 80, 70, 10))
        mock_editor.screen = screen
        mock_editor.alpha_slider.value = 3

        mock_editor.on_right_mouse_button_up_event(_make_event(pos=(500, 500)))

        assert _slider_values(mock_editor) == (90, 80, 70, 255)

    def test_click_off_screen_changes_nothing(self, mock_editor):
        """A position outside the screen surface is ignored."""
        mock_editor.screen = pygame.Surface((800, 600))

        mock_editor.on_right_mouse_button_up_event(_make_event(pos=(900, 900)))

        assert _slider_values(mock_editor) == (128, 64, 32, 255)

    def test_canvas_rect_beyond_pixel_grid_is_not_sampled(self, mock_editor):
        """A point in the canvas rect but past the pixel grid is not a canvas pixel."""
        mock_editor.canvas.pixels_across = 2

        assert (
            mock_editor._sample_canvas_pixel(_make_event(pos=(100, 30)), is_shift_click=False)
            is False
        )

    def test_pixel_index_beyond_pixel_data_is_not_sampled(self, mock_editor):
        """A grid position with no pixel data behind it is not sampled."""
        mock_editor.canvas.pixels = [(1, 2, 3)]

        assert (
            mock_editor._sample_canvas_pixel(_make_event(pos=(15, 25)), is_shift_click=False)
            is False
        )


# ===========================================================================
# 56. Left Mouse Button Down
# ===========================================================================


class TestOnLeftMouseButtonDownEvent:
    """Tests for on_left_mouse_button_down_event and _handle_scroll_arrow_click."""

    def test_visible_up_arrow_goes_to_previous_animation(self, mock_editor, mocker):
        """Clicking the visible up arrow moves the canvas to the previous animation."""
        up_arrow = SimpleNamespace(direction='up', visible=True)
        mock_editor.sprites_at_position = mocker.Mock(return_value=[up_arrow])
        mocker.patch.object(mock_editor.film_strip_coordinator, 'scroll_to_current_animation')
        mocker.patch.object(
            mock_editor.film_strip_coordinator,
            'update_film_strips_for_animated_sprite_update',
        )

        mock_editor.on_left_mouse_button_down_event(_make_event(pos=(10, 10)))

        mock_editor.canvas.previous_animation.assert_called_once()
        assert mock_editor.is_dragging_film_strips is False

    def test_up_arrow_without_canvas_is_still_consumed(self, mock_editor, mocker):
        """With no canvas the up arrow click is consumed without navigating."""
        mock_editor.canvas = None
        up_arrow = SimpleNamespace(direction='up', visible=True)

        assert mock_editor._handle_scroll_arrow_click([up_arrow]) is True

    def test_hidden_and_other_arrows_are_not_consumed(self, mock_editor):
        """Hidden arrows and arrows of other directions do not consume the click."""
        hidden_up_arrow = SimpleNamespace(direction='up', visible=False)
        down_arrow = SimpleNamespace(direction='down', visible=True)

        assert mock_editor._handle_scroll_arrow_click([hidden_up_arrow, down_arrow]) is False

    def test_clicked_slider_gets_the_click_and_drag_scroll_starts(self, mock_editor, mocker):
        """A click on a slider's text box reaches that slider, and film strip dragging starts."""
        mocker.patch.object(
            mock_editor._slider_manager,
            'detect_clicked_slider',
            return_value=mock_editor.green_slider,
        )
        mocker.patch.object(mock_editor._slider_manager, 'commit_slider_text_boxes')
        mocker.patch.object(
            mock_editor.film_strip_coordinator,
            'is_mouse_in_film_strip_area',
            return_value=True,
        )
        other_sprite = mocker.Mock(spec=['on_left_mouse_button_down_event'])
        mock_editor.sprites_at_position = mocker.Mock(return_value=[other_sprite])
        mock_editor.film_strip_scroll_offset = 3
        event = _make_event(pos=(15, 562))

        mock_editor.on_left_mouse_button_down_event(event)

        mock_editor.green_slider.on_left_mouse_button_down_event.assert_called_once_with(event)
        other_sprite.on_left_mouse_button_down_event.assert_called_once_with(event)
        assert mock_editor.is_dragging_film_strips is True
        assert mock_editor.film_strip_drag_start_y == 562
        assert mock_editor.film_strip_drag_start_offset == 3

    def test_missing_sliders_are_skipped(self, mock_editor, mocker):
        """Sliders the editor does not have are not committed; the alpha text box is."""
        del mock_editor.red_slider
        del mock_editor.blue_slider
        mock_editor.green_slider.text_sprite.is_active = True
        mock_editor.alpha_slider.text_sprite.is_active = True
        mocker.patch.object(mock_editor._slider_manager, 'detect_clicked_slider', return_value=None)
        mocker.patch.object(
            mock_editor.film_strip_coordinator,
            'is_mouse_in_film_strip_area',
            return_value=False,
        )
        event = _make_event(pos=(15, 552))

        mock_editor.on_left_mouse_button_down_event(event)

        mock_editor.green_slider.commit_text.assert_called_once_with(event=event)
        mock_editor.alpha_slider.commit_text.assert_called_once_with(event=event)
        assert mock_editor.is_dragging_film_strips is False


# ===========================================================================
# 57. Drag, Mouse Up and Motion Routing
# ===========================================================================


class TestMouseRouting:
    """Tests for drag, mouse-up and motion routing to sprites and sliders."""

    def test_drag_off_canvas_reaches_canvas_and_sprites(self, mock_editor, mocker):
        """A drag outside the canvas still reaches the canvas and the sprites under it."""
        sprite_under_cursor = mocker.Mock()
        mock_editor.sprites_at_position = mocker.Mock(return_value=[sprite_under_cursor])
        event = _make_event(pos=(600, 500))
        trigger = object()

        mock_editor.on_left_mouse_drag_event(event, trigger)

        mock_editor.canvas.on_left_mouse_drag_event.assert_called_once_with(event, trigger)
        sprite_under_cursor.on_left_mouse_drag_event.assert_called_once_with(event, trigger)

    def test_drag_off_canvas_ignores_sprite_lookup_failure(self, mock_editor, mocker):
        """A failing sprite lookup during a drag is ignored."""
        mock_editor.sprites_at_position = mocker.Mock(side_effect=AttributeError('no groups'))

        mock_editor.on_left_mouse_drag_event(_make_event(pos=(600, 500)), object())

        mock_editor.canvas.on_left_mouse_drag_event.assert_called_once()

    def test_mouse_up_releases_dragging_sliders(self, mock_editor, mocker):
        """Every slider that is being dragged is released on mouse up."""
        for slider_name in ('red_slider', 'green_slider', 'blue_slider', 'alpha_slider'):
            getattr(mock_editor, slider_name).dragging = True
        mock_editor.all_sprites = []

        mock_editor.on_mouse_button_up_event(_make_event(pos=(0, 0)))

        for slider_name in ('red_slider', 'green_slider', 'blue_slider', 'alpha_slider'):
            assert getattr(mock_editor, slider_name).dragging is False

    def test_mouse_up_reaches_only_visible_sprites_under_the_cursor(self, mock_editor, mocker):
        """Mouse up goes to visible sprites under the cursor, not hidden or distant ones."""
        for slider_name in ('red_slider', 'green_slider', 'blue_slider', 'alpha_slider'):
            getattr(mock_editor, slider_name).dragging = False
        under_cursor = mocker.Mock(visible=True, rect=pygame.Rect(0, 0, 10, 10))
        hidden = mocker.Mock(visible=False, rect=pygame.Rect(0, 0, 10, 10))
        distant = mocker.Mock(visible=True, rect=pygame.Rect(100, 100, 10, 10))
        mock_editor.all_sprites = [under_cursor, hidden, distant]
        event = _make_event(pos=(5, 5))

        mock_editor.on_mouse_button_up_event(event)

        under_cursor.on_mouse_button_up_event.assert_called_once_with(event)
        hidden.on_mouse_button_up_event.assert_not_called()
        distant.on_mouse_button_up_event.assert_not_called()

    def test_mouse_drag_reaches_visible_sprites(self, mock_editor, mocker):
        """Mouse drags go to visible sprites only."""
        visible_sprite = mocker.Mock(visible=True)
        hidden_sprite = mocker.Mock(visible=False)
        mock_editor.all_sprites = [visible_sprite, hidden_sprite]
        event = _make_event(pos=(5, 5))

        mock_editor.on_mouse_drag_event(event, None)

        visible_sprite.on_mouse_drag_event.assert_called_once_with(event, None)
        hidden_sprite.on_mouse_drag_event.assert_not_called()

    def test_mouse_motion_reaches_visible_sprites_and_hovers_sliders(self, mock_editor, mocker):
        """Mouse motion updates slider hover and reaches visible sprites only."""
        hover = mocker.patch.object(mock_editor._slider_manager, 'update_slider_hover_effects')
        visible_sprite = mocker.Mock(visible=True)
        hidden_sprite = mocker.Mock(visible=False)
        mock_editor.all_sprites = [visible_sprite, hidden_sprite]
        event = _make_event(pos=(5, 5))

        mock_editor.on_mouse_motion_event(event)

        hover.assert_called_once_with((5, 5))
        visible_sprite.on_mouse_motion_event.assert_called_once_with(event)
        hidden_sprite.on_mouse_motion_event.assert_not_called()


# ===========================================================================
# 58. Scene Lifecycle and Frame Update
# ===========================================================================


class TestSceneLifecycleAndUpdate:
    """Tests for setup, text submit, update, _update_animated_canvas and cleanup."""

    def test_text_submit_goes_to_ai_integration(self, mock_editor, mocker):
        """Submitted text is handed to the AI integration."""
        submit = mocker.patch.object(mock_editor._ai_integration, 'on_text_submit_event')

        mock_editor.on_text_submit_event('draw a cat')

        submit.assert_called_once_with('draw a cat')

    def test_setup_sets_up_ai_integration(self, mock_editor, mocker):
        """Scene setup sets up the AI integration."""
        ai_setup = mocker.patch.object(mock_editor._ai_integration, 'setup')

        mock_editor.setup()

        ai_setup.assert_called_once()

    def test_animated_canvas_update_tracks_frames_and_log_time(self, mock_editor, mocker):
        """Each update counts, advances the canvas animation and remembers the shown frame."""
        clock = mocker.patch.object(bitmappy, 'frame_clock_seconds', side_effect=[10.0, 10.0, 11.5])
        mocker.patch.object(
            mock_editor.film_strip_coordinator, 'update_film_strip_animation_timing'
        )
        mocker.patch.object(mock_editor.controller_handler, 'render_visual_indicators')
        mock_editor.canvas.animated_sprite.current_frame = 1

        mock_editor._update_animated_canvas()
        mock_editor.canvas.animated_sprite.current_frame = 0
        mock_editor._update_animated_canvas()

        assert clock.call_count == 3
        assert mock_editor._debug_animation_counter == 2
        assert mock_editor._last_animation_log_time == pytest.approx(11.5)
        assert mock_editor._last_animation_frame == 0
        assert mock_editor.canvas.update_animation.call_count == 2
        mock_editor.canvas.update_animation.assert_called_with(mock_editor.dt)

    def test_update_runs_every_per_frame_service(self, mock_editor, mocker):
        """A scene update animates the canvas and runs the controller, click and AI checks."""
        from glitchygames.scenes.scene import Scene

        mocker.patch.object(Scene, 'update')
        update_canvas = mocker.patch.object(mock_editor, '_update_animated_canvas')
        adjustments = mocker.patch.object(
            mock_editor.controller_handler, 'update_continuous_adjustments'
        )
        movements = mocker.patch.object(
            mock_editor.controller_handler, 'update_continuous_movements'
        )
        click_timer = mocker.patch.object(mock_editor._frame_operations, 'check_single_click_timer')
        ai_responses = mocker.patch.object(mock_editor._ai_integration, 'check_responses')

        mock_editor.update()

        update_canvas.assert_called_once()
        adjustments.assert_called_once()
        movements.assert_called_once()
        click_timer.assert_called_once()
        ai_responses.assert_called_once()

    def test_update_without_animated_sprite_skips_the_canvas(self, mock_editor, mocker):
        """With no animated sprite on the canvas, the canvas is not animated."""
        from glitchygames.scenes.scene import Scene

        mocker.patch.object(Scene, 'update')
        mock_editor.canvas.animated_sprite = None
        update_canvas = mocker.patch.object(mock_editor, '_update_animated_canvas')
        mocker.patch.object(mock_editor._ai_integration, 'check_responses')

        mock_editor.update()

        update_canvas.assert_not_called()

    def test_animated_canvas_update_on_the_same_frame_keeps_the_last_frame(
        self,
        mock_editor,
        mocker,
    ):
        """Two updates on the same frame leave the remembered frame unchanged."""
        mocker.patch.object(
            mock_editor.film_strip_coordinator, 'update_film_strip_animation_timing'
        )
        mocker.patch.object(mock_editor.controller_handler, 'render_visual_indicators')
        mock_editor.canvas.animated_sprite.current_frame = 2

        mock_editor._update_animated_canvas()
        mock_editor._update_animated_canvas()

        assert mock_editor._last_animation_frame == 2
        assert mock_editor.canvas.update_animation.call_count == 2

    def test_voice_cleanup_stops_and_drops_the_voice_manager(self, mock_editor):
        """A running voice manager is stopped and forgotten."""
        stopped = []
        mock_editor.voice_manager = SimpleNamespace(stop_listening=lambda: stopped.append(True))

        mock_editor._cleanup_voice_recognition()

        assert stopped == [True]
        assert mock_editor.voice_manager is None

    def test_voice_cleanup_without_a_voice_manager_does_nothing(self, mock_editor, mocker):
        """With no voice manager, cleanup logs nothing and leaves it None."""
        mock_editor.voice_manager = None
        log_info = mocker.patch.object(mock_editor.log, 'info')

        mock_editor._cleanup_voice_recognition()

        assert mock_editor.voice_manager is None
        log_info.assert_not_called()

    def test_voice_cleanup_failure_is_logged_and_kept(self, mock_editor, mocker):
        """A voice manager that fails to stop is kept and the failure logged."""
        voice_manager = mocker.Mock()
        voice_manager.stop_listening.side_effect = OSError('microphone busy')
        mock_editor.voice_manager = voice_manager
        log_exception = mocker.patch.object(mock_editor.log, 'exception')

        mock_editor._cleanup_voice_recognition()

        assert mock_editor.voice_manager is voice_manager
        log_exception.assert_called_once()


# ===========================================================================
# 59. Keyboard Handling
# ===========================================================================


class TestKeyboardHandling:
    """Tests for key-down routing: panning, arrows, slider mode, canvas and parent fallback."""

    @pytest.fixture(autouse=True)
    def _no_text_input(self, mock_editor, mocker):
        """Make sure no text box or slider text field takes the key."""
        mock_editor.debug_text.is_active = False
        mocker.patch.object(
            mock_editor._slider_manager, 'handle_slider_text_input', return_value=False
        )

    def test_shift_with_non_arrow_key_is_not_a_ctrl_shortcut(self, mock_editor, mocker):
        """Ctrl+Shift with a key that is neither an arrow nor a shortcut is not handled."""
        panning = mocker.patch.object(mock_editor._frame_operations, 'handle_canvas_panning')
        event = _make_event(key=pygame.K_q)

        handled = mock_editor._handle_ctrl_key_shortcuts(
            event, pygame.KMOD_CTRL | pygame.KMOD_SHIFT
        )

        assert handled is False
        panning.assert_not_called()

    def test_ctrl_shift_arrow_pans_the_canvas(self, mock_editor, mocker):
        """Ctrl+Shift+Left pans the canvas one step left."""
        panning = mocker.patch.object(mock_editor._frame_operations, 'handle_canvas_panning')
        event = _make_event(key=pygame.K_LEFT)

        handled = mock_editor._handle_ctrl_key_shortcuts(
            event, pygame.KMOD_CTRL | pygame.KMOD_SHIFT
        )

        assert handled is True
        panning.assert_called_once_with(delta_x=-1, delta_y=0)

    def test_arrow_navigation_without_canvas_is_consumed(self, mock_editor):
        """UP and DOWN are consumed even when there is no canvas to navigate."""
        mock_editor.canvas = None

        assert mock_editor._handle_arrow_key_navigation(_make_event(key=pygame.K_UP)) is True
        assert mock_editor._handle_arrow_key_navigation(_make_event(key=pygame.K_DOWN)) is True
        assert mock_editor._handle_arrow_key_navigation(_make_event(key=pygame.K_a)) is False

    def test_down_arrow_moves_to_next_animation(self, mock_editor, mocker):
        """DOWN moves the canvas to the next animation and scrolls the film strips to it."""
        scroll = mocker.patch.object(
            mock_editor.film_strip_coordinator, 'scroll_to_current_animation'
        )

        mock_editor.on_key_down_event(_make_event(key=pygame.K_DOWN, mod=0))

        mock_editor.canvas.next_animation.assert_called_once()
        scroll.assert_called_once()

    @pytest.mark.parametrize(
        ('key', 'direction'),
        [(pygame.K_UP, 'up'), (pygame.K_DOWN, 'down')],
    )
    def test_slider_mode_arrows_navigate_slider_modes(self, mock_editor, mocker, key, direction):
        """In slider mode UP and DOWN move between slider modes, not animations."""
        mocker.patch.object(
            mock_editor._slider_manager, 'is_any_controller_in_slider_mode', return_value=True
        )
        navigation = mocker.patch.object(
            mock_editor.controller_handler, 'handle_slider_mode_navigation'
        )

        mock_editor.on_key_down_event(_make_event(key=key, mod=0))

        navigation.assert_called_once_with(direction)
        mock_editor.canvas.previous_animation.assert_not_called()
        mock_editor.canvas.next_animation.assert_not_called()

    def test_slider_mode_other_keys_do_not_reach_the_canvas(self, mock_editor, mocker):
        """In slider mode other keys are swallowed rather than routed to the canvas."""
        mocker.patch.object(
            mock_editor._slider_manager, 'is_any_controller_in_slider_mode', return_value=True
        )
        navigation = mocker.patch.object(
            mock_editor.controller_handler, 'handle_slider_mode_navigation'
        )

        mock_editor.on_key_down_event(_make_event(key=pygame.K_a, mod=0))

        navigation.assert_not_called()
        mock_editor.canvas.handle_keyboard_event.assert_not_called()

    def test_slider_mode_entered_during_handling_skips_canvas(self, mock_editor, mocker):
        """When slider mode starts while the key is being handled, the canvas is skipped."""
        mocker.patch.object(
            mock_editor._slider_manager,
            'is_any_controller_in_slider_mode',
            side_effect=[False, True],
        )

        mock_editor._handle_key_down_actions(_make_event(key=pygame.K_a, mod=0))

        mock_editor.canvas.handle_keyboard_event.assert_not_called()

    def test_onion_toggle_without_canvas(self, mock_editor, mocker):
        """O toggles onion skinning even with no canvas to redraw."""
        from glitchygames.bitmappy.onion_skinning import get_onion_skinning_manager

        onion_manager = get_onion_skinning_manager()
        state_before = onion_manager.global_onion_skinning_enabled
        mock_editor.canvas = None
        try:
            mock_editor._handle_key_down_actions(_make_event(key=pygame.K_o, mod=0))
            assert onion_manager.global_onion_skinning_enabled is not state_before
        finally:
            onion_manager.global_onion_skinning_enabled = state_before

    def test_key_without_canvas_handler_goes_to_parent(self, mock_editor, mocker):
        """With no canvas keyboard handler the key goes to the parent scene's handler."""
        from glitchygames.scenes.scene import Scene

        parent_handler = mocker.patch.object(Scene, 'on_key_down_event')
        mock_editor.canvas = SimpleNamespace()
        event = _make_event(key=pygame.K_a, mod=0)

        mock_editor._route_to_canvas_or_parent(event)

        parent_handler.assert_called_once_with(event)

    def test_key_with_editing_film_strip_is_not_routed(self, mock_editor):
        """While a film strip name is being edited, keys do not reach the canvas."""
        mock_editor.film_strips = {
            'idle': SimpleNamespace(editing_animation=None),
            'walk': SimpleNamespace(editing_animation='walk'),
        }

        mock_editor._route_to_canvas_or_parent(_make_event(key=pygame.K_a, mod=0))

        mock_editor.canvas.handle_keyboard_event.assert_not_called()

    def test_key_with_idle_film_strips_reaches_the_canvas(self, mock_editor):
        """With no film strip being edited, the key reaches the canvas."""
        mock_editor.film_strips = {'idle': SimpleNamespace(editing_animation=None)}

        mock_editor._route_to_canvas_or_parent(_make_event(key=pygame.K_a, mod=0))

        mock_editor.canvas.handle_keyboard_event.assert_called_once_with(pygame.K_a)

    def test_scene_key_events_use_the_editor_handler(self, mock_editor, mocker):
        """Scene-level key events are handled by the editor's own key handler."""
        handler = mocker.patch.object(mock_editor, 'on_key_down_event')
        event = _make_event(key=pygame.K_a)

        mock_editor._handle_scene_key_events(event)

        handler.assert_called_once_with(event)


# ===========================================================================
# 60. Undo/Redo Fallback Paths
# ===========================================================================


class TestUndoRedoFallbacks:
    """Tests for the failure and no-canvas paths of handle_undo and handle_redo."""

    def test_undo_without_canvas_uses_global_undo(self, mock_editor, mocker):
        """With no canvas there is no current frame, so the global undo runs."""
        mock_editor.canvas = None
        mock_editor.undo_redo_manager.can_undo.return_value = True
        mock_editor.undo_redo_manager.undo.return_value = True

        mock_editor.handle_undo()

        mock_editor.undo_redo_manager.can_undo_frame.assert_not_called()
        mock_editor.undo_redo_manager.undo.assert_called_once()

    def test_failed_frame_undo_falls_back_to_failed_global_undo(self, mock_editor, mocker):
        """A failed frame undo falls back to the global undo, which may fail too."""
        mock_editor.undo_redo_manager.can_undo_frame.return_value = True
        mock_editor.undo_redo_manager.undo_frame.return_value = False
        mock_editor.undo_redo_manager.can_undo.return_value = True
        mock_editor.undo_redo_manager.undo.return_value = False
        synchronize = mocker.patch.object(mock_editor, '_synchronize_canvas_state_after_undo')

        mock_editor.handle_undo()

        mock_editor.undo_redo_manager.undo.assert_called_once()
        synchronize.assert_not_called()
        mock_editor.canvas.force_redraw.assert_not_called()

    def test_successful_global_undo_redraws_the_canvas(self, mock_editor, mocker):
        """A successful global undo synchronizes and redraws the canvas."""
        mock_editor.undo_redo_manager.can_undo_frame.return_value = False
        mock_editor.undo_redo_manager.can_undo.return_value = True
        mock_editor.undo_redo_manager.undo.return_value = True
        mocker.patch.object(mock_editor, '_synchronize_canvas_state_after_undo')

        mock_editor.handle_undo()

        mock_editor.canvas.force_redraw.assert_called_once()

    def test_redo_without_canvas_uses_global_redo(self, mock_editor):
        """With no canvas there is no current frame, so the global redo runs."""
        mock_editor.canvas = None
        mock_editor.undo_redo_manager.can_redo.return_value = True
        mock_editor.undo_redo_manager.redo.return_value = True

        mock_editor.handle_redo()

        mock_editor.undo_redo_manager.can_redo_frame.assert_not_called()
        mock_editor.undo_redo_manager.redo.assert_called_once()

    def test_failed_frame_redo_falls_back_to_failed_global_redo(self, mock_editor, mocker):
        """A failed frame redo falls back to the global redo, which may fail too."""
        mock_editor.undo_redo_manager.can_redo_frame.return_value = True
        mock_editor.undo_redo_manager.redo_frame.return_value = False
        mock_editor.undo_redo_manager.can_redo.return_value = True
        mock_editor.undo_redo_manager.redo.return_value = False
        synchronize = mocker.patch.object(mock_editor, '_synchronize_canvas_state_after_undo')

        mock_editor.handle_redo()

        mock_editor.undo_redo_manager.redo.assert_called_once()
        synchronize.assert_not_called()
        mock_editor.canvas.force_redraw.assert_not_called()

    def test_successful_global_redo_redraws_the_canvas(self, mock_editor, mocker):
        """A successful global redo synchronizes and redraws the canvas."""
        mock_editor.undo_redo_manager.can_redo_frame.return_value = False
        mock_editor.undo_redo_manager.can_redo.return_value = True
        mock_editor.undo_redo_manager.redo.return_value = True
        mocker.patch.object(mock_editor, '_synchronize_canvas_state_after_undo')

        mock_editor.handle_redo()

        mock_editor.canvas.force_redraw.assert_called_once()

    def test_redo_with_nothing_to_redo_changes_nothing(self, mock_editor):
        """With nothing to redo, nothing is redone or redrawn."""
        mock_editor.undo_redo_manager.can_redo_frame.return_value = False
        mock_editor.undo_redo_manager.can_redo.return_value = False

        mock_editor.handle_redo()

        mock_editor.undo_redo_manager.redo.assert_not_called()
        mock_editor.canvas.force_redraw.assert_not_called()

    def test_synchronize_with_no_animations_shows_nothing(self, mock_editor):
        """A sprite left with no animations is not switched to any frame."""
        mock_editor.canvas.animated_sprite._animations = {}

        mock_editor._synchronize_canvas_state_after_undo()

        mock_editor.canvas.show_frame.assert_not_called()
        mock_editor.canvas.force_redraw.assert_not_called()


# ===========================================================================
# 61. Event Handling and Drop Files
# ===========================================================================


class TestEventHandlingAndDropFiles:
    """Tests for handle_event's confirmation dialog and file drops."""

    def test_confirmation_dialog_click_is_consumed(self, mock_editor, mocker):
        """A click the confirmation dialog handles closes it and stops the event."""
        confirmation_dialog = mocker.Mock()
        confirmation_dialog.rect = pygame.Rect(100, 100, 200, 100)
        confirmation_dialog.handle_mouse_down.return_value = True
        mock_editor.confirmation_dialog = confirmation_dialog
        mocker.patch.object(
            bitmappy,
            'current_input',
            return_value=SimpleNamespace(mouse_position=(150, 130)),
        )

        mock_editor.handle_event(_make_event(type=pygame.MOUSEBUTTONDOWN))

        confirmation_dialog.handle_mouse_down.assert_called_once_with((50, 30))
        assert mock_editor.confirmation_dialog is None

    def test_event_the_dialog_does_not_take_reaches_the_sprites(self, mock_editor, mocker):
        """An event no confirmation dialog takes does not raise (BUGS.md #91).

        handle_event called super().handle_event, which no parent class defines.
        """
        mock_editor.confirmation_dialog = None
        leave_window_sprite = mocker.Mock()
        mock_editor.all_sprites = [leave_window_sprite]
        event = _make_event(type=pygame.WINDOWLEAVE)

        mock_editor.handle_event(event)

        leave_window_sprite.on_mouse_leave_window_event.assert_called_once_with(event)

    def test_click_outside_the_confirmation_dialog_is_not_consumed(self, mock_editor, mocker):
        """A click outside the dialog leaves it open and falls through without raising."""
        confirmation_dialog = mocker.Mock()
        confirmation_dialog.rect = pygame.Rect(100, 100, 200, 100)
        mock_editor.confirmation_dialog = confirmation_dialog
        mock_editor.all_sprites = []
        mocker.patch.object(
            bitmappy,
            'current_input',
            return_value=SimpleNamespace(mouse_position=(5, 5)),
        )

        mock_editor.handle_event(_make_event(type=pygame.MOUSEBUTTONDOWN))

        confirmation_dialog.handle_mouse_down.assert_not_called()
        assert mock_editor.confirmation_dialog is confirmation_dialog

    def test_click_the_dialog_does_not_handle_keeps_it_open(self, mock_editor, mocker):
        """A click inside the dialog that it does not handle leaves the dialog open."""
        confirmation_dialog = mocker.Mock()
        confirmation_dialog.rect = pygame.Rect(100, 100, 200, 100)
        confirmation_dialog.handle_mouse_down.return_value = False
        mock_editor.confirmation_dialog = confirmation_dialog
        mock_editor.all_sprites = []
        mocker.patch.object(
            bitmappy,
            'current_input',
            return_value=SimpleNamespace(mouse_position=(150, 130)),
        )

        mock_editor.handle_event(_make_event(type=pygame.MOUSEBUTTONDOWN))

        confirmation_dialog.handle_mouse_down.assert_called_once_with((50, 30))
        assert mock_editor.confirmation_dialog is confirmation_dialog

    def test_key_down_is_logged(self, mock_editor, caplog):
        """A KEYDOWN reaching handle_event is logged with its key."""
        mock_editor.confirmation_dialog = None

        with caplog.at_level(logging.DEBUG, logger=mock_editor.log.name):
            mock_editor.handle_event(_make_event(type=pygame.KEYDOWN, key=pygame.K_a))

        assert f'KEYDOWN event received in handle_event: key={pygame.K_a}' in caplog.messages

    def test_window_leave_skips_sprites_without_a_handler(self, mock_editor, mocker):
        """Only sprites with a leave-window handler hear that the mouse left the window."""
        mock_editor.confirmation_dialog = None
        listening_sprite = mocker.Mock()
        mock_editor.all_sprites = [SimpleNamespace(), listening_sprite]
        event = _make_event(type=pygame.WINDOWLEAVE)

        mock_editor.handle_event(event)

        listening_sprite.on_mouse_leave_window_event.assert_called_once_with(event)

    def test_drop_file_goes_to_file_io(self, mock_editor, mocker):
        """A dropped file is handed to the file I/O manager."""
        mock_editor._file_io = mocker.Mock()
        event = _make_event(file='sprite.toml')

        mock_editor.on_drop_file_event(event)

        mock_editor._file_io.on_drop_file_event.assert_called_once_with(event)


# ===========================================================================
# 62. Film Strip and Frame Operation Delegation
# ===========================================================================


class TestDelegation:
    """Tests for the editor methods that hand work to its subsystems."""

    def test_update_scroll_arrows(self, mock_editor, mocker):
        """update_scroll_arrows is handled by the film strip coordinator."""
        delegate = mocker.patch.object(mock_editor.film_strip_coordinator, 'update_scroll_arrows')

        mock_editor.update_scroll_arrows()

        delegate.assert_called_once()

    def test_submit_pixel_changes_if_ready(self, mock_editor, mocker):
        """_submit_pixel_changes_if_ready is handled by the frame operations manager."""
        delegate = mocker.patch.object(
            mock_editor._frame_operations, 'submit_pixel_changes_if_ready'
        )

        mock_editor._submit_pixel_changes_if_ready()

        delegate.assert_called_once()


class TestEditorConstructionAndArguments:
    """Tests for BitmapEditorScene construction defaults and command line arguments."""

    def test_missing_options_default_to_a_32_by_32_canvas(self, mocker):
        """Constructing the editor with no options gives the default 32x32 size."""
        from glitchygames.bitmappy.controllers.manager import MultiControllerManager

        mocker.patch.object(MultiControllerManager, '_instance', None)

        scene = BitmapEditorScene(options=None)  # type: ignore[arg-type]

        assert scene.options['size'] == '32x32'
        assert (scene.canvas.pixels_across, scene.canvas.pixels_tall) == (32, 32)

    def test_arguments_add_version_and_size(self):
        """The editor adds --version and --size (default 32x32) to the parser."""
        parser = argparse.ArgumentParser()

        BitmapEditorScene.args(parser)

        assert parser.parse_args([]).size == '32x32'
        parsed = parser.parse_args(['--size', '16x8', '--version'])
        assert parsed.size == '16x8'
        assert parsed.version is True


# ===========================================================================
# Drawing in the real editor: undo, redo and a new canvas redraw the canvas image
# ===========================================================================

MAGENTA_RGB = (255, 0, 255)
PAINT_RGB = (200, 10, 10)


@pytest.fixture
def real_editor(mocker):
    """Build a real Bitmappy editor on the real display, with a fresh controller manager.

    Returns:
        BitmapEditorScene: The editor (one 32x32 frame of magenta).

    """
    from glitchygames.bitmappy.controllers.manager import MultiControllerManager

    mocker.patch.object(MultiControllerManager, '_instance', None)
    return BitmapEditorScene(options={})


def _paint_pixel(editor, *, x, y, color):
    """Paint one canvas pixel with a real mouse press and release."""
    from glitchygames import events

    canvas = editor.canvas
    canvas.active_color = color
    position = (
        canvas.rect.x + x * canvas.pixel_width + 1,
        canvas.rect.y + y * canvas.pixel_height + 1,
    )
    editor.on_left_mouse_button_down_event(
        events.HashableEvent(pygame.MOUSEBUTTONDOWN, pos=position, button=1),
    )
    editor.on_mouse_button_up_event(
        events.HashableEvent(pygame.MOUSEBUTTONUP, pos=position, button=1),
    )


def _drawn_rgb_at(editor, *, x, y):
    """Return the RGB colour the canvas image shows at the centre of a pixel's square.

    Returns:
        tuple[int, int, int]: The drawn colour.

    """
    canvas = editor.canvas
    center = (
        x * canvas.pixel_width + canvas.pixel_width // 2,
        y * canvas.pixel_height + canvas.pixel_height // 2,
    )
    return tuple(canvas.image.get_at(center))[:3]


class TestCanvasRedrawInTheRealEditor:
    """Undo, redo and a new canvas change what the real canvas image shows."""

    def test_undo_and_redo_redraw_the_painted_pixel(self, real_editor):
        """Undo draws the pixel's old colour again and redo draws the paint again."""
        _paint_pixel(real_editor, x=3, y=4, color=(*PAINT_RGB, 255))
        real_editor.canvas.force_redraw()
        assert _drawn_rgb_at(real_editor, x=3, y=4) == PAINT_RGB

        real_editor.handle_undo()
        assert _drawn_rgb_at(real_editor, x=3, y=4) == MAGENTA_RGB

        real_editor.handle_redo()
        assert _drawn_rgb_at(real_editor, x=3, y=4) == PAINT_RGB

    def test_new_file_draws_a_blank_canvas(self, real_editor):
        """A new 3x2 file draws every pixel of the new canvas magenta, the old paint gone."""
        _paint_pixel(real_editor, x=0, y=0, color=(*PAINT_RGB, 255))
        assert _drawn_rgb_at(real_editor, x=0, y=0) == PAINT_RGB

        real_editor.on_new_file_event('3x2')

        canvas = real_editor.canvas
        assert (canvas.pixels_across, canvas.pixels_tall) == (3, 2)
        assert canvas.image.get_size() == (3 * canvas.pixel_width, 2 * canvas.pixel_height)
        drawn_colors = {_drawn_rgb_at(real_editor, x=x, y=y) for x in range(3) for y in range(2)}
        assert drawn_colors == {MAGENTA_RGB}

    @pytest.mark.parametrize('dimensions', ['0x16', '16x0', '-4x4'])
    def test_non_positive_dimensions_keep_the_canvas(self, real_editor, caplog, dimensions):
        """A zero or negative size is refused as invalid; the painted canvas stays as it was.

        A zero width or height used to raise ZeroDivisionError sizing the pixels, and a
        negative one a pygame error making the surface, crashing the editor.
        """
        _paint_pixel(real_editor, x=0, y=0, color=(*PAINT_RGB, 255))

        real_editor.on_new_file_event(dimensions)

        canvas = real_editor.canvas
        assert (canvas.pixels_across, canvas.pixels_tall) == (32, 32)
        assert _drawn_rgb_at(real_editor, x=0, y=0) == PAINT_RGB
        assert f"Invalid dimensions format '{dimensions}'" in caplog.text

    def test_a_failure_building_the_canvas_is_not_reported_as_bad_dimensions(
        self,
        real_editor,
        mocker,
        caplog,
    ):
        """Only parsing the dimensions is guarded: a ValueError building the canvas propagates.

        It used to be logged as an invalid dimensions format, hiding the real error.
        """
        mocker.patch.object(
            real_editor,
            '_create_fresh_animated_sprite',
            side_effect=ValueError('canvas build failed'),
        )

        with pytest.raises(ValueError, match='canvas build failed'):
            real_editor.on_new_file_event('16x16')

        assert 'Invalid dimensions format' not in caplog.text
