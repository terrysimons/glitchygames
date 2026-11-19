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
from typing import Any, Final

import pygame  # ruff: ignore[typing-only-third-party-import] - pydantic resolves CompiledSprite's surfaces and rects at runtime
from pydantic import BaseModel, ConfigDict

from glitchygames.sprites.animated import FrameAnchor  # ruff: ignore[typing-only-first-party-import] - pydantic resolves CompiledSprite.frame_anchor at runtime
from glitchygames.sprites.frame import SpriteFrame  # ruff: ignore[typing-only-first-party-import] - pydantic resolves CompiledSprite.animations at runtime

# Past this many bytes of compiled frames, the least recently used compiles are dropped
DEFAULT_SPRITE_CACHE_LIMIT_BYTES: Final = 64 * 1024 * 1024

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
    animations: dict[str, tuple[SpriteFrame, ...]]
    animation_order: tuple[str, ...]
    animation_frame_intervals: dict[str, float]
    loop_flags: dict[str, bool]
    animations_without_frame_index: frozenset[str]
    game_tables: dict[str, Any]
    transition_data: tuple[dict[str, Any], ...]
    pixel_row_repairs: tuple[str, ...]
    pixel_rows_source: str
    color_map: dict[str, tuple[int, ...]]
    color_order: tuple[str, ...]
    drawn_surfaces: dict[tuple[str, int], pygame.Surface]
    byte_count: int


class SharedSpriteCache:
    """The process's compiled sprites by key, shared by every engine context.

    Reads and keeps take one lock, held only for the lookup or the store: a compile runs outside
    it, so two loads of one text at once may both compile, and ``keep`` gives both the first.
    ``clear`` exists for the test harness, which starts every test with an empty cache.
    """

    def __init__(self) -> None:
        """Start empty."""
        self._compiled: OrderedDict[SpriteKey, CompiledSprite] = OrderedDict()
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
            self._evict_past_the_limit(keep=key)
            return compiled

    def clear(self) -> None:
        """Forget every compile (the test harness's reset; the next load compiles)."""
        with self._lock:
            self._compiled.clear()

    def _evict_past_the_limit(self, *, keep: SpriteKey) -> None:
        """Drop the least recently used compiles, never keep, until the rest fit the limit."""
        held = sum(compiled.byte_count for compiled in self._compiled.values())
        for key in list(self._compiled):
            if held <= self.limit_bytes:
                return
            if key == keep:
                continue
            held -= self._compiled.pop(key).byte_count


# The process's one cache of compiled sprites (SharedSpriteCache)
ENGINE_SPRITE_CACHE: Final[SharedSpriteCache] = SharedSpriteCache()
