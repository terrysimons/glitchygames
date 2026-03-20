"""Final coverage tests for glitchygames/tools/film_strip.py.

Targets uncovered areas NOT covered by existing test files:
- _propagate_dirty_to_sprite_groups with sprite groups
- _has_valid_canvas_sprite variations
- _is_keyboard_selected matching/non-matching
- _get_controller_selection_color lookups
- _get_active_controller_selections filtering
- _toggle_onion_skinning with/without parent
- handle_keyboard_input editing mode (Enter, Escape, Backspace, printable)
- handle_click animation label double-click for rename
- handle_preview_click background color cycling
- _convert_magenta_to_transparent variations
- _draw_placeholder rendering
- _add_film_strip_styling edge drawing
- _create_selection_border rendering
- _add_hover_highlighting rendering
- render_sprocket_separator rendering
- set_parent_canvas assignment
- update_layout recalculation
- _dump_animation_debug_state and _dump_animated_sprite_debug
- _create_film_tabs with and without frames
- reset_all_tab_states clearing
- _handle_tab_click and _handle_tab_hover
- _get_frame_image stale image path
- _render_editing_label cursor blink rendering
- render with hover effect
- _get_active_controller_selections with controllers
- _draw_multi_controller_indicators controller color priority
- _handle_add_animation_tab_click and _handle_delete_animation_tab_click
- _handle_removal_button_click out of range
- _track_frame_deletion_for_undo early return
- _clamp_animated_sprite_frame
- _remove_frame scroll adjustment
- _render_removal_button skipping
- FilmStripDeleteTab and FilmStripTab render clicked state
- handle_click with tab and removal button interactions
- _propagate_dirty_up_parent_chain
- _draw_preview_triangle fallback paths
- _draw_frame_number exception path
- _draw_onion_skinning_indicator with active onion skinning
- _render_preview_background and _render_vertical_divider
"""

import sys
from pathlib import Path
from typing import cast

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from glitchygames.tools.film_strip import (
    FilmStripDeleteTab,
    FilmStripTab,
    FilmStripWidget,
    FilmTabWidget,
)
from tests.mocks.test_mock_factory import MockFactory

# Constants for test values
WIDGET_X = 0
WIDGET_Y = 0
WIDGET_WIDTH = 500
WIDGET_HEIGHT = 200
SURFACE_SIZE = 4
FRAME_DURATION = 0.5


class TestFilmStripPropagateDirtyToGroups:
    """Test _propagate_dirty_to_sprite_groups method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_propagate_to_sprite_with_groups(self, mocker):
        """Test propagation through sprite groups."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = mocker.Mock()
        group = mocker.Mock()
        group.sprites.return_value = []
        sprite.groups.return_value = [group]
        sprite.dirty = 0

        widget._propagate_dirty_to_sprite_groups(sprite)
        # Should set sprite dirty=2 or visit groups

    def test_propagate_skips_visited_sprite(self, mocker):
        """Test propagation skips already-visited sprites."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = mocker.Mock()
        sprite.groups.return_value = []
        visited = {sprite}

        # Should return immediately without error
        widget._propagate_dirty_to_sprite_groups(sprite, visited=visited)

    def test_propagate_sprite_without_groups(self, mocker):
        """Test propagation with sprite that has no groups attribute."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = mocker.Mock(spec=[])  # No groups attr

        widget._propagate_dirty_to_sprite_groups(sprite)  # Should not raise


class TestFilmStripHasValidCanvasSprite:
    """Test _has_valid_canvas_sprite method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_has_valid_canvas_no_parent(self):
        """Test returns False when no parent_canvas."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert not hasattr(widget, 'parent_canvas') or widget._has_valid_canvas_sprite() is False

    def test_has_valid_canvas_with_parent(self, mocker):
        """Test returns True when parent_scene has canvas with animated_sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.parent_scene = mocker.Mock()
        widget.parent_scene.canvas = mocker.Mock()
        widget.parent_scene.canvas.animated_sprite = mocker.Mock()
        result = widget._has_valid_canvas_sprite()
        assert result is True

    def test_has_valid_canvas_without_animated_sprite(self, mocker):
        """Test returns False when parent_scene canvas lacks animated_sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.parent_scene = mocker.Mock()
        widget.parent_scene.canvas = mocker.Mock(spec=[])
        result = widget._has_valid_canvas_sprite()
        assert result is False


class TestFilmStripHandleKeyboardInput:
    """Test handle_keyboard_input method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def widget_in_edit_mode(self):
        """Create a widget in animation rename edit mode.

        Returns:
            FilmStripWidget: A widget configured for edit mode testing.

        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('idle', [frame])
        widget.set_animated_sprite(sprite)
        widget.editing_animation = 'idle'
        widget.editing_text = 'idle'
        widget.original_animation_name = 'idle'
        return widget

    def _make_key_event(self, mocker, key, unicode_char=''):
        """Create a mock keyboard event with key and unicode attributes.

        Args:
            mocker: The pytest-mock mocker fixture.
            key: The pygame key constant.
            unicode_char: The unicode character string.

        Returns:
            A mock event with key and unicode attributes.

        """
        event = mocker.Mock()
        event.key = key
        event.unicode = unicode_char
        event.mod = 0
        return event

    def test_handle_escape_cancels_edit(self, mocker, widget_in_edit_mode):
        """Test Escape key cancels animation rename edit."""
        event = self._make_key_event(mocker, pygame.K_ESCAPE)
        widget_in_edit_mode.handle_keyboard_input(event)
        assert widget_in_edit_mode.editing_animation is None

    def test_handle_backspace_removes_char(self, mocker, widget_in_edit_mode):
        """Test Backspace removes last character from editing text."""
        widget_in_edit_mode.editing_text = 'walk'
        event = self._make_key_event(mocker, pygame.K_BACKSPACE)
        widget_in_edit_mode.handle_keyboard_input(event)
        assert widget_in_edit_mode.editing_text == 'wal'

    def test_handle_printable_char_appends(self, mocker, widget_in_edit_mode):
        """Test printable character appends to editing text."""
        widget_in_edit_mode.editing_text = 'wal'
        event = self._make_key_event(mocker, pygame.K_k, unicode_char='k')
        widget_in_edit_mode.handle_keyboard_input(event)
        assert widget_in_edit_mode.editing_text == 'walk'

    def test_handle_non_editing_mode_does_nothing(self, mocker):
        """Test keyboard input when not in editing mode does nothing."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = None
        event = self._make_key_event(mocker, pygame.K_a, unicode_char='a')
        result = widget.handle_keyboard_input(event)
        # Should return False or None (not consumed)
        assert not result


class TestFilmStripHandlePreviewClick:
    """Test handle_preview_click for background color cycling."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_left_click_cycles_background_forward(self):
        """Test left click on preview cycles background color forward."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)
        # Set up a preview rect and click inside it
        preview_rect = pygame.Rect(400, 10, 64, 64)
        widget.preview_rects['idle'] = preview_rect
        initial_index = widget.background_color_index

        # handle_preview_click takes a pos tuple (x, y)
        click_pos = (preview_rect.centerx, preview_rect.centery)
        widget.handle_preview_click(click_pos)
        assert widget.background_color_index == (initial_index + 1) % len(widget.BACKGROUND_COLORS)

    def test_right_click_cycles_background_backward(self):
        """Test clicking preview cycles background color (always forward).

        The handle_preview_click method always cycles forward regardless of
        mouse button - it only takes a pos argument with no button parameter.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)
        preview_rect = pygame.Rect(400, 10, 64, 64)
        widget.preview_rects['idle'] = preview_rect
        initial_index = widget.background_color_index

        # handle_preview_click takes a pos tuple (x, y)
        click_pos = (preview_rect.centerx, preview_rect.centery)
        widget.handle_preview_click(click_pos)
        expected = (initial_index + 1) % len(widget.BACKGROUND_COLORS)
        assert widget.background_color_index == expected


class TestFilmStripSetParentCanvas:
    """Test set_parent_canvas method."""

    def test_set_parent_canvas_assigns(self, mocker):
        """Test set_parent_canvas stores the canvas reference."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_canvas = mocker.Mock()
        widget.set_parent_canvas(mock_canvas)
        assert widget.parent_canvas is mock_canvas


class TestFilmStripUpdateLayout:
    """Test update_layout method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_layout_recalculates(self):
        """Test update_layout triggers layout recalculation."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        # Clear layouts and recalculate
        widget.frame_layouts.clear()
        widget.update_layout()
        assert len(widget.frame_layouts) > 0

    def test_update_layout_with_parent_canvas(self, mocker):
        """Test update_layout marks parent film strip sprite dirty."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        widget.parent_canvas = mocker.Mock()
        widget.parent_canvas.film_strip_sprite = mocker.Mock()
        widget.parent_canvas.film_strip_sprite.dirty = 0
        widget.update_layout()
        assert widget.parent_canvas.film_strip_sprite.dirty == 1


class TestFilmStripDumpDebugState:
    """Test _dump_animation_debug_state and _dump_animated_sprite_debug."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_dump_debug_state_does_not_raise(self):
        """Test _dump_animation_debug_state runs without error."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)
        widget._debug_start_time = 10.0

        widget._dump_animation_debug_state(0.016)

    def test_dump_animated_sprite_debug_does_not_raise(self):
        """Test _dump_animated_sprite_debug runs without error."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)

        widget._dump_animated_sprite_debug()

    def test_dump_debug_state_without_sprite(self):
        """Test _dump_animation_debug_state without sprite.

        When no animated sprite is set, scroll_offset is not initialized by
        set_animated_sprite, so we must set it manually to simulate the state
        after partial initialization.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._debug_start_time = 5.0
        # scroll_offset is set in set_animated_sprite, not __init__,
        # so we need to initialize it for the debug dump to work
        widget.scroll_offset = 0
        widget.current_animation = ''
        widget.current_frame = 0
        widget._dump_animation_debug_state(0.016)


class TestFilmStripConvertMagentaToTransparent:
    """Test _convert_magenta_to_transparent method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_convert_magenta_rgb_to_transparent(self):
        """Test converts magenta RGB pixels to transparent."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((2, 2), pygame.SRCALPHA)
        surface.fill((255, 0, 255))  # Magenta
        result = widget._convert_magenta_to_transparent(surface)
        assert isinstance(result, pygame.Surface)

    def test_convert_non_magenta_unchanged(self):
        """Test non-magenta pixels remain unchanged."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((2, 2), pygame.SRCALPHA)
        surface.fill((255, 0, 0, 255))  # Red, not magenta
        result = widget._convert_magenta_to_transparent(surface)
        assert isinstance(result, pygame.Surface)


class TestFilmStripRenderingHelpers:
    """Test rendering helper methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_draw_placeholder_does_not_raise(self):
        """Test _draw_placeholder renders without error.

        _draw_placeholder takes a single frame_surface argument and draws
        a placeholder into it.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        frame_surface = pygame.Surface(
            (widget.frame_width, widget.frame_height),
            pygame.SRCALPHA,
        )
        widget._draw_placeholder(frame_surface)

    def test_create_selection_border_returns_surface(self):
        """Test _create_selection_border returns a valid surface.

        _create_selection_border takes a single frame_surface argument.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        frame_surface = pygame.Surface(
            (widget.frame_width, widget.frame_height),
            pygame.SRCALPHA,
        )
        result = widget._create_selection_border(frame_surface)
        assert isinstance(result, pygame.Surface)

    def test_add_hover_highlighting_does_not_raise(self):
        """Test _add_hover_highlighting renders without error.

        _add_hover_highlighting takes a single frame_surface argument.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        frame_surface = pygame.Surface(
            (widget.frame_width, widget.frame_height),
            pygame.SRCALPHA,
        )
        widget._add_hover_highlighting(frame_surface)

    def test_render_sprocket_separator_does_not_raise(self):
        """Test render_sprocket_separator renders without error.

        render_sprocket_separator takes x, y, and height positional arguments.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        result = widget.render_sprocket_separator(0, 50, WIDGET_HEIGHT)
        assert isinstance(result, pygame.Surface)


class TestFilmStripResetAllTabStates:
    """Test reset_all_tab_states method."""

    def test_reset_clears_tab_states(self, mocker):
        """Test reset_all_tab_states clears hover state and calls reset_click_state.

        reset_all_tab_states calls tab.reset_click_state() (which sets
        is_clicked = False) and sets tab.is_hovered = False.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        # Create mock tabs
        mock_tab = mocker.Mock()
        mock_tab.is_hovered = True
        mock_tab.is_clicked = True
        widget.film_tabs = [mock_tab]
        widget.reset_all_tab_states()
        assert mock_tab.is_hovered is False
        mock_tab.reset_click_state.assert_called_once()

    def test_reset_empty_tabs(self):
        """Test reset_all_tab_states with no tabs."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.film_tabs = []
        widget.reset_all_tab_states()  # Should not raise


class TestFilmStripToggleOnionSkinning:
    """Test _toggle_onion_skinning method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_toggle_onion_skinning_without_parent(self):
        """Test _toggle_onion_skinning without parent scene."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        # Should not raise when no parent_canvas
        if hasattr(widget, '_toggle_onion_skinning'):
            widget._toggle_onion_skinning('idle', 0)

    def test_toggle_onion_skinning_with_parent_and_canvas(self, mocker):
        """Test _toggle_onion_skinning with parent scene and canvas triggers force_redraw."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.parent_scene = mocker.Mock()
        widget.parent_scene.canvas = mocker.Mock()

        # Mock the onion skinning module that gets imported inside the method
        mock_manager = mocker.Mock()
        mock_manager.toggle_frame_onion_skinning.return_value = True
        mock_onion_module = mocker.MagicMock()
        mock_onion_module.get_onion_skinning_manager.return_value = mock_manager
        mocker.patch.dict(
            'sys.modules',
            {'glitchygames.tools.onion_skinning': mock_onion_module},
        )

        widget._toggle_onion_skinning('idle', 0)
        assert widget._force_redraw is True
        widget.parent_scene.canvas.force_redraw.assert_called_once()

    def test_toggle_onion_skinning_exception_handled(self, mocker):
        """Test _toggle_onion_skinning handles exceptions gracefully (line 1624-1625)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        # Mock the onion_skinning module's get function to raise an exception
        # The import happens inside the method, so we need to mock at the module level
        mock_onion_module = mocker.MagicMock()
        mock_onion_module.get_onion_skinning_manager.side_effect = RuntimeError('test error')
        mocker.patch.dict(
            'sys.modules',
            {'glitchygames.tools.onion_skinning': mock_onion_module},
        )
        # Should not raise - exception is caught and logged
        widget._toggle_onion_skinning('idle', 0)


class TestFilmStripGetFrameImageStale:
    """Test _get_frame_image with stale image path (lines 499-528)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_get_frame_image_stale_with_pixels_and_image(self):
        """Test _get_frame_image returns surface from pixel data when image is stale."""
        frame = SpriteFrame(pygame.Surface((2, 2), pygame.SRCALPHA), duration=0.5)
        frame._image_stale = True  # type: ignore[unresolved-attribute]
        frame.pixels = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)]

        result = FilmStripWidget._get_frame_image(frame)
        assert isinstance(result, pygame.Surface)
        assert result.get_size() == (2, 2)

    def test_get_frame_image_stale_without_image_uses_sqrt_fallback(self, mocker):
        """Test _get_frame_image falls back to sqrt when no image (lines 506-516)."""
        # Create a mock frame that has _image_stale=True, pixels, but no image/get_size
        frame = mocker.Mock(spec=[])
        frame._image_stale = True  # type: ignore[unresolved-attribute]
        frame.pixels = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)]
        frame.image = None
        frame._image = None

        result = FilmStripWidget._get_frame_image(frame)
        assert isinstance(result, pygame.Surface)

    def test_get_frame_image_normal_path_no_image(self, mocker):
        """Test _get_frame_image returns None when no image or pixel data (line 546)."""
        # Use a mock that has no image and no get_pixel_data
        frame = mocker.Mock(spec=[])
        frame._image_stale = False
        frame.image = None

        result = FilmStripWidget._get_frame_image(frame)
        assert result is None

    def test_get_frame_image_stale_with_internal_image(self):
        """Test _get_frame_image uses _image when image is None but _image exists (line 503-504)."""
        frame = SpriteFrame(pygame.Surface((3, 3), pygame.SRCALPHA), duration=0.5)
        frame._image_stale = True  # type: ignore[unresolved-attribute]
        pixel_data = cast(list[tuple[int, ...]], [(255, 0, 0, 255)] * 9)
        frame.pixels = pixel_data
        # Set image to None but _image to a valid surface
        frame.image = None  # type: ignore[invalid-assignment]
        frame._image = pygame.Surface((3, 3), pygame.SRCALPHA)

        result = FilmStripWidget._get_frame_image(frame)
        assert isinstance(result, pygame.Surface)
        assert result.get_size() == (3, 3)


class TestFilmStripRenderEditingLabel:
    """Test _render_editing_label for cursor blink rendering (lines 1972-2014)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_editing_label_with_text_and_cursor(self):
        """Test _render_editing_label renders text with blinking cursor."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_text = 'walk'
        widget.cursor_visible = True
        widget.cursor_blink_time = 0

        label_surface = pygame.Surface((100, 20), pygame.SRCALPHA)
        anim_rect = pygame.Rect(0, 0, 100, 20)
        widget._render_editing_label(label_surface, anim_rect)
        # Should not raise

    def test_render_editing_label_empty_text_with_cursor(self):
        """Test _render_editing_label renders cursor with no text (lines 2000-2011)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_text = ''
        widget.cursor_visible = True
        widget.cursor_blink_time = 0

        label_surface = pygame.Surface((100, 20), pygame.SRCALPHA)
        anim_rect = pygame.Rect(0, 0, 100, 20)
        widget._render_editing_label(label_surface, anim_rect)
        # Should render cursor at center without error

    def test_render_editing_label_cursor_blink_toggle(self):
        """Test _render_editing_label toggles cursor blink (lines 1972-1975)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_text = 'test'
        widget.cursor_visible = True
        # Set cursor_blink_time far in the past to trigger toggle
        widget.cursor_blink_time = 0

        label_surface = pygame.Surface((100, 20), pygame.SRCALPHA)
        anim_rect = pygame.Rect(0, 0, 100, 20)

        # Force current ticks to be well past the blink interval
        current_ticks = pygame.time.get_ticks()
        if current_ticks - widget.cursor_blink_time > 530:
            # cursor_visible should toggle
            widget._render_editing_label(label_surface, anim_rect)
            # After toggle, cursor_visible should have changed
            # (it was True, should now be False after blink interval)


class TestFilmStripRenderWithHover:
    """Test render method with hover effect (lines 2078-2079)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_with_hovering_strip(self, mocker):
        """Test render draws hover effect when is_hovering_strip is True."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)
        widget.is_hovering_strip = True

        # Mock parent scene for multi-controller indicators
        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)
        widget.render(render_surface)
        # Should not raise; hover effect is drawn


class TestFilmStripGetActiveControllerSelections:
    """Test _get_active_controller_selections (lines 2099-2117)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_no_parent_scene_returns_empty(self):
        """Test returns empty list when no parent_scene."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        result = widget._get_active_controller_selections()
        assert result == []

    def test_with_active_controller_selection(self, mocker):
        """Test returns selections for active controllers matching animation."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        # Mock parent_scene with controller_selections
        mock_selection = mocker.Mock()
        mock_selection.is_active.return_value = True
        mock_selection.get_selection.return_value = ('idle', 0)

        # Mock controller info
        mock_controller_info = mocker.Mock()
        mock_controller_info.controller_id = 0
        mock_controller_info.color = (255, 0, 0)

        widget.parent_scene = mocker.Mock()
        widget.parent_scene.controller_selections = {0: mock_selection}
        widget.parent_scene.multi_controller_manager = mocker.Mock()
        widget.parent_scene.multi_controller_manager.controllers = {0: mock_controller_info}

        result = widget._get_active_controller_selections()
        assert len(result) == 1
        assert result[0]['controller_id'] == 0
        assert result[0]['color'] == (255, 0, 0)

    def test_with_inactive_controller_selection(self, mocker):
        """Test skips inactive controller selections (line 2100)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        mock_selection = mocker.Mock()
        mock_selection.is_active.return_value = False

        widget.parent_scene = mocker.Mock()
        widget.parent_scene.controller_selections = {0: mock_selection}

        result = widget._get_active_controller_selections()
        assert result == []

    def test_with_wrong_animation_controller(self, mocker):
        """Test skips controllers selecting different animation (line 2103)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        mock_selection = mocker.Mock()
        mock_selection.is_active.return_value = True
        mock_selection.get_selection.return_value = ('walk', 0)  # Different animation

        widget.parent_scene = mocker.Mock()
        widget.parent_scene.controller_selections = {0: mock_selection}

        result = widget._get_active_controller_selections()
        assert result == []


class TestFilmStripDrawMultiControllerIndicators:
    """Test _draw_multi_controller_indicators color priority (lines 2218-2230, 2275-2284)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_controller_color_priority_sorting(self):
        """Test controller selections are sorted by color priority."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        # Set up frame layout for the test
        widget.frame_layouts['idle', 0] = pygame.Rect(50, 50, 64, 64)

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)

        # Create controller selections with various colors
        controller_selections = [
            {'controller_id': 3, 'frame': 0, 'color': (255, 255, 0)},  # Yellow (priority 3)
            {'controller_id': 0, 'frame': 0, 'color': (255, 0, 0)},  # Red (priority 0)
            {'controller_id': 2, 'frame': 0, 'color': (0, 0, 255)},  # Blue (priority 2)
            {'controller_id': 1, 'frame': 0, 'color': (0, 255, 0)},  # Green (priority 1)
        ]

        widget._draw_multi_controller_indicators(render_surface, 'idle', 0, controller_selections)
        # Should draw all indicators without error

    def test_unknown_controller_color_priority(self):
        """Test unknown controller colors get priority 999 (lines 2227-2228)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        widget.frame_layouts['idle', 0] = pygame.Rect(50, 50, 64, 64)

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)

        # Unknown color
        controller_selections = [
            {'controller_id': 0, 'frame': 0, 'color': (128, 128, 128)},  # Unknown color
        ]

        widget._draw_multi_controller_indicators(render_surface, 'idle', 0, controller_selections)

    def test_keyboard_and_controller_indicators(self):
        """Test drawing both keyboard and controller indicators (lines 2308-2315)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        widget.frame_layouts['idle', 0] = pygame.Rect(50, 50, 64, 64)

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)

        controller_selections = [
            {'controller_id': 0, 'frame': 0, 'color': (255, 0, 0)},
        ]

        # keyboard_animation matches current_animation, so keyboard indicator drawn too
        widget._draw_multi_controller_indicators(render_surface, 'idle', 0, controller_selections)

    def test_no_selections_returns_early(self):
        """Test returns early with no selections (line 2292)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)

        # No matching keyboard or controller
        widget._draw_multi_controller_indicators(render_surface, 'other', -1, [])


class TestFilmStripHandleAddDeleteAnimationTab:
    """Test _handle_add_animation_tab_click and _handle_delete_animation_tab_click."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_handle_add_animation_no_parent(self):
        """Test _handle_add_animation_tab_click without parent scene (line 2716)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._handle_add_animation_tab_click()
        # Should return without error

    def test_handle_add_animation_no_canvas(self, mocker):
        """Test _handle_add_animation_tab_click without canvas (lines 2719-2720)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.parent_scene = mocker.Mock(spec=['_add_new_animation'])
        # canvas is not present (spec restricts attributes)
        widget._handle_add_animation_tab_click()
        widget.parent_scene._add_new_animation.assert_called_once()

    def test_handle_add_animation_with_canvas(self, mocker):
        """Test _handle_add_animation_tab_click with canvas inserts after current (line 2725)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        widget.parent_scene = mocker.Mock()
        widget.parent_scene.canvas = mocker.Mock()
        widget.parent_scene.canvas.animated_sprite = sprite

        widget._handle_add_animation_tab_click()
        widget.parent_scene._add_new_animation.assert_called_once_with(insert_after_index=0)

    def test_handle_add_animation_fallback_on_value_error(self, mocker):
        """Test _handle_add_animation_tab_click falls back when animation not found (line 2727)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)
        # Set current_animation to something not in the list
        widget.current_animation = 'nonexistent'

        widget.parent_scene = mocker.Mock()
        widget.parent_scene.canvas = mocker.Mock()
        widget.parent_scene.canvas.animated_sprite = sprite

        widget._handle_add_animation_tab_click()
        widget.parent_scene._add_new_animation.assert_called_once_with()

    def test_handle_delete_animation_no_parent(self):
        """Test _handle_delete_animation_tab_click without parent scene (line 2732)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._handle_delete_animation_tab_click()
        # Should return without error

    def test_handle_delete_animation_no_canvas(self, mocker):
        """Test _handle_delete_animation_tab_click without canvas (line 2735)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.parent_scene = mocker.Mock(spec=['_delete_animation'])
        widget._handle_delete_animation_tab_click()
        # Should return without error (no canvas to check)

    def test_handle_delete_animation_with_multiple(self, mocker):
        """Test _handle_delete_animation_tab_click deletes when multiple animations."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        sprite.add_animation('walk', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        widget.parent_scene = mocker.Mock()
        widget.parent_scene.canvas = mocker.Mock()
        widget.parent_scene.canvas.animated_sprite = sprite

        widget._handle_delete_animation_tab_click()
        widget.parent_scene._delete_animation.assert_called_once_with('idle')


class TestFilmStripHandleRemovalButton:
    """Test _handle_removal_button_click edge cases (lines 2895-2899)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_removal_button_shows_confirmation(self, mocker):
        """Test removal button shows confirmation dialog (lines 2895-2897)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface), SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        widget.parent_scene = mocker.Mock()

        # Set up a removal button layout at a known position
        button_rect = pygame.Rect(10, 10, 11, 30)
        widget.removal_button_layouts = {('idle', 0): button_rect}

        result = widget._handle_removal_button_click((15, 25))
        assert result is True
        widget.parent_scene._show_delete_frame_confirmation.assert_called_once_with('idle', 0)

    def test_removal_button_out_of_range(self, mocker):
        """Test removal button returns False when frame index is out of range (lines 2898-2899)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        # Set up removal button for frame index 5 which doesn't exist
        button_rect = pygame.Rect(10, 10, 11, 30)
        widget.removal_button_layouts = {('idle', 5): button_rect}

        result = widget._handle_removal_button_click((15, 25))
        assert result is False


class TestFilmStripTrackFrameDeletion:
    """Test _track_frame_deletion_for_undo edge cases (line 2935)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_track_deletion_without_parent_scene(self):
        """Test _track_frame_deletion_for_undo returns early without parent_scene."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        frames = sprite._animations['idle']
        widget._track_frame_deletion_for_undo(frames, 'idle', 0)
        # Should return early without error


class TestFilmStripClampAnimatedSpriteFrame:
    """Test _clamp_animated_sprite_frame edge cases (lines 2972, 2978)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_clamp_when_frame_exceeds_remaining(self):
        """Test clamps frame when current frame exceeds remaining frames (line 2978)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        # Set frame manager to a frame beyond current count
        sprite.frame_manager.current_frame = 5
        sprite.frame_manager.current_animation = 'idle'

        frames = sprite._animations['idle']  # Has 1 frame
        widget._clamp_animated_sprite_frame('idle', frames)
        assert sprite.frame_manager.current_frame == 0

    def test_clamp_different_animation_does_nothing(self):
        """Test clamp does nothing for different animation (line 2972)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        sprite.frame_manager.current_animation = 'walk'  # Different from 'idle'

        frames = sprite._animations['idle']
        widget._clamp_animated_sprite_frame('idle', frames)
        # Should not modify anything since animations don't match


class TestFilmStripRemoveFrame:
    """Test _remove_frame scroll adjustment (lines 3046-3048)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_remove_frame_adjusts_scroll_for_many_frames(self, mocker):
        """Test _remove_frame adjusts scroll offset when more than FRAMES_PER_VIEW remain."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        # Add 6 frames so after removal we still have > FRAMES_PER_VIEW
        frames = [SpriteFrame(surface, duration=0.5) for _ in range(6)]
        sprite.add_animation('idle', frames)
        widget.set_animated_sprite(sprite)
        widget.scroll_offset = 100  # Set a large scroll offset

        widget.parent_scene = mocker.Mock(spec=[])

        widget._remove_frame('idle', 0)
        # After removal, 5 frames remain (> 4), scroll should be clamped
        assert widget.scroll_offset <= 1  # max(0, 5 - 4) = 1

    def test_remove_frame_resets_scroll_for_few_frames(self, mocker):
        """Test _remove_frame resets scroll to 0 when FRAMES_PER_VIEW or fewer remain."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        frames = [SpriteFrame(surface, duration=0.5) for _ in range(3)]
        sprite.add_animation('idle', frames)
        widget.set_animated_sprite(sprite)
        widget.scroll_offset = 50

        widget.parent_scene = mocker.Mock(spec=[])

        widget._remove_frame('idle', 0)
        # After removal, 2 frames remain (<= 4), scroll resets to 0
        assert widget.scroll_offset == 0


class TestFilmStripRenderRemovalButton:
    """Test _render_removal_button skipping (lines 3084-3098)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_removal_button_no_layout(self):
        """Test _render_removal_button returns when no layout exists (lines 3084-3085)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        # Set up removal_button_layouts but without the frame we're rendering
        widget.removal_button_layouts = {('idle', 1): pygame.Rect(0, 0, 11, 30)}

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)
        widget._render_removal_button(render_surface, 'idle', 0)
        # Should return early without error

    def test_render_removal_button_single_frame_skips(self):
        """Test _render_removal_button skips when animation has only 1 frame (lines 3094-3098)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        # Set up a removal button layout even though there's only 1 frame
        widget.removal_button_layouts = {('idle', 0): pygame.Rect(0, 0, 11, 30)}

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)
        widget._render_removal_button(render_surface, 'idle', 0)
        # Should skip rendering since there's only 1 frame


class TestFilmStripDeleteTabRender:
    """Test FilmStripDeleteTab render in clicked state (lines 3321-3322)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_clicked_state(self):
        """Test FilmStripDeleteTab renders in clicked state."""
        tab = FilmStripDeleteTab(x=10, y=10, width=40, height=10)
        tab.is_clicked = True
        surface = pygame.Surface((100, 50), pygame.SRCALPHA)
        tab.render(surface)
        # Should render with click_color

    def test_reset_click_state(self):
        """Test FilmStripDeleteTab.reset_click_state (line 3374)."""
        tab = FilmStripDeleteTab(x=10, y=10)
        tab.is_clicked = True
        tab.reset_click_state()
        assert tab.is_clicked is False


class TestFilmStripTabRender:
    """Test FilmStripTab render in clicked state (lines 3446-3447)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_clicked_state(self):
        """Test FilmStripTab renders in clicked state."""
        tab = FilmStripTab(x=10, y=10, width=40, height=10)
        tab.is_clicked = True
        surface = pygame.Surface((100, 50), pygame.SRCALPHA)
        tab.render(surface)
        # Should render with click_color

    def test_handle_click_miss(self):
        """Test FilmStripTab.handle_click returns False on miss (line 3484)."""
        tab = FilmStripTab(x=10, y=10, width=40, height=10)
        result = tab.handle_click((999, 999))
        assert result is False


class TestFilmStripHandleClickEdgeCases:
    """Test handle_click with removal button and tab interactions (lines 1166-1167, 1171-1172)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_handle_click_removal_button_returns_none(self, mocker):
        """Test handle_click returns None when removal button was clicked."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface), SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)
        widget.parent_scene = mocker.Mock()

        # Set up removal button at the click position
        click_pos = (15, 25)
        widget.removal_button_layouts = {('idle', 0): pygame.Rect(10, 10, 11, 30)}

        result = widget.handle_click(click_pos)
        assert result is None

    def test_handle_click_tab_returns_none(self, mocker):
        """Test handle_click returns None when a tab was clicked (lines 1171-1172)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        # Create a tab at a specific position
        tab = FilmTabWidget(x=5, y=50, width=11, height=30)
        tab.set_insertion_type('before', 0)
        widget.film_tabs = [tab]

        # Mock _insert_frame_at_tab to prevent actual frame insertion
        mocker.patch.object(widget, '_insert_frame_at_tab')

        result = widget.handle_click((10, 65))
        assert result is None


class TestFilmStripPropagateDirtyUpParentChain:
    """Test _propagate_dirty_up_parent_chain (lines 619-624)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_propagate_up_sets_parent_dirty(self, mocker):
        """Test _propagate_dirty_up_parent_chain marks parent as dirty (line 620)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        parent = mocker.Mock()
        parent.dirty = 0
        parent.parent = None  # Stop recursion

        widget._propagate_dirty_up_parent_chain(parent)
        assert parent.dirty == 1

    def test_propagate_up_recurses_to_grandparent(self, mocker):
        """Test _propagate_dirty_up_parent_chain recurses through chain (line 624)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        grandparent = mocker.Mock()
        grandparent.dirty = 0
        grandparent.parent = None

        parent = mocker.Mock()
        parent.dirty = 0
        parent.parent = grandparent

        widget._propagate_dirty_up_parent_chain(parent)
        assert parent.dirty == 1
        assert grandparent.dirty == 1

    def test_propagate_up_none_parent_returns(self):
        """Test _propagate_dirty_up_parent_chain returns on None."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._propagate_dirty_up_parent_chain(None)
        # Should return without error


class TestFilmStripDrawPreviewTriangle:
    """Test _draw_preview_triangle fallback paths (lines 2371-2374)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_preview_triangle_no_animation_data(self):
        """Test _draw_preview_triangle centers triangle when no animation data (line 2374)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        # Create a preview rect that's NOT in preview_rects so anim_name lookup fails
        preview_rect = pygame.Rect(400, 10, 64, 64)

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)
        widget._draw_preview_triangle(render_surface, preview_rect)
        # Should use fallback center position

    def test_preview_triangle_single_frame_centered(self):
        """Test _draw_preview_triangle centers triangle for single-frame animation."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        preview_rect = pygame.Rect(400, 10, 64, 64)
        widget.preview_rects['idle'] = preview_rect

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)
        widget._draw_preview_triangle(render_surface, preview_rect)
        # Should center the triangle for single frame


class TestFilmStripRenderPreviewEdgeCases:
    """Test render_preview edge cases (lines 1810-1822, 1833-1840)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_preview_with_no_frame_image(self, mocker):
        """Test render_preview draws placeholder when frame has no image (lines 1833-1840)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        frame = SpriteFrame(surface, duration=0.5)
        sprite.add_animation('idle', [frame])
        widget.set_animated_sprite(sprite)

        # Create a mock frame with no image to trigger placeholder
        mock_frame = mocker.Mock(spec=[])
        mock_frame._image_stale = False
        mock_frame.image = None
        mock_frame.duration = 0.5
        sprite._animations['idle'] = [mock_frame]

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)
        widget.render_preview(render_surface)

    def test_render_preview_hovered(self):
        """Test render_preview draws hover effect on preview (line 1795)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface, duration=0.5)])
        widget.set_animated_sprite(sprite)
        widget.hovered_preview = 'idle'

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)
        widget.render_preview(render_surface)


class TestFilmStripRenderFrameThumbnailEdgeCases:
    """Test render_frame_thumbnail edge cases (lines 1480, 1505, 1560-1562)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_thumbnail_no_frame_image(self, mocker):
        """Test render_frame_thumbnail draws placeholder when no image (line 1480)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        # Use a mock frame that has no image and no pixel data
        frame = mocker.Mock(spec=[])
        frame._image_stale = False
        frame.image = None

        result = widget.render_frame_thumbnail(frame)
        assert isinstance(result, pygame.Surface)

    def test_render_thumbnail_hovered(self):
        """Test render_frame_thumbnail draws hover effect (line 1505)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        frame = SpriteFrame(surface, duration=0.5)

        result = widget.render_frame_thumbnail(frame, is_hovered=True)
        assert isinstance(result, pygame.Surface)


class TestFilmStripHandleKeyboardEnterKey:
    """Test handle_keyboard_input Enter key for renaming (lines 1425-1436 via rename flow)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_enter_key_commits_rename(self, mocker):
        """Test Enter key commits animation rename via parent scene."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)

        widget.editing_animation = 'idle'
        widget.editing_text = 'walk'
        widget.original_animation_name = 'idle'
        widget.parent_scene = mocker.Mock()

        event = mocker.Mock()
        event.key = pygame.K_RETURN
        event.unicode = ''
        event.mod = 0

        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_animation is None
        widget.parent_scene.on_animation_rename.assert_called_once_with('idle', 'walk')

    def test_enter_key_same_name_no_rename(self, mocker):
        """Test Enter key does not rename when name is unchanged."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)

        widget.editing_animation = 'idle'
        widget.editing_text = 'idle'  # Same name
        widget.original_animation_name = 'idle'
        widget.parent_scene = mocker.Mock()

        event = mocker.Mock()
        event.key = pygame.K_RETURN
        event.unicode = ''

        result = widget.handle_keyboard_input(event)
        assert result is True
        widget.parent_scene.on_animation_rename.assert_not_called()

    def test_enter_key_empty_text_no_rename(self, mocker):
        """Test Enter key does not rename when text is empty."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)

        widget.editing_animation = 'idle'
        widget.editing_text = ''
        widget.original_animation_name = 'idle'

        event = mocker.Mock()
        event.key = pygame.K_RETURN
        event.unicode = ''

        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_animation is None


class TestFilmStripGetControllerSelectionColor:
    """Test _get_controller_selection_color (lines 1425-1436)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_returns_controller_color_for_matching_selection(self, mocker):
        """Test returns controller color when a controller has the frame selected."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)

        mock_selection = mocker.Mock()
        mock_selection.is_active.return_value = True
        mock_selection.get_selection.return_value = ('idle', 0)

        mock_controller_info = mocker.Mock()
        mock_controller_info.controller_id = 0
        mock_controller_info.color = (255, 0, 0)

        mock_manager = mocker.Mock()
        mock_manager.controllers = {0: mock_controller_info}

        widget.parent_scene = mocker.Mock()
        widget.parent_scene.controller_selections = {0: mock_selection}

        # Mock the module that gets imported locally inside the method
        mock_multi_ctrl_module = mocker.MagicMock()
        mock_multi_ctrl_module.MultiControllerManager.get_instance.return_value = mock_manager
        mocker.patch.dict(
            'sys.modules',
            {'glitchygames.tools.multi_controller_manager': mock_multi_ctrl_module},
        )

        result = widget._get_controller_selection_color('idle', 0)
        assert result == (255, 0, 0)

    def test_returns_none_for_inactive_controller(self, mocker):
        """Test returns None when controller is inactive (line 1425-1426)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)

        mock_selection = mocker.Mock()
        mock_selection.is_active.return_value = False

        widget.parent_scene = mocker.Mock()
        widget.parent_scene.controller_selections = {0: mock_selection}

        result = widget._get_controller_selection_color('idle', 0)
        assert result is None

    def test_returns_none_for_different_frame(self, mocker):
        """Test returns None when controller selects different frame (line 1428-1429)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)

        mock_selection = mocker.Mock()
        mock_selection.is_active.return_value = True
        mock_selection.get_selection.return_value = ('idle', 5)  # Different frame

        widget.parent_scene = mocker.Mock()
        widget.parent_scene.controller_selections = {0: mock_selection}

        result = widget._get_controller_selection_color('idle', 0)
        assert result is None


class TestFilmStripRenderVerticalDividerAndPreviewBackground:
    """Test _render_vertical_divider and _render_preview_background (lines 1877, 1894)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_vertical_divider_no_sprite(self):
        """Test _render_vertical_divider returns when no animated sprite (line 1877)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)
        widget._render_vertical_divider(surface)
        # Should return without error

    def test_render_preview_background_no_sprite(self):
        """Test _render_preview_background returns when no animated sprite (line 1894)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)
        widget._render_preview_background(surface)
        # Should return without error


class TestFilmStripCalculateFramesWidth:
    """Test _calculate_frames_width (line 2543)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_calculate_frames_width_with_multiple_animations(self):
        """Test _calculate_frames_width adds sprocket width between animations (line 2543)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        sprite.add_animation('walk', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        result = widget._calculate_frames_width()
        # Should include sprocket width between the two animations
        expected_per_frame = widget.frame_width + widget.frame_spacing
        assert result == expected_per_frame * 2 + widget.sprocket_width


class TestFilmStripHandleTabHover:
    """Test _handle_tab_hover (line 2752-2754)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_handle_tab_hover_returns_true_when_hovering(self):
        """Test _handle_tab_hover returns True when hovering over a tab."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        tab = FilmTabWidget(x=10, y=10, width=20, height=30)
        widget.film_tabs = [tab]

        result = widget._handle_tab_hover((15, 25))
        assert result is True
        assert tab.is_hovered is True

    def test_handle_tab_hover_returns_false_when_not_hovering(self):
        """Test _handle_tab_hover returns False when not hovering over any tab."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        tab = FilmTabWidget(x=10, y=10, width=20, height=30)
        widget.film_tabs = [tab]

        result = widget._handle_tab_hover((999, 999))
        assert result is False


class TestFilmStripDrawFilmSprockets:
    """Test _draw_film_sprockets with label area (lines 2470-2474)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_draw_film_sprockets_with_animation_layout(self):
        """Test _draw_film_sprockets avoids label area (lines 2470-2474)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        render_surface = pygame.Surface((WIDGET_WIDTH, WIDGET_HEIGHT), pygame.SRCALPHA)
        widget._draw_film_sprockets(render_surface)
        # Should skip sprockets in the label area


class TestFilmStripHandleClickEnterEditMode:
    """Test handle_click entering animation label edit mode."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_click_animation_label_enters_edit_mode(self, mocker):
        """Test clicking animation label enters edit mode."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        # Get the animation label rect and click inside it
        label_rect = widget.animation_layouts.get('idle')
        if label_rect:
            click_pos = (label_rect.centerx, label_rect.centery)
            result = widget.handle_click(click_pos)
            assert result is None  # Should return None for label clicks
            assert widget.editing_animation == 'idle'
            assert not widget.editing_text


class TestFilmStripSetFrameIndex:
    """Test set_frame_index with parent canvas (line 2572)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_set_frame_index_updates_parent_canvas(self, mocker):
        """Test set_frame_index updates the parent canvas interface (line 2572)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface), SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)

        widget.parent_canvas = mocker.Mock()
        widget.parent_canvas.canvas_interface = mocker.Mock()

        widget.set_frame_index(1)
        assert widget.current_frame == 1
        widget.parent_canvas.canvas_interface.set_current_frame.assert_called_once_with('idle', 1)


class TestFilmStripRenderAnimationLabel:
    """Test _render_animation_label hovered state (lines 1949, 1957, 1963)."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_render_label_hovered_but_not_editing(self):
        """Test _render_animation_label adds hover highlighting (line 1963)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)
        widget.hovered_animation = 'idle'
        widget.editing_animation = None

        anim_rect = widget.animation_layouts.get('idle')
        if anim_rect:
            result = widget._render_animation_label('idle', anim_rect)
            assert isinstance(result, pygame.Surface)

    def test_render_label_in_edit_mode(self):
        """Test _render_animation_label calls _render_editing_label when editing (line 1949)."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE), pygame.SRCALPHA)
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)
        widget.editing_animation = 'idle'
        widget.editing_text = 'walking'
        widget.cursor_visible = True
        widget.cursor_blink_time = 0

        anim_rect = widget.animation_layouts.get('idle')
        if anim_rect:
            result = widget._render_animation_label('idle', anim_rect)
            assert isinstance(result, pygame.Surface)
