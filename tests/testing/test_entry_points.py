"""Tests for glitchygames.testing.entry_points: running a package as ``python -m``, in any order."""

from __future__ import annotations

import sys
import types
from typing import TYPE_CHECKING

from glitchygames.testing import entry_points

if TYPE_CHECKING:
    import pytest
    from pytest_mock import MockerFixture


def test_an_earlier_import_of_the_packages_main_is_removed_before_the_run(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
):
    """``<package>.__main__`` left in sys.modules is gone when runpy runs the package.

    runpy warns when it is still there, and the suite makes the warning an error (CircleCI job
    4458: a walk of the package's modules had imported it first, in a shuffled order).
    """
    monkeypatch.setitem(sys.modules, 'stand_in_game.__main__', types.ModuleType('stand_in_game'))
    seen_in_sys_modules: list[bool] = []
    run_module = mocker.patch.object(
        entry_points.runpy,
        'run_module',
        side_effect=lambda *arguments, **options: seen_in_sys_modules.append(
            'stand_in_game.__main__' in sys.modules
        ),
    )

    entry_points.run_package_as_main(package='stand_in_game')

    run_module.assert_called_once_with('stand_in_game', run_name='__main__')
    assert seen_in_sys_modules == [False]


def test_a_package_whose_main_was_never_imported_runs_the_same(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
):
    """Nothing to remove: the package still runs as ``__main__``."""
    monkeypatch.delitem(sys.modules, 'stand_in_game.__main__', raising=False)
    run_module = mocker.patch.object(entry_points.runpy, 'run_module')

    entry_points.run_package_as_main(package='stand_in_game')

    run_module.assert_called_once_with('stand_in_game', run_name='__main__')
