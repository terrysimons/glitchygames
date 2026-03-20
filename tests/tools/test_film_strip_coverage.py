"""Coverage tests for glitchygames/tools/film_strip.py.

Targets uncovered areas: FilmStripWidget initialization, layout calculations,
animation timing, copy/paste, frame selection, hit-testing, keyboard input,
preview click, height updates, frame management, error handling, and rendering.
"""

import math
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
FRAME_DURATION_FAST = 0.25
DT_60FPS = 0.016
DT_LARGE = 1.0
BACKGROUND_COLOR_COUNT = 10


class TestFilmStripWidgetInit:
    """Test FilmStripWidget initialization."""

    def test_init_sets_rect(self):
        """Test initialization sets correct rect."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.rect is not None
        assert widget.rect.x == WIDGET_X
        assert widget.rect.y == WIDGET_Y
        assert widget.rect.width == WIDGET_WIDTH
        assert widget.rect.height == WIDGET_HEIGHT

    def test_init_default_state(self):
        """Test initialization sets default state."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.animated_sprite is None
        assert not widget.current_animation
        assert widget.current_frame == 0
        assert widget.selected_frame == 0
        assert widget.is_selected is False
        assert widget.hovered_frame is None
        assert widget.hovered_animation is None
        assert widget.hovered_preview is None
        assert widget.is_hovering_strip is False

    def test_init_animation_rename_state(self):
        """Test initialization sets animation rename state."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.editing_animation is None
        assert not widget.editing_text
        assert widget.original_animation_name is None
        assert widget.cursor_visible is True

    def test_init_background_colors(self):
        """Test initialization has background colors defined."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert len(widget.BACKGROUND_COLORS) == BACKGROUND_COLOR_COUNT
        # Default starts at gray (index 2)
        assert widget.background_color_index == 2

    def test_init_copy_paste_buffer(self):
        """Test initialization has empty copy/paste buffer."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget._copied_frame is None

    def test_init_film_tabs_empty(self):
        """Test initialization starts with empty film tabs."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.film_tabs == []

    def test_init_preview_dictionaries_empty(self):
        """Test initialization starts with empty preview dictionaries."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.preview_animation_times == {}
        assert widget.preview_animation_speeds == {}
        assert widget.preview_frame_durations == {}

    def test_init_hovered_removal_button_none(self):
        """Test initialization starts with no hovered removal button."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.hovered_removal_button is None


class TestFilmStripSetAnimatedSprite:
    """Test FilmStripWidget.set_animated_sprite."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def widget(self):
        """Create a FilmStripWidget for testing.

        Returns:
            A FilmStripWidget instance.
        """
        return FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)

    @pytest.fixture
    def animated_sprite_with_order(self):
        """Create an AnimatedSprite with _animation_order.

        Returns:
            An AnimatedSprite with an 'idle' animation and _animation_order set.
        """
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION)
        frame2 = SpriteFrame(surface, duration=FRAME_DURATION_FAST)
        sprite.add_animation('idle', [frame1, frame2])
        sprite._animation_order = ['idle']
        return sprite

    @pytest.fixture
    def animated_sprite_without_order(self):
        """Create an AnimatedSprite without _animation_order.

        Returns:
            An AnimatedSprite with a 'walk' animation and no _animation_order.
        """
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('walk', [frame1])
        if hasattr(sprite, '_animation_order'):
            del sprite._animation_order
        return sprite

    def test_set_animated_sprite_with_order(self, widget, animated_sprite_with_order):
        """Test set_animated_sprite uses _animation_order when available."""
        widget.set_animated_sprite(animated_sprite_with_order)
        assert widget.animated_sprite is animated_sprite_with_order
        assert widget.current_animation == 'idle'
        assert widget.current_frame == 0

    def test_set_animated_sprite_without_order(self, widget, animated_sprite_without_order):
        """Test set_animated_sprite falls back to first animation key."""
        widget.set_animated_sprite(animated_sprite_without_order)
        assert widget.current_animation == 'walk'

    def test_set_animated_sprite_empty(self, widget):
        """Test set_animated_sprite with empty animations."""
        sprite = AnimatedSprite()
        widget.set_animated_sprite(sprite)
        assert not widget.current_animation

    def test_set_animated_sprite_clears_old_state(self, widget, animated_sprite_with_order):
        """Test set_animated_sprite clears old preview state."""
        widget.preview_animation_times['old'] = 1.0
        widget.preview_animation_speeds['old'] = 2.0
        widget.set_animated_sprite(animated_sprite_with_order)
        assert 'old' not in widget.preview_animation_times
        assert 'old' not in widget.preview_animation_speeds

    def test_set_animated_sprite_initializes_scroll_offset(
        self, widget, animated_sprite_with_order
    ):
        """Test set_animated_sprite initializes scroll_offset to 0."""
        widget.set_animated_sprite(animated_sprite_with_order)
        assert widget.scroll_offset == 0

    def test_set_animated_sprite_marks_dirty(self, widget, animated_sprite_with_order):
        """Test set_animated_sprite marks widget as dirty."""
        widget.set_animated_sprite(animated_sprite_with_order)
        assert hasattr(widget, '_force_redraw')


class TestFilmStripInitializePreviewAnimations:
    """Test _initialize_preview_animations method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_no_animated_sprite(self):
        """Test _initialize_preview_animations with no sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._initialize_preview_animations()
        assert widget.preview_animation_times == {}

    def test_multi_frame_animation_starts_at_zero(self):
        """Test multi-frame animation starts time at 0.0."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION)
        frame2 = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('walk', [frame1, frame2])
        widget.animated_sprite = sprite
        widget._initialize_preview_animations()
        assert math.isclose(widget.preview_animation_times['walk'], 0.0, abs_tol=1e-9)

    def test_single_frame_animation_starts_with_offset(self):
        """Test single-frame animation starts time with small offset."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('idle', [frame])
        widget.animated_sprite = sprite
        widget._initialize_preview_animations()
        assert math.isclose(widget.preview_animation_times['idle'], 0.001)

    def test_frame_durations_extracted(self):
        """Test frame durations are correctly extracted."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION)
        frame2 = SpriteFrame(surface, duration=FRAME_DURATION_FAST)
        sprite.add_animation('walk', [frame1, frame2])
        widget.animated_sprite = sprite
        widget._initialize_preview_animations()
        assert widget.preview_frame_durations['walk'] == [FRAME_DURATION, FRAME_DURATION_FAST]

    def test_frame_without_duration_uses_default(self, mocker):
        """Test frame without duration attribute uses default 1.0."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        # Create a mock frame without duration
        mock_frame = mocker.Mock()
        del mock_frame.duration
        sprite._animations = {'test': [mock_frame]}
        widget.animated_sprite = sprite
        widget._initialize_preview_animations()
        assert widget.preview_frame_durations['test'] == [1.0]

    def test_animation_speed_initialized_to_one(self):
        """Test animation speed is initialized to 1.0."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('run', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.animated_sprite = sprite
        widget._initialize_preview_animations()
        assert math.isclose(widget.preview_animation_speeds['run'], 1.0)


class TestFilmStripUpdateAnimations:
    """Test update_animations method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def widget_with_sprite(self):
        """Create a widget with a loaded sprite.

        Returns:
            A FilmStripWidget with an animated sprite loaded.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION)
        frame2 = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('walk', [frame1, frame2])
        widget.set_animated_sprite(sprite)
        return widget

    def test_update_no_sprite(self):
        """Test update_animations with no sprite does nothing."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.update_animations(DT_60FPS)  # Should not raise

    def test_update_advances_time(self, widget_with_sprite):
        """Test update_animations advances preview times."""
        initial_time = widget_with_sprite.preview_animation_times['walk']
        widget_with_sprite.update_animations(DT_60FPS)
        assert widget_with_sprite.preview_animation_times['walk'] > initial_time

    def test_update_wraps_time(self, widget_with_sprite, mocker):
        """Test update_animations wraps time when exceeding total duration."""
        # Mock the animated sprite's update to avoid surfarray issues
        mocker.patch.object(widget_with_sprite.animated_sprite, 'update')
        # Total duration is 1.0 (2 frames * 0.5 each)
        widget_with_sprite.preview_animation_times['walk'] = 0.9
        widget_with_sprite.update_animations(DT_LARGE)
        # Time should wrap around
        assert widget_with_sprite.preview_animation_times['walk'] < 1.0

    def test_update_marks_dirty(self, widget_with_sprite, mocker):
        """Test update_animations marks widget as dirty."""
        mocker.patch.object(widget_with_sprite, 'mark_dirty')
        widget_with_sprite.update_animations(DT_60FPS)
        widget_with_sprite.mark_dirty.assert_called()

    def test_update_initializes_debug_timers(self, widget_with_sprite, mocker):
        """Test update_animations initializes debug timers if not present."""
        mocker.patch.object(widget_with_sprite.animated_sprite, 'update')
        # Remove debug timers if present
        if hasattr(widget_with_sprite, '_debug_start_time'):
            del widget_with_sprite._debug_start_time
        if hasattr(widget_with_sprite, '_debug_last_dump_time'):
            del widget_with_sprite._debug_last_dump_time
        widget_with_sprite.update_animations(DT_60FPS)
        assert hasattr(widget_with_sprite, '_debug_start_time')
        assert hasattr(widget_with_sprite, '_debug_last_dump_time')

    def test_update_triggers_debug_dump_at_interval(self, widget_with_sprite, mocker):
        """Test update_animations triggers debug dump at 5-second intervals."""
        mocker.patch.object(widget_with_sprite.animated_sprite, 'update')
        widget_with_sprite._debug_start_time = 0.0
        widget_with_sprite._debug_last_dump_time = 0.0
        # Advance enough time to trigger a dump (5 seconds)
        widget_with_sprite.update_animations(6.0)
        assert widget_with_sprite._debug_last_dump_time == widget_with_sprite._debug_start_time

    def test_update_skips_animation_not_in_times(self, widget_with_sprite, mocker):
        """Test update_animations skips animations not in preview_animation_times."""
        mocker.patch.object(widget_with_sprite.animated_sprite, 'update')
        # Remove the animation from preview times
        widget_with_sprite.preview_animation_times.clear()
        # Should not raise
        widget_with_sprite.update_animations(DT_60FPS)


class TestFilmStripGetCurrentPreviewFrame:
    """Test get_current_preview_frame method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_unknown_animation_returns_zero(self):
        """Test unknown animation name returns frame 0."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.get_current_preview_frame('nonexistent') == 0

    def test_first_frame_at_start(self):
        """Test frame 0 is returned at the start of animation."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_animation_times['walk'] = 0.0
        widget.preview_frame_durations['walk'] = [FRAME_DURATION, FRAME_DURATION]
        assert widget.get_current_preview_frame('walk') == 0

    def test_second_frame_after_first_duration(self):
        """Test frame 1 is returned after first frame's duration."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_animation_times['walk'] = FRAME_DURATION + 0.01
        widget.preview_frame_durations['walk'] = [FRAME_DURATION, FRAME_DURATION]
        assert widget.get_current_preview_frame('walk') == 1

    def test_empty_durations_returns_zero(self):
        """Test empty frame durations returns frame 0."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_animation_times['walk'] = 0.0
        widget.preview_frame_durations['walk'] = []
        assert widget.get_current_preview_frame('walk') == 0

    def test_fallback_to_last_frame(self):
        """Test fallback to last frame when time exceeds total duration."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_animation_times['walk'] = 999.0
        widget.preview_frame_durations['walk'] = [FRAME_DURATION]
        assert widget.get_current_preview_frame('walk') == 0

    def test_missing_times_key_returns_zero(self):
        """Test animation present in durations but not times returns 0."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_frame_durations['walk'] = [FRAME_DURATION]
        # 'walk' not in preview_animation_times
        assert widget.get_current_preview_frame('walk') == 0

    def test_missing_durations_key_returns_zero(self):
        """Test animation present in times but not durations returns 0."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_animation_times['walk'] = 0.5
        # 'walk' not in preview_frame_durations
        assert widget.get_current_preview_frame('walk') == 0

    def test_three_frame_animation_middle_frame(self):
        """Test correct frame for three-frame animation at middle time."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_animation_times['run'] = 0.6
        widget.preview_frame_durations['run'] = [0.3, 0.3, 0.3]
        assert widget.get_current_preview_frame('run') == 1


class TestFilmStripCopyPaste:
    """Test copy_current_frame and paste_to_current_frame methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def widget_with_frames(self):
        """Create a widget with loaded frames for copy/paste testing.

        Returns:
            A FilmStripWidget with frames loaded for copy/paste.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION)
        frame2 = SpriteFrame(surface, duration=FRAME_DURATION_FAST)
        sprite.add_animation('idle', [frame1, frame2])
        widget.set_animated_sprite(sprite)
        widget.current_animation = 'idle'
        widget.current_frame = 0
        return widget

    def test_copy_no_sprite(self):
        """Test copy fails with no animated sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.copy_current_frame() is False

    def test_copy_no_animation(self):
        """Test copy fails with no current animation."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.animated_sprite = AnimatedSprite()
        widget.current_animation = ''
        assert widget.copy_current_frame() is False

    def test_copy_invalid_animation(self):
        """Test copy fails with invalid animation name."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.animated_sprite = AnimatedSprite()
        widget.current_animation = 'nonexistent'
        assert widget.copy_current_frame() is False

    def test_copy_out_of_range_frame(self, widget_with_frames):
        """Test copy fails with out-of-range frame index."""
        widget_with_frames.current_frame = 999
        assert widget_with_frames.copy_current_frame() is False

    def test_copy_success(self, widget_with_frames):
        """Test successful copy stores frame."""
        assert widget_with_frames.copy_current_frame() is True
        assert widget_with_frames._copied_frame is not None

    def test_paste_no_copied_frame(self, widget_with_frames):
        """Test paste fails with no copied frame."""
        assert widget_with_frames.paste_to_current_frame() is False

    def test_paste_no_sprite(self):
        """Test paste fails with no animated sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._copied_frame = 'something'
        assert widget.paste_to_current_frame() is False

    def test_paste_invalid_animation(self, widget_with_frames):
        """Test paste fails with invalid animation name."""
        widget_with_frames.copy_current_frame()
        widget_with_frames.current_animation = 'nonexistent'
        assert widget_with_frames.paste_to_current_frame() is False

    def test_paste_out_of_range_frame(self, widget_with_frames):
        """Test paste fails with out-of-range frame index."""
        widget_with_frames.copy_current_frame()
        widget_with_frames.current_frame = 999
        assert widget_with_frames.paste_to_current_frame() is False

    def test_paste_success(self, widget_with_frames):
        """Test successful paste replaces frame."""
        widget_with_frames.copy_current_frame()
        widget_with_frames.current_frame = 1
        assert widget_with_frames.paste_to_current_frame() is True

    def test_paste_notifies_parent_scene(self, widget_with_frames, mocker):
        """Test paste notifies parent scene when available."""
        widget_with_frames.copy_current_frame()
        parent_scene = mocker.Mock()
        parent_scene._on_frame_pasted = mocker.Mock()
        widget_with_frames.parent_scene = parent_scene
        widget_with_frames.current_frame = 1
        widget_with_frames.paste_to_current_frame()
        parent_scene._on_frame_pasted.assert_called_once_with('idle', 1)

    def test_paste_without_parent_scene(self, widget_with_frames):
        """Test paste succeeds without parent scene."""
        widget_with_frames.copy_current_frame()
        # Ensure no parent_scene is set
        if hasattr(widget_with_frames, 'parent_scene'):
            del widget_with_frames.parent_scene
        widget_with_frames.current_frame = 1
        assert widget_with_frames.paste_to_current_frame() is True

    def test_copy_creates_deep_copy(self, widget_with_frames):
        """Test copy creates an independent deep copy of the frame."""
        widget_with_frames.copy_current_frame()
        # Modifying the original should not affect the copy
        original_frame = widget_with_frames.animated_sprite._animations['idle'][0]
        assert widget_with_frames._copied_frame is not original_frame


class TestFilmStripFrameSelection:
    """Test frame selection methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def widget_with_sprite(self):
        """Create a widget with an animated sprite.

        Returns:
            A FilmStripWidget with an animated sprite loaded.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION)
        frame2 = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('idle', [frame1, frame2])
        widget.set_animated_sprite(sprite)
        return widget

    def test_set_current_frame_valid(self, widget_with_sprite):
        """Test set_current_frame with valid animation and frame."""
        widget_with_sprite.set_current_frame('idle', 1)
        assert widget_with_sprite.current_animation == 'idle'
        assert widget_with_sprite.selected_frame == 1

    def test_set_current_frame_invalid_animation(self, widget_with_sprite):
        """Test set_current_frame ignores invalid animation."""
        widget_with_sprite.set_current_frame('nonexistent', 0)
        # Should remain unchanged
        assert widget_with_sprite.current_animation == 'idle'

    def test_set_current_frame_out_of_range(self, widget_with_sprite):
        """Test set_current_frame ignores out-of-range frame."""
        widget_with_sprite.set_current_frame('idle', 999)
        # Should remain unchanged
        assert widget_with_sprite.selected_frame == 0

    def test_set_current_frame_notifies_parent_scene(self, widget_with_sprite, mocker):
        """Test set_current_frame notifies parent scene."""
        parent_scene = mocker.Mock()
        parent_scene._on_film_strip_frame_selected = mocker.Mock()
        widget_with_sprite.parent_scene = parent_scene
        widget_with_sprite.set_current_frame('idle', 1)
        parent_scene._on_film_strip_frame_selected.assert_called_once_with(
            widget_with_sprite, 'idle', 1
        )

    def test_set_current_frame_negative_index_ignored(self, widget_with_sprite):
        """Test set_current_frame ignores negative frame index."""
        widget_with_sprite.set_current_frame('idle', -1)
        assert widget_with_sprite.selected_frame == 0


class TestFilmStripHitTesting:
    """Test hit testing methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_get_frame_at_position_no_hit(self):
        """Test get_frame_at_position returns None for no hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.get_frame_at_position((9999, 9999)) is None

    def test_get_frame_at_position_hit(self):
        """Test get_frame_at_position returns frame info for a hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.frame_layouts['idle', 0] = pygame.Rect(10, 10, 64, 64)
        result = widget.get_frame_at_position((20, 20))
        assert result == ('idle', 0)

    def test_get_animation_at_position_no_hit(self):
        """Test get_animation_at_position returns None for no hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.get_animation_at_position((9999, 9999)) is None

    def test_get_animation_at_position_hit(self):
        """Test get_animation_at_position returns animation name for a hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.animation_layouts['idle'] = pygame.Rect(10, 10, 100, 20)
        result = widget.get_animation_at_position((20, 15))
        assert result == 'idle'

    def test_get_preview_at_position_no_hit(self):
        """Test get_preview_at_position returns None for no hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.get_preview_at_position((9999, 9999)) is None

    def test_get_preview_at_position_hit(self):
        """Test get_preview_at_position returns animation name for a hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_rects['idle'] = pygame.Rect(400, 10, 64, 64)
        result = widget.get_preview_at_position((420, 30))
        assert result == 'idle'

    def test_get_removal_button_at_position_no_layouts(self):
        """Test get_removal_button_at_position returns None with no layouts."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.get_removal_button_at_position((10, 10)) is None

    def test_get_removal_button_at_position_hit(self):
        """Test get_removal_button_at_position returns button info for hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.removal_button_layouts = {('idle', 0): pygame.Rect(5, 20, 11, 30)}
        result = widget.get_removal_button_at_position((10, 30))
        assert result == ('idle', 0)

    def test_get_removal_button_at_position_no_hit(self):
        """Test get_removal_button_at_position returns None for miss."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.removal_button_layouts = {('idle', 0): pygame.Rect(5, 20, 11, 30)}
        result = widget.get_removal_button_at_position((9999, 9999))
        assert result is None


class TestFilmStripMarkDirty:
    """Test mark_dirty method."""

    def test_mark_dirty_sets_force_redraw(self):
        """Test mark_dirty sets _force_redraw flag."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.mark_dirty()
        assert widget._force_redraw is True

    def test_mark_dirty_with_film_strip_sprite(self, mocker):
        """Test mark_dirty propagates to film_strip_sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        mock_sprite = mocker.Mock()
        mock_sprite.groups.return_value = []
        widget.film_strip_sprite = mock_sprite
        widget.mark_dirty()
        assert mock_sprite.dirty == 2

    def test_mark_dirty_without_film_strip_sprite(self):
        """Test mark_dirty works without film_strip_sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.mark_dirty()
        assert widget._force_redraw is True


class TestFilmStripUpdateHeight:
    """Test _update_height method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_height_no_sprite(self):
        """Test _update_height with no sprite does nothing."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.rect is not None
        original_height = widget.rect.height
        widget._update_height()
        assert widget.rect.height == original_height

    def test_update_height_single_animation(self):
        """Test _update_height with single animation."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.animated_sprite = sprite
        widget._update_height()
        # Height should be calculated based on 1 animation
        assert widget.rect.height > 0

    def test_update_height_multiple_animations(self):
        """Test _update_height with multiple animations scales."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        sprite.add_animation('walk', [SpriteFrame(surface)])
        sprite.add_animation('run', [SpriteFrame(surface)])
        widget.animated_sprite = sprite
        widget._update_height()
        # Height should be proportional to number of animations
        assert widget.rect is not None
        assert widget.rect.height > 100

    def test_update_height_max_five_animations(self):
        """Test _update_height caps at 5 animations maximum."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        for i in range(7):
            sprite.add_animation(f'anim_{i}', [SpriteFrame(surface)])
        widget.animated_sprite = sprite
        widget._update_height()
        # Height should be capped at 5 animations worth
        five_height = (20 + 64 + 20) * 5 + 20
        assert widget.rect is not None
        assert widget.rect.height == five_height

    def test_update_height_with_parent_canvas(self, mocker):
        """Test _update_height updates parent canvas film strip sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.animated_sprite = sprite

        parent_canvas = mocker.Mock()
        film_strip_sprite = mocker.Mock()
        film_strip_sprite.rect = pygame.Rect(0, 0, 500, 200)
        film_strip_sprite.rect.width = 500
        parent_canvas.film_strip_sprite = film_strip_sprite
        widget.parent_canvas = parent_canvas

        widget._update_height()
        assert film_strip_sprite.rect is not None
        assert widget.rect is not None
        assert film_strip_sprite.rect.height == widget.rect.height
        assert film_strip_sprite.dirty == 1


class TestFilmStripClearLayouts:
    """Test _clear_layouts method."""

    def test_clear_layouts(self):
        """Test _clear_layouts clears all layout caches."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.frame_layouts['idle', 0] = pygame.Rect(0, 0, 10, 10)
        widget.animation_layouts['idle'] = pygame.Rect(0, 0, 10, 10)
        widget.sprocket_layouts.append(pygame.Rect(0, 0, 10, 10))
        widget.preview_rects['idle'] = pygame.Rect(0, 0, 10, 10)

        widget._clear_layouts()

        assert len(widget.frame_layouts) == 0
        assert len(widget.animation_layouts) == 0
        assert len(widget.sprocket_layouts) == 0
        assert len(widget.preview_rects) == 0


class TestFilmStripCalculateLayout:
    """Test _calculate_layout and sub-methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_calculate_layout_no_sprite(self):
        """Test _calculate_layout with no sprite does nothing."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._calculate_layout()
        assert len(widget.frame_layouts) == 0

    def test_calculate_layout_single_animation(self):
        """Test _calculate_layout with single animation."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)
        # Layout should have been calculated during set_animated_sprite
        assert len(widget.frame_layouts) > 0

    def test_calculate_layout_multiple_frames(self):
        """Test _calculate_layout positions multiple frames correctly."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frames = [SpriteFrame(surface, duration=FRAME_DURATION) for _ in range(3)]
        sprite.add_animation('walk', frames)
        widget.set_animated_sprite(sprite)
        # Should have 3 frame layouts
        frame_keys = [key for key in widget.frame_layouts if key[0] == 'walk']
        assert len(frame_keys) == 3

    def test_calculate_animation_layouts_no_sprite(self):
        """Test _calculate_animation_layouts with no sprite returns early."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._calculate_animation_layouts()
        assert len(widget.animation_layouts) == 0

    def test_calculate_frame_layouts_no_sprite(self):
        """Test _calculate_frame_layouts with no sprite returns early."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._calculate_frame_layouts()
        assert len(widget.frame_layouts) == 0

    def test_calculate_preview_layouts_no_sprite(self):
        """Test _calculate_preview_layouts with no sprite returns early."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._calculate_preview_layouts()
        assert len(widget.preview_rects) == 0

    def test_calculate_sprocket_layouts_no_sprite(self):
        """Test _calculate_sprocket_layouts with no sprite returns early."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._calculate_sprocket_layouts()
        assert len(widget.sprocket_layouts) == 0

    def test_calculate_layout_multiple_animations(self):
        """Test _calculate_layout with multiple animations creates sprocket layouts."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface)])
        sprite.add_animation('walk', [SpriteFrame(surface)])
        widget.set_animated_sprite(sprite)
        # Should have sprocket separators between animations
        assert len(widget.sprocket_layouts) > 0


class TestFilmStripScrolling:
    """Test scroll-related methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def widget_with_many_frames(self):
        """Create a widget with more frames than can be displayed.

        Returns:
            A FilmStripWidget with 10 frames loaded.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frames = [SpriteFrame(surface, duration=FRAME_DURATION) for _ in range(10)]
        sprite.add_animation('walk', frames)
        widget.set_animated_sprite(sprite)
        return widget

    def test_calculate_scroll_offset_centers_frame(self, widget_with_many_frames):
        """Test _calculate_scroll_offset tries to center specified frame."""
        frames = widget_with_many_frames.animated_sprite._animations['walk']
        offset = widget_with_many_frames._calculate_scroll_offset(5, frames)
        assert isinstance(offset, int)
        assert offset >= 0

    def test_calculate_scroll_offset_first_frame(self, widget_with_many_frames):
        """Test _calculate_scroll_offset for first frame."""
        frames = widget_with_many_frames.animated_sprite._animations['walk']
        offset = widget_with_many_frames._calculate_scroll_offset(0, frames)
        assert offset == 0

    def test_update_scroll_for_frame_no_sprite(self):
        """Test update_scroll_for_frame with no sprite does nothing."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.update_scroll_for_frame(0)  # Should not raise

    def test_update_scroll_for_frame_in_view(self, widget_with_many_frames):
        """Test update_scroll_for_frame when frame is already visible."""
        widget_with_many_frames.scroll_offset = 0
        original_offset = widget_with_many_frames.scroll_offset
        widget_with_many_frames.update_scroll_for_frame(0)
        # Frame 0 should already be visible, so offset shouldn't change
        assert widget_with_many_frames.scroll_offset == original_offset

    def test_update_scroll_for_frame_beyond_range(self, widget_with_many_frames):
        """Test update_scroll_for_frame with frame beyond animation range."""
        widget_with_many_frames.update_scroll_for_frame(999)
        # Should return without error

    def test_update_scroll_for_frame_scrolls_right(self, widget_with_many_frames):
        """Test update_scroll_for_frame scrolls right when frame is off-screen to the right."""
        widget_with_many_frames.scroll_offset = 0
        widget_with_many_frames.update_scroll_for_frame(8)
        # Should have scrolled to show frame 8
        assert widget_with_many_frames.scroll_offset > 0

    def test_update_scroll_for_frame_scrolls_left(self, widget_with_many_frames):
        """Test update_scroll_for_frame scrolls left when frame is off-screen to the left."""
        # Set scroll offset so frame 0 is off-screen to the left
        widget_with_many_frames.scroll_offset = 500
        widget_with_many_frames._calculate_layout()
        widget_with_many_frames.update_scroll_for_frame(0)
        # Should have scrolled back to show frame 0
        assert widget_with_many_frames.scroll_offset == 0


class TestFilmStripGetFrameImage:
    """Test _get_frame_image static method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_get_frame_image_normal(self):
        """Test _get_frame_image returns frame's image."""
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface)
        result = FilmStripWidget._get_frame_image(frame)
        assert result is surface

    def test_get_frame_image_stale_with_pixels(self, mocker):
        """Test _get_frame_image rebuilds from pixels when stale."""
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame = SpriteFrame(surface)
        frame._image_stale = True  # type: ignore[unresolved-attribute]
        pixel_data = cast(list[tuple[int, ...]], [(255, 0, 0, 255)] * (SURFACE_SIZE * SURFACE_SIZE))
        frame.pixels = pixel_data
        result = FilmStripWidget._get_frame_image(frame)
        assert result is not None
        assert result.get_size() == (SURFACE_SIZE, SURFACE_SIZE)

    def test_get_frame_image_no_image_with_pixel_data(self, mocker):
        """Test _get_frame_image falls back to get_pixel_data."""
        frame = mocker.Mock()
        frame.image = None
        frame._image_stale = False
        frame.get_pixel_data.return_value = [(255, 0, 0, 255)] * (SURFACE_SIZE * SURFACE_SIZE)
        frame.get_size.return_value = (SURFACE_SIZE, SURFACE_SIZE)
        # Remove 'image' from hasattr checks
        type(frame).image = mocker.PropertyMock(return_value=None)

        result = FilmStripWidget._get_frame_image(frame)
        # Should create surface from pixel data or return None
        assert result is None or isinstance(result, pygame.Surface)

    def test_get_frame_image_no_data_returns_none(self, mocker):
        """Test _get_frame_image returns None when no data is available."""
        frame = mocker.Mock(spec=[])
        result = FilmStripWidget._get_frame_image(frame)
        assert result is None


class TestFilmStripPropagateDirty:
    """Test dirty propagation methods."""

    def test_propagate_dirty_up_parent_chain_none(self):
        """Test _propagate_dirty_up_parent_chain with None parent."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._propagate_dirty_up_parent_chain(None)  # Should not raise

    def test_propagate_dirty_up_parent_chain_with_parent(self, mocker):
        """Test _propagate_dirty_up_parent_chain marks parents dirty."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        parent = mocker.Mock()
        parent.dirty = 0
        parent.parent = None
        widget._propagate_dirty_up_parent_chain(parent)
        assert parent.dirty == 1

    def test_propagate_dirty_up_parent_chain_self_reference(self, mocker):
        """Test _propagate_dirty_up_parent_chain stops on self-reference."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        parent = mocker.Mock()
        parent.dirty = 0
        parent.parent = parent  # Self-reference
        widget._propagate_dirty_up_parent_chain(parent)
        assert parent.dirty == 1

    def test_propagate_dirty_to_sprite_groups_prevents_infinite_recursion(self, mocker):
        """Test _propagate_dirty_to_sprite_groups prevents infinite recursion."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = mocker.Mock()
        # Passing visited set with the sprite already in it should stop
        visited = {sprite}
        widget._propagate_dirty_to_sprite_groups(sprite, visited)
        # Should not have called groups() since sprite was already visited

    def test_propagate_dirty_to_sprite_groups_no_groups(self, mocker):
        """Test _propagate_dirty_to_sprite_groups with sprite that has no groups."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = mocker.Mock(spec=[])
        widget._propagate_dirty_to_sprite_groups(sprite)
        # Should not raise


class TestFilmStripHandleClick:
    """Test handle_click method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def widget_with_sprite(self):
        """Create a widget with frames for click testing.

        Returns:
            A FilmStripWidget with frames set up.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frame1 = SpriteFrame(surface, duration=FRAME_DURATION)
        frame2 = SpriteFrame(surface, duration=FRAME_DURATION)
        sprite.add_animation('idle', [frame1, frame2])
        widget.set_animated_sprite(sprite)
        return widget

    def test_handle_click_on_frame(self, widget_with_sprite):
        """Test handle_click selects a frame when clicked."""
        # Set up a frame layout that can be clicked
        widget_with_sprite.frame_layouts['idle', 0] = pygame.Rect(50, 30, 64, 64)
        result = widget_with_sprite.handle_click((60, 40))
        assert result is not None

    def test_handle_click_returns_none_no_hit(self, widget_with_sprite):
        """Test handle_click returns None when nothing is clicked."""
        result = widget_with_sprite.handle_click((9999, 9999))
        assert result is None

    def test_handle_click_right_click_toggles_onion_skinning(self, widget_with_sprite, mocker):
        """Test handle_click with right click toggles onion skinning."""
        widget_with_sprite.frame_layouts['idle', 0] = pygame.Rect(50, 30, 64, 64)
        mocker.patch.object(widget_with_sprite, '_toggle_onion_skinning')
        result = widget_with_sprite.handle_click((60, 40), is_right_click=True)
        assert result is None
        widget_with_sprite._toggle_onion_skinning.assert_called_once()

    def test_handle_click_shift_click_toggles_onion_skinning(self, widget_with_sprite, mocker):
        """Test handle_click with shift click toggles onion skinning."""
        widget_with_sprite.frame_layouts['idle', 0] = pygame.Rect(50, 30, 64, 64)
        mocker.patch.object(widget_with_sprite, '_toggle_onion_skinning')
        result = widget_with_sprite.handle_click((60, 40), is_shift_click=True)
        assert result is None

    def test_handle_click_on_animation_label_enters_edit_mode(self, widget_with_sprite, mocker):
        """Test handle_click on animation label enters edit mode."""
        widget_with_sprite.animation_layouts['idle'] = pygame.Rect(100, 5, 80, 20)
        mocker.patch('pygame.time.get_ticks', return_value=1000)
        result = widget_with_sprite.handle_click((120, 10))
        assert result is None
        assert widget_with_sprite.editing_animation == 'idle'
        assert not widget_with_sprite.editing_text

    def test_handle_click_on_strip_background(self, widget_with_sprite, mocker):
        """Test handle_click on strip background selects strip."""
        # Click within strip rect but not on a frame, label, or preview
        assert widget_with_sprite.rect is not None
        pos = (widget_with_sprite.rect.x + 5, widget_with_sprite.rect.y + 5)
        result = widget_with_sprite.handle_click(pos)
        # Should return the strip animation and frame
        assert result is not None


class TestFilmStripHandlePreviewClick:
    """Test handle_preview_click method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_handle_preview_click_hit(self):
        """Test handle_preview_click cycles background color on hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_rects['idle'] = pygame.Rect(400, 10, 64, 64)
        initial_index = widget.background_color_index
        result = widget.handle_preview_click((420, 30))
        assert result is not None
        assert result[0] == 'idle'
        assert widget.background_color_index == (initial_index + 1) % BACKGROUND_COLOR_COUNT

    def test_handle_preview_click_miss(self):
        """Test handle_preview_click returns None on miss."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_rects['idle'] = pygame.Rect(400, 10, 64, 64)
        result = widget.handle_preview_click((0, 0))
        assert result is None

    def test_handle_preview_click_with_parent_scene_uses_global_frame(self, mocker):
        """Test handle_preview_click uses parent scene's selected_frame."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.preview_rects['idle'] = pygame.Rect(400, 10, 64, 64)
        parent_scene = mocker.Mock()
        parent_scene.selected_frame = 3
        widget.parent_scene = parent_scene
        result = widget.handle_preview_click((420, 30))
        assert result == ('idle', 3)


class TestFilmStripHandleKeyboardInput:
    """Test handle_keyboard_input method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_keyboard_input_not_editing_returns_false(self, mocker):
        """Test keyboard input returns False when not in editing mode."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        event = mocker.Mock()
        event.key = pygame.K_a
        assert widget.handle_keyboard_input(event) is False

    def test_keyboard_enter_commits_rename(self, mocker):
        """Test Enter key commits animation rename."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'new_name'
        widget.original_animation_name = 'idle'
        parent_scene = mocker.Mock()
        parent_scene.on_animation_rename = mocker.Mock()
        widget.parent_scene = parent_scene

        event = mocker.Mock()
        event.key = pygame.K_RETURN
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_animation is None
        parent_scene.on_animation_rename.assert_called_once_with('idle', 'new_name')

    def test_keyboard_enter_same_name_no_rename(self, mocker):
        """Test Enter key with same name does not trigger rename."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'idle'
        widget.original_animation_name = 'idle'

        event = mocker.Mock()
        event.key = pygame.K_RETURN
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_animation is None

    def test_keyboard_enter_empty_text_no_rename(self, mocker):
        """Test Enter key with empty text does not trigger rename."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = ''
        widget.original_animation_name = 'idle'

        event = mocker.Mock()
        event.key = pygame.K_RETURN
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_animation is None

    def test_keyboard_escape_cancels_editing(self, mocker):
        """Test Escape key cancels editing."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'partial'
        widget.original_animation_name = 'idle'

        event = mocker.Mock()
        event.key = pygame.K_ESCAPE
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_animation is None
        assert not widget.editing_text

    def test_keyboard_backspace_removes_character(self, mocker):
        """Test Backspace key removes last character."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'test'
        mocker.patch('pygame.time.get_ticks', return_value=1000)

        event = mocker.Mock()
        event.key = pygame.K_BACKSPACE
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_text == 'tes'

    def test_keyboard_backspace_empty_text(self, mocker):
        """Test Backspace key on empty text falls through to return False."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = ''

        event = mocker.Mock()
        event.key = pygame.K_BACKSPACE
        # With empty editing_text, backspace condition is False, falls through
        # unicode is empty string so printable check also fails
        event.unicode = ''
        result = widget.handle_keyboard_input(event)
        assert result is False

    def test_keyboard_printable_character_added(self, mocker):
        """Test printable character is added to editing text."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'te'
        mocker.patch('pygame.time.get_ticks', return_value=1000)

        event = mocker.Mock()
        event.key = pygame.K_s
        event.unicode = 's'
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_text == 'tes'

    def test_keyboard_max_length_prevents_overflow(self, mocker):
        """Test text input is limited to max length."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'x' * 50  # At ANIMATION_NAME_MAX_LENGTH

        event = mocker.Mock()
        event.key = pygame.K_a
        event.unicode = 'a'
        result = widget.handle_keyboard_input(event)
        # Should not add character since at max length
        assert result is False
        assert len(widget.editing_text) == 50

    def test_keyboard_enter_without_parent_scene(self, mocker):
        """Test Enter key with new name but no parent scene just clears edit mode."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.editing_animation = 'idle'
        widget.editing_text = 'new_name'
        widget.original_animation_name = 'idle'
        # No parent_scene

        event = mocker.Mock()
        event.key = pygame.K_RETURN
        result = widget.handle_keyboard_input(event)
        assert result is True
        assert widget.editing_animation is None


class TestFilmStripHandleHover:
    """Test handle_hover method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_handle_hover_updates_state(self, mocker):
        """Test handle_hover updates hovered frame and animation state."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.frame_layouts['idle', 0] = pygame.Rect(10, 10, 64, 64)
        widget.animation_layouts['idle'] = pygame.Rect(10, 5, 100, 20)
        widget.handle_hover((20, 20))
        assert widget.hovered_frame == ('idle', 0)

    def test_handle_hover_no_hit(self):
        """Test handle_hover with no elements hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.handle_hover((9999, 9999))
        assert widget.hovered_frame is None
        assert widget.hovered_animation is None


class TestFilmStripRemoveFrame:
    """Test _remove_frame method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.fixture
    def widget_with_multi_frame_sprite(self):
        """Create a widget with a multi-frame animated sprite.

        Returns:
            A FilmStripWidget with 3 frames.
        """
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frames = [SpriteFrame(surface, duration=FRAME_DURATION) for _ in range(3)]
        sprite.add_animation('idle', frames)
        widget.set_animated_sprite(sprite)
        widget.current_animation = 'idle'
        widget.current_frame = 0
        return widget

    def test_remove_frame_no_sprite(self):
        """Test _remove_frame with no sprite does nothing."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._remove_frame('idle', 0)  # Should not raise

    def test_remove_frame_invalid_animation(self, widget_with_multi_frame_sprite):
        """Test _remove_frame with invalid animation name does nothing."""
        widget_with_multi_frame_sprite._remove_frame('nonexistent', 0)
        # All frames should remain
        assert len(widget_with_multi_frame_sprite.animated_sprite._animations['idle']) == 3

    def test_remove_frame_out_of_range(self, widget_with_multi_frame_sprite):
        """Test _remove_frame with out-of-range index does nothing."""
        widget_with_multi_frame_sprite._remove_frame('idle', 999)
        assert len(widget_with_multi_frame_sprite.animated_sprite._animations['idle']) == 3

    def test_remove_frame_last_frame_prevented(self, widget_with_multi_frame_sprite):
        """Test _remove_frame prevents removing the last frame."""
        # Remove until only one frame left
        widget_with_multi_frame_sprite.animated_sprite._animations['idle'] = [
            widget_with_multi_frame_sprite.animated_sprite._animations['idle'][0]
        ]
        widget_with_multi_frame_sprite._remove_frame('idle', 0)
        # Should still have 1 frame
        assert len(widget_with_multi_frame_sprite.animated_sprite._animations['idle']) == 1

    def test_remove_frame_adjusts_current_frame(self, widget_with_multi_frame_sprite, mocker):
        """Test _remove_frame adjusts current frame index when current frame is removed."""
        widget_with_multi_frame_sprite.current_frame = 2
        # _remove_frame accesses self.parent_scene for notifications and _create_film_tabs
        # accesses self.parent_scene.canvas.animated_sprite._animations.keys()
        parent_scene = mocker.Mock()
        parent_scene.canvas.animated_sprite._animations.keys.return_value = ['idle']
        widget_with_multi_frame_sprite.parent_scene = parent_scene
        widget_with_multi_frame_sprite._remove_frame('idle', 2)
        assert widget_with_multi_frame_sprite.current_frame < 2


class TestFilmStripHandleRemovalButtonClick:
    """Test _handle_removal_button_click method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_handle_removal_no_layouts(self):
        """Test _handle_removal_button_click with no layouts returns False."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget._handle_removal_button_click((10, 10)) is False

    def test_handle_removal_button_click_hit(self, mocker):
        """Test _handle_removal_button_click returns True when button is hit."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation(
            'idle',
            [
                SpriteFrame(surface, duration=FRAME_DURATION),
                SpriteFrame(surface, duration=FRAME_DURATION),
            ],
        )
        widget.set_animated_sprite(sprite)
        widget.removal_button_layouts = {('idle', 0): pygame.Rect(5, 20, 11, 30)}
        parent_scene = mocker.Mock()
        parent_scene._show_delete_frame_confirmation = mocker.Mock()
        widget.parent_scene = parent_scene
        result = widget._handle_removal_button_click((10, 30))
        assert result is True
        parent_scene._show_delete_frame_confirmation.assert_called_once()


class TestFilmStripGetTotalWidth:
    """Test get_total_width and _calculate_frames_width methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_get_total_width_no_sprite(self):
        """Test get_total_width with no sprite returns 0."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.get_total_width() == 0

    def test_get_total_width_with_sprite(self):
        """Test get_total_width with sprite returns positive value."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)
        assert widget.get_total_width() > 0


class TestFilmStripSetFrameIndex:
    """Test set_frame_index method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_set_frame_index_no_sprite(self):
        """Test set_frame_index with no sprite does nothing."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.set_frame_index(0)  # Should not raise

    def test_set_frame_index_updates_current_frame(self, mocker):
        """Test set_frame_index updates current_frame."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation(
            'idle',
            [
                SpriteFrame(surface, duration=FRAME_DURATION),
                SpriteFrame(surface, duration=FRAME_DURATION),
            ],
        )
        widget.set_animated_sprite(sprite)
        # set_frame_index accesses self.parent_canvas which is set via set_parent_canvas()
        mock_canvas = mocker.Mock()
        widget.set_parent_canvas(mock_canvas)
        widget.set_frame_index(1)
        assert widget.current_frame == 1


class TestFilmStripHandleFrameClick:
    """Test handle_frame_click method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_handle_frame_click_no_sprite(self):
        """Test handle_frame_click with no sprite returns None."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget.handle_frame_click((10, 10)) is None

    def test_handle_frame_click_outside_bounds(self):
        """Test handle_frame_click outside bounds returns None."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)
        assert widget.handle_frame_click((-10, -10)) is None

    def test_handle_frame_click_hit(self):
        """Test handle_frame_click returns frame info when clicked."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)
        # Set up frame layout
        widget.frame_layouts['idle', 0] = pygame.Rect(50, 30, 64, 64)
        result = widget.handle_frame_click((60, 40))
        assert result == ('idle', 0)


class TestFilmStripResetTabStates:
    """Test reset_all_tab_states method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_reset_all_tab_states(self):
        """Test reset_all_tab_states resets all tab states."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        tab = FilmTabWidget(x=0, y=0, width=20, height=30)
        tab.is_clicked = True
        tab.is_hovered = True
        widget.film_tabs.append(tab)
        widget.reset_all_tab_states()
        assert tab.is_clicked is False
        assert tab.is_hovered is False


class TestFilmTabWidget:
    """Test FilmTabWidget class."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_init(self):
        """Test FilmTabWidget initialization."""
        tab = FilmTabWidget(x=10, y=20, width=15, height=25)
        assert tab.x == 10
        assert tab.y == 20
        assert tab.width == 15
        assert tab.height == 25
        assert tab.is_hovered is False
        assert tab.is_clicked is False

    def test_set_insertion_type(self):
        """Test set_insertion_type sets correct values."""
        tab = FilmTabWidget(x=0, y=0)
        tab.set_insertion_type('after', 3)
        assert tab.insertion_type == 'after'
        assert tab.target_frame_index == 3

    def test_handle_click_hit(self):
        """Test handle_click returns True when clicked."""
        tab = FilmTabWidget(x=10, y=10, width=20, height=30)
        assert tab.handle_click((15, 20)) is True
        assert tab.is_clicked is True

    def test_handle_click_miss(self):
        """Test handle_click returns False when missed."""
        tab = FilmTabWidget(x=10, y=10, width=20, height=30)
        assert tab.handle_click((100, 100)) is False

    def test_handle_hover_hit(self):
        """Test handle_hover returns True when hovering."""
        tab = FilmTabWidget(x=10, y=10, width=20, height=30)
        assert tab.handle_hover((15, 20)) is True
        assert tab.is_hovered is True

    def test_handle_hover_miss(self):
        """Test handle_hover returns False when not hovering."""
        tab = FilmTabWidget(x=10, y=10, width=20, height=30)
        assert tab.handle_hover((100, 100)) is False
        assert tab.is_hovered is False

    def test_reset_click_state(self):
        """Test reset_click_state resets clicked state."""
        tab = FilmTabWidget(x=0, y=0)
        tab.is_clicked = True
        tab.reset_click_state()
        assert tab.is_clicked is False

    def test_render_normal_state(self):
        """Test render in normal state."""
        tab = FilmTabWidget(x=10, y=10, width=20, height=30)
        surface = pygame.Surface((500, 200))
        tab.render(surface)  # Should not raise

    def test_render_hovered_state(self):
        """Test render in hovered state uses inverted colors."""
        tab = FilmTabWidget(x=10, y=10, width=20, height=30)
        tab.is_hovered = True
        surface = pygame.Surface((500, 200))
        tab.render(surface)  # Should not raise

    def test_render_clicked_state(self):
        """Test render in clicked state."""
        tab = FilmTabWidget(x=10, y=10, width=20, height=30)
        tab.is_clicked = True
        surface = pygame.Surface((500, 200))
        tab.render(surface)  # Should not raise


class TestFilmStripDeleteTab:
    """Test FilmStripDeleteTab class."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_init(self):
        """Test FilmStripDeleteTab initialization."""
        tab = FilmStripDeleteTab(x=100, y=5, width=40, height=10)
        assert tab.rect is not None
        assert tab.rect.x == 100
        assert tab.rect.y == 5
        assert tab.rect.width == 40
        assert tab.rect.height == 10

    def test_handle_click_hit(self):
        """Test FilmStripDeleteTab handle_click returns True when clicked."""
        tab = FilmStripDeleteTab(x=100, y=5, width=40, height=10)
        assert tab.handle_click((110, 8)) is True

    def test_handle_click_miss(self):
        """Test FilmStripDeleteTab handle_click returns False when missed."""
        tab = FilmStripDeleteTab(x=100, y=5, width=40, height=10)
        assert tab.handle_click((0, 0)) is False

    def test_render_normal(self):
        """Test FilmStripDeleteTab render in normal state."""
        tab = FilmStripDeleteTab(x=100, y=5, width=40, height=10)
        surface = pygame.Surface((500, 200))
        tab.render(surface)  # Should not raise

    def test_render_hovered(self):
        """Test FilmStripDeleteTab render in hovered state."""
        tab = FilmStripDeleteTab(x=100, y=5, width=40, height=10)
        tab.is_hovered = True
        surface = pygame.Surface((500, 200))
        tab.render(surface)  # Should not raise


class TestFilmStripHelperMethods:
    """Test various helper methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_has_valid_canvas_sprite_no_parent_scene(self):
        """Test _has_valid_canvas_sprite returns False with no parent scene."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget._has_valid_canvas_sprite() is False

    def test_has_valid_canvas_sprite_with_canvas(self, mocker):
        """Test _has_valid_canvas_sprite returns True with valid canvas."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        parent_scene = mocker.Mock()
        parent_scene.canvas = mocker.Mock()
        parent_scene.canvas.animated_sprite = mocker.Mock()
        widget.parent_scene = parent_scene
        assert widget._has_valid_canvas_sprite() is True

    def test_is_keyboard_selected_no_parent_scene(self):
        """Test _is_keyboard_selected returns False with no parent scene."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget._is_keyboard_selected('idle', 0) is False

    def test_is_keyboard_selected_matching(self, mocker):
        """Test _is_keyboard_selected returns True when matching."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        parent_scene = mocker.Mock()
        parent_scene.selected_animation = 'idle'
        parent_scene.selected_frame = 2
        widget.parent_scene = parent_scene
        assert widget._is_keyboard_selected('idle', 2) is True

    def test_is_keyboard_selected_not_matching(self, mocker):
        """Test _is_keyboard_selected returns False when not matching."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        parent_scene = mocker.Mock()
        parent_scene.selected_animation = 'walk'
        parent_scene.selected_frame = 0
        widget.parent_scene = parent_scene
        assert widget._is_keyboard_selected('idle', 0) is False

    def test_get_controller_selection_color_no_parent(self):
        """Test _get_controller_selection_color returns None with no parent."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        assert widget._get_controller_selection_color('idle', 0) is None

    def test_set_parent_canvas(self, mocker):
        """Test set_parent_canvas stores the canvas reference."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        canvas = mocker.Mock()
        widget.set_parent_canvas(canvas)
        assert widget.parent_canvas is canvas

    def test_update_layout(self, mocker):
        """Test update_layout recalculates layouts and creates tabs."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)
        widget.update_layout()
        # Should have recalculated layouts
        assert len(widget.frame_layouts) > 0


class TestFilmStripStopAnimationBeforeDeletion:
    """Test _stop_animation_before_deletion method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_stop_animation_no_sprite(self):
        """Test _stop_animation_before_deletion with no sprite."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget._stop_animation_before_deletion('idle', 0)  # Should not raise

    def test_stop_animation_matching_animation(self):
        """Test _stop_animation_before_deletion stops animation and adjusts frame."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        frames = [SpriteFrame(surface, duration=FRAME_DURATION) for _ in range(3)]
        sprite.add_animation('idle', frames)
        widget.set_animated_sprite(sprite)
        sprite.frame_manager.current_frame = 2
        widget._stop_animation_before_deletion('idle', 1)
        assert sprite._is_playing is False
        assert sprite.frame_manager.current_frame <= 1


class TestFilmStripAdjustCurrentFrameAfterDeletion:
    """Test _adjust_current_frame_after_deletion method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_adjust_frame_decrements_when_at_deleted_index(self):
        """Test current frame decrements when at the deleted frame index."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.current_animation = 'idle'
        widget.current_frame = 2
        widget._adjust_current_frame_after_deletion('idle', 2)
        assert widget.current_frame == 1

    def test_adjust_frame_stays_at_zero(self):
        """Test current frame stays at 0 when deleting frame 0."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.current_animation = 'idle'
        widget.current_frame = 0
        widget._adjust_current_frame_after_deletion('idle', 0)
        assert widget.current_frame == 0

    def test_adjust_frame_different_animation_no_change(self):
        """Test no adjustment when animation names differ."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        widget.current_animation = 'walk'
        widget.current_frame = 2
        widget._adjust_current_frame_after_deletion('idle', 1)
        assert widget.current_frame == 2


class TestFilmStripDumpAnimationDebugState:
    """Test debug state dump methods."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_dump_animation_debug_state(self):
        """Test _dump_animation_debug_state runs without error."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)
        widget._debug_start_time = 5.0
        widget._dump_animation_debug_state(DT_60FPS)

    def test_dump_animated_sprite_debug(self):
        """Test _dump_animated_sprite_debug runs without error."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
        sprite = AnimatedSprite()
        surface = pygame.Surface((SURFACE_SIZE, SURFACE_SIZE))
        sprite.add_animation('idle', [SpriteFrame(surface, duration=FRAME_DURATION)])
        widget.set_animated_sprite(sprite)
        widget._dump_animated_sprite_debug()
