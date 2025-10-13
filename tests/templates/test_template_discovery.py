"""Template discovery functionality tests."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.templates import get_templates

from mocks.test_mock_factory import create_template_directory_mock


class TestTemplateDiscovery(unittest.TestCase):
    """Test template discovery functionality."""

    def test_get_templates_basic(self):
        """Test basic template discovery."""
        with patch("glitchygames.templates.path") as mock_path:
            # Use centralized mock factory
            mock_directory = create_template_directory_mock(["template1", "template2"])
            mock_path.iterdir.return_value = mock_directory.iterdir.return_value

            # Mock Path.is_dir() static method calls
            with patch("pathlib.Path.is_dir") as mock_is_dir:
                def is_dir_side_effect(path):
                    # Check if the path ends with a template name
                    path_str = str(path)
                    return any(template in path_str for template in [
                        "template1", "template2"
                    ])

                mock_is_dir.side_effect = is_dir_side_effect

                templates = get_templates()
                assert templates == ["template1", "template2"]

    def test_get_templates_empty(self):
        """Test get_templates with empty directory."""
        with patch("glitchygames.templates.path") as mock_path:
            mock_path.iterdir.return_value = []
            templates = get_templates()
            assert templates == []

    def test_get_templates_no_directories(self):
        """Test get_templates with no directories."""
        with patch("glitchygames.templates.path") as mock_path:
            mock_file1 = Mock()
            mock_file1.name = "file1.txt"

            mock_file2 = Mock()
            mock_file2.name = "file2.py"

            mock_path.iterdir.return_value = [mock_file1, mock_file2]

            with patch("pathlib.Path.is_dir") as mock_is_dir:
                mock_is_dir.return_value = False
                templates = get_templates()
                assert templates == []

    def test_get_templates_hidden_directories(self):
        """Test get_templates with hidden directories (implementation doesn't filter them)."""
        with patch("glitchygames.templates.path") as mock_path:
            # Use centralized mock factory
            mock_items = []
            for name in ["template1", "__pycache__", ".git", "__init__.py"]:
                mock_item = Mock()
                mock_item.name = name
                mock_items.append(mock_item)

            mock_path.iterdir.return_value = mock_items

            with patch("pathlib.Path.is_dir") as mock_is_dir:
                def is_dir_side_effect(path):
                    path_str = str(path)
                    return any(name in path_str for name in [
                        "template1", "__pycache__", ".git", "__init__.py"
                    ])

                mock_is_dir.side_effect = is_dir_side_effect

                templates = get_templates()
                # The actual implementation doesn't filter hidden directories
                assert "template1" in templates
                # Note: The current implementation includes hidden directories
                assert len(templates) >= 1

    def test_get_templates_filters_directories(self):
        """Test that get_templates properly filters directories."""
        with patch("glitchygames.templates.path") as mock_path:
            mock_dir = Mock()
            mock_dir.name = "valid_template"

            mock_file = Mock()
            mock_file.name = "not_a_template.txt"

            mock_path.iterdir.return_value = [mock_dir, mock_file]

            with patch("pathlib.Path.is_dir") as mock_is_dir:
                def is_dir_side_effect(path):
                    return "valid_template" in str(path)

                mock_is_dir.side_effect = is_dir_side_effect

                templates = get_templates()
                assert templates == ["valid_template"]


if __name__ == "__main__":
    unittest.main()
