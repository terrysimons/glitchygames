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

import time
from types import SimpleNamespace

import pygame
import pytest

from glitchygames.bitmappy import editor as bitmappy
from glitchygames.bitmappy.ai_manager import AIManager
from glitchygames.bitmappy.controller_handler import ControllerEventHandler
from glitchygames.bitmappy.editor import BitmapEditorScene
from tests.mocks import MockFactory


def _make_event(**kwargs):
    """Create a simple namespace event that supports attribute access like HashableEvent.

    Returns:
        SimpleNamespace: Event-like object with the given attributes.

    """
    return SimpleNamespace(**kwargs)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _ensure_pygame_init():
    """Ensure pygame is initialized for all tests in this module."""
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((800, 600))


@pytest.fixture
def pygame_mocks(mocker):
    """Set up pygame mocks for sprite tests.

    Returns:
        dict: The mock pygame patches dictionary.

    """
    return MockFactory.setup_pygame_mocks_with_mocker(mocker)


def _setup_sliders(editor, mocker):
    """Configure mock sliders and their bounding boxes on the editor."""
    slider_configs = [
        ('red_slider', 128, '128', (13, 550, 256, 9), 'red_slider_bbox', (10, 548, 260, 13)),
        ('green_slider', 64, '64', (13, 560, 256, 9), 'green_slider_bbox', (10, 558, 260, 13)),
        ('blue_slider', 32, '32', (13, 570, 256, 9), 'blue_slider_bbox', (10, 568, 260, 13)),
        ('alpha_slider', 255, '255', (13, 540, 256, 9), 'alpha_slider_bbox', (10, 538, 260, 13)),
    ]
    for slider_name, value, text, text_rect, bbox_name, bbox_rect in slider_configs:
        slider = mocker.Mock()
        slider.value = value
        slider.text_sprite = mocker.Mock()
        slider.text_sprite.active = False
        slider.text_sprite.text = text
        slider.text_sprite.rect = pygame.Rect(*text_rect)
        setattr(editor, slider_name, slider)

        bbox = mocker.Mock()
        bbox.visible = False
        bbox.rect = pygame.Rect(*bbox_rect)
        bbox.image = mocker.Mock()
        setattr(editor, bbox_name, bbox)


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
    editor._applying_undo_redo = False
    editor._pixel_change_timer = None

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
    editor._frame_clipboard = None

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
def mock_editor(mocker, pygame_mocks):
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
    """Tests for _clear_ai_sprite_box."""

    def test_clears_debug_text(self, mock_editor):
        """Clears the debug text box content."""
        mock_editor.debug_text.text = 'some content'
        mock_editor._clear_ai_sprite_box()
        assert not mock_editor.debug_text.text

    def test_no_debug_text_attribute(self, mock_editor):
        """Handles missing debug_text gracefully."""
        del mock_editor.debug_text
        # Should not raise
        mock_editor._clear_ai_sprite_box()

    def test_debug_text_is_none(self, mock_editor):
        """Handles None debug_text gracefully."""
        mock_editor.debug_text = None
        # Should not raise
        mock_editor._clear_ai_sprite_box()


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
        mocker.patch.object(mock_editor.film_strip_coordinator, 'update_film_strips_for_frame')
        mock_editor._synchronize_canvas_state_after_undo()
        mock_editor.canvas.force_redraw.assert_called()


# ===========================================================================
# 17. Canvas Panning
# ===========================================================================


class TestCanvasPanning:
    """Tests for _handle_canvas_panning."""

    def test_no_canvas(self, mock_editor):
        """Warns when canvas is not available."""
        mock_editor.canvas = None
        mock_editor._handle_canvas_panning(1, 0)

    def test_delegates_to_pan_canvas(self, mock_editor):
        """Delegates to canvas pan_canvas method."""
        mock_editor._handle_canvas_panning(1, -1)
        mock_editor.canvas.pan_canvas.assert_called_once_with(1, -1)

    def test_canvas_without_pan_method(self, mock_editor):
        """Warns when canvas does not support panning."""
        mock_editor.canvas.pan_canvas = None
        del mock_editor.canvas.pan_canvas
        mock_editor._handle_canvas_panning(1, 0)


# ===========================================================================
# 18. Handle Copy/Paste Frame Operations
# ===========================================================================


class TestHandleCopyPasteFrame:
    """Tests for _handle_copy_frame and _handle_paste_frame."""

    def test_copy_frame_no_canvas(self, mock_editor):
        """Does nothing when canvas is not available."""
        mock_editor.canvas = None
        mock_editor._handle_copy_frame()

    def test_copy_frame_no_selection(self, mock_editor):
        """Does nothing when no animation/frame is selected."""
        mock_editor.selected_animation = None
        mock_editor.selected_frame = None
        mock_editor._handle_copy_frame()

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
        mock_editor._handle_copy_frame()
        assert mock_editor._frame_clipboard is not None
        assert mock_editor._frame_clipboard['width'] == 32
        assert mock_editor._frame_clipboard['height'] == 32

    def test_paste_frame_no_clipboard(self, mock_editor):
        """Does nothing when clipboard is empty."""
        mock_editor._frame_clipboard = None
        mock_editor._handle_paste_frame()

    def test_paste_frame_dimension_mismatch(self, mock_editor, mocker):
        """Does nothing when clipboard dimensions do not match target."""
        mock_editor._frame_clipboard = {
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
        mock_editor._handle_paste_frame()
        # Should not call set_pixel_data due to dimension mismatch


# ===========================================================================
# 19. Apply Pixel Change for Undo/Redo
# ===========================================================================


class TestApplyPixelChangeForUndoRedo:
    """Tests for _apply_pixel_change_for_undo_redo."""

    def test_sets_pixel(self, mock_editor):
        """Sets pixel via canvas interface."""
        mock_editor._apply_pixel_change_for_undo_redo(5, 10, (255, 0, 0))
        mock_editor.canvas.canvas_interface.set_pixel_at.assert_called_once_with(5, 10, (255, 0, 0))

    def test_sets_and_resets_flag(self, mock_editor):
        """Sets _applying_undo_redo during operation and resets after."""
        assert mock_editor._applying_undo_redo is False
        mock_editor._apply_pixel_change_for_undo_redo(0, 0, (0, 0, 0))
        assert mock_editor._applying_undo_redo is False

    def test_no_canvas_interface(self, mock_editor):
        """Warns when canvas interface is not available."""
        mock_editor.canvas = None
        mock_editor._apply_pixel_change_for_undo_redo(0, 0, (0, 0, 0))


# ===========================================================================
# 20. Apply Frame Selection for Undo/Redo
# ===========================================================================


class TestApplyFrameSelectionForUndoRedo:
    """Tests for _apply_frame_selection_for_undo_redo."""

    def test_applies_selection(self, mock_editor):
        """Applies frame selection via canvas."""
        result = mock_editor._apply_frame_selection_for_undo_redo('default', 1)
        assert result is True
        mock_editor.canvas.show_frame.assert_called_once_with('default', 1)

    def test_resets_flag_after_operation(self, mock_editor):
        """Resets _applying_undo_redo flag after operation."""
        mock_editor._apply_frame_selection_for_undo_redo('default', 0)
        assert mock_editor._applying_undo_redo is False

    def test_no_canvas(self, mock_editor):
        """Returns False when canvas is not available."""
        mock_editor.canvas = None
        result = mock_editor._apply_frame_selection_for_undo_redo('default', 0)
        assert result is False

    def test_handles_exception(self, mock_editor):
        """Returns False on exception."""
        mock_editor.canvas.show_frame.side_effect = IndexError('test')
        result = mock_editor._apply_frame_selection_for_undo_redo('default', 99)
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
# 23. Color Well Event
# ===========================================================================


class TestOnColorWellEvent:
    """Tests for on_color_well_event."""

    def test_logs_event(self, mock_editor, mocker):
        """Logs color well event."""
        event = _make_event()
        trigger = mocker.Mock()
        mock_editor.on_color_well_event(event=event, trigger=trigger)
        # Should not raise


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
        """Marks film strips dirty on pixel update."""
        mock_sprite = mocker.Mock()
        mock_strip = mocker.Mock()
        mock_editor.film_strip_sprites = {'default': mock_sprite}
        mock_editor.film_strips = {'default': mock_strip}
        mock_editor.film_strip_coordinator._update_film_strips_for_pixel_update()
        assert mock_sprite.dirty == 1
        mock_strip.mark_dirty.assert_called_once()

    def test_update_for_animated_sprite_update(self, mock_editor, mocker):
        """Updates layout and marks dirty on animated sprite update."""
        mock_strip = mocker.Mock()
        mock_sprite = mocker.Mock()
        mock_editor.film_strips = {'default': mock_strip}
        mock_editor.film_strip_sprites = {'default': mock_sprite}
        mocker.patch.object(mock_editor.film_strip_coordinator, '_mark_film_strip_sprites_dirty')
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
        assert mock_sprite.dirty == 2

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
            mock_editor.film_strip_coordinator, 'update_film_strips_for_animated_sprite_update'
        )
        mocker.patch.object(
            mock_editor.film_strip_coordinator, '_update_film_strip_layout_after_rename'
        )
        mock_editor.on_animation_rename('old_name', 'new_name')

        assert 'new_name' in mock_editor.canvas.animated_sprite._animations
        assert mock_editor.selected_animation == 'new_name'

    def test_rename_nonexistent_animation(self, mock_editor, mocker):
        """Warns when trying to rename nonexistent animation."""
        mock_editor.canvas.animated_sprite._animations = {'default': [mocker.Mock()]}
        mocker.patch.object(
            mock_editor.film_strip_coordinator, 'update_film_strips_for_animated_sprite_update'
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
            'req-123', 'Sorry I cannot generate sprites'
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
            'req-1', 'draw a cat', '[sprite]...'
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
            'req-1', 'refine it', '[sprite]...'
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
    """Tests for _setup_voice_recognition."""

    def test_voice_manager_not_available(self, mock_editor, mocker):
        """Handles VoiceEventManager not being available."""
        mocker.patch.object(bitmappy, 'VoiceEventManager', None)
        mock_editor._setup_voice_recognition()
        assert mock_editor.voice_manager is None

    def test_voice_exception_handling(self, mock_editor, mocker):
        """Handles exceptions during voice setup."""
        mocker.patch.object(bitmappy, 'VoiceEventManager', side_effect=ImportError)
        mock_editor._setup_voice_recognition()
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
        mocker.patch.object(mock_editor, '_clear_ai_sprite_box')
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
        mocker.patch.object(mock_editor, '_clear_ai_sprite_box')
        mocker.patch.object(mock_editor, '_update_ai_sprite_position')
        mock_editor.on_new_file_event('32x32')
        assert len(mock_editor._ai_integration.pending_ai_requests) == 0


# ===========================================================================
# 30. Apply Frame Paste for Undo/Redo
# ===========================================================================


class TestApplyFramePasteForUndoRedo:
    """Tests for _apply_frame_paste_for_undo_redo."""

    def test_applies_paste(self, mock_editor, mocker):
        """Applies pixel data and duration to target frame."""
        mock_frame = mocker.Mock()
        mock_editor.canvas.animated_sprite._animations = {'default': [mock_frame]}
        pixels = [(100, 50, 25)] * 1024
        result = mock_editor._apply_frame_paste_for_undo_redo('default', 0, pixels, 0.3)
        assert result is True
        mock_frame.set_pixel_data.assert_called_once_with(pixels)
        assert abs(mock_frame.duration - 0.3) < 1e-9

    def test_no_canvas(self, mock_editor):
        """Returns False when canvas is not available."""
        mock_editor.canvas = None
        result = mock_editor._apply_frame_paste_for_undo_redo('default', 0, [], 0.5)
        assert result is False

    def test_animation_not_found(self, mock_editor, mocker):
        """Returns False when animation is not found."""
        mock_editor.canvas.animated_sprite._animations = {}
        result = mock_editor._apply_frame_paste_for_undo_redo('missing', 0, [], 0.5)
        assert result is False

    def test_frame_index_out_of_range(self, mock_editor, mocker):
        """Returns False when frame index is out of range."""
        mock_editor.canvas.animated_sprite._animations = {'default': [mocker.Mock()]}
        result = mock_editor._apply_frame_paste_for_undo_redo('default', 5, [], 0.5)
        assert result is False

    def test_updates_canvas_pixels_if_current(self, mock_editor, mocker):
        """Updates canvas pixels when pasting to currently displayed frame."""
        mock_frame = mocker.Mock()
        mock_editor.canvas.animated_sprite._animations = {'default': [mock_frame]}
        mock_editor.selected_animation = 'default'
        mock_editor.selected_frame = 0
        pixels = [(100, 50, 25)] * 10
        mock_editor.canvas.pixels = [(0, 0, 0)] * 10
        mock_editor.canvas.dirty_pixels = [False] * 10
        result = mock_editor._apply_frame_paste_for_undo_redo('default', 0, pixels, 0.5)
        assert result is True
        assert mock_editor.canvas.pixels == pixels


# ===========================================================================
# 31. Slider Text Format Update
# ===========================================================================


class TestUpdateSliderTextFormat:
    """Tests for _update_slider_text_format."""

    def test_decimal_format(self, mock_editor):
        """Updates slider text in decimal format."""
        mock_editor.slider_input_format = '%d'
        mock_editor._update_slider_text_format()
        assert mock_editor.red_slider.text_sprite.text == '128'
        assert mock_editor.green_slider.text_sprite.text == '64'
        assert mock_editor.blue_slider.text_sprite.text == '32'

    def test_hex_format(self, mock_editor):
        """Updates slider text in hex format."""
        mock_editor.slider_input_format = '%X'
        mock_editor._update_slider_text_format()
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
            200
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
    """Tests for _update_slider_bbox_hover."""

    def test_hover_shows_border(self, mock_editor, mocker):
        """Shows border on hover."""
        mock_editor._update_slider_bbox_hover(
            'red_slider_bbox', is_hovered=True, border_color=(255, 0, 0)
        )
        assert mock_editor.red_slider_bbox.visible is True
        assert mock_editor.red_slider_bbox.dirty == 1

    def test_unhover_hides_border(self, mock_editor, mocker):
        """Hides border on unhover."""
        mock_editor.red_slider_bbox.visible = True
        mock_editor._update_slider_bbox_hover(
            'red_slider_bbox', is_hovered=False, border_color=(255, 0, 0)
        )
        assert mock_editor.red_slider_bbox.visible is False

    def test_already_visible_no_change(self, mock_editor, mocker):
        """No change when already hovered and still hovering."""
        mock_editor.red_slider_bbox.visible = True
        mock_editor._update_slider_bbox_hover(
            'red_slider_bbox', is_hovered=True, border_color=(255, 0, 0)
        )

    def test_nonexistent_bbox(self, mock_editor):
        """Does nothing when bbox attribute does not exist."""
        mock_editor._update_slider_bbox_hover(
            'nonexistent_bbox', is_hovered=True, border_color=(255, 0, 0)
        )


# ===========================================================================
# 36. Slider Text Hover Border
# ===========================================================================


class TestSliderTextHoverBorder:
    """Tests for _update_slider_text_hover_border."""

    def test_add_hover_border(self, mock_editor, mocker):
        """Adds white border on hover."""
        mock_editor.red_slider.text_sprite.hover_border_added = False
        del mock_editor.red_slider.text_sprite.hover_border_added
        mock_editor.red_slider.text_sprite.image = pygame.Surface((50, 10))
        mock_editor.red_slider.text_sprite.rect = pygame.Rect(0, 0, 50, 10)
        mock_editor._update_slider_text_hover_border('red_slider', is_text_hovered=True)
        assert mock_editor.red_slider.text_sprite.hover_border_added is True

    def test_remove_hover_border(self, mock_editor, mocker):
        """Removes hover border when no longer hovering."""
        mock_editor.red_slider.text_sprite.hover_border_added = True
        mock_editor._update_slider_text_hover_border('red_slider', is_text_hovered=False)
        assert mock_editor.red_slider.text_sprite.hover_border_added is False

    def test_nonexistent_slider(self, mock_editor):
        """Does nothing for nonexistent slider."""
        mock_editor._update_slider_text_hover_border('nonexistent_slider', is_text_hovered=True)


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
            'new description'
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

    def test_resets_panning(self, mock_editor, mocker):
        """Resets panning state."""
        mock_editor.canvas._panning_active = True
        mock_editor.canvas.pan_offset_x = 10
        mock_editor.canvas.pan_offset_y = 5
        mock_editor._reset_canvas_for_new_file(32, 32, 10)
        assert mock_editor.canvas._panning_active is False
        assert mock_editor.canvas.pan_offset_x == 0


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
            position=(5, 10)
        )
        mocker.patch.object(mock_editor.controller_handler, '_canvas_move_cursor')
        mock_editor.controller_handler._start_canvas_continuous_movement(0, 1, 0)
        assert 0 in mock_editor.controller_handler.canvas_continuous_movements
        mock_editor.controller_handler._canvas_move_cursor.assert_called_once_with(0, 1, 0)

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
            }
        }
        mock_editor.controller_handler.canvas_continuous_movements = movements
        mock_editor.canvas_continuous_movements = movements
        mock_editor.mode_switcher.get_controller_position.return_value = mocker.Mock(
            position=(6, 10)
        )
        mock_editor.mode_switcher.get_controller_mode.return_value = mocker.Mock(value='canvas')
        mock_editor.controller_handler._stop_canvas_continuous_movement(0)
        assert 0 not in mock_editor.controller_handler.canvas_continuous_movements

    def test_stop_nonexistent_movement(self, mock_editor):
        """Does nothing when stopping nonexistent movement."""
        mock_editor.controller_handler.canvas_continuous_movements = {}
        mock_editor.controller_handler._stop_canvas_continuous_movement(0)

    def test_update_canvas_no_movements(self, mock_editor):
        """Does nothing when no continuous movements exist."""
        mock_editor.controller_handler.canvas_continuous_movements = {}
        mock_editor.controller_handler._update_canvas_continuous_movements()


# ===========================================================================
# 44. Detect Clicked Slider
# ===========================================================================


class TestDetectClickedSlider:
    """Tests for _detect_clicked_slider."""

    def test_detects_red_slider(self, mock_editor):
        """Detects click on red slider text sprite."""
        mock_editor.red_slider.text_sprite.rect = pygame.Rect(270, 550, 50, 10)
        result = mock_editor._detect_clicked_slider((280, 555))
        assert result == 'red'

    def test_detects_green_slider(self, mock_editor):
        """Detects click on green slider text sprite."""
        mock_editor.green_slider.text_sprite.rect = pygame.Rect(270, 560, 50, 10)
        result = mock_editor._detect_clicked_slider((280, 565))
        assert result == 'green'

    def test_detects_blue_slider(self, mock_editor):
        """Detects click on blue slider text sprite."""
        mock_editor.blue_slider.text_sprite.rect = pygame.Rect(270, 570, 50, 10)
        result = mock_editor._detect_clicked_slider((280, 575))
        assert result == 'blue'

    def test_no_slider_clicked(self, mock_editor):
        """Returns None when no slider is clicked."""
        result = mock_editor._detect_clicked_slider((0, 0))
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
            mock_editor.film_strip_coordinator, '_update_film_strip_layout_after_rename'
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
        mock_editor.film_strip_sprites = {'default': mocker.Mock()}
        mocker.patch.object(mock_editor.film_strip_coordinator, '_mark_film_strip_sprites_dirty')
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
            'I apologize, I cannot generate that'
        )
        assert result is True


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
    """Tests for _finalize_canvas_setup (static method)."""

    def test_starts_animation(self, mocker):
        """Starts animation and sets WIDTH/HEIGHT."""
        animated_sprite = mocker.Mock()
        options = {'size': '16x16'}
        BitmapEditorScene._finalize_canvas_setup(animated_sprite, options)
        animated_sprite.play.assert_called_once()


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
