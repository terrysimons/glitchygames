"""Template building functionality tests.

Every test builds from real template directories under ``tmp_path`` (or the bundled ones), so
``build()`` really opens (or fails to open) each ``.repo`` file. Only cookiecutter itself is
patched: a real one would download a remote template or prompt for its variables.
"""

import pytest

from glitchygames.templates import build

REMOTE_TEMPLATE_URL = 'https://github.com/user/repo.git'


class TestTemplateBuilding:
    """build() takes the template location from a .repo file, else the template directory."""

    def test_build_local_template(self, make_template, cookiecutter):
        """A template without a .repo file is built from its own directory."""
        template_directory = make_template(name='local_template')

        build('local_template')

        cookiecutter.assert_called_once_with(str(template_directory))

    def test_build_remote_template(self, make_template, cookiecutter):
        """A .repo file's location is used without its line's newline (BUGS.md #107)."""
        make_template(name='remote_template', repo_contents=f'{REMOTE_TEMPLATE_URL}\n')

        build('remote_template')

        cookiecutter.assert_called_once_with(REMOTE_TEMPLATE_URL)

    def test_build_remote_template_without_a_trailing_newline(self, make_template, cookiecutter):
        """A .repo file whose only line has no newline names the location as written."""
        make_template(name='remote_template', repo_contents=REMOTE_TEMPLATE_URL)

        build('remote_template')

        cookiecutter.assert_called_once_with(REMOTE_TEMPLATE_URL)

    def test_build_template_with_empty_repo_file(self, make_template, cookiecutter):
        """An empty .repo file still wins over the directory: cookiecutter gets ''."""
        make_template(name='empty_repo_template', repo_contents='')

        build('empty_repo_template')

        cookiecutter.assert_called_once_with('')

    def test_build_template_with_whitespace_repo_file(self, make_template, cookiecutter):
        """A whitespace-only .repo file strips to ''."""
        make_template(name='whitespace_repo_template', repo_contents='   \n')

        build('whitespace_repo_template')

        cookiecutter.assert_called_once_with('')

    def test_build_template_with_multiple_lines_in_repo(self, make_template, cookiecutter):
        """Only the .repo file's first line names the location."""
        make_template(
            name='multi_line_repo_template',
            repo_contents=f'{REMOTE_TEMPLATE_URL}\nhttps://github.com/other/ignored.git\n',
        )

        build('multi_line_repo_template')

        cookiecutter.assert_called_once_with(REMOTE_TEMPLATE_URL)

    def test_build_template_with_stripped_whitespace(self, make_template, cookiecutter):
        """Whitespace around the .repo file's location is stripped."""
        make_template(
            name='stripped_whitespace_template',
            repo_contents=f'  {REMOTE_TEMPLATE_URL}  \n',
        )

        build('stripped_whitespace_template')

        cookiecutter.assert_called_once_with(REMOTE_TEMPLATE_URL)

    def test_build_template_path_is_under_the_templates_directory(
        self, make_template, cookiecutter, monkeypatch, tmp_path_factory
    ):
        """The template is looked up in the templates directory, not the working directory."""
        template_directory = make_template(name='path_test_template')
        # A same-named template with a .repo file in the working directory must not be used
        working_directory = tmp_path_factory.mktemp('working_directory')
        (working_directory / 'path_test_template').mkdir()
        (working_directory / 'path_test_template' / '.repo').write_text(REMOTE_TEMPLATE_URL)
        monkeypatch.chdir(working_directory)

        build('path_test_template')

        cookiecutter.assert_called_once_with(str(template_directory))

    def test_build_bundled_pong_template(self, cookiecutter):
        """The bundled pong template names its remote repository in its .repo file."""
        build('pong')

        cookiecutter.assert_called_once_with(
            'https://github.com/sabadam32/cookiecutter-glitchygames-pong'
        )


if __name__ == '__main__':
    pytest.main([__file__])
