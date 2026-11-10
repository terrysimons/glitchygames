"""The animation demo scripts load an animated sprite that exists (BUGS.md #245, #244)."""

import importlib
import tomllib

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

    assert script.SPRITE_PATH.is_file(), script.SPRITE_PATH


@pytest.mark.parametrize('module_name', ANIMATION_DEMO_SCRIPTS)
def test_animation_demo_sprite_is_animated_and_has_a_palette(module_name):
    """Each demo's sprite has animations and colors, so it draws (foo.toml had neither)."""
    script = importlib.import_module(module_name)

    sprite = tomllib.loads(script.SPRITE_PATH.read_text(encoding='utf-8'))

    assert sprite.get('animation'), script.SPRITE_PATH
    assert sprite.get('colors'), script.SPRITE_PATH
