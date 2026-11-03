"""Sprite tags: a plain list of words saying what kind of thing a sprite is.

A sprite file may name its tags in ``[sprite]``, after its description::

    [sprite]
    name = 'Sword'
    tags = ['item', 'weapon', 'sword']

They are for fuzzy search (``glitchygames.sprites.catalog``) and for handing sprites to an LLM or
a vector store. Tags are free-form, one list per sprite (plans/2026-11-02-sprite-tags.md). Each is
kept in one spelling, so matching never depends on how it was typed: stripped, case-folded, runs
of whitespace made one space; an empty tag and a repeat (after that) are dropped, keeping the
first, and the order is kept. Plurals are not merged.
"""

from __future__ import annotations

import logging
from typing import cast

log = logging.getLogger('game.sprites.tags')

# The [sprite] key holding a sprite's tags
TAGS_KEY = 'tags'


def normalize_sprite_tags(raw_tags: object) -> list[str]:
    """Return a file's tags in their one spelling, skipping (and logging) what is not a tag.

    Args:
        raw_tags: The ``[sprite] tags`` value as read (None when the file names none).

    Returns:
        The tags: each stripped, case-folded and single-spaced; empties and repeats dropped,
        the order kept.

    """
    if raw_tags is None:
        return []
    if not isinstance(raw_tags, list):
        log.warning('Sprite tags must be an array of strings; skipping %r', raw_tags)
        return []
    tags: list[str] = []
    for raw_tag in cast('list[object]', raw_tags):
        if not isinstance(raw_tag, str):
            log.warning('Skipping a sprite tag that is not a string: %r', raw_tag)
            continue
        tag = ' '.join(raw_tag.casefold().split())
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def sprite_tags_problems(raw_tags: object) -> list[str]:
    """Return what is wrong with a file's ``tags`` value (nothing for none or well-formed tags).

    Args:
        raw_tags: The ``[sprite] tags`` value as read (None when the file names none).

    Returns:
        One message per problem.

    """
    if raw_tags is None:
        return []
    if not isinstance(raw_tags, list):
        return [f'tags must be an array of strings, not {raw_tags!r}']
    return [
        f'tag {position} is not a string: {raw_tag!r}'
        for position, raw_tag in enumerate(cast('list[object]', raw_tags), start=1)
        if not isinstance(raw_tag, str)
    ]
