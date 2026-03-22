"""Tests for game objects sound functionality.

This module tests sound loading, SFX constants, and sound-related functionality.
"""

import sys
from pathlib import Path

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.game_objects import load_sound
from glitchygames.game_objects.sounds import SFX
from tests.mocks.test_mock_factory import MockFactory


class TestGameObjectsSounds:
    """Test game objects sound functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_load_sound_function(self, mocker):
        """Test load_sound function."""
        mock_sound = mocker.Mock()
        mock_sound_class = mocker.patch(
            'glitchygames.game_objects.sounds.pygame.mixer.Sound',
            return_value=mock_sound,
        )

        result = load_sound('test.wav', 0.5)

        # Verify the sound was created with correct path
        expected_path = (
            Path(__file__).parent.parent.parent
            / 'glitchygames'
            / 'game_objects'
            / 'snd_files'
            / 'test.wav'
        )
        mock_sound_class.assert_called_once_with(expected_path)

        # Verify volume was set
        mock_sound.set_volume.assert_called_once_with(0.5)

        # Verify return value
        assert result == mock_sound

    def test_load_sound_default_volume(self, mocker):
        """Test load_sound function with default volume."""
        mock_sound = mocker.Mock()
        mocker.patch(
            'glitchygames.game_objects.sounds.pygame.mixer.Sound',
            return_value=mock_sound,
        )

        result = load_sound('test.wav')

        # Verify default volume was used
        mock_sound.set_volume.assert_called_once_with(0.25)
        assert result == mock_sound

    def test_sfx_constants(self):
        """Test SFX constants."""
        assert SFX.BOUNCE == 'sfx_bounce.wav'
        assert SFX.SLAP == 'sfx_slap.wav'

    def test_load_sound_with_nonexistent_file(self, mocker):
        """Test load_sound with nonexistent file."""
        mocker.patch(
            'glitchygames.game_objects.sounds.pygame.mixer.Sound',
            side_effect=FileNotFoundError('File not found'),
        )

        with pytest.raises(FileNotFoundError):
            load_sound('nonexistent.wav')
