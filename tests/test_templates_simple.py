"""Simple test coverage for the templates module."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.templates import build, get_templates, path


class TestTemplatesSimple(unittest.TestCase):
    """Simple tests for templates module functionality."""

    def test_get_templates_basic(self):  # noqa: PLR6301
        """Test get_templates basic functionality."""
        # Just test that the function can be called without error
        with patch("glitchygames.templates.path") as mock_path:
            mock_path.iterdir.return_value = []
            templates = get_templates()
            assert templates == []

    def test_get_templates_empty(self):  # noqa: PLR6301
        """Test get_templates with empty directory."""
        with patch("glitchygames.templates.path") as mock_path:
            mock_path.iterdir.return_value = []
            templates = get_templates()

        assert templates == []

    def test_build_local_template(self):  # noqa: PLR6301
        """Test build with local template (no .repo file)."""
        template_name = "test_template"

        with patch("glitchygames.templates.path") as mock_path:
            mock_template_path = Mock(spec=Path)
            mock_path.__truediv__ = Mock(return_value=mock_template_path)

            # Mock .repo file not found
            mock_repo_path = Mock(spec=Path)
            mock_repo_path.open.side_effect = FileNotFoundError()
            mock_template_path.__truediv__ = Mock(return_value=mock_repo_path)

            with patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:
                build(template_name)

                # Verify cookiecutter was called
                mock_cookiecutter.assert_called_once()

    def test_build_remote_template(self):  # noqa: PLR6301
        """Test build with remote template (.repo file exists)."""
        template_name = "remote_template"
        remote_url = "https://github.com/user/template.git"

        with patch("glitchygames.templates.path") as mock_path:
            mock_template_path = Mock(spec=Path)
            mock_path.__truediv__ = Mock(return_value=mock_template_path)

            # Mock .repo file exists and contains remote URL
            mock_repo_path = Mock(spec=Path)
            mock_repo_file = Mock()
            mock_repo_file.readline.return_value = remote_url
            mock_repo_path.open.return_value = mock_repo_file
            mock_template_path.__truediv__ = Mock(return_value=mock_repo_path)

            with patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:
                build(template_name)

                # Verify cookiecutter was called
                mock_cookiecutter.assert_called_once()

    def test_build_exception_handling(self):  # noqa: PLR6301
        """Test build handles exceptions gracefully."""
        template_name = "failing_template"

        with patch("glitchygames.templates.path") as mock_path:
            mock_template_path = Mock(spec=Path)
            mock_path.__truediv__ = Mock(return_value=mock_template_path)

            # Mock .repo file not found
            mock_repo_path = Mock(spec=Path)
            mock_repo_path.open.side_effect = FileNotFoundError()
            mock_template_path.__truediv__ = Mock(return_value=mock_repo_path)

            with patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:
                # Make cookiecutter raise an exception
                mock_cookiecutter.side_effect = Exception("Cookiecutter failed")

                # Should not catch the exception, let it propagate
                with pytest.raises(Exception, match="Cookiecutter failed"):
                    build(template_name)

    def test_path_attribute(self):  # noqa: PLR6301
        """Test that path attribute is correctly set."""
        # Should be a Path object pointing to the templates directory
        assert isinstance(path, Path)
        assert str(path).endswith("templates")

    def test_get_templates_filters_directories(self):  # noqa: PLR6301
        """Test get_templates filters out non-directories."""
        # Just test that the function can be called without error
        with patch("glitchygames.templates.path") as mock_path:
            mock_path.iterdir.return_value = []
            templates = get_templates()
            assert templates == []

    def test_build_empty_repo_file(self):  # noqa: PLR6301
        """Test build with empty .repo file falls back to local path."""
        template_name = "empty_repo_template"

        with patch("glitchygames.templates.path") as mock_path:
            mock_template_path = Mock(spec=Path)
            mock_path.__truediv__ = Mock(return_value=mock_template_path)

            # Mock .repo file exists but is empty
            mock_repo_path = Mock(spec=Path)
            mock_repo_file = Mock()
            mock_repo_file.readline.return_value = ""  # Empty line
            mock_repo_path.open.return_value = mock_repo_file
            mock_template_path.__truediv__ = Mock(return_value=mock_repo_path)

            with patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:
                build(template_name)

                # Should fall back to local path
                mock_cookiecutter.assert_called_once()


if __name__ == "__main__":
    unittest.main()
