"""cookiecutter is the ``templates`` extra: without it the templates list, and build() says so.

Uninstalling cookiecutter is not something a test can do, so its absence is made two ways: the
module imported afresh while ``import cookiecutter`` fails (``sys.modules`` holding None, as
Python's import system honors), and the module's own ``cookiecutter`` set to None, which is what
that import leaves.
"""

from __future__ import annotations

import importlib
import sys

import pytest

import glitchygames.templates
from glitchygames.templates import TemplatesUnavailableError, build, game, get_templates


def test_the_module_imports_without_cookiecutter_and_still_lists_the_templates(monkeypatch):
    """No cookiecutter: the import succeeds, cookiecutter is None, the templates still list."""
    monkeypatch.setitem(sys.modules, 'cookiecutter', None)
    monkeypatch.setitem(sys.modules, 'cookiecutter.main', None)
    monkeypatch.delitem(sys.modules, 'glitchygames.templates.game')
    # Importing the submodule afresh rebinds the package's attribute: put the original back
    monkeypatch.setattr(glitchygames.templates, 'game', game)

    fresh = importlib.import_module('glitchygames.templates.game')

    assert fresh is not game
    assert fresh.cookiecutter is None
    assert 'pong' in fresh.get_templates()


def test_build_without_the_templates_extra_names_it(monkeypatch, make_template):
    """build() raises TemplatesUnavailableError naming `pip install glitchygames[templates]`."""
    make_template(name='any_template')
    monkeypatch.setattr(game, 'cookiecutter', None)

    with pytest.raises(TemplatesUnavailableError, match=r'pip install glitchygames\[templates\]'):
        build('any_template')

    assert get_templates() == ['any_template']


def test_the_missing_extra_is_an_import_error():
    """Callers that guard optional imports with `except ImportError` catch it too."""
    assert issubclass(TemplatesUnavailableError, ImportError)
