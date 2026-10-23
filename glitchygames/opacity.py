"""Opaque frames on displays whose pixels carry alpha (BUGS.md #142).

On real macOS windows (SDL's cocoa video driver) the display surface has per-pixel alpha, and
the window shows a pixel with alpha 0 as black whatever its red, green and blue; the dummy and
x11 drivers' displays have no alpha channel, so the same frame shows its colours there. On such
a display a plain ``pygame.Surface(size)`` (and ``convert()``'s result) takes the display's
format, alpha mask included, without the SRCALPHA flag: blitting it copies its alpha unblended,
and alpha-blending onto it leaves alpha 0. A frame can therefore look black, or have black
holes, only on macOS.

The engine keeps every frame opaque: the scene background is opaque (``Scene.background_color``
refuses translucent colours), ``Scene.screenshot`` is opaque, and ``SceneManager`` makes the
display opaque before each present (``make_opaque``, about 0.04 ms at 800x600), so the window
shows the colours the dummy driver shows.
"""

from __future__ import annotations

import pygame

# The alpha of a fully opaque pixel
OPAQUE = 255


def has_per_pixel_alpha(*, surface: pygame.Surface) -> bool:
    """Tell whether a surface's pixels carry an alpha channel (cocoa's display format does).

    Args:
        surface: The surface.

    Returns:
        bool: True when the surface's pixel format has an alpha mask.

    """
    return surface.get_masks()[3] != 0


def make_opaque(*, surface: pygame.Surface) -> None:
    """Set every pixel's alpha to 255, keeping its red, green and blue (never blending them).

    The channel-wise maximum with opaque black leaves red, green and blue as they are and
    raises alpha to 255. A surface without per-pixel alpha is already opaque and is left alone.

    Args:
        surface: The surface made opaque in place.

    """
    if not has_per_pixel_alpha(surface=surface):
        return
    surface.fill((0, 0, 0, OPAQUE), special_flags=pygame.BLEND_RGBA_MAX)
