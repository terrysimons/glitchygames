"""Basic test coverage for Game Objects module - focusing on non-pygame dependent functionality."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.game_objects import load_sound
from glitchygames.game_objects.sounds import SFX


class TestGameObjectsBasicCoverage(unittest.TestCase):
    """Test coverage for game_objects basic functionality."""

    def test_load_sound_function(self):
        """Test load_sound function."""
        with patch("pygame.mixer.Sound") as mock_sound:
            result = load_sound("test.wav")
            # The function converts the filename to a full path
            expected_path = Path(__file__).parent.parent / "glitchygames" / "game_objects" / "snd_files" / "test.wav"
            mock_sound.assert_called_once_with(expected_path)
            self.assertEqual(result, mock_sound.return_value)

    def test_load_sound_default_volume(self):
        """Test load_sound function with default volume."""
        with patch("pygame.mixer.Sound") as mock_sound:
            mock_sound_instance = Mock()
            mock_sound.return_value = mock_sound_instance
            
            result = load_sound("test.wav")
            
            # The function converts the filename to a full path
            expected_path = Path(__file__).parent.parent / "glitchygames" / "game_objects" / "snd_files" / "test.wav"
            mock_sound.assert_called_once_with(expected_path)
            mock_sound_instance.set_volume.assert_called_once_with(0.25)  # Default volume is 0.25, not 0.5
            self.assertEqual(result, mock_sound_instance)

    def test_sfx_constants(self):
        """Test SFX constants."""
        self.assertEqual(SFX.BOUNCE, "sfx_bounce.wav")
        self.assertEqual(SFX.SLAP, "sfx_slap.wav")


if __name__ == "__main__":
    unittest.main()
