"""The assembled catalog and its lookups (re-exported by ``glitchygames.audio.instruments``)."""

from __future__ import annotations

import difflib
import functools
from typing import TYPE_CHECKING, Final

from glitchygames.audio.instruments.aliases import ALIASES
from glitchygames.audio.instruments.brass import BRASS
from glitchygames.audio.instruments.catalog import ENTRY_NAME_PATTERN, CatalogEntry, Family, Tag
from glitchygames.audio.instruments.idiophones import PLUCKED_IDIOPHONES
from glitchygames.audio.instruments.keyboards import ELECTRONIC, KEYBOARDS, ORGANS
from glitchygames.audio.instruments.percussion import DRUMS_AND_PERCUSSION, TUNED_PERCUSSION
from glitchygames.audio.instruments.strings import (
    BOWED_STRINGS,
    HARPS,
    PLUCKED_STRINGS,
    STRUCK_STRINGS,
)
from glitchygames.audio.instruments.voices import CHOIRS, VOICES
from glitchygames.audio.instruments.winds import (
    BAGPIPES,
    CLARINETS,
    DOUBLE_REEDS,
    FLUTES,
    FREE_REEDS,
    SAXOPHONES,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

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
    ELECTRONIC,
    TUNED_PERCUSSION,
    PLUCKED_IDIOPHONES,
    DRUMS_AND_PERCUSSION,
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


CATALOG: Final[dict[str, CatalogEntry]] = catalog_from(FAMILY_TABLES)


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
        if ENTRY_NAME_PATTERN.match(alias) is None:
            message = f'alias {alias!r} must be lower-case words separated by single spaces'
            raise ValueError(message)
        if alias in catalog:
            message = f'alias {alias!r} is a catalog name'
            raise ValueError(message)
        if target not in catalog:
            message = f'alias {alias!r} names no instrument: {target!r}'
            raise ValueError(message)
    return dict(table)


ALIAS_TABLE: Final[dict[str, str]] = aliases_from(ALIASES, CATALOG)


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
    return entry(name).build()


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
