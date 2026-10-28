"""A member's test modules are named by their path from the repository root, in every environment.

pytest's importlib mode without namespace packages (the root pyproject.toml): this module is
``src.apps.bitmappy.tests.test_bitmappy_test_module_names`` under ``uv run pytest`` (an editable
engine on sys.path) and under nox (installed copies) alike, and a helper beside it, imported by
the same path, is one module, whoever imports it (tests/test_suite_collection.py,
``test_tests_are_imported_by_their_paths``).
"""

import sys

from src.apps.bitmappy.tests import film_strip_support


def test_this_module_is_named_by_its_path_from_the_repository_root():
    """Not ``apps.bitmappy.tests...`` (sys.path-relative), not the bare file name."""
    assert __name__ == 'src.apps.bitmappy.tests.test_bitmappy_test_module_names'


def test_a_helper_imported_by_its_path_is_one_module():
    """The helper imported by its path is the module of that name, loaded once."""
    assert sys.modules['src.apps.bitmappy.tests.film_strip_support'] is film_strip_support
    assert film_strip_support.__name__ == 'src.apps.bitmappy.tests.film_strip_support'
