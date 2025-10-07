"""Test coverage for the templates module.

This module tests the template building functionality which is
essential for project generation in the game engine. These functions handle:

1. Template discovery and listing
2. Template building using cookiecutter
3. Local and remote template handling
4. File system operations for templates

Without these tests, the templates module coverage remains incomplete
as the core template functionality is not exercised.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from glitchygames.templates import build, get_templates


class TestTemplatesCoverage:
    """Test coverage for templates module functions."""

    def test_get_templates_basic(self):  # noqa: PLR6301
        """Test basic template discovery."""
        with patch("glitchygames.templates.path") as mock_path:
            # Mock directory structure
            mock_dir1 = Mock()
            mock_dir1.name = "template1"

            mock_dir2 = Mock()
            mock_dir2.name = "template2"

            mock_file = Mock()
            mock_file.name = "file.txt"

            mock_hidden = Mock()
            mock_hidden.name = "__pycache__"

            mock_path.iterdir.return_value = [mock_dir1, mock_dir2, mock_file, mock_hidden]

            # Mock Path.is_dir() static method calls
            with patch("pathlib.Path.is_dir") as mock_is_dir:
                def is_dir_side_effect(path):
                    # Check if the path ends with a template name
                    path_str = str(path)
                    return any(template in path_str for template in [
                        "template1", "template2", "__pycache__"
                    ])
                mock_is_dir.side_effect = is_dir_side_effect

                result = get_templates()

            expected = ["template1", "template2"]
            assert result == expected

    def test_get_templates_empty(self):  # noqa: PLR6301
        """Test template discovery with empty directory."""
        with patch("glitchygames.templates.path") as mock_path:
            mock_path.iterdir.return_value = []

            result = get_templates()

            assert result == []

    def test_get_templates_no_directories(self):  # noqa: PLR6301
        """Test template discovery with no directories."""
        with patch("glitchygames.templates.path") as mock_path:
            mock_file1 = Mock()
            mock_file1.name = "file1.txt"

            mock_file2 = Mock()
            mock_file2.name = "file2.py"

            mock_path.iterdir.return_value = [mock_file1, mock_file2]

            # Mock Path.is_dir() to return False for all paths
            with patch("pathlib.Path.is_dir", return_value=False):
                result = get_templates()

            assert result == []

    def test_get_templates_hidden_directories(self):  # noqa: PLR6301
        """Test template discovery filtering out hidden directories."""
        with patch("glitchygames.templates.path") as mock_path:
            mock_dir1 = Mock()
            mock_dir1.name = "template1"

            mock_hidden1 = Mock()
            mock_hidden1.name = "__pycache__"

            mock_hidden2 = Mock()
            mock_hidden2.name = ".git"

            mock_path.iterdir.return_value = [mock_dir1, mock_hidden1, mock_hidden2]

            # Mock Path.is_dir() to return True for directories
            with patch("pathlib.Path.is_dir", return_value=True):
                result = get_templates()

            # The function filters out names starting with "__" but not "."
            expected = ["template1", ".git"]
            assert result == expected

    def test_build_local_template(self):  # noqa: PLR6301
        """Test building from local template."""
        template_name = "test_template"

        with patch("glitchygames.templates.path") as mock_path, \
             patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:

            # Mock the path operations correctly
            mock_template_path = Path("/fake/path/templates/test_template")
            mock_path.__truediv__ = lambda _, other: mock_template_path / other

            # Mock that .repo file doesn't exist (local template)
            with patch("pathlib.Path.open", side_effect=FileNotFoundError):
                build(template_name)

            # The actual call will be with the constructed path
            mock_cookiecutter.assert_called_once()
            call_args = mock_cookiecutter.call_args[0][0]
            assert str(call_args).endswith("test_template")

    def test_build_remote_template(self):  # noqa: PLR6301
        """Test building from remote template."""
        template_name = "test_template"
        remote_url = "https://github.com/user/repo.git"

        with patch("glitchygames.templates.path") as mock_path, \
             patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:

            mock_template_path = Path("/fake/path/templates/test_template")
            mock_path.__truediv__ = lambda _, other: mock_template_path / other

            # Mock .repo file exists with remote URL
            mock_repo_file = Mock()
            mock_repo_file.__enter__ = Mock(return_value=mock_repo_file)
            mock_repo_file.__exit__ = Mock(return_value=None)
            mock_repo_file.readline.return_value = remote_url

            with patch("pathlib.Path.open", return_value=mock_repo_file):
                build(template_name)

            mock_cookiecutter.assert_called_once_with(remote_url)

    def test_build_template_with_empty_repo_file(self):  # noqa: PLR6301
        """Test building template with empty .repo file."""
        template_name = "test_template"

        with patch("glitchygames.templates.path") as mock_path, \
             patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:

            mock_template_path = Path("/fake/path/templates/test_template")
            mock_path.__truediv__ = lambda _, other: mock_template_path / other

            # Mock .repo file exists but is empty
            mock_repo_file = Mock()
            mock_repo_file.__enter__ = Mock(return_value=mock_repo_file)
            mock_repo_file.__exit__ = Mock(return_value=None)
            mock_repo_file.readline.return_value = ""

            with patch("pathlib.Path.open", return_value=mock_repo_file):
                build(template_name)

            # Should use the empty string from repo file
            mock_cookiecutter.assert_called_once_with("")

    def test_build_template_with_whitespace_repo_file(self):  # noqa: PLR6301
        """Test building template with whitespace-only .repo file."""
        template_name = "test_template"

        with patch("glitchygames.templates.path") as mock_path, \
             patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:

            mock_template_path = Path("/fake/path/templates/test_template")
            mock_path.__truediv__ = lambda _, other: mock_template_path / other

            # Mock .repo file exists but contains only whitespace
            mock_repo_file = Mock()
            mock_repo_file.__enter__ = Mock(return_value=mock_repo_file)
            mock_repo_file.__exit__ = Mock(return_value=None)
            mock_repo_file.readline.return_value = "   \n"

            with patch("pathlib.Path.open", return_value=mock_repo_file):
                build(template_name)

            # Should use the whitespace string from repo file
            mock_cookiecutter.assert_called_once_with("   \n")

    def test_build_template_cookiecutter_exception(self):  # noqa: PLR6301
        """Test building template when cookiecutter raises exception."""
        template_name = "test_template"

        with patch("glitchygames.templates.path") as mock_path, \
             patch("glitchygames.templates.cookiecutter") as mock_cookiecutter, \
             patch("pathlib.Path.open", side_effect=FileNotFoundError):

            mock_template_path = Path("/fake/path/templates/test_template")
            mock_path.__truediv__ = lambda _, other: mock_template_path / other

            # Mock cookiecutter to raise an exception
            mock_cookiecutter.side_effect = Exception("Cookiecutter error")

            with pytest.raises(Exception, match="Cookiecutter error"):
                build(template_name)

    def test_build_template_path_operations(self):  # noqa: PLR6301
        """Test that path operations work correctly."""
        template_name = "test_template"

        with patch("glitchygames.templates.path") as mock_path, \
             patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:

            # Test that path operations are called correctly
            mock_template_path = Mock()
            mock_path.__truediv__ = Mock(return_value=mock_template_path)

            with patch("pathlib.Path.open", side_effect=FileNotFoundError):
                build(template_name)

            # Verify that cookiecutter was called
            mock_cookiecutter.assert_called_once()

    def test_build_template_with_multiple_lines_in_repo(self):  # noqa: PLR6301
        """Test building template with .repo file containing multiple lines."""
        template_name = "test_template"
        remote_url = "https://github.com/user/repo.git"

        with patch("glitchygames.templates.path") as mock_path, \
             patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:

            mock_template_path = Path("/fake/path/templates/test_template")
            mock_path.__truediv__ = lambda _, other: mock_template_path / other

            # Mock .repo file with multiple lines (only first line should be used)
            mock_repo_file = Mock()
            mock_repo_file.__enter__ = Mock(return_value=mock_repo_file)
            mock_repo_file.__exit__ = Mock(return_value=None)
            mock_repo_file.readline.return_value = remote_url + "\n"

            with patch("pathlib.Path.open", return_value=mock_repo_file):
                build(template_name)

            # Should use the first line with newline
            mock_cookiecutter.assert_called_once_with(remote_url + "\n")

    def test_build_template_with_stripped_whitespace(self):  # noqa: PLR6301
        """Test building template with .repo file containing whitespace around URL."""
        template_name = "test_template"
        remote_url = "https://github.com/user/repo.git"

        with patch("glitchygames.templates.path") as mock_path, \
             patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:

            mock_template_path = Path("/fake/path/templates/test_template")
            mock_path.__truediv__ = lambda _, other: mock_template_path / other

            # Mock .repo file with whitespace around URL
            mock_repo_file = Mock()
            mock_repo_file.__enter__ = Mock(return_value=mock_repo_file)
            mock_repo_file.__exit__ = Mock(return_value=None)
            mock_repo_file.readline.return_value = f"  {remote_url}  \n"

            with patch("pathlib.Path.open", return_value=mock_repo_file):
                build(template_name)

            # Should use the URL with whitespace (no automatic stripping)
            mock_cookiecutter.assert_called_once_with(f"  {remote_url}  \n")
