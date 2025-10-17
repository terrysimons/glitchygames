"""Template error handling tests."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.templates import build

from tests.mocks.test_mock_factory import create_template_path_mock


class TestTemplateErrors:
    """Test template error handling."""

    def test_build_template_cookiecutter_exception(self):
        """Test build template when cookiecutter raises an exception."""
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

                # Should not catch the exception - let it propagate
                with pytest.raises(Exception, match="Cookiecutter failed"):
                    build(template_name)

    def test_build_exception_handling(self):
        """Test build exception handling."""
        template_name = "exception_template"

        with patch("glitchygames.templates.path") as mock_path:
            mock_template_path = Mock(spec=Path)
            mock_path.__truediv__ = Mock(return_value=mock_template_path)

            # Mock .repo file not found
            mock_repo_path = Mock(spec=Path)
            mock_repo_path.open.side_effect = FileNotFoundError()
            mock_template_path.__truediv__ = Mock(return_value=mock_repo_path)

            with patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:
                # Make cookiecutter raise a specific exception
                mock_cookiecutter.side_effect = RuntimeError("Template not found")

                with pytest.raises(RuntimeError, match="Template not found"):
                    build(template_name)

    def test_build_file_not_found_error(self):
        """Test build when .repo file is not found."""
        template_name = "no_repo_template"

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

                # Should call cookiecutter with local path
                mock_cookiecutter.assert_called_once()
                call_args = mock_cookiecutter.call_args[0]
                # The centralized mock returns a string representation of the mock path
                assert call_args[0].startswith("MagicMock/path/")
                assert template_name in call_args[0]

    def test_build_io_error_handling(self):
        """Test build when .repo file causes IO error."""
        template_name = "io_error_template"

        with patch("glitchygames.templates.path") as mock_path:
            # Use centralized mocks
            mock_template_path = create_template_path_mock(template_name)
            mock_path.__truediv__ = Mock(return_value=mock_template_path)

            # Mock .repo file causes IO error - need to mock the correct path structure
            mock_repo_path = Mock(spec=Path)
            mock_repo_path.open.side_effect = OSError("Permission denied")
            mock_template_path.__truediv__ = Mock(return_value=mock_repo_path)

            with patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:
                # Make cookiecutter raise an OSError
                mock_cookiecutter.side_effect = OSError("Permission denied")

                # The code only catches FileNotFoundError, not OSError
                with pytest.raises(OSError, match="Permission denied"):
                    build(template_name)

    def test_build_permission_error_handling(self):
        """Test build when .repo file causes permission error."""
        template_name = "permission_error_template"

        with patch("glitchygames.templates.path") as mock_path:
            # Use centralized mock factory
            mock_template_path = create_template_path_mock(template_name)
            mock_path.__truediv__ = Mock(return_value=mock_template_path)

            # Mock .repo file causes permission error
            mock_repo_path = Mock(spec=Path)
            mock_repo_path.open.side_effect = PermissionError("Access denied")
            mock_template_path.__truediv__ = Mock(return_value=mock_repo_path)

            with patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:
                # Make cookiecutter raise a PermissionError
                mock_cookiecutter.side_effect = PermissionError("Access denied")

                # Should not catch PermissionError - let it propagate
                with pytest.raises(PermissionError, match="Access denied"):
                    build(template_name)

    def test_build_cookiecutter_import_error(self):
        """Test build when cookiecutter import fails."""
        template_name = "import_error_template"

        with patch("glitchygames.templates.path") as mock_path:
            mock_template_path = Mock(spec=Path)
            mock_path.__truediv__ = Mock(return_value=mock_template_path)

            # Mock .repo file not found
            mock_repo_path = Mock(spec=Path)
            mock_repo_path.open.side_effect = FileNotFoundError()
            mock_template_path.__truediv__ = Mock(return_value=mock_repo_path)

            with patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:
                # Make cookiecutter raise ImportError
                mock_cookiecutter.side_effect = ImportError("Cookiecutter not installed")

                with pytest.raises(ImportError, match="Cookiecutter not installed"):
                    build(template_name)

    def test_build_template_not_found_error(self):
        """Test build when template directory doesn't exist."""
        template_name = "nonexistent_template"

        with patch("glitchygames.templates.path") as mock_path:
            # Mock path operations to raise FileNotFoundError
            mock_path.__truediv__.side_effect = FileNotFoundError("Template not found")

            with patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:
                # Make cookiecutter raise a FileNotFoundError
                mock_cookiecutter.side_effect = FileNotFoundError("Template not found")

                # The error will be raised by cookiecutter, not by our code
                with pytest.raises(FileNotFoundError, match="Template not found"):
                    build(template_name)

    def test_build_cookiecutter_timeout_error(self):
        """Test build when cookiecutter times out."""
        template_name = "timeout_template"

        with patch("glitchygames.templates.path") as mock_path:
            mock_template_path = Mock(spec=Path)
            mock_path.__truediv__ = Mock(return_value=mock_template_path)

            # Mock .repo file not found
            mock_repo_path = Mock(spec=Path)
            mock_repo_path.open.side_effect = FileNotFoundError()
            mock_template_path.__truediv__ = Mock(return_value=mock_repo_path)

            with patch("glitchygames.templates.cookiecutter") as mock_cookiecutter:
                # Make cookiecutter raise timeout error
                mock_cookiecutter.side_effect = TimeoutError("Request timed out")

                with pytest.raises(TimeoutError, match="Request timed out"):
                    build(template_name)
