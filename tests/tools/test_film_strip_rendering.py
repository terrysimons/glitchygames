"""Tests for glitchygames.bitmappy.film_strip_rendering: frames, labels and the preview panel."""

import logging
from types import SimpleNamespace

import pygame
import pytest

from glitchygames.bitmappy import onion_skinning
from glitchygames.bitmappy.film_strip import FilmStripWidget
from glitchygames.clock import frame_clock_milliseconds
from glitchygames.fonts import FontManager
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

FRAME_SIZE = 8


def make_frame(*, color: tuple[int, int, int]) -> SpriteFrame:
    """Build an opaque single-colour frame.

    Args:
        color: The frame's colour.

    Returns:
        The frame.

    """
    surface = pygame.Surface((FRAME_SIZE, FRAME_SIZE), pygame.SRCALPHA)
    surface.fill((*color, 255))
    return SpriteFrame(surface, duration=0.5)


@pytest.fixture
def film_strip_with_two_frames() -> FilmStripWidget:
    """Build a film strip showing a red-then-green 'idle' animation.

    Returns:
        The film strip widget.

    """
    animated_sprite = AnimatedSprite()
    animated_sprite._animations = {  # pyright: ignore[reportPrivateUsage]
        'idle': [make_frame(color=(255, 0, 0)), make_frame(color=(0, 255, 0))],
    }
    animated_sprite.frame_manager.current_animation = 'idle'
    film_strip = FilmStripWidget(x=0, y=0, width=400, height=120)
    film_strip.set_animated_sprite(animated_sprite)
    film_strip.current_animation = 'idle'
    return film_strip


class TestRenderPreview:
    """Test FilmStripRendering.render_preview."""

    def test_out_of_range_preview_frame_falls_back_to_the_first_frame(
        self,
        film_strip_with_two_frames,
        mocker,
    ):
        """An out-of-range preview index shows frame 0 and restarts the preview clock."""
        film_strip = film_strip_with_two_frames
        film_strip.preview_animation_times['idle'] = 0.75
        mocker.patch.object(film_strip.animation, 'get_current_preview_frame', return_value=7)
        surface = pygame.Surface(film_strip.rect.size, pygame.SRCALPHA)

        film_strip.renderer.render_preview(surface)

        assert film_strip.preview_animation_times['idle'] == pytest.approx(0.0)
        preview_rect = film_strip.preview_rects['idle']
        center_color = tuple(surface.get_at(preview_rect.center))
        assert center_color[:3] == (255, 0, 0)

    def test_negative_preview_frame_falls_back_to_the_first_frame(
        self,
        film_strip_with_two_frames,
        mocker,
    ):
        """A negative preview index is also replaced by frame 0."""
        film_strip = film_strip_with_two_frames
        mocker.patch.object(film_strip.animation, 'get_current_preview_frame', return_value=-1)
        surface = pygame.Surface(film_strip.rect.size, pygame.SRCALPHA)

        film_strip.renderer.render_preview(surface)

        preview_rect = film_strip.preview_rects['idle']
        assert tuple(surface.get_at(preview_rect.center))[:3] == (255, 0, 0)

    def test_valid_preview_frame_is_shown(self, film_strip_with_two_frames, mocker):
        """A valid preview index shows that frame and keeps the preview clock."""
        film_strip = film_strip_with_two_frames
        film_strip.preview_animation_times['idle'] = 0.75
        mocker.patch.object(film_strip.animation, 'get_current_preview_frame', return_value=1)
        surface = pygame.Surface(film_strip.rect.size, pygame.SRCALPHA)

        film_strip.renderer.render_preview(surface)

        assert film_strip.preview_animation_times['idle'] == pytest.approx(0.75)
        preview_rect = film_strip.preview_rects['idle']
        assert tuple(surface.get_at(preview_rect.center))[:3] == (0, 255, 0)


def surface_contains_color(*, surface: pygame.Surface, color: tuple[int, int, int]) -> bool:
    """Report whether any pixel of the surface has exactly the given RGB colour.

    Args:
        surface: The surface to search.
        color: The RGB colour to look for.

    Returns:
        True if at least one pixel matches.

    """
    width, height = surface.get_size()
    return any(
        tuple(surface.get_at((pixel_x, pixel_y)))[:3] == color
        for pixel_y in range(height)
        for pixel_x in range(width)
    )


@pytest.fixture
def pygame_font_system(mocker):
    """Make FontManager hand out pygame.font fonts, as `--font-system pygame` does."""
    mocker.patch.dict(FontManager.OPTIONS, {'use_freetype': False})


class TestLabelsWithThePygameFontSystem:
    """Test that animation labels render with pygame.font fonts (`--font-system pygame`)."""

    def test_animation_label_draws_the_name_in_white(
        self,
        film_strip_with_two_frames,
        pygame_font_system,
    ):
        """The label of an animation that is not being edited shows its name in white."""
        film_strip = film_strip_with_two_frames
        label_rect = pygame.Rect(0, 0, 80, 20)

        label_surface = film_strip.renderer.render_animation_label('idle', label_rect)

        assert surface_contains_color(surface=label_surface, color=(255, 255, 255))

    def test_editing_label_draws_the_typed_text_in_light_blue(
        self,
        film_strip_with_two_frames,
        pygame_font_system,
    ):
        """While renaming, the typed text is drawn in the light blue editing colour."""
        film_strip = film_strip_with_two_frames
        film_strip.editing_text = 'walk'
        film_strip.cursor_visible = False
        film_strip.cursor_blink_time = frame_clock_milliseconds()
        label_surface = pygame.Surface((80, 20), pygame.SRCALPHA)
        label_surface.fill((0, 0, 0, 255))

        film_strip.renderer.render_editing_label(label_surface, pygame.Rect(0, 0, 80, 20))

        assert surface_contains_color(surface=label_surface, color=(200, 220, 255))


def surface_pixels(surface: pygame.Surface) -> list[tuple[int, ...]]:
    """Read every pixel of a surface, row by row.

    Args:
        surface: The surface to read.

    Returns:
        The RGBA tuples.

    """
    width, height = surface.get_size()
    return [
        tuple(surface.get_at((pixel_x, pixel_y)))
        for pixel_y in range(height)
        for pixel_x in range(width)
    ]


class TestDecorationFailuresAreLogged:
    """Test that a failing frame number or onion skin indicator is logged, not raised."""

    def test_frame_number_font_failure_draws_nothing(
        self, film_strip_with_two_frames, mocker, caplog
    ):
        """A font that cannot be created leaves the frame surface untouched."""
        mocker.patch.object(pygame.font, 'Font', side_effect=pygame.error('no font'))
        surface = pygame.Surface((32, 32), pygame.SRCALPHA)
        pixels_before = surface_pixels(surface)

        film_strip_with_two_frames.renderer._draw_frame_number(surface, 0)

        assert surface_pixels(surface) == pixels_before
        assert 'Font rendering failed' in caplog.text

    def test_onion_skin_lookup_failure_draws_nothing(
        self, film_strip_with_two_frames, mocker, caplog
    ):
        """An onion skinning manager that fails leaves the frame surface untouched."""
        mocker.patch.object(
            onion_skinning,
            'get_onion_skinning_manager',
            side_effect=RuntimeError('no manager'),
        )
        surface = pygame.Surface((32, 32), pygame.SRCALPHA)
        pixels_before = surface_pixels(surface)

        film_strip_with_two_frames.renderer._draw_onion_skinning_indicator(surface, 'idle', 0)

        assert surface_pixels(surface) == pixels_before
        assert 'Onion skinning indicator rendering failed' in caplog.text

    def test_preview_frame_index_font_failure_draws_nothing(
        self,
        film_strip_with_two_frames,
        mocker,
        caplog,
    ):
        """A font that cannot be created leaves the preview untouched."""
        mocker.patch.object(pygame.font, 'Font', side_effect=pygame.error('no font'))
        surface = pygame.Surface((64, 64), pygame.SRCALPHA)
        pixels_before = surface_pixels(surface)

        film_strip_with_two_frames.renderer._draw_preview_frame_index(
            surface,
            pygame.Rect(0, 0, 64, 64),
            'idle',
        )

        assert surface_pixels(surface) == pixels_before
        assert 'Font rendering failed' in caplog.text


class TestDrawPreviewFrameIndex:
    """Test FilmStripRendering._draw_preview_frame_index."""

    def test_unknown_animation_still_draws_an_index(self, film_strip_with_two_frames):
        """An animation the sprite does not have is labelled as one frame, in white."""
        surface = pygame.Surface((64, 64), pygame.SRCALPHA)

        film_strip_with_two_frames.renderer._draw_preview_frame_index(
            surface,
            pygame.Rect(0, 0, 64, 64),
            'missing',
        )

        assert surface_contains_color(surface=surface, color=(255, 255, 255))


class TestGetFrameImageForRendering:
    """Test FilmStripRendering.get_frame_image_for_rendering."""

    def test_frame_without_image_is_built_from_its_pixels(self, film_strip_with_two_frames):
        """A frame with no image gets one built from its pixel data."""
        frame = SimpleNamespace(
            image=None,
            get_pixel_data=lambda: [(0, 0, 255, 255)] * 4,
            get_size=lambda: (2, 2),
        )

        frame_image = film_strip_with_two_frames.renderer.get_frame_image_for_rendering(
            frame,
            is_selected=False,
        )

        assert frame_image is not None
        assert frame_image.get_size() == (2, 2)
        assert tuple(frame_image.get_at((1, 1))) == (0, 0, 255, 255)


class TestRenderWithoutSprite:
    """Test that the film strip draws nothing until it has an animated sprite."""

    def test_render_draws_nothing(self):
        """render() leaves the surface untouched without a sprite."""
        film_strip = FilmStripWidget(x=0, y=0, width=400, height=120)
        surface = pygame.Surface((40, 40), pygame.SRCALPHA)
        pixels_before = surface_pixels(surface)

        film_strip.renderer.render(surface)

        assert surface_pixels(surface) == pixels_before

    def test_render_preview_draws_nothing(self):
        """render_preview() leaves the surface untouched without a sprite."""
        film_strip = FilmStripWidget(x=0, y=0, width=400, height=120)
        film_strip.preview_rects['idle'] = pygame.Rect(0, 0, 40, 40)
        surface = pygame.Surface((40, 40), pygame.SRCALPHA)
        pixels_before = surface_pixels(surface)

        film_strip.renderer.render_preview(surface)

        assert surface_pixels(surface) == pixels_before


class TestRenderPreviewEdges:
    """Test render_preview for animations it cannot show a frame of."""

    def test_animation_without_frames_shows_only_the_background(self, film_strip_with_two_frames):
        """A preview whose animation has no frames is filled with the background colour only."""
        film_strip = film_strip_with_two_frames
        film_strip.animated_sprite._animations['empty'] = []  # pyright: ignore[reportPrivateUsage]
        preview_rect = pygame.Rect(0, 0, 40, 40)
        film_strip.preview_rects = {'empty': preview_rect}
        surface = pygame.Surface(film_strip.rect.size, pygame.SRCALPHA)

        film_strip.renderer.render_preview(surface)

        center_color = tuple(surface.get_at((preview_rect.centerx, preview_rect.top + 8)))
        assert center_color[:3] == tuple(film_strip.background_color)[:3]

    def test_invalid_index_without_preview_time_falls_back_to_frame_zero(
        self,
        film_strip_with_two_frames,
        mocker,
    ):
        """An invalid index for an animation with no preview time shows frame 0 and adds none."""
        film_strip = film_strip_with_two_frames
        film_strip.preview_animation_times.pop('idle', None)
        mocker.patch.object(film_strip.animation, 'get_current_preview_frame', return_value=9)
        surface = pygame.Surface(film_strip.rect.size, pygame.SRCALPHA)

        film_strip.renderer.render_preview(surface)

        assert 'idle' not in film_strip.preview_animation_times
        preview_rect = film_strip.preview_rects['idle']
        assert tuple(surface.get_at(preview_rect.center))[:3] == (255, 0, 0)


class TestRenderFrameThumbnails:
    """Test FilmStripRendering._render_frame_thumbnails with stale layouts."""

    def test_stale_layout_entries_are_skipped(self, film_strip_with_two_frames):
        """Layouts for a missing animation or a removed frame draw nothing."""
        film_strip = film_strip_with_two_frames
        missing_animation_rect = pygame.Rect(300, 60, 20, 20)
        removed_frame_rect = pygame.Rect(330, 60, 20, 20)
        film_strip.frame_layouts['ghost', 0] = missing_animation_rect
        film_strip.frame_layouts['idle', 5] = removed_frame_rect
        surface = pygame.Surface(film_strip.rect.size, pygame.SRCALPHA)
        surface.fill((1, 2, 3, 255))

        film_strip.renderer._render_frame_thumbnails(surface)

        for stale_rect in (missing_animation_rect, removed_frame_rect):
            assert tuple(surface.get_at(stale_rect.center)) == (1, 2, 3, 255)


class TestRenderEditingLabelWithoutText:
    """Test render_editing_label with nothing typed yet."""

    def test_hidden_cursor_leaves_only_the_border(self, film_strip_with_two_frames):
        """With no text and the cursor in its hidden phase, only the edit border is drawn."""
        film_strip = film_strip_with_two_frames
        film_strip.editing_text = ''
        film_strip.cursor_visible = False
        film_strip.cursor_blink_time = frame_clock_milliseconds()
        label_surface = pygame.Surface((80, 20), pygame.SRCALPHA)
        label_surface.fill((0, 0, 0, 255))

        film_strip.renderer.render_editing_label(label_surface, pygame.Rect(0, 0, 80, 20))

        assert tuple(label_surface.get_at((40, 10))) == (0, 0, 0, 255)
        assert tuple(label_surface.get_at((0, 0)))[:3] == (100, 180, 220)


class TestRender:
    """Test FilmStripRendering.render bookkeeping and overlays."""

    def test_every_fiftieth_render_is_logged(self, film_strip_with_two_frames, caplog):
        """The 50th render logs its count and the current frame."""
        film_strip = film_strip_with_two_frames
        film_strip.render_count = 49
        surface = pygame.Surface(film_strip.rect.size, pygame.SRCALPHA)

        with caplog.at_level(logging.DEBUG, logger='game.tools.film_strip'):
            film_strip.renderer.render(surface)

        assert film_strip.render_count == 50
        assert 'FilmStripWidget: Render #50, current_frame=0' in caplog.messages

    def test_render_without_a_forced_redraw_keeps_the_flag_clear(self, film_strip_with_two_frames):
        """A render that was not forced leaves force_redraw False."""
        film_strip = film_strip_with_two_frames
        film_strip.force_redraw = False
        surface = pygame.Surface(film_strip.rect.size, pygame.SRCALPHA)

        film_strip.renderer.render(surface)

        assert film_strip.force_redraw is False

    def test_scene_controller_selections_are_drawn_above_their_frame(
        self,
        film_strip_with_two_frames,
    ):
        """A controller selection from the scene draws a triangle in its colour over the frame."""
        film_strip = film_strip_with_two_frames
        film_strip.parent_scene = SimpleNamespace(
            film_strip_controller_selections={
                'idle': [{'controller_id': 1, 'frame': 1, 'color': (0, 255, 0)}],
            },
        )
        surface = pygame.Surface(film_strip.rect.size, pygame.SRCALPHA)

        film_strip.renderer.render(surface)

        frame_rect = film_strip.frame_layouts['idle', 1]
        assert tuple(surface.get_at((frame_rect.centerx, frame_rect.top - 4)))[:3] == (0, 255, 0)


class TestDrawUnifiedIndicators:
    """Test FilmStripRendering._draw_unified_indicators."""

    def test_controller_alone_is_centered_over_the_frame(self, film_strip_with_two_frames):
        """Without a keyboard selection, a single controller's triangle sits at the centre."""
        frame_rect = pygame.Rect(20, 20, 30, 30)
        surface = pygame.Surface((80, 80), pygame.SRCALPHA)

        film_strip_with_two_frames.renderer._draw_unified_indicators(
            surface,
            frame_rect,
            [{'type': 'controller_2', 'frame': 0, 'color': (0, 0, 255), 'priority': 2}],
        )

        assert tuple(surface.get_at((frame_rect.centerx, frame_rect.top - 4)))[:3] == (0, 0, 255)


class TestDrawFilmSprockets:
    """Test FilmStripRendering.draw_film_sprockets around the animation label."""

    def test_without_a_current_animation_top_sprockets_cross_the_label_area(
        self,
        film_strip_with_two_frames,
    ):
        """With no current animation there is no label to skip, so top sprockets fill the width."""
        film_strip = film_strip_with_two_frames
        label_rect = film_strip.animation_layouts['idle']
        sprocket_color = (60, 50, 40)

        def top_sprocket_pixels_in_label(*, current_animation: str) -> int:
            film_strip.current_animation = current_animation
            surface = pygame.Surface(film_strip.rect.size, pygame.SRCALPHA)
            film_strip.renderer.draw_film_sprockets(surface)
            return sum(
                tuple(surface.get_at((pixel_x, 10)))[:3] == sprocket_color
                for pixel_x in range(label_rect.left, label_rect.right)
            )

        assert top_sprocket_pixels_in_label(current_animation='idle') == 0
        assert top_sprocket_pixels_in_label(current_animation='') > 0
