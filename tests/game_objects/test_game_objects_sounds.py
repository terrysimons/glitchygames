"""Tests for game objects sound functionality.

This module tests sound loading, SFX constants, and sound-related functionality.
"""

import pygame
import pytest

from glitchygames.game_objects import load_sound
from glitchygames.game_objects.sounds import SFX
from tests.harness import imported_engine_directory

# The imported engine's directory (installed: never the source tree by accident)
ENGINE_PACKAGE_DIRECTORY = imported_engine_directory()

# The mixer stores volume in 1/128 steps, so a volume reads back to within one step
MIXER_VOLUME_STEP = 1 / 128


class TestGameObjectsSounds:
    """Test game objects sound functionality on the real mixer."""

    @pytest.mark.parametrize('sound_name', [SFX.BOUNCE, SFX.SLAP])
    def test_load_sound_function(self, sound_name):
        """load_sound loads the bundled file as a real Sound at the given volume."""
        result = load_sound(sound_name, 0.5)

        assert isinstance(result, pygame.mixer.Sound)
        assert result.get_length() > 0
        assert result.get_volume() == pytest.approx(0.5, abs=MIXER_VOLUME_STEP)

    def test_load_sound_reads_the_bundled_file(self):
        """The Sound holds the bundled file's samples: loading it directly gives the same bytes."""
        bundled_path = ENGINE_PACKAGE_DIRECTORY / 'game_objects' / 'snd_files' / SFX.BOUNCE

        result = load_sound(SFX.BOUNCE)

        assert result.get_raw() == pygame.mixer.Sound(bundled_path).get_raw()

    def test_load_sound_default_volume(self):
        """Test load_sound function with default volume."""
        result = load_sound(SFX.BOUNCE)

        assert result.get_volume() == pytest.approx(0.25, abs=MIXER_VOLUME_STEP)

    def test_sfx_constants(self):
        """Test SFX constants."""
        assert SFX.BOUNCE == 'sfx_bounce.wav'
        assert SFX.SLAP == 'sfx_slap.wav'

    def test_load_sound_with_nonexistent_file(self):
        """A missing sound file raises FileNotFoundError from the real mixer."""
        with pytest.raises(FileNotFoundError, match=r'nonexistent\.wav'):
            load_sound('nonexistent.wav')
