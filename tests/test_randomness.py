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
import random
import secrets
from random import SystemRandom, uniform

import numpy as np

token = secrets.token_hex(8)
system_random = random.SystemRandom()
unseeded_random = random.Random()
global_draw = random.uniform(-1.0, 1.0)
unseeded_generator = np.random.default_rng()
legacy_draw = np.random.random()
seeded_random = random.Random(4)
seeded_generator = np.random.default_rng(4)
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


def _is_name(node: ast.expr, *names: str) -> bool:
    return isinstance(node, ast.Name) and node.id in names


def _is_numpy_random(node: ast.expr) -> bool:
    """Report whether a node is ``np.random`` or ``numpy.random``."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == 'random'
        and _is_name(node.value, 'np', 'numpy')
    )


def _unseeded_randomness_in_import(node: ast.Import | ast.ImportFrom) -> list[str]:
    if isinstance(node, ast.Import):
        return [f'import {alias.name}' for alias in node.names if alias.name == 'secrets']
    if node.module == 'secrets':
        return ['from secrets import']
    if node.module == 'random':
        # random.Random is the seedable generator; every other name is global or system state
        return [
            f'from random import {alias.name}' for alias in node.names if alias.name != 'Random'
        ]
    return []


def _unseeded_randomness_in_attribute(node: ast.Attribute) -> str | None:
    # random.Random is the seedable generator; every other random.<name> is the global
    # generator or system entropy (called or passed around)
    if _is_name(node.value, 'random') and node.attr != 'Random':
        return f'random.{node.attr}'
    if node.attr == 'SystemRandom':
        return ast.unparse(node)
    return None


def _unseeded_randomness_in_call(node: ast.Call) -> str | None:
    function = node.func
    if not isinstance(function, ast.Attribute):
        return None
    has_arguments = bool(node.args or node.keywords)
    if _is_name(function.value, 'random') and function.attr == 'Random' and not has_arguments:
        return 'random.Random() without a seed'
    if _is_numpy_random(function.value) and not (function.attr == 'default_rng' and has_arguments):
        suffix = ' without a seed' if function.attr == 'default_rng' else ''
        return f'np.random.{function.attr}(){suffix}'
    return None


def _unseeded_randomness_in_node(node: ast.AST) -> list[str]:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return _unseeded_randomness_in_import(node)
    offender = None
    if isinstance(node, ast.Call):
        offender = _unseeded_randomness_in_call(node)
    elif isinstance(node, ast.Attribute):
        offender = _unseeded_randomness_in_attribute(node)
    return [] if offender is None else [offender]


def unseeded_randomness(source_path: Path) -> list[str]:
    """List each use of randomness that a run's master seed does not control.

    Reports any ``secrets`` import, any ``random.<name>`` other than ``random.Random`` (the
    global generator's functions, ``random.SystemRandom``), ``random.Random()`` without a
    seed, any ``SystemRandom`` attribute, names imported from ``random`` other than
    ``Random``, and any ``np.random`` call other than ``default_rng`` with a seed.

    Args:
        source_path: The Python file to scan.

    Returns:
        ``<path>:<line> <what>`` for every use found, in source order.

    """
    tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
    positioned_offenders = sorted(
        (node.lineno, node.col_offset, what)
        for node in ast.walk(tree)
        if isinstance(node, (ast.stmt, ast.expr))
        for what in _unseeded_randomness_in_node(node)
    )
    return [f'{source_path}:{line} {what}' for line, _column, what in positioned_offenders]


@pytest.fixture
def offending_randomness_file(tmp_path) -> Path:
    """A module using every kind of randomness the guard rejects, plus two seeded uses.

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
    """The scan reports each unseeded use and neither seeded one (it is not vacuous)."""
    path = offending_randomness_file

    assert unseeded_randomness(path) == [
        f'{path}:2 import secrets',
        f'{path}:3 from random import SystemRandom',
        f'{path}:3 from random import uniform',
        f'{path}:8 random.SystemRandom',
        f'{path}:9 random.Random() without a seed',
        f'{path}:10 random.uniform',
        f'{path}:11 np.random.default_rng() without a seed',
        f'{path}:12 np.random.random()',
    ]
