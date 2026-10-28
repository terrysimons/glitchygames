"""The engine's own resources: the sounds it ships as package data."""

import importlib.resources

import pytest

ENGINE_SOUND_NAMES = (
    'sfx_menu_move1.wav',
    'sfx_sounds_impact5.wav',
    'sfx_sounds_impact8.wav',
    'slap8.wav',
)


@pytest.mark.parametrize('sound_name', ENGINE_SOUND_NAMES)
def test_each_engine_sound_is_package_data_holding_a_wave_file(sound_name):
    """Each WAV is read through importlib.resources, wherever the engine is installed."""
    sound = importlib.resources.files('glitchygames') / 'resources' / 'sounds' / sound_name

    assert sound.is_file()
    assert sound.read_bytes().startswith(b'RIFF')
