"""What demo players cost an Arcade: ten a frame, a restart's build, the posters' fast-forward.

Arcade sub-plan 5 (plans/2026-11-20-arcade-5-playback-core.md, Task 6): the measurements its
decisions 3, 7 and 8 rest on, taken with the real bundled demos (``DemoPlayer``,
glitchygames/demo_player.py), not stand-ins. Ten of the eleven bundled demos are the ten tiles
(``TEN_DEMOS``: the text-input demo is left out, as a first Arcade screen may leave it out, since
it changes SDL's key repeat for the whole process: plans/future-work.md):

- **a restart's build** (``test_a_restarts_build``, one case per bundled demo, all eleven): what
  a loop's ``InnerGame.replay`` costs, the one indivisible call decision 7 charges to the shared
  budget. ``BUILD_ROUNDS`` builds a case, each finished untimed before the next: the first is
  cold for the test (the harness empties the process-wide sound and sprite caches before each
  test, and the sound cache has no disk layer in tests), the others warm. pytest-benchmark's
  maximum is then the cold build and its minimum the warm one; the rounds are printed too.
- **ten players per Arcade frame** (``test_ten_demo_players_per_arcade_frame``): one round is one
  Arcade frame: a ``TickBudget`` of ``INNER_FRAME_BUDGET_SECONDS`` on the real clock, handed to
  the ten players in turn, each paid one Arcade frame (``ARCADE_TICK_SECONDS``).
  ``ARCADE_TIMED_FRAMES`` rounds are timed, so the shorter demos loop while timed and their
  builds land in the maximum. Printed: how many rounds spent the budget, and each player's
  frames, loops and effective speed (below 1.0 means it could not keep up here).
- **the ten posters' fast-forward** (``test_ten_posters_fast_forward``): each player
  fast-forwards to a poster frame from a seeded stream (``poster_frame``), every Arcade frame
  sharing one ``INNER_FRAME_BUDGET_SECONDS`` budget among the ten, until all ten stand at their
  posters. Timed in total; printed: how many Arcade frames it took.

The numbers are this machine's and the dummy drivers'. The engine context page's "Performance"
section (docs/architecture/engine_context.md) records them, and its table's ten-player row must
stay within ``INNER_FRAME_BUDGET_SECONDS``
(``test_the_documented_ten_player_frame_fits_the_budget``, in the normal suite); a Raspberry Pi's
are not measured.

A repository test (tests/test_suite_collection.py ``REPOSITORY_TEST_FILES``): it replays our
members' bundled demos through their console scripts. Not in the test run: it builds every
bundled demo five times and plays ten for twenty seconds, so it runs only under
``--benchmark-only`` (``nox -s performance-test``) and is skipped otherwise, as
tests/benchmarks/test_logging_cost.py is. Locally, run this file with pytest's
``-o addopts= -p no:xdist --benchmark-only --dummy-only`` (docs/quality/performance.md).
"""

from __future__ import annotations

import random
import re
import statistics
from pathlib import Path
from typing import TYPE_CHECKING

import pygame
import pytest

from glitchygames import clock
from glitchygames.audio import reserve_inner_game_channels
from glitchygames.audio.engine import default_channel_partition
from glitchygames.demo_player import DemoPlayer, DemoState, poster_frame
from glitchygames.inner_game import InnerGame, InnerGameState
from glitchygames.replay.pacer import INNER_FRAME_BUDGET_SECONDS, TickBudget
from tests.inner_game_tiles import QUIET, recorded_size, recording_id
from tests.workspace_goldens import every_games_golden, every_golden_and_bundled_demo

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Every bundled demo: (console script, recording), the goldens left out
GOLDENS = frozenset(every_games_golden(project_root=PROJECT_ROOT))
BUNDLED_DEMOS = [
    (console_script, recording)
    for console_script, recording in every_golden_and_bundled_demo(project_root=PROJECT_ROOT)
    if recording not in GOLDENS
]
# The demo left out of the ten tiles: it changes SDL's key repeat, one per process
LEFT_OUT_OF_THE_TILES = ('text-input-demo', 'typing.jsonl.gz')
TEN_DEMOS = [
    (console_script, recording)
    for console_script, recording in BUNDLED_DEMOS
    if (console_script, recording.name) != LEFT_OUT_OF_THE_TILES
]
TILE_COUNT = 10
# An Arcade frame at 60 Hz: the time each player is paid a round
ARCADE_TICK_SECONDS = 1 / 60
# Twenty seconds of Arcade frames: the shorter demos (330 to 600 frames) loop while timed
ARCADE_TIMED_FRAMES = 1200
# Builds per demo: the first cold for the test, the rest warm
BUILD_ROUNDS = 5
# The posters' stream seed: an Arcade draws them from random_stream('arcade-posters')
POSTER_SEED = 5
# Rounds of the posters' fast-forward, each from freshly built players
POSTER_ROUNDS = 3
# More Arcade frames than any fast-forward needs: one that never ends fails instead of hanging
MOST_POSTER_FRAMES = 100_000
MILLISECONDS_PER_SECOND = 1000.0
ENGINE_CONTEXT_PAGE = PROJECT_ROOT / 'docs' / 'architecture' / 'engine_context.md'
# The engine context page's Performance table row for ten players: its cost cell's milliseconds
TEN_PLAYERS_ROW = re.compile(r'^\| `ten demo players` \| (?P<milliseconds>\d+(?:\.\d+)?) ms \|')


@pytest.fixture
def benchmarks_only(request: pytest.FixtureRequest) -> None:
    """Skip unless pytest-benchmark times this run (``--benchmark-only``).

    pytest-benchmark turns benchmarks off only under xdist, and the Linux CI job runs serially.
    Every benchmark asks for it (through ``tiles_declared``); the check of the ten demos does
    not, so it runs in the normal suite (``--benchmark-only`` skips every test that is not a
    benchmark).
    """
    if not request.config.getoption('benchmark_only'):
        pytest.skip('builds and plays every bundled demo: run with --benchmark-only')


@pytest.fixture
def tiles_declared(benchmarks_only: None) -> None:
    """Partition the mixer as the outer game does and declare ten tiles' channels.

    Only under ``--benchmark-only`` (``benchmarks_only``).
    """
    default_channel_partition()
    reserve_inner_game_channels(games=TILE_COUNT)


@pytest.fixture
def left_out_demos_key_repeat_restored(console_script: str, recording: Path) -> Generator[None]:
    """Put SDL's key repeat back after the demo left out of the tiles, which changes it.

    Only after that one (plans/2026-11-20-window-owner-events.md is the engine's fix): any other
    demo that changes it fails the leaked-state guard.
    """
    delay, interval = pygame.key.get_repeat()
    try:
        yield
    finally:
        if (console_script, recording.name) == LEFT_OUT_OF_THE_TILES:
            pygame.key.set_repeat(delay, interval)


@pytest.fixture
def ten_players(tiles_declared: None) -> Generator[list[DemoPlayer]]:
    """Make a demo player of each of the ten demos; finish each afterwards.

    Yields:
        The players, each built and playing.

    """
    players = make_ten_players()
    try:
        yield players
    finally:
        finish(players=players)


def make_ten_players() -> list[DemoPlayer]:
    """Make a silent demo player of each of the ten demos, at the Arcade's tick.

    Returns:
        The players, each built and playing.

    """
    players = [
        DemoPlayer(
            command=console_script,
            recording=recording,
            nominal_tick_seconds=ARCADE_TICK_SECONDS,
            arguments=QUIET,
        )
        for console_script, recording in TEN_DEMOS
    ]
    for player in players:
        assert player.outcome.state is DemoState.PLAYING, f'{player.name}: {player.outcome}'
    return players


def finish(*, players: list[DemoPlayer]) -> None:
    """Finish each player, giving its channels back.

    Args:
        players: The players.

    """
    for player in players:
        player.finish()


@pytest.fixture
def print_lines(
    request: pytest.FixtureRequest, capsys: pytest.CaptureFixture[str]
) -> Callable[[list[str]], None]:
    """Return a printer of lines past pytest's capture, as the logging-cost benchmark prints.

    Returns:
        A function printing its lines to the terminal.

    """
    terminal = request.config.pluginmanager.get_plugin('terminalreporter')

    def print_past_the_capture(lines: list[str]) -> None:
        with capsys.disabled():
            terminal.write_line('\n' + '\n'.join(lines))

    return print_past_the_capture


def milliseconds(seconds: float) -> str:
    """Return seconds as milliseconds to a tenth.

    Args:
        seconds: The time.

    Returns:
        ``'12.3 ms'``.

    """
    return f'{seconds * MILLISECONDS_PER_SECOND:.1f} ms'


def test_the_ten_demos_are_ten_of_the_bundled_demos():
    """Ten tiles: every bundled demo but the one left out (an empty list would measure nothing)."""
    assert len(TEN_DEMOS) == TILE_COUNT
    assert len(BUNDLED_DEMOS) == TILE_COUNT + 1
    assert LEFT_OUT_OF_THE_TILES in {
        (console_script, recording.name) for console_script, recording in BUNDLED_DEMOS
    }


def test_the_documented_ten_player_frame_fits_the_budget():
    """The engine context page's ten-player Arcade frame is within ``INNER_FRAME_BUDGET_SECONDS``.

    The page records this file's median; a frame over the budget would mean ten tiles cannot
    play at speed on the machine measured, which the page must not hide.
    """
    lines = ENGINE_CONTEXT_PAGE.read_text(encoding='utf-8').splitlines()
    costs = [
        float(match.group('milliseconds'))
        for match in (TEN_PLAYERS_ROW.match(line) for line in lines)
        if match is not None
    ]

    assert len(costs) == 1, costs
    assert costs[0] / MILLISECONDS_PER_SECOND <= INNER_FRAME_BUDGET_SECONDS


@pytest.mark.usefixtures('left_out_demos_key_repeat_restored')
@pytest.mark.parametrize(
    ('console_script', 'recording'),
    [
        pytest.param(
            console_script,
            recording,
            id=recording_id(console_script=console_script, recording=recording),
        )
        for console_script, recording in BUNDLED_DEMOS
    ],
)
def test_a_restarts_build(
    benchmark,
    console_script: str,
    recording: Path,
    tiles_declared: None,
    print_lines: Callable[[list[str]], None],
):
    """Benchmark a loop's build of each bundled demo: the first cold for the test, then warm."""
    size = recorded_size(recording=recording)
    built: list[InnerGame] = []
    seconds_by_round: list[float] = []
    states_when_built: list[InnerGameState] = []

    def finish_the_last_build() -> None:
        if built:
            built[-1].finish()

    def build() -> None:
        started = clock.measured_seconds()
        built.append(
            InnerGame.replay(
                command=console_script,
                path=recording,
                name=f'build-{len(built) + 1}',
                size=size,
                arguments=QUIET,
            )
        )
        seconds_by_round.append(clock.measured_seconds() - started)
        states_when_built.append(built[-1].outcome.state)

    benchmark.pedantic(build, setup=finish_the_last_build, rounds=BUILD_ROUNDS, iterations=1)
    finish_the_last_build()

    # Each build was a running game, and none ran a frame (finished before its first)
    assert states_when_built == [InnerGameState.RUNNING] * BUILD_ROUNDS
    assert all(inner_game.outcome.frames_run == 0 for inner_game in built)
    label = recording_id(console_script=console_script, recording=recording)
    warm = ', '.join(milliseconds(seconds) for seconds in seconds_by_round[1:])
    print_lines([f'{label} builds: cold {milliseconds(seconds_by_round[0])}, warm {warm}'])


# Timed (--benchmark-only), the real clock decides how many frames each round runs
@pytest.mark.frames_vary(reason='the real-time budget decides how many frames each round runs')
def test_ten_demo_players_per_arcade_frame(
    benchmark,
    ten_players: list[DemoPlayer],
    print_lines: Callable[[list[str]], None],
):
    """Benchmark one Arcade frame: ten players share one ``INNER_FRAME_BUDGET_SECONDS`` budget."""
    frames_by_round: list[int] = []
    budgets_spent = 0

    def one_arcade_frame() -> None:
        nonlocal budgets_spent
        budget = TickBudget(length_seconds=INNER_FRAME_BUDGET_SECONDS)
        frames_by_round.append(
            sum(
                player.tick(elapsed_seconds=ARCADE_TICK_SECONDS, budget=budget)
                for player in ten_players
            )
        )
        budgets_spent += budget.is_spent

    benchmark.pedantic(one_arcade_frame, rounds=ARCADE_TIMED_FRAMES, iterations=1)

    for player in ten_players:
        assert player.outcome.state in {DemoState.PLAYING, DemoState.LOOPED}, player.outcome
        assert player.frames_played > 0, player.name
    print_lines([
        (
            f'Ten players, {ARCADE_TIMED_FRAMES} Arcade frames, a '
            f'{milliseconds(INNER_FRAME_BUDGET_SECONDS)} budget each: the budget was spent in '
            f'{budgets_spent}; frames per Arcade frame: mean '
            f'{statistics.fmean(frames_by_round):.2f}, most {max(frames_by_round)}'
        ),
        *(
            (
                f'  {player.name}: {player.frames_played} frames, {player.generation - 1} loops, '
                f'effective speed {player.effective_speed():.2f}'
            )
            for player in ten_players
        ),
    ])


# Timed (--benchmark-only), the real clock decides how many frames each Arcade frame runs
@pytest.mark.frames_vary(reason='the real-time budget decides how many frames each slice runs')
def test_ten_posters_fast_forward(
    benchmark,
    tiles_declared: None,
    print_lines: Callable[[list[str]], None],
):
    """Benchmark the ten players' fast-forwards to their posters, a shared budget per frame."""
    rounds: list[list[DemoPlayer]] = []
    arcade_frames_by_round: list[int] = []

    def ten_new_players() -> None:
        if rounds:
            finish(players=rounds[-1])
        rounds.append(make_ten_players())

    def fast_forward_every_player_to_its_poster() -> None:
        players = rounds[-1]
        stream = random.Random(POSTER_SEED)
        posters = [
            poster_frame(frame_count=player.frame_count, stream=stream) for player in players
        ]
        waiting = set(range(len(players)))
        for arcade_frame in range(1, MOST_POSTER_FRAMES):
            budget = TickBudget(length_seconds=INNER_FRAME_BUDGET_SECONDS)
            for index in sorted(waiting):
                if players[index].fast_forward(to_frame=posters[index], budget=budget):
                    waiting.discard(index)
            if not waiting:
                arcade_frames_by_round.append(arcade_frame)
                return
        pytest.fail(f'the posters were not reached in {MOST_POSTER_FRAMES} Arcade frames')

    try:
        benchmark.pedantic(
            fast_forward_every_player_to_its_poster,
            setup=ten_new_players,
            rounds=POSTER_ROUNDS,
            iterations=1,
        )
    finally:
        if rounds:
            finish(players=rounds[-1])

    assert len(arcade_frames_by_round) == POSTER_ROUNDS
    budget = milliseconds(INNER_FRAME_BUDGET_SECONDS)
    print_lines([
        (
            f'Ten posters (seed {POSTER_SEED}), a {budget} budget shared each Arcade frame: '
            f'{arcade_frames_by_round} Arcade frames by round'
        )
    ])
