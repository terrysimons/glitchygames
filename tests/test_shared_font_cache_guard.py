"""Nothing restyles a shared cached font in place (the audit's R9; decision 2).

Decision 2 of plans/2026-10-25-engine-context.md, as sub-plan 2
(plans/2026-10-27-engine-context-2-engine-state.md) quotes it: "The font caches (R9) stay shared,
one per process, with a guard test that nothing changes a cached font's style (bold, italic,
underline, size) in place. Owned by sub-plan 2."

Fonts come from ``FontManager``'s one cache per process (``FontManager._font_cache`` and
``RENDER_CACHE``, glitchygames.fonts.font_manager), shared by every engine context. A font
restyled in place would restyle it for every context's text, so a font is styled per render call
(``render(..., style=...)``) or a separate font is asked for, never changed. This scans the
engine's and every workspace member's source (tests/workspace_sources.py) and reports, as
``'<line>: <what>'``:

1. A call of one of ``FONT_STYLE_SETTERS`` (pygame-ce ``pygame.font.Font``'s setters; their
   names are distinctive) on anything, reported by the setter's name.
2. On a receiver whose dotted name contains ``font`` (any case: ``font``, ``self.title_font``,
   ``label_font``, ``label.font``): an assignment, augmented assignment or ``del`` of one of
   ``FONT_STYLE_ATTRIBUTES`` or ``FONT_SIZE_ATTRIBUTES``, reported by the attribute's name, and a
   ``setattr``/``delattr`` call, reported as ``setattr``/``delattr``. The attribute names are
   generic (``self.strength`` is the gravity behaviour's acceleration,
   glitchygames.physics.behaviors; ``rect.size`` is a ``Rect``'s), hence the receiver condition.

There is no allowlist. The one thing not reported is building a font: a style change on a local
name that its function (or the module) binds only to a new font (a call of one of
``FONT_CONSTRUCTORS``: ``pygame.font.Font``, ``pygame.freetype.SysFont``, ...), made before the
name is read in any other way (before it is returned, cached or handed on). A parameter's name,
a name also bound to anything else and a name a nested function reaches are never a new font's.
That font is no one else's yet: FontManager styles the fonts it makes before it caches them
(pygame.font.Font and pygame.freetype.Font take no style in their constructors). A style change
after the name is read otherwise (the font cached, then restyled) is reported.

What an AST scan cannot see: a font reached through a name without ``font`` in it (``label =
FontManager.font(); label.strong = True``), a style change in a loop that runs again after a
read written below it (the order is the source's), and ``exec``.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from tests.ast_scanning import PROJECT_ROOT
from tests.workspace_sources import scanned_source_files

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

# pygame-ce pygame.font.Font's style setters (rule 1)
FONT_STYLE_SETTERS = frozenset({
    'set_bold',
    'set_italic',
    'set_underline',
    'set_strikethrough',
    'set_point_size',
    'set_script',
    'set_direction',
})
# The attributes that change how a font renders (rule 2): pygame.font.Font's, then
# pygame.freetype.Font's
FONT_STYLE_ATTRIBUTES = frozenset({
    'bold',
    'italic',
    'underline',
    'strikethrough',
    'outline',
    'align',
    'style',
    'strong',
    'oblique',
    'wide',
    'strength',
    'underline_adjustment',
    'antialiased',
    'kerning',
    'vertical',
    'rotation',
    'fgcolor',
    'bgcolor',
    'pad',
    'origin',
    'ucs4',
    'use_bitmap_strikes',
})
# The attributes that change a font's size (rule 2): pygame.font.Font's, then pygame.freetype.Font's
FONT_SIZE_ATTRIBUTES = frozenset({'point_size', 'size'})
# The calls that make a new font, by their last name (pygame.font.Font, pygame.font.SysFont,
# pygame.freetype.Font, pygame.freetype.SysFont): styling one before it is read otherwise is
# building it
FONT_CONSTRUCTORS = frozenset({'Font', 'SysFont'})
# The calls that change an attribute named by a string (rule 2)
ATTRIBUTE_WRITING_CALLS = frozenset({'setattr', 'delattr'})
# What a receiver's dotted name contains to be a font's (rule 2), lowercased
FONT_RECEIVER_MARK = 'font'
# The nodes that open a scope of their own (each is scanned apart)
FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda

PLANTED_FONT_CHANGES = """\
def restyle(font, title_font, label, gravity):
    font.set_bold(True)
    title_font.strong = True
    font.underline = True
    title_font.size = 24
    label.rect.size = (4, 4)
    font.render('text', style=1)
    gravity.strength = 2
    setattr(title_font, 'fgcolor', (1, 2, 3))
    label.font.rotation += 90
"""

# Built fonts are not reported (styled before anything else reads them; annotated ``=`` and an
# async function's included); a built font restyled after it is cached is, and so is one whose
# name is also bound to something else (another value, a parameter, a conditional expression,
# ``:=``, unpacking, ``for``, ``with``, a chained or augmented assignment, ``del``, ``global``,
# ``nonlocal``) or that a nested function or lambda reaches. Each case pins one branch of the
# exemption: removing that branch leaves its restyle unreported
PLANTED_FONT_BUILDS = """\
import pygame


def build(path, cache):
    pygame_font = pygame.font.Font(path, 12)
    pygame_font.set_bold(True)
    freetype_font = pygame.freetype.SysFont(name='vera', size=12)
    freetype_font.strong = True
    cache['vera'] = pygame_font
    pygame_font.set_italic(True)
    freetype_font.oblique = True
    return freetype_font


def rebound(path, cache):
    font = pygame.font.Font(path, 12)
    font = cache['vera']
    font.set_bold(True)
    del font.size


def nested(path):
    font = pygame.font.Font(path, 12)

    def restyle():
        font.set_bold(True)

    return restyle


def parameter(font, path):
    if path:
        font = pygame.font.Font(path, 12)
    font.set_bold(True)


def closure(path):
    font = pygame.font.Font(path, 12)

    def reader():
        return font

    font.set_bold(True)
    return reader


def chained(path, cache):
    alias = font = pygame.font.Font(path, 12)
    cache['vera'] = alias
    font.set_bold(True)


def ternary(path, fonts):
    font = pygame.font.Font(path, 12) if path else fonts[0]
    font.set_bold(True)


def walrus(path, fonts):
    font = pygame.font.Font(path, 12)
    if font := fonts[0]:
        font.set_bold(True)


def unpacking(path, fonts):
    font = pygame.font.Font(path, 12)
    font, other = fonts
    font.set_bold(True)


def looped(path, fonts):
    font = pygame.font.Font(path, 12)
    for font in fonts:
        font.set_bold(True)


def borrowed(path, fonts):
    font = pygame.font.Font(path, 12)
    with fonts.borrow() as font:
        font.set_bold(True)


def augmented(path, fonts):
    font = pygame.font.Font(path, 12)
    font += fonts
    font.set_bold(True)


def deleted(path):
    font = pygame.font.Font(path, 12)
    del font
    font.set_bold(True)


def declared_global(path):
    global font
    font = pygame.font.Font(path, 12)
    font.set_bold(True)


def declared_nonlocal(path):
    font = None

    def build():
        nonlocal font
        font = pygame.font.Font(path, 12)
        font.set_bold(True)

    return build


def lambda_closure(path):
    font = pygame.font.Font(path, 12)
    reader = lambda: font
    font.set_bold(True)
    return reader


def annotated(path):
    font: pygame.font.Font = pygame.font.Font(path, 12)
    font.set_bold(True)
    return font


async def build_async(path):
    font = pygame.font.Font(path, 12)
    font.set_bold(True)
    return font
"""


def _is_font_receiver(receiver: ast.expr) -> bool:
    """Tell whether an expression's dotted name says it is a font (rule 2).

    Returns:
        True when its source contains ``font``, in any case.

    """
    return FONT_RECEIVER_MARK in ast.unparse(receiver).lower()


def _style_changes(node: ast.expr) -> Iterator[tuple[ast.expr, str]]:
    """Yield the style change a node makes, as (its receiver, what it changes).

    Yields:
        ``(receiver, name)`` for a setter call (rule 1), an attribute write on a font receiver
        or a ``setattr``/``delattr`` on one (rule 2).

    """
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr in FONT_STYLE_SETTERS:
            yield node.func.value, node.func.attr
        elif (
            isinstance(node.func, ast.Name)
            and node.func.id in ATTRIBUTE_WRITING_CALLS
            and node.args
            and _is_font_receiver(node.args[0])
        ):
            yield node.args[0], node.func.id
    elif (
        isinstance(node, ast.Attribute)
        and isinstance(node.ctx, ast.Store | ast.Del)
        and node.attr in FONT_STYLE_ATTRIBUTES | FONT_SIZE_ATTRIBUTES
        and _is_font_receiver(node.value)
    ):
        yield node.value, node.attr


def _scope_nodes(scope: ast.AST) -> Iterator[ast.AST]:
    """Yield every node of a module's or function's own code, not its nested functions' bodies.

    Yields:
        The nodes; of a nested function, only what is evaluated where it is defined (its
        decorators, defaults and annotations) and its parameters.

    """
    pending = list(ast.iter_child_nodes(scope))
    while pending:
        node = pending.pop()
        yield node
        children = list(ast.iter_child_nodes(node))
        if isinstance(node, FunctionNode):
            # Its body is its own scope
            body = node.body if isinstance(node.body, list) else [node.body]
            children = [child for child in children if not any(child is item for item in body)]
        pending.extend(children)


def _parameter_names(scope: ast.AST) -> set[str]:
    """Return the names a function's parameters bind (none for a module).

    Returns:
        Every parameter's name, ``*args`` and ``**kwargs`` included.

    """
    if not isinstance(scope, FunctionNode):
        return set()
    arguments = scope.args
    parameters = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
    parameters.extend(
        parameter for parameter in (arguments.vararg, arguments.kwarg) if parameter is not None
    )
    return {parameter.arg for parameter in parameters}


def _is_font_construction(value: ast.expr) -> bool:
    """Tell whether an expression makes a new font (a call of one of ``FONT_CONSTRUCTORS``).

    Returns:
        True for ``Font(...)``, ``pygame.font.Font(...)``, ``pygame.freetype.SysFont(...)``, ...

    """
    if not isinstance(value, ast.Call):
        return False
    if isinstance(value.func, ast.Attribute):
        return value.func.attr in FONT_CONSTRUCTORS
    return isinstance(value.func, ast.Name) and value.func.id in FONT_CONSTRUCTORS


def _built_font_names(*, scope: ast.AST, nodes: list[ast.AST]) -> set[str]:
    """Return the local names a scope binds only to new fonts.

    Returns:
        Each name every binding of which (``=`` with one target, annotated ``=``) is a font
        construction and that nothing else binds (no parameter, ``global``, ``nonlocal``,
        ``for``, ``with``, ``:=``, unpacking, chained assignment, augmented assignment or
        ``del``) and no nested function or lambda names.

    """
    constructed: set[str] = set()
    otherwise_bound: set[str] = _parameter_names(scope)
    single_bindings: set[int] = set()
    for node in nodes:
        if isinstance(node, ast.Global | ast.Nonlocal):
            otherwise_bound.update(node.names)
        elif isinstance(node, FunctionNode):
            # A name a nested function reaches may be read whenever it is called
            body = node.body if isinstance(node.body, list) else [node.body]
            otherwise_bound.update(
                reached.id
                for statement in body
                for reached in ast.walk(statement)
                if isinstance(reached, ast.Name)
            )
    for node in nodes:
        if isinstance(node, ast.Assign | ast.AnnAssign) and node.value is not None:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            # A chained assignment (``alias = font = Font(...)``) binds the font to every name:
            # a read of one shares it under the others, so none is a new font's
            is_single_target = len(targets) == 1
            for target in targets:
                if isinstance(target, ast.Name):
                    single_bindings.add(id(target))
                    is_new_font = is_single_target and _is_font_construction(node.value)
                    bound = constructed if is_new_font else otherwise_bound
                    bound.add(target.id)
    for node in nodes:
        if (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Store | ast.Del)
            and id(node) not in single_bindings
        ):
            otherwise_bound.add(node.id)
    return constructed - otherwise_bound


def _scope_style_changes(scope: ast.AST) -> list[tuple[int, str]]:
    """Return a module's or function's own in-place style changes (rules 1 and 2).

    Returns:
        ``(line, what)`` for each, a built font's styling before it is read otherwise left out.

    """
    nodes = list(_scope_nodes(scope))
    built_names = _built_font_names(scope=scope, nodes=nodes)
    changes = [
        (change, receiver, what)
        for change in nodes
        if isinstance(change, ast.expr)
        for receiver, what in _style_changes(change)
    ]
    style_receivers = {
        id(receiver)
        for _, receiver, _ in changes
        if isinstance(receiver, ast.Name) and receiver.id in built_names
    }
    # Where each built font is first read other than to style it: from there on it may be shared
    first_other_read: dict[str, tuple[int, int]] = {}
    for node in nodes:
        if (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in built_names
            and id(node) not in style_receivers
        ):
            position = (node.lineno, node.col_offset)
            first_other_read[node.id] = min(first_other_read.get(node.id, position), position)
    found: list[tuple[int, str]] = []
    for change, receiver, what in changes:
        if isinstance(receiver, ast.Name) and receiver.id in built_names:
            first_read = first_other_read.get(receiver.id)
            if first_read is None or (change.lineno, change.col_offset) < first_read:
                continue
        found.append((change.lineno, what))
    return found


def in_place_font_style_changes(*, source_path: Path) -> list[str]:
    """Return every in-place font style change in a source file.

    Args:
        source_path: The Python file.

    Returns:
        ``'<line>: <what>'`` for each (the setter's or attribute's name, ``setattr`` or
        ``delattr``), in line order.

    """
    tree = ast.parse(source_path.read_text(encoding='utf-8'))
    scopes: list[ast.AST] = [tree]
    scopes.extend(node for node in ast.walk(tree) if isinstance(node, FunctionNode))
    found = sorted(change for scope in scopes for change in _scope_style_changes(scope))
    return [f'{line}: {what}' for line, what in found]


def test_the_font_style_scan_finds_every_in_place_change(tmp_path):
    """Every setter, every style write on a font receiver; never a Rect's or a behaviour's."""
    source_path = tmp_path / 'planted.py'
    source_path.write_text(PLANTED_FONT_CHANGES, encoding='utf-8')

    assert in_place_font_style_changes(source_path=source_path) == [
        '2: set_bold',
        '3: strong',
        '4: underline',
        '5: size',
        '9: setattr',
        '10: rotation',
    ]


def test_the_font_style_scan_leaves_out_only_a_font_being_built(tmp_path):
    """Styling a new font before anything else reads it builds it; afterwards it restyles it."""
    source_path = tmp_path / 'planted.py'
    source_path.write_text(PLANTED_FONT_BUILDS, encoding='utf-8')

    assert in_place_font_style_changes(source_path=source_path) == [
        '10: set_italic',
        '18: set_bold',
        '19: size',
        '26: set_bold',
        '34: set_bold',
        '43: set_bold',
        '50: set_bold',
        '55: set_bold',
        '61: set_bold',
        '67: set_bold',
        '73: set_bold',
        '79: set_bold',
        '85: set_bold',
        '91: set_bold',
        '97: set_bold',
        '106: set_bold',
        '114: set_bold',
    ]


def test_nothing_restyles_a_shared_cached_font_in_place():
    """The font caches are one per process (R9): a style change would reach every context."""
    findings = {
        key: changes
        for key, path in scanned_source_files(project_root=PROJECT_ROOT)
        if (changes := in_place_font_style_changes(source_path=path))
    }

    assert findings == {}
