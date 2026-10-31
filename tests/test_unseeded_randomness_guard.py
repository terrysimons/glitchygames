"""No module in the engine or a member draws randomness a run's master seed does not control.

Gameplay randomness goes through ``random_stream``/``numpy_stream`` (glitchygames/randomness.py),
so a seed reproduces a run. The scan reads the engine's and every workspace member's source
(tests/workspace_sources.py reads the members from the workspace), so it is a test of this
repository; moved here unchanged from tests/test_randomness.py (Part 3, Stage D, Task D9 fix
round 1), which tests the engine's streams alone.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.ast_scanning import PROJECT_ROOT, dynamic_import_name, import_bindings, qualified_name
from tests.workspace_sources import scanned_source_files, write_project_with_member_module

if TYPE_CHECKING:
    from pathlib import Path

# Modules in the package allowed to use unseeded randomness, and why. randomness.py draws
# the master seed itself when no --random-seed is given; replay/tools/compare.py draws a token
# for security, not gameplay (each --compare-trace child proves itself with it).
UNSEEDED_RANDOMNESS_ALLOWED_MODULES: dict[str, str] = {
    'randomness.py': 'draws the master seed from secrets when no --random-seed is given',
    'replay/tools/compare.py': (
        "draws each frame stream's token from secrets (a loopback connection proves it is "
        "OLD's child; never gameplay, never replayed)"
    ),
}

OFFENDING_RANDOMNESS_SOURCE = """\
import os
import random
import random as r
import secrets
import uuid
from random import Random, SystemRandom, uniform

import numpy as np
import numpy.random as npr
from numpy import random as nr
from numpy.random import default_rng

token = secrets.token_hex(8)
system_random = random.SystemRandom()
unseeded_random = random.Random()
global_draw = random.uniform(-1.0, 1.0)
unseeded_generator = np.random.default_rng()
legacy_draw = np.random.random()
aliased_draw = r.uniform(0, 1)
aliased_system_random = r.SystemRandom()
aliased_module_generator = npr.default_rng()
from_imported_module_generator = nr.default_rng()
bare_generator = default_rng()
bare_unseeded_random = Random()
none_seeded_generator = default_rng(None)
none_seeded_random = Random(x=None)
entropy_bytes = os.urandom(4)
random_identifier = uuid.uuid4()
host_time_identifier = uuid.uuid1()
dynamic_draw = __import__('random').random()
bare_uniform = uniform(0, 1)
seeded_random = random.Random(4)
seeded_generator = np.random.default_rng(4)
seeded_bare_random = Random(5)
seeded_bare_generator = default_rng(seed=6)
seeded_aliased_generator = npr.default_rng(7)
name_based_identifier = uuid.uuid5(uuid.NAMESPACE_DNS, 'example')
working_directory = os.getcwd()
"""

# Modules whose import bindings the scan follows (aliases, from-imports, __import__)
WATCHED_MODULES = frozenset({'numpy', 'numpy.random', 'os', 'random', 'secrets', 'uuid'})

# Fully qualified names that are unseeded wherever they are used (called or passed around)
UNSEEDED_NAMES = frozenset({'os.urandom', 'uuid.uuid1', 'uuid.uuid4'})

# Seedable constructors: unseeded when the seed is missing or a literal None
SEEDABLE_CONSTRUCTORS = {'random.Random': 'x', 'numpy.random.default_rng': 'seed'}


def _is_unseeded_name(reference_name: str) -> bool:
    # random.Random is the seedable generator; every other random.<name> is the global
    # generator or system entropy
    if reference_name.startswith('random.') and reference_name != 'random.Random':
        return True
    return reference_name in UNSEEDED_NAMES or reference_name.endswith('.SystemRandom')


def _has_seed(node: ast.Call, *, seed_keyword: str) -> bool:
    """Report whether a call passes a seed that is not a literal None."""
    seed_arguments = [*node.args[:1], *(k.value for k in node.keywords if k.arg == seed_keyword)]
    return any(
        not (isinstance(argument, ast.Constant) and argument.value is None)
        for argument in seed_arguments
    )


def _unseeded_randomness_in_import(node: ast.Import | ast.ImportFrom) -> list[str]:
    if isinstance(node, ast.Import):
        return [f'import {alias.name}' for alias in node.names if alias.name == 'secrets']
    if node.module == 'secrets':
        return ['from secrets import']
    if node.module not in WATCHED_MODULES:
        return []
    return [
        f'from {node.module} import {alias.name}'
        for alias in node.names
        if _is_unseeded_name(f'{node.module}.{alias.name}')
    ]


def _unseeded_randomness_in_call(node: ast.Call, bindings: dict[str, str]) -> str | None:
    imported_module_name = dynamic_import_name(node=node, watched_modules=WATCHED_MODULES)
    if imported_module_name is not None:
        return f"__import__('{imported_module_name}')"
    function_name = qualified_name(
        node=node.func, bindings=bindings, watched_modules=WATCHED_MODULES
    )
    if function_name is None:
        return None
    seed_keyword = SEEDABLE_CONSTRUCTORS.get(function_name)
    if seed_keyword is not None:
        if _has_seed(node, seed_keyword=seed_keyword):
            return None
        return f'{function_name}() without a seed'
    if function_name.startswith('numpy.random.'):
        return f'{function_name}()'
    return None


def _unseeded_randomness_in_reference(
    node: ast.Name | ast.Attribute, bindings: dict[str, str]
) -> str | None:
    reference_name = qualified_name(node=node, bindings=bindings, watched_modules=WATCHED_MODULES)
    if reference_name is not None:
        return reference_name if _is_unseeded_name(reference_name) else None
    if isinstance(node, ast.Attribute) and node.attr == 'SystemRandom':
        return ast.unparse(node)
    return None


def _unseeded_randomness_in_node(node: ast.AST, bindings: dict[str, str]) -> list[str]:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return _unseeded_randomness_in_import(node)
    offender = None
    if isinstance(node, ast.Call):
        offender = _unseeded_randomness_in_call(node, bindings)
    elif isinstance(node, (ast.Name, ast.Attribute)) and isinstance(node.ctx, ast.Load):
        offender = _unseeded_randomness_in_reference(node, bindings)
    return [] if offender is None else [offender]


def unseeded_randomness(source_path: Path) -> list[str]:
    """List each use of randomness that a run's master seed does not control.

    Names are resolved through the module's imports (``import random as r``, ``from
    numpy.random import default_rng``, ``__import__('random')``), so aliases are caught.
    Reports: any ``secrets`` import; any ``random.<name>`` other than ``random.Random``
    (the global generator's functions, ``SystemRandom``), used or imported; any
    ``SystemRandom`` attribute; ``os.urandom``, ``uuid.uuid1`` and ``uuid.uuid4``;
    ``random.Random()`` and ``numpy.random.default_rng()`` with no seed or a literal None
    seed; any other ``numpy.random`` call; and ``__import__`` of a watched module.

    Not detected: generators seeded from something that is not reproducible, such as
    ``random.Random(time.time())`` or ``default_rng(os.getpid())`` (the scan only checks
    that a seed is given), and imports through ``importlib.import_module``.

    Args:
        source_path: The Python file to scan.

    Returns:
        ``<path>:<line> <what>`` for every use found, in source order.

    """
    tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
    bindings = import_bindings(tree=tree, watched_modules=WATCHED_MODULES)
    positioned_offenders = sorted(
        (node.lineno, node.col_offset, what)
        for node in ast.walk(tree)
        if isinstance(node, (ast.stmt, ast.expr))
        for what in _unseeded_randomness_in_node(node, bindings)
    )
    return [f'{source_path}:{line} {what}' for line, _column, what in positioned_offenders]


@pytest.fixture
def offending_randomness_file(tmp_path) -> Path:
    """A module using every kind of randomness the guard rejects, plus seeded and harmless uses.

    Returns:
        The path of the written file.

    """
    source_path = tmp_path / 'offending_randomness.py'
    source_path.write_text(OFFENDING_RANDOMNESS_SOURCE, encoding='utf-8')
    return source_path


def test_package_draws_randomness_only_from_seeded_streams():
    """No module in glitchygames/ or a member package uses randomness the seed does not control.

    Gameplay randomness goes through random_stream / numpy_stream, so a seed reproduces a
    run (replay, golden traces). The allowed modules are listed with their reasons.
    """
    offenders = [
        offender
        for allowlist_key, source_path in scanned_source_files(project_root=PROJECT_ROOT)
        if allowlist_key not in UNSEEDED_RANDOMNESS_ALLOWED_MODULES
        for offender in unseeded_randomness(source_path)
    ]

    assert offenders == []


def test_unseeded_randomness_in_a_member_package_is_reported_under_its_repository_path(tmp_path):
    """The guard's walk reads a member's file: random.random() there is an offender."""
    member_key = write_project_with_member_module(
        project_root=tmp_path, source='import random\n\nroll = random.random()\n'
    )

    offenders = {
        allowlist_key: file_offenders
        for allowlist_key, source_path in scanned_source_files(project_root=tmp_path)
        if allowlist_key not in UNSEEDED_RANDOMNESS_ALLOWED_MODULES
        and (file_offenders := unseeded_randomness(source_path))
    }

    assert list(offenders) == [member_key]
    assert offenders[member_key][0].endswith(':3 random.random')


def test_unseeded_randomness_scan_finds_every_kind(offending_randomness_file):
    """The scan reports each unseeded use, aliased or not, and no seeded one (not vacuous)."""
    path = offending_randomness_file

    unseeded = 'without a seed'
    assert unseeded_randomness(path) == [
        f'{path}:4 import secrets',
        f'{path}:6 from random import SystemRandom',
        f'{path}:6 from random import uniform',
        f'{path}:14 random.SystemRandom',
        f'{path}:15 random.Random() {unseeded}',
        f'{path}:16 random.uniform',
        f'{path}:17 numpy.random.default_rng() {unseeded}',
        f'{path}:18 numpy.random.random()',
        f'{path}:19 random.uniform',
        f'{path}:20 random.SystemRandom',
        f'{path}:21 numpy.random.default_rng() {unseeded}',
        f'{path}:22 numpy.random.default_rng() {unseeded}',
        f'{path}:23 numpy.random.default_rng() {unseeded}',
        f'{path}:24 random.Random() {unseeded}',
        f'{path}:25 numpy.random.default_rng() {unseeded}',
        f'{path}:26 random.Random() {unseeded}',
        f'{path}:27 os.urandom',
        f'{path}:28 uuid.uuid4',
        f'{path}:29 uuid.uuid1',
        f"{path}:30 __import__('random')",
        f'{path}:30 random.random',
        f'{path}:31 random.uniform',
    ]
