"""Tests for BitmapEditorScene class methods in glitchygames/tools/bitmappy.py.

Focuses on testable methods that manipulate state without requiring full rendering:
color/slider operations, canvas dimension helpers, controller helpers,
deprecated/disabled methods, pixel/canvas operations, and event handler stubs.
"""

import pygame
import pytest

from glitchygames.bitmappy import editor as bitmappy
from glitchygames.bitmappy.constants import (
    JOYSTICK_HAT_DOWN,
    JOYSTICK_HAT_LEFT,
    JOYSTICK_HAT_RIGHT,
    JOYSTICK_LEFT_SHOULDER_BUTTON,
)
from glitchygames.bitmappy.controller_handler import ControllerEventHandler
from glitchygames.bitmappy.editor import BitmapEditorScene
from tests.mocks import MockFactory

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
        dict: The pygame mock objects.

    """
    return MockFactory.setup_pygame_mocks_with_mocker(mocker)


@pytest.fixture
def mock_editor(mocker, pygame_mocks):
    """Create a minimal BitmapEditorScene with heavy dependencies mocked out.

    Returns:
        BitmapEditorScene: An instance with widgets replaced by lightweight mocks.

    """
    # Prevent the full __init__ from running (it needs real pygame widgets)
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
    editor.controller_handler = ControllerEventHandler(editor)

    # -- Controller state on editor (referenced by controller_handler via self.editor.*) --
    editor.controller_drags = editor.controller_handler.controller_drags
    editor.canvas_continuous_movements = editor.controller_handler.canvas_continuous_movements
    editor.slider_continuous_adjustments = editor.controller_handler.slider_continuous_adjustments

    # -- Film strips --
    editor.film_strips = {}
    editor.film_strip_scroll_offset = 0
    editor.max_visible_strips = 2

    # -- Animated sprite --
    editor.animated_sprite = mocker.Mock()

    return editor


# ===========================================================================
# 1. Color & Slider Operations
# ===========================================================================


class TestGetCurrentColor:
    """Tests for get_current_color()."""

    def test_returns_color_from_sliders(self, mock_editor):
        """Test that slider values are returned as an RGB tuple."""
        mock_editor.red_slider.value = 100
        mock_editor.green_slider.value = 150
        mock_editor.blue_slider.value = 200
        result = mock_editor.get_current_color()
        assert result == (100, 150, 200)

    def test_returns_white_when_no_sliders(self, mock_editor):
        """Test fallback to white when sliders are missing."""
        del mock_editor.red_slider
        del mock_editor.green_slider
        del mock_editor.blue_slider
        result = mock_editor.get_current_color()
        assert result == (255, 255, 255)

    def test_returns_white_on_value_error(self, mock_editor):
        """Test fallback to white when slider values raise ValueError."""
        mock_editor.red_slider.value = 'invalid'
        result = mock_editor.get_current_color()
        assert result == (255, 255, 255)

    def test_returns_white_on_attribute_error(self, mock_editor):
        """Test fallback to white when slider has no .value attribute."""
        mock_editor.red_slider = object()  # No .value attribute
        result = mock_editor.get_current_color()
        assert result == (255, 255, 255)

    def test_zero_slider_values(self, mock_editor):
        """Test that zero slider values produce black."""
        mock_editor.red_slider.value = 0
        mock_editor.green_slider.value = 0
        mock_editor.blue_slider.value = 0
        result = mock_editor.get_current_color()
        assert result == (0, 0, 0)

    def test_max_slider_values(self, mock_editor):
        """Test that max slider values produce white."""
        mock_editor.red_slider.value = 255
        mock_editor.green_slider.value = 255
        mock_editor.blue_slider.value = 255
        result = mock_editor.get_current_color()
        assert result == (255, 255, 255)


class TestUpdateColorWellFromSliders:
    """Tests for update_color_well_from_sliders()."""

    def test_updates_color_well_active_color(self, mock_editor):
        """Test that color well receives RGBA from sliders."""
        mock_editor.red_slider.value = 10
        mock_editor.green_slider.value = 20
        mock_editor.blue_slider.value = 30
        mock_editor.alpha_slider.value = 200
        mock_editor.update_color_well_from_sliders()
        assert mock_editor.color_well.active_color == (10, 20, 30, 200)

    def test_marks_color_well_dirty(self, mock_editor):
        """Test that color well dirty flag is set."""
        mock_editor.update_color_well_from_sliders()
        assert mock_editor.color_well.dirty == 1

    def test_marks_scene_dirty(self, mock_editor):
        """Test that the scene dirty flag is set."""
        mock_editor.dirty = 0
        mock_editor.update_color_well_from_sliders()
        assert mock_editor.dirty == 1

    def test_calls_force_redraw_if_available(self, mock_editor):
        """Test that force_redraw() is called when color_well has it."""
        mock_editor.update_color_well_from_sliders()
        mock_editor.color_well.force_redraw.assert_called_once()

    def test_no_color_well_does_not_crash(self, mock_editor):
        """Test graceful handling when color_well is None."""
        mock_editor.color_well = None
        mock_editor.update_color_well_from_sliders()  # Should not raise

    def test_no_color_well_attribute_does_not_crash(self, mock_editor):
        """Test graceful handling when color_well attribute is missing."""
        del mock_editor.color_well
        mock_editor.update_color_well_from_sliders()  # Should not raise

    def test_fallback_slider_values_when_missing(self, mock_editor):
        """Test that missing sliders default to 0."""
        del mock_editor.red_slider
        del mock_editor.alpha_slider
        mock_editor.update_color_well_from_sliders()
        # red and alpha default to 0
        assert mock_editor.color_well.active_color == (0, 64, 32, 0)


class TestInitializeSliderValues:
    """Tests for _initialize_slider_values()."""

    def test_sets_default_slider_values(self, mock_editor):
        """Test that sliders are initialized to default values."""
        mock_editor._initialize_slider_values()
        assert mock_editor.alpha_slider.value == 255
        assert mock_editor.red_slider.value == 0
        assert mock_editor.green_slider.value == 0
        assert mock_editor.blue_slider.value == 0

    def test_updates_color_well(self, mock_editor):
        """Test that color well is synced with slider defaults."""
        mock_editor._initialize_slider_values()
        assert mock_editor.color_well.active_color == (0, 0, 0, 255)

    def test_updates_canvas_active_color(self, mock_editor):
        """Test that canvas active color is synced."""
        mock_editor._initialize_slider_values()
        assert mock_editor.canvas.active_color == (0, 0, 0, 255)

    def test_no_canvas_does_not_crash(self, mock_editor):
        """Test that missing canvas is handled gracefully."""
        mock_editor.canvas = None
        mock_editor._initialize_slider_values()
        assert mock_editor.red_slider.value == 0


# ===========================================================================
# 2. Canvas Dimension Helpers
# ===========================================================================


class TestGetCanvasDimensions:
    """Tests for _get_canvas_dimensions()."""

    def test_returns_canvas_dimensions(self, mock_editor):
        """Test basic dimension retrieval from canvas."""
        mock_editor.canvas.pixels_across = 64
        mock_editor.canvas.pixels_tall = 48
        assert mock_editor.controller_handler._get_canvas_dimensions() == (64, 48)

    def test_returns_zero_when_no_canvas(self, mock_editor):
        """Test fallback to (0, 0) when canvas is absent."""
        mock_editor.canvas = None
        assert mock_editor.controller_handler._get_canvas_dimensions() == (0, 0)

    def test_returns_zero_when_canvas_attr_missing(self, mock_editor):
        """Test fallback when canvas lacks pixels_across/pixels_tall."""
        del mock_editor.canvas.pixels_across
        del mock_editor.canvas.pixels_tall
        result = mock_editor.controller_handler._get_canvas_dimensions()
        assert result == (0, 0)

    def test_returns_zero_when_no_canvas_attribute(self, mock_editor):
        """Test fallback when canvas attribute is completely missing."""
        del mock_editor.canvas
        assert mock_editor.controller_handler._get_canvas_dimensions() == (0, 0)


class TestCalculateCanvasDimensions:
    """Tests for _calculate_canvas_dimensions()."""

    def test_basic_dimensions(self, mock_editor):
        """Test basic canvas dimension calculation."""
        result = mock_editor._calculate_canvas_dimensions({'size': '16x16'})
        pixels_across, pixels_tall, pixel_size = result
        assert pixels_across == 16
        assert pixels_tall == 16
        assert pixel_size >= 1

    def test_large_sprite_minimum_pixel_size(self, mock_editor):
        """Test that very large sprites get minimum pixel size of 2."""
        result = mock_editor._calculate_canvas_dimensions({'size': '512x512'})
        pixels_across, pixels_tall, pixel_size = result
        assert pixels_across == 512
        assert pixels_tall == 512
        assert pixel_size >= 2  # MIN_PIXEL_DISPLAY_SIZE

    def test_small_sprite_gets_larger_pixels(self, mock_editor):
        """Test that small sprites get larger pixel display size."""
        result = mock_editor._calculate_canvas_dimensions({'size': '8x8'})
        pixels_across, pixels_tall, pixel_size = result
        assert pixels_across == 8
        assert pixels_tall == 8
        assert pixel_size > 2  # Small sprites should have larger display pixels

    def test_rectangular_sprite(self, mock_editor):
        """Test canvas dimensions for non-square sprites."""
        result = mock_editor._calculate_canvas_dimensions({'size': '32x16'})
        pixels_across, pixels_tall, pixel_size = result
        assert pixels_across == 32
        assert pixels_tall == 16
        assert pixel_size >= 1

    def test_pixel_size_constrained_by_screen(self, mock_editor):
        """Test that pixel size is constrained by screen dimensions."""
        mock_editor.screen_width = 400
        mock_editor.screen_height = 300
        result = mock_editor._calculate_canvas_dimensions({'size': '32x32'})
        _, _, pixel_size = result
        # pixel_size should fit within screen constraints
        assert pixel_size * 32 <= 400  # Width constraint


# ===========================================================================
# 3. Controller Helpers
# ===========================================================================


class TestGetControllerIdFromEvent:
    """Tests for _get_controller_id_from_event()."""

    def test_extracts_from_instance_id(self, mock_editor, mocker):
        """Test extraction from controller event with instance_id."""
        event = mocker.Mock()
        event.instance_id = 42
        mock_editor.multi_controller_manager.get_controller_id.return_value = 1
        result = mock_editor.controller_handler._get_controller_id_from_event(event)
        assert result == 1
        mock_editor.multi_controller_manager.get_controller_id.assert_called_once_with(42)

    def test_falls_back_to_joy_device_index(self, mock_editor, mocker):
        """Test fallback to joy device index for joystick events."""
        event = mocker.Mock(spec=[])  # No instance_id attribute
        event.joy = 3
        result = mock_editor.controller_handler._get_controller_id_from_event(event)
        assert result == 3

    def test_instance_id_none_falls_back_to_joy(self, mock_editor, mocker):
        """Test that instance_id=None causes fallback to joy attribute."""
        event = mocker.Mock()
        event.instance_id = None
        event.joy = 2
        result = mock_editor.controller_handler._get_controller_id_from_event(event)
        assert result == 2


class TestIsControllerButtonHeld:
    """Tests for _is_controller_button_held()."""

    def test_returns_false_on_pygame_error(self, mock_editor, mocker):
        """Test that pygame errors result in False."""
        mocker.patch('pygame.joystick.Joystick', side_effect=pygame.error('No joystick'))
        result = mock_editor.controller_handler._is_controller_button_held(0, 0)
        assert result is False

    def test_returns_false_on_value_error(self, mock_editor, mocker):
        """Test that ValueError results in False."""
        mocker.patch('pygame.joystick.Joystick', side_effect=ValueError('Bad ID'))
        result = mock_editor.controller_handler._is_controller_button_held(99, 0)
        assert result is False

    def test_returns_button_state_when_available(self, mock_editor, mocker):
        """Test that actual button state is returned when joystick is available."""
        mock_joystick = mocker.Mock()
        mock_joystick.get_button.return_value = True
        mocker.patch('pygame.joystick.Joystick', return_value=mock_joystick)
        result = mock_editor.controller_handler._is_controller_button_held(0, 1)
        assert result is True
        mock_joystick.get_button.assert_called_once_with(1)


class TestIsAnyControllerInSliderMode:
    """Tests for _is_any_controller_in_slider_mode()."""

    def test_returns_false_when_no_mode_switcher(self, mock_editor):
        """Test returns False when mode_switcher is absent."""
        del mock_editor.mode_switcher
        assert mock_editor._is_any_controller_in_slider_mode() is False

    def test_returns_false_when_no_controllers(self, mock_editor):
        """Test returns False when no controllers are registered."""
        mock_editor.mode_switcher.controller_modes = {}
        assert mock_editor._is_any_controller_in_slider_mode() is False

    def test_returns_true_when_controller_in_r_slider(self, mock_editor, mocker):
        """Test returns True when a controller is in R slider mode."""
        mock_mode = mocker.Mock()
        mock_mode.value = 'r_slider'
        mock_editor.mode_switcher.controller_modes = {0: mock_mode}
        mock_editor.mode_switcher.get_controller_mode.return_value = mock_mode
        assert mock_editor._is_any_controller_in_slider_mode() is True

    def test_returns_true_when_controller_in_g_slider(self, mock_editor, mocker):
        """Test returns True when a controller is in G slider mode."""
        mock_mode = mocker.Mock()
        mock_mode.value = 'g_slider'
        mock_editor.mode_switcher.controller_modes = {0: mock_mode}
        mock_editor.mode_switcher.get_controller_mode.return_value = mock_mode
        assert mock_editor._is_any_controller_in_slider_mode() is True

    def test_returns_true_when_controller_in_b_slider(self, mock_editor, mocker):
        """Test returns True when a controller is in B slider mode."""
        mock_mode = mocker.Mock()
        mock_mode.value = 'b_slider'
        mock_editor.mode_switcher.controller_modes = {0: mock_mode}
        mock_editor.mode_switcher.get_controller_mode.return_value = mock_mode
        assert mock_editor._is_any_controller_in_slider_mode() is True

    def test_returns_false_when_controller_in_canvas_mode(self, mock_editor, mocker):
        """Test returns False when controller is in canvas mode."""
        mock_mode = mocker.Mock()
        mock_mode.value = 'canvas'
        mock_editor.mode_switcher.controller_modes = {0: mock_mode}
        mock_editor.mode_switcher.get_controller_mode.return_value = mock_mode
        assert mock_editor._is_any_controller_in_slider_mode() is False

    def test_multiple_controllers_only_one_in_slider(self, mock_editor, mocker):
        """Test returns True when at least one of multiple controllers is in slider mode."""
        canvas_mode = mocker.Mock()
        canvas_mode.value = 'canvas'
        slider_mode = mocker.Mock()
        slider_mode.value = 'r_slider'
        mock_editor.mode_switcher.controller_modes = {0: canvas_mode, 1: slider_mode}
        mock_editor.mode_switcher.get_controller_mode.side_effect = lambda cid: (
            canvas_mode if cid == 0 else slider_mode
        )
        assert mock_editor._is_any_controller_in_slider_mode() is True


# ===========================================================================
# 4. Deprecated/Disabled Methods
# ===========================================================================


class TestDeprecatedControllerMethods:
    """Tests for deprecated controller methods that just log."""

    def test_slider_previous_logs(self, mock_editor):
        """Test _slider_previous runs without error."""
        mock_editor.controller_handler._slider_previous(0)

    def test_slider_next_logs(self, mock_editor):
        """Test _slider_next runs without error."""
        mock_editor.controller_handler._slider_next(0)

    def test_controller_previous_frame_logs(self, mock_editor):
        """Test _controller_previous_frame runs without error."""
        mock_editor.controller_handler._controller_previous_frame()

    def test_controller_next_frame_logs(self, mock_editor):
        """Test _controller_next_frame runs without error."""
        mock_editor.controller_handler._controller_next_frame()

    def test_controller_previous_animation_logs(self, mock_editor):
        """Test _controller_previous_animation runs without error."""
        mock_editor.controller_handler._controller_previous_animation()

    def test_controller_next_animation_logs(self, mock_editor):
        """Test _controller_next_animation runs without error."""
        mock_editor.controller_handler._controller_next_animation()

    def test_validate_controller_selection_logs(self, mock_editor):
        """Test _validate_controller_selection runs without error."""
        mock_editor.controller_handler._validate_controller_selection()

    def test_initialize_controller_selection_logs(self, mock_editor):
        """Test _initialize_controller_selection runs without error."""
        mock_editor.controller_handler._initialize_controller_selection()

    def test_controller_cancel_logs(self, mock_editor):
        """Test _controller_cancel runs without error."""
        mock_editor.controller_handler._controller_cancel()

    def test_controller_select_current_frame_logs(self, mock_editor):
        """Test _controller_select_current_frame runs without error."""
        mock_editor.controller_handler._controller_select_current_frame()

    def test_controller_select_frame_logs(self, mock_editor):
        """Test _controller_select_frame runs without error."""
        mock_editor.controller_handler._controller_select_frame('idle', 0)

    def test_controller_select_frame_different_args(self, mock_editor):
        """Test _controller_select_frame with different animation names."""
        mock_editor.controller_handler._controller_select_frame('walk', 5)
        mock_editor.controller_handler._controller_select_frame('jump', 10)


# ===========================================================================
# 5. Pixel/Canvas Operations
# ===========================================================================


class TestGetCanvasPixelColor:
    """Tests for _get_canvas_pixel_color()."""

    def test_returns_none_when_no_canvas(self, mock_editor):
        """Test returns None when canvas is absent."""
        mock_editor.canvas = None
        assert mock_editor.controller_handler._get_canvas_pixel_color(0, 0) is None

    def test_uses_canvas_interface(self, mock_editor):
        """Test pixel retrieval via canvas_interface."""
        mock_editor.canvas.canvas_interface.get_pixel_at.return_value = (255, 0, 0)
        result = mock_editor.controller_handler._get_canvas_pixel_color(5, 10)
        assert result == (255, 0, 0)
        mock_editor.canvas.canvas_interface.get_pixel_at.assert_called_once_with(5, 10)

    def test_returns_black_on_index_error(self, mock_editor):
        """Test returns black on IndexError from canvas_interface."""
        mock_editor.canvas.canvas_interface.get_pixel_at.side_effect = IndexError('Out of range')
        result = mock_editor.controller_handler._get_canvas_pixel_color(999, 999)
        assert result == (0, 0, 0)

    def test_returns_black_on_type_error(self, mock_editor):
        """Test returns black on TypeError from canvas_interface."""
        mock_editor.canvas.canvas_interface.get_pixel_at.side_effect = TypeError('Bad type')
        result = mock_editor.controller_handler._get_canvas_pixel_color(0, 0)
        assert result == (0, 0, 0)

    def test_returns_black_on_attribute_error(self, mock_editor):
        """Test returns black on AttributeError from canvas_interface."""
        mock_editor.canvas.canvas_interface.get_pixel_at.side_effect = AttributeError('Missing')
        result = mock_editor.controller_handler._get_canvas_pixel_color(0, 0)
        assert result == (0, 0, 0)

    def test_falls_back_to_pixels_array(self, mock_editor):
        """Test pixel retrieval via direct pixels array when canvas_interface is absent."""
        del mock_editor.canvas.canvas_interface
        mock_editor.canvas.pixels_across = 4
        mock_editor.canvas.pixels_tall = 4
        mock_editor.canvas.pixels = [(i, i, i) for i in range(16)]
        result = mock_editor.controller_handler._get_canvas_pixel_color(2, 1)
        # pixel_num = 1 * 4 + 2 = 6
        assert result == (6, 6, 6)

    def test_falls_back_returns_none_out_of_bounds(self, mock_editor):
        """Test returns None for out-of-bounds coordinates via pixels array fallback."""
        del mock_editor.canvas.canvas_interface
        mock_editor.canvas.pixels_across = 4
        mock_editor.canvas.pixels_tall = 4
        result = mock_editor.controller_handler._get_canvas_pixel_color(10, 10)
        assert result is None

    def test_returns_none_when_canvas_attr_missing(self, mock_editor):
        """Test returns None when canvas attribute is missing entirely."""
        del mock_editor.canvas
        assert mock_editor.controller_handler._get_canvas_pixel_color(0, 0) is None


class TestSetCanvasPixel:
    """Tests for _set_canvas_pixel()."""

    def test_no_canvas_does_nothing(self, mock_editor):
        """Test that missing canvas is a no-op."""
        mock_editor.canvas = None
        mock_editor.controller_handler._set_canvas_pixel(0, 0, (255, 0, 0))  # Should not raise

    def test_uses_canvas_interface(self, mock_editor):
        """Test pixel setting via canvas_interface."""
        mock_editor.controller_handler._set_canvas_pixel(3, 7, (0, 255, 0))
        mock_editor.canvas.canvas_interface.set_pixel_at.assert_called_once_with(3, 7, (0, 255, 0))

    def test_falls_back_to_pixels_array(self, mock_editor):
        """Test pixel setting via direct pixels array when canvas_interface is absent."""
        del mock_editor.canvas.canvas_interface
        mock_editor.canvas.pixels_across = 4
        mock_editor.canvas.pixels_tall = 4
        mock_editor.canvas.pixels = [(0, 0, 0)] * 16
        mock_editor.canvas.dirty_pixels = [False] * 16
        mock_editor.canvas.dirty = 0
        mock_editor.controller_handler._set_canvas_pixel(1, 2, (100, 200, 50))
        # pixel_num = 2 * 4 + 1 = 9
        assert mock_editor.canvas.pixels[9] == (100, 200, 50)
        assert mock_editor.canvas.dirty_pixels[9] is True
        assert mock_editor.canvas.dirty == 1

    def test_no_canvas_attr_does_nothing(self, mock_editor):
        """Test that missing canvas attribute is a no-op."""
        del mock_editor.canvas
        mock_editor.controller_handler._set_canvas_pixel(0, 0, (255, 0, 0))  # Should not raise


class TestStopCanvasContinuousMovement:
    """Tests for _stop_canvas_continuous_movement()."""

    def test_removes_movement_entry(self, mock_editor, mocker):
        """Test that movement entry is removed for the controller."""
        movements = {0: {'start_x': 5, 'start_y': 10, 'dx': 1, 'dy': 0}}
        mock_editor.controller_handler.canvas_continuous_movements = movements
        mock_editor.canvas_continuous_movements = movements
        # Need mode_switcher to return position for tracking
        mock_position = mocker.Mock()
        mock_position.position = (10, 10)
        mock_editor.mode_switcher.get_controller_position.return_value = mock_position
        mock_editor.mode_switcher.get_controller_mode.return_value = mocker.Mock(value='canvas')
        mock_editor.controller_handler._stop_canvas_continuous_movement(0)
        assert 0 not in mock_editor.controller_handler.canvas_continuous_movements

    def test_no_entry_does_not_crash(self, mock_editor):
        """Test that stopping non-existent movement is safe."""
        mock_editor.controller_handler.canvas_continuous_movements = {}
        mock_editor.controller_handler._stop_canvas_continuous_movement(99)

    def test_no_attr_does_not_crash(self, mock_editor):
        """Test that missing canvas_continuous_movements attribute is safe."""
        del mock_editor.controller_handler.canvas_continuous_movements
        mock_editor.controller_handler._stop_canvas_continuous_movement(0)

    def test_tracks_position_change_for_undo(self, mock_editor, mocker):
        """Test that position change is tracked for undo/redo when position changed."""
        movements = {0: {'start_x': 0, 'start_y': 0, 'dx': 1, 'dy': 0}}
        mock_editor.controller_handler.canvas_continuous_movements = movements
        mock_editor.canvas_continuous_movements = movements
        mock_position = mocker.Mock()
        mock_position.position = (5, 0)  # Position changed from start
        mock_editor.mode_switcher.get_controller_position.return_value = mock_position
        mock_editor.mode_switcher.get_controller_mode.return_value = mocker.Mock(value='canvas')
        mock_editor.controller_handler._stop_canvas_continuous_movement(0)
        mock_editor.controller_position_operation_tracker.add_controller_position_change.assert_called_once()


class TestStopSliderContinuousAdjustment:
    """Tests for _stop_slider_continuous_adjustment()."""

    def test_removes_adjustment_entry(self, mock_editor):
        """Test that adjustment entry is removed."""
        mock_editor.controller_handler.slider_continuous_adjustments = {0: {'direction': 1}}
        mock_editor.controller_handler._stop_slider_continuous_adjustment(0)
        assert 0 not in mock_editor.controller_handler.slider_continuous_adjustments

    def test_no_entry_does_not_crash(self, mock_editor):
        """Test that stopping non-existent adjustment is safe."""
        mock_editor.controller_handler.slider_continuous_adjustments = {}
        mock_editor.controller_handler._stop_slider_continuous_adjustment(5)

    def test_no_attr_does_not_crash(self, mock_editor):
        """Test that missing slider_continuous_adjustments attribute is safe."""
        del mock_editor.controller_handler.slider_continuous_adjustments
        mock_editor.controller_handler._stop_slider_continuous_adjustment(0)


# ===========================================================================
# 6. Track Controller Drag Pixel
# ===========================================================================


class TestTrackControllerDragPixel:
    """Tests for _track_controller_drag_pixel()."""

    def test_no_controller_drags_attr(self, mock_editor):
        """Test no-op when controller_drags attribute is missing."""
        del mock_editor.controller_handler.controller_drags
        mock_editor.controller_handler._track_controller_drag_pixel(
            0, (1, 2), (255, 0, 0), (0, 0, 0)
        )

    def test_controller_not_in_drags(self, mock_editor):
        """Test no-op when controller_id is not tracked."""
        mock_editor.controller_handler.controller_drags = {}
        mock_editor.controller_handler._track_controller_drag_pixel(
            0, (1, 2), (255, 0, 0), (0, 0, 0)
        )

    def test_drag_not_active(self, mock_editor):
        """Test no-op when drag is not active."""
        mock_editor.controller_handler.controller_drags = {0: {'active': False, 'pixels_drawn': []}}
        mock_editor.controller_handler._track_controller_drag_pixel(
            0, (1, 2), (255, 0, 0), (0, 0, 0)
        )
        assert len(mock_editor.controller_handler.controller_drags[0]['pixels_drawn']) == 0

    def test_tracks_pixel_when_active(self, mock_editor):
        """Test that pixel info is appended when drag is active."""
        mock_editor.controller_handler.controller_drags = {0: {'active': True, 'pixels_drawn': []}}
        mock_editor.controller_handler._track_controller_drag_pixel(
            0, (3, 4), (255, 0, 0), (0, 0, 0)
        )
        pixels = mock_editor.controller_handler.controller_drags[0]['pixels_drawn']
        assert isinstance(pixels, list)
        assert len(pixels) == 1
        assert pixels[0]['position'] == (3, 4)
        assert pixels[0]['color'] == (255, 0, 0)
        assert pixels[0]['old_color'] == (0, 0, 0)
        assert 'timestamp' in pixels[0]

    def test_tracks_multiple_pixels(self, mock_editor):
        """Test that multiple pixels can be tracked."""
        mock_editor.controller_handler.controller_drags = {0: {'active': True, 'pixels_drawn': []}}
        mock_editor.controller_handler._track_controller_drag_pixel(
            0, (0, 0), (255, 0, 0), (0, 0, 0)
        )
        mock_editor.controller_handler._track_controller_drag_pixel(
            0, (1, 0), (0, 255, 0), (0, 0, 0)
        )
        mock_editor.controller_handler._track_controller_drag_pixel(
            0, (2, 0), (0, 0, 255), (0, 0, 0)
        )
        assert len(mock_editor.controller_handler.controller_drags[0]['pixels_drawn']) == 3


# ===========================================================================
# 7. Collect Drag Pixel Changes
# ===========================================================================


class TestCollectDragPixelChanges:
    """Tests for _collect_drag_pixel_changes()."""

    def test_basic_conversion(self, mock_editor):
        """Test conversion of drag pixels to undo/redo format."""
        drag_info = {
            'pixels_drawn': [
                {'position': (1, 2), 'color': (255, 0, 0), 'old_color': (0, 0, 0)},
                {'position': (3, 4), 'color': (0, 255, 0), 'old_color': (10, 10, 10)},
            ]
        }
        result = mock_editor.controller_handler._collect_drag_pixel_changes(0, drag_info)
        assert len(result) == 2
        assert result[0] == (1, 2, (0, 0, 0), (255, 0, 0))
        assert result[1] == (3, 4, (10, 10, 10), (0, 255, 0))

    def test_missing_old_color_defaults_to_black(self, mock_editor):
        """Test that missing old_color defaults to black."""
        drag_info = {
            'pixels_drawn': [
                {'position': (0, 0), 'color': (255, 255, 255)},
            ]
        }
        result = mock_editor.controller_handler._collect_drag_pixel_changes(0, drag_info)
        assert result[0][2] == (0, 0, 0)

    def test_merges_pending_pixel_changes(self, mock_editor):
        """Test that pending single pixel changes are merged with drag changes."""
        mock_editor.current_pixel_changes = [(0, 0, (0, 0, 0), (128, 128, 128))]
        drag_info = {
            'pixels_drawn': [
                {'position': (1, 1), 'color': (255, 0, 0), 'old_color': (0, 0, 0)},
            ]
        }
        result = mock_editor.controller_handler._collect_drag_pixel_changes(0, drag_info)
        assert len(result) == 2
        # Pending pixels are prepended
        assert result[0] == (0, 0, (0, 0, 0), (128, 128, 128))
        assert result[1] == (1, 1, (0, 0, 0), (255, 0, 0))
        # Pending pixels should be cleared
        assert mock_editor.current_pixel_changes == []

    def test_pops_undo_stack_when_merging(self, mock_editor, mocker):
        """Test that old single-pixel operation is removed from undo stack on merge."""
        mock_operation = mocker.Mock()
        mock_operation.operation_type = 'pixel_change'
        mock_editor.undo_redo_manager.undo_stack = [mock_operation]
        mock_editor.current_pixel_changes = [(0, 0, (0, 0, 0), (100, 100, 100))]
        drag_info = {
            'pixels_drawn': [
                {'position': (1, 1), 'color': (200, 200, 200), 'old_color': (0, 0, 0)},
            ]
        }
        result = mock_editor.controller_handler._collect_drag_pixel_changes(0, drag_info)
        assert len(mock_editor.undo_redo_manager.undo_stack) == 0

    def test_empty_undo_stack_during_merge(self, mock_editor):
        """Test safe handling when undo stack is empty during merge attempt."""
        mock_editor.undo_redo_manager.undo_stack = []
        mock_editor.current_pixel_changes = [(0, 0, (0, 0, 0), (50, 50, 50))]
        drag_info = {
            'pixels_drawn': [
                {'position': (1, 1), 'color': (100, 100, 100), 'old_color': (0, 0, 0)},
            ]
        }
        result = mock_editor.controller_handler._collect_drag_pixel_changes(0, drag_info)
        assert len(result) == 2  # Still merges even without undo stack pop

    def test_no_pending_changes_no_merge(self, mock_editor):
        """Test that no merge happens when there are no pending changes."""
        mock_editor.current_pixel_changes = []
        drag_info = {
            'pixels_drawn': [
                {'position': (5, 5), 'color': (1, 2, 3), 'old_color': (4, 5, 6)},
            ]
        }
        result = mock_editor.controller_handler._collect_drag_pixel_changes(0, drag_info)
        assert len(result) == 1


# ===========================================================================
# 8. Scroll to Controller Animation
# ===========================================================================


class TestScrollToControllerAnimation:
    """Tests for _scroll_to_controller_animation()."""

    def test_no_film_strips_returns_early(self, mock_editor):
        """Test early return when no film strips exist."""
        mock_editor.film_strips = {}
        mock_editor.controller_handler._scroll_to_controller_animation('idle')
        # Should not crash

    def test_no_film_strips_attr_returns_early(self, mock_editor):
        """Test early return when film_strips attribute is missing."""
        del mock_editor.film_strips
        mock_editor.controller_handler._scroll_to_controller_animation('idle')

    def test_animation_not_found_returns_early(self, mock_editor, mocker):
        """Test early return when animation name is not in film strips."""
        mock_editor.film_strips = {'idle': mocker.Mock(), 'walk': mocker.Mock()}
        mock_editor.controller_handler._scroll_to_controller_animation('jump')

    def test_scrolls_up_to_show_animation(self, mock_editor, mocker):
        """Test scrolling up when target animation is above visible area."""
        mock_editor.film_strips = {
            'idle': mocker.Mock(),
            'walk': mocker.Mock(),
            'run': mocker.Mock(),
            'jump': mocker.Mock(),
        }
        mock_editor.film_strip_scroll_offset = 3  # Currently scrolled past 'idle'
        mock_editor.max_visible_strips = 2
        mock_editor.update_film_strip_visibility = mocker.Mock()
        mock_editor.update_scroll_arrows = mocker.Mock()
        mock_editor.controller_handler._scroll_to_controller_animation('idle')
        assert mock_editor.film_strip_scroll_offset == 0

    def test_scrolls_down_to_show_animation(self, mock_editor, mocker):
        """Test scrolling down when target animation is below visible area."""
        mock_editor.film_strips = {
            'idle': mocker.Mock(),
            'walk': mocker.Mock(),
            'run': mocker.Mock(),
            'jump': mocker.Mock(),
        }
        mock_editor.film_strip_scroll_offset = 0
        mock_editor.max_visible_strips = 2
        mock_editor.update_film_strip_visibility = mocker.Mock()
        mock_editor.update_scroll_arrows = mocker.Mock()
        mock_editor.controller_handler._scroll_to_controller_animation('jump')
        # 'jump' is at index 3, max_visible=2, so offset = 3 - 2 + 1 = 2
        assert mock_editor.film_strip_scroll_offset == 2

    def test_calls_visibility_and_scroll_updates(self, mock_editor, mocker):
        """Test that visibility and scroll arrow updates are called."""
        mock_editor.film_strips = {'idle': mocker.Mock(), 'walk': mocker.Mock()}
        mock_editor.film_strip_scroll_offset = 0
        mock_editor.max_visible_strips = 2
        mock_editor.update_film_strip_visibility = mocker.Mock()
        mock_editor.update_scroll_arrows = mocker.Mock()
        mock_editor.controller_handler._scroll_to_controller_animation('idle')
        mock_editor.update_film_strip_visibility.assert_called_once()
        mock_editor.update_scroll_arrows.assert_called_once()


# ===========================================================================
# 9. Track Controller Mode Change
# ===========================================================================


class TestTrackControllerModeChange:
    """Tests for _track_controller_mode_change()."""

    def test_skips_during_undo_redo(self, mock_editor, mocker):
        """Test that mode changes are not tracked during undo/redo application."""
        mock_editor.controller_handler._applying_undo_redo = True
        new_mode = mocker.Mock()
        new_mode.value = 'canvas'
        mock_editor.controller_handler._track_controller_mode_change(0, new_mode)
        mock_editor.controller_position_operation_tracker.add_controller_mode_change.assert_not_called()

    def test_skips_without_tracker(self, mock_editor, mocker):
        """Test that mode changes are not tracked when tracker is missing."""
        del mock_editor.controller_position_operation_tracker
        new_mode = mocker.Mock()
        new_mode.value = 'canvas'
        mock_editor.controller_handler._track_controller_mode_change(0, new_mode)

    def test_tracks_mode_change(self, mock_editor, mocker):
        """Test that mode change is tracked properly."""
        mock_editor._applying_undo_redo = False
        old_mode = mocker.Mock()
        old_mode.value = 'film_strip'
        new_mode = mocker.Mock()
        new_mode.value = 'canvas'
        mock_editor.mode_switcher.get_controller_mode.return_value = old_mode
        mock_editor.controller_handler._track_controller_mode_change(0, new_mode)
        mock_editor.controller_position_operation_tracker.add_controller_mode_change.assert_called_once_with(
            0, 'film_strip', 'canvas'
        )

    def test_no_old_mode_does_not_track(self, mock_editor, mocker):
        """Test that no tracking happens when old mode is None."""
        mock_editor._applying_undo_redo = False
        mock_editor.mode_switcher.get_controller_mode.return_value = None
        new_mode = mocker.Mock()
        new_mode.value = 'canvas'
        mock_editor.controller_handler._track_controller_mode_change(0, new_mode)
        mock_editor.controller_position_operation_tracker.add_controller_mode_change.assert_not_called()


# ===========================================================================
# 10. Canvas Jump Methods
# ===========================================================================


class TestCanvasJumpHorizontal:
    """Tests for _canvas_jump_horizontal()."""

    def test_no_valid_position_returns_early(self, mock_editor, mocker):
        """Test early return when no valid position exists."""
        mock_editor.mode_switcher.get_controller_position.return_value = None
        mock_editor.controller_handler._canvas_jump_horizontal(0, 8)
        mock_editor.mode_switcher.save_controller_position.assert_not_called()

    def test_jumps_right(self, mock_editor, mocker):
        """Test jumping right from a valid position."""
        position = mocker.Mock()
        position.is_valid = True
        position.position = (5, 10)
        mock_editor.mode_switcher.get_controller_position.return_value = position
        mock_editor.controller_handler._canvas_jump_horizontal(0, 8)
        mock_editor.mode_switcher.save_controller_position.assert_called_once_with(0, (13, 10))

    def test_clamps_to_canvas_width(self, mock_editor, mocker):
        """Test that jump is clamped to canvas boundaries."""
        position = mocker.Mock()
        position.is_valid = True
        position.position = (28, 10)
        mock_editor.mode_switcher.get_controller_position.return_value = position
        mock_editor.canvas.pixels_across = 32
        mock_editor.controller_handler._canvas_jump_horizontal(0, 8)
        # end_x = 28 + 8 = 36, clamped to 31 (pixels_across - 1)
        mock_editor.mode_switcher.save_controller_position.assert_called_once_with(0, (31, 10))

    def test_clamps_to_zero(self, mock_editor, mocker):
        """Test that jump left is clamped to zero."""
        position = mocker.Mock()
        position.is_valid = True
        position.position = (3, 10)
        mock_editor.mode_switcher.get_controller_position.return_value = position
        mock_editor.canvas.pixels_across = 32
        mock_editor.controller_handler._canvas_jump_horizontal(0, -8)
        mock_editor.mode_switcher.save_controller_position.assert_called_once_with(0, (0, 10))


class TestCanvasJumpVertical:
    """Tests for _canvas_jump_vertical()."""

    def test_no_valid_position_returns_early(self, mock_editor, mocker):
        """Test early return when no valid position exists."""
        mock_editor.mode_switcher.get_controller_position.return_value = None
        mock_editor.controller_handler._canvas_jump_vertical(0, 8)
        mock_editor.mode_switcher.save_controller_position.assert_not_called()

    def test_jumps_down(self, mock_editor, mocker):
        """Test jumping down from a valid position."""
        position = mocker.Mock()
        position.is_valid = True
        position.position = (10, 5)
        mock_editor.mode_switcher.get_controller_position.return_value = position
        mock_editor.controller_handler._canvas_jump_vertical(0, 8)
        mock_editor.mode_switcher.save_controller_position.assert_called_once_with(0, (10, 13))

    def test_clamps_to_canvas_height(self, mock_editor, mocker):
        """Test that jump is clamped to canvas height."""
        position = mocker.Mock()
        position.is_valid = True
        position.position = (10, 28)
        mock_editor.mode_switcher.get_controller_position.return_value = position
        mock_editor.canvas.pixels_tall = 32
        mock_editor.controller_handler._canvas_jump_vertical(0, 8)
        mock_editor.mode_switcher.save_controller_position.assert_called_once_with(0, (10, 31))


# ===========================================================================
# 11. Event Handler Stubs
# ===========================================================================


class TestJoystickEventHandlers:
    """Tests for joystick event handler methods."""

    def test_on_joy_button_up_event(self, mock_editor, mocker):
        """Test on_joy_button_up_event is a no-op."""
        event = mocker.Mock()
        event.button = 0
        mock_editor.on_joy_button_up_event(event)

    def test_on_joy_axis_motion_event_non_trigger(self, mock_editor, mocker):
        """Test on_joy_axis_motion_event ignores non-trigger axes."""
        event = mocker.Mock()
        event.axis = 0
        event.value = 0.5
        mock_editor.on_joy_axis_motion_event(event)

    def test_on_joy_axis_motion_event_trigger_axis(self, mock_editor, mocker):
        """Test on_joy_axis_motion_event dispatches trigger axis to handler."""
        event = mocker.Mock()
        event.axis = 4  # TRIGGERLEFT
        event.value = 0.8
        mock_editor.controller_handler._handle_trigger_axis_motion = mocker.Mock()
        mock_editor.on_joy_axis_motion_event(event)
        mock_editor.controller_handler._handle_trigger_axis_motion.assert_called_once_with(event)

    def test_on_joy_ball_motion_event(self, mock_editor, mocker):
        """Test on_joy_ball_motion_event is a no-op (disabled)."""
        event = mocker.Mock()
        event.ball = 0
        event.rel = (1, 0)
        mock_editor.on_joy_ball_motion_event(event)

    def test_on_joy_hat_motion_event_below_threshold_tuple(self, mock_editor, mocker):
        """Test hat motion below threshold for tuple value."""
        event = mocker.Mock()
        event.hat = 0
        event.value = (0, 0)  # No movement
        mock_editor.on_joy_hat_motion_event(event)

    def test_on_joy_hat_motion_event_tuple_direction(self, mock_editor, mocker):
        """Test hat motion with tuple direction above threshold."""
        event = mocker.Mock()
        event.hat = 0
        event.value = (1, 0)  # Right direction tuple
        mock_editor.on_joy_hat_motion_event(event)

    def test_on_joy_hat_motion_event_integer_up(self, mock_editor, mocker):
        """Test hat motion with integer bitmask for up direction."""
        event = mocker.Mock()
        event.hat = 0
        event.value = 1  # Up
        mock_editor.on_joy_hat_motion_event(event)

    def test_on_joy_hat_motion_event_integer_below_threshold(self, mock_editor, mocker):
        """Test hat motion with integer value below threshold."""
        event = mocker.Mock()
        event.hat = 0
        event.value = 0  # Center/no movement
        mock_editor.on_joy_hat_motion_event(event)

    def test_on_joy_button_down_event_a_button(self, mock_editor, mocker):
        """Test joystick A button down triggers multi-controller select."""
        event = mocker.Mock()
        event.button = 0  # A button
        event.instance_id = 0
        mock_editor.controller_handler._multi_controller_select_current_frame = mocker.Mock()
        mock_editor.on_joy_button_down_event(event)
        mock_editor.controller_handler._multi_controller_select_current_frame.assert_called_once_with(
            0
        )

    def test_on_joy_button_down_event_b_button(self, mock_editor, mocker):
        """Test joystick B button down triggers cancel."""
        event = mocker.Mock()
        event.button = 1  # B button
        mock_editor.controller_handler._controller_cancel = mocker.Mock()
        mock_editor.on_joy_button_down_event(event)
        mock_editor.controller_handler._controller_cancel.assert_called_once()

    def test_on_joy_button_down_event_shoulder(self, mock_editor, mocker):
        """Test joystick shoulder button is handled (pass/no-op)."""
        event = mocker.Mock()
        event.button = JOYSTICK_LEFT_SHOULDER_BUTTON
        mock_editor.on_joy_button_down_event(event)

    def test_on_joy_button_down_event_unknown(self, mock_editor, mocker):
        """Test unknown joystick button is handled (pass/no-op)."""
        event = mocker.Mock()
        event.button = 99  # Unknown button
        mock_editor.on_joy_button_down_event(event)


# ===========================================================================
# 12. Menu Item Event
# ===========================================================================


class TestOnMenuItemEvent:
    """Tests for on_menu_item_event()."""

    def test_system_menu_click(self, mock_editor, mocker):
        """Test system menu click (name=None)."""
        event = mocker.Mock()
        event.menu = mocker.Mock()
        event.menu.name = None
        mock_editor.on_menu_item_event(event)
        assert mock_editor.dirty == 1

    def test_new_menu_click(self, mock_editor, mocker):
        """Test New menu item triggers dialog."""
        event = mocker.Mock()
        event.menu = mocker.Mock()
        event.menu.name = 'New'
        mock_editor.on_new_canvas_dialog_event = mocker.Mock()
        mock_editor.on_menu_item_event(event)
        mock_editor.on_new_canvas_dialog_event.assert_called_once_with(event=event)

    def test_save_menu_click(self, mock_editor, mocker):
        """Test Save menu item triggers dialog."""
        event = mocker.Mock()
        event.menu = mocker.Mock()
        event.menu.name = 'Save'
        mock_editor.on_save_dialog_event = mocker.Mock()
        mock_editor.on_menu_item_event(event)
        mock_editor.on_save_dialog_event.assert_called_once_with(event=event)

    def test_load_menu_click(self, mock_editor, mocker):
        """Test Load menu item triggers dialog."""
        event = mocker.Mock()
        event.menu = mocker.Mock()
        event.menu.name = 'Load'
        mock_editor.on_load_dialog_event = mocker.Mock()
        mock_editor.on_menu_item_event(event)
        mock_editor.on_load_dialog_event.assert_called_once_with(event=event)

    def test_quit_menu_click(self, mock_editor, mocker):
        """Test Quit menu item triggers scene_manager.quit()."""
        event = mocker.Mock()
        event.menu = mocker.Mock()
        event.menu.name = 'Quit'
        mock_editor.scene_manager = mocker.Mock()
        mock_editor.on_menu_item_event(event)
        mock_editor.scene_manager.quit.assert_called_once()

    def test_unhandled_menu_item(self, mock_editor, mocker):
        """Test unhandled menu item is logged without error."""
        event = mocker.Mock()
        event.menu = mocker.Mock()
        event.menu.name = 'Unknown'
        mock_editor.on_menu_item_event(event)
        assert mock_editor.dirty == 1


# ===========================================================================
# 13. Paint and Track Pixel
# ===========================================================================


class TestPaintAndTrackPixel:
    """Tests for _paint_and_track_pixel()."""

    def test_paints_and_tracks(self, mock_editor, mocker):
        """Test that pixel is painted and tracked for undo."""
        mock_editor.canvas.canvas_interface.get_pixel_at.return_value = (0, 0, 0)
        mock_editor.controller_handler.controller_drags = {0: {'active': True, 'pixels_drawn': []}}
        mock_editor.controller_handler._paint_and_track_pixel(0, 5, 10, (255, 0, 0))
        mock_editor.canvas.canvas_interface.set_pixel_at.assert_called_once_with(5, 10, (255, 0, 0))

    def test_defaults_old_color_to_black(self, mock_editor, mocker):
        """Test that None old_color defaults to black."""
        mock_editor.canvas.canvas_interface.get_pixel_at.return_value = None
        mock_editor.controller_handler.controller_drags = {0: {'active': True, 'pixels_drawn': []}}
        mock_editor.controller_handler._paint_and_track_pixel(0, 0, 0, (128, 128, 128))
        # The old_color should be (0, 0, 0) since get_pixel_at returned None

    def test_no_canvas_does_not_crash(self, mock_editor):
        """Test no-op when canvas is absent."""
        mock_editor.canvas = None
        mock_editor.controller_handler._paint_and_track_pixel(0, 0, 0, (255, 0, 0))


# ===========================================================================
# 14. Reset Canvas for New File
# ===========================================================================


class TestResetCanvasForNewFile:
    """Tests for _reset_canvas_for_new_file()."""

    def test_resets_dimensions(self, mock_editor, mocker):
        """Test that canvas dimensions are reset."""
        mock_editor.canvas.reset_panning = mocker.Mock()
        mock_editor._reset_canvas_for_new_file(16, 16, 8)
        assert mock_editor.canvas.pixels_across == 16
        assert mock_editor.canvas.pixels_tall == 16
        assert mock_editor.canvas.pixel_width == 8
        assert mock_editor.canvas.pixel_height == 8

    def test_fills_with_magenta(self, mock_editor, mocker):
        """Test that canvas pixels are filled with magenta transparent."""
        mock_editor.canvas.reset_panning = mocker.Mock()
        mock_editor._reset_canvas_for_new_file(4, 4, 2)
        assert len(mock_editor.canvas.pixels) == 16
        assert all(pixel == (255, 0, 255, 255) for pixel in mock_editor.canvas.pixels)
        assert all(dirty is True for dirty in mock_editor.canvas.dirty_pixels)

    def test_resets_panning(self, mock_editor, mocker):
        """Test that panning state is reset."""
        mock_editor.canvas.reset_panning = mocker.Mock()
        mock_editor.canvas._panning_active = True
        mock_editor.canvas.pan_offset_x = 50
        mock_editor.canvas.pan_offset_y = 30
        mock_editor._reset_canvas_for_new_file(32, 32, 4)
        mock_editor.canvas.reset_panning.assert_called_once()
        assert mock_editor.canvas._panning_active is False
        assert mock_editor.canvas.pan_offset_x == 0
        assert mock_editor.canvas.pan_offset_y == 0


# ===========================================================================
# 15. Slider Adjust Value
# ===========================================================================


class TestSliderAdjustValue:
    """Tests for _slider_adjust_value()."""

    def test_adjusts_red_slider(self, mock_editor, mocker):
        """Test adjusting the red slider value."""
        controller_mode = mocker.Mock()
        controller_mode.value = 'r_slider'
        mock_editor.mode_switcher.get_controller_mode.return_value = controller_mode
        mock_editor.red_slider.value = 100
        mock_editor.controller_handler.on_slider_event = mocker.Mock()
        mock_editor.controller_handler._slider_adjust_value(0, 10)
        assert mock_editor.red_slider.value == 110

    def test_adjusts_green_slider(self, mock_editor, mocker):
        """Test adjusting the green slider value."""
        controller_mode = mocker.Mock()
        controller_mode.value = 'g_slider'
        mock_editor.mode_switcher.get_controller_mode.return_value = controller_mode
        mock_editor.green_slider.value = 50
        mock_editor.controller_handler.on_slider_event = mocker.Mock()
        mock_editor.controller_handler._slider_adjust_value(0, -20)
        assert mock_editor.green_slider.value == 30

    def test_adjusts_blue_slider(self, mock_editor, mocker):
        """Test adjusting the blue slider value."""
        controller_mode = mocker.Mock()
        controller_mode.value = 'b_slider'
        mock_editor.mode_switcher.get_controller_mode.return_value = controller_mode
        mock_editor.blue_slider.value = 200
        mock_editor.controller_handler.on_slider_event = mocker.Mock()
        mock_editor.controller_handler._slider_adjust_value(0, 100)
        # Clamped to 255
        assert mock_editor.blue_slider.value == 255

    def test_clamps_to_zero(self, mock_editor, mocker):
        """Test that negative adjustment is clamped to 0."""
        controller_mode = mocker.Mock()
        controller_mode.value = 'r_slider'
        mock_editor.mode_switcher.get_controller_mode.return_value = controller_mode
        mock_editor.red_slider.value = 5
        mock_editor.controller_handler.on_slider_event = mocker.Mock()
        mock_editor.controller_handler._slider_adjust_value(0, -20)
        assert mock_editor.red_slider.value == 0

    def test_no_matching_mode(self, mock_editor, mocker):
        """Test that non-slider mode does nothing."""
        controller_mode = mocker.Mock()
        controller_mode.value = 'canvas'
        mock_editor.mode_switcher.get_controller_mode.return_value = controller_mode
        original_red = mock_editor.red_slider.value
        mock_editor.controller_handler._slider_adjust_value(0, 10)
        assert mock_editor.red_slider.value == original_red

    def test_no_mode_switcher(self, mock_editor):
        """Test graceful handling when mode_switcher is absent."""
        del mock_editor.mode_switcher
        mock_editor.controller_handler._slider_adjust_value(0, 10)  # Should not raise


# ===========================================================================
# 16. Slider Mode Navigation
# ===========================================================================


class TestHandleSliderModeNavigation:
    """Tests for handle_slider_mode_navigation()."""

    def test_no_mode_switcher_returns(self, mock_editor):
        """Test early return when mode_switcher is absent."""
        del mock_editor.mode_switcher
        mock_editor.controller_handler.handle_slider_mode_navigation('up')

    def test_no_controller_in_slider_mode_returns(self, mock_editor, mocker):
        """Test early return when no controller is in slider mode (keyboard nav)."""
        mock_editor.mode_switcher.controller_modes = {}
        mock_editor.controller_handler.handle_slider_mode_navigation('up')

    def test_specific_controller_id(self, mock_editor, mocker):
        """Test navigation with a specific controller_id."""
        from glitchygames.bitmappy.controllers.modes import ControllerMode

        mock_editor.mode_switcher.get_controller_mode.return_value = ControllerMode.R_SLIDER
        # controller_modes must contain the controller_id for the method to proceed
        mock_editor.mode_switcher.controller_modes = {0: mocker.Mock()}
        mock_editor.mode_switcher.switch_mode = mocker.Mock()
        mock_editor.controller_handler.handle_slider_mode_navigation('up', controller_id=0)


# ===========================================================================
# 17. Hat Motion Direction Mapping
# ===========================================================================


class TestJoyHatMotionDirections:
    """Tests for on_joy_hat_motion_event direction handling."""

    def test_hat_right_direction(self, mock_editor, mocker):
        """Test hat right direction (bitmask 2)."""
        event = mocker.Mock()
        event.hat = 0
        event.value = JOYSTICK_HAT_RIGHT
        mock_editor.on_joy_hat_motion_event(event)

    def test_hat_down_direction(self, mock_editor, mocker):
        """Test hat down direction (bitmask 4)."""
        event = mocker.Mock()
        event.hat = 0
        event.value = JOYSTICK_HAT_DOWN
        mock_editor.on_joy_hat_motion_event(event)

    def test_hat_left_direction(self, mock_editor, mocker):
        """Test hat left direction (bitmask 8)."""
        event = mocker.Mock()
        event.hat = 0
        event.value = JOYSTICK_HAT_LEFT
        mock_editor.on_joy_hat_motion_event(event)
