"""One recorded game for an Arcade tile: it loops, fast-forwards and paces itself.

``DemoPlayer`` (glitchygames/demo_player.py; plans/2026-11-20-arcade-5-playback-core.md, Task 4
and decisions 4 to 13) owns one ``InnerGame`` replaying a recording, paces it with a
``RecordedFramePacer`` from the elapsed time its host serves, runs it within a ``TickBudget`` its
host may share among players, rebuilds it from frame 0 at its end, and says how it stands
(``DemoOutcome``). The games are stand-ins installed as commands (tests/stand_in_games.py), so the
engine's tests run no member.

The budgets run on a fake real-time clock (``FrameCostClock``, tests/inner_game_tiles.py) on
which each frame any player runs costs ``FRAME_COST_SECONDS`` and a build what the test charges,
so a test says how many frames a budget allows. Every recording's frames are rewritten to last
``FRAME_SECONDS`` (both powers of two, so every sum the pacer and the budget make is exact in a
float).
"""

from __future__ import annotations

import ast
import hashlib
import itertools
import random
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pygame
import pytest
from pydantic import BaseModel, ConfigDict

import glitchygames.demo_player as demo_player_module
from glitchygames.audio.voices import (
    INNER_CHANNELS_SLOT,
    InnerGameChannelsError,
    reserve_channels,
    reserve_inner_game_channels,
)
from glitchygames.demo_player import (
    POSTER_SPAN_END_FRACTION,
    POSTER_SPAN_START_FRACTION,
    DemoOutcome,
    DemoPlayer,
    DemoState,
    poster_frame,
)
from glitchygames.engine_context import current_context, default_context
from glitchygames.inner_game import InnerGame, InnerGameAudibleError
from glitchygames.replay.audit import read_digest_file
from glitchygames.replay.pacer import MAX_OWED_INNER_FRAMES
from glitchygames.scenes import Scene, SceneManager
from tests.audio.voice_support import LEGACY_CHANNELS, LIBRARY_CHANNELS, LIVE_POOL
from tests.inner_game_tiles import (
    INTERLEAVED_STEPS,
    FrameCostClock,
    play_alone,
    reference_digests,
)
from tests.replay.replay_helpers import rewrite_recording, tamper_first_sprite_rect
from tests.stand_in_games import (
    STAND_IN_GAME_FRAMES,
    StandInGame,
    copy_recording,
    record_stand_in_game_once,
    use_stand_in_game,
    write_chiming_stand_in_game,
    write_header_only_recording,
    write_stand_in_game,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from typing import Any

    from pytest_mock import MockerFixture

# The stand-ins' packages: names no other test's stand-in uses, since this process imports them
STAND_IN_PACKAGE = 'demo_player_rally'
CHIMING_STAND_IN_PACKAGE = 'demo_player_chime'
# The chiming stand-in plays a plain Sound.play() on this frame (its own count, from 1)
CHIME_FRAME = 3
# The seed the second recording of the stand-in is made under: its frames differ from the first's
OTHER_SEED = '7'
# Every recorded frame lasts this long (rewritten), and the players tick at this period
FRAME_SECONDS = 1 / 64
NOMINAL_TICK_SECONDS = 1 / 64
# Ten tiles, as the Arcade's grid; the host declares their channels once (rule 6 of inner_game.py)
DECLARED_PLAYERS = 10
# A shared budget allows this many frames a tick among the ten players
SHARED_BUDGET_FRAMES = 3
# How long any player may wait for a frame beside nine others sharing that budget: ten players,
# three frames a tick, so each should run within four ticks
MOST_TICKS_WAITING = 4
# The shared-budget run's length in ticks: several rounds of the ten players
SHARED_BUDGET_TICKS = 60
# Twenty loops of ten players: no declaration may run out
LOOPS = 20
# A tick paying this many seconds is a stall (more than the pacer's STALL_TICK_SECONDS)
STALL_SECONDS = 10.0
# What a build costs when a test charges it: two frames' worth of real time
BUILD_COST_FRAMES = 2
# More ticks than any test needs: a loop that never ends fails instead of hanging
MOST_TICKS = 2000
# The frame a tampered copy first differs at
TAMPERED_FRAME = 10
# The frame the scene raises on, in the crash test (its own count, from 1)
CRASH_FRAME = 3
# Frames appended to a recording so it is longer than the game's run (a length divergence)
EXTRA_RECORDED_FRAMES = 5
# Quiet inner engines
QUIET = ('--log-level', 'error')
# The modules glitchygames/demo_player.py may import (the guard): no game, no clock
ALLOWED_IMPORTS = frozenset({
    '__future__',
    'logging',
    'enum',
    'typing',
    'collections.abc',
    'pathlib',
    'random',
    'pygame',
    'pydantic',
    'glitchygames.audio.voices',
    'glitchygames.inner_game',
    'glitchygames.replay.driver',
    'glitchygames.replay.pacer',
    'glitchygames.tracing',
})
# What reads time: the guard refuses each in glitchygames/demo_player.py
TIME_MODULES = frozenset({'time', 'datetime', 'glitchygames.clock'})
POSTER_SEEDS = range(50)
POSTER_FRAME_COUNTS = (1, 2, 3, 9, 10, 11, 20, 99, 100, 101, 1234)


def rewrite_frame_durations(*, recording: Path) -> None:
    """Give every frame of a recording the duration ``FRAME_SECONDS`` (the game ignores it)."""

    def change(trace: dict[str, Any]) -> None:
        for frame in trace['frames']:
            frame['dt'] = FRAME_SECONDS

    rewrite_recording(recording_path=recording, change=change)


def lengthen(*, recording: Path) -> None:
    """Append copies of the last frames: the recording outlasts the game's run."""

    def change(trace: dict[str, Any]) -> None:
        last_frames = trace['frames'][-EXTRA_RECORDED_FRAMES:]
        trace['frames'].extend(
            dict(frame, frame=frame['frame'] + EXTRA_RECORDED_FRAMES) for frame in last_frames
        )

    rewrite_recording(recording_path=recording, change=change)


def pixel_hash(surface: pygame.Surface | None) -> str:
    """Return a hash of a player's surface's pixels (it must have one).

    Returns:
        The SHA-256 of its RGB bytes.

    """
    assert surface is not None
    return hashlib.sha256(pygame.image.tobytes(surface, 'RGB')).hexdigest()


def scene_that_raises(*, on_frame: int, mocker: MockerFixture) -> Callable[[InnerGame], None]:
    """Return an ``on_new_game`` hook making the new game's scene raise on one of its frames.

    Args:
        on_frame: The frame it raises on, by the stand-in's own count (from 1), after drawing.
        mocker: pytest-mock's fixture (an injected failure).

    Returns:
        The hook.

    """

    def break_the_scene(inner_game: InnerGame) -> None:
        scene = active_scene(inner_game)
        scene_dt_tick = scene.dt_tick

        def dt_tick_then_raise(dt: float) -> None:
            scene_dt_tick(dt)
            if vars(scene)['frames'] == on_frame:  # the stand-in's own frame count
                message = 'the scene broke'
                raise RuntimeError(message)

        # An injected failure on that frame
        mocker.patch.object(scene, 'dt_tick', side_effect=dt_tick_then_raise)

    return break_the_scene


def active_scene(inner_game: InnerGame) -> Scene:
    """Return an inner game's active scene.

    Returns:
        The scene.

    """
    with inner_game.context.active():
        scene = SceneManager().active_scene
    assert isinstance(scene, Scene)
    return scene


class InstalledStandIn(BaseModel):
    """A stand-in game installed as a command, and this test's own copies of its recordings.

    Attributes:
        command: Its console script.
        recording: Its recording.
        other_recording: Another recording of it (``OTHER_SEED``'s, or the same frames).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    command: str
    recording: Path
    other_recording: Path


@pytest.fixture(scope='module')
def recorded_stand_ins(tmp_path_factory: pytest.TempPathFactory) -> tuple[StandInGame, Path, Path]:
    """Record the stand-in twice (two seeds) once per module, every frame ``FRAME_SECONDS`` long.

    Returns:
        The stand-in game, its recording, and its recording under ``OTHER_SEED``.

    """
    root = tmp_path_factory.mktemp('demo-player')
    game = write_stand_in_game(directory=root / 'site-packages', package=STAND_IN_PACKAGE)
    recording = record_stand_in_game_once(game=game, path=root / 'recorded.jsonl.gz')
    other = record_stand_in_game_once(
        game=game, path=root / 'other.jsonl.gz', extra_arguments=('--random-seed', OTHER_SEED)
    )
    for each in (recording, other):
        rewrite_frame_durations(recording=each)
    return game, recording, other


@pytest.fixture
def rally(
    recorded_stand_ins: tuple[StandInGame, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[InstalledStandIn]:
    """Install the stand-in as a command here and for the children (the reference replays).

    Yields:
        The stand-in and this test's copies of its recordings; its package is forgotten
        afterwards.

    """
    game, recording, other = recorded_stand_ins
    use_stand_in_game(install_directory=game.install_directory, monkeypatch=monkeypatch)
    try:
        yield InstalledStandIn(
            command=game.console_script,
            recording=copy_recording(recording=recording, path=tmp_path / 'rally.jsonl.gz'),
            other_recording=copy_recording(recording=other, path=tmp_path / 'other.jsonl.gz'),
        )
    finally:
        sys.modules.pop(game.package, None)


@pytest.fixture(scope='module')
def recorded_chiming_stand_in(tmp_path_factory: pytest.TempPathFactory) -> tuple[StandInGame, Path]:
    """Record the chiming stand-in (a plain ``Sound.play()`` on ``CHIME_FRAME``) once per module.

    Returns:
        The stand-in game and its recording.

    """
    root = tmp_path_factory.mktemp('demo-player-chime')
    game = write_chiming_stand_in_game(
        directory=root / 'site-packages',
        package=CHIMING_STAND_IN_PACKAGE,
        chime_on_frame=CHIME_FRAME,
    )
    recording = record_stand_in_game_once(game=game, path=root / 'recorded.jsonl.gz')
    rewrite_frame_durations(recording=recording)
    return game, recording


@pytest.fixture
def chime(
    recorded_chiming_stand_in: tuple[StandInGame, Path],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[InstalledStandIn]:
    """Install the chiming stand-in as a command in this process.

    Yields:
        The stand-in and this test's copy of its recording (both recordings); its package is
        forgotten afterwards.

    """
    game, recording = recorded_chiming_stand_in
    monkeypatch.syspath_prepend(game.install_directory)
    copy = copy_recording(recording=recording, path=tmp_path / 'chime.jsonl.gz')
    try:
        yield InstalledStandIn(command=game.console_script, recording=copy, other_recording=copy)
    finally:
        sys.modules.pop(game.package, None)


@pytest.fixture(autouse=True)
def declared_players() -> Generator[None]:
    """Partition the mixer as an outer game does and declare ten tiles' channels, every one idle.

    Yields:
        Nothing; every channel is stopped afterwards.

    """
    pygame.mixer.stop()
    reserve_channels(
        live_pool=LIVE_POOL, library_channels=LIBRARY_CHANNELS, legacy_channels=LEGACY_CHANNELS
    )
    reserve_inner_game_channels(games=DECLARED_PLAYERS)
    try:
        yield
    finally:
        pygame.mixer.stop()


class Players:
    """The test's players, watched by its frame-cost clock; the fixture finishes each one."""

    def __init__(self) -> None:
        """Start with no player and a fresh clock."""
        self.clock = FrameCostClock()
        self.made: list[DemoPlayer] = []

    def make(
        self,
        *,
        command: str,
        recording: Path,
        arguments: tuple[str, ...] = QUIET,
        on_new_game: Callable[[InnerGame], None] | None = None,
    ) -> DemoPlayer:
        """Make a player of a recording, ticking at ``NOMINAL_TICK_SECONDS``.

        Returns:
            The player.

        """
        player = DemoPlayer(
            command=command,
            recording=recording,
            nominal_tick_seconds=NOMINAL_TICK_SECONDS,
            arguments=arguments,
            on_new_game=on_new_game,
        )
        self.made.append(player)
        self.clock.players.append(player)
        return player


@pytest.fixture
def players() -> Generator[Players]:
    """Return the test's players; each is finished afterwards, giving its channels back.

    Yields:
        The players.

    """
    made = Players()
    try:
        yield made
    finally:
        for player in made.made:
            player.finish()


def tick(
    *, player: DemoPlayer, clock: FrameCostClock, frames_of_time: float, budget_frames: float
) -> int:
    """Tick a player with ``frames_of_time`` frames' worth of elapsed time and its own budget.

    Returns:
        How many frames ran.

    """
    return player.tick(
        elapsed_seconds=frames_of_time * FRAME_SECONDS,
        budget=clock.budget(frame_count=budget_frames),
    )


def hashes_by_generation(
    *, player: DemoPlayer, clock: FrameCostClock, generation: int
) -> dict[int, list[str]]:
    """Tick a player a frame of time and a one-frame budget at a time until a generation starts.

    A one-frame budget runs at most one frame a tick, and the frame that ends a game spends it,
    so a tick runs frames of one game only.

    Returns:
        By generation, the pixel hash of its surface after each tick that ran a frame of it.

    """
    hashes: dict[int, list[str]] = {}
    for _tick in range(MOST_TICKS):
        if tick(player=player, clock=clock, frames_of_time=1, budget_frames=1):
            hashes.setdefault(player.generation, []).append(pixel_hash(player.surface))
        if player.generation >= generation:
            return hashes
    pytest.fail(f'the player did not reach generation {generation} in {MOST_TICKS} ticks')


def tick_until_state(*, player: DemoPlayer, clock: FrameCostClock, state: DemoState) -> None:
    """Tick a player a frame of time and a one-frame budget at a time until it is in a state."""
    for _tick in range(MOST_TICKS):
        if player.outcome.state is state:
            return
        tick(player=player, clock=clock, frames_of_time=1, budget_frames=1)
    pytest.fail(f'the player was not {state} after {MOST_TICKS} ticks: {player.outcome}')


def tick_until_generation(*, player: DemoPlayer, clock: FrameCostClock, generation: int) -> None:
    """Tick a player a frame of time and a one-frame budget at a time until a generation starts."""
    hashes_by_generation(player=player, clock=clock, generation=generation)


class TestATick:
    """It pays the pacer the caller's elapsed time and runs the owed frames within the budget."""

    def test_three_frames_of_time_run_three_frames_a_tick_once_running(
        self,
        rally: InstalledStandIn,
        players: Players,
    ):
        """From rest the last owed frame waits a tick (the pacer's rule 2); then three a tick."""
        player = players.make(command=rally.command, recording=rally.recording)

        frames_by_tick = [
            tick(player=player, clock=players.clock, frames_of_time=3, budget_frames=100)
            for _tick in range(4)
        ]

        assert frames_by_tick == [2, 3, 3, 3]
        assert player.frame_index == sum(frames_by_tick)

    def test_a_one_frame_budget_runs_one_and_owes_the_rest_to_the_next_ticks(
        self,
        rally: InstalledStandIn,
        players: Players,
    ):
        """Nothing lost and none skipped: the owed frames run on the ticks after, one each."""
        player = players.make(command=rally.command, recording=rally.recording)

        first = tick(player=player, clock=players.clock, frames_of_time=3, budget_frames=1)
        later = [
            tick(player=player, clock=players.clock, frames_of_time=0, budget_frames=100)
            for _tick in range(3)
        ]

        assert first == 1
        assert later == [1, 1, 0]
        assert player.frame_index == 3

    def test_every_frames_digest_equals_the_recordings_headless_replay(
        self,
        rally: InstalledStandIn,
        players: Players,
        tmp_path: Path,
    ):
        """Ticked unevenly to its end, its frames are the recording replayed alone, headless."""
        digest_path = tmp_path / 'player.digest'
        player = players.make(
            command=rally.command,
            recording=rally.recording,
            arguments=(*QUIET, '--replay-digest', str(digest_path)),
        )
        uneven = itertools.cycle((1, 3, 0, 2, 5))

        for _tick in range(MOST_TICKS):
            tick(player=player, clock=players.clock, frames_of_time=next(uneven), budget_frames=2)
            if player.generation == 2:
                break

        digests, divergence = read_digest_file(path=digest_path)
        assert divergence is None
        assert digests == reference_digests(
            console_script=rally.command, recording=rally.recording, work_directory=tmp_path
        )
        assert len(digests) == STAND_IN_GAME_FRAMES

    def test_the_callers_context_is_current_after_a_tick(
        self,
        rally: InstalledStandIn,
        players: Players,
    ):
        """Every frame runs in the game's own context and the default one is current again."""
        player = players.make(command=rally.command, recording=rally.recording)

        tick(player=player, clock=players.clock, frames_of_time=3, budget_frames=100)

        assert current_context() is default_context()


class TestSlowMotion:
    """A player that cannot keep up plays every frame, slower; a stall never bursts past a limit."""

    def test_a_budget_for_half_the_owed_frames_plays_everything_in_order_at_half_speed(
        self,
        rally: InstalledStandIn,
        players: Players,
    ):
        """One frame a tick of two owed: every frame in order, twice the ticks, speed about 0.5."""
        ample = players.make(command=rally.command, recording=rally.recording)
        slow = players.make(command=rally.command, recording=rally.recording)

        def ticks_to_the_end(player: DemoPlayer, budget_frames: float) -> tuple[int, list[int]]:
            frame_indices: list[int] = []
            for tick_number in range(1, MOST_TICKS):
                tick(
                    player=player,
                    clock=players.clock,
                    frames_of_time=2,
                    budget_frames=budget_frames,
                )
                if player.generation == 2:
                    return tick_number, frame_indices
                frame_indices.append(player.frame_index)
            pytest.fail('the player never looped')

        ample_ticks, _ample_indices = ticks_to_the_end(ample, 100)
        slow_ticks, slow_indices = ticks_to_the_end(slow, 1)

        # The last frame spends its tick's budget, so the loop's build comes the tick after
        assert slow_indices == list(range(1, STAND_IN_GAME_FRAMES + 1))
        assert slow_ticks == STAND_IN_GAME_FRAMES + 1
        assert ample_ticks <= STAND_IN_GAME_FRAMES // 2 + 2
        assert slow.is_behind
        assert slow.effective_speed() == pytest.approx(0.5)
        assert ample.effective_speed() == pytest.approx(1.0, abs=0.1)

    def test_a_stall_runs_no_more_than_the_owed_limit(
        self,
        rally: InstalledStandIn,
        players: Players,
    ):
        """Ten seconds owed at once: a bounded burst (looping on the way), the rest dropped."""
        player = players.make(command=rally.command, recording=rally.recording)
        tick(player=player, clock=players.clock, frames_of_time=1, budget_frames=100)

        burst = player.tick(
            elapsed_seconds=STALL_SECONDS, budget=players.clock.budget(frame_count=MOST_TICKS)
        )

        assert 1 < burst <= MAX_OWED_INNER_FRAMES
        assert player.generation == 2
        assert player.outcome.state is DemoState.LOOPED


class TestBesideAnotherPlayer:
    """Sub-plan 3's proof through the player: two players ticked unevenly each play alone."""

    def test_two_players_ticked_unevenly_each_equal_their_alone_digests(
        self,
        rally: InstalledStandIn,
        players: Players,
        tmp_path: Path,
    ):
        """``INTERLEAVED_STEPS`` frames each in turn; each one's digests are its own alone."""
        digest_paths = (tmp_path / 'first.digest', tmp_path / 'second.digest')
        pair = tuple(
            players.make(
                command=rally.command,
                recording=each,
                arguments=(*QUIET, '--replay-digest', str(digest_path)),
            )
            for each, digest_path in zip(
                (rally.recording, rally.other_recording), digest_paths, strict=True
            )
        )
        steps = itertools.cycle(INTERLEAVED_STEPS)

        for _turn in range(MOST_TICKS):
            if all(player.generation > 1 for player in pair):
                break
            for player, frame_count in zip(pair, next(steps), strict=True):
                player.tick(
                    elapsed_seconds=STALL_SECONDS,
                    budget=players.clock.budget(frame_count=frame_count),
                )

        for each, digest_path in zip(
            (rally.recording, rally.other_recording), digest_paths, strict=True
        ):
            digests, divergence = read_digest_file(path=digest_path)
            assert divergence is None
            assert digests == reference_digests(
                console_script=rally.command, recording=each, work_directory=tmp_path
            )
        first, _ = read_digest_file(path=digest_paths[0])
        second, _ = read_digest_file(path=digest_paths[1])
        assert first != second


class TestASharedBudget:
    """Ten players share one budget a tick, the start rotating: none waits long for a frame."""

    def test_ten_players_with_three_frames_a_tick_each_run_within_a_few_ticks(
        self,
        rally: InstalledStandIn,
        players: Players,
    ):
        """Decision 3's reason: what one player leaves, the next gets, and every one moves on."""
        tiles = [
            players.make(command=rally.command, recording=rally.recording)
            for _index in range(DECLARED_PLAYERS)
        ]
        last_ran = dict.fromkeys(range(DECLARED_PLAYERS), 0)
        longest_wait = 0
        start = 0

        for tick_number in range(1, SHARED_BUDGET_TICKS + 1):
            budget = players.clock.budget(frame_count=SHARED_BUDGET_FRAMES)
            for index in [*range(start, DECLARED_PLAYERS), *range(start)]:
                if tiles[index].tick(elapsed_seconds=FRAME_SECONDS, budget=budget, most_frames=1):
                    longest_wait = max(longest_wait, tick_number - last_ran[index])
                    last_ran[index] = tick_number
                    start = (index + 1) % DECLARED_PLAYERS
        longest_wait = max(
            longest_wait, *(SHARED_BUDGET_TICKS - last for last in last_ran.values())
        )

        assert longest_wait <= MOST_TICKS_WAITING
        # The budget is all used, every tick: what a player leaves, the next one runs
        assert sum(tile.frames_played for tile in tiles) == (
            SHARED_BUDGET_FRAMES * SHARED_BUDGET_TICKS
        )


class TestALoop:
    """At the end it rebuilds from frame 0 in a new context, the old game's channels given back."""

    def test_the_second_run_equals_the_first_and_on_new_game_runs_before_its_first_frame(
        self,
        rally: InstalledStandIn,
        players: Players,
    ):
        """A new context and surface, generation 2, the same frames, the hook before frame 0."""
        games: list[tuple[InnerGame, int]] = []
        player = players.make(
            command=rally.command,
            recording=rally.recording,
            on_new_game=lambda inner_game: games.append((inner_game, inner_game.frame_index)),
        )
        first_surface = player.surface

        hashes_to_the_second = hashes_by_generation(
            player=player, clock=players.clock, generation=2
        )
        assert player.outcome.state is DemoState.LOOPED
        hashes = hashes_by_generation(player=player, clock=players.clock, generation=3)
        first_run = hashes_to_the_second[1]
        second_run = [*hashes_to_the_second[2], *hashes[2]]

        assert player.outcome.state is DemoState.LOOPED
        assert first_run == second_run
        assert len(first_run) == STAND_IN_GAME_FRAMES
        assert [frame_index for _game, frame_index in games] == [0, 0, 0]
        contexts = {id(inner_game.context) for inner_game, _frame_index in games}
        assert len(contexts) == len(games)
        assert player.name == f'{rally.command}/{rally.recording.name}'
        assert games[0][0].context.name == f'{player.name} #1'
        assert player.surface is not first_surface
        assert player.surface is games[-1][0].surface
        tick(player=player, clock=players.clock, frames_of_time=1, budget_frames=1)
        assert player.outcome.state is DemoState.PLAYING

    def test_twenty_loops_of_ten_players_never_exhaust_the_declaration(
        self,
        rally: InstalledStandIn,
        players: Players,
    ):
        """Each loop finishes the old game first: every old one holds no channel, every build ok."""
        games: list[InnerGame] = []
        tiles = [
            players.make(command=rally.command, recording=rally.recording, on_new_game=games.append)
            for _index in range(DECLARED_PLAYERS)
        ]

        for _tick in range(MOST_TICKS):
            if all(tile.generation > LOOPS for tile in tiles):
                break
            for tile in tiles:
                tile.tick(
                    elapsed_seconds=STALL_SECONDS,
                    budget=players.clock.budget(frame_count=MOST_TICKS),
                )

        assert all(tile.generation > LOOPS for tile in tiles)
        assert all(tile.outcome.state is not DemoState.COULD_NOT_START for tile in tiles)
        current = {id(tile.inner_game) for tile in tiles}
        old_games = [inner_game for inner_game in games if id(inner_game) not in current]
        assert len(old_games) >= LOOPS * DECLARED_PLAYERS
        assert all(
            inner_game.context.value(slot=INNER_CHANNELS_SLOT).partition is None
            for inner_game in old_games
        )

    def test_a_restarts_build_is_charged_to_the_shared_budget(
        self,
        rally: InstalledStandIn,
        players: Players,
    ):
        """The build's real time leaves the next player less: here, nothing."""
        looping = players.make(
            command=rally.command,
            recording=rally.recording,
            on_new_game=lambda _inner_game: players.clock.charge_frames(
                frame_count=BUILD_COST_FRAMES
            ),
        )
        waiting = players.make(command=rally.command, recording=rally.other_recording)
        assert looping.fast_forward(
            to_frame=looping.frame_count - 1, budget=players.clock.budget(frame_count=MOST_TICKS)
        )
        tick(player=waiting, clock=players.clock, frames_of_time=1, budget_frames=1)
        budget = players.clock.budget(frame_count=1 + BUILD_COST_FRAMES)

        looping_frames = looping.tick(elapsed_seconds=FRAME_SECONDS, budget=budget)
        waiting_frames = waiting.tick(elapsed_seconds=FRAME_SECONDS, budget=budget)

        assert looping_frames == 1
        assert looping.generation == 2
        assert budget.is_spent
        assert waiting_frames == 0

    def test_a_player_whose_turn_comes_with_the_budget_spent_builds_on_a_later_tick(
        self,
        rally: InstalledStandIn,
        players: Players,
    ):
        """At its end with nothing left of the budget: no build now, one the next tick."""
        player = players.make(command=rally.command, recording=rally.recording)
        assert player.fast_forward(
            to_frame=player.frame_count - 1, budget=players.clock.budget(frame_count=MOST_TICKS)
        )
        tick(player=player, clock=players.clock, frames_of_time=1, budget_frames=1)
        assert player.generation == 1
        assert player.outcome.state is DemoState.PLAYING

        tick(player=player, clock=players.clock, frames_of_time=1, budget_frames=1)

        assert player.generation == 2
        assert player.outcome.state is DemoState.LOOPED


class TestSound:
    """A new player is silent; heard, it is heard, across its loops; a fast-forward refuses it."""

    @staticmethod
    def chime_channel(player: DemoPlayer) -> pygame.mixer.Channel | None:
        """Return what the chiming stand-in's ``Sound.play()`` returned in the current game.

        Returns:
            The channel it played on, or None.

        """
        assert player.inner_game is not None
        channel = vars(active_scene(player.inner_game))['chime_channel']  # the stand-in's own
        assert channel is None or isinstance(channel, pygame.mixer.Channel)
        return channel

    def run_past_the_chime(self, *, player: DemoPlayer, clock: FrameCostClock) -> None:
        """Tick until the chiming stand-in's chime frame has run in the current game."""
        while player.frame_index < CHIME_FRAME:
            tick(player=player, clock=clock, frames_of_time=1, budget_frames=1)

    def test_a_new_player_is_silent_and_its_chime_finds_no_channel(
        self,
        chime: InstalledStandIn,
        players: Players,
    ):
        """Muted by default (decision 11): the plain play starts nothing."""
        player = players.make(command=chime.command, recording=chime.recording)

        self.run_past_the_chime(player=player, clock=players.clock)

        assert player.audible is False
        assert self.chime_channel(player) is None

    def test_heard_it_is_heard_and_stays_heard_across_a_loop(
        self,
        chime: InstalledStandIn,
        players: Players,
    ):
        """The setting is the player's: the looped game is made audible before its first frame."""
        heard_at_build: list[bool] = []
        player = players.make(
            command=chime.command,
            recording=chime.recording,
            on_new_game=lambda inner_game: heard_at_build.append(inner_game.audible),
        )
        player.set_audible(audible=True)

        self.run_past_the_chime(player=player, clock=players.clock)
        assert player.audible is True
        assert self.chime_channel(player) is not None
        tick_until_generation(player=player, clock=players.clock, generation=2)
        self.run_past_the_chime(player=player, clock=players.clock)

        assert player.audible is True
        assert self.chime_channel(player) is not None
        assert heard_at_build == [False, True]
        player.set_audible(audible=False)
        assert player.audible is False

    def test_a_looped_game_that_cannot_be_heard_plays_silent_and_says_so(
        self,
        chime: InstalledStandIn,
        players: Players,
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ):
        """Its heard set refused at the loop (an injected refusal): silent, logged, it plays on."""
        player = players.make(command=chime.command, recording=chime.recording)
        player.set_audible(audible=True)
        # An injected refusal of the looped game's heard set
        mocker.patch.object(
            InnerGame, 'set_audible', side_effect=InnerGameChannelsError('no heard set')
        )

        tick_until_generation(player=player, clock=players.clock, generation=2)

        assert player.audible is False
        assert player.outcome.state is DemoState.LOOPED
        assert any('no heard set' in record.getMessage() for record in caplog.records)

    def test_a_fast_forward_refuses_an_audible_player(
        self,
        rally: InstalledStandIn,
        players: Players,
    ):
        """``InnerGameAudibleError``, nothing run (decision 8)."""
        player = players.make(command=rally.command, recording=rally.recording)
        player.set_audible(audible=True)

        with pytest.raises(InnerGameAudibleError, match='set_audible'):
            player.fast_forward(to_frame=5, budget=players.clock.budget(frame_count=MOST_TICKS))

        assert player.frame_index == 0


class TestAFastForward:
    """Task 3's fast-forward through the player: silent, sliced, and then the next tick's frame."""

    def test_sliced_it_reaches_the_frame_and_the_next_tick_draws_it_as_alone(
        self,
        rally: InstalledStandIn,
        players: Players,
        tmp_path: Path,
    ):
        """Three frames a call to frame 11; the tick after draws frame 11's pixels, as alone."""
        to_frame = 11
        player = players.make(command=rally.command, recording=rally.recording)
        alone = play_alone(
            console_script=rally.command, recording=rally.recording, work_directory=tmp_path
        )

        calls = 0
        while not player.fast_forward(
            to_frame=to_frame, budget=players.clock.budget(frame_count=3)
        ):
            calls += 1
        ran = tick(player=player, clock=players.clock, frames_of_time=1, budget_frames=1)

        assert calls == to_frame // 3
        assert ran == 1
        assert player.frame_index == to_frame + 1
        assert pixel_hash(player.surface) == alone.pixel_hashes[to_frame]

    def test_a_player_that_could_not_start_never_reaches_a_frame(
        self, rally: InstalledStandIn, players: Players
    ):
        """No game: False, not the game's ValueError for a frame count of 0."""
        player = players.make(command='no-such-command-anywhere', recording=rally.recording)

        assert player.fast_forward(to_frame=5, budget=players.clock.budget(frame_count=1)) is False
        assert player.outcome.state is DemoState.COULD_NOT_START

    def test_a_frame_past_the_recording_is_a_value_error(
        self,
        rally: InstalledStandIn,
        players: Players,
    ):
        """The game's own refusal, for a running game."""
        player = players.make(command=rally.command, recording=rally.recording)

        with pytest.raises(ValueError, match='frame count'):
            player.fast_forward(
                to_frame=player.frame_count, budget=players.clock.budget(frame_count=1)
            )

    def test_a_divergence_on_the_way_is_the_players_divergence(
        self,
        rally: InstalledStandIn,
        players: Players,
    ):
        """A tampered frame before the target: False, and the divergence policy's first restart.

        Until the rebuild the player reads PLAYING, never DIVERGED (which means frozen: rule 4),
        with the divergence's report.
        """
        tamper_first_sprite_rect(recording_path=rally.recording, frame_number=TAMPERED_FRAME)
        player = players.make(command=rally.command, recording=rally.recording)

        reached = player.fast_forward(
            to_frame=player.frame_count - 1, budget=players.clock.budget(frame_count=MOST_TICKS)
        )

        assert reached is False
        assert player.generation == 1
        assert player.outcome.state is DemoState.PLAYING
        assert player.outcome.report is not None
        assert player.outcome.report.startswith(f'Replay diverged at frame {TAMPERED_FRAME}')
        tick(player=player, clock=players.clock, frames_of_time=1, budget_frames=1)
        assert player.generation == 2
        assert player.outcome.state is DemoState.LOOPED


class TestAPosterFrame:
    """A frame drawn uniformly from the 10% to 90% span, from the caller's stream (decision 9)."""

    def test_it_is_within_the_span_for_every_length_and_seed(self):
        """Never a title screen's first frames or a quit tail's last, always a real frame."""
        for frame_count in POSTER_FRAME_COUNTS:
            for seed in POSTER_SEEDS:
                frame = poster_frame(frame_count=frame_count, stream=random.Random(seed))
                assert 0 <= frame < frame_count
                assert frame >= int(frame_count * POSTER_SPAN_START_FRACTION)
                assert frame <= frame_count * POSTER_SPAN_END_FRACTION

    def test_the_same_seed_gives_the_same_frames(self):
        """A pure function of the stream: the Arcade's seeded stream gives the same posters."""
        first_stream = random.Random(3)
        second_stream = random.Random(3)

        first = [poster_frame(frame_count=100, stream=first_stream) for _draw in range(5)]
        second = [poster_frame(frame_count=100, stream=second_stream) for _draw in range(5)]

        assert first == second
        # The stream moves on: each draw is a new poster, not one repeated
        assert len(set(first)) > 1

    def test_every_frame_of_the_span_can_be_drawn(self):
        """Uniform over the span: each of its frames comes up, none outside it."""
        stream = random.Random(11)
        drawn = {poster_frame(frame_count=20, stream=stream) for _draw in range(2000)}

        assert drawn == set(range(2, 19))

    def test_a_one_frame_recording_has_only_its_frame(self):
        """Frame 0, whatever the stream."""
        assert {
            poster_frame(frame_count=1, stream=random.Random(seed)) for seed in POSTER_SEEDS
        } == {0}

    @pytest.mark.parametrize('frame_count', [0, -1])
    def test_an_empty_recording_has_no_poster(self, frame_count: int):
        """No frame to show: a ``ValueError``."""
        with pytest.raises(ValueError, match='no frame'):
            poster_frame(frame_count=frame_count, stream=random.Random(0))


class TestOutcomes:
    """How a player stands (decision 10); a failing player never touches the others."""

    @staticmethod
    def play_beside(
        *, player: DemoPlayer, healthy: DemoPlayer, clock: FrameCostClock, ticks: int
    ) -> None:
        """Tick a player and a healthy one in turn; the healthy one must loop and play on."""
        for _tick in range(ticks):
            for each in (player, healthy):
                tick(player=each, clock=clock, frames_of_time=1, budget_frames=1)
        assert healthy.outcome.state in {DemoState.PLAYING, DemoState.LOOPED}
        assert healthy.generation > 1
        assert healthy.outcome.error is None

    @staticmethod
    def make_healthy(*, rally: InstalledStandIn, players: Players) -> DemoPlayer:
        """Make a player of a recording that plays and loops as it should, first.

        Returns:
            The player.

        """
        return players.make(command=rally.command, recording=rally.other_recording)

    def test_a_missing_recording_could_not_start(
        self, rally: InstalledStandIn, players: Players, tmp_path: Path
    ):
        """Nothing built, no surface, the reason kept; ticks run nothing."""
        healthy = self.make_healthy(rally=rally, players=players)
        player = players.make(command=rally.command, recording=tmp_path / 'gone.jsonl.gz')

        self.play_beside(player=player, healthy=healthy, clock=players.clock, ticks=30)

        outcome = player.outcome
        assert outcome.state is DemoState.COULD_NOT_START
        assert outcome.error is not None
        assert 'gone.jsonl.gz' in outcome.error
        assert player.surface is None
        assert player.inner_game is None
        assert player.generation == 0
        assert player.frames_played == 0
        assert player.audible is False
        assert player.frame_count == 0
        player.set_audible(audible=True)
        assert player.audible is False

    def test_an_unreadable_recording_could_not_start(
        self, rally: InstalledStandIn, players: Players, tmp_path: Path
    ):
        """Not a trace: the trace reader's reason."""
        healthy = self.make_healthy(rally=rally, players=players)
        unreadable = tmp_path / 'unreadable.jsonl.gz'
        unreadable.write_bytes(b'not a gzip trace at all')
        player = players.make(command=rally.command, recording=unreadable)

        self.play_beside(player=player, healthy=healthy, clock=players.clock, ticks=30)

        assert player.outcome.state is DemoState.COULD_NOT_START
        assert player.outcome.error is not None
        assert 'not a gzip trace' in player.outcome.error

    def test_a_recording_with_no_screen_size_could_not_start(
        self, rally: InstalledStandIn, players: Players, tmp_path: Path
    ):
        """Its tile's size is unknown (decision 13)."""
        healthy = self.make_healthy(rally=rally, players=players)
        sizeless = tmp_path / 'sizeless.jsonl.gz'
        write_header_only_recording(path=sizeless, header={'game': 'stand_in'})
        player = players.make(command=rally.command, recording=sizeless)

        self.play_beside(player=player, healthy=healthy, clock=players.clock, ticks=30)

        assert player.outcome.state is DemoState.COULD_NOT_START
        assert player.outcome.error is not None
        assert 'screen size' in player.outcome.error

    def test_a_command_that_is_not_installed_could_not_start(
        self,
        rally: InstalledStandIn,
        players: Players,
    ):
        """The build failed: the game's error kept, its blank surface readable."""
        healthy = self.make_healthy(rally=rally, players=players)
        player = players.make(command='no-such-command-anywhere', recording=rally.recording)

        self.play_beside(player=player, healthy=healthy, clock=players.clock, ticks=30)

        assert player.outcome.state is DemoState.COULD_NOT_START
        assert player.outcome.error is not None
        assert 'no-such-command-anywhere' in player.outcome.error
        assert player.surface is not None
        assert player.generation == 1

    def test_a_refused_argument_could_not_start(
        self,
        rally: InstalledStandIn,
        players: Players,
    ):
        """The inner game's refusal is the player's reason, nothing built."""
        healthy = self.make_healthy(rally=rally, players=players)
        player = players.make(
            command=rally.command, recording=rally.recording, arguments=('--audit',)
        )

        self.play_beside(player=player, healthy=healthy, clock=players.clock, ticks=30)

        assert player.outcome.state is DemoState.COULD_NOT_START
        assert player.outcome.error is not None
        assert '--audit' in player.outcome.error
        assert player.inner_game is None

    def test_a_scene_that_raises_crashes_frozen_on_its_last_frame(
        self,
        rally: InstalledStandIn,
        players: Players,
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ):
        """CRASHED with the traceback logged; the last frame drawn stays; never rebuilt."""
        healthy = self.make_healthy(rally=rally, players=players)
        player = players.make(
            command=rally.command,
            recording=rally.recording,
            on_new_game=scene_that_raises(on_frame=CRASH_FRAME, mocker=mocker),
        )
        last_drawn: str | None = None
        for _tick in range(CRASH_FRAME):
            if tick(player=player, clock=players.clock, frames_of_time=1, budget_frames=1):
                last_drawn = pixel_hash(player.surface)

        self.play_beside(player=player, healthy=healthy, clock=players.clock, ticks=30)

        outcome = player.outcome
        assert outcome.state is DemoState.CRASHED
        assert outcome.error == 'RuntimeError: the scene broke'
        assert player.frame_index == CRASH_FRAME - 1
        assert last_drawn is not None
        assert pixel_hash(player.surface) == last_drawn
        assert player.generation == 1
        assert any(
            record.levelname == 'ERROR' and record.exc_info is not None for record in caplog.records
        )

    def test_a_scene_that_raises_on_its_first_frame_could_not_start(
        self, rally: InstalledStandIn, players: Players, mocker: MockerFixture
    ):
        """No frame ran: COULD_NOT_START with the error (decision 10), never rebuilt."""
        healthy = self.make_healthy(rally=rally, players=players)
        player = players.make(
            command=rally.command,
            recording=rally.recording,
            on_new_game=scene_that_raises(on_frame=1, mocker=mocker),
        )

        self.play_beside(player=player, healthy=healthy, clock=players.clock, ticks=30)

        assert player.outcome.state is DemoState.COULD_NOT_START
        assert player.outcome.error == 'RuntimeError: the scene broke'
        assert player.frame_index == 0
        assert player.generation == 1

    def test_a_divergence_restarts_once_then_freezes_on_the_diverged_frame(
        self,
        rally: InstalledStandIn,
        players: Players,
        caplog: pytest.LogCaptureFixture,
    ):
        """Owner decision 4: rebuilt after the first, frozen with DIVERGED after the second."""
        healthy = self.make_healthy(rally=rally, players=players)
        tamper_first_sprite_rect(recording_path=rally.recording, frame_number=TAMPERED_FRAME)
        caplog.set_level('WARNING', logger='game.demo_player')
        player = players.make(command=rally.command, recording=rally.recording)

        tick_until_generation(player=player, clock=players.clock, generation=2)
        assert player.outcome.state is DemoState.LOOPED
        restarts_logged = [record for record in caplog.records if record.name == 'game.demo_player']
        assert len(restarts_logged) == 1
        assert 'restarting once' in restarts_logged[0].getMessage()
        tick_until_state(player=player, clock=players.clock, state=DemoState.DIVERGED)
        frozen_on = pixel_hash(player.surface)
        frozen_at = player.frame_index

        self.play_beside(player=player, healthy=healthy, clock=players.clock, ticks=30)

        outcome = player.outcome
        assert outcome.state is DemoState.DIVERGED
        assert outcome.report is not None
        assert outcome.report.startswith(f'Replay diverged at frame {TAMPERED_FRAME}')
        assert player.generation == 2
        assert player.frame_index == frozen_at
        assert pixel_hash(player.surface) == frozen_on
        logged = [record for record in caplog.records if record.name == 'game.demo_player']
        assert len(logged) == 2
        assert 'frozen' in logged[1].getMessage()
        assert player.audible is False

    def test_the_first_divergence_reads_playing_until_its_rebuild(
        self, rally: InstalledStandIn, players: Players
    ):
        """The diverging frame spends the tick's budget: no DIVERGED before the restart (rule 4).

        DIVERGED means frozen, so a host reading it in that window would show the error label,
        or finish a tile that gets one more try (the owner's decision 4).
        """
        tamper_first_sprite_rect(recording_path=rally.recording, frame_number=TAMPERED_FRAME)
        player = players.make(command=rally.command, recording=rally.recording)
        inner_game = player.inner_game
        assert inner_game is not None
        states: list[DemoState] = []

        for _tick in range(MOST_TICKS):
            tick(player=player, clock=players.clock, frames_of_time=1, budget_frames=1)
            if player.generation > 1:
                break
            states.append(player.outcome.state)

        assert inner_game.outcome.diverged is True
        assert states
        assert set(states) == {DemoState.PLAYING}
        assert player.outcome.state is DemoState.LOOPED

    def test_a_recording_longer_than_the_run_is_a_divergence(
        self,
        rally: InstalledStandIn,
        players: Players,
    ):
        """A length divergence (the game quit before the recording ended): DIVERGED, frozen."""
        healthy = self.make_healthy(rally=rally, players=players)
        lengthen(recording=rally.recording)
        player = players.make(command=rally.command, recording=rally.recording)

        tick_until_state(player=player, clock=players.clock, state=DemoState.DIVERGED)
        self.play_beside(player=player, healthy=healthy, clock=players.clock, ticks=30)

        assert player.outcome.state is DemoState.DIVERGED
        assert player.outcome.report is not None
        assert 'length' in player.outcome.report
        assert player.generation == 2

    def test_a_game_that_could_not_start_after_a_loop_stops(
        self, rally: InstalledStandIn, players: Players, mocker: MockerFixture
    ):
        """The second build failing (an injected failure): COULD_NOT_START with its error."""
        player = players.make(command=rally.command, recording=rally.recording)
        # An injected failure of every later build: its begin_frames raises
        mocker.patch.object(
            SceneManager, 'begin_frames', side_effect=RuntimeError('no frames this time')
        )

        tick_until_generation(player=player, clock=players.clock, generation=2)
        tick(player=player, clock=players.clock, frames_of_time=1, budget_frames=1)

        assert player.outcome.state is DemoState.COULD_NOT_START
        assert player.outcome.error == 'RuntimeError: no frames this time'
        assert player.generation == 2

    def test_the_outcome_is_a_frozen_model(self):
        """Read-only, and refuses unknown fields."""
        fields = {'state': DemoState.PLAYING, 'error': None, 'report': None}

        assert DemoOutcome.model_config.get('frozen') is True
        assert DemoOutcome.model_validate(fields).state is DemoState.PLAYING
        with pytest.raises(ValueError, match='extra'):
            DemoOutcome.model_validate({**fields, 'unknown': 1})


class TestFinishing:
    """The host finishes a player it drops: its game gives its channels back, nothing runs."""

    def test_a_finished_player_holds_no_channel_and_runs_nothing(
        self,
        rally: InstalledStandIn,
        players: Players,
    ):
        """Finished mid-game: its context's partition is gone; later ticks run no frame."""
        player = players.make(command=rally.command, recording=rally.recording)
        tick(player=player, clock=players.clock, frames_of_time=3, budget_frames=100)
        inner_game = player.inner_game
        assert inner_game is not None

        player.finish()
        player.finish()

        assert inner_game.context.value(slot=INNER_CHANNELS_SLOT).partition is None
        assert tick(player=player, clock=players.clock, frames_of_time=3, budget_frames=100) == 0
        assert player.fast_forward(to_frame=5, budget=players.clock.budget(frame_count=1)) is False


def test_the_module_imports_no_game_and_reads_no_clock_but_the_budgets():
    """The guard: only the engine pieces it needs, and no time read of its own (decision 5)."""
    source = Path(demo_player_module.__file__).read_text(encoding='utf-8')
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            imported.add(module)
            imported.update(f'{module}.{alias.name}' for alias in node.names)
    named = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}

    modules = {name for name in imported if name in ALLOWED_IMPORTS or '.' not in name}
    assert modules <= ALLOWED_IMPORTS, modules - ALLOWED_IMPORTS
    assert not imported & TIME_MODULES
    assert not any(name.startswith('glitchygames.clock') for name in imported)
    assert 'clock' not in named
