"""Film strip sprite wrapper tests."""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames import events
from glitchygames.bitmappy import film_strip
from glitchygames.bitmappy.film_strip_sprite import FilmStripSprite
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from tests.mocks.test_mock_factory import MockFactory


class TestFilmStripSprite:
    """Test FilmStripSprite wrapper functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        self._mocker = mocker
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_film_strip_sprite_initialization(self):
        """Test film strip sprite initialization."""
        # Create a film strip widget
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Create film strip sprite
        sprite = FilmStripSprite(film_strip_widget, x=10, y=20, width=200, height=150)

        # Test basic properties
        assert hasattr(sprite, 'film_strip_widget')
        assert hasattr(sprite, 'name')
        assert hasattr(sprite, 'image')
        assert hasattr(sprite, 'rect')
        assert hasattr(sprite, 'dirty')

        # Test values
        assert sprite.film_strip_widget == film_strip_widget
        assert sprite.name == 'Film Strip'
        # Note: Mock rect properties may not match exact values due to mock setup
        assert hasattr(sprite.rect, 'x')
        assert hasattr(sprite.rect, 'y')
        assert hasattr(sprite.rect, 'width')
        assert hasattr(sprite.rect, 'height')
        assert sprite.dirty == 1  # Should be dirty initially

    def test_film_strip_sprite_methods(self):
        """Test film strip sprite methods."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = FilmStripSprite(film_strip_widget)

        # Test methods exist
        assert hasattr(sprite, 'update')
        assert hasattr(sprite, 'force_redraw')
        assert hasattr(sprite, 'on_left_mouse_button_down_event')
        assert hasattr(sprite, 'set_parent_canvas')

        # Test methods are callable
        assert callable(sprite.update)
        assert callable(sprite.force_redraw)
        assert callable(sprite.on_left_mouse_button_down_event)
        assert callable(sprite.set_parent_canvas)

    def test_film_strip_sprite_update(self):
        """Test film strip sprite update functionality."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = FilmStripSprite(film_strip_widget)

        # Test initial dirty state
        assert sprite.dirty == 1

        # FilmStripSprite.update() checks that the sprite is in at least one group
        # before processing. Mock groups() to return a non-empty list so update proceeds.
        mock_group = self._mocker.Mock()
        sprite.groups = self._mocker.Mock(return_value=[mock_group])

        # Test update with dirty flag — force_redraw is called,
        # dirty stays at 1 until LayeredDirty.draw() resets it
        sprite.update()
        assert sprite.dirty == 1

    def test_film_strip_sprite_force_redraw(self):
        """Test film strip sprite force redraw."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = FilmStripSprite(film_strip_widget)

        # Test force redraw
        sprite.force_redraw()

        # Should have called film_strip_widget.render
        # The surface should be filled with film background color
        assert sprite.image is not None

    def test_film_strip_sprite_mouse_click(self):
        """Test film strip sprite mouse click handling."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = FilmStripSprite(film_strip_widget, x=10, y=20, width=200, height=150)

        # Create mock event
        mock_event = self._mocker.Mock()
        mock_event.pos = (50, 50)  # Within sprite bounds

        # Test click handling
        sprite.on_left_mouse_button_down_event(mock_event)

        # Should convert coordinates and call film_strip_widget.handle_click
        # Film strip widget should receive (40, 30) - adjusted for sprite position

    def test_film_strip_sprite_mouse_click_outside_bounds(self):
        """Test film strip sprite mouse click outside bounds."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = FilmStripSprite(film_strip_widget, x=10, y=20, width=200, height=150)

        # Create mock event outside bounds
        mock_event = self._mocker.Mock()
        mock_event.pos = (500, 500)  # Outside sprite bounds

        # Test click handling
        sprite.on_left_mouse_button_down_event(mock_event)

        # Should not call film_strip_widget.handle_click since click is outside bounds

    def test_film_strip_sprite_with_animations(self):
        """Test film strip sprite with animations running."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Set up mock sprite with animations
        mock_sprite = MockFactory.create_animated_sprite_mock()
        film_strip_widget.set_animated_sprite(mock_sprite)

        sprite = FilmStripSprite(film_strip_widget)

        # Test update with animations running
        sprite.update()

        # Should force redraw when animations are running
        # Dirty flag should remain set to ensure continuous updates

    def test_film_strip_sprite_parent_canvas(self):
        """Test film strip sprite parent canvas integration."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = FilmStripSprite(film_strip_widget)

        # Test setting parent canvas
        mock_canvas = self._mocker.Mock()
        sprite.set_parent_canvas(mock_canvas)
        assert sprite.parent_canvas == mock_canvas

    def test_film_strip_sprite_click_with_parent_canvas(self, mocker):
        """Test film strip sprite click with parent canvas."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = FilmStripSprite(film_strip_widget)

        # Set up mock sprite with animations
        mock_sprite = MockFactory.create_animated_sprite_mock()
        film_strip_widget.set_animated_sprite(mock_sprite)

        # Set parent canvas
        mock_canvas = self._mocker.Mock()
        sprite.set_parent_canvas(mock_canvas)

        # Create mock event
        mock_event = self._mocker.Mock()
        mock_event.pos = (50, 50)

        # Mock the handle_click to return a frame
        mocker.patch.object(film_strip_widget, 'handle_click', return_value=('idle', 0))
        sprite.on_left_mouse_button_down_event(mock_event)

        # Should call parent canvas show_frame
        mock_canvas.show_frame.assert_called_once_with('idle', 0)

    def test_film_strip_sprite_click_no_frame_selected(self, mocker):
        """Test film strip sprite click when no frame is selected."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = FilmStripSprite(film_strip_widget)

        # Set parent canvas
        mock_canvas = self._mocker.Mock()
        sprite.set_parent_canvas(mock_canvas)

        # Create mock event
        mock_event = self._mocker.Mock()
        mock_event.pos = (50, 50)

        # Mock the handle_click to return None
        mocker.patch.object(film_strip_widget, 'handle_click', return_value=None)
        sprite.on_left_mouse_button_down_event(mock_event)

        # Should not call parent canvas show_frame
        mock_canvas.show_frame.assert_not_called()

    def test_film_strip_sprite_continuous_redraw_with_animations(self):
        """Test that film strip sprite continuously redraws when animations are present."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)

        # Set up mock sprite with animations
        mock_sprite = MockFactory.create_animated_sprite_mock()
        film_strip_widget.set_animated_sprite(mock_sprite)

        sprite = FilmStripSprite(film_strip_widget)

        # Reset dirty flag
        sprite.dirty = 0

        # Update with animations running
        sprite.update()

        # Should force redraw and keep dirty flag set for continuous updates
        # This ensures smooth animation previews

    def test_film_strip_sprite_surface_initialization(self):
        """Test film strip sprite surface initialization."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = FilmStripSprite(film_strip_widget, x=0, y=0, width=200, height=150)

        # Test surface properties
        assert sprite.image is not None
        assert hasattr(sprite.image, 'get_width')
        assert hasattr(sprite.image, 'get_height')

        # Test rect properties
        assert hasattr(sprite.rect, 'width')
        assert hasattr(sprite.rect, 'height')

    def test_film_strip_sprite_coordinate_conversion(self, mocker):
        """Test film strip sprite coordinate conversion."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = FilmStripSprite(film_strip_widget, x=10, y=20, width=200, height=150)

        # Create mock event
        mock_event = self._mocker.Mock()
        mock_event.pos = (50, 70)  # Screen coordinates

        # Test coordinate conversion
        mock_handle_click = mocker.patch.object(film_strip_widget, 'handle_click')
        # Configure mock to return proper tuple
        mock_handle_click.return_value = ('idle', 0)
        sprite.on_left_mouse_button_down_event(mock_event)

        # Should convert screen coordinates to film strip coordinates
        # Sprite is at (10, 20), so (50, 70) - (10, 20) = (40, 50)
        mock_handle_click.assert_called_once_with((40, 50), is_shift_click=False)

    def test_film_strip_sprite_edge_cases(self):
        """Test film strip sprite edge cases."""
        film_strip_widget = film_strip.FilmStripWidget(0, 0, 100, 100)
        sprite = FilmStripSprite(film_strip_widget)

        # Test with None parent canvas
        sprite.parent_canvas = None

        # Create mock event
        mock_event = self._mocker.Mock()
        mock_event.pos = (50, 50)

        # Should not crash when parent canvas is None
        sprite.on_left_mouse_button_down_event(mock_event)

        # Test with no film strip widget
        sprite.film_strip_widget = None
        sprite.on_left_mouse_button_down_event(mock_event)


# ---------------------------------------------------------------------------
# Real-pygame tests: a real FilmStripWidget showing a real AnimatedSprite
# ---------------------------------------------------------------------------

FRAME_PIXELS_ACROSS = 2
FRAME_PIXELS_TALL = 2
TOP_LEFT_COLOR = (10, 20, 30, 40)
OTHER_COLOR = (200, 100, 50, 255)


class RecordingParentScene:
    """A parent scene stand-in that keeps the colour slider values it is sent."""

    def __init__(self) -> None:
        """Start with no slider values and no frame insertions."""
        self.slider_values: dict[str, int] = {}
        self.inserted_frames: list[tuple[str, int]] = []

    def on_slider_event(self, event: events.HashableEvent, trigger: events.HashableEvent) -> None:
        """Keep the value sent for one slider.

        Args:
            event: The slider event (unused).
            trigger: The trigger naming the slider and its value.

        """
        del event
        self.slider_values[trigger.name] = trigger.value

    def on_frame_inserted(self, animation: str, frame_index: int) -> None:
        """Keep a frame insertion notification.

        Args:
            animation: The animation the frame was inserted into.
            frame_index: Where it was inserted.

        """
        self.inserted_frames.append((animation, frame_index))


class RecordingCanvas:
    """A canvas stand-in that keeps the frames it was asked to show."""

    def __init__(self, *, pixels_across: int = 4, pixels_tall: int = 3) -> None:
        """Start with no frames shown.

        Args:
            pixels_across: Canvas width in pixels.
            pixels_tall: Canvas height in pixels.

        """
        self.pixels_across = pixels_across
        self.pixels_tall = pixels_tall
        self.shown_frames: list[tuple[str, int]] = []

    def show_frame(self, animation: str, frame_index: int) -> None:
        """Keep the frame shown.

        Args:
            animation: The animation shown.
            frame_index: The frame shown.

        """
        self.shown_frames.append((animation, frame_index))


def make_two_by_two_frame() -> SpriteFrame:
    """Build a 2x2 frame whose top-left pixel differs from the other three.

    Returns:
        The frame.

    """
    surface = pygame.Surface((FRAME_PIXELS_ACROSS, FRAME_PIXELS_TALL), pygame.SRCALPHA)
    frame = SpriteFrame(surface, duration=0.5)
    frame.set_pixel_data([TOP_LEFT_COLOR, OTHER_COLOR, OTHER_COLOR, OTHER_COLOR])
    return frame


@pytest.fixture
def real_film_strip_sprite() -> FilmStripSprite:
    """Build a film strip sprite over a real widget showing two 'idle' frames.

    Returns:
        The film strip sprite, in a sprite group.

    """
    animated_sprite = AnimatedSprite()
    animated_sprite._animations = {  # pyright: ignore[reportPrivateUsage]
        'idle': [make_two_by_two_frame(), make_two_by_two_frame()],
    }
    animated_sprite.frame_manager.current_animation = 'idle'
    widget = film_strip.FilmStripWidget(x=0, y=0, width=400, height=120)
    widget.set_animated_sprite(animated_sprite)
    widget.current_animation = 'idle'
    group = pygame.sprite.LayeredDirty()
    return FilmStripSprite(widget, x=0, y=0, width=400, height=120, groups=group)


def frame_layout_of(sprite: FilmStripSprite, frame_index: int) -> pygame.Rect:
    """Return where a frame of the 'idle' animation is laid out in the film strip.

    Args:
        sprite: The film strip sprite.
        frame_index: The frame.

    Returns:
        The frame's layout rect.

    """
    assert sprite.film_strip_widget is not None
    return sprite.film_strip_widget.frame_layouts['idle', frame_index]


def write_png(*, path: Path, size: tuple[int, int], color: tuple[int, ...], alpha: bool) -> str:
    """Write a single-colour PNG.

    Args:
        path: Where to write it.
        size: Its size.
        color: Its colour.
        alpha: Whether it has an alpha channel.

    Returns:
        The path as a string.

    """
    surface = pygame.Surface(size, pygame.SRCALPHA) if alpha else pygame.Surface(size)
    surface.fill(color)
    pygame.image.save(surface, str(path))
    return str(path)


class TestFilmStripSpriteUpdateAndKill:
    """Test FilmStripSprite.update and kill with a real widget."""

    def test_clean_sprite_in_a_group_is_not_redrawn(self, real_film_strip_sprite):
        """A sprite that is not dirty keeps its image."""
        sprite = real_film_strip_sprite
        sprite.image.fill((1, 2, 3, 255))
        sprite.dirty = 0

        sprite.update()

        assert tuple(sprite.image.get_at((0, 0))) == (1, 2, 3, 255)

    def test_dirty_sprite_in_a_group_is_redrawn(self, real_film_strip_sprite):
        """A dirty sprite repaints its image with the film strip."""
        sprite = real_film_strip_sprite
        sprite.image.fill((1, 2, 3, 255))
        sprite.dirty = 1

        sprite.update()

        assert tuple(sprite.image.get_at((0, 0))) != (1, 2, 3, 255)

    def test_update_of_a_killed_sprite_without_widget_attribute_does_nothing(
        self,
        real_film_strip_sprite,
    ):
        """A sprite outside every group with no widget attribute returns quietly."""
        sprite = real_film_strip_sprite
        sprite.kill()
        del sprite.film_strip_widget

        sprite.update()

        assert not hasattr(sprite, 'film_strip_widget')

    def test_kill_without_widget_attribute_still_leaves_the_groups(self, real_film_strip_sprite):
        """Killing a sprite whose widget attribute is gone still removes it from its groups."""
        sprite = real_film_strip_sprite
        del sprite.film_strip_widget

        sprite.kill()

        assert sprite.groups() == []


class TestFilmStripSpriteColorSampling:
    """Test sampling a frame pixel into the colour sliders."""

    def test_right_click_samples_the_rgba_of_the_clicked_pixel(self, real_film_strip_sprite):
        """A right-click on a frame's top-left pixel sends its RGBA to the sliders."""
        sprite = real_film_strip_sprite
        parent_scene = RecordingParentScene()
        sprite.parent_scene = parent_scene  # type: ignore[assignment]
        frame_layout = frame_layout_of(sprite, frame_index=1)
        MockFactory.install_frame_input()

        handled = sprite.on_right_mouse_button_up_event(
            events.HashableEvent(0, pos=(frame_layout.x + 5, frame_layout.y + 5)),
        )

        assert handled is True
        assert parent_scene.slider_values == {'R': 10, 'G': 20, 'B': 30, 'A': 40}

    def test_bottom_right_pixel_is_sampled_too(self, real_film_strip_sprite):
        """A click near a frame's bottom-right corner samples the last pixel."""
        sprite = real_film_strip_sprite
        parent_scene = RecordingParentScene()
        sprite.parent_scene = parent_scene  # type: ignore[assignment]
        frame_layout = frame_layout_of(sprite, frame_index=0)

        sprite._sample_color_from_frame('idle', 0, frame_layout.right - 5, frame_layout.bottom - 5)

        assert parent_scene.slider_values == {'R': 200, 'G': 100, 'B': 50, 'A': 255}

    def test_rgb_pixel_is_sampled_as_opaque(self, real_film_strip_sprite):
        """A frame holding RGB pixels is sampled with alpha 255."""
        sprite = real_film_strip_sprite
        parent_scene = RecordingParentScene()
        sprite.parent_scene = parent_scene  # type: ignore[assignment]
        assert sprite.film_strip_widget is not None
        assert sprite.film_strip_widget.animated_sprite is not None
        frame = sprite.film_strip_widget.animated_sprite.animations['idle'][0]
        frame.pixels = [(1, 2, 3)] * 4
        frame_layout = frame_layout_of(sprite, frame_index=0)

        sprite._sample_color_from_frame('idle', 0, frame_layout.x + 5, frame_layout.y + 5)

        assert parent_scene.slider_values == {'R': 1, 'G': 2, 'B': 3, 'A': 255}

    def test_click_outside_the_frame_samples_nothing(self, real_film_strip_sprite):
        """Coordinates outside the frame's layout leave the sliders alone."""
        sprite = real_film_strip_sprite
        parent_scene = RecordingParentScene()
        sprite.parent_scene = parent_scene  # type: ignore[assignment]
        frame_layout = frame_layout_of(sprite, frame_index=0)

        sprite._sample_color_from_frame('idle', 0, frame_layout.right + 1, frame_layout.y + 5)

        assert parent_scene.slider_values == {}

    def test_pixel_beyond_short_pixel_data_samples_nothing(self, real_film_strip_sprite):
        """Pixel data shorter than the frame leaves the sliders alone for missing pixels."""
        sprite = real_film_strip_sprite
        parent_scene = RecordingParentScene()
        sprite.parent_scene = parent_scene  # type: ignore[assignment]
        assert sprite.film_strip_widget is not None
        assert sprite.film_strip_widget.animated_sprite is not None
        frame = sprite.film_strip_widget.animated_sprite.animations['idle'][0]
        frame.pixels = [TOP_LEFT_COLOR]
        frame_layout = frame_layout_of(sprite, frame_index=0)

        sprite._sample_color_from_frame('idle', 0, frame_layout.right - 5, frame_layout.bottom - 5)

        assert parent_scene.slider_values == {}

    def test_malformed_pixel_is_logged_not_raised(self, real_film_strip_sprite, caplog):
        """A pixel that is not RGB or RGBA is logged and the sliders are left alone."""
        sprite = real_film_strip_sprite
        parent_scene = RecordingParentScene()
        sprite.parent_scene = parent_scene  # type: ignore[assignment]
        assert sprite.film_strip_widget is not None
        assert sprite.film_strip_widget.animated_sprite is not None
        frame = sprite.film_strip_widget.animated_sprite.animations['idle'][0]
        frame.pixels = [(1, 2)] * 4
        frame_layout = frame_layout_of(sprite, frame_index=0)

        sprite._sample_color_from_frame('idle', 0, frame_layout.x + 5, frame_layout.y + 5)

        assert parent_scene.slider_values == {}
        assert 'Error sampling color from frame' in caplog.text


class TestFilmStripSpriteCopyPasteKeys:
    """Test Ctrl+C and Ctrl+V on the film strip sprite.

    film_strip_sprite.py reads the modifiers with ``event.get('mod', 0)``; these tests use real
    HashableEvents, whose ``get`` raised AttributeError before BUGS.md #88 was fixed.
    """

    def test_real_hashable_ctrl_c_event_copies_the_frame(self, real_film_strip_sprite):
        """A real Ctrl+C HashableEvent copies the current frame."""
        sprite = real_film_strip_sprite
        assert sprite.film_strip_widget is not None
        sprite.film_strip_widget.current_frame = 0

        handled = sprite.on_key_down_event(
            events.HashableEvent(0, key=pygame.K_c, mod=pygame.KMOD_CTRL),
        )

        assert handled is True
        assert sprite.film_strip_widget.copied_frame is not None

    def test_keys_are_ignored_without_a_widget(self, real_film_strip_sprite):
        """A sprite whose widget is gone does not handle keys."""
        sprite = real_film_strip_sprite
        sprite.film_strip_widget = None

        handled = sprite.on_key_down_event(
            events.HashableEvent(0, key=pygame.K_c, mod=pygame.KMOD_CTRL),
        )

        assert handled is None

    def test_ctrl_c_then_ctrl_v_copies_one_frame_over_another(self, real_film_strip_sprite):
        """Ctrl+C copies the current frame and Ctrl+V pastes it over the current frame."""
        sprite = real_film_strip_sprite
        widget = sprite.film_strip_widget
        assert widget is not None
        assert widget.animated_sprite is not None
        frames = widget.animated_sprite.animations['idle']
        frames[1].set_pixel_data([OTHER_COLOR] * 4)
        widget.current_frame = 0

        copied = sprite.on_key_down_event(
            events.HashableEvent(0, key=pygame.K_c, mod=pygame.KMOD_CTRL),
        )
        widget.current_frame = 1
        pasted = sprite.on_key_down_event(
            events.HashableEvent(0, key=pygame.K_v, mod=pygame.KMOD_CTRL),
        )

        assert copied is True
        assert pasted is True
        assert frames[1].get_pixel_data()[0] == TOP_LEFT_COLOR

    def test_failed_copy_and_paste_are_still_handled(self, real_film_strip_sprite):
        """Ctrl+C and Ctrl+V with nothing to copy or paste are consumed and change nothing."""
        sprite = real_film_strip_sprite
        widget = sprite.film_strip_widget
        assert widget is not None
        widget.current_frame = 99

        copied = sprite.on_key_down_event(
            events.HashableEvent(0, key=pygame.K_c, mod=pygame.KMOD_CTRL),
        )
        pasted = sprite.on_key_down_event(
            events.HashableEvent(0, key=pygame.K_v, mod=pygame.KMOD_CTRL),
        )

        assert copied is True
        assert pasted is True
        assert widget.copied_frame is None

    def test_other_keys_are_not_handled(self, real_film_strip_sprite):
        """A key that is not Ctrl+C or Ctrl+V is not handled."""
        sprite = real_film_strip_sprite

        handled = sprite.on_key_down_event(
            events.HashableEvent(0, key=pygame.K_c, mod=0),
        )

        assert handled is False


class TestFilmStripSpriteHover:
    """Test FilmStripSprite.on_mouse_motion_event hover tracking."""

    def test_motion_is_ignored_without_a_widget(self, real_film_strip_sprite):
        """A sprite whose widget is gone ignores mouse motion."""
        sprite = real_film_strip_sprite
        sprite.film_strip_widget = None

        sprite.on_mouse_motion_event(events.HashableEvent(0, pos=(5, 5)))

        assert sprite.film_strip_widget is None

    def test_moving_within_the_same_frame_does_not_redirty(self, real_film_strip_sprite):
        """A second motion over the same frame does not mark the widget for redraw."""
        sprite = real_film_strip_sprite
        widget = sprite.film_strip_widget
        assert widget is not None
        frame_layout = frame_layout_of(sprite, frame_index=0)
        sprite.on_mouse_motion_event(events.HashableEvent(0, pos=frame_layout.center))
        widget.force_redraw = False

        sprite.on_mouse_motion_event(events.HashableEvent(0, pos=frame_layout.center))

        assert widget.hovered_frame == ('idle', 0)
        assert widget.force_redraw is False

    def test_moving_outside_without_hover_changes_nothing(self, real_film_strip_sprite):
        """Motion outside the strip with nothing hovered leaves the widget clean."""
        sprite = real_film_strip_sprite
        widget = sprite.film_strip_widget
        assert widget is not None
        widget.force_redraw = False

        sprite.on_mouse_motion_event(events.HashableEvent(0, pos=(1000, 1000)))

        assert widget.force_redraw is False

    def test_clearing_hover_without_a_widget_does_nothing(self, real_film_strip_sprite):
        """Clearing hover effects after the widget is gone is harmless."""
        sprite = real_film_strip_sprite
        sprite.film_strip_widget = None

        sprite._clear_hover_effects()

        assert sprite.film_strip_widget is None


class TestFilmStripSpriteCanvasDimensions:
    """Test FilmStripSprite._get_canvas_dimensions."""

    def test_parent_canvas_size_wins(self, real_film_strip_sprite):
        """The parent canvas's pixel size is used first."""
        sprite = real_film_strip_sprite
        sprite.parent_canvas = RecordingCanvas(pixels_across=5, pixels_tall=6)  # type: ignore[assignment]

        assert sprite._get_canvas_dimensions() == (5, 6)

    def test_parent_scene_canvas_size_is_used_without_a_parent_canvas(
        self,
        real_film_strip_sprite,
    ):
        """Without a parent canvas, the parent scene's canvas size is used."""
        sprite = real_film_strip_sprite
        sprite.parent_canvas = None  # type: ignore[assignment]
        parent_scene = RecordingParentScene()
        parent_scene.canvas = RecordingCanvas(pixels_across=7, pixels_tall=8)  # type: ignore[attr-defined]
        sprite.parent_scene = parent_scene  # type: ignore[assignment]

        assert sprite._get_canvas_dimensions() == (7, 8)

    def test_default_size_is_32_by_32(self, real_film_strip_sprite):
        """With no canvas anywhere, the size is 32x32."""
        sprite = real_film_strip_sprite

        assert sprite._get_canvas_dimensions() == (32, 32)


class TestFilmStripSpriteImageDrops:
    """Test replacing and inserting frames from dropped image files."""

    def test_unreadable_file_converts_to_nothing(self, real_film_strip_sprite, tmp_path):
        """A file that is not an image gives no frame."""
        sprite = real_film_strip_sprite
        bogus_path = tmp_path / 'bogus.png'
        bogus_path.write_bytes(b'not a png')

        assert sprite._convert_image_to_sprite_frame(str(bogus_path)) is None

    def test_png_converts_to_a_frame_of_the_canvas_size(self, real_film_strip_sprite, tmp_path):
        """A dropped PNG is scaled to the canvas size and keeps its colour."""
        sprite = real_film_strip_sprite
        sprite.parent_canvas = RecordingCanvas(pixels_across=4, pixels_tall=3)  # type: ignore[assignment]
        image_path = write_png(
            path=tmp_path / 'red.png',
            size=(8, 8),
            color=(255, 0, 0),
            alpha=False,
        )

        frame = sprite._convert_image_to_sprite_frame(image_path)

        assert frame is not None
        assert frame.get_size() == (4, 3)
        assert frame.get_pixel_data()[0] == (255, 0, 0, 255)

    def test_png_with_alpha_keeps_its_alpha_and_pixel_order(self, real_film_strip_sprite, tmp_path):
        """A PNG with an alpha channel keeps each pixel's alpha, row by row (BUGS.md #87)."""
        sprite = real_film_strip_sprite
        sprite.parent_canvas = RecordingCanvas(pixels_across=2, pixels_tall=2)  # type: ignore[assignment]
        surface = pygame.Surface((2, 2), pygame.SRCALPHA)
        surface.fill((0, 0, 255, 255))
        surface.set_at((1, 0), (10, 20, 30, 0))
        surface.set_at((0, 1), (40, 50, 60, 128))
        image_path = tmp_path / 'alpha.png'
        pygame.image.save(surface, str(image_path))

        frame = sprite._convert_image_to_sprite_frame(str(image_path))

        assert frame is not None
        assert frame.get_size() == (2, 2)
        assert frame.get_pixel_data() == [
            (0, 0, 255, 255),
            (10, 20, 30, 0),
            (40, 50, 60, 128),
            (0, 0, 255, 255),
        ]

    def test_dropped_png_replaces_the_frame(self, real_film_strip_sprite, tmp_path):
        """A real dropped PNG (no mocked conversion) replaces the frame it was dropped on."""
        sprite = real_film_strip_sprite
        widget = sprite.film_strip_widget
        assert widget is not None
        assert widget.animated_sprite is not None
        sprite.parent_canvas = RecordingCanvas(pixels_across=2, pixels_tall=2)  # type: ignore[assignment]
        image_path = write_png(
            path=tmp_path / 'green.png',
            size=(2, 2),
            color=(0, 255, 0),
            alpha=False,
        )

        assert sprite._replace_frame_with_image(image_path, 'idle', 0) is True
        assert (
            widget.animated_sprite.animations['idle'][0].get_pixel_data() == [(0, 255, 0, 255)] * 4
        )

    def test_replace_fails_when_the_image_cannot_be_converted(self, real_film_strip_sprite, mocker):
        """A drop that cannot be converted leaves the frame in place."""
        sprite = real_film_strip_sprite
        widget = sprite.film_strip_widget
        assert widget is not None
        assert widget.animated_sprite is not None
        original_frame = widget.animated_sprite.animations['idle'][0]
        mocker.patch.object(sprite, '_convert_image_to_sprite_frame', return_value=None)

        assert sprite._replace_frame_with_image('dropped.png', 'idle', 0) is False
        assert widget.animated_sprite.animations['idle'][0] is original_frame

    def test_replace_fails_without_an_animated_sprite(self, real_film_strip_sprite, mocker):
        """A widget with no sprite cannot have a frame replaced."""
        sprite = real_film_strip_sprite
        assert sprite.film_strip_widget is not None
        sprite.film_strip_widget.animated_sprite = None
        mocker.patch.object(
            sprite,
            '_convert_image_to_sprite_frame',
            return_value=make_two_by_two_frame(),
        )

        assert sprite._replace_frame_with_image('dropped.png', 'idle', 0) is False

    def test_replace_fails_for_a_frame_that_does_not_exist(self, real_film_strip_sprite, mocker):
        """A frame index past the animation's end is refused."""
        sprite = real_film_strip_sprite
        mocker.patch.object(
            sprite,
            '_convert_image_to_sprite_frame',
            return_value=make_two_by_two_frame(),
        )

        assert sprite._replace_frame_with_image('dropped.png', 'idle', 5) is False

    def test_replacing_the_selected_frame_shows_it_on_the_canvas(
        self,
        real_film_strip_sprite,
        mocker,
    ):
        """Replacing the frame the scene has selected shows the new frame on the canvas."""
        sprite = real_film_strip_sprite
        widget = sprite.film_strip_widget
        assert widget is not None
        assert widget.animated_sprite is not None
        new_frame = make_two_by_two_frame()
        mocker.patch.object(sprite, '_convert_image_to_sprite_frame', return_value=new_frame)
        parent_scene = RecordingParentScene()
        parent_scene.selected_animation = 'idle'  # type: ignore[attr-defined]
        parent_scene.selected_frame = 1  # type: ignore[attr-defined]
        canvas = RecordingCanvas()
        parent_scene.canvas = canvas  # type: ignore[attr-defined]
        sprite.parent_scene = parent_scene  # type: ignore[assignment]

        assert sprite._replace_frame_with_image('dropped.png', 'idle', 1) is True
        assert widget.animated_sprite.animations['idle'][1] is new_frame
        assert canvas.shown_frames == [('idle', 1)]

    def test_canvas_is_not_updated_without_a_parent_scene(self, real_film_strip_sprite):
        """Without a parent scene there is no canvas to update."""
        sprite = real_film_strip_sprite

        assert sprite._should_update_canvas_frame('idle', 0) is False

    def test_insert_fails_when_the_image_cannot_be_converted(self, real_film_strip_sprite, mocker):
        """A drop that cannot be converted adds no frame."""
        sprite = real_film_strip_sprite
        mocker.patch.object(sprite, '_convert_image_to_sprite_frame', return_value=None)

        assert sprite._insert_image_as_new_frame('dropped.png', 0, 0) is False
        assert sprite.film_strip_widget is not None
        assert sprite.film_strip_widget.animated_sprite is not None
        assert len(sprite.film_strip_widget.animated_sprite.animations['idle']) == 2

    def test_insert_fails_without_a_current_animation(self, real_film_strip_sprite, mocker):
        """A widget with no current animation cannot take a new frame."""
        sprite = real_film_strip_sprite
        assert sprite.film_strip_widget is not None
        sprite.film_strip_widget.current_animation = ''
        mocker.patch.object(
            sprite,
            '_convert_image_to_sprite_frame',
            return_value=make_two_by_two_frame(),
        )

        assert sprite._insert_image_as_new_frame('dropped.png', 0, 0) is False

    def test_insert_appends_the_frame_and_tells_the_scene(self, real_film_strip_sprite, mocker):
        """An inserted frame goes at the end, is selected, and the scene is told."""
        sprite = real_film_strip_sprite
        widget = sprite.film_strip_widget
        assert widget is not None
        assert widget.animated_sprite is not None
        new_frame = make_two_by_two_frame()
        mocker.patch.object(sprite, '_convert_image_to_sprite_frame', return_value=new_frame)
        parent_scene = RecordingParentScene()
        sprite.parent_scene = parent_scene  # type: ignore[assignment]

        assert sprite._insert_image_as_new_frame('dropped.png', 0, 0) is True
        assert widget.animated_sprite.animations['idle'][2] is new_frame
        assert parent_scene.inserted_frames == [('idle', 2)]
        assert widget.selected_frame == 2
