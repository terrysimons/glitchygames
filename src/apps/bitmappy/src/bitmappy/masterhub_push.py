"""Turn the edited sprite into frames for a MasterHUB web hub, and de-duplicate pushing them.

In the browser studio the MasterHUB web hub runs in a sibling iframe and mirrors whatever we post
onto its center screens. We drive the two screens with raw RGBA pixels, the same way a static frame
is driven:

* the **dial** gets the selected animation strip's **currently-playing preview frame**. bitmappy
  already animates each strip's preview on its own clock, so we read which frame it is showing now
  (``get_current_preview_frame``) and send that one frame; because the preview keeps advancing, the
  next push is the next frame -- the hub never re-plays an animation, it just shows the frame we
  send, exactly like a static one.
* the **centermost key** gets a **fixed reference**: the idle (first) animation's first frame.

Magenta is left in both -- the hub makes it transparent (its chroma key). The browser wiring that
builds the ``postMessage`` posters lives in the browser layer, which this module never imports.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

LOG = logging.getLogger('game.bitmappy.masterhub_push')

BITMAPPY_SOURCE = 'masterhub-bitmappy'  # tags our messages so the studio relays them to the hub
FRAME_TYPE = 'frame'  # the live dial frame (the selected strip's playing preview frame)
KEY_TYPE = 'key'  # the fixed center-key reference (the idle first frame)

_RGBA_LENGTH = 4
_OPAQUE_ALPHA = 255

_Frame = tuple[bytes, int, int]  # (raw RGBA pixels, width, height)


class _SpriteFrame(Protocol):
    def get_pixel_data(self) -> list[tuple[int, ...]]: ...
    def get_size(self) -> tuple[int, int]: ...


class _FilmStrip(Protocol):
    def get_current_preview_frame(self, anim_name: str) -> int: ...


class _AnimatedSprite(Protocol):
    @property
    def animations(self) -> Mapping[str, Sequence[_SpriteFrame]]: ...


class _Canvas(Protocol):
    @property
    def animated_sprite(self) -> _AnimatedSprite: ...


class _Scene(Protocol):
    """What the push reads from the scene: its sprite and its strips' preview playback."""

    selected_animation: str | None

    @property
    def canvas(self) -> _Canvas: ...

    @property
    def film_strips(self) -> Mapping[str, _FilmStrip]: ...


def _rgba_bytes(pixels: list[tuple[int, ...]]) -> bytes:
    """Flatten a list of RGB(A) pixel tuples to row-major RGBA bytes (RGB padded to opaque).

    Returns:
        The flat RGBA byte string.
    """
    data = bytearray()
    for pixel in pixels:
        if len(pixel) == _RGBA_LENGTH:
            data.extend(pixel)
        else:
            data.extend((*pixel, _OPAQUE_ALPHA))
    return bytes(data)


def _first_animation(sprite: _AnimatedSprite) -> str | None:
    """The idle/first animation name (insertion order), or None when the sprite has none.

    Returns:
        The first animation name, or None.
    """
    return next(iter(sprite.animations), None)


def _frame_rgba(frame: _SpriteFrame) -> _Frame:
    """A sprite frame as ``(raw RGBA pixels, width, height)``.

    Returns:
        The frame's flat RGBA bytes with its native size.
    """
    width, height = frame.get_size()
    return _rgba_bytes(frame.get_pixel_data()), width, height


def preview_frame(scene: _Scene) -> _Frame | None:
    """The selected strip's currently-playing preview frame as raw RGBA + size (the dial frame).

    Reads which frame the selected strip's preview is showing right now and returns that frame's
    pixels; a strip with no preview (or none loaded) falls back to frame 0. Returns None when there
    is no selectable animation or frame yet.

    Returns:
        ``(pixels, width, height)`` or ``None``.
    """
    sprite = scene.canvas.animated_sprite
    anim = scene.selected_animation or _first_animation(sprite)
    if anim is None:
        return None
    frames: Sequence[_SpriteFrame] = sprite.animations.get(anim, [])
    if not frames:
        return None
    strip = scene.film_strips.get(anim)
    index = strip.get_current_preview_frame(anim) if strip is not None else 0
    index = max(0, min(index, len(frames) - 1))  # clamp the preview index to this strip's frames
    return _frame_rgba(frames[index])


def idle_frame(scene: _Scene) -> _Frame | None:
    """The idle (first) animation's first frame as raw RGBA + size (the fixed center-key reference).

    Returns:
        ``(pixels, width, height)`` or ``None`` when the sprite has no frames.
    """
    sprite = scene.canvas.animated_sprite
    anim = _first_animation(sprite)
    if anim is None:
        return None
    frames: Sequence[_SpriteFrame] = sprite.animations.get(anim, [])
    if not frames:
        return None
    return _frame_rgba(frames[0])


class MasterHubPush:
    """Posts the dial frame and center-key reference to the hub when they change, and on demand."""

    def __init__(
        self,
        scene: _Scene,
        *,
        post_dial: Callable[[bytes, int, int], None],
        post_key: Callable[[bytes, int, int], None],
    ) -> None:
        """Post ``scene``'s dial frame via ``post_dial`` and its key reference via ``post_key``.

        Each poster is called ``poster(pixels, width, height)``.
        """
        self._scene = scene
        self._post_dial = post_dial
        self._post_key = post_key
        self._last_dial: _Frame | None = None
        self._last_key: _Frame | None = None

    def push_if_changed(self) -> None:
        """Post the dial frame and key reference, each only if it changed (once per frame)."""
        self._push(force=False)

    def push_now(self) -> None:
        """Post both unconditionally (the first push, or a hub 'ready' re-post)."""
        self._push(force=True)

    def _push(self, *, force: bool) -> None:
        dial = preview_frame(self._scene)
        if dial is not None and (force or dial != self._last_dial):
            self._last_dial = dial
            self._post_dial(*dial)
        key = idle_frame(self._scene)
        if key is not None and (force or key != self._last_key):
            self._last_key = key
            self._post_key(*key)
