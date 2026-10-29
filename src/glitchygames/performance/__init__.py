"""Performance management for glitchygames.

``performance_manager`` is a read-only module view (glitchygames.read_only_views): each read
answers ``AdaptiveClamping()``, the current engine context's manager, and writing it raises.
Engine code calls ``AdaptiveClamping()`` itself; a module-level
``from glitchygames.performance import performance_manager`` would bind the importing module to
the default context's manager for good (tests/test_engine_context_source_guards.py refuses it).
"""

from __future__ import annotations

import sys
import types
from typing import TYPE_CHECKING, override

from glitchygames.read_only_views import ReadOnlyViewError

from .adaptive_clamping import AdaptiveClamping

if TYPE_CHECKING:
    # For the type checkers: at run time __getattr__ answers it (the module view)
    performance_manager: AdaptiveClamping

__all__ = ['AdaptiveClamping', 'performance_manager']

# The module's read-only views, answered by __getattr__ (glitchygames.read_only_views)
READ_ONLY_MODULE_VIEWS = frozenset({'performance_manager'})
# What to do instead of writing a view, for the refusal
WRITE_INSTEAD = "nothing: AdaptiveClamping() is the current context's manager; patch its methods"


def __getattr__(name: str) -> AdaptiveClamping:
    """Answer the module view: ``performance_manager`` is the current context's manager.

    Args:
        name: The attribute's name.

    Returns:
        ``AdaptiveClamping()`` for ``performance_manager``.

    Raises:
        AttributeError: For any other name.

    """
    if name == 'performance_manager':
        return AdaptiveClamping()
    message = f'module {__name__!r} has no attribute {name!r}'
    raise AttributeError(message)


def __dir__() -> list[str]:
    """List the module's names, its views included.

    Returns:
        The names, sorted.

    """
    return sorted({*globals(), *READ_ONLY_MODULE_VIEWS})


def _refusal(*, name: str) -> str:
    """Return the message a write of a view raises with (worded as glitchygames.read_only_views).

    Args:
        name: The view's name.

    Returns:
        The message.

    """
    return f'{__name__}.{name} is a read-only view of the current game; write {WRITE_INSTEAD}'


class ReadOnlyViewsModule(types.ModuleType):
    """This package's module class: it refuses writes and deletes of the module's views."""

    @override
    def __setattr__(self, name: str, value: object) -> None:
        """Refuse writing a view; set any other attribute.

        Args:
            name: The attribute's name.
            value: The value.

        Raises:
            ReadOnlyViewError: If the name is a view's.

        """
        if name in READ_ONLY_MODULE_VIEWS:
            raise ReadOnlyViewError(_refusal(name=name))
        super().__setattr__(name, value)

    @override
    def __delattr__(self, name: str) -> None:
        """Refuse deleting a view; delete any other attribute.

        Args:
            name: The attribute's name.

        Raises:
            ReadOnlyViewError: If the name is a view's.

        """
        if name in READ_ONLY_MODULE_VIEWS:
            raise ReadOnlyViewError(_refusal(name=name))
        super().__delattr__(name)


sys.modules[__name__].__class__ = ReadOnlyViewsModule
