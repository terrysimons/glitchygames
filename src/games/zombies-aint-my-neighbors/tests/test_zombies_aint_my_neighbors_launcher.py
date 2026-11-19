"""The game starts on the title, or replays a recording from the scene it began on."""

from __future__ import annotations

from pathlib import Path

import pytest

from zombies_aint_my_neighbors import launcher
from zombies_aint_my_neighbors.neighborhood import NeighborhoodScene
from zombies_aint_my_neighbors.title import TitleScene

REPLAYS = Path(__file__).parent / 'fixtures' / 'replays'
TITLE_GOLDEN = REPLAYS / 'golden.jsonl.gz'
NEIGHBORHOOD_GOLDEN = REPLAYS / 'golden-neighborhood.jsonl.gz'


def test_a_plain_start_is_the_title():
    """With nothing to replay, the game starts on the title."""
    assert launcher.first_scene(arguments=['--windowed']) is TitleScene


def test_a_title_recording_replays_from_the_title():
    """The title golden began on the title."""
    assert launcher.first_scene(arguments=['--replay-trace', str(TITLE_GOLDEN)]) is TitleScene


def test_a_neighborhood_recording_replays_from_the_neighborhood():
    """The neighborhood golden began in the neighborhood (the engine refuses a mismatch)."""
    arguments = ['--replay-trace', str(NEIGHBORHOOD_GOLDEN), '--headless']

    assert launcher.first_scene(arguments=arguments) is NeighborhoodScene


@pytest.mark.parametrize('content', [None, b'not a recording'])
def test_an_unreadable_recording_starts_on_the_title(tmp_path, content):
    """A missing or broken file starts the title; the engine then refuses it, as for any game."""
    recording = tmp_path / 'broken.jsonl.gz'
    if content is not None:
        recording.write_bytes(content)

    assert launcher.first_scene(arguments=['--replay-trace', str(recording)]) is TitleScene


def test_main_starts_the_engine_on_the_first_scene(mocker):
    """``main`` hands the engine the scene ``first_scene`` chose."""
    engine = mocker.patch.object(launcher, 'GameEngine')
    mocker.patch.object(launcher.sys, 'argv', ['zombies-aint-my-neighbors'])

    launcher.main()

    engine.assert_called_once_with(game=TitleScene)
    engine.return_value.start.assert_called_once_with()
