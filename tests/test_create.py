"""Tests for scripts/create.py: without the templates extra it says how to install it.

It lists the templates and builds one; without the templates extra it names
`pip install glitchygames[templates]` and exits 1, never with a traceback.

cookiecutter itself is patched where a build would run it (it would download the template and
prompt for its variables); its absence is the templates module's own ``cookiecutter`` set to None,
which is what the module's import leaves when the extra is not installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scripts import create

from glitchygames.templates import game

if TYPE_CHECKING:
    import pytest
    from pytest_mock import MockerFixture


def test_list_prints_every_template(capsys: pytest.CaptureFixture[str]):
    """--list prints the bundled templates, one per line, on stdout."""
    assert create.main(['--list']) == 0

    assert capsys.readouterr().out.splitlines() == game.get_templates()


def test_template_builds_it(mocker: MockerFixture):
    """--template pong builds the bundled pong template with cookiecutter."""
    cookiecutter = mocker.patch.object(game, 'cookiecutter')

    assert create.main(['--template', 'pong']) == 0

    cookiecutter.assert_called_once_with(
        'https://github.com/sabadam32/cookiecutter-glitchygames-pong'
    )


def test_without_the_templates_extra_it_says_how_to_install_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """No cookiecutter: one line naming `pip install glitchygames[templates]`, exit 1."""
    monkeypatch.setattr(game, 'cookiecutter', None)

    assert create.main(['--template', 'pong']) == 1

    error = capsys.readouterr().err
    assert error == f'{game.TEMPLATES_EXTRA_MISSING_MESSAGE}\n'
    assert 'pip install glitchygames[templates]' in error
    assert 'Traceback' not in error


def test_no_option_does_nothing(capsys: pytest.CaptureFixture[str]):
    """Neither --list nor --template: nothing printed, exit 0."""
    assert create.main([]) == 0

    assert capsys.readouterr() == ('', '')
