"""Seeds that failed a test are kept, and a failing seed is always reported (the owner's rule).

The final review found a fresh seed reported only through assertion messages: a test that failed
by an exception lost its seed. ``resolve_seed`` now records the seed on the running test, and the
game's conftest adds it to every failed report (``seed_report``).
"""

from __future__ import annotations

import importlib
import json

regressed_seeds = importlib.import_module(
    'src.games.zombies-aint-my-neighbors.tests.regressed_seeds'
)


class Node:
    """A stand-in for a pytest item: the attributes the helpers read and write."""

    def __init__(self) -> None:
        """Start with no seed recorded."""
        self.nodeid = 'tests/test_x.py::test_y[random]'


def test_a_fresh_seed_is_recorded_on_the_running_test():
    """``random`` draws a seed, and the test's node keeps it for the report."""
    node = Node()

    seed = regressed_seeds.resolve_seed(regressed_seeds.RANDOM_CASE, node=node)

    assert regressed_seeds.recorded_seed(node) == seed


def test_a_saved_seed_is_recorded_too():
    """A saved seed is the seed."""
    node = Node()

    assert regressed_seeds.resolve_seed(7, node=node) == 7
    assert regressed_seeds.recorded_seed(node) == 7


def test_the_report_names_the_seed_and_where_to_save_it():
    """Any failure of a seeded test reports its seed and its fixture."""
    node = Node()
    regressed_seeds.resolve_seed(42, node=node, test='test_y', vector='players-4')

    report = regressed_seeds.seed_report(node)

    assert report is not None
    assert 'seed 42' in report
    assert 'test_y.json' in report
    assert 'players-4' in report


def test_a_test_without_a_seed_reports_none():
    """Tests that take no seed add nothing."""
    assert regressed_seeds.seed_report(Node()) is None


def test_every_saved_fixture_is_a_mapping_of_vectors_to_seeds(tmp_path):
    """The fixtures parse: each vector holds a list of whole numbers."""
    for path in regressed_seeds.FIXTURE_DIRECTORY.glob('*.json'):
        seeds = json.loads(path.read_text(encoding='utf-8'))
        assert isinstance(seeds, dict), path
        for vector, values in seeds.items():
            assert all(isinstance(value, int) for value in values), (path, vector)
