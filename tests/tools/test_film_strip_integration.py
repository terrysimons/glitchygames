"""Film strip integration tests with animated canvas."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.sprites import AnimatedSprite
from glitchygames.tools import bitmappy, film_strip

from mocks.test_mock_factory import MockFactory

# Test constants to avoid magic values
MIN_FILM_STRIP_WIDTH = 300
FRAME_INDEX_2 = 2
FRAME_SIZE = 32
MAGENTA_PIXELS = (255, 0, 255)
FRAME_DURATION = 0.5
UPDATE_ITERATIONS = 10
CLICK_OFFSET = 50
PIXEL_SIZE = 16
PIXELS_ACROSS = 32
PIXELS_TALL = 32
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 600
CANVAS_OFFSET = 20
MIN_HEIGHT_OFFSET = 20


class TestFilmStripIntegration:
    """Test film strip integration with animated canvas."""

    @classmethod
    def setup_class(cls):
        """Set up pygame mocks for all tests."""
        cls.patchers = MockFactory.setup_pygame_mocks()
        for patcher in cls.patchers:
            patcher.start()

    @classmethod
    def teardown_class(cls):
        """Tear down pygame mocks."""
        MockFactory.teardown_pygame_mocks(cls.patchers)

    def test_film_strip_canvas_integration(self):
        """Test film strip integration with animated canvas through scene."""
        # Create mock animated sprite
        mock_sprite = MockFactory.create_animated_sprite_mock()

        # Create scene with mock sprite
        with patch("pygame.display.get_surface") as mock_display:
            mock_display.return_value = Mock()
            mock_display.return_value.get_width.return_value = DISPLAY_WIDTH
            mock_display.return_value.get_height.return_value = DISPLAY_HEIGHT

            scene = bitmappy.BitmapEditorScene(
                options={"pixels_across": PIXELS_ACROSS, "pixels_tall": PIXELS_TALL,
                        "pixel_size": PIXEL_SIZE}
            )

            # Load the sprite
            scene._on_sprite_loaded(mock_sprite)

            # Test that film strip is created through scene
            assert hasattr(scene, "film_strips")
            assert len(scene.film_strips) > 0

            # Test backward compatibility - canvas should have film_strip attribute
            assert hasattr(scene.canvas, "film_strip")
            assert isinstance(scene.canvas.film_strip, film_strip.FilmStripWidget)

            # Test that film strip has the animated sprite
            assert scene.canvas.film_strip.animated_sprite is not None

    def test_film_strip_sprite_creation(self):
        """Test film strip sprite creation through scene."""
        mock_sprite = MockFactory.create_animated_sprite_mock()

        # Create scene with mock sprite
        with patch("pygame.display.get_surface") as mock_display:
            mock_display.return_value = Mock()
            mock_display.return_value.get_width.return_value = DISPLAY_WIDTH
            mock_display.return_value.get_height.return_value = DISPLAY_HEIGHT

            scene = bitmappy.BitmapEditorScene(
                options={"pixels_across": PIXELS_ACROSS, "pixels_tall": PIXELS_TALL,
                        "pixel_size": PIXEL_SIZE}
            )

            # Load the sprite
            scene._on_sprite_loaded(mock_sprite)

            # Test that film strip sprites are created through scene
            assert hasattr(scene, "film_strip_sprites")
            assert len(scene.film_strip_sprites) > 0

            # Test backward compatibility - canvas should have film_strip_sprite attribute
            assert hasattr(scene.canvas, "film_strip_sprite")
            assert isinstance(scene.canvas.film_strip_sprite, bitmappy.FilmStripSprite)

            # Test that film strip sprite has the widget
            assert scene.canvas.film_strip_sprite.film_strip_widget == scene.canvas.film_strip

    def test_film_strip_positioning(self):
        """Test film strip positioning relative to canvas through scene."""
        mock_sprite = MockFactory.create_animated_sprite_mock()

        # Create scene with mock sprite
        with patch("pygame.display.get_surface") as mock_display:
            mock_display.return_value = Mock()
            mock_display.return_value.get_width.return_value = DISPLAY_WIDTH
            mock_display.return_value.get_height.return_value = DISPLAY_HEIGHT

            scene = bitmappy.BitmapEditorScene(
                options={"pixels_across": PIXELS_ACROSS, "pixels_tall": PIXELS_TALL,
                        "pixel_size": PIXEL_SIZE}
            )

            # Load the sprite
            scene._on_sprite_loaded(mock_sprite)

            # Test film strip positioning through scene
            film_strip = scene.canvas.film_strip
            # 20px to the right
            assert film_strip.rect.x == scene.canvas.rect.right + CANVAS_OFFSET
            # Same vertical position
            assert film_strip.rect.y == scene.canvas.rect.y

            # Test film strip sprite positioning
            film_strip_sprite = scene.canvas.film_strip_sprite
            assert film_strip_sprite.rect.x == film_strip.rect.x
            assert film_strip_sprite.rect.y == film_strip.rect.y

    def test_film_strip_width_calculation(self):
        """Test film strip width calculation through scene."""
        mock_sprite = MockFactory.create_animated_sprite_mock()

        # Create scene with mock sprite
        with patch("pygame.display.get_surface") as mock_display:
            mock_display.return_value = Mock()
            mock_display.return_value.get_width.return_value = DISPLAY_WIDTH
            mock_display.return_value.get_height.return_value = DISPLAY_HEIGHT

            scene = bitmappy.BitmapEditorScene(
                options={"pixels_across": PIXELS_ACROSS, "pixels_tall": PIXELS_TALL,
                        "pixel_size": PIXEL_SIZE}
            )

            # Load the sprite
            scene._on_sprite_loaded(mock_sprite)

            # Test that film strip has appropriate width
            film_strip = scene.canvas.film_strip
            # Minimum width
            assert film_strip.rect.width >= MIN_FILM_STRIP_WIDTH
            assert film_strip.rect.width > 0

    def test_film_strip_height_calculation(self):
        """Test film strip height calculation."""
        mock_sprite = MockFactory.create_animated_sprite_mock()

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={"pixels_across": PIXELS_ACROSS, "pixels_tall": PIXELS_TALL,
                    "pixel_size": PIXEL_SIZE}
        )
        scene._on_sprite_loaded(mock_sprite)

        # Get the first film strip from the new dictionary-based architecture
        film_strip = next(iter(scene.film_strips.values()))
        assert film_strip.rect.height > 0

        # Height should be reasonable for the number of animations
        assert film_strip.rect.height > 0
        # Height should be at least the minimum for one animation
        min_height = (film_strip.animation_label_height +
                     film_strip.frame_height + MIN_HEIGHT_OFFSET)
        assert film_strip.rect.height >= min_height

    def test_film_strip_frame_selection_integration(self):
        """Test film strip frame selection integration with canvas."""
        mock_sprite = MockFactory.create_animated_sprite_mock()
        canvas = bitmappy.AnimatedCanvasSprite(
            animated_sprite=mock_sprite,
            x=0, y=0,
            pixels_across=PIXELS_ACROSS, pixels_tall=PIXELS_TALL,
            pixel_width=PIXEL_SIZE, pixel_height=PIXEL_SIZE
        )

        # Test initial state
        assert not canvas.current_animation
        assert canvas.current_frame == 0

        # Test setting current frame through film strip
        if mock_sprite._animations:
            anim_name = next(iter(mock_sprite._animations.keys()))
            canvas.show_frame(anim_name, 0)
            assert canvas.current_animation == anim_name
            assert canvas.current_frame == 0

    def test_film_strip_click_integration(self):
        """Test film strip click integration with canvas."""
        mock_sprite = MockFactory.create_animated_sprite_mock()

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={"pixels_across": PIXELS_ACROSS, "pixels_tall": PIXELS_TALL,
                    "pixel_size": PIXEL_SIZE}
        )
        scene._on_sprite_loaded(mock_sprite)

        # Get the first film strip and sprite from the new dictionary-based architecture
        film_strip = next(iter(scene.film_strips.values()))
        film_strip_sprite = next(iter(scene.film_strip_sprites.values()))

        # Create mock click event
        mock_event = Mock()
        mock_event.pos = (film_strip_sprite.rect.x + CLICK_OFFSET,
                         film_strip_sprite.rect.y + CLICK_OFFSET)

        # Get the actual animation name from the mock sprite
        animation_name = next(iter(mock_sprite._animations.keys()))

        # Test click handling
        with patch.object(film_strip, "handle_click", return_value=(animation_name, 1)):
            film_strip_sprite.on_left_mouse_button_down_event(mock_event)

            # Should update canvas to show the selected frame
            assert scene.canvas.current_animation == animation_name
            assert scene.canvas.current_frame == 1

    def test_film_strip_animation_preview_integration(self):
        """Test film strip animation preview integration."""
        mock_sprite = MockFactory.create_animated_sprite_mock()

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={"pixels_across": PIXELS_ACROSS, "pixels_tall": PIXELS_TALL,
                    "pixel_size": PIXEL_SIZE}
        )
        scene._on_sprite_loaded(mock_sprite)

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

        # Create mock frames with proper image data
        def create_mock_frame(duration=FRAME_DURATION):
            frame = Mock()
            frame.duration = duration
            frame.image = Mock()
            frame.image.get_size.return_value = (FRAME_SIZE, FRAME_SIZE)
            frame.pixels = [MAGENTA_PIXELS] * (FRAME_SIZE * FRAME_SIZE)
            return frame

        # Add frames to the animated sprite
        frames = [create_mock_frame(FRAME_DURATION),
                 create_mock_frame(FRAME_DURATION),
                 create_mock_frame(FRAME_DURATION)]
        animated_sprite._animations = {"test_anim": frames}
        animated_sprite._animation_order = ["test_anim"]

        # Use the proper API to set animation
        animated_sprite.set_animation("test_anim")
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

        # Create a mock animated sprite with proper frame durations
        def create_mock_frame(duration=FRAME_DURATION):
            frame = Mock()
            frame.duration = duration
            return frame

        animated_sprite = Mock()
        animated_sprite._animations = {
            "test_anim": [
                create_mock_frame(FRAME_DURATION),
                create_mock_frame(FRAME_DURATION),
                create_mock_frame(FRAME_DURATION)
            ]
        }
        animated_sprite._animation_order = ["test_anim"]
        animated_sprite.current_animation = "test_anim"
        animated_sprite.current_frame = 0
        animated_sprite.is_looping = True
        animated_sprite.is_playing = True

        # Set up the film strip
        film_strip_widget.set_animated_sprite(animated_sprite)

        # Test that preview timing is initialized
        assert "test_anim" in film_strip_widget.preview_animation_times
        assert "test_anim" in film_strip_widget.preview_animation_speeds
        assert "test_anim" in film_strip_widget.preview_frame_durations

        # Test animation timing update
        initial_time = film_strip_widget.preview_animation_times["test_anim"]
        film_strip_widget.update_animations(0.1)
        new_time = film_strip_widget.preview_animation_times["test_anim"]

        # Time should have advanced
        assert new_time > initial_time

        # Test getting current preview frame
        frame_idx = film_strip_widget.get_current_preview_frame("test_anim")
        assert isinstance(frame_idx, int)
        assert frame_idx >= 0

    def test_film_strip_animation_with_real_sprite(self):
        """Test film strip animation with a real animated sprite."""
        # Create a real animated sprite
        animated_sprite = AnimatedSprite()

        # Create mock frames with proper structure
        def create_mock_frame(duration=FRAME_DURATION):
            frame = Mock()
            frame.duration = duration
            frame.image = Mock()
            frame.image.get_size.return_value = (FRAME_SIZE, FRAME_SIZE)
            frame.pixels = [MAGENTA_PIXELS] * (FRAME_SIZE * FRAME_SIZE)
            return frame

        frames = [create_mock_frame(FRAME_DURATION),
                 create_mock_frame(FRAME_DURATION),
                 create_mock_frame(FRAME_DURATION)]
        animated_sprite._animations = {"test_anim": frames}
        animated_sprite._animation_order = ["test_anim"]

        # Use the proper API to set animation
        animated_sprite.set_animation("test_anim")
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
        preview_frame = film_strip_widget.get_current_preview_frame("test_anim")
        assert isinstance(preview_frame, int)
        assert preview_frame >= 0

    def test_film_strip_layout_calculation_integration(self):
        """Test film strip layout calculation integration."""
        mock_sprite = MockFactory.create_animated_sprite_mock()

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={"pixels_across": PIXELS_ACROSS, "pixels_tall": PIXELS_TALL,
                    "pixel_size": PIXEL_SIZE}
        )
        scene._on_sprite_loaded(mock_sprite)

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
        mock_sprite = MockFactory.create_animated_sprite_mock()

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={"pixels_across": PIXELS_ACROSS, "pixels_tall": PIXELS_TALL,
                    "pixel_size": PIXEL_SIZE}
        )
        scene._on_sprite_loaded(mock_sprite)

        # Get the first film strip from the new dictionary-based architecture
        film_strip = next(iter(scene.film_strips.values()))
        film_strip.update_scroll_for_frame(FRAME_INDEX_2)

        # Should update scroll offset
        assert hasattr(film_strip, "scroll_offset")
        assert film_strip.scroll_offset >= 0

    def test_film_strip_rendering_integration(self):
        """Test film strip rendering integration."""
        mock_sprite = MockFactory.create_animated_sprite_mock()

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={"pixels_across": PIXELS_ACROSS, "pixels_tall": PIXELS_TALL,
                    "pixel_size": PIXEL_SIZE}
        )
        scene._on_sprite_loaded(mock_sprite)

        # Get the first film strip from the new dictionary-based architecture
        film_strip = next(iter(scene.film_strips.values()))
        assert callable(film_strip.render)
        assert callable(film_strip.render_frame_thumbnail)
        assert callable(film_strip.render_sprocket_separator)
        assert callable(film_strip.render_preview)

    def test_film_strip_parent_canvas_integration(self):
        """Test film strip parent canvas integration."""
        mock_sprite = MockFactory.create_animated_sprite_mock()

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={"pixels_across": PIXELS_ACROSS, "pixels_tall": PIXELS_TALL,
                    "pixel_size": PIXEL_SIZE}
        )
        scene._on_sprite_loaded(mock_sprite)

        # Get the first film strip and sprite from the new dictionary-based architecture
        film_strip = next(iter(scene.film_strips.values()))
        film_strip_sprite = next(iter(scene.film_strip_sprites.values()))

        # Test that film strip has parent canvas
        assert hasattr(film_strip, "parent_canvas")

        # Test that film strip sprite has parent canvas
        assert hasattr(film_strip_sprite, "parent_canvas")

    def test_film_strip_dirty_flag_integration(self):
        """Test film strip dirty flag integration."""
        mock_sprite = MockFactory.create_animated_sprite_mock()

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={"pixels_across": PIXELS_ACROSS, "pixels_tall": PIXELS_TALL,
                    "pixel_size": PIXEL_SIZE}
        )
        scene._on_sprite_loaded(mock_sprite)

        # Get the first film strip and sprite from the new dictionary-based architecture
        film_strip = next(iter(scene.film_strips.values()))
        film_strip_sprite = next(iter(scene.film_strip_sprites.values()))

        # Test dirty flag handling
        assert film_strip_sprite.dirty >= 1  # Should be dirty initially

        # Test mark_dirty functionality
        film_strip.mark_dirty()
        assert hasattr(film_strip, "_force_redraw")
        assert film_strip._force_redraw is True

    def test_film_strip_multiple_animations_integration(self):
        """Test film strip with multiple animations."""
        # Create mock sprite with multiple animations
        mock_sprite = MockFactory.create_animated_sprite_mock()
        # Add more animations to the mock
        mock_sprite._animations["walk"] = [Mock() for _ in range(3)]
        mock_sprite._animations["jump"] = [Mock() for _ in range(2)]
        mock_sprite._animations["idle"] = [Mock() for _ in range(4)]

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={"pixels_across": PIXELS_ACROSS, "pixels_tall": PIXELS_TALL,
                    "pixel_size": PIXEL_SIZE}
        )

        # Use centralized mock factory to create a proper canvas
        mock_factory = MockFactory()
        mock_canvas = mock_factory.create_canvas_mock()
        scene.canvas = mock_canvas

        scene._on_sprite_loaded(mock_sprite)

        # In the new multi-film strip architecture, each animation gets its own film strip
        # So we should have 4 film strips (one for each animation)
        assert len(scene.film_strips) == len(mock_sprite._animations)
        assert len(scene.film_strip_sprites) == len(mock_sprite._animations)

        # Each film strip should have layouts for its own animation
        for film_strip_widget in scene.film_strips.values():
            assert len(film_strip_widget.animation_layouts) > 0
            assert len(film_strip_widget.frame_layouts) > 0

    def test_film_strip_edge_cases_integration(self):
        """Test film strip edge cases integration."""
        # Test with empty sprite
        empty_sprite = Mock()
        empty_sprite._animations = {}
        empty_sprite._animation_order = []
        empty_sprite.frames = {}  # Add frames attribute
        # Add get_pixel_data method for empty sprite
        empty_sprite.get_pixel_data.return_value = [(0, 0, 0)] * (FRAME_SIZE * FRAME_SIZE)

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={"pixels_across": PIXELS_ACROSS, "pixels_tall": PIXELS_TALL,
                    "pixel_size": PIXEL_SIZE}
        )
        scene._on_sprite_loaded(empty_sprite)

        # Should handle empty sprite gracefully - no film strips should be created
        assert len(scene.film_strips) == 0
        assert len(scene.film_strip_sprites) == 0

    def test_film_strip_coordinate_conversion_integration(self):
        """Test film strip coordinate conversion integration."""
        mock_sprite = MockFactory.create_animated_sprite_mock()

        # Create scene and load sprite to properly initialize film strips
        scene = bitmappy.BitmapEditorScene(
            options={"pixels_across": PIXELS_ACROSS, "pixels_tall": PIXELS_TALL,
                    "pixel_size": PIXEL_SIZE}
        )
        scene._on_sprite_loaded(mock_sprite)

        # Get the first film strip and sprite from the new dictionary-based architecture
        film_strip_sprite = next(iter(scene.film_strip_sprites.values()))
        film_strip_widget = next(iter(scene.film_strips.values()))

        # Create mock event
        mock_event = Mock()
        mock_event.pos = (film_strip_sprite.rect.x + CLICK_OFFSET,
                         film_strip_sprite.rect.y + CLICK_OFFSET)

        # Test coordinate conversion
        with patch.object(film_strip_widget, "handle_click",
                        return_value=("idle", 1)) as mock_handle_click:
            film_strip_sprite.on_left_mouse_button_down_event(mock_event)

            # Should convert screen coordinates to film strip coordinates
            expected_x = mock_event.pos[0] - film_strip_sprite.rect.x
            expected_y = mock_event.pos[1] - film_strip_sprite.rect.y
            mock_handle_click.assert_called_once_with((expected_x, expected_y))
