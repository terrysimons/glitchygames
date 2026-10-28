"""Film strip integration tests with animated canvas."""

import pygame

# Import constants from base class
from src.apps.bitmappy.tests.film_strip_support import (
    FRAME_DURATION,
    FRAME_INDEX_2,
    MIN_FILM_STRIP_WIDTH,
    MIN_HEIGHT_OFFSET,
    PIXEL_SIZE,
    PIXELS_ACROSS,
    PIXELS_TALL,
    UPDATE_ITERATIONS,
    FilmStripTestBase,
    frame_color_for_index,
    make_real_animated_sprite,
    make_real_frame,
)

from bitmappy import editor as bitmappy
from bitmappy import film_strip
from bitmappy.film_strip_sprite import FilmStripSprite
from glitchygames import events
from glitchygames.sprites import AnimatedSprite

# A frame colour far from magenta: the film strip draws magenta pixels as transparent
THUMBNAIL_BASE_COLOR = (200, 40, 10)


def left_click_event(*, position: tuple[int, int]) -> events.HashableEvent:
    """Build a real left MOUSEBUTTONDOWN event.

    Returns:
        The event.

    """
    return events.HashableEvent(pygame.MOUSEBUTTONDOWN, pos=position, button=1)


def screen_center_of_frame(*, film_strip_sprite, animation_name, frame_index):
    """Return the screen position of the centre of a frame's thumbnail in a film strip.

    Returns:
        tuple[int, int]: The screen position.

    """
    frame_rect = film_strip_sprite.film_strip_widget.frame_layouts[animation_name, frame_index]
    return (
        film_strip_sprite.rect.x + frame_rect.centerx,
        film_strip_sprite.rect.y + frame_rect.centery,
    )


class TestFilmStripIntegration(FilmStripTestBase):
    """Test film strip integration with animated canvas."""

    def test_film_strip_canvas_integration(self):
        """Test film strip integration with animated canvas through scene."""
        # Use optimized setup
        scene, _ = self.setup_scene_with_sprite()

        # Test that film strip is created through scene
        assert hasattr(scene, 'film_strips')
        assert len(scene.film_strips) > 0

        # Film strips are stored on the scene, not on the canvas
        first_film_strip = next(iter(scene.film_strips.values()))
        assert isinstance(first_film_strip, film_strip.FilmStripWidget)

        # Test that film strip has the animated sprite
        assert first_film_strip.animated_sprite is not None

    def test_film_strip_sprite_creation(self):
        """Test film strip sprite creation through scene."""
        # Use optimized setup
        scene, _ = self.setup_scene_with_sprite()

        # Test that film strip sprites are created through scene
        assert hasattr(scene, 'film_strip_sprites')
        assert len(scene.film_strip_sprites) > 0

        # Film strip sprites are stored on the scene, keyed by animation name
        first_film_strip_sprite = next(iter(scene.film_strip_sprites.values()))
        assert isinstance(first_film_strip_sprite, FilmStripSprite)

        # Test that film strip sprite has the widget matching its corresponding film strip
        first_film_strip = next(iter(scene.film_strips.values()))
        assert first_film_strip_sprite.film_strip_widget == first_film_strip

    def test_film_strip_positioning(self):
        """Test film strip positioning relative to canvas through scene."""
        # Use optimized setup
        scene, _ = self.setup_scene_with_sprite()

        # Film strips are stored on the scene, not on the canvas
        first_film_strip = next(iter(scene.film_strips.values()))
        first_film_strip_sprite = next(iter(scene.film_strip_sprites.values()))

        # Check that film strip is positioned to the right of canvas
        assert first_film_strip.rect is not None
        assert scene.canvas.rect is not None
        assert first_film_strip_sprite.rect is not None
        assert first_film_strip.rect.x >= scene.canvas.rect.right
        assert first_film_strip.rect.y == scene.canvas.rect.y

        # Test film strip sprite positioning matches its widget
        assert first_film_strip_sprite.rect.x == first_film_strip.rect.x
        assert first_film_strip_sprite.rect.y == first_film_strip.rect.y

    def test_film_strip_width_calculation(self):
        """Test film strip width calculation through scene."""
        # Use optimized setup (base class already initializes pygame display)
        scene, _ = self.setup_scene_with_sprite()

        # Film strips are stored on the scene, not on the canvas
        first_film_strip = next(iter(scene.film_strips.values()))

        # Minimum width
        assert first_film_strip.rect is not None
        assert first_film_strip.rect.width >= MIN_FILM_STRIP_WIDTH
        assert first_film_strip.rect.width > 0

    def test_film_strip_height_calculation(self):
        """Test film strip height calculation."""
        animated_sprite = make_real_animated_sprite()

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={
                'pixels_across': PIXELS_ACROSS,
                'pixels_tall': PIXELS_TALL,
                'pixel_size': PIXEL_SIZE,
            },
        )
        scene.film_strip_coordinator.on_sprite_loaded(animated_sprite)

        # Get the first film strip from the new dictionary-based architecture
        film_strip = next(iter(scene.film_strips.values()))
        assert film_strip.rect is not None
        assert film_strip.rect.height > 0

        # Height should be reasonable for the number of animations
        assert film_strip.rect.height > 0
        # Height should be at least the minimum for one animation
        min_height = film_strip.animation_label_height + film_strip.frame_height + MIN_HEIGHT_OFFSET
        assert film_strip.rect.height >= min_height

    def test_film_strip_frame_selection_integration(self):
        """Test film strip frame selection integration with canvas."""
        animated_sprite = make_real_animated_sprite()
        # Clear the current animation to test initial state
        animated_sprite.frame_manager.current_animation = ''
        canvas = bitmappy.AnimatedCanvasSprite(
            animated_sprite=animated_sprite,
            x=0,
            y=0,
            pixels_across=PIXELS_ACROSS,
            pixels_tall=PIXELS_TALL,
            pixel_width=PIXEL_SIZE,
            pixel_height=PIXEL_SIZE,
        )

        # Test initial state
        assert not canvas.current_animation
        assert canvas.current_frame == 0

        # Test setting current frame through film strip
        if animated_sprite._animations:
            anim_name = next(iter(animated_sprite._animations.keys()))
            canvas.show_frame(anim_name, 0)
            assert canvas.current_animation == anim_name
            assert canvas.current_frame == 0

    def test_film_strip_click_integration(self):
        """Test film strip click integration with canvas."""
        animated_sprite = make_real_animated_sprite()

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={
                'pixels_across': PIXELS_ACROSS,
                'pixels_tall': PIXELS_TALL,
                'pixel_size': PIXEL_SIZE,
            },
        )
        scene.film_strip_coordinator.on_sprite_loaded(animated_sprite)

        film_strip_sprite = next(iter(scene.film_strip_sprites.values()))
        animation_name = next(iter(animated_sprite.animations))

        # Click the real thumbnail of frame 1
        film_strip_sprite.on_left_mouse_button_down_event(
            left_click_event(
                position=screen_center_of_frame(
                    film_strip_sprite=film_strip_sprite,
                    animation_name=animation_name,
                    frame_index=1,
                ),
            ),
        )

        # Should update canvas to show the selected frame
        assert scene.canvas.current_animation == animation_name
        assert scene.canvas.current_frame == 1

    def test_film_strip_animation_preview_integration(self):
        """Test film strip animation preview integration."""
        animated_sprite = make_real_animated_sprite()

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={
                'pixels_across': PIXELS_ACROSS,
                'pixels_tall': PIXELS_TALL,
                'pixel_size': PIXEL_SIZE,
            },
        )
        scene.film_strip_coordinator.on_sprite_loaded(animated_sprite)

        # Get the first film strip from the new dictionary-based architecture
        film_strip = next(iter(scene.film_strips.values()))
        assert len(film_strip.preview_animation_times) > 0
        assert len(film_strip.preview_animation_speeds) > 0
        assert len(film_strip.preview_frame_durations) > 0

        # Test animation timing update
        film_strip.update_animations(0.1)

        # Test getting current preview frame for each animation
        for anim_name in film_strip.preview_animation_times:
            frame_idx = film_strip.get_current_preview_frame(anim_name)
            assert isinstance(frame_idx, int)
            assert frame_idx >= 0

    def test_animated_sprite_frame_advancement(self):
        """Test that animated sprites actually advance frames when updated."""
        # Create a real animated sprite with proper frame data
        animated_sprite = AnimatedSprite()

        frames = [make_real_frame(duration=FRAME_DURATION) for _ in range(3)]
        animated_sprite.add_animation('test_anim', frames)

        # Use the proper API to set animation
        animated_sprite.set_animation('test_anim')
        animated_sprite._is_looping = True
        animated_sprite.play()  # Start playing

        # Test frame advancement
        initial_frame = animated_sprite.current_frame
        assert initial_frame == 0

        # Update with small delta time - should not advance yet
        animated_sprite.update(0.1)
        frame_after_short = animated_sprite.current_frame
        assert frame_after_short == 0

        # Update with longer delta time - should advance
        # Total 0.7s, should advance past first frame (0.5s)
        animated_sprite.update(0.6)
        frame_after_long = animated_sprite.current_frame
        assert frame_after_long == 1

        # Update more to test looping
        # Total 1.7s, should loop back
        animated_sprite.update(1.0)
        frame_after_loop = animated_sprite.current_frame
        assert frame_after_loop == FRAME_INDEX_2

    def test_film_strip_animation_timing(self):
        """Test that film strip animation timing works correctly."""
        # Create a film strip widget
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 400, 100)

        animated_sprite = AnimatedSprite()
        animated_sprite.add_animation(
            'test_anim',
            [make_real_frame(duration=FRAME_DURATION) for _ in range(3)],
        )
        animated_sprite.set_animation('test_anim')
        animated_sprite.play()

        # Set up the film strip
        film_strip_widget.set_animated_sprite(animated_sprite)

        # Test that preview timing is initialized
        assert 'test_anim' in film_strip_widget.preview_animation_times
        assert 'test_anim' in film_strip_widget.preview_animation_speeds
        assert 'test_anim' in film_strip_widget.preview_frame_durations

        # Test animation timing update
        initial_time = film_strip_widget.preview_animation_times['test_anim']
        film_strip_widget.update_animations(0.1)
        new_time = film_strip_widget.preview_animation_times['test_anim']

        # Time should have advanced
        assert new_time > initial_time

        # Test getting current preview frame
        frame_idx = film_strip_widget.get_current_preview_frame('test_anim')
        assert isinstance(frame_idx, int)
        assert frame_idx >= 0

    def test_film_strip_animation_with_real_sprite(self):
        """Test film strip animation with a real animated sprite."""
        # Create a real animated sprite
        animated_sprite = AnimatedSprite()

        frames = [make_real_frame(duration=FRAME_DURATION) for _ in range(3)]
        animated_sprite.add_animation('test_anim', frames)

        # Use the proper API to set animation
        animated_sprite.set_animation('test_anim')
        animated_sprite._is_looping = True
        animated_sprite.play()  # Start playing

        # Create film strip widget
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 400, 100)
        film_strip_widget.set_animated_sprite(animated_sprite)

        # Test multiple updates to see if frames advance
        frame_changes = 0
        for _ in range(UPDATE_ITERATIONS):
            old_frame = animated_sprite.current_frame
            film_strip_widget.update_animations(0.1)
            new_frame = animated_sprite.current_frame

            if old_frame != new_frame:
                frame_changes += 1

        # Should have seen some frame changes
        assert frame_changes > 0

        # Test preview frame calculation
        preview_frame = film_strip_widget.get_current_preview_frame('test_anim')
        assert isinstance(preview_frame, int)
        assert preview_frame >= 0

    def test_film_strip_layout_calculation_integration(self):
        """Test film strip layout calculation integration."""
        animated_sprite = make_real_animated_sprite()

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={
                'pixels_across': PIXELS_ACROSS,
                'pixels_tall': PIXELS_TALL,
                'pixel_size': PIXEL_SIZE,
            },
        )
        scene.film_strip_coordinator.on_sprite_loaded(animated_sprite)

        # Get the first film strip from the new dictionary-based architecture
        film_strip = next(iter(scene.film_strips.values()))
        assert len(film_strip.frame_layouts) > 0
        assert len(film_strip.animation_layouts) > 0
        assert len(film_strip.preview_rects) > 0

        # Test layout calculation methods
        film_strip._calculate_layout()
        assert len(film_strip.frame_layouts) > 0
        assert len(film_strip.animation_layouts) > 0
        assert len(film_strip.preview_rects) > 0

    def test_film_strip_scroll_integration(self):
        """Test film strip scroll integration."""
        animated_sprite = make_real_animated_sprite()

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={
                'pixels_across': PIXELS_ACROSS,
                'pixels_tall': PIXELS_TALL,
                'pixel_size': PIXEL_SIZE,
            },
        )
        scene.film_strip_coordinator.on_sprite_loaded(animated_sprite)

        # Get the first film strip from the new dictionary-based architecture
        film_strip = next(iter(scene.film_strips.values()))
        film_strip.update_scroll_for_frame(FRAME_INDEX_2)

        # Should update scroll offset
        assert hasattr(film_strip, 'scroll_offset')
        assert film_strip.scroll_offset >= 0

    def test_film_strip_rendering_integration(self):
        """Test that rendering the film strip draws each frame's thumbnail in its own colour."""
        animated_sprite = make_real_animated_sprite(base_color=THUMBNAIL_BASE_COLOR)

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={
                'pixels_across': PIXELS_ACROSS,
                'pixels_tall': PIXELS_TALL,
                'pixel_size': PIXEL_SIZE,
            },
        )
        scene.film_strip_coordinator.on_sprite_loaded(animated_sprite)

        # Get the first film strip from the new dictionary-based architecture
        film_strip = next(iter(scene.film_strips.values()))
        surface = pygame.Surface(film_strip.rect.size, flags=0, depth=32)

        film_strip.render(surface)

        for (animation_name, frame_index), frame_rect in film_strip.frame_layouts.items():
            assert animation_name == 'idle'
            drawn_color = tuple(surface.get_at(frame_rect.center))[:3]
            assert drawn_color == frame_color_for_index(
                base_color=THUMBNAIL_BASE_COLOR,
                frame_index=frame_index,
            )

    def test_film_strip_renders_sprocket_separators_between_animations(self):
        """Test that a strip showing two animations draws a sprocket separator between them."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 400, 120)
        film_strip_widget.set_animated_sprite(
            make_real_animated_sprite(
                frame_counts={'idle': 2, 'walk': 2},
                base_color=THUMBNAIL_BASE_COLOR,
            ),
        )
        assert len(film_strip_widget.sprocket_layouts) == 1
        sprocket_rect = film_strip_widget.sprocket_layouts[0]
        surface = pygame.Surface(film_strip_widget.rect.size, flags=0, depth=32)

        film_strip_widget.render(surface)

        # A row through the centre of a pair of perforations (one every 8 pixels from y=4)
        hole_center_y = sprocket_rect.y + 4 + 8 * 6
        assert hole_center_y < sprocket_rect.bottom - 4
        sprocket_color = film_strip_widget.sprocket_color
        border_color = film_strip_widget.frame_border

        def drawn(x):
            return tuple(surface.get_at((sprocket_rect.x + x, hole_center_y)))[:3]

        assert drawn(0) == border_color
        assert drawn(film_strip_widget.sprocket_width - 1) == border_color
        # The left and right perforations, at x=6 and x=14
        assert drawn(6) == sprocket_color
        assert drawn(14) == sprocket_color
        assert drawn(10) == film_strip_widget.film_background

    def test_film_strip_parent_canvas_integration(self):
        """Test film strip parent canvas integration."""
        animated_sprite = make_real_animated_sprite()

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={
                'pixels_across': PIXELS_ACROSS,
                'pixels_tall': PIXELS_TALL,
                'pixel_size': PIXEL_SIZE,
            },
        )
        scene.film_strip_coordinator.on_sprite_loaded(animated_sprite)

        # Get the first film strip and sprite from the new dictionary-based architecture
        film_strip = next(iter(scene.film_strips.values()))
        film_strip_sprite = next(iter(scene.film_strip_sprites.values()))

        # Test that film strip has parent canvas
        assert hasattr(film_strip, 'parent_canvas')

        # Test that film strip sprite has parent canvas
        assert hasattr(film_strip_sprite, 'parent_canvas')

    def test_film_strip_dirty_flag_integration(self):
        """Test film strip dirty flag integration."""
        animated_sprite = make_real_animated_sprite()

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={
                'pixels_across': PIXELS_ACROSS,
                'pixels_tall': PIXELS_TALL,
                'pixel_size': PIXEL_SIZE,
            },
        )
        scene.film_strip_coordinator.on_sprite_loaded(animated_sprite)

        # Get the first film strip and sprite from the new dictionary-based architecture
        film_strip = next(iter(scene.film_strips.values()))
        film_strip_sprite = next(iter(scene.film_strip_sprites.values()))

        # Test dirty flag handling
        assert film_strip_sprite.dirty >= 1  # Should be dirty initially

        # Test mark_dirty functionality — mark_dirty() renders immediately
        # via force_redraw(), so _force_redraw is consumed (reset to False)
        # and the sprite is marked dirty=1 for LayeredDirty to blit
        film_strip.mark_dirty()
        assert film_strip_sprite.dirty == 1

    def test_film_strip_multiple_animations_integration(self):
        """Test film strip with multiple animations."""
        animated_sprite = make_real_animated_sprite(
            frame_counts={'idle': 4, 'walk': 3, 'jump': 2},
        )

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={
                'pixels_across': PIXELS_ACROSS,
                'pixels_tall': PIXELS_TALL,
                'pixel_size': PIXEL_SIZE,
            },
        )

        scene.film_strip_coordinator.on_sprite_loaded(animated_sprite)

        # Each animation gets its own film strip
        assert set(scene.film_strips) == {'idle', 'walk', 'jump'}
        assert set(scene.film_strip_sprites) == {'idle', 'walk', 'jump'}

        # Each film strip lays out every frame of its own animation
        for animation_name, film_strip_widget in scene.film_strips.items():
            assert len(film_strip_widget.animation_layouts) > 0
            assert sorted(film_strip_widget.frame_layouts) == [
                (animation_name, frame_index)
                for frame_index in range(len(animated_sprite.animations[animation_name]))
            ]

    def test_film_strip_edge_cases_integration(self):
        """Test film strip edge cases integration."""
        # A sprite with no animations
        empty_sprite = AnimatedSprite()

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={
                'pixels_across': PIXELS_ACROSS,
                'pixels_tall': PIXELS_TALL,
                'pixel_size': PIXEL_SIZE,
            },
        )
        scene.film_strip_coordinator.on_sprite_loaded(empty_sprite)

        # Should handle empty sprite gracefully - no film strips should be created
        assert len(scene.film_strips) == 0
        assert len(scene.film_strip_sprites) == 0

    def test_film_strip_coordinate_conversion_integration(self):
        """Test that a screen click is converted to the film strip's own coordinates.

        Clicking the screen position of frame 2's thumbnail must select frame 2, which only
        happens when the click is shifted by the film strip sprite's screen position.
        """
        animated_sprite = make_real_animated_sprite()

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={
                'pixels_across': PIXELS_ACROSS,
                'pixels_tall': PIXELS_TALL,
                'pixel_size': PIXEL_SIZE,
            },
        )
        scene.film_strip_coordinator.on_sprite_loaded(animated_sprite)

        film_strip_sprite = scene.film_strip_sprites['idle']
        # The strip sits away from the screen origin, so a missing conversion is visible
        assert film_strip_sprite.rect.topleft != (0, 0)

        film_strip_sprite.on_left_mouse_button_down_event(
            left_click_event(
                position=screen_center_of_frame(
                    film_strip_sprite=film_strip_sprite,
                    animation_name='idle',
                    frame_index=FRAME_INDEX_2,
                ),
            ),
        )

        assert scene.selected_animation == 'idle'
        assert scene.selected_frame == FRAME_INDEX_2
        assert scene.canvas.current_frame == FRAME_INDEX_2
