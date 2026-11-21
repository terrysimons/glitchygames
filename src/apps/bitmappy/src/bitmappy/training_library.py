"""Bitmappy's AI training library: the packaged sprites' examples, loaded once, read-only.

Every Bitmappy in the process reads the same library (it is built from the sprite files the package
ships), so it is shared rather than per engine context; it is frozen, so a second Bitmappy, or any
reader, cannot change what another sees. Until ``load_ai_training_data()``
(``bitmappy.sprite_inspection``) installs it, the library is empty, with no format: Bitmappy's
``main()`` loads it before the engine starts, and a second load returns the installed one.

Readers get copies (``examples_as_dicts``): the AI requests that carry examples to the worker
process are pickled and some add fields, which a frozen mapping would refuse.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, SkipValidation

# The format of every example (the sprite files are TOML)
TRAINING_FORMAT = 'toml'


class FrozenList(tuple[Any, ...]):
    """A list from an example, frozen: a tuple that thaws back into a list."""

    __slots__ = ()


def freeze(value: object) -> object:
    """Return a read-only copy of a value made of dicts, lists and scalars.

    Returns:
        Dicts as ``MappingProxyType``, lists as ``FrozenList``, all the way down; anything else
        as it is.

    """
    if isinstance(value, dict):
        mapping = cast('dict[str, object]', value)
        return MappingProxyType({key: freeze(item) for key, item in mapping.items()})
    if isinstance(value, list):
        items = cast('list[object]', value)
        return FrozenList(freeze(item) for item in items)
    return value


def thaw(value: object) -> object:
    """Return a plain, writable copy of a value ``freeze`` made.

    Returns:
        ``MappingProxyType`` as dicts and ``FrozenList`` as lists, all the way down; anything else
        (a tuple the example held as a tuple included) as it is.

    """
    if isinstance(value, MappingProxyType):
        mapping = cast('MappingProxyType[str, object]', value)
        return {key: thaw(item) for key, item in mapping.items()}
    if isinstance(value, FrozenList):
        return [thaw(item) for item in value]
    return value


class TrainingLibrary(BaseModel):
    """The training examples and their format, frozen.

    Build one with ``TrainingLibrary.of(examples=..., training_format=...)``, which freezes each
    example.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    examples: SkipValidation[tuple[MappingProxyType[str, Any], ...]] = ()
    training_format: Literal['toml'] | None = None

    @classmethod
    def of(
        cls, *, examples: list[dict[str, Any]], training_format: Literal['toml'] | None
    ) -> TrainingLibrary:
        """Return a library of read-only copies of ``examples``.

        Returns:
            The library.

        """
        frozen_examples = tuple(
            MappingProxyType({key: freeze(item) for key, item in example.items()})
            for example in examples
        )
        return cls(examples=frozen_examples, training_format=training_format)

    def examples_as_dicts(self) -> list[dict[str, Any]]:
        """Return a plain, writable copy of every example, in order.

        Returns:
            The copies.

        """
        return [{key: thaw(item) for key, item in example.items()} for example in self.examples]


# What readers get before the first load installs a library
EMPTY_TRAINING_LIBRARY = TrainingLibrary()


class _InstalledLibrary:
    """Where the one installed library is kept (None until the first load)."""

    __slots__ = ('library',)

    def __init__(self) -> None:
        self.library: TrainingLibrary | None = None


_INSTALLED = _InstalledLibrary()


def ai_training_library() -> TrainingLibrary:
    """Return the installed training library (empty, with no format, before the first load).

    Returns:
        The library.

    """
    return _INSTALLED.library or EMPTY_TRAINING_LIBRARY


def install_training_library(*, library: TrainingLibrary) -> TrainingLibrary:
    """Install ``library`` unless one is installed already; return the installed one.

    The first load wins, so a second Bitmappy in the process reads the same library and never
    loads it again.

    Returns:
        The installed library.

    """
    if _INSTALLED.library is None:
        _INSTALLED.library = library
    return _INSTALLED.library
