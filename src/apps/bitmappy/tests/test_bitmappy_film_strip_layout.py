"""Tests for bitmappy.film_strip_layout: label, tab and hit-test geometry."""

import pygame
import pytest

from bitmappy.film_strip import FilmStripWidget
from glitchygames.fonts import FontManager
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

FRAME_SIZE = 8


def make_film_strip(*, animation_names: tuple[str, ...] = ('idle',)) -> FilmStripWidget:
    """Build a film strip showing one single-frame animation per name.

    Args:
        animation_names: The animations to give the sprite.

    Returns:
        The film strip widget.

    """
    animated_sprite = AnimatedSprite()
    for animation_name in animation_names:
        surface = pygame.Surface((FRAME_SIZE, FRAME_SIZE), pygame.SRCALPHA)
        animated_sprite.add_animation(animation_name, [SpriteFrame(surface, duration=0.5)])
    film_strip = FilmStripWidget(x=0, y=0, width=400, height=120)
    film_strip.set_animated_sprite(animated_sprite)
    film_strip.current_animation = animation_names[0]
    return film_strip


@pytest.fixture
def pygame_font_system(mocker):
    """Make FontManager hand out pygame.font fonts, as `--font-system pygame` does."""
    mocker.patch.dict(FontManager.OPTIONS, {'use_freetype': False})


class TestCalculateAnimationLayouts:
    """Test FilmStripLayout.calculate_animation_layouts."""

    def test_label_width_follows_the_name_with_the_pygame_font_system(self, pygame_font_system):
        """With pygame.font fonts, each label is its rendered name plus 20 pixels of padding."""
        film_strip = make_film_strip(animation_names=('idle', 'a much longer name'))

        film_strip.layout.calculate_animation_layouts()

        short_label = film_strip.animation_layouts['idle']
        long_label = film_strip.animation_layouts['a much longer name']
        assert long_label.width > short_label.width
        font = FontManager.get_font()
        assert short_label.width == font.size('idle')[0] + 20


class TestGetPreviewAtPosition:
    """Test FilmStripLayout.get_preview_at_position."""

    def test_point_inside_the_preview_names_its_animation(self):
        """A point inside an animation's preview rect returns that animation."""
        film_strip = make_film_strip()
        preview_rect = film_strip.preview_rects['idle']

        assert film_strip.layout.get_preview_at_position(preview_rect.center) == 'idle'

    def test_point_outside_every_preview_returns_none(self):
        """A point that misses every preview rect returns None."""
        film_strip = make_film_strip()
        preview_rect = film_strip.preview_rects['idle']
        outside_point = (preview_rect.left - 1, preview_rect.top)

        assert film_strip.layout.get_preview_at_position(outside_point) is None


class TestRefresh:
    """Test FilmStripWidget.refresh, which commands call after changing the animations."""

    def test_a_frame_added_behind_the_widget_gets_its_layout_tabs_and_a_redraw(self):
        """After refresh, a frame added straight to the sprite is laid out, tabbed and drawn."""
        film_strip = make_film_strip()
        film_strip.update_layout()
        tab_count_for_one_frame = len(film_strip.film_tabs)
        assert film_strip.animated_sprite is not None
        surface = pygame.Surface((FRAME_SIZE, FRAME_SIZE), pygame.SRCALPHA)
        film_strip.animated_sprite.add_frame('idle', SpriteFrame(surface, duration=0.5))
        film_strip.force_redraw = False

        film_strip.refresh()

        assert ('idle', 1) in film_strip.frame_layouts
        assert len(film_strip.film_tabs) > tab_count_for_one_frame
        assert film_strip.force_redraw is True

    def test_refresh_lays_out_and_tabs_once(self, mocker):
        """One layout calculation and one set of film tabs per refresh (BUGS.md #178 item 24)."""
        film_strip = make_film_strip()
        calculate_layout = mocker.spy(film_strip.layout, 'calculate_layout')
        create_film_tabs = mocker.spy(film_strip.layout, 'create_film_tabs')

        film_strip.refresh()

        assert (calculate_layout.call_count, create_film_tabs.call_count) == (1, 1)
