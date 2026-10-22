"""Tests for film tab functionality and frame insertion.

This module tests the film tab system that allows users to insert new frames
before or after existing frames in film strips.
"""

import itertools

import pygame
import pytest

from glitchygames.bitmappy.film_strip import FilmStripWidget, FilmTabWidget
from glitchygames.sprites import AnimatedSprite, SpriteFrame
from tests.mocks.test_mock_factory import MockFactory, MockSpriteConfig
from tests.tools.test_film_strip_base import FRAME_SIZE, FilmStripTestBase

# Additional test constants
TAB_X = 10
TAB_Y = 20
TAB_WIDTH = 25
TAB_HEIGHT = 35
FRAME_INDEX_2 = 2
TARGET_FRAME_5 = 5
ANIMATION_NAME = 'test_anim'
MAGENTA = (255, 0, 255)
FRAME_COLORS = ((255, 0, 0), (0, 255, 0), (0, 0, 255))
LAST_FRAME_INDEX = len(FRAME_COLORS) - 1
# Distinct from NEW_FRAME_DURATION so a test can tell inserted frames from loaded ones
LOADED_FRAME_DURATION = 0.25
# The blank frames insert_frame_at_tab creates (film_strip_events.py) last 0.5 seconds
NEW_FRAME_DURATION = 0.5
# film_strip_layout.FilmStripLayout.calculate_frame_layouts places frames after the first
# frame_width + tab_width + 11 pixels apart
FRAME_GAP_AFTER_TAB = 11


def find_frame_tab(*, film_strip, insertion_type, target_frame_index):
    """Find a film strip's frame insertion tab.

    Returns:
        FilmTabWidget: The tab that inserts at the given position.

    Raises:
        AssertionError: If the film strip has no such tab.

    """
    for tab in film_strip.film_tabs:
        if (
            type(tab) is FilmTabWidget
            and tab.insertion_type == insertion_type
            and tab.target_frame_index == target_frame_index
        ):
            return tab
    message = f'No {insertion_type!r} tab for frame {target_frame_index}'
    raise AssertionError(message)


def strip_frame_colors(*, film_strip):
    """Read the colour of each frame in the film strip's animation, in order.

    Returns:
        list[tuple[int, int, int]]: The top-left pixel colour of every frame.

    """
    return [
        tuple(frame.image.get_at((0, 0)))[:3]
        for frame in film_strip.animated_sprite.animations[ANIMATION_NAME]
    ]


def strip_frame_rects(*, film_strip):
    """Read the laid-out frame rectangles of the film strip's animation, in frame order.

    Returns:
        list[pygame.Rect]: The frame rectangles.

    """
    frame_keys = sorted(key for key in film_strip.frame_layouts if key[0] == ANIMATION_NAME)
    return [film_strip.frame_layouts[frame_key] for frame_key in frame_keys]


class FilmStripInsertionTestBase(FilmStripTestBase):
    """Film strip tests that run frame insertion through a real editor scene."""

    def create_scene_with_colored_strip(self):
        """Load a three-frame red, green, blue animation into a real editor scene.

        Returns:
            tuple: The BitmapEditorScene and the animation's FilmStripWidget.

        """
        animated_sprite = AnimatedSprite()
        frames = []
        for frame_color in FRAME_COLORS:
            frame_surface = pygame.Surface((FRAME_SIZE, FRAME_SIZE))
            frame_surface.fill(frame_color)
            frames.append(SpriteFrame(frame_surface, duration=LOADED_FRAME_DURATION))
        animated_sprite.add_animation(ANIMATION_NAME, frames)

        scene = self.create_optimized_scene()
        scene.film_strip_coordinator.on_sprite_loaded(animated_sprite)
        return scene, scene.film_strips[ANIMATION_NAME]


class TestFilmTabWidget(FilmStripTestBase):
    """Test the FilmTabWidget class."""

    def test_film_tab_initialization(self):
        """Test that film tab initializes correctly."""
        tab = FilmTabWidget(x=TAB_X, y=TAB_Y, width=TAB_WIDTH, height=TAB_HEIGHT)

        assert tab.x == TAB_X
        assert tab.y == TAB_Y
        assert tab.width == TAB_WIDTH
        assert tab.height == TAB_HEIGHT
        assert tab.rect is not None
        assert tab.rect.x == TAB_X
        assert tab.rect.y == TAB_Y
        assert tab.rect.width == TAB_WIDTH
        assert tab.rect.height == TAB_HEIGHT

        # Check default properties
        assert not tab.is_hovered
        assert not tab.is_clicked
        assert tab.insertion_type == 'before'
        assert tab.target_frame_index == 0

    def test_film_tab_click_handling(self, mock_pygame_patches):
        """Test that film tab handles clicks correctly."""
        tab = FilmTabWidget(x=TAB_X, y=TAB_Y, width=TAB_WIDTH, height=TAB_HEIGHT)

        # Click inside the tab
        result = tab.handle_click((15, 30))
        assert result
        assert tab.is_clicked

        # Reset and click outside the tab
        tab.reset_click_state()
        result = tab.handle_click((50, 50))
        assert not result
        assert not tab.is_clicked

    def test_film_tab_hover_handling(self, mock_pygame_patches):
        """Test that film tab handles hover correctly."""
        tab = FilmTabWidget(x=TAB_X, y=TAB_Y, width=TAB_WIDTH, height=TAB_HEIGHT)

        # Hover inside the tab
        result = tab.handle_hover((15, 30))
        assert result
        assert tab.is_hovered

        # Hover outside the tab
        result = tab.handle_hover((50, 50))
        assert not result
        assert not tab.is_hovered

    def test_film_tab_insertion_type_setting(self, mock_pygame_patches):
        """Test that insertion type and target frame can be set."""
        tab = FilmTabWidget(x=TAB_X, y=TAB_Y)

        tab.set_insertion_type('after', TARGET_FRAME_5)
        assert tab.insertion_type == 'after'
        assert tab.target_frame_index == TARGET_FRAME_5

        tab.set_insertion_type('before', FRAME_INDEX_2)
        assert tab.insertion_type == 'before'
        assert tab.target_frame_index == FRAME_INDEX_2

    def test_film_tab_rendering(self, mock_pygame_patches):
        """Test that film tab renders without errors."""
        tab = FilmTabWidget(x=TAB_X, y=TAB_Y, width=TAB_WIDTH, height=TAB_HEIGHT)
        test_surface = pygame.Surface((100, 100))

        # Should not raise any exceptions
        tab.render(test_surface)

        # Test with different states
        tab.is_hovered = True
        tab.render(test_surface)

        tab.is_clicked = True
        tab.render(test_surface)


class TestFilmStripTabIntegration(FilmStripTestBase):
    """Test film tab integration with film strips."""

    @pytest.fixture(autouse=True)
    def _mock_font_manager(self, mocker):
        """Mock FontManager.get_font to avoid fc-list timeout on CI."""
        mock_rect = pygame.Rect(0, 0, 50, 14)
        real_surface = pygame.Surface((50, 14), pygame.SRCALPHA)
        mock_font = mocker.Mock()
        mock_font.get_rect.return_value = mock_rect
        mock_font.render.return_value = (real_surface, mock_rect)
        mocker.patch('glitchygames.fonts.font_manager.FontManager.get_font', return_value=mock_font)

    def _create_mock_sprite_with_frames(self):
        """Create a mock sprite with frames using centralized mocks.

        Returns:
            object: The result.

        """
        mock_sprite = MockFactory.create_animated_sprite_mock(
            config=MockSpriteConfig(animation_name='idle'),
        )
        mock_sprite._animation_order = ['idle']

        # Ensure frames have proper rect attributes for tab positioning
        for frame in mock_sprite._animations['idle']:
            if not hasattr(frame, 'rect'):
                frame.rect = self._mocker.Mock()
                frame.rect.centerx = 50  # Default center x
                frame.rect.centery = 50  # Default center y
                frame.rect.width = FRAME_SIZE
                frame.rect.height = FRAME_SIZE

        return mock_sprite

    def test_film_tabs_creation(self):
        """Test that film tabs are created correctly."""
        # Create a mock animated sprite with frames using centralized mocks
        mock_sprite = self._create_mock_sprite_with_frames()

        # Create film strip widget
        film_strip = FilmStripWidget(0, 0, 400, 100)
        film_strip.set_animated_sprite(mock_sprite)
        film_strip.current_animation = 'idle'
        film_strip.current_frame = 0

        # Mock parent scene with canvas that has a proper animated_sprite._animations dict
        mock_scene = self._mocker.Mock()
        mock_scene.canvas.animated_sprite._animations = mock_sprite._animations
        mock_scene.canvas.animated_sprite.animations = mock_sprite._animations
        film_strip.parent_scene = mock_scene

        # Update layout to create tabs
        film_strip.update_layout()

        # Should have tabs for each frame
        assert len(film_strip.film_tabs) > 0

        # Check that tabs have correct properties
        for tab in film_strip.film_tabs:
            assert tab.insertion_type in {'before', 'after', 'delete'}
            assert tab.target_frame_index >= 0

    def test_film_tab_click_handling(self):
        """Test that film strip handles tab clicks correctly."""
        # Create a mock animated sprite with frames using centralized mocks
        mock_sprite = self._create_mock_sprite_with_frames()

        # Create film strip widget
        film_strip = FilmStripWidget(0, 0, 400, 100)
        film_strip.set_animated_sprite(mock_sprite)
        film_strip.current_animation = 'idle'
        film_strip.current_frame = 0

        # Mock parent scene with proper canvas dimensions and animated_sprite._animations
        mock_scene = self._mocker.Mock()
        mock_scene.canvas.pixels_across = 32
        mock_scene.canvas.pixels_tall = 32
        mock_scene.canvas.animated_sprite._animations = mock_sprite._animations
        mock_scene.canvas.animated_sprite.animations = mock_sprite._animations
        film_strip.parent_scene = mock_scene

        # Update layout to create tabs
        film_strip.update_layout()

        # Get the first tab
        if film_strip.film_tabs:
            first_tab = film_strip.film_tabs[0]
            assert first_tab.rect is not None
            tab_pos = (first_tab.rect.centerx, first_tab.rect.centery)

            # Test tab click handling
            result = film_strip._handle_tab_click(tab_pos)
            assert result

    def test_film_tab_hover_handling(self):
        """Test that film strip handles tab hover correctly."""
        # Create a mock animated sprite with frames using centralized mocks
        mock_sprite = self._create_mock_sprite_with_frames()

        # Create film strip widget
        film_strip = FilmStripWidget(0, 0, 400, 100)
        film_strip.set_animated_sprite(mock_sprite)
        film_strip.current_animation = 'idle'
        film_strip.current_frame = 0

        # Mock parent scene with canvas that has a proper animated_sprite._animations dict
        mock_scene = self._mocker.Mock()
        mock_scene.canvas.animated_sprite._animations = mock_sprite._animations
        mock_scene.canvas.animated_sprite.animations = mock_sprite._animations
        film_strip.parent_scene = mock_scene

        # Update layout to create tabs
        film_strip.update_layout()

        # Get the first tab
        if film_strip.film_tabs:
            first_tab = film_strip.film_tabs[0]
            assert first_tab.rect is not None
            tab_pos = (first_tab.rect.centerx, first_tab.rect.centery)

            # Test tab hover handling
            result = film_strip._handle_tab_hover(tab_pos)
            assert result

    def test_film_tab_rendering(self):
        """Test that film tabs are rendered correctly."""
        # Create a mock animated sprite with frames using centralized mocks
        mock_sprite = self._create_mock_sprite_with_frames()

        # Create film strip widget
        film_strip = FilmStripWidget(0, 0, 400, 100)
        film_strip.set_animated_sprite(mock_sprite)
        film_strip.current_animation = 'idle'
        film_strip.current_frame = 0

        # Mock parent scene with canvas that has a proper animated_sprite._animations dict
        mock_scene = self._mocker.Mock()
        mock_scene.canvas.animated_sprite._animations = mock_sprite._animations
        mock_scene.canvas.animated_sprite.animations = mock_sprite._animations
        mock_scene.controller_selections = {}
        mock_scene.multi_controller_manager.controllers = {}
        film_strip.parent_scene = mock_scene

        # Update layout to create tabs
        film_strip.update_layout()

        # Clear parent_scene before rendering to avoid deep Mock iteration issues
        # in the rendering path (controller_selections, multi_controller_manager, etc.)
        film_strip.parent_scene = None

        # Should not raise any exceptions when rendering
        test_surface = pygame.Surface((800, 600))
        film_strip.render(test_surface)

        # Check that tabs exist
        assert len(film_strip.film_tabs) > 0


class TestFilmTabFrameInsertion(FilmStripInsertionTestBase):
    """Test frame insertion functionality through film tabs."""

    # Not in TestFilmStripTabIntegration: its FontManager mock makes building a real
    # BitmapEditorScene hang
    def test_frame_insertion_via_tab(self):
        """Test that clicking a frame's insertion tab inserts a new frame after it."""
        _scene, film_strip = self.create_scene_with_colored_strip()
        after_first_tab = find_frame_tab(
            film_strip=film_strip,
            insertion_type='after',
            target_frame_index=0,
        )

        assert film_strip._handle_tab_click(after_first_tab.rect.center)

        red, green, blue = FRAME_COLORS
        assert strip_frame_colors(film_strip=film_strip) == [red, MAGENTA, green, blue]

    def test_insert_frame_before_first(self):
        """Test inserting a frame before the first frame."""
        scene, film_strip = self.create_scene_with_colored_strip()

        film_strip._insert_frame_at_tab(
            find_frame_tab(film_strip=film_strip, insertion_type='before', target_frame_index=0),
        )

        assert strip_frame_colors(film_strip=film_strip) == [MAGENTA, *FRAME_COLORS]
        new_frame = film_strip.animated_sprite.animations[ANIMATION_NAME][0]
        assert new_frame.duration == NEW_FRAME_DURATION
        # The new frame is selected so it can be edited right away
        assert scene.selected_frame == 0

    def test_insert_frame_after_last(self):
        """Test inserting a frame after the last frame."""
        scene, film_strip = self.create_scene_with_colored_strip()

        film_strip._insert_frame_at_tab(
            find_frame_tab(
                film_strip=film_strip,
                insertion_type='after',
                target_frame_index=LAST_FRAME_INDEX,
            ),
        )

        assert strip_frame_colors(film_strip=film_strip) == [*FRAME_COLORS, MAGENTA]
        new_frame = film_strip.animated_sprite.animations[ANIMATION_NAME][-1]
        assert new_frame.duration == NEW_FRAME_DURATION
        assert scene.selected_frame == len(FRAME_COLORS)

    def test_insert_frame_after_middle(self):
        """Test inserting a frame after a middle frame."""
        scene, film_strip = self.create_scene_with_colored_strip()

        film_strip._insert_frame_at_tab(
            find_frame_tab(film_strip=film_strip, insertion_type='after', target_frame_index=1),
        )

        red, green, blue = FRAME_COLORS
        assert strip_frame_colors(film_strip=film_strip) == [red, green, MAGENTA, blue]
        assert scene.selected_frame == FRAME_INDEX_2

    def test_new_frame_has_magenta_background(self):
        """Test that every pixel of a new frame is the magenta transparency key."""
        _scene, film_strip = self.create_scene_with_colored_strip()

        film_strip._insert_frame_at_tab(
            find_frame_tab(film_strip=film_strip, insertion_type='before', target_frame_index=0),
        )

        new_frame_image = film_strip.animated_sprite.animations[ANIMATION_NAME][0].image
        assert new_frame_image.get_size() == (FRAME_SIZE, FRAME_SIZE)
        pixel_colors = pygame.surfarray.array3d(new_frame_image).reshape(-1, 3)
        assert {tuple(int(channel) for channel in color) for color in pixel_colors} == {MAGENTA}

    def test_frames_are_evenly_spaced(self):
        """Test that consecutive frames are frame width + tab width + 11 pixels apart."""
        _scene, film_strip = self.create_scene_with_colored_strip()

        frame_rects = strip_frame_rects(film_strip=film_strip)

        assert len(frame_rects) == len(FRAME_COLORS)
        expected_stride = film_strip.frame_width + film_strip.tab_width + FRAME_GAP_AFTER_TAB
        for previous_rect, current_rect in itertools.pairwise(frame_rects):
            assert current_rect.x - previous_rect.x == expected_stride

    def test_after_tabs_sit_between_frames(self):
        """Test that each frame's insertion tab lies in the gap before the next frame."""
        _scene, film_strip = self.create_scene_with_colored_strip()

        frame_rects = strip_frame_rects(film_strip=film_strip)

        before_tab = find_frame_tab(
            film_strip=film_strip,
            insertion_type='before',
            target_frame_index=0,
        )
        assert before_tab.rect.right <= frame_rects[0].left
        for frame_index, (frame_rect, next_frame_rect) in enumerate(
            itertools.pairwise(frame_rects),
        ):
            after_tab = find_frame_tab(
                film_strip=film_strip,
                insertion_type='after',
                target_frame_index=frame_index,
            )
            # The tab overlaps its own frame's right edge, never the next frame
            assert after_tab.rect.left < frame_rect.right
            assert after_tab.rect.right <= next_frame_rect.left


class TestFilmTabSceneIntegration(FilmStripInsertionTestBase):
    """Test film tab integration with the scene system."""

    def test_scene_handles_frame_insertion(self):
        """Test that the scene records a tab insertion so undo removes the frame."""
        scene, film_strip = self.create_scene_with_colored_strip()

        film_strip._insert_frame_at_tab(
            find_frame_tab(film_strip=film_strip, insertion_type='after', target_frame_index=0),
        )
        assert len(strip_frame_colors(film_strip=film_strip)) == len(FRAME_COLORS) + 1

        assert scene.undo_redo_manager.undo()

        assert strip_frame_colors(film_strip=film_strip) == list(FRAME_COLORS)

    def test_frame_insertion_updates_canvas(self):
        """Test that frame insertion shows the new, blank frame on the canvas."""
        scene, film_strip = self.create_scene_with_colored_strip()
        scene.film_strip_coordinator.switch_to_film_strip(ANIMATION_NAME, 1)
        assert {pixel[:3] for pixel in scene.canvas.pixels} == {FRAME_COLORS[1]}

        film_strip._insert_frame_at_tab(
            find_frame_tab(film_strip=film_strip, insertion_type='before', target_frame_index=0),
        )

        assert scene.selected_animation == ANIMATION_NAME
        assert scene.selected_frame == 0
        assert scene.canvas.current_frame == 0
        assert {pixel[:3] for pixel in scene.canvas.pixels} == {MAGENTA}
