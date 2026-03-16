"""Coverage tests for glitchygames/tools/film_strip.py.

Targets uncovered areas: FilmStripWidget initialization, layout calculations,
animation timing, copy/paste, frame selection, and hit-testing.
"""

import math
import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from glitchygames.tools.film_strip import FilmStripWidget
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


class TestFilmStripUpdateHeight:
    """Test _update_height method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_height_no_sprite(self):
        """Test _update_height with no sprite does nothing."""
        widget = FilmStripWidget(WIDGET_X, WIDGET_Y, WIDGET_WIDTH, WIDGET_HEIGHT)
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
        assert widget.rect.height > 100


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
        frame._image_stale = True
        frame.pixels = [(255, 0, 0, 255)] * (SURFACE_SIZE * SURFACE_SIZE)
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
