"""The assembled catalog and its lookups (re-exported by ``glitchygames.audio.instruments``)."""

from __future__ import annotations

import dataclasses
import difflib
import functools
import inspect
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, cast

from glitchygames.audio.instruments.aliases import ALIASES
from glitchygames.audio.instruments.bagpipes import BAGPIPES
from glitchygames.audio.instruments.bowed_strings import BOWED_STRINGS
from glitchygames.audio.instruments.brass import BRASS
from glitchygames.audio.instruments.catalog import ENTRY_NAME_PATTERN, CatalogEntry, Family, Tag
from glitchygames.audio.instruments.clarinets import CLARINETS
from glitchygames.audio.instruments.double_reeds import DOUBLE_REEDS
from glitchygames.audio.instruments.drums import DRUMS_AND_PERCUSSION
from glitchygames.audio.instruments.electromechanical import ELECTROMECHANICAL
from glitchygames.audio.instruments.electronic import ELECTRONIC
from glitchygames.audio.instruments.flutes import FLUTES
from glitchygames.audio.instruments.free_reeds import FREE_REEDS
from glitchygames.audio.instruments.harps import HARPS
from glitchygames.audio.instruments.idiophones import FRICTION_INSTRUMENTS, PLUCKED_IDIOPHONES
from glitchygames.audio.instruments.keyboards import KEYBOARDS
from glitchygames.audio.instruments.noise_makers import NOISE_MAKERS
from glitchygames.audio.instruments.organs import ORGANS
from glitchygames.audio.instruments.percussion import TUNED_PERCUSSION
from glitchygames.audio.instruments.plucked_strings import PLUCKED_STRINGS
from glitchygames.audio.instruments.saxophones import SAXOPHONES
from glitchygames.audio.instruments.sound_effects import SOUND_EFFECTS
from glitchygames.audio.instruments.struck_strings import STRUCK_STRINGS
from glitchygames.audio.instruments.voices import CHOIRS, VOICES

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from glitchygames.audio.instrument import Instrument

SUGGESTION_COUNT: Final[int] = 3


FAMILY_TABLES: Final[tuple[tuple[CatalogEntry, ...], ...]] = (
    FLUTES,
    CLARINETS,
    SAXOPHONES,
    DOUBLE_REEDS,
    BAGPIPES,
    FREE_REEDS,
    BRASS,
    BOWED_STRINGS,
    PLUCKED_STRINGS,
    HARPS,
    STRUCK_STRINGS,
    KEYBOARDS,
    ORGANS,
    ELECTROMECHANICAL,
    ELECTRONIC,
    TUNED_PERCUSSION,
    PLUCKED_IDIOPHONES,
    FRICTION_INSTRUMENTS,
    DRUMS_AND_PERCUSSION,
    NOISE_MAKERS,
    SOUND_EFFECTS,
    VOICES,
    CHOIRS,
)


def catalog_from(tables: Sequence[Sequence[CatalogEntry]]) -> dict[str, CatalogEntry]:
    """The catalog: every table's entries by name, in table order.

    Args:
        tables: The family tables.

    Returns:
        Name to entry.

    Raises:
        ValueError: When two entries share a name.
    """
    catalog: dict[str, CatalogEntry] = {}
    for table in tables:
        for catalog_entry in table:
            if catalog_entry.name in catalog:
                message = f'the catalog names {catalog_entry.name!r} twice'
                raise ValueError(message)
            catalog[catalog_entry.name] = catalog_entry
    return catalog


def _keyword_parameters(builder: functools.partial[Instrument]) -> frozenset[str]:
    """The parameters a keyword may replace in ``builder``.

    They are its function's keyword parameters that its positional arguments do not already fill.

    Returns:
        The parameter names.
    """
    parameters = list(inspect.signature(builder.func).parameters.values())
    keyword_kinds = {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}
    filled_positionally = {parameter.name for parameter in parameters[: len(builder.args)]}
    return frozenset(
        parameter.name
        for parameter in parameters
        if parameter.kind in keyword_kinds and parameter.name not in filled_positionally
    )


def _sound_alike_build(
    catalog_entry: CatalogEntry, parent: CatalogEntry
) -> Callable[[], Instrument]:
    """The parent's builder, with the sound-alike's ``sound_changes`` replacing its keywords.

    Returns:
        The builder.

    Raises:
        ValueError: When there are changes and the parent's builder is not a
            ``functools.partial``, or a change names no keyword parameter of its function.
    """
    # The catalog's assembly has checked that the parent is no sound-alike, so it has a build
    parent_build = cast('Callable[[], Instrument]', parent.build)
    if not catalog_entry.sound_changes:
        return parent_build
    if not isinstance(parent_build, functools.partial):
        message = (
            f'{catalog_entry.name}: sound changes need a functools.partial builder, and '
            f'{parent.name!r} has none'
        )
        raise ValueError(message)  # ruff: ignore[type-check-without-type-error] - a catalog refusal
    builder = cast('functools.partial[Instrument]', parent_build)
    unknown = sorted(set(catalog_entry.sound_changes) - _keyword_parameters(builder))
    if unknown:
        message = (
            f'{catalog_entry.name}: sound changes {unknown} are not keyword parameters of '
            f"{parent.name!r}'s builder"
        )
        raise ValueError(message)
    return functools.partial(
        builder.func, *builder.args, **{**builder.keywords, **catalog_entry.sound_changes}
    )


def sound_alikes_from(catalog: Mapping[str, CatalogEntry]) -> dict[str, CatalogEntry]:
    """The catalog with every sound-alike given its build, checked against its parent.

    A sound-alike (an entry with ``sounds_like``) builds its parent's instrument, with its
    ``sound_changes`` replacing the parent builder's keywords.

    Args:
        catalog: Name to entry, as ``catalog_from`` assembles it.

    Returns:
        Name to entry, in the same order, each sound-alike carrying its build.

    Raises:
        ValueError: Naming the entry, when sound changes come without ``sounds_like``, or a
            sound-alike has its own build, sounds like itself, an entry that is not in the
            catalog or another sound-alike, is pitched when its parent is not (or the reverse),
            or carries changes its parent's builder cannot take.
    """
    assembled: dict[str, CatalogEntry] = {}
    for name, catalog_entry in catalog.items():
        parent_name = catalog_entry.sounds_like
        if parent_name is None:
            if catalog_entry.sound_changes:
                message = f'{name}: sound changes need the entry it sounds like'
                raise ValueError(message)
            assembled[name] = catalog_entry
            continue
        if catalog_entry.build is not None:
            message = f'{name}: a sound-alike takes the build of {parent_name!r}, not its own'
            raise ValueError(message)
        if parent_name == name:
            message = f'{name}: sounds like itself'
            raise ValueError(message)
        parent = catalog.get(parent_name)
        if parent is None:
            message = f'{name}: sounds like no instrument: {parent_name!r}'
            raise ValueError(message)
        if parent.sounds_like is not None:
            message = f'{name}: sounds like {parent_name!r}, itself a sound-alike'
            raise ValueError(message)
        # Decision 8 (plans/2026-11-07-instrument-catalog-expansion-design.md), extended by
        # plans/2026-11-09-instrument-catalog-batch-4-implementation.md: a pitched sound-alike
        # gives its own sourced range, but pitched-ness comes from the parent's build
        if catalog_entry.pitched != parent.pitched:
            message = f'{name}: pitched exactly when {parent_name!r} is'
            raise ValueError(message)
        assembled[name] = dataclasses.replace(
            catalog_entry, build=_sound_alike_build(catalog_entry, parent)
        )
    return assembled


# Read-only views: a caller writing into either would skip catalog_from's, sound_alikes_from's and
# aliases_from's checks and change what every lookup answers
CATALOG: Final[Mapping[str, CatalogEntry]] = MappingProxyType(
    sound_alikes_from(catalog_from(FAMILY_TABLES))
)


def aliases_from(table: Mapping[str, str], catalog: Mapping[str, CatalogEntry]) -> dict[str, str]:
    """The alias table, checked against the catalog.

    Args:
        table: Alias to catalog name.
        catalog: The catalog the targets must belong to.

    Returns:
        A copy of the table.

    Raises:
        ValueError: When an alias is not lower-case words separated by single spaces, is itself
            a catalog name, or names a target that is not a catalog name.
    """
    for alias, target in table.items():
        if ENTRY_NAME_PATTERN.fullmatch(alias) is None:
            message = f'alias {alias!r} must be lower-case words separated by single spaces'
            raise ValueError(message)
        if alias in catalog:
            message = f'alias {alias!r} is a catalog name'
            raise ValueError(message)
        if target not in catalog:
            message = f'alias {alias!r} names no instrument: {target!r}'
            raise ValueError(message)
    return dict(table)


ALIAS_TABLE: Final[Mapping[str, str]] = MappingProxyType(aliases_from(ALIASES, CATALOG))


def entry(name: str) -> CatalogEntry:
    """The catalog entry named ``name``, in any case.

    Args:
        name: A catalog name or an alias, e.g. ``'tenor saxophone'`` or ``'slapstick'``
            (``'Tenor Saxophone'`` finds it too: the name is lowercased first).

    Returns:
        The entry.

    Raises:
        KeyError: When no instrument has that name (the message suggests close names).
    """
    lowered = name.lower()
    try:
        return CATALOG[ALIAS_TABLE.get(lowered, lowered)]
    except KeyError:
        # Suggestions come from catalog names and aliases together.
        close = difflib.get_close_matches(lowered, [*CATALOG, *ALIAS_TABLE], n=SUGGESTION_COUNT)
        hint = f'; did you mean {", ".join(close)}?' if close else ''
        message = f'no instrument named {name!r} in the catalog{hint}'
        raise KeyError(message) from None


def get(name: str) -> Instrument:
    """The catalog instrument named ``name``, in any case, built on first use and kept.

    Args:
        name: A catalog name or an alias, e.g. ``'violin'`` (``'Violin'`` is the same
            instrument: the name is resolved to its catalog name before the cache, so every
            spelling and every alias shares one build).

    Returns:
        The instrument.

    An unknown name raises ``entry``'s KeyError.
    """
    # An unknown name fails here, quoted as the caller spelled it; an alias resolves to its
    # target's name, so both share one cache slot.
    return _built(entry(name).name)


@functools.cache
def _built(name: str) -> Instrument:
    build = entry(name).build
    if build is None:  # pragma: no cover - sound_alikes_from gives every sound-alike a build
        message = f'{name}: no build'
        raise ValueError(message)
    return build()


def _family(family: Family | str | None) -> Family | None:
    """``family`` as a Family, lowercased first when it is a string (None stays None).

    Returns:
        The family, or None. A string that names no family raises Family's ValueError.
    """
    if family is None:
        return None
    return Family(family.lower())


def _tag(tag: Tag | str | None) -> Tag | None:
    """``tag`` as a Tag, lowercased first when it is a string (None stays None).

    Returns:
        The tag, or None. A string that names no tag raises Tag's ValueError.
    """
    if tag is None:
        return None
    return Tag(tag.lower())


def names(*, family: Family | str | None = None, tag: Tag | str | None = None) -> tuple[str, ...]:
    """Every catalog name, in catalog order, or only one family's and/or one tag's.

    Args:
        family: A family, its name in any case (``'Double Reeds'``), or None for all.
        tag: A tag, its name in any case (``'Mechanical'``), or None for all.

    Returns:
        The names.

    An unknown family or tag name raises ``ValueError``.
    """
    wanted_family = _family(family)
    wanted_tag = _tag(tag)
    return tuple(
        name
        for name, value in CATALOG.items()
        if (wanted_family is None or value.family == wanted_family)
        and (wanted_tag is None or wanted_tag in value.tags)
    )


def entries(
    *, family: Family | str | None = None, tag: Tag | str | None = None
) -> tuple[CatalogEntry, ...]:
    """Every catalog entry, in catalog order, or only one family's and/or one tag's.

    Args:
        family: A family, its name in any case (``'Double Reeds'``), or None for all.
        tag: A tag, its name in any case (``'Mechanical'``), or None for all.

    Returns:
        The entries.
    """
    return tuple(CATALOG[name] for name in names(family=family, tag=tag))


def families() -> tuple[Family, ...]:
    """The families, in catalog order.

    Returns:
        The families.
    """
    return tuple(Family)
