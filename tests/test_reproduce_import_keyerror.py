"""Tests for scripts/reproduce_import_keyerror.py: tallying fresh imports under each mode."""

from __future__ import annotations

import sys

import pytest
from scripts.reproduce_import_keyerror import MODES, forget, import_outcome, main

from glitchygames.exit_codes import ExitCode

# A module that removes its own sys.modules entry while it runs: always the CI KeyError
SELF_REMOVING_MODULE = 'import sys\ndel sys.modules[__name__]\n'


@pytest.fixture
def probe_packages(tmp_path, monkeypatch):
    """Put a plain package and a self-removing module on the path, gone again after the test.

    Yields:
        The plain package's name and the self-removing module's.

    """
    package = tmp_path / 'plain_probe_package'
    package.mkdir()
    (package / '__init__.py').write_text('from . import child\n')
    (package / 'child.py').write_text('VALUE = 1\n')
    (tmp_path / 'self_removing_probe.py').write_text(SELF_REMOVING_MODULE)
    monkeypatch.syspath_prepend(tmp_path)
    yield 'plain_probe_package', 'self_removing_probe'
    forget('plain_probe_package')
    forget('self_removing_probe')


def test_forget_removes_a_package_and_its_submodules_only(probe_packages):
    """The package and its children go; a name that only starts the same way stays."""
    plain, _ = probe_packages
    __import__(plain)
    sys.modules['plain_probe_package_lookalike'] = sys.modules[plain]
    try:
        forget(plain)

        assert plain not in sys.modules
        assert f'{plain}.child' not in sys.modules
        assert 'plain_probe_package_lookalike' in sys.modules
    finally:
        del sys.modules['plain_probe_package_lookalike']


def test_an_import_that_succeeds_is_ok(probe_packages):
    """A plain package imports: ``ok``."""
    plain, _ = probe_packages

    assert import_outcome(plain) == 'ok'


def test_a_module_leaving_sys_modules_is_described_as_the_ci_keyerror(probe_packages):
    """The exception type, its message and the importlib frame it came from."""
    _, self_removing = probe_packages

    outcome = import_outcome(self_removing)

    assert outcome.startswith("KeyError: 'self_removing_probe' at <frozen importlib._bootstrap>:")


def test_the_modes_are_the_three_documented():
    """The command line offers exactly the modes the docstring describes."""
    assert MODES == ('restore-during-import', 'two-importers', 'leftover-importer')


def test_two_importers_of_a_plain_package_all_succeed(probe_packages, capsys):
    """The control: two threads per trial, nothing restoring, every import ok."""
    plain, _ = probe_packages

    status = main(['two-importers', '--trials', '3', '--package', plain])

    assert status == ExitCode.SUCCESS
    assert capsys.readouterr().out == '6 thread: ok\n'


def test_a_failing_import_is_found(probe_packages, capsys):
    """An import that always fails makes the run report it and exit with the "found" code."""
    _, self_removing = probe_packages

    status = main(['two-importers', '--trials', '2', '--package', self_removing])

    assert status == ExitCode.REPLAY_DIVERGED
    assert capsys.readouterr().out.startswith("4 thread: KeyError: 'self_removing_probe'")
