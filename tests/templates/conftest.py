"""Fixtures for the template tests: real template directories, with cookiecutter patched."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from glitchygames.templates import game

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.fixture
def templates_directory(mocker, tmp_path) -> Path:
    """Point the templates module at an empty temporary templates directory.

    Returns:
        Path: The directory build() and get_templates() now read templates from.

    """
    mocker.patch.object(game, 'path', tmp_path)
    return tmp_path


@pytest.fixture
def make_template(templates_directory) -> Callable[..., Path]:
    """Create template directories in the temporary templates directory.

    Returns:
        Callable[..., Path]: `make_template(name=..., repo_contents=None)` makes the directory
            `name`, with a .repo file holding `repo_contents` when that is not None, and returns
            the directory.

    """

    def make(*, name: str, repo_contents: str | None = None) -> Path:
        template_directory = templates_directory / name
        template_directory.mkdir()
        if repo_contents is not None:
            (template_directory / '.repo').write_text(repo_contents)
        return template_directory

    return make


@pytest.fixture
def cookiecutter(mocker):
    """Replace cookiecutter, so a build records where it would generate from.

    A real cookiecutter would download a remote template or prompt for its variables.

    Returns:
        The patched cookiecutter.

    """
    return mocker.patch.object(game, 'cookiecutter')
