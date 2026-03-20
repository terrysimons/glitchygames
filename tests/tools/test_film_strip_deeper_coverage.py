"""Deeper coverage tests for glitchygames/tools/film_strip.py.

Targets uncovered areas NOT covered by existing test files:
- handle_keyboard_input: Enter/Escape/Backspace/printable chars in edit mode
- handle_click: frame clicks, animation label clicks, preview clicks, strip clicks
- handle_hover: hover updates for frames, animations, removal buttons, tabs
- handle_preview_click: background color cycling
- _calculate_scroll_offset: edge cases
- update_scroll_for_frame: scrolling to off-screen frames
- _propagate_dirty_to_sprite_groups: group traversal
- _has_valid_canvas_sprite: various parent states
- _is_keyboard_selected: parent scene selection matching
- _get_controller_selection_color: controller selection lookup
- _get_active_controller_selections: controller selections filtering
- _toggle_onion_skinning: toggle with and without parent scene
- _stop_animation_before_deletion: animation stop and frame adjust
- _adjust_current_frame_after_deletion: frame index adjustment
- _handle_removal_button_click: removal button click handling
- _handle_tab_click: no tabs scenario
- _handle_tab_hover: hover tracking for tabs
- reset_all_tab_states: clearing tab states
- _create_film_tabs: tab creation with and without frames
- _convert_magenta_to_transparent: magenta/RGB/RGBA handling
- _draw_placeholder: placeholder rendering
- _add_film_strip_styling: film strip edges
- _create_selection_border: selection border creation
- _add_hover_highlighting: hover effect drawing
- _add_3d_beveled_border: beveled border rendering
- render_sprocket_separator: sprocket separator rendering
- set_parent_canvas: parent canvas assignment
- update_layout: layout recalculation
- _dump_animation_debug_state: debug state dumping
- _dump_animated_sprite_debug: animated sprite debug output
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from glitchygames.tools.film_strip import (
    ANIMATION_NAME_MAX_LENGTH,
    FilmStripWidget,
)
from tests.mocks.test_mock_factory import MockFactory

# Constants for test values
WIDGET_X = 0
WIDGET_Y = 0
WIDGET_WIDTH = 500
WIDGET_HEIGHT = 200
SURFACE_SIZE = 4
FRAME_DURATION = 0.5
FRAME_DURATION_FAST = 0.25
DT_60FPS = 0.016
DT_LARGE = 1.0


def _make_widget_with_sprite(num_frames=2, animation_name='idle'):
    """Create a FilmStripWidget with an animated sprite.

    Args:
        num_frames: Number of frames to create.
        animation_name: Name of the animation.

    Returns:
        Tuple of (widget, sprite).

    """
    widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
    sprite = AnimatedSprite()
    surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
    frames = [SpriteFrame(surface, duration=FRAME_DURATION) for _ in range(num_frames)]
    sprite.add_animation(animation_name, frames)
    widget.set_animated_sprite(sprite)
    widget.current_animation = animation_name
    widget.current_frame = 0
    return widget, sprite


class TestHandleKeyboardInput:
    """Test handle_keyboard_input for animation renaming."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

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
        return event

    def test_not_editing_returns_false(self, mocker):
        """Test keyboard input is ignored when not in edit mode."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = None
        event = self._make_key_event(mocker, pygame.K_a, 'a')
        assert widget.handle_keyboard_input(event) is False

    def test_escape_cancels_editing(self, mocker):
        """Test Escape key cancels editing mode."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'partial'
        widget.original_animation_name = 'idle'
        event = self._make_key_event(mocker, pygame.K_ESCAPE)
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_animation is None
        assert not widget.editing_text
        assert widget.original_animation_name is None

    def test_enter_commits_rename_with_parent_scene(self, mocker):
        """Test Enter key commits rename when parent scene exists."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'walk_cycle'
        widget.original_animation_name = 'idle'
        mock_parent = mocker.Mock()
        widget.parent_scene = mock_parent
        event = self._make_key_event(mocker, pygame.K_RETURN)
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_animation is None
        mock_parent.on_animation_rename.assert_called_once_with('idle', 'walk_cycle')

    def test_enter_with_same_name_does_not_rename(self, mocker):
        """Test Enter key with unchanged name does not trigger rename."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'idle'
        widget.original_animation_name = 'idle'
        mock_parent = mocker.Mock()
        widget.parent_scene = mock_parent
        event = self._make_key_event(mocker, pygame.K_RETURN)
        result = widget.handle_keyboard_input(event)
        assert result is True
        mock_parent.on_animation_rename.assert_not_called()

    def test_enter_with_empty_text_does_not_rename(self, mocker):
        """Test Enter key with empty text does not trigger rename."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = ''
        widget.original_animation_name = 'idle'
        event = self._make_key_event(mocker, pygame.K_RETURN)
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_animation is None

    def test_backspace_removes_last_character(self, mocker):
        """Test Backspace key removes the last character."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'abc'
        event = self._make_key_event(mocker, pygame.K_BACKSPACE)
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_text == 'ab'

    def test_backspace_on_empty_text_not_handled(self, mocker):
        """Test Backspace key on empty text falls through to printable check."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = ''
        # Backspace with no unicode should fall through and not match printable
        event = self._make_key_event(mocker, pygame.K_BACKSPACE, '')
        result = widget.handle_keyboard_input(event)
        # Backspace condition requires self.editing_text to be truthy, so it falls through
        # Then it checks unicode which is empty, so returns False
        assert result is False

    def test_printable_character_appended(self, mocker):
        """Test printable characters are appended to editing text."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'wa'
        event = self._make_key_event(mocker, pygame.K_l, 'l')
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_text == 'wal'

    def test_printable_character_max_length(self, mocker):
        """Test printable characters are not added beyond max length."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'x' * ANIMATION_NAME_MAX_LENGTH
        event = self._make_key_event(mocker, pygame.K_a, 'a')
        result = widget.handle_keyboard_input(event)
        assert result is False
        assert len(widget.editing_text) == ANIMATION_NAME_MAX_LENGTH

    def test_non_printable_character_ignored(self, mocker):
        """Test non-printable characters are ignored."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'test'
        event = self._make_key_event(mocker, pygame.K_F1, '')
        result = widget.handle_keyboard_input(event)
        assert result is False


class TestHandleClick:
    """Test handle_click method for various click targets."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_click_on_frame_returns_animation_and_frame(self):
        """Test clicking on a frame returns the animation and frame index."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        # Manually set a frame layout for testing
        frame_rect = pygame.Rect(50, 50, 64, 64)
        widget.frame_layouts['idle', 0] = frame_rect
        result = widget.handle_click((60, 60))
        assert result is not None
        assert result[1] == 0

    def test_click_outside_returns_none(self):
        """Test clicking outside the film strip returns None."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        result = widget.handle_click((9999, 9999))
        assert result is None

    def test_right_click_on_frame_toggles_onion_skinning(self, mocker):
        """Test right-clicking on a frame toggles onion skinning."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        frame_rect = pygame.Rect(50, 50, 64, 64)
        widget.frame_layouts['idle', 0] = frame_rect
        mocker.patch.object(widget, '_toggle_onion_skinning')
        result = widget.handle_click((60, 60), is_right_click=True)
        assert result is None  # Right-click doesn't select frame
        widget._toggle_onion_skinning.assert_called_once()

    def test_shift_click_on_frame_toggles_onion_skinning(self, mocker):
        """Test shift-clicking on a frame toggles onion skinning."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        frame_rect = pygame.Rect(50, 50, 64, 64)
        widget.frame_layouts['idle', 0] = frame_rect
        mocker.patch.object(widget, '_toggle_onion_skinning')
        result = widget.handle_click((60, 60), is_shift_click=True)
        assert result is None
        widget._toggle_onion_skinning.assert_called_once()


class TestHandleHover:
    """Test handle_hover method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_hover_updates_hovered_frame(self):
        """Test hovering over a frame updates hovered_frame."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.frame_layouts['idle', 0] = pygame.Rect(50, 50, 64, 64)
        widget.handle_hover((60, 60))
        assert widget.hovered_frame == ('idle', 0)

    def test_hover_outside_clears_hovered_frame(self):
        """Test hovering outside frames clears hovered_frame."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.hovered_frame = ('idle', 0)
        widget.handle_hover((9999, 9999))
        assert widget.hovered_frame is None

    def test_hover_updates_hovered_animation(self):
        """Test hovering over animation label updates hovered_animation."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.animation_layouts['idle'] = pygame.Rect(100, 5, 60, 20)
        widget.handle_hover((110, 10))
        assert widget.hovered_animation == 'idle'


class TestHandlePreviewClick:
    """Test handle_preview_click method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_preview_click_cycles_background_color(self):
        """Test clicking on preview area cycles background color."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        widget.preview_rects['idle'] = pygame.Rect(400, 10, 64, 64)
        initial_index = widget.background_color_index
        result = widget.handle_preview_click((420, 30))
        assert result is not None
        assert widget.background_color_index == (initial_index + 1) % len(widget.BACKGROUND_COLORS)

    def test_preview_click_no_hit_returns_none(self):
        """Test clicking outside preview area returns None."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        result = widget.handle_preview_click((9999, 9999))
        assert result is None

    def test_preview_click_uses_global_selected_frame(self, mocker):
        """Test preview click uses parent scene's selected_frame."""
        widget, _sprite = _make_widget_with_sprite(num_frames=3)
        widget.preview_rects['idle'] = pygame.Rect(400, 10, 64, 64)
        mock_parent = mocker.Mock()
        mock_parent.selected_frame = 2
        widget.parent_scene = mock_parent
        result = widget.handle_preview_click((420, 30))
        assert result == ('idle', 2)


class TestUpdateScrollForFrame:
    """Test update_scroll_for_frame with various scrolling scenarios."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_scroll_to_frame_beyond_view_right(self):
        """Test scrolling to a frame that is to the right of the visible area."""
        widget, _sprite = _make_widget_with_sprite(num_frames=10)
        widget.scroll_offset = 0
        # Frame 8 is well beyond the initial 4-frame window
        widget.update_scroll_for_frame(8)
        assert widget.scroll_offset > 0

    def test_scroll_to_frame_beyond_view_left(self):
        """Test scrolling to a frame that is to the left of the visible area."""
        widget, _sprite = _make_widget_with_sprite(num_frames=10)
        # Set scroll offset so first visible frame is 5
        widget.scroll_offset = 5 * (widget.frame_width + widget.tab_width + 2)
        widget.update_scroll_for_frame(0)
        # Should scroll back to show frame 0
        assert widget.scroll_offset == 0

    def test_scroll_to_frame_out_of_range(self):
        """Test scrolling to a frame index that exceeds frame count."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        widget.update_scroll_for_frame(999)  # Should not raise


class TestPropagateDirtyToSpriteGroups:
    """Test _propagate_dirty_to_sprite_groups method."""

    def test_propagate_with_callable_groups(self, mocker):
        """Test propagation when sprite.groups() is callable."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_other_sprite = mocker.Mock()
        mock_other_sprite.groups.return_value = []
        mock_other_sprite.dirty = 0

        mock_group = mocker.Mock()
        mock_group.__iter__ = mocker.Mock(return_value=iter([mock_other_sprite]))

        mock_sprite = mocker.Mock()
        mock_sprite.groups.return_value = [mock_group]

        widget._propagate_dirty_to_sprite_groups(mock_sprite)
        assert mock_other_sprite.dirty == 1

    def test_propagate_prevents_infinite_recursion(self, mocker):
        """Test propagation stops on already-visited sprites."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_sprite = mocker.Mock()
        mock_sprite.groups.return_value = []
        visited = {mock_sprite}
        # Should return immediately, not recurse
        widget._propagate_dirty_to_sprite_groups(mock_sprite, visited=visited)

    def test_propagate_handles_no_groups_attribute(self, mocker):
        """Test propagation handles sprites without groups attribute."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_sprite = mocker.Mock(spec=[])  # No attributes
        widget._propagate_dirty_to_sprite_groups(mock_sprite)  # Should not raise


class TestHasValidCanvasSprite:
    """Test _has_valid_canvas_sprite method."""

    def test_no_parent_scene(self):
        """Test returns False when no parent_scene exists."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget._has_valid_canvas_sprite() is False

    def test_parent_scene_with_canvas(self, mocker):
        """Test returns True when parent scene has canvas with animated_sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_parent = mocker.Mock()
        mock_parent.canvas.animated_sprite = mocker.Mock()
        widget.parent_scene = mock_parent
        assert widget._has_valid_canvas_sprite() is True

    def test_parent_scene_without_canvas(self, mocker):
        """Test returns False when parent scene has no canvas attribute."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_parent = mocker.Mock(spec=[])
        widget.parent_scene = mock_parent
        assert widget._has_valid_canvas_sprite() is False


class TestIsKeyboardSelected:
    """Test _is_keyboard_selected method."""

    def test_no_parent_scene(self):
        """Test returns False when no parent_scene."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget._is_keyboard_selected('idle', 0) is False

    def test_matching_selection(self, mocker):
        """Test returns True when parent scene selection matches."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_parent = mocker.Mock()
        mock_parent.selected_animation = 'idle'
        mock_parent.selected_frame = 1
        widget.parent_scene = mock_parent
        assert widget._is_keyboard_selected('idle', 1) is True

    def test_non_matching_selection(self, mocker):
        """Test returns False when parent scene selection does not match."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_parent = mocker.Mock()
        mock_parent.selected_animation = 'walk'
        mock_parent.selected_frame = 0
        widget.parent_scene = mock_parent
        assert widget._is_keyboard_selected('idle', 0) is False


class TestGetControllerSelectionColor:
    """Test _get_controller_selection_color method."""

    def test_no_parent_scene(self):
        """Test returns None when no parent_scene."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        result = widget._get_controller_selection_color('idle', 0)
        assert result is None

    def test_no_controller_selections(self, mocker):
        """Test returns None when parent has no controller_selections."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_parent = mocker.Mock(spec=['canvas'])
        widget.parent_scene = mock_parent
        result = widget._get_controller_selection_color('idle', 0)
        assert result is None


class TestToggleOnionSkinning:
    """Test _toggle_onion_skinning method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_toggle_sets_force_redraw(self, mocker):
        """Test toggling onion skinning sets _force_redraw."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        # Mock the onion skinning module
        mock_manager = mocker.Mock()
        mock_manager.toggle_frame_onion_skinning.return_value = True
        mocker.patch(
            'glitchygames.tools.film_strip.get_onion_skinning_manager',
            return_value=mock_manager,
            create=True,
        )
        mocker.patch(
            'glitchygames.tools.onion_skinning.get_onion_skinning_manager',
            return_value=mock_manager,
        )
        widget._toggle_onion_skinning('idle', 0)
        assert widget._force_redraw is True

    def test_toggle_with_parent_canvas_forces_canvas_redraw(self, mocker):
        """Test toggling onion skinning forces canvas redraw via parent scene."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_manager = mocker.Mock()
        mock_manager.toggle_frame_onion_skinning.return_value = True
        mocker.patch(
            'glitchygames.tools.onion_skinning.get_onion_skinning_manager',
            return_value=mock_manager,
        )
        mock_parent = mocker.Mock()
        widget.parent_scene = mock_parent
        widget._toggle_onion_skinning('idle', 0)
        mock_parent.canvas.force_redraw.assert_called_once()


class TestStopAnimationBeforeDeletion:
    """Test _stop_animation_before_deletion method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_stops_animation_and_adjusts_frame(self):
        """Test stops animation and adjusts frame index downward."""
        widget, sprite = _make_widget_with_sprite(num_frames=3)
        sprite._is_playing = True
        sprite.frame_manager.current_animation = 'idle'
        sprite.frame_manager.current_frame = 2
        widget._stop_animation_before_deletion('idle', 1)
        assert sprite._is_playing is False
        assert sprite.frame_manager.current_frame == 1

    def test_no_adjustment_when_animation_mismatch(self):
        """Test no action when animation name doesn't match."""
        widget, sprite = _make_widget_with_sprite(num_frames=3)
        sprite.frame_manager.current_animation = 'walk'
        widget._stop_animation_before_deletion('idle', 0)
        # Should not have changed anything since animation doesn't match

    def test_no_sprite_returns_early(self):
        """Test returns early when no animated sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._stop_animation_before_deletion('idle', 0)  # Should not raise


class TestAdjustCurrentFrameAfterDeletion:
    """Test _adjust_current_frame_after_deletion method."""

    def test_decrements_current_frame(self):
        """Test current frame is decremented after deletion."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.current_animation = 'idle'
        widget.current_frame = 2
        widget._adjust_current_frame_after_deletion('idle', 1)
        assert widget.current_frame == 1

    def test_does_not_go_below_zero(self):
        """Test current frame does not go below 0."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.current_animation = 'idle'
        widget.current_frame = 0
        widget._adjust_current_frame_after_deletion('idle', 0)
        assert widget.current_frame == 0

    def test_no_adjustment_for_different_animation(self):
        """Test no adjustment when animation name differs."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.current_animation = 'idle'
        widget.current_frame = 2
        widget._adjust_current_frame_after_deletion('walk', 0)
        assert widget.current_frame == 2  # Unchanged

    def test_no_adjustment_when_frame_before_deleted(self):
        """Test no adjustment when current frame is before deleted frame."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.current_animation = 'idle'
        widget.current_frame = 0
        widget._adjust_current_frame_after_deletion('idle', 2)
        assert widget.current_frame == 0  # Unchanged


class TestHandleRemovalButtonClick:
    """Test _handle_removal_button_click method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_no_removal_buttons_returns_false(self):
        """Test returns False when no removal buttons exist."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget._handle_removal_button_click((50, 50)) is False

    def test_click_on_removal_button_with_parent(self, mocker):
        """Test clicking a removal button with a parent scene."""
        widget, _sprite = _make_widget_with_sprite(num_frames=3)
        widget.removal_button_layouts = {
            ('idle', 1): pygame.Rect(10, 40, 11, 30),
        }
        mock_parent = mocker.Mock()
        widget.parent_scene = mock_parent
        result = widget._handle_removal_button_click((15, 50))
        assert result is True
        mock_parent._show_delete_frame_confirmation.assert_called_once_with('idle', 1)

    def test_click_miss_returns_false(self):
        """Test clicking outside removal buttons returns False."""
        widget, _sprite = _make_widget_with_sprite(num_frames=3)
        widget.removal_button_layouts = {
            ('idle', 1): pygame.Rect(10, 40, 11, 30),
        }
        result = widget._handle_removal_button_click((9999, 9999))
        assert result is False


class TestHandleTabClick:
    """Test _handle_tab_click method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_no_tabs_returns_false(self):
        """Test returns False when there are no tabs."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.film_tabs = []
        assert widget._handle_tab_click((50, 50)) is False

    def test_click_miss_returns_false(self, mocker):
        """Test returns False when clicking outside tabs."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_tab = mocker.Mock()
        mock_tab.handle_click.return_value = False
        widget.film_tabs = [mock_tab]
        assert widget._handle_tab_click((50, 50)) is False


class TestHandleTabHover:
    """Test _handle_tab_hover method."""

    def test_no_tabs_returns_false(self):
        """Test returns False when there are no tabs."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.film_tabs = []
        assert widget._handle_tab_hover((50, 50)) is False

    def test_hover_over_tab_returns_true(self, mocker):
        """Test returns True when hovering over a tab."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_tab = mocker.Mock()
        mock_tab.handle_hover.return_value = True
        widget.film_tabs = [mock_tab]
        assert widget._handle_tab_hover((50, 50)) is True

    def test_hover_miss_returns_false(self, mocker):
        """Test returns False when not hovering over any tab."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_tab = mocker.Mock()
        mock_tab.handle_hover.return_value = False
        widget.film_tabs = [mock_tab]
        assert widget._handle_tab_hover((50, 50)) is False


class TestResetAllTabStates:
    """Test reset_all_tab_states method."""

    def test_resets_all_tabs(self, mocker):
        """Test all tabs have their states reset."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_tab1 = mocker.Mock()
        mock_tab2 = mocker.Mock()
        widget.film_tabs = [mock_tab1, mock_tab2]
        widget.reset_all_tab_states()
        mock_tab1.reset_click_state.assert_called_once()
        assert mock_tab1.is_hovered is False
        mock_tab2.reset_click_state.assert_called_once()
        assert mock_tab2.is_hovered is False


class TestSetParentCanvas:
    """Test set_parent_canvas method."""

    def test_sets_parent_canvas(self, mocker):
        """Test parent canvas is set correctly."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_canvas = mocker.Mock()
        widget.set_parent_canvas(mock_canvas)
        assert widget.parent_canvas is mock_canvas


class TestUpdateLayout:
    """Test update_layout method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_layout_recalculates(self, mocker):
        """Test update_layout triggers layout recalculation."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        mocker.patch.object(widget, '_calculate_layout')
        mocker.patch.object(widget, '_create_film_tabs')
        widget.update_layout()
        widget._calculate_layout.assert_called_once()
        widget._create_film_tabs.assert_called_once()


class TestConvertMagentaToTransparent:
    """Test _convert_magenta_to_transparent static method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_magenta_pixels_processed(self):
        """Test magenta pixels are handled by the conversion method."""
        surface = pygame.Surface((2, 2), pygame.SRCALPHA)
        surface.fill((255, 0, 255, 255))
        result = FilmStripWidget._convert_magenta_to_transparent(surface)
        assert result is not None
        assert result.get_size() == (2, 2)
        # The method should set magenta pixels to (255, 0, 255, 0)
        pixel = result.get_at((0, 0))
        assert pixel[0] == 255  # Red component
        assert pixel[2] == 255  # Blue component

    def test_non_magenta_pixels_processed(self):
        """Test non-magenta pixels are processed without error."""
        surface = pygame.Surface((2, 2))
        surface.fill((100, 200, 50))
        result = FilmStripWidget._convert_magenta_to_transparent(surface)
        assert result is not None
        assert result.get_size() == (2, 2)

    def test_rgba_surface_processed(self):
        """Test RGBA surfaces are processed correctly."""
        surface = pygame.Surface((2, 2), pygame.SRCALPHA)
        surface.fill((100, 200, 50, 128))
        result = FilmStripWidget._convert_magenta_to_transparent(surface)
        assert result is not None
        assert result.get_size() == (2, 2)


class TestRenderingMethods:
    """Test rendering helper methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_draw_placeholder(self):
        """Test _draw_placeholder creates a placeholder surface."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((64, 64), pygame.SRCALPHA)
        widget._draw_placeholder(surface)
        # Just verify it doesn't crash - visual output testing is limited

    def test_add_film_strip_styling(self):
        """Test _add_film_strip_styling draws film strip edges."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((64, 64), pygame.SRCALPHA)
        widget._add_film_strip_styling(surface)
        # Verify it doesn't crash

    def test_create_selection_border(self):
        """Test _create_selection_border creates a bordered surface."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        frame_surface = pygame.Surface((64, 64), pygame.SRCALPHA)
        result = widget._create_selection_border(frame_surface)
        assert result.get_width() == 68  # 64 + 4 border
        assert result.get_height() == 68

    def test_add_hover_highlighting(self):
        """Test _add_hover_highlighting draws hover border."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((64, 64), pygame.SRCALPHA)
        widget._add_hover_highlighting(surface)
        # Verify it doesn't crash

    def test_add_3d_beveled_border(self):
        """Test _add_3d_beveled_border draws beveled border."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((64, 64), pygame.SRCALPHA)
        widget._add_3d_beveled_border(surface)
        # Verify it doesn't crash

    def test_render_sprocket_separator(self):
        """Test render_sprocket_separator creates a sprocket surface."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        result = widget.render_sprocket_separator(0, 0, 100)
        assert result.get_width() == widget.sprocket_width
        assert result.get_height() == 100


class TestGetActiveControllerSelections:
    """Test _get_active_controller_selections method."""

    def test_no_parent_scene_returns_empty(self):
        """Test returns empty list when no parent scene."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.current_animation = 'idle'
        result = widget._get_active_controller_selections()
        assert result == []

    def test_no_controller_selections_returns_empty(self, mocker):
        """Test returns empty list when parent has no controller_selections."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.current_animation = 'idle'
        mock_parent = mocker.Mock(spec=['canvas'])
        widget.parent_scene = mock_parent
        result = widget._get_active_controller_selections()
        assert result == []


class TestDumpAnimationDebugState:
    """Test _dump_animation_debug_state and _dump_animated_sprite_debug methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_dump_animation_debug_state(self):
        """Test _dump_animation_debug_state runs without error."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        widget._debug_start_time = 5.0
        widget._debug_last_dump_time = 0.0
        widget._dump_animation_debug_state(DT_60FPS)
        # Verify the dump time was updated
        assert widget._debug_last_dump_time > 0.0

    def test_dump_animated_sprite_debug(self):
        """Test _dump_animated_sprite_debug runs without error on loaded sprite."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        widget._dump_animated_sprite_debug()  # Should not raise

    def test_dump_without_sprite(self):
        """Test _dump_animation_debug_state runs without animated sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._debug_start_time = 5.0
        widget._debug_last_dump_time = 0.0
        # scroll_offset is set during set_animated_sprite, so set it manually
        widget.scroll_offset = 0
        widget._dump_animation_debug_state(DT_60FPS)


class TestCalculateScrollOffset:
    """Test _calculate_scroll_offset edge cases."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_offset_for_last_frame_is_clamped(self):
        """Test scroll offset for last frame is clamped to max scroll."""
        widget, sprite = _make_widget_with_sprite(num_frames=10)
        frames = sprite._animations['idle']
        offset = widget._calculate_scroll_offset(9, frames)
        frame_width = widget.frame_width + widget.frame_spacing
        assert widget.rect is not None
        max_scroll = max(0, len(frames) * frame_width - widget.rect.width)
        assert offset <= max_scroll

    def test_offset_for_middle_frame(self):
        """Test scroll offset for a middle frame."""
        widget, sprite = _make_widget_with_sprite(num_frames=20)
        frames = sprite._animations['idle']
        offset = widget._calculate_scroll_offset(10, frames)
        assert offset > 0


class TestGetRemovalButtonAtPosition:
    """Test get_removal_button_at_position method."""

    def test_no_layouts_returns_none(self):
        """Test returns None when no removal button layouts exist."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.get_removal_button_at_position((50, 50)) is None

    def test_hit_returns_tuple(self):
        """Test returns (anim_name, frame_idx) when button is hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.removal_button_layouts = {
            ('idle', 0): pygame.Rect(10, 10, 11, 30),
        }
        result = widget.get_removal_button_at_position((15, 20))
        assert result == ('idle', 0)

    def test_miss_returns_none(self):
        """Test returns None when no button is hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.removal_button_layouts = {
            ('idle', 0): pygame.Rect(10, 10, 11, 30),
        }
        result = widget.get_removal_button_at_position((9999, 9999))
        assert result is None


class TestCalculateLayoutSubMethods:
    """Test layout calculation sub-methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_calculate_sprocket_start_x(self):
        """Test _calculate_sprocket_start_x returns a valid x position."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        start_x = widget._calculate_sprocket_start_x()
        assert isinstance(start_x, int)
        assert start_x >= 0

    def test_calculate_frame_y_single_animation(self):
        """Test _calculate_frame_y centers frames for single animation."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        frame_y = widget._calculate_frame_y(20)
        assert isinstance(frame_y, int)

    def test_calculate_frame_y_multi_animation(self):
        """Test _calculate_frame_y for multi-animation widget."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        sprite.add_animation('walk', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)
        frame_y = widget._calculate_frame_y(40)
        expected_y = 40 + widget.animation_label_height + 3
        assert frame_y == expected_y

    def test_calculate_animation_layouts_no_sprite(self):
        """Test _calculate_animation_layouts with no sprite returns immediately."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._calculate_animation_layouts()
        assert len(widget.animation_layouts) == 0

    def test_calculate_frame_layouts_no_sprite(self):
        """Test _calculate_frame_layouts with no sprite returns immediately."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._calculate_frame_layouts()
        assert len(widget.frame_layouts) == 0

    def test_calculate_preview_layouts_no_sprite(self):
        """Test _calculate_preview_layouts with no sprite returns immediately."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._calculate_preview_layouts()
        assert len(widget.preview_rects) == 0

    def test_calculate_sprocket_layouts_no_sprite(self):
        """Test _calculate_sprocket_layouts with no sprite returns immediately."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._calculate_sprocket_layouts()
        assert len(widget.sprocket_layouts) == 0

    def test_calculate_sprocket_layouts_multi_animation(self):
        """Test _calculate_sprocket_layouts creates sprockets between animations."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        sprite.add_animation('walk', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)
        # Should have at least one sprocket between the two animations
        assert len(widget.sprocket_layouts) >= 1


class TestAddRemovalButton:
    """Test _add_removal_button method."""

    def test_creates_removal_button_layout(self):
        """Test _add_removal_button creates a removal button rect."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._add_removal_button('idle', 0, 50, 50)
        assert ('idle', 0) in widget.removal_button_layouts

    def test_initializes_layouts_dict_if_missing(self):
        """Test _add_removal_button initializes removal_button_layouts if absent."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        # Remove the attribute if it was already set
        if hasattr(widget, 'removal_button_layouts'):
            del widget.removal_button_layouts
        widget._add_removal_button('idle', 0, 50, 50)
        assert hasattr(widget, 'removal_button_layouts')
        assert ('idle', 0) in widget.removal_button_layouts


class TestUpdateHeightMultipleAnimations:
    """Test _update_height with boundary conditions."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_height_caps_at_five_animations(self):
        """Test height caps at 5 visible animations even with more."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        for i in range(7):
            sprite.add_animation(f'anim_{i}', [SpriteFrame(surface)])
        widget.animated_sprite = sprite
        widget._update_height()
        # Calculate expected height for 5 animations (the max)
        expected_height = (widget.animation_label_height + widget.frame_height + 20) * 5 + 20
        assert widget.rect is not None
        assert widget.rect.height == expected_height

    def test_update_height_with_parent_canvas(self, mocker):
        """Test _update_height updates parent canvas sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.animated_sprite = sprite
        mock_canvas = mocker.Mock()
        mock_canvas.film_strip_sprite.rect.width = 500
        widget.parent_canvas = mock_canvas
        widget._update_height()
        assert mock_canvas.film_strip_sprite.rect.height == widget.rect.height
        assert mock_canvas.film_strip_sprite.dirty == 1


class TestCreateFilmTabs:
    """Test _create_film_tabs method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_no_sprite_creates_no_tabs(self):
        """Test _create_film_tabs with no sprite creates no tabs."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._create_film_tabs()
        assert len(widget.film_tabs) == 0

    def test_no_current_animation_creates_no_tabs(self):
        """Test _create_film_tabs with missing animation creates no tabs."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        widget.current_animation = 'nonexistent'
        widget._create_film_tabs()
        assert len(widget.film_tabs) == 0

    def test_creates_tabs_for_frames(self):
        """Test _create_film_tabs creates tabs for available frames."""
        widget, _sprite = _make_widget_with_sprite(num_frames=2)
        widget._create_film_tabs()
        # Should have at least some tabs (before/after for each frame + bottom)
        assert len(widget.film_tabs) > 0


class TestDrawMultiControllerIndicatorsNew:
    """Test _draw_multi_controller_indicators_new method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_no_sprite_returns_early(self):
        """Test returns early with no animated sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((500, 200), pygame.SRCALPHA)
        widget._draw_multi_controller_indicators_new(surface)  # Should not raise

    def test_no_animation_returns_early(self):
        """Test returns early with empty current_animation."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.animated_sprite = AnimatedSprite()
        widget.current_animation = ''
        surface = pygame.Surface((500, 200), pygame.SRCALPHA)
        widget._draw_multi_controller_indicators_new(surface)  # Should not raise


class TestGetFrameImageForRendering:
    """Test _get_frame_image_for_rendering method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_returns_frame_image_when_available(self):
        """Test returns frame's image attribute when present."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface)
        result = widget._get_frame_image_for_rendering(frame, is_selected=False)
        assert result is surface

    def test_falls_back_to_get_frame_image(self, mocker):
        """Test falls back to _get_frame_image when image is None."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        frame = mocker.Mock()
        frame.image = None
        mocker.patch.object(
            FilmStripWidget,
            '_get_frame_image',
            return_value=None,
        )
        result = widget._get_frame_image_for_rendering(frame, is_selected=False)
        assert result is None
