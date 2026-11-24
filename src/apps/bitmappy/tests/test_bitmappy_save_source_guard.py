"""No Bitmappy module writes a file in place: every save of a person's work is whole or nothing.

A sprite or settings file written in place (``Path.write_text``, or ``open`` for writing) and
stopped part way (Ctrl-C, a crash, a kill) is left truncated, and the earlier version is gone
with it (bugs/2026-11-21-sprite-saves-are-not-atomic.md). So Bitmappy saves through
``glitchygames.output_files.write_text_whole``, and opens a file for writing only where
ALLOWED_WRITERS says, each for the reason given and as many times as given. Every module of the
package is scanned, so a new one is held to the rule too.

The scan names the top-level class or function a write is in, not the method, so an allowance
covers a whole class: its count keeps a second writer in that class from passing unseen.

The engine's sprite modules have the same guard
(``tests/sprites/test_sprite_save_source_guard.py``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import bitmappy
from tests.ast_scanning import writing_calls

PACKAGE = Path(bitmappy.__file__).parent
BITMAPPY_MODULES = sorted(path.relative_to(PACKAGE).as_posix() for path in PACKAGE.rglob('*.py'))

# (module, top-level class or function) -> (how many writing calls it may hold, why)
ALLOWED_WRITERS = {
    ('ai_manager.py', 'AIManager'): (
        1,
        (
            'writes the current frame to a temporary TOML file for the AI request, a file the '
            'person never keeps (_save_current_frame_to_temp_toml)'
        ),
    ),
}


def unexpected_writes(*, module: str, source: str) -> list[str]:
    """Return each writing call in a module beyond what ALLOWED_WRITERS lets it hold.

    Returns:
        ``module:line in owner`` for each writing call of an owner with no allowance, or for
        every writing call of an owner holding more than its allowance.

    """
    calls = writing_calls(source=source)
    unexpected = []
    for owner in sorted({owner for owner, _line in calls}):
        lines = [line for name, line in calls if name == owner]
        allowed_count, _reason = ALLOWED_WRITERS.get((module, owner), (0, ''))
        if len(lines) > allowed_count:
            unexpected.extend(f'{module}:{line} in {owner}' for line in lines)
    return unexpected


def test_the_bitmappy_modules_are_found():
    """An empty scan would pass for any code: the package's saving modules are all there."""
    assert {'file_io.py', 'ai_manager.py', 'controllers/error_handling.py'} <= set(BITMAPPY_MODULES)


@pytest.mark.parametrize('module', BITMAPPY_MODULES)
def test_no_bitmappy_module_writes_a_file_in_place(module):
    """A Bitmappy module saves only through output_files.write_text_whole."""
    source = (PACKAGE / module).read_text(encoding='utf-8')

    assert unexpected_writes(module=module, source=source) == [], (
        'Save through glitchygames.output_files.write_text_whole '
        '(or list a one-off write in ALLOWED_WRITERS with its count and reason)'
    )


@pytest.mark.parametrize(('module', 'owner'), sorted(ALLOWED_WRITERS))
def test_every_allowed_writer_still_writes_as_many_times(module, owner):
    """A stale allowance would let a new writer of that name through unseen."""
    source = (PACKAGE / module).read_text(encoding='utf-8')
    allowed_count, _reason = ALLOWED_WRITERS[module, owner]

    calls = [line for name, line in writing_calls(source=source) if name == owner]

    assert len(calls) == allowed_count


@pytest.mark.parametrize(
    ('module', 'source', 'expected'),
    [
        (
            'file_io.py',
            (
                'class FileIOManager:\n'
                '    def save(self, path, text):\n'
                "        path.write_text(text, encoding='utf-8')\n"
            ),
            ['file_io.py:3 in FileIOManager'],
        ),
        (
            'ai_manager.py',
            (
                'class AIManager:\n'
                '    def temporary(self, path):\n'
                "        path.write_text('x')\n"
                '    def save(self, path):\n'
                "        path.open('w')\n"
            ),
            ['ai_manager.py:3 in AIManager', 'ai_manager.py:5 in AIManager'],
        ),
        (
            'ai_manager.py',
            "class AIManager:\n    def temporary(self, path):\n        path.write_text('x')\n",
            [],
        ),
    ],
    ids=['unallowed-save', 'second-writer-in-an-allowed-class', 'the-allowed-write'],
)
def test_a_planted_in_place_save_is_found(module, source, expected):
    """The guard can fail: a save put back in place, or a second writer in AIManager."""
    assert unexpected_writes(module=module, source=source) == expected
