"""Swatches: recolouring a sprite by palette swap.

A sprite file lists swatch sets beside its palette. A set names parts of the sprite (a helmet, a
uniform), and each part lists palette characters: the first is the part's base colour, the rest
are shades of it (a shadow) that keep their brightness ratio when the part is recoloured.

    [swatches.livery.helmet]
    colors = ["h", "H"]
    role = "primary"

A Scheme gives colours to parts by name or by role, and recolor_surface() swaps them in. Nothing
here names a game: it is written to move into the engine.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from glitchygames.sprites.animated import AnimatedSprite
from glitchygames.sprites.pixel_utils import is_color_transparent

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

type Color = tuple[int, int, int]

MAX_CHANNEL_VALUE = 255
ROLE_PRIMARY = 'primary'
ROLE_SECONDARY = 'secondary'


class SwatchError(Exception):
    """A sprite file's swatches are wrong; the message names the file and the part."""


@dataclass(frozen=True)
class SwatchPart:
    """One recolourable part of a sprite.

    Attributes:
        name: The part's name (for example 'helmet').
        colors: The RGB of each listed palette character, in the file's order: the base colour,
            then its shades.
        role: What the part is for ('primary', 'secondary'), or None for a part with no role.

    """

    name: str
    colors: tuple[Color, ...]
    role: str | None


@dataclass(frozen=True)
class SwatchSet:
    """A named set of parts (for example a 'livery') that are recoloured together."""

    name: str
    parts: tuple[SwatchPart, ...]


@dataclass(frozen=True)
class Scheme:
    """The colours to give a swatch set: by role, with named parts overriding their role.

    Attributes:
        primary: The colour for parts whose role is 'primary'.
        secondary: The colour for parts whose role is 'secondary'.
        parts: Colours by part name; a part's own colour wins over its role's. Given as a
            mapping, kept as a tuple of (name, colour) pairs sorted by name, so a Scheme is
            hashable (the cache keys on it) and equal mappings give equal Schemes.

    """

    primary: Color | None = None
    secondary: Color | None = None
    parts: Mapping[str, Color] | tuple[tuple[str, Color], ...] = field(default=())

    def __post_init__(self) -> None:
        """Store the parts as sorted (name, colour) pairs, so the Scheme can be hashed."""
        pairs = self.parts if isinstance(self.parts, tuple) else self.parts.items()
        # frozen=True forbids assignment, so the normalized value goes through object.__setattr__
        object.__setattr__(self, 'parts', tuple(sorted(pairs)))

    def color_for(self, part: SwatchPart) -> Color | None:
        """Find the colour for a part: its own, else its role's, else none.

        Args:
            part: The part to colour.

        Returns:
            The new base colour, or None when the scheme gives the part none.

        """
        part_color = dict(self.parts).get(part.name)
        if part_color is not None:
            return part_color
        if part.role == ROLE_PRIMARY:
            return self.primary
        if part.role == ROLE_SECONDARY:
            return self.secondary
        return None


def load_swatch_sets(*, path: Path) -> dict[str, SwatchSet]:
    """Read a sprite file's swatch sets, with each part's colours looked up in its palette.

    Args:
        path: The sprite's TOML file.

    Returns:
        The swatch sets by name (empty when the file has no [swatches]).

    Raises:
        SwatchError: A part lists a character that is not in [colors], a part has no colours, or
            a character is in two parts of one set.

    """
    with path.open('rb') as sprite_file:
        document = tomllib.load(sprite_file)
    palette: dict[str, Color] = {
        character: (entry['red'], entry['green'], entry['blue'])
        for character, entry in document.get('colors', {}).items()
    }

    swatch_sets: dict[str, SwatchSet] = {}
    for set_name, part_tables in document.get('swatches', {}).items():
        character_owner: dict[str, str] = {}
        parts: list[SwatchPart] = []
        for part_name, part_table in part_tables.items():
            characters = part_table.get('colors', [])
            if not characters:
                message = f'{path}: swatch {set_name}.{part_name} has no colours'
                raise SwatchError(message)
            for character in characters:
                if character not in palette:
                    message = (
                        f'{path}: swatch {set_name}.{part_name} lists {character!r}, '
                        'which is not in [colors]'
                    )
                    raise SwatchError(message)
                owner = character_owner.setdefault(character, part_name)
                if owner != part_name:
                    message = (
                        f'{path}: swatch {set_name} lists {character!r} in both '
                        f'{owner} and {part_name}'
                    )
                    raise SwatchError(message)
            parts.append(
                SwatchPart(
                    name=part_name,
                    colors=tuple(palette[character] for character in characters),
                    role=part_table.get('role'),
                ),
            )
        swatch_sets[set_name] = SwatchSet(name=set_name, parts=tuple(parts))
    return swatch_sets


def load_frames(*, path: Path) -> dict[str, tuple[pygame.Surface, ...]]:
    """Load a sprite file's animations as surfaces, with the engine's own sprite loader.

    Args:
        path: The sprite's TOML file.

    Returns:
        Each animation's frame surfaces, by animation namespace.

    """
    sprite = AnimatedSprite(filename=str(path))
    return {
        namespace: tuple(_with_transparency(frame.image) for frame in animation_frames)
        for namespace, animation_frames in sprite.animations.items()
    }


def _with_transparency(image: pygame.Surface) -> pygame.Surface:
    """Copy a loaded frame with its transparent pixels (magenta, or alpha 0) at alpha 0.

    The engine's loader leaves magenta pixels opaque in a frame's image; the engine knows to
    skip them, but a plain blit would draw them, so they are cleared here.

    Returns:
        A per-pixel alpha copy that blits with its transparency.

    """
    cleared = pygame.Surface(image.get_size(), pygame.SRCALPHA)
    for x in range(image.get_width()):
        for y in range(image.get_height()):
            pixel = tuple(image.get_at((x, y)))
            if not is_color_transparent(pixel):
                cleared.set_at((x, y), pixel)
    return cleared


def shade_map(*, part: SwatchPart, color: Color) -> dict[Color, Color]:
    """Map a part's colours to its new ones: the first becomes color, the others keep their ratio.

    Each shade is scaled per channel by new base / old base, rounded and clamped to 0..255. A
    base channel of 0 has no ratio, so the shade takes the new colour's channel as it is. A
    colour listed twice maps once, to what its first listing gets.

    Args:
        part: The part being recoloured.
        color: The part's new base colour.

    Returns:
        Each old colour of the part and the colour that replaces it.

    """
    base = part.colors[0]
    mapping: dict[Color, Color] = {base: color}
    for shade in part.colors[1:]:
        recolored = tuple(
            new_channel
            if base_channel == 0
            else min(MAX_CHANNEL_VALUE, max(0, round(shade_channel * new_channel / base_channel)))
            for shade_channel, base_channel, new_channel in zip(shade, base, color, strict=True)
        )
        mapping.setdefault(shade, (recolored[0], recolored[1], recolored[2]))
    return mapping


def recolor_surface(
    *,
    surface: pygame.Surface,
    swatch_set: SwatchSet,
    scheme: Scheme,
) -> pygame.Surface:
    """Recolour a surface: a new one with the scheme's colours swapped in for the parts' own.

    Pixels are replaced by exact RGB. Alpha and the colorkey are kept, pixels that are
    transparent (alpha 0, or the colorkey) are never replaced, and parts the scheme gives no
    colour stay as drawn.

    Args:
        surface: The surface as drawn.
        swatch_set: The parts to recolour.
        scheme: The colours to give them.

    Returns:
        The recoloured copy.

    """
    replacements: dict[Color, Color] = {}
    for part in swatch_set.parts:
        color = scheme.color_for(part)
        if color is not None:
            replacements.update(shade_map(part=part, color=color))

    recolored = surface.copy()
    colorkey = surface.get_colorkey()
    keyed_color = tuple(colorkey)[:3] if colorkey is not None else None
    for x in range(surface.get_width()):
        for y in range(surface.get_height()):
            red, green, blue, alpha = surface.get_at((x, y))
            if alpha == 0 or (red, green, blue) == keyed_color:
                continue
            replacement = replacements.get((red, green, blue))
            if replacement is not None:
                recolored.set_at((x, y), (*replacement, alpha))
    return recolored


class RecoloredFrames:
    """A sprite's animation frames in any scheme's colours, each scheme built once."""

    def __init__(
        self,
        *,
        frames: Mapping[str, Sequence[pygame.Surface]],
        swatch_set: SwatchSet,
    ) -> None:
        """Hold the frames as drawn.

        Args:
            frames: The frame surfaces by animation namespace.
            swatch_set: The parts to recolour.

        """
        self._frames = frames
        self._swatch_set = swatch_set
        self._built: dict[Scheme, Mapping[str, tuple[pygame.Surface, ...]]] = {}

    def frames_for(self, scheme: Scheme) -> Mapping[str, tuple[pygame.Surface, ...]]:
        """Get the frames in a scheme's colours: built on first use, then the same surfaces.

        Args:
            scheme: The colours to give the swatch set.

        Returns:
            The recoloured frame surfaces by animation namespace.

        """
        if scheme not in self._built:
            self._built[scheme] = {
                namespace: tuple(
                    recolor_surface(surface=surface, swatch_set=self._swatch_set, scheme=scheme)
                    for surface in surfaces
                )
                for namespace, surfaces in self._frames.items()
            }
        return self._built[scheme]
