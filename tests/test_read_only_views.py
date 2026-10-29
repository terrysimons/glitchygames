"""Read-only views (glitchygames.read_only_views) and the guard that engine code never reads one.

A view answers the current engine context's value when read on its class and an object's own
state when read on an instance; writing one raises. ``VIEW_CHECKS`` holds each view's check
that it answers per context (``test_every_view_has_a_check`` fails for a view without one), and
``test_the_engine_never_reads_a_view`` keeps the engine reading its own state (plans/
2026-10-27-engine-context-2-engine-state.md, Task 1).
"""

from __future__ import annotations

import abc
import ast
import functools
import re
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from glitchygames.read_only_views import (
    ClassOnlyView,
    ReadOnlyView,
    ReadOnlyViewError,
    ReadOnlyViews,
    ReadOnlyViewsABC,
    ViewReadError,
)
from glitchygames.replay.tools.golden_traces import GoldenTraceEngine
from glitchygames.scenes import Scene
from tests.ast_scanning import PROJECT_ROOT, qualified_name
from tests.engine_source import ENGINE_DIRECTORY

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping, Sequence
    from pathlib import Path

    from pytest_mock import MockerFixture

    from glitchygames.engine import GameEngine

# The view descriptors, by the name a class body calls them with
READ_ONLY_VIEW_NAME = 'ReadOnlyView'
CLASS_ONLY_VIEW_NAME = 'ClassOnlyView'
VIEW_DESCRIPTOR_NAMES = frozenset({READ_ONLY_VIEW_NAME, CLASS_ONLY_VIEW_NAME})
# The keywords a view takes its read functions with
VIEW_READ_KEYWORDS = frozenset({'read_current', 'read_own'})
# The mark naming a module's views (answered by its module-level __getattr__)
MODULE_VIEWS_MARK = 'READ_ONLY_MODULE_VIEWS'
MODULE_GETATTR = '__getattr__'
# The module the views are defined in: allowed to name every view
READ_ONLY_VIEWS_SOURCE = PROJECT_ROOT / ENGINE_DIRECTORY / 'read_only_views.py'
STAND_IN_GAME_NAME = 'Read-only views stand-in'

# Every view, as 'GameEngine.OPTIONS' or 'glitchygames.performance.performance_manager', with
# the check that it answers per context: (*, first, second, mocker) -> None
VIEW_CHECKS: dict[str, Callable[..., None]] = {}


class ViewScanError(Exception):
    """A view declaration the scan cannot read (a mark naming what no __getattr__ answers)."""


# What the stand-in class-level view reads (a box, so the test can change it between reads)
SHOWN_BOX: list[int] = [0]


def _current_shown(owner: type) -> int | None:
    return SHOWN_BOX[0] if owner is StandInOwner else None


class StandInOwner(metaclass=ReadOnlyViews):
    """A stand-in owner whose instances keep their own state under lowercase names."""

    SHOWN = ReadOnlyView[int | None, int](
        read_current=_current_shown,
        read_own=lambda owner: owner.shown,
        write_instead='owner.shown',
    )
    kept = ClassOnlyView[int | None](read_current=_current_shown, write_instead='owner.kept')
    plain = 0

    def __init__(self, *, shown: int) -> None:
        """Keep the instance's own state."""
        self.shown = shown


class StandInScene(Scene):
    """The game scene of a stand-in engine (the engine never builds it)."""

    NAME = STAND_IN_GAME_NAME
    VERSION = '1.0'


def make_stand_in_engine(*, mocker: MockerFixture, target_fps: int) -> GameEngine:
    """Make an engine of a stand-in scene in the current context (registered as its engine).

    The command line is patched as tests/events/test_events_integration.py's
    ``start_engine_with_scene`` gives it (a plain window: GoldenTraceEngine).

    Args:
        mocker: pytest-mock's fixture.
        target_fps: The engine's --target-fps.

    Returns:
        The engine, constructed (not started).

    """
    mocker.patch.object(
        sys,
        'argv',
        [
            'test_read_only_views',
            '--windowed',
            '--resolution',
            '800x600',
            '--log-level',
            'warning',
            '--target-fps',
            str(target_fps),
        ],
    )
    return GoldenTraceEngine(game=StandInScene)


# --- The scan: where views are declared, and where engine code reads them ---


@dataclass
class ScannedClass:
    """A class as the scan sees it: its base classes' names and the views its body declares."""

    base_names: set[str] = field(default_factory=set[str])
    # View name -> READ_ONLY_VIEW_NAME or CLASS_ONLY_VIEW_NAME
    view_kinds: dict[str, str] = field(default_factory=dict[str, str])


@dataclass
class ScannedFile:
    """What one file declares: its classes, its module views and the definitions allowed."""

    module_name: str
    tree: ast.Module
    classes: dict[str, ScannedClass]
    module_views: frozenset[str]
    # The statements that define views: reading a view's name inside them is allowed
    definitions: list[ast.stmt]


def engine_source_files() -> list[Path]:
    """Return every Python file of the engine's source.

    Returns:
        The files, sorted.

    """
    return sorted((PROJECT_ROOT / ENGINE_DIRECTORY).rglob('*.py'))


def module_name_of_file(*, source_path: Path) -> str:
    """Return the module a file is imported as: its packages are the directories above it.

    Args:
        source_path: A Python file.

    Returns:
        The dotted name (a package's ``__init__.py`` is the package; a file in a directory
        that is not a package is a top-level module).

    """
    parts = [] if source_path.stem == '__init__' else [source_path.stem]
    directory = source_path.parent
    while (directory / '__init__.py').exists():
        parts.insert(0, directory.name)
        directory = directory.parent
    return '.'.join(parts)


def view_descriptor_kind(value: ast.expr | None) -> str | None:
    """Return which view a class-body value makes (``ReadOnlyView[...](...)`` or not), else None.

    Args:
        value: The assigned value.

    Returns:
        READ_ONLY_VIEW_NAME, CLASS_ONLY_VIEW_NAME or None.

    """
    if not isinstance(value, ast.Call):
        return None
    called = value.func.value if isinstance(value.func, ast.Subscript) else value.func
    if isinstance(called, ast.Name):
        name = called.id
    elif isinstance(called, ast.Attribute):
        name = called.attr
    else:
        return None
    return name if name in VIEW_DESCRIPTOR_NAMES else None


def assigned_name_and_value(statement: ast.stmt) -> tuple[str, ast.expr | None] | None:
    """Return the name and value of ``NAME = value`` or ``NAME: type = value``, else None.

    Args:
        statement: A statement.

    Returns:
        The name and value, or None for any other statement.

    """
    if (
        isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
    ):
        return statement.targets[0].id, statement.value
    if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
        return statement.target.id, statement.value
    return None


def base_class_names(class_definition: ast.ClassDef) -> set[str]:
    """Return the names of a class's bases (``events.EventManager`` -> ``EventManager``).

    Args:
        class_definition: The class.

    Returns:
        The names.

    """
    names: set[str] = set()
    for base in class_definition.bases:
        if isinstance(base, ast.Name):
            names.add(base.id)
        elif isinstance(base, ast.Attribute):
            names.add(base.attr)
    return names


def marked_module_views(*, tree: ast.Module, source_path: Path) -> list[ast.stmt]:
    """Return the module's view mark and ``__getattr__`` when it marks views, else nothing.

    Args:
        tree: The parsed module.
        source_path: Its file, for the errors.

    Returns:
        ``[mark, __getattr__]``, or ``[]`` for a module without the mark.

    Raises:
        ViewScanError: If the mark is not a ``frozenset({...})`` of string literals, the module
            has no module-level ``__getattr__``, or the ``__getattr__`` never compares its
            argument with a marked name.

    """
    marks = [
        statement
        for statement in tree.body
        if (assigned := assigned_name_and_value(statement)) is not None
        and assigned[0] == MODULE_VIEWS_MARK
    ]
    if not marks:
        return []
    (mark,) = marks
    marked_names = marked_view_names(mark=mark, source_path=source_path)
    getattr_definitions = [
        statement
        for statement in tree.body
        if isinstance(statement, ast.FunctionDef) and statement.name == MODULE_GETATTR
    ]
    if not getattr_definitions:
        message = f'{source_path}: {MODULE_VIEWS_MARK} without a module-level {MODULE_GETATTR}'
        raise ViewScanError(message)
    (getattr_definition,) = getattr_definitions
    unanswered = marked_names - compared_names(function=getattr_definition)
    if unanswered:
        message = (
            f'{source_path}:{mark.lineno}: {MODULE_VIEWS_MARK} marks {sorted(unanswered)}, '
            f'which {MODULE_GETATTR} never compares its argument with'
        )
        raise ViewScanError(message)
    return [mark, getattr_definition]


def marked_view_names(*, mark: ast.stmt, source_path: Path) -> frozenset[str]:
    """Return the names a ``READ_ONLY_MODULE_VIEWS = frozenset({...})`` mark lists.

    Args:
        mark: The mark's assignment.
        source_path: Its file, for the error.

    Returns:
        The names.

    Raises:
        ViewScanError: If the value is not ``frozenset({...})`` of string literals.

    """
    assigned = assigned_name_and_value(mark)
    value = None if assigned is None else assigned[1]
    elements = (
        value.args[0].elts
        if isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == 'frozenset'
        and len(value.args) == 1
        and isinstance(value.args[0], ast.Set)
        else None
    )
    names = [
        element.value
        for element in elements or []
        if isinstance(element, ast.Constant) and isinstance(element.value, str)
    ]
    if elements is None or len(names) != len(elements):
        message = (
            f'{source_path}:{mark.lineno}: {MODULE_VIEWS_MARK} must be frozenset({{...}}) of '
            'string literals'
        )
        raise ViewScanError(message)
    return frozenset(names)


def compared_names(*, function: ast.FunctionDef) -> frozenset[str]:
    """Return the strings a function compares its first argument with (``==`` or ``in``).

    Args:
        function: A module ``__getattr__(name)``.

    Returns:
        The strings.

    """
    argument = function.args.args[0].arg
    names: set[str] = set()
    for node in ast.walk(function):
        if not (
            isinstance(node, ast.Compare)
            and isinstance(node.left, ast.Name)
            and node.left.id == argument
        ):
            continue
        for operator, comparator in zip(node.ops, node.comparators, strict=True):
            if isinstance(operator, ast.Eq):
                candidates = [comparator]
            elif isinstance(operator, ast.In) and isinstance(
                comparator, (ast.Tuple, ast.List, ast.Set)
            ):
                candidates = comparator.elts
            else:
                continue
            names.update(
                candidate.value
                for candidate in candidates
                if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str)
            )
    return frozenset(names)


@functools.cache
def scanned_file(source_path: Path) -> ScannedFile:
    """Return what a file declares (each file is parsed once per run).

    Args:
        source_path: A Python file.

    Returns:
        Its classes, module views and view definitions.

    """
    tree = ast.parse(source_path.read_text(encoding='utf-8'))
    classes: dict[str, ScannedClass] = {}
    definitions: list[ast.stmt] = []
    helper_names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        scanned_class = classes.setdefault(node.name, ScannedClass())
        scanned_class.base_names |= base_class_names(node)
        for statement in node.body:
            assigned = assigned_name_and_value(statement)
            kind = None if assigned is None else view_descriptor_kind(assigned[1])
            if assigned is None or kind is None:
                continue
            scanned_class.view_kinds[assigned[0]] = kind
            definitions.append(statement)
            assert isinstance(assigned[1], ast.Call)
            helper_names.update(
                keyword.value.id
                for keyword in assigned[1].keywords
                if keyword.arg in VIEW_READ_KEYWORDS and isinstance(keyword.value, ast.Name)
            )
    # The helpers passed to a view as its read functions
    definitions.extend(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in helper_names
    )
    module_view_definitions = marked_module_views(tree=tree, source_path=source_path)
    definitions.extend(module_view_definitions)
    module_views = (
        marked_view_names(mark=module_view_definitions[0], source_path=source_path)
        if module_view_definitions
        else frozenset[str]()
    )
    return ScannedFile(
        module_name=module_name_of_file(source_path=source_path),
        tree=tree,
        classes=classes,
        module_views=module_views,
        definitions=definitions,
    )


def declared_views(*, source_paths: Sequence[Path]) -> dict[str, frozenset[str]]:
    """Return every view the files declare, by owner.

    A class view is a class-body ``NAME = ReadOnlyView[...](...)`` or ``ClassOnlyView`` (owner:
    the class's name). A module view is a name its module lists in ``READ_ONLY_MODULE_VIEWS``,
    answered by its module-level ``__getattr__`` (owner: the module's dotted name); a module
    ``__getattr__`` without the mark (a lazy import, as glitchygames.audio's) is never a view.

    Args:
        source_paths: The Python files.

    Returns:
        Owner -> its view names.

    """
    views: dict[str, set[str]] = {}
    for source_path in source_paths:
        scanned = scanned_file(source_path)
        for class_name, scanned_class in scanned.classes.items():
            if scanned_class.view_kinds:
                views.setdefault(class_name, set()).update(scanned_class.view_kinds)
        if scanned.module_views:
            views.setdefault(scanned.module_name, set()).update(scanned.module_views)
    return {owner: frozenset(names) for owner, names in views.items()}


def merged_classes(*, source_paths: Sequence[Path]) -> dict[str, ScannedClass]:
    """Return the classes the files declare, by name (same-named classes merged).

    Args:
        source_paths: The Python files.

    Returns:
        Class name -> its bases and views.

    """
    classes: dict[str, ScannedClass] = {}
    for source_path in source_paths:
        for class_name, scanned_class in scanned_file(source_path).classes.items():
            merged = classes.setdefault(class_name, ScannedClass())
            merged.base_names |= scanned_class.base_names
            merged.view_kinds |= scanned_class.view_kinds
    return classes


def class_and_ancestors(*, class_name: str, classes: Mapping[str, ScannedClass]) -> set[str]:
    """Return a class's name and its ancestors' names, followed by name through the classes.

    Args:
        class_name: The class.
        classes: Every class the scan knows, by name.

    Returns:
        The names.

    """
    found: set[str] = set()
    waiting = [class_name]
    while waiting:
        name = waiting.pop()
        if name in found:
            continue
        found.add(name)
        if name in classes:
            waiting.extend(classes[name].base_names)
    return found


def import_bindings_of(*, tree: ast.Module, module_name: str, is_package: bool) -> dict[str, str]:
    """Map each local name an import binds to the qualified name it refers to.

    Relative imports are resolved from the file's own module.

    Args:
        tree: The parsed module.
        module_name: Its dotted name.
        is_package: Whether it is a package's ``__init__.py``.

    Returns:
        Local name -> qualified name.

    """
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname is None:
                    top_level_name = alias.name.split('.')[0]
                    bindings[top_level_name] = top_level_name
                else:
                    bindings[alias.asname] = alias.name
        elif isinstance(node, ast.ImportFrom):
            imported_from = absolute_import_module(
                node=node, module_name=module_name, is_package=is_package
            )
            for alias in node.names:
                bindings[alias.asname or alias.name] = f'{imported_from}.{alias.name}'
    return bindings


def absolute_import_module(*, node: ast.ImportFrom, module_name: str, is_package: bool) -> str:
    """Return the module a ``from ... import`` imports from, relative imports resolved.

    Args:
        node: The import.
        module_name: The importing file's dotted name.
        is_package: Whether the importing file is a package's ``__init__.py``.

    Returns:
        The absolute dotted name.

    """
    if node.level == 0:
        return node.module or ''
    package_parts = module_name.split('.') if is_package else module_name.split('.')[:-1]
    base_parts = package_parts[: len(package_parts) - (node.level - 1)]
    return '.'.join([*base_parts, *([node.module] if node.module else [])])


def nodes_outside(*, tree: ast.AST, excluded: Sequence[ast.stmt]) -> Iterator[ast.AST]:
    """Yield every node of the tree except those inside the excluded statements.

    Args:
        tree: The parsed module.
        excluded: The statements skipped, with everything inside them.

    Yields:
        Each node, parents before children.

    """
    excluded_ids = {id(statement) for statement in excluded}
    waiting: list[ast.AST] = [tree]
    while waiting:
        node = waiting.pop()
        if id(node) in excluded_ids:
            continue
        yield node
        waiting.extend(ast.iter_child_nodes(node))


def engine_view_reads(*, source_path: Path, views: Mapping[str, frozenset[str]]) -> list[str]:
    """Return ``'<line>: <read>'`` for each read of a view in a file.

    A read is an attribute load ``<Name>.<view>`` of an owner class or a subclass (resolved by
    name through the engine's classes and the file's); an attribute load ``.<view>`` of a
    ``ReadOnlyView``'s name on any other receiver (``self``, ``manager``, ``self.game``), except
    a bare capitalized name of a class that owns no view of that name; or an import or attribute
    load of a module view. The view definitions (read_only_views.py, the class-body
    assignments, the helpers passed to them, the marked module ``__getattr__`` and its mark)
    are allowed. An unrelated attribute named like a ``ReadOnlyView`` is reported: rename it.

    Args:
        source_path: A Python file.
        views: Owner -> its view names (``declared_views``).

    Returns:
        The reads, by line.

    """
    if source_path == READ_ONLY_VIEWS_SOURCE:
        return []
    scanned = scanned_file(source_path)
    classes = merged_classes(source_paths=[*engine_source_files(), source_path])
    class_owners = {owner: names for owner, names in views.items() if owner in classes}
    read_only_view_names = {
        name
        for owner, names in class_owners.items()
        for name in names
        if classes[owner].view_kinds.get(name) == READ_ONLY_VIEW_NAME
    }
    module_views = {
        f'{owner}.{name}'
        for owner, names in views.items()
        if owner not in class_owners
        for name in names
    }
    bindings = import_bindings_of(
        tree=scanned.tree,
        module_name=scanned.module_name,
        is_package=source_path.stem == '__init__',
    )
    reads: list[tuple[int, str]] = []
    for node in nodes_outside(tree=scanned.tree, excluded=scanned.definitions):
        if isinstance(node, ast.ImportFrom):
            imported_from = absolute_import_module(
                node=node,
                module_name=scanned.module_name,
                is_package=source_path.stem == '__init__',
            )
            reads.extend(
                (node.lineno, f'{imported_from}.{alias.name}')
                for alias in node.names
                if f'{imported_from}.{alias.name}' in module_views
            )
            continue
        if not (isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load)):
            continue
        if qualified_name(node=node, bindings=bindings, watched_modules=frozenset()) in (
            module_views
        ):
            reads.append((node.lineno, ast.unparse(node)))
            continue
        receiver = node.value
        if isinstance(receiver, ast.Name) and receiver.id[:1].isupper():
            owned_names = {
                name
                for ancestor in class_and_ancestors(class_name=receiver.id, classes=classes)
                for name in class_owners.get(ancestor, frozenset())
            }
            is_read = node.attr in owned_names
        else:
            is_read = node.attr in read_only_view_names
        if is_read:
            reads.append((node.lineno, ast.unparse(node)))
    return [f'{line}: {read}' for line, read in sorted(reads)]


# --- The views' mechanism ---


def test_a_class_read_answers_the_current_value_on_every_access():
    """A view stores nothing: each class read runs read_current again."""
    SHOWN_BOX[0] = 1
    first_read = StandInOwner.SHOWN
    SHOWN_BOX[0] = 2

    assert (first_read, StandInOwner.SHOWN, StandInOwner.kept) == (1, 2, 2)


def test_an_instance_read_answers_the_instances_own_state():
    """An instance reads its own state; without its own kept, a ClassOnlyView answers None."""
    owner = StandInOwner(shown=7)
    no_own_kept = owner.kept
    owner.kept = 5

    assert (owner.SHOWN, no_own_kept, owner.kept) == (7, None, 5)


def test_writing_a_view_raises_and_names_where_to_write(mocker):
    """Set, delete and patch, on the class and an instance, each raise with the view's message."""
    owner = StandInOwner(shown=7)
    message = 'StandInOwner.SHOWN is a read-only view of the current game; write owner.shown'
    for write in (
        lambda: setattr(StandInOwner, 'SHOWN', 3),
        lambda: setattr(owner, 'SHOWN', 3),
        lambda: delattr(StandInOwner, 'SHOWN'),
        lambda: delattr(owner, 'SHOWN'),
        lambda: mocker.patch.object(StandInOwner, 'SHOWN', 3),
    ):
        with pytest.raises(ReadOnlyViewError, match=re.escape(message)):
            write()
    with pytest.raises(ReadOnlyViewError, match=re.escape('write owner.kept')):
        StandInOwner.kept = 3


def test_the_metaclass_lets_every_other_class_attribute_be_written():
    """Only a view's name is refused."""
    StandInOwner.plain = 1
    del StandInOwner.plain

    assert not hasattr(StandInOwner, 'plain')


def test_a_read_that_fails_is_never_mistaken_for_a_missing_attribute():
    """An AttributeError a read raises becomes ViewReadError; any other error propagates."""

    class Broken(metaclass=ReadOnlyViews):
        SHOWN = ReadOnlyView[int, int](
            read_current=lambda _owner: {}['missing'],
            read_own=lambda broken: broken.never_set,
            write_instead='nowhere',
        )
        kept = ClassOnlyView[int](read_current=lambda owner: owner.never_set, write_instead='x')

    with pytest.raises(ViewReadError):
        Broken().SHOWN  # ruff: ignore[useless-expression]
    with pytest.raises(ViewReadError):
        Broken.kept  # ruff: ignore[useless-expression]
    with pytest.raises(KeyError):
        Broken.SHOWN  # ruff: ignore[useless-expression]


def test_an_abc_class_takes_the_abc_views_metaclass():
    """An abc.ABC class gets views through ReadOnlyViewsABC."""

    class AbstractOwner(abc.ABC, metaclass=ReadOnlyViewsABC):
        SHOWN = ReadOnlyView[int | None, int](
            read_current=_current_shown, read_own=lambda _owner: 0, write_instead='nowhere'
        )

    assert AbstractOwner.SHOWN is None
    with pytest.raises(ReadOnlyViewError):
        AbstractOwner.SHOWN = 1


# --- The guards ---


def test_every_view_has_a_check():
    """A view added without a check here fails (each view answers per context)."""
    found = {
        f'{owner}.{name}'
        for owner, names in declared_views(source_paths=engine_source_files()).items()
        for name in names
    }

    assert found == set(VIEW_CHECKS)


def test_the_engine_never_reads_a_view():
    """Engine code reads its own state (self.options, slots), never a view (the hot paths)."""
    views = declared_views(source_paths=engine_source_files())
    reads = {
        str(path): found
        for path in engine_source_files()
        if (found := engine_view_reads(source_path=path, views=views))
    }

    assert reads == {}


# A module declaring views: an owner class, a marked module view and a class owning none, then
# reads of each (the reads: lines 30-33 and 41; the definitions name views too, which is allowed)
PLANTED_VIEWS = """\
from glitchygames.read_only_views import ClassOnlyView, ReadOnlyView, ReadOnlyViews

READ_ONLY_MODULE_VIEWS = frozenset({'manager'})


def _current_options(owner):
    return owner.OPTIONS


class Owner(metaclass=ReadOnlyViews):
    OPTIONS = ReadOnlyView[dict | None, dict](
        read_current=_current_options, read_own=lambda owner: owner.options, write_instead='x'
    )
    game = ClassOnlyView[object](read_current=lambda owner: Owner.game, write_instead='x')


class Other:
    OPTIONS = {}


def __getattr__(name):
    if name == 'manager':
        return Owner.OPTIONS
    raise AttributeError(name)


def reads(owner, self):
    from lazy import Helper
    return (
        Owner.OPTIONS,
        owner.OPTIONS,
        self.game.OPTIONS,
        Owner.game,
        owner.game,
        Other.OPTIONS,
        Helper,
    )


def imports():
    from planted import manager
    return manager
"""

# A lazy import through a module __getattr__ (PEP 562, as glitchygames.audio's VoiceAssistant):
# no mark, so never a view
PLANTED_LAZY_IMPORT = """\
def __getattr__(name):
    if name == 'Helper':
        from planted import Other
        return Other
    raise AttributeError(name)
"""


def test_the_view_read_scan_finds_class_instance_and_module_reads(tmp_path):
    """Five reads; not the definitions, an instance's own attribute or a class owning none."""
    planted_path = tmp_path / 'planted.py'
    planted_path.write_text(PLANTED_VIEWS, encoding='utf-8')
    lazy_path = tmp_path / 'lazy.py'
    lazy_path.write_text(PLANTED_LAZY_IMPORT, encoding='utf-8')
    views = declared_views(source_paths=[planted_path, lazy_path])

    assert views == {'Owner': frozenset({'OPTIONS', 'game'}), 'planted': frozenset({'manager'})}
    assert engine_view_reads(source_path=planted_path, views=views) == [
        '30: Owner.OPTIONS',
        '31: owner.OPTIONS',
        '32: self.game.OPTIONS',
        '33: Owner.game',
        '41: planted.manager',
    ]
    assert engine_view_reads(source_path=lazy_path, views=views) == []


# Appended to PLANTED_VIEWS: a subclass of the owner, read through the subclass, and the module
# view read as an attribute of the imported module (line 52)
PLANTED_SUBCLASS_READS = """\

import planted


class Derived(Owner):
    pass


def subclass_reads():
    return Derived.game, planted.manager
"""


def test_the_view_read_scan_follows_subclasses_and_module_attributes(tmp_path):
    """A subclass of an owner reads the owner's views; so does module.view."""
    planted_path = tmp_path / 'planted.py'
    planted_path.write_text(PLANTED_VIEWS + PLANTED_SUBCLASS_READS, encoding='utf-8')
    views = declared_views(source_paths=[planted_path])

    assert engine_view_reads(source_path=planted_path, views=views)[-2:] == [
        '52: Derived.game',
        '52: planted.manager',
    ]


def test_a_marked_name_the_module_getattr_never_answers_is_a_scan_error(tmp_path):
    """A mark must name only what the module __getattr__ answers."""
    planted_path = tmp_path / 'marked.py'
    planted_path.write_text(
        PLANTED_VIEWS.replace("frozenset({'manager'})", "frozenset({'manager', 'missing'})"),
        encoding='utf-8',
    )

    with pytest.raises(ViewScanError, match=re.escape("marks ['missing']")):
        declared_views(source_paths=[planted_path])
