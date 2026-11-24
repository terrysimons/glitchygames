"""No sprite module writes a file in place: every sprite save is whole or nothing.

A sprite file written in place (``Path.write_text``, or ``open`` for writing) and stopped part
way (Ctrl-C, a crash, a kill) is left truncated, and the earlier version is gone with it
(bugs/2026-11-21-sprite-saves-are-not-atomic.md). So no module of ``glitchygames.sprites``
opens a file for writing: each save goes through ``glitchygames.output_files.write_text_whole``,
which writes a partial copy, syncs it, then replaces the file. Every module is scanned, so a
new one is held to the rule too.

Bitmappy's own modules have the same guard (``src/apps/bitmappy/tests``).
"""

from __future__ import annotations

import pytest

from tests.ast_scanning import PROJECT_ROOT, writing_calls
from tests.engine_source import ENGINE_DIRECTORY

SPRITES_PACKAGE = PROJECT_ROOT / ENGINE_DIRECTORY / 'sprites'
SPRITE_MODULES = sorted(path.name for path in SPRITES_PACKAGE.glob('*.py'))


def in_place_writes(*, module: str, source: str) -> list[str]:
    """Return each call in a sprite module's source that writes a file in place.

    Returns:
        ``module:line in owner`` for each writing call.

    """
    return [f'{module}:{line} in {owner}' for owner, line in writing_calls(source=source)]


def test_the_sprite_modules_are_found():
    """An empty scan would pass for any code: the package's modules are all there."""
    assert {'animated.py', 'bitmappy_sprite.py', 'catalog.py', 'saved_sprites.py'} <= set(
        SPRITE_MODULES
    )


@pytest.mark.parametrize('module', SPRITE_MODULES)
def test_no_sprite_module_writes_a_file_in_place(module):
    """A sprite module saves only through output_files.write_text_whole."""
    source = (SPRITES_PACKAGE / module).read_text(encoding='utf-8')

    assert in_place_writes(module=module, source=source) == [], (
        'Save sprite files through glitchygames.output_files.write_text_whole '
        '(bugs/2026-11-21-sprite-saves-are-not-atomic.md)'
    )


def test_a_planted_in_place_save_is_found():
    """The guard can fail: the save this branch replaced, put back, is reported."""
    planted = (
        'class AnimatedSprite:\n'
        '    def save(self, filename):\n'
        "        Path(filename).write_text(self.to_text(), encoding='utf-8')\n"
    )

    assert in_place_writes(module='animated.py', source=planted) == [
        'animated.py:3 in AnimatedSprite'
    ]
