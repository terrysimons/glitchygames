"""Tests for the process cache of compiled sprites (glitchygames/sprites/compiled_sprites.py).

A sprite file's text compiles once per process into read-only frames that every sprite loaded
from the same text shares, as compiled sounds are shared (plans/2026-11-18-shared-sprite-frames.md).
"""

import pygame
import pytest

from glitchygames.sprites.animated import FrameAnchor
from glitchygames.sprites.compiled_sprites import (
    ENGINE_SPRITE_CACHE,
    CompiledSprite,
    SharedSpriteCache,
    sprite_key,
)
from glitchygames.sprites.frame import SpriteFrame


def _compiled(*, byte_count: int, name: str = 'kept') -> CompiledSprite:
    """Return a compiled sprite of one one-frame animation, said to hold byte_count bytes.

    Returns:
        CompiledSprite: The compiled sprite.

    """
    surface = pygame.Surface((2, 2))
    return CompiledSprite(
        name=name,
        description='',
        tags=(),
        default_hitbox=None,
        frame_anchor=FrameAnchor.NONE,
        animations={'idle': (SpriteFrame(surface),)},
        animation_order=('idle',),
        animation_frame_intervals={'idle': 0.5},
        loop_flags={'idle': True},
        animations_without_frame_index=frozenset(),
        game_tables={},
        transition_data=(),
        pixel_row_repairs=(),
        pixel_rows_source='kept.toml',
        color_map={},
        color_order=(),
        drawn_surfaces={('idle', 0): surface},
        byte_count=byte_count,
    )


def test_a_kept_sprite_is_found_by_its_key():
    """What was kept under a key is what that key finds."""
    cache = SharedSpriteCache()
    key = sprite_key(text='[sprite]', source_name='a.toml')
    compiled = _compiled(byte_count=10)

    cache.keep(key=key, compiled=compiled)

    assert cache.compiled(key=key) is compiled
    assert len(cache) == 1


def test_the_same_text_from_another_source_is_another_key():
    """Its repair warnings name its source, so another source compiles anew."""
    assert sprite_key(text='[sprite]', source_name='a.toml') != sprite_key(
        text='[sprite]', source_name='b.toml'
    )


def test_another_text_is_another_key():
    """An edited file is a new key: nothing kept goes stale."""
    assert sprite_key(text='[sprite]', source_name='a.toml') != sprite_key(
        text='[sprite]\n', source_name='a.toml'
    )


def test_a_second_keep_of_a_key_returns_the_first():
    """Two loads compiling one text at once keep one compile, and both get it."""
    cache = SharedSpriteCache()
    key = sprite_key(text='[sprite]', source_name='a.toml')
    first = _compiled(byte_count=10, name='first')

    cache.keep(key=key, compiled=first)
    kept = cache.keep(key=key, compiled=_compiled(byte_count=10, name='second'))

    assert kept is first
    assert cache.compiled(key=key) is first


def test_past_the_limit_the_least_recently_used_go():
    """Reading an entry makes it the most recent; the oldest unread one goes first."""
    cache = SharedSpriteCache()
    cache.limit_bytes = 20
    keys = [sprite_key(text=f'[sprite] {index}', source_name='a.toml') for index in range(3)]
    cache.keep(key=keys[0], compiled=_compiled(byte_count=10))
    cache.keep(key=keys[1], compiled=_compiled(byte_count=10))

    cache.compiled(key=keys[0])
    cache.keep(key=keys[2], compiled=_compiled(byte_count=10))

    assert cache.compiled(key=keys[0]) is not None
    assert cache.compiled(key=keys[1]) is None
    assert cache.compiled(key=keys[2]) is not None


def test_an_entry_larger_than_the_limit_is_still_kept():
    """The entry just compiled stays, as the sound cache keeps the sound it just compiled."""
    cache = SharedSpriteCache()
    cache.limit_bytes = 5
    key = sprite_key(text='[sprite]', source_name='a.toml')

    cache.keep(key=key, compiled=_compiled(byte_count=10))

    assert cache.compiled(key=key) is not None


def test_bytes_held_is_the_sum_of_its_entries():
    """The byte count is what the limit is measured against."""
    cache = SharedSpriteCache()
    cache.keep(key=sprite_key(text='a', source_name='a.toml'), compiled=_compiled(byte_count=7))
    cache.keep(key=sprite_key(text='b', source_name='a.toml'), compiled=_compiled(byte_count=5))

    assert cache.bytes_held == 12


def test_clear_empties_it():
    """The test harness's reset: the next load compiles."""
    cache = SharedSpriteCache()
    key = sprite_key(text='[sprite]', source_name='a.toml')
    cache.keep(key=key, compiled=_compiled(byte_count=10))

    cache.clear()

    assert len(cache) == 0
    assert cache.compiled(key=key) is None
    assert cache.bytes_held == 0


@pytest.mark.parametrize('test_order', ['first', 'second'])
def test_every_test_starts_with_an_empty_engine_sprite_cache(test_order):
    """The harness empties the process cache around each test, so tests stay independent."""
    assert len(ENGINE_SPRITE_CACHE) == 0

    ENGINE_SPRITE_CACHE.keep(
        key=sprite_key(text='[sprite]', source_name='order.toml'),
        compiled=_compiled(byte_count=10),
    )

    assert len(ENGINE_SPRITE_CACHE) == 1, test_order
