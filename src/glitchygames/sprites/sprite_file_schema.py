"""The sprite file schema: every value a sprite file holds, checked once, at load.

A sprite file's values were trusted as written: a ``frame_interval`` of text loaded without a word
and crashed the game on its first frame, in ``AnimatedSprite.update`` (reproduced 2026-11-17).
The loaders now pass the parsed file through ``validate_sprite_file`` first, so a bad value fails
at load, naming the file and the field. It is pygame-free on purpose:
plans/2026-11-17-sprite-generation-in-the-ai-service.md moves it into the
``glitchygames-sprite-format`` package, so the engine's loader and the AI service accept exactly the
same files.

Rules:

1. Values are checked strictly: text is never a number, a boolean never a number, and a number
   never text.
2. ``frame_interval`` is a positive number of seconds (``0.25`` is a quarter of a second), on an
   animation or a frame. Color channels and alpha are whole numbers from 0 to 255. A hitbox's
   width and height are whole numbers from 0, its offsets whole numbers. A frame index is a whole
   number from 0. ``loop`` is a boolean. ``tags`` is a list of text.
3. Inside the sections the engine reads (``[sprite]``, each ``[[animation]]`` and its frames, each
   color, each hitbox, each ``[[transition]]``) an unknown key is refused, so a misspelling fails
   at load. A top-level table the engine does not read is kept: games keep data of their own
   beside the sprite (Drawing Fire's ``swatches``).
4. Only types and ranges are checked here. The pixel rows and their glyphs keep their own rules
   (``pixel_utils.normalize_pixel_rows`` repairs rows, ``palette_key_problems`` reports keys),
   and a ``frame_anchor``'s name is checked by the loader that knows the anchors.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

# Whole numbers from 0 to 255: a color channel or an alpha
ColorValue = Annotated[int, Field(ge=0, le=255)]
# A positive number of seconds
Seconds = Annotated[float, Field(gt=0)]
WholeNumberFromZero = Annotated[int, Field(ge=0)]


class _Section(BaseModel):
    """A section the engine reads: strict values, no unknown keys (rules 1 and 3)."""

    model_config = ConfigDict(frozen=True, extra='forbid', strict=True)


class Hitbox(_Section):
    """A ``hitbox`` table, on the sprite or a frame."""

    offset_x: int = 0
    offset_y: int = 0
    width: WholeNumberFromZero = 0
    height: WholeNumberFromZero = 0


class Color(_Section):
    """One glyph's color in ``[colors]``; a missing channel is 0, as the loader reads it."""

    red: ColorValue = 0
    green: ColorValue = 0
    blue: ColorValue = 0
    alpha: ColorValue | None = None


class Frame(_Section):
    """One ``[[animation.frame]]``."""

    namespace: str | None = None
    frame_index: WholeNumberFromZero | None = None
    frame_interval: Seconds | None = None
    pixels: str | None = None
    hitbox: Hitbox | None = None


class Animation(_Section):
    """One ``[[animation]]``."""

    namespace: str | None = None
    frame_interval: Seconds | None = None
    loop: bool | None = None
    frame: list[Frame] = Field(default_factory=list)


class Transition(_Section):
    """One ``[[transition]]``: from one animation to another, on a condition."""

    from_animation: str | None = Field(default=None, alias='from')
    to: str | None = None
    when: str | None = None


class Sprite(_Section):
    """The ``[sprite]`` table."""

    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    frame_anchor: str | None = None
    pixels: str | None = None
    hitbox: Hitbox | None = None


class SpriteFile(BaseModel):
    """A whole sprite file. Top-level tables the engine does not read are kept (rule 3)."""

    model_config = ConfigDict(frozen=True, extra='allow', strict=True)

    sprite: Sprite | None = None
    animation: list[Animation] = Field(default_factory=list)
    transition: list[Transition] = Field(default_factory=list)
    colors: dict[str, Color] = Field(default_factory=dict)


class SpriteFileError(ValueError):
    """A sprite file holds a value of the wrong type or range, or an unknown key."""


def validate_sprite_file(*, data: dict[str, Any], source_name: str) -> SpriteFile:
    """Check a parsed sprite file's values (rules 1 to 4).

    Args:
        data: The file as ``tomllib`` read it.
        source_name: The file, for the error (its path or name).

    Returns:
        The checked file.

    Raises:
        SpriteFileError: Naming the file and each field that is wrong, and why.
    """
    try:
        return SpriteFile.model_validate(data)
    except ValidationError as error:
        problems = '; '.join(
            f'{".".join(str(part) for part in detail["loc"])}: {detail["msg"]}'
            for detail in error.errors()
        )
        message = f'{source_name}: {problems}'
        raise SpriteFileError(message) from error
