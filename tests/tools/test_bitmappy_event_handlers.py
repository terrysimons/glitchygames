"""Tests for BitmapEditorScene event handler methods in glitchygames/tools/bitmappy.py.

Covers menu event dispatch, keyboard handlers, mouse handlers,
controller handlers, and setup/lifecycle helpers.
"""

from types import SimpleNamespace

import pygame
import pytest

from glitchygames.bitmappy import editor as bitmappy
from glitchygames.bitmappy.editor import BitmapEditorScene
from tests.mocks import MockFactory


def _make_event(**kwargs):
    """Create a simple namespace event that supports attribute access like HashableEvent.

    Returns:
        A SimpleNamespace with the given attributes.
    """
    return SimpleNamespace(**kwargs)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _ensure_pygame_init():
    """Ensure pygame is initialized for all tests in this module."""
    if not pygame.get_init():  # pragma: no branch
        pygame.init()
    # get_surface() returns None before set_mode() despite stubs saying Surface
    surface: pygame.Surface | None = pygame.display.get_surface()
    if surface is None:  # pragma: no branch
        pygame.display.set_mode((800, 600))


@pytest.fixture
def pygame_mocks(mocker):
    """Set up pygame mocks for sprite tests.

    Returns:
        The mock objects created by MockFactory.
    """
    return MockFactory.setup_pygame_mocks_with_mocker(mocker)


@pytest.fixture
def mock_editor(mocker, pygame_mocks):  # noqa: PLR0915
    """Create a minimal BitmapEditorScene with heavy dependencies mocked out.

    Returns:
        A BitmapEditorScene instance with all dependencies mocked.
    """
    mocker.patch.object(BitmapEditorScene, '__init__', return_value=None)

    editor = BitmapEditorScene.__new__(BitmapEditorScene)

    # -- Minimal Scene-like state --
    editor.options = {
        'size': '32x32',
        'debug_events': False,
        'no_unhandled_events': True,
    }
    editor.dirty = 0
    editor.log = bitmappy.LOG
    editor.screen_width = 800
    editor.screen_height = 600

    # -- Sliders --
    editor.red_slider = mocker.Mock()
    editor.red_slider.value = 128
    editor.green_slider = mocker.Mock()
    editor.green_slider.value = 64
    editor.blue_slider = mocker.Mock()
    editor.blue_slider.value = 32
    editor.alpha_slider = mocker.Mock()
    editor.alpha_slider.value = 255

    # -- Color well --
    editor.color_well = mocker.Mock()
    editor.color_well.active_color = (128, 64, 32, 255)
    editor.color_well.dirty = 0

    # -- Canvas --
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

    # -- Animated sprite on canvas --
    editor.canvas.animated_sprite = mocker.Mock()
    editor.canvas.animated_sprite._animations = {
        'default': [mocker.Mock(), mocker.Mock()],
    }
    editor.canvas.animated_sprite.frame_manager = mocker.Mock()
    editor.canvas.animated_sprite.frame_manager.current_animation = 'default'
    editor.canvas.animated_sprite.frame_manager.current_frame = 0

    # -- Multi-controller system --
    editor.multi_controller_manager = mocker.Mock()
    editor.controller_selections = {}

    # -- Mode switcher --
    editor.mode_switcher = mocker.Mock()
    editor.mode_switcher.controller_modes = {}

    # -- Visual collision manager --
    editor.visual_collision_manager = mocker.Mock()

    # -- Undo/redo --
    editor.undo_redo_manager = mocker.Mock()
    editor.undo_redo_manager.undo_stack = []
    editor.canvas_operation_tracker = mocker.Mock()
    editor.controller_position_operation_tracker = mocker.Mock()
    editor.current_pixel_changes = []
    editor._is_drag_operation = False
    editor._applying_undo_redo = False

    # -- Controller handler (extracted subsystem) --
    from glitchygames.bitmappy.controller_handler import ControllerEventHandler

    editor._controller_handler = ControllerEventHandler(editor)
    # Controller handler code references self.editor.* for state
    editor.controller_drags = editor._controller_handler.controller_drags
    editor.canvas_continuous_movements = editor._controller_handler.canvas_continuous_movements
    editor.slider_continuous_adjustments = editor._controller_handler.slider_continuous_adjustments

    # -- AI integration (extracted subsystem) --
    from glitchygames.bitmappy.ai_integration import AIIntegrationManager

    ai_integration = AIIntegrationManager.__new__(AIIntegrationManager)
    ai_integration.editor = editor
    ai_integration.log = editor.log
    ai_integration.pending_ai_requests = {}
    ai_integration.ai_request_queue = None
    ai_integration.ai_response_queue = None
    ai_integration.ai_process = None
    ai_integration.last_successful_sprite_content = None
    ai_integration.last_conversation_history = None
    editor._ai_integration = ai_integration

    # -- Film strips --
    editor.film_strips = {}
    editor.film_strip_sprites = {}
    editor.film_strip_scroll_offset = 0
    editor.max_visible_strips = 2

    # -- Film strip drag state --
    editor.is_dragging_film_strips = False
    editor.film_strip_drag_start_y = None
    editor.film_strip_drag_start_offset = None

    # -- Animated sprite --
    editor.animated_sprite = mocker.Mock()

    # -- Selection state --
    editor.selected_animation = 'default'
    editor.selected_frame = 0
    editor.selected_frame_visible = True

    # -- Frame clipboard --
    editor._frame_clipboard = None

    # -- Screen --
    editor.screen = mocker.Mock()

    # -- All sprites --
    editor.all_sprites = []

    # -- Scene manager --
    editor.scene_manager = mocker.Mock()

    # -- Next scene --
    editor.next_scene = None

    return editor


# ===========================================================================
# 1. Menu Event Dispatch (on_menu_item_event)
# ===========================================================================


class TestOnMenuItemEvent:
    """Tests for on_menu_item_event dispatch."""

    def test_system_menu_no_name(self, mock_editor, mocker):
        """Empty menu name triggers system menu log."""
        menu_mock = mocker.Mock()
        menu_mock.name = ''
        event = _make_event(menu=menu_mock)
        mock_editor.on_menu_item_event(event)
        assert mock_editor.dirty == 1

    def test_new_dispatches_to_dialog(self, mock_editor, mocker):
        """'New' menu item dispatches to on_new_canvas_dialog_event."""
        menu_mock = mocker.Mock()
        menu_mock.name = 'New'
        event = _make_event(menu=menu_mock)
        mocker.patch.object(mock_editor, 'on_new_canvas_dialog_event')
        mock_editor.on_menu_item_event(event)
        mock_editor.on_new_canvas_dialog_event.assert_called_once()
        assert mock_editor.dirty == 1

    def test_save_dispatches_to_dialog(self, mock_editor, mocker):
        """'Save' menu item dispatches to on_save_dialog_event."""
        menu_mock = mocker.Mock()
        menu_mock.name = 'Save'
        event = _make_event(menu=menu_mock)
        mocker.patch.object(mock_editor, 'on_save_dialog_event')
        mock_editor.on_menu_item_event(event)
        mock_editor.on_save_dialog_event.assert_called_once()

    def test_load_dispatches_to_dialog(self, mock_editor, mocker):
        """'Load' menu item dispatches to on_load_dialog_event."""
        menu_mock = mocker.Mock()
        menu_mock.name = 'Load'
        event = _make_event(menu=menu_mock)
        mocker.patch.object(mock_editor, 'on_load_dialog_event')
        mock_editor.on_menu_item_event(event)
        mock_editor.on_load_dialog_event.assert_called_once()

    def test_quit_calls_scene_manager_quit(self, mock_editor, mocker):
        """'Quit' menu item calls scene_manager.quit()."""
        menu_mock = mocker.Mock()
        menu_mock.name = 'Quit'
        event = _make_event(menu=menu_mock)
        mock_editor.on_menu_item_event(event)
        mock_editor.scene_manager.quit.assert_called_once()

    def test_unhandled_menu_item_logs(self, mock_editor, mocker):
        """Unknown menu items are logged but don't crash."""
        menu_mock = mocker.Mock()
        menu_mock.name = 'UnknownItem'
        event = _make_event(menu=menu_mock)
        mock_editor.on_menu_item_event(event)
        assert mock_editor.dirty == 1


# ===========================================================================
# 2. Canvas reset / New file helpers
# ===========================================================================


class TestResetCanvasForNewFile:
    """Tests for _reset_canvas_for_new_file."""

    def test_resets_dimensions_and_pixels(self, mock_editor):
        """Dimensions and pixel arrays are reset correctly."""
        mock_editor._reset_canvas_for_new_file(16, 16, 20)
        assert mock_editor.canvas.pixels_across == 16
        assert mock_editor.canvas.pixels_tall == 16
        assert mock_editor.canvas.pixel_width == 20
        assert mock_editor.canvas.pixel_height == 20
        assert len(mock_editor.canvas.pixels) == 256
        assert all(p == (255, 0, 255, 255) for p in mock_editor.canvas.pixels)
        assert all(mock_editor.canvas.dirty_pixels)

    def test_resets_panning_if_available(self, mock_editor, mocker):
        """Calls reset_panning if available on canvas."""
        mock_editor.canvas.reset_panning = mocker.Mock()
        mock_editor.canvas._panning_active = True
        mock_editor.canvas.pan_offset_x = 5
        mock_editor.canvas.pan_offset_y = 10
        mock_editor._reset_canvas_for_new_file(8, 8, 10)
        mock_editor.canvas.reset_panning.assert_called_once()
        assert mock_editor.canvas._panning_active is False
        assert mock_editor.canvas.pan_offset_x == 0
        assert mock_editor.canvas.pan_offset_y == 0


class TestOnNewFileEvent:
    """Tests for on_new_file_event."""

    def test_creates_canvas_with_valid_dimensions(self, mock_editor, mocker):
        """Valid dimension string creates a new canvas."""
        mocker.patch.object(mock_editor, '_reset_canvas_for_new_file')
        mocker.patch.object(mock_editor, '_create_fresh_animated_sprite')
        mocker.patch.object(mock_editor, '_clear_film_strips_for_new_canvas')
        mocker.patch.object(mock_editor, '_clear_ai_sprite_box')
        mocker.patch.object(mock_editor, '_update_ai_sprite_position')
        mock_editor.on_new_file_event('16x16')
        mock_editor._reset_canvas_for_new_file.assert_called_once()
        assert mock_editor.dirty == 1

    def test_invalid_dimensions_handled(self, mock_editor, mocker):
        """Invalid dimensions don't crash."""
        mocker.patch.object(mock_editor, '_reset_canvas_for_new_file')
        mock_editor.on_new_file_event('invalid')
        assert mock_editor.dirty == 1


# ===========================================================================
# 3. Slider Events
# ===========================================================================


class TestOnSliderEvent:
    """Tests for on_slider_event."""

    def test_red_slider_updated(self, mock_editor, mocker):
        """Red slider value is updated by 'R' trigger."""
        mocker.patch.object(mock_editor, '_update_slider_text_format')
        trigger = mocker.Mock()
        trigger.name = 'R'
        trigger.value = 200
        event = _make_event()
        mock_editor.on_slider_event(event, trigger)
        assert mock_editor.red_slider.value == 200

    def test_green_slider_updated(self, mock_editor, mocker):
        """Green slider value is updated by 'G' trigger."""
        mocker.patch.object(mock_editor, '_update_slider_text_format')
        trigger = mocker.Mock()
        trigger.name = 'G'
        trigger.value = 150
        event = _make_event()
        mock_editor.on_slider_event(event, trigger)
        assert mock_editor.green_slider.value == 150

    def test_blue_slider_updated(self, mock_editor, mocker):
        """Blue slider value is updated by 'B' trigger."""
        mocker.patch.object(mock_editor, '_update_slider_text_format')
        trigger = mocker.Mock()
        trigger.name = 'B'
        trigger.value = 100
        event = _make_event()
        mock_editor.on_slider_event(event, trigger)
        assert mock_editor.blue_slider.value == 100

    def test_alpha_slider_updated(self, mock_editor, mocker):
        """Alpha slider value is updated by 'A' trigger."""
        mocker.patch.object(mock_editor, '_update_slider_text_format')
        trigger = mocker.Mock()
        trigger.name = 'A'
        trigger.value = 128
        event = _make_event()
        mock_editor.on_slider_event(event, trigger)
        assert mock_editor.alpha_slider.value == 128

    def test_clamps_below_min(self, mock_editor, mocker):
        """Values below 0 are clamped to MIN_COLOR_VALUE."""
        mocker.patch.object(mock_editor, '_update_slider_text_format')
        trigger = mocker.Mock()
        trigger.name = 'R'
        trigger.value = -5
        event = _make_event()
        mock_editor.on_slider_event(event, trigger)
        assert mock_editor.red_slider.value == 0

    def test_clamps_above_max(self, mock_editor, mocker):
        """Values above 255 are clamped to MAX_COLOR_VALUE."""
        mocker.patch.object(mock_editor, '_update_slider_text_format')
        trigger = mocker.Mock()
        trigger.name = 'R'
        trigger.value = 300
        event = _make_event()
        mock_editor.on_slider_event(event, trigger)
        assert mock_editor.red_slider.value == 255

    def test_updates_color_well_and_canvas(self, mock_editor, mocker):
        """Slider event updates color well and canvas active color."""
        mocker.patch.object(mock_editor, '_update_slider_text_format')
        trigger = mocker.Mock()
        trigger.name = 'R'
        trigger.value = 200
        event = _make_event()
        mock_editor.on_slider_event(event, trigger)
        assert mock_editor.color_well.active_color == (200, 64, 32, 255)
        assert mock_editor.canvas.active_color == (200, 64, 32, 255)


# ===========================================================================
# 4. On Tab Change Event
# ===========================================================================


class TestOnTabChangeEvent:
    """Tests for on_tab_change_event."""

    def test_stores_format_and_updates_text(self, mock_editor, mocker):
        """Tab change stores the format and updates slider text."""
        mocker.patch.object(mock_editor, '_update_slider_text_format')
        mock_editor.on_tab_change_event('%X')
        assert mock_editor.slider_input_format == '%X'
        mock_editor._update_slider_text_format.assert_called_once_with('%X')


# ===========================================================================
# 5. Mouse Handlers
# ===========================================================================


class TestOnLeftMouseButtonDownEvent:
    """Tests for on_left_mouse_button_down_event."""

    def test_deactivates_slider_text_boxes(self, mock_editor, mocker):
        """Clicking outside sliders deactivates slider text boxes."""
        mocker.patch.object(mock_editor, 'sprites_at_position', return_value=[])
        mocker.patch.object(mock_editor, '_detect_clicked_slider', return_value=None)
        mocker.patch.object(mock_editor, '_commit_and_deactivate_slider')
        mocker.patch.object(mock_editor, '_is_mouse_in_film_strip_area', return_value=False)
        event = _make_event(pos=(400, 300))
        mock_editor.on_left_mouse_button_down_event(event)
        assert mock_editor._commit_and_deactivate_slider.call_count == 3

    def test_starts_film_strip_drag(self, mock_editor, mocker):
        """Clicking in film strip area starts drag scrolling."""
        mocker.patch.object(mock_editor, 'sprites_at_position', return_value=[])
        mocker.patch.object(mock_editor, '_detect_clicked_slider', return_value=None)
        mocker.patch.object(mock_editor, '_commit_and_deactivate_slider')
        mocker.patch.object(mock_editor, '_is_mouse_in_film_strip_area', return_value=True)
        event = _make_event(pos=(500, 200))
        mock_editor.on_left_mouse_button_down_event(event)
        assert mock_editor.is_dragging_film_strips is True
        assert mock_editor.film_strip_drag_start_y == 200

    def test_scroll_arrow_up_navigates(self, mock_editor, mocker):
        """Clicking visible up scroll arrow navigates to previous animation."""
        arrow = mocker.Mock()
        arrow.direction = 'up'
        arrow.visible = True
        mocker.patch.object(mock_editor, 'sprites_at_position', return_value=[arrow])
        mocker.patch.object(mock_editor, '_scroll_to_current_animation')
        mocker.patch.object(mock_editor, '_update_film_strips_for_animated_sprite_update')
        event = _make_event(pos=(500, 50))
        mock_editor.on_left_mouse_button_down_event(event)
        mock_editor.canvas.previous_animation.assert_called_once()


class TestOnLeftMouseButtonUpEvent:
    """Tests for on_left_mouse_button_up_event."""

    def test_stops_film_strip_drag(self, mock_editor, mocker):
        """Mouse up stops film strip drag scrolling."""
        mock_editor.is_dragging_film_strips = True
        mock_editor.film_strip_drag_start_y = 200
        mock_editor.film_strip_drag_start_offset = 0
        mocker.patch.object(mock_editor, 'sprites_at_position', return_value=[])
        event = _make_event(pos=(500, 250))
        mock_editor.on_left_mouse_button_up_event(event)
        assert mock_editor.is_dragging_film_strips is False
        assert mock_editor.film_strip_drag_start_y is None

    def test_delegates_to_sprites(self, mock_editor, mocker):
        """Mouse up event is forwarded to sprites at position."""
        sprite_mock = mocker.Mock()
        mocker.patch.object(mock_editor, 'sprites_at_position', return_value=[sprite_mock])
        event = _make_event(pos=(100, 100))
        mock_editor.on_left_mouse_button_up_event(event)
        sprite_mock.on_left_mouse_button_up_event.assert_called_once_with(event)


class TestOnLeftMouseDragEvent:
    """Tests for on_left_mouse_drag_event."""

    def test_film_strip_drag_scroll(self, mock_editor, mocker):
        """Drag during film strip scroll calls handler."""
        mock_editor.is_dragging_film_strips = True
        mocker.patch.object(mock_editor, '_handle_film_strip_drag_scroll')
        event = _make_event(pos=(500, 250))
        trigger = mocker.Mock()
        mock_editor.on_left_mouse_drag_event(event, trigger)
        mock_editor._handle_film_strip_drag_scroll.assert_called_once_with(250)

    def test_canvas_drag_bypasses_sprite_iteration(self, mock_editor, mocker):
        """Drag on canvas skips expensive sprite iteration."""
        mock_editor.is_dragging_film_strips = False
        mock_editor.canvas.rect = pygame.Rect(0, 24, 320, 320)
        event = _make_event(pos=(100, 100))
        trigger = mocker.Mock()
        mock_editor.on_left_mouse_drag_event(event, trigger)
        mock_editor.canvas.on_left_mouse_drag_event.assert_called_once_with(event, trigger)


class TestOnMouseMotionEvent:
    """Tests for on_mouse_motion_event."""

    def test_updates_slider_hover_effects(self, mock_editor, mocker):
        """Mouse motion updates slider hover effects."""
        mocker.patch.object(mock_editor, '_update_slider_hover_effects')
        mock_editor.all_sprites = []
        event = _make_event(pos=(400, 300))
        mock_editor.on_mouse_motion_event(event)
        mock_editor._update_slider_hover_effects.assert_called_once_with((400, 300))


class TestOnMouseButtonUpEvent:
    """Tests for on_mouse_button_up_event."""

    def test_submits_pixel_changes(self, mock_editor, mocker):
        """Mouse button up submits pixel changes and resets drag flag."""
        mock_editor.debug_text = mocker.Mock()
        mock_editor.debug_text.rect = pygame.Rect(0, 0, 10, 10)
        mock_editor.all_sprites = []
        mocker.patch.object(mock_editor, '_submit_pixel_changes_if_ready')
        event = _make_event(pos=(400, 300))
        mock_editor.on_mouse_button_up_event(event)
        mock_editor._submit_pixel_changes_if_ready.assert_called_once()
        assert mock_editor._is_drag_operation is False

    def test_releases_stuck_sliders(self, mock_editor, mocker):
        """Mouse button up releases sliders that are in dragging state."""
        mock_editor.debug_text = mocker.Mock()
        mock_editor.debug_text.rect = pygame.Rect(0, 0, 10, 10)
        mock_editor.all_sprites = []
        mock_editor.red_slider.dragging = True
        mock_editor.green_slider.dragging = True
        mock_editor.blue_slider.dragging = True
        mocker.patch.object(mock_editor, '_submit_pixel_changes_if_ready')
        event = _make_event(pos=(400, 300))
        mock_editor.on_mouse_button_up_event(event)
        assert mock_editor.red_slider.dragging is False
        assert mock_editor.green_slider.dragging is False
        assert mock_editor.blue_slider.dragging is False


# ===========================================================================
# 6. Keyboard Handlers
# ===========================================================================


class TestOnKeyDownEvent:
    """Tests for on_key_down_event."""

    def test_debug_text_active_handles_input(self, mock_editor, mocker):
        """When debug text is active, key events route to it."""
        mock_editor.debug_text = mocker.Mock()
        mock_editor.debug_text.active = True
        event = mocker.Mock()
        event.key = pygame.K_a
        result = mock_editor.on_key_down_event(event)
        mock_editor.debug_text.on_key_down_event.assert_called_once_with(event)
        assert result is None

    def test_slider_text_input_handled(self, mock_editor, mocker):
        """When slider text is active, key events route to slider."""
        mock_editor.debug_text = mocker.Mock()
        mock_editor.debug_text.active = False
        mocker.patch.object(mock_editor, '_handle_slider_text_input', return_value=None)
        event = mocker.Mock()
        event.key = pygame.K_a
        result = mock_editor.on_key_down_event(event)
        assert result is None

    def test_film_strip_text_input_handled(self, mock_editor, mocker):
        """When film strip text is active, key events route to film strip."""
        mock_editor.debug_text = mocker.Mock()
        mock_editor.debug_text.active = False
        mocker.patch.object(mock_editor, '_handle_slider_text_input', return_value=False)
        mocker.patch.object(mock_editor, '_handle_film_strip_text_input', return_value=None)
        event = mocker.Mock()
        event.key = pygame.K_a
        result = mock_editor.on_key_down_event(event)
        assert result is None

    def test_onion_skinning_toggle(self, mock_editor, mocker):
        """O key toggles onion skinning."""
        mock_editor.debug_text = mocker.Mock()
        mock_editor.debug_text.active = False
        mocker.patch.object(mock_editor, '_handle_slider_text_input', return_value=False)
        mocker.patch.object(mock_editor, '_handle_film_strip_text_input', return_value=False)
        onion_mock = mocker.Mock()
        onion_mock.toggle_global_onion_skinning.return_value = True
        mocker.patch(
            'glitchygames.bitmappy.editor.get_onion_skinning_manager',
            return_value=onion_mock,
            create=True,
        )
        mocker.patch(
            'glitchygames.bitmappy.onion_skinning.get_onion_skinning_manager',
            return_value=onion_mock,
        )
        event = mocker.Mock()
        event.key = pygame.K_o
        result = mock_editor.on_key_down_event(event)
        assert result is None
        mock_editor.canvas.force_redraw.assert_called()

    def test_ctrl_z_calls_undo(self, mock_editor, mocker):
        """Ctrl+Z triggers undo."""
        mock_editor.debug_text = mocker.Mock()
        mock_editor.debug_text.active = False
        mocker.patch.object(mock_editor, '_handle_slider_text_input', return_value=False)
        mocker.patch.object(mock_editor, '_handle_film_strip_text_input', return_value=False)
        mocker.patch.object(mock_editor, '_handle_ctrl_key_shortcuts', return_value=True)
        event = mocker.Mock()
        event.key = pygame.K_z
        event.mod = pygame.KMOD_CTRL
        result = mock_editor.on_key_down_event(event)
        assert result is None

    def test_up_arrow_navigates_animation(self, mock_editor, mocker):
        """UP arrow navigates to previous animation."""
        mock_editor.debug_text = mocker.Mock()
        mock_editor.debug_text.active = False
        mocker.patch.object(mock_editor, '_handle_slider_text_input', return_value=False)
        mocker.patch.object(mock_editor, '_handle_film_strip_text_input', return_value=False)
        mocker.patch.object(mock_editor, '_is_any_controller_in_slider_mode', return_value=False)
        mocker.patch.object(mock_editor, '_handle_arrow_key_navigation', return_value=True)
        event = mocker.Mock()
        event.key = pygame.K_UP
        event.mod = 0
        result = mock_editor.on_key_down_event(event)
        assert result is None

    def test_routes_to_canvas_when_no_special_handling(self, mock_editor, mocker):
        """Non-special keys route to canvas."""
        mock_editor.debug_text = mocker.Mock()
        mock_editor.debug_text.active = False
        mocker.patch.object(mock_editor, '_handle_slider_text_input', return_value=False)
        mocker.patch.object(mock_editor, '_handle_film_strip_text_input', return_value=False)
        mocker.patch.object(mock_editor, '_is_any_controller_in_slider_mode', return_value=False)
        mocker.patch.object(mock_editor, '_handle_arrow_key_navigation', return_value=False)
        mocker.patch.object(mock_editor, '_route_to_canvas_or_parent')
        event = mocker.Mock()
        event.key = pygame.K_x
        event.mod = 0
        mock_editor.on_key_down_event(event)
        mock_editor._route_to_canvas_or_parent.assert_called_once()


class TestOnKeyUpEvent:
    """Tests for on_key_up_event."""

    def test_ctrl_shift_arrow_commits_panned_buffer(self, mock_editor, mocker):
        """Ctrl+Shift+Arrow key release commits panned buffer."""
        mocker.patch.object(mock_editor, '_commit_panned_buffer')
        event = mocker.Mock()
        event.key = pygame.K_LEFT
        event.mod = pygame.KMOD_CTRL | pygame.KMOD_SHIFT
        mock_editor.on_key_up_event(event)
        mock_editor._commit_panned_buffer.assert_called_once()

    def test_non_ctrl_shift_arrow_passes_to_parent(self, mock_editor, mocker):
        """Non-Ctrl+Shift key releases pass to parent."""
        mocker.patch.object(BitmapEditorScene.__bases__[0], 'on_key_up_event', create=True)
        event = mocker.Mock()
        event.key = pygame.K_a
        event.mod = 0
        # Should not raise
        mock_editor.on_key_up_event(event)


# ===========================================================================
# 7. Ctrl Key Shortcuts
# ===========================================================================


class TestHandleCtrlKeyShortcuts:
    """Tests for _handle_ctrl_key_shortcuts."""

    def test_ctrl_z_calls_undo(self, mock_editor, mocker):
        """Ctrl+Z triggers undo."""
        mocker.patch.object(mock_editor, 'handle_undo')
        event = mocker.Mock()
        event.key = pygame.K_z
        result = mock_editor._handle_ctrl_key_shortcuts(event, pygame.KMOD_CTRL)
        assert result is True
        mock_editor.handle_undo.assert_called_once()

    def test_ctrl_shift_z_calls_redo(self, mock_editor, mocker):
        """Ctrl+Shift+Z triggers redo."""
        mocker.patch.object(mock_editor, 'handle_redo')
        event = mocker.Mock()
        event.key = pygame.K_z
        result = mock_editor._handle_ctrl_key_shortcuts(event, pygame.KMOD_CTRL | pygame.KMOD_SHIFT)
        assert result is True
        mock_editor.handle_redo.assert_called_once()

    def test_ctrl_y_calls_redo(self, mock_editor, mocker):
        """Ctrl+Y triggers redo."""
        mocker.patch.object(mock_editor, 'handle_redo')
        event = mocker.Mock()
        event.key = pygame.K_y
        result = mock_editor._handle_ctrl_key_shortcuts(event, pygame.KMOD_CTRL)
        assert result is True
        mock_editor.handle_redo.assert_called_once()

    def test_ctrl_c_calls_copy_frame(self, mock_editor, mocker):
        """Ctrl+C triggers copy frame."""
        mocker.patch.object(mock_editor, '_handle_copy_frame')
        event = mocker.Mock()
        event.key = pygame.K_c
        result = mock_editor._handle_ctrl_key_shortcuts(event, pygame.KMOD_CTRL)
        assert result is True
        mock_editor._handle_copy_frame.assert_called_once()

    def test_ctrl_v_calls_paste_frame(self, mock_editor, mocker):
        """Ctrl+V triggers paste frame."""
        mocker.patch.object(mock_editor, '_handle_paste_frame')
        event = mocker.Mock()
        event.key = pygame.K_v
        result = mock_editor._handle_ctrl_key_shortcuts(event, pygame.KMOD_CTRL)
        assert result is True
        mock_editor._handle_paste_frame.assert_called_once()

    def test_ctrl_shift_arrow_handles_panning(self, mock_editor, mocker):
        """Ctrl+Shift+Arrow keys trigger canvas panning."""
        mocker.patch.object(mock_editor, '_handle_canvas_panning')
        event = mocker.Mock()
        event.key = pygame.K_LEFT
        result = mock_editor._handle_ctrl_key_shortcuts(event, pygame.KMOD_CTRL | pygame.KMOD_SHIFT)
        assert result is True
        mock_editor._handle_canvas_panning.assert_called_once_with(-1, 0)

    def test_no_ctrl_returns_false(self, mock_editor, mocker):
        """Without Ctrl modifier, returns False."""
        event = mocker.Mock()
        event.key = pygame.K_z
        result = mock_editor._handle_ctrl_key_shortcuts(event, 0)
        assert result is False

    def test_unhandled_ctrl_key_returns_false(self, mock_editor, mocker):
        """Ctrl + unhandled key returns False."""
        event = mocker.Mock()
        event.key = pygame.K_q
        result = mock_editor._handle_ctrl_key_shortcuts(event, pygame.KMOD_CTRL)
        assert result is False


# ===========================================================================
# 8. Arrow Key Navigation
# ===========================================================================


class TestHandleArrowKeyNavigation:
    """Tests for _handle_arrow_key_navigation."""

    def test_up_arrow_previous_animation(self, mock_editor, mocker):
        """UP arrow navigates to previous animation."""
        mocker.patch.object(mock_editor, '_scroll_to_current_animation')
        event = mocker.Mock()
        event.key = pygame.K_UP
        result = mock_editor._handle_arrow_key_navigation(event)
        assert result is True
        mock_editor.canvas.previous_animation.assert_called_once()

    def test_down_arrow_next_animation(self, mock_editor, mocker):
        """DOWN arrow navigates to next animation."""
        mocker.patch.object(mock_editor, '_scroll_to_current_animation')
        event = mocker.Mock()
        event.key = pygame.K_DOWN
        result = mock_editor._handle_arrow_key_navigation(event)
        assert result is True
        mock_editor.canvas.next_animation.assert_called_once()

    def test_other_key_returns_false(self, mock_editor, mocker):
        """Non-arrow keys return False."""
        event = mocker.Mock()
        event.key = pygame.K_a
        result = mock_editor._handle_arrow_key_navigation(event)
        assert result is False

    def test_no_canvas_skips(self, mock_editor, mocker):
        """UP arrow with no canvas doesn't crash."""
        mock_editor.canvas = None
        event = mocker.Mock()
        event.key = pygame.K_UP
        result = mock_editor._handle_arrow_key_navigation(event)
        assert result is True


# ===========================================================================
# 9. Route to Canvas or Parent
# ===========================================================================


class TestRouteToCanvasOrParent:
    """Tests for _route_to_canvas_or_parent."""

    def test_routes_to_canvas_keyboard_handler(self, mock_editor, mocker):
        """Routes to canvas handle_keyboard_event."""
        mock_editor.canvas.handle_keyboard_event = mocker.Mock()
        event = mocker.Mock()
        event.key = pygame.K_a
        mock_editor._route_to_canvas_or_parent(event)
        mock_editor.canvas.handle_keyboard_event.assert_called_once_with(pygame.K_a)

    def test_editing_film_strip_returns_early(self, mock_editor, mocker):
        """Film strip in editing mode blocks canvas routing."""
        strip = mocker.Mock()
        strip.editing_animation = True
        mock_editor.film_strips = {'default': strip}
        event = mocker.Mock()
        event.key = pygame.K_a
        mock_editor._route_to_canvas_or_parent(event)
        assert not mock_editor.canvas.handle_keyboard_event.called


# ===========================================================================
# 10. Undo / Redo Handlers
# ===========================================================================


class TestHandleUndo:
    """Tests for handle_undo."""

    def test_no_manager_warns(self, mock_editor):
        """Warns when no undo_redo_manager exists."""
        del mock_editor.undo_redo_manager
        # Should not raise
        mock_editor.handle_undo()

    def test_frame_specific_undo(self, mock_editor):
        """Frame-specific undo is attempted first."""
        mock_editor.undo_redo_manager.can_undo_frame.return_value = True
        mock_editor.undo_redo_manager.undo_frame.return_value = True
        mock_editor.handle_undo()
        mock_editor.undo_redo_manager.undo_frame.assert_called_once_with('default', 0)

    def test_falls_back_to_global_undo(self, mock_editor, mocker):
        """Falls back to global undo when frame-specific is unavailable."""
        mock_editor.undo_redo_manager.can_undo_frame.return_value = False
        mock_editor.undo_redo_manager.can_undo.return_value = True
        mock_editor.undo_redo_manager.undo.return_value = True
        mocker.patch.object(mock_editor, '_synchronize_canvas_state_after_undo')
        mock_editor.handle_undo()
        mock_editor.undo_redo_manager.undo.assert_called_once()
        mock_editor._synchronize_canvas_state_after_undo.assert_called_once()

    def test_no_operations_to_undo(self, mock_editor):
        """No undo when nothing is available."""
        mock_editor.undo_redo_manager.can_undo_frame.return_value = False
        mock_editor.undo_redo_manager.can_undo.return_value = False
        mock_editor.handle_undo()
        mock_editor.undo_redo_manager.undo.assert_not_called()


class TestHandleRedo:
    """Tests for handle_redo."""

    def test_no_manager_warns(self, mock_editor):
        """Warns when no undo_redo_manager exists."""
        del mock_editor.undo_redo_manager
        mock_editor.handle_redo()

    def test_frame_specific_redo(self, mock_editor):
        """Frame-specific redo is attempted first."""
        mock_editor.undo_redo_manager.can_redo_frame.return_value = True
        mock_editor.undo_redo_manager.redo_frame.return_value = True
        mock_editor.handle_redo()
        mock_editor.undo_redo_manager.redo_frame.assert_called_once_with('default', 0)

    def test_falls_back_to_global_redo(self, mock_editor, mocker):
        """Falls back to global redo when frame-specific is unavailable."""
        mock_editor.undo_redo_manager.can_redo_frame.return_value = False
        mock_editor.undo_redo_manager.can_redo.return_value = True
        mock_editor.undo_redo_manager.redo.return_value = True
        mocker.patch.object(mock_editor, '_synchronize_canvas_state_after_undo')
        mock_editor.handle_redo()
        mock_editor.undo_redo_manager.redo.assert_called_once()

    def test_no_operations_to_redo(self, mock_editor):
        """No redo when nothing is available."""
        mock_editor.undo_redo_manager.can_redo_frame.return_value = False
        mock_editor.undo_redo_manager.can_redo.return_value = False
        mock_editor.handle_redo()
        mock_editor.undo_redo_manager.redo.assert_not_called()


# ===========================================================================
# 11. Canvas Panning
# ===========================================================================


class TestHandleCanvasPanning:
    """Tests for _handle_canvas_panning."""

    def test_delegates_to_canvas_pan(self, mock_editor, mocker):
        """Panning delegates to canvas.pan_canvas."""
        mock_editor.canvas.pan_canvas = mocker.Mock()
        mock_editor._handle_canvas_panning(1, 0)
        mock_editor.canvas.pan_canvas.assert_called_once_with(1, 0)

    def test_no_canvas_warns(self, mock_editor):
        """No canvas doesn't crash."""
        mock_editor.canvas = None
        mock_editor._handle_canvas_panning(1, 0)

    def test_canvas_without_pan_warns(self, mock_editor):
        """Canvas without pan_canvas method doesn't crash."""
        del mock_editor.canvas.pan_canvas
        mock_editor._handle_canvas_panning(1, 0)


# ===========================================================================
# 12. Copy / Paste Frame
# ===========================================================================


class TestHandleCopyFrame:
    """Tests for _handle_copy_frame."""

    def test_no_canvas_warns(self, mock_editor):
        """No canvas doesn't crash."""
        mock_editor.canvas = None
        mock_editor._handle_copy_frame()

    def test_no_selected_animation_warns(self, mock_editor):
        """No selected animation warns."""
        del mock_editor.selected_animation
        mock_editor._handle_copy_frame()

    def test_none_animation_warns(self, mock_editor):
        """None animation warns."""
        mock_editor.selected_animation = None
        mock_editor._handle_copy_frame()

    def test_animation_not_found_warns(self, mock_editor):
        """Animation not in sprite warns."""
        mock_editor.selected_animation = 'nonexistent'
        mock_editor._handle_copy_frame()

    def test_frame_out_of_range_warns(self, mock_editor):
        """Frame index out of range warns."""
        mock_editor.selected_frame = 99
        mock_editor._handle_copy_frame()

    def test_successful_copy(self, mock_editor, mocker):
        """Successful copy stores frame data in clipboard."""
        frame_obj = mocker.Mock()
        frame_obj.get_pixel_data.return_value = [(255, 0, 0)] * 16
        frame_obj.get_size.return_value = (4, 4)
        frame_obj.duration = 1.0
        mock_editor.canvas.animated_sprite._animations = {
            'default': [frame_obj, mocker.Mock()],
        }
        mock_editor.selected_frame = 0
        mock_editor._handle_copy_frame()
        assert mock_editor._frame_clipboard is not None
        assert mock_editor._frame_clipboard['width'] == 4
        assert mock_editor._frame_clipboard['height'] == 4


class TestHandlePasteFrame:
    """Tests for _handle_paste_frame."""

    def test_no_canvas_warns(self, mock_editor):
        """No canvas doesn't crash."""
        mock_editor.canvas = None
        mock_editor._handle_paste_frame()

    def test_no_clipboard_warns(self, mock_editor):
        """Empty clipboard warns."""
        mock_editor._frame_clipboard = None
        mock_editor._handle_paste_frame()

    def test_dimension_mismatch_warns(self, mock_editor, mocker):
        """Mismatched dimensions prevent paste."""
        mock_editor._frame_clipboard = {
            'pixels': [(255, 0, 0)] * 16,
            'width': 4,
            'height': 4,
            'duration': 1.0,
            'animation': 'default',
            'frame': 0,
        }
        frame_obj = mocker.Mock()
        frame_obj.get_size.return_value = (8, 8)  # Different size
        frame_obj.get_pixel_data.return_value = [(0, 0, 0)] * 64
        mock_editor.canvas.animated_sprite._animations = {
            'default': [frame_obj],
        }
        mock_editor._handle_paste_frame()
        # Should not crash, paste not applied due to mismatch


# ===========================================================================
# 13. Slider Text Input
# ===========================================================================


class TestHandleSliderTextInput:
    """Tests for _handle_slider_text_input."""

    def test_active_slider_handles_event(self, mock_editor, mocker):
        """Active slider text box handles key event."""
        mock_editor.red_slider.text_sprite = mocker.Mock()
        mock_editor.red_slider.text_sprite.active = True
        event = mocker.Mock()
        event.key = pygame.K_a
        result = mock_editor._handle_slider_text_input(event)
        assert result is None
        mock_editor.red_slider.text_sprite.on_key_down_event.assert_called_once()

    def test_escape_in_slider_returns_true(self, mock_editor, mocker):
        """Escape key in active slider returns True."""
        mock_editor.red_slider.text_sprite = mocker.Mock()
        mock_editor.red_slider.text_sprite.active = True
        event = mocker.Mock()
        event.key = pygame.K_ESCAPE
        result = mock_editor._handle_slider_text_input(event)
        assert result is True

    def test_no_active_slider_returns_false(self, mock_editor, mocker):
        """No active slider text box returns False."""
        # Remove text_sprite attribute from all sliders so they appear inactive
        mock_editor.red_slider = mocker.Mock(spec=['value'])
        mock_editor.red_slider.value = 128
        mock_editor.green_slider = mocker.Mock(spec=['value'])
        mock_editor.green_slider.value = 64
        mock_editor.blue_slider = mocker.Mock(spec=['value'])
        mock_editor.blue_slider.value = 32
        mock_editor.alpha_slider = mocker.Mock(spec=['value'])
        mock_editor.alpha_slider.value = 255
        result = mock_editor._handle_slider_text_input(mocker.Mock())
        assert result is False


# ===========================================================================
# 14. Film Strip Text Input
# ===========================================================================


class TestHandleFilmStripTextInput:
    """Tests for _handle_film_strip_text_input."""

    def test_no_film_strips_returns_false(self, mock_editor, mocker):
        """No film_strips attribute returns False."""
        del mock_editor.film_strips
        result = mock_editor._handle_film_strip_text_input(mocker.Mock())
        assert result is False

    def test_editing_strip_handles_event(self, mock_editor, mocker):
        """Film strip in editing mode handles keyboard input."""
        strip = mocker.Mock()
        strip.editing_animation = True
        strip.handle_keyboard_input.return_value = True
        mock_editor.film_strips = {'default': strip}
        event = mocker.Mock()
        event.key = pygame.K_a
        result = mock_editor._handle_film_strip_text_input(event)
        assert result is None

    def test_escape_in_film_strip_returns_true(self, mock_editor, mocker):
        """Escape key in editing film strip returns True."""
        strip = mocker.Mock()
        strip.editing_animation = True
        strip.handle_keyboard_input.return_value = True
        mock_editor.film_strips = {'default': strip}
        event = mocker.Mock()
        event.key = pygame.K_ESCAPE
        result = mock_editor._handle_film_strip_text_input(event)
        assert result is True


# ===========================================================================
# 15. Controller Handlers
# ===========================================================================


class TestOnControllerButtonDownEvent:
    """Tests for on_controller_button_down_event."""

    def test_no_controller_info_returns(self, mock_editor, mocker):
        """No controller info for instance_id returns early."""
        mock_editor.multi_controller_manager.get_controller_info.return_value = None
        event = mocker.Mock()
        event.instance_id = 42
        mock_editor.on_controller_button_down_event(event)
        # Should not crash

    def test_connected_controller_assigned(self, mock_editor, mocker):
        """Connected controller gets assigned on first press."""
        controller_info = mocker.Mock()
        controller_info.status.value = 'connected'
        mock_editor.multi_controller_manager.get_controller_info.return_value = controller_info
        mock_editor.multi_controller_manager.assign_controller.return_value = 0
        mock_editor.multi_controller_manager.get_controller_id.return_value = 0
        mock_editor.mode_switcher.get_controller_mode.return_value = None
        mocker.patch.object(mock_editor._controller_handler, '_handle_film_strip_button_press')
        event = mocker.Mock()
        event.instance_id = 42
        event.button = pygame.CONTROLLER_BUTTON_A
        mock_editor.on_controller_button_down_event(event)
        assert 0 in mock_editor.controller_selections

    def test_canvas_mode_dispatches_to_canvas_handler(self, mock_editor, mocker):
        """Canvas mode dispatches to _handle_canvas_button_press."""
        controller_info = mocker.Mock()
        controller_info.status.value = 'active'
        mock_editor.multi_controller_manager.get_controller_info.return_value = controller_info
        mock_editor.multi_controller_manager.get_controller_id.return_value = 0
        mode = mocker.Mock()
        mode.value = 'canvas'
        mock_editor.mode_switcher.get_controller_mode.return_value = mode
        mocker.patch.object(mock_editor._controller_handler, '_handle_canvas_button_press')
        event = mocker.Mock()
        event.instance_id = 42
        event.button = pygame.CONTROLLER_BUTTON_A
        mock_editor.on_controller_button_down_event(event)
        mock_editor._controller_handler._handle_canvas_button_press.assert_called_once_with(
            0,
            pygame.CONTROLLER_BUTTON_A,
        )

    def test_slider_mode_dispatches_to_slider_handler(self, mock_editor, mocker):
        """Slider mode dispatches to _handle_slider_button_press."""
        controller_info = mocker.Mock()
        controller_info.status.value = 'active'
        mock_editor.multi_controller_manager.get_controller_info.return_value = controller_info
        mock_editor.multi_controller_manager.get_controller_id.return_value = 0
        mode = mocker.Mock()
        mode.value = 'r_slider'
        mock_editor.mode_switcher.get_controller_mode.return_value = mode
        mocker.patch.object(mock_editor._controller_handler, '_handle_slider_button_press')
        event = mocker.Mock()
        event.instance_id = 42
        event.button = pygame.CONTROLLER_BUTTON_DPAD_LEFT
        mock_editor.on_controller_button_down_event(event)
        mock_editor._controller_handler._handle_slider_button_press.assert_called_once()


class TestHandleFilmStripButtonPress:
    """Tests for _handle_film_strip_button_press."""

    @pytest.fixture(autouse=True)
    def _setup_handle_undo(self, mock_editor, mocker):
        """Add _handle_undo to controller handler (referenced in button_handlers dict)."""
        mock_editor._controller_handler.handle_undo = mocker.Mock()

    def test_a_button_selects_frame(self, mock_editor, mocker):
        """A button calls _multi_controller_select_current_frame."""
        mocker.patch.object(
            mock_editor._controller_handler, '_multi_controller_select_current_frame'
        )
        mock_editor._controller_handler._handle_film_strip_button_press(
            0, pygame.CONTROLLER_BUTTON_A
        )
        mock_editor._controller_handler._multi_controller_select_current_frame.assert_called_once_with(
            0
        )

    def test_b_button_calls_undo(self, mock_editor, mocker):
        """B button calls _handle_undo."""
        mocker.patch.object(mock_editor, 'handle_undo')
        mock_editor._controller_handler._handle_film_strip_button_press(
            0, pygame.CONTROLLER_BUTTON_B
        )
        mock_editor.handle_undo.assert_called_once()

    def test_x_button_redo_when_visible(self, mock_editor, mocker):
        """X button calls redo when selected frame is visible."""
        mocker.patch.object(mock_editor, 'handle_redo')
        mock_editor.selected_frame_visible = True
        mock_editor._controller_handler._handle_film_strip_button_press(
            0, pygame.CONTROLLER_BUTTON_X
        )
        mock_editor.handle_redo.assert_called_once()

    def test_x_button_disabled_when_hidden(self, mock_editor, mocker):
        """X button is disabled when selected frame is hidden."""
        mocker.patch.object(mock_editor, 'handle_redo')
        mock_editor.selected_frame_visible = False
        mock_editor._controller_handler._handle_film_strip_button_press(
            0, pygame.CONTROLLER_BUTTON_X
        )
        mock_editor.handle_redo.assert_not_called()

    def test_dpad_left_previous_frame(self, mock_editor, mocker):
        """D-pad left calls previous frame."""
        mocker.patch.object(mock_editor._controller_handler, '_multi_controller_previous_frame')
        mock_editor._controller_handler._handle_film_strip_button_press(
            0, pygame.CONTROLLER_BUTTON_DPAD_LEFT
        )
        mock_editor._controller_handler._multi_controller_previous_frame.assert_called_once_with(0)

    def test_dpad_right_next_frame(self, mock_editor, mocker):
        """D-pad right calls next frame."""
        mocker.patch.object(mock_editor._controller_handler, '_multi_controller_next_frame')
        mock_editor._controller_handler._handle_film_strip_button_press(
            0, pygame.CONTROLLER_BUTTON_DPAD_RIGHT
        )
        mock_editor._controller_handler._multi_controller_next_frame.assert_called_once_with(0)

    def test_unhandled_button_no_crash(self, mock_editor, mocker):
        """Unhandled button doesn't crash."""
        # _handle_undo is referenced in the button_handlers dict, so it must exist
        mock_editor._controller_handler.handle_undo = mocker.Mock()
        mock_editor._controller_handler._handle_film_strip_button_press(0, 999)


class TestHandleCanvasButtonPress:
    """Tests for _handle_canvas_button_press."""

    def test_a_button_calls_handler(self, mock_editor, mocker):
        """A button dispatches to canvas A handler."""
        mocker.patch.object(mock_editor._controller_handler, '_handle_canvas_a_button')
        mock_editor._controller_handler._handle_canvas_button_press(0, pygame.CONTROLLER_BUTTON_A)
        mock_editor._controller_handler._handle_canvas_a_button.assert_called_once_with(0)

    def test_b_button_calls_undo(self, mock_editor, mocker):
        """B button calls undo."""
        mocker.patch.object(mock_editor, 'handle_undo')
        mock_editor._controller_handler._handle_canvas_button_press(0, pygame.CONTROLLER_BUTTON_B)
        mock_editor.handle_undo.assert_called_once()

    def test_y_button_calls_handler(self, mock_editor, mocker):
        """Y button dispatches to canvas Y handler."""
        mocker.patch.object(mock_editor._controller_handler, '_handle_canvas_y_button')
        mock_editor._controller_handler._handle_canvas_button_press(0, pygame.CONTROLLER_BUTTON_Y)
        mock_editor._controller_handler._handle_canvas_y_button.assert_called_once_with(0)

    def test_x_button_calls_handler(self, mock_editor, mocker):
        """X button dispatches to canvas X handler."""
        mocker.patch.object(mock_editor._controller_handler, '_handle_canvas_x_button')
        mock_editor._controller_handler._handle_canvas_button_press(0, pygame.CONTROLLER_BUTTON_X)
        mock_editor._controller_handler._handle_canvas_x_button.assert_called_once_with(0)

    def test_dpad_starts_continuous_movement(self, mock_editor, mocker):
        """D-pad buttons start continuous movement."""
        mocker.patch.object(mock_editor._controller_handler, '_start_canvas_continuous_movement')
        mock_editor._controller_handler._handle_canvas_button_press(
            0, pygame.CONTROLLER_BUTTON_DPAD_LEFT
        )
        mock_editor._controller_handler._start_canvas_continuous_movement.assert_called_once_with(
            0, -1, 0
        )

    def test_dpad_right_starts_movement(self, mock_editor, mocker):
        """D-pad right starts rightward movement."""
        mocker.patch.object(mock_editor._controller_handler, '_start_canvas_continuous_movement')
        mock_editor._controller_handler._handle_canvas_button_press(
            0, pygame.CONTROLLER_BUTTON_DPAD_RIGHT
        )
        mock_editor._controller_handler._start_canvas_continuous_movement.assert_called_once_with(
            0, 1, 0
        )

    def test_dpad_up_starts_movement(self, mock_editor, mocker):
        """D-pad up starts upward movement."""
        mocker.patch.object(mock_editor._controller_handler, '_start_canvas_continuous_movement')
        mock_editor._controller_handler._handle_canvas_button_press(
            0, pygame.CONTROLLER_BUTTON_DPAD_UP
        )
        mock_editor._controller_handler._start_canvas_continuous_movement.assert_called_once_with(
            0, 0, -1
        )

    def test_dpad_down_starts_movement(self, mock_editor, mocker):
        """D-pad down starts downward movement."""
        mocker.patch.object(mock_editor._controller_handler, '_start_canvas_continuous_movement')
        mock_editor._controller_handler._handle_canvas_button_press(
            0, pygame.CONTROLLER_BUTTON_DPAD_DOWN
        )
        mock_editor._controller_handler._start_canvas_continuous_movement.assert_called_once_with(
            0, 0, 1
        )

    def test_left_shoulder_calls_handler(self, mock_editor, mocker):
        """Left shoulder button dispatches to shoulder handler."""
        mocker.patch.object(mock_editor._controller_handler, '_handle_canvas_shoulder_button')
        mock_editor._controller_handler._handle_canvas_button_press(
            0, pygame.CONTROLLER_BUTTON_LEFTSHOULDER
        )
        mock_editor._controller_handler._handle_canvas_shoulder_button.assert_called_once_with(
            0, is_left=True
        )

    def test_right_shoulder_calls_handler(self, mock_editor, mocker):
        """Right shoulder button dispatches to shoulder handler."""
        mocker.patch.object(mock_editor._controller_handler, '_handle_canvas_shoulder_button')
        mock_editor._controller_handler._handle_canvas_button_press(
            0, pygame.CONTROLLER_BUTTON_RIGHTSHOULDER
        )
        mock_editor._controller_handler._handle_canvas_shoulder_button.assert_called_once_with(
            0, is_left=False
        )


class TestHandleCanvasAButton:
    """Tests for _handle_canvas_a_button."""

    def test_disabled_when_frame_hidden(self, mock_editor):
        """A button disabled when selected frame not visible."""
        mock_editor.selected_frame_visible = False
        mock_editor._controller_handler._handle_canvas_a_button(0)
        # Should not crash, no painting occurred

    def test_starts_drag_and_paints(self, mock_editor, mocker):
        """A button starts drag and paints at position."""
        mock_editor.selected_frame_visible = True
        mock_editor.mode_switcher.get_controller_position.return_value = mocker.Mock(
            is_valid=True, position=(5, 5)
        )
        mocker.patch.object(mock_editor._controller_handler, '_canvas_paint_at_controller_position')
        mock_editor._controller_handler._handle_canvas_a_button(0)
        assert 0 in mock_editor._controller_handler.controller_drags
        assert mock_editor._controller_handler.controller_drags[0]['active'] is True
        mock_editor._controller_handler._canvas_paint_at_controller_position.assert_called_once_with(
            0
        )


class TestHandleCanvasXButton:
    """Tests for _handle_canvas_x_button."""

    def test_redo_when_visible(self, mock_editor, mocker):
        """X button triggers redo when frame visible."""
        mocker.patch.object(mock_editor, 'handle_redo')
        mock_editor.selected_frame_visible = True
        mock_editor._controller_handler._handle_canvas_x_button(0)
        mock_editor.handle_redo.assert_called_once()

    def test_disabled_when_hidden(self, mock_editor, mocker):
        """X button disabled when frame hidden."""
        mocker.patch.object(mock_editor, 'handle_redo')
        mock_editor.selected_frame_visible = False
        mock_editor._controller_handler._handle_canvas_x_button(0)
        mock_editor.handle_redo.assert_not_called()


class TestHandleCanvasYButton:
    """Tests for _handle_canvas_y_button."""

    def test_toggles_visibility(self, mock_editor, mocker):
        """Y button toggles selected frame visibility."""
        mocker.patch.object(
            mock_editor._controller_handler, '_multi_controller_toggle_selected_frame_visibility'
        )
        mock_editor._controller_handler._handle_canvas_y_button(0)
        mock_editor._controller_handler._multi_controller_toggle_selected_frame_visibility.assert_called_once_with(
            0
        )


class TestHandleSliderButtonPress:
    """Tests for _handle_slider_button_press."""

    def test_dpad_left_starts_decrease(self, mock_editor, mocker):
        """D-pad left starts continuous decrease."""
        mocker.patch.object(mock_editor._controller_handler, '_start_slider_continuous_adjustment')
        mock_editor._controller_handler._handle_slider_button_press(
            0, pygame.CONTROLLER_BUTTON_DPAD_LEFT
        )
        mock_editor._controller_handler._start_slider_continuous_adjustment.assert_called_once_with(
            0, -1
        )

    def test_dpad_right_starts_increase(self, mock_editor, mocker):
        """D-pad right starts continuous increase."""
        mocker.patch.object(mock_editor._controller_handler, '_start_slider_continuous_adjustment')
        mock_editor._controller_handler._handle_slider_button_press(
            0, pygame.CONTROLLER_BUTTON_DPAD_RIGHT
        )
        mock_editor._controller_handler._start_slider_continuous_adjustment.assert_called_once_with(
            0, 1
        )

    def test_dpad_up_navigates_slider(self, mock_editor, mocker):
        """D-pad up navigates to previous slider mode."""
        mocker.patch.object(mock_editor._controller_handler, 'handle_slider_mode_navigation')
        mock_editor._controller_handler._handle_slider_button_press(
            0, pygame.CONTROLLER_BUTTON_DPAD_UP
        )
        mock_editor._controller_handler.handle_slider_mode_navigation.assert_called_once_with(
            'up', 0
        )

    def test_dpad_down_navigates_slider(self, mock_editor, mocker):
        """D-pad down navigates to next slider mode."""
        mocker.patch.object(mock_editor._controller_handler, 'handle_slider_mode_navigation')
        mock_editor._controller_handler._handle_slider_button_press(
            0, pygame.CONTROLLER_BUTTON_DPAD_DOWN
        )
        mock_editor._controller_handler.handle_slider_mode_navigation.assert_called_once_with(
            'down', 0
        )

    def test_left_shoulder_starts_fast_decrease(self, mock_editor, mocker):
        """Left shoulder starts continuous decrease by 8."""
        mocker.patch.object(mock_editor._controller_handler, '_start_slider_continuous_adjustment')
        mock_editor._controller_handler._handle_slider_button_press(
            0, pygame.CONTROLLER_BUTTON_LEFTSHOULDER
        )
        mock_editor._controller_handler._start_slider_continuous_adjustment.assert_called_once_with(
            0, -8
        )

    def test_right_shoulder_starts_fast_increase(self, mock_editor, mocker):
        """Right shoulder starts continuous increase by 8."""
        mocker.patch.object(mock_editor._controller_handler, '_start_slider_continuous_adjustment')
        mock_editor._controller_handler._handle_slider_button_press(
            0, pygame.CONTROLLER_BUTTON_RIGHTSHOULDER
        )
        mock_editor._controller_handler._start_slider_continuous_adjustment.assert_called_once_with(
            0, 8
        )

    def test_a_button_no_action(self, mock_editor):
        """A button has no action in slider mode."""
        # Should not crash
        mock_editor._controller_handler._handle_slider_button_press(0, pygame.CONTROLLER_BUTTON_A)

    def test_unhandled_button(self, mock_editor):
        """Unhandled button in slider mode doesn't crash."""
        mock_editor._controller_handler._handle_slider_button_press(0, 999)


class TestOnControllerButtonUpEvent:
    """Tests for on_controller_button_up_event."""

    def test_no_controller_id_returns(self, mock_editor, mocker):
        """Unknown instance_id returns early."""
        mock_editor.multi_controller_manager.get_controller_id.return_value = None
        event = mocker.Mock()
        event.instance_id = 42
        event.button = pygame.CONTROLLER_BUTTON_A
        mock_editor.on_controller_button_up_event(event)

    def test_dpad_release_stops_adjustments(self, mock_editor, mocker):
        """D-pad release stops slider and canvas continuous adjustments."""
        mock_editor.multi_controller_manager.get_controller_id.return_value = 0
        mock_editor.mode_switcher.get_controller_mode.return_value = mocker.Mock(value='film_strip')
        mocker.patch.object(mock_editor._controller_handler, '_stop_slider_continuous_adjustment')
        mocker.patch.object(mock_editor._controller_handler, '_stop_canvas_continuous_movement')
        mocker.patch.object(mock_editor._controller_handler, '_handle_controller_drag_end')
        event = mocker.Mock()
        event.instance_id = 42
        event.button = pygame.CONTROLLER_BUTTON_DPAD_LEFT
        mock_editor.on_controller_button_up_event(event)
        mock_editor._controller_handler._stop_slider_continuous_adjustment.assert_called_once_with(
            0
        )
        mock_editor._controller_handler._stop_canvas_continuous_movement.assert_called_once_with(0)

    def test_a_button_release_ends_drag(self, mock_editor, mocker):
        """A button release ends controller drag."""
        mock_editor.multi_controller_manager.get_controller_id.return_value = 0
        mocker.patch.object(mock_editor._controller_handler, '_stop_slider_continuous_adjustment')
        mocker.patch.object(mock_editor._controller_handler, '_stop_canvas_continuous_movement')
        mocker.patch.object(mock_editor._controller_handler, '_handle_controller_drag_end')
        event = mocker.Mock()
        event.instance_id = 42
        event.button = pygame.CONTROLLER_BUTTON_A
        mock_editor.on_controller_button_up_event(event)
        mock_editor._controller_handler._handle_controller_drag_end.assert_called_once_with(0)

    def test_slider_mode_updates_color_well(self, mock_editor, mocker):
        """Slider mode controller updates color well on button release."""
        mock_editor.multi_controller_manager.get_controller_id.return_value = 0
        mode = mocker.Mock()
        mode.value = 'r_slider'
        mock_editor.mode_switcher.get_controller_mode.return_value = mode
        mocker.patch.object(mock_editor._controller_handler, '_stop_slider_continuous_adjustment')
        mocker.patch.object(mock_editor._controller_handler, '_stop_canvas_continuous_movement')
        mocker.patch.object(mock_editor._controller_handler, '_handle_controller_drag_end')
        mock_editor.update_color_well_from_sliders = mocker.Mock()
        event = mocker.Mock()
        event.instance_id = 42
        event.button = pygame.CONTROLLER_BUTTON_DPAD_LEFT
        mock_editor.on_controller_button_up_event(event)
        mock_editor.update_color_well_from_sliders.assert_called_once()


# ===========================================================================
# 16. Controller Drag End
# ===========================================================================


class TestHandleControllerDragEnd:
    """Tests for _handle_controller_drag_end."""

    def test_no_drags_returns(self, mock_editor):
        """No controller drags returns early."""
        mock_editor._controller_handler.controller_drags = {}
        mock_editor._controller_handler._handle_controller_drag_end(0)

    def test_inactive_drag_returns(self, mock_editor):
        """Inactive drag returns early."""
        mock_editor._controller_handler.controller_drags = {0: {'active': False}}
        mock_editor._controller_handler._handle_controller_drag_end(0)

    def test_no_pixels_drawn_returns(self, mock_editor):
        """Drag with no pixels drawn doesn't submit."""
        mock_editor.mode_switcher.get_controller_position.return_value = (5, 5)
        mock_editor._controller_handler.controller_drags = {
            0: {'active': True, 'pixels_drawn': [], 'start_position': (0, 0)},
        }
        mock_editor._controller_handler._handle_controller_drag_end(0)
        assert mock_editor._controller_handler.controller_drags[0]['active'] is False

    def test_pixels_drawn_submits(self, mock_editor, mocker):
        """Drag with pixels drawn submits changes."""
        mock_editor.mode_switcher.get_controller_position.return_value = (5, 5)
        mock_editor._controller_handler.controller_drags = {
            0: {
                'active': True,
                'pixels_drawn': [
                    {'position': (1, 1), 'color': (255, 0, 0), 'old_color': (0, 0, 0)},
                ],
                'start_position': (0, 0),
            },
        }
        mocker.patch.object(
            mock_editor._controller_handler,
            '_collect_drag_pixel_changes',
            return_value=[(1, 1, (0, 0, 0), (255, 0, 0))],
        )
        mocker.patch.object(mock_editor._controller_handler, '_submit_drag_pixel_changes')
        mock_editor._controller_handler._handle_controller_drag_end(0)
        mock_editor._controller_handler._submit_drag_pixel_changes.assert_called_once()


# ===========================================================================
# 17. Controller Axis Motion
# ===========================================================================


class TestOnControllerAxisMotionEvent:
    """Tests for on_controller_axis_motion_event."""

    def test_trigger_axis_dispatches(self, mock_editor, mocker):
        """Trigger axis events dispatch to trigger handler."""
        mocker.patch.object(mock_editor._controller_handler, '_handle_trigger_axis_motion')
        event = mocker.Mock()
        event.axis = pygame.CONTROLLER_AXIS_TRIGGERLEFT
        mock_editor.on_controller_axis_motion_event(event)
        mock_editor._controller_handler._handle_trigger_axis_motion.assert_called_once_with(event)

    def test_stick_axis_returns_early(self, mock_editor, mocker):
        """Stick axis events are currently disabled and return early."""
        event = mocker.Mock()
        event.axis = pygame.CONTROLLER_AXIS_LEFTX
        # Should not raise
        mock_editor.on_controller_axis_motion_event(event)


# ===========================================================================
# 18. Film Strip Helpers
# ===========================================================================


class TestIsMouseInFilmStripArea:
    """Tests for _is_mouse_in_film_strip_area."""

    def test_no_film_strip_sprites_returns_false(self, mock_editor):
        """No film strip sprites returns False."""
        mock_editor.film_strip_sprites = {}
        assert mock_editor._is_mouse_in_film_strip_area((500, 200)) is False

    def test_mouse_in_sprite_returns_true(self, mock_editor, mocker):
        """Mouse inside film strip sprite returns True."""
        sprite = mocker.Mock()
        sprite.rect = pygame.Rect(400, 100, 200, 200)
        mock_editor.film_strip_sprites = {'default': sprite}
        assert mock_editor._is_mouse_in_film_strip_area((500, 200)) is True

    def test_mouse_outside_returns_false(self, mock_editor, mocker):
        """Mouse outside film strip sprite returns False."""
        sprite = mocker.Mock()
        sprite.rect = pygame.Rect(400, 100, 200, 200)
        mock_editor.film_strip_sprites = {'default': sprite}
        assert mock_editor._is_mouse_in_film_strip_area((50, 50)) is False


class TestFilmStripDragScroll:
    """Tests for _handle_film_strip_drag_scroll."""

    def test_not_dragging_returns(self, mock_editor):
        """Not dragging returns early."""
        mock_editor.is_dragging_film_strips = False
        mock_editor._handle_film_strip_drag_scroll(200)

    def test_no_start_y_returns(self, mock_editor):
        """No start Y returns early."""
        mock_editor.is_dragging_film_strips = True
        mock_editor.film_strip_drag_start_y = None
        mock_editor._handle_film_strip_drag_scroll(200)


class TestNavigateFrame:
    """Tests for _navigate_frame."""

    def test_no_canvas_returns(self, mock_editor):
        """No canvas returns early."""
        mock_editor.canvas = None
        mock_editor._navigate_frame(1)

    def test_no_current_animation_returns(self, mock_editor):
        """No current animation returns early."""
        mock_editor.canvas.current_animation = ''
        mock_editor._navigate_frame(1)

    def test_navigate_forward_wraps(self, mock_editor, mocker):
        """Navigating past last frame wraps to first."""
        mock_editor.canvas.current_animation = 'default'
        mock_editor.canvas.animated_sprite._animations = {
            'default': [mocker.Mock(), mocker.Mock()],
        }
        mock_editor.selected_frame = 1
        film_strip = mocker.Mock()
        mock_editor.film_strips = {'default': film_strip}
        mock_editor._navigate_frame(1)
        assert mock_editor.selected_frame == 0

    def test_navigate_backward_wraps(self, mock_editor, mocker):
        """Navigating before first frame wraps to last."""
        mock_editor.canvas.current_animation = 'default'
        mock_editor.canvas.animated_sprite._animations = {
            'default': [mocker.Mock(), mocker.Mock()],
        }
        mock_editor.selected_frame = 0
        film_strip = mocker.Mock()
        mock_editor.film_strips = {'default': film_strip}
        mock_editor._navigate_frame(-1)
        assert mock_editor.selected_frame == 1


class TestScrollFilmStrips:
    """Tests for scroll_film_strips_up and scroll_film_strips_down."""

    def test_scroll_up_decrements_offset(self, mock_editor, mocker):
        """Scrolling up decrements offset."""
        mock_editor.film_strip_scroll_offset = 1
        mocker.patch.object(mock_editor, 'update_film_strip_visibility')
        mock_editor.scroll_film_strips_up()
        assert mock_editor.film_strip_scroll_offset == 0

    def test_scroll_up_at_zero_stays(self, mock_editor):
        """Scrolling up at offset 0 stays at 0."""
        mock_editor.film_strip_scroll_offset = 0
        mock_editor.scroll_film_strips_up()
        assert mock_editor.film_strip_scroll_offset == 0

    def test_scroll_down_increments_offset(self, mock_editor, mocker):
        """Scrolling down increments offset when animations exceed visible."""
        mock_editor.canvas.animated_sprite._animations = {
            'anim1': [mocker.Mock()],
            'anim2': [mocker.Mock()],
            'anim3': [mocker.Mock()],
        }
        mock_editor.film_strip_scroll_offset = 0
        mock_editor.max_visible_strips = 2
        mocker.patch.object(mock_editor, 'update_film_strip_visibility')
        mock_editor.scroll_film_strips_down()
        assert mock_editor.film_strip_scroll_offset == 1


# ===========================================================================
# 19. Color Well and Slider Helpers
# ===========================================================================


class TestUpdateColorWellFromSliders:
    """Tests for update_color_well_from_sliders."""

    def test_updates_color_well(self, mock_editor):
        """Updates color well with slider values."""
        mock_editor.red_slider.value = 100
        mock_editor.green_slider.value = 150
        mock_editor.blue_slider.value = 200
        mock_editor.alpha_slider.value = 128
        mock_editor.update_color_well_from_sliders()
        assert mock_editor.color_well.active_color == (100, 150, 200, 128)
        assert mock_editor.dirty == 1

    def test_no_color_well_no_crash(self, mock_editor):
        """No color well doesn't crash."""
        mock_editor.color_well = None
        mock_editor.update_color_well_from_sliders()


class TestIsAnyControllerInSliderMode:
    """Tests for _is_any_controller_in_slider_mode."""

    def test_no_mode_switcher_returns_false(self, mock_editor):
        """No mode_switcher returns False."""
        del mock_editor.mode_switcher
        assert mock_editor._is_any_controller_in_slider_mode() is False

    def test_no_slider_modes_returns_false(self, mock_editor, mocker):
        """No controllers in slider mode returns False."""
        mock_editor.mode_switcher.controller_modes = {0: mocker.Mock()}
        mock_editor.mode_switcher.get_controller_mode.return_value = mocker.Mock(value='canvas')
        assert mock_editor._is_any_controller_in_slider_mode() is False

    def test_slider_mode_returns_true(self, mock_editor, mocker):
        """Controller in slider mode returns True."""
        mock_editor.mode_switcher.controller_modes = {0: mocker.Mock()}
        mock_editor.mode_switcher.get_controller_mode.return_value = mocker.Mock(value='r_slider')
        assert mock_editor._is_any_controller_in_slider_mode() is True


# ===========================================================================
# 20. Pixel Change Helpers
# ===========================================================================


class TestGetCanvasPixelColor:
    """Tests for _get_canvas_pixel_color."""

    def test_returns_color_from_interface(self, mock_editor):
        """Returns color from canvas interface."""
        mock_editor.canvas.canvas_interface.get_pixel_at.return_value = (255, 0, 0)
        result = mock_editor._controller_handler._get_canvas_pixel_color(5, 5)
        assert result == (255, 0, 0)

    def test_returns_none_no_canvas(self, mock_editor):
        """Returns None when no canvas."""
        mock_editor.canvas = None
        result = mock_editor._controller_handler._get_canvas_pixel_color(5, 5)
        assert result is None

    def test_returns_default_on_error(self, mock_editor):
        """Returns (0,0,0) on error from canvas interface."""
        mock_editor.canvas.canvas_interface.get_pixel_at.side_effect = IndexError('out of bounds')
        result = mock_editor._controller_handler._get_canvas_pixel_color(999, 999)
        assert result == (0, 0, 0)


class TestSetCanvasPixel:
    """Tests for _set_canvas_pixel."""

    def test_sets_via_interface(self, mock_editor):
        """Sets pixel via canvas interface."""
        mock_editor._controller_handler._set_canvas_pixel(5, 5, (255, 0, 0))
        mock_editor.canvas.canvas_interface.set_pixel_at.assert_called_once_with(5, 5, (255, 0, 0))

    def test_no_canvas_no_crash(self, mock_editor):
        """No canvas doesn't crash."""
        mock_editor.canvas = None
        mock_editor._controller_handler._set_canvas_pixel(5, 5, (255, 0, 0))

    def test_fallback_sets_directly(self, mock_editor):
        """Without canvas_interface, sets pixels directly."""
        del mock_editor.canvas.canvas_interface
        mock_editor._controller_handler._set_canvas_pixel(1, 1, (255, 0, 0))
        expected_idx = 1 * 32 + 1
        assert mock_editor.canvas.pixels[expected_idx] == (255, 0, 0)
        assert mock_editor.canvas.dirty_pixels[expected_idx] is True


class TestApplyPixelChangeForUndoRedo:
    """Tests for _apply_pixel_change_for_undo_redo."""

    def test_applies_change(self, mock_editor):
        """Applies pixel change and resets flag."""
        mock_editor._apply_pixel_change_for_undo_redo(5, 5, (255, 0, 0))
        mock_editor.canvas.canvas_interface.set_pixel_at.assert_called_once_with(5, 5, (255, 0, 0))
        assert mock_editor._applying_undo_redo is False

    def test_resets_flag_on_error(self, mock_editor):
        """Resets flag even on error."""
        mock_editor.canvas.canvas_interface.set_pixel_at.side_effect = RuntimeError('fail')
        with pytest.raises(RuntimeError):
            mock_editor._apply_pixel_change_for_undo_redo(5, 5, (255, 0, 0))
        assert mock_editor._applying_undo_redo is False

    def test_no_canvas_warns(self, mock_editor):
        """No canvas warns."""
        mock_editor.canvas = None
        mock_editor._apply_pixel_change_for_undo_redo(5, 5, (255, 0, 0))


class TestApplyFrameSelectionForUndoRedo:
    """Tests for _apply_frame_selection_for_undo_redo."""

    def test_applies_selection(self, mock_editor):
        """Applies frame selection."""
        result = mock_editor._apply_frame_selection_for_undo_redo('default', 0)
        assert result is True
        mock_editor.canvas.show_frame.assert_called_once_with('default', 0)

    def test_no_canvas_returns_false(self, mock_editor):
        """No canvas returns False."""
        mock_editor.canvas = None
        result = mock_editor._apply_frame_selection_for_undo_redo('default', 0)
        assert result is False


# ===========================================================================
# 21. Film Strip Selection and Update Helpers
# ===========================================================================


class TestCopyCurrentFrame:
    """Tests for _copy_current_frame."""

    def test_no_film_strips_returns_false(self, mock_editor):
        """No film strips returns False."""
        mock_editor.film_strips = {}
        assert mock_editor._copy_current_frame() is False

    def test_no_selected_animation_returns_false(self, mock_editor, mocker):
        """No matching film strip returns False."""
        strip = mocker.Mock()
        strip.current_animation = 'other'
        mock_editor.film_strips = {'other': strip}
        mock_editor.selected_animation = 'nonexistent'
        assert mock_editor._copy_current_frame() is False

    def test_active_strip_copies(self, mock_editor, mocker):
        """Active film strip copy_current_frame is called."""
        strip = mocker.Mock()
        strip.current_animation = 'default'
        strip.copy_current_frame.return_value = True
        mock_editor.film_strips = {'default': strip}
        mock_editor.selected_animation = 'default'
        assert mock_editor._copy_current_frame() is True


class TestPasteToCurrentFrame:
    """Tests for _paste_to_current_frame."""

    def test_no_film_strips_returns_false(self, mock_editor):
        """No film strips returns False."""
        mock_editor.film_strips = {}
        assert mock_editor._paste_to_current_frame() is False

    def test_active_strip_pastes(self, mock_editor, mocker):
        """Active film strip paste_to_current_frame is called."""
        strip = mocker.Mock()
        strip.current_animation = 'default'
        strip.paste_to_current_frame.return_value = True
        mock_editor.film_strips = {'default': strip}
        mock_editor.selected_animation = 'default'
        assert mock_editor._paste_to_current_frame() is True


class TestUpdateFilmStripSelectionState:
    """Tests for update_film_strip_selection_state."""

    def test_no_film_strips_returns(self, mock_editor):
        """No film strips returns early."""
        mock_editor.film_strips = {}
        mock_editor.update_film_strip_selection_state()

    def test_marks_selected_and_deselects_others(self, mock_editor, mocker):
        """Correctly marks selected and deselects other strips."""
        strip1 = mocker.Mock()
        strip1.selected_frame = 0
        strip2 = mocker.Mock()
        strip2.selected_frame = 0
        mock_editor.film_strips = {'default': strip1, 'walk': strip2}
        mock_editor.selected_animation = 'default'
        mock_editor.selected_frame = 1
        mock_editor.update_film_strip_selection_state()
        assert strip1.is_selected is True
        assert strip1.selected_frame == 1
        assert strip2.is_selected is False


class TestMarkAllFilmStripsDirty:
    """Tests for _mark_all_film_strips_dirty."""

    def test_no_film_strips_returns(self, mock_editor):
        """No film strips returns early."""
        mock_editor.film_strips = {}
        mock_editor._mark_all_film_strips_dirty()

    def test_marks_strips_dirty(self, mock_editor, mocker):
        """All strips and sprites are marked dirty."""
        strip = mocker.Mock()
        strip.animated_sprite = mocker.Mock()
        mock_editor.film_strips = {'default': strip}
        sprite = mocker.Mock()
        mock_editor.film_strip_sprites = {'default': sprite}
        mock_editor._mark_all_film_strips_dirty()
        strip.mark_dirty.assert_called_once()
        assert sprite.dirty == 2
        assert strip.animated_sprite.dirty == 2


# ===========================================================================
# 22. Synchronize Canvas State After Undo
# ===========================================================================


class TestSynchronizeCanvasStateAfterUndo:
    """Tests for _synchronize_canvas_state_after_undo."""

    def test_no_canvas_warns(self, mock_editor):
        """No canvas warns."""
        mock_editor.canvas = None
        mock_editor._synchronize_canvas_state_after_undo()

    def test_current_animation_not_found_switches(self, mock_editor, mocker):
        """Switches to first animation when current is deleted."""
        mock_editor.canvas.animated_sprite._animations = {
            'walk': [mocker.Mock()],
        }
        mock_editor.canvas.current_animation = 'deleted'
        mock_editor._synchronize_canvas_state_after_undo()
        mock_editor.canvas.show_frame.assert_called_once_with('walk', 0)

    def test_invalid_frame_adjusts(self, mock_editor, mocker):
        """Invalid frame index is adjusted to last valid frame."""
        mock_editor.canvas.animated_sprite._animations = {
            'default': [mocker.Mock()],
        }
        mock_editor.canvas.current_animation = 'default'
        mock_editor.canvas.current_frame = 5  # Out of range
        mock_editor._synchronize_canvas_state_after_undo()
        mock_editor.canvas.show_frame.assert_called_once_with('default', 0)

    def test_valid_state_forces_redraw(self, mock_editor, mocker):
        """Valid state forces redraw and updates film strips."""
        mock_editor.canvas.animated_sprite._animations = {
            'default': [mocker.Mock(), mocker.Mock()],
        }
        mock_editor.canvas.current_animation = 'default'
        mock_editor.canvas.current_frame = 0
        mocker.patch.object(mock_editor, '_update_film_strips_for_frame')
        mock_editor._synchronize_canvas_state_after_undo()
        mock_editor.canvas.force_redraw.assert_called()


# ===========================================================================
# 23. Has Single Animation Canvas
# ===========================================================================


class TestHasSingleAnimationCanvas:
    """Tests for _has_single_animation_canvas."""

    def test_single_animation_returns_true(self, mock_editor, mocker):
        """Single animation returns True."""
        mock_editor.canvas.animated_sprite.animations = {'default': [mocker.Mock()]}
        assert mock_editor._ai_integration._has_single_animation_canvas() is True

    def test_multiple_animations_returns_false(self, mock_editor, mocker):
        """Multiple animations returns False."""
        mock_editor.canvas.animated_sprite.animations = {
            'default': [mocker.Mock()],
            'walk': [mocker.Mock()],
        }
        assert mock_editor._ai_integration._has_single_animation_canvas() is False

    def test_no_canvas_returns_false(self, mock_editor):
        """No canvas returns False."""
        mock_editor.canvas = None
        assert mock_editor._ai_integration._has_single_animation_canvas() is False


# ===========================================================================
# 24. Detect Clicked Slider
# ===========================================================================


class TestDetectClickedSlider:
    """Tests for _detect_clicked_slider."""

    def test_red_slider_clicked(self, mock_editor, mocker):
        """Detects click on red slider text box."""
        mock_editor.red_slider.text_sprite = mocker.Mock()
        mock_editor.red_slider.text_sprite.rect = pygame.Rect(100, 100, 50, 20)
        result = mock_editor._detect_clicked_slider((110, 110))
        assert result == 'red'

    def test_no_slider_clicked(self, mock_editor):
        """Returns None when no slider clicked."""
        # Ensure mock sliders' text_sprite.rect.collidepoint returns False
        # so no slider is detected as clicked
        mock_editor.red_slider.text_sprite.rect.collidepoint.return_value = False
        mock_editor.green_slider.text_sprite.rect.collidepoint.return_value = False
        mock_editor.blue_slider.text_sprite.rect.collidepoint.return_value = False
        result = mock_editor._detect_clicked_slider((0, 0))
        assert result is None


# ===========================================================================
# 25. Slider Hover Helpers
# ===========================================================================


class TestIsSliderHovered:
    """Tests for _is_slider_hovered."""

    def test_hovered_returns_true(self, mock_editor):
        """Returns True when mouse is over slider."""
        mock_editor.alpha_slider.rect = pygame.Rect(100, 100, 200, 30)
        assert mock_editor._is_slider_hovered('alpha_slider', (150, 115)) is True

    def test_not_hovered_returns_false(self, mock_editor):
        """Returns False when mouse is not over slider."""
        mock_editor.alpha_slider.rect = pygame.Rect(100, 100, 200, 30)
        assert mock_editor._is_slider_hovered('alpha_slider', (0, 0)) is False

    def test_missing_slider_returns_false(self, mock_editor):
        """Returns False for nonexistent slider."""
        assert mock_editor._is_slider_hovered('nonexistent_slider', (100, 100)) is False


class TestIsSliderTextHovered:
    """Tests for _is_slider_text_hovered."""

    def test_text_hovered(self, mock_editor, mocker):
        """Returns True when hovering over slider text sprite."""
        mock_editor.red_slider.text_sprite = mocker.Mock()
        mock_editor.red_slider.text_sprite.rect = pygame.Rect(100, 100, 50, 20)
        assert mock_editor._is_slider_text_hovered('red_slider', (110, 110)) is True

    def test_missing_slider_returns_false(self, mock_editor):
        """Returns False for nonexistent slider."""
        assert mock_editor._is_slider_text_hovered('nonexistent', (100, 100)) is False


# ===========================================================================
# 26. Start / Stop Continuous Adjustments
# ===========================================================================


class TestStartSliderContinuousAdjustment:
    """Tests for _start_slider_continuous_adjustment."""

    def test_creates_adjustment_entry(self, mock_editor, mocker):
        """Creates continuous adjustment entry for controller."""
        mocker.patch.object(mock_editor._controller_handler, '_slider_adjust_value')
        mock_editor._controller_handler._start_slider_continuous_adjustment(0, -1)
        assert 0 in mock_editor._controller_handler.slider_continuous_adjustments
        assert mock_editor._controller_handler.slider_continuous_adjustments[0]['direction'] == -1
        mock_editor._controller_handler._slider_adjust_value.assert_called_once_with(0, -1)


class TestStopSliderContinuousAdjustment:
    """Tests for _stop_slider_continuous_adjustment."""

    def test_removes_adjustment_entry(self, mock_editor):
        """Removes continuous adjustment entry for controller."""
        mock_editor._controller_handler.slider_continuous_adjustments = {0: {'direction': -1}}
        mock_editor._controller_handler._stop_slider_continuous_adjustment(0)
        assert 0 not in mock_editor._controller_handler.slider_continuous_adjustments

    def test_no_entry_no_crash(self, mock_editor):
        """Missing entry doesn't crash."""
        mock_editor._controller_handler._stop_slider_continuous_adjustment(99)


# ===========================================================================
# 27. Cleanup
# ===========================================================================


class TestCleanup:
    """Tests for cleanup method."""

    def test_calls_shutdown_methods(self, mock_editor, mocker):
        """Cleanup calls AI cleanup and voice recognition cleanup."""
        mocker.patch.object(mock_editor._ai_integration, 'cleanup')
        mocker.patch.object(mock_editor, '_cleanup_voice_recognition')
        mocker.patch.object(BitmapEditorScene.__bases__[0], 'cleanup', create=True)
        mock_editor.cleanup()
        mock_editor._ai_integration.cleanup.assert_called_once()
        mock_editor._cleanup_voice_recognition.assert_called_once()


# ===========================================================================
# 28. Submit Pixel Changes
# ===========================================================================


class TestSubmitPixelChangesIfReady:
    """Tests for _submit_pixel_changes_if_ready."""

    def test_dict_path_submits(self, mock_editor):
        """Dict-based pixel changes are submitted."""
        mock_editor.current_pixel_changes_dict = {
            (1, 1): (1, 1, (0, 0, 0), (255, 0, 0)),
        }
        mock_editor._submit_pixel_changes_if_ready()
        mock_editor.canvas_operation_tracker.add_frame_pixel_changes.assert_called_once()

    def test_list_fallback_submits(self, mock_editor):
        """List-based pixel changes are submitted as fallback."""
        mock_editor.current_pixel_changes = [(1, 1, (0, 0, 0), (255, 0, 0))]
        mock_editor._submit_pixel_changes_if_ready()
        mock_editor.canvas_operation_tracker.add_frame_pixel_changes.assert_called_once()

    def test_empty_no_submission(self, mock_editor):
        """Empty pixel changes don't trigger submission."""
        mock_editor.current_pixel_changes = []
        mock_editor._submit_pixel_changes_if_ready()
        mock_editor.canvas_operation_tracker.add_frame_pixel_changes.assert_not_called()
        mock_editor.canvas_operation_tracker.add_pixel_changes.assert_not_called()


# ===========================================================================
# 29. On Color Well Event
# ===========================================================================


class TestOnColorWellEvent:
    """Tests for on_color_well_event."""

    def test_logs_event(self, mock_editor, mocker):
        """Color well event is logged."""
        event = _make_event()
        trigger = mocker.Mock()
        mock_editor.on_color_well_event(event, trigger)
        # Should not crash - just logs


# ===========================================================================
# 30. Controller ID from Event
# ===========================================================================


class TestGetControllerIdFromEvent:
    """Tests for _get_controller_id_from_event."""

    def test_instance_id_path(self, mock_editor, mocker):
        """Gets controller ID from instance_id."""
        mock_editor.multi_controller_manager.get_controller_id.return_value = 2
        event = mocker.Mock()
        event.instance_id = 42
        result = mock_editor._controller_handler._get_controller_id_from_event(event)
        assert result == 2

    def test_joystick_fallback(self, mock_editor, mocker):
        """Falls back to joy device index."""
        event = mocker.Mock(spec=[])
        event.joy = 3
        # No instance_id attribute
        result = mock_editor._controller_handler._get_controller_id_from_event(event)
        assert result == 3
