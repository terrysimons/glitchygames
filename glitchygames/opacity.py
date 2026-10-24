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

import numpy as np
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


def every_pixel_has_alpha(*, surface: pygame.Surface) -> bool:
    """Tell whether no pixel of a per-pixel-alpha surface has alpha 0.

    Args:
        surface: A surface with per-pixel alpha.

    Returns:
        bool: True when every pixel's alpha is above zero.

    """
    # A mask's bits are set where alpha is above the threshold
    visible_pixels = pygame.mask.from_surface(surface, threshold=0)
    return visible_pixels.count() == surface.get_width() * surface.get_height()


def shown_rgb_bytes(*, surface: pygame.Surface) -> bytes:
    """Return a display's pixels as the window shows them: RGB bytes, alpha 0 shown black.

    On a display with per-pixel alpha (cocoa's) the window shows a pixel with alpha 0 as black
    whatever its red, green and blue; any other alpha shows the colour. A display without an
    alpha channel (dummy, x11) shows its colours. The bytes are row by row, three per pixel
    (``pygame.image.tobytes(surface, 'RGB')``), so two drivers' frames compare byte for byte
    whatever their pixel formats.

    The conversion costs about 0.3 ms at 800x600; the alpha check about 0.3 ms more, on a
    display with per-pixel alpha only, and the masking (numpy) only when some alpha is 0.

    Args:
        surface: The display surface (or any surface).

    Returns:
        bytes: Width x height x 3 bytes of red, green and blue.

    """
    rgb_bytes = pygame.image.tobytes(surface, 'RGB')
    if not has_per_pixel_alpha(surface=surface) or every_pixel_has_alpha(surface=surface):
        return rgb_bytes
    # Row by row, four bytes per pixel: red, green, blue, alpha
    rgba = np.frombuffer(pygame.image.tobytes(surface, 'RGBA'), dtype=np.uint8).reshape(
        surface.get_height(), surface.get_width(), 4
    )
    shown = rgba[:, :, :3].copy()
    shown[rgba[:, :, 3] == 0] = 0
    return shown.tobytes()
