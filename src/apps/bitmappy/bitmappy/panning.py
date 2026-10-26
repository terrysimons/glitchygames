"""Canvas panning for the Bitmappy editor: moving a frame's pixels with Ctrl+Shift+Arrow.

A pan is one gesture: from the first Ctrl+Shift+Arrow press until the arrow, Ctrl or Shift
is released (``BitmapEditorScene.on_key_up_event``). Each press moves the frame's pixels one
step from the pixels the gesture started with, so stepping back and forth inside one gesture
loses nothing. Every step is written straight into the frame (the canvas, the film strip and
a save all see it at once), and the finished gesture becomes one undoable command
(``FrameOperationManager.finish_canvas_panning``).

``PanSession`` holds the gesture's state; ``shift_pixels`` computes one step.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
from pydantic import BaseModel, ConfigDict

from glitchygames.color import RGBA_COMPONENT_COUNT

from .constants import MAGENTA_TRANSPARENT

if TYPE_CHECKING:
    from collections.abc import Sequence

# Releasing any of these keys ends a pan gesture (Ctrl+Shift+Arrow, released in any order)
PAN_GESTURE_KEYS = frozenset({
    pygame.K_LEFT,
    pygame.K_RIGHT,
    pygame.K_UP,
    pygame.K_DOWN,
    pygame.K_LCTRL,
    pygame.K_RCTRL,
    pygame.K_LSHIFT,
    pygame.K_RSHIFT,
})

# Furthest a gesture may move the pixels from where it started, in pixels on each axis
MAX_PAN_DISTANCE = 10

type Pixel = tuple[int, ...]


class PanSession(BaseModel):
    """One pan gesture on one frame.

    Attributes:
        animation: The animation of the frame being panned.
        frame_index: The index of the frame being panned.
        pixels_before: The frame's pixels before the gesture (what undo restores).
        source_pixels: The pixels each step moves (the gesture's start, or the frame as an
            edit made during the gesture left it).
        offset_x: How far the source pixels are moved right (negative: left).
        offset_y: How far the source pixels are moved down (negative: up).
        panned_pixels: The pixels the last step wrote into the frame.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    animation: str
    frame_index: int
    pixels_before: tuple[Pixel, ...]
    source_pixels: tuple[Pixel, ...]
    offset_x: int = 0
    offset_y: int = 0
    panned_pixels: tuple[Pixel, ...]

    @classmethod
    def starting_from(
        cls,
        *,
        animation: str,
        frame_index: int,
        pixels: Sequence[Pixel],
    ) -> PanSession:
        """Start a gesture on a frame that holds the given pixels.

        Args:
            animation: The frame's animation.
            frame_index: The frame's index.
            pixels: The frame's pixels now.

        Returns:
            The new session, not yet moved.

        """
        frame_pixels = tuple(pixels)
        return cls(
            animation=animation,
            frame_index=frame_index,
            pixels_before=frame_pixels,
            source_pixels=frame_pixels,
            panned_pixels=frame_pixels,
        )

    def is_for(self, *, animation: str, frame_index: int) -> bool:
        """Whether this gesture pans the given frame.

        Args:
            animation: The animation name.
            frame_index: The frame index.

        Returns:
            True if the gesture is on that frame.

        """
        return self.animation == animation and self.frame_index == frame_index

    def rebased_on(self, *, pixels: Sequence[Pixel]) -> PanSession:
        """Continue the gesture from pixels an edit changed since its last step.

        The next step moves the edited pixels, so the edit is kept; undo still restores
        the pixels from before the whole gesture.

        Args:
            pixels: The frame's pixels now.

        Returns:
            The session, moving the given pixels from where they are.

        """
        frame_pixels = tuple(pixels)
        return self.model_copy(
            update={
                'source_pixels': frame_pixels,
                'offset_x': 0,
                'offset_y': 0,
                'panned_pixels': frame_pixels,
            },
        )

    def moved_to(
        self,
        *,
        offset_x: int,
        offset_y: int,
        panned_pixels: Sequence[Pixel],
    ) -> PanSession:
        """Record a step that wrote the given pixels into the frame.

        Args:
            offset_x: The new horizontal offset from the source pixels.
            offset_y: The new vertical offset from the source pixels.
            panned_pixels: The pixels written into the frame.

        Returns:
            The session after the step.

        """
        return self.model_copy(
            update={
                'offset_x': offset_x,
                'offset_y': offset_y,
                'panned_pixels': tuple(panned_pixels),
            },
        )

    @property
    def changed_the_frame(self) -> bool:
        """Whether the frame now differs from before the gesture (whether undo has work)."""
        return self.panned_pixels != self.pixels_before


def can_pan_to(*, offset_x: int, offset_y: int) -> bool:
    """Whether a gesture may move its pixels this far.

    Args:
        offset_x: The horizontal offset from the gesture's source pixels.
        offset_y: The vertical offset from the gesture's source pixels.

    Returns:
        True if both offsets are within MAX_PAN_DISTANCE.

    """
    return abs(offset_x) <= MAX_PAN_DISTANCE and abs(offset_y) <= MAX_PAN_DISTANCE


def transparent_pixel_for(pixels: Sequence[Pixel]) -> Pixel:
    """Return the transparent (magenta) pixel in the form the pixel data uses.

    Pixel data that holds any RGBA pixel is RGBA data, whose magenta is opaque
    (255, 0, 255, 255), as the editor's own RGBA canvases are filled; all-RGB data gets
    RGB magenta.

    Args:
        pixels: The pixel data.

    Returns:
        The transparent pixel.

    """
    if any(len(pixel) == RGBA_COMPONENT_COUNT for pixel in pixels):
        return (*MAGENTA_TRANSPARENT, 255)
    return MAGENTA_TRANSPARENT


def shift_pixels(
    *,
    pixels: Sequence[Pixel],
    width: int,
    height: int,
    offset_x: int,
    offset_y: int,
) -> list[Pixel]:
    """Move row-by-row pixel data by an offset, filling uncovered pixels with transparency.

    Pixels moved past an edge are dropped.

    Args:
        pixels: The pixel data (width * height pixels, row by row).
        width: Pixels per row.
        height: Rows.
        offset_x: How far to move right (negative: left).
        offset_y: How far to move down (negative: up).

    Returns:
        The moved pixel data.

    """
    transparent_pixel = transparent_pixel_for(pixels)
    shifted_pixels: list[Pixel] = []
    for y in range(height):
        source_y = y - offset_y
        for x in range(width):
            source_x = x - offset_x
            if 0 <= source_x < width and 0 <= source_y < height:
                shifted_pixels.append(pixels[source_y * width + source_x])
            else:
                shifted_pixels.append(transparent_pixel)
    return shifted_pixels
