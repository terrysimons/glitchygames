"""Template discovery functionality tests.

Each test lists a real temporary templates directory (or the bundled one), with real files and
subdirectories, so get_templates() really asks the filesystem what is a directory.
"""

import sys
from pathlib import Path

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.templates import get_templates


class TestTemplateDiscovery:
    """get_templates() lists the template directories, skipping dunder entries and files."""

    def test_get_templates_basic(self, make_template):
        """Every template directory is listed."""
        make_template(name='template1')
        make_template(name='template2')

        assert sorted(get_templates()) == ['template1', 'template2']

    def test_get_templates_empty(self, templates_directory):
        """An empty templates directory has no templates."""
        assert get_templates() == []

    def test_get_templates_no_directories(self, templates_directory):
        """Files are not templates."""
        (templates_directory / 'file1.txt').write_text('not a template')
        (templates_directory / 'file2.py').write_text('# not a template\n')

        assert get_templates() == []

    def test_get_templates_hidden_directories(self, make_template, templates_directory):
        """Dunder entries are skipped; hidden directories are not (they are not filtered)."""
        make_template(name='template1')
        make_template(name='__pycache__')
        make_template(name='.git')
        (templates_directory / '__init__.py').write_text('')

        assert sorted(get_templates()) == ['.git', 'template1']

    def test_get_templates_filters_directories(self, make_template, templates_directory):
        """Only the directory is listed when a file sits beside it."""
        make_template(name='valid_template')
        (templates_directory / 'not_a_template.txt').write_text('not a template')

        assert get_templates() == ['valid_template']

    def test_get_templates_bundled(self):
        """The package's own templates directory lists the bundled pong template."""
        assert get_templates() == ['pong']


if __name__ == '__main__':
    pytest.main([__file__])
