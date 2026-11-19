"""Compiled sprites: a sprite file's text loaded once per process, its frames shared read-only.

Every ``AnimatedSprite`` loaded from the same text, by the same source, shares one compile: its
frames (``SpriteFrame`` objects, their surfaces and pixels) and each frame's drawn surface at scale
1. Each sprite keeps its own playback state and its own copies of everything else the load set
(plans/2026-11-18-shared-sprite-frames.md, the owner, 2026-11-18: "like we did with sounds").
Before this, sixteen zombies loaded from one file held sixteen copies of its frames
(bugs/2026-11-18-sprite-frames-held-a-tuple-per-pixel.md).

``ENGINE_SPRITE_CACHE`` is the process's one cache, shaped like ``audio/library.py``'s
``SharedSoundCache``: shared by every engine context (an Arcade tile reuses what another game
compiled), least recently used first out past ``limit_bytes``, emptied by the test harness
around every test. It is a read-only cache in the engine context's sense
(plans/2026-10-25-engine-context.md): its values are computed only from their keys and never
written after they are made. A sprite already loaded keeps its frames when its entry goes, as it
holds them.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from types import MappingProxyType  # ruff: ignore[typing-only-standard-library-import] - pydantic resolves CompiledSprite's read-only mappings at runtime
from typing import Any, Final

import pygame
from pydantic import BaseModel, ConfigDict

from glitchygames.sprites.animated import AnimatedSprite, FrameAnchor
from glitchygames.sprites.frame import SpriteFrame  # ruff: ignore[typing-only-first-party-import] - pydantic resolves CompiledSprite.animations at runtime

# Past this many bytes of compiled frames, the least recently used compiles are dropped
DEFAULT_SPRITE_CACHE_LIMIT_BYTES: Final = 64 * 1024 * 1024

# The AnimatedSprite attributes a load sets from the text alone, which a compile captures and every
# load from it copies (frames shared): measured as every attribute a load of each shipped sprite
# changes, less the ones each sprite sets for itself (its state machine, first animation, image,
# surface cache and draw tracking). The conservation test compares a cached load with the loader's
# own on each of them (tests/sprites/test_animated_sprite.py, TestSharedFrames)
SHARED_SPRITE_FIELDS: Final = (
    'name',
    'description',
    'tags',
    '_default_hitbox',
    'frame_anchor',
    '_animation_order',
    '_animation_frame_intervals',
    '_loop_flags',
    '_animations_without_frame_index',
    '_game_tables',
    'transition_data',
    'pixel_row_repairs',
    '_pixel_rows_source',
    '_color_map',
    '_color_order',
)

# A compile's key: the sha256 of the sprite file's text, and the source it was loaded from (the
# compile's pixel-row repair warnings name its source, so another source compiles anew)
type SpriteKey = tuple[str, str]


def sprite_key(*, text: str, source_name: str) -> SpriteKey:
    """Return the key a sprite file's text, loaded from source_name, is compiled under.

    Args:
        text: The sprite file's TOML text.
        source_name: What the text came from (a file name, a console).

    Returns:
        SpriteKey: The text's sha256 hexdigest, and the source.

    """
    return (hashlib.sha256(text.encode('utf-8')).hexdigest(), source_name)


class CompiledSprite(BaseModel):
    """Everything one load of a sprite file's text set on its sprite, kept read-only.

    The fields are AnimatedSprite's of the same names (without the leading underscore): a
    sprite loaded from the cache copies the mutable ones for itself and shares the frames.
    ``drawn_surfaces`` holds each frame's drawn surface at scale 1, by (animation, frame index);
    ``byte_count`` is what the entry counts against the cache's limit.
    """

    model_config = ConfigDict(frozen=True, extra='forbid', arbitrary_types_allowed=True)

    name: str
    description: str
    tags: tuple[str, ...]
    default_hitbox: pygame.Rect | None
    frame_anchor: FrameAnchor
    animations: MappingProxyType[str, tuple[SpriteFrame, ...]]
    animation_order: tuple[str, ...]
    animation_frame_intervals: MappingProxyType[str, float]
    loop_flags: MappingProxyType[str, bool]
    animations_without_frame_index: frozenset[str]
    game_tables: MappingProxyType[str, Any]
    transition_data: tuple[dict[str, Any], ...]
    pixel_row_repairs: tuple[str, ...]
    pixel_rows_source: str
    color_map: MappingProxyType[str, tuple[int, ...]]
    color_order: tuple[str, ...]
    # The loader's last [[animation]] frame_interval, or None when it set none (written, never
    # read: carried so a cached load is the loader's sprite exactly)
    frame_interval: float | None
    drawn_surfaces: MappingProxyType[tuple[str, int], pygame.Surface]
    byte_count: int


def compile_sprite_text(*, text: str, source_name: str) -> CompiledSprite:
    """Compile a sprite file's text: run the loader once and keep what it set, read-only.

    The loader is AnimatedSprite's own, run on a private sprite (``AnimatedSprite.compiled_from_
    text``), so a sprite loaded from the compile and one loaded without it cannot differ. A text
    the loader refuses raises here, and nothing is made.

    Args:
        text: The sprite file's TOML text.
        source_name: What the text came from (a file name, a console).

    Returns:
        CompiledSprite: The compile.

    """
    return AnimatedSprite.compiled_from_text(text=text, source_name=source_name)


def compiled_sprite_bytes(
    *,
    animations: dict[str, tuple[SpriteFrame, ...]],
    drawn_surfaces: dict[tuple[str, int], pygame.Surface],
) -> int:
    """Return what a compile holds: its surfaces' pixel bytes and 8 bytes per pixel reference.

    Returns:
        int: The byte count.

    """
    frames = [frame for frames in animations.values() for frame in frames]
    surfaces = [frame.read_only_image for frame in frames] + list(drawn_surfaces.values())
    surface_bytes = sum(
        surface.get_width() * surface.get_height() * surface.get_bytesize() for surface in surfaces
    )
    return surface_bytes + sum(8 * len(frame.read_only_pixels) for frame in frames)


def compiled_sprite_fingerprint(*, compiled: CompiledSprite) -> str:
    """Return a digest of a compile's surfaces: their pixels, colorkeys and surface alphas.

    Returns:
        str: The sha256 hexdigest.

    """
    digest = hashlib.sha256()
    surfaces = [
        frame.read_only_image for frames in compiled.animations.values() for frame in frames
    ] + list(compiled.drawn_surfaces.values())
    for surface in surfaces:
        digest.update(pygame.image.tobytes(surface, 'RGBA'))
        digest.update(repr((surface.get_colorkey(), surface.get_alpha())).encode())
    return digest.hexdigest()


class SharedSpriteCache:
    """The process's compiled sprites by key, shared by every engine context.

    Reads and keeps take one lock, held only for the lookup or the store: a compile runs outside
    it, so two loads of one text at once may both compile, and ``keep`` gives both the first.
    ``clear`` exists for the test harness, which starts every test with an empty cache.
    """

    def __init__(self) -> None:
        """Start empty."""
        self._compiled: OrderedDict[SpriteKey, CompiledSprite] = OrderedDict()
        # Each kept compile's fingerprint when kept (changed_entries)
        self._fingerprints: dict[SpriteKey, str] = {}
        self._lock = threading.Lock()
        self.limit_bytes: int = DEFAULT_SPRITE_CACHE_LIMIT_BYTES

    def __len__(self) -> int:
        """The number of compiled sprites kept.

        Returns:
            The count.

        """
        return len(self._compiled)

    @property
    def bytes_held(self) -> int:
        """The bytes every kept compile counts against the limit."""
        with self._lock:
            return sum(compiled.byte_count for compiled in self._compiled.values())

    def compiled(self, *, key: SpriteKey) -> CompiledSprite | None:
        """Return the compile kept under key, if any (it becomes the most recently used).

        Args:
            key: The text's key (``sprite_key``).

        Returns:
            The compiled sprite, or None.

        """
        with self._lock:
            compiled = self._compiled.get(key)
            if compiled is not None:
                self._compiled.move_to_end(key)
            return compiled

    def keep(self, *, key: SpriteKey, compiled: CompiledSprite) -> CompiledSprite:
        """Keep a fresh compile under key, unless one is kept already.

        Args:
            key: The text's key (``sprite_key``).
            compiled: The fresh compile.

        Returns:
            The compile now kept under key: the first one when another load kept one first.

        """
        with self._lock:
            kept = self._compiled.get(key)
            if kept is not None:
                self._compiled.move_to_end(key)
                return kept
            self._compiled[key] = compiled
            self._fingerprints[key] = compiled_sprite_fingerprint(compiled=compiled)
            self._evict_past_the_limit(keep=key)
            return compiled

    def changed_entries(self) -> list[SpriteKey]:
        """Return the keys of kept compiles whose surfaces changed since they were kept.

        A compile is never written after it is made: a change is a path that wrote around a
        frame's copy-on-write. The test harness fails a test that leaves one.

        Returns:
            list[SpriteKey]: The changed compiles' keys, in the cache's order.

        """
        with self._lock:
            return [
                key
                for key, compiled in self._compiled.items()
                if compiled_sprite_fingerprint(compiled=compiled) != self._fingerprints[key]
            ]

    def clear(self) -> None:
        """Forget every compile (the test harness's reset; the next load compiles)."""
        with self._lock:
            self._compiled.clear()
            self._fingerprints.clear()

    def _evict_past_the_limit(self, *, keep: SpriteKey) -> None:
        """Drop the least recently used compiles, never keep, until the rest fit the limit."""
        held = sum(compiled.byte_count for compiled in self._compiled.values())
        for key in list(self._compiled):
            if held <= self.limit_bytes:
                return
            if key == keep:
                continue
            held -= self._compiled.pop(key).byte_count
            del self._fingerprints[key]


# The process's one cache of compiled sprites (SharedSpriteCache)
ENGINE_SPRITE_CACHE: Final[SharedSpriteCache] = SharedSpriteCache()
