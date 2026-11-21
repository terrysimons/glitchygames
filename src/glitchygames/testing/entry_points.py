"""Run a game's package as ``python -m`` runs it, in a test, whatever the test run imported first.

``runpy.run_module(package, run_name='__main__')`` runs the package's ``__main__`` module as
``__main__``, as ``python -m package`` does, but warns (RuntimeWarning: "found in sys.modules after
import of package ..., but prior to execution of ...") when ``<package>.__main__`` is already in
``sys.modules``, and the engine's suite makes that warning an error. Any earlier test that
imported every module of the package (a walk for its scenes) leaves it there, so a test of
``python -m`` passed or failed by the order tests ran in (CircleCI job 4458, a shuffled order).
``run_package_as_main`` removes the module first, so the run is the same in any order.
"""

from __future__ import annotations

import runpy
import sys


def run_package_as_main(*, package: str) -> None:
    """Run a package's ``__main__`` as ``python -m package`` does, after any earlier import of it.

    Args:
        package: The import package (``zombies_aint_my_neighbors``). Patch what its
            ``__main__`` calls first, or the game starts.

    """
    sys.modules.pop(f'{package}.__main__', None)
    runpy.run_module(package, run_name='__main__')
