"""Every game in the workspace plays the CRT power-on sequence through its own main().

Each member's console script (read from the workspace with scripts/workspace_packages.py) is
started through its real entry point, so this is a test of this repository's games, not of the
engine alone: moved here unchanged from tests/engine/test_engine_lifecycle.py (Part 3, Stage D,
Task D9 fix round 1), which tests the engine's lifecycle with its own scenes.
"""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pygame
import pytest
from scripts.workspace_packages import declared_console_scripts, workspace_members

from glitchygames.backgrounds import BackgroundPattern, paint_default_background
from glitchygames.crt_power_on import PowerOnOutcome
from glitchygames.engine import game_engine as game_engine_module
from glitchygames.replay.tools.children import game_entry_point
from glitchygames.replay.tools.golden_traces import GoldenTraceEngine, command_line
from tests import demo_runs
from tests.workspace_expectations import EXPECTED_ALL_CONSOLE_SCRIPTS

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytest_mock import MockerFixture


@pytest.fixture
def engine_run_environment(mocker: MockerFixture) -> Generator[None]:
    """Let the test start a real engine, leaving pygame usable for later tests.

    tests/demo_runs.py's ``engine_run_environment``, the same as
    tests/engine/test_engine_lifecycle.py's fixture of that name.

    Yields:
        None, while the environment is in place.

    """
    yield from demo_runs.engine_run_environment(mocker)


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Console scripts that are not games: the API server and client, and the engine's tools'
# command (glitchygames, which starts games but is none)
NOT_GAME_CONSOLE_SCRIPTS = frozenset({'glitchygames-server', 'glitchygames-client', 'glitchygames'})

# Every game's console script, read from the workspace (the root's and the members'
# [project.scripts]) less the root's API scripts: the power-on sequence must play before each
# (brave-adventurer's, Brave Adventurer's launcher, before its title screen: one sequence for
# both its games, as the engine plays it once, before the first scene)
GAME_CONSOLE_SCRIPTS = tuple(
    sorted(set(declared_console_scripts(project_root=PROJECT_ROOT)) - NOT_GAME_CONSOLE_SCRIPTS)
)


class PowerOnPlayed(BaseException):
    """Raised after the real power-on sequence played, to stop the run before the game is built.

    Not an Exception (start()'s crash boundary would turn it into INTERNAL_ERROR), and not a
    SystemExit (Bitmappy's main catches that), so it reaches the test unchanged.
    """


def test_every_game_console_script_is_covered():
    """The power-on test runs every workspace member's console script, and only those.

    Found independently of GAME_CONSOLE_SCRIPTS: each member's own ``console_scripts``
    (src/games/mr-muncher's pyproject.toml), so the parametrization cannot pass on zero.
    """
    members_console_scripts = {
        console_script
        for member in workspace_members(project_root=PROJECT_ROOT)
        for console_script in member.console_scripts
    }

    assert set(GAME_CONSOLE_SCRIPTS) == members_console_scripts
    # Written out by hand (tests/workspace_expectations.py): 5 games, 3 demos and Bitmappy
    assert set(GAME_CONSOLE_SCRIPTS) == EXPECTED_ALL_CONSOLE_SCRIPTS


@pytest.mark.usefixtures('engine_run_environment')
@pytest.mark.parametrize('background', [pattern.value for pattern in BackgroundPattern])
@pytest.mark.parametrize('console_script', GAME_CONSOLE_SCRIPTS)
def test_every_game_powers_on_through_its_own_main(mocker, console_script, background):
    """Each game's real main() plays the real sequence to its end on the game's canvas first.

    Once per screen it can settle on (--default-background): the colour bars and channel 3.

    The run is stopped once it has (PowerOnPlayed), before the game's scene is built.
    """
    main = game_entry_point(console_script=console_script).load()
    # The dummy driver cannot honour GameEngine's SCALED window (GoldenTraceEngine's docstring)
    mocker.patch.dict(main.__globals__, {'GameEngine': GoldenTraceEngine})
    # Bitmappy's main sets it process-wide; later tests on this worker keep their own
    mocker.patch('multiprocessing.set_start_method')
    mocker.patch(
        'glitchygames.clock.measured_seconds', side_effect=itertools.count(start=0.0, step=0.05)
    )
    played: list[tuple[PowerOnOutcome, bool]] = []
    real_player = game_engine_module.play_power_on

    def play_then_stop(**arguments: Any) -> PowerOnOutcome:
        # Its frames do not wait: it is given a sleep that returns at once (its default,
        # glitchygames/clock.py's raw_sleep, is bound when play_power_on is defined, so a patch
        # could not reach it)
        outcome = real_player(**arguments, sleep=lambda _seconds: None)
        settled = pygame.Surface(arguments['screen'].get_size())
        paint_default_background(surface=settled)
        shows_settled = pygame.image.tobytes(arguments['screen'], 'RGB') == pygame.image.tobytes(
            settled, 'RGB'
        )
        played.append((outcome, shows_settled))
        raise PowerOnPlayed

    mocker.patch.object(game_engine_module, 'play_power_on', side_effect=play_then_stop)

    with (
        command_line([
            '--crt-power-on',
            'on',
            '--default-background',
            background,
            '--log-level',
            'warning',
            '--resolution',
            '320x240',
        ]),
        pytest.raises(PowerOnPlayed),
    ):
        main()

    assert played == [(PowerOnOutcome.FINISHED, True)]
