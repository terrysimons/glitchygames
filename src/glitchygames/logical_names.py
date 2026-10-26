"""Logical names: how a recording names a game or scene class, unchanged when its code moves.

A logical name is ``<layer>.<module path inside its package>:<qualified name>``
(``games.mr_muncher.game:MrMuncherScene``). The layer (``games``, ``demos``, ``apps``) is the
workspace layer the class's package belongs to (``src/<layer>/<member>/``,
plans/2026-10-24-workspace-packages.md); the module path starts with the package's name, wherever
the package is installed. A module that belongs to no layer (the engine's own, a test's, a
third-party game's, ``__main__``) keeps its module path.

The layers are data here, not read from the workspace: an installed engine has no workspace to
read, and the engine never imports scripts/. ``MEMBER_LAYERS`` is kept equal to the workspace
(scripts/workspace_packages.py) by tests/test_workspace_config.py; ``EXAMPLES_LAYERS`` covers
the games and demos still inside glitchygames/examples/ and goes when that directory does.
A leaf module: it imports nothing from the engine.
"""

from __future__ import annotations

LAYERS: tuple[str, ...] = ('games', 'demos', 'apps')
EXAMPLES_PACKAGE = 'glitchygames.examples'
# Games and demos not yet moved out of glitchygames/examples/: package name there -> layer
# (the user, 2026-10-25; Part 2 of the workspace plan deletes it)
EXAMPLES_LAYERS: dict[str, str] = {
    'paddleslap': 'games',
    'drawing_fire': 'games',
    'dt_demo': 'demos',
    'joystick_demo': 'demos',
    'text_input_demo': 'demos',
}
# Workspace members: top-level import package -> layer (src/<layer>/<member>/); equal to the
# workspace, checked by tests/test_workspace_config.py
MEMBER_LAYERS: dict[str, str] = {
    'mr_muncher': 'games',
    'brave_adventurer_core': 'games',
    'brave_adventurer': 'games',
    'brave_adventurer_papyrus': 'games',
    'brave_adventurer_modes': 'games',
    'clockwork_keep': 'games',
}


def logical_module_name(*, module: str) -> str:
    """Return a module's logical name: its layer and its path inside its package.

    Args:
        module: A module's import path (``glitchygames.examples.paddleslap``, ``mr_muncher.game``).

    Returns:
        ``<layer>.<path from the package>`` (``games.paddleslap``), or the module itself when it
        belongs to no layer.

    """
    examples_prefix = f'{EXAMPLES_PACKAGE}.'
    if module.startswith(examples_prefix):
        inside_examples = module.removeprefix(examples_prefix)
        layer = EXAMPLES_LAYERS.get(inside_examples.partition('.')[0])
        return module if layer is None else f'{layer}.{inside_examples}'
    layer = MEMBER_LAYERS.get(module.partition('.')[0])
    return module if layer is None else f'{layer}.{module}'


def logical_name(*, scene_class: type) -> str:
    """Return a class's logical name, as recordings name games and scenes.

    Args:
        scene_class: The class (a game or scene class).

    Returns:
        ``<logical module>:<qualified name>`` (``games.paddleslap:Game``).

    """
    return f'{logical_module_name(module=scene_class.__module__)}:{scene_class.__qualname__}'


def module_for_logical_module(*, logical_module: str) -> str:
    """Return the module that holds a logical module today (the inverse of ``logical_module_name``).

    Args:
        logical_module: A logical module (``games.paddleslap``).

    Returns:
        The import path (``glitchygames.examples.paddleslap``, ``mr_muncher.game``), or the name
        itself when its first part is not a layer.

    """
    layer, _, inside_package = logical_module.partition('.')
    if layer not in LAYERS or not inside_package:
        return logical_module
    package = inside_package.partition('.')[0]
    if MEMBER_LAYERS.get(package) == layer:
        return inside_package
    if EXAMPLES_LAYERS.get(package) == layer:
        return f'{EXAMPLES_PACKAGE}.{inside_package}'
    return logical_module
