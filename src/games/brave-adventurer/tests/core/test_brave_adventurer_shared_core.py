"""The primitives both games share (brave_adventurer_core) import neither game.

Both scenes are built on one base there (BraveAdventurerSceneBase), each game giving only what
differs, and the shared level manager builds each game's own collectible through its hook.
"""

from __future__ import annotations

import ast
import types
from pathlib import Path

import pygame
import pytest

import brave_adventurer_core
from brave_adventurer.constants import PLAYER_HEIGHT
from brave_adventurer.enemies import Scarab
from brave_adventurer.game import BraveAdventurerScene
from brave_adventurer.levels import ClassicLevelManager
from brave_adventurer.terrain import GoldScarab
from brave_adventurer_core.constants import GROUND_Y
from brave_adventurer_core.levels import LEVEL_1, LevelManager
from brave_adventurer_core.scene import BraveAdventurerSceneBase
from brave_adventurer_papyrus.constants import PAPYRUS_PLAYER_HEIGHT
from brave_adventurer_papyrus.enemies import PapyrusScarab
from brave_adventurer_papyrus.game import PapyrusBraveAdventurerScene
from brave_adventurer_papyrus.levels import PapyrusLevelManager
from brave_adventurer_papyrus.terrain import PapyrusGoldScarab
from glitchygames.display_mode import set_display_mode

# The two games, which the shared primitives must never import
GAME_PACKAGES = frozenset({'brave_adventurer', 'brave_adventurer_papyrus'})
# The base's hooks: what a game may give its own (every other method of the base is shared and
# no game redefines it). Classic extends __init__ (its voice assistant) and _create_action_map
# (its mic button); the rest are the foot line, the scarab and the voice assistant
SCENE_HOOKS = frozenset({
    '__init__',
    '_create_action_map',
    '_scarab_class',
    '_player_top_and_foot_line',
    '_player_world_y_standing_on',
    '_update_voice_assistant',
    '_on_voice_button_down',
    '_on_voice_button_up',
})


def imported_modules(*, path: Path) -> set[str]:
    """Return every module a source file imports, at any depth (functions included).

    Returns:
        The imported modules' names (``from x import y`` gives ``x``).

    """
    tree = ast.parse(path.read_text(encoding='utf-8'))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


@pytest.mark.parametrize('scene_class', [BraveAdventurerScene, PapyrusBraveAdventurerScene])
def test_both_scenes_share_one_base(scene_class):
    """Each game's scene is the shared base plus its hooks: neither repeats the shared code."""
    assert issubclass(scene_class, BraveAdventurerSceneBase)
    assert BraveAdventurerSceneBase.__module__ == 'brave_adventurer_core.scene'
    base_methods = {
        name
        for name, member in vars(BraveAdventurerSceneBase).items()
        if isinstance(member, (types.FunctionType, staticmethod, classmethod))
    }
    # The guard follows the base: a hook renamed or removed there must be renamed here too
    assert base_methods >= SCENE_HOOKS
    shared_methods = base_methods - SCENE_HOOKS
    assert {'dt_tick', 'render', 'on_joy_button_up_event', '_pause_game'} <= shared_methods
    repeated = sorted(name for name in shared_methods if name in vars(scene_class))
    assert not repeated, f'{scene_class.__name__} repeats {repeated}'


@pytest.mark.parametrize(
    ('scene_class', 'save_name', 'player_start_world_y', 'scarab_class', 'standing_type'),
    [
        (BraveAdventurerScene, 'brave-adventurer', GROUND_Y - PLAYER_HEIGHT, Scarab, float),
        (
            PapyrusBraveAdventurerScene,
            'brave-adventurer-papyrus',
            GROUND_Y - PAPYRUS_PLAYER_HEIGHT,
            PapyrusScarab,
            int,
        ),
    ],
    ids=['classic', 'papyrus'],
)
def test_each_scene_gives_its_own_hooks(
    scene_class, save_name, player_start_world_y, scarab_class, standing_type
):
    """What differs between the games: each keeps its save, start, scarab and foot line type."""
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=(800, 480))

    scene = scene_class(options={'input_mode': 'joystick'})

    # The save namespace is players' saved high scores: each game keeps its own
    assert scene.saves.app_name == save_name
    assert scene.player.world_y == player_start_world_y
    assert scene._scarab_class() is scarab_class
    # Classic stands the player from its hitbox (a float world_y), Papyrus from a fixed height
    # (an int): each keeps the type its recordings were made with
    assert type(scene._player_world_y_standing_on(GROUND_Y)) is standing_type


def test_the_core_imports_neither_game():
    """brave_adventurer_core is below both games: no module of it imports either."""
    core_directory = Path(brave_adventurer_core.__file__).parent
    core_modules = sorted(core_directory.rglob('*.py'))

    assert core_modules
    for path in core_modules:
        game_imports = {
            module
            for module in imported_modules(path=path)
            if module.partition('.')[0] in GAME_PACKAGES
        }
        assert not game_imports, f'{path.name} imports {sorted(game_imports)}'


@pytest.mark.parametrize(
    ('manager_class', 'collectible_class'),
    [(ClassicLevelManager, GoldScarab), (PapyrusLevelManager, PapyrusGoldScarab)],
    ids=['ClassicLevelManager', 'PapyrusLevelManager'],
)
def test_each_level_manager_builds_its_own_gold_scarab(manager_class, collectible_class):
    """The shared LevelManager builds each game's collectible through its hook."""
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=(800, 480))

    manager = manager_class(level_data=LEVEL_1, groups=pygame.sprite.LayeredDirty())

    assert manager.collectible_sprites
    assert {type(collectible) for collectible in manager.collectible_sprites} == {collectible_class}
    # One _build, the shared one: Papyrus's copy is gone
    assert issubclass(manager_class, LevelManager)
    assert '_build' not in vars(manager_class)


def test_the_shared_level_manager_needs_a_game():
    """The core knows no game's sprites: only a game's level manager can be built."""
    with pytest.raises(TypeError, match='abstract'):
        LevelManager(level_data=LEVEL_1, groups=pygame.sprite.LayeredDirty())  # type: ignore[abstract]
