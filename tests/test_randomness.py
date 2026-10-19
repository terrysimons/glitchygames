"""Tests for the engine's random number streams (glitchygames/randomness.py).

One master seed per run; every subsystem draws from its own named stream, seeded from
(master seed, name) through a stable hash, so a seed reproduces a run and a draw in one
subsystem never shifts another's sequence. A guard scan keeps unseeded randomness out of the
package.
"""

from __future__ import annotations

import ast
import random
from pathlib import Path

import numpy as np
import pytest

from glitchygames import randomness
from glitchygames.randomness import (
    SEED_BITS,
    engine_random,
    engine_random_seed,
    numpy_stream,
    random_stream,
    reset_streams,
    seed_engine_random,
    stream_seed,
)

DRAW_COUNT = 20
TEST_SEED = 123
# stream_seed(kind='random', master_seed=123, name='engine'): the blake2b-128 digest of
# b'random\x00123\x00engine' as a big-endian integer. Pinned: Python's hash() is salted per
# process, so a value that matched in every run proves the hash is stable.
PINNED_ENGINE_STREAM_SEED = 182259697978296911412075486029851279510
PINNED_ENGINE_STREAM_FIRST_VALUE = 0.9962194675483362
# The numpy stream seed of master seed 123 and the name 'audio.synth'
PINNED_SYNTH_NUMPY_STREAM_SEED = 138955109165650377915384574469052649923

# Modules in the package allowed to use unseeded randomness, and why. randomness.py draws
# the master seed itself when no --random-seed is given. No module uses randomness for
# security (tokens, keys) today; one that does would be listed here with its reason.
UNSEEDED_RANDOMNESS_ALLOWED_MODULES: dict[str, str] = {
    'randomness.py': 'draws the master seed from secrets when no --random-seed is given',
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


def _draws(name: str) -> list[float]:
    return [random_stream(name).random() for _ in range(DRAW_COUNT)]


class TestStreams:
    """Named streams: reproducible, independent, lazily created and cached."""

    def test_same_seed_gives_the_same_sequence_per_stream(self):
        """Two resets with seed 123 give every stream the same sequence again."""
        reset_streams(seed=TEST_SEED)
        first_run = (_draws('shake'), _draws('ball.serve'))
        reset_streams(seed=TEST_SEED)

        assert (_draws('shake'), _draws('ball.serve')) == first_run

    def test_different_names_give_different_sequences(self):
        """Two streams of one master seed do not repeat each other."""
        reset_streams(seed=TEST_SEED)

        assert _draws('shake') != _draws('ball.serve')

    def test_drawing_from_one_stream_does_not_shift_another(self):
        """Extra draws from stream A leave stream B's next value unchanged."""
        reset_streams(seed=TEST_SEED)
        undisturbed_value = random_stream('ball.serve').random()
        reset_streams(seed=TEST_SEED)
        for _ in range(DRAW_COUNT):
            random_stream('shake').random()

        assert random_stream('ball.serve').random() == undisturbed_value

    def test_different_seeds_give_different_sequences(self):
        """Master seeds 123 and 124 give a stream different sequences."""
        reset_streams(seed=TEST_SEED)
        first_run = _draws('shake')
        reset_streams(seed=TEST_SEED + 1)

        assert _draws('shake') != first_run

    def test_streams_are_cached_by_name_until_reset(self):
        """The same name returns the same generator; a reset starts new ones."""
        reset_streams(seed=TEST_SEED)
        generator = random_stream('shake')
        numpy_generator = numpy_stream('audio.live')

        assert random_stream('shake') is generator
        assert numpy_stream('audio.live') is numpy_generator
        reset_streams(seed=TEST_SEED)
        assert random_stream('shake') is not generator
        assert numpy_stream('audio.live') is not numpy_generator

    def test_numpy_stream_is_reproducible_and_independent(self):
        """Streams from numpy_stream follow the same rules as random streams."""
        reset_streams(seed=TEST_SEED)
        first_run = numpy_stream('audio.synth').uniform(-1.0, 1.0, DRAW_COUNT)
        other_stream = numpy_stream('audio.live').uniform(-1.0, 1.0, DRAW_COUNT)
        reset_streams(seed=TEST_SEED)

        assert np.array_equal(numpy_stream('audio.synth').uniform(-1.0, 1.0, DRAW_COUNT), first_run)
        assert not np.array_equal(first_run, other_stream)

    def test_engine_random_is_the_engine_stream(self):
        """engine_random() is random_stream('engine')."""
        reset_streams(seed=TEST_SEED)

        assert engine_random() is random_stream('engine')


class TestStableHash:
    """Stream seeds come from a stable hash of (kind, master seed, name), never hash()."""

    def test_known_seed_and_name_give_a_pinned_stream_seed(self):
        """stream_seed is the same in every process (Python's hash() would not be)."""
        assert (
            stream_seed(kind='random', master_seed=TEST_SEED, name='engine')
            == PINNED_ENGINE_STREAM_SEED
        )
        assert (
            stream_seed(kind='numpy', master_seed=TEST_SEED, name='audio.synth')
            == PINNED_SYNTH_NUMPY_STREAM_SEED
        )

    def test_known_seed_and_name_give_a_pinned_first_value(self):
        """The engine stream of seed 123 always starts with the same value."""
        reset_streams(seed=TEST_SEED)

        assert random_stream('engine').random() == PINNED_ENGINE_STREAM_FIRST_VALUE

    def test_random_and_numpy_streams_of_one_name_have_different_seeds(self):
        """The kind is part of the hashed bytes."""
        assert stream_seed(kind='random', master_seed=1, name='x') != stream_seed(
            kind='numpy', master_seed=1, name='x'
        )

    def test_negative_master_seed_is_accepted(self):
        """--random-seed accepts any int, including negative ones."""
        reset_streams(seed=-5)

        assert engine_random_seed() == -5
        assert (
            random_stream('engine').random()
            == random.Random(stream_seed(kind='random', master_seed=-5, name='engine')).random()
        )


class TestMasterSeed:
    """The master seed: given, or drawn once from secrets."""

    def test_seed_engine_random_with_a_seed_resets_the_streams(self):
        """seed_engine_random(seed=n) is reset_streams(seed=n) and returns n."""
        assert seed_engine_random(seed=TEST_SEED) == TEST_SEED
        first_run = _draws('shake')
        reset_streams(seed=TEST_SEED)

        assert _draws('shake') == first_run

    def test_no_seed_draws_one_from_secrets(self, mocker):
        """Without a seed, the seed is secrets.randbits(SEED_BITS) and is remembered."""
        randbits = mocker.patch.object(randomness.secrets, 'randbits', return_value=987654321)

        assert seed_engine_random() == 987654321
        randbits.assert_called_once_with(SEED_BITS)
        assert engine_random_seed() == 987654321

    def test_a_stream_seeds_the_master_seed_on_first_use(self, mocker):
        """A draw before the engine seeded gets a secrets-seeded stream, not an error."""
        mocker.patch.object(randomness.secrets, 'randbits', return_value=42)

        generator = random_stream('shake')

        assert generator is random_stream('shake')
        assert engine_random_seed() == 42


# Modules whose import bindings the scan follows (aliases, from-imports, __import__)
WATCHED_MODULES = frozenset({'numpy', 'numpy.random', 'os', 'random', 'secrets', 'uuid'})
# Fully qualified names that are unseeded wherever they are used (called or passed around)
UNSEEDED_NAMES = frozenset({'os.urandom', 'uuid.uuid1', 'uuid.uuid4'})
# Seedable constructors: unseeded when the seed is missing or a literal None
SEEDABLE_CONSTRUCTORS = {'random.Random': 'x', 'numpy.random.default_rng': 'seed'}


def _import_bindings(tree: ast.Module) -> dict[str, str]:
    """Map each local name bound to a watched module (or a name in one) to its qualified name.

    ``import random as r`` binds ``r`` to ``random``; ``import numpy.random`` binds
    ``numpy``; ``from numpy import random as nr`` binds ``nr`` to ``numpy.random``;
    ``from random import Random`` binds ``Random`` to ``random.Random``. Bindings are
    module-wide: an import inside a function counts too, and shadowing is ignored.

    Returns:
        Local name -> fully qualified name.

    """
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname is not None and alias.name in WATCHED_MODULES:
                    bindings[alias.asname] = alias.name
                elif alias.asname is None and alias.name.split('.')[0] in WATCHED_MODULES:
                    top_level_name = alias.name.split('.')[0]
                    bindings[top_level_name] = top_level_name
        elif isinstance(node, ast.ImportFrom) and node.module in WATCHED_MODULES:
            for alias in node.names:
                bindings[alias.asname or alias.name] = f'{node.module}.{alias.name}'
    return bindings


def _dynamic_import_name(node: ast.expr) -> str | None:
    """Return the watched module ``__import__('<module>')`` imports, else None."""
    is_dynamic_import = (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == '__import__'
        and bool(node.args)
    )
    if not is_dynamic_import:
        return None
    assert isinstance(node, ast.Call)
    module_argument = node.args[0]
    if isinstance(module_argument, ast.Constant) and module_argument.value in WATCHED_MODULES:
        return str(module_argument.value)
    return None


def _qualified_name(node: ast.expr, bindings: dict[str, str]) -> str | None:
    """Resolve a name or attribute chain through the import bindings.

    Returns:
        The fully qualified name (``random.uniform``), or None if it is not from a watched module.

    """
    if isinstance(node, ast.Name):
        return bindings.get(node.id)
    if isinstance(node, ast.Attribute):
        owner = _qualified_name(node.value, bindings)
        return None if owner is None else f'{owner}.{node.attr}'
    return _dynamic_import_name(node)


def _is_unseeded_name(qualified_name: str) -> bool:
    # random.Random is the seedable generator; every other random.<name> is the global
    # generator or system entropy
    if qualified_name.startswith('random.') and qualified_name != 'random.Random':
        return True
    return qualified_name in UNSEEDED_NAMES or qualified_name.endswith('.SystemRandom')


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
    dynamic_import_name = _dynamic_import_name(node)
    if dynamic_import_name is not None:
        return f"__import__('{dynamic_import_name}')"
    function_name = _qualified_name(node.func, bindings)
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
    qualified_name = _qualified_name(node, bindings)
    if qualified_name is not None:
        return qualified_name if _is_unseeded_name(qualified_name) else None
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
    bindings = _import_bindings(tree)
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
    """No module in glitchygames/ uses randomness the master seed does not control.

    Gameplay randomness goes through random_stream / numpy_stream, so a seed reproduces a
    run (replay, golden traces). The allowed modules are listed with their reasons.
    """
    package_root = Path(randomness.__file__).parent
    offenders = [
        offender
        for source_path in sorted(package_root.rglob('*.py'))
        if source_path.relative_to(package_root).as_posix()
        not in UNSEEDED_RANDOMNESS_ALLOWED_MODULES
        for offender in unseeded_randomness(source_path)
    ]

    assert offenders == []


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
