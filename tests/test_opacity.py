"""Tests for glitchygames/opacity.py: per-pixel alpha and making a surface opaque.

The surfaces are built explicitly (SRCALPHA, or 32-bit masks with and without an alpha mask),
so the rules are tested on the dummy video driver too, whose display has no alpha channel.
"""

from __future__ import annotations

import pygame

from glitchygames.opacity import (
    OPAQUE,
    every_pixel_has_alpha,
    has_per_pixel_alpha,
    make_opaque,
    shown_rgb_bytes,
)

SURFACE_SIZE = (4, 3)
NO_ALPHA_MASKS = (0xFF0000, 0x00FF00, 0x0000FF, 0)
ALPHA_MASKS = (0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)


class TestHasPerPixelAlpha:
    """has_per_pixel_alpha tells whether a surface's pixels carry an alpha channel."""

    def test_a_srcalpha_surface_has_per_pixel_alpha(self):
        """A SRCALPHA surface stores an alpha per pixel."""
        assert has_per_pixel_alpha(surface=pygame.Surface(SURFACE_SIZE, pygame.SRCALPHA))

    def test_a_surface_with_an_alpha_mask_has_per_pixel_alpha(self):
        """A 32-bit surface with an alpha mask (cocoa's display format) carries alpha."""
        surface = pygame.Surface(SURFACE_SIZE, depth=32, masks=ALPHA_MASKS)

        assert has_per_pixel_alpha(surface=surface)

    def test_a_surface_without_an_alpha_mask_has_none(self):
        """A surface with no alpha mask (the dummy and x11 display format) carries none."""
        surface = pygame.Surface(SURFACE_SIZE, depth=32, masks=NO_ALPHA_MASKS)

        assert not has_per_pixel_alpha(surface=surface)


class TestMakeOpaque:
    """make_opaque sets every pixel's alpha to 255 and keeps its colour."""

    def test_transparent_and_translucent_pixels_become_opaque_with_their_colour(self):
        """Alpha 0 and alpha 128 become 255; red, green and blue are kept, never blended."""
        surface = pygame.Surface(SURFACE_SIZE, pygame.SRCALPHA)
        surface.fill((10, 20, 30, 0))
        surface.set_at((1, 1), (40, 50, 60, 128))

        make_opaque(surface=surface)

        assert surface.get_at((0, 0)) == (10, 20, 30, OPAQUE)
        assert surface.get_at((1, 1)) == (40, 50, 60, OPAQUE)
        alpha_values = pygame.surfarray.array_alpha(surface)
        assert (alpha_values == OPAQUE).all()

    def test_a_surface_with_an_alpha_mask_but_no_srcalpha_flag_becomes_opaque(self):
        """A surface whose alpha is copied, never blended (cocoa's non-SRCALPHA format)."""
        surface = pygame.Surface(SURFACE_SIZE, depth=32, masks=ALPHA_MASKS)
        surface.fill((70, 80, 90, 0))

        make_opaque(surface=surface)

        assert surface.get_at((2, 2)) == (70, 80, 90, OPAQUE)

    def test_a_surface_without_alpha_is_left_alone(self):
        """A surface without per-pixel alpha is already opaque: its pixels do not change."""
        surface = pygame.Surface(SURFACE_SIZE, depth=32, masks=NO_ALPHA_MASKS)
        surface.fill((70, 80, 90))
        pixels_before = pygame.image.tobytes(surface, 'RGB')

        make_opaque(surface=surface)

        assert pygame.image.tobytes(surface, 'RGB') == pixels_before


class TestEveryPixelHasAlpha:
    """every_pixel_has_alpha tells whether no pixel of an alpha surface has alpha 0."""

    def test_an_opaque_surface_has_alpha_everywhere(self):
        """Alpha 255 everywhere."""
        surface = pygame.Surface(SURFACE_SIZE, pygame.SRCALPHA)
        surface.fill((10, 20, 30, OPAQUE))

        assert every_pixel_has_alpha(surface=surface)

    def test_one_pixel_with_alpha_0_is_found(self):
        """A single transparent pixel is enough."""
        surface = pygame.Surface(SURFACE_SIZE, pygame.SRCALPHA)
        surface.fill((10, 20, 30, 1))
        surface.set_at((3, 2), (10, 20, 30, 0))

        assert not every_pixel_has_alpha(surface=surface)


class TestShownRgbBytes:
    """shown_rgb_bytes: a surface's colours as the window shows them, alpha 0 shown black."""

    def test_a_surface_without_alpha_shows_its_colours(self):
        """The dummy and x11 display format: the RGB bytes as they are."""
        surface = pygame.Surface(SURFACE_SIZE, depth=32, masks=NO_ALPHA_MASKS)
        surface.fill((70, 80, 90))

        assert shown_rgb_bytes(surface=surface) == bytes((70, 80, 90)) * 12

    def test_an_opaque_alpha_surface_shows_its_colours(self):
        """Cocoa's format with every pixel opaque (the engine's frames)."""
        surface = pygame.Surface(SURFACE_SIZE, depth=32, masks=ALPHA_MASKS)
        surface.fill((70, 80, 90, OPAQUE))

        assert shown_rgb_bytes(surface=surface) == bytes((70, 80, 90)) * 12

    def test_alpha_0_shows_black_and_any_other_alpha_its_colour(self):
        """Row by row: the transparent pixel is black, the translucent one keeps its colour."""
        surface = pygame.Surface(SURFACE_SIZE, depth=32, masks=ALPHA_MASKS)
        surface.fill((70, 80, 90, 0))
        surface.set_at((1, 0), (40, 50, 60, 1))

        shown = shown_rgb_bytes(surface=surface)

        assert shown[:6] == bytes((0, 0, 0, 40, 50, 60))
        assert shown[6:] == bytes(30)
