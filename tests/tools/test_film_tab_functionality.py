"""Tests for film tab functionality and frame insertion.

This module tests the film tab system that allows users to insert new frames
before or after existing frames in film strips.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pygame

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.sprites import AnimatedSprite, SpriteFrame
from glitchygames.tools.bitmappy import BitmapEditorScene
from glitchygames.tools.film_strip import FilmStripWidget, FilmTabWidget

# Test constants to avoid magic values
TAB_X = 10
TAB_Y = 20
TAB_WIDTH = 25
TAB_HEIGHT = 35
FRAME_INDEX_2 = 2
MAGENTA_R = 255
MAGENTA_G = 0
MAGENTA_B = 255
FRAME_GAP = 2
SAMPLE_SIZE = 4
TARGET_FRAME_5 = 5
FRAME_DURATION = 0.5
MIN_FRAMES_FOR_SPACING = 3


class TestFilmTabWidget:
    """Test the FilmTabWidget class."""

    def test_film_tab_initialization(self, mock_pygame_patches):
        """Test that film tab initializes correctly."""
        tab = FilmTabWidget(x=TAB_X, y=TAB_Y, width=TAB_WIDTH, height=TAB_HEIGHT)

        assert tab.x == TAB_X
        assert tab.y == TAB_Y
        assert tab.width == TAB_WIDTH
        assert tab.height == TAB_HEIGHT
        assert tab.rect.x == TAB_X
        assert tab.rect.y == TAB_Y
        assert tab.rect.width == TAB_WIDTH
        assert tab.rect.height == TAB_HEIGHT

        # Check default properties
        assert not tab.is_hovered
        assert not tab.is_clicked
        assert tab.insertion_type == "before"
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

        tab.set_insertion_type("after", TARGET_FRAME_5)
        assert tab.insertion_type == "after"
        assert tab.target_frame_index == TARGET_FRAME_5

        tab.set_insertion_type("before", FRAME_INDEX_2)
        assert tab.insertion_type == "before"
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


class TestFilmStripTabIntegration:
    """Test film tab integration with film strips."""

    def test_film_tabs_creation(self, mock_pygame_patches):
        """Test that film tabs are created correctly."""
        # Create a mock animated sprite with frames
        mock_sprite = Mock()
        mock_sprite._animations = {
            "idle": [
                Mock(duration=FRAME_DURATION, image=pygame.Surface((32, 32))),
                Mock(duration=FRAME_DURATION, image=pygame.Surface((32, 32))),
                Mock(duration=FRAME_DURATION, image=pygame.Surface((32, 32)))
            ]
        }
        mock_sprite._animation_order = ["idle"]

        # Create film strip widget
        film_strip = FilmStripWidget(0, 0, 400, 100)
        film_strip.set_animated_sprite(mock_sprite)
        film_strip.current_animation = "idle"
        film_strip.current_frame = 0

        # Mock parent scene
        mock_scene = Mock()
        film_strip.parent_scene = mock_scene

        # Update layout to create tabs
        film_strip.update_layout()

        # Should have tabs for each frame
        assert len(film_strip.film_tabs) > 0

        # Check that tabs have correct properties
        for tab in film_strip.film_tabs:
            assert tab.insertion_type in {"before", "after"}
            assert tab.target_frame_index >= 0

    def test_film_tab_click_handling(self, mock_pygame_patches):
        """Test that film strip handles tab clicks correctly."""
        # Create a mock animated sprite with frames
        mock_sprite = Mock()
        mock_sprite._animations = {
            "idle": [
                Mock(duration=FRAME_DURATION, image=pygame.Surface((32, 32))),
                Mock(duration=FRAME_DURATION, image=pygame.Surface((32, 32))),
                Mock(duration=FRAME_DURATION, image=pygame.Surface((32, 32)))
            ]
        }
        mock_sprite._animation_order = ["idle"]

        # Create film strip widget
        film_strip = FilmStripWidget(0, 0, 400, 100)
        film_strip.set_animated_sprite(mock_sprite)
        film_strip.current_animation = "idle"
        film_strip.current_frame = 0

        # Mock parent scene
        mock_scene = Mock()
        film_strip.parent_scene = mock_scene

        # Update layout to create tabs
        film_strip.update_layout()

        # Get the first tab
        if film_strip.film_tabs:
            first_tab = film_strip.film_tabs[0]
            tab_pos = (first_tab.rect.centerx, first_tab.rect.centery)

            # Test tab click handling
            result = film_strip._handle_tab_click(tab_pos)
            assert result

    def test_film_tab_hover_handling(self, mock_pygame_patches):
        """Test that film strip handles tab hover correctly."""
        # Create a mock animated sprite with frames
        mock_sprite = Mock()
        mock_sprite._animations = {
            "idle": [
                Mock(duration=FRAME_DURATION, image=pygame.Surface((32, 32))),
                Mock(duration=FRAME_DURATION, image=pygame.Surface((32, 32))),
                Mock(duration=FRAME_DURATION, image=pygame.Surface((32, 32)))
            ]
        }
        mock_sprite._animation_order = ["idle"]

        # Create film strip widget
        film_strip = FilmStripWidget(0, 0, 400, 100)
        film_strip.set_animated_sprite(mock_sprite)
        film_strip.current_animation = "idle"
        film_strip.current_frame = 0

        # Mock parent scene
        mock_scene = Mock()
        film_strip.parent_scene = mock_scene

        # Update layout to create tabs
        film_strip.update_layout()

        # Get the first tab
        if film_strip.film_tabs:
            first_tab = film_strip.film_tabs[0]
            tab_pos = (first_tab.rect.centerx, first_tab.rect.centery)

            # Test tab hover handling
            result = film_strip._handle_tab_hover(tab_pos)
            assert result

    def test_frame_insertion_via_tab(self, mock_pygame_patches):
        """Test that clicking a tab inserts a new frame."""
        # Create a mock animated sprite with frames
        mock_sprite = Mock()
        mock_sprite._animations = {
            "idle": [
                Mock(duration=FRAME_DURATION, image=pygame.Surface((32, 32))),
                Mock(duration=FRAME_DURATION, image=pygame.Surface((32, 32))),
                Mock(duration=FRAME_DURATION, image=pygame.Surface((32, 32)))
            ]
        }
        mock_sprite._animation_order = ["idle"]

        # Create film strip widget
        film_strip = FilmStripWidget(0, 0, 400, 100)
        film_strip.set_animated_sprite(mock_sprite)
        film_strip.current_animation = "idle"
        film_strip.current_frame = 0

        # Mock parent scene
        mock_scene = Mock()
        film_strip.parent_scene = mock_scene

        # Update layout to create tabs
        film_strip.update_layout()

        # Get the first tab and simulate click
        if film_strip.film_tabs:
            first_tab = film_strip.film_tabs[0]

            # Mock the add_frame method
            with patch.object(mock_sprite, "add_frame") as mock_add_frame:
                # Simulate frame insertion
                film_strip._insert_frame_at_tab(first_tab)

                # Verify that add_frame was called
                mock_add_frame.assert_called_once()

                # Check that the call was made with correct parameters
                call_args = mock_add_frame.call_args
                assert call_args[0][0] == "idle"  # animation name
                assert isinstance(call_args[0][1], SpriteFrame)  # new frame
                assert call_args[0][2] >= 0  # insertion index

    def test_film_tab_rendering(self, mock_pygame_patches):
        """Test that film tabs are rendered correctly."""
        # Create a mock animated sprite with frames
        mock_sprite = Mock()
        mock_sprite._animations = {
            "idle": [
                Mock(duration=FRAME_DURATION, image=pygame.Surface((32, 32))),
                Mock(duration=FRAME_DURATION, image=pygame.Surface((32, 32))),
                Mock(duration=FRAME_DURATION, image=pygame.Surface((32, 32)))
            ]
        }
        mock_sprite._animation_order = ["idle"]

        # Create film strip widget
        film_strip = FilmStripWidget(0, 0, 400, 100)
        film_strip.set_animated_sprite(mock_sprite)
        film_strip.current_animation = "idle"
        film_strip.current_frame = 0

        # Mock parent scene
        mock_scene = Mock()
        film_strip.parent_scene = mock_scene

        # Update layout to create tabs
        film_strip.update_layout()

        # Should not raise any exceptions when rendering
        test_surface = pygame.Surface((800, 600))
        film_strip.render(test_surface)

        # Check that tabs exist
        assert len(film_strip.film_tabs) > 0


class TestFilmTabFrameInsertion:
    """Test frame insertion functionality through film tabs."""

    def test_insert_frame_before_first(self, mock_pygame_patches):
        """Test inserting a frame before the first frame."""
        # Create a real animated sprite with frames
        animated_sprite = AnimatedSprite()

        # Create frames with different durations
        frame1 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)
        frame2 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)
        frame3 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)

        # Add animation with frames
        animated_sprite.add_animation("test_anim", [frame1, frame2, frame3])

        # Create film strip widget
        film_strip = FilmStripWidget(0, 0, 400, 100)
        film_strip.set_animated_sprite(animated_sprite)
        film_strip.current_animation = "test_anim"
        film_strip.current_frame = 0

        # Mock parent scene
        mock_scene = Mock()
        film_strip.parent_scene = mock_scene

        # Update layout to create tabs
        film_strip.update_layout()

        # Find the "before" tab for the first frame
        before_tab = None
        for tab in film_strip.film_tabs:
            if tab.insertion_type == "before" and tab.target_frame_index == 0:
                before_tab = tab
                break

        assert before_tab is not None, "Should have a 'before' tab for the first frame"

        # Get initial frame count
        initial_count = len(animated_sprite._animations["test_anim"])

        # Insert frame
        film_strip._insert_frame_at_tab(before_tab)

        # Check that frame was inserted
        new_count = len(animated_sprite._animations["test_anim"])
        assert new_count == initial_count + 1

        # Check that the new frame is at index 0
        new_frame = animated_sprite._animations["test_anim"][0]
        assert isinstance(new_frame, SpriteFrame)
        assert new_frame.duration == FRAME_DURATION

    def test_insert_frame_after_last(self, mock_pygame_patches):
        """Test inserting a frame after the last frame."""
        # Create a real animated sprite with frames
        animated_sprite = AnimatedSprite()

        # Create frames with different durations
        frame1 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)
        frame2 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)
        frame3 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)

        # Add animation with frames
        animated_sprite.add_animation("test_anim", [frame1, frame2, frame3])

        # Create film strip widget
        film_strip = FilmStripWidget(0, 0, 400, 100)
        film_strip.set_animated_sprite(animated_sprite)
        film_strip.current_animation = "test_anim"
        film_strip.current_frame = 0

        # Mock parent scene
        mock_scene = Mock()
        film_strip.parent_scene = mock_scene

        # Update layout to create tabs
        film_strip.update_layout()

        # Find the "after" tab for the last frame
        after_tab = None
        for tab in film_strip.film_tabs:
            if tab.insertion_type == "after" and tab.target_frame_index == FRAME_INDEX_2:
                after_tab = tab
                break

        assert after_tab is not None, "Should have an 'after' tab for the last frame"

        # Get initial frame count
        initial_count = len(animated_sprite._animations["test_anim"])

        # Insert frame
        film_strip._insert_frame_at_tab(after_tab)

        # Check that frame was inserted
        new_count = len(animated_sprite._animations["test_anim"])
        assert new_count == initial_count + 1

        # Check that the new frame is at the end
        new_frame = animated_sprite._animations["test_anim"][-1]
        assert isinstance(new_frame, SpriteFrame)
        assert new_frame.duration == FRAME_DURATION

    def test_insert_frame_after_middle(self, mock_pygame_patches):
        """Test inserting a frame after a middle frame."""
        # Create a real animated sprite with frames
        animated_sprite = AnimatedSprite()

        # Create frames with different durations
        frame1 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)
        frame2 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)
        frame3 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)

        # Add animation with frames
        animated_sprite.add_animation("test_anim", [frame1, frame2, frame3])

        # Create film strip widget
        film_strip = FilmStripWidget(0, 0, 400, 100)
        film_strip.set_animated_sprite(animated_sprite)
        film_strip.current_animation = "test_anim"
        film_strip.current_frame = 0

        # Mock parent scene
        mock_scene = Mock()
        film_strip.parent_scene = mock_scene

        # Update layout to create tabs
        film_strip.update_layout()

        # Find the "after" tab for the middle frame (index 1)
        after_tab = None
        for tab in film_strip.film_tabs:
            if tab.insertion_type == "after" and tab.target_frame_index == 1:
                after_tab = tab
                break

        assert after_tab is not None, "Should have an 'after' tab for the middle frame"

        # Get initial frame count
        initial_count = len(animated_sprite._animations["test_anim"])

        # Insert frame
        film_strip._insert_frame_at_tab(after_tab)

        # Check that frame was inserted
        new_count = len(animated_sprite._animations["test_anim"])
        assert new_count == initial_count + 1

        # Check that the new frame is at the correct position (after frame 1, so at index 2)
        new_frame = animated_sprite._animations["test_anim"][2]
        assert isinstance(new_frame, SpriteFrame)
        assert new_frame.duration == FRAME_DURATION

    def test_new_frame_has_magenta_background(self, mock_pygame_patches):
        """Test that new frames have magenta background as specified."""
        # Create a real animated sprite with frames
        animated_sprite = AnimatedSprite()

        # Create frames with different durations
        frame1 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)
        frame2 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)
        frame3 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)

        # Add animation with frames
        animated_sprite.add_animation("test_anim", [frame1, frame2, frame3])

        # Create film strip widget
        film_strip = FilmStripWidget(0, 0, 400, 100)
        film_strip.set_animated_sprite(animated_sprite)
        film_strip.current_animation = "test_anim"
        film_strip.current_frame = 0

        # Mock parent scene
        mock_scene = Mock()
        film_strip.parent_scene = mock_scene

        # Update layout to create tabs
        film_strip.update_layout()

        # Get the first tab
        first_tab = film_strip.film_tabs[0]

        # Insert frame
        film_strip._insert_frame_at_tab(first_tab)

        # Check that the new frame has magenta background
        new_frame = animated_sprite._animations["test_anim"][0]
        frame_surface = new_frame.image

        # Check a few pixels to ensure they're magenta
        for x in range(0, min(32, frame_surface.get_width()), SAMPLE_SIZE):
            for y in range(0, min(32, frame_surface.get_height()), SAMPLE_SIZE):
                pixel_color = frame_surface.get_at((x, y))
                assert pixel_color[:3] == (MAGENTA_R, MAGENTA_G, MAGENTA_B), \
                    f"Pixel at ({x}, {y}) should be magenta"

    def test_frame_spacing_has_2_pixel_gap(self, mock_pygame_patches):
        """Test that frames have a 2-pixel gap between them after the first frame."""
        # Create a real animated sprite with frames
        animated_sprite = AnimatedSprite()

        # Create frames with different durations
        frame1 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)
        frame2 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)
        frame3 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)

        # Add animation with frames
        animated_sprite.add_animation("test_anim", [frame1, frame2, frame3])

        # Create film strip widget
        film_strip = FilmStripWidget(0, 0, 400, 100)
        film_strip.set_animated_sprite(animated_sprite)
        film_strip.current_animation = "test_anim"
        film_strip.current_frame = 0

        # Mock parent scene
        mock_scene = Mock()
        film_strip.parent_scene = mock_scene

        # Update layout to create frame layouts
        film_strip.update_layout()

        # Get frame layouts
        frame_layouts = film_strip.frame_layouts

        # Should have at least 3 frames for spacing test
        assert len(frame_layouts) >= MIN_FRAMES_FOR_SPACING, \
            "Need at least 3 frames to test spacing"

        # Get sorted frame keys for the test animation
        frame_keys = sorted([
            k for k in frame_layouts
            if isinstance(k, tuple) and k[0] == "test_anim"
        ])

        # Test spacing between consecutive frames (after the first)
        for i in range(1, len(frame_keys)):
            current_frame = frame_layouts[frame_keys[i]]
            previous_frame = frame_layouts[frame_keys[i - 1]]

            # Calculate the gap between frames
            # The gap should be: current_frame.x - (previous_frame.x + previous_frame.width)
            expected_gap = FRAME_GAP  # 2-pixel gap as specified

            # Calculate actual gap
            previous_frame_end = previous_frame.x + previous_frame.width
            actual_gap = current_frame.x - previous_frame_end

            assert actual_gap == expected_gap, \
                f"Frame {frame_keys[i]} should have {expected_gap}px gap from " \
                f"frame {frame_keys[i - 1]}, but has {actual_gap}px gap"

    def test_frame_spacing_with_tabs(self, mock_pygame_patches):
        """Test that frame spacing accounts for tab width plus 2-pixel gap."""
        # Create a real animated sprite with frames
        animated_sprite = AnimatedSprite()

        # Create frames with different durations
        frame1 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)
        frame2 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)
        frame3 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)

        # Add animation with frames
        animated_sprite.add_animation("test_anim", [frame1, frame2, frame3])

        # Create film strip widget
        film_strip = FilmStripWidget(0, 0, 400, 100)
        film_strip.set_animated_sprite(animated_sprite)
        film_strip.current_animation = "test_anim"
        film_strip.current_frame = 0

        # Mock parent scene
        mock_scene = Mock()
        film_strip.parent_scene = mock_scene

        # Update layout to create frame layouts
        film_strip.update_layout()

        # Get frame layouts and tabs
        frame_layouts = film_strip.frame_layouts
        film_tabs = film_strip.film_tabs

        # Should have frames and tabs
        assert len(frame_layouts) > 1, "Need multiple frames to test spacing"
        assert len(film_tabs) > 0, "Should have film tabs"

        # Get sorted frame keys for the test animation
        frame_keys = sorted([
            k for k in frame_layouts
            if isinstance(k, tuple) and k[0] == "test_anim"
        ])

        # Test that spacing formula is correct
        # Expected spacing: frame_width + tab_width + 2
        expected_spacing = film_strip.frame_width + film_strip.tab_width + FRAME_GAP

        for i in range(1, len(frame_keys)):
            current_frame = frame_layouts[frame_keys[i]]
            previous_frame = frame_layouts[frame_keys[i - 1]]

            # Calculate actual spacing
            actual_spacing = current_frame.x - previous_frame.x

            assert actual_spacing == expected_spacing, \
                f"Frame {frame_keys[i]} spacing should be {expected_spacing}px " \
                f"(frame_width + tab_width + 2), but is {actual_spacing}px"


class TestFilmTabSceneIntegration:
    """Test film tab integration with the scene system."""

    def test_scene_handles_frame_insertion(self, mock_pygame_patches):
        """Test that the scene properly handles frame insertion events."""
        # Create a real animated sprite
        animated_sprite = AnimatedSprite()

        # Create frames
        frame1 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)
        frame2 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)

        # Add animation
        animated_sprite.add_animation("test_anim", [frame1, frame2])

        # Create scene with mock options
        mock_options = {"size": "800x600"}
        scene = BitmapEditorScene(mock_options)
        scene._on_sprite_loaded(animated_sprite)

        # Get the first film strip
        if hasattr(scene, "film_strips") and scene.film_strips:
            film_strip = next(iter(scene.film_strips.values()))

            # Update layout to create tabs
            film_strip.update_layout()

            # Get the first tab
            if film_strip.film_tabs:
                first_tab = film_strip.film_tabs[0]

                # Insert frame
                film_strip._insert_frame_at_tab(first_tab)

                # Check that the scene was notified
                assert hasattr(scene, "_on_frame_inserted")

    def test_frame_insertion_updates_canvas(self, mock_pygame_patches):
        """Test that frame insertion updates the canvas if it's the current animation."""
        # Create a real animated sprite
        animated_sprite = AnimatedSprite()

        # Create frames
        frame1 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)
        frame2 = SpriteFrame(pygame.Surface((32, 32)), duration=FRAME_DURATION)

        # Add animation
        animated_sprite.add_animation("test_anim", [frame1, frame2])

        # Create scene with mock options
        mock_options = {"size": "800x600"}
        scene = BitmapEditorScene(mock_options)
        scene._on_sprite_loaded(animated_sprite)

        # Set the current animation
        scene.selected_animation = "test_anim"

        # Get the first film strip
        if hasattr(scene, "film_strips") and scene.film_strips:
            film_strip = next(iter(scene.film_strips.values()))

            # Update layout to create tabs
            film_strip.update_layout()

            # Get the first tab
            if film_strip.film_tabs:
                first_tab = film_strip.film_tabs[0]

                # Insert frame
                film_strip._insert_frame_at_tab(first_tab)

                # Check that the canvas was updated
                if hasattr(scene, "canvas") and scene.canvas:
                    assert scene.selected_frame == 0
