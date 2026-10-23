"""Animated sprite classes for GlitchyGames.

This module contains the animated sprite implementation that extends the
basic sprite functionality to support multi-frame animations with flexible
timing and playback control.
"""

from __future__ import annotations

import hashlib
import logging
import math
import operator
import tomllib
from collections import Counter
from enum import Enum
from pathlib import Path
from typing import IO, Any, Self, cast, override

import pygame

from glitchygames.animation import AnimationStateMachine
from glitchygames.collision.bounds import trims_transparent_hitbox

# YAML support removed - TOML only
# Import constants
from glitchygames.color import (
    MAGENTA_TRANSPARENCY_KEY,
    MAX_COLOR_CHANNEL_VALUE,
    MAX_PER_PIXEL_ALPHA,
    RGBA_COMPONENT_COUNT,
)

from .animated_interface import AnimatedSpriteInterface
from .constants import DEFAULT_FILE_FORMAT, SPRITE_GLYPHS
from .frame import FrameManager, SpriteFrame
from .pixel_utils import (
    convert_pixels_to_rgb_if_possible,
    convert_pixels_to_rgba_if_needed,
    create_alpha_surface,
    create_indexed_surface,
    extract_pixel_colors,
    is_color_transparent,
    lookup_pixel_char,
    needs_alpha_channel,
    normalize_pixel_for_color_map,
)

# Characters TOML basic strings must escape with a short escape sequence
# (https://toml.io/en/v1.0.0#string)
TOML_SHORT_ESCAPES = {
    '\\': '\\\\',
    '"': '\\"',
    '\b': '\\b',
    '\t': '\\t',
    '\n': '\\n',
    '\f': '\\f',
    '\r': '\\r',
}
# Code points below this, and DEL, are control characters TOML strings must escape
TOML_FIRST_PRINTABLE_CODE_POINT = 0x20
TOML_DELETE_CODE_POINT = 0x7F
# Bare TOML keys may use only these characters
TOML_BARE_KEY_CHARACTERS = frozenset(
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-'
)


def toml_basic_string(value: str) -> str:
    """Quote a string as a TOML basic string, escaping what TOML requires.

    Returns:
        str: The quoted, escaped string: a quote becomes backslash-quote, a backslash
        becomes two backslashes and control characters use their escape sequences.

    """
    escaped_characters: list[str] = []
    for character in value:
        if character in TOML_SHORT_ESCAPES:
            escaped_characters.append(TOML_SHORT_ESCAPES[character])
        elif (
            ord(character) < TOML_FIRST_PRINTABLE_CODE_POINT
            or ord(character) == TOML_DELETE_CODE_POINT
        ):
            escaped_characters.append(f'\\u{ord(character):04X}')
        else:
            escaped_characters.append(character)
    return '"' + ''.join(escaped_characters) + '"'


def toml_multiline_basic_string(value: str) -> str:
    """Quote a string as a TOML multi-line basic string (triple quotes), escaping as needed.

    Newlines stay as real line breaks so descriptions stay readable. Backslashes and quotes
    are escaped (so no run of three quotes can end the string early), as are other control
    characters, and a leading newline is written as an escape because TOML drops a newline
    right after the opening quotes.

    Returns:
        str: The value wrapped in triple quotes.

    """
    escaped_characters: list[str] = []
    for position, character in enumerate(value):
        if character == '\n' and position > 0:
            escaped_characters.append(character)
        elif character in TOML_SHORT_ESCAPES:
            escaped_characters.append(TOML_SHORT_ESCAPES[character])
        elif (
            ord(character) < TOML_FIRST_PRINTABLE_CODE_POINT
            or ord(character) == TOML_DELETE_CODE_POINT
        ):
            escaped_characters.append(f'\\u{ord(character):04X}')
        else:
            escaped_characters.append(character)
    return '"""' + ''.join(escaped_characters) + '"""'


def toml_key(key: str) -> str:
    """Return a TOML key: bare when TOML allows it, otherwise a quoted basic string.

    Returns:
        str: The key as written in a TOML file.

    """
    if key and all(character in TOML_BARE_KEY_CHARACTERS for character in key):
        return key
    return toml_basic_string(key)


def toml_scalar(value: object) -> str:
    """Format a string, boolean, integer or float as a TOML value.

    Returns:
        str: The value as written in a TOML file.

    Raises:
        TypeError: For any other type (TOML tables, arrays and dates are not supported here).

    """
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        return toml_basic_string(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return 'nan'
        if math.isinf(value):
            return 'inf' if value > 0 else '-inf'
        return repr(value)
    msg = f'Cannot write {type(value).__name__} value {value!r} as a TOML scalar'
    raise TypeError(msg)


class FrameAnchor(Enum):
    """Which point of every animation frame's hitbox is kept in place when drawn.

    Frames are authored top-left aligned. When their hitboxes differ (a short running frame
    next to a tall idle frame), anchoring moves each frame so the chosen part of its hitbox
    lands on the same part of the reference hitbox: the sprite-level default hitbox, else the
    union of all frames' hitboxes. Edge anchors move only their own axis; CENTER and the
    corners move both. Alternatively, author the art already aligned and keep NONE.

    ============  ==========================  ==========================
    Anchor        Horizontal (x)              Vertical (y)
    ============  ==========================  ==========================
    NONE          as authored                 as authored
    TOP           as authored                 hitbox tops aligned
    BOTTOM        as authored                 hitbox bottoms aligned
    LEFT          hitbox left edges aligned   as authored
    RIGHT         hitbox right edges aligned  as authored
    CENTER        hitbox centres aligned      hitbox centres aligned
    TOP_LEFT      left edges                  tops
    TOP_RIGHT     right edges                 tops
    BOTTOM_LEFT   left edges                  bottoms
    BOTTOM_RIGHT  right edges                 bottoms
    ============  ==========================  ==========================

    Walkers use BOTTOM, spinners and floaters CENTER, hanging things TOP.

    Contract: the sprite's rect must be placed at its world position (through the camera)
    plus AnimatedSprite.draw_offset. The engine does this for world sprites
    (CoordinateSpace.WORLD, e.g. Papyrus's PapyrusPlayer: glitchygames.world.screen_position_for
    adds draw_offset); a game that places an anchored sprite's rect itself must add it.
    hitbox already includes the offset, and the debug overlay
    (glitchygames.debug.panels.screen_rect_for) takes it back out of rect, so a rect placed
    without it shows outlines and collisions that do not match the drawing.
    """

    NONE = 'none'  # Draw frames as authored (default)
    TOP_LEFT = 'top_left'
    TOP = 'top'
    TOP_RIGHT = 'top_right'
    LEFT = 'left'
    CENTER = 'center'
    RIGHT = 'right'
    BOTTOM_LEFT = 'bottom_left'
    BOTTOM = 'bottom'
    BOTTOM_RIGHT = 'bottom_right'


# (horizontal edge, vertical edge) each anchor aligns: 'start', 'center', 'end', or None to
# leave that axis as authored
_FRAME_ANCHOR_EDGES: dict[FrameAnchor, tuple[str | None, str | None]] = {
    FrameAnchor.TOP_LEFT: ('start', 'start'),
    FrameAnchor.TOP: (None, 'start'),
    FrameAnchor.TOP_RIGHT: ('end', 'start'),
    FrameAnchor.LEFT: ('start', None),
    FrameAnchor.CENTER: ('center', 'center'),
    FrameAnchor.RIGHT: ('end', None),
    FrameAnchor.BOTTOM_LEFT: ('start', 'end'),
    FrameAnchor.BOTTOM: (None, 'end'),
    FrameAnchor.BOTTOM_RIGHT: ('end', 'end'),
}


def _doubled_anchor_offset(
    *,
    reference_start: int,
    reference_size: int,
    frame_start: int,
    frame_size: int,
    edge: str | None,
) -> int:
    """Return twice the offset that puts a frame span's edge on the reference span's edge.

    Returns:
        int: The doubled offset (exact for half-pixel centres); 0 when edge is None.

    """
    if edge is None:
        return 0
    return _doubled_edge(reference_start, reference_size, edge) - _doubled_edge(
        frame_start, frame_size, edge
    )


def _doubled_edge(start: int, size: int, edge: str) -> int:
    """Return twice the coordinate of a span's start, centre or end (exact for half pixels).

    Returns:
        int: 2 * start, 2 * start + size, or 2 * (start + size).

    """
    match edge:
        case 'start':
            return 2 * start
        case 'center':
            return 2 * start + size
        case _:
            return 2 * (start + size)


# Import detect_file_format function
try:
    from glitchygames.bitmappy import detect_file_format
except ImportError:
    # Fallback if bitmappy module is not available
    def detect_file_format(filename: str) -> str:  # ruff: ignore[unused-function-argument]
        """Detect file format based on extension.

        Currently only supports TOML format. To add new formats:
        1. Add file extension detection here
        2. Add analysis method in _analyze_file()
        3. Add save/load methods in AnimatedSprite
        4. Update tests
        See LOADER_README.md for detailed implementation guide.

        Returns:
            str: The resulting string.

        """
        # NOTE: Only TOML format is currently supported.
        # See LOADER_README.md for adding new format detection.
        return 'toml'  # Default to TOML only


LOG = logging.getLogger('game.sprites.animated')

# Error message templates
ERR_ANIMATION_NOT_FOUND = "Animation '{}' not found"
ERR_ANIMATION_NAME_EXISTS = "Animation '{}' already exists"
ERR_ANIMATION_NOT_FOUND_AVAILABLE = "Animation '{}' not found. Available animations: {}"
ERR_NO_ANIMATION_SET = 'No animation is currently set'
ERR_FRAME_INDEX_OUT_OF_RANGE = "Frame index {} out of range for animation '{}'"
ERR_FRAME_INDEX_OUT_OF_RANGE_WITH_BOUNDS = "Frame index {} out of range for animation '{}' (0-{})"
ERR_UNSUPPORTED_FORMAT = 'Unsupported format: {}. Only TOML is currently supported.'
ERR_SPRITE_FILE_NOT_FOUND = 'Sprite file not found: {}'
ERR_TOML_LOAD_FAILED = 'Error loading TOML file {}: {}'
ERR_TOO_MANY_COLORS = 'Too many colors (max {})'

# How a transparent pixel is stored in a per-pixel alpha sprite image: the magenta key at alpha 0
TRANSPARENT_MAGENTA = (*MAGENTA_TRANSPARENCY_KEY, 0)


class AnimatedSprite(AnimatedSpriteInterface, pygame.sprite.DirtySprite):  # ruff: ignore[too-many-public-methods]
    """A prototype Sprite Animation class with proper dirty sprite integration."""

    log = LOG

    # Override pygame's optional property typing — AnimatedSprite always has
    # a valid image and rect after __init__, so the getter return types narrow
    # out None.  Setters keep the parent's wider parameter types to satisfy LSP.

    @property
    @override
    def image(self) -> pygame.Surface:
        """The sprite image (always non-None for AnimatedSprite)."""
        return self._gg_image

    @image.setter
    def image(self, value: pygame.Surface | None) -> None:
        self._gg_image = cast('pygame.Surface', value)

    @property
    @override
    def rect(self) -> pygame.FRect | pygame.Rect:
        """The sprite rect (always non-None for AnimatedSprite)."""
        return self._gg_rect

    @rect.setter
    def rect(self, value: pygame.FRect | pygame.Rect | None) -> None:
        self._gg_rect = cast('pygame.FRect | pygame.Rect', value)

    @property
    def default_hitbox(self) -> pygame.Rect | None:
        """The sprite-level default hitbox.

        This is the hitbox defined in [sprite.hitbox] in the TOML file.
        Individual frames may override this with per-frame hitboxes.
        """
        return self._default_hitbox

    @default_hitbox.setter
    def default_hitbox(self, value: pygame.Rect | None) -> None:
        """Set the sprite-level default hitbox."""
        self._default_hitbox = value

    @property
    def hitbox(self) -> pygame.Rect:
        """The effective hitbox for the current frame.

        Hitboxes are in native (TOML) pixels and are multiplied by hitbox_scale, offset
        and size, for sprites drawn scaled up (Papyrus draws at 2x). When hitbox_flip_x is
        True (the game draws the image mirrored, e.g. facing left) the result is mirrored
        within the drawn frame width: x = drawn_width - (x + width).

        Resolution order:
        1. Current frame's explicit hitbox (per-frame override)
        2. Sprite-level default hitbox ([sprite.hitbox])
        3. The visible pixels of the current frame's image (measured once per
           frame surface, see SpriteFrame.opaque_bounds), or the frame's full
           rect when the sprite sets TRIM_TRANSPARENT_HITBOX = False

        Always returns a valid pygame.Rect — game code never needs null checks.
        """
        current_frame = self.get_current_frame()
        if current_frame is None:
            # No frame: the sprite's own rect is already in drawn pixels, so it is not scaled
            return pygame.Rect(0, 0, self._gg_rect.width, self._gg_rect.height)
        drawn_hitbox = self._drawn_hitbox(
            self._native_frame_hitbox(current_frame), native_frame_width=current_frame.rect.width
        )
        # Anchored frames are drawn at an offset (see draw_offset); the hitbox moves with them
        draw_offset_x, draw_offset_y = self.draw_offset
        drawn_hitbox.move_ip(draw_offset_x, draw_offset_y)
        return drawn_hitbox

    def _frame_anchor_reference(self: Self) -> pygame.Rect | None:
        """Return the native hitbox every anchored frame is aligned to.

        The sprite-level default hitbox if there is one, else the union of all frames'
        hitboxes (so every anchor point has a well-defined reference).

        Returns:
            pygame.Rect | None: The reference hitbox, or None without frames.

        """
        if self._default_hitbox is not None:
            return self._default_hitbox
        # Cached per frame set: frames are not changed after loading, so the union is built
        # again only when frames are added, removed or replaced. A frame whose hitbox is
        # edited in place keeps the old union (no game does that; Bitmappy does not anchor).
        current_frames = tuple(frame for frames in self._animations.values() for frame in frames)
        cached_entry = self._frame_anchor_reference_cache
        if cached_entry is None or cached_entry[0] != current_frames:
            cached_entry = (current_frames, self._union_of_frame_hitboxes(current_frames))
            self._frame_anchor_reference_cache = cached_entry
        cached_reference = cached_entry[1]
        return None if cached_reference is None else cached_reference.copy()

    def _union_of_frame_hitboxes(self: Self, frames: tuple[SpriteFrame, ...]) -> pygame.Rect | None:
        """Return the union of the given frames' native hitboxes.

        Returns:
            pygame.Rect | None: The union, or None for no frames.

        """
        frame_hitboxes = [self._native_frame_hitbox(frame) for frame in frames]
        if not frame_hitboxes:
            return None
        return frame_hitboxes[0].unionall(frame_hitboxes[1:])

    def _frame_draw_offset(self: Self, frame: SpriteFrame) -> tuple[int, int]:
        """Return where a frame is drawn relative to its authored position (see draw_offset).

        Returns:
            tuple[int, int]: (x, y) offset in drawn pixels; (0, 0) for FrameAnchor.NONE.

        """
        if self.frame_anchor is FrameAnchor.NONE:
            return (0, 0)
        reference = self._frame_anchor_reference()
        if reference is None:
            return (0, 0)
        frame_hitbox = self._native_frame_hitbox(frame)
        horizontal_edge, vertical_edge = _FRAME_ANCHOR_EDGES[self.frame_anchor]
        # Computed in authored (unflipped) native pixels, doubled so centres stay exact
        doubled_offset_x = _doubled_anchor_offset(
            reference_start=reference.x,
            reference_size=reference.width,
            frame_start=frame_hitbox.x,
            frame_size=frame_hitbox.width,
            edge=horizontal_edge,
        )
        doubled_offset_y = _doubled_anchor_offset(
            reference_start=reference.y,
            reference_size=reference.height,
            frame_start=frame_hitbox.y,
            frame_size=frame_hitbox.height,
            edge=vertical_edge,
        )
        drawn_offset_x = doubled_offset_x * self.hitbox_scale // 2
        drawn_offset_y = doubled_offset_y * self.hitbox_scale // 2
        if self.hitbox_flip_x and horizontal_edge is not None:
            # Mirrored with the image. Each frame flips within its own width, so mirror the
            # anchored point against one common axis (the widest frame): frames narrower than
            # it are moved right by the difference, which is exact for differing widths
            widest_frame_width = max(
                (other.rect.width for frames in self._animations.values() for other in frames),
                default=frame.rect.width,
            )
            drawn_offset_x = -drawn_offset_x + (widest_frame_width - frame.rect.width) * (
                self.hitbox_scale
            )
        return (drawn_offset_x, drawn_offset_y)

    @property
    def draw_offset(self: Self) -> tuple[int, int]:
        """Where the current frame is drawn relative to its authored (top-left) position.

        With a frame_anchor other than NONE, each frame is moved so the anchor point of its
        hitbox (see FrameAnchor) lands on the same point of the reference hitbox, in drawn
        pixels (times hitbox_scale; computed in authored space and, when hitbox_flip_x,
        mirrored with the image about the widest frame's width, so frames of differing widths
        stay exact). The engine adds it when placing a world-space sprite's rect
        (glitchygames.world.screen_position_for); a screen-space game adds it itself. hitbox
        includes it, so collisions match the drawing. NONE (the default) is (0, 0).

        Returns:
            tuple[int, int]: (x, y) offset in drawn pixels.

        """
        current_frame = self.get_current_frame()
        if current_frame is None:
            return (0, 0)
        return self._frame_draw_offset(current_frame)

    @staticmethod
    def _parse_frame_anchor(frame_anchor_name: str | None) -> FrameAnchor:
        """Parse the optional [sprite] frame_anchor TOML value.

        Returns:
            FrameAnchor: The anchor; NONE when the key is absent.

        Raises:
            ValueError: If the value names no FrameAnchor.

        """
        if frame_anchor_name is None:
            return FrameAnchor.NONE
        try:
            return FrameAnchor(frame_anchor_name)
        except ValueError:
            valid_names = ', '.join(repr(anchor.value) for anchor in FrameAnchor)
            msg = f'[sprite] frame_anchor must be one of {valid_names}, got {frame_anchor_name!r}'
            raise ValueError(msg) from None

    def common_hitbox_x_range(self: Self) -> tuple[int, int]:
        """Return the horizontal hitbox span shared by every animation frame.

        The intersection of all frames' hitbox x-ranges (drawn pixels, after hitbox_scale and
        hitbox_flip_x), relative to the sprite's position. Unlike ``hitbox`` it does not
        change from frame to frame, so games use it for support (standing on ledges and wall
        tops): a wider falling frame then cannot catch a player that just walked off an edge
        with a narrower idle frame, which would make it land, fall and land again forever.

        Returns:
            tuple[int, int]: (left, right) offsets; right is exclusive. Without frames, or if
            the frames share no column, the current hitbox's x-range.

        """
        common_left: int | None = None
        common_right: int | None = None
        for frames in self._animations.values():
            for frame in frames:
                frame_hitbox = self._drawn_hitbox(
                    self._native_frame_hitbox(frame), native_frame_width=frame.rect.width
                )
                frame_hitbox.move_ip(self._frame_draw_offset(frame))
                common_left = (
                    frame_hitbox.left
                    if common_left is None
                    else max(common_left, frame_hitbox.left)
                )
                common_right = (
                    frame_hitbox.right
                    if common_right is None
                    else min(common_right, frame_hitbox.right)
                )
        if common_left is None or common_right is None or common_left >= common_right:
            current_hitbox = self.hitbox
            return (current_hitbox.left, current_hitbox.right)
        return (common_left, common_right)

    def _native_frame_hitbox(self: Self, frame: SpriteFrame) -> pygame.Rect:
        """Return a frame's hitbox in native, unflipped pixels (resolution order of hitbox).

        The visible-pixel fallback is measured on the unflipped frame image; hitbox_flip_x
        mirrors it (and the TOML hitboxes) afterwards in _drawn_hitbox.

        Returns:
            pygame.Rect: The native hitbox (may be the frame's or the sprite's own rect).

        """
        if frame.has_explicit_hitbox:
            return frame.hitbox
        if self._default_hitbox is not None:
            return self._default_hitbox
        if trims_transparent_hitbox(self):
            return frame.opaque_bounds()
        return frame.rect

    def _drawn_hitbox(
        self: Self, native_hitbox: pygame.Rect, *, native_frame_width: int
    ) -> pygame.Rect:
        """Return a new rect: a native hitbox scaled by hitbox_scale, mirrored if flipped.

        Args:
            native_hitbox: The hitbox in native frame pixels.
            native_frame_width: The frame's width in native pixels (the mirror span).

        Returns:
            pygame.Rect: The hitbox in drawn pixels (never the caller's rect object).

        """
        drawn_x = native_hitbox.x * self.hitbox_scale
        drawn_width = native_hitbox.width * self.hitbox_scale
        if self.hitbox_flip_x:
            drawn_x = native_frame_width * self.hitbox_scale - (drawn_x + drawn_width)
        return pygame.Rect(
            drawn_x,
            native_hitbox.y * self.hitbox_scale,
            drawn_width,
            native_hitbox.height * self.hitbox_scale,
        )

    def get_hitbox_world_rect(
        self: Self,
        world_x: float,
        world_y: float,
    ) -> pygame.Rect:
        """Return the hitbox positioned in world coordinates.

        Args:
            world_x: The sprite's world X position.
            world_y: The sprite's world Y position.

        Returns:
            A pygame.Rect with the hitbox offset applied to the world position.
        """
        current_hitbox = self.hitbox
        return pygame.Rect(
            round(world_x) + current_hitbox.x,
            round(world_y) + current_hitbox.y,
            current_hitbox.width,
            current_hitbox.height,
        )

    def __init__(
        self: Self,
        filename: str | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize the Sprite Animation prototype."""
        super().__init__()

        # Initialize pygame.sprite.DirtySprite
        if groups is None:
            groups = pygame.sprite.LayeredDirty()
        pygame.sprite.DirtySprite.__init__(self, groups)

        # Animation state
        self.name = 'animated_sprite'  # Default name
        self.description = ''  # Description field for metadata
        self._animations: dict[str, list[SpriteFrame]] = {}
        # Each animation's [[animation]] frame_interval and loop as loaded, so a save writes
        # them back (frames without a per-frame override use the animation's frame_interval).
        # set_animation applies the animation's loop flag to is_looping; the animation state
        # machine reads _loop_flags too
        self._animation_frame_intervals: dict[str, float] = {}
        self._loop_flags: dict[str, bool] = {}
        # The [[transition]] tables as loaded (keys and values verbatim, in file order), so a
        # save writes the animation state machine back; transitions games add in code are not
        # part of it
        self.transition_data: list[dict[str, Any]] = []
        self._is_playing: bool = False
        self._is_looping: bool = False
        self._frame_timer: float = 0.0
        self._color_map: dict[str, tuple[int, ...]] = {}
        # The animations' order as loaded from a file; None for a sprite never loaded, whose
        # animation_order is its animations' insertion order
        self._animation_order: list[str] | None = None
        # The color glyphs in their file order, so a save keeps the file's layout; None for a
        # sprite never loaded (a save then orders them itself)
        self._color_order: list[str] | None = None
        # The glyphs whose colors had per-pixel alpha (0-254) in the loaded file, and that alpha
        self._colors_with_per_pixel_alpha: dict[str, int] = {}

        # Initialize frame manager as the single source of truth
        self.frame_manager = FrameManager(self)

        # Dirty sprite properties
        self.dirty = 1  # Start dirty to ensure initial render
        # The (animation, frame index) the image was last drawn from; None forces a redraw.
        # Both parts matter: an animation change resets the frame index to 0, so comparing
        # the index alone would keep the old animation's frame 0 image
        self._last_drawn_frame: tuple[str, int] | None = None
        self._surface_cache: dict[str, pygame.Surface] = {}

        # Initialize with default surface
        self._gg_image = pygame.Surface((32, 32))
        self._gg_rect = pygame.Rect(0, 0, 32, 32)

        # Sprite-level default hitbox (loaded from [sprite.hitbox] in TOML)
        self._default_hitbox: pygame.Rect | None = None

        # Multiplier from native TOML pixels to drawn pixels for hitboxes (see hitbox);
        # games that draw this sprite scaled up set it to their scale factor
        self.hitbox_scale: int = 1
        # True while the game draws this sprite mirrored horizontally (see hitbox)
        self.hitbox_flip_x: bool = False
        # How frames of different shapes line up when drawn (see draw_offset); NONE draws
        # each frame as authored. When set, rect must include draw_offset: the engine adds it
        # for world sprites, a game placing rect itself must (see FrameAnchor's contract)
        self.frame_anchor: FrameAnchor = FrameAnchor.NONE
        # (frames it was built from, union of their hitboxes); see _frame_anchor_reference
        self._frame_anchor_reference_cache: (
            tuple[tuple[SpriteFrame, ...], pygame.Rect | None] | None
        ) = None

        if filename:
            self.load(filename)

    def __getitem__(self: Self, animation_name: str) -> SpriteFrame | None:
        """Return the current frame of the specified animation.

        Returns:
            SpriteFrame | None: The item at the given index.

        """
        return self._animations.get(animation_name, [None])[self.frame_manager.current_frame]

    def get_current_frame(self: Self) -> SpriteFrame | None:
        """Return the current frame as a "SpriteFrame".

        Returns:
            SpriteFrame | None: The current frame.

        """
        return self.frame_manager.get_frame_data()

    # Sprite properties - return current frame's surface information
    def _get_current_surface(self: Self) -> pygame.Surface:
        """Get the current frame's surface with caching.

        Returns:
            pygame.Surface: The current surface.

        """
        frame = self.get_current_frame()
        if not frame:
            # Use cached default surface if available
            cache_key = 'default_surface'
            if cache_key in self._surface_cache:
                return self._surface_cache[cache_key]

            # Create and cache default surface
            surface = pygame.Surface((32, 32))
            self._surface_cache[cache_key] = surface
            return surface

        # Use cached surface if available
        cache_key = f'{self.frame_manager.current_animation}_{self.frame_manager.current_frame}'
        if cache_key in self._surface_cache:
            return self._surface_cache[cache_key]

        # Create and cache surface if not available
        surface = self._create_optimized_surface(frame)
        self._surface_cache[cache_key] = surface
        return surface

    @staticmethod
    def _create_optimized_surface(frame: SpriteFrame) -> pygame.Surface:
        """Create the sprite image for a frame (cached per frame by _get_current_surface).

        A frame with a pixels list (every TOML frame) is drawn from its pixels, which may be
        ahead of the frame's image while Bitmappy edits it (see SpriteFrame._image_stale), in
        a format that draws its transparency (see _create_surface_from_toml_pixels). A frame
        without pixels (built in code) is drawn as a copy of its own image.

        Returns:
            pygame.Surface: The result.

        """
        if hasattr(frame, 'pixels') and frame.pixels:
            width, height = frame.image.get_size()
            return AnimatedSprite._create_surface_from_toml_pixels(width, height, frame.pixels)

        # Fallback to frame's existing surface
        return frame.image.copy()

    # Animation state properties (read-only)
    @property
    @override
    def current_animation(self: Self) -> str:
        """The current animation name."""
        return self.frame_manager.current_animation

    @property
    @override
    def current_frame(self: Self) -> int:
        """The current frame index."""
        return self.frame_manager.current_frame

    @property
    @override
    def is_playing(self: Self) -> bool:
        """Whether animation is currently playing."""
        return self._is_playing

    @property
    @override
    def is_looping(self: Self) -> bool:
        """Whether current animation loops."""
        return self._is_looping

    @property
    @override
    def frames(self: Self) -> dict[str, list[SpriteFrame]]:
        """All frames for all animations."""
        return self._animations.copy()

    @property
    @override
    def animations(self: Self) -> dict[str, list[SpriteFrame]]:
        """Animation frames for all animations."""
        return self._animations.copy()

    @property
    def animation_data(self: Self) -> dict[str, list[SpriteFrame]]:
        """Direct access to animation frame data for internal components like FrameManager."""
        return self._animations

    @animation_data.setter
    def animation_data(self: Self, value: dict[str, list[SpriteFrame]]) -> None:
        """Set animation frame data directly."""
        self._animations = value

    @property
    def animation_order(self: Self) -> list[str]:
        """The order of animations as loaded from file."""
        if self._animation_order is None:
            return list(self._animations.keys())
        return self._animation_order

    @property
    def has_own_animation_order(self: Self) -> bool:
        """Whether the sprite keeps an animation order of its own (a loaded file's, or one set).

        False for a sprite never loaded, whose animation_order is its animations' order.
        """
        return self._animation_order is not None

    @property
    @override
    def frame_interval(self: Self) -> float:
        """The frame interval for the current animation."""
        if not self.frame_manager.current_animation:
            return 0.5  # Default frame interval

        frames = self._animations.get(self.frame_manager.current_animation, [])
        if not frames or self.frame_manager.current_frame >= len(frames):
            return 0.5  # Default frame interval

        frame = frames[self.frame_manager.current_frame]
        return frame.duration if frame else 0.5  # Default frame interval

    @property
    @override
    def loop(self: Self) -> bool:
        """Whether the current animation loops."""
        return self._is_looping

    # Animation metadata properties (read-only)
    @property
    def animation_count(self: Self) -> int:
        """The number of animations."""
        return len(self._animations)

    @property
    def current_animation_frame_count(self: Self) -> int:
        """The number of frames in the current animation."""
        if not self.frame_manager.current_animation:
            return 0
        return len(self._animations.get(self.frame_manager.current_animation, []))

    @property
    def current_animation_total_duration(self: Self) -> float:
        """The total duration of the current animation."""
        if not self.frame_manager.current_animation:
            return 0.0
        frames = self._animations.get(self.frame_manager.current_animation, [])
        return sum(f.duration for f in frames)

    @property
    def animation_names(self: Self) -> list[str]:
        """List of animation names."""
        return list(self._animations.keys())

    # Animation metadata properties (read/write)
    @is_looping.setter
    def is_looping(self: Self, value: bool) -> None:
        """Set whether animations loop."""
        self._is_looping = value

    @property
    def frame_count(self: Self) -> int:
        """The number of frames in the current animation."""
        return self.frame_manager.get_frame_count()

    @property
    def next_animation(self: Self) -> str:
        """The next animation in the sequence."""
        if not self._animations:
            return ''
        animation_names = list(self._animations.keys())
        current_index = (
            animation_names.index(self.frame_manager.current_animation)
            if self.frame_manager.current_animation in animation_names
            else -1
        )
        next_index = (current_index + 1) % len(animation_names)
        return animation_names[next_index]

    # Animation control methods
    @override
    def play(self: Self, animation_name: str | None = None) -> None:
        """Start playing the specified animation (or current if None)."""
        if animation_name:
            self.set_animation(animation_name)
        self._is_playing = True
        self._frame_timer = 0.0

    def play_animation(self: Self, animation_name: str | None = None) -> None:
        """Alias for play method for backwards compatibility."""
        self.play(animation_name)

    @override
    def pause(self: Self) -> None:
        """Pause the current animation."""
        self._is_playing = False

    @override
    def stop(self: Self) -> None:
        """Stop the current animation and reset to frame 0."""
        self._is_playing = False
        self.frame_manager.current_frame = 0
        self._frame_timer = 0.0

    @override
    def set_frame(self: Self, frame_index: int) -> None:
        """Set the current frame index.

        Raises:
            ValueError: If no animation is currently set.
            IndexError: If the frame index is out of range.

        """
        if not self.frame_manager.current_animation:
            raise ValueError(ERR_NO_ANIMATION_SET)

        if not self.frame_manager.set_frame(frame_index):
            frames = self._animations.get(self.frame_manager.current_animation, [])
            raise IndexError(
                ERR_FRAME_INDEX_OUT_OF_RANGE_WITH_BOUNDS.format(
                    frame_index,
                    self.frame_manager.current_animation,
                    len(frames) - 1,
                ),
            )

        self._frame_timer = 0.0
        self._update_surface_and_mark_dirty()

    @override
    def set_animation(self: Self, animation_name: str) -> None:
        """Set the current animation.

        Raises:
            ValueError: If the animation name is not found.

        """
        if animation_name not in self._animations:
            available = list(self._animations.keys())
            raise ValueError(
                ERR_ANIMATION_NOT_FOUND_AVAILABLE.format(animation_name, available),
            )

        # The name was validated above (the frame manager validates against the same
        # animations), so set it directly
        self.frame_manager.current_animation = animation_name

        self._apply_animation_loop_flag(animation_name)
        self._frame_timer = 0.0
        self._update_surface_and_mark_dirty()

    # Animation data methods
    @override
    def add_animation(
        self: Self,
        name: str,
        frames: list[SpriteFrame],
        metadata: dict[str, object] | None = None,
    ) -> None:
        """Add a new animation."""
        self._animations[name] = frames.copy()
        if not self.frame_manager.current_animation:
            self.frame_manager.current_animation = name

    @override
    def remove_animation(self: Self, name: str) -> None:
        """Remove an animation and the transitions from or to it."""
        if name in self._animations:
            del self._animations[name]
            self.remove_transitions_for_animation(name)
            self.forget_animation_settings(name)
            if self.frame_manager.current_animation == name:
                # Switch to first available animation
                if self._animations:
                    self.frame_manager.current_animation = next(iter(self._animations.keys()))
                    self.frame_manager.current_frame = 0
                else:
                    self.frame_manager.current_animation = ''
                    self.frame_manager.current_frame = 0

    def rename_animation(self: Self, *, old_name: str, new_name: str) -> None:
        """Rename an animation and move everything stored under its name.

        The frames keep their place in the animation order; the animation's loop flag and
        frame interval, the transitions from or to it and, when it is the current animation,
        the frame manager's current animation (keeping the current frame) follow the new
        name. Cached surfaces for either name are dropped.

        Args:
            old_name (str): The animation's current name.
            new_name (str): The name to give it.

        Raises:
            ValueError: If old_name is not an animation, or new_name already is one.

        """
        if old_name not in self._animations:
            raise ValueError(ERR_ANIMATION_NOT_FOUND.format(old_name))
        if new_name != old_name and new_name in self._animations:
            raise ValueError(ERR_ANIMATION_NAME_EXISTS.format(new_name))

        self._animations = {
            (new_name if name == old_name else name): frames
            for name, frames in self._animations.items()
        }
        if self._animation_order is not None:
            self._animation_order = [
                (new_name if name == old_name else name) for name in self._animation_order
            ]
        if old_name in self._loop_flags:
            self._loop_flags[new_name] = self._loop_flags.pop(old_name)
        if old_name in self._animation_frame_intervals:
            self._animation_frame_intervals[new_name] = self._animation_frame_intervals.pop(
                old_name
            )
        self.rename_animation_in_transitions(old_name=old_name, new_name=new_name)

        # Surfaces are cached as '<animation>_<frame>'; a stale entry for new_name would
        # show another animation's frame. The prefix can also match another animation whose
        # name starts with '<name>_'; dropping its entries only costs a re-render
        for cache_key in list(self._surface_cache):
            if cache_key.startswith((f'{old_name}_', f'{new_name}_')):
                del self._surface_cache[cache_key]

        if self.frame_manager.current_animation == old_name:
            current_frame = self.frame_manager.current_frame
            # Setting the animation resets the frame to 0, so restore it afterwards
            self.frame_manager.current_animation = new_name
            self.frame_manager.current_frame = current_frame

    def rename_animation_in_transitions(self: Self, *, old_name: str, new_name: str) -> None:
        """Rename an animation in transition_data, wherever it is a transition's from or to."""
        for transition in self.transition_data:
            for end_key in ('from', 'to'):
                if transition.get(end_key) == old_name:
                    transition[end_key] = new_name

    def remove_transitions_for_animation(self: Self, animation_name: str) -> None:
        """Drop the transitions from or to a deleted animation, logging a warning for each."""
        kept_transitions: list[dict[str, Any]] = []
        for transition in self.transition_data:
            if animation_name in {transition.get('from'), transition.get('to')}:
                self.log.warning(
                    "Dropping transition %s: animation '%s' was removed", transition, animation_name
                )
            else:
                kept_transitions.append(transition)
        self.transition_data = kept_transitions

    def transitions_for_animation(
        self: Self, animation_name: str
    ) -> list[tuple[int, dict[str, Any]]]:
        """Return a copy of each transition from or to an animation, with its index.

        Bitmappy captures them before deleting the animation so an undo can put them back with
        restore_transitions.

        Args:
            animation_name (str): The animation's name.

        Returns:
            list[tuple[int, dict[str, Any]]]: (index in transition_data, transition copy) pairs,
            in transition order.

        """
        return [
            (index, dict(transition))
            for index, transition in enumerate(self.transition_data)
            if animation_name in {transition.get('from'), transition.get('to')}
        ]

    def restore_transitions(
        self: Self, indexed_transitions: list[tuple[int, dict[str, Any]]]
    ) -> None:
        """Put transitions back at the indices transitions_for_animation reported.

        Inserting in ascending index order rebuilds the original order, provided transition_data
        is otherwise as it was when they were removed.

        Args:
            indexed_transitions (list[tuple[int, dict[str, Any]]]): (index, transition) pairs.

        """
        for index, transition in sorted(indexed_transitions, key=operator.itemgetter(0)):
            self.transition_data.insert(index, dict(transition))

    def forget_animation_settings(self: Self, animation_name: str) -> None:
        """Drop a removed animation's loop flag, frame interval and place in the order.

        Otherwise a later animation given the same name would inherit them, and animation_order
        would still list it.

        Args:
            animation_name (str): The removed animation's name.

        """
        self._loop_flags.pop(animation_name, None)
        self._animation_frame_intervals.pop(animation_name, None)
        if self._animation_order is not None:
            self._animation_order = [
                name for name in self._animation_order if name != animation_name
            ]

    def restore_animation_settings(
        self: Self,
        animation_name: str,
        *,
        position: int,
        loop_flag: bool | None,
        frame_interval: float | None,
    ) -> None:
        """Put a restored animation back in its place, with its loop flag and frame interval.

        The animation's frames must already be in the sprite (Bitmappy's undo re-adds them).

        Args:
            animation_name (str): The restored animation's name.
            position (int): Its index in the animation order before it was removed.
            loop_flag (bool | None): Its loop flag, or None if it had none.
            frame_interval (float | None): Its frame interval, or None if it had none.

        """
        frames = self._animations.pop(animation_name)
        names = list(self._animations)
        names.insert(position, animation_name)
        self._animations = {
            name: (frames if name == animation_name else self._animations[name]) for name in names
        }
        if self._animation_order is not None:
            order = [name for name in self._animation_order if name != animation_name]
            order.insert(position, animation_name)
            self._animation_order = order
        if loop_flag is not None:
            self._loop_flags[animation_name] = loop_flag
        if frame_interval is not None:
            self._animation_frame_intervals[animation_name] = frame_interval

    def copy_transitions_from(self: Self, source: AnimatedSprite) -> None:
        """Copy another sprite's transition_data (Bitmappy builds derived sprites to save).

        Args:
            source (AnimatedSprite): The sprite whose transitions to copy.

        """
        self.transition_data = [dict(transition) for transition in source.transition_data]

    def copy_sprite_metadata_from(self: Self, source: AnimatedSprite) -> None:
        """Copy every sprite-level field the TOML writers save from another sprite.

        name, description, frame_anchor, the sprite-level default hitbox, the transitions,
        and the loaded color glyphs and their order (so a save reuses the source file's
        characters). Bitmappy uses it when it builds a new sprite to save from a loaded one.

        Args:
            source (AnimatedSprite): The sprite whose metadata to copy.

        """
        self.name = source.name
        self.description = source.description
        self.frame_anchor = source.frame_anchor
        self.default_hitbox = (
            None if source.default_hitbox is None else source.default_hitbox.copy()
        )
        self.copy_transitions_from(source)
        self._color_map = dict(source._color_map)
        # A source never loaded has no color order: the copy gets an empty one
        self._color_order = list(source._color_order) if source._color_order is not None else []
        self._colors_with_per_pixel_alpha = dict(source._colors_with_per_pixel_alpha)

    @override
    def get_frame(self: Self, animation_name: str, frame_index: int) -> SpriteFrame:
        """Get a specific frame from a specific animation.

        Returns:
            'SpriteFrame': The frame.

        Raises:
            ValueError: If the animation name is not found.
            IndexError: If the frame index is out of range.

        """
        if animation_name not in self._animations:
            raise ValueError(ERR_ANIMATION_NOT_FOUND.format(animation_name))
        frames = self._animations[animation_name]
        if not 0 <= frame_index < len(frames):
            raise IndexError(
                ERR_FRAME_INDEX_OUT_OF_RANGE.format(frame_index, animation_name),
            )
        return frames[frame_index]

    def add_frame(self: Self, animation_name: str, frame: SpriteFrame, index: int = -1) -> None:
        """Add a frame to an animation."""
        if animation_name not in self._animations:
            self._animations[animation_name] = []

        frames = self._animations[animation_name]

        # Check if this animation had only 1 frame before adding the new frame
        # If so, we should start the animation since it now has multiple frames
        was_single_frame = len(frames) == 1

        if index == -1:
            frames.append(frame)
        else:
            frames.insert(index, frame)

        # If this was a single-frame animation and we just added a second frame,
        # start the animation to make it play
        multi_frame_threshold = 2
        if was_single_frame and len(frames) == multi_frame_threshold:
            self.log.info("Animation '%s' now has 2 frames, starting animation", animation_name)
            self._is_playing = True
            self._is_looping = True  # Enable looping for multi-frame animations

        # Update surface if this is the current animation
        if self.frame_manager.current_animation == animation_name:
            self._update_surface_and_mark_dirty()

    def remove_frame(self: Self, animation_name: str, frame_index: int) -> None:
        """Remove a frame from an animation.

        Raises:
            ValueError: If the animation name is not found.
            IndexError: If the frame index is out of range.

        """
        if animation_name not in self._animations:
            raise ValueError(ERR_ANIMATION_NOT_FOUND.format(animation_name))

        frames = self._animations[animation_name]
        if not 0 <= frame_index < len(frames):
            raise IndexError(
                ERR_FRAME_INDEX_OUT_OF_RANGE.format(frame_index, animation_name),
            )

        frames.pop(frame_index)

        # Adjust current frame if needed
        if (
            self.frame_manager.current_animation == animation_name
            and self.frame_manager.current_frame >= len(frames)
        ):
            self.frame_manager.current_frame = max(0, len(frames) - 1)
            self._update_surface_and_mark_dirty()

    def get_animation_metadata(self: Self, animation_name: str) -> dict[str, object]:
        """Get metadata for a specific animation.

        Returns:
            dict: The animation metadata.

        Raises:
            ValueError: If the animation name is not found.

        """
        if animation_name not in self._animations:
            raise ValueError(ERR_ANIMATION_NOT_FOUND.format(animation_name))

        frames = self._animations[animation_name]
        return {
            'frame_count': len(frames),
            'total_duration': sum(f.duration for f in frames),
            # The animation's own loop flag; the runtime flag for one without a loaded flag
            'is_looping': self._loop_flags.get(animation_name, self._is_looping),
        }

    def set_animation_metadata(
        self: Self,
        animation_name: str,
        metadata: dict[str, object],
    ) -> None:
        """Set metadata for a specific animation.

        Raises:
            ValueError: If the animation name is not found.

        """
        if animation_name not in self._animations:
            raise ValueError(ERR_ANIMATION_NOT_FOUND.format(animation_name))

        # Update this animation's loop flag (and is_looping if it is the current animation)
        if 'is_looping' in metadata:
            self._loop_flags[animation_name] = bool(metadata['is_looping'])
            if self.frame_manager.current_animation == animation_name:
                self._apply_animation_loop_flag(animation_name)

    # File I/O methods
    @override
    def load(self: Self, filename: str) -> None:
        """Load animated sprite from a file.

        Currently only supports TOML format. To add new formats:
        1. Add format detection in _detect_file_format()
        2. Add load logic here (e.g., _load_json(), _load_xml())
        3. Add save methods in save()
        4. Update tests
        See LOADER_README.md for detailed implementation guide.

        Raises:
            ValueError: If the file format is not supported.

        """
        file_format = detect_file_format(filename)

        if file_format == 'toml':
            self._load_toml(filename)
        else:
            raise ValueError(ERR_UNSUPPORTED_FORMAT.format(file_format))

    def _apply_animation_loop_flag(self: Self, animation_name: str) -> None:
        """Make is_looping follow the animation's own [[animation]] loop flag, when it has one.

        Animations without a loaded flag (built in code or in Bitmappy) leave is_looping as
        it is. Setting is_looping afterwards still overrides it until the next animation is set.
        """
        loop_flag = self._loop_flags.get(animation_name)
        if loop_flag is not None:
            self._is_looping = loop_flag

    def _set_initial_animation(self: Self) -> None:
        """Set the initial animation and frame."""
        if self._animations:
            # Use the first animation as it appears in the file
            initial_animation = (
                self._animation_order[0]
                if self._animation_order
                else next(iter(self._animations.keys()))
            )
            self.frame_manager.current_animation = initial_animation
            self._apply_animation_loop_flag(initial_animation)
            self.log.debug(
                "Set initial animation to first animation in file: '%s' with %s frames",
                initial_animation,
                len(self._animations[initial_animation]),
            )
            self.frame_manager.current_frame = 0
        else:
            self.frame_manager.current_animation = ''
            self.frame_manager.current_frame = 0
            self.log.debug('No animations available, set to empty')

    def _load_toml(self: Self, filename: str) -> None:
        """Load animated sprite from TOML file.

        Raises:
            FileNotFoundError: If the sprite file does not exist.
            ValueError: If the TOML file cannot be parsed or loaded.

        """
        try:
            with Path(filename).open('rb') as f:
                data = tomllib.load(f)
        except FileNotFoundError as e:
            raise FileNotFoundError(ERR_SPRITE_FILE_NOT_FOUND.format(filename)) from e
        except Exception as e:
            raise ValueError(ERR_TOML_LOAD_FAILED.format(filename, e)) from e

        self.name = data.get('sprite', {}).get('name', 'animated_sprite')
        self.description = data.get('sprite', {}).get('description', '')

        # Parse sprite-level default hitbox from [sprite.hitbox]
        self._default_hitbox = AnimatedSprite._parse_hitbox_data(
            data.get('sprite', {}).get('hitbox'),
        )
        # Optional [sprite] frame_anchor = "none", "bottom", "top_left", ... (FrameAnchor values)
        self.frame_anchor = AnimatedSprite._parse_frame_anchor(
            data.get('sprite', {}).get('frame_anchor')
        )

        self._animations = {}
        self._animation_order = []
        self._animation_frame_intervals = {}
        self._loop_flags = {}
        self.transition_data = [dict(transition) for transition in data.get('transition', [])]

        color_map, color_order, colors_with_per_pixel_alpha = self.build_color_map(data)
        self._color_map = color_map  # Store color map for later use
        self._color_order = color_order  # Store color order for preserving file format
        # Store which colors originally had alpha=0-254 (per-pixel
        # alpha) vs alpha=255 or no alpha (indexed)
        self._colors_with_per_pixel_alpha = colors_with_per_pixel_alpha
        animations = data.get('animation', [])

        self.log.debug('Found %s animation(s) in TOML file', len(animations))

        # Check if this is a static sprite (has sprite.pixels but no animations)
        if not animations and 'sprite' in data and 'pixels' in data['sprite']:
            self.log.debug('Detected static sprite, converting to single-frame animation')
            self._animation_order.append(self._convert_static_sprite(data, color_map))
        else:
            # Process normal animated sprite
            for anim_data in animations:
                anim_name = anim_data.get('namespace', 'default')
                frames = self._process_toml_animation(anim_data, color_map)
                if frames:
                    self._animations[anim_name] = frames
                    self._animation_order.append(anim_name)  # Track order

        # Auto-create animation state machine if [[transition]] sections exist
        self.state_machine: AnimationStateMachine | None = None
        transitions = data.get('transition', [])
        if transitions:
            self.state_machine = AnimationStateMachine(self)
            self.state_machine.load_from_toml(transitions)

        # Log if no animations found
        if not animations and not self._animations:
            self.log.info('NO ANIMATIONS FOUND IN FILE')

        self._set_initial_animation()
        self._log_toml_load_results()

        # Initialize the sprite surface with the first frame
        if (
            self.frame_manager.current_animation
            and self.frame_manager.current_animation in self._animations
        ):
            self.log.debug(
                "INITIAL FRAME STATE: animation='%s', frame=%s",
                self.frame_manager.current_animation,
                self.frame_manager.current_frame,
            )
            # Force initial surface update by resetting frame tracking
            self._last_drawn_frame = None  # Force update regardless of previous state
            self._update_surface_and_mark_dirty()

    def _convert_static_sprite(
        self: Self,
        data: dict[str, Any],
        color_map: dict[str, tuple[int, ...]],
    ) -> str:
        """Convert a static sprite to a single-frame animation.

        Returns:
            str: The animation's name (the caller adds it to the animation order).

        """
        sprite_data = data['sprite']
        pixels = sprite_data['pixels']

        # Parse pixel rows
        pixel_rows = pixels.strip().split('\n')
        height = len(pixel_rows)

        # Calculate maximum width across all rows to handle inconsistent widths
        row_widths = [len(row) for row in pixel_rows]
        width = max(row_widths) if row_widths else 0

        # Check for inconsistent row widths and pad if needed
        if len(set(row_widths)) > 1:
            self.log.warning(
                'Inconsistent row widths detected in static sprite: '
                'min=%s, max=%s. '
                'Padding shorter rows to %s characters.',
                min(row_widths),
                max(row_widths),
                width,
            )
            # Pad shorter rows with first character (usually transparency)
            # Find the most common character to use as padding (likely transparency)
            from collections import Counter

            all_chars = ''.join(pixel_rows)
            char_counts = Counter(all_chars)
            pad_char = char_counts.most_common(1)[0][0] if char_counts else ' '

            # Pad rows to consistent width
            pixel_rows = [row.ljust(width, pad_char) for row in pixel_rows]
            self.log.debug("Using '%s' as padding character", pad_char)

        # Create a surface from the pixel data
        surface = pygame.Surface((width, height))
        surface.convert()

        # Convert character pixels to actual colors
        for y, row in enumerate(pixel_rows):
            for x, char in enumerate(row):
                if char in color_map:
                    surface.set_at((x, y), color_map[char])
                else:
                    # Default to magenta for unknown characters
                    surface.set_at((x, y), (255, 0, 255))

        # Parse hitbox for static sprite from [sprite.hitbox]
        static_hitbox = AnimatedSprite._parse_hitbox_data(sprite_data.get('hitbox'))

        # Create a single frame from the surface
        frame = SpriteFrame(surface, hitbox=static_hitbox)
        frame.pixels = []

        # Build raw pixel data from the character grid using the color map
        raw_pixels: list[tuple[int, ...]] = []
        for y in range(height):
            for x in range(width):
                char = pixel_rows[y][x]
                if char in color_map:
                    raw_pixels.append(color_map[char])
                else:
                    # Default to magenta for unknown characters
                    raw_pixels.append((255, 0, 255))

        # Normalize pixel format to prevent mixed RGB/RGBA tuples.
        # If the TOML defines any colors with per-pixel alpha (alpha 0-254),
        # normalize all pixels to RGBA. Otherwise keep RGB (indexed color mode).
        if any(len(color) == RGBA_COMPONENT_COUNT for color in color_map.values()):
            frame.pixels = convert_pixels_to_rgba_if_needed(raw_pixels)
        else:
            frame.pixels = convert_pixels_to_rgb_if_possible(raw_pixels)

        # Create a single animation with one frame
        animation_name = sprite_data.get('name', 'idle')
        self._animations[animation_name] = [frame]

        self.log.debug(
            "Converted static sprite to single-frame animation '%s' (%sx%s)",
            animation_name,
            width,
            height,
        )
        return animation_name

    @staticmethod
    def build_color_map(
        data: dict[str, Any],
    ) -> tuple[dict[str, tuple[int, ...]], list[str], dict[str, int]]:
        """Build color map from TOML colors section.

        Returns:
            tuple: (color_map dict, color_order list, original_alpha_values dict) -
                   color_map maps char->color,
                   color_order preserves the order colors appeared in the file,
                   original_alpha_values maps char->alpha_value for
                   colors that had alpha=0-254 (per-pixel)

        """
        color_map: dict[str, tuple[int, ...]] = {}
        color_order: list[str] = []  # Preserve order of colors as they appear in file
        # Track original alpha values for colors with alpha=0-254
        original_alpha_values: dict[str, int] = {}
        colors_section: dict[str, Any] = data.get('colors', {})
        for char, color_data in colors_section.items():
            r = color_data.get('red', 0)
            g = color_data.get('green', 0)
            b = color_data.get('blue', 0)

            # Check if 'alpha' was explicitly in the original file
            if 'alpha' in color_data:
                a = color_data['alpha']
                if 0 <= a <= MAX_PER_PIXEL_ALPHA:
                    # Has per-pixel alpha (0-254) - store the original value for preservation
                    color_map[char] = (r, g, b, a)
                    original_alpha_values[char] = a
                else:
                    # Had alpha=255 explicitly - treat as indexed (RGBA with alpha=255)
                    color_map[char] = (r, g, b, 255)
            else:
                # No alpha field in original - use RGB (indexed color)
                color_map[char] = (r, g, b)
            color_order.append(char)  # Preserve order
        return color_map, color_order, original_alpha_values

    def _process_toml_animation(
        self: Self,
        anim_data: dict[str, Any],
        color_map: dict[str, tuple[int, ...]],
    ) -> list[SpriteFrame]:
        """Process a single animation from TOML data.

        Returns:
            list: The result.

        """
        anim_name = anim_data.get('namespace', 'default')
        frames_data = anim_data.get('frame', [])

        # Loop property from TOML data (applied when the animation is set, see set_animation)
        loop_setting = anim_data.get('loop', True)

        # Set frame interval from TOML data
        frame_interval = anim_data.get('frame_interval', 0.5)
        self._frame_interval = frame_interval

        # Remember both per animation so save() writes them back
        self._animation_frame_intervals[anim_name] = frame_interval
        self._loop_flags[anim_name] = loop_setting

        self.log.debug("Processing animation '%s' with %s frame(s)", anim_name, len(frames_data))
        self._log_animation_metadata(anim_data, anim_name)

        frames: list[SpriteFrame] = []
        for frame_idx, frame_data in enumerate(frames_data):
            frame = self._create_toml_frame(frame_data, frame_idx, color_map, frame_interval)
            if frame:
                frames.append(frame)

        if frames:
            frames.sort(key=lambda f: getattr(f, 'frame_index', 0))
            self.log.debug("Animation '%s' loaded with %s frame(s)", anim_name, len(frames))
        else:
            self.log.debug("Animation '%s' has no valid frames", anim_name)

        return frames

    def _log_animation_metadata(self: Self, anim_data: dict[str, Any], anim_name: str) -> None:
        """Log animation metadata for debugging."""
        self.log.debug("  Animation '%s' metadata:", anim_name)
        for key, value in anim_data.items():
            if key != 'frame':  # Don't show the frame array
                self.log.debug('    %s: %s', key, value)

    def _create_toml_frame(
        self: Self,
        frame_data: dict[str, Any],
        frame_idx: int,
        color_map: dict[str, tuple[int, ...]],
        frame_interval: float = 0.5,
    ) -> SpriteFrame | None:
        """Create a SpriteFrame from TOML frame data.

        Returns:
            SpriteFrame: The result.

        """
        frame_index = frame_data.get('frame_index', frame_idx)
        self.log.debug('  Processing frame %s (data index %s)', frame_index, frame_idx)

        pixel_data = frame_data.get('pixels', '')
        pixel_lines = AnimatedSprite.parse_toml_pixel_lines(pixel_data)

        if not pixel_lines:
            self.log.debug('    Skipping empty frame %s', frame_index)
            return None

        width, height, normalized_lines = self._validate_toml_frame_dimensions(
            pixel_lines,
            frame_index,
        )
        # Extract the frame's colors once: they decide the surface type and are the frame's
        # pixel data
        raw_pixels = extract_pixel_colors(normalized_lines, width, height, color_map)
        needs_alpha = needs_alpha_channel(raw_pixels)
        surface = AnimatedSprite._create_toml_surface(
            width,
            height,
            normalized_lines,
            color_map,
            needs_alpha=needs_alpha,
        )

        # Check for per-frame frame_interval, otherwise use global frame_interval
        frame_duration = frame_data.get('frame_interval', frame_interval)
        if 'frame_interval' in frame_data:
            self.log.debug('    Using per-frame frame_interval: %s', frame_duration)
        else:
            self.log.debug('    Using global frame_interval: %s', frame_duration)

        # Parse optional per-frame hitbox from [animation.frame.hitbox]
        frame_hitbox = AnimatedSprite._parse_hitbox_data(frame_data.get('hitbox'))

        frame = SpriteFrame(surface, duration=frame_duration, hitbox=frame_hitbox)
        # Store RGBA only when a pixel needs alpha; otherwise RGB (more efficient)
        if needs_alpha:
            frame.pixels = convert_pixels_to_rgba_if_needed(raw_pixels)
        else:
            frame.pixels = convert_pixels_to_rgb_if_possible(raw_pixels)

        self._log_frame_debug_info(frame_index, pixel_lines, frame_data)
        return frame

    @staticmethod
    def _parse_hitbox_data(
        hitbox_data: dict[str, int] | None,
    ) -> pygame.Rect | None:
        """Parse a hitbox dict from TOML data into a pygame.Rect.

        Args:
            hitbox_data: Dict with offset_x, offset_y, width, height keys, or None.

        Returns:
            A pygame.Rect if hitbox_data is not None, otherwise None.
        """
        if hitbox_data is None:
            return None
        return pygame.Rect(
            hitbox_data.get('offset_x', 0),
            hitbox_data.get('offset_y', 0),
            hitbox_data.get('width', 0),
            hitbox_data.get('height', 0),
        )

    @staticmethod
    def parse_toml_pixel_lines(pixel_data: str) -> list[str]:
        """Parse pixel data string into lines.

        Returns:
            list: The result.

        """
        raw_lines = pixel_data.split('\n')
        return [line.strip() for line in raw_lines if line.strip()]

    def _validate_toml_frame_dimensions(
        self: Self,
        pixel_lines: list[str],
        frame_index: int,
    ) -> tuple[int, int, list[str]]:
        """Validate and return frame dimensions and normalized lines.

        The lines come from parse_toml_pixel_lines, so they are already stripped and none is
        empty.

        Returns:
            tuple[int, int, list]: The result.

        """
        # Normalize line lengths for consistency
        # This helps handle AI-generated content with inconsistent formatting
        normalized_lines: list[str] = list(pixel_lines)

        # Find the most common line length (mode) to handle AI inconsistencies
        line_lengths = [len(line) for line in normalized_lines]
        length_counts = Counter(line_lengths)
        most_common_length = length_counts.most_common(1)[0][0]

        # If there are inconsistencies, try to normalize to the most common length
        if len(set(line_lengths)) > 1:
            self.log.warning(
                '    Frame %s: Inconsistent line lengths detected. '
                'Most common length: %s, lengths found: %s',
                frame_index,
                most_common_length,
                set(line_lengths),
            )

            # Normalize lines to the most common length
            normalized_lines = []
            for line in pixel_lines:
                normalized_line = line
                if len(normalized_line) > most_common_length:
                    # Truncate if too long
                    normalized_line = normalized_line[:most_common_length]
                elif len(normalized_line) < most_common_length:
                    # Pad with the last character if too short (no line is empty)
                    padding_length = most_common_length - len(normalized_line)
                    normalized_line += normalized_line[-1] * padding_length
                normalized_lines.append(normalized_line)

            self.log.info(
                '    Frame %s: Normalized to %s characters per line',
                frame_index,
                most_common_length,
            )

        # Every line now has the most common length
        height = len(normalized_lines)
        width = most_common_length
        self.log.debug('    Frame %s: %sx%s pixels', frame_index, width, height)
        self.log.debug('    Processed: %s lines of %s pixels each', len(normalized_lines), width)
        return width, height, normalized_lines

    @staticmethod
    def _create_toml_surface(
        width: int,
        height: int,
        pixel_lines: list[str],
        color_map: dict[str, tuple[int, ...]],
        *,
        needs_alpha: bool,
    ) -> pygame.Surface:
        """Create pygame surface from TOML pixel data.

        Args:
            width: The frame width in pixels.
            height: The frame height in pixels.
            pixel_lines: The frame's pixel rows, one glyph per pixel.
            color_map: Glyph to color mapping.
            needs_alpha: True when a pixel has alpha below 255 (needs_alpha_channel).

        Returns:
            pygame.Surface: The result.

        """
        if needs_alpha:
            surface = create_alpha_surface(width, height, pixel_lines, color_map)
        else:
            surface = create_indexed_surface(width, height, pixel_lines, color_map)

        return surface

    def _log_frame_debug_info(
        self: Self,
        frame_index: int,
        pixel_lines: list[str],
        frame_data: dict[str, Any],
    ) -> None:
        """Log debug information for a frame."""
        self.log.debug('    Frame %s loaded successfully', frame_index)
        self.log.debug('    Sanitized pixel data for frame %s:', frame_index)

        for y, line in enumerate(pixel_lines):
            self.log.debug('      %02x: %s', y, line)

        self.log.debug('    Frame %s metadata:', frame_index)
        for key, value in frame_data.items():
            if key != 'pixels':  # Don't repeat the pixel data
                self.log.debug('      %s: %s', key, value)

    def _log_toml_load_results(self: Self) -> None:
        """Log the results of TOML loading."""
        if self._animations:
            self.log.debug('TOML load complete: %s animation(s) loaded', len(self._animations))
            for anim_name, frames in self._animations.items():
                self.log.debug("  Animation '%s': %s frame(s)", anim_name, len(frames))
        else:
            self.log.debug('TOML load complete: No animations loaded')

    @override
    def save(self: Self, filename: str, file_format: str = DEFAULT_FILE_FORMAT) -> None:
        """Save animated sprite to a file.

        Currently only supports TOML format. To add new formats:
        1. Add format detection in _detect_file_format()
        2. Add save logic here (e.g., _save_json(), _save_xml())
        3. Add load methods in _load()
        4. Update tests
        See LOADER_README.md for detailed implementation guide.

        Raises:
            ValueError: If the file format is not supported.

        """
        # Check if this is a single animation with a single frame
        if self._is_single_frame_sprite():
            self.log.info('Detected single-frame sprite, saving in static sprite format')
            self._save_as_static_sprite(filename, file_format)
        elif file_format == 'toml':
            self._save_toml(filename)
        else:
            raise ValueError(ERR_UNSUPPORTED_FORMAT.format(file_format))

    def get_total_frame_count(self: Self) -> int:
        """Get the total number of frames across all animations.

        Returns:
            Total frame count across all animations. Returns 0 if no animations exist.

        """
        total_frames = 0
        for frames in self._animations.values():
            total_frames += len(frames)
        return total_frames

    def is_static_sprite(self: Self) -> bool:
        """Check if this sprite is static (has exactly 1 frame total).

        A static sprite has a single frame across all animations.
        This is determined by frame count, not by file format.

        Returns:
            True if sprite has exactly 1 frame, False otherwise

        """
        return self.get_total_frame_count() == 1

    def _is_single_frame_sprite(self: Self) -> bool:
        """Check if this sprite has only one animation with one frame.

        Returns:
            bool: True if the condition is met, False otherwise.

        """
        if len(self._animations) != 1:
            return False

        # Get the first (and only) animation
        animation_frames = next(iter(self._animations.values()))
        return len(animation_frames) == 1

    def _save_as_static_sprite(self: Self, filename: str, file_format: str) -> None:
        """Save as a static sprite format using existing TOML save methods.

        Raises:
            ValueError: If the file format is not supported.

        """
        if file_format == 'toml':
            # Use the existing TOML save method but modify it for single frame
            self._save_toml_single_frame(filename)
        else:
            # For unsupported formats, raise an error
            raise ValueError(ERR_UNSUPPORTED_FORMAT.format(file_format))

    def _get_effective_static_hitbox(
        self: Self,
        frame: SpriteFrame,
    ) -> dict[str, int] | None:
        """Get the effective hitbox dict for a static (single-frame) sprite save.

        For static sprites, uses the sprite-level default hitbox, or promotes
        the frame's explicit hitbox if no default is set.

        Returns:
            A hitbox dict with offset_x, offset_y, width, height, or None.
        """
        effective_hitbox = self._default_hitbox
        if effective_hitbox is None and frame.has_explicit_hitbox:
            effective_hitbox = frame.hitbox
        if effective_hitbox is None:
            return None
        return {
            'offset_x': effective_hitbox.x,
            'offset_y': effective_hitbox.y,
            'width': effective_hitbox.width,
            'height': effective_hitbox.height,
        }

    def _save_toml_single_frame(self: Self, filename: str) -> None:
        """Save single frame as static TOML using existing TOML infrastructure."""
        # Get the single frame from the single animation
        animation_name = next(iter(self._animations.keys()))
        frame = self._animations[animation_name][0]

        # Build color map for the single frame
        color_map = self._build_toml_color_map()

        # Get frame dimensions and pixel data
        width, height = frame.get_size()
        pixels = frame.get_pixel_data()

        # Convert pixels to characters with the same lookup as animated saves, which matches
        # RGBA pixels against RGB color-map keys (and raises for a missing color) instead of
        # requiring identical tuples and silently writing '.'
        pixel_rows = AnimatedSprite._convert_pixels_to_toml_chars(pixels, width, height, color_map)

        # Write TOML file with proper block string format
        with Path(filename).open('w', encoding='utf-8') as f:
            f.write('[sprite]\n')
            f.write(f'name = {toml_basic_string(self.name)}\n')
            # The same [sprite] keys, in the same format, as _write_toml_sprite_section
            if self.description:
                f.write(f'description = {toml_multiline_basic_string(self.description)}\n')
            if self.frame_anchor is not FrameAnchor.NONE:
                f.write(f'frame_anchor = "{self.frame_anchor.value}"\n')
            f.write('pixels = """\n')
            f.write('\n'.join(pixel_rows))
            f.write('\n"""\n\n')

            hitbox_data = self._get_effective_static_hitbox(frame)
            if hitbox_data is not None:
                AnimatedSprite._write_toml_hitbox_section(
                    f,
                    section_header='[sprite.hitbox]',
                    hitbox_data=hitbox_data,
                )

            # Write colors using the shared writer for consistent TOML format
            color_data = AnimatedSprite._color_map_to_defs(color_map)
            AnimatedSprite._write_toml_colors(
                f,
                {'colors': color_data},
                self._color_order,
            )
            AnimatedSprite._write_toml_transitions(f, self.transition_data)

    def _save_toml(self: Self, filename: str) -> None:
        """Save animated sprite in TOML format.

        This is the main TOML save method for animated sprites. To add new formats:
        1. Create similar methods like _save_json(), _save_xml()
        2. Add format detection in _detect_file_format()
        3. Add save logic in save() method
        4. Update tests
        See LOADER_README.md for detailed implementation guide.
        """
        color_map = self._build_toml_color_map()
        data = self._build_toml_data_structure(color_map)

        with Path(filename).open('w', encoding='utf-8') as f:
            AnimatedSprite._write_toml_sprite_section(f, data)
            AnimatedSprite._write_toml_animations(f, data)
            # Use original color order if available to preserve file format
            AnimatedSprite._write_toml_colors(f, data, self._color_order)
            AnimatedSprite._write_toml_transitions(f, self.transition_data)

    def _build_toml_color_map(self: Self) -> dict[tuple[int, ...], str]:
        """Build color map for TOML format.

        This method creates a mapping from RGB/RGBA colors to characters for TOML format.
        If the sprite was loaded from a TOML file, it preserves the original character assignments.
        To add new formats, create similar methods like _build_json_color_map(),
        _build_xml_color_map()
        See LOADER_README.md for detailed implementation guide.

        Returns:
            dict: The result.

        Raises:
            ValueError: If there are too many unique colors to map to characters.

        """
        color_map: dict[tuple[int, ...], str] = {}
        universal_chars = SPRITE_GLYPHS
        char_index = 0

        # If we have an original color map from loading, build reverse mapping (color -> char)
        original_color_to_char, used_chars = self._build_reverse_color_map()

        # Check if the sprite uses per-pixel alpha mode.
        # This determines whether magenta is stored as RGBA (255,0,255,255)
        # or stays as RGB (255,0,255) for indexed color mode.
        sprite_needs_alpha = self._sprite_uses_per_pixel_alpha()
        has_magenta = self._any_pixel_is_magenta()

        if has_magenta:
            # Reserve character for magenta transparency key
            if sprite_needs_alpha:
                magenta_key: tuple[int, ...] = (255, 0, 255, 255)
            else:
                magenta_key = (255, 0, 255)
            color_map[magenta_key] = original_color_to_char.get(
                magenta_key,
                original_color_to_char.get((255, 0, 255, 255), '\u2588'),
            )
            universal_chars = [c for c in universal_chars if c != '\u2588']

        for frames in self._animations.values():
            for frame in frames:
                pixels = frame.get_pixel_data()
                needs_alpha = sprite_needs_alpha

                for pixel in pixels:
                    color_tuple = normalize_pixel_for_color_map(pixel, needs_alpha=needs_alpha)

                    if color_tuple in color_map:
                        continue

                    # First try to use original character assignment
                    if color_tuple in original_color_to_char:
                        color_map[color_tuple] = original_color_to_char[color_tuple]
                        continue

                    # New color - assign next available character
                    # Skip characters already used in original map
                    while (
                        char_index < len(universal_chars)
                        and universal_chars[char_index] in used_chars
                    ):
                        char_index += 1
                    if char_index >= len(universal_chars):
                        raise ValueError(ERR_TOO_MANY_COLORS.format(len(universal_chars)))
                    char = universal_chars[char_index]
                    color_map[color_tuple] = char
                    used_chars.add(char)
                    char_index += 1

        return color_map

    def _build_reverse_color_map(self: Self) -> tuple[dict[tuple[int, ...], str], set[str]]:
        """Build reverse mapping from colors to characters using original color map.

        Returns:
            Tuple of (original_color_to_char dict, used_chars set).

        """
        original_color_to_char: dict[tuple[int, ...], str] = {}
        used_chars: set[str] = set()
        if not self._color_map:
            return original_color_to_char, used_chars

        for char, color in self._color_map.items():
            used_chars.add(char)
            # Normalize color to match how we'll look it up.
            # Map magenta to both RGB and RGBA keys so either mode can find it.
            if len(color) == RGBA_COMPONENT_COUNT:
                r, g, b, a = color
                if (r, g, b) == MAGENTA_TRANSPARENCY_KEY:
                    original_color_to_char[255, 0, 255, 255] = char
                    original_color_to_char[255, 0, 255] = char
                elif a == MAX_COLOR_CHANNEL_VALUE:
                    # Opaque RGBA - can match as RGB or RGBA
                    original_color_to_char[color] = char
                    original_color_to_char[r, g, b] = char
                else:
                    # Has transparency - only RGBA key
                    original_color_to_char[color] = char
            elif color == MAGENTA_TRANSPARENCY_KEY:
                original_color_to_char[255, 0, 255] = char
                original_color_to_char[255, 0, 255, 255] = char
            else:
                original_color_to_char[color] = char
                # Also allow RGBA version with alpha=255
                original_color_to_char[color[0], color[1], color[2], 255] = char

        return original_color_to_char, used_chars

    def _any_pixel_is_magenta(self: Self) -> bool:
        """Check if any pixel across all animations is magenta.

        Returns:
            True if any pixel is the magenta transparency key.

        """
        for frames in self._animations.values():
            for frame in frames:
                pixels = frame.get_pixel_data()
                for pixel in pixels:
                    if len(pixel) == RGBA_COMPONENT_COUNT:
                        r, g, b, _a = pixel
                        if (r, g, b) == MAGENTA_TRANSPARENCY_KEY:
                            return True
                    elif pixel == MAGENTA_TRANSPARENCY_KEY:
                        return True
        return False

    def _sprite_uses_per_pixel_alpha(self: Self) -> bool:
        """Check if any pixel in the sprite has actual per-pixel alpha (alpha < 255).

        This excludes magenta transparency which is handled by indexed color mode.
        Used to decide whether the save pipeline should use RGBA or RGB format.

        Returns:
            True if any pixel has alpha in the range 0-254.
        """
        for frames in self._animations.values():
            for frame in frames:
                pixels = frame.get_pixel_data()
                for pixel in pixels:
                    if len(pixel) == RGBA_COMPONENT_COUNT:
                        _r, _g, _b, a = pixel
                        if a != MAX_COLOR_CHANNEL_VALUE:
                            return True
        return False

    def _build_toml_color_definitions(
        self: Self,
        color_map: dict[tuple[int, ...], str],
    ) -> dict[str, dict[str, int]]:
        """Build TOML color definitions from the color map.

        Preserves original alpha format: colors with alpha=0-254 are per-pixel alpha,
        colors with alpha=255 or no alpha are indexed (RGB only).

        Returns:
            dict: Mapping of character to color definition dict.

        """
        colors: dict[str, dict[str, int]] = {}
        original_alpha_values = self._colors_with_per_pixel_alpha
        for color_tuple, char in color_map.items():
            r, g, b = color_tuple[:3]
            if char in original_alpha_values:
                # This color originally had alpha=0-254 (per-pixel alpha) - preserve that value
                colors[char] = {
                    'red': r,
                    'green': g,
                    'blue': b,
                    'alpha': original_alpha_values[char],
                }
            elif (
                len(color_tuple) == RGBA_COMPONENT_COUNT
                and color_tuple[3] != MAX_COLOR_CHANNEL_VALUE
            ):
                # RGBA color with alpha 0-254 (per-pixel alpha) - write the alpha value
                colors[char] = {'red': r, 'green': g, 'blue': b, 'alpha': color_tuple[3]}
            else:
                # RGB color or alpha=255 (indexed) - write RGB only
                colors[char] = {'red': r, 'green': g, 'blue': b}

        return colors

    def _build_toml_data_structure(
        self: Self,
        color_map: dict[tuple[int, ...], str],
    ) -> dict[str, Any]:
        """Build TOML data structure.

        Returns:
            dict: The result.

        """
        sprite_section: dict[str, Any] = {
            'name': self.name or 'animated_sprite',
            'description': self.description or '',
        }
        if self.frame_anchor is not FrameAnchor.NONE:
            sprite_section['frame_anchor'] = self.frame_anchor.value

        # Write the sprite-level hitbox only when one was defined (loaded or set); without
        # one, collision uses the visible pixels, which a written hitbox would freeze
        if self._default_hitbox is not None:
            sprite_section['hitbox'] = {
                'offset_x': self._default_hitbox.x,
                'offset_y': self._default_hitbox.y,
                'width': self._default_hitbox.width,
                'height': self._default_hitbox.height,
            }

        data: dict[str, Any] = {
            'sprite': sprite_section,
            'colors': {},
            'animation': [],
        }

        # Add color definitions - preserve original alpha format
        data['colors'] = self._build_toml_color_definitions(color_map)

        # Add animations
        for anim_name, frames in self._animations.items():
            data['animation'].append(self._build_toml_animation_entry(anim_name, frames, color_map))
            self.log.debug("Serializing animation '%s' with %s frames", anim_name, len(frames))

        return data

    def _build_toml_animation_entry(
        self: Self,
        animation_name: str,
        frames: list[SpriteFrame],
        color_map: dict[tuple[int, ...], str],
    ) -> dict[str, Any]:
        """Build one [[animation]] entry with its timing and frames.

        Returns:
            dict: The animation's namespace, frame_interval, loop and frame list. Only frames
            whose duration differs from the animation's frame_interval carry their own.

        """
        animation_frame_interval = self._animation_frame_interval_for_save(animation_name)
        animation_frames = AnimatedSprite._create_toml_animation_frames(frames, color_map)
        for frame, frame_data in zip(frames, animation_frames, strict=True):
            if frame.duration != animation_frame_interval:
                frame_data['frame_interval'] = frame.duration
        return {
            'namespace': animation_name,
            'frame_interval': animation_frame_interval,
            'loop': self._loop_flags.get(animation_name, True),
            'frame': animation_frames,
        }

    def _animation_frame_interval_for_save(self: Self, animation_name: str) -> float:
        """Return the [[animation]] frame_interval to write for an animation.

        The value loaded from TOML when there is one. Otherwise (an animation built in code
        or in Bitmappy) the most common frame duration, the first frame's on a tie, so as few
        frames as possible need a per-frame override; 0.5 (the loader's default) with no
        frames.

        Returns:
            float: The animation's frame_interval in seconds.

        """
        loaded_frame_interval = self._animation_frame_intervals.get(animation_name)
        if loaded_frame_interval is not None:
            return loaded_frame_interval
        durations = [frame.duration for frame in self._animations.get(animation_name, [])]
        if not durations:
            return 0.5
        return max(durations, key=durations.count)

    @staticmethod
    def _create_toml_animation_frames(
        frames: list[SpriteFrame],
        color_map: dict[tuple[int, ...], str],
    ) -> list[dict[str, Any]]:
        """Create TOML animation frames.

        Returns:
            list: The result.

        """
        animation_frames: list[dict[str, Any]] = []
        for i, frame in enumerate(frames):
            frame_data = AnimatedSprite._create_toml_frame_data(frame, i, color_map)
            animation_frames.append(frame_data)
        return animation_frames

    @staticmethod
    def _create_toml_frame_data(
        frame: SpriteFrame,
        frame_index: int,
        color_map: dict[tuple[int, ...], str],
    ) -> dict[str, Any]:
        """Create TOML frame data.

        Returns:
            dict: The result.

        """
        pixels = frame.get_pixel_data()
        width, height = frame.get_size()
        pixel_chars = AnimatedSprite._convert_pixels_to_toml_chars(pixels, width, height, color_map)
        frame_data: dict[str, Any] = {
            'frame_index': frame_index,
            'pixels': '\n'.join(pixel_chars),
        }

        # Write a per-frame hitbox only when the frame has an explicit one (never the
        # visible-pixel fallback)
        if frame.has_explicit_hitbox:
            hitbox = frame.hitbox
            frame_data['hitbox'] = {
                'offset_x': hitbox.x,
                'offset_y': hitbox.y,
                'width': hitbox.width,
                'height': hitbox.height,
            }

        return frame_data

    @staticmethod
    def _convert_pixels_to_toml_chars(
        pixels: list[tuple[int, ...]],
        width: int,
        height: int,
        color_map: dict[tuple[int, ...], str],
    ) -> list[str]:
        """Convert pixels to TOML character representation.

        Returns:
            list: The result.

        """
        pixel_chars: list[str] = []
        # Determine whether the color map expects RGBA or RGB tuples
        # If any key in the color_map has length 4, we assume alpha-aware mapping
        map_uses_alpha = (
            any(len(k) == RGBA_COMPONENT_COUNT for k in color_map) if color_map else False
        )
        for y in range(height):
            row_chars: list[str] = []
            for x in range(width):
                pixel_idx = y * width + x
                if pixel_idx < len(pixels):
                    pixel = pixels[pixel_idx]
                    color_char = lookup_pixel_char(pixel, color_map, map_uses_alpha=map_uses_alpha)
                    row_chars.append(color_char)
                else:
                    row_chars.append('.')
            pixel_chars.append(''.join(row_chars))
        return pixel_chars

    @staticmethod
    def _write_toml_sprite_section(f: IO[str], data: dict[str, Any]) -> None:
        """Write TOML sprite section."""
        f.write('[sprite]\n')
        f.write(f'name = {toml_basic_string(data["sprite"]["name"])}\n')
        if data['sprite'].get('description'):
            description = data['sprite']['description']
            f.write(f'description = {toml_multiline_basic_string(description)}\n')
        if 'frame_anchor' in data['sprite']:
            f.write(f'frame_anchor = "{data["sprite"]["frame_anchor"]}"\n')
        f.write('\n')

        # Write sprite-level hitbox if present
        if 'hitbox' in data['sprite']:
            AnimatedSprite._write_toml_hitbox_section(
                f,
                section_header='[sprite.hitbox]',
                hitbox_data=data['sprite']['hitbox'],
            )

    @staticmethod
    def _write_toml_animations(f: IO[str], data: dict[str, Any]) -> None:
        """Write TOML animations section."""
        for animation in data['animation']:
            f.write('[[animation]]\n')
            f.write(f'namespace = "{animation["namespace"]}"\n')
            f.write(f'frame_interval = {animation["frame_interval"]}\n')
            f.write(f'loop = {str(animation["loop"]).lower()}\n\n')

            for frame in animation['frame']:
                f.write('[[animation.frame]]\n')
                f.write(f'namespace = "{animation["namespace"]}"\n')
                f.write(f'frame_index = {frame["frame_index"]}\n')
                if 'frame_interval' in frame:
                    f.write(f'frame_interval = {frame["frame_interval"]}\n')
                f.write('pixels = """\n')
                f.write(frame['pixels'])
                f.write('\n"""\n\n')

                # Write per-frame hitbox if present
                if 'hitbox' in frame:
                    AnimatedSprite._write_toml_hitbox_section(
                        f,
                        section_header='[animation.frame.hitbox]',
                        hitbox_data=frame['hitbox'],
                    )

    @staticmethod
    def _color_map_to_defs(
        color_map: dict[tuple[int, ...], str],
    ) -> dict[str, dict[str, int]]:
        """Convert a color_map (tuple→char) to TOML color definitions (char→{r,g,b[,a]}).

        Returns:
            Dict mapping character to color definition dict.
        """
        color_defs: dict[str, dict[str, int]] = {}
        for color_tuple, char in color_map.items():
            if len(color_tuple) == RGBA_COMPONENT_COUNT:
                r, g, b, a = color_tuple
                color_defs[char] = {'red': r, 'green': g, 'blue': b, 'alpha': a}
            else:
                r, g, b = color_tuple
                color_defs[char] = {'red': r, 'green': g, 'blue': b}
        return color_defs

    @staticmethod
    def _write_toml_transitions(f: IO[str], transitions: list[dict[str, Any]]) -> None:
        """Write [[transition]] tables in order, each key and value as loaded (escaped)."""
        for transition in transitions:
            f.write('\n[[transition]]\n')
            for key, value in transition.items():
                f.write(f'{toml_key(key)} = {toml_scalar(value)}\n')

    @staticmethod
    def _write_toml_hitbox_section(
        f: IO[str],
        section_header: str,
        hitbox_data: dict[str, int],
    ) -> None:
        """Write a TOML hitbox section with offset and dimension fields.

        Args:
            f: File handle to write to.
            section_header: The TOML section header (e.g. '[sprite.hitbox]').
            hitbox_data: Dict with offset_x, offset_y, width, height keys.
        """
        f.write(f'{section_header}\n')
        f.write(f'offset_x = {hitbox_data["offset_x"]}\n')
        f.write(f'offset_y = {hitbox_data["offset_y"]}\n')
        f.write(f'width = {hitbox_data["width"]}\n')
        f.write(f'height = {hitbox_data["height"]}\n')
        f.write('\n')

    @staticmethod
    def _write_toml_colors(
        f: IO[str],
        data: dict[str, Any],
        color_order: list[str] | None = None,
    ) -> None:
        """Write TOML colors section.

        Args:
            f: File handle to write to
            data: TOML data structure
            color_order: Optional list of characters in the order they should be written.
                        If None, uses dictionary iteration order.

        """
        if data['colors']:
            f.write('[colors]\n')
            # Use original order if provided, otherwise use dict iteration order
            if color_order:
                chars_to_write = [char for char in color_order if char in data['colors']]
                # Add any new colors not in original order
                for char in data['colors']:
                    if char not in chars_to_write:
                        chars_to_write.append(char)
            else:
                chars_to_write = list(data['colors'].keys())

            for char in chars_to_write:
                color = data['colors'][char]
                f.write(f'[colors."{char}"]\n')
                f.write(f'red = {color["red"]}\n')
                f.write(f'green = {color["green"]}\n')
                f.write(f'blue = {color["blue"]}\n')
                if 'alpha' in color:
                    f.write(f'alpha = {color["alpha"]}\n')
                f.write('\n')

    @staticmethod
    def _write_toml_alpha(
        f: IO[str],
        data: dict[str, Any],
        *,
        preserve_trailing_newline: bool = False,
    ) -> None:
        """Write TOML alpha section if needed."""
        if 'alpha' in data:
            f.write('[alpha]\n')
            f.write(f'blending = {str(data["alpha"]["blending"]).lower()}\n')
            if not preserve_trailing_newline:
                f.write('\n')

    @override
    def update(self: Self, dt: float = 0.016) -> None:
        """Update animation timing."""
        if not self._is_playing or not self.frame_manager.current_animation:
            return

        if self.frame_manager.current_animation not in self._animations:
            return

        frames = self._animations[self.frame_manager.current_animation]
        if not frames:
            # No frames available, stop animation
            self._is_playing = False
            return

        # Update frame timer
        self._frame_timer += dt

        # Use the current frame's duration for timing
        # Ensure current frame index is within bounds
        if self.frame_manager.current_frame >= len(frames):
            self.frame_manager.current_frame = max(0, len(frames) - 1)

        self.frame_manager.current_frame = max(self.frame_manager.current_frame, 0)

        current_frame = frames[self.frame_manager.current_frame]
        frame_interval = current_frame.duration

        if self._frame_timer >= frame_interval:
            self._advance_frame(frames)
            self._update_surface_and_mark_dirty()
            # The dump hashes the frame's pixels or copies its image: skip it unless it is logged
            if self.log.isEnabledFor(logging.DEBUG):
                self._debug_frame_info(frames)

    def _advance_frame(self: Self, frames: list[SpriteFrame]) -> None:
        """Advance to the next frame in the animation."""
        old_frame = self.frame_manager.current_frame
        self._frame_timer = 0.0
        self.frame_manager.current_frame += 1

        # Log only on frame transitions. Every playing sprite advances several times a second,
        # so the arguments are read only when DEBUG is on.
        debug_enabled = self.log.isEnabledFor(logging.DEBUG)
        if debug_enabled:
            self.log.debug('Frame advance: %s -> %s', old_frame, self.frame_manager.current_frame)
            if old_frame == 0 and self.frame_manager.current_frame == 1:
                self.log.debug('FIRST FRAME ADVANCE: 0 -> 1')

        # Check if we've reached the end
        if self.frame_manager.current_frame >= len(frames):
            if self._is_looping:
                self.frame_manager.current_frame = 0
                if debug_enabled:
                    self.log.debug('Looping back to frame 0 (total frames: %s)', len(frames))
            else:
                self.frame_manager.current_frame = len(frames) - 1
                self._is_playing = False
                if debug_enabled:
                    self.log.debug(
                        'Animation ended, stopped at frame %s',
                        self.frame_manager.current_frame,
                    )

    def _debug_frame_info(self: Self, frames: list[SpriteFrame]) -> None:
        """Debug frame information for development."""
        if (
            not self.frame_manager.current_animation
            or self.frame_manager.current_animation not in self._animations
        ):
            self.log.debug(
                "ANIMATION FRAME DUMP: animation '%s' not found or no animation",
                self.frame_manager.current_animation,
            )
            return

        if self.frame_manager.current_frame >= len(frames):
            self.log.debug(
                'ANIMATION FRAME DUMP: frame_index %s out of range for %s frames',
                self.frame_manager.current_frame,
                len(frames),
            )
            return

        frame = frames[self.frame_manager.current_frame]
        self.log.debug(
            "ANIMATION FRAME DUMP: animation='%s', frame_index=%s, frame=%s, has_surface=%s",
            self.frame_manager.current_animation,
            self.frame_manager.current_frame,
            frame,
            hasattr(frame, 'surface'),
        )

        self._debug_frame_pixel_data(frame)

    def _debug_frame_pixel_data(self: Self, frame: SpriteFrame) -> None:
        """Debug pixel data for a frame."""
        if hasattr(frame, 'pixels') and frame.pixels:
            # Create hash of frame pixel data for debugging
            pixel_data_str = str(frame.pixels)
            pixel_hash = hashlib.sha256(pixel_data_str.encode()).hexdigest()[:8]
            self.log.debug(
                '  Frame %s pixel hash: %s', self.frame_manager.current_frame, pixel_hash
            )
            self.log.debug('  Total pixels: %s', len(frame.pixels))
        elif hasattr(frame, 'image'):
            self._debug_frame_image_data(frame)
        else:
            self.log.debug('  No pixel data available')

    def _debug_frame_image_data(self: Self, frame: SpriteFrame) -> None:
        """Debug image data for a frame."""
        try:
            pixel_array = pygame.surfarray.array3d(frame.image)  # type: ignore[no-untyped-call]
        except (ValueError, pygame.error) as e:
            self.log.debug('  Could not get pixel data from image: %s', e)
            return
        self.log.debug('  Image surface size: %s', frame.image.get_size())
        self.log.debug('  Pixel array shape: %s', pixel_array.shape)
        # Show a small sample of pixel data
        if pixel_array.size > 0:
            # array3d always returns a (width, height, 3) array
            sample_data = str(pixel_array[0, 0, :])  # pyright: ignore[reportUnknownArgumentType]
            self.log.debug('  Sample pixel data: %s', sample_data)

    def _update_surface_and_mark_dirty(self) -> None:
        """Update the sprite's surface and mark as dirty for efficient rendering."""
        if (
            not self.frame_manager.current_animation
            or self.frame_manager.current_animation not in self._animations
        ):
            return

        frames = self._animations[self.frame_manager.current_animation]
        if self.frame_manager.current_frame >= len(frames):
            return

        # Check if the animation or frame actually changed
        current_frame_key = (
            self.frame_manager.current_animation,
            self.frame_manager.current_frame,
        )
        if self._last_drawn_frame == current_frame_key:
            return  # No change needed

        # Update the sprite's image and rect
        new_surface = self._get_current_surface()
        self.image = new_surface

        # Preserve the current position when updating rect
        old_center = self.rect.center
        self.rect = new_surface.get_rect()
        self.rect.center = old_center

        # Update frame tracking
        self._last_drawn_frame = current_frame_key

        # Mark as dirty for pygame's dirty sprite system
        self.dirty = 1

        # Runs on every frame change of every playing sprite: read the arguments only for DEBUG
        if self.log.isEnabledFor(logging.DEBUG):
            self.log.debug(
                "Updated surface for frame %s of animation '%s'",
                self.frame_manager.current_frame,
                self.frame_manager.current_animation,
            )

    @staticmethod
    def _create_surface_from_toml_pixels(
        width: int,
        height: int,
        pixels: list[tuple[int, ...]],
    ) -> pygame.Surface:
        """Create a drawable pygame surface from TOML RGB or RGBA pixel data.

        Transparency follows the TOML rules (see pixel_utils.is_color_transparent): magenta
        (255, 0, 255) is the transparency key, also when stored as opaque RGBA (the loader
        stores every frame that has magenta as RGBA), and alpha 0 is transparent.

        A frame with translucent pixels (alpha 1-254) gives a per-pixel alpha surface that
        keeps each pixel's alpha, its transparent pixels at alpha 0. Any other frame gives a
        plain surface with magenta as its colorkey: it blits faster than per-pixel alpha, and
        its keyed pixels are never written, whatever the destination's alpha (a per-pixel
        alpha source over a destination pixel of alpha 0 copies its color instead of
        blending, as on a display with an alpha channel). Pixels past width * height are
        ignored.

        Returns:
            pygame.Surface: The result.

        """
        pixels_to_draw = pixels[: width * height]
        has_translucent_pixels = any(
            len(pixel) == RGBA_COMPONENT_COUNT and 0 < pixel[3] < MAX_COLOR_CHANNEL_VALUE
            for pixel in pixels_to_draw
        )
        if has_translucent_pixels:
            surface = pygame.Surface((width, height), pygame.SRCALPHA)
            transparent_color = TRANSPARENT_MAGENTA
        else:
            surface = pygame.Surface((width, height))
            surface.set_colorkey(MAGENTA_TRANSPARENCY_KEY)
            transparent_color = MAGENTA_TRANSPARENCY_KEY

        # Set each pixel on the surface from the pixel data
        for pixel_index, pixel in enumerate(pixels_to_draw):
            position = (pixel_index % width, pixel_index // width)
            if is_color_transparent(pixel):
                surface.set_at(position, transparent_color)
            else:
                surface.set_at(position, pixel)

        return surface

    def update_nested_sprites(self: Self) -> None:
        """Update nested sprites (required by SpriteInterface)."""
        # AnimatedSprite doesn't have nested sprites, so this is a no-op

    def clear_surface_cache(self: Self) -> None:
        """Clear the surface cache to free memory."""
        self._surface_cache.clear()
        self.log.debug('Surface cache cleared')

    def _get_animation_data(self: Self) -> dict[str, dict[str, object]]:
        """Get animation data for AI training.

        Returns:
            dict: The animation data.

        """
        if not self._animations:
            return {}

        animation_data: dict[str, dict[str, object]] = {}
        for anim_name, frames in self._animations.items():
            animation_data[anim_name] = {
                'frames': len(frames),
                'frame_interval': 0.5,  # Default frame interval
                'loop': True,  # Default loop setting
            }

        return animation_data
