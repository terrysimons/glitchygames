"""A sprite loaded from text: the engine's side of ``sprite_toml``.

``sprite_toml`` turns a sprite file's text into data and back without pygame; this module turns
the text into the sprite the engine draws. It is the one path a sprite loads by:
``AnimatedSprite._load_toml`` reads a file's text and calls the same ``AnimatedSprite.load_text``
that ``sprite_from_text`` calls, so a sprite from text and from a file are the same sprite. No
temporary file is involved.
"""

from __future__ import annotations

from .animated import AnimatedSprite


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
