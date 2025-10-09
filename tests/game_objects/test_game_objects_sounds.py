"""Tests for game objects sound functionality.

This module tests sound loading, SFX constants, and sound-related functionality.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.game_objects import load_sound
from glitchygames.game_objects.sounds import SFX

from mocks.test_mock_factory import MockFactory


class TestGameObjectsSounds:
    """Test game objects sound functionality."""

    def test_load_sound_function(self, mock_pygame_patches):
        """Test load_sound function."""
        with patch("pygame.mixer.Sound") as mock_sound_class:
            mock_sound = Mock()
            mock_sound_class.return_value = mock_sound
            
            result = load_sound("test.wav", 0.5)
            
            # Verify the sound was created with correct path
            expected_path = Path(__file__).parent.parent.parent / "glitchygames" / "game_objects" / "snd_files" / "test.wav"
            mock_sound_class.assert_called_once_with(expected_path)
            
            # Verify volume was set
            mock_sound.set_volume.assert_called_once_with(0.5)
            
            # Verify return value
            assert result == mock_sound

    def test_load_sound_default_volume(self, mock_pygame_patches):
        """Test load_sound function with default volume."""
        with patch("pygame.mixer.Sound") as mock_sound_class:
            mock_sound = Mock()
            mock_sound_class.return_value = mock_sound
            
            result = load_sound("test.wav")
            
            # Verify default volume was used
            mock_sound.set_volume.assert_called_once_with(0.25)
            assert result == mock_sound

    def test_sfx_constants(self, mock_pygame_patches):
        """Test SFX constants."""
        assert SFX.BOUNCE == "sfx_bounce.wav"
        assert SFX.SLAP == "sfx_slap.wav"

    def test_load_sound_with_nonexistent_file(self, mock_pygame_patches):
        """Test load_sound with nonexistent file."""
        with patch("pygame.mixer.Sound") as mock_sound_class:
            mock_sound_class.side_effect = FileNotFoundError("File not found")
            
            with pytest.raises(FileNotFoundError):
                load_sound("nonexistent.wav")
