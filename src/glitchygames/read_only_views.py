"""Read-only views: class attributes that answer the current game's state and refuse writes.

plans/2026-10-27-engine-context-2-engine-state.md (Task 1, answer 2) is the design. Several games
can run in one process (glitchygames.engine_context), so a class attribute that held one game's
state (``GameEngine.OPTIONS``) becomes a view declared in the class body:

    OPTIONS = ReadOnlyView[dict[str, Any] | None, dict[str, Any]](
        read_current=current_options, read_own=lambda engine: engine.options,
        write_instead="the engine's own: engine.options",
    )

Read on the class, a view answers the current context's value (``read_current``, given the class
read through, so a subclass answers its own); read on an instance, that object's own state
(``read_own``). A view stores nothing: its functions run on every read. ``ClassOnlyView`` is the
non-data form, for a name each instance keeps as its own attribute (``engine.game``).

Writing or deleting a view, on the class or an instance, raises ``ReadOnlyViewError`` naming
what to write instead. A class-level write never reaches a descriptor in the class body, so the
class's metaclass refuses it: ``ReadOnlyViews``, or ``ReadOnlyViewsABC`` for an ``abc.ABC``
class (``Sprite``). The metaclasses only refuse writes, which is the same for every class.

This module imports only the standard library.
"""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any, Never, Self, cast, overload

if TYPE_CHECKING:
    from collections.abc import Callable


class ReadOnlyViewError(AttributeError):
    """A read-only view was written or deleted."""


class ViewReadError(RuntimeError):
    """A view's read raised AttributeError (re-raised, so no ``__getattr__`` swallows it)."""


class ViewBase:
    """What every view has: its name in the class body and where to write instead."""

    def __init__(self: Self, *, write_instead: str) -> None:
        """Make the view; its name is set when the class body binds it (``__set_name__``).

        Args:
            write_instead: What to write instead, for the refusal (``'engine.options'``).

        """
        self.name = ''
        self.write_instead = write_instead

    def __set_name__(self: Self, owner: type, name: str) -> None:
        """Keep the name the class body binds the view to.

        Args:
            owner: The class (unused).
            name: The name.

        """
        del owner
        self.name = name

    def refusal(self: Self, *, owner: type) -> str:
        """Return the message a write of the view raises with.

        Args:
            owner: The class written through (or the class of the instance written to).

        Returns:
            The message.

        """
        return (
            f'{owner.__name__}.{self.name} is a read-only view of the current game; '
            f'write {self.write_instead}'
        )

    def read_failure(self: Self, *, owner: type, error: AttributeError) -> str:
        """Return the message a read that raised AttributeError is re-raised with.

        Args:
            owner: The class read through (or the class of the instance read).
            error: What the read raised.

        Returns:
            The message.

        """
        return f'Reading {owner.__name__}.{self.name} failed: {error}'


class ReadOnlyView[ClassReadT, InstanceReadT](ViewBase):
    """A data descriptor: the current context's value on the class, the object's own on one."""

    def __init__(
        self: Self,
        *,
        read_current: Callable[[type], ClassReadT],
        read_own: Callable[[Any], InstanceReadT],
        write_instead: str,
    ) -> None:
        """Make the view.

        Args:
            read_current: Answers a read on the class, given the class read through.
            read_own: Answers a read on an instance, given the instance.
            write_instead: What to write instead, for the refusal.

        """
        super().__init__(write_instead=write_instead)
        self._read_current = read_current
        self._read_own = read_own

    @overload  # pragma: no cover - a typing stub, never called (the implementation below is)
    def __get__(self: Self, instance: None, owner: type) -> ClassReadT: ...

    @overload  # pragma: no cover - a typing stub, never called (the implementation below is)
    def __get__(self: Self, instance: object, owner: type | None = None) -> InstanceReadT: ...

    def __get__(self: Self, instance: object, owner: Any = None) -> object:
        """Answer the current context's value (on the class) or the instance's own state.

        Args:
            instance: The instance read, or None for a read on the class.
            owner: The class read through (``Any``: Python passes it on every read through the
                class, so the read's hot path neither checks nor casts it).

        Returns:
            The value.

        Raises:
            ViewReadError: If the read raised AttributeError.

        """
        try:
            if instance is None:
                return self._read_current(owner)
            return self._read_own(instance)
        except AttributeError as error:
            read_through = owner if instance is None else type(instance)
            raise ViewReadError(self.read_failure(owner=read_through, error=error)) from error

    def __set__(self: Self, instance: object, value: object) -> Never:
        """Refuse a write through an instance.

        Args:
            instance: The instance written to.
            value: The value (refused).

        Raises:
            ReadOnlyViewError: Always.

        """
        del value
        raise ReadOnlyViewError(self.refusal(owner=type(instance)))

    def __delete__(self: Self, instance: object) -> Never:
        """Refuse a delete through an instance.

        Args:
            instance: The instance.

        Raises:
            ReadOnlyViewError: Always.

        """
        raise ReadOnlyViewError(self.refusal(owner=type(instance)))


class ClassOnlyView[ClassReadT](ViewBase):
    """A non-data descriptor: the current context's value on the class; instances keep their own.

    An instance's own attribute of the same name hides the view; an instance without one reads
    ``None``, as the class default the view replaces did. So ``ClassReadT`` must include
    ``None`` (``ClassOnlyView[Scene | None]``), as every class read where no game runs does.
    """

    def __init__(
        self: Self, *, read_current: Callable[[type], ClassReadT], write_instead: str
    ) -> None:
        """Make the view.

        Args:
            read_current: Answers a read on the class, given the class read through.
            write_instead: What to write instead, for the refusal.

        """
        super().__init__(write_instead=write_instead)
        self._read_current = read_current

    def __get__(self: Self, instance: object | None, owner: type) -> ClassReadT:
        """Answer the current context's value (on the class), or None (an instance without its own).

        Args:
            instance: The instance read (it has no attribute of its own), or None.
            owner: The class read through.

        Returns:
            The value.

        Raises:
            ViewReadError: If the read raised AttributeError.

        """
        if instance is not None:
            return cast('ClassReadT', None)
        try:
            return self._read_current(owner)
        except AttributeError as error:
            raise ViewReadError(self.read_failure(owner=owner, error=error)) from error


def _view_along_the_mro(*, cls: type, name: str) -> ViewBase | None:
    """Return the view a name resolves to on a class, else None.

    Args:
        cls: The class.
        name: The attribute's name.

    Returns:
        The first entry of that name along the MRO when it is a view, else None.

    """
    for klass in cls.__mro__:
        if name in klass.__dict__:
            entry = klass.__dict__[name]
            return entry if isinstance(entry, ViewBase) else None
    return None


class ReadOnlyViews(type):
    """The metaclass that refuses class-level writes and deletes of a view."""

    # Hidden from the type checkers: a metaclass __setattr__ makes basedpyright and ty accept a
    # write of any attribute, declared or not, on every class using the metaclass (and its
    # subclasses: every Sprite), so a misspelt class attribute would no longer be reported.
    # Hidden, a write of an undeclared attribute stays a type error; a view's write is refused
    # here, at run time
    if not TYPE_CHECKING:  # pragma: no branch - a type checker's branch, never taken at run time

        def __setattr__(cls, name: str, value: object) -> None:
            """Refuse writing a view's name on the class; set any other attribute.

            Args:
                name: The attribute's name.
                value: The value.

            Raises:
                ReadOnlyViewError: If the name is a view's.

            """
            view = _view_along_the_mro(cls=cls, name=name)
            if view is not None:
                raise ReadOnlyViewError(view.refusal(owner=cls))
            super().__setattr__(name, value)

        def __delattr__(cls, name: str) -> None:
            """Refuse deleting a view's name on the class; delete any other attribute.

            Args:
                name: The attribute's name.

            Raises:
                ReadOnlyViewError: If the name is a view's.

            """
            view = _view_along_the_mro(cls=cls, name=name)
            if view is not None:
                raise ReadOnlyViewError(view.refusal(owner=cls))
            super().__delattr__(name)


class ReadOnlyViewsABC(ReadOnlyViews, abc.ABCMeta):
    """``ReadOnlyViews`` for an ``abc.ABC`` class, whose metaclass is ``abc.ABCMeta``."""
