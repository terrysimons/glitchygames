"""Every piece of process-wide state in the engine and the members is in the engine-context audit.

An engine context (glitchygames.engine_context) owns one running game's state, so several games
can run in one process. State that lives in a module or a class instead is shared by every
context, so the audit (plans/2026-10-25-engine-context.md: the rows C*, S* and R*) names each
piece and why it may stay shared. This guard is that audit as an allowlist: it scans the
engine's and every workspace member's source (tests/workspace_sources.py) and fails on any
process state ``PROCESS_STATE`` does not list, and on any listing the scan no longer finds.

What the scan reports (the rules; nothing else is decided):

1. A module-level or class-body binding (``=``, annotated ``=``) whose value is not evidently
   immutable, except ``__all__`` and ``model_config``. Evidently immutable: a literal constant,
   an f-string, a name or attribute reference (but a bare name bound, in the same module, to a
   value this scan reports is reported too: an alias of a mutable), a subscript (a type alias,
   ``Literal[...]``, ``Annotated[...]``, ``vars(SomeClass)['name']``), a lambda, a comparison or
   boolean expression, a tuple (starred items included) of evidently immutable values, a unary
   or binary operation on them, a method call on a string literal (``'; '.join(...)``), and a
   call to one of ``IMMUTABLE_CALLS`` (spelled in full or by its last name alone), to
   ``math.*``, or to a class in ``frozen_class_names`` (scanned classes that subclass ``Enum``,
   ``IntEnum``, ``StrEnum``, ``Flag`` or ``NamedTuple``, are ``@dataclass(frozen=True)``, or
   set ``model_config = ConfigDict(frozen=True, ...)``, and whose name no unfrozen scanned
   class shares). ``typing.cast(type, value)`` returns its value unchanged, so it is as
   immutable as that value. A view (``ReadOnlyView``, ``ClassOnlyView``) computes on every read
   and stores nothing. A ``type X = ...`` statement is not a binding and is never reported, nor
   is anything in a script's ``if __name__ == '__main__':`` block (never run on import).
2. Except: a constant-named binding (``_*[A-Z][A-Z0-9_]*``) whose value is a dict, list or set
   display or comprehension, or an operation on one, is a table, reported only when the scan
   sees it written anywhere in the scanned files: an item or attribute assignment, augmented
   assignment or ``del`` through it, or a call of one of ``TABLE_MUTATORS`` on it (matched by
   its last name: ``NAME``, ``self.NAME``, ``cls.NAME``, ``Class.NAME``).
3. Every name in a ``global`` statement.
4. Every assignment, augmented assignment or ``del``, inside a function, of an attribute of a
   class object: the receiver is ``cls`` (reported as the enclosing class's), a capitalized,
   non-constant name, a parameter annotated ``type[...]`` (alone or in a union, such as
   ``game: type[Scene] | Scene``), ``type(<expression>)`` or ``<expression>.__class__``; and
   every ``setattr(...)``/``delattr(...)`` call whose first argument is one of
   those, or an imported module or an attribute of one (``setattr(pygame.mixer.music, ...)``),
   reported as ``setattr(<receiver>)``. An attribute store is reported as ``<class>.<name>``:
   the enclosing class for ``cls``, ``type(self)`` and ``self.__class__``, the annotated class
   for a ``type[...]`` parameter (the first ``type[...]`` member of a union). At import time
   (outside every function) the same writes are reported, and an attribute store into an
   imported module or an attribute of one too (``other.Thing.attr = 1``: ``other.Thing.attr``).
5. Every function decorated with ``functools.cache``, ``functools.lru_cache``, ``cache`` or
   ``lru_cache`` (a process-wide cache), reported by the function's qualified name.

Limits: an object bound to a constant-named table is trusted unless the scan sees it written by
those means; changes through other methods are not seen, which is why rule 1 reports every
non-immutable object whatever its name. A frozen class is trusted even when it holds a mutable
field (``BOOKMARK_CONTROL_EVENT = ControlEvent(..., data={...})`` in
glitchygames.replay.driver). A ``setattr`` whose receiver is only known at run time is not seen
(glitchygames.replay.tools.golden_traces swaps a module function in a loop over pairs,
restoring it in a ``finally``: the same kind of state as S17's, which the scan does see, a
recording tool's, never in a game).

The scan parses one file at a time and keeps no tree past its file (CI's memory limit; #112): a
first pass over the files collects only names (``frozen_class_names``,
``written_table_names``), then a second pass parses each file again and runs
``process_state_in_source`` on it.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

from tests.ast_scanning import PROJECT_ROOT
from tests.workspace_sources import scanned_source_files, write_project_with_member_module

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from pathlib import Path

# A constant's name (rule 2's tables, and the names rule 4 does not read as a class)
CONSTANT_NAME = re.compile(r'_*[A-Z][A-Z0-9_]*')
# A capitalized name (rule 4: a class, when it is not a constant's)
CAPITALIZED_NAME = re.compile(r'_*[A-Z]\w*')
# The bindings rule 1 never reports: a module's export list and a pydantic model's configuration
UNREPORTED_BINDINGS = frozenset({'__all__', 'model_config'})
# The calls whose result is evidently immutable (rule 1), spelled in full; a call spelled by the
# last name alone (``from typing import cast``) counts too
IMMUTABLE_CALLS = frozenset({
    'frozenset',
    'tuple',
    'int',
    'float',
    'str',
    'bool',
    'bytes',
    'object',
    're.compile',
    'logging.getLogger',
    'ContextSlot',
    'contextvars.ContextVar',
    'typing.TypeVar',
    'typing.ParamSpec',
    'typing.TypeVarTuple',
    'typing.TypeAliasType',
    'typing.NewType',
    'pathlib.Path',
    'types.MappingProxyType',
    'dataclasses.field',
    'pydantic.Field',
    'pydantic.ConfigDict',
    'struct.Struct',
    'enum.auto',
    'fractions.Fraction',
    'pygame.event.custom_type',
    'datetime.timedelta',
    'decimal.Decimal',
    'collections.namedtuple',
    'ReadOnlyView',
    'ClassOnlyView',
})
IMMUTABLE_CALL_LAST_NAMES = frozenset(name.rsplit('.', 1)[-1] for name in IMMUTABLE_CALLS)
# typing.cast, as spelled: immutable only when the value it is given is (rule 1)
CAST_CALLS = frozenset({'cast', 'typing.cast'})
# The arguments cast takes: the type, then the value it returns
CAST_ARGUMENT_COUNT = 2
# The modules every function of which returns an immutable value (rule 1)
IMMUTABLE_CALL_MODULES = frozenset({'math'})
# The bases that make a scanned class frozen (rule 1)
FROZEN_BASES = frozenset({'Enum', 'IntEnum', 'StrEnum', 'Flag', 'NamedTuple'})
# The methods whose call on a table writes it (rule 2)
TABLE_MUTATORS = frozenset({
    'append',
    'extend',
    'insert',
    'update',
    'setdefault',
    'pop',
    'popitem',
    'clear',
    'remove',
    'discard',
    'add',
    'sort',
    'reverse',
})
# The decorators that make a function a process-wide cache (rule 5)
CACHE_DECORATORS = frozenset({'functools.cache', 'functools.lru_cache', 'cache', 'lru_cache'})
# The builtins whose call writes an attribute (rule 4)
ATTRIBUTE_WRITERS = frozenset({'setattr', 'delattr'})


def _dotted_name(node: ast.expr) -> str | None:
    """Return a name or attribute chain spelled out (``pygame.event.custom_type``), else None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _dotted_name(node.value)
        return None if owner is None else f'{owner}.{node.attr}'
    return None


def _last_name(node: ast.expr) -> str | None:
    """Return the last name of a name or attribute chain (``self.NAME``: ``NAME``), else None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _report(*, found: dict[str, int], name: str, line: int) -> None:
    """Record a finding at its first line."""
    found[name] = min(line, found.get(name, line))


def _flattened_targets(target: ast.expr) -> Iterator[ast.expr]:
    """Yield every target an assignment target holds (``a, (b, *c) = ...``: a, b and c)."""
    if isinstance(target, ast.Tuple | ast.List):
        for element in target.elts:
            yield from _flattened_targets(element)
    elif isinstance(target, ast.Starred):
        yield from _flattened_targets(target.value)
    else:
        yield target


def _child_statements(statement: ast.stmt) -> Iterator[ast.stmt]:
    """Yield the statements a compound statement holds (its handlers' and cases' included)."""
    for child in ast.iter_child_nodes(statement):
        if isinstance(child, ast.stmt):
            yield child
        elif isinstance(child, ast.ExceptHandler | ast.match_case):
            yield from child.body


def _is_main_block(statement: ast.If) -> bool:
    """Return whether an ``if`` is a script's ``if __name__ == '__main__':`` block."""
    test = statement.test
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == '__name__'
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == '__main__'
    )


def _is_true_keyword(*, keyword: ast.keyword, name: str) -> bool:
    """Return whether a call's keyword is ``name=True``."""
    return (
        keyword.arg == name
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is True
    )


def _sets_frozen(call: ast.expr) -> bool:
    """Return whether an expression is a call given ``frozen=True``."""
    return isinstance(call, ast.Call) and any(
        _is_true_keyword(keyword=keyword, name='frozen') for keyword in call.keywords
    )


def _is_frozen_class(node: ast.ClassDef) -> bool:
    """Return whether a class is frozen by its bases, its dataclass decorator or its config."""
    if any(_last_name(base) in FROZEN_BASES for base in node.bases):
        return True
    if any(
        isinstance(decorator, ast.Call)
        and _last_name(decorator.func) == 'dataclass'
        and _sets_frozen(decorator)
        for decorator in node.decorator_list
    ):
        return True
    return any(
        isinstance(statement, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == 'model_config'
            for target in statement.targets
        )
        and isinstance(statement.value, ast.Call)
        and _last_name(statement.value.func) == 'ConfigDict'
        and _sets_frozen(statement.value)
        for statement in node.body
    )


def frozen_class_names(*, source_paths: Sequence[Path]) -> frozenset[str]:
    """Return the names of the scanned classes whose instances are immutable (rule 1).

    Args:
        source_paths: The files to read, one at a time.

    Returns:
        The class names (``Point``) of every class that subclasses an enum or ``NamedTuple``,
        is ``@dataclass(frozen=True)`` or sets ``model_config = ConfigDict(frozen=True, ...)``,
        less every name another scanned class that is not frozen also has: a call is matched by
        its class's name alone, so a shared name could be either class.

    """
    frozen_names: set[str] = set()
    unfrozen_names: set[str] = set()
    for source_path in source_paths:
        tree = ast.parse(source_path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                (frozen_names if _is_frozen_class(node) else unfrozen_names).add(node.name)
    return frozenset(frozen_names - unfrozen_names)


def _written_base(node: ast.expr) -> str | None:
    """Return the last name of what an item or attribute write goes through (rule 2).

    ``NAME[key][other] = ...`` and ``self.NAME.field = ...`` go through ``NAME``.
    """
    while isinstance(node, ast.Subscript):
        node = node.value
    return _last_name(node)


def _assignment_targets(node: ast.AST) -> list[ast.expr]:
    """Return what an assignment, augmented assignment or ``del`` writes, else nothing."""
    if isinstance(node, ast.Assign | ast.Delete):
        return [flat for target in node.targets for flat in _flattened_targets(target)]
    if isinstance(node, ast.AnnAssign | ast.AugAssign):
        return list(_flattened_targets(node.target))
    return []


def _tables_written_in(tree: ast.Module) -> set[str]:
    """Return the last names of everything a module writes through (rule 2's means)."""
    written: set[str | None] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in TABLE_MUTATORS
        ):
            written.add(_written_base(node.func.value))
        for target in _assignment_targets(node):
            if isinstance(target, ast.Subscript | ast.Attribute):
                written.add(_written_base(target.value))
            if isinstance(node, ast.AugAssign):
                written.add(_last_name(target))
    return {name for name in written if name is not None}


def written_table_names(*, source_paths: Sequence[Path]) -> frozenset[str]:
    """Return the last names of everything the scanned files write through (rule 2).

    Args:
        source_paths: The files to read, one at a time.

    Returns:
        Every name an item or attribute assignment, augmented assignment, ``del`` or a
        ``TABLE_MUTATORS`` call goes through.

    """
    names: set[str] = set()
    for source_path in source_paths:
        names.update(_tables_written_in(ast.parse(source_path.read_text(encoding='utf-8'))))
    return frozenset(names)


def _is_table_display(node: ast.expr) -> bool:
    """Return whether a value is a dict, list or set display or comprehension, or uses one."""
    if isinstance(node, ast.Dict | ast.List | ast.Set | ast.DictComp | ast.ListComp | ast.SetComp):
        return True
    if isinstance(node, ast.BinOp):
        return _is_table_display(node.left) or _is_table_display(node.right)
    return False


def _is_immutable_call(*, node: ast.Call, frozen_classes: frozenset[str]) -> bool:
    """Return whether a call's result is evidently immutable (rule 1)."""
    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Constant):
        return isinstance(node.func.value.value, str)
    # A parametrized class is called as itself (``ReadOnlyView[int, int](...)``)
    called = node.func.value if isinstance(node.func, ast.Subscript) else node.func
    spelled = _dotted_name(called)
    if spelled is None:
        return False
    last_name = spelled.rsplit('.', 1)[-1]
    return (
        spelled in IMMUTABLE_CALLS
        or (spelled == last_name and last_name in IMMUTABLE_CALL_LAST_NAMES)
        or spelled.split('.', 1)[0] in IMMUTABLE_CALL_MODULES
        or last_name in frozen_classes
    )


def _is_evidently_immutable(
    *, node: ast.expr, reported_names: set[str], frozen_classes: frozenset[str]
) -> bool:
    """Return whether a bound value is evidently immutable (rule 1)."""
    if isinstance(
        node,
        ast.Constant
        | ast.JoinedStr
        | ast.Attribute
        | ast.Subscript
        | ast.Lambda
        | ast.Compare
        | ast.BoolOp,
    ):
        return True
    if isinstance(node, ast.Name):
        return node.id not in reported_names
    operands: list[ast.expr] = []
    if isinstance(node, ast.Tuple):
        operands = [
            element.value if isinstance(element, ast.Starred) else element for element in node.elts
        ]
    elif isinstance(node, ast.UnaryOp):
        operands = [node.operand]
    elif isinstance(node, ast.BinOp):
        operands = [node.left, node.right]
    elif isinstance(node, ast.Call) and _dotted_name(node.func) in CAST_CALLS:
        # cast returns its value unchanged: as immutable as that value, which is its second
        # argument (an incomplete call is not read as one)
        if len(node.args) != CAST_ARGUMENT_COUNT:
            return False
        operands = [node.args[1]]
    elif isinstance(node, ast.Call):
        return _is_immutable_call(node=node, frozen_classes=frozen_classes)
    else:
        return False
    return all(
        _is_evidently_immutable(
            node=operand, reported_names=reported_names, frozen_classes=frozen_classes
        )
        for operand in operands
    )


def _bound_pairs(*, targets: list[ast.expr], value: ast.expr) -> Iterator[tuple[str, ast.expr]]:
    """Yield each bare name an assignment binds with the value it gets.

    ``a, b = 1, []`` pairs ``a`` with ``1`` and ``b`` with ``[]``; any other unpacking gives
    each name the whole value.
    """
    for target in targets:
        if (
            isinstance(target, ast.Tuple | ast.List)
            and isinstance(value, ast.Tuple | ast.List)
            and len(target.elts) == len(value.elts)
            and not any(isinstance(element, ast.Starred) for element in target.elts)
        ):
            for element, element_value in zip(target.elts, value.elts, strict=True):
                yield from _bound_pairs(targets=[element], value=element_value)
            continue
        for flat in _flattened_targets(target):
            if isinstance(flat, ast.Name):
                yield flat.id, value


class _BindingScan:
    """Rules 1 and 2: the module-level and class-body bindings of one module."""

    def __init__(
        self: _BindingScan,
        *,
        found: dict[str, int],
        frozen_classes: frozenset[str],
        written_tables: frozenset[str],
    ) -> None:
        self.found = found
        self.frozen_classes = frozen_classes
        self.written_tables = written_tables

    def scan(
        self: _BindingScan, *, statements: list[ast.stmt], prefix: str, reported_names: set[str]
    ) -> None:
        """Scan one scope's statements (a module's, or a class body's under its prefix)."""
        for statement in statements:
            if isinstance(statement, ast.ClassDef):
                self.scan(
                    statements=statement.body,
                    prefix=f'{prefix}{statement.name}.',
                    reported_names=set(reported_names),
                )
            elif isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef) or (
                isinstance(statement, ast.If) and _is_main_block(statement)
            ):
                continue
            elif isinstance(statement, ast.Assign):
                self._scan_binding(
                    pairs=_bound_pairs(targets=statement.targets, value=statement.value),
                    line=statement.lineno,
                    prefix=prefix,
                    reported_names=reported_names,
                )
            elif isinstance(statement, ast.AnnAssign):
                if statement.value is not None:
                    self._scan_binding(
                        pairs=_bound_pairs(targets=[statement.target], value=statement.value),
                        line=statement.lineno,
                        prefix=prefix,
                        reported_names=reported_names,
                    )
            else:
                self.scan(
                    statements=list(_child_statements(statement)),
                    prefix=prefix,
                    reported_names=reported_names,
                )

    def _scan_binding(
        self: _BindingScan,
        *,
        pairs: Iterator[tuple[str, ast.expr]],
        line: int,
        prefix: str,
        reported_names: set[str],
    ) -> None:
        """Report each name a binding gives a value rule 1 or 2 reports."""
        for name, value in pairs:
            if name in UNREPORTED_BINDINGS:
                continue
            if CONSTANT_NAME.fullmatch(name) and _is_table_display(value):
                is_reported = name in self.written_tables
            else:
                is_reported = not _is_evidently_immutable(
                    node=value, reported_names=reported_names, frozen_classes=self.frozen_classes
                )
            if is_reported:
                reported_names.add(name)
                _report(found=self.found, name=f'{prefix}{name}', line=line)


def _first_type_member(annotation: ast.expr | None) -> str | None:
    """Return the class a ``type[...]`` annotation (alone or in a union) names, else None."""
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        return _first_type_member(ast.parse(annotation.value, mode='eval').body)
    if isinstance(annotation, ast.BinOp):
        return _first_type_member(annotation.left) or _first_type_member(annotation.right)
    if not isinstance(annotation, ast.Subscript):
        return None
    if _last_name(annotation.value) == 'type':
        return ast.unparse(annotation.slice)
    if _last_name(annotation.value) in {'Union', 'Optional'}:
        members = (
            annotation.slice.elts if isinstance(annotation.slice, ast.Tuple) else [annotation.slice]
        )
        for member in members:
            annotated = _first_type_member(member)
            if annotated is not None:
                return annotated
    return None


def _imported_names(tree: ast.Module) -> frozenset[str]:
    """Return every name an import binds in a module (a module, or a name from one)."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return frozenset(names)


def _is_receiver_self(node: ast.expr) -> bool:
    """Return whether an expression is the name ``self``."""
    return isinstance(node, ast.Name) and node.id == 'self'


class _WriteScan(ast.NodeVisitor):
    """Rules 3, 4 and 5: globals, writes to class objects and process-wide caches."""

    def __init__(
        self: _WriteScan, *, found: dict[str, int], imported_names: frozenset[str]
    ) -> None:
        self.found = found
        self.imported_names = imported_names
        self.scope: list[str] = []
        self.classes: list[str] = []
        # One mapping per enclosing function: each ``type[...]`` parameter -> its class
        self.type_parameters: list[dict[str, str]] = []

    def visit_ClassDef(self: _WriteScan, node: ast.ClassDef) -> None:
        """Scan a class body, inside its name."""
        self.scope.append(node.name)
        self.classes.append('.'.join(self.scope))
        self.generic_visit(node)
        self.classes.pop()
        self.scope.pop()

    def visit_FunctionDef(self: _WriteScan, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Report a cached function (rule 5), then scan its body with its type parameters."""
        for decorator in node.decorator_list:
            decorated_by = decorator.func if isinstance(decorator, ast.Call) else decorator
            if _dotted_name(decorated_by) in CACHE_DECORATORS:
                _report(found=self.found, name='.'.join([*self.scope, node.name]), line=node.lineno)
        arguments = node.args
        parameters = [
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
            *(argument for argument in (arguments.vararg, arguments.kwarg) if argument is not None),
        ]
        annotated_classes = {
            parameter.arg: annotated
            for parameter in parameters
            if (annotated := _first_type_member(parameter.annotation)) is not None
        }
        self.scope.append(node.name)
        self.type_parameters.append(annotated_classes)
        self.generic_visit(node)
        self.type_parameters.pop()
        self.scope.pop()

    def visit_AsyncFunctionDef(self: _WriteScan, node: ast.AsyncFunctionDef) -> None:
        """Scan an ``async def`` as a ``def``."""
        self.visit_FunctionDef(node)

    def visit_If(self: _WriteScan, node: ast.If) -> None:
        """Scan an ``if``, except a script's ``__main__`` block (never run on import)."""
        if not _is_main_block(node):
            self.generic_visit(node)

    def visit_Global(self: _WriteScan, node: ast.Global) -> None:
        """Report every name a ``global`` statement names (rule 3)."""
        for name in node.names:
            _report(found=self.found, name=name, line=node.lineno)

    def _enclosing_class(self: _WriteScan, *, otherwise: str) -> str:
        """Return the innermost enclosing class's qualified name, else ``otherwise``."""
        return self.classes[-1] if self.classes else otherwise

    def _named_class_receiver(self: _WriteScan, node: ast.Name) -> str | None:
        """Return the class a name receiver is: ``cls``, a ``type[...]`` parameter, a class name."""
        if node.id == 'cls':
            return self._enclosing_class(otherwise='cls')
        for annotated_classes in reversed(self.type_parameters):
            if node.id in annotated_classes:
                return annotated_classes[node.id]
        if CAPITALIZED_NAME.fullmatch(node.id) and not CONSTANT_NAME.fullmatch(node.id):
            return node.id
        return None

    def _class_receiver(self: _WriteScan, node: ast.expr) -> str | None:
        """Return the class an attribute write's receiver is (rule 4), else None."""
        if isinstance(node, ast.Name):
            return self._named_class_receiver(node)
        instance: ast.expr | None = None
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == 'type'
            and len(node.args) == 1
        ):
            instance = node.args[0]
        elif isinstance(node, ast.Attribute) and node.attr == '__class__':
            instance = node.value
        if instance is None:
            return None
        spelled = ast.unparse(node)
        return self._enclosing_class(otherwise=spelled) if _is_receiver_self(instance) else spelled

    def _module_receiver(self: _WriteScan, node: ast.expr) -> str | None:
        """Return an imported module (or an attribute of one) a ``setattr`` writes, else None."""
        root = node
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name) and root.id in self.imported_names:
            return _dotted_name(node)
        return None

    def _report_class_attribute_writes(self: _WriteScan, *, node: ast.stmt) -> None:
        """Report each target of a statement that stores a class's attribute (rule 4).

        Inside a function the receiver is a class object; at import time (outside every
        function) an imported module, or an attribute of one, too.
        """
        at_import = not self.type_parameters
        for target in _assignment_targets(node):
            if isinstance(target, ast.Attribute):
                receiver = self._class_receiver(target.value)
                if receiver is None and at_import:
                    receiver = self._module_receiver(target.value)
                if receiver is not None:
                    _report(found=self.found, name=f'{receiver}.{target.attr}', line=target.lineno)

    def visit_Assign(
        self: _WriteScan, node: ast.Assign | ast.AnnAssign | ast.AugAssign | ast.Delete
    ) -> None:
        """Report a write to a class object's attribute (rule 4)."""
        self._report_class_attribute_writes(node=node)
        self.generic_visit(node)

    def visit_AnnAssign(self: _WriteScan, node: ast.AnnAssign) -> None:
        """Report a write to a class object's attribute (rule 4)."""
        self.visit_Assign(node)

    def visit_AugAssign(self: _WriteScan, node: ast.AugAssign) -> None:
        """Report a write to a class object's attribute (rule 4)."""
        self.visit_Assign(node)

    def visit_Delete(self: _WriteScan, node: ast.Delete) -> None:
        """Report a deleted class object's attribute (rule 4)."""
        self.visit_Assign(node)

    def visit_Call(self: _WriteScan, node: ast.Call) -> None:
        """Report a ``setattr``/``delattr`` on a class object or a module (rule 4)."""
        if isinstance(node.func, ast.Name) and node.func.id in ATTRIBUTE_WRITERS and node.args:
            receiver = self._class_receiver(node.args[0]) or self._module_receiver(node.args[0])
            if receiver is not None:
                _report(found=self.found, name=f'setattr({receiver})', line=node.lineno)
        self.generic_visit(node)


def process_state_in_source(
    *,
    source_path: Path,
    frozen_classes: frozenset[str],
    written_tables: frozenset[str] | None = None,
) -> dict[str, int]:
    """Return the process state one file holds, by the five rules.

    Args:
        source_path: The file to scan.
        frozen_classes: The scanned classes whose instances are immutable
            (``frozen_class_names``).
        written_tables: The names written through anywhere in the scanned files
            (``written_table_names``); None reads only this file's writes.

    Returns:
        Each finding's qualified name (``name``, ``Class.name``, ``Outer.Inner.name``,
        ``setattr(module)``) and its first line.

    """
    tree = ast.parse(source_path.read_text(encoding='utf-8'))
    if written_tables is None:
        written_tables = frozenset(_tables_written_in(tree))
    found: dict[str, int] = {}
    _BindingScan(found=found, frozen_classes=frozen_classes, written_tables=written_tables).scan(
        statements=tree.body, prefix='', reported_names=set()
    )
    _WriteScan(found=found, imported_names=_imported_names(tree)).visit(tree)
    return found


def scanned_process_state(*, project_root: Path) -> dict[str, dict[str, int]]:
    """Return the process state in the engine's and every member's source, by allowlist key.

    Args:
        project_root: The repository.

    Returns:
        Allowlist key -> {qualified name: first line}, for every file with a finding.

    """
    scanned = scanned_source_files(project_root=project_root)
    source_paths = [source_path for _, source_path in scanned]
    frozen_classes = frozen_class_names(source_paths=source_paths)
    written_tables = written_table_names(source_paths=source_paths)
    found_by_key: dict[str, dict[str, int]] = {}
    for key, source_path in scanned:
        found = process_state_in_source(
            source_path=source_path, frozen_classes=frozen_classes, written_tables=written_tables
        )
        if found:
            found_by_key[key] = found
    return found_by_key


# The reasons several listings share
API_SERVER = "R11: the sprite API server's (not a game's): one server per process, configured once."
EVENT_TYPE_TABLE = (
    "R15: the engine's event types, computed from pygame at import and never written; one "
    'pygame per process, so the same in every context.'
)
DRAWING_CACHE = (
    "R14: the game's own drawing cache, each picture computed from its arguments alone and "
    'never drawn on.'
)
CATALOG_BUILD = (
    'R16: an instrument build (functools.partial of a module function with constant '
    'arguments), immutable though the rules cannot prove it.'
)
CATALOG_SERIES = (
    'R16: a harmonic series, a tuple of floats computed at import from constants; the rules '
    'cannot prove a function returns a tuple.'
)
DEFAULT_COLOR = (
    'R2: a colour constant, a tuple made by _to_rgb or _to_rgba from the default palette.'
)
BITMAPPY_STATE = (
    "C16: Bitmappy's own state, one Bitmappy per process; a Bitmappy demo tile would need it "
    'per context (the audit leaves it open).'
)

# Every piece of process state the scan finds, by allowlist key (the engine's files keyed from
# src/glitchygames/, a member's from the repository), each with its audit row and why it may be
# shared; the audit is plans/2026-10-25-engine-context.md. Rows R16, R17, S18, S19 and S20 are
# new (Task 13), added to the audit by Task 16
PROCESS_STATE: dict[str, dict[str, str]] = {
    'ai_introspection.py': {
        'SCALAR_CONVERSIONS': (
            'R16: a tuple of (types, lambda or function) pairs; immutable, but it calls '
            'type(None), which the rules do not list.'
        ),
    },
    'ai_link.py': {
        'DEFAULT_INSTALL_ROOT': (
            "R16: a Path (the user's home directory joined with constants), immutable; the "
            'rules cannot prove Path.home() returns one.'
        ),
    },
    'api/dependencies.py': {
        'get_config': API_SERVER,
        'get_sprite_generation_service': API_SERVER,
        'get_renderer_service': API_SERVER,
    },
    'api/main.py': {'app': API_SERVER},
    'api/routes/health.py': {'router': API_SERVER},
    'api/routes/sprites.py': {'router': API_SERVER, 'ALLOWED_OUTPUT_ROOT': API_SERVER},
    'audio/assets.py': {
        '_CACHE': (
            'R17: loaded sound files (frozen SoundFile) by path, reloaded when the file changes; '
            'a value computed from its key, one cache per process.'
        ),
        '_DEFINITIONS_CACHE': (
            "R17: a sound file's parsed definitions (frozen _Definitions) by path, reloaded when "
            'the file changes; a value computed from its key, one cache per process.'
        ),
    },
    'audio/engine.py': {
        'SYSTEM_OWNER': (
            "R16: the engine's own voices' owner, an identity sentinel with no state; every "
            'context compares against the same one.'
        ),
    },
    'audio/instruments/bowed_strings.py': {
        'VIOLIN': CATALOG_BUILD,
        'VIOLA': CATALOG_BUILD,
        'CELLO': CATALOG_BUILD,
        'DOUBLE_BASS': CATALOG_BUILD,
        'VIOL': CATALOG_BUILD,
        'FOLK_FIDDLE': CATALOG_BUILD,
        'SPIKE_FIDDLE': CATALOG_BUILD,
    },
    'audio/instruments/brass.py': {
        'HARMON_LEVELS': CATALOG_SERIES,
        'STRAIGHT_MUTE_LEVELS': CATALOG_SERIES,
        'CUP_MUTE_LEVELS': CATALOG_SERIES,
        'TRUMPET': CATALOG_BUILD,
        'CORNET': CATALOG_BUILD,
        'FLUGELHORN': CATALOG_BUILD,
        'HORN': CATALOG_BUILD,
        'TENOR_BRASS': CATALOG_BUILD,
        'TROMBONE': CATALOG_BUILD,
        'TUBA': CATALOG_BUILD,
        'NATURAL': CATALOG_BUILD,
        'WOODEN_LIP_REED': CATALOG_BUILD,
    },
    'audio/instruments/flutes.py': {
        'METAL_FLUTE': CATALOG_BUILD,
        'WOODEN_FLUTE': CATALOG_BUILD,
        'RECORDER': CATALOG_BUILD,
        'WHISTLE': CATALOG_BUILD,
        'END_BLOWN': CATALOG_BUILD,
        'VESSEL': CATALOG_BUILD,
    },
    'audio/instruments/organs.py': {
        'PRINCIPAL_LEVELS': CATALOG_SERIES,
        'REED_STOP_LEVELS': CATALOG_SERIES,
        'STRING_STOP_LEVELS': CATALOG_SERIES,
    },
    'audio/instruments/percussion.py': {
        'GLOCKENSPIEL': CATALOG_BUILD,
        'XYLOPHONE': CATALOG_BUILD,
        'MARIMBA': CATALOG_BUILD,
        'VIBRAPHONE': CATALOG_BUILD,
        'GAMELAN_METALLOPHONE': CATALOG_BUILD,
        'KETTLE_GONG': CATALOG_BUILD,
        'HARMONIC_PAN': CATALOG_BUILD,
    },
    'audio/instruments/plucked_strings.py': {
        'NYLON_GUITAR': CATALOG_BUILD,
        'STEEL_GUITAR': CATALOG_BUILD,
        'ELECTRIC_BASS': CATALOG_BUILD,
        'LUTE': CATALOG_BUILD,
        'BRIGHT_LUTE': CATALOG_BUILD,
        'BUZZING_LUTE': CATALOG_BUILD,
        'SHORT_LUTE': CATALOG_BUILD,
    },
    'audio/instruments/registry.py': {
        '_built': (
            'R17: each catalog instrument built once per process (CLAUDE.md, Instrument '
            'catalog), a frozen Instrument computed from its name alone.'
        ),
    },
    'audio/instruments/timbres.py': {
        'HARMONIC_FIELD_NAMES': (
            'R16: a tuple of strings, its harmonics unpacked from a generator expression, '
            'which the rules do not read.'
        ),
        'HIGHEST_HARMONIC': 'R16: an int, the length of HARMONIC_FIELD_NAMES.',
    },
    'audio/instruments/voices.py': {
        '_VOICE_BUILDS': (
            'R16: a tuple of frozen CatalogEntry values, unpacked from a function the rules '
            'cannot read.'
        ),
        '_CHOIR_BUILDS': (
            'R16: a tuple of frozen CatalogEntry values, returned by a function the rules '
            'cannot read.'
        ),
        # The rules treat a name bound to a reported name as reported (reported_names), so the
        # concatenations are reported because _VOICE_BUILDS and _CHOIR_BUILDS are: each is those
        # reasoned tuples plus a literal tuple of frozen CatalogEntry values
        'VOICES': (
            'R16: _VOICE_BUILDS (above) plus the voice sound-alikes, both tuples of frozen '
            'CatalogEntry values; reported only because _VOICE_BUILDS is.'
        ),
        'CHOIRS': (
            'R16: _CHOIR_BUILDS (above) plus the choir sound-alikes, both tuples of frozen '
            'CatalogEntry values; reported only because _CHOIR_BUILDS is.'
        ),
    },
    'audio/instruments/winds.py': {
        'FREE_REED_LEVELS': CATALOG_SERIES,
    },
    'audio/library.py': {
        'ENGINE_SOUND_CACHE': (
            "R17: the engine's own sounds' compiled, read-only samples by identity key, one "
            'cache per process by design (the owner, 2026-11-02; CLAUDE.md, Scene backgrounds).'
        ),
    },
    'audio/pitch.py': {
        '_warned_hertz_values': (
            'S20: not yet per context: the out-of-range frequencies already warned about, so a '
            'second context never warns about a value the first did (an open audit row).'
        ),
    },
    'audio/render.py': {
        '_lfsr_sequence': (
            "R17: one period of an LFSR's output by its bits and taps, a read-only array "
            'computed from its key alone.'
        ),
        '_anti_alias_kernel': (
            'R17: the oversampling low-pass kernel by sample rate, a read-only array computed '
            'from its key alone.'
        ),
    },
    'audio/voices.py': {
        '_partitioned_mixer': (
            "S3: the mixer's channel partition (its channel count and reserved channels), "
            "pygame's one mixer per process; it replaced audio/live.py's channel counts."
        ),
    },
    'backgrounds.py': {
        'background_pattern_surface': (
            'R7: the background pattern by (pattern, size), copied by every reader and never '
            'drawn on.'
        ),
    },
    'build_info.py': {
        'package_source_revision': 'R6: the source revision of a package; one checkout.',
        'engine_source_revision': "R6: the engine's source revision; one checkout.",
    },
    'clipboard.py': {
        '_REGISTRY': "S9: the player's clipboard; the browser page installs its own.",
    },
    'code_tree.py': {
        '_LANDED_COMMIT_CODE_TREES': (
            "R6: a commit's code tree by (repository, commit, paths), which never changes; one "
            "checkout, a tool's cache, never a game's."
        ),
    },
    'color/constants.py': {
        '_default_colors': 'R2: the default palette the colour constants are read from.',
        'YELLOW': DEFAULT_COLOR,
        'PURPLE': DEFAULT_COLOR,
        'BLUE': DEFAULT_COLOR,
        'GREEN': DEFAULT_COLOR,
        'WHITE': DEFAULT_COLOR,
        'BLACK': DEFAULT_COLOR,
        'BLACKLUCENT': DEFAULT_COLOR,
        'BLUELUCENT': DEFAULT_COLOR,
        'RED': DEFAULT_COLOR,
    },
    'debug/panels.py': {
        '_BACKING_SURFACES': 'R8: identical blank text backings by size.',
    },
    'engine/game_engine.py': {
        'GameEngine.icon': "S2: the window's icon, a window service of the one display.",
        'GameEngine.PYGAME_FOUND_WITH_SDL_SIGNAL_HANDLERS': (
            "S8: whether this process's pygame started with SDL's signal handlers; one pygame "
            "per process (the controller's ruling, 2026-10-29)."
        ),
        'GameEngine.USE_FASTEVENTS': "R12: decided once by the installed pygame's version.",
    },
    'engine_context.py': {
        '_DECLARED_SLOTS': 'R13: the declared context slots, written once per slot at import.',
        '_DEFAULT_CONTEXT': 'R13: the default context, the mechanism itself.',
    },
    'events/base.py': {
        'pygame_event_names': (
            "R15: pygame's compiled event names, an immutable table scanned once per process, "
            "the same in every context (the controller's ruling, 2026-10-29)."
        ),
        '_NAMED_CUSTOM_EVENT_TYPES': (
            "S18: pygame's custom event types by name; pygame allocates them once per process, "
            "and each name is registered once, at its module's import."
        ),
        'FPSEVENT': EVENT_TYPE_TABLE,
        'GAMEEVENT': EVENT_TYPE_TABLE,
        'MENUEVENT': EVENT_TYPE_TABLE,
        'AUDIO_EVENTS': EVENT_TYPE_TABLE,
        'APP_EVENTS': EVENT_TYPE_TABLE,
        'CONTROLLER_EVENTS': EVENT_TYPE_TABLE,
        'DROP_EVENTS': EVENT_TYPE_TABLE,
        'TOUCH_EVENTS': EVENT_TYPE_TABLE,
        'JOYSTICK_EVENTS': EVENT_TYPE_TABLE,
        'KEYBOARD_EVENTS': EVENT_TYPE_TABLE,
        'MIDI_EVENTS': EVENT_TYPE_TABLE,
        'MOUSE_EVENTS': EVENT_TYPE_TABLE,
        'TEXT_EVENTS': EVENT_TYPE_TABLE,
        'WINDOW_EVENTS': EVENT_TYPE_TABLE,
        'ALL_EVENTS': EVENT_TYPE_TABLE,
        'GAME_EVENTS': EVENT_TYPE_TABLE,
        'HashableEvent._hashing_ids': (
            'S13: a recursion guard, empty between calls, so empty whenever a context switch can '
            'happen.'
        ),
        'HashableEvent._comparing_ids': (
            'S13: a recursion guard, empty between calls, so empty whenever a context switch can '
            'happen.'
        ),
    },
    'events/midi.py': {'MIDI_MODULE': "R5: an import's result, the same in every context."},
    'fonts/font_manager.py': {
        'FontManager._font_cache': (
            'R9: fonts by their settings, one cache per process (the owner, 2026-10-25).'
        ),
    },
    'input/devices.py': {
        '_SDL_CONTROLLER_MODULE': "R5: an import's result, the same in every context.",
    },
    'input/state.py': {
        '_SCANCODE_OF_KEY_CODE': 'R3: an immutable scancode table built at import.',
    },
    'machine_state.py': {
        'current_machine_state': "R6: this machine's description; one machine per process.",
    },
    'replay/silence.py': {
        '_MUSIC_FOLLOWING': (
            "S4: what follows pygame's one music stream while a replay silences it."
        ),
        'setattr(pygame.mixer.music)': (
            "S4: replaces pygame.mixer.music's pause and unpause, the process's one music stream."
        ),
    },
    'replay/tools/scripted_sessions.py': {
        'setattr(live_sources)': (
            "S17: a recording tool's temporary swap of glitchygames.live_sources' "
            'capture_live_snapshot, restored in a finally; record-session records one game in '
            'its own process, never inside a game or an inner context.'
        ),
    },
    'replay/tools/settings.py': {
        'ProjectSettings.recording_renames': (
            'R12: a pydantic field default, copied per instance.'
        ),
    },
    'replay/viewer.py': {
        '_SLEEP_TIMER': (
            "S12: the outer viewer's FastTimer and its sleep model; it holds no game state."
        ),
    },
    'services/renderer_service.py': {
        'RendererService.pygame_initialized': (
            "S16: whether the API server's renderer started pygame, the process's."
        ),
    },
    'sprites/bitmappy_sprite.py': {
        'BitmappySprite.DEFAULT_SURFACE': 'R12: a class default nothing draws on.',
        'BitmappySprite._get_pixel_string': (
            "R12: a method attached to the class at the module's import, a function never rebound."
        ),
        'BitmappySprite._get_color_map': (
            "R12: a method attached to the class at the module's import, a function never rebound."
        ),
    },
    'state/manager.py': {
        '_DISK_SAVE_CHANGE_OBSERVERS': (
            "S11: the browser's IndexedDB flush; demo contexts use MemorySaveManager and never "
            'call it.'
        ),
    },
    'testing/frame_comparison.py': {
        'DriverComparison.frames_vary': 'R12: a pydantic field default, copied per instance.',
    },
    'user_files.py': {
        '_REGISTRY': "S10: the browser's file picker and downloads, the player's.",
    },
    'world.py': {
        '_scenes_warned_about_double_update': (
            'S14: scenes already warned (weak); keyed by scene, so per context in effect.'
        ),
    },
    'src/apps/bitmappy/src/bitmappy/ai_manager.py': {
        '_RUNNING_AI_MANAGERS': (
            "S15: Bitmappy's running AI workers (weak), all shut down at exit."
        ),
        '_AI_REQUEST_COUNTER': "S15: Bitmappy's AI request ids, unique across the process.",
    },
    'src/apps/bitmappy/src/bitmappy/constants.py': {'ai_training_state': BITMAPPY_STATE},
    'src/apps/bitmappy/src/bitmappy/controllers/manager.py': {
        'MultiControllerManager._instance': BITMAPPY_STATE,
    },
    'src/apps/bitmappy/src/bitmappy/masterhub.py': {
        '_REGISTRY': (
            "S19: Bitmappy's MasterHUB installer, registered by the browser page (the player's, "
            'as S9 and S10 are).'
        ),
    },
    'src/apps/bitmappy/src/bitmappy/onion_skinning.py': {'onion_skinning_manager': BITMAPPY_STATE},
    'src/apps/bitmappy/src/bitmappy/pixel_sprite.py': {
        'BitmapPixelSprite.PIXEL_CACHE': "R10: Bitmappy's pixel surfaces by colour and size.",
    },
    'src/demos/sound-board-demo/src/sound_board_demo/__init__.py': {
        'STEPS_PER_ROW': 'R16: an int, the length of a tuple of scancodes.',
    },
    'src/games/brave-adventurer/src/brave_adventurer/player.py': {
        '_COMMON_POSE_X_RANGES': (
            "R14: the game's own cache of the x-span every pose frame shares, by facing."
        ),
    },
    'src/games/brave-adventurer/src/brave_adventurer_core/drawing.py': {
        '_vertical_gradient_cache': DRAWING_CACHE,
    },
    'src/games/clockwork-keep/src/clockwork_keep/levels.py': {
        'FLOOR_BOILER_ROOM': "R14: the game's floor table (a FloorData), never written.",
        'FLOOR_GEAR_WORKS': "R14: the game's floor table (a FloorData), never written.",
        'FLOOR_CLOCK_FACE': "R14: the game's floor table (a FloorData), never written.",
    },
    'src/games/drawing-fire/src/drawing_fire/drawing.py': {
        'text_surface': DRAWING_CACHE,
        '_banner_surface': DRAWING_CACHE,
    },
    'src/games/drawing-fire/src/drawing_fire/game.py': {
        'SCANCODE_NAMES': "R14: the game's table of scancode names, built at import.",
    },
    'src/games/mr-muncher/src/mr_muncher/drawing.py': {
        'maze_picture': DRAWING_CACHE,
        'player_picture': DRAWING_CACHE,
        'player_dying_picture': DRAWING_CACHE,
        'muncher_picture': DRAWING_CACHE,
        'frightened_muncher_picture': DRAWING_CACHE,
        'eyes_picture': DRAWING_CACHE,
        'sprocket_picture': DRAWING_CACHE,
        'snack_picture': DRAWING_CACHE,
        'bonus_reel_picture': DRAWING_CACHE,
        'film_strip_panel': DRAWING_CACHE,
    },
    'src/games/mr-muncher/src/mr_muncher/game.py': {
        'shared_sound_bank': "R14: the game's sound bank, built once from its recipes.",
    },
    'src/games/mr-muncher/src/mr_muncher/sounds.py': {
        'CRUNCH_ONE': "R14: one of the game's sound recipes, never written.",
        'CRUNCH_TWO': "R14: one of the game's sound recipes, never written.",
        'CRUNCH_RECIPES': "R14: a tuple of the game's sound recipes, never written.",
        'ALL_RECIPES': "R14: a tuple of the game's sound recipes, never written.",
    },
}
# Each listing's reason begins with its audit row's name and a colon
AUDIT_ROW_REASON = re.compile(r'(S\d+|R\d+|C16): .+')

PLANTED_PROCESS_STATE = """\
import functools
import itertools
from typing import NamedTuple

import numpy as np
import numpy.typing as npt

from glitchygames.engine_context import ContextSlot
from glitchygames.read_only_views import ClassOnlyView, ReadOnlyView, ReadOnlyViews

LIMIT = 3
NAMES = ('a', 'b')
TABLE = {'a': 1}
WRITTEN_TABLE = {'a': 1}
cache_of_drawings = {}
COUNTER = itertools.count()
SLOT = ContextSlot(name='planted.slot', factory=dict)


class Point(NamedTuple):
    x: int


ORIGIN = Point(x=0)


class Holder:
    DEFAULTS = ()
    instances = []
    count = 0

    @classmethod
    def made(cls):
        cls.count += 1


def remember(key):
    global last_key
    last_key = key
    WRITTEN_TABLE[key] = 2


@functools.cache
def picture(size):
    return size


FloatArray = npt.NDArray[np.float64]
COUNT_SLOT = vars(Holder)['count']
ALIAS = cache_of_drawings


class Rebinder:
    def touch(self, game: type[Holder] | Holder):
        type(self).touched = True
        self.__class__.seen = True
        setattr(Rebinder, 'flag', True)
        game.options = {}


class PlantedMeta(type):
    @property
    def computed(cls):
        return LIMIT


class Viewed(metaclass=ReadOnlyViews):
    SHOWN = ReadOnlyView(
        read_current=lambda owner: LIMIT, read_own=lambda viewed: LIMIT, write_instead='nowhere'
    )
    kept = ClassOnlyView(read_current=lambda owner: None, write_instead='nowhere')


def __getattr__(name):
    if name == 'manager':
        return LIMIT
    raise AttributeError(name)
"""


def test_the_process_state_scan_finds_every_kind(tmp_path):
    """Mutable bindings, written tables, objects, rebound class names, globals and caches.

    Never a view: the class's ReadOnlyView and ClassOnlyView, a metaclass property and the module
    __getattr__ store nothing.
    """
    source_path = tmp_path / 'planted.py'
    source_path.write_text(PLANTED_PROCESS_STATE, encoding='utf-8')
    frozen = frozen_class_names(source_paths=[source_path])

    found = process_state_in_source(source_path=source_path, frozen_classes=frozen)

    assert set(found) == {
        'WRITTEN_TABLE',
        'cache_of_drawings',
        'COUNTER',
        'Holder.instances',
        'Holder.count',
        'last_key',
        'picture',
        'ALIAS',
        'Rebinder.touched',
        'Rebinder.seen',
        'setattr(Rebinder)',
        'Holder.options',
    }


FROZEN_SETTINGS_SOURCE = """\
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    size: int = 0
"""

MUTABLE_SETTINGS_SOURCE = """\
class Settings:
    def __init__(self):
        self.size = 0


SETTINGS = Settings()
"""


def test_a_class_name_also_defined_unfrozen_is_not_trusted(tmp_path):
    """Two files define ``Settings``, one frozen: an instance of the mutable one is reported."""
    frozen_path = tmp_path / 'frozen_settings.py'
    frozen_path.write_text(FROZEN_SETTINGS_SOURCE, encoding='utf-8')
    mutable_path = tmp_path / 'mutable_settings.py'
    mutable_path.write_text(MUTABLE_SETTINGS_SOURCE, encoding='utf-8')
    frozen = frozen_class_names(source_paths=[frozen_path, mutable_path])

    found = process_state_in_source(source_path=mutable_path, frozen_classes=frozen)

    assert 'Settings' not in frozen
    assert found == {'SETTINGS': 6}


IMPORT_TIME_WRITES_SOURCE = """\
import other

from elsewhere import Other

other.Thing.attr = 1
Other.flag = True
other.setting = 2
LOCAL = 3
"""


def test_an_import_time_write_to_a_class_or_a_module_is_reported(tmp_path):
    """Rule 4 at module scope: a class's or an imported module's attribute stored at import."""
    source_path = tmp_path / 'import_time_writes.py'
    source_path.write_text(IMPORT_TIME_WRITES_SOURCE, encoding='utf-8')

    found = process_state_in_source(source_path=source_path, frozen_classes=frozenset())

    assert found == {'other.Thing.attr': 5, 'Other.flag': 6, 'other.setting': 7}


CAST_SOURCE = """\
from typing import cast

HIDDEN = cast(dict, {})
hidden_list = cast('list[int]', [])
SHOWN = cast(int, 3)
NAMED = cast('tuple[str, ...]', ('a', 'b'))
"""


def test_a_cast_is_as_immutable_as_its_value(tmp_path):
    """``cast`` returns its value unchanged, so it is immutable only when that value is."""
    source_path = tmp_path / 'casts.py'
    source_path.write_text(CAST_SOURCE, encoding='utf-8')

    found = process_state_in_source(source_path=source_path, frozen_classes=frozenset())

    assert found == {'HIDDEN': 3, 'hidden_list': 4}


MAIN_BLOCK_SOURCE = """\
import sys

if __name__ == '__main__':
    arguments = list(sys.argv)
    seen = []
"""


def test_a_scripts_main_block_is_not_scanned(tmp_path):
    """What a module binds when it runs as a script is never bound on import."""
    source_path = tmp_path / 'script.py'
    source_path.write_text(MAIN_BLOCK_SOURCE, encoding='utf-8')

    assert process_state_in_source(source_path=source_path, frozen_classes=frozenset()) == {}


def test_process_state_in_a_member_is_reported_under_its_repository_path(tmp_path):
    """A member's file is keyed by its path from the repository."""
    key = write_project_with_member_module(project_root=tmp_path, source='seen = []\n')

    assert scanned_process_state(project_root=tmp_path) == {key: {'seen': 1}}


def test_every_piece_of_process_state_is_in_the_audit():
    """A new module- or class-level mutable, rebinding, global or cache fails until listed."""
    found = scanned_process_state(project_root=PROJECT_ROOT)
    unlisted = {
        f'{key}: {name} (line {line})'
        for key, names in found.items()
        for name, line in names.items()
        if name not in PROCESS_STATE.get(key, {})
    }

    assert unlisted == set()


def test_every_listed_piece_of_process_state_still_exists():
    """A listing the scan no longer finds (moved into a context, or gone) fails until removed."""
    found = scanned_process_state(project_root=PROJECT_ROOT)
    stale = {
        f'{key}: {name}'
        for key, names in PROCESS_STATE.items()
        for name in names
        if name not in found.get(key, {})
    }

    assert stale == set()


def test_every_listing_names_its_audit_row():
    """Every reason begins with its audit row (plans/2026-10-25-engine-context.md)."""
    unnamed = {
        f'{key}: {name}'
        for key, names in PROCESS_STATE.items()
        for name, reason in names.items()
        if AUDIT_ROW_REASON.fullmatch(reason) is None
    }

    assert unnamed == set()
