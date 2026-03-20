"""Coverage tests for glitchygames/sprites/core.py.

Targets uncovered lines: property accessors, event handler stubs,
BitmappySprite methods, Sprite coordinate operations, callbacks,
and the __str__ method.
"""

import sys
from pathlib import Path
from typing import cast

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.sprites import BitmappySprite, RootSprite, Singleton, Sprite
from tests.mocks.test_mock_factory import MockFactory

# Constants for magic values
SPRITE_X = 10
SPRITE_Y = 20
SPRITE_WIDTH = 30
SPRITE_HEIGHT = 40
SPRITE_NEW_X = 50
SPRITE_NEW_Y = 60
SPRITE_DT_VALUE = 0.016
SPRITE_DT_VALUE_SECOND = 0.032
EXPECTED_DT_SUM = 0.048


class TestRootSpriteInitialization:
    """Test RootSprite initialization edge cases."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_root_sprite_has_rect_and_image(self):
        """Test RootSprite initializes with rect and image attributes via Sprite subclass.

        RootSprite is abstract (via MouseEvents), so we test via Sprite which
        provides all the abstract method implementations.
        """
        groups = pygame.sprite.LayeredDirty()
        sprite = Sprite(x=0, y=0, width=10, height=10, groups=groups)

        # RootSprite.__init__ sets rect and image=None,
        # but Sprite.__init__ overrides them
        assert isinstance(sprite, RootSprite)
        assert sprite.rect is not None

    def test_root_sprite_without_groups_creates_default(self):
        """Test RootSprite creates a default group when none provided (via Sprite)."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        assert isinstance(sprite, RootSprite)
        assert len(sprite.groups()) >= 1


class TestSpriteCoordinateProperties:
    """Test Sprite x, y and rect coordinate properties."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_x_property_getter(self):
        """Test that x returns rect.x."""
        sprite = Sprite(x=SPRITE_X, y=SPRITE_Y, width=SPRITE_WIDTH, height=SPRITE_HEIGHT)
        assert sprite.rect is not None
        assert sprite.rect.x == SPRITE_X

    def test_y_property_getter(self):
        """Test that y returns rect.y."""
        sprite = Sprite(x=SPRITE_X, y=SPRITE_Y, width=SPRITE_WIDTH, height=SPRITE_HEIGHT)
        assert sprite.rect is not None
        assert sprite.rect.y == SPRITE_Y

    def test_width_setter_marks_dirty(self):
        """Test that setting width marks the sprite as dirty."""
        sprite = Sprite(x=0, y=0, width=SPRITE_WIDTH, height=SPRITE_HEIGHT)
        sprite.dirty = 0
        sprite.width = 100
        assert sprite.width == 100
        assert sprite.dirty == 1

    def test_height_setter_marks_dirty(self):
        """Test that setting height marks the sprite as dirty."""
        sprite = Sprite(x=0, y=0, width=SPRITE_WIDTH, height=SPRITE_HEIGHT)
        sprite.dirty = 0
        sprite.height = 100
        assert sprite.height == 100
        assert sprite.dirty == 1

    def test_width_setter_preserves_existing_dirty(self):
        """Test that setting width preserves dirty=2 if already dirty."""
        sprite = Sprite(x=0, y=0, width=SPRITE_WIDTH, height=SPRITE_HEIGHT)
        sprite.dirty = 2
        sprite.width = 100
        assert sprite.dirty == 2

    def test_height_setter_preserves_existing_dirty(self):
        """Test that setting height preserves dirty=2 if already dirty."""
        sprite = Sprite(x=0, y=0, width=SPRITE_WIDTH, height=SPRITE_HEIGHT)
        sprite.dirty = 2
        sprite.height = 100
        assert sprite.dirty == 2


class TestSpriteDtTick:
    """Test Sprite dt_tick method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_dt_tick_sets_dt(self):
        """Test dt_tick sets dt value."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        sprite.dt_tick(SPRITE_DT_VALUE)
        assert sprite.dt == SPRITE_DT_VALUE

    def test_dt_tick_accumulates_timer(self):
        """Test dt_tick accumulates dt_timer."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        sprite.dt_tick(SPRITE_DT_VALUE)
        sprite.dt_tick(SPRITE_DT_VALUE_SECOND)
        assert sprite.dt == SPRITE_DT_VALUE_SECOND
        assert abs(sprite.dt_timer - EXPECTED_DT_SUM) < 1e-9


class TestSpriteEventHandlerStubs:
    """Test that Sprite event handler stubs can be called without errors."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def sprite(self):
        """Create a sprite instance for testing.

        Returns:
            A Sprite instance.
        """
        return Sprite(x=0, y=0, width=10, height=10, name='test_sprite')

    @pytest.fixture
    def mock_event(self, mocker):
        """Create a mock pygame event.

        Returns:
            A mock event with pos, button, rel, and buttons attributes.
        """
        event = mocker.Mock()
        event.pos = (5, 5)
        event.button = 1
        event.rel = (1, 1)
        event.buttons = (0, 0, 0)
        return event

    def test_on_joy_axis_motion_event(self, sprite, mock_event):
        """Test on_joy_axis_motion_event does not raise."""
        sprite.on_joy_axis_motion_event(mock_event)

    def test_on_joy_button_down_event(self, sprite, mock_event):
        """Test on_joy_button_down_event does not raise."""
        sprite.on_joy_button_down_event(mock_event)

    def test_on_joy_button_up_event(self, sprite, mock_event):
        """Test on_joy_button_up_event does not raise."""
        sprite.on_joy_button_up_event(mock_event)

    def test_on_joy_hat_motion_event(self, sprite, mock_event):
        """Test on_joy_hat_motion_event does not raise."""
        sprite.on_joy_hat_motion_event(mock_event)

    def test_on_joy_ball_motion_event(self, sprite, mock_event):
        """Test on_joy_ball_motion_event does not raise."""
        sprite.on_joy_ball_motion_event(mock_event)

    def test_on_mouse_motion_event(self, sprite, mock_event):
        """Test on_mouse_motion_event does not raise."""
        sprite.on_mouse_motion_event(mock_event)

    def test_on_mouse_focus_event(self, sprite, mock_event):
        """Test on_mouse_focus_event does not raise."""
        sprite.on_mouse_focus_event(mock_event, entering_focus=None)

    def test_on_mouse_unfocus_event(self, sprite, mock_event):
        """Test on_mouse_unfocus_event does not raise."""
        sprite.on_mouse_unfocus_event(mock_event)

    def test_on_mouse_enter_event(self, sprite, mock_event):
        """Test on_mouse_enter_event does not raise."""
        sprite.on_mouse_enter_event(mock_event)

    def test_on_mouse_exit_event(self, sprite, mock_event):
        """Test on_mouse_exit_event does not raise."""
        sprite.on_mouse_exit_event(mock_event)

    def test_on_mouse_drag_down_event(self, sprite, mock_event):
        """Test on_mouse_drag_down_event does not raise."""
        sprite.on_mouse_drag_down_event(mock_event, trigger=None)

    def test_on_left_mouse_drag_down_event(self, sprite, mock_event):
        """Test on_left_mouse_drag_down_event does not raise."""
        sprite.on_left_mouse_drag_down_event(mock_event, trigger=None)

    def test_on_left_mouse_drag_up_event(self, sprite, mock_event):
        """Test on_left_mouse_drag_up_event does not raise."""
        sprite.on_left_mouse_drag_up_event(mock_event, trigger=None)

    def test_on_middle_mouse_drag_down_event(self, sprite, mock_event):
        """Test on_middle_mouse_drag_down_event does not raise."""
        sprite.on_middle_mouse_drag_down_event(mock_event, trigger=None)

    def test_on_middle_mouse_drag_up_event(self, sprite, mock_event):
        """Test on_middle_mouse_drag_up_event does not raise."""
        sprite.on_middle_mouse_drag_up_event(mock_event, trigger=None)

    def test_on_right_mouse_drag_down_event(self, sprite, mock_event):
        """Test on_right_mouse_drag_down_event does not raise."""
        sprite.on_right_mouse_drag_down_event(mock_event, trigger=None)

    def test_on_right_mouse_drag_up_event(self, sprite, mock_event):
        """Test on_right_mouse_drag_up_event does not raise."""
        sprite.on_right_mouse_drag_up_event(mock_event, trigger=None)

    def test_on_mouse_drag_up_event(self, sprite, mock_event):
        """Test on_mouse_drag_up_event does not raise."""
        sprite.on_mouse_drag_up_event(mock_event)

    def test_on_mouse_button_up_event(self, sprite, mock_event):
        """Test on_mouse_button_up_event does not raise."""
        sprite.on_mouse_button_up_event(mock_event)

    def test_on_middle_mouse_button_up_event(self, sprite, mock_event):
        """Test on_middle_mouse_button_up_event does not raise."""
        sprite.on_middle_mouse_button_up_event(mock_event)

    def test_on_mouse_button_down_event(self, sprite, mock_event):
        """Test on_mouse_button_down_event does not raise."""
        sprite.on_mouse_button_down_event(mock_event)

    def test_on_middle_mouse_button_down_event(self, sprite, mock_event):
        """Test on_middle_mouse_button_down_event does not raise."""
        sprite.on_middle_mouse_button_down_event(mock_event)

    def test_on_mouse_scroll_down_event(self, sprite, mock_event):
        """Test on_mouse_scroll_down_event does not raise."""
        sprite.on_mouse_scroll_down_event(mock_event)

    def test_on_mouse_scroll_up_event(self, sprite, mock_event):
        """Test on_mouse_scroll_up_event does not raise."""
        sprite.on_mouse_scroll_up_event(mock_event)

    def test_on_mouse_chord_up_event(self, sprite, mock_event):
        """Test on_mouse_chord_up_event does not raise."""
        sprite.on_mouse_chord_up_event(mock_event)

    def test_on_mouse_chord_down_event(self, sprite, mock_event):
        """Test on_mouse_chord_down_event does not raise."""
        sprite.on_mouse_chord_down_event(mock_event)

    def test_on_key_down_event(self, sprite, mock_event):
        """Test on_key_down_event does not raise."""
        sprite.on_key_down_event(mock_event)

    def test_on_key_up_event(self, sprite, mock_event):
        """Test on_key_up_event does not raise."""
        sprite.on_key_up_event(mock_event)

    def test_on_key_chord_down_event(self, sprite, mock_event):
        """Test on_key_chord_down_event does not raise."""
        sprite.on_key_chord_down_event(mock_event, keys=[pygame.K_a])

    def test_on_key_chord_up_event(self, sprite, mock_event):
        """Test on_key_chord_up_event does not raise."""
        sprite.on_key_chord_up_event(mock_event, keys=[pygame.K_a])

    def test_on_active_event(self, sprite, mock_event):
        """Test on_active_event does not raise."""
        sprite.on_active_event(mock_event)

    def test_on_video_resize_event(self, sprite, mock_event):
        """Test on_video_resize_event does not raise."""
        sprite.on_video_resize_event(mock_event)

    def test_on_video_expose_event(self, sprite, mock_event):
        """Test on_video_expose_event does not raise."""
        sprite.on_video_expose_event(mock_event)

    def test_on_sys_wm_event(self, sprite, mock_event):
        """Test on_sys_wm_event does not raise."""
        sprite.on_sys_wm_event(mock_event)

    def test_on_user_event(self, sprite, mock_event):
        """Test on_user_event does not raise."""
        sprite.on_user_event(mock_event)

    def test_on_left_mouse_drag_event(self, sprite, mock_event):
        """Test on_left_mouse_drag_event does not raise."""
        sprite.on_left_mouse_drag_event(mock_event, trigger=None)

    def test_on_middle_mouse_drag_event(self, sprite, mock_event):
        """Test on_middle_mouse_drag_event does not raise."""
        sprite.on_middle_mouse_drag_event(mock_event, trigger=None)

    def test_on_right_mouse_drag_event(self, sprite, mock_event):
        """Test on_right_mouse_drag_event does not raise."""
        sprite.on_right_mouse_drag_event(mock_event, trigger=None)

    def test_on_left_mouse_drop_event(self, sprite, mock_event):
        """Test on_left_mouse_drop_event does not raise."""
        sprite.on_left_mouse_drop_event(mock_event, trigger=None)

    def test_on_middle_mouse_drop_event(self, sprite, mock_event):
        """Test on_middle_mouse_drop_event does not raise."""
        sprite.on_middle_mouse_drop_event(mock_event, trigger=None)

    def test_on_right_mouse_drop_event(self, sprite, mock_event):
        """Test on_right_mouse_drop_event does not raise."""
        sprite.on_right_mouse_drop_event(mock_event, trigger=None)

    def test_on_mouse_drag_event(self, sprite, mock_event):
        """Test on_mouse_drag_event does not raise."""
        sprite.on_mouse_drag_event(mock_event, trigger=None)

    def test_on_mouse_drop_event(self, sprite, mock_event):
        """Test on_mouse_drop_event does not raise."""
        sprite.on_mouse_drop_event(mock_event, trigger=None)

    def test_on_mouse_wheel_event(self, sprite, mock_event):
        """Test on_mouse_wheel_event does not raise."""
        sprite.on_mouse_wheel_event(mock_event)


class TestSpriteCallbackHandlers:
    """Test Sprite event handlers with callbacks registered."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_on_left_mouse_button_up_with_callback(self, mocker):
        """Test on_left_mouse_button_up_event fires callback."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        callback = mocker.Mock()
        sprite.callbacks['on_left_mouse_button_up_event'] = callback
        event = mocker.Mock()
        sprite.on_left_mouse_button_up_event(event)
        callback.assert_called_once_with(event=event, trigger=sprite)

    def test_on_left_mouse_button_up_without_callback(self, mocker):
        """Test on_left_mouse_button_up_event without callback logs."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        event = mocker.Mock()
        # Should not raise when no callbacks set
        sprite.on_left_mouse_button_up_event(event)

    def test_on_right_mouse_button_up_with_callback(self, mocker):
        """Test on_right_mouse_button_up_event fires callback."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        callback = mocker.Mock()
        sprite.callbacks['on_right_mouse_button_up_event'] = callback
        event = mocker.Mock()
        sprite.on_right_mouse_button_up_event(event)
        callback.assert_called_once_with(event=event, trigger=sprite)

    def test_on_right_mouse_button_up_without_callback(self, mocker):
        """Test on_right_mouse_button_up_event without callback logs."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        event = mocker.Mock()
        sprite.on_right_mouse_button_up_event(event)

    def test_on_left_mouse_button_down_with_callback(self, mocker):
        """Test on_left_mouse_button_down_event fires callback."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        callback = mocker.Mock()
        sprite.callbacks['on_left_mouse_button_down_event'] = callback
        event = mocker.Mock()
        sprite.on_left_mouse_button_down_event(event)
        callback.assert_called_once_with(event=event, trigger=sprite)

    def test_on_left_mouse_button_down_without_callback(self, mocker):
        """Test on_left_mouse_button_down_event without callback logs."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        event = mocker.Mock()
        sprite.on_left_mouse_button_down_event(event)

    def test_on_right_mouse_button_down_with_callback(self, mocker):
        """Test on_right_mouse_button_down_event fires callback."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        callback = mocker.Mock()
        sprite.callbacks['on_right_mouse_button_down_event'] = callback
        event = mocker.Mock()
        sprite.on_right_mouse_button_down_event(event)
        callback.assert_called_once_with(event=event, trigger=sprite)

    def test_on_right_mouse_button_down_without_callback(self, mocker):
        """Test on_right_mouse_button_down_event without callback logs."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        event = mocker.Mock()
        sprite.on_right_mouse_button_down_event(event)

    def test_on_left_mouse_button_up_with_empty_callbacks(self, mocker):
        """Test on_left_mouse_button_up_event with empty callbacks dict."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        sprite.callbacks = {}  # Empty dict is falsy
        event = mocker.Mock()
        # Should not raise with empty callbacks
        sprite.on_left_mouse_button_up_event(event)


class TestSpriteQuitEvent:
    """Test Sprite on_quit_event calls terminate."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_on_quit_event_calls_terminate(self, mocker):
        """Test on_quit_event calls terminate method."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        sprite.terminate = mocker.Mock()  # type: ignore[unresolved-attribute]
        event = mocker.Mock()
        sprite.on_quit_event(event)
        sprite.terminate.assert_called_once()  # type: ignore[unresolved-attribute]


class TestSpriteStr:
    """Test Sprite __str__ method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_str_representation(self):
        """Test __str__ returns a descriptive string."""
        sprite = Sprite(x=0, y=0, width=10, height=10, name='test_sprite')
        result = str(sprite)
        assert 'test_sprite' in result
        assert 'Sprite' in result


class TestSpriteBreakWhen:
    """Test Sprite.break_when class method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def teardown_method(self):
        """Reset SPRITE_BREAKPOINTS after each test."""
        Sprite.SPRITE_BREAKPOINTS = None

    def test_break_when_none_initializes_list(self):
        """Test break_when with None initializes SPRITE_BREAKPOINTS list."""
        Sprite.SPRITE_BREAKPOINTS = None
        Sprite.break_when(sprite_type=None)
        assert Sprite.SPRITE_BREAKPOINTS == []

    def test_break_when_specific_type_appends(self):
        """Test break_when with specific type appends to the list."""
        Sprite.SPRITE_BREAKPOINTS = None
        Sprite.break_when(sprite_type=Sprite)
        assert Sprite.SPRITE_BREAKPOINTS is not None
        assert len(Sprite.SPRITE_BREAKPOINTS) == 1


class TestBitmappySpriteBasics:
    """Test BitmappySprite initialization and methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_bitmappy_sprite_init_with_dimensions(self):
        """Test BitmappySprite initialization with width and height."""
        sprite = BitmappySprite(x=10, y=20, width=32, height=32)
        assert sprite.rect is not None
        assert sprite.rect.x == 10
        assert sprite.rect.y == 20
        assert sprite.width == 32
        assert sprite.height == 32
        assert sprite.pixels == []
        assert sprite.pixels_across == 32
        assert sprite.pixels_tall == 32

    def test_bitmappy_sprite_focusable_attribute(self):
        """Test BitmappySprite stores focusable attribute."""
        sprite = BitmappySprite(x=0, y=0, width=10, height=10, focusable=True)
        assert sprite.focusable is True

    def test_bitmappy_sprite_default_filename(self):
        """Test BitmappySprite default filename is empty string."""
        sprite = BitmappySprite(x=0, y=0, width=10, height=10)
        assert not sprite.filename

    def test_bitmappy_sprite_raise_unsupported_format_error(self):
        """Test _raise_unsupported_format_error raises ValueError."""
        with pytest.raises(ValueError, match='Unsupported format'):
            BitmappySprite._raise_unsupported_format_error('json')

    def test_bitmappy_sprite_raise_animated_sprite_error(self):
        """Test _raise_animated_sprite_error raises ValueError."""
        with pytest.raises(ValueError, match='animated sprite data'):
            BitmappySprite._raise_animated_sprite_error('test.toml')

    def test_bitmappy_sprite_raise_too_many_colors_error(self):
        """Test _raise_too_many_colors_error raises ValueError."""
        sprite = BitmappySprite(x=0, y=0, width=10, height=10)
        with pytest.raises(ValueError, match='Too many colors'):
            sprite._raise_too_many_colors_error(9999)


class TestBitmappySpriteDeflate:
    """Test BitmappySprite deflate and related methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_deflate_empty_surface(self):
        """Test deflate returns minimal config for empty surface."""
        sprite = BitmappySprite(x=0, y=0, width=10, height=10)
        sprite.pixels_across = 0
        sprite.pixels_tall = 0
        config = sprite.deflate(file_format='toml')
        assert config['sprite']['pixels_across'] == 0
        assert config['sprite']['pixels_tall'] == 0

    def test_deflate_empty_surface_unsupported_format(self):
        """Test deflate raises ValueError for unsupported format on empty surface."""
        sprite = BitmappySprite(x=0, y=0, width=10, height=10)
        sprite.pixels_across = 0
        sprite.pixels_tall = 0
        with pytest.raises(ValueError, match='Unsupported format'):
            sprite.deflate(file_format='json')

    def test_create_color_map_empty_pixels(self):
        """Test _create_color_map returns empty dict for no pixels."""
        sprite = BitmappySprite(x=0, y=0, width=10, height=10)
        sprite.pixels = []
        result = sprite._create_color_map()
        assert result == {}

    def test_create_color_map_with_pixels(self):
        """Test _create_color_map creates mapping for pixel colors."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2)
        sprite.pixels = [(255, 0, 0), (0, 255, 0), (255, 0, 0), (0, 255, 0)]
        result = sprite._create_color_map()
        # Should have 2 unique colors mapped to characters
        assert len(result) == 2
        # All values should be the original colors
        assert set(result.values()) == {(255, 0, 0), (0, 255, 0)}

    def test_process_pixel_rows(self):
        """Test _process_pixel_rows converts pixels to character rows."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2)
        sprite.pixels = [(255, 0, 0), (0, 255, 0), (255, 0, 0), (0, 255, 0)]
        sprite.pixels_across = 2
        sprite.pixels_tall = 2
        color_map = sprite._create_color_map()
        # Invert the map for _process_pixel_rows (it expects char -> color)
        rows = sprite._process_pixel_rows(color_map, pixels_across=2, pixels_tall=2)
        assert len(rows) == 2
        assert len(rows[0]) == 2

    def test_deflate_with_pixel_data(self):
        """Test deflate with actual pixel data produces TOML config."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2)
        sprite.pixels_across = 2
        sprite.pixels_tall = 2
        sprite.pixels = [(255, 0, 0), (0, 255, 0), (255, 0, 0), (0, 255, 0)]
        sprite.name = 'test'
        config = sprite.deflate(file_format='toml')
        assert 'sprite' in config
        assert 'colors' in config
        assert config['sprite']['name'] == 'test'

    def test_deflate_pads_short_pixels_list(self):
        """Test deflate pads pixels list if shorter than expected."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2)
        sprite.pixels_across = 2
        sprite.pixels_tall = 2
        sprite.pixels = [(255, 0, 0)]  # Only 1 pixel, expected 4
        sprite.name = 'test'
        config = sprite.deflate(file_format='toml')
        assert 'sprite' in config

    def test_deflate_truncates_long_pixels_list(self):
        """Test deflate truncates pixels list if longer than expected."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2)
        sprite.pixels_across = 2
        sprite.pixels_tall = 2
        pixel_data = cast('list[tuple[int, ...]]', [(255, 0, 0)] * 10)  # 10 pixels, expected 4
        sprite.pixels = pixel_data
        sprite.name = 'test'
        config = sprite.deflate(file_format='toml')
        assert 'sprite' in config

    def test_create_toml_config_without_pixel_rows(self):
        """Test _create_toml_config when no pixel_rows provided and no pixels."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2)
        sprite.pixels = []
        sprite.name = 'test'
        config = sprite._create_toml_config()
        assert config['sprite']['name'] == 'test'
        assert not config['sprite']['pixels']


class TestBitmappySpriteInflate:
    """Test BitmappySprite inflate class method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_inflate_creates_surface(self):
        """Test inflate creates a properly sized surface."""
        color_map = {'#': (0, 0, 0), '.': (255, 255, 255)}
        pixels = ['#.', '.#']
        image, rect = BitmappySprite.inflate(width=2, height=2, pixels=pixels, color_map=color_map)
        assert image.get_size() == (2, 2)
        assert rect.width == 2
        assert rect.height == 2


class TestBitmappySpriteStr:
    """Test BitmappySprite __str__ method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_str_no_filename(self):
        """Test __str__ when no filename is loaded."""
        sprite = BitmappySprite(x=0, y=0, width=10, height=10, name='test')
        result = str(sprite)
        assert 'no file loaded' in result

    def test_str_with_missing_file(self):
        """Test __str__ when filename doesn't exist gracefully returns fallback."""
        sprite = BitmappySprite(x=0, y=0, width=10, height=10, name='test')
        sprite.filename = '/nonexistent/file.toml'
        result = str(sprite)
        assert 'error rendering' in result


class TestBitmappySpriteEventHandlers:
    """Test BitmappySprite event handler overrides."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def bitmappy_sprite(self):
        """Create a BitmappySprite for testing.

        Returns:
            A BitmappySprite instance.
        """
        return BitmappySprite(x=0, y=0, width=10, height=10, name='test')

    def test_bitmappy_on_left_mouse_drag_event(self, bitmappy_sprite, mocker):
        """Test BitmappySprite on_left_mouse_drag_event does not raise."""
        event = mocker.Mock()
        bitmappy_sprite.on_left_mouse_drag_event(event, trigger=None)

    def test_bitmappy_on_middle_mouse_drag_event(self, bitmappy_sprite, mocker):
        """Test BitmappySprite on_middle_mouse_drag_event does not raise."""
        event = mocker.Mock()
        bitmappy_sprite.on_middle_mouse_drag_event(event, trigger=None)

    def test_bitmappy_on_right_mouse_drag_event(self, bitmappy_sprite, mocker):
        """Test BitmappySprite on_right_mouse_drag_event does not raise."""
        event = mocker.Mock()
        bitmappy_sprite.on_right_mouse_drag_event(event, trigger=None)

    def test_bitmappy_on_left_mouse_drop_event(self, bitmappy_sprite, mocker):
        """Test BitmappySprite on_left_mouse_drop_event does not raise."""
        event = mocker.Mock()
        bitmappy_sprite.on_left_mouse_drop_event(event, trigger=None)

    def test_bitmappy_on_middle_mouse_drop_event(self, bitmappy_sprite, mocker):
        """Test BitmappySprite on_middle_mouse_drop_event does not raise."""
        event = mocker.Mock()
        bitmappy_sprite.on_middle_mouse_drop_event(event, trigger=None)

    def test_bitmappy_on_right_mouse_drop_event(self, bitmappy_sprite, mocker):
        """Test BitmappySprite on_right_mouse_drop_event does not raise."""
        event = mocker.Mock()
        bitmappy_sprite.on_right_mouse_drop_event(event, trigger=None)

    def test_bitmappy_on_mouse_drag_event(self, bitmappy_sprite, mocker):
        """Test BitmappySprite on_mouse_drag_event does not raise."""
        event = mocker.Mock()
        bitmappy_sprite.on_mouse_drag_event(event, trigger=None)

    def test_bitmappy_on_mouse_drop_event(self, bitmappy_sprite, mocker):
        """Test BitmappySprite on_mouse_drop_event does not raise."""
        event = mocker.Mock()
        bitmappy_sprite.on_mouse_drop_event(event, trigger=None)

    def test_bitmappy_on_mouse_wheel_event(self, bitmappy_sprite, mocker):
        """Test BitmappySprite on_mouse_wheel_event does not raise."""
        event = mocker.Mock()
        bitmappy_sprite.on_mouse_wheel_event(event)

    def test_bitmappy_on_mouse_chord_down_event(self, bitmappy_sprite, mocker):
        """Test BitmappySprite on_mouse_chord_down_event does not raise."""
        event = mocker.Mock()
        bitmappy_sprite.on_mouse_chord_down_event(event, keys=[])

    def test_bitmappy_on_mouse_chord_up_event(self, bitmappy_sprite, mocker):
        """Test BitmappySprite on_mouse_chord_up_event does not raise."""
        event = mocker.Mock()
        bitmappy_sprite.on_mouse_chord_up_event(event, keys=[])


class TestSingletonPattern:
    """Test Singleton class."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_singleton_returns_same_instance(self):
        """Test that Singleton returns the same instance."""
        instance1 = Singleton()
        instance2 = Singleton()
        assert instance1 is instance2

    def test_singleton_stores_args(self):
        """Test that Singleton stores args and kwargs."""
        instance = Singleton('arg1', key='value')
        assert instance.kwargs == {'key': 'value'}  # type: ignore[unresolved-attribute]


class TestBitmappySpriteInflateFromFile:
    """Test BitmappySprite inflate_from_file and load_static_only."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_inflate_from_file_unsupported_format(self, mocker):
        """Test inflate_from_file raises on unsupported format."""
        sprite = BitmappySprite(x=0, y=0, width=10, height=10)
        # Mock _detect_file_format to return unsupported format
        mocker.patch(
            'glitchygames.sprites.core.SpriteFactory.detect_file_format',
            return_value='json',
        )
        with pytest.raises(ValueError, match='Unsupported format'):
            sprite.inflate_from_file('test.json')

    def test_load_static_only_unsupported_format(self, mocker):
        """Test _load_static_only raises on unsupported format."""
        sprite = BitmappySprite(x=0, y=0, width=10, height=10)
        mocker.patch(
            'glitchygames.sprites.core.SpriteFactory.detect_file_format',
            return_value='json',
        )
        with pytest.raises(ValueError, match='Unsupported file format'):
            sprite._load_static_only('test.json')


class TestBitmappySpriteGeneratePixelRows:
    """Test BitmappySprite _generate_pixel_rows method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_generate_pixel_rows_without_color_map(self):
        """Test _generate_pixel_rows generates both rows and color_map."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2)
        sprite.pixels_across = 2
        sprite.pixels_tall = 2
        sprite.pixels = [(255, 0, 0), (0, 255, 0), (255, 0, 0), (0, 255, 0)]
        rows, color_map = sprite._generate_pixel_rows()
        assert len(rows) == 2
        assert len(color_map) == 2

    def test_generate_pixel_rows_with_short_pixels(self):
        """Test _generate_pixel_rows handles pixels shorter than expected."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2)
        sprite.pixels_across = 2
        sprite.pixels_tall = 2
        sprite.pixels = [(255, 0, 0)]  # Only 1 pixel, expected 4
        rows, _color_map = sprite._generate_pixel_rows()
        assert len(rows) == 2
        # Missing pixels should use '.' as default
        assert '.' in rows[0] or '.' in rows[1]
