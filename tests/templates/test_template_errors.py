"""Template error handling tests.

build() catches only a missing .repo file; every other error, from reading the .repo file or
from cookiecutter, reaches the caller. The templates are real temporary directories. Failures
cookiecutter cannot be made to produce here (a timeout, a missing install) come from a patched
cookiecutter; a template it cannot find is given to the real one.
"""

import os
import sys
from pathlib import Path

import pytest
from cookiecutter.exceptions import RepositoryNotFound

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.templates import build


class TestTemplateErrors:
    """Errors from the .repo file or cookiecutter propagate out of build()."""

    def test_build_template_cookiecutter_exception(self, make_template, cookiecutter):
        """A cookiecutter error is not caught."""
        make_template(name='failing_template')
        cookiecutter.side_effect = RuntimeError('Cookiecutter failed')

        with pytest.raises(RuntimeError, match='Cookiecutter failed'):
            build('failing_template')

    def test_build_exception_handling(self, make_template, cookiecutter):
        """A remote template's cookiecutter error is not caught either."""
        make_template(name='exception_template', repo_contents='gh:user/missing\n')
        cookiecutter.side_effect = RuntimeError('Template not found')

        with pytest.raises(RuntimeError, match='Template not found'):
            build('exception_template')

        cookiecutter.assert_called_once_with('gh:user/missing')

    def test_build_file_not_found_error(self, make_template, cookiecutter):
        """A missing .repo file is the one error build() handles: it builds the directory."""
        template_directory = make_template(name='no_repo_template')

        build('no_repo_template')

        cookiecutter.assert_called_once_with(str(template_directory))

    def test_build_io_error_handling(self, make_template, cookiecutter):
        """A .repo that cannot be read (here a directory) is an OSError build() does not catch."""
        template_directory = make_template(name='io_error_template')
        (template_directory / '.repo').mkdir()

        # IsADirectoryError on POSIX, PermissionError on Windows: both OSError, neither caught
        with pytest.raises(OSError, match=r'\.repo'):
            build('io_error_template')

        cookiecutter.assert_not_called()

    def test_build_permission_error_handling(self, make_template, cookiecutter):
        """An unreadable .repo file raises PermissionError instead of falling back."""
        template_directory = make_template(
            name='permission_error_template', repo_contents='gh:user/repo\n'
        )
        repo_file = template_directory / '.repo'
        repo_file.chmod(0)
        try:
            if os.access(repo_file, os.R_OK):
                pytest.skip('this user can read a file without read permission (root, Windows)')

            with pytest.raises(PermissionError):
                build('permission_error_template')
        finally:
            repo_file.chmod(0o644)

        cookiecutter.assert_not_called()

    def test_build_cookiecutter_import_error(self, make_template, cookiecutter):
        """An ImportError raised inside cookiecutter is not caught."""
        make_template(name='import_error_template')
        cookiecutter.side_effect = ImportError('Cookiecutter not installed')

        with pytest.raises(ImportError, match='Cookiecutter not installed'):
            build('import_error_template')

    def test_build_template_not_found_error(self, templates_directory, monkeypatch):
        """A template that does not exist reaches the real cookiecutter, which cannot find it."""
        # cookiecutter reads ~/.cookiecutterrc: an empty home keeps the user's out of the test
        monkeypatch.setenv('HOME', str(templates_directory))
        monkeypatch.setenv('USERPROFILE', str(templates_directory))
        monkeypatch.delenv('COOKIECUTTER_CONFIG', raising=False)

        with pytest.raises(RepositoryNotFound, match='nonexistent_template'):
            build('nonexistent_template')

    def test_build_template_without_cookiecutter_json(
        self, make_template, templates_directory, monkeypatch
    ):
        """A template directory that is not a cookiecutter template is refused by cookiecutter."""
        make_template(name='not_a_cookiecutter_template')
        monkeypatch.setenv('HOME', str(templates_directory))
        monkeypatch.setenv('USERPROFILE', str(templates_directory))
        monkeypatch.delenv('COOKIECUTTER_CONFIG', raising=False)

        with pytest.raises(RepositoryNotFound, match='not_a_cookiecutter_template'):
            build('not_a_cookiecutter_template')

    def test_build_cookiecutter_timeout_error(self, make_template, cookiecutter):
        """A cookiecutter timeout (e.g. cloning a remote template) is not caught."""
        make_template(name='timeout_template', repo_contents='gh:user/slow\n')
        cookiecutter.side_effect = TimeoutError('Request timed out')

        with pytest.raises(TimeoutError, match='Request timed out'):
            build('timeout_template')


if __name__ == '__main__':
    pytest.main([__file__])
