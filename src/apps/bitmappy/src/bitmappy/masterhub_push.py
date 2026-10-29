"""Turn the edited sprite into frames for a MasterHUB web hub, and de-duplicate pushing them.

In the browser studio the MasterHUB web hub runs in a sibling iframe and mirrors whatever sprite we
post onto its center screens (the dial and the centermost key). This module holds the parts that
are pure Python and need no browser: turning the canvas into a flat RGBA frame (magenta left in,
because the hub makes it transparent -- its chroma key), and a small object that posts a frame only
when it changes. The actual browser wiring -- building a ``postMessage`` poster from ``js`` and
calling it each frame -- lives in the browser layer, which this module never imports.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

LOG = logging.getLogger('game.bitmappy.masterhub_push')

BITMAPPY_SOURCE = 'masterhub-bitmappy'  # tags our messages so the studio relays them to the hub
FRAME_TYPE = 'frame'  # a posted canvas frame

_RGBA_LENGTH = 4
_OPAQUE_ALPHA = 255


class _Canvas(Protocol):
    """What the push needs from the editor's canvas: its native pixels and dimensions."""

    pixels: list[tuple[int, ...]]
    pixels_across: int
    pixels_tall: int


def canvas_rgba(canvas: _Canvas) -> tuple[bytes, int, int]:
    """Turn the canvas's native pixels into a flat RGBA byte string with its width and height.

    Row-major, four bytes per pixel. A pixel stored as RGB (three components) is padded to opaque
    RGBA. Magenta is left as-is; the hub makes it transparent.

    Returns:
        ``(pixels, width, height)`` -- the RGBA bytes and the canvas's native dimensions.
    """
    data = bytearray()
    for pixel in canvas.pixels:
        if len(pixel) == _RGBA_LENGTH:
            data.extend(pixel)
        else:
            data.extend((*pixel, _OPAQUE_ALPHA))
    return bytes(data), canvas.pixels_across, canvas.pixels_tall


class MasterHubPush:
    """Posts the canvas to the hub when it changes, de-duplicated, and on demand."""

    def __init__(self, canvas: _Canvas, *, poster: Callable[[bytes, int, int], None]) -> None:
        """Post ``canvas`` frames through ``poster`` (called ``poster(pixels, width, height)``)."""
        self._canvas = canvas
        self._poster = poster
        self._last: bytes | None = None

    def push_if_changed(self) -> None:
        """Post the canvas if its pixels differ from the last post (called once per frame)."""
        pixels, width, height = canvas_rgba(self._canvas)
        if pixels == self._last:
            return
        self._last = pixels
        self._poster(pixels, width, height)

    def push_now(self) -> None:
        """Post the current canvas unconditionally (the first frame, or a forced refresh)."""
        pixels, width, height = canvas_rgba(self._canvas)
        self._last = pixels
        self._poster(pixels, width, height)
