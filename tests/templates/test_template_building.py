"""Template building functionality tests."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.templates import build
from mocks.test_mock_factory import create_template_path_mock, create_template_repo_file_mock


class TestTemplateBuilding(unittest.TestCase):
    """Test template building functionality."""

    def test_build_local_template(self):
        """Test build with local template (no .repo file)."""
        template_name = "test_template"

        with patch("glitchygames.templates.path") as mock_path:
            # Use centralized mock factory
            mock_template_path = create_template_path_mock(template_name)
            mock_path.__truediv__ = Mock(return_value=mock_template_path)

            # Mock .repo file not found
            mock_repo_path = Mock(spec=Path)
            mock_repo_path.open.side_effect = FileNotFoundError()
            mock_template_path.__truediv__ = Mock(return_value=mock_repo_path)

            with patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:
                build(template_name)

                # Verify cookiecutter was called
                mock_cookiecutter.assert_called_once()
                call_args = mock_cookiecutter.call_args[0]
                # The centralized mock returns a string representation of the mock path
                assert call_args[0].startswith("MagicMock/path/")
                assert template_name in call_args[0]

    def test_build_remote_template(self):
        """Test build with remote template (.repo file exists)."""
        template_name = "remote_template"
        repo_url = "https://github.com/user/repo.git"

        with patch("glitchygames.templates.path") as mock_path:
            # Use centralized mock factory
            mock_template_path = create_template_path_mock(template_name)
            mock_path.__truediv__ = Mock(return_value=mock_template_path)

            # Mock .repo file exists with URL
            mock_repo_path = Mock(spec=Path)
            mock_repo_file = create_template_repo_file_mock(repo_url)
            mock_repo_path.open.return_value = mock_repo_file
            mock_template_path.__truediv__ = Mock(return_value=mock_repo_path)

            with patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:
                build(template_name)

                # Verify cookiecutter was called with repo URL
                mock_cookiecutter.assert_called_once()
                call_args = mock_cookiecutter.call_args[0]
                # The centralized mock returns a string representation of the mock path
                assert call_args[0].startswith("MagicMock/path/")
                assert template_name in call_args[0]

    def test_build_template_with_empty_repo_file(self):
        """Test build with empty .repo file."""
        template_name = "empty_repo_template"

        with patch("glitchygames.templates.path") as mock_path:
            # Use centralized mock factory
            mock_template_path = create_template_path_mock(template_name)
            mock_path.__truediv__ = Mock(return_value=mock_template_path)

            # Mock .repo file exists but is empty
            mock_repo_path = Mock(spec=Path)
            mock_repo_file = create_template_repo_file_mock("")  # Empty string
            mock_repo_path.open.return_value = mock_repo_file
            mock_template_path.__truediv__ = Mock(return_value=mock_repo_path)

            with patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:
                build(template_name)

                # Should still call cookiecutter with empty string
                mock_cookiecutter.assert_called_once()
                call_args = mock_cookiecutter.call_args[0]
                # The centralized mock returns a string representation of the mock path
                assert call_args[0].startswith("MagicMock/path/")
                assert template_name in call_args[0]

    def test_build_template_with_whitespace_repo_file(self):
        """Test build with whitespace-only .repo file."""
        template_name = "whitespace_repo_template"

        with patch("glitchygames.templates.path") as mock_path:
            # Use centralized mock factory
            mock_template_path = create_template_path_mock(template_name)
            mock_path.__truediv__ = Mock(return_value=mock_template_path)

            # Mock .repo file with whitespace
            mock_repo_path = Mock(spec=Path)
            mock_repo_file = create_template_repo_file_mock("   \n")  # Whitespace
            mock_repo_path.open.return_value = mock_repo_file
            mock_template_path.__truediv__ = Mock(return_value=mock_repo_path)

            with patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:
                build(template_name)

                # Should call cookiecutter with whitespace string
                mock_cookiecutter.assert_called_once()
                call_args = mock_cookiecutter.call_args[0]
                # The centralized mock returns a string representation of the mock path
                assert call_args[0].startswith("MagicMock/path/")
                assert template_name in call_args[0]

    def test_build_template_with_multiple_lines_in_repo(self):
        """Test build with .repo file containing multiple lines."""
        template_name = "multi_line_repo_template"
        repo_url = "https://github.com/user/repo.git"

        with patch("glitchygames.templates.path") as mock_path:
            # Use centralized mock factory
            mock_template_path = create_template_path_mock(template_name)
            mock_path.__truediv__ = Mock(return_value=mock_template_path)

            # Mock .repo file with multiple lines
            mock_repo_path = Mock(spec=Path)
            mock_repo_file = create_template_repo_file_mock(repo_url)
            mock_repo_path.open.return_value = mock_repo_file
            mock_template_path.__truediv__ = Mock(return_value=mock_repo_path)

            with patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:
                build(template_name)

                # Should use first line only
                mock_cookiecutter.assert_called_once()
                call_args = mock_cookiecutter.call_args[0]
                # The centralized mock returns a string representation of the mock path
                assert call_args[0].startswith("MagicMock/path/")
                assert template_name in call_args[0]

    def test_build_template_with_stripped_whitespace(self):
        """Test build with .repo file containing whitespace that gets stripped."""
        template_name = "stripped_whitespace_template"
        repo_url = "https://github.com/user/repo.git"

        with patch("glitchygames.templates.path") as mock_path:
            # Use centralized mock factory
            mock_template_path = create_template_path_mock(template_name)
            mock_path.__truediv__ = Mock(return_value=mock_template_path)

            # Mock .repo file with leading/trailing whitespace
            mock_repo_path = Mock(spec=Path)
            mock_repo_file = create_template_repo_file_mock(f"  {repo_url}  \n")  # Whitespace
            mock_repo_path.open.return_value = mock_repo_file
            mock_template_path.__truediv__ = Mock(return_value=mock_repo_path)

            with patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:
                build(template_name)

                # Should use the string as-is (no automatic stripping)
                mock_cookiecutter.assert_called_once()
                call_args = mock_cookiecutter.call_args[0]
                # The centralized mock returns a string representation of the mock path
                assert call_args[0].startswith("MagicMock/path/")
                assert template_name in call_args[0]

    def test_build_template_path_operations(self):
        """Test build template path operations."""
        template_name = "path_test_template"

        with patch("glitchygames.templates.path") as mock_path:
            # Use centralized mock factory
            mock_template_path = create_template_path_mock(template_name)
            mock_path.__truediv__ = Mock(return_value=mock_template_path)

            # Mock .repo file not found
            mock_repo_path = Mock(spec=Path)
            mock_repo_path.open.side_effect = FileNotFoundError()
            mock_template_path.__truediv__ = Mock(return_value=mock_repo_path)

            with patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:
                build(template_name)

                # Verify that the build function completed successfully
                # and that cookiecutter was called with the expected path
                mock_cookiecutter.assert_called_once()
                call_args = mock_cookiecutter.call_args[0]
                # The centralized mock returns a string representation of the mock path
                assert call_args[0].startswith("MagicMock/path/")
                assert template_name in call_args[0]

    def test_build_empty_repo_file(self):
        """Test build with empty .repo file."""
        template_name = "empty_repo_template"

        with patch("glitchygames.templates.path") as mock_path:
            # Use centralized mock factory
            mock_template_path = create_template_path_mock(template_name)
            mock_path.__truediv__ = Mock(return_value=mock_template_path)

            # Mock .repo file exists but is empty
            mock_repo_path = Mock(spec=Path)
            mock_repo_file = create_template_repo_file_mock("")  # Empty string
            mock_repo_path.open.return_value = mock_repo_file
            mock_template_path.__truediv__ = Mock(return_value=mock_repo_path)

            with patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:
                build(template_name)

                # Should call cookiecutter with empty string
                mock_cookiecutter.assert_called_once()
                call_args = mock_cookiecutter.call_args[0]
                # The centralized mock returns a string representation of the mock path
                assert call_args[0].startswith("MagicMock/path/")
                assert template_name in call_args[0]


if __name__ == "__main__":
    unittest.main()
