"""Tests for game objects sound functionality.

This module tests sound loading, SFX constants, and sound-related functionality.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.game_objects import load_sound
from glitchygames.game_objects.sounds import SFX

from tests.mocks.test_mock_factory import MockFactory


class TestGameObjectsSounds(unittest.TestCase):
    """Test game objects sound functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all patchers
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_load_sound_function(self):
        """Test load_sound function."""
        with patch("glitchygames.game_objects.sounds.pygame.mixer.Sound") as mock_sound_class:
            mock_sound = Mock()
            mock_sound_class.return_value = mock_sound

            result = load_sound("test.wav", 0.5)

            # Verify the sound was created with correct path
            expected_path = (Path(__file__).parent.parent.parent / "glitchygames" /
                            "game_objects" / "snd_files" / "test.wav")
            mock_sound_class.assert_called_once_with(expected_path)

            # Verify volume was set
            mock_sound.set_volume.assert_called_once_with(0.5)

            # Verify return value
            assert result == mock_sound

    def test_load_sound_default_volume(self):
        """Test load_sound function with default volume."""
        with patch("glitchygames.game_objects.sounds.pygame.mixer.Sound") as mock_sound_class:
            mock_sound = Mock()
            mock_sound_class.return_value = mock_sound

            result = load_sound("test.wav")

            # Verify default volume was used
            mock_sound.set_volume.assert_called_once_with(0.25)
            assert result == mock_sound

    def test_sfx_constants(self):
        """Test SFX constants."""
        assert SFX.BOUNCE == "sfx_bounce.wav"
        assert SFX.SLAP == "sfx_slap.wav"

    def test_load_sound_with_nonexistent_file(self):
        """Test load_sound with nonexistent file."""
        with patch("glitchygames.game_objects.sounds.pygame.mixer.Sound") as mock_sound_class:
            mock_sound_class.side_effect = FileNotFoundError("File not found")

            with pytest.raises(FileNotFoundError):
                load_sound("nonexistent.wav")
