"""The engine context: the state one running game owns, so several can run in one process.

plans/2026-10-25-engine-context.md is the design (the audit of every piece of process-wide
state, the shared resources, the sub-plans). Rules:

1. Per-context state is declared where it is used, as a ``ContextSlot`` (a unique dotted name
   and a factory), once, at module level::

       ENGINE_RANDOM_STATE_SLOT = ContextSlot(
           name='glitchygames.randomness.streams', factory=EngineRandomState
       )

   A second slot of the same name is refused (``DuplicateContextSlotError``).
2. Code reads a slot when it needs it, ``current_context().value(slot=...)``, never as its
   module is imported (at module level, in a class body or in a default argument): a value read
   then would be the default context's for every context. tests/test_engine_context.py scans
   the engine and every workspace member for such reads.
3. A context makes each slot's value with the slot's factory the first time it is read there,
   so a new context starts as a fresh process would. ``reset_value`` makes a fresh one.
4. ``current_context()`` is the context switched to last in this thread or asyncio task, else
   the default context. Ordinary games and every test run in the default context and never
   switch.
5. ``with context.active():`` makes the context current and puts back the one that was current
   when the block began, when it ends normally or by an exception (which propagates). Switches
   nest. The current context is a ``contextvars.ContextVar``: an asyncio task made inside a
   switch keeps that context (asyncio copies the context into a task as it makes it), and a
   switch held across an ``await`` is never seen by another task. A ``threading.Thread`` sees
   the context current where it is started only when started with
   ``context=contextvars.copy_context()`` (or on an interpreter whose
   ``sys.flags.thread_inherit_context`` is set); otherwise it sees the default context.
6. A context owns only what its slots hold. Objects are not bound to a context (a stream, a set
   of doors, a scene keeps its own state wherever it is used); only the module-level lookups
   follow the current context. The display, the mixer, SDL's event queue and the joystick
   subsystem are one per process, arbitrated by the master plan's later sub-plans, never
   switched.

This module is a leaf: it imports only the standard library, so any module may import it.
"""

from __future__ import annotations

import contextlib
import contextvars
from typing import TYPE_CHECKING, Any, Self, cast, override

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

# The name of the context every game runs in unless it switches (rule 4)
DEFAULT_CONTEXT_NAME = 'default'


class DuplicateContextSlotError(ValueError):
    """A ContextSlot was declared with the name of a slot declared before (rule 1)."""


# Every slot declared so far, by name: written once per slot, as its module is imported
_DECLARED_SLOTS: dict[str, ContextSlot[Any]] = {}


class ContextSlot[T]:
    """One piece of per-context state: its name and the factory a context makes it with.

    Compared by identity (it is a dictionary key in every context), never by name.
    """

    __slots__ = ('factory', 'name')

    def __init__(self: Self, *, name: str, factory: Callable[[], T]) -> None:
        """Declare the slot (rule 1).

        Args:
            name: Unique: the declaring module's dotted name and what it holds
                (``'glitchygames.randomness.streams'``).
            factory: Makes the slot's value for a context, the first time it is read there.

        Raises:
            DuplicateContextSlotError: If a slot of this name was declared before.

        """
        if name in _DECLARED_SLOTS:
            message = f'A context slot named {name!r} is already declared'
            raise DuplicateContextSlotError(message)
        self.name = name
        self.factory = factory
        _DECLARED_SLOTS[name] = self

    @override
    def __repr__(self: Self) -> str:
        """Return ``ContextSlot(name='...')``.

        Returns:
            The repr.

        """
        return f'ContextSlot(name={self.name!r})'


class EngineContext:
    """The state one running game owns: a value for each slot, made on first read (rule 3)."""

    def __init__(self: Self, *, name: str) -> None:
        """Make a context holding no values yet.

        Args:
            name: What logs and failures call it (``'default'``, ``'demo player 3'``).

        """
        self.name = name
        self._values: dict[ContextSlot[Any], object] = {}

    @override
    def __repr__(self: Self) -> str:
        """Return ``EngineContext(name='...')``.

        Returns:
            The repr.

        """
        return f'EngineContext(name={self.name!r})'

    def value[T](self: Self, *, slot: ContextSlot[T]) -> T:
        """Return this context's value of ``slot``, made by the slot's factory on first read.

        Args:
            slot: The slot.

        Returns:
            The value: the same object on every read until ``reset_value``.

        """
        values = self._values
        if slot in values:
            return cast('T', values[slot])
        made_value = slot.factory()
        values[slot] = made_value
        return made_value

    def reset_value[T](self: Self, *, slot: ContextSlot[T]) -> T:
        """Replace this context's value of ``slot`` with a fresh one from the factory.

        Args:
            slot: The slot.

        Returns:
            The fresh value.

        """
        made_value = slot.factory()
        self._values[slot] = made_value
        return made_value

    @contextlib.contextmanager
    def active(self: Self) -> Generator[Self]:
        """Make this the current context until the block ends (rule 5).

        Yields:
            This context.

        """
        token = _CURRENT_CONTEXT.set(self)
        try:
            yield self
        finally:
            _CURRENT_CONTEXT.reset(token)


# The context switched to last in this thread or asyncio task; None means the default (rule 4)
_CURRENT_CONTEXT: contextvars.ContextVar[EngineContext | None] = contextvars.ContextVar(
    'glitchygames_engine_context', default=None
)

_DEFAULT_CONTEXT = EngineContext(name=DEFAULT_CONTEXT_NAME)


def current_context() -> EngineContext:
    """Return the context switched to last in this thread or task, else the default one.

    Returns:
        The current context.

    """
    switched_to = _CURRENT_CONTEXT.get()
    return _DEFAULT_CONTEXT if switched_to is None else switched_to


def default_context() -> EngineContext:
    """Return the default context (every game's, unless it switches).

    Returns:
        The default context.

    """
    return _DEFAULT_CONTEXT


def declared_context_slots() -> tuple[ContextSlot[Any], ...]:
    """Return every slot declared so far, in the order declared.

    Returns:
        The slots.

    """
    return tuple(_DECLARED_SLOTS.values())
