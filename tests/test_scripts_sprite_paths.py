"""The animation demo scripts load a sprite that exists (BUGS.md #245)."""

import importlib

import pytest

ANIMATION_DEMO_SCRIPTS = (
    'scripts.animation_demo',
    'scripts.animation_scene_demo',
    'scripts.animation_scene_full_demo',
)


@pytest.mark.parametrize('module_name', ANIMATION_DEMO_SCRIPTS)
def test_animation_demo_sprite_path_exists(module_name):
    """Each demo's sprite path names a real file, not one in the repository root."""
    script = importlib.import_module(module_name)

    assert script.FOO_TOML_PATH.is_file(), script.FOO_TOML_PATH
