"""A sprite loaded from text: the engine's side of ``sprite_toml``.

``sprite_toml`` turns a sprite file's text into data and back without pygame; this module turns
the text into the sprite the engine draws. It is the one path a sprite loads by:
``AnimatedSprite._load_toml`` reads a file's text and calls the same ``AnimatedSprite.load_text``
that ``sprite_from_text`` calls, so a sprite from text and from a file are the same sprite. No
temporary file is involved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pygame

from glitchygames.color import MAGENTA_TRANSPARENCY_KEY

from .animated import AnimatedSprite
from .constants import SPRITE_GLYPHS
from .frame import SpriteFrame

if TYPE_CHECKING:
    from collections.abc import Sequence


class SpriteColorLimitError(ValueError):
    """Frames use more distinct colors than a sprite file has glyphs for.

    Attributes:
        color_count: How many distinct RGBA colors the frames use.
        limit: How many colors a sprite file holds (the size of the glyph set).

    """

    def __init__(self, *, color_count: int, limit: int) -> None:
        """Record the count and the limit, and say both in the message.

        Args:
            color_count: How many distinct RGBA colors the frames use.
            limit: How many colors a sprite file holds.

        """
        super().__init__(
            f'The frames use {color_count} distinct colors; a sprite file holds at most {limit}'
        )
        self.color_count = color_count
        self.limit = limit


def sprite_from_text(*, text: str, source_name: str) -> AnimatedSprite:
    """Build a sprite from the text of a sprite file.

    The sprite is what ``SpriteFactory.load_sprite`` returns for the same text in a file: an
    ``AnimatedSprite`` (static text is one frame), in no sprite group. The caller sets what
    belongs to the game, such as ``COORDINATE_SPACE``. Use ``SpriteFactory.load_sprite_from_text``
    to also refuse text that is neither a static nor an animated sprite, as a file is.

    Args:
        text: The sprite file's TOML text.
        source_name: What the text came from (a file name, a console); it names the text in an
            error and in the warnings about pixel rows the loader repaired.

    Returns:
        The loaded sprite. Text that is not valid TOML is refused with a ValueError naming
        ``source_name``.

    """
    sprite = AnimatedSprite(groups=None)
    sprite.load_text(text=text, source_name=source_name)
    return sprite


def sprite_to_text(*, sprite: AnimatedSprite) -> str:
    """Write a sprite as the text of a sprite file.

    This is the text ``AnimatedSprite.save`` writes to its file: a single animation with one
    frame in the static layout (pixels in ``[sprite]``), anything else with its ``[[animation]]``
    tables. No temporary file is involved. ``sprite.to_text()`` is the same text as a method.

    Args:
        sprite: The sprite to write.

    Returns:
        The sprite file's TOML text; ``sprite_from_text`` loads it back to the same sprite.

    """
    return sprite.to_text()


def surface_rgba_pixels(*, surface: pygame.Surface) -> list[tuple[int, int, int, int]]:
    """Read a surface's pixels as (red, green, blue, alpha), row by row.

    A surface with no alpha channel reads as fully opaque.

    Args:
        surface: The surface to read.

    Returns:
        One tuple per pixel, row-major: the first row left to right, then the next.

    """
    width, height = surface.get_size()
    # pygame-ce has no surfarray.array4d (BUGS.md #87), so read the color and alpha planes
    # separately; both are indexed [x, y]
    color_planes: Any = pygame.surfarray.array3d(surface)
    alpha_plane: Any = pygame.surfarray.array_alpha(surface)
    pixels: list[tuple[int, int, int, int]] = []
    for y in range(height):
        for x in range(width):
            red, green, blue = color_planes[x, y]
            pixels.append((int(red), int(green), int(blue), int(alpha_plane[x, y])))
    return pixels


# The two colors the sprite format writes with its transparency key's own glyph
_KEY_GLYPH_COLORS = frozenset({(*MAGENTA_TRANSPARENCY_KEY, 0), (*MAGENTA_TRANSPARENCY_KEY, 255)})


def _canonical_pixel(*, pixel: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Give every fully transparent pixel the one color the format writes for it.

    An image often carries arbitrary RGB under alpha 0; each would take a glyph of its own for
    a color nobody sees. They all become the transparency key, magenta, with alpha 0.

    Returns:
        The pixel, or the transparent key when its alpha is 0.

    """
    if pixel[3] == 0:
        return (*MAGENTA_TRANSPARENCY_KEY, 0)
    return pixel


def sprite_text_from_frames(
    *,
    frames: Sequence[pygame.Surface],
    frame_intervals: Sequence[float],
    name: str,
) -> str:
    """Write an image's frames as the text of a sprite file.

    The frames become one animation named ``name``, each with its own interval; a single frame
    is written in the static layout. Pixels, including partial alpha, are kept exactly, with
    two exceptions that come from the format's transparency key (magenta, 255, 0, 255):

    - Every fully transparent pixel (alpha 0) is written as the key, whatever its RGB.
    - An opaque magenta pixel is written as the key too, and loads and draws as transparent:
      the format cannot tell the two apart. The color is lost, not changed to another.

    This touches no files: the caller decodes the image and passes the surfaces.

    Args:
        frames: The frames, all the same size.
        frame_intervals: Each frame's display time in seconds, one per frame.
        name: The sprite's name, also its animation's name.

    Returns:
        The sprite file's TOML text.

    Raises:
        SpriteColorLimitError: If the frames together use more distinct colors than a sprite
            file has glyphs for. Colors are never reduced silently.
        ValueError: If there are no frames, the number of ``frame_intervals`` differs from the
            number of frames, or the frames are not all the same size.

    """
    if not frames:
        message = 'A sprite needs at least one frame'
        raise ValueError(message)
    if len(frame_intervals) != len(frames):
        message = (
            f'frame_intervals has {len(frame_intervals)} entries for {len(frames)} frames; '
            'there must be one interval per frame'
        )
        raise ValueError(message)
    first_size = frames[0].get_size()
    for index, frame_surface in enumerate(frames):
        if frame_surface.get_size() != first_size:
            message = (
                f'Every frame must be the same size: frame 0 is {first_size} but frame {index} '
                f'is {frame_surface.get_size()}'
            )
            raise ValueError(message)

    frame_pixels = [
        [_canonical_pixel(pixel=pixel) for pixel in surface_rgba_pixels(surface=surface)]
        for surface in frames
    ]
    # The transparency key's glyph is outside the glyph set, so the key (what a transparent pixel
    # becomes) and an opaque magenta pixel (which the format cannot tell from it) take none
    distinct_colors = {
        pixel for pixels in frame_pixels for pixel in pixels if pixel not in _KEY_GLYPH_COLORS
    }
    if len(distinct_colors) > len(SPRITE_GLYPHS):
        raise SpriteColorLimitError(color_count=len(distinct_colors), limit=len(SPRITE_GLYPHS))

    sprite = AnimatedSprite(groups=None)
    sprite.name = name
    sprite_frames: list[SpriteFrame] = []
    for pixels, interval in zip(frame_pixels, frame_intervals, strict=True):
        frame = SpriteFrame(pygame.Surface(first_size, pygame.SRCALPHA), duration=interval)
        frame.set_pixel_data(pixels)
        sprite_frames.append(frame)
    sprite.add_animation(name, sprite_frames)
    return sprite_to_text(sprite=sprite)
