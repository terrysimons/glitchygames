"""Tests for film tab functionality and frame insertion.

This module tests the film tab system that allows users to insert new frames
before or after existing frames in film strips.
"""

import itertools

import pygame
from src.apps.bitmappy.tests.film_strip_support import (
    FRAME_SIZE,
    FilmStripTestBase,
    make_real_animated_sprite,
)

from bitmappy.film_strip import FilmTabWidget
from glitchygames.sprites import AnimatedSprite, SpriteFrame

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
# FilmTabWidget's colours (film_strip.py)
TAB_COLOR = (200, 200, 200)
CLICK_COLOR = (100, 100, 100)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
# FilmTabWidget draws a 2-pixel border
TAB_BORDER_WIDTH = 2


def drawn_tab_colors(*, surface, tab):
    """Read a rendered tab's fill colour (inside its border) and its border colour.

    Returns:
        tuple: The (fill, border) RGB colours.

    """
    inside_border = (tab.rect.x + TAB_BORDER_WIDTH, tab.rect.y + TAB_BORDER_WIDTH)
    fill_color = tuple(surface.get_at(inside_border))[:3]
    border_color = tuple(surface.get_at(tab.rect.topleft))[:3]
    return fill_color, border_color


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

    def test_film_tab_click_handling(self):
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

    def test_film_tab_hover_handling(self):
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

    def test_film_tab_insertion_type_setting(self):
        """Test that insertion type and target frame can be set."""
        tab = FilmTabWidget(x=TAB_X, y=TAB_Y)

        tab.set_insertion_type('after', TARGET_FRAME_5)
        assert tab.insertion_type == 'after'
        assert tab.target_frame_index == TARGET_FRAME_5

        tab.set_insertion_type('before', FRAME_INDEX_2)
        assert tab.insertion_type == 'before'
        assert tab.target_frame_index == FRAME_INDEX_2

    def test_film_tab_rendering(self):
        """Test that the tab draws grey with a black border, inverted on hover, dark on click."""
        tab = FilmTabWidget(x=TAB_X, y=TAB_Y, width=TAB_WIDTH, height=TAB_HEIGHT)
        test_surface = pygame.Surface((100, 100), flags=0, depth=32)

        tab.render(test_surface)
        assert drawn_tab_colors(surface=test_surface, tab=tab) == (TAB_COLOR, BLACK)
        # The plus sign at the centre is drawn in the border colour
        assert tuple(test_surface.get_at(tab.rect.center))[:3] == BLACK

        tab.is_hovered = True
        tab.render(test_surface)
        assert drawn_tab_colors(surface=test_surface, tab=tab) == (BLACK, WHITE)
        assert tuple(test_surface.get_at(tab.rect.center))[:3] == WHITE

        tab.is_clicked = True
        tab.render(test_surface)
        assert drawn_tab_colors(surface=test_surface, tab=tab) == (CLICK_COLOR, BLACK)


class TestFilmStripTabIntegration(FilmStripTestBase):
    """Test film tab integration with film strips in a real editor scene."""

    def create_idle_strip(self):
        """Load a five-frame 'idle' animation into a real editor scene.

        Returns:
            tuple: The scene and the 'idle' FilmStripWidget.

        """
        scene = self.create_optimized_scene()
        scene.film_strip_coordinator.on_sprite_loaded(make_real_animated_sprite())
        return scene, scene.film_strips['idle']

    def test_film_tabs_creation(self):
        """Test that the strip has a 'before' tab for frame 0 and an 'after' tab per frame."""
        _scene, film_strip = self.create_idle_strip()

        film_strip.update_layout()

        # Tabs exist only for the frames laid out in the strip's visible width
        laid_out_frame_indexes = [frame_index for _name, frame_index in film_strip.frame_layouts]
        assert laid_out_frame_indexes
        frame_tabs = [tab for tab in film_strip.film_tabs if type(tab) is FilmTabWidget]
        assert {(tab.insertion_type, tab.target_frame_index) for tab in frame_tabs} == {
            ('before', 0),
            *(('after', frame_index) for frame_index in laid_out_frame_indexes),
        }
        for tab in film_strip.film_tabs:
            assert tab.insertion_type in {'before', 'after', 'delete'}
            assert tab.target_frame_index >= 0

    def test_film_tab_click_handling(self):
        """Test that clicking the first tab is handled and inserts a frame."""
        _scene, film_strip = self.create_idle_strip()
        frame_count = len(film_strip.animated_sprite.animations['idle'])
        first_tab = film_strip.film_tabs[0]
        assert type(first_tab) is FilmTabWidget

        result = film_strip._handle_tab_click(first_tab.rect.center)

        assert result
        assert len(film_strip.animated_sprite.animations['idle']) == frame_count + 1

    def test_film_tab_hover_handling(self):
        """Test that hovering over the first tab marks it, and only it, hovered."""
        _scene, film_strip = self.create_idle_strip()
        first_tab = film_strip.film_tabs[0]

        result = film_strip._handle_tab_hover(first_tab.rect.center)

        assert result
        assert first_tab.is_hovered
        assert not any(tab.is_hovered for tab in film_strip.film_tabs[1:])

    def test_film_tab_rendering(self):
        """Test that rendering the film strip draws each frame tab where it is laid out."""
        _scene, film_strip = self.create_idle_strip()
        test_surface = pygame.Surface(film_strip.rect.size, flags=0, depth=32)

        film_strip.render(test_surface)

        frame_tabs = [tab for tab in film_strip.film_tabs if type(tab) is FilmTabWidget]
        assert frame_tabs
        for tab in frame_tabs:
            # The tab's right border is not covered by the frame thumbnails drawn after it
            right_border = (tab.rect.right - 1, tab.rect.centery)
            assert tuple(test_surface.get_at(right_border))[:3] == BLACK
            inside_right_border = (tab.rect.right - 1 - TAB_BORDER_WIDTH, tab.rect.centery)
            assert tuple(test_surface.get_at(inside_right_border))[:3] == TAB_COLOR


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
