"""A game's identity, from the game object alone (glitchygames/replay/tools/identity.py).

On stand-in games and distributions (tests/stand_in_games.py), never one of our members. Each
stand-in scene class is made here with the stand-in package as its ``__module__``, so this
process never imports the stand-in package (its metadata and directory are only looked up).
"""

from __future__ import annotations

import importlib.metadata
import sys
import types

import pytest

from glitchygames.replay.tools.identity import (
    GameIdentity,
    console_script_identity,
    game_identity,
)
from glitchygames.scenes import Scene
from tests.stand_in_games import (
    use_stand_in_game,
    write_stand_in_distribution,
    write_stand_in_game,
)


def scene_class_in(*, module: str) -> type[Scene]:
    """Return a scene class whose module is ``module`` (as if defined there).

    Returns:
        The class.

    """
    return types.new_class(
        'StandInScene', (Scene,), exec_body=lambda body: body.update({'__module__': module})
    )


def test_a_game_knows_its_package_and_console_script(tmp_path, monkeypatch):
    """The stand-in's package, its directory, its one console script and its distribution."""
    game = write_stand_in_game(directory=tmp_path, package='stand_in_rally')
    use_stand_in_game(install_directory=tmp_path, monkeypatch=monkeypatch)
    scene_class = scene_class_in(module='stand_in_rally.game')

    identity = game_identity(game=scene_class)

    assert identity == GameIdentity(
        package='stand_in_rally',
        package_directory=tmp_path / 'stand_in_rally',
        console_script=game.console_script,
    )
    assert identity.distribution == game.distribution
    # A scene object is identified by its class
    assert game_identity(game=object.__new__(scene_class)) == identity


def test_a_game_with_no_console_script_still_has_an_identity(tmp_path, monkeypatch):
    """A package no installed console script starts: its package and directory, no script."""
    package_directory = tmp_path / 'loose_game'
    package_directory.mkdir()
    (package_directory / '__init__.py').write_text('', encoding='utf-8')
    monkeypatch.syspath_prepend(tmp_path)

    identity = game_identity(game=scene_class_in(module='loose_game'))

    assert identity == GameIdentity(
        package='loose_game', package_directory=package_directory, console_script=None
    )
    assert identity.distribution is None


def test_a_game_in_a_single_module_has_that_modules_directory(tmp_path, monkeypatch):
    """A top-level module (``loose_game.py``, no package) lives in its file's directory."""
    (tmp_path / 'single_module_game.py').write_text('', encoding='utf-8')
    monkeypatch.syspath_prepend(tmp_path)

    identity = game_identity(game=scene_class_in(module='single_module_game'))

    assert identity.package == 'single_module_game'
    assert identity.package_directory == tmp_path


def test_a_distribution_that_lists_its_package_names_the_game(tmp_path, monkeypatch):
    """A distribution whose metadata lists the package is the game's, with no console script.

    The stand-in dist-info names its top-level package (``top_level.txt``) and has no console
    script, so the distribution comes from the package lookup alone.
    """
    write_stand_in_distribution(directory=tmp_path, distribution='listed-game', console_scripts={})
    (tmp_path / 'listed_game-1.0.0.dist-info' / 'top_level.txt').write_text(
        'listed_game\n', encoding='utf-8'
    )
    (tmp_path / 'listed_game').mkdir()
    (tmp_path / 'listed_game' / '__init__.py').write_text('', encoding='utf-8')
    monkeypatch.syspath_prepend(tmp_path)

    identity = game_identity(game=scene_class_in(module='listed_game.game'))

    assert identity.distribution == 'listed-game'
    assert identity.console_script is None


def test_a_package_two_console_scripts_start_names_no_console_script(tmp_path, monkeypatch):
    """When more than one console script starts the game's module, none is chosen."""
    game = write_stand_in_game(directory=tmp_path, package='twice_started')
    write_stand_in_distribution(
        directory=tmp_path,
        distribution='twice-started-again',
        console_scripts={'twice-started-again': 'twice_started:main'},
    )
    use_stand_in_game(install_directory=tmp_path, monkeypatch=monkeypatch)

    identity = game_identity(game=scene_class_in(module='twice_started'))

    assert identity.console_script is None
    assert identity.package_directory == tmp_path / game.package


def test_a_game_run_as_a_script_lives_in_the_scripts_directory(tmp_path, mocker):
    """``python mygame.py``: its module is ``__main__``, found by the script's file."""
    script_module = types.ModuleType('__main__')
    script_module.__file__ = str(tmp_path / 'mygame.py')
    mocker.patch.dict(sys.modules, {'__main__': script_module})

    identity = game_identity(game=scene_class_in(module='__main__'))

    assert identity == GameIdentity(
        package='__main__', package_directory=tmp_path, console_script=None
    )
    assert identity.distribution is None


def test_a_game_whose_module_cannot_be_found_has_no_directory(mocker):
    """A module that is neither importable nor loaded with a file (a class made at a prompt)."""
    fileless = types.ModuleType('made_at_a_prompt')
    mocker.patch.dict(sys.modules, {'made_at_a_prompt': fileless})

    identity = game_identity(game=scene_class_in(module='made_at_a_prompt'))
    nowhere = game_identity(game=scene_class_in(module='not_anywhere_at_all'))

    assert identity.package_directory is None
    assert nowhere == GameIdentity(
        package='not_anywhere_at_all', package_directory=None, console_script=None
    )
    assert nowhere.distribution is None


def test_a_console_scripts_game_is_known_without_importing_it(tmp_path, monkeypatch):
    """What the command knows of a game it names by console script: the same identity.

    Read from the console script's entry point and the package's spec (Task D6's ``unmeasured``
    command): the stand-in package is never imported here.
    """
    game = write_stand_in_game(directory=tmp_path, package='stand_in_rally')
    use_stand_in_game(install_directory=tmp_path, monkeypatch=monkeypatch)

    identity = console_script_identity(console_script=game.console_script)

    assert identity == game_identity(game=scene_class_in(module='stand_in_rally.game'))
    assert identity.distribution == game.distribution
    assert 'stand_in_rally' not in sys.modules
    with pytest.raises(KeyError):
        console_script_identity(console_script='glitchygames-no-such-game')


def test_the_distribution_is_looked_up_only_when_read_and_once(tmp_path, monkeypatch, mocker):
    """Making an identity scans no installed files; reading its distribution does, once.

    The scan (``importlib.metadata.packages_distributions``) reads every installed
    distribution's files, and no tool reads the distribution.
    """
    game = write_stand_in_game(directory=tmp_path, package='stand_in_rally')
    use_stand_in_game(install_directory=tmp_path, monkeypatch=monkeypatch)
    scan = mocker.spy(importlib.metadata, 'packages_distributions')

    identity = game_identity(game=scene_class_in(module='stand_in_rally.game'))
    scanned_on_making = scan.call_count
    first = identity.distribution
    second = identity.distribution

    assert scanned_on_making == 0
    assert scan.call_count == 1
    assert first == second == game.distribution
