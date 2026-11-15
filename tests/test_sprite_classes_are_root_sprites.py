"""Every sprite class in the engine and the members is a RootSprite, so it has the input handlers.

The engine's dispatchers call mouse and keyboard handlers on the sprites in a scene (the mouse
manager's focus and motion, the scene's clicks). A RootSprite has every one (silent by default);
a class built straight on pygame's sprites has none, and the pointer over one ended the game
(2026-11-15: ``AnimatedSprite``, so every game's animated sprite; BUGS.md #225 met the same
error in a test). The dispatchers now skip a handler a sprite lacks, but a sprite without them
also misses every event meant for it, so new sprite classes start from RootSprite. Scans every
workspace member's source (tests/workspace_sources.py), so this is a test of the repository.
"""

from __future__ import annotations

import ast
from types import MappingProxyType
from typing import Final

from tests.ast_scanning import PROJECT_ROOT
from tests.workspace_sources import scanned_source_files

# A class base naming one of pygame's sprite classes, as the code spells it
PYGAME_SPRITE_BASES: Final = frozenset({
    'pygame.sprite.Sprite',
    'pygame.sprite.DirtySprite',
    'DirtySprite',
})
# Allowed to stand on pygame's sprites, each with its reason (keyed by scan key and class)
ALLOWED_PYGAME_SPRITE_CLASSES: Final = MappingProxyType({
    ('sprites/root_sprite.py', 'RootSprite'): 'the root every other sprite stands on',
    ('replay/ghosts.py', 'GhostSprite'): (
        'a translucent replay of a recorded run, drawn only: it takes no input, and the '
        'dispatchers skip the handlers it lacks'
    ),
})


def classes_on_pygame_sprites() -> set[tuple[str, str]]:
    """Return every class whose bases name one of pygame's sprite classes, by scan key and name.

    Returns:
        The classes.

    """
    found: set[tuple[str, str]] = set()
    for scan_key, path in scanned_source_files(project_root=PROJECT_ROOT):
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                ast.unparse(base) in PYGAME_SPRITE_BASES for base in node.bases
            ):
                found.add((scan_key, node.name))
    return found


def test_no_sprite_class_stands_on_pygames_sprites_but_the_allowed():
    """A new class on pygame's sprites fails here: start it from RootSprite (or a subclass)."""
    assert classes_on_pygame_sprites() == set(ALLOWED_PYGAME_SPRITE_CLASSES)
