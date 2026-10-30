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
* the three **M003K knobs** get a **fixed color legend** (blue/green/red by knob index): the knobs
  are bitmappy's RGB color picker, and each knob's LED names the channel it drives. It never
  changes, so it is posted on connect only (``push_now``), not per frame.
* the five **M005S faders** get their own **fixed color legend** (``FADER_LED_COLORS`` by fader
  index, left to right): the faders are bitmappy's H/S/V/alpha/onion-skin controls, and each
  fader's LED names what it drives. Like the knob legend, it is posted on connect only.
* the **current colorwell color** is posted live (the ``color`` message, de-duplicated) for the hub
  to show on its base LED, the key borders and the deck's GLITCHY GAMES label.

The knobs are also an **input**: the hub forwards each knob turn (its index and a signed delta) and
``MasterHubPush.apply_knob_delta`` nudges that knob's color channel, so the knobs double as the
editor's R/G/B color picker.

Magenta is left in both screens -- the hub makes it transparent (its chroma key). The browser wiring
that builds the ``postMessage`` posters lives in the browser layer, which this module never imports.
"""

from __future__ import annotations

import colorsys
import logging
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

LOG = logging.getLogger('game.bitmappy.masterhub_push')

BITMAPPY_SOURCE = 'masterhub-bitmappy'  # tags our messages so the studio relays them to the hub
FRAME_TYPE = 'frame'  # the live dial frame (the selected strip's playing preview frame)
KEY_TYPE = 'key'  # the fixed center-key reference (the idle first frame)
KNOB_COLORS_TYPE = 'knob_colors'  # the fixed M003K knob LED legend (posted on connect only)
KNOB_DELTA_TYPE = 'knob_delta'  # a hub -> bitmappy turn: a knob index and a signed channel delta
FADER_TYPE = 'fader'  # a hub -> bitmappy fader move: a fader index and its absolute 0-100 position
FADER_COLORS_TYPE = 'fader_colors'  # the fixed M005S fader LED legend (posted on connect only)
COLOR_TYPE = (
    'color'  # bitmappy -> hub: the current colorwell color, for the base LED, keys and deck
)

_RGBA_LENGTH = 4
_OPAQUE_ALPHA = 255

RGB = tuple[int, int, int]
_Frame = tuple[bytes, int, int]  # (raw RGBA pixels, width, height)

# The fixed knob LED legend, indexed by M003K knob index. The three knobs are bitmappy's RGB color
# picker, and each knob's LED color names the channel it drives: knob 0 (top) -> the blue channel,
# knob 1 (bottom right) -> the green channel, knob 2 (bottom left) -> the red channel. It never
# changes, so it is signaled once on connect; the hub sets each knob's solid LED to this color.
KNOB_LED_COLORS: tuple[RGB, ...] = ((0, 0, 255), (0, 255, 0), (255, 0, 0))

# The color channel each M003K knob drives, by knob index -- the inverse of the LED legend above, so
# the LED color a knob shows is the channel a turn moves. The hub sends only a knob index and a
# signed delta; this is the single place that index becomes a channel ('R', 'G' or 'B').
KNOB_CHANNELS: tuple[str, ...] = ('B', 'G', 'R')

_MIN_CHANNEL = 0
_MAX_CHANNEL = 255

# What each M005S fader drives, by fader index: the color's hue, saturation and value, then its
# alpha, then the onion-skin translucency. Each fader's 0-100 position is a 0-100% of its target's
# range (a ~100-step resolution, the accepted tradeoff). Faders are absolute, so each sets its
# target directly; the H/S/V faders go through the current color so the other components survive.
_FADER_HUE = 0
_FADER_SATURATION = 1
_FADER_VALUE = 2
_FADER_ALPHA = 3
_FADER_ONION_SKIN = 4
_FADER_MAX = 100  # a fader's position runs 0-100

# The fixed fader LED legend, indexed by M005S fader index (left to right, as the hub is mounted).
# Like the knob legend, each fader's LED color names what it controls -- but hue, saturation, value,
# alpha and onion-skin have no canonical colors, so these are chosen to be distinct from one another
# and from the knobs' blue/green/red: hue yellow, saturation cyan, value white (white reads as
# brightness), alpha magenta, onion orange. Fixed, so it is signaled once on connect; the hub
# lights each fader this color and its own dimmer brightens it to the fader's position.
FADER_LED_COLORS: tuple[RGB, ...] = (
    (255, 255, 0),  # fader 0 (leftmost): hue
    (0, 255, 255),  # fader 1: saturation
    (255, 255, 255),  # fader 2: value
    (255, 0, 255),  # fader 3: alpha
    (255, 128, 0),  # fader 4 (rightmost): onion-skin translucency
)


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
    """What the push touches on the scene: its sprite, its strips' playback and its color picker."""

    selected_animation: str | None

    @property
    def canvas(self) -> _Canvas: ...

    @property
    def film_strips(self) -> Mapping[str, _FilmStrip]: ...

    def get_current_color(self) -> tuple[int, int, int, int]: ...

    def apply_color(self, *, red: int, green: int, blue: int, alpha: int) -> None: ...

    def set_onion_skin_transparency(self, transparency: float) -> None: ...


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

    def __init__(  # ruff: ignore[too-many-arguments]
        self,
        scene: _Scene,
        *,
        post_dial: Callable[[bytes, int, int], None],
        post_key: Callable[[bytes, int, int], None],
        post_knob_colors: Callable[[Sequence[RGB]], None],
        post_fader_colors: Callable[[Sequence[RGB]], None],
        post_color: Callable[[int, int, int, int], None],
    ) -> None:
        """Post ``scene``'s dial frame, key reference, knob/fader LED legends and colorwell color.

        The screen posters are each called ``poster(pixels, width, height)``; ``post_knob_colors``
        and ``post_fader_colors`` are each called ``poster(colors)`` with one RGB tuple per knob
        (``KNOB_LED_COLORS``) or per fader (``FADER_LED_COLORS``); ``post_color`` is called
        ``post_color(red, green, blue, alpha)`` with the current color.
        """
        self._scene = scene
        self._post_dial = post_dial
        self._post_key = post_key
        self._post_knob_colors = post_knob_colors
        self._post_fader_colors = post_fader_colors
        self._post_color = post_color
        self._last_dial: _Frame | None = None
        self._last_key: _Frame | None = None
        self._last_color: tuple[int, int, int, int] | None = None
        self._legends_posted = False

    def push_if_changed(self) -> None:
        """Post the dial frame, key and color if changed, and the fixed legends once (safety net).

        The knob and fader LED legends are fixed, so they ride ``push_now`` on a hub 'ready'. But a
        'ready' can be missed -- the hub announces it once, and if this push was not listening yet
        the legends would never reach the hub while the per-frame color still does, leaving the
        knobs and faders dark. So the first ``push_if_changed`` also posts the legends once; after
        that it posts only the screens and color that changed.
        """
        if not self._legends_posted:
            self._post_legends()
        self._push(force=False)

    def push_now(self) -> None:
        """Post both screens unconditionally and the fixed LED legends (first push / hub 'ready').

        A 'ready' means the hub (re)connected and its LEDs need relighting, so the legends always
        go out here.
        """
        self._post_legends()
        self._push(force=True)

    def _post_legends(self) -> None:
        """Post the fixed knob and fader LED legends, once marked (re-posting them is harmless)."""
        self._post_knob_colors(KNOB_LED_COLORS)
        self._post_fader_colors(FADER_LED_COLORS)
        self._legends_posted = True

    def mark_hub_disconnected(self) -> None:
        """Forget what was pushed, so a reconnecting hub gets a full fresh push (disconnect path).

        The heartbeat calls this when the hub stops answering. It resets the same state a first
        connect assumes empty -- the de-duplicated last frames/color and the legend-posted flag --
        so the next push (on the hub's next pong/'ready') re-handshakes exactly like a fresh
        connection: the legends re-post and every screen redraws, nothing suppressed as unchanged.
        """
        self._last_dial = None
        self._last_key = None
        self._last_color = None
        self._legends_posted = False

    def apply_knob_delta(self, *, knob: int, delta: int) -> None:
        """Nudge the color channel knob ``knob`` drives by ``delta``, clamped to 0-255.

        The knobs are the editor's RGB color picker: ``knob`` names which channel (0 blue, 1 green,
        2 red, via ``KNOB_CHANNELS``) and ``delta`` is the signed turn (clockwise raises). It nudges
        relative to the current color, so a mouse- or eyedropper-set color stays in sync; alpha is
        never touched, and a knob index that maps to no channel is ignored.
        """
        if not 0 <= knob < len(KNOB_CHANNELS):
            return
        channel = KNOB_CHANNELS[knob]
        red, green, blue, alpha = self._scene.get_current_color()
        levels = {'R': red, 'G': green, 'B': blue}
        levels[channel] = max(_MIN_CHANNEL, min(_MAX_CHANNEL, levels[channel] + delta))
        self._scene.apply_color(red=levels['R'], green=levels['G'], blue=levels['B'], alpha=alpha)

    def apply_fader(self, *, fader: int, position: int) -> None:
        """Apply an M005S fader move: 0-2 set the color's H/S/V, 3 its alpha, 4 the onion skin.

        ``position`` is absolute (0-100), read as a 0-100% fraction of the target's range. The
        H/S/V faders convert through the current color so the untouched components survive; a fader
        index with no target is ignored.
        """
        fraction = max(0, min(_FADER_MAX, position)) / _FADER_MAX
        if fader == _FADER_ONION_SKIN:
            self._scene.set_onion_skin_transparency(fraction)
            return
        red, green, blue, alpha = self._scene.get_current_color()
        if fader == _FADER_ALPHA:
            self._scene.apply_color(red=red, green=green, blue=blue, alpha=round(fraction * 255))
            return
        if fader in {_FADER_HUE, _FADER_SATURATION, _FADER_VALUE}:
            hue, saturation, value = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
            if fader == _FADER_HUE:
                hue = fraction
            elif fader == _FADER_SATURATION:
                saturation = fraction
            else:
                value = fraction
            new_red, new_green, new_blue = colorsys.hsv_to_rgb(hue, saturation, value)
            self._scene.apply_color(
                red=round(new_red * 255),
                green=round(new_green * 255),
                blue=round(new_blue * 255),
                alpha=alpha,
            )

    def _push(self, *, force: bool) -> None:
        dial = preview_frame(self._scene)
        if dial is not None and (force or dial != self._last_dial):
            self._last_dial = dial
            self._post_dial(*dial)
        key = idle_frame(self._scene)
        if key is not None and (force or key != self._last_key):
            self._last_key = key
            self._post_key(*key)
        color = self._scene.get_current_color()
        if force or color != self._last_color:
            self._last_color = color
            self._post_color(*color)
