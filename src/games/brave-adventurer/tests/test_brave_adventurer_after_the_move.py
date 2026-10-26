"""Brave Adventurer and Papyrus moved from glitchygames/examples into one project.

Their recordings did not change: each scene keeps its logical name, both goldens keep their
history, and the primitives both games share (brave_adventurer_core) import neither game. Both
scenes are built on one base there (BraveAdventurerSceneBase), each game giving only what differs.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
from pathlib import Path

import pygame
import pytest

import brave_adventurer.game
import brave_adventurer_core
import brave_adventurer_papyrus.game
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
from glitchygames.logical_names import logical_name
from glitchygames.recording_metrics import RECORDING_PATH_RENAMES
from glitchygames.scenes import Scene
from glitchygames.testing.replays import recording_console_script

PROJECT_ROOT = Path(__file__).resolve().parents[4]
MEMBER_DIRECTORY = Path(__file__).resolve().parents[1]
REPLAY_FIXTURES_DIRECTORY = MEMBER_DIRECTORY / 'tests' / 'fixtures' / 'replays'
# Each game's golden replay: where it was in the engine's tests (named after the console script
# that replayed it then), where it is now, and the console script that replays it now: the
# launcher, for both
GOLDENS = [
    (
        'tests/fixtures/replays/brave-adventurer/golden.jsonl.gz',
        'golden-classic.jsonl.gz',
        'brave-adventurer',
    ),
    (
        'tests/fixtures/replays/brave-adventurer-papyrus/golden.jsonl.gz',
        'golden-papyrus.jsonl.gz',
        'brave-adventurer',
    ),
]
# The two games, which the shared primitives must never import
GAME_PACKAGES = frozenset({'brave_adventurer', 'brave_adventurer_papyrus'})
# What both scenes play by, defined once on BraveAdventurerSceneBase and by neither game
SHARED_SCENE_METHODS = (
    'args',
    'setup',
    'dt_tick',
    '_resolve_player_ground_collision',
    '_resolve_player_wall_collision',
    '_player_support_span',
    '_entered_wall_from_left',
    '_resolve_enemy_terrain_collisions',
    '_on_player_enemy_collision',
    '_on_player_collect',
    '_player_die',
    '_save_high_score',
    '_respawn_player',
    '_process_movement_input',
    'on_key_down_event',
    'on_controller_button_down_event',
    'on_joy_button_down_event',
    'render',
    '_draw_pits',
    '_draw_hud',
)


def scene_classes(module):
    """Return the scene classes a game module defines (not those it imports).

    Returns:
        The classes.

    """
    return [
        scene_class
        for _name, scene_class in inspect.getmembers(module, inspect.isclass)
        if issubclass(scene_class, Scene) and scene_class.__module__ == module.__name__
    ]


@pytest.mark.parametrize('game_module', [brave_adventurer.game, brave_adventurer_papyrus.game])
def test_both_games_keep_their_logical_names(game_module):
    """Recordings name games.<package>.game:<scene>, as before the move."""
    package = game_module.__name__.partition('.')[0]
    scenes = scene_classes(game_module)

    assert scenes, f'{game_module.__name__} defines its scenes'
    for scene_class in scenes:
        assert logical_name(scene_class=scene_class) == (
            f'games.{package}.game:{scene_class.__qualname__}'
        )


def test_the_scene_classes_kept_their_names():
    """Each scene class stays in its game's game.py under its old name."""
    assert brave_adventurer.game.BraveAdventurerScene.__module__ == 'brave_adventurer.game'
    assert brave_adventurer_papyrus.game.PapyrusBraveAdventurerScene.__module__ == (
        'brave_adventurer_papyrus.game'
    )


@pytest.mark.parametrize(
    'old_package',
    ['glitchygames.examples.brave_adventurer', 'glitchygames.examples.brave_adventurer_papyrus'],
)
def test_the_old_example_packages_are_gone(old_package):
    """Nothing is left in glitchygames/examples to import (a stale __pycache__ would be)."""
    assert importlib.util.find_spec(old_package) is None
    old_directory = PROJECT_ROOT.joinpath('src', *old_package.split('.'))
    assert not old_directory.exists()


@pytest.mark.parametrize(('old_path', 'new_name', 'console_script'), GOLDENS)
def test_both_goldens_keep_their_history(old_path, new_name, console_script):
    """Each golden moved (its ledger rows follow it) and still replays through its own game."""
    new_path = REPLAY_FIXTURES_DIRECTORY / new_name

    assert new_path.is_file()
    assert not (PROJECT_ROOT / old_path).exists()
    assert RECORDING_PATH_RENAMES[old_path] == new_path.relative_to(PROJECT_ROOT).as_posix()
    assert recording_console_script(path=new_path) == console_script


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
    repeated = [name for name in SHARED_SCENE_METHODS if name in vars(scene_class)]
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
