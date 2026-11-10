"""A sprite removed from every group is freed: nothing in a run holds on to it.

The rule (the owner, 2026-11-06): what a game keeps is the game's choice, and the engine doesn't
keep a game's objects alive just for having seen them. Each golden replays in a child under
``tests/replay/removed_sprites_watch.py``.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pygame
import pytest

from glitchygames.process import OutputCapture, run_command
from glitchygames.replay.tools.children import recording_console_script
from tests.replay.removed_sprites_watch import RemovedSpriteWatch
from tests.workspace_goldens import every_games_golden

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CHILD_TIMEOUT_SECONDS = 300.0
# Draws its stick figures without sprites, so a replay of it samples none
GAMES_WITHOUT_SPRITES = frozenset({'drawing-fire'})
GOLDENS = every_games_golden(project_root=PROJECT_ROOT)


@pytest.mark.parametrize('golden', GOLDENS, ids=lambda path: f'{path.parents[3].name}-{path.stem}')
def test_replaying_a_game_holds_no_removed_sprite(golden):
    """Its removed sprites are gone at every check, or the report names what holds them."""
    console_script = recording_console_script(path=golden)

    finished = run_command(
        command=[
            sys.executable,
            '-m',
            'tests.replay.removed_sprites_watch',
            console_script,
            str(golden),
        ],
        environment={**os.environ, 'SDL_VIDEODRIVER': 'dummy', 'SDL_AUDIODRIVER': 'dummy'},
        timeout_seconds=CHILD_TIMEOUT_SECONDS,
        capture_output=OutputCapture.APART,
        working_directory=PROJECT_ROOT,
    )

    assert finished.returncode == 0, finished.stderr[-2000:]
    report = json.loads(finished.stdout.splitlines()[-1])
    assert report['most_held'] == {}, report['holders']
    if console_script in GAMES_WITHOUT_SPRITES:
        assert report['sprites_seen'] == 0
    else:
        # A watch that saw nothing, or a golden too short to reach a check, would pass on nothing
        assert report['sprites_seen'] > 0
        assert report['checks'] > 0


class Plain(pygame.sprite.DirtySprite):
    """A sprite with nothing else to it."""


def test_the_watch_finds_a_removed_sprite_something_holds():
    """Otherwise the test above could never fail: it names the class and the holder."""
    watch = RemovedSpriteWatch()
    group = pygame.sprite.LayeredDirty()
    sprite = Plain(group)
    watch.see(sprite)

    watch.check()
    assert watch.report()['most_held'] == {}

    group.remove(sprite)
    keeper = [sprite]
    watch.check()

    report = watch.report()
    assert keeper
    assert report['most_held'] == {'Plain': 1}
    assert report['checks'] == 2
    assert any(holder.startswith('Plain held by') for holder in report['holders'])


def test_the_watch_says_nothing_of_a_removed_sprite_that_was_freed():
    """Removed, let go, and so gone."""
    watch = RemovedSpriteWatch()
    group = pygame.sprite.LayeredDirty()
    sprite = Plain(group)
    watch.see(sprite)
    watch.see(sprite)

    group.remove(sprite)
    del sprite
    watch.check()

    assert watch.report() == {'sprites_seen': 1, 'checks': 1, 'most_held': {}, 'holders': {}}
